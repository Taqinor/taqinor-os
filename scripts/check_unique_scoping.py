"""YDATA18 — CI guard: unique constraints on tenant data must be company-scoped;
a unique on a soft-delete model must be a partial index.

Two AST checks over ``backend/django_core/apps/*/models.py`` (DB-free, mirrors
``check_company_fk.py`` / ``check_safe_migrations.py``):

  (a) A business field declared ``unique=True`` is a GLOBAL uniqueness — in a
      multi-tenant ERP two companies can legitimately reuse the same reference,
      code, slug… so the uniqueness should be company-scoped via a
      ``UniqueConstraint(fields=['company', <field>], ...)`` (or
      ``unique_together``) instead. Global tokens/hashes (by name:
      ``token`` / ``key_hash`` / ``endpoint`` / ``uuid`` …) are legitimately
      global — allowlisted by name. Existing, human-reviewed sites are
      allowlisted by ``path::Model.field`` in
      ``scripts/unique_scoping_allow.txt``. A NEW business ``unique=True``
      field, not name-allowlisted and not covered by a company-scoped
      constraint, fails CI.

  (b) A model inheriting ``core.SoftDeleteModel`` must give every
      ``UniqueConstraint`` a ``condition=`` excluding the tombstones
      (``Q(is_deleted=False)`` / ``Q(deleted_at__isnull=True)``) — otherwise
      re-creating a "deleted" row collides with the soft-deleted one and fails
      mysteriously.

Usage:
    python scripts/check_unique_scoping.py            # check (CI)
    python scripts/check_unique_scoping.py --list     # list every unique=True site
"""
from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DJANGO_CORE = ROOT / "backend" / "django_core"
APPS_DIR = DJANGO_CORE / "apps"
ALLOWLIST_PATH = ROOT / "scripts" / "unique_scoping_allow.txt"

# Field NAMES that are legitimately globally unique (tokens/hashes/opaque ids),
# never tenant business data — matched as a whole-word substring, case-insens.
GLOBAL_NAME_RE = re.compile(
    r"(token|key_hash|api_key|secret|endpoint|uuid|external_id|"
    r"idempotency|webhook_id|event_id|hash|digest|fingerprint)",
    re.IGNORECASE,
)

SOFT_DELETE_BASE = "SoftDeleteModel"
SOFT_DELETE_CONDITION_MARKERS = ("is_deleted", "deleted_at")


def _iter_models_files():
    if not APPS_DIR.is_dir():
        return
    for app_dir in sorted(APPS_DIR.iterdir()):
        m = app_dir / "models.py"
        if m.is_file():
            yield m


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
        if not line or line.startswith("#"):
            continue
        out.add(line)
    return out


def _base_names(classdef):
    names = set()
    for b in classdef.bases:
        if isinstance(b, ast.Name):
            names.add(b.id)
        elif isinstance(b, ast.Attribute):
            names.add(b.attr)
    return names


def _field_call(value):
    """If ``value`` is a ``models.XField(...)`` call, return the call node."""
    if isinstance(value, ast.Call):
        f = value.func
        name = f.attr if isinstance(f, ast.Attribute) else (
            f.id if isinstance(f, ast.Name) else "")
        if name.endswith("Field"):
            return value
    return None


def _kwarg(call, name):
    for kw in call.keywords:
        if kw.arg == name:
            return kw.value
    return None


def _is_true(node):
    return isinstance(node, ast.Constant) and node.value is True


def _string_elts(node):
    """List of string values from a List/Tuple of string constants."""
    out = []
    if isinstance(node, (ast.List, ast.Tuple)):
        for e in node.elts:
            if isinstance(e, ast.Constant) and isinstance(e.value, str):
                out.append(e.value)
    return out


