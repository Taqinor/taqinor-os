"""ACAL534 — un altimètre qui lit un relief GeoTIFF fourni par l'installateur.

``lidar_ign.suggerer_pentes`` accepte un altimètre injecté
(``[(lon, lat), …] -> [altitude | None, …]``) ; le seul altimètre réel était
celui de l'IGN (France). Ici, les octets d'un GeoTIFF d'altitudes (produit par
l'outil de drone de l'installateur) deviennent le même appelable.

* Lecture par Pillow et numpy (déjà épinglés) : AUCUNE dépendance ajoutée. Les
  étiquettes TIFF lues sont ``ModelPixelScaleTag`` (33550),
  ``ModelTiepointTag`` (33922) et ``GeoKeyDirectoryTag`` (34735).
* Projection en DEGRÉS seulement (WGS84, EPSG:4326) : un relief en mètres
  (UTM…) est REFUSÉ en le nommant, jamais reprojeté de façon approximative.
* Un point hors de l'emprise du fichier, ou voisin d'une valeur sans donnée,
  rend ``None`` — jamais une altitude de repli. Le filtre d'altitudes est celui
  d'IGN (-500 à 9 000 m).
* Le nombre de pixels est borné par la protection de Pillow, aucune autre
  limite inventée. Rien n'est conservé côté serveur.
"""
from __future__ import annotations

import io
import math

__all__ = ['ReliefIllisible', 'altimetre_depuis_geotiff']

#: Numéros d'étiquettes et de clés fixés par la spécification GeoTIFF (OGC
#: GeoTIFF 1.1, OGC 19-008r4 ; reprend GeoTIFF Revision 1.0, 1995) :
#: ModelPixelScaleTag 33550, ModelTiepointTag 33922, ModelTransformationTag
#: 34264, GeoKeyDirectoryTag 34735 ; clés GTModelTypeGeoKey 1024 (1 =
#: projeté, 2 = géographique), GTRasterTypeGeoKey 1025 (1 = PixelIsArea,
#: 2 = PixelIsPoint), GeographicTypeGeoKey 2048 (code EPSG, 4326 = WGS84).
#: 42113 est l'étiquette privée GDAL_NODATA (documentation du pilote GTiff de
#: GDAL), hors de la spécification OGC.
TAG_ECHELLE = 33550
TAG_POINT_DE_LIAISON = 33922
TAG_TRANSFORMATION = 34264
TAG_CLES_GEO = 34735
TAG_SANS_DONNEE = 42113
CLE_TYPE_MODELE = 1024      # 1 = projeté, 2 = géographique
CLE_TYPE_RASTER = 1025      # 1 = pixel-surface, 2 = pixel-point
CLE_GEOGRAPHIQUE = 2048     # 4326 = WGS84
ALTITUDE_MIN, ALTITUDE_MAX = -500.0, 9000.0
MODES_ALTITUDE = ('F', 'I', 'I;16', 'I;16S')


class ReliefIllisible(ValueError):
    """Le relief ne peut pas servir : la cause est nommée, en français."""


def _cles_geo(etiquette):
    """``{clé: valeur}`` du ``GeoKeyDirectoryTag`` (entrées sans renvoi)."""
    brut = list(etiquette or ())
    cles = {}
    for i in range(4, len(brut) - 3, 4):
        cle, renvoi, _compte, valeur = brut[i:i + 4]
        if renvoi == 0:
            cles[cle] = valeur
    return cles


