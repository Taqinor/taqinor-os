"""YOPSB4 — CI guard: blocks dangerous DDL migration patterns before merge.

DB-free, mirrors the spirit of ``scripts/check_stages.py``/``check_modules.py``:
scans migration SOURCE files with the stdlib ``ast`` module (no Django setup,
no database) so it can run in the fast, ungated ``stage-names`` CI job.

Flags, per migration file (``backend/django_core/{apps/*,core,authentication}/
migrations/*.py``):

  (a) ``AddField(..., null=False, default=...)`` — a NOT NULL column with a
      fixed default added directly to a (potentially populated) table,
      without a separate nullable-add -> backfill -> AlterField(not-null)
      3-step migration. The real-prod trap noted in project memory.
  (b) ``RenameField``/``RemoveField`` — silent data loss / rename-in-place
      risk without a human-reviewed companion migration.
  (c) ``AddIndex`` inside a migration that does NOT set ``atomic = False`` —
      a blocking index build on a live table (should use
      ``core.migrations_utils.concurrent_index_migration`` — YOPSB6 — or
      otherwise be reviewed).
  (d) ``RunPython`` whose callable body contains a queryset ``.update(...)``
      call with no visible batching (heuristic: no ``[:`` slice / ``.iterator(``
      / loop variable named batch/chunk nearby) — a global unbatched update.

Each finding is a WARNING unless the migration file is listed in
``scripts/safe_migrations_allow.txt`` (one relative path per line, historical
migrations already merged — silences it entirely), in which case it is
skipped. A NEW migration (not in the allowlist) with ANY finding makes this
script exit non-zero (CI failure); an allowlisted migration is fully exempt.

Usage:
    python scripts/check_safe_migrations.py            # check the whole repo
    python scripts/check_safe_migrations.py --check     # same, explicit (CI)
"""
from __future__ import annotations

import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DJANGO_CORE = ROOT / "backend" / "django_core"
ALLOWLIST_PATH = ROOT / "scripts" / "safe_migrations_allow.txt"

MIGRATION_ROOTS = [
    DJANGO_CORE / "core" / "migrations",
    DJANGO_CORE / "authentication" / "migrations",
]
# All apps/<x>/migrations directories.
APPS_DIR = DJANGO_CORE / "apps"


def _iter_migration_files():
    roots = list(MIGRATION_ROOTS)
    if APPS_DIR.is_dir():
        for app_dir in sorted(APPS_DIR.iterdir()):
            mig_dir = app_dir / "migrations"
            if mig_dir.is_dir():
                roots.append(mig_dir)
    for root in roots:
        if not root.is_dir():
            continue
        for path in sorted(root.glob("*.py")):
            if path.name == "__init__.py":
                continue
            yield path


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


def _rel(path: Path) -> str:
    return str(path.relative_to(ROOT)).replace("\\", "/")


def _call_name(node):
    """Best-effort dotted/bare call name, e.g. 'AddField' or 'migrations.AddField'."""
    func = node.func
    if isinstance(func, ast.Name):
        return func.id
    if isinstance(func, ast.Attribute):
        return func.attr
    return None


def _kwarg(node, name):
    for kw in node.keywords:
        if kw.arg == name:
            return kw.value
    return None


def _is_literal_false(value):
    return isinstance(value, ast.Constant) and value.value is False


def _find_operations_list(tree):
    """Find the `operations = [...]` list assigned inside class Migration."""
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            targets = [t.id for t in node.targets if isinstance(t, ast.Name)]
            if "operations" in targets and isinstance(node.value, ast.List):
                return node.value.elts
    return []


def _module_has_atomic_false(tree):
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            targets = [t.id for t in node.targets if isinstance(t, ast.Name)]
            if "atomic" in targets and _is_literal_false(node.value):
                return True
    return False


def _runpython_looks_unbatched(call_node, source):
    """Heuristic: the RunPython's referenced function (by name, textually
    located in the same file) calls `.update(` without any nearby batching
    marker (`[:`, `.iterator(`, `batch`, `chunk`)."""
    # Best-effort: look at the source text of the whole file for `.update(`
    # not preceded/followed closely by a batching marker. This is a coarse
    # heuristic by design (v1, per YOPSB4 spec) — false negatives are
    # acceptable, false positives are mitigated by the allowlist.
    if ".update(" not in source:
        return False
    batching_markers = (".iterator(", "[:", "batch", "chunk", "Paginator")
    return not any(marker in source for marker in batching_markers)


