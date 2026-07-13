"""YDATA21 — CI guard: multi-tenant isolation on business-app viewsets.

Every business ``ModelViewSet``/``Generic*APIView`` must (a) scope its queryset
to the tenant — inherit a company-scoping base (``TenantMixin`` /
``CompanyScopedModelViewSet`` …) OR define a ``get_queryset`` that filters by
``company``/``request.user.company`` — and (b) never let ``company`` be set from
the request body: ``perform_create``/``perform_update`` must not read
``company`` from ``serializer.validated_data``/``request.data`` (it must be
force-assigned server-side), and an associated serializer must not list
``company`` as a writable field.

DB-free AST sweep over ``backend/django_core/apps/*/{views.py,views/*.py,
*_views.py}`` (mirrors ``core/object_scope_scan.py``). ``core`` /
``authentication`` (foundation) are out of scope by path. v1: foundation/public
views already reviewed are listed in ``scripts/tenant_view_allowlist.txt``
(``path::ClassName``); a NEW business view missing the company filter or
exposing ``company`` writable fails CI.

Usage:
    python scripts/check_tenant_isolation.py            # check (CI)
    python scripts/check_tenant_isolation.py --list     # list every view + verdict
"""
from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DJANGO_CORE = ROOT / "backend" / "django_core"
APPS_DIR = DJANGO_CORE / "apps"
ALLOWLIST_PATH = ROOT / "scripts" / "tenant_view_allowlist.txt"

# A class is a DRF view if a base name ends with these.
VIEW_BASE_RE = re.compile(r"(ViewSet|APIView)$")
# Model-backed views that OWN a queryset and therefore must scope it. A bare
# ``APIView``/``ViewSet`` action endpoint has no queryset to scope and is out of
# the (a) company-filter requirement (spec: ModelViewSet/GenericAPIView).
MODEL_BACKED_RE = re.compile(
    r"(ModelViewSet|GenericViewSet|GenericAPIView"
    r"|(List|Create|Retrieve|Update|Destroy)\w*APIView)$")
# Bases that already guarantee company scoping (by name).
SCOPING_BASE_RE = re.compile(r"(TenantMixin|CompanyScoped|Scoped\w*ViewSet)")
# Tokens in a get_queryset body that prove company/user scoping (a queryset
# scoped to the caller's user is at least as tight as company scoping).
COMPANY_TOKENS = ("company", "scope_queryset", "scope_client_queryset",
                  "get_company_object", "for_user", "_scoped",
                  "employe__user", "visible_user_ids", "subtree_user_ids",
                  "peer_user_ids")


def _iter_view_files():
    if not APPS_DIR.is_dir():
        return
    for app_dir in sorted(APPS_DIR.iterdir()):
        if not app_dir.is_dir():
            continue
        vp = app_dir / "views.py"
        if vp.is_file():
            yield vp
        vpkg = app_dir / "views"
        if vpkg.is_dir():
            for f in sorted(vpkg.glob("*.py")):
                if f.name != "__init__.py":
                    yield f
        for f in sorted(app_dir.glob("*_views.py")):
            yield f


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


def _base_names(classdef):
    names = []
    for b in classdef.bases:
        if isinstance(b, ast.Name):
            names.append(b.id)
        elif isinstance(b, ast.Attribute):
            names.append(b.attr)
    return names


def _is_view(classdef):
    return any(VIEW_BASE_RE.search(n) for n in _base_names(classdef))


def _is_model_backed(classdef):
    return any(MODEL_BACKED_RE.search(n) for n in _base_names(classdef))


def _method(classdef, name):
    for node in classdef.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) \
                and node.name == name:
            return node
    return None


def _has_company_scoping(classdef):
    if any(SCOPING_BASE_RE.search(n) for n in _base_names(classdef)):
        return True
    gq = _method(classdef, "get_queryset")
    if gq is not None:
        src = ast.dump(gq)
        if any(tok in src for tok in COMPANY_TOKENS):
            return True
    # A get_object that scopes by company also counts (detail-only views).
    go = _method(classdef, "get_object")
    if go is not None and "company" in ast.dump(go):
        return True
    return False


def _reads_company_from_body(classdef):
    """True if perform_create/perform_update reads company from the request
    body (validated_data/request.data) — a mass-assignment tenant leak."""
    for mname in ("perform_create", "perform_update"):
        m = _method(classdef, mname)
        if m is None:
            continue
        for sub in ast.walk(m):
            # serializer.validated_data['company'] / .get('company')
            if isinstance(sub, ast.Subscript):
                if _subscript_key(sub) == "company" \
                        and "validated_data" in ast.dump(sub.value):
                    return True
            if isinstance(sub, ast.Call) and isinstance(sub.func, ast.Attribute) \
                    and sub.func.attr == "get":
                if "validated_data" in ast.dump(sub.func.value) \
                        or "request" in ast.dump(sub.func.value):
                    if sub.args and isinstance(sub.args[0], ast.Constant) \
                            and sub.args[0].value == "company":
                        return True
    return False


def _subscript_key(node):
    sl = node.slice
    if isinstance(sl, ast.Constant) and isinstance(sl.value, str):
        return sl.value
    return None


