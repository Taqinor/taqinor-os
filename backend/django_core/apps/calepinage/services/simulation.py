"""CALX5 — L'ORCHESTRATION de la simulation : le seul chemin qui la lance.

CE QUE CE MODULE EST
--------------------
La simulation du calepinage a une dizaine de producteurs — la chaîne de pertes
(CALX147), la météo (CALX150-155), la courbe de charge (CALX189), la batterie
et l'autoconsommation (CALX188-191), l'incertitude (CALX186), le ratio de
performance (CALX179), la projection pluriannuelle (CALX178), l'écart contre
PVGIS (CALX195), la simulation module par module (CALX182). Chacun est PUR et
ignore la base. Ce module est celui qui les COMPOSE : il lit le document et ses
fiches, bâtit LE contexte que tous partagent, les exécute dans l'ordre, et
écrit le résultat dans ``Calepinage.resultat`` PAR FUSION DE CLÉS (D-CALX 4).

Il ne calcule rien lui-même. Aucun coefficient, aucun seuil, aucun forfait n'est
écrit ici : une entrée absente fait OMETTRE le bloc concerné avec le champ
manquant nommé (D-CALX 7).

L'ORDRE, ET POURQUOI C'EST CELUI-LÀ
------------------------------------
1. ``decision_meteo`` — le mode météo est SAISI ou la simulation est REFUSÉE,
   avant le moindre appel réseau (CALX153).
2. la chaîne de pertes. Un pan : la chaîne entière d'affilée. Plusieurs pans
   (ACAL53) : la météo est posée AVANT, chaque pan passe la phase PAN avec
   sa propre irradiance, la SOMME DC passe la phase ONDULEUR (écrêtage, η(P),
   MPPT jugés sur tous les pans à la fois), puis la phase SITE ; la cascade
   publiée est celle de la SOMME, et les sorties par pan sont posées sous
   ``sorties_par_pan``.
3. la simulation MODULE PAR MODULE (CALX182) quand le document porte un accès
   solaire par module ;
4. la courbe de charge (CALX189), puis batterie → autoconsommation → hors
   réseau, dans cet ordre : chacun lit les colonnes que le précédent a posées ;
5. l'incertitude (sur les totaux annuels de la chaîne), le ratio de
   performance, l'écart contre PVGIS, la projection pluriannuelle.

CE QU'IL ÉCRIT, ET CE QU'IL NE TOUCHE PAS
------------------------------------------
Les blocs déclarés par CALX4 plus ``simulation`` (empreinte, version du moteur,
date, durée). ``resultat['pertes']`` — la LISTE PLATE des postes saisis
(D-CALX 11) — n'est jamais réécrite, et aucun statut n'est touché (règle #4).

Voir ``contract_samples/calepinage_simulation.json`` pour la forme exacte.
"""
from __future__ import annotations

import datetime
import logging
import time

from .chaine_pertes import (
    CLE_CHARGE, CLE_CLIENT_PVGIS, CLE_FOURNISSEUR_METEO, CLE_SORTIES_PAR_PAN,
    ETAPES_ONDULEUR, MOTIF_TMY_HORIZONTAL, MeteoIndecise, appliquer_chaine,
    bloc_serie_horaire, completude_de_la_chaine, decision_meteo,
)
from .etapes.autoconsommation import bloc_autoconsommation
from .etapes.batterie import bloc_batterie
from .etapes.hors_reseau import bloc_hors_reseau
from .etapes.vieillissement import tableau_pluriannuel
from .incertitude import (
    IncertitudeInvalide, bloc_incertitude, masquer_depassements,
)
from .performance import bloc_performance
from .pvgis_serie import (
    AVERTISSEMENT_EST_OUEST_SUPPOSE, BASE_PAR_DEFAUT, ClientPvgis,
    EntreeInvalide, PvgisIndisponible, azimut_pvgis, jambes_du_pan,
)
from .horizon import profil_depuis_document
from .simulation_modules import production_module_par_module
from .validation import ecart_vs_pvcalc
from .valeurs import nombre as _nombre

__all__ = [
    'CLE_SIMULATION', 'COLONNE_ENTREE_CHAINE', 'DETAIL_DEJA_CALCULE',
    'MOTIF_ECRETAGE_SANS_AFFECTATION', 'MOTIF_SANS_PAN_EQUIPE',
    'MOTIF_SANS_POINT',
    'SOURCE_ENTREE_CHAINE', 'SimulationRefusee', 'VERSION_SIMULATION',
    'construire_contexte', 'empreinte_simulation', 'fichier_meteo_depose',
    'lire_compagnon_meteo', 'lire_piece_meteo',
    'recalculer_simulations_societe', 'simuler_calepinage',
    'verifier_simulable',
]

logger = logging.getLogger(__name__)

#: ACAL48 — la version du MODÈLE de simulation du calepinage. Elle entre dans
#: :func:`empreinte_simulation` : la bumper périme TOUTES les simulations
#: stockées (défaut gravé « bump + version dans l'empreinte »), sans toucher
#: ``core/electrique/version.VERSION_MOTEUR`` (le moteur ÉLECTRIQUE, qui a sa
#: propre vie). Journal des bumps (une ligne par changement de chiffre publié) :
#:
#: * ``sim-1`` (ACAL48, 06/10/2026) — empreinte de simulation unique : document
#:   (hors volatils) + entrées hors ``roof_layout`` + cette version.
#: * ``sim-2`` (ACAL54, 06/10/2026) — P50, mensuel, par pan, batterie,
#:   autoconsommation, hors réseau, incertitude, projection et écart PVcalc
#:   publiés sur l'ANNÉE MOYENNE de la fenêtre météo (plus la somme de ses N
#:   années) ; ``production.annees[]`` = totaux observés. Toute simulation
#:   ``sim-1`` est périmée.
#: * ``sim-3`` (ACAL128, 06/10/2026) — ratio de performance sur
#:   l'irradiation INCIDENTE capturée avant la chaîne (plus celle de la série
#:   finale, réécrite par les étapes optiques).
VERSION_SIMULATION = 'sim-3'

#: ACAL48 — les saisies de l'entrée électrique enregistrée qui ENTRENT dans
#: la simulation (câbles, affectation, polystring, optimiseur, températures
#: SAISIES, batterie et mode hors réseau déclarés, transformateur). Les
#: options du noyau (longueurs, phases, régime…) s'y ajoutent par
#: ``services/electrique.py::_options_entree``. Les décisions de check-list
#: (protections, terre), l'exigence de marché et les dérogations n'y sont PAS :
#: aucune étape de la chaîne ne les lit.
ENTREES_ELECTRIQUES_SIMULEES = (
    'module_produit', 'onduleur_produit', 'optimiseur_produit',
    'cheminement', 'affectation_manuelle', 'polystring',
    'temperature_min_c', 'temperature_max_c',
    'batterie', 'hors_reseau', 'transformateur',
)

#: ACAL48 — les sections de réglages société que la simulation LIT (D-ACAL-8).
SECTIONS_REGLAGES_SIMULEES = ('simulation', 'electrique_societe',
                              'norme_electrique')

#: ACAL48 — les sections dont chaque clé ``{valeur, source, reference}`` est
#: FIGÉE dans ``resultat.simulation.reglages_utilises`` (D-ACAL-8). La section
#: ``simulation`` garde ses noms nus (forme du contrat) ; les autres sont
#: préfixées par leur section.
SECTIONS_REGLAGES_FIGEES = (('simulation', ''),
                            ('electrique_societe', 'electrique_societe.'))

#: La clé d'en-tête écrite dans ``Calepinage.resultat`` (CALX4). Elle vient de
#: ``services/electrique.py`` : un seul nom pour l'écrivain et pour le lecteur
#: de fraîcheur (CALX70).
CLE_SIMULATION = 'simulation'

#: La colonne d'énergie de la série qui ENTRE dans la chaîne, et la phrase qui
#: dit d'où elle sort. Ce n'est pas un modèle : c'est la DÉFINITION du
#: kilowatt-crête (puissance du champ sous 1 000 W/m² aux conditions STC), donc
#: ``p_w = kWc × G(i)``. Tout le reste — température, niveau d'irradiance,
#: salissure, onduleur — est retranché ENSUITE, étape par étape, par la chaîne.
COLONNE_ENTREE_CHAINE = 'p_w'
SOURCE_ENTREE_CHAINE = (
    'p_w = kWc × G(i) — définition du kilowatt-crête aux conditions STC '
    '(1 000 W/m², 25 °C) ; toutes les pertes sont retranchées ensuite par la '
    'chaîne, aucune ne l\'est ici.')

DETAIL_DEJA_CALCULE = (
    "Les entrées n'ont pas bougé depuis le dernier calcul : aucune simulation "
    'relancée. Passez `forcer: true` pour recalculer.')

MOTIF_SANS_PAN_EQUIPE = (
    'Aucun pan de ce calepinage ne porte à la fois des modules et une '
    "puissance crête : il n'y a rien à simuler. Posez des modules, puis "
    "désignez le module PV dans l'onglet Matériel électrique (ou liez un "
    'devis qui porte une ligne module) avant de lancer la simulation.')

MOTIF_SANS_POINT = (
    "Le site de ce calepinage n'a pas de point GPS : la météo se demande à "
    'une latitude et une longitude, elles ne se devinent pas. Posez '
    "l'épingle du site sur la carte (« roof_layout.pin »).")

MOTIF_FICHIER_PLUSIEURS_PANS = (
    'La série météo déposée décrit UN plan ; ce calepinage en porte '
    '{pans}. La même série sert donc à tous les pans : leurs irradiances ne '
    'sont pas distinguées.')

MOTIF_PROJECTION = (
    "Projection pluriannuelle non publiée. {motif}")


class SimulationRefusee(ValueError):
    """La simulation est REFUSÉE, et le champ fautif est NOMMÉ.

    ``champ`` porte la clé à corriger sous le nom que l'écran affiche, et
    ``motif`` la phrase française à montrer SOUS ce champ (règle fondateur du
    08/09/2026 : jamais un « non enregistré » générique).
    """

    def __init__(self, message, *, champ=''):
        super().__init__(message)
        self.champ = champ
        self.motif = message


# ═══════════════════════════════════════════════════════════════════════════
# LE CONTEXTE — tout ce que les producteurs PURS ont besoin de lire
# ═══════════════════════════════════════════════════════════════════════════

