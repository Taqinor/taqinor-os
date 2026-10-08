"""ADEP2/ADEP3 — tests de scripts/check_parite_image_ci.py. Stdlib pur."""
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import check_parite_image_ci as cp  # noqa: E402

PROD = ("FROM python:3.11\nRUN apt-get update && apt-get install -y --no-install-recommends \\\n"
        "    libcairo2 fonts-noto-core libxml2-dev \\\n    && rm -rf /var/lib/apt/lists/*\n")
CI = "RUN apt-get install -y --no-install-recommends libcairo2 %s\n"


def _arbre(tmp, ci_paquets, front='FROM node:22.12-alpine AS builder\n', wf_node='22'):
    r = Path(tmp)
    for rel in (cp.PROD, *cp.COPIES_CI, cp.DOCKERFILE_FRONT, *cp.WORKFLOWS_NODE):
        (r / rel).parent.mkdir(parents=True, exist_ok=True)
    (r / cp.PROD).write_text(PROD, encoding='utf-8')
    for rel in cp.COPIES_CI:
        (r / rel).write_text(CI % ci_paquets, encoding='utf-8')
    (r / cp.DOCKERFILE_FRONT).write_text(front, encoding='utf-8')
    for rel in cp.WORKFLOWS_NODE:
        (r / rel).write_text(f"          node-version: '{wf_node}'\n", encoding='utf-8')
    return r


class ParitePaquetsTests(unittest.TestCase):
    def test_paquet_prod_absent_ci_rouge(self):
        with tempfile.TemporaryDirectory() as tmp:
            erreurs = cp.verifier_apt(_arbre(tmp, ''))
            self.assertEqual(len(erreurs), 3, erreurs)
            self.assertTrue(all('fonts-noto-core' in e for e in erreurs))

    def test_parite_vert_et_dev_ignore(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(cp.verifier_apt(_arbre(tmp, 'fonts-noto-core')), [])

    def test_dejavu_interdit(self):
        with tempfile.TemporaryDirectory() as tmp:
            erreurs = cp.verifier_apt(_arbre(tmp, 'fonts-noto-core fonts-dejavu-core'))
            self.assertTrue(any('fonts-dejavu-core' in e for e in erreurs))


class DepotReelTests(unittest.TestCase):
    def test_depot_reel_vert(self):
        self.assertEqual(cp.verifier(ROOT), [])


if __name__ == '__main__':
    unittest.main()
