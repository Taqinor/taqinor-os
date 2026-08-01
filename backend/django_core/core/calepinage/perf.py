# -*- coding: utf-8 -*-
"""AOF48 — coût de calcul : points de rupture, mémoïsation, budget, contrat.

Le coût réel d'une étude n'est pas UN DP : c'est
``N_surfaces × N_variantes × N_sensibilités × N_marches × N_recommandations``,
chacun rejouant un DP complet. Un site à 5 bâtiments et 3 variantes en fait
plusieurs centaines — et l'UX « choix maximum » est inutilisable si un tiroir
coûte 4 s par clic. Trois leviers, dans cet ordre d'efficacité mesurée :

1. **Mémoïsation** (``moteur``) — les sensibilités, les marches d'échelle et
   les recommandations rejouent MASSIVEMENT les mêmes rangées ; le cache LRU
   les rend gratuites à partir du deuxième appel ;
2. **Points de rupture fermés par chaînage** (ici) — entre deux ruptures une
   rangée voit les mêmes obstacles ; le jeu de positions utiles est le
   voisinage des ruptures, FERMÉ par les enchaînements « rangée + allée » (une
   rangée optimale est soit calée sur une rupture, soit collée à la
   précédente). Le jeu n'est adopté que s'il est PLUS PETIT que la grille :
   avec deux kits, la fermeture peut coûter plus cher que le balayage, et le
   moteur ne doit jamais ralentir pour faire joli ;
3. **Budget** — ``estimer_cout`` chiffre le travail AVANT de le lancer et dit
   à l'appelant s'il doit répondre en synchrone ou passer en tâche de fond.

Les comptes ne changent JAMAIS : ``positions_utiles`` rend un jeu STRICTEMENT
équivalent au balayage au centimètre, et le test le vérifie sur les 3 jeux.
"""

from dataclasses import dataclass

from core.calepinage.moteur import (
    info_cache,
    positions_de_rupture,
    vider_cache,
)
from core.calepinage.optimum import optimiser, positions_grille
from core.calepinage.units import TOL_LONGUEUR_M

__all__ = [
    "CONTRAT_PERFORMANCE", "BudgetCalcul", "CoutEstime", "positions_utiles",
    "optimiser_economique", "estimer_cout", "caper", "vider_cache",
    "info_cache",
]

#: CONTRAT DE PERFORMANCE écrit pour la lane d'interface (AOF48).
#: Il n'est pas décoratif : c'est lui qui dit à l'écran quand basculer en
#: asynchrone plutôt que de faire attendre l'utilisateur devant un tiroir.
CONTRAT_PERFORMANCE = (
    ("apercu_ms", 500,
     "un aperçu de tiroir (impact chiffré d'un paramètre) doit rendre en "
     "moins de 500 ms — sinon l'atelier de variantes est inutilisable"),
    ("calcul_lourd_ms", 2000,
     "au-delà de 2 s estimées, le calcul part en tâche de fond suivie "
     "(core.jobs) et l'écran affiche une progression, jamais un gel"),
    ("etude_complete_ms", 2000,
     "plan + 6 sensibilités + échelle d'un bâtiment : sous 2 s sur le runner "
     "d'intégration continue"),
    ("plafond_recommandations", 12,
     "au plus 12 recommandations CALCULÉES par appel : chacune rejoue le "
     "moteur sur une entrée patchée"),
)


@dataclass(frozen=True)
class BudgetCalcul:
    """Bornes de calcul d'un appel — immuables, passées en argument."""

    seuil_synchrone_ms: float = 2000.0
    plafond_recommandations: int = 12
    plafond_sensibilites: int = 12
    #: coût unitaire mesuré d'un comptage de rangée (mémoïsé exclu)
    cout_rangee_ms: float = 0.06


@dataclass(frozen=True)
class CoutEstime:
    """Ce que va coûter un calcul, AVANT de le lancer."""

    positions: int
    kits: int
    variantes: int
    appels: int
    millisecondes: float
    synchrone: bool
    motif: str = ""


def positions_utiles(surface, parametres, obstacles=(), zones=()):
    """Positions de rangée candidates, ÉQUIVALENTES au balayage au centimètre.

    Construction : les points de rupture (où l'ensemble bloquant change), plus
    leur voisinage immédiat au pas de recherche (une classe ouverte à gauche
    n'est atteignable qu'un cran après sa borne), le tout FERMÉ par chaînage
    « position + emprise + allée » pour toutes les combinaisons de kits — car
    une rangée optimale est soit calée sur une rupture, soit collée à la
    précédente. Rend la GRILLE si la fermeture est plus coûteuse qu'elle.
    """
    ymin, ymax = surface.bornes_transversales_utiles()
    grille = positions_grille(ymin, ymax, parametres.pas_recherche_m)
    ruptures = positions_de_rupture(surface, parametres.kits, obstacles, zones)
    if ruptures is None:
        return grille
    pas = parametres.pas_recherche_m
    increments = tuple(kit.emprise_transversale_m + parametres.allee_m
                       for kit in parametres.kits)
    base = set()
    for point in ruptures:
        for candidat in (point, point + pas):
            if ymin - TOL_LONGUEUR_M <= candidat <= ymax + TOL_LONGUEUR_M:
                base.add(max(ymin, candidat))
    # Au-delà de la moitié de la grille, la fermeture ne fait plus gagner
    # assez pour payer sa propre construction : on rend la grille tout de
    # suite (mesuré : avec deux kits, la fermeture COÛTE plus qu'elle ne
    # rapporte — le moteur ne doit jamais ralentir pour faire joli).
    plafond = max(1, len(grille) // 2)
    atteints = set(base)
    frontiere = set(base)
    while frontiere:
        suivants = set()
        for position in frontiere:
            for increment in increments:
                candidat = position + increment
                if candidat > ymax + TOL_LONGUEUR_M:
                    continue
                if candidat not in atteints and candidat not in suivants:
                    suivants.add(candidat)
                    if len(atteints) + len(suivants) > plafond:
                        return grille
        atteints |= suivants
        frontiere = suivants
    return tuple(sorted(atteints))


def optimiser_economique(surface, parametres, obstacles=(), zones=(),
                         politique=None):
    """``optimiser`` sur le jeu de positions utiles — MÊME résultat, moins cher."""
    return optimiser(surface, parametres, obstacles, zones, politique,
                     positions=positions_utiles(surface, parametres, obstacles,
                                                zones))


def estimer_cout(surface, parametres, obstacles=(), zones=(), variantes=1,
                 budget=None):
    """Chiffre le travail AVANT de le lancer et pilote la bascule asynchrone."""
    budget = budget or BudgetCalcul()
    positions = positions_utiles(surface, parametres, obstacles, zones)
    appels = len(positions) * len(parametres.kits) * max(1, variantes)
    millisecondes = appels * budget.cout_rangee_ms
    synchrone = millisecondes <= budget.seuil_synchrone_ms
    motif = ("%d positions × %d kits × %d variantes = %d comptages estimés à "
             "%.0f ms — %s" % (len(positions), len(parametres.kits),
                               max(1, variantes), appels, millisecondes,
                               "synchrone" if synchrone
                               else "tâche de fond suivie"))
    return CoutEstime(positions=len(positions), kits=len(parametres.kits),
                      variantes=max(1, variantes), appels=appels,
                      millisecondes=millisecondes, synchrone=synchrone,
                      motif=motif)


def caper(sequence, plafond):
    """Cape une liste de propositions — le moteur ne calcule jamais sans borne."""
    if plafond < 0:
        raise ValueError("plafond négatif")
    return tuple(sequence)[:plafond]
