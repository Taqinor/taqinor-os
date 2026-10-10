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


class GardesTests(unittest.TestCase):
    """AMET86 (C-AMET-029) - la garde C20 tourne dans stage-names sur un clone COMPLET
    (sinon elle echoue fermee) ; check_ao_api_contract (NO-OP, app `ao` parquee) est retiree."""

    def test_forme_code_presente_et_ao_api_contract_absente(self):
        commandes = [c for _n, c, _w in ci_guards.GARDES["stage-names"]]
        self.assertIn("python scripts/check_forme_code.py --base origin/main", commandes)
        self.assertIn("python -m unittest scripts.tests.test_check_forme_code -v", commandes)
        toutes = [c for rows in ci_guards.GARDES.values() for _n, c, _w in rows]
        self.assertFalse([c for c in toutes if "check_ao_api_contract" in c])
        self.assertFalse(os.path.exists(os.path.join(REPO_ROOT, "scripts", "check_ao_api_contract.py")))
        etapes = ci_fast_gate_steps.load_jobs()["stage-names"]["steps"]
        checkout = next(e for e in etapes if str(e.get("uses", "")).startswith("actions/checkout"))
        self.assertEqual((checkout.get("with") or {}).get("fetch-depth"), 0)


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


# ADEP12 - une garde de `backend-lint-fast` ne doit lire AUCUN fichier sous `frontend/` ni
# `apps/web/` : ce job est gate sur `backend == true`, donc une PR frontend seule ne la
# lancerait pas et une regression frontend qu'elle detecte passerait au vert.
_SONDE = r"""
import json, os, runpy, shlex, sys
out, repo, cmd = sys.argv[1], sys.argv[2], sys.argv[3]
vus = set()
def hook(ev, args):
    if ev in ('open', 'os.listdir', 'os.scandir') and args and isinstance(args[0], (str, bytes, os.PathLike)):
        try:
            vus.add(os.path.abspath(os.fsdecode(args[0])))
        except Exception:
            pass
sys.addaudithook(hook)
argv = shlex.split(cmd)[1:]
sys.path.insert(0, os.path.join(repo, 'scripts'))
try:
    if argv[0] == '-m':
        sys.argv = [argv[1]] + argv[2:]
        runpy.run_module(argv[1], run_name='__main__', alter_sys=True)
    else:
        sys.argv = argv
        runpy.run_path(argv[0], run_name='__main__')
except SystemExit:
    pass
except BaseException:
    pass
finally:
    with open(out, 'w', encoding='utf-8') as fh:
        json.dump(sorted(vus), fh)
"""


def _fichiers_ouverts(commande, wd, tmpdir, idx):
    import json
    import subprocess
    sonde = os.path.join(tmpdir, "sonde.py")
    if not os.path.exists(sonde):
        with open(sonde, "w", encoding="utf-8") as fh:
            fh.write(_SONDE)
    sortie = os.path.join(tmpdir, f"vus{idx}.json")
    subprocess.run([sys.executable, sonde, sortie, REPO_ROOT, commande],
                   cwd=os.path.join(REPO_ROOT, wd), capture_output=True, timeout=600)
    with open(sortie, encoding="utf-8") as fh:
        return json.load(fh)


def _sous_surface_frontend(chemin):
    rel = os.path.relpath(chemin, REPO_ROOT).replace(os.sep, "/")
    return rel.startswith("frontend/") or rel.startswith("apps/web/") \
        or rel in ("frontend", "apps/web")


class GardeBackendNeLitPasLeFrontendTests(unittest.TestCase):
    def test_garde_backend_lint_fast_ne_lit_pas_le_frontend(self):
        import tempfile
        from concurrent.futures import ThreadPoolExecutor
        import shlex
        candidates = []
        for nom, commande, wd in ci_guards.GARDES["backend-lint-fast"]:
            mots = shlex.split(commande)
            if mots[0] != "python" or mots[1] in ("-m",) and mots[2] == "compileall":
                continue
            candidates.append((nom, commande, wd))
        self.assertGreaterEqual(len(candidates), 20)
        fautives = []
        with tempfile.TemporaryDirectory() as tmp:
            with ThreadPoolExecutor(max_workers=6) as pool:
                futs = [(nom, commande, pool.submit(_fichiers_ouverts, commande, wd, tmp, i))
                        for i, (nom, commande, wd) in enumerate(candidates)]
                for nom, commande, fut in futs:
                    lus = [c for c in fut.result() if _sous_surface_frontend(c)]
                    if lus:
                        fautives.append(f"{commande} lit {os.path.relpath(lus[0], REPO_ROOT)}")
        self.assertEqual(fautives, [],
                         "gardes de `backend-lint-fast` qui lisent le frontend — a deplacer "
                         "dans GARDES['stage-names'] : " + "; ".join(fautives))


