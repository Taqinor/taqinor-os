"""YDATA22 — mono-currency (MAD) invariant sweep, DB-free AST/source scan.

TAQINOR OS is mono-currency (MAD) today: ``Devis``/``Facture`` already carry a
``devise``/``taux_change`` pair, but most monetary models still store a bare
amount with no explicit currency code alongside it — the invariant "montant +
devise voyagent ensemble" (amount and currency travel together, see
``docs/money-convention.md``) lives only in the unstated assumption that
everything is MAD.

This is v1 (YDATA22): a pure ADVISORY sweep, never a hard CI gate — the plan
task is explicit ("v1 : liste ... pas de blocage"). It:

1. Walks every Django model class under ``backend/django_core/apps/*/models*.py``
   (plain ``models.py``, split ``models_*.py`` files, and ``models/*.py``
   packages).
2. Lists every monetary field (name matches ``MONEY_FIELD_RE``) and whether the
   model it lives on already carries an explicit ``devise``/``devise_defaut``/
   ``currency`` field (and, informationally, an exchange-rate field).
3. Regenerates ``docs/currency-audit.md`` (with ``--write``) — the reviewable
   table confirming the mono-devise MAD hypothesis for everything that has no
   explicit devise field.

Scope note — this script's filename is shared with two SEPARATE, NOT YET BUILT
sibling tasks: YDATA6 (ban bare ``FloatField`` on money fields) and YDATA7
(require explicit ``max_digits``/``decimal_places=2`` on money
``DecimalField``). Neither is implemented here — only the YDATA22
currency-audit sweep is. When YDATA6/7 land, EXTEND this same module (its
model-scanning helpers are written to be reused) rather than creating a
second file.

Run
---
    python scripts/check_money_fields.py            # prints the audit; advisory only, exit 0
    python scripts/check_money_fields.py --write     # also regenerates docs/currency-audit.md
"""
from __future__ import annotations

import ast
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DJANGO_CORE = ROOT / "backend" / "django_core"
APPS_DIR = DJANGO_CORE / "apps"
AUDIT_DOC = ROOT / "docs" / "currency-audit.md"

#: Same field-name regex as the YDATA6/7 spec (money semantics).
MONEY_FIELD_RE = re.compile(
    r"(prix|montant|total|_ht|_ttc|tva|remise|acompte|solde|amount|price|"
    r"cost|cout|honoraire|penalite)",
    re.IGNORECASE,
)
#: Field names that count as "this model already carries an explicit currency".
DEVISE_FIELD_NAMES = {"devise", "devise_defaut", "currency"}
#: Field names that count as "this model already carries an exchange rate"
#: (informational column only — not required by the v1 advisory).
RATE_FIELD_NAMES = {
    "taux_change", "taux_vers_mad", "taux_origine", "taux_reglement", "taux_cloture",
}


def _iter_model_files():
    """Yield every model source file (three on-disk layouts used in the repo)."""
    yield from APPS_DIR.glob("*/models.py")
    yield from APPS_DIR.glob("*/models_*.py")
    yield from APPS_DIR.glob("*/models/*.py")


def _is_field_call(node: ast.AST) -> bool:
    """True if *node* is a Call whose callable name ends in ``Field`` —
    matches ``models.DecimalField(...)`` and a bare ``DecimalField(...)``
    (after ``from django.db.models import DecimalField``)."""
    if not isinstance(node, ast.Call):
        return False
    func = node.func
    name = func.attr if isinstance(func, ast.Attribute) else (
        func.id if isinstance(func, ast.Name) else None
    )
    return bool(name) and name.endswith("Field")


@dataclass
class ModelMoneyInfo:
    app: str
    relpath: str
    model: str
    lineno: int
    money_fields: list = field(default_factory=list)
    has_devise: bool = False
    has_rate: bool = False


