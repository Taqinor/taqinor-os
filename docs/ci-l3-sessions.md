# Générateur de devis C&I — sessions L3 parallèles (fondateur, 27/10/2026)

Chaque session lit d'abord le **bloc commun**, puis **sa** section, et l'exécute de bout en bout.
Une session = une surface, des fichiers qui ne sont qu'à elle, des tâches ajoutées à son plan
propriétaire et construites dans la même session.

---

## Bloc commun (toutes les sessions)

### 0. Précondition
Ne commence rien avant que les PR **#1070** (option « avec batterie » C&I) et **#1074** (talon par
type de commerce, 23 activités, question « équipements hors horaires ») soient mergées sur `main`
(`gh pr view 1070 --json state` / `1074`). Branche ta session depuis `origin/main` à jour :
`claude/ci-<code>`. Réclame tes fichiers : `python scripts/plan_claims.py claim file:<plan propriétaire> app:<chaque app touchée>`
(refus ⇒ attends ou prends un autre morceau de ta surface ; `renew` à chaque round ; `release` après le merge).

### 1. Décisions fondateur déjà prises (ne pas re-demander)
- D-CIQ-0..26 : `docs/claude-memory/ci-decisions-fondateur.md`. Moteur serveur seul ; autoconso heure par heure ;
  règle des 10 ans ; anciens devis C&I oubliés ; bande prix/kWc interne jamais imprimée.
