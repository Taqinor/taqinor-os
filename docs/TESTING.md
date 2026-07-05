# Stratégie de tests — TAQINOR OS

But : des tests **utiles et non redondants**, **gatés** (ne tournent que quand la
bonne surface change) et **étagés** (le retour est rapide à chaque merge ; le gros
de la vérification ne tourne qu'« à la toute fin »). On lance `work on the plan`
2–3 fois — chaque merge passe un gate rapide — puis on tire **une fois** la suite
complète avant de livrer.

## Les deux axes de gating

1. **Par surface (quoi a changé)** — le job `changes` de `ci.yml` calcule, par
   `git diff`, des booléens `backend` / `frontend` / `web` / `code`. Chaque job
   lourd porte un `if:` sur ces sorties (fail-open : si le diff est introuvable,
   tout tourne). `stage-names` reste **toujours** actif (garde-fou de dérive).
2. **Par cadence (quand ça vaut le coût)** — étiquettes de tests + un workflow
   `release-verify.yml` séparé. C'est la pièce qui répond à « les gros tests
   seulement à la fin ».

## Les 4 paliers

| Palier | Contenu | Quand | Mécanisme |
|--------|---------|-------|-----------|
| 0 — Statique | flake8, eslint, `tsc` (web), import-linter, check_stages, fingerprint CODEMAP | chaque changement, par surface | `if:` chemin (déjà en place) |
| 1 — Unitaire | logique pure : sizing solaire, références, utils, composants/UX (RTL+axe) | chaque changement, par surface | chemin ; back `--exclude-tag` |
| 2 — Intégration + smoke | service-layer, multi-tenant, **événements métier**, + **smoke e2e** (lead→devis→PDF, santé) | **chaque merge** (garde `main` sûr) | chemin ; smoke Playwright |
| 3 — Vérif complète | suite Django COMPLÈTE (`pdf`/`slow`), **matrice e2e complète** (desktop+mobile), **régression visuelle**, Lighthouse | **à la toute fin** — manuel + nightly | `release-verify.yml` |

Le palier 3 **ne garde pas `main`** (non requis) : c'est une vérif d'ampleur, pas
le gate de merge — donc il peut être plus lent/flaky sans bloquer les livraisons.

## Backend — étager sans dépendance

Le runner Django gère les étiquettes nativement. Les tests lourds (rendu
WeasyPrint, golden PDF) portent `@tag('pdf')` / `@tag('slow')` :

```bash
# Palier par-merge (rapide) — exclut le lourd :
python manage.py test apps authentication --exclude-tag=pdf --exclude-tag=slow
# Palier release-verify (complet) :
python manage.py test apps authentication
```

Tests étiquetés `pdf` aujourd'hui : `test_pdf.TestPdfRender`,
`test_quote_engine.TestPremiumPdfRender`, `test_extra_docs._Base` (et ses
sous-classes). Pour en ajouter : `from django.test import tag` puis `@tag('pdf')`
sur la classe.

## Frontend — deux couches distinctes

* **Logique pure** → `node --test` sur `src/**/*.test.mjs` (**auto-découverte** :
  tout nouveau `*.test.mjs` tourne, aucune liste à maintenir).
* **Composants / UX** → **Vitest + Testing Library + axe** sur `src/**/*.test.jsx`
  (jsdom) : rendu, interaction (clic/frappe) et **accessibilité**. Lancer
  `npm run test:unit`. Les deux couples ne se chevauchent pas (extensions
  distinctes).

Régression visuelle (`e2e/visual.spec.js`, étiquette `@visual`) : tourne
**uniquement** dans `release-verify`. Au 1er run, `--update-snapshots` génère les
baselines, uploadées en artefact `visual-baselines` ; le fondateur les relit puis
les commit sous `e2e/**-snapshots/` pour activer la vraie comparaison pixel.

## Smoke e2e vs matrice complète

Le projet Playwright `setup` (connexion réelle) est une **dépendance** des projets
`chromium`/`mobile`, donc il tourne toujours. Le smoke par-merge cible des parcours
UTILISATEUR **self-contained** (`--project=chromium devis.spec.js health.spec.js`
— `devis` = lead → devis → PDF) ; la matrice complète (toutes les specs + mobile)
part dans `release-verify`. ⚠️ Pour promouvoir un spec en smoke il doit être
AUTONOME : `leads.spec` (E7 → Signé) dépend d'un devis créé par un spec antérieur
dans la matrice ordonnée, donc il reste en e2e complet (le rendre autonome est un
préalable à sa promotion).

### Règle permanente : un parcours e2e par fonctionnalité
Toute nouvelle fonctionnalité ship avec **au moins un test e2e qui la pilote comme
un utilisateur** (Playwright + les helpers `e2e/helpers.js`). Les parcours
réellement critiques sont **promus dans le smoke par-merge** (ci.yml) pour attraper
« ça marchait pas au final » AVANT le merge ; les autres vivent dans la matrice
complète (`release-verify`). C'est le garde-fou n°1 contre les régressions
fonctionnelles silencieuses.

## Couverture (un % visible, pas une promesse)
- Front (logique pure) : `node --test --experimental-test-coverage`.
- Front (composants/UX) : `npm run test:coverage` (Vitest + v8).
- Back : `coverage run manage.py test … && coverage report` (config `.coveragerc`).
Les % s'impriment en CI (informatif, **non bloquant** — on ne fixe pas de seuil
artificiel). But : rendre l'écart visible, jamais prétendre « 100 % testé ».

