"""YDATA20 — CI guard: safe migrations for populated tables + deterministic
index/constraint names.

Complements ``check_safe_migrations.py`` (YOPSB4, blocking DDL patterns) with
the two YDATA20 checks, DB-free via ``ast`` over
``backend/django_core/{apps/*,core,authentication}/migrations/*.py``:

  (a) A ``AddField(unique=True)`` OR a ``AddField(null=False, default=<fixed>)``
      on a table NOT created in the SAME migration is a one-shot constraint on
      a potentially-populated table — CI on an empty DB passes but prod fails.
      The safe shape is a 3-step migration: nullable/unconstrained add ->
      ``RunPython`` backfill -> ``AlterField(unique=True/null=False)``. A single
      such migration that adds the field AND the constraint at once is flagged.

  (b) A ``AddIndex``/``AddConstraint``/``RenameIndex`` whose ``name=`` is
      neither a Django deterministic-hash name NOR declared verbatim in any
      ``models.py`` ``Meta`` risks the "changes not reflected" drift (project
      memory: fix = ``RenameIndex``) — the migration names an index the models
      no longer describe under that name. Legitimate hand-written names that
      ARE mirrored in ``models.py`` pass silently (explicit names are fine).

v1: existing (historical) migrations that match are recorded in
``scripts/migration_safety_allow.txt`` (baseline); only a NEW migration with an
un-allowlisted finding fails CI.

Usage:
    python scripts/check_migration_safety.py           # check (CI)
    python scripts/check_migration_safety.py --list     # print every finding
"""
from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DJANGO_CORE = ROOT / "backend" / "django_core"
APPS_DIR = DJANGO_CORE / "apps"
ALLOWLIST_PATH = ROOT / "scripts" / "migration_safety_allow.txt"

MIGRATION_ROOTS = [
    DJANGO_CORE / "core" / "migrations",
    DJANGO_CORE / "authentication" / "migrations",
]

# Django's auto-generated index/constraint names always end with a hex hash
# segment (>= 6 hex chars), e.g. crm_lead_company_9a1b2c_idx. A name without
# any such segment is hand-written and must match models.py verbatim.
_HASH_SEGMENT_RE = re.compile(r"_[0-9a-f]{6,}(_idx|_uniq)?$")


def _iter_migration_files():
    roots = list(MIGRATION_ROOTS)
    if APPS_DIR.is_dir():
        for app_dir in sorted(APPS_DIR.iterdir()):
            mig = app_dir / "migrations"
            if mig.is_dir():
                roots.append(mig)
    for root in roots:
        if not root.is_dir():
            continue
        for path in sorted(root.glob("*.py")):
            if path.name != "__init__.py":
                yield path


def _model_declared_names():
    """Every explicit ``name='...'`` string declared in a models.py (the set of
    index/constraint names the models currently describe)."""
    names = set()
    files = [DJANGO_CORE / "core" / "models.py",
             DJANGO_CORE / "authentication" / "models.py"]
    if APPS_DIR.is_dir():
        for app_dir in sorted(APPS_DIR.iterdir()):
            m = app_dir / "models.py"
            if m.is_file():
                files.append(m)
    for f in files:
        if not f.is_file():
            continue
        try:
            tree = ast.parse(f.read_text(encoding="utf-8"))
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                nm = _kwarg(node, "name")
                if isinstance(nm, ast.Constant) and isinstance(nm.value, str):
                    names.add(nm.value)
    return names


def _rel(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT)).replace("\\", "/")
    except ValueError:
        return path.name


def _load_allowlist():
    if not ALLOWLIST_PATH.exists():
        return set()
    out = set()
    for line in ALLOWLIST_PATH.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            out.add(line)
    return out


def _call_name(node):
    f = node.func
    if isinstance(f, ast.Name):
        return f.id
    if isinstance(f, ast.Attribute):
        return f.attr
    return None


def _kwarg(call, name):
    for kw in call.keywords:
        if kw.arg == name:
            return kw.value
    return None


def _is_true(node):
    return isinstance(node, ast.Constant) and node.value is True


def _is_false(node):
    return isinstance(node, ast.Constant) and node.value is False


