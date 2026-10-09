"""ADEP26 — les six gardes à allowlist `fichier::symbole` refusent une ligne
dont le fichier n'existe plus ; `check_modules` refuse un alias mort.

    python -m unittest scripts.tests.test_allowlists_orphelines -v
"""
import importlib
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

GARDES = [
    "check_action_permission_override",
    "check_beat_active_companies",
    "check_fk_scoping",
    "check_money_rounding",
    "check_read_modify_write",
    "check_tenant_isolation",
]
MORTE = "backend/django_core/apps/app_disparue/views.py::JouetViewSet"


class OrphelinesTests(unittest.TestCase):
    def test_ligne_morte_detectee_par_chaque_garde(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            vivant = root / "backend" / "django_core" / "apps" / "x"
            vivant.mkdir(parents=True)
            (vivant / "views.py").write_text("", encoding="utf-8")
            for nom in GARDES:
                mod = importlib.import_module(nom)
                morts = mod.fichiers_morts(
                    [MORTE, "backend/django_core/apps/x/views.py::Ok | raison"],
                    root=root)
                self.assertEqual(morts, [MORTE], nom)

    def test_ligne_a_raison_et_separateur_money(self):
        mod = importlib.import_module("check_money_rounding")
        self.assertEqual(
            mod.fichiers_morts([MORTE + "::abc | raison"]), [MORTE + "::abc | raison"])

    def test_depot_reel_vert(self):
        for nom in GARDES:
            mod = importlib.import_module(nom)
            if nom == "check_money_rounding":
                cles = mod.load_allowlist()
            else:
                cles = mod._load_allowlist()
            self.assertEqual(mod.fichiers_morts(cles), [], nom)

    def test_alias_mort_refuse_par_check_modules(self):
        mod = importlib.import_module("check_modules")
        mod.FRONTEND_KEY_ALIASES["alias_jouet_mort"] = "stock"
        try:
            self.assertEqual(mod.main(), 1)
        finally:
            del mod.FRONTEND_KEY_ALIASES["alias_jouet_mort"]
        self.assertEqual(mod.main(), 0)


if __name__ == "__main__":
    unittest.main()
