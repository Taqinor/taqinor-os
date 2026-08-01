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
    "point_dans_polygone", "rectangles_se_croisent",
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
