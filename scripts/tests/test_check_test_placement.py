"""Tests de scripts/check_test_placement.py — garde de placement des tests sur le diff (AMET84).

Nouveau fichier car : convention (un module de test par garde, cf. la ligne de tache AMET84).
Depots git JETABLES (memes helpers que test_check_forme_code) : aucun reseau, aucun docker.
    python -m unittest scripts.tests.test_check_test_placement -v
"""
import contextlib
import io
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "scripts" / "tests"))

import check_test_placement as ctp  # noqa: E402
from test_check_forme_code import Depot as DepotForme, PLAN, _git, tache  # noqa: E402

V2 = "scripts/taches_audit_v2.txt"
BASE = {"apps/x/tests/test_existant.py": "X = 1\n", PLAN: tache("ZZ1", "x", coche=False), V2: "ZZV2\n"}


class Depot(DepotForme):
    def juger(self, base=None, racine=None):
        sortie = io.StringIO()
        with contextlib.redirect_stdout(sortie):
            code = ctp.main(["--base", base or self.base, "--racine", str(racine or self.racine)])
        return code, sortie.getvalue()


class PlacementTests(unittest.TestCase):
    def depot(self, fichiers=None) -> Depot:
        depot = Depot(fichiers or BASE)
        self.addCleanup(depot.tmp.cleanup)
        return depot

    def test_fichier_nomme_par_id_de_tache_refuse(self):
        d = self.depot()
        code, sortie = d.scenario({"apps/ventes/tests/test_amet9_solde.py": "X = 1\n"})
        self.assertEqual(code, 1, sortie)
        self.assertIn("apps/ventes/tests/test_amet9_solde.py : le nom porte un id de tâche", sortie)
        # Meme avec « Nouveau fichier car : » cite par une tache cochee : le nom par id reste refuse.
        chemin = "apps/ventes/tests/test_amet9_solde.py"
        code, sortie = d.scenario({chemin: "X = 1\n", PLAN: tache("ZZ1", f"`{chemin}` (Nouveau fichier car : x)")})
        self.assertEqual(code, 1, sortie)
        # Le motif second (JS) est refuse aussi.
        code, sortie = d.scenario({"frontend/src/lib/outbox.amet12.test.mjs": "x\n"})
        self.assertEqual(code, 1, sortie)
        self.assertIn("le nom porte un id de tâche", sortie)

    def test_fichier_neuf_accepte_seulement_avec_nouveau_fichier_car_cite(self):
        d = self.depot()
        chemin = "apps/facturation/tests/test_parcours_pa4.py"
        code, sortie = d.scenario({chemin: "X = 1\n"})
        self.assertEqual(code, 1, sortie)
        self.assertIn("sans « Nouveau fichier car : »", sortie)
        # Tache cochee qui porte la clause mais ne cite PAS ce chemin : refuse.
        code, sortie = d.scenario({chemin: "X = 1\n", PLAN: tache("ZZ1", "Nouveau fichier car : convention")})
        self.assertEqual(code, 1, sortie)
        # Tache NON cochee par la PR : refuse.
        code, sortie = d.scenario({chemin: "X = 1\n", PLAN: tache("ZZ1", f"`{chemin}` nouveau fichier car : c",
                                                                  coche=False)})
        self.assertEqual(code, 1, sortie)
        # Cochee + clause (casse libre) + chemin cite, meme apres un backtick impair : accepte.
        ligne = f"`impair {chemin}` (Nouveau FICHIER car : convention) `{chemin}::T::t`"
        code, sortie = d.scenario({chemin: "X = 1\n", PLAN: tache("ZZ1", ligne)})
        self.assertEqual(code, 0, sortie)
        self.assertIn("OK", sortie)

    def test_nouveau_dossier_car_couvre_les_fichiers_du_dossier_cite(self):
        # AMET90 : « nouveau dossier car : un fichier par groupe » + un chemin du dossier cité
        # admet les autres fichiers de test NEUFS de CE dossier (pas d'un autre).
        d = self.depot()
        neuf = "frontend/e2e/acceptation/adep.spec.js"
        ligne = "`frontend/e2e/acceptation/amet.spec.js` (nouveau dossier car : un fichier par groupe)"
        code, sortie = d.scenario({neuf: "x\n", PLAN: tache("ZZ1", ligne)})
        self.assertEqual(code, 0, sortie)
        code, sortie = d.scenario({"frontend/e2e/autre/x.spec.js": "x\n", PLAN: tache("ZZ1", ligne)})
        self.assertEqual(code, 1, sortie)

    def test_chemin_dicte_par_une_tache_v2_gelee_avertit_sans_echouer(self):
        d = self.depot()
        chemin = "apps/ventes/tests/test_zzv2_solde.py"  # nom par id ET dicte par une v2 gelee
        code, sortie = d.scenario({chemin: "X = 1\n", PLAN: tache("ZZV2", f"Files: `{chemin}`")})
        self.assertEqual(code, 0, sortie)
        self.assertIn(f"AVERTISSEMENT {chemin} : chemin dicté par la tâche v2 gelée ZZV2", sortie)

    def test_test_ajoute_a_un_module_existant_ou_helper_passent(self):
        d = self.depot()
        code, sortie = d.scenario({"apps/x/tests/test_existant.py": "X = 1\nY = 2\n",
                                   "apps/x/tests/helpers.py": "Z = 3\n", "apps/x/tests/__init__.py": ""})
        self.assertEqual(code, 0, sortie)
        self.assertIn("0 fichier(s) de test neuf(s)", sortie)

    def test_renommage_sur_place_n_est_pas_un_fichier_neuf(self):
        d = self.depot()
        _git(d.racine, "checkout", "-q", "-B", "ren", d.base)
        os.makedirs(d.racine / "apps" / "y", exist_ok=True)
        _git(d.racine, "mv", "apps/x/tests/test_existant.py", "apps/y/test_existant.py")
        _git(d.racine, "commit", "-qm", "ren")
        code, sortie = d.juger()
        self.assertEqual(code, 0, sortie)

    def test_clone_superficiel_echoue_ferme(self):
        d = self.depot()
        d.scenario({"apps/x/tests/test_existant.py": "X = 2\n"})
        with mock.patch.dict(os.environ, {"GITHUB_ACTIONS": "true"}):
            code, sortie = d.juger(base="origin/main")
        self.assertEqual(code, 1)
        self.assertIn("clone superficiel : garde inopérante", sortie)
        clone = tempfile.TemporaryDirectory()
        self.addCleanup(clone.cleanup)
        _git(clone.name, "clone", "-q", "--depth", "1", d.racine.as_uri(), "c")
        code, sortie = d.juger(base="origin/main", racine=Path(clone.name) / "c")
        self.assertEqual(code, 1)
        self.assertIn("garde inopérante", sortie)

    def test_reconnaissance_des_noms(self):
        for nom in ("a/test_x.py", "a/x_test.py", "a/tests.py", "a/x.test.mjs", "a/y.spec.js", "a/tests_z.py"):
            self.assertTrue(ctp.est_fichier_test(nom), nom)
        for nom in ("a/conftest.py", "a/__init__.py", "a/helpers.py", "a/test_data.json", "node_modules/x.test.js"):
            self.assertFalse(ctp.est_fichier_test(nom), nom)
        for nom in ("a/test_amet9_x.py", "a/tests_ab12_x.py", "a/x.amet9.test.mjs"):
            self.assertTrue(ctp.NOM_AVEC_ID.search(nom), nom)
        for nom in ("a/test_parcours_pa4.py", "a/test_sonde.py", "a/x.erreurHttp.test.mjs", "a/test_check_x.py"):
            self.assertFalse(ctp.NOM_AVEC_ID.search(nom), nom)


if __name__ == "__main__":
    unittest.main()
