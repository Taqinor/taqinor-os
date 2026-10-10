"""Tests de scripts/check_forme_code.py — garde C20 sur le diff (AMET85).

Depots git JETABLES (un commit de base, une branche par scenario) : aucune
baseline, aucun reseau, aucun docker. Lancer :
    python -m unittest scripts.tests.test_check_forme_code -v
"""
import contextlib
import io
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import check_forme_code as cfc  # noqa: E402

SERVICES = "backend/django_core/apps/crm/services.py"
PLAN = "docs/plans/PLAN_ZZ.md"
PR_888 = "b9972acda"


def _git(racine, *args) -> str:
    return subprocess.run(["git", "-c", "user.email=t@t", "-c", "user.name=t", "-c", "core.autocrlf=false", *args],
                          cwd=racine, capture_output=True, text=True, check=True).stdout.strip()


def mur(extra: int = 0) -> str:
    return "".join(f"x_{i} = {i}\n" for i in range(2001 + extra))


def fonction(nom: str, n: int) -> str:
    """Fonction de `n` lignes logiques (def + n-2 affectations + return)."""
    return f"def {nom}():\n" + "".join(f"    v{i} = {i}\n" for i in range(n - 2)) + "    return 0\n"


def tache(ident: str, texte: str, coche: bool = True) -> str:
    return f"- [{'x' if coche else ' '}] {ident} — **t** : {texte}\n"


class Depot:
    def __init__(self, fichiers: dict):
        self.tmp = tempfile.TemporaryDirectory()
        self.racine = Path(self.tmp.name)
        _git(self.racine, "init", "-q", "-b", "main")
        self.base = self.commit(fichiers, "base")

    def commit(self, fichiers: dict, message: str = "pr") -> str:
        for rel, contenu in fichiers.items():
            chemin = self.racine / rel
            if contenu is None:
                chemin.unlink()
                continue
            chemin.parent.mkdir(parents=True, exist_ok=True)
            chemin.write_text(contenu, encoding="utf-8", newline="\n")
        _git(self.racine, "add", "-A")
        _git(self.racine, "commit", "-qm", message, "--allow-empty")
        return _git(self.racine, "rev-parse", "HEAD")

    def scenario(self, fichiers: dict) -> tuple:
        _git(self.racine, "checkout", "-q", "-B", f"s{len(fichiers)}{id(fichiers)}", self.base)
        self.commit(fichiers)
        return self.juger()

    def juger(self, base: str | None = None, racine=None) -> tuple:
        sortie = io.StringIO()
        with contextlib.redirect_stdout(sortie):
            code = cfc.main(["--base", base or self.base, "--racine", str(racine or self.racine)])
        return code, sortie.getvalue()


