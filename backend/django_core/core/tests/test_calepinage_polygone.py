# -*- coding: utf-8 -*-
"""AOF39 — le polygone quelconque, et la PREUVE que découper le L coûte cher.

Repère du moteur : ``x`` court le long des rangées (nord-sud sur l'aile en L),
``y`` est la coordonnée transversale (est-ouest) qui range les rangées.
"""

import math
import unittest

from core.calepinage.geometrie import (
    bandes_couvertes,
    intersection_intervalles,
    intervalles_a_y,
    point_dans_polygone,
)
from core.calepinage.surfaces.polygone import SurfacePolygone
from core.calepinage.surfaces.rectangle import SurfaceRectangle
from core.calepinage.types import KIT_AO_PORTRAIT, Rives
from core.tests.test_calepinage_surfaces import ConformiteSurface

# ------------------------------------------------------------ aile en L FRDISI
BARRE_LONG = 47.08          # développé est-ouest de la barre (transversal ici)
BARRE_LARG = 10.76          # profondeur nord-sud de la barre
AILE_LARG = 11.2            # largeur est-ouest de l'aile
AILE_LONG = 29.74           # descente nord-sud de l'aile

#: contour (x, y) — x nord-sud (le long des rangées), y est-ouest (transversal)
CONTOUR_L = (
    (BARRE_LARG, 0.0), (BARRE_LARG, BARRE_LONG), (0.0, BARRE_LONG),
    (0.0, AILE_LARG), (-AILE_LONG, AILE_LARG), (-AILE_LONG, 0.0),
)

RIVES = Rives(laterale_m=0.35, extremite_m=0.35)
#: les 8 rangées explicites de la planche V2 (positions est-ouest)
RANGEES_V2 = (0.35, 5.65, 12.80, 20.65, 25.95, 31.25, 36.55, 41.85)


def _compter(surface, positions, kit=KIT_AO_PORTRAIT):
    """Compteur JOUET local (le vrai vit dans ``moteur.py``) : sans obstacle."""
    total = 0
    emprise = kit.emprise_transversale_m
    for y0 in positions:
        bornes = getattr(surface, "bandes", None)
        familles = bornes(y0, emprise) if bornes else ()
        if not familles:
            b = surface.bande(y0, emprise)
            familles = (b,) if b else ()
        for a, b in familles:
            a2, b2 = surface.bornes_utiles((a, b))
            if b2 > a2:
                total += kit.modules_par_pas * int(
                    math.floor((b2 - a2 + 1e-9) / surface.pas_de_pose(kit, y0)))
    return total


class PolygoneEstConforme(ConformiteSurface, unittest.TestCase):
    def surface(self):
        return SurfacePolygone(repere="AILE_L", contour=CONTOUR_L, rives=RIVES)

    def y_valide(self):
        return 0.35


class BalayageDeBande(unittest.TestCase):
    def test_intervalles_a_y_sur_un_rectangle(self):
        rect = ((0.0, 0.0), (10.0, 0.0), (10.0, 5.0), (0.0, 5.0))
        self.assertEqual(intervalles_a_y(rect, (), 2.5), ((0.0, 10.0),))

    def test_un_trou_coupe_l_intervalle_en_deux(self):
        rect = ((0.0, 0.0), (10.0, 0.0), (10.0, 5.0), (0.0, 5.0))
        trou = ((4.0, 1.0), (6.0, 1.0), (6.0, 4.0), (4.0, 4.0))
        familles = intervalles_a_y(rect, (trou,), 2.5)
        self.assertEqual(len(familles), 2)
        self.assertAlmostEqual(familles[0][1], 4.0)
        self.assertAlmostEqual(familles[1][0], 6.0)

    def test_intersection_d_intervalles(self):
        self.assertEqual(
            intersection_intervalles(((0.0, 10.0),), ((3.0, 12.0),)),
            ((3.0, 10.0),))

    def test_bande_a_cheval_sur_un_trou_est_amputee(self):
        rect = ((0.0, 0.0), (10.0, 0.0), (10.0, 5.0), (0.0, 5.0))
        trou = ((4.0, 1.0), (6.0, 1.0), (6.0, 4.0), (4.0, 4.0))
        familles = bandes_couvertes(rect, (trou,), 2.0, 3.0)
        self.assertEqual(len(familles), 2)

    def test_point_dans_polygone(self):
        self.assertTrue(point_dans_polygone((5.0, 20.0), CONTOUR_L))
        self.assertFalse(point_dans_polygone((-10.0, 30.0), CONTOUR_L))


