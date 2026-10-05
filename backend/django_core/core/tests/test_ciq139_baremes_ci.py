# -*- coding: utf-8 -*-
"""CIQ139 — barèmes électriques étendus aux puissances C&I : sections au-delà
de 25 mm² et calibres au-delà de 250 A, chacun RELEVÉ dans sa norme (aucune
extrapolation). Une exigence au-delà de la dernière ligne relevée sort un
verdict NON CONFORME nommé — jamais la plus grosse section en silence.

Noyau pur : ``unittest``, aucune base.
"""
import math
import unittest
from types import SimpleNamespace

from core.electrique.cables import (
    AMPACITE_H1Z2Z2K, AMPACITE_H1Z2Z2K_CI, AMPACITE_U1000R2V_MONO,
    AMPACITE_U1000R2V_MONO_CI, AMPACITE_U1000R2V_TRI,
    AMPACITE_U1000R2V_TRI_CI, CHUTE_CIBLE_AC_PCT,
    CRITERE_HORS_BAREME_THERMIQUE, SECTIONS_MM2, SECTIONS_MM2_CI,
    bareme_pour, dimensionner_cables, proposer_section, verifier_ib_in_iz,
)
from core.electrique.protections import (
    CALIBRES_DISJONCTEUR_A, CALIBRES_DISJONCTEUR_CI_A, calibre_disjoncteur,
)


def _ib_tri(kw):
    return kw * 1000.0 / (math.sqrt(3.0) * 400.0)


def _cables_ac(ib_a, calibre_a, longueur_m=30.0, phases=3, tension=400.0):
    entree = SimpleNamespace(phases=phases, ac_m=longueur_m,
                             tension_reseau_v=tension, dc_m=0.0, module=None)
    protections = SimpleNamespace(courant_ac_ib_a=ib_a,
                                  calibre_ac_a=calibre_a,
                                  calibre_fusible_a=None)
    return dimensionner_cables(entree, None, protections)


class BaremesReleves(unittest.TestCase):
    def test_les_bases_sont_des_prefixes_inchanges(self):
        for base, etendu in ((AMPACITE_H1Z2Z2K, AMPACITE_H1Z2Z2K_CI),
                             (AMPACITE_U1000R2V_MONO,
                              AMPACITE_U1000R2V_MONO_CI),
                             (AMPACITE_U1000R2V_TRI,
                              AMPACITE_U1000R2V_TRI_CI)):
            self.assertEqual(etendu[:len(base)], base)
            self.assertEqual(tuple(s for s, _ in etendu), SECTIONS_MM2_CI)
            valeurs = [iz for _, iz in etendu]
            self.assertEqual(valeurs, sorted(valeurs))
        self.assertEqual(SECTIONS_MM2_CI[:len(SECTIONS_MM2)], SECTIONS_MM2)
        self.assertEqual(SECTIONS_MM2_CI[-1], 240.0)

    def test_valeurs_relevees_iec_60364_5_52_colonne_b1(self):
        self.assertIn((50.0, 175.0), AMPACITE_U1000R2V_TRI_CI)
        self.assertIn((240.0, 450.0), AMPACITE_U1000R2V_TRI_CI)
        self.assertIn((50.0, 198.0), AMPACITE_U1000R2V_MONO_CI)
        self.assertIn((35.0, 218.0), AMPACITE_H1Z2Z2K_CI)

    def test_calibres_iec_60059_au_dela_de_250(self):
        self.assertEqual(CALIBRES_DISJONCTEUR_CI_A[:len(
            CALIBRES_DISJONCTEUR_A)], CALIBRES_DISJONCTEUR_A)
        self.assertEqual(CALIBRES_DISJONCTEUR_CI_A[-4:], (315, 400, 500, 630))
        self.assertEqual(calibre_disjoncteur(144.3), 160.0)
        self.assertEqual(calibre_disjoncteur(250.0), 250.0)
        self.assertEqual(calibre_disjoncteur(260.0), 315.0)
        # Résidentiel inchangé.
        self.assertEqual(calibre_disjoncteur(26.1), 32.0)

    def test_la_base_reste_choisie_tant_qu_elle_tient(self):
        self.assertIs(bareme_pour(AMPACITE_U1000R2V_TRI, 36.0, 40.0),
                      AMPACITE_U1000R2V_TRI)
        self.assertIs(bareme_pour(AMPACITE_U1000R2V_TRI, 144.0, 160.0),
                      AMPACITE_U1000R2V_TRI_CI)


