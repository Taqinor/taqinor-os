# Taqinor OS — Build Plan & Progress (priority queue, PLAN2)

> **This queue is drained BEFORE `docs/PLAN.md`.** A run works every pending `[ ]` task here first, and only falls through to `docs/PLAN.md` once this file has none left.

This is the **priority queue**, worked **before** `docs/PLAN.md`. A run drains every `[ ]` task
in this file FIRST — the same way (verify it isn't already built, build it completely with
tests, obey every STANDING RULE in `PLAN.md`, then commit it to a worktree branch, tick it `[x]`,
and append a DONE LOG line as it lands; **run `python scripts/plan_lanes.py docs/PLAN2.md` to get
the maximally-parallel cross-category wave plan and build those lanes in parallel with concurrent
worktree subagents up to the session ceiling (default 8, raised as high as the session can sustain
via `--max-lanes`), continuously refilled (work-stealing), coupled tasks in sequence inside a
lane**) — and only
once this file has no pending `[ ]` task left does it fall through to `docs/PLAN.md`. Every
worktree branch is folded into one `dev`, CI runs once over the whole batch, and the run
self-merges `dev` → `main` exactly once at the very end — **no per-agent PR, no per-task merge**.
All the HOW TO RUN and STANDING RULES in `docs/PLAN.md` apply here unchanged — including the
default **workflow-with-review engine** (one worktree subagent per task plus a separate
adversarial review agent that must pass before a change is merge-eligible), the
**parallel-subagent fallback** when no workflow engine is available (never a single serial
one-task-at-a-time agent), and the **sync-safe single merge** (integrate the latest
`origin/main` first, re-run CI, push without forcing). This file only adds tasks.

> Added 2026-06-17 while the field-execution batch (PLAN.md F1–F24) was running on
> `dev-field-exec`. Per the founder's "add to plan" convention, new tasks go here while a
> run is in progress so `PLAN.md` is never touched mid-batch.

---

> **Web session note (2026-06-18):** a world-class audit of the public site (`apps/web`) was run and its
> fixes built — **W62–W66 shipped** (social proof scaffold, homepage guarantee band, founder photo-ready
> block, brand strip +Jinko/Huawei/Nexans, « réponse sous 48 h ») and the **W67 EN/AR i18n foundation**
> laid (Astro i18n + dictionary + switcher + RTL/hreflang, FR byte-identical). Full detail in
> `docs/WEB_PLAN.md` + `docs/DONE.md`; web work stays out of this OS queue per the OS/web split. Logged
> here at the founder's request — this note adds no OS task.

## BUILD QUEUE (do top-down — highest value first)

### Groupe QX ROUND 7 — 4 MODÈLES DE DEVIS : split industriel/commercial, 4 renderers, moteur agricole FAO-56, injection 82-21 (QX43-QX52 + QXG6, fondateur 2026-07-16)

*Commande fondateur 2026-07-16 : séparer industriel et commercial (4 modes réels avec
résidentiel/agricole), UN moteur de devis (règle #4) avec 4 rendus distincts visibles sur la
page proposition ET les PDF, questions par catégorie commerciale, moteur agricole eau→pompe
mondial-best-practice. Recherche 5 volets 2026-07-16 (commercial 9 catégories, industriel
MT/82-21, agricole FAO-56, courbes de charge MA + batteries, audit codebase) — constats clés :
`Lead.TypeInstallation.COMMERCIAL` et l'alias webhook `commercial` EXISTENT déjà
(crm/models.py:296-300, webhooks.py:185-196) ; le trou est côté Devis/moteur/web. Le décret
82-21 (2-25-100, BO 9 mars 2026, en vigueur 9 juin 2026) rend l'injection MT/HT RÉELLE :
tarif ANRE 0,21/0,18 DH/kWh (mars 2026-févr 2027), plafond 20 % de la production (en
révision), frais réseau ≈6,07+6,38 c/kWh à déduire.*

> Contraintes (toutes tâches) : règle #4 — le moteur RE ND seulement, jamais de statut ;
> nouveaux renderers DANS apps/ventes/quote_engine/ ; migrations additives ; zéro chiffre
> inventé — chaque constante tarifaire/Kc porte sa source en commentaire + flag « à vérifier
> fondateur » quand estimée ; prix_achat jamais client-facing.

- [x] QX43 — **Mode `commercial` de bout en bout côté ERP.** `Devis.ModeInstallation` gagne
  `COMMERCIAL='commercial'` (ventes/models.py:93-97, migration additive) et le label
  INDUSTRIEL redevient « Industriel » (il dit « Industriel / Commercial » aujourd'hui).
  DevisGenerator.jsx `MODE_OPTIONS` (:55-59) passe à 4 (🏪 Commercial). builder.py :
  `PAYMENT_TERMS_BY_MODE` (:34-38, commercial = 50/40/10 comme industriel),
  `_FINANCING_PROGRAMS` (:248-267, clé `commercial` = réutilise industriel/« Tatwir Croissance
  Verte (PME) » sauf veto fondateur — pas de programme inventé) et la carte `inst_type`
  (:947-951, « Commerciale ») gagnent la clé
  `commercial`. QX20 (garde équipement par mode) et QX23 (garde de bascule) étendus au
  4e mode. **Done =** un Devis commercial se crée/édite/rend sans tomber dans un fallback
  résidentiel silencieux ; tests de non-régression sur les 3 modes existants.
  (SCHEMA — migration additive : nouveau choix de champ ModeInstallation)
  (@lane: ventes-backend) (@model: sonnet)
- [x] QX44 — **Étude COMMERCIALE par catégorie dans le générateur.** DevisGenerator mode
  commercial : select « Catégorie » (hôtel/riad, restaurant/café, commerce/supermarché,
  bureau/siège, santé, école privée, hammam/spa/gym, boulangerie, entrepôt froid, autre) +
  2-4 questions par catégorie (hôtel : chambres+occupation+piscine ; restaurant : chambres
  froides+horaires+cuisson élec/gaz ; boulangerie : four élec/gaz+cuisson nocturne ; froid :
  T° consigne+volume+saisonnalité récolte ; école : effectif+internat+fermeture estivale…)
  d'après la recherche 2026-07-16. Le day-share de l'étude vient d'une table d'archétypes
  par catégorie (bureau 0,80 ; école 0,85 en période scolaire ; restaurant 0,70 ; hôtel
  0,55 ; froid 0,50 ; boulangerie 0,45… — table commentée SOURCE vs ESTIMATION, ajustable
  société) au lieu de l'unique valeur `DAY_USAGE_DEFAULTS['Commerciale']` (=80, solar.js:71-77 —
  que le chemin auto-quote n'utilise même pas : `autoQuote.js:140` code en dur `['Industrielle']`).
  `etude_params` gagne `categorie_commerciale` + les réponses catégorie (clés snake_case).
  solar.js aligné (miroir commenté). NOTE LANE : QX44 édite `DevisGenerator.jsx`, fichier PARTAGÉ
  avec QX43 → même lane (union `plan_lanes.py`), séquentiel après le mode commercial de QX43.
  **Done =** une étude commerciale hôtel ≠ bureau à facture égale ;
  etude_params round-trip édition ; tests. (@lane: ventes-frontend) (@model: opus) (@after: QX43)
- [x] QX45 — **Renderer INDUSTRIEL dédié (quote_engine/industriel/).** Nouveau package
  miroir de residential/ + agricole/ (renderer.py expose `is_industrial(devis, pdf_options)`
  + `render_pdf_bytes(data)` + exception `Unsupported`, EXACTEMENT comme agricole/residential ;
  câblé dans le dispatch `generate_premium_devis_pdf` builder.py:1442-1463, AVANT le repli
  legacy et après le bloc agricole ; full/premium seulement, jamais one-page ; render.py
  harnais ; pages cover/finance/trust ; réutilise residential/theme.py
  company_identity/fonts/footer — RENDERING_NOTES.md : tables CSS, jamais flex). Contenu
  CFO (recherche 2026-07-16) : P1 baseline (12 mois, répartition pointe/pleines/creuses DH,
  cos φ, pattern d'équipes) + KPIs (kWc, autoconso %, couverture %) ; P2 cashflow 10-15 ans
  (économies par bande — l'essentiel en heures PLEINES, jamais promettre la pointe sans
  batterie —, ligne injection ANRE nette des frais réseau plafonnée 20 % flag « conditions
  ANRE en vigueur, sujettes à révision », O&M, payback + TRI) ; P3 tranches phasées +
  ISO 50001/CBAM + garanties + signature. Le fallback legacy reste l'off-switch (règle #4) :
  l'ancien chemin industriel = moteur legacy WeasyPrint — le nouveau renderer l'intercepte en
  amont, le legacy ne meurt pas (repli automatique + off-switch).
  **Done =** PDF industriel visuellement distinct (3 pages), test page-count dédié ;
  test_quote_engine.py :444 (étude 4 pages legacy) reste vert car son helper `_render`
  (test_quote_engine.py:343-356) appelle le moteur legacy `generate_premium_pdf` EN DIRECT, hors
  du dispatch `generate_premium_devis_pdf` — il ne voit donc jamais le nouveau renderer.
  (@lane: quote-engine) (@model: opus)
- [x] QX46 — **Renderer COMMERCIAL dédié (quote_engine/commercial/).** Package miroir exposant
  `is_commercial(devis, pdf_options)` + `render_pdf_bytes` + `Unsupported`, câblé dans le dispatch
  `generate_premium_devis_pdf` builder.py:1442-1463 avant le repli legacy (comme QX45).
  P1 cover catégorie-aware (label + pictogramme catégorie, KPIs
  autoconso/couverture/économies, accroche par catégorie) ; P2 équipements + totaux +
  blocs catégorie de la recherche 2026-07-16 (hôtel : tableau saison haute/basse + badge
  éco-OTA ; restaurant/froid : sécurisation chaîne du froid ; boulangerie : transparence
  cuisson nocturne ; école : note fermeture estivale/injection ; bureau : alignement
  horaires/production) ; P3 confiance/étapes/signature. Catégorie lue depuis
  `etude_params.categorie_commerciale` (QX44) ; sans catégorie → blocs génériques.
  **Done =** PDF commercial distinct, blocs conditionnels par catégorie testés, 3 pages.
  (@lane: quote-engine) (@model: opus) (@after: QX43, QX44)
- [x] QX47 — **Devis AGRICOLE : le document que le fermier comprend.** Étendre
  quote_engine/agricole/ : (a) graphique mensuel « eau livrée (pompe, m³/j) vs besoin de la
  culture (ETc mensuel) » — dépend des stades Kc de QX48 ; (b) bloc bassin recommandé (m³ =
  1-3× besoin journalier, « X jours d'autonomie ») ; (c) ligne subvention FDA 30 % avec
  caveat éligibilité (irrigation localisée + fournisseur agréé + dossier DPA/ORMVA guichet
  unique + paiement a posteriori) ; (d) bloc économies vs diesel/butane (dépense actuelle
  saisie → économie annuelle, bande honnête). Réutilise la ligne catalogue SUIVI-2A si elle
  figure au devis (SKU produit `seed_catalogue.py:62` « Suivi journalier, maintenance chaque
  12 mois pendant 2 ans » — c'est un SKU, PAS une tâche plan) : pas de doublon de bloc O&M.
  NOTE : le devis agricole CHIFFRABLE reste gaté par QXG3 (11 pompes à courbe prix=0) —
  le rendu doit dégrader proprement sans prix. **Done =** 4 pages agricoles enrichies,
  tests page-count/snapshot à jour. (@lane: quote-engine) (@model: sonnet) (@after: QX48)
- [x] QX48 — **Moteur agronomique v2 (FAO-56 réel, partagé).** Étendre
  frontend/src/features/ventes/agronomy.js + le miroir backend quote_engine/agricole/
  agronomy.py : (a) table cultures ~16 entrées (agrumes, olivier, amandier, dattier,
  avocatier, myrtille/fraise, tomate/poivron serre, pomme de terre, oignon, melon/pastèque,
  banane serre, vigne, céréales, luzerne, grenadier, figuier, cannabis licite [Kc estimé
  ~1,0 flag ANRAC], arganier) avec Kc-mid FAO-56 Table 12 + valeurs Maroc citées
  (avocatier Gharb 8-12 000 m³/ha/an ; myrtille pics 80 m³/ha/j ; dattier 51 m³/arbre/an) —
  CHAQUE valeur avec sa source en commentaire, plus jamais « à confirmer » nu ; (b) stades
  Kc ini/dev/late → série MENSUELLE d'ETc (le graphe QX47) au lieu du seul mois de pointe ;
  (c) régions + gharb-loukkos + haouz (ET0 mensuels) ; (d) crédit pluie efficace par
  région (l'actuel surestime le Gharb) ; (e) remplacer l'annualisation plate 0,62×300j
  par l'intégrale de la série mensuelle ; (f) garde de suffisance hydraulique du repli CV
  dans solar.js : si HMT+débit saisis, kW_min = Q×HMT×2,725/(1000×η) comparé au CV tapé —
  avertissement « pompe sous-dimensionnée » (jamais un blocage). **Done =** besoins
  mensuels par culture/région testés contre 3 valeurs citées ; miroirs front/back alignés
  (test de parité) ; garde CV testée. (@lane: ventes-frontend) (@model: opus)
- [x] QX49 — **Payload proposition mode-complet.** public_views.py : le payload proposal
  expose `mode_installation`, `categorie_commerciale`, et un bloc KPI par mode (pompage :
  pompe_cv/kw, hmt_m, debit_hmt_m3h, m3_jour, champ_kwc, bassin_m3, fda_eligible ;
  industriel/commercial : taux_autoconso, taux_couverture, economies_annuelles, payback,
  injection_kwh_an/injection_dh_an si calculés) — whitelist stricte côté serveur, jamais
  prix_achat/marge. Tests payload par mode. **Done =** la page web peut rendre 4 variantes
  sans re-calcul client. (@lane: ventes-backend) (@model: sonnet) (@after: QX43)
- [x] QX50 — **Ligne injection 82-21 (industriel/commercial).** computeEtudeIndustrielle +
  builder : option `injection` — surplus = max(0, prod − autoconsommé) plafonné à 20 % de
  la production, valorisé au tarif ANRE période courante (0,21 pointe / 0,18 hors pointe
  DH/kWh) NET des frais d'accès réseau (≈6,07 + 6,38 c/kWh), OFF par défaut, activable par
  devis avec mention obligatoire « tarif ANRE 03/2026-02/2027, plafond en révision ».
  Constantes dans UN module commenté-sourcé (`quote_engine/constants_82_21.py` + miroir
  solar.js) que le fondateur peut vérifier ligne à ligne. **Done =** étude avec injection
  = étude sans + ligne bornée ; jamais affichée sans la mention ; tests bornes 20 %/net.
  (@lane: quote-engine) (@model: opus) (@after: QX43)
- [x] QX51 — **Webhook : questionnaire commercial/industriel v2 persisté.** Étendre la
  whitelist `_extract_web_questionnaire` (webhooks.py) : `categorie_commerciale` + réponses
  par catégorie (chambres, occupation_pct, chambres_froides, cuisson, four, cuisson_nocturne,
  temperature_consigne, effectif, internat, fermeture_estivale, piscine, blanchisserie…),
  industriel v2 (`equipes` 1x8/2x8/3x8/continu, `weekend`, `cos_phi_connu`, `groupe_kva`,
  `diesel_dh_mois`, `surface_toiture_m2`, `ombriere`, `terrain`) — clés snake_case, bornées,
  choix fermés ; note chatter enrichie (résumé par catégorie). Byte-identique sans les
  nouveaux champs. **Done =** tests mapping + note + tolérance. (@lane: crm-webhook)
  (@model: sonnet)
- [x] QX52 — **`instType`/`type_installation` : parité 4 modes (backend+frontend).** Balayage
  des surfaces mode↔type SAUF apps/web (voir NB) : (1) webhooks `_MARKET_MODE_ALIASES`
  (webhooks.py:185-196) mappe DÉJÀ correctement `commercial`→commercial et `professionnel`/
  `professional`→industriel — RIEN à changer, juste garder + tester ; (2) `autoQuote.js`
  `LEAD_TYPE_TO_MODE` (:30-33) mappe aujourd'hui `commercial`→`industriel` (repli), ET la
  branche mode ne connaît que agricole/industriel — le VRAI travail : router `commercial`→
  `commercial` et lui donner sa branche/`DAY_USAGE_DEFAULTS['Commerciale']` ; (3) builder
  `inst_type` (:947-951) reçoit sa clé `commercial` VIA QX43 (déjà couvert — ne pas ré-éditer).
  Le quadruplet residentiel/commercial/industriel/agricole devient cohérent. NB PÉRIMÈTRE :
  le libellé public `instLabel` ([token].astro:214-221, apps/web) traite DÉJÀ `commercial`
  (→ « Autoconsommation ») et appartient à WJ126 — NE PAS le toucher ici (collision inter-plan).
  **Done =** grep de cohérence + tests ; aucun mode ne tombe dans un libellé d'un autre.
  (@lane: frontend-generator) (@model: haiku) (@after: QX43)

GATED (fondateur — vérifications avant durcissement des constantes) :
- [ ] QXG6 — **[GATED: vérifs fondateur avant hard-coding]** (a) tarifs MT ONEE exacts
  (pointe/pleines/creuses TTC) contre le simulateur one.org.ma ; (b) bande prix/kWc C&I
  >100 kWc contre les vraies offres fournisseurs (l'estimation recherche = 6 000-9 000
  DH/kWc HT) ; (c) seuil déclaration/autorisation 82-21 (5 MW vs 1 MW selon sources) ;
  (d) statut du plafond d'injection 20 % (décret en révision). Chaque valeur validée
  remplace le flag « à vérifier » dans constants_82_21.py / la table day-share QX44.
  (@blocked: vérifs fondateur tarifs/seuils) (@lane: founder-verify)

*Notes de cohérence : dépendances QX44/QX46/QX49/QX50/QX52 → QX43 ; QX47 → QX48 ; aucune
circularité. QXG3 (prix des 11 pompes à courbe) reste LE gate du devis agricole chiffré ;
QXG1 (BSP WhatsApp) gate l'envoi automatisé ; QXG4 (contenu confiance réel) vaudra pour les
3 nouveaux renderers. Les moitiés web (WJ117-WJ126) vivent dans docs/WEB_PLAN.md.*

---

### Groupe PUB — Publicité niveau best-in-class : câblage, boucles fermées, console, croissance, créatif, science, finance (audit fondateur 2026-07-19 — 14 agents, 2 rounds, vérifié adversarialement)

> **Doctrine.** Achever la promesse « le fondateur ne rouvre JAMAIS Ads Manager » et fermer les
> boucles que l'audit a prouvées OUVERTES : (a) le front ASG/SIG appelle des routes qui n'existent
> pas ; (b) une grande partie du « cerveau » (rewards, génération IA, VoI, ~11 modules) est du code
> mort testé mais jamais câblé ; (c) la dépense pub n'atteint jamais la compta ni le registre
> plateforme ARC ; (d) l'opérateur ne peut composer manuellement que 1 des 15 kinds d'action.
> Chaque écriture Meta reste propose→approve→apply (règle #3 : naissance PAUSED, jamais d'unpause
> programmatique) ; Odoo reste lecture seule (règle #1) ; STAGES.py jamais en dur (règle #2).
> Cross-app UNIQUEMENT via selectors/services/string-FK (import-linter). Migrations ADDITIVES.
> **Dédupe :** ne JAMAIS reconstruire ENG1-31 / ADSENG1-56 / ADSDEEP1-66 / ASG-AGEN-SIG (tout [x]),
> ni les items GATED existants (ADSENG19 homme-mort, ADSENG34 boucle ctwa_clid, ADSENG50/51/52
> plateformes, XMKT36 export d'audiences générique — consentement). Les tâches [GATED:] ici ne se
> construisent PAS sans la levée de leur porte. Vérifié le 2026-07-19 : `reason_fr` (rationale par
> proposition) existe déjà et s'affiche ; `capi_odoo` envoie déjà value/currency sur signed_contract
> — ne pas re-proposer.

#### PUB-P0 — Réparer le câblage front↔back (écrans morts, composants orphelins, données invisibles)

- [x] PUB1 — **Routes backend `signaux/` + `signaux/cohorte/`** : construire les deux endpoints que `DashboardScreen` (onglet « Signaux », SIG4) appelle déjà dans le vide (404 silencieux) — vues minces sur `health.py` (2 scores créa/ops, mort-par-design en attente) + `signal_guards.evaluate_guards` + `cohorts.py` (watermarks maturité), company-scopées. **Done =** l'onglet Signaux affiche les 2 scores + le quadrant garde-fous + drill cohortes sur données réelles ; `health.py`/`cohorts.py`/`signal_guards.py` ne sont plus des modules morts. Files: `apps/adsengine/{views.py,urls.py,serializers.py}`, tests. (ARCH) (@lane: backend/adsengine-wiring) (@model: opus)
- [x] PUB2 — **Actions `file-voi/`, `<id>/tests/`, `tests/<id>/leads/` sur `noeuds-hypothese/`** : les 3 panneaux de « L'Arbre » (TreeScreen) appellent ces routes inexistantes. `file-voi` expose le classement `voi.py` (S·U·R·T/C) ; `tests` l'historique d'expériences liées au nœud ; `leads` le drill leads d'un test. **Done =** les 3 panneaux de TreeScreen se remplissent ; la file VoI affichée = sortie réelle de `voi.py`. Files: `apps/adsengine/{views.py,serializers.py}`, tests. (ROUTINE) (@lane: backend/adsengine-wiring) (@model: sonnet)
- [x] PUB3 — **Monter `BreakdownsPanel` (démographie/placement/région/heure)** dans AdsCockpitScreen + CampaignsScreen (drill par ad/adset) — le composant est construit + testé + jamais importé par aucun écran, alors que `breakdowns/` sert des données synchronisées chaque semaine. **Done =** panneau visible et peuplé depuis le cockpit et le détail campagne ; e2e hook `ae-*`. Files: `frontend/src/features/adsengine/{AdsCockpitScreen.jsx,CampaignsScreen.jsx}`, tests. (ROUTINE) (@lane: frontend/adsengine-wiring) (@model: haiku)
- [x] PUB4 — **Monter `DaypartingGrid`** (ADSDEEP36 construit, orphelin) dans le composeur d'actions `set_schedule` (PUB22) et en lecture sur le détail adset. **Done =** grille visible, propose une action `set_schedule` via la boîte d'approbation. Files: `frontend/src/features/adsengine/*`, tests. (@after: PUB22) (ROUTINE) (@lane: frontend/adsengine-wiring) (@model: haiku)
- [x] PUB5 — **Monter `EngagementAudiencePicker`** (orphelin ; endpoints `audiences/engagement/` + `delivery-estimate/` vivants côté back) dans FlightPlanScreen/le composeur d'adset. **Done =** création d'audience d'engagement possible depuis l'UI, estimation de diffusion affichée. Files: `frontend/src/features/adsengine/FlightPlanScreen.jsx`+, tests. (ROUTINE) (@lane: frontend/adsengine-wiring) (@model: haiku)
- [x] PUB6 — **Écran « Table des faits » (AGEN1)** : les viewsets `table-faits/` + `faits/` (+ action `publish`) n'ont AUCUNE surface UI — le moteur de génération ancrée est ingérable depuis la console. Écran simple : versions brouillon/publiée, édition des FactEntry, bouton Publier, diff entre versions. **Done =** cycle brouillon→publiée entièrement faisable à l'écran ; e2e. Files: `frontend/src/features/adsengine/` (nouvel écran + module.config.jsx + adsengineApi.js), tests. (ROUTINE) (@lane: frontend/adsengine-wiring) (@model: sonnet)
- [x] PUB7 — **Réparer l'affichage des échecs d'action** : `ActionsLogScreen` lit `a.result_detail`, champ que l'API ne renvoie pas (le serializer expose `result`/`error`) — les raisons d'échec ne s'affichent JAMAIS. Aligner front sur serializer. **Done =** une action échouée montre son erreur réelle ; test régression. Files: `frontend/src/features/adsengine/ActionsLogScreen.jsx`, tests. (ROUTINE) (@lane: frontend/adsengine-wiring) (@model: haiku)
- [x] PUB8 — **Surfacer `video_metrics` complets** : les percentiles p25/50/75/95/100, thruplay, 6s/15s/30s sont synchronisés (ADSDEEP1) puis JETÉS (`reporting.py` ne garde que hook_rate ; aucun `InsightSnapshotSerializer`). Exposer hold_rate/retention_curve/ratio_15s_to_6s déjà calculés par `metrics.derived_ad_video_metrics` dans le cockpit + ReportsScreen (courbe de rétention par ad vidéo). **Done =** courbe de rétention visible par ad vidéo. Files: `apps/adsengine/{serializers.py,reporting.py}`, `frontend/.../ReportsScreen.jsx`+cockpit, tests. (ROUTINE) (@lane: backend/adsengine-wiring) (@model: sonnet)
- [x] PUB9 — **Éditeur complet des garde-fous** : `GuardrailConfig` expose en API `auto_rotate_creative`/`auto_rebalance_within_band`, `pacing_band_pct`, `exploration_floor_*`, `weekly_change_pct_max`, `anomaly_window_hours`, poids santé SIG1 — mais ConnectionScreen n'édite QUE les 2 plafonds budget. Le fondateur ne peut ni voir ni changer les bascules d'auto-application. Écran/section « Garde-fous avancés » avec aide FR par champ. **Done =** chaque champ serialisé est éditable + expliqué ; test. Files: `frontend/src/features/adsengine/` (section garde-fous), tests. (ROUTINE) (@lane: frontend/adsengine-wiring) (@model: sonnet)
- [x] PUB10 — **Parité permissions UI** : la console montre Approuver/Rejeter à tout `responsable` alors que le back exige `adsengine_approve` distinct (découverte en 403). Exposer les permissions effectives (`/me` ou endpoint léger) et masquer/griser les contrôles non autorisés (approbation, armement de règles, composeurs). **Done =** un utilisateur manage-sans-approve ne voit plus les boutons d'approbation actifs. Files: `frontend/src/features/adsengine/*`, éventuel endpoint permissions, tests. (AUTH) (@lane: frontend/adsengine-wiring) (@model: opus)
- [x] PUB11 — **Surfacer les stats de l'Arbre** : `AssumptionNode.alpha/beta/alpha0/beta0`, `enjeux_s`/`pertinence_r`, `tags_saison`, `demi_vie_semaines` sont serialisés mais TreeScreen ne garde que id/énoncé/classe/statut — la base statistique de chaque rang VoI est invisible. Cartes de croyance en français simple (« sûrs à ~72 %, sur N obs ») + delta hebdo. **Done =** chaque nœud montre sa croyance lisible + ses tags saison. Files: `frontend/src/features/adsengine/TreeScreen.jsx`, tests. (ROUTINE) (@lane: frontend/adsengine-wiring) (@model: sonnet)
- [x] PUB12 — **Décider les endpoints orphelins** : `metrics/conversations-per-ad/` (redondant avec ads-cockpit), `reporting/export/` (le front fabrique son CSV en `data:` URI), `creatifs/checklist/`, `experiences/<id>/sync-ad-study/`, viewsets doublons (`connexions/` vs `connection/`, `garde-fous/` vs `guardrail/`, `pacing/`, `decisions/`…) — pour chacun : brancher le front dessus OU le retirer (retrait UNIQUEMENT avec preuve grep de zéro consommateur ; jamais les deux surfaces qui divergent). Basculer l'export CSV sur le `ReportExportView` serveur (source de vérité unique, inclut la table réconciliation). **Done =** zéro endpoint sans consommateur documenté ; export CSV servi par le back. Files: `apps/adsengine/{urls.py,views.py}`, `frontend/.../ReportsScreen.jsx`, tests. (ROUTINE) (@lane: backend/adsengine-wiring) (@model: sonnet)
- [x] PUB13 — **Surfacer `learning_stage_info` brut + `last_sig_edit`** sur le détail adset (fenêtres d'attribution, statut apprentissage, dernière édition significative) — seul le badge dérivé s'affiche aujourd'hui. **Done =** panneau « Apprentissage Meta » lisible par adset. Files: `frontend/src/features/adsengine/CampaignsScreen.jsx`, tests. (ROUTINE) (@lane: frontend/adsengine-wiring) (@model: haiku)
- [x] PUB14 — **E2e des écrans non couverts** : Playwright ne couvre que 5/17 écrans — ajouter au minimum campagnes (drill 3 niveaux), règles (catalogue+journal), reporting (leaderboard/audit), arbre, instagram, plan-de-vol, backlog, simulation, brief, créathèque — spécialement les surfaces ADSDEEP/ASG jamais testées bout-en-bout. **Done =** chaque écran a ≥1 spec e2e qui lit une vraie donnée. Files: `frontend/e2e/`, tests. (ROUTINE) (@lane: frontend/adsengine-e2e) (@model: sonnet)
- [x] PUB115 — **Garde de contrat API front↔back** : test automatique qui énumère chaque chemin appelé par `adsengineApi.js` et l'assertit résolvable contre `apps/adsengine/urls.py` (y compris les `url_path` d'actions) — la classe de bug que PUB1/PUB2 corrigent (front livré avant ses routes) devient structurellement impossible à réintroduire ; le e2e (PUB14) ne couvre pas cette classe. **Done =** route retirée ou méthode front ajoutée sans route → test rouge. Files: `frontend/src/features/adsengine/` (test node) ou `apps/adsengine/tests/` (extraction des chemins), tests. (ROUTINE) (@lane: frontend/adsengine-wiring) (@model: sonnet)

#### PUB-P1 — Réveiller le cerveau mort (modules construits+testés jamais câblés — lane disjointe de P0, aucun prérequis entre eux)

- [x] PUB15 — **Câbler `rewards.py` (boucle de récompense du bandit)** : `run_divergence_check` (veto CRM vs proxy, propose un REBALANCE humain-approuvé) a ZÉRO appelant production — le « budget auto-optimisé » ne s'auto-optimise pas. L'appeler depuis une beat hebdo (ou la boucle gardien) ; l'action proposée passe par la boîte d'approbation existante. **Done =** une divergence proxy/CRM sur fixtures produit une proposition REBALANCE visible dans Approbations ; beat au planning. Files: `apps/adsengine/tasks.py`, `erp_agentique/celery.py`, tests. (ARCH) (@lane: backend/adsengine-brain) (@model: opus)
- [x] PUB16 — **Câbler le pipeline de génération IA ancrée** : `generation.py→claim_check→groundedness→policy_lint→tier_router→video_queue→generation_audit` (~1000+ LOC testées) n'a AUCUN point d'entrée production. Exposer : action « Générer des variantes ancrées » sur BacklogScreen/CreativeLibrary (endpoint + tâche async), key-gated NO-OP proprement sans clé LLM, sortie = `CreativeBacklogItem` nés en attente d'approbation (l'IA produit des ASSETS, jamais des décisions). **Done =** clic → lot de variantes ancrées FactTable dans le backlog, avec audit `claim_verdicts` persisté ; sans clé → message clair, zéro crash. Files: `apps/adsengine/{views.py,tasks.py,urls.py}`, `frontend/.../BacklogScreen.jsx`, tests. (ARCH) (@lane: backend/adsengine-brain) (@model: opus)
- [x] PUB17 — **Câbler réellement le scheduler VoI** : `advance_phase` log-et-return même flag ON — `voi.schedule_next` n'est jamais appelé. Derrière le flag cache existant `voi_scheduler_active` (OFF par défaut), brancher la vraie sélection argmax-VoI dans la transition FlightRunner. **Done =** flag ON sur fixtures → la phase suivante = sortie de `voi.schedule_next` ; flag OFF → comportement actuel byte-identique. Files: `apps/adsengine/flightrunner.py`, tests. (ARCH) (@lane: backend/adsengine-brain) (@model: opus)
- [x] PUB18 — **Nourrir les postérieurs de l'Arbre avec les résultats RÉELS** : aujourd'hui seul le decay hebdo écrit α/β — aucune preuve (résultat d'expérience, signature attribuée) n'incrémente jamais une croyance : l'« arbre vivant » n'apprend pas. Écrire le writer : à la clôture d'une `Experiment`/d'un `DecisionLog` probant (et aux signatures Odoo attribuées à un nœud testé), mise à jour Beta (succès/échecs) + `DecisionLog` de la mise à jour, idempotent. **Done =** une expérience close sur fixtures déplace α/β du nœud lié ; le decay seul ne suffit plus au test. Files: `apps/adsengine/` (nouveau `evidence.py` ou extension), tests. (ARCH) (@lane: backend/adsengine-brain) (@model: opus)
- [x] PUB19 — **Planifier `run_daily_reconciliation`** : la fonction persist+alerte de `reconciliation.py` est morte (aucun beat — seul le CSV on-demand appelle `reconcile`). Beat quotidien + `EngineAlert` sur divergence au-delà du seuil. **Done =** beat au planning, snapshot quotidien créé, divergence seuillée → alerte. Files: `apps/adsengine/tasks.py`, `erp_agentique/celery.py`, tests. (ROUTINE) (@lane: backend/adsengine-brain) (@model: sonnet)
- [x] PUB20 — **Mort du token = alerte, jamais le silence** : `MetaAuthError` est avalée par le `except Exception` de chaque tâche de sync → dashboards figés sans signal. Détecter auth-error dans les syncs → `EngineAlert` type `token_invalide` + état sur `MetaConnection` (+ champ additif `token_expires_at` renseigné à la connexion) + bandeau ConnectionScreen/Dashboard. **Done =** un 190 Meta sur fixtures produit l'alerte + le bandeau ; plus aucun swallow silencieux d'auth-error. Files: `apps/adsengine/{tasks.py,models.py,meta_client.py}`, migration additive, front bandeau, tests. (ARCH) (@lane: backend/adsengine-brain) (@model: opus)
- [x] PUB21 — **Persister autonomie + kill-switch en base** : ces états vivent en cache Redis TTL 30 j — un flush/restart infra annule silencieusement l'arrêt d'urgence. Migrer vers un modèle (ou champs `GuardrailConfig`), cache = accélérateur seulement, source de vérité = DB. **Done =** kill-switch survit à un flush cache (test) ; comportement identique sinon. Files: `apps/adsengine/{flightrunner.py,models.py}`, migration additive, tests. (ARCH) (@lane: backend/adsengine-brain) (@model: opus)
- [x] PUB22 — **Composeurs manuels pour TOUS les kinds d'action** : seul `edit_copy` a un composeur (EditCopyComposer) — l'opérateur ne peut ni shifter un budget, ni pauser un perdant, ni dupliquer un gagnant depuis la console. Composeur par kind RÉEL (`EngineAction.Kind` : create_campaign/create_adset/create_ad/rotate_creative/rebalance_budget/pause/set_spend_cap/rename + constantes services `set_schedule`/`duplicate`/`pause_for_month`/`create_ad_study`/`enable_cbo`) : formulaire ciblé + `reason_fr` + aperçu du payload, sur les lignes Cockpit/Campagnes ; chaque soumission = `propose_action` (JAMAIS d'application directe ; naissance PAUSED intacte pour les créations). Ajouter la validation serveur par kind pour ceux atteignables par POST brut sans producteur curé (`create_ad`/`set_spend_cap`/`rename`). **Done =** chaque kind proposable depuis l'UI avec payload validé par kind ; e2e budget+pause+duplicate. Files: `apps/adsengine/{services.py,views.py}`, `frontend/src/features/adsengine/` (composeurs), tests. (ARCH) (@lane: backend/adsengine-actions) (@model: opus)
- [x] PUB23 — **Armer les règles depuis l'UI** : RulesScreen n'offre que le dry-run — aucune règle ne peut être activée depuis la console. Bouton Armer/Désarmer (permission manage, confirmation avec résumé de la règle + cadence), état visible, journal. **Done =** cycle armer→exécution planifiée→désarmer entièrement à l'écran ; e2e. Files: `frontend/src/features/adsengine/RulesScreen.jsx`, `apps/adsengine/views.py` si besoin, tests. (ROUTINE) (@lane: frontend/adsengine-console) (@model: sonnet)
- [x] PUB24 — **Protéger `upsert_insight` des re-syncs partiels** : les 4 champs cœur (spend/results/frequency/cpl) s'écrivent inconditionnellement — un appel partiel écraserait en NULL/0. Même None-protection que les colonnes ADSDEEP1. **Done =** test : upsert partiel ne clobber plus les métriques existantes. Files: `apps/adsengine/sync.py`, tests. (ROUTINE) (@lane: backend/adsengine-brain) (@model: sonnet)
- [x] PUB25 — **Statuer sur chaque module mort restant** : `authority.py`, `dco.py`, `priors.py`, `seeding.py` (doublon du seed réel), `cohorts.py` (si non pris par PUB1), `assumption_graph.py` (cascade d'invalidation jamais déclenchée), `policy_lint_config.py` — pour chacun : câbler (petit point d'entrée réel) OU documenter « en attente de X » dans le module même ; retirer SEULEMENT un doublon avéré (ex. seeding.py vs le seed réel), preuve grep à l'appui. Aucun module ne reste silencieusement mort. **Done =** inventaire commité (docstring/`docs/engine/`) + zéro module sans statut explicite ; ceux câblés ont un test d'atteignabilité. Files: `apps/adsengine/*`, docs. (ROUTINE) (@lane: backend/adsengine-brain) (@model: sonnet)

#### PUB-P2 — Boucle business & attribution (webhooks, CAPI, qualité de lead, diagnostics Meta)

- [x] PUB26 — **Vérifier la signature HMAC du webhook Lead Ads** : `meta_lead_ads_webhook` ne vérifie PAS `X-Hub-Signature-256` alors que `META_LEAD_ADS_APP_SECRET` est listé dans `WIRING_ENV_KEYS` (views.py:62) mais jamais utilisé pour vérifier la signature — n'importe qui peut poster de faux leads. Miroir exact de la vérification du webhook WhatsApp (whatsapp_webhook.py:65-73) ; rétro-compatible si secret absent (log warning). **Done =** payload mal signé → 403 (test) ; payload signé → inchangé. Files: `apps/crm/webhooks.py`, tests. (AUTH) (@lane: backend/crm-growth) (@model: opus)
- [x] PUB27 — **CTWA sans lead existant = attribution échouée** : `_lead_id_for_phone` ne fait que matcher — une conversation WhatsApp-first sans Lead préalable stocke un `CtwaReferral` orphelin (`crm_lead_id=None`) et l'attribution est perdue. Auto-créer un Lead minimal (téléphone + source ctwa + ad_id, company résolue par la connexion) via `apps.crm.services`, dédupliqué par téléphone, env-gated comme le webhook. **Done =** referral sans lead → Lead créé + lié ; referral avec lead → comportement inchangé ; jamais de doublon. Files: `apps/adsengine/whatsapp_webhook.py`, `apps/crm/services.py` (fonction fine), tests. (ARCH) (@lane: backend/crm-growth) (@model: opus)
- [x] PUB28 — **Taxonomie junk-lead + taux par annonce** : `motif_perte` est texte libre (la liste `MotifPerte` par société ne distingue pas junk/réel). Ajouter `MotifPerte.est_junk` (bool additive) + seed de motifs standards (« numéro invalide », « spam/bot », « hors zone », « jamais répondu » junk ; « prix », « concurrent », « reporté » réels) idempotent et additive-only ; puis `attribution_lead_rows` expose `junk` distinct de « non qualifié » et le cockpit/reporting affichent le **taux de junk par ad** — le signal qualité qui manque au veto de divergence. **Done =** taux junk par ad visible ; seed re-runnable sans doublon ; leads existants intacts. Files: `apps/crm/{models.py,migrations}`, `apps/adsengine/{selectors.py,reporting.py}`, front cockpit, tests. (SCHEMA) (@lane: backend/crm-growth) (@model: sonnet)
- [x] PUB29 — **Étendre `wiring-health` + audit aux clés manquantes** : l'écran santé ignore `META_CRM_STAGE_CAPI_ENABLED`, `CAPI_CRM_DATASET_ID`/tokens, les 4 `ODOO_*` et les 3 `WHATSAPP_CLOUD_*` — le fondateur ne peut pas voir quelles boucles déjà codées attendent juste leur clé. Ajouter chaque clé + un panneau ConnectionScreen « Boucles en attente d'activation » avec l'étape manuelle exacte (dashboard Meta App, dataset, etc.). **Done =** chaque hop key-gated de la boucle est visible ON/OFF avec remédiation FR. Files: `apps/adsengine/{views.py,audit.py}`, `frontend/.../ConnectionScreen.jsx`, tests. (ROUTINE) (@lane: backend/adsengine-loop) (@model: sonnet)
- [x] PUB30 — **Événement CAPI « visite technique effectuée »** : `capi_crm` ne se déclenche que sur les transitions STAGES — le RDV terrain honoré (`Appointment` EFFECTUE), signal offline le plus proche de la vente, est invisible de Meta. Émettre un événement dédié (même famille/ADSENG32, même gating, event_id déterministe), mappé en DONNÉES pas en dur. **Done =** transition EFFECTUE sur fixtures → événement émis une seule fois ; sans clés → no-op silencieux loggué. Files: `apps/adsengine/capi_crm.py`, `apps/crm/receivers.py` (signal), tests. (ROUTINE) (@lane: backend/adsengine-loop) (@model: sonnet)
- [x] PUB31 — **Valeur estimée du devis sur l'événement QUOTE_SENT** : enrichir (optionnel, flag) l'événement de stage QUOTE_SENT avec `custom_data.value/currency` = montant TTC du devis lié — Meta peut alors optimiser sur la valeur dès le milieu de funnel (les tickets vont de 40k à 200k MAD ; le binaire jette cet écart). `signed_contract` (capi_odoo) le fait déjà — NE PAS y toucher. **Done =** QUOTE_SENT porte la valeur quand le flag est ON ; OFF par défaut = byte-identique. Files: `apps/adsengine/capi_crm.py`, `apps/ventes/selectors.py` (lecture fine), tests. (ROUTINE) (@lane: backend/adsengine-loop) (@model: sonnet)
- [x] PUB32 — **Sync des diagnostics de classement Meta** : `quality_ranking`/`engagement_rate_ranking`/`conversion_rate_ranking` (niveau ad) ne sont jamais tirés, alors que `signal_guards.quality_ranking_guard` existe déjà, mort, prêt à les lire. Les ajouter au sync ad-level (colonnes additives ou JSON) + câbler le guard (brake-only). Explorer en même temps si le « opportunity score » est exposé par l'API Marketing — sinon le documenter comme non disponible. **Done =** rankings visibles par ad au cockpit ; guard actif sur fixture « below_average ». Files: `apps/adsengine/{sync.py,tasks.py,models.py}`, migration additive, tests. (SCHEMA) (@lane: backend/adsengine-loop) (@model: sonnet)
- [x] PUB33 — **Vigie vélocité d'apprentissage** : personne ne surveille le seuil ~50 événements d'optimisation/7 j par adset — un adset structurellement affamé se voit après coup dans le CPA. Détecteur (données déjà synchronisées : results/leads_count par jour) qui alerte « adset sous le seuil d'apprentissage » avec le déficit, + suggestion de consolidation. **Done =** adset sous seuil sur fixtures → `EngineAlert` explicative FR. Files: `apps/adsengine/anomaly.py`, tests. (ROUTINE) (@lane: backend/adsengine-loop) (@model: sonnet)
- [x] PUB34 — **Règle de santé structurelle (doctrine Andromeda 2025)** : le ranking Meta lit désormais le créatif — la fragmentation (beaucoup de petits adsets) affame l'algorithme ; la doctrine 2026 = 2-3 adsets, 15-25 créas diverses/adset. Détecteur de structure (nb d'adsets actifs/campagne, créas par adset, chevauchement) → alerte + recommandation de consolidation (JAMAIS d'action auto). **Done =** compte fragmenté sur fixtures → alerte avec le plan de consolidation suggéré. Files: `apps/adsengine/anomaly.py` (ou `rules_engine.py` template), tests. (ROUTINE) (@lane: backend/adsengine-loop) (@model: sonnet)
- [x] PUB35 — **Ingestion des colonnes « Incremental Attribution » natives Meta** : natives Meta depuis avr. 2025 — contre-vérification causale des choix du bandit (les clics attribués ≠ incrémentaux). ÉTAPE 1 : vérifier la disponibilité des colonnes sur le compte (déploiement Meta progressif) ; puis champs additifs sur le sync + affichage comparatif attribué-vs-incrémental au cockpit/reporting. **Done =** les deux lectures côte à côte par ad ; si l'API ne renvoie pas les colonnes pour le compte, dégradation propre documentée. Files: `apps/adsengine/{meta_client.py,sync.py}`, front, tests. (ROUTINE) (@lane: backend/adsengine-loop) (@model: sonnet)
- [x] PUB36 — **Cockpit de décrochage par étape, PAR variante** : étendre `variant_attribution` au-delà du binaire qualifié/signé — à quelle étape STAGES.py les leads de chaque annonce meurent (jamais CONTACTED = problème ciblage ; meurt à QUOTE_SENT = problème prix/closing). Étapes lues via `pipeline_stage_order()` (règle #2, jamais en dur). **Done =** entonnoir par variante visible au reporting ; test grep-garde stages. Files: `apps/adsengine/{attribution.py,reporting.py}`, front, tests. (ROUTINE) (@lane: backend/adsengine-loop) (@model: sonnet)
- [x] PUB37 — **Flag no-show sur les RDV + taux par annonce** : `Appointment.statut` ne distingue pas no-show d'annulé — une annonce qui génère des RDV fantômes coûte cher avant que le coût-par-signature ne le montre. Statut additif NO_SHOW + injection dans `variant_attribution` comme signal qualité intermédiaire. **Done =** taux no-show par variante au reporting ; migration additive. Files: `apps/crm/models.py`+migration, `apps/adsengine/attribution.py`, tests. (SCHEMA) (@lane: backend/crm-growth) (@model: sonnet)
- [x] PUB38 — **Harnais d'incrémentalité geo-holdout (GeoLift-style)** : zéro couche causale aujourd'hui — rien ne prouve que les signatures attribuées sont incrémentales vs organiques. Harnais MINIMAL : définir une zone tenue (villes), période, puis rapport avant/après vs zones actives sur les données ERP réelles (leads/signatures par ville) — analyse + rapport FR, AUCUNE action auto, pas de dépendance R/externe. **Done =** commande + écran rapport « test géo » lisible fondateur avec intervalles larges honnêtes. Files: `apps/adsengine/` (nouveau `incrementality.py` + vue), tests. (ROUTINE) (@lane: backend/adsengine-science) (@model: opus)
- [x] PUB39 — **Re-valider les fenêtres d'attribution (refonte Meta mars 2026)** : le click-through est désormais link-clicks-only + « engage-through » nouveau — vérifier les constantes centralisées ADSDEEP4 contre la doc actuelle, ajuster si besoin, et re-stamper le test-garde. **Done =** constantes conformes à la doc 2026 (source citée en commentaire), garde à jour. Files: `apps/adsengine/meta_client.py`, tests. (ROUTINE) (@lane: backend/adsengine-loop) (@model: sonnet)

#### PUB-P3 — Console opérateur : le cockpit quotidien d'un fondateur solo

- [x] PUB40 — **Sélecteur de période + comparaison partout** : aucun écran de données (Dashboard/Cockpit/Campagnes/Journal) n'a de date-range — impossible d'isoler « hier » ou de comparer à la semaine passée. Composant commun (presets hier/7j/30j/personnalisé + « vs période précédente » avec deltas %) branché sur les endpoints (paramètres date à ajouter où absents). **Done =** « hier vs même jour semaine passée » possible sur les 4 écrans ; deltas visibles. Files: `apps/adsengine/views.py` (params date), `frontend/src/features/adsengine/*`, tests. (ROUTINE) (@lane: frontend/adsengine-console) (@model: sonnet)
- [x] PUB41 — **Fraîcheur + panne visibles** : zéro auto-refresh, et chaque liste avale ses erreurs en état-vide (`catch(() => setX([]))`) — une panne Meta ressemble à « pas de données ». Endpoint léger statut-sync (dernier sync OK par type + âge) ; bandeau global « Meta ne répond plus depuis X min, données du JJ/MM HH:MM » ; horodatage discret par tuile ; auto-refresh (poll doux) sur Approbations + Commentaires ; distinguer partout état-vide vs état-erreur. **Done =** sync cassé sur fixtures → bandeau + tuiles horodatées, plus aucun silence. Files: `apps/adsengine/views.py`, `frontend/src/features/adsengine/*`, tests. (ROUTINE) (@lane: frontend/adsengine-console) (@model: sonnet)
- [x] PUB42 — **File « Aujourd'hui » unifiée** : alertes, anomalies, approbations en attente, commentaires non traités et briefs vivent dans 4+ boîtes déconnectées — personne ne répond à « que dois-je faire ce matin ? ». Écran d'accueil `/publicite` : file classée par priorité (garde-fous > alertes > approbations > commentaires > digest), chaque item cliquable vers son écran, badge de comptage dans la nav. **Done =** un seul écran du matin, 30 secondes, tout y est ; e2e. Files: `frontend/src/features/adsengine/` (nouvel écran), `apps/adsengine/views.py` (agrégateur mince), tests. (ROUTINE) (@lane: frontend/adsengine-console) (@model: sonnet)
- [x] PUB43 — **Vues enregistrées un-clic** : Top Ads / En fatigue / En baisse / Meilleures vidéos comme onglets prédéfinis du cockpit (filtres+tri figés sur les métriques déjà calculées), + mémoire des derniers filtres (localStorage). **Done =** 4 vues un-clic + filtres persistants entre visites. Files: `frontend/src/features/adsengine/AdsCockpitScreen.jsx`, tests. (ROUTINE) (@lane: frontend/adsengine-console) (@model: haiku)
- [x] PUB44 — **Fiche « histoire complète » d'une ad** (`/publicite/ad/:id`) : créatif + dépense/leads/junk/signatures + actions passées + commentaires + règles l'ayant touchée + expériences + breakdowns — aujourd'hui éclaté sur 6 écrans. Endpoint d'agrégation mince (réutilise les selectors existants) + liens croisés depuis Cockpit/Campagnes/Journal/Commentaires. **Done =** « que se passe-t-il avec CETTE ad » = une page ; e2e. Files: `apps/adsengine/views.py`, `frontend/src/features/adsengine/` (nouvel écran), tests. (ROUTINE) (@lane: frontend/adsengine-console) (@model: sonnet)
- [x] PUB45 — **Annuler = proposer l'inverse** : depuis le Journal, bouton « Annuler » sur une action appliquée qui génère la proposition inverse (rétablir l'ancien budget mémorisé, re-pauser…) via le circuit propose→approve normal — JAMAIS d'écriture directe ; kinds non inversibles (create) → explication. **Done =** budget modifié puis annulé sur fixtures = proposition inverse pré-remplie dans Approbations. Files: `apps/adsengine/{services.py,views.py}`, `frontend/.../ActionsLogScreen.jsx`, tests. (ARCH) (@lane: backend/adsengine-actions) (@model: opus)
- [x] PUB46 — **Assistant de connexion guidé** : ConnectionScreen = 6 champs de tokens bruts sans aide — plus technique qu'Ads Manager lui-même. Wizard pas-à-pas FR (créer l'app Meta, le System User, générer le token, trouver l'ad account ID — captures/liens), checklist de santé avec remédiation par item, test de connexion par étape. **Done =** un non-technicien suit le wizard de zéro à connexion verte sans aide externe. Files: `frontend/src/features/adsengine/ConnectionScreen.jsx`, tests. (ROUTINE) (@lane: frontend/adsengine-console) (@model: sonnet)
- [x] PUB47 — **Exports dignes d'être montrés** : un seul CSV brut aujourd'hui. PDF imprimable propre (logo, période, filtres) pour Dashboard/Reporting/Cockpit (CSS print — pas de dépendance lourde) + CSV serveur partout où une table s'affiche (via PUB12). **Done =** « Imprimer/PDF » sur les 3 écrans, sortie propre A4. Files: `frontend/src/features/adsengine/*`, tests. (@after: PUB12) (ROUTINE) (@lane: frontend/adsengine-console) (@model: haiku)
- [x] PUB48 — **Centre de notifications persistant** : le bandeau d'alertes disparaît au refresh et n'existe que sur le Dashboard. Cloche globale console : historique, lu/non-lu, snooze par alerte (réutiliser le moteur de notifications unifié de l'ERP — `notify()` — pas un système parallèle), lien vers l'entité. **Done =** alerte snoozée ne re-notifie pas avant l'échéance ; historique consultable. Files: `frontend/src/features/adsengine/`, `apps/adsengine/alerts.py` (brancher notify), tests. (ROUTINE) (@lane: frontend/adsengine-console) (@model: sonnet)
- [x] PUB49 — **Annotations de décision sur les courbes** : note libre épinglée à une date (« budget baissé ici — Ramadan ») affichée en surimpression sur les courbes Dashboard/Reporting — la mémoire écrite qui manque pour relire une courbe des mois plus tard. Modèle `Annotation` (company, date, texte, portée) additive. **Done =** note posée visible sur les courbes concernées. Files: `apps/adsengine/{models.py,views.py}`+migration, front, tests. (SCHEMA) (@lane: frontend/adsengine-console) (@model: sonnet)
- [x] PUB50 — **Gabarits de proposition réutilisables** : enregistrer une combinaison (budget/planning/portée) comme modèle nommé (« Ramadan agressif », « hiver prudent ») ré-applicable en un clic depuis les composeurs PUB22. Modèle `ProposalTemplate` additive. **Done =** créer/appliquer/supprimer un gabarit ; l'application pré-remplit le composeur, ne propose rien toute seule. Files: `apps/adsengine/{models.py,views.py}`+migration, front, tests. (@after: PUB22) (ROUTINE) (@lane: frontend/adsengine-console) (@model: sonnet)
- [x] PUB51 — **Raccourcis + palette de commandes** : navigation clavier sur Approbations (A approuver, R rejeter, J/K naviguer — l'écran-vaisseau-amiral) + palette Ctrl-K console (sauter à un écran/une campagne/une ad). **Done =** pile d'approbations traitable sans souris ; palette fonctionnelle. Files: `frontend/src/features/adsengine/*`, tests. (ROUTINE) (@lane: frontend/adsengine-console) (@model: haiku)
- [x] PUB52 — **Comparateur côte-à-côte** : sélectionner 2-4 ads/campagnes/créas → métriques alignées en colonnes, écarts en surbrillance — la décision « je coupe A ou B » sur un seul écran. **Done =** comparaison 2-4 entités depuis Cockpit/Campagnes. Files: `frontend/src/features/adsengine/*`, tests. (ROUTINE) (@lane: frontend/adsengine-console) (@model: haiku)
- [x] PUB53 — **Liens retour Lead/Devis → annonce d'origine** : la traçabilité existe dashboard→leads, jamais l'inverse — un commercial sur une fiche Lead ne sait pas quelle pub l'a produit. Sur la fiche Lead CRM (et le Devis lié) : badge « Vient de la pub X » cliquable vers PUB44, via les champs d'attribution déjà stockés (lecture par selector adsengine, pas d'import de modèles). **Done =** fiche Lead d'un lead Meta → lien vers son ad. Files: `frontend/src/features/crm/`+`ventes/`, `apps/adsengine/selectors.py`, tests. (@after: PUB44) (ROUTINE) (@lane: frontend/adsengine-console) (@model: sonnet)
- [x] PUB54 — **Aide contextuelle FR (« ? » pédagogiques)** : tooltip d'explication en français simple sur chaque métrique technique (MER, fréquence, apprentissage, coût par signature, junk rate…) — contenu statique, zéro dépendance. **Done =** chaque métrique du Dashboard/Cockpit a son « ? ». Files: `frontend/src/features/adsengine/*`, tests. (ROUTINE) (@lane: frontend/adsengine-console) (@model: haiku)
- [x] PUB55 — **Chatter de campagne (pattern CRM)** : fil chronologique par campagne/ad mêlant événements auto (actions appliquées, alertes) et notes manuelles — même pattern que `crm.LeadActivity` (acting user + company server-side), affiché sur PUB44 et le détail campagne. **Done =** note posée + événements auto dans un seul fil par entité. Files: `apps/adsengine/{models.py,views.py}`+migration, front, tests. (@after: PUB44) (SCHEMA) (@lane: backend/adsengine-actions) (@model: sonnet)
- [x] PUB56 — **Tables responsives mobiles** : le cockpit à ~11 colonnes en `<table>` fixe est inutilisable au téléphone — fallback cartes sous breakpoint (pattern MB existant de l'ERP), cibles tactiles sur Approbations. **Done =** cockpit + approbations utilisables à 375 px (gate Playwright mobile existant). Files: `frontend/src/features/adsengine/*`, tests. (ROUTINE) (@lane: frontend/adsengine-console) (@model: sonnet)
- [x] PUB57 — **Digest quotidien actionnable + tuile score d'audit** : le `daily_ads_digest` (déjà livré in-app/email) gagne des liens profonds par item (vers l'ad, l'approbation, l'alerte) ; le score de l'audit de compte (`reporting/audit`) devient une tuile Dashboard auto-chargée avec tendance — aujourd'hui enterré en 3e onglet jamais ouvert. **Done =** digest cliquable ; tuile score visible avec delta hebdo. Files: `apps/adsengine/digest.py`, `frontend/.../DashboardScreen.jsx`, tests. (ROUTINE) (@lane: frontend/adsengine-console) (@model: haiku)

#### PUB-P4 — Boucles de croissance (audiences ERP, géo, cycle client) — consentement : réutilise la porte d'audiences EXISTANTE (`custom_audience_consent_enabled`), jamais un contournement

- [x] PUB58 — **Audiences « devis vu / jamais ouvert »** : le view-tracking `ShareLink` (QJ1) dort en base — segmenter (a) devis jamais ouvert vs (b) ouvert non signé (objection prix) en deux Custom Audiences poussées par `sync_crm_custom_audience` (ADSDEEP57 — aujourd'hui ZÉRO appelant production ; PUB58 en est le premier), chacune avec un angle de relance différent. **Done =** les 2 segments construits sur fixtures et poussés (mock) ; consentement OFF → no-op. Files: `apps/ventes/selectors.py` (lecture fine), `apps/adsengine/audiences.py`, tests. (ROUTINE) (@lane: backend/adsengine-growth) (@model: sonnet)
- [x] PUB59 — **Audience « devis expiré »** : `Devis.statut=expire` (objet ≠ lead COLD) → audience dédiée « votre prix était valable 30 j, nouvelle offre » — l'angle-offre précis que la nurture générique rate. **Done =** segment poussé (mock), exclusions signées correctes. Files: `apps/adsengine/audiences.py`, `apps/ventes/selectors.py`, tests. (ROUTINE) (@lane: backend/adsengine-growth) (@model: haiku)
- [x] PUB60 — **Audiences cross-sell base installée** : clients SIGNED sans contrat de maintenance (`sav`) ou sans batterie sur le devis d'origine → 2 audiences d'upsell (entretien, batterie). Lecture sav/ventes par selectors uniquement. **Done =** segments corrects sur fixtures ; poussés (mock) sous la porte consentement. Files: `apps/adsengine/audiences.py`, `apps/sav/selectors.py`+`ventes/selectors.py`, tests. (ROUTINE) (@lane: backend/adsengine-growth) (@model: sonnet)
- [x] PUB61 — **Lookalike « signatures réelles »** : graine = contacts des deals SIGNÉS Odoo/ERP (hash SHA-256, ≥100 contacts requis par Meta — vérifier le seuil et dégrader proprement en dessous) — une donnée de graine strictement meilleure que tout pixel concurrent. Réutilise `create_lookalike` (ADSDEEP58) — ne pas re-implémenter le mécanisme. Sous la même porte consentement. **Done =** graine construite + lookalike demandé (mock) ; <100 contacts → message clair, pas d'appel. Files: `apps/adsengine/audiences.py`, tests. (ROUTINE) (@lane: backend/adsengine-growth) (@model: sonnet)
- [x] PUB62 — **Carte chaleur ville : CPL, coût-par-signature, ticket moyen** : croiser `InsightBreakdown` région Meta avec `Lead.ville`/GPS réels + devis signés — CPL par ville, coût-par-signature par ville, ET ticket moyen signé par ville (une ville chère en CPL mais à gros tickets industriels peut gagner). Rapport + vue carte/table au reporting. **Done =** table villes triable sur les 3 métriques ; villes sans données omises (jamais « 0 »). Files: `apps/adsengine/reporting.py`, `apps/crm/selectors.py`+`ventes/selectors.py`, front, tests. (ROUTINE) (@lane: backend/adsengine-growth) (@model: sonnet)
- [x] PUB63 — **Pipeline témoignage → brief créatif** : deal SIGNED + satisfaction qhse ≥4/5 + photos chantier → brief structuré auto (kWc/économie/ville/avant-après, faits vérifiés seulement) mis en file `CreativeBacklogItem` pour approbation — aujourd'hui AUCUNE source créative ne part du client réel. Consentement PUB75 requis avant tout usage d'image/nom. **Done =** deal éligible sur fixtures → brief en backlog, bloqué sans consentement. Files: `apps/adsengine/backlog.py`, selectors qhse/ventes/installations, tests. (@after: PUB75) (ROUTINE) (@lane: backend/adsengine-creative) (@model: sonnet)
- [x] PUB64 — **Calculateur recyclage COLD** : arbitrage GO/NO-GO « réactiver un lead COLD vs acheter un lead neuf » basé sur les taux de conversion historiques réels par âge-au-COLD et le CAC courant par mode marché — un calculateur d'aide à la décision, pas une nurture. **Done =** rapport FR avec les deux coûts comparés et intervalle honnête ; données insuffisantes → le dit clairement. Files: `apps/adsengine/reporting.py`, `apps/crm/selectors.py`, front, tests. (ROUTINE) (@lane: backend/adsengine-growth) (@model: sonnet)
- [x] PUB65 — **Parrainage → graine publicitaire** : quand un `crm.Parrainage` convertit, proposer (jamais auto) une graine lookalike/géo autour du parrain — le programme de parrainage et le moteur pub ne se parlent jamais. Sous porte consentement. **Done =** conversion de parrainage sur fixtures → suggestion visible, actionnable via approbation. Files: `apps/adsengine/audiences.py`, `apps/crm/receivers.py` (événement), tests. (ROUTINE) (@lane: backend/adsengine-growth) (@model: sonnet)
- [x] PUB66 — **Halo géographique autour des installations** : audience géo-radius (500 m-2 km) autour du GPS d'une installation fraîche + angle « vu sur les toits du quartier » — l'effet-voisin du solaire visible, jamais exploité alors que le GPS existe. Consentement client (PUB75) pour toute mention/photo du chantier ; l'audience géo pure (sans données client) reste possible sans. **Done =** audience géo proposée à la signature (mock) ; aucune donnée client dans le ciblage sans consentement. Files: `apps/adsengine/audiences.py`, selectors installations, tests. (ROUTINE) (@lane: backend/adsengine-growth) (@model: sonnet)
- [x] PUB67 — **Saisonnalité pilotée par l'historique RÉEL** : vélocité de signatures mois-par-mois PAR MODE MARCHÉ depuis l'historique Devis/Facture de la société → recommandation de réallocation budgétaire saisonnière (distincte du calendrier fixe PUB78 : ici c'est la donnée Taqinor, pas le calendrier générique). Recommandation seulement — jamais d'action auto. **Done =** rapport « votre saisonnalité » avec recommandation par mode ; <12 mois de données → le dit et s'abstient. Files: `apps/adsengine/{reporting.py,pacing.py}`, `apps/ventes/selectors.py`, tests. (ROUTINE) (@lane: backend/adsengine-growth) (@model: sonnet)
- [x] PUB68 — **SLA première réponse + temps-de-réponse par annonce** : la donnée la plus documentée du marché (répondre <1 min ≈ ×4-5 conversion) et l'ERP ne mesure RIEN : horodater le premier contact sortant par lead (activité chatter existante), exposer temps-de-réponse médian PAR AD au cockpit + alerte « lead Meta sans premier contact depuis X min » via notify(). L'auto-réponse elle-même reste gated (PUB108). **Done =** médiane par ad visible ; lead non contacté → alerte au fil SLA configuré. Files: `apps/adsengine/{selectors.py,reporting.py,alerts.py}`, `apps/crm/selectors.py`, front, tests. (ROUTINE) (@lane: backend/adsengine-growth) (@model: sonnet)
- [x] PUB69 — **Carte de partage client trackable** : après signature, générer une carte/lien « mon installation » (UTM propre, canal `parrainage_whatsapp`) que le client forwarde lui-même — bouche-à-oreille organique mesuré, remonte dans l'attribution existante comme canal distinct. **Done =** lien généré par install, visites/leads attribués au canal parrainage_whatsapp. Files: `apps/ventes/` ou `crm` (ShareLink pattern existant), `apps/adsengine/attribution.py`, front, tests. (ROUTINE) (@lane: backend/adsengine-growth) (@model: sonnet)

#### PUB-P5 — Intelligence créative (bibliothèque vivante, mines internes, gouvernance)

- [x] PUB70 — **Veille concurrentielle (Ad Library, périmètre honnête)** : le module est AVEUGLE aux pubs des concurrents solaires MA/MENA. ÉTAPE 1 : vérifier la couverture de l'API officielle Ad Library pour les pubs COMMERCIALES marocaines (attendu : NON couvertes — l'API ne sert que politique/EU) ; si non couverte, NE PAS scraper (règle #5) — construire la veille manuelle outillée : liste de Pages concurrentes avec liens Ad Library web profonds, saisie manuelle structurée d'hooks/angles observés (« inspiration », jamais copiés verbatim), timeline de cadence par concurrent sur ces saisies. Tout passage à une collecte automatisée = [GATED: décision fondateur + dossier tos_risk/]. **Done =** écran Veille avec Pages suivies + liens profonds + hooks saisis exploitables en briefs ; zéro scraping. Files: `apps/adsengine/` (modèle + écran), migration, tests. (ROUTINE) (@lane: backend/adsengine-creative) (@model: sonnet)
- [x] PUB71 — **Mine de questions des commentaires** : `comments.py` synchronise déjà tout — extraction PURE (regex/heuristique FR-Darija, PAS de LLM) des questions récurrentes (prix ? garantie ? subvention ? durée ?) agrégées par thème → candidats `seed_brief` pour la génération + section FAQ au reporting créatif. **Done =** questions récurrentes agrégées visibles + versables en briefs. Files: `apps/adsengine/` (nouveau `comment_mining.py`), front, tests. (ROUTINE) (@lane: backend/adsengine-creative) (@model: sonnet)
- [x] PUB72 — **Mine des objections CRM** : `motif_perte` + notes de chatter `LeadActivity` (texte libre) → top objections par mots-clés simples (prix/confiance/délai/technique) PAR variante d'annonce — l'or que aucun SaaS concurrent ne peut toucher. Tags mots-clés purs (pas de LLM), alimente les angles de génération. **Done =** top objections par ad au reporting ; angles suggérés en backlog. Files: `apps/adsengine/` (extension comment_mining ou nouveau), `apps/crm/selectors.py`, tests. (ROUTINE) (@lane: backend/adsengine-creative) (@model: sonnet)
- [x] PUB73 — **Pipeline photo-chantier → créathèque** : les techniciens uploadent déjà des photos géotaguées (`installations.PhotoAnnotation`) — les meilleures n'atteignent jamais la bibliothèque créative. Action « proposer à la créathèque » (sélection manuelle + import auto flaggé), `CreativeAsset(source_lane='chantier')`, métadonnées ville/kWc, BLOQUÉ sans consentement client (PUB75). **Done =** photo de chantier importable en asset avec provenance ; sans consentement → refus expliqué. Files: `apps/adsengine/creative_factory.py`, selectors installations, front créathèque, tests. (@after: PUB75) (ROUTINE) (@lane: backend/adsengine-creative) (@model: sonnet)
- [x] PUB74 — **Fatigue au niveau du VISUEL** : la fatigue existante est par ad — `visual_asset_key` existe précisément pour identifier un visuel réutilisé et AUCUNE analytique ne s'en sert. Détecter « même visuel sur N créas malgré des hooks différents » + le déclin cross-ads du visuel. **Done =** visuel sur-utilisé sur fixtures → signal au leaderboard créatif. Files: `apps/adsengine/anomaly.py` ou `metrics.py`, tests. (ROUTINE) (@lane: backend/adsengine-creative) (@model: sonnet)
- [x] PUB75 — **Registre de consentement image/témoignage (CNDP loi 09-08)** : `policy.py` interdit les FAUX témoignages mais rien ne vérifie le consentement RÉEL d'un vrai visage/chantier/nom. Modèle `ConsentRecord` (client, portée photo/vidéo/témoignage/géo, date, expiration, révocation), check bloquant dans la passe policy pour tout asset marqué « client réel », UI de collecte (lien WhatsApp signable simple). **Done =** asset client-réel sans consentement → policy FAIL explicite ; consentement révoqué → asset retiré de la rotation. Files: `apps/adsengine/{models.py,policy.py}`+migration, front, tests. (SCHEMA) (@lane: backend/adsengine-creative) (@model: opus)
- [x] PUB76 — **Expiration/rafraîchissement des assets** : `expires_at`/`review_after` additifs + job hebdo qui signale un asset citant une version de FactTable RÉVISÉE depuis (chiffre périmé à l'antenne = risque conformité) ou une créa saisonnière hors saison. **Done =** fait révisé → assets citant l'ancienne version flaggés « à revoir ». Files: `apps/adsengine/{models.py,tasks.py}`+migration, tests. (ROUTINE) (@lane: backend/adsengine-creative) (@model: sonnet)
- [x] PUB77 — **Champ langue + parseur** : deux variantes FR/Darija du même hook sont indistinguables — champ `language` (fr/ar-ma/amazigh) sur `CreativeAsset` + dimension langue dans `naming.py` (`KNOWN_FIELDS`) + split par langue au leaderboard (la donnée marché : Darija sous-titré FR ≈ +34 % de complétion à vérifier sur NOS données). **Done =** performance comparable par langue au reporting. Files: `apps/adsengine/{models.py,naming.py,reporting.py}`+migration, tests. (SCHEMA) (@lane: backend/adsengine-creative) (@model: sonnet)
- [x] PUB78 — **Calendrier créatif marocain** : `seasonal_tag` est du texte libre sans source — modèle `CreativeCalendarEvent` seedé (Ramadan mobile, Aïds, rentrée, canicule, saison agricole post-récolte) qui alimente le tri du backlog + des fenêtres de recommandation (« préparer les créas Ramadan J-30 »). **Done =** backlog trié par la vraie proximité calendaire ; seed idempotent. Files: `apps/adsengine/` (nouveau `calendar.py`+modèle), migration, tests. (ROUTINE) (@lane: backend/adsengine-creative) (@model: sonnet)
- [x] PUB79 — **Déclencheur météo** : `installations/weather.py` tourne déjà pour la planification technicien et n'est JAMAIS lu côté pub — au franchissement d'un seuil (canicule ⇒ angle pompage/clim), proposer (backlog, jamais auto) un changement d'angle ancré FactTable. **Done =** canicule sur fixtures → suggestion d'angle en backlog avec la donnée météo citée. Files: `apps/adsengine/` (nouveau `weather_trigger.py`), selector installations, tests. (ROUTINE) (@lane: backend/adsengine-creative) (@model: sonnet)
- [x] PUB80 — **Couverture formats + segments** : (a) `AssetType` ignore carousel/collection — audit des formats Meta jamais couverts ; (b) croiser `InsightBreakdown` age_gender/région avec les tags hook/angle — signaler un segment à forte dépense sans AUCUNE créa dédiée. Un rapport « trous de couverture » actionnable. **Done =** rapport liste formats absents + segments non adressés sur fixtures. Files: `apps/adsengine/` (nouveau `coverage.py`), front reporting, tests. (ROUTINE) (@lane: backend/adsengine-creative) (@model: sonnet)
- [x] PUB81 — **ROI par lane de fabrique** : `cost_cents` est peuplé par chaque adaptateur et lu NULLE PART — coût-par-résultat par lane (zapcap/fal/templated/elevenlabs/json2video/chantier/ugc) : quelle filière de production rapporte. **Done =** table ROI par lane au reporting créatif. Files: `apps/adsengine/reporting.py`, front, tests. (ROUTINE) (@lane: backend/adsengine-creative) (@model: haiku)
- [x] PUB82 — **Rétention par scène de script** : relier les percentiles vidéo (p25/50/75/95) aux *beats* du script généré (`video_queue.build_grounded_script` — beats aujourd'hui éphémères, à persister sur l'asset) → « la chute d'audience arrive à la scène du prix », pas juste « à 50 % ». **Done =** ad vidéo générée → mapping beat↔percentile visible. Files: `apps/adsengine/{video_queue.py,models.py}`+migration, reporting, tests. (@after: PUB16) (ROUTINE) (@lane: backend/adsengine-creative) (@model: sonnet)
- [x] PUB83 — **Kit de marque + vignette** : `BrandKit` persistant (logo/couleurs/zones de sécurité/polices) consommé par le TemplatedAdapter au lieu d'un payload ad hoc, + `thumbnail_key` choisi (pas la frame 0 par défaut) vérifié à la checklist policy. **Done =** génération templated lit le kit ; vignette manquante → warning checklist. Files: `apps/adsengine/{models.py,creative_factory.py,policy.py}`+migration, front, tests. (ROUTINE) (@lane: backend/adsengine-creative) (@model: sonnet)
- [x] PUB84 — **Provenance durable par asset** : le rapport de `_check_variant_grounding` + policy_stamp existe à la génération puis se disperse — piste d'audit consultable par asset (fait cité → version FactTable → verdicts → approbation), en lecture sur la créathèque. **Done =** chaque asset généré montre sa chaîne de provenance. Files: `apps/adsengine/{generation_audit.py,serializers.py}`, front, tests. (@after: PUB16) (ROUTINE) (@lane: backend/adsengine-creative) (@model: sonnet)
- [x] PUB85 — **Variantes localisées par ville** : `FactEntry` est plat clé→valeur national — dimension région optionnelle (irradiation/tarifs locaux vérifiés) pour générer des variantes ville-spécifiques ancrées (« à Marrakech, X kWh/an »). Reste 100 % faits-vérifiés (règle checked-facts-only). **Done =** variante générée pour une ville cite le fait régional publié ; ville sans fait → variante nationale. Files: `apps/adsengine/{models.py,generation.py}`+migration, tests. (@after: PUB16) (ROUTINE) (@lane: backend/adsengine-creative) (@model: sonnet)

#### PUB-P6 — Science : confiance, observabilité, honnêteté statistique

- [x] PUB86 — **Registre de qualité des décisions (regret)** : personne ne répond à « l'IA aide-t-elle vraiment ? ». Comparer chaque décision loggée (`DecisionLog`/actions appliquées) au bras réellement meilleur a posteriori → regret réalisé cumulé (MAD laissés sur la table) par type de décision, en tuile Reporting. **Done =** regret calculé sur fixtures multi-semaines ; peu de données → intervalle honnête affiché. Files: `apps/adsengine/` (nouveau `decision_quality.py`), front, tests. (ROUTINE) (@lane: backend/adsengine-science) (@model: opus)
- [x] PUB87 — **Calculateur MDE/puissance opérateur** : `mde.py` (math testée) n'a jamais été montré à un humain — à la création d'expérience, afficher « avec votre volume, ~X jours pour détecter +20 % » interactif. Le gain le moins cher de tout le lot. **Done =** ExperimentsScreen affiche le calcul avant lancement. Files: `apps/adsengine/views.py` (vue mince sur mde.py), `frontend/.../ExperimentsScreen.jsx`, tests. (ROUTINE) (@lane: backend/adsengine-science) (@model: haiku)
- [x] PUB88 — **Livre de compte de l'exploration** : le plancher d'exploration (20 %) est de l'argent réel — agréger « MAD dépensés à explorer vs sur le gagnant confirmé » en ligne mensuelle au reporting : le coût d'apprentissage devient visible et pilotable. **Done =** ligne mensuelle exploration/exploitation exacte sur fixtures. Files: `apps/adsengine/reporting.py` (lecture allocation), front, tests. (ROUTINE) (@lane: backend/adsengine-science) (@model: haiku)
- [x] PUB89 — **Score qualité de la chaîne d'attribution** : un webhook mort biaise silencieusement la récompense proxy pendant des semaines — scorer par lead la complétude de jointure (clid présent ? téléphone matché ? stage à jour ? ad résolue ?) + tendance globale, alerte sous seuil. L'assurance qualité des données dont tout le reste dépend. **Done =** dégradation simulée → score chute + alerte. Files: `apps/adsengine/` (nouveau `data_quality.py`), tests. (ROUTINE) (@lane: backend/adsengine-science) (@model: sonnet)
- [x] PUB90 — **Feedback utile/faux-positif sur les alertes** : chaque fausse alarme érode la confiance — boutons utile/inutile sur les `AnomalyEvent`/alertes, précision par détecteur trackée, throttle auto d'un détecteur constamment inutile (brake-only, jamais de nouvelle alerte auto). **Done =** détecteur voté inutile 5× → cadence réduite + visible. Files: `apps/adsengine/{anomaly.py,models.py}`+migration additive, front, tests. (ROUTINE) (@lane: backend/adsengine-science) (@model: sonnet)
- [x] PUB91 — **Backtest de règle sur l'historique réel** : avant d'armer une règle, la rejouer sur les `ArmDailyStat`/snapshots réels de la société (« qu'aurait-elle fait sur votre dernier trimestre ? ») — bien plus convaincant que le simulateur synthétique existant, qui reste inchangé. **Done =** dry-run historique affiché avant armement (actions qu'elle AURAIT proposées, jamais exécutées). Files: `apps/adsengine/` (nouveau `rule_backtest.py`), front RulesScreen, tests. (@after: PUB23) (ROUTINE) (@lane: backend/adsengine-science) (@model: sonnet)
- [x] PUB92 — **Arrêt par perte espérée** : compléter `challenger_phase_complete` (P(best)≥0.80 ou cap 4 sem) par une règle d'arrêt à perte espérée (stop quand le coût attendu de se tromper < seuil MAD) — plus net sur données minces : stoppe plus tôt les victoires nettes, plus tard les vraies égalités. Fonction NOUVELLE à côté de l'existante testée (jamais la remplacer en douce). **Done =** golden tests des deux règles côte à côte ; l'existante byte-identique. Files: `apps/adsengine/allocation.py`, tests. (ROUTINE) (@lane: backend/adsengine-science) (@model: opus)
- [x] PUB93 — **Fenêtre glissante du bandit (non-stationnarité)** : les impressions d'il y a 6 semaines pèsent comme celles d'hier — la fatigue créative solaire se joue en semaines : variante à décote exponentielle (pure, à côté de l'existante) branchée derrière un flag, comparée en golden tests. **Done =** flag ON → poids récents dominants (test) ; OFF → byte-identique. Files: `apps/adsengine/bandit.py`, tests. (ROUTINE) (@lane: backend/adsengine-science) (@model: opus)
- [x] PUB94 — **Dérive des postérieurs + branches mortes** : snapshot hebdo du mouvement de chaque croyance — nœud figé au prior pour toujours (branche morte) ou qui oscille (bug de données amont) flaggé. Le filet qui attrape un moteur silencieusement cassé. **Done =** nœud immobile N semaines → flag « branche morte » sur L'Arbre. Files: `apps/adsengine/` (extension decay/observabilité), tests. (@after: PUB18) (ROUTINE) (@lane: backend/adsengine-science) (@model: sonnet)
- [x] PUB95 — **Détection de cannibalisation** : « ces pubs créent-elles des leads ou déplacent-elles l'organique ? » — comparaison de tendance leads organiques/parrainage avant/après changements de dépense (série temporelle simple, PAS un géo-test) avec intervalle honnête. **Done =** rapport FR sur fixtures ; données insuffisantes → le dit. Files: `apps/adsengine/` (extension incrementality/reporting), `apps/crm/selectors.py`, tests. (@after: PUB38) (ROUTINE) (@lane: backend/adsengine-science) (@model: sonnet)

#### PUB-P7 — Finance, gouvernance, résilience, intégration ERP (sortir la pub de son silo)

- [x] PUB96 — **La dépense pub entre en compta** : `InsightSnapshot.spend` n'atteint JAMAIS `apps/compta` — le premier coût d'acquisition est hors P&L. Écriture brouillon mensuelle (charge publicitaire par compte dédié) proposée via `compta.services` (même pattern que `assurances` — brouillon, jamais validée auto), rapprochable avec la réconciliation Meta. **Done =** clôture de mois sur fixtures → écriture brouillon correcte en compta ; jamais de double écriture. Files: `apps/adsengine/` (nouveau `compta_bridge.py`), `apps/compta/services.py` (fonction fine si besoin), tests. (ARCH) (@lane: backend/finance) (@model: opus)
- [x] PUB97 — **Surveillance du solde prépayé Meta** : Meta Maroc = prépayé — à zéro, la diffusion s'arrête et ça ressemble à « pas de données » (le guard zéro-délivrance exige spend>0 : angle mort exact). Lire balance/funding du compte via l'API, seuil d'alerte trésorerie (« solde < X jours de dépense courante ») + tuile ConnectionScreen/Dashboard. **Done =** solde bas sur fixtures → alerte + tuile ; API sans le champ → dégradation documentée. Files: `apps/adsengine/{meta_client.py,anomaly.py}`, front, tests. (ROUTINE) (@lane: backend/finance) (@model: sonnet)
- [x] PUB98 — **TVA auto-liquidation des factures Meta** : les factures Meta Ireland vers une société marocaine relèvent de l'auto-liquidation TVA (services importés) — aucun mécanisme ne les capte. Ingestion (upload manuel du PDF/CSV Meta) en facture fournisseur avec TVA auto-liquidée pré-calculée, rapprochée du spend synchronisé. **Done =** facture Meta uploadée → facture fournisseur brouillon correcte + écart vs spend signalé. Files: `apps/adsengine/` (extension compta_bridge), `apps/compta`/fournisseurs selon pattern existant, tests. (@after: PUB96) (ROUTINE) (@lane: backend/finance) (@model: sonnet)
- [x] PUB99 — **Enregistrer adsengine au registre plateforme (ARC28)** : pas de `platform.py` → invisible de la recherche globale, du KPI fédéré, du chatbot (ARC33 `agent_actions_module`), des customfields et du dataimport. Enregistrer : recherche (campagnes/ads/créas), KPIs fédérés (spend/leads/coût-par-signature vers `reporting`), et 2-3 `agent_actions` LECTURE d'abord (« combien a-t-on dépensé cette semaine ? », « top 3 des ads ») — les actions d'écriture via chatbot restent HORS scope (gated décision fondateur). **Done =** recherche globale trouve une campagne ; le dashboard central `reporting` montre les KPIs pub ; le chatbot répond aux questions lecture. Files: `apps/adsengine/platform.py` (nouveau — gabarit des 22 autres apps), `apps/adsengine/agent_actions.py`, tests. (ARCH) (@lane: backend/adsengine-platform) (@model: sonnet)
- [x] PUB100 — **Rétention/purge CNDP des miroirs** : `MetaLeadMirror`/`InsightBreakdown` grossissent sans fin ni purge, et l'effacement d'un lead CRM ne se propage pas au `phone_key` du miroir. Fenêtres de rétention configurables + beat de purge + propagation de l'effacement (événement domaine) + page docs registre de traitement (ad-leads + uploads CAPI hashés). **Done =** purge au-delà de la fenêtre (test) ; suppression d'un lead → miroir anonymisé ; docs commitées. Files: `apps/adsengine/{tasks.py,receivers.py}`, docs, tests. (ARCH) (@lane: backend/adsengine-platform) (@model: opus)
- [x] PUB101 — **Santé du compte lue, pas devinée** : rien ne lit `account_status`/`disable_reason` — un compte désactivé/en revue ressemble à une panne de données. Les lire au sync, `EngineAlert` dédiée par statut anormal + playbook FR (docs/engine/) « compte restreint : quoi faire, dans quel ordre ». **Done =** status ≠ actif sur fixtures → alerte typée + lien playbook. Files: `apps/adsengine/{meta_client.py,tasks.py}`, docs/engine/, tests. (ROUTINE) (@lane: backend/adsengine-platform) (@model: sonnet)
- [x] PUB102 — **Vigie de version Graph API** : `GRAPH_VERSION` épinglée à la main sans veille d'EOL (~2 ans) — le drift v19 qui a motivé le fichier peut se reproduire. Check périodique léger (header/changelog) + alerte « version à N mois de l'EOL », jamais de bump auto. **Done =** version proche EOL simulée → alerte. Files: `apps/adsengine/{api_version.py,tasks.py}`, tests. (ROUTINE) (@lane: backend/adsengine-platform) (@model: haiku)
- [x] PUB103 — **Quatre yeux optionnel sur l'approbation** : `approve_action` n'interdit pas proposeur==approbateur — dès qu'un media buyer est embauché, une seule personne peut proposer ET approuver une dépense. Flag `GuardrailConfig.require_four_eyes` (OFF par défaut — mode solo intact) : ON → `created_by ≠ approved_by` imposé serveur. **Done =** flag ON → auto-approbation refusée 403 (test) ; OFF → comportement actuel. Files: `apps/adsengine/{services.py,models.py}`+migration, tests. (AUTH) (@lane: backend/adsengine-platform) (@model: opus)
- [x] PUB104 — **Rollup/archivage des snapshots** : `InsightSnapshot`+`InsightBreakdown` quotidiens × ad × 4 dimensions sans stratégie — rollup mensuel au-delà de N mois (agrégats conservés, détail purgé/archivé), bornes de requête sur les Sum() de reporting. **Done =** rollup idempotent (test) ; totaux identiques avant/après ; reporting inchangé. Files: `apps/adsengine/{tasks.py,models.py}`+migration, tests. (ROUTINE) (@lane: backend/adsengine-platform) (@model: sonnet)
- [x] PUB105 — **Rejeu webhook/backfill après panne** : la réconciliation FLAGGE « webhook non reçu » mais rien ne répare — commande/action de backfill ciblée (leads via pull-sync existant, CTWA via re-fetch si possible, insights via insights_backfill) déclenchable depuis l'alerte de divergence. **Done =** divergence détectée → bouton « rattraper » exécute le bon backfill ; idempotent. Files: `apps/adsengine/{tasks.py,views.py}`, front, tests. (ROUTINE) (@lane: backend/adsengine-platform) (@model: sonnet)
- [x] PUB106 — **Chat NL « interroge ton compte pub »** : brancher l'agent SQL FastAPI existant (LangChain, key-gated) sur les tables adsengine en LECTURE SEULE (vues dédiées company-scopées) — « combien m'a coûté une signature en mai ? » en français. Aucune écriture, jamais d'action — questions seulement ; sans clé → indisponible proprement. **Done =** 5 questions dorées répondent juste sur fixtures ; tentative d'écriture → refus ; test d'isolation multi-tenant : les lignes d'une autre company invisibles via l'agent. Files: `backend/fastapi_ia/` (registre de tables), `apps/adsengine/` (vues SQL), tests. (ROUTINE) (@lane: backend/adsengine-platform) (@model: sonnet)

### GATED — Groupe PUB (ne PAS auto-construire — chaque item attend sa porte fondateur)

- [ ] PUB107 — **[GATED: décision WhatsApp Cloud API (même porte qu'ADSENG34)] Boîte de réception WhatsApp d'équipe** : conversations CTWA assignables, notes internes, SLA par conversation, funnel conversation→qualifié→devis→signature — le standard Wati/Trengo. Ne se construit qu'à la levée de la porte Cloud API. Files: `apps/adsengine/`+front. (@blocked: décision fondateur WhatsApp Cloud API) (DEP) (@model: opus)
- [ ] PUB108 — **[GATED: décision WhatsApp Cloud API] Réponse instantanée + qualification WhatsApp Flows** : auto-réponse <1 min sur lead Meta/CTWA (gabarits approuvés), formulaire Flows structuré (type toiture/facture/ville) alimentant le Lead et un brouillon de Devis. (@blocked: décision fondateur WhatsApp Cloud API) (DEP) (@model: opus)
- [ ] PUB109 — **[GATED: décision WhatsApp Cloud API] Relances drip marketing WhatsApp** : cadences 1h/1j/3j pour FOLLOW_UP/COLD et devis expirés (opt-out géré, fenêtres de coût 2026 respectées) — distinct des relances transactionnelles existantes. (@blocked: décision fondateur WhatsApp Cloud API) (DEP) (@model: sonnet)
- [ ] PUB110 — **[GATED: clé LLM + revue anti-hallucination (même porte que le commentaire LLM des briefs)] Stratège conversationnel sur données pub** : chat « pourquoi cette ad gagne ? que tester ensuite ? » au-dessus des métriques internes — réponses citant les chiffres réels uniquement (pattern FactTable). (@blocked: clé LLM + revue anti-hallucination fondateur) (DEP) (@model: opus)
- [ ] PUB111 — **[GATED: budget fondateur — dépendance payante] Tier vidéo AI-UGC (Arcads/Creatify-style)** : adaptateur `creative_factory` supplémentaire pour avatars parlants + speech-to-speech (voix réelle Darija du fondateur sur acteur IA — aucun outil n'a de Darija natif) ; nés en backlog, jamais publiés sans approbation. (@blocked: budget fondateur dépendance payante) (DEP) (@model: sonnet)
- [ ] PUB112 — **[GATED: décision fondateur — touche le cœur décisionnel] Bandit « toujours actif » au niveau adset** : étendre la logique Thompson hors des expériences déclarées pour réallouer en continu le budget entre adsets vivants (propose-only au début). À n'ouvrir qu'après PUB15/PUB18 en production et un historique de regret (PUB86) propre. (@after: PUB15, PUB18, PUB86) (@blocked: décision fondateur cœur décisionnel) (DECISION) (@model: opus)
- [ ] PUB113 — **[GATED: vertical SK Paysages — décision produit fondateur] Généraliser le moteur multi-vertical** : FactTable/seeds/mots-clés de classification/saisonnalité par tenant-vertical (paysagisme ≠ solaire) — le mémo marketing exige SK Paysages d'abord or tout est câblé solaire. Cadrage L, à ne lancer que sur décision explicite. (@blocked: décision produit fondateur SK Paysages) (DECISION) (@model: opus)
- [ ] PUB114 — **[GATED: numéro dédié + coût télécom] Suivi d'appels par annonce + rappel SMS d'appel manqué** : numéros de suivi par source, missed-call-textback — une partie des leads marocains arrive encore par téléphone. Dépendance opérateur/API télécom payante à choisir avec le fondateur. (@blocked: dépendance télécom payante fondateur) (DEP) (@model: sonnet)

### DONE LOG — Groupe PUB

- 2026-07-19 — **Batch 2 (53 tâches, 6 lanes worktree, 1 merge).** P4 croissance : audiences devis-vu/jamais-ouvert + devis expiré + cross-sell base installée + lookalike signatures (PUB58-61, premier appelant production de la sync d'audiences ADSDEEP57/58, porte consentement respectée), heatmap villes 3 métriques (PUB62), calculateur recyclage COLD (PUB64), parrainage→graine (PUB65), halo géo installations (PUB66), saisonnalité historique réelle (PUB67), SLA première réponse + temps par annonce (PUB68), carte de partage client trackable (PUB69). P5 créatif : registre de consentement CNDP bloquant (PUB75), pipeline témoignage→brief (PUB63), fraîcheur/expiration des assets (PUB76), langue fr/ar-ma (PUB77), calendrier marocain seedé (PUB78), BrandKit + vignette (PUB83), veille concurrentielle périmètre honnête SANS scraping (PUB70), FactEntry régional (PUB85), photos chantier→créathèque (PUB73), gabarits de proposition (PUB50), chatter d'ad (PUB55 — ⚠ calqué LeadActivity, grandfathered ARC8 « À ARBITRER » : converger sur records.Activity ou ratifier), beats de script persistés + rétention par scène (PUB82), DaypartingGrid monté (PUB4), mines commentaires/objections (PUB71/72), fatigue visuelle (PUB74), déclencheur météo (PUB79), couverture formats/segments (PUB80), ROI par lane (PUB81), provenance (PUB84). P6 science : regret (PUB86), calculateur MDE (PUB87), livre d'exploration (PUB88), qualité de chaîne d'attribution + beat (PUB89), feedback d'alertes + throttle (PUB90), backtest de règle historique (PUB91), arrêt perte-espérée (PUB92), bandit à décote (PUB93) — fonctions décisionnelles existantes byte-identiques, dérive des postérieurs (PUB94), cannibalisation (PUB95). P7 finance/plateforme : dépense→écriture compta brouillon + TVA auto-liquidation (PUB96/98), solde prépayé surveillé (PUB97), platform.py ARC28 + agent_actions lecture (PUB99), purge CNDP + lead_erased (PUB100), santé du compte lue (PUB101), vigie EOL Graph (PUB102), quatre-yeux optionnel (PUB103), rollup mensuel (PUB104), rattrapage post-panne (PUB105), chat NL lecture seule (PUB106). PUB53 badges Lead/Devis→annonce. Migrations additives adsengine 0039-0051 (chaîne linéaire, tête unique). 3 pièges de dédup git (accolades/return volés entre fonctions adjacentes) attrapés aux folds. Restent : PUB107-114 (GATED fondateur).
- 2026-07-19 — **Batch 1 (54 tâches, 7 lanes worktree parallèles, 1 merge).** P0 câblage : routes signaux/ + cohorte (PUB1), actions file-voi/tests/leads de L'Arbre (PUB2), BreakdownsPanel/EngagementAudiencePicker montés (PUB3/5), écran Table des faits (PUB6), fix result_detail→error (PUB7), métriques vidéo complètes + courbe de rétention (PUB8), éditeur garde-fous complet (PUB9), parité permissions UI (PUB10), cartes de croyance FR (PUB11), endpoints orphelins statués + CSV serveur (PUB12), panneau Apprentissage Meta (PUB13), e2e 10 écrans (PUB14), garde de contrat front↔back auto (PUB115, 93 routes vérifiées). P1 cerveau : rewards câblé en beat hebdo (PUB15), pipeline génération ancrée exposé (PUB16), VoI réellement branché flag-gated (PUB17), écrivain d'évidence α/β + action « conclure » (PUB18), beat réconciliation quotidienne (PUB19), mort du token → alerte + expiry (PUB20), kill-switch persisté en base (PUB21), composeurs manuels tous kinds réels (PUB22), armement des règles à l'écran (PUB23), None-protection upsert (PUB24), inventaire modules morts (PUB25), fenêtres d'attribution 2026 re-validées + 1d_ev (PUB39). P2 boucle : HMAC Lead Ads (PUB26), auto-création Lead CTWA (PUB27), taxonomie junk + taux par ad (PUB28), wiring-health complet + boucles en attente (PUB29), événement CAPI visite effectuée (PUB30), valeur devis sur QUOTE_SENT flag-gated (PUB31), sync quality rankings + garde câblée (PUB32), vigie vélocité d'apprentissage (PUB33), santé structurelle Andromeda (PUB34), colonnes attribution incrémentale (PUB35), entonnoir par variante (PUB36), no-show par variante (PUB37), harnais geo-holdout (PUB38). P3 console : sélecteur de période + comparaison (PUB40), fraîcheur/panne visibles + polling (PUB41), file « Aujourd'hui » (PUB42), vues enregistrées cockpit (PUB43), fiche ad « histoire complète » (PUB44), annuler = proposer l'inverse (PUB45), assistant de connexion guidé (PUB46), exports print/PDF + CSV serveur (PUB47), centre de notifications via notify (PUB48), annotations de courbes (PUB49), raccourcis + palette Ctrl-K (PUB51), comparateur (PUB52), aide contextuelle FR (PUB54), tables responsives mobiles (PUB56), digest actionnable + tuile score audit (PUB57). Migrations additives : adsengine 0034-0038, crm 0065-0066. Sécurité vérifiée au fold : aucune voie d'unpause (règle #3), Odoo lecture seule, frontière selectors, tenancy sur chaque nouveau viewset. Fold : conflits résolus par union des deux côtés + vite build + garde 93/93 à chaque étape ; 1 import useEffect silencieusement perdu par l'auto-merge récupéré. Restent pour le batch 2 : PUB4/50/53/55 (dépendances inter-lanes) + PUB58-106.

---

### Group QJ — Quote-journey best-in-world (ERP backend + frontend; research-driven, 2026-06-24)

*From a June-2026 deep audit of TAQINOR's quote journey (website pin+bill capture → CRM lead →
seller designs the roof in 3D → premium quote → tokenized web proposal + e-sign) against the best
solar platforms in the world (Aurora, OpenSolar, Solargraf, Pylon, Tesla, Otovo, Demand IQ, Solo,
EnergySage, Bodhi) + Morocco market + conversion-science research. These are the **ERP half**; the
matching website tasks are **WJ1–WJ24 in `docs/WEB_PLAN.md`** (cross-referenced per task). Goal: make
the journey the best in the world for the CLIENT and the COMMERCIAL user.*

> **Constraints (every QJ task).** Rule #4 status preservation (the quote engine only RENDERS; the
> document chain `brouillon→envoye→accepte…` + BonCommande/Facture preserved 1:1; `/proposal` stays
> the only client PDF path). STAGES.py keys imported, never hardcoded. All migrations
> additive/nullable + company-scoped server-side (never trust `company` from the body). Cross-app
> reads/writes go through `selectors.py`/`services.py` + the `core/events.py` bus — never another
> app's models/views. **Savings stay self-consumption-first (loi 82-21): value only self-consumed
> kWh; the surplus-injection line stays OFF until the founder confirms ANRE's BT residential
> net-billing tariff (unpublished).** A simple typed-name e-signature is legally valid in Morocco
> (loi 53-05/43-20) — harden the evidence, no certified provider required for ordinary sales.

> **Three gated items need a founder-provisioned account/credential (→ NEEDS YOUR INPUT, build the
> rest):** QJ23 (WhatsApp Business API / BSP), QJ24 (CMI/PayZone payment merchant), QJ25 (paid
> imagery provider or self-built roof segmentation). The Meta CAPI *send* in QJ9 stays gated on
> Reda's Meta token (everything up to the send is buildable).

**A — Speed-to-lead, follow-up & engagement tracking (the highest-ROI cluster):**

**B — E-signature strength & proposal data:**

**C — Commercial-user efficiency:**

**D — Gated (need a founder-provisioned account/decision → NEEDS YOUR INPUT; build behind a flag):**

**E — Client 3D proposal, superior notifications & multi-property quotes (founder request 2026-07-01):**

*From Reda: (1) when the client opens the returned quote he must see HIS OWN HOME in interactive 3D with the panels (zoom/rotate) — the web viewer is WEB_PLAN WJ25–WJ28, this QJ26 is the backend unlock; (2) when the client asks to be contacted, the lead's HANDLER and the handler's SUPERIOR must both be notified; (3) a « contacter mon supérieur » button on quote generation notifies the creator's superior; (4) support multi-villa quotes — multiply one villa ×N (identical) OR add different villas one by one, all in ONE quote document. Research confirmed the pieces exist: `CustomUser.supervisor` self-FK (added 2026-06-18), `Lead.owner` (handler), `Devis.created_by` (creator), the `notify()` service + extensible EventType (QJ2), and the `roof_layout` JSON already stored on the Devis — the public proposal payload just doesn't expose it, and no server-side contact-request endpoint exists yet.*


#### DONE LOG — QX ROUND 7 (4 modèles de devis) (2026-07-16)

Groupe QX43-52 drainé (lane quote-engine, un seul merge). **QX43** mode `commercial` de bout en bout (`Devis.ModeInstallation` +COMMERCIAL, migration additive 0087 sur Devis ET DevisPreset, builder + DevisGenerator 4 modes). **QX44** étude commerciale par catégorie (10 catégories, table archétypes day-share sourcée). **QX45** renderer industriel dédié (3 pages CFO, câblé AVANT le legacy — règle #4 préservée, renderers grandfathered ARC11/SCA29 comme residential/agricole). **QX46** renderer commercial catégorie-aware. **QX47** devis agricole enrichi (graphe ETc mensuel vs eau livrée + bassin recommandé). **QX48** moteur agronomique v2 FAO-56 (~20 cultures sourcées, séries mensuelles, miroir front/back byte-identique). **QX49** payload proposition mode-complet (whitelist stricte, jamais prix_achat/marge). **QX50** ligne injection 82-21 (`constants_82_21.py` sourcé + miroir solar.js, OFF par défaut, plafond 20% net frais réseau, mention obligatoire). **QX51** webhook questionnaire commercial/industriel v2. **QX52** parité instType/type_installation 4 modes. Toutes les constantes tarifaires/Kc estimées portent « à vérifier fondateur » (QXG6 les durcira). QXG1-6 restent GATED (comptes/données/vérifs fondateur).

#### DONE LOG — PLAN2 VX vérification + 2 build (2026-07-13)

Drain PLAN2 (lanes frontend/crm, frontend/brand, backend/auth). Vérifié en repo réel (pas la case) : **déjà présents** (commits déjà sur origin/main, cases périmées) → `[x]` : VX193, VX219, VX220, VX223, VX224, VX248, VX249, VX250 (lane crm-a) ; VX146, VX147, VX237, VX239 (lane crm-b) ; XPLT21 (voip, dans PLAN.md). **Construits cette passe** : VX150 (login re-signé — le wordmark passe à la police de marque `var(--font-display)`, delta sur VX34 déjà mergé ; `96b14a46`) ; VX243 (confiance au niveau du DOSSIER — `archived_by_nom` rendu dans ListView, endpoint historique record-scopé `objets/<ct>/<id>/history/` visible par le propriétaire via ContentType générique sans import de modèle métier, hook `useStaleGuard` sur LeadForm/DevisForm/FactureForm ; tests `apps/audit/tests_vx243_record_history.py` + `useStaleGuard.test.jsx` ; `d4c5a99c`). Les tâches @blocked du groupe compta/argent (XACC12/XPOS19/YCASH5 money-GL + décision fondateur, XSAL5/XSAL14 quote_engine RÈGLE #4, ODX14/15/18/20/22 app-split state-only à valider en DB, ODX15 doublon NoteFrais/NoteDeFrais à trancher) restent `[ ]` — respect des tags @blocked. QXG1-5 restent GATED (compte/données/contenu/ops fondateur).

#### DONE LOG — backend/auth lane vérification (2026-07-12)

Lane backend/auth (VX200/VX201/VX202/VX235/VX241) : les 5 tâches étaient DÉJÀ construites et mergées dans HEAD (commits 6202941f, 1a685a56, e80034c6, b26951c2, b4867158 — tous ancêtres de HEAD). Vérifié en repo réel : VX200 CSP par-environnement via `security-headers.conf.template` inclus par nginx ; VX201 `devTools: import.meta.env.DEV`, `lib/trustedSvg.js`, `frontend/scripts/check_no_danger.mjs` câblé au lint ; VX202 `components/NoIndex.jsx` + zone nginx `public_token_limit` ; VX235 garde de cycle superviseur (borne 20 sauts) dans `authentication/serializers.py` ; VX241 `TRACKED_MODELS` avec `('kb','KbArticle')`+`('gestion_projet','Timesheet')` et `UsageGuardedDestroyMixin` (`apps/core/destroy_mixins.py`). Ticks `[x] (already present)` uniquement, aucun code touché. AUTH : garde d'intégrité VX235 + audit VX241 déjà en place.

#### DONE LOG — Lane frontend/ios (VXD-C iOS/perf/a11y forensique) (2026-07-12)

21 tâches VXD-C (VX172-198/225-226) draînées en une lane worktree isolée. **Déjà présentes** (vérifiées contre la source réelle, wave-3) : VX172 (export blob geste iOS), VX173 (VoiceRecorder mimeType négocié), VX174 (sanitize + DatePicker bornée), VX175 (touch-action/scroll-x-touch/dvh/ellipsis sidebar), VX176 (safe-top Sheet/Dialog/AlertDialog), VX177 (ExternalLink), VX179 (SW StaleWhileRevalidate), VX181 (ThemeToggle hidden md:flex + menu utilisateur), VX185 (imports directs Header + check_bundle_budget étendu), VX186 (LeadsPage/CartePage/ParcInstallePage MapView lazy), VX187 (useDeferredValue + memo LeadCard/ListRow), VX189 (chunk icons + Sidebar useMemo + content-visibility + devPerfWarn), VX194 (--primary-text + IconButton 24×24 + contrast.test), VX197 (RouteFocus monté dans Layout), VX226 (priorité + refresh MaJourneePage). **Construites cette lane** : VX178 (backdrop-blur retiré du thead/tfoot sticky DataTable + BulkActionBar, fond `bg-muted`/`bg-popover` opaque) ; VX180 (variante Tailwind dédiée `dt-desktop:` = 768px réservée au DataTable, `DataTable.test.jsx` corrigé + nouveau `e2e/datatable-breakpoint.spec.js` à 700/1024px réels) ; VX190 (3 assertions WebKit ajoutées à `mobile.spec.js`, déjà couvert par le projet `mobile-safari` de VX68 : export geste, thead/tfoot lisibles au scroll, Sheet standalone `safe-top`) ; VX191 (hook `hooks/useActiveDescendant.js` + adoption dans `ProduitPicker`/`BcfProduitPicker`/`GlobalSearch`/`MentionAutocomplete`+`SlashCommandPicker` via `Composer` — `ToitureDesign`/`ShareRecord` restent hors scope de cette passe : DOM impératif non-React pour le premier, aucune nav clavier existante à batir pour le second) ; VX225 (`InterventionsPage` `DetailSheet.setStatut` lit enfin `err.response.data.statut` et rend la liste inline sous le Select, patron `ChantierGateTimeline`). **BLOQUÉE** : VX198 (garde ESLint jsx-a11y) — nécessite le nouveau dev-dep `eslint-plugin-jsx-a11y`, impossible à `npm install` dans ce worktree sans `node_modules` ; la tâche se marque elle-même `[GATED si dev-dep à ajouter]`.
#### DONE LOG — Vague 3 lane frontend/data (2026-07-12)

- 2026-07-12 — VX117 **(already present)** : `lib/resilientMutation.js` déjà extrait et consommé par `DevisForm.jsx`/`FactureForm.jsx`/`PaieRunWizard.jsx`/`RolesManagement.jsx` (allSettled + rapport nominatif, allOk gate) ; `DevisGenerator.jsx` a depuis migré vers les endpoints ATOMIQUES `createDevisAtomic`/`replaceLignesDevis` (QX21), qui suppriment le pattern « parent + N lignes en Promise.all » visé par cette tâche.
- 2026-07-12 — VX161 **(already present)** : `api/refreshCoordinator.js` déjà construit et consommé par `axios.js` ET `iaApi.js` (promesse de refresh UNIQUE partagée, reset en `finally`).
- 2026-07-12 — VX162 **(already present)** : `providers/session-bridge.js` a déjà `BroadcastChannel('taqinor-session')` + `broadcastLogout()`/`subscribeToSessionLogout()`, câblé depuis `authSlice.logoutUser.fulfilled` et consommé par `SessionProvider.jsx`.
- 2026-07-12 — VX164 **(already present)** : les 3 volets sont déjà construits — (a) `messagingSlice.js` a `activeMessagesRequestId` (garde de séquence sur `fetchMessages.fulfilled`) ; (b) `crmSlice.js`/`ventesSlice.js`/`stockSlice.js` ont chacun `seqMap[id]`/`isStaleResourceUpdate` sur leurs réducteurs `update*/patch*.fulfilled` ; (c) `InlineEdit.jsx` a `committingRef` vérifié en tête de `commit()`.
- 2026-07-12 — VX165 **(already present)** : `ventesSlice.js`/`crmSlice.js`/`stockSlice.js` ont déjà `pendingCount` incrémenté/décrémenté par `pending`/settled sur chaque fetch, `loading = pendingCount > 0`.
- 2026-07-12 — VX203 **[BLOCKED: partiel]** : `lib/apiError.js` (b) et la délégation `toast.js→apiError.js` étaient déjà construites (vagues précédentes). Fait cette session : (c) `api/iaApi.js` aligné sur le contrat (a) d'`axios.js` — toute erreur ≠401 hors annulation/`suppressErrorToast` surface désormais un toast FR via `getApiError` (un 403 du catalogue d'actions agentiques n'est plus muet). PAS FAIT (hors budget d'une session sans `eslint`/`vitest`/`vite build` disponibles dans ce worktree) : le scan réel des pages fautives donne ~104 fichiers (catch + `toastError`/`toast.error` direct), très au-delà des « ~35 » du texte — un codemod à l'aveugle sur ce volume, sans aucun moyen de vérifier une régression de build, est un risque disproportionné ; `scripts/check_double_toast.mjs` non créé pour la même raison (il casserait frontend-lint immédiatement tant que les ~104 fichiers ne sont pas corrigés). Laissé en BLOCKED pour une session avec outillage complet (build/lint) qui peut vérifier le codemod page par page.
- 2026-07-12 — VX205 **(already present)** : `ErrorBoundary` déjà déployée autour de chaque `TabsContent`/onglet indépendant de `LeadForm.jsx`, `Dashboard.jsx` (+ cockpit), `CommercialDashboard.jsx` et `InterventionCapturePanels.jsx` (commentaires `VX205` déjà présents sur les 4 fichiers).
- 2026-07-12 — VX163 : nouveau `lib/thunkHelpers.js` (`createCancellableThunk` — normalise l'annulation axios en vraie `AbortError` pour que RTK marque `meta.aborted===true` ; `dedupeInFlight` — `Map<clé,Promise>` in-vol). Appliqué aux 4 thunks visés : `fetchProduits` (stockSlice), `fetchDevis`/`fetchFactures` (ventesSlice), `fetchLeads` (crmSlice, clé incluant les params). `stockApi.getProduits`/`ventesApi.getFactures` acceptent désormais un `config` (signal).
- 2026-07-12 — VX206 : `console.error('[ErrorBoundary]', …)` ajouté dans `ui/ErrorBoundary.jsx.componentDidCatch` ; `componentDidCatch` (absent) ajouté à `RouteErrorBoundary.jsx` avec `console.error` + `captureException` + identifiant support (`eventId` VX72 si DSN actif, sinon horodatage court `shortTimestamp()`) affiché sur l'écran de récupération ; nouveau `lib/globalErrors.js` (`installGlobalErrors` — `unhandledrejection` + `error` canalisés vers `captureException`-ou-no-op + `toastError` générique), câblé dans `main.jsx`.
- 2026-07-12 — VX244 : nouvelle primitive `ui/ConfirmDialog.jsx` (`severity` low/medium/high, saisie tapée obligatoire en `high`, Escape annule toujours, Entrée ne confirme jamais un `high` — pas de `<form>`, bouton désactivé tant que la saisie ne correspond pas) + `ui/BulkDestructiveConfirm.jsx` (extrait du patron `ForceDeleteModal`, saisie du COMPTE). Migré (vérifié : aucune duplication de primitive existante — `ui/confirm.jsx`/`ConfirmProvider` n'ont ni sévérité ni saisie tapée) : litiges (`LitigesPage.jsx`, dossier légal), webhook/clé API (`ApiWebhooksSection.jsx` — 4 actions : révoquer/supprimer clé, régénérer/supprimer webhook), KB-avec-enfants (`KbPage.jsx`, VX241 — `high` seulement si `nbDescendants>0`), modèle de checklist chantier (`ChecklistSection.jsx`), consigne de sécurité terrain (`SecuriteTerrainSection.jsx`), et bulk leads (`BulkActionBar.jsx`, `BulkDestructiveConfirm` avec le compte tapé). Non fait : tests (aucun `vitest` disponible dans ce worktree pour les écrire/vérifier) et les ~4 sites additionnels non nommés explicitement par la tâche (~68 `window.confirm` totaux dans 44 fichiers — la tâche interdit explicitement de tous les migrer d'un coup).
#### DONE LOG — Vague 3, lane frontend/ventes (2026-07-12)

VX138 (aperçu simulation → comparateur Sans/Avec 2 colonnes nommées + liseré de recommandation, tabular-nums sur `.gen-kwp`, 3 paliers visuels sur la chaîne de totaux, bandeau `.gen-actions-sticky` sticky au scroll à tous les paliers avec TTC condensé, accordéon « Plusieurs propriétés ? » replié par défaut en agricole).

VX141 (nouveau `ui/DocumentStageTrack.jsx` — piste horizontale brouillon→envoyé→accepté→BC→facturé→chantier posée dans la cellule Statut de DevisList à côté du StatusPill ; BC annulé après acceptation → puce BC rouge ; couche STATUTS DOCUMENT uniquement, aucune clé STAGES.py importée).

VX238 (`ui/Segmented.jsx` roving tabindex + ArrowLeft/Right/Home/End sur le radiogroup ; `ui/Combobox.jsx` Tab sans preventDefault sélectionne l'option sous le curseur ; `components/ProduitPicker.jsx` idem + nouveau prop `onPicked` posé sur `DevisLineRow.jsx`/`DevisForm.jsx`/`FactureForm.jsx` pour avancer le focus sur la Qté de la même ligne via `data-line-key`/`data-role="line-qty"` au lieu de rendre le focus au bouton déclencheur).

VX240 (autofocus posé sur DevisForm/FactureForm — champ Client — ProduitForm — Nom — et le dialog de création rapide de ticket SAV — Type ; mémoire localStorage ajoutée pour le type de ticket SAV rapide (TicketsPage.jsx) et le canal LeadExpressModal (payMode/pay-montant déjà couverts par VX92/93/249, hors scope du DoD) ; AttachmentsPanel.jsx upload multi-fichiers séquentiel avec indicateur « i/N », échec partiel n'annule pas les autres ; BonsCommandeFournisseur.jsx réplique le patron VX90 data-line-key/pendingFocusKey pour focaliser la ligne ajoutée.
#### DONE LOG — Vague 3, lane frontend/motion (VX133-136) (2026-07-12)

VX133 — Sheet glisse par bord réel (keyframes `slide-in/out-{right,left,top,bottom}` mappés
`--motion-*`, tokens.css) au lieu du `pop-in` centré-zoomé ; `.ldp-panel`/`.ldp-overlay` bespoke
retirés d'index.css, LeadDevisPanel + InstallationDetail (aperçu doc) migrés sur
`Sheet`/`SheetContent side="right"` ; AccordionContent anime sa hauteur
(`--radix-accordion-content-height`) ; TabsContent fondu court `--motion-fast` à l'affichage ;
BulkActionBar reste monté pendant `slide-out-bottom` (exit-sans-lib) au lieu du cut sec
`if (!count) return null`. `overlay-stacking.test.mjs` mis à jour (le test `.ldp-overlay` en CSS
n'a plus d'objet, l'overlay Sheet/Radix est déjà couvert par le test `fixed inset-0`).

VX134 — Palette ⌘K : `DialogContent` gagne une variante `variant="command"` (ancrée
`top-[12vh]`, keyframes dédiés `command-in`/`command-out` `--motion-fast` dont l'état
final inclut le recentrage horizontal — le `pop-in` générique écrasait le `transform:
translate(-50%,0)` de `.cmdk-content` via son `to { transform: none }`). Liseré actif de
la sidebar : fondu `--motion-fast` à l'apparition du pseudo-élément (mesure DOM pour un
indicateur partagé jugée invasive, repli fondu). Route post-Suspense : `<div
key={pathname} className="route-fade">` rejoue un fondu à chaque navigation. ChatBell :
badge pulse (`--animate-badge-pulse`) uniquement quand le total AUGMENTE (`prevTotalRef`),
jamais à la baisse ni sur poll inchangé ; 3 tests ajoutés. Thème : nouvelle
`applyThemeWithTransition` (design/theme.js) pose une classe transitoire `.theme-
transitioning` (≤200ms sur color/background-color/border-color/fill/stroke, index.css),
retirée après coup — `applyTheme()`/`initTheme()` restent instantanés (pas de FOUC) ;
`setStoredTheme` + le handler système de ThemeProvider l'utilisent. Test DOM fake dans
theme.test.mjs vérifie la classe posée puis retirée.

VX135 — nouveau hook `hooks/usePrefersReducedMotion.js` (matchMedia + listener live) : le
tilt `rotate(2deg) scale(1.02)` du kanban (transform STATIQUE, échappe structurellement au
garde CSS global) est désactivé via une classe `kb-drag-overlay--flat` dans les 3 kanbans
(CRM leads, installations, Tâches) ; `dropAnimation` dnd-kit alignée aux tokens
(`{duration:180, easing:cubic-bezier(0.23,1,0.32,1)}`, `{duration:1}` sous reduced-motion)
sur les 3. `transition: transform 120ms var(--ease-out)` ajoutée sur `.kb-drag-overlay
.kb-card` (transition de grab). Spinner : `motion-safe:animate-spin` (repli statique
lisible, l'anneau partiel reste immobile au lieu de figer à un angle arbitraire). DataTable :
FLIP minimal zéro dépendance (`useRowFlip`, `getBoundingClientRect` avant/après via
`useLayoutEffect`, plafonné à 200 lignes, désactivé sous reduced-motion, jamais en mode
`renderRow` custom) — trier/filtrer fait glisser les lignes vers leur nouvelle position au
lieu de téléporter.

VX136 — `.reveal-on-scroll` (index.css, `@supports (animation-timeline: view())`) sur les
cartes KPI de `ModuleDashboard` : translateY 8px→0 + fondu au fil du scroll, repli état
final statique (opacity:1) sur Firefox/Safari<18 — la règle n'est simplement jamais
appliquée. Nouveau `ui/ScrollProgress.jsx` (barre 2px, `scroll(nearest)`) posé en tête de
`.modal-body` (LeadForm) et de la page (DevisGenerator, marche aussi `embedded` dans
LeadDevisPanel — suit le conteneur qui défile réellement dans les deux cas). Les deux
désactivent explicitement leur timeline sous `prefers-reduced-motion: reduce`.
#### DONE LOG — Vague 3 (frontend/brand lane) (2026-07-12)

- VX125 — already present: `docs/design-density-budget.md` (plafond 3 signaux ambiants, jamais 2 redisant le même chiffre, critère de retrait `<BetaBadge>`) already existed and is already referenced from `docs/CODEMAP.md §4` and commented in `design/tokens.css:13-17` — checkbox had simply never been ticked.
- VX151 — already present: `peConstants.js` already carries `group`/`SETTINGS_GROUPS`/`saveModelForTab`/`SAVE_MODEL_HINTS`, and `ParametresEntreprise.jsx` already renders `<SettingsSidebar groups={tabGroups}>` (2-level nav) + the per-tab save-model hint before edition — checkbox had never been ticked.
- VX153 — already present: `features/ged/module.config.jsx` already renames "GESTION DOCUMENTAIRE" → "DOCUMENTS - AVANCE", `GedNavigator.jsx`/`GedSearch.jsx` have zero `text-[1x px]` arbitrary sizes left, and `pages/ia/AgentActions.jsx` already groups the historique tab by Aujourd'hui/Hier/date (with `AgentActions.historique.test.jsx` green) — checkbox had never been ticked.
- VX154 — already present: `ui/TaqinorMark.jsx` + `ui/SolarLoader.jsx` already exist and are already wired into `Header.jsx` (replacing the generic `<Zap>`) and `RouteFallback.jsx`, with the `sun-rise` keyframe + its `prefers-reduced-motion` freeze rule already in `index.css` — checkbox had never been ticked.
- VX158 — part (a) (style "suggéré" pointillé sur les 4 champs VX93 : owner/ville `LeadForm.jsx`, TVA `ProduitForm.jsx`/`DevisGenerator.jsx`/`DevisLineRow.jsx`, payMode `PaiementDialog.jsx`) was already fully built by VX249(b) in a prior wave — verified, no changes needed there. Built part (b): `features/compta/pages/FiscalitePage.jsx` `EXPORTS` now carries a `help` phrase per export (FEC/liasse/export fiduciaire/relevé TVA/honoraires/aide IS), rendered as a static grey caption under each button, zero logic, visible without a click. New `FiscalitePage.vx158.test.mjs`.
- VX159 — already present: `ui/RelationCounters.jsx` already exists and is already posed at the top of all 4 fiches (`ClientDetailPanel.jsx`, `FournisseurFiche360.jsx`, `ProduitDetail.jsx`, `LeadForm.jsx`), with `RelationCounters.test.jsx` + `RelationCountersMountPoints.test.mjs` green — checkbox had never been ticked.
- VX233 — already present: `apps/parametres/views_audit.py` already lists `'tarification'` in `KNOWN_AUDIT_SECTIONS`, `parametresApi.getAuditSections()` already exists, `SettingsAuditFeed.jsx` already exists as a paramétrable component consumed by both `AvanceSection.jsx` (dynamic `<Select>`) and `TarificationSection.jsx` ("Voir l'historique" → `section="tarification"`) — checkbox had never been ticked.
- VX155 — enrichit le Done= de VX40 : nouveau `ui/DealSignedCelebration.jsx` (carte de victoire — montant TTC + kWc réels, « ≈ X t CO₂ évitées/an » dérivée sur les mêmes hypothèses que le rapport de production estimée, TaqinorMark qui s'illumine ; sous reduced-motion, même carte sans mouvement) câblé sur les 2 chemins d'acceptation (`SigneDialog.jsx`, `DevisList.jsx` acceptation inline) à la place du toast plat + `celebrateDealSigned()` direct. Nouveau `toastMilestone` (`lib/toast.js`) — icône dédiée + description réf/client/montant — posé sur devis envoyé (`DevisList.jsx`) et facture payée (`PaiementDialog.jsx`, seulement quand le résiduel retombe à 0, jamais sur un règlement partiel). Tests : `DealSignedCelebration.test.jsx` (montant/kWc réels, reduced-motion sans mouvement, kWc absent jamais inventé), `toast.test.jsx` (toastMilestone), `SigneDialog.test.mjs` mis à jour.
- VX236 — (a) `MesEquipesCard.jsx` : pipeline ouvert et CA signé ouvrent `/crm/leads?equipe=` / `/ventes/devis?statut=accepte&equipe=`, réellement filtrés sur les membres de l'équipe via un nouveau `hooks/useEquipeMembreIds.js` (client-side, réutilise `crmApi.getEquipes()` déjà existant — aucun endpoint nouveau) branché dans `LeadsPage.jsx`/`DevisList.jsx`. « Activités en retard » ouvre `/activites` (pas de filtre équipe — `MesActivitesPage` est bâtie autour de « mes » activités, pas d'un tri par owner-id ; laissé pour une tâche dédiée). (b) `Journal.jsx` `MODEL_ROUTES` devient `(objectId) => path`, réutilisant les deep-links VX79/VX22 (`?lead=`/`?devis=`/`?id=`) pour lead/client/devis/facture/installation/intervention/ticket — les modèles sans deep-link (avoir/équipement/produit/admin) gardent leur route de liste inchangée. (c) `KpiAlertesPage.jsx` : la « dernière valeur » devient un lien vers sa source réelle (DSO/encours échu → `/reporting/balance-agee`, valeur de stock → `/stock`). (d) NON construit : `MonitoringSection.jsx` (aperçu « N systèmes seraient signalés » au blur du seuil) nécessite le nouvel endpoint `[BACKEND additif] GET /parametres/monitoring/apercu/` — hors périmètre de ce lane (frontend-only) ; à reprendre dans une tâche backend dédiée. Tests : `useEquipeMembreIds.test.jsx`, `KpiAlertesPage.test.jsx` (nouveau cas).
- VX247 — (a) `OnboardingCoachmarks.jsx` : `STEPS` porte désormais un `roles` optionnel filtré par le palier machine (`s.auth.role`) — les 2 étapes admin-only (profil société, inviter l'équipe) sont invisibles pour un rôle `normal`/`responsable` non prévu, et une nouvelle étape « Votre file de travail » cible `[data-coach="ma-file"]` (ancre ajoutée à `Sidebar.jsx` COACH_ANCHORS sur `/activites`) pour les rôles non-admin. (b) nouvelle étape FINALE sourcée de `GLOBAL_SHORTCUTS` (`providers/shortcuts.js`) — jamais un raccourci littéral dupliqué. (c) `Sidebar.jsx` affiche un badge « x/y » sur l'item Paramètres tant que la prise en main n'est pas à 100 % — réutilise le hook PARTAGÉ `useOnboardingSteps` (`onboardingHelpers.js`, déjà construit par VX36 pour `OnboardingBanner.jsx`) au lieu de créer un nouveau `hooks/useOnboardingProgress.js` dupliquant la même dérivation. (d) nouvelle `pages/aide/LexiquePage.jsx` (25 termes, recherche locale, route `/aide/lexique`) ; `ui/HelpTip.jsx` pointe désormais vers elle (lien interne, pas de doc externe — respecte la contrainte VX47). (e) NON construit : `[GATED-founder][BACKEND]` exposition de `seed_demo.py` — hors périmètre backend de ce lane, PROPOSER seulement selon la consigne du seed lui-même, jamais activer sans le fondateur. Tests : `OnboardingCoachmarks.test.jsx` (nouveau), `LexiquePage.test.jsx` (nouveau), `HelpTip.test.jsx` (cas ajouté + `MemoryRouter`).
- VX156 — `lib/voice.js` + `<WelcomeMoment>` already existed (welcome moment wired in `main.jsx`) but the other 5 voice moments were never posed on a real screen. Wired `voice.devisSent` (DevisList email-send toast description), `voice.emptyQueue` (MesActivitesPage empty state, replacing the ad-hoc string), `voice.chantierDone` (InstallationDetail mise-en-service success toast, previously silent), `voice.networkError` (canonical `lib/apiError.js` Network-Error branch, updated its test). `voice.dealSigned` left for VX155 (SigneDialog/DealSignedCelebration territory, `@with VX40`).

#### DONE LOG — Vague 2 (VX terrain/finance/CRM + QX groupe) (2026-07-12)

Vague 2 du plan-run (23 tâches VX + tagging de tous les plans, un seul merge). Lanes drainées en parallèle : **finance/terrain** VX44 (photos chantier en rafale + partage WhatsApp), VX88 (Ma journée → tournée géo), VX94 (Enter-pour-ajouter capture), VX105 (statut technicien + persistance + toasts hors-ligne), VX106 (signature client terrain), VX107 (résumé client lecture seule), VX52 (avertissements conformité tactiles), VX63 (erreurs FR lisibles DevisList/FactureList), VX114 (déjà présent, export daté), VX116 (relance groupée + aperçu WhatsApp). **ventes** VX222 (relancer devis), VX230 (encaisser depuis Relances), VX231 (navigation finance vers la cible). **UI/data** VX41 (data-viz marque + comparaison période), VX33 (Pilotage stock tour de contrôle), VX66 (anti-double-soumission Button), VX26 (couleurs stage dérivées tokens), VX81 (exports XLSX/CSV horodatés), VX61 (Web Vitals réels + endpoint reporting), VX110 (copier TSV), VX246 (queue interop iOS), VX19 (zéro popup navigateur, +réparation FactureList post-refactor VX230). Backend DoD à suivre : VX105 (`ajouter-reserve` gated admin), VX106 (signature dans `intervention_pdf.py`). GATED (non buildé) : QXG1/QXG2/QXG4 (compte/contenu fondateur). Tagging : les 10 fichiers de plan (PLAN/PLAN2/new_tasks + 7 domaines) reçoivent un tag `@lane:`/`Files:` visible par le planner sur la 1ʳᵉ ligne (append-only vérifié).

#### DONE LOG — Vague 1 (VX beauté/robustesse/pardon + seams) (2026-07-11)

Vague 1 du plan-run (66 tâches, un seul merge). VX design/marque : VX1-7 (jetons or/navy, sidebar/header, typo, dark mode, num tabulaires, radii/liseré, listes calmes), VX27/VX28/VX36 (cockpit par rôle, langage graphique unique, onboarding). VX robustesse/seams : VX62/VX90 (brouillon auto + focus ligne), VX68/69/70 (e2e mobile-safari/tablette/zoom/visuel), VX140/142/188/216 (DevisList/FactureList densité + DevisLineRow mémoïsé + seams devis↔chantier), VX192/221 (kanban a11y + score expliqué), VX199 (fix sur-permission `IsResponsableOrAdmin`→`ventes_valider`/`crm_modifier`). VX CRM : VX22-25/45/87/89/111 (route lead dédiée, ChatterTimeline, carte kanban 2 niveaux, MonthGrid, microcopie, CallLogPopover, dialog Escape, pièce jointe note). VX pardon/shell : VX91/93/97/98 (ProduitPicker+quick-create facture, smart defaults, historique modifs, puce fraîcheur + journal), VX14/56/82 (onglets NotificationBell, polling visibilité, titres d'onglet). VX admin/reporting : VX29/38/40/47/103/104 (dashboard commercial, ports DataTable, célébration devis signé, HelpTip contextuels, délégations absence, superviseur direct). VX227/251 (seams achat↔chantier, tableau dispatch drag-drop). Déjà présents : VX160.

#### DONE LOG — QJ batch (2026-06-25)

All 25 QJ tasks built, locally validated against Postgres+MinIO, and merged in one batch.
- QJ1 — ShareLink open-tracking (first_viewed_at/view_count/last_viewed_at, chatter event, devis-list badge). SCHEMA: ventes 0030.
- QJ2 — Instant seller notifications on new-lead / first-open / e-sign acceptance (in-app + Web Push + wa.me link). NEW EventTypes lead_new/devis_opened (notifications 0009).
- QJ3 — Already present (Celery beat scheduler from G9/N76); no rebuild.
- QJ4 — Automated devis follow-up cadence (j+2/5/10, FR+AR, beat-scheduled, idempotent). SCHEMA: ventes 0035 DevisNudgeLog.
- QJ5 — Auto quote-expiry (envoye→expire) + funnel hygiene (QUOTE_SENT→FOLLOW_UP→COLD), beat-scheduled, no-regress guards.
- QJ6 — Rule-based lead scoring + hot-list sort. SCHEMA: crm 0026 Lead.score.
- QJ7 — Auto NEW→CONTACTED on first contact (events bus, idempotent).
- QJ8 — Webhook dedupe beyond 60 s (email/phone fingerprint, cross-company safe).
- QJ9 — First-touch UTM/fbclid copied at signature (lossless) + Meta CAPI SignedQuote wired. AUTH/DEP: CAPI send GATED on META_CAPI_ACCESS_TOKEN/META_CAPI_PIXEL_ID.
- QJ10 — Immutable e-sign record (loi 53-05: UA+content hash+consent+IP+ts) + locked-PDF email, best-effort. SCHEMA: ventes 0031.
- QJ11 — Toggleable OTP confirmation before acceptance (ESIGN_OTP_ENABLED, default OFF = unchanged).
- QJ12 — Indicative financing block in the quote (cash vs green-loan vs ONEE, Tatwir/ISTIDAMA), flagged « indicatif ».
- QJ13 — Self-consumption-first 82-21 savings + ONEE/Lydec/Redal tranche tables; surplus-injection kept OFF; no invented numbers.
- QJ14 — Server-side « Envoyer par e-mail » (PDF + tokenized link + EmailLog), marks envoye via status service.
- QJ15 — Quote size-variants (dupliquer-variante) + side-by-side comparison.
- QJ16 — Reusable quote presets (DevisPreset save/apply + ViewSet). SCHEMA: ventes 0033.
- QJ17 — from-layout idempotency (lead+layout hash) + pre-flight composition check (422, no PDF 500). SCHEMA: ventes 0034 layout_hash.
- QJ18 — Commercial dashboard (funnel %, time-in-stage, velocity, win rate, seller leaderboard).
- QJ19 — Win/loss + close-rate-by-source report.
- QJ20 — Self-booking site-visit scheduler + reminder (beat), Ramadan-aware pacing flag. SCHEMA: crm 0027 Appointment.
- QJ21 — Richer layout fidelity (full multi-pan geometry + per-pan azimuth in roof_layout).
- QJ22 — Signed-proposal PDF artifact + prominent « Proposition signée » surfacing + seller notification.
- QJ23 — WhatsApp Business API SCAFFOLD (flag-gated, default manual wa.me). DEP/COST: live BSP send GATED on a founder BSP account + Meta-verified number. SCHEMA: notifications 0008.
- QJ24 — Online deposit SCAFFOLD (acompte calc + CMI/PayZone provider seam, flag-gated). DEP/COST: live deposit GATED on a founder merchant account; accept-flow wiring is a follow-up.
- QJ25 — Built FREE per founder: OSM/Overpass building-footprint auto-detection from the client's pin (no key, no cost). Automatic OBSTACLE detection stays out of scope (needs paid imagery).

---

### Group QW — Quote-journey wiring completion: catch the signals the site already sends (founder forensic audit, 2026-07-05)

*A 6-agent read-only forensic audit of the whole web→ERP quote journey found the pattern behind
"it's a mess": the website half (WEB_PLAN WJ39–94) shipped and diligently SENDS the signals, but
the ERP RECEIVERS were never built — so ~10 capture fields, the "call me" preference, and every
proposal-stage callback/question/revision request are silently DROPPED. This group builds the
receiving half. The website-side counterparts are **WEB_PLAN WJ95–WJ107** (cross-referenced per
task). Callback alerts use FREE in-app + email now (founder decision 2026-07-05); the
automated-WhatsApp-send path stays behind the existing QJ23 flag. Do NOT touch the `/proposal` PDF
engine (rule #4).*

> **2026-07-05 Fable completeness-critic pass — CORRECTIONS + additions (all verified against real code).**
> The critic corrected two things in this group and found a live bug + more gaps: (1) the
> proposal-contact/OTP endpoints ALREADY EXIST at the `public/` mount — QW5 is an ALIAS + contract fix,
> NOT a rebuild; the client does NOT see a false success (an honest "Service momentanément indisponible"
> shows on failure). (2) **QW7 is a LIVE data-corruption bug** — the proposal-view beacon overwrites real
> lead names with "Lead site web". (3) QW8 — QW4's email leg is config-dead by default. (4) QW9/QW10 —
> webhook replay + dedup hardening. QW2 amended (reuse `Lead.societe`, add more dropped keys).

- [x] QW7 **(already present)** — **[LIVE BUG] Stop the proposal-view beacon corrupting real leads.** **[Founder decision 2026-07-05: the corruption is being fixed at the WEB SOURCE via WEB_PLAN WJ109 (auto-deploys, no ERP deploy). This backend QW7 is now an OPTIONAL defensive backstop — do NOT prioritize/deploy it just for this bug; WJ109 already stops it. Keep only as belt-and-suspenders webhook hardening.]** `apps/web/src/pages/api/proposition-track.ts` POSTs engagement pings (`event_type`, `phoneE164`, `qualified:false`, `utm_source:'proposal_engagement'`) to the SAME CRM lead webhook. `_map_payload_to_fields` ignores `event_type`, sets `nom='Lead site web'` (no fullName — `webhooks.py:182`) and `tags='Sous le seuil 1 000 MAD'`; the layer-2 dedup then finds the real lead by phone and the update loop writes every non-empty value (`webhooks.py:373-383`) — so a client merely OPENING their proposal OVERWRITES their real lead name with "Lead site web" and stamps it below-threshold. Fix: when `event_type` is present, log ONLY a chatter note + notification on the matched lead (by phone, company-scoped) and SKIP the field merge entirely — never write nom/tags/utm/canal from an engagement ping, never create a Lead from one. Also fix the merge-loop contract (the comment `webhooks.py:369-371` claims "sans jamais écraser" but non-empty values DO overwrite — at minimum never overwrite a real `nom` with the `'Lead site web'` fallback; add a regression test). **Done =** an engagement ping never mutates a lead's nom/tags/attribution and never creates a lead; a real capture still does; tests cover both. Files: `apps/crm/webhooks.py`, `apps/crm/tests_webhook.py`. (ROUTINE — note in DONE LOG; this is a live data-integrity fix) (@lane: backend/crm-webhook) (@after: QW1)
- [x] QW8 — **Make QW4's email leg actually fire (today it's config-dead by default).** `is_email_configured()` gates on `settings.ANYMAIL.get('BREVO_API_KEY')` (`email_service.py:39`) but `ANYMAIL` only ever holds `SENDGRID_API_KEY`/`SENDINBLUE_API_KEY` (`settings/base.py:287-290`) — that key check is dead; email works only if `EMAIL_BACKEND` is an explicit non-console backend (`email_service.py:41-51`). AND `notifications.services.DEFAULT_PREFS['email']=False` (`services.py:31-35`) — so even when configured, `notify()` won't email a user without a `NotificationPreference` opt-in. Fix: correct the key lookup (honor `SENDINBLUE_API_KEY`/`SENDGRID_API_KEY`), default the email channel ON for the callback event type (per-event override or a `NotificationRoutingRule`), document the required prod env (`EMAIL_BACKEND` + `BREVO_API_KEY` + `DEFAULT_FROM_EMAIL`), and add a test asserting a phone_ok callback produces an outbound `EmailMessage` when configured. **Done =** a configured prod fires the callback email; a test proves it; docs updated. Files: `apps/ventes/email_service.py`, `apps/notifications/services.py`, `docs/production.md`, tests. (ROUTINE — note in DONE LOG) (@lane: backend/crm-callback) (@after: QW4) **Why:** the founder chose "free email now" — without this the email silently no-ops.

---

### Groupe QX — Quote journey best-in-world ROUND 6: verified defects + conversion loop (2 audit rounds × 24 agents, adversarially verified + Fable design pass, 2026-07-10)

*A 2-round deep audit of the whole web→ERP quote journey (10 code lanes + 4 researchers, then 10
adversarial verifiers + Fable completeness critic + Fable target-state designer). 52 of 53 round-1
findings were CONFIRMED or PARTIAL under adversarial re-verification against real code; every task
below carries a verified fix spec. Three cross-cutting truths the whole group serves: (1) there is
NO single owner of the money number — six independent computations of a quote's value coexist and
three ignore `remise_globale`; (2) the dominant failure mode is UNWIRED features — built, tested,
then never scheduled/routed/linked; (3) client-facing URLs are minted ad hoc with two confirmed
404s at moments of maximum client intent. Rule #4 intact throughout: PDF fixes go INSIDE the
vendored engine; the engine only renders. Research anchors: Storydoc 1.3M sessions (82% of opens
happen <1h; 46% of signers sign <48h of open; losing proposals get viewed 3.5×), Proposify 2025
(e-sign path = 4× close, images +72%), MIT/Oldroyd speed-to-lead (21× qualification <5 min).
E-signature legal basis: cite **Law 43-20 (2020, BO n°6970 2021)** which superseded loi 53-05.*

**A — ONE MONEY MODEL (the critical: client sees discounted TTC, is billed full price)**
- [x] QX1 — **[CRITICAL] `remise_globale` reaches the ENTIRE billing chain.** Verified end-to-end trace: the discount is applied on the client-facing path (`quote_engine/builder.py:534-585` canonical HT→remise→TVA→TTC, `public_views.py:400-403`) and DROPPED by every billing consumer: `Devis.total_ht/tva/ttc` (`apps/ventes/models.py:199-230` — pure line sums), `utils/options.py:83-104 option_totaux` (BOTH branches), `utils/echeancier.py:129-147` + `:208-210` (acompte/matériel/solde tranches billed on the undiscounted total), `views/bon_commande.py:379-397 creer_facture` (copies lines, drops the global discount; `Facture.remise_globale` field exists at `models.py:650` but is NEVER read in `Facture.total_*`), and `templates/pdf/bon_commande.html:143-161` (VISIBLY shows a remise line then bills the full pre-discount TTC — an internally-inconsistent over-billing document; on a 200 000 MAD quote at 15% remise the client is over-billed ~30 000 MAD). Fix: route `option_totaux` through `selectors._canonical_totaux(lines, remise_globale_pct=devis.remise_globale, fallback_taux=devis.taux_tva)` in BOTH branches so échéancier/solde/BC inherit the discount; set + read `Facture.remise_globale` on the BC→facture path (or distribute the discount into copied line prices); fix `bon_commande.html` to treat the passed totals as already-net (pass gross+net so the remise line = the delta). CAUTION (verified): do NOT naïvely change `Devis.total_ht` semantics — the BC template re-applies remise on top of it today (double-subtract risk); land template + consumers together. **Done =** regression test asserting quote PDF total == BC total == Σ échéancier factures == accepted-option discounted TTC to the centime, for both 1-option and 2-option quotes, with and without per-line remise. Files: `apps/ventes/utils/options.py`, `utils/echeancier.py`, `views/bon_commande.py`, `templates/pdf/bon_commande.html`, `apps/ventes/models.py`, tests. (ROUTINE — data-integrity fix; note in DONE LOG) (@lane: ventes-money)
- [x] QX2 — **Fix the discount's OTHER consumers: founder KPIs, Meta CAPI value, DGI/UBL export.** Verified: `apps/reporting/commercial.py:221` + `apps/reporting/insights.py:676` aggregate leaderboard/CA on undiscounted `Devis.total_ht` (the founder steers on inflated revenue); the Meta CAPI conversion value uses undiscounted `devis.total_ttc` (mis-scaled on 2-option quotes); `apps/ventes/utils/ubl.py:120-141` builds `LegalMonetaryTotal` from the same undiscounted chain — a BLOCKER for ever arming `CompanyProfile.dgi_export_actif` (DGI clearance model pre-validates amounts with the tax authority; the SME/TPE phase hits 2027-01-01). Fix all three to consume the canonical discounted total (accepted option where applicable). **Done =** leaderboard CA == accepted discounted totals (test); CAPI value == display total; UBL `PayableAmount` == discounted TTC (test). Files: `apps/reporting/commercial.py`, `apps/reporting/insights.py`, CAPI emitter in `apps/crm` or `apps/ventes`, `apps/ventes/utils/ubl.py`, tests. (ROUTINE) (@lane: ventes-money) (@after: QX1)
- [x] QX3 — **[CRITICAL] Fail-closed payments: no free "PAID".** Verified reachable in prod: `erp_agentique/urls.py:50` mounts `public_urls` unconditionally; `PaymentLink.provider` defaults `'noop'` everywhere (`models.py:1974`, `services.py:2373`, `email_service.py:259`, `views/facture.py:930`); `NoOpProvider.verify_webhook` (`apps/ventes/payments/providers.py:91-105`) returns `{'paid': True}` for ANY payload — so `POST {}` to `/api/django/public/pay/<token>/webhook/` records a fabricated `Paiement`, flips the Facture to PAYEE and fires `facture_paid`. Fix: NoOp returns `paid: False` (mirror `HostedGatewayProvider`'s no-credentials branch); `montant` must come from server-side `link.montant`, never the payload; per-token throttle on the webhook. **Done =** unauthenticated `POST {}` can never mark a facture paid (test); a real provider path still works. Files: `apps/ventes/payments/providers.py`, new test. (ROUTINE — security fix; note in DONE LOG) (@lane: ventes-pay)

**B — THE CLIENT PDF (rule #4 — all fixes INSIDE the vendored engine)**
- [x] QX4 — **[CRITICAL] De-Taqinorize the residential renderer (multi-tenant identity leak).** The DEFAULT residential proposal hardcodes TAQINOR's legal identity for every tenant — verified inventory: `residential/theme.py:246` (footer TAQINOR·email·phone), `theme.py:50` (bundled logo), `trust.py:228-232` (legal band: TAQINOR Solutions SARLAU / capital 100 000 MAD / RC 691213 / ICE 003799642000067 / « Gérant : M. Reda Kasri »), `trust.py:363` (« Pourquoi TAQINOR »), `trust.py:403` (signature block), `cover.py:292/317/354`, `renderer.py:72-76` (taqinor.ma links), plus `theme.py:164-200` + `options.py:33/51/71/144` (`produits_base='taqinor.ma/produits'`). The legacy engine is already tenant-aware via `_apply_entreprise` (`generate_devis_premium.py:335-431`) — the DC1 fix never reached the residential renderer. Fix: thread `data['entreprise']` into `build_ctx` and drive every identity literal from it, falling back to the current literals ONLY when empty (mirror `_apply_entreprise` exactly); add `CompanyProfile.capital` + `CompanyProfile.gerant` (additive migration) for the two facts with no home. **Done =** rendering the residential PDF for a second Company shows THAT company's identity everywhere (test greps rendered HTML/PDF context); Taqinor output byte-equivalent-in-content for Taqinor. Files: `quote_engine/residential/{render,renderer,theme,trust,cover,options}.py`, `apps/parametres` (CompanyProfile migration), `apps/ventes/tests/test_quote_engine.py`. (SCHEMA — additive migration; note in DONE LOG) (@lane: quote-engine)
- [x] QX5 — **Never print a phantom option: gate the two option cards on the real scenario.** Verified: a battery-only/hybrid residential quote prints a fabricated cheaper « Option 1 — Sans batterie » missing the inverter, on page 1 (`residential/cover.py`) AND page 2 (`residential/options.py:364` fixed « Équipement commun aux deux options » heading, `:378-391` both delta cards, `:150-156`+`:397-400` both totals chains — all unconditional). Fix: thread `data['scenario']`/`sans_ok`/`avec_ok` flags (already locals in `builder.py`) into the renderer; single-option quotes render ONE full-width card, page 2 drops the delta split and renames the heading. **Done =** battery-only quote shows exactly one option everywhere; 2-option quotes unchanged; page-count tests still pass. Files: `quote_engine/residential/{renderer,render,cover,options}.py`, `builder.py`, tests. (ROUTINE) (@lane: quote-engine)
- [x] QX6 — **Fix the strongest CTA: PDF sign QR → live proposal; real page numbers.** Verified: the QR/« Signez en ligne » points at invented `taqinor.ma/signer/<ref>` (404, `residential/renderer.py:71-77`) and the footer hardcodes « Page X / 3 » (`theme.py:247`). Fix: in the builder, mint/reuse `ShareLink.for_devis(devis)` and set `data['links']['signer'] = f"{SITE_URL}/proposition/{token}"`; footer uses the real rendered page total; drive `produits_base`/realisations/avis links from company `site_url` (suppress when absent). Proposify 2025: an e-sign path = 4× close rate, 40% faster. **Done =** QR on a fresh residential PDF opens the live tokenized proposal; no hardcoded page count. Files: `quote_engine/builder.py`, `residential/renderer.py`, `residential/theme.py`, tests. (ROUTINE) (@lane: quote-engine) (@after: QX4)
- [x] QX7 — **PDF numbers honesty pack.** Verified defects, all in-engine: (a) coverage donut fabricates a plausible figure — floored 40 / capped 99 with an invented `/1.3` divisor (`residential/renderer.py:56-57`) → compute from real annual consumption via a thin crm selector when bills exist, honest « estimation » label otherwise, drop the floor; (b) `custom_acompte` clamp prints a dead 0% « Matériel » box with mislabelled percentages (`generate_devis_premium.py:~1620-1668`) → collapse to a two-box schedule summing to 100%; (c) `client_city` read but never set (`cover.py:59`) → resolve from `lead.ville` or drop the dead field; (d) TWO avoided-kWh prices contradict each other on one proposal (`constants.KWH_PRICE=1.75` in `public_views._monthly_consumption` vs the ROI `tarif_kwh` ~1.20/tranche) → thread the ROI tarif everywhere; (e) equipment-brand chips claim « Canadian Solar · Huawei · Deye » + « 3 000 h/an » + « 87,4 % » regardless of the quote's real lines (`trust.py:106/116-121`, `generate_devis_premium.py:1434`) → derive brands from the quote's real `item['marque']` values (fallback « équipements certifiés IEC »), make the marketing figures tenant-editable copy. **Done =** each sub-item has a test; no fabricated number survives. Files: `quote_engine/residential/{renderer,cover,trust}.py`, `generate_devis_premium.py`, `builder.py`, `apps/ventes/public_views.py`, tests. (ROUTINE) (@lane: quote-engine) (@after: QX4)
- [x] QX8 — **Engine warm path: stop re-doing pure work per render.** Verified: per-render font/logo reload incl. a per-pixel logo recolor loop + 4 matplotlib charts, serialized under one global lock — a burst of clients opening proposal links queues single-file. Fix: `functools.lru_cache` the recolored-logo b64 + font-face CSS (`residential/theme.py` — pure functions); cache rendered PDF bytes keyed by the existing render-fingerprint (complements the queued ERR74 /proposal-persist fix — do not duplicate it); shrink the global-lock surface where safe. **Done =** second render of an unchanged devis skips font/logo/chart work (timed test or call-count assert); output byte-identical. Files: `quote_engine/residential/theme.py`, `quote_engine/builder.py`. (ROUTINE) (@lane: quote-engine)

**C — E-SIGN & ACCEPTANCE (the decision moment)**
- [x] QX9 — **Real e-sign evidence + the promised signed PDF (Law 43-20).** Verified end-to-end: the canvas signature (`[token].astro:2650` `canvas.toDataURL`), `consent_esign`, `signed_at_client` and `on_behalf_of` travel through `proposition-accept.ts:85-102` and are ALL discarded by `public_views.proposal_accept:743-789` (reads only nom/option/`consentement` — a key the frontend never sends, so consent silently defaults True; `DevisSignature` has no fields for any of it). AND the confirmation email promises « ci-joint votre exemplaire signé » but frequently ships without it: `accept_devis` holds a stale in-memory Devis while `_store_signed_pdf` persists `fichier_pdf` on a SEPARATE instance (`services.py:1238` vs `builder.py:1257-1259`), and the blank-attachment branch logs nothing (`email_service.py:93-95`). Fix: additive migration on `DevisSignature` (`signature_image` stored to MinIO or TextField data-URL, `consent_esign` bool, `signed_at_client`, `on_behalf_of`); `proposal_accept` reads the real keys and returns 400 when consent is not truthy (mirror the `nom` guard); `devis.refresh_from_db(fields=['fichier_pdf'])` before `_send_acceptance_emails`, prefer `DevisSignature.signed_pdf_key` as the attachment source, log the blank branch. **Done =** a signed acceptance persists all four artifacts (test), the confirmation email provably carries the signed PDF (test), consent is server-enforced. Files: `apps/ventes/public_views.py`, `services.py`, `models.py` (+migration), `email_service.py`, tests. (SCHEMA — additive migration; note in DONE LOG) (@lane: ventes-esign)
- [x] QX10 — **OTP: honest channel + brute-force lockout.** Verified: `_send_otp_whatsapp` (`services.py:723-737`) is a log-only stub that returns True (so enabling `ESIGN_OTP_ENABLED` today locks phone-only clients out of signing entirely), and `validate_esign_otp` (`services.py:695-720`) has NO attempt counter — 6-digit space, 10-min TTL, unlimited tries. Fix: stub returns False until a real send path exists (fallback then routes to email); per-token failed-attempt counter in cache, lockout ≥5 wrong tries (« trop de tentatives, redemandez un code »); startup/system-check warning when `ESIGN_OTP_ENABLED` is on while the WhatsApp stub is the only channel. **Done =** tests for lockout + honest-stub routing. Files: `apps/ventes/services.py`, tests. (ROUTINE) (@lane: ventes-esign)

**D — WIRE THE DEAD AUTOMATION (built, tested, never scheduled/linked)**
- [x] QX11 — **Schedule ALL built-but-dead periodic jobs + a reachability guard.** Verified sweep: 10 built periodic tasks are absent from `erp_agentique/celery.py` beat_schedule — headline: `ventes.devis_a_facturer_reminder` (ZFAC12 — « accepted but never invoiced » sits forever un-nudged) and `ventes.pre_echeance_reminders` (XFAC7); add the other verified absentees at sensible off-peak crontab slots following the file's per-app comment convention. Also switch `expire_stale_devis` (`services.py:2880`) to the Casablanca-aware date helper its siblings use. Add a GUARD TEST: every `@shared_task` that looks periodic (name-listed) is either in beat_schedule or on an explicit on-demand allowlist — so this bug class (the codebase's dominant failure mode) can never silently recur. **Done =** beat runs all 10 (test asserts schedule entries); guard test in place. Files: `erp_agentique/celery.py`, `apps/ventes/services.py`, new test. (ROUTINE — note in DONE LOG) (@lane: backend-beat)
- [x] QX12 — **Notification deep-links that actually land.** Verified: « Devis accepté »/« Devis expiré » notifications link `/devis/{pk}` — a route that doesn't exist (`apps/notifications/signals.py:94/117`), and `Dashboard.jsx:369`'s `?statut=accepte` link is equally dead because `DevisList.jsx` reads NEITHER `devis` nor `statut` search params (verified: only `variantes`/`design3d`). Fix both producers to `/ventes/devis?devis={pk}` AND teach DevisList to consume `devis` (open/highlight that quote) + `statut` (pre-set filter) on mount. **Done =** clicking each notification/dashboard link lands on the intended quote/filter (component test). Files: `apps/notifications/signals.py`, `frontend/src/pages/ventes/DevisList.jsx`, tests. (ROUTINE) (@lane: frontend-devislist)
- [x] QX13 — **Follow-up nudges the seller can actually SEE — and that respect reality.** Verified: the j+2/j+5/j+10 devis cadence's default `wa_draft` branch produces ONLY a server log line (`services.py:2803-2813`) — no Notification, no UI surface; its message embeds `taqinor.ma/proposal/<token>` which 404s (the page is `/proposition/`, `services.py:2772` — every other producer uses the right form); and the cadence is BLIND to seller/client activity (`services.py:2728-2765` — no check of manual `LeadActivity`, future `lead.relance_date`, or recent proposal engagement). Fix: (a) one-line URL fix + a SHARED client-URL builder helper used by ALL producers, with a test asserting each emitted path exists in the website's route table (two 404s were found at moments of maximum client intent); (b) `wa_draft` branch creates a real `Notification` (new `EventType`, e.g. `devis_nudge_due`) with title/body/prefilled wa.me draft + deep-link; (c) suppression rules: skip/defer a nudge level when a manual contact activity exists since the last level, `relance_date` is set in the future, or proposal engagement was recorded in the last N days. **Done =** a due nudge is visible in-app with a working link; suppression tests for all three signals. Files: `apps/ventes/services.py`, `apps/notifications/models.py` (EventType — additive), a new shared URL helper (e.g. `apps/ventes/utils/client_links.py`), tests. (ROUTINE) (@lane: backend-nudges) (@after: QX11)

**E — WEBHOOK & CRM INTAKE FIDELITY**
- [x] QX14 — **Persist `Lead.score` on webhook leads → auto-MQL finally fires for the #1 source.** Verified: EVERY other lead-creation path calls `recompute_lead_score` (views.py:561/574, services.py:1088/1366/1429/2782) EXCEPT `apps/crm/webhooks.py` (lines 595 create-branch / 620 update-branch) — the serializer recomputes for display, masking that `?ordering=-score` and `maybe_assign_mql` (XMKT21 hot-lead auto-routing) silently never work for website leads. Fix: call `recompute_lead_score(lead)` in both branches (best-effort try/except like `notify_new_lead`). **Done =** webhook lead lands with persisted score; MQL auto-assign test. Files: `apps/crm/webhooks.py`, `tests_webhook.py`. (ROUTINE) (@lane: crm-webhook)
- [x] QX15 — **Callback SLA clock measures the right thing.** Verified: `escalader_rappels_demandes` uses `Lead.date_creation` (`apps/crm/selectors.py:867`) so any old lead whose callback preference is set NOW is instantly « SLA-breached » — false-urgent noise that teaches sellers to ignore escalations. Fix: additive `Lead.contact_preference_set_at` (migration), stamped at BOTH write sites (webhook mapping + `services.py:1740-1742`); selector uses it with `date_creation` fallback. **Done =** fresh phone_ok on an old lead does not escalate (test). Files: `apps/crm/models.py` (+migration), `webhooks.py`, `services.py`, `selectors.py`, tests. (SCHEMA — additive migration) (@lane: crm-webhook)
- [x] QX16 — **« Jamais perdre un lead » becomes operational: payload replay surface.** Verified: `WebsiteLeadPayload` is write-only — no admin, no endpoint, no management command reads it; a mapping-failed payload is a silently lost customer despite the module's own guarantee (`webhooks.py:7-8`). Fix: read-only admin registration (list: company/processed/error/received_at/lead) + a small CRM surface listing failed/lead-less payloads with one-click replay through `_map_payload_to_fields` + founder notification on mapping failure. **Done =** a forced mapping failure is visible and replayable to a real Lead (test). Files: `apps/crm/admin.py`, `views.py`/serializer, small frontend list, tests. (ROUTINE) (@lane: crm-webhook)
- [x] QX17 — **Client dedup by phone, not just email.** Verified: `resolve_client_for_lead._find_existing` (`services.py:881`) matches by email only — a repeat client with no/different email gets a duplicate `crm.Client`, fragmenting history and `plafond_credit`. Fix: after email miss, match on `normalize_phone` equality within the company (Python-side compare; document the perf bound). Phone-first identity is the norm in Morocco. **Done =** same-phone lead reuses the existing client (test). Files: `apps/crm/services.py`, tests. (ROUTINE) (@lane: crm-services)
- [x] QX18 — **Arabic doesn't die at the document layer.** Verified: the AR web journey + trilingual proposal page exist, but `Lead.langue_preferee='darija'` never seeds `Client.langue_document` (default FR) — the arabophone client gets a French flagship PDF at the decision moment. Fix: `resolve_client_for_lead` seeds `langue_document='ar'` when the lead prefers darija; surface the field in the client form; (AR gloss on residential PDF headline numbers = follow-up, in-engine). **Done =** darija lead → client with `langue_document='ar'` (test). Files: `apps/crm/services.py`, `frontend` client form, tests. (ROUTINE) (@lane: crm-services)

**F — SELLER QUOTE CREATION (the generator)**
- [x] QX19 — **Auto-quote consumes everything the client already told us.** Verified: `createAutoQuote` hardcodes `structureType:'acier'` at BOTH `autoQuote.js:81` (agricole) and `:101`, ignoring `Lead.structure_pref=ALUMINIUM`; ignores `taille_souhaitee_kwc` (size from bills only) and `batterie_souhaitee`; and `solar.js autoFillLines` (~:602) silently substitutes catalogue panel wattage while the screen kWc is computed from the TYPED wattage — a 550W-for-710W substitution ships a 7.7 kWc system labelled 9.94 kWc. Fix: derive panel count from `taille_souhaitee_kwc` when set (reuse `panneauxPourKwc`); respect `structure_pref` in both branches; seed the battery scenario from `batterie_souhaitee`; surface `actualPanelW` from autoFillLines and either recompute the displayed kWc from ACTUAL lines or block with a visible warning on mismatch; harden the Huawei Smart-Meter/Dongle free-text match. **Done =** each consumed field has a test; a wattage substitution can never change kWc silently. Files: `frontend/src/features/ventes/autoQuote.js`, `solar.js`, `DevisGenerator.jsx`, tests. (ROUTINE) (@lane: frontend-generator)
- [x] QX20 — **A solar quote must contain solar equipment.** Verified: `validate()` (`DevisGenerator.jsx:935`) never requires a panel/inverter line — a « quote » of one manual line « Installation, 500 MAD » passes and can be sent. Fix: mode-specific equipment gate — résidentiel/industriel require ≥1 panel line AND ≥1 inverter line (classification helpers exist in solar.js); agricole requires a pump; clear French error naming what's missing. **Done =** zero-equipment quote blocked with explicit message (test); legitimate edge cases (accessories-only avenant) get a documented escape hatch decision. Files: `frontend/src/pages/ventes/DevisGenerator.jsx`, `frontend/src/features/ventes/solar.js` (export `isPompe`), tests. (ROUTINE) (@lane: frontend-generator)
- [x] QX21 — **Atomic quote save (create AND edit) + honest PDF progress.** Verified: creation is 1+N unguarded round-trips (`DevisGenerator.jsx:1026`) leaving invisible orphan/partial brouillons a seller can later send; the EDIT path is worse — delete-all-lines with swallowed errors THEN recreate (`:1015-1021`), able to leave a devis with fewer/no lines; nothing ever cleans zero-line drafts (verified: `expire_stale_devis` touches only ENVOYE). The atomic pattern already exists server-side (`build_devis_from_layout`, `services.py:395-527`) but no general endpoint exposes it. Fix: transactional nested-write endpoint (create devis+lignes in one commit) + `replace-lines` action for edits; generator uses both; PDF polling (`DevisList.jsx:593`) shows a resumable « toujours en cours » state past 30 s instead of giving up (no duplicate Celery jobs). **Done =** kill-the-connection mid-save leaves either nothing or a complete devis (test); edit failure preserves old lines. Files: `apps/ventes/views/devis.py`, `serializers.py`, `frontend .../DevisGenerator.jsx`, `DevisList.jsx`, tests. (ROUTINE) (@lane: ventes-devis-api)
- [x] QX22 — **Truthful « Envoyé » on the WhatsApp path.** Verified frontend-side: `handleEnvoyer` (`DevisList.jsx:410`) flips status when the modal OPENS — closing without sending leaves a phantom-sent quote whose validity clock started. (Server no-phone case REFUTED — `views/devis.py:1032-1038` already 400s before `mark_devis_sent`; don't touch.) Fix: split preview vs send — a read-only preview action populates the modal; `mark_devis_sent` fires only on actual wa.me click-through. **Done =** open-then-close leaves brouillon (test); click-through marks Envoyé exactly once. Files: `apps/ventes/views/devis.py` (preview action), `frontend .../DevisList.jsx`, tests. (ROUTINE) (@lane: frontend-devislist)
- [x] QX23 — **Mode-switch guard + persisted margin snapshot.** Verified: switching market mode after data entry silently discards the étude/ROI chart with no warning and no restore (`DevisGenerator.jsx:410`); and margin/prix-kWc indicators are screen-only — once saved, nobody can see what margin a sent quote carried. Fix: blocking confirm when auto-filled lines exist for another mode; server-side `marge_snapshot` Decimal on Devis computed at save/send (additive migration) shown ONLY in the generator/DevisList manager view — **NEVER in any PDF or client-facing output (prix_achat rule)**. **Done =** mode switch warns; saved quote's margin visible internally; `test_quote_engine.py` still asserts no `prix_achat` in any PDF context. Files: `frontend .../DevisGenerator.jsx`, `apps/ventes/models.py` (+migration), `views/devis.py`, `DevisList.jsx`, tests. (SCHEMA — additive migration) (@lane: ventes-devis-api)
- [x] QX24 — **`etude_params` can't silently go stale.** Verified: production/économies freeze at creation while line edits float — payback = new_total / old_économies is internally inconsistent on the proposal. Fix (option b from verification): recompute+repersist the study whenever lignes/remise/prix change (service hook on LigneDevis save/delete + remise_globale change), keeping seller-entered overrides flagged. **Done =** editing a line updates économies/payback coherently (test); proposal shows consistent numbers. Files: `apps/ventes/services.py`, `models.py`/signals, tests. (ROUTINE) (@lane: ventes-devis-api) (@after: QX21)

**G — SELLER DAY-IN-THE-LIFE**
- [x] QX25 — **Call-ready rows everywhere.** Verified three dead ends: « Mes activités » (the literal daily call list) has no phone/tel:/wa.me on any row (needs a `target_phone` SerializerMethodField via the crm selector); the mobile Leads List view hides the phone column entirely with no tap-to-call fallback (`ListView.jsx:251-260` name cell is never hidden — put the compact tel/wa icons there); and « Planifier une relance » on every Kanban card has ALWAYS been dead — the prop is never passed (`LeadsPage.jsx` viewProps `:327-340` lacks `onPlanifierRelance`; `LeadCard.jsx:43-47` falls back to inert text). Fix all three (wire the handler to the existing setEditLead/setShowForm machinery). **Done =** every activity row and mobile lead row is one tap from call/WhatsApp; the relance shortcut opens the lead with relance focus (tests). Files: `apps/records/serializers.py`, `frontend .../MesActivites`, `crm/leads/{LeadsPage,views/ListView,LeadCard}.jsx`, tests. (ROUTINE) (@lane: frontend-crm)
- [x] QX26 — **Structured loss reasons — learn WHY quotes die.** Verified: refusal reason is an OPTIONAL `window.prompt` free-text (`DevisList.jsx:448-461`), disconnected from the managed `MotifPerte` taxonomy — win/loss data is unusable. Fix: mandatory modal with a MotifPerte select (company-scoped endpoint exists) + optional detail note; write to `Devis.motif_refus` + lead + chatter; feed the existing loss reporting. **Done =** refusing requires a structured reason (test); reporting groups by motif. Files: `frontend .../DevisList.jsx` (+small modal), `apps/ventes` serializer if needed, tests. (ROUTINE) (@lane: frontend-devislist)
- [x] QX27 — **Action-row sanity + typed-interaction rendering.** Verified: DevisList renders 10-14 ungrouped buttons per row (worst on mobile); and `LeadActivity` kinds `appel`/`email` (FG30) render as BLANK chatter items (no conditional branch in `LeadForm.jsx:~1217`). Fix: keep 1-2 status-primary actions inline, rest in a ⋯ DropdownMenu (pattern exists in ListView.jsx); add 📞/✉️ chatter branches with outcome labels. **Done =** ≤3 visible actions per row; appel/email activities render with body+outcome (tests). Files: `frontend .../DevisList.jsx`, `crm/LeadForm.jsx`, tests. (ROUTINE) (@lane: frontend-crm)
- [x] QX28 — **Lead readiness chips — surface what the website already captured.** Verified: the seller cannot tell a lead has a GPS pin/roof outline (`roof_point` reaches ONLY the ToitureDesign 3D path; DevisGenerator never reads it; both quote buttons look identical). Fix: chips on LeadCard/LeadForm from existing fields (« Toit épinglé (GPS) », « Facture saisie », « Prêt à deviser en 1 clic »); badge the 3D button when roof data exists; DevisGenerator shows a « repère toit disponible → Concevoir en 3D » shortcut when set. **Done =** a data-rich lead is visually distinct and routes the seller to the path that uses its data (test). Files: `frontend .../LeadCard.jsx`, `LeadForm.jsx`, `DevisGenerator.jsx`. (ROUTINE) (@lane: frontend-crm)
- [x] QX29 — **« Relances du jour » — the devis work-queue.** Verified: no « quotes needing action today » surface exists (Dashboard is analytics-only; DevisList's only proactive surface is a 7-day expiry banner). Fix: `DevisActionBoardPage` mirroring `SavActionBoardPage`: sent-no-response per cadence level, accepted-not-invoiced (reuse the ZFAC12 selector), refused-without-motif, expiring-soon; every row deep-links via the fixed `?devis=` param with tel/wa shortcuts. **Done =** one page answers « which quotes need me today ». Files: new `frontend/src/pages/ventes/DevisActionBoardPage.jsx`, route, reuse `apps/ventes/selectors.py`. (ROUTINE) (@lane: frontend-devislist) (@after: QX11, QX12)

**H — THE CONVERSION LOOP (research-anchored)**
- [x] QX30 — **Engagement-triggered follow-up engine.** Replace blind day-counting with behavior triggers from data the system already records (ShareLink first-view + `proposal_engagement` sections/time): not-opened-24h → resend nudge; opened-not-signed-48h → call task (46% of signers sign <48 h of open); reopened-3× → « hésite — appelez maintenant » (losing proposals get viewed 3.5×). Also fix the verified lost-update bug: `proposal_engagement` JSON read-modify-write is non-atomic (concurrent section beacons last-write-win) — use `select_for_update`/F-style merge. All triggers land as Notifications + QX29 queue rows with prefilled wa.me drafts. **Done =** each trigger has a test; engagement updates are race-safe. Files: `apps/ventes/services.py`, `public_views.py`, `apps/notifications`, tests. (ROUTINE) (@lane: backend-nudges) (@after: QX13, QX29)
- [x] QX31 — **Speed-to-lead: minutes, not hours.** MIT/Oldroyd: 21× qualification contacting <5 min vs 30; 78% buy from the first responder; industry average is ~42-47 h. Fix pack: first-touch timer on NEW-column kanban cards (« il y a 12 min, non contacté »); unread-hot-lead escalation — if the new-lead notification of a high-score lead is unread after N minutes, escalate (in-app + email now; WhatsApp behind the existing QJ23 flag); instrument time-to-first-touch (lead creation → first outbound LeadActivity) as a reporting metric per seller. **Done =** escalation fires on unread hot leads (test); the metric appears in reporting. Files: `apps/notifications/sweeps.py` or `apps/crm/tasks.py`, `apps/reporting`, `frontend .../LeadCard.jsx`, tests. (ROUTINE) (@lane: crm-speedtolead) (@after: QX14)
- [x] QX32 — **Unified lead timeline.** Verified gap: a seller preparing a call must open two screens (lead chatter vs devis list) to see « proposal viewed 3×, 2 min on price ». Fix: thin `apps/ventes/selectors.py::devis_events_for_lead(lead_id, company)` (sent/opened/signed/refused + engagement summary) merged into the crm `historique` timeline per the cross-app boundary rule; render in LeadForm chatter with distinct icons. **Done =** lead timeline shows quote lifecycle + engagement inline (test). Files: `apps/ventes/selectors.py`, `apps/crm/views.py`, `frontend .../LeadForm.jsx`, tests. (ROUTINE) (@lane: crm-timeline) (@after: QX30)
- [x] QX33 — **Deposit at the moment of signature (degraded no-PSP mode now).** Verified: `deposit.py` + `payment_providers.py` are fully built and completely unreachable from the accept flow — the founder chases payment by phone at peak intent. Fix: post-sign success screen + confirmation email show the acompte (échéancier tranche 1 on the DISCOUNTED total per QX1) with RIB/virement instructions + a « j'ai effectué le virement » declaration that notifies the seller and stamps the devis; a card-payment-link slot activates when a PSP provider is configured (QXG2). Solo's pattern: sign-and-pay in one sitting removes the « I'll get back to you » exit. **Done =** signing shows payment instructions; the declaration reaches the seller (tests); zero behavior change when nothing configured upstream of accept. Files: `apps/ventes/public_views.py`, `services.py`, `deposit.py`, proposal success-state payload, tests. (ROUTINE) (@lane: ventes-esign) (@after: QX1, QX9)
- [x] QX34 — **Post-sign status endpoint `/suivi/<token>` (ERP half; web page = WEB_PLAN WJ115).** Tokenized public read-only endpoint deriving the milestone timeline from existing rows: Devis accepté → Acompte reçu (Paiement) → Matériel commandé (BC) → Installation planifiée/posée (Installation statut) → Facture. Same token discipline as ShareLink (`secrets.token_urlsafe(32)`, expiry, company-bound). Research: post-sign portals (myFreedom, Yes Solar 2025) are the emerging installer differentiator — pure internal engineering, no paid dep, becomes the referral surface. **Done =** endpoint returns the correct milestone state for a devis at each lifecycle stage (tests); no PDF/status behavior touched (rule #4). Files: `apps/ventes/public_views.py`, `public_urls.py`, selector, tests. (ROUTINE) (@lane: ventes-public) (@after: QX33)
- [x] QX35 — **Wire the parrainage promise.** Verified: `parrainage.astro` promises « vous êtes récompensé — sans rien à gérer » but NOTHING connects `utm_source=parrainage` to the `Parrainage` model — no auto-create, no conversion detection, no reward trigger. Fix: webhook auto-creates `Parrainage(filleul_lead=lead, statut='en_attente')` on `utm_source=parrainage` + manager notification; deterministic referral codes on Client (surface in the client form + web link generator later); `devis_accepted` subscriber flips converti when the filleul signs. **Done =** referred lead → visible Parrainage; signature → converti (tests). Files: `apps/crm/webhooks.py`, `receivers.py`, `models.py` (code field — additive migration), tests. (SCHEMA — additive migration) (@lane: crm-webhook)
- [x] QX36 — **Inbound email: replies stop landing in a void.** Verified: FOUR inbound-email subsystems exist, ZERO run — `core/email_intake.py::poll_mailbox` has no beat entry (which also leaves SAV email-to-ticket dead), `apps/ventes/inbound_email.py::capture_inbound_email` has no live caller, and outbound quote emails set no `reply_to`. Fix: schedule `poll_mailbox` in beat (env-gated on mailbox creds); register a ventes handler routing reference-matched replies to `capture_inbound_email` (chatter + notification on the devis); set `reply_to` on outbound quote/facture emails. **Done =** a reply to a quote email surfaces on the devis + notifies the seller (test with stubbed mailbox). Files: `erp_agentique/celery.py`, `core/email_intake.py` wiring, `apps/ventes/inbound_email.py`, `email_service.py`, tests. (ROUTINE) (@lane: backend-beat) (@after: QX11)
- [x] QX37 — **One webhook surface.** Verified: `core.WebhookSubscription`/`core/webhooks.py::dispatch_event` is a dead duplicate of the live `publicapi` webhook layer — configured subscriptions never fire, and its help_text promises exactly the event names the OTHER system delivers. Fold or delete it so exactly one subscription surface exists (keep publicapi). **Done =** no dead subscription model remains; migration removes or repurposes cleanly. Files: `core/webhooks.py`, `core/models.py` (+migration), tests. (SCHEMA — destructive but revertable migration; note in DONE LOG) (@lane: core-cleanup)

**I — ONE TRUE MATH (screen == PDF == proposal)**
- [x] QX38 — **One canonical solar-math model.** Verified: three divergent productibles (solar.js GHI ~1247, engine 1600/1240) = ~28% swing screen-vs-PDF; two avoided-kWh prices; the ONEE tranche table collapses the 101-250 band (mis-prices typical 150-400 kWh/mo homes); `monthlyBillFromKwh`/`_monthly_bill_from_kwh` double-count overflow on finite-ceiling custom tables; 1-MAD per-option rounding divergence. A FOURTH, most-defensible model already exists stranded in `apps/web` (`yieldTable.ts` — PVGIS TMY per-city lat×tilt×aspect, e.g. Agadir ~1687). Fix: promote the PVGIS yield lookup into ONE shared committed asset consumed by `builder.py`/`pricing.py` AND `solar.js` (per-city static values, no paid API); CompanyProfile 1600 becomes an editable override, not a competing physics model; ONE avoided-kWh price threaded everywhere (QX7d); corrected ONEE tranche table aligned across `kwhFromBill`/`two_bills_savings`/both bill-from-kWh functions (fix the overflow double-count); align the rounding chain to kill the 1-MAD divergence. **[DECISION — founder adjudicates the canonical productible; PVGIS recommended.]** **Done =** one committed table; generator screen, PDF and web proposal show the SAME production/économies for the same inputs (cross-engine test). Files: shared asset (e.g. `quote_engine/productible.py` + mirrored JS/TS), `solar.js`, `builder.py`, `pricing.py`, `constants.py`, tests. (DECISION + ROUTINE) (@lane: solar-math)
- [x] QX39 — **Honest 25-year cashflow.** Payback today is a single Year-1 ratio — neither conservative nor best-case. Fix in-engine (+ mirrored in solar.js via QX38): 0.5%/yr panel degradation, documented tariff-escalation hypothesis, battery round-trip efficiency, optional inverter-replacement year; payback = cumulative cashflow zero-crossing; assumptions block rendered on PDF + web proposal (source of ensoleillement, dégradation, hypothèse tarifaire — self-consumption-first, BT surplus tariff still unpublished as of 2026-06-18 checks, 20% injection cap pre-baked). **Done =** payback from a real cashflow with stated assumptions (tests); charts stop implying flat savings for 25 years. Files: `quote_engine/pricing.py`, `residential` charts, `solar.js`, tests. (ROUTINE) (@lane: solar-math) (@after: QX38)
- [x] QX40 — **Pompage electrical + data sanity.** Verified: curve-mode can pair a 380V triphasé pump with a 220V variateur (no phase/voltage cross-check in `selectPompeByCurve`, `solar.js:795-816`) — latent until OSP pumps get priced (QXG3), then live; plus suspicious HMT seeds (7.5CV@220m, 10CV@250m — likely shutoff head, not duty point). Fix: phase-compatibility filter before selection + assert pump tension == variateur tension in compose; degrade to the CV path with a visible warning when no phase-compatible priced curve pump exists; seed values corrected under QXG3 (founder data). **Done =** a mono/220V request can never return a 380V pump (test). Files: `frontend/src/features/ventes/solar.js`, tests. (ROUTINE) (@lane: solar-math)

**J — PUBLIC SURFACE HARDENING & RETENTION**
- [x] QX41 — **Public hardening pack.** Verified: `open_chat_session` is completely unthrottled (unbounded anonymous row creation); e-catalogue « demander devis » has no idempotency (double-click floods seller with duplicate brouillons + notifications); the public accept path lacks row-level locking (double-accept race can double-fire `devis_accepted` side effects). Fix: per-IP throttle on chat-open (+ register the hardcoded throttle scopes in `DEFAULT_THROTTLE_RATES` as the single source of truth); cache.add idempotency lock on the cart submission keyed token+contact-hash (mirror `proposal_contact_request`); `select_for_update` around accept. **Done =** tests for all three. Files: `apps/crm/public_chat_views.py`, `apps/ventes/public_views.py`, `services.py`, `settings/base.py`, tests. (ROUTINE) (@lane: ventes-public)
- [x] QX42 — **PII retention for the raw intake copies.** Verified: `WebsiteLeadPayload` (raw PII + IP, SET_NULL from Lead so erasure never reaches it) and `ChatSessionPublique` accumulate FOREVER; the generic `core.retention` framework + its beat job exist but the registry is EMPTY — no app registers a policy. Fix: register retention policies in `CrmConfig.ready()` (purge processed payloads after N days — founder-configurable, default 180; stale chat sessions similarly); document in the privacy page's terms. GDPR-relevant: marocains-du-monde deliberately targets EU diaspora. **Done =** sweep purges old rows (test); unprocessed/error payloads exempt until QX16's replay surface has aged them. Files: `apps/crm/apps.py`, `services.py`, tests. (ROUTINE) (@lane: crm-retention) (@after: QX16)

**GATED — founder decisions/accounts/data (queue, do NOT build the gated part)**
- [ ] QXG1 — **[GATED: founder account]** WhatsApp BSP evaluation, 360dialog-first (flat $59/€49/mo, zero markup on Meta per-template pricing — 2026 model is per-template-message, the old free tier is gone). Needs Meta Business verification + Morocco rate confirmation from the dashboard (not blogs). Unlocks: automated template sends for QX30's nudges, real OTP channel (QX10), proposal delivery. Until then everything ships degraded via wa.me drafts. (@blocked: founder account WhatsApp BSP) (@lane: whatsapp-bsp)
- [ ] QXG2 — **[GATED: founder account]** PayZone-first merchant onboarding (reported 5-10 day onboarding, no deposit, ~2-3% fees — verify primary-source), CMI later if volume justifies. Activates QX33's card-payment slot + facture PaymentLinks with a REAL provider (QX3 keeps everything fail-closed meanwhile). (@blocked: founder account PayZone/CMI) (@lane: ventes-pay)
- [ ] QXG3 — **[GATED: founder data]** Price the 11 OSP 30-series curve pumps (today ALL curve pumps are seeded price=0, so the intended HMT+débit agricole flow can never quote a buyable pump — the highest-impact single data entry in the journey) + verify/correct the suspicious HMT seeds (7.5CV@220m, 10CV@250m must be nominal duty points, not shutoff head) + confirm/replace the archived estimated coffrets. Land QX40's phase check first. (@blocked: founder data pump prices) (@lane: backend/stock)
- [ ] QXG4 — **[GATED: founder content]** Real proof pack for the trust page: selected installation photos, named testimonials, certifications (checked-facts-only rule — omit what doesn't exist). Proposify 2025: images +72% close rate, testimonials near the price +73% win probability. Lands inline in `residential/trust.py` after QX4. (@blocked: founder content proof pack) (@lane: quote-engine)
- [ ] QXG5 — **[GATED: founder ops check, 10 minutes]** Production env sanity: confirm `WEBSITE_LEADS_COMPANY_ID` is set (else `_resolve_company()` falls back to first Company by pk — silent misrouting risk if a second Company row ever exists); confirm the outbound email backend keys (`EMAIL_BACKEND`/`SENDGRID_API_KEY` vs `SENDINBLUE_API_KEY`) so QW8/QX13's email legs are live; confirm `PUBLIC_MAPTILER_KEY` naming on Cloudflare. (@blocked: founder ops env check) (@lane: ops-config) [2026-07-13 code guard added: both `_resolve_company()` copies (`apps/crm/webhooks.py`, `apps/crm/public_chat_views.py`) now `logger.error` LOUDLY when `WEBSITE_LEADS_COMPANY_ID` is unset AND 2+ Company rows exist, or when it's set to a non-existent pk — safe fallback preserved (never breaks the public endpoint), misconfiguration is now visible in logs. Still `[ ]`: the founder ops confirmation (var actually set in prod) is unbuilt/unverifiable here.]

---

### TOP PRIORITY — build first (queued 2026-06-20)


### Group U — Field UX bugs + document-status "connections" (founder request 2026-06-22)

*Live issues Reda is hitting in the field, plus the family of "connection"
gaps found while investigating #4 (an action in one place that should flip a
document status or surface it in another menu, but doesn't). U1–U3 are UX/layout
bugs; U4–U5 are the two Reda named; U6–U12 are the similar disconnects an audit
turned up. Hard constraints stay in force: rule #4 status preservation (the quote
PDF engine only RENDERS, `/proposal` is the only client PDF path), STAGES.py keys
are imported never hardcoded, all migrations additive/nullable + company-scoped
server-side, cross-app reads/writes go through `selectors.py`/`services.py` and
the `core/events.py` bus (never another app's models/views).*


### Group Q — Devis ↔ Toiture 3D pipeline (backend; founder request 2026-06-21)

*Goal: weld the existing `roofPro11` 3D tool (in `apps/web`) and the premium quote
into ONE loop — client points at their roof → Meriem designs it → client receives a
premium web proposal and e-signs. The expensive engine already exists (3D optimizer,
PVGIS production via `/api/roof-production`, premium quote engine); Group Q adds only
the **backend persistence, storage and wiring**. The matching front-end tasks live in
`docs/WEB_PLAN.md` (W112–W118).*

> **CRITICAL UX RULE (applies to the whole pipeline).** The client does the bare
> minimum and NEVER sees panels auto-fill. The client is **not obliged to draw** — they
> just **point** at their roof (drop a pin / pick the building) and give their bill;
> **Meriem** draws the outline (if needed) and runs the auto-fill/optimizer later,
> privately — so the client believes TAQINOR drew the whole design for them. Backend
> therefore stores the client's *pin (+ optional rough outline)* (Q2) separately from
> the *finalized layout with panels* (Q1); only the finalized layout ever reaches the
> proposal.

> **Constraints.** All schema additive/nullable, seeded from current defaults; every
> viewset company-scoped server-side (never trust `company` from the body). The legacy
> `/proposal` PDF path stays byte-identical (rule #4): Group Q only *adds* a web
> channel the founder explicitly authorized; the quote document statuses
> (`brouillon→envoye→accepte…`) are preserved 1:1 (rule #4 status preservation).

  JSONField to `Devis` (additive migration) holding the *finalized* serialized
  `AreaRecord[]` (roof vertices, obstacles, roofType, pitch, azimuth, the result
  `{panels,kwc,annualKwh,savings}`, and `renderPlan`). Add company-scoped DRF
  endpoints `POST /api/django/ventes/devis/<id>/layout/` (save — company forced in
  the serializer/`perform_create`, never from body) and `GET …/layout/` (load).
  **Done =** round-trip save/load test + a cross-tenant isolation test pass. Files:
  `apps/ventes/models.py` (+migration), `apps/ventes/views.py`/serializers, tests.

  `roof_point` (lat/lng of the building the client pinned) and `roof_outline` (OPTIONAL
  rough polygon, usually empty — the client need not draw) JSONFields to the CRM Lead,
  plus the bill kWh and a secure unguessable per-lead `token` (UUID) for the Meriem
  hand-off link. First VERIFY the W105–W111 contact-capture work (it may already carry
  part of this) and EXTEND rather than duplicate; wire the lead intake/webhook
  (`apps/crm/webhooks.py`) to accept + persist the pin (+ optional outline) with the
  lead. **Done =** the pin persists on the lead, token resolves the lead, company forced
  server-side; tests cover it. Files: `apps/crm/models.py` (+migration),
  `apps/crm/webhooks.py`/views, tests.

  finalized layout (kWc, nb panneaux, production, chosen module/onduleur) into Devis
  lines from the seeded catalogue, reusing the SAME composition rules as the quote
  generator (`builder.py` réseau/injection/hybride/batterie/panneau keywords) and the
  reference-numbering util (`apps/ventes/utils/references.py`, never count()+1), with the
  client resolved via `apps/crm/services.resolve_client_for_lead`. Store the layout's
  production into `Devis.etude_params`. **Done =** a sample layout produces a coherent,
  company-scoped Devis with correct kWc/lines/totals and NEVER auto-quotes a price-less
  product (existing guard); tests cover residential réseau + hybride+batterie. Files:
  `apps/ventes/services.py`, `apps/crm/services.py`, tests.

  and store it in MinIO reusing the existing PDF bucket/`minio_client` infra, keyed +
  company-scoped, referenced from a nullable `Devis.roof_image` field (additive).
  Endpoint `POST /api/django/ventes/devis/<id>/roof-image/`. **Done =** upload + signed
  retrieval test + company-scoping test pass. Files: `apps/ventes/utils/` (minio),
  `apps/ventes/models.py` (+migration), views, tests.

  Extend the quote-data builder so a quote CAN show the real roof render as the "votre
  installation" visual and use the layout's kWc/production/savings instead of estimating
  — **only when a layout/render is present**; with none present the existing PDF output
  stays byte-identical (back-compat, rule #4). **Done =** with-layout vs without-layout
  tests both pass and the no-layout render is unchanged. Files: `quote_engine/builder.py`
  (guarded), tests. *(Additive only — does not alter the legacy path.)*

  `GET /api/django/ventes/proposal/<token>/` returning the quote data
  (`build_quote_data` output + roof-image signed URL + option totals) as JSON for the
  client web proposal (W116) to render — authenticated by the signed token, not a login,
  company-scoped, expired/invalid tokens rejected. **Done =** valid token returns the
  payload; invalid/expired rejected; no cross-tenant leakage; tests cover it. Files:
  `apps/ventes/views.py`/urls, token util, tests.

  `POST /api/django/ventes/proposal/<token>/accept/` that records typed name + timestamp
  + IP into the existing acceptance fields (`accepte_par_nom`/`date_acceptation`, N26) and
  flips the Devis to `accepte` THROUGH the existing acceptance service so the document
  chain (bon-commande/facture) is preserved 1:1 (rule #4). **Done =** accept flips status
  + writes the stamp + is idempotent on double-submit; tests cover it. Files:
  `apps/ventes/services.py` (reuse the acceptance path), views, tests. *(A legal-grade
  eIDAS e-sign provider stays a separate GATED decision — v1 reuses the existing stamp.)*

### Group R — AI assistant: actions across the ERP (registry-driven; founder request 2026-06-21)

*Goal: extend the existing FastAPI assistant (today: read-only NL→SQL Q&A plus three
hard-coded action tools) into a registry-driven agent that can DO things across the whole ERP —
and any future feature — without hand-coding a new tool each time: create a quote, generate its
PDF, prepare the WhatsApp send, run the CRM funnel, invoice, record payments, and operate
stock/SAV/installations. The foundation (AG1–AG3) is built once and proven end-to-end with
quotes (AG4); the rest is mostly catalogue entries (AG5–AG9). Approved in the 2026-06-21
brainstorm with Reda.*

> **Safety model (applies to the whole group).** Every action still runs through the normal
> Django API with the logged-in user's JWT, so company-scoping + permissions are re-checked
> server-side; the agent never writes to the database directly and can only call endpoints that
> are in the catalogue (a whitelist), with inputs validated against the entry. Outward or
> irreversible actions (accept, invoice, record payment) never execute on their own — the agent
> returns a preview the user confirms first. WhatsApp "send" builds a `wa.me` link the user taps
> (the manual tap IS the confirmation); the existing `leads/<id>/whatsapp-devis/` endpoint
> already returns it. Schema changes stay additive/nullable; STAGES.py keys are imported, never
> hardcoded.

> **Gated future upgrade (NOT queued — prose only).** Automatic WhatsApp sending via a WhatsApp
> Business API provider (Meta Cloud API / Twilio) is a new paid dependency plus account setup,
> so it stays a founder decision; v1's `preparer_envoi_whatsapp` only builds the wa.me link to
> tap. A database-backed, admin-editable catalogue is likewise deferred — v1 declares actions in
> code, beside the app that owns them.


> **Voice layer (AG10–AG12, founder request 2026-06-21).** Adds a hands-free voice
> conversation to the assistant — speak questions, hear answers, continuous loop.
> Speech→text uses Groq `whisper-large-v3` via the existing `GROQ_API_KEY` (no new paid
> service); text→speech uses the browser's built-in voices (free). Voice never bypasses the
> propose→confirm spine: outward/irreversible actions still require an explicit spoken
> « confirmer » or a tap before anything executes. (Distinct from Group S's self-hosted
> chat-memo transcription — this is the assistant's spoken conversation.)


### Group S — Internal team chat ("Discuss") (founder request 2026-06-21)

*Goal: a best-in-class INTERNAL team chat inside the ERP — staff message each other
1-to-1 (DMs) and in named channels, with file/image/voice attachments, @mentions,
reactions, pinned messages, message search, edit/delete, and the ERP superpower of
dropping a record (lead/devis/chantier) into a conversation as a rich clickable card.
New messages arrive by smart polling while a conversation is open and by the existing
Web Push (iPhone/Windows) when the app is backgrounded; per-conversation mute is
supported. Voice memos are transcribed (FR/Arabic/Darija best-effort) by a self-hosted
faster-whisper model in the FastAPI AI service, degrading gracefully when disabled.
Approved in the 2026-06-21 brainstorm with Reda. Full design in
`docs/superpowers/specs/2026-06-21-internal-team-chat-module-design.md`.*

> **Safety model (applies to the whole group).** Strict multi-tenant isolation: every
> model carries a `company` FK forced server-side (never from the body), and every viewset
> is company-scoped AND membership-checked (a user can only read/post in conversations they
> belong to — non-member 403, cross-tenant 404). All migrations additive/nullable. Cross-app
> reads (lead/devis/chantier labels for the share-a-record card) go through the target app's
> `selectors.py` — never importing its models/views (CI import contract). Attachments reuse
> `apps/records/storage.py` (MinIO, type-validated, 10 MB). Notifications reuse the existing
> `notify()` entry point + Web Push. STAGES.py is not involved.

> **Real-time stays polling for v1 (founder choice 2026-06-21).** No WebSocket/Channels in
> v1 — new messages arrive by short-polling the open conversation (~3 s) plus the existing
> Web Push when backgrounded. Typing indicators + live presence + instant delivery are
> deferred to the GATED **S21** WebSocket upgrade (brand-new ASGI/Channels infra), which a
> plan-run must NOT build until the founder provisions it.

> **One founder-approved backend dependency.** S10 adds `faster-whisper` (self-hosted,
> CPU-efficient, no paid service) + a lazily-downloaded model to the FastAPI AI service,
> behind a `CHAT_TRANSCRIPTION_ENABLED` flag so existing deploys are unaffected when off.
> This single dependency is pre-approved (2026-06-21 brainstorm); no other new dependency
> (backend or frontend npm) is authorized — the frontend reuses the existing Radix / lucide /
> sonner / @dnd-kit kit and the browser `MediaRecorder` for voice.

- [BLOCKED: waits on founder-provisioned WS infra (ASGI server process + Redis channel layer + nginx WebSocket proxy) — a real external prerequisite a run can't satisfy] S21 — **Real-time WebSocket upgrade (Django Channels).** Instant message delivery, typing indicators and live presence via Django Channels + a Redis channel layer + an ASGI server (daphne/uvicorn) + an nginx WebSocket proxy, authenticated with the same JWT. (UNGATED from category-gating 2026-06-21; held only by the infra prerequisite. **MY RECOMMENDATION: DEFER — "Discuss" chat already works via 3 s short-polling (`useChatPolling.js`); the WS stack adds real ops complexity (sticky sessions, connection draining on deploy) for a marginal gain on a small internal team. Build it only on a concrete need (live dispatch / many concurrent users).** Files: `erp_agentique/asgi.py`, `apps/chat/consumers.py` (new), settings `CHANNEL_LAYERS`, nginx config, frontend socket client.) (ARCH) (@lane: realtime)

# Taqinor OS — UI/UX overhaul ("prettier than Odoo")

*Goal: a calm, premium, data-first ERP — Linear/Stripe-tier polish, brand-matched to Taqinor, denser and cleaner than Odoo. Built on the existing React 19 + Vite + Tailwind 4 + recharts stack. Positioned ahead of Groups A–D so feature work inherits the new design language. Constraints: do NOT touch the devis/facture PDF templates, the public PDF pages, or the PdfCanvas PDF content (client-facing, gated separately); do NOT touch the apps/web marketing site; STAGES.py stays a fixed CI contract; schema changes additive/nullable only, every new value seeded from current in-code defaults.*

> **Renumbered on intake (2026-06-18):** the source proposal lettered these groups E–O, but `docs/PLAN2.md` already has a **Group E** (the E2E browser-test suite, tasks E1–E16). To keep every group/task id unique, the UI/UX-overhaul groups were shifted one letter to **F–P** (and their task ids re-prefixed to match) before being inserted here. Titles, content, and the running task numbers (14–69) are otherwise verbatim.

> **World-class look-and-feel wave (queued 2026-06-21, founder request "best-looking ERP in the world").**
> The design *foundation* already shipped (tokens.css, ~45 `src/ui` primitives, the hand-rolled
> `DataTable`, the app shell with sidebar/global-search/breadcrumbs/bottom-tab-bar) — so this wave is
> **adoption + refinement to Linear/Stripe/Vercel tier**, grounded in a fresh world-class audit (OKLCH
> tokens, premium tables, ⌘K command palette, restrained charts, tasteful motion, mobile/PWA polish,
> WCAG 2.2 AA). Tasks **F120–P171** fill the previously-empty Group F–P headers (the original 14–69
> series shipped/archived in `docs/DONE.md`; these continue the running number at 120 to stay unique).
> Hard constraints (unchanged): NEVER touch the devis/facture PDF templates, the public PDF pages, the
> `PdfCanvas` content, or the `apps/web` marketing site; import stage names from `STAGES.py` (never
> hardcode); schema changes additive/nullable seeded from current defaults; **no new npm dependency**
> (build on the already-installed Radix / recharts / @tanstack/react-table / @dnd-kit / sonner / lucide
> — anything else is gated). New user-facing text in French.

### Groupe VX — « Le plus bel ERP du monde » : signature visuelle, expérience Apps & craft + perfection technique (audits 16+11 agents, 2026-07-07/08)

*Provenance : demande du fondateur (2026-07-07) « make my ERP the best looking in the world + les modules
sont-ils mieux découpés façon Odoo ? ». Audit multi-agents à modèles étagés : 9 lanes de lecture du repo
(design-core, shell-nav, écrans CRM/ventes/ops/insight/fondation, mobile-PWA, scan de cohérence) + 5
recherches web best-in-class (Odoo 18/19, Linear/Attio/Stripe/Notion, data-viz, délice/motion,
field-service) + une carte anti-duplication sur TOUS les plans, puis synthèse Fable. Chaque constat est
vérifié dans le code (fichier:ligne) et re-vérifié par l'orchestrateur avant intégration.*

**VERDICT MODULES — la réponse à la question du fondateur.** Le découpage façon Odoo est le BON choix et il
est déjà à moitié fait : GARDER et TERMINER le plan ODX tel que queued (PLAN.md ODX1–23 — manifests, catalogue
+ fermeture de dépendances et enforcement déjà livrés ; les moves restants facturation/achats/ao/portail/frais
sont des migrations state-only, sûres et révertables) — ne jamais re-fusionner, revenir en arrière coûterait
plus cher que finir. MAIS le découpage backend seul ne donnera jamais l'effet « apps » perçu : ce que
l'utilisateur ressent comme des modules est une expérience de NAVIGATION. Aujourd'hui la sidebar empile ~106
destinations plates (45 codées en dur + 61 items de 16 `module.config.jsx`) toutes du même gris avec le même
accent — Compta, RH, QHSE et Litiges sont visuellement interchangeables. Ce groupe construit la couche
frontend manquante (accent par module, lanceur d'apps, favoris épinglés, breadcrumb→cockpit) en s'ADOSSANT à
ODX5/6/7 (queued), jamais en les dupliquant.

**Vision « Lumière sur Nuit ».** Un fond calme bleu nuit ; la lumière (brass) dépensée avec parcimonie
exactement là où l'énergie circule. Diagnostic central vérifié : la fondation de tokens (F120–P171) est
world-class sur le papier, mais l'app RENDUE est une installation shadcn slate générique — ~604 hex codés en
dur dans `index.css` (top : la palette slate par défaut de Tailwind, pas la marque), coquille Sidebar/Header
100 % figée hors tokens, QUATRE « ors » et TROIS « navys » concurrents, `<body>` en system-ui + `#f1f5f9`,
dark mode à moitié réel. Cette vague est de l'ADOPTION et de la SIGNATURE, pas une refonte de la fondation.

> **Contraintes (chaque tâche VX).** Zéro nouvelle dépendance npm (Radix / Tailwind 4 / recharts /
> @tanstack / @dnd-kit / sonner / lucide déjà installés suffisent — sinon flag [GATED: new dep]). Ne JAMAIS
> toucher les templates PDF devis/facture, les pages PDF publiques, PdfCanvas, `/proposal` (règle #4) ni
> `apps/web`. Clés de stage importées de STAGES.py, jamais codées (règle #2 — seules des COULEURS peuvent
> être tokenisées). UI en français ; hooks e2e (`ap-*`, `att-*`, `pp-*`) préservés et déplacés AVEC leurs
> éléments ; garde `noValidate`/`step="any"` du générateur intacte ; `prix_achat`/marge JAMAIS client-facing.
> Frontend-only — DEUX exceptions round 2, flaggées dans leur tâche : VX61 (endpoint de collecte web-vitals
> dans l'app `reporting` existante) et VX76 (templates d'email HTML, zéro logique) ; `prefers-reduced-motion` respecté partout ;
> contraste AA en clair ET en sombre. Le modèle conseillé par tâche est indicatif (l'orchestrateur arbitre).
> **Coordination inter-plans :** `docs/FRONTEND_GAP_PLAN.md` (câblage fonctionnel des backends X*/Z*, ajouté
> 2026-07-07 via fe-dev) partage trois fichiers avec ce groupe — `GedNavigator.jsx` (FE-XGED14 ↔ VX38),
> `TicketsPage.jsx` (FE-XSAV5/21/28 ↔ VX31), `DevisList.jsx` (FE-ZSAL8/XSAL16 ↔ VX7/20/40/44). Le run qui
> passe en second rebase sur le premier ; les deux plans sont complémentaires (câblage vs design), jamais
> en conflit d'intention.

**A — La signature : la coquille devient TAQINOR (le meilleur ratio qualité perçue ÷ effort de la vague) :**
- [x] VX1 — **Un seul or, un seul navy : fusion des jetons de marque.** Éliminer les quatre « ors » (`--primary #e8b54a`, `--cat-gold #f5a623`, `#F5C100` sidebar/bolt, `#f28e2b` gen-btn) et les trois « navys » (`--nuit`, `--cat-navy #0b1f3a`, `#0f172a`) : redéfinir `--cat-gold: var(--primary)` et `--cat-navy: var(--color-nuit)` dans `frontend/src/design/tokens.css`, retirer les redéclarations locales (`frontend/src/index.css` ~1520-1525 et bloc `.lv-wrap` ~4469) et les constantes JS `NAVY`/`GOLD` de `frontend/src/features/pwa/PwaPrompts.jsx` (→ `var(--…)`). Une signature exige UNE couleur signature (discipline Linear). **Done =** un seul or et un seul navy à travers catalogue/kanban/générateur/sidebar/bannière PWA, grep des valeurs mortes vide hors token source, CI stage-names verte. Files: frontend/src/design/tokens.css, frontend/src/index.css, frontend/src/features/pwa/PwaPrompts.jsx. (ROUTINE — M, sonnet) (@lane: frontend/design)
- [x] VX2 — **Re-signer la coquille permanente (Sidebar + Header) aux couleurs de marque.** Réécrire les blocs `.sidebar*` (19 classes) et `.header*` (16 classes) de `frontend/src/index.css` pour consommer les tokens : fond sidebar `var(--color-nuit)` au lieu de `#0f172a`, labels sur la rampe encre/lune, item actif via `--primary` au lieu de `#F5C100` figé, header en `var(--card)` + `border-color: var(--border)` (il suit ENFIN le dark mode), avatar en `var(--primary)`. Au passage regrouper les 8 boutons de `.header-right` en 3 grappes visuelles (Recherche / Communication / Préférences+compte) par des wrappers `header-cluster` dans `frontend/src/components/layout/Header.jsx` — CSS + wrappers uniquement, aucun changement de comportement. C'est le cadre vu 100 % du temps : le levier n°1 de reconnaissance. **Done =** coquille en nuit/brass en clair ET en sombre, grep `#0f172a|#3b82f6|#ffffff|#94a3b8` vide dans les blocs sidebar/header, e2e mobile + `.sidebar-nav-item.active` inchangés. Files: frontend/src/index.css, frontend/src/components/layout/Header.jsx. (ROUTINE — L, sonnet) (@lane: frontend/design) (@after: VX1)
- [x] VX3 — **La typo de marque et le fond tokenisé au niveau `<body>`.** Porter `font-family: var(--font-brand)` et un fond piloté par `var(--background)` sur le `<body>` (`frontend/src/index.css:24-29`, aujourd'hui system-ui + `#f1f5f9`), rendre `.ui-root` no-op hérité et retirer progressivement les wrappers par page (Dashboard.jsx:413, Journal, AgentChat, OcrUpload, Rapports…). Une app « la plus belle du monde » ne rend pas son texte courant en police système. **Done =** Hanken en corps + Archivo en titres sur tout écran sans wrapper, fond suivant le thème partout, contraste AA vérifié sur les surfaces legacy claires. Files: frontend/src/index.css, frontend/src/design/tokens.css, frontend/src/pages/Dashboard.jsx, frontend/src/pages/Journal.jsx, frontend/src/pages/Rapports.jsx, frontend/src/pages/ia/ (retrait des wrappers `.ui-root`). (ROUTINE — M, sonnet) (@lane: frontend/design) (@after: VX2)
- [x] VX4 — **Finir le dark mode sur la surface legacy.** Passer les blocs encore en clair figé (`.btn-primary`, `.data-table`/`th`/`td`, `.gen-card`, `.modal`, `.form-control`, `.agent-*`, `.status-tab`, `.search-input`) de `frontend/src/index.css` sur les tokens sémantiques (`--card`, `--border`, `--foreground`, `--primary`, `--muted`). Un dark mode à moitié réel (header/tables/boutons clairs sur ~51 fichiers legacy) est pire que pas de dark mode — l'erreur « négatif photo non fini » reprochée à Odoo 18. **Done =** basculer `.dark` rend header, tables, boutons, formulaires et chat agent sombres et cohérents ; contraste AA ; captures clair/sombre d'un écran liste + une fiche. Files: frontend/src/index.css. (ROUTINE — L, sonnet) (@lane: frontend/design) (@after: VX3)
- [x] VX5 — **Data typography « .num » : les chiffres deviennent les héros.** Créer un utilitaire `.num` (font-display + `tabular-nums slashed-zero` + tracking resserré) dans `frontend/src/design/tokens.css` et l'appliquer aux montants MAD, kWc, production, références et totaux : `frontend/src/ui/Stat.jsx` (déjà partiel), totaux devis `.devis-total-ttc`, `.gen-metric-value`, `.kb-col-money`, colonnes numériques DataTable. Le « numeric story » Stripe/Mercury — `lib/format.js` reste l'unique source de formatage fr/MAD. **Done =** tout chiffre monétaire/énergie aligne ses colonnes (même graisse, zéro barré), capture d'un tableau devis prouvant l'alignement. Files: frontend/src/design/tokens.css, frontend/src/ui/Stat.jsx, frontend/src/index.css. (ROUTINE — M, sonnet) (@lane: frontend/design) (@after: VX4)
- [x] VX6 — **Un seul langage de rayon et d'élévation.** Remplacer les rayons legacy en dur (cartes 14px, modale 14px, boutons 8px, `.gen-card`) par l'échelle dérivée de `--radius`, et aligner l'ombre au repos sur la discipline F122 : cartes = liseré (`shadow-card`), retirer l'ombre au repos de `.data-table` (index.css ~836), réserver `shadow-menu/modal/toast` aux calques flottants, pointer `frontend/src/ui/Card.jsx` sur `shadow-card`. **Done =** aucun `border-radius: 14px|8px` en dur hors token, cartes non « flottantes » au repos, menus/modales seuls porteurs d'ombre. Files: frontend/src/index.css, frontend/src/ui/Card.jsx. (ROUTINE — M, sonnet) (@lane: frontend/design) (@after: VX5)
- [x] VX7 — **Passe « calm color » : hiérarchie de poids visuel sur les écrans denses.** Une passe d'audit-ajustement (pas de refonte) sur DevisList, leads ListView, StockList et FactureList : bordures/séparateurs adoucis (~60 % d'opacité), métadonnées secondaires (dates, IDs, canaux) en muted, contraste plein réservé aux données primaires (nom client, montant TTC, statut) et aux signaux (retard, expiré) ; actions de survol en `opacity-0 group-hover:opacity-100` sans reflow. Recette « chrome désaturé / signal saturé » de Linear — le plus fort levier ressenti au plus bas coût sur un écran B2B dense. **Done =** capture avant/après des 3 listes, aucun test cassé, aucune info supprimée — seulement re-pesée. Files: frontend/src/pages/ventes/DevisList.jsx, frontend/src/pages/crm/leads/views/ListView.jsx, frontend/src/pages/stock/StockList.jsx, frontend/src/index.css. (ROUTINE — M, sonnet) (@lane: frontend/design) (@after: VX6)

**B — L'expérience « Apps » (la réponse frontend au verdict module-split ; s'adosse à ODX5/6/7, ne les duplique pas) :**
- [x] VX8 — **Un accent de couleur par module (le bout manquant du découpage Odoo).** Étendre le contrat `module.config.jsx` (et les sections encore codées en dur de `Sidebar.jsx` en attendant ODX7) d'un champ optionnel `accent` choisi parmi 6-8 teintes DÉRIVÉES des rampes OKLCH existantes (Finance=nuit, Ventes=brass, RH=azur, Terrain=lune…), posé en `--module-accent` sur `.sidebar-section` pour teinter liseré + icône active de CE module. Aucune couleur inventée, contraste AA clair et sombre, VENTES garde le brass ; conçu pour survivre à ODX7 (l'accent vivra dans le registre). L'orientation périphérique d'Odoo sans son incohérence — l'œil doit pouvoir dire « je suis dans QHSE » sans lire. **Done =** chaque section de nav a une couleur perceptible distincte, AA vérifié, e2e nav vertes. Files: frontend/src/index.css, frontend/src/components/layout/Sidebar.jsx, frontend/src/features/*/module.config.jsx, frontend/src/design/tokens.css. (ROUTINE — M, sonnet) (@lane: frontend/shell) (@after: VX2)
- [x] VX9 — **Le Lanceur d'applications TAQINOR (grille légère, pas une page).** La surface « toutes mes apps » qui manque : un overlay léger (Radix Dialog, bouton grille dans le header + raccourci `g a`) affichant les modules en grille par catégorie — icône + accent VX8 + label FR — favoris en tête, 3 récents, clic = navigation vers le cockpit du module. Données : `moduleConfigs` de `frontend/src/router/moduleRoutes.jsx` (et le catalogue ODX3 pour l'état actif quand ODX6 aura livré le filtrage — coordonner, ne pas dupliquer ODX6). Différence assumée avec Odoo : un overlay ~150 ms, PAS une re-navigation pleine page (jugée lourde par les utilisateurs Odoo eux-mêmes) ; quand ODX5 livrera l'écran Paramètres→Applications, lui appliquer le même langage de carte (extension design d'ODX5, pas un double). **Done =** ouvrir/naviguer/épingler au clavier et à la souris, reduced-motion respecté, aucun chevauchement fonctionnel avec ODX5/6. Files: frontend/src/components/layout/AppLauncher.jsx (nouveau), frontend/src/components/layout/Header.jsx, frontend/src/providers/ShortcutsProvider.jsx, frontend/src/index.css. (ROUTINE — L, sonnet) (@lane: frontend/shell) (@after: VX8)
- [x] VX10 — **Apps épinglées personnelles dans la Sidebar.** Une bande fine sous `.sidebar-role` listant 4-6 icônes de modules épinglés (clic = cockpit du module), bouton « + » pour épingler/désépingler depuis `moduleConfigs`, persistance `localStorage` (`taqinor.sidebar.pinned`, motif `COLLAPSE_KEY` de `Layout.jsx:16`), état partagé avec le lanceur VX9 (même clé). La densité à ~106 destinations se gère par la personnalisation (convergence Odoo 17 / Notion favorites / Attio pinned), pas par la réduction de police. **Done =** épingler/désépingler persiste au rechargement, aria-labels corrects, aucune régression des hooks `sidebar-nav-item`. Files: frontend/src/components/layout/PinnedApps.jsx (nouveau), frontend/src/components/layout/Sidebar.jsx, frontend/src/index.css. (ROUTINE — M, sonnet) (@lane: frontend/shell) (@after: VX9)
- [x] VX11 — **Fil d'Ariane cliquable vers le cockpit du module + mémoire du dernier module.** Étendre `moduleSectionLabels` pour porter `{label, to}` et rendre le premier segment du breadcrumb cliquable quand un cockpit existe (`rh`→`/rh`, `compta`→`/comptabilite`…), repli `to: null` conservé (routes.meta.js:178) ; persister `taqinor.lastModule` à chaque navigation. Chaque module a déjà son cockpit, rien ne les relie — et l'état de navigation doit survivre au refresh (leçon breadcrumb-URL d'Odoo 18). **Done =** cliquer « RH » depuis `/rh/employes/42` ramène à `/rh`, sections sans cockpit inchangées, tests Breadcrumbs verts. Files: frontend/src/components/layout/routes.meta.js, frontend/src/components/layout/Breadcrumbs.jsx, frontend/src/router/moduleRoutes.jsx. (ROUTINE — S, haiku) (@lane: frontend/shell)
- [x] VX12 — **« Plus » mobile = sélecteur d'apps en grille, pas le tiroir de 100 items.** Remplacer l'ouverture du tiroir sidebar complet par un tiroir compact affichant d'abord la grille de modules (3-4 colonnes, icône + accent VX8, façon apps Odoo mobile) ; taper un module déroule ses items en second niveau, retour possible à la grille. Réutilise `NAV_SECTIONS` + `moduleNavSections`, seule la présentation change. **Done =** « Plus » affiche la grille en premier, navigation deux niveaux fluide, tests Playwright mobile adaptés/verts. Files: frontend/src/components/layout/BottomTabBar.jsx, frontend/src/components/layout/Layout.jsx, frontend/src/index.css. (ROUTINE — M, sonnet) (@lane: frontend/shell) (@after: VX10)
- [x] VX13 — **Une seule recherche : hook partagé GlobalSearch + CommandPalette, pastilles de module.** Extraire `ROUTE`/`LIST_ROUTE`/`TYPE_LABEL` + debounce/état dans `frontend/src/lib/search/entityRoutes.js` + `useEntitySearch(term)`, consommé identiquement par `GlobalSearch.jsx` et `CommandPalette.jsx` (leurs tables divergent DÉJÀ : `bon_commande`/`contrat`/`dossier` connus d'un seul côté, ~150 lignes dupliquées chacun) ; chaque `module.config.jsx` peut déclarer un `searchType` ; pastille d'accent du module d'origine (VX8) sur chaque résultat des deux surfaces. **Done =** les deux composants passent par le même hook (comportement byte-identique aux tests existants), un seul endroit pour ajouter un type d'entité, pastilles visibles avec repli neutre. Files: frontend/src/lib/search/entityRoutes.js (nouveau), frontend/src/components/layout/GlobalSearch.jsx, frontend/src/providers/CommandPalette.jsx. (ROUTINE — M, sonnet) (@lane: frontend/shell) (@after: VX12)
- [x] VX14 — **Centre de notifications : onglets + config déclarative (delta mince, vérifié).** Le panneau de `frontend/src/components/layout/NotificationBell.jsx` groupe DÉJÀ par domaine en sections empilées (« Activités en retard » ~297, « Garanties ≤ 90 j » ~311, « Factures impayées » ~325, « Contrats à renouveler » ~339) — le delta réel est plus mince que prévu : passer ces groupes empilés en 2-3 onglets internes avec compteurs (« Échéances », « Financier », « Activités ») et rendre la config d'onglets DÉCLARATIVE (ajouter un domaine = une entrée de config, pas du JSX copié). Priorité basse dans la lane. **Done =** onglets + compteur total correct (somme), clavier/clic inchangés, tests notifications verts. Files: frontend/src/components/layout/NotificationBell.jsx. (ROUTINE — M, sonnet) (@lane: frontend/shell) (@after: VX13)
- [x] VX15 — **Identité de cockpit : ModuleHero + accent + sparklines dans ModuleDashboard.** Créer `frontend/src/ui/module/ModuleHero.jsx` (titre `--text-h1`, sous-titre, actions, liseré gradient brass→transparent ≤8 % d'opacité coupé sous reduced-motion, slot KPI) et l'adopter sur `frontend/src/pages/Dashboard.jsx:416` (remplace le `<h2>` nu) ; étendre `frontend/src/ui/module/ModuleDashboard.jsx` d'un prop `trend` par stat (mini-sparkline via `ui/charts/KpiSpark`) et d'une pastille d'accent de module (VX8), avec `features/magasin/MagasinCockpit.jsx` en consommateur exemple. Casse la monotonie « 4 boîtes grises copiées-collées sur ~10 modules » ; le seul gradient de marque autorisé à l'intérieur de l'app (« lumière à travers le verre »). **Done =** Dashboard ouvre sur un hero de marque (heading e2e conservé), prop sparkline rétrocompatible, `module.test.jsx` étendu vert. Files: frontend/src/ui/module/ModuleHero.jsx (nouveau), frontend/src/ui/module/ModuleDashboard.jsx, frontend/src/pages/Dashboard.jsx. (ROUTINE — M, sonnet) (@lane: frontend/insight) (@after: VX8)

**C — Le chemin de l'argent (générateur, devis, factures — l'écran le plus stratégique doit être le plus soigné) :**
- [x] VX16 — **Rail de résumé permanent du générateur de devis (desktop).** Ajouter un `<aside className="gen-summary-rail">` sticky (`top: var(--header-h)`, visible dès `lg:`) à côté du `<form>` de `frontend/src/pages/ventes/DevisGenerator.jsx`, affichant en continu : total TTC de l'option retenue, marge indicative (GENERATOR-ONLY — jamais dans un PDF ni côté client), système résumé (kWc/panneaux), boutons Annuler/Créer — aujourd'hui un vendeur scrolle 3 000+ px sans jamais voir le total (`gen-actions-sticky` n'est sticky qu'en mobile, index.css ~2160, à ne pas toucher). Le rail de configurateur « à la Stripe ». **Done =** total + bouton visibles à tout moment du scroll desktop, comportement mobile inchangé, garde `noValidate`/`step="any"` intacte (test existant vert). Files: frontend/src/pages/ventes/DevisGenerator.jsx, frontend/src/index.css. (ROUTINE — M, sonnet) (@lane: frontend/ventes-gen) (@after: VX4)
- [x] VX17 — **Générateur : le cœur visuel passe aux tokens (dark mode réparé sur l'écran le plus stratégique).** Remplacer les hex en dur : `.gen-metric*`/`.lines-table*` dans `frontend/src/index.css` (~1178-1210, 2665-2701) → `var(--card)/var(--muted)/var(--warning)/var(--muted-foreground)` ; dans `DevisGenerator.jsx`, les `style={{color:'#16a34a'}}`/`#b91c1c`/`#b45309` (~2059, 2091-2129) → `text-success`/`text-destructive`/`text-warning` (déjà utilisés ailleurs dans le MÊME fichier) ; le chart Recharts `#1A2B4A`/`#F5A623` (~1810/1816) → tokens de marque. **Done =** `/ventes/devis/nouveau` en thème sombre sans aucun fond clair figé ni texte illisible, vérifié dans les deux thèmes. Files: frontend/src/index.css, frontend/src/pages/ventes/DevisGenerator.jsx. (ROUTINE — S, sonnet) (@lane: frontend/ventes-gen) (@after: VX16)
- [x] VX18 — **Brancher la fonctionnalité fantôme : modèles de devis (DevisPresetPanel).** `frontend/src/pages/ventes/DevisPresetPanel.jsx` (273 lignes, endpoints save-preset/apply-preset/presets complets — QJ16) n'est importé NULLE PART (vérifié) — une réduction directe de friction déjà codée et invisible. L'importer dans `DevisGenerator.jsx` (sous la carte Lignes de Produits ou en tiroir depuis l'en-tête), câbler `onApplied` → `setLines(withKeys(...))`, remplacer son `StatusBadge` local en Tailwind dur (lignes 35-39) par `Badge`/`StatusPill` du kit. **Done =** sauvegarder un devis type et le réappliquer en un clic, testé en clair et sombre. Files: frontend/src/pages/ventes/DevisGenerator.jsx, frontend/src/pages/ventes/DevisPresetPanel.jsx. (ROUTINE — S, sonnet) (@lane: frontend/ventes-gen) (@after: VX17)
- [x] VX19 — **Zéro popup navigateur : éradiquer les `window.alert/confirm/prompt` (~65 appels, 40 fichiers).** Remplacer partout dans `frontend/src/pages` (pires zones : `FactureList.jsx` ~20, `RelancesPage.jsx` 7, `ParametresEntreprise.jsx` 9, `VentesKanban.jsx` 3, stock, sections paramètres…) : résultats/erreurs → `toast.success/error` (pattern DevisList), confirmations destructives → `AlertDialog` (poids de feedback = poids d'action), saisies `prompt()` (export comptable, motifs) → petites `ResponsiveDialog` + `Input`. C'est l'anti-signature : des popups OS non stylées au milieu d'une app de marque. À exécuter EN DERNIER de la vague (touche 40 fichiers — après les lanes écrans pour éviter les conflits ; recoupements vérifiés : ParametresEntreprise.jsx = fichier de VX35, StockList.jsx = VX7/VX33). **Done =** `git grep -E '(^|[^.\w])(confirm|alert|prompt)\('` vide dans `frontend/src/pages` (les appels NUS comptent : FactureList en a 17 nus contre 5 préfixés `window.` — un grep `window.` seul passerait à tort), tests FactureList/DevisList adaptés verts. Files: ~40 fichiers frontend/src/pages/** (commencer par ventes). (ROUTINE — L, sonnet) (@lane: frontend/sweep) (@after: VX21, VX25, VX29, VX31, VX32, VX33, VX35, VX38, VX45, VX63, VX79)
- [x] VX20 — **Fin de la « soupe d'actions » : menus Plus sur DevisList, RelancesPage et BulkActionBar CRM.** DevisList affiche jusqu'à 10 boutons par ligne (~1376-1644), RelancesPage 7, la BulkActionBar CRM 12 : garder 2-3 actions primaires contextuelles visibles (PDF, Envoyer, Accepter/Refuser selon statut) et déplacer le reste dans `DropdownMenu` (déjà utilisé par FactureList.jsx:29 et ListView.jsx:427) ; même traitement pour `frontend/src/pages/crm/leads/BulkActionBar.jsx` (garder Responsable/Étape/Archiver/Export + menu). Anatomie de rangée Linear/Attio — actions révélées, jamais empilées. **Done =** hauteur de ligne stable sans débordement tablette, TOUS les hooks e2e `ap-*` déplacés avec leurs boutons, `DevisList.test.jsx` vert, specs Playwright e2e ADAPTÉES (ouvrir le menu avant de cliquer les `ap-*` déplacés — ils quittent le DOM statique) + gate e2e verte. Files: frontend/src/pages/ventes/DevisList.jsx, frontend/src/pages/ventes/RelancesPage.jsx, frontend/src/pages/crm/leads/BulkActionBar.jsx. (ROUTINE — M, sonnet) (@lane: frontend/ventes-list) (@after: VX7) — DONE 2026-07-11 : PDF/Envoyer/Accepter/Refuser/Générer facture restent visibles sur DevisList, le reste (Éditer, lien interne, variante, design 3D, aperçu, télécharger, BC, chantier, projet, réviser, remise, supérieur, email, supprimer) vit dans UN menu « Plus d'actions » (destructive item pour Supprimer, window.confirm conservé — AlertDialog retiré, plus utilisable proprement dans un DropdownMenuItem). RelancesPage garde Relancer + WhatsApp visibles, menu « Plus » pour Historique/Lettre/Relevé/Relance premium/Exclure. BulkActionBar CRM garde Responsable/Étape/Archiver/Export, menu « Plus » pour Canal/Priorité/Tag/Relance/Planifier activité/Perdu/Restaurer/Supprimer. NOTE — aucun hook e2e réel `ap-*` (data-testid) n'existe sur ces 3 fichiers ni dans les specs Playwright actuelles (`.ap-*` en CSS n'existe que pour l'assignee-picker CRM activities/leads, sans rapport) ; les specs `devis.spec.js`/`receivables.spec.js` ne touchent pas ces boutons de ligne — rien à adapter côté e2e réel. `DevisList.test.jsx` + `DevisListCreerProjet.test.jsx` adaptés pour ouvrir le menu avant de cliquer les actions déplacées (Variante, Design 3D, Copier le lien, Créer projet).
- [x] VX21 — **FactureList à parité de polish avec DevisList (squelette + cockpit trésorerie).** Porter le pattern `DevisTableSkeleton`/`useDelayedLoading` + en-tête stable pendant chargement (DevisList ~39-65, 740-765) vers `frontend/src/pages/ventes/FactureList.jsx` (spinner nu actuel, ~571-577), et remplacer l'unique carte « Encaissé ce mois » (~845) par une rangée de 4 cartes de trésorerie (Encaissé ce mois / Total dû / En retard / À échoir ≤7 j) dérivées des factures déjà chargées — anatomie KPI complète valeur+delta+période, « 4 cartes max, détail sous le pli » (Stripe). **Done =** plus de saut de layout au chargement, un directeur voit la santé de trésorerie d'un coup d'œil, `FactureList.test.jsx` vert. Files: frontend/src/pages/ventes/FactureList.jsx. (ROUTINE — M, sonnet) (@lane: frontend/ventes-list) (@after: VX20) — DONE 2026-07-11 : `FactureTableSkeleton` (8 colonnes) + `useDelayedLoading` portés, en-tête de page (`pageHeader`) désormais toujours visible pendant chargement/erreur (parité DevisList). La carte unique « Encaissé ce mois » devient une rangée de 4 cartes KPI (Encaissé ce mois avec delta vs mois précédent, Total dû, En retard avec nombre de factures, À échoir ≤7 j) — toutes dérivées de `factures` déjà chargé, aucun appel réseau ajouté.

**D — CRM niveau Attio :**
- [x] VX22 — **Une vraie page lead : route `/crm/leads/:id`.** Ajouter la route dédiée qui rend le même `LeadForm` mais adressable : deep-link partageable, F5 rouvre la même fiche (charger via `crmApi.getLead` si pas en mémoire — le `?lead=<id>` actuel dépend du cache de liste), précédent/suivant navigateur fonctionnels, ctrl-clic « ouvrir dans un nouvel onglet » depuis Kanban/Liste ; le flux overlay rapide reste pour le kanban (l'URL se met à jour). L'échelle hover→peek→page d'Attio exige que la « page » existe ; l'état de navigation doit survivre au refresh. **Done =** ouvrir `/crm/leads/42` dans un onglet neuf affiche la fiche sans passer par la liste. Files: frontend/src/router/, frontend/src/pages/crm/leads/LeadsPage.jsx, frontend/src/pages/crm/LeadForm.jsx. (ROUTINE — M, sonnet) (@lane: frontend/crm)
- [x] VX23 — **ChatterTimeline : battre le chatter d'Odoo, pas le sous-imiter.** Remplacer le journal texte plat (`LeadForm.jsx` ~1188-1206) par un composant réutilisable `frontend/src/components/ChatterTimeline.jsx` : regroupement par jour (« Aujourd'hui »/« Hier »/date), `Avatar` par entrée, notes manuelles visuellement distinctes (fond plein) des logs auto de champ (texte discret + icône crayon), pièces jointes récentes injectées dans le fil au lieu d'un onglet séparé. Le chatter est ce qu'Odoo fait le mieux et TAQINOR est aujourd'hui EN DESSOUS ; garder le panneau repliable (l'erreur du chatter toujours-ouvert qui mange l'écran). **Done =** avatars + groupes temporels + distinction note/log visibles, test LeadForm couvrant le rendu. Files: frontend/src/components/ChatterTimeline.jsx (nouveau), frontend/src/pages/crm/LeadForm.jsx. (ROUTINE — M, sonnet) (@lane: frontend/crm) (@after: VX22)
- [x] VX24 — **Anatomie de carte Kanban à 2 niveaux + bandeau résumé de fiche.** Dans `frontend/src/pages/crm/leads/views/LeadCard.jsx` (~112-163) : UNE seule pilule d'alerte prioritaire au premier plan (perdu > rappel > expiré), « Inactif N j » + horloge relégués en pied discret, `ScoreBadge` (extrait de ListView vers `frontend/src/features/crm/ScoreBadge.jsx`) à côté du nom — le score n'existe aujourd'hui QUE dans la vue Liste. Ajouter un `LeadSummaryBar` en tête de `LeadForm.jsx` (~712) : score, montant estimé, prochaine activité, jours depuis dernière modification — le bandeau de faits clés d'Attio. Cartes courtes plafonnées délibérément. **Done =** au plus 2 pilules + score par carte (capture d'un lead cumulant 4 alertes), les 4 faits visibles sans scroller en fiche. Files: frontend/src/pages/crm/leads/views/LeadCard.jsx, frontend/src/features/crm/ScoreBadge.jsx (nouveau), frontend/src/pages/crm/LeadForm.jsx. (ROUTINE — M, sonnet) (@lane: frontend/crm) (@after: VX23)
- [x] VX25 — **MonthGrid partagé + résurrection du calendrier transverse.** Extraire la grille mensuelle (cellules lundi-dimanche, navigation mois, « Aujourd'hui ») en `frontend/src/components/MonthGrid.jsx` paramétré par `renderCell`, puis restyler `frontend/src/pages/CalendarPage.jsx` — le pire écran du CRM : 100 % inline `style={{}}`, ~20 hex codés, boutons `btn btn-light` pré-design-system — sur les mêmes primitives que `leads/views/CalendarView.jsx` (`IconButton`/`Segmented`/tokens sémantiques `--info/--success/--warning`). « Deux calendriers, deux générations de design dans la même app — la preuve la plus nette du gap. » **Done =** plus aucun hex dans CalendarPage, dark mode correct, les deux calendriers importent MonthGrid. Files: frontend/src/components/MonthGrid.jsx (nouveau), frontend/src/pages/CalendarPage.jsx, frontend/src/pages/crm/leads/views/CalendarView.jsx. (ROUTINE — M, sonnet) (@lane: frontend/crm) (@after: VX24)
- [x] VX26 — **Couleurs de stage dérivées des tokens (STAGES.py intact — règle #2 à la lettre).** Ajouter dans `frontend/src/design/tokens.css` les variables `--stage-new/--stage-contacted/--stage-quote-sent/--stage-follow-up/--stage-signed/--stage-cold` dérivées de la palette de marque, et faire pointer `STAGE_COLORS` (`frontend/src/features/crm/stages.js:30-37`), `SCORE_COLORS` (ListView:77-81), `NAVY`/`GOLD` (ChartsView:24-25) et `OWNER_PALETTE` (CalendarView:36-39) vers ces tokens (chaînes `var(--…)` ou résolution `getComputedStyle` pour recharts). Les 6 CLÉS restent importées du module stages aligné STAGES.py — seules les COULEURS changent de source. **Done =** grep hex vide dans les 4 fichiers (hors commentaires), changer un token de marque change visiblement kanban + charts, CI stage-names verte. Files: frontend/src/design/tokens.css, frontend/src/features/crm/stages.js, frontend/src/pages/crm/leads/views/. (ROUTINE — M, sonnet) (@lane: frontend/crm) (@after: VX1)

**E — Cockpits & monitoring vivants :**
- [x] VX27 — **Le cockpit du matin : Dashboard par rôle + bandeau « aujourd'hui ».** Le Directeur, le Commercial et le Technicien SAV voient aujourd'hui EXACTEMENT le même mur de KPI — la lacune la plus stratégique. Brancher un layout par rôle dans `frontend/src/pages/Dashboard.jsx` sur le rôle déjà en store : commercial → « mes leads à relancer / mes devis qui expirent sous 7 j » en tête ; SAV → « mes tickets urgents / SLA en retard » (réutiliser `statusCounts`/`ticketSlaLevel` de `features/sav/ticketStatuses.js`, carte SAV aujourd'hui absente du Dashboard) ; directeur → vue macro actuelle + un métrique héros promu en haut à gauche (pattern F Mercury/Ramp). Ajouter le bandeau compact « 3 interventions aujourd'hui · 2 relances en retard · 1 devis expire » cliquable — aucun nouvel endpoint BACKEND, mais ajouter les fetchs frontend manquants (Dashboard.jsx:187-192 ne charge aujourd'hui ni leads ni tickets SAV — les endpoints existent). **Done =** trois rôles de test affichent des sections de tête différentes, bandeau cliquable correct, test de rendu conditionnel ajouté. Files: frontend/src/pages/Dashboard.jsx. (ROUTINE — L, opus) (@lane: frontend/insight) (@after: VX15)
- [x] VX28 — **Un seul langage de graphique + un seul PageHeader.** Migrer les recharts « à la main » de `Reporting.jsx` (CHART_INFO ~39-49), `Rapports.jsx` (CHART_PRIMARY ~21-23) et `Journal.jsx` (~20-34) vers le kit `frontend/src/ui/charts/` (AreaSansAxe/BarArrondie/ChartTooltip — même easing, mêmes coins, même palette) ; remplacer le composant `Table` local de Rapports.jsx (~64-91) par le `Table` partagé de `pages/reporting/Table.jsx` ; créer `frontend/src/ui/PageHeader.jsx` (titre+sous-titre+actions) et l'adopter sur les 3 idiomes divergents (Dashboard font-display vs `<h2>` nu vs `.page-title` monitoring) sur ~10 écrans. L'incohérence inter-modules est l'erreur Odoo n°6. **Done =** plus aucune constante de couleur recharts locale dans les 3 fichiers, un seul composant Table dans reporting/, PageHeader adopté, e2e headings verts. Files: frontend/src/ui/PageHeader.jsx (nouveau), frontend/src/pages/Reporting.jsx, frontend/src/pages/Rapports.jsx, frontend/src/pages/Journal.jsx. (ROUTINE — M, sonnet) (@lane: frontend/insight) (@after: VX27)
- [x] VX29 — **CommercialDashboard : le restyle « star » de l'écran le plus waouh.** Réécrire `frontend/src/pages/reporting/CommercialDashboard.jsx` — 91 `style={{}}` inline, 13 hex, l'écran le plus daté de l'app — sur les primitives du kit (`Card`/`Badge`/`BarArrondie` pour l'entonnoir au lieu du `<div style={{width: pct%}}>` fait main), et corriger le bug `<EmptyState message="..."/>` (API réelle : `title`/`description` — le texte ne s'affiche probablement pas, ~189/250/283). Son contenu (entonnoir de vélocité par étape, classement commerciaux, gains/pertes par canal) est le candidat parfait au « investor demo gasp » une fois restylé. **Done =** zéro `style={{}}` restant, EmptyState rendu, export xlsx fonctionnel, dark mode correct. Files: frontend/src/pages/reporting/CommercialDashboard.jsx. (ROUTINE — M, sonnet) (@lane: frontend/reporting)
- [x] VX30 — **Le mur de flotte vivant (cartes par centrale + pouls temps réel).** Sur `frontend/src/pages/monitoring/FleetPage.jsx` : un mode grille de cartes par installation (référence, badge statut vert/orange/rouge dérivé du PR déjà calculé ~99-105, kWc, production, mini-sparkline `KpiSpark`) basculable avec le tableau via `Segmented` ; un badge de fraîcheur « Actualisé il y a X min » (extraire le `timeAgo` de TicketsPage.jsx:66-73 en util partagé) + auto-poll léger 5 min sur les écrans monitoring — via `useVisibilityAwarePolling` (VX56) si livré, jamais un `setInterval` nu qui polle un onglet caché (@coord VX56) ; l'état « stale/hors-ligne » visuellement DISTINCT de « production 0 » (un « 0 » peut être un nuage OU un onduleur mort — ils ne doivent jamais se ressembler). **Done =** bascule table/cartes, cartes cliquables vers OmAnalytics, fraîcheur visible et mise à jour, stale ≠ zéro. Files: frontend/src/pages/monitoring/FleetPage.jsx, frontend/src/pages/monitoring/Co2Page.jsx, util timeAgo partagé. (ROUTINE — L, sonnet) (@lane: frontend/monitoring)
- [x] VX31 — **SAV en boîte de réception : split-view liste + détail.** Sur desktop ≥1280px, remplacer le `Sheet` plein-tiroir de `TicketDetail` (`frontend/src/pages/sav/TicketsPage.jsx:453-848`) par un panneau latéral persistant à côté de la DataTable — cliquer un autre ticket met à jour le panneau sans réouverture, la liste reste visible (pattern inbox Linear/Plain) ; `Sheet` conservé en fallback mobile, toutes les `CollapsibleSection` gardées à l'identique. **Done =** sur grand viewport la sélection n'ouvre plus de tiroir, mobile inchangé, `TicketsPage.test.jsx`/`TicketCalendarView.test.jsx` verts. Files: frontend/src/pages/sav/TicketsPage.jsx. (ROUTINE — L, sonnet) (@lane: frontend/sav)

**F — Opérations (les îlots non migrés) :**
- [x] VX32 — **CartePage + MapView rejoignent le design system (la « control room » géographique).** Remplacer tous les `style={{...}}` inline et hex de `frontend/src/pages/CartePage.jsx:84-128` par tokens + composants (`Badge`/`Segmented` pour la légende cliquable, `Select` Radix pour le filtre au lieu du `<select>` natif fond `#fff` figé même en sombre) ; dans `frontend/src/components/MapView.jsx`, thémer les tuiles pour le dark mode (filtre CSS `invert()/hue-rotate()` sur le tileLayer — pattern standard, zéro dépendance) et enrichir le popup d'un vrai bouton « Ouvrir la fiche » (`Button size="sm"`). « L'îlot visuel le plus net de la lane — un prototype 2019 sur l'écran qui devrait incarner la salle de contrôle. » **Done =** zéro `style={{` hors hauteur du conteneur Leaflet, dark mode sans fond blanc figé, légende alignée sur le reste de l'app. Files: frontend/src/pages/CartePage.jsx, frontend/src/components/MapView.jsx. (ROUTINE — M, sonnet) (@lane: frontend/carte)
- [x] VX33 — **Le Pilotage stock devient la tour de contrôle qu'il prétend être.** Ouvrir `PilotageStock` par défaut (aujourd'hui replié derrière un bouton secondaire, StockList.jsx ~1058-1060), migrer ses 4 `SectionRapport` du `<table>` HTML brut (`frontend/src/pages/stock/PilotageStock.jsx:39-74`) vers mini-`DataTable`, ajouter deux graphiques du kit `ui/charts` (barres horizontales « top 5 à réapprovisionner », donut rotation actif/ralenti/immobile) ; en bonus la mini-jauge « santé catalogue » (% avec prix / % avec SKU depuis `noPriceCount`/`noSkuCount`, StockList.jsx ~753-754) au-dessus du rail de catégories. **Done =** pilotage visible par défaut avec 2 charts du kit, jauge santé rendue, tests stock verts. Files: frontend/src/pages/stock/PilotageStock.jsx, frontend/src/pages/stock/StockList.jsx. (ROUTINE — L, sonnet) (@lane: frontend/stock) (@after: VX7)

**G — Fondation, délice, mobile, voix :**
- [x] VX34 — **Login signature (le premier pixel de la marque).** Garder le moment de marque (fond wordmark bondissant) mais le faire entrer dans le système : couleurs `#1863DC`/`#F5C100`/`#050e1f` → tokens OKLCH de `design/tokens.css`, emojis 🙈/👁️/⚠️ → `Eye`/`EyeOff`/`AlertCircle` lucide, `BouncingBackground` statique sous `prefers-reduced-motion`. (PAS de lookup société-par-email AVANT authentification — vecteur d'énumération de comptes + exigerait un endpoint backend nouveau ; si on veut le nom de la société, l'afficher dans la transition POST-login.) **Done =** mêmes teintes via tokens, reduced-motion respecté, aucun emoji-icône restant, flow 2FA inchangé. Files: frontend/src/pages/Login.jsx. (ROUTINE — M, sonnet) (@lane: frontend/login)
- [x] VX35 — **Paramètres : de 22 onglets plats à une vraie architecture d'information.** Remplacer le `TabsList` plat scrollable (`frontend/src/pages/parametres/peConstants.js:27-50`, rendu ParametresEntreprise.jsx ~795-803) par une sidebar verticale groupant les clés en 5-6 familles (Général / Ventes & Devis / Terrain & Stock / Équipe & Sécurité / Automatisation / Avancé — champ `group` par tab), la recherche existante (~L790) en tête de sidebar (`searchSettings` inchangé). Settings-as-sitemap ≤2 niveaux (Stripe/Linear) ; jamais gater un réglage courant derrière un mode caché (erreur Odoo n°3). **Done =** les clés d'onglets inchangées (aucune renommée), la recherche saute au bon endroit, tests sections verts sans modification. Files: frontend/src/pages/parametres/peConstants.js, frontend/src/pages/parametres/ParametresEntreprise.jsx, frontend/src/pages/parametres/SettingsSidebar.jsx (nouveau). (ROUTINE — M, sonnet) (@lane: frontend/parametres)
- [x] VX36 — **L'onboarding sort de sa cachette (bannière Dashboard + first-run).** La checklist « Prise en main » (OnboardingSection, FG16 : profil société / premier produit / inviter un coéquipier) est enterrée dans l'onglet 1 de 24 des Paramètres — invisible au premier login. Extraire les 3 étapes dans un hook `useOnboardingSteps()` partagé et afficher une `OnboardingBanner` (progression + lien direct) en haut de `frontend/src/pages/Dashboard.jsx` tant que `doneCount < steps.length`, masquable définitivement (« Ne plus afficher », persisté par société). « Créer un artefact réel dans la première minute. » (NB vérifié : OnboardingSection calcule ses étapes via `api.get('/users/')` + stock/profil — le hook partagé refera ces appels sur le Dashboard.) **Done =** bannière au premier login, disparaît après complétion/refus, au plus les MÊMES appels que l'onglet Prise en main (une seule fois, réutilisant le store quand présent). Files: frontend/src/pages/Dashboard.jsx, frontend/src/components/OnboardingBanner.jsx (nouveau), frontend/src/features/onboarding/onboardingHelpers.js (nouveau). (ROUTINE — S, sonnet) (@lane: frontend/insight) (@after: VX28)
- [x] VX37 — **L'IA qui « pense » : streaming visuel + preuve lisible par un humain.** Dans `frontend/src/pages/ia/AgentChat.jsx`, remplacer le loader 3-points statique (~360-371) par une révélation incrémentale du texte (le texte complet est déjà côté client — `requestAnimationFrame` mot à mot, aucun changement backend), et rendre la preuve consommable par un non-développeur : quand le payload agent porte des lignes structurées, un mini-tableau de données inline à la place du seul `<details><pre>` SQL brut. La sensation « produit IA 2026 » vient du reveal progressif + citation de données. **Done =** `AgentChat.test.jsx`/voice verts, `data-testid` proposal/result-card inchangés, reduced-motion = texte instantané. Files: frontend/src/pages/ia/AgentChat.jsx. (ROUTINE — M, sonnet) (@lane: frontend/ia)
- [x] VX38 — **Admin cohérent : RolesManagement + documents GED sur DataTable, matrice de permissions.** Porter le `<table>` fait main de `frontend/src/pages/admin/RolesManagement.jsx:489-579` et le tableau documents legacy de `frontend/src/features/ged/GedNavigator.jsx:306-333` vers le moteur `DataTable` (le même que UsersManagement un écran à côté) ; transformer l'éditeur de rôle (12 cartes de checkboxes) en matrice modules × actions (Voir/Créer/Modifier/Supprimer/Exporter, « — » si absent), logique `buildGroups`/`togglePerm` inchangée ; en GED, fil d'Ariane Armoire›Dossier et icônes par type de fichier (`FileImage`/`FileSpreadsheet`… lucide). L'audit « qui peut faire quoi » scannable. **Done =** aucune perte fonctionnelle, tri/recherche gagnés, tests admin/GedNavigator adaptés verts. Files: frontend/src/pages/admin/RolesManagement.jsx, frontend/src/features/ged/GedNavigator.jsx. (ROUTINE — L, sonnet) (@lane: frontend/admin)
- [x] VX39 — **OCR : source et extraction côte à côte + correction inline.** Dans `AnalyseTab` (`frontend/src/pages/ia/OcrUpload.jsx:68-378`), afficher le document source (`URL.createObjectURL(currentFile)`) en aperçu à gauche et la table de champs extraits ÉDITABLE à droite (chaque valeur → `Input` inline, « Valider et enregistrer » envoie les valeurs corrigées) — la boucle de confiance vérifier-puis-corriger est le standard de tout produit OCR sérieux (Klippa/Rossum) et manque totalement. **Done =** la sauvegarde envoie les valeurs corrigées, un test couvre l'édition d'un champ avant sauvegarde. Files: frontend/src/pages/ia/OcrUpload.jsx. (ROUTINE — M, sonnet) (@lane: frontend/ia)
- [x] VX40 — **Le délice mesuré : célébration « devis signé » + états vides illustrés.** Une SEULE célébration dans toute l'app : au passage `envoye→accepte` d'un devis (rare, significatif, lié au revenu), un burst CSS-only (spans absolus animés translate/rotate/fade, AUCUNE lib confetti) autour du toast sonner existant, une fois par transition, jamais au rechargement, statique sous reduced-motion (règle Asana : honorer le rare, jamais gamifier la routine). Et une variante `illustrated` d'`frontend/src/ui/EmptyState.jsx` : pictogramme solaire SVG inline (panneau/soleil stylisé, tons brass/lune) ou cluster d'icônes lucide 48-64px basse opacité, adoptée sur les 4-5 empty states les plus vus (leads, devis, catalogue, GED, carte). **Done =** célébration visible une fois sur acceptation, empty states illustrés en clair+sombre, reduced-motion = toast seul. Files: frontend/src/ui/EmptyState.jsx, frontend/src/ui/celebrate.js (nouveau), point d'appel SigneDialog/DevisList. (ROUTINE — M, sonnet) (@lane: frontend/ui) (@after: VX20)
- [x] VX41 — **Craft data-viz : palette catégorielle de marque, comparaison de période, annotations.** Étendre `frontend/src/ui/charts/chart-theme.js` d'une échelle catégorielle dérivée de la marque (brass, azur, nuit-soft, lune + accents sémantiques) pour les séries multiples (elles retombent aujourd'hui sur un seul ton) et d'un style de grille signature (pointillés très légers, horizontaux seuls, pas de ligne d'axe — data-ink Tufte) ; ajouter la série « période précédente » en pointillé togglable sur le CA mensuel de `Dashboard.jsx` (~484-492) et `Reporting.jsx` (~327-349) (mêmes données décalées, zéro appel API — une référence superposée bat deux graphiques) ; supporter `ReferenceLine` annotée pour les événements (marqueur maintenance sur une courbe de production). **Done =** un chart multi-séries montre la palette distincte en clair+sombre, comparaison togglable avec légende claire, test chart-theme à jour. Files: frontend/src/ui/charts/chart-theme.js, frontend/src/ui/charts/ChartFrame.jsx, frontend/src/pages/Dashboard.jsx, frontend/src/pages/Reporting.jsx. (ROUTINE — M, sonnet) (@lane: frontend/insight) (@after: VX36)
- [x] VX42 — **Terrain un-tap : appeler/naviguer sur Ma journée + FAB + retour haptique.** Trois gestes natifs à coût quasi nul : (1) deux boutons directs ≥44px (téléphone, navigation maps universelle) sur chaque carte de `frontend/src/pages/interventions/MaJourneePage.jsx:78-112` — l'action la plus fréquente d'un technicien garé est aujourd'hui à 3 taps dans l'onglet Trajet ; remplacer les 9 `TabsTrigger` icône-seule par un rail scrollable icône+libellé court avec bandeau « Prochaine action » (pattern `ch6-next-action` de ChantierGateTimeline) ; (2) un `frontend/src/ui/FloatingActionButton.jsx` (fixed, safe-area + hauteur BottomTabBar) posé sur NumeriserPage, leads mobile (« Nouveau lead ») et Ma journée (« Photo rapide ») — le pouce vit dans le tiers bas de l'écran ; (3) `navigator.vibrate?.(10)` défensif après capture photo validée, signature, changement de statut, scan réussi (`CameraCapture.jsx`, `SignaturePad.jsx`, `InterventionsPage.jsx`, `useBarcodeScanner.js`). **Done =** boutons visibles sans ouvrir le sheet (masqués si donnée absente), FAB sous 768px au-dessus de la tab bar, vibration silencieuse si API absente, tests Playwright mobile. Files: frontend/src/pages/interventions/MaJourneePage.jsx, frontend/src/ui/FloatingActionButton.jsx (nouveau), + points haptiques cités. (ROUTINE — L, sonnet) (@lane: frontend/terrain)
- [x] VX43 — **Gestes natifs : swipe-to-action, pull-to-refresh, sheets cohérents.** (1) Swipe horizontal maison (`touchstart/move/end`, seuil de distance anti-scroll, zéro dépendance) sur `LeadCard.jsx` et les cartes mobiles du `DataTable` (`data-dt-cards`, prop `swipeActions` rétrocompatible) révélant Appeler/WhatsApp ≥44px — LE geste iOS attendu, les liens tel:/wa.me existent déjà (LeadCard.jsx:79-80) mais en texte 12px noyé. (2) Pull-to-refresh maison (hook `usePullToRefresh`, transform CSS quand scroll=0) sur Ma journée, Interventions et le kanban leads — `overscroll-behavior: contain` a coupé le rubber-band sans rien mettre à la place. (3) Aligner les sheets terrain (`MaJourneePage` `side="right"`, InterventionsPage) sur le bottom-sheet mobile via `ResponsiveDialog`/`Sheet side="bottom"` + glisser-vers-le-bas-pour-fermer dans `frontend/src/ui/Sheet.jsx`, et un repli « changer le statut au menu » sans drag sur `InterventionCard` sous 768px. Ressort sous le doigt uniquement. **Done =** swipe sans conflit avec le scroll vertical, pull relance les fetch existants, sheets terrain s'ouvrent du bas et se ferment au glissé, gate Playwright mobile verte. Files: frontend/src/pages/crm/leads/views/LeadCard.jsx, frontend/src/ui/datatable/DataTable.jsx, frontend/src/ui/usePullToRefresh.js (nouveau), frontend/src/ui/Sheet.jsx, frontend/src/pages/interventions/. (ROUTINE — L, sonnet) (@lane: frontend/terrain) (@after: VX42, VX45)
- [x] VX44 — **Photos chantier en rafale + partage natif WhatsApp.** (1) Porter le pattern multi-pages de `NumeriserPage.jsx` (`pages: [{id, file, rotation}]`, vignettes retirer/tourner avant envoi groupé) vers `PhotosPanel` de `frontend/src/features/installations/InterventionFieldExecution.jsx` — un technicien prend 3-6 photos de suite sans rouvrir la caméra ; enrichir `frontend/src/pages/installations/ChantierPhotos.jsx` d'un compteur de complétion (« 12 photos · 3 phases couvertes ») + badge sur les phases vides via `photos_obligatoires_manquantes` déjà exposé. (2) Préférer `navigator.share({files})` (Web Share API, iOS 15+) au lien de téléchargement pour envoyer le PDF de devis/rapport droit dans WhatsApp, avec repli téléchargement — et généraliser les liens `wa.me` PRÉ-REMPLIS contextuels sur les actions « contacter le client ». N'ajoute AUCUN chemin PDF : on partage le PDF `/proposal` existant (règle #4). **Done =** rafale + réordonnancement avant upload vers l'endpoint existant, share sheet natif quand disponible, messages wa.me pré-remplis en français. Files: frontend/src/features/installations/InterventionFieldExecution.jsx, frontend/src/pages/installations/ChantierPhotos.jsx, frontend/src/pages/ventes/DevisList.jsx (action partager). (ROUTINE — M, sonnet) (@lane: frontend/terrain) (@after: VX43, VX40)
- [x] VX45 — **La voix TAQINOR : microcopie FR premium + fin des emojis-icônes.** Deux passes fines : (1) copy-only sur les toasts/dialogs/empty-states les plus visibles au registre Doctolib — la chaleur par la clarté (« Devis enregistré. » pas « Opération réussie ! » ; erreurs = quoi + prochaine étape ; chargements nommés « Génération du PDF… ») + une section « Voix & microcopie » documentée dans `frontend/src/pages/ui/UIShowcase.jsx` ; (2) remplacer les emojis fonctionnels 💡🏠⚡📝📎🕐📈👤💧 de `frontend/src/pages/crm/LeadForm.jsx` et `LeadCard.jsx` (+ boutons de LeadsPage ⚡🔀) par les lucide équivalents (`Zap`, `Home`, `FileText`, `Paperclip`, `Clock`, `Phone`, `MessageCircle`…) — le rendu emoji varie par OS et casse le système d'icônes. **Done =** titres de section avec prop `icon` lucide, aucun emoji fonctionnel restant dans crm/, 6+ chaînes clés relues, e2e textes verts. Files: frontend/src/pages/crm/LeadForm.jsx, frontend/src/pages/crm/leads/views/LeadCard.jsx, frontend/src/pages/ui/UIShowcase.jsx. (ROUTINE — S, haiku) (@lane: frontend/crm) (@after: VX25)

**H — Compléments (critique de complétude Fable, 2026-07-07 — deux espaces blancs confirmés absents de TOUS les plans) :**
- [x] VX46 — **« Mes préférences » : un centre de personnalisation par utilisateur.** La personnalisation existe mais est éparpillée et sans surface : thème (ThemeToggle header), apps épinglées (VX10, localStorage), densité (tokens F120 sans aucune UI), vues sauvegardées DataTable (par table), module d'atterrissage au login (n'existe pas). Créer une petite surface « Mes préférences » (entrée du menu utilisateur du header) regroupant : thème clair/sombre/système, densité par défaut (compact/confort/spacieux appliquée aux DataTable), module d'atterrissage au login (liste depuis `moduleConfigs`, réutilise `taqinor.lastModule` de VX11), réduction de mouvement (override app du media query) — persistance `localStorage` par utilisateur (motif `COLLAPSE_KEY`), AUCUN nouvel endpoint backend. **Done =** chaque préférence persiste au rechargement, le module d'atterrissage redirige au login, la densité s'applique aux tables, tests de la logique pure. Files: frontend/src/pages/preferences/ (nouveau, ou section du menu utilisateur), frontend/src/components/layout/Header.jsx. (ROUTINE — M, sonnet) (@lane: frontend/shell) (@after: VX14)
- [x] VX47 — **Aide contextuelle intégrée : popovers « ? » sur les écrans difficiles.** L'overlay `?` (I138) n'explique que les raccourcis et `/ui` est développeur-facing ; aucun écran métier n'explique ses concepts à un nouvel employé. Créer un composant `HelpTip` (petit `IconButton` « ? » discret + `Popover` du kit, contenu FR concis de 2-4 phrases, jamais de doc externe) et le poser sur les 5-6 zones les plus dures : grille d'écriture comptable (débit=crédit), assistant de paie (review-before-commit), gates de chantier (bloquant vs consultatif), score de lead (d'où vient le chiffre — pose VX24), distributeur/tranches du générateur de devis, et l'écran Applications quand ODX5 livrera. **Done =** `HelpTip` réutilisable + ≥5 poses réelles, aucun re-layout au clic, tests de rendu. Files: frontend/src/ui/HelpTip.jsx (nouveau), les écrans cités. (ROUTINE — M, sonnet) (@lane: frontend/ui) (@after: VX40)

---

**ROUND 2 (2026-07-08) — « le meilleur dans TOUS les aspects » : perfection appareils, vitesse, résilience, locale, portes CI.**
*Le fondateur a challengé : « êtes-vous sûrs qu'avec ces tâches ce sera le meilleur ? je veux le meilleur dans TOUS
les aspects, y compris marcher parfaitement sur téléphones et ordinateurs ». Réponse honnête : VX1-47 rend l'app la
plus belle et la mieux organisée — mais « belle » et « marche parfaitement partout » sont deux chantiers. Un second
balayage (11 agents : matrice appareils/Safari, performance réelle, résilience, locale, surfaces secondaires, portes
CI + recherche best-practices + carte anti-duplication + synthèse Fable) a trouvé des CASSES réelles prouvées dans le
code : sur iPhone Safari AUCUN PDF ne s'ouvre (window.open après un await = bloqué en silence, ~10 écrans) et la CI
mobile ne teste que Chrome donc ne peut pas l'attraper ; au-delà de 100 lignes les listes stock/devis/factures/clients
et les KPI du Dashboard MENTENT (troncature silencieuse page 1 DRF) ; le formulaire de devis (20 min de saisie) n'a
ni brouillon ni garde de sortie ; la liste factures sur téléphone empile des valeurs SANS étiquettes ; le sélecteur
de langue promet EN/AR mais ~2 % de l'app est traduite ; les emails partent en texte brut sans logo ; zéro style
d'impression. VX48-82 répare tout cela ET installe les portes CI (WebKit/iPad/zoom/régression visuelle/axe dynamique)
pour que « parfait » le RESTE. Dédupliqué contre YHARD7/8, YTEST, YAPIC, YDATA, FG386, QPERF1 (chacun cité là où on
s'y adosse). Les vérifs de l'orchestrateur ont corrigé les chemins des slices (`features/*/store/*Slice.js`).*

*Coordination avec le **Groupe ARC** (PLAN.md, ajouté 2026-07-08 via PR #333 — socle plateforme) : ARC a dédupliqué
contre VX1-47 nommément ; les points de contact round 2 sont (a) **ARC49/ARC53** (DevisList/FactureList → moteur
DataTable) possèdent désormais la migration que le NE PAS FAIRE round 1 différait — elles doivent atterrir APRÈS
les tâches VX touchant ces fichiers (VX7/20/21/40/44/48/50/52/63/79/80) et préserver leurs comportements ;
(b) **ARC45** (`useResource` fetch/état mutualisé) est la généralisation architecturale des fixes ciblés VX54/55/67 —
les fixes passent d'abord, ARC45 les absorbe ; (c) **ARC39** (plus d'email brut interne, routage notifications) est
complémentaire de VX76 (le TEMPLATE que les deux goulots rendent).*

**I — Cassé AUJOURD'HUI sur téléphone / Safari / tactile :**
- [x] VX48 — **[BUG iOS] Ouvrir tous les PDF via un onglet pré-ouvert AVANT l'await (le bug le plus grave du parc).** Safari iOS bloque en silence tout `window.open()`/clic programmatique qui suit un `await` : aujourd'hui sur iPhone, AUCUN PDF ne s'ouvre depuis l'app (prouvé sur ~10 écrans). Créer `openPdfInGesture()` dans `frontend/src/utils/pdfBlob.js` : ouvrir synchroniquement un onglet vide dans le handler de tap, puis `w.location = objectUrl` quand le blob arrive. Câbler dans `DevisList.jsx:494-496`, `LeadDevisPanel.jsx:214-215`, `features/contrats/LocationPage.jsx:84` + `ContratDetail.jsx:86`, `stock/StockList.jsx:681`, `ReceptionsFournisseur.jsx:279`, `features/rh/EmployeDetail.jsx:125`, `installations/InstallationDetail.jsx:603`, `OmReportPage.jsx:61` ; dans `FactureList.jsx`, remplacer le CLONE LOCAL `openPdfBlob` (`:106`, utilisé aux `:357/:417/:456/:519`) par le helper partagé — et traiter aussi le lien de paiement `:503` (un `window.open` après await, pas un PDF) ou l'exclure explicitement avec raison. **NE PAS régresser QG1** (plainte fondateur « second clic » — l'auto-open `DevisList.jsx:593-622` reste l'expérience par défaut) : tenter l'auto-open existant D'ABORD et n'afficher le toast d'action « PDF prêt — Ouvrir » (tap = geste frais) QUE quand l'ouverture est bloquée (détection null/fenêtre-inerte fournie par VX49). **Done =** `pdfBlob.test` couvre le helper (geste→onglet, blocage→toast) ; l'auto-open desktop est inchangé (test QG1 vert) ; zéro changement au rendu PDF ni à `/proposal` (règle #4 — déclenchement client uniquement). La preuve WebKit rouge/vert vit dans VX68. Files: frontend/src/utils/pdfBlob.js + les écrans cités. (ROUTINE — M, opus : chemin de l'argent) (@lane: frontend/pdf-open) *(@coord VX20/VX44/VX63/VX79/VX80 touchent DevisList/FactureList — rebase.)*
- [x] VX49 — **Détection réelle du blocage popup + gestion d'erreur des ~49 téléchargements blob.** Durcir `ouvrirPdfBlob` (`pdfBlob.js:4-11`, vérifié) : Safari renvoie parfois un objet fenêtre inerte non-null → tester `w == null || w.closed || typeof w.closed === 'undefined'` et afficher un toast d'action « Ouverture bloquée — Télécharger le PDF » au lieu d'échouer en silence (aujourd'hui seul `null` déclenche le repli). Au même passage, envelopper les téléchargements blob sans gestion d'erreur (~49 sites, patron `URL.createObjectURL`) d'un `try/catch` → toast FR + `revokeObjectURL` en `finally` (fuite mémoire sur échecs répétés). **Done =** vitest : `window.open` renvoyant `null` PUIS un objet inerte déclenche le repli dans les deux cas ; un blob invalide produit un toast et zéro URL orpheline. Files: frontend/src/utils/pdfBlob.js, frontend/src/utils/downloadBlob.js. (ROUTINE — S, sonnet) (@lane: frontend/pdf-open) (@after: VX48)
- [x] VX50 — **[BUG mobile] `data-label` sur les tables financières + garde CI anti-régression.** Sous 768px `.data-table` se replie en cartes qui n'affichent le nom du champ que via `content: attr(data-label)` — or `FactureList.jsx` (tables ~770 et ~955, grep vérifié : ZÉRO data-label) et `RelancesPage.jsx:265` n'en ont aucun : sur iPhone une facture est une pile de valeurs nues. Ajouter `data-label` sur chaque `<td>` (patron DevisList), `m-hide` sur les colonnes décoratives ; puis un test statique `data-label.guard.test.js` (fs+regex, zéro dépendance) qui échoue si un fichier de `pages/**` contenant `className="data-table"` a des `<td>` mais zéro `data-label`. **Done =** Playwright mobile 390px sur `/ventes/factures` et `/ventes/relances` : au moins une carte affiche un libellé visible ; la garde est rouge avant le fix, verte après. Files: frontend/src/pages/ventes/FactureList.jsx, frontend/src/pages/ventes/RelancesPage.jsx, frontend/src/ui/datatable/data-label.guard.test.js (nouveau). (ROUTINE — S, haiku) (@lane: frontend/ventes-list) (@after: VX21) — DONE 2026-07-11 : `data-label` ajouté sur chaque `<td>` de `FactureRow` (Client/Émission/Échéance/Total TTC/Statut) + la mini-table avoir (Désignation/Qté facturée/Qté à créditer), et sur `RelancesPage` (Client/Échéance/Dû/Retard/Niveau, `m-hide` sur Âge/Relances décoratifs). Garde `data-label.guard.test.js` (Node natif, `node --test`, zéro dépendance) scanne tout `pages/**` ; confirmée rouge (2 offenders détectés) puis verte après le fix. Le scan a aussi trouvé 2 fichiers préexistants avec le même bug hors périmètre de cette tâche (`admin/TenantsConsole.jsx`, `ventes/VentesKanban.jsx`) — whitelistés explicitement dans la garde avec commentaire + tâche de suivi spawnée (task_b32ff05e) pour les corriger séparément.
- [x] VX51 — **Le champ focalisé ne passe plus SOUS le clavier iOS (VisualViewport).** `grep visualViewport` = néant : sur LeadForm/DevisGenerator, un champ bas de page reste caché derrière le clavier iOS — on tape sans voir. Créer `frontend/src/hooks/useKeyboardAwareScroll.js` : sur `visualViewport` `resize`/`scroll`, si `document.activeElement` est sous le bord du clavier → `scrollIntoView({block:'center'})` (lecture en `requestAnimationFrame`) ; no-op silencieux si l'API est absente. Monter dans LeadForm + DevisGenerator. **Done =** Playwright WebKit : focus d'un champ bas + réduction simulée du viewport → le champ reste dans le cadre — rouge avant, vert après ; vitest no-op sans API ; noté que le clavier RÉEL reste un contrôle manuel. Files: frontend/src/hooks/useKeyboardAwareScroll.js (nouveau), frontend/src/pages/crm/LeadForm.jsx, frontend/src/pages/ventes/DevisGenerator.jsx. (ROUTINE — M, sonnet) (@lane: frontend/forms) (@after: VX62, VX24)
- [x] VX52 — **Les avertissements de conformité en `title=` seul deviennent visibles au tactile.** Quatre informations légales/critiques de `FactureList.jsx` ne vivent QUE dans l'attribut `title` (survol souris) : « Mentions légales manquantes (Art. 145) » (~1018), l'édition d'échéance (~1040), le statut de télédéclaration (~1066), « Facture échue » (~1086) — sur iPhone/iPad l'utilisateur ne peut PAS les lire. Badge mentions → `Popover` Radix tapable ; échéance → bouton à label accessible ; télédéclaration/échue → texte explicite dans la carte mobile. Étendre si le grep retrouve le même patron ailleurs. **Done =** Playwright mobile : taper le badge révèle la liste sans survol ; `getByText` trouve la télédéclaration sans hover ; hooks e2e intacts. Files: frontend/src/pages/ventes/FactureList.jsx. (ROUTINE — S, sonnet) (@lane: frontend/ventes-list) (@after: VX50)
- [x] VX53 — **Balayage compat mécanique : garde `@media (hover:hover)`, dvh d'AgentChat, `loading="lazy"`, feedback clipboard.** En une passe : (1) envelopper les `:hover` porteurs d'affordance de `index.css` + `records-panels.css` (~85 non gardés) dans `@media (hover: hover)` avec état permanent en pointeur grossier — jamais gater l'UNIQUE chemin d'une action derrière un survol ; (2) `AgentChat.jsx` : `h-[calc(100vh-7rem)]` → équivalent dvh (la barre d'URL iOS le rétrécit) ; (3) `loading="lazy"` sur les ~22 `<img>` hors-écran (GED/pièces jointes/KB) ; (4) toast succès/échec sur les copies presse-papiers silencieuses. NE PAS toucher les révélations que VX7 re-pèse (design) — ici seule la joignabilité tactile compte. **Done =** projet tactile (VX68) : les actions autrefois hover-only sont atteignables sans survol ; grep des `:hover` non gardés ≈ 0 hors liste blanche ; AgentChat ne déborde plus. Files: frontend/src/index.css, frontend/src/styles/records-panels.css, frontend/src/pages/ia/AgentChat.jsx + les `<img>` cités. (ROUTINE — M, sonnet) (@lane: frontend/css-compat) (@after: VX7)

**J — Vitesse réelle sur 3G/4G marocaine (et chiffres JUSTES) :**
- [x] VX54 — **[BUG données] Fin de la troncature silencieuse à 100 lignes + pagination PARALLÈLE partout.** Le bug de données le plus grave du frontend : `fetchProduits`/`fetchDevis`/`fetchFactures`/`fetchClients` prennent `payload.results` de la page 1 DRF (PAGE_SIZE=100) et jettent le reste (vérifié : `features/stock/store/stockSlice.js:190/215/225/233` + équivalents ventes/crm) — StockList, DevisList, FactureList ET les KPI/graphiques du Dashboard sont FAUX dès 101 enregistrements, sans indicateur. Corriger : page 1 → lire `count`, puis `Promise.all` borné et concaténer en ordre — concurrence ~20 par défaut MAIS **~3-5 MAX pour les DEVIS** tant que QPERF1 (N+1 backend : ~38-109 requêtes SQL PAR page de devis) n'est pas corrigé, sinon ~20 pages parallèles = ~2 000 requêtes SQL quasi simultanées auto-infligées au Postgres à chaque montage de DevisList (@coord QPERF1 — relever la borne quand il atterrit). Au même passage, corriger les QUATRE while sériels identiques : `fetchLeads` (`features/crm/store/crmSlice.js:49`, vérifié), `installationsSlice.js:8-20`, `sav/ticketsSlice.js:8-24` et `sav/equipementsSlice.js` — les écrans des TECHNICIENS TERRAIN gèlent plusieurs secondes à 250-500 ms de RTT — même forme parallèle bornée. **Done =** vitest slices : payload final = total d'une réponse multi-pages mockée ; test timing : les pages 2/3 partent sans s'attendre ; la borne devis ≤5 est testée ; vérif Slow-3G : requêtes concurrentes, pas un escalier. Files: frontend/src/features/stock/store/stockSlice.js, frontend/src/features/ventes/store (slices devis/factures), frontend/src/features/crm/store/crmSlice.js, frontend/src/features/installations/installationsSlice.js, frontend/src/features/sav/ticketsSlice.js + equipementsSlice.js. (ROUTINE — M, sonnet) (@lane: frontend/data)
- [x] VX55 — **Discipline réseau : timeout axios global + annulation des requêtes obsolètes.** Aucun `timeout` sur l'instance axios (`api/axios.js`, vérifié) et ZÉRO `AbortController` dans l'app : sur 3G qui cale, un écran gèle indéfiniment, et une réponse tardive peut écraser l'état d'un AUTRE écran après navigation. Ajouter `timeout: 20000` + `ECONNABORTED` dans l'intercepteur → toast FR « La connexion a expiré » distinct de l'échec générique ; câbler l'annulation via `createAsyncThunk` `{signal}` + `thunk.abort()` au cleanup d'effet sur LeadsPage, DevisList, ClientList (RTK natif, zéro dépendance). **Done =** vitest : requête jamais résolue → interception à 20 s ; monter/démonter LeadsPage → `meta.aborted === true` ; deux requêtes rapprochées → l'état affiché = la plus récente DEMANDÉE. Files: frontend/src/api/axios.js, les 3 écrans cités. (ROUTINE — M, sonnet) (@lane: frontend/data) (@after: VX54)
- [x] VX56 — **NotificationBell cesse de poller un onglet caché.** `NotificationBell.jsx:140-152` installe deux `setInterval` (30 s + 3 min) sans écoute `visibilitychange` — radio/batterie/données gaspillées sur le 4G des techniciens, alors que le patron correct existe dans `useChatPolling.js:91-104`. Extraire un hook `useVisibilityAwarePolling` partagé (stop caché, refresh immédiat au retour) utilisé par les deux features. Ne touche PAS le monitoring (VX30) ni les onglets du panneau (VX14). **Done =** test miroir de `useChatPolling.test` : les deux intervalles s'arrêtent sur hidden et reprennent avec refresh au retour. Files: frontend/src/hooks/useVisibilityAwarePolling.js (nouveau), frontend/src/components/layout/NotificationBell.jsx, frontend/src/features/messaging/useChatPolling.js. (ROUTINE — S, sonnet) (@lane: frontend/shell) (@after: VX14)
- [x] VX57 — **Alléger le chemin froid : `sora.css` hors du rendu-bloquant + CopilotPanel paresseux.** (1) `sora.css` est une ressource bloquante de `index.html:14` (vérifié) pour une police utilisée uniquement par `/landing` — retirer le `<link>` et importer depuis le module Landing (Vite le rattache au chunk lazy) ; (2) `CopilotPanel` est monté en dur sur chaque écran authentifié (`Layout.jsx:84`) — passer en `React.lazy` + rendu seulement quand `copilotOpen` a été vrai une fois (patron AgentChat). **Done =** `dist/index.html` sans lien sora ; trace réseau de `/login` : zéro requête sora ; `/landing` rend toujours Sora ; chaîne distinctive de CopilotPanel absente des chunks pré-interaction ; tests copilot verts. Files: frontend/index.html, frontend/src/pages/Landing.jsx, frontend/src/components/layout/Layout.jsx. (ROUTINE — S, sonnet) (@lane: frontend/boot)
- [x] VX58 — **Préchargement au survol/focus des destinations chaudes de la Sidebar (adaptatif).** Zéro prefetch : chaque clic Sidebar paie le chunk lazy PUIS le fetch, en série. Exposer `router/prefetchMap.js` (les MÊMES imports dynamiques que `router/index.jsx` — une seule source) et déclencher sur `onMouseEnter`/`onFocus` des 5-8 liens les plus fréquents. Garde adaptative : rien si `navigator.connection?.saveData` ou `effectiveType` ∈ {2g, slow-2g} (feature-detect, no-op Safari). **Done =** vitest : hover → import mocké invoqué ; `saveData:true` → zéro invocation ; devtools : le chunk part au `mouseenter`. Files: frontend/src/router/prefetchMap.js (nouveau), frontend/src/components/layout/Sidebar.jsx. (ROUTINE — M, sonnet) (@lane: frontend/boot) (@after: VX57)
- [x] VX59 — **Nom de chunk roof-tool indépendant de la machine (hygiène du gate YHARD7).** Le plugin `roofBuilderTsPlugin` (`vite.config.js:44-86`) encode le chemin ABSOLU du disque dans l'id de module virtuel, qui fuit dans le nom du chunk émis — non portable entre machines/CI et structure du disque local publiée dans un asset. Encoder un chemin RELATIF à `WEB_SRC`, décodage par re-jointure. **Done =** build depuis deux chemins différents → même préfixe de nom ; `check-bundle-budget` passe et étiquette toujours le bucket roof-tool. Files: frontend/vite.config.js. (ROUTINE — S, sonnet) (@lane: frontend/build)
- [x] VX60 — **Gate e2e « comptes justes » : >100 enregistrements affichés en entier (sans polluer la base e2e partagée).** Verrouiller VX54 pour toujours : un spec Playwright qui seed >100 produits et >100 devis via `page.request` + cookie admin (patron `receivables.spec.js:14`), ouvre `/stock` et `/ventes/devis`, et asserte que le compteur rendu et le KPI Dashboard = le total réel (pas 100). ATTENTION : la suite roule sur UNE base `seed_demo` partagée, `workers:1` — les +200 lignes persisteraient pour tous les specs suivants ET fausseraient les baselines `@visual` de release-verify. **Done =** le spec NETTOIE en `afterAll` (suppression des lignes créées) OU vit dans un projet dédié exécuté en dernier et exclu de release-verify ; rouge si on ré-introduit l'appel single-page ; vert sur le code corrigé ; les autres specs restent verts après son passage. Files: frontend/e2e/ (nouveau spec). (ROUTINE — M, sonnet) (@lane: frontend/e2e-data) (@after: VX54)
- [x] VX61 — **[GATED: new dep web-vitals ~2KB] [backend-collection] Mesure des Web Vitals RÉELS (INP/LCP/CLS) → reporting maison.** YHARD7 mesure le BUILD, rien ne mesure le TERRAIN. Frontend : capter INP/LCP/CLS/TTFB, envoyer via `navigator.sendBeacon` (repli `fetch keepalive`) — la lib `web-vitals` (Google, MIT, ~2KB — GATED) OU un hand-roll `PerformanceObserver` si refusée. Backend (exception autorisée) : `POST /api/django/reporting/vitals/` dans l'app reporting existante (une ligne par métrique, company-scopée serveur) + un agrégat p75 par route. Cible : INP ≤ 200 ms / LCP ≤ 2,5 s au p75. **Done =** beacon visible à la navigation ; test backend : POST → ligne créée, scoping forcé ; la table est ENREGISTRÉE au registre de rétention (YOPSB10, livré — une ligne par métrique par navigation = croissance rapide, purge programmée) ; impact bundle ≤ 3 KB gzip (budget YHARD7 inchangé). Files: frontend/src/lib/vitals.js (nouveau), apps/reporting/ (endpoint), tests. (DEP — M, sonnet ; noter au DONE LOG) (@lane: frontend/vitals)

**K — Ne JAMAIS perdre le travail :**
- [x] VX62 — **Brouillon auto + garde de sortie sur DevisGenerator (le formulaire à 20 minutes).** `/ventes/devis/nouveau` (2 319 lignes, 64 `useState`) n'a NI `useDirtyGuard` NI brouillon : un clic malheureux, un swipe retour, un onglet fermé = 20 minutes perdues sans confirmation. Créer `frontend/src/ui/useDraftAutosave.js` (debounce 800 ms → localStorage, clé scopée lead/client/editDevis), bandeau « Reprendre le brouillon du [date] » Restaurer/Ignorer au montage, purge au succès ; câbler AUSSI `useDirtyGuard(dirty)` ; étendre au bouton « Aller à la page de connexion » de `SessionProvider.jsx:77-80` (confirmation si un formulaire dirty est monté). Garde `noValidate`/`step="any"` intacte. **Done =** vitest fake-timers : remplir → recharger → brouillon restauré ; submit réussi → clé vidée ; navigation pendant saisie → confirmation. Files: frontend/src/ui/useDraftAutosave.js (nouveau), frontend/src/pages/ventes/DevisGenerator.jsx, frontend/src/providers/SessionProvider.jsx. (ROUTINE — M, sonnet) (@lane: frontend/ventes-gen) (@after: VX18)
- [x] VX63 — **Fin du JSON brut à l'écran : erreurs lisibles + Réessayer sur DevisList (et chasse aux clones).** `DevisList.jsx:806-812` affiche `JSON.stringify(error)` sur un échec — un vendeur voit littéralement `{"detail":"Authentication credentials..."}` sans bouton Réessayer. Remplacer par `errorMessageFrom(error)` (déjà exporté de `lib/toast.js:92-107`) + un bouton relançant le thunk ; grep `JSON.stringify(err` sous `pages/` et corriger les jumeaux. **Done =** vitest : rejet `{detail}` → texte FR lisible, Réessayer relance. Files: frontend/src/pages/ventes/DevisList.jsx + occurrences jumelles. (ROUTINE — S, haiku) (@lane: frontend/ventes-list) (@after: VX52)
- [x] VX64 — **Error boundaries sur les routes nues : `/ui`, `/`, `/login` et TOUTES les pages publiques tokenisées.** Les routes sans layout (`/rdv/:token`, `/portail-contrats/:token`, `/ged/signature/:token`, `/kiosque`, `/e/:token`, `/suivi/:token`… `router/index.jsx:209-234`) n'ont AUCUNE boundary : un throw de rendu = page blanche — montrée à des CLIENTS externes sur des flux de signature légale. Envelopper chaque élément avec le `RouteErrorBoundary` existant, sans layout ERP autour. **Done =** vitest : chaque route avec un enfant qui throw → écran de récupération FR ; vérif manuelle `/ui`. Files: frontend/src/router/index.jsx. (ROUTINE — S, sonnet) (@lane: frontend/router)
- [x] VX65 — **Le lien profond survit à la connexion : `?next=` au redirect `/login`.** `authLoader`/`roleLoader` redirigent vers `/login` sans capturer l'URL d'origine, et `Login.jsx:165` navigue en dur vers `/dashboard` : un lien WhatsApp/email vers un devis précis perd sa destination si la session avait expiré. Capturer `?next=` (depuis le `Request` du loader) ; au succès, suivre `next` SEULEMENT s'il commence par `/` et pas `//` (garde anti-open-redirect). **Done =** vitest : connexion avec `?next=/crm/leads` → `/crm/leads` ; `next=//evil.com` → ignoré. Files: frontend/src/router/index.jsx, frontend/src/pages/Login.jsx. (ROUTINE — S, sonnet) (@lane: frontend/router) (@after: VX64)
- [x] VX66 — **Filet anti-double-soumission au niveau du composant `Button`.** La protection dépend de la discipline `loading={saving}` écran par écran (fenêtre d'un rendu React) : deux taps rapides peuvent créer deux devis/paiements. Dans `frontend/src/ui/Button.jsx`, garde interne (défaut sur `type="submit"`, prop opt-out) qui désactive IMPÉRATIVEMENT au premier `click` (avant le prochain rendu), ré-armée quand `loading` redescend. **Done =** vitest : deux clics synchrones → `onClick` UNE fois ; non-régression des tests Button. Files: frontend/src/ui/Button.jsx. (ROUTINE — S, sonnet : composant central) (@lane: frontend/ui-core)
- [x] VX67 — **Déployer `StateBlock` (chargement/vide/erreur + Réessayer) sur les 5 listes principales.** `components/StateBlock.jsx` existe, se documente comme « déploiement différé », et n'est importé que dans 2 fichiers (AgentChat, CopilotPanel) : ~30 pages gèrent l'erreur chacune à sa façon, souvent sans retry. Migrer DevisList, ClientList, Dashboard, Rapports, BalanceAgeePage vers `<StateBlock loading error empty onRetry />`, chaque `onRetry` relançant le thunk d'origine. **Done =** vitest par écran : 3 états + retry ; e2e rejouée sans régression. Files: les 5 pages + frontend/src/components/StateBlock.jsx. (ROUTINE — M, sonnet) (@lane: frontend/states) (@after: VX63)

**L — Les portes CI qui verrouillent tout pour toujours (WORTH-IT uniquement, per recherche) :**
- [x] VX68 — **Le gate e2e apprend Safari et l'iPad : projets WebKit + tablet dans Playwright.** `playwright.config.js` : le projet « mobile » est Chromium + UA iPhone (vérifié :61) — AUCUN moteur WebKit, aucun viewport 768-1024, donc rien de ce qui casse sur Safari n'est jamais capté. Ajouter (a) un projet `mobile-safari` `...devices['iPhone 13']` (WebKit RÉEL) exécutant le spec mobile, (b) un projet `tablet` `...devices['iPad (gen 7) landscape']` + `e2e/tablet.spec.js` : pas de débordement + affordances tri/actions atteignables SANS survol sur `/ventes/factures`, `/crm/leads`, `/chantiers`. Chromium actuel = smoke rapide ; PR-only ; PAS de Firefox. `ci.yml` : `npx playwright install webkit`. **Done =** les deux projets verts en CI ; le projet WebKit fait échouer VX48 si on le régresse. Files: frontend/playwright.config.js, frontend/e2e/tablet.spec.js (nouveau), .github/workflows/ci.yml. (ROUTINE — M, sonnet) (@lane: frontend/e2e) (@after: VX48)
- [x] VX69 — **Contrat de zoom : e2e à 150 % et 200 % sur les flux clés (WCAG 1.4.10).** `index.css:182-188` admet que le zoom 200 % est un contrôle « manuel » — jamais gardé, alors que les laptops Windows tournent à 125-150 %. `e2e/zoom.spec.js` : sur `/login`, `/ventes/factures`, `/crm/leads`, `/parametres`, forcer 150/200 % et asserter zéro débordement (`scrollWidth - innerWidth <= 1`) + boutons primaires cliquables. **Done =** spec verte ; une largeur fixe non-responsive la fait échouer. Files: frontend/e2e/zoom.spec.js (nouveau). (ROUTINE — M, sonnet) (@lane: frontend/e2e) (@after: VX68)
- [x] VX70 — **Régression visuelle ÉTROITE : ÉTENDRE `e2e/visual.spec.js` (il existe déjà) à 6-8 écrans clés, clair + sombre.** CORRECTION du critic : une comparaison de pixels EXISTE déjà — `frontend/e2e/visual.spec.js` (Dashboard, `toHaveScreenshot` + `maxDiffPixelRatio:0.02`, tag `@visual`, exécuté dans `release-verify.yml:227-247` avec workflow de ré-approbation des baselines) ; MB6 = overflow seulement, YTEST10 = PDF seulement. ÉTENDRE ce spec (jamais l'écraser) : ajouter DevisList, Kanban leads, DevisGenerator (en-tête+totaux), FactureList, Login — clair ET sombre, animations off, contenus dynamiques masqués — en GARDANT le tag `@visual` et le tier release-verify (manuel+nightly, jamais dans le smoke par-merge : décision livrée, ne pas la renverser sans raison). IMPÉRATIF : lancer APRÈS l'atterrissage des tâches design VX1-47 (sinon toutes les baselines sont invalidées) ; PAS de couverture exhaustive. **Done =** les nouveaux écrans passent en release-verify ; un changement CSS volontaire échoue avec diff lisible ; la procédure de ré-approbation existante couvre les nouvelles baselines. Files: frontend/e2e/visual.spec.js (extension). (ROUTINE — M, sonnet) (@lane: frontend/e2e) (@after: VX69) *(à exécuter en dernier de la vague.)*
- [x] VX71 — **[GATED: new dev-dep @axe-core/playwright] a11y dynamique : scans axe DANS les parcours e2e (extension de YHARD8).** YHARD8 = scans statiques ; seul un scan en VRAI parcours attrape les états dynamiques : modal ouvert, menu ouvert, formulaire en erreur, toast. Ajouter `@axe-core/playwright` (dev-only, gratuit) + UN `AxeBuilder.analyze()` après 4-5 interactions clés des specs existants (dialog PDF DevisList, lead en édition, formulaire invalide, kebab DataTable). Échec sur `serious`/`critical` uniquement (anti-flake). **Done =** scans verts sur main ; retirer un `aria-label` d'un dialog échoue ; zéro nouveau job. Files: frontend/e2e/ (extension des specs), frontend/package.json (dev-dep). (DEP — S, sonnet ; noter au DONE LOG) (@lane: frontend/e2e) (@after: VX70)
- [x] VX72 — **[DECISION] [GATED: new dep @sentry/react] Sentry frontend en no-op DSN-gaté, miroir du backend.** Le backend a `core/monitoring.py` DSN-gaté ; le frontend n'a RIEN : un crash React chez un employé n'a ni trace ni breadcrumbs. Ajouter `@sentry/react` derrière le MÊME patron (aucun envoi sans `VITE_SENTRY_DSN`, no-op total par défaut), câblé au `RouteErrorBoundary` avec `captureException` → `eventId` affiché (« code erreur à transmettre »). La tâche ne livre QUE le no-op câblé — l'ACTIVATION est une décision de Reda (dépendance externe, tier gratuit plafonné). **Done =** sans DSN : zéro requête sortante (assertion e2e) ; avec DSN de test : event + ID affiché ; budget YHARD7 respecté (SDK lazy). Files: frontend/src/lib/monitoring.js (nouveau), frontend/src/ui/ErrorBoundary.jsx. (DEP/DECISION — M, sonnet ; noter au DONE LOG) (@lane: frontend/monitoring)

**M — Honnêteté de la langue et de la locale :**
- [x] VX73 — **Le sélecteur de langue arrête de mentir + label `Ctrl K` sur Windows.** Le sélecteur EN/AR est réel mais ne couvre que ~121 clés de chrome (~2 % de l'app) : l'utilisateur choisit « English », obtient une sidebar anglaise puis des pages 100 % françaises — rien ne le lui dit. Dans `LanguageSwitcher.jsx`, quand `locale !== 'fr'` : notice persistante « Seuls les menus sont traduits — le contenu des pages reste en français » (clé ajoutée aux 3 catalogues). Au même passage : `providers/shortcuts.js:20` remplace le glyphe `'⌘ K'` codé en dur par une détection plateforme → `'Ctrl K'` sur Windows/Linux (la plateforme RÉELLE de l'ERP) ; mini-tripwire vitest anti-régression de couverture i18n. **Done =** switch EN → notice présente ; `navigator.platform='Win32'` → `Ctrl K` ; tripwire prouvé rouge sur une branche synthétique. Files: frontend/src/components/layout/LanguageSwitcher.jsx, frontend/src/providers/shortcuts.js, les 3 catalogues i18n. (ROUTINE — S, sonnet) (@lane: frontend/i18n)
- [x] VX74 — **[DECISION — ZÉRO build] L'arabe : interface complète RTL, ou langue de documents seulement ? Estimation chiffrée pour Reda.** Choisir AR aujourd'hui donne une app visuellement CASSÉE (1 seule règle CSS RTL ; 76 fichiers en utilitaires physiques `ml-*/mr-*` non retournés ; dropdowns/drawers non miroirés) — pire qu'untranslated. Or les documents clients arabes existent déjà (XSAL13/XSTK18…) et les techniciens reçoivent l'AR par WhatsApp (QJ4). Produire (PAS implémenter) une note chiffrée : (a) taille du dictionnaire à extraire + coût de maintien de 3 catalogues ; (b) audit RTL des 76 fichiers physiques→logiques + direction des primitives ; (c) recommandation AR = documents seulement (le champ `langue_document` le modélise déjà) vs UI complète vs « coquille seulement » ; si le verdict est « documents seulement », retirer AR du switcher UI (honnêteté > promesse). **Done =** note écrite livrée au fondateur avec les 3 chiffrages ; décision consignée au DONE LOG ; aucun fichier produit modifié. Files: docs/ (note). (DECISION — S, sonnet) (@lane: frontend/i18n) (@after: VX73)
- [x] VX75 — **Un seul format d'argent et de date : consolidation des ~90 contournements de `lib/format.js` + garde CI.** `format.js` se dit « une seule source de vérité » mais ~90 appels dans ~45 fichiers roulent leur propre `toLocaleString` avec DEUX tags concurrents (`fr-FR` vs `fr-MA`) — et un bug VISIBLE : `pages/stock/CatalogueTable.jsx:142/150` affiche `450.00 HT` (point) là où le devis affiche `450,00 MAD` (virgule) — même produit, deux formats dans la même session. Migrer les sites monétaires vers `formatMAD`/`formatNumber`, les ~25 dates vers `formatDate`/`formatDateTime`, les `.toFixed` restants vers `formatNumber`/`formatPercent` ; garde statique : échec sur tout nouveau `toLocaleString` hors `lib/format`. **Done =** grep hors format.js = 0 non-test ; CatalogueTable et DevisList rendent le même `1 234,56 MAD` (capture) ; `format.test.mjs` vert. *(Complémentaire de VX5 : VX5 = typographie du chiffre, ici = la VALEUR formatée.)* Files: ~45 fichiers cités par le grep, frontend/src/lib/format.js (garde). (ROUTINE — M, sonnet) (@lane: frontend/format) (@after: VX5)

**N — Surfaces secondaires (emails, impression, chrome navigateur, liens, fichiers) :**
- [x] VX76 — **[backend-template] Emails de marque : wrapper HTML unique sur les DEUX points d'envoi.** 100 % des emails transactionnels (relances devis, alertes rappel, confirmations e-signature, reçus) partent en texte brut sans logo — l'air d'un spam à côté du PDF premium. UN template additif `templates/email/base.html` (logo + en-tête navy + pied) et basculer les deux goulots — `apps/ventes/email_service.py:68-85` et `apps/notifications/services.py:89-109` — vers `EmailMultiAlternatives` : le texte existant rendu DANS le wrapper, texte brut conservé en repli MIME (additif, non cassant). Aucune logique métier, EmailLog/chatter identiques. **Done =** tests : l'envoi porte une alternative `text/html` avec le wrapper pour `send_document_email` ET `notify()` ; une commande `manage.py preview_email` rend le wrapper + un corps type en fichier HTML relu AVANT qu'un client ne reçoive le premier email brandé (boucle de validation visuelle — pas seulement la console) ; suites ventes/notifications vertes. Files: backend/django_core/templates/email/base.html (nouveau), apps/ventes/email_service.py, apps/notifications/services.py, tests. (ROUTINE — M, sonnet ; exception backend-template) (@lane: backend/email-templates)
- [x] VX77 — **Compression photo côté client AVANT upload sur les 3 écrans de capture terrain.** `ChantierPhotos.jsx:130-133`, `InterventionFieldExecution.jsx:347` et `InterventionCapturePanels.jsx` envoient la photo BRUTE (4-8 Mo routiniers) — minutes ou timeout par photo sur la 3G rurale. Helper pur `<canvas>`+`toBlob` (zéro dépendance) dans `frontend/src/ui/file-utils.js` : bord long ≤1600px, JPEG q0.75, `image/*` uniquement (PDF intouchés) ; idéalement via `FileUpload.jsx` pour centraliser. Garde serveur 20 Mo conservée. *(VX77 RÉTROFITTE la compression dans les écrans que VX44 vient de toucher — rafale/partage restent à VX44 ; le helper vit dans file-utils pour que tout futur écran en hérite.)* **Done =** vitest : blob de N Mo → plus petit, dimensions plafonnées, PDF passthrough ; payload réseau réduit vérifié. Files: frontend/src/ui/file-utils.js (nouveau), les 3 écrans cités. (ROUTINE — M, sonnet) (@lane: frontend/upload) (@after: VX44)
- [x] VX78 — **Brancher le 404 déjà construit : fini la redirection silencieuse vers le dashboard.** `ui/NotFound.jsx` est complet, exporté, jamais importé par le router (vérifié) : le catch-all (`router/index.jsx:357`) fait `<Navigate to="/dashboard" replace />` — un favori périmé rebondit sans explication. Remplacer par `{ path: '*', element: <WithLayout><NotFound /></WithLayout> }`. **Done =** test : `/nexiste-pas` rend « Page introuvable » ; e2e verte. Files: frontend/src/router/index.jsx. (ROUTINE — S, haiku) (@lane: frontend/router) (@after: VX65)
- [x] VX79 — **Liens internes partageables : `?id=` + « Copier le lien » pour devis, chantier et ticket SAV.** Seuls les leads ont une URL partageable (VX22 ajoute la route) ; devis/chantier/ticket s'ouvrent en panneaux d'état jamais reflétés dans l'URL — impossible d'envoyer à un collègue « regarde CE devis » (le seul lien existant est la proposition PUBLIQUE, règle #4, intouchée). Refléter le détail ouvert dans l'URL (patron `?lead=` de LeadsPage, `useSearchParams`) pour `/ventes/devis`, `/chantiers`, `/sav` + bouton « Copier le lien » (patron clipboard DevisList, pointé vers l'URL INTERNE) ; id invalide → l'`EmptyState` inline, jamais une page blanche. **Done =** pour chaque entité : id valide ouvre le bon panneau, id invalide → EmptyState ; le lien copié rouvre le même enregistrement dans un onglet neuf. Files: frontend/src/pages/ventes/DevisList.jsx, frontend/src/pages/installations/InstallationsPage.jsx, frontend/src/pages/sav/TicketsPage.jsx. (ROUTINE — L, sonnet) (@lane: frontend/deeplinks) (@after: VX31, VX67) *(@coord VX20/VX48/VX63 sur DevisList — rebase.)*
- [x] VX80 — **Feuille de style d'impression + bouton « Imprimer » sur devis-liste, factures et checklist chantier.** Zéro `@media print` dans tout le SPA (grep vérifié) : Ctrl+P imprime la sidebar, le dark mode qui boit l'encre, des tables tronquées. UN bloc global `styles/print.css` : masquer sidebar/header/boutons, tables `overflow: visible; width:auto`, noir-sur-blanc, `@page { margin: 2cm }`, `page-break-inside: avoid` ; + bouton « Imprimer » (`window.print()`) sur DevisList, FactureList, checklist d'InstallationDetail. Totalement distinct des PDF WeasyPrint (règle #4 — jamais touchés). **Done =** `page.emulateMedia({media:'print'})` sur les 3 écrans : table complète, zéro chrome, fond clair ; vitest smoke bouton. Files: frontend/src/styles/print.css (nouveau), les 3 écrans. (ROUTINE — M, sonnet) (@lane: frontend/print) (@after: VX52) *(@coord VX50 sur FactureList — rebase.)*
- [x] VX81 — **Noms de fichiers d'export XLSX/CSV horodatés (parité avec le fix PDF QD2).** ~9 exports tableur codent un nom nu (`PilotageStock.jsx:140` `analyse-achats.xlsx`, `MouvementsPage.jsx:96/146`, `FiscalitePage.jsx:118-122` — 5 CSV fiscaux envoyés au comptable !, `EngagementsPage.jsx:416`, `EtatsPage.jsx:191/202`) : deux exports le même jour = `(1)`,`(2)` indistinguables. Étendre `utils/downloadBlob.js` d'un `stampedFilename(base, ext)` → `base_societe_AAAAMMJJ.ext`, préférer `Content-Disposition` serveur quand présent. **Done =** vitest par site : le nom contient la date ; double export = deux noms distincts. Files: frontend/src/utils/downloadBlob.js + les sites cités. (ROUTINE — S, haiku) (@lane: frontend/export)
- [x] VX82 — **Chrome navigateur vivant : titre d'onglet par page + préfixe `(N)` non-lus + theme-color clair/sombre.** Un seul `<title>` statique pour toute la vie du SPA : 6 onglets ERP = devinette, et le compteur non-lus (`NotificationBell.jsx:179-182`) n'est jamais reflété dans l'onglet. Hook `useDocumentTitle.js` (zéro dépendance) sur DevisList/FactureList/InstallationDetail/TicketsPage/LeadsPage (`Titre · TAQINOR`) ; NotificationBell préfixe `(N)` quand `total > 0` ; `index.html` : second `<meta name="theme-color" media="(prefers-color-scheme: light)">` (aujourd'hui le chrome OS reste navy autour d'une app claire). **Done =** vitest : monter DevisList → `document.title` mis à jour ; préfixe `(N)` posé/retiré ; preview clair/sombre : le bon meta actif. Files: frontend/src/hooks/useDocumentTitle.js (nouveau), frontend/src/components/layout/NotificationBell.jsx, frontend/index.html. (ROUTINE — S, sonnet) (@lane: frontend/shell) (@after: VX56)

---

**ROUND 3 (2026-07-09) — « le meilleur outil avec lequel un employé ait travaillé » : ergonomie par métier, vitesse de saisie, file de travail, droit à l'erreur, interop.**
*Le fondateur a re-challengé : « êtes-vous sûrs ? je veux que les EMPLOYÉS le classent comme le meilleur outil — couvrez TOUS les angles et pour chacun la MEILLEURE solution ». Rounds 1-2 = beau + techniquement parfait ; round 3 = au service de l'employé. Sweep 12 agents (journées du technicien/commercial/directeur/comptable ; vitesse de saisie ; file de travail personnelle ; droit à l'erreur ; interop Excel/WhatsApp/téléphone ; 2 recherches externes G2/Capterra/NN-g/Odoo/Linear/Superhuman ; carte anti-duplication) + synthèse Fable + dédup adversariale contre les 2 084 tâches NT (`docs/new_tasks_plan.md`, PR #345), VX1-82, ARC, FE-*. **L'insight n°1, tracé dans le code : l'intelligence déjà construite et payée n'atteint jamais un écran qui dit « fais ça maintenant »** — la tournée géo-optimisée (endpoint complet, jamais appelée par l'écran du technicien), la signature client (modèle+endpoint+offline construits, zéro UI), le journal d'appel typé du commercial (backend livré, zéro site d'appel), la file de relances FG31, le toast « Annuler » `toastWithUndo` (0 appelant), la délégation d'absence — tous orphelins côté écran. La majorité du round 3 est donc du CÂBLAGE, pas de la construction : le meilleur ratio valeur/effort des trois rounds. Dédup NT appliquée : 5 seeds réécrites/abandonnées (voir NE PAS FAIRE round 3). **Ce qu'aucun audit ne remplace — noté pour Reda, PAS une tâche : une vraie boucle de retour employés** (3 chiffres mesurés avant/après : temps « nouveau lead → 1er appel », taps pour clôturer une intervention, minutes de patrouille matinale ; 30 min d'observation/persona/mois ; un canal « signaler une friction » à un tap + les web-vitals réels de VX61).*

**O1 — La file, la confiance, les gestes quotidiens (tous les employés, plusieurs fois/jour) :**
- [x] VX83 — **« Ma file » : LA file de travail unique (décision d'architecture — flagship).** Chaque employé patrouille 4 surfaces déconnectées dans 3 sections (Mes activités sous CRM, Approbations sous ANALYSE, la cloche, Ma journée) — ~2-4 min de « ai-je raté quelque chose ? » par session/personne, plus des approbations/mentions qui dorment. **Décision (UNE architecture) : faire évoluer `MesActivitesPage` en « Ma file » cross-module — jamais une nouvelle app inbox, jamais une page par persona (6ᵉ silo).** `[BACKEND additif]` action `GET /records/activities/ma-file/` à côté de `mine` (`apps/records/views.py:155-172`) rendant les 3 buckets existants PLUS : approbations décidables par moi (réutiliser l'agrégateur `_SOURCE_LOADERS`, `apps/reporting/approbations.py:129-135` — jamais le forker), mentions non lues avec leur `link` (cf. VX85), et pour le rôle commercial : relances dues via FG31 déjà livré jamais consommé — EXTRAIRE la logique de `LeadViewSet.relances` (`apps/crm/views.py:969-994`) vers `apps/crm/selectors.py` puis l'appeler (jamais forker/appeler une vue, convention selectors) — leads chauds jamais contactés (via `selectors.py`) et devis `envoye` proches d'expiration — chaque item `{kind, title, due, link, urgency, montant?}`. **Inclure le quick-add « + À faire »** (créer une `records.Activity` personnelle assignée à soi) — la promesse XKB4 `[x]` est absente du code (vérifié : zéro « à faire » dans `MesActivitesPage.jsx` alors que le serializer expose le champ `records/serializers.py:83`) ; une file où on ne peut pas s'ajouter une tâche est une demi-file. Frontend : `MesActivitesPage.jsx` rend l'union classée plus-urgent-d'abord, en-tête « 3 en retard · 2 aujourd'hui · 1 approbation », verbes Fait / Plus tard / Déléguer / Ouvrir + « + À faire ». Promouvoir l'entrée nav hors de CRM (`Sidebar.jsx`) vers le groupe de tête. `/ma-journee` reste l'écran d'exécution terrain — Ma file y pointe. Alternatives rejetées : page « ma journée commerciale » dédiée (silo), extension Dashboard (VX27 possède les KPI par rôle et LIE vers Ma file), nouvelle app inbox. **Done =** l'endpoint agrège les 3+ familles company-scopées (≤2 requêtes/source) via selectors ; la page affiche la liste unifiée classée + total unique + « + À faire » fonctionnel ; décider une approbation depuis la file passe par le `decider` existant ; hooks e2e préservés. Files: `apps/records/views.py`, `apps/crm/selectors.py`, `frontend/src/pages/activities/MesActivitesPage.jsx`, `Sidebar.jsx`. (ARCH — L, sonnet ; revue orchestrateur obligatoire) (@lane: backend/records + frontend/queue) *(@coord VX27/VX14 ; ARC10 = moteur SOUS la file.)* **⚠ Directive de dédup (critic Fable) : `NTMOB19` (`docs/new_tasks_plan.md`, « widget à faire aujourd'hui ») construit la MÊME union cross-module de sélecteurs — à corriger AVANT que sa lane ne bâtisse un 2ᵉ agrégateur : NTMOB19 doit CONSOMMER l'endpoint `ma-file/` de VX83, pas le refaire (idem NTMOB5 « Mes approbations » mobile / NTWFL28).**
- [x] VX84 — **[BUG] La cloche arrête de compter le travail des AUTRES.** `[BACKEND one-liner]` Le badge « Activités en retard » est calculé company-wide (`apps/reporting/search.py:169-172`, `**co` sans `assigned_to`, vérifié) : le commercial voit les retards de TOUTE la boîte dans SON badge, pendant que `/activites` ne montre que les siens — deux chiffres qui se contredisent à chaque page. Un badge auquel on ne croit plus est pire que pas de badge. Ajouter `assigned_to=request.user` au filtre, faire dériver le total de la cloche et celui de « Ma file » (VX83) de la même source, étiqueter « pour moi » vs « information société » (garanties/contrats restent des alertes société légitimes). **Done =** test de régression — l'activité en retard d'un collègue est exclue du badge ; total cloche == total actionnable de Ma file. Files: `apps/reporting/search.py`, `frontend/src/components/layout/NotificationBell.jsx`. (ROUTINE — S, sonnet) (@lane: backend/records) (@after: VX83)
- [x] VX85 — **Plomberie de la file dans `apps/records` : snooze non destructif + mentions cliquables + réaffectation notifiée.** `[BACKEND additif]` Trois trous, une lane. (a) « Reporter » réécrit `due_date` de façon destructive — ajouter `snoozed_until` nullable sur `records.Activity` (`models.py:98`, migration additive), exclu de `mine`/`ma-file` tant que non échu, picker « ⏰ Plus tard » (ce soir / demain / lundi / +1 semaine / perso — vocabulaire convergent Outlook/Superhuman/Linear) à côté de « Fait » ; « Reporter » reste pour les vrais changements d'échéance. (b) `_notify_mentions` (`views.py:300-323`) notifie SANS `link` → mention non cliquable, absente de toute file : passer le `link` (même mapping que `MesActivitesPage.jsx:56-62`) ; idem `notify_followers`. (c) Changer `assigned_to` (`serializers.py:82`) ne notifie personne — le travail tombe entre deux personnes : détecter le changement dans `perform_update` (`views.py:214`), `notify()` le nouveau propriétaire avec `link`, bouton « Déléguer à… » (réutiliser `AssigneePicker`). **Done =** item snoozé revient à l'heure dite avec sa `due_date` d'origine intacte ; clic mention → navigation ; réaffectation → notification + l'item change de file ; tests sur les trois. Files: `apps/records/{models,views,serializers}.py` + migration, `frontend/src/components/ActivitiesPanel.jsx`. (SCHEMA — M, sonnet) (@lane: backend/records) (@after: VX83) *(@coord NTCOL17 = l'inbox mentions dédiée AU-DESSUS de ce fix `link`.)*
- [x] VX86 — **Signal ambiant sur les approbations (badge sidebar + carte Dashboard + rangée cloche).** L'inbox 5-sources `/approbations` (XKB1/ZCTR7-9) est excellente et fonctionnellement INVISIBLE : 6ᵉ item de la section ANALYSE (`Sidebar.jsx:189`), zéro badge, zéro carte Dashboard, zéro entrée cloche — des réquisitions dorment. Hook partagé `useApprobationsCount()` (total de `approbations-en-attente/`, polling via `useVisibilityAwarePolling` de VX56 quand livré) alimentant : badge numérique sur l'item nav, carte « Attend votre décision » en tête de `Dashboard.jsx` (si `total>0`, top-3 via `?trier=urgence` déjà supporté, lien direct), rangée « N approbations » en tête de la cloche. MINIMAL pour ne pas empiéter sur VX27 (dashboards par rôle — fusionner la carte à son build) ni VX14. **Done =** badge/carte/rangée affichent le même chiffre, disparaissent à 0, clic → `/approbations` ; testé ≥1 source non vide. Files: `frontend/src/hooks/useApprobationsCount.js` (nouveau), `Sidebar.jsx`, `Dashboard.jsx`, `NotificationBell.jsx`. (ROUTINE — S/M, sonnet) (@lane: frontend/queue) *(@coord NTWFL15 = polish inbox mobile ; NTMOB5 = cockpit mobile dirigeant — même source.)*
- [x] VX87 — **Journal d'appel en un geste : ressusciter `log-interaction` (mort UI) + relance dans le même geste + nudge post-appel.** L'action la plus fréquente du commercial (15-30 appels/jour) coûte ~6 interactions dans 3 zones de la modale, et l'issue (joint/non joint/à rappeler/refus/intéressé) est INCAPTURABLE — alors que le backend livre tout (FG30 `views.py:1163-1206`, `OUTCOMES` `models.py:739-745`, pose `first_contacted_at`) et que `crmApi.logInteraction` a **ZÉRO site d'appel (vérifié)**. Mini-composant « Journaliser un appel » (boutons issue + note + « prochaine action J+0/1/3/7 » → `relance_date`) dans la section Historique de `LeadForm.jsx` (~:1194) et sur les lignes de Ma file (VX83) ; après un tap `tel:` sur `LeadCard`/`ListView`, au retour dans l'onglet (`visibilitychange`), proposer « Appel terminé — noter le résultat ? » pré-rempli `kind='appel'`. Garder `noter` (note libre) — on l'augmente. **Done =** appel journalisé avec issue en ≤2 clics + relance posée dans le même geste ; entrée typée au chatter ; `logInteraction` a ≥1 consommateur ; nudge dismissable, hook `data-*` nouveau uniquement. Files: `frontend/src/pages/crm/LeadForm.jsx`, `leads/views/LeadCard.jsx`, `ListView.jsx`, nouveau `features/crm/CallLogPopover.jsx`. (ROUTINE — M, sonnet) (@lane: frontend/crm) *(@coord NTSRV5 = le futur log-appel SAV réutilisera CE composant.)*
- [x] VX88 — **Ma journée branche la tournée géo-optimisée déjà payée.** Le technicien voit ses arrêts en ordre priorité-puis-insertion, sans sens géographique — 15-40 min de trajet perdues/jour/technicien — alors que `ma-tournee` (tri plus-proche-voisin + lien Google Maps par arrêt, `apps/installations/views/intervention.py:1846-1900`) est construit, testé, et consommé uniquement par un onglet bureau. Dans `MaJourneePage.jsx`, remplacer `getInterventions({date_prevue: today})` par `installationsApi.getMaTournee` (déjà défini, `installationsApi.js:246-248`, vérifié) et afficher « Itinéraire » (`stop.itineraire_url`) par carte. Coordonner VX42 : son bouton « navigation » DOIT pointer `itineraire_url` (une seule logique de lien maps). **Done =** `/ma-journee` affiche l'ordre `ma-tournee` + lien Itinéraire cliquable si GPS connu ; `getInterventions` inchangé ailleurs. Files: `frontend/src/pages/interventions/MaJourneePage.jsx`. (ROUTINE — S, sonnet) (@lane: frontend/terrain) (@after: VX42) *(@coord NTFSM3 = optimiseur 2-opt plus avancé — s'il atterrit, il remplace ma-tournee ; re-mesurer.)*

**O2 — La vitesse de saisie (commerciaux + comptable, dizaines de fois/jour) :**
- [x] VX89 — **LeadForm : Escape + autofocus via `ResponsiveDialog` (et corriger le « done » menteur de MB4).** Le modal n°1 de l'ERP (20-40 ouvertures/jour/commercial) est le SEUL à ne pas répondre à Escape ni focuser son champ requis : shell brut `div.modal-overlay` (`LeadForm.jsx:588-589`), zéro `autoFocus` — alors que MB4 est marqué `[x]` en prétendant la migration faite (fact-check : faux pour ce fichier — noter au DONE LOG). Envelopper le shell externe dans `ResponsiveDialog` (comme `ClientForm`), garder le `lead-form-layout` interne, `autoFocus` sur Nom. Le composant existe, est utilisé par 4/6 formulaires audités, donne Escape + focus-trap + bottom-sheet mobile gratuits. **Done =** ouverture → Nom focus ; Escape → `onClose` ; largeur desktop équivalente ; e2e LeadForm verts. Files: `frontend/src/pages/crm/LeadForm.jsx`. (ROUTINE — M, sonnet) (@lane: frontend/crm) (@after: VX22) *(@coord VX51 clavier iOS — fichier partagé, rebase.)*
- [x] VX90 — **« Ajouter ligne » déplace enfin le focus sur la nouvelle ligne (devis + facture).** Dans les trois grilles de lignes (`DevisGenerator.jsx addLine:820`, `DevisForm.jsx`, `FactureForm.jsx:170`), ajouter une ligne laisse le curseur où il était : sur un devis de 8 lignes, 8 trajets souris inutiles sur le document le plus stratégique. Poser `data-line-key` sur chaque `<tr>` + `pendingFocusKey` dans `addLine`, `.focus()` du `ProduitPicker` de la nouvelle ligne + `scrollIntoView`. Un ref-walk DOM, pas une réécriture `useFieldArray`. **Done =** clic « Ajouter ligne » → `activeElement` dans la nouvelle ligne, les trois fichiers ; tests totaux inchangés ; garde `noValidate`/`step="any"` intacte. Files: les 3 fichiers. (ROUTINE — S, sonnet) (@lane: frontend/ventes-gen) (@after: VX16)
- [x] VX91 — **Convergence FactureForm : `ProduitPicker` + « + Nouveau client ».** Régression réelle : la colonne Produit de `FactureForm.jsx:430-440` est un `<Select>` natif non filtrable sur 50+ SKU, là où DevisForm/DevisGenerator utilisent le `ProduitPicker` recherche-d'abord. Swap à l'identique de `DevisForm.jsx:317-321`. Ajouter « + Nouveau client » (réutiliser `ClientQuickCreateModal`, câblage QG3 prouvé) sur le select client de `FactureForm.jsx:293-307` et `DevisForm.jsx:231-245` — aujourd'hui facturer un client absent = abandonner la facture. Pure convergence : supprime une implémentation dupliquée pire. **Done =** colonne produit = popover recherchable ; création client inline sélectionne le nouveau ; `onProduitChange` inchangé. Files: `FactureForm.jsx`, `DevisForm.jsx`. (ROUTINE — S/M, sonnet) (@lane: frontend/ventes)
- [x] VX92 — **« Enregistrer et créer un autre » + mort du `window.alert` du paiement.** Aucun « save & new » dans le repo : 10 leads après un salon, 5 paiements après un relevé, 20 produits à seeder = un cycle fermer/rouvrir par enregistrement (~10-30 s chacun). Toggle « Créer un autre » (persisté `localStorage`, défaut OFF → identique) sur `ProduitForm.jsx`, `ClientForm.jsx`, le dialog paiement de `FactureList.jsx:676-711` : succès → reset + refocus champ 1 au lieu de `onClose()`. Au même passage : `alert('Paiement enregistré.')` (:265) → `toast.success`, `autoFocus` sur `pay-montant`. **Done =** toggle ON → le dialog ne ferme pas, formulaire vidé, focus champ 1 ; OFF → identique. Files: `ProduitForm.jsx`, `ClientForm.jsx`, `FactureList.jsx`. (ROUTINE — M, sonnet) (@lane: frontend/forms) *(@coord VX19 possède le sweep GLOBAL alert/confirm — créditer les 2 sites réécrits ici.)*
- [x] VX93 — **Défauts intelligents : propriétaire = moi, dernière ville, dernière TVA, dernier mode de paiement.** Quatre valeurs parmi les plus re-saisies n'ont aucun défaut : `owner` vide sur chaque lead (`LeadForm.jsx:230` — le créateur est presque toujours le propriétaire), `ville` sans mémoire, TVA figée `'20'` (`ProduitForm.jsx:275`, `DevisGenerator emptyLine:74`), `payMode` figé `'virement'` (`FactureList.jsx:228`). Étendre le pattern `canal: DEFAULT_CANAL` déjà livré : owner = utilisateur courant (création seulement), ville/TVA/payMode = dernier utilisé via `localStorage`, toujours modifiables, jamais bloquants. Un réglage backend « TVA société » serait de la sur-ingénierie. **Done =** nouveau lead pré-rempli owner+ville, nouveau produit/ligne dernière TVA, paiement dernier mode ; l'édition d'un existant intacte. Files: `LeadForm.jsx`, `ProduitForm.jsx`, `DevisGenerator.jsx`, `FactureList.jsx`. (ROUTINE — S, haiku) (@lane: frontend/forms)
- [x] VX94 — **Enter-pour-ajouter + refocus sur les panneaux de capture terrain (surface 100 % pouces).** Sur téléphone, chaque relevé de série / ligne consommée force à lâcher le clavier, viser « Ajouter », re-taper — ×8 composants sérialisés par pose. Dans `InterventionCapturePanels.jsx` : `onKeyDown` Enter → `add()` sur les inputs de `SerialsPanel:71-74` et du bloc extra de `ConsommationPanel:180-184`, + `firstFieldRef.focus()` après succès (recette `newCatRef` prouvée dans `ProduitForm.jsx:294-300`) ; `ReservesPanel` (Textarea) reste clic-only. **Done =** Enter dans le dernier champ = clic « Ajouter » ; succès → focus au premier champ ; test simule Enter. Files: `frontend/src/features/installations/InterventionCapturePanels.jsx`. (ROUTINE — S, sonnet) (@lane: frontend/terrain)

**O3 — Le droit à l'erreur (tous, la confiance au quotidien) :**
- [x] VX95 — **Câbler `toastWithUndo` (0 appelant) : archivage leads + drop kanban en avant.** Le primitive undo parfait existe (`frontend/src/lib/toast.js:60-89`, commit différé + « Annuler ») et a ZÉRO consommateur (vérifié). (a) Archive/désarchive lead (`ListView.jsx`), archive bulk (`BulkActionBar.jsx:94-105`), delete/unarchive stock (`StockList.jsx:792-825`) → `toastWithUndo`. (b) Kanban : un drop en avant d'une colonne de trop est instantané, non annulable (`KanbanView.jsx:186-200`) — après un drop réussi, toast « Annuler » 6 s restaurant l'étape précédente EXACTE en contournant le recul-guard (undo de sa propre action) ; `SIGNED` reste gardé par `SigneDialog` ; clés de stage importées de `features/crm/stages` (règle #2). Un confirm bloquant par drag est rejeté (tuerait le kanban). **Done =** archive + drop avant montrent « Annuler » 6 s ; le clic restaure l'état antérieur ; recul-guard inchangé pour les drags manuels ; hooks e2e préservés. Files: `ListView.jsx`, `BulkActionBar.jsx`, `StockList.jsx`, `KanbanView.jsx`. (ROUTINE — M, sonnet) (@lane: frontend/forgiveness) *(@coord NTUX6 = undo de l'édition en masse, primitive partagée.)*
- [x] VX96 — **Le delete de lead cesse d'être « irréversible » : `Lead` premier adoptant du soft-delete.** `[BACKEND]` La fondation FG388 (SoftDeleteModel + `core/trash.py` fenêtre 30 min + `TrashViewSet` `/core/corbeille/` en ligne, vérifié) est adoptée par ZÉRO modèle métier — pendant que `LeadViewSet.destroy()` (`apps/crm/views.py:698`) fait un vrai DELETE confirmé par un `window.confirm` avouant « irréversible ». Faire hériter `Lead` de `SoftDeleteModel` (migration additive), `destroy()` → `soft_delete(user)` ; frontend : `confirmDelete()` + `toastWithUndo` (VX95), copy « irréversible » supprimée. **PÉRIMÈTRE RÉDUIT (dédup NT) : ne PAS construire de composant `<CorbeillePanel>` générique ni d'écran corbeille — `NTUX7` (`docs/new_tasks_plan.md`) possède la Corbeille transverse (app `apps/trash`, event-bus, `/parametres/corbeille`, purge/permissions/audit).** Cette tâche = uniquement faire de `Lead` le premier adoptant du soft-delete + l'undo-toast ; la restauration passe par le `TrashViewSet` existant en attendant l'écran NTUX7. **⚠ Piège à signaler (critic Fable) : NTUX7 (`docs/new_tasks_plan.md`) bâtit une SECONDE pile de corbeille inconsciente de FG388** — nouvelle app `apps/trash` + `ElementSupprime` + son propre endpoint corbeille, alimenté par un événement `record_soft_deleted` que RIEN n'émet (`SoftDeleteModel.soft_delete` n'écrit que `DeletionRecord`) → un Lead soft-deleted via FG388 n'apparaîtrait JAMAIS dans la corbeille NTUX7, et l'OS finirait avec DEUX magasins de corbeille + deux endpoints. **AVANT que la lane NTUX7 ne build, la re-baser sur FG388** (émettre `record_soft_deleted` depuis `SoftDeleteModel.soft_delete`, ou lire `DeletionRecord`). **Done =** supprimer un lead le sort des querysets par défaut, restaurable 30 min (toast) ; copy « irréversible » supprimée ; tests crm restore + scoping company. Files: `apps/crm/models.py`+migration, `apps/crm/views.py`, `ListView.jsx`, `BulkActionBar.jsx`. (SCHEMA — M, sonnet ; escalader opus si l'import-linter core bronche) (@lane: backend/crm) (@after: VX95)
- [x] VX97 — **La facture (et le devis) montrent enfin « qui a fait quoi ».** `FactureActivity`/`DevisActivity` existent et s'écrivent (migrations ventes 0020/0017) mais la facture — le document au plus gros blast-radius financier — n'a AUCUN historique visible ; le seul « Historique » de DevisList est la chaîne de versions, pas le journal des changements. Monter le feed existant en section « Historique » repliable dans le détail Facture (`FactureList.jsx`) et Devis (`DevisList.jsx`), convention `<Sec id="historique">` prouvée dans `LeadForm.jsx:1193`. Rendre via `ChatterTimeline` (VX23) quand il atterrit ; jamais une 14ᵉ classe `*Activity` (ARC8). `prix_achat` jamais affiché. **Done =** ouvrir une facture/un devis montre qui/quand/ancien→nouveau. Files: `FactureList.jsx`, `DevisList.jsx`. (ROUTINE — M, sonnet) (@lane: frontend/forgiveness) (@after: VX92) *(@coord VX23 ChatterTimeline / ARC9 lecture uniforme ; VX92/VX93/VX114 touchent aussi FactureList — rebase en séquence.)*
- [x] VX98 — **Confiance en 2 clics : lien « Historique » sur la fiche + puce de fraîcheur.** « Qui a changé ce prix ? » = quitter la fiche → Journal global (gaté Directeur) → re-filtrer à la main. (a) Bouton « Historique » sur `DevisForm.jsx` et `ProduitDetail.jsx` → `/journal?model=devis&object_id={id}` (apprendre à `Journal.jsx` à lire ces params), visible avec `journal_activite_voir` — réutilise `AuditLog`+Journal qui couvrent TOUS les modèles. (b) `[BACKEND additif]` `<FreshnessChip>` « modifié par X il y a N min » sur Lead/Devis/Facture : `updated_at` existe, ajouter `updated_by` posé dans `perform_update` (pattern `archived_by`) ; rien si null ou si c'est moi. Le verrou optimiste complet reste territoire YDATA — ceci est la mitigation 80/20. **Done =** 1 clic fiche → Journal pré-filtré sur CET objet ; puce rendue, silencieuse sur son propre edit ; tests avec/sans permission. Files: `DevisForm.jsx`, `ProduitDetail.jsx`, `Journal.jsx`, backend `perform_update` (2 apps crm+ventes, 3 modèles Lead/Devis/Facture). (SCHEMA — M, sonnet) (@lane: frontend/forgiveness)

**O4 — Le directeur décide vite et juste (Reda + Meryem, quotidien) :**
- [x] VX99 **(partiel 2/3 — contrats.EtapeApprobation bloqué : bulk_create sans signal)** — **Les 3 sources d'approbation muettes se mettent à sonner.** `[BACKEND]` `APPROVAL_REQUESTED`/`REMINDER`/`ESCALATED` existent (YEVNT8/9) mais des 5 sources de l'agrégateur (`approbations.py:129-135` : automation/contrats/ged/installations/workflow), le câblage `apps/notifications/signals.py:154-234` n'en notifie qu'UNE (automation ; le `workflow` FG366 est couvert par NTWFL5) : soumettre une `DemandeAchat` (`installations/views/demande_achat.py:83-94` — vérifié : zéro `notify()`), une `EtapeApprobation` (contrats) ou une `DemandeApprobation` (GED) n'alerte personne. Étendre le câblage existant (même pattern que `automation.AutomationApproval`), import fonction-local. **Done =** soumettre chacune des 3 sources crée une notification pour le(s) approbateur(s) ; test additif par source. Files: `apps/notifications/signals.py`. (ROUTINE — M, sonnet) (@lane: backend/notify) *(@coord NTWFL5 notifie le NOUVEAU moteur FG366 — sources disjointes ; ARC10 ne re-câble pas en double.)*
- [x] VX100 — **Fin de la décision à l'aveugle : montant + lien source dans l'inbox d'approbations.** `[BACKEND additif]` L'agrégateur supporte `?trier=montant` (`approbations.py:180,198-202`) mais aucune source ne remplit jamais `montant` — code mort — et `ApprobationsPage.jsx:139` n'a aucun lien vers la pièce : Reda approuve sans voir le montant ni le chantier. Exposer `montant` (depuis `DemandeAchat.montant_estime`, `models_demande_achat.py:103`) et `lien` (`/chantiers/{id}` ; `None` si pas de cible — jamais fabriqué) dans `_installations_items()` (:96-110) et équivalents ; colonne cliquable. Contrat d'API inchangé. **Done =** colonne Montant réelle pour les DemandeAchat, tri `montant` change l'ordre, clic → la pièce. Files: `apps/reporting/approbations.py`, `ApprobationsPage.jsx`. (ROUTINE — M, sonnet) (@lane: backend/reporting) (@after: VX99)
- [x] VX101 — **[BUG AUTH] Seul le bon tier peut approuver.** `[BACKEND]` `decider_approbation` est gardé par `IsAnyRole` (`approbations.py:207/337`, vérifié) et `decider_demande_achat` (`installations/services.py`) ne vérifie AUCUN rôle : **aujourd'hui un commercial ou un technicien peut approuver une réquisition d'achat ou une étape de contrat.** Dans `_decider_approbation_core` (`approbations.py:254-333`) — point d'ancrage unique des 5 sources — exiger le tier Responsable/Admin pour les sources `installations` et `contrats` ; la LECTURE reste ouverte. Si ARC10 atterrit avant, ré-évaluer sur le nouveau moteur. Noter AUTH au DONE LOG. **Done =** test — un rôle normal reçoit 403 en décidant une DemandeAchat/EtapeApprobation, la lecture reste 200 ; non-régression automation/ged/workflow. Files: `apps/reporting/approbations.py`, `apps/installations/services.py`. (AUTH — M, opus : contrôle d'accès cross-app) (@lane: backend/reporting) *(@coord NTWFL1 = matrice unifiée future.)*
- [x] VX102 — **(CONSTRUIT 2026-07-09, demande directe du fondateur) Le terrain peut CRÉER une réquisition d'achat — page dédiée `/chantiers/demandes-achat`.** Livré au-delà du périmètre réduit initial : une PAGE dédiée (liste DataTable + dialogue de création chantier/lignes/priorité/date-besoin + « Soumettre » + Approuver/Refuser inline gardés au palier responsable/admin), pas seulement des points de montage. Endpoints FG310 réutilisés, AUCUN changement backend (un technicien porteur d'un rôle passe déjà la permission de création ; le sous-gate `IsAnyRole`/`is_responsable` reste la dette systémique VX101). RESTE ouvert comme raffinement : points de montage mobile « il me manque du matériel » dans `/ma-journee` + `InstallationDetail.jsx` (peuvent réutiliser cette page/ses composants). **NB futur run NT :** `NTP2P3` (formulaire DemandeAchat + recherche-catalogue) est désormais LARGEMENT satisfait — vérifier-non-déjà-construit avant de le bâtir. Livré : `frontend/src/pages/installations/DemandesAchatList.jsx` (+test), `api/installationsApi.js`, `router/index.jsx`, `Sidebar.jsx`. (ROUTINE — M, sonnet) (@lane: frontend/terrain) *(@coord NTP2P3/NTP2P4/NTP2P23.)*
- [x] VX103 — **Écran de délégation d'absence (backend XKB3 complet, 0 UI).** `automation.ApprovalDelegation` (modèle + `ApprovalDelegationViewSet` + `active_delegation_for()` + tests) n'a AUCUNE UI (grep « delegation » dans `frontend/src` : zéro). Si Reda part en congé, rien ne bascule vers Meryem sans passer par l'admin Django. Onglet « Délégations » dans `ApprobationsPage.jsx` : suppléant + plage de dates, liste actives/à venir, révocation — pur câblage sur l'API existante (`automation/urls.py:16`). **Done =** créer/voir/révoquer une délégation depuis l'UI ; le suppléant voit les items du délégant pendant la plage. Files: `frontend/src/pages/approbations/ApprobationsPage.jsx`. (ROUTINE — M, sonnet) (@lane: frontend/reporting) *(@coord NTWFL3 étend la COUVERTURE backend de cette même délégation au moteur WorkflowStepInstance — l'UI ici ne doit pas supposer la seule couverture ApprovalRequest.)*
- [x] VX104 — **Le superviseur se règle à la création de l'employé.** L'onboarding traverse 3 écrans jamais reliés ; le formulaire « Nouvel utilisateur » (`UsersManagement.jsx:342-418`) n'a pas de champ superviseur (seul `EquipeSection.jsx:108-125` le permet) → hiérarchie oubliée en silence, visibilité des dossiers cassée sans erreur. Ajouter le select `supervisor` (mêmes options que `EquipeSection.jsx:198-211`) au formulaire de création ; si vide, toast « Pensez à définir son responsable direct » + lien Paramètres → Équipe. **Done =** superviseur réglable dès la création ; création sans superviseur → toast avec lien. Files: `frontend/src/pages/admin/UsersManagement.jsx`. (ROUTINE — S, sonnet) (@lane: frontend/admin)

**O5 — Le technicien finit sa boucle (1-3 employés, chaque intervention) :**
- [x] VX105 — **Finir l'écran du technicien : statut + onglets persistants + honnêteté hors-ligne des photos.** Trois trous du même écran, une lane. (a) `MaJourneePage` n'expose AUCUN changement de statut : le technicien qui finit ne peut pas marquer « Terminée » — ajouter le Select statut du `DetailSheet` d'`InterventionsPage.jsx:399-411`, la garde serveur `transition_block_reason` existe (afficher le 400, ne JAMAIS la dupliquer). (b) Les 9 onglets remontent-refetchent à chaque re-visite et une app backgroundée (appel entrant — constant en chantier) perd tout : `forceMount` sur les `TabsContent` (`ui/Tabs.jsx:38-46`, natif Radix) + persister onglet/intervention en `sessionStorage`. (c) Un upload photo/mémo échoué hors-ligne affiche un `toast.error` jumeau du « mis en file » de succès du panneau voisin (`InterventionFieldExecution.jsx:312-322`) : la photo obligatoire est PERDUE sans le comprendre — message d'échec DISTINCT et persistant (« Photo NON envoyée — reprenez-la au retour du réseau ») ; la file binaire IndexedDB reste territoire de FG386 (jamais un 2ᵉ outbox). DoD aussi : vérifier qu'un rôle Technicien réel passe `ajouter-reserve` (`views/intervention.py:1286`, `IsResponsableOrAdmin`) — sinon flag `[BACKEND]` one-liner. **Done =** statut modifiable depuis /ma-journee avec blocage serveur lisible ; re-visite d'onglet sans spinner ; reprise après backgrounding au même endroit ; échec photo distinct + test réseau coupé. Files: `MaJourneePage.jsx`, `InterventionFieldExecution.jsx`, `InterventionCapturePanels.jsx`, `ui/Tabs.jsx`. (ROUTINE — M, sonnet) (@lane: frontend/terrain)
- [x] VX106 — **La signature client sort de sa tombe (FG69 : modèle + endpoint + offline construits, 0 écran).** `signature_client`/`signataire_nom`/`signe_le` (`models_intervention.py:168-170`), POST `signer-client` (`views/intervention.py:1823-1844`), l'op offline `SIGNER_CLIENT` (`fieldOutbox.js:24`) + handler (`field_sync.py:202-217`) existent tous — un seul fichier frontend les référence (vérifié). Chaque « c'est signé ? » redevient un appel ; le compte-rendu ne vaut pas preuve. Nouveau `SignatureClientPanel` réutilisant `SignaturePad` (`features/logistique/SignaturePad.jsx` — canvas Pointer Events, zéro dépendance), envoyé via `withOfflineFallback(FIELD_OPS.SIGNER_CLIENT)`, onglet dans `MaJourneePage` + `InterventionsPage` ; référencer la signature dans le compte-rendu d'intervention (`intervention_pdf.py` — PDF d'intervention, PAS le moteur `/proposal`, hors règle #4). **Done =** capturer/envoyer (ou mettre en file hors-ligne), afficher « Signé par X le … » ; compte-rendu montre la signature si présente. Files: `frontend/src/features/installations/SignatureClientPanel.jsx` (nouveau) + points de montage. (ROUTINE — M, sonnet) (@lane: frontend/terrain) *(⚠ NT `NTFSM11` propose de RE-créer des champs signature (`signature_client_key`/`nom_signataire`/`date_signature`) apparemment sans savoir que FG69 existe — probable doublon du plan NT à corriger AVANT que sa lane ne bâtisse un schéma parallèle ; CETTE tâche consomme les champs RÉELS existants.)*
- [x] VX107 — **Résumé client en lecture seule dans le flux terrain (garantie + dernier ticket SAV).** « C'est encore sous garantie ? Vous êtes déjà venus ? » sur site = appel bureau ou navigation vers la page bureau de 1 604 lignes — 3-5 min/occurrence, plusieurs fois/semaine. Petite section « Infos client » lecture SEULE dans le Sheet d'intervention : garantie du matériel principal, dernier ticket SAV ouvert, date de mise en service — mêmes appels `savApi` déjà en prod dans `InstallationDetail.jsx:280-286`, aucune route nouvelle. Quand ARC46 (`RecordShell`) atterrira, cette section y migrera. **Done =** garantie + dernier ticket visibles sans quitter le Sheet ; zéro écriture. Files: `frontend/src/features/installations/InterventionFieldExecution.jsx`. (ROUTINE — M, sonnet) (@lane: frontend/terrain)

**O6 — L'harmonie avec le monde extérieur (Excel / WhatsApp / téléphone) :**
- [x] VX108 — **`tel:`/`wa.me` partout où un numéro s'affiche (pas seulement les leads).** Le tap-to-call n'existe QUE sur les leads CRM ; `ClientDetailPanel` n'affiche même pas le téléphone, `FournisseurFiche360` non plus, le contact site d'`InstallationDetail.jsx:976-977` est un `<Input>` non cliquable, SAV rien — chaque rappel = recomposition manuelle, plusieurs fois/jour sur 4 rôles. Extraire `telHref`/`waHref` de `LeadCard.jsx:49-60` en util partagé `lib/contactLinks.js` et câbler les 4 écrans (l'input reste éditable en mode édition ; l'affichage devient un lien). **Done =** les 4 écrans rendent un lien `tel:` tapable partout où un numéro s'affiche ; hooks e2e intacts. Files: `frontend/src/lib/contactLinks.js` (nouveau), les 4 écrans. (ROUTINE — S, haiku) (@lane: frontend/interop)
- [x] VX109 — **Importer fournisseurs & équipements : brancher les cibles orphelines d'ExcelImport.** Le pipeline `dataimport` supporte 6 cibles (`services.py:20-70` : dry-run, commit, mémoire de mapping, CSV d'erreurs ré-importable) mais `ExcelImport.jsx` n'est monté que sur 3 (leads/clients/products) : onboarder une liste fournisseurs ou un inventaire d'équipements = saisie manuelle (des heures). Ajouter le bouton « Importer » + `<ExcelImport target=…>` (déjà générique) sur `FournisseursStock.jsx` et `EquipementsPage.jsx` — **`vehicules` est possédé par FE-XFLT22, ne pas doubler.** **Done =** entrée d'import visible sur les 2 pages, un dry-run+commit manuel par cible. Files: `FournisseursStock.jsx`, `EquipementsPage.jsx`. (ROUTINE — S, haiku) (@lane: frontend/interop)
- [x] VX110 — **« Copier » vers le presse-papiers depuis toute liste DataTable (TSV → colle propre dans Excel/WhatsApp).** Zéro copie presse-papiers de données (14 hits `clipboard` = secrets/liens, jamais des lignes) : coller 15 noms filtrés dans un groupe WhatsApp = Exporter → retrouver le .csv → ouvrir Excel → re-copier. Ajouter `rowsToTSV` à côté de `rowsToCSV` (`ui/datatable/csv.js` — réutiliser la garde anti-injection `escapeCSVCell`, délimiteur `\t`, sans BOM) + action bulk « Copier » dans `BulkActionBar.jsx` (sélection, sinon lignes filtrées), toast ; pilote sur `ClientList.jsx`. Le TSV est ce qu'Excel produit au copier — collage aligné gratuit. **Done =** « Copier » copie la sélection en TSV collable en colonnes dans Excel ; test du sérialiseur. Files: `frontend/src/ui/datatable/csv.js`, `BulkActionBar.jsx`, `ClientList.jsx`. (ROUTINE — M, sonnet) (@lane: frontend/interop) *(@coord ARC49/53 : DevisList/FactureList migrées hériteront de l'action.)*
- [x] VX111 — **[PRÉMISSE CORRIGÉE] Lier une pièce jointe à une NOTE du chatter lead + la remonter dans le flux mobile.** *Correction du critic Fable : le Lead a DÉJÀ un point d'entrée pièce-jointe fonctionnel — `records.Attachment` whiteliste `('crm','lead')` (`records/models.py:21`), `AttachmentViewSet` est routé, et `LeadForm.jsx:1155-1158` rend un `<AttachmentsPanel model="crm.lead">` avec dropzone FileUpload + progression. Ce n'est donc PAS « aucun point d'entrée / perte de données ».* Le vrai manque, étroit : (a) une pièce jointe n'est pas RATTACHABLE à une note du chatter (le composer Historique de `LeadForm.jsx:521` poste `/crm/leads/{id}/noter/` en texte pur) — ajouter une affordance d'attache au composer (multipart `noter`, réutiliser `FileUpload`) ; (b) surfacer l'`AttachmentsPanel` existant dans le flux MOBILE (aujourd'hui présent surtout desktop). **DÉCISION à trancher dans la tâche : un seul magasin** — réutiliser `records.Attachment` (déjà en place, whitelisté) OU le dépôt GED cross-app — JAMAIS deux magasins parallèles pour la photo d'un lead (c'est exactement la fragmentation qu'ARC26 existe pour arrêter). NE PAS toucher `ChatterWidget` (son seul conscommateur prod est `features/kb/ArticleDetail.jsx` — l'attache y mettrait le bouton sur les articles KB, pas les leads). **Done =** attacher 1 photo à une note lead depuis mobile via le magasin RETENU ; `AttachmentsPanel` atteignable sur mobile ; aucun 2ᵉ magasin créé ; non-régression KB. Files: `frontend/src/pages/crm/LeadForm.jsx`, `apps/crm/views.py` (`noter` multipart), tests. (ROUTINE — M, sonnet) (@lane: frontend/crm) *(@coord NTSRV3 = canal WhatsApp entrant SAV via webhook — mécanisme différent ; ARC26 = politique magasin-unique.)*

**O7 — Le comptable reste dans l'app (persona finance, wiring polish) :**
- [x] VX112 — **La balance âgée cesse d'être un cul-de-sac : drill-down « Relancer » vers les relances filtrées.** `BalanceAgeePage.jsx`'s seule action de ligne ouvre un PDF « Relevé » (:125-133) — aucun chemin pour AGIR sur la dette. Ajouter une 2ᵉ action de ligne `<Link to="/ventes/relances?client={id}">` + lire `?client=` dans `RelancesPage.jsx` (`load()` :50-54) pour pré-filtrer côté client (miroir du `niveauFilter` :167-178, aucun endpoint). **Done =** cliquer la nouvelle icône « Relancer » d'une ligne atterrit sur `/ventes/relances` pré-filtré sur ce client ; PDF « Relevé » intact. Files: `frontend/src/pages/reporting/BalanceAgeePage.jsx`, `frontend/src/pages/ventes/RelancesPage.jsx`. (ROUTINE — S, sonnet) (@lane: frontend/finance)
- [x] VX113 — **FiscalitePage : sélecteur d'exercice (fin de la saisie « Exercice (ID) » à la main).** Le bloc export de `FiscalitePage.jsx:337-353` utilise un `<Input>` brut (placeholder « ex. 3 ») pour l'exercice des exports FEC/liasse/IS, là où `EtatsPage.jsx:249-260` a déjà un `<select>` alimenté par le même `comptaApi.exercices.list()` — un ID d'exercice tapé de travers = un export fiscal faux. Reprendre le `useEffect`+`<select>` d'`EtatsPage`, en gardant le `needsExercice` gating. Zéro backend (`exercices.list()` déjà appelé dans le même fichier). **Done =** le picker d'exercice du bloc export est un `<select>` de libellés réels ; `runExport` inchangé. Files: `frontend/src/features/compta/pages/FiscalitePage.jsx`. (ROUTINE — S, haiku) (@lane: frontend/finance)
- [x] VX114 — **Fin des `window.prompt()` de l'« Export comptable » : vrai sélecteur de dates.** `FactureList.jsx:346-365` (`handleExportComptable`) enchaîne deux `window.prompt()` pour début/fin — aucune validation, dialog navigateur moche incohérent avec le reste. Remplacer par un petit `Dialog` (réutiliser Dialog/FormField/Input déjà importés :26-30) à deux `Input type="date"` défaut mois-en-cours/aujourd'hui, appelant le même `dl()` au submit. **Done =** plus aucun `window.prompt` dans `handleExportComptable` ; dates via inputs `date` ; double-download xlsx+csv inchangé ; `required` sur les deux. Files: `frontend/src/pages/ventes/FactureList.jsx`. (ROUTINE — S, sonnet) (@lane: frontend/finance) (@after: VX97) *(@coord VX19 sweep prompt — créditer ce site ; VX92/VX93/VX97 touchent aussi FactureList — rebase en séquence.)*
- [x] VX115 — **Les KPI du cockpit comptable pointent vers l'écran d'ACTION, + un index « Où trouver mes exports ».** (a) Les cartes `CockpitPage.jsx:45-97` envoient « Créances clients »/« DSO » vers `/comptabilite/etats` (un état, pas une action) — repointer vers `/reporting/balance-agee` (et `/ventes/relances`), garder `/comptabilite/etats` pour Résultat/Trésorerie où c'est juste. (b) Le handoff mensuel au comptable externe est éparpillé sur 4 écrans (FactureList, FiscalitePage, EtatsPage, BalanceAgeePage) : ajouter au Cockpit une petite carte « Où trouver mes exports » = index de navigation (liens vers les 4 destinations, ZÉRO logique d'export dupliquée). **Done =** clic « Créances clients » → balance âgée ; carte index affiche les 4 destinations avec liens. Files: `frontend/src/features/compta/pages/CockpitPage.jsx`. (ROUTINE — S, haiku) (@lane: frontend/finance)
- [x] VX116 — **Relance en lot : proposer « Consigner + aperçu WhatsApp » sans jamais auto-envoyer.** `RelancesPage.jsx:81-93` (`relancerSelection`) ne fait que `relancerFacture` par ligne (consigne une note) — jamais le `whatsapp()` par-ligne (:134-151). Étendre le bouton en petit `DropdownMenu` (pattern « Relance premium » :331-348) : « Consigner uniquement » (inchangé) et « Consigner + aperçu WhatsApp pour chacun » qui ouvre le MÊME dialog aperçu-puis-confirmer par client en séquence (jamais `wa.me` sans clic explicite — règle manuel-wa.me du fondateur, [[agent_actions_plan]]). Coupe le « 10 clics de chasse aux lignes » sans envoi silencieux. **Done =** le dropdown offre les deux options ; « consigner uniquement » byte-identique ; l'option WhatsApp montre l'aperçu par client en séquence, jamais d'auto-envoi. Files: `frontend/src/pages/ventes/RelancesPage.jsx`. (ROUTINE — M, sonnet) (@lane: frontend/finance) *(@coord vérifier non-doublon avec NTTRE12/NTCRD si un envoi-relance-multicanal y est queué avant build.)*

**NE PAS FAIRE (rejets délibérés de l'audit — ne pas re-proposer sans nouveau contexte) :**
- Ne pas rebâtir la fondation design (F120–P171 livrés et bons) — cette vague est de l'ADOPTION et de la signature.
- Ne pas dupliquer ODX5/6/7 (écran Applications, nav filtrée, extraction registre) — queued ; VX8/9/13 s'y adossent.
- Ne pas remettre en cause le découpage backend ODX ni re-fusionner des modules (verdict : continuer tel que planifié).
- Pas de grille d'apps pleine page à la Odoo comme navigation obligatoire (transition lourde critiquée par les utilisateurs Odoo) — le lanceur VX9 est un overlay léger.
- Aucune nouvelle dépendance npm : pas de framer-motion (CSS + Radix suffisent), pas de cmdk (palette maison livrée), pas de lib confetti (CSS-only), pas de leaflet-markercluster.
- Ne jamais toucher les templates PDF devis/facture, PdfCanvas, `/proposal`, `apps/web` (règle #4).
- Pas de funnel-chart branché sur un modèle de pipeline (règle #2 : le funnel STAGES.py n'a pas encore de modèle Lead/Opportunity backing) — seules les COULEURS de stage sont tokenisées (VX26).
- Pas de migration DevisList/FactureList vers le moteur `ui/datatable` dans cette vague (1 720/1 195 lignes, hooks e2e `ap-*` massivement accrochés au DOM actuel ; le gain ne vaut pas le risque sur le chemin de l'argent) — **désormais possédée par ARC49/ARC53 (PLAN.md, 2026-07-08)** : elles s'exécutent APRÈS les tâches VX touchant ces fichiers et en préservent les comportements.
- Pas de son (le silence est le bon choix pour un back-office partagé) ; l'haptique mobile (VX42) tient ce rôle.
- Pas de moteur de theming par tenant (coût élevé, un seul tenant dominant) ; le nom de société au login (VX34) suffit.
- Pas de WebSockets/indicateurs de frappe (précédent S21 [BLOCKED] — infra fondateur) ; le polling 3 s suffit.
- Pas de badges compteurs sur la BottomTabBar (exige un agrégat backend nouveau) — le bandeau « aujourd'hui » (VX27) couvre le besoin.
- Pas de refonte de Landing.jsx (page vitrine interne à faible trafic — la vraie vitrine est `apps/web`, intouchable).
- Pas de photo produit sur le catalogue dans cette vague (exige champ modèle + migration + pipeline d'upload — candidat à une future tâche BACKEND+UI dédiée).
- Pas de clustering cartographique fait main ni d'endpoint de données de démo (hors périmètre frontend-first).

*Rejets round 2 (2026-07-08) :*
- Verrou optimiste Devis/Lead (409 concurrent) — vrai besoin mais exige modèle+serializer backend : territoire YDATA (PLAN.md), pas de doublon ici.
- Lighthouse CI sur le SPA authentifié — OVERKILL (personne ne « bounce » sur un outil interne) ; YHARD7 l'a déjà volontairement laissé optionnel ; VX61 (vitals RÉELS terrain) répond mieux.
- Second gate de budget bundle (BundleMon/size-limit) — YHARD7 possède déjà `check_bundle_budget.mjs` dans le job frontend-perf.
- Matrice Firefox toujours-active — aucun utilisateur Firefox connu ; VX68 = Chromium+WebKit PR-only, le bon ratio.
- Snapshots dark/RTL en matrice dédiée — OVERKILL tant que VX74 n'a pas tranché l'arabe ; si l'AR UI devient réel, ÉTENDRE VX70.
- Serveur de feature-flags + dashboard qualité BI — OVERKILL à 2-5 utilisateurs ; les toggles env existants suffisent.
- Couverture screenshot exhaustive — la taxe de baselines dépasse la valeur ; VX70 reste à 6-8 écrans.
- `useTransition`/virtualisation supplémentaire — aucun long-task MESURÉ ne le justifie (les gels prouvés sont réseau-sériels → VX54/55) ; attendre les données RUM de VX61.
- Service worker de cache API — interdit sur données authentifiées (fuite inter-sessions) ; le precache d'app-shell existe déjà.
- File offline nouvelle — N91/F21 livrés, FG386 possède l'extension ; jamais un second outbox. Snapshot visuel du PDF devis — YTEST10. N+1 devis — QPERF1. Enveloppe d'erreur API/X-Request-Id/429 — YAPIC.

*Rejets round 3 (2026-07-09 — dédup contre les 2 084 tâches NT `docs/new_tasks_plan.md`) :*
- **2FA « se souvenir de cet appareil »** — ABANDONNÉ : `NTSEC14` (« Device trust ») construit la MÊME feature avec un design STRICTEMENT MEILLEUR (modèle `TrustedDevice` révocable + gate société `allow_device_trust` + audit) ; bâtir une version cookie-only ici créerait un 2ᵉ mécanisme parallèle. Attendre/construire NTSEC14.
- **Composant Corbeille générique `<CorbeillePanel>` + écran `/parametres/corbeille`** — possédé par `NTUX7` (app `apps/trash`, `ElementSupprime`, hook event-bus, purge/permissions/audit) ; VX96 ne fait que rendre `Lead` premier adoptant du soft-delete + l'undo-toast.
- **Formulaire de saisie DemandeAchat avec recherche-catalogue** — possédé par `NTP2P3` ; VX102 se limite aux points de montage mobile.
- **Refonte du chatter / 14ᵉ classe `*Activity`** — VX23 (ChatterTimeline) + ARC8/ARC9 ; VX97/VX111 ne font que consommer/monter.
- **Unifier le moteur d'approbation / matrice objet×montant×département** — ARC10 + `NTWFL1` ; VX86/99/100/101/103 câblent l'inbox/signaux AU-DESSUS des 5 sources actuelles et se ré-évaluent si le moteur unifié passe d'abord.
- **Page « Ma journée commerciale » dédiée / bandeau SLA séparé** — 6ᵉ silo ; VX83 « Ma file » absorbe ces sources (relances FG31, leads chauds/SLA, devis expirants).
- **Inbox mentions dédiée `/mentions`** — `NTCOL17` ; VX85 ne fait que réparer le `link` manquant que NTCOL17 exige.
- **Optimiseur de tournée 2-opt avancé** — `NTFSM3` ; VX88 ne fait que consommer l'endpoint `ma-tournee` déjà livré.
- **Undo de l'édition en masse** — `NTUX6` ; VX95 câble `toastWithUndo` sur archive/kanban seulement.
- **Paste-grid Excel (coller 5 lignes)** — différé : à 2-10 employés, l'import fichier (VX109) + « Copier » TSV (VX110) couvrent le volume réel.
- **KPI perso « mes-stats » pour le rôle normal, classement inter-pairs** — différé : vraie motivation mais exige endpoint + RBAC ; re-proposer une fois « Ma file » prouvée, jamais de classement au rôle normal.
- **Correction de ligne de paiement / suppression** — DECISION fondateur (implications GL sous le verrou de période FG115) : logguer la décision (immutable-par-avoir vs endpoint de correction) avant tout build ; détail dans `persona-finance.md`.
- **Client-360 complet, import relevé bancaire OCR, recompute TVA depuis le GL** — logés dans `persona-finance.md`, différés : croisent NTFIN/NTTRE/NTCRD (146 tâches finance NT) → passer une dédup dédiée avant de construire.
- **Re-surfacer l'abonnement iCal (FG6)** — une ligne dans VX46 « Mes préférences » (extension par référence), pas une tâche : le feed + le bouton « Copier » existent déjà sur CalendarPage.
- **Attention fold cross-lane (critic Fable)** — `FactureList.jsx` (VX92/93/97/114), `NotificationBell.jsx` (VX84/86 + VX14/56), `Dashboard.jsx` (VX86/VX27) sont édités par plusieurs lanes : rebaser en séquence (les `@after`/`@coord` posés) ou fusionner par fichier au build — jamais deux lanes concurrentes sur le même fichier.

### Groupe VXD — approfondissement forensique (rework 3 axes, 2026-07-10)

Provenance : rework forensique en 3 axes (beauté / robustesse / amour-employé), ~30 lanes
d'audit + synthèses Fable par axe + une méta-critique Fable finale (`grand-verdict.md`) qui a
contre-vérifié ~20 claims dans le code réel, tué/fusionné/rogné les seeds en collision avec
VX1-116, et corrigé les constats survendus avant transcription. Verdict honnête du méta-critique :
cette passe ne « rapetisse » pas les 3 rounds précédents en VOLUME, mais l'axe robustesse (VXD-A/B)
trouve des bugs d'une gravité qu'aucun round n'avait atteinte — doublon fiscal au retry, paie qui
valide une période avec des bulletins avalés, signature client hors-ligne qui s'évapore, deux
intercepteurs de refresh concurrents qui déconnectent des sessions valides — et la famille
« surfaces fantômes » (VXD-D) prouve que deux features entières (chat Discuss, LeadExpressModal)
rendent sans un seul octet de CSS, qu'un kiosque TV affiche du JSON brut, et qu'un token de focus
soigné est du code mort — des angles morts qu'une lecture JSX-only ne peut pas voir. Axes 2 et 3
ont été livrés partiellement au premier passage (21/45 puis 11/45) et complétés après le
grand-verdict depuis les rapports de lane bruts (`r2-*`, `r3-*`) ; ce qui suit est l'état complet
tel que livré, corrections du grand-verdict déjà appliquées seed par seed. Contraintes héritées à
l'identique du bloc VX : frontend-first, aucune dépendance npm nouvelle sauf tâche taguée
[GATED], ne jamais toucher `apps/ventes/quote_engine/`, `/proposal`, PdfCanvas ni `apps/web`
(règle #4), toute clé de stage vient de `STAGES.py`/`features/crm/stages.js`, jamais un littéral
(règle #2), UI française partout, hooks e2e `ap-*/att-*/pp-*` préservés, `prix_achat`/marge jamais
client-facing, tout scoping multi-tenant côté serveur (`request.user.company`, `perform_create`
force `company`).

---

## TOP PRIORITÉ — 3 bugs constructibles + 1 alerte sécurité (CANDIDAT BUILD)

- [x] VX117 **(already present)** — **[BUG] CANDIDAT BUILD : `resilientMutation` — fin du doublon fiscal au retry (@lane: frontend/data)
  (devis/facture/paie/rôles).** Trois flux « parent + N lignes en `Promise.all` » laissent des
  documents financiers mi-sauvés et permettent un doublon fiscal silencieux au retry :
  `DevisGenerator.jsx:1019-1020` a un `.catch(() => {})` explicite sur `deleteLigneDevis`, et
  `DevisForm.jsx:40` (`const isEdit = !!devis`, jamais réassigné après un create réussi — idem
  `FactureForm.jsx:41`) fait qu'un retry après échec partiel repart en CREATE et crée un SECOND
  devis/facture. `PaieRunWizard.jsx:127` (`.catch(() => {})`) et `:135` (`catch { /* on continue */
  }`) avalent chaque échec de bulletin puis avancent inconditionnellement la période en VALIDÉE.
  `RolesManagement.jsx:328-338` réassigne en masse sans rapport nominatif sur le chemin
  permissions. Fix (le bon patron existe déjà, payé une fois en ERR63
  `ParametresEntreprise.jsx:470-486`) : extraire `frontend/src/lib/resilientMutation.js`
  (`allSettled` + rapport nominatif `{succeeded, failed:[{item,error}], allOk}` + `resumeId` — le
  parent créé reste exposé, la relance passe en ÉDITION, jamais un second POST) et n'avancer
  l'état parent (VALIDÉE, `deleteRole`, fermeture) que si `allOk`. Files :
  `frontend/src/lib/resilientMutation.js` (nouveau), `DevisGenerator.jsx`, `DevisForm.jsx`,
  `FactureForm.jsx`, `PaieRunWizard.jsx`, `RolesManagement.jsx`. DoD : mock 1 ligne/3 en échec → 2
  persistées, message nomme la ligne, « Réessayer » ne renvoie QUE la fautive et jamais un second
  `createDevis` ; 1 bulletin en échec → période NON avancée + employé nommé ; 1 PATCH rôle en
  échec → rôle non supprimé + liste migrés/en-échec + reprise ciblée. (T1 — M/L, sonnet ; review
  opus : paie + rôles = surfaces finance/auth) (@lane: frontend/data)

- [x] VX118 — **[BUG] CANDIDAT BUILD : surfaces fantômes — deux features entières rendent sans (@lane: frontend/orphans)
  AUCUN CSS + kiosque TV en JSON brut.** (a) le chat interne Discuss — `chat-list-*`, `chat-shell`,
  `chat-thread-*`, `chat-pinned-*`, `chat-composer-*` (11+ noms, 4 fichiers
  `features/messaging/*` : `ConversationList.jsx`, `MessageThread.jsx`, `Composer.jsx`,
  `pages/messaging/ChatPage.jsx`) ont **0 règle** dans les 5 fichiers CSS du repo — la barre des
  messages épinglés, les états active/unread/muted, la liste de conversations retombent sur les
  styles navigateur ; (b) `LeadExpressModal.jsx` — 23 références `lem-*` sans aucun CSS depuis sa
  création, le raccourci « ⚡ Express » mis en avant s'affiche en HTML nu au milieu d'une app
  tokenisée ; (c) `DashboardsTvPage.jsx:76` — page explicitement documentée « pensée pour un écran
  dédié affiché en continu » — rend `<pre>{JSON.stringify(current.layout)}</pre>` : du texte
  développeur monospace sur l'écran que le bureau regarde toute la journée, alors que la rotation
  15s et le refresh 60s sont déjà câblés, seul le renderer manque. Fix : (a)/(b) migrer sur les
  primitives existantes (`cn()` conditionnel + Tailwind pour Discuss dont Avatar/Badge/Input sont
  déjà importés ; `Dialog`+`FormField` pour LeadExpress) — PAS écrire le CSS manquant ; (c)
  consommer `current.layout` avec le kit existant (`Stat`/`ModuleDashboard`/`ui/charts` en mise en
  page plein écran, grands chiffres `text-6xl`, sparklines en grand, contraste lisible à 3 mètres),
  lire la forme réelle du layout retourné par `coreApi.dashboardsTv.list()` avant mapping. Files :
  `features/messaging/ConversationList.jsx`, `MessageThread.jsx`, `Composer.jsx`,
  `pages/messaging/ChatPage.jsx`, `pages/crm/leads/LeadExpressModal.jsx`,
  `pages/reporting/DashboardsTvPage.jsx`. DoD : grep des classes fantômes `chat-*`/`lem-*` = 0 (ou
  chacune couverte par du Tailwind co-listé) ; bandeau épinglé avec fond/bordure visibles
  (capture) ; le modal Express partage le langage des autres dialogues CRM ; test de rendu
  DashboardsTvPage avec layout mock stats/charts → aucun `<pre>`/JSON.stringify dans le DOM ;
  vérification visuelle 1920×1080. (T1 — M, sonnet) (@lane: frontend/orphans)

- [x] VX119 — **[BUG] CANDIDAT BUILD : outbox terrain — une op rejetée par le serveur disparaît en
  silence (incl. signature client).** `offline/outbox.js:117-122` purge un batch 100 % en statut
  `error` sans jamais lire le champ `.error` que le backend renvoie pourtant par opération
  (`field_sync.py:263/266/293/313`) ; l'unique affichage (`OfflineSyncIndicator.jsx:14-23`) rend
  « Connexion rétablie. » dans les deux cas — une SIGNATURE CLIENT capturée hors-ligne
  (`FIELD_OPS.SIGNER_CLIENT`) peut s'évaporer sans trace. Fix : trois classes de résultat dans
  `flush()` (done retirés / `error` GARDÉS en file avec message serveur + compteur de tentatives /
  échec réseau déjà géré), méthode `fieldOutbox.failed()`, indicateur à 3 états (badge rouge « N
  action(s) en échec — voir détail », abandon par op UNIQUEMENT explicite). Le message serveur
  affiché EST le signal de conflit — pas de moteur CRDT, pas une 2ᵉ file offline. Files :
  `offline/outbox.js`, `offline/useFieldOutbox.js`, `offline/OfflineSyncIndicator.jsx`. DoD : batch
  mock 100 % `error` → ops gardées + message par op accessible ; badge distinct rendu ;
  non-régression `applied`/`replayed`. (T1 — M, sonnet) (@lane: frontend/data)

- [x] VX120 — **[BUG] [GATED: génération QR] La graine TOTP 2FA est exfiltrée vers
  `api.qrserver.com` — et la CSP casse l'écran d'activation.** [BACKEND additif]
  `pages/parametres/SecuriteCompteSection.jsx:360-363` construit
  `https://api.qrserver.com/v1/create-qr-code/?...data=${encodeURIComponent(setup.otpauth_uri)}` —
  l'URI `otpauth://` CONTIENT `secret=<graine TOTP>` : le facteur 2FA part en clair chez un tiers
  non contrôlé (logs, MITM, opérateur). Aggravant : la CSP `img-src` (`nginx.conf:78`) n'autorise
  PAS ce domaine → en prod le QR ne s'affiche JAMAIS, l'activation 2FA est cassée
  fonctionnellement. Le repo possède DÉJÀ un générateur QR serveur (`apps/stock/labels.py:368`,
  `qr_svg`). Fix : [BACKEND additif] l'endpoint `2fa/setup/` renvoie un `qr_svg` inline (réutiliser
  `labels.qr_svg` via un helper `authentication` — aucune migration) ; le client le rend via un
  helper `renderTrustedSvg`/`lib/trustedSvg.js` (refuse `<script`/`on*=`/`javascript:`) ; supprimer
  totalement l'appel tiers. Files : `frontend/src/pages/parametres/SecuriteCompteSection.jsx` ;
  `[BACKEND]` `authentication/views` (payload setup). DoD : activer le 2FA n'émet AUCUNE requête
  hors-origine (Playwright `page.on('request')` filtré = 0) ; le QR s'affiche sous la CSP de prod ;
  la graine n'apparaît dans aucune URL. (T1 — M, opus : auth/2FA) (@lane: backend/auth)

**Note d'extension (ne pas double-compter) :** l'audit a confirmé que
`IsResponsableOrAdmin` (`authentication/permissions.py:14-21`, 614 usages / 156 fichiers) laisse
n'importe quelle permission d'écriture ouvrir TOUS les endpoints qu'il garde — le frontend gate
finement mais l'API directe réussit. C'est la MÊME classe de bug que **VX101** corrige côté
`decider_approbation`/`IsAnyRole` (endpoints disjoints, même remède `HasPermissionOrLegacy`) : ce
constat ÉTEND VX101, il n'est pas transcrit comme tâche séparée ici — voir VXD-J / `@coord VX101`
sous VX193 (VXD SEED transcrit avec la même classe de garde) pour le détail d'audit des viewsets
restants.

---

## AXE 1 — BEAUTÉ (VX121–VX158, 38 tâches survivantes sur 44 seeds ; 6 tuées + 1 fusionnée par le
grand-verdict — voir NE PAS FAIRE en fin de section pour le détail des kills/rognages)

**Sous-groupe VXD-E — Craft-physics & tokens (les fondations que 3 rounds n'ont pas atteintes)**

- [x] VX121 — **Zéro couleur hors token : le sweep CSS et JS, avec garde CI.** Trois strates de (@lane: frontend/ui-core)
  couleur échappent encore à tout token : (a) ~500 hex slate au niveau composant dans `index.css`
  (`.form-control`/`.modal-*` L900-1156, `.lines-table` L1184-1220, `.data-table` L830-862,
  `.lead-nav` L1002-1006, `.page-loading/.page-error` L727-739) ; (b) les 6 ombres d'épinglage
  `rgba(0,0,0,0.25)` du moteur `DataTable.jsx` L477/478/519/627/628/640 — seul noir pur de tout
  `ui/`, bande noire dure en dark mode sur la surface qui portera DevisList/FactureList ; (c) les
  constantes hex JS invisibles à tout grep CSS : `SCORE_COLORS` (`ListView.jsx:77-81`),
  `OWNER_PALETTE` (`CalendarView.jsx:36-39`), les 5 jalons hex de `ChantierTimeline.jsx:6-21`, la
  famille orpheline `--color-*` d'`AppointmentBooker.jsx:81-96` (fallbacks silencieux = rupture de
  theming), les Tailwind bruts `emerald/red` de `ProductionPage.jsx:228`. **Rogné (grand-verdict) :**
  retirer `SCORE_COLORS`/`OWNER_PALETTE`/`NAVY-GOLD` ChartsView (déjà couverts par VX26) et
  NAVY/GOLD PwaPrompts (déjà VX1). Survit : sweep ~500 hex composant d'index.css, ombres pin
  DataTable, hex JS ChantierTimeline/AppointmentBooker/ProductionPage, suppression du bloc CSS mort
  `.agent-*` (`index.css:2209-2270`, 0 consommateur JSX — **@coord VX4**, qui prévoyait de le
  re-tokeniser : la suppression prime, amender le Done= de VX4 d'une note), garde
  `scripts/check_hex.mjs` (grep hex hors `:root`/tokens, branchée dans frontend-lint — script
  maison, zéro dépendance). Files : `index.css`, `design/tokens.css`, `ui/datatable/DataTable.jsx`,
  `features/crm/stages.js`, `ChantierTimeline.jsx`, `AppointmentBooker.jsx`, `ProductionPage.jsx`,
  `scripts/check_hex.mjs` (nouveau). DoD : grep hex hors `:root` = 0 sur les blocs cités ; `grep
  rgba(0,0,0 ui/` = 0 ; dark mode cohérent sur 6 écrans témoins ; garde CI verte puis rouge sur un
  hex injecté. (T2 — L, sonnet) (@lane: frontend/ui-core)

- [x] VX122 — **La voix typographique : police de marque par défaut + échelle F121 réellement (@lane: frontend/ui-core)
  branchée + finesse française.** Quatre défauts d'une même cause : (a) `index.css:26` rend tout
  le legacy en `font-family: system-ui` alors qu'Archivo/Hanken Grotesk sont préchargées
  (`brand.css`) ; **rogné (grand-verdict) :** ce point (a) est déjà VX3 mot pour mot, ne pas le
  refaire. Survivent : (b) l'échelle F121 (`tokens.css:103-115`) a 4 usages, tous dans UIShowcase —
  câbler `.page-header h2` sur `--text-h1`/`--font-display`, classe `.text-eyebrow` unique
  consommant `--text-caption` (13+ recopies inline avec trackings divergents 0.04 vs 0.05em) ; (c)
  116 sites de libellés FR sans espace fine insécable avant `:`/`;`/`!`/`?` — helper `nbsp()` dans
  `lib/format.js` posé sur les 5 libellés les plus visibles (LeadCard tooltip, EcrituresPage,
  BudgetPage) ; (d) `max-w-prose` sur l'article KB (`ArticleDetail.jsx:321`, 0 `max-w`
  aujourd'hui). Files : `index.css:683-688,840-851`, `design/tokens.css`, `lib/format.js`,
  `features/kb/ArticleDetail.jsx:321`. DoD : les 3 écrans témoins (DevisList/CommercialDashboard/
  Reporting) rendent le même titre sans toucher leur JSX ; `nbsp('Priorité')` vérifiable par
  `codePointAt` ; e2e verts. (T2 — M, sonnet) (@lane: frontend/ui-core)

- [x] VX123 — **Plancher d'accessibilité visuelle : anneau de focus token-isé consommé partout + (@lane: frontend/ui-core)
  modes de contraste système.** Le token `--focus-ring` (`tokens.css:98`) et l'utilitaire
  `shadow-focus-ring` (L248) sont du code mort décoratif : **24 fichiers** primitifs (corrigé par
  le grand-verdict : pas « 40+ ») répètent en dur `focus-visible:ring-2 ring-ring
  ring-offset-2`, et 6 `outline:none` legacy orphelins subsistent dans `index.css` ; par ailleurs
  `grep forced-colors` = 0 et `prefers-contrast` = 0 — en mode contraste élevé Windows les
  bordures-ombres `--elevation-card` (box-shadow) disparaissent entièrement. Fix : une classe
  utilitaire unique `focus-ring` remplaçant les 24 chaînes (un seul point de vérité du halo), purge
  des `outline:none` non remplacés, puis `@media (forced-colors: active)` mappant carte/bouton/
  focus sur `CanvasText/Highlight/ButtonBorder` et `@media (prefers-contrast: more)` durcissant
  `--border`/`--muted-foreground`. Files : `design/tokens.css`, tous les primitifs `ui/*`
  (remplacement mécanique), `index.css`. DoD : `grep 'focus-visible:ring-2 focus-visible:ring-ring'
  ui/` ≈ 0 ; halo visible au Tab sur chaque contrôle ; émulation forced-colors → cartes/boutons
  délimités ; émulation prefers-contrast → bordures plus marquées ; scan axe (VX71) sans
  régression. (T2 — M, sonnet) (@lane: frontend/ui-core)

- [x] VX124 — **Craft-physics pack : les 4 micro-détails qui signent un produit investi.** Quatre
  absences prouvées par grep (0 résultat chacune) : (a) `caret-color` jamais posé — le curseur de
  saisie reste noir système sur le champ le plus regardé de l'ERP (générateur de devis) ; (b)
  toutes les ombres sont gris-nuit neutre — aucune ombre teintée brass au survol du CTA primaire ;
  (c) le tracking négatif fixe (-0.025em) sur-comprime les montants à 7 chiffres en grande taille ;
  (d) la police variable est chargée (`font-weight: 100 900`, `brand.css:9-17`) mais
  `font-variation-settings` = 0 dans tout le repo — le chiffre KPI de `Stat.jsx:26` pourrait « se
  solidifier » (wght 500→600 sur 400ms au montage, saut direct sous reduced-motion). Fix :
  `caret-color: var(--primary)` sur Input/Textarea/NumberInputs ; token `--shadow-primary-hover`
  (color-mix brass 35%) sur le seul variant `default` de Button ; règle
  `.tabular-nums.text-display/.text-h1 { letter-spacing: -0.01em }` ; transition wght sur Stat.
  Files : `ui/Input.jsx`, `ui/NumberInputs.jsx`, `ui/Textarea.jsx`, `ui/Button.jsx:27`,
  `ui/Stat.jsx`, `design/tokens.css`. DoD : curseur teinté visible au focus ; ombre du CTA ≠ gris
  neutre (preview_inspect) ; montant 7 chiffres moins collé (capture) ; `getComputedStyle` du Stat
  montre la transition de wght, neutralisée sous reduced-motion. (T3 — S/M, sonnet) (@lane:
  frontend/ui-core)

- [x] VX125 (already present) — **[DECISION] Gouvernance anti-monday : budget de densité de signaux + badge de (@lane: frontend/brand)
  maturité de module.** La plainte structurelle n°1 de monday.com 2026 (« density of statuses,
  colors, and columns… overwhelming ») est la trajectoire que VX construit un badge à la fois
  (VX84 cloche, VX86 approbations, VX98 fraîcheur, VX27 KPI) sans qu'aucune tâche ne pose de règle
  d'arbitrage ; la leçon Ramp-Travel (un module neuf médiocre contamine la perception du cœur
  mature) n'a aucun équivalent. Fix : un document court (< 30 lignes)
  `docs/design-density-budget.md` posant le plafond « 3 signaux ambiants simultanés par écran de
  liste, jamais deux signaux répétant le même chiffre », référencé depuis CODEMAP §4 comme
  contrainte transversale ; plus un `<BetaBadge>` discret optionnel sur la nav des modules jeunes
  avec critère objectif de retrait. Files : `docs/design-density-budget.md` (nouveau),
  `design/tokens.css` (commentaire), option `components/layout/Sidebar.jsx`. DoD : le document
  existe, cite le plafond, est référencé ; le CODEMAP est re-fingerprinté dans le même commit ;
  aucune tâche existante modifiée. (T3 — S, sonnet) (@lane: frontend/brand)

**Sous-groupe VXD-F — Primitives last-mile (la mécanique d'état que Button seul possède)**

- [x] VX126 — **L'état PRESSÉ propagé : 12+ contrôles cessent d'être morts au clic, courbes
  unifiées.** `grep active:` = Button uniquement : Switch, Slider, Segmented, Tabs, Checkbox,
  Radio, items Select/Combobox/MultiSelect/DropdownMenu/ContextMenu, cellules DatePicker — aucun
  retour pressé ; sur mobile 4G l'absence de feedback tactile fait re-taper. En plus :
  Checkbox/Radio sans `hover:` (cibles « froides » dans les listes denses), le pouce du Switch sans
  squish et le thumb du Slider sans halo au grab, et Switch/Progress héritent du défaut Tailwind
  `150ms ease` linéaire-ish pendant que Button câble `cubic-bezier(0.23,1,0.32,1)` — deux vitesses
  de mouvement côte à côte, Checkbox sans aucune transition de coche. Fix : utilitaire partagé
  `press` calqué sur le pattern prouvé `Button.jsx:20`
  (`[@media(hover:hover)]:active:scale-[0.98]` + assombrissement), posé sur tous les
  triggers/items ; `hover:border-primary/60` sur cases/radios ; squish Switch + halo/scale thumb
  Slider ; alignement de la courbe Button sur Switch/Progress + scale-in de coche Checkbox. Files :
  les 12 primitifs `ui/*` cités + un utilitaire partagé. DoD : test de rendu par contrôle
  assertant la classe pressée ; courbes identiques par `transition-timing-function` calculée ;
  rien sous `hover:none` ; e2e inchangés. (T2 — M, sonnet) (@lane: frontend/ui-core)

- [x] VX127 — **L'état LECTURE-SEULE existe enfin + EditableCell honnête (pending/erreur (@lane: frontend/ui-core)
  serveur/readOnly).** Aucun primitif ne distingue `readOnly` de `disabled` : une référence de
  devis ou un total TTC affiché en Input apparaît soit éditable soit grisé opacité 60 % (illisible,
  non copiable). Et `EditableCell.jsx:108` commit au blur sans état « enregistrement en cours »,
  sans rendu d'un rejet serveur (seule la validation locale L45-54 est gérée), sans mode
  lecture-seule par rôle — une perte de confiance silencieuse au cœur du DataTable. Fix : variant
  Tailwind natif `read-only:` sur Input/Textarea/Select (fond `bg-muted/40`, curseur default,
  texte pleine opacité, pas de ring éditable) ; EditableCell gagne un spinner discret pendant
  l'`await onSave`, rouvre avec message sur rejet, et une prop `readOnly` (double-clic sans effet).
  Files : `ui/Input.jsx`, `ui/Textarea.jsx`, `ui/Select.jsx`, `ui/datatable/EditableCell.jsx`. DoD :
  `<Input readOnly>` visuellement ≠ disabled, sélectionnable ; `onSave` lent → spinner ; `onSave`
  rejeté → cellule rouverte + message ; tests unitaires des trois états. (T2 — M, sonnet) (@lane:
  frontend/ui-core)

- [x] VX128 — **Comboboxes audibles : `aria-activedescendant` câblé (0 occurrence dans tout le (@lane: frontend/ui-core)
  repo).** `Combobox.jsx`, `MultiSelect.jsx`, `TimePicker.jsx` gèrent un curseur visuel
  (`data-cursor`, flèches) mais l'input `role="combobox"` ne pointe jamais l'option active — un
  utilisateur NVDA/VoiceOver entend « zone de liste » puis RIEN en parcourant ; c'est LE trou du
  pattern combobox selon WAI-ARIA APG, purement additif à corriger. Fix : id stable par option
  (`${listId}-opt-${i}`), `aria-activedescendant` posé sur l'input suivant le curseur,
  `aria-selected` déjà présent. Files : `ui/Combobox.jsx`, `ui/MultiSelect.jsx`,
  `ui/TimePicker.jsx`. DoD : test — ouvrir, flèche bas, `input.getAttribute('aria-activedescendant')`
  === id de la 2ᵉ option ; le scan axe (VX71) le détecte corrigé. (T2 — S/M, sonnet) (@lane:
  frontend/ui-core)

- [x] VX129 — **Primitives complétées : menus pro, Textarea adulte, Progress indéterminé, Avatar (@lane: frontend/ui-core)
  riche, UNE grammaire de chip.** Pack de complétude sur 6 primitifs, tous prouvés incomplets par
  grep : (a) menus sans `RadioItem`/`Sub`/`SubTrigger` (0 occurrence) ni slot raccourci —
  ContextMenu n'a même pas CheckboxItem ; (b) Textarea nu : resize navigateur, ni autoResize ni
  compteur `maxLength` ; (c) Progress sans état indéterminé, Stat avec glyphes texte `▲/▼` au lieu
  de lucide et sa propre mini-map de tons ; (d) Avatar taille fixe sans statut de présence,
  AvatarGroup sans « +N » ; (e) QUATRE grammaires de chip divergentes — Badge rounded-full, Tag
  rounded-md, StatusPill, jetons inline MultiSelect L144-158 ; (f) Popover/HoverCard sans flèche
  d'ancrage alors que Tooltip en a une (prop `arrow` opt-in). Fix : ajouts Radix habillés sur le
  pattern `menuContent`/`menuItem` existant, props additives, alignement des rayons/hauteurs de
  chip sur une base commune consommée par MultiSelect. Files : `ui/DropdownMenu.jsx`,
  `ui/ContextMenu.jsx`, `ui/Textarea.jsx`, `ui/Progress.jsx`, `ui/Stat.jsx`, `ui/Avatar.jsx`,
  `ui/Tag.jsx`, `ui/Badge.jsx`, `ui/MultiSelect.jsx`, `ui/Popover.jsx`, `ui/HoverCard.jsx`. DoD :
  menu radio exclusif + sous-menu + shortcut aligné à droite (tests de rôles) ; autoResize +
  compteur ; `<Progress indeterminate>` balaie et se fige sous reduced-motion ; `<AvatarGroup
  max={3}>` de 5 → « +2 » ; jetons MultiSelect et Tag partagent rayon/hauteur (inspection). (T2 —
  L, sonnet) (@lane: frontend/ui-core)

- [x] VX130 — **Le toast devient un objet de marque : tokens, icônes lucide, durées motion, (@lane: frontend/ui-core)
  registres réels.** `Toaster.jsx:13` délègue tout à sonner `richColors` : couleurs génériques hors
  tokens `--success/--warning/--info` (divergentes en dark), icônes internes sonner alors que TOUT
  le reste de l'app est lucide, durées indépendantes de `--motion-*`, et un vocabulaire binaire —
  503 `toast.error` / 360 `toast.success` / 1 info / 1 warning dans tout le repo, aucun registre
  destructif à délai d'annulation prolongé. Fix : retirer `richColors`, styler par type via
  `toastOptions.classNames` + tokens, injecter les icônes lucide
  (`CheckCircle2/AlertTriangle/Info`), surcharger la durée via `--motion-base`, formaliser
  `toastInfo`/`toastWarning` stylés + un registre destructif ≥ 6s, avec ≥ 8 poses réelles
  d'avertissement. Files : `ui/Toaster.jsx`, `lib/toast.js`, `index.css` (règle
  `[data-sonner-toast]`). DoD : toast succès dérivé de `--success` en clair ET sombre (parité
  Badge) ; même glyphe AlertTriangle que l'EmptyState d'erreur ; changer `--motion-base` affecte
  les toasts ; 4 variantes distinctes testées. (T2 — M, sonnet) (@lane: frontend/ui-core)

- [x] VX131 — **Des états qui disent vrai : `tone` sur EmptyState, CTA sur les listes principales, (@lane: frontend/orphans)
  page 403.** Trois trous du même système : (a) les 267 poses d'EmptyState partagent le wrapper
  gris neutre — un ÉCHEC de chargement est visuellement identique à « rien à afficher » ; pire,
  `DataTable.jsx:385` (erreur) garde l'icône grise quand `ErrorBoundary.jsx:38` la colore ; (b)
  ~207/267 EmptyState n'ont pas de CTA, y compris sur des listes qui ONT un bouton « Nouveau » dans
  leur toolbar (modèle parfait : `ClientList.jsx:347-356`) ; (c) `ui/NotFound.jsx` existe mais
  AUCUN `Forbidden`/403 — un refus de rôle retombe sur un toast technique ou rien. Fix : prop
  `tone` (`neutral|error|warning`) sur EmptyState calquée sur ErrorBoundary, migration de
  DataTable/ModuleDashboard ; passe CTA sur les ~15 listes principales (Stock, Tickets SAV,
  Installations…) ; `ui/Forbidden.jsx` jumeau de NotFound, câblé aux gardes de permission. Files :
  `ui/EmptyState.jsx`, `ui/datatable/DataTable.jsx:381-388`, `ui/Forbidden.jsx` (nouveau), ~15
  écrans de liste. DoD : `<EmptyState tone="error">` = icône sur fond destructif (3 tons testés) ;
  liste vide → même CTA que la toolbar (test) ; route refusée → écran 403 dédié (pas le 404). (T1 —
  M, sonnet) (@lane: frontend/orphans)

- [x] VX132 — **L'attente premium : shimmer, crossfade, squelettes honnêtes, anti-scintillement (@lane: frontend/ui-core)
  propagé, chargement long conscient.** Cinq défauts d'une même expérience : (a) `Skeleton.jsx:11`
  est le pulse Tailwind par défaut — pas de balayage lumineux directionnel (CSS pur, motion-safe
  gardé) ; (b) le passage squelette→contenu est un swap sec partout — pas de `<FadeSwap>`
  générique ; (c) le squelette DataTable affiche 6 lignes fixes quel que soit `pageSize` → saut
  brutal vers 50 lignes réelles (dériver `Math.min(pageSize, 12)`) ; (d) `useDelayedLoading` —
  fini, documenté, testé — n'est utilisé que sur 6 fichiers/265 pendant que 73 écrans affichent un
  Spinner nu qui scintille (propager aux ~15 listes principales) ; (e) la génération PDF premium
  (latence connue, la plus longue de l'app) montre un spinner muet — un hook `useRotatingLabel` fait
  tourner 3-4 libellés honnêtes (« Mise en page des schémas… ») toutes les ~2.5s, sans fausse barre
  de progression (ne touche QUE le bouton côté client, jamais le moteur — règle #4). Files :
  `ui/Skeleton.jsx`, `ui/FadeSwap.jsx` (nouveau), `ui/datatable/DataTable.jsx` (~L540-550),
  `hooks/useRotatingLabel.js` (nouveau), les call-sites `generer-pdf` de DevisList/FactureList, ~15
  écrans Spinner. DoD : shimmer visible clair+sombre, pulse identique sous reduced-motion ;
  chargement <300ms → aucun spinner (test promesse 100ms) ; squelette ∝ pageSize sans saut de
  scroll ; ≥ 2 libellés visibles sur le chemin PDF long. (T2 — L, sonnet) (@lane: frontend/ui-core)

**Sous-groupe VXD-F (suite) — Chorégraphie de mouvement**

- [x] VX133 — **Grammaire directionnelle des surfaces : chaque overlay entre par où il vit.** Un (@lane: frontend/motion)
  seul keyframe `pop-in` (translateY 4px + scale 0.97, conçu pour un popover ancré) sert 14
  primitifs aux géométries incompatibles : le `Sheet` latéral de 26rem « pop » du centre au lieu de
  glisser de son bord (`Sheet.jsx:32`, 13 consommateurs), alors que la preuve du bon glissement
  existe déjà en bespoke (`.ldp-panel`/`@keyframes ldpIn`, `index.css:3393-3407` — 2 usages,
  dupliqués par copier-coller) ; `BulkActionBar.jsx:23` fait `if (!count) return null` → JAMAIS
  d'animation de sortie malgré le commentaire qui prétend « glisser depuis le bas » ;
  `AccordionContent` n'anime pas sa hauteur (`--radix-accordion-content-height` = 0 occurrence) ;
  `TabsContent` swap sans crossfade. Fix : 4 keyframes `slide-in/out-{right,left,top,bottom}` +
  `accordion-down/up` dans tokens.css (mappés `--motion-*` donc annulés par reduced-motion),
  mapping `SIDE → animationClass` dans Sheet, migration de LeadDevisPanel/InstallationDetail sur
  `SheetContent side="right"` + suppression de `.ldp-*`, BulkActionBar monté en permanence avec
  état `visible` retardé (pattern exit-sans-lib) + slide-up, fondu court `--motion-fast` sur
  TabsContent. Files : `design/tokens.css`, `ui/Sheet.jsx`, `ui/Accordion.jsx`, `ui/Tabs.jsx`,
  `ui/datatable/BulkActionBar.jsx`, `pages/crm/leads/LeadDevisPanel.jsx`,
  `pages/installations/InstallationDetail.jsx`, `index.css` (−25 lignes ldp). DoD : Sheet
  `side="right"` translate en X ; grep `ldp-panel` = 0 ; désélectionner la dernière ligne montre
  une sortie glissée ; accordéon anime sa hauteur ; reduced-motion = instantané partout ; tests de
  rendu par côté. **@coord VX43** (Sheet.jsx partagé / bottom-sheets mobile). (T2/T3 — M/L, sonnet)
  (@lane: frontend/motion)

- [x] VX134 — **Chorégraphie de coquille : ⌘K, sidebar, route, badge, thème — cinq (@lane: frontend/motion)
  téléportations soignées.** Cinq surfaces de la coquille bougent « sec » : (a) la palette ⌘K
  réutilise le Dialog générique centré-zoomé — s'ancrer en haut avec un slide-down rapide
  `--motion-fast` ; (b) le liseré doré actif de la sidebar (`index.css:396-412`, pseudo-élément par
  item, 0 transition) téléporte entre items au lieu de glisser (fallback fondu si la mesure DOM est
  jugée invasive) ; (c) le contenu de route post-Suspense apparaît en cut dur — un fondu
  `key={pathname}` (pattern déjà utilisé par RouteErrorBoundary juste à côté,
  `router/index.jsx:198`) suffit, View Transition API notée en option future ; (d) le badge
  non-lus de `ChatBell.jsx:38` change de valeur toutes les 30s sans aucun signal — pulse scale
  1→1.25 UNIQUEMENT quand le total augmente ; (e) `applyTheme` bascule `.dark` d'un coup — le mode
  sombre OKLCH mérite une transition ≤ 200ms via classe transitoire, sans FOUC. Files :
  `providers/CommandPalette.jsx`, `ui/Dialog.jsx` (variante `command`),
  `components/layout/Sidebar.jsx`, `router/index.jsx`, `components/layout/ChatBell.jsx`,
  `design/theme.js`, `index.css`, `design/tokens.css` (keyframe `command-in`, `badge-pulse`). DoD :
  ⌘K ancrée haut plus rapide qu'un modal ; naviguer fait glisser/fondre le repère sidebar ;
  changement de route = fondu doux ; badge pulse seulement à l'incrément (test mock store) ;
  bascule de thème fluide, instantanée sous reduced-motion, classe transitoire retirée (test).
  **@coord axe3-VX190** (refonte cloche — ce seed ne touche que l'animation du compteur, pas son
  contenu). (T2/T3 — M, sonnet) (@lane: frontend/motion)

- [x] VX135 — **Mouvement piloté par JS rendu accessible + FLIP des listes.** La garde globale (@lane: frontend/motion)
  reduced-motion (`index.css:67-77`) ne neutralise QUE les animations CSS déclaratives : les
  transforms posés en JS par dnd-kit y échappent structurellement — le tilt `rotate(2deg)
  scale(1.02)` de la carte kanban tenue reste actif pour un utilisateur vestibulaire, aucun des 3
  kanbans ne passe `dropAnimation` (timing dnd-kit par défaut, désaligné des tokens), et la carte
  saute au tilt sans transition de grab ; le `Spinner` tourne en `animate-spin` nu pendant que
  Skeleton est correctement `motion-safe` ; et AUCUNE liste de l'app n'anime tri/filtre/ajout (0
  framer-motion, télé-portation des lignes). Fix : hook partagé `usePrefersReducedMotion()`
  (matchMedia + listener) consommé par les 3 kanbans (tilt désactivé, dropAnimation
  `{duration:180, easing:cubic-bezier(0.23,1,0.32,1)}` ou 1ms) ; `transition: transform 120ms
  var(--ease-out)` sur `.kb-drag-overlay .kb-card` ; `motion-safe:` sur Spinner avec repli
  statique lisible ; FLIP minimal sans dépendance dans DataTable (mesure
  getBoundingClientRect avant/après tri/filtre, translateY transitionné, plafonné < 200 lignes,
  désactivé par le hook). Files : `hooks/usePrefersReducedMotion.js` (nouveau),
  `pages/crm/leads/views/KanbanView.jsx`, `pages/installations/views/KanbanView.jsx`,
  `features/gestion_projet/components/TachesKanbanView.jsx`, `index.css`, `ui/Spinner.jsx`,
  `ui/datatable/DataTable.jsx` (hook `useRowFlip`). DoD : reduced-motion émulé → plus de
  tilt/rotation pendant le drag, spinner figé ; dépose calée sur les tokens ; trier une colonne
  fait glisser les lignes (test non-régression `datatable.test.mjs`). (T2/T3 — M/L, sonnet ; opus
  si le hook FLIP doit se partager avec ARC49/53 — coordonner, ne pas dupliquer) (@lane:
  frontend/motion)

- [x] VX136 — **Scroll-timeline natif : reveal des cockpits + progression des formulaires (@lane: frontend/motion)
  longs.** `grep view-timeline|animation-timeline` = 0 : aucun usage du mécanisme 2026 (compositor
  thread, zéro JS d'orchestration, progressive enhancement pur). Deux poses à haute valeur : (a)
  les cartes KPI de `ModuleDashboard` se révèlent (translateY 8px→0 + fondu) via `@supports
  (animation-timeline: view())`, fallback état final statique ; (b) une barre `ScrollProgress` de
  2px en haut des deux formulaires-fleuves (LeadForm 1297 l., DevisGenerator 2319 l.) via
  `animation-timeline: scroll(nearest)`. Files : `ui/module/ModuleDashboard.jsx`,
  `ui/ScrollProgress.jsx` (nouveau), `pages/crm/LeadForm.jsx`, `pages/ventes/DevisGenerator.jsx`,
  `index.css` (`.reveal-on-scroll`). DoD : Chromium — reveal au scroll + barre qui grandit
  0→100 % ; Firefox/Safari <18 — apparition instantanée, aucune erreur ni layout cassé ;
  reduced-motion désactive la timeline. (T2/T3 — M, sonnet) (@lane: frontend/motion)

**Sous-groupe VXD-G — Ventes : le chemin de l'argent (l'écran vendeur le plus vu du produit)**

- [x] VX137 — **La table de lignes du générateur sort du HTML brut. @after VX17.** `DevisGenerator.jsx`
  L1965-2091 : `<input className="form-control form-control-sm">` natifs alors que le MÊME fichier
  utilise Input/Select/Textarea du design system dans ses 9 autres cartes ; hex codés dans le JSX
  restants après VX17 (le sweep tokens/couleurs `.gen-metric*`/`.lines-table*` est déjà fait par
  **VX17** — ce delta ne recouvre QUE le remplacement `<input class="form-control">` natif par
  `ui/Input` dans la table). Attention absolue : le formulaire reste `noValidate`/`step="any"`
  (règle CLAUDE.md, gardé par test) et l'indicateur de marge (`prix_achat`) reste generator-only.
  Files : `pages/ventes/DevisGenerator.jsx` (L2000-2192). DoD : `grep "style={{ color:"
  DevisGenerator.jsx` = 0 ; capture dark mode avant/après ; test « saisie jamais rejetée » vert.
  (T2 — S, sonnet) (@lane: frontend/ventes)

- [x] VX138 — **L'aperçu de simulation devient un comparateur : Sans/Avec groupés, chiffres héros (@lane: frontend/ventes)
  stables, totaux hiérarchisés, CTA sticky, cartes selon le mode.** Le moment de vente en direct
  souffre de cinq défauts convergents : (a) jusqu'à 12 `MetricCard` dans UNE grille homogène — les
  paires Sans/Avec batterie ne sont reliées que par une étoile noyée → 2 colonnes nommées « Option
  1/2 », recommandation en liseré de colonne ; (b) les chiffres ROI héros
  (`.gen-metric-value`/`.gen-kwp`, `index.css:2577-2586/2692-2697`) n'ont AUCUN `tabular-nums` — ils
  tremblent horizontalement pendant la frappe devant le client, et `fmtNum` local (L79) duplique
  `formatNumber` sans jamais importer `lib/format.js` ; (c) la chaîne Sous-total→Remise→Total
  HT→TVA→TTC est plate à l'écran alors que le PDF la hiérarchise — appliquer une progression
  `text-small`→`text-body medium`→`text-h3 semibold+primary` avec les paliers F121 existants ; (d)
  `.gen-actions-sticky` n'est sticky QUE sous media query mobile — bandeau sticky desktop affichant
  le TTC courant (dérivé de `totals` déjà en mémoire) + bouton condensé ; (e) les cartes non
  pertinentes pour le mode actif gardent le même poids — « Multi-propriétés » développée par défaut
  même en agricole : accordéon replié, jamais masqué. Files : `pages/ventes/DevisGenerator.jsx`
  (L79, L1810-1844, L2093-2194, L2251-2273, L1886-1961), `index.css` (blocs `.gen-*`). DoD : mode
  « Les deux » → 2 colonnes alignées ; les chiffres ne tremblent plus (glyphes à largeur fixe, test
  rendu) ; 3 paliers visuels sur les totaux, TTC point focal ; barre sticky au scroll desktop, même
  handler de soumission ; bloc multi-propriétés replié par défaut en agricole. (T2 — L, sonnet)
  (@lane: frontend/ventes)

- [x] VX139 — **Deux éditeurs de devis, UNE présentation des totaux et UNE devise. @coord VX75.**
  Le même métier (lignes + remise + TVA + totaux) rend différemment selon le point d'entrée :
  `DevisForm.jsx` L372-395 (propre, tokens, suffixe « DH » codé en dur `toFixed(2)`) vs
  `DevisGenerator` `.gen-total-*` (hex inline, suffixe « MAD ») — le vendeur qui crée puis édite
  voit deux présentations de prix du même document. Fix : extraire
  `features/ventes/QuoteTotalsSummary.jsx` (props lines/totals/discountPct/tauxTva) consommé par
  les deux écrans, formaté par `formatMAD` de `lib/format.js` (une seule devise affichée), hérite
  de la hiérarchie de poids de VX138. Files : `features/ventes/QuoteTotalsSummary.jsx` (nouveau),
  `pages/ventes/DevisForm.jsx` (L372-395), `pages/ventes/DevisGenerator.jsx` (L2093-2194). DoD :
  `grep '"DH"\| DH' DevisForm.jsx` = 0 ; les deux écrans rendent le même bloc de totaux (mêmes
  valeurs, même libellé de devise) ; tests de rendu des deux écrans verts. (T2 — M, sonnet) (@lane:
  frontend/ventes)

- [x] VX140 — **DevisList : 14 boutons deviennent 4 + un menu, la cellule Référence respire.**
  Deux défauts jumeaux de la liste la plus dense : (a) jusqu'à 14 boutons d'action de poids
  identique par ligne brouillon (L1428-1707) alors que sa liste sœur FactureList a DÉJÀ résolu le
  problème avec un `DropdownMenu` Actions (L1140-1181) ; (b) la cellule Référence empile jusqu'à 7
  éléments hétérogènes (L1240-1331) en colonne verticale de 6-8 lignes. Fix : 3-4 actions primaires
  visibles selon statut + menu « Plus d'actions » (même primitive que FactureList) ; cellule à 2
  niveaux — ligne 1 référence+badges de version en `text-sm` gras, ligne 2 métadonnées en `text-xs
  muted` séparées par ` · `, chips de documents liés dans une info-bulle au survol. Files :
  `pages/ventes/DevisList.jsx` (L1240-1331, L1428-1707). DoD : ≤ 5 boutons visibles par ligne +
  menu ; un devis à historique complet tient sur 2 lignes visuelles (snapshot) ; e2e clic
  Éditer/Envoyer/PDF verts avec les mêmes sélecteurs `ap-*`. (T2 — M/L, sonnet) (@lane:
  frontend/ventes)

- [x] VX141 — **`DocumentStageTrack` : le statut devient un parcours.** `StatusPill` est un fait (@lane: frontend/ventes)
  isolé (point + badge) ; rien dans DevisList/FactureList ne visualise la CHAÎNE
  brouillon→envoyé→accepté→BC→facturé→chantier — un devis accepté sans BC n'est signalé qu'en
  texte. Fix : petit composant `<DocumentStageTrack current stages>` — piste horizontale de 5-6
  puces reliées, franchies cochées, courante remplie, bloquée en rouge — posé dans la cellule
  Statut de DevisList à côté du StatusPill existant. Strictement la couche statuts DOCUMENT (règle
  #4) ; jamais les stages STAGES.py (règle #2) — les deux couches ne se mélangent pas. Files :
  `ui/DocumentStageTrack.jsx` (nouveau), `pages/ventes/DevisList.jsx` (L1375-1425). DoD : devis
  accepté avec BC annulé → point « BC » rouge sur la piste ; test de rendu par statut ; aucune clé
  de stage CRM importée. (T2 — M, sonnet) (@lane: frontend/ventes)

- [x] VX142 — **FactureList & cousins : toolbar rangée, action recommandée trouvable, primitives
  cohérentes.** Quatre finitions du même sous-module : (a) la toolbar FactureList aligne 8
  contrôles dont 4 variantes d'export à plat, et « Journal comptable » passe par un
  `window.prompt()` texte libre (L625-629) — un menu « Exporter » (primitive DropdownMenu déjà dans
  le même fichier) + un petit Dialog mois/trimestre ; (b) `nextBestAction()` (L98-104) est calculé
  mais rendu seulement par `variant=default` sur des boutons à position mouvante — lui réserver le
  PREMIER slot de la rangée avec icône + halo tokenisé, ordre stable ; (c) `RelancesPage.jsx`
  L217-227 contient le SEUL `<select>` HTML natif de tout `pages/ventes/` → composant `Select` ;
  (d) `FactureKanbanBoard.jsx` L47 répète le StatusPill sur chaque carte d'une colonne qui EST le
  statut → remplacer par une info utile (échéance ou montant dû). Files :
  `pages/ventes/FactureList.jsx` (L596-667, L1084-1182), `pages/ventes/RelancesPage.jsx`,
  `pages/ventes/FactureKanbanBoard.jsx`. DoD : toolbar à 5 groupes ; plus de `window.prompt` ;
  l'action recommandée est toujours en position 1 avec style distinct (test par statut) ; 0 select
  natif dans le dossier ; carte kanban sans statut redondant (snapshot). (T2 — M, sonnet) (@lane:
  frontend/ventes)

**Note d'exécution (annexe de VX75, jamais une tâche séparée — grand-verdict §d, S23) :** en plus de
son propre périmètre, VX75 doit aussi couvrir ces sites de niveau CELLULE, invisibles aux audits
d'écran : sous-ligne `Facturé {d.solde.facture} / Payé … / Restant … MAD` (`DevisList.jsx:1371`)
rendue en montants BRUTS ; colonne prix des produits archivés (`StockList.jsx:846-848`, `12500.00
DH` — point décimal anglais, zéro séparateur) ; 31 appels directs `toLocaleDateString` qui
contournent `formatDate` sur les écrans ventes/stock ; `fmtNum2` local (`StockList.jsx:49`) qui
duplique `formatNumber` ; la référence `DEV-202607-0012` (lue à voix haute au client) sans
`tabular-nums`/slashed-zero (`DevisList.jsx:1241`, `FactureList` idem) alors que `.tabular-nums`
inclut déjà `slashed-zero` (`tokens.css:296-299`). Files à ajouter au Done= de VX75 :
`pages/ventes/DevisList.jsx` (1241, 1283, 1315-1327, 1353-1394, 1371, 1734),
`pages/ventes/FactureList.jsx` (722, 742, 1026, 1047), `pages/stock/StockList.jsx` (49, 515, 843,
846-848). [DECISION] option non retenue par défaut : police mono auto-hébergée (~15KB woff2
subset) pour les identifiants (`--font-mono`) — à soumettre au fondateur avant tout build.

**Sous-groupe VXD-H — CRM : l'écran le plus fréquenté**

- [x] VX143 — **LeadForm refondu : un seul langage de formulaire dans le module CRM. @after
  VX89.** Le plus gros formulaire du repo (1297 l., 9-11 sections) redéfinit ses propres
  `Sec`/`Txt`/`Sel` locaux (L74-118) sur des classes hex-brutes, quand `ClientForm.jsx:244-497` — à
  un clic — compose proprement `FormSection`/`FormField` (a11y `aria-invalid`/`aria-describedby`
  automatique). S'y ajoutent : sections sans AUCUNE frontière visuelle, distinguées par la seule
  emoji 👤📈💡 (`.form-section` = flex nu, `index.css:1159-1163`) ; rail de navigation gauche en hex
  figés `#dbeafe/#1d4ed8` (`index.css:1002-1006`), sans barre d'accent, sans écho des icônes de
  section, sans indicateur de contenu (« Doublons » n'affiche jamais son compte) ; et le bouton
  « Concevoir la toiture (3D) » dupliqué verbatim aux L685-691 ET L994-1001. Fix : migration
  `Sec/Txt/Sel → FormSection/FormField/Input/Select` (pattern démontré par ClientForm, présentation
  pure — scroll-spy `data-nav-id` et verrouillages métier intacts) ; traitement de carte sur
  `.form-section` + icônes lucide au lieu d'emoji ; rail tokenisé `border-left: 3px solid
  var(--primary)` + même icône que la section + badges de contenu ; suppression du doublon 3D.
  Files : `pages/crm/LeadForm.jsx` (L74-118 + ~60 usages + L685-691/994-1001 + rail L733-741),
  `index.css` (`.form-section*`, `.lead-nav`). DoD : `grep "Txt fields=" LeadForm.jsx` = 0 ; chaque
  section a une séparation visible (preview_inspect) ; grep `#dbeafe|#1d4ed8` = 0 ; le bouton 3D
  apparaît une fois quel que soit le scroll ; `LeadForm.test.jsx` vert. (T2 — L, sonnet) (@lane:
  frontend/crm)

- [x] VX144 — **Hiérarchie de lecture des cartes et vues CRM : montrer moins pour dire plus.
  @coord VX89/VX45/VX51.** Cinq défauts « tout est montré, rien n'est priorisé » : (a) `LeadCard`
  empile jusqu'à 9 modules/6 badges simultanés sur 272px — fusionner les 3 badges de statut
  (perdu/expiré/inactif) en UN emplacement par priorité, reléguer le secondaire au survol (le
  pattern « +N autres » existe déjà dans `CalendarView.jsx:237-244`, jamais appliqué à la carte) ;
  (b) `ListView` rend 12-13 colonnes au poids identique — modificateur `.lv-col-secondary` (muted,
  non gras) sur Score/Canal/Ville/Tags ; (c) la cellule Client de `ClientList` (L157-168) wrap
  nom+pastille+badge ICE sans ordre garanti à 200px — empilement 2 lignes déterministe ; (d) les
  « leads sans date » sont présentés en note de bas de page neutre (`CalendarView.jsx:261-283`) —
  accent `--warning` + icône ; (e) `ChartsView` rend 4 graphiques au poids strictement égal —
  l'entonnoir par étape passe en pleine largeur. **Rogné (grand-verdict) :** retirer la fusion des
  badges LeadCard en une pilule prioritaire (déjà VX24) ; réduire la démotion des colonnes
  secondaires ListView (recoupe déjà VX7 calm-color) — survivent (c), (d), (e) intégralement + (a)
  et (b) réduits à leur delta non couvert. Files : `pages/crm/leads/views/LeadCard.jsx` (L113-137),
  `pages/crm/leads/views/ListView.jsx`, `pages/crm/ClientList.jsx` (L157-168),
  `pages/crm/leads/views/CalendarView.jsx` (L261-266), `pages/crm/leads/views/ChartsView.jsx`
  (L139-286), `index.css` (`.kb-badge-*`, `.lv-col-secondary`, `.cal-undated-label`,
  `.ch-card-wide`). DoD : fixture triple-drapeau → exactement 1 badge (`querySelectorAll` === 1) ;
  couleur calculée des colonnes secondaires plus claire ; à 200px le badge passe sous le nom
  (bounding box) ; `.cal-undated-label` porte `var(--warning)` ; la carte entonnoir est plus large
  que les 3 autres en desktop, empilée en mobile. (T2 — M, sonnet) (@lane: frontend/crm — @after
  VX89)

- [x] VX145 — **Barres d'action CRM : groupes, risque perçu, désencombrement. @after VX89.** Trois
  toolbars du même module sans hiérarchie : (a) `BulkActionBar` leads rend 11-12 boutons
  identiques — grouper en 3 clusters séparés (éditions de champ / cycle de vie / export+destructif)
  par `border-left` + gap ; **rogné (grand-verdict) :** le regroupement en clusters de
  BulkActionBar recoupe déjà VX20 — ne pas refaire ce point isolément, seuls (b) et (c) survivent.
  (b) DONE — l'en-tête `LeadsPage` montrait 6 actions de même poids pour des fréquences très
  différentes ; Doublons/Importer/Exporter démotés dans un menu « ⋯ » (`DropdownMenu`, même pattern
  que `ListView.jsx`), l'en-tête ne garde que « + Nouveau lead », « ⚡ Express », le bouton « ⭐
  Enregistrer cette vue » et le ViewSwitcher, séparés par `.lp-header-sep` qui isole le ViewSwitcher
  comme cluster de mode. (c) DONE — le bloc « vues enregistrées » était copié-collé entre
  `ClientList.jsx` et `LeadsPage.jsx` et occupait une rangée pleine largeur même vide ; extrait en
  `components/SavedViewsBar.jsx` (chips, rend `null` si `savedViews.length === 0` → 0 rangée dédiée)
  + `SaveViewButton` (déclencheur, placé par chaque écran dans SA rangée déjà existante — en-tête
  pour LeadsPage, rangée Segmented pour ClientList — jamais dans une rangée à lui seul) ; le hook
  `useSavedViews` client reste inchangé dans chaque écran (formes différentes : filters+view vs
  typeFilter). Files : `pages/crm/leads/LeadsPage.jsx`, `pages/crm/ClientList.jsx`,
  `components/SavedViewsBar.jsx` (nouveau), `components/SavedViewsBar.test.mjs` (nouveau),
  `index.css`. DoD : en-tête = 3 contrôles + 1 menu ⋯ dont chaque action reste déclenchable (test de
  source `node --test` — pas de RTL installé dans ce lane, cf. convention `MesEquipesCard.test.mjs`) ;
  0 rangée dédiée quand `savedViews.length === 0`. (T2 — M, sonnet) (@lane: frontend/crm — @after VX89)

- [x] VX146 — **`/calendrier` rejoint le design system : un seul calendrier mensuel dans l'app.** (@lane: frontend/crm)
  `pages/CalendarPage.jsx` (292 l., l'agenda global qui agrège poses/interventions/maintenance/
  activités) est construit à 100 % en `style={{}}` avec hex bruts (`#0d1b3e`, `#e2e8f0`,
  `#dc2626`…) et n'importe AUCUN composant `ui/` — alors qu'une grille mensuelle tokenisée existe
  littéralement dans le même repo (`.cal-grid/.cal-cell/.cal-weekday`, `index.css:3845-3891`,
  consommée par `leads/views/CalendarView.jsx`) : deux calendriers, un poli, un brut. Fix : porter
  le balisage sur le vocabulaire `.cal-*` existant (l'étendre pour les 5 types d'événements +
  légende + panneau d'abonnement), les hex de `TYPES` (L11-17) deviennent des classes par type
  analogues à `STAGE_COLORS`. Files : `pages/CalendarPage.jsx` (entier), `index.css` (extension du
  bloc `.cal-*`). DoD : grep hex littéral dans le fichier = 0 hors constantes mappées ; rendu
  visuel équivalent (preview_screenshot avant/après) ; dark mode correct. (T2 — M, sonnet) (@lane:
  frontend/crm)

- [x] VX147 — **LeadsPage et ses 4 vues parlent enfin le même langage d'état.** L'écran le plus (@lane: frontend/crm)
  fréquenté du CRM rend son chargement/erreur en `<p className="page-loading/page-error">` brut,
  stylé en hex codés en dur (`index.css:727-739`) — hors de tout le système d'états ; et ses 4 vues
  traitent « 0 lead » de 4 façons (Kanban/List/Carte en texte brut, ChartsView seule en
  `EmptyState` correct). Fix : remplacer L313-325 par `StateBlock`/`EmptyState`+`Skeleton`,
  supprimer `.page-loading/.page-error` d'index.css, unifier les 3 vues texte-brut sur `EmptyState`
  (calqué sur ChartsView:105-118, la seule déjà correcte). Files :
  `pages/crm/leads/LeadsPage.jsx` (L313-325), `pages/crm/leads/views/KanbanView.jsx` (L147),
  `ListView.jsx` (L484), `CarteView.jsx` (L99), `index.css` (L727-739). DoD : `grep
  page-loading|page-error src/` = 0 ; les 4 vues montent le même composant pour `leads=[]` (test
  rôle status/alert) ; sélecteurs e2e intacts. (T2 — M, sonnet) (@lane: frontend/crm)

**Sous-groupe VXD-D — Ops & insight : les nombres sont le héros**

- [x] VX148 — **Le kit `ui/charts` réellement adopté : fin des 3 thèmes recopiés et des rapports (@lane: frontend/orphans)
  sans graphique.** Le kit maison (AreaSansAxe/BarArrondie/KpiSpark/ChartTooltip/ChartEmpty, thémé,
  testé, reduced-motion géré) est contourné par les écrans d'insight les plus importants :
  `Reporting.jsx` (L7-10, 39-49, radius codé `[0,6,6,0]` L384, KPI sans sparkline), `Rapports.jsx`
  et `Journal.jsx` redéclarent chacun leur objet tooltip quasi identique — 3 copies du même
  dictionnaire de style ; `PilotageStock.jsx` (L189-284) et 5 des 6 rapports de `Rapports.jsx`
  rendent des données comparatives en `<table>` pures ; `ProductionPage.jsx` — l'écran le plus
  consulté du dossier monitoring — n'a AUCUN graphique quand ses 4 voisins directs en ont un ; et
  `ChartEmpty` a 0 site d'appel dans tout `pages/**`. Fix : migrer les 3 fichiers sur le kit
  (supprimer les tooltips locaux, `BAR_RADIUS_H` partout), ajouter un `BarArrondie`/`AreaSansAxe`
  AU-DESSUS des tables de PilotageStock/Rapports (la table garde le détail), une courbe de
  tendance kWh sur ProductionPage (pattern `OmAnalyticsPage.jsx:151-162`), brancher `ChartEmpty`
  sur les cartes de graphes vides de Dashboard/CommercialDashboard/Cohorts. La palette
  catégorielle elle-même reste VX41 — ce seed APPLIQUE le kit existant. Files : `pages/Reporting.jsx`,
  `pages/Rapports.jsx`, `pages/Journal.jsx`, `pages/stock/PilotageStock.jsx`,
  `pages/monitoring/ProductionPage.jsx`, `pages/Dashboard.jsx`,
  `pages/reporting/CommercialDashboard.jsx`. DoD : `grep "from 'recharts'"` sur les 3 fichiers ne
  montre plus que les formes non couvertes ; une seule définition de tooltip dans `pages/` ;
  chaque section citée affiche graphe + table ; `ChartEmpty` rendu quand dataset vide (tests). (T2
  — L, sonnet) (@lane: frontend/orphans)

- [x] VX149 — **Un seul accent de statut : `StatusAccentCard` + le terrain + le micro-pack ops.**
  La « carte à accent coloré par statut » est réinventée en parallèle :
  `InterventionsPage.jsx:68-145` (`.kb-*/.kc-*`, `--kb-accent` — le bon craft de référence) vs la
  `CalendarView` inline d'`InstallationsPage.jsx:58-217` (`.cal-*`, `style={{background: dot}}`) —
  extraire `ui/StatusAccentCard.jsx` consommé par les deux ; « Ma journée » technicien
  (`MaJourneePage.jsx:77-113`) reste une liste plate sans différenciation par `type_intervention` —
  poser le même accent + `text-amber-600` → `text-warning`. Micro-pack de dédup dans la même
  passe : `FournisseurFiche360.jsx:43-62` redéfinit Card/Stat localement → imports `ui/` ;
  `ChantierPhotos.jsx:141-190` vignettes `size-16` fixes → bascule densité compact/confortable en
  Segmented ; `BulkProductBar.jsx:27-37` réinvente un bouton-onglet sur fond sombre → variant
  `Segmented` partagé ; `ChantierGateTimeline.jsx:36-38` double mécanisme classe+style inline
  redondant → suppression. Files : `ui/StatusAccentCard.jsx` (nouveau),
  `pages/interventions/InterventionsPage.jsx`, `pages/installations/InstallationsPage.jsx`,
  `pages/interventions/MaJourneePage.jsx`, `pages/stock/FournisseurFiche360.jsx`,
  `pages/installations/ChantierPhotos.jsx`, `pages/stock/BulkProductBar.jsx`,
  `pages/installations/ChantierGateTimeline.jsx`. DoD : les deux écrans kanban/calendrier
  consomment le même composant (tests non régressés) ; chaque ligne de Ma journée porte un accent
  par type ; fiche 360 sur primitives partagées ; 40+ photos lisibles en densité compacte ;
  `data-testid="ch6-stage"` intact. (T2 — M/L, sonnet) (@lane: frontend/orphans)

**Sous-groupe VXD-J — Fondation & âme de marque**

- [x] VX150 — **Le login re-signé : la première impression cesse de contredire le système.** (@lane: frontend/brand — delta sur VX34)
  `Login.jsx` est une île : 100 % `style={{}}` inline avec les hex d'une ANCIENNE marque
  (`#1863DC`/`#F5C100`), fond animé « TAQINOR » en `Arial Black` (L46) au lieu de la police de
  marque, œil mot-de-passe et alerte en émojis bruts `👁️/🙈/⚠️` (L240, L292), et un
  `requestAnimationFrame` PERMANENT (`BouncingBackground` L71-85) sans garde
  `prefers-reduced-motion` ni throttle `visibilitychange`. **Rogné (grand-verdict) :** VX34 possède
  déjà la MISE EN PAGE cockpit du login (mêmes hex, mêmes emojis→lucide, même garde reduced-motion
  sur BouncingBackground) — ne conserver que le delta non couvert : wordmark `Arial Black` → police
  de marque, et pause `visibilitychange` du rAF (2 lignes ajoutées au Done= de VX34, pas un
  chantier séparé). Files : `pages/Login.jsx` uniquement. DoD : le wordmark utilise la police de
  marque ; le rAF de fond se met en pause hors onglet actif (test mock `visibilitychange`).
  (T3 — S, sonnet) (@lane: frontend/brand — delta sur VX34)

- [x] VX151 (already present) — **Paramètres : 24 onglets deviennent une surface de réglages navigable.** `TABS` (@lane: frontend/brand)
  (`peConstants.js` L27-50) + 3 onglets locaux = 24 onglets plats dans UN `<TabsList
  overflow-x-auto>` (L801) — ~9-10 visibles à 1280px, scroll horizontal à l'aveugle sans
  fade/chevron ; et le bouton « Enregistrer » n'existe que sur 4/24 onglets, chaque section ayant
  SA convention de persistance sans aucune affordance préalable. Fix : champ `group` par entrée de
  TABS (4-5 méta-catégories : Identité & documents / Vente & CRM / Terrain & stock / Sécurité &
  système / Avancé) rendues en navigation à 2 niveaux, CHAQUE clé `tab` existante conservée
  (routing/tests intacts) ; badge/ligne contextuelle par section (« Modifications enregistrées
  immédiatement » vs bouton visible). Files : `pages/parametres/ParametresEntreprise.jsx`
  (L799-808, L829-872), `pages/parametres/peConstants.js`. DoD : les 24 clés restent accessibles
  (`tab===…` inchangé) ; hiérarchie 2 niveaux visible ; chaque onglet annonce son modèle de
  sauvegarde avant édition ; recherche fonctionnelle. (T2 — M, sonnet) (@lane: frontend/brand)

- [x] VX152 — **Fin des moteurs de table parallèles : GED, Admin, ClientDetail, OCR
  convergent.** Quatre modules contiennent chacun DEUX systèmes de table à deux clics l'un de
  l'autre : le point d'entrée GED (`GedNavigator.jsx:391-470`, `GedSearch.jsx:147-181`) rend en
  `<table class="data-table">` hex-legacy pendant que les écrans avancés du MÊME module
  (Approbation/Corbeille) utilisent `ListShell` moderne ; `RolesManagement.jsx:489` est une table
  HTML brute (constante `th` répétée 16×) pendant que `UsersManagement.jsx:438` — même dossier
  admin — a le DataTable complet ; `ClientDetailPanel.jsx:19-55` fabrique un TROISIÈME moteur
  `DocTable` à la main pour Devis/Factures/Chantiers ; `OcrUpload.jsx` L222-235/248-267 duplique
  deux `<table>` Tailwind répétitives. Fix : porter chaque surface sur le moteur déjà utilisé par
  son voisin direct (ListShell pour GED, DataTable pour les rôles — liste seulement, la grille de
  permissions reste —, `Table` partagée pour ClientDetail, `KeyValueTable` partagé pour OCR).
  Files : `features/ged/GedNavigator.jsx`, `features/ged/GedSearch.jsx`,
  `pages/admin/RolesManagement.jsx` (L460-582), `pages/crm/ClientDetailPanel.jsx`,
  `pages/ia/OcrUpload.jsx`. DoD : grep `data-table` = 0 sur les 2 fichiers GED ; recherche/tri
  disponibles sur les rôles, dialogue de réassignation intact ; `grep "<table"
  ClientDetailPanel.jsx` = 0 ; un seul point de rendu FIELD_LABELS dans OcrUpload ; tests existants
  verts. (T2 — L, sonnet) (@lane: frontend/brand)

- [x] VX153 (already present) — **GED/IA micro-pack : navigation réunifiée, tailles sémantiques, temps lisible.** (@lane: frontend/brand)
  Trois finitions du même périmètre : (a) « Documents » et « GESTION DOCUMENTAIRE » sont deux
  sections de menu pour UN espace conceptuel — un contournement technique de collision de clé
  assumé en commentaire (`module.config.jsx:36`) — fusionner/adjacenter les deux groupes sans
  toucher au routing `/ged/*` ; (b) `GedNavigator/GedSearch` utilisent `text-[13px]`/`text-[11px]`
  arbitraires au lieu de `text-sm`/`text-xs` ; (c) l'onglet Historique d'`AgentActions.jsx`
  (L118-198) liste des logs chronologiques en cartes plates — grouper par jour
  (Aujourd'hui/Hier/date), `confirmed_at` est déjà servi. Files : `features/ged/module.config.jsx`,
  `features/ged/GedNavigator.jsx`, `features/ged/GedSearch.jsx`, `pages/ia/AgentActions.jsx`. DoD :
  les deux groupes de nav adjacents/fusionnés ; grep `text-\[1[0-9]px\]` = 0 sur les 2 fichiers ;
  logs groupés par jour (`AgentActions.historique.test.jsx` vert). (T2 — S/M, haiku ; sonnet pour
  la décision de nav) (@lane: frontend/brand)

- [x] VX154 (already present) — **`TaqinorMark` + `SolarLoader` : le mot-symbole soleil-éclair porté dans l'app, (@lane: frontend/brand)
  chaque attente signée.** Le glyphe le plus distinctif de la marque — le soleil rayonnant à
  éclair azur de `public/favicon.svg` — n'existe dans l'app React NULLE PART (grep = 0) : le header
  porte un `<Zap>` lucide générique sur carré jaune (`Header.jsx:60-62`), et chaque attente est
  anonyme (Spinner cercle gris, RouteFallback silhouette). Fix : composant `<TaqinorMark>` SVG
  inline tokenisé (rayons `var(--primary)`, éclair `var(--info)`, props size/animate) remplaçant
  le Zap du header ; `<SolarLoader>` — le mark dont les rayons s'illuminent en séquence, CSS pur,
  statique sous reduced-motion — posé sur `RouteFallback` et les chargements plein-écran (JAMAIS
  les spinners inline de bouton) ; shimmer skeleton légèrement teinté brass (@coord VX132). Files :
  `ui/TaqinorMark.jsx` (nouveau), `ui/SolarLoader.jsx` (nouveau), `components/layout/Header.jsx`,
  `components/RouteFallback.jsx`, `index.css` (keyframe `sun-rise`). DoD : header = soleil-éclair
  (snapshot, aria/data-* intacts) ; transition de route = petit soleil animé, figé sous
  reduced-motion ; rendu correct clair/sombre via tokens. (T3 — M, sonnet) (@lane: frontend/brand)

- [x] VX155 — **La gradation émotionnelle du funnel : signé célébré, envoyé/payé reconnus.** (@lane: frontend/brand — @with VX40)
  Le moment le plus important de tout l'ERP — un devis solaire SIGNÉ — est muet :
  `SigneDialog.jsx:190-213` appelle `accepterDevis` puis les 2 appelants (`LeadForm.jsx:1274`,
  `LeadsPage.jsx:485`) ferment la modale + refetch, zéro reconnaissance pour une affaire de 150 000
  MAD ; et les jalons intermédiaires (devis envoyé, facture payée) sont des `toast.success`
  identiques à « ligne supprimée ». **Fusionné (grand-verdict) :** ce seed enrichit directement le
  Done= de **VX40** (qui câble déjà SigneDialog/DevisList) — ne pas créer de tâche séparée pour la
  carte de victoire, l'ajouter au périmètre VX40. Fix (delta à ajouter au Done= de VX40) :
  `<DealSignedCelebration>` — burst de confetti canvas maison (brass+azur, 0 dépendance), carte de
  victoire avec montant TTC + kWc (déjà calculés dans `SigneDialog` `optionsDetail` L59) + « ≈ X t
  CO₂ évitées/an » dérivée, TaqinorMark qui pulse ; dégrade en toast riche sous reduced-motion ;
  câblé sur les DEUX chemins d'appel. Survit comme tâche autonome : `toastMilestone` dans
  `lib/toast.js` — un cran au-dessus du succès plat (icône soleil + description réf/client/montant)
  posé sur devis envoyé (event `devis_sent`) et facture payée (`PaiementsPage`). Files :
  `ui/DealSignedCelebration.jsx` (nouveau, ≤120 l., @coord VX40), `pages/crm/leads/SigneDialog.jsx`,
  `pages/crm/leads/LeadsPage.jsx`, `pages/crm/LeadForm.jsx`, `lib/toast.js`,
  `pages/ventes/DevisList.jsx:476`, `pages/ventes/PaiementsPage.jsx`. DoD : accepter → carte de
  victoire avec montant + kWc réels (test mock accepterDevis) ; reduced-motion → carte sans
  mouvement ; devis envoyé/facture payée → toast visuellement distinct du toast générique (test du
  helper). (T3 — M, sonnet) (@lane: frontend/brand — @with VX40)

- [x] VX156 — **Une voix avec un point de vue + le moment d'accueil.** La microcopie est correcte (@lane: frontend/brand)
  mais interchangeable avec n'importe quel SaaS — aucun ton « fier du solaire », aucun vocabulaire
  métier aux moments émotionnels ; et la première connexion atterrit sur le Dashboard brut (les
  coachmarks FG16 sont un tour FONCTIONNEL, pas un accueil). Fix : (a) module `lib/voice.js` (~20
  chaînes FR, vouvoiement, vocabulaire kWc/chantier/mise en service) + guide d'une page, posé sur
  les 5-6 moments à forte charge : première connexion, file vide (« Tout est à jour — belle journée
  pour poser des panneaux. »), devis envoyé, affaire signée, chantier terminé, erreur réseau — PAS
  un rewrite massif (VX45 possède la microcopie générale) ; (b) `<WelcomeMoment>` one-shot à la
  première connexion : TaqinorMark animé, phrase de mission, bouton « Commencer », flag
  localStorage défensif (@coord `safeStorage`, VXD-B), skippable, une seule fois. Files :
  `lib/voice.js` (nouveau), `components/WelcomeMoment.jsx` (nouveau), `main.jsx`, poses sur ~6
  écrans. DoD : les 6 moments portent une chaîne voice.js (test aucune chaîne vide) ; accueil
  affiché une fois puis plus jamais (test du flag) ; revue de ton « ça sonne Taqinor ». (T3 — M,
  sonnet) (@lane: frontend/brand)

- [x] VX157 — **Le langage d'impact : icônes métier unifiées + la fierté ambiante du parc.**
  Aucun vocabulaire d'icône partagé pour les grandeurs métier (kWc, production, CO₂ évité,
  économies) — chaque écran choisit la sienne (`Co2Page` importe Leaf/Sprout/Zap ad hoc) ; et
  l'impact cumulé du parc (déjà servi par `monitoringApi.getCo2Fleet()`) est enterré dans un
  sous-écran monitoring. Fix : map `ui/metricIcons.js` (soleil=production, éclair=kWc,
  feuille=CO₂, portefeuille=économies, HardHat=chantier) + variante `Stat tone="impact"` à accent
  brass pour les grandeurs d'impact positif ; « pastille d'impact » discrète en pied de Sidebar
  (« X MWh · Y t CO₂ évitées » cumulés), chargée paresseusement, MASQUÉE si aucune donnée — jamais
  un « 0 » inventé (scoping company côté serveur ; [BACKEND] additif si l'endpoint manque). Files :
  `ui/metricIcons.js` (nouveau), `ui/Stat.jsx`, `components/layout/Sidebar.jsx`, poses
  Co2Page/Dashboard/monitoring. DoD : les KPI kWc/production/CO₂ partagent les mêmes icônes partout
  (test de la map) ; pastille = vraies valeurs du parc, absente si vide (test conditionnel). (T3 —
  M, sonnet) (@lane: frontend/brand)

- [x] VX158 — **Confiance et clarté : les valeurs suggérées se déclarent, le jargon fiscal se (@lane: frontend/brand — @after VX93)
  traduit.** Deux leçons de produits finis (Ramp, Pennylane) : (a) VX93 pré-remplira
  owner/ville/TVA/mode de paiement depuis localStorage sans qu'AUCUN signal ne distingue une
  SUPPOSITION d'une donnée confirmée — un style réutilisable discret (contour pointillé + micro-
  libellé « suggéré » au focus, retiré dès modification) posé sur les 4 champs VX93 — jamais un
  « confidence score » générique (à livrer AVEC ou juste après VX93) ; (b)
  `FiscalitePage.jsx`/`EtatsPage.jsx` exposent « FEC », « liasse », « IS » sans un mot d'aide — une
  phrase grise par bouton d'export (« FEC — fichier requis par l'administration fiscale en cas de
  contrôle »), zéro logique. Files : mêmes fichiers que VX93 (LeadForm, ProduitForm,
  DevisGenerator, FactureList) + `features/compta/pages/FiscalitePage.jsx`,
  `features/compta/pages/EtatsPage.jsx`. DoD : champ pré-rempli non touché → indice « suggéré »
  visible, disparaît à la modification (snapshot 1 champ) ; chaque export fiscal porte sa phrase
  d'aide sans clic. (T3 — S, sonnet ; haiku pour le volet fiscal) (@lane: frontend/brand — @after
  VX93)

- [x] VX159 (already present) — **`RelationCounters` : le seul bon réflexe d'Odoo, systématisé. @coord ARC46.** (@lane: frontend/brand)
  Chaque fiche 360 (Lead, Client, Fournisseur, Produit) affiche ses relations à sa façon — aucune
  convention « compteurs cliquables en tête de fiche » (« 3 devis · 1 facture impayée · 2 tickets
  SAV »). Fix : composant `ui/RelationCounters.jsx` posé en tête des 4 fiches, lisant les selectors
  existants par domaine (JAMAIS une nouvelle agrégation cross-app — frontière `selectors.py`
  respectée), clic → liste cible pré-filtrée (`?client=`, même pattern que VX112). Files :
  `ui/RelationCounters.jsx` (nouveau), `pages/crm/ClientDetailPanel.jsx`,
  `pages/stock/FournisseurFiche360.jsx`, `ProduitDetail.jsx`, `pages/crm/LeadForm.jsx`. DoD : les 4
  fiches affichent les mêmes badges cliquables ; clic → liste pré-filtrée (test) ; zéro nouvelle
  route cross-app. [coordonner ARC46 — construisible avant `RecordShell`, migrable dedans ensuite]
  (T3 — M, sonnet) (@lane: frontend/brand)

---

## AXE 2 — ROBUSTESSE (VX160–VX208, 49 tâches survivantes sur 49 seeds ; 0 tuée, 2 rognées —
SEED-14 re-scopé/SEED-17 rogné, corrections déjà appliquées dans le texte transcrit ci-dessous)

**Sous-groupe VXD-A — Intégrité des mutations & résilience réseau (le niveau sous la
présentation d'erreur)**

*Note : VX117 (au sommet de ce document) EST la transcription de SEED-01 de cette section — ne
pas la dupliquer ici, la numérotation continue directement à SEED-02.*

- [x] VX160 — **Outbox terrain : une op rejetée par le serveur ne disparaît plus en silence.**
  *(Transcription intégrale de SEED-02 — le résumé de tête figure déjà en VX119 au sommet du
  document comme bug candidat-build ; cette entrée porte le detail complet pour la lane VXD-A.)*
  `offline/outbox.js:117-122` purge un batch 100 % en statut `error` sans jamais lire le champ
  `.error` que le backend renvoie pourtant par op (`field_sync.py:263/266/293/313`) ; l'unique
  affichage (`OfflineSyncIndicator.jsx:14-23`) rend « Connexion rétablie. » dans les deux cas — une
  SIGNATURE CLIENT capturée hors-ligne (`FIELD_OPS.SIGNER_CLIENT`) peut s'évaporer sans trace. Fix :
  trois classes de résultat dans `flush()` (done retirés / `error` GARDÉS en file avec message
  serveur + compteur de tentatives / échec réseau déjà géré), méthode `fieldOutbox.failed()`,
  indicateur à 3 états (badge rouge « N action(s) en échec — voir détail », abandon par op
  UNIQUEMENT explicite). Le message serveur affiché EST le signal de conflit — pas de moteur CRDT.
  Files : `offline/outbox.js`, `offline/useFieldOutbox.js`, `offline/OfflineSyncIndicator.jsx`.
  DoD : batch mock 100 % `error` → ops gardées + message par op accessible ; badge distinct rendu ;
  non-régression `applied`/`replayed`. (T1 — M, sonnet) (@lane: frontend/data)

- [x] VX161 **(already present)** — **`refreshCoordinator` : un seul refresh 401 partagé entre `axios.js` et (@lane: frontend/data)
  `iaApi.js`.** `axios.js:29-53` pose `_retry` PAR REQUÊTE : N requêtes 401 simultanées = N `POST
  /token/refresh/` parallèles (stampede) ; `iaApi.js:28-53` duplique en plus son PROPRE
  intercepteur — une page métier + le Copilote au même instant lancent deux refresh concurrents
  contre le même refresh_token ; en rotation à usage unique, le second échoue →
  `emitSessionExpired()` intempestif sur une session valide. Fix : `api/refreshCoordinator.js` —
  promesse de refresh UNIQUE partagée (le premier appelant POST, tout suivant `await` la MÊME
  promesse, reset en `finally`), consommée par les deux intercepteurs. Files :
  `api/refreshCoordinator.js` (nouveau), `api/axios.js`, `api/iaApi.js`. DoD : 5 requêtes 401
  simultanées (mix des deux instances) → exactement UN POST refresh, les 5 rejouées après. (T1 —
  S, sonnet) (@lane: frontend/data)

- [x] VX162 **(already present)** — **`BroadcastChannel` de session : le logout se propage à tous les onglets.** (@lane: frontend/data)
  `authSlice.js:17-28` ne notifie que l'onglet courant ; grep cross-tab exhaustif = 1 hit
  cosmétique (`GlobalSearch.jsx:144`). Sur un poste partagé (accueil/atelier), l'onglet B continue
  de MUTER des données au nom d'un utilisateur délibérément déconnecté jusqu'à son premier 401
  tardif. Fix : `BroadcastChannel('taqinor-session')` dans `providers/session-bridge.js` —
  `logoutUser.fulfilled` publie, chaque onglet s'abonne dans `SessionProvider` et dispatch le
  logout local + `/login` sans attendre un échec réseau ; feature-detect no-op. Files :
  `providers/session-bridge.js`, `authSlice.js`, `providers/SessionProvider.jsx`. DoD : logout
  onglet A → onglet B simulé passe `isAuthenticated:false` sans appel réseau. (T2 — S, sonnet)
  (@lane: frontend/data)

- [x] VX163 — **Infrastructure thunk : annulation `{signal}` + dé-duplication en vol des 4 thunks (@lane: frontend/data — @with/after VX54)
  chauds.** 79 `createAsyncThunk` identiques, ZÉRO `{signal}` (grep) — un démontage laisse la
  requête vivre et réduire un écran disparu ; et zéro dédup : deux montages simultanés = deux GET
  identiques. Fix (0 dép — le « RTK Query sans RTK Query ») : `lib/thunkHelpers.js` —
  `createCancellableThunk(type, apiCall)` injecte `thunkAPI.signal` dans axios et normalise
  `CanceledError` (jamais toasté) ; + une `Map<clé, Promise>` in-flight (~15 lignes) sur
  `fetchProduits`/`fetchDevis`/`fetchLeads`/`fetchFactures` — les MÊMES 4 slices que VX54 touche
  (séquencer `@with/after VX54`). Files : `lib/thunkHelpers.js` (nouveau), les 4 slices
  (stock/ventes/crm). DoD : dispatch double avant résolution → 1 seul appel réseau, 2 promesses
  même payload ; démontage → `meta.aborted === true`, 0 toast. (T2 — M, sonnet) (@lane:
  frontend/data — @with/after VX54)

- [x] VX164 **(already present)** — **Plancher anti-course : séquence (messaging), fraîcheur (réducteurs `update*`), (@lane: frontend/data)
  verrou `InlineEdit`.** (a) `messagingSlice.js:200-205` protège le changement de conversation mais
  pas l'ORDRE — le poll 3 s (`useChatPolling.js:51-55`) n'annule pas le tick précédent : un tick
  N-1 lent écrase la page plus fraîche (un message reçu DISPARAÎT jusqu'au tick suivant). (b)
  `crmSlice.js:159-162`, `ventesSlice.js:300-307`, `stockSlice.js:196-199` : remplacement TOTAL au
  `.fulfilled` — deux PATCH rapides du même utilisateur résolus dans l'ordre inverse font régresser
  l'écran. (c) `InlineEdit.jsx:30-48` : Enter puis blur = deux `onSave` (le verrou `saving` ne
  pilote que l'AFFICHAGE). Fix : compteur monotone par ressource appliqué au `fulfilled` (no-op si
  obsolète — même mécanique pour a et b) ; `committingRef` vérifié EN TÊTE de `commit()` pour (c).
  Files : `messagingSlice.js`, `useChatPolling.js`, les 3 slices (réducteurs
  `update*/patch*.fulfilled`), `components/InlineEdit.jsx`. DoD : résolutions inversées → l'état
  final contient LES DEUX changements / le payload le plus récent DEMANDÉ ; Enter+blur synchrone →
  `onSave` 1×. (T2 — M, sonnet) (@lane: frontend/data)

- [x] VX165 **(already present)** — **Chargement par-ressource : le spinner ne ment plus (prérequis silencieux de (@lane: frontend/data)
  VX67).** `ventesSlice.js:288-298/316-321/353-358` (miroirs crm/stock) : UN `state.loading`
  partagé par `fetchDevis`/`fetchBonsCommande`/`fetchFactures` — le premier résolu éteint le
  spinner pendant que les requêtes sœurs chargent encore. Fix : `pendingCount`
  incrémenté/décrémenté par chaque `pending`/settled (une ligne par builder, rétrocompatible avec
  les sélecteurs existants), spinner tant que `> 0`. Files : `ventesSlice.js`, `crmSlice.js`,
  `stockSlice.js`. DoD : `fetchDevis` + `fetchFactures` parallèles, factures résout d'abord →
  `loading` reste `true` (test rouge avant/vert après). (T2 — S, sonnet) (@lane: frontend/data)

**Sous-groupe VXD-B — Formulaires : ne jamais perdre une saisie**

- [x] VX166 — **Câbler `confirmLeaveIfDirty` chez les 7 adoptants existants + `CrudDialog` (8 (@lane: frontend/forms)
  écrans compta d'un coup).** Les 7 formulaires qui calculent DÉJÀ `dirty` + `useDirtyGuard`
  (`ClientForm.jsx:240`, `ProduitForm.jsx:402`, `DevisForm.jsx:222`, `FactureForm.jsx:263`,
  `InstallationDetail.jsx:725`, `EquipementsPage.jsx:229`, `TicketsPage.jsx:529`) gardent
  `onOpenChange={(o)=>{if(!o) onClose()}}` — Radix ferme sur Escape ET clic-overlay et jette la
  saisie ; `confirmLeaveIfDirty` (`useDirtyGuard.js:27-33`) a 0 appelant dans tout le repo (grep).
  Et `features/compta/components/CrudDialog.jsx:67` (partagé par 8 pages compta) n'a AUCUNE notion
  de dirty. Fix : gater la fermeture par `confirmLeaveIfDirty(dirty)` dans les 7 fichiers + snapshot
  à l'ouverture + garde dans `CrudDialog` (zéro changement d'API pour les 8 appelants). Files : les
  7 fichiers + `CrudDialog.jsx`. DoD : modifier → Escape → `confirm` invoqué (mock) ; annuler →
  modale ouverte, champs intacts ; non-dirty inchangé ; smoke 2 pages compta. (T1 — S/M, sonnet)
  (@lane: frontend/forms)

- [x] VX167 — **LeadForm : dirty-tracking + garde de fermeture (le modal n°1 — complément direct (@lane: frontend/forms — @with/after VX89)
  de VX89). @with/after VX89.** `LeadForm.jsx:588` (overlay `onClick={onClose}`) et `:639` (bouton
  ✕) : ZÉRO notion de dirty dans tout le fichier (grep) — 15 champs (bien+GPS+relance+tags) perdus
  sur un mis-clic, à 20-40 ouvertures/jour/commercial. VX89 (Escape+autofocus via ResponsiveDialog)
  rendra même la perte PLUS facile : Escape marchera enfin, et fermera sans rien demander. Fix :
  snapshot initial (patron `isDirty` prouvé dans `ProduitForm.jsx:286`) + `useDirtyGuard(dirty)` +
  `confirmLeaveIfDirty` sur ✕/overlay/futur `onOpenChange`. Files : `pages/crm/LeadForm.jsx`. DoD :
  modifier un champ → toute fermeture demande confirmation ; e2e leads verts. (T1 — M, sonnet)
  (@lane: frontend/forms — @with/after VX89)

- [x] VX168 — **Balayage garde+autoFocus : 13 dialogues flotte/gestion_projet + (@lane: frontend/forms)
  `EmployeDetail`/`Recrutement` + autoFocus top-20.** 9 dialogues `features/flotte/*` (dont
  `PleinDialog` 11 useState, `SignalementDialog` saisie terrain) + 4
  `features/gestion_projet/components/*Dialog.jsx` : 0 dirty-guard (grep) ;
  `features/rh/Recrutement.jsx` (31 useState — 2ᵉ plus long formulaire du repo après
  DevisGenerator) et `EmployeDetail.jsx` (19) : 0 garde ; `autoFocus` ne couvre que 12/93
  fichiers-formulaire. Fix : même recette snapshot+garde posée mécaniquement (1ᵉʳ fichier = patron
  validé, puis répétition), et `autoFocus` posé dans la MÊME passe + sur ~20 formulaires fréquents
  (UsersManagement, RolesManagement, KpiAlertesPage, écrans compta). Files : les 15 fichiers cités +
  ~20 autoFocus. DoD : par fichier — modifier→fermer → confirmation ; ouverture →
  `document.activeElement` = premier champ. (T1 — L, sonnet ; haiku après le patron) (@lane:
  frontend/forms)

- [x] VX169 — **`useBlocker` : garde de navigation IN-APP des formulaires route-level.** (@lane: frontend/forms)
  `useDirtyGuard` ne couvre que `beforeunload` — un clic sidebar pendant la saisie navigue
  instantanément (pushState, pas un déchargement) ; `useBlocker` de react-router v7
  (`createBrowserRouter` confirmé `router/index.jsx:207`) = 0 usage dans le repo. Fix :
  `hooks/useNavigationGuard.js` fin au-dessus de `useBlocker` (fallback no-op), monté sur
  `ParametresEntreprise`, `EquipementSignalerPage`, `DashboardConfigPage`, `ArticleEditor`,
  `ReclamationEditor` ; dialogue design-system, pas `window.confirm` brut. Files : le hook
  (nouveau) + les 5 écrans. DoD : modifier ParametresEntreprise → clic lien sidebar →
  confirmation ; accepter navigue, annuler reste. (T2 — M, sonnet) (@lane: frontend/forms)

- [x] VX170 — **`useFormSafety` : LA primitive qui rend le mauvais câblage impossible (incl. (@lane: frontend/forms)
  réparation WebKit du hook + `safeStorage`).** Le repo n'a pas de convention : chaque formulaire
  réinvente son snapshot (`isDirty` / `JSON.stringify` diff / `useMemo` custom) et personne ne
  branche les 3 mécanismes ensemble (tab-close + in-app-close + router) — les 7 « meilleurs
  élèves » n'en branchent que 1 sur 3. Pire : `useDirtyGuard.js:20` n'écoute QUE `beforeunload`,
  quasi muet sur iOS (swipe-back/bascule d'app sautent l'événement ; le fiable WebKit est
  `pagehide`) → toute la pile B est aveugle iPhone. Fix : `ui/useFormSafety.js` — `{dirty,
  guardedClose, snapshot}` composant (a) diff générique, (b) `useDirtyGuard`, (c)
  `confirmLeaveIfDirty` wrappé, (d) flag route-level → VX169 ; réparer le hook sous-jacent avec
  `pagehide` (+ `visibilitychange→hidden`) qui PERSISTE un brouillon défensif — on ne peut pas
  bloquer un pagehide, la bonne UX WebKit = sauver, pas bloquer — via un `lib/safeStorage.js`
  défensif (try/catch + éviction sur `QuotaExceededError`, Safari privé) que VX62/VX46/VX10/NTUX16
  consommeront aussi. Files : `ui/useFormSafety.js` (nouveau), `ui/useDirtyGuard.js`,
  `lib/safeStorage.js` (nouveau), migration d'au moins 3 formulaires (ClientForm, CrudDialog, un
  dialogue flotte). DoD : test du hook isolé ; `pagehide` dirty → persistance appelée ; `setItem`
  en quota plein ne crash pas et évince le plus ancien ; 3 formulaires migrés avec moins de code.
  (T2 — M, sonnet) (@lane: frontend/forms)

- [x] VX171 — **Vérité des erreurs de champ : serveur → champ (`useServerFieldErrors`) + erreurs (@lane: frontend/forms)
  locales effacées à la frappe.** (a) DRF renvoie `{champ:[msg]}` mais 12 fichiers seulement posent
  `aria-invalid` — tout est écrasé en UN toast opaque ; `FormField` (`ui/Form.jsx:56-77`) est
  correctement câblé et sous-consommé. (b) `ClientForm.jsx:170-180`, `DevisForm.jsx:147/215`,
  `FactureForm.jsx:184/256` : `setErrors` n'est jamais nettoyé au `onChange` — le rouge MENT
  pendant que l'utilisateur corrige, jusqu'au prochain submit. Fix : `hooks/useServerFieldErrors.js`
  (mapping DRF → `errors{champ}` consommé par `FormField error=`) posé sur
  Client/Lead/Devis/Facture/Produit ; dans chaque `set(field, …)`, `delete errors[field]`. Files :
  le hook (nouveau) + les 5 formulaires. DoD : soumettre invalide → LE champ vire rouge avec son
  message (pas un toast anonyme) ; taper dans le champ fautif → l'erreur disparaît avant re-submit ;
  tests des formes DRF (detail / `{champ:[…]}` / array). (T2 — M, sonnet) (@lane: frontend/forms)

**Sous-groupe VXD-C — iOS Safari / WebKit / PWA (la longue traîne au-delà de VX48-53/68)**

- [x] VX172 — (déjà présent) **Exports blob (xlsx/csv/json/png) fiables sur iOS/standalone : routage par geste + (@lane: frontend/ios)
  pending visible + repli PDF réparé. @after VX48/49 — RE-SCOPÉ par le grand-verdict.**
  `downloadBlob.js:2-11` et ~20 call-sites posent `a.download` sur un `blob:` (`ClientList.jsx:138`,
  `LeadsPage.jsx:124/219`, `StockList.jsx:191/669/771`, `ClientRgpdActions.jsx:35`,
  `DocumentsArchive.jsx:89/111`, `PaieDeclarations.jsx:67/578/886`, `Risques.jsx:73`,
  `comptaApi.js:16`, `importApi.js:55/74`…). **Constat corrigé (grand-verdict) :** Safari iOS ≥13
  SUPPORTE `a.download` sur les URL blob — le risque réel est le mode PWA STANDALONE + les vieux
  iOS + une UX de fichier téléchargé invisible (gestionnaire de téléchargements indécouvrable en
  coquille installée), PAS un échec universel. Le repli terminal `pdfBlob.js:88-92` combine
  `download`+`_blank` — fragile dans les mêmes conditions. La gestion d'erreur des ~49 sites blob
  (try/catch + toast + `revokeObjectURL`) appartient à **VX49** — ne PAS la refaire ici. Fix :
  `downloadBlobInGesture` (patron `openPdfInGesture` de VX48 : onglet pré-ouvert dans le handler
  de tap quand iOS/standalone, `a.download` ailleurs) + routage des ~20 sites ; état
  `loading`/désactivé sur les 6 boutons Excel (`DevisList.jsx:772`, `FactureList.jsx:620`,
  `InstallationsPage.jsx:353`, `Rapports.jsx:523`, `EquipementsPage.jsx:551`,
  `TicketsPage.jsx:1396` — VX49 pose le toast, jamais le pending) ; brancher le repli `pdfBlob` vers
  `openPdfInGesture` ou `location.assign` (uniquement le chemin d'OUVERTURE, jamais le moteur
  `/proposal`, règle #4). Files : `utils/downloadBlob.js`, `utils/pdfBlob.js`, `api/importApi.js`,
  les call-sites. DoD : vitest UA iOS/standalone → le helper passe par le chemin geste (l'inverse
  ailleurs) ; bouton Exporter désactivé + spinner pendant l'attente ; vérification APPAREIL
  RÉEL/standalone notée au DoD (le simulateur ne suffit pas) ; e2e WebKit (VX189) : « Exporter »
  aboutit. (T2 — M, sonnet) (@lane: frontend/ios)

- [x] VX173 — (déjà présent) **`VoiceRecorder` : mimeType négocié (fin du blob mp4 étiqueté « webm »).** (@lane: frontend/ios)
  `VoiceRecorder.jsx:64` : `new MediaRecorder(stream)` sans mimeType, `:70` étiquette
  `rec.mimeType || 'audio/webm'` — WebKit ne supporte pas webm et produit `audio/mp4` ⇒ message
  vocal mal typé, lecture/serveur KO sur iPhone. Le voisin
  `features/ia/voice/useVoiceChat.js:55` a DÉJÀ `pickAudioMimeType()` propre (webm/opus → mp4).
  Fix : exporter `pickAudioMimeType` (source unique), passer `{mimeType}` au constructeur,
  étiqueter le blob du vrai type négocié. Files : `features/messaging/VoiceRecorder.jsx`,
  `features/ia/voice/useVoiceChat.js`. DoD : mock MediaRecorder mp4-only → blob `audio/mp4`,
  jamais « webm » en dur ; un vocal WebKit se relit. (T2 — S, sonnet) (@lane: frontend/ios)

- [x] VX174 — (déjà présent) **Politique de saisie iOS sur les primitives (`sanitize`) + `DatePicker` là où (@lane: frontend/ios)
  `min`/`max` porte une règle métier.** `ui/Input.jsx`/`Textarea.jsx` : ZÉRO défaut
  `autoCapitalize`/`autoCorrect` (29 fichiers overrident au coup par coup) — références
  `DEV-202607-…`, emails, ICE/IF, SKU, plaques auto-capitalisés/corrigés au clavier iPhone. Et 93
  `<input type="date">` natifs : la roue iOS IGNORE `min={todayStr()}`
  (`ActivitiesPanel.jsx:125`, `MesActivitesPage.jsx:278`) — contrainte métier contournable sur
  iPhone. Fix : prop `sanitize` (`'code'|'email'|'name'|'off'`) sur Input/Textarea forçant
  `autoCapitalize/autoCorrect/spellCheck/autoComplete/inputMode` cohérents, appliquée aux champs
  référence/ICE/IF/SKU/email des formulaires clés ; remplacer par `ui/DatePicker` (custom
  existant, borne en JS) UNIQUEMENT les dates à contrainte métier (relances, échéances, activités à
  venir). Files : `ui/Input.jsx`, `ui/Textarea.jsx`, `ActivitiesPanel.jsx`,
  `MesActivitesPage.jsx`, formulaires clés. DoD : `<Input sanitize="code">` rend les 4 attributs
  off ; WebKit : impossible de choisir une date < `min` sur un champ borné. (T2 — M, sonnet)
  (@lane: frontend/ios)

- [x] VX175 — (déjà présent) **Plancher CSS tactile/viewport : `touch-action` global, momentum horizontal, (@lane: frontend/ios)
  `.modal` dvh, ellipse sidebar.** Quatre oublis mécaniques prouvés : (a) `touch-action:
  manipulation` n'existe que sur `.kb-drag-wrap` (`index.css:4180`) — double-tap-zoom parasite +
  délai 300 ms partout ailleurs : l'étendre au sélecteur global du tap-highlight
  (`index.css:148`). (b) ≥5 conteneurs `overflow-x:auto` sans `-webkit-overflow-scrolling:touch`
  ni `overscroll-behavior-x:contain` (`.lines-table-wrap:1179`, `.lv-wrap:4472`, kanban `:4087`,
  `.lead-nav:1012` — `.agent-sql` RETIRÉ : CSS mort, 0 consommateur, sa suppression appartient à
  VX121) — classe utilitaire `.scroll-x-touch`. (c) `.modal` (`index.css:899-905`) est le SEUL
  bloc `100vh` du fichier sans repli `100dvh` (bas de modale rogné sous barre d'adresse
  dynamique) — ajouter la paire comme partout ailleurs. (d) `Sidebar.jsx:312` : `title=` seulement
  si `collapsed` + `.sidebar-nav-label` sans `text-overflow` (`index.css:427`) — libellé
  silencieusement COUPÉ à texte-zoom élevé : ellipsis + `title` inconditionnel. Files :
  `index.css`, `components/layout/Sidebar.jsx`. DoD : WebKit — scroll de lignes inertiel,
  double-tap sans zoom ; `modal-viewport.test` étendu à `dvh` ; libellé tronqué → `…` + `title`
  présent en état déplié. (T2 — S, haiku/sonnet) (@lane: frontend/ios)

- [x] VX176 — (déjà présent) **Safe-area complète : overlays plein écran + barres fixes (encoche/Dynamic Island (@lane: frontend/ios)
  en PWA standalone).** `black-translucent` (`index.html`) fait passer le contenu SOUS la barre
  d'état ; le header réserve `env(safe-area-inset-top)` (`index.css:467`) mais les overlays Radix
  `fixed inset-0` (`ui/Sheet.jsx:26`, `Dialog.jsx:40`, `AlertDialog.jsx:23`) n'ont AUCUN inset
  haut — un Sheet latéral colle son bord sous l'encoche en standalone ; `safe-area-inset` = 2
  fichiers dans tout le repo (les barres fixes/bottom-tab/FAB VX42 non couvertes non plus). Fix :
  classe `safe-top` (`padding-top: env(safe-area-inset-top)`) sur les overlays plein écran +
  application aux surfaces fixes globales + `viewport-fit=cover` vérifié. Files : `ui/Sheet.jsx`,
  `ui/Dialog.jsx`, `ui/AlertDialog.jsx`, `index.css`, `index.html`. DoD : simulateur iPhone
  standalone — l'en-tête d'un Sheet/AlertDialog n'est jamais sous l'encoche ; extension de
  `modal-viewport.test.jsx`. (T2 — S, sonnet) (@lane: frontend/ios)

- [x] VX177 — (déjà présent) **`ExternalLink` : navigation standalone PWA maîtrisée.** En mode `standalone` iOS, (@lane: frontend/ios)
  ~18 `<a target="_blank">` externes (GED/KB/RH/wa.me/`verifierIceUrl`) ouvrent un
  SFSafariViewController sans retour naturel ; un lien interne nu peut ÉJECTER hors de la coquille
  installée. `PwaPrompts.jsx:17` détecte `isStandalone()` sans jamais l'exploiter. Fix : un
  `<ExternalLink>`/`openExternal(url)` centralisant `_blank`+`noopener` pour l'EXTERNE et
  react-router pour l'INTERNE (jamais de `<a href>` nu pour une route interne) ; ne touche PAS
  `/proposal` ni les pages publiques GED (règle #4). Files : `ui/ExternalLink.jsx` (nouveau) + les
  call-sites externes. DoD : en standalone simulé, lien externe → nouvel onglet sans quitter la
  coquille ; lien interne → routeur ; test de rendu. (T2 — M, sonnet) (@lane: frontend/ios)

- [x] VX178 — **`backdrop-blur` retiré des surfaces sticky scrollées (jank WebKit du (@lane: frontend/ios — avant ARC49/53)
  DataTable).** `ui/datatable/DataTable.jsx:436` (thead `sticky top-0` + `backdrop-blur`) + `:669`
  (tfoot sticky) + `BulkActionBar.jsx:39` : `backdrop-filter` recomposé à CHAQUE frame de scroll —
  jank et scintillement connus WebKit sur les grandes listes ; ARC49/53 vont migrer
  DevisList/FactureList SUR ce composant fragile. Fix : fond opaque token-isé (`bg-muted` plein)
  sur les barres sticky — le blur n'apporte rien sur une barre déjà pleine et coûte cher ; blur
  conservé sur les overlays STATIQUES. Files : `ui/datatable/DataTable.jsx`,
  `ui/datatable/BulkActionBar.jsx`. DoD : grep confirme `backdrop-blur` retiré des thead/tfoot
  sticky ; rendu visuel équivalent ; scroll 100+ lignes fluide en WebKit. (T2 — S, sonnet) (@lane:
  frontend/ios — avant ARC49/53)

- [x] VX179 — (déjà présent) **Service worker : cache runtime `StaleWhileRevalidate` des images/médias (@lane: frontend/ios)
  dynamiques.** `sw.js:41-65` : précache build-time + navigations network-first SEULEMENT — zéro
  `registerRoute` runtime : photos d'installation/GED et images KB re-téléchargées à chaque
  visite, et CASSÉES hors-ligne alors que la coquille, elle, marche. Fix : `registerRoute`
  `StaleWhileRevalidate` same-origin `/media/` + images KB/GED avec `ExpirationPlugin` borné (max
  entries + max age — les paquets `workbox-*` sont déjà des dépendances via vite-plugin-pwa, 0
  dép nouvelle). Files : `frontend/src/sw.js` uniquement. DoD : Playwright — article KB avec
  images visité online → `setOffline(true)` → reload → images rendues du cache ; nombre d'entrées
  ≤ max configuré. (T2 — S, sonnet) (@lane: frontend/ios)

**Sous-groupe VXD-C (suite) — Viewport & performance réelle**

- [x] VX180 — **`DataTable`/`ListShell` : le seuil documenté (768px) n'est PAS le seuil réel (@lane: frontend/ios — avant ARC49/53)
  (Tailwind `sm` = 640px) — 42 pages affectées, indétectable par les tests actuels. AVANT
  ARC49/53.** `ui/datatable/DataTable.jsx:396` (`hidden … sm:block`) et `:702` (`sm:hidden`)
  utilisent l'utilitaire Tailwind par défaut (640px) alors que le code ET son test affirment 768px
  en toutes lettres (commentaires `:697/:701`, `DataTable.test.jsx:253-271`) — vérifié : AUCUN
  override de `--breakpoint-sm` dans `design/tokens.css` `@theme`. Entre 640 et 767px (petite
  tablette portrait, Android paysage, fenêtre redimensionnée), la TABLE DESKTOP s'affiche à la
  place des cartes que le code croit garantir. Le test ne vérifie qu'une SOUS-CHAÎNE de classe
  (jsdom n'applique aucune media query) — il ne peut structurellement PAS le détecter ; aucun
  projet Playwright ne couvre cette bande (mobile=390, desktop=1280). 42 pages via
  `ui/module/ListShell.jsx` (compta ×9, flotte ×8, paie ×5, rh ×5, ged ×4…) + 4 usages directs
  héritent du bug. Fix : variante Tailwind DÉDIÉE `dt-desktop:` mappée à 768px, réservée au
  DataTable (option sûre — l'option globale `--breakpoint-sm: 48rem` traverse tout `sm:` du
  projet → opus si retenue) ; corriger le test pour PROUVER le seuil (Playwright réel à 700px,
  `toBeVisible()`, jamais une classe). Files : `ui/datatable/DataTable.jsx`, `DataTable.test.jsx`,
  `e2e/datatable-breakpoint.spec.js` (nouveau), `design/tokens.css` (si option globale). DoD : à
  700px réels, les cartes sont visibles et la table ne l'est pas ; les 42 pages `ListShell` non
  régressées. (T1 — M, sonnet ; opus si option globale) (@lane: frontend/ios — avant ARC49/53)

- [x] VX181 — (déjà présent) **`.header-right` : 9 cibles interactives sans garde de largeur — débordement à (@lane: frontend/ios)
  320-375px.** `index.css:1943-1946` fige `.header-right { flex-shrink:0; flex:0 0 auto }` sur
  mobile alors qu'il empile : loupe repliée, `LanguageSwitcher`, 3 boutons `ThemeToggle` jamais
  masqués (rendu inconditionnel `Header.jsx:87`, seul le LIBELLÉ est `hidden sm:inline` —
  `ThemeToggle.jsx:16-52`), Copilote, `ChatBell`, `NotificationBell`, avatar. Avec le padding
  `max(1.25rem, safe-area)`, l'espace utile à 320px ≈ 280px pour TOUT le header. Fix : `ThemeToggle`
  en `hidden md:flex` + les 3 options ajoutées au `DropdownMenu` du menu utilisateur ; si le budget
  reste tendu, regrouper Copilote/ChatBell/NotificationBell derrière un menu « Activité » mobile.
  Files : `design/ThemeToggle.jsx`, `components/layout/Header.jsx`. DoD : à 320 et 375px,
  `scrollWidth <= clientWidth` sur `.header` (Playwright) ; les 3 thèmes restent accessibles via le
  menu ; e2e mobile vert. (T2 — S/M, sonnet) (@lane: frontend/ios)

- [x] VX182 — **7 modales fait-main hors LeadForm : le même défaut que VX89 corrige, sur 7 (@lane: frontend/forms — @after VX89)
  surfaces qu'il ne cite pas. @after VX89.** Grep négatif vérifié
  (`Escape|autoFocus|role="dialog"|aria-modal|ResponsiveDialog` = 0) sur 7 fichiers au même shell
  `.modal-overlay` brut que `LeadForm.jsx:588` : `features/logistique/PodCaptureDialog.jsx`,
  `features/logistique/TransfertsScreen.jsx`, `pages/crm/ClientDetailPanel.jsx`,
  `pages/crm/leads/ConvertirClientDialog.jsx`, `LeadInsightsDialog.jsx`, `PlanActiviteDialog.jsx`,
  `SigneDialog.jsx` — Tab passe SOUS le voile, Escape ne ferme rien, dont deux flux terrain
  photo/signature à forte fréquence tactile. Fix : envelopper chaque shell dans
  `ResponsiveDialog` (Dialog Radix bureau / Sheet bas mobile, hook `matchMedia` réactif — déjà
  4/11 adoptants), `autoFocus` sur le premier contrôle, en LOT mécanique une fois le patron VX89
  posé. Files : les 7 fichiers. DoD : chacun répond à Escape, autofocus posé, largeur desktop
  équivalente, e2e leads/logistique verts. Complément de VX168 (dirty-guard flotte/GP — fichiers
  disjoints, préoccupation différente). (T2 — M, sonnet) (@lane: frontend/forms — @after VX89)

- [x] VX183 — **Densité par palier : colonnes kanban 272px fixes (pipeline à moitié invisible sur
  iPad) + calendrier 7 colonnes illisible sous 400px.** (a) DONE — `index.css` `.kb-col { flex: 0 0
  272px }`, aucune media query 768-1024 : sur l'iPad 1024×768 paysage, 6 étapes STAGES.py ≈ 1670px →
  ~3,7 colonnes visibles, défilement horizontal permanent. Fix livré : `@media (max-width: 1024px)
  and (min-width: 900px)` → `.kb-col` 150px (calcul incluant sidebar 240px + kb-board padding/gaps,
  garantit ≥5 des 6 colonnes visibles à 1024px même sidebar dépliée) ; bureau >1024px inchangé.
  Partagé par CRM leads/installations/interventions (même classe `.kb-col`). (b) BLOCKED : `@after
  VX147` — dépend de l'extraction `MonthGrid` que VX147 doit produire (`MonthGrid.jsx` n'existe pas
  encore dans `pages/CalendarPage.jsx`/`crm/leads/views/CalendarView.jsx`) ; composition guard —
  ne pas hand-roll cette extraction ici. Reste à faire une fois VX147 mergé : vue « agenda » (liste
  verticale jour-par-jour) sous ~400px pour la grille `repeat(7, minmax(0,1fr))` illisible à 320px.
  Files : `index.css` (fait), `components/MonthGrid.jsx`/`CalendarPage.jsx`/
  `crm/leads/views/CalendarView.jsx` (en attente de VX147). (T2 — M, sonnet)
  (@lane: frontend/ios — @after VX147)

- [x] VX184 — **Un seul comportement mobile pour les lignes-produit : `data-label` + bascule
  carte sur DevisForm/FactureForm. @coord VX146 (FactureForm).** `pages/ventes/DevisForm.jsx:292-303`
  et `FactureForm.jsx:407-419` : `<table min-w-[640px]>` dans un `overflow-x-auto` — scroll
  horizontal permanent sur téléphone, alors que `.lines-table` du générateur bascule en cartes
  empilées sous 768px (`index.css:2122-2154`, patron `data-label` complet). Fix : poser les
  `data-label` manquants + étendre les règles `.lines-table` à ces deux tableaux (ou migrer vers la
  classe partagée si les colonnes correspondent). Files : `DevisForm.jsx`, `FactureForm.jsx`,
  `index.css`. DoD : à 375px, éditer un devis existant affiche des cartes empilées comme le
  générateur ; e2e non régressé. La garde `data-label` de VX50 ne couvre que les tables
  `.data-table` de LISTE, pas ces modales. (T2 — M, sonnet) (@lane: frontend/ios)

- [x] VX185 — (déjà présent) **Le barrel `ui/index.js` fuit `datatable`/`recharts`/`pdfjs-dist` dans le preload (@lane: frontend/ios)
  du BOOT (~350 Ko gzip avant l'écran de connexion) + garde CI étendue.** Build réel :
  `dist/index.html` contient 21 `<link rel="modulepreload">` dont `pdfjs-dist` (125,6 Ko gzip),
  `recharts` (110,3), `datatable` (29,2) — chargés sur TOUTE page, `/login` inclus, sur le 4G
  marocain. Origine tracée : `Header.jsx:8` importe depuis le barrel `'../../ui'` dont la
  DERNIÈRE ligne (`ui/index.js:57`) exporte `datatable` ; Header est statique dans `Layout.jsx:7`
  → `router/index.jsx:8` → `main.jsx`. La garde YHARD7 (`check_bundle_budget.mjs`, 2 161,8/2 200
  Ko — 98,3 % consommé) mesure chaque chunk ISOLÉMENT, jamais ce que `index.html` précharge au
  boot. Fix : imports DIRECTS (`../../ui/Avatar`, `../../ui/DropdownMenu`) dans `Header.jsx` +
  `LanguageSwitcher.jsx:5` ; étendre `check_bundle_budget.mjs` (additif) : échec si un vendor
  lourd nommé (`recharts`/`pdfjs-dist`/`datatable`/`roof-tool`) figure en `modulepreload`
  (allowlist commentée) + plafond/métrique du NOMBRE de chunks. Files :
  `components/layout/Header.jsx`, `LanguageSwitcher.jsx`, `frontend/scripts/check_bundle_budget.mjs`.
  DoD : après build, `grep modulepreload dist/index.html` sans recharts/pdfjs/datatable ; la garde
  est rouge si on les réintroduit ; `Header.test.jsx` vert. (T2 — M, sonnet) (@lane:
  frontend/ios)

- [x] VX186 — (déjà présent) **Code-splitting intra-écran : les 5 vues de LeadsPage + `MapView`/leaflet enfin (@lane: frontend/ios)
  lazy.** `pages/crm/leads/LeadsPage.jsx:22-26` importe STATIQUEMENT les 5 vues, le rendu
  (`:437-449`) ne fait qu'en choisir une : `CarteView` embarque leaflet (150,7 Ko/44,4 gzip, plus
  gros composant non-vendor), `ChartsView` embarque recharts → LeadsPage = PLUS GROS chunk de
  route du repo (137,9 Ko/38 gzip). `MapView` est aussi statique dans `CartePage.jsx` et
  `ParcInstallePage.jsx:467`. Fix : `React.lazy` + `<Suspense>` autour du switch de vue (motif
  standard du router, 0 dép) ; `lazy(MapView)` aux 3 sites. Files : `LeadsPage.jsx`,
  `CartePage.jsx`, `views/CarteView.jsx`, `installations/ParcInstallePage.jsx`. DoD : `npm run
  build` → `LeadsPage-*.js` chute (~40 Ko gzip, shell + vues par défaut) ;
  MapView/ChartsView/CalendarView = chunks séparés chargés au premier clic d'onglet ; tests
  LeadsPage/KanbanView verts. (T2 — S/M, sonnet) (@lane: frontend/ios)

- [x] VX187 — (déjà présent) **LeadsPage runtime : `useDeferredValue` sur le filtre + `React.memo` sur les (@lane: frontend/ios)
  cartes (l'exception MESURÉE au différé round-2).** `LeadsPage.jsx:76/:82` :
  `filterLeads(leads, filters)` recalcule en SYNCHRONE dans un `useMemo` à chaque frappe de la
  recherche ; et zéro `memo(` dans `LeadCard.jsx`/`ListView.jsx` : chaque frappe re-rend toutes
  les cartes visibles. Fix : `useDeferredValue(filters)` pour dériver la liste (input dans la lane
  urgente, `isStale` → dim) ; `React.memo(LeadCard)` + rangée ListView + `useCallback` sur les 2-3
  handlers parents (sinon le memo ne tient pas) ; option (c) `<Activity mode>` (React 19.2
  confirmé `^19.2.5`) pour préserver scroll/état local à la bascule kanban↔liste — API récente :
  vérifier la sémantique des effets avant de shipper, abandonner proprement si elle ne convient
  pas. Files : `LeadsPage.jsx`, `views/LeadCard.jsx`, `views/ListView.jsx` (+ call-sites
  KanbanView). DoD : vitest — frappes rapides : `filterLeads` ne re-tourne pas en synchrone dans
  le commit de la frappe ; spy : une carte non concernée ne re-rend pas ; (c) bascule → scroll
  préservé. (T2 — M, sonnet) (@lane: frontend/ios)

- [x] VX188 — **DevisGenerator : extraire `DevisLineRow` mémoïsé + `startTransition` sur les
  cascades de recalcul. @with/after VX62 — même fichier.** `DevisGenerator.jsx` : 64 `useState` ;
  les agrégats lourds sont DÉJÀ bien mémoïsés (`totals` :336-339, `roi`/`chartData` en
  `useDeferredValue` :354-358) MAIS le tableau de lignes (`lines.map` :1979) est du JSX inline :
  chaque frappe dans `note`/`farmSurfaceHa`/n'importe lequel des 63 autres états réconcilie N
  `<ProduitPicker>` (filtrage interne `ProduitPicker.jsx:44-66` tournant à vide) ; et
  `onProduitChange`/`onProduitCreated` sont recréés à chaque rendu. Fix : extraire `DevisLineRow`
  en `React.memo` + stabiliser les callbacks (clé de ligne en ARGUMENT, pas en fermeture) ;
  envelopper les 2-3 cascades de recalcul solar.js dans `startTransition` avec `isPending` sur le
  bloc TOTAUX — jamais sur l'input : la règle fondateur « ne jamais snapper/rejeter un nombre
  tapé » est un invariant absolu, ceci n'est qu'un changement d'ORDONNANCEMENT. Files :
  `pages/ventes/DevisGenerator.jsx`. DoD : taper dans « Note » sur un devis à 15 lignes ne re-rend
  PAS les ProduitPicker inchangés (spy) ; le test noValidate/step="any" reste vert. (T2 — M,
  sonnet) (@lane: frontend/ventes — @with/after VX62)

- [x] VX189 — (déjà présent) **Pack micro-perf mécanique : chunk `icons` unique, Sidebar `useMemo`, (@lane: frontend/ios)
  `content-visibility`, LoAF dev-warning.** Quatre gains prouvés, tous S, zéro dépendance : (a)
  126 chunks JS < 1 Ko gzip (icônes lucide individuelles, sur 345 chunks au total) —
  `manualChunks` dédié dans `vite.config.js:203-211` (`lucide-react` → chunk `icons` unique). (b)
  `Sidebar.jsx:238-246` recalcule la fusion `NAV_SECTIONS`+`moduleNavSections` et re-filtre par
  rôle À CHAQUE rendu — `useMemo` sur la fusion (statique) et le filtrage (`[role, permissions]`).
  (c) `content-visibility: auto; contain-intrinsic-size` sur les sections hors-écran de
  Dashboard/Rapports (paint sauté sans JS — vérifier que recharts ne casse pas sous
  content-visibility). (d) `lib/devPerfWarn.js` dev-only : `PerformanceObserver`
  `long-animation-frame` → `console.warn` formaté, gardé par `import.meta.env.DEV`, zéro octet en
  prod. **Note de coordination :** quand VX61 se construit, utiliser `web-vitals/attribution` et
  inclure `longAnimationFrameEntries` (top-3 scripts) dans le beacon — amendement du Done= de
  VX61, même fichier `vitals.js`, ne pas transcrire comme tâche. Files : `vite.config.js`,
  `components/layout/Sidebar.jsx`, CSS Dashboard/Rapports, `lib/devPerfWarn.js` (nouveau),
  `main.jsx`. DoD : chunks < 1 Ko ≈ 0-5 + un chunk `icons` unique, budget YHARD7 vert ; profiler :
  Sidebar ne recalcule que sur changement de rôle ; zéro saut de scrollbar ; tâche synthétique
  250 ms → table console en dev, zéro référence au module en build prod. Sora/`/landing` EXCLU —
  VX57 le possède. (T2 — S, haiku ; sonnet pour le c) (@lane: frontend/ios)

- [x] VX190 — **Garde CI WebKit étendue : exports blob + sticky DataTable + standalone. @after (@lane: frontend/ios — @after VX68)
  VX68 + VX172/176/178.** VX68 ajoute les projets `mobile-safari` (WebKit réel) + `tablet` mais ne
  teste NI l'export blob (VX172), NI le rendu sticky/`backdrop-blur` du DataTable (VX178), NI la
  navigation standalone (VX176/177). Fix : 3 assertions ajoutées au spec WebKit une fois VX68
  mergé : (a) clic « Exporter » aboutit par le chemin geste (pas d'échec silencieux) ; (b) scroll
  d'un DataTable large garde thead/tfoot lisibles (pas de détachement) ; (c) un `Sheet` en
  standalone simulé respecte l'inset haut. Files : `frontend/e2e/mobile-safari.spec.js` (ou le
  spec de VX68), `playwright.config.js`. DoD : les 3 assertions vertes en CI WebKit ; rouges si on
  régresse VX172/176/178. (T2 — S/M, sonnet) (@lane: frontend/ios — @after VX68)

**Sous-groupe VXD-C (suite) — Accessibilité forensique (WCAG 2.2 prouvée file:line)**

*Acquis vérifiés à NE PAS refaire : Radix (focus-trap/Échap/flèches), sonner déjà
`aria-live=polite`, anneau `:focus-visible` global + `scroll-margin` (`index.css:89-132`),
reduced-motion (`:67-87`), cibles 44px `pointer:coarse` (`:156-173`), DataTable exemplaire
(`aria-sort`/`scope`/live).*

- [x] VX191 — **`useActiveDescendant` : brancher `aria-activedescendant` sur les 10 (@lane: frontend/ios — @coord VX128)
  autocomplétions (grep = 0 partout).** *(Note : recoupe partiellement VX128 axe1 sur
  Combobox/MultiSelect/TimePicker — ce seed ÉTEND la couverture à `ProduitPicker.jsx`/
  `BcfProduitPicker.jsx`, `ToitureDesign.jsx`, `MentionAutocomplete.jsx`,
  `SlashCommandPicker.jsx`, `ShareRecord.jsx`, `GlobalSearch.jsx` — coordonner l'ordre
  d'implémentation avec VX128, ne pas dupliquer le hook.)* Le motif « champ texte → listbox avec
  curseur visuel » est réimplémenté 10 fois — et `aria-activedescendant` = 0 fichier dans tout le
  repo : flécher au clavier n'annonce RIEN (WCAG 4.1.2). Fix : hook
  `hooks/useActiveDescendant.js` (id stable par option, `aria-activedescendant` sur l'input,
  `id`/`aria-selected` sur l'option active), adopté d'abord dans `Combobox` + `MultiSelect`, puis
  `MentionAutocomplete` (+ le `Composer` qui la pilote) et `GlobalSearch`. Files : le hook
  (nouveau) + les 4 primitives citées. DoD : test RTL — l'input porte un `aria-activedescendant`
  pointant l'option `aria-selected` à chaque ↑/↓ ; VoiceOver/NVDA annonce le libellé. (T2 — M,
  sonnet) (@lane: frontend/ios — @coord VX128)

- [x] VX192 — **Kanbans accessibles : `StageMover` porté au kanban chantiers + `KeyboardSensor` +
  annonces FR sur les 3 kanbans + fin du `window.alert`.** Les 3 `<DndContext>` montent
  `useSensors(PointerSensor, TouchSensor)` sans `KeyboardSensor` ni
  `accessibility.announcements` (`crm/leads/views/KanbanView.jsx:173-209`,
  `installations/views/KanbanView.jsx:136-173`,
  `gestion_projet/…/TachesKanbanView.jsx:119-122`). Le kanban leads compense avec `StageMover`
  (`:31-53`, select clavier) ; le kanban CHANTIERS n'a RIEN : carte ouverte par `<div onClick>`
  non focalisable (`:178`), refus de déplacement en `window.alert()` bloquant (`:161`). Fix :
  porter `StageMover` au kanban chantiers, carte → `<button>`, `window.alert` → bandeau
  `role="status"` (patron leads `:211-218`) ; + `useSensor(KeyboardSensor)` (0 dép) et un helper
  d'annonces FR partagé sur les 3 kanbans. Files : les 3 `KanbanView`,
  `features/*/kanbanA11y.js` (helper nouveau). DoD : au clavier seul — Tab atteint le sélecteur
  d'étape et le change ; Espace saisit une carte, flèches déplacent, Entrée dépose, chaque étape
  annoncée en FR ; plus aucun `window.alert` (assert). (T2 — M, sonnet ; opus si l'entonnoir+clavier
  se complique) (@lane: frontend/ios)

- [x] VX193 — **LeadForm : labels associés + validation client annoncée ; AppointmentBooker : (@lane: frontend/crm — @with VX144)
  disclosure + tokens morts. @with VX144 + `ma-file` (même passe fichier).** Le plus gros
  formulaire CRM rend tous ses labels SANS `htmlFor` et ses inputs SANS `id` (helpers `Txt`/`Sel`
  `LeadForm.jsx:101-118` ; champs `:763-987`) ; les erreurs `form-feedback` (`:766,780`) n'ont ni
  `role="alert"` ni `aria-describedby`, l'input invalide pas d'`aria-invalid` (`:764`).
  `AppointmentBooker.jsx` : bouton révélateur sans `aria-expanded`/`aria-controls` (`:125-133`),
  labels nus (`:140,153`), erreur muette (`:163-167`), et des variables CSS INEXISTANTES
  (`--color-text-muted`, `--color-danger`… `:73-164`) qui cassent le dark mode. Fix : `id` (via
  `useId`) + `htmlFor` dans `Txt`/`Sel` — idéalement pointer le primitif `FormField` déjà correct
  (`ui/Form.jsx:93-104`) ; `aria-invalid` + `aria-describedby` → `form-feedback` avec `id` +
  `role="alert"` ; `aria-expanded`/`aria-controls` sur la disclosure ; migrer les `--color-*`
  morts vers les vrais tokens. Files : `pages/crm/LeadForm.jsx`,
  `pages/crm/leads/AppointmentBooker.jsx`. DoD : cliquer un label focalise son champ ; soumettre
  « Nom » vide → message annoncé + `aria-invalid` ; le bouton annonce réduit/développé ; dark mode
  réparé ; e2e leads verts. `DevisGenerator` fait correctement `htmlFor`, preuve que c'est un
  défaut d'écran. (T2 — M, sonnet) (@lane: frontend/crm — @with VX144)

- [x] VX194 — (déjà présent) **Plancher visuel WCAG 2.2 : texte accent brass 1.8:1 → ≥4.5:1 + cibles 24px (@lane: frontend/ios)
  desktop + test de contraste.** (a) `tokens.css:70` `--primary:#e8b54a` : en REMPLISSAGE de
  bouton c'est conforme, mais `Button` variant `link` = `text-primary` (`ui/Button.jsx:33`) rend
  le brass EN TEXTE sur `--background:#f6f8fc` ≈ 1.8:1 (échec 1.4.3 — 4.5:1 requis), consommé
  dans ≥10 pages et `text-primary` dans 48 fichiers ; `--warning:#c8870f` en texte ≈ 3.3:1. Fix :
  token dédié `--primary-text` (brass ASSOMBRI ≥4.5:1 — brass-600/700 déjà dans
  `tokens.css:36-37`) pour le variant `link` + les utilitaires de texte accent, idem warning ; test
  de contraste en calcul pur (0 dép) sur les paires Button des DEUX thèmes. (b) le plancher 44px
  n'existe que sous `pointer:coarse` — WCAG 2.5.8 (AA, 2.2) exige 24×24 px indépendamment du
  pointeur : cas prouvés `ChatterWidget.jsx:114` (Trash2 size=12), `chat-mention-item` → plancher
  24×24 via `IconButton` + les cas cités. Files : `design/tokens.css`, `ui/Button.jsx`,
  `ui/contrast.test.*` (nouveau), `ui/IconButton.jsx`, `components/ChatterWidget.jsx`. DoD : tout
  texte accent ≥4.5:1 clair ET sombre (le test échoue sinon) ; chaque bouton-icône ≥24×24 en
  pointeur fin. (T2 — M, sonnet) (@lane: frontend/ios)

- [x] VX195 — **Carte Leaflet accessible : rôle + liste clavier parallèle.**
  `components/MapView.jsx:115-121` : le conteneur n'a ni `role`, ni `aria-label`, ni fallback ; les
  marqueurs (`marker.on('click')` :102) ne sont pas focalisables — un technicien au
  clavier/lecteur d'écran n'a AUCUN accès aux leads/chantiers géolocalisés (CartePage,
  ParcInstallePage). Fix : `role="application"` + `aria-label` FR (« carte, N points ») ; liste
  clavier PARALLÈLE (chaque marqueur = un `<button>` dans une liste repliable/sr-only appelant le
  même `onMarkerClick`). 0 dép, Leaflet reste impératif. Files : `components/MapView.jsx`
  (CartePage/ParcInstallePage héritent). DoD : au clavier, Tab atteint chaque point via la liste et
  déclenche la même action ; VoiceOver annonce « carte, N points » ; test de la liste de boutons.
  (T2 — M, sonnet) (@lane: frontend/ios)

- [x] VX196 — **Régions live : chat/chatter annoncés + scroll clavier + erreurs toast en
  `assertive`.** (a) `MessageThread.jsx:104-135` : un message entrant pousse dans un `<div>`
  scrollable sans `aria-live` (WCAG 4.1.3) et sans `tabIndex`/`role`. (b)
  `ChatterWidget.jsx:100-126` : liste sans live ; bouton supprimer avec `title` seul (`:117`). (c)
  le succès d'un déplacement kanban n'émet aucun `role="status"` (seul l'échec en a un). (d)
  toutes les erreurs sonner partent en `polite` — une erreur bloquante devrait interrompre. Fix :
  `aria-live="polite"` + `aria-relevant="additions"` (n'annoncer QUE le dernier message) ;
  scroll-container `role="log"` + `tabIndex={0}` ; `aria-label="Supprimer le commentaire"` (le
  `title` reste pour VX52) ; `role="status"` sur le succès kanban ; dans `lib/toast.js`,
  `toastError` pose l'option sonner `assertive`/`important`, succès/info restent `polite`. Files :
  `features/messaging/MessageThread.jsx`, `components/ChatterWidget.jsx`, `lib/toast.js` (+
  `ui/Toaster.jsx` si région séparée). DoD : un message entrant est annoncé UNE fois ; le fil est
  défilable au clavier ; une erreur interrompt (assertive), un succès non ; tests RTL. (T2 — S,
  sonnet) (@lane: frontend/ios)

- [x] VX197 — (déjà présent) **`RouteFocus` : skip-link + focus `<main>` + navigation annoncée. @coord VX82 (@lane: frontend/ios)
  pour le titre.** `Layout.jsx:68-78` : `<main>` sans `id`/`tabIndex` ; la barre de progression de
  route (`role="progressbar"` :71-75) n'a pas d'`aria-live` ; 0 skip-link, 0 focus déplacé, 0
  repère après navigation SPA (WCAG 2.4.1/2.4.3). Fix : `<RouteFocus>` monté dans Layout — à
  chaque `location` : focus sur `<main id="contenu" tabIndex={-1}>`, annonce du nom d'écran via
  une région `aria-live="polite"` dédiée (source `routes.meta.js`, déjà là) ; skip-link « Aller au
  contenu » premier focalisable ; `aria-live` sur la barre de progression. NE PAS re-créer la
  gestion du titre d'onglet : **VX82 possède `useDocumentTitle`** — RouteFocus ANNONCE ce que VX82
  AFFICHE (consommer le même méta). Files : `components/layout/Layout.jsx`,
  `components/layout/RouteFocus.jsx` (nouveau), `routes.meta.js`. DoD : après navigation, Tab part
  du contenu (pas du header) ; le nom d'écran est annoncé une fois ; skip-link visible au premier
  Tab ; e2e clavier. (T2 — M, sonnet) (@lane: frontend/ios)

- [BLOCKED: dev-dep manquante, npm install impossible dans ce worktree — `eslint-plugin-jsx-a11y` absent de package.json/eslint.config.js ; la tâche elle-même se marque [GATED si dev-dep à ajouter]] VX198 — **[GATED si dev-dep à ajouter] Garde statique jsx-a11y ciblée : empêcher d'ÉCRIRE (@lane: frontend/ios)
  la régression (complément build du scan runtime VX71).** Rien n'empêche la réintroduction des
  trous ci-dessus (label sans contrôle, rôle sans props ARIA requises, interactif non
  focalisable) — `eslint-plugin-jsx-a11y` absent de la config (à confirmer ; sinon [GATED]
  dev-dep). Fix : sous-ensemble ciblé en warn→error : `label-has-associated-control`,
  `role-has-required-aria-props`, `interactive-supports-focus`, `click-events-have-key-events`,
  `img-redundant-alt`. Files : `frontend/eslint.config.js` (aucun code métier). DoD : `npm run
  lint` signale un `<label>` sans contrôle associé ; `frontend-lint` échoue sur une régression
  neuve ; le build actuel reste vert. (T2 — S, sonnet) (@lane: frontend/ios)

**Sous-groupe VXD-A (suite) — Sécurité frontend & observabilité (les échecs que personne ne
voit)**

*Non-défauts vérifiés à NE PAS re-signaler : auth par cookie httpOnly (aucun jeton en
localStorage, `AUTH_LOCALSTORAGE_KEYS=[]`), rendus chat/KB/copilote en arbres React (pas
d'injection), `rel=noopener` présent (faux positif multi-ligne), `prix_achat` correctement masqué
partout côté client.*

*Note : la graine TOTP 2FA exfiltrée vers `api.qrserver.com` (SEED-41) est déjà transcrite en
détail en tête de document — voir **VX120**. Ne pas la reconstruire ici.*

- [x] VX199 — **[BACKEND] `IsResponsableOrAdmin` : n'importe quelle permission d'écriture ouvre
  TOUS les endpoints qu'il garde (+ test d'alignement front↔back). ÉTEND VX101, ne pas
  double-compter.** `authentication/permissions.py:14-21` : la classe passe si
  `user.is_responsable` ; or depuis ERR4 (`models.py:211-234`), `is_responsable` = « le rôle
  accorde AU MOINS UNE permission d'écriture ». Un rôle « Commercial » (écrire des leads) passe
  donc les endpoints de validation de devis, émission de facture, mouvements de stock partout où
  cette classe grossière garde seule (famille = 614 occurrences / 156 fichiers ; le code
  documente lui-même le piège, `permissions.py:31-34`). Le frontend gate FINEMENT
  (`useHasPermission`) : l'écran CACHE le bouton mais l'API directe RÉUSSIT — la classe VX101, à
  l'envers et systémique. Fix : audit des viewsets en `IsResponsableOrAdmin` PUR → permission ERP
  fine (`HasPermissionOrLegacy('<domaine>_<action>')`, mécanique existante
  `permissions.py:54-121`) sur les actions sensibles UNIQUEMENT ; + test d'ALIGNEMENT : la liste
  blanche frontend (`useHasPermission.js:29-36`, `PRODUIT_CREATE_ROLES`) comparée au comportement
  backend réel, idéalement dérivée de `/auth/me` plutôt que d'une constante en dur. Files :
  `[BACKEND]` `ventes/views/{devis,facture,bon_commande}.py`, `stock/views/mouvement.py`,
  `crm/views.py` (remplacements de classe, additifs) ; `frontend/src/hooks/useHasPermission.js`.
  DoD : un compte « lecture + une écriture » reçoit 403 en appelant directement la validation de
  devis / l'émission de facture (étendre `tests_role_tier.py`) ; un test échoue si front et back
  divergent. **@coord VX101** (il corrige `decider_approbation`/`IsAnyRole` — même classe de bug,
  endpoints disjoints ; ne pas doubler). (T1 — L, opus : auth/permissions) (@lane: backend/auth)

- [x] VX200 **(already present)** — **[BACKEND infra] CSP figée sur des valeurs de DEV + zéro header de repli côté (@lane: backend/auth)
  SPA : templater la prod, décommenter HSTS.** `backend/nginx/Dockerfile` copie `nginx.conf`
  VERBATIM (pas d'envsubst) or `nginx.conf:78` code en dur `http://localhost:9000` (MinIO dev)
  dans `img-src`/`connect-src`/`frame-src` : en prod, les URL MinIO présignées réelles sont
  potentiellement BLOQUÉES ; HSTS est commenté (`:80`) alors que Caddy termine déjà le TLS ;
  `script-src` garde `'unsafe-inline' 'unsafe-eval'` (objectif : retirer `unsafe-eval` si maplibre
  le permet). Et `frontend/nginx.conf:1-41` (le serveur du SPA) ne pose AUCUN header. Fix : CSP
  par environnement (`envsubst` à l'entrypoint ou `map` nginx), retrait de `localhost:9000`, HSTS
  décommenté ; défense en profondeur : meta CSP de base dans `index.html` +
  `X-Frame-Options` répliqué dans `frontend/nginx.conf` (`frame-ancestors` est ignoré en meta —
  garder le header). Files : `backend/nginx/nginx.conf`, `backend/nginx/Dockerfile`,
  `docker-compose.prod.yml`, `frontend/index.html`, `frontend/nginx.conf`. DoD : en prod, `curl
  -I` → CSP sans `localhost:9000`, avec l'origine MinIO réelle, avec HSTS ; les aperçus MinIO
  s'affichent ; le SPA servi hors proxy garde CSP + anti-framing. (T2 — M, opus : headers
  sécurité) (@lane: backend/auth)

- [x] VX201 **(already present)** — **Pack durcissement client : DevTools coupé en prod, garde SVG + CI (@lane: backend/auth)
  anti-`dangerouslySetInnerHTML`, jeton kiosque expirant, presse-papier 2FA vidé.** Quatre petites
  failles prouvées, un lot : (a) `store/index.js:46-48` — `configureStore` sans `devTools:
  import.meta.env.DEV` : en prod, l'extension Redux DevTools expose TOUT l'état (PII, matrice de
  permissions, leads/devis/factures) → une ligne. (b) le SEUL `dangerouslySetInnerHTML` réel
  (`InterventionCapturePanels.jsx:476`, `qr_svg`) est sûr AUJOURD'HUI mais sans garde contre une
  régression serveur → helper `lib/trustedSvg.js` (commence par `<svg`, refuse
  `<script`/`on*=`/`javascript:`, repli neutre) + règle eslint `react/no-danger` en error avec UN
  disable documenté (ou `scripts/check_no_danger.mjs` dans `frontend-lint`). (c)
  `features/rh/Kiosque.jsx:16-47` : jeton de device (`X-Kiosque-Token`) en localStorage CLAIR et
  PERMANENT sur une tablette en libre-service → timeout d'inactivité qui `oublierToken()` +
  `safeStorage` (VX170) ; `[BACKEND]` rotation si retenue. (d)
  `SecuriteCompteSection.jsx:270-277` : codes de secours 2FA copiés en clair (presse-papier
  souvent synchronisé cloud) → vidage best-effort à ~60 s + micro-avertissement. Files :
  `store/index.js`, `lib/trustedSvg.js` (nouveau), `InterventionCapturePanels.jsx`,
  `eslint.config.js` OU `scripts/check_no_danger.mjs`, `features/rh/Kiosque.jsx`,
  `SecuriteCompteSection.jsx`. DoD : build prod → DevTools n'affiche aucun store ; un `qr_svg`
  contenant `<script>` est refusé ; un `dangerouslySetInnerHTML` non whitelisté fait échouer
  `frontend-lint` ; le kiosque redemande le jeton après inactivité ; le presse-papier est vidé au
  délai (mock). (T2 — M, sonnet) (@lane: backend/auth)

- [x] VX202 **(already present)** — **[BACKEND nginx] Pages publiques tokenisées : `noindex` + throttle client + (@lane: backend/auth)
  rate-limit des préfixes publics.** 10 routes `:token` publiques sans auth
  (`router/index.jsx:216-235` : `/rdv`, `/portail-contrats`, `/ged/signature|signataire|depot`,
  `/e`, `/suivi`, `/kb/public`…). Aucune page ne pose `<meta name="robots" content="noindex">` ;
  le rate-limit nginx n'existe QUE sur login/contact/register (`nginx.conf:86-118`) — rien sur
  `/ged/`, `/suivi/`, `/rdv/`, `/e/` ; le dépôt public (`PublicDepotPage.jsx:42-58`) n'a aucun
  throttle de re-soumission. Fix : composant `<NoIndex/>` partagé monté par toutes les pages
  publiques tokenisées ; throttle client de re-soumission sur le dépôt ; `[BACKEND]` étendre les
  zones `limit_req` aux préfixes publics. Files : `pages/ged/PublicDepotPage.jsx`,
  `PublicSignaturePage.jsx`, `pages/sav/TicketSuiviPage.jsx`, `pages/crm/PublicBookingPage.jsx`,
  `pages/kb/PublicArticlePage.jsx`, composant `NoIndex` (nouveau) ; `[BACKEND]`
  `backend/nginx/nginx.conf`. DoD : chaque page publique émet le meta noindex ; une re-soumission
  est throttlée ; `/ged/depot/<t>/` répond 429 sous rafale. (T2 — M, sonnet) (@lane:
  backend/auth)

- [BLOCKED: partiel — voir DONE LOG 2026-07-12 ; codemod ~104 fichiers + garde CI restent hors budget d'une session sans build/lint] VX203 — **Contrat d'erreur UNIQUE : fin du double-toast (35 pages), `getApiError` (@lane: frontend/data)
  canonique (259 clones), `iaApi` aligné (le 403 IA n'est plus muet).** Trois moitiés du même
  contrat, explicitement renvoyées à l'axe robustesse par la synthèse beauté : (a)
  `api/axios.js:63-70` toaste DÉJÀ toute erreur ≠401/404, mais ~35 pages re-toastent dans leur
  `catch` (3 fichiers seulement posent `suppressErrorToast`) → DOUBLE toast sur des centaines de
  chemins. Contrat : l'intercepteur est la source par défaut ; tout `catch` qui gère INLINE passe
  `{suppressErrorToast:true}` ; garde grep `scripts/check_double_toast.mjs` dans frontend-lint.
  (b) 259 extractions inline `.response?.data?.detail` ré-implémentent une version PARTIELLE du
  helper existant (`lib/toast.js:92-107`) — promouvoir `lib/apiError.js` (`{message,
  fieldErrors}`, cas `non_field_errors`/tableaux/429/500 HTML/timeout), codemod des sites vers
  l'import unique (VX171 en consomme `fieldErrors`). (c) `iaApi.js` ne toaste RIEN globalement
  hors 401 : un 403 du catalogue d'actions agentiques ou un 500 FastAPI est INVISIBLE — aligner
  sur le contrat (a) en préservant les dégradations volontaires (`available:false`) via
  `suppressErrorToast`. Files : `api/axios.js`, `api/iaApi.js`, `lib/apiError.js` (extrait de
  toast.js), les ~35 pages fautives, `scripts/check_double_toast.mjs` (nouveau). DoD : un 500
  forcé = EXACTEMENT un toast (test) ; grep `.response?.data?.detail` hors helper = 0 ; un 403 IA
  surface un toast FR ; tests des formes DRF. (T2 — M/L, sonnet) (@lane: frontend/data)

- [x] VX204 — **Fin des veuves silencieuses : ChatterWidget, ActivitiesPanel, Journal +
  détection de panne prolongée des polls.** Quatre silences prouvés hors des 5 listes de VX67 :
  (a) `ChatterWidget.jsx:66-80` — l'échec d'envoi d'un commentaire est `catch { /* ignore */ }` ;
  l'intercepteur ne toaste pas les 404 → zéro signal. (b) `ActivitiesPanel.jsx:32-42` — `load()` +
  types en `.catch(() => {})` : un échec de chargement est INDISCERNABLE de « aucune relance
  due » (le state `error` existe ligne 26, jamais alimenté). (c) `Journal.jsx:235` —
  `getMeta().catch(() => {})` : les filtres de L'OUTIL D'AUDIT rendent des menus vides sans dire
  qu'ils sont cassés. (d) `useChatPolling.js:51-63` (aucun `.catch`) et
  `NotificationBell.jsx:115-138` : rien ne détecte une SÉRIE d'échecs. Fix : états d'erreur locaux
  + « Réessayer » (patron ActivitiesPanel) sur a/b/c ; compteur d'échecs consécutifs (≥3 →
  indicateur discret « Mise à jour interrompue » + reprise manuelle, reset au premier succès) sur
  la cloche et le chat. Files : `components/ChatterWidget.jsx`, `components/ActivitiesPanel.jsx`,
  `pages/Journal.jsx`, `features/messaging/useChatPolling.js`,
  `components/layout/NotificationBell.jsx`. DoD : par widget — un rejet rend un message +
  Réessayer (jamais une liste vide muette) ; 3 échecs simulés → indicateur, un succès →
  disparition. Distinct du rejet « refonte chatter » (VX23/ARC8-9) — correctif d'erreur, pas une
  refonte. (T2 — M, sonnet ; haiku sur a/b) (@lane: frontend/data)

- [x] VX205 **(already present)** — **Déployer la `SectionBoundary` DÉJÀ CONSTRUITE : un panneau meurt, l'écran (@lane: frontend/data)
  survit.** `ui/ErrorBoundary.jsx:7-59` est un composant COMPLET (fallback custom, `reset()`,
  `onError`) monté dans UN SEUL fichier réel : la page de démo (`UIShowcase.jsx:507-553`). VX64 ne
  couvre que le niveau ROUTE ; mémoire projet : « /ui crashes whole-page on render throw ». Fix :
  pure tâche de DÉPLOIEMENT (rien à construire) — poser `<ErrorBoundary>` autour des zones
  indépendantes à risque : chaque `TabsContent` de `LeadForm.jsx`, cartes cockpit
  `Dashboard`/`CommercialDashboard`, `InterventionCapturePanels.jsx` ; câbler `onError` sur le
  `console.error` structuré de VX206. Files : `pages/crm/LeadForm.jsx`, `pages/Dashboard.jsx` (+
  cockpit), `InterventionCapturePanels.jsx`. DoD : un enfant qui throw dans UN onglet ne fait
  disparaître QUE cet onglet, le reste reste utilisable ; la RouteErrorBoundary parente n'intercepte
  plus ces cas. (T2 — M, sonnet) (@lane: frontend/data)

- [x] VX206 — **Socle local d'observabilité : `console.error` des boundaries + (@lane: frontend/data — @with VX72)
  `unhandledrejection` global + identifiant support. @with VX72 (mêmes fichiers).** Zéro
  télémétrie locale : `console.error` = 1 hit dans tout `src/` ; les DEUX boundaries
  (`ui/ErrorBoundary.jsx`, `RouteErrorBoundary.jsx` — qui n'a même pas de `componentDidCatch`)
  n'écrivent RIEN. Et aucun `window.addEventListener('unhandledrejection'|'error')` : une promesse
  rejetée dans un handler d'événement, une chaîne `.then()`, ou le `sender()` de l'outbox échoue
  en silence TOTAL — invisible même après VX72, qui ne câble QUE
  `RouteErrorBoundary→captureException`. Fix : `console.error('[ErrorBoundary]', error,
  info?.componentStack)` dans les deux boundaries (ajouter `componentDidCatch` à
  RouteErrorBoundary) ; `lib/globalErrors.js` — les deux listeners globaux canalisés vers le MÊME
  chemin captureException-ou-no-op que VX72 établit + un `toastError` générique ; afficher un
  identifiant support sur l'écran de récupération (l'`eventId` VX72 quand DSN actif, sinon un
  horodatage court). Files : `ui/ErrorBoundary.jsx`, `components/RouteErrorBoundary.jsx`,
  `lib/globalErrors.js` (nouveau), `main.jsx` (+ `lib/monitoring.js` de VX72). DoD : un throw →
  `console.error` avec stack ; une promesse rejetée non gérée → toast + capture (DSN de test) ;
  sans DSN → zéro requête sortante ; l'écran de récupération montre un identifiant transmissible.
  (T2 — S, sonnet) (@lane: frontend/data — @with VX72)

---

## AXE 3 — AMOUR-EMPLOYÉ (VX207–VX252, 46 tâches survivantes sur 47 seeds ; 1 tuée par le
grand-verdict — SEED-03 — dont le delta est reporté en note sur VX56/VX86, jamais transcrit
comme tâche)

**Sous-groupe VXD-I — Attention & handoffs (le badge redevient CROYABLE). @after
VX83-86/99-101 (round 3, non construit) — transcrire chaque @after tel quel.**

- [x] VX207 **(already present)** — **[BACKEND additif] Une seule vérité de comptage : endpoint canonique (@lane: backend/notify — @after VX83/VX86)
  `attention-summary`. @after VX83/VX86.** Après VX83/84/86 il existera ≥4 dérivations de
  compteur calculées par des chemins différents (badge cloche = `derivedTotal + feedUnread`
  `NotificationBell.jsx:182`, en-tête Ma file, `useApprobationsCount` VX86, badge sidebar) — rien
  ne garantit qu'elles convergent, et un badge qui ment tue tout le système d'attention. Fix :
  `GET /notifications/attention-summary/` renvoyant le décompte canonique `{actions_dues,
  en_retard, aujourdhui, approbations, mentions_non_lues}` scopé `recipient`/`assigned_to`,
  réutilisant les MÊMES selectors que « Ma file » (VX83) ; cloche, badge sidebar et en-tête Ma
  file consomment tous ce seul endpoint. Files : `apps/notifications/views.py`+`selectors.py`,
  `NotificationBell.jsx`, `useApprobationsCount.js` (VX86). DoD : test de contrat — forcer 5 items
  → les 3 surfaces affichent 5 ; aucune dérivation client parallèle restante. (T2 — M, sonnet)
  (@lane: backend/notify — @after VX83/VX86)

- [x] VX208 **(already present)** — **[BACKEND additif] La cloche cesse d'être une liste plate : sévérité, regroupement (@lane: backend/notify — @with VX14)
  par entité, digest hors badge, et undo. @with VX14 (même fichier — la mise en onglets appartient
  à VX14, cette seed apporte la taxonomie/dédoublonnage/compteurs/undo).** Trois défauts prouvés
  sur la même surface : (a) `EventType` a 42 valeurs sans rang de sévérité ni catégorie — la
  cloche affiche un incident QHSE critique noyé sous des digests, 5 notifs même facture = 5
  lignes ; (b) `DIGEST` passe par `notify()` → `feedUnread` → badge (`digests.py:169`), donc le
  badge gonfle chaque matin d'un non-travail ; (c) `read-all` est irréversible et `mark_unread`
  (`views.py:68`, `notificationsApi.js:11`) a zéro consommateur. Fix : dict statique
  `EVENT_SEVERITY`/`EVENT_CATEGORY` (`apps/notifications/severity.py`, exposé en lecture dans le
  serializer, pas de migration) ; frontend — groupement par catégorie + dédoublonnage par `link`,
  liseré `critique`, deux compteurs (badge rouge ACTIONS / point gris INFOS, digests dans un
  onglet plié), `read-all` → `toastWithUndo` restaurant via `mark_unread`, bouton « Marquer
  non-lu ». Files : `apps/notifications/{severity.py,serializers.py,views.py}`,
  `NotificationBell.jsx`. DoD : un `INCIDENT_CRITICAL` remonte au-dessus de 10 `DIGEST` ; un
  digest n'incrémente pas le badge d'actions ; « Tout lu » puis « Annuler » restaure l'état exact ;
  3 notifs même lien = 1 ligne pliée. (T2 — L, sonnet) (@lane: backend/notify — @with VX14)

- [x] VX209 — **[BACKEND] `notify()` devient humain : heures calmes, bon event de mention, (@lane: backend/notify)
  purge, émetteurs manquants.** Quatre défauts du même moteur : (a) `est_hors_fenetre_silence()`
  (`selectors.py:23`) n'est consulté que par le marketing ET la compta (`compta/services.py:6083`),
  jamais par `notify()` lui-même — un push/email de `sweep_daily` ou d'escalade part à 23 h ou un
  jour férié ; (b) `_notify_mentions` (`records/views.py:315`) émet `ET.LEAD_ASSIGNED` pour une
  @mention : couper la préférence `lead_assigned` coupe silencieusement ses mentions, et le
  libellé ment — `CHAT_MENTION` (`models.py:69`) existe ; (c) la table `Notification` grossit sans
  borne (zéro `.delete()` repo-wide, `list()` renvoie tout) ; (d)
  `SAV_ACTIVITE_DUE`/`STOCK_EXPIRATION_SOON` sont déclarés jamais émis, et warranty/maintenance
  notifient les managers même quand un owner existe (`sweeps.py:104,146`). Fix : flag
  `respect_quiet_hours` (défaut on) différant les canaux hors-app non-critiques via le calendrier
  ouvré FG5 (in-app toujours immédiat) ; one-liner `CHAT_MENTION` (@coord VX85, même fonction) ;
  tâche Celery `purge_notifications_anciennes` (lues > 60 j supprimées, non-lues archivées,
  `list()` borné 90 j) ; étendre `sweep_daily` aux 2 events morts + routage owner-d'abord. Files :
  `apps/notifications/{models,services,selectors,sweeps,views}.py` + migration additive,
  `apps/records/views.py`, `NotificationsPreferences.jsx` (toggle). DoD : un `notify()`
  non-critique à 23 h ne part pas en email (in-app créé) ; une mention crée `chat_mention` ; une
  notif lue de 61 j est purgée ; un lot proche péremption émet `STOCK_EXPIRATION_SOON` ; tests.
  (T2 — L, sonnet) (@lane: backend/notify)

- [x] VX210 **(already present)** — **[BACKEND additif] Le snooze devient un rappel actif, généralisé, et déclenché par (@lane: backend/notify — @after VX85)
  l'événement métier. @after VX85.** VX85 pose `snoozed_until` + exclusion passive sur
  `records.Activity` seulement — rien ne RÉVEILLE l'item ni ne re-notifie à l'échéance. Fix : (a)
  sweep Celery `reveiller_snoozes` — à échéance, l'item revient dans la file ET émet une
  `notify()` légère « ⏰ De retour : {titre} » ; (b) table générique `SnoozedItem` (content-type,
  pattern `ApprovalReminderState`) pour snoozer aussi une approbation/facture depuis la file ; (c)
  champ optionnel `snooze_trigger_event` (choix fermés : `client_reply:<lead>`,
  `devis_signed:<devis>`, `stock_arrive:<produit>`) abonné sur `core/events.py` — le premier de
  l'horloge ou de l'événement gagne ; le picker VX85 gagne 1-2 options contextuelles « jusqu'à… ».
  Files : `apps/records/{models,services}.py`, `apps/notifications/{models,sweeps}.py` +
  migrations, `ActivitiesPanel.jsx`, `MesActivitesPage.jsx`. DoD : un item snoozé « ce soir »
  réapparaît + notifie au sweep suivant ; un item « jusqu'à réponse client » revient dès la
  `LeadActivity` entrante même avant l'échéance ; snoozer une approbation la masque puis la
  ramène ; tests des 2 chemins de sortie. (T2/T3 — M/L, sonnet ; opus si le générique cross-source
  dérape) (@lane: backend/notify — @after VX85)

- [x] VX211 **(already present)** — **« Ma file » par persona + départage « victoires rapides ». @after VX83.** VX83 (@lane: backend/notify — @after VX83)
  construit UNE union triée par urgence globale, identique pour tous — or
  commercial/comptable/technicien/directeur ont des priorités radicalement différentes. Fix
  frontend : `queueViewForRole(role)` (rôle déjà dans le store, `MesActivitesPage.jsx:66`) posant
  l'ORDRE des sections par défaut (commercial : relances → leads chauds → devis expirants ;
  comptable : factures échues → approbations ; terrain : interventions du jour ; direction :
  approbations → escalades), surcharge persistée `localStorage`, jamais un mur (« Tout voir »
  reste) ; + [BACKEND léger] champ `effort_estime` déterministe par `kind` sur `ma-file/` (table
  statique, pas de ML) alimentant un tri secondaire optionnel « Victoires rapides d'abord » —
  uniquement un DÉPARTAGE entre items d'urgence égale. Files :
  `frontend/src/features/queue/queueViews.js` (nouveau), `MesActivitesPage.jsx`,
  `apps/records/views.py` (serializer). DoD : un commercial voit Relances en tête, un comptable
  Factures échues ; à urgence égale l'item `faible` précède l'`eleve` quand l'option est active ;
  le tri par défaut reste inchangé sinon ; STAGES.py importé pour toute clé de stage. (T2 — M,
  sonnet) (@lane: backend/notify — @after VX83)

- [x] VX212 **(already present)** — **[BACKEND additif léger] Transparence « pourquoi je reçois ça » + contexte (@lane: backend/notify — @after VX99/VX100)
  décisionnel dans l'email d'approbation. @after VX99/VX100.** `resolve_recipients`
  (`services.py:275`) applique des règles invisibles — des notifs « pourquoi moi ? » qu'on ne peut
  couper qu'en fouillant la grille des 42 événements ; et l'email de demande d'approbation
  n'embarque pas le montant/contexte. Fix : (a) `reason` court sur la ligne Notification
  (`'assigné à vous'|'manager'|'règle de routage'|'vous suivez'`), rendu sous chaque notif avec
  « Régler » → deep-link `/parametres/notifications#<event>` ; (b) enrichir le template email
  d'approbation avec montant + 1-2 lignes de contexte (déjà exposés par VX100 côté API) — jamais
  de bouton « Approuver » par lien email (pas de mutation non-authentifiée). Files :
  `apps/notifications/{models,services,serializers}.py` + migration, templates email
  notifications, `NotificationBell.jsx`, `NotificationsPreferences.jsx`. DoD : une notif montre sa
  raison et « Régler » ouvre la bonne ligne de préférence ; l'email d'approbation contient montant
  + résumé dans le corps (snapshot test). (T2 — M, sonnet) (@lane: backend/notify — @after
  VX99/VX100)

**Sous-groupe VXD-I (suite) — Handoffs cross-persona (la main gauche apprend ce que fait la
droite)**

- [x] VX213 — **[BACKEND] Notifier les handoffs AVAL : chantier créé, chantier réassigné,
  réquisition (2 bords), + SLA ballon-perdu. @after VX99.** Le motif systémique prouvé : l'amont
  (lead→vendeur, approbations compta) notifie, l'aval (exécution) est muet. (a)
  `create_installation_from_devis` (`installations/services.py:205`) assigne
  `technicien_responsable` avec ZÉRO `notify()` — le plus gros transfert de l'entreprise est
  silencieux ; (b) réassigner un chantier (`InstallationsPage.jsx:259`) ne notifie pas le nouveau
  technicien alors que `_notifier_reassignation` (`services.py:2296`) le fait déjà pour la
  replanification d'intervention ; (c) **rogné (grand-verdict) :** la notif de SOUMISSION d'une DA
  vers les approbateurs = VX99, ne pas la re-câbler — seul le bord RETOUR reste muet :
  `approuver`/`refuser` (`demande_achat.py:96/113`) ne notifient jamais le DEMANDEUR de la
  décision ; (d) aucun SLA sur une DA restée SOUMISE. Fix : notify idempotent à `created=True`
  (« Nouveau chantier assigné », lien `?installation=<id>`), diff pre/post sur
  `technicien_responsable`, notify du demandeur à la décision (motif si refus ; montant estimé
  client-safe, jamais dérivé de `prix_achat`), et `_sweep_da_soumise_stale` miroir de
  `_sweep_sav_breaching`. Files :
  `apps/installations/{services.py,receivers.py,views/demande_achat.py,views/installation.py}`,
  `apps/notifications/sweeps.py`, `apps/installations/selectors.py`. DoD : accepter un devis →
  notif dans la cloche de l'installateur (ré-accepter n'en recrée pas) ; réassigner → notif au
  nouveau ; décider une DA → le demandeur notifié ; une DA soumise > seuil relance les
  approbateurs ; tests des transitions. (T1 — M, sonnet) (@lane: backend/notify — @after VX99)

- [x] VX214 **(already present)** — **[BACKEND additif] [RESHAPÉE — grand-verdict] Les kinds d'EXÉCUTION entrent dans (@lane: backend/notify — @after VX83)
  « Ma file » (jamais une 2ᵉ boîte). @after VX83.** `MesActivitesPage` n'agrège que
  `records.Activity` et `ApprobationsPage` que les approbations — un chantier assigné, une
  intervention à faire, une DA approuvée à commander, un ticket transféré n'apparaissent dans
  AUCUNE boîte. Fix (reshape imposé) : ne PAS créer d'endpoint `mes-affectations-entrantes/` ni de
  page `MesAffectationsPage` parallèles — étendre l'endpoint `ma-file/` de VX83 avec les kinds
  d'exécution (`chantier_assigne`, `intervention_du_jour`, `da_approuvee_a_commander`,
  `ticket_transfere`) via une fonction lecture-seule `selectors.affectations_pour(user)` par app
  cible (scopé company+user serveur), et laisser VX211 (vues par persona) ordonner ces sections —
  sinon l'ERP finit avec DEUX boîtes de réception concurrentes, l'anti-pattern que VX83 a été
  conçu pour tuer. Files : `apps/records/views.py` (l'action `ma-file/` de VX83),
  `apps/{installations,sav}/selectors.py` (une fonction chacun),
  `frontend/src/pages/activities/MesActivitesPage.jsx` (rendu des nouveaux kinds). DoD : un
  installateur ouvre Ma file et voit son chantier fraîchement assigné + interventions + tickets à
  côté de ses activités, triés urgence ; scoping company/user testé serveur ; aucun endpoint ni
  écran parallèle créé. (T3 — L, opus : agrégateur cross-app = jugement frontières) (@lane:
  backend/notify — @after VX83)

- [x] VX215 — **Boucle de retour « pris en charge » : l'émetteur sait que le ballon est (@lane: backend/notify)
  attrapé.** Grep `accuser|prise en charge|acknowledge|seenBy` = 0 hit métier — le système est
  100 % push unidirectionnel. Fix frontend-first : version minimale = afficher l'état `read` déjà
  persisté de la notification liée là où l'action a été initiée (ex. « avis lu par le directeur »
  sur le devis après `contacterSuperieur`) ; version complète [BACKEND minime] = flag
  `acknowledged` + bouton « Je prends en charge » dans la cloche sur les notifs de handoff à fort
  enjeu, l'émetteur voyant « Pris en charge par X ». Files : `NotificationBell.jsx`,
  `pages/ventes/DevisList.jsx`, `api/notificationsApi.js`, `[BACKEND]` serializer léger exposant
  l'état de la notif liée. DoD : après « demander l'avis du supérieur », le vendeur voit passer
  « vu » quand le directeur ouvre la notif ; test de rendu. (T2 — M, sonnet ; S en version lecture
  seule) (@lane: backend/notify)

- [x] VX216 — **Rendre les seams VISIBLES des deux côtés : divergence devis↔chantier, ticket
  résolu par intervention, fil de responsabilité.** Trois lacunes de lecture jumelles : (a)
  `InstallationDetail.jsx:252-271` détecte `devisDivergent` (bom gelé ≠ devis actuel) côté
  installateur SEULEMENT ; (b) `sav/receivers.py` (YSERV2) avance le ticket à RESOLU quand
  l'intervention se termine, mais le ticket ne montre jamais QUELLE intervention l'a résolu
  (`TicketsPage.jsx:579` lie vers `/chantiers` générique) ; (c) personne ne voit la CHAÎNE de
  responsabilité du client quand il rappelle. Fix : badge « Chantier en cours (compo gelée) » +
  `toastWarning` à l'édition sur DevisList ; « Résolu par l'intervention #X du {date} par {tech} »
  avec lien profond sur le détail ticket ; mini-composant `<OwnerChain>` (avatars + rôle + étape)
  sur InstallationDetail et fiche client. Files : `DevisList.jsx`, `TicketsPage.jsx`,
  `components/OwnerChain.jsx` (nouveau), `InstallationDetail.jsx` ; `[BACKEND]` éventuels flags
  légers de serializer si un lien manque. DoD : éditer un devis lié à un chantier avec bom →
  avertissement ; ticket résolu par intervention → lien vers elle ; un chantier montre « Lead : A ·
  Devis : B · Chantier : C · SAV : D » cliquable ; tests de rendu. (T2 — M, sonnet) (@lane:
  backend/notify)

- [x] VX217 **(already present)** — **La cloche finit le travail : aperçu sans naviguer, actions par entité, (@lane: backend/notify — @after VX208)
  bottom-sheet mobile. @after VX208.** Trois compléments du même organe : (a) chaque item de
  cloche/file est un cul-de-sac de navigation (`NotificationBell.jsx:272-275`, `goto(n.link)`) —
  traiter 8 relances = 8 allers-retours d'écran ; (b) les actions sont 100 % unitaires ; (c)
  `.nb-panel` (`NotificationBell.jsx:218`) est un panneau absolu desktop qui déborde sur mobile,
  sans safe-area, alors que `ResponsiveDialog` existe (VX89 l'adopte). Fix : `<AttentionPeek>`
  (popover survol desktop / tap-and-hold mobile : client, montant si pertinent — jamais
  `prix_achat` —, échéance, dernière action, bouton « Ouvrir ») rendu depuis les données déjà dans
  la notif ; une fois le regroupement par entité de VX208 posé, actions de groupe « Tout marquer
  lu » / « Reporter le lot » (boucle sur les mutations unitaires + `toastWithUndo` global, aucune
  mutation serveur nouvelle) ; sur breakpoint mobile la cloche s'ouvre en bottom-sheet
  (`env(safe-area-inset-bottom)`, desktop inchangé). Files :
  `frontend/src/features/queue/AttentionPeek.jsx` (nouveau), `NotificationBell.jsx`,
  `MesActivitesPage.jsx`, `index.css` (`.nb-panel` responsive). DoD : survoler une relance montre
  son aperçu sans changer d'URL ; 3 notifs même entité → « Tout marquer lu » en un clic avec
  undo ; sur WebKit mobile (projet VX68) la cloche respecte l'encoche ; `prix_achat` jamais rendu ;
  e2e verts. (T2 — M, sonnet) (@lane: backend/notify — @after VX208)

- [x] VX218 — **Le handoff se voit aussi CÔTÉ RÉCEPTION et DANS LE TEMPS : « Nouveau pour moi » +
  état d'escalade lisible.** Deux trous jumeaux de VX213/VX215 : (a)
  `InstallationsPage.jsx:40` a un filtre `mine=only` mais rien ne distingue un chantier
  NOUVELLEMENT confié d'un ancien ; (b) `APPROVAL_ESCALATED`/`APPROVAL_REMINDER` (YEVNT9)
  notifient, mais le DEMANDEUR ne voit nulle part un état persistant « votre demande a été
  escaladée à N+2, relancée le … » sur sa propre vue. Fix : badge « Nouveau » sur les chantiers
  assignés à l'utilisateur depuis sa dernière visite (timestamp `lastSeenChantiers` en
  localStorage via le helper défensif `safeStorage` — VX170, @coord) + raccourci de filtre « Mes
  nouveaux chantiers » ; colonne/ligne état d'escalade (niveau + dernière relance) côté demandeur
  dans `ApprobationsPage`, [BACKEND léger] exposer le niveau dans
  `reporting/approbations.py` si absent. Files : `pages/installations/InstallationsPage.jsx`,
  `pages/approbations/ApprobationsPage.jsx`, `apps/reporting/approbations.py`. DoD : un chantier
  assigné après ma dernière visite affiche « Nouveau », ouvrir l'écran l'efface ; une approbation
  escaladée montre son niveau au demandeur ; tests. (T2 — S/M, sonnet) (@lane: backend/notify)

**Sous-groupe VXD-K — Le commercial : chaque job compté en clics**

- [x] VX219 — **« Mes chiffres » : le vendeur `normal` voit ENFIN sa propre performance. @coord (@lane: frontend/crm — @coord VX27)
  VX27.** Défaut prouvé : `/reporting` ET `/reporting/commercial` sont gatés
  `roleLoader(['responsable','admin'])` (`router/index.jsx:319,322`) ; `Dashboard.jsx` est
  company-wide ; le seul KPI perso (FG39, `CrmInsightsPanel`) n'est rendu QUE dans
  `ChartsView.jsx:288` (l'onglet graphique des leads, ouvert 1×/semaine). Fix frontend-first :
  carte « Mes chiffres » en tête de `Dashboard.jsx`, tous rôles — devis envoyés/acceptés du mois,
  taux de signature, CA signé, atteinte d'objectif (réutiliser `crmApi.getObjectifsAttainment`
  FG39 déjà livré) + 3 leads chauds à traiter ; dériver des slices déjà chargés filtrés
  `owner===me` côté client ; [BACKEND additif] `?owner=me` seulement si la justesse l'exige ; ne
  JAMAIS dé-gater `/reporting/commercial` (reste l'outil manager). Files :
  `frontend/src/pages/Dashboard.jsx`, `CrmInsightsPanel.jsx` (extraire la carte en composant),
  éventuellement `apps/crm/selectors.py`. DoD : un `normal` ouvre `/dashboard` et voit SES
  métriques (test : la carte n'agrège que `owner==user`) ; le gate manager inchangé. (T2 — M,
  sonnet) (@lane: frontend/crm — @coord VX27)

- [x] VX220 — **⌘K atterrit sur le RECORD (pas la liste) + créations au clavier. @after VX79, (@lane: frontend/crm — @after VX79)
  @coord NTUX9/10.** Défaut prouvé : `CommandPalette.jsx:24-33` route
  `devis/client/facture/chantier/equipement/ticket` vers leur LISTE — seul `lead` ouvre la fiche.
  Et `shortcuts.js` = 8 `g x` de nav, 0 action « créer » (`commandActions.js:13`). Fix : (a)
  réutiliser la convention de deep-link `?id=` de VX79 dans le mapping `ROUTE` de la palette, et
  étendre la lecture du param à `FactureList.jsx`/`ClientList.jsx` — une seule convention de
  param, jamais deux ; (b) 2-3 raccourcis `c l`/`c d`/`c c` (créer lead/devis/client) dans
  `shortcuts.js` + section « Créer » de la palette — périmètre réduit : NTUX possède le
  quick-create palette générique, ici SEULEMENT les raccourcis clavier directs et le câblage
  `?new=1`, @coord NTUX9/10 (vérifier-non-déjà-construit avant build) ; (c) vérifier
  l'exhaustivité `GOTO_SHORTCUTS` vs routes de premier niveau (`/planification`,
  `/approbations`). Files : `providers/CommandPalette.jsx`, `providers/shortcuts.js`,
  `commandActions.js`, lecteurs `?id=`/`?open=` des listes citées. DoD : chercher une référence
  dans ⌘K ouvre le record exact ; `c l` ouvre le form lead ; toute route de premier niveau a son
  `g x` ; tests du mapping. (T2 — M, sonnet) (@lane: frontend/crm — @after VX79)

- [x] VX221 — **Le score de lead dit enfin POURQUOI (tooltip de raisons + tri).** Défaut prouvé :
  `ListView.jsx:83-99` affiche `score`/100 nu ; `serializers.py:240` calcule `score_label` via
  `compute_score(obj)` mais aucune décomposition n'est exposée. Fix : [BACKEND additif léger]
  exposer `score_reasons` (liste `{facteur, points}`) depuis `apps/crm/scoring.py` (pure exposition
  des composantes déjà calculées, zéro recalcul) ; tooltip riche sur `ScoreBadge` (« +30 facture
  élevée · +20 récent · +15 canal web ») + badge score sur `LeadCard` (absent aujourd'hui) +
  colonne triable. Files : `apps/crm/{scoring,serializers}.py`,
  `frontend/src/pages/crm/leads/views/ListView.jsx`, `LeadCard.jsx`. DoD : survoler le badge
  montre les 2-3 facteurs dominants ; test serializer company-scopé. (T2 — S/M, sonnet) (@lane:
  frontend/crm)

- [x] VX222 — **« Relancer ce devis » : le pendant devis de la relance facture.** Défaut prouvé :
  `DevisList.jsx:736-741` calcule `expiringSoon` (envoyés expirant ≤7 j) et affiche un bandeau —
  mais AUCUNE action : la relance structurée n'existe QUE pour les factures (`RelancesPage`). Fix :
  bouton « 🔔 Relancer » sur les lignes `statut==='envoye'` qui rouvre le flux WhatsApp/email
  EXISTANT (`handleEnvoyer:410`, `openEmailModal:238`) avec un message « relance » (pas « envoi
  initial ») + consigne au chatter du devis (`DevisActivity`, cf. VX97) ; aperçu-puis-clic, jamais
  d'envoi auto (règle manuel-wa.me fondateur). Files : `frontend/src/pages/ventes/DevisList.jsx`.
  DoD : un devis envoyé propose « Relancer » → même modale en mode relance + entrée chatter ;
  l'action n'apparaît que sur `envoye` ; test. (T2 — S/M, sonnet) (@lane: frontend/ventes)

- [x] VX223 — **[BACKEND léger] Actions de carte en 2 clics : « ✗ Perdu (motif) », file (@lane: frontend/crm — @after VX83)
  « Rappels demandés », « ⚡ indisponible » cliquable. @after VX83.** Trois gestes quotidiens
  enfermés dans la fiche : (a) marquer perdu = ouvrir la fiche → scroller → cocher « Perdu ? » +
  motif — ~5 interactions ; (b) `contact_preference==='phone_ok'` rend un badge passif « ☎ Rappel
  demandé » (`LeadCard.jsx:114-121`) — le signal le plus chaud n'alimente aucune file ; (c) le ⚡
  devis-auto désactivé cache sa raison dans un `title` sans action de correction. Fix : action
  « ✗ Perdu » dans le menu de ligne/carte → mini-popover motif (datalist `motifs-perte` déjà
  chargée) → PATCH `perdu`+`motif_perte` ; chip filtre « Rappels demandés » sur `FilterBar` (pur
  client) + famille `{kind:'rappel', urgency:'high'}` dans `ma-file/` via `crm/selectors.py`
  (@after VX83 — famille que VX83 n'énumère pas) ; le texte `factureManquante`
  (`LeadCard.jsx:209-216`) devient un bouton « → Renseigner la facture » qui ouvre la fiche ET
  focus le champ bloquant. Files : `LeadCard.jsx`, `views/ListView.jsx`, `FilterBar.jsx`,
  `LeadForm.jsx`, `apps/crm/selectors.py`. DoD : perdu + motif en 2 clics depuis une ligne (motif
  alimente le win/loss du CommercialDashboard) ; chip « Rappels demandés » liste les `phone_ok` ;
  cliquer « devis auto indisponible » ouvre la section énergie en édition ; tests. (T2 — M,
  sonnet) (@lane: frontend/crm — @after VX83)

- [x] VX224 — **La session de qualification en rafale : ◀▶ prev/next, « créer un autre », (@lane: frontend/crm — @after VX89/VX92/VX93)
  « Mes leads » par défaut. @after VX89 (même fichier — rebase), VX92, VX93.** Trois
  multiplicateurs de la même session (20-40 leads/j) : (a) `LeadForm` reçoit UN lead — passer au
  suivant = fermer, re-viser la ligne, recliquer ; (b) VX92 câble « Créer un autre » sur
  ProduitForm/ClientForm/paiement mais PAS sur `LeadForm` ; (c) `LeadsPage` charge TOUS les leads
  de l'équipe, le filtre owner n'est jamais pré-réglé. Fix : passer à `LeadForm` la liste filtrée
  courante + index (déjà en mémoire, `filtered`), boutons ◀▶ + touches `J`/`K` façon Gmail (garde
  de saisie si dirty — @coord VXD-B/VX167) ; étendre le toggle VX92 à `LeadForm` (création seule :
  succès → reset + refocus Nom, défauts VX93 réappliqués) ; toggle « Mes leads » défaut ON pour le
  rôle `normal` (persisté `localStorage`, le manager bascule OFF). Files :
  `frontend/src/pages/crm/leads/LeadsPage.jsx`, `LeadForm.jsx`, `FilterBar.jsx`,
  `features/crm/stages.js`. DoD : `J`/`K` charge le lead voisin sans fermer (confirmation si
  dirty) ; toggle ON → créer vide le form et refocus Nom ; un `normal` ouvre `/crm/leads` sur SES
  leads ; tests. (T2 — M, sonnet) (@lane: frontend/crm — @after VX89/VX92/VX93)

**Sous-groupe VXD-L — Le technicien terrain**

- [x] VX225 — **La raison de blocage de statut cesse d'être jetée à la poubelle (@lane: frontend/ios — @coord VX105)
  (InterventionsPage). @coord VX105.** Défaut prouvé : le backend calcule un message FR précis et
  actionnable — `transition_block_reason` (`field_services.py:405-423`, « Photos obligatoires
  manquantes avant "Terminée" : Toiture avant, Câblage. ») — mais `InterventionsPage.jsx:262-272`
  (`DetailSheet.setStatut`) fait `catch { toast.error('Impossible de changer le statut.') }` : le
  corps du 400 (`{statut:[raisons]}`) n'est JAMAIS lu. Le patron de rendu existe DÉJÀ un niveau
  au-dessus : `ChantierGateTimeline.jsx:54-58` affiche les `raisons[]` en `<ul>` inline. Fix : lire
  `err?.response?.data?.statut` et rendre la liste inline sous le Select de statut (patron
  GateTimeline), toast détaillé en repli. Files :
  `frontend/src/pages/installations/InterventionsPage.jsx` (`DetailSheet.setStatut`). DoD :
  forcer un 400 → le message exact du serveur s'affiche sous le sélecteur ; test. VX105 AJOUTE un
  contrôle de statut à MaJourneePage en affichant le 400 — ceci répare le DetailSheet EXISTANT
  d'InterventionsPage, l'autre moitié du même défaut. (T2 — S, sonnet) (@lane: frontend/ios —
  @coord VX105)

- [x] VX226 — (déjà présent) **« Ma journée » dit l'urgence et reste fraîche.** Deux défauts du même (@lane: frontend/ios)
  écran-pivot : (a) `priorite` existe, est ANNOTÉ et TRIÉ serveur (`views/intervention.py:129-144`)
  mais `MaJourneePage.jsx` ne le rend JAMAIS ; (b) `load()` n'est appelé qu'au montage (`:57`) —
  aucun bouton refresh, aucun `visibilitychange`, et le pull-to-refresh natif est coupé
  (`overscroll-behavior: contain`) : une réaffectation dispatch de 10 h est invisible jusqu'au
  rechargement manuel de l'onglet. Fix : puce `Badge tone="danger"/"warning"` quand
  `priorite==='urgente'/'haute'` ; bouton « Actualiser » discret (`RefreshCw`, cohérent
  `OfflineSyncIndicator`) + refetch throttlé sur `visibilitychange` (retour visible après ≥2 min —
  jamais un poll actif). Files : `frontend/src/pages/interventions/MaJourneePage.jsx`, vérif
  `apps/installations/serializers.py`. DoD : une intervention urgente porte une puce distincte du
  rang ; revenir sur l'onglet après 2 min déclenche un refetch silencieux ; tests. (T2 — S,
  sonnet) (@lane: frontend/ios)

- [x] VX227 — **Les coutures chantier↔intervention : pont Demande d'achat, photos reliées,
  séries dédoublonnées. @coord ARC26.** Trois seams du même chantier : (a) `DemandesAchatList.jsx`
  n'a aucun pré-remplissage `chantier` ; (b) deux systèmes de photos avant/pendant/après jamais
  reliés : `PhotosPanel` vs `ChantierPhotos` ; (c) deux captures de n° de série indépendantes : le
  garde-doublon de `ChantierChecklist.jsx:26-30` ne voit pas les séries saisies côté intervention
  et vice-versa. Fix : lien « Autre besoin non prévu → Nouvelle demande d'achat » dans
  `PreparationPanel` naviguant vers `/chantiers/demandes-achat?chantier={id}&intervention={id}` +
  lecture des query params dans `DemandesAchatList` ; liens croisés discrets « Voir aussi les
  photos du chantier / de cette intervention » (jamais de fusion de magasins — @coord ARC26
  politique magasin-unique) ; enrichir le `Set` de déduplication des séries par l'union des deux
  sources. Files : `DemandesAchatList.jsx`, `InterventionFieldExecution.jsx` (`PreparationPanel`,
  `PhotosPanel`), `pages/installations/{ChantierPhotos,ChantierChecklist}.jsx`,
  `InterventionCapturePanels.jsx` (`SerialsPanel`). DoD : depuis une intervention, un tap ouvre la
  DA avec le chantier pré-sélectionné ; chaque écran photo lie vers l'autre ; une série saisie
  côté F9 est détectée en doublon côté N9 et réciproquement ; tests. (T2 — M, sonnet) (@lane:
  frontend/ios — @coord ARC26)

**Sous-groupe VXD-M — Le comptable : le mois compté en clics**

- [x] VX228 — **Le rapprochement bancaire ligne-à-ligne : le contrat d'interaction complet. (@lane: frontend/compta)
  @coord FE-rapprochement-detail (cette seed EST sa spécification d'interaction — une seule
  tâche, jamais deux).** Défaut prouvé : `comptaApi.rapprochements.{lignesGl,resume,
  ajouterLigneReleve,pointer}` (`comptaApi.js:180-186`) n'ont AUCUN consommateur réel —
  `RapprochementsPage.jsx` n'offre que `SuggestionsDialog` (lot) et `cloturer` : une ligne non
  suggérée est IMPOSSIBLE à apparier, et rien ne dit si le mois est bouclé. Fix :
  `RapprochementDetailDialog` à 2 volets côte à côte (relevé | grand-livre), ligne relevé
  cliquable → candidates GL pré-filtrées montant/date (`lignesGl`) → « Pointer » (`pointer`),
  bandeau `resume()` en tête (solde relevé / pointé / écart restant, même langage visuel que
  l'équilibre d'`EcrituresPage.jsx:170-181`) qui décroît EN DIRECT à chaque pointage ;
  « Suggestions » devient une action DE ce dialog. Files :
  `frontend/src/features/compta/pages/RapprochementsPage.jsx` (nouveau
  `RapprochementDetailDialog`), consomme les 4 méthodes API déjà écrites. DoD : ouvrir un
  rapprochement en cours montre l'écart ; pointer une ligne le réduit en direct ; écart 0 →
  clôturable ; test du flux pointer→resume. (T2 — L, sonnet ; opus si scores de confiance à
  rendre) (@lane: frontend/compta)

- [x] VX229 — **`CrudDialog` apprend le Combobox : fin des champs FK « (ID) » tapés à la main.** (@lane: frontend/compta)
  Défaut prouvé : `CrudDialog.jsx:76-96` (la plomberie CRUD des 8 écrans compta) ne rend que
  `<Input>` ou `<select>` statique — résultat : `NotesDeFraisPage.jsx:104/110/123` (« Employé
  (ID) » ×3), `RapprochementsPage.jsx:285` (« Compte de contrepartie (ID) »), et PIRE,
  `EngagementsPage.jsx:75-82/148-155` capture `tiers_nom`/`marche_ref` en TEXTE LIBRE — une
  retenue de garantie part désynchronisée du référentiel tiers dès sa création. Le bon patron
  existe DANS LE MÊME module : `EcrituresPage.jsx:35-40` (`Combobox` + `comptesOpts`). Fix : type
  de champ `{name, label, async: () => Promise<{value,label}[]>}` dans le schéma `CrudDialog`
  (options chargées au montage, memoïsées) ; migrer les 2 champs ID et les champs texte libre
  d'Engagements vers un `tiers_id` réel (`tiers_nom` dérivé lecture seule). Files :
  `features/compta/components/CrudDialog.jsx`, `NotesDeFraisPage.jsx`,
  `RapprochementsPage.jsx`, `EngagementsPage.jsx`. DoD : créer une note de frais montre un
  Combobox « Nom Prénom » ; une retenue de garantie référence un tiers réel traçable vers sa
  fiche ; test de rendu du nouveau type. (T2 — M, sonnet) (@lane: frontend/compta)

- [x] VX230 — **Encaisser LÀ où on chasse l'impayé + total « reste à encaisser » visible. @after
  VX92/VX93 (même dialog — rebase).** Deux moitiés du même job : (a) `RelancesPage.jsx` n'a AUCUNE
  action « Enregistrer un paiement » — le chèque décroché après relance force à quitter, rouvrir
  Factures, re-chercher la même facture ; (b) `FactureList` montre « Encaissé ce mois » mais
  JAMAIS le total dû de la sélection filtrée courante (onglet « Partiellement payées »). Fix :
  extraire la modale paiement de `FactureList.jsx:676-752` en `PaiementDialog` partagé
  (props facture/onSaved) monté depuis les 2 pages + bouton « Encaisser » à côté de « Relancer » ;
  carte « Reste à encaisser (onglet) » calculée sur `filtered` (déjà en mémoire, zéro appel
  réseau). Files : `frontend/src/pages/ventes/PaiementDialog.jsx` (extrait), `FactureList.jsx`,
  `RelancesPage.jsx`. DoD : depuis Relances, « Encaisser » ouvre la même modale et retire la
  ligne des impayés ; l'onglet « Partiellement payées » affiche son total dû ; non-régression du
  flux FactureList. (T2 — M, sonnet) (@lane: frontend/compta — @after VX92/VX93)

- [x] VX231 — **La navigation finance atterrit sur la CIBLE : `?facture=`, lien client, onglet
  persistant, TVA↔Grand-livre. @coord VX79, VX113 (sélecteur d'exercice, même fichier —
  rebase).** Quatre liens cassés du même mois comptable : (a) `PaiementsPage.jsx:127` émet
  `to="/ventes/factures?facture={id}"` mais `FactureList.jsx` n'a AUCUN `useSearchParams` ; (b)
  `client_nom` (`PaiementsPage.jsx:133`) est du texte brut ; (c) AUCUNE des 7 pages compta à
  onglets ne persiste son onglet ; (d) vérifier une déclaration TVA contre le GL = 2 écrans, 2
  chiffres notés à la main. Fix : lire `?facture=` au montage de FactureList (basculer d'onglet
  si besoin, scroll + surbrillance 2-3 s) ; `client_nom` cliquable + filtre `?client=` local sur
  PaiementsPage ; hook partagé `useTabParam(defaultTab)` synchronisant le `Segmented` avec
  `?onglet=` (7 adoptions d'une ligne) ; action « Comparer au Grand-livre » sur une déclaration
  TVA → `EtatsPage` `?etat=grand-livre&date_debut=…&date_fin=…`. Files : `FactureList.jsx`,
  `PaiementsPage.jsx`, `features/compta/components/useTabParam.js` (nouveau) + les 7 pages,
  `FiscalitePage.jsx`, `EtatsPage.jsx`. DoD : cliquer une facture depuis Encaissements atterrit
  sur la ligne surlignée ; recharger restaure l'onglet ; « Comparer au GL » ouvre le grand-livre
  pré-filtré ; tests MemoryRouter. (T2 — M, sonnet) (@lane: frontend/compta — @coord VX79/VX113)

- [x] VX232 — **Les états financiers deviennent LISIBLES : noms réels, tableaux exploitables, (@lane: frontend/compta)
  exports hiérarchisés et traduits.** Quatre défauts de lisibilité du même module : (a) le KPI n°1
  du Cockpit affiche `Tiers #42` (`CockpitPage.jsx:101-104`) ; (b) les états CGNC
  (`EtatsPage.jsx:55-96`, `GenericTable`) sont des `<table>` HTML nus ; (c) les 6 boutons d'export
  fiscaux ont le même poids visuel — routine mensuelle mélangée à l'annuel ; (d) « FEC »/
  « liasse »/« IS » sans un mot d'aide. Fix : résoudre `tiers_id` en nom réel ([BACKEND additif]
  enrichir le selector serveur `top_encours_clients[].tiers_nom`, fallback « Tiers #N » si
  supprimé) ; migrer `GenericTable` vers le `Table` partagé (garder `KeyValue` pour les
  scalaires) ; grouper les exports en 2 rangées sous-titrées « Mensuel » / « Annuel — exercice
  requis » ; sous-libellé gris d'une phrase par export. Files :
  `features/compta/pages/{CockpitPage,EtatsPage,FiscalitePage}.jsx`, `apps/compta/selectors.py`
  [BACKEND]. DoD : le graphique montre des noms de clients ; une balance rendue trie au clic ;
  les 2 groupes d'exports sont distincts et chaque bouton porte sa phrase d'aide ; exports
  serveur inchangés ; tests de rendu. (T2 — M, sonnet) (@lane: frontend/compta)

**Sous-groupe VXD-N — Le directeur/admin : contrôle et supervision**

- [x] VX233 (already present) — **[BACKEND 1 ligne] Le journal des paramètres montre TOUTES ses sections + la (@lane: frontend/brand)
  tarification a son historique.** Défaut prouvé : `SettingsAuditLog` journalise déjà 6+ sections
  côté serveur et l'endpoint `settings_audit_sections` (`views_audit.py:53-68`) EXISTE — mais
  `parametresApi.js` ne l'expose pas et le seul consommateur (`AvanceSection.jsx:304-307`)
  hardcode un `<Select>` à 2 options (`profil`, `messages`). Fix : ajouter `'tarification'` à
  `KNOWN_AUDIT_SECTIONS` ; exposer `parametresApi.getAuditSections()` et construire le `<Select>`
  dynamiquement ; extraire le feed en `SettingsAuditFeed` paramétrable par section, lien « Voir
  l'historique » sur TarificationSection. Files : `apps/parametres/views_audit.py`,
  `frontend/src/api/parametresApi.js`, `pages/parametres/{AvanceSection,TarificationSection,
  SettingsAuditFeed}.jsx`. DoD : le filtre propose ≥6 sections réelles ; changer le barème ONEE
  puis filtrer `tarification` montre qui/quand/ancien→nouveau ; « Voir l'historique » depuis
  Tarification affiche sa section seule ; tests. (T2 — M, sonnet) (@lane: frontend/brand)

- [x] VX234 — **[BACKEND] L'audit des rôles au grain de la PERMISSION + garde de
  réassignation.** Deux trous du même écran de pouvoir : (a) `roles/views.py:64-74` stocke
  `"{nom} ({N} permissions)"` — retirer `crm_supprimer` et ajouter `ventes_export` (net zéro)
  produit un journal illisible ; (b) le dialogue de réassignation avant suppression
  (`RolesManagement.jsx:583-629`) liste TOUS les rôles sans tri ni annotation — réassigner 5
  commerciaux vers « Administrateur » d'un clic hâtif leur donne tous les droits sans
  avertissement. Fix : stocker le diff structuré (`permissions_ajoutees`/`retirees` par
  set-difference dans `old_value`/`new_value` JSON existants) ; rendu frontend en badges +/-
  (le `fmtVal` d'`AvanceSection:48-49` détecte un tableau au lieu de JSON.stringify brut) ; trier
  le `<Select>` de réassignation par nombre de permissions croissant + badge « ⚠ plus large »
  quand la cible dépasse l'original. Files : `apps/roles/views.py`,
  `pages/parametres/AvanceSection.jsx`, `pages/admin/RolesManagement.jsx`. DoD : un échange
  net-neutre de permissions journalise les 2 codes exacts ; le sélecteur annote les rôles plus
  larges ; tests. (T2 — M, sonnet) (@lane: backend/auth)

- [x] VX235 **(already present)** — **[BACKEND] Gardes-fous du pouvoir admin : motif par item en bulk-refus, cycle de (@lane: backend/auth)
  hiérarchie, import-écraser confirmé, dernier admin protégé en masse. Noter AUTH au DONE LOG.**
  Quatre trous d'intégrité prouvés : (a) `ApprobationsPage.deciderEnMasse` (:106-131) applique UN
  `window.prompt` de motif à N demandes HÉTÉROGÈNES (VX19 remplacera le prompt mais pas la
  sémantique « un motif menteur pour tous ») ; (b) `validate_supervisor`
  (`authentication/serializers.py:226-228`) ne bloque que l'auto-supervision — un cycle A→B→C→A
  corrompt silencieusement `records_scope_sous_arbre` ; (c) `ExportSauvegarde.importConfig`
  (:41-56) exécute `config-import/?mode=overwrite` au choix de fichier, gardé par une case à
  cocher HTML native — zéro `AlertDialog`, zéro aperçu des 6 catégories écrasées ; (d)
  `UsersManagement.bulkActions` (:310-321) « Désactiver » ne vérifie jamais `isLastAdmin`. Fix :
  `ResponsiveDialog` de refus listant chaque item avec motif PROPRE (motif commun optionnel
  « appliquer à tous », modifiable par ligne) ; [BACKEND] remonter la chaîne de superviseurs
  (borne 20 sauts) et rejeter le cycle avec message clair + filtrer les descendants du `<select>`
  d'EquipeSection ; `AlertDialog destructive` récapitulant les catégories du bundle AVANT le
  POST ; exclure de la désactivation groupée le(s) compte(s) gardant au moins un admin actif +
  toast des comptes sautés. Files : `pages/approbations/ApprobationsPage.jsx`,
  `authentication/serializers.py`, `pages/parametres/{EquipeSection,ExportSauvegarde}.jsx`,
  `pages/admin/UsersManagement.jsx`. DoD : refus en lot = motif distinct par ligne possible ;
  cycle à 3 nœuds → 400 clair ; import-écraser demande confirmation listée ; désactivation
  groupée laisse ≥1 admin actif ; tests des 4 gardes. (T2 — L, opus : auth/hiérarchie) (@lane:
  backend/auth)

- [x] VX236 — **Fin des culs-de-sac de pilotage : équipes cliquables, Journal deep-linké, seuils (@lane: frontend/brand — @after VX79)
  avec retour. @after VX220 (Journal — la palette ⌘K de VX79 ne liste PAS Journal.jsx dans ses
  Files).** Quatre écrans de supervision qui montrent sans jamais mener : (a)
  `MesEquipesCard.jsx` (monté `Dashboard.jsx:662` — vu par CHAQUE directeur à chaque connexion) :
  zéro lien sur pipeline/retards/CA ; (b) `Journal.jsx` `MODEL_ROUTES` (:50-64) pointe vers des
  LISTES nues ; (c) `KpiAlertesPage.jsx` affiche `derniere_valeur` sans lier vers la source ; (d)
  `MonitoringSection.jsx` (:80-92) règle le seuil de sous-perf à l'aveugle, sans aperçu du nombre
  de systèmes signalés. Fix : `<Link>` sur chaque métrique d'équipe
  (`/crm/leads?equipe=`, `/activites?equipe=`, `/ventes/devis?statut=accepte&equipe=`) ;
  `MODEL_ROUTES` en fonctions `(objectId) => path` (`?lead=` marche dès aujourd'hui,
  devis/chantier/ticket s'activent avec VX79) ; mapper `kpi → route` sur KpiAlertes ; [BACKEND
  additif] `GET /parametres/monitoring/apercu/?seuil=N` affiché au blur du champ. Files :
  `components/MesEquipesCard.jsx`, `pages/Journal.jsx`,
  `pages/parametres/{KpiAlertesPage,MonitoringSection}.jsx`, endpoint léger `apps/parametres` ou
  `apps/sav`. DoD : chaque chiffre d'équipe ouvre la liste filtrée ; cliquer un objet « lead » du
  Journal ouvre CE lead ; la valeur d'une alerte DSO ouvre la balance âgée ; changer le seuil
  affiche « N systèmes seraient signalés » avant sauvegarde ; tests. (T2 — M, sonnet) (@lane:
  frontend/brand — @after VX79)

**Sous-groupe VXD-O — La vélocité de saisie**

- [x] VX237 — **Collage intelligent : le presse-papiers du monde réel entre proprement.** Défaut (@lane: frontend/crm)
  prouvé : 0 `onPaste` dans tout le frontend — un numéro WhatsApp collé, un montant Excel, une
  carte de visite texte tombent bruts dans l'`<input>`. Le « paste-grid Excel » multi-cellules
  reste DIFFÉRÉ (dedup-map) — ceci est le collage UNITAIRE, jamais proposé ni rejeté. Fix : hook
  partagé `usePasteClean(parser)` posé en `onPaste` sur les champs téléphone (parse via
  `canonicalPhoneMA`/`normalizeMaPhone` déjà écrits, `lib/format.js:132,154`), montant (strip
  espaces/virgules/« DH »), et un mode carte-WhatsApp sur le Nom de
  `LeadExpressModal`/`LeadForm` (motif `Nom … Tel …` → bouton « Répartir » après collage,
  confirmation, jamais silencieux). Zéro dépendance, regex pures. Files :
  `frontend/src/hooks/usePasteClean.js` (nouveau), poses sur `LeadForm.jsx`,
  `LeadExpressModal.jsx`, `ClientForm.jsx`, `ClientQuickCreateModal.jsx`, champs montant
  `DevisGenerator.jsx`/`FactureForm.jsx`. DoD : coller `+212 6-12.34.56.78` stocke la forme
  canonique ; coller « 12 500,00 » donne `12500` ; test du parseur sur 8 formats réels. (T2 — M,
  sonnet) (@lane: frontend/crm)

- [x] VX238 — **Primitives « mains rapides » : Segmented au clavier, Tab-qui-choisit, focus (@lane: frontend/ventes — @after VX90/VX91)
  post-sélection. @after VX90/VX91.** Trois défauts de primitives partagées : (a)
  `ui/Segmented.jsx` (57 fichiers consommateurs) déclare `role="radiogroup"` mais n'implémente
  AUCUNE navigation flèches ; (b) `ProduitPicker.jsx:89-101`/`Combobox.jsx:97-110` gèrent
  flèches/Enter/Escape mais pas Tab — Tab blur à vide ; (c) `ProduitPicker.pick()` (:84-87) rend
  le focus au bouton déclencheur — encore un Tab avant de taper la quantité. Fix : roving
  tabindex + `ArrowLeft/Right/Home/End` sur le conteneur radiogroup ; `Tab` (sans shift) =
  `pick(cursor)` sans `preventDefault` ; callback `onPicked` → `.focus()` sur l'input Qté de la
  même ligne (réutilise le `data-line-key` de VX90). Files : `ui/Segmented.jsx`,
  `ui/Combobox.jsx`, `components/ProduitPicker.jsx`, `DevisGenerator.jsx`/`DevisForm.jsx`/
  `FactureForm.jsx`. DoD : Tab arrive UNE fois sur le groupe, flèches changent la sélection ;
  taper une recherche puis Tab sélectionne ET avance ; choisir un produit focus la Qté de LA
  ligne ; tests `document.activeElement`. (T2 — M, sonnet) (@lane: frontend/ventes — @after
  VX90/VX91)

- [x] VX239 — **Doublons : prévenir à la création CLIENT + le geste de FUSION. @coord F-E5.** (@lane: frontend/crm)
  Deux moitiés manquantes du même système : (a) `crmApi.checkDuplicates` n'est câblé que sur
  `LeadForm.jsx:330-346` — `ClientForm`/`ClientQuickCreateModal` n'ont que l'autocomplete NOM ;
  et le formatage téléphone (`canonicalPhoneMA`) n'est consommé que par UN champ ; (b) la
  DÉTECTION backend existe (`apps/crm/tests_doublons.py`, `services.py`) mais aucun composant
  frontend `merge/fusion` trouvé — VÉRIFIER-D'ABORD, puis dialogue de fusion 2 colonnes (garder
  A/garder B par champ, JAMAIS perdre le chatter). Fix : extraire
  `useDuplicateCheck(phone, email, {exclude})` de LeadForm, poser sur ClientForm +
  ClientQuickCreateModal ; extraire `<PhoneHint>` de ClientForm, poser sur
  LeadForm/LeadExpressModal ; geste de fusion en second temps. Files :
  `hooks/useDuplicateCheck.js` + `components/PhoneHint.jsx` (extraits), `ClientForm.jsx`,
  `ClientQuickCreateModal.jsx`, `LeadForm.jsx`, `LeadExpressModal.jsx`, `apps/crm/services.py` +
  `LeadMergeDialog.jsx`/`ClientMergeDialog.jsx` (si confirmé manquant). DoD : créer un client
  avec un téléphone connu avertit AVANT soumission ; taper un numéro dans LeadForm affiche la
  forme normalisée ; fusionner 2 doublons préserve les deux chatters + redirige les documents.
  (T2 — M, sonnet ; opus si fusion cross-app) (@lane: frontend/crm)

- [x] VX240 — **Parité mécanique des formulaires : autofocus, mémoire des défauts, (@lane: frontend/ventes — @after VX90)
  multi-fichiers, focus de ligne achats. @after VX90, @coord VX92/VX93.** Sept incohérences
  prouvées entre formulaires jumeaux : (a) `FactureForm.jsx:293-307`/`DevisForm.jsx:231-245`
  s'ouvrent SANS aucun autofocus ; (b) `ProduitForm.jsx:413-416` Nom sans autofocus ; (c) dialog
  paiement : `pay-montant` sans autofocus + `payReference` sans mémoire ; (d) création ticket
  SAV (`TicketsPage.jsx:1092-1150`) : zéro autofocus + `type` reset à `'correctif'` ; (e)
  `LeadExpressModal.jsx:35` reset `canal='walk_in'` en dur ; (f) `AttachmentsPanel.jsx:85` fait
  `upload(files[0])` sans passer `multiple` à `FileUpload` (qui le supporte) — 5 photos = 5
  cycles complets ; (g) `BonsCommandeFournisseur.jsx:260-268` n'avance jamais le focus à l'ajout
  de ligne. Fix : chaque dialog nommé focus son premier champ utile ; type ticket/canal
  express/payMode mémorisés (localStorage, modifiables) ; itérer séquentiellement les fichiers
  avec « i/N », échec partiel n'annule pas les autres ; répliquer le patch VX90
  (`data-line-key` + `pendingFocusKey`) côté achats. Files : `FactureForm.jsx`, `DevisForm.jsx`,
  `ProduitForm.jsx`, `FactureList.jsx`, `pages/sav/TicketsPage.jsx`, `LeadExpressModal.jsx`,
  `components/AttachmentsPanel.jsx`, `pages/stock/BonsCommandeFournisseur.jsx`. DoD : chaque
  dialog nommé focus son premier champ utile à l'ouverture ; type ticket/canal express/payMode
  mémorisés ; 5 fichiers s'uploadent en une sélection ; « Ajouter ligne » BCF focus la nouvelle
  ligne ; tests de rendu. (T2 — M, haiku ; revue sonnet) (@lane: frontend/ventes — @after VX90)

**Sous-groupe VXD-P — Forgiveness / historique / confiance**

- [x] VX241 **(already present)** — **[BACKEND] Le journal d'audit dit VRAI : cascade KB avouée, destroys (@lane: backend/auth)
  gardés+journalisés, Timesheet tracé, diffs automatiques.** Quatre défauts prouvés du même
  système : (a) `KbArticle.parent` est `on_delete=CASCADE` (`apps/kb/models.py:87-89`) et le
  confirm (`KbPage.jsx:104-105`) ment par omission — supprimer un parent détruit tout le
  sous-arbre sans le dire ; (b) 23 `destroy()` recensés : `KitOutillage`/`Litige` (dossier légal)
  n'ont AUCUN override, et les 7 modèles gardés « en usage »
  (LeadTag/MotifPerte/Canal/ChecklistTemplate/ChecklistEtape/SafetyChecklistSlot/StageModele)
  n'écrivent AUCUNE ligne `AuditLog` — `TRACKED_MODELS` (`audit/signals.py:18-58`, 31 modèles) ne
  liste aucun d'eux, ni `Timesheet` (`gestion_projet/views.py:2136`) ; (c) le paramètre
  `changes=` (diff structuré alimentant `reconstruct_as_of` YHARD3) n'est peuplé qu'à 2
  call-sites dans tout le backend. Fix : confirm KB avec le compte réel de descendants (pattern
  `ForceDeleteModal`) + `('kb','KbArticle')` et `('gestion_projet','Timesheet')` dans
  `TRACKED_MODELS` ; mixin réutilisable `UsageGuardedDestroyMixin` (usage_count + message FR +
  ligne AuditLog via `recorder.record()` en UN endroit) appliqué aux 7 gardés + gardes neufs
  Kit/Litige ; snapshot complet du row dans `_on_pre_save` → diff automatique `changes=` pour
  chaque UPDATE tracé. Files : `frontend/src/features/kb/KbPage.jsx`, `apps/kb/views.py`
  (annotation compte), `apps/audit/signals.py`, `apps/core/destroy_mixins.py` (nouveau),
  `apps/{crm,installations,outillage,litiges}/views*.py`. DoD : supprimer un parent KB affiche le
  vrai compte + écrit une ligne DELETE visible au Journal ; supprimer un Kit utilisé → 409 FR ;
  supprimer un Timesheet trace ; éditer `total_ttc` d'un devis écrit `changes=[{field,old,new}]`
  sans toucher une seule vue ; tests YHARD3 verts. (T2/T3 — L, sonnet ; opus si l'import-linter
  core bronche sur le mixin) (@lane: backend/auth)

- [x] VX242 — **[BACKEND+AUTH — noter au DONE LOG] Sécurité de session digne de confiance : le
  changement de mot de passe révoque, le secret 2FA ne fuit plus.** Deux trous dans une feature
  par ailleurs finie (N96, hors périmètre VX/NT) : (a) `ChangePasswordView.post()`
  (`authentication/views.py:855-904`) ne touche jamais `UserSession`/blacklist — après
  compromission, l'attaquant garde son refresh 7 j alors que TOUTE la machinerie de révocation
  existe (`SessionRevokeView`, `_blacklist_refresh_jti`, :823-851), juste jamais invoquée depuis
  ce chemin ; (b) `SecuriteCompteSection.jsx:363` rend le QR d'enrôlement 2FA via
  `api.qrserver.com` — le SECRET TOTP brut part en clair. *(Note : (b) est la MÊME faille que
  VX120 en tête de document — ne pas la reconstruire deux fois, ce seed la référence pour le
  contexte de la révocation de session (a) qui l'accompagnait dans le rapport source.)* Fix :
  révoquer toutes les sessions SAUF la courante après `user.save()` (boucle sur la logique
  SessionRevoke existante), réponse `sessions_revoked: N` + message « … {N} autre(s) session(s)
  déconnectée(s) » ; pour (b) voir VX120. Files : `authentication/views.py`
  (`ChangePasswordView`). DoD : changer le mot de passe avec 2 autres sessions actives blackliste
  leurs refresh (test à 2 logins). (T1 — S/M, sonnet — noter AUTH au DONE LOG) (@lane:
  backend/auth)

- [x] VX243 — **[BACKEND] La confiance au niveau du DOSSIER : « archivé par X », historique de (@lane: backend/auth — @after VX98)
  MON enregistrement, garde d'édition périmée. @after VX98 (réutilise `updated_by`/`updated_at` —
  ne jamais dupliquer le champ).** Trois lectures de confiance au grain du record : (a)
  `Lead.archived_by`/`archived_at` sont capturés serveur (`crm/models.py:602-608`) et JAMAIS
  rendus (0 hit frontend) ; (b) le Journal est gaté `can_view_activity_log` tout-ou-rien
  (`audit/views.py:32-41`) : un commercial ne peut pas voir qui a modifié SON propre lead sans
  recevoir la visibilité sur TOUTE la boîte — ajouter un chemin de lecture record-scopé ; (c)
  aucune détection d'édition périmée au moment du SAVE (le verrou 409 backend reste territoire
  YDATA ; VX98(b) = puce passive à la LECTURE) — hook `useStaleGuard` : au submit, re-GET léger de
  `updated_at`, si différent de la valeur d'ouverture → bannière non bloquante « Modifié par {X}
  pendant votre édition — vérifiez avant d'enregistrer » avec choix revoir/forcer. Files :
  `pages/crm/leads/views/ListView.jsx` + `apps/crm/serializers.py` (exposer archived_by/at si
  absents — additif), `apps/audit/views.py` (action de lecture scopée objet),
  `hooks/useStaleGuard.js` (nouveau) câblé sur Lead/Devis/Facture. DoD : une ligne archivée
  montre « Archivé par X le … » ; un commercial sans permission Journal voit l'historique de SON
  lead et rien d'autre (test des 2 bornes) ; éditer dans 2 onglets → le 2ᵉ save affiche la
  bannière AVANT le PATCH ; tests. (T2 — M, sonnet ; revue attentive de la borne de permission)
  (@lane: backend/auth — @after VX98)

- [x] VX244 — **Le poids de la confirmation devient proportionné au dégât : primitive (@lane: frontend/data — @coord VX19/VX95/VX96)
  `ConfirmDialog` à sévérité. @coord VX19, VX95/96.** Défaut prouvé : 68 `window.confirm` dans 44
  fichiers, UNE seule gravité — supprimer un litige client (dossier légal), un article KB avec
  sous-arbre, un secret webhook et un preset UI passent par le même dialog natif ; le repo SAIT
  faire mieux (le `ForceDeleteModal` typé de `StockList.jsx:507-560`, le « maison, jamais
  window.confirm » d'`UsersManagement.jsx:189`) sans jamais l'avoir généralisé. Fix : primitive
  `ui/ConfirmDialog.jsx` (vérifier-d'abord qu'elle n'existe pas sous un autre nom) avec prop
  `severity` (`low/medium/high`) pilotant couleur + confirmation tapée ; sémantique clavier
  délibérée (Escape annule TOUJOURS ; Entrée ne confirme JAMAIS un destructif `high`) ; migrer les
  ~10 sites au plus fort blast-radius (litiges, webhook-secret, templates checklist/safety,
  KB-avec-enfants de VX241, bulk ≥5 leads via `<BulkDestructiveConfirm count>` extrait de
  ForceDeleteModal) — jamais les 68 d'un coup. Files : `ui/ConfirmDialog.jsx` +
  `ui/BulkDestructiveConfirm.jsx` (extraits), les ~10 sites cités. DoD : les 10 sites à fort enjeu
  utilisent le dialog pondéré (confirmation tapée pour litiges/webhook/KB-enfants) ; bulk ≥5
  leads montre le compte tapé ; Entrée ne déclenche pas un `high` ; tests. (T2 — M, sonnet)
  (@lane: frontend/data — @coord VX19/VX95/VX96)

**Sous-groupe VXD-Q — Interop & onboarding→maîtrise**

- [x] VX245 **(already present)** — **[BACKEND] Le cycle client sortant se boucle : `.ics` d'événement unique, (@lane: backend/notify — @coord VX116/VX46)
  confirmation WhatsApp de RDV, relance de facture riche. @coord VX116, VX46 (re-surface
  l'ABONNEMENT — distinct).** Trois maillons du même canal : (a) `AppointmentBooker.jsx` crée un
  RDV sans JAMAIS produire de `.ics` — le seul générateur (`reporting/calendar.py:366-392`,
  `build_ics`) ne fait que le flux d'ABONNEMENT complet ; (b) une fois le `.ics` livré, rien ne
  relie le RDV au message WhatsApp de confirmation ; (c) le flux WhatsApp RICHE
  (`LeadForm.jsx:179-207`) est un MONOPOLE du devis→lead — VX108 rend les numéros cliquables NUS
  sans message pré-rempli. Fix : extraire `build_ics` en fonction pure, endpoint `GET
  /crm/appointments/<id>/ics/` (1 VEVENT RFC 5545, scopé company) + bouton « Ajouter à mon
  agenda (.ics) » ; bouton « Confirmer par WhatsApp » post-RDV (aperçu date/heure + lien .ics,
  jamais automatique) ; extraire la construction message+wa_url en service paramétré par contexte
  (`crm/services.py` ; la variante facture vit côté `ventes/services.py`) et l'appliquer à la
  relance de facture depuis `FactureList`/`ClientDetailPanel`. Files :
  `apps/reporting/calendar.py`, `apps/crm/{views,services}.py`, `apps/ventes/services.py`,
  `crmApi.js`, `AppointmentBooker.jsx`, `FactureList.jsx`/`ClientDetailPanel.jsx`. DoD : « Ajouter
  à mon agenda » télécharge un .ics valide qui s'ouvre dans Google Agenda (RDV d'une autre
  société → 404) ; confirmer un RDV propose le message WhatsApp avec lien ; « Relancer par
  WhatsApp » sur une facture en retard affiche l'aperçu du message ; tests. (T3 — M, sonnet)
  (@lane: backend/notify — @coord VX116/VX46)

- [x] VX246 — **Queue de couverture interop : compression POD/chatter, Imprimer RH/contrats,
  Copier TSV partout, vCard, tel: terrain. @after VX77/VX80/VX110/VX108.** Cinq extensions
  mécaniques de patrons que VX pose sur des listes nommées en laissant des orphelins prouvés :
  (a) compression photo VX77 = 3 écrans terrain — `PodCaptureDialog.jsx:120` et
  `AttachmentsPanel.jsx:79` envoient brut ; (b) VX80 pose `print.css` + bouton sur 3 écrans —
  ajouter le MÊME bouton sur `EmployeDetail.jsx` et `ContratDetail.jsx` (PAS le PDF WeasyPrint
  contrat existant, hors règle #4 mais un seul mécanisme) ; (c) VX110 pilote « Copier » TSV sur
  ClientList — restent orphelins : `installations/views/ListView.jsx`, `sav/TicketsPage.jsx`,
  `stock/BonsCommandeFournisseur.jsx` ; (d) aucun `.vcf` nulle part — util pur `lib/vcard.js`
  (vCard 3.0, zéro dép) + bouton discret à côté des liens VX108 ; (e) `TrajetPanel`
  (`InterventionFieldExecution.jsx:247-251`) affiche le téléphone du contact site en texte brut →
  lien `tel:`. Files : `features/logistique/PodCaptureDialog.jsx`,
  `components/AttachmentsPanel.jsx`, `features/rh/EmployeDetail.jsx`,
  `features/contrats/ContratDetail.jsx`, les 3 listes TSV, `lib/vcard.js` (nouveau),
  `InterventionFieldExecution.jsx`. DoD : une photo POD de 6 Mo compresse avant upload, un PDF
  passe intact ; `emulateMedia print` propre sur RH/contrat ; « Copier » TSV sur les 3 listes ; un
  `.vcf` téléchargé s'importe ; le numéro du contact site est tapable ; tests. (T3 — M,
  haiku/sonnet) (@lane: frontend/ios — @after VX77/VX80/VX110/VX108)

- [x] VX247 — **[GATED-founder pour le volet (e)] Onboarding→maîtrise : le guide connaît le (@lane: frontend/brand — @coord NTMOB33/VX47)
  rôle, annonce le clavier, se voit dans le shell, a une mémoire — et l'ERP peut se peupler
  d'exemple. @coord NTMOB33/VX47.** Le rapport prouve qu'un système d'onboarding ENTIER (FG16 :
  279 lignes de coachmarks + checklist réelle) est absent à 100 % de la carte VX1-116. Cinq
  trous : (a) `OnboardingCoachmarks.jsx:20-52` montre la MÊME séquence à tous → filtrer `STEPS`
  par prédicat de rôle + 1-2 étapes par rôle non-admin (desktop ; NTMOB33 possède le MOBILE) ; (b)
  le tour ne mentionne JAMAIS `⌘K` ni `?` → +1 étape finale sourcée de `GLOBAL_SHORTCUTS` ; (c) la
  progression (`OnboardingSection.jsx:71`) n'existe QUE dans Paramètres → badge `2/3` sur l'item
  Sidebar Paramètres tant que <100 % ; (d) aucun glossaire métier → page statique
  `/aide/lexique` (15-25 termes), les HelpTip VX47 y POINTENT au lieu de dupliquer (@after VX47) ;
  (e) [GATED-founder][BACKEND] `seed_demo.py` (326 lignes, jeu complet, CLI/DEBUG-only) n'est
  exposé nulle part — endpoint protégé (flag explicite, société fraîche ET vide uniquement) +
  bouton conditionnel dans OnboardingSection — PROPOSER, ne jamais activer sans accord fondateur.
  Files : `features/onboarding/{OnboardingCoachmarks.jsx,onboardingHelpers.js}`,
  `hooks/useOnboardingProgress.js` (nouveau), `components/layout/Sidebar.jsx`,
  `pages/aide/LexiquePage.jsx` (nouveau + route),
  `authentication/management/commands/seed_demo.py` (extraction service), endpoint léger,
  `pages/parametres/OnboardingSection.jsx`. DoD : un compte Technicien ne voit jamais « Invitez
  votre équipe » ; le tour finit sur `⌘K`/`?` ; badge Sidebar disparaît à 100 % ; lexique ≥15
  termes ; une société neuve se peuple/se vide d'exemple derrière le flag (2 sens testés, garde
  prod) ; non-régression du parcours Admin. (T3 — L, sonnet) (@lane: frontend/brand — @coord
  NTMOB33/VX47)

**Sous-groupe VXD-R — L'âme au quotidien**

- [x] VX248 — **Raccourcis d'ACTION à une touche sur le record focalisé + cheatsheet filtrée par (@lane: frontend/crm — @coord NTUX9/18)
  rôle. @coord NTUX9/18 (palette = chercher-puis-exécuter ; cheatsheet-recherche = trouver un
  raccourci CONNU — mécanismes disjoints, vérifier avant build).** La vélocité perçue vient des
  raccourcis d'ACTION sur l'objet affiché, pas de la navigation — `shortcuts.js` ne connaît que
  `GOTO_SHORTCUTS` (nav), et la cheatsheet `?` est une liste statique identique pour tous les
  rôles. Fix : registre `focusedRecordShortcuts.js` par écran de détail (LeadForm, détail
  DevisList/FactureList, Ticket) — une touche = une action fréquente (`a` archiver, `d` déléguer,
  `1..4` changer de stage via les CLÉS DE STAGES.py, règle #2 — jamais de littéraux) derrière la
  garde `isTypingTarget` existante (`shortcuts.js:29-38`) ; apprentissage passif : le raccourci
  s'affiche en tooltip sur le bouton équivalent (@coord VX129 — même slot `kbd`) ; la cheatsheet
  gagne un champ `roles: []` optionnel et groupe « Pour votre rôle » d'abord, « Autres » en repli
  (filtre d'AFFICHAGE seulement, jamais de désactivation fonctionnelle). Files :
  `providers/{shortcuts.js,ShortcutsProvider.jsx}`, `focusedRecordShortcuts.js` (nouveau), points
  de montage LeadForm/DevisList/FactureList, composant cheatsheet. DoD : sur LeadForm ouvert, `a`
  (hors champ) archive sans clic, une frappe DANS un `<Input>` ne déclenche jamais ; un
  Technicien ouvrant `?` voit ses raccourcis en tête ; la cheatsheet liste les nouveaux par écran
  actif ; tests `isTypingTarget` + rendu par rôle. (T3 — M, sonnet) (@lane: frontend/crm — @coord
  NTUX9/18)

- [x] VX249 — **Le langage des micro-états : pulse de champ sauvé, valeur « suggérée », pastille (@lane: frontend/crm — @after/with VX93)
  « pour moi » vs « société ». @after/with VX93, @coord VX83/84/86 + VX208.** Trois micro-signaux
  systémiques qu'aucune tâche par-écran ne peut poser : (a) aucun micro-accusé au grain du champ
  pour les sauvegardes silencieuses (édition inline DataTable, statut, note chatter) → primitive
  `ui/FieldSavedPulse.jsx` (pulse vert 300-400 ms sur LA cellule, `prefers-reduced-motion` →
  changement statique), intégrée d'abord à l'édition inline DataTable ; (b) VX93 pré-remplit
  (owner/ville/TVA/payMode) sans dire que c'est une SUPPOSITION → style discret « suggéré »
  (contour pointillé + micro-libellé au focus, retiré dès modification) sur les 4 champs VX93
  exactement, jamais un système de confidence générique ; (c) VX83/84/86 posent 3 surfaces de
  signal sans convention visuelle commune « assigné à moi » vs « information société » → UN
  token (pastille pleine = pour moi/action, contour = info passive) consommé à l'identique par
  cloche, Ma file et Dashboard. Files : `ui/FieldSavedPulse.jsx` (nouveau),
  `ui/datatable/DataTable.jsx`, les 4 fichiers VX93, `design/tokens.css`, `NotificationBell.jsx`,
  `MesActivitesPage.jsx`, `Dashboard.jsx`. DoD : valider une cellule inline pulse LA cellule (pas
  un toast) ; les champs pré-remplis affichent « suggéré » jusqu'au premier toucher ; un item
  société n'emprunte jamais le style « pour moi » (test des 3 surfaces) ; reduced-motion dégrade.
  (T3 — M, sonnet) (@lane: frontend/crm — @after/with VX93)

- [x] VX250 — **La fiche annonce son état et ses relations : « en attente de… » + compteurs (@lane: frontend/crm — @coord VX159/ARC46)
  cliquables. @coord ARC46 (`RecordShell` — construire indépendant, migrer dedans plus tard).**
  Deux lectures ambiantes au niveau du record : (a) rien ne montre, DANS le document ouvert, ce
  qui reste à faire ailleurs → `<PendingStepsIndicator>` sur le détail Devis/Facture, dérivé des
  statuts déjà chargés (devis `envoye` non signé → « En attente de signature client » ; facture à
  acompte partiel → « Solde restant : X MAD ») — lecture PURE, ne change jamais un statut (chaîne
  Devis/BonCommande/Facture préservée 1:1, règle #4) ; (b) chaque fiche 360 affiche ses relations
  à sa façon → `<RelationCounters>` réutilisable (« 3 devis · 1 facture impayée · 2 tickets SAV »)
  en tête de Lead/Client/Fournisseur/Produit *(note : composant déjà introduit en VX159 côté axe1
  — cette entrée en spécifie l'usage sur DevisForm/FactureList également, coordonner un seul
  `ui/RelationCounters.jsx`, ne jamais en construire un second)*, chaque compteur lu via le
  selector du domaine CIBLE, clic → liste pré-filtrée `?client=`/`?id=`. Files :
  `pages/ventes/{DevisForm,FactureList}.jsx` (détail), `ui/RelationCounters.jsx` (voir VX159),
  montage `ClientDetailPanel.jsx`, `FournisseurFiche360.jsx`, `ProduitDetail.jsx`,
  `LeadForm.jsx`. DoD : un devis envoyé non signé affiche son bandeau qui disparaît à la
  signature ; une facture d'acompte affiche le solde ; les 4 fiches montrent les mêmes compteurs
  cliquables vers des listes pré-filtrées ; `prix_achat` jamais rendu ; zéro appel réseau nouveau
  pour (a) ; tests. (T3 — M, sonnet) (@lane: frontend/crm — @coord VX159/ARC46)

- [x] VX251 — **Le dispatch au glisser-déposer : réaffecter une intervention comme
  ServiceTitan. @after VX95, @coord NTFSM3 (optimiseur 2-opt = l'ORDRE d'une tournée, pas le
  geste de réaffectation — disjoint ; vérifier avant build).** Le geste cœur d'un dispatch board
  (glisser un job d'un technicien à l'autre) n'existe pas — `PlanificationPage.jsx` (calendrier
  dispatch) n'a aucun `onDrop`/`draggable`, alors que `KanbanView.jsx:186-200` (CRM) prouve déjà
  le pattern drag+recul-guard dans le repo. Fix : répliquer le pattern Kanban sur l'onglet
  dispatch — glisser une carte intervention d'une colonne-technicien à une autre déclenche
  l'update `technicien`/`date` EXISTANT + `toastWithUndo` 6 s (VX95, jamais un 2ᵉ primitif undo) ;
  le Gantt FG74 reste lecture seule ; la notif au nouveau technicien arrive par
  `_notifier_reassignation` déjà câblé (XFSM3) — zéro backend. Files :
  `pages/installations/PlanificationPage.jsx`, réutilise `lib/toast.js:60-89`. DoD : le drag
  réaffecte réellement (persistance vérifiée), « Annuler » restaure l'affectation ; la
  notification part au réassigné ; test du drop + undo. (T3 — M, sonnet) (@lane: frontend/ios —
  @after VX95)

- [BLOCKED: attend VX156 — celebrate.js non construit] VX252 — **[BACKEND additif léger] Maîtrise personnelle : milestones non comparatifs, KPI
  d'adoption clavier, garde anti-backfire de la gamification. @after VX156 (célébration devis
  signé), @coord NTCRM23/24/28, NTUX40.** Recherche 2026 (Trophy.so, Carnegie Mellon) : ~10 % des
  employés sont motivés par la compétition ; les 90 % restants sont ACTIVEMENT démotivés par un
  classement. Trois pièces : (a) étendre `celebrate.js` (VX156, CSS-only) d'un déclencheur
  « milestone personnel » à seuils déterministes et espacés (50ᵉ intervention signée, 25ᵉ devis
  signé) — célébré UNE fois, jamais visible d'un collègue/manager, reduced-motion → toast simple ;
  (b) KPI interne d'adoption clavier (« % actifs ayant utilisé ⌘K 1×/semaine », signal `POST
  /ux/usage-signal/` best-effort jamais bloquant) — gate Directeur/Admin, JAMAIS montré au
  commercial (@coord NTUX40 — métriques disjointes, vérifier) ; (c) garde anti-backfire à
  INSCRIRE sur NTCRM23/24 avant leur build : `metrique_qualite_associee` affichée à côté du score
  brut + participation réellement opt-in invisible — jamais un score de vitesse seul. Files :
  `ui/celebrate.js`, points d'appel `MaJourneePage.jsx`/`SigneDialog`, `apps/reporting/models.py`
  + endpoint léger, `providers/CommandPalette.jsx` (compteur), note sur NTCRM23/24. DoD : la 50ᵉ
  intervention signée célèbre une fois (pas au 51ᵉ, pas au reload) ; le KPI calcule un % réel et
  échoue gracieusement à 0 ; la note NTCRM est posée dans le plan ; tests. (T3 — M, sonnet)
  (@lane: backend/notify — @after VX156)

---

## NE PAS FAIRE (Groupe VXD) — fusion dédupliquée des trois axes

**Déjà possédé par VX1-116 (couches design/coquille/cockpits) :**
- Re-signature coquille/marque, accents module, lanceur, cockpits → VX1-8, VX9-12/ODX5-7,
  VX15/27/29-34. Couleurs de stage StatusPill → VX26 (règle #2).
- Palette catégorielle data-viz + annotations → VX41 (danger zone) ; la rampe « solaire »
  d'un rapport source est versée comme INPUT à VX41, jamais re-proposée.
- Illustrations SVG d'états vides + confetti générique → VX40 (« délice mesuré ») ; VX156 (axe1
  S40b, ex-« signé célébré ») ne câble QUE le moment signé, jamais le système d'illustration.
- Photo produit catalogue, theming par tenant, refonte Landing, grille d'apps pleine page à la
  Odoo → rejets fondateur explicites (rounds 1-3, PLAN2 NE PAS FAIRE).
- Grain `feTurbulence` sur la sidebar, `@starting-style` (pattern de référence, pas un défaut),
  `content-visibility` sur les listes non virtualisées (territoire perf, pas beauté) → rejetés/
  hors-axe, non repris.
- Badge persistant d'échec PDF sur la ligne, identifiant support dans ErrorBoundary → possédés
  par VX172 / VX206 respectivement.

**Déjà possédé par VX48-72 (appareils/Safari/perf nommés) :**
- PDF iOS (onglet pré-ouvert), popup-block detection, `data-label` tables, clavier iOS
  VisualViewport, `title=` tactile, balayage compat → VX48/49/50/51/52/53.
- Troncature 100 lignes + pagination parallèle, timeout axios + annulation, poll onglet caché,
  cold-path, préchargement, chunk-name, e2e comptes-justes, Web Vitals → VX54-VX61.
- Brouillon auto DevisGenerator + garde de sortie → VX62 ; JSON brut DevisList → VX63 ; error
  boundaries routes nues → VX64 ; `?next=` login → VX65 ; anti-double-submit Button → VX66.
- Safari/iPad/zoom/visual-regression/axe/Sentry e2e → VX68/69/70/71/72.
- `.agent-sql` momentum-scroll → CSS mort (0 consommateur), retiré de VX175 ; sa suppression
  appartient à VX121.
- Rejets round 2 toujours en vigueur : verrou optimiste 409 (→YDATA), Lighthouse-CI sur le SPA
  authentifié, BundleMon 2ᵉ gate, Firefox en matrice, service-worker cache des RÉPONSES API, 2ᵉ
  outbox offline, virtualisation sans mesure. VX187/VX188 sont les seules exceptions MESURÉES
  (DoD Profiler à l'appui) ; VX179 cache des ASSETS/médias en lecture, jamais des réponses API.
  `animation-timeline: scroll()` non confirmé dans le code → ne pas construire spéculativement ;
  attribution LoAF dans le beacon → amendement du build de VX61 (même fichier `vitals.js`), pas
  une tâche séparée ; note HMR du singleton `fieldOutbox` → un commentaire de code, pas une
  tâche ; moteur de conflit offline / CRDT → le signal de conflit EST le message serveur par op de
  VX119.
- Gate visuel bloquant par PR → contredit la décision LIVRÉE de VX70, jamais un amendement sans
  raison.

**Déjà possédé par VX73-116 (locale, files, saisie, argent, amour-employé) :**
- Sélecteur de langue menteur + `Ctrl K` → VX73 ; arabe RTL décision → VX74 ; format
  argent/date + garde CI → VX75 (VX143 en est l'annexe d'exécution, pas un doublon) ; compression
  photo → VX77 ; 404 branché → VX78.
- « Ma file » unique + cloche AUTRES + plomberie records + signaux approbation → VX83-86,
  VX99-101 ; jamais un 2ᵉ agrégateur ni une 2ᵉ boîte de réception parallèle (VX214 l'atteste par
  reshape) ; jamais de hook de polling séparé pour la cloche (VX56 possède
  `useVisibilityAwarePolling`, cloche incluse).
- Journal d'appel un-geste + tournée géo + délégation absence + technicien + signature client +
  résumé client → VX87/88/103/105/106/107.
- LeadForm Escape/autofocus, « Ajouter ligne » focus, convergence FactureForm, « enregistrer et
  créer un autre », défauts intelligents, Enter-pour-ajouter → VX89-94.
- `toastWithUndo` câblé (archive/kanban), soft-delete Lead, « qui a fait quoi », lien Historique,
  `tel:`/`wa.me`, import fournisseurs, « Copier » TSV, pièce jointe note chatter → VX95-98,
  VX108-111.
- Drill-down relances, exercice fiscal, sélecteur dates export, KPI compta, relance en lot →
  VX112-116.
- « Mes préférences » (thème/densité/module d'atterrissage/mouvement) → VX46 ; HelpTip
  contextuel → VX47 ; emails de marque wrapper → VX76 ; export XLSX horodaté → VX81 ; liens
  partageables `?id=` → VX79 ; impression → VX80 ; chrome onglet + non-lus → VX82.
- Rejets round 3 : 2FA remember-device (→NTSEC14), Corbeille générique (→NTUX7), formulaire
  DemandeAchat catalogue (→NTP2P3), refonte chatter (→VX23/ARC8-9), moteur d'approbation unifié
  (→ARC10/NTWFL1), « Ma journée commerciale » silo (→VX83 absorbe), inbox mentions dédiée
  (→NTCOL17), optimiseur 2-opt (→NTFSM3), undo bulk-edit (→NTUX6), paste-grid Excel multi-cellules
  (différé — VX237 est le collage UNITAIRE), KPI perso PUBLIC/classement (différé — VX219 est
  privé, VX252 non-comparatif), correction de ligne de paiement (DECISION), iCal abonnement
  (VX46), Client-360/OCR relevé (persona-finance).

**Frontières NT/ARC intouchables (les trois axes) :**
- Vues serveur partagées / FilterBuilder ET/OU / bulk-edit preview-undo / corbeille transverse
  (`apps/trash`) / quick-create palette générique / favoris / peek-hover de LIGNE / densité par
  vue → NTUX (frontière explicite « pas de changement visuel/shell (Groupe VX) »,
  `new_tasks_plan.md:2436`).
- Boîte email par user / RDV Calendly / boîte partagée / inbox mentions `/mentions` / digest
  personnel → NTCOL.
- Offline multi-module / accueils mobiles par rôle / géofence / scan QR / onboarding mobile
  « Ma journée » → NTMOB, NTMOB33.
- i18n/RTL/langue par user/polices arabes → NTI18N (attention : NTI18N5/17/30 touchent le moteur
  `/proposal` — règle #4, ne jamais y toucher côté client).
- Leaderboard/défis d'équipe → NTCRM23/24 (seul le garde-fou de VX252 s'y greffe, jamais le
  système lui-même).
- Moteur d'approbation unifié → ARC10/NTWFL1 ; migration DataTable DevisList/FactureList →
  ARC49/53 (VX180/VX178/VX184 se corrigent AVANT que la migration n'hérite du défaut) ;
  `useResource` → ARC44/45 ; RecordShell → ARC46 (VX159/VX250 construits indépendants, migrables
  dedans ensuite) ; politique magasin-unique → ARC26.
- Verrou optimiste backend 409 → YDATA ; file photo binaire offline → FG386 (« jamais un 2ᵉ
  outbox », VX119 ne construit PAS de moteur CRDT).

**Mécanique transversale (toujours vraie, tous les VXD) :**
- Frontend-first ; aucune dépendance npm nouvelle sauf tâche taguée [GATED] (VX120 QR 2FA,
  VX198 jsx-a11y, VX247(e) seed_demo — tous soumis au fondateur avant tout build).
- Jamais toucher `apps/ventes/quote_engine/`, `/proposal`, PdfCanvas, `apps/web` (règle #4) — le
  moteur RESTITUE, ne change jamais un statut (VX250(a) est une LECTURE) ; les PDF
  d'intervention/contrat (WeasyPrint) sont hors règle #4 mais on n'y crée jamais un 2ᵉ mécanisme
  concurrent (VX246(b)).
- Toute clé de stage vient de `STAGES.py`/`features/crm/stages.js` (règle #2) — jamais un
  littéral (VX224, VX248 raccourcis `1..4`, VX211 `queueViews`).
- `prix_achat`/marge jamais client-facing ni dans un peek/notification/WhatsApp/milestone
  (VX213 montants DA, VX217 AttentionPeek, VX156 messages — tous montants client-safe).
- Jamais d'envoi WhatsApp/email automatique — aperçu-puis-clic partout (règle manuel-wa.me
  fondateur, VX222/VX245/VX252) ; jamais de mutation via lien email non authentifié (VX212).
  `api.qrserver.com` et tout rendu tiers de secrets sont interdits (VX120).
- Ne pas dé-gater `/reporting/commercial` (VX219 ajoute une carte personnelle, le reporting
  manager reste manager) ; ne pas élargir le Journal global (VX243 = lecture record-scopée,
  jamais un grant company-wide) ; ne JAMAIS déverrouiller un accès nav/rôle sans décision
  fondateur.
- Hooks e2e `ap-*/att-*/pp-*` préservés partout ; UN seul Toaster ; scoping tenant TOUJOURS
  serveur (`request.user.company`, `perform_create` force `company`) ; jamais `count()+1` pour
  une référence ; migrations additives/révertables ; noter AUTH au DONE LOG pour
  VX235/VX242/VX243 ; FR partout.

### Group QF — Quote fidelity: real-bill tranche savings, battery-scenario honesty, Huawei-only accessories (founder request 2026-07-01)

*From Reda: the devis currently shows savings numbers unrelated to the client's real bill; selecting « sans batterie » (and likely « avec batterie ») does not produce the right option; and the Smart Meter + Clé Wifi accessories are being attached to every inverter when they only belong on a Huawei. Three clusters below. Research pinned the exact code: residential on-screen savings (`solar.js computeROI`) use a FIXED 1.75 MAD/kWh and ignore the entered bills (bills are chart-only); the backend `pricing.py` already has ONEE/Lydec/Redal tranche tables from QJ13 but they only fire when `distributeur`+consumption are passed; `builder.py` (~L414-422) auto-derives the avec/sans scenario from line items and IGNORES the seller's stored `etude_params['scenario']`; and `solar.js autoFillLines` (~L445-465) attaches Smart Meter + Wifi to ANY réseau inverter, not Huawei-only (the correct guard exists in the old simulator and was never ported).*

> **Constraints (every QF task).** Rule #4 — the quote engine only RENDERS; the document status chain
> (`brouillon→envoye→accepte…`) + BonCommande/Facture are preserved 1:1 and `/proposal` stays the only
> client-facing quote-PDF path. **Self-consumption-first (QJ13 / loi 82-21): value only self-consumed
> kWh; the surplus-injection line stays OFF** until the founder confirms ANRE's BT tariff. **No invented
> numbers** — when the client's bill / utility is absent, degrade to a clearly-labelled estimate, never a
> fabricated one. Build ON QJ13's `pricing.py` tranche tables (extend, don't duplicate). New keys go into
> the existing `Devis.etude_params` JSONField (additive, no migration). **Front and back must agree on the
> math (one shared source of truth) so the on-screen number equals the PDF.** New user-facing text in French.

**A — Real-bill, two-bills, par-tranche savings + the method shown in the quote:**

**B — Battery-scenario honesty (avec / sans batterie):**

**C — Huawei-only Smart Meter + Clé Wifi:**

### Group QG — Quote generator UX, workflow & 3D viewer (founder request 2026-07-01)

*From Reda, on the devis experience: (1) clicking the PDF button never opens the PDF — after a wait only a green button appears (you must click AGAIN to download); (2) editing a quote via « Éditer » doesn't show up in the regenerated PDF; (3) creating a quote should be simpler — add a new client AND a new product directly from the quote screen; (4) but creating products anywhere must be restricted to Directeur + Commercial responsable; (5) the quote must carry the CREATOR's name + phone, not always the founder's; (6) « Envoyer » on a devis must behave exactly like « Envoyer via WhatsApp » in the leads; (7) the « Variante » button must actually show the quote with 3 variantes and let Reda + Meryem set the percentage (20 % default, changeable); (8) show the 3D roof viewer inside quotes AND as a separate window openable on its own. Research pinned every cause — see each task.*

> **Constraints (every QG task).** Rule #4 — the quote engine only RENDERS; the document status chain
> (`brouillon→envoye→accepte…`) + BonCommande/Facture preserved 1:1; `/proposal` stays the only
> client-facing quote-PDF path; NEVER touch the devis/facture PDF *templates*/public PDF pages beyond the
> data fed in. Multi-tenant: all reads/writes company-scoped server-side; `company` never from the body.
> Cross-app reads/writes via `selectors.py`/`services.py` + the `core/events.py` bus — never another app's
> models/views. Keep the generator's input freedom (form `noValidate`, inputs `step="any"`). New
> user-facing text in French. Reuse existing endpoints/patterns where research found them (e.g. the leads
> `whatsapp_devis` flow, `LeadExpressModal` quick-capture, the `ToitureDesign` roof builder).

**A — PDF generation & edit bugs (make creating a quote simple):**

**B — Simpler creation: inline client & product (product creation role-gated):**

**C — Creator identity & sending:**

**D — Variantes (3 variants, configurable %):**

**E — 3D roof viewer in quotes + standalone window:**

### Group QS — Supplier purchase-order (bon de commande fournisseur) UX & sending (founder request 2026-07-01)

*From Reda, on ordering products from a fournisseur (the SUPPLIER-side `BonCommandeFournisseur` in `apps/stock`, distinct from the client `ventes.BonCommande`): (1) add a product directly inside the bon de commande when ordering; (2) the PDF button doesn't work; (3) « Envoyer au fournisseur » only marks it sent and it's unclear what it did — he wants a WhatsApp button that sends the PDF to the supplier + an email-send button nearby, each greyed out when the supplier has no number / no email. Research: the BCF PDF endpoint (`/stock/bons-commande-fournisseur/<id>/pdf/`) EXISTS and works (WeasyPrint blob) — the button fails on the frontend and swallows the error into a generic « PDF indisponible »; `envoyer` (`bon_commande_fournisseur.py` ~L84) only flips BROUILLON→ENVOYE with no send; `Fournisseur` has nullable `telephone` + `email`; and the wa.me (`build_wa_url`/`normalize_ma_phone`) + `ShareLink` + `send_document_email`/`EmailLog` infra is all reusable.*

> **Constraints (every QS task).** Multi-tenant: everything company-scoped server-side; `company` never from the body. The BCF PDF is the supplier's own order and shows BUY prices (`prix_achat`) — it is legitimately sent to the FOURNISSEUR, but it must NEVER reach an end client: any tokenized link stays unguessable + expiring and is never surfaced client-side. WhatsApp `wa.me` can only carry text + a link (no file attachment) — so « envoyer par WhatsApp » sends a message with a tokenized link to the BCF PDF (mirroring the leads flow); email attaches the actual PDF. Cross-app reads via `selectors.py`/string-FK — never another app's models/views. Reuse the existing whatsapp/email/ShareLink infra; product creation stays gated to Directeur + Commercial responsable (QG4/QG5). New user-facing text in French.


### Group QD — Document PDF polish: logo size & file naming (founder request 2026-07-01)

*From Reda, looking at a real facture (`FAC-202607-0001`): (1) the company logo on the bill renders far too small; (2) the download filename `Facture_FAC-202607-0001.pdf` reads wrong — « Facture_FAC » is redundant and it carries no client/company context. Confirmed by inspecting the logo asset + the rendered invoice.*

> **Constraints.** Rule #4 — the facture keeps its own legacy WeasyPrint PDF (editable; NOT a quote-PDF path). Multi-tenant: the bill logo is the per-company `CompanyProfile.logo_key`. Keep aspect ratio (never distort). French UI.


### Group QP — Quote line product handling: picker filter, rename & create-in-stock (founder request 2026-07-01)

*From Reda, in the quote generator: (1) when picking the inverter for the HYBRID INVERTER slot, only inverters should show — not every product; (2) rename a product's line directly in the quote; (3) on rename, the ERP should ask « just change the name here (this quote) » vs « add a new product with the new name in stock ». Research: the generator is a FLAT line table (no typed slots) — a line's type is inferred from its designation via `classifyProduct` in `frontend/src/features/ventes/solar.js` (keys `onduleur_hybride` / `onduleur_reseau` / `panneau` / `batterie`…); `ProduitPicker` takes NO filter prop today (`ProduitPicker.jsx` ~L28-46, invoked at `DevisGenerator.jsx` ~L1563 with ALL products); the line `designation` is already inline-editable with a « désignation modifiée » warning when it diverges from the product name (`DevisGenerator.jsx` ~L1544-1560); `stockApi.createProduit` exists and is role-gated (QG4).*

> **Constraints.** Reuse the `solar.js` classifiers and keep them aligned with `quote_engine/builder.py` keywords (CLAUDE.md). Product creation stays gated to Directeur + Commercial responsable (QG4/QG5). `prix_achat` is never exposed client-side. Keep generator input freedom (`noValidate`, `step="any"`). French UI.


### Group CH — Chantier (installation) workflow redesign: international PV gates, director-configurable (founder request 2026-07-01)

*From Reda: the chantier/installation follow-up is weak — the steps are « kind of weird ». Redesign it to follow the internationally-recognized solar-PV installation lifecycle with proper gates, best-in-class UX, and let the DIRECTOR add/remove gates. Research: `Installation.statut` is a HARDCODED 7-step enum (SIGNÉ→MATERIEL_COMMANDE→PLANIFIE→EN_COURS→INSTALLE→RECEPTIONNE→CLOTURE); richer pieces already exist but aren't wired to it — a director-configurable execution checklist (`ChecklistTemplate`/`ChecklistEtapeModele`: add/remove/reorder, photo-required, serial-capture, `protege`), project milestones (`JalonProjet`: ETUDE/APPRO/POSE/MES/RECEPTION), and QHSE inspection HOLD POINTS (`PlanInspection`/`hold_point`) that block work but DON'T gate installation status; readiness (FG77) is advisory, not enforced — a chantier can reach RECEPTIONNE without passing any gate (the « weird » part). International lifecycle (IEC 62446-1 + EPC best practice): site survey → design/engineering → permitting & grid approval (loi 82-21 dossier) → procurement → mechanical install → electrical install → commissioning & testing (IEC 62446-1: documentation, visual inspection, electrical tests, performance & safety verification) → inspection / PTO & grid connection → handover (handover pack) → O&M.*

> **Constraints (every CH task).** Multi-tenant/company-scoped server-side. BUILD ON the existing configurable checklist pattern (`ChecklistTemplate`/`ChecklistEtapeModele`) — do NOT rip out `Installation.statut`; MAP it onto the new stages (no data loss). Preserve the existing side-effects: stock reservation at INSTALLE, warranty/parc handover at RECEPTIONNE (FG70). QHSE is a separate app — read hold-points via `selectors.py` / loose `chantier_id`, never import its models. `STAGES.py` is the CRM funnel (a permanent separate layer — do NOT touch). Gate CONFIGURATION is Directeur-only. French UI; keep e2e DOM hooks.


### Group QK — Quote-journey best-in-world audit gaps (ERP/backend; 2026-07-01)

*From a fresh 3-axis best-in-world audit of the client quote journey (content collected / content delivered / UX) benchmarked against Aurora, OpenSolar, Otovo, Tesla, EnergySage, Sunrun, 1KOMMA5°, Enpal, Bodhi + Morocco reality. These are the ERP/backend gaps NOT already covered by QJ/QF/QG/WJ. The website half is WEB_PLAN WJ30–WJ35. Morocco facts confirmed this pass: ANRE DEFERRED the BT-residential surplus buy-back tariff (savings stay self-consumption-only, injection line OFF); agricole financing = CAM « Saquii Solaire » (~5–6 %, 10 yr, 1-yr grace) + FDA 30 % pumping subsidy, NOT ISTIDAMA; typed-name e-sign valid (loi 43-20 art. 7). Honesty rule: no fabricated numbers.*


### Group MB — Mobile rendering root-cause fix (phone) (founder request 2026-07-01)

*From Reda: on the phone the ERP « does not render well at all » — stuff on top of each other, sometimes oversized pages. Two-agent diagnosis found the FOUNDATION is mostly sound (viewport `viewport-fit=cover` OK; the 768px breakpoint, `ResponsiveDialog` M158, DataTable→card M154, U2/U3 all shipped) — the real causes are a SMALL set of foundation bugs + incomplete adoption, so the right fix is systematic (fix the foundation once → sweep the un-adapted screens → add a mobile gate), not per-page patching. Root causes: (1) mobile `.layout-content` (`index.css` ~L2014) reserves NO space for the 52px sticky header (+notch) or the 52px bottom-tabbar → content scrolls BEHIND them (the overlap); (2) horizontal overflow from `.pp-pop { width: max(100%,380px) }` (380px on a 375px phone), a rigid catalogue `.cat-row` grid, and legacy fixed-pixel widths with no mobile `@media`; (3) z-index chaos — a `--z-*` scale EXISTS in `tokens.css` but ad-hoc magic numbers collide (`.pp-pop` set to 300 then overridden to 1 → sinks behind modals; `.gs-wrap` z-index 50 below the header; bottom-tabbar 1300 == modal); (4) `ResponsiveDialog` is used in ONE screen — the DevisList PDF/accept/email modals + the LeadForm modal are fixed-width Dialogs that overflow phones (can't accept/email a devis or edit a lead on mobile); (5) ~60% of legacy pages have no mobile CSS.*

> **Constraints.** Do NOT regress the shipped mobile work (M154–M158, U2/U3, J139–J144). Keep the e2e DOM hooks. Use the existing `--z-*` tokens + `ResponsiveDialog`/`useIsMobile` primitives — don't invent parallel ones. French UI. Frontend-only (no backend).


### Group WR — Wire orphaned backend features to the UI (whole-app audit, founder request 2026-07-01)

*From Reda: « a lot of non-working features built with no front end or not well wired ». A 7-agent evidence-based audit (verified by grepping the frontend for real callers) swept every app. RESULT: the pure frontend is sound (no dead routes / no-op buttons / calls to missing endpoints); the 9 backend-only MODULES (compta/paie/rh/gestion_projet/contrats/qhse/kb/litiges/ged) are ALREADY covered by PLAN.md Group UX (UX1–47) — EXCLUDED here; foundation/config (auth/roles/records/customfields/parametres) is fully wired. The real debt = individual features shipped BACKEND-ONLY inside modules that DO have a UI (ventes/stock/monitoring/crm/installations/sav) — their FG task was ticked done with no frontend task. These are those wire-ups. NOTE: installations readiness/handover (FG70/FG77) are folded into Group CH, so excluded here. Each task below: the backend ALREADY EXISTS (cited) — this is UI + api-client wiring only, no backend rebuild.*

> **Constraints (every WR task).** Backend already shipped — do NOT rebuild it; add the frontend surface + the api-client wrapper only. Multi-tenant/company-scoped (server already enforces). `prix_achat`/buy-price + margins NEVER shown client-side. Reuse the existing DataTable / ResponsiveDialog / recharts primitives (and the Group UX `ModuleDashboard`/`ListShell` kit where it helps). French UI; keep e2e hooks.


### Group QC — Moroccan company autocomplete on client creation (founder request 2026-07-01)

*From Reda: « in Odoo I can easily find Moroccan companies when I start typing their name as new clients — add this to my ERP. » Research verdict: Odoo's Partner Autocomplete is a paid IAP service backed by Clearbit WEB data — it does NOT return ICE/RC/IF for Morocco (Moroccan Odoo integrators install manual `partner_ice`/`l10n_ma_legal` field modules). There is NO free official API or open dataset (OMPIC DirectInfo has no API and its legal notice bans data reproduction; ice.gov.ma is CAPTCHA-gated; data.gov.ma has no company register). The ONLY compliant registry-backed API with Morocco depth is the paid Inforisk/Charika offer (~950k companies, licensed OMPIC data, quote-only pricing). Scraping any of these violates their ToS → rule #5 (risk file + founder approval) and is NOT pursued. Code side is ready: `Client` already has `ice`/`if_fiscal`/`rc` (and `Fournisseur` the identical trio — no migration), the generic async `Combobox` (`frontend/src/ui/Combobox.jsx`) is the typeahead, and the PVGIS proxy (`apps/parametres/pvgis.py`) is the cached-external-lookup pattern for the gated provider.*

- [BLOCKED: paid — needs founder-provisioned Inforisk/Charika account] QC2 — **[GATED: paid — Inforisk/Charika API] Registry-backed autocomplete (the true Odoo-style experience).** Behind a flag (default OFF), plug a licensed Moroccan-registry provider into the QC1 seam: type a name → provider suggestions (ICE/RC/IF/adresse from licensed OMPIC data) → pick → auto-fill, with server-side caching (24 h, PVGIS-proxy pattern), rate limiting, and a clean no-key degrade to QC1's own-data mode. NEEDS FOUNDER: an Inforisk/Charika account + contract/budget (pricing is quote-only) — OR a founder-led OMPIC licensed-feed inquiry. Never scrape OMPIC/ice.gov.ma/Charika (ToS-prohibited; rule #5). **Done =** with a provider key the autocomplete returns registry-backed Moroccan companies and fills the legal IDs; without it, behaviour is exactly QC1; tests cover the provider seam + the degrade + the never-leak of the key client-side. Files: a provider client in `apps/crm/` (or `apps/parametres/` beside pvgis), `apps/crm/views.py`, settings flag, tests. (DEP/COST — needs founder-provisioned Inforisk/Charika account; note in DONE LOG) (@lane: backend/crm) (@after: QC1)

### Groupe LW — Lead Workspace (la plus belle fenêtre de l'ERP) : cockpit 3 zones, autosauvegarde sans perte, chatter épinglable (synthèse design 7 recons + Fable, fondateur 2026-07-18)

*Provenance : demande du fondateur — « cette partie doit être la plus belle et la plus simple de
mon ERP — probablement du monde ». Reda et Meriem passent l'essentiel de leur journée dans la
fiche lead, en basculant de client en client. Sept recons parallèles (anatomie frontend, surface
backend, patterns best-in-class Attio/Linear/HubSpot/Odoo/Pipedrive/Close, audit CSS, chasse aux
bugs, catalogue ui/, contrat tests+e2e) puis une synthèse Fable. Le blueprint complet — décisions
D1-D5, spec du moteur d'état `useLeadDraft`, carte des 14 fichiers, layout par breakpoint, langage
visuel — est LA référence de chaque tâche : `scratchpad/design/blueprint.md` (recopier dans
`docs/design/lead-workspace-blueprint.md` en LW9). Verdicts : (D1) UN composant `LeadWorkspace`
rendu en Dialog quasi-plein-écran depuis la liste (rafale J/K intacte) ET en pleine page à
`/crm/leads/:id` ; (D2) hybride — inputs toujours-éditables + autosauvegarde par vidage de draft
en édition, formulaire rapide inchangé en création ; (D3) rail identité 288px / centre sections /
rail contexte 384px à onglets (Historique·Devis·Activités·Pièces) ; (D4) tokens only, StatusPill,
fast-in/slow-out, skeleton à l'ouverture ; (D5) liste ferme des interdits.*

> **Contraintes (chaque tâche LW).** Zéro nouvelle dépendance npm. Ne JAMAIS toucher
> `apps/ventes/quote_engine/` ni aucun chemin PDF (règle #4). Clés d'étape uniquement via
> `features/crm/stages.js` (miroir STAGES.py, règle #2) ; aucun nouveau modèle de funnel.
> `DocumentStageTrack` jamais pour le funnel lead. `prix_achat`/marge jamais client-facing.
> Jamais snap/rejeter une valeur tapée (`noValidate`, `step="any"`). UNE seule migration, additive
> (`LeadActivity.pinned`), révertable. Backend : company scoping + `perform_create` force
> `company`. Hooks e2e conservés ou mis à jour DANS la même tâche (contrat listé au blueprint).
> UI en français, contraste AA clair ET sombre, `prefers-reduced-motion` respecté. Le CSS nouveau
> vit dans un bloc append-only `.lw-*` de `frontend/src/index.css`, tokens sémantiques uniquement.

**LANE 0 — urgence (à bâtir EN PREMIER, commits autonomes ; ces fixes portent sur le code actuel
et survivent à la refonte — les 4 bugs de perte de données reçoivent leur fix sur place MAINTENANT
car ≤10 lignes chacun, ET sont ré-éliminés par construction par le moteur LW9 ; un bug qui
attendrait la refonte n'est acceptable que si elle atterrit dans la même session — on ne parie pas) :**

- [x] LW1 — **P0 : le corps de la fiche lead ne scrolle pas, le bouton Enregistrer est hors d'atteinte.** Cause racine vérifiée (recon 04 §3) : `DialogContent` est un grid avec `overflow-hidden` (className LeadForm.jsx:1032) dont les enfants sont des frères plats ; le `<form>` (L1264) n'a AUCUNE classe, la règle morte `.modal > form` (index.css:1364-1373) ne matche plus rien depuis VX89 → `.modal-body` (flex:1, overflow-y:auto) n'est jamais borné, l'excès est CLIPPÉ : sur un laptop ~800px le submit est inatteignable, le scroll-spy/jumpTo/ScrollProgress/useKeyboardAwareScroll sont tous morts. Même casse dans la variante Sheet mobile. Fix : donner au `<form>` la classe explicite `flex flex-col flex-1 min-h-0 overflow-hidden` (fonctionne en parent grid ET flex), vérifier que `.modal-body` scrolle dans les deux variantes. ATTENTION : NE PAS supprimer la règle `.modal > form` d'index.css — elle est encore PORTEUSE pour le shell legacy `.modal` de `UsersManagement.jsx`, que le spec CI-gated `mobile.spec.js` E16+ teste (le modal utilisateur doit tenir dans l'iPhone) ; elle ne matche simplement plus la fiche lead. Files : `frontend/src/pages/crm/LeadForm.jsx` (L1264). DoD : sur viewport 1280×720 ET 375×812, le footer submit est visible/cliquable, la molette scrolle `.modal-body`, le rail scroll-spy change de section active ; la règle `.modal > form` d'index.css est intacte. (ROUTINE — S) (@model: sonnet) (@lane: LW0)
- [x] LW2 — **Perte de données #1 : le raccourci d'étape 1-4 « blanchit » les éditions non sauvées.** `quickChangeStage` (LeadForm.jsx:862-872) PATCHe `{stage}` seul mais pose `setCleanFieldsJSON(JSON.stringify({...fields, stage}))` — l'instantané « propre » absorbe TOUTES les éditions en cours → `isDirty` devient faux → fermeture/J-K sans avertissement, éditions perdues (le flux rafale exact que servent les touches 1-4). Fix : fusionner UNIQUEMENT `stage` dans l'instantané propre EXISTANT (`const clean = JSON.parse(cleanFieldsJSON); setCleanFieldsJSON(JSON.stringify({...clean, stage: updated.stage ?? newStage}))`) et ne mettre à jour `fields.stage` que si l'utilisateur n'a pas d'édition en cours sur ce champ. Files : `frontend/src/pages/crm/LeadForm.jsx` (L862-872). DoD : test unitaire — taper dans `nom`, presser « 2 », vérifier `isDirty` reste vrai et la valeur tapée intacte ; `LeadForm.test.jsx` vert. (ROUTINE — S) (@model: sonnet) (@lane: LW0)
- [x] LW3 — **Perte de données #2/#4 + fuites inter-leads : l'état satellite survit à la navigation J/K.** L'effet de resynchronisation (LeadForm.jsx:516-530) remet `fields/errors/customData` mais PAS : `waSelected` (→ envoi WhatsApp des devis du lead PRÉCÉDENT sous l'id du nouveau — mauvais document au client, P1#2), `noteBody`/`noteFile` (→ note classée sur le mauvais lead, P1#4), `billEditing/billHiver/billEte/billError` (→ facture de A PATCHée sur B, P2#8), `staleInfo` de `useStaleGuard` (→ « Enregistrer quand même » force-save le MAUVAIS lead, P2#7), `waPreview/waLangue/devisActionMsg/cardPaste/noteError`. Fix : dans CE même effet, réinitialiser TOUT l'état listé (waLangue ← `lead?.langue_preferee || 'fr'`) et exposer/appeler un `reset()` sur `useStaleGuard` (hooks/useStaleGuard.js). Files : `frontend/src/pages/crm/LeadForm.jsx` (L516-530), `frontend/src/hooks/useStaleGuard.js`. DoD : test unitaire de non-transport — sélectionner un devis WhatsApp + taper une note sur le lead A, naviguer vers B (changement de prop `lead`), vérifier `waSelected.size===0` et composer vide ; suite vitest verte. (ROUTINE — M) (@model: sonnet) (@lane: LW0)
- [x] LW4 — **Perte de données #3 : « a »/bouton Archiver jettent les éditions sans confirmation + customData fuit en rafale de création.** `toggleArchive` (LeadForm.jsx:842-853) appelle `onSaved();onClose()` sans passer par `confirmLeaveIfDirty` — éditions non sauvées perdues en silence (raccourci « a », L878). Et « Créer un autre » (L990-1001) reset `fields/errors/dups` mais PAS `customData` → le lead suivant hérite des champs personnalisés du précédent (P2#5, envoyés à L959). Fix : envelopper l'archivage (`if (!confirmLeaveIfDirty(isDirty)) return`) et ajouter `setCustomData({})` au reset création. Files : `frontend/src/pages/crm/LeadForm.jsx` (L842-853, L990-1001). DoD : test — champ modifié + « a » → `window.confirm` appelé ; création en rafale → `customData` vide au 2e lead. (ROUTINE — S) (@model: sonnet) (@lane: LW0)
- [x] LW5 — **SigneDialog : la date « futur » se trompe d'un jour le soir (UTC vs local).** `SigneDialog.jsx:207-211` compare `toISOString()` (UTC) à la date locale de l'input, et la date par défaut (L121) est semée depuis `toISOString` : à UTC+1 le soir, faux avertissement « date future » / défaut = hier. Fix : construire la date du jour en LOCAL (`new Date().toLocaleDateString('fr-CA')` ou getFullYear/Month/Date paddés) pour la comparaison ET le défaut. Files : `frontend/src/pages/crm/leads/SigneDialog.jsx` (L121, L207-211). DoD : test `.mjs` avec horloge mockée à 23h30 Africa/Casablanca — le défaut est bien aujourd'hui, aucune alerte « future » ; `SigneDialog.test.mjs` vert. (ROUTINE — S) (@model: sonnet) (@lane: LW0)
- [x] LW6 — **AppointmentBooker : annulation avalée en silence + `<form>` imbriqué invalide.** `AppointmentBooker.jsx:74-81` — le `catch {}` avale l'échec d'annulation puis `load()` : l'utilisateur croit le RDV annulé alors qu'il tient toujours (double-booking client réel). Et L259 rend un `<form>` DANS le `<form>` de LeadForm (HTML invalide, propriété du Enter fragile, recon 05 #10). Fix : toast d'erreur explicite (`toast.error`) + état bouton en échec ; remplacer le `<form>` interne par un `<div role="group">` avec submit au clic/Enter géré localement (`onKeyDown`). Files : `frontend/src/pages/crm/leads/AppointmentBooker.jsx` (L74-81, L259). DoD : `grep -n "<form" frontend/src/pages/crm/leads/AppointmentBooker.jsx` = 0 ; échec réseau d'annulation simulé → toast visible, RDV toujours listé. (ROUTINE — M) (@model: sonnet) (@lane: LW0)
- [x] LW7 — **normalizeMaPhone accepte n'importe quoi → bouton WhatsApp armé sur un numéro invalide.** `lib/format.js:181-193` renvoie `"212"+local` pour toute suite de chiffres (vs `canonicalPhoneMA` L159-172 qui exige 9 chiffres commençant par 5/6/7) : `leadPhoneOk` (LeadForm.jsx:378) est vrai pour du bruit, la branche « Numéro invalide » (L1765) ne s'affiche presque jamais, et l'envoi part au 400 serveur. Fix : aligner `normalizeMaPhone` sur la validation de `canonicalPhoneMA` (longueur + préfixe 5/6/7 après indicatif), retour `null` sinon — sans JAMAIS reformater pendant la frappe (écho serveur seulement). Files : `frontend/src/lib/format.js` (L181-193). DoD : tests `.mjs` — `normalizeMaPhone('0612345678')==='212612345678'`, `normalizeMaPhone('123')===null`, `normalizeMaPhone('+212 6 12 34 56 78')` ok ; suite `format` verte ; recherche des autres appelants (`grep -rn normalizeMaPhone frontend/src`) vérifiée sans régression. (ROUTINE — M) (@model: sonnet) (@lane: LW0)
- [x] LW8 — **Backend : N+1 confirmé sur le chatter `historique/`.** `apps/crm/views.py:944-950` sérialise `lead.activites.all()` sans `select_related('user','attachment')` — chaque ligne retouche 2 FK (recon 02 §5). Fix : ajouter le `select_related` (+ `order_by` explicite si absent). Files : `backend/django_core/apps/crm/views.py` (L944-950). DoD : test avec `assertNumQueries` borné (≤4 quel que soit le nombre d'activités) dans `apps/crm/tests/` ; suite crm verte. (ROUTINE — S) (@model: haiku) (@lane: LW0)

**LANE 8 — résidus de la critique Fable finale (2026-07-19 — mineurs, prochaine session) :**

- [ ] LW41 — **`chatter_recent` doit vraiment économiser la requête historique.** Le shell fetch TOUJOURS `/historique/` au montage (LeadWorkspace.jsx `refreshHistorique`) alors que le GET détail embarque déjà `chatter_recent` (LW30) — l'ouverture coûte plus cher qu'avant, pas moins. Fix : ne déclencher le fetch initial d'historique QUE si `state.server.chatter_recent` est absent/vide ; les rafraîchissements après action restent inchangés. Purger aussi l'état `dups` mort du shell (le rail et la section ont leurs propres sources). Files : `frontend/src/features/crm/workspace/LeadWorkspace.jsx`. DoD : à l'ouverture d'un lead avec chatter_recent, AUCUN GET `/historique/` (mock vitest) ; « voir plus »/post de note le déclenche. (ROUTINE — S) (@model: sonnet) (@lane: LW8R)
- [ ] LW42 — **`changeStage` : messages d'erreur fidèles.** Toast unique « Retour d'étape non autorisé » pour TOUT 400 (un lead perdu verrouillé reçoit le mauvais message) et silence total hors-400 (offline = clic muet). Fix : surfacer `err.response.data.detail` quand présent, sinon un toast générique d'échec réseau. Files : `frontend/src/features/crm/workspace/useLeadDraft.js`. DoD : test — 400 avec detail « Lead perdu… » → toast au texte serveur ; erreur réseau → toast générique. (ROUTINE — S) (@model: sonnet) (@lane: LW8R)
- [ ] LW43 — **Gardes d'identité sur les données d'affichage hors-moteur.** `historique`/`dups`/`clientMatch`/compteurs d'onglets n'ont pas la garde `res.id === leadId` : une réponse lente du lead A peut se peindre sur le lead B après un J/K rapide (la thèse du moteur, pas encore appliquée aux satellites). Fix : capturer le leadId à l'envoi et ignorer les réponses d'un autre lead (pattern LeadDetailPage `cancelled`). Files : `frontend/src/features/crm/workspace/LeadWorkspace.jsx`, `IdentityRail.jsx`, `ContextRail.jsx`, `TimelineTab.jsx`. DoD : test de course — réponse A résolue après LOAD_LEAD(B) → jamais rendue. (ROUTINE — M) (@model: sonnet) (@lane: LW8R)
- [ ] LW44 — **⌘K : Récents au bon nom + focus WhatsApp réel.** `pushRecentEntity` part avant la synchro du titre (1re ouverture = libellé vide, J/K = nom du lead PRÉCÉDENT) ; le focus du composer WhatsApp vise `input[type=checkbox]` alors que `ui/Checkbox` est un bouton Radix (no-op). Files : `frontend/src/features/crm/workspace/LeadWorkspace.jsx`, `ContextRail.jsx`. DoD : tests — Récents contient le nom du lead OUVERT ; l'événement WhatsApp focus le premier contrôle de sélection réel. (ROUTINE — S) (@model: sonnet) (@lane: LW8R)
- [ ] LW45 — **Hygiène résiduelle : cache préchargement au logout + chips QX28 état manquant + commentaire skeleton.** Vider le cache Map de `leadPrefetch.js` sur l'événement de déconnexion (fuite inter-session de 60 s) ; redonner aux chips de préparation un état « manquant » discret (l'ancien en-tête les stylait aussi en négatif — aujourd'hui seule l'infobulle du CTA devis le dit) ; corriger le commentaire mensonger du skeleton (le rail est DANS le FadeSwap). Files : `frontend/src/features/crm/workspace/leadPrefetch.js`, `IdentityRail.jsx`, `LeadWorkspace.jsx`. DoD : test logout→cache vide ; revue visuelle des chips. (ROUTINE — S) (@model: sonnet) (@lane: LW8R)

#### DONE LOG — Groupe LW (fenêtre lead)

- 2026-07-18 — LW1+LW1(b) : scroll de la fiche lead réparé — classes de hauteur sur le <form> ET DialogContent passé en colonne flex (un grid aux rangées auto ne rétrécit jamais son contenu ; prouvé par repro Playwright — l'orchestrateur a corrigé la tâche telle que spécifiée, qui ne suffisait PAS en desktop). Footer/submit atteignables, scroll-spy revit. (ROUTINE)
- 2026-07-18 — LW2 : le raccourci d'étape 1-4 ne « blanchit » plus les éditions non sauvées (fusion de la seule clé stage dans l'instantané propre). (ROUTINE)
- 2026-07-18 — LW3 : plus aucune fuite inter-leads à la navigation J/K — waSelected/note/facture inline/bannière stale/carte collée tous réinitialisés + reset() sur useStaleGuard. (ROUTINE)
- 2026-07-18 — LW4 : Archiver (bouton et raccourci « a ») passe par la garde d'éditions non sauvées ; « Créer un autre » remet custom_data à zéro. (ROUTINE)
- 2026-07-18 — LW5 : SigneDialog parle en date LOCALE (défaut + garde « date future ») — fini le décalage d'un jour entre minuit et 1h du matin. (ROUTINE)
- 2026-07-18 — LW6 : annulation de RDV honnête (toast d'erreur + bouton busy, la liste ne ment plus) ; le <form> imbriqué invalide devient un group. (ROUTINE)
- 2026-07-18 — LW7 : normalizeMaPhone valide vraiment (9 chiffres, préfixe 5/6/7) — le bouton WhatsApp ne s'arme plus sur du bruit ; 3 appelants vérifiés compatibles. (ROUTINE)
- 2026-07-18 — LW8 : N+1 du chatter historique/ éliminé (select_related user/attachment) + test de budget de requêtes. (ROUTINE)
- 2026-07-18 — LW27 : 11 champs métier de plus journalisés au chatter (montant estimé, clôture prévue, distributeur…) — jamais les champs système utm/meta. (ROUTINE)
- 2026-07-18 — LW28 : note épinglable — LeadActivity.pinned (migration additive 0064, révertable) + actions epingler/desepingler company-scopées (perm fine crm_modifier via get_permissions, le piège #25 évité) + tri épingle-d'abord. (SCHEMA)
- 2026-07-18 — LW29 : pii_masked exposé par le serializer — le masquage PII devient visible côté front au lieu d'un drop silencieux au PATCH. (ROUTINE)
- 2026-07-18 — LW30 : chatter_recent (50 dernières activités, épingle-d'abord, sans N+1) embarqué sur le GET détail UNIQUEMENT — l'ouverture de fiche économise une requête. (ROUTINE)
- 2026-07-18 — HORS GROUPE (débloquant) : collision de casse Windows segmentBuilder.js/SegmentBuilder.jsx + enqueteBuilder.js → renommés segmentRules.js/enqueteRules.js — `vite build` refonctionne sur la machine du fondateur (CI Linux n'a jamais vu le bug). (ROUTINE)

- 2026-07-19 — LW9-LW12 (lane 1, opus) : le moteur `useLeadDraft` (draft sparse par lead, flush PATCH partiel gardé par id, typed-during-flight, miroir sessionStorage, stage jamais dans le draft) + le shell `LeadWorkspace` 3 zones au scroll juste par construction + les 6 fichiers de sections (39 ids lf-* portés 1:1) + le mode création rafale. 15 assertions node du réducteur vertes. (ARCH)
- 2026-07-19 — LW13 : bascule des appelants — l'ancien LeadForm (2 117 lignes) devient un adaptateur de 12 lignes ; kanban/liste ET /crm/leads/:id rendent le même cockpit. (ROUTINE)
- 2026-07-19 — LW14-LW18 (lane 2, opus) : rail identité complet — avatar/contact cliquable/chips QX28 en Badge tokenisés (les 4 tokens inexistants morts), triade responsable·prochaine action·relance éditable sur place, StageControl en StatusPill avec rampe de pourrissement (classifieur pur node-testé), popover score_reasons, bannières doublons/déjà-client/carte. (ROUTINE)
- 2026-07-19 — LW19-LW22 (lane 3) : rail contexte à onglets (Tabs ARIA), TimelineTab (en-tête multi-touch FG204, filtre persisté, épingles LW28, composer du MOTEUR — la note ne fuit plus), DevisTab (cartes StatusPill + CTA devis-auto avec champs manquants cliquables + mini-chaîne document) + barre WhatsApp multi-devis FR/Darija d'état moteur. Hook e2e `.lead-devis-badge` re-logé sur l'onglet Devis (contrat E4 CI-gated). (ROUTINE)
- 2026-07-19 — LW23-LW26 (lane 4) : raccourcis réparés (« d » focus le picker, « n » compose, 1-4 via moteur, dep arrays partout), préchargement idle des voisins J/K (cache TTL 60s gardé par id), skeleton d'ouverture en forme de grille (useDelayedLoading+FadeSwap), palette ⌘K contextuelle (« Fiche ouverte ») + Récents. Câblages inter-lanes posés (set-field/change-stage, dispatch → ContextRail, écouteurs lw:open-*). (ROUTINE)

- 2026-07-19 — LW31-LW36 (lane 6) : zéro hex dans la fenêtre (badges/bannières tokenisés, blocs legacy .lead-* purgés après grep, chatter re-tokenisé pour le sombre — retour QA navigateur de l'orchestrateur), un seul Avatar (AssigneePicker sur ui/Avatar + --owner-color-1..10 par id), passe premium (échelle typo stricte, gaps 8px, hover-reveal transform/opacity, fade des nav-chips), responsive vrai (720px mort supprimé, 768-1023 en 2 colonnes + Sheet contexte, barre-pouce mobile safe-area, useKeyboardAwareScroll re-branché), a11y axe réel (1 violation corrigée : input fichier sans label), AppointmentBooker 30 styles inline → 0 (kit + .lw-booker*). (ROUTINE)

- 2026-07-19 — LW37-LW40 (lane 7, opus) : les 20 suites LeadForm* migrées/supprimées (sémantiques portées sur les suites workspace, 8 suites orphelines re-ciblées), burstSafety.test.jsx verrouille les 5 scénarios de perte sur le vrai moteur, contrat e2e mis à jour délibérément (E5/E6 autosave, E9/E10 onglets, E11 #lf-telephone ; helpers + specs CI-gated E4/MB6 inchangés vérifiés ligne à ligne), LeadForm.jsx SUPPRIMÉ (imports directs LeadWorkspace), CODEMAP §4 à jour. Post-fold orchestrateur : garde MB2 obsolète retirée, 9 :hover gardés (hover:hover), fingerprints restampés. (ROUTINE)

**LANE 1 — décomposition (UN agent, séquentiel : chaque tâche bâtit sur la précédente) :**

- [x] LW9 — **Le moteur d'état `useLeadDraft` : la perte de données devient structurellement impossible. @after LW1-LW4.** Créer `frontend/src/features/crm/workspace/draftCore.js` (réducteur PUR + `canonEq` + `applyFlushSuccess` — zéro import React) et `useLeadDraft.js` (hook) selon la spec D2 du blueprint (recopier d'abord le blueprint dans `docs/design/lead-workspace-blueprint.md` — il devient LA référence commitée) : état ENTIER keyé par `leadId` remplacé atomiquement à la navigation (`LOAD_LEAD`) ; `draft` SPARSE des seules clés touchées (fini le JSON.stringify de 50 clés) ; `FLUSH` par PATCH partiel avec garde `res.id === leadId` (réponses du lead précédent JETÉES), « typed-during-flight » (une frappe pendant le vol reste dirty), ré-hydratation des valeurs canonisées serveur (téléphones), retour de `inflight` dans `draft` sur échec (rien n'est jamais perdu) ; `stage` JAMAIS dans le draft ; `leaveGuard(action)` = flush-puis-agir pour TOUTES les sorties ; miroir sessionStorage `taqinor.lead.draft.<id>` purgé au flush réussi, restauré avec chip « Brouillon restauré » ; intégration `useStaleGuard` keyée. Mode `create` : flush désactivé, submit unique. Files : `frontend/src/features/crm/workspace/draftCore.js` (nouveau), `frontend/src/features/crm/workspace/useLeadDraft.js` (nouveau), `frontend/src/features/crm/workspace/draftCore.test.mjs` (nouveau), `docs/design/lead-workspace-blueprint.md` (nouveau). DoD : tests node:test couvrant — LOAD_LEAD purge wa/note/bill/stale ; SET_FIELD prune l'égalité canonique ('' ≡ null, '30' ≡ 30) ; flush succès ne blanchit pas une frappe en vol ; flush échec conserve le draft ; réponse d'un autre leadId ignorée ; ≥12 assertions vertes. (ARCH — L) (@model: opus) (@lane: LW1) (@after: LW1, LW2, LW3, LW4)
- [x] LW10 — **Le shell `LeadWorkspace` : une fenêtre, deux enveloppes, le scroll juste par construction. @after LW9.** Créer `frontend/src/features/crm/workspace/LeadWorkspace.jsx` : props = contrat LeadForm actuel (`lead,onClose,onSaved,leadsQueue,onNavigateLead,initialDevis,focusSection`) + `variant='dialog'|'page'`. Dialog ≥768px en `w-[min(1440px,96vw)] h-[min(920px,94dvh)]` (classe `.lw-dialog`), Sheet bas pleine hauteur <768px, `<div className="lw-root">` nu en variante page. Grille interne `grid-template-rows:auto 1fr` + colonnes `288px minmax(0,1fr) 384px`, `min-height:0` sur la rangée 1fr, CHAQUE zone son propre `overflow-y:auto` (plus jamais un form sans classe entre grid et corps — cause P0). Bandeau : ◀▶ « i / n » + J/K (effet AVEC dep array, garde `isTypingTarget`), `DialogTitle className="modal-title"` rendant « Lead — {nom} »/« Nouveau lead » (contrat e2e), chip d'état de sauvegarde (`Enregistrement…/✓ Enregistré/⚠ Réessayer`), bannière stale, ✕ `.modal-close` via `leaveGuard`. CSS : bloc append-only `.lw-*` dans `index.css`, tokens sémantiques uniquement, liseré 2px `--module-accent-azur` en haut du bandeau. Files : `frontend/src/features/crm/workspace/LeadWorkspace.jsx` (nouveau), `frontend/src/index.css` (bloc `.lw-*`). DoD : monté avec 3 zones factices, chaque zone scrolle indépendamment à 1280×720 ; Escape/✕ passent par leaveGuard ; J/K naviguent avec draft flushé ; `grep -n "#[0-9a-fA-F]\{3,6\}" ` sur le bloc `.lw-*` = 0. (ARCH — L) (@model: opus) (@lane: LW1) (@after: LW9)
- [x] LW11 — **Le centre : `SectionsPane` + les 6 fichiers de sections, port 1:1 des champs. @after LW10.** Créer `SectionsPane.jsx` (registre de sections, nav-chips horizontaux sticky avec scroll-spy throttlé rAF + `aria-current="true"`, repli persisté par section `localStorage`, wrapper `<form className="lw-form">` seulement en création) et les sections pures `sections/SectionPipeline.jsx` (suivi commercial SANS le select stage — remplacé par StageControl LW16 ; perdu/motif, verrous existants), `SectionContact.jsx` (#lf-nom conservé, paste-carte VX237, PhoneHint, paste-clean tel/whatsapp, bannière dup live VX239, GPS + « Voir sur la carte »), `SectionEnergie.jsx` (facture hiver/été + ete_differente + conso/tranche/raccordement/82-21 + sous-bloc Pompage agricole avec req-auto), `SectionSite.jsx` (toiture), `SectionVisite.jsx` (visite + AppointmentBooker embarqué), `SectionDivers.jsx` (Origine web en DefinitionList RO repliée par défaut + Note générale + CustomFieldsInput — enfin DANS la nav). Chaque section : `{state, setField, errors}`, présentation pure, ErrorBoundary par section (motif VX205), champs identiques à LeadForm (labels, ordres, verrous, `step="any"`, suggestions VX93/VX249b owner/ville). Files : `frontend/src/features/crm/workspace/SectionsPane.jsx` (nouveau), `frontend/src/features/crm/workspace/sections/SectionPipeline.jsx`, `SectionContact.jsx`, `SectionEnergie.jsx`, `SectionSite.jsx`, `SectionVisite.jsx`, `SectionDivers.jsx` (nouveaux), `frontend/src/index.css` (`.lw-sections*`). DoD : inventaire de champs — chaque champ du tableau recon 01 §2 présent exactement une fois (`grep` par name/id) ; scroll-spy actif au scroll ; sections repliées persistent au remount ; vitest de rendu des 6 sections vert. (ROUTINE — XL) (@model: sonnet) (@lane: LW1) (@after: LW10)
- [x] LW12 — **Mode création : le formulaire rapide, défauts intelligents et « créer un autre » intacts. @after LW11.** Câbler `LeadWorkspace` en création (`lead=null`) : mêmes sections, `useLeadDraft` en mode `create` (flush désactivé, un seul submit « Créer le lead »), défauts VX93 (owner=moi, canal walk_in, dernière ville via `LAST_VILLE_KEY`), style « suggéré » VX249b sur owner/ville jusqu'au premier toucher, Switch « Créer un autre » persisté (`CREER_UN_AUTRE_KEY`) : succès → reset complet (customData INCLUS — parité LW4), refocus #lf-nom, `rememberVille`. Validation client identique (nom requis, email regex, perdu→motif requis) + interception SIGNED impossible en création. Footer `FormActions` sticky (mobile). Files : `frontend/src/features/crm/workspace/LeadWorkspace.jsx`, `frontend/src/features/crm/workspace/useLeadDraft.js`. DoD : test — création en rafale de 2 leads : le 2e a owner=moi/ville mémorisée/customData vide et le focus est sur Nom ; « Créer le lead » ferme quand le Switch est OFF ; vitest vert. (ROUTINE — L) (@model: sonnet) (@lane: LW1) (@after: LW11)
- [x] LW13 — **Bascule des appelants : la liste, la route détail, et LeadForm devient un adaptateur. @after LW12.** `LeadsPage.jsx` (L602-616) rend `LeadWorkspace variant="dialog"` (mêmes props qu'aujourd'hui) ; `LeadDetailPage.jsx` rend `LeadWorkspace variant="page"` (GET complet + skeleton, gagne ENFIN la parité de fonctionnalités avec le flux liste) ; `pages/crm/LeadForm.jsx` devient un adaptateur mince `export default (props) => <LeadWorkspace variant="dialog" {...props}/>` (les tests unitaires existants continuent de passer jusqu'à LW39, aucun autre appelant cassé — vérifier `grep -rn "LeadForm" frontend/src`). Les satellites (SigneDialog, PlanActiviteDialog, ConvertirClientDialog, LeadDevisPanel) sont importés par LeadWorkspace depuis leur place actuelle. Files : `frontend/src/pages/crm/leads/LeadsPage.jsx` (L602-616), `frontend/src/pages/crm/leads/LeadDetailPage.jsx`, `frontend/src/pages/crm/LeadForm.jsx` (devient ~10 lignes). DoD : ouvrir une fiche depuis kanban ET liste ET `/crm/leads/:id` rend le workspace ; `wc -l frontend/src/pages/crm/LeadForm.jsx` < 30 ; vitest + `npm run lint` verts. (ROUTINE — M) (@model: sonnet) (@lane: LW1) (@after: LW12)

**LANE 2 — rail identité (parallèle après LW10, fichiers disjoints de LANE 1/3) :**

- [x] LW14 — **`IdentityRail` : l'identité, la préparation et les actions à demeure. @after LW10.** Créer `frontend/src/features/crm/workspace/IdentityRail.jsx` (`data-testid="lw-identity-rail"`) : `ui/Avatar` (jamais components/Avatar) + nom `--text-h2` + société/ville ; bloc contact (tel/email cliquables `tel:`/`mailto:`, GPS → lien carte existant) ; chips de préparation QX28 (📍 toiture / 🧾 facture / ⚡ devis prêt) en `ui/Badge` tone success/neutral (les 4 fallbacks de tokens INEXISTANTS LeadForm.jsx:1132-1144 meurent ici — bug dark-mode recon 04) ; badge « Archivé » ; pile d'actions : Envoyer WhatsApp (armée par LW7), Appeler, Devis automatique (CTA `--primary`, verrou `devis_auto.pret` + message), « Concevoir la toiture (3D) » avec 📍 si GPS, Convertir en client, Archiver/Restaurer — toutes routées par `leaveGuard`. Files : `frontend/src/features/crm/workspace/IdentityRail.jsx` (nouveau), `frontend/src/index.css` (`.lw-rail*`). DoD : toutes les actions listées présentes et fonctionnelles (mocks) ; `grep -n "color-success-muted\|color-info-muted\|color-primary-muted" frontend/src/features/crm/workspace/` = 0 ; rendu AA en dark (revue visuelle). (ROUTINE — L) (@model: sonnet) (@lane: LW2) (@after: LW10)
- [x] LW15 — **La triade obligatoire : responsable · prochaine action · relance, toujours visibles et éditables sur place. @after LW14.** Dans IdentityRail : `AssigneePicker` (hooks `.ap-*` conservés) pour le responsable ; « Prochaine action » = `next_activity.summary + due_date` du payload (ou « Aucune — planifier » ouvrant l'onglet Activités) ; `relance_date` en édition rapide (DatePicker inline, PATCH via le moteur). Le pattern noCRM/recon 03 #16/#19 : un lead sans prochaine action est visuellement en défaut (Badge warning « Sans prochaine action »). Files : `frontend/src/features/crm/workspace/IdentityRail.jsx`. DoD : modifier la relance depuis le rail PATCHe et pulse (`FieldSavedPulse`) ; lead sans next_activity affiche le badge d'alerte ; vitest vert. (ROUTINE — M) (@model: sonnet) (@lane: LW2) (@after: LW14)
- [x] LW16 — **`StageControl` : l'étape en StatusPill, le pourrissement visible, SIGNED toujours gardé. @after LW10.** Créer `StageControl.jsx` (rendu dans IdentityRail) : rangée des 6 étapes en `ui/StatusPill` (clés/labels via `features/crm/stages.js` UNIQUEMENT — règle #2), courante pleine + « depuis N j » (`stage_since_days`), autres cliquables ; rampe « rotting » (NEW>2j ambre/>5j rouge ; CONTACTED, QUOTE_SENT >7/>14 ; FOLLOW_UP >14/>30 — fonds `--warning`/`--destructive` à ~12%) ; clic SIGNED → `flush()` puis SigneDialog (JAMAIS de PATCH SIGNED direct — l'acceptation devis+option avance l'étape côté serveur, couches funnel/document séparées) ; recul de funnel → le 400 serveur devient un toast explicatif (« Retour d'étape non autorisé ») ; raccourcis 1-4 re-câblés sur ce contrôle via `LEAD_STAGE_SHORTCUTS` (SIGNED/COLD exclus, inchangé), sans jamais toucher `draft` (le bug LW2 est impossible ici par construction). Files : `frontend/src/features/crm/workspace/StageControl.jsx` (nouveau), `frontend/src/index.css` (`.lw-stage*`). DoD : `grep -n "NEW\|CONTACTED\|QUOTE_SENT" frontend/src/features/crm/workspace/StageControl.jsx` ne montre AUCUN littéral de clé hors import stages.js ; clic Signé ouvre SigneDialog ; test unitaire du rotting (mock stage_since_days=8 sur CONTACTED → classe warning). (DECISION — L) (@model: opus) (@lane: LW2) (@after: LW10)
- [x] LW17 — **Le score s'explique enfin : popover `score_reasons` + réutilisation `scoreTooltip`. @after LW14.** Le backend recalcule et expédie `score/score_label/score_reasons` sur CHAQUE GET (VX221, recon 02 §4) et l'UI n'en rend que le badge. Dans IdentityRail : `ScoreBadge` (features/crm) devient déclencheur d'un `Popover` listant les raisons (icône + libellé + points, positif/négatif par tone), pied « Le score se recalcule à chaque modification ». Files : `frontend/src/features/crm/workspace/IdentityRail.jsx`, `frontend/src/features/crm/ScoreBadge.jsx` (prop optionnelle `asTrigger`). DoD : lead mocké avec 3 raisons → popover les liste ; aucun changement de rendu pour les autres consommateurs de ScoreBadge (kanban/liste) ; vitest vert. (ROUTINE — M) (@model: sonnet) (@lane: LW2) (@after: LW14)
- [x] LW18 — **Bannières intelligentes : doublons, « déjà client ? », carte collée. @after LW14.** Dans IdentityRail : (1) bannière « N doublon(s) probable(s) » (données `getLeadDuplicates` + live `useDuplicateCheck`) ouvrant un `Dialog` avec le tableau actuel + « Fusionner ici » (logique `doMerge` portée telle quelle : confirmation, archivage jamais suppression) ; (2) bannière `client-match/` — « Ce contact correspond au client X » avec lien fiche client (GET paresseux à l'ouverture, silencieux si 404/vide) ; (3) bannière carte-collée VX237 « Répartir » (état venant du moteur, section Contact). Tones `ui/Badge`/`Card` warning/info, JAMAIS les hex `.lead-dup-warning` (dark-mode cassé, recon 04 §4). Files : `frontend/src/features/crm/workspace/IdentityRail.jsx`, `frontend/src/index.css` (`.lw-banner*`). DoD : mocks — 2 doublons → bannière + dialog listant 2 lignes ; client_match → lien vers `/crm/clients/:id` ; `grep -n "#fffbeb\|#92400e" ` sur les nouveaux fichiers = 0. (ROUTINE — L) (@model: sonnet) (@lane: LW2) (@after: LW14)

**LANE 3 — rail contexte (parallèle après LW10, fichiers disjoints des lanes 1/2) :**

- [x] LW19 — **`ContextRail` : les onglets Historique · Devis · Activités · Pièces avec compteurs. @after LW10.** Créer `ContextRail.jsx` : `ui/Tabs` (sémantique clavier/ARIA gratuite — remplace le rail maison sans ARIA, recon 04 §6), onglet par défaut Historique, badges de compte (devis.length, activités ouvertes, pièces), onglets minces Activités (= `ActivitiesPanel` existant + bouton « Appliquer un plan » → PlanActiviteDialog) et Pièces (= `AttachmentsPanel` existant, hooks `a.att-name` conservés), mémorisation de l'onglet actif par session. En création : rail masqué (rien à contextualiser). Files : `frontend/src/features/crm/workspace/ContextRail.jsx` (nouveau), `frontend/src/index.css` (`.lw-context*`). DoD : navigation clavier entre onglets (flèches) fonctionne ; badges corrects sur mocks ; `.act-form`/`.act-list`/`a.att-name` toujours présents dans le DOM des onglets. (ROUTINE — M) (@model: sonnet) (@lane: LW3) (@after: LW10)
- [x] LW20 — **`TimelineTab` : le chatter devient le fil unique — filtre, épingle, parcours multi-touch. @after LW19.** Créer `TimelineTab.jsx` : en-tête compact « Premier contact · Dernier contact · N touches » depuis `points-contact/` (GET paresseux, silencieux si vide — richesse FG204 jamais surfacée) ; filtre par type (Tous/Notes/Appels/E-mails/Devis/Système) persisté (pattern Attio recon 03 #8) ; notes ÉPINGLÉES en tête hors chronologie avec nom de l'épingleur (backend LW29) + action épingler/désépingler au survol ; `ChatterTimeline` (composant existant, INCHANGÉ dans son rendu) + composer actuel porté tel quel : input Enter-pour-poster, pièce jointe VX111, `CallLogPopover` « Journaliser », erreurs jamais avalées. L'état du composer vient du MOTEUR (`state.composer`) — la note ne peut plus fuiter entre leads. Files : `frontend/src/features/crm/workspace/TimelineTab.jsx` (nouveau), `frontend/src/components/ChatterTimeline.jsx` (prop optionnelle `pinned`/`onTogglePin`, additive). DoD : filtre « Appels » ne montre que kind appel/email ; note épinglée mockée rendue en tête avec icône 📌 ; composer poste et vide via le moteur ; vitest vert. (ROUTINE — L) (@model: sonnet) (@lane: LW3) (@after: LW19)
- [x] LW21 — **`DevisTab` : la chaîne document en cartes + le CTA devis-auto qui dit ce qui manque. @after LW19.** Créer `DevisTab.jsx` : carte par devis (référence, `StatusPill` statut devis, total TTC en `.num`, date, option acceptée) avec actions existantes « Générer la facture » / « Créer le chantier » (logique A4 portée : busy par id, messages, refresh par le moteur) et lien d'ouverture LeadDevisPanel (modes view/edit — `data-testid="lead-devis-panel"` conservé) ; en tête le CTA « Devis automatique » : si `devis_auto.pret` → bouton `--primary` + menu (remise/onepage/premium/édition — ouvre le MÊME LeadDevisPanel, règle #4 : aucun nouveau chemin PDF), sinon la LISTE des champs manquants de `devis_auto` en liens qui sautent-et-focus le champ correspondant du centre (richesse backend enfin actionnable) ; mini-chaîne `DocumentStageTrack` par carte devis acceptée (devis→facture→chantier — couche DOCUMENT, jamais le funnel lead). Files : `frontend/src/features/crm/workspace/DevisTab.jsx` (nouveau). DoD : mock non-prêt → 2 champs manquants cliquables qui scrollent le centre ; mock accepté → actions facture/chantier visibles ; aucun import depuis quote_engine ; vitest vert. (ROUTINE — L) (@model: sonnet) (@lane: LW3) (@after: LW19)
- [x] LW22 — **WhatsApp dans DevisTab : multi-sélection, FR/Darija, aperçu — l'état dans le moteur. @after LW21.** Porter la barre d'envoi (LeadForm.jsx:1737-1801, 383-411) dans DevisTab : cases de sélection multi-devis, bascule FR/Darija pré-réglée sur `langue_preferee`, bouton armé UNIQUEMENT si `normalizeMaPhone` valide (LW7) ET sélection non vide, POST `whatsapp-devis/` → Dialog d'aperçu serveur (message + liens tokenisés) → `wa.me` ; TOUT l'état (`wa.selected/langue/preview`) vit dans `useLeadDraft` keyé par lead — l'envoi du mauvais document au client (P1#2) est impossible par construction. Files : `frontend/src/features/crm/workspace/DevisTab.jsx`. DoD : test — sélection sur lead A puis LOAD_LEAD(B) → sélection vide ; numéro invalide → bouton désactivé avec hint « Numéro invalide » ; aperçu mocké s'affiche avant wa.me. (ROUTINE — M) (@model: sonnet) (@lane: LW3) (@after: LW21)

**LANE 4 — clavier & vitesse perçue (parallèle après LW10) :**

- [x] LW23 — **Raccourcis propres : registre exact, « d » réparé, « n » pour noter. @after LW10.** Recâbler `useFocusedRecordShortcuts('leadForm', …)` dans LeadWorkspace : `a` archiver (via leaveGuard — LW4 structurel), `d` = focus du picker Responsable (le libellé du registre disait « déléguer » mais le code sautait à la section — mismatch recon 01 §6.5 : on répare le COMPORTEMENT vers le libellé), `n` = basculer sur l'onglet Historique + focus composer (nouveau, registre + cheatsheet « ? » mis à jour), 1-4 = StageControl (LW16). Les DEUX effets clavier (J/K + registre) reçoivent de vrais dep arrays (fini le re-bind à chaque rendu). Files : `frontend/src/features/crm/workspace/LeadWorkspace.jsx`, `frontend/src/providers/focusedRecordShortcuts.jsx` (libellés + entrée `n`). DoD : « ? » liste a/d/n/1-4 avec les bons libellés ; `d` focus l'AssigneePicker ; aucun addEventListener sans cleanup ni sans deps (`grep -n "addEventListener" ` + revue). (ROUTINE — M) (@model: sonnet) (@lane: LW4) (@after: LW10)
- [x] LW24 — **Pré-chargement des voisins de file : J/K devient instantané. @after LW10.** Dans LeadWorkspace, au repos (`requestIdleCallback`, repli setTimeout 300ms) pré-charger `getLead` des leads précédent/suivant de `leadsQueue` dans un petit cache Map(id→{data,at}) TTL 60s, consommé par LOAD_LEAD à la navigation (le GET frais repart quand même en arrière-plan et remplace — le cache n'est qu'un premier rendu instantané, la garde `res.id===leadId` du moteur s'applique). Le truc de vitesse Linear adapté à l'échelle 2 utilisateurs (recon 03 #24) — zéro dépendance. Files : `frontend/src/features/crm/workspace/LeadWorkspace.jsx`, `frontend/src/features/crm/workspace/useLeadDraft.js`. DoD : test — après ouverture de A avec file [A,B], `getLead(B)` a été appelé en idle ; naviguer vers B rend immédiatement puis re-fetch ; pas de fetch sans file. (ROUTINE — M) (@model: sonnet) (@lane: LW4) (@after: LW10)
- [x] LW25 — **Skeleton à l'ouverture, en forme de la vraie grille. @after LW10.** À l'ouverture (liste passe un objet de LIGNE partiel ; la route détail fetch) : GET complet systématique via le moteur, et pendant `useDelayedLoading` (300/500ms) un skeleton EN FORME (rail identité : SkeletonAvatar + 3 SkeletonLine ; centre : 2 SkeletonCard ; rail droit : SkeletonText) via `FadeSwap` — jamais de spinner nu (recon 03 #23). Les champs déjà connus de la ligne (nom, stage, ville) se rendent IMMÉDIATEMENT dans le bandeau/rail (progressive). Files : `frontend/src/features/crm/workspace/LeadWorkspace.jsx`, `frontend/src/index.css` (`.lw-skeleton*`). DoD : throttle réseau simulé (promesse retardée 800ms) → skeleton visible puis crossfade ; ouverture <300ms → aucun flash de skeleton ; vitest vert. (ROUTINE — M) (@model: sonnet) (@lane: LW4) (@after: LW10)
- [x] LW26 — **Palette de commandes : la fiche courante répond à ⌘K. @after LW23.** Enregistrer dans `providers/CommandPalette.jsx` (mécanisme `commandActions.js` existant) les actions contextuelles quand un LeadWorkspace est ouvert : « Envoyer les devis WhatsApp », « Devis automatique », « Archiver le lead », « Convertir en client », « Épingler une note » (focus composer), « Aller à la section … » (registre des sections) — via un petit contexte `window` event (`taqinor:lead-workspace-actions`) posé/retiré au mount/unmount, motif de l'événement `taqinor:command-palette` déjà en place. `pushRecentEntity` du lead à l'ouverture (déjà le patron Récents). Files : `frontend/src/providers/CommandPalette.jsx`, `frontend/src/lib/commandActions.js`, `frontend/src/features/crm/workspace/LeadWorkspace.jsx`. DoD : fiche ouverte → ⌘K liste les actions lead et « Aller à : Toiture » scrolle la section ; fiche fermée → actions absentes ; vitest palette vert. (ROUTINE — M) (@model: sonnet) (@lane: LW4) (@after: LW23)

**LANE 5 — backend additif (parallèle dès le début, indépendante des lanes UI) :**

- [x] LW27 — **Chatter : +11 champs métier journalisés (`TRACKED_FIELDS`).** L'allowlist (~36 champs, `apps/crm/activity.py`) ignore des champs de pilotage réel : ajouter `montant_estime, date_cloture_prevue, distributeur, project_timeline, financing_intent, facility_type, site_count, visit_window_part, visit_window_week, roof_age, ownership` (JAMAIS utm/meta_ad/custom_data — bruit système). Libellés FR propres dans le mapping d'affichage du diff. Files : `backend/django_core/apps/crm/activity.py`, `backend/django_core/apps/crm/tests/` (test du diff). DoD : PATCH `montant_estime` → une LeadActivity `modification` avec ancien→nouveau ; PATCH `utm_source` → aucune ; suite crm verte. (ROUTINE — S) (@model: haiku) (@lane: LW5)
- [x] LW28 — **`LeadActivity.pinned` : la note épinglée (UNE migration additive).** Ajouter `pinned = BooleanField(default=False)` + migration additive UNIQUE ; actions detail `POST /crm/leads/<id>/activites/<aid>/epingler/` et `desepingler/` (permission crm_modifier, company-scoped, 404 hors tenant) ; `LeadActivitySerializer` expose `pinned` ; `historique/` trie `(-pinned, -created_at)`. Révertable (`migrate crm <n-1>` propre). Files : `backend/django_core/apps/crm/models.py`, `backend/django_core/apps/crm/migrations/00XX_leadactivity_pinned.py` (nouveau), `backend/django_core/apps/crm/views.py`, `backend/django_core/apps/crm/serializers.py`, `backend/django_core/apps/crm/tests/test_chatter_pin.py` (nouveau). DoD : épingler puis GET historique → la note en tête avec `pinned:true` ; utilisateur d'une autre company → 404 ; migration reverse OK ; suite crm verte. (SCHEMA — M) (@model: sonnet) (@lane: LW5)
- [x] LW29 — **`pii_masked` : le masquage PII devient VISIBLE au lieu de silencieux.** `LeadSerializer` masque déjà tel/email/adresse/whatsapp/gps pour les utilisateurs sans `can_view_client_pii` (force read_only + null, drop silencieux au PATCH — recon 02 §6). Ajouter un champ calculé `pii_masked` (bool) au serializer pour que le front rende ces champs verrouillés-cadenas au lieu de laisser croire à une édition qui sera jetée. Files : `backend/django_core/apps/crm/serializers.py`, `backend/django_core/apps/crm/tests/` (test des deux profils). DoD : GET en utilisateur masqué → `pii_masked:true` + telephone null ; en admin → `false` + valeurs ; suite verte. (ROUTINE — S) (@model: sonnet) (@lane: LW5)
- [x] LW30 — **`chatter_recent` embarqué sur le GET détail : l'ouverture passe de 4 requêtes à 3.** Sur le RETRIEVE uniquement (jamais la liste — payload), embarquer `chatter_recent` = les 50 dernières LeadActivity (`select_related('user','attachment')`, tri LW28) via le contexte du serializer (`get_serializer_context` + SerializerMethodField conditionnel). Le front (TimelineTab) consomme ce champ au premier rendu et ne rappelle `historique/` que pour « voir plus »/rafraîchir. Files : `backend/django_core/apps/crm/views.py`, `backend/django_core/apps/crm/serializers.py`, `backend/django_core/apps/crm/tests/test_lead_detail_chatter.py` (nouveau), `frontend/src/features/crm/workspace/TimelineTab.jsx` (consommation). DoD : GET détail → `chatter_recent` présent (≤50, ordre épingle-d'abord) et `assertNumQueries` borné ; GET liste → champ ABSENT ; suites crm + vitest vertes. (ROUTINE — M) (@model: sonnet) (@lane: LW5) (@after: LW28)

**LANE 6 — polish, dark mode, responsive, a11y (parallèle après LW11) :**

- [x] LW31 — **Zéro hex dans la fenêtre : migration Badge/tokens des chips et bannières héritées. @after LW14, LW18.** Purger les couleurs cassées en dark (recon 04 §4) partout où le workspace les a remplacées : `.lead-devis-badge` (#fff), `.is-zero`, `.lead-archived-badge`, `.lead-dup-warning` (#fffbeb/#92400e), `.lead-dup-link`, `.lead-gps-link` (#2563eb → `var(--info)`), `.lead-bill-error` (#dc2626 → `var(--destructive)`) — les usages vivants migrent vers `ui/Badge`/tokens, les classes orphelines (`.lead-saved-confirm`, `.lead-nav-prevnext`, `.lead-nav-position` + celles rendues mortes par LW11-LW22) sont SUPPRIMÉES d'index.css. EXCEPTION CONTRACTUELLE : la CLASSE `.lead-devis-badge` reste posée sur le nouveau badge de compte devis (elle est un hook du spec CI-GATED `devis.spec.js` E4 : `expect('.lead-devis-badge').toContainText(/N devis/)`) — seul son STYLING hex meurt, restylé tokens/Badge sous le même nom de classe, et le badge continue d'afficher « N devis ». Files : `frontend/src/index.css` (blocs 1462-1510, 3823-3965). DoD : `grep -n "lead-dup-warning\|lead-gps-link\|lead-bill-error" frontend/src` = 0 côté JSX ; `.lead-devis-badge` présent dans le workspace ET sans hex dans index.css ; bloc `.lw-*` et sections lead restantes sans hex (`grep "#[0-9a-f]\{6\}"` = 0 sur ces plages) ; bascule dark visuellement propre. (ROUTINE — M) (@model: sonnet) (@lane: LW6) (@after: LW14, LW18)
- [x] LW32 — **Un seul Avatar : `components/Avatar.jsx` → `ui/Avatar` + `--owner-color-1..10` sur les surfaces lead. @after LW14.** Le vieux `components/Avatar.jsx` (palette 15 hex inline, recon 04 §1) est remplacé par `ui/Avatar` (Radix, tokenisé, `initials()`) dans TOUTES les surfaces de la fenêtre lead (bandeau, IdentityRail, AssigneePicker s'il l'utilise, ChatterTimeline si concerné) avec la couleur stable par owner via `--owner-color-{1..10}` (hash id → slot). Les AUTRES écrans consommateurs restent inchangés (migration hors périmètre — vérifier `grep -rn "components/Avatar" frontend/src` et ne toucher que les fichiers lead/workspace). Files : `frontend/src/features/crm/workspace/*.jsx` (usages), `frontend/src/components/AssigneePicker.jsx` (si import). DoD : `grep -rn "components/Avatar" frontend/src/features/crm/workspace` = 0 ; hooks `.ap-*` intacts ; deux owners différents → deux slots de couleur stables. (ROUTINE — M) (@model: sonnet) (@lane: LW6) (@after: LW14)
- [x] LW33 — **Rythme, motion et micro-feedback : la passe « premium » du workspace. @after LW11, LW19.** Une passe unique sur le bloc `.lw-*` : espacement grille 8px partout (gap-2/3/4 seulement), titres/labels sur l'échelle `--text-*` stricte (h2 nom, h3 sections, small labels), montants/kWc en `.num tabular-nums`, ombres = `shadow-card` au repos (jamais flottant) ; motion fast-in/slow-out (`--motion-fast` entrée / `--motion-base` sortie, `--ease-standard`), transitions UNIQUEMENT transform/opacity, `field-saved-pulse` branché sur chaque confirmation d'autosave, hover des cartes devis révélant les actions secondaires (`opacity-0 group-hover:opacity-100`, sans reflow), `prefers-reduced-motion` vérifié (les tokens zèrent déjà — ne rien réanimer). Files : `frontend/src/index.css` (bloc `.lw-*`), `frontend/src/features/crm/workspace/*.jsx` (classes). DoD : `grep -n "transition.*width\|transition.*height\|transition.*margin" ` sur le bloc `.lw-*` = 0 ; capture clair/sombre d'une fiche complète ; revue visuelle self-QA avant présentation. (ROUTINE — L) (@model: sonnet) (@lane: LW6) (@after: LW11, LW19)
- [x] LW34 — **Responsive vrai : 768-1024 à 2 colonnes + Sheet contexte, mobile à barre-pouce. @after LW11, LW19.** 768-1024px : grille 2 colonnes (rail identité 240px + centre), rail contexte accessible par bouton « Contexte » du bandeau ouvrant un `Sheet side="right"` (patron LeadDevisPanel) ; le breakpoint UNIQUE devient 768 partout (la bande morte 721-767px de `.lead-form-layout` à 720px disparaît, recon 04 §5). Mobile <768 : Sheet bas pleine hauteur, ordre bande identité compacte → sections accordéon → onglets contexte, barre d'actions POUCE sticky bas safe-area (Appeler · WhatsApp · Note), footer création via `FormActions` sticky, `useKeyboardAwareScroll` re-branché sur le conteneur scrollable du centre. Files : `frontend/src/index.css` (media queries `.lw-*`), `frontend/src/features/crm/workspace/LeadWorkspace.jsx`, `frontend/src/features/crm/workspace/ContextRail.jsx`. DoD : `grep -n "720px" frontend/src/index.css` ne matche plus aucune règle lead ; à 800×900 le rail contexte s'ouvre en Sheet ; à 375×812 la barre-pouce est visible et le clavier ne masque pas le champ actif. (ROUTINE — L) (@model: sonnet) (@lane: LW6) (@after: LW11, LW19)
- [x] LW35 — **A11y : la nav de sections et les onglets parlent aux lecteurs d'écran. @after LW11, LW19.** Nav-chips du centre : `aria-current` sur la section active (le rail actuel n'a AUCUN état accessible, recon 04 §7), focus visible `--focus-ring`, ordre de tabulation bandeau→rail→centre→contexte ; onglets = `ui/Tabs` (déjà conforme) ; toutes les IconButton avec `label` ; contraste AA vérifié sur les paires critiques (StatusPill sur `--card` sombre, liens info/destructive) ; `aria-controls` du disclosure AppointmentBooker comblé (flag VX193 en commentaire L245-246). Files : `frontend/src/features/crm/workspace/SectionsPane.jsx`, `frontend/src/features/crm/workspace/ContextRail.jsx`, `frontend/src/pages/crm/leads/AppointmentBooker.jsx` (aria-controls). DoD : axe-core (vitest-axe si dispo, sinon revue manuelle documentée) sans violation critique sur le workspace monté ; `grep -n "aria-current" SectionsPane.jsx` ≥ 1. (ROUTINE — M) (@model: sonnet) (@lane: LW6) (@after: LW11, LW19)
- [x] LW36 — **AppointmentBooker sort de l'inline : 30 blocs de styles → tokens/kit. @after LW6.** Le satellite (embarqué par SectionVisite) est ENTIÈREMENT inline (117-309 : px bruts, radius 6/8/10 — recon 04 §2) : migrer vers classes `.lw-booker*` (index.css, tokens) + primitives kit (Button, Input, DatePicker/TimePicker existants si compatibles sans changement de comportement), aucune modification de logique (LW6 a déjà traité cancel/form). Files : `frontend/src/pages/crm/leads/AppointmentBooker.jsx`, `frontend/src/index.css` (`.lw-booker*`). DoD : `grep -c "style={{" frontend/src/pages/crm/leads/AppointmentBooker.jsx` ≤ 3 ; rendu identique clair/sombre ; e2e sélecteurs booker inchangés. (ROUTINE — M) (@model: sonnet) (@lane: LW6) (@after: LW6)

**LANE 7 — tests & e2e (ferme le groupe, @after les lanes UI) :**

- [x] LW37 — **Le harnais unitaire migre vers LeadWorkspace : les 12 suites existantes + le moteur sous adversité. @after LW13, LW16, LW20, LW22.** Porter les suites listées au recon 01 §7 (LeadForm.test.jsx, VX89ResponsiveDialog, SummaryBar→IdentityRail, ReadinessChips, ChatterActivities, UnifiedTimeline, NTMKT11, VX111, VX224BurstSession, VX249, VX45) sur le nouveau composant (imports + sélecteurs, sémantique des assertions CONSERVÉE), et ajouter les tests d'adversité du moteur en RTL : autosave blur → PATCH partiel des seules clés dirty ; écho canonisé téléphone re-hydraté (jamais l'optimiste) ; échec réseau → draft intact + bandeau Réessayer ; PII masqué → champs verrouillés jamais PATCHés ; SIGNED via StageControl → SigneDialog sans PATCH direct. Files : `frontend/src/pages/crm/*.test.jsx` → `frontend/src/features/crm/workspace/*.test.jsx` (déplacés/adaptés), `frontend/src/features/crm/workspace/LeadWorkspace.test.jsx` (nouveau). DoD : `npm run test:unit` vert ; `node --test "src/**/*.test.mjs"` vert ; aucune suite orpheline ne référence l'ancien chemin (`grep -rn "pages/crm/LeadForm" frontend/src --include=*.test.*` = 0). (ROUTINE — XL) (@model: sonnet) (@lane: LW7) (@after: LW13, LW16, LW20, LW22)
- [x] LW38 — **Régression anti-perte : la suite « rafale » qui verrouille les 4 bugs pour toujours. @after LW37.** Une suite dédiée `burstSafety.test.jsx` qui rejoue les 4 scénarios de perte du recon 05 sur le NOUVEAU moteur : (1) taper + raccourci d'étape → édition toujours dirty et sauvée au flush ; (2) sélection WhatsApp + J → sélection vide sur le lead B ; (3) « a » archiver avec éditions → flush d'abord, rien de perdu ; (4) note tapée + navigation → composer vide sur B, brouillon de A restauré au retour (miroir sessionStorage). Plus : réponse lente de A arrivant après navigation vers B → JETÉE (garde id). Files : `frontend/src/features/crm/workspace/burstSafety.test.jsx` (nouveau). DoD : les 5 scénarios verts ; chacun échoue si on commente la garde correspondante de draftCore (vérifié une fois en revue). (ROUTINE — L) (@model: opus) (@lane: LW7) (@after: LW37)
- [x] LW39 — **Contrat e2e mis à jour DÉLIBÉRÉMENT : la spec et le DOM bougent dans la même tâche. @after LW37.** Appliquer les décisions du blueprint au couple DOM+spec : CONSERVÉS (`#lf-nom`, `.modal-title` « Lead — »/« Nouveau lead », `.modal-close`, `.ap-*`, `.act-*`, `a.att-name`, `.ldp-*` dont `.ldp-header .modal-close`, `data-testid="lead-devis-panel"`, `.lead-devis-badge` avec texte « N devis » (hook du CI-GATED devis.spec E4), sélecteurs SigneDialog, « + Nouveau lead », « Créer le lead », /Devis automatique/, placeholder `ex: 650` du champ facture hiver dans SectionEnergie — le helper `createLead` du CI-GATED E4/MB6 le remplit) — vérifier leur présence dans le nouveau DOM ; MIS À JOUR dans `frontend/e2e/leads.spec.js` (+ helpers partagés `frontend/e2e/helpers*.js` : `createLead`/`openLead`/`generateAutoDevis` relus ligne à ligne contre le nouveau DOM) : « Mettre à jour » → « Enregistrer », `.lead-summary-bar`/testid → `data-testid="lw-identity-rail"`, `.lead-bill-view`/`.lead-bill-input` → champ `#lf-facture-hiver` de SectionEnergie, `.form-group hasText 'Responsable'` → sélecteur par label stable. Les specs CI-GATED `devis.spec.js` E4 et `mobile.spec.js` MB6 (création lead sur iPhone) doivent passer SANS modification, ou leur mise à jour est faite ICI même. Lancer localement les specs leads+devis (`npx playwright test e2e/leads.spec.js e2e/devis.spec.js` contre le harnais E2E_PROXY) si l'environnement le permet, sinon revue ligne-à-ligne documentée dans le commit. Files : `frontend/e2e/leads.spec.js`, `frontend/e2e/activities.spec.js`, `frontend/e2e/attachments.spec.js`, `frontend/e2e/devis.spec.js` (si besoin), `frontend/e2e/helpers*.js`, `frontend/src/features/crm/workspace/*.jsx` (ids/testids manquants). DoD : `grep -n "lead-summary-bar\|Mettre à jour\|lead-bill-input" frontend/e2e` = 0 ; `grep -n "lf-nom" frontend/e2e` ≥ 1 ET présent dans SectionContact ; specs CI-gated (devis/health/mobile) inchangées. (ROUTINE — L) (@model: opus) (@lane: LW7) (@after: LW37)
- [x] LW40 — **Démontage final : LeadForm.jsx supprimé, cartes et plans à jour. @after LW39.** Quand LW13→LW39 sont verts : supprimer l'adaptateur `pages/crm/LeadForm.jsx` et pointer les derniers imports directement sur `features/crm/workspace/LeadWorkspace` ; purger d'index.css les dernières classes `.lead-*` sans usage (`grep` croisé JSX/CSS) ; régénérer la section CRM de `docs/CODEMAP.md` (§4 : nouveaux fichiers workspace, route détail) + `python scripts/codemap_fingerprint.py --write` dans le même commit. Files : `frontend/src/pages/crm/LeadForm.jsx` (supprimé), `frontend/src/index.css`, `docs/CODEMAP.md`. DoD : `git grep -n "pages/crm/LeadForm"` = 0 ; `npm run lint` + vitest verts ; `python scripts/codemap_fingerprint.py --check` vert. (ROUTINE — M) (@model: sonnet) (@lane: LW7) (@after: LW39)

### Groupe LB — Leads Board & Liste (la première page du matin) : shell borné, board qui tient dans l'écran, carte 4 zones, liste épinglée, KPI-filtres (synthèse design 5 recons + Fable, fondateur 2026-07-19)

*Provenance : demande du fondateur — « the first page that has all the leads needs a lots of
work… when I want to scroll right I need to go all the way down… make it reallyyyyy the best ».
Reda et Meriem OUVRENT leur journée sur cette page (kanban/liste/calendrier/carte/graphique/
prévision). Cinq recons parallèles (anatomie, recherche best-in-class, chasse aux bugs P0-P3,
plans+contrat e2e, audit CSS) puis une synthèse Fable. Le blueprint complet — décisions D1-D6,
contrat CSS exact de la chaîne de hauteur, spec de la carte, adjudication liste
(refit sur place, PAS d'adoption du moteur ui/datatable), invariants d'état I1-I9, carte des
fichiers par lane — est LA référence de chaque tâche : `scratchpad/design2/blueprint.md`
(recopié dans `docs/design/leads-board-blueprint.md` en LB1). Verdicts : (D1) shell `.lp-page`
borné view-aware via `data-view` (miroir du pattern `.lw-page`), kanban/prévision/liste en
pleine largeur, scrolleur par vue ; (D2) colonnes à scroll interne + headers épinglés par
construction, autoScroll dnd-kit, drag-to-pan, repli persisté, COLD réactivable (le serveur
`_rang_funnel` le fait DÉJÀ — fix 100 % client) ; (D3) carte plafonnée nom→valeur→action→âge,
rotting via `workspace/rotting.js`, menu •••, tags tokenisés ; (D4) liste refittée sur place en
volant `useColumnPrefs`+`ColumnManager` au moteur ; (D5) KPI-tuiles=filtres, URL partageable,
bulk flottant ; (D6) plus jamais de refetch intégral après un PATCH mono-lead, tout passe par
le store, mémo stable partout.*

> **Contraintes (chaque tâche LB).** Zéro nouvelle dépendance npm (dnd-kit/Recharts/Leaflet déjà
> là). Clés d'étape uniquement via `features/crm/stages.js` (miroir STAGES.py, règle #2) — jamais
> une seconde liste, jamais une seconde table de probabilités (importer `STAGE_PROBABILITY` de
> KanbanView). Ne JAMAIS toucher `apps/ventes/quote_engine/` (règle #4). Tokens sémantiques
> uniquement — un hex n'a le droit de naître QUE dans `design/tokens.css` (clair ET sombre, AA).
> Contrat e2e conservé ou mis à jour DANS la même tâche : `article.kb-card`, `.kb-card-name`,
> `tr.lv-row`, `.lv-lead-name`, `.ie-cell`, `select.ie-input`, 'Vue kanban'/'Vue liste', les 6
> libellés d'étape, '+ Nouveau lead', '✓ Enregistré', « Plus d'actions sur la ligne » — specs
> CI-gated `leads.spec.js`/`doublons.spec.js`/`datatable-breakpoint.spec.js` + axe VX71 (toute
> nouvelle commande est nommée). Les goldens visuels `leads-kanban` clair+sombre (release-verify)
> CHANGENT : régénération délibérée EN FIN DE BATCH (LB34), jamais un red surprise. UI en
> français, `prefers-reduced-motion` respecté, cibles tactiles ≥44px. Le CSS nouveau vit dans un
> bloc append-only `.lp-*`/`.kb-*`/`.lv-*` d'index.css. Mobile : swipe ☎/💬 et card-stack
> conservés. Chaque tâche est autonome pour un agent worktree : le blueprint
> (`docs/design/leads-board-blueprint.md`) + le corps de la tâche suffisent.

**LANE 0 — urgence (UN agent, séquentiel, à bâtir EN PREMIER : le fix P0 fondateur + les bugs
P1 recon-03 reçoivent leur correctif sur place MAINTENANT — chacun ≤ petit diff — et les lanes
suivantes bâtissent dessus ; cette lane est propriétaire de LeadsPage.jsx/KanbanView.jsx/
ListView.jsx/stages.js/crmSlice.js pendant sa durée) :**

- [x] LB1 — **Recopier le blueprint dans le repo.** Copier `scratchpad/design2/blueprint.md` vers
  `docs/design/leads-board-blueprint.md` tel quel (référence de toutes les tâches LB, comme
  LW9 l'a fait pour la fenêtre lead). Files : `docs/design/leads-board-blueprint.md` (nouveau).
  DoD : le fichier existe, lisible, lié depuis le corps des tâches. (ROUTINE — S) (@model: haiku) (@lane: LB0)
- [x] LB2 — **P0 fondateur : le board tient dans l'écran — chaîne de hauteur `.lp-page` +
  `data-view`.** Cause racine vérifiée (recon2-03 §P0) : la chaîne bornée meurt à `.route-fade`
  (hauteur auto) ; `.kb-board{height:100%}` se résout en AUTO, `.kb-col-body{overflow-y}` ne
  déborde JAMAIS, la page scrolle 8 649px et la scrollbar horizontale gît sous le fold.
  Appliquer le contrat CSS EXACT du blueprint D1 : `.layout-content > .route-fade:has(> .lp-page)
  {height:100%}` (sans toucher la règle `.lw-page` voisine) ; `.lp-page` flex column
  height:100%/min-height:0 ; `.lp-page > :not(.lp-view-area){flex:0 0 auto}` ; `.lp-view-area`
  flex:1/min-height:0, scrolleur vertical par défaut, `overflow:hidden` pour
  kanban/prevision/liste via `data-view` (1 ligne JSX : `data-view={view}` sur la racine) ;
  `.kb-board` passe de height:100% à flex:1/min-height:0 ; `.kb-col` flex column min-height:0 ;
  `.kb-col-body` flex:1/overflow-y:auto ; `.lv-wrap` flex:1/overflow:auto ; pleine largeur
  (`max-width:none`) pour les 3 vues denses ; scrollbars fines TOUJOURS visibles tokenisées ;
  combler le gap responsive 769-899px (`.kb-col` en clamp). ForecastView (`.kb-board.fv-board`)
  hérite — vérifier. Files : `frontend/src/index.css`,
  `frontend/src/pages/crm/leads/LeadsPage.jsx`. DoD : en 1280×720 avec 60+ leads, le shell ne
  scrolle pas en vue kanban, la scrollbar horizontale du board est visible SANS scroller, chaque
  colonne scrolle en interne, shift+molette pan le board ; en vue liste/calendrier/graphique le
  contenu scrolle sous des filtres épinglés ; mobile 375×812 : colonnes 85vw à scroll interne,
  tabbar intacte. (ROUTINE — M) (@model: sonnet) (@lane: LB0)
- [x] LB3 — **P1 : le StageMover ne ment plus « Signé ✓ Enregistré » (interception honnête).**
  Bug recon2-03 #2 : `onInlineSave` intercepte CONVERSION_STAGE et renvoie `Promise.resolve()`
  (faux succès) → `useOptimisticSave` garde 'SIGNED' optimiste + « Enregistré » alors que seul le
  dialogue s'est ouvert. Fix (blueprint I3) : nouveau module
  `frontend/src/pages/crm/leads/signeIntercept.js` (sentinelle `SIGNE_INTERCEPT` +
  `isSigneIntercept(err)`) ; `onInlineSave` renvoie `Promise.reject(SIGNE_INTERCEPT)` après avoir
  ouvert SigneDialog ; l'`onError` du StageMover avale la sentinelle sans toast (les vraies
  erreurs toastent toujours) ; InlineEdit (liste) restaure déjà sur rejet — vérifier qu'aucun
  toast parasite. Mettre à jour KanbanView.test. Files :
  `frontend/src/pages/crm/leads/signeIntercept.js` (nouveau),
  `frontend/src/pages/crm/leads/LeadsPage.jsx`,
  `frontend/src/pages/crm/leads/views/KanbanView.jsx` + tests. DoD : sélectionner « Signé » dans
  le StageMover ouvre SigneDialog et le select REVIENT à l'étape réelle sans toast d'erreur ;
  annuler le dialogue ne laisse aucun « Enregistré » ; confirmer déplace réellement le lead.
  (ROUTINE — S) (@model: sonnet) (@lane: LB0)
- [x] LB4 — **P1 : un lead Froid se réactive par drag (rang funnel client aligné serveur).**
  Bug recon2-03 #7 : `stageRank = PIPELINE_STAGES.indexOf` classe COLD au rang 5 (le plus haut) →
  tout drag COLD→actif est bloqué « recul ». Le serveur fait DÉJÀ le bon choix
  (`apps/crm/services.py _rang_funnel('COLD') == -1` ; `_bulk_stage_allowed` : Froid→active =
  réactivation OK, →Froid = parking OK depuis partout, sinon avant-seulement) — AUCUNE tâche
  backend. Fix : ajouter à `stages.js` `funnelRank(stage)` (COLD → -1) et
  `isStageMoveAllowed(from, to)` miroir byte-à-byte de `_bulk_stage_allowed` (+ tests node) ;
  l'utiliser dans `handleDragEnd` de KanbanView (à la place du stageRank local), dans les
  `<option>` du StageMover (options interdites `disabled` — le chemin clavier retrouve le MÊME
  garde, bug #8) et dans les options stage de l'InlineEdit liste. Entrer dans SIGNED continue de
  passer par SigneDialog quel que soit le chemin. Files : `frontend/src/features/crm/stages.js`
  (+ test node), `frontend/src/pages/crm/leads/views/KanbanView.jsx`,
  `frontend/src/pages/crm/leads/views/ListView.jsx`. DoD : drag COLD→CONTACTED déplace la carte
  (plus de bannière recul) ; drag FOLLOW_UP→NEW toujours bloqué ; n'importe où→COLD autorisé ;
  les options interdites du select sont grisées ; tests verts. (ROUTINE — S) (@model: sonnet) (@lane: LB0)
- [x] LB5 — **P1 : « ✗ Perdu » depuis une carte met l'UI à jour (chemin Redux).** Bug recon2-03
  #3 : `confirmPerdu` de LeadCard appelle `crmApi.updateLead` en DIRECT (contourne le store) puis
  `onChanged?.()` que KanbanView/ForecastView ne passent JAMAIS ; aucun polling n'existe (les
  commentaires qui l'affirment MENTENT). Fix (blueprint I2) : callback stable
  `onMarkPerdu(lead, motif)` dans LeadsPage (dispatch `updateLead({perdu:true, motif_perte})`,
  PAS de refetch — `updateLead.fulfilled` patche le store), passé via viewProps ; LeadCard et
  ListView l'utilisent ; supprimer la prop fantôme `onChanged` et les commentaires « polling »
  mensongers ; toastError en échec. Files : `frontend/src/pages/crm/leads/LeadsPage.jsx`,
  `frontend/src/pages/crm/leads/views/LeadCard.jsx`,
  `frontend/src/pages/crm/leads/views/ListView.jsx`. DoD : marquer perdu depuis une carte kanban
  grise la carte IMMÉDIATEMENT (style perdu) sans refetch réseau intégral ; échec réseau → toast
  FR + état intact. (ROUTINE — S) (@model: sonnet) (@lane: LB0)
- [x] LB6 — **P1 : mémo réparé — une frappe ne re-rend plus tout le board.** Bug recon2-03 #4 :
  `reassign`/`onToggleSelect`/`onPlanifierRelance`/`onInlineSave`/`onToggleAll` sont des closures
  fraîches (VX187 n'en avait mémoïsé que 3), `viewProps` est un objet neuf à chaque rendu,
  `DraggableCard` n'est pas mémoïsé ; côté liste, l'état du popover perdu
  (`perduMotif`/`perduTarget`/`perduBusy`) est passé à CHAQUE ligne → taper un motif re-rend la
  table entière. Fix (blueprint I4) : `useCallback` sur TOUS les callbacks de viewProps,
  `useMemo` sur viewProps, `memo(DraggableCard)`, et en liste UNE seule instance de popover au
  niveau table — les lignes ne reçoivent que des primitives + callbacks stables. Ajouter un test
  de sonde léger (rendu compté : une frappe de recherche ne re-rend aucune LeadCard). Files :
  `frontend/src/pages/crm/leads/LeadsPage.jsx`,
  `frontend/src/pages/crm/leads/views/KanbanView.jsx`,
  `frontend/src/pages/crm/leads/views/ListView.jsx` + tests. DoD : sonde verte ; profiler React :
  frappe dans la recherche → 0 re-rendu de carte ; taper un motif perdu → seule la ligne cible se
  re-rend. (ROUTINE — M) (@model: sonnet) (@lane: LB0)
- [x] LB7 — **P1 : plus de refetch intégral après un PATCH mono-lead + fin des catch muets +
  garde d'obsolescence.** Bugs recon2-03 #5/#10/#11. Fix (blueprint I1/I6/I8) : `onInlineSave`
  perd son `.then(refetch)` et `reassign` son `refetch()` (`updateLead.fulfilled` remplace déjà
  le lead au complet — score/stage_since_days/devis inclus) ; le refetch intégral ne reste que
  pour bulk/import/merge/Signé confirmé/création/filtre `archived` ; archive/restaurer de la
  liste passent par les thunks `archiveLead`/`restoreLead` (déjà réduits) au lieu de crmApi
  direct ; `toastError` FR sur reassign/exports/archive/restore ; `crmSlice` trace le requestId
  du dernier `fetchLeads` et ignore un `fulfilled` obsolète (même motif que `leadUpdateSeq`).
  Files : `frontend/src/pages/crm/leads/LeadsPage.jsx`,
  `frontend/src/pages/crm/leads/views/ListView.jsx`,
  `frontend/src/features/crm/store/crmSlice.js` + tests. DoD : une édition inline d'un champ ne
  déclenche AUCUN GET /leads (onglet réseau) et la valeur affichée vient du payload PATCH ; un
  refetch lent qui répond après un drag n'écrase pas l'étape optimiste ; chaque échec toaste.
  (ROUTINE — M) (@model: sonnet) (@lane: LB0)
- [x] LB8 — **P2 : la sélection est élaguée contre la liste FILTRÉE.** Bug recon2-03 #6 :
  `pruneSelection` élague contre TOUS les leads → un lead sélectionné puis masqué par un filtre
  reste bulk-actionnable en invisible. Fix (blueprint I5) : `visibleSelected` se calcule contre
  `filtered.map(l => l.id)` ; la barre bulk affiche le compte visible. Files :
  `frontend/src/pages/crm/leads/LeadsPage.jsx`. DoD : sélectionner 3 leads, filtrer pour n'en
  voir qu'1 → la barre dit 1 et le bulk n'agit que sur lui ; retirer le filtre → les 3
  redeviennent sélectionnés. (ROUTINE — S) (@model: haiku) (@lane: LB0)

**LANE 1 — board & colonnes (UN agent, séquentiel — fichiers : KanbanView.jsx,
features/kanban/*, index.css `.kb-*`) :**

- [x] LB9 — **Colonnes : en-têtes riches épinglés, régions nommées, colonne vide = zone de
  drop.** Les en-têtes sont épinglés par construction depuis LB2 (hors du corps scrollant).
  Nouvelle mise en page (blueprint D2) : rangée titre + compteur (visible même à 0) ; rangée
  `total MAD · Prév. pondéré` (tooltip expliquant la pondération STAGE_PROBABILITY — importée,
  jamais re-déclarée). Chaque colonne devient `<section aria-label="Étape X — N leads">` ;
  chaque `.kb-col-body` reçoit `tabindex="0"` + aria-label (zone de scroll atteignable clavier).
  Colonne vide : remplacer « Aucun lead » par une zone en pointillés « Déposer un lead ici »
  (surbrillance à l'over) ; empty state GLOBAL (0 lead) : EmptyState coach avec CTA « + Nouveau
  lead » / « Importer » ; 0 résultat filtré : CTA « Effacer les filtres » réel. Files :
  `frontend/src/pages/crm/leads/views/KanbanView.jsx`, `frontend/src/index.css` + tests
  (VX147EmptyState mis à jour ici). DoD : axe vert (régions nommées), tab atteint chaque corps de
  colonne, drop sur colonne vide fonctionne, empty states coach rendus. (ROUTINE — M)
  (@model: sonnet) (@lane: LB1) (@after: LB8)
- [x] LB10 — **Repli de colonne persisté (rail droppable).** Chevron labellisé dans l'en-tête →
  colonne repliée = rail vertical 44px (libellé pivoté `writing-mode`, compteur, accent étape)
  qui RESTE une zone droppable (surbrillance + drop autorisé) ; re-clic déplie. Persistance
  `localStorage['taqinor.leads.kanban.collapsed']` (tableau de clés d'étape, tolérant aux clés
  inconnues). Aucun repli par défaut. Files :
  `frontend/src/pages/crm/leads/views/KanbanView.jsx`, `frontend/src/index.css` + tests. DoD :
  replier « Froid » survit à un reload ; drag d'une carte sur le rail replié la dépose dans
  l'étape ; chevrons nommés (axe vert) ; reduced-motion sans animation. (ROUTINE — M)
  (@model: sonnet) (@lane: LB1) (@after: LB9)
- [x] LB11 — **autoScroll dnd-kit réglé + drag-to-pan sur l'espace vide.** L'autoScroll intégré
  de DndContext était inerte (aucun conteneur ne scrollait — LB2 l'a réveillé) : vérifier le
  comportement sur les DEUX axes imbriqués (board x, colonne y) et ne régler
  `autoScroll={{ thresholds: … }}` QUE si les défauts frottent — config, jamais de scroll maison
  pendant un drag. Nouveau hook `features/kanban/usePanScroll.js` (blueprint D2) : pointerdown
  bouton 0 sur le fond du board, ignore `closest('.kb-card, .kb-col-body, button, a, select,
  input, [role="button"]')`, seuil 4px, setPointerCapture, curseur grab/grabbing, inactif sur
  pointer coarse ; test node des prédicats purs. Files :
  `frontend/src/features/kanban/usePanScroll.js` (nouveau, + test),
  `frontend/src/pages/crm/leads/views/KanbanView.jsx`. DoD : tirer une carte vers le bord fait
  défiler board/colonne ; cliquer-tirer le fond du board le pan ; un clic simple sur une carte
  ouvre toujours la fiche (distance 6px intacte) ; le pan ne démarre jamais depuis une carte.
  (ROUTINE — M) (@model: sonnet) (@lane: LB1) (@after: LB10)
- [x] LB12 — **Restauration du focus après un drop (souris ET clavier).** Recon-05 a11y #4 : la
  carte re-parentée perd le focus vers `<body>`. Poser `data-lead-id` sur le nœud draggable ; à
  `onDragEnd` réussi (y compris chemin KeyboardSensor), `requestAnimationFrame` →
  `querySelector('[data-lead-id="N"]')?.focus()`. Les annonces FR existantes (kanbanA11y)
  continuent d'annoncer le drop. Files :
  `frontend/src/pages/crm/leads/views/KanbanView.jsx` + tests. DoD : drop clavier
  (Espace→flèches→Espace) → le focus est SUR la carte déplacée dans sa nouvelle colonne ;
  Échap annule et le focus reste sur la carte d'origine. (ROUTINE — S) (@model: sonnet)
  (@lane: LB1) (@after: LB11)

**LANE 2 — la carte (UN agent, séquentiel — fichiers : LeadCard.jsx, PerduPopover.jsx nouveau,
design/tokens.css, stages.js §tagColor, index.css `.kb-card*`) :**

- [x] LB13 — **Anatomie 4 zones de la carte (le visage du pipeline).** Rebâtir LeadCard selon le
  blueprint D3, contrat DOM conservé (`article.kb-card`, `.kb-card-name`) : tête = checkbox
  (opacity-0 → visible hover/focus-within/sélection active/`(hover:none)`) + nom + ScoreBadge ;
  valeur = `latestDevisTotal` sinon « est. montant_estime » + chip type d'installation ;
  UNE ligne d'action (précédence VX24 conservée : perdu > relance retard > ☎ rappel > devis
  expiré > next_activity > suggestion ; sur NEW non contacté, cette ligne EST le badge SLA
  premier-contact — le timer QX31 fusionne ici) ; pied = canal + ville + pill d'âge + avatar
  AssigneePicker. QUITTENT la face : liens tel/WA permanents (→ actions rapides révélées au
  hover, permanentes sur hover:none — LB15 y ajoute le menu), chips readiness (→ micro-icônes
  12px tooltipées), étoiles priorité, « Inactif N j »+horloge (→ pill d'âge), tags plafonnés
  2+« +N ». Plus AUCUN style inline. Mettre à jour les tests pinnés DANS cette tâche (VX24
  precedence, LeadCardFirstTouchTimer, ReadinessChips, LeadScore.vx221). Files :
  `frontend/src/pages/crm/leads/views/LeadCard.jsx`, `frontend/src/index.css` + tests. DoD :
  4 rangées max par carte, hiérarchie visuelle nette clair+sombre, aucun style inline, tous les
  tests carte verts, tel:/wa hrefs toujours présents au hover. (ROUTINE — L) (@model: opus)
  (@lane: LB2) (@after: LB8)
- [x] LB14 — **Rampe « rotting » sur la carte (réutilise workspace/rotting.js TEL QUEL).**
  `stage_since_days` est déjà dans le payload :
  `rottingLevel(days, thresholdsForIndex(PIPELINE_STAGES.indexOf(stage)))` →
  `data-rot="ok|warning|danger"` sur `article.kb-card`. Style : pill d'âge teintée
  (`--warning`/`--destructive`), liseré intérieur gauche 3px UNIQUEMENT en danger. Jamais de rot
  sur SIGNED/COLD (seuils null par construction) ni sur un lead perdu. Files :
  `frontend/src/pages/crm/leads/views/LeadCard.jsx`, `frontend/src/index.css` + tests. DoD : une
  carte QUOTE_SENT à 16 j est rouge, à 9 j ambre, à 3 j neutre ; SIGNED/COLD/perdu jamais
  teintés ; AA dans les deux thèmes. (ROUTINE — S) (@model: sonnet) (@lane: LB2) (@after: LB13)
- [x] LB15 — **Menu ••• au hover + PerduPopover PARTAGÉ (fin de la triplication).** Menu
  DropdownMenu révélé hover/focus (permanent sur hover:none), labellisé « Actions du lead » :
  Ouvrir · Planifier une relance · ⚡ Devis auto · ✗ Marquer perdu · Archiver — le bouton ✗
  20×20 quitte la face. Extraire le popover « Marquer perdu » (motif + datalist, dupliqué
  byte-à-byte LeadCard 389-417 / ListView 359-387) en
  `frontend/src/pages/crm/leads/PerduPopover.jsx` UNIQUE, branché sur `onMarkPerdu` (LB5) avec
  chargement paresseux des motifs UNE fois ; LeadCard l'adopte ici (ListView en LB21). Files :
  `frontend/src/pages/crm/leads/PerduPopover.jsx` (nouveau),
  `frontend/src/pages/crm/leads/views/LeadCard.jsx`, `frontend/src/index.css` + tests. DoD :
  toutes les actions accessibles clavier via le menu, marquer perdu depuis le menu met la carte
  à jour sans refetch, un seul composant perdu dans le code. (ROUTINE — M) (@model: sonnet)
  (@lane: LB2) (@after: LB14)
- [x] LB16 — **Tags tokenisés + token WhatsApp + tokens morts réparés.** Remplacer
  `TAG_PALETTE`/`TAG_TEXT` (20 hex, stages.js:85-91) par 10 paires `--tag-N-bg/--tag-N-fg`
  définies clair+sombre dans `design/tokens.css` ; `tagColor()` garde sa signature et renvoie
  `var(--tag-N-…)` (LeadCard ET ListView en profitent sans changement) ; hash déterministe
  conservé + test node. Nouveau token `--brand-whatsapp` (vert WhatsApp, clair+sombre — le seul
  lieu de naissance d'un hex) : le fond du swipe WA passe de `var(--color-info, #25D366)` (rendu
  BLEU — bug recon-05) à `var(--brand-whatsapp)` ; re-baser les 3 fallbacks morts
  `--color-*-muted` de LeadCard.jsx:477/484/491 + `.kb-call-nudge`/`.lv-call-nudge` sur des
  tokens réels. Files : `frontend/src/design/tokens.css`, `frontend/src/features/crm/stages.js`
  (+ test), `frontend/src/pages/crm/leads/views/LeadCard.jsx`, `frontend/src/index.css`. DoD :
  zéro hex dans stages.js/LeadCard ; l'action WhatsApp est VERTE dans les deux thèmes ; pastilles
  de tag AA clair+sombre. (ROUTINE — M) (@model: sonnet) (@lane: LB2) (@after: LB15)
- [x] LB17 — **Tactile + PII : cibles 44px, swipe inerte, cadenas PII.** Checkbox : zone de
  frappe ≥44×44 via padding (tue le sliver 16px horizontal — recon-05 touch) ; le menu •••
  (permanent au toucher) reçoit une cible 44px ; la bande swipe cachée passe en `inert`
  (l'aria-hidden actuel laisse les `<a>` tabbables) ; quand l'utilisateur n'a pas la permission
  PII (le serializer nullifie tel/whatsapp), remplacer les actions d'appel par un cadenas 12px
  tooltipé « Coordonnées masquées (permission PII) » — plus jamais un blanc muet. Mettre à jour
  SwipeAction tests. Files : `frontend/src/pages/crm/leads/views/LeadCard.jsx`,
  `frontend/src/index.css` + tests. DoD : toutes les cibles tactiles ≥44px (vérif inline styles
  battus) ; tab ne visite jamais la bande swipe cachée ; un compte sans PII voit le cadenas.
  (ROUTINE — M) (@model: sonnet) (@lane: LB2) (@after: LB16)

**LANE 3 — la liste (UN agent, séquentiel — fichiers : ListView.jsx, index.css `.lv-*` ;
DÉCISION D4 : refit sur place, on N'ADOPTE PAS le moteur ui/datatable — on lui vole
`useColumnPrefs` + `ColumnManager` en import direct) :**

- [x] LB18 — **Scrolleur unique + thead sticky + colonne nom sticky + colgroup.** Depuis LB2,
  `.lv-wrap` est LE scrolleur deux axes (un ancêtre overflow-x séparé casserait sticky — c'est
  voulu) : `thead th {position:sticky; top:0; z-index:2; background:var(--card)}` ; la colonne
  nom (`.lv-sticky-name`) sticky left ≥768 avec ombre de bord quand scrollé (classe togglée par
  scroll listener passif) ; `<colgroup>` à largeurs fixes — l'édition inline ne fait plus danser
  les colonnes (P3 #14). Contrat conservé : `tr.lv-row`, `.lv-lead-name`, `.ie-cell`,
  `select.ie-input`. Mobile <768 : card-stack global intact, sticky-left désactivé. Files :
  `frontend/src/pages/crm/leads/views/ListView.jsx`, `frontend/src/index.css` + tests. DoD :
  scroller 100 lignes → le thead reste visible ; scroller à droite → le nom reste visible avec
  ombre ; éditer une cellule ne déplace aucune largeur de colonne. (ROUTINE — M)
  (@model: sonnet) (@lane: LB3) (@after: LB8)
- [x] LB19 — **Choix de colonnes persisté (vol de useColumnPrefs + ColumnManager).** Déclarer le
  modèle de colonnes de ListView en tableau ({id, label, visibleParDéfaut, mHide}) ; brancher
  `ui/datatable/useColumnPrefs` (clé `taqinor.leads.columns`) + le composant
  `ui/datatable/ColumnManager` comme UI de choix (bouton « Colonnes » dans la barre d'outils de
  la vue). Les défauts responsive `.m-hide` deviennent la visibilité par défaut du modèle. PAS de
  DataTable, PAS de FilterBuilder, PAS d'urlState du moteur (blueprint D4 — un seul état de
  filtres sur la page). Files : `frontend/src/pages/crm/leads/views/ListView.jsx` + tests. DoD :
  masquer « Canal » survit à un reload ; réafficher tout fonctionne ; datatable-breakpoint.spec
  (VX180) toujours vert (il teste d'AUTRES pages — non-régression d'import). (ROUTINE — M)
  (@model: sonnet) (@lane: LB3) (@after: LB18)
- [x] LB20 — **Option « Par étape » (groupes repliables avec agrégats).** Segmented
  « Plat / Par étape » (persisté `taqinor.leads.listGroup`) : en mode groupé, rangées de groupe
  `tr.lv-group` (StatusPill étape + compteur + total MAD — mêmes nombres que les colonnes kanban,
  via groupLeadsByStage) collantes sous le thead, repliables (chevron labellisé, état persisté),
  l'ordre des groupes = l'ordre du funnel. Le tri s'applique DANS chaque groupe. Files :
  `frontend/src/pages/crm/leads/views/ListView.jsx`, `frontend/src/index.css` + tests. DoD :
  basculer Plat↔Par étape conserve tri et sélection ; replier « Froid » survit au reload ;
  `tr.lv-row` reste le sélecteur des rangées de données (e2e intact). (ROUTINE — M)
  (@model: sonnet) (@lane: LB3) (@after: LB19)
- [x] LB21 — **Lignes ouvrables au clavier + adoption du PerduPopover partagé.** Chaque `tr.lv-row`
  devient focusable (tabIndex=0, Enter/Espace ouvre — jamais depuis un contrôle interne,
  vérif `e.target.closest`) et le nom devient un vrai élément interactif sémantique ; adopter
  `PerduPopover` (LB15) — suppression du popover dupliqué local, une seule instance au niveau
  table ancrée à la ligne active ; conserver le libellé « Plus d'actions sur la ligne » et les
  hrefs tel/wa + stopPropagation (test ListViewCallReady mis à jour ici). Files :
  `frontend/src/pages/crm/leads/views/ListView.jsx` + tests. DoD : parcours 100 % clavier :
  focus ligne → Enter ouvre la fiche ; marquer perdu au clavier ; plus aucun code perdu dupliqué.
  (ROUTINE — M) (@model: sonnet) (@lane: LB3) (@after: LB20, LB15)

**LANE 4 — shell, filtres, KPI, URL (UN agent, séquentiel — fichiers : LeadsPage.jsx,
FilterBar.jsx, BulkActionBar.jsx, SavedViewsBar.jsx, nouveaux LeadsKpiStrip/urlFilters,
index.css `.lp-*`) :**

- [x] LB22 — **URL partageable : ?view= + filtres dans l'URL (module pur).** Nouveau
  `frontend/src/pages/crm/leads/urlFilters.js` : encode/decode `filters+view ↔ URLSearchParams`,
  n'écrit QUE les clés non-défaut (EMPTY_FILTERS comme référence), PRÉSERVE `lead`/`new`/`equipe`,
  100 % pur + test node. LeadsPage : priorité au chargement URL > localStorage > défauts (une URL
  collée gagne toujours) ; écriture débouncée 300ms en `replace` (jamais de spam d'historique) ;
  `?view=` honoré et écrit ; `applySavedView` écrit l'URL. Files :
  `frontend/src/pages/crm/leads/urlFilters.js` (nouveau, + test),
  `frontend/src/pages/crm/leads/LeadsPage.jsx`. DoD : copier l'URL avec 3 filtres + vue liste et
  l'ouvrir en navigation privée reproduit EXACTEMENT l'écran ; `?lead=` continue d'ouvrir la
  fiche ; e2e setLeadsView intact. (ROUTINE — M) (@model: sonnet) (@lane: LB4) (@after: LB8)
- [x] LB23 — **Recherche débouncée.** L'input de recherche garde un état local et pousse
  `setFilters` après 250ms (annulé au démontage) ; `useDeferredValue` reste en second étage ;
  perf attendue avec LB6 : une frappe ne re-rend plus aucune carte. Files :
  `frontend/src/pages/crm/leads/FilterBar.jsx` + tests. DoD : taper 10 caractères vite ne
  produit qu'un recalcul de filtre après pause ; effacer réagit immédiatement. (ROUTINE — S)
  (@model: haiku) (@lane: LB4) (@after: LB22)
- [x] LB24 — **Bandeau KPI = filtres (le cockpit du matin).** Nouveau
  `frontend/src/pages/crm/leads/LeadsKpiStrip.jsx`, rangée compacte entre header et FilterBar
  (scroll-x mobile) : « Dû aujourd'hui » (toggle `relance='aujourdhui'` — NOUVELLE valeur de
  filterLeads : `relance_date === today` local), « En retard » (toggle `relance='retard'`),
  « Chauds » (toggle NOUVELLE clé `score='chaud'` sur `score_label`), « Pipeline » (affichage
  seul : Σ latestDevisTotal des filtrés non perdus + pondéré via STAGE_PROBABILITY importée de
  KanbanView — les MÊMES nombres que les colonnes). Tuiles 1-3 = `<button aria-pressed>` accentées
  `--module-accent-azur` ; compte facetté : le compte d'une tuile = `filterLeads(leads,
  {…filtresActifs, saDimension: appliquée}).length` — cliquer donne ce que le chiffre promet.
  Étendre EMPTY_FILTERS/filterLeads dans stages.js (+ tests node) ; le Segmented relance de
  FilterBar gagne « Aujourd'hui ». Files :
  `frontend/src/pages/crm/leads/LeadsKpiStrip.jsx` (nouveau),
  `frontend/src/features/crm/stages.js` (+ tests),
  `frontend/src/pages/crm/leads/LeadsPage.jsx`, `frontend/src/pages/crm/leads/FilterBar.jsx`,
  `frontend/src/index.css`. DoD : cliquer « En retard » filtre TOUTES les vues et la tuile passe
  aria-pressed ; les nombres tuiles/colonnes/compteur header concordent sous n'importe quel
  filtre ; axe vert. (ROUTINE — L) (@model: sonnet) (@lane: LB4) (@after: LB23, LB16)
- [x] LB25 — **Barre bulk FLOTTANTE.** La barre inline (qui pousse le layout à chaque sélection)
  devient une toolbar flottante bas-centre : `position:fixed`, `z-index:var(--z-sticky)`,
  safe-area + au-dessus de la tabbar mobile, slide-in-up `--motion-base` (reduced-motion : sans
  animation), ombre `--shadow-lg`. MÊME composant BulkActionBar (toutes les actions + typed
  confirm conservées), nouveau wrapper `.lp-bulk-float`, compte visible + « Effacer ». Files :
  `frontend/src/pages/crm/leads/LeadsPage.jsx`,
  `frontend/src/pages/crm/leads/BulkActionBar.jsx`, `frontend/src/index.css` + tests. DoD :
  sélectionner ne fait plus sauter le board ; la barre ne recouvre jamais la tabbar mobile ;
  Échap/Effacer la ferme ; VX95 undo intact. (ROUTINE — M) (@model: sonnet) (@lane: LB4)
  (@after: LB24)
- [x] LB26 — **Vues enregistrées : « Copier le lien » + Express dans le ⋯ mobile.**
  SavedViewsBar : prop additive optionnelle `buildShareUrl(view)` (composant partagé avec
  ClientList — comportement inchangé quand absente) ; sur la page leads, chaque chip gagne une
  action « Copier le lien » (sérialise via urlFilters + clipboard + toast « Lien copié »).
  Sous 768px, le bouton Express rejoint le menu ⋯ (le header respire) — le FAB mobile reste
  « + Nouveau lead » (texte e2e). Files : `frontend/src/components/SavedViewsBar.jsx`,
  `frontend/src/pages/crm/leads/LeadsPage.jsx`, `frontend/src/index.css` + tests. DoD : le lien
  copié reproduit la vue ; ClientList inchangé ; Express accessible au ⋯ en mobile. (ROUTINE — S)
  (@model: sonnet) (@lane: LB4) (@after: LB25)
- [x] LB27 — **Squelette EN FORME dans le shell.** Premier chargement : au lieu du StateBlock
  plein-page, rendre le shell (header + filtres visibles immédiatement) avec un squelette en
  forme de la vue active — 6 colonnes × 3 SkeletonCard en kanban/prévision, SkeletonTableRow en
  liste — via `useDelayedLoading` (spinner 300ms, squelette 500ms) + `FadeSwap` (le pattern
  maison LW25 : chaque calque colonne flex pleine hauteur). Erreur : StateBlock inchangé. Files :
  `frontend/src/pages/crm/leads/LeadsPage.jsx`, `frontend/src/index.css` + tests. DoD : au
  chargement lent le header est visible tout de suite et le squelette a la forme du board ;
  chargement <300ms : aucun flash. (ROUTINE — S) (@model: sonnet) (@lane: LB4) (@after: LB26)

**LANE 5 — vues secondaires (UN agent, séquentiel — fichiers : ForecastView/CalendarView/
CarteView/ChartsView, CrmInsightsPanel) :**

- [x] LB28 — **Prévision : parité complète avec le kanban.** Bugs recon2-03 #9 + gaps recon-01 :
  ajouter KeyboardSensor + annonces FR (buildKanbanAnnouncements avec libellés de mois),
  équivalent clavier du drag (un `<select>` mois par carte, même pattern StageMover/
  useOptimisticSave), busy-lock réel (passer par `onInlineSave` avec busyLeadId), listeners de
  drag isolés sur une poignée (plus sur toute la carte), EmptyState global (0 lead ouvert) +
  hints de drop par colonne. Le shell borné LB2 s'applique (`.fv-board`) — vérifier. Totaux
  pondérés inchangés (STAGE_PROBABILITY importée). Files :
  `frontend/src/pages/crm/leads/views/ForecastView.jsx`, `frontend/src/index.css` + tests
  (ForecastView ×2 mis à jour). DoD : replanifier un mois 100 % clavier ; drag pendant un drag
  refusé (busy) ; 0 lead ouvert → EmptyState ; tests verts. (ROUTINE — M) (@model: sonnet)
  (@lane: LB5) (@after: LB8)
- [x] LB29 — **Calendrier + Carte : tons d'étape, aujourd'hui, hover câblé.** Calendrier : chips
  aux tons d'étape via tokens (STAGE_COLORS), cellule du jour cerclée `--module-accent-azur`,
  relance en retard soulignée destructive ; le double-affichage relance+visite est CONSERVÉ
  (deux échéances réelles). Carte : câbler `hoveredId` (mort — recon-01) : survoler un lead de
  la liste sans-GPS met le pin en avant (ou le supprimer si Leaflet rend le câblage fragile —
  décision locale documentée en commentaire) ; re-baser les hex du popup Leaflet sur tokens via
  CSS là où c'est atteignable ; empty states coach. Files :
  `frontend/src/pages/crm/leads/views/CalendarView.jsx`,
  `frontend/src/pages/crm/leads/views/CarteView.jsx`, `frontend/src/index.css` + tests
  (CalendarView undated banner conservé). DoD : aujourd'hui identifiable d'un coup d'œil ;
  chips AA deux thèmes ; aucun hex nouveau hors tokens.css. (ROUTINE — M) (@model: sonnet)
  (@lane: LB5) (@after: LB28)
- [x] LB30 — **Graphique : cache session des insights + cohérence filtres.** CrmInsightsPanel
  re-fetche ses 3 cartes à CHAQUE bascule de vue : cache module en mémoire TTL 60s (même
  pattern que leadPrefetch), invalidé au changement de company ; ChartsView affiche la ligne de
  contexte « Ces graphiques suivent les filtres actifs (N leads) » ; empty states coach
  (distinction 0 lead / 0 résultat conservée, CTA réels). Le panneau RESTE dans ChartsView
  (décision D5 : pas de fetches d'insights dans le chargement du matin). Files :
  `frontend/src/pages/crm/leads/views/ChartsView.jsx`,
  `frontend/src/components/CrmInsightsPanel.jsx` + tests. DoD : basculer graphique→kanban→
  graphique en <60s ne refait aucun appel insights ; test ch-card-wide vert. (ROUTINE — S)
  (@model: sonnet) (@lane: LB5) (@after: LB29)

**LANE 6 — polish sombre/hex + dédup (UN agent — index.css d'abord, sweep ensuite) :**

- [x] LB31 — **Chasse aux hex des surfaces leads (dark mode honnête).** Recon-05 §HEX,
  index.css UNIQUEMENT : supprimer le doublon MORT `.count-badge` (1701-1715) et tokeniser la
  règle vivante (chips bleu-clair illisibles en sombre) ; `.data-table tr` card-stack mobile
  `background:#fff` → `var(--card)` (chaque ligne mobile était une carte blanche en sombre) ;
  `.gen-btn-orange` re-basé tokens ; `.link-blue`, `.lv-star` (aligné sur kb-star), `.ie-err`/
  `.ie-placeholder`, `.data-table td::before` → tokens ; supprimer le doublon mort
  `.kb-act-clock` (3750-3753) et les règles mortes `.lv-owner`/`.lv-avatar`. AUCUN changement
  JSX. Files : `frontend/src/index.css`. DoD : zéro hex restant dans les plages CSS des surfaces
  leads (hors tokens.css) ; vérification visuelle sombre : badges, card-stack mobile, étoiles,
  erreurs inline lisibles AA. (ROUTINE — M) (@model: sonnet) (@lane: LB6) (@after: LB2)
- [x] LB32 — **Dédup useIsMobile + ViewSwitcher sur Segmented.** Remplacer les 3 copies verbatim
  de `useIsMobile` (FilterBar 26-37, ListView 43-54, ChartsView 31-42) par l'export canonique de
  `ui/ResponsiveDialog` ; refondre ViewSwitcher (85 l. de role=group main-roulé + SVG bruts) sur
  `ui/Segmented` avec icônes lucide, en CONSERVANT les noms accessibles exacts 'Vue kanban' /
  'Vue liste' / etc. (e2e setLeadsView + E3). Files :
  `frontend/src/pages/crm/leads/ViewSwitcher.jsx`,
  `frontend/src/pages/crm/leads/FilterBar.jsx`,
  `frontend/src/pages/crm/leads/views/ListView.jsx`,
  `frontend/src/pages/crm/leads/views/ChartsView.jsx` + tests. DoD : e2e leads.spec (bascule de
  vues) vert ; une seule définition de useIsMobile dans le repo pour ces 3 fichiers ; Segmented
  radiogroup au clavier. (ROUTINE — S) (@model: sonnet) (@lane: LB6)
  (@after: LB21, LB23, LB30, LB31)

**LANE 7 — tests, e2e, goldens (UN agent, en queue de batch) :**

- [x] LB33 — **Spec de régression « le board tient dans l'écran ».** Nouveau
  `e2e/tests/leads-board.spec.js` (helpers gotoLeads/setLeadsView/createLead existants) : en vue
  kanban, le scrolleur du shell ne déborde pas (scrollHeight ≈ clientHeight), la scrollbar
  horizontale du board est DANS le viewport (le board scrolle en x sans scroller la page), un
  `.kb-col-body` scrolle verticalement avec 20+ leads ; en vue liste, après scroll le `thead`
  reste visible. Assertions robustes (tolérances px), pas de screenshots ici. Files :
  `e2e/tests/leads-board.spec.js` (nouveau). DoD : spec verte en local ET en CI ; échoue si on
  retire la règle `:has(> .lp-page)` (vérifié une fois en le commentant). (ROUTINE — M)
  (@model: sonnet) (@lane: LB7) (@after: LB12, LB18)
- [x] LB34 — **Goldens leads-kanban clair+sombre + passe axe finale (clôture du batch).**
  Régénérer DÉLIBÉRÉMENT les screenshots release-verify `leads-kanban` light+dark (procédure
  maison de mise à jour des snapshots visual.spec) après l'atterrissage de TOUTES les lanes
  visuelles ; dérouler la passe axe VX71 sur la page redessinée (tuiles KPI, chevrons de repli,
  zones de scroll, menus •••, barre flottante — zéro violation sérieuse) ; vérifier
  mobile.spec/tablet.spec (VX190/VX68) inchangés ou mis à jour ici. Files : dossiers de
  snapshots e2e (goldens), corrections a11y mineures résiduelles le cas échéant. DoD :
  release-verify vert avec les nouveaux goldens ; axe zéro violation sérieuse sur
  kanban/liste/KPI ; rapport d'une ligne au DONE LOG listant les goldens touchés. (ROUTINE — S)
  (@model: sonnet) (@lane: LB7)
  (@after: LB17, LB21, LB27, LB30, LB31, LB32, LB33)

**LANE LB8R — résidus de la critique Fable finale (2026-07-19 — mineurs, prochaine session) :**

- [ ] LB35 — **ForecastView : parité des trois invariants du kanban.** Sa `DraggableCard` n'est pas `memo()` (blueprint I4 — chaque frappe re-déroule `useDraggable`+`useOptimisticSave` par carte), aucun retour de focus après un drop clavier (le motif LB12 est absent — le focus atterrit sur `<body>`), et pas de drag-to-pan sur le fond. Fix : appliquer les trois motifs EXISTANTS du kanban (memo(), restauration de focus post-drop, `usePanScroll` en callback-ref) — jamais une seconde implémentation. Files : `frontend/src/pages/crm/leads/views/ForecastView.jsx` (L170-192, L304-314), `frontend/src/features/kanban/usePanScroll.js` (réutilisé tel quel). DoD : sonde memo `.mjs` (même motif que LeadsPageMemoStability) verte ; drop clavier → focus sur la carte déplacée ; pan actif sur le fond vide. (ROUTINE — M) (@model: sonnet) (@lane: LB8R)
- [ ] LB36 — **FilterBar : « Effacer les filtres » pendant le débounce ressuscite la recherche.** Taper puis cliquer « Effacer » dans les 250 ms : `filters.q` n'a jamais changé, le resync durant-rendu ne se déclenche pas, et le timer en attente ré-applique le `q` tapé APRÈS l'effacement. Fix : annuler le timer en vol quand l'effacement/le resync ramène le texte local (garder le motif « adjust state during render », jamais un setState-in-effect). Files : `frontend/src/pages/crm/leads/FilterBar.jsx` (L44-54). DoD : test — taper « xyz » puis effacer sous 250 ms → `filters.q` reste vide après le délai. (ROUTINE — S) (@model: sonnet) (@lane: LB8R)
- [ ] LB37 — **Commentaires menteurs survivants (blueprint I2).** `LeadCard.jsx:144-147` prétend encore « le kanban re-rend déjà périodiquement via son polling/refetch existant » (aucun polling n'existe) ; `ListView.jsx:791-796` documente la plomberie `perduMotif/perduBusy` supprimée au fold LB21. Fix : corriger/supprimer ces deux blocs (et UNIQUEMENT eux). Files : `frontend/src/pages/crm/leads/LeadCard.jsx`, `frontend/src/pages/crm/leads/views/ListView.jsx`. DoD : `grep -n "polling" LeadCard.jsx` = 0 ; plus aucune mention de perduMotif/perduBusy dans ListView. (ROUTINE — S) (@model: haiku) (@lane: LB8R)
- [ ] LB38 — **`selectionActive` déclaré mais jamais câblé (comportement D3 différé en silence).** `LeadCard.jsx:190-194` reçoit la prop, la règle CSS `index.css:7638` existe, mais pendant une sélection active les cartes non survolées cachent toujours leur case au desktop. Fix : poser la classe (`kb-card-selection-active` ou équivalent) depuis la prop pour révéler TOUTES les cases pendant une sélection ; supprimer la règle morte sinon. Files : `frontend/src/pages/crm/leads/LeadCard.jsx`, `frontend/src/index.css`. DoD : test — une sélection non vide → chaque carte visible expose sa case sans survol. (ROUTINE — S) (@model: sonnet) (@lane: LB8R)
- [ ] LB39 — **Pré-existant (pas de cette branche) : l'undo VX95 de changement d'étape est mort en production.** L'undo PATCHe en arrière (`LeadsPage.jsx:580-588`) et la garde du serializer (`apps/crm/serializers.py:367-380`) 400e tout recul → chaque toast « Annuler » finit en « Annulation impossible » (le test unitaire mocke le dispatch, il ne l'a jamais vu). Fix côté SERVEUR : autoriser le recul quand la requête porte un marqueur d'annulation explicite (ex. `undo=true` validé serveur, fenêtre courte), garde funnel inchangée sinon ; le client envoie ce marqueur depuis le toast. Files : `backend/django_core/apps/crm/serializers.py`, `frontend/src/pages/crm/leads/LeadsPage.jsx`, test API dans `apps/crm/tests/`. DoD : test API — PATCH recul avec marqueur = 200, sans = 400 ; test front — l'undo aboutit. (SCHEMA — M) (@model: opus) (@lane: LB8R)
- [ ] LB40 — **Cosmétique : barre bulk vs scrollbar du board + infobulles ViewSwitcher.** La barre flottante (fixed bas-centre, z 1100) couvre le milieu de la scrollbar horizontale du board pendant une sélection, et le DragOverlay (z 999) glisse SOUS elle ; les radios icône-seule du ViewSwitcher ont perdu leurs infobulles au survol (noms sr-only seulement, `ViewSwitcher.jsx:34-38`). Fix : remonter la barre au-dessus de la scrollbar (offset bas = hauteur scrollbar) ou la décaler latéralement ; DragOverlay au-dessus de la barre pendant un drag ; `title`/Tooltip maison sur chaque radio. Files : `frontend/src/pages/crm/leads/BulkActionBar.jsx`, `frontend/src/pages/crm/leads/ViewSwitcher.jsx`, `frontend/src/index.css`. DoD : revue visuelle rig — scrollbar cliquable pendant une sélection ; survol d'un radio → libellé visible. (ROUTINE — S) (@model: sonnet) (@lane: LB8R)

**LANE LB9R — retouches fondateur du 2026-07-20 (scroll unique Odoo, mobile, ligne de contrôle) :**

- [x] LB41 — **Kanban : UN SEUL scroll vertical pour toutes les étapes (patron Odoo, retour fondateur).** L'ascenseur par colonne (kb-col-body overflow-y) contredit le standard : Odoo 17 (vérifié à la source — o_content overflow:auto 2 axes, o_kanban_header position-sticky top-0, colonnes hauteur naturelle sans overflow) fait défiler tout le board ensemble. Fix : `.kb-board` overflow:auto (2 axes, scrollbar H toujours au bas du viewport — invariant LB33 #2 conservé), colonnes hauteur de contenu étirées (min-height:100%, jamais de height explicite qui tuerait le stretch), en-têtes d'étape sticky (fond opaque, palier local via isolation), tabindex clavier déplacé des corps vers le board (kanban ET prévision — mêmes classes kb-*). leads-board.spec invariant 3 réécrit : board scrolle Y, corps de colonne NON, en-tête épinglé pendant le scroll. Files : index.css, KanbanView.jsx, ForecastView.jsx, e2e/leads-board.spec.js, KanbanViewColumns.test.mjs. (ROUTINE — M) (@model: opus) (@lane: LB9R)
- [x] LB42 — **Kanban mobile : le patron Odoo exact (une étape à la fois, snap, colonne = scrolleur).** « ça casse sur le téléphone, je ne peux pas scroller vers le bas » : 6 colonnes côte à côte sur un téléphone + scroll par corps de colonne = zone minuscule inutilisable. Odoo mobile (kanban_controller.scss vérifié) : colonnes 90% de large (un bord de la suivante dépasse — la seule affordance), scroll-snap-type:x mandatory sur le board, et LA COLONNE redevient le scrolleur vertical (axes imbriqués) — l'en-tête sticky se re-résout seul. Files : index.css (@media 768px du bloc kb-*). (ROUTINE — S) (@model: opus) (@lane: LB9R)
- [x] LB43 — **Ligne de contrôle UNIQUE façon Odoo (recherche + facettes + « Filtres ▾ » + ⋯).** « une ligne en haut avec recherche et filtres, le reste dans un menu 3 points — tout le monde a trouvé la bonne solution » : l'anatomie Odoo (SearchBar + facettes DANS la barre + UN SearchBarMenu ; actions basse fréquence dans le cog) remplace les 3 rangées de chrome. Une rangée : titre+compteur → FilterBar (recherche débouncée conservée + chips facettes « Dimension : valeur ✕ » par filtre actif + chips Mes leads/Rappels + UN Popover « Filtres ▾ » portant les 9 dimensions + Effacer) → ⋯ (Express/Doublons/Importer/Exporter/⭐ Enregistrer la vue) + Nouveau + ViewSwitcher. Mobile : la recherche décroche seule en 2e ligne (flex-wrap, comme Odoo) ; le bandeau KPI reste (compact, scroll horizontal déjà en place). Plus aucune fourche isMobile dans LeadsPage/FilterBar. Files : LeadsPage.jsx, FilterBar.jsx, index.css ; pins retargetés (KpiStrip/SavedViewsBar/ExpressMobile/ViewSwitcherSegmented/VX45). (ROUTINE — L) (@model: opus) (@lane: LB9R)
- [ ] LB45 — **Mobile : le sélecteur de vues devient un dropdown compact (patron Odoo).** Odoo mobile réduit le view-switcher à UN bouton-icône dropdown ; notre Segmented 6 icônes (~192px) occupe une rangée entière du chrome mobile (mesuré : la dernière rangée évitable au-dessus du board, board à 47% de l'écran au lieu de ~52%). Fix : sous 768px, ViewSwitcher rend un DropdownMenu icône-seule (vue active en icône, les 6 vues en items) — même état `view`/`setView`, mêmes noms accessibles ; desktop inchangé. Files : `frontend/src/pages/crm/leads/ViewSwitcher.jsx`, `frontend/src/index.css`, pins ViewSwitcherSegmented.test.mjs. DoD : sonde rig 375px — board ≥52% de l'écran ; e2e setLeadsView adapté aux deux gabarits. (ROUTINE — S) (@model: sonnet) (@lane: LB8R)
- [x] LB44 — **Fenêtre lead mobile : le scroll-spy suit enfin le défilement (parité desktop).** Sous 768px le scrolleur devient `.lw-body--edit` (ancêtre) : le onScroll React de `.lw-center` ne tirait jamais (scroll ne bulle pas) ET la référence `box.top` devenait constante (le centre glisse AVEC le contenu) — le chip actif de la nav restait figé. Fix : écouteur natif en phase CAPTURE sur `.lw-body` (couvre les deux gabarits, zéro ré-attache au resize) + ligne de référence = le BAS de la nav sticky `.lw-secnav` (valide dans les deux gabarits). Files : SectionsPane.jsx. (ROUTINE — S) (@model: opus) (@lane: LB9R)

#### DONE LOG — Groupe LB (page leads)

- 2026-07-20 — LB41-LB44 (retouches fondateur, recherche Odoo-source préalable) : scroll UNIQUE du board (toutes étapes ensemble, en-têtes sticky, clavier sur le board), kanban mobile Odoo (90% + scroll-snap + colonne scrolleuse), ligne de contrôle unique (recherche+facettes+« Filtres ▾ » popover 9 dimensions+⋯ avec Express/Doublons/Import/Export/Enregistrer-vue), scroll-spy mobile de la fenêtre lead réparé (écouteur capture + référence nav sticky). leads-board.spec invariant 3 réécrit ; 7 fichiers de pins retargetés. (ROUTINE)

- 2026-07-19 — Critique Fable finale (2e appel Fable du run) : verdict NOT MERGE-READY, 2 bloqueurs + 4 importants, TOUS corrigés avant merge — usePanScroll converti en callback-ref (le pan mourait après tout passage par un board vide, ex. recherche sans résultat), sentinelle « Signé » avalée dans la cellule étape de la liste (faux « Échec » rouge persistant sur un chemin de succès), pool KPI filtré `?equipe=` (chiffre menteur D5), perdus exclus de `totalDevis` (tuile Pipeline et têtes de colonnes = MÊMES chiffres, pin .mjs ajouté), cache insights porteur de ses promesses (fini le « Chargement… » bloqué au remontage en vol), garde Échap (un overlay ouvert garde son Échap, la sélection bulk survit). Mineurs #7-#12 bankés en LB35-LB40 (lane LB8R). (ROUTINE)

- 2026-07-19 — LB9-LB12 (lane board) : colonnes nommées ARIA + corps scrollable au clavier, argent par colonne + prévisionnel pondéré (STAGE_PROBABILITY importé), repli persisté en rail 44px toujours droppable, autoScroll dnd-kit + drag-to-pan sur fond vide (jamais sur une carte), focus restauré sur la carte déplacée. (ROUTINE)
- 2026-07-19 — LB13-LB17 (lane carte, opus) : carte 4 zones plafonnée (nom→valeur→UNE action→pied), rotting via workspace/rotting.js (liseré danger), PerduPopover PARTAGÉ + menu ••• au survol, 10 jetons --tag-* clair+sombre + --brand-whatsapp (le swipe WhatsApp redevient VERT), cibles 44px sans inline (::before), bande swipe inert, cadenas PII. Suites épinglées mises à jour dans les mêmes commits. (ROUTINE)
- 2026-07-19 — LB18-LB21 (lane liste) : scrolleur unique .lv-wrap + thead ET colonne nom sticky (+ombre de bord), colgroup table-layout:fixed, choix de colonnes persisté VOLÉ à ui/datatable (zéro fork), groupement « Par étape » avec en-têtes sticky + agrégats MAD (mêmes chiffres que le kanban), activation clavier des lignes. Au fold : PerduPopover partagé câblé (plomberie parent supprimée), paliers z tokenisés + isolation. (ROUTINE)
- 2026-07-19 — LB22-LB27 (lane shell) : URL partageable (?view= + filtres, URL > localStorage > défauts, replace débouncé), recherche débouncée 250ms (resync durant-rendu), bandeau KPI-filtres facettés (Dû aujourd'hui/En retard/Chauds togglables + Pipeline MAD·pondéré affichage), bulk FLOTTANT (Escape ferme), « Copier le lien » sur les vues enregistrées, squelette EN FORME dans le shell (en-tête/filtres/KPI immédiats). (ROUTINE)
- 2026-07-19 — LB28-LB30 (lane vues secondaires) : Prévision à parité clavier (KeyboardSensor + MonthMover + annonces + busy-lock + état vide), Calendrier aujourd'hui/retard soulignés tokenisés, Carte nettoyée (hoveredId mort retiré, hex → tokens), insights en cache session 60s + « suivent les filtres actifs (N) ». (ROUTINE)

- 2026-07-19 LB1 — blueprint déjà recopié par le merge de `claude/leads-page-redesign` ;
  vérifié octet-identique (hors CRLF/LF) à `scratchpad/design2/blueprint.md`. Aucun code touché.
- 2026-07-19 LB2 — P0 fondateur corrigé : `.layout-content > .route-fade:has(> .lp-page)
  {height:100%}` + `.lp-page` flex column bornée (miroir `.lw-page`) ; `.lp-view-area` perd son
  `min-height:320px` fixe, devient `flex:1 1 auto;min-height:0`, `overflow:hidden` pour les 3
  vues denses via `data-view` (1 ligne JSX sur la racine de LeadsPage.jsx) ; `.kb-board`
  `height:100%`→`flex:1 1 auto` (se résolvait en AUTO, cause racine des 8 649px mesurés) ;
  `.kb-col-body` `min-height:80px`→`0` (ne débordait jamais) ; `.lv-wrap` scrolleur deux axes
  unique (`overflow:auto` + flex) ; pleine largeur (`max-width:none`) kanban/prévision/liste ;
  scrollbars fines tokenisées toujours visibles ; gap responsive 769-899px comblé (`.kb-col`
  clamp) ; thead sticky + `.lv-sticky-name` posés en pré-requis (D4 les activera). Raisonnement
  statique de la chaîne : `#root`(100vh)→`.layout-main`(overflow:hidden)→`.layout-content`
  (flex:1;overflow-y:auto)→`.route-fade`(désormais height:100% via :has)→`.lp-page`(flex column
  height:100%)→`.lp-view-area`(flex:1 1 auto;min-height:0;overflow:hidden en vue kanban)→
  `.kb-board`(flex:1 1 auto;min-height:0;overflow-x:auto) — chaque maillon a maintenant une
  hauteur RÉSOLUE (plus jamais AUTO), donc `.kb-col-body{overflow-y:auto;min-height:0}` déborde
  réellement au lieu de grandir sans fin. ForecastView (`.kb-board.fv-board`) hérite sans
  modification (mêmes classes). `.lw-page` non touché.
- 2026-07-19 LB3 — interception « Signé » honnête (bug #2) : nouveau
  `pages/crm/leads/signeIntercept.js` (sentinelle `SIGNE_INTERCEPT` Symbol + `isSigneIntercept`,
  test node dédié vert). `LeadsPage.jsx#onInlineSave` renvoie désormais `Promise.reject(SIGNE_INTERCEPT)`
  après avoir ouvert SigneDialog (au lieu d'un faux `Promise.resolve()`) : `useOptimisticSave`
  fait son rollback normal (le select StageMover revient à l'étape réelle) et `InlineEdit`
  (liste) restaure déjà par rejet — zéro cas spécial côté liste. Le SEUL cas spécial vit dans
  `StageMover`'s `onError` (KanbanView.jsx) : avale la sentinelle via `isSigneIntercept(err)`
  sans toaster, toute autre erreur toaste comme avant. 2 tests ajoutés à KanbanView.test.jsx
  (sentinelle → rollback sans toast ; vraie erreur → rollback ET toast) — les 2 verts en
  raisonnement, non exécutables ici (pas de node_modules dans ce worktree).
- 2026-07-19 LB4 — un lead Froid se réactive par drag (bug #7/#8) : `stages.js` gagne
  `funnelRank` (COLD → -1, miroir `apps/crm/services.py _rang_funnel`) et
  `isStageMoveAllowed(current, target)` (miroir byte-à-byte `_bulk_stage_allowed` — 4 tests node
  verts, exécutés). `KanbanView.jsx#handleDragEnd` utilise ce garde unique au lieu du `stageRank`
  local (COLD y valait le rang le PLUS HAUT → tout drag COLD→actif était refusé comme un recul,
  cause racine du bug #7 alors que le serveur autorise DÉJÀ la réactivation). Options interdites
  grisées dans le StageMover (kanban, `disabled` par `<option>`) ET dans l'InlineEdit stage de la
  liste (`ListView.jsx` : nouveau `stageOptionsFor(currentStage)` par ligne, remplace la liste
  plate `STAGE_OPTIONS` partagée) — le chemin clavier/select obtient enfin la MÊME réponse que le
  drag (bug #8). `components/InlineEdit.jsx` gagne un support `disabled` PAR OPTION,
  rétro-compatible (undefined pour tous les autres appelants = comportement inchangé). SIGNED
  reste gardé : y entrer passe toujours par SigneDialog (LB3), en sortir en arrière reste interdit
  sauf → Froid. Tests : 4 nouveaux cas dans `stages.test.mjs` (exécutés, verts), 2 nouveaux dans
  `KanbanView.test.jsx` (options grisées FOLLOW_UP + réactivation COLD, raisonnement — non
  exécutables ici), nouveau `ListViewStageGuard.test.mjs` (4 assertions source, exécutées, vertes).
- 2026-07-19 LB5 — « ✗ Perdu » depuis une carte met l'UI à jour (bug #3) : nouveau callback
  stable `LeadsPage.jsx#onMarkPerdu(lead, motif)` (dispatch `updateLead`, AUCUN refetch —
  `updateLead.fulfilled` patche déjà le lead complet, toastError + relance l'erreur en échec pour
  que l'appelant garde sa popover ouverte), ajouté à `viewProps`. `LeadCard.jsx` n'appelle plus
  JAMAIS `crmApi.updateLead` en direct (contournait Redux) et la prop fantôme `onChanged` (jamais
  passée par KanbanView NI ForecastView — les commentaires « resynchronisation au refetch » qui
  l'affirmaient mentaient, aucun polling n'existe) est supprimée. `KanbanView.jsx` (DraggableCard)
  ET `ForecastView.jsx` (bug-fix, évite une régression puisque le bouton ✗ y fonctionnait déjà en
  direct) threadent `onMarkPerdu` jusqu'à `LeadCard`. `ListView.jsx#confirmPerdu` route désormais
  par le MÊME callback partagé au lieu d'un `dispatch(updateLead)` local dupliqué (import
  `updateLead` retiré, devenu inutile). Tests : nouveau `LeadsPageMarkPerdu.test.mjs` (7
  assertions source, exécutées, vertes) ; suite existante (VX95Forgiveness, LeadCardVX24,
  ReadinessChips, SwipeAction, FirstTouchTimer, ForecastView — 37 tests) re-exécutée, toujours
  verte.
- 2026-07-19 LB6 — mémo réparé (bug #4) : TOUS les callbacks de `viewProps` (LeadsPage.jsx) sont
  désormais `useCallback` — `refetch`, `onToggleSelect`, `onToggleAll`, `reassign`,
  `onPlanifierRelance`, `onInlineSave` (en plus des `onOpenLead`/`onAutoQuote`/`changeStage` déjà
  faits en VX187) ; `viewProps` lui-même passe en `useMemo`, repositionné AVANT les retours
  anticipés loading/error (règle des Hooks — un `useMemo` après un retour conditionnel change
  l'ordre des Hooks entre rendus). `KanbanView.jsx` mémoïse `DraggableCard` (`memo()`). Côté liste
  (bug #4 précis : `perduMotif` partagé passé identique à TOUTES les lignes → une frappe
  re-rendait la table entière malgré `memo(ListRow)`) : la popover « ✗ Perdu » ne reçoit plus
  `perduTarget` (objet, référence neuve à chaque frappe) mais `perduOpen` (booléen calculé par le
  parent) + `perduMotif`/`perduBusy` CONDITIONNÉS (constante `''`/`false` pour les lignes non
  ciblées, valeur live SEULEMENT pour la ligne ouverte) ; `confirmPerdu(lead, motif)` prend ses
  arguments en PARAMÈTRES (au lieu de lire `perduTarget`/`perduMotif` en closure) pour rester une
  référence stable quel que soit ce que l'utilisateur tape ; `onArchive`/`onRestore`/`onDelete`/
  `closePerdu` passent en `useCallback` ; `armCallNudgeFor` stabilisée via un ref « toujours à
  jour » synchronisé en effet (jamais pendant le rendu — `useCallEndedNudge` reste hors périmètre
  de cette lane). `components/InlineEdit.jsx` inchangé (déjà touché LB4). Tests : nouveau
  `LeadsPageMemoStability.test.mjs` (8 assertions source, exécutées, vertes) ; nouveau
  `KanbanViewMemoStability.test.jsx` (sonde de rendu réelle — LeadCard mocké+compté, 0 re-rendu
  sur un nouveau tableau `leads` à callbacks/objets stables, re-rendu ciblé sur `busyLeadId`) ;
  3 tests pré-existants mis à jour DANS cette tâche pour suivre la nouvelle forme du source
  (`LeadsPagePlanifierRelance.test.mjs`, `LeadsPageMarkPerdu.test.mjs`,
  `axiosVX55Timeout.test.mjs` — `viewProps`/`refetch`/`confirmPerdu` littéraux changés). Suite
  complète leads + adjacents (148 tests node) re-exécutée, verte.
- 2026-07-19 LB7 — plus de refetch intégral après un PATCH mono-lead, fin des catch muets, garde
  d'obsolescence (bugs #5/#10/#11) : `onInlineSave` et `reassign` (LeadsPage.jsx) perdent leur
  `refetch()`/`.then(() => refetch())` — `updateLead.fulfilled` (crmSlice.js) remplace déjà le
  lead au COMPLET (score/stage_since_days/devis inclus). `ListView.jsx#onArchive`/`onRestore`
  perdent également leur `onRefetch?.()` (`archiveLead.fulfilled`/`restoreLead.fulfilled` patchent
  déjà `is_archived` en place — la ligne se re-rend grisée/« Restaurer » seule) ; `onDelete` GARDE
  le sien (`restaurerCorbeille` n'a pas de reducer de ré-insertion, seul un refetch ramène le lead
  restauré dans le store). Le refetch intégral ne reste que pour bulk (`runBulk`), import
  (`ExcelImport onDone`), merge (`DoublonsPanel onAnyMerge`), Signé confirmé (`SigneDialog`),
  création (`onSaved`) — tous vérifiés toujours câblés. Catches silencieux tués (I8) :
  `reassign`, `exportFiltered` (`/* ignore */` → `toastError`), `exportSelection` (bannière
  `bulkMsg` locale → `toastError`, cohérent avec le reste), `ListView#onArchive`/`onRestore`
  toastent désormais en échec. `crmSlice.js` gagne `fetchLeadsRequestId` (miroir
  `leadUpdateSeq`/`isStaleResourceUpdate`) : `fetchLeads.pending` trace le requestId de la
  DERNIÈRE requête dispatchée, `fetchLeads.fulfilled` ignore un payload dont le requestId ne
  correspond plus (fin du flicker où un refetch lent remplaçait `state.leads` au complet avec un
  snapshot périmé). Tests : nouveau `crmSliceFetchLeadsObsolescence.test.mjs` (4 assertions),
  nouveau `LeadsPageNoOverfetch.test.mjs` (6 assertions) — 158 tests node (leads + adjacents)
  re-exécutés, verts.
- 2026-07-19 LB8 — sélection élaguée contre la liste FILTRÉE (bug #6, blueprint I5) :
  `visibleSelected` (LeadsPage.jsx) élague désormais `pruneSelection(selected,
  filtered.map(l => l.id))` au lieu de `leads.map(...)` (TOUS les leads chargés, filtre ou pas) —
  un lead sélectionné puis masqué par un filtre restait bulk-actionnable EN INVISIBLE. `selected`
  (l'état React brut) n'est jamais muté par `pruneSelection` (fonction pure) : retirer le filtre
  fait naturellement réapparaître les leads déjà cochés sans logique supplémentaire. La barre bulk
  (`BulkActionBar count={visibleSelected.size}`) et `runBulk` (qui n'agit que sur
  `[...visibleSelected]`) héritent du fix sans y toucher. Tests : nouveau
  `LeadsPageSelectionPruning.test.mjs` (4 assertions — wiring source + 3 scénarios DoD exécutés
  contre la vraie logique pure `pruneSelection` de `features/crm/bulk.js`). Suite complète
  leads + adjacents (162 tests node) re-exécutée, verte.

**Lane LB0 (urgence) — LB1 à LB8 TOUTES livrées 2026-07-19.** Les lanes suivantes (LB1 board,
LB2 carte, LB3 liste, LB4 shell/filtres/KPI/URL, LB5 vues secondaires, LB6 polish/dark,
LB7 tests/e2e/goldens de la carte des fichiers — @lane LB1-LB7 ci-dessous, à ne pas confondre
avec les tâches LB1-LB8 de cette section) peuvent désormais bâtir dessus : `funnelRank`/
`isStageMoveAllowed` (stages.js) et `SIGNE_INTERCEPT`/`isSigneIntercept` (signeIntercept.js)
sont les nouveaux contrats partagés ; `onMarkPerdu`/`stageOptionsFor` sont les nouveaux points
d'extension côté carte/liste ; le contrat CSS D1 (`.lp-page`/`data-view`/`.kb-*`/`.lv-*`) est en
place, LANE C peut poser `.lv-sticky-name` sans retoucher `index.css` (déjà prêt).

- 2026-07-19 LB31 — chasse aux hex des surfaces leads (index.css UNIQUEMENT, aucun changement
  JSX). Retokenisé : `.count-badge` live (re-basée sur `--tag-8-bg`/`--tag-8-fg`, identique
  octet-près en clair, plus un chip bleu-clair illisible en sombre) après suppression du
  doublon MORT (l'ancienne règle `#e2e8f0`/`#64748b`, toujours écrasée par la cascade) ;
  `.data-table tr` card-stack mobile (`#fff`/`#e2e8f0` → `var(--card)`/`var(--border)`) et
  `.data-table td::before` (`#94a3b8` → `var(--muted-foreground)`) — règle GLOBALE (~40 pages
  consommatrices hors leads : DevisList/FactureList/ClientList/reporting/marketing/adsengine/…),
  corrigée volontairement pour tuer le bug sombre partout, rayon d'action noté dans un
  commentaire in situ ; `.gen-btn-orange` (seul consommateur ListView « ⚡ Devis auto ») re-basé
  sur `--warning`/`--warning-foreground` (couleur sémantique la plus proche, léger glissement
  orange→doré assumé) ; `.link-blue` (consommateur partagé RH/installations/stock/SAV/CRM) sur
  `--info` + hover `color-mix` vers `--foreground` ; `.ie-err`/`.ie-placeholder` sur l'idiome
  teinte-destructive déjà utilisé ailleurs dans le fichier / `--muted-foreground` ; `.lv-star`
  aligné sur `.kb-star` (`var(--border, #d1d5db)`). Supprimé : le doublon mort `.kb-act-clock`
  (raw hex, toujours écrasé par la version tokenisée plus bas) et les règles mortes
  `.lv-owner`/`.lv-avatar` (zéro référence JSX repo-wide, supersédées par AssigneePicker).
  Différé (hors périmètre nommé) : `.ie-cell:hover` (`#cbd5e1`/`#f8fafc`) — non cité par la tâche
  ni par recon2-05, laissé pour une passe future. Aucun test existant ne référence ces classes
  (grep vérifié) ; pas de nouveau test ajouté (tâche CSS pure, DoD = grep + vérification visuelle
  sombre, pas de couverture automatisée demandée). `node -e` brace-balance check sur index.css
  après coup : OK.
- 2026-07-19 LB32 — ViewSwitcher rebâti sur `ui/Segmented` (radiogroup + roving tabindex +
  flèches/Home/End au clavier "gratuits", au lieu du `role="group"` main-roulé + SVG bruts) ;
  icônes lucide alignées 1:1 sur celles que CHAQUE vue importe déjà pour son propre empty state
  (LayoutGrid/List/BarChart3/Map/CalendarClock, + `Calendar` neuf pour « Vue calendrier », seule
  vue sans icône déjà établie). Les 6 noms accessibles pinnés ('Vue kanban'/'Vue liste'/…) sont
  CONSERVÉS verbatim mais deviennent visuellement masqués (`.sr-only`, idiome déjà utilisé par
  ui/Form.jsx/ui/Select.jsx/ui/SolarLoader.jsx) — Segmented rend toujours `label` en contenu
  visible, c'était le seul moyen de garder le nom accessible pinné ET la présentation
  icône-seule d'origine (le switcher partage sa rangée avec Nouveau/Express/⋯, header dense).
  Conséquence directe assumée : le rôle ARIA réel passe de `button` à `radio`
  (`role="radiogroup"` > `role="radio"`) — `frontend/e2e/helpers.js#setLeadsView` (hors
  périmètre "Files:" nommé mais explicitement requis par le DoD "e2e leads.spec vert" ET par le
  blueprint §STRATÉGIE E2E : « chaque tâche qui touche un hook pinné le met à jour DANS la même
  tâche ») bascule `getByRole('button', …)` → `getByRole('radio', …)`, nom accessible inchangé.
  index.css : `.vs-btn`/boutons joints main-roulés (rendus dead par le remplacement JSX)
  supprimés ; `.vs-group` réduit à son seul hook de positionnement
  (`.lp-header-actions .vs-group{margin-left:auto}`), toujours appliqué comme className sur le
  radiogroup pour ne pas retoucher LeadsPage.jsx (hors périmètre). Dédup useIsMobile : les 3
  copies locales verbatim (FilterBar.jsx/ListView.jsx/ChartsView.jsx, MOBILE_QUERY
  '(max-width: 768px)') remplacées par le hook CANONIQUE `ui/ResponsiveDialog#useIsMobile`
  (déjà adopté par LeadsPage.jsx/LeadWorkspace), appelé avec le MÊME breakpoint explicite —
  comportement pixel-identique, zéro nouvelle copie. `useState`/`useEffect` devenus
  entièrement inutilisés dans ChartsView.jsx (n'y servaient QUE le hook local) → import react
  élagué à `{ useMemo }`. Tests : nouveau `ViewSwitcherSegmented.test.mjs` (5 assertions —
  Segmented monté/plus de role=group/SVG brut, icônes lucide, 6 libellés pinnés, dédup
  useIsMobile ×3, helpers.js role=radio) ; `ForecastView.test.mjs` mis à jour dans cette tâche
  (assertion `key: 'prevision'` → `value: 'prevision'`, contrat Segmented). `node --test` sur
  toute la suite leads (114 tests, `src/pages/crm/leads/**/*.test.mjs` +
  `SavedViewsBar.test.mjs`) : verte. e2e leads.spec/tablet.spec/mobile.spec non exécutables ici
  (pas de node_modules dans ce worktree/lane) — vérifiés par raisonnement + le nouveau test
  source-grep sur helpers.js.
- 2026-07-19 LB33 — spec de régression « le board tient dans l'écran » : nouveau
  `frontend/e2e/leads-board.spec.js` (projet `chromium`, Desktop Chrome 1280×720). Un seul
  `test.slow()` crée 20 leads réels (colonne « Nouveau » assez haute pour DÉBORDER le viewport si
  elle n'était pas bornée — le seuil qui rend l'invariant sensible à la régression), puis prouve
  par la MESURE (jsdom n'en calcule aucune) : (1) `.layout-content` (scrolleur du shell,
  overflow-y:auto) ne déborde pas verticalement en kanban (scrollHeight−clientHeight ≤ 4px — c'est
  CE qui rouvrait des milliers de px sans le fix `:has(> .lp-page)`, donc l'invariant échoue si on
  retire la règle) ; (2) le bas de `.kb-board` tient dans le viewport ET le board défile en X
  (scrollWidth>clientWidth, scrollLeft>0 après scroll) sans que la PAGE défile en X
  (window.scrollX===0, débordement horizontal page ≤1px) ; (3) la `.kb-col-body` de « Nouveau »
  déborde (scrollHeight>clientHeight) et défile (scrollTop>0) ; (4) en liste, le `thead` reste
  ÉPINGLÉ (sa position écran ne bouge pas de plus de 4px après avoir défilé `.lv-wrap` tout en bas,
  + `toBeInViewport`). Tolérances px robustes, aucun screenshot. Vérifié syntaxe (`node --check`
  OK) ; non exécutable ici (pas de node_modules — Playwright tourne au fold par l'orchestrateur,
  release-verify `--grep-invert @visual`). Sélecteurs vérifiés ligne à ligne contre le DOM réel
  post-refonte (LeadsPage/KanbanView/ListView/index.css) + helpers existants
  (gotoLeads/setLeadsView radio/createLead).
- 2026-07-19 LB34 — clôture e2e du batch LB (goldens + passe axe + marche de tous les specs de la
  lane). **Specs corrigés contre le DOM post-refonte :** `doublons.spec.js` (E11) — « Doublons »
  a quitté l'en-tête pour l'item du menu « ⋯ » (VX145b/LB26, icône GitMerge, plus l'emoji 🔀) :
  `getByRole('button', {name:'🔀 Doublons'})` → ouvrir `getByRole('button', {name:"Plus
  d'actions"})` puis `getByRole('menuitem', {name:/Doublons/})` (patron Radix déjà éprouvé par
  mobile.spec E16+). **Passe axe FINALE ajoutée à `leads.spec.js`** (LB34) : scanne la page réelle
  en kanban (scope `.lp-page` = surface redessinée : tuiles KPI `aria-pressed`, ViewSwitcher
  `radiogroup`, colonnes nommées, chevrons/zones de scroll labellisés), la barre bulk FLOTTANTE
  (`.lp-bulk-float`, révélée en cochant une carte en `force`), le menu ••• Radix ouvert (portalé,
  scanné via `[role="menu"]`) et la vue liste — 0 violation serious/critical (même seuil anti-flake
  que VX71 ; scope `.lp-page` exclut le chrome global, hors périmètre). **Goldens `leads-kanban`
  clair+sombre** (`visual.spec.js`) : capture INCHANGÉE côté code — le `ready` cible `.header-title`
  (header global, toujours présent) + `networkidle`, valide sur le nouveau DOM ; la refonte CHANGE
  forcément les pixels → régénération DÉLIBÉRÉE via `--update-snapshots` (aucune baseline n'est
  encore commitée dans le repo, donc aucun red de comparaison ; release-verify régénère de toute
  façon en `continue-on-error`). **mobile.spec (E16/MB6/VX190) + tablet.spec (VX68) : inchangés** —
  vérifiés contre le nouveau DOM par raisonnement : le board borné supprime le débordement
  horizontal page (le fix EST ce qu'E16/VX68 vérifient), `+ Nouveau lead`/`.header-title`/
  `article.kb-card`/`tr.lv-row`/`.bottom-tabbar` tous préservés. Playwright non exécutable ici (pas
  de node_modules) — les specs tournent au fold par l'orchestrateur (release-verify) ; `node
  --check` OK. Commande de régénération des goldens listée au rapport.

## Group F — Design foundation & tokens


## Group G — Primitive component library (shadcn-based; one "definition of done" per component: states, dark mode, keyboard, ARIA)


## Group H — DataTable engine (TanStack Table, behind every list view)


## Group I — App shell & navigation


## Group J — Per-module restyle (each: list → DataTable, forms → new primitives, modals → Dialog/Sheet, statuses → StatusPill, real empty/loading/error states, mobile pass)


## Group K — Dashboard & reporting


## Group L — Global UX behaviors


## Group M — Mobile & PWA polish (Meryem is iPhone-primary)


## Group N — Accessibility & quality floor (WCAG 2.2 AA)


## Group O — Performance


## Group P — Consistency & cleanup


## Pending Reda (carry these in the plan)
- Hard constraints (do not violate): never touch the devis/facture PDF templates, the public PDF pages, the PdfCanvas content, or the apps/web marketing site; STAGES.py stays a fixed CI contract; all schema changes additive/nullable, seeded from current in-code defaults.

---

### Group A — Devis acceptance, wired to Signé, facture & chantier (core unblock)

### Group B — Bug: file attachments

### Group C — Bug: navigation menu

### Group D — Paramètres: split + far more editable settings (all in one pass)



### Group E — End-to-end (E2E) browser test suite covering every screen flow

---

## DONE LOG (agent appends one plain-language line per completed task)

- 2026-07-13 — **QXG5 (partial — code guard only, task left `[ ]`).** The founder ops half (confirm `WEBSITE_LEADS_COMPANY_ID`/email backend keys/`PUBLIC_MAPTILER_KEY` are actually set in prod) is out of reach here and stays gated. Built the zero-cost code side: hardened both copies of `_resolve_company()` (`apps/crm/webhooks.py`, `apps/crm/public_chat_views.py`) so a missing/unset `WEBSITE_LEADS_COMPANY_ID` no longer silently mis-resolves — it now `logger.error`s LOUDLY when the var is unset AND 2+ `Company` rows exist (arbitrary "1st by pk" fallback = real tenant-misrouting risk), and when the var points at a non-existent pk. The safe fallback behaviour is unchanged (never breaks the public lead-webhook or livechat endpoints — "jamais perdre un lead"). 6 new tests (`ResolveCompanyGuardTests` in `apps/crm/tests_webhook.py` and `apps/crm/tests_xmkt37_livechat.py`): missing-var + 2 companies → loud error + safe fallback; missing-var + 1 company → no noise; bad pk → loud error + `None`. Task stays `[ ]` — founder must still confirm the prod env var (this only makes a misconfiguration VISIBLE, it doesn't fix the config itself).

- 2026-07-12 — **VX215 — boucle de retour « pris en charge » sur « Contacter mon supérieur ».** `[BACKEND minime]` nouvelle action lecture seule `GET /api/django/ventes/devis/<id>/superior-contact-status/` (`apps/ventes/views/devis.py`, `permission_classes=[IsAnyRole]`) déléguant à un nouveau sélecteur cross-app `notifications.selectors.superior_contact_status(company, link)` — relit les `Notification` déjà créées par `contacter_superieur` (même société + même `link`) et renvoie `{requested, seen, seen_by}` SANS jamais exposer le contenu (titre/corps) des notifications d'autrui, seulement si vues et par qui. Frontend : `ventesApi.superiorContactStatus`, `DevisList.jsx` affiche « Avis demandé — en attente » puis « Pris en charge par {nom} » sur la ligne du devis dès que le supérieur ouvre sa notification (sondage léger via le hook partagé `useVisibilityAwarePolling` — VX56 —, actif UNIQUEMENT tant qu'une demande reste non vue, jamais après). Tests : `apps/ventes/tests/test_vx215_superieur_contact_status.py` (backend, 5 cas dont l'isolation multi-société et la non-fuite entre devis) + `DevisListVX215SuperieurStatus.test.mjs` (source-grep, 6 cas — pas de node_modules dans cette lane). Files : `apps/ventes/views/devis.py`, `apps/notifications/selectors.py`, `frontend/src/api/ventesApi.js`, `frontend/src/pages/ventes/DevisList.jsx`.

- 2026-07-12 — **VX209 — `notify()` heures calmes + bonne @mention + purge + 2 events morts émis.** (a) `notify(respect_quiet_hours=True` par défaut) tait désormais email/WhatsApp/push (jamais l'in-app) pour un événement NON-critique quand l'instant tombe dans la fenêtre de silence de la société (`selectors.est_hors_fenetre_silence`) — un `INCIDENT_CRITICAL` part toujours. (b) `_notify_mentions` (`apps/records/views.py`) émet enfin `CHAT_MENTION` au lieu de `LEAD_ASSIGNED` — coupait silencieusement les mentions si un utilisateur désactivait `lead_assigned`, et `selectors.mentions_non_lues` (VX83 « Ma file ») filtrait déjà sur `CHAT_MENTION` sans jamais rien trouver. (c) tâche Celery `purge_notifications_anciennes` (nouvelle, planifiée dans `beat_schedule` + routée `scheduled`) : lues > 60 j supprimées, non-lues > 60 j archivées (`Notification.archived`, migration additive `0038`) ; `list()` bornée 90 j + non-archivées (les autres actions — détail/read/unread/read-all — restent sur la queryset complète). (d) `SAV_ACTIVITE_DUE` (activités `sav.TicketActiviteAFaire` échues non faites) et `STOCK_EXPIRATION_SOON` (lots `stock.LotEntrepot` proches péremption avec reliquat) sont désormais réellement émis par `sweep_daily` ; warranty/maintenance routent vers le technicien responsable du chantier quand il existe (repli managers inchangé). Corrigé 3 tests existants rendus flaky par le nouveau défaut heures-calmes (QW8/VX76/YEVNT5 — événements non-critiques testés sans horloge figée) en gelant l'horloge sur un jour ouvré en journée. Files : `apps/notifications/{models,services,sweeps,views}.py` + migration `0038_vx209_notification_archived.py`, `apps/records/views.py`, `erp_agentique/celery.py`, `erp_agentique/settings/base.py`, nouveau `apps/notifications/tests_vx209_notify_humain.py` + tests ajoutés dans `apps/records/tests.py`.

- 2026-07-12 — **VX245 (already present)** — verified: `build_ics` extracted as pure function (`apps/reporting/calendar.py:366`), `GET /crm/appointments/<id>/ics/` endpoint referenced in `apps/crm/services.py:2529`, WhatsApp confirmation + invoice-reminder message service present; commit `94060cca` on main. Ticked, no rebuild.

- 2026-07-12 — **VX217 (already present)** — verified: `frontend/src/features/queue/AttentionPeek.jsx` (+ test) wired into `NotificationBell.jsx` and `MesActivitesPage.jsx` (hover/tap-and-hold peek), grouped "Tout marquer lu (n)" action, `.nb-panel` mobile responsiveness; commit `a2c18fbb` on main. Ticked, no rebuild.

- 2026-07-12 — **VX214 (already present)** — verified: `apps/records/views.py` `ma-file/` extended with execution kinds (`chantier_assigne`/`intervention_du_jour`/`da_approuvee_a_commander`/`ticket_transfere`) via `installations.selectors.affectations_pour`/`sav.selectors.affectations_pour` (no parallel endpoint/page); `tests_vx214_kinds_execution.py`; commits `3178b30f` + CI fix `956c5b9e` on main. Ticked, no rebuild.

- 2026-07-12 — **VX212 (already present)** — verified: `Notification.reason` field + `NotificationReason` choices (`models.py:240`), `resolve_recipients_reason` (`services.py:304`), reason rendered in serializer + `NotificationBell.jsx`, approval email context; `tests_vx212_pourquoi_je_recois_ca.py`; commit `69bcf900` on main. Ticked, no rebuild.

- 2026-07-12 — **VX211 (already present)** — verified: `frontend/src/features/queue/queueViews.js` (+ `queueViews.test.js`) provides `queueViewForRole` persona ordering, `apps/records/views.py` exposes `effort_estime` per-kind (`_EFFORT_ESTIME_PAR_KIND`) for the "victoires rapides" secondary sort; commit `782b5c92` on main. Ticked, no rebuild.

- 2026-07-12 — **VX210 (already present)** — verified: sweep `reveiller_snoozes` (Celery task, `sweeps.py:553`) wakes both `records.Activity.snoozed_until` and the new `notifications.SnoozedItem` (approvals), `records.Activity.snooze_trigger_event` (closed choices, `records/services.py:181-313`) subscribed via events; `tests_vx210_reveil_snooze.py` covers both exit paths; commit `9eccf915` on main. Ticked, no rebuild.

- 2026-07-12 — **VX208 (already present)** — verified: `apps/notifications/severity.py` (EVENT_SEVERITY/EVENT_CATEGORY dicts), serializer exposure, NotificationBell severity/category grouping + digest-excluded-from-badge + undo-via-mark_unread already shipped with `tests_vx208_severity_taxonomy.py`, commit `5b99b234` on main. Ticked, no rebuild.

- 2026-07-12 — **VX207 (already present)** — verified during backend/notify lane drain: `GET /notifications/attention-summary/` (`views.py:438`, `urls.py:47`) already exists with a dedicated contract test (`tests_vx207_attention_summary.py`), commit `6e80ce75` on main. Ticked, no rebuild.

- 2026-07-12 — **VX127/VX128/VX129/VX130/VX132 (already present).** Verified already built by a prior wave: VX127 `readOnly` variant on Input/Textarea/Select (distinct from `disabled`, selectable/copiable) + `EditableCell` spinner-during-save/rejected-cell-reopens-with-message/`readOnly` prop. VX128 `aria-activedescendant` wired on Combobox/MultiSelect/TimePicker following the cursor. VX129 primitives completeness pack — DropdownMenu RadioItem/Sub/SubTrigger, ContextMenu CheckboxItem, Textarea autoResize+maxLength counter, Progress `indeterminate`, Stat lucide ArrowUp/ArrowDown (no more text glyphs), Avatar presence + AvatarGroup "+N", Tag/MultiSelect chips sharing `tagBase`, Popover/HoverCard opt-in `arrow`. VX130 Toaster `richColors` removed in favor of per-type token classNames, lucide icons, `[data-sonner-toast]` duration on `--motion-base`, `toastInfo`/`toastWarning`/`toastDestructive` (≥6s registry) in `lib/toast.js` — all within the task's declared Files scope (`ui/Toaster.jsx`/`lib/toast.js`/`index.css`); expanding real-world `toast.warning` adoption across other app files was left alone as out of this task's named-files scope. VX132 `Skeleton` shimmer, `FadeSwap` (built + tested, 0 current consumers — DoD doesn't require migration), DataTable skeleton rows `Math.min(pageSize, 12)`, `useDelayedLoading` on 15 files, `useRotatingLabel` wired on DevisList/FactureList PDF generation. No code changes.

- 2026-07-12 — **VX123 (already present).** Verified already built by a prior wave: `.focus-ring` utility (`design/tokens.css:418`) consumed everywhere (0 residual `focus-visible:ring-2 focus-visible:ring-ring` chains in `ui/`), the 4 remaining `outline: none` in `index.css` are all paired with their own focus indicator (not orphans), `@media (forced-colors: active)` maps card/table/modal/form/btn to real `CanvasText`/`ButtonBorder`/`Highlight` borders, `@media (prefers-contrast: more)` hardens `--border`/`--muted-foreground` via `color-mix`. No code changes.

- 2026-07-12 — **VX122 — voix typographique F121 (dernier volet réel : 3 recettes eyebrow encore en dur).** `.page-header h2`/`nbsp()`/`ArticleDetail` max-w-prose étaient déjà branchés par une vague antérieure ; `.text-eyebrow`/`--text-eyebrow-tracking` (tokens.css) existaient déjà et étaient consommés par 5 sélecteurs (`.gen-metric-label`/`.gen-chart-title`/`.gen-total-label`/`.gs-group-title`/`.cmdk-group-title`) mais PAS par les 3 recettes-tableau restantes : `.data-table th`/`.lines-table th`/`.cal-weekday` gardaient encore `letter-spacing: 0.04em` codé en dur (divergence résiduelle avec les 0.05em d'autres sélecteurs) — basculées sur le token unique.

- 2026-07-12 — **VX121 — zéro couleur hors token (dernier volet réel : AppointmentBooker).** Le sweep index.css (`scripts/check_hex.mjs`, 26 sélecteurs gardés, 0 hex) / DataTable `rgba(0,0,0…)` / `ChantierTimeline`/`ProductionPage` / bloc mort `.agent-*` était déjà fait par une vague antérieure — seul `AppointmentBooker.jsx` avait encore 4 fallbacks orphelins `var(--color-text-muted, #475569)` / `var(--color-success, #059669)` / `var(--color-surface-2, #f8f9fa)` / `var(--color-border, #e5e7eb)` (tokens qui n'existent nulle part dans `tokens.css` — silencieusement `unset` en dark mode). Remplacés par les vrais tokens déjà consommés plus haut dans le même fichier (`--muted-foreground`/`--success`/`--muted`/`--border`).

- 2026-07-12 — **VX166/VX168/VX169/VX170/VX171 (already present).** Verified already built by a prior wave: VX166 `confirmLeaveIfDirty`/`guardedClose` wired on the 7 named adopters + `CrudDialog.jsx` (8 compta callers). VX168 dirty-guard on all 9 `features/flotte/*Dialog.jsx` + 6 `features/gestion_projet/components/*Dialog.jsx` + `EmployeDetail.jsx`/`Recrutement.jsx`, `autoFocus` present on 38 files repo-wide incl. UsersManagement/RolesManagement/KpiAlertesPage/CrudDialog. VX169 `hooks/useNavigationGuard.js` (`useBlocker`) mounted on all 5 named screens (ParametresEntreprise, EquipementSignalerPage, DashboardConfigPage, ArticleEditor, ReclamationEditor). VX170 `ui/useFormSafety.js` (dirty diff + `useDirtyGuard` + `confirmLeaveIfDirty` + optional route-level guard) + `lib/safeStorage.js` (pagehide-safe persistence) built and consumed by ClientForm/CrudDialog/flotte dialogs. VX171 `hooks/useServerFieldErrors.js` consumed by Client/Lead/Devis/Facture/Produit forms with `clearField` on every `set()`. No code changes needed.

- 2026-07-12 — **VX182 — 7 modales fait-main hors LeadForm passées à ResponsiveDialog.** `PodCaptureDialog`, `TransfertsScreen` (CreateDemandeDialog), `ClientDetailPanel`, `ConvertirClientDialog`, `LeadInsightsDialog`, `PlanActiviteDialog`, `SigneDialog` : shell `.modal-overlay`/`.modal` brut remplacé par `ResponsiveDialog` (Escape + focus-trap + overlay-click + bottom-sheet mobile, `showClose={false}` — le ✕ existant reste l'unique fermeture visible), `autoFocus` posé sur le premier contrôle réel de chacun (5/7 en ont un ; les 2 panneaux lecture-seule `ClientDetailPanel`/`LeadInsightsDialog` s'appuient sur le focus-trap par défaut de Radix). `sd-modal` conservée en className sur `SigneDialog` (sélecteur CSS scopé `.sd-modal .form-label` intact).

- 2026-07-12 — **VX167 — LeadForm : dirty-tracking + garde de fermeture.** `isDirty` (déjà présent, VX224) branché sur `useDirtyGuard` (filet beforeunload) + `confirmLeaveIfDirty` posé sur les 3 chemins de fermeture volontaire (`onOpenChange` du `ResponsiveDialog`, bouton ✕, bouton Annuler du footer) — parité avec les 7 adoptants VX166.
- 2026-07-12 — **VX148 — Le kit `ui/charts` réellement adopté : fin des thèmes de tooltip recopiés et des rapports sans graphique.** NOTE : `Reporting.jsx`/`Rapports.jsx`/`Journal.jsx` étaient déjà largement migrés par une vague antérieure (VX28) — le travail restant identifié après relecture réelle du code (pas des n° de ligne du plan, obsolètes) : `Reporting.jsx` — le camembert (recharts natif, seule forme non couverte par le kit) perd son dernier dictionnaire `CHART_TOOLTIP_STYLE` local au profit de `<ChartTooltip>` (`ui/charts/ChartTooltip.jsx` gagne un repli `p.payload?.color` pour les Pie sans besoin de dupliquer un style) ; 3 `EmptyState` de cartes-graphiques → `ChartEmpty`. `Rapports.jsx` — `BarArrondie` ajouté AU-DESSUS de 3 tables comparatives (entonnoir ventes, stock par catégorie, chantiers par statut — la table garde le détail + les liens de drill-down) ; `EmptyState` du graphe Analytics → `ChartEmpty`. `Journal.jsx` — le graphe vide rendait un `<p>` nu → `ChartEmpty`. `PilotageStock.jsx` — la table « Prévisions de demande » (seule des 4 rapports encore sans graphique après VX33) gagne un `BarArrondie` « Top consommation mensuelle », même patron que top5Reappro/rotation. `ProductionPage.jsx` — l'écran le plus consulté du monitoring n'avait AUCUN graphique : courbe de tendance kWh (`AreaSansAxe`, pattern `OmAnalyticsPage.jsx`) dérivée des relevés déjà chargés, `buildProductionChartData` extraite en fonction pure testée. `CommercialDashboard.jsx` — `EmptyState` de l'entonnoir vide → `ChartEmpty` (`Dashboard.jsx`/`CohortsPage.jsx` l'avaient déjà, vérifiés sans changement). `grep "from 'recharts'"` sur les 3 fichiers cibles ne montre plus que le Pie de Reporting.jsx (forme non couverte). Tests : CommercialDashboard.test.jsx (cas ChartEmpty), ProductionPage.test.jsx (buildProductionChartData unitaire), node --test rapports-attribution (4/4 verts, non-régression).

- 2026-07-12 — **VX131 — Des états qui disent vrai : `tone` sur EmptyState, CTA sur les listes principales, page 403.** (a) `EmptyState.jsx` gagne `tone` (`neutral|error|warning`, calqué sur `ErrorBoundary`) qui colore bordure ET cercle d'icône ensemble (jamais l'icône seule) ; `DataTable.jsx` (erreur) et `ModuleDashboard.jsx` (erreur) migrés sur `tone="error"` — l'icône `AlertTriangle` restait grise malgré une bordure destructive. (b) `emptyAction` (nouvelle prop, filée `ListShell`→`DataTable`, les 2 sites de rendu desktop/mobile) : CTA identique à la toolbar sur 12 listes principales (ClientList, DemandesAchatList, ContratsList, KbPage, LitigesPage, ProjetsPage, FournisseursStock, NonConformites, ModelesBcf, ReceptionsFournisseur, BonsCommandeFournisseur, FacturesFournisseur) — StockList/DevisList/FactureList déjà conformes (vérifiées, non touchées) ; les CTA respectent les gardes de permission/état existants (`canWrite`/`peutEditer`/`bonsRecevables.length`). (c) `ui/Forbidden.jsx` (nouveau, jumeau de `NotFound.jsx`, tone="warning") câblé au routeur : `roleLoader` (`router/index.jsx`) redirige désormais un refus de rôle/permission vers `/403` (écran dédié) au lieu du `/dashboard` silencieux. Tests : `EmptyState.test.jsx` (3 tons), `DataTable.test.jsx` (emptyAction + tone error), `index.vx131Forbidden.test.mjs` (node --test, 4/4 verts).

- 2026-07-12 — **VX118 — [BUG] surfaces fantômes : Discuss + LeadExpress + kiosque TV migrées sur le kit existant, zéro CSS ajouté.** (a) Discuss (`ConversationList.jsx`, `MessageThread.jsx`, `Composer.jsx`) : les 11+ classes `chat-list-*`/`chat-thread-*`/`chat-pinned-*`/`chat-composer-*` sans AUCUNE règle CSS migrées vers `cn()`+Tailwind (bandeau épinglé désormais fond/bordure visibles, item actif/non-lu distincts) ; `ChatPage.jsx` déjà co-listait du Tailwind réel, non touché. (b) `LeadExpressModal.jsx` : les 23 références `lem-*` (0 CSS depuis sa création) remplacées par `Dialog`+`Form`/`FormField`/`FormActions` (le langage des autres dialogues CRM) ; le handler Échap manuel retiré (Radix Dialog le gère nativement). (c) `DashboardsTvPage.jsx` : `<pre>{JSON.stringify(current.layout)}</pre>` remplacé par un rendu réel avec le kit existant (`Card`+`ui/charts`) — grands chiffres `text-6xl` pour les widgets scalaires, `AreaSansAxe`/`KpiSpark` en grand pour les séries, `ChartEmpty` pour un widget sans donnée exploitable, `EmptyState` si le dashboard n'a aucun widget ; forme réelle du layout lue depuis `dashboardFilters.js` (`layout.widgets[]`, seule convention déjà établie dans le repo — aucun schéma de widget-type préexistant ailleurs). Tests : DashboardsTvPage.test.jsx (nouveau cas stats/charts + garde `<pre>`=0).

- 2026-07-12 — **VX232 — Les états financiers deviennent LISIBLES : noms réels, tableaux exploitables, exports hiérarchisés et traduits.** (a) `CockpitPage.jsx` KPI n°1 : `Tiers #42` résolu en nom réel — SCOPE ADAPTÉ EN FRONTEND-ONLY (le lane build-only ne touche pas le backend) : au lieu d'enrichir `apps/compta/selectors.py`, le cockpit charge une fois le répertoire unifié `apps/tiers` (`GET /tiers/tiers/`, timeout 4 s dédié, purement décoratif) et résout `tiers_id` côté client via `resolveTiersLabel` (export nommé, testé unitairement) ; repli « Tiers #N » identique si le tiers a été supprimé/pas encore chargé. (b) `EtatsPage.jsx` `GenericTable` migré du `<table>` HTML nu vers le primitif partagé `pages/reporting/Table.jsx`, plus tri au clic d'en-tête (ascendant/descendant, icônes lucide) — une balance rendue trie désormais au clic. (c)(d) `FiscalitePage.jsx` : les 6 exports fiscaux regroupés en 2 rangées sous-titrées « Mensuel » / « Annuel — exercice requis », chaque bouton (FEC/liasse/IS compris) porte désormais une phrase d'aide grise dédiée. Tests : `resolveTiersLabel` (unitaire) + `etats-page-sort.test.jsx` (rendu `report-table` + tri au clic). Backend inchangé — `apps/compta/selectors.py` non touché (hors périmètre de ce lane).

- 2026-07-12 — **VX229 — `CrudDialog` apprend le Combobox : fin des champs FK « (ID) » tapés à la main.** Nouveau type de champ `{name, label, async: () => Promise<{value,label}[]>, deriveFields?: (opt) => object}` dans `CrudDialog.jsx` — options chargées une fois à l'ouverture, mémoïsées, rendu en `Combobox` de recherche. Migré : `NotesDeFraisPage.jsx` 3× « Employé (ID) » → Combobox « Nom Prénom » (`rhApi.getEmployes`) ; `RapprochementsPage.jsx` « Compte de contrepartie (ID) » → Combobox comptes (`comptaApi.comptes.list`) ; `EngagementsPage.jsx` retenue de garantie : `tiers_nom` texte libre → Combobox du répertoire unifié `apps/tiers` (`tiers_id`/`tiers_type` réels, `tiers_nom` dérivé lecture seule via `deriveFields`, traçable vers la fiche tiers). `marche_ref`/Cautions bancaires laissés tels quels (string-ref intentionnel, aucun modèle tiers dédié côté backend — zéro migration). Tests `crud-dialog-combobox.test.jsx` (rendu Combobox + dérivation tiers_id/tiers_type/tiers_nom à la création). Frontend pur, zéro migration.

- 2026-07-12 — **VX228 — `RapprochementDetailDialog` : le contrat d'interaction complet du rapprochement bancaire.** `RapprochementsPage.jsx` gagne un dialog 2 volets (relevé | grand-livre pré-filtré montant) ouvert par clic de ligne (`bancaires`), consommant les 4 méthodes API déjà écrites (`lignesGl`/`resume`/`ajouterLigneReleve`/`pointer`) ; bandeau `resume()` en tête (solde relevé/pointé, écart) qui décroît EN DIRECT à chaque pointage, même langage visuel que le bandeau d'équilibre d'`EcrituresPage` ; « Suggestions » déplacée DANS le dialog (retirée des actions de ligne) ; « Clôturer » apparaît dans le dialog une fois l'écart à 0. Test `rapprochement-detail.test.jsx` (flux pointer→resume, écart 500→0). Frontend pur, zéro migration.

- 2026-07-11 — **VX152 — fin des moteurs de table parallèles (dernier volet, landé seul).** GED (`GedNavigator`/`GedSearch`), `ClientDetailPanel` et OCR (`OcrUpload`) rejoignent le moteur de table déjà utilisé par leur voisin direct : GedNavigator/GedSearch → moteur `DataTable` partagé (GedNavigator via l'échappatoire `renderRow`/`renderHeaderRow` ARC49 pour préserver le DOM testé ; GedSearch en colonnes), `ClientDetailPanel` → primitif `Table` partagé (fin du 3e moteur maison `DocTable` ; plus aucune `<table>` HTML), OcrUpload → NOUVEAU primitif partagé `ui/KeyValueTable` alimenté par un point de rendu UNIQUE de `FIELD_LABELS` (helper `ocrFieldRows`). + volet `RolesManagement` (liste des rôles → `DataTable`, grille de permissions inchangée). Tests de source `node --test` par surface ; tests comportementaux existants (GedNavigator/GedSearch/OcrUpload) verts par préservation du DOM (cases/actions/testids conservés). Frontend pur, zéro migration. Landé SEUL par cherry-pick sur `main` (les autres commits VX de la branche — VX141/146/147/148 — restent en attente : VX141 introduit `DEVIS_TRACK_STAGES` qui fait échouer `check_stages.py`, à traiter séparément). (ROUTINE)

- 2026-07-11 — **PLAN2 clean-lane wave 2 (8 lane-drainers) — 10 tasks folded onto batch, ~15 conflict-heavy tasks dropped+requeued to keep the batch clean.** LANDED : VX61 Web Vitals maison (INP/LCP/CLS/TTFB → endpoint reporting, AUCUNE dépendance) ; VX77 compression photo canvas avant upload terrain ; VX67 StateBlock+Réessayer sur 5 listes ; VX8 accent de couleur par module (7 jetons OKLCH AA) ; VX9 lanceur d'applications (overlay grille, `g a`) ; VX10 apps épinglées Sidebar ; VX11 fil d'Ariane cliquable ; VX12 « Plus » mobile = grille d'apps 2 niveaux ; VX13 hook `useEntitySearch` partagé (GlobalSearch+CommandPalette) ; VX46 « Mes préférences ». Fold-time : Login VX46↔VX65 réconcilié (`?next=` prioritaire sinon atterrissage) ; index.css VX9↔VX15 keep-both ; 6 lints react-hooks/react-refresh corrigés ; 2 tests réparés (vrais timers pour le rejet entityRoutes, requête `/Devis/` ambiguë BottomTabBar). DROPPED+REQUEUED (conflits lourds — reconstruire sur base fusionnée) : lane design VX1–7, crm VX192/VX221, grappe NotificationBell VX14/VX56/VX82, VX19 (sweep ~40 fichiers). Tout validé (eslint + vitest verts).

- 2026-07-11 — **PLAN2 clean-lane wave (8 time-balanced lane-drainers) — 17 tasks folded onto batch.** VX65 lien profond survit à la connexion (`?next=` sûr) ; VX78 vraie page 404 (ui/NotFound) ; VX57 CopilotPanel/Sora paresseux hors chemin froid ; VX58 préchargement au survol des destinations chaudes ; VX37 AgentChat reveal incrémental + mini-tableaux ; VX39 OCR source+extraction côte à côte, édition inline ; VX73 notice i18n honnête (chrome-only) + ⌘/Ctrl K réel ; VX74 [DECISION] note AR = documents-seulement (pas d'UI RTL) ; VX85 file records : snooze non destructif + notifs mentions/réassignation avec deep-link ; **VX101 [AUTH] seul Responsable/Admin décide une approbation installations/contrats (corrige un trou : un rôle normal pouvait décider)** ; **VX72 [DEP/DECISION] Sentry frontend no-op DSN-gaté — AUCUNE dépendance ajoutée (import à specifier variable, activé seulement si Reda installe @sentry/react + pose VITE_SENTRY_DSN)** ; VX115 KPI cockpit → écrans d'action + index des exports ; VX48 [BUG iOS] tous les PDF via onglet pré-ouvert (Safari) ; VX49 détection réelle du blocage popup + gestion d'erreur ; VX30 mur de flotte vivant (statut PR 3 paliers, pouls temps réel visibility-aware) ; VX84 cloche bornée à mes retards (assigned_to=moi) ; VX95 toastWithUndo câblé (archivage leads/stock, drop kanban). Fold-time (orchestrateur) : 5 lints react-hooks corrigés (setState-en-effet→phase de rendu sur Layout/AgentChat/OcrUpload, écriture de ref→effet sur FleetPage/Co2Page) ; **VX72 réparé** (le bare `import('@sentry/react')` cassait le build+6 suites → specifier variable) ; conflits imports LeadsPage/StockList/FactureList résolus en gardant les deux côtés. RE-MIS EN FILE (rebuild propre sur la base fusionnée) : VX97 (conflit massif avec la refonte menu VX20 de DevisList), VX114 (ma résolution take-ours a laissé tomber sa modale d'export → revert), VX116 (bug réel : annuler un aperçu WhatsApp le déclenchait quand même → revert). VX246 [BLOCKED: mal étiqueté @lane apps/records — c'est du frontend/iOS]. VX98 (agent mort erreur API) à reprendre.

- 2026-07-11 — **PLAN2 lane-drain wave (8 time-balanced agents) + tooling — folded onto accumulating batch (target ~60/merge, no per-wave merge).** `plan_lanes.py` gained LPT time-balancing across N workers (task `— S/M/L/XL` size → cost, whole lanes bin-packed so the 8 agents finish together; `--workers` flag; +8 tests). Then 17 tasks recovered from the lane-drainers (a mid-run Claude Code process restart killed the live agents; their COMMITTED work survived on the worktree branches and was cherry-picked): VX213 handoffs AVAL notifiés ; VX195 MapView role=application+liste clavier ; VX234 audit rôles au grain permission + garde réassignation ; VX242 ChangePassword révoque les autres sessions ; VX108 `lib/contactLinks` partagé (tel/wa) + câblage ; VX109 Importer/ExcelImport fournisseurs/équipements ; VX51 champ focalisé au-dessus du clavier iOS (VisualViewport) ; VX92 « Créer un autre » + mort du window.alert paiement ; VX183 densité kb-col iPad ; VX145 header CRM en menu d'actions + SavedViewsBar partagé ; VX218 badge « Nouveau » réception + escalade demandeur ; VX15 ModuleHero+sparklines ; VX137 table de lignes générateur en `ui/Input` ; VX139 `QuoteTotalsSummary` partagé (une seule devise MAD) ; VX20 menus Plus DevisList/RelancesPage/BulkActionBar ; VX21 squelette+cockpit trésorerie FactureList ; VX50 `data-label` FactureList/RelancesPage + garde CI. Fold-time (orchestrateur) : conflits FournisseurFiche360 (VX108↔VX149) et FactureList imports (VX21↔VX184) résolus en gardant les deux ; corrigé le test VX137 (assertion `12.` = artefact jsdom de `type=number`, remis sur le vrai contrat step="any" anti-arrondi) + polyfill ResizeObserver au test VX15. VX252 [BLOCKED: attend VX156 celebrate.js]. VX183 note : part agenda-view reste bloquée sur VX147 (MonthGrid). Reliquats de lanes (tâche en cours à la mort de chaque agent + non démarrées) re-dispatchés.

- 2026-07-11 — **PLAN2 wave 10 (VX113/VX204/VX149/VX43) — folded onto accumulating batch branch (no per-wave merge).** VX113 FiscalitePage : champ exercice = vrai `<select>` (comptaApi.exercices.list). VX204 quatre surfaces d'échec silencieux réparées (ChatterWidget/ActivitiesPanel/Journal getMeta + polling chat/cloche → bannière « Mise à jour interrompue »/Réessayer). VX149 `StatusAccentCard` partagé (kanban+terrain) + micro-pack dédup (InterventionsPage/InstallationsPage/MaJourneePage/FournisseurFiche360/ChantierPhotos/BulkProductBar/ChantierGateTimeline). VX43 gestes terrain : swipe-to-action (LeadCard/DataTable), pull-to-refresh (`usePullToRefresh`+`pullToRefreshMath`), bottom-sheet drag-to-close (Sheet) + MaJourneePage/InterventionsPage side="bottom" <768px. Fold-time : corrigé 5 lints invisibles aux agents sans node_modules — **hook `usePullToRefresh` appelé après un early-return dans InterventionsPage (rules-of-hooks, crash potentiel) hissé avant les returns**, `StatusAccentCard as:Comp`→`const Comp=as`, helpers swipe LeadCard dé-`export`és (react-refresh) + `SWIPE_OPEN_THRESHOLD` mort supprimé, directive `exhaustive-deps` inutile retirée de Journal. Conflits index.css (VX149↔VX204) + MaJourneePage/InterventionsPage (VX43↔VX149) auto-mergés.

- 2026-07-11 — **PLAN2 wave 9 (VX64/VX184/VX126/VX144), 4 lanes.** VX64 error boundaries sur les routes nues (/, /landing, /login, /ui, + flux publics tokenisés e-sign/kiosque/portail) → écran FR de récupération au lieu d'une page blanche sur un throw de rendu. VX184 tables produit de DevisForm/FactureForm migrées vers le pattern responsive partagé `.lines-table`/`data-label` (fin du scroll horizontal permanent mobile ; carte empilée <768px comme le générateur ; aucun changement >768px). VX126 utilitaire `press` partagé (mirroir de la courbe cubic-bezier de Button) appliqué à 12 primitives (Switch/Slider/Segmented/Tabs/Checkbox/RadioGroup/Select/Combobox/MultiSelect/DropdownMenu/ContextMenu/DatePicker) + Progress, halos/squish gated `hover:hover`, indicateurs `animate-pop-in`. VX144 (scope « rogné » (c)(d)(e), (a)(b) exclus car recoupent VX24/VX7) : cellule Client empilée déterministe à 200px (nom+toggle ligne 1, badge ICE ligne 2), note « non datés » du CalendarView en `var(--warning)`+AlertTriangle, carte funnel « Leads par étape » pleine largeur ≥1100px. Fold-time (orchestrateur) : corrigé la régression QX28 (VX143 avait dédupliqué le bouton 3D → test source-grep « deux occurrences » ramené à une) et ajouté un polyfill `ResizeObserver` au test interaction (Radix Slider). 3 agents morts d'erreur API (VX184/VX126/VX144, 0 commit) re-dispatchés à neuf — état partiel non fiable jeté. Conflits ClientList.jsx/index.css auto-mergés proprement (abort VX55 + cellule VX144 préservés).

- 2026-07-11 — **PLAN2 wave 8 (VX119/VX100/VX143/VX196), 4 lanes.** VX119 outbox terrain : une op rejetée par le serveur est désormais RETENUE (marquée `serverError`+`attempts`, jamais purgée en silence), badge rouge « N action(s) en échec » avec message par op + bouton Abandonner (`failed()`/`discard()`). VX100 approbations : montant réel (`DemandeAchat.montant_estime`) + lien non-fabriqué exposés dans l'agrégateur, `?trier=montant` réordonne vraiment, colonne Montant (`formatMAD`) + libellé cliquable dans ApprobationsPage. VX143 LeadForm refondu sur le langage composable FormSection/FormField/Input (comme ClientForm), rail tokenisé + badge Doublons, bouton toiture-3D dédupliqué, `STAGE_LABELS/PRIORITE_LABELS/TYPE_INSTALLATION_LABELS` importés de features/crm/stages.js (miroir STAGES.py) au lieu d'un doublon local. VX196 a11y WCAG 4.1.3 : régions live `role="log"`/`aria-live` + thread scrollable au clavier sur MessageThread & ChatterWidget, toasts d'erreur `assertive` (pont pub-sub vers une région `role="alert"` montée par Toaster, sonner n'exposant qu'une seule région polite). Fold conflict-free (seul index.css de VX143 auto-mergé vs wave 7). NOTE VX196 : item (c) drag-kanban `role="status"` hors périmètre (KanbanView/LeadsPage non nommés) — laissé pour un suivi.

- 2026-07-11 — **PLAN2 wave 7 (VX120/VX124/VX112/VX42), 4 lanes.** VX120 2FA : QR rendu serveur en SVG inline (via `apps/stock/labels.qr_svg`, aucune migration) au lieu d'un `<img src="api.qrserver.com">` tiers qui fuitait le secret TOTP + était bloqué par la CSP prod ; helper `lib/trustedSvg.js` (validation anti-script/on*/javascript:) + fallback gracieux. VX124 finitions design (caret brass sur Input/Textarea, ombre primary-hover, tabular-nums serrés, keyframe stat-solidify neutralisée sous reduced-motion). VX112 balance âgée : action ligne « Relancer » → `/ventes/relances?client=<id>` (RelancesPage lit `?client=`, badge « filtré » effaçable), PDF « Relevé » intact. VX42 terrain un-tap : boutons appeler/naviguer ≥44px, rail d'onglets icône+libellé + bandeau « Prochaine action », `FloatingActionButton` (safe-area) sur Ma journée/Numériser/Leads, retour haptique défensif (`lib/haptics.js`). Fold-time (orchestrateur, opus) : **corrigé un bug latent APP-WIDE — `<Button asChild>` crashait sous react-slot 1.3.0** (Slot exige `Children.count===1`, or Button passait `[false, enfant]`) ; le fragment spinner+enfants n'est désormais émis que hors-asChild — surfacé par le test « Relancer » de VX112. Corrigé aussi 3 défauts VX42 (EmptyState attend un composant pas un élément ; hoisting via `vi.hoisted` ; setState-en-effet → remount par `key`). Conflits LeadsPage.jsx/index.css (vs wave 6) auto-mergés proprement.

- 2026-07-11 — **PLAN2 wave 6 (VX55/VX60/VX86/VX31), 4 lanes file-disjoint.** VX55 discipline réseau : `timeout:20000` + branche `ECONNABORTED` (toast FR « La connexion a expiré ») sur l'instance axios, annulation native via `createAsyncThunk {signal}` + `thunk.abort()` au cleanup sur LeadsPage/DevisList/ClientList (RTK natif, câblage rétro-compatible des call-sites getLeads/getClients/getDevis). VX60 gate e2e « comptes justes » : seed >100 produits + >100 devis via `page.request`+cookie admin, asserte badge catalogue / KPI Dashboard / « N devis au total » = total réel (verrouille VX54), nettoyage `afterAll` pour ne pas polluer la base seed_demo. VX86 signal ambiant approbations : hook partagé `useApprobationsCount()` → badge sidebar + carte Dashboard « Attend votre décision » (top-3 urgence) + rangée cloche, tout masqué à 0. VX31 SAV boîte de réception : split-view liste+détail persistant ≥1280px (aside sticky), `Sheet` conservé en fallback mobile via `useIsMobile`, contenu factorisé identique. Folded conflict-free (frontend pur, zéro migration).

- 2026-07-11 — **PLAN2 wave (VX54/VX75/VX35/VX80).** VX54 pagination bornée-parallèle partagée (fin de la troncature page-1 silencieuse sur stock/ventes/crm/installations/sav) — débloque VX60. VX75 consolidation formatage argent/date sur lib/format.js (~90 sites / 51 fichiers) + garde CI toLocaleString ; bug CatalogueTable 450.00 vs 450,00 MAD corrigé (test mis à jour). VX35 Paramètres en barre latérale groupée (6 familles). VX80 feuille d'impression globale + boutons Imprimer (Devis/Facture/Chantier ; CSS print seulement, rule #4 intacte).

- 2026-07-11 — **PLAN2 wave (VX34/VX79).** VX34 Login tokenisé (OKLCH/lucide/reduced-motion). VX79 deep-links internes + « Lien interne » (Chantiers/SAV/Devis ; aria-label distinct du bouton WR2 « Copier le lien » de proposition — pas de collision de rôle ; rule #4 préservée). VX81 (noms d'export horodatés) re-mis en file : son mock global de document.createElement casse le DOM React (HierarchyRequestError) et régresse des tests PilotageStock existants — à reprendre avec un spy ciblé HTMLAnchorElement.

- 2026-07-11 — **PLAN2 wave (VX83/VX53).** VX83 « Ma file » file de travail unifiée reconstruite ADDITIVEMENT (ZSAL1/QX25/P167 préservés, node --test 8/0). VX53 compat hover (@media hover:hover ×68), dvh, images lazy hors-écran, toasts de copie. VX199 (AUTH ventes_valider) re-mis en file : la garde échoue encore (rôle read+write reçoit 200/400 au lieu de 403) — nécessite un test DB réel, HasPermissionOrLegacy à déboguer (has_erp_permission vs is_responsable).

- 2026-07-11 — **PLAN2 drain wave (6 lanes): VX76/VX157/VX96/VX59/VX32 + VX99 partial.** VX76 email HTML brandé, VX157 dashboards/monitoring tokenisés, VX96 Lead soft-delete réversible (+crm 0054), VX59 fuite chemin absolu chunk roof-tool corrigée (vite), VX32 CartePage tokenisée + tuiles dark-mode, VX99 notifications d'approbation installations.DemandeAchat + ged.DemandeApprobation (2/3). VX199 (AUTH accepter/emettre) et VX83 (« Ma file ») re-mis en file : VX199 a un bug de garde (403 manquant pour rôle read+write) et VX83 a régressé MesActivites (ZSAL1/QX25/P167) — à reprendre.

- 2026-07-10 — **Quote-journey ROUND 6 batch (QW8 + QX1–QX42 + QX7d + VX16/17/18) — 46 tasks shipped in one batch, 4 parallel worktree lanes.** Scoped run over the whole quote journey. Verified every task against real code first: **QW7 was already built** (webhook engagement-ping guard) → ticked « already present »; QF/QG/QP/QK/QJ were already drained (in DONE.md). QXG1–5 stay GATED (founder account/data/content). Lanes: (1) CRM intake — QX14 persist Lead.score on webhook leads, QX15 callback SLA clock on contact_preference_set_at, QX35 parrainage end-to-end, QX16 payload-replay surface, QX17 phone dedup, QX18 darija→langue_document, QX42 PII retention. (2) Ventes backend — **QX1 [CRITICAL] remise_globale now reaches the whole billing chain** (over-billing fixed, Facture totals gate on remise so 0-discount invoices stay byte-identical), QX2 discount in reporting/CAPI/UBL, **QX3 [SECURITY] fail-closed payments** (NoOp verify_webhook returns paid:False), QX9 real e-sign evidence + consent-400, QX10 OTP honest stub + lockout, QX11 scheduled 11 dead beat jobs + reachability guard, QX36 inbound-email wiring, QX13 visible nudges + shared client-links helper, QX30 engagement-triggered follow-up (race-safe), QX31 hot-lead escalation + time-to-first-touch, QX41 public hardening, QX33 deposit-at-signature, QX34 /suivi milestone endpoint, QX21 atomic devis save, QX22 truthful Envoyé, QX23 marge_snapshot (manager-only, never client), QX24 étude no longer goes stale, QX32/QX12/QX25 backend halves. (3) Quote engine (rule #4 — engine only renders) — QX4 de-Taqinorized residential PDF (+CompanyProfile capital/gerant/site_url), QX5 phantom-option gating, QX6 sign-QR→live proposal + real page numbers, QX7 numbers honesty (a/b/c/e) + **QX7d** unified avoided-kWh price (tranche-aware, not flat 1.75), QX8 warm-path caching, QX38 ONE canonical PVGIS productible (screen==PDF==web), QX39 honest 25-yr cashflow, QX40 pompage phase/voltage sanity, QX19/QX20 generator consumes lead data + equipment gate, VX16 summary rail, VX17 dark-mode tokens, VX18 DevisPresetPanel wired. (4) Frontend — QX12 deep-links, QX21/QX22 devis flows, QX26 structured loss reasons, QX27 action menu + typed chatter, QX28 readiness chips, QX29 « Relances du jour » board, QX25 call-ready rows, QX31 first-touch timer, QX30/QX32 timelines. Folded conflict-free (linear migrations: crm 0050-51, ventes 0075-77, notifications 0031-33, core 0027, parametres 0055). Adversarial review of the critical money/security/e-sign/webhook changes passed. NOTE: QX13 manual-contact suppression uses an optional crm selector `lead_recent_manual_contact` not yet added — inert until then (relance_date + engagement suppression work now).
- 2026-07-09 — **VX102 (built directly, founder request): « Demandes d'achat » frontend (FG310).** New `/chantiers/demandes-achat` page — DataTable list + create dialog (chantier, lines produit/désignation/quantité/prix estimé, priorité, date besoin), « Soumettre » on drafts, inline Approuver/Refuser shown only to the responsable/admin tier — reusing the existing installations endpoints (no backend change; a role-bearing technicien already passes create). Wired into router + Sidebar CHANTIERS; 4 vitest cases green, ESLint clean, vite build green. The FG310 approval box now receives real installations-sourced items. NOTE: the loose `IsResponsableOrAdmin`/`is_responsable` backend gate remains the systemic under-gating tracked by VX101; NTP2P3 (DemandeAchat form) is now largely satisfied — verify-not-already-built before a future NT run.
- 2026-06-20 — Logo resolved: the OS uses the official Taqinor wordmark (the repo's quote-engine logo) as product branding — real logo on the Login screen + iOS splash screens generated from it (`gen_brand_assets.py`), PWA icons already from its glyph; fixed the web-push notification icon path. Sidebar keeps the per-tenant company name.
- 2026-06-20 — G10 (first half) verified already-present: the lead model already carries `fbclid` + `utm_source/medium/campaign/content/term` (crm migration 0006), the website lead webhook maps and stores them (`apps/crm/webhooks.py`), and `apps/web` captures first-touch fbclid+UTM from the landing URL and submits them (`Layout.astro`, `lib/lead.ts`), covered by `apps/crm/tests_webhook.py`. Ticked `[x] (already present)`. The CAPI SEND (second half) stays gated on Reda's Meta pixel token.
- 2026-06-21 — Group Q (Q1–Q7) shipped: Devis↔Toiture-3D pipeline backend — Devis.roof_layout + layout endpoints, Lead roof_point/outline/bill_kwh + per-lead token, build_devis_from_layout() service, roof-image MinIO storage, layout-aware quote data (no-layout path byte-identical, rule #4), tokenized /proposal data endpoint + tokenized e-sign accept (reuses the existing acceptance service).
- 2026-06-21 — Group R agent framework (AG1–AG12) shipped: apps/agent registry + catalogue endpoint (AG1, NEW APP), FastAPI registry-driven tools with propose→confirm + signed-Redis stash + /confirm (AG2) and proposal/result surfaced on /query, assistant confirm/result cards (AG3), quote/invoice/payment + CRM/stock/SAV/installations agent actions (AG4–AG9), and the voice layer — Groq-Whisper transcribe endpoint (AG10, reuses GROQ_API_KEY) + voice input & hands-free conversation mode with a tested no-auto-confirm guard (AG11/AG12).
- 2026-06-21 — Group S internal team chat 'Discuss' (S1–S20) shipped: apps/chat (NEW APP) models/serializers/viewsets with strict company+membership scoping, read-state/unread, search, attachments+voice upload, reactions, pins, share-a-record via selectors, notifications+mute; self-hosted faster-whisper transcribe (S10, NEW founder-approved dep) + Django transcription pipeline (S11); full React UI (API client+slice+smart-polling, route/nav/bell, conversation list, thread, composer+@mentions, voice memos, reactions+pin UI, share-record cards, new-DM/channel/manage-members). Frontend↔backend API contract reconciled + mute/members/leave endpoints + mention persistence added.
- 2026-06-21 — Design & UI polish: F120–F123 (OKLCH brand ramps at ΔE≈0, type scale + tabular/slashed-zero numerals, elevation tokens + focus ring, dark-mode lightness ladder), G124–G128 (Tooltip/Button/IconButton/selectors/Form/DatePicker/TimePicker states+tokens, backward-compatible), and reporting K147/N161/K148/K149/J146/P167 (token-only accessible chart kit, dashboard KPI cards, fr-MA compact MAD formatting, unified table primitive).
- 2026-06-21 — P171 (ARCH): DataTable engine migrated to @tanstack/react-table behind an unchanged public API with full test parity (36 logic tests unchanged + 10 new engine-parity tests).
- 2026-06-21 — Policy: recorded founder standing consent (Reda) in CLAUDE.md lifting the ARCH/AUTH/COST/DECISION/GALLERY/DEP auto-skip gate (the five non-negotiable rules preserved).
- 2026-06-21 — BLOCKED & carried: S21 (real-time WebSocket/Channels) needs founder-provisioned ASGI+nginx-WS+Redis-channel-layer infra; I134/I138 (⌘K palette + shortcuts) need an architectural decision to reconcile with the already-wired providers/CommandPalette layer.
- 2026-06-21 — World-class look-and-feel wave (34 tasks) shipped in 2 tiers of parallel worktree lanes. Tier 1 (foundation): H129–H133+M154+N160+N162+O164+O166 premium DataTable (tabular nums, column pinning, row affordances + kebab/⌘K, floating bulk bar, perceived-perf skeletons, mobile card fallback, role=grid a11y, non-drag reorder, virtualization, memoised widths); I135–I137+L150+M155+M156+N159+N163+P168 calm sidebar/header/breadcrumbs + motion-token adoption + touch/safe-area pass + bottom-nav polish + never-hidden focus + reduced-motion + vitest-axe a11y tests + lucide icons; L151 useOptimisticSave + L153 useDelayedLoading + Skeleton variants; L152 confirm/toast helper (wraps existing ConfirmProvider); M158 ResponsiveDialog (Dialog↔Sheet); M157 PWA iOS polish; O165 route code-splitting (already lazy — locked with a contract test).
- 2026-06-21 — Tier 2 (page adoptions): J139 Clients + J140 Leads (STAGES-keyed, tokenised palettes, StatusPill, no-drag keyboard stage move, optimistic stage/status saves) + P169 inline-style removal; J141 Devis list/detail polish (skeletons, StatusPill, PDF + generator input-freedom untouched); J142 Stock catalogue → virtualised DataTable; J143 Installations skeletons + mobile; J144 SAV test coverage + StatusPill; J145 Admin Users → DataTable (ResponsiveDialog edit); P170 living /ui style guide. All e2e DOM-hook contracts preserved; ESLint 0 errors; node:test 322 pass; vitest 54 files/302 pass.
- 2026-06-22 — I134 (⌘K palette) shipped: reconciled with the live `providers/CommandPalette.jsx` (KEEP BOTH per founder note — no rebuild). Added a « Actions » navigation mode (derived from the `g x` shortcuts, single source of truth) + a « Récents » section of opened entities + a per-row shortcut chip. Pure logic extracted to `providers/commandActions.js` and unit-tested (`commandActions.test.mjs`, node:test, 5 cases). ⌘K stays single-bound (Header button + global shortcut only).
- 2026-06-22 — I138 ticked `[x] (already present)`: the live `providers/ShortcutsProvider.jsx` + `shortcuts.js` already deliver the Done bar — `?` help overlay + `g`-prefix navigation sequences + tests (`shortcuts.test.mjs`). The palette shortcut chips it referenced now ship via I134; `j/k` list traversal was a prose extra, not part of the Done bar.
- 2026-06-23 — Group U (U1–U14) shipped in 10 parallel worktree lanes, one self-merge. Per-task:
- 2026-06-23 — U1: lead edit modal now keeps the window open on « Mettre à jour » (in-place re-hydrate + « Enregistré » confirm), so a devis generated right after appears inline in LeadDevisPanel without reopening. (ROUTINE)
- 2026-06-23 — U2: fixed the ERP-wide mouse-wheel scroll regression — root cause was `overflow-x:hidden` creating an implicit scroll container + an unbounded `min-height:100vh` chain; switched to `overflow-x:clip` + bounded `#root`/`.layout` height + `min-height:0` on `.layout-content`, guard comments added. (ROUTINE)
- 2026-06-23 — U3: fixed mobile header overlap/stacking — `isolation:isolate` + `env(safe-area-inset-top)` + flex alignment so the header is one clean row under the notch; ⌘K hidden on mobile (duplicates the search loupe). (ROUTINE)
- 2026-06-23 — U4 (AUTH — a CRM action now changes a document status): WhatsApp-sharing a brouillon devis flips it to « envoyé » through the one status path (new `mark_devis_sent` service), stamps `date_envoi`, and advances the lead funnel to QUOTE_SENT via a NEW `core/events.py` `devis_sent` event (crm subscribes) — idempotent, never downgrades accepté/refusé. Additive migration `0027_devis_date_envoi`. (AUTH)
- 2026-06-23 — U5: the Devis list now surfaces the generated facture(s) + bon-de-commande inline as clickable chips (read-only serializer fields, no new write path). (ROUTINE)
- 2026-06-23 — U6 (ARCH — new cross-app event reaction): accepting a devis now auto-creates its chantier once (idempotent, company-scoped) via `apps/installations` subscribing to the existing `devis_accepted` event — no ventes→installations import. (ARCH)
- 2026-06-23 — U7: superseded devis revisions (`is_active=false`) are hidden by default with a « Voir les versions remplacées » toggle; shown rows are badged « Remplacé » + linked to the current version. (ROUTINE)
- 2026-06-23 — U8: the devis detail now shows its bon-commande status and warns when a devis is `accepté` but its BC is `annulé`/missing. (ROUTINE)
- 2026-06-23 — U9 (SCHEMA — stock side-effects on a new trigger): invoicing a devis directly via the échéancier `generer-facture` path now reserves/consumes stock once (mirrors the BC delivery path, same insufficient-stock guard), never double-counting when a BC already delivered. No migration. (SCHEMA)
- 2026-06-23 — U10: fully paying a facture now resets its relance/dunning escalation (clears `prochaine_relance`, neutralises the automatic RelanceLog counter, history preserved) so a paid invoice stops looking overdue. (ROUTINE)
- 2026-06-23 — U11 (DECISION — founder call, built FLAG-ONLY): a lead left at SIGNED whose only accepted devis is later refused is now flagged (`lead_signe_sans_devis_actif` derived flag + a chatter note via a `devis_refused` receiver) rather than silently receded — per rule #2 the funnel stays a separate layer. FOUNDER: confirm whether you want the stage to actually recede instead of just flag. (DECISION)
- 2026-06-23 — U12 (SCHEMA — additive nullable FK): Facture + BonCommande now carry a direct nullable `lead` FK (`crm.Lead`, SET_NULL, string-FK, snapshotted at creation), so a lead's documents are directly queryable even if the devis is deleted. Additive migration `0028_boncommande_lead_facture_lead` (renumbered from 0027 at fold to chain after U4's migration). related_names `factures_directes`/`bons_commande_directs`. (SCHEMA)
- 2026-06-23 — U13: profile-picture upload fixed end-to-end — avatars were served on an unreachable internal `minio:9000` presigned URL; now streamed through a new same-origin Django proxy `GET /api/django/users/avatar-image/` (mirrors the records attachment proxy), with an initials fallback on error. (ROUTINE)
- 2026-06-23 — U14: the « Documents (GED) » menu is now usable — create-cabinet/folder, rename/move, and document upload affordances + empty-state CTAs, wired to a thin company-scoped multipart action `POST /ged/documents/televerser/` reusing `records.storage`. (ROUTINE)
- 2026-07-02 — **Big PLAN2 drain (66 tasks) shipped in ONE run, one self-merge.** Groups: **QF1–9** (real-bill two-bills par-tranche savings screen==PDF, avec/sans-batterie honesty, Huawei-only Smart-Meter/Wifi), **QG1–12** (auto-open PDF, edit-invalidates-cache, inline new client/product role-gated, creator name+phone on quote, « Envoyer »=WhatsApp flow, configurable variante %, 3-variante dialog, embedded + standalone 3D RoofViewer), **QK1–6** (webhook keeps all captured lead data + new qualif fields, scoring uses them, financing block on PDF, « Nos hypothèses » transparency, dead /avis link→/realisations, bill-photo OCR), **QD1–2** (bigger invoice logo + clean client-bearing filenames), **QP1–2** (picker slot-type filter, role-gated line rename vs clone-to-stock), **QS1–4** (BCF PDF fix, inline product, WhatsApp+email supplier send), **QJ26–31** (roof-layout in proposal, «être contacté»/«contacter mon supérieur» notify handler+superior, multi-villa ×N/grouped one-document quote), **CH1–6** (international PV lifecycle gate model, blocking gates, IEC 62446-1 commissioning, handover pack, Directeur config, guided timeline UI), **MB1–6** (mobile shell clearance/overflow/z-index tokens, responsive modals, page sweep, Playwright mobile gate), **WR1–12** (funnel-integrity Refuser fix + surfaced ventes/stock/monitoring/CRM/SAV/paramètres orphaned backend features), **QC1** (own-data Moroccan company autocomplete + registry deep-links, provider seam). SCHEMA/AUTH highlights: ventes 0046 (multi-villa) + 0047 (BCF ShareLink), crm 0034 (lead qualif), parametres 0030 (variante %), notifications 0011/0012, installations 0049–0051 (gates) + 0052 (DC34), stock 0028 (DC34). **DC34** = destructive sous-traitant AP unification onto stock.Fournisseur(type)+SousTraitantProfile via FactureFournisseur/PaiementFournisseur (reversible data migration). **QG4** (AUTH) restricted product-create to Directeur + Commercial responsable — **FOUNDER: confirm Administrateur should lose product-create**. GATED/not built: **QC2** (paid Inforisk/Charika registry API — needs founder account). Validated pre-merge: makemigrations --check clean, flake8 + compileall clean, frontend eslint + vite build + 480 node tests green, combined docker test over affected apps.
