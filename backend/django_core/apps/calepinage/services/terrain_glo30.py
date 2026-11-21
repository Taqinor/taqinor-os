"""ACAL466 — la pente et l'orientation du RELIEF d'un champ au sol, lues sur
Copernicus GLO-30 (gratuit, sans compte, hors France comme en France).

Pourquoi ce module existe à côté de ``lidar_ign`` : l'IGN ne sert que la France
et que des pans de TOIT. Un champ au sol au Maroc n'avait aucune source de
relief ; l'écran Terrain demandait la pente à la main.

La SOURCE : tuiles COG du seau public ``copernicus-dem-30m`` (HTTP anonyme,
requêtes ``Range``). Une tuile = 1° × 1° = 3 600 × 3 600 pixels float32, en
blocs de 1 024², compression Deflate + prédicteur flottant 3. Lisible avec
``zlib`` + ``numpy`` : AUCUNE dépendance de plus, AUCUN compte. C'est un DSM
(bâtiments et végétation inclus), erreur annoncée < 4 m à 90 % : valable pour
un terrain, JAMAIS pour un toit.

L'ajustement du plan est celui de ``lidar_ign._ajuster_plan`` (réutilisé, pas
recopié). Réseau coupé, tuile illisible, moins de trois pixels distincts ou
points alignés ⇒ ``pente_deg: None`` et un motif français : jamais une altitude
de repli (un chiffre inventé serait pire que pas de chiffre).
"""
from __future__ import annotations

import logging
import math
import struct
import zlib
from datetime import datetime, timezone
from urllib.request import Request, urlopen

from .lidar_ign import _ajuster_plan

logger = logging.getLogger(__name__)

SOURCE = 'Copernicus GLO-30 (modèle numérique de surface, 30 m)'
URL_SOURCE = 'https://registry.opendata.aws/copernicus-dem'
URL_BASE = 'https://copernicus-dem-30m.s3.amazonaws.com'
#: Texte de citation relevé sur la page du jeu de données le 21/11/2026,
#: imprimé tel quel ; ``DATE`` y est remplacée par la date de lecture.
ATTRIBUTION_MODELE = (
    'Copernicus Digital Elevation Model (DEM) was accessed on DATE '
    f'from {URL_SOURCE}.')
DELAI_RESEAU_S = 20
OCTETS_ENTETE = 8192
MAX_SOMMETS = 50
MAX_CELLULES = 4
ALTITUDE_MIN_M, ALTITUDE_MAX_M = -500.0, 9000.0

__all__ = ['SOURCE', 'URL_SOURCE', 'ATTRIBUTION_MODELE', 'TerrainIndisponible',
           'lire_pente_surface']

_TAILLE_TYPE = {1: 1, 2: 1, 3: 2, 4: 4, 5: 8, 12: 8, 16: 8}
_FORMAT_TYPE = {1: 'B', 2: 'c', 3: 'H', 4: 'I', 12: 'd', 16: 'Q'}


class TerrainIndisponible(Exception):
    """Le relief n'a pas pu être lu : le message est le motif, en français."""


def _nom_tuile(lon, lat):
    """``(url, nom)`` de la tuile 1° qui contient ``(lon, lat)``."""
    ns = 'N' if math.floor(lat) >= 0 else 'S'
    ew = 'E' if math.floor(lon) >= 0 else 'W'
    nom = (f'Copernicus_DSM_COG_10_{ns}{abs(math.floor(lat)):02d}_00_'
           f'{ew}{abs(math.floor(lon)):03d}_00_DEM')
    return f'{URL_BASE}/{nom}/{nom}.tif', nom


def _lire_plage_http(url, debut, fin):
    """Octets ``[debut, fin]`` (inclus) de ``url`` par requête ``Range``."""
    requete = Request(url, headers={'Range': f'bytes={debut}-{fin}'})
    try:
        with urlopen(requete, timeout=DELAI_RESEAU_S) as reponse:
            return reponse.read()
    except Exception as exc:
        logger.warning('terrain glo30 : lecture impossible (%s)', url,
                       exc_info=True)
        raise TerrainIndisponible(
            "Le relief Copernicus n'est pas joignable pour le moment : "
            "saisissez la pente à la main.") from exc


