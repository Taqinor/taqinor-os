"""ADEP1 — tests de scripts/check_binaires_image.py. Stdlib pur."""
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import check_binaires_image as cbi  # noqa: E402

DOCKERFILE = ("FROM python:3.11\nRUN apt-get update && apt-get install -y --no-install-recommends \\\n"
              "    libcairo2 \\\n%s    && rm -rf /var/lib/apt/lists/*\n")
CODE = "import subprocess\nsubprocess.run(['%s', '-Fc'])\n"


def _arbre(tmp, dockerfile_extra, binaire):
    racine = Path(tmp)
    (racine / 'backend/django_core/core').mkdir(parents=True)
    (racine / cbi.DOCKERFILE).write_text(DOCKERFILE % dockerfile_extra, encoding='utf-8')
    (racine / 'backend/django_core/core/job.py').write_text(CODE % binaire, encoding='utf-8')
    return racine


class BinairesImageTests(unittest.TestCase):
    def test_binaire_sans_paquet_rouge(self):
        for binaire in ('pg_dump', 'pg_restore'):
            with self.subTest(binaire=binaire), tempfile.TemporaryDirectory() as tmp:
                erreurs = cbi.verifier(_arbre(tmp, '', binaire))
                self.assertTrue(any('postgresql-client-16' in e for e in erreurs), erreurs)

    def test_binaire_avec_paquet_vert(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(
                cbi.verifier(_arbre(tmp, '    postgresql-client-16 \\\n', 'pg_dump')), [])

    def test_binaire_inconnu_rouge(self):
        with tempfile.TemporaryDirectory() as tmp:
            erreurs = cbi.verifier(_arbre(tmp, '', 'ffmpeg'))
            self.assertTrue(any('ffmpeg' in e and 'BINAIRES' in e for e in erreurs), erreurs)

    def test_depot_reel_vert(self):
        self.assertEqual(cbi.verifier(ROOT), [])


if __name__ == '__main__':
    unittest.main()
