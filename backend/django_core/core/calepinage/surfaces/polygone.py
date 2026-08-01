# -*- coding: utf-8 -*-
"""AOF39 — polygone quelconque : le L en est un cas, pas une exception.

Le moteur d'origine découpait l'aile en L en DEUX bandes rectangulaires
indépendantes (barre + aile), chacune avec ses propres rives. Chaque rive
ajoutée à la jonction est une perte SÈCHE : une rangée qui reste à l'ouest de
l'aile descend en réalité d'un seul tenant de la barre dans l'aile. La
planche V2 l'a corrigé à la main avec une fonction ``band(x0)`` écrite pour ce
bâtiment-là ; ici c'est le contour lui-même qui répond, pour n'importe quelle
forme concave, trous compris.
"""

from dataclasses import dataclass
from typing import Tuple

from core.calepinage.geometrie import (
    aire_polygone,
    bandes_couvertes,
    boite_englobante,
    normaliser_contour,
)
from core.calepinage.surfaces.base import Surface

__all__ = ["SurfacePolygone"]


@dataclass(frozen=True)
class SurfacePolygone(Surface):
    """Contour quelconque ``(x, y)`` — ``x`` le long des rangées, ``y`` transversal."""

    contour: Tuple[Tuple[float, float], ...] = ()
    trous: Tuple[Tuple[Tuple[float, float], ...], ...] = ()

    def __post_init__(self):
        object.__setattr__(self, "contour", normaliser_contour(self.contour))
        object.__setattr__(self, "trous",
                           tuple(normaliser_contour(t) for t in self.trous))

    # ------------------------------------------------------------- protocole
    def bornes_transversales(self):
        _xmin, _xmax, ymin, ymax = boite_englobante(self.contour)
        return (ymin, ymax)

    def bandes(self, y0, emprise=0.0):
        """TOUS les intervalles ``x`` posables par une rangée ``[y0, y0+emprise]``.

        Un contour en U rend plusieurs intervalles : le compteur les traite
        tous, ce qu'un ``bande()`` scalaire ne saurait pas exprimer.
        """
        ymin, ymax = self.bornes_transversales_utiles()
        if y0 < ymin - 1e-9 or y0 + emprise > ymax + 1e-9:
            return ()
        return bandes_couvertes(self.contour, self.trous, y0, y0 + emprise)

    def bande(self, y0, emprise=0.0):
        """Intervalle posable le PLUS LONG (contrat scalaire du protocole)."""
        familles = self.bandes(y0, emprise)
        if not familles:
            return None
        return max(familles, key=lambda ab: ab[1] - ab[0])

    @property
    def aire_m2(self):
        return aire_polygone(self.contour) - sum(aire_polygone(t)
                                                 for t in self.trous)
