"""YDATA19 — advisory sweep: DB defence-in-depth for money/quantity invariants.

Business invariants (``remise`` in [0, 100], ``montant >= 0``, ``ttc >= ht``,
quantities ``>= 0``) often live ONLY in a Python ``clean()``/``save()`` — which
``bulk_create``/``bulk_update``/``QuerySet.update``/raw SQL all bypass. A
``CheckConstraint`` in ``Meta.constraints`` is the DB-level backstop.

This ADVISORY, DB-free AST tool scans the money/quantity models
(``Devis``, ``LigneDevis``, ``Facture``, ``LigneFacture``, ``MouvementStock``,
``Paiement``) and, per model, lists the numeric invariants it can find in
``clean()``/``save()`` that have NO matching ``CheckConstraint`` — plus the
canonical money/quantity invariants that are absent from BOTH layers. It writes
``docs/db-invariants-gap.md`` (the gap register, to be closed later by targeted
additive ``AddConstraint`` migrations — NOT here). It never fails the build.

Usage:
    python scripts/check_db_invariants.py            # print the gap report
    python scripts/check_db_invariants.py --write     # (re)generate the doc
"""
from __future__ import annotations

import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DJANGO_CORE = ROOT / "backend" / "django_core"
APPS_DIR = DJANGO_CORE / "apps"
GAP_DOC = ROOT / "docs" / "db-invariants-gap.md"

# Target money/quantity models (model name -> app) and the canonical invariants
# each SHOULD carry at the DB level.
TARGET_MODELS = {
    "Devis": ("ventes", ["remise in [0,100]", "total_ht >= 0", "total_ttc >= 0"]),
    "LigneDevis": ("ventes", ["remise in [0,100]", "quantite >= 0",
                              "prix_unitaire >= 0"]),
    "Facture": ("facturation", ["remise in [0,100]", "total_ht >= 0",
                                "total_ttc >= total_ht"]),
    "LigneFacture": ("facturation", ["quantite >= 0", "prix_unitaire >= 0",
                                     "remise in [0,100]"]),
    "MouvementStock": ("stock", ["quantite >= 0"]),
    "Paiement": ("facturation", ["montant >= 0"]),
}

_REL_OPS = {ast.GtE: ">=", ast.LtE: "<=", ast.Gt: ">", ast.Lt: "<"}


def _self_attr(node):
    if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name) \
            and node.value.id == "self":
        return node.attr
    return None


def _numeric_const(node):
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)) \
            and not isinstance(node.value, bool):
        return node.value
    return None


def _find_class(tree, name):
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == name:
            return node
    return None


def _method(classdef, name):
    for node in classdef.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) \
                and node.name == name:
            return node
    return None


def python_invariants(classdef):
    """Field names that appear in a numeric-bound comparison inside
    clean()/save() — the Python-side invariants."""
    fields = set()
    for mname in ("clean", "save"):
        m = _method(classdef, mname)
        if m is None:
            continue
        for cmp_node in ast.walk(m):
            if not isinstance(cmp_node, ast.Compare):
                continue
            if not any(type(op) in _REL_OPS for op in cmp_node.ops):
                continue
            operands = [cmp_node.left, *cmp_node.comparators]
            attrs = [_self_attr(o) for o in operands]
            nums = [_numeric_const(o) for o in operands]
            # self.field <op> number   (or reversed)
            if any(a for a in attrs) and any(n is not None for n in nums):
                for a in attrs:
                    if a:
                        fields.add(a)
            # self.a <op> self.b (cross-field, e.g. ttc >= ht)
            elif sum(1 for a in attrs if a) >= 2:
                for a in attrs:
                    if a:
                        fields.add(a)
    return fields


