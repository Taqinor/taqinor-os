# Générateur de devis C&I — sessions L3 parallèles (fondateur, 27/10/2026)

Chaque session lit d'abord le **bloc commun**, puis **sa** section, et l'exécute de bout en bout.
Une session = une surface et des fichiers qui ne sont qu'à elle ; ses tâches vont dans le plan du
**propriétaire de chaque fichier** et sont construites dans la même session.
Version 2 — corrigée après la critique Fable du 27/10/2026 (claims, propriétaires, goldens, CODEMAP,
pile locale, budget Fable, procédure de rendu).

---

## Bloc commun

### 0. Démarrage
- **Précondition** : PR **#1070** (option « avec batterie ») et **#1074** (talon par activité, 23 activités) mergées sur `main`
  (`gh pr view 1070 --json state` / `1074`). La session coordinatrice (celle qui a écrit ce document) les fait passer et
  donne le feu vert. Si elles ne sont pas mergées : fais ton **R1 en lecture seule** et ne pousse rien.
- **Cohortes** : cohorte A (moteur) **CLD, CMP, CEC, CORC, CCAT, CSV** d'abord ; cohorte B (client et vendeur)
  **CVL, CGN, CPDF, CPRS, CPRW, CQST** quand la cohorte A a fait son premier merge. **CE2E** après toutes les autres.
- Branche depuis `origin/main` à jour : `claude/ci-<code>` (ex. `claude/ci-cld`).
- **Pas de claims entre ces 12 sessions** (les claims sont exclusives par app et bloqueraient 9 sessions sur 12) :
  l'exclusion, ce sont les listes de fichiers ci-dessous. Mais avant chaque vague, `python scripts/plan_claims.py list` :
  si une AUTRE session (autre poste, « work on all plans ») tient une app ou un plan que tu touches, attends son release.
- Propriétaire d'un fichier, toujours vérifié : `python scripts/check_ownership.py --owner-of <chemins>`.
  Une tâche va dans le plan de CE propriétaire (`devis` → `docs/plans/PLAN_AUDIT_DEVIS.md`, `lead` → `PLAN_AUDIT_LEAD.md`,
  `moteur` → `PLAN_AUDIT_MOTEUR.md`, `generateur` → `PLAN_AUDIT_GENERATEUR.md`, `stock` → `PLAN_AUDIT_STOCK.md`,
  `parametres` → `PLAN_AUDIT_PARAMETRES.md`, `web` → `docs/WEB_PLAN.md`, `deploy` → `PLAN_AUDIT_DEPLOY.md`) ;
  plusieurs propriétaires ⇒ `PLAN_AUDIT_TRANSVERSE.md`. Une session peut donc écrire dans plusieurs plans.
- Avant d'inventer : vérifier les tâches C&I encore ouvertes (CIQ220, CIQ221, CIQ425 gatées ; CIQM1-25 manuelles) — ne pas les refaire.

