# -*- coding: utf-8 -*-
"""AOF49 — marges de tronçon / de bande, et départage déterministe des optima.

Les marges de l'ARC sont celles que le script d'origine vérifiait à chaque
exécution : ``MARGE_L >= 0,02`` et ``MARGE_B >= 0,04``, valeurs mesurées
4,15 cm et 4,90 cm.
"""

import unittest

from core.calepinage.robustesse import (
    cle_de_departage,
    departager,
    marges_du_plan,
    valider_marges,
)
from core.calepinage.surfaces.rectangle import SurfaceRectangle
from core.calepinage.types import (
    KIT_AO_PAYSAGE,
    KIT_AO_PORTRAIT,
    NatureZone,
    Rives,
    Zone,
)
from core.tests.test_calepinage_moteur import ECOLE_OBSTACLES, ECOLE_RANGEES
from core.tests.test_calepinage_pose_uniforme import (
    ARC_KITS,
    ARC_RANGEES,
    obstacles_arc,
    segment_arc,
)
from core.calepinage.obstacles import appliquer_regles

RIVES_AO = Rives(laterale_m=0.35, extremite_m=0.35)


class MargesDeLArc(unittest.TestCase):
    """Les marges publiées par la planche V2 du bâtiment B."""

    def _marges(self):
        troncon, bande = None, None
        for segment in ("S1", "S2", "S3"):
            surface = segment_arc(segment, RIVES_AO)
            kit = ARC_KITS[segment]
            marges = marges_du_plan(
                surface, tuple((y, kit) for y in ARC_RANGEES[segment]),
                obstacles_arc(segment))
            troncon = (marges.troncon_min_m if troncon is None
                       else min(troncon, marges.troncon_min_m))
            bande = (marges.bande_min_m if bande is None
                     else min(bande, marges.bande_min_m))
        return troncon, bande

    def test_marge_de_troncon_du_script_d_origine(self):
        troncon, _bande = self._marges()
        self.assertAlmostEqual(troncon, 0.0415, delta=0.0005)

    def test_marge_de_bande_du_script_d_origine(self):
        _troncon, bande = self._marges()
        self.assertAlmostEqual(bande, 0.0490, delta=0.0005)

    def test_les_seuils_du_script_sont_tenus(self):
        troncon, bande = self._marges()
        self.assertGreaterEqual(troncon, 0.02)
        self.assertGreaterEqual(bande, 0.04)


class MargesPubliablesEnCentimetres(unittest.TestCase):
    def test_les_marges_sont_exposees_en_cm(self):
        surface = SurfaceRectangle(repere="BAT_C", longueur_m=51.10,
                                   largeur_m=25.62, rives=RIVES_AO)
        marges = marges_du_plan(
            surface, tuple((y, KIT_AO_PORTRAIT) for y in ECOLE_RANGEES),
            appliquer_regles(ECOLE_OBSTACLES))
        self.assertAlmostEqual(marges.troncon_min_cm,
                               marges.troncon_min_m * 100.0, delta=1e-9)
        self.assertAlmostEqual(marges.bande_min_cm,
                               marges.bande_min_m * 100.0, delta=1e-9)
        self.assertTrue(marges.rangee_critique)

    def test_un_plan_sans_obstacle_a_une_marge_de_bande_nulle(self):
        surface = SurfaceRectangle(repere="R", longueur_m=20.0, largeur_m=12.0,
                                   rives=RIVES_AO)
        marges = marges_du_plan(surface, ((0.35, KIT_AO_PORTRAIT),))
        self.assertEqual(marges.bande_min_m, 0.0)
        self.assertGreater(marges.troncon_min_m, 0.0)


class UnPlanAuRasEstRefuse(unittest.TestCase):
    def test_marge_de_troncon_sous_seuil_nomme_la_rangee(self):
        surface = SurfaceRectangle(repere="R", longueur_m=20.0, largeur_m=12.0,
                                   rives=RIVES_AO)
        marges = marges_du_plan(surface, ((0.35, KIT_AO_PORTRAIT),))
        ok, motifs = valider_marges(marges, seuil_troncon_m=1.0,
                                    seuil_bande_m=0.0)
        self.assertFalse(ok)
        self.assertIn("marge de tronçon", motifs[0])
        self.assertIn("y0=0.350", motifs[0])

    def test_marge_de_bande_sous_seuil_nomme_l_obstacle(self):
        surface = segment_arc("S2", RIVES_AO)
        marges = marges_du_plan(
            surface, tuple((y, KIT_AO_PAYSAGE) for y in ARC_RANGEES["S2"]),
            obstacles_arc("S2"))
        ok, motifs = valider_marges(marges, seuil_troncon_m=0.0,
                                    seuil_bande_m=10.0)
        self.assertFalse(ok)
        self.assertIn("marge de bande", motifs[0])
        self.assertTrue(marges.obstacle_critique)

    def test_un_plan_conforme_passe(self):
        surface = segment_arc("S3", RIVES_AO)
        marges = marges_du_plan(
            surface, tuple((y, KIT_AO_PAYSAGE) for y in ARC_RANGEES["S3"]),
            obstacles_arc("S3"))
        ok, motifs = valider_marges(marges)
        self.assertTrue(ok, motifs)


class DepartageDeterministe(unittest.TestCase):
    def _surface(self):
        return SurfaceRectangle(repere="R", longueur_m=20.0, largeur_m=12.0,
                                rives=RIVES_AO)

    def test_deux_plans_de_meme_compte_sont_departages(self):
        surface = self._surface()
        a = ((0.35, KIT_AO_PORTRAIT), (5.65, KIT_AO_PORTRAIT))
        b = ((0.60, KIT_AO_PORTRAIT), (5.90, KIT_AO_PORTRAIT))
        choisi = departager(surface, (a, b))
        self.assertIn(choisi, (a, b))
        self.assertEqual(departager(surface, (b, a)), choisi)

    def test_le_departage_ne_sacrifie_jamais_un_module(self):
        surface = self._surface()
        riche = ((0.35, KIT_AO_PORTRAIT), (5.65, KIT_AO_PORTRAIT))
        pauvre = ((0.35, KIT_AO_PORTRAIT),)
        self.assertEqual(departager(surface, (pauvre, riche)), riche)

    def test_la_cle_est_reproductible(self):
        surface = self._surface()
        rangees = ((0.35, KIT_AO_PORTRAIT), (5.65, KIT_AO_PORTRAIT))
        self.assertEqual(cle_de_departage(surface, rangees),
                         cle_de_departage(surface, rangees))

    def test_une_zone_preferee_departage_sans_changer_le_compte(self):
        surface = self._surface()
        zone = Zone(repere="PREF", nature=NatureZone.PREFEREE,
                    sommets=((0.0, 0.0), (20.0, 0.0), (20.0, 5.0), (0.0, 5.0)))
        rangees = ((0.35, KIT_AO_PORTRAIT), (5.65, KIT_AO_PORTRAIT))
        avec = cle_de_departage(surface, rangees, zones=(zone,))
        sans = cle_de_departage(surface, rangees)
        self.assertGreater(avec[2], sans[2])
        self.assertEqual(avec[0], sans[0])

    def test_aucun_candidat_leve(self):
        with self.assertRaises(ValueError):
            departager(self._surface(), ())


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
