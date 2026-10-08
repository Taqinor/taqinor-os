"""ADEV73 - tests de scripts/check_date_jour_utc.py. Stdlib pur."""
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import check_date_jour_utc as g  # noqa: E402

UTC = "const d = new Date().toISOString().slice(0, 10)\n"


def _arbre(tmp, fichiers):
    r = Path(tmp)
    for rel, src in fichiers.items():
        p = r / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(src, encoding="utf-8")
    return r


class DateJourUtcTests(unittest.TestCase):
    def test_nouveau_site_rouge(self):
        with tempfile.TemporaryDirectory() as tmp:
            r = _arbre(tmp, {"frontend/src/pages/Neuf.jsx": UTC})
            erreurs = g.verifier(r, {})
            self.assertEqual(len(erreurs), 1)
            self.assertIn("pages/Neuf.jsx", erreurs[0])

    def test_site_dans_la_liste_figee_vert(self):
        with tempfile.TemporaryDirectory() as tmp:
            r = _arbre(tmp, {"frontend/src/pages/Vieux.jsx": UTC})
            self.assertEqual(g.verifier(r, {"frontend/src/pages/Vieux.jsx": 1}), [])

    def test_depassement_du_plafond_rouge(self):
        with tempfile.TemporaryDirectory() as tmp:
            r = _arbre(tmp, {"frontend/src/pages/Vieux.jsx": UTC + UTC})
            self.assertEqual(len(g.verifier(r, {"frontend/src/pages/Vieux.jsx": 1})), 1)

    def test_fichier_retire_de_la_liste_est_nomme(self):
        with tempfile.TemporaryDirectory() as tmp:
            r = _arbre(tmp, {"frontend/src/pages/Vieux.jsx": UTC})
            erreurs = g.verifier(r, {})
            self.assertIn("Vieux.jsx", erreurs[0])

    def test_cliquet_plafond_perime_rouge(self):
        with tempfile.TemporaryDirectory() as tmp:
            r = _arbre(tmp, {"frontend/src/pages/Corrige.jsx": "const d = todayLocalIso()\n"})
            erreurs = g.verifier(r, {"frontend/src/pages/Corrige.jsx": 1})
            self.assertEqual(len(erreurs), 1)
            self.assertIn("abaissez", erreurs[0])

    def test_tests_et_variantes_d_espaces(self):
        with tempfile.TemporaryDirectory() as tmp:
            r = _arbre(tmp, {
                "frontend/src/a.test.mjs": UTC,
                "frontend/src/b.js": "x = d.toISOString().slice(0,10)\n",
            })
            self.assertEqual(list(g.compter(r)), ["frontend/src/b.js"])

    def test_depot_reel_vert(self):
        self.assertEqual(g.verifier(ROOT), [])


if __name__ == "__main__":
    unittest.main()
