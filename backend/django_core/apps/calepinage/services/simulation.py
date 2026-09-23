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
2. la chaîne de pertes, UNE PASSE PAR PLAN : chaque pan a sa propre irradiance,
   donc sa propre cascade. Les séries de sortie sont posées sous
   ``sorties_par_pan`` pour que la chaîne additionne les pans sans jamais
   répartir un total au prorata.
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
import time

from .chaine_pertes import (
    CLE_CHARGE, CLE_CLIENT_PVGIS, CLE_FOURNISSEUR_METEO, CLE_SORTIES_PAR_PAN,
    MOTIF_TMY_HORIZONTAL, MeteoIndecise, appliquer_chaine, decision_meteo,
)
from .etapes.autoconsommation import bloc_autoconsommation
from .etapes.batterie import bloc_batterie
from .etapes.hors_reseau import bloc_hors_reseau
from .etapes.vieillissement import tableau_pluriannuel
from .incertitude import bloc_incertitude
from .performance import bloc_performance
from .pvgis_serie import (
    BASE_PAR_DEFAUT, ClientPvgis, EntreeInvalide, PvgisIndisponible,
    azimut_pvgis,
)
from .simulation_modules import production_module_par_module
from .validation import ecart_vs_pvcalc

__all__ = [
    'CLE_SIMULATION', 'COLONNE_ENTREE_CHAINE', 'DETAIL_DEJA_CALCULE',
    'MOTIF_PLUSIEURS_PANS', 'MOTIF_SANS_PAN_EQUIPE', 'MOTIF_SANS_POINT',
    'SOURCE_ENTREE_CHAINE', 'SimulationRefusee', 'construire_contexte',
    'simuler_calepinage',
]

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
    "puissance crête : il n'y a rien à simuler. Posez des modules et "
    'désignez le module PV avant de lancer la simulation.')

MOTIF_SANS_POINT = (
    "Le site de ce calepinage n'a pas de point GPS : la météo se demande à "
    'une latitude et une longitude, elles ne se devinent pas. Posez '
    "l'épingle du site sur la carte (« roof_layout.pin »).")

MOTIF_PLUSIEURS_PANS = (
    'Plusieurs pans équipés : la cascade et la série horaire publiées sont '
    'celles du pan « {pan} » (le plus puissant). La production, elle, est la '
    'SOMME des pans — chacun a été passé dans la chaîne avec sa propre '
    'irradiance.')

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

