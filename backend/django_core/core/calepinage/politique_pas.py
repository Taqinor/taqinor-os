# -*- coding: utf-8 -*-
"""AOF46 — la politique de PAS : ce qui unifie l'appel d'offres et la VILLA.

Le DP consomme ``pas_apres_rangee(kit, y0)`` et JAMAIS un scalaire ``allee``.
C'est la SEULE différence structurelle entre les deux métiers :

* **AO** — allée constante ; les tables dos-à-dos à 15° ne s'ombrent pas entre
  elles (chaque table a une face est et une face ouest), donc l'espacement est
  un choix de maintenance, pas de physique ;
* **VILLA** — pas variable ANTI-OMBRAGE : au solstice d'hiver, une rangée
  projette son ombre sur la suivante ; le pas se calcule
  (``profondeur projetée + longueur d'ombre + marge``), exactement comme le
  cerveau TypeScript du site (``roofPro2.ts``) ;
* **AFFLEURANT** — toiture en pente : les modules sont posés jointifs, il n'y a
  pas d'allée du tout.

Absorber la différence ici, au lieu de juxtaposer deux moteurs, donne
GRATUITEMENT à l'AO la capacité anti-ombrage le jour où une toiture plein sud
l'exige — et à la villa tout l'appareillage de preuve de l'AO.
"""

import math
from dataclasses import dataclass
from typing import Optional

from core.calepinage.types import PolitiquePas

__all__ = [
    "AlleeFixe", "AntiOmbrage", "Affleurant", "ELEVATION_DIMENSIONNEMENT_DEG",
    "DECLINAISON_SOLSTICE_DEG", "HEURE_SOLAIRE_DIMENSIONNEMENT",
    "ELEVATION_PLANCHER_DEG", "position_solaire_solstice",
    "politique_par_defaut",
]

#: Élévation solaire de DIMENSIONNEMENT au solstice d'hiver (degrés).
#: Valeur de référence du cerveau TypeScript : elle n'est pas l'élévation
#: maximale de midi mais celle retenue pour garantir une plage utile autour du
#: midi solaire. Elle est PARAMÉTRABLE — jamais un littéral enfoui.
#:
#: PV65 : c'est une valeur de RÉFÉRENCE, pas une vérité de site — elle vaut le
#: Maroc « moyen ». Une ``AntiOmbrage`` qui reçoit sa ``latitude_deg`` calcule
#: l'élévation du LIEU (Agadir n'est pas Tanger) ; sans latitude, cette
#: constante s'applique, à l'identique de tout ce qui a déjà été publié.
ELEVATION_DIMENSIONNEMENT_DEG = 21.0

#: Déclinaison solaire au solstice d'hiver (hémisphère nord), en degrés.
DECLINAISON_SOLSTICE_DEG = -23.44

#: Heure SOLAIRE de dimensionnement : 10 h, le point le plus défavorable de la
#: fenêtre de travail 10 h - 14 h. Midi solaire donnerait une règle plus dense
#: — donc des rangées plus serrées, donc de l'ombre entre 10 h et midi.
HEURE_SOLAIRE_DIMENSIONNEMENT = 10.0

#: Garde-fou « soleil très bas » : sous 5°, la tangente explose et le pas de
#: rangée deviendrait absurde (une latitude polaire rendrait une toiture
#: infinie). Le cerveau TypeScript porte exactement le même plancher.
ELEVATION_PLANCHER_DEG = 5.0


def _borner(valeur, bas=-1.0, haut=1.0):
    """Ramène un sinus dans [-1, 1] : l'arrondi flottant sort du domaine."""
    return max(bas, min(haut, valeur))


def position_solaire_solstice(latitude_deg,
                              heure_solaire=HEURE_SOLAIRE_DIMENSIONNEMENT):
    """(élévation, azimut depuis le SUD) en degrés, au solstice d'hiver.

    Portage FIDÈLE du cerveau TypeScript du site (``estimatorBrainV2.ts``,
    ``sunPositionWinterSolstice``) : le site et l'ERP doivent espacer les
    rangées de la MÊME façon, sinon la même villa reçoit deux calepinages
    selon l'écran qui l'a produite.

        sin α = sin φ · sin δ + cos φ · cos δ · cos h
        sin γ = − cos δ · sin h / cos α

    avec φ la latitude, δ la déclinaison du solstice et h l'angle horaire
    (15° par heure depuis le midi solaire).
    """
    phi = math.radians(latitude_deg)
    delta = math.radians(DECLINAISON_SOLSTICE_DEG)
    angle_horaire = math.radians(15.0 * (heure_solaire - 12.0))
    sin_alpha = (math.sin(phi) * math.sin(delta)
                 + math.cos(phi) * math.cos(delta) * math.cos(angle_horaire))
    alpha = math.asin(_borner(sin_alpha))
    cos_alpha = math.cos(alpha)
    if abs(cos_alpha) < 1e-12:
        # Soleil au zénith : l'azimut n'est plus défini, l'ombre est nulle.
        return math.degrees(alpha), 0.0
    sin_gamma = -math.cos(delta) * math.sin(angle_horaire) / cos_alpha
    return math.degrees(alpha), math.degrees(math.asin(_borner(sin_gamma)))


