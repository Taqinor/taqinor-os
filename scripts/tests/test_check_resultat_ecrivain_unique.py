"""ACAL321 — scripts/check_resultat_ecrivain_unique.py."""
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import check_resultat_ecrivain_unique as guard  # noqa: E402


def _repo(fichiers: dict) -> Path:
    tmp = Path(tempfile.mkdtemp())
    for rel, contenu in fichiers.items():
        p = tmp / guard.APP / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(contenu, encoding="utf-8")
    return tmp


class ResultatEcrivainUniqueTests(unittest.TestCase):
    def test_ecriture_directe_detectee(self):
        root = _repo({
            "services/sld.py": "def f(calepinage, r):\n    calepinage.resultat = r\n",
            "services/autre.py": (
                "def g(c):\n    c.save(update_fields=['resultat', 'updated_at'])\n"),
        })
        trouves = guard.analyser(root)
        self.assertEqual(len(trouves), 2)
        self.assertTrue(any(c.endswith("sld.py::f") for c in trouves))
        erreurs = guard.verifier(trouves, set())
        self.assertEqual(len(erreurs), 2)
        self.assertIn("sld.py:2", " ".join(erreurs))

    def test_helper_et_layout_exemptes(self):
        root = _repo({
            "services/resultat.py": "def m(c, r):\n    c.resultat = r\n",
            "services/layout.py": "def m(c, r):\n    c.resultat = r\n",
            "tests/test_x.py": "def t(c):\n    c.resultat = 1\n",
            "migrations/0001.py": "def t(c):\n    c.resultat = 1\n",
        })
        self.assertEqual(guard.analyser(root), {})

    def test_baseline_ne_croit_pas(self):
        tmp = Path(tempfile.mkdtemp()) / "base.txt"
        with self.assertRaises(ValueError):
            guard.ecrire_base({"a.py::f"}, path=tmp, base_actuelle=set())
        guard.ecrire_base({"a.py::f"}, path=tmp, base_actuelle=set(),
                          autoriser_croissance=True)
        guard.ecrire_base(set(), path=tmp)  # rétrécir est toujours permis
        self.assertEqual(guard.charger_base(tmp), set())

    def test_cle_morte_echoue(self):
        self.assertTrue(guard.verifier({}, {"x.py::f"}))

    def test_depot_reel_vert(self):
        self.assertEqual(guard.verifier(guard.analyser(), guard.charger_base()), [])


if __name__ == "__main__":
    unittest.main()
