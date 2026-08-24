"""CJ2a — Aperçu générateur du moteur horaire : POST /ventes/etude-horaire/preview/.

C'EST LA SOURCE UNIQUE DES CHIFFRES D'ÉCONOMIE RÉSIDENTIELS. L'écran générateur
(CJ2b) appellera CET endpoint au lieu de recalculer de son côté : c'est la fin
du miroir JS ↔ Python pour CES chiffres-là. Le devis enregistré et l'aperçu à
l'écran passent par le MÊME code, donc ne peuvent plus diverger.

Deux usages, un seul endpoint :

* **avec ``kwc``** — « voici ce que donne CETTE taille » : le bloc d'étude
  horaire complet (12 mois, 3 saisons, l'année), sans et avec batterie ;
* **avec ``dimensionner``** — « quelle taille pour ce client ? » : le TABLEAU
  de toutes les tailles candidates plus la recommandation motivée. C'est le
  successeur de la règle « 900 DH/mois ».

Les deux se demandent ensemble.

DIM2 (fondateur 24/08/2026) — le bloc ``dimensionnement`` porte désormais DEUX
dimensions : la taille du champ ET le stockage. Chaque ligne du tableau expose
son ``balayage_stockage`` (les paliers de batteries réellement composables, avec
coût, économie marginale, résiduel et taux de remplissage), le palier REFUSÉ qui
prouve la borne (« batteries toujours pleines »), les colonnes
``residuel_kwh_mois`` / ``tranche_apres`` qui rendent la marche du barème
visible, et le bloc rend en plus ``recommandation_avec``, ``falaise`` et
``meilleure_falaise``. Forme exacte : ``contract_samples/etude_horaire.json``.

AUCUNE ÉCRITURE : ni devis, ni statut, ni ligne. C'est un calculateur — comme
``roof_load_view``, dont il reprend la forme (fonction ``@api_view``, jamais
une action de ViewSet, donc AUCUN piège ``get_permissions``).

Company-scopé : la société vient TOUJOURS de ``request.user``, jamais du corps
de la requête. Un ``devis`` demandé est résolu dans la société de l'appelant
uniquement.
"""
from __future__ import annotations

import logging

from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import serializers
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from authentication.permissions import IsAnyRole

logger = logging.getLogger(__name__)

#: Occupations acceptées — celles que le serveur sait servir
#: (``courbes_journalieres``). Une valeur hors liste est ignorée (repli
#: documenté), jamais une erreur : l'aperçu doit toujours répondre.
OCCUPATIONS = ('presence_jour', 'absence_jour', 'presence_partielle')


def _num(valeur, defaut=None):
    """Flottant tolérant préservant ``None`` (jamais un 0 fabriqué)."""
    if valeur in (None, ''):
        return defaut
    try:
        return float(valeur)
    except (TypeError, ValueError):
        return defaut


def _devis_de_la_societe(request, devis_id):
    """Devis demandé, SCOPÉ à la société de l'appelant, ou ``None``.

    Le scoping est la raison d'être de cette fonction : un identifiant de devis
    fourni dans le corps ne doit JAMAIS permettre de lire le profil d'un client
    d'une autre société.
    """
    if not devis_id:
        return None
    from .models import Devis
    user = request.user
    qs = Devis.objects.all()
    company_id = getattr(user, 'company_id', None)
    if company_id:
        qs = qs.filter(company_id=company_id)
    elif not user.is_superuser:
        return None
    return qs.filter(pk=devis_id).first()