class FormeCodeTests(unittest.TestCase):
    def depot(self, fichiers: dict) -> Depot:
        depot = Depot(fichiers)
        self.addCleanup(depot.tmp.cleanup)
        return depot

    def test_mur_sans_budget_echoue_et_budget_sur_chemin_exact_passe(self):
        d = self.depot({SERVICES: mur(), PLAN: tache("ZZ1", "x", coche=False)})
        code, sortie = d.scenario({SERVICES: mur(40)})
        self.assertEqual(code, 1, sortie)
        self.assertIn(f"[FICHIER_MUR] {SERVICES} : fichier de 2041 lignes : +40 lignes logiques nettes > budget 0",
                      sortie)
        # Mutant « budget lu sur `services.py` nu » : le budget FUIRAIT vers tout services.py.
        code, sortie = d.scenario({SERVICES: mur(40), PLAN: tache("ZZ1", "`services.py` lignes nettes attendues ≤ 50")})
        self.assertEqual(code, 1, sortie)
        self.assertIn("budget 0 (aucune tâche cochée par la PR ne cite ce chemin exact)", sortie)
        code, sortie = d.scenario({SERVICES: mur(40), PLAN: tache("ZZ1", "`apps/crm/services.py` "
                                                                         "lignes nettes attendues ≤ 50")})
        self.assertEqual(code, 0, sortie)
        code, sortie = d.scenario({SERVICES: mur(40), PLAN: tache("ZZ1", f"`{SERVICES}` lignes nettes attendues ≤ 30")})
        self.assertEqual(code, 1, sortie)
        self.assertIn("+40 lignes logiques nettes > budget 30 (ZZ1 ≤ 30)", sortie)
        # Budget porte par une tache NON cochee par la PR : sans effet.
        code, sortie = d.scenario({SERVICES: mur(40), PLAN: tache("ZZ2", f"`{SERVICES}` lignes nettes attendues ≤ 99",
                                                                  coche=False)})
        self.assertEqual(code, 1, sortie)

    def test_fonctions_neuve_et_mur_jugees_en_lignes_logiques(self):
        d = self.depot({"scripts/a.py": fonction("vieille", 101)})
        code, sortie = d.scenario({"scripts/a.py": fonction("vieille", 101) + fonction("neuve", 61)
                                   + fonction("courte", 60)})
        self.assertIn("[FONCTION_NEUVE] scripts/a.py::neuve : fonction neuve de 61 lignes logiques", sortie)
        self.assertNotIn("::courte", sortie)
        code, sortie = d.scenario({"scripts/a.py": fonction("vieille", 102)})
        self.assertIn("[FONCTION_MUR] scripts/a.py::vieille : fonction de 102 lignes logiques (> 100) : +1", sortie)
        # +1 ligne brute, -2 lignes logiques (trois affectations fusionnees) : rien.
        reformatee = fonction("vieille", 101).replace(
            "    v0 = 0\n    v1 = 1\n    v2 = 2\n", "    v0, v1, v2 = (\n        0, 1,\n        2,\n    )\n")
        code, sortie = d.scenario({"scripts/a.py": reformatee})
        self.assertEqual(code, 0, sortie)

    def test_facade_jugee_sur_les_noms_neufs(self):
        d = self.depot({"backend/app/a.py": "from .b import f  # noqa: F401\n",
                        "backend/app/b.py": "def f():\n    return 1\n\n\ndef g():\n    return 2\n",
                        "backend/app/signals.py": "X = 1\n", "backend/app/tests/test_a.py": "X = 1\n"})
        code, sortie = d.scenario({
            "backend/app/a.py": ("from .c import f  # noqa: F401\nfrom .b import g  # noqa: F401\n"
                                 "from . import signals  # noqa: F401\nh = g\n"
                                 "from django.db.models import QuerySet  # noqa: F401\n"),
            "backend/app/tests/test_a.py": "from ..b import g  # noqa: F401\n"})
        self.assertEqual(code, 1, sortie)
        self.assertIn("[FACADE] backend/app/a.py::g", sortie)
        self.assertIn("[FACADE] backend/app/a.py::h : nouvelle façade (alias de g", sortie)
        for absent in ("a.py::f ", "::signals", "test_a.py", "::QuerySet"):
            self.assertNotIn(absent, sortie)

    def test_reglage_neuf_declare_dans_settings_et_env_example(self):
        vue = "backend/django_core/apps/x/vue.py"
        d = self.depot({"backend/django_core/erp_agentique/settings/base.py": (
            "import os\nA_DECLARE = os.environ.get('A_DECLARE')\nB_ENV = os.environ.get('B_ENV', '')\n"),
            ".env.example": "A_DECLARE=1\n", vue: "from django.conf import settings\n\n\ndef v():\n    return 1\n"})
        code, sortie = d.scenario({vue: ("from django.conf import settings\n\n\ndef v():\n    return (settings.A_DECLARE, "
                                         "settings.B_ENV, getattr(settings, 'C_ABSENT', None))\n")})
        self.assertEqual(code, 1, sortie)
        self.assertIn(f"[REGLAGE] {vue}::B_ENV : réglage B_ENV lu par ce fichier lu depuis l'environnement (B_ENV) "
                      "mais absent de .env.example", sortie)
        self.assertIn(f"[REGLAGE] {vue}::C_ABSENT", sortie)
        self.assertNotIn("A_DECLARE :", sortie)

    def test_garde_neuve_admise_seulement_si_citee_par_une_tache_cochee(self):
        d = self.depot({PLAN: tache("ZZ3", "x", coche=False)})
        code, sortie = d.scenario({"scripts/check_neuf.py": "X = 1\n", "scripts/check_admis.py": "X = 1\n",
                                   PLAN: tache("ZZ3", "Files: `scripts/check_admis.py`")})
        self.assertEqual(code, 1, sortie)
        self.assertIn("[GARDE_NEUVE] scripts/check_neuf.py", sortie)
        self.assertNotIn("check_admis.py :", sortie)

    def test_baseline_qui_grossit_et_exception_par_ligne_de_tache(self):
        dette = "docs/audits/acceptation/ZZ/_dette.yml"
        d = self.depot({"scripts/x_allow.txt": "a\n# c\n", PLAN: tache("ZZ4", "x", coche=False)})
        code, sortie = d.scenario({"scripts/x_allow.txt": "a\n# c\n# commentaire\nb\n", dette: "- ZZ1\n"})
        self.assertIn("[BASELINE_GROSSIT] scripts/x_allow.txt : +1 entrée(s) gelée(s) (b)", sortie)
        self.assertIn(f"[BASELINE_GROSSIT] {dette} : +1", sortie)
        exceptions = ("Exception C20 : BASELINE_GROSSIT docs/audits/acceptation/ car : amorçage ; "
                      "Exception C20 : FICHIER_MUR scripts/y.py car : inutile")
        code, sortie = d.scenario({"scripts/x_allow.txt": "a\nb\n", dette: "- ZZ1\n", PLAN: tache("ZZ4", exceptions)
                                   + tache("ZZ5", "Exception C20 : BASELINE_GROSSIT scripts/x_allow.txt car : x",
                                           coche=False)})
        self.assertEqual(code, 1, sortie)
        self.assertIn(f"exception C20 de ZZ4 : 1 constat(s) exempté(s) — BASELINE_GROSSIT {dette}", sortie)
        self.assertIn("exception C20 sans effet : ZZ4 : FICHIER_MUR scripts/y.py", sortie)
        self.assertIn("[BASELINE_GROSSIT] scripts/x_allow.txt", sortie)

    def test_cle_ligne_refusee_sur_baseline_neuve_par_numero_de_ligne(self):
        """AMET100 : une entree ajoutee dont la cle porte `:123` / `#L123` est refusee ; `::symbole` et `#2` passent."""
        d = self.depot({"scripts/x_allow.txt": "a::f\n"})
        code, sortie = d.scenario({"scripts/x_allow.txt": (
            "a::f\nb/c.py:123  # motif\nd.py::g#2  # occurrence\ne.py::h\nf.jsx#L45\n")})
        self.assertEqual(code, 1, sortie)
        self.assertIn("[CLE_LIGNE] scripts/x_allow.txt : +2 clé(s) par numéro de ligne (b/c.py:123 ; f.jsx#L45)", sortie)
        self.assertNotIn("d.py::g#2  #", sortie.split("CLE_LIGNE")[1])
        code, sortie = d.scenario({"scripts/x_allow.txt": "a::f\nd.py::g#2  # occurrence\n"})
        self.assertNotIn("CLE_LIGNE", sortie)

    def test_deplacement_spl_exempte_par_empreinte(self):
        mur_py = "backend/app/w.py"

        def grosse(module):  # le deplacement re-cible son import local : toujours un deplacement
            return fonction("grosse", 70).replace("():\n", f"():\n    from .{module} import y  # noqa: F401\n", 1)
        d = self.depot({mur_py: grosse("ancien") + mur()})
        code, sortie = d.scenario({mur_py: "from .n import grosse  # noqa: F401\n" + mur(),
                                   "backend/app/n.py": '"""module extrait."""\n\n\n' + grosse("nouveau")})
        self.assertEqual(code, 0, sortie)
        self.assertIn("1 symbole(s) déplacé(s)", sortie)

    def test_clone_superficiel_ou_base_absente_echoue_ferme(self):
        d = self.depot({"a.py": "X = 1\n"})
        d.commit({"a.py": "X = 2\n"})
        with mock.patch.dict(os.environ, {"GITHUB_ACTIONS": "true"}):
            code, sortie = d.juger(base="origin/main")
        self.assertEqual(code, 1)
        self.assertIn("clone superficiel : garde inopérante", sortie)
        clone = tempfile.TemporaryDirectory()
        self.addCleanup(clone.cleanup)
        _git(clone.name, "clone", "-q", "--depth", "1", d.racine.as_uri(), "c")
        code, sortie = d.juger(base="origin/main", racine=Path(clone.name) / "c")
        self.assertEqual(code, 1)
        self.assertIn("clone superficiel : garde inopérante (dépôt shallow", sortie)

    def test_pr_de_revert_non_jugee_et_pr_mixte_jugee(self):
        """Revue du lot audit_deploy : `main` reste revertable — re-ajouter une garde supprimee par un
        `git revert` n'est pas une GARDE_NEUVE ; un commit non-revert dans la PR la fait juger."""
        d = self.depot({"scripts/check_vieux.py": "X = 1\n"})
        base = d.commit({"scripts/check_vieux.py": None}, "supprime la garde")
        _git(d.racine, "revert", "--no-edit", base)
        code, sortie = d.juger(base=base)
        self.assertEqual(code, 0, sortie)
        self.assertIn("PR de revert : forme du code non jugée (main toujours revertable)", sortie)
        d.commit({"scripts/a.py": "X = 1\n"}, "ajout ordinaire")
        code, sortie = d.juger(base=base)
        self.assertEqual(code, 1, sortie)
        self.assertIn("[GARDE_NEUVE] scripts/check_vieux.py", sortie)

    def test_fetch_de_secours_jamais_superficiel(self):
        """Un fetch `--depth=1` rendrait le clone CI shallow : check_forme_code echouerait ferme."""
        import check_acceptation as cacc
        import check_ancres_taches as cat
        appels = []

        def faux_git(*args, **_):
            appels.append(args)
            return None
        with mock.patch.dict(os.environ, {"GITHUB_ACTIONS": "true"}), \
                mock.patch.object(cacc, "_git", faux_git), mock.patch.object(cat, "_git", faux_git):
            self.assertFalse(cacc.base_disponible("origin/main"))
            self.assertFalse(cat.base_disponible("origin/main", ROOT))
        fetchs = [a for a in appels if "fetch" in a]
        self.assertEqual(len(fetchs), 2, appels)
        self.assertFalse([a for a in fetchs if any(str(x).startswith("--depth") for x in a)], fetchs)

    @unittest.skipUnless(subprocess.run(["git", "cat-file", "-e", PR_888 + "^{commit}"], cwd=ROOT).returncode == 0,
                         "PR #888 absente du dépôt local")
    def test_pr_888_rejouee_ne_leve_rien(self):
        r = cfc.analyser(ROOT, PR_888 + "^1", PR_888)
        self.assertEqual(r["constats"], [])
        self.assertIn("ASAV18", [i for i, _ in r["taches"]])


