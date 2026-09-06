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
_ASSIGN_RE = re.compile(r"\b(backend|frontend|web)\s*=\s*true\b")


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
    out = {"backend": False, "frontend": False, "web": False}
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

    def test_docs_only_diff_stays_cheap(self):
        """Cas negatif : docs/**.md ne doit declencher aucun job lourd.

        Sans ce cas, une regle trop large (`.` ou `^`) satisferait le test
        precedent tout en supprimant l'economie des merges docs-only (~2 min).
        """
        resolved = _resolve(self.rules, ["docs/PLAN.md", "README.md", ".gitignore"])
        self.assertFalse(
            resolved["backend"] or resolved["frontend"] or resolved["web"],
            "ci.yml : un diff docs-only declenche un job lourd — la regle "
            "ajoutee pour scripts/ est trop large.",
        )


if __name__ == "__main__":
    unittest.main()
