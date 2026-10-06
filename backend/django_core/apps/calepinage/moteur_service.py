"""Le moteur de calepinage, vu du module — copie rapatriée du service AO.

SOLMVP15 — ``apps.calepinage`` calculait par les sélecteurs du module AO
(``calepinage_json``, ``cout_calepinage``, ``erreurs_moteur_calepinage``), qui
déléguait à ``apps/ao/calepinage_service.py``. AO sort du produit : la moitié
PURE de ce service — celle qui ne lit ni n'écrit aucune ligne, le calcul
STATELESS d'AOF60 — vit désormais ici, à la ligne près. Rien n'a changé pour
l'atelier : même document d'entrée, même JSON publié, mêmes refus français,
même bascule synchrone/asynchrone, même cache (même clé, même empreinte).

CE QUI EST RESTÉ CHEZ AO : tout ce qui PERSISTE une ``ao.VarianteCalepinage``
(``calculer_variante``, ``retenir_variante``, ``comparer_variantes``,
``calculer_sensibilites``, ``generer_variantes_orientation``,
``calculer_marches``). C'est le studio 2D OPPOSABLE d'AO — la règle D9 du
module (``docs/calepinage-module.md``) veut précisément que les deux systèmes
de variantes ne se mélangent jamais. L'atelier 3D n'en appelait aucun.

Les trois fonctions PUBLIQUES du bas (``erreurs_moteur_calepinage``,
``cout_calepinage``, ``calepinage_json``) portent exactement la signature et le
contrat que les sélecteurs AO publiaient : les appelants du module n'ont
changé que d'adresse d'import.
"""
from __future__ import annotations

import hashlib
import json
import logging

from core.calepinage.exceptions import (
    CalepinageIncoherent, EntreeInvalide as EntreeMoteurInvalide,
)
from core.calepinage.garde_fous import valider
from core.calepinage.obstacles import appliquer_regles, engageable
from core.calepinage.optimum import calculer as calculer_optimum
from core.calepinage.perf import BudgetCalcul, estimer_cout, optimiser_economique
from core.calepinage.poseur import poser_plan
from core.calepinage.robustesse import marges_du_plan
from core.calepinage.serialisation import (
    EntreeCalepinage, SchemaIncompatible, hash_entree,
)
from core.calepinage.types import ModePose
from core.calepinage.version import VERSION_MOTEUR

from . import moteur_io
from .moteur_io import EntreeInvalide

logger = logging.getLogger(__name__)


__all__ = [
    'MoteurCalepinage', 'EntreeInvalide', 'CalepinageIncoherent',
    'calepiner', 'cout_estime', 'empreinte_document',
    'cle_cache', 'resultat_en_cache', 'mettre_en_cache',
    'multiplicateur_suggestions',
    'PLAFOND_SUGGESTIONS',
    'erreurs_moteur_calepinage', 'cout_calepinage', 'calepinage_json',
]

#: Suggestions PUBLIÉES par calcul (PV50). Le moteur en cape déjà 12
#: (``PLAFOND_RECOMMANDATIONS``) ; en afficher douze reviendrait à n'en faire
#: lire aucune. Cinq est ce qu'un panneau montre sans replier.
PLAFOND_SUGGESTIONS = 5


def multiplicateur_suggestions(plafond=None):
    """PV50 — combien de DP COMPLETS un jeu de suggestions rejoue, au pire.

    Une recommandation ne vaut que parce que son gain est REJOUÉ sur l'entrée
    patchée : le moteur cape ce travail (``PLAFOND_RECOMMANDATIONS``), et c'est
    ce plafond-là qu'on lit — pas un chiffre recopié. ``+ 1`` pour le compte de
    référence, ``+ 1`` pour la recherche d'allée gratuite.
    """
    from core.calepinage.recommandations import PLAFOND_RECOMMANDATIONS

    plafond = (PLAFOND_RECOMMANDATIONS if plafond is None else int(plafond))
    return 1 + max(0, plafond) + 1


