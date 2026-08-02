# -*- coding: utf-8 -*-
"""AOF40 — l'arc : correction de pas, dégagements en mètres RÉELS, murets."""

import math
import unittest

from core.calepinage.surfaces.arc import (
    MURET_FRDISI,
    SEGMENTS_FRDISI,
    ErreurArc,
    SurfaceArc,
    arc_frdisi,
)
from core.calepinage.types import KIT_AO_PAYSAGE, KIT_AO_PORTRAIT, Rives
from core.tests.test_calepinage_surfaces import ConformiteSurface

RIVES = Rives(laterale_m=0.35, extremite_m=0.35)
#: rangées retenues sur la planche V2 (ordonnées depuis le bord INTÉRIEUR)
RANGEES_S2 = (0.80, 5.20, 8.30)
RANGEES_S1 = (0.55, 5.85)


class ArcEstConforme(ConformiteSurface, unittest.TestCase):
    def surface(self):
        return arc_frdisi(rives=RIVES)

    def y_valide(self):
        return 0.55


class GeometrieRelevee(unittest.TestCase):
    def test_le_developpe_est_celui_du_releve_muret_a_muret(self):
        s = arc_frdisi()
        self.assertAlmostEqual(s.developpe_m, 68.05, delta=1e-9)
        self.assertAlmostEqual(sum(SEGMENTS_FRDISI) + 2 * MURET_FRDISI, 68.05,
                               delta=1e-9)

    def test_rayons(self):
        s = arc_frdisi()
        self.assertAlmostEqual(s.rayon_ext_m, 274.0)
        self.assertAlmostEqual(s.rayon_int_m, 263.10, delta=1e-9)
        self.assertAlmostEqual(s.rayon(10.90), 274.0, delta=1e-9)

    def test_les_murets_coupent_l_arc_en_trois_segments(self):
        s = arc_frdisi()
        morceaux = s.troncons_entre_coupures((0.0, s.developpe_m))
        self.assertEqual(len(morceaux), 3)
        for morceau, attendu in zip(morceaux, SEGMENTS_FRDISI):
            self.assertAlmostEqual(morceau[1] - morceau[0], attendu, delta=1e-9)

    def test_aucune_rangee_a_cheval_sur_un_muret(self):
        s = arc_frdisi()
        self.assertTrue(s.enjambe_une_coupure(20.40, 21.10))
        self.assertFalse(s.enjambe_une_coupure(10.0, 12.0))

    def test_geometrie_invalide_leve(self):
        with self.assertRaises(ErreurArc):
            SurfaceArc(repere="X", rayon_ext_m=5.0, largeur_m=10.0)
        with self.assertRaises(ErreurArc):
            SurfaceArc(repere="X", developpe_m=0.0)


class CorrectionDePas(unittest.TestCase):
    """Le VRAI bug : deux tables jointives en abscisse se recouvrent au rayon
    intérieur."""

    def test_le_pas_est_corrige_par_le_rapport_des_rayons(self):
        s = arc_frdisi()
        attendu = KIT_AO_PAYSAGE.cote_le_long_rangee_m * 274.0 / (263.10 + 0.80)
        self.assertAlmostEqual(s.pas_de_pose(KIT_AO_PAYSAGE, 0.80), attendu,
                               delta=1e-12)

    def test_le_pas_corrige_est_toujours_plus_grand_que_la_table(self):
        s = arc_frdisi()
        for y0 in RANGEES_S2:
            self.assertGreater(s.pas_de_pose(KIT_AO_PAYSAGE, y0),
                               KIT_AO_PAYSAGE.cote_le_long_rangee_m)

    def test_le_pas_decroit_vers_le_bord_exterieur(self):
        s = arc_frdisi()
        self.assertGreater(s.pas_de_pose(KIT_AO_PAYSAGE, 0.80),
                           s.pas_de_pose(KIT_AO_PAYSAGE, 8.30))

    def test_recouvrement_evite_publie_entre_2_et_9_cm(self):
        s = arc_frdisi()
        paires = ([(KIT_AO_PORTRAIT, y) for y in RANGEES_S1]
                  + [(KIT_AO_PAYSAGE, y) for y in RANGEES_S2])
        mini, maxi = s.recouvrements_cm(paires)
        self.assertGreaterEqual(mini, 2.0)
        self.assertLessEqual(maxi, 9.9)
        self.assertLess(mini, maxi)

    def test_recouvrement_sur_jeu_vide(self):
        self.assertEqual(arc_frdisi().recouvrements_cm(()), (0.0, 0.0))


