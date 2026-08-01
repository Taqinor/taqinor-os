# -*- coding: utf-8 -*-
"""AOF35 — dégagement DÉRIVÉ de (type, provenance), règle appliquée TRACÉE.

Le script d'origine posait ``CLEAR = 0.30`` et ``CLEAR_INC = 0.50`` puis
choisissait à la main, ligne par ligne, lequel des deux s'appliquait. Ici la
règle est une TABLE : dégagement effectif = ``max(défaut du type, défaut de la
provenance)``, surchargeable par obstacle, **et la règle retenue est écrite
dans le résultat** — un maître d'ouvrage qui demande « pourquoi 0,50 ici ? »
obtient la phrase, pas une relecture de code.

``engageable(obstacles)`` est la version moteur de l'``assert len(OBS) == 28``
de ``planche_06H`` : un plan dont le compte englobe un objet venu du PLAN ou
DEVINÉ n'est pas engageable — sur l'aile L ces deux emprises valent 12 modules.
"""

from core.calepinage.types import Obstacle, Provenance, TypeObstacle
from core.calepinage.units import TOL_FUSION_M, TOL_LONGUEUR_M

__all__ = [
    "DEGAGEMENT_PAR_TYPE", "DEGAGEMENT_PAR_PROVENANCE", "PROVENANCES_ENGAGEABLES",
    "degagement_par_type", "degagement_par_provenance", "degagement_effectif",
    "appliquer_regles", "engageable", "fusionner", "intervalles_bloques",
]


#: Dégagement PAR DÉFAUT du type métier (13 types, en mètres).
DEGAGEMENT_PAR_TYPE = (
    (TypeObstacle.CAISSON_BETON, 0.30),
    (TypeObstacle.CAGE_ESCALIER, 0.30),
    (TypeObstacle.EDICULE, 0.30),
    (TypeObstacle.SOUCHE, 0.50),
    (TypeObstacle.CLIMATISEUR, 0.50),
    (TypeObstacle.LANTERNEAU, 0.50),
    (TypeObstacle.ACROTERE, 0.35),
    (TypeObstacle.JOINT_DILATATION, 0.10),
    (TypeObstacle.MURET, 0.35),
    (TypeObstacle.ANTENNE, 0.50),
    (TypeObstacle.GARDE_CORPS, 0.30),
    (TypeObstacle.EVACUATION_EU, 0.30),
    (TypeObstacle.NATURE_INCONNUE, 0.50),
)

#: Dégagement PLANCHER imposé par la PROVENANCE (6 provenances).
#: Une cote douteuse ou devinée impose le traitement « nature inconnue ».
DEGAGEMENT_PAR_PROVENANCE = (
    (Provenance.RELEVE, 0.00),
    (Provenance.RELEVE_DOUTEUX, 0.50),
    (Provenance.DECLARE_CLIENT, 0.30),
    (Provenance.PLAN, 0.35),
    (Provenance.DEVINE, 0.50),
    (Provenance.ECARTE, 0.00),
)

#: Provenances dont la géométrie peut entrer dans un compte ENGAGÉ.
PROVENANCES_ENGAGEABLES = frozenset({
    Provenance.RELEVE, Provenance.RELEVE_DOUTEUX, Provenance.DECLARE_CLIENT,
})

#: Motif NOMMÉ par provenance non engageable (jamais une phrase rédigée ailleurs).
_MOTIFS = (
    (Provenance.PLAN,
     "emprise issue du PLAN, jamais relevée sur site — à confirmer au relevé"),
    (Provenance.DEVINE,
     "emprise DEVINÉE (ni cotée ni relevée) — à confirmer au relevé"),
)


def _lire(table, cle, defaut=None):
    for k, v in table:
        if k is cle:
            return v
    if defaut is None:
        raise KeyError("clé absente de la table : %r" % (cle,))
    return defaut


def degagement_par_type(type_obstacle):
    """Dégagement par défaut du TYPE métier (mètres)."""
    return _lire(DEGAGEMENT_PAR_TYPE, type_obstacle)


def degagement_par_provenance(provenance):
    """Dégagement PLANCHER imposé par la provenance (mètres)."""
    return _lire(DEGAGEMENT_PAR_PROVENANCE, provenance)


