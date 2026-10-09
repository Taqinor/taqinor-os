#!/usr/bin/env python3
"""AUD826 — le filtre de chemins `changes` de ci.yml doit couvrir `scripts/`.

POURQUOI CETTE GARDE EXISTE. Le job `changes` de `.github/workflows/ci.yml`
resout quelles surfaces une PR a touchees, et les jobs lourds sont gates
dessus. 27 des 32 gardes de `backend-lint-fast` + 2 de `backend-openapi` sont
conditionnees a `backend == true` et lisent leur BASELINE dans `scripts/`
(`on_delete_allowlist.txt`, `tenant_view_allowlist.txt`,
`read_modify_write_allow.txt`, ...). Tant que le filtre ne connaissait que
`STAGES.py`, `backend/`, `frontend/` et `apps/web/`, un commit d'hygiene qui
ne touchait QUE `scripts/*.txt` — typiquement « allowlists rebasees », qui
ELARGIT une exemption — rendait `backend=false` : la garde modifiee ne
tournait pas, les six checks requis etaient satisfaits (un `skipped` ne fait
pas rougir un agregateur), et la PR fusionnait sans que la garde ne se soit
jamais validee elle-meme.

CE QUE LE TEST FAIT. Il n'execute pas bash (le job tourne sous Linux, la
garde doit tourner partout) : il LIT le script shell du job `changes` dans
ci.yml, en extrait les regles `grep -qE '<regex>' <<< "$changed" && <affect>`
telles qu'elles sont ecrites, puis rejoue la resolution en Python sur des
listes de fichiers modifies. La source de verite reste ci.yml — le test ne
porte aucune copie de la liste des regles.

Stdlib pure (le job `stage-names` n'installe aucune dependance : pas de
PyYAML disponible, et de toute facon le contenu a lire est un script shell
imbrique, pas de la donnee YAML).
"""
from __future__ import annotations

import re
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
WORKFLOW = REPO_ROOT / ".github" / "workflows" / "ci.yml"

# `grep -qE '<regex>' <<< "$changed" && <affectations> || true`
_RULE_RE = re.compile(
    r"""^\s*grep\s+-qE\s+'(?P<regex>[^']+)'\s*<<<\s*"\$changed"\s*&&\s*(?P<assign>.+?)\s*(?:\|\|\s*true)?\s*$"""
)
_ASSIGN_RE = re.compile(r"\b(backend|frontend|web|yanbow)\s*=\s*true\b")


def _detect_step_script() -> str:
    """Return the shell script of the `changes` job's `detect` step, verbatim."""
    text = WORKFLOW.read_text(encoding="utf-8")
    # The `changes` job is a top-level job (2-space indent); take everything up
    # to the next top-level job header.
    m = re.search(r"^  changes:\n(?P<body>.*?)(?=^  [A-Za-z0-9_-]+:\n)", text, re.S | re.M)
    if not m:
        raise AssertionError(
            "ci.yml : job `changes` introuvable — le filtre de chemins a ete "
            "renomme ou supprime. Cette garde doit suivre, pas se taire."
        )
    body = m.group("body")
    m2 = re.search(r"^        run: \|\n(?P<script>(?:^ {10}.*\n|^\s*\n)+)", body, re.S | re.M)
    if not m2:
        raise AssertionError(
            "ci.yml : etape `detect` du job `changes` sans bloc `run: |` "
            "reconnaissable — la lecture est cassee, on refuse plutot que de "
            "rendre un test faussement vert."
        )
    return m2.group("script")


def _parse_rules(script: str):
    """[(regex, {surfaces mises a true})] dans l'ordre d'apparition de ci.yml."""
    rules = []
    for line in script.splitlines():
        m = _RULE_RE.match(line)
        if not m:
            continue
        surfaces = set(_ASSIGN_RE.findall(m.group("assign")))
        if surfaces:
            rules.append((m.group("regex"), surfaces))
    return rules


def _resolve(rules, changed_files):
    """Rejoue la resolution du job sur une liste de chemins modifies."""
    out = {"backend": False, "frontend": False, "web": False, "yanbow": False}
    for regex, surfaces in rules:
        rx = re.compile(regex)
        if any(rx.search(path) for path in changed_files):
            for surface in surfaces:
                out[surface] = True
    out["code"] = out["backend"] or out["frontend"]
    return out


class CiChangesFilterTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rules = _parse_rules(_detect_step_script())

    def test_rules_are_readable(self):
        """Une lecture qui ne rend AUCUNE regle serait un faux vert."""
        self.assertGreaterEqual(
            len(self.rules),
            4,
            "ci.yml : moins de 4 regles `grep -qE ... && <surface>=true` "
            "extraites du job `changes` — la lecture est cassee.",
        )

    def test_scripts_only_diff_runs_the_backend_gates(self):
        """AUD826 — un diff limite a scripts/ doit declencher les gardes backend.

        Les gardes de `backend-lint-fast` lisent leurs baselines dans
        `scripts/` : un commit qui ELARGIT une allowlist doit faire tourner la
        garde qu'il vient de modifier.
        """
        for path in (
            "scripts/on_delete_allowlist.txt",
            "scripts/tenant_view_allowlist.txt",
            "scripts/read_modify_write_allow.txt",
            "scripts/check_tenant_isolation.py",
        ):
            with self.subTest(path=path):
                self.assertTrue(
                    _resolve(self.rules, [path])["backend"],
                    f"ci.yml : un diff limite a {path} rend backend=false — "
                    "les gardes de backend-lint-fast qui lisent cette baseline "
                    "ne tourneraient pas, et la PR fusionnerait sans que la "
                    "garde modifiee se soit validee elle-meme (AUD826). "
                    "Ajoutez une regle `^scripts/` au job `changes`.",
                )

    def test_known_surfaces_still_resolve(self):
        """Les quatre surfaces historiques ne doivent pas avoir regresse."""
        cases = [
            ("STAGES.py", ("backend", "frontend")),
            ("backend/django_core/apps/crm/models.py", ("backend",)),
            ("frontend/src/main.jsx", ("frontend",)),
            ("apps/web/src/pages/index.astro", ("web",)),
        ]
        for path, expected in cases:
            with self.subTest(path=path):
                resolved = _resolve(self.rules, [path])
                for surface in expected:
                    self.assertTrue(
                        resolved[surface],
                        f"ci.yml : {path} ne met plus {surface}=true.",
                    )

    def test_yanbow_only_diff_runs_the_site_job(self):
        """YBW1 — un diff limite a apps/yanbow-web doit poser yanbow=true.

        Sans cette regle, un diff YanBow seul passait TOUS les controles requis
        sans rien construire (le motif `^apps/web/` ne couvre pas
        `apps/yanbow-web/`). Il ne doit PAS non plus reconstruire le site
        TAQINOR ni lancer les jobs ERP.
        """
        resolved = _resolve(self.rules, ["apps/yanbow-web/src/pages/_bonjour.astro"])
        self.assertTrue(
            resolved["yanbow"],
            "ci.yml : un diff limite a apps/yanbow-web rend yanbow=false — le "
            "job requis web-build-test ne construirait pas le site YanBow (YBW1).",
        )
        self.assertFalse(
            resolved["web"] or resolved["backend"] or resolved["frontend"],
            "ci.yml : un diff apps/yanbow-web declenche aussi apps/web ou l'ERP.",
        )
        self.assertFalse(
            _resolve(self.rules, ["apps/web/src/pages/index.astro"])["yanbow"],
            "ci.yml : un diff apps/web pose yanbow=true (regle trop large).",
        )

    def test_docs_only_diff_stays_cheap(self):
        """Cas negatif : docs/**.md ne doit declencher aucun job lourd.

        Sans ce cas, une regle trop large (`.` ou `^`) satisferait le test
        precedent tout en supprimant l'economie des merges docs-only (~2 min).
        """
        resolved = _resolve(self.rules, ["docs/PLAN.md", "README.md", ".gitignore"])
        self.assertFalse(
            resolved["backend"] or resolved["frontend"] or resolved["web"]
            or resolved["yanbow"],
            "ci.yml : un diff docs-only declenche un job lourd — la regle "
            "ajoutee pour scripts/ est trop large.",
        )


# ---------------------------------------------------------------------------
# ADEP10 — les cinq checks requis alimentes par `changes` doivent ROUGIR quand
# `changes` n'est pas `success` (checkout transitoire, timeout 5 min), tandis qu'un
# saut par filtre de chemins reste vert. Emulation minimale de la semantique des `if`.
# ---------------------------------------------------------------------------
import yaml  # noqa: E402

REQUIS_ALIMENTES_PAR_CHANGES = ("backend-lint", "backend-tests", "frontend-lint", "e2e",
                                "web-build-test")
_ALL_JOBS = ("changes", "ci-image-check", "backend-lint-fast", "backend-openapi",
             "backend-tests-shard", "frontend-static", "frontend-vitest-shard",
             "e2e-shard", "web-build-test")