def _nombre(valeur):
    """Un flottant lisible, ou ``None`` — jamais un 0 de repli."""
    if valeur is None or isinstance(valeur, bool):
        return None
    try:
        nombre = float(valeur)
    except (TypeError, ValueError):
        return None
    return None if nombre != nombre else nombre


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

    Rien n'est normalisé ici : ``services/ombrage_chaines.py`` et les étapes
    savent lire les deux orthographes (``solar_access`` / ``solarAccess``).
    """
    document = document if isinstance(document, dict) else {}
    return {
        'solar_access': document.get('solar_access'),
        'solarAccess': document.get('solarAccess'),
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
    return {
        'lat': lat,
        'lon': lon,
        'altitude_m': altitude_du_site(imagerie)['altitude_m'],
        'fuseau': fuseau_du_site(imagerie)['fuseau'],
    }


def _declaration_batterie(calepinage, document, entree, company):
    """La batterie DÉCLARÉE et les specs de son pack, ou ``{}``.

    La déclaration vit sur le document (``roof_layout.battery``) ; les
    grandeurs viennent de la FICHE du produit batterie du devis lié, résolue
    ici parce que ce module est le seul à avoir accès au stock. Aucune
    stratégie n'est supposée : sans stratégie saisie, CALX188 omet le bloc et
    le dit.
    """
    from .batterie import specs_batterie
    from .equipements import equipements_du_calepinage

    brute = (document.get('battery') if isinstance(document, dict) else None)
    if not isinstance(brute, dict) or not brute:
        return {}

    produit_batterie = None
    produit_onduleur = None
    if company is not None:
        from apps.stock.selectors import get_produit_scoped

        equipements = equipements_du_calepinage(calepinage)
        bloc = equipements.get('batterie') if isinstance(equipements,
                                                         dict) else None
        if isinstance(bloc, dict) and bloc.get('produit'):
            produit_batterie = get_produit_scoped(company, bloc['produit'])
        identifiant = (entree or {}).get('onduleur_produit')
        if identifiant not in (None, ''):
            produit_onduleur = get_produit_scoped(company, identifiant)

    packs = int(_nombre(brute.get('count')) or 1) or 1
    declaration = dict(brute)
    declaration['groupes'] = [{
        'groupe': str(brute.get('model') or 'Batterie'),
        'packs': packs,
        'specs': specs_batterie(produit_batterie,
                                produit_onduleur=produit_onduleur,
                                nb_packs=packs),
    }]
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


def _section_du_document(document, nom):
    """Une section DÉCLARÉE du document (``{}`` quand elle n'y est pas).

    Rien n'est supposé : un raccordement sans plafond saisi ne plafonne rien,
    et un calepinage sans section ``hors_reseau`` est raccordé — c'est le cas
    de tous les calepinages existants (comportement d'aujourd'hui inchangé).
    """
    if not isinstance(document, dict):
        return {}
    section = document.get(nom)
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
    from .chaines import bloc_electrique, bloc_pose, empreinte_entree
    from .electrique import (
        _options_entree, conception_du_calepinage, parametres_societe,
    )
    from .norme import norme_applicable
    from .pertes import postes_du_calepinage

    conception, materiel_resolu, donnees, document = conception_du_calepinage(
        calepinage, entree=entree, layout=layout, materiel=materiel)
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

    contexte = {
        # ── les réglages société (CALX145) ──────────────────────────────
        'reglages_simulation': dict(reglages.get('simulation') or {}),
        'electrique_societe': dict(reglages.get('electrique_societe') or {}),
        # ── les fiches produit, déjà résolues ───────────────────────────
        'fiche_module': materiel_resolu.get('module') or {},
        'fiche_onduleur': materiel_resolu.get('onduleur') or {},
        'fiche_optimiseur': materiel_resolu.get('optimiseur'),
        'fiches_modules': [materiel_resolu.get('module') or {}],
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
        'horizon': ((document or {}).get('horizonProfile')
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
        'batterie': _declaration_batterie(calepinage, document, donnees,
                                          company),
        'raccordement': _section_du_document(document, 'raccordement'),
        'hors_reseau': _section_du_document(document, 'hors_reseau'),
        # CALX271 — les batteries du STOCK, pour comparer leurs capacités.
        'capacites_batterie_stock': _capacites_batterie_du_stock(company),
    }
    contexte['hash_entree'] = empreinte_entree(
        document, module_specs=materiel_resolu['module'],
        onduleur_specs=materiel_resolu['onduleur'],
        temperatures=conception.temperatures,
        options=_options_entree(donnees))

    meta = {
        'hash_entree': contexte['hash_entree'],
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
# LA MÉTÉO — PVGIS, ou le fichier DÉPOSÉ par la société (CALX62)
# ═══════════════════════════════════════════════════════════════════════════

def _serie_meteo_deposee(calepinage):
    """La série du DERNIER fichier météo déposé sur ce calepinage, ou ``None``.

    CALX62 range le dépôt dans une ``records.Attachment`` rattachée au
    calepinage, sous une clé ``meteo/…``. Quand il y en a un, c'est LUI la
    source météo : la société a mesuré, on ne redemande pas à PVGIS. Un
    fichier illisible (objet effacé du magasin, contenu devenu invalide) rend
    ``None`` — la simulation repart alors sur PVGIS plutôt que de s'arrêter.
    """
    from django.contrib.contenttypes.models import ContentType

    from apps.records.models import Attachment
    from apps.ventes import services as ventes_services

    from .meteo_fichier import MeteoFichierRefuse, lire_serie_meteo

    if getattr(calepinage, 'pk', None) is None:
        return None
    piece = (Attachment.objects
             .filter(content_type=ContentType.objects.get_for_model(
                 type(calepinage)),
                 object_id=calepinage.pk,
                 file_key__startswith='meteo/')
             .order_by('-id')
             .first())
    if piece is None:
        return None
    contenu = ventes_services.lire_fichier_toiture(piece.file_key)
    if not contenu:
        return None
    try:
        return lire_serie_meteo(contenu, fournisseur='',
                                nom_fichier=piece.filename or '')
    except MeteoFichierRefuse:
        return None


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
    horizon = ((document or {}).get('horizonProfile')
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

def _simulation_enregistree(calepinage):
    """L'en-tête ``simulation`` déjà écrit sur ce calepinage (``{}`` sinon)."""
    stocke = getattr(calepinage, 'resultat', None)
    stocke = stocke if isinstance(stocke, dict) else {}
    entete = stocke.get(CLE_SIMULATION)
    return dict(entete) if isinstance(entete, dict) else {}


def _fusionner(calepinage, blocs):
    """Pose ``blocs`` dans ``Calepinage.resultat`` PAR FUSION DE CLÉS.

    Patron de ``services/electrique.py::enregistrer_entree`` : les clés que la
    simulation ne produit pas (``entree_electrique``, ``pertes`` saisies,
    ``horizon``…) sont conservées à l'octet près. Seule la colonne ``resultat``
    est écrite — AUCUN statut (règle #4).
    """
    resultat = getattr(calepinage, 'resultat', None)
    resultat = dict(resultat) if isinstance(resultat, dict) else {}
    resultat.update(blocs)
    calepinage.resultat = resultat
    if getattr(calepinage, 'pk', None):
        calepinage.save(update_fields=['resultat', 'updated_at'])
    return resultat


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
        # : ``appliquer_chaine`` en rend UNE, celle du plan de référence.
        # L'attribuer à chaque chaîne inventerait une perte (D-CALX 7), donc
        # les deux clés s'omettent avec le motif que CALX183 publie déjà.
        cascades=None)
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