def _profil_depuis_corps(corps):
    """Profil de consommation depuis le corps brut de la requête.

    Chemin SANS devis persisté : le commercial saisit les réponses du script
    d'appel et voit immédiatement le résultat. Mêmes fonctions que le chemin
    devis — aucune règle dupliquée.
    """
    from .courbes_journalieres import composer_equipements
    from .etude_horaire import profil_depuis_factures

    conso, source, detail = profil_depuis_factures(
        facture_hiver_mad=_num(corps.get('facture_hiver')),
        facture_ete_mad=_num(corps.get('facture_ete')),
        ete_differente=bool(corps.get('ete_differente')),
        factures_mensuelles_mad=corps.get('factures_mensuelles'),
        conso_kwh_mensuelles=corps.get('conso_kwh_mensuelles'))

    occupation = corps.get('occupation')
    if occupation not in OCCUPATIONS:
        occupation = None
    equipements = composer_equipements(corps.get('equipements') or {})
    return conso, source, detail, occupation, equipements


def _profil_depuis_devis(devis, corps):
    """Profil de consommation lu sur un devis et son lead (sélecteurs CRM)."""
    from apps.crm.selectors import lead_bills_for_devis

    from .courbes_journalieres import equipements_du_devis, occupation_du_devis
    from .etude_horaire import profil_depuis_factures

    bills = lead_bills_for_devis(devis) or {}
    etude_params = getattr(devis, 'etude_params', None) or {}
    conso, source, detail = profil_depuis_factures(
        facture_hiver_mad=bills.get('facture_hiver'),
        facture_ete_mad=bills.get('facture_ete'),
        ete_differente=bills.get('ete_differente'),
        factures_mensuelles_mad=etude_params.get('factures_mensuelles_reelles'),
        conso_kwh_mensuelles=etude_params.get('conso_kwh_mensuelles'))

    occupation, _source_occ = occupation_du_devis(devis, corps)
    equipements = equipements_du_devis(devis)
    return conso, source, detail, occupation, equipements


