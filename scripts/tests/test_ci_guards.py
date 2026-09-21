"""SOLMVP54 — garde du runner parallele des gardes hote (`scripts/ci_guards.py`).

Le runner a remplace ~85 etapes `run:` de ci.yml (`stage-names` 41, `backend-lint-fast`
44) par UNE etape par job. Ce que cela pourrait casser en silence, et ce que ce test
verrouille :

1. une garde qui pointe sur un script disparu passerait « ECHEC » au premier run — mais
   une garde SUPPRIMEE de la liste cesserait d'etre executee sans aucun rouge. Chaque
   commande doit donc designer un fichier `scripts/*.py` ou un module
   `scripts.tests.*` qui existe (et aucune commande n'est en double) ;
2. ci.yml doit APPELER le runner pour chacun des deux jobs, sinon les gardes ne tournent
   plus nulle part (et aucune etape `check_*.py` ne doit rester en serie a cote : la
   liste vit a UN endroit) ;
3. `scripts/ci_fast_gate_steps.py` (ce que lit `scripts/preflight.ps1`) doit
   DEVELOPPER l'etape runner en une entree par garde — un preflight qui ne verrait
   qu'une ligne « ci_guards.py » aurait perdu le detail, et un preflight qui ne la
   verrait pas du tout ne lancerait plus aucune garde ;
4. la semantique du runner : un echec d'une garde = code 1 et la garde est nommee ;
   toutes vertes = code 0 ; l'ordre d'affichage n'importe pas.
"""
from __future__ import annotations

import io
import os
import re
import sys
import unittest
from contextlib import redirect_stdout

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(REPO_ROOT, "scripts"))

import ci_guards  # noqa: E402
import ci_fast_gate_steps  # noqa: E402

_SCRIPT_RE = re.compile(r"python\s+(?:-\S+\s+)*scripts/([\w_]+\.py)")
_UNITTEST_RE = re.compile(r"python\s+-m\s+unittest\s+scripts\.tests\.([\w_]+)")
_MODULE_RE = re.compile(r"python\s+-m\s+(compileall)\b")
_BINAIRES = ("flake8", "lint-imports")


class ManifesteTests(unittest.TestCase):
    def test_deux_jobs_non_vides(self):
        self.assertEqual(set(ci_guards.GARDES), {"stage-names", "backend-lint-fast"})
        for job, rows in ci_guards.GARDES.items():
            self.assertGreaterEqual(len(rows), 30, f"{job} : liste anormalement courte")

    def test_chaque_commande_designe_un_script_ou_module_existant(self):
        for job, rows in ci_guards.GARDES.items():
            for nom, commande, wd in rows:
                with self.subTest(job=job, garde=nom):
                    self.assertTrue(nom.strip(), "nom vide")
                    self.assertTrue(
                        os.path.isdir(os.path.join(REPO_ROOT, wd)),
                        f"repertoire de travail introuvable : {wd}",
                    )
                    m = _SCRIPT_RE.search(commande)
                    if m:
                        self.assertTrue(
                            os.path.isfile(os.path.join(REPO_ROOT, "scripts", m.group(1))),
                            f"script introuvable : scripts/{m.group(1)}",
                        )
                        continue
                    m = _UNITTEST_RE.search(commande)
                    if m:
                        self.assertTrue(
                            os.path.isfile(os.path.join(REPO_ROOT, "scripts", "tests",
                                                        m.group(1) + ".py")),
                            f"module de test introuvable : scripts/tests/{m.group(1)}.py",
                        )
                        continue
                    if _MODULE_RE.search(commande) or commande.split()[0] in _BINAIRES:
                        continue
                    self.fail(f"commande non reconnue (ni script, ni module, ni binaire "
                              f"connu) : {commande}")

    def test_aucune_commande_en_double(self):
        vues: dict[str, str] = {}
        for job, rows in ci_guards.GARDES.items():
            for nom, commande, wd in rows:
                cle = f"{wd}::{commande}"
                self.assertNotIn(cle, vues, f"commande en double : {commande} "
                                            f"({vues.get(cle)} et {job})")
                vues[cle] = job

    def test_filtre_only(self):
        rows = ci_guards.gardes_de("stage-names", only="codemap_fingerprint")
        self.assertEqual(len(rows), 1)
        with self.assertRaises(SystemExit):
            ci_guards.gardes_de("stage-names", only="garde-qui-n-existe-pas")
        with self.assertRaises(SystemExit):
            ci_guards.gardes_de("job-inconnu")


class CiYmlTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with open(os.path.join(REPO_ROOT, ".github", "workflows", "ci.yml"),
                  encoding="utf-8") as fh:
            cls.jobs = ci_fast_gate_steps.load_jobs()
            cls.texte = fh.read()

    def test_ci_yml_appelle_le_runner_pour_chaque_job(self):
        for job in ci_guards.GARDES:
            runs = [st.get("run") or "" for st in self.jobs[job]["steps"]]
            appels = [r for r in runs if re.search(rf"python scripts/ci_guards\.py {job}\b", r)]
            self.assertEqual(len(appels), 1, f"{job} : le runner doit etre appele UNE fois")
            residus = [r for r in runs if re.search(r"scripts/check_\w+\.py", r)]
            self.assertEqual(residus, [], f"{job} : des gardes restent en etapes serie "
                                          f"dans ci.yml — deplacez-les dans ci_guards.GARDES")

    def test_preflight_developpe_le_runner_en_une_entree_par_garde(self):
        for job, rows in ci_guards.GARDES.items():
            with self.subTest(job=job):
                steps = ci_fast_gate_steps.extract(job, self.jobs)
                commandes = [cmd for _lbl, _wd, cmd in steps]
                self.assertFalse(any("ci_guards.py" in c for c in commandes),
                                 "l'etape runner doit etre remplacee, pas listee")
                for _nom, commande, _wd in rows:
                    self.assertIn(commande, commandes,
                                  f"{job} : la garde « {commande} » n'apparait pas dans "
                                  f"le developpement preflight")
                self.assertGreaterEqual(len(steps), len(rows))


class RunnerTests(unittest.TestCase):
    def _run(self, gardes):
        buf = io.StringIO()
        with redirect_stdout(buf):
            echecs = ci_guards.run_guards(gardes, jobs=2, repo_root=REPO_ROOT, gh=False)
        return echecs, buf.getvalue()

    def test_toutes_vertes_rend_zero_echec(self):
        py = sys.executable
        gardes = [
            ("une", f'"{py}" -c "print(\'un\')"', "."),
            ("deux", f'"{py}" -c "print(\'deux\')"', "scripts"),
        ]
        echecs, sortie = self._run(gardes)
        self.assertEqual(echecs, [])
        self.assertIn("OK", sortie)
        self.assertIn("un", sortie)
        self.assertIn("(cd scripts)", sortie)

    def test_une_rouge_est_nommee_et_rend_un_echec(self):
        py = sys.executable
        gardes = [
            ("verte", f'"{py}" -c "print(\'ok\')"', "."),
            ("rouge", f'"{py}" -c "import sys; print(\'boum\'); sys.exit(3)"', "."),
        ]
        echecs, sortie = self._run(gardes)
        self.assertEqual([r["nom"] for r in echecs], ["rouge"])
        self.assertEqual(echecs[0]["code"], 3)
        self.assertIn("1 garde(s) en ECHEC", sortie)
        self.assertIn("boum", sortie)

    def test_commande_introuvable_est_un_echec(self):
        echecs, _ = self._run([("fantome", "commande-qui-n-existe-pas-42 --x", ".")])
        self.assertEqual(len(echecs), 1)
        self.assertNotEqual(echecs[0]["code"], 0)


if __name__ == "__main__":
    unittest.main()