def _zones_du_document(document):
    """``{repère du pan: zone}`` — les deux repères mènent à la même zone."""
    par_repere = {}
    for zone in ((document or {}).get('zones') or []):
        if not isinstance(zone, dict):
            continue
        for repere in (zone.get('label'), zone.get('id')):
            if repere:
                par_repere[str(repere)] = zone
    return par_repere


def _plans_du_contexte(pose, document):
    """Les pans, à la forme que les étapes lisent (CALX147 et suivantes).

    ``geometry`` est la géométrie BRUTE du document (``zones[].geometry``) :
    les étapes inter-rangées, bifacial et thermique y lisent leurs champs
    (``tiltDeg``, ``panelSlopeLenM``, ``rowPitchM``, ``rowCount``,
    ``panels[]``, ``kwc``) sans qu'aucune valeur ne soit recopiée ici.
    """
    zones = _zones_du_document(document)
    plans = []
    for ligne in (pose.get('pans') or []):
        repere = str(ligne.get('pan') or '')
        zone = zones.get(repere) or {}
        geometrie = zone.get('geometry')
        azimut = _nombre(ligne.get('azimut_deg'))
        plan = {
            'cle': repere,
            'pan': repere,
            'modules': int(ligne.get('modules') or 0),
            'kwc': _nombre(ligne.get('kwc')),
            'inclinaison_deg': _nombre(ligne.get('inclinaison_deg')),
            'azimut_deg': azimut,
            'azimut_pvgis_deg': (azimut_pvgis(azimut) if azimut is not None
                                 else None),
            'type_pose': (zone.get('type_pose') or zone.get('pose')
                          or (geometrie or {}).get('family')),
            'geometry': geometrie if isinstance(geometrie, dict) else None,
        }
        plans.append(plan)
    return plans


def _ombrage_du_document(document):
    """Les lectures d'ombrage du constructeur, telles que le document les porte.

    ACAL137 — l'accès solaire par module vit dans la géométrie de chaque pan
    (``zones[].geometry.solarAccess``) : il est lu là, par
    ``etapes.acces_module.acces_du_pan``, depuis ``layout`` — aucune clé
    racine ``solar_access``/``solarAccess`` (inexistante) n'est publiée.
    """
    document = document if isinstance(document, dict) else {}
    return {
        'shading12x24': document.get('shading12x24'),
        'layout': document,
    }


def _site_du_calepinage(calepinage, document, imagerie):
    """``{lat, lon, altitude_m, fuseau}`` — SAISI, jamais déduit.

    L'épingle du document prime ; à défaut, celle que le sélecteur résout
    depuis le lead. Aucune coordonnée n'est inventée : sans épingle, ``lat``
    et ``lon`` restent ``None`` et la simulation est refusée en le disant.
    """
    from ..selectors import contexte_geographique
    from .site import altitude_du_site, fuseau_du_site

    epingle = (document.get('pin') if isinstance(document, dict) else None)
    if not isinstance(epingle, dict):
        epingle = contexte_geographique(calepinage).get('pin') or {}
    lat = _nombre(epingle.get('lat'))
    lon = _nombre(epingle.get('lng') if epingle.get('lng') is not None
                  else epingle.get('lon'))
    # ACAL129 — le fuseau des réglages d'imagerie, sinon celui du PROFIL de
    # la société (repli déclaré), avec sa provenance.
    fuseau = fuseau_du_site(imagerie,
                            company=getattr(calepinage, 'company', None))
    return {
        'lat': lat,
        'lon': lon,
        'altitude_m': altitude_du_site(imagerie)['altitude_m'],
        'fuseau': fuseau['fuseau'],
        'fuseau_source': fuseau['provenance'],
    }


def _declaration_batterie(calepinage, donnees, materiel, company):
    """La batterie DÉCLARÉE et les specs de son pack, ou ``{}``.

    ACAL166 — la déclaration vit sur l'ENTRÉE électrique enregistrée
    (``POST entree-electrique/`` → ``donnees['batterie']``), plus sur
    ``roof_layout.battery`` (un second porteur qu'aucun écrivain ne
    produisait). Le PRODUIT et le nombre de PACKS prennent, à défaut de saisie,
    la ligne batterie du devis lié — la provenance (``explicite`` | ``devis``)
    voyage dans ``provenance`` ; les grandeurs viennent de la FICHE du
    produit, résolue ici parce que ce module est le seul à avoir accès au
    stock. AUCUNE stratégie n'est supposée : sans stratégie saisie, CALX188
    omet le bloc et le DIT.

    ACAL56 — l'onduleur est celui du RÉSOLVEUR (``materiel``, rendu par
    ``services/electrique.py::resoudre_materiel`` : désignation explicite,
    sinon ligne du devis lié).
    """
    from .chaines import batterie_du_calepinage

    batterie = batterie_du_calepinage(calepinage, donnees, materiel, company)
    if batterie is None:
        return {}
    declaration = {cle: valeur for cle, valeur in batterie['saisie'].items()
                   if cle not in ('produit', 'packs') and valeur is not None}
    nom = str(getattr(batterie['produit'], 'nom', '') or '').strip()
    declaration['groupes'] = [{
        'groupe': nom or 'Batterie',
        'packs': batterie['packs'],
        'specs': batterie['specs'],
    }]
    declaration['provenance'] = batterie['provenance']
    return declaration


def _capacites_batterie_du_stock(company):
    """CALX271 — les batteries du STOCK de la société, lues sur leur fiche.

    Le sélecteur du stock rend les produits ACTIFS de catégorie « batterie »
    SANS filtre de prix (``avec_prix=False`` : aucun prix n'est lu, D5) ;
    ``specs_batterie`` lit leur fiche. Une capacité candidate est ainsi une
    fiche RÉELLE, jamais une capacité inventée — celles qui ne publient pas
    de capacité utile sont écartées par ``etapes/batterie.py``, qui compare
    les autres. Sans société : aucune lecture, liste vide.
    """
    if company is None:
        return []
    from apps.stock.selectors import produits_par_type_equipement

    from .batterie import specs_batterie

    capacites = []
    for produit in produits_par_type_equipement(company, 'batterie',
                                                avec_prix=False):
        specs = specs_batterie(produit)
        grandeurs = specs.get('grandeurs') or {}
        capacites.append({
            'produit': produit.pk,
            'libelle': str(getattr(produit, 'nom', '') or '').strip()
            or f'Batterie {produit.pk}',
            'capacite_utile_kwh': specs.get('capacite_utile_kwh'),
            'puissance_charge_kw': specs.get('puissance_charge_kw'),
            'puissance_decharge_kw': specs.get('puissance_decharge_kw'),
            'rendement_ar_pct': grandeurs.get('rendement_ar_pct'),
            'source': specs.get('capacite_utile_source') or 'fiche',
        })
    return capacites


def _section_de_l_entree(donnees, nom):
    """ACAL166 — une section DÉCLARÉE de l'entrée électrique (``{}`` si absente)."""
    section = donnees.get(nom) if isinstance(donnees, dict) else None
    return dict(section) if isinstance(section, dict) else {}


def _declaration_consommation(document):
    """La déclaration de consommation du document (CALX255), ou ``{}``.

    ``layout`` y entre toujours : c'est par lui que ``courbe_charge`` atteint
    ``consumption.courbe24``. Les autres entrées admises (import d'intervalle,
    profil mensuel, kWh annuel, profil type, charges) sont reprises telles
    quelles quand le document les porte — aucune n'est fabriquée.
    """
    document = document if isinstance(document, dict) else {}
    brute = document.get('consumption')
    declaration = dict(brute) if isinstance(brute, dict) else {}
    declaration['layout'] = document
    return declaration


# ═══════════════════════════════════════════════════════════════════════════
# ACAL48 — L'EMPREINTE DE SIMULATION (D-ACAL-21), UNE SEULE, PARTOUT
# ═══════════════════════════════════════════════════════════════════════════

def _canonique(valeur):
    """Le JSON canonique (clés triées) d'une valeur, ``str`` pour l'exotique."""
    import json

    return json.dumps(valeur, sort_keys=True, ensure_ascii=False,
                      separators=(',', ':'), default=str)


def _reglages_utilises(reglages):
    """ACAL48 / D-ACAL-8 — les réglages société FIGÉS dans le résultat.

    ``{cle: {valeur, source, reference}}`` pour chaque clé SAISIE des sections
    :data:`SECTIONS_REGLAGES_FIGEES` (une clé absente n'est jamais inventée).
    Le résultat garde ainsi la valeur avec laquelle il a été calculé, même
    quand la société change ensuite son réglage (la simulation devient alors
    « périmée », jamais réécrite).
    """
    fige = {}
    reglages = reglages if isinstance(reglages, dict) else {}
    for section, prefixe in SECTIONS_REGLAGES_FIGEES:
        contenu = reglages.get(section)
        if not isinstance(contenu, dict):
            continue
        for cle in sorted(contenu):
            entree = contenu[cle]
            if not isinstance(entree, dict) or 'valeur' not in entree:
                continue
            fige[prefixe + str(cle)] = {
                'valeur': entree.get('valeur'),
                'source': entree.get('source'),
                'reference': entree.get('reference'),
            }
    return fige


def lire_piece_meteo(calepinage):
    """ACAL146 — LA ``records.Attachment`` du DERNIER fichier météo déposé
    sur ce calepinage, ou ``None`` — la SEULE résolution (simulation,
    empreinte, ``GET meteo-fichier/``).

    Le filtre SOCIÉTÉ est EXPLICITE : une pièce « meteo/… » rattachée au même
    ``object_id`` par une autre société n'est jamais lue. Un pivot jamais
    enregistré (``pk`` absent) ou un double de calcul qui n'est pas un modèle
    n'a aucune pièce jointe : rien n'est lu.
    """
    if (getattr(calepinage, 'pk', None) is None
            or not hasattr(type(calepinage), '_meta')):
        return None
    from django.contrib.contenttypes.models import ContentType

    from apps.records.models import Attachment
    from apps.trash.selectors import ids_dans_corbeille

    # ACAL148 — une pièce mise à la CORBEILLE (fichier retiré ou remplacé)
    # n'est plus RETENUE : l'état vit dans la corbeille (patron CAL208), la
    # ligne ``Attachment`` n'est jamais supprimée.
    company = getattr(calepinage, 'company', None)
    # Sous-requête (jamais ``list()``) : la corbeille et la pièce sont lues
    # en UNE requête — ``GET resultat/`` relit cette signature à chaque appel
    # (budget CALX390).
    en_corbeille = ids_dans_corbeille('records.attachment', company=company)
    return (Attachment.objects
            .filter(company=company,
                    content_type=ContentType.objects.get_for_model(
                        type(calepinage)),
                    object_id=calepinage.pk,
                    file_key__startswith='meteo/')
            .exclude(pk__in=en_corbeille)
            .order_by('-id')
            .first())


