# -*- coding: utf-8 -*-
"""CAL88 — la surface AU SOL : terrain, pas inter-rangées, taux d'occupation.

POURQUOI ELLE EXISTE
--------------------
Le moteur ne traitait QUE des surfaces de toiture et l'absence de champ au sol
était un non-objectif explicite (``docs/moteur-calepinage.md`` §6). La parité
visée est celle des outils du secteur, qui posent un champ au sol À CÔTÉ des
toitures dans le même outil. Rien du moteur ne l'interdisait : ce qui manquait
était une surface qui sache dire ce qu'un TERRAIN a de particulier.

CE QU'UN TERRAIN A DE PARTICULIER, ET C'EST TOUT
--------------------------------------------------
1. **Le pas inter-rangées n'est pas une allée de maintenance, c'est une
   contrainte SOLAIRE.** Sur un toit plat, l'allée est un choix ; au sol, deux
   rangées trop serrées s'ombrent au solstice et la centrale perd en hiver ce
   qu'elle a gagné en emprise. Le pas est donc SAISI (l'exploitant impose son
   entraxe) ou CALCULÉ par la politique anti-ombrage de CAL167, qui connaît
   l'élévation solaire du LIEU. Aucun défaut national n'est appliqué ici :
   sans entraxe saisi ET sans latitude, le calcul est REFUSÉ en nommant le
   champ manquant — le noyau ne devine jamais un lieu.
2. **Le taux d'occupation du sol (GCR) est une SORTIE, jamais une entrée.**
   Il se MESURE sur le plan réellement posé (aire de modules ÷ aire de
   terrain). L'imposer en entrée reviendrait à décider du compte avant de
   l'avoir prouvé, ce que tout ce moteur refuse.

CE QU'ELLE NE CHANGE PAS
-------------------------
Aucune surface de toiture n'est touchée, aucun golden ne bouge : le rectangle,
le polygone, l'arc et le multi-niveaux sont inchangés au bit près. Le DP, le
poseur, les garde-fous et le rendu ignorent totalement qu'un terrain existe —
c'est exactement ce que le protocole ``Surface`` promet.

POURQUOI ELLE N'EST PAS UN ``SurfacePolygone``
-----------------------------------------------
Elle en a la géométrie (un contour quelconque, trous compris) et elle
s'appuie sur les MÊMES primitives (``core.calepinage.geometrie``), mais elle
n'en hérite PAS : ``serialisation.surface_vers_dict`` reconnaît les types par
``isinstance`` et un terrain serait alors sérialisé en « polygone », en
perdant SILENCIEUSEMENT son entraxe et sa latitude. Le contrat d'échange v1
ne connaît pas le sol : il le REFUSE explicitement (``SchemaIncompatible``,
« surface non sérialisable »), ce qui est un message, pas une perte. Ouvrir le
type ``sol`` dans ``schema.json`` est le travail de la tâche qui PERSISTERA un
champ au sol — pas de celle qui le calcule.
"""

import math
from dataclasses import dataclass
from typing import Optional, Tuple

from core.calepinage.geometrie import (
    aire_polygone,
    bandes_couvertes,
    boite_englobante,
    normaliser_contour,
)
from core.calepinage.surfaces.base import Surface

__all__ = ["SurfaceSol"]


