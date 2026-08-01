# -*- coding: utf-8 -*-
"""AOF37 — chaînes de cotes : déduction par fermeture, tolérance PAR chaîne,
échec-objet et non exception. Les jeux sont ceux du relevé FRDISI 27/07/2026."""

import unittest

from core.calepinage.solveur_cotes import (
    Chaine,
    Cote,
    StatutCote,
    compenser,
    fermeture,
    positions_cumulees,
    resoudre,
)


class PositionsEtFermeture(unittest.TestCase):
    def test_positions_cumulees_reproduit_chain(self):
        self.assertEqual(positions_cumulees(0, (1.26, 1.53, 0.64)),
                         (0, 1.26, 2.79, 3.43))

    def test_fermeture_sans_effet_console(self):
        ok, residu, pct = fermeture("B — chaîne basse", 23.58, 23.58, 0.05)
        self.assertTrue(ok)
        self.assertAlmostEqual(residu, 0.0)
        self.assertAlmostEqual(pct, 0.0)

    def test_compensation_au_prorata(self):
        positions = (0.0, 10.0, 20.0)
        compensees = compenser(0.2, positions)
        self.assertAlmostEqual(compensees[0], 0.0)
        self.assertAlmostEqual(compensees[1], 9.9)
        self.assertAlmostEqual(compensees[2], 19.8)


class ChaineBasseDeLEcole(unittest.TestCase):
    """La chaîne fermée au centimètre : tolérance 0,02 propre à CETTE chaîne."""

    def test_chaine_b_fermee(self):
        c = Chaine(nom="B — chaîne basse",
                   cotes=(Cote("3,39", 3.39), Cote("1,31", 1.31),
                          Cote("6,47", 6.47), Cote("1,33", 1.33),
                          Cote("6,55", 6.55), Cote("1,30", 1.30),
                          Cote("3,23", 3.23)),
                   total_mesure=23.58, tolerance_m=0.05)
        r = resoudre(c)
        self.assertTrue(r.ok)
        self.assertAlmostEqual(r.somme, 23.58, delta=1e-9)
        self.assertAlmostEqual(r.residu_m, 0.0, delta=1e-9)


class FermetureVerticaleDeLEcole(unittest.TestCase):
    """La cote DÉDUITE : 8,82 — le client annonçait « ≈8,5 »."""

    def _chaine(self):
        return Chaine(
            nom="École — chaîne verticale",
            cotes=(Cote("19,36", 19.36),
                   Cote("profondeur de cage", None),
                   Cote("cage→local (relevé)", 7.92),
                   Cote("local", 4.50),
                   Cote("10,50", 10.50)),
            total_mesure=51.10, tolerance_m=0.02)

    def test_la_cote_manquante_est_deduite_a_8_82(self):
        r = resoudre(self._chaine())
        self.assertTrue(r.ok)
        deduite = [c for c in r.cotes if c.nom == "profondeur de cage"][0]
        self.assertAlmostEqual(deduite.valeur, 8.82, delta=1e-9)

    def test_la_cote_deduite_est_marquee_a_confirmer(self):
        r = resoudre(self._chaine())
        deduite = [c for c in r.cotes if c.nom == "profondeur de cage"][0]
        self.assertIs(deduite.statut, StatutCote.A_CONFIRMER)
        self.assertEqual(len(r.cotes_a_confirmer), 1)
        self.assertIn("DÉDUITE", r.motif)

    def test_la_cote_deduite_n_est_pas_les_8_5_annonces(self):
        r = resoudre(self._chaine())
        deduite = [c for c in r.cotes if c.nom == "profondeur de cage"][0]
        self.assertNotAlmostEqual(deduite.valeur, 8.50, delta=0.01)

    def test_residu_en_metres_et_en_pourcent_dans_le_resultat(self):
        c = Chaine(nom="essai", cotes=(Cote("a", 10.0), Cote("b", 10.0)),
                   total_mesure=20.10, tolerance_m=0.30)
        r = resoudre(c)
        self.assertAlmostEqual(r.residu_m, -0.10, delta=1e-9)
        self.assertAlmostEqual(r.residu_pct, -0.4975, delta=1e-3)


class ToleranceDepasseeRendUnEchec(unittest.TestCase):
    def test_echec_objet_et_non_exception(self):
        c = Chaine(nom="aile 2 — chaîne ouest",
                   cotes=(Cote("a", 10.0), Cote("b", 10.0)),
                   total_mesure=25.0, tolerance_m=0.30)
        r = resoudre(c)          # ne lève PAS
        self.assertFalse(r.ok)
        self.assertTrue(r.en_echec)
        self.assertIn("fermeture NON tenue", r.motif)
        self.assertAlmostEqual(r.residu_m, -5.0)

    def test_tolerance_est_un_attribut_de_la_chaine(self):
        cotes = (Cote("a", 10.0), Cote("b", 10.0))
        serree = Chaine(nom="serrée", cotes=cotes, total_mesure=20.10,
                        tolerance_m=0.02)
        lache = Chaine(nom="lâche", cotes=cotes, total_mesure=20.10,
                       tolerance_m=0.30)
        self.assertFalse(resoudre(serree).ok)
        self.assertTrue(resoudre(lache).ok)

    def test_deux_cotes_manquantes_sont_refusees(self):
        with self.assertRaises(ValueError):
            Chaine(nom="x", cotes=(Cote("a", None), Cote("b", None)),
                   total_mesure=10.0)

    def test_deduction_impossible_rend_un_echec(self):
        c = Chaine(nom="x", cotes=(Cote("a", 30.0), Cote("manque", None)),
                   total_mesure=20.0)
        r = resoudre(c)
        self.assertFalse(r.ok)
        self.assertIn("déduction impossible", r.motif)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
