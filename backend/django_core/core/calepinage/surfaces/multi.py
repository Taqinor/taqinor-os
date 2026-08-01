# -*- coding: utf-8 -*-
"""AOF41 — surfaces MULTI-NIVEAUX : aucune table à cheval sur une coupure.

Le bâtiment C (école) l'exige : le croquis porte une ligne interne à 31,74 qui
est un CHANGEMENT DE NIVEAU, pas une simple ligne de dessin. Une table posée à
cheval dessus serait invendable et le script d'origine devait le vérifier à la
main, planche par planche. Ici, une surface DÉCLARE ses paliers ; la coupure
entre deux paliers de niveaux différents est infranchissable par construction
et le contrôle vit dans le moteur, donc aussi sur le chemin API et le chemin
villa.

Chaque palier porte son ``niveau``, sa ``pente_deg`` et son ``azimut_deg`` :
un toit à deux pans est un multi-niveaux à deux paliers.
"""

from dataclasses import dataclass
from typing import Tuple

from core.calepinage.surfaces.base import Coupure, Surface
from core.calepinage.units import TOL_LONGUEUR_M

__all__ = ["Palier", "SurfaceMultiNiveaux"]


@dataclass(frozen=True)
class Palier:
    """Un tronçon de surface homogène en niveau / pente / azimut."""

    repere: str
    x0: float
    x1: float
    niveau: int = 0
    pente_deg: float = 0.0
    azimut_deg: float = 180.0

    def __post_init__(self):
        if self.x1 <= self.x0:
            raise ValueError("palier %s : bornes inversées" % self.repere)

    @property
    def longueur_m(self):
        return self.x1 - self.x0


@dataclass(frozen=True)
class SurfaceMultiNiveaux(Surface):
    """Paliers CONTIGUS partageant la même largeur transversale."""

    paliers: Tuple[Palier, ...] = ()
    largeur_m: float = 0.0

    def __post_init__(self):
        if len(self.paliers) < 1:
            raise ValueError("surface %s : au moins un palier" % self.repere)
        if self.largeur_m <= 0:
            raise ValueError("surface %s : largeur strictement positive"
                             % self.repere)
        ordonnes = sorted(self.paliers, key=lambda p: p.x0)
        for gauche, droite in zip(ordonnes, ordonnes[1:]):
            if droite.x0 < gauche.x1 - TOL_LONGUEUR_M:
                raise ValueError("surface %s : paliers qui se chevauchent"
                                 % self.repere)
        object.__setattr__(self, "paliers", tuple(ordonnes))

    # ------------------------------------------------------------- protocole
    def bornes_transversales(self):
        return (0.0, self.largeur_m)

    def bande(self, y0, emprise=0.0):
        ymin, ymax = self.bornes_transversales_utiles()
        if y0 < ymin - 1e-9 or y0 + emprise > ymax + 1e-9:
            return None
        return (self.paliers[0].x0, self.paliers[-1].x1)

    def coupures(self):
        """Coupures DÉCLARÉES + une coupure par changement de niveau."""
        auto = []
        for gauche, droite in zip(self.paliers, self.paliers[1:]):
            if gauche.niveau != droite.niveau:
                auto.append(Coupure(
                    repere="NIVEAU_%s_%s" % (gauche.repere, droite.repere),
                    axe="x", position=(gauche.x1 + droite.x0) / 2.0,
                    epaisseur_m=max(0.0, droite.x0 - gauche.x1)))
        return tuple(self.coupures_declarees) + tuple(auto)

    # --------------------------------------------------------------- paliers
    def palier_de(self, x):
        for p in self.paliers:
            if p.x0 - TOL_LONGUEUR_M <= x <= p.x1 + TOL_LONGUEUR_M:
                return p
        return None

    def paliers_traverses(self, x0, x1):
        """Paliers réellement RECOUVERTS par ``[x0, x1]`` (contact exclu).

        Le contact exact — une table qui DÉMARRE sur la coupure — ne compte
        pas : sans cette règle, le seul plan de pose acceptable de l'école
        (rangées calées sur le changement de niveau) serait refusé.
        """
        return tuple(p for p in self.paliers
                     if min(p.x1, x1) - max(p.x0, x0) > TOL_LONGUEUR_M)

    def table_a_cheval(self, x0, x1):
        """``True`` si une table ``[x0, x1]`` change de niveau ou sort du toit."""
        if self.enjambe_une_coupure(x0, x1):
            return True
        traverses = self.paliers_traverses(x0, x1)
        if not traverses:
            return True
        couverture = sum(min(p.x1, x1) - max(p.x0, x0) for p in traverses)
        if couverture < (x1 - x0) - TOL_LONGUEUR_M:
            return True
        return len({p.niveau for p in traverses}) > 1

    @property
    def niveaux(self):
        return tuple(sorted({p.niveau for p in self.paliers}))

    @property
    def aire_m2(self):
        return sum(p.longueur_m for p in self.paliers) * self.largeur_m
