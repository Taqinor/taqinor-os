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

import functools
import logging
import math

from django.http import QueryDict
from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import serializers
from rest_framework.decorators import (
    api_view, parser_classes, permission_classes,
)
from rest_framework.parsers import JSONParser
from rest_framework.response import Response

from authentication.permissions import IsAnyRole
from core.champs_stricts import ChaineStricte, non_blanc

from .dimensionnement import CRITERES
from .horaire.productible_societe import productible_societe

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


#: CI #997 fuzz (24/10) — bornes PUBLIÉES au schéma ET appliquées ci-dessous
#: (``-2.6e16`` kWh ou ``1.9e-163`` kWh de batterie débordaient le calcul en
#: 500) : toute grandeur est dans ±1e9, latitude ±90, longitude ±180.
BORNE = 1e9
BORNES_GEO = {'lat': 90.0, 'lon': 180.0}


def _dans_bornes(nom, valeur):
    return abs(valeur) <= BORNES_GEO.get(nom, BORNE)


#: CI #997 api-fuzz — drapeaux publiés ``boolean`` au schéma : un vrai
#: booléen JSON (``{}``, ``0``, ``"oui"`` passaient en silence par leur
#: « vérité » Python). En formulaire (multipart / urlencoded, où tout voyage en
#: chaîne), seules « true » / « false » (casse libre) sont lues.
DRAPEAUX = ('dimensionner', 'ete_differente')


def _drapeau(corps, nom):
    """``True``/``False`` d'un drapeau du corps (absent → ``False``), ou
    ``None`` quand sa valeur n'est pas un booléen (→ 400 côté vue)."""
    if nom not in corps:
        return False
    valeur = corps.get(nom)
    if isinstance(valeur, bool):
        return valeur
    if isinstance(corps, QueryDict) and isinstance(valeur, str) and (
            valeur.strip().lower() in ('true', 'false')):
        return valeur.strip().lower() == 'true'
    return None


#: CI #997 api-fuzz — séries publiées « 12 nombres ou null » :
#: ``conso_kwh_mensuelles: true`` (ou une chaîne) passait en silence (200) et
#: une liste d'une autre longueur était ignorée sans un mot. En formulaire,
#: chaque valeur répétée doit se lire comme un nombre.
SERIES_12 = ('factures_mensuelles', 'conso_kwh_mensuelles')


def _serie_12(corps, nom):
    """``(True, liste | None)`` pour 12 nombres finis (absent/null → None),
    ``(False, None)`` pour toute autre forme (→ 400 côté vue)."""
    if nom not in corps:
        return True, None
    formulaire = isinstance(corps, QueryDict)
    brutes = corps.getlist(nom) if formulaire else corps.get(nom)
    if brutes is None:
        return True, None
    types = (str,) if formulaire else (int, float)
    if not isinstance(brutes, list) or len(brutes) != 12 or any(
            isinstance(v, bool) or not isinstance(v, types) for v in brutes):
        return False, None
    try:
        valeurs = [float(v) for v in brutes]
    except (ValueError, OverflowError):
        return False, None
    return (all(map(math.isfinite, valeurs))
            and all(abs(v) <= BORNE for v in valeurs)), valeurs


#: CI #997 (2) — forme publiée des champs scalaires : un champ PRÉSENT a son
#: type JSON exact (``critere: "\f"``, ``lat: "0"``, ``devis: null`` étaient
#: lus en silence) ; un champ absent reste facultatif.
_ENTIERS = ('devis', 'lead')
_NOMBRES = ('lat', 'lon', 'facture_hiver', 'facture_ete', 'kwc',
            'batterie_kwh')
_TEXTES = ('ville', 'raccordement')


def _champ_hors_forme(corps):
    """Nom du premier champ scalaire présent hors de sa forme publiée, ou
    ``None``."""
    def _nombre(v):
        return isinstance(v, (int, float)) and not isinstance(v, bool)
    regles = [(_ENTIERS, lambda v: _nombre(v) and isinstance(v, int)),
              (_NOMBRES, _nombre),
              # CI #997 (3) — motif publié : non blanc ET aucun nul.
              (_TEXTES, lambda v: isinstance(v, str) and '\x00' not in v
               and non_blanc(v)),
              (('occupation',), lambda v: isinstance(v, str)),
              (('equipements',), lambda v: isinstance(v, dict)),
              (('batteries',), lambda v: isinstance(v, list)),
              (('critere',), lambda v: v in CRITERES)]
    for noms, valide in regles:
        for nom in noms:
            if nom in corps and not valide(corps.get(nom)):
                return nom
    for nom in _NOMBRES:
        valeur = corps.get(nom) if nom in corps else None
        if _nombre(valeur) and not _dans_bornes(nom, valeur):
            return nom
    return None


