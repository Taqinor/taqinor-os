# -*- coding: utf-8 -*-
"""AOF40 — l'ARC : géométrie courbe de PREMIÈRE CLASSE (bâtiment B, FRDISI).

Repère de l'arc, dans la convention unifiée du moteur :

* ``x`` — abscisse CURVILIGNE sur le bord EXTÉRIEUR (le ``s`` du script
  d'origine) : c'est là que les tables se suivent ;
* ``y`` — ordonnée depuis le bord INTÉRIEUR (0 = rayon intérieur 263,10 ;
  10,90 = rayon extérieur 274,0) : c'est là que les rangées se rangent.

Relevé : R_ext 274,0 · largeur 10,90 · R_int 263,10 ; développé muret-à-muret
20,55 + 0,45 + 23,00 + 0,45 + 23,60 = 68,05 m. Les murets au ras (0,45) sont
des COUPURES : aucune rangée n'est à cheval, chaque segment a SON plan de pose
et SES rives d'extrémité (0,35).

**LE VRAI BUG CORRIGÉ.** L'ancien modèle posait les tables JOINTIVES en
abscisse développée. Une table est un rectangle RIGIDE : posée au repère
tangent local, son emprise angulaire est fixée par son centre, si bien que deux
tables voisines se RECOUVRENT de 2 à 9 cm au rayon INTÉRIEUR. Le pas de pose
vaut donc ``mod_l × R_ext / (R_int + y0)``. Coût assumé : 4 modules ; le
recouvrement évité est RECALCULÉ et publié (min/max en centimètres).

**Les dégagements sont convertis, et deux assertions le PROUVENT à chaque
exécution :** 0,35 en abscisse développée vaut 0,336 m RÉELS au rayon
intérieur (≥ 0,30 exigé) ; 0,53 vaut 0,509 m (≥ 0,50). Un 0,30 en abscisse
n'en vaudrait que 0,288 — sous la règle, et personne ne le verrait.
"""

import math
from dataclasses import dataclass

from core.calepinage.surfaces.base import Coupure, Surface

__all__ = ["ErreurArc", "SurfaceArc", "SEGMENTS_FRDISI"]

#: Développés des 3 segments du bâtiment B et épaisseur des murets (relevé).
SEGMENTS_FRDISI = (20.55, 23.00, 23.60)
MURET_FRDISI = 0.45


class ErreurArc(ValueError):
    """Géométrie d'arc incohérente — jamais un plan silencieusement faux."""


