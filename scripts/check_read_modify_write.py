"""YDATA16 — sweep: read-modify-write on shared counters/stock must hold a
lock (``select_for_update()``) or use an atomic ``F()`` expression.

``apps/stock/services.py`` already does the right thing (``select_for_update()``
+ ``F()``), but nothing GUARANTEES a future read-then-save on a shared numeric
field (quantities, aggregate counters, balances) takes a lock. A bare
``x = Model.objects.get(...)`` / ``x.field = x.field ± ...`` / ``x.save()``
under concurrency loses updates (lost-update anomaly).

DB-free, AST-only (mirrors ``scripts/check_get_or_create.py`` /
``check_safe_migrations.py``). Scans every ``{apps/*,core,authentication}/
{services.py,services_*.py,services/*.py}`` and, per function, flags a
read-modify-write pattern:

AUD828 (M-03) — before this fix the scan matched ONLY the bare
``services.py`` file, missing ~20 ``services_*.py`` split files (e.g.
``apps/stock/services_wms.py``) and both ``core``/``authentication``
entirely. A contre-sonde over the widened surface found real NEW unlocked
sites (AUD829: ``services_wms.py::ajouter_ligne_unite_logistique`` /
``controler_scan_emballage``, among ~20 others) — this was NOT a pure
coverage gap like M-07/M-08/M-09, it hid live debt.

  * an assignment ``obj.field = <expr referencing obj.field>`` OR an augmented
    assignment ``obj.field += / -= ...`` on a numeric-looking attribute,
  * followed (anywhere in the same function) by ``obj.save(...)``,
  * while the function does NOT call ``select_for_update(`` and the modifying
    expression is NOT an ``F(...)`` atomic update.

ASTK53 — STATUS CHECK, same family: a document-status guard
``if <doc>.statut ...: raise`` followed by writes, where ``<doc>`` is a
PARAMETER of the function (an instance read BEFORE the transaction), and the
function never calls ``select_for_update()`` (so the status is not re-read
under a lock) — two concurrent requests both pass the check and both write
(MVT-9 pattern). The correct AUD217/AUD320 patterns (lock + re-read inside
``transaction.atomic()``) pass. Reported as ``path::function (<doc>.statut)``
and allowlisted the same way.

v1 = ADVISORY via an allowlist: existing, human-reviewed safe sites are
recorded in ``scripts/read_modify_write_allow.txt`` (one ``path::function``
per line). A NEW unlocked read-modify-write (not in the allowlist) fails CI —
the fix is ``F()`` for a pure increment, ``select_for_update`` for a
read-decide-write.

Usage:
    python scripts/check_read_modify_write.py            # check (CI)
    python scripts/check_read_modify_write.py --list     # print every site found
"""
from __future__ import annotations

import ast
import sys
from pathlib import Path
TYPE_DE_CLE = "par_symbole"  # AMET100 — cle de contenu `fichier::symbole` (jamais un numero de ligne)

ROOT = Path(__file__).resolve().parent.parent
DJANGO_CORE = ROOT / "backend" / "django_core"
APPS_DIR = DJANGO_CORE / "apps"
CORE_DIR = DJANGO_CORE / "core"
AUTH_DIR = DJANGO_CORE / "authentication"
ALLOWLIST_PATH = ROOT / "scripts" / "read_modify_write_allow.txt"


def _iter_services_files():
    # AUD828 (M-03) — the THREE dispositions this repo uses for a
    # "services" surface (same pattern as check_on_delete.py's model-file
    # iterator): bare services.py, split services_*.py, or a services/
    # package — across apps/* AND the two foundation dirs.
    dirs = list(sorted(APPS_DIR.iterdir())) if APPS_DIR.is_dir() else []
    for app_dir in dirs + [CORE_DIR, AUTH_DIR]:
        if not app_dir.is_dir():
            continue
        for svc in sorted(app_dir.glob("services.py")):
            yield svc
        for svc in sorted(app_dir.glob("services_*.py")):
            yield svc
        svc_pkg = app_dir / "services"
        if svc_pkg.is_dir():
            for f in sorted(svc_pkg.glob("*.py")):
                if f.name != "__init__.py":
                    yield f
    # SPL3 — la scission de crm/services.py (SPL3-SPL26) déplace ses écritures
    # dans des modules thématiques : sans ce balayage, une fonction déplacée
    # sortirait SILENCIEUSEMENT de la garde.
    crm_dir = APPS_DIR / "crm"
    if crm_dir.is_dir():
        vus = set()
        for motif in _MODULES_SCISSION_CRM:
            for f in sorted(crm_dir.glob(motif)):
                if f.name not in vus:
                    vus.add(f.name)
                    yield f


#: SPL3 — modules issus de la scission de ``apps/crm/services.py``.
_MODULES_SCISSION_CRM = (
    "leads_*.py", "fiche_*.py", "clients_*.py", "visites_rdv.py",
    "visites_retour_lead.py", "cadence_*.py", "devis_chatter.py",
)


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


def _attr_key(node):
    """Return ('varname', 'attr') for an ``x.attr`` Attribute node, else None."""
    if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name):
        return (node.value.id, node.attr)
    return None


_ARITH_OPS = (ast.Add, ast.Sub, ast.Mult, ast.Div, ast.FloorDiv, ast.Mod,
              ast.Pow)


def _is_string_constant(node):
    return isinstance(node, ast.Constant) and isinstance(
        node.value, (str, bytes))


def _binop_is_numeric_arith(binop):
    """True for an arithmetic BinOp with no string operand (excludes the
    ``x.note = x.note + "\\n"`` string-concat false positive)."""
    if not isinstance(binop, ast.BinOp) or not isinstance(binop.op, _ARITH_OPS):
        return False
    for operand in (binop.left, binop.right):
        if _is_string_constant(operand):
            return False
    return True