@dataclass(frozen=True)
class SurfaceSol(Surface):
    """Terrain d'une centrale au sol — ``x`` le long des rangées, ``y`` transversal.

    ``pas_inter_rangee_m`` est l'ENTRAXE de rangée à rangée (et non le vide
    entre elles) : c'est la grandeur qu'un exploitant saisit et qu'il lit sur
    un plan d'implantation. Laissé à ``None``, il est CALCULÉ par la politique
    anti-ombrage à partir de ``latitude_deg``.
    """

    contour: Tuple[Tuple[float, float], ...] = ()
    trous: Tuple[Tuple[Tuple[float, float], ...], ...] = ()
    #: Entraxe SAISI entre deux rangées (m). ``None`` = calculé à la latitude.
    pas_inter_rangee_m: Optional[float] = None
    #: Latitude du site (degrés, positif au nord). Jamais devinée.
    latitude_deg: Optional[float] = None

    def __post_init__(self):
        object.__setattr__(self, "contour", normaliser_contour(self.contour))
        object.__setattr__(self, "trous",
                           tuple(normaliser_contour(t) for t in self.trous))
        if len(self.contour) < 3:
            raise ValueError(
                "terrain %s : un contour de moins de 3 sommets ne délimite "
                "aucune surface" % self.repere)
        if self.pas_inter_rangee_m is not None \
                and self.pas_inter_rangee_m <= 0:
            raise ValueError(
                "terrain %s : champ `pas_inter_rangee_m` — l'entraxe de "
                "rangée est strictement positif" % self.repere)
        if self.latitude_deg is not None \
                and not (-90.0 <= self.latitude_deg <= 90.0):
            raise ValueError(
                "terrain %s : champ `latitude_deg` — latitude hors bornes "
                "(-90 à 90 degrés)" % self.repere)

    # ------------------------------------------------------------- protocole
    def bornes_transversales(self):
        _xmin, _xmax, ymin, ymax = boite_englobante(self.contour)
        return (ymin, ymax)

    def bandes(self, y0, emprise=0.0):
        """TOUS les intervalles ``x`` posables — un terrain en L en rend deux."""
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
        """Aire du TERRAIN (contour moins trous) — le dénominateur du GCR."""
        return aire_polygone(self.contour) - sum(aire_polygone(t)
                                                 for t in self.trous)

    # ----------------------------------------------------- propre au terrain
    def politique_pas(self, kit):
        """La politique d'espacement des rangées de CE terrain.

        * entraxe SAISI → ``AlleeFixe`` du vide correspondant (entraxe moins
          l'emprise transversale de la table) : c'est l'exploitant qui impose,
          et le moteur pose exactement ce qu'il a demandé ;
        * entraxe ABSENT → ``AntiOmbrage`` à la latitude du site (CAL167), qui
          calcule l'élévation solaire du lieu au solstice.

        Raises:
            ValueError: entraxe absent ET latitude absente (le champ manquant
                est NOMMÉ), ou entraxe plus court que l'emprise de la table.
        """
        from core.calepinage.politique_pas import AlleeFixe, AntiOmbrage

        if self.pas_inter_rangee_m is None:
            if self.latitude_deg is None:
                raise ValueError(
                    "terrain %s : champ `latitude_deg` — sans entraxe saisi, "
                    "le pas inter-rangées se calcule à partir de la LATITUDE "
                    "du site (l'ombre d'une rangée sur la suivante dépend de "
                    "l'élévation du soleil au solstice). Saisissez "
                    "`pas_inter_rangee_m` ou transmettez la latitude."
                    % self.repere)
            return AntiOmbrage(latitude_deg=self.latitude_deg)
        vide = self.pas_inter_rangee_m - kit.emprise_transversale_m
        if vide < -1e-9:
            raise ValueError(
                "terrain %s : champ `pas_inter_rangee_m` — l'entraxe saisi "
                "(%.3f m) est plus court que l'emprise transversale de la "
                "table (%.3f m) : deux rangées se chevaucheraient."
                % (self.repere, self.pas_inter_rangee_m,
                   kit.emprise_transversale_m))
        return AlleeFixe(allee_m=max(0.0, vide))

    def entraxe_m(self, kit, y0=0.0):
        """L'entraxe RÉELLEMENT appliqué (m) : emprise + vide entre rangées.

        Saisi, c'est la valeur saisie ; calculé, c'est ce que l'anti-ombrage
        impose à cette latitude. Dans les deux cas, c'est la grandeur qui se
        lit sur un plan d'implantation.
        """
        politique = self.politique_pas(kit)
        return (kit.emprise_transversale_m
                + politique.pas_apres_rangee(kit, y0))

    def rangees_theoriques(self, kit):
        """Nombre de rangées que la largeur UTILE du terrain peut porter.

        Une estimation de dimensionnement, jamais un compte publiable : le
        compte, c'est le DP qui le prouve, rangée par rangée.
        """
        ymin, ymax = self.bornes_transversales_utiles()
        largeur = max(0.0, ymax - ymin)
        if largeur < kit.emprise_transversale_m - 1e-9:
            return 0
        entraxe = self.entraxe_m(kit)
        if entraxe <= 0:
            return 0
        return 1 + int(math.floor(
            (largeur - kit.emprise_transversale_m + 1e-9) / entraxe))

    def aire_modules_m2(self, kit, modules):
        """Aire de MODULE posée (m²) — la surface de verre, pas l'emprise."""
        return modules * kit.module_long_m * kit.module_court_m

    def taux_occupation(self, kit, modules):
        """GCR MESURÉ : aire de modules ÷ aire de terrain.

        C'est une SORTIE. Elle se lit sur le plan réellement posé : un plan
        qui n'a rien posé rend ``0.0``, et c'est un zéro MESURÉ, pas un zéro
        par défaut. Un terrain d'aire nulle est impossible (le contour est
        validé à la construction), donc aucune division par zéro n'est
        possible ici.
        """
        return self.aire_modules_m2(kit, modules) / self.aire_m2

    def taux_occupation_theorique(self, kit):
        """GCR d'un champ INFINI au même entraxe — le repère de comparaison.

        ``aire de modules d'une table ÷ (entraxe × pas le long de la rangée)``
        : c'est le taux que la maille d'implantation impose, indépendamment
        des rives et de la forme du terrain. L'écart avec le GCR mesuré dit ce
        que la forme du terrain coûte.
        """
        maille = self.entraxe_m(kit) * kit.cote_le_long_rangee_m
        if maille <= 0:
            return 0.0
        return self.aire_modules_m2(kit, kit.modules_par_table) / maille
