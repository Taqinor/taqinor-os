"""ADCG82 — tests de scripts/check_tests_sautes_environnement.py (stdlib pure).

Nouveau fichier car : aucun module de test pour ce script (texte de la tâche).
Run:
    python -m unittest scripts.tests.test_check_tests_sautes_environnement -v
"""
import importlib
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

garde = importlib.import_module("check_tests_sautes_environnement")


class SitesTests(unittest.TestCase):
    def _sites(self, source):
        with tempfile.TemporaryDirectory(dir=ROOT / "backend") as tmp:
            chemin = Path(tmp) / "test_saut.py"
            chemin.write_text(source, encoding="utf-8")
            rel = chemin.relative_to(ROOT).as_posix()
            return {k.replace(rel + "::", ""): v for k, v in garde._sites_fichier(chemin).items()}

    def test_raise_skiptest_est_un_site(self):
        sites = self._sites(
            "import unittest\nfrom unittest import SkipTest\n\n"
            "class T(unittest.TestCase):\n"
            "    def test_a(self):\n        raise unittest.SkipTest('x')\n\n"
            "    def test_b(self):\n        raise SkipTest\n"
        )
        self.assertEqual(set(sites), {"T.test_a", "T.test_b"})
        self.assertIn("raise unittest.SkipTest('x')", sites["T.test_a"])

    def test_autre_raise_ignore(self):
        sites = self._sites("def f():\n    raise ValueError('x')\n\ndef g():\n    raise\n")
        self.assertEqual(sites, {})


if __name__ == "__main__":
    unittest.main()