class _DevisDepuisLead:
    """L-QA1 (24/08/2026) FIX1 — duck-type minimal exposant SEULEMENT
    ``.lead``, pour réutiliser TELS QUELS les sélecteurs devis→lead
    (``equipements_du_devis``, ``occupation_du_devis``, ``lead_bills_for_devis``,
    ``site_location_for_devis`` — tous ``getattr(devis, 'lead', None)``) pour un
    LEAD SANS DEVIS PERSISTÉ (écran générateur, avant tout enregistrement).
    Sans lui, ces quatre règles de provenance devraient être dupliquées ici
    pour le seul chemin lead — exactement ce que ces façades existent pour
    éviter."""
    __slots__ = ('lead',)

    def __init__(self, lead):
        self.lead = lead


def _lead_de_la_societe(request, lead_id):
    """Lead demandé, SCOPÉ à la société de l'appelant, ou ``None``.

    Même garde que :func:`_devis_de_la_societe` : un identifiant fourni dans
    le corps ne doit jamais permettre de lire le profil d'un lead d'une autre
    société."""
    if not lead_id:
        return None
    company = getattr(request.user, 'company', None)
    if company is None:
        return None
    from apps.crm.selectors import get_company_lead
    return get_company_lead(company, lead_id)


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
        # ADEV41 — bornée à la portée équipe (ADEV21, ``created_by``).
        from core.scoping import scope_queryset
        qs = scope_queryset(qs.filter(company_id=company_id), user,
                            ['created_by'])
    elif not user.is_superuser:
        return None
    # ADEV41 — bornée aussi à la portée équipe (mêmes ``owner_fields`` que
    # ADEV21) : un devis hors portée se traite comme introuvable.
    from core.scoping import scope_queryset
    qs = scope_queryset(qs, user, ['created_by'])
    return qs.filter(pk=devis_id).first()


def _profil_depuis_corps(corps):
    """Profil de consommation depuis le corps brut de la requête.

    Chemin SANS devis persisté : le commercial saisit les réponses du script
    d'appel et voit immédiatement le résultat. Mêmes fonctions que le chemin
    devis — aucune règle dupliquée.
    """
    from .courbes_journalieres import composer_equipements
    from .horaire.conso import profil_depuis_factures

    conso, source, detail = profil_depuis_factures(
        facture_hiver_mad=_num(corps.get('facture_hiver')),
        facture_ete_mad=_num(corps.get('facture_ete')),
        ete_differente=bool(_drapeau(corps, 'ete_differente')),
        factures_mensuelles_mad=corps.get('factures_mensuelles'),
        conso_kwh_mensuelles=corps.get('conso_kwh_mensuelles'))

    occupation = corps.get('occupation')
    if occupation not in OCCUPATIONS:
        occupation = None
    equipements = composer_equipements(corps.get('equipements') or {})
    return conso, source, detail, occupation, equipements


def _profil_depuis_devis(devis, corps, *, tranches=None,
                         charges_fixes_mad=None):
    """Profil de consommation lu sur un devis et son lead (sélecteurs CRM).

    ERR-QAH-FIG-EDITION-ETUDE-LIVE-VS-DOCUMENT — LA MÊME RÉSOLUTION QUE LE BLOC
    DU DEVIS : :func:`etude_horaire.profil_conso_du_devis` (kWh mensuel DÉCLARÉ
    du lead, CAD166, et barème de la SOCIÉTÉ). L'aperçu appelait
    ``profil_depuis_factures`` sans l'un ni l'autre : l'« Édition complète »
    montrait une étude à la même production mais à d'AUTRES économies que le
    document (écran 2 742 / 5 932 MAD/an, devis 5 158 / 7 822)."""
    from .courbes_journalieres import equipements_du_devis, occupation_du_devis
    from .etude_horaire import profil_conso_du_devis

    conso, source, detail = profil_conso_du_devis(
        devis, tranches=tranches, charges_fixes_mad=charges_fixes_mad)

    # CI #752 (figures-parite : couverture écran 28 % contre 47,51 % à la
    # proposition) — MÊME OCCUPATION que le bloc du devis. L'écran n'envoie pas
    # ``mode_installation`` : sans lui, ``_occupation`` retombait sur le défaut
    # NON résidentiel ``absence_jour`` pendant que le bloc
    # (``etude_horaire._etude_horaire_pour_devis``) lit le mode sur le devis
    # et applique le défaut fondateur ``presence_jour``. Même contexte ici :
    # le mode du devis quand le corps ne le fournit pas, jamais écrasé.
    contexte = dict(corps)
    if not contexte.get('mode_installation'):
        contexte['mode_installation'] = getattr(devis, 'mode_installation', None)
    occupation, _source_occ = occupation_du_devis(devis, contexte)
    equipements = equipements_du_devis(devis)
    return conso, source, detail, occupation, equipements