def _lire(octets):
    """``(tableau, echelle, point_de_liaison, pixel_point, sans_donnee)``."""
    import numpy as np
    from PIL import Image

    try:
        image = Image.open(io.BytesIO(octets))
        etiquettes = image.tag_v2
        image.load()
    except Exception as erreur:
        raise ReliefIllisible(
            "Le relief est illisible (GeoTIFF non compressé attendu) : "
            f"{erreur}.") from erreur
    if image.mode not in MODES_ALTITUDE:
        raise ReliefIllisible(
            "Le relief ne porte pas d'altitudes lisibles (mode "
            f"{image.mode} : un GeoTIFF d'altitudes en nombres à virgule "
            "ou entiers est attendu).")
    echelle = etiquettes.get(TAG_ECHELLE)
    liaison = etiquettes.get(TAG_POINT_DE_LIAISON)
    cles = _cles_geo(etiquettes.get(TAG_CLES_GEO))
    if (not echelle or not liaison or len(echelle) < 2 or len(liaison) < 6
            or CLE_TYPE_MODELE not in cles):
        raise ReliefIllisible(
            "Le relief n'a pas d'étiquettes de géoréférencement "
            "(ModelPixelScale, ModelTiepoint, GeoKeyDirectory) : exportez-le "
            "en GeoTIFF géoréférencé.")
    if etiquettes.get(TAG_TRANSFORMATION):
        raise ReliefIllisible(
            "Le relief porte une transformation tournée (ModelTransformation)"
            " : exportez-le sans rotation.")
    if cles[CLE_TYPE_MODELE] != 2:
        raise ReliefIllisible(
            "Le relief est en mètres (projection) : exportez-le en WGS84 "
            "(degrés).")
    if cles.get(CLE_GEOGRAPHIQUE, 4326) != 4326:
        raise ReliefIllisible(
            "Le relief n'est pas en WGS84 (EPSG:4326) : exportez-le en WGS84 "
            "(degrés).")
    brut = etiquettes.get(TAG_SANS_DONNEE)
    try:
        sans_donnee = float(brut) if brut not in (None, '') else None
    except (TypeError, ValueError):
        sans_donnee = None
    tableau = np.asarray(image, dtype='float64')
    return (tableau, (float(echelle[0]), float(echelle[1])),
            tuple(float(v) for v in liaison[:6]),
            cles.get(CLE_TYPE_RASTER, 1) == 2, sans_donnee)


def altimetre_depuis_geotiff(octets):
    """L'altimètre ``[(lon, lat), …] -> [altitude | None, …]`` d'un GeoTIFF.

    Raises:
        ReliefIllisible: fichier illisible, sans géoréférencement, sans
            altitudes lisibles, ou en mètres.
    """
    tableau, (dx, dy), liaison, pixel_point, sans_donnee = _lire(octets)
    hauteur, largeur = tableau.shape[:2]
    if not (dx > 0 and dy > 0):
        raise ReliefIllisible(
            "Le relief n'a pas de pas de pixel lisible (ModelPixelScale).")
    i0, j0, _, lon0, lat0, _ = liaison
    decalage = 0.0 if pixel_point else 0.5   # centre du pixel (0, 0)

    def valide(z):
        return (math.isfinite(z) and ALTITUDE_MIN <= z <= ALTITUDE_MAX
                and (sans_donnee is None or z != sans_donnee))

    def altitude(lon, lat):
        colonne = (lon - lon0) / dx + i0 - decalage
        ligne = (lat0 - lat) / dy + j0 - decalage
        if not (-0.5 <= colonne <= largeur - 0.5
                and -0.5 <= ligne <= hauteur - 0.5):
            return None
        c = min(max(colonne, 0.0), largeur - 1.0)
        r = min(max(ligne, 0.0), hauteur - 1.0)
        c0, r0 = int(math.floor(c)), int(math.floor(r))
        c1, r1 = min(c0 + 1, largeur - 1), min(r0 + 1, hauteur - 1)
        quatre = [float(tableau[r0, c0]), float(tableau[r0, c1]),
                  float(tableau[r1, c0]), float(tableau[r1, c1])]
        if not all(valide(z) for z in quatre):
            return None
        fc, fr = c - c0, r - r0
        haut = quatre[0] * (1 - fc) + quatre[1] * fc
        bas = quatre[2] * (1 - fc) + quatre[3] * fc
        return float(haut * (1 - fr) + bas * fr)

    def altimetre(points):
        return [altitude(float(lon), float(lat)) for lon, lat in points or []]

    return altimetre