#: ACAL146 — le suffixe de l'objet COMPAGNON d'un fichier météo déposé :
#: ``<file_key>.meta.json`` porte {fournisseur, sha256, nom}. Ni migration, ni
#: écriture dans ``Calepinage.resultat``.
SUFFIXE_COMPAGNON_METEO = '.meta.json'


def lire_compagnon_meteo(piece):
    """ACAL146 — ``{fournisseur, sha256, nom}`` du fichier météo déposé,
    relu dans son objet compagnon, ou ``{}`` (dépôt antérieur, magasin
    injoignable, contenu illisible)."""
    import json

    from apps.ventes import services as ventes_services

    if piece is None or not getattr(piece, 'file_key', ''):
        return {}
    brut = ventes_services.lire_fichier_toiture(
        piece.file_key + SUFFIXE_COMPAGNON_METEO)
    if not brut:
        return {}
    try:
        donnees = json.loads(brut.decode('utf-8') if isinstance(brut, bytes)
                             else brut)
    except (TypeError, ValueError, UnicodeDecodeError):
        return {}
    return donnees if isinstance(donnees, dict) else {}


def _signature_meteo_deposee(calepinage):
    """ACAL48 — ce qui IDENTIFIE le fichier météo retenu, ou ``None``.

    L'identifiant de la pièce, sa clé de stockage et sa taille : un nouveau
    dépôt (nouvelle pièce), un retrait (retour à PVGIS) ou un autre contenu
    changent la signature. Le contenu n'est PAS relu ici — l'empreinte est
    calculée à chaque ``GET resultat/`` et ne va pas chercher le fichier dans
    le magasin d'objets à chaque lecture.
    """
    piece = lire_piece_meteo(calepinage)
    if piece is None:
        return None
    return {'piece_jointe': piece.pk, 'cle': piece.file_key or '',
            'taille': getattr(piece, 'size', None)}


def empreinte_simulation(calepinage, *, document, donnees, materiel,
                         reglages):
    """ACAL48 — L'empreinte de SIMULATION (D-ACAL-21) : SHA-256 hex.

    = l'empreinte « document » (``services/layout.py::empreinte_document``,
    hors volatils : horizon, ombrage dessiné, environnement, obstacles,
    consommation, stratégie batterie, épingle… y sont déjà) + les entrées
    HORS ``roof_layout`` :

    * les postes de pertes SAISIS du calepinage (IAM comprise) ;
    * les réglages société LUS par la simulation
      (:data:`SECTIONS_REGLAGES_SIMULEES`) ;
    * les fiches module / onduleur / optimiseur ENTIÈRES et leurs
      désignations ;
    * les saisies électriques simulées (:data:`ENTREES_ELECTRIQUES_SIMULEES`)
      et les options du noyau (longueurs, phases, régime…) ;
    * la saisie de raccordement (cos φ, plafond d'injection) ;
    * le site (lat/lon arrondis à 5 décimales, altitude, fuseau effectif) ;
    * la signature du fichier météo retenu ;
    * la grille horaire TOU de la société ;
    * :data:`VERSION_SIMULATION`.

    ``document`` est un PARAMÈTRE : la même fonction sert une variante
    (D-ACAL-17). Les températures de REPLI (PVGIS TMY en panne) n'y entrent
    pas — seules les températures SAISIES comptent, une panne réseau ne
    périme rien. ``empreinte_entree`` (``services/chaines.py``) reste
    l'empreinte d'AFFECTATION et n'est plus jamais comparée à
    ``resultat.simulation``.

    Lecture seule : rien n'est écrit.
    """
    import hashlib

    from .batterie import heures_tarif_societe
    from .electrique import _options_entree
    from .layout import empreinte_document
    from .raccordement import saisie_du_calepinage

    reglages = reglages if isinstance(reglages, dict) else {}
    donnees = donnees if isinstance(donnees, dict) else {}
    materiel = materiel if isinstance(materiel, dict) else {}
    site = _site_du_calepinage(calepinage, document,
                               dict(reglages.get('imagerie') or {}))
    for cle in ('lat', 'lon'):
        if site.get(cle) is not None:
            site[cle] = round(float(site[cle]), 5)
    charge = {
        'version_simulation': VERSION_SIMULATION,
        'document': empreinte_document(document),
        # Les postes STOCKÉS, tels quels : l'empreinte constate un changement,
        # elle ne valide pas (un poste devenu illisible ne fait pas tomber
        # ``GET resultat/`` ; la simulation, elle, le refuse en le nommant).
        'postes': getattr(calepinage, 'pertes', None) or [],
        # Une section absente et une section vide disent la même chose
        # (« rien de saisi ») : elles ne doivent pas périmer l'une l'autre.
        'reglages': {section: reglages.get(section) or {}
                     for section in SECTIONS_REGLAGES_SIMULEES},
        'materiel': {
            'module': materiel.get('module'),
            'onduleur': materiel.get('onduleur'),
            'optimiseur': materiel.get('optimiseur'),
            'designations': materiel.get('designations'),
            # ACAL264 — les fiches des modules PAR PAN, seulement quand un
            # pan porte un autre produit que le défaut (clé absente sinon :
            # l'empreinte d'un champ mono-module est inchangée).
            **({'fiches_modules': {
                str(cle): valeur for cle, valeur
                in materiel['fiches_modules'].items()}}
               if materiel.get('fiches_modules') else {}),
        },
        'entree': {cle: donnees.get(cle)
                   for cle in ENTREES_ELECTRIQUES_SIMULEES
                   if donnees.get(cle) is not None},
        'options': _options_entree(donnees),
        'raccordement': saisie_du_calepinage(calepinage),
        'site': site,
        'meteo_fichier': _signature_meteo_deposee(calepinage),
        'tou_heures': heures_tarif_societe(getattr(calepinage, 'company',
                                                   None)),
    }
    return hashlib.sha256(_canonique(charge).encode('utf-8')).hexdigest()


def construire_contexte(calepinage, *, entree=None, layout=None,
                        materiel=None, reglages=None):
    """Le contexte PARTAGÉ de la simulation, et ce qu'il a fallu lire.

    Args:
        calepinage: le pivot. Sa société borne toutes les lectures.
        entree / layout / materiel: substitutions d'évaluation à chaud, comme
            ``services/electrique.py::conception_du_calepinage``.
        reglages: les sections de réglages société, en remplacement de celles
            que le sélecteur lit. Comme ``materiel``, c'est réservé aux APPELS
            INTERNES et aux tests : AUCUNE vue ne l'expose, pour qu'un corps
            de requête ne puisse jamais glisser un réglage que la société n'a
            pas saisi.

    Returns:
        ``(contexte, meta)``. ``meta`` porte ``hash_entree``, ``pose``,
        ``plans_equipes``, ``document``, ``kwc`` et ``avertissements``.

    Lecture seule : rien n'est écrit ici.
    """
    from .agregation_electrique import affectation_du_calepinage
    from .cables import cables_du_calepinage
    from .chaines import bloc_electrique, bloc_pose
    from .electrique import conception_du_calepinage, parametres_societe
    from .norme import norme_applicable
    from .pertes import postes_du_calepinage
    from .raccordement import saisie_du_calepinage

    from .electrique import TemperaturesInvalides

    try:
        conception, materiel_resolu, donnees, document = (
            conception_du_calepinage(calepinage, entree=entree,
                                     layout=layout, materiel=materiel))
    except TemperaturesInvalides as refus:
        # ACAL126 — une seule température saisie : 400 NOMMÉ, jamais 500.
        raise SimulationRefusee(str(refus),
                                champ=getattr(refus, 'champ', '')
                                or 'temperatures') from refus
    company = getattr(calepinage, 'company', None)
    if reglages is None:
        reglages = parametres_societe(calepinage)
    imagerie = dict(reglages.get('imagerie') or {})

    pose = bloc_pose(conception)
    plans = _plans_du_contexte(pose, document)
    plans_equipes = [plan for plan in plans
                     if plan['modules'] and (plan['kwc'] or 0) > 0]

    norme = norme_applicable(reglages)
    cables = cables_du_calepinage(conception,
                                  cheminement=donnees.get('cheminement'),
                                  norme=norme, layout=document)
    electrique, _avertissements = bloc_electrique(conception)
    # CALX183 — la table d'affectation RÉELLE, affectation MANUELLE comprise
    # (CAL234). Jusqu'ici la simulation appelait ``affectation(conception)``
    # sans l'affectation imposée : elle agrégeait donc une AUTRE partition
    # que celle que l'installateur avait enregistrée. Le motif de l'absence
    # de table et les refus de lecture voyagent dans ``meta`` — ils sont
    # publiés en avertissements par :func:`simuler_calepinage`, jamais
    # avalés.
    rattachement = affectation_du_calepinage(conception, donnees)
    table_affectation = list(rattachement['affectation'])

    # CALX63 — la grille horaire de la société (heures seules, jamais un prix)
    # pour la stratégie « heures_tarif » : aucune grille saisie ⇒ None, et la
    # stratégie publie son omission en nommant `parametres.tou_heures`.
    from .batterie import heures_tarif_societe

    contexte = {
        # ── les réglages société (CALX145) ──────────────────────────────
        'reglages_simulation': dict(reglages.get('simulation') or {}),
        'electrique_societe': dict(reglages.get('electrique_societe') or {}),
        'tou_heures': heures_tarif_societe(company),
        # ── les fiches produit, déjà résolues ───────────────────────────
        'fiche_module': materiel_resolu.get('module') or {},
        'fiche_onduleur': materiel_resolu.get('onduleur') or {},
        'fiche_optimiseur': materiel_resolu.get('optimiseur'),
        # ACAL264 — le module par défaut PUIS celui de chaque pan qui en
        # porte un autre : la simulation lit les modules RÉELLEMENT posés.
        'fiches_modules': [materiel_resolu.get('module') or {}] + [
            dict(fiche.get('specs') or {}) for fiche in (
                materiel_resolu.get('fiches_modules') or {}).values()],
        'designations': dict(materiel_resolu.get('designations') or {}),
        'materiel': {
            'optimiseur': materiel_resolu.get('optimiseur'),
            'designations': dict(materiel_resolu.get('designations') or {}),
        },
        # ── le site et le document ──────────────────────────────────────
        'site': _site_du_calepinage(calepinage, document, imagerie),
        'plans': plans,
        'layout': document,
        'ombrage': _ombrage_du_document(document),
        # ACAL123 — le profil tel que l'écran l'enregistre (camelCase v2),
        # converti par LE lecteur unique du document.
        'horizon': profil_depuis_document(
            (document or {}).get('horizonProfile')
            if isinstance(document, dict) else None),
        # ── l'électrique (CALX167-175) ──────────────────────────────────
        'entree_electrique': dict(donnees),
        'electrique': electrique,
        'affectation': table_affectation,
        'cables': cables.get('cables') or [],
        'cheminement': donnees.get('cheminement'),
        'norme': norme,
        'suivi_mpp_par_module': bool(materiel_resolu.get('optimiseur')),
        # ── les postes SAISIS (D-CALX 11 : la liste plate, telle quelle) ─
        'postes_saisis': postes_du_calepinage(calepinage),
        # ── les déclarations aval ───────────────────────────────────────
        'consommation': _declaration_consommation(document),
        'batterie': _declaration_batterie(calepinage, donnees,
                                          materiel_resolu, company),
        # ACAL155 — LA saisie de raccordement (cos φ imposé, plafond
        # d'injection), écrite par ``POST raccordement/`` : jamais une
        # section du document qu'aucun écrivain ne produit.
        'raccordement': saisie_du_calepinage(calepinage),
        # ACAL166 — le mode hors réseau est DÉCLARÉ dans l'entrée électrique
        # enregistrée (jamais une section du document qu'aucun écrivain ne
        # produisait) ; absent, l'installation est raccordée (inchangé).
        'hors_reseau': _section_de_l_entree(donnees, 'hors_reseau'),
        # CALX271 — les batteries du STOCK, pour comparer leurs capacités.
        'capacites_batterie_stock': _capacites_batterie_du_stock(company),
    }
    # ACAL48 — l'empreinte de SIMULATION (D-ACAL-21), plus l'empreinte
    # d'affectation : c'est elle que l'en-tête porte et que la fraîcheur
    # compare, ici, dans la vue ``simuler/`` et dans ``GET resultat/``.
    contexte['hash_entree'] = empreinte_simulation(
        calepinage, document=document, donnees=donnees,
        materiel=materiel_resolu, reglages=reglages)

    meta = {
        'hash_entree': contexte['hash_entree'],
        # ACAL48 / D-ACAL-8 — les réglages FIGÉS dans l'en-tête du résultat.
        'reglages_utilises': _reglages_utilises(reglages),
        'document': document,
        'pose': pose,
        'plans_equipes': plans_equipes,
        'kwc': _nombre(pose.get('kwc')),
        'avertissements': list(materiel_resolu.get('absents') or ()),
        # CALX183 — ``{affectation, motif, avertissements}`` : POURQUOI il n'y
        # a pas de table quand il n'y en a pas.
        'affectation': rattachement,
    }
    return contexte, meta


