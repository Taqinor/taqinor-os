"""ACAL317 — scripts/check_calepinage_ecrivains_layout.py (dépôt factice en tmp)."""
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import check_calepinage_ecrivains_layout as guard  # noqa: E402


def _repo(fichiers: dict) -> Path:
    tmp = Path(tempfile.mkdtemp())
    for rel, contenu in fichiers.items():
        p = tmp / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(contenu, encoding="utf-8")
    return tmp


class EcrivainsLayoutTests(unittest.TestCase):
    def test_appel_hors_atelier_detecte(self):
        root = _repo({
            "frontend/src/features/calepinage/HorizonPanel.jsx":
                "api.calepinages.enregistrerLayoutCalepinage(id, doc)\n",
        })
        erreurs = guard.verifier(root, allow={})
        self.assertEqual(len(erreurs), 1)
        self.assertIn("HorizonPanel.jsx:1", erreurs[0])

    def test_atelier_definition_commentaire_test_ignores(self):
        root = _repo({
            guard.ATELIER: "api.enregistrerLayoutCalepinage(id, doc)\n",
            "frontend/src/api/calepinageApi.js":
                "enregistrerLayoutCalepinage: (id) => 1,\n"
                "// enregistrerLayoutCalepinage(x)\n"
                "enregistrerLayoutCalepinageConditionnel(x)\n",
            "frontend/src/features/x/A.test.jsx": "enregistrerLayoutCalepinage(1)\n",
        })
        self.assertEqual(guard.verifier(root, allow={}), [])

    def test_entree_morte_echoue(self):
        root = _repo({"frontend/src/a.js": "x\n"})
        erreurs = guard.verifier(root, allow={"frontend/src/a.js": "raison"})
        self.assertTrue(any("MORTE" in e for e in erreurs))

    def test_depot_reel_vert(self):
        self.assertEqual(guard.verifier(), [])


if __name__ == "__main__":
    unittest.main()
