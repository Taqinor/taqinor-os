"""ADCG81 — scripts/check_invariants.py : un registre absent fait échouer
la garde (avant : « nothing to check », rc 0 — un renommage la désarmait).

Nouveau fichier car : aucun module de test n'existait pour check_invariants.py.

    python -m unittest scripts.tests.test_check_invariants -v
"""
import contextlib
import io
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import check_invariants as ci  # noqa: E402 — après sys.path


class AbsenceTests(unittest.TestCase):
    def setUp(self):
        self._orig = ci.INVARIANTS_FILE
        self.addCleanup(setattr, ci, "INVARIANTS_FILE", self._orig)

    def test_fichier_absent_rouge(self):
        ci.INVARIANTS_FILE = Path(tempfile.mktemp(suffix=".md"))
        sortie = io.StringIO()
        with contextlib.redirect_stdout(sortie):
            self.assertEqual(ci.main(), 1)
        self.assertIn("introuvable", sortie.getvalue())

    def test_fichier_present_inchange(self):
        """Fichier du dépôt présent ⇒ comportement inchangé (rc 0)."""
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(ci.main(), 0)


if __name__ == "__main__":
    unittest.main()