class _Tuile:
    """En-tête d'une tuile GeoTIFF tuilée + décodage d'un bloc à la demande."""

    def __init__(self, url, lecteur):
        self.url, self.lecteur = url, lecteur
        self.blocs = {}
        entete = lecteur(url, 0, OCTETS_ENTETE - 1)
        if entete[:2] == b'II':
            self.o = '<'
        elif entete[:2] == b'MM':
            self.o = '>'
        else:
            raise TerrainIndisponible("Tuile de relief illisible (en-tête).")
        if struct.unpack(self.o + 'H', entete[2:4])[0] != 42:
            raise TerrainIndisponible("Tuile de relief illisible (BigTIFF).")
        debut = struct.unpack(self.o + 'I', entete[4:8])[0]
        n = struct.unpack(self.o + 'H', self._ifd(entete, debut, 2))[0]
        brut = self._ifd(entete, debut + 2, 12 * n)
        t = {}
        for i in range(n):
            e = brut[12 * i:12 * i + 12]
            tag, typ, nb = struct.unpack(self.o + 'HHI', e[:8])
            t[tag] = self._valeurs(entete, typ, nb, e[8:])
        try:
            self.largeur, self.hauteur = t[256][0], t[257][0]
            self.tw, self.th = t[322][0], t[323][0]
            self.offsets, self.longueurs = t[324], t[325]
            self.compression = t[259][0]
            self.predicteur = t.get(317, [1])[0]
            self.bits = t[258][0]
            self.format = t.get(339, [1])[0]
            self.sx, self.sy = t[33550][0], t[33550][1]
            self.lon0, self.lat0 = t[33922][3], t[33922][4]
        except (KeyError, IndexError) as exc:
            raise TerrainIndisponible(
                "Tuile de relief illisible (balises manquantes).") from exc
        cles = t.get(34735, [])
        # GTRasterTypeGeoKey (1025) : 2 = PixelIsPoint, sinon PixelIsArea.
        self.point = any(cles[i] == 1025 and cles[i + 3] == 2
                         for i in range(4, len(cles) - 3, 4))
        if (self.compression not in (8, 32946) or self.bits != 32
                or self.format != 3 or self.predicteur not in (1, 3)):
            raise TerrainIndisponible(
                "Tuile de relief dans un format non pris en charge.")

    def _ifd(self, entete, debut, n):
        if debut + n <= len(entete):
            return entete[debut:debut + n]
        return self.lecteur(self.url, debut, debut + n - 1)

    def _valeurs(self, entete, typ, nb, champ):
        taille = _TAILLE_TYPE.get(typ)
        if taille is None:
            return []
        if taille * nb <= 4:
            octets = champ[:taille * nb]
        else:
            adresse = struct.unpack(self.o + 'I', champ)[0]
            octets = self._ifd(entete, adresse, taille * nb)
        if typ == 5:
            return []
        return list(struct.unpack(f'{self.o}{nb}{_FORMAT_TYPE[typ]}', octets))

    def centre(self, col, ligne):
        """``(lon, lat)`` du centre du pixel ``(col, ligne)``."""
        d = 0.0 if self.point else 0.5
        return (self.lon0 + (col + d) * self.sx,
                self.lat0 - (ligne + d) * self.sy)

    def pixel(self, lon, lat):
        """``(col, ligne)`` du pixel le plus proche de ``(lon, lat)``."""
        d = 0.0 if self.point else 0.5
        col = round((lon - self.lon0) / self.sx - d)
        ligne = round((self.lat0 - lat) / self.sy - d)
        return (min(max(col, 0), self.largeur - 1),
                min(max(ligne, 0), self.hauteur - 1))

    def altitude(self, col, ligne):
        """Altitude (m) du pixel, ou ``None`` : absence de donnée, jamais 0."""
        import numpy as np

        across = -(-self.largeur // self.tw)
        indice = (ligne // self.th) * across + (col // self.tw)
        if indice not in self.blocs:
            if not self.longueurs[indice] or not self.offsets[indice]:
                self.blocs[indice] = None
            else:
                debut = self.offsets[indice]
                brut = self.lecteur(self.url, debut,
                                    debut + self.longueurs[indice] - 1)
                try:
                    donnees = zlib.decompress(brut)
                    a = np.frombuffer(donnees, np.uint8)
                    a = a.reshape(self.th, self.tw * 4)
                    if self.predicteur == 3:
                        # Inverse du prédicteur flottant : cumul des octets par
                        # ligne, puis les 4 plans d'octets (poids fort d'abord)
                        # redeviennent des float32 big-endian.
                        a = np.cumsum(a, axis=1, dtype=np.uint8)
                        a = a.reshape(self.th, 4, self.tw).transpose(0, 2, 1)
                        self.blocs[indice] = np.ascontiguousarray(
                            a).view('>f4').reshape(self.th, self.tw)
                    else:
                        self.blocs[indice] = a.view(self.o + 'f4')
                except Exception as exc:
                    raise TerrainIndisponible(
                        "Tuile de relief illisible (décodage).") from exc
        bloc = self.blocs[indice]
        if bloc is None:
            return None
        v = float(bloc[ligne % self.th, col % self.tw])
        if not math.isfinite(v) or not ALTITUDE_MIN_M <= v <= ALTITUDE_MAX_M:
            return None
        return v


def _sommets(vertices):
    pts = [(float(v[0]), float(v[1])) for v in vertices or []
           if isinstance(v, (list, tuple)) and len(v) >= 2
           and all(isinstance(c, (int, float)) and not isinstance(c, bool)
                   for c in v[:2])][:MAX_SOMMETS]
    if len(pts) >= 3:
        pts.append((sum(p[0] for p in pts) / len(pts),
                    sum(p[1] for p in pts) / len(pts)))
    return pts


def _resultat(surface, maintenant, pente=None, azimut=None, points=None,
              motif=''):
    lu = maintenant or datetime.now(timezone.utc).strftime(
        '%Y-%m-%dT%H:%M:%SZ')
    return {
        'surface': surface, 'pente_deg': pente, 'azimut_pente_deg': azimut,
        'source': SOURCE, 'source_url': URL_SOURCE,
        'attribution': ATTRIBUTION_MODELE.replace('DATE', lu[:10]),
        'lu_le': lu, 'points': points or [], 'motif': motif,
        'ancrage': 'contour_trace',
    }


def _lire_pente_terrain(surface, vertices, *, lecteur=None, maintenant=None):
    """Pente / azimut de pente du relief sous ``vertices`` ([lng, lat]).

    ``lecteur(url, debut, fin) -> bytes`` est la SEULE sortie réseau
    (injectable pour les tests). Rend toujours le dict de la route ; en cas
    d'échec ``pente_deg`` vaut ``None`` et ``motif`` dit pourquoi.
    """
    lecteur = lecteur or _lire_plage_http
    pts = _sommets(vertices)
    if len(pts) < 3:
        return _resultat(surface, maintenant, motif=(
            "Le champ n'a pas trois sommets tracés : tracez son contour "
            "sur la carte."))
    cellules = {}
    for lon, lat in pts:
        cellules.setdefault((math.floor(lon), math.floor(lat)), []).append(
            (lon, lat))
    if len(cellules) > MAX_CELLULES:
        return _resultat(surface, maintenant, motif=(
            "Le champ s'étend sur trop de tuiles de relief."))
    mesures, vus = [], set()
    try:
        for (cx, cy), liste in cellules.items():
            url, nom = _nom_tuile(cx + 0.5, cy + 0.5)
            tuile = _Tuile(url, lecteur)
            for lon, lat in liste:
                col, ligne = tuile.pixel(lon, lat)
                if (nom, col, ligne) in vus:
                    continue
                z = tuile.altitude(col, ligne)
                if z is None:
                    continue
                vus.add((nom, col, ligne))
                clon, clat = tuile.centre(col, ligne)
                mesures.append((clon, clat, z))
    except TerrainIndisponible as refus:
        return _resultat(surface, maintenant, motif=str(refus))
    if len(mesures) < 3:
        return _resultat(surface, maintenant, motif=(
            "Moins de trois pixels de relief de 30 m distincts sous ce "
            "champ : trop petit pour en lire une pente."))
    plan = _ajuster_plan(mesures)
    if plan is None:
        return _resultat(surface, maintenant, motif=(
            "Les pixels de relief sont alignés : aucune pente ne s'en "
            "déduit."))
    pente, azimut = plan
    points = [{'lon': round(m[0], 6), 'lat': round(m[1], 6),
               'altitude_m': round(m[2], 2)} for m in mesures]
    return _resultat(surface, maintenant, pente, azimut, points)


def _contour_m_vers_lnglat(contour_m, epingle):
    """Contour ``[[x, y], …]`` en MÈTRES -> ``[[lng, lat], …]``, ou ``None``.

    Le contour saisi (``poseSurfaces[].contourM``) est un repère local sans
    géoréférence ; la seule donnée géographique du document est l'épingle du
    site (``roof_layout.pin``, ``{lat, lng}``). Le champ est CENTRÉ sur
    l'épingle (x = est, y = nord) par la projection équirectangulaire unique
    du module (``core.calepinage.geo.deprojeteur_local``) : à l'échelle d'un
    champ (< 1 km) l'erreur de projection est négligeable devant le pixel de
    30 m. Contour ou épingle inutilisable ⇒ ``None``.
    """
    from core.calepinage.geo import deprojeteur_local

    try:
        pts = [(float(p[0]), float(p[1])) for p in contour_m or []]
        origine = (float(epingle['lng']), float(epingle['lat']))
    except (TypeError, ValueError, KeyError, IndexError):
        return None
    if len(pts) < 3:
        return None
    cx = sum(p[0] for p in pts) / len(pts)
    cy = sum(p[1] for p in pts) / len(pts)
    deproj = deprojeteur_local(origine)
    return [list(deproj((x - cx, y - cy))) for x, y in pts]


def lire_pente_surface(surface_id, surface, epingle=None, **kw):
    """``_lire_pente_terrain`` pour un ``poseSurfaces[]`` du document.

    Contour tracé sur la carte (``vertices``) d'abord ; sinon le contour saisi
    en mètres centré sur l'épingle du site (``ancrage: 'epingle_du_site'``) ;
    sinon refus nommant la donnée manquante.
    """
    surface = surface if isinstance(surface, dict) else {}
    if len(_sommets(surface.get('vertices'))) >= 3:
        return _lire_pente_terrain(surface_id, surface['vertices'], **kw)
    if len(surface.get('contourM') or []) < 3:
        return _resultat(surface_id, kw.get('maintenant'), motif=(
            "Le champ n'a ni contour tracé sur la carte ni dimensions "
            "saisies : le relief n'a aucun emplacement à lire."))
    sommets = _contour_m_vers_lnglat(surface.get('contourM'), epingle)
    if sommets is None:
        return _resultat(surface_id, kw.get('maintenant'), motif=(
            "L'emplacement du champ est inconnu : le contour saisi en "
            "mètres n'a pas de coordonnées et le site n'a pas d'épingle "
            "(roof_layout.pin). Posez l'épingle du site ou tracez le "
            "contour sur la carte."))
    resultat = _lire_pente_terrain(surface_id, sommets, **kw)
    resultat['ancrage'] = 'epingle_du_site'
    return resultat
