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
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from authentication.permissions import IsAdminOrResponsableTier, IsAnyRole
from .models import SettingsAuditLog
from .models_tariff import TariffSettings
from .serializers_tariff import TariffSettingsSerializer
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


def _settings(request):
    """TariffSettings de la société de l'utilisateur (get-or-create)."""
    return TariffSettings.get(
        company=request.user.company if request.user.company_id else None
    )


@api_view(['GET'])
@permission_classes([IsAnyRole])
def get_tariff_settings(request):
    obj = _settings(request)
    return Response(TariffSettingsSerializer(obj).data)


@api_view(['PUT', 'PATCH'])
@permission_classes([IsAdminOrResponsableTier])
def update_tariff_settings(request):
    obj = _settings(request)
    partial = request.method == 'PATCH'
    before = {f: getattr(obj, f, None) for f in _TARIFF_AUDIT_FIELDS}
    serializer = TariffSettingsSerializer(
        obj, data=request.data, partial=partial,
        context={'request': request},
    )
    serializer.is_valid(raise_exception=True)
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
        updated.version = (updated.version or 1) + 1
        updated.save(update_fields=['version'])

    return Response(TariffSettingsSerializer(updated).data)


def _num(data, key, default=0):
    try:
        return float(data.get(key, default))
    except (TypeError, ValueError):
        return default


@api_view(['POST'])
@permission_classes([IsAnyRole])
def compute_roi(request):
    """Calcule la facture ONEE mensuelle + le ROI conservateur.

    Corps : {kwc, conso_mensuelle_kwh, cout_total_ttc, classe?,
             autoconsommation_pct?, productible_kwh_kwc?}.
    Tous les montants sortent en chaînes (Decimal sérialisé)."""
    obj = _settings(request)
    data = request.data or {}
    classe = data.get('classe', 'residentiel')
    conso = _num(data, 'conso_mensuelle_kwh', 0)

    auto = data.get('autoconsommation_pct', None)
    prod = data.get('productible_kwh_kwc', None)
    result = tariff_service.compute_roi(
        obj,
        kwc=_num(data, 'kwc', 0),
        conso_mensuelle_kwh=conso,
        cout_total_ttc=_num(data, 'cout_total_ttc', 0),
        classe=classe,
        autoconsommation_pct=auto if auto not in (None, '') else None,
        productible_kwh_kwc=prod if prod not in (None, '') else None,
    )
    result['facture_mensuelle_ttc'] = tariff_service.monthly_bill(
        obj, conso, classe)
    # Decimal → str pour une sérialisation JSON sans perte.
    out = {k: (str(v) if v is not None else None) for k, v in result.items()}
    return Response(out)


@api_view(['GET'])
@permission_classes([IsAnyRole])
def get_productible(request):
    """Productible PVGIS au point GPS (lat/lon) ; repli manuel hors-ligne.

    Query : lat, lon, peakpower? (kWc), tilt?, azimuth?. Ne lève jamais : si
    PVGIS est injoignable (réseau bloqué), retourne la source 'manual'."""
    obj = _settings(request)
    lat = request.query_params.get('lat')
    lon = request.query_params.get('lon')
    peak = request.query_params.get('peakpower', 1.0)
    tilt = request.query_params.get('tilt', None)
    azimuth = request.query_params.get('azimuth', None)
    try:
        peak = float(peak)
    except (TypeError, ValueError):
        peak = 1.0
    result = pvgis_client.fetch_productible(
        obj, lat, lon, peakpower_kwc=peak,
        tilt=int(tilt) if tilt not in (None, '') else None,
        azimuth=int(azimuth) if azimuth not in (None, '') else None,
    )
    return Response(result)
