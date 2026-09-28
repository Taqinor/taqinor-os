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
`test_quote_engine_formats.TestPremiumPdfRender` (la suite `test_quote_engine`
a été scindée le 19/08/2026 en `_formats` / `_residential` / `_documents` /
`_builder` ; les classes résidentielles portent aussi `pdf`),
`test_extra_docs._Base` (et ses
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
- Front (logique pure) : `node --test "src/**/*.test.mjs"` (ajouter `--experimental-test-coverage` en local si l'on veut le % couvert — la CI ne l'instrumente plus depuis SOLMVP54, personne ne lisait le rapport).
- Front (composants/UX) : `npm run test:unit` (Vitest) ; `npm run test:coverage` (v8) reste disponible en local, hors CI.
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
petit périmètre à haut risque et vérifie que la suite existante tue chaque
mutant. Lancé UNIQUEMENT par `.github/workflows/mutation.yml` (nightly +
bouton, `continue-on-error`, jamais un gate par-commit — le coût est
O(mutants × suite complète)).

**Périmètre (QAH5, `setup.cfg [mutmut]`)** : `apps/ventes/quote_engine/builder.py`,
`apps/ventes/utils/references.py`, `apps/roles/models.py` (héritage YTEST9) ;
plus, depuis QAH5, la CHAÎNE D'ARGENT ventes — `apps/ventes/domain/argent.py`
(la façade dont délèguent `Devis.total_ht`/`total_tva`/`total_ttc`) et
`apps/facturation/totaux.py` (`TotauxDocumentMixin`, le SEUL propriétaire de
la chaîne HT → remise globale → TVA → TTC partagé par `Facture`/`Avoir`
(`apps/facturation/models.py`) et `NoteDebit` (`apps/ventes/models.py`),
AUD105-107) — et les MIXINS/PERMISSIONS DE SCOPING SOCIÉTÉ —
`core/mixins.py` (`TenantMixin`, `SameCompanyFKSerializerMixin`) et
`core/permissions.py` (`ScopedPermission`, `WriteScopedPermissionMixin`),
la base ARC2/ARC55 dont hérite `CompanyScopedModelViewSet`.

**QAH5 — mutmut 2.4.4 → 3.8.0 : le VRAI constat de départ était pire que
« la config a changé ».** Un run CI réel de l'ANCIENNE config (mutmut 2.4.4,
`gh run view 36309232413 --log`) prouve que ce job n'a **jamais exécuté un
seul mutant** : `mutmut run --CI` s'arrêtait en 0,4 s avec
`Error: You must specify a list of paths to mutate.`, avalé en silence par le
`|| true` du workflow — d'où un job « vert » en ~1,5 min qui ne testait rien.
Cause racine, reproduite avec le code source de mutmut 2.4.4 : `setup.cfg`
écrivait `paths_to_mutate` en continuation multi-ligne AVEC UNE VIRGULE en
fin de ligne (`apps/.../builder.py,\n    apps/.../references.py,`) —
ConfigParser joint les lignes de continuation par un VRAI `\n`, donc chaque
chemin découpé sur la virgule gardait un `\n` COLLÉ EN TÊTE
(`'\napps/.../builder.py'`) ; `Path('\napps/...').exists()` teste un premier
segment bogué (`"\napps"`, pas `"apps"`) et échoue TOUJOURS, donc mutmut ne
voyait plus aucun chemin valide. mutmut 3.8.0 aurait fait la MÊME erreur
autrement : son lecteur de config découpe la même valeur sur `\n` au lieu de
la virgule, ce qui aurait laissé une VIRGULE COLLÉE EN FIN de chaque chemin
sauf le dernier (`'apps/.../builder.py,'`) — silencieusement 0 fichier
trouvé, sans la moindre erreur cette fois. **Le seul format sûr pour les deux
lecteurs : un chemin par ligne, jamais de virgule** — c'est celui posé
maintenant dans `setup.cfg [mutmut]`.

