# -*- coding: utf-8 -*-
"""AOF162 — adaptateur VILLA : ``AreaRecord`` roofPro11 -> ``EntreeCalepinage``.

La villa n'est pas un autre moteur : c'est le MÊME, avec un kit à UN module
(720 Wc, 2,384 × 1,303 à 13°) et une politique de pas anti-ombrage. Cet
adaptateur ne fait donc que de la traduction de format et de la projection
géographique — aucune règle de calepinage n'y vit.

**Le piège lat/lng est traité ici, une fois pour toutes.** Le lecteur de cartes
sérialise ses contours en ``[lng, lat]`` (convention GeoJSON) tandis que le
lead CRM stocke ses coordonnées en ``[lat, lng]``. Les deux se ressemblent et
la confusion produit une toiture retournée, plausible et fausse. L'ordre est
donc un ARGUMENT EXPLICITE, jamais deviné, et un test dédié le couvre.

``apps/web`` n'est PAS modifié : le cerveau TypeScript reste en place et
intact ; la bascule se fera derrière un drapeau, avec comparaison A/B.
"""

import math
from dataclasses import dataclass

from core.calepinage.politique_pas import Affleurant, AntiOmbrage
from core.calepinage.serialisation import EntreeCalepinage
from core.calepinage.surfaces.polygone import SurfacePolygone
from core.calepinage.types import (
    KIT_VILLA_720,
    Axe,
    Obstacle,
    Parametres,
    Provenance,
    Rives,
    TypeObstacle,
)

__all__ = [
    "RAYON_TERRE_M", "RETRAIT_VILLA_M", "DEGAGEMENT_VILLA_M", "Projection",
    "projection_locale", "vers_entree", "vers_panneaux", "politique_villa",
    "expliquer_ecart",
]

#: Rayon terrestre moyen (WGS84 demi-grand axe) — projection ENU locale.
RAYON_TERRE_M = 6378137.0
#: Retrait de rive villa (setback) et dégagement autour d'un obstacle déclaré.
RETRAIT_VILLA_M = 0.50
DEGAGEMENT_VILLA_M = 0.30


@dataclass(frozen=True)
class Projection:
    """Projection ENU locale autour d'un point d'ancrage."""

    lat0_deg: float
    lng0_deg: float

    @property
    def metres_par_degre_lat(self):
        return RAYON_TERRE_M * math.pi / 180.0

    @property
    def metres_par_degre_lng(self):
        return (RAYON_TERRE_M * math.pi / 180.0
                * math.cos(math.radians(self.lat0_deg)))

    def vers_local(self, lat_deg, lng_deg):
        """``(lat, lng)`` -> ``(est, nord)`` en mètres."""
        return ((lng_deg - self.lng0_deg) * self.metres_par_degre_lng,
                (lat_deg - self.lat0_deg) * self.metres_par_degre_lat)

    def vers_geo(self, est_m, nord_m):
        """``(est, nord)`` -> ``(lat, lng)`` — la reprojection de l'écran."""
        return (self.lat0_deg + nord_m / self.metres_par_degre_lat,
                self.lng0_deg + est_m / self.metres_par_degre_lng)


def _couple(point, ordre):
    """Rend ``(lat, lng)`` quel que soit l'ordre de sérialisation.

    ``ordre='lnglat'`` — convention GeoJSON du lecteur de cartes ;
    ``ordre='latlng'`` — convention du lead CRM. Aucun défaut deviné : un
    contour retourné est indétectable à l'œil et faux au mètre près.
    """
    if ordre == "lnglat":
        return (float(point[1]), float(point[0]))
    if ordre == "latlng":
        return (float(point[0]), float(point[1]))
    raise ValueError("ordre de coordonnées inconnu : %r (lnglat | latlng)"
                     % (ordre,))


def projection_locale(points, ordre="lnglat"):
    """Ancre la projection sur le BARYCENTRE du contour (stable et local)."""
    couples = [_couple(p, ordre) for p in points]
    if not couples:
        raise ValueError("contour vide : aucune projection possible")
    lat0 = sum(c[0] for c in couples) / len(couples)
    lng0 = sum(c[1] for c in couples) / len(couples)
    return Projection(lat0_deg=lat0, lng0_deg=lng0)


def politique_villa(area):
    """Toit PLAT -> anti-ombrage ; toit en PENTE -> pose affleurante."""
    plat = area.get("flat", area.get("plat", True))
    pente = float(area.get("tilt", area.get("pente_deg", 0.0)) or 0.0)
    if plat and pente < 5.0:
        return AntiOmbrage()
    return Affleurant()