def _model_names_created_in(operations):
    """Model names (lowercased, as Django stores them) created by a
    CreateModel operation IN THIS SAME migration — an AddIndex/AddField on
    one of these is on a BRAND NEW table, never a populated live one."""
    created = set()
    for op in operations:
        if isinstance(op, ast.Call) and _call_name(op) == "CreateModel":
            name_kw = _kwarg(op, "name")
            if isinstance(name_kw, ast.Constant) and isinstance(name_kw.value, str):
                created.add(name_kw.value.lower())
    return created


def check_file(path: Path):
    """Returns a list of (code, message) findings for one migration file."""
    source = path.read_text(encoding="utf-8")
    try:
        tree = ast.parse(source, filename=str(path))
    except SyntaxError as exc:
        return [("PARSE_ERROR", f"could not parse: {exc}")]

    findings = []
    atomic_false = _module_has_atomic_false(tree)
    operations = _find_operations_list(tree)
    created_models = _model_names_created_in(operations)

    has_runpython_update = _runpython_looks_unbatched(None, source)
    if has_runpython_update:
        findings.append((
            "UNBATCHED_RUNPYTHON_UPDATE",
            "RunPython appears to call a queryset .update(...) without a "
            "visible batching marker (.iterator(/slice/batch/chunk) — a "
            "global unbatched update on a large table can lock for a long "
            "time.",
        ))

    for op in operations:
        if not isinstance(op, ast.Call):
            continue
        name = _call_name(op)

        if name == "AddField":
            default = _kwarg(op, "default")
            null_kw = _kwarg(op, "null")
            is_null_false = (
                null_kw is not None
                and isinstance(null_kw, ast.Constant)
                and null_kw.value is False
            )
            # Inspect the `field=` construct for null=False too (common
            # Django-generated shape: AddField(..., field=models.XField(null=False, default=...))).
            field_kw = _kwarg(op, "field")
            if isinstance(field_kw, ast.Call):
                inner_null = _kwarg(field_kw, "null")
                inner_default = _kwarg(field_kw, "default")
                if inner_null is not None and isinstance(inner_null, ast.Constant) \
                        and inner_null.value is False:
                    is_null_false = True
                if default is None:
                    default = inner_default
            if is_null_false and default is not None:
                findings.append((
                    "ADDFIELD_NOT_NULL_WITH_DEFAULT",
                    "AddField(null=False, default=...) on what may be a "
                    "populated table — prefer a 3-step migration (nullable "
                    "add -> RunPython backfill -> AlterField not-null).",
                ))

        elif name in ("RenameField", "RemoveField"):
            findings.append((
                f"{name.upper()}",
                f"{name} risks silent data loss / a rename-in-place — "
                "confirm a human-reviewed migration plan.",
            ))

        elif name == "AddIndex":
            model_kw = _kwarg(op, "model_name")
            model_name = None
            if isinstance(model_kw, ast.Constant):
                model_name = model_kw.value
            # An index added on a model CREATED in this very migration is a
            # brand-new (empty) table — never a live populated one, so it is
            # never a blocking-lock risk. Only flag AddIndex on a
            # PRE-EXISTING model.
            if model_name not in created_models and not atomic_false:
                findings.append((
                    "ADDINDEX_NOT_CONCURRENT",
                    "AddIndex on a pre-existing model, in a migration "
                    "without `atomic = False`, can hold a blocking write "
                    "lock on a live table — consider "
                    "core.migrations_utils.concurrent_index_migration "
                    "(YOPSB6).",
                ))

    return findings


def main(argv):
    allow = _load_allowlist()
    report_lines = []

    for path in _iter_migration_files():
        rel = _rel(path)
        findings = check_file(path)
        if not findings:
            continue
        if rel in allow:
            continue
        for code, message in findings:
            report_lines.append(f"{rel}: [{code}] {message}")

    if report_lines:
        print("check_safe_migrations: unsafe migration pattern(s) found "
              "(not in scripts/safe_migrations_allow.txt):")
        for line in report_lines:
            print(f"  - {line}")
        print(
            "\nIf this is a REVIEWED historical migration, add its path to "
            "scripts/safe_migrations_allow.txt. A NEW migration must fix the "
            "pattern instead."
        )
        return 1

    print("check_safe_migrations: OK — no unsafe pattern outside the "
          "allowlist.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