- 26-27/10/2026 (boulangerie, lead 1637) :
  - onduleurs : **le moins d'appareils d'abord**, puis le moins cher, sous la puissance souscrite déclarée ;
  - taille : un palier cher seul (saut d'onduleur) est gardé si **le groupe avec les paliers suivants** se rembourse en 10 ans ;
  - **devis préliminaire, jamais un prix vide** : câbles/structure estimés avant visite (DC = 2 × chaînes × 30 m,
    AC = 30 m/onduleur, toit inconnu = toit plat lesté) ; bandeau unique « Devis préliminaire — les prix pourront
    être ajustés après la visite technique » ;
  - **aucune incertitude imprimée** côté client (pas de « fiche muette », « hypothèse », « à confirmer », « prix ferme ») ;
  - **aucun « C&I »** dans ce que lit le client ; même article au même prix = une ligne ;
  - **une ligne « Installation clé en main »** regroupe les 8 prestations sur le document client (le devis interne garde le détail) ;
  - coffrets au barème **par onduleur + par panneau** ; câbles AC « 5×S mm² » Nexans ;
  - **deux options « sans / avec batterie » par défaut** (Deye BT hybrides + Dyness, banque homogène, soir/nuit couverts,
    panneaux ajoutés jusqu'à batterie pleine puis règle des 10 ans ; batterie sans prix ⇒ offre « sans » seule + alerte interne) ;
  - talon = % du niveau de jour, par type de commerce (20 % défaut fondateur) ; 23 activités ; vrai nom d'activité sur le PDF.
- Règles maison : CLAUDE.md (règle #4 moteur PDF = rendu seul ; multi-tenant ; `selectors.py`/`services.py` entre apps ;
  `prix_achat` jamais côté client ; chiffres client réels, dérivés-traçables ou omis).

### 2. Méthode : plusieurs rounds L3 complets (skill `go-deep`, niveau L3)
Au **minimum 3 rounds complets**, puis on continue jusqu'à **2 rounds consécutifs secs** (rien de nouveau de vrai).
Chaque round :
1. **R1 COMPRENDRE** — lire le code de ta surface ET regarder le **rendu réel** (voir §4) + les vraies données
   (production en LECTURE seule, cf. `docs/claude-memory/prod-read-access.md`) ; liste numérotée de problèmes, chacun avec preuve (fichier:ligne, capture, PDF page N).
2. **R2 CREUSER** — une lane par sous-partie indépendante, cause racine + solution concrète.
3. **R3 VALIDER** — chaque constat et chaque solution vérifiés par des agents NEUFS, 2-3 angles par constat
   (toujours un angle « chiffres vérifiés / rien d'inventé » sur ce que voit le client). **Fable** arbitre tout constat contesté.
4. **R4 REVUE** — **Fable** critique de complétude (« qu'est-ce qui manque ? une surface non vue, un chiffre non vérifié ? »).
5. **TÂCHES** — ajoute les tâches retenues à ton plan propriétaire (groupe à ton préfixe, format v3 de
   `docs/audits/METHODE.md` : clauses calculées, test dans le module existant, `@model` explicite). Une décision qui
   n'est pas à toi ⇒ question au fondateur (outil de question, recommandation en premier — jamais une liste dans un rapport).
6. **CONSTRUIRE** — lanes en worktree (`isolation: worktree`), sonnet par défaut, opus pour moteur PDF / sécurité / migrations ;
   un commit par tâche ; `flake8` + `py_compile` + `check_forme_code.py --base origin/main` + eslint sur les fichiers touchés.
7. **TESTER** — tests des modules touchés (CI d'abord ; harnais local `scripts/test-backend.ps1 -Parallel 1` seulement
   en parallèle d'un run CI lancé — il est mono-écrivain, d'autres sessions le partagent : s'il refuse, ne pas forcer) ;
   puis **regarder à nouveau le rendu réel** (§4) avec un **œil client critique Fable** : chaque page, chaque chiffre,
   chaque mot, mobile et desktop, FR/EN/AR.
8. **MERGER** — PR de la vague (tâches cochées + DONE LOG dans le plan), `gh pr merge --auto --merge` (merge queue),
   CI rouge ⇒ corrigé dans la même vague, jamais une vague empilée sur une rouge. **Fable critique pré-merge** de la vague.
   Aucun déploiement (Reda déploie). Puis round suivant, sur le code mergé.

### 3. Fable — utilisation AUGMENTÉE (fondateur, 27/10/2026 : « pas réduire, augmenter »)
Ce run dépasse volontairement le plafond maison 1-3 : Fable (effort high) à **chaque** R3 contesté, **chaque** R4,
**chaque** relecture « œil client » du rendu réel, et **chaque** critique pré-merge. Les constructeurs restent
sonnet/opus. Une ligne DONE LOG par appel Fable (à quoi il a servi, ce qu'il a trouvé).

### 4. Rendu réel — on regarde ce que voit l'humain, pas un test vert
- **PDF** : générer de vrais PDF (scénarios : boulangerie lead 1637 type, bureau, hôtel, industriel MT, avec et sans
  batterie, FR/EN/AR, une page et premium) dans ton scratchpad via le moteur (`build_quote_data` + `generate_premium_devis_pdf`
  dans le conteneur django du harnais, worktree monté), puis les **lire page par page** (outil Read sur le PDF).
- **Devis web** (`/proposition`) : `apps/web` en dev local (`npm run dev`, jonction node_modules) + navigateur intégré,
  desktop et mobile, chaque section, chaque chiffre comparé au PDF.
- **Questionnaires** : la page client (`/questionnaire/<token>`) et l'écran vendeur, parcourus comme un humain.
- **Production** : lecture seule via le navigateur intégré connecté à l'ERP (aperçu `etude-ci/preview` du lead 1637
  et de vrais leads C&I) — aucune écriture en prod.
Chaque constat « rendu » cite la capture / la page PDF.

### 5. Fichiers et coordination
- Tu n'édites QUE tes fichiers (ta section). Les autres : lecture seule, via `selectors.py`/`services.py`.
- Fichiers ≥ 2 000 lignes : aucune croissance nette (`check_forme_code`) ; préfère un module neuf de ta surface.
- `etude_ci.py`, `creation_auto.py` : propriétaire = session **CORC**. Une autre session qui a besoin d'un branchement
  y fait **au plus un appel d'une ligne** vers sa fonction neuve, fusionne `origin/main` juste avant de pousser, et le dit.
- Fichiers de plan : ajout en fin de groupe seulement ; conflit ⇒ garder les deux côtés.
- Avant chaque push : `git fetch origin && git merge origin/main`.
- Goldens : recapture seulement si TES hachages bougent (résidentiel/agricole jamais) ; vérifier le diff.

### 6. Rapport (à chaque merge)
Français simple : ce qui a changé pour le vendeur / pour le client, captures ou pages PDF clés, tâches faites/restantes,
appels Fable et ce qu'ils ont trouvé, ce qui n'a PAS été vérifié.

---

## Sessions

### CLD — Moteur : profil de charge et taille
- **Préfixe tâches** : `CLD` · **Plan** : `docs/plans/PLAN_AUDIT_DEVIS.md`
- **Fichiers** : `backend/django_core/apps/ventes/moteur_ci/{charge,profils,talons,categories,taille,degradation,reactif}.py`,
  `moteur_ci/donnees/archetypes_charge.json`.
- **Tests** : `test_ciq107/108/110/114/116/130/133/134/141*`, `test_ciq122_cas_reference`.
- **Axes de départ** : profils par activité (23 types) justes et sourcés ; horaires (dont nuit, équipes, fermetures, ramadan) qui changent vraiment
  le résultat ; courbe mesurée / relevés 12 mois ; facteur de puissance ; contrainte de charge du toit ; règle des 10 ans + regard
  sur les paliers suivants testée sur des cas réels (boulangerie, bureau, hôtel, usine).
- **Rendu réel** : aperçu prod du lead 1637 et de 5 vrais leads C&I, avant/après, horaires variés.

### CMP — Moteur : composition, onduleurs, batterie
- **Préfixe** : `CMP` · **Plan** : `docs/plans/PLAN_AUDIT_DEVIS.md`
- **Fichiers** : `moteur_ci/{composition,onduleurs,production,autoconso,batterie}.py`, `apps/ventes/domain/etude_ci_batterie.py`.
- **Tests** : `test_ciq109/111/115*`, `test_ciq116`, `test_ciq120` (classe batterie).
- **Axes** : bornes DC/AC « convention atelier, non sourcée » (`onduleurs.py`) à sourcer ; chaînes/strings réalistes
  (le 50 kW donnait 7 strings / 420 m DC) ; protections DC/AC, parafoudres, terre ; option batterie (taille, banque, hybrides,
  panneaux ajoutés) vérifiée sur cas réels ; quantités et sections justes.
- **Rendu réel** : lignes du devis automatique sur 6 profils ; PDF équipement.

### CEC — Moteur : économie et tarifs
- **Préfixe** : `CEC` · **Plan** : `docs/plans/PLAN_AUDIT_DEVIS.md`
- **Fichiers** : `apps/ventes/{economie_ci,tarif_ci,economie_ci_view,etude_ci_view}.py`, `apps/ventes/domain/conditions_ci.py`.
- **Tests** : `test_ciq203-209/231/233*`, `test_amot67*`.
- **Axes** : tarifs ONEE/distributeurs à jour et sourcés (BT patenté, force motrice, MT, bi-horaire) ; facture du client > grille ;
  indexation, dégradation, remplacement onduleur, O&M ; retour, TRI, VAN ; HT/TTC selon TVA récupérable ; économie de
  l'option batterie ; revente 82-21 ; scénario prudent.
- **Rendu réel** : chiffres d'économie du PDF et de la page web recalculés à la main sur 3 cas.

### CORC — Orchestrateur d'étude et devis automatique
- **Préfixe** : `CORC` · **Plan** : `docs/plans/PLAN_AUDIT_DEVIS.md`
- **Fichiers** : `apps/ventes/domain/etude_ci.py`, chemin C&I de `apps/ventes/domain/creation_auto.py`,
  `apps/crm/devis_auto.py`, `apps/crm/devis_selectors.py` (lecteurs C&I).
- **Tests** : `test_ciq117/118/119/120/121`, `apps/crm/tests_devis_auto*`.
- **Axes** : messages de refus (champ du lead nommé, consigne au vendeur) ; rafraîchissement d'un devis modifié ; brouillons
  en double (le lead 1637 en a 4) ; idempotence ; performances (4 études par devis auto) ; branchement propre des autres sessions.
- **Rendu réel** : le bouton « Devis automatique » sur des leads incomplets et complets (prod lecture + local).

### CVL — Vendeur : fiche lead et devis automatique
- **Préfixe** : `CVL` · **Plan** : `docs/plans/PLAN_AUDIT_LEAD.md`
- **Fichiers** : `frontend/src/features/crm/workspace/sections/SectionPro.jsx`, `DevisTab.jsx`, `devisTabLogique.js`,
  `LeadWorkspace.jsx` (partie devis auto), `EnvoiDevisDialog.jsx`.
- **Tests** : `DevisTab*.test`, `devisAutoRequis.test.mjs`, `devisAutoKwc.ez5.test.mjs`, `SectionsRender.test.jsx`.
- **Axes** : saisie pro rapide et guidée (champs requis visibles avant de cliquer) ; modale « Devis automatique » qui explique
  ce qui manque et propose de le remplir sur place ; choix sans/avec batterie ; envoi du devis ; zéro jargon moteur.
- **Rendu réel** : parcours vendeur complet en local (navigateur), desktop + mobile, avec un vrai vendeur en tête (Meryem).

### CSV — Vendeur : questionnaire de suivi client (script d'appel, visite technique C&I)
- **Préfixe** : `CSV` · **Plan** : `docs/plans/PLAN_AUDIT_LEAD.md` (crm) et le plan propriétaire de `apps/visites` (lire `docs/ownership.yml`)
- **Fichiers** : `frontend/src/features/crm/relances/**` (script d'appel, `appelGuidance.js`, panneau d'appel), la checklist C&I
  de la visite technique (`apps/visites/visite_checklist.py` + écran visite), le parcours de suivi C&I (`parcours_suivi.json` côté C&I).
- **Tests** : modules existants de relances / visites / parcours (grep).
- **Axes** : que le vendeur pose au téléphone les questions qui débloquent le devis C&I (contrat, phase, horaires, conso de nuit,
  puissance souscrite, toiture) dans le bon ordre ; la visite technique relève ce que le devis préliminaire a estimé
  (longueurs câbles, type de pose, chaînes) et le devis se met à jour ; aucune question en double avec le questionnaire client.
- **Rendu réel** : script d'appel et visite parcourus en local comme Meryem et comme le technicien.

### CGN — Vendeur : écran générateur C&I et boîte d'options PDF
- **Préfixe** : `CGN` · **Plan** : `docs/plans/PLAN_AUDIT_GENERATEUR.md`
- **Fichiers** : `frontend/src/pages/ventes/generator/{PanneauCommercial,PanneauIndustriel,CarteResultatCi,CarteEconomieCi,CarteEcheancier,CarteFacturesElectriques,BlocEtudeReseau,ApercuSimulation}.jsx`,
  `frontend/src/features/ventes/etudeCi*.js`, `features/ventes/quote/{profilCi,etudeMarcheBloc}.js`, `MargeIndicative.jsx`,
  `pages/ventes/devisList/{DevisPdfDialog,useDevisPdf,useDevisEnvoi}.*`. (`DevisGenerator.jsx`, `solar.js` : lecture seule — nouveaux fichiers seulement.)
- **Tests** : `DevisGeneratorCategorieCommerciale.test`, `PanneauCommercial.test`, `profilCi.test`, `etudeMarcheBloc*.test`, `etudeCiPreview.test`, `DevisPdfDialog*.test`.
- **Axes** : l'écran montre la même chose que le PDF (taille, options sans/avec, économie, retour) ; édition des lignes qui
  garde l'étude cohérente ; marge indicative claire ; options PDF C&I utiles ; 100 % TTC, jamais de nombre corrigé de force.
- **Rendu réel** : générateur en local, desktop + mobile, comparé ligne à ligne au PDF.

### CPDF — Client : PDF C&I
- **Préfixe** : `CPDF` · **Plan** : `docs/plans/PLAN_AUDIT_MOTEUR.md`
- **Fichiers** : `backend/django_core/apps/ventes/quote_engine/{ci,commercial,industriel}/**`, parties C&I de `legacy_onepage.py` ;
  nouvelles clés dans un module neuf `quote_engine/i18n_labels_ci.py` (pas de croissance de `i18n_labels.py` / `generate_devis_premium.py`).
- **Tests** : `test_ciq3xx*`, `test_qx43/45/46*`, `test_quote_engine_amot36*`, `test_ciq333/345` (langues).
- **Axes** : un PDF qu'un patron de boulangerie ou un directeur d'usine comprend en 30 secondes ; deux options côte à côte ;
  « Installation clé en main » ; graphiques justes et lisibles ; aucune incertitude ; vrai nom d'activité ; FR/EN/AR sans faute ;
  pages qui ne débordent jamais ; signature/bon pour accord.
- **Rendu réel** : 12 PDF minimum par round (6 profils × avec/sans batterie, + EN/AR), lus page par page par Fable.

### CPRS — Client : devis web (serveur `/proposition`)
- **Préfixe** : `CPRS` · **Plan** : `docs/plans/PLAN_AUDIT_DEVIS.md`
- **Fichiers** : `apps/ventes/public/{payload_*,noyau,lecture_views,signature_views}.py`, `apps/ventes/public_urls.py`
  (`public_views.py` : lecture seule sauf un appel d'une ligne). Contrat d'abord : `apps/ventes/contract_samples/proposal_*.json`.
- **Tests** : `test_amot67`, tests publics C&I (grep `proposal`), contrats `check_api_shapes`.
- **Axes** : la page sert exactement les chiffres du PDF (parité prouvée) ; deux options ; ligne Installation ; signature et
  acompte C&I ; niveau standard/confiance ; rien d'interne ne fuit.
- **Rendu réel** : payload JSON comparé au PDF sur 6 cas ; coordination avec CPRW par le contrat.

### CPRW — Client : devis web (page `apps/web`)
- **Préfixe** : `CPRW` · **Plan** : `docs/WEB_PLAN.md` (n'édite que `apps/web/**`)
- **Fichiers** : `apps/web/src/lib/{proposition*,commercialCategories}.ts`, `apps/web/src/components/proposition/**`,
  `apps/web/src/pages/proposition/[...token].astro` (fichier de 12 000 lignes : extraire vers des composants, aucune croissance).
- **Tests** : `apps/web/tests/proposition*CIW*`, `industrielV2WJ123`, `commercialCategoriesWJ122`.
- **Axes** : page C&I aussi claire que la meilleure page de devis solaire du marché, mobile d'abord ; comparaison sans/avec
  batterie ; signature fluide ; FR/EN/AR ; vitesse ; cohérence parfaite avec le PDF. Le merge déploie le site (Cloudflare) — jamais `wrangler`.
- **Rendu réel** : page en local sur 6 propositions réelles (données de test), captures desktop + mobile chaque round.

### CQST — Client : questionnaire envoyé au client C&I
- **Préfixe** : `CQST` · **Plan** : `docs/plans/PLAN_AUDIT_LEAD.md` (backend crm) + `docs/WEB_PLAN.md` (page)
- **Fichiers** : `apps/crm/questionnaire.py`, `apps/crm/public_questionnaire_views.py`, `apps/web/src/lib/questionnaire.ts`,
  `apps/web/src/pages/questionnaire/[token].astro`, `apps/web/src/pages/api/questionnaire-repondre.ts`, contrats `questionnaire_*.json`.
- **Tests** : `apps/crm/tests_ciq412/413`, `tests_qx51`, `apps/web/tests/questionnaire*`.
- **Axes** : un patron le remplit en 3 minutes sur son téléphone ; seulement ce qui manque au lead ; chaque réponse débloque
  vraiment le devis (preuve : devis auto après remplissage) ; photos de factures exploitées ; FR/EN/AR ; zéro jargon.
- **Rendu réel** : remplir le questionnaire en local comme un client (mobile), puis lancer le devis auto sur le lead obtenu.

### CCAT — Catalogue et paramètres C&I
- **Préfixe** : `CCAT` · **Plans** : `docs/plans/PLAN_AUDIT_STOCK.md` (stock) et `docs/plans/PLAN_AUDIT_PARAMETRES.md` (paramètres)
- **Fichiers** : `apps/stock/selectors.py::produits_ci` (fichier de 3 668 lignes : aucune croissance), `core/product_roles.py`,
  `apps/stock/management/commands/seed_catalogue.py` (articles C&I), `apps/parametres/serializers_company.py` (forfaits_ci, bande),
  `frontend/src/pages/parametres/DevisSection.jsx`, écrans stock des fiches C&I.
- **Tests** : `test_ciq101-103/123`, `tests_ciq105/202/211`, `DevisSection.ciq225.test`.
- **Axes** : l'admin voit d'un coup d'œil ce qui manque pour qu'un devis C&I soit chiffrable (prix, rôles, fiches) et le remplit
  sur place ; rôles C&I/hybrides/batteries sans ambiguïté ; fiches techniques complètes ; barèmes (coffrets, forfaits) éditables clairement.
- **Rendu réel** : écrans en local + état du catalogue de prod en lecture (aucune écriture prod sans accord explicite de Reda).

### CE2E — Recette finale de bout en bout (À LANCER APRÈS toutes les autres)
- **Préfixe** : `CE2E` · **Plan** : `docs/plans/PLAN_AUDIT_TRANSVERSE.md`
- **Fichiers** : aucun en propre ; corrections minimes routées au propriétaire du fichier, specs `frontend/e2e/acceptation/ci*.spec.js`.
- **Axes** : parcours complet sur la pile locale à jour : lead → questionnaire client → script d'appel → devis auto (sans/avec
  batterie) → PDF → page web → signature → visite → devis révisé ; 10 profils ; enregistrements d'acceptation
  `docs/audits/acceptation/…` ; Fable lit chaque sortie avec un œil de client exigeant.
