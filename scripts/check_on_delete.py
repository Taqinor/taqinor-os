"""YDATA1 — CI guard: every ForeignKey/OneToOneField declares `on_delete`
explicitly, and every `CASCADE` is justified.

DB-free, AST-only (mirrors ``scripts/check_safe_migrations.py``/
``check_query_budgets.py``): scans MODEL source files
(``backend/django_core/apps/*/models*.py`` + ``core/models.py`` +
``authentication/models.py``) — never migrations, never a live DB.

For every ``models.ForeignKey(...)``/``models.OneToOneField(...)`` (or the
bare ``ForeignKey(...)``/``OneToOneField(...)`` form after
``from django.db import models`` / ``from django.db.models import
ForeignKey``) call found in a class body:

  (a) missing ``on_delete=`` kwarg entirely -> always a finding (Django
      itself requires it at import time, but a future refactor pattern —
      e.g. building the field via a helper/partial — could hide it from a
      naive grep; the AST walk here looks at the literal call site).
  (b) ``on_delete=models.CASCADE`` (or bare ``CASCADE``) present but with
      NO inline ``# on_delete: <reason>`` comment on the same or an
      adjacent line, AND the field is not already listed in
      ``scripts/on_delete_allowlist.txt`` (one ``path:lineno`` per line,
      generated once from the current repo state so this guard does not
      block on the ~1300 pre-existing FKs).

Also always checked (YDATA3): any ``on_delete=SET_NULL`` must have
``null=True`` on the same field (else a guaranteed migration/runtime
failure), and must never be on a tenant/owner-identity field
(``company``/``societe``/``owner``/``responsable`` — a SET_NULL there would
silently de-scope the row).

With ``--financial``, also enumerates every FK targeting a money/audit-
bearing model (``Devis``/``Facture``/``BonCommande``/``Paiement``/``Avoir``/
``Company``/``Produit``) and flags any ``CASCADE``/``SET_NULL`` policy not
already recorded in the CHECKED-IN ``docs/on-delete-financial-audit.md``
(YDATA2 — the sweep records the gap, it does not presume any one FK is the
wrong one: the committed doc IS the baseline). The doc is then regenerated
in full so it stays up to date; a file:line NOT present in the doc as it
existed on disk before this run is a NEW un-reviewed occurrence.

Prints an auditable table (file:line, model, field, target, policy) of
EVERY FK/O2O found, then fails (non-zero exit) only on a NEW violation
(missing on_delete, an un-justified/un-allowlisted CASCADE, a SET_NULL
without null=True or on a tenant field, or — in --financial mode — a new
un-reviewed financial-target CASCADE/SET_NULL).

Usage:
    python scripts/check_on_delete.py             # base checks (YDATA1/3)
    python scripts/check_on_delete.py --financial # + financial sweep (YDATA2)
"""
from __future__ import annotations

import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DJANGO_CORE = ROOT / "backend" / "django_core"
ALLOWLIST_PATH = ROOT / "scripts" / "on_delete_allowlist.txt"
# YDATA2 — the checked-in audit doc IS the baseline: a file:line already
# present in it (as committed) is reviewed debt (sweep records the gap,
# does not presume any one FK is wrong — fixes are ERROR_PLAN material); a
# NEW file:line absent from it fails CI. Regenerated in full every run.
FINANCIAL_AUDIT_DOC = ROOT / "docs" / "on-delete-financial-audit.md"

FK_CALL_NAMES = {"ForeignKey", "OneToOneField"}

# YDATA2 — targets considered "money/audit-bearing" (last dotted component
# of the FK target, case-sensitive to the model class name).
FINANCIAL_TARGET_NAMES = {
    "Devis", "Facture", "BonCommande", "Paiement", "Avoir", "Company",
    "Produit",
}
# YDATA3 — FK field names that identify the tenant/owner scope: SET_NULL on
# one of these would silently de-scope the row.
TENANT_FIELD_NAMES = {"company", "societe", "owner", "responsable"}


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


def _on_delete_repr(value):
    """Best-effort textual form of the on_delete= value, e.g. 'CASCADE'."""
    if isinstance(value, ast.Attribute):
        return value.attr
    if isinstance(value, ast.Name):
        return value.id
    if isinstance(value, ast.Call):
        return _call_name(value) or "?"
    return "?"