def _expr(cond, results, outputs):
    """Evalue une condition `${{ ... }}` (sous-ensemble : always(), success(), needs.X.result,
    needs.X.outputs.Y, hashFiles(), ==, !=, &&, ||, ()). Rend un booleen."""
    if cond is None:
        return None
    if isinstance(cond, bool):
        return cond
    texte = str(cond).strip()
    m = re.fullmatch(r"\$\{\{(.*)\}\}", texte, re.S)
    texte = (m.group(1) if m else texte).strip()
    texte = re.sub(r"hashFiles\([^)]*\)", "'h'", texte)
    texte = re.sub(r"\b(always|success)\(\)", "True", texte)
    texte = re.sub(r"needs\.([\w-]+)\.result", lambda g: f"R[{g.group(1)!r}]", texte)
    texte = re.sub(r"needs\.([\w-]+)\.outputs\.(\w+)",
                   lambda g: f"O[{g.group(1)!r}].get({g.group(2)!r}, '')", texte)
    texte = texte.replace("&&", " and ").replace("||", " or ")
    if re.search(r"contains\(|github\.|failure\(\)|cancelled\(\)", texte):
        raise AssertionError(f"condition hors du sous-ensemble emule : {cond}")
    return bool(eval(texte, {"__builtins__": {}}, {"R": results, "O": outputs}))  # noqa: S307


def _verdict(jobs, nom, results, outputs):
    """'failure' | 'success' | 'skipped' pour l'agregateur `nom` dans le scenario."""
    job = jobs[nom]
    needs = job.get("needs", [])
    needs = [needs] if isinstance(needs, str) else needs
    cond = _expr(job.get("if"), results, outputs)
    if cond is None:
        cond = all(results.get(n) == "success" for n in needs)
    if not cond:
        return "skipped"
    for step in job["steps"]:
        marche = _expr(step.get("if"), results, outputs)
        if marche is None or marche:
            if "exit 1" in (step.get("run") or ""):
                return "failure"
    return "success"


class AgregateursChangesTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.jobs = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))["jobs"]

    def _scenario(self, changes, outputs):
        results = {j: "skipped" for j in _ALL_JOBS}
        results["changes"] = changes
        results["ci-image-check"] = "success"
        out = {"changes": outputs}
        return results, out

    def test_changes_echec_rougit_les_requis(self):
        results, out = self._scenario("failure", {})
        for nom in REQUIS_ALIMENTES_PAR_CHANGES:
            with self.subTest(requis=nom):
                self.assertEqual(
                    _verdict(self.jobs, nom, results, out), "failure",
                    f"ci.yml : `{nom}` reste vert quand `changes` echoue — un check REQUIS "
                    f"ne doit jamais passer sans que le filtre ait resolu.")

    def test_filtre_saute_reste_vert(self):
        tout_faux = {"backend": "false", "frontend": "false", "web": "false",
                     "yanbow": "false", "code": "false"}
        results, out = self._scenario("success", tout_faux)
        for nom in REQUIS_ALIMENTES_PAR_CHANGES:
            with self.subTest(requis=nom):
                self.assertIn(_verdict(self.jobs, nom, results, out), ("success", "skipped"))


class CouplagesInterSurfacesTest(unittest.TestCase):
    """ADEP11 - couplages inter-surfaces prouves : un test/une garde d'une surface lit un
    fichier d'une autre ; l'edition seule de ce fichier doit declencher la surface qui lit."""

    @classmethod
    def setUpClass(cls):
        cls.rules = _parse_rules(_detect_step_script())

    def test_apps_web_src_declenche_frontend(self):
        r = _resolve(self.rules, ["apps/web/src/lib/roofPro2.ts"])
        self.assertTrue(r["frontend"] and r["code"] and r["web"], r)

    def test_apps_web_worker_declenche_frontend(self):
        r = _resolve(self.rules, ["apps/web/worker/index.ts"])
        self.assertTrue(r["frontend"] and r["web"], r)

    def test_apps_web_public_reste_web_seul(self):
        r = _resolve(self.rules, ["apps/web/public/robots.txt"])
        self.assertTrue(r["web"])
        self.assertFalse(r["frontend"] or r["code"], r)

    def test_nginx_declenche_frontend(self):
        r = _resolve(self.rules, ["backend/nginx/security-headers.conf.template"])
        self.assertTrue(r["frontend"] and r["code"], r)

    def test_contract_samples_declenche_frontend(self):
        r = _resolve(self.rules, ["backend/django_core/apps/crm/contract_samples/x.json"])
        self.assertTrue(r["frontend"] and r["backend"], r)

    def test_baseline_docs_declenche_backend(self):
        for doc in ("on-delete-financial-audit.md", "openapi-schema.yml",
                    "money-fields-audit.md", "currency-audit.md"):
            with self.subTest(doc=doc):
                r = _resolve(self.rules, ["docs/" + doc])
                self.assertTrue(r["backend"] and r["code"], r)
                self.assertFalse(r["frontend"], r)

    def test_docs_ordinaire_reste_leger(self):
        r = _resolve(self.rules, ["docs/README.md", "docs/plans/PLAN_AUDIT_DEPLOY.md"])
        self.assertFalse(any(r.values()), r)


if __name__ == "__main__":
    unittest.main()
