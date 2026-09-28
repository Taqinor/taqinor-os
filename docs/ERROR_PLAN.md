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
- [ ] ERR-QAH-CI-TESTS-JS-JAMAIS-EXECUTES — **13 fichiers de test frontend nommés `*.test.js` ne tournent NULLE PART, ni en local ni en CI** (constaté au fold de QAH3, 28/09/2026). `frontend/vitest.config.js` n'inclut par défaut que `src/**/*.test.jsx` et `scripts/ci_frontend_shard.py` ne répartit que `.test.jsx` ; le job `node:test` ne ramasse que `src/**/*.test.mjs`. Fichiers orphelins : 12 tests vitest (`features/adsengine/{adFullStory,cockpitViews,connectionWizard,dateRange,syncStatus,todayQueue}.test.js`, `features/installations/store/installationsSlice.test.js`, `features/onboarding/onboardingHelpers.test.js`, `features/queue/queueViews.test.js`, `lib/voice.test.js`, `router/moduleGating.test.js`, `ui/celebrate.test.js`) + 1 test `node:test` (`ui/datatable/data-label.guard.test.js`). Mieux : élargir l'include vitest ET le sharder à `*.test.{js,jsx}` (et le glob node:test si besoin), lancer ces 13 fichiers, corriger ceux qui ont pourri depuis — jamais les supprimer pour passer au vert — et poser une garde qui refuse tout fichier de test qu'aucun lanceur ne ramasse. Sévérité : moyenne (fausse couverture). Confiance : haute. Files: frontend/vitest.config.js, scripts/ci_frontend_shard.py, scripts/tests/test_ci_frontend_shard.py. (ROUTINE) (@lane: ci/frontend-tests) (@model:sonnet)
- [ ] ERR-QAH-TESTS-RACINE — **Le paquet racine `backend/django_core/tests/` n'est ramassé par AUCUN job CI : ses 8 anciens modules n'ont jamais tourné et ont dérivé** (trouvé en câblant QAH4, 28/09/2026). `scripts/ci_shard.py` ne découvre que `apps/*`, `authentication`, `core` (QAH4 y a opté SEUL `tests.test_tenant_sweep` via `TOP_LEVEL_MODULES`) et `release-verify` lance `apps authentication core`. Mesuré en local (tests sans base) : 7 échecs — `test_api_ordering_whitelist` + `test_api_surface_parity` (bases YAPIC2/YAPIC11 périmées : `crm.PlaybookViewSet`/`PlaybookEtapeViewSet`/`PlaybookTacheViewSet`, `stock.PortailTiersTokenViewSet`), `test_aud417_admin_scoping_transverse` (plancher « > 100 admins » et cibles paie/rh faux depuis le parcage SOLMVP ; ses vrais constats publicapi ont été corrigés par QAH4) ; `test_schema` (base requise, non exécuté) exige encore `/api/django/rh` et `/api/django/compta`, apps parquées. Mieux : remettre chaque module au vert sur le code RÉEL (jamais assouplir une garde de sécurité pour passer), puis l'ajouter à `ci_shard.TOP_LEVEL_MODULES`. Repro : `python manage.py test tests.test_api_ordering_whitelist tests.test_api_surface_parity tests.test_aud417_admin_scoping_transverse`. Sévérité : moyenne (gardes sécurité/qualité mortes en silence). Confiance : haute (7 échecs mesurés ; `test_schema` lu, pas exécuté). Files: backend/django_core/tests/test_api_ordering_whitelist.py, backend/django_core/tests/test_api_surface_parity.py, backend/django_core/tests/test_aud417_admin_scoping_transverse.py, backend/django_core/tests/test_schema.py, scripts/ci_shard.py. (ROUTINE) (@lane: backend/tests-racine) (@model:sonnet)

---

## GATED — needs founder decision before fixing (agent does NOT auto-build)

Move any task here with a `[BLOCKED: <reason>]` tag when fixing it would require a
destructive migration, a new external dependency, an auth/cost policy change, or a
conflict with a non-negotiable rule. (none yet)

---

## AUTOPILOT INTAKE LOG (the error-autopilot appends one line per run)

The daily error-autopilot (`.claude/skills/error-autopilot/SKILL.md`) appends
one dated line per run summarising how many NEW verified `ERR` items it filed
into the BUILD QUEUE above (a run that finds nothing verified appends nothing
and makes no commit). Fixing those items stays the job of `work on error plan`.

- *(intake log started 2026-06-21 — daily autopilot now files verified items here.)*
- 2026-09-28 — lot QAH (plan run, pas l'autopilot) : 4 constats vérifiés déposés (ERR-QAH-SOLAR-TOTALS-ROUNDING-ORDER, ERR-QAH-VENTES-FACTURE-HT-NON-ARRONDI, ERR-QAH-CI-TESTS-JS-JAMAIS-EXECUTES, ERR-QAH-TESTS-RACINE).

---


- [ ] ERR-NTCON35-LEVER-RESERVE — **Lever une réserve chantier est IMPOSSIBLE dans l'UI** : `btp_chantier.services.lever_reserve` exige une pièce jointe photo `phase='apres'`, mais l'écran `frontend/src/features/btp_chantier/ReservesChantier.jsx` n'offre AUCUN téléversement de photo (son commentaire l.141 le reconnaît : « Le serveur refuse sans photo ») — le bouton « Lever » ne peut jamais aboutir. Découvert par la lane NTCON35 (12/09/2026, drain NT). Correctif attendu : ajouter la capture/le téléversement de photo « après » au dialogue de levée (réutiliser CameraCapture/le pipeline photos chantier existant), + test e2e du parcours complet. Files: frontend/src/features/btp_chantier/ReservesChantier.jsx, backend/django_core/apps/btp_chantier/tests. (ROUTINE) «model: sonnet»

## DONE LOG (agent appends one plain-language line per fixed task)
