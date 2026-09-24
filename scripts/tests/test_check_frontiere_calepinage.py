"""Tests de scripts/check_frontiere_calepinage.py (CALX372).

Stdlib pur (unittest), aucune base de donnees :
    python -m unittest scripts.tests.test_check_frontiere_calepinage -v

DETECTION : chaque forme d'import interdit (import, from … import, from apps
import ged, from apps.visites import models, import_module littéral) rougit
en citant `fichier:ligne`. SILENCE : apps.visites.selectors, les imports
relatifs et les fichiers de test ne comptent pas ; une dette gelée ne fait pas
échouer `main`. BASE : une ligne devenue inutile rougit ; --write-baseline
ré-enregistre un import DÉPLACÉ mais refuse un import NOUVEAU. REEL : le
dépôt passe avec sa base committée.
"""
from __future__ import annotations

import contextlib
import io
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import check_frontiere_calepinage as cfc  # noqa: E402


def write(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def lancer(argv=()) -> tuple:
    sortie = io.StringIO()
    with contextlib.redirect_stdout(sortie):
        code = cfc.main(list(argv))
    return code, sortie.getvalue()


class FauxDepot:
    def __init__(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.racine = Path(self.tmp.name)
        self.calepinage = (self.racine / "backend" / "django_core" / "apps"
                           / "calepinage")
        self.baseline = self.racine / "scripts" / "allow.txt"
        self.baseline.parent.mkdir(parents=True)
        self._sauvegarde = (cfc.ROOT, cfc.CALEPINAGE_DIR, cfc.BASELINE_PATH)
        cfc.ROOT = self.racine
        cfc.CALEPINAGE_DIR = self.calepinage
        cfc.BASELINE_PATH = self.baseline
        write(self.calepinage / "__init__.py", "")

    def module(self, relatif: str, contenu: str) -> Path:
        return write(self.calepinage / relatif, contenu)

    def close(self):
        cfc.ROOT, cfc.CALEPINAGE_DIR, cfc.BASELINE_PATH = self._sauvegarde
        self.tmp.cleanup()


class BaseDepot(unittest.TestCase):
    def setUp(self):
        self.depot = FauxDepot()
        self.addCleanup(self.depot.close)


# ===========================================================================
# Detection
# ===========================================================================

class DetectionTests(BaseDepot):
    def test_import_ged_neuf_cite_fichier_et_ligne(self):
        self.depot.module("services/pack.py",
                          "x = 1\n\ndef f():\n    from apps.ged.services import deposit_document\n")
        code, sortie = lancer()
        self.assertEqual(code, 1)
        self.assertIn("apps/calepinage/services/pack.py:4", sortie)
        self.assertIn("apps.ged.services", sortie)

    def test_toutes_les_formes_d_import(self):
        source = (
            "import apps.ao.models\n"                       # 1
            "from apps.ao import selectors\n"               # 2
            "from apps import ged\n"                        # 3
            "from apps.visites import models\n"             # 4
            "from apps.visites.models import VisiteTerrain\n"  # 5
            "import importlib\n"                            # 6
            "importlib.import_module('apps.ao.services')\n"  # 7
            "__import__('apps.ged')\n"                      # 8
        )
        self.assertEqual(cfc.imports_interdits(source), [
            (1, "apps.ao.models"), (2, "apps.ao"), (3, "apps.ged"),
            (4, "apps.visites.models"), (5, "apps.visites.models"),
            (7, "apps.ao.services"), (8, "apps.ged"),
        ])

    def test_selectors_des_visites_admis(self):
        source = ("from apps.visites.selectors import releve_pour_calepinage\n"
                  "import apps.visites.selectors\n"
                  "from apps.crm.selectors import get_company_lead\n")
        self.assertEqual(cfc.imports_interdits(source), [])

    def test_noms_voisins_non_confondus(self):
        source = ("import apps.aof\nfrom apps.gedx import y\n"
                  "from apps.visites import selectors\n")
        self.assertEqual(cfc.imports_interdits(source), [])

    def test_imports_relatifs_et_nom_dynamique_ignores(self):
        source = ("from .models import Calepinage\nfrom ..ged import x\n"
                  "nom = 'apps.ged'\nimportlib.import_module(nom)\n")
        self.assertEqual(cfc.imports_interdits(source), [])

    def test_texte_illisible_jamais_accuse(self):
        self.assertEqual(cfc.imports_interdits("def (:\n"), [])

    def test_fichiers_de_test_ignores(self):
        self.depot.module("tests/test_x.py", "import apps.ao.models\n")
        self.depot.module("tests_y.py", "from apps.ged import services\n")
        self.depot.module("services/test_z.py", "import apps.ged\n")
        self.depot.module("services/propre.py", "x = 1\n")
        code, sortie = lancer()
        self.assertEqual(code, 0, sortie)


# ===========================================================================
# Base de reference
# ===========================================================================

class BaseTests(BaseDepot):
    SOURCE = "def f():\n    from apps.ged.services import fusionner_pdf\n"

    def test_dette_gelee_ne_rougit_pas(self):
        self.depot.module("services/pack.py", self.SOURCE)
        self.assertEqual(lancer(["--write-baseline"])[0], 0)  # amorce
        code, sortie = lancer()
        self.assertEqual(code, 0, sortie)
        self.assertIn("1 dette(s)", sortie)

    def test_ligne_de_base_devenue_inutile_rougit(self):
        self.depot.module("services/pack.py", self.SOURCE)
        lancer(["--write-baseline"])
        self.depot.module("services/pack.py", "x = 1\n")
        code, sortie = lancer()
        self.assertEqual(code, 1)
        self.assertIn("DEVENUE(S) INUTILE(S)", sortie)
        self.assertIn("services/pack.py:2:apps.ged.services", sortie)

    def test_import_deplace_se_reenregistre(self):
        self.depot.module("services/pack.py", self.SOURCE)
        lancer(["--write-baseline"])
        self.depot.module("services/pack.py", "\n\n" + self.SOURCE)
        self.assertEqual(lancer()[0], 1)  # nouveau :4 ET périmé :2
        self.assertEqual(lancer(["--write-baseline"])[0], 0)
        self.assertEqual(lancer()[0], 0)
        self.assertIn("services/pack.py:4:apps.ged.services",
                      self.depot.baseline.read_text(encoding="utf-8"))

    def test_import_nouveau_refuse_par_write_baseline(self):
        self.depot.module("services/pack.py", self.SOURCE)
        lancer(["--write-baseline"])
        self.depot.module("services/pack.py",
                          self.SOURCE + "\ndef g():\n    import apps.ged.services\n")
        code, sortie = lancer(["--write-baseline"])
        self.assertEqual(code, 1)
        self.assertIn("REFUS", sortie)
        self.assertEqual(cfc.charger_base(),
                         ["backend/django_core/apps/calepinage/services/"
                          "pack.py:2:apps.ged.services"])

    def test_croissance_autorisee_par_le_fondateur(self):
        self.depot.module("services/pack.py", self.SOURCE)
        lancer(["--write-baseline"])
        self.depot.module("services/autre.py", "import apps.ao\n")
        self.assertEqual(
            lancer(["--write-baseline", "--autoriser-croissance"])[0], 0)
        self.assertEqual(len(cfc.charger_base()), 2)

    def test_base_retrecit_sans_drapeau(self):
        self.depot.module("services/pack.py", self.SOURCE)
        self.depot.module("services/autre.py", "import apps.ao\n")
        lancer(["--write-baseline"])
        self.depot.module("services/autre.py", "x = 1\n")
        self.assertEqual(lancer(["--write-baseline"])[0], 0)
        self.assertEqual(len(cfc.charger_base()), 1)

    def test_module_introuvable_rougit(self):
        cfc.CALEPINAGE_DIR = self.depot.racine / "absent"
        code, sortie = lancer()
        self.assertEqual(code, 1)
        self.assertIn("a cessé de garder", sortie)


# ===========================================================================
# Le vrai depot
# ===========================================================================

class DepotReelTests(unittest.TestCase):
    def test_le_depot_passe_avec_sa_base(self):
        code, sortie = lancer()
        self.assertEqual(code, 0, sortie)

    def test_la_base_mesuree_ne_porte_que_la_ged(self):
        base = cfc.charger_base()
        self.assertTrue(base, "base vide — la mesure du jour a disparu")
        for cle in base:
            self.assertIn(":apps.ged.", cle)


if __name__ == "__main__":
    unittest.main()