def _target_repr(node):
    """First positional arg (the FK target), best-effort."""
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


def _has_justification_comment(source_lines, lineno):
    """A `# on_delete: <reason>` comment on the field's own line or within
    the following 2 lines (call args often span multiple lines)."""
    for offset in range(0, 3):
        idx = lineno - 1 + offset
        if 0 <= idx < len(source_lines) and "# on_delete:" in source_lines[idx]:
            return True
    return False


def _is_financial_target(target: str) -> bool:
    last = target.rsplit(".", 1)[-1]
    return last in FINANCIAL_TARGET_NAMES


def _iter_fk_assignments(tree):
    """Single pass: yields (model_name, field_name, call_node) for every
    `field = models.ForeignKey(...)`/`OneToOneField(...)` (direct or
    annotated) assignment found in any class body — O(N) instead of the
    naive O(N^2) "walk the whole tree per call node" approach (which timed
    out on the largest models.py files, ~230 FK fields x thousands of
    nodes)."""
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
            if _call_name(value) not in FK_CALL_NAMES:
                continue
            yield classdef.name, target.id, value


def check_file(path: Path):
    """Returns (all_rows, findings). all_rows = every FK/O2O (audit table,
    tuples of (rel_path, lineno, model, field, target, policy, null)).
    findings = (code, message) for violations only."""
    source = path.read_text(encoding="utf-8")
    lines = source.splitlines()
    try:
        tree = ast.parse(source, filename=str(path))
    except SyntaxError as exc:
        return [], [("PARSE_ERROR", f"could not parse: {exc}")]

    all_rows = []
    findings = []

    for model, field, node in _iter_fk_assignments(tree):
        target = _target_repr(node)
        lineno = node.lineno
        on_delete_kw = _kwarg(node, "on_delete")
        null_kw = _kwarg(node, "null")
        is_nullable = (
            isinstance(null_kw, ast.Constant) and null_kw.value is True
        )

        if on_delete_kw is None:
            policy = "MISSING"
            findings.append((
                "MISSING_ON_DELETE",
                f"{model}.{field} (-> {target}) at line {lineno}: "
                "ForeignKey/OneToOneField without an explicit on_delete=.",
            ))
        else:
            policy = _on_delete_repr(on_delete_kw)
            allow_key = f"{_rel(path)}:{lineno}"

            if policy == "CASCADE":
                justified = _has_justification_comment(lines, lineno)
                if not justified and allow_key not in _ALLOW_CACHE:
                    findings.append((
                        "UNJUSTIFIED_CASCADE",
                        f"{model}.{field} (-> {target}) at line {lineno}: "
                        "on_delete=CASCADE with no inline "
                        "'# on_delete: <reason>' comment and not in "
                        "scripts/on_delete_allowlist.txt.",
                    ))

            if policy == "SET_NULL":
                # YDATA3 — SET_NULL requires null=True, and must never be on
                # a tenant/owner-identity field (would silently de-scope the
                # row on a cross-tenant-safe delete elsewhere). Reuses the
                # SAME on_delete_allowlist.txt as the CASCADE check (YDATA3's
                # Files: list adds no second allowlist) so a reviewed
                # pre-existing case is silenced, a NEW one is not.
                if not is_nullable and allow_key not in _ALLOW_CACHE:
                    findings.append((
                        "SET_NULL_WITHOUT_NULLABLE",
                        f"{model}.{field} (-> {target}) at line {lineno}: "
                        "on_delete=SET_NULL without null=True on the same "
                        "field (guaranteed migration/runtime failure).",
                    ))
                if field in TENANT_FIELD_NAMES and allow_key not in _ALLOW_CACHE:
                    findings.append((
                        "SET_NULL_ON_TENANT_FIELD",
                        f"{model}.{field} (-> {target}) at line {lineno}: "
                        "on_delete=SET_NULL on a tenant/owner-identity "
                        "field would silently de-scope the row.",
                    ))

            if _FINANCIAL_MODE and policy in ("CASCADE", "SET_NULL") \
                    and _is_financial_target(target) \
                    and allow_key not in _FINANCIAL_DEBT_CACHE:
                findings.append((
                    "FINANCIAL_FK_NOT_PROTECT",
                    f"{model}.{field} (-> {target}) at line {lineno}: "
                    f"on_delete={policy} targets a money/audit-bearing "
                    "model and was not already recorded in "
                    "docs/on-delete-financial-audit.md (YDATA2 — sweep "
                    "records the gap, does not presume this one FK is "
                    "wrong; commit the regenerated doc after review).",
                ))

        all_rows.append(
            (_rel(path), lineno, model, field, target, policy, is_nullable))

    return all_rows, findings


