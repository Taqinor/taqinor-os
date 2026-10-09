"""ADEP24 - tests de scripts/check_test_determinism.py. Stdlib pur."""
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import check_test_determinism as ctd  # noqa: E402


def _arbre(tmp, fichiers):
    r = Path(tmp)
    for rel, contenu in fichiers.items():
        p = r / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(contenu, encoding="utf-8")
    return r


class DeterminismeTests(unittest.TestCase):
    def test_sleep_nu_importe_rouge(self):
        with tempfile.TemporaryDirectory() as tmp:
            r = _arbre(tmp, {"backend/django_core/apps/x/tests/test_a.py":
                             "from time import sleep\n\ndef test():\n    sleep(2)\n"})
            f = ctd.scan(r, set())
            self.assertEqual(len(f), 1, f)
            self.assertIn("test_a.py:4", f[0])

    def test_time_sleep_toujours_rouge(self):
        with tempfile.TemporaryDirectory() as tmp:
            r = _arbre(tmp, {"backend/django_core/apps/x/tests/test_a.py":
                             "import time\ntime.sleep(1)\n"})
            self.assertEqual(len(ctd.scan(r, set())), 1)

    def test_spec_ts_rouge(self):
        with tempfile.TemporaryDirectory() as tmp:
            r = _arbre(tmp, {"frontend/e2e/a.spec.ts": "await page.waitForTimeout(500)\n"})
            f = ctd.scan(r, set())
            self.assertEqual(len(f), 1, f)
            self.assertIn("a.spec.ts:1", f[0])

    def test_settimeout_attendu_rouge(self):
        with tempfile.TemporaryDirectory() as tmp:
            r = _arbre(tmp, {"frontend/e2e/b.spec.js":
                             "await new Promise(r => setTimeout(r, 1000))\n"})
            self.assertEqual(len(ctd.scan(r, set())), 1)

    def test_budget_de_test_playwright_vert(self):
        with tempfile.TemporaryDirectory() as tmp:
            r = _arbre(tmp, {"frontend/e2e/c.spec.js": "test.setTimeout(180_000)\n"})
            self.assertEqual(ctd.scan(r, set()), [])

    def test_base_autorise_et_orpheline(self):
        with tempfile.TemporaryDirectory() as tmp:
            r = _arbre(tmp, {"frontend/e2e/b.spec.js": "setTimeout(r, 1000)\n"})
            self.assertEqual(ctd.scan(r, {"frontend/e2e/b.spec.js :: setTimeout(r, 1000)"}), [])
            f = ctd.scan(r, {"frontend/e2e/b.spec.js :: setTimeout(r, 1000)",
                             "frontend/e2e/z.spec.js :: setTimeout(r, 9)"})
            self.assertEqual(len(f), 1)
            self.assertIn("orpheline", f[0])

    def test_depot_reel_vert(self):
        self.assertEqual(ctd.scan(ROOT), [])

    def test_cles_vivantes_par_contenu(self):
        for cle in ctd.WHITELISTED_LIVE_NOW:
            rel, _, ligne = cle.partition(" :: ")
            fichier = ROOT / "backend" / "django_core" / rel
            self.assertTrue(fichier.exists(), rel)
            self.assertIn(ligne, [x.strip() for x in fichier.read_text(encoding="utf-8").splitlines()])

    def test_cle_orpheline_rouge(self):
        with tempfile.TemporaryDirectory() as tmp:
            r = _arbre(tmp, {"backend/django_core/apps/x/tests/test_a.py": "x = 1\n"})
            f = ctd.scan(r, set(), {"apps/x/tests/test_a.py :: self.assertEqual(a, timezone.now())"})
            self.assertTrue(any("orpheline" in x and "apps/x/tests/test_a.py" in x for x in f), f)


if __name__ == "__main__":
    unittest.main()
