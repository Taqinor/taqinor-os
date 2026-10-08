"""AMOT74 - tests de scripts/check_echeances_reglementaires.py (horloge injectee). Stdlib pur."""
import datetime as dt
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import check_echeances_reglementaires as cer  # noqa: E402


class EcheancesRealesTests(unittest.TestCase):
    def test_constantes_reelles_decouvertes(self):
        noms = {nom for _rel, nom, _fin in cer.echeances()}
        self.assertIn("ANRE_PERIODE", noms)
        self.assertIn("MILLESIME_COURANT", noms)

    def test_anre_periode_fin_28_02_2027(self):
        fins = {nom: fin for _rel, nom, fin in cer.echeances()}
        self.assertEqual(fins["ANRE_PERIODE"], dt.date(2027, 2, 28))

    def test_rouge_au_30_12_2026(self):
        erreurs = cer.verifier(dt.date(2026, 12, 30))
        self.assertTrue(any(e.startswith("ANRE_PERIODE") and "28/02/2027" in e and "re-sourcer" in e
                            for e in erreurs), erreurs)

    def test_vert_au_08_10_2026(self):
        self.assertEqual(cer.verifier(dt.date(2026, 10, 8)), [])

    def test_rouge_apres_expiration(self):
        self.assertTrue(any("a expire" in e for e in cer.verifier(dt.date(2027, 3, 5))))


class FixtureTests(unittest.TestCase):
    def _moteur(self, tmp, source):
        racine = Path(tmp)
        (racine / "c.py").write_text(source, encoding="utf-8")
        return racine

    def test_fin_dans_la_fenetre_est_nommee(self):
        with tempfile.TemporaryDirectory() as tmp:
            r = self._moteur(tmp, "import datetime as _dt\nTARIF_X_PERIODE = (_dt.date(2026, 1, 1), _dt.date(2026, 12, 1))\n")
            erreurs = cer.verifier(dt.date(2026, 10, 15), r)
            self.assertEqual(len(erreurs), 1)
            self.assertIn("TARIF_X_PERIODE", erreurs[0])

    def test_fin_hors_fenetre_vert(self):
        with tempfile.TemporaryDirectory() as tmp:
            r = self._moteur(tmp, "import datetime as _dt\nTARIF_X_PERIODE = (_dt.date(2026, 1, 1), _dt.date(2028, 1, 1))\n")
            self.assertEqual(cer.verifier(dt.date(2026, 10, 15), r), [])

    def test_date_de_validite_nommee(self):
        with tempfile.TemporaryDirectory() as tmp:
            r = self._moteur(tmp, "import datetime as _dt\nGRILLE_FIN_VALIDITE = _dt.date(2026, 11, 1)\n")
            self.assertEqual(len(cer.verifier(dt.date(2026, 10, 15), r)), 1)


if __name__ == "__main__":
    unittest.main()
