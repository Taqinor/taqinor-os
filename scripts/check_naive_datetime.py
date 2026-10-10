"""YDATA10/YDATA11 — CI guard: `timezone.now()` everywhere, no naive
`datetime`, and timestamps are aware `DateTimeField` (never `DateField`).

DB-free, AST-only (mirrors ``scripts/check_on_delete.py``). Two sweeps:

YDATA10 — scans every ``apps/*/**.py`` file (excluding ``migrations/`` and
test files) for:
  * ``datetime.now(...)`` / ``datetime.utcnow(...)`` — always naive-risk;
    recommend ``django.utils.timezone.now()``.
  * a bare ``datetime.datetime(...)``/``datetime(...)`` CONSTRUCTOR call with
    no ``tzinfo=`` keyword — a naive datetime literal.
A NEW site fails CI; sites already present in ``NAIVE_DATETIME_ALLOWLIST``
below (deliberate business ``date(...)`` usage, generated from the current
repo state) are exempt.

YDATA11 — extends the sweep to MODEL files (``apps/*/models*.py`` + core/
authentication) for:
  * ``models.DateField(auto_now=True)`` / ``models.DateField(auto_now_add=True)``
    — the "today" timezone is ambiguous near midnight; timestamp columns
    should be ``DateTimeField``.
  * a field named like a timestamp (``created|updated|sent|paid|
    date_creation|date_maj|envoye_le|paye_le``) that is declared as a plain
    ``DateField`` (no auto_now) rather than ``DateTimeField``.
Both print an auditable table; a NEW finding fails CI, existing ones in
``DATEFIELD_AUTO_NOW_ALLOWLIST``/``TIMESTAMP_AS_DATEFIELD_ALLOWLIST`` are
baseline-exempt (v1, generated from current state).

Usage:
    python scripts/check_naive_datetime.py
"""
from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

TYPE_DE_CLE = "par_symbole"  # AMET81 — lu par audit_tache.py listes-figees : cle `fichier::Classe.champ` (ADEP25)
ROOT = Path(__file__).resolve().parent.parent
DJANGO_CORE = ROOT / "backend" / "django_core"
APPS_DIR = DJANGO_CORE / "apps"

# ADEP25 — les listes d'exceptions sont des IDENTITES DE CONTENU (`fichier::Classe.champ`),
# jamais `fichier:ligne` : une cle par numero de ligne se decalait a chaque insertion
# (bug-class #34), laissait des cles mortes et PRE-AUTORISAIT la ligne vide laissee
# derriere (un `DateField(auto_now_add=True)` pose en ligne 697 passait). Une cle qui
# n'apparie plus aucun site FAIT ECHOUER la garde (cliquet decroissant).

# YDATA10 — appels datetime.now/utcnow/ctor naifs revus : aucun (cle = `fichier::fonction`).
NAIVE_DATETIME_ALLOWLIST: set[str] = set()

# YDATA11 — DateField(auto_now[_add]=True) revus : dates-ancre de numerotation, champs
# DATE metier (jour), pas des horodatages.
DATEFIELD_AUTO_NOW_ALLOWLIST = {
    "backend/django_core/apps/facturation/models.py::Facture.date_emission",
    "backend/django_core/apps/facturation/models.py::Avoir.date_emission",
    "backend/django_core/apps/facturation/models.py::RelanceLog.date",
    "backend/django_core/apps/ventes/models_facturation.py::NoteDebit.date_emission",
}
# DateField dont le nom ressemble a un horodatage mais qui est une DATE (jour) revue.
TIMESTAMP_AS_DATEFIELD_ALLOWLIST = {
    # CommissionPartenaire.paye_le : date de paiement (jour).
    "backend/django_core/apps/crm/models.py::CommissionPartenaire.paye_le",
    # PUB75 ConsentRecord.date_consentement : jour de recueil du consentement (loi 09-08).
    "backend/django_core/apps/adsengine/models.py::ConsentRecord.date_consentement",
}

TIMESTAMP_NAME_RE = re.compile(
    r"(created|updated|sent|paid|date_creation|date_maj|envoye_le|paye_le)",
    re.IGNORECASE,
)


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
                    or name.endswith("_test.py") \
                    or "tests" in rel_parts:
                continue
            yield app_dir.name, path


def _iter_model_files():
    if APPS_DIR.is_dir():
        for app_dir in sorted(APPS_DIR.iterdir()):
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


def _is_naive_datetime_now_call(node):
    """`datetime.now(...)`/`datetime.utcnow(...)` with NO positional/tzinfo
    argument giving it a timezone. `datetime.now(CASABLANCA)` is fine;
    `datetime.now()`/`datetime.utcnow()` (utcnow NEVER accepts a tz arg) are
    naive-risk."""
    name = _call_name(node)
    if name not in ("now", "utcnow"):
        return False
    if not isinstance(node.func, ast.Attribute):
        return False
    owner = node.func.value
    owner_name = owner.attr if isinstance(owner, ast.Attribute) else \
        (owner.id if isinstance(owner, ast.Name) else None)
    if owner_name != "datetime":
        return False
    if name == "utcnow":
        return True  # always naive, no tz argument exists for utcnow()
    return len(node.args) == 0 and _kwarg(node, "tzinfo") is None


def _is_naive_datetime_ctor_call(node):
    """A bare `datetime.datetime(2026, 1, 1)`/`datetime(2026, 1, 1)`
    constructor (>=3 positional args, i.e. year/month/day) with no
    `tzinfo=` keyword."""
    name = _call_name(node)
    if name != "datetime":
        return False
    if len(node.args) < 3:
        return False
    return _kwarg(node, "tzinfo") is None


