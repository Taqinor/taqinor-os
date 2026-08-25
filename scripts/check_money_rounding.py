"""YDATA8 â€” advisory guard: `round()` on a money-looking value in a
pricing/tax module should use `core.money.quantize_mad` instead.

DB-free, AST-only. Scans ONLY the pricing/tax modules named by the task
spec (`apps/ventes/services.py`, `apps/ventes/quote_engine/builder.py`,
`apps/compta/services.py`) for a call to the builtin `round(...)` whose
FIRST argument's source text matches the money-semantic name regex (same
family as ``scripts/check_money_fields.py``: prix/montant/total/_ht/_ttc/
tva/remise/acompte/solde/amount/price/cost/cout/honoraire/penalite).

v1 = ADVISORY (per spec): this does NOT rewrite any existing logic. Every
site found today is in ``BASELINE_ALLOWLIST`` below (generated once from
the current repo state) so the guard does not block on pre-existing code â€”
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

# Baseline generated once from the current repo state (2026-07-12) â€” every
# round() site already flagged today, so the guard does not block on
# pre-existing code (advisory v1, per spec: correctifs = ERROR_PLAN). No
# separate allowlist FILE (not in this task's Files: list) â€” the baseline
# lives here, in the one script file the task does declare. A NEW site not
# in this set fails CI.
BASELINE_ALLOWLIST = {
    # Rebase 2026-08-25 (L-2OPT) : 10 entrees builder.py decalees (+149..+181,
    # scalaires par option + comparatif + avec-first inseres en amont) et les 2
    # derivations de PUISSANCE de services.py (composition_deux_optimiseurs,
    # +~283 lignes). MEMES sites, MEMES expressions, aucun round() nouveau.

    # 2026-08-18 â€” SIX ENTRÃ‰ES MORTES RETIRÃ‰ES (`ventes/services.py` :381,
    # :384, :397, :400, :1822, :1979 â€” anciens recalages NTUX13 puis
    # PV14/PV16/PV18). Relecture ligne Ã  ligne de l'arbre courant : AUCUNE de
    # ces six lignes ne porte de `round()`. Les quatre seuls sites que le
    # dÃ©tecteur AST retient dans ce fichier sont :687, :690, :2135 et :2305
    # (surface mÂ² / kWc), dÃ©jÃ  listÃ©s plus bas. Une entrÃ©e morte n'est pas
    # neutre : elle PRÃ‰-AUTORISE en silence un futur `round(total_ht, 2)`
    # insÃ©rÃ© Ã  cette ligne, c.-Ã -d. exactement l'arrondi monÃ©taire hors
    # `quantize_mad` que cette garde existe pour faire relire.
    # 2026-08-19 â€” DIX ENTRÃ‰ES RECALÃ‰ES (mÃªmes formules, lignes dÃ©calÃ©es par
    # la garde au-mÃ¨tre de services.py [+15] et le contrat factures rÃ©elles +
    # le barÃ¨me sociÃ©tÃ© de builder.py [+21/+45]) : 935â†’950, 938â†’953,
    # 2456â†’2471, 2523â†’2538 ; builder 1112â†’1133, 1125â†’1146, 1777â†’1822,
    # 1783â†’1828, 1836â†’1881, 1837â†’1882. VÃ©rifiÃ© formule par formule.
    # apps/ventes/services.py â€” 4 dÃ©rivations de PUISSANCE (kWc), pas d'argent.
    # RecalÃ©es par CONTENU sur l'arbre INTÃ‰GRÃ‰ du 24/08/2026 (L-TRI +49 et
    # L-FORFAIT +84 lignes ont dÃ©calÃ© le fichier ; leurs recalages faits
    # chacun dans son worktree se contredisaient â€” vraies lignes relues).
    # 2026-08-24 (soir) â€” DEUX ENTRÃ‰ES RECALÃ‰ES sur l'arbre intÃ©grÃ© L-2OPT
    # (+~26/+31 lignes de prÃ©servation Â« Les deux Â» dans sync_devis_from_layout
    # au-dessus d'elles) : 3213â†’3239, 3300â†’3331. VÃ©rifiÃ© par contenu (mÃªmes
    # formules kWc `round(total_panneaux * watt / 1000.0, 3)`, main vs arbre).
    "backend/django_core/apps/ventes/services.py:1033",
    "backend/django_core/apps/ventes/services.py:1036",
    "backend/django_core/apps/ventes/services.py:3650",
    "backend/django_core/apps/ventes/services.py:3783",
    "backend/django_core/apps/ventes/quote_engine/builder.py:1906",  # QJ29 multi-villa Ã—N (rÃ©Ã©crit PVUNI, formule prÃ©existante revue)
    "backend/django_core/apps/ventes/quote_engine/builder.py:1926",  # total_ttc ligne gamme (rÃ©Ã©crit PVUNI, formule prÃ©existante revue)
    "backend/django_core/apps/ventes/quote_engine/builder.py:644",
    "backend/django_core/apps/ventes/quote_engine/builder.py:646",
    "backend/django_core/apps/ventes/quote_engine/builder.py:702",
    "backend/django_core/apps/ventes/quote_engine/builder.py:167",
    "backend/django_core/apps/ventes/quote_engine/builder.py:190",
    "backend/django_core/apps/ventes/quote_engine/builder.py:551",
    "backend/django_core/apps/ventes/quote_engine/builder.py:591",
    "backend/django_core/apps/ventes/quote_engine/builder.py:817",
    "backend/django_core/apps/ventes/quote_engine/builder.py:1445",
    "backend/django_core/apps/ventes/quote_engine/builder.py:815",
    "backend/django_core/apps/ventes/quote_engine/builder.py:1284",
    # compta/services.py re-based 2026-08-25 (numeros internationaux, -2 lignes
    # au-dela de ~8050 : normaliseurs Meta dedupliques raccourcis). Memes sites.
    # compta/services.py entries re-based (WIR153, 2026-07-31, -3 lines above
    # them from removing two dead OCR-provider try/except blocks + docstring
    # edits in extraire_releve_bancaire/extraire_justificatif_note_frais;
    # same NPS/ROI/percentage round() sites, unmoved logic, verified by AST
    # arg-text diff against origin/main â€” identical, uniform -3 shift, NOT
    # new sites â€” bug-class #34).
    # RE-BASED AGAIN 2026-08-01 (AOF1) : le corps des deux services AO
    # (``echeances_ao_dues``/``taux_reussite_ao``, ~44 lignes) est relogÃ© dans
    # ``apps/ao/services.py`` et remplacÃ© par un shim de rÃ©-export ; l'import
    # de tÃªte perd 2 noms et gagne 2 lignes de commentaire. DÃ©calage uniforme
    # +2 avant le bloc retirÃ©, -30 aprÃ¨s. MÃŠMES sites de round() (NPS / ROI /
    # pourcentages), aucune logique dÃ©placÃ©e, aucun NOUVEAU site â€”
    # bug-class #34.
    # RE-DÃ‰RIVÃ‰ 2026-08-14 aprÃ¨s fusion de deux lanes qui avaient recalÃ© ce
    # bloc chacune de son cÃ´tÃ© : la fusion cumule leurs insertions, donc
    # les deux recalages Ã©taient faux. NumÃ©ros relus sur lâ€™arbre fusionnÃ©.
    # MÃŠMES sites NPS/ROI/pourcentages, aucun monÃ©taire, aucun NOUVEAU.
    "backend/django_core/apps/compta/services.py:9811",
    "backend/django_core/apps/compta/services.py:7789",
    "backend/django_core/apps/compta/services.py:7792",
    "backend/django_core/apps/compta/services.py:12279",
    "backend/django_core/apps/compta/services.py:12681",
    "backend/django_core/apps/compta/services.py:9096",
    "backend/django_core/apps/compta/services.py:9100",
    # XSAL14 (2026-07-16) â€” builder.py edits shifted existing display-round
    # sites; re-based 1:1 (premium engine, sanctioned rounding).
    "backend/django_core/apps/ventes/quote_engine/builder.py:1496",
    "backend/django_core/apps/ventes/quote_engine/builder.py:1454",
    "backend/django_core/apps/ventes/quote_engine/builder.py:1495",
    "backend/django_core/apps/ventes/quote_engine/builder.py:1442",
    "backend/django_core/apps/ventes/quote_engine/builder.py:554",
    "backend/django_core/apps/ventes/quote_engine/builder.py:631",
    "backend/django_core/apps/ventes/quote_engine/builder.py:669",
    "backend/django_core/apps/ventes/quote_engine/builder.py:699",
    "backend/django_core/apps/ventes/quote_engine/builder.py:683",
    "backend/django_core/apps/ventes/quote_engine/builder.py:827",
    "backend/django_core/apps/ventes/quote_engine/builder.py:857",
    # QX ROUND 7 (2026-07-16) â€” QX43/QX50 builder.py edits shifted existing
    # display-round sites again; re-based 1:1 (premium engine, sanctioned
    # whole-MAD display rounding â€” rule #4 vendored engine, not new logic).
    "backend/django_core/apps/ventes/quote_engine/builder.py:190",
    "backend/django_core/apps/ventes/quote_engine/builder.py:191",
    "backend/django_core/apps/ventes/quote_engine/builder.py:502",
    "backend/django_core/apps/ventes/quote_engine/builder.py:679",
    "backend/django_core/apps/ventes/quote_engine/builder.py:647",
    "backend/django_core/apps/ventes/quote_engine/builder.py:711",
    "backend/django_core/apps/ventes/quote_engine/builder.py:647",
    "backend/django_core/apps/ventes/quote_engine/builder.py:826",
    "backend/django_core/apps/ventes/quote_engine/builder.py:802",
    "backend/django_core/apps/ventes/quote_engine/builder.py:1551",
    "backend/django_core/apps/ventes/quote_engine/builder.py:1458",
    "backend/django_core/apps/ventes/quote_engine/builder.py:1370",
    "backend/django_core/apps/ventes/quote_engine/builder.py:1491",
    # QRES (2026-07-18) puis PV11/PV46/PV77 (fiche wattage, annexe technique,
    # bloc bankable) â€” les MÃŠMES arrondis d'affichage dÃ©jÃ  revus, re-dÃ©calÃ©s.
    # QRES (2026-07-18) â€” les blocs hypothÃ¨ses/tarif/photo-toiture ajoutÃ©s dans
    # builder.py ont dÃ©calÃ© les MÃŠMES arrondis d'affichage existants (dÃ©jÃ 
    # revus : PU/ROI/TVA affichÃ©s, jamais un calcul monÃ©taire persistÃ©).
    "backend/django_core/apps/ventes/quote_engine/builder.py:321",
    "backend/django_core/apps/ventes/quote_engine/builder.py:322",
    "backend/django_core/apps/ventes/quote_engine/builder.py:702",
    "backend/django_core/apps/ventes/quote_engine/builder.py:795",
    "backend/django_core/apps/ventes/quote_engine/builder.py:795",
    "backend/django_core/apps/ventes/quote_engine/builder.py:824",
    "backend/django_core/apps/ventes/quote_engine/builder.py:805",
    "backend/django_core/apps/ventes/quote_engine/builder.py:1055",
    # 1068â†’1100 : recalage L-VAR du 24/08/2026, voir le bloc datÃ© plus bas ;
    # puis 1249â†’1282 (lane F1 du 26/08/2026, mÃªme bloc datÃ©).
    "backend/django_core/apps/ventes/quote_engine/builder.py:1282",
    # PV84 (chemin_proposition â€” nom du client dans le lien) â€” l'import
    # chemin_proposition + son commentaire ajoutÃ©s au bloc "signer" ont
    # dÃ©calÃ© les MÃŠMES 4 arrondis d'affichage (PU/total ligne) de +2 lignes ;
    # aucune logique dÃ©placÃ©e, aucun NOUVEAU site â€” bug-class #34.
    "backend/django_core/apps/ventes/quote_engine/builder.py:1798",
    "backend/django_core/apps/ventes/quote_engine/builder.py:1705",
    "backend/django_core/apps/ventes/quote_engine/builder.py:1797",
    "backend/django_core/apps/ventes/quote_engine/builder.py:1738",
    # PV86 (2026-08-15, Â« la seule vÃ©ritÃ© est le devis Â») â€” le bloc qui exige
    # qu'une alternative soit DÃ‰CLARÃ‰E avant de rendre deux options a insÃ©rÃ©
    # 46 lignes dans builder.py : les MÃŠMES arrondis d'affichage (HT brut,
    # TTC exact, ROI/prix-kWc, Ã—N villas, total de ligne d'option) glissent
    # tous de +46, Ã  l'identique. VÃ©rifiÃ© : le diff n'ajoute AUCUN round() â€”
    # aucun NOUVEAU site, simple re-calage file:line (bug-class #34).
    "backend/django_core/apps/ventes/quote_engine/builder.py:834",
    "backend/django_core/apps/ventes/quote_engine/builder.py:884",
    "backend/django_core/apps/ventes/quote_engine/builder.py:1103",
    "backend/django_core/apps/ventes/quote_engine/builder.py:1082",
    "backend/django_core/apps/ventes/quote_engine/builder.py:1756",
    "backend/django_core/apps/ventes/quote_engine/builder.py:1790",
    "backend/django_core/apps/ventes/quote_engine/builder.py:1873",
    "backend/django_core/apps/ventes/quote_engine/builder.py:1784",
    # GAMMES (2026-08-18, offre Ã  deux gammes) â€” RE-CALAGE file:line, PAS de
    # nouveau site (bug-class #34). Deux insertions purement additives :
    #   * `apps/ventes/services.py` â€” le bloc de services Â« gamme Â»
    #     (creer_variante_gamme / regler_envoi_gammeâ€¦) insÃ©rÃ© AVANT
    #     `create_devis_from_reserve` dÃ©cale tout ce qui suit ;
    #   * `quote_engine/builder.py` â€” `_line_to_item` porte deux clÃ©s de plus
    #     (`garantie_mois` / `garantie_production_mois`, durÃ©es catalogue qui
    #     alimentent la bande Â« Nos garanties Â»).
    # VÃ©rifiÃ© : aucun des deux diffs n'ajoute un seul `round()` â€” ce sont les
    # MÃŠMES arrondis d'AFFICHAGE (PU/HT/TVA/TTC du moteur, kWc/surface des
    # services), simplement dÃ©placÃ©s. Lignes relues sur l'arbre courant.
    # PVSYNC/PVOND (2026-08-18) â€” RE-CALAGE file:line, PAS de nouveau site
    # (bug-class #34). Deux insertions purement additives dans
    # `apps/ventes/services.py` : le garde batterie data-driven (avant
    # `extract_roof_config`) et le bloc de resynchronisation Ã©vÃ©nementielle
    # (aprÃ¨s `sync_devis_from_layout`). VÃ©rifiÃ© : le diff n'ajoute AUCUN
    # `round()` â€” ce sont les MÃŠMES arrondis d'AFFICHAGE (surface mÂ², kWc,
    # jamais un montant), simplement dÃ©placÃ©s. Lignes relues sur l'arbre
    # courant : 599â†’687, 602â†’690, 2038â†’2135, 2197â†’2305.
    # REVUE 2026-08-18 (garde batterie corrigÃ© + verrou de complÃ©tude backend +
    # transparence resync + bordereauâ†’devis) â€” RE-CALAGE file:line, PAS de
    # nouveau site (bug-class #34). Insertions purement additives dans
    # `apps/ventes/services.py` : `_onduleur_complet`/
    # `_filtrer_onduleurs_complets` et la docstring corrigÃ©e de
    # `_batterie_compatible` (avant les deux round() de surface/kWc), puis
    # `avertissement_vivier_batterie_vide`, le marqueur `resync_apres_envoi` et
    # les helpers de rafraÃ®chissement bordereauâ†’devis. VÃ©rifiÃ© par relecture :
    # le diff n'ajoute AUCUN `round()` â€” ce sont les MÃŠMES arrondis
    # d'AFFICHAGE (surface mÂ², kWc ; jamais un montant), simplement dÃ©placÃ©s.
    # Lignes relues sur l'arbre courant : 687â†’753, 690â†’756, 2135â†’2263,
    # 2305â†’2442.
    # U3 (20/08/2026) â€” MÃŠMES quatre sites, recalÃ©s aprÃ¨s le dÃ©placement de
    # lignes de `services.py` (la composition rÃ©sidentielle a gagnÃ© les rÃ¨gles
    # cÃ¢bles/marques/ordre). Aucun n'est monÃ©taire : ce sont une surface de
    # toit, une puissance en kWc et deux dÃ©rivations kWc = panneaux Ã— Wc.
    # 24/08/2026 â€” RE-CALAGE par CONTENU sur l'arbre INTÃ‰GRÃ‰ (L-TRI +49 lignes
    # ET L-FORFAIT +84 lignes dans apps/ventes/services.py, chacune avait
    # recalÃ© dans son propre worktree ; les deux mÃªmes dÃ©rivations
    # kWc = panneaux Ã— Wc vivent dÃ©sormais aux lignes 3213 et 3300).
    "backend/django_core/apps/ventes/quote_engine/builder.py:385",
    "backend/django_core/apps/ventes/quote_engine/builder.py:386",
    "backend/django_core/apps/ventes/quote_engine/builder.py:725",
    "backend/django_core/apps/ventes/quote_engine/builder.py:856",
    "backend/django_core/apps/ventes/quote_engine/builder.py:840",
    "backend/django_core/apps/ventes/quote_engine/builder.py:894",
    "backend/django_core/apps/ventes/quote_engine/builder.py:895",
    "backend/django_core/apps/ventes/quote_engine/builder.py:1131",
    "backend/django_core/apps/ventes/quote_engine/builder.py:1183",
    # QXMT (2026-08-18) â€” le bloc Â« un dossier MT ne porte jamais un chiffre
    # BT Â» (+36 lignes, insÃ©rÃ© APRÃˆS le calcul ROI, avant QF2) dÃ©cale les
    # QUATRE arrondis d'affichage qui le suivent (montant de TVA Ã—N villas,
    # total d'affichage multi, total HT/TTC d'une ligne d'option) : 1579â†’1615,
    # 1585â†’1621, 1638â†’1674, 1639â†’1675. DÃ©calage UNIFORME, aucune logique
    # dÃ©placÃ©e, aucun NOUVEAU `round()` â€” bug-class #34. Les neuf sites
    # au-dessus (300â€¦985) sont AVANT l'insertion et ne bougent pas.
    "backend/django_core/apps/ventes/quote_engine/builder.py:1893",
    "backend/django_core/apps/ventes/quote_engine/builder.py:1839",
    "backend/django_core/apps/ventes/quote_engine/builder.py:2215",
    "backend/django_core/apps/ventes/quote_engine/builder.py:1794",
    # Z1/Z2 (20/08/2026) â€” RE-CALAGE file:line, PAS de nouveau site
    # (bug-class #34), et un site MONÃ‰TAIRE EN MOINS. Le bloc Â« batterie de
    # synthÃ¨se Â» de `build_quote_data` a Ã©tÃ© SUPPRIMÃ‰ (ordre fondateur : aucun
    # composant ni prix inventÃ© sur un document client) ; il portait le seul
    # round() vraiment monÃ©taire du lot,
    # `round(synth["prix_unit_ttc"] / (1 + taux/100), 2)` â€” il n'existe plus.
    # Les commentaires Z1/Z2 ajoutÃ©s dÃ©calent ensuite uniformÃ©ment les arrondis
    # d'AFFICHAGE qui suivent (+26 puis +45 lignes). PREUVE DE CONTENU (script
    # de recalage, chaque ligne retrouvÃ©e mot pour mot sur HEAD) :
    #   868â†’903 ht_brut Â· 870â†’905 ht_net Â· 895â†’930 tva_amt Â· 897â†’932 ttc_exact
    #   1133â†’1168 roi_s Â· 1146â†’1181 prix_kwc Â· 1822â†’1876 montant TVA Ã—N
    #   1828â†’1882 display_total_multi Â· 1881â†’1935 total_ht Â· 1882â†’1936 total_ttc
    # (336/337 sont AVANT toute insertion et ne bougent pas.)
    # 2026-08-20 â€” LANE MOTEUR (M1-M11/Q1-Q8) : DOUZE ENTRÃ‰ES RECALÃ‰ES,
    # zÃ©ro ajout hors celle documentÃ©e juste dessous. Le rebasage sur la
    # base Z+W+N+O et les correctifs de la lane ont dÃ©calÃ© builder.py de
    # ~+107 Ã  +228 lignes selon la zone. Chaque numÃ©ro a Ã©tÃ© retrouvÃ© PAR
    # PREUVE DE CONTENU (la ligne de base et la nouvelle portent la MÃŠME
    # expression, Ã  la lettre), jamais par un dÃ©calage supposÃ© :
    #   336â†’387 pu_ht Â· 337â†’388 pu_ttc Â· 903â†’1010 ht_brut Â· 905â†’1012
    #   ht_net Â· 930â†’1037 tva_amt Â· 932â†’1039 ttc_exact Â· 1168â†’1295 roi_s
    #   1181â†’1308 prix_kwc Â· 1876â†’2104 montant TVA Ã—N Â· 1882â†’2110
    #   display_total_multi Â· 1935â†’2163 total_ht Â· 1936â†’2164 total_ttc.
    "backend/django_core/apps/ventes/quote_engine/builder.py:1008",
    # 2026-08-20 â€” Q1 (lane moteur) : NOUVEAU site relu. Somme TTC des
    # lignes onduleur d'une option (`_cout_onduleur`), qui devient la
    # provision de remplacement Ã  l'annÃ©e 12 â€” elle remplace un forfait
    # Â« 8 % du CAPEX Â». MÃªme unitÃ© et mÃªme arrondi float que les sites
    # voisins dÃ©jÃ  listÃ©s de ce module (le moteur de devis travaille en
    # float de bout en bout ; `quantize_mad` est la convention des
    # modÃ¨les, pas de ce rendu). Valeur JAMAIS persistÃ©e : elle ne sert
    # qu'au tracÃ© et Ã  la ligne d'hypothÃ¨se.
    "backend/django_core/apps/ventes/quote_engine/builder.py:268",
    "backend/django_core/apps/ventes/quote_engine/builder.py:1049",
    "backend/django_core/apps/ventes/quote_engine/builder.py:1074",
    "backend/django_core/apps/ventes/quote_engine/builder.py:1076",
    # 2026-08-21 â€” CJ2a (lane moteur horaire) : RECALAGE DE LIGNES, AUCUN
    # NOUVEAU SITE. Le passage de `etude_horaire=` Ã  `calculate_savings_roi`
    # a insÃ©rÃ© 5 lignes dans `roi_kwargs` (builder.py ~1278), dÃ©calant de +5
    # les six sites d'arrondi dÃ©jÃ  relus ci-dessous. VÃ©rifiÃ© par diff contre
    # 196c8870 : avec le builder.py de base, la garde est VERTE â€” les six
    # Â« nouveaux Â» sites sont les six anciens, au mot prÃ¨s.
    #   1293â†’1298, 1306â†’1311, 2111â†’2116, 2117â†’2122, 2170â†’2175, 2171â†’2176
    "backend/django_core/apps/ventes/quote_engine/builder.py:1298",
    "backend/django_core/apps/ventes/quote_engine/builder.py:1350",
    "backend/django_core/apps/ventes/quote_engine/builder.py:2214",
    "backend/django_core/apps/ventes/quote_engine/builder.py:2220",
    "backend/django_core/apps/ventes/quote_engine/builder.py:2273",
    "backend/django_core/apps/ventes/quote_engine/builder.py:2274",
    # 2026-08-24 â€” LANE ANTICOPIE (PDF public Â« standard Â») : RECALAGE DE
    # LIGNES, AUCUN NOUVEAU SITE. Les commits a798d33d (Â« rÃ¨gle d'agrÃ©gation
    # kit factorisÃ©e + appliquÃ©e au PDF public Â») et 5e6b75ac ont insÃ©rÃ©
    # 53 lignes dans builder.py, dÃ©calant de +4 (haut de fichier), +19
    # (bloc totaux/ROI) puis +44 (bloc multi-villa/lignes) les douze sites
    # d'arrondi d'affichage DÃ‰JÃ€ relus ci-dessus. Chaque numÃ©ro a Ã©tÃ©
    # retrouvÃ© PAR PREUVE DE CONTENU (ligne de base et nouvelle ligne
    # identiques Ã  la lettre, diff contre origin/main), jamais par dÃ©calage
    # supposÃ© :
    #   268â†’272 total Â· 385â†’389 pu_ht Â· 386â†’390 pu_ttc Â· 1008â†’1027 ht_brut
    #   1035â†’1054 tva_amt Â· 1037â†’1056 ttc_exact Â· 1298â†’1317 roi_s
    #   1311â†’1330 prix_kwc Â· 2176â†’2220 montant TVA Ã—N Â· 2182â†’2226
    #   display_total_multi Â· 2235â†’2279 total_ht Â· 2236â†’2280 total_ttc.
    # 2026-08-24 â€” LANE L-VAR (variante servable + contrat variantes_servables)
    # : RECALAGE DE LIGNES, AUCUN NOUVEAU SITE. La garde L-VAR Ã©largie (+32
    # lignes, milieu de fichier) et la clÃ© `variantes_servables` du
    # dictionnaire de sortie (+7 lignes, aprÃ¨s le bloc multi-villa) ont dÃ©calÃ©
    # les MÃŠMES treize sites d'arrondi d'affichage dÃ©jÃ  relus. Aucun `round()`
    # n'a Ã©tÃ© ajoutÃ© par cette lane. Chaque numÃ©ro est retrouvÃ© PAR PREUVE DE
    # CONTENU (ligne de base Ã  `git show 0fd60ae7:â€¦builder.py` et nouvelle
    # ligne IDENTIQUES Ã  la lettre, les treize vÃ©rifiÃ©es), jamais par dÃ©calage
    # supposÃ© :
    #   272/389/390 inchangÃ©s (avant les insertions) Â·
    #   1066â†’1098 ht_brut Â· 1068â†’1100 ht_net Â· 1093â†’1125 tva_amt Â·
    #   1095â†’1127 ttc_exact Â· 1356â†’1388 roi_s Â· 1369â†’1401 prix_kwc Â·
    #   2258â†’2297 montant TVA Ã—N Â· 2264â†’2303 display_total_multi Â·
    #   2317â†’2356 total_ht Â· 2318â†’2357 total_ttc.
    # 2026-08-26 (lane F1, correctifs bloquants PDF) : RECALAGE DE LIGNES,
    # AUCUN NOUVEAU SITE. Trois insertions dans `builder.py` â€” le recalage des
    # scalaires sur la variante rendue (+33 lignes, avant les totaux
    # canoniques), la chaÃ®ne Ã©conomies/ROI par option (+40, aprÃ¨s l'appel
    # `calculate_savings_roi`) et les deux clÃ©s `prod_kwh_sans/avec` (+5, dans
    # le dictionnaire de sortie) â€” ont dÃ©calÃ© les MÃŠMES dix sites d'arrondi
    # d'AFFICHAGE dÃ©jÃ  relus. Aucun `round()` n'a Ã©tÃ© ajoutÃ© par cette lane
    # (13 sites dÃ©tectÃ©s avant comme aprÃ¨s). Chaque numÃ©ro est retrouvÃ© PAR
    # PREUVE DE CONTENU (expression identique Ã  la lettre entre
    # `git show 9a969ab1:â€¦builder.py` et l'arbre courant), jamais par dÃ©calage
    # supposÃ© :
    #   272/389/390 inchangÃ©s (avant les insertions) Â·
    #   1247â†’1280 ht_brut Â· 1249â†’1282 ht_net (entrÃ©e plus haut) Â·
    #   1274â†’1307 montant TVA Â· 1276â†’1309 ttc_exact Â·
    #   1547â†’1620 roi_s Â· 1560â†’1633 prix_kwc Â·
    #   2478â†’2556 montant TVA Ã—N Â· 2484â†’2562 display_total_multi Â·
    #   2537â†’2615 total_ht ligne Â· 2538â†’2616 total_ttc ligne.
    "backend/django_core/apps/ventes/quote_engine/builder.py:272",
    "backend/django_core/apps/ventes/quote_engine/builder.py:389",
    "backend/django_core/apps/ventes/quote_engine/builder.py:390",
    "backend/django_core/apps/ventes/quote_engine/builder.py:1280",
    "backend/django_core/apps/ventes/quote_engine/builder.py:1307",
    "backend/django_core/apps/ventes/quote_engine/builder.py:1309",
    "backend/django_core/apps/ventes/quote_engine/builder.py:1635",
    "backend/django_core/apps/ventes/quote_engine/builder.py:1648",
    "backend/django_core/apps/ventes/quote_engine/builder.py:2571",
    "backend/django_core/apps/ventes/quote_engine/builder.py:2577",
    "backend/django_core/apps/ventes/quote_engine/builder.py:2630",
    "backend/django_core/apps/ventes/quote_engine/builder.py:2631",
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
                "monetary value â€” prefer core.money.quantize_mad() (see "
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

    print("\ncheck_money_rounding: OK (advisory â€” all sites are baselined).")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