# ═══════════════════════════════════════════════════════════════════════════
# ACAL126 — LES REFUS NOMMÉS, UNE SEULE SOURCE POUR LA VUE ET POUR LA TÂCHE
# ═══════════════════════════════════════════════════════════════════════════

#: Les exceptions d'ENTRÉE qu'une simulation peut rencontrer après la
#: pré-vérification (réseau PVGIS, horizon ou paramètre d'appel illisible,
#: σ saisi illisible) : toutes deviennent une :class:`SimulationRefusee`
#: qui NOMME son champ.
REFUS_D_ENTREE = (PvgisIndisponible, EntreeInvalide, IncertitudeInvalide)


def _refus_nomme(refus):
    """Une exception d'entrée, convertie en refus NOMMÉ (champ + motif)."""
    champ = getattr(refus, 'champ', '') or 'meteo'
    motif = getattr(refus, 'motif', '') or str(refus)
    return SimulationRefusee(motif, champ=champ)


def verifier_simulable(contexte, meta, *, fichier_depose=False):
    """ACAL126 — les refus AVANT tout calcul, nommés : mode météo saisi,
    au moins un pan équipé, épingle du site (sauf fichier météo déposé),
    pas d'année type sans fichier.

    Appelée par :func:`simuler_calepinage` ET par la vue ``simuler/`` (400
    immédiat au lieu d'une tâche de fond vouée à l'échec) : une seule
    source, jamais une copie. Rend la décision météo.

    Raises:
        SimulationRefusee: le champ fautif est nommé.
    """
    try:
        decision = decision_meteo(contexte)
    except MeteoIndecise as refus:
        raise SimulationRefusee(refus.motif, champ=refus.champ) from refus
    if not meta.get('plans_equipes'):
        raise SimulationRefusee(MOTIF_SANS_PAN_EQUIPE, champ='plans')
    if not fichier_depose:
        site = contexte.get('site') or {}
        if site.get('lat') is None or site.get('lon') is None:
            raise SimulationRefusee(MOTIF_SANS_POINT, champ='site.pin')
        if decision['mode'] == 'tmy':
            # Le service ``tmy`` de PVGIS ne publie que l'irradiance GLOBALE
            # HORIZONTALE : la chaîne travaille sur le PLAN des modules et ne
            # transpose pas. Le refus NOMME la colonne, comme la chaîne le
            # ferait elle-même.
            raise SimulationRefusee(MOTIF_TMY_HORIZONTAL,
                                    champ='parametres.simulation.mode_meteo')
    return decision


def fichier_meteo_depose(calepinage):
    """ACAL126 — un fichier météo est-il déposé sur ce calepinage ? (la vue
    pré-vérifie sans relire le fichier lui-même)."""
    return lire_piece_meteo(calepinage) is not None


# ═══════════════════════════════════════════════════════════════════════════
# LA MÉTÉO — PVGIS, ou le fichier DÉPOSÉ par la société (CALX62)
# ═══════════════════════════════════════════════════════════════════════════

#: ACAL134 — le nombre MAXIMAL de simulations relancées par un appel du geste
#: « tout recalculer » (plan ACAL134, C-ACAL-068) : au-delà, la réponse dit
#: combien RESTENT, et un nouvel appel reprend.
PLAFOND_RECALCUL_PAR_APPEL = 200


def recalculer_simulations_societe(company, user, *,
                                   plafond=PLAFOND_RECALCUL_PAR_APPEL):
    """ACAL134 — relance EN TÂCHE DE FOND chaque simulation de la société.

    Après un changement de réglage société, toutes les simulations sont
    périmées (l'empreinte de simulation porte les réglages, D-ACAL-8). Ce
    geste soumet, pour chaque calepinage NON archivé de ``company`` dont le
    résultat porte une simulation, le MÊME travail que ``POST simuler/``
    (kind ``calepinage``, nature ``simulation``), SANS forcer : une
    simulation encore fraîche se court-circuite d'elle-même.

    Returns:
        ``{soumis, jobs: [{calepinage, job_id}], reste}`` — au plus
        ``plafond`` travaux par appel ; ``reste`` compte ceux à relancer par
        un nouvel appel.
    """
    from core.jobs import submit

    from ..selectors import liste_calepinages
    from ..tasks import (
        KIND_CALEPINAGE, NATURE_SIMULATION,
        simuler_calepinage as tache_de_simulation,
    )

    candidats = []
    for calepinage in liste_calepinages(company).only('pk', 'resultat'):
        entete = ((calepinage.resultat or {}).get(CLE_SIMULATION)
                  if isinstance(calepinage.resultat, dict) else None)
        if isinstance(entete, dict) and entete.get('hash_entree'):
            candidats.append(calepinage.pk)
    jobs = []
    for calepinage_id in candidats[:plafond]:
        job = submit(KIND_CALEPINAGE, tache_de_simulation, company=company,
                     user=user, calepinage_id=calepinage_id,
                     nature=NATURE_SIMULATION, forcer=False)
        jobs.append({'calepinage': calepinage_id, 'job_id': job.pk})
    return {'soumis': len(jobs), 'jobs': jobs,
            'reste': max(0, len(candidats) - len(jobs))}


def _serie_meteo_deposee(calepinage):
    """La série du DERNIER fichier météo déposé sur ce calepinage, ou ``None``.

    CALX62 range le dépôt dans une ``records.Attachment`` rattachée au
    calepinage, sous une clé ``meteo/…``. Quand il y en a un, c'est LUI la
    source météo : la société a mesuré, on ne redemande pas à PVGIS. Un
    fichier illisible (objet effacé du magasin, contenu devenu invalide) rend
    ``None`` — la simulation repart alors sur PVGIS plutôt que de s'arrêter.
    """
    import hashlib

    from apps.ventes import services as ventes_services

    from .meteo_fichier import MeteoFichierRefuse, lire_serie_meteo

    piece = lire_piece_meteo(calepinage)
    if piece is None:
        return None
    contenu = ventes_services.lire_fichier_toiture(piece.file_key)
    if not contenu:
        return None
    # ACAL146 — le fournisseur SAISI au dépôt, REJOUÉ depuis le compagnon.
    compagnon = lire_compagnon_meteo(piece)
    try:
        serie = lire_serie_meteo(
            contenu, fournisseur=str(compagnon.get('fournisseur') or ''),
            nom_fichier=piece.filename or '')
    except MeteoFichierRefuse:
        return None
    serie['identite'] = {
        'piece_jointe': piece.pk,
        'sha256': hashlib.sha256(contenu).hexdigest(),
        'nom': piece.filename or None,
        'fournisseur': compagnon.get('fournisseur') or None,
    }
    return serie


def _serie_de_chaine(reponse, plan):
    """La série qui ENTRE dans la chaîne, pour CE pan.

    La réponse météo porte l'irradiance ; la puissance du champ naît ICI, et
    d'une seule façon : ``p_w = kWc × G(i)`` (:data:`SOURCE_ENTREE_CHAINE`).
    Les points sont RECOPIÉS — deux pans qui partagent la même réponse ne
    peuvent donc pas s'écraser l'un l'autre.
    """
    kwc = _nombre(plan.get('kwc')) or 0.0
    points = []
    for point in (reponse.get('points') or []):
        if not isinstance(point, dict):
            continue
        copie = dict(point)
        globale = _nombre(point.get('gi_w_m2'))
        copie[COLONNE_ENTREE_CHAINE] = (None if globale is None
                                        else kwc * globale)
        points.append(copie)
    bloc = reponse.get('serie_horaire') or {}
    return {
        'points': points,
        'pas_minutes': bloc.get('pas_minutes') or 60,
        'colonne_energie': COLONNE_ENTREE_CHAINE,
    }