#: Durée de vie d'un résultat en cache (12 h). Un résultat n'est jamais
#: « faux » en cache — la clé porte l'empreinte de l'entrée ET la version du
#: moteur — mais on ne garde pas indéfiniment des toitures qu'on ne rouvrira
#: plus.
DUREE_CACHE_S = 12 * 3600


def cle_cache(hash_entree):
    """Nom de cache d'un résultat de calepinage (AOF61).

    **La version du moteur est DANS la clé.** L'invalidation au bump de
    version est donc structurelle : les entrées de l'ancien moteur deviennent
    inatteignables du jour au lendemain, sans purge à ne pas oublier — c'est la
    seule forme d'invalidation qui ne se dégrade pas avec le temps.
    """
    return 'ao:calepinage:%s:%s' % (hash_entree, VERSION_MOTEUR)


def resultat_en_cache(company_id, hash_entree):
    """Résultat déjà calculé pour cette société, ou ``None`` (best-effort)."""
    from core import cache as cache_tenant

    return cache_tenant.get(company_id, cle_cache(hash_entree))


def mettre_en_cache(company_id, resultat, timeout=DUREE_CACHE_S):
    """Mémorise un résultat, SCOPÉ SOCIÉTÉ (``core.cache.tenant_key``)."""
    from core import cache as cache_tenant

    cache_tenant.set(company_id, cle_cache(resultat['hash_entree']), resultat,
                     timeout=timeout)
    return resultat


class VariantePerimee(Exception):
    """AOF62 — on ne retient jamais une variante dont l'entrée a bougé."""


class SansVarianteRetenue(Exception):
    """PV67 — comparer des alternatives suppose une variante DE RÉFÉRENCE."""


class MoteurCalepinage:
    """Adaptateur MINCE devant le paquet pur — le seul « moteur » injectable.

    Il ne fait qu'un choix, et ce choix est celui des ``Parametres`` :
    ``RANGEES_EXPLICITES_DP`` passe par ``perf.optimiser_economique`` (le même
    optimum que le balayage au centimètre, sur un jeu de positions
    strictement équivalent et bien plus petit) ; tout autre mode de pose passe
    par ``optimum.calculer``, qui sait déléguer au balayage de phase.

    ``appels`` compte les délégations RÉELLES au moteur : c'est ce compteur que
    le test du cache d'AOF61 observe pour prouver qu'un second appel identique
    ne recalcule rien.
    """

    version = VERSION_MOTEUR

    def __init__(self):
        self.appels = 0

    def calculer(self, surface, parametres, obstacles=(), zones=(),
                 politique=None):
        self.appels += 1
        if parametres.mode_pose is ModePose.RANGEES_EXPLICITES_DP:
            return optimiser_economique(surface, parametres, obstacles, zones,
                                        politique)
        return calculer_optimum(surface, parametres, obstacles, zones,
                                politique)


def _moteur(moteur):
    return moteur if moteur is not None else MoteurCalepinage()


def _entree(document):
    """Désérialise un document du contrat — refus NOMMÉ, jamais un ``KeyError``."""
    try:
        return EntreeCalepinage.depuis_dict(document)
    except SchemaIncompatible as erreur:
        raise EntreeInvalide(str(erreur)) from erreur
    except (KeyError, TypeError, ValueError) as erreur:
        raise EntreeInvalide(
            "Document de calepinage invalide : %s" % erreur) from erreur


def empreinte_document(document):
    """Empreinte canonique d'un document d'entrée (AOF57), au millimètre.

    **PV44 — la section ÉLECTRIQUE entre dans l'empreinte, mais seulement
    quand elle existe.** ``hash_entree`` ne hache que le contrat de calepinage
    (il ne connaît pas ``electrique``) : sans ce repli, changer la longueur de
    chaîne laisserait l'empreinte identique et un résultat en cache décrirait
    la saisie d'AVANT. La section absente ne change RIEN : toutes les
    empreintes déjà publiées restent identiques au bit près.
    """
    empreinte = hash_entree(_entree(document))
    electrique = (document or {}).get('electrique') or {}
    if not electrique:
        return empreinte
    canonique = json.dumps(electrique, sort_keys=True, separators=(',', ':'),
                           ensure_ascii=True)
    return hashlib.sha256(
        ('%s|%s' % (empreinte, canonique)).encode('ascii')).hexdigest()