def degagement_effectif(obstacle):
    """``(valeur, règle appliquée)`` — la règle est une PHRASE, pas un code.

    Ordre : une surcharge explicite gagne toujours ; sinon le maximum entre le
    défaut du type et le plancher de la provenance.
    """
    if obstacle.degagement_m is not None:
        return (obstacle.degagement_m,
                "surcharge explicite de l'obstacle %s : %.2f m"
                % (obstacle.repere, obstacle.degagement_m))
    d_type = degagement_par_type(obstacle.type_obstacle)
    d_prov = degagement_par_provenance(obstacle.provenance)
    if d_prov > d_type:
        return (d_prov,
                "provenance %s impose %.2f m (au-delà du défaut de type %s : %.2f m)"
                % (obstacle.provenance.value, d_prov,
                   obstacle.type_obstacle.value, d_type))
    return (d_type,
            "type %s : dégagement par défaut %.2f m (provenance %s : %.2f m)"
            % (obstacle.type_obstacle.value, d_type,
               obstacle.provenance.value, d_prov))


def appliquer_regles(obstacles):
    """Rend les obstacles avec ``degagement_m`` DÉRIVÉ et ``regle_appliquee`` écrite.

    Les obstacles ÉCARTÉS conservent leur géométrie (ils restent dessinables et
    chiffrables) mais leur dégagement est mis à 0 : ils ne bloquent plus rien.
    """
    sortie = []
    for o in obstacles:
        if o.provenance is Provenance.ECARTE:
            # Un motif d'écartement déjà écrit (« souche jamais relevée »,
            # « pan coupé confirmé absent ») est de l'information de dossier :
            # on la GARDE et on la complète, on ne l'écrase pas.
            standard = ("obstacle ÉCARTÉ : géométrie conservée, hors du "
                        "compte et sans dégagement")
            sortie.append(Obstacle(
                repere=o.repere, x0=o.x0, x1=o.x1, y0=o.y0, y1=o.y1,
                type_obstacle=o.type_obstacle, provenance=o.provenance,
                degagement_m=0.0, hauteur_m=o.hauteur_m,
                regle_appliquee=("%s — %s" % (o.regle_appliquee, standard)
                                 if o.regle_appliquee else standard)))
            continue
        valeur, regle = degagement_effectif(o)
        sortie.append(Obstacle(
            repere=o.repere, x0=o.x0, x1=o.x1, y0=o.y0, y1=o.y1,
            type_obstacle=o.type_obstacle, provenance=o.provenance,
            degagement_m=valeur, hauteur_m=o.hauteur_m, regle_appliquee=regle))
    return tuple(sortie)


def engageable(obstacles):
    """``(bool, motifs)`` — un compte n'est engageable qu'avec du RELEVÉ.

    Les obstacles ÉCARTÉS ne bloquent pas l'engagement : ils sont sortis du
    compte, donc ils ne le fragilisent pas.
    """
    motifs = []
    for o in obstacles:
        if o.provenance is Provenance.ECARTE:
            continue
        if o.provenance in PROVENANCES_ENGAGEABLES:
            continue
        motifs.append("%s — %s" % (o.repere, _lire(_MOTIFS, o.provenance,
                                                   "provenance non engageable")))
    return (not motifs, tuple(motifs))


def fusionner(intervalles):
    """Fusion d'intervalles bloqués (tolérance de FUSION nommée)."""
    sortie = []
    for a, b in sorted(intervalles):
        if b <= a:
            continue
        if sortie and a <= sortie[-1][1] + TOL_FUSION_M:
            sortie[-1] = (sortie[-1][0], max(sortie[-1][1], b))
        else:
            sortie.append((a, b))
    return tuple(sortie)


def intervalles_bloques(obstacles, y0, y1, borne_min, borne_max):
    """Intervalles [x] bloqués pour une bande transversale ``[y0, y1]``.

    Un obstacle ÉCARTÉ ou sans dégagement dérivé ne bloque rien : appeler
    ``appliquer_regles`` en amont est OBLIGATOIRE (sinon le moteur devinerait).
    """
    bruts = []
    for o in obstacles:
        if o.provenance is Provenance.ECARTE:
            continue
        c = o.degagement_m
        if c is None:
            raise ValueError(
                "obstacle %s sans dégagement dérivé : appeler "
                "obstacles.appliquer_regles() avant le comptage" % o.repere)
        # Tolérance de LONGUEUR obligatoire : ``20.35 + 0.30`` vaut
        # 20.650000000000002 en binaire, si bien qu'un obstacle dont le
        # dégagement AFFLEURE la rangée bloquerait une bande entière sans
        # qu'aucune cote n'ait bougé. Le moteur historique portait déjà ce
        # ``1e-9`` — l'oublier coûtait 36 modules sur l'aile L.
        if o.y1 + c <= y0 + TOL_LONGUEUR_M or o.y0 - c >= y1 - TOL_LONGUEUR_M:
            continue
        bruts.append((max(borne_min, o.x0 - c), min(borne_max, o.x1 + c)))
    return fusionner(bruts)