def checkconstraint_fields(classdef):
    """Field names referenced by any CheckConstraint in Meta.constraints."""
    fields = set()
    meta = None
    for node in classdef.body:
        if isinstance(node, ast.ClassDef) and node.name == "Meta":
            meta = node
    if meta is None:
        return fields
    for stmt in meta.body:
        if not isinstance(stmt, ast.Assign):
            continue
        targets = [t.id for t in stmt.targets if isinstance(t, ast.Name)]
        if "constraints" not in targets:
            continue
        for elt in ast.walk(stmt.value):
            if isinstance(elt, ast.Call):
                fn = elt.func
                fname = fn.attr if isinstance(fn, ast.Attribute) else (
                    fn.id if isinstance(fn, ast.Name) else "")
                if fname != "CheckConstraint":
                    continue
                # Q(field__gte=0) -> keyword arg 'field__gte' -> field 'field'.
                for q in ast.walk(elt):
                    if isinstance(q, ast.keyword) and q.arg \
                            and "__" in q.arg:
                        fields.add(q.arg.split("__", 1)[0])
                    if isinstance(q, ast.Call):
                        f = q.func
                        n = f.attr if isinstance(f, ast.Attribute) else (
                            f.id if isinstance(f, ast.Name) else "")
                        if n == "F" and q.args and isinstance(q.args[0], ast.Constant):
                            fields.add(str(q.args[0].value))
    return fields


def scan():
    """Return a list of (model, app, python_fields, cc_fields, canonical)."""
    out = []
    for model, (app, canonical) in TARGET_MODELS.items():
        path = APPS_DIR / app / "models.py"
        py_fields, cc_fields = set(), set()
        if path.is_file():
            try:
                tree = ast.parse(path.read_text(encoding="utf-8"))
            except SyntaxError:
                tree = None
            if tree is not None:
                cls = _find_class(tree, model)
                if cls is not None:
                    py_fields = python_invariants(cls)
                    cc_fields = checkconstraint_fields(cls)
        out.append((model, app, py_fields, cc_fields, canonical))
    return out


def render_doc(rows):
    lines = [
        "# DB-invariant gap register (YDATA19)",
        "",
        "Advisory register of money/quantity invariants that are NOT enforced by",
        "a database `CheckConstraint` — generated by",
        "`python scripts/check_db_invariants.py --write`. Each gap is a candidate",
        "for a later, targeted, additive `AddConstraint` migration (not created",
        "here). `bulk_create`/`bulk_update`/`QuerySet.update`/raw SQL bypass any",
        "Python `clean()`/`save()` guard, so the DB constraint is the real",
        "backstop.",
        "",
        "| Model | App | Python invariant fields (clean/save) | CheckConstraint fields | Canonical invariants still un-constrained |",
        "| --- | --- | --- | --- | --- |",
    ]
    for model, app, py_fields, cc_fields, canonical in rows:
        py = ", ".join(sorted(py_fields)) or "—"
        cc = ", ".join(sorted(cc_fields)) or "—"
        # Canonical invariants whose primary field is not covered by a CC.
        missing = []
        for inv in canonical:
            field = inv.split()[0]
            if field not in cc_fields:
                missing.append(inv)
        gap = "; ".join(missing) or "(all constrained)"
        lines.append(f"| `{model}` | {app} | {py} | {cc} | {gap} |")
    lines.append("")
    lines.append("Legend: a field in *Python invariant fields* but absent from")
    lines.append("*CheckConstraint fields* is a Python-only invariant (bypassable).")
    lines.append("A *Canonical invariant still un-constrained* has no DB backstop")
    lines.append("at all and is the highest-priority gap to close.")
    lines.append("")
    return "\n".join(lines)


def main(argv):
    rows = scan()
    doc = render_doc(rows)
    if "--write" in argv:
        GAP_DOC.write_text(doc, encoding="utf-8")
        print(f"check_db_invariants: wrote {_rel(GAP_DOC)}")
        return 0
    print(doc)
    print("check_db_invariants: advisory — no build failure. "
          "Run with --write to refresh docs/db-invariants-gap.md.")
    return 0


def _rel(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT)).replace("\\", "/")
    except ValueError:
        return path.name


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
