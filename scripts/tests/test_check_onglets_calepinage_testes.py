"""Tests de scripts/check_onglets_calepinage_testes.py (CALX383).

Stdlib pur (unittest), aucune base de donnees :
    python -m unittest scripts.tests.test_check_onglets_calepinage_testes -v

Trois garanties verrouillees sur un registre SYNTHETIQUE (jamais le vrai
`atelier/onglets.js`) : un onglet sans test rougit en nommant sa `cle` et le
fichier attendu ; une `cle` dupliquee rougit en citant les DEUX lignes ; un
registre complet (tests, cles uniques, aucun contournement) ne rougit jamais.
"""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import check_onglets_calepinage_testes as cot  # noqa: E402


def write(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


class FauxAtelier:
    """Dossier `atelier/` jetable, branche sur les constantes du module."""

    def __init__(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.racine = Path(self.tmp.name)
        self.atelier = self.racine / "frontend" / "src" / "features" / "calepinage" / "atelier"
        self.atelier.mkdir(parents=True)
        self.baseline = self.racine / "scripts" / "allow.txt"

        self._sauvegarde = (
            cot.ROOT, cot.ATELIER_DIR, cot.ONGLETS_PATH, cot.RAIL_PATH,
            cot.BASELINE_PATH,
        )
        cot.ROOT = self.racine
        cot.ATELIER_DIR = self.atelier
        cot.ONGLETS_PATH = self.atelier / "onglets.js"
        cot.RAIL_PATH = self.atelier / "Rail.jsx"
        cot.BASELINE_PATH = self.baseline

    def onglets(self, corps_entrees: str):
        write(self.atelier / "onglets.js", f"export const ONGLETS = [\n{corps_entrees}\n]\n")

    def composant(self, chemin_relatif: str, avec_test: bool = True):
        cible = (self.atelier / chemin_relatif).resolve().with_suffix(".jsx")
        write(cible, "export default function X() { return null }\n")
        if avec_test:
            write(cible.with_suffix("").with_suffix(".test.jsx"),
                  "test('monte', () => {})\n")
        return cible

    def rail(self, imports_supplementaires: str = ""):
        write(self.atelier / "Rail.jsx",
              f"import {{ ONGLETS }} from './onglets'\n{imports_supplementaires}\n")

    def close(self):
        (cot.ROOT, cot.ATELIER_DIR, cot.ONGLETS_PATH, cot.RAIL_PATH,
         cot.BASELINE_PATH) = self._sauvegarde
        self.tmp.cleanup()


class BaseAtelier(unittest.TestCase):
    def setUp(self):
        self.depot = FauxAtelier()
        self.addCleanup(self.depot.close)


def entree(cle: str, chemin: str) -> str:
    return (f"  {{ cle: '{cle}', libelle: '{cle}', groupe: 'G', ordre: 10, "
            f"composant: lazy(() => import('{chemin}')) }},")


# ===========================================================================
# Detection
# ===========================================================================

class DetectionTests(BaseAtelier):
    def test_onglet_sans_test_rougit_en_nommant_la_cle_et_le_fichier(self):
        self.depot.composant("./Panneau", avec_test=False)
        self.depot.onglets(entree("mon-onglet", "./Panneau"))
        self.depot.rail()
        resultat = cot.analyse()
        cles = {e["cle"] for e in resultat["sans_test"]}
        self.assertEqual(cles, {"mon-onglet"})

    def test_main_rend_1_et_nomme_la_cle_hors_base(self):
        import contextlib
        import io
        self.depot.composant("./Panneau", avec_test=False)
        self.depot.onglets(entree("mon-onglet", "./Panneau"))
        self.depot.rail()
        sortie = io.StringIO()
        with contextlib.redirect_stdout(sortie):
            code = cot.main([])
        self.assertEqual(code, 1)
        self.assertIn("mon-onglet", sortie.getvalue())

    def test_cle_dupliquee_rougit_en_citant_les_deux_lignes(self):
        self.depot.composant("./A", avec_test=True)
        self.depot.composant("./B", avec_test=True)
        self.depot.onglets(entree("doublon", "./A") + "\n" + entree("doublon", "./B"))
        self.depot.rail()
        resultat = cot.analyse()
        self.assertIn("doublon", resultat["cles_dupliquees"])
        self.assertEqual(len(resultat["cles_dupliquees"]["doublon"]), 2)

    def test_contournement_du_registre_par_rail_est_detecte(self):
        self.depot.composant("./Enregistre", avec_test=True)
        fantome = self.depot.composant("./Fantome", avec_test=True)
        self.depot.onglets(entree("ok", "./Enregistre"))
        self.depot.rail("import Fantome from './Fantome'\n")
        resultat = cot.analyse()
        self.assertIn(fantome, resultat["bypass"])


# ===========================================================================
# Silence
# ===========================================================================

class SilenceTests(BaseAtelier):
    def test_registre_complet_ne_rougit_jamais(self):
        self.depot.composant("./A", avec_test=True)
        self.depot.composant("./B", avec_test=True)
        self.depot.onglets(entree("a", "./A") + "\n" + entree("b", "./B"))
        self.depot.rail()
        resultat = cot.analyse()
        self.assertEqual(resultat["sans_test"], [])
        self.assertEqual(resultat["cles_dupliquees"], {})
        self.assertEqual(resultat["bypass"], [])

    def test_onglet_couvert_par_le_passif_ne_fait_pas_echouer_main(self):
        import contextlib
        import io
        self.depot.composant("./Panneau", avec_test=False)
        self.depot.onglets(entree("mon-onglet", "./Panneau"))
        self.depot.rail()
        write(self.depot.baseline, cot.ENTETE_BASE + "mon-onglet  # dette de test\n")
        sortie = io.StringIO()
        with contextlib.redirect_stdout(sortie):
            code = cot.main([])
        self.assertEqual(code, 0)

    def test_composant_du_registre_importe_ailleurs_nest_pas_un_bypass(self):
        # Le composant est resolu HORS de atelier/ (patron reel :
        # `../PlanImporteCalage`) : Rail.jsx ne l'importe jamais directement,
        # donc aucun bypass — seul onglets.js le fait, via son lazy().
        cible = self.depot.racine / "frontend" / "src" / "features" / "calepinage" / "Ailleurs.jsx"
        write(cible, "export default function X() { return null }\n")
        write(cible.with_suffix("").with_suffix(".test.jsx"), "test('monte', () => {})\n")
        self.depot.onglets(entree("ailleurs", "../Ailleurs"))
        self.depot.rail()
        resultat = cot.analyse()
        self.assertEqual(resultat["sans_test"], [])
        self.assertEqual(resultat["bypass"], [])


# ===========================================================================
# Base de reference
# ===========================================================================

class BaselineTests(BaseAtelier):
    def test_write_baseline_refuse_de_grandir_sans_lautorisation(self):
        self.depot.composant("./Panneau", avec_test=False)
        self.depot.onglets(entree("mon-onglet", "./Panneau"))
        self.depot.rail()
        write(self.depot.baseline, cot.ENTETE_BASE)
        code = cot.main(["--write-baseline"])
        self.assertEqual(code, 1)

    def test_write_baseline_retire_une_dette_corrigee(self):
        self.depot.composant("./Panneau", avec_test=True)
        self.depot.onglets(entree("mon-onglet", "./Panneau"))
        self.depot.rail()
        write(self.depot.baseline, cot.ENTETE_BASE + "mon-onglet  # ancienne dette\n")
        code = cot.main(["--write-baseline"])
        self.assertEqual(code, 0)
        base = cot.charger_base(self.depot.baseline)
        self.assertNotIn("mon-onglet", base)


if __name__ == "__main__":
    unittest.main()