def _fournisseur_meteo(*, client, decision, document, fichier=None,
                       compteur=None):
    """``(fournisseur, provenance)`` — UNE requête par couple d'angles.

    ``fournisseur(plan)`` rend la série d'entrée de chaîne du pan.
    ``provenance`` est le bloc ``meteo`` de la première réponse obtenue : c'est
    lui que l'ordonnanceur publie (CALX154).
    """
    memoire = {}
    etat = {'provenance': None}
    compteur = compteur if isinstance(compteur, dict) else {}
    compteur.setdefault('appels', 0)
    debut, fin = (decision['fenetre_annees'] or (None, None))
    # ACAL123 — même lecteur que ``construire_contexte`` : la requête PVGIS
    # porte le profil du document converti en forme service.
    horizon = profil_depuis_document(
        (document or {}).get('horizonProfile')
        if isinstance(document, dict) else None)

    def fournisseur(plan):
        cle = (plan.get('inclinaison_deg'), plan.get('azimut_pvgis_deg'))
        if cle not in memoire:
            if fichier is not None:
                reponse = fichier
            else:
                reponse = client.serie_irradiance(
                    lat=plan.get('lat'), lon=plan.get('lon'),
                    inclinaison_deg=plan.get('inclinaison_deg'),
                    aspect_deg=plan.get('azimut_pvgis_deg'),
                    annee_debut=debut, annee_fin=fin,
                    base=BASE_PAR_DEFAUT, horizon=horizon,
                    composantes=True)
                if not reponse.get('depuis_cache'):
                    compteur['appels'] += 1
            if etat['provenance'] is None:
                etat['provenance'] = reponse.get('meteo') or {}
            memoire[cle] = reponse
        return _serie_de_chaine(memoire[cle], plan)

    return fournisseur, etat


def _plan_avec_le_site(plan, site):
    """Le pan, enrichi des coordonnées du site pour l'appel météo."""
    enrichi = dict(plan)
    enrichi['lat'] = site.get('lat')
    enrichi['lon'] = site.get('lon')
    return enrichi


# ═══════════════════════════════════════════════════════════════════════════
# L'ÉCART CONTRE PVGIS (CALX195) — la réponse BRUTE ``pvcalculation=1``
# ═══════════════════════════════════════════════════════════════════════════

def _reponse_pvcalculation(client, plan, site, decision, cascade, kwc):
    """La réponse PVGIS BRUTE du même plan, à PERTE TOTALE ÉGALE, ou ``None``.

    ``ecart_vs_pvcalc`` compare notre chaîne à la production que PVGIS calcule
    lui-même. Pour que les deux parlent de la même installation, la perte
    plate envoyée à PVGIS est le TOTAL que la cascade vient de mesurer — la
    seule valeur qui rende l'écart lisible comme un écart de MODÈLE.

    ``None`` dès qu'une entrée manque (total de cascade inconnu, fenêtre
    d'années absente en mode année type) ou que PVGIS ne répond pas : le bloc
    ``validation`` est alors publié SANS écart, avec son motif.
    """
    total_pct = _nombre((cascade or {}).get('total_pct'))
    debut, fin = (decision['fenetre_annees'] or (None, None))
    if total_pct is None or debut is None or fin is None or not kwc:
        return None
    appeler = getattr(client, '_appeler', None)
    parametres_communs = getattr(client, '_params_communs', None)
    if not callable(appeler) or not callable(parametres_communs):
        # Un client injecté qui n'expose que la lecture d'irradiance ne peut
        # pas demander une production à PVGIS : l'écart est alors publié SANS
        # mesure, avec son motif, jamais estimé.
        return None
    from .pertes_politique import PertesInvalides, politique_de_pertes

    try:
        politique = politique_de_pertes([{
            'poste': 'chaine_calepinage',
            'libelle': 'Total de la cascade du module',
            'pct': round(total_pct, 3),
            'source': 'mesure',
        }])
        parametres = {
            'lat': site.get('lat'), 'lon': site.get('lon'),
            'base': BASE_PAR_DEFAUT, 'politique': politique,
            'inclinaison_deg': plan.get('inclinaison_deg'),
            'aspect_deg': plan.get('azimut_pvgis_deg'),
            'annee_debut': debut, 'annee_fin': fin,
            'puissance_kwc': kwc,
        }
        # ``serie_horaire`` publie la série DÉJÀ lue ; l'écart, lui, a besoin
        # de la réponse telle que PVGIS l'a servie (``outputs.hourly[].P`` et
        # ``inputs.pv_module``). ``_appeler`` est le point d'entrée unique du
        # client — cadence, retentative et cache compris : l'emprunter évite
        # d'ouvrir un second chemin réseau pour la même requête.
        charge, _depuis_cache = appeler(
            'seriescalc',
            dict(parametres_communs(
                lat=parametres['lat'], lon=parametres['lon'],
                base=parametres['base'], politique=politique),
                startyear=int(debut), endyear=int(fin), pvcalculation=1,
                peakpower=round(float(kwc), 3),
                angle=float(parametres['inclinaison_deg'] or 0.0),
                aspect=float(parametres['aspect_deg'] or 0.0),
                pvtechchoice='crystSi', mountingplace='building',
                outputformat='json'))
        return charge
    except (PertesInvalides, EntreeInvalide, PvgisIndisponible,
            TypeError, ValueError):
        return None


# ═══════════════════════════════════════════════════════════════════════════
# L'ÉCRITURE — fusion de clés, jamais un remplacement
# ═══════════════════════════════════════════════════════════════════════════

def _ecrire_resultat_variante(variante, blocs):
    """ACAL112 — fusionne ``blocs`` dans ``variante.resultat`` relu SOUS
    VERROU de ligne ; seule la colonne ``resultat`` est écrite."""
    from django.db import transaction

    from ..models import CalepinageVariante

    with transaction.atomic():
        fraiche = (CalepinageVariante.objects.select_for_update()
                   .get(pk=variante.pk))
        resultat = (dict(fraiche.resultat)
                    if isinstance(fraiche.resultat, dict) else {})
        resultat.update(blocs)
        fraiche.resultat = resultat
        fraiche.save(update_fields=['resultat', 'updated_at'])
    variante.resultat = resultat


def _poser_version_moteur(calepinage, version):
    """ACAL121 — l'UNIQUE écrivain de ``Calepinage.version_moteur`` : la
    version publiée dans ``resultat['simulation']['version_moteur']``.
    Hors base (pas de ``pk``) ou double de test non-modèle : l'attribut seul
    est posé, rien n'est enregistré."""
    from django.db import models

    calepinage.version_moteur = version or ''
    if getattr(calepinage, 'pk', None) and isinstance(calepinage,
                                                      models.Model):
        calepinage.save(update_fields=['version_moteur', 'updated_at'])


def _simulation_enregistree(calepinage):
    """L'en-tête ``simulation`` déjà écrit sur ce calepinage (``{}`` sinon)."""
    stocke = getattr(calepinage, 'resultat', None)
    stocke = stocke if isinstance(stocke, dict) else {}
    entete = stocke.get(CLE_SIMULATION)
    return dict(entete) if isinstance(entete, dict) else {}


def _ajouter_avertissement(blocs, texte):
    """Un avertissement FRANÇAIS de plus, sans doublon ni chaîne vide."""
    if not texte:
        return
    liste = blocs.get('avertissements')
    if not isinstance(liste, list):
        liste = []
        blocs['avertissements'] = liste
    if texte not in liste:
        liste.append(texte)


#: CALX183 — les TROIS blocs que l'agrégation électrique ajoute sous
#: ``production``. Ils sont TOUJOURS présents : omis, ils valent ``null`` et
#: leur motif part dans ``avertissements`` (discipline du null du contrat).
CLES_AGREGATION = ('par_mppt', 'par_onduleur', 'hors_chaine')

#: Les DEUX pertes de la maille chaîne et leurs motifs, posés sur chaque
#: ligne de ``production.par_chaine``.
CLES_PERTE_CHAINE = ('perte_mismatch_pct', 'perte_ecretage_pct',
                     'motif_mismatch', 'motif_ecretage')

#: Le motif d'une chaîne publiée par CALX182 sans agrégat CALX183 en face
#: (``par_module`` tronqué, chaîne absente de la table d'affectation).
MOTIF_CHAINE_NON_AGREGEE = (
    "cette chaîne n'a pas d'agrégat électrique : ni le mismatch ni "
    "l'écrêtage ne sont lus, et aucune valeur n'est supposée.")


def _poser_les_pertes_de_chaine(production, agregation, motif):
    """CALX183 — les deux pertes de la maille chaîne, ligne par ligne.

    Les QUATRE clés sont posées sur TOUTES les lignes de ``par_chaine``, y
    compris quand l'agrégation s'est omise : un écran qui reçoit parfois une
    clé et parfois pas finit par tester l'ABSENCE DE CLÉ au lieu de l'absence
    de donnée. Une perte non lue vaut ``None`` avec son motif — jamais ``0``,
    qui se lirait « mesuré à zéro » (D-CALX 7).
    """
    par_cle = {(ligne.get('pan'), ligne.get('chaine')): ligne
               for ligne in agregation['par_chaine']
               if isinstance(ligne, dict)}
    for ligne in production.get('par_chaine') or ():
        if not isinstance(ligne, dict):
            continue
        agregee = par_cle.get((ligne.get('pan'), ligne.get('chaine')))
        if agregee is None:
            ligne['perte_mismatch_pct'] = None
            ligne['perte_ecretage_pct'] = None
            ligne['motif_mismatch'] = motif or MOTIF_CHAINE_NON_AGREGEE
            ligne['motif_ecretage'] = motif or MOTIF_CHAINE_NON_AGREGEE
            continue
        for cle in CLES_PERTE_CHAINE:
            ligne[cle] = agregee.get(cle)


