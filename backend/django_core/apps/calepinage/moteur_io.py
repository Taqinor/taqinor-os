"""Sérialisation ENTRÉE/SORTIE du moteur de calepinage — copie du module.

SOLMVP15 — ce fichier est la RAPATRIATION, dans ``apps.calepinage``, des parties
PURES de l'ancien ``apps/ao/calepinage_io.py`` : le module autonome (roof_layout
v2) doit calculer sans dépendre du module AO, qui sort du produit. Le
comportement est celui d'avant, à la ligne près — aucune valeur, aucun refus,
aucune clé publiée n'a bougé.

CE QUI A ÉTÉ LAISSÉ CHEZ AO, ET POURQUOI : les fonctions qui prennent une
``ToitureAO`` ou un ``KitCalepinage`` en entrée (``surface_vers_document``,
``obstacles_vers_document``, ``zones_vers_document``, ``kits_vers_document``,
``document_entree``). Elles composent un document depuis les MODÈLES d'AO —
c'est le studio 2D d'AO, pas l'atelier 3D : le module, lui, reçoit toujours un
document DÉJÀ composé (le contrat d'entrée du moteur). Aucune capacité de
l'atelier n'en dépend.

Le noyau de calcul reste où il est : ``core.calepinage`` est une fondation, ce
fichier n'en est que l'adaptateur de sérialisation.
"""
from __future__ import annotations

from decimal import Decimal

from core.calepinage.version import SCHEMA_VERSION, VERSION_MOTEUR

#: ACAL327 — SEULS les noms qu'un autre module lit (garde AST :
#: ``tests/test_acal_moteur_symboles_morts.py``). Les tables et traducteurs
#: internes restent des détails de ce module.
__all__ = [
    'EntreeInvalide',
    'affectations_du_document',
    'AXE_AUTO', 'deriver_axe_rangee',
    'resultat_vers_json', 'preuve_vers_json',
    'marges_vers_json', 'suggestion_vers_json', 'plan_vers_json',
]


class EntreeInvalide(ValueError):
    """L'entrée persistée ne peut pas produire un document de calepinage.

    Toujours porteuse d'un motif en FRANÇAIS : c'est ce que l'utilisateur lit
    dans un 400, pas un code d'erreur.
    """


#: ``ObstacleAO.Nature`` (13 valeurs métier AO) -> ``TypeObstacle`` du moteur
#: (13 valeurs). Les natures AO sans équivalent exact tombent sur
#: ``NATURE_INCONNUE`` — sans conséquence sur le calcul : le dégagement
#: RÉELLEMENT appliqué est toujours celui que l'ORM a dérivé (AOF22), transmis
#: en surcharge explicite, jamais redevine par le moteur.
NATURE_VERS_TYPE_MOTEUR = {
    'caisson_technique': 'CAISSON_BETON',
    'cage_escalier': 'CAGE_ESCALIER',
    'edicule': 'EDICULE',
    'souche': 'SOUCHE',
    'groupe_clim': 'CLIMATISEUR',
    'acrotere': 'ACROTERE',
    'joint_dilatation': 'JOINT_DILATATION',
    'muret': 'MURET',
    'decrochement_niveau': 'MURET',
    'pan_coupe': 'NATURE_INCONNUE',
    'lanterneau': 'LANTERNEAU',
    'exutoire_fumee': 'NATURE_INCONNUE',
    'chemin_cables': 'NATURE_INCONNUE',
}

#: ``ObstacleAO.Provenance`` -> ``Provenance`` du moteur. Le vocabulaire AO est
#: le format CANONIQUE (en-tête du groupe) ; le moteur nomme ``RELEVE`` ce que
#: l'AO nomme ``MESURE``.
PROVENANCE_VERS_MOTEUR = {
    'MESURE': 'RELEVE',
    'MESURE_DOUTEUX': 'RELEVE_DOUTEUX',
    'PLAN': 'PLAN',
    'DEVINE': 'DEVINE',
    'DECLARE_CLIENT': 'DECLARE_CLIENT',
    'ECARTE': 'ECARTE',
}


def _f(valeur, defaut=None):
    """``Decimal``/``str``/``None`` -> ``float`` (ou ``defaut``)."""
    if valeur is None or valeur == '':
        return defaut
    if isinstance(valeur, Decimal):
        return float(valeur)
    return float(valeur)


