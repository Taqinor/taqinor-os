"""Contrat de GÉOMÉTRIE du module Appels d'offres (``apps.ao``) — AOF19.

ORDRE DES AXES — LA RÈGLE, ÉCRITE UNE FOIS
==========================================
Le dépôt porte DEUX conventions incompatibles pour un même point du globe :

* l'outil de tracé de toiture manipule ``[lng, lat]`` (longitude d'abord) ;
* le lead CRM stocke son ``roof_outline`` en ``[lat, lng]`` (latitude d'abord).

Une inversion d'axes entre les deux est SILENCIEUSE : les nombres restent
plausibles, le polygone atterrit simplement à des centaines de kilomètres. Ce
module tranche :

1. **Le repère CANONIQUE du domaine AO est LOCAL et MÉTRIQUE** : une liste de
   ``[x, y]`` en MÈTRES, x vers l'est, y vers le nord. Le moteur de calepinage
   ne voit JAMAIS de degrés.
2. **Les degrés n'existent qu'à la FRONTIÈRE**, et chaque fonction porte
   l'ordre des axes DANS SON NOM (``..._lnglat`` / ``..._latlng``). Une
   fonction nommée ``convertir_coordonnees`` rendrait l'inversion
   indétectable — c'est exactement l'erreur que ce module refuse de rendre
   possible.

Module PUR : stdlib uniquement, aucun Django, aucune I/O, aucune globale
mutable. ``apps.ao.models`` l'importe (même app) ; il n'importe rien du projet.
"""
from __future__ import annotations

import math

__all__ = [
    'RAYON_TERRE_M',
    'ORDRE_AXES_CANONIQUE',
    'aire_polygone_m2',
    'perimetre_polygone_m',
    'polygone_est_simple',
    'normaliser_orientation',
    'lnglat_vers_local_m',
    'local_m_vers_lnglat',
    'latlng_vers_lnglat',
    'lnglat_vers_latlng',
    'aire_geodesique_m2',
    'perimetre_geodesique_m',
]

#: Rayon moyen de la Terre (IUGG), en mètres.
RAYON_TERRE_M = 6371008.8

#: Documentation exécutable : l'ordre des axes du repère de frontière.
ORDRE_AXES_CANONIQUE = 'lng,lat'


# ── Repère local métrique — géométrie plane pure ───────────────────────────

def _points(contour):
    """Normalise un contour en liste de tuples ``(x, y)`` flottants, ouverte."""
    points = [(float(p[0]), float(p[1])) for p in (contour or [])]
    if len(points) > 1 and points[0] == points[-1]:
        points = points[:-1]
    return points


def polygone_est_simple(contour):
    """Vrai si ``contour`` (``[x, y]`` en MÈTRES) est un polygone simple.

    « Simple » = au moins 3 sommets DISTINCTS et aucun croisement d'arêtes non
    adjacentes. Une enveloppe qui se croise produirait des rangées de modules
    hors du bâtiment : c'est un refus de saisie, pas un avertissement.
    """
    points = _points(contour)
    if len(points) < 3:
        return False
    if len(set(points)) != len(points):
        return False
    n = len(points)
    for i in range(n):
        a1, a2 = points[i], points[(i + 1) % n]
        for j in range(i + 1, n):
            if j == i or (j + 1) % n == i or j == (i + 1) % n:
                continue
            b1, b2 = points[j], points[(j + 1) % n]
            if _segments_se_croisent(a1, a2, b1, b2):
                return False
    return True


def _orientation(p, q, r):
    val = ((q[1] - p[1]) * (r[0] - q[0])) - ((q[0] - p[0]) * (r[1] - q[1]))
    if abs(val) < 1e-12:
        return 0
    return 1 if val > 0 else 2


def _sur_segment(p, q, r):
    return (min(p[0], r[0]) <= q[0] <= max(p[0], r[0])
            and min(p[1], r[1]) <= q[1] <= max(p[1], r[1]))


def _segments_se_croisent(p1, q1, p2, q2):
    o1, o2 = _orientation(p1, q1, p2), _orientation(p1, q1, q2)
    o3, o4 = _orientation(p2, q2, p1), _orientation(p2, q2, q1)
    if o1 != o2 and o3 != o4:
        return True
    if o1 == 0 and _sur_segment(p1, p2, q1):
        return True
    if o2 == 0 and _sur_segment(p1, q2, q1):
        return True
    if o3 == 0 and _sur_segment(p2, p1, q2):
        return True
    if o4 == 0 and _sur_segment(p2, q1, q2):
        return True
    return False


def _aire_signee(points):
    total = 0.0
    n = len(points)
    for i in range(n):
        x1, y1 = points[i]
        x2, y2 = points[(i + 1) % n]
        total += (x1 * y2) - (x2 * y1)
    return total / 2.0


