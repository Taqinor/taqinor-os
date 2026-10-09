"""ACAL343 — scripts/check_calepinage_cles_document.py (dépôt factice en tmp)."""
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import _cliquet  # noqa: E402
import check_calepinage_cles_document as guard  # noqa: E402


def _repo(proprietes, exemple, ecrivain_js):
    tmp = Path(tempfile.mkdtemp())
    schema = tmp / guard.SCHEMA
    schema.parent.mkdir(parents=True)
    schema.write_text(json.dumps({"properties": {k: {} for k in proprietes},
                                  "exemple": exemple}), encoding="utf-8")
    js = tmp / "frontend" / "src" / "features" / "calepinage" / "ecrit.js"
    js.parent.mkdir(parents=True)
    js.write_text(ecrivain_js, encoding="utf-8")
    return tmp


class ClesDocumentTests(unittest.TestCase):
    def test_cle_absente_de_l_exemple_est_refusee(self):
        root = _repo(["poseSurfaces", "pin"], {"pin": 1}, "o = { poseSurfaces: 1, pin: 2 }")
        dettes, _n = guard.analyser(root)
        self.assertEqual(dettes, {"exemple::poseSurfaces"})
        erreurs = guard.verifier(dettes, set())
        self.assertIn("poseSurfaces", erreurs[0])

    def test_cle_sans_ecrivain_est_refusee_hors_liste_blanche(self):
        root = _repo(["parcelle", "pin"], {"parcelle": 1, "pin": 1}, "o = { pin: 2 }")
        dettes, _n = guard.analyser(root)
        self.assertEqual(dettes, {"ecrivain::parcelle"})
        self.assertTrue(guard.verifier(dettes, set()))
        self.assertEqual(guard.verifier(dettes, {"ecrivain::parcelle"}), [])
        self.assertTrue(guard.verifier(set(), {"ecrivain::parcelle"}))  # morte

    def test_prose_n_est_pas_un_ecrivain(self):
        root = _repo(["parcelle"], {"parcelle": 1}, "// la parcelle est lue ici")
        self.assertEqual(guard.analyser(root)[0], {"ecrivain::parcelle"})

    def test_baseline_ne_croit_pas(self):
        chemin = Path(tempfile.mkdtemp()) / "b.txt"
        _cliquet.ecrire(chemin, {"a"}, "", "r")
        with self.assertRaises(ValueError):
            _cliquet.ecrire(chemin, {"a", "b"}, "", "r")

    def test_depot_reel_vert(self):
        dettes, n = guard.analyser()
        self.assertGreater(n, 0)
        self.assertEqual(guard.verifier(dettes, _cliquet.charger(guard.BASELINE)), [])


if __name__ == "__main__":
    unittest.main()
