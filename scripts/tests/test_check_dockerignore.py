"""ADEP4 — tests de scripts/check_dockerignore.py. Stdlib pur."""
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import check_dockerignore as cd  # noqa: E402


def _arbre(tmp, contenu, allow=''):
    r = Path(tmp)
    (r / 'svc').mkdir()
    (r / 'svc' / '.dockerignore').write_text(contenu, encoding='utf-8')
    (r / 'scripts').mkdir()
    (r / cd.ALLOW).write_text(allow, encoding='utf-8')
    return r


class DockerignoreTests(unittest.TestCase):
    def test_motif_racine_seul_rouge(self):
        with tempfile.TemporaryDirectory() as tmp:
            erreurs = cd.verifier(_arbre(tmp, '__pycache__/\n*.log\n'))
            self.assertEqual(len(erreurs), 2, erreurs)

    def test_motif_ancre_vert(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(cd.verifier(_arbre(
                tmp, '# c\n**/__pycache__/\n/media/\n**/.env.*\n!**/.env.example\n')), [])

    def test_base_autorise_et_cliquet(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(cd.verifier(_arbre(tmp, 'docs\n', 'svc/.dockerignore::docs\n')), [])
        with tempfile.TemporaryDirectory() as tmp:
            erreurs = cd.verifier(_arbre(tmp, '**/x\n', 'svc/.dockerignore::docs\n'))
            self.assertTrue(any('obsolete' in e for e in erreurs), erreurs)

    def test_depot_reel_vert(self):
        self.assertEqual(cd.verifier(ROOT), [])


if __name__ == '__main__':
    unittest.main()
