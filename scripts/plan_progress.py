#!/usr/bin/env python3
"""SCA2 — per-group task completeness across the plan files.

Counts ``[x]`` (done) vs ``[ ]``/``[BLOCKED: ...]`` (open) task lines by
task-id PREFIX across ``docs/PLAN.md``, ``docs/PLAN2.md``,
``docs/new_tasks_plan.md`` and ``docs/FRONTEND_GAP_PLAN.md``, and prints a
stable JSON ``{prefix: {done, total, pct}}``.

This is the measurement half of SCA1/SCA3: ``BUILD_ORDER.yml`` names
percentage thresholds (e.g. ``ARC-noyau: 80``) and ``plan_lanes.py`` (SCA3)
reads THIS script's output to decide whether a later-wave group's
prerequisite is actually satisfied yet.

Task-line formats tolerated (mirrors ``scripts/plan_lanes.py`` plus two
extensions this repo's plan files actually use — verified by grep across all
four files on 2026-07-10):

1. Checkbox list item:      ``- [ ] ARC1 — ...``          (the vast majority)
2. Checkbox, bold id:       ``- [ ] **NTIDE1** — ...``    (docs/new_tasks_plan.md)
3. Header task:              ``### ARC1 — label — [ ]``   (rare; plan_lanes.py
                                                             supports it too)
4. Compound id:              ``FE-XFLT4`` inside a checkbox line
   (docs/FRONTEND_GAP_PLAN.md — the frontend-wiring plan keys tasks by a
   compound ``FE-<domain>`` prefix, e.g. ``FE-XFLT4``/``FE-COMPTA2``, not a
   bare letter prefix)

A task line is "done" if its status text is exactly ``x`` (case-insensitive,
surrounding whitespace ignored); anything else inside the brackets (empty,
``BLOCKED: ...``, etc.) counts as open. This matches ``plan_lanes.py``, which
only ever treats a truly-empty ``[ ]`` as buildable.

Pure standard library. No third-party dependency (JSON stdlib only).

CLI:
    python scripts/plan_progress.py                  # pretty JSON to stdout
    python scripts/plan_progress.py --prefix ARC      # single prefix only
    python scripts/plan_progress.py --compact         # no indent
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

DEFAULT_PLAN_FILES = [
    ROOT / "docs" / "PLAN.md",
    ROOT / "docs" / "PLAN2.md",
    ROOT / "docs" / "new_tasks_plan.md",
    ROOT / "docs" / "FRONTEND_GAP_PLAN.md",
]

# ``- [ ] ARC1 — ...`` / ``- [x] **NTIDE1** — ...`` / ``- [ ] FE-XFLT4 — ...``
# Prefix group ``compound`` = a dash-joined lane id like ``FE-XFLT`` (used by
# docs/FRONTEND_GAP_PLAN.md); group ``plain`` = the bare letter-prefix task id
# used everywhere else. A single task line may name a RANGE or a LIST of
# sibling ids after the first one (``FE-XFLT7/15/18``, ``FE-XMFG1-16``,
# ``FE-XFAC14/XACC26``) — verified pervasive in FRONTEND_GAP_PLAN.md by grep.
# Each checkbox LINE still counts as exactly one task (matching
# plan_lanes.py's one-id-per-line model): the trailing
# ``(-N|/[A-Z]*\d+)*`` suffix is consumed and ignored, never re-counted.
_ID_SUFFIX = r"(?:[-/][A-Z]*\d+)*"
_TASK_LIST_RE = re.compile(
    r"^\s*-\s\[(?P<status>[^\]]*)\]\s+"
    r"\*{0,2}(?:(?P<compound>[A-Z]+-[A-Z]+)|(?P<plain>[A-Z]+))\d+" + _ID_SUFFIX + r"\b\*{0,2}\s+—"
)
# ``### ARC1 — label — [ ]`` header-style task (plan_lanes.py supports this
# shape too, e.g. docs/PLAN2.md T-series headers).
_TASK_HEADER_RE = re.compile(
    r"^#{2,4}\s+(?:(?P<compound>[A-Z]+-[A-Z]+)|(?P<plain>[A-Z]+))\d+" + _ID_SUFFIX
    + r"\s+—.*?—\s+\[(?P<status>[^\]]*)\]"
)


def _is_done(status: str) -> bool:
    return status.strip().lower() == "x"


def _prefix_of(match: re.Match) -> str:
    compound = match.group("compound")
    if compound:
        return compound
    return match.group("plain")


def count_file(path: Path) -> dict[str, dict[str, int]]:
    """Return ``{prefix: {"done": int, "total": int}}`` for one plan file."""
    counts: dict[str, dict[str, int]] = {}
    if not path.is_file():
        return counts
    text = path.read_text(encoding="utf-8")
    for line in text.splitlines():
        m = _TASK_LIST_RE.match(line) or _TASK_HEADER_RE.match(line)
        if not m:
            continue
        prefix = _prefix_of(m)
        bucket = counts.setdefault(prefix, {"done": 0, "total": 0})
        bucket["total"] += 1
        if _is_done(m.group("status")):
            bucket["done"] += 1
    return counts


def aggregate(paths: list[Path]) -> dict[str, dict[str, int]]:
    total: dict[str, dict[str, int]] = {}
    for path in paths:
        for prefix, bucket in count_file(path).items():
            agg = total.setdefault(prefix, {"done": 0, "total": 0})
            agg["done"] += bucket["done"]
            agg["total"] += bucket["total"]
    return total


def with_pct(counts: dict[str, dict[str, int]]) -> dict[str, dict[str, float]]:
    """Attach a stable ``pct`` (0-100, one decimal) to every prefix bucket."""
    out: dict[str, dict[str, float]] = {}
    for prefix, bucket in counts.items():
        done, total = bucket["done"], bucket["total"]
        pct = round((done / total) * 100, 1) if total else 0.0
        out[prefix] = {"done": done, "total": total, "pct": pct}
    return out


def progress(paths: list[Path] | None = None) -> dict[str, dict[str, float]]:
    """Public entry point other scripts (plan_lanes.py) import."""
    return with_pct(aggregate(paths if paths is not None else DEFAULT_PLAN_FILES))


def group_pct(prefix: str, paths: list[Path] | None = None) -> float:
    """Convenience: percent-complete for a single prefix (0.0 if unseen)."""
    data = progress(paths)
    return data.get(prefix, {}).get("pct", 0.0)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Per-task-id-prefix completeness across the plan files "
        "([x] done vs [ ]/[BLOCKED:...] open), stable JSON output.",
    )
    parser.add_argument(
        "--prefix", default=None,
        help="only report this one prefix (exact match, e.g. ARC or FE-XFLT)",
    )
    parser.add_argument(
        "--compact", action="store_true",
        help="emit compact JSON (no indentation)",
    )
    parser.add_argument(
        "--files", nargs="*", default=None,
        help="override the plan files scanned (default: the 4 standard plan files)",
    )
    args = parser.parse_args(argv)

    paths = [Path(f) for f in args.files] if args.files else DEFAULT_PLAN_FILES
    data = progress(paths)

    if args.prefix is not None:
        data = {args.prefix: data.get(args.prefix, {"done": 0, "total": 0, "pct": 0.0})}

    # Stable output: sort keys so the JSON is byte-identical across runs
    # given identical input (no dict-ordering surprises).
    indent = None if args.compact else 2
    print(json.dumps(data, ensure_ascii=False, indent=indent, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
