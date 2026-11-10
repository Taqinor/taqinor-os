"""YDATA21 — CI guard: multi-tenant isolation on business-app viewsets.

Every business ``ModelViewSet``/``Generic*APIView`` must (a) scope its queryset
to the tenant — inherit a company-scoping base (``TenantMixin`` /
``CompanyScopedModelViewSet`` …) OR define a ``get_queryset`` that filters by
``company``/``request.user.company`` — and (b) never let ``company`` be set from
the request body: ``perform_create``/``perform_update`` must not read
``company`` from ``serializer.validated_data``/``request.data`` (it must be
force-assigned server-side), and an associated serializer must not list
``company`` as a writable field.

DB-free AST sweep over ``backend/django_core/{apps/*,core,authentication}/
{views.py,views_*.py,*_views.py,views/*.py}`` (mirrors
``core/object_scope_scan.py``) and the matching serializer surface
(``{serializers.py,serializers_*.py,*_serializers.py,serializers/*.py}``).

AUD828 (M-07) — before this fix the view scan matched ONLY the ``*_views.py``
SUFFIX, missing 26 ``views_*.py`` PREFIX files (``authentication/
views_console.py``, ``ao/views_qualification.py``…) and both ``core`` and
``authentication`` entirely; the serializer scan matched only bare
``serializers.py`` + a ``serializers/`` package, missing 17
``serializers_*.py`` files. Widening the surface to its full declared shape
found 0 NEW live violation on the current tree (a structural coverage gap,
not a proven leak) — ``core``/``authentication`` foundation views that are
legitimately unscoped stay covered by
``scripts/tenant_view_allowlist.txt`` like any other reviewed exemption.

APFS64 — the sweep also reads every ``@api_view`` FUNCTION (292 of them
were never opened) and demands an EFFECTIVE company filter: a ``company*``
keyword (or a COMPANY_TOKENS keyword) passed to a call, or a scoping call
(``company_qs``, ``scope_queryset``…) — the word « company » cited in a
condition or a branch no longer counts. The sites found on 09/11/2026 are a
FROZEN debt (``DETTE_FILTRE_EFFECTIF``, ``path::symbol``) that only shrinks:
a key without a site fails the guard.

v1: foundation/public views already reviewed are listed in
``scripts/tenant_view_allowlist.txt`` (``path::ClassName``); a NEW business
view missing the company filter or exposing ``company`` writable fails CI.

Usage:
    python scripts/check_tenant_isolation.py            # check (CI)
    python scripts/check_tenant_isolation.py --list     # list every view + verdict
"""
from __future__ import annotations

import ast
import re
import sys
from pathlib import Path
TYPE_DE_CLE = "par_symbole"  # AMET100 — cle de contenu `fichier::symbole` (jamais un numero de ligne)

ROOT = Path(__file__).resolve().parent.parent
DJANGO_CORE = ROOT / "backend" / "django_core"
APPS_DIR = DJANGO_CORE / "apps"
CORE_DIR = DJANGO_CORE / "core"
AUTH_DIR = DJANGO_CORE / "authentication"
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

APPELS_FILTRANTS = frozenset({"filter", "get", "exclude",
                              "get_object_or_404", "Q"})

