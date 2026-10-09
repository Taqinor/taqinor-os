"""ACAL341 — scripts/check_tests_skips_inconditionnels.py (fichiers factices)."""
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import check_tests_skips_inconditionnels as guard  # noqa: E402

SQUELETTE = '''
import unittest

class T(unittest.TestCase):
    @unittest.skip("a faire")
    def test_squelette(self):
        raise NotImplementedError
'''
SKIPUNLESS_NOTIMPL = '''
import unittest

class T(unittest.TestCase):
    @unittest.skipUnless(False, "dependance absente")
    def test_x(self):
        raise NotImplementedError
'''
RAISON_CI = '''
import unittest

class T(unittest.TestCase):
    @unittest.skip("CI validera")
    def test_y(self):
        self.assertTrue(True)
'''
SKIPUNLESS_OK = '''
import unittest

class T(unittest.TestCase):
    @unittest.skipUnless(False, "dependance absente")
    def test_z(self):
        self.assertTrue(True)
'''
SKIP_VIDE = '''
import pytest

@pytest.mark.skip(reason="plus tard")
def test_vide():
    pass
'''


def _regles(source):
    return {(f, r) for f, _l, r in guard.analyser_source(source)}


class SkipsInconditionnelsTests(unittest.TestCase):
    def test_skip_inconditionnel_plus_notimplemented_est_refuse(self):
        self.assertEqual(_regles(SQUELETTE), {("test_squelette", "c")})
        self.assertEqual(_regles(SKIP_VIDE), {("test_vide", "a")})

    def test_skipunless_est_admis(self):
        self.assertEqual(_regles(SKIPUNLESS_OK), set())
        # ... mais un NotImplementedError dans un test reste refusé (règle c)
        self.assertEqual(_regles(SKIPUNLESS_NOTIMPL), {("test_x", "c")})

    def test_raison_ci_validera_est_refusee(self):
        self.assertEqual(_regles(RAISON_CI), {("test_y", "b")})
        self.assertEqual(_regles(
            "def test_t(self):\n    self.skipTest('non exécuté ici')\n"),
            {("test_t", "b")})

    def test_depot_factice_et_cliquet(self):
        tmp = Path(tempfile.mkdtemp())
        f = tmp / guard.BACKEND / "apps" / "x" / "tests" / "test_a.py"
        f.parent.mkdir(parents=True)
        f.write_text(SQUELETTE, encoding="utf-8")
        trouves = guard.analyser(tmp)
        self.assertEqual(len(trouves), 1)
        self.assertTrue(guard.verifier(trouves, set()))
        cle = next(iter(trouves))
        self.assertEqual(guard.verifier(trouves, {cle}), [])
        self.assertTrue(guard.verifier({}, {cle}))  # clé morte

    def test_depot_reel_vert(self):
        self.assertEqual(guard.verifier(guard.analyser(),
                                        guard._cliquet.charger(guard.BASELINE)), [])


if __name__ == "__main__":
    unittest.main()