def _obstacles_villa(area, projection, ordre):
    """``centre + dimensions`` -> rectangles, provenance DÉCLARÉE PAR LE CLIENT."""
    obstacles = []
    for i, brut in enumerate(area.get("obstacles", ()) or ()):
        centre = brut.get("center", brut.get("centre"))
        if centre is None:
            continue
        lat, lng = _couple(centre, ordre)
        est, nord = projection.vers_local(lat, lng)
        largeur = float(brut.get("widthM", brut.get("largeur_m", 1.0)))
        profondeur = float(brut.get("heightM", brut.get("profondeur_m", 1.0)))
        obstacles.append(Obstacle(
            repere=str(brut.get("id", "OBS%d" % (i + 1))),
            x0=est - largeur / 2.0, x1=est + largeur / 2.0,
            y0=nord - profondeur / 2.0, y1=nord + profondeur / 2.0,
            type_obstacle=TypeObstacle.NATURE_INCONNUE,
            provenance=Provenance.DECLARE_CLIENT,
            degagement_m=DEGAGEMENT_VILLA_M,
            regle_appliquee="obstacle déclaré par le client au lecteur de "
                            "cartes : dégagement villa %.2f m"
                            % DEGAGEMENT_VILLA_M))
    return tuple(obstacles)


def vers_entree(area, ordre="lnglat", kit=KIT_VILLA_720,
                retrait_m=RETRAIT_VILLA_M, pas_recherche_m=0.01):
    """``AreaRecord`` -> ``(EntreeCalepinage, Projection, PolitiquePas)``.

    Le repère du moteur pour la villa : ``x`` = EST (les rangées courent
    est-ouest pour des modules plein sud), ``y`` = NORD.
    """
    points = area.get("polygon", area.get("points", ()))
    if len(points) < 3:
        raise ValueError("toiture villa %r : contour de moins de 3 sommets"
                         % (area.get("id", "?"),))
    projection = projection_locale(points, ordre)
    contour = tuple(projection.vers_local(*_couple(p, ordre)) for p in points)
    rives = Rives(laterale_m=retrait_m, extremite_m=retrait_m)
    surface = SurfacePolygone(
        repere=str(area.get("id", "VILLA")), contour=contour, rives=rives,
        axe_rangee=Axe.EST_OUEST,
        pente_deg=float(area.get("tilt", 0.0) or 0.0),
        azimut_deg=float(area.get("azimuth", 180.0) or 180.0))
    parametres = Parametres(kits=(kit,), rives=rives, axe_rangee=Axe.EST_OUEST,
                            allee_m=0.0, pas_recherche_m=pas_recherche_m)
    entree = EntreeCalepinage(
        repere=surface.repere, surfaces=(surface,), kits=(kit,),
        parametres=parametres,
        obstacles=_obstacles_villa(area, projection, ordre))
    return (entree, projection, politique_villa(area))


def vers_panneaux(tables, projection, kit=KIT_VILLA_720):
    """Tables posées -> structure compatible ``PanelGrid`` (écran existant).

    Chaque panneau porte ses 4 sommets en ``[lng, lat]`` — la convention du
    lecteur de cartes, pour que rien ne change côté écran.
    """
    panneaux = []
    for i, table in enumerate(tables):
        sommets = table.polygone or ((table.x0, table.y0), (table.x1, table.y0),
                                     (table.x1, table.y1), (table.x0, table.y1))
        coins = []
        for est, nord in sommets:
            lat, lng = projection.vers_geo(est, nord)
            coins.append([lng, lat])
        panneaux.append({
            "id": "P%d" % (i + 1),
            "corners": coins,
            "widthM": kit.cote_le_long_rangee_m,
            "heightM": kit.emprise_transversale_m,
            "wc": kit.puissance_table_wc,
        })
    return tuple(panneaux)


def expliquer_ecart(entree, compte_moteur, compte_reference, impacts=()):
    """Explique un écart OBSTACLE PAR OBSTACLE — jamais « environ ».

    ``impacts`` : couples ``(repère, modules)`` mesurés en rejouant le moteur
    sans l'obstacle. La somme des impacts DOIT couvrir l'écart, sinon la phrase
    le dit : c'est un écart NON EXPLIQUÉ, et il faut le regarder.
    """
    ecart = compte_moteur - compte_reference
    lignes = ["écart moteur/référence : %+d module(s)" % ecart]
    couvert = 0
    for repere, impact in impacts:
        couvert += impact
        lignes.append("  %s : %+d module(s)" % (repere, impact))
    reste = ecart - couvert
    if reste:
        lignes.append("  RESTE NON EXPLIQUÉ : %+d module(s)" % reste)
    else:
        lignes.append("  écart intégralement expliqué obstacle par obstacle")
    return (reste == 0, tuple(lignes))