def check_view_file(path: Path):
    """Return (views, findings). views = [(cls, compliant_bool)]."""
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except SyntaxError:
        return [], []
    rel = _rel(path)
    views = []
    findings = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.ClassDef) or not _is_view(node):
            continue
        key = f"{rel}::{node.name}"
        model_backed = _is_model_backed(node)
        scoped = _has_company_scoping(node)
        views.append((node.name, scoped if model_backed else "n/a"))
        if model_backed and not scoped:
            findings.append((
                "COMPANY_FILTER_MISSING", key,
                f"{node.name} is a model-backed business view without a "
                "company-scoping base and without a get_queryset filtering by "
                "request.user.company.",
            ))
        if _reads_company_from_body(node):
            findings.append((
                "COMPANY_FROM_BODY", key,
                f"{node.name} reads 'company' from the request body "
                "(validated_data/request.data) — force-assign it server-side "
                "in perform_create instead.",
            ))
    return views, findings


def serializer_company_writable(path: Path):
    """Findings for serializers explicitly listing 'company' as writable."""
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except SyntaxError:
        return []
    rel = _rel(path)
    findings = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.ClassDef):
            continue
        if not any("Serializer" in n for n in _base_names(node)):
            continue
        # A class-level ``company = serializers.HiddenField(...)`` or any field
        # declared ``read_only=True`` is server-set/safe — never client-writable
        # even when it appears in Meta.fields.
        company_field_safe = False
        for b in node.body:
            if isinstance(b, ast.Assign) and len(b.targets) == 1 \
                    and isinstance(b.targets[0], ast.Name) \
                    and b.targets[0].id == "company" \
                    and isinstance(b.value, ast.Call):
                fn = b.value.func
                fname = fn.attr if isinstance(fn, ast.Attribute) else (
                    fn.id if isinstance(fn, ast.Name) else "")
                if fname == "HiddenField":
                    company_field_safe = True
                for kw in b.value.keywords:
                    if kw.arg == "read_only" and isinstance(kw.value, ast.Constant) \
                            and kw.value.value is True:
                        company_field_safe = True
        if company_field_safe:
            continue
        meta = None
        for b in node.body:
            if isinstance(b, ast.ClassDef) and b.name == "Meta":
                meta = b
        if meta is None:
            continue
        fields, read_only = None, set()
        for stmt in meta.body:
            if not isinstance(stmt, ast.Assign):
                continue
            targets = [t.id for t in stmt.targets if isinstance(t, ast.Name)]
            if "fields" in targets and isinstance(stmt.value, (ast.List, ast.Tuple)):
                fields = [e.value for e in stmt.value.elts
                          if isinstance(e, ast.Constant)]
            if "read_only_fields" in targets:
                if isinstance(stmt.value, (ast.List, ast.Tuple)):
                    read_only = {e.value for e in stmt.value.elts
                                 if isinstance(e, ast.Constant)}
                # read_only_fields = fields  -> the whole serializer is read-only
                elif isinstance(stmt.value, ast.Name) \
                        and stmt.value.id == "fields" and fields:
                    read_only = set(fields)
            # extra_kwargs = {'company': {'read_only': True}}
            if "extra_kwargs" in targets and isinstance(stmt.value, ast.Dict):
                for k, v in zip(stmt.value.keys, stmt.value.values):
                    if isinstance(k, ast.Constant) and k.value == "company" \
                            and isinstance(v, ast.Dict):
                        for ik, iv in zip(v.keys, v.values):
                            if isinstance(ik, ast.Constant) \
                                    and ik.value == "read_only" \
                                    and isinstance(iv, ast.Constant) \
                                    and iv.value is True:
                                read_only.add("company")
        # Also honour a field-level read_only via extra_kwargs is out of scope
        # for v1 (explicit fields list only, low-noise).
        if fields and "company" in fields and "company" not in read_only:
            findings.append((
                "SERIALIZER_COMPANY_WRITABLE", f"{rel}::{node.name}",
                f"{node.name} lists 'company' as a writable field — mark it "
                "read_only or drop it (company is server-assigned).",
            ))
    return findings


def _iter_serializer_files():
    if not APPS_DIR.is_dir():
        return
    for app_dir in sorted(APPS_DIR.iterdir()):
        sp = app_dir / "serializers.py"
        if sp.is_file():
            yield sp
        spkg = app_dir / "serializers"
        if spkg.is_dir():
            for f in sorted(spkg.glob("*.py")):
                if f.name != "__init__.py":
                    yield f


def main(argv):
    list_mode = "--list" in argv
    allow = _load_allowlist()
    all_views = []
    offenders = []

    for path in _iter_view_files():
        rel = _rel(path)
        views, findings = check_view_file(path)
        for cls, scoped in views:
            all_views.append(f"{rel}::{cls} scoped={scoped}")
        for code, key, msg in findings:
            if key in allow:
                continue
            offenders.append(f"[{code}] {key}: {msg}")

    for path in _iter_serializer_files():
        for code, key, msg in serializer_company_writable(path):
            if key in allow:
                continue
            offenders.append(f"[{code}] {key}: {msg}")

    if list_mode:
        for line in sorted(all_views):
            print(line)
        return 0

    if offenders:
        print("check_tenant_isolation: tenant-isolation gap(s) "
              "(not in scripts/tenant_view_allowlist.txt):")
        for line in sorted(offenders):
            print(f"  - {line}")
        print(
            "\nScope the queryset to request.user.company (inherit "
            "core.viewsets.CompanyScopedModelViewSet or override get_queryset) "
            "and force-assign company in perform_create; never expose it in the "
            "serializer or request body. A REVIEWED foundation/public view may "
            "be added to scripts/tenant_view_allowlist.txt."
        )
        return 1

    print("check_tenant_isolation: OK — every business view is company-scoped "
          "or allowlisted.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
