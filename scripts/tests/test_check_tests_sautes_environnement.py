"""ADCG82 — tests de scripts/check_tests_sautes_environnement.py (stdlib pure).

Nouveau fichier car : aucun module de test pour ce script (texte de la tâche).
Run:
    python -m unittest scripts.tests.test_check_tests_sautes_environnement -v
"""
import contextlib
import importlib
import io
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

garde = importlib.import_module("check_tests_sautes_environnement")

#: ATST45 — les trois autres formes de saut : décorateur de classe, de méthode,
#: appel ``self.skipTest()`` (sites ``T``, ``T.test_b``, ``T.test_c``).
TROIS_FORMES = (
    "import unittest\n\n"
    "@unittest.skipIf(True, 'x')\n"
    "class T(unittest.TestCase):\n"
    "    @unittest.skip('y')\n"
    "    def test_b(self):\n        pass\n\n"
    "    def test_c(self):\n        self.skipTest('z')\n"
)


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

    def test_decorateurs_et_appel_skiptest_sont_des_sites(self):
        sites = self._sites(TROIS_FORMES)
        self.assertEqual(set(sites), {"T", "T.test_b", "T.test_c"})
        self.assertIn("self.skipTest('z')", sites["T.test_c"])


class MainTests(unittest.TestCase):
    """ATST45 — ``main()`` : site non signé ⇒ 1, tous signés ⇒ 0, entrée périmée ⇒ 1."""

    def _main(self, signes):
        with tempfile.TemporaryDirectory(dir=ROOT / "backend") as tmp:
            chemin = Path(tmp) / "test_saut.py"
            chemin.write_text(TROIS_FORMES, encoding="utf-8")
            rel = chemin.relative_to(ROOT).as_posix()
            cles = {f"{rel}::{s}" for s in signes}
            sortie = io.StringIO()
            with mock.patch.object(garde, "BACKEND", Path(tmp)), \
                    mock.patch.object(garde.ep, "charger", return_value=cles), \
                    mock.patch.object(sys, "argv", ["check"]), contextlib.redirect_stdout(sortie):
                code = garde.main()
        return code, sortie.getvalue()

    def test_saut_non_signe_rend_un(self):
        code, sortie = self._main(set())
        self.assertEqual(code, 1)
        self.assertEqual(sortie.count("saut NON SIGNÉ"), 3)

    def test_tous_signes_rend_zero(self):
        code, sortie = self._main({"T", "T.test_b", "T.test_c"})
        self.assertEqual(code, 0)
        self.assertIn("3 saut(s), tous signés", sortie)

    def test_entree_perimee_rend_un(self):
        code, sortie = self._main({"T", "T.test_b", "T.test_c", "T.test_disparu"})
        self.assertEqual(code, 1)
        self.assertIn("entrée périmée", sortie)


if __name__ == "__main__":
    unittest.main()