def _expr_references_attr(expr, key):
    """True if the expression is a NUMERIC arithmetic update reading ``x.attr``
    (the same key) — e.g. ``x.qty = x.qty - n``. String concatenation and
    ``or``-default idioms are deliberately excluded (not lost-update prone)."""
    for sub in ast.walk(expr):
        if _binop_is_numeric_arith(sub) and _expr_references_attr_raw(sub, key):
            return True
    return False


def _expr_references_attr_raw(expr, key):
    for sub in ast.walk(expr):
        if isinstance(sub, ast.Attribute) and _attr_key(sub) == key:
            return True
    return False


def _expr_is_f_expression(expr):
    """True if the expression is built from an ``F(...)`` atomic update."""
    for sub in ast.walk(expr):
        if isinstance(sub, ast.Call):
            func = sub.func
            fname = func.id if isinstance(func, ast.Name) else (
                func.attr if isinstance(func, ast.Attribute) else None)
            if fname == "F":
                return True
    return False


def _function_calls_select_for_update(func_node):
    for sub in ast.walk(func_node):
        if isinstance(sub, ast.Call):
            f = sub.func
            name = f.attr if isinstance(f, ast.Attribute) else (
                f.id if isinstance(f, ast.Name) else None)
            if name == "select_for_update":
                return True
    return False


def _function_saves_var(func_node, varname):
    """True if ``<varname>.save(...)`` is called anywhere in the function."""
    for sub in ast.walk(func_node):
        if isinstance(sub, ast.Call) and isinstance(sub.func, ast.Attribute):
            if sub.func.attr == "save":
                inner = sub.func.value
                if isinstance(inner, ast.Name) and inner.id == varname:
                    return True
    return False


def _rmw_sites_in_function(func_node):
    """Yield (varname, attr) read-modify-write targets found in the function.

    A target is a bare ``obj.field = <expr referencing obj.field>`` OR an
    ``obj.field += / -= ...`` whose modifying expression is NOT ``F(...)``.
    """
    sites = []
    for sub in ast.walk(func_node):
        # obj.field += n   /   obj.field -= n   (numeric arithmetic only)
        if isinstance(sub, ast.AugAssign):
            key = _attr_key(sub.target)
            if (key and isinstance(sub.op, _ARITH_OPS)
                    and not _is_string_constant(sub.value)
                    and not _expr_is_f_expression(sub.value)):
                sites.append(key)
        # obj.field = <expr that reads obj.field>
        elif isinstance(sub, ast.Assign):
            if len(sub.targets) != 1:
                continue
            key = _attr_key(sub.targets[0])
            if not key:
                continue
            if _expr_is_f_expression(sub.value):
                continue
            if _expr_references_attr(sub.value, key):
                sites.append(key)
    return sites


_WRITE_ATTRS = ("save", "update", "create", "bulk_create", "bulk_update",
                "delete", "update_or_create", "get_or_create")


def _params_of(func_node):
    args = func_node.args
    noms = [a.arg for a in args.posonlyargs + args.args + args.kwonlyargs]
    return {n for n in noms if n not in ("self", "cls")}


def _status_checked_params(func_node):
    """Paramètres ``p`` testés par ``if ... p.statut ...: ... raise`` (ASTK53)."""
    params = _params_of(func_node)
    trouves = []
    for sub in ast.walk(func_node):
        if not isinstance(sub, ast.If):
            continue
        if not any(isinstance(n, ast.Raise)
                   for stmt in sub.body for n in ast.walk(stmt)):
            continue
        for n in ast.walk(sub.test):
            if (isinstance(n, ast.Attribute) and n.attr == "statut"
                    and isinstance(n.value, ast.Name)
                    and n.value.id in params and n.value.id not in trouves):
                trouves.append(n.value.id)
    return trouves


def _function_writes(func_node):
    for sub in ast.walk(func_node):
        if isinstance(sub, ast.Call) and isinstance(sub.func, ast.Attribute):
            if sub.func.attr in _WRITE_ATTRS:
                return True
    return False


def _status_findings(func_node):
    if _function_calls_select_for_update(func_node):
        return []
    if not _function_writes(func_node):
        return []
    return [(func_node.name, f"{p}.statut")
            for p in _status_checked_params(func_node)]


def check_file(path: Path):
    """Return a list of (funcname, varname.attr) unlocked read-modify-writes."""
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except SyntaxError:
        return []
    findings = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        findings.extend(_status_findings(node))
        if _function_calls_select_for_update(node):
            continue
        for varname, attr in _rmw_sites_in_function(node):
            if _function_saves_var(node, varname):
                findings.append((node.name, f"{varname}.{attr}"))
    return findings


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
    offenders = _morts_offenders(allow)
    listed = []
    for path in _iter_services_files():
        rel = _rel(path)
        for funcname, target in check_file(path):
            key = f"{rel}::{funcname}"
            listed.append(f"{key} ({target})")
            if key not in allow:
                offenders.append(f"{key} ({target})")

    if list_mode:
        for line in listed:
            print(line)
        return 0

    if offenders:
        print("check_read_modify_write: unlocked read-modify-write on a "
              "shared field (not in scripts/read_modify_write_allow.txt):")
        for line in offenders:
            print(f"  - {line}")
        print(
            "\nUse F() for a pure increment (obj.field = F('field') + n) or "
            "select_for_update() for a read-decide-write inside atomic(). If "
            "this site is genuinely safe (not concurrently shared), add "
            "'path::function' to scripts/read_modify_write_allow.txt."
        )
        return 1

    print("check_read_modify_write: OK — no unlocked read-modify-write "
          "outside the allowlist.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
