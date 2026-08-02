# -*- coding: utf-8 -*-
"""AOF34 — le contrat de données est GELÉ et les kits sont DÉRIVÉS.

Tests PURS : ni Django, ni base de données.
"""

import unittest

from core.calepinage.types import (
    Axe,
    Kit,
    KIT_AO_PAYSAGE,
    KIT_AO_PORTRAIT,
    KIT_VILLA_720,
    MethodePreuve,
    ModePose,
    Obstacle,
    OrientationModule,
    Parametres,
    Preuve,
    Provenance,
    Rives,
    Sensibilite,
    remplacer,
)
from core.calepinage.units import arrondi_mm, en_mm, fr, nb_entier


class KitsDerives(unittest.TestCase):
    """Le kit RECALCULE 4,70 et 2,25 — il ne les recopie pas."""

    def test_portrait_redonne_4_70_a_1_mm_pres(self):
        self.assertAlmostEqual(KIT_AO_PORTRAIT.emprise_transversale_m, 4.70,
                               delta=0.001)
        self.assertAlmostEqual(KIT_AO_PORTRAIT.cote_le_long_rangee_m, 1.134,
                               delta=1e-9)

    def test_paysage_redonne_2_25_a_1_mm_pres(self):
        self.assertAlmostEqual(KIT_AO_PAYSAGE.emprise_transversale_m, 2.25,
                               delta=0.001)
        self.assertAlmostEqual(KIT_AO_PAYSAGE.cote_le_long_rangee_m, 2.382,
                               delta=1e-9)

    def test_kit_villa_un_module_est_exprimable(self):
        self.assertEqual(KIT_VILLA_720.modules_par_table, 1)
        self.assertEqual(KIT_VILLA_720.puissance_table_wc, 720.0)
        # 2,384 × cos(13°) = 2,3229 — un seul plan de modules, aucun faîtage.
        self.assertAlmostEqual(KIT_VILLA_720.emprise_transversale_m, 2.3229,
                               delta=0.001)
        self.assertAlmostEqual(KIT_VILLA_720.cote_le_long_rangee_m, 1.303,
                               delta=1e-9)

    def test_puissance_de_table_et_modules_par_pas(self):
        self.assertEqual(KIT_AO_PORTRAIT.puissance_table_wc, 1250.0)
        self.assertEqual(KIT_AO_PORTRAIT.modules_par_pas, 2)
        self.assertTrue(KIT_AO_PORTRAIT.dos_a_dos)
        self.assertFalse(KIT_VILLA_720.dos_a_dos)

    def test_axe_de_faitage_dos_a_dos(self):
        self.assertIs(KIT_AO_PORTRAIT.axe_faitage, Axe.NORD_SUD)
        self.assertIs(Axe.NORD_SUD.perpendiculaire, Axe.EST_OUEST)

    def test_kit_invalide_leve(self):
        with self.assertRaises(ValueError):
            Kit(code="X", libelle="", module_long_m=1.0, module_court_m=2.0,
                puissance_module_wc=500, inclinaison_deg=15,
                orientation=OrientationModule.PORTRAIT)
        with self.assertRaises(ValueError):
            Kit(code="X", libelle="", module_long_m=2.0, module_court_m=1.0,
                puissance_module_wc=500, inclinaison_deg=95,
                orientation=OrientationModule.PORTRAIT)


class ImmuabiliteDuContrat(unittest.TestCase):
    """Zéro globale mutable : un Parametres se REMPLACE, il ne se mute pas."""

    def test_parametres_immuable_et_hachable(self):
        p = Parametres(kits=(KIT_AO_PORTRAIT,))
        with self.assertRaises(Exception):
            p.allee_m = 1.90
        self.assertIsInstance(hash(p), int)

    def test_remplacer_rend_un_nouvel_objet(self):
        p = Parametres(kits=(KIT_AO_PORTRAIT,), allee_m=0.60)
        q = remplacer(p, allee_m=1.90)
        self.assertEqual(p.allee_m, 0.60)
        self.assertEqual(q.allee_m, 1.90)
        self.assertIsNot(p, q)

    def test_parametres_refuse_kits_vides_et_doublons(self):
        with self.assertRaises(ValueError):
            Parametres(kits=())
        with self.assertRaises(ValueError):
            Parametres(kits=(KIT_AO_PORTRAIT, KIT_AO_PORTRAIT))

    def test_defaut_mode_pose(self):
        p = Parametres(kits=(KIT_AO_PORTRAIT,))
        self.assertIs(p.mode_pose, ModePose.RANGEES_EXPLICITES_DP)
        self.assertFalse(p.multi_kits)
        self.assertTrue(Parametres(kits=(KIT_AO_PORTRAIT, KIT_AO_PAYSAGE)).multi_kits)


