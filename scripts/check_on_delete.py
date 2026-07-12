"""YDATA1 — CI guard: every ForeignKey/OneToOneField declares `on_delete`
explicitly, and every `CASCADE` is justified.

DB-free, AST-only (mirrors ``scripts/check_safe_migrations.py``/
``check_query_budgets.py``): scans MODEL source files
(``backend/django_core/apps/*/models*.py`` + ``core/models.py`` +
``authentication/models.py``) — never migrations, never a live DB.

For every ``models.ForeignKey(...)``/``models.OneToOneField(...)`` (or the
bare ``ForeignKey(...)``/``OneToOneField(...)`` form after
``from django.db import models`` / ``from django.db.models import
ForeignKey``) call found in a class body:

  (a) missing ``on_delete=`` kwarg entirely -> always a finding (Django
      itself requires it at import time, but a future refactor pattern —
      e.g. building the field via a helper/partial — could hide it from a
      naive grep; the AST walk here looks at the literal call site).
  (b) ``on_delete=models.CASCADE`` (or bare ``CASCADE``) present but with
      NO inline ``# on_delete: <reason>`` comment on the same or an
      adjacent line, AND the field is not already listed in
      ``scripts/on_delete_allowlist.txt`` (one ``path:lineno`` per line,
      generated once from the current repo state so this guard does not
      block on the ~1300 pre-existing FKs).

Prints an auditable table (file:line, model, field, target, policy) of
EVERY FK/O2O found, then fails (non-zero exit) only on a NEW violation
(missing on_delete, or an un-justified/un-allowlisted CASCADE).

Usage:
    python scripts/check_on_delete.py            # check the whole repo
    python scripts/check_on_delete.py --check     # same, explicit (CI)
"""
from __future__ import annotations

import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DJANGO_CORE = ROOT / "backend" / "django_core"
ALLOWLIST_PATH = ROOT / "scripts" / "on_delete_allowlist.txt"

FK_CALL_NAMES = {"ForeignKey", "OneToOneField"}


def _iter_model_files():
    apps_dir = DJANGO_CORE / "apps"
    if apps_dir.is_dir():
        for app_dir in sorted(apps_dir.iterdir()):
            if not app_dir.is_dir():
                continue
            for path in sorted(app_dir.glob("models*.py")):
                yield path
            models_pkg = app_dir / "models"
            if models_pkg.is_dir():
                for path in sorted(models_pkg.glob("*.py")):
                    if path.name != "__init__.py":
                        yield path
    for extra in (DJANGO_CORE / "core" / "models.py",
                  DJANGO_CORE / "authentication" / "models.py"):
        if extra.exists():
            yield extra


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


def _call_name(node):
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


def _on_delete_repr(value):
    """Best-effort textual form of the on_delete= value, e.g. 'CASCADE'."""
    if isinstance(value, ast.Attribute):
        return value.attr
    if isinstance(value, ast.Name):
        return value.id
    if isinstance(value, ast.Call):
        return _call_name(value) or "?"
    return "?"


def _target_repr(node):
    """First positional arg (the FK target), best-effort."""
    if not node.args:
        return "?"
    arg = node.args[0]
    if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
        return arg.value
    if isinstance(arg, ast.Attribute):
        parts = []
        cur = arg
        while isinstance(cur, ast.Attribute):
            parts.append(cur.attr)
            cur = cur.value
        if isinstance(cur, ast.Name):
            parts.append(cur.id)
        return ".".join(reversed(parts))
    if isinstance(arg, ast.Name):
        return arg.id
    return "?"


def _enclosing_class(node, tree):
    """Name of the nearest enclosing ClassDef for `node`, walking the tree."""
    best = None
    for candidate in ast.walk(tree):
        if isinstance(candidate, ast.ClassDef):
            for child in ast.walk(candidate):
                if child is node:
                    best = candidate.name
    return best or "?"


def _has_justification_comment(source_lines, lineno):
    """A `# on_delete: <reason>` comment on the field's own line or within
    the following 2 lines (call args often span multiple lines)."""
    for offset in range(0, 3):
        idx = lineno - 1 + offset
        if 0 <= idx < len(source_lines) and "# on_delete:" in source_lines[idx]:
            return True
    return False


def check_file(path: Path):
    """Returns (all_rows, findings). all_rows = every FK/O2O (audit table).
    findings = (code, message) for violations only."""
    source = path.read_text(encoding="utf-8")
    lines = source.splitlines()
    try:
        tree = ast.parse(source, filename=str(path))
    except SyntaxError as exc:
        return [], [("PARSE_ERROR", f"could not parse: {exc}")]

    all_rows = []
    findings = []

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        name = _call_name(node)
        if name not in FK_CALL_NAMES:
            continue

        model = _enclosing_class(node, tree)
        target = _target_repr(node)
        lineno = node.lineno
        on_delete_kw = _kwarg(node, "on_delete")

        if on_delete_kw is None:
            policy = "MISSING"
            findings.append((
                "MISSING_ON_DELETE",
                f"{model}.<field> (-> {target}) at line {lineno}: "
                "ForeignKey/OneToOneField without an explicit on_delete=.",
            ))
        else:
            policy = _on_delete_repr(on_delete_kw)
            if policy == "CASCADE":
                justified = _has_justification_comment(lines, lineno)
                allow_key = f"{_rel(path)}:{lineno}"
                if not justified and allow_key not in _ALLOW_CACHE:
                    findings.append((
                        "UNJUSTIFIED_CASCADE",
                        f"{model}.<field> (-> {target}) at line {lineno}: "
                        "on_delete=CASCADE with no inline "
                        "'# on_delete: <reason>' comment and not in "
                        "scripts/on_delete_allowlist.txt.",
                    ))

        all_rows.append((_rel(path), lineno, model, target, policy))

    return all_rows, findings


_ALLOW_CACHE = set()


def main(argv):
    global _ALLOW_CACHE
    _ALLOW_CACHE = _load_allowlist()

    all_rows = []
    report_lines = []

    for path in _iter_model_files():
        rows, findings = check_file(path)
        all_rows.extend(rows)
        for code, message in findings:
            report_lines.append(f"{_rel(path)}: [{code}] {message}")

    print(f"check_on_delete: scanned {len(all_rows)} ForeignKey/OneToOneField "
          f"declaration(s) across {DJANGO_CORE.name}/apps + core + "
          "authentication.")
    print("file:line  model.field -> target  [policy]")
    for rel, lineno, model, target, policy in all_rows:
        print(f"  {rel}:{lineno}  {model} -> {target}  [{policy}]")

    if report_lines:
        print("\ncheck_on_delete: violation(s) found:")
        for line in report_lines:
            print(f"  - {line}")
        print(
            "\nFix by adding on_delete= (required), or for a NEW CASCADE add "
            "an inline '# on_delete: <reason>' comment, or list the "
            "file:line in scripts/on_delete_allowlist.txt if it is a "
            "reviewed historical CASCADE."
        )
        return 1

    print("\ncheck_on_delete: OK — no unjustified/missing on_delete found.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
