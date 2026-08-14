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

from core.calepinage.orientation import axe_rangee_impose
from core.calepinage.politique_pas import Affleurant, AntiOmbrage
from core.calepinage.serialisation import EntreeCalepinage
from core.calepinage.surfaces.polygone import SurfacePolygone
from core.calepinage.types import (
    KIT_VILLA_720,
    KIT_VILLA_EW,
    Axe,
    Obstacle,
    Parametres,
    Provenance,
    Rives,
    TypeObstacle,
    remplacer,
)

__all__ = [
    "RAYON_TERRE_M", "RETRAIT_VILLA_M", "DEGAGEMENT_VILLA_M", "Projection",
    "projection_locale", "vers_entree", "vers_panneaux", "politique_villa",
    "expliquer_ecart", "FAMILLE_SUD", "FAMILLE_EST_OUEST", "FAMILLES_VILLA",
    "kit_de_famille", "kit_sud", "kit_est_ouest",
]

#: Rayon terrestre moyen (WGS84 demi-grand axe) — projection ENU locale.
RAYON_TERRE_M = 6378137.0
#: Retrait de rive villa (setback) et dégagement autour d'un obstacle déclaré.
RETRAIT_VILLA_M = 0.50
DEGAGEMENT_VILLA_M = 0.30

#: PV66 — les DEUX familles de pose villa, nommées comme sur le site
#: (``ConfigFamily = 'south' | 'eastwest'``).
FAMILLE_SUD = "SUD"
FAMILLE_EST_OUEST = "EST_OUEST"
FAMILLES_VILLA = (FAMILLE_SUD, FAMILLE_EST_OUEST)


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


# ============================================================ familles de kit
#
# PV66 — deux façons de couvrir la MÊME villa avec le MÊME panneau :
#
# * **SUD** — un module par table, plein sud, rangées est-ouest : le rendement
#   par panneau est maximal, la toiture en loge moins ;
# * **EST-OUEST** — deux modules dos-à-dos en chevron, faîtage nord-sud,
#   rangées nord-sud : chaque panneau produit un peu moins mais la toiture en
#   loge nettement plus, et la production est étalée matin/soir.
#
# Le choix est un ARGUMENT, jamais une devinette : ni l'inclinaison, ni le
# nombre de modules par table ne se déduisent d'un ``AreaRecord``. Sans famille
# demandée, RIEN ne change — le kit reçu est utilisé tel quel.


def kit_sud(base=KIT_VILLA_720):
    """Le kit SUD (un module) portant la géométrie de module de ``base``.

    ``base`` déjà à un module est rendu TEL QUEL — c'est le chemin par défaut
    de la villa et le kit dérivé d'un produit (PV12) : sa géométrie, son SKU et
    son inclinaison sont déjà un choix, on ne les réécrit pas.
    """
    if not base.dos_a_dos:
        return base
    return remplacer(
        KIT_VILLA_720,
        code="%s_SUD" % base.code,
        libelle="Module unique plein sud dérivé de %s" % base.libelle,
        module_long_m=base.module_long_m,
        module_court_m=base.module_court_m,
        puissance_module_wc=base.puissance_module_wc)


def kit_est_ouest(base=KIT_VILLA_720):
    """Le CHEVRON dos-à-dos est-ouest portant la géométrie de ``base``.

    Le gabarit est ``KIT_VILLA_EW`` : on n'y remplace que les trois grandeurs
    qui appartiennent au module vendu (longueur, largeur, puissance). Tout le
    reste — deux modules par table, paysage, 10°, aucun jeu de faîte — est la
    définition MÊME du chevron et ne dépend pas du panneau qu'on y pose.

    Conséquence directe : le panneau du catalogue (PV12) s'applique aux DEUX
    familles. Un ``base`` déjà dos-à-dos est rendu tel quel (c'est déjà un
    chevron, le redécrire inventerait un second gabarit).
    """
    if base.dos_a_dos:
        return base
    if (base.module_long_m == KIT_VILLA_EW.module_long_m
            and base.module_court_m == KIT_VILLA_EW.module_court_m
            and base.puissance_module_wc == KIT_VILLA_EW.puissance_module_wc):
        return KIT_VILLA_EW
    return remplacer(
        KIT_VILLA_EW,
        code="%s_EW" % base.code,
        libelle="Chevron dos-à-dos est-ouest dérivé de %s" % base.libelle,
        module_long_m=base.module_long_m,
        module_court_m=base.module_court_m,
        puissance_module_wc=base.puissance_module_wc)


def kit_de_famille(famille, base=KIT_VILLA_720):
    """Rend le kit de la famille demandée — ``None`` laisse ``base`` INTACT.

    C'est le point de composition avec le kit-produit de PV12 : l'appelant
    résout d'abord SON kit (kit explicite > fiche technique du produit > kit
    villa par défaut), puis cette fonction lui donne la forme de table de la
    famille choisie. L'ordre importe : la famille change la TABLE, jamais le
    panneau — sans quoi choisir « est-ouest » changerait en douce le module
    facturé au client.
    """
    if famille is None:
        return base
    code = str(famille).strip().upper()
    if code in ("", FAMILLE_SUD, "SOUTH"):
        return kit_sud(base)
    if code in (FAMILLE_EST_OUEST, "EST-OUEST", "EASTWEST", "EAST_WEST", "EW"):
        return kit_est_ouest(base)
    raise ValueError("famille de pose villa inconnue : %r (%s)"
                     % (famille, " | ".join(FAMILLES_VILLA)))


def politique_villa(area):
    """Toit PLAT -> anti-ombrage ; toit en PENTE -> pose affleurante."""
    plat = area.get("flat", area.get("plat", True))
    pente = float(area.get("tilt", area.get("pente_deg", 0.0)) or 0.0)
    if plat and pente < 5.0:
        return AntiOmbrage()
    return Affleurant()


