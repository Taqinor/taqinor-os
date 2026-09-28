# Taqinor OS — Error Plan & Bug Backlog

This file is the bug/error backlog **drained by the `work on error plan` command**
(defined in `CLAUDE.md`). That command is identical to `work on the plan` in every
respect — same `scripts/plan_lanes.py`-driven maximally-parallel cross-category lane
plan (run it on `docs/ERROR_PLAN.md`), same concurrent worktree subagents up to the
session ceiling continuously refilled (work-stealing), same dynamic-workflow-with-
review engine, same stop conditions, same per-task commit/tick/DONE-LOG, same
sync-safe single self-merge `dev` → `main` — **with exactly one difference: it
works through THIS file** instead of `docs/PLAN.md` / `docs/PLAN2.md`. There is no
`.running` lock (same as `work on the plan`). Tasks use `ERR*` ids so their states
feed the plan fingerprint and CODEMAP §10 exactly like the other plan files
(`scripts/codemap_fingerprint.py` → `PLAN_FILES`).

This file is the single source of truth + memory between sessions for known bugs.
Each run **verifies a task isn't already fixed before building it** (mark
`[x] (already present)` if it is), fixes it with tests on its lane's worktree
branch, ticks it `[x]`, adds a DONE LOG line, refreshes CODEMAP §10 + re-runs
`--write` in the same commit as the tick, and the run self-merges once at the end.

**Provenance.** Seeded 2026-06-20 from a read-only 11-lane audit of `main`
@ `98e9d23` (backend apps, FastAPI IA service, React frontend, and the apps/web
Astro site). `main` advanced to `24b0cb5` during the audit, so a handful of items
may already be fixed (notably the notifications-engine wiring) — the verify-step
catches those and ticks them `[x] (already present)`. Severities are the auditors'
ratings; the build run re-confirms each on the live tree.

---

## HOW TO RUN (read this every session)

Follow the `work on error plan` rules in `CLAUDE.md` (they mirror `docs/PLAN.md`'s
HOW TO RUN verbatim, only the drain file changes). One-line starter:

> Read `docs/ERROR_PLAN.md`. Work through EVERY unchecked `[ ]` ERR task: first
> run `python scripts/plan_lanes.py docs/ERROR_PLAN.md` to get the maximally-parallel
> cross-category wave plan, then build those lanes in parallel with concurrent worktree
> subagents (each in its own git worktree) up to the session ceiling (default 8, raised
> as high as the session can sustain via `--max-lanes`), continuously refilled
> (work-stealing), coupled fixes in sequence
> inside a lane (default: dynamic workflow with a separate adversarial review agent
> that must pass each change before it's merge-eligible; fall back to plain parallel
> worktree subagents — never a single serial one-task-at-a-time agent). For each
> task: verify it isn't already fixed, build the fix with tests, commit it to its
> worktree branch, tick it `[x]`, add a dated DONE LOG line, refresh CODEMAP §10 and
> re-run `python scripts/codemap_fingerprint.py --write` in the same commit, then
> continue to the next. Skip-and-note any blocker (`[BLOCKED: reason]` → GATED) and
> keep going. At the very end, fold every worktree branch into one `dev`, integrate
> the latest `origin/main` first (merge it in, never force-push), get the four
> required CI checks green over the whole batch (with MinIO) and self-merge `dev` →
> `main` exactly once (auto-deploys — no deploy command; no per-agent PR, no
> per-task merge). Report once, in plain language, including the lane plan. Finally
> print `PLAN_STATUS: EMPTY` if no `[ ]` task remains, else `PLAN_STATUS: MORE`.

---

## BUILD QUEUE (fix highest-severity first)