def cout_estime(document, *, budget=None, suggestions=False):
    """Chiffre le travail AVANT de le lancer, sur la surface la plus lourde.

    C'est ce chiffre qui pilote la bascule synchrone/asynchrone d'AOF61 : au
    delà du budget, l'API refuse de faire attendre l'utilisateur et renvoie la
    consigne d'appel asynchrone.

    ``suggestions=True`` (PV50) chiffre le travail TOUT COMPRIS : la charge
    utile rejoue une dizaine de DP complets, et la publier sans la compter
    reviendrait à promettre une réponse synchrone qu'on ne peut pas tenir. Le
    multiplicateur vient du moteur, pas d'un chiffre recopié. ACAL292 — les
    cinq tiroirs d'atelier AO ne sont plus calculés : ils ne coûtent plus rien.
    """
    entree = _entree(document)
    obstacles = appliquer_regles(entree.obstacles)
    par_surface = moteur_io.affectations_du_document(
        document, entree.surfaces, obstacles)
    budget = budget or BudgetCalcul()
    supplements = 0
    if suggestions:
        supplements += multiplicateur_suggestions() - 1
    variantes = 1 + supplements
    cumul = None
    for surface in entree.surfaces:
        cout = estimer_cout(surface, entree.parametres,
                            par_surface.get(surface.repere, ()),
                            entree.zones, variantes=variantes, budget=budget)
        if cumul is None:
            cumul = cout
            continue
        # cumul HONNÊTE : on additionne les appels, pas les motifs.
        cumul = type(cout)(
            positions=cumul.positions + cout.positions,
            kits=cout.kits, variantes=cout.variantes,
            appels=cumul.appels + cout.appels,
            millisecondes=cumul.millisecondes + cout.millisecondes,
            synchrone=(cumul.millisecondes + cout.millisecondes
                       <= budget.seuil_synchrone_ms),
            motif=cout.motif)
    if cumul is None:
        raise EntreeInvalide("Le document ne déclare aucune surface.")
    return cumul