# SCHÉMA RÉELLEMENT DÉCLARÉ, PAS BASELINÉ NI VIDE.
#
# Deux facilités étaient possibles ici, toutes deux refusées :
#   · baseliner l'endpoint dans ``scripts/openapi_schema_allow.txt`` comme le
#     calculateur voisin ``roof_load_check`` — un aveu toléré, mais cet
#     endpoint EST le contrat que l'écran CJ2b consommera ;
#   · déclarer ``OpenApiTypes.OBJECT`` — un « type: object » sans aucune
#     propriété, qui valide TOUT et ne protège donc RIEN (exactement ce que
#     déclarait /ao/tableau-marches/ le jour où l'écran a planté, 03/08/2026 —
#     `check_openapi_shapes.py` le refuse, à raison).
#
# On déclare donc les cinq clés de premier niveau, avec leur nullabilité. Le
# DÉTAIL d'``etude``/``dimensionnement`` reste décrit par
# ``contract_samples/etude_horaire.json`` (PACT10), vérifié par
# ``check_api_shapes.py`` : le recopier en sérialiseur imbriqué créerait une
# SECONDE définition à maintenir en parallèle, ce que PACT10 interdit
# précisément.
@extend_schema(
    request=inline_serializer('EtudeHorairePreviewRequest', {
        'devis': serializers.IntegerField(
            required=False, help_text='Profil lu sur ce devis (scopé société)'),
        'ville': serializers.CharField(required=False),
        'lat': serializers.FloatField(required=False),
        'lon': serializers.FloatField(required=False),
        'facture_hiver': serializers.FloatField(
            required=False, help_text='MAD/mois — ancrage réel'),
        'facture_ete': serializers.FloatField(required=False),
        'ete_differente': serializers.BooleanField(required=False),
        'factures_mensuelles': serializers.ListField(
            child=serializers.FloatField(), required=False,
            help_text='12 factures MAD réelles'),
        'conso_kwh_mensuelles': serializers.ListField(
            child=serializers.FloatField(), required=False,
            help_text='12 consommations kWh saisies'),
        'occupation': serializers.ChoiceField(
            choices=OCCUPATIONS, required=False),
        'equipements': serializers.DictField(required=False),
        'raccordement': serializers.CharField(required=False),
        'kwc': serializers.FloatField(required=False),
        'batterie_kwh': serializers.FloatField(required=False),
        'dimensionner': serializers.BooleanField(required=False),
        'critere': serializers.CharField(required=False),
    }),
    responses={
        200: inline_serializer('EtudeHorairePreviewResponse', {
            'etude': serializers.JSONField(
                allow_null=True,
                help_text="Bloc etude_horaire (12 mois, 3 saisons, annuel) — "
                          "null quand rien n'est calculable"),
            'dimensionnement': serializers.JSONField(
                allow_null=True,
                help_text='Tableau des tailles × paliers de STOCKAGE (DIM2) + '
                          'recommandations motivées (sans batterie et avec) + '
                          'la marche du barème et la première combinaison qui '
                          'la franchit — null si non demandé ou non calculable'),
            'consommation': inline_serializer('EtudeHoraireConsommation', {
                'source': serializers.CharField(),
                'kwh_mensuels': serializers.ListField(
                    child=serializers.FloatField()),
                'detail': serializers.JSONField(),
            }),
            'profil': inline_serializer('EtudeHoraireProfil', {
                'occupation': serializers.CharField(allow_null=True),
                'equipements_actifs': serializers.ListField(
                    child=serializers.CharField()),
            }),
            'avertissements': serializers.ListField(
                child=serializers.CharField()),
        }),
        400: inline_serializer('EtudeHorairePreviewErreur', {
            'detail': serializers.CharField(),
        }),
    },
    summary="CJ2a — étude horaire + dimensionnement (aperçu, aucune écriture)",
    description=(
        "Économies résidentielles calculées par intégration HORAIRE de la "
        "production PVGIS réelle contre la courbe de consommation réelle du "
        "client, mois par mois, valorisées au barème ONEE. Renvoie aussi, sur "
        "demande (`dimensionner: true`), le tableau des tailles candidates et "
        "la taille recommandée. Forme exacte de la réponse : "
        "apps/ventes/contract_samples/etude_horaire.json."),
)
@api_view(['POST'])
@permission_classes([IsAnyRole])
def etude_horaire_preview(request):
    """CJ2a — Aperçu du moteur horaire + dimensionnement, SANS devis persisté.

    Corps accepté (tout est optionnel sauf de quoi ancrer un calcul) ::

        {
          "devis": 123,                  // profil lu sur ce devis (scopé société)
          "ville": "Casablanca",         // sinon ville du chantier du devis
          "lat": 33.57, "lon": -7.59,    // PVGIS live au point exact
          "facture_hiver": 1200,         // MAD/mois — ancrage réel
          "facture_ete": 1600, "ete_differente": true,
          "factures_mensuelles": [12 MAD],
          "conso_kwh_mensuelles": [12 kWh],
          "occupation": "presence_jour",
          "equipements": {"piscine": true, "piscine_pompe_kw": 1.1, ...},
          "raccordement": "monophase",   // PVCOMPAT — vivier onduleurs
          "kwc": 6.0,                    // étude de CETTE taille
          "batterie_kwh": 10,
          "dimensionner": true,          // + tableau des tailles candidates
          "critere": "meilleur_payback"
        }

    Réponse ``200`` toujours de la MÊME FORME (contrat PACT10
    ``contract_samples/etude_horaire.json``) : ``etude`` et ``dimensionnement``
    valent ``null`` quand ils ne sont pas calculables, jamais une clé absente —
    l'écran n'a ainsi jamais à deviner.

    ``400`` seulement quand le corps est inexploitable (pas un objet JSON).
    """
    corps = request.data if isinstance(request.data, dict) else None
    if corps is None:
        return Response(
            {'detail': 'Corps de requête invalide : un objet JSON est attendu.'},
            status=400)

    company = getattr(request.user, 'company', None)
    avertissements = []

    devis = _devis_de_la_societe(request, corps.get('devis'))
    if corps.get('devis') and devis is None:
        avertissements.append(
            'Devis introuvable dans votre société — profil lu depuis le corps '
            'de la requête.')

    if devis is not None:
        conso, source, detail, occupation, equipements = _profil_depuis_devis(
            devis, corps)
        company = getattr(devis, 'company', None) or company
    else:
        conso, source, detail, occupation, equipements = _profil_depuis_corps(
            corps)

    ville, lat, lon = _localisation(corps, devis)

    if not conso:
        avertissements.append(
            "Aucune facture exploitable : sans ancrage réel, le moteur ne "
            "calcule rien plutôt que d'afficher une estimation déguisée en "
            "mesure.")
        return Response(_reponse(
            None, None, conso, source, detail, occupation, equipements,
            avertissements))

    from .etude_horaire import calculer_etude_horaire

    etude = None
    kwc = _num(corps.get('kwc'))
    if kwc and kwc > 0:
        etude = calculer_etude_horaire(
            kwc=kwc, conso_kwh_mensuelles=conso, ville=ville, lat=lat, lon=lon,
            occupation=occupation, equipements=equipements,
            batterie_kwh_utile=_num(corps.get('batterie_kwh')),
            source_conso=source, detail_conso=detail)
        if etude is None:
            avertissements.append(
                'Étude non calculable pour cette taille : localisation du '
                'chantier non résolue par PVGIS (ni GPS, ni ville reconnue).')

    dimensionnement = None
    if corps.get('dimensionner'):
        dimensionnement = _dimensionner(
            company=company, conso=conso, ville=ville, lat=lat, lon=lon,
            occupation=occupation, equipements=equipements, corps=corps,
            source=source, avertissements=avertissements)

    return Response(_reponse(
        etude, dimensionnement, conso, source, detail, occupation,
        equipements, avertissements))


