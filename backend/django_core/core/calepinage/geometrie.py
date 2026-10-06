# -*- coding: utf-8 -*-
"""AOF39 — primitives géométriques du moteur, SANS shapely.

Le moteur reste un noyau pur (stdlib + numpy) : ajouter une dépendance
topologique pour découper un contour en L serait payer très cher un balayage
de 60 lignes. Tout ce dont le calepinage a besoin est ici :

* le contour d'une surface est un polygone simple, éventuellement CONCAVE,
  éventuellement percé de TROUS (patio, trémie) ;
* une rangée occupe une BANDE transversale ``[y0, y1]`` ; elle n'est posable
  que là où le contour couvre la bande ENTIÈRE ;
* le balayage rend l'ensemble des intervalles ``x`` ainsi couverts.

Constat dur qui justifie ce module : sur l'aile en L, une rangée qui reste à
l'ouest de l'aile descend d'un seul tenant de la barre dans l'aile. Découper
le L en deux rectangles indépendants ajoute deux rives à la jonction et coûte
des modules — le test d'AOF39 le PROUVE au lieu de le supposer.
"""

from core.calepinage.units import TOL_LONGUEUR_M
from core.calepinage.zones import aire_polygone

__all__ = [
    "aire_polygone", "boite_englobante", "normaliser_contour",
    "intervalles_a_y", "intersection_intervalles", "bandes_couvertes",
    "point_dans_polygone", "rectangles_se_croisent", "est_polygone_simple",
]


def normaliser_contour(sommets):
    """Retire un éventuel point de fermeture dupliqué et fige le contour."""
    pts = list(sommets)
    if len(pts) >= 2 and abs(pts[0][0] - pts[-1][0]) <= TOL_LONGUEUR_M \
            and abs(pts[0][1] - pts[-1][1]) <= TOL_LONGUEUR_M:
        pts = pts[:-1]
    if len(pts) < 3:
        raise ValueError("un contour compte au moins 3 sommets distincts")
    return tuple((float(x), float(y)) for x, y in pts)


def boite_englobante(sommets):
    """``(xmin, xmax, ymin, ymax)``."""
    xs = [p[0] for p in sommets]
    ys = [p[1] for p in sommets]
    return (min(xs), max(xs), min(ys), max(ys))


def _croisements(contour, y):
    """Abscisses ``x`` où la droite transversale ``y`` coupe le contour.

    Convention semi-ouverte ``ymin <= y < ymax`` : elle rend le balayage exact
    au passage d'un sommet (aucun double comptage, aucun trou fantôme).
    """
    xs = []
    n = len(contour)
    for i in range(n):
        ax, ay = contour[i]
        bx, by = contour[(i + 1) % n]
        if ay == by:
            continue
        bas, haut = (ay, by) if ay < by else (by, ay)
        if bas <= y < haut:
            t = (y - ay) / (by - ay)
            xs.append(ax + t * (bx - ax))
    return sorted(xs)


def intervalles_a_y(contour, trous, y):
    """Intervalles ``x`` INTÉRIEURS au contour (trous retirés) à l'ordonnée ``y``."""
    xs = _croisements(contour, y)
    pleins = tuple((xs[i], xs[i + 1]) for i in range(0, len(xs) - 1, 2))
    for trou in trous or ():
        troues = _croisements(trou, y)
        vides = [(troues[i], troues[i + 1]) for i in range(0, len(troues) - 1, 2)]
        for a, b in vides:
            reste = []
            for c, d in pleins:
                if b <= c or a >= d:
                    reste.append((c, d))
                    continue
                if c < a:
                    reste.append((c, a))
                if d > b:
                    reste.append((b, d))
            pleins = tuple(reste)
    return tuple((a, b) for a, b in pleins if b - a > TOL_LONGUEUR_M)


def intersection_intervalles(gauche, droite):
    """Intersection de deux familles d'intervalles triées."""
    sortie = []
    i = j = 0
    gauche = list(gauche)
    droite = list(droite)
    while i < len(gauche) and j < len(droite):
        a = max(gauche[i][0], droite[j][0])
        b = min(gauche[i][1], droite[j][1])
        if b - a > TOL_LONGUEUR_M:
            sortie.append((a, b))
        if gauche[i][1] < droite[j][1]:
            i += 1
        else:
            j += 1
    return tuple(sortie)