def _contour(points):
    return [[_f(p[0], 0.0), _f(p[1], 0.0)] for p in (points or [])]


# ─────────────────────────────────────────────────────── axe des rangées
#: ERR-QAH-CALEPINAGE-SOL-AXE-NORD-SUD — valeur d'``axe_rangee`` qui DEMANDE au
#: serveur de dériver l'axe. L'écran terrain/ombrière envoyait toujours
#: ``NORD_SUD`` : un module par table orienté SUD (le cas courant) était alors
#: refusé « inconstructible » (400) alors que l'axe est IMPOSÉ par le kit et
#: l'azimut. Le front ne recopie pas la règle : il envoie ``AUTO`` et c'est
#: ``core.calepinage.orientation.axe_rangee_impose`` — la seule source — qui
#: tranche ici.
AXE_AUTO = 'AUTO'


class _KitAxe:
    """Le seul attribut que ``axe_rangee_impose`` lit d'un kit."""

    __slots__ = ('modules_par_table',)

    def __init__(self, modules_par_table):
        self.modules_par_table = modules_par_table


def deriver_axe_rangee(document):
    """Remplace ``axe_rangee: "AUTO"`` par l'axe IMPOSÉ par les kits.

    Rend le document inchangé quand aucun ``AUTO`` n'y figure (un axe
    explicite reste contrôlé — et refusé s'il est faux — par le moteur).
    Sinon, rend une COPIE où ``parametres.axe_rangee`` et chaque surface en
    ``AUTO`` (ou sans axe) portent l'axe dérivé de chaque kit utilisé et de
    l'azimut de chaque surface. Des kits/surfaces imposant deux axes
    différents sont REFUSÉS (``EntreeInvalide``), jamais arbitrés.
    """
    if not isinstance(document, dict):
        return document
    params = document.get('parametres')
    surfaces = document.get('surfaces')
    if not isinstance(params, dict):
        return document
    surfaces = surfaces if isinstance(surfaces, list) else []
    auto = params.get('axe_rangee') == AXE_AUTO or any(
        isinstance(s, dict) and s.get('axe_rangee') == AXE_AUTO
        for s in surfaces)
    if not auto:
        return document

    from core.calepinage.orientation import axe_rangee_impose

    codes = params.get('kits')
    kits = [k for k in (document.get('kits') or []) if isinstance(k, dict)
            and (not codes or k.get('code') in codes)]
    if not kits:
        raise EntreeInvalide(
            "Axe des rangées « AUTO » : aucun kit à partir duquel le dériver.")
    azimuts = [s.get('azimut_deg', 180.0) for s in surfaces
               if isinstance(s, dict)] or [180.0]
    axes = set()
    try:
        for kit in kits:
            modele = _KitAxe(int(kit.get('modules_par_table', 1)))
            for azimut in azimuts:
                axes.add(axe_rangee_impose(
                    modele, 180.0 if azimut is None else float(azimut)).value)
    except (TypeError, ValueError) as erreur:
        raise EntreeInvalide(
            "Axe des rangées « AUTO » : kit ou azimut illisible (%s)."
            % erreur) from erreur
    if len(axes) > 1:
        raise EntreeInvalide(
            "Axe des rangées « AUTO » : les kits et orientations de ce relevé "
            "imposent deux axes différents (%s) — calepinez-les séparément."
            % ', '.join(sorted(axes)))
    axe = axes.pop()
    copie = dict(document)
    copie['parametres'] = dict(params, axe_rangee=axe)
    copie['surfaces'] = [
        dict(s, axe_rangee=axe)
        if isinstance(s, dict) and s.get('axe_rangee') in (None, AXE_AUTO)
        else s
        for s in surfaces]
    return copie


