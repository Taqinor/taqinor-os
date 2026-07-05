"""CI guard: every invariant in docs/invariants.md still has its test (YTEST16).

docs/invariants.md lists critical business invariants, each pinned to a
``file::Class::test_method`` reference. This script parses those references
and fails the build if any of them no longer resolves — i.e. the guarding
test was renamed, moved, or deleted without updating the registry. It is a
static (regex/AST) check: it does NOT run the tests, just confirms they
still exist, so it stays fast and dependency-free (same style as
scripts/check_stages.py).
"""
from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
INVARIANTS_FILE = ROOT / "docs" / "invariants.md"
BACKEND_ROOT = ROOT / "backend" / "django_core"

# `` `path/to/file.py::ClassName::test_method` ``
REFERENCE_RE = re.compile(r"`([\w./-]+\.py)::(\w+)::(\w+)`")


def _find_method_in_class(tree: ast.Module, class_name: str, method_name: str) -> bool:
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == class_name:
            for child in node.body:
                if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)) and child.name == method_name:
                    return True
    return False


def main() -> int:
    if not INVARIANTS_FILE.exists():
        print("docs/invariants.md not found — nothing to check.")
        return 0

    text = INVARIANTS_FILE.read_text(encoding="utf-8")
    references = REFERENCE_RE.findall(text)
    if not references:
        sys.exit("docs/invariants.md has no parseable `file.py::Class::test` references.")

    failures: list[str] = []
    for rel_path, class_name, method_name in references:
        full_path = BACKEND_ROOT / rel_path
        ref = f"{rel_path}::{class_name}::{method_name}"
        if not full_path.exists():
            failures.append(f"{ref} — file not found ({full_path})")
            continue
        try:
            tree = ast.parse(full_path.read_text(encoding="utf-8"), filename=str(full_path))
        except SyntaxError as exc:
            failures.append(f"{ref} — could not parse {full_path}: {exc}")
            continue
        if not _find_method_in_class(tree, class_name, method_name):
            failures.append(
                f"{ref} — {class_name}.{method_name} not found in {rel_path} "
                f"(renamed/removed without updating docs/invariants.md?)"
            )

    if failures:
        print(f"Invariant registry drift ({len(failures)} broken reference(s)):")
        for failure in failures:
            print(f"  - {failure}")
        return 1

    print(f"Invariant registry OK — {len(references)} reference(s) resolve to a real test.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
