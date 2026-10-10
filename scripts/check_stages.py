"""CI guard: pipeline stage names must come from STAGES.py, never hardcoded.

Behavior:
- STAGES.py absent  -> the canonical 6 stage names have not been decided yet
  (open question for the founder). The check prints a notice and passes, so CI
  stays green until the file lands. It activates automatically afterwards.
- STAGES.py present -> it must define STAGES, a list of exactly 6 unique
  names. Any other file that declares a stage-list variable (NAME containing
  STAGE/PIPELINE) whose string values diverge from STAGES.py fails the build.
- CRX20: a *scalar* stage assignment (`obj.stage = 'QUOTE_SENT'`) in
  production code also fails the build. A stage list is not the only way to
  hardcode a stage name: `lead.stage = 'FOLLOW_UP'` slipped through the
  list-only check for months (apps/ventes/domain/recouvrement.py). Write
  `lead.stage = stages.FOLLOW_UP` instead (`from apps.crm import stages`, which
  re-exports the repo-root STAGES.py). Test files are exempt: a test may pin a
  literal on purpose to prove the mapping, and it never ships behaviour.
- AANA46: production Python must not carry a stage key as a *literal* in a
  dict keyed by stages (`{'SIGNED': ...}`), a comparison (`== 'SIGNED'`) or a
  keyword/local assignment (`stage='SIGNED'`). The pre-existing sites are
  frozen per file in LITERAL_ALLOW below — a ceiling that may only DECREASE
  (a file above its ceiling fails; a file below it must lower the ceiling).
  Exempt: tests, `STAGES.py`, `apps/crm/stages.py`, migrations, parked code.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path
TYPE_DE_CLE = "par_symbole"  # AMET100 — cle de contenu `fichier::symbole` (jamais un numero de ligne)

ROOT = Path(__file__).resolve().parent.parent


def _rel_parts(path, base=ROOT):
    """ADEP27 - parties du chemin RELATIVES a la racine du depot : un depot
    range sous un dossier nomme `build/`, `dist/` ou `tests/` doit donner le
    meme verdict (jamais tester les dossiers du chemin absolu)."""
    try:
        return path.relative_to(base).parts
    except ValueError:
        return path.parts

STAGES_FILE = ROOT / "STAGES.py"

SCANNED_SUFFIXES = {".py", ".js", ".jsx"}
# SOLMVP37 — "parked" added: backend/parked/ mirrors the pre-parking source of
# the 47 apps sorted out of the solar MVP (backend/django_core/core/parked.py)
# straight from ROOT.rglob("*") below — dead code that must stay out of every
# CI guard, this one included, even though nothing there diverges today.
SKIPPED_PARTS = {".git", "node_modules", "migrations", "scripts", "dist", "build", "parked"}

DECLARATION_RE = re.compile(
    # (?<!LE)STAGE : le vocabulaire solaire français contient « lestage » et
    # « délestage » (ballast, load-shedding) — un identifiant comme
    # CLES_STRUCTURE_LESTAGE n'est pas une liste d'étapes du funnel.
    r"(?:const\s+|let\s+|var\s+)?([A-Za-z_][A-Za-z0-9_]*(?:(?<!LE)STAGE|PIPELINE)[A-Za-z0-9_]*)\s*=\s*[\[\(]([^\]\)]*)[\]\)]",
    re.IGNORECASE,
)
STRING_RE = re.compile(r"['\"]([^'\"]+)['\"]")

# CRX20 — `<something>.stage = 'LITERAL'` (Python and JS share this shape).
# This ratchet targets the WRITES; comparisons/dict keys are AANA46 below.
SCALAR_ASSIGN_RE = re.compile(r"\.stage\s*=\s*(['\"])([A-Za-z_][A-Za-z0-9_]*)\1")


# AANA46 — literal stage keys outside a `.stage = '...'` write. Three shapes:
# dict key, ==/!= comparison, `stage='X'` keyword/local assignment.
_KEYS = r"(?:NEW|CONTACTED|QUOTE_SENT|FOLLOW_UP|SIGNED|COLD)"
LITERAL_USE_RE = re.compile(
    r"(?:^|[{,])\s*['\"]" + _KEYS + r"['\"]\s*:"            # dict key
    r"|(?:==|!=)\s*['\"]" + _KEYS + r"['\"]"                  # x == 'SIGNED'
    r"|['\"]" + _KEYS + r"['\"]\s*(?:==|!=)"                  # 'SIGNED' == x
    r"|(?<![\w.])stage(?:__exact)?\s*=\s*['\"]" + _KEYS + r"['\"]",  # stage='X'
    re.MULTILINE,
)
# Files that ARE the stage vocabulary (never flagged).
LITERAL_EXEMPT = {
    "backend/django_core/apps/crm/stages.py",
}
# Per-file ceilings (number of literal uses) frozen on 2026-10-07 — DECREASE ONLY.
LITERAL_ALLOW = {
    "backend/django_core/apps/crm/leads_selectors.py": 1,
    "backend/django_core/apps/crm/services.py": 3,
    "backend/django_core/apps/crm/views.py": 1,
    "backend/django_core/core/win_probability.py": 6,
}


def count_literal_uses(text: str) -> int:
    return len(LITERAL_USE_RE.findall(text))


# ADEP23 — the same literals on the FRONTEND (js/jsx): bare dict keys
# (`NEW: 0.1`, the shape KanbanView uses), quoted keys, ===/!==/==/!= comparisons
# against a key, and literal lists of two or more keys. The Python regex above
# needs quotes around a dict key, so `{ NEW: 0.1 }` slipped through.
_JS_Q = r"['\"]"
_JS_KEY = _JS_Q + _KEYS + _JS_Q
LITERAL_USE_JS_RE = re.compile(
    "|".join([
        r"(?:^|[{,])\s*" + _JS_KEY + r"\s*:",                    # 'NEW': x
        r"(?:^|[{,])\s*" + _KEYS + r"\s*:",                      # NEW: x
        r"(?:===|!==|==|!=)\s*" + _JS_KEY,                       # s === 'NEW'
        _JS_KEY + r"\s*(?:===|!==|==|!=)",                       # 'NEW' === s
        r"\[\s*" + _JS_KEY + r"\s*(?:,\s*" + _JS_KEY + r"\s*)+",  # ['NEW', 'SIGNED']
    ]),
    re.MULTILINE,
)
# The stage vocabulary of the frontend (never flagged).
JS_LITERAL_EXEMPT = {
    "frontend/src/features/crm/stages.js",
}
JS_ALLOW_FILE = ROOT / "scripts" / "stages_litteraux_js_allow.txt"


def count_js_literal_uses(text: str) -> int:
    return len(LITERAL_USE_JS_RE.findall(text))


def load_js_allow() -> dict[str, int]:
    """`chemin = N` per line (decrease-only ceilings), `#` comments."""
    allow: dict[str, int] = {}
    if not JS_ALLOW_FILE.exists():
        return allow
    for raw in JS_ALLOW_FILE.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        rel, _, n = line.partition("=")
        allow[rel.strip()] = int(n.strip())
    return allow


def _is_js_test(path: Path) -> bool:
    return is_test_file(path) or "__tests__" in _rel_parts(path) or ".test." in path.name


def scan_js_literals() -> dict[str, int]:
    counts: dict[str, int] = {}
    base = ROOT / "frontend" / "src"
    if not base.is_dir():
        return counts
    for path in base.rglob("*"):
        if path.suffix not in {".js", ".jsx"} or _is_js_test(path):
            continue
        if any(part in SKIPPED_PARTS for part in path.parts[len(ROOT.parts):]):
            continue
        rel = path.relative_to(ROOT).as_posix()
        if rel in JS_LITERAL_EXEMPT:
            continue
        try:
            n = count_js_literal_uses(path.read_text(encoding="utf-8"))
        except (UnicodeDecodeError, OSError):
            continue
        if n:
            counts[rel] = n
    return counts


def js_literal_failures(counts: dict[str, int], allow: dict[str, int]) -> list[str]:
    out: list[str] = []
    for rel, n in sorted(counts.items()):
        ceiling = allow.get(rel, 0)
        if n > ceiling:
            out.append(
                f"{rel}: {n} literal stage key(s) in the frontend (dict key / "
                f"comparison / key list), ceiling {ceiling} — import them from "
                f"features/crm/stages.js instead"
            )
    for rel, ceiling in sorted(allow.items()):
        n = counts.get(rel, 0)
        if n < ceiling:
            out.append(
                f"{rel}: only {n} literal stage key(s) left, ceiling is {ceiling} "
                f"— lower scripts/stages_litteraux_js_allow.txt (decrease-only ratchet)"
            )
    return out


def literal_failures(literal_counts: dict[str, int],
                     allow: dict[str, int] | None = None) -> list[str]:
    """AANA46 — compare per-file literal counts to the decrease-only ceilings."""
    allow = LITERAL_ALLOW if allow is None else allow
    out: list[str] = []
    for rel, n in sorted(literal_counts.items()):
        ceiling = allow.get(rel, 0)
        if n > ceiling:
            out.append(
                f"{rel}: {n} literal stage key(s) (dict key / comparison / "
                f"stage='X'), ceiling {ceiling} — use `from apps.crm import "
                f"stages` (`stages.SIGNED`) instead"
            )
    for rel, ceiling in sorted(allow.items()):
        n = literal_counts.get(rel, 0)
        if n < ceiling:
            out.append(
                f"{rel}: only {n} literal stage key(s) left, ceiling is "
                f"{ceiling} — lower LITERAL_ALLOW (decrease-only ratchet)"
            )
    return out


def is_test_file(path: Path) -> bool:
    """Test modules are exempt from the scalar-assignment ratchet.

    A test may hardcode a stage key on purpose (to prove that the canonical
    key really is the one stored), and it ships no behaviour.
    """
    if any(part in {"tests", "test"} for part in _rel_parts(path)):
        return True
    name = path.name
    return (
        name.startswith(("test_", "tests_"))
        or name in {"tests.py", "conftest.py"}
        or name.endswith(("_test.py", "_tests.py", ".test.js", ".test.jsx"))
    )


def load_canonical() -> list[str]:
    namespace: dict = {}
    exec(STAGES_FILE.read_text(encoding="utf-8"), namespace)  # noqa: S102 — our own file
    stages = namespace.get("STAGES")
    if not isinstance(stages, (list, tuple)):
        sys.exit("STAGES.py must define STAGES as a list of stage names.")
    if len(stages) != 6 or len(set(stages)) != 6:
        sys.exit(f"STAGES.py must define exactly 6 unique stage names, found {len(stages)}.")
    return list(stages)


def main() -> int:
    if not STAGES_FILE.exists():
        print(
            "STAGES.py not found — stage-name check skipped.\n"
            "The canonical 6 pipeline stage names are still an open question; "
            "this check activates automatically once STAGES.py is committed."
        )
        return 0

    canonical = set(load_canonical())
    failures: list[str] = []
    literal_counts: dict[str, int] = {}

    for path in ROOT.rglob("*"):
        if path.suffix not in SCANNED_SUFFIXES:
            continue
        if any(part in SKIPPED_PARTS for part in _rel_parts(path)):
            continue
        if path == STAGES_FILE:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        for match in DECLARATION_RE.finditer(text):
            names = STRING_RE.findall(match.group(2))
            if names and set(names) != canonical:
                failures.append(
                    f"{path.relative_to(ROOT)}: {match.group(1)} = {names} "
                    f"diverges from STAGES.py {sorted(canonical)}"
                )

        # CRX20 — scalar stage writes in production code.
        if is_test_file(path):
            continue
        # AANA46 — dict keys / comparisons / keyword literals (Python only).
        rel = path.relative_to(ROOT).as_posix()
        if path.suffix == ".py" and rel not in LITERAL_EXEMPT:
            n = count_literal_uses(text)
            if n:
                literal_counts[rel] = n
        for match in SCALAR_ASSIGN_RE.finditer(text):
            literal = match.group(2)
            if literal not in canonical:
                continue
            line_no = text.count("\n", 0, match.start()) + 1
            failures.append(
                f"{path.relative_to(ROOT)}:{line_no}: hardcoded stage write "
                f"`.stage = '{literal}'` — import it instead "
                f"(`from apps.crm import stages` then `stages.{literal}`)"
            )

    failures.extend(literal_failures(literal_counts))
    failures.extend(js_literal_failures(scan_js_literals(), load_js_allow()))

    if failures:
        print("Stage-name divergence detected (stage names must come from STAGES.py):")
        for failure in failures:
            print(f"  - {failure}")
        return 1

    print("Stage names consistent with STAGES.py.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