**QAH5 (approfondi) — le pont pytest-django est maintenant posé et VÉRIFIÉ
localement (autant que possible sans Postgres).** `requirements-dev.txt`
gagne `pytest==9.0.3` + `pytest-django==4.14.0` ; `setup.cfg` gagne une
section `[tool:pytest]` (`DJANGO_SETTINGS_MODULE`, les motifs de fichiers de
test RÉELS de ce dépôt, `--no-migrations`, l'exclusion `pdf`/`slow`) :

* **Vérifié avec le vrai lecteur de config de mutmut 3.8.0** (import direct
  de `mutmut.configuration._load_config()` contre ce `setup.cfg`, pas une
  ré-implémentation) : les 7 chemins de `paths_to_mutate` et les 13 fichiers
  de `tests_dir` ressortent PROPRES, sans virgule parasite, `process_isolation`
  vaut bien `forkserver`.
* **Vérifié avec un vrai `pytest`, sans AUCUN flag manuel** (tout vient de
  l'ini) : les deux modules `SimpleTestCase` de ce périmètre
  (`test_qjr122_totaux_additifs.py`, `test_action_permissions.py`) tournent
  **pour de vrai, en vert** — 11 tests + 6 sous-tests passés, zéro base de
  données nécessaire. La collecte (`--collect-only`, aucun accès DB requis)
  réussit sur les 13 fichiers ciblés : **364/429 tests collectés** (65
  déselectionnés par `pdf`/`slow` — proportion cohérente avec l'ancien
  `--exclude-tag`).
* **`python_files` était nécessaire, pas cosmétique** : par défaut pytest ne
  voit que `test_*.py`/`*_test.py`, qui NE matche PAS `tests.py` (un des
  fichiers ciblés, `apps/roles/tests.py`) — preuve : `pytest apps/roles/`
  sans ce réglage collecte 0 test ; avec, 108 (tout le dossier — d'où
  `tests_dir` listant des FICHIERS précis, jamais un dossier, pour rester
  bornée à ce que QAH5 vise réellement).
* **WeasyPrint cassait la collecte de 2 des 13 fichiers**
  (`test_aud106_avoir_remise.py`, `test_aud107_note_debit_remise.py` —
  `import apps.ventes.utils.pdf` en tête de fichier) : `OSError: cannot load
  library 'libgobject-2.0-0'` — WeasyPrint fait un `dlopen()` de
  pango/gobject AU CHARGEMENT du module, et `mutation.yml` n'installait
  aucun paquet système (contrairement à `.github/actions/backend-env`, que
  `ci.yml` utilise ailleurs). Le workflow installe maintenant les 4 mêmes
  paquets apt (`libpango-1.0-0 libpangoft2-1.0-0 libharfbuzz0b
  fonts-dejavu-core`) — vérifié en LOCAL avec un stub `weasyprint` jetable
  hors dépôt sur `PYTHONPATH` (ce poste Windows n'a pas ces bibliothèques
  natives), l'apt réel reste à prouver par la CI.
* **`process_isolation=forkserver`, pas le défaut `fork`** : le défaut forke
  chaque worker depuis le process principal de mutmut APRÈS qu'il ait « fait
  tourner la suite pour collecter les stats » (docstring de
  `mutmut/configuration.py`) — pour nos tests basés sur `TestCase`, ça
  suppose une connexion Postgres/psycopg2 déjà ouverte dans ce process AVANT
  chaque fork, et une socket forkée en plein usage est une source connue de
  corruption silencieuse (psycopg2 n'est pas fork-safe). `forkserver` force
  au contraire un process DÉDIÉ qui ne fait QUE de la collecte
  (`forkserver_warmup=collect`, le défaut) — jamais de vraie connexion DB —
  avant de forker les workers, qui ouvrent chacun leur PROPRE connexion
  après coup. Raisonné depuis le code source de mutmut, pas prouvé contre un
  vrai Postgres (aucun disponible dans ce lot sandboxé).
* **Ce qui reste STRICTEMENT vérifiable seulement en CI** : la création
  réelle de la base de test par `pytest-django` (`--no-migrations`) contre
  un VRAI Postgres — vérifié que les migrations RunPython des apps
  concernées (`apps/roles/migrations/0004_vta4_...py`,
  `0005_calx347_...py`) ne sont lues par AUCUN des tests ciblés (ils
  construisent leurs propres fixtures dans `setUp`/`setUpTestData`), mais
  « pas de dépendance trouvée dans le code » n'est pas « prouvé vert » ; et
  l'exécution réelle des 353 tests restants (basés sur `TestCase`, donc
  base de données) que ce poste ne peut pas lancer (pas de docker, pas de
  base de test ici).
* **`mutmut run` n'a plus de flag `--CI`** (seul `--max-children` et une
  liste optionnelle de noms de mutants sur la ligne de commande) ; le
  workflow appelle maintenant `mutmut run --max-children 2` (concurrence
  modeste, périmètre volontairement petit).
* **`mutmut junitxml` n'existe plus.** Remplacé par `mutmut results --all`
  (texte, tous les mutants) et `mutmut export-cicd-stats` (JSON global dans
  `mutants/mutmut-cicd-stats.json`) — le workflow écrit un tableau par
  module dans le job summary (script Python inline sur les internals
  `mutmut.stats`/`mutmut.mutation.data`, défensif si le format interne
  change) en plus de l'artefact `mutation-report`.

**Baseline** : à remplir par la première exécution nocturne réussie (artefact
`mutation-report` / job summary de `.github/workflows/mutation.yml`) — le
pont existe et est vérifié autant que possible sans Postgres, mais le
premier vrai chiffre ne peut venir que de la CI (base réelle, 13 fichiers,
~360 tests par mutant). Une table vide dans le job summary après ce lot
signale maintenant un VRAI problème (à diagnostiquer dans le log de l'étape
`mutmut run`), plus « pont manquant, normal ».

**Triage d'un mutant survivant** (rapport `mutmut results --all` / artefact
CI) :
* Assertion manquante → ajouter un test qui aurait tué ce mutant.
* Mutant sémantiquement équivalent (le mutant produit le même comportement
  observable, ex. `<` → `<=` sur une borne jamais atteinte) → whitelister
  explicitement dans `setup.cfg` avec un commentaire justifiant pourquoi.

