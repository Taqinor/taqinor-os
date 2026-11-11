"""ATST52 — tests de scripts/check_no_anon_snapshot.py (stdlib pure).

Nouveau fichier car : aucun module de test pour ce script (texte de la tâche).
Run:
    python -m unittest scripts.tests.test_check_no_anon_snapshot -v
"""
import contextlib
import importlib
import io
import subprocess
import sys
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

garde = importlib.import_module("check_no_anon_snapshot")


class NoAnonSnapshotTests(unittest.TestCase):
    def _main(self, sortie_git=b"", erreur=None):
        resultat = subprocess.CompletedProcess(["git"], 0, stdout=sortie_git)
        texte = io.StringIO()
        with mock.patch.object(garde.subprocess, "run", return_value=resultat, side_effect=erreur), \
                contextlib.redirect_stdout(texte):
            code = garde.main()
        return code, texte.getvalue()

    def test_offending_voit_les_instantanes_et_rien_d_autre(self):
        vus = garde.offending([
            "var/anon/snap.json", "backend/var/anon/x.json", "docs/a.anon.json.gz",
            "a\\var\\anon\\b.json", "docs/anon.md", "var/anonymous.txt", "a.anon.json"])
        self.assertEqual(vus, ["var/anon/snap.json", "backend/var/anon/x.json",
                               "docs/a.anon.json.gz", "a/var/anon/b.json"])

    def test_instantane_suivi_fait_sortir_un(self):
        code, texte = self._main(b"README.md\0var/anon/snap.anon.json.gz\0")
        self.assertEqual(code, 1)
        self.assertIn("ECHEC", texte)
        self.assertIn("var/anon/snap.anon.json.gz", texte)

    def test_git_en_echec_fait_sortir_un(self):
        code, texte = self._main(erreur=subprocess.CalledProcessError(128, ["git"]))
        self.assertEqual(code, 1)
        self.assertIn("git ls-files impossible", texte)

    def test_depot_propre_sort_zero(self):
        code, texte = self._main(b"README.md\0docs/anon.md\0")
        self.assertEqual(code, 0)
        self.assertIn("OK", texte)


if __name__ == "__main__":
    unittest.main()