def _affectations_par_prefixe(surfaces, obstacles):
    """Affecte chaque obstacle au segment dont le repère porte le suffixe.

    Convention de relevé (planches FRDISI) : un obstacle du segment ``S2``
    s'appelle ``S2_cage``. On rattache par ce préfixe ; un obstacle qui ne
    désigne AUCUN segment n'est pas affecté — le service refusera, plutôt que
    de le compter partout (il bloquerait trois fois) ou nulle part (il
    disparaîtrait du plan).
    """
    affectations = {}
    for index, surface in enumerate(surfaces, start=1):
        prefixe = 'S%d_' % index
        affectations[surface['repere']] = [
            o['repere'] for o in obstacles
            if o['repere'].startswith(prefixe)
            or o['repere'].startswith('%s_' % surface['repere'])
        ]
    return affectations


def affectations_du_document(document, surfaces, obstacles):
    """``{repère de surface: (obstacles du moteur, …)}`` — jamais deviné.

    Une seule surface : tous les obstacles. Plusieurs surfaces : l'affectation
    DOIT être déclarée et COMPLÈTE (chaque obstacle appartient à exactement une
    surface). Toute lacune est un refus nommé, jamais un compte silencieux.
    """
    obstacles = tuple(obstacles)
    if len(surfaces) == 1:
        return {surfaces[0].repere: obstacles}

    declarees = (document or {}).get('affectations')
    if not declarees:
        raise EntreeInvalide(
            "Entrée à %d surfaces sans affectation des obstacles : préciser "
            "`affectations` ({repère de surface: [repères d'obstacles]}). "
            "Deviner l'affectation produirait un compte faux."
            % len(surfaces))

    par_repere = {o.repere: o for o in obstacles}
    resultat = {}
    affectes = set()
    for surface in surfaces:
        reperes = declarees.get(surface.repere)
        if reperes is None:
            raise EntreeInvalide(
                "La surface « %s » n'a aucune affectation d'obstacles "
                "déclarée." % surface.repere)
        lot = []
        for repere in reperes:
            if repere not in par_repere:
                raise EntreeInvalide(
                    "La surface « %s » référence l'obstacle inconnu « %s »."
                    % (surface.repere, repere))
            lot.append(par_repere[repere])
            affectes.add(repere)
        resultat[surface.repere] = tuple(lot)

    orphelins = sorted(set(par_repere) - affectes)
    if orphelins:
        raise EntreeInvalide(
            "Obstacles non affectés à une surface : %s. Un obstacle sans "
            "segment disparaîtrait du plan sans que personne le voie."
            % ', '.join(orphelins))
    return resultat


# ─────────────────────────────────────────────────────── sortie
def preuve_vers_json(preuve, marges, *, controles=(), pas_recherche_m=0.01):
    """La PREUVE persistable d'AOF28, dans SON vocabulaire.

    Les clés sont celles que ``VarianteCalepinage.raisons_de_non_publiabilite``
    lit (``total_retenu``, ``total_optimal``, ``marge_troncon_min``,
    ``marge_bande_min``) : c'est ce qui rend la garde de publication effective
    au lieu d'être un commentaire.

    **Une marge NON MESURÉE vaut ``None``, jamais 0.** ``Marges`` du moteur
    rend ``0.0`` aussi bien pour « au ras » que pour « aucune marge de ce type
    n'existe dans ce plan » (une toiture sans obstacle n'a aucune marge de
    bande). Persister ce ``0.0`` refuserait la publication d'un plan sans
    obstacle : la garde d'AOF28 se dévaluerait, et l'utilisateur apprendrait à
    l'ignorer. Le critère de mesure est le repère fautif : ``marges_du_plan``
    ne nomme une rangée ou un obstacle QUE lorsqu'il a réellement mesuré
    quelque chose.
    """
    troncon = bande = None
    if marges is not None:
        if marges.rangee_critique:
            troncon = round(marges.troncon_min_m, 6)
        if marges.obstacle_critique:
            bande = round(marges.bande_min_m, 6)
    return {
        'total_retenu': preuve.compte_retenu,
        'total_optimal': preuve.compte_optimal,
        'methode': preuve.methode.value,
        'methode_exacte': bool(preuve.methode.exacte),
        'optimal': bool(preuve.optimal),
        'libelle': preuve.libelle,
        'pas_cm': round(pas_recherche_m * 100.0, 3),
        'nb_optima': preuve.nb_plans_optimaux,
        'borne_superieure': preuve.borne_superieure,
        'marge_troncon_min': troncon,
        'marge_bande_min': bande,
        'rangee_critique': marges.rangee_critique if marges else '',
        'obstacle_critique': marges.obstacle_critique if marges else '',
        'controles': list(controles),
        'version_moteur': VERSION_MOTEUR,
    }


