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

from core.calepinage.types import PolitiquePas

__all__ = [
    "AlleeFixe", "AntiOmbrage", "Affleurant", "ELEVATION_DIMENSIONNEMENT_DEG",
    "politique_par_defaut",
]

#: Élévation solaire de DIMENSIONNEMENT au solstice d'hiver (degrés).
#: Valeur de référence du cerveau TypeScript : elle n'est pas l'élévation
#: maximale de midi mais celle retenue pour garantir une plage utile autour du
#: midi solaire. Elle est PARAMÉTRABLE — jamais un littéral enfoui.
ELEVATION_DIMENSIONNEMENT_DEG = 21.0


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
    """

    elevation_deg: float = ELEVATION_DIMENSIONNEMENT_DEG
    marge_m: float = 0.05
    allee_minimale_m: float = 0.0
    code: str = "ANTI_OMBRAGE"

    def __post_init__(self):
        if not (0.0 < self.elevation_deg < 90.0):
            raise ValueError("élévation de dimensionnement hors bornes")
        if self.marge_m < 0:
            raise ValueError("marge négative")

    def hauteur_module_m(self, kit):
        """Hauteur du haut du module au-dessus du plan (côté pente × sin)."""
        return kit.cote_dans_la_pente_m * math.sin(
            math.radians(kit.inclinaison_deg))

    def longueur_ombre_m(self, kit):
        """Ombre portée par UNE rangée à l'élévation de dimensionnement."""
        return self.hauteur_module_m(kit) / math.tan(
            math.radians(self.elevation_deg))

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
