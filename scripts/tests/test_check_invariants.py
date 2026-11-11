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


class ReferencesTests(unittest.TestCase):
    """ATST44 (C-ATST-023) — la branche cœur : une référence qui ne résout
    plus fait sortir 1 (registre et racine backend temporaires)."""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.racine = Path(tmp.name)
        demo = self.racine / "apps" / "demo"
        demo.mkdir(parents=True)
        (demo / "tests.py").write_text(
            "class DemoTests:\n    def test_ok(self):\n        pass\n", encoding="utf-8")
        (demo / "casse.py").write_text("class X(:\n", encoding="utf-8")
        for nom, valeur in (("INVARIANTS_FILE", self.racine / "invariants.md"),
                            ("BACKEND_ROOT", self.racine)):
            self.addCleanup(setattr, ci, nom, getattr(ci, nom))
            setattr(ci, nom, valeur)

    def _jouer(self, ligne):
        ci.INVARIANTS_FILE.write_text(f"- {ligne}\n", encoding="utf-8")
        sortie = io.StringIO()
        with contextlib.redirect_stdout(sortie):
            rc = ci.main()
        return rc, sortie.getvalue()

    def test_reference_resolue_rend_zero(self):
        rc, sortie = self._jouer("`apps/demo/tests.py::DemoTests::test_ok`")
        self.assertEqual(rc, 0)
        self.assertIn("1 reference(s)", sortie)

    def test_methode_renommee_rend_un(self):
        rc, sortie = self._jouer("`apps/demo/tests.py::DemoTests::test_absent`")
        self.assertEqual(rc, 1)
        self.assertIn("not found", sortie)

    def test_fichier_absent_rend_un(self):
        rc, sortie = self._jouer("`apps/demo/absent.py::X::y`")
        self.assertEqual(rc, 1)
        self.assertIn("file not found", sortie)

    def test_fichier_illisible_rend_un(self):
        rc, sortie = self._jouer("`apps/demo/casse.py::X::y`")
        self.assertEqual(rc, 1)
        self.assertIn("could not parse", sortie)

    def test_registre_sans_reference_sort(self):
        with self.assertRaises(SystemExit):
            self._jouer("aucune référence ici")


if __name__ == "__main__":
    unittest.main()