- [ ] ERR-QAH-SOLAR-TOTALS-ROUNDING-ORDER — **Le total TTC affiché pendant la composition d'un devis peut différer d'1 centime du total réellement facturé (PDF/BC/facture)** (trouvé par QAH3, 28/09/2026). `frontend/src/features/ventes/solar.js` `optionTotalsTTC` additionne les TTC déjà arrondis ligne à ligne puis applique la remise globale sur cette somme ; la chaîne canonique serveur (`apps/ventes/selectors.py` `_canonical_totaux`, celle que `domain/argent.py`, `utils/options.py option_totaux` et le PDF facturent) applique la remise sur le HT brut, taux par taux, avant la TVA. Mesuré sur le corpus figé de 200 devis (multi-taux 10/20 %, remises 0-12 %) : 36/200 divergent, toujours de ±0,01 MAD exactement. Repro : `backend/django_core/apps/ventes/tests/test_solar_differential.py` (`KNOWN_DIVERGENCES`, 36 ids figés ; `TotauxDifferentielTest`). Mieux : l'écran s'aligne sur la chaîne canonique (le chiffre facturé fait foi), puis un humain régénère `solar_corpus_expected.json` (`node frontend/scripts/solar_corpus.mjs`) et vide `KNOWN_DIVERGENCES` — le test exige l'ÉGALITÉ de l'ensemble, donc il rougit tant que la liste n'est pas réduite. Sévérité : moyenne (le vendeur voit un chiffre, le client en reçoit un autre d'un centime). Confiance : haute. Files: frontend/src/features/ventes/solar.js, backend/django_core/apps/ventes/tests/test_solar_differential.py, backend/django_core/apps/ventes/tests/fixtures/solar_corpus_expected.json. (ROUTINE) (@lane: frontend/ventes-solar) (@model:sonnet)
- [ ] ERR-QAH-VENTES-FACTURE-HT-NON-ARRONDI — **`Facture`/`Avoir`/`NoteDebit` : sans remise globale (le cas courant), `total_ht`/`total_tva` ne passent pas par le noyau canonique arrondi** (trouvé par QAH2, 28/09/2026). `TotauxDocumentMixin` (`apps/facturation/totaux.py`) retombe sur `sum(ligne.total_ht …)` — somme BRUTE jamais quantifiée au centime — et `tva_par_taux`/`total_tva` (via `tva_buckets`) calculent la TVA sur cette base brute, alors que `Devis` passe TOUJOURS par `selectors._canonical_totaux`. Repro minimale (épinglée, `apps/ventes/tests/test_invariants_money.py::test_facture_total_ht_arrondi_sans_remise_globale_ERR_QAH_VENTES_FACTURE_HT_NON_ARRONDI`, `expectedFailure`) : `LigneFacture(quantite=3.00, prix_unitaire=10.00, remise=33.33, taux_tva=20)` → `total_ht == 20.00100000` au lieu de `20.00` ; `LigneFacture(quantite=1.00, prix_unitaire=450.00, remise=91.19, taux_tva=10)` → TVA `3.96` (base brute) au lieu de `3.97` (noyau canonique). Mieux : faire passer le chemin « sans remise globale » par le même noyau que le devis, puis retirer le `expectedFailure` (qui rougira de lui-même — « unexpected success »). Sévérité : moyenne (centimes fantômes dans soldes/paiements/exports). Confiance : haute. Files: backend/django_core/apps/facturation/totaux.py, backend/django_core/apps/ventes/tests/test_invariants_money.py. (ROUTINE) (@lane: backend/facturation) (@model:sonnet)
- [ ] ERR-QAH-CRM-TESTS-MASQUES — **Les 61 tests de `apps/crm/tests.py` ne tournent plus NULLE PART depuis le 21/09/2026, et le nocturne `backend-full` plante dessus** (trouvé en validant CAD177, 28/09/2026). CALX106 (commit `4f0c0f22`) a créé le PAQUET `apps/crm/tests/` (`__init__.py` + `test_calx106_empreinte_osm.py`, `test_qjr414_webhooks_fail_closed.py`, `test_qjr415_repli_company_bruyant.py`) à côté du MODULE `apps/crm/tests.py` : en Python le paquet gagne, `tests.py` est inimportable. Par merge, `ci_shard` passe le label `apps.crm.tests` → c'est le paquet (3 fichiers) qui tourne, jamais les 61 tests du module ; la nuit, `manage.py test apps authentication core` découvre par dossier et lève `ImportError: 'tests' module incorrectly imported from …/apps/crm/tests. Expected …/apps/crm` (run 36377688263, job `backend-full`) — AUCUN test backend nocturne ne tourne. Seule app concernée (vérifié sur toutes les apps + core/authentication). Mieux : aplatir le paquet en fichiers `apps/crm/tests_calx106_empreinte_osm.py` etc. (convention des autres `tests_*.py` de crm) et supprimer `apps/crm/tests/` ; lancer `apps.crm.tests` (les 61 tests réveillés — ceux qui ont pourri depuis le 21/09 se CORRIGENT, jamais un skip) ; ajouter une garde qui refuse `tests/` + `tests.py` dans une même app. Puis relancer `release-verify` pour cocher CAD177. Sévérité : haute (couverture CRM perdue en silence + nocturne aveugle). Confiance : haute (erreur lue dans le journal, masquage vérifié). Files: backend/django_core/apps/crm/tests/, backend/django_core/apps/crm/tests.py, scripts/ci_shard.py. (ROUTINE) (@lane: backend/crm-tests) (@model:sonnet)
- [ ] ERR-QAH-MIGRATION-STOCK-0125-REJEU — **`stock.0125` plante tout `migrate` sur une base qui avait des produits AVANT elle** (trouvé en montant la stack QA locale, 28/09/2026) : `AttributeError: 'FicheTechnique' object has no attribute 'ond_bat_max_charge_kw'` — la migration importe le dictionnaire VIVANT `FICHES_TECHNIQUES` du seeder, qui porte des champs ajoutés plus tard (migration 0130). Concerne tout poste/machine de nuit/restauration dont la base est antérieure à 0125 ; la prod l'a déjà appliquée (20/08) et n'est PAS concernée. Correctif PRÊT et prouvé sur une vraie base (le `migrate` local passe 0125 puis 0130) : commit `8f653e49` de la PR #722, retiré du lot par `8e9627a7` — ÉDITER une migration déjà appliquée invalide le cache WOW8 de la CI (rejeu froid ~1 h sur chaque shard). À livrer SEUL, dans sa propre PR (un seul cycle froid, puis le push sur main ressauve le dump) : `git cherry-pick 8f653e49`. Mieux : filtrer `valeurs` sur `FicheTechnique._meta.get_fields()` de l'état historique (c'est ce que fait le commit). Sévérité : moyenne (bloque l'installation de la nuit QA sur une machine à base ancienne). Confiance : haute (reproduit). Files: backend/django_core/apps/stock/migrations/0125_pvfch_combler_fiches_manquantes.py. (ROUTINE) (@lane: backend/stock-migration) (@model:sonnet)
- [ ] ERR-QAH-CI-TESTS-JS-JAMAIS-EXECUTES — **13 fichiers de test frontend nommés `*.test.js` ne tournent NULLE PART, ni en local ni en CI** (constaté au fold de QAH3, 28/09/2026). `frontend/vitest.config.js` n'inclut par défaut que `src/**/*.test.jsx` et `scripts/ci_frontend_shard.py` ne répartit que `.test.jsx` ; le job `node:test` ne ramasse que `src/**/*.test.mjs`. Fichiers orphelins : 12 tests vitest (`features/adsengine/{adFullStory,cockpitViews,connectionWizard,dateRange,syncStatus,todayQueue}.test.js`, `features/installations/store/installationsSlice.test.js`, `features/onboarding/onboardingHelpers.test.js`, `features/queue/queueViews.test.js`, `lib/voice.test.js`, `router/moduleGating.test.js`, `ui/celebrate.test.js`) + 1 test `node:test` (`ui/datatable/data-label.guard.test.js`). Mieux : élargir l'include vitest ET le sharder à `*.test.{js,jsx}` (et le glob node:test si besoin), lancer ces 13 fichiers, corriger ceux qui ont pourri depuis — jamais les supprimer pour passer au vert — et poser une garde qui refuse tout fichier de test qu'aucun lanceur ne ramasse. Sévérité : moyenne (fausse couverture). Confiance : haute. Files: frontend/vitest.config.js, scripts/ci_frontend_shard.py, scripts/tests/test_ci_frontend_shard.py. (ROUTINE) (@lane: ci/frontend-tests) (@model:sonnet)
- [ ] ERR-QAH-TESTS-RACINE — **Le paquet racine `backend/django_core/tests/` n'est ramassé par AUCUN job CI : ses 8 anciens modules n'ont jamais tourné et ont dérivé** (trouvé en câblant QAH4, 28/09/2026). `scripts/ci_shard.py` ne découvre que `apps/*`, `authentication`, `core` (QAH4 y a opté SEUL `tests.test_tenant_sweep` via `TOP_LEVEL_MODULES`) et `release-verify` lance `apps authentication core`. Mesuré en local (tests sans base) : 7 échecs — `test_api_ordering_whitelist` + `test_api_surface_parity` (bases YAPIC2/YAPIC11 périmées : `crm.PlaybookViewSet`/`PlaybookEtapeViewSet`/`PlaybookTacheViewSet`, `stock.PortailTiersTokenViewSet`), `test_aud417_admin_scoping_transverse` (plancher « > 100 admins » et cibles paie/rh faux depuis le parcage SOLMVP ; ses vrais constats publicapi ont été corrigés par QAH4) ; `test_schema` (base requise, non exécuté) exige encore `/api/django/rh` et `/api/django/compta`, apps parquées. Mieux : remettre chaque module au vert sur le code RÉEL (jamais assouplir une garde de sécurité pour passer), puis l'ajouter à `ci_shard.TOP_LEVEL_MODULES`. Repro : `python manage.py test tests.test_api_ordering_whitelist tests.test_api_surface_parity tests.test_aud417_admin_scoping_transverse`. Sévérité : moyenne (gardes sécurité/qualité mortes en silence). Confiance : haute (7 échecs mesurés ; `test_schema` lu, pas exécuté). Files: backend/django_core/tests/test_api_ordering_whitelist.py, backend/django_core/tests/test_api_surface_parity.py, backend/django_core/tests/test_aud417_admin_scoping_transverse.py, backend/django_core/tests/test_schema.py, scripts/ci_shard.py. (ROUTINE) (@lane: backend/tests-racine) (@model:sonnet)