## Déclencher le palier 3

`release-verify.yml` : **bouton** « Run workflow » (workflow_dispatch) **+**
**nightly** (cron 03:00 UTC, filet anti-pourrissement). À tirer une fois, après
les 2–3 passes de `work on the plan`, avant de livrer.

## Principes anti-redondance

* Tester le **comportement**, pas l'implémentation ni le framework (pas de
  snapshot de markup trivial, pas de test de Radix/React-Router/Django).
* Vérifier chaque comportement **au palier le plus bas** qui a du sens ; ne
  promouvoir en e2e que les parcours transverses réels.
* **Une intention par test.**

## Service FastAPI (IA)
`backend/fastapi_ia/tests/` (sécurité agent NL→SQL, JWT, OCR, garde-marge) tourne
désormais dans **`release-verify`** (job `fastapi-tests`, Postgres + Redis +
requirements complètes) — palier 3 car les dépendances sont lourdes
(langchain/torch). Les suites se sautent proprement si une dépendance manque.
Promotion possible en gate par-merge (path-gated sur `backend/fastapi_ia/**`) une
fois la stabilité confirmée.

## Cohérence des données inter-modules
Tous les liens inter-modules sont de **vrais FK** (`db_constraint=True`) : la base
empêche déjà les orphelins (la ligne référencée existe forcément). Ce qu'un FK ne
garantit PAS : qu'elle soit dans la **bonne société**. D'où l'outil :

```bash
python manage.py check_data_integrity          # rapport + exit 1 si fuite
```

`authentication/management/commands/check_data_integrity.py` — auditeur LECTURE
SEULE, **générique** (registre d'apps Django) : il couvre AUTOMATIQUEMENT tout
modèle, présent ou futur, portant un FK `company`, et signale tout FK pointant vers
une autre société (168 liens analysés aujourd'hui). À lancer sur la prod (sans
risque) ou en cron. Le logique est gardée par `tests_data_integrity.py` (détecte un
lien inter-sociétés planté, ignore les données propres). C'est le filet « quand on
ajoute une fonctionnalité, la donnée reste connectée DANS sa société » — il s'étend
tout seul aux nouveaux modèles.

## Base partagée — `testkit/` (factories + auth multi-tenant)

`backend/django_core/testkit/` (dép DEV `factory_boy`, jamais en prod) fournit :

* `testkit/factories.py` — `CompanyFactory`, `UserFactory`, `ClientFactory`,
  `ProduitFactory`, `DevisFactory`/`LigneDevisFactory` : chaque factory
  attache une `company` par défaut et garde le graphe cohérent (le client
  d'un devis est TOUJOURS dans la même société que le devis). `build()` =
  instance en mémoire, sans requête DB (logique pure/serializers) ; `create()`
  = persistance réelle (querysets/contraintes). `another_tenant()` construit
  une 2ᵉ société + utilisateur pour les tests d'isolation.
* `testkit/base.py` — `TenantAPITestCase(TestCase)` : `setUp` monte
  `self.company`/`self.user` + `self.other_company`/`self.other_user`, et
  `self.client_as(user=None, role=None)` renvoie un `APIClient` authentifié
  (JWT réel via `AccessToken.for_user`).

**Convention : tout nouveau test API hérite de `TenantAPITestCase` ; on
construit les objets via les factories `testkit`, jamais `objects.create` à la
main.** Exemple d'usage : `core/tests/test_testkit.py`.

## Mutation testing (qualité des assertions, pas juste la couverture)

La couverture (% de lignes exécutées) ne dit rien de la QUALITÉ des
assertions — un test peut exécuter une ligne sans jamais vérifier son
résultat. `mutmut` (dép DEV, `setup.cfg [mutmut]`) mute volontairement un
petit périmètre à haut risque — `apps/ventes/quote_engine/builder.py`,
`apps/ventes/utils/references.py`, `apps/roles/models.py` — et vérifie que la
suite existante tue chaque mutant. Lancé UNIQUEMENT par
`.github/workflows/mutation.yml` (nightly + bouton, `continue-on-error`,
jamais un gate par-commit — le coût est O(mutants × suite complète)).

**Triage d'un mutant survivant** (rapport `mutmut results` / artefact CI) :
* Assertion manquante → ajouter un test qui aurait tué ce mutant.
* Mutant sémantiquement équivalent (le mutant produit le même comportement
  observable, ex. `<` → `<=` sur une borne jamais atteinte) → whitelister
  explicitement dans `setup.cfg` avec un commentaire justifiant pourquoi.
Lancer localement sur un seul module : `mutmut run --paths-to-mutate
apps/ventes/utils/references.py`.

## Pistes restantes
* Parcours e2e par fonctionnalité pour les flux encore non couverts (stock,
  installations, SAV, reporting) : **scaffolds prêts** (`frontend/e2e/{stock,
  installations,sav,reporting}.spec.js`, en `test.fixme` → visibles comme TODO
  sans casser la suite). Pour les remplir : `bash scripts/e2e-local.sh` (monte la
  pile en une commande), puis `npx playwright codegen http://localhost:4173/<route>`
  pour des sélecteurs FIABLES ; enlever `.fixme`, garder le test autonome, puis
  promouvoir les plus critiques dans le smoke.
* Garde-fous de règles (#3 Meta `PAUSED`, #4 `/proposal` seul chemin PDF devis) —
  à étoffer au palier 1/2 quand le code correspondant atterrit.
* Régression visuelle : commiter les baselines générées par `release-verify` pour
  activer la comparaison pixel.
