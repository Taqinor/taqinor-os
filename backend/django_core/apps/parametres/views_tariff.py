"""N64/N65 — Vues « Tarification & ROI ».

Éditeur du barème ONEE + hypothèses ROI/productible (Paramètres → Tarification
& ROI). Lecture pour tout rôle ; écriture réservée à Admin/Responsable promu.
``company`` est résolue côté serveur (jamais lue du corps). À chaque sauvegarde
modifiée, ``version`` est incrémentée et chaque champ modifié est journalisé
(SettingsAuditLog).

Deux endpoints de calcul (lecture seule, tout rôle) exposent le service :
* ``compute-roi`` : facture mensuelle ONEE + ROI à partir de kWc/conso/coût.
* ``productible`` : productible PVGIS au point GPS exact (repli manuel
  hors-ligne — fonctionne sans réseau).
"""
from django.db.models import F
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import (
    OpenApiParameter, extend_schema, inline_serializer,
)
from rest_framework import serializers
from rest_framework.decorators import (
    api_view, parser_classes, permission_classes,
)
from rest_framework.parsers import JSONParser
from rest_framework.response import Response

from authentication.permissions import (
    HasPermissionOrLegacy, IsAdminOrResponsableTier, IsAnyRole,
)
from core.champs_stricts import ChaineStricte, entier_ou_400, nombre_ou_400

from .erreurs_metier import valider_ou_conflit
from .models import SettingsAuditLog
from .models_tariff import TariffSettings
from .serializers_tariff import (
    CHAMPS_LOT5, CHAMPS_POMPAGE, TariffSettingsSerializer)
from .requetes_strictes import FlottantStrict, valider_corps
from .views_common import _audit_company
from . import tariff as tariff_service
from . import pvgis as pvgis_client


# Libellé FR par champ pour l'audit (N55).
_TARIFF_AUDIT_FIELDS = {
    'residential_tiers': "Barème ONEE résidentiel",
    'tolerance_kwh': "Tolérance (kWh)",
    'selective_threshold_kwh': "Seuil progressif/sélectif (kWh)",
    'force_motrice_prix_kwh_ttc': "Tarif force motrice / agricole",
    'surplus_injecte_compense': "Surplus injecté compensé",
    'surplus_prix_kwh_ttc': "Tarif de rachat du surplus",
    'autoconsommation_pct_defaut': "Autoconsommation par défaut (%)",
    'pertes_systeme_pct': "Pertes système (%)",
    'pvgis_actif': "PVGIS actif",
    'productible_manuel_kwh_kwc': "Productible manuel (kWh/kWc/an)",
    'inclinaison_defaut_deg': "Inclinaison par défaut (°)",
    'azimut_defaut_deg': "Azimut par défaut (°)",
}

# CALX72/CALX284 — les réglages du lot 5 (TOU, compensation, structure, taxes,
# indexation, fiscalité) entrent dans l'audit de version : un champ servi à
# l'écran sans trace d'audit dériverait en silence. Libellés = verbose_name du
# modèle, une seule source.
_TARIFF_AUDIT_FIELDS.update({
    champ: str(TariffSettings._meta.get_field(champ).verbose_name)
    for champ in CHAMPS_LOT5 + CHAMPS_POMPAGE
    if champ not in _TARIFF_AUDIT_FIELDS
})


def _settings(request):
    """TariffSettings de la société de l'utilisateur (get-or-create)."""
    return TariffSettings.get(
        company=request.user.company if request.user.company_id else None
    )


@extend_schema(responses=TariffSettingsSerializer)
@api_view(['GET'])
@permission_classes([IsAnyRole])
def get_tariff_settings(request):
    obj = _settings(request)
    return Response(TariffSettingsSerializer(obj).data)


@extend_schema(request=TariffSettingsSerializer,
               responses=TariffSettingsSerializer)
@api_view(['PUT', 'PATCH'])
@parser_classes([JSONParser])  # ENF8 (D2) — aucun upload
# ASEC31 — écriture des réglages société : palier ET droit
# `parametres_modifier` (D-ASEC-4/5 : Admin RH, Technicien responsable
# n'y touchent plus).
@permission_classes([IsAdminOrResponsableTier,
                     HasPermissionOrLegacy('parametres_modifier')])
def update_tariff_settings(request):
    obj = _settings(request)
    partial = request.method == 'PATCH'
    before = {f: getattr(obj, f, None) for f in _TARIFF_AUDIT_FIELDS}
    serializer = TariffSettingsSerializer(
        obj, data=request.data, partial=partial,
        context={'request': request},
    )
    # ENF11 — les refus de règle métier (source obligatoire, coefficient…) sur
    # un corps conforme au schéma répondent 409, pas 400.
    valider_ou_conflit(serializer)
    updated = serializer.save()

    # Détecte un vrai changement (un seul champ suffit) → version + audit.
    changed = False
    company = _audit_company(request)
    for field, label in _TARIFF_AUDIT_FIELDS.items():
        old = before.get(field)
        new = getattr(updated, field, None)
        if old == new:
            continue
        changed = True
        SettingsAuditLog.log_change(
            company=company, user=request.user, section='tarification',
            field=field, field_label=label, old=old, new=new,
        )
    if changed:
        # AUD829 — F() atomic increment: a bare read-decide-write
        # (updated.version = updated.version + 1; save()) loses an update
        # under two concurrent PUT/PATCH (lost-update anomaly on the
        # tarification version counter itself).
        TariffSettings.objects.filter(pk=updated.pk).update(
            version=F('version') + 1)
        updated.refresh_from_db(fields=['version'])

    return Response(TariffSettingsSerializer(updated).data)


