# -*- coding: utf-8 -*-
"""AOF38 — le rectangle : implémentation de RÉFÉRENCE du protocole ``Surface``.

C'est la surface la plus simple du moteur et c'est délibéré : elle sert de
témoin à la suite de conformité que toute forme future (polygone, arc,
multi-niveaux) doit passer. Le bâtiment C de FRDISI (école, 51,10 × 25,62)
en est un cas réel.
"""

from dataclasses import dataclass

from core.calepinage.surfaces.base import Surface

__all__ = ["SurfaceRectangle"]


@dataclass(frozen=True)
class SurfaceRectangle(Surface):
    """Rectangle ``longueur_m`` (le long des rangées) × ``largeur_m`` (transversal)."""

    longueur_m: float = 0.0
    largeur_m: float = 0.0

    def __post_init__(self):
        if self.longueur_m <= 0 or self.largeur_m <= 0:
            raise ValueError("rectangle %s : dimensions strictement positives"
                             % self.repere)

    def bornes_transversales(self):
        return (0.0, self.largeur_m)

    def bande(self, y0, emprise=0.0):
        ymin, ymax = self.bornes_transversales_utiles()
        if y0 < ymin - 1e-9 or y0 + emprise > ymax + 1e-9:
            return None
        return (0.0, self.longueur_m)

    @property
    def aire_m2(self):
        return self.longueur_m * self.largeur_m
