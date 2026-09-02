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
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STAGES_FILE = ROOT / "STAGES.py"

SCANNED_SUFFIXES = {".py", ".js", ".jsx"}
SKIPPED_PARTS = {".git", "node_modules", "migrations", "scripts", "dist", "build"}

DECLARATION_RE = re.compile(
    r"(?:const\s+|let\s+|var\s+)?([A-Za-z_][A-Za-z0-9_]*(?:STAGE|PIPELINE)[A-Za-z0-9_]*)\s*=\s*[\[\(]([^\]\)]*)[\]\)]",
    re.IGNORECASE,
)
STRING_RE = re.compile(r"['\"]([^'\"]+)['\"]")

# CRX20 — `<something>.stage = 'LITERAL'` (Python and JS share this shape).
# `==` is deliberately NOT matched: a comparison is a read, and the ratchet
# targets the WRITES that move a lead through the funnel.
SCALAR_ASSIGN_RE = re.compile(r"\.stage\s*=\s*(['\"])([A-Za-z_][A-Za-z0-9_]*)\1")


def is_test_file(path: Path) -> bool:
    """Test modules are exempt from the scalar-assignment ratchet.

    A test may hardcode a stage key on purpose (to prove that the canonical
    key really is the one stored), and it ships no behaviour.
    """
    if any(part in {"tests", "test"} for part in path.parts):
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

    for path in ROOT.rglob("*"):
        if path.suffix not in SCANNED_SUFFIXES:
            continue
        if any(part in SKIPPED_PARTS for part in path.parts):
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

    if failures:
        print("Stage-name divergence detected (stage names must come from STAGES.py):")
        for failure in failures:
            print(f"  - {failure}")
        return 1

    print("Stage names consistent with STAGES.py.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
