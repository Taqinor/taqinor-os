"""ADEP2/ADEP3 — tests de scripts/check_parite_image_ci.py. Stdlib pur."""
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import check_parite_image_ci as cp  # noqa: E402 — après sys.path/setup() (D-ENF22)

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

    def test_paquet_ci_absent_prod_rouge(self):
        with tempfile.TemporaryDirectory() as tmp:
            r = _arbre(tmp, 'fonts-noto-core')
            (r / cp.PROD).write_text(PROD.replace('fonts-noto-core', ''), encoding='utf-8')
            erreurs = cp.verifier_apt(r)
            self.assertTrue(any('fonts-noto-core : present dans .github/ci-image/Dockerfile, '
                                'absent de backend/django_core/Dockerfile' in e for e in erreurs), erreurs)

    def test_outillage_ci_seul_admis(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(cp.verifier_apt(_arbre(tmp, 'fonts-noto-core procps zstd')), [])

    def test_dejavu_interdit(self):
        with tempfile.TemporaryDirectory() as tmp:
            erreurs = cp.verifier_apt(_arbre(tmp, 'fonts-noto-core fonts-dejavu-core'))
            self.assertTrue(any('fonts-dejavu-core' in e for e in erreurs))


class NodeTests(unittest.TestCase):
    def test_node_majeure_divergente_rouge(self):
        with tempfile.TemporaryDirectory() as tmp:
            erreurs = cp.verifier_node(_arbre(tmp, '', front='FROM node:20.18-alpine\n'))
            self.assertTrue(any('node-version 22' in e for e in erreurs), erreurs)

    def test_tag_flottant_rouge(self):
        with tempfile.TemporaryDirectory() as tmp:
            erreurs = cp.verifier_node(_arbre(tmp, '', front='FROM node:22-alpine\n'))
            self.assertTrue(any('flottant' in e for e in erreurs), erreurs)

    def test_node_vert(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(cp.verifier_node(_arbre(tmp, '')), [])


class PythonTests(unittest.TestCase):
    """ADCG90 — tag `FROM python:` identique prod / CI ; workflows sur la même mineure."""

    def _python(self, tmp, ci='3.11.11-slim-bookworm', ia='3.11.11-slim-bookworm', wf='3.11'):
        r = _arbre(tmp, 'fonts-noto-core')
        (r / cp.PROD).write_text('FROM python:3.11.11-slim-bookworm\n' + PROD, encoding='utf-8')
        (r / cp.COPIES_CI[0]).write_text(f'FROM python:{ci}\n', encoding='utf-8')
        (r / 'backend' / 'fastapi_ia').mkdir(parents=True)
        (r / 'backend' / 'fastapi_ia' / 'Dockerfile').write_text(f'FROM python:{ia}\n', encoding='utf-8')
        workflow = r / '.github' / 'workflows' / 'x.yml'
        workflow.write_text(f"          python-version: '{wf}'\n", encoding='utf-8')
        return cp.verifier_python(r)

    def test_tag_python_ci_divergent_rouge(self):
        with tempfile.TemporaryDirectory() as tmp:
            erreurs = self._python(tmp, ci='3.11-slim-bookworm')
            self.assertEqual(len(erreurs), 1, erreurs)
            self.assertIn('python:3.11-slim-bookworm contre python:3.11.11-slim-bookworm', erreurs[0])
        with tempfile.TemporaryDirectory() as tmp:
            self.assertIn('backend/fastapi_ia/Dockerfile', ' '.join(self._python(tmp, ia='3.12.1-slim')))

    def test_python_version_workflow_divergente_rouge(self):
        with tempfile.TemporaryDirectory() as tmp:
            erreurs = self._python(tmp, wf='3.12')
            self.assertTrue(any('x.yml : python-version 3.12 contre Python 3.11' in e for e in erreurs), erreurs)

    def test_python_vert(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(self._python(tmp), [])


class DepotReelTests(unittest.TestCase):
    def test_depot_reel_vert(self):
        self.assertEqual(cp.verifier(ROOT), [])


if __name__ == '__main__':
    unittest.main()