class OnduleurCI(unittest.TestCase):
    def test_144_a_triphase_sur_30_m_section_conforme_du_bareme_etendu(self):
        ib = _ib_tri(100.0)
        self.assertAlmostEqual(ib, 144.3, places=1)
        calibre = calibre_disjoncteur(ib)
        proposee = proposer_section(
            courant_ib_a=ib, longueur_m=30.0, tension_v=400.0,
            cible_pct=CHUTE_CIBLE_AC_PCT,
            bareme=bareme_pour(AMPACITE_U1000R2V_TRI, ib, calibre),
            coefficient=math.sqrt(3.0), calibre_in_a=calibre)
        self.assertGreater(proposee.section_mm2, 25.0)
        self.assertIn(proposee.section_mm2, SECTIONS_MM2_CI)
        self.assertFalse(proposee.thermique_hors_bareme)
        conforme, motif = verifier_ib_in_iz(ib, calibre, proposee.iz_a)
        self.assertTrue(conforme, motif)

        resultat = _cables_ac(ib, calibre)
        w2 = [c for c in resultat.cables if c.repere == 'W2'][0]
        self.assertTrue(w2.conforme)
        self.assertEqual(w2.section_mm2, proposee.section_mm2)
        self.assertEqual(resultat.bloquants, ())

    def test_150_kw_aussi_dimensionnable(self):
        ib = _ib_tri(150.0)
        resultat = _cables_ac(ib, calibre_disjoncteur(ib))
        w2 = [c for c in resultat.cables if c.repere == 'W2'][0]
        self.assertTrue(w2.conforme)
        self.assertGreaterEqual(w2.iz_a, w2.in_a)

    def test_au_dela_de_la_derniere_ligne_verdict_non_conforme_nomme(self):
        ib = 480.0  # > 450 A, dernière ligne relevée (240 mm², tri, B1)
        calibre = calibre_disjoncteur(ib)
        proposee = proposer_section(
            courant_ib_a=ib, longueur_m=30.0, tension_v=400.0,
            cible_pct=CHUTE_CIBLE_AC_PCT, bareme=AMPACITE_U1000R2V_TRI_CI,
            coefficient=math.sqrt(3.0), calibre_in_a=calibre)
        self.assertTrue(proposee.thermique_hors_bareme)
        self.assertEqual(proposee.critere, CRITERE_HORS_BAREME_THERMIQUE)
        self.assertIsNone(proposee.section_par_echauffement_mm2)

        resultat = _cables_ac(ib, calibre)
        w2 = [c for c in resultat.cables if c.repere == 'W2'][0]
        self.assertFalse(w2.conforme)
        self.assertTrue(any('NON CONFORME' in b and 'dernière ligne relevée'
                            in b for b in resultat.bloquants),
                        resultat.bloquants)
        # Jamais une section extrapolée au-delà du barème relevé.
        self.assertLessEqual(w2.section_mm2, SECTIONS_MM2_CI[-1])

    def test_residentiel_inchange(self):
        """Un onduleur 10 kW tri garde exactement le barème de base."""
        ib = _ib_tri(10.0)
        resultat = _cables_ac(ib, calibre_disjoncteur(ib))
        w2 = [c for c in resultat.cables if c.repere == 'W2'][0]
        self.assertIn(w2.section_mm2, SECTIONS_MM2)
        self.assertTrue(w2.conforme)


if __name__ == '__main__':
    unittest.main()