def _profil_depuis_lead(lead, corps, *, tranches=None,
                        charges_fixes_mad=None):
    """L-QA1 (24/08/2026) FIX1 — profil de consommation lu directement sur un
    LEAD SANS DEVIS PERSISTÉ (écran générateur, avant tout enregistrement).

    AVANT ce chemin, un ``lead`` sans ``devis`` retombait sur
    ``_profil_depuis_corps`` : l'aperçu répondait alors avec
    ``occupation: null, equipements_actifs: []`` même quand le lead portait un
    script d'appel COMPLET (occupation_jour, VE, clim, piscine, chauffe-eau) —
    le commercial ne voyait jamais l'effet réel de ces réponses avant
    l'enregistrement. Mêmes fonctions EXACTES que le chemin devis (via le
    duck-type :class:`_DevisDepuisLead`), aucune règle dupliquée."""
    from apps.crm.selectors import (
        conso_mensuelle_kwh_pour_devis, lead_bills_for_devis)

    from .courbes_journalieres import equipements_du_devis, occupation_du_devis
    from .horaire.conso import profil_depuis_factures

    devis_duck = _DevisDepuisLead(lead)
    bills = lead_bills_for_devis(devis_duck) or {}
    # ERR-QAH-FIG-EDITION-ETUDE-LIVE-VS-DOCUMENT — mêmes arguments que
    # ``etude_horaire.profil_conso_du_devis`` (kWh déclaré du lead + barème
    # société) : le devis que ce lead deviendra est chiffré ainsi.
    conso, source, detail = profil_depuis_factures(
        facture_hiver_mad=bills.get('facture_hiver'),
        facture_ete_mad=bills.get('facture_ete'),
        ete_differente=bills.get('ete_differente'),
        factures_mensuelles_mad=corps.get('factures_mensuelles'),
        conso_kwh_mensuelles=corps.get('conso_kwh_mensuelles'),
        conso_kwh_mensuelle_unique=conso_mensuelle_kwh_pour_devis(devis_duck),
        tranches=tranches, charges_fixes_mad=charges_fixes_mad)

    # Lead 1635 (23/10/2026) — MÊME DÉFAUT D'OCCUPATION QUE LE DEVIS QUE CE
    # LEAD DEVIENDRA. L'écran générateur n'envoie pas ``mode_installation`` et
    # le duck-type n'en porte pas : ``_occupation`` retombait sur le défaut
    # NON résidentiel ``absence_jour`` pendant que le devis automatique
    # (``domain.entrees.entrees_depuis_lead`` → ``occupation_du_lead``, D4)
    # dimensionnait le MÊME lead en ``presence_jour`` — 8 panneaux (5,68 kWc)
    # recommandés à l'écran contre 24 (17,04 kWc) au devis, sur une facture
    # de 6 000 MAD. Même correctif que le chemin devis (CI #752) : le mode du
    # lead (``type_installation``, celui que ``creation_auto`` recopie en
    # ``mode_installation``) quand le corps ne le fournit pas, jamais écrasé.
    contexte = dict(corps)
    if not contexte.get('mode_installation'):
        contexte['mode_installation'] = getattr(lead, 'type_installation', None)
    occupation, _source_occ = occupation_du_devis(devis_duck, contexte)
    equipements = equipements_du_devis(devis_duck)
    return conso, source, detail, occupation, equipements


