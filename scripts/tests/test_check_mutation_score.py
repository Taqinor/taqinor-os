"""ENF12 — tests de scripts/check_mutation_score.py."""
import importlib
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

ms = importlib.import_module("check_mutation_score")


class MutationScoreTests(unittest.TestCase):
    def test_passe_vide_echoue(self):
        ok, msg = ms.evaluer({"killed": 0, "survived": 0, "total": 5608})
        self.assertFalse(ok)
        self.assertIn("pas réellement tourné", msg)

    def test_sous_le_plancher_echoue(self):
        ok, _ = ms.evaluer({"killed": 40, "survived": 60})
        self.assertFalse(ok)

    def test_au_dessus_du_plancher_passe(self):
        ok, msg = ms.evaluer({"killed": 70, "timeout": 5, "survived": 25})
        self.assertTrue(ok, msg)

    def test_fichier_absent_echoue(self):
        self.assertEqual(ms.main(["x", os.path.join(tempfile.gettempdir(), "absent-enf12.json")]), 1)

    def test_fichier_valide(self):
        with tempfile.TemporaryDirectory() as tmp:
            chemin = os.path.join(tmp, "stats.json")
            with open(chemin, "w", encoding="utf-8") as fh:
                json.dump({"killed": 90, "survived": 10}, fh)
            self.assertEqual(ms.main(["x", chemin]), 0)


if __name__ == "__main__":
    unittest.main()
