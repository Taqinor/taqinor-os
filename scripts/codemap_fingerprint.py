#!/usr/bin/env python3
"""Freshness guards for ``docs/CODEMAP.md``.

The map carries two independent SHA-256 digests, both stamped by
``--write`` and verified by ``--check`` (the default). The check runs
inside the required ``stage-names`` CI job, so a drift that does not
refresh the map blocks the merge.

1. **Structure fingerprint** -- one digest over the repository's
   "structural surface", the files whose change should force a refresh
   of the CODEMAP body.
2. **Plan fingerprint** -- one digest over the *task states* declared in
   ``docs/PLAN.md`` and ``docs/PLAN2.md`` (each task id + done/open/
   blocked status). Ticking, adding, or removing a task flips this
   digest, so the §"Plan status" section of the CODEMAP cannot silently
   lag the plan. (Reordering the human-readable Done/Open lists or
   editing a blocked task's reason text does *not* flip it -- only a
   change in the set of task ids or their done/open state does.)

Structural surface
------------------
* file CONTENTS of: every ``models.py`` and every ``urls.py`` under
  ``backend/``, the root ``STAGES.py``,
  ``backend/django_core/requirements.txt``,
  ``backend/fastapi_ia/requirements.txt``, ``frontend/package.json``,
  ``.github/workflows/ci.yml`` and every file under
  ``frontend/src/router``;
* the sorted list of file PATHS (not contents) under
  ``frontend/src/features`` and ``frontend/src/pages`` -- so adding or
  removing a feature/page flips the fingerprint while editing inside a
  component does not.

Plan surface
------------
The canonical ``(source-file, task-id, status)`` triples parsed from the
BUILD QUEUE tasks of ``docs/PLAN.md`` and ``docs/PLAN2.md``. A task is
either a list item (``- [x] N1 — …`` / ``- [ ] N14 — …`` /
``- [BLOCKED: …] N26 — …``) or a header (``### T3 — … — [x]``). Status is
normalised to ``done`` / ``open`` / ``blocked`` / ``skip`` so the digest
tracks the build state, not prose.

Determinism
-----------
Everything is sorted, paths are emitted with forward slashes, and file
contents are newline-normalised (CRLF/CR -> LF) before hashing, so the
digests are identical on a Windows checkout (``core.autocrlf=true``) and
a Linux CI runner. ``docs/CODEMAP.md`` itself and the ``scripts/``
directory never contribute to the structure fingerprint. Both guards are
computed purely from files in the checkout -- never from live ``git``
state -- so a clone reproduces them exactly.

Pure Python standard library; no third-party dependency.
"""
from __future__ import annotations

import argparse
import hashlib
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CODEMAP = ROOT / "docs" / "CODEMAP.md"

FINGERPRINT_PREFIX = "Structure fingerprint:"
PLAN_FINGERPRINT_PREFIX = "Plan fingerprint:"
GENERATED_PREFIX = "Generated from commit"

# Plan files whose task states feed the plan fingerprint (existing only).
PLAN_FILES = ("docs/PLAN.md", "docs/PLAN2.md")

# A BUILD-QUEUE task as a list item: "- [x] N1 — …", "- [ ] N14 — …",
# "- [BLOCKED: …] N26 — …", "- [x] **A1 — …".
_TASK_LIST_RE = re.compile(
    r"^- \[(?P<status>[^\]]*)\]\s+\*{0,2}(?P<id>[A-Z]+\d+)\s+—\s+(?P<label>.*)$"
)
# A BUILD-QUEUE task as a header with a trailing status box:
# "### T3 — Bulk actions on leads — [x]".
_TASK_HEADER_RE = re.compile(
    r"^#{2,4}\s+(?P<id>[A-Z]+\d+)\s+—\s+(?P<label>.*?)\s+—\s+\[(?P<status>[^\]]*)\]"
)

# Directory names that never contribute (vendored / generated / state).
VENDORED = {
    ".git", "node_modules", "__pycache__", "migrations",
    ".venv", ".venv_test", "dist", "build",
}


