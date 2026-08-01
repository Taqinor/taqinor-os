# -*- coding: utf-8 -*-
"""AOF36 — 4 natures de contour, chacune avec sa sémantique propre.

Un rectangle d'obstacle ne sait pas représenter une servitude POLYGONALE ni une
bande coupe-feu : les outils du marché (HelioScope modélise le *keepout* avec
retrait ET hauteur, PVcase génère les exclusions réglementaires en même temps
que l'ombrage) séparent depuis longtemps l'obstacle physique de la zone.

* ``ENVELOPPE``  — bord posable (le contour de la surface) ;
* ``INTERDITE``  — servitude, bande coupe-feu, ombre portée déclarée : la
  surface en est RETIRÉE, exactement comme un obstacle mais avec une forme
  quelconque ;
* ``RESERVEE``   — usage futur : retirée elle aussi, mais chiffrée à part (on
  publie ce qu'elle coûte, c'est un argument de négociation) ;
* ``PREFEREE``   — bonus DOUX servant UNIQUEMENT au départage entre plans
  DÉJÀ optimaux. Elle ne change JAMAIS un compte : le test le prouve.
"""

from core.calepinage.types import NatureZone
from core.calepinage.units import TOL_LONGUEUR_M

__all__ = [
    "NATURES_BLOQUANTES", "aire_polygone", "sommets_decales",
    "x_extent_dans_bande", "intervalles_bloques_zones", "aire_retiree",
    "bonus_preference",
]

#: Seules ces natures RETIRENT de la surface. ``PREFEREE`` n'y est pas — et
#: c'est le cœur de la tâche : un bonus doux ne peut pas coûter un module.
NATURES_BLOQUANTES = frozenset({NatureZone.INTERDITE, NatureZone.RESERVEE})


def aire_polygone(sommets):
    """Aire d'un polygone simple par la formule des lacets (toujours ≥ 0)."""
    n = len(sommets)
    if n < 3:
        return 0.0
    somme = 0.0
    for i in range(n):
        x0, y0 = sommets[i]
        x1, y1 = sommets[(i + 1) % n]
        somme += x0 * y1 - x1 * y0
    return abs(somme) / 2.0


def _centre(sommets):
    n = float(len(sommets))
    return (sum(p[0] for p in sommets) / n, sum(p[1] for p in sommets) / n)


def sommets_decales(sommets, retrait):
    """Polygone DILATÉ de ``retrait`` (approximation radiale depuis le centre).

    Le moteur n'embarque pas de *buffer* topologique (pas de shapely) : pour un
    retrait de quelques dizaines de centimètres sur des contours convexes de
    servitude, la dilatation radiale est conservatrice et suffit. Les cas fins
    (contour très concave) passent par un obstacle rectangulaire explicite.
    """
    if retrait <= 0:
        return tuple(sommets)
    cx, cy = _centre(sommets)
    sortie = []
    for x, y in sommets:
        dx, dy = x - cx, y - cy
        norme = (dx * dx + dy * dy) ** 0.5
        if norme <= TOL_LONGUEUR_M:
            sortie.append((x, y))
        else:
            sortie.append((x + retrait * dx / norme, y + retrait * dy / norme))
    return tuple(sortie)


def x_extent_dans_bande(sommets, y0, y1):
    """Étendue en ``x`` de l'intersection du polygone avec la bande ``[y0, y1]``.

    Rend ``None`` si le polygone ne touche pas la bande. La bande est le seul
    découpage dont le moteur a besoin : une rangée occupe exactement une bande.
    """
    if y1 < y0:
        y0, y1 = y1, y0
    xs = []
    n = len(sommets)
    for i in range(n):
        ax, ay = sommets[i]
        bx, by = sommets[(i + 1) % n]
        # sommet dans la bande
        if y0 - TOL_LONGUEUR_M <= ay <= y1 + TOL_LONGUEUR_M:
            xs.append(ax)
        # intersections de l'arête avec les deux droites de la bande
        for yc in (y0, y1):
            if (ay - yc) * (by - yc) < 0.0:
                t = (yc - ay) / (by - ay)
                xs.append(ax + t * (bx - ax))
    if not xs:
        return None
    return (min(xs), max(xs))


def intervalles_bloques_zones(zones, y0, y1, borne_min, borne_max):
    """Intervalles ``x`` bloqués par les zones RETIRANTES sur la bande donnée.

    Les zones ``ENVELOPPE`` (bord posable) et ``PREFEREE`` (bonus doux) ne
    bloquent rien — c'est ce que le test « une zone préférée ne change jamais
    un compte » verrouille.
    """
    bruts = []
    for z in zones:
        if z.nature not in NATURES_BLOQUANTES:
            continue
        sommets = sommets_decales(z.sommets, z.retrait_m)
        extent = x_extent_dans_bande(sommets, y0, y1)
        if extent is None:
            continue
        a, b = max(borne_min, extent[0]), min(borne_max, extent[1])
        if b > a:
            bruts.append((a, b))
    # fusion locale (même règle que les obstacles)
    sortie = []
    for a, b in sorted(bruts):
        if sortie and a <= sortie[-1][1]:
            sortie[-1] = (sortie[-1][0], max(sortie[-1][1], b))
        else:
            sortie.append((a, b))
    return tuple(sortie)


def aire_retiree(zones, nature=None):
    """Surface RETIRÉE par les zones (m²), chiffrable nature par nature."""
    total = 0.0
    for z in zones:
        if nature is not None and z.nature is not nature:
            continue
        if nature is None and z.nature not in NATURES_BLOQUANTES:
            continue
        total += aire_polygone(sommets_decales(z.sommets, z.retrait_m))
    return total


def bonus_preference(zones, rangees):
    """Score de DÉPARTAGE : nombre de rangées recouvrant une zone préférée.

    Ce score n'entre JAMAIS dans un compte de modules : il ne sert qu'à choisir
    entre deux plans qui comptent déjà pareil (``robustesse.departager``).
    """
    score = 0
    for z in zones:
        if z.nature is not NatureZone.PREFEREE:
            continue
        for r in rangees:
            if x_extent_dans_bande(z.sommets, r.y0, r.y1) is not None:
                score += 1
    return score