def _enclosing_function(tree, node) -> str:
    """Nom (qualifie par la classe) de la fonction englobante, `<module>` sinon : identite
    de CONTENU stable quand des lignes sont inserees au-dessus."""
    meilleur, taille = "<module>", None
    for outer in ast.walk(tree):
        if not isinstance(outer, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        fin = getattr(outer, "end_lineno", outer.lineno)
        if outer.lineno <= node.lineno <= fin and (taille is None or fin - outer.lineno < taille):
            meilleur, taille = outer.name, fin - outer.lineno
    return meilleur


def _orphelines(allow, used, nom):
    return [("ORPHAN_ALLOWLIST_KEY",
             f"{nom} : cle « {cle} » n'apparie aucun site - retirez-la "
             "(les exceptions sont des identites de contenu, base decroissante).")
            for cle in sorted(set(allow) - used)]


def check_naive_datetime():
    all_rows = []
    findings = []
    used = set()
    for _app, path in _iter_source_files():
        source = path.read_text(encoding="utf-8")
        try:
            tree = ast.parse(source, filename=str(path))
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            kind = None
            if _is_naive_datetime_now_call(node):
                kind = "NAIVE_DATETIME_NOW"
            elif _is_naive_datetime_ctor_call(node):
                kind = "NAIVE_DATETIME_CTOR"
            if kind is None:
                continue
            lineno = node.lineno
            rel = _rel(path)
            all_rows.append((rel, lineno, kind))
            allow_key = f"{rel}::{_enclosing_function(tree, node)}"
            used.add(allow_key)
            if allow_key not in NAIVE_DATETIME_ALLOWLIST:
                findings.append((
                    kind,
                    f"{rel}:{lineno}: naive datetime construction — use "
                    "django.utils.timezone.now() instead.",
                ))
    findings += _orphelines(NAIVE_DATETIME_ALLOWLIST, used, "NAIVE_DATETIME_ALLOWLIST")
    return all_rows, findings


def _iter_field_assignments(tree):
    for classdef in ast.walk(tree):
        if not isinstance(classdef, ast.ClassDef):
            continue
        for stmt in ast.walk(classdef):
            if isinstance(stmt, ast.Assign):
                target = stmt.targets[0] if stmt.targets else None
                value = stmt.value
            elif isinstance(stmt, ast.AnnAssign):
                target = stmt.target
                value = stmt.value
            else:
                continue
            if value is None or not isinstance(value, ast.Call):
                continue
            if not isinstance(target, ast.Name):
                continue
            yield classdef.name, target.id, value


def check_datefield_timestamps():
    all_rows = []
    findings = []
    used_auto = set()
    used_ts = set()
    for path in _iter_model_files():
        source = path.read_text(encoding="utf-8")
        try:
            tree = ast.parse(source, filename=str(path))
        except SyntaxError:
            continue
        for model, field, node in _iter_field_assignments(tree):
            field_type = _call_name(node)
            if field_type != "DateField":
                continue
            lineno = node.lineno
            rel = _rel(path)
            allow_key = f"{rel}::{model}.{field}"

            auto_now = _kwarg(node, "auto_now")
            auto_now_add = _kwarg(node, "auto_now_add")
            has_auto_now = (
                (isinstance(auto_now, ast.Constant) and auto_now.value is True)
                or (isinstance(auto_now_add, ast.Constant)
                    and auto_now_add.value is True)
            )
            if has_auto_now:
                all_rows.append((rel, lineno, model, field, "AUTO_NOW_DATEFIELD"))
                used_auto.add(allow_key)
                if allow_key not in DATEFIELD_AUTO_NOW_ALLOWLIST:
                    findings.append((
                        "DATEFIELD_AUTO_NOW",
                        f"{rel}:{lineno}: {model}.{field} is a "
                        "DateField(auto_now[_add]=True) — 'today' is "
                        "timezone-ambiguous near midnight; use a "
                        "DateTimeField if this is a timestamp.",
                    ))
            elif TIMESTAMP_NAME_RE.search(field):
                all_rows.append((rel, lineno, model, field, "TIMESTAMP_AS_DATEFIELD"))
                used_ts.add(allow_key)
                if allow_key not in TIMESTAMP_AS_DATEFIELD_ALLOWLIST:
                    findings.append((
                        "TIMESTAMP_AS_DATEFIELD",
                        f"{rel}:{lineno}: {model}.{field} looks like a "
                        "timestamp but is a plain DateField — use an aware "
                        "DateTimeField.",
                    ))
    findings += _orphelines(DATEFIELD_AUTO_NOW_ALLOWLIST, used_auto,
                            "DATEFIELD_AUTO_NOW_ALLOWLIST")
    findings += _orphelines(TIMESTAMP_AS_DATEFIELD_ALLOWLIST, used_ts,
                            "TIMESTAMP_AS_DATEFIELD_ALLOWLIST")
    return all_rows, findings


def main(argv):
    naive_rows, naive_findings = check_naive_datetime()
    date_rows, date_findings = check_datefield_timestamps()

    print(f"check_naive_datetime: {len(naive_rows)} datetime.now/utcnow/"
          "ctor call(s) found.")
    for rel, lineno, kind in naive_rows:
        print(f"  {rel}:{lineno}  [{kind}]")

    print(f"\ncheck_naive_datetime: {len(date_rows)} DateField timestamp-"
          "shaped declaration(s) found.")
    for rel, lineno, model, field, kind in date_rows:
        print(f"  {rel}:{lineno}  {model}.{field}  [{kind}]")

    all_findings = naive_findings + date_findings
    if all_findings:
        print("\ncheck_naive_datetime: violation(s) found:")
        for code, message in all_findings:
            print(f"  - [{code}] {message}")
        return 1

    print("\ncheck_naive_datetime: OK.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
