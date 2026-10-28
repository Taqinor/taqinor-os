# Audit Fable final — run L3 « générateurs de devis » (PR #1094 → #1131), 28/10/2026 07:15 UTC

Lecture seule sur `origin/main` = 666fbd833f ; aucun test lancé ; chaque constat appuyé sur un `git show/diff/grep`.

## 1. Bloquants (et suite donnée par la coordinatrice)
1. **Garantie batterie : site ≠ PDF ≠ catalogue** pour `BAT-DEY-10` (Powerbox Pro, 120 mois) et `BAT-DYN-PB-SC-16` (PowerBrick SC, 120 mois) — #1131. `apps/web/src/lib/proposition/garanties.ts:36-41` ne rend 10 ans que si « powerbox » figure dans marque+désignation ; le catalogue nomme « Batterie Dyness 10 kWh » ; le payload public (`builder.py:2098`) ne sert pas `garantie_mois` ; le PDF le lit (`residential/theme.py:527`) → PDF 10 ans, page 7 ans. → **FIX-WEB** (servir `garantie_mois` + SKU, contrat d'abord, lecture côté site).
2. **Chiffre C&I corrigé sans garde niveau 3 sur le chemin « composition » de l'option avec** — #1094, non couvert par #1126. `etude_ci_batterie.py:238` `investissement_hors_om(...)` avec `actif=True` par défaut ; seul l.427 est gardé ; `_bloc` (l.299) retombe sur ce chemin dès que `_investissement_des_lignes` rend None ; atteignable sur un devis envoyé ≤ 2 par `force_etudes`. Même faiblesse : CMP5/CMP7/CMP8 dans `moteur_ci/*` n'ont aucun `regles_au_moins` (protégés par l'empreinte seulement). → **FIX-MOTEUR** (l.238) ; CMP5/7/8 = **décision fondateur** (tâche v3 GATED).
3. **« garanties de 10 à 30 ans » résiduel** (Deye = 5) — `pourquoi-taqinor.astro:61` (meta FR), `ar/pourquoi-taqinor.astro:56` et `:66`. → **FIX-WEB**.
4. **RWEB24 — brut/net sous mention de parité** — page « Économies cumulées … Même calcul que votre devis PDF » = cumul BRUT (`public_views.py:1128`), PDF « Gain net sur 25 ans » = NET (`residential/options.py:787-790`). → **FIX-WEB** (servir le net du PDF).
5. **RHOR5** : omission du retour quand `roi_*_jamais` sans garde niveau 3 (`economies_periodes.py:62-68`, #1095), assumée « pour le fondateur » ; idem seuils CPDF (`SEUIL_COUVRE_SOIR` 0,90, « scénario prudent » retiré, « règle de dimensionnement » retirée). → **décisions fondateur**, consignées.
6. **Forme ≥ 2 000 lignes** : `builder.py` 3046→3047 (#1130), `solar.js` 2604→2605 (#1103). → FIX-MOTEUR / FIX-WEB.
7. **Deux recapteurs de `golden/moteur/build_quote_data`** (#1095 RHOR 32 goldens, puis #1114 RPDF 104 + 17) ; état final = RPDF, hash-only. → noté, pas d'action.

## 2. Optionnels
- `montants.py` : contextvar `regles_avant_2710` jamais remise à zéro (→ FIX-MOTEUR).
- #1130 : imports `# noqa: F401` sans effet (`couverture.py:21`, `options_cote.py:17`, `finance.py:26`, `trust.py:26`) ; `ci/blocs.py:43` imprime le littéral FR du site d'appel.
- #1112 : `test_ciq111` budget 1 s → 5 s.
- #1096 : `_est_batterie` (« fusible », préfixe « Batterie ») ; tarif niveau ≤ 2 bi-horaire `omis` → `grille_officielle`.
- #1103 : `fixtures/solar_calculs_expected.json` (« UNIQUEMENT par un humain ») recapturé par un agent (payback_sans 6,2 → 12 ans).
- #1106 : `bat_max_modules_par_banc` DL5.0C 200→50 non réappliqué aux bases semées ; PowerBrick SC quantité 500 ; commentaire périmé « Harmonisé sur 10 ans » ; Powerbox Pro 10 ans = décision fondateur sans lettre constructeur.
- Textes client préexistants : « à confirmer par la visite » (`agricole/mentions.py:296`, `syntheseAgricole.ts:307`), « selon fiche fournisseur » (`agricole/garanties.py:56`), « Taux calculés par estimation » (`i18n_labels.py:918`), « m³ d'eau par jour (estimation) », « Garantie performance 25 ans » JA Solar (`équipement.astro:46`) ; 14 commentaires HTML « fondateur » dans `[...token].astro` ; TVA pompage (art. 91-I-C-6°) à valider.
- Tests dont l'attendu est calculé par la fonction testée : `test_ciq306:~82`, `test_agr308:~116`, `test_qjr120:~143`, `test_ciq342:~62`.

## 3. Vérifié propre
- Règle #4 : aucun nouveau chemin PDF hors `/proposal` ; aucun changement de statut dans `quote_engine/` ; `prix_achat` absent de tout rendu/payload client.
- Devis envoyés : `etude_ci_batterie.py:427` gardé ; drapeau `regles_avant_2710` posé par `builder.py:522/2174` et reposé par `generate_devis_premium.py`, `commercial/renderer.py`, `industriel/renderer.py` ; Celery et /proposition passent par `build_quote_data` ; RSIZ2/3/5/8 et RPDF8/9/15/16 au niveau 3 ; golden `regles_calcul_origine.json` non recapturé ; masque `rpdf_*` = gabarits statiques seulement.
- Aucun texte incertain/interne AJOUTÉ aux rendus par les 21 PR ; payload public assaini (`_RESIDU_INTERNE`, `_PREFIXE_DECISION`).
- Garanties Deye 5 / Huawei 10 / Dyness DL5.0C 7 / Powerbox Pro 10 cohérentes seed ↔ `warranty.ts` ↔ pages ↔ FAQ (hors bloquants 1 et 3).
- 0 `skip/xfail/.only` ajouté ; CIW406 plus fort qu'avant ; RSIZ 4 assertions voulues ; ProductTour non touché.
- Multi-tenant : vues publiques par token, `panneau_appel` company-scopée ; crm 0144 = 2 AddField nullables ; stock 0174 réversible ; aucune migration renumérotée ; `economie_ci.py` 2008→1993, `public_views.py` 2226→2217, `selectors.py` 1998.
- `i18n_labels.LIBELLES` inchangé ; CPDF résout via `ci/blocs.py` ; #1129 ne touche que sa famille de goldens.
- `roi_*_jamais` et `option_servie` servis et rendus ; chiffres alignés par `_etude_de_l_option` (sauf RWEB24).

Temps ~30 min ; 4 lanes Sonnet lecture seule + re-vérification Fable de chaque bloquant.
