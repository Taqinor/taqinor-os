# CI et calepinage : qui lit quoi (lecture seule)

Dernier run complet CI sur main : 45077305806 (PR #1526, sha bfb859c9), tous jobs verts. Nocturne le plus récent : release-verify 45014638342 (22/11 10:53, échec).

| Job | Lit le calepinage ? | Preuve |
|---|---|---|
| backend-tests (shards 0-7) | OUI | 534 fichiers test sous `apps/calepinage/tests`, 47 sous `core/calepinage`; shards = découverte Django complète (`scripts/ci_shard.py`, `os.walk`) |
| frontend-vitest (shards 1-4) | OUI, en partie | 114 fichiers `*.test.*` sous `features/calepinage` ; 136 fichiers test (features + pages) mentionnent calepinage ou ToitureDesign. Lanes par `scripts/ci_frontend_shard.py` |
| e2e (shard 1, chromium) | OUI, 2 specs seulement | `calepinage-parcours.spec.js` et `calepinage-onglets.spec.js` (ci.yml ~l.2417). Shard 2 : aucun calepinage |
| e2e-shard PR, reste des specs | NON | playwright.config.js exclut `acceptation/` (testIgnore) |
| backend-lint, frontend-lint, stage-names, bandit, semgrep, backend-openapi, web-build | Non (statique, ou hors module) | pas de chemin calepinage |
| api-fuzz-pr (0-7) | NON | aucune mention calepinage dans `api-fuzz-full.yml` ni dans la liste PR |
| a11y, visuel, perf | NON en PR | aucune mention dans les configs ; `calepinage-a11y`, `calepinage-perf` ne tournent que la nuit (e2e-full) |

Specs e2e calepinage et où elles tournent :
- `calepinage-parcours`, `calepinage-onglets` : PR (shard 1) + nocturne e2e-full. Skips : 1 garde `test.skip` chacune (carte indisponible).
- `calepinage-a11y` (2 skips), `calepinage-mesures-ecran` (1 skip conditionnel), `calepinage-maquettes`, `calepinage-parite-crm`, `calepinage-studio`, `calepinage-perf` (1 skip), `calepinage-horizon-telephone`, `calepinage-atelier-telephone` : nocturne e2e-full uniquement (pas en PR).
- `calepinage_tactile` : nocturne uniquement ; 5 gardes skip (carte, navigateur WebKit, Chromium seulement).
- `e2e/acceptation/acal*.spec.js` (10 fichiers, ~5 600 lignes) : JAMAIS en CI ni nocturne. Ne tournent que via `scripts/acceptation.ps1` (E2E_ACCEPTATION=1, à la main). Zéro skip.

Nocturne 45014638342 (22/11), jobs en échec : e2e-full, backend-full, alert-on-repeated-failure. Touche le calepinage :
- e2e-full : `calepinage-perf` ACAL440 (2 tests, glissé 500 modules 10.8 s, mode bas de gamme 10.1 s) ; `calepinage-horizon-telephone` ACAL521 (« douze visées simulées », 8.9 s) ; monkey « calepinage (9 écrans) » : navigation interrompue vers /calepinage/reglages.
- backend-full : `test_calx389_budget_simulation` (4 échecs, dont « Aucun résultat de moteur enregistré » : RapportRefuse) ; `test_calx328_pages_documents` : rapport_etude 19 pages, attendu ≤ 14 (ACAL226).
Les jobs PR de la même période sont verts, donc ces rouges n'arrivent pas au merge.

Angles morts (aucun job PR ne les lit) :
- Specs nocturnes de perf, tactile et téléphone : pas de gate PR.
- Acceptation ACAL : jamais automatisée ; dépend d'un passage manuel.
- api-fuzz et a11y n'ont aucune route calepinage listée.
- Les 5 gardes de `calepinage_tactile` et les skips de perf/mesures peuvent passer « sautés » sans alerte.
- Non vérifié : si shard 2 du backend ou le reste des vitest couvrent exactement les 534 modules (la table de durées les répartit, je n'ai pas recompté chaque lane).
