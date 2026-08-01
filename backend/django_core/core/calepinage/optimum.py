# -*- coding: utf-8 -*-
"""AOF44 — UN SEUL DP exact, multi-kits, et une ``Preuve`` à vocabulaire VERROUILLÉ.

Les trois planches du dossier FRDISI contenaient TROIS implémentations
divergentes de la même récurrence — dont une (l'école) sans DP du tout, ses
rangées écrites en dur. Les fusionner supprime la divergence ; sinon chaque
nouvel appel d'offres ajoute un quatrième moteur de 40 ko.

La récurrence, unique, progresse sur l'axe transversal fourni par la Surface :

    best[i] = max( best[i+1],
                   max_kit( compte(y_i, kit) + best[idx(y_i + emprise + pas)] ) )

L'arc ne change QUE l'axe et le pas de pose ; le multi-segment est N DP
indépendants (les murets sont des coupures, gérées par la Surface).

**RISQUE COMMERCIAL N°1, traité ici.** Le DP n'est exact que sous l'hypothèse
« rangées parallèles à un axe unique, pas uniforme après chaque rangée ». Dès
qu'on ouvre l'orientation par zone, l'optimalité cesse d'être démontrée alors
que le code, lui, continue de tourner. C'est pourquoi ``Preuve`` porte la
MÉTHODE : « optimum prouvé » n'est ACCESSIBLE que si la méthode est exacte ET
que le compte retenu égale le compte optimal. Une heuristique ne rend jamais
que « meilleur plan trouvé + borne supérieure » — le mot est structurellement
hors de portée, pas laissé à la discipline du rédacteur.
"""

from dataclasses import dataclass
from typing import Tuple

from core.calepinage.moteur import compter_plan, compter_rangee
from core.calepinage.types import MethodePreuve, Plan, Preuve
from core.calepinage.units import TOL_LONGUEUR_M

__all__ = [
    "ResultatOptimum", "CAP_PLANS_OPTIMAUX", "optimiser", "evaluer_plan_impose",
    "positions_grille",
]

#: Au-delà, le nombre de plans optimaux n'a plus d'intérêt métier : on publie
#: « au moins CAP ». Sur le seul segment S3 de l'arc, 766 788 jeux de rangées
#: atteignent l'optimum — un optimum calé au millimètre est sans valeur sur
#: chantier, c'est ``robustesse.py`` qui doit ensuite CHOISIR.
CAP_PLANS_OPTIMAUX = 1000000


@dataclass(frozen=True)
class ResultatOptimum:
    """Plan retenu + preuve. Le compte n'est jamais recopié : il vit dans le plan."""

    plan: Plan
    rangees: Tuple[Tuple[float, str], ...]
    preuve: Preuve
    ecart_a_l_optimum: int = 0

    @property
    def modules(self):
        return self.plan.modules

    @property
    def optimal(self):
        return self.preuve.optimal


def positions_grille(ymin, ymax, pas):
    """Positions de rangée candidates, au pas de recherche (1 cm par défaut)."""
    if pas <= 0:
        raise ValueError("pas de recherche strictement positif")
    nb = int((ymax - ymin) / pas + 1e-9) + 1
    return tuple(ymin + i * pas for i in range(nb))


def _pas_apres(politique, parametres, kit, y0):
    """Espacement après une rangée — scalaire par défaut, POLITIQUE si fournie."""
    if politique is not None:
        return politique.pas_apres_rangee(kit, y0)
    return parametres.allee_m