class LeLEstUnSeulContour(unittest.TestCase):
    def _surface(self):
        return SurfacePolygone(repere="AILE_L", contour=CONTOUR_L, rives=RIVES)

    def test_une_rangee_a_l_ouest_descend_d_un_seul_tenant(self):
        s = self._surface()
        bornes = s.bande(0.35, 4.70)
        self.assertAlmostEqual(bornes[0], -AILE_LONG, delta=1e-6)
        self.assertAlmostEqual(bornes[1], BARRE_LARG, delta=1e-6)
        self.assertAlmostEqual(bornes[1] - bornes[0], 40.50, delta=1e-6)

    def test_une_rangee_a_l_est_s_arrete_a_la_barre(self):
        s = self._surface()
        bornes = s.bande(20.65, 4.70)
        self.assertAlmostEqual(bornes[0], 0.0, delta=1e-6)
        self.assertAlmostEqual(bornes[1], BARRE_LARG, delta=1e-6)

    def test_une_rangee_a_cheval_sur_le_bord_de_l_aile_ne_descend_pas(self):
        s = self._surface()
        bornes = s.bande(8.0, 4.70)      # [8,00 ; 12,70] dépasse l'aile (11,20)
        self.assertAlmostEqual(bornes[0], 0.0, delta=1e-6)

    def test_les_bandes_du_script_d_origine_sont_reproduites(self):
        """``band(x0)`` de la planche V2 : aile si la rangée tient à l'ouest."""
        s = self._surface()
        for y0 in RANGEES_V2:
            bornes = s.bande(y0, 4.70)
            attendu_bas = -AILE_LONG if y0 + 4.70 <= AILE_LARG + 1e-9 else 0.0
            self.assertAlmostEqual(bornes[0], attendu_bas, delta=1e-6,
                                   msg="rangée %.2f" % y0)
            self.assertAlmostEqual(bornes[1], BARRE_LARG, delta=1e-6)

    def test_aire_du_l(self):
        s = self._surface()
        attendu = BARRE_LONG * BARRE_LARG + AILE_LARG * AILE_LONG
        self.assertAlmostEqual(s.aire_m2, attendu, delta=1e-6)


class DecouperLeLEstUnePerteSeche(unittest.TestCase):
    """Test EXPLICITE exigé par la tâche : 2 rectangles < 1 contour."""

    def test_deux_rectangles_donnent_strictement_moins(self):
        entier = SurfacePolygone(repere="AILE_L", contour=CONTOUR_L, rives=RIVES)
        barre = SurfaceRectangle(repere="BARRE", longueur_m=BARRE_LARG,
                                 largeur_m=BARRE_LONG, rives=RIVES)
        aile = SurfaceRectangle(repere="AILE", longueur_m=AILE_LONG,
                                largeur_m=AILE_LARG, rives=RIVES)
        n_entier = _compter(entier, RANGEES_V2)
        n_decoupe = (_compter(barre, RANGEES_V2)
                     + _compter(aile, (0.35, 5.65)))
        self.assertGreater(n_entier, n_decoupe)
        # 2 rangées traversantes × (35 pas contre 8 + 25) = 8 modules perdus
        self.assertEqual(n_entier - n_decoupe, 8)

    def test_le_contour_entier_ne_perd_jamais_de_rive_a_la_jonction(self):
        entier = SurfacePolygone(repere="AILE_L", contour=CONTOUR_L, rives=RIVES)
        self.assertAlmostEqual(entier.longueur_utile(0.35, 4.70), 39.80,
                               delta=1e-6)


class PolygoneConcaveATrou(unittest.TestCase):
    def test_traite_sans_decoupage_manuel(self):
        contour = ((0.0, 0.0), (30.0, 0.0), (30.0, 20.0), (0.0, 20.0))
        trou = ((10.0, 5.0), (14.0, 5.0), (14.0, 15.0), (10.0, 15.0))
        s = SurfacePolygone(repere="PATIO", contour=contour, trous=(trou,),
                            rives=RIVES)
        familles = s.bandes(6.0, 4.70)
        self.assertEqual(len(familles), 2)
        self.assertAlmostEqual(familles[0][1], 10.0, delta=1e-6)
        self.assertAlmostEqual(familles[1][0], 14.0, delta=1e-6)
        self.assertAlmostEqual(s.aire_m2, 600.0 - 40.0, delta=1e-6)

    def test_contour_trop_court_refuse(self):
        with self.assertRaises(ValueError):
            SurfacePolygone(repere="X", contour=((0.0, 0.0), (1.0, 1.0)))


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