Lancer localement (contre une vraie base Postgres) : éditer temporairement
`paths_to_mutate`/`only_mutate` dans `setup.cfg` pour ne garder qu'un seul
fichier, puis `mutmut run` — il n'y a plus de flag CLI `--paths-to-mutate`
en 3.x (toute la config vit dans `setup.cfg`). Pour vérifier juste le pont
pytest (sans mutmut, sans base pour les modules `SimpleTestCase`) :
`cd backend/django_core && python -m pytest apps/ventes/tests/test_qjr122_totaux_additifs.py core/tests/test_action_permissions.py`.

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

## Palier 4 — production (Sentry) — QAH8

Le palier 3 vérifie le code avant qu'il parte ; ce palier 4 est le SEUL qui
observe le comportement RÉEL en production, une fois le pilote armé.

* **Armement** — `@sentry/react` est en dépendance (`frontend/package.json`,
  QAH8) et `frontend/src/lib/monitoring.js` reste un NO-OP TOTAL sans
  `VITE_SENTRY_DSN` (zéro octet, zéro appel — voir `frontend/src/lib/
  monitoring.test.mjs`). Armer le pilote : renseigner `VITE_SENTRY_DSN` (+
  `VITE_SENTRY_ENVIRONMENT`) dans `.env` (voir `.env.example`) et
  `SENTRY_DSN` côté Django (`core/monitoring.py`), puis rebuild — c'est un
  flag BUILD-TIME côté frontend (`docker compose up -d --build frontend`,
  transmis en build arg par `docker-compose.yml`).
* **Session replay** — échantillonnage bas (10 % des sessions, 100 % sur
  erreur) avec masquage de TOUT texte/toute saisie par défaut (`maskAllText`,
  `maskAllInputs`, `blockAllMedia`) : jamais une donnée client (devis, leads,
  factures) dans une capture.
* **Tag `company`** — chaque évènement (backend et frontend) porte le tag
  `company` (`core.monitoring.bind_company` côté Django, `bindCompany` côté
  React dans `monitoring.js`), pour filtrer le bruit d'une société pilote sans
  voir celui des autres.
* **Triage quotidien (15 min)** — chaque matin pendant le pilote : ouvrir le
  projet Sentry, filtrer par `company`, et pour chaque erreur NOUVELLE
  (jamais vue la veille) : (1) lire la pile + le replay associé si présent ;
  (2) décider — bug réel (→ ligne dans `docs/ERROR_PLAN.md`, jamais réparé à
  la volée sans test de régression, voir la règle permanente ci-dessus) ou
  bruit (navigateur/extension du client, réseau) → ignorer/muter dans Sentry ;
  (3) si un même type d'erreur revient sur PLUSIEURS sociétés, la prioriser
  (un défaut transverse touche tout le pilote, pas une seule société).
* **Limites du gratuit** — le tier Sentry gratuit plafonne le volume mensuel
  d'évènements et de replays ; l'échantillonnage bas (10 %) est calibré pour
  rester dedans avec un pilote à quelques sociétés. Un dépassement de quota
  fait taire Sentry silencieusement (jamais une panne applicative) — à
  surveiller dans le tableau de bord du projet, pas dans les tests.
## Fuzz API (Schemathesis) — QAH6

