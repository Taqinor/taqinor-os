# Devis résidentiel et agricole — sessions L3 parallèles (fondateur, 27/10/2026)

Même méthode que le C&I : chaque session lit d'abord le **bloc commun de `docs/ci-l3-sessions.md`** (§0 à §6, appliqué
tel quel sauf les différences ci-dessous), puis **sa** section ici, et l'exécute de bout en bout.
**Règle fondatrice de ce document : seulement les différences.** Tout ce qui est générique (page `/proposition`,
questionnaire client, liste des devis, options PDF, admin catalogue/paramètres, parcours de suivi, envoi du devis) reste
aux sessions C&I, dont la mission couvre désormais **les trois segments**. Une session résidentielle ou agricole ne refait
jamais du générique : elle fait ce qui est propre à son segment.
Plan conçu par Fable puis corrigé après une critique Fable indépendante (27/10/2026).

---

## Différences avec le bloc commun C&I

1. **Décisions à lire** (ne pas re-demander) : `docs/claude-memory/residentiel-decisions-2710.md`,
   `dimensionnement-decisions-2310.md`, `qjr5-decisions-fondateur.md`, `agricole-decisions-fondateur.md`,
   `devis-envoyes-nouveaux-rendus.md`, `kwh-declare-vs-factures.md`, et `ci-decisions-2610.md` pour le vocabulaire commun.
2. **Chiffres des devis déjà envoyés** :
   - résidentiel : toute correction de chiffre du 27/10 ou après est gardée derrière le **niveau de règles de calcul 3**
     (`regles_calcul ≥ 3`, PR « niveau 3 » de la coordinatrice — `@after` sur elle) : un devis déjà envoyé garde ce que le
     client a reçu ; les nouveaux rendus prennent la correction ;
   - agricole et C&I : anciens devis oubliés (D-AGR-13, D-CIQ-21), mais jamais un devis envoyé réécrit en silence.
3. **Préfixes** : `RSIZ`, `RHOR`, `RGEN`, `RPDF`, `RWEB` (résidentiel), `AGM`, `AGV`, `AGC` (agricole). Branches
   `claude/res-<code>` / `claude/agr-<code>`.