### 1. Décisions fondateur déjà prises (ne pas re-demander)
- **D-CIQ-0..22 et D-CIQ-26** : `docs/claude-memory/ci-decisions-fondateur.md`.
- **26-27/10/2026** : `docs/claude-memory/ci-decisions-2610.md` (onduleurs au moins d'appareils, taille avec regard sur les paliers
  suivants, devis préliminaire jamais vide, aucune incertitude imprimée, aucun « C&I » côté client, « Installation clé en main »,
  coffrets par onduleur + panneau, câbles 5×S Nexans, deux options sans/avec batterie, talon par activité en % du niveau de jour,
  23 activités, vrai nom d'activité au PDF, phrase soir/nuit).
- Règles maison : CLAUDE.md (règle #4 moteur PDF = rendu seul ; multi-tenant ; `selectors.py`/`services.py` entre apps ;
  `prix_achat` jamais côté client ; chiffres client réels, dérivés-traçables ou omis ; jamais `--force-wave`).

### 2. Méthode : plusieurs rounds L3 complets (skill `go-deep`, L3)
**Minimum 3 rounds complets**, puis jusqu'à **2 rounds consécutifs secs**. Un round = une vague = un merge.
1. **R1 COMPRENDRE** — code de ta surface + **rendu réel** (§4) ; liste numérotée de problèmes, chacun avec preuve.
2. **R2 CREUSER** — une lane par sous-partie indépendante (sonnet high ; opus sur moteur PDF / sécurité / migrations).
3. **R3 VALIDER** — chaque constat et solution vérifiés par des agents NEUFS, 2-3 angles (dont toujours « chiffres vérifiés /
   rien d'inventé » sur ce que voit le client). Constats contestés ⇒ **un** arbitrage Fable groupé.
4. **R4 REVUE + ŒIL CLIENT** — **un** appel Fable qui fait à la fois la critique de complétude et la relecture du rendu réel
   (chaque page PDF, chaque écran, chaque chiffre, chaque mot, desktop + mobile, FR/EN/AR).
5. **TÂCHES** — format v3 de `docs/audits/METHODE.md` (clauses calculées, test dans le module EXISTANT, `@model` explicite),
   sous un en-tête de groupe à toi `## Groupe <PRÉFIXE> — … · format v3` créé dès ta 1re PR. Décision qui n'est pas à toi ⇒
   question au fondateur (outil de question, recommandation en premier — jamais une liste dans un rapport).
6. **CONSTRUIRE** — lanes en worktree, un commit par tâche, au plus **3 lanes lourdes** à la fois par session (RAM partagée).
   Contrôles : `flake8`, `py_compile`, `PYTHONIOENCODING=utf-8 python scripts/check_forme_code.py --base origin/main`, eslint.
7. **TESTER** — **la CI vérifie d'abord** (une PR par vague, pas un push par tâche). Le harnais local
   (`powershell -File scripts/test-backend.ps1 -Parallel 1 -Modules "…"`) seulement en parallèle d'un run CI lancé :
   il est mono-écrivain et partagé par les 12 sessions — s'il refuse, on ne force pas. Puis rendu réel à nouveau (§4).
8. **MERGER** — avant le push : `git fetch origin && git merge origin/main`, goldens (§5), CODEMAP (§5).
   **Critique Fable pré-merge** de la vague. `gh pr merge --auto --merge` (merge queue). Rouge ⇒ corrigé dans la même vague.
   Aucun déploiement (Reda déploie). Puis round suivant sur le code mergé.

### 3. Fable — AUGMENTÉ mais tenable (fondateur : « pas réduire, augmenter »)
Par session et par round : **1** appel R4 + œil client, **1** critique pré-merge, **1** arbitrage R3 groupé si contesté
⇒ 2-3 appels Fable par round et par session (≈ 10 fois le plafond maison habituel), aucun pour les lanes de construction.
Cohortes de 6 pour ne pas épuiser la fenêtre d'usage commune. Une ligne DONE LOG par appel (à quoi il a servi, ce qu'il a trouvé).
Si la limite d'usage est atteinte : arrêter proprement le round, ne pas sauter la relecture Fable.

### 4. Rendu réel — ce que voit l'humain, pas un test vert
- **Données** : la pile docker locale (`docker compose`, projet `erp-agentique`) avec l'instantané **anonymisé** de la prod
  (`manage.py qa_import_anonymise`, cf. `docs/claude-memory/qa-coherence-auditor.md`, login `anon_admin`) + des leads de
  démo C&I (boulangerie 6 000 kWh/mois 7/7 6-22 h, bureau, hôtel, supermarché, industriel MT). **Aucune écriture en prod.**
- **Gardien de la pile = session CORC** : elle seule fait `migrate` / rebuild après un merge. Les autres ne migrent jamais la base de dev.
- **PDF depuis ta branche** : lancé DEPUIS ton worktree (le compose monte `./backend` de ce worktree) :
  `docker compose -p erp-agentique run --rm --no-deps django_core python manage.py shell` →
  `from apps.ventes.quote_engine.builder import build_quote_data` ; `from apps.ventes.quote_engine.generate_devis_premium import generate_premium_pdf` ;
  `generate_premium_pdf(build_quote_data(devis, options), '<chemin>')`, pour chaque scénario (avec / sans batterie, une page,
  premium, FR/EN/AR). Puis **lire chaque page** (outil Read sur le PDF). Si ta branche porte une migration non appliquée à la
  base de dev : demande au gardien, ou rends depuis les fixtures des tests.
- **Devis web / questionnaire** : `apps/web` en dev local (`npm run dev` dans ton worktree, jonction `node_modules`) +
  navigateur intégré, desktop et mobile. Au plus 2 `astro dev` en même temps sur la machine.
- Chaque constat « rendu » cite la capture ou la page PDF.

### 5. Fichiers, contrats, goldens, CODEMAP
- Tu n'édites QUE tes fichiers. Les autres : lecture seule, via `selectors.py`/`services.py`.
- Fichiers ≥ 2 000 lignes : aucune croissance nette ; préfère un module neuf de ta surface.
- **Contrat d'abord (PACT10/11)** : quand deux sessions partagent une forme de données, le contrat
  (`contract_samples/*.json`) est livré SEUL sur `main` par son propriétaire, et la tâche consommatrice porte `@after` sur
  la tâche productrice. Paires : CORC → CVL/CGN (`etude_ci_preview.json`) ; CPRS → CPRW (`proposal_*.json`) ;
  CQST backend → CQST page (`questionnaire_*.json`).
- **Goldens partagés** (`tests/golden/split_sd_rendu_html.json`, `golden/moteur/build_quote_data/*`) : presque chaque session
  les fait bouger. Avant CHAQUE push : merge `origin/main`, recapture (`SPLIT_GOLDEN_CAPTURE=1` / `UPDATE_GOLDEN=1`, harnais
  `-Parallel 1`), vérifie que seuls des hachages C&I bougent (résidentiel/agricole jamais), et liste-les dans la PR.
  Si la merge queue renvoie la PR pour un golden, re-synchronise et recapture.
- **CODEMAP** : nouveau module / route / modèle ⇒ régénérer §4 de `docs/CODEMAP.md` + `python scripts/codemap_fingerprint.py --write`
  dans le même commit ; conflit ⇒ prendre l'arbre fusionné et relancer `--write`.
- **Plans** : ton groupe à toi ; conflit textuel ⇒ garder les deux côtés.
- **Migrations** : avant d'en créer une, `git fetch` et prendre le numéro libre sur `origin/main` ; collision au merge ⇒
  `makemigrations --merge`, jamais renuméroter une migration déjà sur `main`.

### 6. Rapport (à chaque merge)
Français simple : ce qui change pour le vendeur / pour le client, pages PDF ou captures clés, tâches faites/restantes,
appels Fable et ce qu'ils ont trouvé, ce qui n'a PAS été vérifié.

---

## Sessions — cohorte A (moteur et données)

### CLD — Moteur : profil de charge et taille
- **Préfixe** `CLD` · **Plan** `PLAN_AUDIT_DEVIS.md`
- **Fichiers** : `apps/ventes/moteur_ci/{charge,profils,talons,categories,taille,degradation,reactif}.py`, `moteur_ci/donnees/archetypes_charge.json`.
- **Tests** : `test_ciq107/108/110/114/116/130/133/134/141*`, `test_ciq122_cas_reference`.
- **Axes** : profils et talons des 23 activités justes et sourcés ; horaires (nuit, équipes, fermetures, ramadan) qui changent
  vraiment le résultat ; relevés 12 mois / courbe mesurée ; facteur de puissance ; charge admissible du toit ; règle des 10 ans
  avec regard sur les paliers suivants, éprouvée sur boulangerie / bureau / hôtel / usine.

### CMP — Moteur : composition, onduleurs, batterie
- **Préfixe** `CMP` · **Plan** `PLAN_AUDIT_DEVIS.md`
- **Fichiers** : `moteur_ci/{composition,onduleurs,production,autoconso,batterie}.py`, `apps/ventes/domain/etude_ci_batterie.py`.
- **Tests** : `test_ciq109/111/115*` (`test_ciq116` est à CLD, `test_ciq120` à CORC — y ajouter des cas via ces sessions ou dans tes modules).
- **Axes** : bornes DC/AC « convention atelier, non sourcée » à sourcer ; chaînes réalistes (un 50 kW donnait 7 chaînes / 420 m DC) ;
  protections DC/AC, parafoudres, terre ; option batterie (taille, banque, hybrides BT, panneaux ajoutés) sur cas réels ; sections et quantités justes.

### CEC — Moteur : économie et tarifs
- **Préfixe** `CEC` · **Plan** `PLAN_AUDIT_DEVIS.md`
- **Fichiers** : `apps/ventes/{economie_ci,tarif_ci,economie_ci_view}.py`, `apps/ventes/domain/conditions_ci.py` (`economie_ci.py` ≥ 2 000 lignes : aucune croissance).
- **Tests** : `test_ciq203-209/231/233*`, `test_amot67*`.
- **Axes** : tarifs ONEE/distributeurs à jour et sourcés (BT patenté, force motrice, MT, bi-horaire) ; facture du client avant la grille ;
  indexation, dégradation, remplacement onduleur, O&M ; retour, TRI, VAN ; HT/TTC selon TVA récupérable ; économie de l'option batterie ;
  revente 82-21 ; scénario prudent. Recalcul à la main sur 3 cas comparé au PDF et à la page web.

### CORC — Orchestrateur d'étude, devis automatique, gardien de la pile
- **Préfixe** `CORC` · **Plan** `PLAN_AUDIT_DEVIS.md`
- **Fichiers** : `apps/ventes/domain/etude_ci.py`, chemin C&I de `apps/ventes/domain/creation_auto.py`, `apps/ventes/etude_ci_view.py`,
  `apps/ventes/contract_samples/etude_ci_preview.json`, `apps/crm/devis_selectors.py` (lecteurs C&I, propriétaire devis).
  (`apps/crm/devis_auto.py` est au propriétaire lead : session CVL.)
- **Tests** : `test_ciq117/118/119/120/121`.
- **Seule session** autorisée à éditer `etude_ci.py` / `creation_auto.py` ; une autre session qui a besoin d'un branchement y fait
  au plus un appel d'une ligne, fusionne `origin/main` juste avant de pousser, et le dit.
- **Gardien de la pile locale** : `migrate` + rebuild après chaque merge, instantané anonymisé, leads de démo C&I.
- **Axes** : refus qui nomment le champ du lead et la consigne au vendeur ; rafraîchissement et **devis révisé après visite** (V2) ;
  brouillons en double (le lead 1637 en a 4) ; idempotence ; performances (4 études par devis auto).

### CCAT — Catalogue et paramètres C&I
- **Préfixe** `CCAT` · **Plans** `PLAN_AUDIT_STOCK.md` (stock, `core/product_roles.py`) et `PLAN_AUDIT_PARAMETRES.md`
- **Fichiers** : `apps/stock/selectors.py::produits_ci` (3 668 lignes : aucune croissance), `core/product_roles.py`,
  articles C&I de `seed_catalogue.py`, `apps/parametres/serializers_company.py` (forfaits_ci, bande), `frontend/src/pages/parametres/DevisSection.jsx`, écrans stock des fiches C&I.
- **Tests** : `test_ciq101-103/123`, `tests_ciq105/202/211`, `DevisSection.ciq225.test`.
- **Axes** : l'admin voit d'un coup d'œil ce qui manque pour qu'un devis C&I soit chiffrable (prix, rôles, fiches) et le remplit sur place ;
  rôles hybrides/batteries sans ambiguïté ; fiches complètes ; barèmes éditables clairement. **Aucune écriture prod** sans accord explicite de Reda.

### CSV — Vendeur : questionnaire de suivi client (script d'appel, visite technique C&I)
- **Préfixe** `CSV` · **Plan** `PLAN_AUDIT_LEAD.md` (relances et visites = propriétaire lead)
- **Fichiers** : `frontend/src/features/crm/relances/**`, `apps/visites/visite_checklist.py` + écran de visite (parties C&I), parcours de suivi C&I.
- **Tests** : modules existants relances / visites / parcours (grep).
- **Axes** : le vendeur pose au téléphone, dans le bon ordre, les questions qui débloquent le devis C&I (contrat, phase, horaires,
  conso de nuit, puissance souscrite, toiture) ; la visite relève ce que le devis préliminaire a estimé (longueurs, pose, chaînes)
  et déclenche le devis révisé (avec CORC, contrat d'abord) ; aucune question en double avec le questionnaire client.

## Sessions — cohorte B (vendeur et client)

### CVL — Vendeur : fiche lead, devis automatique, envoi
- **Préfixe** `CVL` · **Plan** `PLAN_AUDIT_LEAD.md` (et `PLAN_AUDIT_DEVIS.md` pour `EnvoiDevisDialog`/`useDevisEnvoi` si propriétaire devis — vérifier)
- **Fichiers** : `frontend/src/features/crm/workspace/sections/SectionPro.jsx`, `DevisTab.jsx`, `devisTabLogique.js`,
  partie devis auto de `LeadWorkspace.jsx`, `EnvoiDevisDialog.jsx`, `pages/ventes/devisList/useDevisEnvoi.js`, `apps/crm/devis_auto.py`.
- **Tests** : `DevisTab*.test`, `devisAutoRequis.test.mjs`, `devisAutoKwc.ez5.test.mjs`, `SectionsRender.test.jsx`, `apps/crm/tests_devis_auto*`.
- **Axes** : champs requis visibles avant de cliquer ; modale « Devis automatique » qui dit ce qui manque et le fait remplir sur place ;
  choix sans/avec batterie ; **message reçu par le client** (e-mail / WhatsApp) relu comme un client ; zéro jargon moteur.

### CGN — Vendeur : écran générateur C&I, liste des devis, options PDF
- **Préfixe** `CGN` · **Plans** `PLAN_AUDIT_GENERATEUR.md` (`pages/ventes/generator/*`) et `PLAN_AUDIT_DEVIS.md` (le reste)
- **Fichiers** : `frontend/src/pages/ventes/generator/{PanneauCommercial,PanneauIndustriel,CarteResultatCi,CarteEconomieCi,CarteEcheancier,CarteFacturesElectriques,BlocEtudeReseau,ApercuSimulation}.jsx`,
  `frontend/src/features/ventes/etudeCi*.js`, `features/ventes/quote/{profilCi,etudeMarcheBloc}.js`, `MargeIndicative.jsx`,
  `pages/ventes/devisList/{DevisPdfDialog,useDevisPdf,DevisRow}.*`. (`DevisGenerator.jsx`, `solar.js` : lecture seule — fichiers neufs seulement.)
- **Tests** : `DevisGeneratorCategorieCommerciale.test`, `PanneauCommercial.test`, `profilCi.test`, `etudeMarcheBloc*.test`, `etudeCiPreview.test`, `DevisPdfDialog*.test`.
- **Axes** : l'écran montre la même chose que le PDF (taille, options sans/avec, économie, retour) ; édition des lignes qui garde l'étude
  cohérente ; marge indicative claire ; options PDF C&I utiles ; 100 % TTC, jamais un nombre corrigé de force ; liste des devis C&I lisible.

### CPDF — Client : PDF C&I
- **Préfixe** `CPDF` · **Plan** `PLAN_AUDIT_MOTEUR.md`
- **Fichiers** : `apps/ventes/quote_engine/{ci,commercial,industriel}/**`, parties C&I de `legacy_onepage.py`, module neuf
  `quote_engine/i18n_labels_ci.py` (aucune croissance de `i18n_labels.py` / `generate_devis_premium.py`).
- **Tests** : `test_ciq3xx*`, `test_qx43/45/46*`, `test_quote_engine_amot36*`, `test_ciq333/345`.
- **Axes** : un PDF qu'un patron de boulangerie ou un directeur d'usine comprend en 30 secondes ; deux options côte à côte ;
  « Installation clé en main » ; graphiques justes et lisibles ; aucune incertitude ; vrai nom d'activité ; FR/EN/AR sans faute ;
  aucune page qui déborde ; bon pour accord ; **devis révisé V2** et **une page**.
- **Rendu réel** : au moins 14 PDF par round (6 profils × avec/sans batterie + une page + EN/AR), chaque page lue.

### CPRS — Client : devis web, serveur (`/proposition`)
- **Préfixe** `CPRS` · **Plan** `PLAN_AUDIT_DEVIS.md`
- **Fichiers** : `apps/ventes/public/{payload_*,noyau,lecture_views,signature_views}.py`, `apps/ventes/public_urls.py`,
  `contract_samples/proposal_*.json` (`public_views.py` : lecture seule sauf un appel d'une ligne ; `paiement_views.py` = facturation, hors périmètre).
- **Tests** : `test_amot67`, tests publics C&I (grep `proposal`), `scripts/check_api_shapes.py`.
- **Axes** : la page sert exactement les chiffres du PDF (parité prouvée) ; deux options ; ligne Installation ; signature C&I ;
  niveau standard/confiance ; **notification « devis ouvert »** ; rien d'interne ne fuit. Contrat livré seul d'abord pour CPRW.

### CPRW — Client : devis web, page `apps/web` + entrée pro du site
- **Préfixe** `CPRW` · **Plan** `docs/WEB_PLAN.md` (n'édite que `apps/web/**`)
- **Fichiers** : `apps/web/src/lib/{proposition*,commercialCategories,propositionB2b}.ts`, `apps/web/src/components/proposition/**`,
  `apps/web/src/pages/proposition/[...token].astro` (12 000 lignes : extraire vers des composants, aucune croissance),
  `apps/web/src/pages/professionnel.astro`.
- **Tests** : `apps/web/tests/proposition*CIW*`, `industrielV2WJ123`, `commercialCategoriesWJ122`.
- **Axes** : page C&I mobile d'abord, aussi claire que la meilleure du marché ; comparaison sans/avec batterie ; signature fluide ;
  FR/EN/AR ; vitesse ; cohérence parfaite avec le PDF ; page « professionnel » qui amène au devis. `@after` sur le contrat CPRS.
  Le merge déploie le site (Cloudflare) — jamais `wrangler`.

### CQST — Client : questionnaire envoyé au client C&I
- **Préfixe** `CQST` · **Plans** `PLAN_AUDIT_LEAD.md` (backend crm) + `docs/WEB_PLAN.md` (page)
- **Fichiers** : `apps/crm/questionnaire.py`, `apps/crm/public_questionnaire_views.py`, `apps/web/src/lib/questionnaire.ts`,
  `apps/web/src/pages/questionnaire/[token].astro` (≥ 2 000 lignes : aucune croissance), `apps/web/src/pages/api/questionnaire-repondre.ts`, contrats `questionnaire_*.json`.
- **Tests** : `apps/crm/tests_ciq412/413`, `tests_qx51`, `apps/web/tests/questionnaire*`.
- **Axes** : un patron le remplit en 3 minutes sur son téléphone ; seulement ce qui manque au lead ; chaque réponse débloque vraiment
  le devis (preuve : devis auto après remplissage) ; photos de factures exploitées ; FR/EN/AR ; zéro jargon. Backend + contrat d'abord, page ensuite.

## Recette finale

### CE2E — Recette de bout en bout (après les 12 autres)
- **Préfixe** `CE2E` · **Plan** `PLAN_AUDIT_DEPLOY.md` (specs `frontend/e2e/acceptation/**` = propriétaire deploy) ; corrections routées au propriétaire du fichier.
- **Axes** : parcours complet sur la pile locale à jour : lead → questionnaire client → script d'appel → devis auto (sans/avec batterie)
  → PDF → page web → signature → visite → devis révisé ; 10 profils ; enregistrements `docs/audits/acceptation/…` ;
  relecture Fable de chaque sortie avec l'œil d'un client exigeant.
