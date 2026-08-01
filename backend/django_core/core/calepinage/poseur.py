# -*- coding: utf-8 -*-
"""AOF43 — le POSEUR : chemin de code B, qui ne compte RIEN.

Le poseur pose des tables et rend leur GÉOMÉTRIE. Il ne renvoie aucun total et
**n'importe JAMAIS ``moteur``**. C'est délibérément un SECOND algorithme, pas
une réécriture du premier :

* le compteur soustrait des INTERVALLES bloqués puis divise chaque tronçon
  libre par le pas ;
* le poseur avance emplacement par emplacement et teste, pour CHAQUE table, la
  collision RECTANGLE contre RECTANGLE avec chaque obstacle dilaté de son
  dégagement ; en cas de collision il saute derrière l'obstacle et reprend.

Deux chemins indépendants qui doivent tomber d'accord au module près
(``2 × len(tables) == compte``) : c'est cet accord — et lui seul — qui autorise
à écrire « dessiné = compté » sur une planche remise à un maître d'ouvrage. Un
seul chemin de code, aussi soigné soit-il, ne prouve rien.
"""

from core.calepinage.geometrie import rectangles_se_croisent
from core.calepinage.types import Table
from core.calepinage.units import TOL_LONGUEUR_M
from core.calepinage.zones import NATURES_BLOQUANTES, sommets_decales, x_extent_dans_bande

__all__ = ["poser_rangee", "poser_plan", "obstacles_dilates"]


def obstacles_dilates(obstacles, zones=()):
    """Rectangles ``(x0, x1, y0, y1, repère)`` DILATÉS de leur dégagement.

    Le poseur ne fusionne rien : il garde les obstacles séparés et les teste un
    par un. C'est plus lent que le compteur, et c'est le prix de
    l'indépendance des deux chemins.
    """
    rectangles = []
    for o in obstacles:
        if o.provenance.value == "ECARTE":
            continue
        c = o.degagement_m
        if c is None:
            raise ValueError(
                "obstacle %s sans dégagement dérivé : appeler "
                "obstacles.appliquer_regles() avant la pose" % o.repere)
        rectangles.append((o.x0 - c, o.x1 + c, o.y0 - c, o.y1 + c, o.repere))
    for z in zones:
        if z.nature not in NATURES_BLOQUANTES:
            continue
        sommets = sommets_decales(z.sommets, z.retrait_m)
        ys = [p[1] for p in sommets]
        xs = [p[0] for p in sommets]
        rectangles.append((min(xs), max(xs), min(ys), max(ys), z.repere))
    return tuple(rectangles)


def _bandes(surface, y0, kit):
    emprise = kit.emprise_transversale_m
    multiple = getattr(surface, "bandes", None)
    if multiple is not None:
        return tuple(multiple(y0, emprise))
    bornes = surface.bande(y0, emprise)
    return (bornes,) if bornes else ()


def _collision(rectangles, x0, x1, y0, y1, zones_polygonales):
    """Repère du premier obstacle heurté et fin de son emprise dilatée."""
    fin = None
    touche = ""
    for rx0, rx1, ry0, ry1, repere in rectangles:
        if rectangles_se_croisent((x0, x1, y0, y1), (rx0, rx1, ry0, ry1)):
            if fin is None or rx1 > fin:
                fin, touche = rx1, repere
    for sommets, repere in zones_polygonales:
        extent = x_extent_dans_bande(sommets, y0, y1)
        if extent is None:
            continue
        if extent[1] > x0 + TOL_LONGUEUR_M and extent[0] < x1 - TOL_LONGUEUR_M:
            if fin is None or extent[1] > fin:
                fin, touche = extent[1], repere
    return fin, touche


def poser_rangee(surface, y0, kit, obstacles=(), zones=()):
    """Tables POSÉES sur une rangée — géométrie seule, aucun total."""
    emprise = kit.emprise_transversale_m
    y1 = y0 + emprise
    pas = surface.pas_de_pose(kit, y0)
    longueur_table = kit.cote_le_long_rangee_m
    rectangles = obstacles_dilates(obstacles, ())
    zones_polygonales = tuple(
        (sommets_decales(z.sommets, z.retrait_m), z.repere)
        for z in zones if z.nature in NATURES_BLOQUANTES)
    polygone_de = getattr(surface, "polygone_table", None)

    posees = []
    for bande in _bandes(surface, y0, kit):
        for brut in surface.troncons_entre_coupures(bande):
            debut, fin_troncon = surface.bornes_utiles(brut)
            curseur = debut
            while curseur + pas <= fin_troncon + TOL_LONGUEUR_M:
                heurt, _repere = _collision(rectangles, curseur, curseur + pas,
                                            y0, y1, zones_polygonales)
                if heurt is not None:
                    curseur = max(heurt, curseur + TOL_LONGUEUR_M)
                    continue
                centre = curseur + pas / 2.0
                x0 = centre - longueur_table / 2.0
                x1 = centre + longueur_table / 2.0
                polygone = (tuple(polygone_de(x0, x1, y0, y1))
                            if polygone_de is not None else
                            ((x0, y0), (x1, y0), (x1, y1), (x0, y1)))
                posees.append(Table(x0=x0, x1=x1, y0=y0, y1=y1,
                                    kit_code=kit.code,
                                    surface_repere=surface.repere,
                                    polygone=polygone, pas_m=pas))
                curseur += pas
    return tuple(posees)


def poser_plan(surface, rangees, obstacles=(), zones=()):
    """Tables de TOUTES les rangées ``((y0, kit), …)`` — toujours aucun total."""
    posees = []
    for y0, kit in rangees:
        posees.extend(poser_rangee(surface, y0, kit, obstacles, zones))
    return tuple(posees)
