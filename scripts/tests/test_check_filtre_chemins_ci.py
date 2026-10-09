"""ADEP13 - tests de scripts/check_filtre_chemins_ci.py."""
import os
import shlex
import sys
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "scripts" / "tests"))

import check_filtre_chemins_ci as cf  # noqa: E402
import ci_guards  # noqa: E402
import test_ci_guards as tcg  # noqa: E402

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

    def test_depot_reel_vert(self):
        self.assertEqual(cf.verifier(ROOT), [])


class GardesGateesTests(unittest.TestCase):
    """Fichiers OUVERTS (sys.addaudithook) par les gardes de `backend-lint-fast`, job gate
    sur `backend == true` : chacun situe dans le depot doit declencher `backend`."""

    def test_fichiers_lus_par_gardes_gatees_declenchent_le_job(self):
        rules = cf.regles(ROOT)
        candidates = []
        for nom, commande, wd in ci_guards.GARDES["backend-lint-fast"]:
            mots = shlex.split(commande)
            if mots[0] != "python" or (mots[1] == "-m" and mots[2] == "compileall"):
                continue
            candidates.append((commande, wd))
        rouges = {}
        with tempfile.TemporaryDirectory() as tmp:
            with ThreadPoolExecutor(max_workers=6) as pool:
                futs = [(c, pool.submit(tcg._fichiers_ouverts, c, wd, tmp, i))
                        for i, (c, wd) in enumerate(candidates)]
                for commande, fut in futs:
                    for chemin in fut.result():
                        rel = os.path.relpath(chemin, ROOT).replace(os.sep, "/")
                        if rel.startswith("..") or rel.startswith(".git/") \
                                or "/__pycache__" in rel or not os.path.isfile(chemin):
                            continue
                        if not cf.filtre._resolve(rules, [rel])["backend"]:
                            rouges.setdefault(rel, commande)
        self.assertEqual(rouges, {}, "fichiers ouverts par une garde de `backend-lint-fast` "
                                     "sans declencher `backend` dans le filtre `changes`")


if __name__ == "__main__":
    unittest.main()