def _localisation(corps, devis):
    """(ville, lat, lon) — corps d'abord, puis le chantier du devis."""
    ville = (corps.get('ville') or '').strip() or None
    lat = _num(corps.get('lat'))
    lon = _num(corps.get('lon'))
    if devis is not None and not (ville or (lat and lon)):
        try:
            from apps.crm.selectors import site_location_for_devis
            loc = site_location_for_devis(devis) or {}
            ville = ville or loc.get('site_ville')
            lat = lat if lat is not None else loc.get('gps_lat')
            lon = lon if lon is not None else loc.get('gps_lng')
        except Exception:  # noqa: BLE001 — lead illisible ⇒ pas de localisation
            pass
    return ville, lat, lon


def _dimensionner(*, company, conso, ville, lat, lon, occupation, equipements,
                  corps, source, avertissements):
    """Tableau + recommandation, ou ``None`` avec un avertissement explicite."""
    if company is None:
        avertissements.append(
            'Dimensionnement impossible : aucune société rattachée au compte '
            '(le catalogue est scopé société).')
        return None
    try:
        from apps.ventes.compatibilites import normaliser_phase
        from apps.ventes.dimensionnement import recommander_taille
        return recommander_taille(
            company=company, conso_kwh_mensuelles=conso, ville=ville, lat=lat,
            lon=lon, occupation=occupation, equipements=equipements,
            phase=normaliser_phase(corps.get('raccordement')),
            critere=corps.get('critere') or None,
            source_conso=source)
    except Exception:  # noqa: BLE001 — un aperçu ne casse jamais
        logger.warning('dimensionnement indisponible', exc_info=True)
        avertissements.append(
            'Dimensionnement indisponible (catalogue incomplet ou '
            'localisation non résolue).')
        return None


def _reponse(etude, dimensionnement, conso, source, detail, occupation,
             equipements, avertissements):
    """Charge utile de l'endpoint — forme STABLE, clés toujours présentes."""
    return {
        'etude': etude,
        'dimensionnement': dimensionnement,
        'consommation': {
            'source': source,
            'kwh_mensuels': conso or [],
            'detail': detail or {},
        },
        'profil': {
            'occupation': occupation,
            'equipements_actifs': sorted((equipements or {}).keys()),
        },
        'avertissements': avertissements,
    }
