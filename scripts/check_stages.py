"""CI guard: pipeline stage names must come from STAGES.py, never hardcoded.

Behavior:
- STAGES.py absent  -> the canonical 6 stage names have not been decided yet
  (open question for the founder). The check prints a notice and passes, so CI
  stays green until the file lands. It activates automatically afterwards.
- STAGES.py present -> it must define STAGES, a list of exactly 6 unique
  names. Any other file that declares a stage-list variable (NAME containing
  STAGE/PIPELINE) whose string values diverge from STAGES.py fails the build.
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

    if failures:
        print("Stage-name divergence detected (stage names must come from STAGES.py):")
        for failure in failures:
            print(f"  - {failure}")
        return 1

    print("Stage names consistent with STAGES.py.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