# ADEP21 - test inverse : tout `scripts/tests/test_*.py` et tout `scripts/check_*.py` est
# cite par GARDES (ou une etape des workflows) ou par la liste d'exclusion nommee et datee.
class ToutEstBrancheTests(unittest.TestCase):
    EXCLUSIONS = os.path.join(REPO_ROOT, "scripts", "ci_guards_non_branches.txt")

    @classmethod
    def _textes_cites(cls):
        morceaux = [c for rows in ci_guards.GARDES.values() for _n, c, _w in rows]
        wf = os.path.join(REPO_ROOT, ".github", "workflows")
        for nom in sorted(os.listdir(wf)):
            with open(os.path.join(wf, nom), encoding="utf-8") as fh:
                # lignes de commentaire exclues : une mention n'est pas une execution
                morceaux.extend(ligne for ligne in fh if not ligne.lstrip().startswith("#"))
        return "\n".join(morceaux)

    @classmethod
    def _exclusions(cls):
        sortie = {}
        if not os.path.isfile(cls.EXCLUSIONS):
            return sortie
        with open(cls.EXCLUSIONS, encoding="utf-8") as fh:
            for ligne in fh:
                ligne = ligne.strip()
                if not ligne or ligne.startswith("#"):
                    continue
                champs = [c.strip() for c in ligne.split("|")]
                sortie[champs[0]] = champs
        return sortie

    @classmethod
    def _fichiers(cls):
        sortie = []
        for nom in sorted(os.listdir(os.path.join(REPO_ROOT, "scripts", "tests"))):
            if nom.startswith("test_") and nom.endswith(".py"):
                sortie.append((f"tests/{nom}", nom[:-3]))
        for nom in sorted(os.listdir(os.path.join(REPO_ROOT, "scripts"))):
            if nom.startswith("check_") and nom.endswith(".py"):
                sortie.append((nom, nom))
        return sortie

    def test_tout_test_et_garde_est_branche(self):
        texte = self._textes_cites()
        exclusions = self._exclusions()
        orphelins = [rel for rel, cle in self._fichiers()
                     if cle not in texte and rel not in exclusions]
        self.assertEqual(
            orphelins, [],
            "scripts jamais executes en CI - ajoutez une entree a ci_guards.GARDES, ou une "
            "ligne `fichier | motif | date` a scripts/ci_guards_non_branches.txt : "
            + ", ".join(orphelins))

    def test_exclusions_datees_et_vivantes(self):
        texte = self._textes_cites()
        existants = {rel: cle for rel, cle in self._fichiers()}
        for rel, champs in self._exclusions().items():
            with self.subTest(exclusion=rel):
                self.assertEqual(len(champs), 3, f"{rel} : format `fichier | motif | date`")
                self.assertRegex(champs[2], r"^\d{4}-\d{2}-\d{2}$")
                self.assertIn(rel, existants, f"{rel} n'existe plus - retirez la ligne")
                self.assertNotIn(existants[rel], texte,
                                 f"{rel} est desormais branche - retirez la ligne (cliquet)")


class RegistresDeriveTests(unittest.TestCase):
    """ADEP22 - les deux registres generes sont gardes en `--check` (derive seulement ; les
    violations restent consultatives, YDATA22 / AUD831 inchanges)."""

    def test_registres_derive_branches(self):
        commandes = [c for rows in ci_guards.GARDES.values() for _n, c, _w in rows]
        for script in ("check_db_invariants.py", "check_money_monodevise.py"):
            with self.subTest(script=script):
                self.assertIn(f"python scripts/{script} --check", commandes)


class TypeDeCleTests(unittest.TestCase):
    """AMET100 - toute garde qui lit une baseline / allowlist declare `TYPE_DE_CLE` (lu par
    `audit_tache.py listes-figees`) : `par_symbole` = cle de contenu, `par_ligne` = numero de ligne."""

    _BASELINE = re.compile(r"\w+_(?:allow|allowlist|exceptions|non_branches)\w*\.txt|exceptions_permanentes\.yml|_dette\.yml")
    _TYPE = re.compile(r"(?m)^TYPE_DE_CLE\s*=\s*['\"](par_ligne|par_symbole)['\"]")

    def test_toute_garde_a_baseline_declare_son_type_de_cle(self):
        scripts = os.path.join(REPO_ROOT, "scripts")
        sans_type = []
        lisant = 0
        for nom in sorted(os.listdir(scripts)):
            if not (nom.startswith("check_") and nom.endswith(".py")):
                continue
            with open(os.path.join(scripts, nom), encoding="utf-8") as f:
                source = f.read()
            if self._BASELINE.search(source):
                lisant += 1
                if not self._TYPE.search(source):
                    sans_type.append(nom)
        self.assertGreater(lisant, 40)  # la detection ne s'est pas videe
        self.assertEqual(sans_type, [], "ajoutez `TYPE_DE_CLE = \"par_symbole\"` (ou par_ligne) apres les imports")


if __name__ == "__main__":
    unittest.main()