def _calcul_borne(vue):
    """CI #997 fuzz (24/10) — un calcul dont les entrées, bien que dans les
    bornes publiées, ne tiennent pas (division par une grandeur infime,
    débordement flottant) est un refus d'ÉTAT, 409 : jamais la page HTML d'une
    500 non gérée. Une réponse portant un flottant infini est refusée de même
    (non sérialisable en JSON)."""
    @functools.wraps(vue)
    def enveloppe(request, *args, **kwargs):
        from core.conflit_etat import ConflitEtat
        try:
            reponse = vue(request, *args, **kwargs)
        except (ArithmeticError, ValueError, TypeError) as exc:
            logger.warning('etude_horaire_preview : calcul impossible (%s)',
                           exc, exc_info=True)
            raise ConflitEtat(
                'Ces valeurs ne permettent pas de calcul : vérifiez les '
                'consommations, la puissance et la capacité de batterie.')
        if not _fini(getattr(reponse, 'data', None)):
            raise ConflitEtat(
                'Ces valeurs ne permettent pas de calcul fini : vérifiez les '
                'consommations, la puissance et la capacité de batterie.')
        return reponse
    return enveloppe


def _fini(valeur):
    if isinstance(valeur, float):
        return math.isfinite(valeur)
    if isinstance(valeur, dict):
        return all(_fini(v) for v in valeur.values())
    if isinstance(valeur, (list, tuple)):
        return all(_fini(v) for v in valeur)
    return True


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
# On déclare donc les six clés de premier niveau, avec leur nullabilité. Le
# DÉTAIL d'``etude``/``dimensionnement`` reste décrit par
# ``contract_samples/etude_horaire.json`` (PACT10), vérifié par
# ``check_api_shapes.py`` : le recopier en sérialiseur imbriqué créerait une
# SECONDE définition à maintenir en parallèle, ce que PACT10 interdit
# précisément.
@extend_schema(
    request=inline_serializer('EtudeHorairePreviewRequest', {
        'devis': serializers.IntegerField(
            required=False, help_text='Profil lu sur ce devis (scopé société)'),
        'lead': serializers.IntegerField(
            required=False,
            help_text='L-QA1 — profil lu directement sur ce lead SANS devis '
                      'persisté (écran générateur), scopé société. Un `devis` '
                      'fourni en même temps PRIME toujours sur `lead`.'),
        'ville': ChaineStricte(required=False),
        'lat': serializers.FloatField(
            required=False, min_value=-90, max_value=90),
        'lon': serializers.FloatField(
            required=False, min_value=-180, max_value=180),
        'facture_hiver': serializers.FloatField(
            required=False, min_value=-BORNE, max_value=BORNE,
            help_text='MAD/mois — ancrage réel'),
        'facture_ete': serializers.FloatField(
            required=False, min_value=-BORNE, max_value=BORNE),
        'ete_differente': serializers.BooleanField(required=False),
        'factures_mensuelles': serializers.ListField(
            child=serializers.FloatField(min_value=-BORNE, max_value=BORNE),
            required=False, allow_null=True,
            min_length=12, max_length=12,
            help_text='12 factures MAD réelles'),
        'conso_kwh_mensuelles': serializers.ListField(
            child=serializers.FloatField(min_value=-BORNE, max_value=BORNE),
            required=False, allow_null=True,
            min_length=12, max_length=12,
            help_text='12 consommations kWh saisies'),
        # Une occupation hors des valeurs servies est IGNORÉE (repli
        # documenté de ``OCCUPATIONS``) : le schéma publie un texte libre.
        'occupation': serializers.CharField(
            required=False, allow_blank=True,
            help_text='Servies : ' + ', '.join(OCCUPATIONS) + ' ; toute '
                      'autre valeur est ignorée (repli documenté).'),
        'equipements': serializers.DictField(required=False),
        'raccordement': ChaineStricte(required=False),
        'kwc': serializers.FloatField(
            required=False, min_value=-BORNE, max_value=BORNE),
        'batterie_kwh': serializers.FloatField(
            required=False, min_value=-BORNE, max_value=BORNE),
        'batteries': serializers.ListField(
            child=serializers.DictField(), required=False,
            help_text='RHOR9 — lignes « avec » batterie de l’écran '
                      '([{produit, quantite}]) lues sur leurs fiches quand '
                      'aucun devis n’est enregistré (scopé société).'),
        'dimensionner': serializers.BooleanField(required=False),
        'critere': serializers.ChoiceField(choices=CRITERES, required=False),
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
            'estimation_conso': serializers.JSONField(
                allow_null=True,
                help_text='Décomposition MENSUELLE base/ajouts/total '
                          '(T4/L-QA1) — null quand aucune couche équipement '
                          "n'est décomposable."),
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
# CI #997 (D2) — JSON seul, comme l'écran l'envoie : en formulaire,
# ``equipements`` (objet publié) voyageait en chaîne « {} » et une requête
# conforme était refusée. Un corps multipart reçoit 415.
@parser_classes([JSONParser])
@_calcul_borne
def etude_horaire_preview(request):
    """CJ2a — Aperçu du moteur horaire + dimensionnement, SANS devis persisté.

    Corps accepté (tout est optionnel sauf de quoi ancrer un calcul) ::

        {
          "devis": 123,                  // profil lu sur ce devis (scopé société)
          "lead": 17,                    // L-QA1 — sinon profil lu sur ce lead SANS
                                          // devis (un `devis` fourni prime toujours)
          "ville": "Casablanca",         // sinon ville du chantier du devis/lead
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

    ``400`` seulement quand le corps est inexploitable (pas un objet JSON,
    ``equipements`` non-objet, drapeau ``dimensionner``/``ete_differente``
    non booléen, ``factures_mensuelles``/``conso_kwh_mensuelles`` autre
    chose que 12 nombres ou null).
    """
    corps = request.data if isinstance(request.data, dict) else None
    if corps is None:
        return Response(
            {'detail': 'Corps de requête invalide : un objet JSON est attendu.'},
            status=400)
    # ENF1b — `equipements` est un OBJET (`{"piscine": true, …}`) : une
    # chaîne (corps multipart « {} », texte libre) faisait planter
    # `composer_equipements` (`'str' object has no attribute 'get'`, 500 au
    # fuzz du 09/10). Corps inexploitable → 400, comme ci-dessus.
    equipements_bruts = corps.get('equipements')
    if equipements_bruts not in (None, '') \
            and not isinstance(equipements_bruts, dict):
        return Response(
            {'detail': 'Corps de requête invalide : « equipements » doit '
                       'être un objet JSON (ex. {"piscine": true}).'},
            status=400)

    for nom in DRAPEAUX:
        if _drapeau(corps, nom) is None:
            return Response(
                {'detail': f'Corps de requête invalide : « {nom} » doit être '
                           'un booléen (true / false).'},
                status=400)
    for nom in SERIES_12:
        valide, valeurs = _serie_12(corps, nom)
        if not valide:
            return Response(
                {'detail': f'Corps de requête invalide : « {nom} » doit être '
                           'une liste de 12 nombres (ou null).'},
                status=400)
        if valeurs is not None and isinstance(corps, QueryDict):
            corps = corps.copy()
            corps[nom] = valeurs  # la liste lue, plus la dernière chaîne
    hors_forme = _champ_hors_forme(corps)
    if hors_forme:
        return Response(
            {'detail': f'Corps de requête invalide : « {hors_forme} » ne '
                       'suit pas sa forme publiée.'},
            status=400)

    company = getattr(request.user, 'company', None)
    avertissements = []

    devis = _devis_de_la_societe(request, corps.get('devis'))
    if corps.get('devis') and devis is None:
        avertissements.append(
            'Devis introuvable dans votre société — profil lu depuis le corps '
            'de la requête.')

    # L-QA1 (24/08/2026) FIX1 — un ``lead`` n'est résolu QUE si aucun devis
    # utilisable n'a été fourni : un devis existant prime toujours (même
    # chaîne que ``_devis_de_la_societe`` ci-dessus).
    lead = None
    if devis is None:
        lead = _lead_de_la_societe(request, corps.get('lead'))
        if corps.get('lead') and lead is None:
            avertissements.append(
                'Lead introuvable dans votre société — profil lu depuis le '
                'corps de la requête.')

    from .etude_horaire import _reglages_tarifaires, calculer_etude_horaire
    from .horaire.ombrage import perte_ombrage_du_devis

    if devis is not None:
        company = getattr(devis, 'company', None) or company
    elif lead is not None:
        company = getattr(lead, 'company', None) or company
    # QJR46 — UN SEUL barème pour toute cette réponse : l'étude d'une taille et
    # le tableau de dimensionnement servis côte à côte ne peuvent pas valoriser
    # le kWh différemment (l'étude lisait la surcharge de la société via
    # ``etude_horaire_pour_devis`` ailleurs, le tableau la grille nationale).
    # ERR-QAH-FIG-EDITION-ETUDE-LIVE-VS-DOCUMENT — et l'inversion facture → kWh
    # du profil lit CE MÊME barème, comme le bloc du devis enregistré.
    tranches, charges_fixes = _reglages_tarifaires(company)

    if devis is not None:
        conso, source, detail, occupation, equipements = _profil_depuis_devis(
            devis, corps, tranches=tranches, charges_fixes_mad=charges_fixes)
    elif lead is not None:
        conso, source, detail, occupation, equipements = _profil_depuis_lead(
            lead, corps, tranches=tranches, charges_fixes_mad=charges_fixes)
    else:
        conso, source, detail, occupation, equipements = _profil_depuis_corps(
            corps)

    ville, lat, lon = _localisation(corps, devis, lead)

    # QJR432 — MÊME HORLOGE QUE LE DEVIS RÉSOLU (même classe que QJR406/QJR232) :
    # sans elle, cet aperçu recalcule contre l'horloge du serveur au moment de
    # l'appel, alors que le bloc PERSISTÉ du devis a été calculé contre SA
    # propre date de référence (``domain.entrees.jour_reference_du_devis`` —
    # surcharge D12 déclarée, sinon la date de création du devis, jamais
    # « aujourd'hui »). L'écart est visible pendant et autour du Ramadan, où la
    # fenêtre imsak/iftar dépend de la date. Sans devis résolu, comportement
    # INCHANGÉ : ``None`` laisse ``jours_types_annee`` retomber sur son repli
    # d'horloge, comme avant cette tâche.
    jour_reference = None
    if devis is not None:
        from apps.ventes.domain.entrees import jour_reference_du_devis
        jour_reference = jour_reference_du_devis(devis)

    if not conso:
        avertissements.append(
            "Aucune facture exploitable : sans ancrage réel, le moteur ne "
            "calcule rien plutôt que d'afficher une estimation déguisée en "
            "mesure.")
        return Response(_reponse(
            None, None, conso, source, detail, occupation, equipements,
            avertissements))

    etude = None
    kwc = _num(corps.get('kwc'))
    if kwc and kwc > 0:
        batterie = _batterie_de_l_apercu(devis, _num(corps.get('batterie_kwh')))
        if devis is None and corps.get('batteries'):
            # RHOR9 — sans devis enregistré, les lignes « avec » de l'écran
            # lues sur leurs fiches (capacité utile, puissances, rendement).
            from .horaire.batterie_apercu import batterie_des_produits
            batterie = batterie_des_produits(
                corps.get('batteries'), company) or batterie
        etude = _bloc_enregistre_du_devis(devis, corps, kwc, occupation,
                                          batterie)
        if etude is None:
            etude = calculer_etude_horaire(
                kwc=kwc, conso_kwh_mensuelles=conso, ville=ville, lat=lat,
                lon=lon, occupation=occupation, equipements=equipements,
                source_conso=source, detail_conso=detail,
                tranches=tranches, charges_fixes_mad=charges_fixes,
                jour_reference=jour_reference,
                # D-RES-2710-1 — même ombrage du calepinage que le bloc du
                # devis enregistré (``None`` sans devis : aucun ombrage).
                perte_ombrage_pct=perte_ombrage_du_devis(devis),
                # CE2E6 — le productible saisi par la société, comme le devis.
                productible_kwh_kwc=productible_societe(company, devis), **batterie)
        if etude is None:
            avertissements.append(
                'Étude non calculable pour cette taille : localisation du '
                'chantier non résolue par PVGIS (ni GPS, ni ville reconnue).')

    dimensionnement = None
    if _drapeau(corps, 'dimensionner'):
        dimensionnement = _dimensionner(
            company=company, conso=conso, ville=ville, lat=lat, lon=lon,
            occupation=occupation, equipements=equipements, corps=corps,
            source=source, avertissements=avertissements,
            tranches=tranches, charges_fixes_mad=charges_fixes)

    # T4/L-QA1 — même décomposition mensuelle que le devis enregistré
    # (``services.rafraichir_etude_horaire_devis`` ne l'expose nulle part sur
    # l'APERÇU jusqu'ici) : best-effort, ``None`` quand rien n'est
    # décomposable (aucune couche équipement, ou série non exploitable).
    from .horaire.public import estimation_conso_mensuelle
    estimation_conso = estimation_conso_mensuelle(conso, equipements)

    return Response(_reponse(
        etude, dimensionnement, conso, source, detail, occupation,
        equipements, avertissements, estimation_conso))


def _batterie_de_l_apercu(devis, batterie_kwh_corps):
    """Arguments batterie de l'aperçu horaire, ceux du bloc ENREGISTRÉ du devis
    quand l'écran décrit LA MÊME batterie.

    ERR-FIG-APERCU-BATTERIE (06/10/2026, e2e figures-parite) — l'écran envoie
    la capacité NOMINALE lue sur le nom de ses lignes (« Dyness 5 kWh » → 5) et
    rien d'autre : l'aperçu tournait donc à 5 kWh × rendement de référence
    0,90, pendant que le bloc du devis (``_etude_horaire_pour_devis``) tourne
    à la capacité UTILE de la fiche (4,6 kWh) × le rendement PUBLIÉ (0,98,
    QJR137) avec les puissances de la fiche. Même devis, deux paybacks
    (6,9 ans à l'écran contre 6,7 au PDF).

    Quand un devis est résolu et que la capacité envoyée est le NOMINAL de son
    option « avec » (l'écran n'explore pas une autre batterie), l'aperçu prend
    les grandeurs du devis — le même calcul que le bloc enregistré. Sinon
    (pas de devis, ou une batterie différente essayée à l'écran) : la capacité
    du corps, comme avant, sans rien emprunter à une fiche qui ne la décrit
    pas.
    """
    if devis is None or not batterie_kwh_corps:
        return {'batterie_kwh_utile': batterie_kwh_corps}
    try:
        from apps.ventes.horaire.batterie_lignes import (
            capacite_batterie_du_devis, ligne_dans_option,
            puissance_batterie_du_devis, rendement_batterie_du_devis,
        )
        from apps.ventes.services import _parse_kwh, classer_produit
        nominal = 0.0
        for ligne in devis.lignes.all():
            designation = getattr(ligne, 'designation', '') or ''
            if (not ligne_dans_option(ligne, 'avec')
                    or classer_produit(designation) != 'batterie'):
                continue
            nominal += float(_parse_kwh(designation) or 0) * float(
                getattr(ligne, 'quantite', 0) or 0)
        if not nominal or abs(nominal - float(batterie_kwh_corps)) > 0.01:
            return {'batterie_kwh_utile': batterie_kwh_corps}
        puissances = puissance_batterie_du_devis(devis)
        rendement = rendement_batterie_du_devis(devis)
        return {
            'batterie_kwh_utile': (capacite_batterie_du_devis(devis, 'avec')
                                   or batterie_kwh_corps),
            'batterie_puissance_decharge_kw': puissances['packs_decharge_kw'],
            'batterie_puissance_decharge_onduleur_kw':
                puissances['ond_decharge_kw'],
            'batterie_puissance_charge_kw': puissances['charge_kw'],
            'batterie_rendement': rendement['rendement'],
            'batterie_rendement_source': rendement['source'],
        }
    except Exception:  # noqa: BLE001 — un aperçu ne casse jamais : corps seul (D-ENF22-BLE001)
        logger.warning('batterie du devis illisible pour l\'aperçu',
                       exc_info=True)
        return {'batterie_kwh_utile': batterie_kwh_corps}


def _meme_ville(ville_corps, ville_chantier):
    """La ville envoyée par l'écran désigne-t-elle le chantier (vide = oui) ?"""
    tapee = (ville_corps or '').strip().casefold()
    return not tapee or tapee == (ville_chantier or '').strip().casefold()


def _localisation(corps, devis, lead=None):
    """(ville, lat, lon) — corps d'abord, puis le chantier du devis/lead.

    ERR-QAH-FIG-EDITION-ETUDE-LIVE-VS-DOCUMENT — l'écran envoie TOUJOURS la
    ville de calcul du lead : le GPS du chantier n'était donc jamais lu, et
    l'aperçu chiffrait la table PVGIS de la ville pendant que le bloc du devis
    (``etude_horaire._etude_horaire_pour_devis`` : ville du chantier + GPS du
    lead) chiffrait le point exact. Le GPS du chantier est désormais repris
    dès que la ville envoyée EST celle du chantier ; une autre ville tapée
    (simulation) garde le comportement d'avant, sans GPS emprunté.
    """
    ville = (corps.get('ville') or '').strip() or None
    lat = _num(corps.get('lat'))
    lon = _num(corps.get('lon'))
    source_localisation = devis if devis is not None else (
        _DevisDepuisLead(lead) if lead is not None else None)
    if source_localisation is not None and not (lat and lon):
        try:
            from apps.crm.selectors import site_location_for_devis
            loc = site_location_for_devis(source_localisation) or {}
            if not _meme_ville(ville, loc.get('site_ville')):
                return ville, lat, lon
            ville = ville or loc.get('site_ville')
            lat = lat if lat is not None else loc.get('gps_lat')
            lon = lon if lon is not None else loc.get('gps_lng')
        except Exception:  # noqa: BLE001 — lead illisible ⇒ pas de localisation (D-ENF22-BLE001)
            logger.warning("etude_horaire_view._localisation : erreur ignorée (mode dégradé)", exc_info=True)
    return ville, lat, lon


def _bloc_enregistre_du_devis(devis, corps, kwc, occupation, batterie):
    """ERR-QAH-FIG-EDITION-ETUDE-LIVE-VS-DOCUMENT — le bloc RANGÉ du devis,
    servi TEL QUEL quand l'écran décrit ce que le document chiffre.

    L'« Édition complète » recalculait l'étude en direct pendant que le PDF,
    l'API et la proposition lisent le bloc rangé : deux calculs, et chaque
    argument qui diverge (localisation, batterie, occupation) ou chaque
    caprice de PVGIS rendait deux chiffres. Tant que l'écran n'explore rien
    — même kWc et même batterie que le devis, ni GPS ni autre ville ni autre
    occupation demandés — l'aperçu rend le bloc que
    ``domain.etudes.bloc_horaire_enregistre_pour`` juge frais ET que le moteur
    accepte : écran et document lisent alors la MÊME étude. Sinon ``None`` et
    l'aperçu recalcule comme avant. Ne lève jamais.
    """
    if (devis is None or corps.get('lat') not in (None, '')
            or corps.get('lon') not in (None, '')):
        return None
    try:
        from apps.crm.selectors import site_location_for_devis
        from apps.ventes.domain.etudes import bloc_horaire_enregistre_pour
        bloc = bloc_horaire_enregistre_pour(devis, kwc)
        if bloc is None or bloc.get('occupation') != occupation:
            return None
        loc = site_location_for_devis(devis) or {}
        if not _meme_ville(corps.get('ville'), loc.get('site_ville')):
            return None
        capacite = batterie.get('batterie_kwh_utile')
        if capacite and 'batterie_rendement' not in batterie:
            return None  # une AUTRE batterie essayée à l'écran
        rangee = bloc.get('batterie_kwh_utile')
        if bool(capacite) != bool(rangee) or (
                capacite and abs(float(capacite) - float(rangee)) > 0.05):
            return None
        return {cle: valeur for cle, valeur in bloc.items()
                if not str(cle).startswith('_')}
    except Exception:  # noqa: BLE001 — un aperçu ne casse jamais : recalcul (D-ENF22-BLE001)
        logger.warning("bloc enregistré illisible pour l'aperçu",
                       exc_info=True)
        return None


def _dimensionner(*, company, conso, ville, lat, lon, occupation, equipements,
                  corps, source, avertissements, tranches, charges_fixes_mad):
    """Tableau + recommandation, ou ``None`` avec un avertissement explicite.

    QJR46 — ``tranches`` / ``charges_fixes_mad`` sont EXIGÉS et viennent de
    l'appelant : cet aperçu valorisait le kWh sur la grille nationale pendant
    que l'étude horaire de la MÊME réponse appliquait la surcharge société.
    """
    if company is None:
        avertissements.append(
            'Dimensionnement impossible : aucune société rattachée au compte '
            '(le catalogue est scopé société).')
        return None
    try:
        from apps.ventes.compatibilites import (
            est_site_isole, normaliser_phase)
        from apps.ventes.dimensionnement import recommander_taille
        return recommander_taille(
            company=company, conso_kwh_mensuelles=conso, ville=ville, lat=lat,
            lon=lon, occupation=occupation, equipements=equipements,
            phase=normaliser_phase(corps.get('raccordement')),
            critere=corps.get('critere') or None,
            source_conso=source,
            # ERR-QJR605 — raccordement « aucun » : kit off-grid.
            hors_reseau=est_site_isole(corps.get('raccordement')),
            tranches=tranches, charges_fixes_mad=charges_fixes_mad)
    except Exception:  # noqa: BLE001 — un aperçu ne casse jamais (D-ENF22-BLE001)
        logger.warning('dimensionnement indisponible', exc_info=True)
        avertissements.append(
            'Dimensionnement indisponible (catalogue incomplet ou '
            'localisation non résolue).')
        return None


def _reponse(etude, dimensionnement, conso, source, detail, occupation,
             equipements, avertissements, estimation_conso=None):
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
        # T4/L-QA1 — décomposition MENSUELLE base/ajouts/total, même fonction
        # que le devis enregistré. None quand rien n'est décomposable.
        'estimation_conso': estimation_conso,
    }
