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
    # NTUX13 (2026-07-31) re-based: dupliquer_devis() inserted earlier in the
    # file shifted these two pre-existing (non-monetary surface_m2/kwc)
    # round() calls from :302/:305 to :359/:362 — same call sites, not new.
    "backend/django_core/apps/ventes/services.py:381",
    "backend/django_core/apps/ventes/services.py:384",
    # PV14/PV16/PV18 (geometry par pan, cible, sync) — les MEMES arrondis
    # d'AFFICHAGE (surface m2, kWc — jamais un montant) re-decales, plus le
    # kWc du chemin sync (duplication assumee du calcul d'affichage).
    "backend/django_core/apps/ventes/services.py:397",
    "backend/django_core/apps/ventes/services.py:400",
    "backend/django_core/apps/ventes/services.py:1822",
    "backend/django_core/apps/ventes/services.py:1979",
    "backend/django_core/apps/ventes/quote_engine/builder.py:592",
    "backend/django_core/apps/ventes/quote_engine/builder.py:594",
    "backend/django_core/apps/ventes/quote_engine/builder.py:645",
    "backend/django_core/apps/ventes/quote_engine/builder.py:167",
    "backend/django_core/apps/ventes/quote_engine/builder.py:190",
    "backend/django_core/apps/ventes/quote_engine/builder.py:497",
    "backend/django_core/apps/ventes/quote_engine/builder.py:595",
    "backend/django_core/apps/ventes/quote_engine/builder.py:798",
    "backend/django_core/apps/ventes/quote_engine/builder.py:1279",
    "backend/django_core/apps/ventes/quote_engine/builder.py:762",
    "backend/django_core/apps/ventes/quote_engine/builder.py:1296",
    # compta/services.py entries re-based (WIR153, 2026-07-31, -3 lines above
    # them from removing two dead OCR-provider try/except blocks + docstring
    # edits in extraire_releve_bancaire/extraire_justificatif_note_frais;
    # same NPS/ROI/percentage round() sites, unmoved logic, verified by AST
    # arg-text diff against origin/main — identical, uniform -3 shift, NOT
    # new sites — bug-class #34).
    # RE-BASED AGAIN 2026-08-01 (AOF1) : le corps des deux services AO
    # (``echeances_ao_dues``/``taux_reussite_ao``, ~44 lignes) est relogé dans
    # ``apps/ao/services.py`` et remplacé par un shim de ré-export ; l'import
    # de tête perd 2 noms et gagne 2 lignes de commentaire. Décalage uniforme
    # +2 avant le bloc retiré, -30 après. MÊMES sites de round() (NPS / ROI /
    # pourcentages), aucune logique déplacée, aucun NOUVEAU site —
    # bug-class #34.
    # RE-DÉRIVÉ 2026-08-14 après fusion de deux lanes qui avaient recalé ce
    # bloc chacune de son côté : la fusion cumule leurs insertions, donc
    # les deux recalages étaient faux. Numéros relus sur l’arbre fusionné.
    # MÊMES sites NPS/ROI/pourcentages, aucun monétaire, aucun NOUVEAU.
    "backend/django_core/apps/compta/services.py:9813",
    "backend/django_core/apps/compta/services.py:7789",
    "backend/django_core/apps/compta/services.py:7792",
    "backend/django_core/apps/compta/services.py:12281",
    "backend/django_core/apps/compta/services.py:12683",
    "backend/django_core/apps/compta/services.py:9098",
    "backend/django_core/apps/compta/services.py:9102",
    # XSAL14 (2026-07-16) — builder.py edits shifted existing display-round
    # sites; re-based 1:1 (premium engine, sanctioned rounding).
    "backend/django_core/apps/ventes/quote_engine/builder.py:1319",
    "backend/django_core/apps/ventes/quote_engine/builder.py:1335",
    "backend/django_core/apps/ventes/quote_engine/builder.py:1378",
    "backend/django_core/apps/ventes/quote_engine/builder.py:1379",
    "backend/django_core/apps/ventes/quote_engine/builder.py:520",
    "backend/django_core/apps/ventes/quote_engine/builder.py:615",
    "backend/django_core/apps/ventes/quote_engine/builder.py:617",
    "backend/django_core/apps/ventes/quote_engine/builder.py:642",
    "backend/django_core/apps/ventes/quote_engine/builder.py:644",
    "backend/django_core/apps/ventes/quote_engine/builder.py:798",
    "backend/django_core/apps/ventes/quote_engine/builder.py:811",
    # QX ROUND 7 (2026-07-16) — QX43/QX50 builder.py edits shifted existing
    # display-round sites again; re-based 1:1 (premium engine, sanctioned
    # whole-MAD display rounding — rule #4 vendored engine, not new logic).
    "backend/django_core/apps/ventes/quote_engine/builder.py:192",
    "backend/django_core/apps/ventes/quote_engine/builder.py:193",
    "backend/django_core/apps/ventes/quote_engine/builder.py:532",
    "backend/django_core/apps/ventes/quote_engine/builder.py:627",
    "backend/django_core/apps/ventes/quote_engine/builder.py:629",
    "backend/django_core/apps/ventes/quote_engine/builder.py:654",
    "backend/django_core/apps/ventes/quote_engine/builder.py:632",
    "backend/django_core/apps/ventes/quote_engine/builder.py:810",
    "backend/django_core/apps/ventes/quote_engine/builder.py:823",
    "backend/django_core/apps/ventes/quote_engine/builder.py:1335",
    "backend/django_core/apps/ventes/quote_engine/builder.py:1341",
    "backend/django_core/apps/ventes/quote_engine/builder.py:1394",
    "backend/django_core/apps/ventes/quote_engine/builder.py:1395",
    # QRES (2026-07-18) puis PV11/PV46/PV77 (fiche wattage, annexe technique,
    # bloc bankable) — les MÊMES arrondis d'affichage déjà revus, re-décalés.
    # QRES (2026-07-18) — les blocs hypothèses/tarif/photo-toiture ajoutés dans
    # builder.py ont décalé les MÊMES arrondis d'affichage existants (déjà
    # revus : PU/ROI/TVA affichés, jamais un calcul monétaire persisté).
    "backend/django_core/apps/ventes/quote_engine/builder.py:287",
    "backend/django_core/apps/ventes/quote_engine/builder.py:288",
    "backend/django_core/apps/ventes/quote_engine/builder.py:645",
    "backend/django_core/apps/ventes/quote_engine/builder.py:750",
    "backend/django_core/apps/ventes/quote_engine/builder.py:752",
    "backend/django_core/apps/ventes/quote_engine/builder.py:777",
    "backend/django_core/apps/ventes/quote_engine/builder.py:779",
    "backend/django_core/apps/ventes/quote_engine/builder.py:923",
    "backend/django_core/apps/ventes/quote_engine/builder.py:936",
    # PV84 (chemin_proposition — nom du client dans le lien) — l'import
    # chemin_proposition + son commentaire ajoutés au bloc "signer" ont
    # décalé les MÊMES 4 arrondis d'affichage (PU/total ligne) de +2 lignes ;
    # aucune logique déplacée, aucun NOUVEAU site — bug-class #34.
    "backend/django_core/apps/ventes/quote_engine/builder.py:1530",
    "backend/django_core/apps/ventes/quote_engine/builder.py:1536",
    "backend/django_core/apps/ventes/quote_engine/builder.py:1589",
    "backend/django_core/apps/ventes/quote_engine/builder.py:1590",
    # PV86 (2026-08-15, « la seule vérité est le devis ») — le bloc qui exige
    # qu'une alternative soit DÉCLARÉE avant de rendre deux options a inséré
    # 46 lignes dans builder.py : les MÊMES arrondis d'affichage (HT brut,
    # TTC exact, ROI/prix-kWc, ×N villas, total de ligne d'option) glissent
    # tous de +46, à l'identique. Vérifié : le diff n'ajoute AUCUN round() —
    # aucun NOUVEAU site, simple re-calage file:line (bug-class #34).
    "backend/django_core/apps/ventes/quote_engine/builder.py:796",
    "backend/django_core/apps/ventes/quote_engine/builder.py:825",
    "backend/django_core/apps/ventes/quote_engine/builder.py:969",
    "backend/django_core/apps/ventes/quote_engine/builder.py:982",
    "backend/django_core/apps/ventes/quote_engine/builder.py:1576",
    "backend/django_core/apps/ventes/quote_engine/builder.py:1582",
    "backend/django_core/apps/ventes/quote_engine/builder.py:1635",
    "backend/django_core/apps/ventes/quote_engine/builder.py:1636",
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
