#!/usr/bin/env python3
"""CI guard: every `frontend/src/**/*.test.*` file must be picked up by AT
LEAST ONE test runner's include glob.

Why (ERR-QAH-CI-TESTS-JS-JAMAIS-EXECUTES, 28/09/2026). 13 frontend test files
named `*.test.js` were matched by NO runner: `frontend/vitest.config.js`
included only `src/**/*.test.jsx`, `scripts/ci_frontend_shard.py` sharded
only `.test.jsx`, and the `node:test` job (`.github/workflows/ci.yml`,
`frontend-static`) only collected `src/**/*.test.mjs`. Every job stayed
green while these files silently never executed — false coverage, caught
only by a human QA pass (QAH3). This guard makes that class of drift a RED
CI check instead of a QA finding.

Mechanics. Two runners exist today, each with its own include rule:
  - Vitest: `.test.jsx` and `.test.js` (read from
    `scripts/ci_frontend_shard.INCLUDE_SUFFIXES` — the SAME constant the
    sharder uses, so the two can never drift apart from each other; a guard
    test below pins that `frontend/vitest.config.js` still literally contains
    each of `ci_frontend_shard.INCLUDE_PATTERNS`).
  - `node --test`: `.test.mjs`, read directly out of
    `.github/workflows/ci.yml`'s `node --test "<glob>"` invocation — never
    hand-copied — so a future change to that glob is picked up automatically
    instead of silently invalidating this guard.

A `frontend/src/**/*.test.*` file whose suffix matches NEITHER family fails
the build, naming the orphan file(s) and which suffixes ARE covered today.

Usage
-----
    python scripts/check_frontend_test_runner_coverage.py
"""
from __future__ import annotations

import os
import re
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FRONTEND = os.path.join(REPO_ROOT, "frontend")
SRC_DIR = os.path.join(FRONTEND, "src")
CI_YML = os.path.join(REPO_ROOT, ".github", "workflows", "ci.yml")

SKIP_DIRS = {"node_modules", "__pycache__", ".git", "dist", "build", "coverage"}

_TEST_FILE_RE = re.compile(r"^(?P<stem>.+)\.test\.(?P<suffix>[A-Za-z0-9]+)$")
_NODE_TEST_GLOB_RE = re.compile(r'node\s+--test\s+"src/\*\*/\*\.test\.([A-Za-z0-9]+)"')


def _import_ci_frontend_shard():
    sys.path.insert(0, os.path.join(REPO_ROOT, "scripts"))
    import ci_frontend_shard  # noqa: PLC0415 (deliberate lazy import, see module docstring)
    return ci_frontend_shard


def vitest_suffixes() -> set[str]:
    """Suffixes Vitest picks up — the sharder's own constant, never re-derived."""
    fs = _import_ci_frontend_shard()
    return {suffix.rsplit(".", 1)[-1] for suffix in fs.INCLUDE_SUFFIXES}


def node_test_suffixes(ci_yml_path: str = CI_YML) -> set[str]:
    """Suffixes `node --test` picks up, read straight from ci.yml — never a
    hand-maintained copy that could drift from the real glob (AUD830 class)."""
    try:
        with open(ci_yml_path, encoding="utf-8") as fh:
            text = fh.read()
    except OSError:
        return set()
    return set(_NODE_TEST_GLOB_RE.findall(text))


def discover_test_files(src_dir: str, frontend: str) -> list[str]:
    """Every `*.test.<suffix>` file under `src_dir`, path relative to
    `frontend` (e.g. `src/lib/foo.test.js`)."""
    found = []
    for dirpath, dirnames, filenames in os.walk(src_dir):
        dirnames[:] = sorted(d for d in dirnames if d not in SKIP_DIRS)
        for name in sorted(filenames):
            if _TEST_FILE_RE.match(name):
                rel = os.path.relpath(os.path.join(dirpath, name), frontend)
                found.append(rel.replace(os.sep, "/"))
    return sorted(found)


def find_orphans(frontend: str | None = None) -> tuple[list[tuple[str, str]], set[str]]:
    """Returns (orphans, covered_suffixes). Each orphan is (relpath, suffix).

    `frontend` defaults to the module-level `FRONTEND` looked up at CALL
    time (not baked into a default-argument value) so a test can monkeypatch
    `check_frontend_test_runner_coverage.FRONTEND` and have `main()` pick it
    up transparently."""
    if frontend is None:
        frontend = FRONTEND
    covered = vitest_suffixes() | node_test_suffixes()
    src_dir = os.path.join(frontend, "src")
    orphans = []
    for rel in discover_test_files(src_dir, frontend):
        match = _TEST_FILE_RE.match(os.path.basename(rel))
        suffix = match.group("suffix")
        if suffix not in covered:
            orphans.append((rel, suffix))
    return orphans, covered


def main(argv=None) -> int:
    del argv
    orphans, covered = find_orphans()
    if orphans:
        print(
            "check_frontend_test_runner_coverage : %d fichier(s) *.test.* sous "
            "frontend/src ne sont ramasses par AUCUN lanceur (glob Vitest = %s, "
            "glob node:test = %s) :" % (
                len(orphans),
                sorted(vitest_suffixes()),
                sorted(node_test_suffixes()),
            )
        )
        for rel, suffix in orphans:
            print("  - %s (.%s)" % (rel, suffix))
        print(
            "\nUn fichier de test qu'aucun lanceur ne ramasse ne tourne NULLE PART "
            "(ni local, ni CI) : fausse couverture, silence total sur une "
            "regression (ERR-QAH-CI-TESTS-JS-JAMAIS-EXECUTES, 28/09/2026). "
            "Corriger : soit widen l'include Vitest "
            "(frontend/vitest.config.js + scripts/ci_frontend_shard.py) pour un "
            "fichier vitest-style (`import ... from 'vitest'`), soit renommer un "
            "fichier node:test-style (`import test from 'node:test'`) en "
            "`.mjs` pour rejoindre le glob `node --test` existant."
        )
        return 1
    print(
        "check_frontend_test_runner_coverage : OK — tous les fichiers "
        "*.test.* sous frontend/src sont ramasses par au moins un lanceur "
        "(suffixes couverts : %s)." % sorted(covered)
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
