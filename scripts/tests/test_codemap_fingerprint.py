"""ADCG65 — scripts/codemap_fingerprint.py : une montée de version seule
(PR Dependabot) garde l'empreinte de structure ; un paquet ajouté la change.

Nouveau fichier car : aucun module de test n'existait pour codemap_fingerprint.py.

    python -m unittest scripts.tests.test_codemap_fingerprint -v
"""
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import codemap_fingerprint as cfp  # noqa: E402 — après sys.path

REQ = "Django==5.2.1\nPillow==12.3.0  # images\ncelery[redis]>=5.4,<6\n"
PKG = ('{\n  "name": "f",\n  "dependencies": {"axios": "^1.20.0"},\n'
       '  "devDependencies": {"vite": "7.1.0"}\n}\n')
CI = "jobs:\n  t:\n    steps:\n      - uses: actions/checkout@v4\n      - run: echo ok\n"


class EmpreinteStructureTests(unittest.TestCase):
    def setUp(self):
        self.racine = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.racine, ignore_errors=True)
        self._orig = (cfp.ROOT, cfp.CODEMAP)
        self.addCleanup(self._restaurer)
        cfp.ROOT, cfp.CODEMAP = self.racine, self.racine / "docs" / "CODEMAP.md"
        self.ecrire("backend/django_core/requirements.txt", REQ)
        self.ecrire("frontend/package.json", PKG)
        self.ecrire(".github/workflows/ci.yml", CI)

    def _restaurer(self):
        cfp.ROOT, cfp.CODEMAP = self._orig

    def ecrire(self, rel, texte):
        chemin = self.racine / rel
        chemin.parent.mkdir(parents=True, exist_ok=True)
        chemin.write_text(texte, encoding="utf-8")

    def test_montee_de_version_seule_garde_l_empreinte(self):
        avant = cfp.compute_fingerprint()
        self.ecrire("backend/django_core/requirements.txt",
                    REQ.replace("Pillow==12.3.0", "Pillow==13.0.0").replace(">=5.4,<6", ">=5.5,<7"))
        self.ecrire("frontend/package.json", PKG.replace("^1.20.0", "^1.21.0"))
        self.ecrire(".github/workflows/ci.yml", CI.replace("@v4", "@v5"))
        self.assertEqual(cfp.compute_fingerprint(), avant)

    def test_paquet_ajoute_change_l_empreinte(self):
        avant = cfp.compute_fingerprint()
        self.ecrire("backend/django_core/requirements.txt", REQ + "nouveau-paquet==1.0\n")
        self.assertNotEqual(cfp.compute_fingerprint(), avant)

    def test_dependance_npm_ajoutee_ou_action_changee_change_l_empreinte(self):
        avant = cfp.compute_fingerprint()
        self.ecrire("frontend/package.json", PKG.replace('"axios": "^1.20.0"',
                                                         '"axios": "^1.20.0", "zod": "3.0.0"'))
        self.assertNotEqual(cfp.compute_fingerprint(), avant)
        self.ecrire("frontend/package.json", PKG)
        self.ecrire(".github/workflows/ci.yml", CI.replace("actions/checkout", "actions/autre"))
        self.assertNotEqual(cfp.compute_fingerprint(), avant)


if __name__ == "__main__":
    unittest.main()