def _relposix(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def _keep(path: Path) -> bool:
    """Drop excluded files: CODEMAP itself, scripts/, vendored dirs."""
    rel_parts = path.relative_to(ROOT).parts
    if rel_parts and rel_parts[0] == "scripts":
        return False
    if path.resolve() == CODEMAP.resolve():
        return False
    return not any(part in VENDORED for part in rel_parts)


def _content_files() -> list[Path]:
    """Files whose contents feed the fingerprint (existing only)."""
    backend = ROOT / "backend"
    candidates: list[Path] = []
    candidates += backend.rglob("models.py")
    candidates += backend.rglob("urls.py")
    candidates += [
        ROOT / "STAGES.py",
        backend / "django_core" / "requirements.txt",
        backend / "fastapi_ia" / "requirements.txt",
        ROOT / "frontend" / "package.json",
        ROOT / ".github" / "workflows" / "ci.yml",
    ]
    router = ROOT / "frontend" / "src" / "router"
    if router.is_dir():
        candidates += [p for p in router.rglob("*") if p.is_file()]
    kept = {
        _relposix(p): p
        for p in candidates
        if p.is_file() and _keep(p)
    }
    return [kept[rel] for rel in sorted(kept)]


def _path_only(*dirs: Path) -> list[str]:
    """Sorted relative paths of every file under the given dirs."""
    found: set[str] = set()
    for base in dirs:
        if not base.is_dir():
            continue
        for path in base.rglob("*"):
            if path.is_file() and _keep(path):
                found.add(_relposix(path))
    return sorted(found)


def _normalised(path: Path) -> bytes:
    raw = path.read_bytes()
    return raw.replace(b"\r\n", b"\n").replace(b"\r", b"\n")


def compute_fingerprint() -> str:
    """One SHA-256 over the whole structural surface."""
    lines: list[str] = []
    for path in _content_files():
        digest = hashlib.sha256(_normalised(path)).hexdigest()
        lines.append(f"C {_relposix(path)} {digest}")
    features = ROOT / "frontend" / "src" / "features"
    pages = ROOT / "frontend" / "src" / "pages"
    for rel in _path_only(features):
        lines.append(f"P features {rel}")
    for rel in _path_only(pages):
        lines.append(f"P pages {rel}")
    blob = "\n".join(lines) + "\n"
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


# --------------------------------------------------------------------------
# Plan-status fingerprint (docs/PLAN.md + docs/PLAN2.md task states)
# --------------------------------------------------------------------------

def _status_norm(token: str) -> str:
    """Normalise a checkbox token to done/open/blocked/skip."""
    token = token.strip()
    if token.lower() == "x":
        return "done"
    if token == "":
        return "open"
    head = token.split(":", 1)[0].split()[0].upper() if token else ""
    if head == "BLOCKED":
        return "blocked"
    if head == "SKIP":
        return "skip"
    return token.lower()


def _id_sort_key(source: str, task_id: str) -> tuple:
    """Natural sort key so N9 precedes N10, grouped by source then prefix."""
    match = re.match(r"([A-Z]+)(\d+)", task_id)
    prefix, number = (match.group(1), int(match.group(2))) if match else (task_id, 0)
    return (source, prefix, number)


def _short_label(text: str) -> str:
    """A compact, deterministic one-line label for a task."""
    text = text.strip().lstrip("*").strip()
    # Drop a trailing status box left on header tasks ("… — [x] (already…)").
    text = re.split(r"\s+—\s+\[", text)[0].strip()
    # Cut at the first bold-close ("**Title**, …" / "Title.** body" forms).
    if "**" in text:
        text = text.split("**", 1)[0].strip()
    # Keep the first sentence when it lands early (ignore e.g./i.e.).
    for sentence in re.finditer(r"\.\s", text):
        if text[max(0, sentence.start() - 3):sentence.start()].lower() in ("e.g", "i.e"):
            continue
        if sentence.start() <= 90:
            text = text[: sentence.start()]
        break
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) > 88:
        text = text[:88].rsplit(" ", 1)[0].rstrip(",;:") + "…"
    elif text.endswith("."):
        text = text[:-1]
    return text


def extract_plan_tasks() -> list[dict]:
    """Parse every BUILD-QUEUE task from the plan files (existing only).

    Returns dicts ``{source, id, status, label}`` in (source, id) order.
    Only checkbox list items and status-boxed headers count as tasks, so
    DONE-LOG prose, GATED ``G*`` items, and MANUAL bullets are ignored.
    """
    tasks: dict[tuple, dict] = {}
    for rel in PLAN_FILES:
        path = ROOT / rel
        if not path.is_file():
            continue
        for raw in path.read_text(encoding="utf-8").splitlines():
            match = _TASK_LIST_RE.match(raw) or _TASK_HEADER_RE.match(raw)
            if not match:
                continue
            task_id = match.group("id")
            key = (rel, task_id)
            # First declaration wins (the queue line, not a later mention).
            tasks.setdefault(
                key,
                {
                    "source": rel,
                    "id": task_id,
                    "status": _status_norm(match.group("status")),
                    "label": _short_label(match.group("label")),
                },
            )
    return [tasks[k] for k in sorted(tasks, key=lambda k: _id_sort_key(*k))]


def compute_plan_fingerprint() -> str:
    """One SHA-256 over the canonical (source, id, status) task triples."""
    lines = [f"{t['source']} {t['id']} {t['status']}" for t in extract_plan_tasks()]
    blob = "\n".join(lines) + "\n"
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def render_plan_status() -> str:
    """Markdown Done / Open / Blocked lists for the CODEMAP §Plan status."""
    tasks = extract_plan_tasks()
    done = [t for t in tasks if t["status"] == "done"]
    blocked = [t for t in tasks if t["status"] == "blocked"]
    other = [t for t in tasks if t["status"] not in ("done", "blocked")]

    def fmt(items: list[dict]) -> list[str]:
        return [f"- `{t['id']}` — {t['label']}" for t in items] or ["- _(none)_"]

    out = [
        f"**Done ({len(done)})**",
        "",
        *fmt(done),
        "",
        f"**Open — to build ({len(other)})**",
        "",
        *fmt(other),
        "",
        f"**Blocked — awaiting founder decision ({len(blocked)})**",
        "",
        *fmt(blocked),
    ]
    return "\n".join(out)


