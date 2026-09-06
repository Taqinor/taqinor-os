"""YDATA14 — CI guard (advisory v1): Celery tasks with external effects
should take PKs, never model instances, as parameters.

DB-free, AST-only (mirrors ``scripts/check_on_delete.py``). Scans EVERY
source file across ``apps/*``, ``core`` and ``authentication`` (excluding
``tests/``/``migrations/``) for any function decorated with
``@shared_task``/``@app.task`` and flags a parameter that LOOKS like a model
instance (named after a business object — ``devis``, ``facture``, ``lead``,
``client``, ``chantier``, ``paiement``, ``avoir``, ``bon_commande``…
WITHOUT an ``_id``/``_pk`` suffix) rather than a primary key. Recommends
passing ``pk`` + re-fetching inside the task body (a stale/pickled instance
is a correctness + idempotence risk across a retry).

AUD828 (M-09) — before this fix the file discovery was a CLOSED SET of 3
literal filenames (``tasks.py``/``scheduled.py``/``beat_tasks.py``), missing
14 of 54 files that actually decorate a function with ``@shared_task``
(``core/jobs.py``, ``core/idempotent_task.py``, ``authentication/tasks.py``,
every ``*_tasks.py``/``sweeps.py``/``digests.py``/``*_alertes.py``-style
split file…). Detection is now BY CONTENT: every source file is a candidate
(cheap textual pre-filter for the decorator token, same false-negative-safe
pattern as ``check_platform.py``'s full-tree scans), never a filename
allowlist — a task module can be named anything.

v1 = ADVISORY (per spec): a NEW task signature that passes what looks like a
model instance fails CI; every signature already in the repo today is
recorded in ``scripts/celery_task_allowlist.txt`` (generated once from the
current state) so this does not block on existing code — correctness fixes
for an allowlisted signature are ERROR_PLAN material, not this guard's job.

Usage:
    python scripts/check_celery_tasks.py
"""
from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DJANGO_CORE = ROOT / "backend" / "django_core"
APPS_DIR = DJANGO_CORE / "apps"
CORE_DIR = DJANGO_CORE / "core"
AUTH_DIR = DJANGO_CORE / "authentication"
ALLOWLIST_PATH = ROOT / "scripts" / "celery_task_allowlist.txt"

# AUD828 (M-09) — cheap textual pre-filter only (the AST walk in check_file()
# is the real, authoritative detector of an ACTUAL @shared_task/@app.task
# decorator on a function); this just avoids parsing every source file in
# the tree. A false-positive candidate (the substring appears but never as a
# real decorator) costs nothing — check_file() finds 0 decorated functions
# in it and moves on.
_TASK_TOKEN_RE = re.compile(r"shared_task|\.task\s*\(")
_EXCLUDED_DIR_PARTS = {"tests", "migrations", "__pycache__"}

# Parameter names that look like a bare model INSTANCE (business object),
# i.e. would need to be a fully hydrated ORM object rather than a PK, for a
# task boundary that must survive broker serialization + retries.
INSTANCE_LIKE_NAME_RE = re.compile(
    r"^(devis|facture|lead|client|chantier|paiement|avoir|bon_commande|"
    r"commande|ticket|activite|contrat|projet|intervention|opportunite)$",
    re.IGNORECASE,
)
# A name ending in _id/_pk/_ids/_pks (or literally 'pk'/'id') is a PK — safe.
PK_SUFFIX_RE = re.compile(r"(_id|_pk|_ids|_pks)$", re.IGNORECASE)


def _iter_task_files():
    """AUD828 (M-09) — content-based: every .py source file across apps/*,
    core and authentication (excluding tests/migrations/__pycache__) that
    TEXTUALLY mentions a task-decorator token, in deterministic path order.
    Replaces the old closed filename set (tasks.py/scheduled.py/
    beat_tasks.py) which missed a real @shared_task in 14 of 54 files."""
    for root_dir in (APPS_DIR, CORE_DIR, AUTH_DIR):
        if not root_dir.is_dir():
            continue
        for path in sorted(root_dir.glob("**/*.py")):
            if path.name == "__init__.py":
                continue
            if _EXCLUDED_DIR_PARTS & set(path.relative_to(root_dir).parts[:-1]):
                continue
            try:
                text = path.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                continue
            if _TASK_TOKEN_RE.search(text):
                yield path


def _rel(path: Path) -> str:
    return str(path.relative_to(ROOT)).replace("\\", "/")


def _load_allowlist():
    if not ALLOWLIST_PATH.exists():
        return set()
    out = set()
    for line in ALLOWLIST_PATH.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        out.add(line)
    return out


def _is_task_decorator(dec):
    """`@shared_task` / `@shared_task(...)` / `@app.task` / `@app.task(...)`."""
    node = dec
    if isinstance(node, ast.Call):
        node = node.func
    if isinstance(node, ast.Name):
        return node.id == "shared_task"
    if isinstance(node, ast.Attribute):
        return node.attr == "task"
    return False


def check_file(path: Path):
    source = path.read_text(encoding="utf-8")
    try:
        tree = ast.parse(source, filename=str(path))
    except SyntaxError as exc:
        return [], [("PARSE_ERROR", f"could not parse: {exc}")]

    all_rows = []
    findings = []

    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if not any(_is_task_decorator(d) for d in node.decorator_list):
            continue

        params = [a.arg for a in node.args.args if a.arg not in ("self", "cls")]
        lineno = node.lineno
        for param in params:
            if PK_SUFFIX_RE.search(param):
                continue
            if not INSTANCE_LIKE_NAME_RE.match(param):
                continue
            all_rows.append((_rel(path), lineno, node.name, param))
            allow_key = f"{_rel(path)}:{node.name}"
            if allow_key not in _ALLOW_CACHE:
                findings.append((
                    "TASK_TAKES_MODEL_INSTANCE",
                    f"{_rel(path)}:{lineno}: task {node.name}(...) has a "
                    f"parameter '{param}' that looks like a model instance "
                    "rather than a PK — pass an id and re-fetch inside the "
                    "task body.",
                ))

    return all_rows, findings


_ALLOW_CACHE = set()


def main(argv):
    global _ALLOW_CACHE
    _ALLOW_CACHE = _load_allowlist()

    all_rows = []
    report_lines = []
    for path in _iter_task_files():
        rows, findings = check_file(path)
        all_rows.extend(rows)
        for code, message in findings:
            report_lines.append(message)

    print(f"check_celery_tasks: {len(all_rows)} instance-like task "
          "parameter(s) found across every @shared_task/@app.task in "
          "apps/*, core, authentication.")
    for rel, lineno, task_name, param in all_rows:
        print(f"  {rel}:{lineno}  {task_name}({param})")

    if report_lines:
        print("\ncheck_celery_tasks: violation(s) found:")
        for line in report_lines:
            print(f"  - {line}")
        print(
            "\nFix by passing a pk and re-fetching in the task body, or — "
            "if reviewed and intentional — add '<file>:<task_name>' to "
            "scripts/celery_task_allowlist.txt."
        )
        return 1

    print("\ncheck_celery_tasks: OK.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
