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
    # 2026-08-18 — SIX ENTRÉES MORTES RETIRÉES (`ventes/services.py` :381,
    # :384, :397, :400, :1822, :1979 — anciens recalages NTUX13 puis
    # PV14/PV16/PV18). Relecture ligne à ligne de l'arbre courant : AUCUNE de
    # ces six lignes ne porte de `round()`. Les quatre seuls sites que le
    # détecteur AST retient dans ce fichier sont :687, :690, :2135 et :2305
    # (surface m² / kWc), déjà listés plus bas. Une entrée morte n'est pas
    # neutre : elle PRÉ-AUTORISE en silence un futur `round(total_ht, 2)`
    # inséré à cette ligne, c.-à-d. exactement l'arrondi monétaire hors
    # `quantize_mad` que cette garde existe pour faire relire.
    # 2026-08-19 — DIX ENTRÉES RECALÉES (mêmes formules, lignes décalées par
    # la garde au-mètre de services.py [+15] et le contrat factures réelles +
    # le barème société de builder.py [+21/+45]) : 935→950, 938→953,
    # 2456→2471, 2523→2538 ; builder 1112→1133, 1125→1146, 1777→1822,
    # 1783→1828, 1836→1881, 1837→1882. Vérifié formule par formule.
    "backend/django_core/apps/ventes/quote_engine/builder.py:1822",  # QJ29 multi-villa ×N (réécrit PVUNI, formule préexistante revue)
    "backend/django_core/apps/ventes/quote_engine/builder.py:1881",  # total_ttc ligne gamme (réécrit PVUNI, formule préexistante revue)
    "backend/django_core/apps/ventes/quote_engine/builder.py:628",
    "backend/django_core/apps/ventes/quote_engine/builder.py:630",
    "backend/django_core/apps/ventes/quote_engine/builder.py:686",
    "backend/django_core/apps/ventes/quote_engine/builder.py:167",
    "backend/django_core/apps/ventes/quote_engine/builder.py:190",
    "backend/django_core/apps/ventes/quote_engine/builder.py:533",
    "backend/django_core/apps/ventes/quote_engine/builder.py:590",
    "backend/django_core/apps/ventes/quote_engine/builder.py:819",
    "backend/django_core/apps/ventes/quote_engine/builder.py:1408",
    "backend/django_core/apps/ventes/quote_engine/builder.py:799",
    "backend/django_core/apps/ventes/quote_engine/builder.py:1286",
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
    "backend/django_core/apps/ventes/quote_engine/builder.py:1498",
    "backend/django_core/apps/ventes/quote_engine/builder.py:1444",
    "backend/django_core/apps/ventes/quote_engine/builder.py:1497",
    "backend/django_core/apps/ventes/quote_engine/builder.py:1438",
    "backend/django_core/apps/ventes/quote_engine/builder.py:556",
    "backend/django_core/apps/ventes/quote_engine/builder.py:615",
    "backend/django_core/apps/ventes/quote_engine/builder.py:653",
    "backend/django_core/apps/ventes/quote_engine/builder.py:683",
    "backend/django_core/apps/ventes/quote_engine/builder.py:685",
    "backend/django_core/apps/ventes/quote_engine/builder.py:829",
    "backend/django_core/apps/ventes/quote_engine/builder.py:870",
    # QX ROUND 7 (2026-07-16) — QX43/QX50 builder.py edits shifted existing
    # display-round sites again; re-based 1:1 (premium engine, sanctioned
    # whole-MAD display rounding — rule #4 vendored engine, not new logic).
    "backend/django_core/apps/ventes/quote_engine/builder.py:192",
    "backend/django_core/apps/ventes/quote_engine/builder.py:193",
    "backend/django_core/apps/ventes/quote_engine/builder.py:504",
    "backend/django_core/apps/ventes/quote_engine/builder.py:663",
    "backend/django_core/apps/ventes/quote_engine/builder.py:631",
    "backend/django_core/apps/ventes/quote_engine/builder.py:695",
    "backend/django_core/apps/ventes/quote_engine/builder.py:631",
    "backend/django_core/apps/ventes/quote_engine/builder.py:841",
    "backend/django_core/apps/ventes/quote_engine/builder.py:810",
    "backend/django_core/apps/ventes/quote_engine/builder.py:1514",
    "backend/django_core/apps/ventes/quote_engine/builder.py:1460",
    "backend/django_core/apps/ventes/quote_engine/builder.py:1382",
    "backend/django_core/apps/ventes/quote_engine/builder.py:1454",
    # QRES (2026-07-18) puis PV11/PV46/PV77 (fiche wattage, annexe technique,
    # bloc bankable) — les MÊMES arrondis d'affichage déjà revus, re-décalés.
    # QRES (2026-07-18) — les blocs hypothèses/tarif/photo-toiture ajoutés dans
    # builder.py ont décalé les MÊMES arrondis d'affichage existants (déjà
    # revus : PU/ROI/TVA affichés, jamais un calcul monétaire persisté).
    "backend/django_core/apps/ventes/quote_engine/builder.py:323",
    "backend/django_core/apps/ventes/quote_engine/builder.py:324",
    "backend/django_core/apps/ventes/quote_engine/builder.py:686",
    "backend/django_core/apps/ventes/quote_engine/builder.py:781",
    "backend/django_core/apps/ventes/quote_engine/builder.py:783",
    "backend/django_core/apps/ventes/quote_engine/builder.py:808",
    "backend/django_core/apps/ventes/quote_engine/builder.py:789",
    "backend/django_core/apps/ventes/quote_engine/builder.py:1018",
    "backend/django_core/apps/ventes/quote_engine/builder.py:1031",
    # PV84 (chemin_proposition — nom du client dans le lien) — l'import
    # chemin_proposition + son commentaire ajoutés au bloc "signer" ont
    # décalé les MÊMES 4 arrondis d'affichage (PU/total ligne) de +2 lignes ;
    # aucune logique déplacée, aucun NOUVEAU site — bug-class #34.
    "backend/django_core/apps/ventes/quote_engine/builder.py:1714",
    "backend/django_core/apps/ventes/quote_engine/builder.py:1660",
    "backend/django_core/apps/ventes/quote_engine/builder.py:1713",
    "backend/django_core/apps/ventes/quote_engine/builder.py:1654",
    # PV86 (2026-08-15, « la seule vérité est le devis ») — le bloc qui exige
    # qu'une alternative soit DÉCLARÉE avant de rendre deux options a inséré
    # 46 lignes dans builder.py : les MÊMES arrondis d'affichage (HT brut,
    # TTC exact, ROI/prix-kWc, ×N villas, total de ligne d'option) glissent
    # tous de +46, à l'identique. Vérifié : le diff n'ajoute AUCUN round() —
    # aucun NOUVEAU site, simple re-calage file:line (bug-class #34).
    "backend/django_core/apps/ventes/quote_engine/builder.py:827",
    "backend/django_core/apps/ventes/quote_engine/builder.py:868",
    "backend/django_core/apps/ventes/quote_engine/builder.py:1064",
    "backend/django_core/apps/ventes/quote_engine/builder.py:1084",
    "backend/django_core/apps/ventes/quote_engine/builder.py:1672",
    "backend/django_core/apps/ventes/quote_engine/builder.py:1706",
    "backend/django_core/apps/ventes/quote_engine/builder.py:1828",
    "backend/django_core/apps/ventes/quote_engine/builder.py:1700",
    # GAMMES (2026-08-18, offre à deux gammes) — RE-CALAGE file:line, PAS de
    # nouveau site (bug-class #34). Deux insertions purement additives :
    #   * `apps/ventes/services.py` — le bloc de services « gamme »
    #     (creer_variante_gamme / regler_envoi_gamme…) inséré AVANT
    #     `create_devis_from_reserve` décale tout ce qui suit ;
    #   * `quote_engine/builder.py` — `_line_to_item` porte deux clés de plus
    #     (`garantie_mois` / `garantie_production_mois`, durées catalogue qui
    #     alimentent la bande « Nos garanties »).
    # Vérifié : aucun des deux diffs n'ajoute un seul `round()` — ce sont les
    # MÊMES arrondis d'AFFICHAGE (PU/HT/TVA/TTC du moteur, kWc/surface des
    # services), simplement déplacés. Lignes relues sur l'arbre courant.
    # PVSYNC/PVOND (2026-08-18) — RE-CALAGE file:line, PAS de nouveau site
    # (bug-class #34). Deux insertions purement additives dans
    # `apps/ventes/services.py` : le garde batterie data-driven (avant
    # `extract_roof_config`) et le bloc de resynchronisation événementielle
    # (après `sync_devis_from_layout`). Vérifié : le diff n'ajoute AUCUN
    # `round()` — ce sont les MÊMES arrondis d'AFFICHAGE (surface m², kWc,
    # jamais un montant), simplement déplacés. Lignes relues sur l'arbre
    # courant : 599→687, 602→690, 2038→2135, 2197→2305.
    # REVUE 2026-08-18 (garde batterie corrigé + verrou de complétude backend +
    # transparence resync + bordereau→devis) — RE-CALAGE file:line, PAS de
    # nouveau site (bug-class #34). Insertions purement additives dans
    # `apps/ventes/services.py` : `_onduleur_complet`/
    # `_filtrer_onduleurs_complets` et la docstring corrigée de
    # `_batterie_compatible` (avant les deux round() de surface/kWc), puis
    # `avertissement_vivier_batterie_vide`, le marqueur `resync_apres_envoi` et
    # les helpers de rafraîchissement bordereau→devis. Vérifié par relecture :
    # le diff n'ajoute AUCUN `round()` — ce sont les MÊMES arrondis
    # d'AFFICHAGE (surface m², kWc ; jamais un montant), simplement déplacés.
    # Lignes relues sur l'arbre courant : 687→753, 690→756, 2135→2263,
    # 2305→2442.
    # U3 (20/08/2026) — MÊMES quatre sites, recalés après le déplacement de
    # lignes de `services.py` (la composition résidentielle a gagné les règles
    # câbles/marques/ordre). Aucun n'est monétaire : ce sont une surface de
    # toit, une puissance en kWc et deux dérivations kWc = panneaux × Wc.
    "backend/django_core/apps/ventes/services.py:1033",
    "backend/django_core/apps/ventes/services.py:1036",
    "backend/django_core/apps/ventes/services.py:2817",
    "backend/django_core/apps/ventes/services.py:2884",
    "backend/django_core/apps/ventes/quote_engine/builder.py:387",
    "backend/django_core/apps/ventes/quote_engine/builder.py:388",
    "backend/django_core/apps/ventes/quote_engine/builder.py:727",
    "backend/django_core/apps/ventes/quote_engine/builder.py:840",
    "backend/django_core/apps/ventes/quote_engine/builder.py:842",
    "backend/django_core/apps/ventes/quote_engine/builder.py:895",
    "backend/django_core/apps/ventes/quote_engine/builder.py:897",
    "backend/django_core/apps/ventes/quote_engine/builder.py:1133",
    "backend/django_core/apps/ventes/quote_engine/builder.py:1146",
    # QXMT (2026-08-18) — le bloc « un dossier MT ne porte jamais un chiffre
    # BT » (+36 lignes, inséré APRÈS le calcul ROI, avant QF2) décale les
    # QUATRE arrondis d'affichage qui le suivent (montant de TVA ×N villas,
    # total d'affichage multi, total HT/TTC d'une ligne d'option) : 1579→1615,
    # 1585→1621, 1638→1674, 1639→1675. Décalage UNIFORME, aucune logique
    # déplacée, aucun NOUVEAU `round()` — bug-class #34. Les neuf sites
    # au-dessus (300…985) sont AVANT l'insertion et ne bougent pas.
    "backend/django_core/apps/ventes/quote_engine/builder.py:1809",
    "backend/django_core/apps/ventes/quote_engine/builder.py:1755",
    "backend/django_core/apps/ventes/quote_engine/builder.py:2110",
    "backend/django_core/apps/ventes/quote_engine/builder.py:1749",
    # Z1/Z2 (20/08/2026) — RE-CALAGE file:line, PAS de nouveau site
    # (bug-class #34), et un site MONÉTAIRE EN MOINS. Le bloc « batterie de
    # synthèse » de `build_quote_data` a été SUPPRIMÉ (ordre fondateur : aucun
    # composant ni prix inventé sur un document client) ; il portait le seul
    # round() vraiment monétaire du lot,
    # `round(synth["prix_unit_ttc"] / (1 + taux/100), 2)` — il n'existe plus.
    # Les commentaires Z1/Z2 ajoutés décalent ensuite uniformément les arrondis
    # d'AFFICHAGE qui suivent (+26 puis +45 lignes). PREUVE DE CONTENU (script
    # de recalage, chaque ligne retrouvée mot pour mot sur HEAD) :
    #   868→903 ht_brut · 870→905 ht_net · 895→930 tva_amt · 897→932 ttc_exact
    #   1133→1168 roi_s · 1146→1181 prix_kwc · 1822→1876 montant TVA ×N
    #   1828→1882 display_total_multi · 1881→1935 total_ht · 1882→1936 total_ttc
    # (336/337 sont AVANT toute insertion et ne bougent pas.)
    # 2026-08-20 — LANE MOTEUR (M1-M11/Q1-Q8) : DOUZE ENTRÉES RECALÉES,
    # zéro ajout hors celle documentée juste dessous. Le rebasage sur la
    # base Z+W+N+O et les correctifs de la lane ont décalé builder.py de
    # ~+107 à +228 lignes selon la zone. Chaque numéro a été retrouvé PAR
    # PREUVE DE CONTENU (la ligne de base et la nouvelle portent la MÊME
    # expression, à la lettre), jamais par un décalage supposé :
    #   336→387 pu_ht · 337→388 pu_ttc · 903→1010 ht_brut · 905→1012
    #   ht_net · 930→1037 tva_amt · 932→1039 ttc_exact · 1168→1295 roi_s
    #   1181→1308 prix_kwc · 1876→2104 montant TVA ×N · 1882→2110
    #   display_total_multi · 1935→2163 total_ht · 1936→2164 total_ttc.
    "backend/django_core/apps/ventes/quote_engine/builder.py:1010",
    # 2026-08-20 — Q1 (lane moteur) : NOUVEAU site relu. Somme TTC des
    # lignes onduleur d'une option (`_cout_onduleur`), qui devient la
    # provision de remplacement à l'année 12 — elle remplace un forfait
    # « 8 % du CAPEX ». Même unité et même arrondi float que les sites
    # voisins déjà listés de ce module (le moteur de devis travaille en
    # float de bout en bout ; `quantize_mad` est la convention des
    # modèles, pas de ce rendu). Valeur JAMAIS persistée : elle ne sert
    # qu'au tracé et à la ligne d'hypothèse.
    "backend/django_core/apps/ventes/quote_engine/builder.py:270",
    "backend/django_core/apps/ventes/quote_engine/builder.py:1012",
    "backend/django_core/apps/ventes/quote_engine/builder.py:1037",
    "backend/django_core/apps/ventes/quote_engine/builder.py:1039",
    "backend/django_core/apps/ventes/quote_engine/builder.py:1295",
    "backend/django_core/apps/ventes/quote_engine/builder.py:1308",
    "backend/django_core/apps/ventes/quote_engine/builder.py:2104",
    "backend/django_core/apps/ventes/quote_engine/builder.py:2110",
    "backend/django_core/apps/ventes/quote_engine/builder.py:2163",
    "backend/django_core/apps/ventes/quote_engine/builder.py:2164",
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
