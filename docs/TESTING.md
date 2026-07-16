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
sous-classes), `test_quote_engine_snapshot.TestQuoteEngineGoldenSnapshots`
(YTEST10, également `@tag('slow')`). Pour en ajouter : `from django.test import
tag` puis `@tag('pdf')` sur la classe.

### Snapshots golden PDF (YTEST10/YTEST11) — mise à jour des baselines

`apps/ventes/tests/test_quote_engine_snapshot.py` rend chaque format du moteur
de devis premium (full, full+étude, une-page, agricole/pompage) sur des
données fixes, rasterise en PNG (PyMuPDF/`fitz`) et compare à un baseline
COMMITÉ sous `apps/ventes/tests/baselines/` avec un seuil de diff pixels (2 %
— jamais une égalité octet-à-octet, WeasyPrint/matplotlib varient légèrement
d'une machine à l'autre). Assertions structurelles en plus du pixel : nombre
de pages exact, présence de la chaîne de totaux (Sous-total HT/Total HT/
TVA/Total TTC), absence stricte de `prix_achat`.

**La CI ne régénère JAMAIS les baselines automatiquement** — un baseline
manquant ou divergent fait ÉCHOUER le test avec un message pointant ici,
jamais un auto-accept silencieux. Pour régénérer (revue humaine du diff PNG
obligatoire avant de committer) :

```bash
docker compose exec django_core python manage.py update_pdf_baselines
git diff --stat apps/ventes/tests/baselines/   # relire CHAQUE page qui a changé
git add apps/ventes/tests/baselines/ && git commit
```

La commande partage le même code de rendu/comparaison que le test
(`UPDATE_PDF_SNAPSHOTS=1` en interne) — jamais deux logiques de génération
divergentes. Un changement de baseline non revu ne doit jamais être committé
« parce que le test passe » : le diff PNG EST la revue.

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

## Test de charge (k6) — le gate est le percentile, jamais la moyenne

`loadtests/` (k6) modélise un mix de trafic réaliste sur les endpoints
critiques : `browse.js` (scénario `load` — login rare + liste devis/clients en
lecture, montée progressive), `create-devis.js` (écriture — création de devis
isolée pour ne pas diluer sa latence dans le volume de lecture), `spike.js`
(scénario `spike` — surge soudaine 5→100 VUs, mode de défaillance différent
d'une charge soutenue : saturation de pool/queue). Seuils déclarés par
PERCENTILE (`p(95)<800ms`, `p(99)<1500ms`, `http_req_failed<0.5%`,
`loadtests/common.js`) — **jamais la moyenne**, qui masque la traîne qui fait
mal aux utilisateurs réels. `.github/workflows/loadtest.yml` lance un smoke
COURT (~5 min, `browse.js` seul) en nightly + bouton, `continue-on-error`
(non bloquant tant que la stabilité n'est pas prouvée) ; le soak long et
`spike.js` restent manuels. Lancer en local : `k6 run -e
BASE_URL=http://localhost:8000 loadtests/browse.js`.

## Déterminisme — temps figé + Faker seedé

Tout test dépendant de la date/heure ou de l'aléatoire doit être déterministe :
* **Temps** — `testkit/time.py` expose `frozen(when)` (enrobe `freezegun`, dép
  DEV) : `with frozen('2026-01-01 10:00:00'): …` ou en décorateur. Jamais de
  test qui compare à un `timezone.now()` VIVANT dans une assertion (flaky près
  d'une frontière d'horloge) — figer le temps à la place.
* **Aléatoire** — `Faker.seed(1234)` (ou `faker.Faker().seed_instance(1234)`)
  pour toute donnée « réaliste mais aléatoire » ; ne jamais compter sur la
  seed par défaut de Faker (change à chaque run).
* **Jamais de `sleep` fixe** — ni `time.sleep(` côté backend, ni
  `page.waitForTimeout(`/`sleep(` fixe côté Playwright (attendre une
  condition explicite à la place).

Gardé par `scripts/check_test_determinism.py` (job `stage-names`, toujours
actif) : échoue sur un `time.sleep(` backend, un `page.waitForTimeout(` e2e,
ou une assertion comparant à un `timezone.now()` non figé. Les infractions
préexistantes (2026-07, apps `compta`/`kb`/`ventes` — hors périmètre de cette
lane) sont whitelistées explicitement dans le script avec la justification ;
toute NOUVELLE infraction fait échouer le build.

## Registre d'invariants métier + bug → test-rouge-d'abord

`docs/invariants.md` recense les invariants critiques (référence sous
concurrence, numérotation non-count+1, chaîne TVA, réconciliation des
totaux, transitions de statut légales, scoping tenant, absence de
`prix_achat` client-facing), chacun lié au test NOMMÉ qui le garde
(`fichier.py::Classe::test_méthode`). `scripts/check_invariants.py` (job
`stage-names`, toujours actif) échoue si une référence ne résout plus vers un
test réel — un invariant ne doit jamais perdre son garde-fou en silence.

**Règle permanente : tout bug corrigé atterrit avec un test qui échoue AVANT
le correctif et passe après** (le backlog de bugs vit dans
`docs/ERROR_PLAN.md`). Un ticket qui change un comportement observable sans
un test de régression qui l'aurait attrapé n'est pas terminé.

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