def optimiser(surface, parametres, obstacles=(), zones=(), politique=None):
    """DP exact au pas de recherche, sur TOUS les kits déclarés.

    Rend le meilleur plan ET sa preuve. Aucune heuristique, aucun repli
    silencieux : si l'entrée sort du domaine d'exactitude, c'est l'appelant
    (``pose_uniforme``) qui déclare une autre méthode.
    """
    ymin, ymax = surface.bornes_transversales_utiles()
    grille = positions_grille(ymin, ymax, parametres.pas_recherche_m)
    n = len(grille)
    pas = parametres.pas_recherche_m

    def index_de(y):
        if y >= ymax - TOL_LONGUEUR_M:
            return n
        brut = int((y - ymin) / pas + 1.0 - 1e-9)
        return max(0, min(n, brut))

    meilleur = [0] * (n + 1)
    choix = [None] * (n + 1)
    combien = [1] * (n + 1)

    for i in range(n - 1, -1, -1):
        y0 = grille[i]
        meilleur[i] = meilleur[i + 1]
        choix[i] = None
        combien[i] = combien[i + 1]
        for kit in parametres.kits:
            emprise = kit.emprise_transversale_m
            if y0 + emprise > ymax + TOL_LONGUEUR_M:
                continue
            rangee = compter_rangee(surface, y0, kit, obstacles, zones)
            if rangee.modules <= 0:
                continue
            suivant = index_de(y0 + emprise
                               + _pas_apres(politique, parametres, kit, y0))
            valeur = rangee.modules + meilleur[suivant]
            if valeur > meilleur[i]:
                meilleur[i] = valeur
                choix[i] = (kit, suivant)
                combien[i] = combien[suivant]
            elif valeur == meilleur[i]:
                combien[i] = min(CAP_PLANS_OPTIMAUX,
                                 combien[i] + combien[suivant])

    retenues = []
    i = 0
    while i < n:
        if choix[i] is None:
            i += 1
            continue
        kit, suivant = choix[i]
        retenues.append((grille[i], kit))
        i = max(suivant, i + 1)

    plan = compter_plan(surface, tuple(retenues), obstacles, zones)
    preuve = Preuve(methode=MethodePreuve.DP_EXACT_1CM,
                    pas_recherche_m=pas,
                    compte_retenu=plan.modules,
                    compte_optimal=meilleur[0],
                    borne_superieure=meilleur[0],
                    nb_plans_optimaux=combien[0])
    return ResultatOptimum(
        plan=plan,
        rangees=tuple((y0, kit.code) for y0, kit in retenues),
        preuve=preuve,
        ecart_a_l_optimum=meilleur[0] - plan.modules)


def evaluer_plan_impose(surface, parametres, rangees, obstacles=(), zones=(),
                        politique=None, methode=MethodePreuve.IMPOSE_UTILISATEUR,
                        compte_optimal=None):
    """Évalue un plan IMPOSÉ (rangées fournies) et le situe face à l'optimum.

    C'est le seul chemin par lequel un plan choisi à la main entre dans le
    moteur : il en ressort avec ``optimal=False`` et l'ÉCART chiffré si
    quelqu'un a fait moins bien que le DP.
    """
    plan = compter_plan(surface, tuple(rangees), obstacles, zones)
    if compte_optimal is None:
        compte_optimal = optimiser(surface, parametres, obstacles, zones,
                                   politique).preuve.compte_optimal
    preuve = Preuve(methode=methode,
                    pas_recherche_m=parametres.pas_recherche_m,
                    compte_retenu=plan.modules,
                    compte_optimal=compte_optimal,
                    borne_superieure=compte_optimal)
    return ResultatOptimum(
        plan=plan,
        rangees=tuple((y0, kit.code) for y0, kit in rangees),
        preuve=preuve,
        ecart_a_l_optimum=compte_optimal - plan.modules)


def borne_superieure_kit(surface, kit, obstacles=(), zones=(),
                         pas_recherche=0.01):
    """Borne haute d'un kit : meilleure rangée × nombre de rangées possibles.

    Grossière ET honnête — elle sert à qualifier une méthode heuristique, pas
    à publier un maximum commercial.
    """
    ymin, ymax = surface.bornes_transversales_utiles()
    emprise = kit.emprise_transversale_m
    if emprise <= 0:
        return 0
    meilleure = 0
    for y0 in positions_grille(ymin, max(ymin, ymax - emprise), pas_recherche):
        meilleure = max(meilleure,
                        compter_rangee(surface, y0, kit, obstacles,
                                       zones).modules)
    nb = int((ymax - ymin) / emprise + TOL_LONGUEUR_M)
    return meilleure * nb