def _vers_repere(est, nord, axe):
    """``(est, nord)`` -> ``(x, y)`` du moteur, où ``x`` court LE LONG des rangées.

    ``SurfacePolygone`` n'interprète PAS ``axe_rangee`` : son contour est déjà
    exprimé dans le repère de la rangée (``x`` le long, ``y`` en travers).
    Déclarer un axe nord-sud en laissant ``x`` = est produirait des rangées
    est-ouest étiquetées nord-sud — plausible et faux, exactement la classe de
    bug que ce paquet refuse. La conversion est donc faite ICI, une fois.
    """
    return (nord, est) if axe is Axe.NORD_SUD else (est, nord)


def _obstacles_villa(area, projection, ordre, axe=Axe.EST_OUEST):
    """``centre + dimensions`` -> rectangles, provenance DÉCLARÉE PAR LE CLIENT.

    ``widthM`` est une largeur EST-OUEST et ``heightM`` une profondeur
    NORD-SUD : sur des rangées nord-sud, les deux échangent leur rôle en même
    temps que les coordonnées.
    """
    obstacles = []
    for i, brut in enumerate(area.get("obstacles", ()) or ()):
        centre = brut.get("center", brut.get("centre"))
        if centre is None:
            continue
        lat, lng = _couple(centre, ordre)
        est, nord = projection.vers_local(lat, lng)
        x, y = _vers_repere(est, nord, axe)
        largeur = float(brut.get("widthM", brut.get("largeur_m", 1.0)))
        profondeur = float(brut.get("heightM", brut.get("profondeur_m", 1.0)))
        demi_x, demi_y = _vers_repere(largeur / 2.0, profondeur / 2.0, axe)
        obstacles.append(Obstacle(
            repere=str(brut.get("id", "OBS%d" % (i + 1))),
            x0=x - demi_x, x1=x + demi_x,
            y0=y - demi_y, y1=y + demi_y,
            type_obstacle=TypeObstacle.NATURE_INCONNUE,
            provenance=Provenance.DECLARE_CLIENT,
            degagement_m=DEGAGEMENT_VILLA_M,
            regle_appliquee="obstacle déclaré par le client au lecteur de "
                            "cartes : dégagement villa %.2f m"
                            % DEGAGEMENT_VILLA_M))
    return tuple(obstacles)


def vers_entree(area, ordre="lnglat", kit=KIT_VILLA_720,
                retrait_m=RETRAIT_VILLA_M, pas_recherche_m=0.01,
                famille=None):
    """``AreaRecord`` -> ``(EntreeCalepinage, Projection, PolitiquePas)``.

    Le repère du moteur a TOUJOURS ``x`` le long des rangées. En pose SUD
    (module unique plein sud) les rangées courent est-ouest : ``x`` = EST,
    ``y`` = NORD, comme depuis AOF162. En pose EST-OUEST (chevron dos-à-dos,
    PV66) le faîtage est nord-sud, donc les rangées aussi : ``x`` = NORD et les
    chevrons s'empilent vers l'est.

    ``famille`` (PV66) — ``None`` (défaut) laisse le kit reçu INTACT et rend un
    calcul bit-à-bit identique à l'existant ; ``SUD``/``EST_OUEST`` demandent
    explicitement une famille de table. L'axe des rangées n'est jamais saisi :
    il est DÉRIVÉ du kit par ``orientation.axe_rangee_impose``, la seule source
    de vérité du dépôt sur ce qui est constructible.
    """
    points = area.get("polygon", area.get("points", ()))
    if len(points) < 3:
        raise ValueError("toiture villa %r : contour de moins de 3 sommets"
                         % (area.get("id", "?"),))
    kit = kit_de_famille(famille, kit)
    azimut = float(area.get("azimuth", 180.0) or 180.0)
    axe = axe_rangee_impose(kit, azimut)
    projection = projection_locale(points, ordre)
    contour = tuple(_vers_repere(*projection.vers_local(*_couple(p, ordre)),
                                 axe=axe)
                    for p in points)
    rives = Rives(laterale_m=retrait_m, extremite_m=retrait_m)
    surface = SurfacePolygone(
        repere=str(area.get("id", "VILLA")), contour=contour, rives=rives,
        axe_rangee=axe,
        pente_deg=float(area.get("tilt", 0.0) or 0.0),
        azimut_deg=azimut)
    parametres = Parametres(kits=(kit,), rives=rives, axe_rangee=axe,
                            allee_m=0.0, pas_recherche_m=pas_recherche_m)
    entree = EntreeCalepinage(
        repere=surface.repere, surfaces=(surface,), kits=(kit,),
        parametres=parametres,
        obstacles=_obstacles_villa(area, projection, ordre, axe))
    return (entree, projection, politique_villa(area))


def vers_panneaux(tables, projection, kit=KIT_VILLA_720, axe=Axe.EST_OUEST):
    """Tables posées -> structure compatible ``PanelGrid`` (écran existant).

    Chaque panneau porte ses 4 sommets en ``[lng, lat]`` — la convention du
    lecteur de cartes, pour que rien ne change côté écran. ``axe`` est celui
    des rangées : il défait exactement la transposition de ``_vers_repere``,
    sinon un chevron est-ouest se dessinerait à 90° de là où il est posé.
    """
    panneaux = []
    for i, table in enumerate(tables):
        sommets = table.polygone or ((table.x0, table.y0), (table.x1, table.y0),
                                     (table.x1, table.y1), (table.x0, table.y1))
        coins = []
        for x, y in sommets:
            est, nord = _vers_repere(x, y, axe)
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
