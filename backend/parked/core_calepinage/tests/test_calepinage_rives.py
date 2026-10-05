# -*- coding: utf-8 -*-
"""AOF36 — 4 rives NOMMÉES (``core.calepinage.rives``), PARQUÉ par ACAL328.

Extrait de ``core/tests/test_calepinage_zones.py`` (la partie natures de zone
y reste). Au retour (voir ``backend/parked/core_calepinage/README.md``), ce
fichier revient dans ``backend/django_core/core/tests/``.
"""

import unittest

from core.calepinage import rives as R
from core.calepinage.types import Rangee, Rives


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
