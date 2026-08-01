# -*- coding: utf-8 -*-
"""AOF47 — mode de pose « rangées uniformes à phase balayée » (moteur v1).

Sans ce mode, l'échelle de décomposition d'AOF53 serait INEXÉCUTABLE : la
marche A de l'arc vaut 112 et l'école publie une variante « uniforme 0,60 »
d'information — or ces deux chiffres sortent du moteur v1
(``calepinage.rows_for`` / ``best_phase``), un mode que le DP à rangées
explicites ne sait pas simuler. Le récit « ancien → aujourd'hui » serait alors
invérifiable, donc invendable.

Le mode est ici de PREMIÈRE CLASSE, partageant compteur, surfaces et
garde-fous avec le DP — mais il porte ``Preuve.methode='heuristique_bornee'``,
si bien que le mot « prouvé » y reste STRUCTURELLEMENT hors de portée : les
rangées sont contraintes à un pas constant, rien ne démontre qu'aucun autre
jeu ne fait mieux. Et il ne peut, par construction, jamais battre le DP (le DP
explore un sur-ensemble) : un test de monotonie le verrouille.
"""

from core.calepinage.moteur import compter_plan
from core.calepinage.optimum import ResultatOptimum
from core.calepinage.types import MethodePreuve, Preuve
from core.calepinage.units import PAS_PHASE_DEFAUT_M, TOL_LONGUEUR_M, nb_entier

__all__ = [
    "nb_rangees", "jeu_de_rangees", "jeu_maximal", "compter_uniforme",
    "balayer_phase",
]


def nb_rangees(ymin, ymax, emprise, allee):
    """``int((largeur - 2×rive + allée) // (emprise + allée))`` du moteur v1."""
    if emprise + allee <= 0:
        return 0
    return nb_entier((ymax - ymin) + allee, emprise + allee)


def jeu_de_rangees(surface, kit, allee, phase=0.0):
    """Positions des rangées uniformes, décalées de ``phase``."""
    ymin, ymax = surface.bornes_transversales_utiles()
    emprise = kit.emprise_transversale_m
    n = nb_rangees(ymin, ymax, emprise, allee)
    positions = []
    for i in range(n):
        y0 = ymin + phase + i * (emprise + allee)
        if y0 + emprise > ymax + TOL_LONGUEUR_M:
            continue
        positions.append(y0)
    return tuple(positions)


def jeu_maximal(surface, kit, allee):
    """Décalage MAXIMAL admissible (le ``slack`` du moteur v1)."""
    ymin, ymax = surface.bornes_transversales_utiles()
    emprise = kit.emprise_transversale_m
    n = nb_rangees(ymin, ymax, emprise, allee)
    if n <= 0:
        return 0.0
    return max(0.0, (ymax - ymin) - (n * emprise + (n - 1) * allee))


def compter_uniforme(surface, kit, obstacles=(), zones=(), allee=0.60,
                     phase=0.0):
    """Compte d'un jeu uniforme à phase donnée — MÊME compteur que le DP."""
    rangees = jeu_de_rangees(surface, kit, allee, phase)
    return compter_plan(surface, tuple((y0, kit) for y0 in rangees),
                        obstacles, zones)


def balayer_phase(surface, parametres, obstacles=(), zones=(), allee=None,
                  pas_phase=PAS_PHASE_DEFAUT_M, borne_superieure=None):
    """Balayage de phase du moteur v1, sur chaque kit déclaré.

    Rend un ``ResultatOptimum`` dont la preuve est HEURISTIQUE BORNÉE : le
    balayage explore un sous-ensemble strict des plans, il ne prouve rien.
    """
    if pas_phase <= 0:
        raise ValueError("pas de balayage de phase strictement positif")
    allee = parametres.allee_m if allee is None else allee
    meilleur_plan = None
    meilleur_kit = None
    for kit in parametres.kits:
        maximal = jeu_maximal(surface, kit, allee)
        phase = 0.0
        while phase <= maximal + TOL_LONGUEUR_M:
            plan = compter_uniforme(surface, kit, obstacles, zones, allee,
                                    phase)
            if meilleur_plan is None or plan.modules > meilleur_plan.modules:
                meilleur_plan, meilleur_kit = plan, kit
            phase += pas_phase
    if meilleur_plan is None:
        meilleur_plan = compter_plan(surface, (), obstacles, zones)
        meilleur_kit = parametres.kits[0]
    preuve = Preuve(methode=MethodePreuve.HEURISTIQUE_BORNEE,
                    pas_recherche_m=pas_phase,
                    compte_retenu=meilleur_plan.modules,
                    compte_optimal=None,
                    borne_superieure=borne_superieure)
    return ResultatOptimum(
        plan=meilleur_plan,
        rangees=tuple((r.y0, meilleur_kit.code)
                      for r in meilleur_plan.rangees),
        preuve=preuve,
        ecart_a_l_optimum=(0 if borne_superieure is None
                           else borne_superieure - meilleur_plan.modules))
