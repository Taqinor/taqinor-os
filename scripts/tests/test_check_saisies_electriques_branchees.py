"""ACAL322 — scripts/check_saisies_electriques_branchees.py (dépôt factice en tmp)."""
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import _cliquet  # noqa: E402
import check_saisies_electriques_branchees as guard  # noqa: E402

ELECTRIQUE = "CHAMPS_ENTREE = (\n    'alpha',\n    'beta',\n)\n"
PARAMETRES = (
    "SECTION_SIMULATION = 'simulation'\n"
    "CLES_SIMULATION = (\n    ('gamma', 'libelle', '', 'ref'),\n)\n"
    "REGISTRES = {SECTION_SIMULATION: CLES_SIMULATION}\n"
)


def _repo(extra: dict) -> Path:
    tmp = Path(tempfile.mkdtemp())
    fichiers = {str(guard.ELECTRIQUE): ELECTRIQUE, str(guard.PARAMETRES): PARAMETRES}
    fichiers.update(extra)
    for rel, contenu in fichiers.items():
        p = tmp / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(contenu, encoding="utf-8")
    return tmp


class SaisiesBrancheesTests(unittest.TestCase):
    def test_cle_sans_ecran_detectee(self):
        root = _repo({
            str(guard.BACKEND / "services" / "lecteur.py"):
                "def f(d):\n    return d['alpha'], d['beta'], d.get('gamma')\n",
            str(guard.FRONT_API): "const o = { alpha: 1 }\n",
        })
        dettes = guard.analyser(root)
        self.assertEqual(dettes, {"entree::beta::ecran"})

    def test_cle_sans_lecteur_detectee(self):
        root = _repo({
            str(guard.BACKEND / "services" / "lecteur.py"): "def f(d):\n    return d['alpha']\n",
            str(guard.FRONT_API): "alpha beta\n",
        })
        dettes = guard.analyser(root)
        self.assertEqual(dettes, {"entree::beta::lecteur", "registre::simulation.gamma::lecteur"})
        self.assertTrue(guard.verifier(dettes, set()))

    def test_baseline_ne_croit_pas(self):
        chemin = Path(tempfile.mkdtemp()) / "b.txt"
        _cliquet.ecrire(chemin, {"a"}, "", "r")  # amorçage (fichier absent)
        with self.assertRaises(ValueError):
            _cliquet.ecrire(chemin, {"a", "b"}, "", "r")
        _cliquet.ecrire(chemin, set(), "", "r")  # rétrécir : permis
        self.assertEqual(_cliquet.charger(chemin), set())

    def test_cle_morte_echoue(self):
        self.assertTrue(guard.verifier(set(), {"entree::x::ecran"}))

    def test_depot_reel_vert(self):
        self.assertEqual(guard.verifier(guard.analyser(), _cliquet.charger(guard.BASELINE)), [])


if __name__ == "__main__":
    unittest.main()
