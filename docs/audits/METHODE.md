# Méthode d'audit TAQINOR OS (v2) — référence de la commande « audit »

*Version du 02/10/2026, établie sur `origin/main` `6742fc3a1`. Remplace le BLOC COMMUN et la table des
14 déclencheurs de `docs/claude-memory/audits-modules.md` (v1) ; les mots v1 restent acceptés (§D.4).
Opérationnel : `.claude/skills/audit/SKILL.md`. Registre partagé : `docs/audits/unites.yml`.*

**Statut des faits.** Les scripts, workflows, tests nommés et répertoires de contrats cités ici existent
sur `6742fc3a1` (vérifiés par commande le 02/10/2026) ; 7 chemins du découpage initial ont été corrigés
par la critique de complétude finale (§D.6 les donne sous leur forme corrigée). Les chiffres de couplage
de §D.1 viennent d'une lane de recherche dont les scripts ne sont pas conservés : ils sont à reproduire par
`scripts/audit_couplage.py` (§B, phase 4-a) avant toute réutilisation. Rien de ce document n'a été
exécuté comme audit : c'est une méthode, pas un résultat.

**Pourquoi une v2.** L'audit QJR5 (167 constats, 166 confirmés, 1 réfuté) a produit un build de 171
tâches qui a livré 14 défauts derrière des tâches cochées et une CI verte. Les causes, prouvées dans
`docs/claude-memory/lecons-construction-qjr5.md`, ne sont pas des défauts de *détection* : ce sont des
défauts de **spécification des contrôles**, de **format des tâches** et de **clôture**. La v2 rend la
preuve exécutée obligatoire et structurelle (une revue LLM sans preuve plafonne à ~17 % de précision —
SWR-Bench), répartit les tâches par propriétaire de fichiers pour que les builds tournent en parallèle
sans conflit, et tient l'avancement dans un registre versionné lisible depuis n'importe quel poste.

---

## §0 Commandes et progression

| Commande | Effet |
|---|---|
| `audit first` | audite l'unité de rang 1 du registre |
| `audit next` | audite la première unité (par rang) au statut « à auditer » et non réclamée (§D.5) |
| `continue audit` | reprend l'unité « en cours » (run interrompu ou lancé sur un autre poste) ; s'il n'y en a pas, équivaut à `audit next` |
| `loop audit` | enchaîne en mode `/loop` auto-rythmé : une unité par itération (audit → PR docs fusionnée → registre à jour → unité suivante) jusqu'à épuisement de la liste ou arrêt par Reda |
| `audit <mot>` | audite une unité précise, hors ordre (mots : §D.2 ; mots v1 : §D.4) |
| `audit <mot> L1\|L2\|L3` | impose le niveau (sinon niveau par défaut du registre, ajusté par l'auto-pick go-deep) |
| `audit <mot> contre-visite` | ré-audit par différence d'une unité déjà auditée (§C.4.4) |
| `audit status` | affiche le tableau classé des 19 unités avec leur état (registre + branches de claim vivantes) |
| `vérifie <GROUPE>` | vérification post-construction d'un groupe de tâches d'audit (§C.4.3) |

Les **précisions libres** tapées après la commande priment sur tout : elles restreignent le périmètre
(`audit stock prix`), désignent un jeu de données (`anon`), une persona, ou gravent une décision
fondateur. Toute décision à prendre pendant l'audit passe par `AskUserQuestion` (questions groupées,
option recommandée en premier), jamais par une liste en prose.

---

## §A Définition de la commande

### A.1 Ce que produit un audit

1. **Un dossier d'évaluation** `docs/audits/<AAAA-MM-JJ>-<mot>.md` (l'*evaluation record* d'ISO/IEC
   25040 : preuve objective documentée de chaque activité ; ISO/IEC 5055 : toutes les entrées — version
   du source, artefacts — listées pour qu'un tiers recalcule). Ordre : charte → spécification des
   contrôles → plan des lanes → manifeste de couverture (fichiers lus / **non lus** par lane, détecteurs
   exécutés / **non exécutés**, scénarios live joués / prévus) → registre des constats (§C.1) →
   non-risques avec hypothèses (ATAM) → verdicts de réfutation → rapport. **Plafond ≈ 400 lignes** : les
   sorties brutes des détecteurs restent dans le scratchpad de la session ; le dossier cite la commande
   exacte, le SHA et un extrait court.
2. **Des tâches routées par PROPRIÉTAIRE** (§D.3) : l'audit découvre par unité, mais chaque tâche va
   dans le fichier de plan du propriétaire des fichiers qu'elle édite —
   `docs/plans/PLAN_AUDIT_<UNITE>.md`, ou `docs/plans/PLAN_AUDIT_TRANSVERSE.md` si ses `Files:` couvrent
   plusieurs propriétaires. Format de groupe QJR5 (provenance, décisions gravées, séquencement, NE PAS
   FAIRE, non couvert, puis M0 contrats seuls → M1 bloquant-fondateur → M2 → M3 nettoyage et gardes →
   GATED), chaque tâche au format §C.2. Plus jamais de groupe d'audit dans `docs/PLAN2.md`.
3. **Des gardes permanentes**, une par *classe* de constat (Google, *Searching for Build Debt* : sans
   prévention la dette revient ; automatiser, rendre facile le bon geste, rendre difficile le mauvais) :
   tâches M3 (script `check_*.py`, contrat import-linter, test nommé, étape CI).
4. **La mise à jour du registre** `docs/audits/unites.yml` (statut `audité`, groupe, plans alimentés,
   PR, date) dans la même PR.
5. **Un rapport en français** : constats vérifiés / réfutés / renvoyés au fondateur, couverture
   chiffrée, ce qui n'a PAS été couvert, décisions prises, coût (agents, modèle par lane).
6. **UNE PR docs-only** en auto-merge (merge commit), poussée depuis la branche de claim `audit-<id>`
   après un `git fetch origin` immédiatement avant le push ; `python scripts/ci_guards.py stage-names`
   vert en local. Comme `docs/plans/*` est **hors de la surface du plan-fingerprint**, la PR ne touche
   **pas** CODEMAP §10 — sauf si elle édite aussi `docs/PLAN.md`, `docs/PLAN2.md` ou
   `docs/ERROR_PLAN.md` (alors : §10 rafraîchi + `python scripts/codemap_fingerprint.py --write` dans le
   même commit).

### A.2 Ce qu'un audit ne produit PAS

- Aucun code, correctif, migration ni dépendance (l'audit *rend* ; `work on the plan audit_<unité>`
  construit).
- Aucune exécution contre la production : le run live est TOUJOURS la pile locale (`localhost`), jeu
  `demo` ou `anon` (confidentiel : jamais de montant absolu du jeu anonymisé dans un constat, une
  capture ou un commit — règle qa-explorer).
- Jamais `seed_demo --force`, jamais d'envoi réel (e-mail / WhatsApp / SMS), jamais de campagne Meta,
  jamais de scraping, jamais de deploy (règle Deploys : Reda déploie).
- Pas de constat sans pointeur de preuve exécutée (§B phase 5) ; pas de « Nit » transformé en tâche.
- Pas de nouveau nom d'étape de pipeline, pas de chemin PDF devis alternatif (règles #2 et #4).

### A.3 Niveaux : go-deep L1-L3 ↔ rigueur ISO/IEC 25040

ISO/IEC 25040 définit *evaluation level* (profondeur des techniques), *stringency* (rigueur exigée par la
criticité), *coverage*, *decision criteria* et *evaluation records*. Le skill `go-deep` porte le choix
automatique du niveau (STAKES × BREADTH × UNCERTAINTY) ; le registre donne un niveau par défaut par unité,
que l'auto-pick peut relever (jamais abaisser sous L2 un sujet à chiffres client) et que Reda peut imposer.

| | **L1 « go deep »** | **L2 « go very deep »** | **L3 « go extremely deep »** |
|---|---|---|---|
| Quand | unité sans argent, sans sortie client, sans multi-société ; ou passe de confirmation | tout chiffre client, toute saisie propagée, OU 4-8 surfaces, OU terrain contesté (go-deep : checked-facts ⇒ ≥ L2) | argent + PDF/portail + multi-société + parcours chaud — **défaut pour J1b, J5, X1, X2, D2, D3** |
| Techniques | détecteurs mécaniques + lecture statique + CAAT, **sans pile** ; 1 vérificateur frais par constat | + walkthrough d'UNE transaction réelle en direct (Playwright) + rejeu indépendant ; 2 lentilles sur les constats critiques | + jeu `anon` obligatoire ; 2-3 passes de recherche indépendantes sur les surfaces à risque ; 2-3 lentilles par constat ; boucle jusqu'à sec (2 tours sans nouveauté, plafond ~5) ; Fable 1-3 |
| Couverture rapportée | % de contrôles spécifiés exécutés ; fichiers non lus listés | idem + scénarios live joués / prévus | idem + non-risques consignés avec hypothèses |
| Agents | ~3-7 | ~8-15 | ~15-35 |

Escalade en cours de route autorisée et annoncée en une ligne (un chiffre client inventé découvert en R1
⇒ L3). L'agrégation de plusieurs passes indépendantes est sourcée (SWR-Bench : F1 +43 %, rappel +119 % en
agrégeant 10 passes) ; elle s'achète par profondeur de lane, jamais par nombre de lanes.

### A.4 La liste fermée des critères (modèle qualité, écrit AVANT tout constat)

SQALE (partie vérifiée : le modèle qualité est défini d'abord ; pas de dette sans violation d'une
exigence ; coût de remédiation = principal, de non-remédiation = intérêt) et ISO 25040 imposent que
critères et seuils précèdent les constats ; sinon un constat est une opinion (Google *standard.md* :
« technical facts and data overrule opinions and personal preference »). ATAM rejette les objectifs non
réfutables : chaque critère se décline en scénarios *stimulus → réponse → mesure* (arc42 §10, types
*usage* et *changement*). **Un constat sans critère de cette liste est rétrogradé en OPTIONNEL.**