def _agregation_electrique(blocs, par_module, contexte, rattachement):
    """CALX183 — la production agrégée par chaîne, MPPT et onduleur.

    ``services/agregation_electrique.py`` était écrit, testé et fusionné sans
    qu'aucun appelant ne l'exécute : c'est ici qu'il entre dans le résultat de
    SIMULATION. Il ne simule rien — il CROISE la table d'affectation réelle
    (affectation manuelle comprise, CAL234) et la production module par
    module (CALX182), à la maille où se lisent l'écrêtage et le mismatch.

    ``par_chaine`` reste celui de CALX182 (il porte en plus ``kwc``,
    ``acces_solaire_min_pct``, ``ecart_intra_chaine_pct`` et ``source``,
    figés par ``contract_samples/calepinage_simulation.json``) : l'agrégation
    l'ENRICHIT des deux pertes de la maille chaîne au lieu de le remplacer,
    ce qui perdrait quatre clés du contrat.

    Sans table d'affectation ou sans module simulé, les trois blocs valent
    ``null`` et le motif — celui de ``services/chaines.py`` quand il existe,
    plus précis que le motif générique — part dans ``avertissements``. Jamais
    des zéros.
    """
    from .agregation_electrique import agregation_production

    production = blocs.get('production')
    if not isinstance(production, dict):
        return
    agregation = agregation_production(
        par_module, contexte.get('affectation') or (),
        # AUCUNE cascade PAR CHAÎNE n'existe dans la simulation d'aujourd'hui
        # : l'attribuer à chaque chaîne inventerait une perte (D-CALX 7),
        # donc les deux clés de la maille chaîne s'omettent avec leur motif.
        cascades=None,
        # ACAL142 — la phase ONDULEUR, elle, existe (ACAL53) : son écrêtage
        # est publié par onduleur.
        cascade_onduleur=[etape for etape in
                          ((blocs.get('cascade') or {}).get('etapes') or ())
                          if isinstance(etape, dict)
                          and etape.get('etape') in ETAPES_ONDULEUR])
    motif = (rattachement or {}).get('motif') or agregation['motif'] or ''
    if motif:
        for cle in CLES_AGREGATION:
            production[cle] = None
        _ajouter_avertissement(blocs, motif)
    else:
        production['par_mppt'] = agregation['par_mppt']
        production['par_onduleur'] = agregation['par_onduleur']
        production['hors_chaine'] = agregation['hors_chaine']
    _poser_les_pertes_de_chaine(production, agregation, motif)
    for texte in agregation['omissions']:
        _ajouter_avertissement(blocs, texte)
    for texte in (rattachement or {}).get('avertissements') or ():
        _ajouter_avertissement(blocs, texte)


def _annoncer_simulation(calepinage):
    """CALX368 — annonce sur le bus ``core.events`` qu'une simulation a abouti.

    Appelée UNIQUEMENT après la fusion réelle du résultat : un « déjà
    calculé », un refus ou un calcul à blanc (``enregistrer=False``)
    n'annoncent rien. Un pivot jamais enregistré (``pk`` absent) n'a rien
    écrit et n'annonce donc rien non plus.

    Le module ne sait pas qui écoute (aujourd'hui : le webhook
    ``calepinage.simule`` de ``apps.publicapi``). Best-effort : un abonné qui
    lève ne transforme jamais une simulation ENREGISTRÉE en échec — le
    résultat est déjà en base, la réponse doit le dire.
    """
    if getattr(calepinage, 'pk', None) is None:
        return
    from core import events

    try:
        events.calepinage_simule.send(
            sender=type(calepinage), calepinage=calepinage,
            company_id=getattr(calepinage, 'company_id', None))
    except Exception:  # noqa: BLE001 — un abonné ne casse jamais le calcul
        logger.exception('calepinage_simule : un abonné a échoué '
                         '(calepinage %s)', getattr(calepinage, 'pk', None))


def _horodatage(maintenant=None):
    """L'instant du calcul, à la seconde, forme ``…Z`` du contrat."""
    moment = maintenant or datetime.datetime.now(datetime.timezone.utc)
    return moment.replace(microsecond=0).isoformat().replace('+00:00', 'Z')


# ═══════════════════════════════════════════════════════════════════════════
# LE POINT D'ENTRÉE
# ═══════════════════════════════════════════════════════════════════════════

