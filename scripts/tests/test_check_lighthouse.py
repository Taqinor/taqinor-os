"""ENF12 — tests de scripts/check_lighthouse.py."""
import importlib
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

lh = importlib.import_module("check_lighthouse")


def rapport(perf, a11y=0.93, bp=0.92, seo=1.0):
    return {"categories": {"performance": {"score": perf}, "accessibility": {"score": a11y},
                           "best-practices": {"score": bp}, "seo": {"score": seo}}}


class LighthouseTests(unittest.TestCase):
    def test_mesures_du_jour_passent(self):
        for perf, bp in ((0.69, 0.92), (0.44, 0.92), (0.61, 0.77), (0.72, 0.77)):
            ok, lignes = lh.evaluer([rapport(perf, bp=bp)])
            self.assertTrue(ok, lignes)

    def test_mediane_de_trois(self):
        ok, _ = lh.evaluer([rapport(0.30), rapport(0.60), rapport(0.70)])
        self.assertTrue(ok)
        ok, _ = lh.evaluer([rapport(0.30), rapport(0.35), rapport(0.70)])
        self.assertFalse(ok)

    def test_regression_a11y_echoue(self):
        ok, _ = lh.evaluer([rapport(0.7, a11y=0.85)])
        self.assertFalse(ok)

    def test_aucun_rapport_echoue(self):
        ok, _ = lh.evaluer([])
        self.assertFalse(ok)

    def test_categorie_absente_echoue(self):
        ok, _ = lh.evaluer([{"categories": {"performance": {"score": 0.9}}}])
        self.assertFalse(ok)


if __name__ == "__main__":
    unittest.main()
