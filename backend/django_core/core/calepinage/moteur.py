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

from functools import lru_cache

from core.calepinage.obstacles import fusionner, intervalles_bloques
from core.calepinage.types import Plan, Provenance, Rangee
from core.calepinage.units import TOL_LONGUEUR_M, nb_entier
from core.calepinage.zones import NATURES_BLOQUANTES, intervalles_bloques_zones

__all__ = [
    "bandes_de_rangee", "segments_libres", "compter_troncon",
    "compter_rangee", "compter_plan", "capacite_theorique",
    "positions_de_rupture", "pas_constant", "vider_cache", "info_cache",
    "TAILLE_CACHE_RANGEES",
]

#: Taille du cache LRU de ``compter_rangee`` (AOF48). Le vrai coût d'une étude
#: n'est pas UN DP mais N_variantes × N_sensibilités × N_marches, chacune
#: rejouant le même comptage de rangée sur des entrées IDENTIQUES.
TAILLE_CACHE_RANGEES = 200000


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


@lru_cache(maxsize=TAILLE_CACHE_RANGEES)
def _rangee_memoisee(surface, y0, kit, obstacles, zones):
    """Comptage MÉMOÏSÉ — surfaces, kits, obstacles et zones sont immuables.

    Le moteur reste PUR : le cache est une fonction de ses arguments, jamais
    un état de configuration. Deux entrées identiques rendent le même objet,
    y compris entre deux tâches Celery.
    """
    pas = surface.pas_de_pose(kit, y0)
    troncons = segments_libres(surface, y0, kit, obstacles, zones)
    modules = sum(compter_troncon(b - a, pas, kit.modules_par_pas)
                  for a, b in troncons)
    return Rangee(y0=y0, kit_code=kit.code,
                  emprise_m=kit.emprise_transversale_m,
                  troncons=troncons, modules=modules,
                  surface_repere=surface.repere)


def compter_rangee(surface, y0, kit, obstacles=(), zones=()):
    """``Rangee`` complète : tronçons occupés + modules, AUCUNE table."""
    return _rangee_memoisee(surface, y0, kit, tuple(obstacles), tuple(zones))


def vider_cache():
    """Vide le cache de comptage (bancs de mesure, tests de performance)."""
    _rangee_memoisee.cache_clear()


def info_cache():
    """``CacheInfo`` du cache de comptage — lisible par ``perf.estimer_cout``."""
    return _rangee_memoisee.cache_info()


def pas_constant(surface, kit):
    """``True`` si le pas de pose ne dépend PAS de la position de rangée.

    Il l'est en géométrie plane et il ne l'est PAS sur l'arc (correction
    ``mod_l × R_ext / (R_int + y0)``). C'est ce qui décide si le balayage sur
    points de rupture est EXACT : sur une surface à pas variable, deux
    positions d'une même classe de blocage ne comptent pas pareil.
    """
    ymin, ymax = surface.bornes_transversales_utiles()
    return abs(surface.pas_de_pose(kit, ymin)
               - surface.pas_de_pose(kit, ymax)) <= TOL_LONGUEUR_M


def positions_de_rupture(surface, kits, obstacles=(), zones=()):
    """Positions de rangée où l'ensemble BLOQUANT change — et elles seules.

    Entre deux ruptures, la rangée voit exactement les mêmes obstacles, la
    même bande et les mêmes zones : son compte est constant. La position la
    plus PRÉCOCE de chaque classe domine (elle laisse au moins autant de place
    aux rangées suivantes), donc le DP restreint à ces positions rend le même
    optimum que le balayage aveugle au centimètre — en 100 fois moins d'appels.

    Rend ``None`` si une surface à pas VARIABLE rend le raccourci inexact.
    """
    ymin, ymax = surface.bornes_transversales_utiles()
    if not all(pas_constant(surface, kit) for kit in kits):
        return None
    emprises = tuple(kit.emprise_transversale_m for kit in kits)
    points = {ymin}
    for o in obstacles:
        if o.provenance is Provenance.ECARTE:
            continue
        c = o.degagement_m or 0.0
        points.add(o.y1 + c)
        for emprise in emprises:
            points.add(o.y0 - c - emprise)
    for z in zones:
        if z.nature not in NATURES_BLOQUANTES:
            continue
        ys = [p[1] for p in z.sommets]
        points.add(max(ys) + z.retrait_m)
        for emprise in emprises:
            points.add(min(ys) - z.retrait_m - emprise)
    for sommet in getattr(surface, "contour", ()) or ():
        points.add(sommet[1])
        for emprise in emprises:
            points.add(sommet[1] - emprise)
    for emprise in emprises:
        points.add(ymax - emprise)
    retenus = sorted(p for p in points
                     if ymin - TOL_LONGUEUR_M <= p <= ymax + TOL_LONGUEUR_M)
    return tuple(max(ymin, p) for p in retenus)


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
