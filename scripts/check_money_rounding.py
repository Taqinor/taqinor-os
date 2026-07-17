"""YDATA8 — advisory guard: `round()` on a money-looking value in a
pricing/tax module should use `core.money.quantize_mad` instead.

DB-free, AST-only. Scans ONLY the pricing/tax modules named by the task
spec (`apps/ventes/services.py`, `apps/ventes/quote_engine/builder.py`,
`apps/compta/services.py`) for a call to the builtin `round(...)` whose
FIRST argument's source text matches the money-semantic name regex (same
family as ``scripts/check_money_fields.py``: prix/montant/total/_ht/_ttc/
tva/remise/acompte/solde/amount/price/cost/cout/honoraire/penalite).

v1 = ADVISORY (per spec): this does NOT rewrite any existing logic. Every
site found today is in ``BASELINE_ALLOWLIST`` below (generated once from
the current repo state) so the guard does not block on pre-existing code —
it fails CI only on a NEW `round()` site (not in the baseline) that looks
like it is rounding money.

Usage:
    python scripts/check_money_rounding.py
"""
from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DJANGO_CORE = ROOT / "backend" / "django_core"

# Baseline generated once from the current repo state (2026-07-12) — every
# round() site already flagged today, so the guard does not block on
# pre-existing code (advisory v1, per spec: correctifs = ERROR_PLAN). No
# separate allowlist FILE (not in this task's Files: list) — the baseline
# lives here, in the one script file the task does declare. A NEW site not
# in this set fails CI.
BASELINE_ALLOWLIST = {
    "backend/django_core/apps/ventes/services.py:302",
    "backend/django_core/apps/ventes/services.py:305",
    "backend/django_core/apps/ventes/quote_engine/builder.py:568",
    "backend/django_core/apps/ventes/quote_engine/builder.py:570",
    "backend/django_core/apps/ventes/quote_engine/builder.py:597",
    "backend/django_core/apps/ventes/quote_engine/builder.py:172",
    "backend/django_core/apps/ventes/quote_engine/builder.py:173",
    "backend/django_core/apps/ventes/quote_engine/builder.py:473",
    "backend/django_core/apps/ventes/quote_engine/builder.py:595",
    "backend/django_core/apps/ventes/quote_engine/builder.py:754",
    "backend/django_core/apps/ventes/quote_engine/builder.py:1268",
    "backend/django_core/apps/ventes/quote_engine/builder.py:741",
    "backend/django_core/apps/ventes/quote_engine/builder.py:1262",
    # compta/services.py entries re-based (NTFIN allocations/engagement batch,
    # 2026-07-17, +2 lines above them from NTFIN20-25 model imports; same
    # NPS/ROI/percentage round() sites, unmoved logic, verified uniform +2 line
    # shift, NOT new sites — bug-class #34).
    "backend/django_core/apps/compta/services.py:9592",
    "backend/django_core/apps/compta/services.py:7536",
    "backend/django_core/apps/compta/services.py:7539",
    "backend/django_core/apps/compta/services.py:12060",
    "backend/django_core/apps/compta/services.py:12462",
    "backend/django_core/apps/compta/services.py:8845",
    "backend/django_core/apps/compta/services.py:8849",
    # XSAL14 (2026-07-16) — builder.py edits shifted existing display-round
    # sites; re-based 1:1 (premium engine, sanctioned rounding).
    "backend/django_core/apps/ventes/quote_engine/builder.py:1285",
    "backend/django_core/apps/ventes/quote_engine/builder.py:1291",
    "backend/django_core/apps/ventes/quote_engine/builder.py:1344",
    "backend/django_core/apps/ventes/quote_engine/builder.py:1345",
    "backend/django_core/apps/ventes/quote_engine/builder.py:496",
    "backend/django_core/apps/ventes/quote_engine/builder.py:591",
    "backend/django_core/apps/ventes/quote_engine/builder.py:593",
    "backend/django_core/apps/ventes/quote_engine/builder.py:618",
    "backend/django_core/apps/ventes/quote_engine/builder.py:620",
    "backend/django_core/apps/ventes/quote_engine/builder.py:764",
    "backend/django_core/apps/ventes/quote_engine/builder.py:777",
    # QX ROUND 7 (2026-07-16) — QX43/QX50 builder.py edits shifted existing
    # display-round sites again; re-based 1:1 (premium engine, sanctioned
    # whole-MAD display rounding — rule #4 vendored engine, not new logic).
    "backend/django_core/apps/ventes/quote_engine/builder.py:175",
    "backend/django_core/apps/ventes/quote_engine/builder.py:176",
    "backend/django_core/apps/ventes/quote_engine/builder.py:508",
    "backend/django_core/apps/ventes/quote_engine/builder.py:603",
    "backend/django_core/apps/ventes/quote_engine/builder.py:605",
    "backend/django_core/apps/ventes/quote_engine/builder.py:630",
    "backend/django_core/apps/ventes/quote_engine/builder.py:632",
    "backend/django_core/apps/ventes/quote_engine/builder.py:776",
    "backend/django_core/apps/ventes/quote_engine/builder.py:789",
    "backend/django_core/apps/ventes/quote_engine/builder.py:1301",
    "backend/django_core/apps/ventes/quote_engine/builder.py:1307",
    "backend/django_core/apps/ventes/quote_engine/builder.py:1360",
    "backend/django_core/apps/ventes/quote_engine/builder.py:1361",
}