class RivesNommees(unittest.TestCase):
    def test_les_quatre_rives_sont_nommees(self):
        r = Rives(laterale_m=0.35, extremite_m=0.35, acrotere_m=0.28, joint_m=0.05)
        self.assertAlmostEqual(r.laterale_totale_m, 0.63)
        self.assertAlmostEqual(r.extremite_totale_m, 0.40)

    def test_rive_negative_refusee(self):
        with self.assertRaises(ValueError):
            Rives(laterale_m=-0.1)


class ObstacleContrat(unittest.TestCase):
    def test_bornes_inversees_refusees(self):
        with self.assertRaises(ValueError):
            Obstacle(repere="O", x0=2.0, x1=1.0, y0=0.0, y1=1.0)

    def test_dimensions_et_ecarte(self):
        o = Obstacle(repere="GRECT", x0=1.0, x1=2.3, y0=0.0, y1=2.21,
                     provenance=Provenance.DEVINE)
        self.assertAlmostEqual(o.largeur_m, 1.3)
        self.assertAlmostEqual(o.profondeur_m, 2.21)
        self.assertFalse(o.ecarte)
        self.assertTrue(remplacer(o, provenance=Provenance.ECARTE).ecarte)


class VocabulaireDeLaPreuve(unittest.TestCase):
    def test_prouve_inaccessible_sur_heuristique(self):
        p = Preuve(methode=MethodePreuve.HEURISTIQUE_BORNEE,
                   pas_recherche_m=0.05, compte_retenu=112,
                   compte_optimal=112, borne_superieure=126)
        self.assertFalse(p.optimal)
        self.assertNotIn("prouvé", p.libelle)

    def test_prouve_accessible_sur_dp_exact(self):
        p = Preuve(methode=MethodePreuve.DP_EXACT_1CM, pas_recherche_m=0.01,
                   compte_retenu=178, compte_optimal=178)
        self.assertTrue(p.optimal)
        self.assertIn("prouvé", p.libelle)

    def test_plan_impose_inferieur_n_est_pas_optimal(self):
        p = Preuve(methode=MethodePreuve.IMPOSE_UTILISATEUR, pas_recherche_m=0.01,
                   compte_retenu=170, compte_optimal=178)
        self.assertFalse(p.optimal)


class SensibiliteEtVerdict(unittest.TestCase):
    def test_sensibilite_porte_son_delta(self):
        s = Sensibilite(code="ALLEE_190", libelle="allées 1,90", modules=178,
                        delta=0)
        self.assertEqual(s.delta, 0)


class UnitesNommees(unittest.TestCase):
    def test_arrondi_mm_symetrique(self):
        self.assertAlmostEqual(arrondi_mm(1.23449), 1.234, delta=1e-12)
        self.assertAlmostEqual(arrondi_mm(-1.23449), -1.234, delta=1e-12)
        self.assertEqual(en_mm(4.7004), 4700)
        self.assertEqual(en_mm(-0.0005), -1)

    def test_nb_entier_absorbe_l_erreur_flottante(self):
        # 4 pas EXACTEMENT : sans tolérance de comptage, // rendrait 3.
        self.assertEqual(nb_entier(0.1 + 0.1 + 0.1 + 0.1, 0.1), 4)
        self.assertEqual(nb_entier(0.0, 1.0), 0)
        with self.assertRaises(ValueError):
            nb_entier(1.0, 0.0)

    def test_formatage_francais(self):
        self.assertEqual(fr(4.7), "4,70")


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