class RejeuTests(unittest.TestCase):
    """AMET87 : le rejeu suit `--first-parent` — un squash (un seul parent) est une PR comme un merge."""

    def test_first_parent_inclut_les_squash(self):
        from forme_code import rejouer_prs
        d = Depot({"a.py": "X = 1\n"})
        self.addCleanup(d.tmp.cleanup)
        _git(d.racine, "checkout", "-q", "-b", "pr")
        d.commit({"b.py": "Y = 1\n"}, "interne de la PR")
        _git(d.racine, "checkout", "-q", "main")
        _git(d.racine, "-c", "user.email=t@t", "merge", "-q", "--no-ff", "pr", "-m", "Merge pull request #1")
        squash = d.commit({"c.py": fonction("neuve", 61)}, "PR squashée (#2)")
        commits = rejouer_prs.commits_fusionnes(d.racine, "main", 10)
        self.assertEqual([s for _, _, s in commits], ["PR squashée (#2)", "Merge pull request #1"])
        res = rejouer_prs.rejouer(d.racine, "main", 10, journal=io.StringIO())
        self.assertEqual(res["plantages"], [])
        self.assertEqual([t for _, t in res["par_classe"]["FONCTION_NEUVE"]],
                         ["c.py::neuve : fonction neuve de 61 lignes logiques (> 60)"])
        self.assertTrue(squash.startswith(res["par_classe"]["FONCTION_NEUVE"][0][0][:9]))
        self.assertIn("| FONCTION_NEUVE | 1 | à remplir |", rejouer_prs.rapport(res, 11))


if __name__ == "__main__":
    unittest.main()
