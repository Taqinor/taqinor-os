# -*- coding: utf-8 -*-
"""AOF49 — marges de chantier et DÉPARTAGE automatique des optima.

Constat mesuré sur le seul segment S3 de l'arc : **766 788 jeux de rangées
atteignent l'optimum de 44**. Un optimum calé au millimètre est sans valeur sur
un chantier — le moteur doit CHOISIR, et rendre un plan, pas une liste.

Deux métriques, calculées par rangée puis minimées sur le plan :

* **marge de tronçon** — ce qui RESTE d'un tronçon libre après ses k tables.
  Une marge de 2 mm veut dire qu'une cote relevée à 2 cm près fait tomber une
  table à l'exécution ;
* **marge de bande** — la distance entre une rangée et le dégagement de
  l'obstacle qu'elle ESQUIVE. Une bande calée au ras d'un caisson est un
  litige de chantier en puissance.

Seuils par défaut : 2 cm et 4 cm — les valeurs constatées sur la planche de
l'arc, que ses propres assertions vérifiaient déjà. Un plan sous seuil est
REFUSÉ en nommant la rangée fautive ; les marges sont publiées en CENTIMÈTRES
et imprimées sur la planche.
"""

from core.calepinage.moteur import segments_libres
from core.calepinage.types import Marges
from core.calepinage.units import (
    MARGE_BANDE_DEFAUT_M,
    MARGE_TRONCON_DEFAUT_M,
    TOL_LONGUEUR_M,
    en_cm,
    nb_entier,
)
from core.calepinage.zones import bonus_preference

__all__ = [
    "marges_du_plan", "valider_marges", "departager", "cle_de_departage",
]


def marges_du_plan(surface, rangees, obstacles=(), zones=()):
    """``Marges`` d'un plan ``((y0, kit), …)`` — minima, et QUI les porte."""
    troncon_min = None
    bande_min = None
    rangee_critique = ""
    obstacle_critique = ""
    for y0, kit in rangees:
        y1 = y0 + kit.emprise_transversale_m
        pas = surface.pas_de_pose(kit, y0)
        for a, b in segments_libres(surface, y0, kit, obstacles, zones):
            k = nb_entier(b - a, pas)
            if not k:
                continue
            reste = (b - a) - k * pas
            if troncon_min is None or reste < troncon_min:
                troncon_min = reste
                rangee_critique = "y0=%.3f (%s)" % (y0, kit.code)
        for o in obstacles:
            c = o.degagement_m or 0.0
            if not (o.y1 + c <= y0 + TOL_LONGUEUR_M
                    or o.y0 - c >= y1 - TOL_LONGUEUR_M):
                continue                       # obstacle TRAVERSÉ, pas esquivé
            ecart = min(abs(y0 - (o.y1 + c)), abs((o.y0 - c) - y1))
            if bande_min is None or ecart < bande_min:
                bande_min = ecart
                obstacle_critique = o.repere
    return Marges(troncon_min_m=0.0 if troncon_min is None else troncon_min,
                  bande_min_m=0.0 if bande_min is None else bande_min,
                  rangee_critique=rangee_critique,
                  obstacle_critique=obstacle_critique)


def valider_marges(marges, seuil_troncon_m=MARGE_TRONCON_DEFAUT_M,
                   seuil_bande_m=MARGE_BANDE_DEFAUT_M):
    """``(bool, motifs)`` — un plan au ras est REFUSÉ, en nommant le fautif."""
    motifs = []
    if marges.troncon_min_m < seuil_troncon_m - TOL_LONGUEUR_M:
        motifs.append(
            "marge de tronçon %.1f cm < seuil %.1f cm — rangée %s au ras"
            % (en_cm(marges.troncon_min_m), en_cm(seuil_troncon_m),
               marges.rangee_critique or "(non identifiée)"))
    if marges.bande_min_m < seuil_bande_m - TOL_LONGUEUR_M:
        motifs.append(
            "marge de bande %.1f cm < seuil %.1f cm — bande au ras de "
            "l'obstacle %s" % (en_cm(marges.bande_min_m), en_cm(seuil_bande_m),
                               marges.obstacle_critique or "(non identifié)"))
    return (not motifs, tuple(motifs))


def cle_de_departage(surface, rangees, obstacles=(), zones=()):
    """Clé de tri TOTALE et déterministe entre plans de compte IDENTIQUE.

    Ordre : marge de tronçon, puis marge de bande, puis bonus de zone
    PRÉFÉRÉE (qui ne change jamais un compte — il ne sert QUE là), puis les
    positions de rangée. La dernière composante garantit qu'aucun ex æquo ne
    subsiste : deux exécutions rendent le MÊME plan, sur Windows comme sur
    Linux.
    """
    marges = marges_du_plan(surface, rangees, obstacles, zones)
    posees = tuple(
        type("_R", (), {"y0": y0, "y1": y0 + kit.emprise_transversale_m})()
        for y0, kit in rangees)
    return (round(marges.troncon_min_m, 6), round(marges.bande_min_m, 6),
            bonus_preference(zones, posees),
            tuple(-round(y0, 6) for y0, _kit in rangees))


def departager(surface, candidats, obstacles=(), zones=()):
    """Choisit UN plan parmi des candidats — jamais une liste rendue à l'écran.

    Les candidats de compte inférieur sont écartés d'abord : le départage ne
    sacrifie JAMAIS un module.
    """
    candidats = tuple(candidats)
    if not candidats:
        raise ValueError("aucun plan candidat à départager")
    comptes = []
    for rangees in candidats:
        from core.calepinage.moteur import compter_plan

        comptes.append(compter_plan(surface, rangees, obstacles,
                                    zones).modules)
    meilleur = max(comptes)
    finalistes = [r for r, n in zip(candidats, comptes) if n == meilleur]
    return max(finalistes,
               key=lambda r: cle_de_departage(surface, r, obstacles, zones))