def bandes_couvertes(contour, trous, y0, y1):
    """Intervalles ``x`` où le contour couvre la bande ``[y0, y1]`` ENTIÈRE.

    Méthode : les bornes des intervalles varient LINÉAIREMENT en ``y`` entre
    deux ordonnées critiques (sommet du contour ou d'un trou). Il suffit donc
    d'intersecter les familles d'intervalles évaluées aux ordonnées critiques
    — plus un point intérieur par sous-bande, qui rend le balayage exact sur
    les contours à angles droits (tous les toits du dossier FRDISI) et précis
    au micromètre ailleurs.
    """
    if y1 < y0:
        y0, y1 = y1, y0
    critiques = {y0, y1}
    for poly in (contour,) + tuple(trous or ()):
        for _x, y in poly:
            if y0 < y < y1:
                critiques.add(y)
    ordonnees = sorted(critiques)
    echantillons = []
    for a, b in zip(ordonnees, ordonnees[1:]):
        eps = min(1e-6, (b - a) / 1000.0)
        echantillons.extend([a + eps, (a + b) / 2.0, b - eps])
    if not echantillons:                       # bande d'épaisseur nulle
        echantillons = [y0]
    courant = None
    for y in echantillons:
        familles = intervalles_a_y(contour, trous, y)
        courant = familles if courant is None else \
            intersection_intervalles(courant, familles)
        if not courant:
            return ()
    return courant


def point_dans_polygone(point, contour, trous=()):
    """Test d'appartenance (règle pair-impair), trous compris."""
    x, y = point
    for a, b in intervalles_a_y(contour, trous, y):
        if a - TOL_LONGUEUR_M <= x <= b + TOL_LONGUEUR_M:
            return True
    return False


def rectangles_se_croisent(a, b, tolerance=0.0):
    """``a`` et ``b`` = ``(x0, x1, y0, y1)`` — recouvrement STRICT."""
    return not (a[1] <= b[0] + tolerance or b[1] <= a[0] + tolerance
                or a[3] <= b[2] + tolerance or b[3] <= a[2] + tolerance)


def _orientation(a, b, c):
    """Signe du produit vectoriel (b - a) × (c - a) : -1, 0 ou 1."""
    valeur = (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])
    if valeur > 0:
        return 1
    if valeur < 0:
        return -1
    return 0


def _sur_segment(a, b, c):
    """``c`` (colinéaire à ``ab``) tombe-t-il dans la boîte du segment ?"""
    return (min(a[0], b[0]) <= c[0] <= max(a[0], b[0])
            and min(a[1], b[1]) <= c[1] <= max(a[1], b[1]))


def _segments_se_touchent(p1, p2, p3, p4):
    """Les segments fermés ``p1p2`` et ``p3p4`` ont-ils un point commun ?"""
    o1 = _orientation(p1, p2, p3)
    o2 = _orientation(p1, p2, p4)
    o3 = _orientation(p3, p4, p1)
    o4 = _orientation(p3, p4, p2)
    if o1 != o2 and o3 != o4 and 0 not in (o1, o2, o3, o4):
        return True
    return ((o1 == 0 and _sur_segment(p1, p2, p3))
            or (o2 == 0 and _sur_segment(p1, p2, p4))
            or (o3 == 0 and _sur_segment(p3, p4, p1))
            or (o4 == 0 and _sur_segment(p3, p4, p2)))


def est_polygone_simple(contour):
    """ACAL76 — le contour est-il un polygone SIMPLE (aucun côté ne se croise) ?

    L'invariant du module (« le contour d'une surface est un polygone
    simple », en tête de fichier) n'était jamais vérifié : un « nœud
    papillon » ``[[0,0],[10,6],[10,0],[0,6]]`` a une aire signée nulle et
    fausse aire, pavage et kWc. Fonction PURE, sans tolérance inventée :

    * deux côtés NON adjacents qui se touchent (croisement ou contact) ⇒
      ``False`` ;
    * deux côtés adjacents qui reviennent l'un sur l'autre (pointe
      colinéaire repliée) ⇒ ``False`` ;
    * un point de fermeture dupliqué est ignoré ; moins de 4 sommets
      distincts ne peuvent pas se croiser ⇒ ``True`` (le minimum de sommets
      est une autre règle, portée par le schéma ou par
      :func:`normaliser_contour`).
    """
    pts = [(float(p[0]), float(p[1])) for p in contour]
    if len(pts) >= 2 and pts[0] == pts[-1]:
        pts = pts[:-1]
    n = len(pts)
    if n < 3:
        return True
    cotes = [(pts[i], pts[(i + 1) % n]) for i in range(n)]
    for i in range(n):
        a, b = cotes[i]
        for j in range(i + 1, n):
            c, d = cotes[j]
            adjacents = j == i + 1 or (i == 0 and j == n - 1)
            if adjacents:
                # Sommet partagé : seul un repli colinéaire est un défaut.
                if j == i + 1:
                    commun, autre_i, autre_j = b, a, d
                else:
                    commun, autre_i, autre_j = a, b, c
                if (_orientation(autre_i, commun, autre_j) == 0
                        and ((autre_i[0] - commun[0]) * (autre_j[0] - commun[0])
                             + (autre_i[1] - commun[1])
                             * (autre_j[1] - commun[1])) > 0):
                    return False
                continue
            if _segments_se_touchent(a, b, c, d):
                return False
    return True