def _scan_class(app: str, relpath: str, node: ast.ClassDef):
    """Return a ``ModelMoneyInfo`` for *node* if it declares >=1 money field,
    else ``None``. Pure/no I/O — reusable directly by unit tests."""
    money_fields: list[str] = []
    has_devise = False
    has_rate = False
    for stmt in node.body:
        targets: list[str] = []
        value = None
        if isinstance(stmt, ast.Assign):
            value = stmt.value
            targets = [t.id for t in stmt.targets if isinstance(t, ast.Name)]
        elif isinstance(stmt, ast.AnnAssign) and isinstance(stmt.target, ast.Name):
            targets = [stmt.target.id]
            value = stmt.value
        if not targets or value is None or not _is_field_call(value):
            continue
        for fname in targets:
            lname = fname.lower()
            if lname in DEVISE_FIELD_NAMES:
                has_devise = True
            if lname in RATE_FIELD_NAMES:
                has_rate = True
            if MONEY_FIELD_RE.search(lname):
                money_fields.append(fname)
    if not money_fields:
        return None
    return ModelMoneyInfo(
        app=app, relpath=relpath, model=node.name, lineno=node.lineno,
        money_fields=sorted(set(money_fields)), has_devise=has_devise, has_rate=has_rate,
    )


def scan_money_models() -> list:
    """Scan the whole repo's model files; return sorted ``ModelMoneyInfo`` list."""
    results: list[ModelMoneyInfo] = []
    for path in _iter_model_files():
        if not path.exists():
            continue
        relpath = path.relative_to(DJANGO_CORE).as_posix()
        app = path.relative_to(APPS_DIR).parts[0]
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                info = _scan_class(app, relpath, node)
                if info is not None:
                    results.append(info)
    results.sort(key=lambda r: (r.app, r.relpath, r.lineno))
    return results


def render_audit_markdown(models: list) -> str:
    without_devise = [m for m in models if not m.has_devise]
    with_devise = [m for m in models if m.has_devise]
    lines = [
        "# Currency audit — YDATA22",
        "",
        "Generated by `python scripts/check_money_fields.py --write` — do not hand-edit,",
        "re-run the script instead. Advisory sweep, not a CI gate (v1 per YDATA22: \"pas",
        "de blocage\"). Confirms the mono-devise MAD hypothesis documented in",
        "`docs/money-convention.md`: every model below persists money with no explicit",
        "currency code EXCEPT the ones already carrying `devise`/`devise_defaut`",
        "(multi-currency purchasing/quoting/FX-revaluation models).",
        "",
        f"- Money-bearing models scanned: **{len(models)}**",
        f"- Already carry an explicit devise/currency field: **{len(with_devise)}**",
        f"- Assume mono-devise MAD implicitly (no devise field): **{len(without_devise)}**",
        "",
        "## Models WITHOUT an explicit devise field (assume MAD)",
        "",
        "| App | Model | File | Money fields |",
        "| --- | --- | --- | --- |",
    ]
    for m in without_devise:
        lines.append(f"| {m.app} | {m.model} | `{m.relpath}:{m.lineno}` | {', '.join(m.money_fields)} |")
    lines += [
        "",
        "## Models WITH an explicit devise/currency field",
        "",
        "| App | Model | File | Money fields | Has exchange rate? |",
        "| --- | --- | --- | --- | --- |",
    ]
    for m in with_devise:
        lines.append(
            f"| {m.app} | {m.model} | `{m.relpath}:{m.lineno}` | {', '.join(m.money_fields)} | "
            f"{'yes' if m.has_rate else 'no'} |"
        )
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
    except (AttributeError, ValueError):  # pragma: no cover - non-reconfigurable stream
        pass
    models = scan_money_models()
    without_devise = [m for m in models if not m.has_devise]
    print(
        f"check_money_fields (YDATA22): {len(models)} modeles argent scannes, "
        f"{len(without_devise)} sans champ devise explicite (hypothese mono-MAD)."
    )
    if "--write" in sys.argv[1:]:
        AUDIT_DOC.write_text(render_audit_markdown(models), encoding="utf-8")
        print(f"  -> {AUDIT_DOC.relative_to(ROOT).as_posix()} regenere.")
    # v1 = advisory only (YDATA22 spec: "pas de blocage") — never fails CI.
    return 0


if __name__ == "__main__":
    sys.exit(main())
