"""ACAL281 — LA projection lat/lng → mètres et LA paire boussole ↔ aspect.

Source UNIQUE (stdlib seulement, aucun Django) de deux conventions qui
vivaient en plusieurs copies divergentes côté serveur :

* **Projection locale** — plan tangent sur la SPHÈRE de rayon
  ``RAYON_TERRE_M = 6 378 137 m`` (le demi-grand axe WGS84), autour d'une
  origine ``(lon, lat)`` : ``x = Δlon·k·cos(lat0)``, ``y = Δlat·k`` avec
  ``k = R·π/180``. C'est la convention de l'atelier (``roofPro2.ts``,
  ``viewerFullModel.ringENUFromVertices``), du site public (``roof.ts``
  ``geodesicAreaM2``) et du devis (``calepinage_options.anneau_enu``). Choix de
  COHÉRENCE (une seule aire du même tracé partout), pas un gain de précision :
  l'ancienne copie « 111 320 / 110 540 » et la copie ellipsoïdale de
  ``repere.js`` différaient de ≤ 0,7 %.
* **Azimuts** — azimut BOUSSOLE (« de face » : 0 = Nord, 90 = Est,
  180 = Sud) ↔ ``aspect`` PVGIS (0 = Sud, −90 = Est, +90 = Ouest). Le Nord
  vaut **+180** côté aspect, partout. Aucun arrondi ici : on n'arrondit qu'au
  point de publication.
"""
from __future__ import annotations

import math

__all__ = [
    'RAYON_TERRE_M', 'METRES_PAR_DEGRE',
    'projeteur_local', 'deprojeteur_local', 'anneau_local',
    'aire_anneau_m2', 'aire_contour_m2',
    'boussole_vers_aspect', 'aspect_vers_boussole',
]

#: Demi-grand axe WGS84, utilisé comme rayon de SPHÈRE (convention partagée).
RAYON_TERRE_M = 6378137.0
_DEG2RAD = math.pi / 180.0
#: Mètres par degré d'arc sur cette sphère (≈ 111 319,49 m).
METRES_PAR_DEGRE = _DEG2RAD * RAYON_TERRE_M


def _fini(valeur):
    """Coordonnée : ``int``/``float`` fini, ou ``None`` (jamais un booléen,
    jamais une chaîne)."""
    if isinstance(valeur, bool) or not isinstance(valeur, (int, float)):
        return None
    nombre = float(valeur)
    return nombre if math.isfinite(nombre) else None


def _angle(valeur):
    """Angle : tout ce que ``float()`` lit (chaîne numérique comprise), fini,
    ou ``None``."""
    if isinstance(valeur, bool):
        return None
    try:
        nombre = float(valeur)
    except (TypeError, ValueError):
        return None
    return nombre if math.isfinite(nombre) else None


def _cos_lat(lat0):
    return math.cos(lat0 * _DEG2RAD)


def projeteur_local(origine):
    """``(lon, lat) -> (x_m, y_m)`` autour de ``origine`` ``(lon, lat)``."""
    lon0, lat0 = float(origine[0]), float(origine[1])
    cos_lat0 = _cos_lat(lat0)

    def projeter(point):
        return ((float(point[0]) - lon0) * METRES_PAR_DEGRE * cos_lat0,
                (float(point[1]) - lat0) * METRES_PAR_DEGRE)

    return projeter


def deprojeteur_local(origine):
    """L'inverse exact de :func:`projeteur_local` : ``(x, y) m -> (lon, lat)``."""
    lon0, lat0 = float(origine[0]), float(origine[1])
    echelle_x = METRES_PAR_DEGRE * _cos_lat(lat0)

    def deprojeter(point):
        return (lon0 + float(point[0]) / echelle_x,
                lat0 + float(point[1]) / METRES_PAR_DEGRE)

    return deprojeter


def anneau_local(contour, origine):
    """Le contour ``[[lng, lat], …]`` en mètres autour de ``origine``.

    Les sommets illisibles (non numériques, NaN, paire incomplète) sont
    écartés ; une origine illisible rend ``[]``.
    """
    olng = _fini((origine or [None, None])[0])
    olat = _fini((origine or [None, None])[1])
    if olng is None or olat is None:
        return []
    projeter = projeteur_local((olng, olat))
    anneau = []
    for sommet in contour or []:
        if not isinstance(sommet, (list, tuple)) or len(sommet) < 2:
            continue
        lng, lat = _fini(sommet[0]), _fini(sommet[1])
        if lng is None or lat is None:
            continue
        anneau.append(projeter((lng, lat)))
    return anneau


def aire_anneau_m2(anneau):
    """L'aire (m², positive) d'un anneau plan ``[(x, y), …]`` — lacet."""
    if len(anneau or []) < 3:
        return 0.0
    aire2 = 0.0
    for i in range(len(anneau)):
        ax, ay = anneau[i]
        bx, by = anneau[(i + 1) % len(anneau)]
        aire2 += ax * by - bx * ay
    return abs(aire2) / 2.0


def aire_contour_m2(contour):
    """L'aire PROJETÉE (m²) d'un contour ``[[lng, lat], …]``, ou ``None``.

    Origine = premier sommet. ``None`` sous 3 sommets lisibles ou pour une
    aire nulle — jamais une surface inventée.
    """
    if len(contour or []) < 3:
        return None
    anneau = anneau_local(contour, contour[0])
    if len(anneau) < 3:
        return None
    aire = aire_anneau_m2(anneau)
    return aire if aire > 0 else None


def boussole_vers_aspect(azimut):
    """Azimut BOUSSOLE (180 = Sud) → ``aspect`` PVGIS dans ]−180, 180].

    Nord (0 ou 360) → +180. Valeur illisible → ``None``.
    """
    face = _angle(azimut)
    if face is None:
        return None
    aspect = (face - 180.0) % 360.0
    if aspect > 180.0:
        aspect -= 360.0
    return aspect


def aspect_vers_boussole(aspect):
    """``aspect`` PVGIS (0 = Sud) → azimut BOUSSOLE dans [0, 360).

    Réciproque de :func:`boussole_vers_aspect`. Valeur illisible → ``None``.
    """
    valeur = _angle(aspect)
    if valeur is None:
        return None
    return (valeur + 180.0) % 360.0