def aire_polygone_m2(contour):
    """Aire (m²) d'un contour en repère LOCAL MÉTRIQUE (formule du lacet)."""
    points = _points(contour)
    if len(points) < 3:
        return 0.0
    return abs(_aire_signee(points))


def perimetre_polygone_m(contour):
    """Périmètre (m) d'un contour en repère LOCAL MÉTRIQUE."""
    points = _points(contour)
    if len(points) < 2:
        return 0.0
    total = 0.0
    n = len(points)
    for i in range(n):
        x1, y1 = points[i]
        x2, y2 = points[(i + 1) % n]
        total += math.hypot(x2 - x1, y2 - y1)
    return total


def normaliser_orientation(contour):
    """Renvoie le contour en sens TRIGONOMÉTRIQUE (anti-horaire).

    Une orientation normalisée est ce qui rend comparables deux relevés du même
    bâtiment saisis dans des sens opposés — et ce qui permet à l'empreinte
    d'entrée (AOF29) d'être stable.
    """
    points = _points(contour)
    if len(points) < 3:
        return [list(p) for p in points]
    if _aire_signee(points) < 0:
        points = list(reversed(points))
    return [list(p) for p in points]


# ── Frontière : degrés ↔ repère local métrique ─────────────────────────────

def lnglat_vers_local_m(contour_lnglat, origine_lnglat):
    """``[[lng, lat], …]`` → ``[[x, y], …]`` en MÈTRES (projection ENU locale).

    ``origine_lnglat`` est le point ``[lng, lat]`` qui devient ``(0, 0)``. x
    pointe vers l'EST, y vers le NORD. Approximation plane tangente : à
    l'échelle d'un site (quelques centaines de mètres) l'erreur est très
    inférieure au centimètre, et l'aller-retour est exact par construction.

    L'ordre des axes est dans le NOM : ``lnglat`` = longitude d'abord.
    """
    lng0, lat0 = float(origine_lnglat[0]), float(origine_lnglat[1])
    k = math.pi / 180.0
    cos_lat0 = math.cos(lat0 * k)
    sortie = []
    for point in contour_lnglat or []:
        lng, lat = float(point[0]), float(point[1])
        x = (lng - lng0) * k * RAYON_TERRE_M * cos_lat0
        y = (lat - lat0) * k * RAYON_TERRE_M
        sortie.append([x, y])
    return sortie


def local_m_vers_lnglat(contour_local_m, origine_lnglat):
    """``[[x, y], …]`` en MÈTRES → ``[[lng, lat], …]`` (inverse exacte).

    L'ordre des axes est dans le NOM : la sortie est ``lng`` PUIS ``lat``.
    """
    lng0, lat0 = float(origine_lnglat[0]), float(origine_lnglat[1])
    k = math.pi / 180.0
    cos_lat0 = math.cos(lat0 * k)
    sortie = []
    for point in contour_local_m or []:
        x, y = float(point[0]), float(point[1])
        lng = lng0 + x / (k * RAYON_TERRE_M * cos_lat0)
        lat = lat0 + y / (k * RAYON_TERRE_M)
        sortie.append([lng, lat])
    return sortie


def latlng_vers_lnglat(contour_latlng):
    """``[[lat, lng], …]`` (format lead CRM) → ``[[lng, lat], …]``.

    ADAPTATEUR EXPLICITE, à appeler exactement une fois, à la frontière. C'est
    la seule fonction du dépôt autorisée à échanger les deux axes ; son nom dit
    ce qu'elle fait dans les deux sens.
    """
    return [[float(p[1]), float(p[0])] for p in (contour_latlng or [])]


def lnglat_vers_latlng(contour_lnglat):
    """``[[lng, lat], …]`` → ``[[lat, lng], …]`` (format lead CRM)."""
    return [[float(p[1]), float(p[0])] for p in (contour_lnglat or [])]


def aire_geodesique_m2(contour_lnglat, origine_lnglat=None):
    """Aire (m²) d'un contour donné en DEGRÉS ``[lng, lat]``.

    Passe par la projection locale (origine = premier sommet à défaut) : le
    calcul métrique reste l'unique implémentation, les degrés ne sont qu'une
    entrée de frontière.
    """
    contour = list(contour_lnglat or [])
    if len(contour) < 3:
        return 0.0
    origine = origine_lnglat or contour[0]
    return aire_polygone_m2(lnglat_vers_local_m(contour, origine))


def perimetre_geodesique_m(contour_lnglat, origine_lnglat=None):
    """Périmètre (m) d'un contour donné en DEGRÉS ``[lng, lat]``."""
    contour = list(contour_lnglat or [])
    if len(contour) < 2:
        return 0.0
    origine = origine_lnglat or contour[0]
    return perimetre_polygone_m(lnglat_vers_local_m(contour, origine))
