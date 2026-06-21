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
`chromium`/`mobile`, donc il tourne toujours. Le smoke par-merge cible quelques
parcours (`--project=chromium devis.spec.js health.spec.js`) ; la matrice complète
(toutes les specs + mobile) part dans `release-verify`.

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

## Suites encore hors-CI (pistes)

* `backend/fastapi_ia/tests/` (sécurité SQL, scoping, OCR) — non câblées au CI
  Django ; candidates à un job `release-verify` dédié (dépendances FastAPI).
* Tests service-layer cross-app et garde-fous de règles (#3 Meta `PAUSED`,
  #4 `/proposal` seul chemin PDF devis) — à étoffer au palier 1/2.