#: APFS64 — dette GELÉE (``--list``, 09/11/2026) : ne fait que décroître.
DETTE_FILTRE_EFFECTIF = frozenset({
    "backend/django_core/apps/crm/clients_views.py::lead_playbook_view",
    "backend/django_core/apps/crm/public_booking_views.py::public_booking_reserve",
    "backend/django_core/apps/crm/public_chat_views.py::get_chat_session",
    "backend/django_core/apps/crm/public_views.py::public_apporteur_mes_deals",
    "backend/django_core/apps/crm/public_views.py::public_salle_vente",
    "backend/django_core/apps/ged/views.py::public_signataire",
    "backend/django_core/apps/ged/views.py::public_signataire_document",
    "backend/django_core/apps/ged/views.py::public_signature_document",
    "backend/django_core/apps/notifications/views.py::push_subscribe",
    "backend/django_core/apps/notifications/views.py::push_unsubscribe",
    "backend/django_core/apps/portail/views_externes.py::preference_portail",
    "backend/django_core/apps/reporting/views.py::dashboard",
    "backend/django_core/apps/sav/public_views.py::ticket_public_status",
    "backend/django_core/apps/statuspage/views.py::public_abonner",
    "backend/django_core/apps/statuspage/views.py::public_confirmer_abonnement",
    "backend/django_core/apps/statuspage/views.py::public_desabonner",
    "backend/django_core/apps/ventes/public_views.py::public_bcf_document",
    "backend/django_core/authentication/views.py::CompanyViewSet",
    "backend/django_core/core/views.py::secrets_rotation_due",
    # APFS118 (10/11/2026) — @api_view hors fichiers « vues » ; ne fait que décroître.
    "backend/django_core/apps/reporting/approbations.py::decider_approbation_via_push",
    "backend/django_core/apps/reporting/archive.py::archive_chantier",
    "backend/django_core/apps/reporting/archive.py::archive_client",
    "backend/django_core/apps/reporting/calendar.py::calendar_events",
    "backend/django_core/apps/reporting/calendar.py::calendar_reschedule",
    "backend/django_core/apps/reporting/commercial.py::commercial_dashboard",
    "backend/django_core/apps/reporting/commercial.py::win_loss_by_source",
    "backend/django_core/apps/reporting/geo.py::geo_points",
    "backend/django_core/apps/reporting/insights.py::analytics",
    "backend/django_core/apps/reporting/insights.py::audit_log",
    "backend/django_core/apps/reporting/insights.py::cohorts",
    "backend/django_core/apps/reporting/insights.py::job_costing",
    "backend/django_core/apps/reporting/insights.py::profitability",
    "backend/django_core/apps/reporting/insights.py::recurring_revenue",
    "backend/django_core/apps/reporting/insights.py::sales_leaderboard",
    "backend/django_core/apps/reporting/pipeline.py::funnel_velocity",
    "backend/django_core/apps/reporting/pipeline.py::pipeline",
    "backend/django_core/apps/reporting/reports.py::sales_report",
    "backend/django_core/apps/reporting/reports.py::service_report",
    "backend/django_core/apps/reporting/reports.py::stock_report",
    "backend/django_core/apps/reporting/reports_field.py::field_service_report",
    "backend/django_core/apps/reporting/sav_sla.py::sav_sla_insight",
    "backend/django_core/apps/ventes/public/lecture_views.py::proposal_engagement",
    "backend/django_core/apps/ventes/public/signature_views.py::proposal_accept",
    "backend/django_core/core/trust_center.py::trust_center_public",
    # APFS119 (10/11/2026) — mot-clé company hors appel de filtrage ; ne fait que décroître.
    "backend/django_core/apps/adminops/views.py::tracker_usage_view",
    "backend/django_core/apps/audit/views.py::object_as_of",
    "backend/django_core/apps/crm/public_chat_views.py::post_chat_message",
    "backend/django_core/apps/ged/views.py::public_partage",
    "backend/django_core/apps/sav/public_views.py::ticket_public_satisfaction",
    "backend/django_core/core/export_registry.py::declencher_export_reversibilite",
    "backend/django_core/authentication/views.py::UserViewSet",
})


# AUD828 (M-07) — the THREE dispositions the repo actually uses for a
# "views" surface (mirrors check_platform.py's model-file pattern): a bare
# ``views.py``, a split ``views_*.py`` (prefix) or ``*_views.py`` (suffix)
# module, or a ``views/`` package. Exact filename patterns (never a loose
# ``views*.py`` wildcard) so this never accidentally opens ``viewsets.py``
# (a base-class module, not an endpoint module).
_VIEW_FILE_PATTERNS = ("views.py", "views_*.py", "*_views.py")
_SERIALIZER_FILE_PATTERNS = (
    "serializers.py", "serializers_*.py", "*_serializers.py")


def _app_dirs_and_foundation():
    """Every apps/<app> dir PLUS the two foundation dirs (core, authentication)
    — AUD828: these carry real ViewSets/serializers too (authentication/
    views_console.py, core/views.py…) and were entirely unscanned before."""
    dirs = list(sorted(APPS_DIR.iterdir())) if APPS_DIR.is_dir() else []
    return dirs + [CORE_DIR, AUTH_DIR]


def _iter_view_files():
    seen = set()
    for app_dir in _app_dirs_and_foundation():
        if not app_dir.is_dir():
            continue
        for pattern in _VIEW_FILE_PATTERNS:
            for f in sorted(app_dir.glob(pattern)):
                if f not in seen:
                    seen.add(f)
                    yield f
        vpkg = app_dir / "views"
        if vpkg.is_dir():
            for f in sorted(vpkg.glob("*.py")):
                if f.name != "__init__.py" and f not in seen:
                    seen.add(f)
                    yield f


def _iter_fichiers_api_view():
    """APFS118 — tout autre ``*.py`` (hors tests/migrations et hors fichiers
    déjà rendus par ``_iter_view_files``) : seules ses ``@api_view`` sont lues."""
    deja = set(_iter_view_files())
    for app_dir in _app_dirs_and_foundation():
        if not app_dir.is_dir():
            continue
        for f in sorted(app_dir.rglob("*.py")):
            parts = f.relative_to(app_dir).parts
            if f in deja or any(
                    p == "migrations" or p == "tests" or p.startswith("test")
                    for p in parts):
                continue
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