@dataclass(frozen=True)
class AlleeFixe(PolitiquePas):
    """Allée CONSTANTE — la politique de l'appel d'offres."""

    allee_m: float = 0.60
    code: str = "ALLEE_FIXE"

    def __post_init__(self):
        if self.allee_m < 0:
            raise ValueError("allée négative")

    def pas_apres_rangee(self, kit, y0):
        return self.allee_m

    def allee_minimale(self):
        return self.allee_m


@dataclass(frozen=True)
class AntiOmbrage(PolitiquePas):
    """Pas ANTI-OMBRAGE au solstice d'hiver — la politique de la villa.

    ``pas_apres_rangee`` rend le VIDE entre deux rangées ; le pas de rangée
    complet vaut ``emprise + pas_apres_rangee``, soit exactement
    ``profondeur projetée + longueur d'ombre + marge`` du calcul de référence.

    **PV65 — l'élévation peut venir du LIEU.** ``latitude_deg`` renseignée, le
    soleil de dimensionnement est calculé (déclinaison du solstice + angle
    horaire de 10 h) au lieu d'être lu dans une constante nationale : à Agadir
    (30,4°) le soleil monte plus haut qu'à Tanger (35,8°), l'ombre est plus
    courte et la toiture porte donc plus de rangées. Sans latitude, RIEN ne
    change : la constante historique s'applique et les comptes déjà publiés
    restent reproductibles au bit près.
    """

    elevation_deg: float = ELEVATION_DIMENSIONNEMENT_DEG
    marge_m: float = 0.05
    allee_minimale_m: float = 0.0
    #: Latitude du site (degrés, positif au nord). ``None`` = valeur nationale.
    latitude_deg: Optional[float] = None
    heure_solaire: float = HEURE_SOLAIRE_DIMENSIONNEMENT
    code: str = "ANTI_OMBRAGE"

    def __post_init__(self):
        if not (0.0 < self.elevation_deg < 90.0):
            raise ValueError("élévation de dimensionnement hors bornes")
        if self.marge_m < 0:
            raise ValueError("marge négative")
        if self.latitude_deg is not None and not (-90.0 <= self.latitude_deg
                                                  <= 90.0):
            raise ValueError("latitude hors bornes (-90 à 90 degrés)")
        if not (0.0 <= self.heure_solaire <= 24.0):
            raise ValueError("heure solaire hors bornes (0 à 24)")

    def hauteur_module_m(self, kit):
        """Hauteur du haut du module au-dessus du plan (côté pente × sin)."""
        return kit.cote_dans_la_pente_m * math.sin(
            math.radians(kit.inclinaison_deg))

    def elevation_effective_deg(self):
        """L'élévation RETENUE : celle du lieu, ou la constante nationale."""
        if self.latitude_deg is None:
            return self.elevation_deg
        alpha, _azimut = position_solaire_solstice(self.latitude_deg,
                                                   self.heure_solaire)
        return max(ELEVATION_PLANCHER_DEG, alpha)

    def longueur_ombre_m(self, kit):
        """Ombre portée par UNE rangée à l'élévation de dimensionnement.

        Sans latitude, le calcul est celui d'avant PV65, à l'expression près :
        c'est ce qui garantit que les golden villa restent verts sans être
        régénérés. Avec latitude, l'ombre porte AUSSI la composante
        directionnelle ``|cos γ|`` du soleil — le même terme que le cerveau
        TypeScript (``shadeLengthM``), car à 10 h le soleil n'est pas au sud
        et une ombre projetée droit vers le nord surestimerait l'espacement.
        """
        hauteur = self.hauteur_module_m(kit)
        if self.latitude_deg is None:
            return hauteur / math.tan(math.radians(self.elevation_deg))
        _alpha, azimut = position_solaire_solstice(self.latitude_deg,
                                                   self.heure_solaire)
        direction = abs(math.cos(math.radians(azimut)))
        return max(0.0, hauteur * direction / math.tan(
            math.radians(self.elevation_effective_deg())))

    def pas_de_rangee_m(self, kit):
        """Pas COMPLET de rangée (profondeur + ombre + marge) — publiable."""
        return (kit.emprise_transversale_m + self.longueur_ombre_m(kit)
                + self.marge_m)

    def pas_apres_rangee(self, kit, y0):
        return max(self.allee_minimale_m,
                   self.longueur_ombre_m(kit) + self.marge_m)

    def allee_minimale(self):
        return self.allee_minimale_m


@dataclass(frozen=True)
class Affleurant(PolitiquePas):
    """Pose JOINTIVE sur toiture en pente — aucune allée."""

    jeu_m: float = 0.0
    code: str = "AFFLEURANT"

    def __post_init__(self):
        if self.jeu_m < 0:
            raise ValueError("jeu négatif")

    def pas_apres_rangee(self, kit, y0):
        return self.jeu_m

    def allee_minimale(self):
        return self.jeu_m


def politique_par_defaut(parametres):
    """``AlleeFixe`` construite depuis les paramètres — la non-régression AO."""
    return AlleeFixe(allee_m=parametres.allee_m)