def _collect_meta(classdef):
    """Return (constraint_field_sets, unique_together_sets, constraint_nodes).

    constraint_field_sets/unique_together_sets are lists of frozenset(field
    names); constraint_nodes are the UniqueConstraint Call nodes (for the
    soft-delete condition check).
    """
    constraint_sets = []
    unique_together = []
    constraint_nodes = []
    for node in classdef.body:
        if not (isinstance(node, ast.ClassDef) and node.name == "Meta"):
            continue
        for stmt in node.body:
            if not isinstance(stmt, ast.Assign):
                continue
            targets = [t.id for t in stmt.targets if isinstance(t, ast.Name)]
            if "constraints" in targets and isinstance(stmt.value, (ast.List, ast.Tuple)):
                for elt in stmt.value.elts:
                    if isinstance(elt, ast.Call):
                        fn = elt.func
                        fname = fn.attr if isinstance(fn, ast.Attribute) else (
                            fn.id if isinstance(fn, ast.Name) else "")
                        if fname == "UniqueConstraint":
                            constraint_nodes.append(elt)
                            fields_kw = _kwarg(elt, "fields")
                            constraint_sets.append(
                                frozenset(_string_elts(fields_kw)))
            if "unique_together" in targets:
                val = stmt.value
                # unique_together can be a tuple of tuples or a single tuple.
                groups = []
                if isinstance(val, (ast.List, ast.Tuple)):
                    if val.elts and isinstance(val.elts[0], (ast.List, ast.Tuple)):
                        groups = val.elts
                    else:
                        groups = [val]
                for g in groups:
                    unique_together.append(frozenset(_string_elts(g)))
    return constraint_sets, unique_together, constraint_nodes


def check_file(path: Path):
    """Return (unique_sites, findings).

    unique_sites: list of (model, field) declared unique=True (for --list).
    findings: list of (code, 'Model.field', message).
    """
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except SyntaxError:
        return [], []

    unique_sites = []
    findings = []
    rel = _rel(path)

    for cls in ast.walk(tree):
        if not isinstance(cls, ast.ClassDef):
            continue
        constraint_sets, unique_together, constraint_nodes = _collect_meta(cls)
        covered_sets = constraint_sets + unique_together
        is_soft_delete = SOFT_DELETE_BASE in _base_names(cls)

        # (a) business unique=True fields.
        for stmt in cls.body:
            if not isinstance(stmt, ast.Assign):
                continue
            if len(stmt.targets) != 1 or not isinstance(stmt.targets[0], ast.Name):
                continue
            fname = stmt.targets[0].id
            call = _field_call(stmt.value)
            if call is None:
                continue
            unique_kw = _kwarg(call, "unique")
            if unique_kw is None or not _is_true(unique_kw):
                continue
            unique_sites.append((cls.name, fname))
            if GLOBAL_NAME_RE.search(fname):
                continue
            key = f"{rel}::{cls.name}.{fname}"
            company_scoped = any(
                {"company", fname} <= s for s in covered_sets)
            if not company_scoped:
                findings.append((
                    "UNIQUE_NOT_COMPANY_SCOPED", key,
                    f"{cls.name}.{fname} is unique=True (globally unique) but "
                    "carries no company-scoped UniqueConstraint/unique_together"
                    " — a multi-tenant business field should scope uniqueness "
                    "to company.",
                ))

        # (b) soft-delete model UniqueConstraints must be partial.
        if is_soft_delete:
            for cnode in constraint_nodes:
                cond = _kwarg(cnode, "condition")
                cond_src = ast.dump(cond) if cond is not None else ""
                if not any(m in cond_src for m in SOFT_DELETE_CONDITION_MARKERS):
                    fields_kw = _kwarg(cnode, "fields")
                    flds = ",".join(_string_elts(fields_kw)) or "?"
                    findings.append((
                        "SOFTDELETE_UNIQUE_NOT_PARTIAL",
                        f"{rel}::{cls.name}({flds})",
                        f"{cls.name} is a SoftDeleteModel but its "
                        f"UniqueConstraint({flds}) has no "
                        "condition=Q(is_deleted=False) — recreating a "
                        "soft-deleted row will collide with the tombstone.",
                    ))

    return unique_sites, findings


def main(argv):
    list_mode = "--list" in argv
    allow = _load_allowlist()
    all_sites = []
    offenders = []
    for path in _iter_models_files():
        rel = _rel(path)
        sites, findings = check_file(path)
        for model, field in sites:
            all_sites.append(f"{rel}::{model}.{field}")
        for code, key, msg in findings:
            if key in allow:
                continue
            offenders.append(f"[{code}] {key}: {msg}")

    if list_mode:
        for line in sorted(all_sites):
            print(line)
        return 0

    if offenders:
        print("check_unique_scoping: unscoped/unsafe unique constraint(s) "
              "(not in scripts/unique_scoping_allow.txt):")
        for line in offenders:
            print(f"  - {line}")
        print(
            "\nScope a business unique to the tenant with "
            "UniqueConstraint(fields=['company', <field>]); on a soft-delete "
            "model add condition=Q(is_deleted=False). If this site is a "
            "reviewed legitimate global unique, add 'path::Model.field' to "
            "scripts/unique_scoping_allow.txt."
        )
        return 1

    print("check_unique_scoping: OK — every business unique is company-scoped "
          "or allowlisted.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