def simuler_calepinage(calepinage, *, forcer=False, client=None,
                       maintenant=None, enregistrer=True, materiel=None,
                       reglages=None, variante=None):
    """Simule le calepinage et ÉCRIT le résultat — le seul chemin (D-CALX 4).

    Args:
        calepinage: le pivot à simuler.
        forcer: relance le calcul même si l'empreinte des entrées n'a pas
            bougé. À ``False`` (défaut), une entrée inchangée rend la date du
            calcul existant sans rien recalculer.
        client: le ``ClientPvgis`` à employer (les tests en passent un dont le
            transport rejoue une réponse enregistrée). À défaut, un client
            neuf : cadence, retentative et cache de processus compris.
        maintenant: l'horodatage du calcul (les tests le figent).
        enregistrer: ``False`` rend les blocs SANS les écrire (usage interne
            et tests) — rien n'est alors posé sur le calepinage.
        materiel / reglages: substitutions réservées aux APPELS INTERNES et
            aux tests, décrites par :func:`construire_contexte`.
        variante: ACAL112 (D-ACAL-17) — une variante du calepinage : le
            contexte est construit sur ``variante.roof_layout`` avec les
            pertes et réglages du calepinage, et le résultat est écrit par
            FUSION SUR LA VARIANTE — ``Calepinage.resultat`` reste intact.

    Returns:
        dict — ``{deja_calcule: True, calcule_le, hash_entree, detail}`` quand
        rien n'a été recalculé, sinon ``{deja_calcule: False, hash_entree,
        calcule_le, duree_s, blocs}`` où ``blocs`` est ce qui a été fusionné
        dans ``Calepinage.resultat``.

    Raises:
        SimulationRefusee: un réglage ou une entrée INDISPENSABLE manque — le
            champ fautif est nommé, jamais un refus générique.
    """
    depart = time.monotonic()
    if variante is not None and not isinstance(
            getattr(variante, 'roof_layout', None), dict):
        raise SimulationRefusee(
            "La variante n'a pas de conception : dessinez-la avant de la "
            'simuler.', champ='variante')
    contexte, meta = construire_contexte(
        calepinage, materiel=materiel, reglages=reglages,
        layout=(variante.roof_layout if variante is not None else None))
    empreinte = meta['hash_entree']

    entete = _simulation_enregistree(
        variante if variante is not None else calepinage)
    if not forcer and empreinte and entete.get('hash_entree') == empreinte:
        return {
            'deja_calcule': True,
            'calcule_le': entete.get('calcule_le'),
            'hash_entree': empreinte,
            'detail': DETAIL_DEJA_CALCULE,
        }

    # 1. LE MODE MÉTÉO, AVANT LE MOINDRE APPEL RÉSEAU (CALX153) — et les
    # autres refus nommés, par LA fonction que la vue appelle aussi (ACAL126).
    fichier = _serie_meteo_deposee(calepinage)
    decision = verifier_simulable(contexte, meta,
                                  fichier_depose=fichier is not None)
    plans_equipes = meta['plans_equipes']
    site = contexte['site']

    compteur = {'appels': 0}
    client = client if client is not None else ClientPvgis()
    fournisseur, provenance = _fournisseur_meteo(
        client=client, decision=decision,
        document=meta['document'], fichier=fichier, compteur=compteur)
    contexte[CLE_FOURNISSEUR_METEO] = fournisseur
    # CALX58 — le MÊME client sert le plan optimal du site (un appel PVcalc
    # « optimalangles », cache et cadence compris). Absent, le TOF est omis
    # avec son motif plutôt que supposé à 1,0.
    contexte[CLE_CLIENT_PVGIS] = client

    blocs = {}
    # ACAL139 — un pan est-ouest est simulé en DEUX jambes (face E, face O),
    # chacune à son aspect PVGIS et pour sa part du kWc ; la météo de
    # référence est celle de la jambe (ou du pan) la plus puissante.
    plans_chaine, avertissements_jambes = _plans_de_chaine(plans_equipes)
    for texte in avertissements_jambes:
        _ajouter_avertissement(blocs, texte)
    reference = max(plans_chaine, key=lambda plan: plan.get('kwc') or 0.0)
    reference = _plan_avec_le_site(reference, site)

    # 1 bis. LA MÉTÉO DE RÉFÉRENCE, AVANT TOUTE CHAÎNE (ACAL53) : sa
    # provenance (``meteo.heure``) est ce que chaque chaîne de pan lit pour
    # se ré-indexer et appliquer IAM, horizon, inter-rangées et accès module.
    try:
        serie_reference = fournisseur(reference)
    except REFUS_D_ENTREE as refus:
        raise _refus_nomme(refus) from refus
    contexte['meteo'] = dict(provenance['provenance'] or {})
    contexte['plan'] = reference

    ecrit = {}
    sorties = {}
    try:
        if len(plans_chaine) > 1:
            # 2. PLUSIEURS PANS (ACAL53) : phase PAN pan par pan, phase
            # ONDULEUR sur la SOMME DC des pans rattachés, phase SITE.
            sortie, cascade, sorties = _chaine_par_phases(
                contexte, plans_equipes, site, fournisseur, ecrit,
                plans_chaine=plans_chaine)
            if fichier is not None and len(plans_equipes) > 1:
                _ajouter_avertissement(
                    blocs, MOTIF_FICHIER_PLUSIEURS_PANS.format(
                        pans=len(plans_equipes)))
        else:
            # 2. UN SEUL PAN : la chaîne entière d'affilée (inchangé).
            sortie, cascade = appliquer_chaine(serie_reference, contexte,
                                               ecrit)
    except REFUS_D_ENTREE as refus:
        # ACAL126 — un horizon illisible, PVGIS indisponible pour un pan, un
        # σ saisi illisible : un refus NOMMÉ, jamais une exception brute.
        raise _refus_nomme(refus) from refus
    blocs['cascade'] = cascade
    blocs['meteo'] = ecrit['meteo']
    blocs['production'] = ecrit['production']
    blocs['serie_horaire'] = ecrit['serie_horaire']
    # CALX58 — le bloc TOF/TSRF par pan, publié par la chaîne (elle seule
    # tient les séries par pan) et relayé tel quel.
    blocs['ombrage'] = ecrit['ombrage']
    for texte in (ecrit.get('avertissements') or []):
        _ajouter_avertissement(blocs, texte)
    # ACAL49 — la « borne haute » ouvre les avertissements (D-ACAL-7).
    entete = completude_de_la_chaine(cascade, contexte)['avertissement']
    if entete and entete in blocs.get('avertissements', ()):
        blocs['avertissements'].remove(entete)
        blocs['avertissements'].insert(0, entete)
    # Le compteur d'appels RÉELS : l'ordonnanceur compte ses demandes, le
    # fournisseur compte ce qui est réellement parti sur le réseau.
    blocs['meteo']['appels_pvgis'] = compteur['appels']
    # ACAL146 — ``meteo.fichier`` {nom, fournisseur} quand un fichier déposé
    # est la source (``null`` sinon : PVGIS), et le fournisseur rejoué.
    identite = (fichier or {}).get('identite') if fichier else None
    blocs['meteo']['fichier'] = (
        {'nom': identite.get('nom'), 'fournisseur': identite.get('fournisseur')}
        if identite else None)
    if identite:
        blocs['meteo']['fournisseur'] = identite.get('fournisseur')

    # 3. LA SIMULATION MODULE PAR MODULE (CALX182).
    par_module = production_module_par_module(contexte)
    if par_module.get('par_module') or par_module.get('par_chaine'):
        blocs['production']['par_module'] = par_module['par_module']
        blocs['production']['par_chaine'] = par_module['par_chaine']
    _ajouter_avertissement(blocs, par_module.get('motif'))
    # CALX183 — la MAILLE ÉLECTRIQUE : par chaîne, par MPPT, par onduleur.
    _agregation_electrique(blocs, par_module, contexte, meta['affectation'])

    # 4. LA CHARGE, PUIS BATTERIE → AUTOCONSOMMATION → HORS RÉSEAU.
    # La série du SITE : sortie de la chaîne (un pan) ou de la phase SITE
    # appliquée à la somme des pans (ACAL53). C'est elle qui croise la
    # consommation, et c'est sur elle que se lisent PR et écart PVcalc.
    serie_site = serie_production = sortie
    from .charges import ChargeInvalide
    from .courbe_charge import CourbeChargeInvalide, construire_courbe_charge

    try:
        charge = construire_courbe_charge(serie_site, contexte)
    except (ChargeInvalide, CourbeChargeInvalide) as refus:
        raise SimulationRefusee(str(refus),
                                champ=getattr(refus, 'champ',
                                              'consommation')) from refus
    blocs['consommation'] = charge['consommation']
    for texte in (charge.get('avertissements') or []):
        _ajouter_avertissement(blocs, texte)
    contexte[CLE_CHARGE] = {'pas_minutes': charge.get('pas_minutes'),
                            'points': charge.get('courbe') or []}

    serie_site, blocs['batterie'] = bloc_batterie(serie_site, contexte,
                                                  charge=charge)
    serie_site, blocs['autoconsommation'] = bloc_autoconsommation(
        serie_site, contexte, charge=charge)
    serie_site, blocs['hors_reseau'] = bloc_hors_reseau(serie_site, contexte,
                                                        charge=charge)
    # ACAL142 — la série PERSISTÉE est celle d'APRÈS batterie,
    # autoconsommation et hors réseau : elle porte charge_kwh,
    # batterie_soc_pct, reseau_import_kwh et reseau_export_kwh (l'export CSV
    # les promet « pour refaire le calcul »), sous la MÊME borne de volume.
    blocs['serie_horaire'] = bloc_serie_horaire(serie_site)

    # 5. INCERTITUDE, PERFORMANCE, ÉCART PVGIS, PROJECTION.
    total = blocs['production'].get('total') or {}
    annuels = {ligne['annee']: ligne['kwh']
               for ligne in (blocs['production'].get('annees') or [])
               if isinstance(ligne, dict) and ligne.get('kwh') is not None}
    try:
        blocs['incertitude'] = bloc_incertitude(
            total.get('p50_kwh'), totaux_par_annee=annuels,
            reglages=contexte['reglages_simulation'])
    except IncertitudeInvalide as refus:
        # ACAL126 — un σ saisi illisible (« 2,5 ») : refus NOMMÉ.
        raise _refus_nomme(refus) from refus
    # ACAL49 — P75, P90 et P95 masqués ENSEMBLE tant que le socle manque :
    # la complétude est celle que la chaîne a publiée, jamais recalculée.
    masquer_depassements(blocs['incertitude'],
                         total.get('performance_ratio_motif'))
    # ACAL53 — le PR est UNE définition : celui de ``production.total`` ;
    # ``bloc_performance`` ne garde en propre que sa variante corrigée en
    # température, lue sur la série du site au kWc total.
    blocs['performance'] = bloc_performance(
        serie_production, kwc=meta['kwc'],
        fiche_module=contexte['fiche_module'],
        pr=total.get('performance_ratio'),
        irradiation_incidente=cascade.get('irradiation_incidente_kwh_m2'))

    reponse_pvgis = None
    if fichier is None and _orientations_identiques(plans_chaine):
        # Une série DÉPOSÉE n'a pas de contrepartie « PVGIS a calculé la même
        # installation » : l'écart est alors publié SANS mesure, avec son
        # motif, plutôt que confronté à un autre point que celui du fichier.
        # ACAL53 — PVcalc décrit UN plan : des pans d'orientations
        # différentes ne s'y comparent pas (écart publié sans mesure).
        reponse_pvgis = _reponse_pvcalculation(
            client, reference, site, decision, cascade, meta['kwc'])
    blocs['validation'] = ecart_vs_pvcalc(
        serie_reference, contexte, reponse_pvgis, kwc=meta['kwc'],
        maintenant=maintenant, sortie=serie_production, cascade=cascade)
    _ajouter_avertissement(blocs, blocs['validation'].get('avertissement'))

    projection = tableau_pluriannuel(total.get('p50_kwh'), contexte)
    # CALX63 — chaque année de la projection porte la capacité restante de la
    # batterie quand le vieillissement est publié (fiche cycles/EOL saisie) ;
    # sans lui, les lignes sortent inchangées.
    from .batterie import capacite_batterie_par_annee
    blocs['production']['projection'] = capacite_batterie_par_annee(
        projection['annees'],
        ((blocs.get('batterie') or {}).get('total') or {}).get('vieillissement'))
    if projection.get('motif_omission'):
        _ajouter_avertissement(blocs, MOTIF_PROJECTION.format(
            motif=projection['motif_omission']))

    for texte in meta['avertissements']:
        _ajouter_avertissement(blocs, texte)

    calcule_le = _horodatage(maintenant)
    blocs[CLE_SIMULATION] = {
        'hash_entree': empreinte,
        # ACAL48 — la version du modèle de simulation et les réglages FIGÉS
        # (D-ACAL-8) : le résultat dit avec quoi il a été calculé.
        'version_simulation': VERSION_SIMULATION,
        'reglages_utilises': meta['reglages_utilises'],
        # ACAL146 — le fichier météo RETENU (identité + empreinte du
        # contenu), ``null`` quand la source est PVGIS.
        'meteo_fichier': ({'piece_jointe': identite.get('piece_jointe'),
                           'sha256': identite.get('sha256')}
                          if identite else None),
        'version_moteur': _version_moteur(),
        'calcule_le': calcule_le,
        'duree_s': round(time.monotonic() - depart, 3),
    }
    if enregistrer and variante is not None:
        # ACAL112 — la fusion PROPRE à la variante (jamais celle du
        # calepinage) : relue sous verrou de ligne, clés fusionnées.
        _ecrire_resultat_variante(variante, blocs)
    elif enregistrer:
        # ACAL57 — l'écrivain unique : les blocs de la simulation sont posés
        # PAR FUSION DE CLÉS sur le resultat RELU sous verrou au moment
        # d'écrire. Une saisie faite PENDANT le calcul (``entree_electrique``,
        # ``sld_edition``…) n'est donc jamais effacée par l'instantané lu au
        # début. Seule la colonne ``resultat`` est écrite — AUCUN statut.
        # ACAL121 — ``Calepinage.version_moteur`` est écrit dans la MÊME
        # transaction, depuis la version PUBLIÉE dans ``resultat.simulation``
        # (une seule source) : le pied de planche, les documents et le
        # webhook lisent enfin la version du calcul.
        from django.db import transaction

        from .resultat import modifier_resultat

        with transaction.atomic():
            modifier_resultat(calepinage,
                              lambda resultat: resultat.update(blocs))
            _poser_version_moteur(
                calepinage, blocs[CLE_SIMULATION]['version_moteur'])
        _annoncer_simulation(calepinage)
    return {
        'deja_calcule': False,
        'hash_entree': empreinte,
        'calcule_le': calcule_le,
        'duree_s': blocs[CLE_SIMULATION]['duree_s'],
        'blocs': blocs,
    }


#: ACAL53 — l'écrêtage d'un toit à plusieurs pans se lit sur la SOMME DC des
#: pans RATTACHÉS aux onduleurs : sans table d'affectation, on ne sait pas
#: quels pans partagent quel onduleur, et l'étape est OMISE avec ce motif
#: (jamais 0 %).
MOTIF_ECRETAGE_SANS_AFFECTATION = (
    "Aucune table d'affectation des pans aux onduleurs : l'écrêtage d'un toit "
    'à plusieurs pans se lit sur la SOMME des pans rattachés à chaque '
    "onduleur, et cette somme n'est pas connue — étape omise, aucune valeur "
    'supposée.')


def _copier_meteo(provenance):
    """Une copie PROFONDE du bloc météo : chaque chaîne de pan ré-indexe sa
    série et réécrit ``meteo.heure`` — un dict partagé ferait sauter la
    ré-indexation du pan suivant."""
    import copy

    return copy.deepcopy(provenance if isinstance(provenance, dict) else {})


def _somme_des_series(series):
    """La SOMME point à point de séries de même pas, sur leur colonne
    d'énergie (la même pour toutes : elles sortent des mêmes étapes).

    Les points sont RECOPIÉS depuis la première série (ses colonnes non
    énergétiques — températures, irradiance — y restent) ; les séries reçues
    ne bougent pas. ``None`` si aucune colonne n'est lisible.
    """
    from .etapes import colonne_energie

    series = [serie for serie in series if isinstance(serie, dict)]
    if not series:
        return None
    colonne = colonne_energie(series[0])
    if colonne is None:
        return None
    points = []
    for rang, point in enumerate(series[0].get('points') or []):
        copie = dict(point)
        cumul = _nombre(point.get(colonne))
        for autre in series[1:]:
            autres_points = autre.get('points') or []
            if rang >= len(autres_points):
                continue
            valeur = _nombre(autres_points[rang].get(colonne))
            if valeur is not None:
                cumul = valeur if cumul is None else cumul + valeur
        copie[colonne] = cumul
        points.append(copie)
    return {'points': points,
            'pas_minutes': series[0].get('pas_minutes'),
            'colonne_energie': colonne}