def marges_vers_json(marges):
    """PV49 — les marges de robustesse PUBLIÉES, en centimètres.

    **Une grandeur NON MESURÉE vaut ``None``, jamais ``0``.** ``Marges`` du
    moteur rend ``0.0`` aussi bien pour « au ras » que pour « ce plan n'a
    aucune marge de ce type » (une toiture sans obstacle n'a aucune marge de
    bande). Publier ce zéro ferait lire « marge nulle » là où rien n'a été
    mesuré — exactement l'erreur que ``preuve_vers_json`` évite déjà, avec le
    MÊME critère : le repère fautif. ``marges_du_plan`` ne nomme une rangée ou
    un obstacle QUE lorsqu'il a réellement mesuré quelque chose.
    """
    troncon = bande = None
    rangee = obstacle = ''
    if marges is not None:
        rangee = marges.rangee_critique or ''
        obstacle = marges.obstacle_critique or ''
        if rangee:
            troncon = round(marges.troncon_min_cm, 3)
        if obstacle:
            bande = round(marges.bande_min_cm, 3)
    return {
        'troncon_min_cm': troncon,
        'bande_min_cm': bande,
        'rangee_critique': rangee,
        'obstacle_critique': obstacle,
    }


# ─────────────────────────────────────────────────── suggestions (PV50)
#
# ``recommandations.proposer`` rend des ``Recommandation`` dont le
# ``patch_entree`` est écrit dans le vocabulaire du MOTEUR (``allee_m``,
# ``kits``, ``ecarter``…). L'écran, lui, ne sait appliquer que deux choses :
# un patch de PARAMÈTRES de calepinage (le dict de paramètres que la requête
# porte) ou une décision sur un OBSTACLE (le champ ``provenance`` d'un
# ``ObstacleAO``). La traduction est donc EXPLICITE, clé par clé — et une clé
# non cartographiée fait TOMBER la suggestion entière plutôt que de publier un
# bouton « appliquer » qui n'appliquerait rien.

#: Patch MOTEUR -> clé du dict de PARAMÈTRES de l'API (vocabulaire du preset).
#: Seul ``allee_m`` change de nom : les autres portent déjà le même.
PATCH_MOTEUR_VERS_PARAMS = {
    'allee_m': 'allee_min_m',
    'rive_laterale_m': 'rive_laterale_m',
    'rive_extremite_m': 'rive_extremite_m',
    'axe_rangee': 'axe_rangee',
    'kits': 'kits_autorises',
}

#: Patch MOTEUR -> provenance AO visée. Le vocabulaire AO est le format
#: CANONIQUE (cf. ``PROVENANCE_VERS_MOTEUR``) : le moteur nomme ``RELEVE`` ce
#: que l'AO nomme ``MESURE``, et c'est la valeur AO qui doit voyager, puisque
#: c'est elle que l'écran écrira sur ``ObstacleAO.provenance``.
PATCH_MOTEUR_VERS_OBSTACLE = {
    'ecarter': 'ECARTE',
    'confirmer': 'MESURE',
}


def _valeur_de_patch(cle, valeur):
    """Convertit la valeur d'un patch (le moteur les écrit en CHAÎNES)."""
    if cle in ('allee_m', 'rive_laterale_m', 'rive_extremite_m'):
        return float(valeur)
    if cle == 'kits':
        return [code for code in str(valeur).split('+') if code]
    return str(valeur)


