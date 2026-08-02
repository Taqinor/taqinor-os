# -*- coding: utf-8 -*-
"""AOF56 — chaîne électrique du bâtiment C : 288 modules → 180,0 kWc → 3 × 50 kW."""

import unittest

from core.calepinage.electrique import (
    BORNES_RATIO_AC_DC,
    MODULES_PAR_CHAINE,
    PLAFOND_DC_PAR_ONDULEUR_KWC,
    chainer,
    dimensionner,
    evaluer_onduleurs,
    note_de_calcul,
    plafond_modules_pour_kwc,
)
from core.calepinage.site import CompteSurface, Deport, Site, agreger


class LeBatimentC(unittest.TestCase):
    def setUp(self):
        self.chainage = chainer(288)

    def test_288_modules_font_180_kwc(self):
        self.assertAlmostEqual(self.chainage.puissance_kwc, 180.0, delta=1e-9)

    def test_18_chaines_de_16(self):
        self.assertEqual(self.chainage.chaines, 18)
        self.assertEqual(self.chainage.modules_par_chaine, MODULES_PAR_CHAINE)
        self.assertEqual(self.chainage.reste, 0)
        self.assertEqual(self.chainage.modules_en_chaine, 288)

    def test_le_reste_part_en_reserve_d_appoint(self):
        chainage = chainer(290)
        self.assertEqual(chainage.chaines, 18)
        self.assertEqual(chainage.reste, 2)
        self.assertIn("réserve d'appoint",
                      " ".join(note_de_calcul(chainage, None)))

    def test_trois_onduleurs_de_50_kw_sont_conformes(self):
        retenue, _refusees = dimensionner(self.chainage.puissance_kwc)
        self.assertTrue(retenue.conforme)
        self.assertEqual(retenue.nombre, 3)
        self.assertAlmostEqual(retenue.taille_kw, 50.0)
        self.assertAlmostEqual(retenue.puissance_ac_kw, 150.0)
        self.assertAlmostEqual(retenue.ratio_ac_dc, 150.0 / 180.0, delta=1e-9)
        self.assertAlmostEqual(retenue.ratio_dc_ac, 180.0 / 150.0, delta=1e-9)

    def test_60_et_80_kw_sont_rejetes_avec_le_motif(self):
        for taille in (60.0, 80.0):
            config = evaluer_onduleurs(180.0, taille, 1)
            self.assertFalse(config.conforme, "%s kW devrait être refusé"
                             % taille)
            self.assertIn("ratio AC/DC", config.motif)
            self.assertIn("hors bornes", config.motif)

    def test_le_ratio_hors_bornes_hautes_est_nomme(self):
        config = evaluer_onduleurs(100.0, 50.0, 4)      # 200 kW AC pour 100 kWc
        self.assertFalse(config.conforme)
        self.assertIn("surdimensionnés", config.motif)

    def test_le_plafond_par_onduleur_est_nomme(self):
        config = evaluer_onduleurs(180.0, 160.0, 1,
                                   bornes=(0.75, 1.10))
        self.assertFalse(config.conforme)
        self.assertIn("plafond", config.motif)

    def test_les_bornes_sont_parametrables(self):
        self.assertEqual(BORNES_RATIO_AC_DC, (0.75, 1.00))
        config = evaluer_onduleurs(180.0, 60.0, 1, bornes=(0.30, 1.00),
                                   plafond_dc_kwc=None)
        self.assertTrue(config.conforme)

    def test_la_note_de_calcul_est_generee(self):
        retenue, refusees = dimensionner(self.chainage.puissance_kwc)
        note = note_de_calcul(self.chainage, retenue, refusees[:2])
        texte = " ".join(note)
        self.assertIn("288 modules", texte)
        self.assertIn("180,0 kWc", texte)
        self.assertIn("18 chaînes", texte)
        self.assertIn("3 onduleurs de 50 kW", texte)
        self.assertIn("REFUSÉ", texte)

    def test_parametres_invalides(self):
        with self.assertRaises(ValueError):
            chainer(288, modules_par_chaine=0)
        with self.assertRaises(ValueError):
            evaluer_onduleurs(180.0, 0.0, 1)


class LePlafondReboucleSurLeCalepinage(unittest.TestCase):
    """Un calepinage calculé sans la contrainte est optimal ET inutilisable."""

    def test_un_plafond_kwc_se_traduit_en_modules(self):
        self.assertEqual(plafond_modules_pour_kwc(60.0), 96)
        self.assertIsNone(plafond_modules_pour_kwc(None))

    def test_un_plafond_de_60_kwc_force_le_deport(self):
        site = Site(repere="FRDISI", plafond_kwc_par_surface=60.0)
        agregat = agreger(site, (CompteSurface(repere="BAT_B", modules=120),))
        self.assertEqual(agregat.compte("BAT_B").modules, 96)
        self.assertTrue(agregat.motifs)
        self.assertIn("déporter", agregat.motifs[0])

    def test_le_deport_conserve_le_total_du_site(self):
        site = Site(repere="FRDISI",
                    deports=(Deport(depuis="BAT_B", vers="BAT_A", modules=24,
                                    motif="aucun onduleur au-dessus de "
                                          "60 kWc"),))
        agregat = agreger(site, (CompteSurface(repere="BAT_A", modules=148),
                                 CompteSurface(repere="BAT_B", modules=120)))
        self.assertEqual(agregat.modules, 268)
        self.assertEqual(agregat.compte("BAT_B").modules, 96)
        self.assertAlmostEqual(agregat.compte("BAT_B").kwc, 60.0, delta=1e-9)

    def test_le_plafond_par_onduleur_du_dossier(self):
        self.assertAlmostEqual(PLAFOND_DC_PAR_ONDULEUR_KWC, 60.0)


class AucunDimensionnementPossible(unittest.TestCase):
    def test_rend_none_et_garde_les_motifs(self):
        retenue, refusees = dimensionner(1000.0, calibres_kw=(5.0,),
                                         nombre_max=2)
        self.assertIsNone(retenue)
        self.assertTrue(refusees)
        self.assertTrue(all(not r.conforme for r in refusees))


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