# ───────────────────────────────────────────────── AOF60 — calcul STATELESS
def calepiner(document, *, company, user=None, moteur=None, budget=None,
              suggestions=True):
    """Calcule un calepinage COMPLET et renvoie du JSON. N'écrit RIEN.

    ``company`` est OBLIGATOIRE : le service refuse de tourner hors société,
    de sorte qu'aucun chemin d'appel ne puisse contourner le cloisonnement
    multi-tenant en oubliant un argument.

    **PV49/PV50 — la sortie porte aussi ``marges`` et ``suggestions``.**
    ``marges`` publie ce que la passe de robustesse a MESURÉ (``None`` quand
    elle n'a rien mesuré, jamais ``0``) ; ``suggestions`` les propositions
    APPLICABLES à gain rejoué, CALCULÉES par le moteur. ACAL292 — les cinq
    tiroirs d'atelier AO (dont une conception électrique de référence,
    troisième modèle de chaînage du produit) ne sont plus produits : leur
    coût dans le pré-vol privait l'écran des suggestions qu'il affiche.

    Les suggestions sont calculées par surface puis FUSIONNÉES : un patch de
    paramètres n'est publié que s'il a été mesuré à l'identique sur TOUTES
    les surfaces. Elles valent une liste VIDE (jamais une clé absente) quand
    le coût estimé dépasse le budget synchrone.

    Raises:
        EntreeInvalide: document non conforme au contrat (motif français).
        CalepinageIncoherent: un contrôle d'AOF51 a échoué — le résultat ne
            sort JAMAIS de cette fonction.
    """
    if company is None:
        raise EntreeInvalide(
            'Un calepinage se calcule toujours dans une société : '
            '`company` est obligatoire.')
    entree = _entree(document)
    obstacles = appliquer_regles(entree.obstacles)
    par_surface = moteur_io.affectations_du_document(
        document, entree.surfaces, obstacles)
    machine = _moteur(moteur)
    budget = budget or BudgetCalcul()

    plans = []
    total_modules = 0
    total_kwc = 0.0
    preuves = []
    marges_globales = None
    controles = None

    for surface in entree.surfaces:
        lot = par_surface.get(surface.repere, ())
        try:
            resultat = machine.calculer(surface, entree.parametres, lot,
                                        entree.zones)
        except EntreeMoteurInvalide as erreur:
            # PV30 — le NOYAU refuse déjà en français (rangées imposées vides,
            # phase forcée hors du jeu possible), mais avec SON exception, que
            # l'API ne sait pas retraduire : sans cette traduction, une faute
            # de saisie sortirait en 500 au lieu du 400 nommé.
            raise EntreeInvalide(str(erreur)) from erreur
        rangees = tuple((y0, entree.parametres.kit(code))
                        for y0, code in resultat.rangees)
        tables = poser_plan(surface, rangees, lot, entree.zones)

        # AOF51 — la porte, PAS un rapport : ``strict=True`` lève avant retour.
        rapport = valider(surface, entree.parametres, rangees, lot,
                          entree.zones, tables=tables, preuve=resultat.preuve,
                          strict=True)
        controles = (tuple(rapport.controles_passes) if controles is None
                     else tuple(c for c in controles
                                if c in set(rapport.controles_passes)))

        marges_globales = _cumuler_marges(
            marges_globales,
            marges_du_plan(surface, rangees, lot, entree.zones))

        plans.append(moteur_io.plan_vers_json(surface.repere, resultat,
                                              tables))
        total_modules += resultat.plan.modules
        for rangee in resultat.plan.rangees:
            kit = entree.parametres.kit(rangee.kit_code)
            total_kwc += rangee.modules * kit.puissance_module_wc / 1000.0
        preuves.append(resultat.preuve)

    ok_engagement, motifs = engageable(obstacles)
    empreinte = empreinte_document(document)
    sortie = moteur_io.resultat_vers_json(
        repere=entree.repere, hash_entree=empreinte, modules=total_modules,
        kwc=total_kwc, plans=plans, engageable=ok_engagement,
        motifs_non_engageable=motifs)
    sortie['company_id'] = getattr(company, 'id', company)
    sortie['preuve'] = moteur_io.preuve_vers_json(
        _preuve_cumulee(preuves), marges_globales,
        controles=controles or (),
        pas_recherche_m=entree.parametres.pas_recherche_m)
    sortie['engagement_modules'] = entree.parametres.engagement_modules
    sortie['marges'] = moteur_io.marges_vers_json(marges_globales)
    # Le pré-vol ne chiffre plus que les suggestions (ACAL292).
    abordable = suggestions and _cout_charge_utile(
        entree, par_surface, budget=budget, suggestions=suggestions)
    # Le contrat de l'endpoint agrégé enveloppe la liste dans
    # ``{"suggestions": […]}`` ; ICI la clé du résultat EST la liste, comme
    # ``plans`` et ``rangees`` — chaque ÉLÉMENT, lui, a exactement la forme du
    # contrat.
    sortie['suggestions'] = _suggestions_publiables(
        entree, par_surface, demandes=bool(suggestions and abordable))
    return sortie