def action_de_patch(patch_entree):
    """``patch_entree`` du moteur -> ``action`` DISCRIMINÉE, ou ``None``.

    Deux familles, jamais mélangées dans la même action : un patch qui
    toucherait à la fois un paramètre et un obstacle n'aurait aucun bouton
    capable de l'appliquer d'un clic. ``None`` = suggestion à JETER.
    """
    patch = list(patch_entree or ())
    if not patch:
        return None
    cles = {cle for cle, _valeur in patch}
    if not cles <= (set(PATCH_MOTEUR_VERS_PARAMS)
                    | set(PATCH_MOTEUR_VERS_OBSTACLE)):
        # Clé de patch inconnue de cette table : le moteur a gagné un levier
        # que l'écran ne sait pas appliquer. On JETTE la suggestion — publier
        # un bouton qui n'applique rien est pire que ne rien proposer.
        return None
    if cles <= set(PATCH_MOTEUR_VERS_OBSTACLE):
        if len(patch) != 1:
            return None  # deux décisions d'obstacle = deux suggestions
        cle, repere = patch[0]
        return {'type': 'obstacle', 'obstacle': str(repere),
                'provenance': PATCH_MOTEUR_VERS_OBSTACLE[cle]}
    if cles <= set(PATCH_MOTEUR_VERS_PARAMS):
        return {'type': 'parametres',
                'patch': {PATCH_MOTEUR_VERS_PARAMS[cle]:
                          _valeur_de_patch(cle, valeur)
                          for cle, valeur in patch}}
    return None  # patch MIXTE paramètres + obstacle : inapplicable en un clic


def suggestion_vers_json(recommandation):
    """Une ``Recommandation`` du moteur -> une suggestion du contrat.

    Rend ``None`` quand l'action n'est pas traduisible (cf. ``action_de_patch``).

    ``gain_modules`` est SIGNÉ : un arbitrage d'obstacle peut coûter des
    modules, et le publier positif ferait passer une perte assumée pour un
    gain. ``gain_kwc``, ``confiance`` et ``question_a_poser`` sont déclarés
    FACULTATIFS par le contrat ; le moteur les CALCULE pour toutes ses
    propositions, alors on ne les jette pas.
    """
    action = action_de_patch(recommandation.patch_entree)
    if action is None:
        return None
    return {
        'code': recommandation.code,
        'titre': recommandation.titre,
        'gain_modules': int(recommandation.gain_modules),
        'gain_kwc': round(float(recommandation.gain_kwc), 3),
        'confiance': recommandation.confiance.value,
        'question_a_poser': recommandation.question_a_poser,
        'action': action,
    }


def resultat_vers_json(*, repere, hash_entree, modules, kwc, plans,
                       engageable=True, motifs_non_engageable=()):
    """Le RÉSULTAT persistable d'AOF28 : rangées explicites + tables + totaux.

    **Sur la clé ``x0``.** Le contrat d'AOF28 nomme ``x0`` la position d'une
    rangée ; le moteur, dans son repère unifié, la nomme ``y0`` (``x`` court le
    long de la rangée, ``y`` en travers). Les deux clés sont émises avec la
    MÊME valeur — elles ne peuvent donc pas diverger — pour honorer le contrat
    déjà publié sans inscrire un axe faux dans la donnée.
    """
    return {
        'repere': repere,
        'hash_entree': hash_entree,
        'version_moteur': VERSION_MOTEUR,
        'schema_version': SCHEMA_VERSION,
        'total_modules': int(modules),
        'kwc': round(float(kwc), 3),
        'engageable': bool(engageable),
        'motifs_non_engageable': list(motifs_non_engageable),
        'plans': list(plans),
        'rangees': [rangee for plan in plans for rangee in plan['rangees']],
    }


def plan_vers_json(surface_repere, resultat_optimum, tables=()):
    """Un plan de pose (une surface) : rangées explicites + tables posées."""
    rangees = []
    for rangee in resultat_optimum.plan.rangees:
        rangees.append({
            'surface': surface_repere,
            # même valeur sous les deux noms — voir ``resultat_vers_json``
            'x0': round(rangee.y0, 4),
            'y0': round(rangee.y0, 4),
            'kit': rangee.kit_code,
            'modules': int(rangee.modules),
            'emprise_m': round(rangee.emprise_m, 4),
            'troncons': [[round(a, 4), round(b, 4)]
                         for a, b in rangee.troncons],
        })
    return {
        'surface': surface_repere,
        'modules': int(resultat_optimum.plan.modules),
        'ecart_a_l_optimum': int(resultat_optimum.ecart_a_l_optimum),
        'rangees': rangees,
        'tables': [{'x0': round(t.x0, 4), 'x1': round(t.x1, 4),
                    'y0': round(t.y0, 4), 'y1': round(t.y1, 4),
                    'kit': t.kit_code}
                   for t in tables],
    }