def _read_line(prefix: str) -> str | None:
    """Return the digest stored under ``prefix`` in CODEMAP, or None."""
    if not CODEMAP.exists():
        return None
    for line in CODEMAP.read_text(encoding="utf-8").splitlines():
        if line.startswith(prefix):
            return line[len(prefix):].strip()
    return None


def read_stored() -> str | None:
    """Return the stored structure fingerprint, or None if absent."""
    return _read_line(FINGERPRINT_PREFIX)


def read_stored_plan() -> str | None:
    """Return the stored plan fingerprint, or None if absent."""
    return _read_line(PLAN_FINGERPRINT_PREFIX)


def _stamp(lines: list[str], prefix: str, value: str, anchors: tuple[str, ...]) -> list[str]:
    """Insert/replace ``prefix`` line right after the highest-priority anchor.

    ``anchors`` is tried in order: the line is placed after the first
    anchor that exists in the file, not merely the first anchor line in
    file order — so a fingerprint can be pinned just below another.
    """
    new_line = f"{prefix} {value}"
    kept = [ln for ln in lines if not ln.startswith(prefix)]
    anchor = next((a for a in anchors if any(ln.startswith(a) for ln in kept)), None)
    if anchor is None:
        sys.exit(
            f"Cannot write '{prefix}': no anchor line "
            f"({', '.join(anchors)}) found in {CODEMAP}."
        )
    out: list[str] = []
    inserted = False
    for line in kept:
        out.append(line)
        if not inserted and line.startswith(anchor):
            out.append(new_line)
            inserted = True
    return out


def write_fingerprints(structure: str, plan: str) -> None:
    """Insert/replace both fingerprint lines under the commit header."""
    if not CODEMAP.exists():
        sys.exit(f"Cannot write fingerprint: {CODEMAP} is missing.")
    lines = CODEMAP.read_text(encoding="utf-8").split("\n")
    lines = _stamp(lines, FINGERPRINT_PREFIX, structure, (GENERATED_PREFIX,))
    # The plan line sits just under the structure line (falls back to the
    # commit header if the structure line is somehow absent).
    lines = _stamp(
        lines, PLAN_FINGERPRINT_PREFIX, plan, (FINGERPRINT_PREFIX, GENERATED_PREFIX)
    )
    CODEMAP.write_text("\n".join(lines), encoding="utf-8", newline="\n")


_GUIDANCE = (
    "Regenerate docs/CODEMAP.md from the current source, then run:\n"
    "    python scripts/codemap_fingerprint.py --write"
)
_PLAN_GUIDANCE = (
    "Refresh the §\"Plan status\" section of docs/CODEMAP.md from the plan "
    "files (paste `--print-plan-status`), then run:\n"
    "    python scripts/codemap_fingerprint.py --write"
)


def _check_one(label: str, expected: str, stored: str | None, guidance: str) -> int:
    if stored is None:
        print(
            f"docs/CODEMAP.md has no '{label}' line.\n" + guidance,
            file=sys.stderr,
        )
        return 1
    if stored != expected:
        print(
            f"docs/CODEMAP.md is stale: the {label.rstrip(':').lower()} "
            "changed but the map was not refreshed.\n"
            + guidance
            + f"\n  expected: {expected}\n  stored:   {stored}",
            file=sys.stderr,
        )
        return 1
    print(f"docs/CODEMAP.md {label.rstrip(':').lower()} OK ({expected}).")
    return 0


def _check() -> int:
    status = _check_one(
        "Structure fingerprint:", compute_fingerprint(), read_stored(), _GUIDANCE
    )
    status |= _check_one(
        "Plan fingerprint:",
        compute_plan_fingerprint(),
        read_stored_plan(),
        _PLAN_GUIDANCE,
    )
    return status


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Verify or write the docs/CODEMAP.md structure and "
        "plan-status fingerprints.",
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--write",
        action="store_true",
        help="compute both fingerprints and stamp them into CODEMAP.md",
    )
    mode.add_argument(
        "--check",
        action="store_true",
        help="verify both stored fingerprints still match (default)",
    )
    mode.add_argument(
        "--print-plan-status",
        action="store_true",
        help="print the Done/Open/Blocked markdown for the §Plan status "
        "section (paste into CODEMAP.md when regenerating)",
    )
    args = parser.parse_args(argv)
    if args.print_plan_status:
        print(render_plan_status())
        return 0
    if args.write:
        structure = compute_fingerprint()
        plan = compute_plan_fingerprint()
        write_fingerprints(structure, plan)
        print(
            "Wrote structure fingerprint "
            f"({structure}) and plan fingerprint ({plan}) to docs/CODEMAP.md."
        )
        return 0
    return _check()


if __name__ == "__main__":
    sys.exit(main())
