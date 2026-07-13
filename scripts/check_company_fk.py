"""YDATA4 — CI guard: every business-app model carries a `company` scope.

DB-free, AST-only (mirrors ``scripts/check_on_delete.py``): scans MODEL
source files (``apps/*/models*.py``) across the BUSINESS apps (everything
under ``apps/`` except the small foundation set — ``roles``, ``records``,
``parametres``, ``customfields`` — plus the top-level ``authentication``/
``core`` apps, which are foundation and out of scope here) and verifies that
every concrete ``models.Model`` subclass either:

  (a) declares its own ``company`` ForeignKey/OneToOneField, or
  (b) inherits ``core.models.TenantModel`` (by base-class name — the
      abstract mixin that carries ``company``), or
  (c) declares a ForeignKey/OneToOneField to ANOTHER model (in the same file
      or a different app) that itself qualifies under (a)/(b)/(c) —
      resolved by fixed-point iteration, so a line-item model like
      ``LigneDevis`` (FK'd to ``Devis``, which HAS company) is not required
      to repeat the FK itself.

A model that fails all three is a finding UNLESS it is listed by name in
``scripts/tenant_exempt_models.txt`` (one ``app.Model`` per line — global/
foundation-shaped models: singleton config, token/hash tables, pure
many-to-many "through" tables with no business fields of their own, etc.;
generated once from the current repo state so this v1 heuristic — a purely
syntactic sweep, no Django app registry — does not block on any case its
AST resolution cannot prove).

Usage:
    python scripts/check_company_fk.py
"""
from __future__ import annotations

import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DJANGO_CORE = ROOT / "backend" / "django_core"
APPS_DIR = DJANGO_CORE / "apps"
EXEMPT_PATH = ROOT / "scripts" / "tenant_exempt_models.txt"

# Foundation apps under apps/ that are intentionally out of scope (never
# scanned — not even for exemption bookkeeping): they are the base layer,
# not "business apps needing a company scope".
FOUNDATION_APPS = {"roles", "records", "parametres", "customfields"}

FK_CALL_NAMES = {"ForeignKey", "OneToOneField"}
COMPANY_MIXIN_BASES = {"TenantModel"}
# Recognized Django-model base names (last dotted component). A ClassDef
# whose base chain does not resolve — directly, or transitively through
# another class defined in the SAME file — to one of these is NOT a model
# (e.g. `models.TextChoices` enums, plain `Exception` subclasses that also
# live in models*.py files in this repo) and is skipped entirely: it needs
# no company scope because it is not a table.
MODEL_BASE_SEED = {
    "Model", "TenantModel", "TimestampedModel", "SoftDeleteModel",
    "AbstractUser", "AbstractBaseUser",
}


def _iter_model_files():
    if not APPS_DIR.is_dir():
        return
    for app_dir in sorted(APPS_DIR.iterdir()):
        if not app_dir.is_dir() or app_dir.name in FOUNDATION_APPS:
            continue
        for path in sorted(app_dir.glob("models*.py")):
            yield app_dir.name, path
        models_pkg = app_dir / "models"
        if models_pkg.is_dir():
            for path in sorted(models_pkg.glob("*.py")):
                if path.name != "__init__.py":
                    yield app_dir.name, path


def _rel(path: Path) -> str:
    return str(path.relative_to(ROOT)).replace("\\", "/")


def _load_exempt():
    if not EXEMPT_PATH.exists():
        return set()
    out = set()
    for line in EXEMPT_PATH.read_text(encoding="utf-8").splitlines():
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


def _base_names(classdef):
    names = []
    for base in classdef.bases:
        if isinstance(base, ast.Name):
            names.append(base.id)
        elif isinstance(base, ast.Attribute):
            names.append(base.attr)
    return names


def _target_model_key(app_label, target_repr):
    """Resolve a FK target string/expr to an ``app.Model`` key. A bare
    ``'Devis'`` or ``Devis`` resolves to the CURRENT file's app; a dotted
    ``'ventes.Devis'``/``ventes.models.Devis`` resolves explicitly. ``self``
    resolves to a marker handled by the caller."""
    if "." in target_repr:
        parts = target_repr.split(".")
        return f"{parts[0]}.{parts[-1]}"
    return f"{app_label}.{target_repr}"


def _target_repr(node):
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


