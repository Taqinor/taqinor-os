"""AOF60/AOF62 — service d'orchestration du calepinage : la COUTURE, STATELESS
côté moteur.

Ce module est le seul point par lequel ``apps.ao`` appelle
``core.calepinage``. Il ne contient **aucune géométrie** : il désérialise,
délègue, VALIDE, et — pour le chemin persistant — écrit le résultat, la preuve
et les marges en appliquant les gardes de publication d'AOF28.

Deux fonctions, deux responsabilités qui ne doivent jamais fusionner
--------------------------------------------------------------------
* ``calepiner(entree_json, *, company, user)`` — **STATELESS**. Elle
  désérialise un document du contrat AOF57, calcule, valide, et renvoie du
  JSON. Elle n'écrit RIEN en base, ne change AUCUN statut, ne produit AUCUN
  document. C'est ce qui rend l'aperçu d'un tiroir de l'atelier gratuit : on
  peut la rejouer mille fois sans laisser de trace.
* ``calculer_variante(toiture, params, *, user)`` — compose l'entrée depuis
  les modèles (enveloppe, obstacles actifs, kits, preset), appelle la première,
  puis PERSISTE résultat + preuve + marges sur une ``VarianteCalepinage``.

**Le moteur est injectable.** ``moteur=`` accepte tout objet exposant
``calculer(surface, parametres, obstacles, zones)`` : les tests peuvent
compter les appels (preuve du cache d'AOF61) ou simuler un moteur lent sans
toucher au paquet pur.

Frontières respectées
---------------------
* aucun import de ``apps.crm`` / ``apps.ventes`` / ``apps.stock`` — le prix
  d'un kit vient de la string-FK ``stock.Produit`` portée par le modèle, jamais
  d'un import cross-app ici ;
* ``valider()`` (AOF51) est appelée sur CHAQUE surface AVANT tout retour : un
  résultat incohérent lève ``CalepinageIncoherent``, il ne sort jamais de ce
  module ;
* aucun coût, aucun ``prix_achat``, aucune marge ne transite ici : le service
  ne produit que de la géométrie et des comptes.
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

from . import calepinage_io
from .calepinage_io import EntreeInvalide

logger = logging.getLogger(__name__)

__all__ = [
    'MoteurCalepinage', 'EntreeInvalide', 'CalepinageIncoherent',
    'calepiner', 'calculer_variante', 'cout_estime', 'empreinte_document',
    'retenir_variante', 'comparer_variantes', 'calculer_sensibilites',
    'calculer_marches', 'VariantePerimee', 'cle_cache', 'resultat_en_cache',
    'mettre_en_cache', 'multiplicateur_tiroirs', 'multiplicateur_suggestions',
    'PLAFOND_SUGGESTIONS', 'SansVarianteRetenue',
    'generer_variantes_orientation', 'VARIANTES_ORIENTATION',
]

#: Suggestions PUBLIÉES par calcul (PV50). Le moteur en cape déjà 12
#: (``PLAFOND_RECOMMANDATIONS``) ; en afficher douze reviendrait à n'en faire
#: lire aucune. Cinq est ce qu'un panneau montre sans replier.
PLAFOND_SUGGESTIONS = 5


def multiplicateur_tiroirs(budget_appels=None):
    """PV49 — combien de DP COMPLETS un jeu de tiroirs rejoue, au pire.

    Un tiroir n'affiche AUCUN chiffre saisi : chaque contre-épreuve de kit,
    chaque impact de rive, chaque point du graphe d'allée est un appel moteur
    de plus. Le multiplicateur est donc lu SUR LE MOTEUR (``tiroirs`` publie
    son ``BUDGET_APPELS_DEFAUT`` et rapporte ce qu'il consomme), jamais
    recopié ici : le jour où le budget du moteur bouge, l'estimation suit.

    ``1`` pour le calcul du plan lui-même, ``+ budget`` pour les impacts,
    ``+ 1`` pour la recherche d'allée gratuite — que ``donnees_tiroirs``
    compte à part (``recherches_allee``) parce que sa dichotomie a sa propre
    borne : l'omettre cacherait un coût réel.
    """
    from core.calepinage.tiroirs import BUDGET_APPELS_DEFAUT

    budget = BUDGET_APPELS_DEFAUT if budget_appels is None else int(
        budget_appels)
    return 1 + max(0, budget) + 1


#: PV44 — ce que la conception ÉLECTRIQUE coûte, exprimé en DP ÉQUIVALENTS.
#:
#: Elle n'exécute AUCUN DP : ``core.electrique`` ne balaie aucune position, il
#: enchaîne quelques passes arithmétiques sur la liste des chaînes (plus UNE
#: contre-épreuve de répartition quand le dossier est bloqué). Son coût réel est
#: donc très inférieur à un DP de calepinage. On le compte quand même comme UN
#: DP entier : le budget synchrone est une PROMESSE de temps de réponse, et sur
#: une promesse on surestime — jamais l'inverse.
COUT_ELECTRIQUE_EN_DP = 1


def multiplicateur_electrique():
    """Combien de DP équivalents le tiroir électrique ajoute — PV44."""
    return COUT_ELECTRIQUE_EN_DP


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
    chaîne laisserait l'empreinte identique, le cache de résultat rendrait le
    tiroir électrique d'AVANT, et l'écran afficherait la répartition qu'on
    vient justement de corriger. La section absente ne change RIEN : toutes les
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


def cout_estime(document, *, budget=None, tiroirs=False, suggestions=False):
    """Chiffre le travail AVANT de le lancer, sur la surface la plus lourde.

    C'est ce chiffre qui pilote la bascule synchrone/asynchrone d'AOF61 : au
    delà du budget, l'API refuse de faire attendre l'utilisateur et renvoie la
    consigne d'appel asynchrone.

    ``tiroirs=True`` (PV49) et ``suggestions=True`` (PV50) chiffrent le travail
    TOUT COMPRIS : ces deux charges utiles rejouent chacune une dizaine de DP
    complets, et les publier sans les compter reviendrait à promettre une
    réponse synchrone qu'on ne peut pas tenir. Les multiplicateurs viennent du
    moteur, pas d'un chiffre recopié ; le plan de base n'est compté qu'UNE
    fois même quand les deux sont demandées.
    """
    entree = _entree(document)
    obstacles = appliquer_regles(entree.obstacles)
    par_surface = calepinage_io.affectations_du_document(
        document, entree.surfaces, obstacles)
    budget = budget or BudgetCalcul()
    supplements = 0
    if tiroirs:
        # PV44 : le tiroir ÉLECTRIQUE voyage avec les tiroirs — il est calculé
        # sous la même garde, donc il est chiffré sous la même garde.
        supplements += multiplicateur_tiroirs() - 1 + multiplicateur_electrique()
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
              tiroirs=True, suggestions=True):
    """Calcule un calepinage COMPLET et renvoie du JSON. N'écrit RIEN.

    ``company`` est OBLIGATOIRE : le service refuse de tourner hors société,
    de sorte qu'aucun chemin d'appel ne puisse contourner le cloisonnement
    multi-tenant en oubliant un argument.

    **PV49/PV50 — la sortie porte aussi ``marges``, ``tiroirs`` et
    ``suggestions``.** ``marges`` publie ce que la passe de robustesse a MESURÉ
    (``None`` quand elle n'a rien mesuré, jamais ``0``). ``tiroirs`` porte les
    5 charges utiles de l'atelier et ``suggestions`` les propositions
    APPLICABLES à gain rejoué — toutes CALCULÉES par le moteur, jamais rédigées
    ici. Les trois sont toujours présentes comme CLÉS : ``tiroirs`` vaut un jeu
    dégradé (``donnees: null``) et ``suggestions`` une liste vide quand ils ne
    sont pas produits, jamais une clé absente.

    Les deux charges utiles sont DÉGRADÉES, pas silencieusement payées, dans
    deux cas :

    * document à PLUSIEURS surfaces — le moteur n'a aucun modèle de tiroir par
      segment, et en meubler un depuis une seule surface publierait les
      chiffres d'un segment sous le nom du site. Les SUGGESTIONS, elles, sont
      bien calculées par surface puis FUSIONNÉES : un patch de paramètres n'est
      publié que s'il a été mesuré à l'identique sur TOUTES les surfaces (son
      gain est alors leur somme), sinon l'appliquer aurait un effet non mesuré
      ailleurs ;
    * coût estimé HORS budget synchrone — chaque impact chiffré rejoue un DP
      complet ; les produire quand même tiendrait la promesse d'affichage en
      brisant celle du temps de réponse.

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
    par_surface = calepinage_io.affectations_du_document(
        document, entree.surfaces, obstacles)
    machine = _moteur(moteur)
    budget = budget or BudgetCalcul()

    plans = []
    total_modules = 0
    total_kwc = 0.0
    preuves = []
    marges_globales = None
    controles = None
    dernier_resultat = None
    pans = []

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

        plans.append(calepinage_io.plan_vers_json(surface.repere, resultat,
                                                  tables))
        total_modules += resultat.plan.modules
        for rangee in resultat.plan.rangees:
            kit = entree.parametres.kit(rangee.kit_code)
            total_kwc += rangee.modules * kit.puissance_module_wc / 1000.0
        preuves.append(resultat.preuve)
        dernier_resultat = resultat
        # PV44 — un PAN par surface pour le moteur électrique : deux
        # orientations ne se mélangent jamais sur une entrée MPPT.
        pans.append({
            'label': surface.repere,
            'nb_modules': resultat.plan.modules,
            'azimut_deg': getattr(surface, 'azimut_deg', 180.0),
            'inclinaison_deg': max(
                [entree.parametres.kit(r.kit_code).inclinaison_deg
                 for r in resultat.plan.rangees] or [0.0]),
        })

    ok_engagement, motifs = engageable(obstacles)
    empreinte = empreinte_document(document)
    sortie = calepinage_io.resultat_vers_json(
        repere=entree.repere, hash_entree=empreinte, modules=total_modules,
        kwc=total_kwc, plans=plans, engageable=ok_engagement,
        motifs_non_engageable=motifs)
    sortie['company_id'] = getattr(company, 'id', company)
    sortie['preuve'] = calepinage_io.preuve_vers_json(
        _preuve_cumulee(preuves), marges_globales,
        controles=controles or (),
        pas_recherche_m=entree.parametres.pas_recherche_m)
    sortie['engagement_modules'] = entree.parametres.engagement_modules
    sortie['marges'] = calepinage_io.marges_vers_json(marges_globales)
    # UN SEUL pré-vol pour les deux charges utiles : chacune chiffrée de son
    # côté, elles pourraient toutes deux « tenir » et ne pas tenir ENSEMBLE —
    # et la promesse rompue serait celle de la réponse, pas celle d'un tiroir.
    abordable = (tiroirs or suggestions) and _cout_charge_utile(
        entree, par_surface, budget=budget, tiroirs=tiroirs,
        suggestions=suggestions)
    sortie['tiroirs'] = _tiroirs_publiables(
        entree, par_surface, dernier_resultat,
        demandes=bool(tiroirs and abordable))
    # PV44 — le tiroir ÉLECTRIQUE se calcule sur le SITE, pas sur une surface :
    # il est donc publié même en multi-surfaces (un pan par segment), là où les
    # quatre autres restent dégradés faute de modèle de tiroir par segment.
    sortie['tiroirs']['electrique'] = _tiroir_electrique(
        document, pans, total_modules, total_kwc,
        demandes=bool(tiroirs and abordable))
    # Le contrat de l'endpoint agrégé enveloppe la liste dans
    # ``{"suggestions": […]}`` ; ICI la clé du résultat EST la liste, comme
    # ``plans`` et ``rangees`` — chaque ÉLÉMENT, lui, a exactement la forme du
    # contrat.
    sortie['suggestions'] = _suggestions_publiables(
        entree, par_surface, demandes=bool(suggestions and abordable))
    return sortie


def _tiroirs_publiables(entree, par_surface, resultat, *, demandes=True):
    """Les 5 tiroirs — ou leur forme DÉGRADÉE, jamais une clé absente.

    Le garde de coût est un PRÉ-VOL fait par l'appelant (``calepiner``), pas un
    regret : on chiffre le travail AVANT de le lancer et on renonce quand il ne
    tient pas dans le budget synchrone. La promesse « cet appel répond en
    synchrone » ne peut donc pas être rompue en douce par un tiroir.
    """
    if not demandes or resultat is None or len(entree.surfaces) != 1:
        return calepinage_io.tiroirs_vides()
    surface = entree.surfaces[0]
    lot = par_surface.get(surface.repere, ())

    from core.calepinage.recommandations import EntreeMoteur
    from core.calepinage.tiroirs import donnees_tiroirs

    donnees = donnees_tiroirs(
        EntreeMoteur(surface=surface, parametres=entree.parametres,
                     obstacles=tuple(lot), zones=tuple(entree.zones)),
        resultat, catalogue=entree.kits)
    return calepinage_io.tiroirs_vers_json(donnees, entree.parametres)


def _tiroir_electrique(document, pans, total_modules, total_kwc, *,
                       demandes=True):
    """PV44 — le tiroir « Contraintes électriques », CALCULÉ par le moteur.

    Il était livré dégradé (``donnees: null``) parce que le calepinage n'a
    aucun modèle électrique. ``core.electrique`` en a un depuis PV33-39, et il
    publie déjà la projection exacte que l'écran lit : il ne reste qu'à lui
    donner l'entrée.

    La puissance unitaire du module est DÉDUITE du plan lui-même
    (``kWc × 1000 ÷ modules``) et non recopiée d'un kit : sur une toiture qui
    mélange deux kits de puissances différentes, c'est le seul chiffre qui
    redonne EXACTEMENT la puissance crête du plan. Sur un kit unique, il vaut
    sa puissance unitaire au flottant près.

    Le garde de coût est celui des autres tiroirs (pré-vol de ``calepiner``) :
    hors budget, la forme DÉGRADÉE d'origine est rendue telle quelle.
    """
    if not demandes:
        return calepinage_io.tiroirs_vides()['electrique']
    electrique = (document or {}).get('electrique') or {}
    taille = electrique.get('taille_chaine')
    puissance_module_wc = (total_kwc * 1000.0 / total_modules
                           if total_modules else 0.0)
    entree_elec = calepinage_io.entree_electrique(
        pans, puissance_module_wc, taille_chaine=taille)

    from core.electrique import concevoir

    resultat = concevoir(entree_elec)
    return calepinage_io.tiroir_electrique_vers_json(
        (resultat.tiroirs or {}).get('electrique'),
        entree_elec.longueur_chaine_forcee)


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
            suggestion = calepinage_io.suggestion_vers_json(proposition)
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


def _cout_charge_utile(entree, par_surface, *, budget, tiroirs=False,
                       suggestions=False):
    """Pré-vol d'une charge utile d'atelier — coût CUMULÉ sur les surfaces.

    Le cumul est celui de ``cout_estime`` : on additionne les millisecondes de
    chaque surface, parce que le serveur les paiera toutes dans la même
    requête. Ne regarder que la plus lourde ferait passer trois segments pour
    un seul.
    """
    supplements = 0
    if tiroirs:
        # PV44 : le tiroir ÉLECTRIQUE voyage avec les tiroirs — il est calculé
        # sous la même garde, donc il est chiffré sous la même garde.
        supplements += multiplicateur_tiroirs() - 1 + multiplicateur_electrique()
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


# ─────────────────────────────────────── AOF60 — calcul PERSISTÉ (variante)
def calculer_variante(toiture, params=None, *, user=None, moteur=None,
                      nom='', role=None, parent=None, appel_offre=None,
                      variante=None):
    """Compose l'entrée depuis les modèles, calcule, et PERSISTE la variante.

    Les gardes de publication d'AOF28 sont appliquées ICI : la variante ne
    devient ``publiable`` que si sa PREUVE le démontre (total retenu = total
    optimal, marges au-dessus des seuils, aucun obstacle non mesuré actif).
    Sinon elle reste ``calculee`` et porte ses motifs dans ``justification`` —
    jamais un statut optimiste qu'un écran présenterait comme engageant.
    """
    from .models import VarianteCalepinage

    document = calepinage_io.document_entree(toiture, params=params)
    # ``tiroirs=False`` (PV49) : ce chemin PERSISTE un résultat, il n'alimente
    # aucun atelier — et la variante ne les garde pas. Les produire ferait
    # rejouer une douzaine de DP complets pour les jeter aussitôt.
    sortie = calepiner(document, company=toiture.company, user=user,
                       moteur=moteur, tiroirs=False, suggestions=False)

    if variante is None:
        variante = VarianteCalepinage(
            company=toiture.company, toiture=toiture,
            appel_offre=appel_offre or toiture.batiment.appel_offre,
            role=role or VarianteCalepinage.Role.RETENUE, parent=parent)
    variante.nom = nom or variante.nom or (
        'Calepinage %s' % (toiture.code_document or toiture.pk))
    variante.params = dict(params if params is not None
                           else (toiture.parametres_calepinage or {}))
    variante.entree_hash = sortie['hash_entree']
    # ``tiroirs`` (PV49) et ``suggestions`` (PV50) ne sont PAS persistés : ce
    # sont des charges utiles d'ATELIER, recalculées à la demande, dont les
    # impacts chiffrés valent pour les paramètres du moment. Les figer dans une
    # variante ferait lire un jour « -4 modules si vous élargissez la rive » sur
    # des réglages qui ont bougé. ``marges``, elle, MESURE ce plan-ci : elle
    # reste avec lui.
    variante.resultat = {k: v for k, v in sortie.items()
                         if k not in ('preuve', 'tiroirs', 'suggestions')}
    variante.preuve = sortie['preuve']
    variante.version_moteur = VERSION_MOTEUR
    variante.statut = VarianteCalepinage.Statut.CALCULEE
    variante.save()

    _appliquer_gardes_publication(variante)
    return variante


def _appliquer_gardes_publication(variante):
    """AOF28 — passe ``publiable`` SI et SEULEMENT SI la preuve le démontre."""
    raisons = variante.raisons_de_non_publiabilite()
    if raisons:
        variante.statut = variante.Statut.CALCULEE
        variante.justification = '\n'.join(raisons)
    else:
        variante.statut = variante.Statut.PUBLIABLE
        variante.justification = variante.preuve.get('libelle', '')
    variante.save(update_fields=['statut', 'justification', 'updated_at'])
    return variante


# ─────────────────────────────────────── AOF62 — actions de variante
def retenir_variante(variante, *, user=None):
    """Désigne LA variante retenue — IDEMPOTENTE, et jamais sur une périmée.

    Rejouer l'appel sur une variante déjà retenue ne fait rien (aucune seconde
    bascule, aucun second calcul). Une variante ``PERIME`` est REFUSÉE : son
    entrée a bougé depuis le calcul, la retenir publierait un plan que la
    donnée ne soutient plus.
    """
    from . import services

    if variante.statut == variante.Statut.PERIME:
        raise VariantePerimee(
            "La variante « %s » est PÉRIMÉE : son entrée a changé depuis le "
            "calcul. Recalculez-la avant de la retenir." % variante.nom)
    if variante.est_retenue:
        return variante
    return services.retenir_variante(variante)


def comparer_variantes(company, identifiants):
    """Compare N variantes EN UN APPEL — une requête, aucun calcul moteur.

    Les nombres comparés sont ceux qui ont été PROUVÉS au calcul : la
    comparaison ne rejoue pas le moteur, sans quoi deux colonnes du même écran
    pourraient sortir de deux versions différentes.
    """
    from .models import VarianteCalepinage

    identifiants = [int(i) for i in identifiants]
    variantes = list(VarianteCalepinage.objects.filter(
        company=company, pk__in=identifiants).select_related('toiture'))
    trouvees = {v.pk for v in variantes}
    manquantes = [i for i in identifiants if i not in trouvees]
    lignes = []
    for variante in variantes:
        preuve = variante.preuve or {}
        lignes.append({
            'id': variante.pk,
            'nom': variante.nom,
            'role': variante.role,
            'statut': variante.statut,
            'est_retenue': variante.est_retenue,
            'toiture': variante.toiture_id,
            'total_modules': variante.total_modules,
            'kwc': variante.puissance_kwc,
            'total_optimal': preuve.get('total_optimal'),
            'optimal': preuve.get('optimal'),
            'methode': preuve.get('methode'),
            'marge_troncon_min': preuve.get('marge_troncon_min'),
            'marge_bande_min': preuve.get('marge_bande_min'),
            'version_moteur': variante.version_moteur,
            'entree_hash': variante.entree_hash,
        })
    lignes.sort(key=lambda ligne: (-(ligne['total_modules'] or 0),
                                   ligne['id']))
    reference = lignes[0]['total_modules'] if lignes else 0
    for ligne in lignes:
        ligne['delta_modules'] = (ligne['total_modules'] or 0) - reference
    return {'lignes': lignes, 'introuvables': manquantes,
            'reference_modules': reference}


def calculer_sensibilites(variante, *, user=None, moteur=None):
    """Rejoue la batterie défavorable et PERSISTE les marches ``SENSIBILITE``.

    IDEMPOTENTE par construction : chaque sensibilité est identifiée par son
    CODE moteur et écrite en ``update_or_create`` sous la variante parente —
    rejouer l'appel met à jour les mêmes lignes, il n'en crée jamais de
    secondes.
    """
    from core.calepinage.sensibilites import batterie

    from .models import VarianteCalepinage

    toiture = variante.toiture
    document = calepinage_io.document_entree(toiture,
                                             params=variante.params or None)
    entree = _entree(document)
    obstacles = appliquer_regles(entree.obstacles)
    par_surface = calepinage_io.affectations_du_document(
        document, entree.surfaces, obstacles)
    if len(entree.surfaces) != 1:
        raise EntreeInvalide(
            "La batterie de sensibilités se calcule surface par surface : "
            "cette toiture en déclare %d." % len(entree.surfaces))
    surface = entree.surfaces[0]
    resultat = batterie(surface, entree.parametres,
                        par_surface.get(surface.repere, ()), entree.zones,
                        engagement=entree.parametres.engagement_modules)

    enfants = []
    for sensibilite in resultat.sensibilites:
        enfant, _cree = VarianteCalepinage.objects.update_or_create(
            company=variante.company, toiture=toiture, parent=variante,
            role=VarianteCalepinage.Role.SENSIBILITE, nom=sensibilite.code,
            defaults={
                'appel_offre_id': variante.appel_offre_id,
                'params': dict(variante.params or {}),
                'entree_hash': variante.entree_hash,
                'resultat': {'total_modules': sensibilite.modules,
                             'delta': sensibilite.delta,
                             'libelle': sensibilite.libelle},
                'preuve': {'total_retenu': sensibilite.modules,
                           'total_optimal': sensibilite.modules,
                           'methode': 'sensibilite',
                           'version_moteur': VERSION_MOTEUR},
                'statut': VarianteCalepinage.Statut.CALCULEE,
                'justification': sensibilite.libelle,
                'version_moteur': VERSION_MOTEUR,
            })
        enfants.append(enfant)
    return {
        'reference_modules': resultat.reference,
        'plancher_modules': resultat.plancher,
        'engagement_modules': resultat.engagement,
        'verdict': resultat.verdict(),
        'non_applicables': list(resultat.non_applicables),
        'sensibilites': [
            {'id': enfant.pk, 'code': sensibilite.code,
             'libelle': sensibilite.libelle, 'modules': sensibilite.modules,
             'delta': sensibilite.delta, 'tenu': sensibilite.tenu}
            for enfant, sensibilite in zip(enfants, resultat.sensibilites)],
    }


# ───────────────────────────── PV67 — variantes d'ORIENTATION auto-générées
#
# Le dessinateur savait déjà comparer des variantes : encore fallait-il les
# SAISIR une par une, en recopiant les paramètres et en changeant un mot. Les
# trois questions d'orientation d'une toiture — dans quel sens courent les
# rangées, quelle table pose-t-on, peut-on mélanger deux kits — sont pourtant
# toujours les mêmes, et personne ne les posait toutes.
#
# Deux règles gouvernent ce module, et elles ne se négocient pas :
#
# 1. **Aucun compte n'est estimé.** Chaque alternative est REJOUÉE par
#    ``calculer_variante`` — le même chemin que la variante retenue, la même
#    preuve, les mêmes gardes de publication. Une comparaison dont une colonne
#    serait extrapolée serait une comparaison fausse.
# 2. **Une orientation inconstructible n'est jamais posée.** C'est
#    ``orientation.verifier`` qui tranche (la table dos-à-dos est-ouest de
#    AOF45 a coûté une planche entière) et son MOTIF est publié tel quel :
#    l'alternative écartée dit POURQUOI, elle ne disparaît pas.

#: Les quatre familles d'alternative, dans leur ordre de publication.
VARIANTES_ORIENTATION = (
    ('AXE_INVERSE', 'Rangées dans le sens perpendiculaire'),
    ('TABLE_INVERSEE', 'Modules posés dans l\'autre orientation de table'),
    ('TABLE_DOS_A_DOS', 'Autre famille de table (dos-à-dos / panneau simple)'),
    ('KITS_MIXTES', 'Les deux orientations de table autorisées ensemble'),
)

#: Libellés indexés par code — l'écran ne rédige rien, il affiche.
LIBELLES_ORIENTATION = dict(VARIANTES_ORIENTATION)


def _variante_retenue(toiture):
    """LA variante de référence de cette toiture, ou ``None``."""
    from .models import VarianteCalepinage

    return VarianteCalepinage.objects.filter(
        company=toiture.company, toiture=toiture, est_retenue=True).first()


def _catalogue_kits(company):
    """Les kits ACTIFS de la société, traduits au vocabulaire du contrat.

    La traduction passe par ``kits_vers_document`` — la SEULE qui existe : la
    refaire ici créerait une deuxième table de correspondance modèle -> moteur,
    et les deux divergeraient. Un kit dont la géométrie est inexploitable est
    IGNORÉ plutôt que fatal : un kit incomplet au catalogue ne doit pas priver
    la toiture de ses alternatives.
    """
    from .models import KitCalepinage

    lignes = []
    for kit in KitCalepinage.objects.filter(
            company=company, actif=True).order_by('code'):
        try:
            lignes.extend(calepinage_io.kits_vers_document([kit]))
        except EntreeInvalide:
            continue
    return lignes


def _patchs_orientation(entree, catalogue):
    """Les patchs de PARAMÈTRES candidats — ou leur motif de renoncement.

    Rend ``[(code, patch_ou_None, motif)]`` dans l'ordre de publication. Le
    vocabulaire des patchs est celui du preset (``axe_rangee``,
    ``kits_autorises``), c'est-à-dire exactement celui que ``majParametres``
    rejoue et que PV50 publie déjà dans ses suggestions : une alternative
    proposée ici s'applique donc du même geste qu'une suggestion.
    """
    courants = [k.code for k in entree.kits]
    orientations = {k.orientation.value for k in entree.kits}
    familles = {k.modules_par_table >= 2 for k in entree.kits}
    axe = entree.parametres.axe_rangee

    candidats = [('AXE_INVERSE', {'axe_rangee': axe.perpendiculaire.value},
                  '')]

    if len(orientations) != 1:
        candidats.append((
            'TABLE_INVERSEE', None,
            'Le jeu de kits mélange déjà les deux orientations de table : '
            "il n'y a pas d'autre orientation à proposer."))
        autres_orientations = []
    else:
        courante = orientations.pop()
        autres_orientations = [ligne['code'] for ligne in catalogue
                               if ligne['orientation'] != courante]
        if autres_orientations:
            candidats.append(('TABLE_INVERSEE',
                              {'kits_autorises': autres_orientations}, ''))
        else:
            candidats.append((
                'TABLE_INVERSEE', None,
                'Aucun kit actif ne pose ses modules dans une autre '
                'orientation que %s : le catalogue ne permet pas cette '
                'alternative.' % courante.lower()))

    if len(familles) != 1:
        candidats.append((
            'TABLE_DOS_A_DOS', None,
            'Le jeu de kits mélange déjà les tables dos-à-dos et les panneaux '
            "simples : il n'y a pas d'autre famille à proposer."))
    else:
        dos_a_dos = familles.pop()
        autres_familles = [ligne['code'] for ligne in catalogue
                           if (ligne['modules_par_table'] >= 2) != dos_a_dos]
        if autres_familles:
            candidats.append(('TABLE_DOS_A_DOS',
                              {'kits_autorises': autres_familles}, ''))
        else:
            candidats.append((
                'TABLE_DOS_A_DOS', None,
                'Aucun kit actif de la famille « %s » : le catalogue ne '
                'permet pas cette alternative.'
                % ('panneau simple' if dos_a_dos else 'table dos-à-dos')))

    mixtes = sorted(set(courants) | set(autres_orientations))
    if autres_orientations and mixtes != sorted(set(courants)):
        candidats.append(('KITS_MIXTES', {'kits_autorises': mixtes}, ''))
    else:
        candidats.append((
            'KITS_MIXTES', None,
            "Aucun second jeu de kits à autoriser en plus de l'actuel : le "
            'mélange serait identique au plan retenu.'))
    return candidats


def _alternative_calculable(toiture, params):
    """``(entree, motif)`` — l'entrée patchée, ou le MOTIF de son refus.

    Le refus vient du MOTEUR (``orientation.verifier``), jamais d'une règle
    réécrite ici : c'est lui qui sait qu'une table dos-à-dos impose des rangées
    nord-sud, et sa phrase est celle qu'on publie.
    """
    from core.calepinage.orientation import ErreurOrientation, verifier

    try:
        document = calepinage_io.document_entree(toiture, params=params)
        entree = _entree(document)
    except EntreeInvalide as erreur:
        return (None, str(erreur))
    try:
        verifier(entree.parametres, entree.surfaces)
    except ErreurOrientation as erreur:
        return (None, str(erreur))
    return (entree, '')


def generer_variantes_orientation(toiture, *, user=None, moteur=None):
    """PV67 — pose les alternatives d'orientation de CETTE toiture, REJOUÉES.

    Part de la variante RETENUE (ses paramètres sont la référence : ce sont
    ceux que le dessinateur a validés), en dérive 2 à 4 patchs, et rejoue
    chacun par ``calculer_variante(role=ALTERNATIVE, parent=retenue)``. Les
    comptes publiés sont donc ceux du moteur, avec leur preuve — jamais une
    extrapolation.

    IDEMPOTENTE : chaque alternative est identifiée par son CODE sous la
    variante parente ; rejouer l'appel met à jour les mêmes lignes au lieu
    d'empiler des jumelles dans l'écran de comparaison.

    Raises:
        SansVarianteRetenue: la toiture n'a aucune variante retenue — il n'y a
            alors ni référence à comparer ni paramètres à patcher.
    """
    from .models import VarianteCalepinage

    retenue = _variante_retenue(toiture)
    if retenue is None:
        raise SansVarianteRetenue(
            'Cette toiture n\'a aucune variante RETENUE : les alternatives '
            "d'orientation se comparent à un plan de référence, et il n'y en "
            'a pas encore. Calculez un calepinage puis retenez-le.')

    params_base = dict(retenue.params or toiture.parametres_calepinage or {})
    reference, motif = _alternative_calculable(toiture, params_base)
    if reference is None:
        raise EntreeInvalide(motif)

    catalogue = _catalogue_kits(toiture.company)
    produites, ignorees = [], []
    for code, patch, motif in _patchs_orientation(reference, catalogue):
        libelle = LIBELLES_ORIENTATION[code]
        if patch is None:
            ignorees.append({'code': code, 'libelle': libelle,
                             'motif': motif})
            continue
        params = dict(params_base)
        params.update(patch)
        _entree_patchee, motif = _alternative_calculable(toiture, params)
        if _entree_patchee is None:
            ignorees.append({'code': code, 'libelle': libelle,
                             'motif': motif})
            continue
        existante = VarianteCalepinage.objects.filter(
            company=toiture.company, toiture=toiture, parent=retenue,
            role=VarianteCalepinage.Role.ALTERNATIVE, nom=code).first()
        try:
            variante = calculer_variante(
                toiture, params=params, user=user, moteur=moteur, nom=code,
                role=VarianteCalepinage.Role.ALTERNATIVE, parent=retenue,
                appel_offre=retenue.appel_offre, variante=existante)
        except (EntreeInvalide, CalepinageIncoherent) as erreur:
            # Une alternative qui ne tient pas debout est ÉCARTÉE avec son
            # motif : elle ne doit ni être publiée, ni emporter les autres.
            ignorees.append({'code': code, 'libelle': libelle,
                             'motif': str(erreur)})
            continue
        produites.append({
            'id': variante.pk, 'code': code, 'libelle': libelle,
            'nom': variante.nom, 'statut': variante.statut,
            'modules': variante.total_modules,
            'kwc': variante.puissance_kwc,
            'delta_modules': ((variante.total_modules or 0)
                              - (retenue.total_modules or 0)),
            'patch': patch,
        })
    return {
        'toiture': toiture.pk,
        'retenue': retenue.pk,
        'reference_modules': retenue.total_modules or 0,
        'variantes': produites,
        'ignorees': ignorees,
    }


def calculer_marches(variante):
    """Rejoue l'échelle de décomposition d'une variante — deltas SIGNÉS.

    Les marches sont les variantes filles de rôle ``MARCHE`` : chacune porte
    son état nommé et son compte. ``echelle.comparer`` republie les deltas à
    partir des comptes PERSISTÉS, et ``verifier_honnetete`` fait échouer une
    marche qui n'a pas redonné le nombre qu'elle annonçait.
    """
    from core.calepinage.echelle import EtatNomme, comparer, verifier_honnetete

    from .models import VarianteCalepinage

    filles = list(VarianteCalepinage.objects.filter(
        company=variante.company, parent=variante,
        role=VarianteCalepinage.Role.MARCHE).order_by('id'))
    etats = [
        EtatNomme(code=fille.nom, libelle=fille.justification or fille.nom,
                  calculer=(lambda f=fille: int(f.total_modules or 0)),
                  attendu=(fille.resultat or {}).get('attendu'))
        for fille in filles
    ]
    echelle = comparer(etats)
    motifs = verifier_honnetete(echelle, strict=False)
    return {
        'recit': echelle.recit(),
        'depart': echelle.depart,
        'arrivee': echelle.arrivee,
        'gain_total': echelle.gain_total,
        'honnete': not motifs,
        'motifs': list(motifs),
        'marches': [{'code': m.code, 'libelle': m.libelle,
                     'modules': m.modules, 'delta': m.delta,
                     'attendu': m.attendu} for m in echelle.marches],
    }
