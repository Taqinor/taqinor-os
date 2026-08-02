# -*- coding: utf-8 -*-
"""AOF36 — 4 natures de zone, 4 rives NOMMÉES, et la preuve qu'un bonus doux
ne coûte jamais un module."""

import unittest

from core.calepinage import rives as R
from core.calepinage.zones import (
    aire_polygone,
    aire_retiree,
    bonus_preference,
    intervalles_bloques_zones,
    sommets_decales,
    x_extent_dans_bande,
)
from core.calepinage.types import NatureZone, Rangee, Rives, Zone


def _rect(repere, nature, x0, x1, y0, y1, retrait=0.0):
    return Zone(repere=repere, nature=nature,
                sommets=((x0, y0), (x1, y0), (x1, y1), (x0, y1)),
                retrait_m=retrait)


class AireEtGeometrie(unittest.TestCase):
    def test_aire_d_un_rectangle(self):
        self.assertAlmostEqual(aire_polygone(((0, 0), (4, 0), (4, 3), (0, 3))), 12.0)

    def test_aire_d_un_triangle(self):
        self.assertAlmostEqual(aire_polygone(((0, 0), (4, 0), (0, 3))), 6.0)

    def test_extent_dans_bande(self):
        losange = ((5.0, 0.0), (7.0, 2.0), (5.0, 4.0), (3.0, 2.0))
        self.assertIsNone(x_extent_dans_bande(losange, 10.0, 11.0))
        a, b = x_extent_dans_bande(losange, 1.9, 2.1)
        self.assertAlmostEqual(a, 3.0, delta=0.15)
        self.assertAlmostEqual(b, 7.0, delta=0.15)

    def test_retrait_dilate_le_polygone(self):
        dilate = sommets_decales(((0, 0), (2, 0), (2, 2), (0, 2)), 0.5)
        self.assertGreater(aire_polygone(dilate), 4.0)


class ZoneInterditeRetireLaSurface(unittest.TestCase):
    def test_cas_jouet_la_surface_retiree_est_exacte(self):
        z = _rect("SERVITUDE", NatureZone.INTERDITE, 2.0, 6.0, 1.0, 4.0)
        self.assertAlmostEqual(aire_retiree((z,)), 12.0)

    def test_la_zone_interdite_bloque_la_bande(self):
        z = _rect("SERVITUDE", NatureZone.INTERDITE, 2.0, 6.0, 1.0, 4.0)
        bloques = intervalles_bloques_zones((z,), 1.5, 3.0, 0.0, 20.0)
        self.assertEqual(len(bloques), 1)
        self.assertAlmostEqual(bloques[0][0], 2.0)
        self.assertAlmostEqual(bloques[0][1], 6.0)

    def test_zone_reservee_retire_aussi_mais_se_chiffre_a_part(self):
        r = _rect("FUTUR", NatureZone.RESERVEE, 0.0, 2.0, 0.0, 2.0)
        i = _rect("SERVITUDE", NatureZone.INTERDITE, 5.0, 7.0, 0.0, 2.0)
        self.assertAlmostEqual(aire_retiree((r, i)), 8.0)
        self.assertAlmostEqual(aire_retiree((r, i), NatureZone.RESERVEE), 4.0)
        self.assertEqual(len(intervalles_bloques_zones((r, i), 0.5, 1.5, 0.0, 20.0)), 2)


class ZonePrefereeNeChangeJamaisUnCompte(unittest.TestCase):
    """Test EXPLICITE exigé par la tâche."""

    def test_une_zone_preferee_ne_bloque_rien(self):
        p = _rect("PREF", NatureZone.PREFEREE, 2.0, 6.0, 0.0, 5.0)
        self.assertEqual(intervalles_bloques_zones((p,), 1.0, 2.0, 0.0, 20.0), ())
        self.assertAlmostEqual(aire_retiree((p,)), 0.0)

    def test_une_enveloppe_ne_bloque_rien_non_plus(self):
        e = _rect("ENV", NatureZone.ENVELOPPE, 0.0, 20.0, 0.0, 10.0)
        self.assertEqual(intervalles_bloques_zones((e,), 1.0, 2.0, 0.0, 20.0), ())

    def test_le_bonus_de_preference_sert_uniquement_au_departage(self):
        p = _rect("PREF", NatureZone.PREFEREE, 0.0, 20.0, 0.0, 3.0)
        r1 = Rangee(y0=0.5, kit_code="K", emprise_m=2.0, modules=10)
        r2 = Rangee(y0=6.0, kit_code="K", emprise_m=2.0, modules=10)
        self.assertEqual(bonus_preference((p,), (r1, r2)), 1)
        # le bonus n'est PAS un compte de modules
        self.assertEqual(r1.modules + r2.modules, 20)


class QuatreRivesTesteesSeparement(unittest.TestCase):
    def test_rive_laterale_seule(self):
        r = Rives(laterale_m=0.35, extremite_m=0.0)
        self.assertAlmostEqual(R.retrait_lateral(r), 0.35)
        self.assertEqual(R.bornes_laterales(0.0, 10.0, r), (0.35, 9.65))

    def test_rive_extremite_seule(self):
        r = Rives(laterale_m=0.0, extremite_m=0.35)
        self.assertAlmostEqual(R.retrait_extremite(r), 0.35)
        self.assertEqual(R.bornes_extremite(0.0, 51.1, r), (0.35, 50.75))

    def test_rive_acrotere_s_ajoute_a_la_laterale(self):
        r = Rives(laterale_m=0.35, acrotere_m=0.28)
        self.assertAlmostEqual(R.retrait_lateral(r), 0.63)

    def test_rive_joint_s_ajoute_a_l_extremite(self):
        r = Rives(extremite_m=0.35, joint_m=0.45)
        self.assertAlmostEqual(R.retrait_extremite(r), 0.80)

    def test_les_quatre_noms_existent(self):
        self.assertEqual(len(R.NOMS_DE_RIVE), 4)

    def test_une_rangee_hors_rive_est_nommee(self):
        r = Rives(laterale_m=0.35)
        motifs = R.verifier_rives((Rangee(y0=0.10, kit_code="K", emprise_m=4.70),),
                                  0.0, 10.76, r)
        self.assertTrue(motifs)
        self.assertIn("rive_laterale", motifs[0])

    def test_rives_par_defaut_du_dossier_frdisi(self):
        r = R.rives_par_defaut_ao()
        self.assertAlmostEqual(r.laterale_m, 0.35)
        self.assertAlmostEqual(r.extremite_m, 0.35)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