_ALLOW_CACHE = set()
_FINANCIAL_MODE = False
_FINANCIAL_DEBT_CACHE = set()


def _load_financial_debt():
    """The file:line column of the CHECKED-IN docs/on-delete-financial-audit.md
    IS the baseline (parsed BEFORE this run regenerates the doc)."""
    if not FINANCIAL_AUDIT_DOC.exists():
        return set()
    out = set()
    for line in FINANCIAL_AUDIT_DOC.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line.startswith("| `"):
            continue
        key = line.split("`", 2)[1]
        out.add(key)
    return out


def _write_financial_audit_doc(rows):
    """YDATA2 — docs/on-delete-financial-audit.md: every FK targeting a
    money/audit-bearing model, with its current on_delete policy."""
    fin_rows = [r for r in rows if _is_financial_target(r[4])]
    lines = [
        "# Audit on_delete — FK vers un modèle financier/audit (YDATA2)",
        "",
        "Généré par `python scripts/check_on_delete.py --financial`. Ce "
        "tableau recense l'ÉCART (une politique `CASCADE`/`SET_NULL` sur un "
        "FK financier n'est pas présumée fautive — revue au cas par cas, "
        "correctifs = ERROR_PLAN).",
        "",
        "| Fichier:ligne | Modèle.champ | Cible | Politique |",
        "|---|---|---|---|",
    ]
    for rel, lineno, model, field, target, policy, _null in sorted(fin_rows):
        lines.append(
            f"| `{rel}:{lineno}` | {model}.{field} | {target} | {policy} |")
    FINANCIAL_AUDIT_DOC.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main(argv):
    global _ALLOW_CACHE, _FINANCIAL_MODE, _FINANCIAL_DEBT_CACHE
    _FINANCIAL_MODE = "--financial" in argv
    _ALLOW_CACHE = _load_allowlist()
    _FINANCIAL_DEBT_CACHE = _load_financial_debt()

    all_rows = []
    report_lines = []

    for path in _iter_model_files():
        rows, findings = check_file(path)
        all_rows.extend(rows)
        for code, message in findings:
            report_lines.append(f"{_rel(path)}: [{code}] {message}")

    print(f"check_on_delete: scanned {len(all_rows)} ForeignKey/OneToOneField "
          f"declaration(s) across {DJANGO_CORE.name}/apps + core + "
          "authentication.")
    print("file:line  model.field -> target  [policy]")
    for rel, lineno, model, field, target, policy, _null in all_rows:
        print(f"  {rel}:{lineno}  {model}.{field} -> {target}  [{policy}]")

    if _FINANCIAL_MODE:
        _write_financial_audit_doc(all_rows)
        print(f"\ncheck_on_delete --financial: wrote {_rel(FINANCIAL_AUDIT_DOC)}")

    if report_lines:
        print("\ncheck_on_delete: violation(s) found:")
        for line in report_lines:
            print(f"  - {line}")
        print(
            "\nFix by adding on_delete= (required); for a NEW CASCADE add an "
            "inline '# on_delete: <reason>' comment or list the file:line in "
            "scripts/on_delete_allowlist.txt; for SET_NULL, set null=True "
            "and never target a company/societe/owner/responsable field; "
            "for a NEW financial-target CASCADE/SET_NULL (--financial mode) "
            "review it and commit the regenerated "
            "docs/on-delete-financial-audit.md."
        )
        return 1

    print("\ncheck_on_delete: OK — no violation found.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