4. **Aucun fichier à deux sessions** : quand un segment a besoin d'un fichier possédé par une autre session, il crée un
   **module neuf de son segment** et le propriétaire du fichier pose **un appel d'une ligne** (demande par message).
   Cas déjà tranchés :
   - `apps/ventes/domain/creation_auto.py` : CORC fait un déplacement pur (le **dispatcher `build_devis_auto` reste** dans
     ce fichier) vers `creation_auto_residentiel.py` (→ RGEN) et `creation_auto_agricole.py` (→ AGM) ;
   - `apps/visites/visite_checklist.py` : CSV ; la visite agricole (point d'eau) vit dans `visite_checklist_pompage.py` (AGV) ;
   - `seed_catalogue.py` et `frontend/src/features/stock/catalogue.js` : CCAT ; modules neufs `seed_catalogue_residentiel.py`
     (RSIZ), `seed_catalogue_pompage.py` et `catalogue_pompage.js` (AGM) ;
   - `quote_engine/legacy_onepage.py` : **RPDF** ; la une-page C&I vit dans un module neuf de CPDF, l'agricole dans un module neuf d'AGC ;
   - `apps/web/src/pages/proposition/[...token].astro` et `lib/proposition.ts` : **RWEB** (le corps résidentiel/commun reste
     en place). La **1re PR de CPRW** déplace seulement les blocs C&I vers `components/proposition/ci/**` et les blocs agricoles
     vers `components/proposition/agricole/**` (→ AGC) ; ensuite CPRW n'y garde qu'un appel de composant ;
   - `quote_engine/pricing.py` : RHOR (payback résidentiel ; CEC lit ses constantes : exports gelés) ;
   - `apps/ventes/public/payload_horaire.py`, `payload_batterie.py` : RHOR (CPRS : appel d'une ligne ; batterie C&I côté page dans un module neuf de CPRS).
5. **Exports gelés** (le C&I les importe) : `apps/ventes/dimensionnement.py` (`HORIZON_MARGINAL_PV`, `depart_dans_horizon`,
   `point_depart_meilleur_payback`, `ratio_pas_marginal`), `etude_horaire._formes_production_par_saison`,
   `horaire.conso.RATIO_KWH_FACTURE_MIN/MAX`, constantes de `quote_engine/pricing.py`.
6. **Goldens — un recapteur par famille** (finit le ping-pong de la merge queue) :
   - `golden/moteur/build_quote_data/` : `commercial__*` / `industriel_etude__*` → sessions C&I ; `agricole__*` → **AGC**
     (AGM liste les hachages qu'elle fait bouger) ; **tous les autres cas** (résidentiels) → **RPDF** seule recapture ;
     RSIZ / RHOR / RGEN listent dans leur PR les hachages qu'elles font bouger et préviennent RPDF ;
   - `tests/golden/split_sd_rendu_html.json` : clés C&I → sessions C&I, clés résidentielles → RPDF ;
   - golden générateur `DevisGeneratorGolden.test.jsx` : cas `a, b, g, i, j` → RGEN ; `f` → AGV ; `d, e` → CGN ; `c, h` → garder les deux côtés.
7. **Contrats** : le PRODUCTEUR livre le contrat seul sur `main` (PACT10). Questionnaire : CQST livre ; RWEB / AGV posent une
   tâche `@after` qui liste les champs dont leur devis a besoin (et l'envoient à CQST par message).
8. **Capacité** : au plus **7 sessions vivantes** sur la machine (C&I + résidentiel + agricole confondus), 3 lanes lourdes
   chacune, 2 `astro dev` maximum ; la coordinatrice lance la suivante quand une place se libère.
9. **Fable** : comme le §3 C&I (R4 + œil client, pré-merge, arbitrage groupé si contesté) **plus**, pour RPDF, RWEB, AGC,
   un appel « un seul produit » par round qui compare leur rendu à celui du C&I (même grammaire visuelle, mêmes mots, même
   chaîne de prix). La coordinatrice fait un appel « rien en double » par vague de merges.
10. **Données de démo** : la gardienne de la pile (CORC) ajoute 4 leads résidentiels (factures 1 500 / 6 000 / 25 000 /
    80 000 MAD, mono et tri, avec et sans batterie) et 2 leads pompage (forage connu / inconnu, pompe neuve / existante).

### Décisions prises pour le fondateur (défauts appliqués sans attendre, à revoir)
- D1 `core/pompage/**` et ses tests → propriétaire **devis** (`docs/ownership.yml`, cette PR).
- D2/D3 D-RES-2710-1 (ombrage du calepinage dans le moteur horaire) et D-RES-2710-2 (VE déjà possédé n'ajoute rien) :
  construits par RHOR, derrière le niveau 3.
- D4 AGRM1-6 / AGR135 (prix OSP, fiches VEICHI) : jamais inventés ; l'écran admin « ce qui manque pour chiffrer » (CCAT,
  trois segments) les montre ; pompes OSP restent « prix à renseigner ».
- D5 pas de session résidentielle dédiée pour le questionnaire ni la page `/proposition` : CQST / CPRS / CPRW couvrent les trois segments.
- D6 dossier technique (+1 page, D-RES-2710-3) : option explicite seulement (QJR666), dernier round de RPDF.
- D7 règles batterie résidentielles (QJR612) inchangées, sauf D-RES-2710-2 (VE possédé hors plancher de stockage).
- D8 TVA kit pompage, garanties écrites fournisseurs : manuels, intouchés.

---

## Sessions résidentielles

### RSIZ — Taille et composition résidentielles
- **Mission** : la bonne taille et le bon kit pour une facture de 500 à 100 000 MAD/mois.
- **Fichiers** : `apps/ventes/dimensionnement.py` (2 224 l., aucune croissance), `balayage_adaptatif.py`,
  `domain/dimensionnement_devis.py`, `domain/taille.py`, `offres_tailles.py`, `domain/{composition,catalogue,lignes,entrees}.py`,
  `etape_composer.py`, module neuf `stock/management/commands/seed_catalogue_residentiel.py`.
- **Lecture seule** : `core/product_roles.py`, `stock/selectors.py` (CCAT), `moteur_ci/taille.py` (CLD).
- **Tests** : `test_dimensionnement_exemples`, `test_dimensionnement_amot31_lignes_vendues`, `test_qjr_dimensionnement_surface`,
  `test_t5_dimensionnement_devis`, `test_offres_tailles_*`, `test_pvkit_composition`, `test_composition_source_unique`,
  `test_deux_optimiseurs`, `test_sld_batterie_packs`, `dimensionnementKwc.ez5.test.mjs`.
- **Plans** : propriétaires vérifiés par `check_ownership.py` (devis / moteur).
- **Axes** : balayage adaptatif éprouvé de 20 à 100 k MAD/mois (mémoire 23/10) ; écart écran / devis auto (lead 1635) ;
  couple panneau/onduleur impossible (`_refuser_couple_panneau_onduleur_impossible`) ; découpe de `composition_residentielle`
  (920 l.) et de `dimensionnement.py` en **déplacement pur au R1, seul** ; structure et forfaits.
- **Rendu réel** : 6 devis auto (villas 1 500 / 6 000 / 25 000 / 80 000 MAD, mono/tri, avec/sans batterie) relus ligne à ligne.

### RHOR — Étude horaire, batterie, VE, ombrage, économie résidentielles
- **Mission** : les chiffres du client (production, couverture, économies, retour) justes et sourcés.
- **Fichiers** : `etude_horaire.py` (2 077 l.), `etude_horaire_view.py`, `economie.py`, `economies_periodes.py`, `etude.py`,
  `quote_engine/productible.py`, `quote_engine/pricing.py`, `horaire/{conso,public,ve_nocturne,batterie_lignes}.py`,
  `courbes_journalieres.py`, `profils_comparatifs.py`, `domain/etude_schema.py`, `domain/creation_calepinage.py`,
  `coherence/regles_calepinage.py`, `public/payload_horaire.py`, `public/payload_batterie.py`.
- **Lecture seule** : `apps/calepinage/selectors*` (dont `ombrage_servi`), `solar.js:296-415` (miroir JS, appel d'une ligne par RGEN).
- **Tests** : `test_etude_horaire*`, `test_split_devis_horaire`, `test_cad16x/17x`, `test_qjr140_*`, `test_err_apercu_*`,
  `test_amot58`, `test_leco_economies*`, `test_calx280/288*`, `test_err_payback_jamais_rembourse`,
  `test_pvuni_verite_unique_calepinage`, `test_pv86_*`, `calepinage/tests/test_agr125_parite_devis`.
- **Précondition** : PR « niveau de règles 3 » mergée (`@after`).
- **Axes** : D-RES-2710-1 ombrage servi par le calepinage dans le moteur horaire ; D-RES-2710-2 VE possédé ; plancher batterie ;
  parité Python / JS du retour ; AMOT64 productible ; chaque chiffre changé derrière le niveau 3.
- **Rendu réel** : 4 PDF + 4 pages web résidentiels avant/après, courbe « journée type » FR/EN/AR.

### RGEN — Vendeur résidentiel : écran, fiche énergie, devis auto résidentiel
- **Fichiers** : `pages/ventes/generator/PanneauResidentiel.jsx`, `hooks/useApercuEtude.js`, nouveaux `generator/residentiel/*` ;
  `features/ventes/quote/{sizingReducer,forfaitsPanneau,paireDimensionnement,ecranDefauts}.js`, `etudeHorairePreview(Pur).js` ;
  `features/crm/workspace/sections/SectionEnergie.jsx` ; `apps/ventes/domain/creation_auto_residentiel.py` (après le déplacement de CORC).
- **Lecture seule** : `DevisGenerator.jsx`, `solar.js` (appel d'une ligne), `CarteFacturesElectriques.jsx` (CGN), `SectionPro`/`DevisTab` (CVL).
- **Tests** : `sizingReducer.test`, `forfaitsPanneau.test`, `etudeHorairePreview.test`, `DevisGenerator.agnr*`, `solar.batterie*`,
  `gestes-autofill-residentiel` ; golden générateur `a, b, g, i, j`.
- **Plans** : generateur + devis + lead (vérifier chaque fichier).
- **Axes** : AGNR42 (acceptation en direct — jouée par la coordinatrice) ; `avecBatterieAvailability` ; états de refus ;
  l'aperçu ignore `occupation` envoyée ; écran = PDF.
- **Rendu réel** : parcours lead → devis auto → écran, desktop + mobile.

### RPDF — Client résidentiel : PDF (et recapteur des goldens résidentiels)
- **Fichiers** : `quote_engine/residential/*`, `quote_engine/legacy_onepage.py` (propriétaire), module neuf `i18n_labels_residentiel.py`.
- **Lecture seule** : `generate_devis_premium.py`, `i18n_labels.py`, `builder.py` (aucune croissance ; ajout commun = 1 ligne).
- **Tests** : `test_pdf_residentiel_sections_options`, `test_qjr666_*`, `test_quote_engine_amot18_*`, `test_pdf_apdf_*`,
  `test_moteur_golden_build_quote_data` (cas résidentiels — recapture pour toutes les sessions résidentielles).
- **Axes** : découpe de `build_pages` et `cover.build` ; FR/EN/AR relus mot à mot ; aucune page ajoutée sans option explicite (QJR666) ;
  dossier technique en option (dernier round) ; même grammaire visuelle que le PDF C&I.
- **Rendu réel** : au moins 12 PDF par round (4 profils × premium / une page / + étude, EN/AR), chaque page lue.

### RWEB — Client résidentiel : site, tunnel, page `/proposition` (corps résidentiel)
- **Fichiers** : `apps/web/src/pages/devis/mon-toit.astro` (+ `en/`, `ar/`), `pages/résidentiel.astro`,
  `components/InstantEstimator.astro`, `lib/{lead,billEstimate,batterySim,estimatorBrainV2,estimatorBrainCommun}.ts`,
  `tunnel/champs.ts`, `lib/estimatorBrainV3..V8.ts` (propriétaire calepinage — tâches dans son plan),
  `pages/proposition/[...token].astro` et `lib/proposition.ts` (corps résidentiel/commun, après la 1re PR de CPRW).
- **Tests** : `monToitTunnel.test`, `estimatorBrainV*`, `billEstimate`, `wj112RefineEstimate`, `proposition*` résidentiels.
- **Précondition** : `@after` la 1re PR de CPRW et le contrat questionnaire de CQST.
- **Axes** : 7 cerveaux d'estimation → un seul ; mon-toit découpé ; chiffres du site = chiffres du moteur (règle des chiffres vérifiés) ;
  mobile d'abord ; page de devis résidentielle aussi claire que la meilleure du marché. Le merge déploie le site (Cloudflare) — jamais `wrangler`.
- **Rendu réel** : captures mobile/desktop FR/EN/AR, tunnel complet jusqu'au lead, page de devis comparée au PDF.

## Sessions agricoles

### AGM — Moteur pompage, catalogue pompes, devis auto agricole
- **Fichiers** : `core/pompage/*` (propriétaire devis depuis cette PR), `domain/pompage.py`, `economie_pompage.py`,
  `views/economie_pompage.py`, `etude_pompage_view.py`, `apps/ventes/domain/creation_auto_agricole.py` (après le déplacement de CORC),
  modules neufs `seed_catalogue_pompage.py`, `frontend/src/features/stock/catalogue_pompage.js` (`debitAtHmt`),
  `apps/crm/devis_selectors_pompage.py`.
- **Lecture seule** : `crm/devis_selectors.py` (CORC, appel d'une ligne), `payload_economie.py` (CPRS).
- **Tests** : `core/tests/test_agr110..133`, `test_pompage_purete`, `test_agr121-124`, `test_agr206`, `stock/tests/test_agr100-104`,
  `test_adev25_auto_ci_agricole_pipeline` (doit rester vert).
- **Axes** : AMOT65 ; données AGRM1-6/AGR135 jamais inventées (fonction « ce qui manque » servie à l'écran admin de CCAT) ;
  parité `etudePompagePreviewPur.js` ; volume déclaré d'abord (D-AGR-3) ; m³/jour (D-AMOT-7).
- **Rendu réel** : 5 devis auto (3 / 5,5 / 7,5 / 15 / 30 CV, pompe neuve / existante).

### AGV — Vendeur agricole : écran, fiche lead pompage, visite du point d'eau
- **Fichiers** : `generator/PanneauAgricole.jsx`, `CarteEconomiePompage(Interne).jsx`, `quote/entreesPompageLead.js`,
  `economiePompagePreviewPur.js`, `etudePompagePreviewPur.js`, `etatDevis.js`, `apps/crm/models_lead_pompage.py`,
  module neuf `apps/visites/visite_checklist_pompage.py` (CSV pose l'appel d'une ligne).
- **Lecture seule** : `DevisGenerator.jsx`, `solar.js` (appel d'une ligne), `questionnaire.py` (CQST).
- **Tests** : `PanneauAgricole.test`, `CarteEconomiePompage*.test`, `entreesPompageLead.test`, `etudePompagePreview.test`,
  golden générateur `f`, `gestes-autofill-agricole`, `crm/tests_agr400-424`, `tests_agr411_questionnaire_pompage`.
- **Axes** : relevé du point d'eau avant devis (D-AGR-4) ; bandeau type de lead (D-AGR-9) ; refus qui nomment le champ ;
  recette pompage `installations/tests_agr6*` (tâche routée au propriétaire chantiers) ; écran = PDF.
- **Rendu réel** : parcours lead pompage → visite → devis auto, desktop + mobile.

### AGC — Client agricole : PDF, page de devis, site pompage (et recapteur des goldens agricoles)
- **Fichiers** : `quote_engine/agricole/*`, `utils/garanties.py`, modules neufs `i18n_labels_agricole.py` et une-page agricole ;
  `apps/web/src/lib/{propositionAgricole,estimatorAgricole,agronomy}.ts`, `pages/pompage-solaire.astro`,
  `components/CarteAideEtat.astro`, `components/proposition/agricole/**` (après la 1re PR de CPRW).
- **Lecture seule** : `payload_economie.py` (CPRS, appel d'une ligne), `[...token].astro` (RWEB).
- **Tests** : `test_agr300-319`, `test_quote_engine_amot37_pages_agricole`, `test_qx48_agronomy_v2`, goldens `agricole__*`,
  `propositionAgricole*AGW300/303/304`, `pompageFdaAGW307`, `pompageTvaAGW305`, `estimatorAgricole`, `wj111AgricoleEstimate`.
- **Axes** : acceptation après accord FDA, délai SAV saisi (D-AGQ-12..15) ; règle FDA sans montant (D-AGR-6) ; économies déclarées
  sur 10 ans (D-AGR-5) ; darija relue (D-AGR-11) ; aucun toit en preuve (D-AGR-10) ; même grammaire que le C&I.
- **Rendu réel** : au moins 8 PDF (4 cas × 3 pages / une page, EN/AR) + page web mobile.

---

## Ordre de lancement (plafond 7 sessions vivantes)
0. Coordinatrice : merge #1074 ; PR « niveau de règles 3 » ; CORC : déplacement pur de `creation_auto.py` ; cette PR (docs + propriété).
1. Maintenant, avec la cohorte A C&I : **AGM** (fichiers pompage disjoints).
2. Places libérées par la cohorte A : **RSIZ**, puis **RHOR** (après le niveau 3).
3. Cohorte B C&I, producteurs de contrats d'abord : **CPRS → CPRW (1re PR = déplacement des blocs C&I et agricoles) → CQST → CPDF → CGN → CVL**.
4. Cohorte D : **RPDF, AGC, RGEN, AGV, RWEB** (pages après la 1re PR de CPRW et le contrat de CQST).
5. **CE2E** en dernier : 10 profils C&I + 4 résidentiels + 2 pompage.