| ID | Critère | Source / objectif | Preuve EXIGÉE (sans elle, pas de constat CONFIRMÉ) |
|---|---|---|---|
| **C1** | Exactitude de ce que le client voit (chiffres, textes, langue, version en vigueur) | ISO 25010 *functional correctness* ; contrôles de sortie ; objectif 4 | Parité écran = objet serveur = PDF / page publique sur le MÊME enregistrement (`apps/ventes/tests/test_figures_parite.py`, `frontend/e2e/figures-parite.spec.js` — un des 50 fichiers `frontend/e2e/*.spec.js`) ; recalcul indépendant (`manage.py audit_coherence --json --no-persist`) ; texte PDF extrait (PyMuPDF dans le conteneur) ; capture Playwright. Toujours *correctness*, jamais optionnel. |
| **C2** | Modifiabilité à chaque étape + propagation sans écrasement d'une saisie manuelle | 25010 *modifiability* ; contrôles d'entrée (correction après coup) et de traitement (override préservé, piste old→new) ; objectif 1 | Aller-retour : enregistrer → rouvrir → enregistrer sans toucher ⇒ objet serveur byte-identique (leçon 2) ; table saisie → consommateurs (phase 2) ; test comportemental ou machine à états Hypothesis (`RuleBasedStateMachine`, invariant « un champ manuel garde sa valeur après changement amont ») ; chatter `LeadActivity` old→new. |
| **C3** | Une fonction par geste (aucune implémentation jumelle écran / serveur / PDF / page publique / `apps/web`) | 25010 *modularity*, *reusability* ; contrôle de doublons ; objectif 2 | Inventaire des implémentations avec `file:line` et survivant nommé ; détecteur de duplicata littéral ≥ 6 lignes (règle SIG, à construire) ; alignement mots-clés `solar.js` ↔ `quote_engine/builder.py` ; `scripts/check_calepinage_actions_consommees.py`. |
| **C4** | Code propre : analysabilité, testabilité, zéro code mort, zéro résidu parqué, dépendances saines | 25010 *analysability*, *testability* ; ISO 5055 : CWE-561, CWE-1041, CWE-1047, CWE-1054, CWE-1057 ; objectif 3 | `scripts/check_ecrans_atteignables.py`, `check_services_appeles.py`, `rapport_backend_sombre.py` (preuve grep « zéro appelant ») ; `lint-imports` (`backend/django_core/.importlinter`, 16 contrats) ; `scripts/check_parked_apps.py` ; imports directs inter-apps de `models`/`views` ; signaux sans abonné / sans émetteur (`core/event_coverage.py`, `ALLOWED_UNCONSUMED`). |
| **C5** | Étanchéité multi-société et autorisations | 25010 *integrity*, *confidentiality* ; OWASP ASVS 5.0 8.4.1 (inter-locataires), 8.2.2 (objet, IDOR/BOLA), 8.2.3 (champ, BOPLA) ; cheat-sheet multi-tenant | `backend/django_core/tests/test_tenant_sweep.py` + `testkit/tenant_sweep.py` (« 404 jamais 403 ») ; énumération viewsets / tâches Celery / chemins MinIO / clés de cache / requêtes reporting (`company` FK + `perform_create` forcé) ; rejeu live à DEUX comptes (`seed_demo_company`) en substituant les références de l'autre société (WSTG IDOR) + contrôle positif même société. Cible ASVS L2 ; le caractère « cumulatif » des niveaux n'est pas retenu (non confirmé). |
| **C6** | Contrôles d'entrée : validation, autorisation, anti-doublon, saisie jamais rejetée ni arrondie | GTAG/ISACA entrée ; règles maison (jamais snap, erreur sous le champ, référence unique) | Tests négatifs scriptés (OWASP WSTG *Business Logic* : sauter une étape, éditer l'amont quand l'aval existe, annuler en gardant un crédit) ; `apps/ventes/utils/references.py` (jamais `count()+1`) ; formulaire `noValidate`, `step="any"`. |
| **C7** | Contrôles de traitement : UN calcul, rapprochement inter-modules, piste d'audit, override tracé | GTAG/ISACA traitement ; ISACA tests de contrôles (CAAT) | Lane données en lecture seule (rapprochement facture/BC → devis + client de la même société ; recalcul kWc, économie, HT→TVA→TTC ; doublons ; trous de numérotation ; anomalies) ; `audit_coherence` (22 règles, ventes/crm seulement — à étendre). |
| **C8** | Contrôles de sortie : destinataires autorisés, `prix_achat`/marge jamais côté client, bonne version | GTAG sortie ; règle maison | Oracles 6 et 7 de qa-explorer (`/proposal`, `prix_achat` dans PDF, `/portail/client*`, pages à jeton, JSON servi). |
| **C9** | Données maîtres et paramètres : qui change, journal avant/après, figé vs vivant, une seule lecture par réglage | Indiana SBOA 14.6.5 (maigre), ISACA (avant/après, séparation des tâches), PCAOB AS 2201 B30 | Table réglage/produit/prix → chaque lecteur ; preuve qu'un document envoyé/signé garde sa version figée ; journal old→new sur `Produit`, `CompanyProfile`, rôles. |
| **C10** | Interfaces / coutures : contrat partagé, émetteur ET abonné vivants, tous les appelants, source réelle | Fowler *Consumer-Driven Contracts* + Pact ; Evans *Shared Kernel* ; leçons 3 et 4 | `apps/<x>/contract_samples/*.json` (11 apps) chargés par producteur ET consommateur (`check_api_shapes.py`, `check_api_contract.py`, `check_openapi_shapes.py`) ; `core/event_coverage.py` ; grep de tous les appelants ; interdiction de mocker une source interne (`check_tests_source_regex.py` + revue). |
| **C11** | Règles maison non négociables | `CLAUDE.md` #1-#5 | `scripts/check_stages.py`, `ci_guards.py stage-names`, `/proposal` seul chemin, `--status PAUSED`, Odoo JSON-2. |
| **C12** | Déployabilité (vert en CI ≠ déployable) | ISACA (système entier en staging, interfaces réelles) ; leçon 1 | `frontend/scripts/check_dockerfile_context.mjs` ; `docker compose up -d --build frontend` + `manage.py migrate` réussis AVANT le run live. |
| **C13** | Fiabilité d'exécution | oracles durs qa-explorer 1-4 et 8 | Aucun 5xx, aucun 4xx sur action légitime, aucun `console.error`/`pageerror`, aucun dialogue natif, aucun écran cassé — réseau + console lus avant de quitter chaque page. |
| **C14** | Performance (L3, ou unité X6) | 25010 *performance efficiency* | `assertNumQueries` / N+1 mesuré, export non paginé, boucle O(n²) prouvée. |

Chaque constat porte **exactement un** critère : une cause racine = UN constat avec N emplacements,
jamais N constats (convention maison ; l'« orthogonalité » de SQALE n'a pas été confirmée dans les
sources lues).

---

## §B Déroulé en phases

Les cinq activités d'ISO/IEC 25040 (établir → spécifier → concevoir → exécuter → conclure) deviennent
six phases ; les rondes go-deep s'y logent (R1 = phases 1-2, R2 = phase 4, R3 = phase 5, R4 = phase 6).
Le dossier d'évaluation est committé et poussé sur la branche de claim **à la fin de chaque phase** :
c'est ce qui permet `continue audit` depuis un autre poste.

### Phase 0 — Préconditions (orchestrateur, mécanique)

- `git fetch origin --prune` ; lire `docs/audits/unites.yml` sur `origin/main` ; claim (§D.5).
- `python scripts/check_parked_apps.py` (liste unique : `core/parked.py` `APPS_PARQUEES`, importée,
  jamais recopiée) : les 47 apps parquées sont HORS périmètre, sauf la classe « code MVP qui référence une
  app parquée » (leçon 3 : QJR668 → `cpq`).
- Dédoublonnage contre les tâches ouvertes (`docs/PLAN2.md`, `docs/PLAN.md`, `docs/ERROR_PLAN.md`,
  `docs/plans/*`) et contre `git log` (déjà corrigé sur `main`) ; lecture de `docs/done_task.md` pour les
  groupes antérieurs de l'unité.
- **Pile locale (L2 et L3 seulement ; L1 = détecteurs + lecture + CAAT sans pile)** : `manage.py migrate`
  + `docker compose up -d --build frontend` + `seed_demo` (idempotent, jamais `--force`) +
  `seed_demo_company` (second locataire) + `qa_import_anonymise` si L3. Respecter le verrou mono-écrivain
  du DB de test et le kill switch comme qa-explorer (STEP 0).

### Phase 1 — CHARTE (écrite AVANT tout constat)

Un bloc d'une page, en tête du dossier, montré à Reda si une décision manque :
- **Système et frontière** (SIG : le propriétaire fixe la frontière) : SHA, unité, chemins possédés et
  `perimetre_lu` du registre (= manifeste de couverture initial), coutures lues seulement par
  `selectors.py`/`services.py`/FK chaîne, apps parquées exclues.
- **Objet et parties prenantes** : les 4 objectifs fondateur ; les personas RÉELLES
  (`roles/models.py:1301` `CANONICAL_SYSTEM_ROLES` : aucun rôle « bureau d'études », « magasinier » ni
  « comptable » n'existe — les personas correspondantes jouent en `demo_admin` et l'audit le dit).
- **Niveau** avec sa justification en une ligne ; **jeu de données** (`demo` / `anon`).
- **Modèle qualité** : les critères C1-C14 retenus (jamais tous : une unité sans argent n'a pas C7-argent).
- **Sous-domaine** (Evans / Microsoft : cœur / support / générique) : cœur = devis, tarification,
  dimensionnement, argent, PDF client ⇒ L3 ; support = stock, chantiers, SAV, GED, portail ⇒ L2 ;
  générique = auth, paramètres, notifications ⇒ L1 + piste X1 (sauf texte client ⇒ ≥ L2).
- **Étapes** de l'unité, identifiants stables `P<n>.<m>`, et **non-objectifs**.

### Phase 2 — SPÉCIFICATION des contrôles et seuils

- **Arbre d'utilité (ATAM)** : par critère retenu, des scénarios *stimulus → réponse → mesure*, types
  *usage* (« le client ouvre `/proposal` : chaque chiffre imprimé = chiffre écran ») et *changement*
  (« l'utilisateur modifie kWc / une ligne / la remise à l'étape N et rouvre : la saisie manuelle
  persiste, l'aval se recalcule »). Priorité H/M/L sur **importance × risque perçu**. Les H×H sont
  obligatoirement joués en direct (L2+).
- **Table « chaque saisie → chaque consommateur »** (Lean VSM : le gaspillage est *entre* les étapes) :
  prix, quantité, remise, TVA, nombre de panneaux, adresse, factures… → écran, DB, `/proposal`, page
  publique, facture, chantier, portail, message. Deux recalculs indépendants = constat C3 ; une saisie
  figée sans mention « mis à jour le … » = constat C2.
- **Chaîne documentaire 1:N explicite** (Berti & van der Aalst, approche *object-centric*) : lead 1-N
  devis/révisions ; devis 1-N BC ; BC 1-N factures/échéances ; facture 1-N paiements/avoirs ; devis →
  chantier → mouvements de stock → parc SAV. Tests de couture **par lien** : copié / référencé /
  recalculé quand la source change ; sort des objets aval quand l'amont est édité, révisé (V2), annulé.
- **Seuils de décision** : S1-S2 correctness/spec ⇒ tâche ; S3 ⇒ tâche si effort ≤ M ; S4, style,
  durcissement hypothétique ⇒ liste OPTIONNELLE séparée (Google « Nit: »). Chiffre client / zéro chiffre
  inventé : TOUJOURS correctness.
- **Liste versionnée des détecteurs** (phase 4-a) et des scénarios live (≤ 1 walkthrough par processus +
  étapes négatives à chaque passage de main ; la passe large d'un audit L3 ne devient PAS une suite E2E
  permanente — Fowler *Practical Test Pyramid*).
- **Catalogue d'étapes à identifiants stables** (Microsoft : catalogue numéroté, l'id ne change jamais) :
  `frontend/src/features/crm/relances/parcours_suivi.json` (18 étapes) pour la cadence, et la table des
  unités §D.2 — chaque unité porte ses étapes `P<n>.<m>` dans sa charte. Une étape sans test nommé est
  elle-même un constat C10.

### Phase 3 — PLAN DES LANES

- Lanes = surfaces indépendantes, jamais le nombre d'emphase ; plafond du niveau go-deep (**jamais plus
  de 10-12 lanes par run**) ; flotte en lecture seule = fan-out `Workflow` dans le même répertoire
  (cache par répertoire), jamais de worktree pour lire.