def _nom_appel(call):
    f = call.func
    return f.attr if isinstance(f, ast.Attribute) else getattr(f, "id", "")


def _filtre_effectif(fonction):
    """APFS64 — un filtre société EFFECTIF : mot-clé ``company*`` (ou jeton
    de COMPANY_TOKENS) d'un appel, ou appel de portée (``company_qs``…)."""
    for n in ast.walk(fonction):
        if not isinstance(n, ast.Call):
            continue
        nom = _nom_appel(n)
        # APFS119 — le mot-clé ne compte que sur un appel de filtrage.
        if nom in APPELS_FILTRANTS and any(
                k.arg and any(t in k.arg for t in COMPANY_TOKENS)
                for k in n.keywords):
            return True
        if any(t in nom for t in COMPANY_TOKENS):
            return True
    return False


def _est_api_view(fonction):
    for d in fonction.decorator_list:
        cible = d.func if isinstance(d, ast.Call) else d
        if (cible.attr if isinstance(cible, ast.Attribute)
                else getattr(cible, "id", "")) == "api_view":
            return True
    return False


def _lit_orm(fonction):
    return any(isinstance(n, ast.Attribute) and n.attr == "objects"
               for n in ast.walk(fonction))


def _has_company_scoping(classdef):
    if any(SCOPING_BASE_RE.search(n) for n in _base_names(classdef)):
        return True
    gq = _method(classdef, "get_queryset")
    if gq is not None and _filtre_effectif(gq):
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


def check_view_file(path: Path, fonctions_seules=False):
    """Return (views, findings). views = [(cls, compliant_bool)]."""
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except SyntaxError:
        return [], []
    rel = _rel(path)
    views = []
    findings = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) \
                and _est_api_view(node) and _lit_orm(node):
            scoped = _filtre_effectif(node)
            views.append((node.name, scoped))
            if not scoped:
                findings.append((
                    "API_VIEW_COMPANY_FILTER_MISSING", f"{rel}::{node.name}",
                    f"@api_view {node.name} reads the ORM without an "
                    "effective company filter (company=… / company_qs)."))
        if fonctions_seules or not (
                isinstance(node, ast.ClassDef) and _is_view(node)):
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
    seen = set()
    for app_dir in _app_dirs_and_foundation():
        if not app_dir.is_dir():
            continue
        for pattern in _SERIALIZER_FILE_PATTERNS:
            for f in sorted(app_dir.glob(pattern)):
                if f not in seen:
                    seen.add(f)
                    yield f
        spkg = app_dir / "serializers"
        if spkg.is_dir():
            for f in sorted(spkg.glob("*.py")):
                if f.name != "__init__.py" and f not in seen:
                    seen.add(f)
                    yield f


def fichiers_morts(cles, root=None):
    """ADEP26 — clés d'allowlist dont le fichier n'existe plus (app sortie
    du périmètre) : une ligne morte est un faux acquis, la garde la refuse."""
    root = ROOT if root is None else root
    morts = []
    for cle in sorted(cles):
        chemin = cle.split("#")[0].split("|")[0].split("::")[0].strip()
        if chemin and not (root / chemin).exists():
            morts.append(cle)
    return morts


def _morts_offenders(cles):
    return [f"{c} — ligne d'allowlist morte (fichier absent) : retirez-la"
            for c in fichiers_morts(cles)]


def main(argv):
    list_mode = "--list" in argv
    allow = _load_allowlist()
    all_views = []
    offenders = _morts_offenders(allow)
    dette_vue = set()

    sources = ([(p, False) for p in _iter_view_files()]
               + [(p, True) for p in _iter_fichiers_api_view()])
    for path, seules in sources:
        rel = _rel(path)
        views, findings = check_view_file(path, fonctions_seules=seules)
        for cls, scoped in views:
            all_views.append(f"{rel}::{cls} scoped={scoped}")
        for code, key, msg in findings:
            all_views.append(f"{key} [{code}]")
            if key in DETTE_FILTRE_EFFECTIF:
                dette_vue.add(key)
            if key in allow or key in DETTE_FILTRE_EFFECTIF:
                continue
            offenders.append(f"[{code}] {key}: {msg}")
    offenders += [f"[DETTE_MORTE] {k}: site corrigé ou disparu — retirez la "
                  "clé de DETTE_FILTRE_EFFECTIF (la dette ne fait que décroître)"
                  for k in sorted(DETTE_FILTRE_EFFECTIF - dette_vue)]

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