---

## GATED — needs founder decision before fixing (agent does NOT auto-build)

Move any task here with a `[BLOCKED: <reason>]` tag when fixing it would require a
destructive migration, a new external dependency, an auth/cost policy change, or a
conflict with a non-negotiable rule.

- [ ] ERR-QAH-MINIO-IMAGE-INTROUVABLE — [GATED: décision fondateur — changer l'image de stockage des pièces jointes en prod] **L'image MinIO de `docker-compose.yml` (`minio/minio:RELEASE.2025-01-20T14-49-07Z`, reprise telle quelle par la prod) ne se télécharge PLUS nulle part** (constaté le 28/09/2026 en montant le lot QAH, PR #722) : Docker Hub `minio/minio` → « pull access denied », `quay.io/minio/minio` → 401, `dl.min.io` → 410 sur toutes les archives. Les machines qui l'ont en cache (serveur de prod, poste de Reda) tournent ; mais toute machine NEUVE échoue au `docker compose up` — la seconde machine de nuit QA (commande « setup nightly QA », QAH11), un serveur réinstallé, un poste de développeur. Le `docker image prune -f` de `deploy-prod.ps1` ne touche que les images orphelines (sans danger aujourd'hui). Pont déjà posé pour la CI (image `.github/ci-image/Dockerfile`) : l'archive GELÉE `bitnamilegacy/minio:2025.1.20-debian-12-r0`, même commit serveur vérifié. À trancher : (a) basculer le compose sur cette archive Bitnami gelée (attention : autre utilisateur 1001, autre dossier de données `/bitnami/minio/data`, autres variables — migration du volume à prévoir) ; (b) construire MinIO depuis ses sources (AGPL) dans une image maison ; (c) passer à un autre stockage compatible S3. Recommandation : (b) ou (c) pour la durée, (a) seulement comme pont court. Sévérité : haute pour toute nouvelle machine, nulle pour la prod actuelle. Confiance : haute (trois registres testés le 28/09). Files: docker-compose.yml, docker-compose.prod.yml, .github/ci-image/Dockerfile. (DECISION) (@lane: infra/minio) (@model:opus)

---

## AUTOPILOT INTAKE LOG (the error-autopilot appends one line per run)

The daily error-autopilot (`.claude/skills/error-autopilot/SKILL.md`) appends
one dated line per run summarising how many NEW verified `ERR` items it filed
into the BUILD QUEUE above (a run that finds nothing verified appends nothing
and makes no commit). Fixing those items stays the job of `work on error plan`.

- *(intake log started 2026-06-21 — daily autopilot now files verified items here.)*
- 2026-09-28 — lot QAH (plan run, pas l'autopilot) : 7 constats vérifiés déposés (ERR-QAH-CRM-TESTS-MASQUES, ERR-QAH-MIGRATION-STOCK-0125-REJEU, ERR-QAH-SOLAR-TOTALS-ROUNDING-ORDER, ERR-QAH-VENTES-FACTURE-HT-NON-ARRONDI, ERR-QAH-CI-TESTS-JS-JAMAIS-EXECUTES, ERR-QAH-TESTS-RACINE ; ERR-QAH-MINIO-IMAGE-INTROUVABLE en GATED).

---


- [ ] ERR-NTCON35-LEVER-RESERVE — **Lever une réserve chantier est IMPOSSIBLE dans l'UI** : `btp_chantier.services.lever_reserve` exige une pièce jointe photo `phase='apres'`, mais l'écran `frontend/src/features/btp_chantier/ReservesChantier.jsx` n'offre AUCUN téléversement de photo (son commentaire l.141 le reconnaît : « Le serveur refuse sans photo ») — le bouton « Lever » ne peut jamais aboutir. Découvert par la lane NTCON35 (12/09/2026, drain NT). Correctif attendu : ajouter la capture/le téléversement de photo « après » au dialogue de levée (réutiliser CameraCapture/le pipeline photos chantier existant), + test e2e du parcours complet. Files: frontend/src/features/btp_chantier/ReservesChantier.jsx, backend/django_core/apps/btp_chantier/tests. (ROUTINE) «model: sonnet»

## DONE LOG (agent appends one plain-language line per fixed task)