def _sorties_par_pan(series_dc, somme_dc, sortie_site):
    """La sortie du SITE répartie HEURE PAR HEURE entre les pans, au prorata
    de leur puissance DC À CETTE HEURE (celle qui est entrée dans l'onduleur).

    Ce n'est pas une part supposée : à chaque pas, l'onduleur convertit la
    somme de ce que les pans lui envoient, et chaque pan reçoit la part de la
    sortie qu'il a fournie. Les points du pan gardent leurs colonnes propres
    (irradiance de SON plan, pour son TOF et son PR).
    """
    from .etapes import colonne_energie

    colonne_dc = colonne_energie(somme_dc)
    colonne_sortie = colonne_energie(sortie_site)
    points_somme = somme_dc.get('points') or []
    points_sortie = sortie_site.get('points') or []
    rendues = {}
    for cle, serie in series_dc.items():
        points = []
        for rang, point in enumerate(serie.get('points') or []):
            copie = dict(point)
            dc_pan = _nombre(point.get(colonne_dc))
            dc_total = (_nombre(points_somme[rang].get(colonne_dc))
                        if rang < len(points_somme) else None)
            sortie = (_nombre(points_sortie[rang].get(colonne_sortie))
                      if rang < len(points_sortie) else None)
            if sortie is None or dc_pan is None:
                valeur = None
            elif not dc_total:
                valeur = 0.0
            else:
                valeur = sortie * dc_pan / dc_total
            if colonne_sortie != colonne_dc:
                copie.pop(colonne_dc, None)
            copie[colonne_sortie] = valeur
            points.append(copie)
        rendues[cle] = {'points': points,
                        'pas_minutes': serie.get('pas_minutes'),
                        'colonne_energie': colonne_sortie}
    return rendues


def _plans_de_chaine(plans_equipes):
    """ACAL139 — ``(plans simulés, avertissements)`` : un plan par JAMBE.

    Un pan est-ouest donne deux jambes (``pvgis_serie.jambes_du_pan``) :
    même pan au rapport (``parent``), mais chacune son azimut, son aspect
    PVGIS, ses modules et sa part du kWc. Tout autre pan passe tel quel.
    """
    rendus = []
    avertissements = []
    for plan in plans_equipes:
        jambes = jambes_du_pan(plan)
        if len(jambes) == 1 and jambes[0]['face'] is None:
            rendus.append(plan)
            continue
        if any(jambe['hypothese'] for jambe in jambes):
            avertissements.append(AVERTISSEMENT_EST_OUEST_SUPPOSE.format(
                pan=plan.get('pan') or plan.get('cle')))
        for jambe in jambes:
            azimut = jambe['azimut_face_deg']
            rendus.append(dict(
                plan, cle='%s#%s' % (plan.get('cle'), jambe['face']),
                parent=plan.get('cle'), jambe=jambe['face'],
                part=jambe['part'], modules=jambe['modules'],
                kwc=(plan.get('kwc') or 0.0) * jambe['part'],
                inclinaison_deg=jambe['inclinaison_deg'],
                azimut_deg=azimut, azimut_pvgis_deg=azimut_pvgis(azimut)))
    return rendus, avertissements


#: ACAL139 — les colonnes d'irradiance d'une série de pan : celles d'un pan
#: à deux jambes sont la moyenne de ses faces PONDÉRÉE par leur part du kWc.
COLONNES_IRRADIANCE_PAN = ('gi_w_m2', 'gb_i_w_m2', 'gd_i_w_m2', 'gr_i_w_m2')


def _fusionner_jambes(series, parts):
    """La série d'UN pan à partir de ses jambes : énergie SOMMÉE, irradiance
    pondérée par la part de kWc de chaque face (le plan « moyen » du pan)."""
    somme = _somme_des_series(series)
    if somme is None:
        return None
    for rang, point in enumerate(somme['points']):
        for colonne in COLONNES_IRRADIANCE_PAN:
            valeurs = []
            for serie, part in zip(series, parts):
                points = serie.get('points') or []
                valeur = (_nombre(points[rang].get(colonne))
                          if rang < len(points) else None)
                valeurs.append(None if valeur is None else valeur * part)
            if valeurs and all(valeur is not None for valeur in valeurs):
                point[colonne] = sum(valeurs)
    return somme


def _cascade_des_jambes(cascades, plans):
    """La cascade de PHASE PAN d'un pan à deux jambes : leurs kWh sommés
    (``cascade_de_la_somme`` sans onduleur ni site), et l'irradiation
    incidente pondérée par le kWc des jambes."""
    from .chaine_pertes import cascade_de_la_somme

    cascade = cascade_de_la_somme(cascades, None, None)
    kwc = sum((plan.get('kwc') or 0.0) for plan in plans)
    ponderee = None
    for sienne, plan in zip(cascades, plans):
        incidente = sienne.get('irradiation_incidente_kwh_m2')
        if incidente is not None and kwc:
            ponderee = (ponderee or 0.0) + incidente * (plan.get('kwc')
                                                        or 0.0)
    cascade['irradiation_incidente_kwh_m2'] = (
        round(ponderee / kwc, 3) if ponderee is not None else None)
    return cascade


def _chaine_par_phases(contexte, plans_equipes, site, fournisseur, ecrit,
                       plans_chaine=None):
    """ACAL53 — la chaîne d'un toit à PLUSIEURS pans, phase par phase.

    1. phase PAN, pan par pan, chacun avec SA série d'irradiance et une copie
       de la météo de référence (ré-indexation propre) ;
    2. phase ONDULEUR sur la SOMME DC des pans rattachés : la table
       d'affectation ne numérote un onduleur que quand il est seul (sinon
       ``null`` : le noyau dimensionne un modèle, pas des exemplaires) — les
       pans rattachés partagent donc l'ensemble des onduleurs, que les étapes
       lisent déjà comme tel ; sans table, l'écrêtage est OMIS
       (:data:`MOTIF_ECRETAGE_SANS_AFFECTATION`) ;
    3. phase SITE sur la sortie de l'ensemble.

    Publie dans ``ecrit`` (meteo, production, ombrage, série horaire) avec la
    cascade de la SOMME et les sorties par pan. Rend ``(sortie du site,
    cascade de la somme, {pan: sortie})``.
    """
    from .chaine_pertes import (
        CLE_CASCADES_PAR_PAN, CLE_CROISEMENT_HORAIRE, cascade_de_la_somme,
        publier_resultat_de_chaine,
    )

    provenance = contexte.get('meteo')
    series_jambes = {}
    cascades_jambes = {}
    premier_contexte = None
    plans_chaine = plans_chaine or plans_equipes
    for plan in plans_chaine:
        avec_site = _plan_avec_le_site(plan, site)
        contexte_plan = dict(contexte)
        contexte_plan['meteo'] = _copier_meteo(provenance)
        contexte_plan['plan'] = avec_site
        contexte_plan['plans'] = [avec_site]
        serie_dc, cascade_pan = appliquer_chaine(
            fournisseur(avec_site), contexte_plan, phase='pan')
        series_jambes[plan['cle']] = serie_dc
        cascades_jambes[plan['cle']] = cascade_pan
        if premier_contexte is None:
            premier_contexte = contexte_plan
    # ACAL139 — les jambes d'un pan est-ouest se REJOIGNENT en UN pan : le
    # rapport, les sorties et les cascades restent pan par pan.
    series_dc = {}
    cascades_pan = {}
    for plan in plans_equipes:
        jambes = [jambe for jambe in plans_chaine
                  if jambe.get('parent') == plan['cle']]
        if not jambes:
            series_dc[plan['cle']] = series_jambes[plan['cle']]
            cascades_pan[plan['cle']] = cascades_jambes[plan['cle']]
            continue
        series = [series_jambes[jambe['cle']] for jambe in jambes]
        cascades = [cascades_jambes[jambe['cle']] for jambe in jambes]
        if len(jambes) == 1:
            series_dc[plan['cle']] = series[0]
            cascades_pan[plan['cle']] = cascades[0]
            continue
        series_dc[plan['cle']] = _fusionner_jambes(
            series, [jambe['part'] for jambe in jambes])
        cascades_pan[plan['cle']] = _cascade_des_jambes(cascades, jambes)
    # Le verdict horaire est le même pour tous les pans (même série de
    # référence, même fuseau) : celui du premier est publié.
    contexte['meteo'] = premier_contexte['meteo']
    if CLE_CROISEMENT_HORAIRE in premier_contexte:
        contexte[CLE_CROISEMENT_HORAIRE] = premier_contexte[
            CLE_CROISEMENT_HORAIRE]

    somme_dc = _somme_des_series(
        [series_dc[plan['cle']] for plan in plans_equipes])
    kwc_total = sum((plan.get('kwc') or 0.0) for plan in plans_equipes)
    contexte_onduleur = dict(contexte)
    contexte_onduleur['plan'] = dict(
        contexte.get('plan') or {}, kwc=kwc_total,
        modules=sum(int(plan.get('modules') or 0) for plan in plans_equipes))
    omettre = ({} if contexte.get('affectation')
               else {'ecretage': MOTIF_ECRETAGE_SANS_AFFECTATION})
    sortie_ac, cascade_onduleur = appliquer_chaine(
        somme_dc, contexte_onduleur, phase='onduleur', omettre=omettre)
    sortie, cascade_site = appliquer_chaine(
        sortie_ac, contexte_onduleur, phase='site')

    cascade = cascade_de_la_somme(
        [cascades_pan[plan['cle']] for plan in plans_equipes],
        cascade_onduleur, cascade_site, contexte)
    # ACAL128 — l'irradiation incidente du site, pondérée par le kWc.
    ponderee = None
    for plan in plans_equipes:
        incidente = cascades_pan[plan['cle']].get(
            'irradiation_incidente_kwh_m2')
        if incidente is not None and kwc_total:
            ponderee = (ponderee or 0.0) + incidente * (plan.get('kwc')
                                                        or 0.0)
    cascade['irradiation_incidente_kwh_m2'] = (
        round(ponderee / kwc_total, 3) if ponderee is not None else None)
    sorties = _sorties_par_pan(series_dc, somme_dc, sortie)
    contexte[CLE_SORTIES_PAR_PAN] = sorties
    contexte[CLE_CASCADES_PAR_PAN] = cascades_pan
    publier_resultat_de_chaine(ecrit, sortie, contexte, cascade)
    return sortie, cascade, sorties


def _orientations_identiques(plans_equipes):
    """Tous les pans ont-ils la même inclinaison et le même azimut ?"""
    angles = {(plan.get('inclinaison_deg'), plan.get('azimut_pvgis_deg'))
              for plan in plans_equipes}
    return len(angles) <= 1


def _version_moteur():
    """La version du moteur qui a produit ce résultat — une seule source."""
    from core.electrique.version import VERSION_MOTEUR

    return VERSION_MOTEUR