Job `api-fuzz` de `release-verify.yml` (palier 3, nightly + `workflow_dispatch`,
**non bloquant** — `continue-on-error: true`, ne garde jamais `main`). Recherche
L2 du 27/09/2026 (GROUPE QAH) : un agent LLM explore bien et juge mal — les
**oracles durs** portent le jugement. [Schemathesis](https://schemathesis.readthedocs.io/)
lit le schéma OpenAPI drf-spectacular déjà validé en CI (YAPIC6,
`GET /api/schema/`, voir `erp_agentique/urls.py`) et génère des requêtes
positives **et négatives** contre chaque opération documentée, avec `--checks
all` (5xx/`not_a_server_error`, conformité de réponse/`response_schema_
conformance`, données négatives/`negative_data_rejection`, en-têtes/
`response_headers_conformance`+`missing_required_header`, etc.) et les 4 phases
(`examples,coverage,fuzzing,stateful` — la phase `stateful` exploite les
`links` OpenAPI quand le schéma en déclare).

**Auth.** `/api/schema/` est derrière `IsAuthenticated`
(`SPECTACULAR_SETTINGS['SERVE_PERMISSIONS']`) : le job obtient un JWT
`demo_admin` (identifiants seedés en dur par `seed_demo` —
`demo_admin` / `Demo@2026!`, jamais un compte de prod) via
`POST /api/django/token/`, puis le passe en `-H "Authorization: Bearer …"` à
`schemathesis run` — Schemathesis l'applique À LA FOIS à la récupération du
schéma et à chaque requête de test (vérifié en local contre un faux schéma
protégé avant d'écrire ce job).

**Exclusions (destructif / envois externes réels)** — `--exclude-path-regex`,
documentées et vérifiées contre le code (jamais une supposition) :

| Surface exclue | Pourquoi |
|---|---|
| `adsengine/` | Moteur Meta Ads/Instagram de l'ERP : publication réelle, réponse/suppression/masquage de commentaires Instagram, connexions Meta — surface entière exclue (trop large/connectée à l'API Graph pour un tri fiable opération par opération). |
| `/contact/` | Formulaire de contact public → e-mail SendGrid (parqué par défaut — voir CLAUDE.md « Public contact form »). |
| `statuspage/public/(abonner\|confirmer\|desabonner)/` | Abonnement au statut public → e-mail de confirmation (`apps/statuspage/views.py::_envoyer_email_confirmation`). |
| `automation/approvals/<id>/approve/` | Approuver une approbation **relance réellement** l'action différée (`engine.run_approved`), qui peut envoyer e-mail/SMS/WhatsApp selon la règle configurée. `reject` et `simuler` (dry-run explicite) restent fuzzables. |

Sans clés API réelles dans l'environnement CI (`SENDGRID_API_KEY`, identifiants
Meta — voir CLAUDE.md « Key-gated features »), ces intégrations échouent déjà
gracieusement ; l'exclusion reste utile en défense en profondeur ET pour la
qualité du signal (un 5xx dû à une clé absente n'est pas un vrai bug d'API).
Cette liste est un point de départ documenté, pas un audit exhaustif — l'élargir
au fil des faux positifs constatés dans le rapport.

**Résultat.** Rapport JUnit + JSON uploadé en artefact (`schemathesis-report`,
14 jours). Chaque échec **reproductible** devient une tâche `ERR*` dans
`docs/ERROR_PLAN.md` — jamais un gate (règle du groupe QAH : « canonisation
d'oracle interdite », on ne rend jamais un test vert en l'alignant sur un bug).

**Recette locale (docker) :**
```bash
# 1. Monter la pile (db/redis/minio + Django + seed_demo) — même script que
#    la piste e2e ci-dessus :
bash scripts/e2e-local.sh up

# 2. Installer schemathesis (déjà dans requirements-dev.txt) :
cd backend/django_core && pip install -r requirements-dev.txt && cd ../..

# 3. Obtenir un JWT demo_admin :
ACCESS=$(curl -sf -X POST http://127.0.0.1:8000/api/django/token/ \
  -H "Content-Type: application/json" \
  -d '{"username": "demo_admin", "password": "Demo@2026!"}' \
  | python3 -c "import json,sys; print(json.load(sys.stdin)['access'])")

# 4. Lancer le fuzz (mêmes flags que le job nightly ; réduire --max-time pour
#    un aller-retour rapide en local) :
schemathesis run \
  --url http://127.0.0.1:8000 \
  -H "Authorization: Bearer ${ACCESS}" \
  --checks all \
  --phases examples,coverage,fuzzing,stateful \
  --mode all \
  --max-time 120 \
  --exclude-path-regex '(adsengine/|/contact/|statuspage/public/(abonner|confirmer|desabonner)/|automation/approvals/[0-9]+/approve/)' \
  http://127.0.0.1:8000/api/schema/

# 5. Arrêter :
bash scripts/e2e-local.sh stop
```

DEP : `schemathesis==4.28.0` (v4 — CLI restructurée vs v3, vérifiée contre
`schemathesis run --help` avant de choisir les flags ci-dessus) dans
`backend/django_core/requirements-dev.txt`, jamais dans l'image de production.