#: Bornes du calcul ROI (publiées au schéma) : au-delà, l'arithmétique Decimal
#: du service débordait (500). Ordres de grandeur sans rapport avec un projet
#: réel (1e9 kWh/mois, 1e12 MAD) : aucune valeur utile n'est refusée.
_BORNE_NOMBRE = 1e9
_BORNE_COUT = 1e12


class CalculRoiRequestSerializer(serializers.Serializer):
    """Corps de ``POST tarification/roi/`` — source du schéma ET de la
    validation (ENF11). Nombres JSON réels uniquement : une chaîne, un objet ou
    une valeur démesurée répond 400 au lieu d'être remplacé par 0 en silence
    (200) ou de lever dans le calcul (500)."""

    kwc = FlottantStrict(
        required=False, min_value=-_BORNE_NOMBRE, max_value=_BORNE_NOMBRE)
    conso_mensuelle_kwh = FlottantStrict(
        required=False, min_value=-_BORNE_NOMBRE, max_value=_BORNE_NOMBRE)
    cout_total_ttc = FlottantStrict(
        required=False, min_value=-_BORNE_COUT, max_value=_BORNE_COUT)
    classe = ChaineStricte(required=False, allow_blank=True)
    autoconsommation_pct = FlottantStrict(
        required=False, allow_null=True,
        min_value=-_BORNE_NOMBRE, max_value=_BORNE_NOMBRE)
    productible_kwh_kwc = FlottantStrict(
        required=False, allow_null=True,
        min_value=-_BORNE_NOMBRE, max_value=_BORNE_NOMBRE)


_ROI_REQUEST = CalculRoiRequestSerializer


def _q(nom, type_, description):
    return OpenApiParameter(
        nom, type_, OpenApiParameter.QUERY, required=False,
        description=description)


@extend_schema(
    request=_ROI_REQUEST,
    responses={200: {'type': 'object', 'additionalProperties': {
        'type': 'string', 'nullable': True}}})
@api_view(['POST'])
@permission_classes([IsAnyRole])
@parser_classes([JSONParser])  # ENF8 (D2) — aucun upload
def compute_roi(request):
    """Calcule la facture ONEE mensuelle + le ROI conservateur.

    Corps : {kwc, conso_mensuelle_kwh, cout_total_ttc, classe?,
             autoconsommation_pct?, productible_kwh_kwc?}.
    Tous les montants sortent en chaînes (Decimal sérialisé)."""
    obj = _settings(request)
    data = valider_corps(CalculRoiRequestSerializer, request)
    classe = data.get('classe', 'residentiel')
    conso = data.get('conso_mensuelle_kwh', 0)
    result = tariff_service.compute_roi(
        obj,
        kwc=data.get('kwc', 0),
        conso_mensuelle_kwh=conso,
        cout_total_ttc=data.get('cout_total_ttc', 0),
        classe=classe,
        autoconsommation_pct=data.get('autoconsommation_pct'),
        productible_kwh_kwc=data.get('productible_kwh_kwc'),
    )
    result['facture_mensuelle_ttc'] = tariff_service.monthly_bill(
        obj, conso, classe)
    # Decimal → str pour une sérialisation JSON sans perte.
    out = {k: (str(v) if v is not None else None) for k, v in result.items()}
    return Response(out)


@extend_schema(
    parameters=[
        _q('lat', OpenApiTypes.DOUBLE, 'Latitude (degrés).'),
        _q('lon', OpenApiTypes.DOUBLE, 'Longitude (degrés).'),
        _q('peakpower', OpenApiTypes.DOUBLE, 'Puissance crête (kWc).'),
        _q('tilt', OpenApiTypes.INT, 'Inclinaison (degrés).'),
        _q('azimuth', OpenApiTypes.INT, 'Azimut (degrés).'),
    ],
    responses=inline_serializer('ProductibleReponse', {
        'source': serializers.CharField(),
        'productible_kwh_kwc': serializers.FloatField(),
        'production_mensuelle_kwh_kwc': serializers.ListField(
            child=serializers.FloatField(), allow_null=True),
        'reason': serializers.CharField(allow_null=True),
    }))
@api_view(['GET'])
@permission_classes([IsAnyRole])
def get_productible(request):
    """Productible PVGIS au point GPS (lat/lon) ; repli manuel hors-ligne.

    Query : lat, lon, peakpower? (kWc), tilt?, azimuth?. Ne lève jamais : si
    PVGIS est injoignable (réseau bloqué), retourne la source 'manual'."""
    obj = _settings(request)
    # ENF11 — le schéma déclare des NOMBRES : une valeur illisible est un 400
    # nommant le paramètre (``int('abc')`` levait un 500) ; absent/vide garde
    # le repli documenté (coordonnées manquantes → productible manuel).
    params = request.query_params
    lat = nombre_ou_400(params.get('lat'), 'lat')
    lon = nombre_ou_400(params.get('lon'), 'lon')
    peak = nombre_ou_400(params.get('peakpower'), 'peakpower', defaut=1.0)
    tilt = entier_ou_400(params.get('tilt'), 'tilt', maxi=2147483647)
    azimuth = entier_ou_400(params.get('azimuth'), 'azimuth', maxi=2147483647)
    result = pvgis_client.fetch_productible(
        obj, lat, lon, peakpower_kwc=peak, tilt=tilt, azimuth=azimuth)
    return Response(result)