def _suggestions_publiables(entree, par_surface, *, demandes=True):
    """PV50 — les suggestions APPLICABLES, fusionnées puis CAPÉES.

    Le moteur propose PAR SURFACE ; l'écran, lui, applique au SITE. La fusion
    est donc conservatrice : un patch de paramètres n'est publié que s'il a été
    mesuré à l'IDENTIQUE sur toutes les surfaces (son gain devient leur somme),
    car un patch mesuré sur un seul segment aurait, appliqué partout, un effet
    que personne n'a chiffré. Une décision d'obstacle ne concerne qu'un repère
    nommé : elle passe telle quelle.
    """
    if not demandes or not entree.surfaces:
        return []

    from core.calepinage.recommandations import EntreeMoteur, proposer

    par_code = {}
    for surface in entree.surfaces:
        lot = tuple(par_surface.get(surface.repere, ()))
        moteur_entree = EntreeMoteur(surface=surface,
                                     parametres=entree.parametres,
                                     obstacles=lot,
                                     zones=tuple(entree.zones))
        try:
            propositions = proposer(moteur_entree, catalogue_kits=entree.kits)
        except AssertionError:
            # La contre-épreuve de kit du moteur a échoué : c'est un vrai
            # défaut, il est JOURNALISÉ — mais il ne doit pas emporter le
            # calepinage lui-même, qui est le résultat qu'on est venu chercher.
            logger.exception(
                'calepinage : contre-épreuve de recommandation en échec sur '
                'la surface %s', surface.repere)
            continue
        for proposition in propositions:
            suggestion = moteur_io.suggestion_vers_json(proposition)
            if suggestion is None:
                continue
            par_code.setdefault(suggestion['code'], []).append(suggestion)

    nb_surfaces = len(entree.surfaces)
    retenues = []
    for suggestions in par_code.values():
        fusionnee = _fusionner_suggestions(suggestions, nb_surfaces)
        if fusionnee is not None:
            retenues.append(fusionnee)
    retenues.sort(key=lambda s: (-s['gain_modules'], s['code']))
    return retenues[:PLAFOND_SUGGESTIONS]


def _fusionner_suggestions(suggestions, nb_surfaces):
    """Les occurrences d'UN code sur N surfaces -> une suggestion, ou ``None``."""
    premiere = suggestions[0]
    if premiere['action']['type'] == 'obstacle':
        # Un obstacle appartient à une seule surface : aucune fusion à faire.
        return premiere if len(suggestions) == 1 else None
    if len(suggestions) != nb_surfaces:
        return None  # non mesuré partout : l'appliquer partout serait un pari
    patchs = [s['action']['patch'] for s in suggestions]
    if any(patch != patchs[0] for patch in patchs[1:]):
        return None  # deux valeurs différentes : aucune n'a été mesurée seule
    fusionnee = dict(premiere)
    fusionnee['gain_modules'] = sum(s['gain_modules'] for s in suggestions)
    fusionnee['gain_kwc'] = round(sum(s['gain_kwc'] for s in suggestions), 3)
    return fusionnee


def _cout_charge_utile(entree, par_surface, *, budget, suggestions=False):
    """Pré-vol d'une charge utile d'atelier — coût CUMULÉ sur les surfaces.

    Le cumul est celui de ``cout_estime`` : on additionne les millisecondes de
    chaque surface, parce que le serveur les paiera toutes dans la même
    requête. Ne regarder que la plus lourde ferait passer trois segments pour
    un seul.
    """
    supplements = 0
    if suggestions:
        supplements += multiplicateur_suggestions() - 1
    millisecondes = 0.0
    for surface in entree.surfaces:
        cout = estimer_cout(surface, entree.parametres,
                            tuple(par_surface.get(surface.repere, ())),
                            entree.zones, variantes=1 + supplements,
                            budget=budget)
        millisecondes += cout.millisecondes
    return millisecondes <= budget.seuil_synchrone_ms


