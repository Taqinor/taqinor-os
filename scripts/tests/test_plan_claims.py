"""ADCG85 — scripts/plan_claims.py : jamais un bail perdu en silence.

Nouveau fichier car : aucun module de test n'existait pour plan_claims.py.
Faux origin = dépôt nu local (`git init --bare`) ; un hook `pre-receive` qui
sort 1 simule un push refusé.

    python -m unittest scripts.tests.test_plan_claims -v
"""
import contextlib
import io
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import plan_claims as pc  # noqa: E402 — après sys.path


def _git(cwd, *args):
    return subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, check=True)


class ClaimTests(unittest.TestCase):
    def setUp(self):
        tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, tmp, ignore_errors=True)
        self.origin = tmp / "origin.git"
        _git(tmp, "init", "-q", "--bare", str(self.origin))
        self.travail = [tmp / "w1", tmp / "w2"]
        for w in self.travail:
            _git(tmp, "init", "-q", str(w))
            _git(w, "remote", "add", "origin", str(self.origin))
            _git(w, "config", "user.name", "test")
            _git(w, "config", "user.email", "test@example.invalid")
        avant = os.getcwd()
        self.addCleanup(os.chdir, avant)
        os.chdir(self.travail[0])

    def lancer(self, *args, travail=0):
        os.chdir(self.travail[travail])
        sortie = io.StringIO()
        with contextlib.redirect_stdout(sortie):
            rc = pc.main(list(args))
        return rc, sortie.getvalue()

    def baux(self):
        os.chdir(self.travail[0])
        return {s: d for s, (_sha, d) in pc.remote_claims().items()}

    def refuser_les_push(self):
        hook = self.origin / "hooks" / "pre-receive"
        hook.write_text("#!/bin/sh\nexit 1\n", encoding="utf-8", newline="\n")
        hook.chmod(0o755)

    def test_retour_arriere_garde_les_baux_deja_tenus(self):
        self.assertEqual(self.lancer("claim", "file:A", "--owner", "X/1")[0], 0)
        self.assertEqual(self.lancer("claim", "file:B", "--owner", "Y/2")[0], 0)
        rc, out = self.lancer("claim", "file:A", "file:C", "file:B", "--owner", "X/1")
        self.assertEqual(rc, 1, out)
        baux = self.baux()
        self.assertEqual(baux["file_A"]["owner"], "X/1")   # déjà tenu : gardé
        self.assertEqual(baux["file_B"]["owner"], "Y/2")
        self.assertNotIn("file_C", baux)                   # neuve : rendue

    def test_renew_refuse_sort_1(self):
        self.assertEqual(self.lancer("claim", "file:A", "--owner", "X/1")[0], 0)
        self.refuser_les_push()
        rc, out = self.lancer("renew", "file:A", "--owner", "X/1")
        self.assertEqual(rc, 1, out)
        self.assertIn("NON RENOUVELÉ file:A", out)

    def test_release_refuse_sort_1(self):
        self.assertEqual(self.lancer("claim", "file:A", "--owner", "X/1")[0], 0)
        self.refuser_les_push()
        rc, out = self.lancer("release", "file:A", "--owner", "X/1")
        self.assertEqual(rc, 1, out)
        self.assertIn("NON LIBÉRÉ file:A", out)
        self.assertIn("file_A", self.baux())

    def test_bail_porte_un_message_json(self):
        self.lancer("claim", "app:crm", "--owner", "X/1", "--branch", "dev-all")
        self.assertEqual(self.baux()["app_crm"]["branch"], "dev-all")


if __name__ == "__main__":
    unittest.main()
