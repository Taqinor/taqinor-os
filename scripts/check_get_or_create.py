"""YDATA15 — advisory sweep: `get_or_create`/`update_or_create` lookup keys
should be backed by a `UniqueConstraint` (Django's documented race).

DB-free, AST-only (mirrors ``scripts/check_on_delete.py``). Scans every
``apps/*/*.py`` (migrations/tests excluded) for a
``.get_or_create(...)``/``.update_or_create(...)`` call and lists, per call
site, its LOOKUP keyword arguments (everything except ``defaults=``) — the
keys that SHOULD correspond to a company-scoped ``UniqueConstraint``/
``unique_together`` on the target model to make the call race-safe.

v1 = ADVISORY (per spec): this does not verify the constraint actually
exists (that would need real model introspection via a live Django app
registry, out of scope for a DB-free AST sweep) and does not fix anything —
it produces ``docs/get-or-create-audit.md`` (file:line, lookup keys) for
human review. The committed doc IS the baseline (same pattern as
``check_on_delete.py --financial``): a call site already recorded there
passes; a NEW site not yet recorded fails CI (forces the reviewer to look
at whether the target model needs a constraint before merging).

Usage:
    python scripts/check_get_or_create.py
"""
from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DJANGO_CORE = ROOT / "backend" / "django_core"
APPS_DIR = DJANGO_CORE / "apps"
AUDIT_DOC = ROOT / "docs" / "get-or-create-audit.md"

CALL_NAMES = {"get_or_create", "update_or_create"}


def _iter_source_files():
    if not APPS_DIR.is_dir():
        return
    for app_dir in sorted(APPS_DIR.iterdir()):
        if not app_dir.is_dir():
            continue
        for path in sorted(app_dir.rglob("*.py")):
            rel_parts = path.relative_to(app_dir).parts
            if "migrations" in rel_parts:
                continue
            name = path.name
            if re.match(r"^tests?(_.*)?\.py$", name) \
                    or name.endswith("_test.py") or "tests" in rel_parts:
                continue
            yield path


def _rel(path: Path) -> str:
    return str(path.relative_to(ROOT)).replace("\\", "/")


def _lookup_keys(node):
    """Keyword arg names of the call, excluding 'defaults'."""
    return sorted(kw.arg for kw in node.keywords
                  if kw.arg and kw.arg != "defaults")


def _call_target_repr(node):
    """Best-effort textual form of the receiver, e.g. 'Devis.objects' or
    'self.queryset'."""
    try:
        return ast.unparse(node.func.value)
    except Exception:
        return "?"


def check_file(path: Path):
    source = path.read_text(encoding="utf-8")
    try:
        tree = ast.parse(source, filename=str(path))
    except SyntaxError:
        return []

    rows = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if not isinstance(node.func, ast.Attribute):
            continue
        if node.func.attr not in CALL_NAMES:
            continue
        receiver = _call_target_repr(node)
        keys = _lookup_keys(node)
        rows.append((_rel(path), node.lineno, node.func.attr, receiver, keys))
    return rows


def _load_baseline():
    if not AUDIT_DOC.exists():
        return set()
    out = set()
    for line in AUDIT_DOC.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line.startswith("| `"):
            continue
        key = line.split("`", 2)[1]
        out.add(key)
    return out


def _write_audit_doc(rows):
    lines = [
        "# Audit get_or_create / update_or_create (YDATA15)",
        "",
        "Généré par `python scripts/check_get_or_create.py`. Chaque appel "
        "liste ses clés de lookup (hors `defaults`) — chaque clé PARTAGÉE "
        "devrait correspondre à une `UniqueConstraint`/`unique_together` "
        "company-scopée sur le modèle cible pour être course-safe. Advisory : "
        "ce sweep ne corrige rien (correctifs = ERROR_PLAN).",
        "",
        "| Fichier:ligne | Appel | Récepteur | Clés de lookup |",
        "|---|---|---|---|",
    ]
    for rel, lineno, call, receiver, keys in sorted(rows):
        lines.append(
            f"| `{rel}:{lineno}` | {call} | {receiver} | {', '.join(keys)} |")
    AUDIT_DOC.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main(argv):
    baseline = _load_baseline()

    all_rows = []
    for path in _iter_source_files():
        all_rows.extend(check_file(path))

    print(f"check_get_or_create: {len(all_rows)} get_or_create/"
          "update_or_create call(s) found.")
    for rel, lineno, call, receiver, keys in all_rows:
        print(f"  {rel}:{lineno}  {receiver}.{call}({', '.join(keys)})")

    findings = []
    for rel, lineno, call, receiver, keys in all_rows:
        key = f"{rel}:{lineno}"
        if key not in baseline:
            findings.append(
                f"{key}: NEW {call}({', '.join(keys)}) on {receiver} — "
                "review whether the target model has a matching "
                "UniqueConstraint, then commit the regenerated "
                "docs/get-or-create-audit.md.")

    _write_audit_doc(all_rows)
    print(f"\ncheck_get_or_create: wrote {_rel(AUDIT_DOC)}")

    if findings:
        print("\ncheck_get_or_create: violation(s) found:")
        for line in findings:
            print(f"  - {line}")
        return 1

    print("\ncheck_get_or_create: OK.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
