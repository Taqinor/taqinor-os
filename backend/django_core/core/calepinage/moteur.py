# -*- coding: utf-8 -*-
"""AOF42 — le COMPTEUR générique : chemin de code A, qui ne pose RIEN.

Le moteur répond à une seule question : « combien de modules tiennent ? ». Il
ne construit aucune table, ne connaît pas la forme du toit (il interroge la
``Surface``) et **n'importe JAMAIS ``poseur``**. Le poseur, symétriquement, ne
compte rien. Deux chemins de code indépendants qui doivent tomber d'accord :
c'est l'invariant commercial le plus précieux du dépôt, celui qui autorise à
écrire « prouvé » à un maître d'ouvrage. Un test échoue si l'un importe
l'autre.

Ordre de traitement d'une rangée, identique pour toutes les surfaces :

1. la ``Surface`` rend la (ou les) étendue(s) posable(s) de la bande ;
2. les COUPURES (murets, changements de niveau) la découpent ;
3. les RIVES d'extrémité s'appliquent à CHAQUE tronçon ;
4. obstacles et zones retirent leurs intervalles bloqués ;
5. le pas de pose — fourni par la Surface, corrigé sur l'arc — compte.
"""

from core.calepinage.obstacles import fusionner, intervalles_bloques
from core.calepinage.types import Plan, Rangee
from core.calepinage.units import TOL_LONGUEUR_M, nb_entier
from core.calepinage.zones import intervalles_bloques_zones

__all__ = [
    "bandes_de_rangee", "segments_libres", "compter_troncon",
    "compter_rangee", "compter_plan", "capacite_theorique",
]


def bandes_de_rangee(surface, y0, kit):
    """Étendues ``x`` posables par une rangée de ``kit`` placée à ``y0``.

    Les surfaces qui savent rendre PLUSIEURS intervalles (polygone à trou,
    contour en U) exposent ``bandes()`` ; les autres n'ont que le contrat
    scalaire ``bande()``.
    """
    emprise = kit.emprise_transversale_m
    multiple = getattr(surface, "bandes", None)
    if multiple is not None:
        return tuple(multiple(y0, emprise))
    bornes = surface.bande(y0, emprise)
    return (bornes,) if bornes else ()


def segments_libres(surface, y0, kit, obstacles=(), zones=()):
    """Tronçons LIBRES d'une rangée, dégagements et rives appliqués."""
    emprise = kit.emprise_transversale_m
    y1 = y0 + emprise
    libres = []
    for bande in bandes_de_rangee(surface, y0, kit):
        for brut in surface.troncons_entre_coupures(bande):
            debut, fin = surface.bornes_utiles(brut)
            if fin - debut <= TOL_LONGUEUR_M:
                continue
            bloques = fusionner(
                tuple(intervalles_bloques(obstacles, y0, y1, debut, fin))
                + tuple(intervalles_bloques_zones(zones, y0, y1, debut, fin)))
            courant = debut
            for a, b in bloques:
                if a > courant + TOL_LONGUEUR_M:
                    libres.append((courant, min(a, fin)))
                courant = max(courant, b)
            if courant < fin - TOL_LONGUEUR_M:
                libres.append((courant, fin))
    return tuple((a, b) for a, b in libres if b - a > TOL_LONGUEUR_M)


def compter_troncon(longueur, pas, modules_par_pas):
    """Modules tenant dans un tronçon libre — la seule division du moteur."""
    return modules_par_pas * nb_entier(longueur, pas)


def compter_rangee(surface, y0, kit, obstacles=(), zones=()):
    """``Rangee`` complète : tronçons occupés + modules, AUCUNE table."""
    pas = surface.pas_de_pose(kit, y0)
    troncons = segments_libres(surface, y0, kit, obstacles, zones)
    modules = sum(compter_troncon(b - a, pas, kit.modules_par_pas)
                  for a, b in troncons)
    return Rangee(y0=y0, kit_code=kit.code,
                  emprise_m=kit.emprise_transversale_m,
                  troncons=troncons, modules=modules,
                  surface_repere=surface.repere)


def compter_plan(surface, rangees, obstacles=(), zones=()):
    """``Plan`` d'un jeu ``((y0, kit), …)`` — le total est une PROPRIÉTÉ."""
    posees = tuple(compter_rangee(surface, y0, kit, obstacles, zones)
                   for y0, kit in rangees)
    return Plan(surface_repere=surface.repere, rangees=posees,
                kit_codes=tuple(sorted({kit.code for _y0, kit in rangees})))


def capacite_theorique(surface, kit, obstacles=(), zones=()):
    """BORNE SUPÉRIEURE grossière : rangées jointives, sans allée.

    Elle ne prétend rien d'autre que borner — elle sert à qualifier une
    méthode heuristique, jamais à publier un « maximum » commercial.
    """
    ymin, ymax = surface.bornes_transversales_utiles()
    emprise = kit.emprise_transversale_m
    if emprise <= 0:
        return 0
    total = 0
    y0 = ymin
    while y0 + emprise <= ymax + TOL_LONGUEUR_M:
        total += compter_rangee(surface, y0, kit, obstacles, zones).modules
        y0 += emprise
    return total