def _cumuler_marges(cumul, marges):
    """Retient la marge la PLUS SERRÉE de chaque axe, indépendamment.

    Un site de trois segments a trois jeux de marges : publier celles d'un seul
    segment cacherait le segment au ras. Les deux axes sont cumulés
    SÉPARÉMENT — un segment sans obstacle (aucune marge de bande MESURÉE) ne
    doit jamais écraser la marge de bande réelle d'un autre segment par un
    zéro qui ne veut rien dire.
    """
    from core.calepinage.types import Marges

    if cumul is None:
        return marges
    troncon, rangee = cumul.troncon_min_m, cumul.rangee_critique
    if marges.rangee_critique and (
            not rangee or marges.troncon_min_m < troncon):
        troncon, rangee = marges.troncon_min_m, marges.rangee_critique
    bande, obstacle = cumul.bande_min_m, cumul.obstacle_critique
    if marges.obstacle_critique and (
            not obstacle or marges.bande_min_m < bande):
        bande, obstacle = marges.bande_min_m, marges.obstacle_critique
    return Marges(troncon_min_m=troncon, bande_min_m=bande,
                  rangee_critique=rangee, obstacle_critique=obstacle)


def _preuve_cumulee(preuves):
    """Agrège les preuves de N surfaces en UNE preuve du site.

    La méthode retenue est la MOINS forte des méthodes rencontrées : un site
    dont un seul segment a été calculé par heuristique n'est pas « prouvé
    optimal ». C'est le verrou de vocabulaire d'AOF44, appliqué au cumul.
    """
    from core.calepinage.types import Preuve

    if not preuves:
        raise EntreeInvalide('Aucune surface calculée : preuve impossible.')
    if len(preuves) == 1:
        return preuves[0]
    inexactes = [p for p in preuves if not p.methode.exacte]
    methode = inexactes[0].methode if inexactes else preuves[0].methode
    optimaux = [p.compte_optimal for p in preuves]
    bornes = [p.borne_superieure for p in preuves]
    return Preuve(
        methode=methode,
        pas_recherche_m=max(p.pas_recherche_m for p in preuves),
        compte_retenu=sum(p.compte_retenu for p in preuves),
        compte_optimal=(None if any(v is None for v in optimaux)
                        else sum(optimaux)),
        borne_superieure=(None if any(v is None for v in bornes)
                          else sum(bornes)),
        nb_plans_optimaux=None)


# ──────────────────────── SOLMVP15 — la PORTE publique du moteur, pour le module
#
# Ces trois fonctions sont la copie EXACTE (docstring comprise) de ce que
# les sélecteurs du module AO publiaient pour ``apps.calepinage`` : un appelant
# n'a jamais eu accès au service, il passait par ce point d'entrée mince, et il y
# passe toujours. LECTURE PURE : aucune ligne n'est lue ni écrite.


def erreurs_moteur_calepinage():
    """``(EntreeInvalide, CalepinageIncoherent)`` — les deux refus du moteur.

    Un appelant doit pouvoir les ATTRAPER pour répondre 400 avec le motif
    FRANÇAIS du serveur, sans connaître le détail du service.
    """
    return EntreeInvalide, CalepinageIncoherent


def cout_calepinage(document, *, budget=None, suggestions=False):
    """Le coût ESTIMÉ d'un calcul — chiffré AVANT de le lancer.

    C'est ce chiffre qui pilote la bascule synchrone/asynchrone : au-delà du
    budget, l'appelant rend 202 et la consigne de suivi, plutôt que de faire
    attendre l'utilisateur devant un écran gelé.
    """
    return cout_estime(document, budget=budget, suggestions=suggestions)


def calepinage_json(document, *, company, user=None, suggestions=True,
                    budget=None):
    """Calcule un calepinage et rend le JSON PUBLIÉ du moteur.

    ``company`` est OBLIGATOIRE (le service refuse de tourner hors société) et
    sert à estampiller la sortie : aucune ligne n'est lue ni écrite. La forme
    est celle que le contrat fige — une seule sérialisation pour tous les
    consommateurs.
    """
    return calepiner(document, company=company, user=user,
                     suggestions=suggestions, budget=budget)