class DegagementsEnMetresReels(unittest.TestCase):
    """Les DEUX assertions que le script d'origine exécutait à chaque run."""

    def test_035_en_abscisse_vaut_au_moins_030_reels(self):
        s = arc_frdisi()
        reel = s.degagement_reel(0.35, 0.0)
        self.assertGreaterEqual(reel, 0.30)
        self.assertAlmostEqual(reel, 0.336, delta=0.001)

    def test_053_en_abscisse_vaut_au_moins_050_reels(self):
        s = arc_frdisi()
        reel = s.degagement_reel(0.53, 0.0)
        self.assertGreaterEqual(reel, 0.50)
        self.assertAlmostEqual(reel, 0.509, delta=0.001)

    def test_030_en_abscisse_ne_vaut_que_0288_reels(self):
        s = arc_frdisi()
        self.assertAlmostEqual(s.degagement_reel(0.30, 0.0), 0.288, delta=0.001)

    def test_un_degagement_qui_ne_tient_pas_en_metres_reels_leve(self):
        s = arc_frdisi()
        with self.assertRaises(ErreurArc) as ctx:
            s.verifier_degagement(0.30, 0.30, 0.0, repere="X3")
        self.assertIn("X3", str(ctx.exception))
        self.assertIn("RÉELS", str(ctx.exception))

    def test_un_degagement_conforme_rend_sa_valeur_reelle(self):
        s = arc_frdisi()
        self.assertAlmostEqual(s.verifier_degagement(0.35, 0.30, 0.0), 0.336,
                               delta=0.001)

    def test_conversion_inverse(self):
        s = arc_frdisi()
        abscisse = s.degagement_abscisse_pour(0.30, 0.0)
        self.assertAlmostEqual(s.degagement_reel(abscisse, 0.0), 0.30, delta=1e-12)


class PrimitivesDeDessin(unittest.TestCase):
    def test_la_table_rigide_a_quatre_sommets(self):
        s = arc_frdisi()
        poly = s.polygone_table(0.0, 2.382, 0.80, 3.05)
        self.assertEqual(len(poly), 4)
        cote = math.dist(poly[0], poly[1])
        self.assertAlmostEqual(cote, 2.382, delta=1e-9)

    def test_la_reprise_angulaire_par_table_est_faible(self):
        """≈0,24°/table en portrait, ≈0,50° en paysage (éclisses)."""
        s = arc_frdisi()
        portrait = math.degrees(1.134 / s.rayon_ext_m)
        paysage = math.degrees(2.382 / s.rayon_ext_m)
        self.assertAlmostEqual(portrait, 0.237, delta=0.01)
        self.assertAlmostEqual(paysage, 0.498, delta=0.01)

    def test_points_arc_suivent_le_rayon(self):
        s = arc_frdisi()
        points = s.points_arc(0.0, 10.0, 0.0, n=4)
        self.assertEqual(len(points), 5)
        for point in points:
            rayon = math.hypot(point[0], point[1] + s.rayon_ext_m
                               * math.cos(s.angle_total / 2.0))
            self.assertAlmostEqual(rayon, s.rayon_int_m, delta=1e-6)

    def test_aire_de_la_couronne(self):
        s = arc_frdisi()
        self.assertGreater(s.aire_m2, 68.05 * 10.90 * 0.9)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