- **Brief standard par lane** (Anthropic multi-agent : objectif, format de sortie, outils, frontières) :
  objectif ; surface (chemins) ; critères ; scénarios H/M/L ; sortie = constat §C.1 ; règle de preuve ;
  hors-périmètre ; `model:` + effort explicites ; le **bloc de grounding verbatim** de `CLAUDE.md`.
- **Qui fait quoi** (routage `CLAUDE.md`, jamais d'héritage du modèle de session) :

| Rôle | Modèle / effort | Travail |
|---|---|---|
| Orchestrateur | modèle de session | charte, spécification, plan, triage (classer → décider, jamais « corrige les N »), **run live** (seul à piloter docker/Playwright : `docs/LANE_BRIEF.md` interdit docker et DB de test aux lanes), rejeu indépendant, routage des tâches, registre, PR |
| Scouts | haiku, low | inventaires (manifeste, appelants, signaux, imports), dédoublonnage, exécution des détecteurs et collage brut |
| Lanes de jugement | **sonnet, medium (défaut)** ; **opus, high** sur moteur de devis (règle #4), argent, auth/multi-société, `core` sous import-linter, flux d'événements inter-apps | lecture complète de la surface + scénarios + constats avec preuve |
| Passes multiples | 2-3 lanes sonnet/opus indépendantes à cadrage différent, union puis réfutation | L3 uniquement (SWR-Bench : peu de recouvrement entre runs du même modèle) |
| Réfuteurs | opus, high, **contexte frais**, jamais l'auteur | phase 5 |
| Fable | **1-3 appels par run au total**, high, chacun avec sa ligne DONE LOG (dans le fichier de plan alimenté) | critique de complétude, adjudication d'une contradiction, revue finale du groupe assemblé |

### Phase 4 — EXÉCUTION

**4-a. Détecteurs mécaniques versionnés** (ISO 5055 : automatisé, objectif, transparent, vérifiable ;
SIG : pourcentage de code en catégorie de risque, pas un tas de violations). Commande, SHA et extrait dans
le dossier ; sortie brute au scratchpad.
- Existants : `python scripts/ci_guards.py stage-names` et `backend-lint-fast` ; `lint-imports` ;
  `scripts/check_ecrans_atteignables.py`, `check_services_appeles.py`, `rapport_backend_sombre.py`,
  `check_calepinage_actions_consommees.py` ; `check_parked_apps.py` ; `check_api_shapes.py`,
  `check_api_contract.py`, `check_openapi_shapes.py`, `check_lead_webhook_parite.py`,
  `check_modes_marche.py` ; `check_tests_source_regex.py`, `check_test_determinism.py`,
  `check_invariants.py` + `docs/invariants.md` ; `check_taches_cablage.py`,
  `check_plan_taches_mixtes.py`, `plan_lanes.py --check` ; `frontend/scripts/check_dockerfile_context.mjs` ;
  `tests/test_tenant_sweep.py` ; `manage.py audit_coherence --json --no-persist` ;
  `manage.py makemigrations --check --dry-run` ; `core/event_coverage.py`.
- **À construire, comme gardes M3 du premier audit qui en a besoin (pas avant)** : détecteur de duplicata
  littéral ≥ 6 lignes modulo espaces (règle SIG) entre `pages/`, `features/`, `apps/web`,
  `quote_engine` ; vérificateur « paramètre ajouté sans appelant qui le transmet » (leçon 4) ; diff
  « assertion affaiblie/supprimée dans un fichier de test » (EvilGenie : la détection d'édition des
  fichiers de test et le juge LLM sont efficaces, les tests cachés n'apportent qu'une amélioration
  minimale — donc pas de corpus caché, mais un diff net-additif obligatoire) ; **écriture de
  `scripts/audit_couplage.py`** (ré-implémentation : les scripts de la lane dépôt du 02/10 vivaient dans
  un scratchpad de session et ne sont pas récupérables ; les chiffres de §D.1 sont donc à reproduire par
  ce script avant réutilisation ; co-changements sur l'HISTORIQUE COMPLET, la fenêtre des 1 500 derniers
  commits n'étant pas représentative) ; extension d'`audit_coherence` à stock / chantiers / sav / ged /
  portail / parametres (aujourd'hui 22 règles ventes/crm ; `docs/claude-memory/qa-coherence-auditor.md` :
  0 bug de faux chiffre sur 30 attrapé par la CI).

**4-b. Lanes de jugement** : lecture complète de la surface (manifeste), scénarios de la phase 2,
constats §C.1. Sur les points chauds (`crm/services.py` 13 547 l. ; `apps/web/src/pages/proposition/
[...token].astro` 11 158 l. ; `installations/services.py` 4 712 l.), une lane dédiée découpée par
sous-flux, jamais par nombre de fichiers (ex. pour `installations/services.py` : achats/réception,
kitting/livraison, réception chantier → parc).

**4-c. Walkthrough d'une transaction réelle** (L2+ ; PCAOB AS 2201 §.37, appliqué par analogie : suivre
UNE transaction de l'origine à l'enregistrement final avec les mêmes documents et le même système que le
personnel) : un enregistrement du premier clic au dernier artefact client (PDF, page publique, facture,
message), en chaîne de personas aux rôles RÉELS (Microsoft : les rôles se passent les résultats, tests
négatifs à chaque passage), avec étapes négatives : éditer l'amont quand l'aval existe, archiver un
produit référencé, changer un paramètre société en cours de flux, revenir d'une étape, en sauter une. Sur
`anon` à L3 (les données réelles ont d'autres motifs que la démo).

**4-d. Run Playwright** (orchestrateur ; bonnes pratiques Playwright vérifiées : comportement visible,
contexte isolé, locators par rôle, assertions web-first, traces conservées, « ne mockez que ce que vous ne
contrôlez pas ») : oracles durs qa-explorer 1-10 (le verdict est porté par l'oracle, pas par le LLM) ;
captures JPEG sous `docs/qa-explorer/captures/<date>/` (aucune en `anon`) ; **rejeu indépendant** de
chaque candidat dans Chrome DevTools MCP ; jamais de mock d'une source interne.

**4-e. Lane données (CAAT) et conformance** : requêtes lecture seule (C7) ; à L3, *conformance checking*
(van der Aalst : journal cas / activité / horodatage, alignement coût-pondéré, fitness = part de traces
conformes) sur `LeadActivity` + historiques de statuts Devis / BC / Facture / Installation contre la
machine d'états légale (STAGES.py pour le funnel ; brouillon → envoyé → accepté / refusé / expiré ; BC ;
Facture ; Installation). Signale : facture sans devis accepté, devis accepté modifié sans trace, états
sautés, horodatages désordonnés. Hypothèse non vérifiée : que l'historique stocké suffit.

### Phase 5 — VÉRIFICATION ADVERSARIALE (R3)

- **Indépendance** : l'agent qui a trouvé ne vérifie jamais ; les réfuteurs sont frais et ne voient que
  le constat, la preuve et les critères (Claude Code *best practices* : le vérificateur frais ne voit que
  le diff et les critères ; « show evidence rather than asserting success » ; Huang et al. : l'auto-
  correction sans retour externe n'améliore pas).
- **Lentilles** (2 à L2 sur les critiques, 2-3 à L3) : *checked-facts* (chiffre recalculé
  indépendamment), *reproduction*, *spec/correctness* (critère violé ou préférence ?),
  *déjà-corrigé-sur-main*, *frères et sœurs* (le même motif ailleurs : « fix the class, not the
  instance »), *cause racine* (la garde manquante, pas « le dev a oublié »).
- **Porte empirique obligatoire** : un constat touchant un chiffre client, une persistance, de l'argent
  ou le multi-société n'est CONFIRMÉ que par une vérification **exécutée** (test rouge, requête, trace
  Playwright, diff de deux calculs). Un consensus de relecteurs n'est jamais une preuve : Refute-or-Promote
  (domaine sécurité ; ~79 % des candidats tués en rétrospectif, 83 % sur un sous-ensemble prospectif de 30)
  rapporte dix relecteurs unanimes sur une vulnérabilité inexistante, tuée par un seul test empirique.
  Les cas limites remontent au fondateur ; l'argument de réfutation est stocké à côté du constat.
- **Calibration du réfuteur** : avant de lui faire confiance, le passer sur un corpus étiqueté — le texte
  des 14 défauts QJR5 + le diff pré/post-correctif de chacun (SHA), pas un dépôt « planté » — et
  rapporter rappel et spécificité (arXiv 2511.21140 ; la taille d'échantillon recommandée n'a pas été
  vérifiée). Un réfuteur qui réfute 1/167 (QJR5, provenance du groupe dans `docs/PLAN2.md`) — ou 0/77 pour QJR2
  selon la recherche du 02/10, non re-vérifié — n'est pas calibré. Biais documentés
  (survey 2411.15594 : position, longueur, concrétude, auto-valorisation) ; la permutation de position
  **nuit** sur données adversariales pour certains modèles (2604.23178) : rubrique + raisonnement
  décomposé par critère, pas de débiaisage mécanique aveugle.
- **Audit de l'audit** (Anthropic *Demystifying evals* : graders par code d'abord, LLM calibrés,
  humains en or ; `pass^k` pour les flux critiques) : les défauts connus du corpus doivent être
  redécouverts ; un run L3 qui en rate un est lui-même un constat sur l'audit.

### Phase 6 — CONCLUSION

Rapport avec **couverture chiffrée** (contrôles spécifiés / exécutés par critère ; fichiers lus / non lus
par lane ; scénarios live joués / prévus ; détecteurs non exécutés et pourquoi), constats vérifiés /
réfutés / renvoyés, **non-risques** consignés avec leurs hypothèses (ATAM : valides tant que l'hypothèse
tient — la mémoire anti-régression), coût. Puis : routage des tâches par propriétaire (§D.3), mise à jour
du registre (§D.5), dossier committé, PR docs-only, fin au merge.

---

## §C Formats

Chaque champ de §C.1 et chaque clause de §C.2 est **présent** : quand il ne s'applique pas, il porte
`n/a` + une raison courte, jamais une omission (la garde `check_taches_cablage.py` devient un simple
test de présence).

### C.1 Le CONSTAT (ouvreur / fermeur, façon ODC)

IBM ODC v5.2 sépare les attributs d'ouverture (*Activity*, *Trigger*, *Impact*) et de fermeture
(*Target*, *Defect Type*, *Qualifier*, *Age*, *Source*) ; la liste des *triggers* est fermée ; leur
distribution dit quelle activité de vérification a échoué. Mozilla Bugzilla sépare gravité (S1-S4) et
priorité. Google SRE : priorité = risque de récurrence ; suivre l'âge des P0/P1.

```
## C-<GROUPE>-<NNN>   (ex. C-AFAC-007 — préfixe « C- » : jamais confondu avec un ID de tâche)
OUVREUR (lane d'audit)
  unité          : J5 facturation            critère : C7
  étape          : P1.9 « générer-facture depuis devis »  (id stable de la charte)
  activité       : lecture statique | détecteur <nom+version> | walkthrough | Playwright | CAAT anon
  déclencheur    : (liste FERMÉE, ne jamais en inventer)
                   réouverture-après-enregistrement | édition-puis-recalcul | source-absente-ou-parquée |
                   mock-vs-réel | chemin-double-jumeau | paramètre-non-transmis | déploiement |
                   chiffre-client | multi-société | événement-sans-abonné-ou-émetteur | règle-maison |
                   état-sauté-ou-contourné | données-maîtres-non-propagées
  observé        : …            attendu : …   (scénario stimulus→réponse→mesure cité)
  reproduction   : étapes numérotées depuis /login, ou la commande exacte
  preuve         : file:line ; sortie de commande ; chemin trace/capture ; requête + résultat
  gravité        : S1 chiffre client faux / perte / fuite locataire — S2 saisie manuelle effacée,
                   geste cassé sans contournement — S3 contournement existe — S4 cosmétique
  confiance      : CONFIRMÉ (vérification exécutée) | PLAUSIBLE (jamais promu en tâche sans oracle)
  frères/sœurs   : même motif ailleurs (grep) → UN constat, N emplacements
  cause racine   : 1-2 « pourquoi » ; la garde système manquante (jamais « humain »)
  correction     : locale (cette instance)   action corrective : la classe (ISO 9001 10.2, source
                   secondaire : corriger ≠ supprimer la cause ; chercher les non-conformités similaires)
  effort         : S/M/L            intérêt : ce qui casse / qui le voit si on laisse (SQALE)
ORCHESTRATEUR
  priorité       : P0-P3 (jamais fixée par la lane)    tâche(s) : <ID> → <fichier de plan>
FERMEUR (vérificateur à la clôture, jamais le constructeur)
  type de défaut : assignation | contrôle | algorithme | fonction/classe | synchronisation | interface | relation
  qualificatif   : manquant | incorrect | superflu      âge : base | nouveau | réécrit | re-corrigé
  activité d'échappement : quelle porte aurait dû l'attraper (test unitaire | CI | Playwright | déploiement)
  preuve de clôture : SHA rouge + sortie ; SHA vert + sortie ; mutation/réversion ; live ; frères balayés
  garde permanente : script/test/contrat ajouté (ou « aucune » avec justification)
```

La liste des déclencheurs est une conception maison (non sourcée). Après chaque `vérifie <GROUPE>`, la
distribution déclencheur × activité d'échappement dit quelle porte renforcer (Chillarege).

### C.2 La TÂCHE de plan

Google SRE (Lunney) : **actionnable** (verbe + résultat), **spécifique**, **bornée** (dit quand c'est
fini), un seul propriétaire, suivie. INVEST (Wake) : testable. Given-When-Then (Fowler ; Cucumber :
déclaratif, le comportement pas l'implémentation).

**Forme physique.** Dans le fichier de plan, une tâche tient sur **UNE ligne** (forme réelle des tâches
QJR600-601 de `docs/PLAN2.md`) : `scripts/plan_lanes.py` lit la première ligne seulement, prend les
chemins après le DERNIER `Files:` et lit `@after` / `@lane` / `@model` en fin de ligne. Les clauses
ci-dessous s'enchaînent donc en ligne, chacune ouverte par son libellé en gras.

```
- [ ] <ID> — **<Verbe + objet + condition de fin bornée>** :
  Constat : C-<GROUPE>-<NNN> (critère Cn, gravité Sn) ; Priorité : Pn.
  Given <état d'entrée : enregistrement, rôle, données> When <geste unique>
  Then <résultat observable> + CLAUSE PERSISTANCE (« rouvrir → identique ») + CLAUSE CLIENT si sortie
    client (« /proposal / page publique = écran »).
  Test rouge d'abord : <chemin::test> — comportemental (jamais espion, jamais regex sur le source —
    check_tests_source_regex) ; il DOIT échouer sur le commit pré-correctif.
  Test-du-test : mutation sur les LIGNES CHANGÉES (au plus un mutant par ligne, en revue — Google) OU
    réversion explicite (« retirer <X> ⇒ le test échoue ») ; obligatoire P0/P1. Jamais un % de couverture.
  Source réelle : <app/fonction> existe et n'est PAS parquée ; aucun mock d'une source interne.
  Appelants : <liste grep complète file:line> — CHACUN transmet le nouveau paramètre.
  Jumeaux : <autres implémentations du geste : page publique, PDF, apps/web> — supprimés dans le même
    commit, survivant nommé.
  Listes figées : toute liste d'exceptions par numéro de ligne (scripts/check_naive_datetime.py) et tout
    tuple positionnel (apps/ventes/domain/entrees.py EntreesMoteur) touchés par l'insertion d'un champ
    sont mis à jour dans le même commit (grep préalable listé).
  Contrat partagé : apps/<x>/contract_samples/<f>.json — M0 seul sur main d'abord (PACT10) ; la moitié
    front porte @after sur la moitié BACK qui produit ses données (PACT11).
  Déployable : check_dockerfile_context.mjs vert si le front est touché ; migration revertable.
  Preuve en direct : étape P<n>.<m> rejouée. La tâche d'acceptation live est exécutée par
    l'ORCHESTRATEUR du plan-run (il possède la pile et le DB mono-écrivain, CLAUDE.md étape 3) AVANT le
    merge unique, sur la branche d'intégration ; `vérifie <GROUPE>` reste la contre-visite post-merge sur
    origin/main. Un merge sans trace Playwright de cette tâche = groupe non livré.
  Hors périmètre : …
  Files: `a`, `b` (ROUTINE|SCHEMA|…) (@after: <IDs>) (@lane: <clé>) (@model: sonnet|opus)
```

`@model: opus` pour règle #4, argent, auth, `core`. Chaque groupe se termine par UNE tâche d'acceptation
live rejouant le parcours entier.

**Garde d'application.** `check_taches_cablage.py` / `plan_lanes.py` doivent REFUSER une tâche sans ces
clauses. Elle est la **PREMIÈRE tâche M3 du premier groupe d'audit v2** (ID réservé, `@model:sonnet`,
`Files: scripts/check_taches_cablage.py` + son test ; propriétaire `scripts/**` = X5, donc routée dans
`PLAN_AUDIT_DEPLOY.md`, §D.3) ; tant qu'elle n'est pas sur `main`, l'orchestrateur applique les clauses
à la relecture de chaque tâche exportée (relecture bloquante, pas optionnelle). Vérifié le 02/10 :
`check_taches_cablage.py` et `check_plan_taches_mixtes.py` scannent déjà `docs/plans/PLAN_*.md`, donc
les fichiers `PLAN_AUDIT_*` sont couverts dès leur création. Rappel prouvé : QJR570 avait un texte
parfait et a quand même livré des lignes dupliquées ⇒ le texte ne remplace jamais l'oracle côté build ;
c'est la clause « Preuve en direct » qui compte.

### C.3 Definition of Done (checklist par tâche, `passes=false` jusqu'au vérificateur)

Scrum Guide : ce qui ne satisfait pas la DoD ne se livre pas. Anthropic *harness* : liste avec
`passes=false`, « inacceptable de retirer ou éditer des tests », complétion prématurée corrigée seulement
par vérification bout-en-bout.

`[ ] rouge sur pré-correctif (SHA, sortie) · [ ] vert sur correctif (SHA, sortie) · [ ] diff des fichiers
de test net-additif en assertions · [ ] aucun mock de source interne · [ ] tous les appelants transmettent
· [ ] jumeaux supprimés · [ ] listes figées mises à jour · [ ] frères balayés · [ ] mutation/réversion
(P0/P1) · [ ] docker build + migrate OK · [ ] live rejoué (trace) · [ ] CI verte (nécessaire, jamais
suffisante)`

### C.4 Protocole de clôture

1. **Une tâche n'est fermée que par un vérificateur frais** (pas le constructeur) qui rejoue la
   reproduction d'origine ; si elle ne peut pas être rejouée, la tâche reste ouverte. Le constructeur dit
   « fait » avec SHA + commande + sortie ; le vérificateur spot-checke l'état git.
2. **Preuve que la cause a disparu, pas seulement le symptôme** (CMMI CAR SG2 et ISO 9001 10.2 — sources
   secondaires, retenues pour l'intention) : test rouge-d'abord vert, mutation/réversion qui le rend
   rouge, frères fermés sous la même cause, garde de classe présente.
3. **`vérifie <GROUPE>` est OBLIGATOIRE après chaque build d'un groupe d'audit** (Microsoft : un seul
   cycle de test à la fin est risqué) : sur `origin/main`, lister les tâches du groupe cochées (dans
   TOUS les fichiers de plan où le registre dit qu'elles sont allées) et leurs PR, la CI, l'état serveur
   en lecture seule (`docs/claude-memory/prod-read-access.md`) ; une lane par surface (≤ 10, `model:` +
   effort explicites, grounding) compare TEXTE de tâche ↔ commit(s) ↔ test rouge nommé (verdict
   ok / partiel / non-fait / faux / régression avec preuve) sous les 7 critères de
   `lecons-construction-qjr5.md` ; run live du parcours (migrate + rebuild du front d'abord) ; **UNE
   critique Fable sur l'ensemble des écarts bloquants du `vérifie`** (compte dans le plafond 1-3 appels
   par run, ligne DONE LOG) ; écarts confirmés déposés en `ERR-<GROUPE>-*` dans `docs/ERROR_PLAN.md`
   (titre, file:line, correctif, test rouge, `Files:`) **(docs/ERROR_PLAN.md est dans la surface
   plan-fingerprint : rafraîchir CODEMAP §10 + `codemap_fingerprint.py --write` dans le même commit)**,
   après `git fetch origin` (#767 et #768 ont construit deux fois les mêmes 14 items en parallèle). Le
   registre passe à `vérifié` quand le `vérifie` ne laisse aucun écart S1-S2, sinon reste `construit`.
4. **Ré-audit par différence** (`audit <mot> contre-visite` ; benchmarking AS 2201 B28-B29 avec sa
   précondition) : un contrôle automatisé vérifié devient un test de régression nommé ; on ne relit que ce
   que `git diff` a touché depuis le dernier audit, **à condition que les contrôles généraux (CI, revue,
   accès) soient restés effectifs** ; tout changement de `parametres` ou du catalogue `Produit` invalide le
   benchmark de chaque calcul qui le lit (B30). Une sélection centrée sur le changement ne prouve pas
   l'absence de régression ailleurs (Microsoft) : le rapport le dit.
5. **Métriques rapportées, jamais ciblées** (DORA : *change failure rate*, *rework rate* ; Goodhart) :
   défauts trouvés par `vérifie` ÷ tâches livrées ; commits de reprise après merge ; âge des P0/P1
   ouverts.
6. **Critère de sortie** : une surface ré-auditée 5 fois en 32 jours (QJR → QJR5) n'avait pas de critère
   de sortie. Désormais une unité sort du cycle quand `vérifie` + run live + CAAT sont à zéro écart S1-S2
   **deux fois de suite** — le second passage étant une **contre-visite par différence** (point 4), pas
   un `vérifie` complet.

---

## §D Découpage de l'ERP en unités d'audit

### D.1 Pourquoi ce découpage

- **Principe** : découper par capacité métier et vocabulaire stable (Fowler *Bounded Context* ;
  Microsoft : capacités, pas couches ; Ozkan et al. : la frontière est la partie dure), jamais par app
  Django ni par écran ; ajouter des **pistes transverses** pour ce qu'aucune unité verticale ne voit (SIG :
  l'enchevêtrement n'est visible qu'entre composants ; ISO 5055 : CWE-1047, CWE-1054, CWE-1057). *Partiel* :
  aucune source ne dicte « découper l'audit par surfaces indépendantes » — c'est une inférence étayée par
  ces ingrédients et par la mesure ci-dessous.
- **Mesure** (lane dépôt, lecture seule, `6742fc3a1` ; scripts non conservés, à reproduire par
  `scripts/audit_couplage.py`) : poids de couture entre deux apps métier = imports de production + FK
  chaîne + 5 par arête d'événement vive ; total 1 160, 55 arêtes d'événements vives ; 748 549 lignes
  (backend prod + pages/features front + pages client `apps/web`).

| Critère | A : une unité par app | B : 9 parcours + 5 pistes | **C : hybride (retenu)** |
|---|---|---|---|
| Poids de couture interne à une unité | 0 % | 80 % | **96 %** |
| Arêtes d'événements internes | 0/55 | 24/55 | **46/55** (les 9 autres = événements plateforme, pistes X3/X7) |
| Apps possédées | 40/40 | 23/40 | **40/40** |
| Taille par unité | 64 → 149 877 lignes | 220k-344k par parcours | **≈10k → ≈90k, médiane ≈35k** |
| Code relu par plusieurs unités | 1,00× | 3,83× | **≈1,03×** |

- **19 unités, jamais plus de 10-12 lanes par run d'audit** : un run audite UNE unité (ses lanes sont ses
  surfaces internes), et la file des 19 se draine unité par unité (§0, `loop audit`).
- **Points chauds et co-changements** (historique complet, 12 289 commits ; Tornhill ; Nagappan & Ball :
  dépendances + churn prédisent les défauts) : crm/ventes et stock/installations ne se séparent pas en
  parcours disjoints ; ils se séparent par **sous-flux** avec la couture possédée par une seule unité.
- **Réserve** : comptes par regex (imports absolus `apps.*`, FK littérales, `.send/.connect/@receiver`) ;
  le canal `post_save` parallèle (`publicapi/signals.py`, `adsengine/capi_crm.py`) n'est pas pondéré ;
  graphe d'imports front non calculé ; tailles X3-X7 estimées.

### D.2 Classement des unités (ordre de passage)

**Règle.** Risque = **probabilité** (churn mesuré, défauts QAH/ERR récents, signaux morts, canal parallèle,
absence d'audit antérieur, ratio test/prod) × **impact** (argent, sortie client, fuite locataire, perte de
données ⇒ 5) — ISTQB CTFL §5.2 (niveau = probabilité × impact, matrice qualitative ; « calculs
incorrects » cité comme risque produit). Le **rang** suit le score P×I décroissant ; **à égalité, l'argent
puis la sortie client passent d'abord** ; une unité **couverte par l'audit QJR5 (J1b, D4) attend un cycle
de build** et se range après le dernier groupe de score ≥ 12, quel que soit son score. (FMEA S×O×D : non
vérifié, non retenu.)

| Rang | Id | Mot (`audit <mot>`) | Titre | P×I | Niveau défaut | Fichier de plan du propriétaire |
|---|---|---|---|---|---|---|
| 1 | X2 | `totaux` | Invariants de la chaîne argent (piste) | 4×5 | L3 | — (tâches routées) |
| 2 | J5 | `facturation` | BC → facture → paiement → avoir → relances | 4×5 | L3 | `PLAN_AUDIT_FACTURATION.md` |
| 3 | D3 | `calepinage` | Studio toiture, simulation, publication, livrables | 5×4 | L3 | `PLAN_AUDIT_CALEPINAGE.md` |
| 4 | J0 | `acquisition` | Site, Meta Lead Ads, webhooks, RDV | 4×4 | L2 | `PLAN_AUDIT_ACQUISITION.md` |
| 5 | J1a | `lead` | Lead → fiche → cadence → visite | 4×4 | L2 | `PLAN_AUDIT_LEAD.md` |
| 6 | D1 | `crm` | Plongée : les 3 fichiers chauds du CRM | 4×4 | L2 | `PLAN_AUDIT_CRM.md` |
| 7 | X1 | `sécurité` | Multi-société, auth, rôles | 3×5 | L3 | `PLAN_AUDIT_SECURITE.md` |
| 8 | X4 | `pdf` | Documents imprimés (piste) | 3×5 | L2 | — (tâches routées) |
| 9 | D2 | `moteur` | Moteur de devis (règle #4) + calculateurs | 3×5 | L3 | `PLAN_AUDIT_MOTEUR.md` |
| 10 | J2 | `chantiers` | Signature → chantier → réception | 3×4 | L2 | `PLAN_AUDIT_CHANTIERS.md` |
| 11 | J3 | `stock` | Catalogue, prix, stock, achats | 3×4 | L2 | `PLAN_AUDIT_STOCK.md` |
| 12 | J6 | `documents` | GED, portail, suivi public | 3×4 | L2 | `PLAN_AUDIT_DOCUMENTS.md` |
| 13 | X3 | `parametres` | Paramètres, notifications, bus d'événements | 3×4 | L2 | `PLAN_AUDIT_PARAMETRES.md` |
| 14 | D4 | `générateur` | Écran générateur + `solar.js` (contre-visite QJR5) | 4×5 | L2 | `PLAN_AUDIT_GENERATEUR.md` |
| 15 | J1b | `devis` | Étude → devis → signature (contre-visite QJR5) | 2×5 | L3 | `PLAN_AUDIT_DEVIS.md` |
| 16 | X5 | `deploy` | Déployabilité, CI, outillage, socle front | 2×5 | L1 | `PLAN_AUDIT_DEPLOY.md` |
| 17 | J4 | `sav` | Parc, tickets, SLA, garanties, monitoring | 3×3 | L2 | `PLAN_AUDIT_SAV.md` |
| 18 | X7 | `analyse` | Pilotage, API publique, imports, hors-ligne, IA | 3×3 | L1 | `PLAN_AUDIT_ANALYSE.md` |
| 19 | X6 | `performance` | Performance des points chauds (piste) | 2×3 | L2 | — (tâches routées) |

Le registre `docs/audits/unites.yml` porte les mêmes valeurs plus les chemins, coutures, préfixes de
groupe et statuts : **c'est lui la source de vérité** ; ce tableau en est la lecture. Re-scorer à chaque
lot fusionné ; si deux unités produisent beaucoup de constats qui se référencent, les fusionner ; si une
unité mélange deux vocabulaires, la couper (Microsoft : commencer gros, couper est plus facile que
fusionner).

### D.3 Propriété et routage des tâches (un fichier de plan par propriétaire)

**Découvrir par unité, écrire chez le propriétaire.** L'audit d'une unité lit ses chemins et ses coutures
(`perimetre_lu`), mais chaque tâche qu'il produit est **routée vers le fichier de plan du propriétaire des
fichiers qu'elle édite** :

1. **Table de propriété** : si `docs/ownership.yml` existe (session de propriété séparée), **elle
   prime** ; sinon le champ `possede` de `docs/audits/unites.yml`. Le chemin le plus spécifique gagne
   (fichier > dossier > glob résiduel : `crm/services.py` → D1 bien que `apps/crm/**` soit à J1a).
2. **Un seul propriétaire** pour tous les `Files:` de la tâche → `docs/plans/PLAN_AUDIT_<UNITE>.md`
   (UNITE = mot du déclencheur en majuscules sans accent : `FACTURATION`, `SECURITE`, `GENERATEUR`…).
3. **Plusieurs propriétaires** → `docs/plans/PLAN_AUDIT_TRANSVERSE.md`. Ce fichier ne tourne **jamais en
   même temps** qu'un plan qui possède l'un de ses fichiers.
4. **Chemin sans propriétaire** → corriger le registre dans la même PR (ajout à l'unité naturelle,
   signalé dans le rapport) ; **chemin d'une app parquée** → pas de tâche (hors périmètre, sauf la classe
   « code MVP qui référence une parquée », dont la tâche porte sur le code MVP).
5. Les pistes X2, X4, X6 ne possèdent aucun fichier : leurs tâches vont toujours chez les propriétaires.
6. Les tâches d'un groupe gardent le **préfixe de l'unité auditée** (registre, champ `groupe`), quel que
   soit le fichier où elles atterrissent ; le registre liste les fichiers alimentés (`plans_alimentes`).
7. **Append-only** : plusieurs audits ajoutent au même fichier de propriétaire, chacun sous son propre
   en-tête de groupe ; on ne réécrit, ne réordonne ni ne recoche jamais les tâches d'un autre groupe.

**Gabarit d'un fichier `PLAN_AUDIT_<UNITE>.md`** (créé par le premier audit qui y route une tâche ;
contrat dans le style de `docs/plans/PLAN_CRM_VENTES.md`) :

```
# PLAN_AUDIT_<UNITE> — tâches d'audit dont <Id> est propriétaire des fichiers

> **CONTRAT DE PROPRIÉTÉ (non négociable — c'est lui qui garantit zéro conflit).**
> Une session `work on the plan audit_<unite>` n'écrit QUE dans les chemins `possede` de l'unité <Id>
> (docs/audits/unites.yml, ou docs/ownership.yml s'il existe — il prime). Tout le reste est INTERDIT en
> écriture ; lire une app étrangère = via son `selectors.py`/`services.py`/string-FK uniquement. Une
> tâche qui EXIGE d'écrire hors périmètre → `[BLOCKED: hors périmètre AUDIT_<UNITE>]` + continuer.
> Fichiers frontend PARTAGÉS (router/nav/api/ui) : ajouts APPEND-ONLY minimaux ; conflit à
> l'update-branch = garder les DEUX ajouts. Base de test locale : `DB_NAME=erp_audit_<unite>` (jamais la
> DB partagée). La session merge sa propre branche `dev-audit_<unite>` vers main (update-branch → CI →
> auto-merge) ; conflit sur `docs/CODEMAP.md` (fingerprint structure) = prendre l'arbre mergé et relancer
> `python scripts/codemap_fingerprint.py --write`. Ce fichier n'est PAS dans la surface du
> plan-fingerprint : tick + DONE LOG ici, jamais CODEMAP §10. Les 7 leçons de
> docs/claude-memory/lecons-construction-qjr5.md sont des critères d'acceptation de chaque tâche, et la
> tâche d'acceptation live de chaque groupe est jouée par l'orchestrateur AVANT le merge.
> Ne pas lancer en même temps que : <plans concurrents, ex. PLAN_CRM_VENTES.md, PLAN_AUDIT_TRANSVERSE.md>.

## Groupe <PREFIXE> — audit <mot> du <AAAA-MM-JJ> (dossier docs/audits/<AAAA-MM-JJ>-<mot>.md)
**Provenance.** … **Décisions gravées.** … **Séquencement.** … **NE PAS FAIRE.** … **Non couvert.** …
### <PREFIXE> — M0 contrats (seuls sur main d'abord)
### <PREFIXE> — M1 bloquant-fondateur
### <PREFIXE> — M2
### <PREFIXE> — M3 nettoyage et gardes
### <PREFIXE> — GATED (ne PAS auto-construire)

## DONE LOG
```

Les en-têtes de jalon sont de niveau `###` et le GATED s'écrit `### <PREFIXE> — GATED` : c'est la forme
que `plan_lanes.py` (`_NON_QUEUE_SECTION`) reconnaît comme hors file ; un `####` ne serait pas reconnu.
Un nouveau groupe s'insère juste avant `## DONE LOG` ; les lignes de DONE LOG s'ajoutent à la fin.

**Construire.** `work on the plan audit_<unite>` = « How a plan run works » de `CLAUDE.md` restreint au
fichier `docs/plans/PLAN_AUDIT_<UNITE>.md` et au contrat ci-dessus (même modèle que les sessions de
domaine `docs/plans/PLAN_*`). `work on the plan audit_transverse` tourne seul vis-à-vis des propriétaires
de ses fichiers. `docs/BUILD_ORDER.yml` ne gêne pas : l'inventaire de `scripts/plan_progress.py` ne lit
que `PLAN.md`, `PLAN2.md`, `new_tasks_plan.md`, `FRONTEND_GAP_PLAN.md` (vérifié le 02/10), donc les
préfixes des `docs/plans/PLAN_AUDIT_*` ne sont ni gatés ni signalés orphelins.

**Chevauchement honnête avec l'existant.** À ce jour, `docs/plans/` ne contient que `PLAN_CRM_VENTES.md`
(vérifié le 02/10). Son contrat possède `apps/crm`, `apps/ventes` (hors `quote_engine`), `apps/marketing`
et les écrans crm/ventes/marketing : il recouvre `PLAN_AUDIT_{LEAD,CRM,DEVIS,FACTURATION,GENERATEUR,MOTEUR}`
— et aussi `PLAN_AUDIT_ACQUISITION` (`crm/webhooks.py`, `crm/odoo_sync.py`) et `PLAN_AUDIT_CALEPINAGE`
(écrans toiture de `pages/ventes`, `ventes/domain/geometrie.py`). **Ces plans ne tournent jamais en même
temps que `PLAN_CRM_VENTES.md`** tant que la session de propriété n'a pas réconcilié les deux tables.

### D.4 Résolution des mots

Mots v2 : la colonne « Mot » de §D.2 (accents facultatifs : `securite` = `sécurité`, `generateur` =
`générateur`). Mots v1 (`audits-modules.md`) :

| Mot v1 | Résolution |
|---|---|
| `leads` | `audit acquisition` (site, Meta, webhooks) par défaut ; `audit lead leads` si la précision porte sur dédoublonnage, attribution, score |
| `fiche`, `cadence`, `clients` | `audit lead <mot>` (+ D1 pour `crm/services.py`) |
| `visites` | `audit lead visites` |
| `calepinage`, `devis`, `facturation`, `stock`, `chantiers`, `sav`, `parametres` | unité de même nom |
| `ged`, `portail` | `audit documents <mot>` |

Nouveaux en v2 : acquisition (Publicité est MVP et n'avait ni déclencheur ni mission QA), sécurité,
totaux, crm (plongée), moteur, générateur, pdf, deploy, performance, analyse. Les 10 clés de
`docs/qa-explorer.config.yml` restent des missions d'exploration nocturne, pas des unités d'audit.

### D.5 Registre partagé, claim et progression

**Le registre** `docs/audits/unites.yml` est versionné : tout poste le lit sur `origin/main`. Statuts :
`à auditer` → `en cours` → `audité` (PR docs de l'audit fusionnée) → `construit` (tâches du groupe
cochées et mergées) → `vérifié` (`vérifie` sans écart S1-S2).

**Claim (verrou entre postes).**
1. `git fetch origin --prune`, puis `git ls-remote --heads origin 'audit-*'`.
2. Une unité est **réclamée** si la branche `origin/audit-<id>` existe ET que sa pointe n'est pas un
   ancêtre de `origin/main` (`git merge-base --is-ancestor origin/audit-<id> origin/main` échoue).
3. Pour réclamer : depuis `origin/main`, créer une branche locale `audit-<id>` portant **un commit vide**
   (`git commit --allow-empty -m "audit(<id>): claim"`), puis `git push origin HEAD:refs/heads/audit-<id>`.
   Le commit vide est nécessaire : une branche qui pointerait sur un commit de `main` serait lue comme déjà
   fusionnée. Si le push est refusé (branche créée entre-temps ailleurs) : l'unité est prise, passer à la
   suivante.
4. Tout le travail de l'audit (dossier poussé à chaque fin de phase, plans, registre) est committé sur
   cette branche ; la PR docs part de `audit-<id>` ; elle passe le registre à `audité` + groupe + plans
   alimentés + PR + date.
5. Merge en merge commit avec suppression de la branche (`gh pr merge --auto --merge --delete-branch`) :
   la suppression libère le claim. Une branche oubliée mais fusionnée (pointe ancêtre de main) ne
   bloque rien.
6. `en cours` est lu sur les branches vivantes ; il n'est écrit dans le registre que si un audit livre
   volontairement un dossier partiel. `audit status` signale un claim **périmé** (dernier commit de la
   branche > 48 h) ; seul `continue audit` reprend un claim existant.

**Sélection.** `audit next` : plus petit rang au statut `à auditer` et non réclamé. `continue audit` :
claim vivant de plus petit rang (dossier partiel lu sur la branche, reprise à la première phase non
close) ; aucun → `audit next`. `loop audit` : `/loop` sans intervalle (auto-rythmé), une unité par
itération : audit next → PR auto-merge → attente du merge (`scripts/watch-ci.ps1`) → registre à jour sur
main → itération suivante ; arrêt quand aucune unité `à auditer` non réclamée ne reste, ou sur demande de
Reda. En loop, une décision fondateur non tranchée devient une tâche M1 « bloquant-fondateur » et
l'audit continue.

### D.6 Fiches d'unités (coutures et pièges vérifiés)

Les chemins possédés complets sont dans le registre ; ici, ce qu'il faut savoir avant de charter.

- **X2 totaux** — aucune propriété ; invariants Sous-total HT → Remise → Total HT → TVA → TTC identiques
  sur devis, BC, facture, avoir, PDF, page publique, portail ; numérotation (`references.py`) ;
  `prix_achat` jamais client ; relations métamorphiques maison (modifier puis annuler ⇒ totaux
  byte-identiques ; quantité ×2 ⇒ ligne ×2 ; remise avant TVA = remise sur TTC/1,2 ; réordonner ne change
  rien ; rouvrir reproduit l'écran — conception maison, non sourcée). Oracles existants :
  `test_proprietes_devis.py`, `test_proprietes_tarifs.py`, `test_solar_differential*.py`,
  `test_figures_parite.py`, `solar.properties.test.mjs`, `frontend/e2e/figures-parite.spec.js`,
  `audit_coherence` sur `anon`. Produit les oracles que J5, J1b et J3 réutilisent.
- **J5 facturation** — `facturation.totaux → ventes.selectors` = exception import-linter explicite ;
  **deux chemins de création de facture** (`devis/generer-facture` échéancier et
  `bon_commande/creer-facture`), chaîne de totaux commune non vérifiée ; signaux argent émis sans abonné
  (`paiement_rejete`, `facture_annulee`, `paiement_enregistre`, `avoir_cree`, `avoir_annule` ;
  `facture_paid` autorisé par `ALLOWED_UNCONSUMED`) ; `effet_rejete` abonné sans émetteur. Contrat :
  chaque montant suit UNE chaîne, facture corrigée par avoir jamais en place, totaux au centime. PDF
  facture = legacy, séparé de la règle #4.
- **D3 calepinage** — tout endroit qui dessine ou stocke un toit : `apps/calepinage`,
  `features/calepinage`, `pages/ventes/{ToitureDesign,RoofViewer,Conception3DPage}.jsx`,
  `apps/web/src/scripts/roof-tool*.ts`, `ventes/domain/geometrie.py` (possédés) ; crm
  `roof_outline/roof_point/traceToit` et `ventes/domain/resynchronisation.py` (lus). 48 fichiers dans
  `calepinage/contract_samples/` ; 6 items `ERR-QAH-CALEPINAGE-*` dans `docs/ERROR_PLAN.md`. Livrables PDF d'étude hors règle #4.
- **J0 acquisition** — `meta_lead_captured`, `appointment_effectue` crm → adsengine ; `lead_erased`
  abonné adsengine sans émetteur ; canal `post_save` parallèle `adsengine/capi_crm.py` ;
  `check_lead_webhook_parite.py` ; liaison KV Cloudflare `LEADS_DLQ` (QJR663, `apps/web` — no-op tant que
  l'espace KV n'est pas créé par le fondateur ; aucun équivalent backend). Contrat : ce que le client a
  saisi est corrigeable sans réécrasement par une nouvelle soumission ; une seule normalisation
  téléphone / ville / factures. Règles #1 (Odoo JSON-2) et #3 (`--status PAUSED`).
- **J1a lead** — `visite_planifiee/terminee/validee` visites → crm ; `crm/urls.py:32` importe
  `apps.visites.views` (violation de doctrine) ; `deal_commission_due` (`crm/receivers.py:156`) et
  `salle_vente_signal_interet` (`crm/services.py:286`) sans abonné ; crm abonné à `ao_depose`/`ao_gagne`
  d'une app parquée ; deux tables de home mobile divergentes (`authentication/selectors.py` ↔
  `features/offlinesync/mobile/mobileHome.js` : « Commercial terrain » présent côté serveur, absent
  de `mobileHome.js`). Contrats : `apps/crm/contract_samples/` (dont `controle_suivi.json`),
  `parcours_suivi.json` (18 étapes). Contrat : chaque champ modifiable et tracé au chatter, autosave sans
  perte, correction propagée à devis / visite / calepinage.
- **D1 crm** — `crm/services.py` (13 547 l.), `selectors.py` (5 889), `views.py` (5 817) ;
  `resolve_client_for_lead` (jamais de doublon) ; `crm/selectors.py:364,421` importent
  `ventes.models.Facture`. Une lane partagée par les précisions v1 pour éviter le triple rapport.
- **X1 sécurité** — **roles** (`CANONICAL_SYSTEM_ROLES`, `roles/models.py:1301`) ; **authentication**
  (`permissions.py` : `IsAdminRole`, `IsResponsableOrAdmin`) ; core (hors `events.py` /
  `event_coverage.py`), identity, accessreview, audit, records, trash, customfields, entites, tiers,
  adminops ; checklist ASVS 8.4.1 / 8.2.2 / 8.2.3 + cheat-sheet multi-tenant ; modélisation des menaces
  par décomposition (OWASP *Threat Modeling Process* : DFD, points d'entrée, actifs, frontières de
  confiance) ; comptes démo sur prod (`docs/claude-memory/demo-accounts-prod-incident.md`). `audit`
  porte l'abonné de `devis_expired` (événement J1b, abonnés audit + notifications).
- **X4 pdf** — `/proposal` (règle #4), PDF facture legacy, PDF d'étude calepinage,
  `ventes/utils/pdf.py`, textes CGV de `parametres` : même texte / CGV PDF = page publique = portail,
  extraction PyMuPDF, `prix_achat` jamais.
- **D2 moteur** (opus) — `apps/ventes/quote_engine/` (`builder.py` 4 470 l., `generate_devis_premium.py`
  4 833 l., `pricing.py`, `bareme.py`, `figures.py`, `montants.py`, sous-dossiers
  `residential/industriel/commercial/agricole`), les calculateurs de tête d'app
  `apps/ventes/{solar_design,etude_horaire,dimensionnement,offres_tailles,economie}.py`,
  `apps/ventes/domain/dimensionnement_devis.py`, et `apps/ventes/coherence/` (22 règles). Modes
  Résidentiel / Industriel / Agricole ; pompage (jamais onduleur ni batterie ; m³/jour seulement pompe à
  courbe ; jamais de produit sans prix) ; pages 3 / 4 / 1 (`test_quote_engine.py`) ; mots-clés alignés avec
  `solar.js`. La lane QJR79 (« surfaces jamais auditées ») a trouvé de nombreux constats dans des
  fichiers que les lanes antérieures n'avaient pas lus (149 selon la recherche du 02/10, non re-vérifié)
  ⇒ manifeste de couverture obligatoire.
- **J2 chantiers** — `devis_accepted` → `installations/receivers.py:30` ; `bon_commande_cree` →
  installations + notifications ; `chantier_annule` → ventes ; `document_statut_change` sans abonné ;
  bascule nomenclature → parc SAV : `sweep_bom_to_parc` est défini dans `apps/sav/services.py:127` et
  appelé depuis `installations/services.py:3203-3211` ; `chantier_receptionne.send` à
  `installations/services.py:3335`. Contrat : une V2 de devis met à jour le chantier comme décidé ; une
  intervention se corrige après coup ; une seule nomenclature.
- **J3 stock** — couture installations ↔ stock lourde (mesure §D.1, à reproduire) ;
  `reception_fournisseur_confirmee` et `facture_fournisseur_creee` → installations ; `produit_modifie` →
  ventes ; `ventes.utils` est un noyau partagé de fait ; `paiement_fournisseur_enregistre`,
  `mouvement_stock_enregistre` sans abonné. Contrat : prix/fiche corrigé propagé aux devis non figés
  (« prix négocié intouchable »), réservations cohérentes avec chantiers / BC.
- **J6 documents** — `document_produit` ventes → ged ; portail = consommateur pur par sélecteurs.
  Contrat : le client voit TOUJOURS la version en vigueur (« mis à jour le … »), rien hors de son
  périmètre (NTPRT14), même CGV que le PDF ; aucun compte portail seedé (couverture à déclarer).
- **X3 parametres** — parametres, notifications, automation, onboarding, bus `core/events.py` (79
  signaux déclarés) et `core/event_coverage.py`. Contrat : un réglage lu UNE fois ; documents envoyés
  gardent leur version figée ; aucun texte client codé en dur ailleurs ; messages WA / e-mail = ce que
  l'étape promet.
- **D4 générateur** — `pages/ventes/DevisGenerator.jsx` (5 668 l.), `features/ventes/solar.js` ;
  internes de `proposition/[...token].astro` et `roof-tool-pro11.ts` lus. Écran 100 % TTC, `noValidate`,
  `step="any"`, indicateur de marge générateur seulement. Contre-visite QJR5.
- **J1b devis** — propriétaire résiduel de `apps/ventes` et des écrans ventes ; couture crm ↔ ventes la
  plus lourde (`creation.py`, `crm/selectors.py:364,421`) ; `devis_accepted` (`cycle_vie.py:1192`) →
  crm, installations, sav, automation, onboarding (pas publicapi ni notifications) ; `devis_sent`
  (`cycle_vie.py:2317`) → crm, calepinage, onboarding ; `accept_devis` (`:1196`) doit se comporter à
  l'identique depuis ses DEUX appelants (`views/devis.py:2327` interne, `public_views.py:4489` OTP
  public) ; `devis_refused` émis depuis une vue (`views/devis.py:2386`) ; `Devis.roof_layout`
  (`models.py:207`, re-posé par `resynchronisation.py:1070-1097`). Contre-visite QJR5 : les 171 tâches
  QJR5 + les 14 ERR-QJR5 + #772 tiennent-elles EN DIRECT ?
- **X5 deploy** — `erp_agentique/settings/*`, Dockerfiles, `docker-compose*.yml`, Caddy / nginx,
  `.github/workflows`, `scripts/**`, socle front (`router/index.jsx`, `components/`, `ui/`, client API) ;
  `manage.py check --deploy` ; parité CI ↔ image (leçon 1).
- **J4 sav** — `chantier_receptionne` → sav + monitoring ; `intervention_completed` → sav + onboarding ;
  `ticket_resolu` → crm + notifications ; `equipement_remplace`, `abonnement_monitoring_resilie` abonnés
  sans émetteur ; `/suivi/:token` ERP ≠ `apps/web/src/pages/suivi` (hôtes différents). Contrat : ticket
  corrigeable / réouvrable ; garantie à partir de la réception ; SLA calculé d'une seule façon.
- **X7 analyse** — reporting, publicapi, dataimport, offlinesync, uxviews, semantic, statuspage, agent,
  `backend/fastapi_ia` ; `publicapi/signals.py` écoute `pre_save`/`post_save` sur Lead, Devis,
  Installation, Intervention, Facture… = **second canal d'événements que personne n'audite** ; reporting
  importe directement les modèles d'autres apps (app fondation, autorisé, mais couplage) ; les chiffres de
  pilotage se recalculent depuis UNE source.
- **X6 performance** — C14 sur les points chauds ; tâches routées aux propriétaires.

---

## §E Ce qu'on NE fait PAS, et limites honnêtes

### E.1 Anti-patterns

1. Prompt « trouve des problèmes » sans modèle qualité ni seuils écrits d'abord (ISO 25040, SQALE, Google).
2. Objectif non réfutable (« modifiable et robuste ») — ATAM.
3. Découper par app Django, par couche ou par écran — mesuré : 0 % de couture interne, 40 lanes.
4. Un parcours géant par unité — mesuré : ventes relu 7 fois, 23/40 apps sans propriétaire.
5. Auditer le code partagé dans chaque unité verticale (Evans *Shared Kernel*) — verdicts contradictoires.
6. Le constructeur certifie sa construction ; le même agent trouve et vérifie ; reprendre un agent pour
   la ronde 2 (ISO 25040, Huang et al., Claude Code best practices).
7. Verdict LLM sans preuve exécutée, ou consensus de relecteurs comme preuve (SWR-Bench, Refute-or-Promote).
8. Mocker la source interne dont la fonctionnalité dépend (Fowler *Mocks Aren't Stubs*, Pact, leçon 3).
9. « Tests verts » ou « % de couverture » comme signal de fin (UTBoost, Fowler *TestCoverage*, mutation
   sur le diff chez Google / Meta ACH).
10. Affaiblir, sauter ou supprimer une assertion ; tester le symptôme par espion ou regex sur le source
    (Anthropic *harness*, EvilGenie, leçon 5).
11. Un seul cycle de test en fin de build ; pas de `vérifie` après fusion (Microsoft, QJR5).
12. Walkthrough « chemin heureux » seulement, sur données de démo seulement (Microsoft, OWASP).
13. Compter les violations en tas ; N constats pour une cause (SIG).
14. Nettoyage ponctuel sans garde (Google *Build Debt*).
15. Mélanger obligatoire et optionnel ; « corrige les N » sans triage (épisode des 47 constats, #547).
16. « Le dev a oublié » comme cause (Lunney ; poka-yoke : empêcher à la source).
17. Tâche vague (« investiguer X »), sans propriétaire, priorité fixée par la lane (Lunney, Bugzilla).
18. Couplage calculé sur une fenêtre courte ou des commits de lot (Tornhill / CodeScene).
19. Convertir les scénarios d'audit en suite E2E permanente (Fowler, Google Testing Blog).
20. Benchmarker un contrôle automatisé après un changement de paramètres/catalogue, ou sans contrôles
    généraux effectifs (AS 2201 B29-B30).
21. Faire confiance à un juge LLM débiaisé mécaniquement sans calibration (2604.23178).
22. Réparer la prod sans diff préalable (`docs/claude-memory/reconfirm-client-visible-repairs.md`).
23. Ajouter des lanes pour « aller plus loin » (go-deep : la profondeur s'achète par lane).
24. Écrire une tâche dans le fichier d'un autre propriétaire, ou réécrire les tâches d'un autre groupe ;
    lancer `PLAN_AUDIT_TRANSVERSE.md` ou `PLAN_CRM_VENTES.md` en même temps qu'un plan qui possède leurs
    fichiers.

### E.2 Limites honnêtes

- **Un audit est un indicateur corrélé, jamais une preuve d'absence** (ISO/IEC 5055 : mesures
  « correlated rather than absolute » ; 5055 mesure le source sans observer le comportement, 25023 le
  comportement sans localiser la cause — d'où les deux canaux). Le rapport dit ce qui n'a PAS été lu,
  exécuté ou joué.
- Cinq audits du même parcours en 32 jours n'ont pas convergé. La v2 change le format des tâches et la
  clôture, pas la capacité de détection : le gain attendu est sur les 14 défauts post-build, pas sur les
  167 constats.
- Les réfuteurs maison n'ont presque jamais réfuté (1/167 sur QJR5 ; 0/77 sur QJR2 selon la recherche,
  non re-vérifié) : jusqu'à calibration, « confirmé »
  signifie « preuve exécutée », pas « un second agent est d'accord ».
- Les chiffres de couplage viennent de regex et de scripts de session non conservés : à reproduire par
  `scripts/audit_couplage.py` avant réutilisation ; canal `post_save` non pondéré ; graphe front non
  calculé ; tailles X3-X7 estimées ; historique dominé par des lots d'agents.
- La table de propriété du registre est une première affectation : `pages/activities`, `backend/fastapi_ia`
  et le résiduel front attribué à X5 sont à confirmer par la session de propriété (`docs/ownership.yml`).
- Les sources ERP (Microsoft Dynamics, ISACA, PCAOB) sont appliquées par analogie ; AS 2201 lu dans une
  compilation archivée 2017 ; GTAG de seconde main (Indiana) ; CMMI / ISO 9001 via sources secondaires ;
  SAP et Odoo : rien de vérifié, rien d'utilisé.
- Relations métamorphiques (X2) et liste fermée des déclencheurs : conceptions maison ; le test
  différentiel (McKeeman) et métamorphique (Chen et al.) n'ont été confirmés qu'au niveau de leur
  existence, ils ne sont donc pas cités en §F.
- Les personas « comptable », « magasinier », « bureau d'études » n'ont pas de rôle réel : le walkthrough
  par rôles réels est partiel tant que ces rôles n'existent pas (décision fondateur, hors audit).
- Les lanes ne pilotent ni docker ni la DB de test (`docs/LANE_BRIEF.md`) : la preuve en direct est portée
  par l'orchestrateur et la CI — un goulot assumé.

---

## §F Sources

Vérifiées le 02/10/2026 ; « partiel » = seule la partie confirmée est utilisée.

**Normes et modèles qualité**
- ISO/IEC 25040:2011 Evaluation process (aperçu : définitions, table des matières) — https://cdn.standards.iteh.ai/samples/35765/6a04b9b3833d405fa71336750ae72198/ISO-IEC-25040-2011.pdf
- iso25000.com — ISO/IEC 25040 (listes de tâches d'activité : portail seulement) — https://iso25000.com/index.php/en/23-english/iso-iec-25040
- iso25000.com — ISO/IEC 25010 — https://iso25000.com/index.php/en/iso-25000-standards/iso-25010
- ISO/IEC 5055:2021 (aperçu) — https://cdn.standards.iteh.ai/samples/80623/df09ef29b30644ae9921f30c955fa939/ISO-IEC-5055-2021.pdf
- SIG / TÜV NORD CERT — Evaluation Criteria Trusted Product Maintainability v17.0 — https://softwareimprovementgroup.com/wp-content/uploads/2020-SIG-TUViT-Evaluation-Criteria-Trusted-Product-Maintainability.pdf
- SIG — Maintainability model 2024 update — https://www.softwareimprovementgroup.com/blog/maintainability-model-2024-update/
- Cutter — The SQALE Method (partiel) — https://www.cutter.com/article/managing-technical-debt-sqale-method-490726
- SonarSource — SQALE (partiel) — https://www.sonarsource.com/blog/sqale-the-ultimate-quality-model-to-assess-technical-debt/
- SEI/CMU — ATAM (CMU/SEI-2000-TR-004, partiel : arbre d'utilité, H/M/L) — https://www.sei.cmu.edu/documents/629/2000_005_001_13706.pdf
- arc42 — Section 10 (partiel : stimulus/réponse/mesure, usage et changement) — https://docs.arc42.org/section-10/
- Google eng-practices — The Standard of Code Review (partiel) — https://github.com/google/eng-practices/blob/master/review/reviewer/standard.md
- Google eng-practices — What to look for in a code review — https://github.com/google/eng-practices/blob/master/review/reviewer/looking-for.md
- Google — Morgenthaler et al., Searching for Build Debt — https://static.googleusercontent.com/media/research.google.com/en//pubs/archive/37755.pdf
- OWASP — ASVS 5.0 V8 Authorization (partiel pour les niveaux) — https://github.com/OWASP/ASVS/blob/master/5.0/en/0x17-V8-Authorization.md
- OWASP — WSTG 4.2 IDOR — https://wstg.owasp.org/v4.2/4-Web_Application_Security_Testing/05-Authorization_Testing/04-Testing_for_Insecure_Direct_Object_References
- OWASP — Multi-Tenant Security Cheat Sheet — https://cheatsheetseries.owasp.org/cheatsheets/Multi_Tenant_Security_Cheat_Sheet.html
- OWASP — WSTG 4.2 Business Logic Testing — https://wstg.owasp.org/v4.2/4-Web_Application_Security_Testing/10-Business_Logic_Testing/00-Introduction_to_Business_Logic

**Audit d'ERP et de processus**
- Microsoft Learn — Process-focused solution implementation lifecycle — https://learn.microsoft.com/en-us/dynamics365/guidance/implementation-guide/process-focused-solution-implementation-lifecycle
- Microsoft Learn — Testing strategy: test types — https://learn.microsoft.com/en-us/dynamics365/guidance/implementation-guide/testing-strategy-test-types
- Microsoft Learn — Testing strategy checklist — https://learn.microsoft.com/en-us/dynamics365/guidance/implementation-guide/testing-strategy-checklist
- ISACA Journal — Singleton, Auditing Applications, Part 2 — https://community.mis.temple.edu/mis5203sec951spring2023/files/2019/01/Auditing-Applications-Part-2.pdf
- Indiana SBOA — Chapter 14 IT Controls (partiel pour 14.6.5) — https://www.in.gov/sboa/files/CH14-Information-Technology-Controls.pdf
- PCAOB — Auditing Standards as of December 14, 2017 (AS 2201 .21, .37, B28-B30 ; partiel) — https://assets.pcaobus.org/pcaob-dev/docs/default-source/standards/archived/documents/auditing-standards-as-of-december-14-2017-944330126.pdf
- van der Aalst — Process Mining in the Large: A Tutorial — https://www.vdaalst.rwth-aachen.de/publications/p775.pdf
- Berti, van der Aalst — Event Data Extraction from SAP ERP (arXiv 2110.03467) — https://arxiv.org/pdf/2110.03467

**Découpage et dépendances**
- Martin Fowler — BoundedContext — https://martinfowler.com/bliki/BoundedContext.html
- Microsoft — Domain analysis for microservices — https://learn.microsoft.com/en-us/azure/architecture/microservices/model/domain-analysis
- Microsoft — Identify microservice boundaries — https://learn.microsoft.com/en-us/azure/architecture/microservices/model/microservice-boundaries
- Ozkan et al. — DDD: A Systematic Literature Review (arXiv 2310.01905) — https://arxiv.org/pdf/2310.01905
- Eric Evans — Domain-Driven Design Reference (2015 ; partiel pour les pistes transverses) — https://www.domainlanguage.com/wp-content/uploads/2016/05/DDD_Reference_2015-03.pdf
- Lean Enterprise Institute — Value-Stream Mapping — https://www.lean.org/lexicon-terms/value-stream-mapping/
- ISTQB — CTFL Syllabus v4.0.1 §5.2 (partiel) — https://istqb.org/wp-content/uploads/2024/11/ISTQB_CTFL_Syllabus_v4.0.1.pdf
- Adam Tornhill — Code as a Crime Scene — https://www.adamtornhill.com/articles/crimescene/codeascrimescene.htm
- CodeScene — Change Coupling — https://codescene.io/docs/guides/technical/change-coupling.html
- Microsoft Research — Nagappan, Ball, TR-2006-03 — https://www.microsoft.com/en-us/research/wp-content/uploads/2016/02/tr-2006-03.pdf
- Martin Fowler — The Practical Test Pyramid (partiel) — https://martinfowler.com/articles/practical-test-pyramid.html
- Google Testing Blog — Just Say No to More End-to-End Tests — https://testing.googleblog.com/2015/04/just-say-no-to-more-end-to-end-tests.html
- Martin Fowler — Consumer-Driven Contracts — https://martinfowler.com/articles/consumerDrivenContracts.html
- Pact — Documentation — https://docs.pact.io/

**Agents LLM, vérification, oracles**
- Anthropic — Claude Code best practices — https://code.claude.com/docs/en/best-practices
- Anthropic — Claude Code sub-agents — https://code.claude.com/docs/en/sub-agents
- Anthropic — How we built our multi-agent research system — https://www.anthropic.com/engineering/multi-agent-research-system
- Anthropic — Demystifying evals for AI agents — https://www.anthropic.com/engineering/demystifying-evals-for-ai-agents
- Anthropic — Effective harnesses for long-running agents — https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents
- SWR-Bench (arXiv 2509.01494) — https://arxiv.org/html/2509.01494v1
- Refute-or-Promote (arXiv 2604.19049 ; partiel : domaine sécurité) — https://arxiv.org/abs/2604.19049
- Huang et al. — LLMs Cannot Self-Correct Reasoning Yet (arXiv 2310.01798) — https://arxiv.org/pdf/2310.01798
- Survey LLM-as-a-judge (arXiv 2411.15594 ; partiel) — https://arxiv.org/html/2411.15594v6
- Judging the judges (arXiv 2604.23178 ; partiel) — https://arxiv.org/html/2604.23178
- Sensitivity/specificity reporting for LLM judges (arXiv 2511.21140 ; tailles non vérifiées) — https://arxiv.org/pdf/2511.21140
- Meta — ACH (arXiv 2501.12862 ; partiel) — https://arxiv.org/html/2501.12862v1
- Google Research — State of Mutation Testing at Google — https://research.google/pubs/state-of-mutation-testing-at-google/
- UTBoost (arXiv 2506.09289) — https://arxiv.org/pdf/2506.09289
- Hypothesis — Stateful testing — https://hypothesis.readthedocs.io/en/latest/stateful.html
- Playwright — Best practices (partiel) — https://playwright.dev/docs/best-practices
- EvilGenie (arXiv 2511.21654 ; partiel) — https://arxiv.org/pdf/2511.21654

**Du constat à la tâche et à la clôture**
- IBM — Orthogonal Defect Classification v5.2 — https://s3.us.cloud-object-storage.appdomain.cloud/res-files/70-ODC-5-2.pdf
- Chillarege — ODC for process control — https://www.chillarege.com/docs/Papers/odc-process-control/
- Google SRE — Lunney et al., Postmortem Action Items — https://static.googleusercontent.com/media/sre.google/en//static/pdf/login_spring17_09_lunney.pdf
- Google SRE — Workbook, Postmortem Culture — https://sre.google/workbook/postmortem-culture/
- ISO 9001:2015 clause 10.2 (secondaire, partiel) — https://davidbarker.consulting/iso9001/clause-10-2-nonconformity-and-corrective-action/
- Wikipedia — Process area (CMMI), CAR (secondaire, partiel) — https://en.wikipedia.org/wiki/Process_area_(CMMI)
- Bill Wake — INVEST in Good Stories, and SMART Tasks — https://www.xp123.com/invest-in-good-stories-and-smart-tasks/
- Martin Fowler — GivenWhenThen — https://martinfowler.com/bliki/GivenWhenThen.html
- Cucumber — Writing better Gherkin — https://cucumber.io/docs/bdd/better-gherkin/
- Martin Fowler — SelfTestingCode — https://martinfowler.com/bliki/SelfTestingCode.html
- Martin Fowler — TestCoverage — https://martinfowler.com/bliki/TestCoverage.html
- Martin Fowler — Mocks Aren't Stubs — https://martinfowler.com/articles/mocksArentStubs.html
- DORA — Software delivery metrics — https://dora.dev/guides/dora-metrics/
- Mozilla — Bugzilla fields (Severity, Priority) — https://wiki.mozilla.org/BMO/UserGuide/BugFields
- Scrum.org — The Scrum Guide — https://scrumguides.org/scrum-guide.html

**Dépôt** (vérifié par commande sur `6742fc3a1`, 02/10/2026) : `backend/django_core/core/parked.py` (47
apps parquées ; 39 dossiers conservés sous `apps/` + `authentication` = 40 propriétés, chacune possédée
par exactement une unité du registre) ; les scripts `scripts/check_*.py`, `plan_lanes.py`,
`plan_progress.py`, `ci_guards.py`, `codemap_fingerprint.py`, `rapport_backend_sombre.py`,
`frontend/scripts/check_dockerfile_context.mjs` ; `backend/django_core/tests/test_tenant_sweep.py`,
`testkit/tenant_sweep.py` ; `apps/ventes/coherence/` + `management/commands/audit_coherence.py` (22
`@regle`) ; les tests `test_proprietes_*`, `test_solar_differential*`, `test_figures_parite.py`,
`solar.properties.test.mjs`, `frontend/e2e/figures-parite.spec.js` (parmi 50 fichiers
`frontend/e2e/*.spec.js`) ; 11 répertoires `contract_samples` ; `.importlinter` (16 contrats) ;
`docs/{LANE_BRIEF,TEST_AUTHORING_CONTRACT,invariants}.md`, `docs/BUILD_ORDER.yml`,
`docs/qa-explorer.config.yml` ; commandes `seed_demo`, `seed_demo_company`, `qa_import_anonymise`
(`authentication/management/commands/`).