@dataclass(frozen=True)
class SurfaceArc(Surface):
    """Arc de rayon extérieur ``rayon_ext_m``, de largeur ``largeur_m``."""

    rayon_ext_m: float = 274.0
    largeur_m: float = 10.90
    developpe_m: float = 68.05

    def __post_init__(self):
        if self.largeur_m <= 0 or self.rayon_ext_m <= self.largeur_m:
            raise ErreurArc("arc %s : rayon extérieur incompatible avec la "
                            "largeur" % self.repere)
        if self.developpe_m <= 0:
            raise ErreurArc("arc %s : développé strictement positif" % self.repere)

    # -------------------------------------------------------------- rayons
    @property
    def rayon_int_m(self):
        return self.rayon_ext_m - self.largeur_m

    def rayon(self, y):
        """Rayon RÉEL d'une ordonnée transversale (0 = bord intérieur)."""
        return self.rayon_int_m + y

    # ------------------------------------------------------------- protocole
    def bornes_transversales(self):
        return (0.0, self.largeur_m)

    def bande(self, y0, emprise=0.0):
        ymin, ymax = self.bornes_transversales_utiles()
        if y0 < ymin - 1e-9 or y0 + emprise > ymax + 1e-9:
            return None
        return (0.0, self.developpe_m)

    def pas_de_pose(self, kit, y0):
        """Pas en abscisse développée qui INTERDIT le recouvrement intérieur.

        Deux tables voisines partagent une génératrice : c'est au rayon
        INTÉRIEUR de la rangée que l'emprise angulaire est la plus large.
        """
        return kit.cote_le_long_rangee_m * self.rayon_ext_m / self.rayon(y0)

    def vers_feuille(self, coord_locale):
        """``(s, y)`` -> point de feuille (le ``P`` du script d'origine)."""
        s, y = coord_locale
        r = self.rayon(y)
        f = self.angle(s)
        y_zero = self.rayon_ext_m * math.cos(self.angle_total / 2.0)
        return (self.origine[0] + r * math.sin(f),
                self.origine[1] + r * math.cos(f) - y_zero)

    # ---------------------------------------------------------- primitives
    @property
    def angle_total(self):
        """Angle au centre couvert par le développé (radians)."""
        return self.developpe_m / self.rayon_ext_m

    def angle(self, s):
        """``phi`` du script : angle d'une abscisse développée, centré."""
        return (s - self.developpe_m / 2.0) / self.rayon_ext_m

    def polygone_table(self, s0, s1, y0, y1):
        """``rigid`` du script : rectangle RIGIDE au repère TANGENT du centre."""
        sc, yc = (s0 + s1) / 2.0, (y0 + y1) / 2.0
        f = self.angle(sc)
        cx, cy = self.vers_feuille((sc, yc))
        tang = (math.cos(f), -math.sin(f))
        norm = (math.sin(f), math.cos(f))
        demi_s, demi_y = (s1 - s0) / 2.0, (y1 - y0) / 2.0
        return tuple(
            (cx + a * demi_s * tang[0] + b * demi_y * norm[0],
             cy + a * demi_s * tang[1] + b * demi_y * norm[1])
            for a, b in ((-1, -1), (1, -1), (1, 1), (-1, 1)))

    def points_arc(self, s0, s1, y, n=80):
        """``arcpts`` du script : polyligne d'un bord courbe (pour le dessin)."""
        return tuple(self.vers_feuille((s0 + (s1 - s0) * i / float(n), y))
                     for i in range(n + 1))

    # ----------------------------------------------------- dégagements réels
    def degagement_reel(self, degagement_abscisse, y0=0.0):
        """Un dégagement EXPRIMÉ en abscisse développée vaut moins en mètres
        réels au rayon intérieur : c'est là qu'il faut le vérifier."""
        return degagement_abscisse * self.rayon(y0) / self.rayon_ext_m

    def degagement_abscisse_pour(self, degagement_reel_m, y0=0.0):
        """Abscisse développée nécessaire pour tenir ``degagement_reel_m``."""
        return degagement_reel_m * self.rayon_ext_m / self.rayon(y0)

    def verifier_degagement(self, degagement_abscisse, exige_reel_m, y0=0.0,
                            repere=""):
        """LÈVE si le dégagement ne tient pas en MÈTRES RÉELS.

        C'est l'assertion du script d'origine, remontée dans le moteur : elle
        s'exécute en production, pas seulement dans un script de planche.
        """
        reel = self.degagement_reel(degagement_abscisse, y0)
        if reel < exige_reel_m - 1e-9:
            raise ErreurArc(
                "dégagement %s : %.3f m en abscisse développée ne vaut que "
                "%.3f m RÉELS au rayon %.2f (exigé %.2f m)"
                % (repere or "(sans repère)", degagement_abscisse, reel,
                   self.rayon(y0), exige_reel_m))
        return reel

    # ----------------------------------------------------- recouvrement évité
    def recouvrement_evite_m(self, kit, y0):
        """Ce que l'ANCIEN modèle recouvrait à cette rangée (mètres)."""
        return self.pas_de_pose(kit, y0) - kit.cote_le_long_rangee_m

    def recouvrements_cm(self, paires_kit_rangee):
        """``(min, max)`` en CENTIMÈTRES sur un jeu ``(kit, y0)`` — publiable."""
        valeurs = [100.0 * self.recouvrement_evite_m(kit, y0)
                   for kit, y0 in paires_kit_rangee]
        if not valeurs:
            return (0.0, 0.0)
        return (min(valeurs), max(valeurs))

    @property
    def aire_m2(self):
        """Aire réelle de la couronne (jamais utilisée pour compter)."""
        return self.angle_total * (self.rayon_ext_m ** 2
                                   - self.rayon_int_m ** 2) / 2.0


def arc_frdisi(repere="BAT_B_ARC", rives=None):
    """L'arc du bâtiment B, murets déclarés en COUPURES (aucune table à cheval)."""
    positions = []
    curseur = 0.0
    for i, longueur in enumerate(SEGMENTS_FRDISI[:-1]):
        curseur += longueur
        positions.append(Coupure(repere="MURET_%d" % (i + 1), axe="x",
                                 position=curseur + MURET_FRDISI / 2.0,
                                 epaisseur_m=MURET_FRDISI))
        curseur += MURET_FRDISI
    developpe = curseur + SEGMENTS_FRDISI[-1]
    champs = dict(repere=repere, rayon_ext_m=274.0, largeur_m=10.90,
                  developpe_m=developpe, coupures_declarees=tuple(positions))
    if rives is not None:
        champs["rives"] = rives
    return SurfaceArc(**champs)