def _collect_file(app_label, path):
    """Returns a dict {model_key: {'bases': [...], 'fk_targets': [key,...],
    'has_direct_company': bool, 'lineno': int}} for every top-level ClassDef
    in this file resolved (via MODEL_BASE_SEED, transitively within the
    file) to be an actual Django model — never a TextChoices enum or a
    plain Exception subclass, both of which also live in models*.py here."""
    source = path.read_text(encoding="utf-8")
    try:
        tree = ast.parse(source, filename=str(path))
    except SyntaxError:
        return {}

    classdefs = [n for n in tree.body if isinstance(n, ast.ClassDef)
                 and n.name != "Meta"]
    bases_by_name = {n.name: _base_names(n) for n in classdefs}

    # Intra-file fixed point: a class IS a Django model if any of its bases
    # is a recognized model base, or transitively resolves (within this same
    # file) to a class that is. Cross-file abstract bases not in
    # MODEL_BASE_SEED (rare in this codebase) are not resolved — v1 limit.
    is_model = {name: any(b in MODEL_BASE_SEED for b in bases)
                for name, bases in bases_by_name.items()}
    changed = True
    while changed:
        changed = False
        for name, bases in bases_by_name.items():
            if is_model[name]:
                continue
            if any(is_model.get(b) for b in bases):
                is_model[name] = True
                changed = True

    out = {}
    for node in classdefs:
        if not is_model.get(node.name):
            continue
        bases = _base_names(node)
        model_key = f"{app_label}.{node.name}"
        fk_targets = []
        has_direct_company = False
        for stmt in ast.walk(node):
            if isinstance(stmt, ast.Assign):
                target = stmt.targets[0] if stmt.targets else None
                value = stmt.value
            elif isinstance(stmt, ast.AnnAssign):
                target = stmt.target
                value = stmt.value
            else:
                continue
            if not isinstance(target, ast.Name) or not isinstance(value, ast.Call):
                continue
            if _call_name(value) not in FK_CALL_NAMES:
                continue
            target_repr = _target_repr(value)
            if target.id == "company":
                has_direct_company = True
            if target_repr != "self":
                fk_targets.append(_target_model_key(app_label, target_repr))
        out[model_key] = {
            "bases": bases,
            "fk_targets": fk_targets,
            "has_direct_company": has_direct_company,
            "lineno": node.lineno,
            "file": _rel(path),
        }
    return out


def build_model_graph():
    graph = {}
    for app_label, path in _iter_model_files():
        graph.update(_collect_file(app_label, path))
    return graph


def resolve_has_company(graph):
    """Fixed-point iteration: a model has company directly, via a
    TenantModel base, or via any FK target that (transitively) has one."""
    has_company = {
        key: (info["has_direct_company"]
              or any(b in COMPANY_MIXIN_BASES for b in info["bases"]))
        for key, info in graph.items()
    }
    changed = True
    while changed:
        changed = False
        for key, info in graph.items():
            if has_company.get(key):
                continue
            for target_key in info["fk_targets"]:
                if has_company.get(target_key):
                    has_company[key] = True
                    changed = True
                    break
    return has_company


def main(argv):
    exempt = _load_exempt()
    graph = build_model_graph()
    has_company = resolve_has_company(graph)

    findings = []
    print(f"check_company_fk: scanned {len(graph)} model(s) across business apps.")
    for key in sorted(graph):
        info = graph[key]
        ok = has_company.get(key, False)
        status = "OK" if ok else "MISSING"
        if not ok and key in exempt:
            status = "EXEMPT"
        print(f"  {info['file']}:{info['lineno']}  {key}  [{status}]")
        if not ok and key not in exempt:
            findings.append(
                f"{info['file']}:{info['lineno']}: {key} has no company "
                "scope (no direct FK, no TenantModel base, no FK to a "
                "model that has one) and is not in "
                "scripts/tenant_exempt_models.txt.")

    if findings:
        print("\ncheck_company_fk: violation(s) found:")
        for line in findings:
            print(f"  - {line}")
        print(
            "\nFix by adding a `company` FK (or a FK to a company-scoped "
            "model), inheriting core.models.TenantModel, or — if this is "
            "genuinely a foundation/global model — add its 'app.Model' key "
            "to scripts/tenant_exempt_models.txt after review."
        )
        return 1

    print("\ncheck_company_fk: OK — every business model is company-scoped "
          "(directly, transitively, or exempted).")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
