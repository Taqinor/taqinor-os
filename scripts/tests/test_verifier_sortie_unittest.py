"""ADEP14 - scripts/verifier_sortie_unittest.py sur des sorties unittest reelles."""
import io
import subprocess
import sys
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import verifier_sortie_unittest as v  # noqa: E402

SORTIE_SAINE = """test_a (tests.test_x.T.test_a) ... ok
----------------------------------------------------------------------
Ran 218 tests in 41.220s

OK
"""
SORTIE_SKIPPED = """test_a (tests.test_margin_guard.T.test_a) ... skipped 'app.core.config absent'
----------------------------------------------------------------------
Ran 8 tests in 0.004s

OK (skipped=8)
"""
SORTIE_SOUS_PLANCHER = """----------------------------------------------------------------------
Ran 120 tests in 9.100s

OK
"""
SORTIE_FAILED = """----------------------------------------------------------------------
Ran 218 tests in 41.220s

FAILED (failures=1)
"""


class VerifierSortieUnittestTests(unittest.TestCase):
    def test_skipped_rouge(self):
        raisons = v.analyser(SORTIE_SKIPPED, 0)
        self.assertEqual(len(raisons), 1)
        self.assertIn("8 tests sautés", raisons[0])

    def test_sous_plancher_rouge(self):
        raisons = v.analyser(SORTIE_SOUS_PLANCHER, 218)
        self.assertEqual(len(raisons), 1)
        self.assertIn("sous le plancher 218", raisons[0])

    def test_sortie_saine_verte(self):
        self.assertEqual(v.analyser(SORTIE_SAINE, 218), [])

    def test_failed_et_absence_de_ran_rouges(self):
        self.assertTrue(v.analyser(SORTIE_FAILED, 218))
        self.assertTrue(v.analyser("ImportError: boom", 218))

    def test_cli_code_de_sortie(self):
        for sortie, attendu in ((SORTIE_SAINE, 0), (SORTIE_SKIPPED, 1)):
            resultat = subprocess.run(
                [sys.executable, str(ROOT / "scripts" / "verifier_sortie_unittest.py"),
                 "--plancher", "1"], input=sortie, capture_output=True, text=True)
            self.assertEqual(resultat.returncode, attendu, resultat.stdout)
            self.assertIn("Ran ", resultat.stdout)  # la sortie est recopiee

    def test_main_en_memoire(self):
        with mock.patch.object(sys, "stdin", io.StringIO(SORTIE_SAINE)):
            with redirect_stdout(io.StringIO()):
                self.assertEqual(v.main(["--plancher", "218"]), 0)


if __name__ == "__main__":
    unittest.main()