def _horodatage(maintenant=None):
    """L'instant du calcul, à la seconde, forme ``…Z`` du contrat."""
    moment = maintenant or datetime.datetime.now(datetime.timezone.utc)
    return moment.replace(microsecond=0).isoformat().replace('+00:00', 'Z')


# ═══════════════════════════════════════════════════════════════════════════
# LE POINT D'ENTRÉE
# ═══════════════════════════════════════════════════════════════════════════

def simuler_calepinage(calepinage, *, forcer=False, client=None,
                       maintenant=None, enregistrer=True, materiel=None,
                       reglages=None):
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
    contexte, meta = construire_contexte(calepinage, materiel=materiel,
                                         reglages=reglages)
    empreinte = meta['hash_entree']

    entete = _simulation_enregistree(calepinage)
    if not forcer and empreinte and entete.get('hash_entree') == empreinte:
        return {
            'deja_calcule': True,
            'calcule_le': entete.get('calcule_le'),
            'hash_entree': empreinte,
            'detail': DETAIL_DEJA_CALCULE,
        }

    # 1. LE MODE MÉTÉO, AVANT LE MOINDRE APPEL RÉSEAU (CALX153).
    try:
        decision = decision_meteo(contexte)
    except MeteoIndecise as refus:
        raise SimulationRefusee(refus.motif, champ=refus.champ) from refus

    plans_equipes = meta['plans_equipes']
    if not plans_equipes:
        raise SimulationRefusee(MOTIF_SANS_PAN_EQUIPE, champ='plans')

    fichier = _serie_meteo_deposee(calepinage)
    site = contexte['site']
    if fichier is None:
        if site.get('lat') is None or site.get('lon') is None:
            raise SimulationRefusee(MOTIF_SANS_POINT, champ='site.pin')
        if decision['mode'] == 'tmy':
            # Le service ``tmy`` de PVGIS ne publie que l'irradiance GLOBALE
            # HORIZONTALE : la chaîne travaille sur le PLAN des modules et ne
            # transpose pas. Le refus NOMME la colonne, comme la chaîne le
            # ferait elle-même.
            raise SimulationRefusee(MOTIF_TMY_HORIZONTAL,
                                    champ='parametres.simulation.mode_meteo')

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
    reference = max(plans_equipes, key=lambda plan: plan.get('kwc') or 0.0)
    reference = _plan_avec_le_site(reference, site)

    # 2. LA CHAÎNE, UNE PASSE PAR PLAN.
    sorties = {}
    if len(plans_equipes) > 1:
        for plan in plans_equipes:
            avec_site = _plan_avec_le_site(plan, site)
            contexte_plan = dict(contexte)
            contexte_plan['plan'] = avec_site
            contexte_plan['plans'] = [avec_site]
            sortie, _cascade = appliquer_chaine(
                fournisseur(avec_site), contexte_plan)
            sorties[plan['cle']] = sortie
        _ajouter_avertissement(
            blocs, MOTIF_PLUSIEURS_PANS.format(pan=reference['cle']))
        if fichier is not None:
            _ajouter_avertissement(blocs, MOTIF_FICHIER_PLUSIEURS_PANS.format(
                pans=len(plans_equipes)))

    try:
        serie_reference = fournisseur(reference)
    except (PvgisIndisponible, EntreeInvalide) as refus:
        raise SimulationRefusee(str(refus),
                                champ=getattr(refus, 'champ', 'meteo') or
                                'meteo') from refus

    # La provenance de la série AVANT la chaîne : c'est elle que
    # ``_reindexer_sur_l_heure_du_site`` lit (``meteo.heure.base``) et que
    # l'ordonnanceur publie ensuite dans ``resultat['meteo']``.
    contexte['meteo'] = dict(provenance['provenance'] or {})
    contexte[CLE_SORTIES_PAR_PAN] = sorties
    contexte['plan'] = reference

    ecrit = {}
    sortie, cascade = appliquer_chaine(serie_reference, contexte, ecrit)
    blocs['cascade'] = cascade
    blocs['meteo'] = ecrit['meteo']
    blocs['production'] = ecrit['production']
    blocs['serie_horaire'] = ecrit['serie_horaire']
    # CALX58 — le bloc TOF/TSRF par pan, publié par la chaîne (elle seule
    # tient les séries par pan) et relayé tel quel.
    blocs['ombrage'] = ecrit['ombrage']
    for texte in (ecrit.get('avertissements') or []):
        _ajouter_avertissement(blocs, texte)
    # Le compteur d'appels RÉELS : l'ordonnanceur compte ses demandes, le
    # fournisseur compte ce qui est réellement parti sur le réseau.
    blocs['meteo']['appels_pvgis'] = compteur['appels']
    if fichier is not None:
        # Les deux clés de provenance qu'un fichier apporte et que la liste
        # fixe du bloc météo ne porte pas.
        for cle in ('fournisseur', 'fichier'):
            if cle in (provenance['provenance'] or {}):
                blocs['meteo'][cle] = provenance['provenance'][cle]

    # 3. LA SIMULATION MODULE PAR MODULE (CALX182).
    par_module = production_module_par_module(contexte)
    if par_module.get('par_module') or par_module.get('par_chaine'):
        blocs['production']['par_module'] = par_module['par_module']
        blocs['production']['par_chaine'] = par_module['par_chaine']
    _ajouter_avertissement(blocs, par_module.get('motif'))
    # CALX183 — la MAILLE ÉLECTRIQUE : par chaîne, par MPPT, par onduleur.
    _agregation_electrique(blocs, par_module, contexte, meta['affectation'])

    # 4. LA CHARGE, PUIS BATTERIE → AUTOCONSOMMATION → HORS RÉSEAU.
    serie_site = _serie_du_site(sortie, sorties, plans_equipes)
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

    # 5. INCERTITUDE, PERFORMANCE, ÉCART PVGIS, PROJECTION.
    total = blocs['production'].get('total') or {}
    annuels = {ligne['annee']: ligne['kwh']
               for ligne in (blocs['production'].get('annees') or [])
               if isinstance(ligne, dict) and ligne.get('kwh') is not None}
    blocs['incertitude'] = bloc_incertitude(
        total.get('p50_kwh'), totaux_par_annee=annuels,
        reglages=contexte['reglages_simulation'])
    blocs['performance'] = bloc_performance(
        sortie, kwc=meta['kwc'], fiche_module=contexte['fiche_module'])

    reponse_pvgis = None
    if fichier is None:
        # Une série DÉPOSÉE n'a pas de contrepartie « PVGIS a calculé la même
        # installation » : l'écart est alors publié SANS mesure, avec son
        # motif, plutôt que confronté à un autre point que celui du fichier.
        reponse_pvgis = _reponse_pvcalculation(
            client, reference, site, decision, cascade, meta['kwc'])
    blocs['validation'] = ecart_vs_pvcalc(
        serie_reference, contexte, reponse_pvgis, kwc=meta['kwc'],
        maintenant=maintenant)
    _ajouter_avertissement(blocs, blocs['validation'].get('avertissement'))

    projection = tableau_pluriannuel(total.get('p50_kwh'), contexte)
    blocs['production']['projection'] = projection['annees']
    if projection.get('motif_omission'):
        _ajouter_avertissement(blocs, MOTIF_PROJECTION.format(
            motif=projection['motif_omission']))

    for texte in meta['avertissements']:
        _ajouter_avertissement(blocs, texte)

    calcule_le = _horodatage(maintenant)
    blocs[CLE_SIMULATION] = {
        'hash_entree': empreinte,
        'version_moteur': _version_moteur(),
        'calcule_le': calcule_le,
        'duree_s': round(time.monotonic() - depart, 3),
    }
    if enregistrer:
        _fusionner(calepinage, blocs)
    return {
        'deja_calcule': False,
        'hash_entree': empreinte,
        'calcule_le': calcule_le,
        'duree_s': blocs[CLE_SIMULATION]['duree_s'],
        'blocs': blocs,
    }


def _serie_du_site(sortie_reference, sorties, plans_equipes):
    """La série du SITE : la somme des séries de sortie, pan par pan.

    Un seul pan équipé ⇒ sa série EST celle du site. Plusieurs ⇒ l'énergie
    s'additionne point à point sur la colonne déclarée ; les points sont
    recopiés, les séries reçues ne bougent pas. C'est cette série qui croise
    la consommation : croiser celle d'un seul pan sous-estimerait
    l'autoconsommation de tous les autres.
    """
    from .etapes import colonne_energie

    if len(plans_equipes) <= 1 or not sorties:
        return sortie_reference
    series = [sorties[plan['cle']] for plan in plans_equipes
              if plan['cle'] in sorties]
    if not series:
        return sortie_reference
    colonne = colonne_energie(series[0])
    if colonne is None:
        return sortie_reference
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


def _version_moteur():
    """La version du moteur qui a produit ce résultat — une seule source."""
    from core.electrique.version import VERSION_MOTEUR

    return VERSION_MOTEUR