TARGET_FILES = [
    DJANGO_CORE / "apps" / "ventes" / "services.py",
    DJANGO_CORE / "apps" / "ventes" / "quote_engine" / "builder.py",
    DJANGO_CORE / "apps" / "compta" / "services.py",
]

MONEY_NAME_RE = re.compile(
    r"(prix|montant|total|_ht|_ttc|tva|remise|acompte|solde|amount|price|"
    r"cost|cout|honoraire|penalite)",
    re.IGNORECASE,
)


def _rel(path: Path) -> str:
    return str(path.relative_to(ROOT)).replace("\\", "/")


def _arg_source(node):
    """Best-effort textual form of the round() call's first argument."""
    try:
        return ast.unparse(node)
    except Exception:
        return ""


def check_file(path: Path):
    source = path.read_text(encoding="utf-8")
    try:
        tree = ast.parse(source, filename=str(path))
    except SyntaxError as exc:
        return [], [("PARSE_ERROR", f"could not parse: {exc}")]

    rows = []
    findings = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if not isinstance(node.func, ast.Name) or node.func.id != "round":
            continue
        if not node.args:
            continue
        arg_src = _arg_source(node.args[0])
        if not MONEY_NAME_RE.search(arg_src):
            continue
        lineno = node.lineno
        rows.append((_rel(path), lineno, arg_src))
        allow_key = f"{_rel(path)}:{lineno}"
        if allow_key not in BASELINE_ALLOWLIST:
            findings.append((
                "MONEY_ROUND_INSTEAD_OF_QUANTIZE",
                f"line {lineno}: round({arg_src[:60]}...) looks like a "
                "monetary value — prefer core.money.quantize_mad() (see "
                "docs/money-convention.md) and add its file:line to "
                "BASELINE_ALLOWLIST in this script if reviewed.",
            ))
    return rows, findings


def main(argv):
    all_rows = []
    report_lines = []
    for path in TARGET_FILES:
        if not path.exists():
            continue
        rows, findings = check_file(path)
        all_rows.extend(rows)
        for code, message in findings:
            report_lines.append(f"{_rel(path)}: [{code}] {message}")

    print(f"check_money_rounding: {len(all_rows)} round() site(s) on a "
          "money-looking value found in pricing/tax modules.")
    for rel, lineno, arg_src in all_rows:
        print(f"  {rel}:{lineno}  round({arg_src[:60]})")

    if report_lines:
        print("\ncheck_money_rounding: NEW site(s) not in the baseline "
              "allowlist:")
        for line in report_lines:
            print(f"  - {line}")
        return 1

    print("\ncheck_money_rounding: OK (advisory — all sites are baselined).")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