def _find_operations(tree):
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            targets = [t.id for t in node.targets if isinstance(t, ast.Name)]
            if "operations" in targets and isinstance(node.value, ast.List):
                return node.value.elts
    return []


def _models_created(operations):
    created = set()
    for op in operations:
        if isinstance(op, ast.Call) and _call_name(op) == "CreateModel":
            nm = _kwarg(op, "name")
            if isinstance(nm, ast.Constant) and isinstance(nm.value, str):
                created.add(nm.value.lower())
    return created


def _string_names_in(call):
    """All string ``name=`` kwargs in the call and any nested Index/Constraint
    constructors (AddIndex(index=models.Index(name='...'))/AddConstraint(...))."""
    names = []
    for sub in ast.walk(call):
        if isinstance(sub, ast.Call):
            nm = _kwarg(sub, "name")
            if isinstance(nm, ast.Constant) and isinstance(nm.value, str):
                names.append(nm.value)
    return names


def check_file(path: Path, model_names=frozenset()):
    """Return list of (code, message)."""
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except SyntaxError as exc:
        return [("PARSE_ERROR", f"could not parse: {exc}")]

    findings = []
    operations = _find_operations(tree)
    created = _models_created(operations)

    for op in operations:
        if not isinstance(op, ast.Call):
            continue
        name = _call_name(op)

        # (a) AddField adding a hard constraint on a possibly-populated table.
        if name == "AddField":
            model_kw = _kwarg(op, "model_name")
            model = model_kw.value.lower() if isinstance(model_kw, ast.Constant) else None
            on_new_table = model in created
            field_kw = _kwarg(op, "field")
            unique = null_false = has_default = False
            if isinstance(field_kw, ast.Call):
                u = _kwarg(field_kw, "unique")
                n = _kwarg(field_kw, "null")
                d = _kwarg(field_kw, "default")
                unique = u is not None and _is_true(u)
                null_false = n is not None and _is_false(n)
                has_default = d is not None
            if not on_new_table and unique:
                findings.append((
                    "ADDFIELD_UNIQUE_ONESHOT",
                    "AddField(unique=True) on a pre-existing table — use a "
                    "3-step migration (nullable add -> RunPython backfill of "
                    "distinct values -> AlterField(unique=True)).",
                ))
            if not on_new_table and null_false and has_default:
                findings.append((
                    "ADDFIELD_NOT_NULL_ONESHOT",
                    "AddField(null=False, default=...) on a pre-existing table "
                    "— use a 3-step migration (nullable add -> backfill -> "
                    "AlterField(null=False)).",
                ))

        # (b) index/constraint name not in models.py and not a Django hash →
        #     model<->migration name drift.
        if name in ("AddIndex", "AddConstraint", "RenameIndex"):
            for nm in _string_names_in(op):
                if _HASH_SEGMENT_RE.search(nm) or nm in model_names:
                    continue
                findings.append((
                    "INDEX_NAME_DRIFT",
                    f"{name} names '{nm}', which is neither a Django-hash name "
                    "nor declared in any models.py Meta — the models no longer "
                    "describe this index/constraint under that name "
                    "(makemigrations 'changes not reflected' drift). Mirror "
                    "the name in models.py Meta or use RenameIndex.",
                ))

    return findings


def main(argv):
    list_mode = "--list" in argv
    allow = _load_allowlist()
    model_names = _model_declared_names()
    offenders = []
    listed = []
    for path in _iter_migration_files():
        rel = _rel(path)
        for code, msg in check_file(path, model_names):
            listed.append(f"{rel}: [{code}] {msg}")
            if rel not in allow:
                offenders.append(f"{rel}: [{code}] {msg}")

    if list_mode:
        for line in listed:
            print(line)
        return 0

    if offenders:
        print("check_migration_safety: unsafe/ambiguous migration(s) "
              "(not in scripts/migration_safety_allow.txt):")
        for line in offenders:
            print(f"  - {line}")
        print(
            "\nSplit a constraint-on-populated-table into a 3-step migration, "
            "and let Django name indexes/constraints (or mirror the explicit "
            "name verbatim in models.py Meta). A REVIEWED historical migration "
            "may be added to scripts/migration_safety_allow.txt."
        )
        return 1

    print("check_migration_safety: OK — no unsafe migration outside the "
          "allowlist.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
