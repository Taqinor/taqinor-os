"""YDATA6 — CI guard: monetary fields are `DecimalField`, never `FloatField`.

DB-free, AST-only (mirrors ``scripts/check_on_delete.py``): scans
``apps/*/models*.py`` + ``core/models.py`` + ``authentication/models.py``
for any field assignment whose NAME matches the money-semantic regex
(``prix|montant|total|_ht|_ttc|tva|remise|acompte|solde|amount|price|cost|
cout|honoraire|penalite``, case-insensitive) and flags it if declared
``models.FloatField(...)`` (or a bare ``IntegerField`` with no "centimes"
comment nearby). A field also matching the GPS/technical-unit allowlist
(``lat|lng|latitude|longitude|hmt|debit|kwc|kwh|puissance|
taux_autoconsommation``) is never flagged, regardless of the money regex —
this is how the two legitimate ``FloatField`` GPS columns
(``compta.models.DeplacementSAV.depart_lat/lng``,
``site_lat``/``site_lng``) stay green.

With ``--decimal-places`` (YDATA7), also sweeps every monetary
``DecimalField`` and requires an explicit ``decimal_places`` (2 for plain
amounts; 4 tolerated for a field named ``taux_*``/``*_pct``/``pourcentage``)
and an explicit ``max_digits``; writes ``docs/money-fields-audit.md`` (every
monetary DecimalField + its max_digits/decimal_places, so drift is
visible) and fails only on a field with no/wrong ``decimal_places``.

Usage:
    python scripts/check_money_fields.py                  # YDATA6 only
    python scripts/check_money_fields.py --decimal-places  # + YDATA7 sweep
"""
from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DJANGO_CORE = ROOT / "backend" / "django_core"
MONEY_AUDIT_DOC = ROOT / "docs" / "money-fields-audit.md"

MONEY_NAME_RE = re.compile(
    r"(prix|montant|total|_ht|_ttc|tva|remise|acompte|solde|amount|price|"
    r"cost|cout|honoraire|penalite)",
    re.IGNORECASE,
)
GPS_TECH_NAME_RE = re.compile(
    r"(lat|lng|latitude|longitude|hmt|debit|kwc|kwh|puissance|"
    r"taux_autoconsommation)",
    re.IGNORECASE,
)
RATE_NAME_RE = re.compile(r"(taux_|_pct$|pourcentage)", re.IGNORECASE)

# YDATA7 — reviewed exceptions: fields whose decimal_places is intentionally
# outside {2, 4} because the unit itself is not a plain percentage/amount.
# One entry today: gestion_projet.Projet.taux_penalite_retard is a PER-MILLE
# (‰) rate per day (Moroccan public-works penalty convention), correctly at
# decimal_places=3 — not a drift to fix.
DECIMAL_PLACES_ALLOWLIST = {
    "backend/django_core/apps/gestion_projet/models.py:103",
}

FLOAT_LIKE = {"FloatField"}
DECIMAL_LIKE = {"DecimalField"}


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


def _is_money_name(name: str) -> bool:
    if GPS_TECH_NAME_RE.search(name):
        return False
    return bool(MONEY_NAME_RE.search(name))


def _iter_field_assignments(tree):
    """Single pass: yields (model_name, field_name, call_node) for every
    `field = models.XField(...)` assignment in any class body."""
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


def check_file(path: Path, decimal_places_mode: bool):
    source = path.read_text(encoding="utf-8")
    try:
        tree = ast.parse(source, filename=str(path))
    except SyntaxError as exc:
        return [], [("PARSE_ERROR", f"could not parse: {exc}")]

    all_rows = []
    findings = []

    for model, field, node in _iter_field_assignments(tree):
        field_type = _call_name(node)
        if field_type not in FLOAT_LIKE | DECIMAL_LIKE:
            continue
        if not _is_money_name(field):
            continue
        lineno = node.lineno

        if field_type in FLOAT_LIKE:
            findings.append((
                "MONEY_FLOAT_FIELD",
                f"{model}.{field} at line {lineno}: FloatField() on a "
                "money-semantic name — use DecimalField(max_digits=..., "
                "decimal_places=2).",
            ))
            all_rows.append(
                (_rel(path), lineno, model, field, "FloatField", None, None))
            continue

        # DecimalField
        max_digits_kw = _kwarg(node, "max_digits")
        decimal_places_kw = _kwarg(node, "decimal_places")
        max_digits = (
            max_digits_kw.value
            if isinstance(max_digits_kw, ast.Constant) else None)
        decimal_places = (
            decimal_places_kw.value
            if isinstance(decimal_places_kw, ast.Constant) else None)
        all_rows.append((
            _rel(path), lineno, model, field, "DecimalField", max_digits,
            decimal_places))

        if decimal_places_mode:
            is_rate = bool(RATE_NAME_RE.search(field))
            expected = {2, 4} if is_rate else {2}
            allow_key = f"{_rel(path)}:{lineno}"
            if (max_digits is None or decimal_places is None
                    or decimal_places not in expected) \
                    and allow_key not in DECIMAL_PLACES_ALLOWLIST:
                findings.append((
                    "MONEY_DECIMAL_PLACES",
                    f"{model}.{field} at line {lineno}: DecimalField "
                    f"missing max_digits/decimal_places, or decimal_places "
                    f"not in {sorted(expected)} "
                    f"(got max_digits={max_digits!r}, "
                    f"decimal_places={decimal_places!r}).",
                ))

    return all_rows, findings


def _write_audit_doc(rows):
    decimal_rows = [r for r in rows if r[4] == "DecimalField"]
    lines = [
        "# Audit champs monétaires — DecimalField (YDATA7)",
        "",
        "Généré par `python scripts/check_money_fields.py --decimal-places`. "
        "Tableau de tous les champs `DecimalField` à sémantique monétaire "
        "(dérive visible : max_digits/decimal_places attendus).",
        "",
        "| Fichier:ligne | Modèle.champ | max_digits | decimal_places |",
        "|---|---|---|---|",
    ]
    for rel, lineno, model, field, _t, max_digits, decimal_places in sorted(
            decimal_rows):
        lines.append(
            f"| `{rel}:{lineno}` | {model}.{field} | {max_digits} | "
            f"{decimal_places} |")
    MONEY_AUDIT_DOC.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main(argv):
    decimal_places_mode = "--decimal-places" in argv
    all_rows = []
    report_lines = []

    for path in _iter_model_files():
        rows, findings = check_file(path, decimal_places_mode)
        all_rows.extend(rows)
        for code, message in findings:
            report_lines.append(f"{_rel(path)}: [{code}] {message}")

    print(f"check_money_fields: scanned {len(all_rows)} money-semantic "
          "field(s).")
    for rel, lineno, model, field, ftype, max_digits, decimal_places in all_rows:
        extra = (f" max_digits={max_digits} decimal_places={decimal_places}"
                 if ftype == "DecimalField" else "")
        print(f"  {rel}:{lineno}  {model}.{field}  [{ftype}]{extra}")

    if decimal_places_mode:
        _write_audit_doc(all_rows)
        print(f"\ncheck_money_fields --decimal-places: wrote "
              f"{_rel(MONEY_AUDIT_DOC)}")

    if report_lines:
        print("\ncheck_money_fields: violation(s) found:")
        for line in report_lines:
            print(f"  - {line}")
        return 1

    print("\ncheck_money_fields: OK.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
