"""ADEP13 - tests de scripts/check_filtre_chemins_ci.py."""
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "scripts" / "tests"))

import check_filtre_chemins_ci as cf  # noqa: E402 — après sys.path/setup() (D-ENF22)

CI_YML = """jobs:
  changes:
    runs-on: ubuntu-latest
    steps:
      - id: detect
        run: |
%s
  autre:
    runs-on: ubuntu-latest
"""
TEST_JS = ("import { readFileSync } from 'node:fs'\n"
           "const P = readFileSync(join(HERE, '../../../../backend/django_core/apps/crm/platform.py'))\n")


def _arbre(tmp, regle):
    r = Path(tmp)
    (r / ".github/workflows").mkdir(parents=True)
    (r / ".github/workflows/ci.yml").write_text(CI_YML % regle, encoding="utf-8")
    (r / "frontend/src/features/crm").mkdir(parents=True)
    (r / "frontend/src/features/crm/Planner.test.mjs").write_text(TEST_JS, encoding="utf-8")
    (r / "backend/django_core/apps/crm").mkdir(parents=True)
    (r / "backend/django_core/apps/crm/platform.py").write_text("x = 1\n", encoding="utf-8")
    return r


REGLE_BACKEND = """          grep -qE '^backend/' <<< "$changed" && backend=true || true"""
REGLE_COUVRANTE = REGLE_BACKEND + """
          grep -qE '^backend/django_core/apps/crm/platform\\.py$' <<< "$changed" && frontend=true || true"""


class FiltreCheminsTests(unittest.TestCase):
    def test_lecture_backend_non_couverte_rouge(self):
        with tempfile.TemporaryDirectory() as tmp:
            erreurs = cf.verifier(_arbre(tmp, REGLE_BACKEND))
            self.assertEqual(len(erreurs), 1, erreurs)
            self.assertIn("apps/crm/platform.py", erreurs[0])

    def test_lecture_couverte_vert(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(cf.verifier(_arbre(tmp, REGLE_COUVRANTE)), [])

    def test_commentaire_ignore(self):
        with tempfile.TemporaryDirectory() as tmp:
            r = _arbre(tmp, REGLE_BACKEND)
            (r / "frontend/src/features/crm/Planner.test.mjs").write_text(
                "// voir '../../../../backend/django_core/apps/crm/platform.py'\n", encoding="utf-8")
            self.assertEqual(cf.verifier(r), [])

    def test_join_compose_rouge(self):
        with tempfile.TemporaryDirectory() as tmp:
            r = _arbre(tmp, REGLE_BACKEND)
            (r / "backend/django_core/fix").mkdir()
            (r / "backend/django_core/fix/a.json").write_text("{}", encoding="utf-8")
            (r / "frontend/src/features/crm/Planner.test.mjs").write_text(
                "const D = join(HERE, '..', '..', 'backend', 'django_core', 'fix')\n"
                "const P = join(D, 'a.json')\n", encoding="utf-8")
            erreurs = cf.verifier(r)
            self.assertEqual(len(erreurs), 1, erreurs)
            self.assertIn("fix/a.json", erreurs[0])

    def test_module_frontend_scripts_importe_par_un_test_rouge(self):
        with tempfile.TemporaryDirectory() as tmp:
            r = _arbre(tmp, REGLE_BACKEND)
            (r / "backend/django_core/fix").mkdir()
            (r / "backend/django_core/fix/a.json").write_text("{}", encoding="utf-8")
            (r / "frontend/scripts").mkdir()
            (r / "frontend/scripts/mod.mjs").write_text(
                "const D = join(HERE, '..', '..', 'backend', 'django_core', 'fix')\n"
                "export const P = join(D, 'a.json')\n", encoding="utf-8")
            (r / "frontend/src/features/crm/Planner.test.mjs").write_text(
                "import { P } from '../../../scripts/mod.mjs'\n", encoding="utf-8")
            erreurs = cf.verifier(r)
            self.assertEqual(len(erreurs), 1, erreurs)
            self.assertIn("fix/a.json", erreurs[0])

    def test_depot_reel_vert(self):
        self.assertEqual(cf.verifier(ROOT), [])


# CI-5MIN (23/10/2026) — `GardesGateesTests` (fichiers ouverts par les gardes de
# `backend-lint-fast` -> doivent declencher `backend`) vit desormais dans
# scripts/tests/test_ci_guards.py, `GardeBackendNeLitPasLeFrontendTests`, ou il
# partage la trace d'ADEP12 au lieu de rejouer une seconde fois toutes les gardes.


if __name__ == "__main__":
    unittest.main()
