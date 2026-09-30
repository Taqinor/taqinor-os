# Audit QA complet — COUV-HOR (30/09/2026)

Rapport intégral de l'audit (6 agents : inventaire CI, inventaire runtime, historique, prototype sur la prod, synthèse, critique).
Résumé et décisions : [README.md](README.md) §6. Prototype : [auditeur_coherence_prototype.py](auditeur_coherence_prototype.py).

## 1. Inventaire — QA au build (CI, gardes, tests)

The short answer is yes, this kind of error can be caught automatically, but nothing you have today is built to catch it. Repo root: C:\dev\taqinor-os, on branch fix/couverture-horaire-donut. I found five gaps.

**1. No check compares two figures on the same client document in general.** There are some hand-written tests for specific figure pairs, each added after an incident: two production figures (test_qjr115), the totals chain (test_qjr122), ROI star vs curve (test_qjr125), page vs PDF vs screen totals (test_pv86, test_err_qah_total_divergence_creation) and public consumption (test_conso_publique_source_unique). The donut next to "−37 %" had no such test.

**2. Nothing in build-time QA runs on real data.**
- Every fixture is consistent with itself. The golden snapshot data has conso 120000 and taux_couverture 10.4, which is exactly 12486/120000. The residential full case has no bills, so its economics block (donut included) isn't printed at all.
- The only tool designed for real data is `check_data_integrity`, and it checks cross-company links only. Nothing schedules it.
- `check_db_invariants.py` is written but not connected to any job.

**3. The PDF tier gives no signal today.**
- Every test that renders a real PDF is excluded from the PR gate and only runs in the nightly `release-verify`, which isn't required.
- That nightly failed in 39 of its last 40 runs. The latest one (run 36550090131) had 19 PDF-tier test failures, including all 5 golden snapshots, plus 67 failing browser tests and a failed API fuzz.
- `residentiel_full` never had a baseline image committed, so that case can only fail.
- The nightly visual-regression step runs with `--update-snapshots`, so it rewrites its baselines instead of comparing.

**4. The browser test ran the exact faulty path on every PR and couldn't see it.** The devis e2e test creates a lead with a 900 bill in Casablanca and no distributor, which is exactly the bills ÷ 1.20 case. It only checks that the PDF preview appears and that a .pdf downloads; it never reads the PDF's text.

**5. The existing checks compare declarations, not numbers.**
- The ~100 `check_*` guards and the 134 contract sample files are static comparisons of code and declarations: keys, types, enums, write sites, where constants come from. They prove `coverage_pct` exists and is a number; none compares its value to a sibling figure.
- The solar.js vs Python differential test explicitly leaves tariffs, real bills and savings out of scope. That's where the 1.20 MAD/kWh fallback lived.
- Some tests actually locked the bug in. The solar.js QF4 test asserted `kwhFromBill(120, 'inconnu') = 120 / FALLBACK_KWH_PRICE`. The autoQuote test replayed a copy of the code instead of the real block (PR #738 fixes that).
- The "estimated" flag that `kwhFromBill` returns was dropped before saving, and no check notices a lost label. The etude-params schema marks `conso_annuelle` as a plain screen input, with no record of where it came from and no link to `etude_horaire.annuel.consommation_kwh` as the same quantity.

**How to detect much more of this family**, roughly in order of value:
1. **A fast consistency test on the rendered document.** The per-PR tier can already render the real residential HTML without a database or WeasyPrint (`apps/ventes/tests/_moteur_fixtures.py`). A test there would pull every figure off the page and check the relationships between them: coverage = self-consumed ÷ the same consumption the bills imply, savings % consistent with bills before/after, consumption printed = the hourly engine's. It would generate inputs where the two sources deliberately disagree (Hypothesis).
2. **The same check run nightly against production, read-only**, over every draft and sent devis. It would build the quote data, the donut figures and the online proposal payload, and alert on disagreement. It would have flagged the 134 quotes the first night.
3. **Declare "same quantity" groups and a quality flag in the etude-params schema**, plus a guard that any value computed from an estimate keeps its "estimated" label when saved, and a guard over every use of the fallback price.
4. **Extend the JS/Python differential** to `kwhFromBill`, `consoAnnuelleDepuisFactures` and the savings functions, with distributor set to none, SRM and "autre".
5. **Make the devis e2e test read the PDF text** and assert coverage and savings agree.
6. **Get the nightly back to green, or move a few text-level PDF checks into the PR gate.** That means committing the `residentiel_full` baseline and making visual regression compare instead of update.

I stayed within the inventory and made no production queries.

### Merge gate: `changes` detector plus the 6 required aggregate checks

- **Où :** .github/workflows/ci.yml (jobs changes, ci-image-check, backend-lint, backend-tests, frontend-lint, e2e, ci-gate). Branch protection on main requires: e2e, backend-lint, backend-tests, frontend-lint, stage-names, web-build-test
- **Détecte :** Routes a PR to the heavy jobs by path (backend/, scripts/, frontend/, apps/web/, STAGES.py). Fails open to the full suite when the diff range can't be resolved. Each aggregate fails if any of its lanes failed or was cancelled; a skipped lane counts as success.
- **Quand :** Every pull_request, and on push to main/dev. Measured ~6-10 min on the cache-hit path.
- **Angle mort :** This only decides which suites run. It has no semantic checks of its own. A docs/CI-only diff runs only stage-names. The PDF tier (@tag pdf/slow) is never part of the merge gate.

### backend-lint-fast: 44 static host guards run in parallel (scripts/ci_guards.py backend-lint-fast)

- **Où :** scripts/ci_guards.py GARDES['backend-lint-fast'] and the scripts/check_*.py it calls. Allowlists in scripts/*_allow.txt
- **Détecte :** (1) Syntax and lint: compileall on 3.11, flake8, import-linter contracts, check_platform. (2) Data model, tenancy and money schema: check_on_delete (+--financial), check_company_fk, check_money_fields (+--decimal-places), check_money_monodevise, check_money_rounding (advisory), check_unique_scoping, check_tenant_isolation, check_viewset_model_scope, check_fk_scoping, check_action_permission_override, check_machine_etats_statut_readonly, check_naive_datetime. (3) Concurrency and write paths: check_read_modify_write, check_mouvement_stock_service, check_get_or_create, check_override_registry (etude_params and LigneDevis write sites outside sanctioned modules). (4) Ops: check_celery_tasks, check_commandes_planifiees, check_beat_active_companies, check_migration_safety. (5) Mirror parity: check_modes_marche (6 market-mode enumerations vs contracts/modes_marche.json). (6) Test hygiene: check_tests_source_regex (blocks new regex-on-source tests). Also check_ao_api_contract. Most guards have their own unittest.
- **Quand :** Every PR with backend==true (which includes scripts/). ~1.5-2 min, no Docker image needed.
- **Angle mort :** All of these are pure AST/regex reads of code against code: keys, types, enums, write sites, FK options. None evaluates a computed value, reads a rendered document or looks at data. check_override_registry would flag a scattered etude_params write, but not a sanctioned writer (autoQuote/etude_schema) persisting a number that was computed from a fallback. Nothing links etude_params['conso_annuelle'] to etude_horaire.annuel.consommation_kwh as the same quantity.

### stage-names: about 60 host guards and self-tests (scripts/ci_guards.py stage-names), ungated

- **Où :** scripts/ci_guards.py GARDES['stage-names'] and the scripts/check_*.py it calls
- **Détecte :** (A) Front<->back contract and shape drift: check_api_contract (frontend calls a route that doesn't exist); check_api_shapes (frontend/apps-web mocks and screen reads vs the key->nature map derived from server code, per endpoint, including apps/web samples); check_openapi_shapes; check_lead_webhook_parite (tunnel keys vs crm/webhooks.py via committed contract); check_contrats_calepinage_deux_moities. (B) Hand-copied vocabulary mirrors: check_stages, check_modules, check_roles_mirror (4 role mirrors incl. solar.js PRODUCT_CATEGORIES), check_choices_declares (opt-in `// source-choix:` markers). (C) Provenance of constants: check_seuils_electriques, check_calepinage_provenance_constantes (numeric literals must cite a source). (D) Reachability and dead code: check_ecrans_atteignables (+parametres), check_services_appeles, check_calepinage_actions_consommees, check_documents_calepinage (declared doc has a renderer), check_onglets_calepinage_testes, check_frontiere_calepinage, check_parked_apps, check_taches_cablage, check_plan_taches_mixtes, check_build_order, codemap_fingerprint --check. (E) Test and CI hygiene: check_test_tags, check_test_determinism, check_test_tenant_distinctness, check_test_package_shadow, check_frontend_test_runner_coverage, check_invariants, check_query_budgets, and self-tests of ci_shard, ci_frontend_shard, the changes filter, the testdb manifest and nightly_alert_gate. (F) check_frontend_errors (raw JSON/jargon shown to users), check_safe_migrations, check_odoo_writes.
- **Quand :** Every push and PR, with no path gate. Required check.
- **Angle mort :** Same pattern as backend-lint-fast: declarations are compared, values never are. check_api_shapes and the contract samples prove a key exists with the right type (e.g. coverage_pct is a number); they never compare its value with a sibling key. Class (d) mirrors are only caught where someone hand-listed the pair (roles, modes, stages, webhook keys). There is no generic 'this JS function claims to mirror that Python function' registry. The constant-provenance guards cover calepinage/electrique only. solar.js FALLBACK_KWH_PRICE and pricing._FALLBACK_KWH_PRICE are not policed.

### Unwired or unscheduled guards

- **Où :** scripts/check_db_invariants.py; backend/django_core/authentication/management/commands/check_data_integrity.py
- **Détecte :** check_db_invariants: an advisory register of money/quantity invariants that live only in clean()/save() without a DB CheckConstraint. Its --check mode is written but its own docstring says it is 'not wired into any CI job yet'. check_data_integrity: a read-only generic auditor of cross-company FK leaks, meant for prod or cron.
- **Quand :** Never. Grep finds no reference in any workflow, ci_guards.py, preflight or beat.
- **Angle mort :** This is the only tool designed to run on REAL data (check_data_integrity), and it only covers tenant-FK leaks, not figure consistency. Neither tool is executed.

### backend-openapi

- **Où :** .github/workflows/ci.yml job backend-openapi; scripts/check_openapi_schema.py
- **Détecte :** Missing migrations (makemigrations --check). A generated OpenAPI schema that is valid and adds no new drf-spectacular warnings.
- **Quand :** Every PR with backend==true, inside the prebuilt ci-backend image. Part of the required backend-lint check.
- **Angle mort :** Schema-level only. The public proposal_data is a hand-built dict with no serializer, so it isn't described there at all.

### backend-tests-shard: Django fast tier, 8 duration-balanced shards

- **Où :** .github/workflows/ci.yml backend-tests-shard; scripts/ci_shard.py (+ci_shard_timings.json); .github/actions/backend-env (cached test_erp_db); backend/django_core/{apps/*/tests,core/tests,authentication,tests}: about 2,680 test*.py files; testkit/ factories; RLS suite on lane 0
- **Détecte :** Unit and integration tests with `--exclude-tag=pdf --exclude-tag=slow --parallel 4 --keepdb`. For the quote engine this includes HTML-level tests that render the real residential HTML without DB or WeasyPrint (apps/ventes/tests/_moteur_fixtures.py -> residential_render.build_html), and some per-incident single-source tests: test_qjr115_production_unique (two annual productions on the Étude page), test_qjr122_totaux_additifs (totals chain adds to the centime), test_qjr125_graphe_roi_coherent (ROI star vs curve), test_qjr410_chiffres_document, test_pv86_verite_unique_devis and test_err_qah_total_divergence_creation (page vs PDF vs screen totals), test_conso_publique_source_unique (public monthly consumption vs hourly engine), test_moteur_zero_invention and test_calx286_non_invention (no invented number), test_qjr156_tarif_estime (an estimated tariff is labelled), test_qjr157_facture_actuelle, test_etude_horaire (engine physics and tariff inversion), test_proposal_data_shape (key->nature vs contract), and a Hypothesis state machine on the Devis->BC->Facture chain (test_invariants_documents, @tag slow, so nightly only).
- **Quand :** Every PR with backend==true. Required 'backend-tests'.
- **Angle mort :** Cross-figure consistency exists only as hand-written tests for a few specific figure pairs, each added after an incident. There is no generic rule that every figure on a document derived from the same quantity (conso, production, coverage, savings %, bill before/after) must agree. The donut/−37 % pair had no such test until PR #738. Fixtures are internally consistent by construction: they never feed conso_annuelle that disagrees with etude_horaire.annuel.consommation_kwh, so a second source could never diverge. Tests also PINNED the fallback behaviour: test_qjr156 asserted _FALLBACK_KWH_PRICE with estime=True, but nothing checked that the 'estimated' flag survives into the persisted etude_params. No test uses real or production-shaped data.

### Quote-engine PDF tier and golden snapshots (@tag pdf/slow)

- **Où :** apps/ventes/tests/test_quote_engine_snapshot.py (5 cases: residentiel_full 3p, industriel_full_etude 4p, residentiel_onepage 1p, agricole_pompage_full 4p, agricole_pompage_onepage 1p); baselines in apps/ventes/tests/baselines/*.png; manage.py update_pdf_baselines. The pdf tag appears 75 times across 43 test files (test_quote_engine_residential/formats/documents/builder/deux_optimiseurs, calepinage calx29x-32x, stock, core). scripts/check_test_tags.py forces any test importing weasyprint/matplotlib/boto3 to carry a tag.
- **Détecte :** Real WeasyPrint render, rasterised with PyMuPDF. Checks exact page count, a pixel diff ≤2% against a committed PNG, that the totals literals (Sous-total HT/Total HT/TVA/Total TTC) are present, and that no prix_achat marker leaks.
- **Quand :** Never per-PR (excluded by the tags). Only nightly in release-verify backend-full, which is not required.
- **Angle mort :** This tier gives no usable signal today. In the latest nightly (run 36550090131) backend-full had 19 FAILs, all in the PDF tier, including all 5 golden snapshots, test_qj30 (4 pages != 3) and a prix_achat test. residentiel_full_p*.png was never committed, so that case can only fail. Fixture data is self-consistent (ETUDE_PARAMS conso 120000 / taux_couverture 10.4 = 12486/120000). The residential case has only distributeur='onee' and no bills, so under rule Z2 the economics block, including the donut, is omitted and can't be checked. The text assertions are totals-label presence only, with no numeric cross-checks. A 2% pixel threshold would not notice '28 %' vs '37 %' in a donut label.

### JS/Python mirror (differential) tests

- **Où :** backend: apps/ventes/tests/test_solar_differential.py, test_classification_parity.py, test_tariff_drift_lock.py (pricing.py vs parametres/tariff.py), test_dc9_ghi_parity.py; frozen corpus apps/ventes/tests/fixtures/solar_corpus.json + solar_corpus_expected.json generated by frontend/scripts/solar_corpus.mjs; frontend/src/features/ventes/solar.corpus.test.jsx (vitest); apps/web billInversionParite.test.ts, tunnelParite, leadBandParite
- **Détecte :** On about 200 seeded entries: line classification predicates, kWc derived from lines, productible per city, production derate, and option TTC totals to the centime (with one frozen known divergence of ±0.01). Also tariff-grid drift between the two Python implementations. The vitest side recomputes the corpus with solar.js and fails if solar.js changes without the expected file being regenerated.
- **Quand :** Per PR (backend fast tier + vitest lanes).
- **Angle mort :** The corpus header says outright that tariffs by tranche, real bills and savings/ROI are OUT OF SCOPE. kwhFromBill, consoAnnuelleDepuisFactures, the no-distributor path, twoBillsSavings and coverage are exactly where the 1.20 MAD/kWh drift lived, and none of them is compared. Corpus inputs are frozen and never include distributeur=None/srm/autre. Mirror pairs are enumerated by hand. frontend/src/features/ventes/solar.test.mjs (QF4) asserted `kwhFromBill(120,'inconnu') = 120/FALLBACK_KWH_PRICE`, which pinned the bug. autoQuote.facturesReelles.test.mjs replayed a copy of the autoQuote block instead of the real code (fixed in PR #738).

### frontend-static (part of required frontend-lint)

- **Où :** .github/workflows/ci.yml frontend-static; frontend/package.json (lint = eslint + scripts/check_no_danger.mjs, check-hex, check-bundle-budget); node --test "src/**/*.test.mjs" (330 files)
- **Détecte :** ESLint and dangerouslySetInnerHTML use, pure-logic node:test suites (solar.js, autoQuote, sizingReducer...), hex colours outside design tokens, a production vite build, and the bundle size budget.
- **Quand :** Every PR with frontend==true.
- **Angle mort :** Pure-function tests with hand-picked inputs. Nothing compares screen figures with the PDF or proposal for the same devis. The estimation flag returned by kwhFromBill was dropped by autoQuote and no test asserted it was carried.

### frontend-vitest-shard: component, UX and a11y tests (4 lanes)

- **Où :** .github/workflows/ci.yml frontend-vitest-shard; frontend/vitest.config.js (jsdom, RTL, axe); scripts/ci_frontend_shard.py; 709 *.test.jsx/*.test.js files
- **Détecte :** Screen rendering and behaviour with mocked API responses (mocks policed by check_api_shapes), and accessibility.
- **Quand :** Every PR with frontend==true.
- **Angle mort :** The data is mocked, so it can only prove that the screen shows what the mock says. It can't see a server-side number that disagrees with another server-side number.

### web-build-test (required): apps/web public site and online proposal

- **Où :** .github/workflows/ci.yml web-build-test; apps/web: tsc check + check-astro-types, astro build, vitest (265 test files incl. proposition*.test.ts, propositionDevisFideleP18, contractSamplesParite.test.ts)
- **Détecte :** Types, build, the pure libs behind the proposal page (couvertureSolaire, syntheseEconomies...), JSON equality of apps/web/src/contract_samples with the backend twins, and source-regex locks that the page reads served values rather than recomputing them.
- **Quand :** PRs touching apps/web/. The nightly web-full adds Lighthouse (non-blocking).
- **Angle mort :** The Astro proposal page itself is not rendered in CI (per the test's own header). The web page faithfully displays whatever the backend serves, so a wrong served coverage_pct passes. Screen vs PDF vs web is only checked for the shape of the samples.

### e2e-shard (required 'e2e'): Playwright smoke on seeded demo data

- **Où :** .github/workflows/ci.yml e2e-shard (2 lanes, chromium, seed_demo + seed_catalogue, gunicorn); frontend/e2e/*.spec.js (53 specs), playwright.config.js, e2e/helpers.js
- **Détecte :** Lane 1 runs fumee-ecrans-1/2/3 (visits every route declared in module.config) and the calepinage parcours/onglets. Lane 2 runs devis.spec.js (E4: create lead → Devis automatique → PDF preview on canvas → download is a .pdf → lead badge count), health and mobile (chromium + mobile-safari).
- **Quand :** Every PR where backend or frontend changed.
- **Angle mort :** E4 ran the exact faulty path on every PR: createLead(facture=900, ville=Casablanca) sets no distributor, so conso = bills ÷ 1.20. It only asserts that a canvas is visible and a file downloads. It never reads the PDF text or compares the donut, the savings % or the bills. Only demo seed data is used, never real or anonymised data.

### release-verify nightly (palier 3)

- **Où :** .github/workflows/release-verify.yml: backend-full (all tests incl pdf/slow + coverage), frontend-full, e2e-full (full matrix desktop+mobile+monkey), visual (@visual --update-snapshots), web-full + Lighthouse, fastapi-tests, api-fuzz (Schemathesis --checks all, stateful), alert-on-repeated-failure (scripts/nightly_alert_gate.py opens a `nightly-alert` issue after 2 red nights)
- **Détecte :** Everything the PR gate excludes: the PDF tier, golden snapshots, the full e2e matrix, API fuzzing for 5xx and schema non-conformance.
- **Quand :** 03:00 UTC daily plus workflow_dispatch. Not required and doesn't gate main.
- **Angle mort :** It has been red long enough to carry no signal: 39 of the last 40 runs failed. Latest run 36550090131: backend-full 19 test failures (PDF tier), e2e-full 67 failed / 108 passed, api-fuzz failed. The @visual step runs with --update-snapshots, so it rewrites baselines and never compares. Schemathesis checks conformance and status codes, not values. Even when green, the data is seed_demo.

### Contract samples (PACT10) and invariant registry

- **Où :** backend/django_core/apps/*/contract_samples (134 JSON: calepinage 48, crm 33, ventes 25 incl. proposal_data.json, etude_horaire.json, couverture_batterie.json, ventes_economie.json; portail 11, …) + apps/ventes/contracts/modes_marche.json; docs/invariants.md + scripts/check_invariants.py (~21 test references)
- **Détecte :** Samples: key→nature maps consumed by check_api_shapes, test_proposal_data_shape (two share levels) and contractSamplesParite.test.ts, so that two lanes can't invent two contracts. Invariants: money chain to the centime, reference numbering, status guards, no prix_achat in 5 documents, tenant FK. check_invariants only verifies that the referenced tests still exist.
- **Quand :** Per PR (stage-names and the backend fast tier).
- **Angle mort :** Contracts are shape-only and never assert value relations between keys. The invariant registry has no energy or solar invariant (e.g. 'coverage shown = autoconsumed ÷ the same consumption the bills were inverted from'), and check_invariants doesn't run the tests.

### Mutation testing (mutation.yml)

- **Où :** .github/workflows/mutation.yml; backend/django_core/setup.cfg [mutmut] paths_to_mutate: quote_engine/builder.py, ventes/domain/argent.py, facturation/totaux.py, utils/references.py, roles/models.py, core/mixins.py, core/permissions.py
- **Détecte :** Weak assertions (surviving mutants) in high-risk money and builder modules. A per-module score goes to the job summary.
- **Quand :** Nightly 03:30 UTC. `|| true`, informational, always green. QAH5 notes it had never mutated anything before the config fix.
- **Angle mort :** Gates nothing. pricing.py, residential/renderer.py (synthese_economies), public_views.py, solar.js and autoQuote.js are not targets. Mutants are judged against fixture tests that are self-consistent, so a sibling-figure drift survives.

### Load tests

- **Où :** .github/workflows/load-smoke.yml (Locust load/locustfile.py, seed_scale 5000 leads/500 devis, p95 gate 1000 ms); .github/workflows/loadtest.yml (k6 loadtests/browse.js, `|| true`); loadtests/create-devis.js and spike.js are not scheduled
- **Détecte :** Latency regressions (p95) on read paths.
- **Quand :** load-smoke weekly Monday 05:00 UTC (last 3 runs failed). k6 nightly 04:00 UTC (always green because of `|| true`).
- **Angle mort :** Irrelevant to correctness, and uses synthetic data.

### Security and dependency scans

- **Où :** .github/workflows/security-sast.yml (bandit vs .bandit.baseline), semgrep.yml (p/django + .semgrep/), dependency-audit.yml (pip-audit + npm audit, opens issue)
- **Détecte :** Security anti-patterns and CVEs.
- **Quand :** bandit and semgrep on push to main (both `|| true`, non-blocking). Audit weekly on Monday.
- **Angle mort :** Out of scope for the bug family. Custom semgrep rules could host a value-provenance rule but currently don't.

### Local mirrors and the nightly QA explorer (not GitHub CI)

- **Où :** scripts/preflight.ps1 (+scripts/ci_fast_gate_steps.py expands the same GARDES list); scripts/test-backend.ps1 (docker --keepdb harness, -Snapshot/-RestoreDb); scripts/nightly-qa.ps1 + .claude/skills/qa-explorer + docs/qa-explorer.config.yml
- **Détecte :** Preflight runs the same static guards before a push. The QA explorer (23:00 local) has one Sonnet agent per module browsing http://localhost with hard oracles: 4xx/5xx, console errors, a failing /proposal PDF, visible prix_achat, cross-tenant data, empty list after a create. A judged grid covers totals to the centime and the state chain.
- **Quand :** Preflight before a push on the cold-cache path. QA explorer nightly on the founder's machine.
- **Angle mort :** Localhost only, on seed_demo, never production (hard-coded refusal). The oracles don't include 'two numbers on one document must agree'. It judges totals, not solar figures. It found ERR-QAH-VENTES-TOTAL-DIVERGENCE-CREATION (the same class of bug, for totals) only because a totals oracle existed.

## 2. Inventaire — détection en production / processus QA

Everything you have set up catches errors that crash or show as an error: 5xx, console errors, schema breaks, crashes, a failed PDF, totals that don't add up to the centime, data from another company. The DEV-202609-0113 bug raised no error at all, so nothing could catch it. No job ever looks at production quotes. And the local nightly QA cannot even reach the fallback-price path, because seed_demo.py has 5 quotes with no étude and one lead with no bills and no distributor.

What I checked read-only on production today:
- **Sentry is off.** Both DSNs are empty, and the sentry_sdk package is missing from the running django_core container even though requirements.txt:153 pins it.
- **The only production data sweep is ignored.** `reporting.controle_integrite` has sent the same "3 anomalies" message to 7 people every Monday since 10/08: 75 notifications, 3 read. It only checks workflow orphans, never figures inside a quote.
- **Scheduling.** No error-autopilot scheduled on this PC (no Windows task, no Claude desktop task), and no cloud routines on your account. The 29/09 run was manual. The other PC could have a desktop task I can't see.
- **Last QA pass.** The 29/09 night pass (about $46) never mentions coverage, étude or savings.
- **The JS/Python mirror test** (`test_solar_differential.py`) explicitly leaves the tariff, conso, coverage and savings maths out of scope. That is exactly where this bug lived.

**Yes, this can be caught automatically.** A simple rule on production data — stored `conso_annuelle` within 5 % of `etude_horaire.annuel.consommation_kwh` — would have fired on the very first bad quote, DEV-202608-0018 on 21/08 (a draft, off by ×1.505). That is before almost any were sent: non-draft divergent quotes per week went 1, 1, 4, 14, 19, 7 (W35–W40). The rule flags 127 of 135 quotes with an hourly étude, so the stored conso almost never matches the hourly engine. It needs tuning before it becomes an alert (for example, is a hand-entered C&I conso allowed to differ?).

What I'd add, most useful first:
1. **A nightly read-only coherence check on production quotes.** Add it as a new check group in `apps/reporting/integrity.py`, run every night. It rebuilds each quote's PDF data (`build_quote_data`, confirm first that it writes nothing) and the online-proposal data (`proposal_data`), then asserts rules such as:
   - (a) donut coverage equals the hourly engine's coverage, and it is consistent with the "−X % sur votre facture" figure;
   - the printed current bill matches the lead's bills;
   - `conso_annuelle` matches the hourly conso;
   - (c) the PDF data equals the proposal data equals what the screen saved.
   It should alert only on NEW anomalies, by e-mail or WhatsApp to you or a GitHub issue like `nightly-alert`, not the in-app digest nobody reads.
2. **The same checks as a gate before a quote goes out** (send, create share link). A bad quote gets blocked or flagged before the client sees it.
3. **Flag estimated values when they are saved (b).** `etude_schema` stores `conso_annuelle` as a plain screen input with no marker that it came from an estimate. solar.js already computes `estimation: true` but it is never saved. Save the marker, and have the check flag any printed figure that came from an estimate without an "(estimation)" label.
4. **Make silent fallbacks visible.** Arm Sentry, then send a warning whenever FALLBACK_KWH_PRICE feeds a saved value, plus soft (non-crashing) consistency checks inside the PDF builder. That way fallbacks show up as countable events instead of staying silent.
5. **Upgrade the nightly QA explorer:**
   - add a fixed check that compares figures within the same document (PDF text is already extracted with PyMuPDF for the prix_achat check);
   - compare screen, /proposal PDF and online-proposal values;
   - add the public proposal page to a mission;
   - extend seed_demo (QAH12 is already pending) with leads that have energy profiles covering each branch: no distributor, SRM, "autre", summer≠winter;
   - add a mission step "quote from a lead with bills and no distributor".
6. **Extend the JS/Python mirror test (d)** to bill→kWh conversion, coverage and savings. Add a nightly production check that recomputes on the server the values solar.js saved at creation.
7. **Give the error-autopilot a real schedule,** plus a scan for "same quantity computed in two places" and "fallback result saved".

Scratch probe scripts (read-only, run inside transaction.atomic with set_rollback(True)) are in C:\Users\kasri\AppData\Local\Temp\claude\C--dev\86026cd6-52e4-4480-9adc-4c9517346d88\scratchpad\ (qa_runtime_probe.py, qa_notif_probe.py, qa_latency_probe.py).

### Error-autopilot (ERR / WEBERR intake)

- **Où :** C:\dev\taqinor-os\.claude\skills\error-autopilot\SKILL.md, C:\dev\taqinor-os\docs\error-autopilot.md, C:\dev\taqinor-os\docs\error-autopilot.config.yml (kill switch enabled: true). Findings go to docs/ERROR_PLAN.md and docs/WEB_ERROR_PLAN.md (AUTOPILOT INTAKE LOG). Last run: commit 7965f81b, PR #734.
- **Détecte :** An LLM sweep of the CODE, not the data. Scout agents fan out over 14 surfaces: tests, flake8/ruff/eslint/tsc/mypy, bandit/semgrep, pip-audit/npm audit, concurrency, missing migrations, multi-tenancy, the CLAUDE.md rules, N+1, swallowed errors, frontend runtime, web, deploy hardening. It only files an item after reproducing it red and proving a fix green in a worktree. The 29/09 run filed ERR115–ERR124 (tenant, mass-assignment, red nightlies, CVEs, static and integrity checks).
- **Quand :** The docs say daily at 12:00 (desktop task or cloud Routine). What I found: this machine has no Windows task for it (only 'TAQINOR nightly QA' and 'TaqinorDevClean' are registered), Claude Desktop has no scheduled tasks, and RemoteTrigger lists no cloud routines on the account. Git has autopilot commits only on 2026-06-16..21 and 2026-09-28/29, and the intake log calls the 29/09 run 'run manuel'. So it currently runs only when started by hand. The other PC might have a desktop task I cannot see.
- **Angle mort :** It never looks at production data or rendered documents. Its reproduce-first gate needs a failing test someone thought to write, and the bug family needs a hypothesis like 'the donut and the savings figure use different sources', which no surface asks for. 'logic_invariants' only checks the CLAUDE.md rules (stages, statuses, /proposal, prix_achat, pompage), and none says one quantity must have one source. A fallback value saved as an input (conso = bills ÷ 1.20) is valid code with valid types, so nothing goes red. Because it is not scheduled, it did not run once between 21/06 and 28/09, which covers the whole 2026-08-20→09-29 bug window.

### QA-explorer nightly fleet (QAH1 + QAH11)

- **Où :** C:\dev\taqinor-os\.claude\skills\qa-explorer\SKILL.md, docs/qa-explorer.md, docs/qa-explorer.config.yml, scripts/nightly-qa.ps1, scripts/setup-nightly-qa.ps1, docs/nightly-qa.md, .mcp.json (Playwright MCP + Chrome DevTools MCP). Logs in C:\dev\taqinor-os\logs\nightly-qa\. Output lands as ERR-QAH-* in ERROR_PLAN (dev-qa-20260929 → PR #735).
- **Détecte :** One sonnet 'human tester' per module (10 modules) drives the LOCAL demo ERP. Nine fixed checks (not LLM judgment) decide what counts as a bug: 5xx; 4xx with no field message; console.error, pageerror or unhandled rejection; native alert/confirm dialogs; an empty list right after a create; a /proposal PDF with status≠200, not application/pdf, not %PDF-, or <10 kB; prix_achat labels in client output (text extracted with PyMuPDF); a broken or stuck screen; data from the other tenant. It also applies a per-module checklist: the ventes one checks Sous-total→Remise→HT→TVA→TTC to the centime on form, list, BC and facture, the status chain, and unique references. Each finding is replayed in a separate Chrome before filing. Real catches: 16 findings on 28/09, 3 on 29/09 (for example ERR-QAH-VENTES-TOTAL-DIVERGENCE-CREATION and FORM-TOTAL-CEIL, both totals mismatches).
- **Quand :** Windows task 'TAQINOR nightly QA', daily at 23:00 local. Its last run was 29/09 at 02:53 with result 0: 1h31 of Claude time, estimated cost total_cost_usd≈$45.9, filed 3, dropped 5. It targets http://localhost only and refuses production by design. QAH10 (a cloud version that runs without a PC) is still GATED.
- **Angle mort :** This is the biggest gap for this bug family. (1) The demo world cannot reach the bug. seed_demo.py creates 5 quotes with no étude and a bare lead with no bills and no distributor, so there are zero quotes with an hourly étude and the no-distributor fallback path is never exercised. The 29/09 report never mentions couverture, étude or économie. (2) There is no check that compares two figures on the same document. Check 6 only looks at PDF bytes, and check 7 already extracts the PDF text but only searches it for prix_achat. The ventes checklist covers the money chain and ignores the energy/étude block (coverage, −X % facture, current bill, production). (3) The public online proposal (proposal/<token>/data, taqinor.ma/proposition/<token>) is in no mission and is not on the token-page list of check 7, so screen, PDF and proposal are never compared. (4) The LLM may only judge against its checklist, and 'does 28 % next to −37 % make sense' is not a checklist line.

### QAH3 JS↔Python differential test (solar.js vs builder/pricing)

- **Où :** C:\dev\taqinor-os\backend\django_core\apps\ventes\tests\test_solar_differential.py, frontend/scripts/solar_corpus.mjs, frontend/src/features/ventes/solar.corpus.test.js, fixtures solar_corpus.json / solar_corpus_expected.json
- **Détecte :** Mirror drift on a frozen corpus of 200 quotes. It compares line classification (réseau/hybride/batterie/panneau), kWc derived from lines, productible per city, production = kWc×productible×derate, and TTC totals to the centime. It found ERR-QAH-SOLAR-TOTALS-ROUNDING-ORDER (1 centime, 36/200). KNOWN_DIVERGENCES can only shrink.
- **Quand :** Every CI run that touches the paths (vitest plus the backend shard). Deterministic.
- **Angle mort :** Its own header puts the rest of calculate_savings_roi out of scope: per-tranche tariffs, the hourly battery shift, and by extension the bill→kWh conversion, coverage and savings. That is exactly the mirror pair PR #738 had to fix (solar.resolveTranches / FALLBACK_KWH_PRICE vs pricing._table_tarifaire / _FALLBACK_KWH_PRICE). The corpus is synthetic inputs, so the 'lead with bills and no distributor' branch is not a corpus dimension. It compares the two mirrors with each other, never with the stored etude_params or the rendered PDF.

### release-verify nightly (full suite, e2e-full, gremlins monkey, Schemathesis api-fuzz, visual) + alert-on-repeated-failure

- **Où :** C:\dev\taqinor-os\.github\workflows\release-verify.yml, scripts/nightly_alert_gate.py, frontend/e2e/monkey.spec.js (QAH7), frontend/e2e/visual.spec.js, per-merge smoke frontend/e2e/devis.spec.js
- **Détecte :** The full Django suite including the pdf/slow tags, the full Playwright matrix on desktop and mobile, gremlins random clicking (pageerror, console.error, ≥500), Schemathesis fuzzing (5xx, response vs schema, negative data), and the web build with Lighthouse. Since CAD177 it opens or updates a 'nightly-alert' GitHub issue and fails loudly after 2 red nights in a row; that was added after 12 silent red nights, 12/09→27/09.
- **Quand :** Cron 03:00 UTC nightly, plus manual dispatch. It is not a merge gate.
- **Angle mort :** Everything here detects crashes or schema errors, and a wrong figure crashes nothing. The e2e devis spec only asserts that the downloaded filename ends in .pdf. Visual regression is non-blocking and its baselines are not committed (TESTING.md 'Pistes restantes'). All of it runs on seed_demo, which has no étude data. It never looks at production.

### Golden PDF snapshots + invariant registry (docs/invariants.md, check_invariants.py) + check_db_invariants.py

- **Où :** backend/django_core/apps/ventes/tests/test_quote_engine_snapshot.py (+ baselines/), C:\dev\taqinor-os\docs\invariants.md, scripts/check_invariants.py (wired into ci_guards stage-names), scripts/check_db_invariants.py → docs/db-invariants-gap.md (advisory, NOT wired into CI)
- **Détecte :** Snapshots: page count, presence of the totals chain, no prix_achat, and a pixel diff under 2 % on FIXED data. Registry: 10 named invariants (references, TVA chain, mixed-rate reconciliation, status transitions, tenant FKs, prix_achat, legacy-PDF totals, per-line discount), and check_invariants.py only fails if one of those named tests disappears. check_db_invariants: an AST scan for missing CheckConstraints on money and quantity models.
- **Quand :** Snapshots in the release-verify full suite (tag pdf). check_invariants on every CI run. check_db_invariants only by hand.
- **Angle mort :** None of the 10 invariants is about étude or energy figures, and none says 'one quantity, one source'. A 28 %→37 % donut change is far below 2 % of the page's pixels, and a golden generated while the bug existed freezes the bug in place. check_db_invariants is static, only sees money/quantity CheckConstraints, and never reads a row. None of these ever runs against production data.

### Sentry backend + frontend (QAH8) + globalErrors / ErrorBoundary

- **Où :** backend/django_core/core/monitoring.py, frontend/src/lib/monitoring.js, frontend/src/lib/globalErrors.js, frontend/src/ui/ErrorBoundary.jsx, docs/TESTING.md 'Palier 4 — production' (15-min daily triage per company), .env.example, docker-compose.yml build args
- **Détecte :** Uncaught exceptions, unhandled rejections and error-boundary crashes, tagged by company, with masked session replay (10 % of sessions, 100 % on error).
- **Quand :** Continuously once armed. It is NOT armed in production. Checked read-only on prod today: SENTRY_DSN and VITE_SENTRY_DSN are empty in /opt/taqinor-os/.env, and sentry_sdk raises ModuleNotFoundError in the running django_core container (created 2026-09-28 06:37 UTC) even though requirements.txt:153 pins sentry-sdk==2.70.0. core/health reports 'monitoring unknown — Aucun DSN'. So the daily triage cannot be happening.
- **Angle mort :** It is dormant. Even armed, it is structurally blind to this family: a wrong donut throws nothing. It would only help if the code emitted warnings itself, for example a capture_message whenever FALLBACK_KWH_PRICE feeds a saved value, or a soft assertion in build_quote_data when couverture_donut and couverture_horaire differ by more than N points.

### check_frontend_errors.py (EZ16)

- **Où :** C:\dev\taqinor-os\scripts\check_frontend_errors.py (in ci_guards stage-names)
- **Détecte :** A static regression check: JSON.stringify(err) in a user-facing message, or toast.error(err) with a raw error object, under frontend/src/pages and features.
- **Quand :** Every CI run (stage-names).
- **Angle mort :** It is about how errors are shown to users, not a runtime error reporter. It has nothing to say about correct-looking wrong numbers.

### Backend logging / health / beat heartbeat

- **Où :** backend/django_core/core/health.py (+ /api/django/core/health/, /metrics), core.beat_heartbeat every 5 min, settings/dev.py and prod.py LOGGING (StreamHandler → docker logs), docs/production.md
- **Détecte :** Whether infra is alive: DB, cache, broker, storage, beat freshness, queue depth, Redis memory. Checked live on prod: all ok, heartbeat 78 s, 116 beat entries.
- **Quand :** Heartbeat every 5 min; health on request. Logs go to container stdout only, with no aggregation or alerting. Prod deliberately runs settings.dev with DEBUG (docs/production.md, 2026-06-12 decision), so the prod.py LOGGING block is not active.
- **Angle mort :** It reports only infra and liveness. Nobody scans the logs, and the fallback price paths (solar.js estimation flag, pricing._FALLBACK_KWH_PRICE) log nothing when they are used.

### reporting.controle_integrite: weekly cross-document integrity sweep (YSERV13 / WIR22), the ONLY production data sweep

- **Où :** backend/django_core/apps/reporting/integrity.py, apps/reporting/tasks.py, apps/reporting/management/commands/controle_integrite.py, beat 'reporting-controle-integrite-hebdo' in erp_agentique/celery.py
- **Détecte :** Read-only, per company, 7 families of workflow orphans: accepted quote with no chantier, delivered chantier with no equipment, reservations not released, open interventions on a closed chantier, closed tickets with an open intervention, expired active contracts, paid invoices with a balance. It sends an in-app notification when at least 1 anomaly is found.
- **Quand :** Weekly, Monday 03:00 Casablanca, on prod. Checked live: the same digest 'Contrôle d'intégrité : 3 anomalie(s) détectée(s)' has gone to 7 recipients every Monday since 2026-08-10 (75 notifications). Only 3 of the 75 have been read. Current result for taqinor-demo: 2 devis_acceptes_sans_chantier and 1 factures_payees_avec_solde.
- **Angle mort :** No family checks the figures inside a document. It is the right place to add a quote-coherence family, but its alert channel is already effectively ignored: the same 3 anomalies re-sent weekly, 4 % read, no 'only NEW anomalies' logic of the kind the ads reconciliation uses.

### Other production beat detectors (not document-level)

- **Où :** erp_agentique/celery.py: core.scan_live_isolation (monthly dry-run of company_id NULL or orphan), reporting.evaluate_kpi_alertes + core.assurer_alertes_fiabilite_kpi (2 default KpiAlerte: stale restore drill, quota), semantic.detecter_anomalies_metriques (weekly z-score → core.AnomalyFlag), ged.verifier_integrite_archives, adsengine reconciliation/attribution checks, monitoring.balayage_quotidien (PV plant under-performance, not app monitoring). Also the manual command authentication/management/commands/check_data_integrity.py (cross-company FKs).
- **Détecte :** Tenant isolation leaks, infra and backup KPIs, outliers in monthly metric series, archive hash integrity, Meta↔ERP ad drift.
- **Quand :** Monthly or daily or weekly on prod beat. check_data_integrity only by hand. Checked live: AnomalyFlag has 0 rows and KpiAlerte has 2.
- **Angle mort :** None of them reads etude_params or rendered quote figures. The metric anomaly detector works on aggregate monthly series, so a per-quote wrong coverage would never show up.

### Human bug bash brief (QAH9)

- **Où :** C:\dev\taqinor-os\docs\qa-bug-bash-brief.md
- **Détecte :** Timed 90-min sessions for 1-2 French-speaking testers (commercial, technician, accountant charters). The explicit instruction is 'break the totals and the PDF' and check the HT→TTC chain with a calculator.
- **Quand :** Ad hoc. I found no session records in the repo.
- **Angle mort :** Local demo only (no étude data). The charter points testers at the money chain, not at 'do the energy figures on page 1 agree with each other'. A human is actually the most likely to notice 28 % next to −37 %, but only with a realistic lead (bills, no distributor).

### Scheduled jobs actually registered (inventory)

- **Où :** Windows Task Scheduler on this PC; Claude Desktop scheduled tasks; claude.ai cloud routines; GitHub crons
- **Détecte :** n/a (inventory)
- **Quand :** Registered here: 'TAQINOR nightly QA' (next run 29/09 23:00) and 'TaqinorDevClean' (weekly dev cleanup). Claude Desktop scheduled tasks: none. Cloud routines (RemoteTrigger list): none. GitHub: release-verify 03:00 UTC, mutation 03:30 UTC (QAH5, mutmut, non-blocking), loadtest k6 04:00 UTC, load-smoke (Locust) and dependency-audit weekly on Monday, bandit and semgrep on push (advisory).
- **Angle mort :** Nothing scheduled ever looks at production quote documents. The only prod-data sweep is the weekly workflow-orphan digest nobody reads. The error-autopilot is documented as daily but is not scheduled anywhere I could see.

### Non-QA folders and session notes (checked briefly)

- **Où :** C:\dev\meta_audit_output (Meta Ads account/lead audit snapshot, 24/07), C:\dev\odoo_worklists (lead reactivation CSVs, 24/07), C:\dev\radar (+radar.rar; weekly tool/MCP scanner repo), C:\dev\taqinor-os\NOTES_LANE.md / NOTES_LANE_AO_FABRIQUE.md (lane delivery notes), TOITURE_DEVIS_SESSION_SUMMARY.md (June 2026 session record with one-off 'verified live' checks)
- **Détecte :** Nothing on an ongoing basis. They are data exports, a tool radar, or historical notes.
- **Quand :** Never (one-off artifacts).
- **Angle mort :** Not QA tooling. They can be left out of any detection plan.

## 3. Pourquoi ce bug a échappé

Short answer: every test that touched this chain checked one link on its own, against inputs picked by hand. No fixture ever held two sources for the same consumption at once, so a disagreement between them could not happen in a test. Paths are relative to C:\dev\taqinor-os. Checked at 0f166b99, the parent of the fix.

1) frontend/src/features/ventes/autoQuote.facturesReelles.test.mjs (PACT10/QF-REAL, added e3656b2a on 19/08, edited 20/08 and 25/08)
- It ran a hand-written copy of the createAutoQuote block (seedFacturesReellesLikeAutoQuote), which called kwhFromBill itself. The real code was never executed. From 25/08 the real code called consoAnnuelleDepuisFactures(facturesReelles, distributeurLead) and the copy was never updated.
- Its "source lock" tests only regex-checked that three assignment strings and the import were present.
- It even had the exact failing case: "lead avec facture d'hiver flat, sans distributeur connu : … conso estimée". That case asserted only `out.conso_annuelle > 0` and that no distributor key was invented. So it accepted bill ÷ 1.20 as correct. It never asserted a value and never compared with the server's national-grid inversion.
- scripts/check_tests_source_regex.py (QJR239) explicitly allowlists this file (line 71: "createAutoQuote non importable"). The guard meant to stop copy/regex tests exempted the one that mattered.

2) solar.test.mjs, test "QF4 — kwhFromBill : sans distributeur connu → repli FALLBACK_KWH_PRICE, étiqueté estimation"
- It pins bill/1.20 with estimation:true as intended behaviour.
- consoAnnuelleDepuisFactures sums kwhMensuel and throws that flag away. No test checks that the estimate flag survives aggregation and storage.
- test_cad167_distributeur_srm.py::test_SANS_distributeur_le_comportement_d_avant_est_conserve (21/09) pinned the no-distributor fallback as "inchangé".
- test_un_lead_SANS_distributeur_obtient_sa_SRM_depuis_sa_ville proves the SERVER infers an SRM from the city. The front end still read lead.distributeur = NULL. No test compares the two sides' answer to "does this lead have a distributor?".

3) Bill-to-kWh mirror tests never used the no-distributor path
- test_bareme_selectif_fondateur.py (the three-branch drift lock) and QJW24 billInversionParite only call kwh_from_bill with utility onee/lydec/redal or an override. None uses utility=None, 'autre' or an SRM code, which is where solar.js and pricing.py disagreed.
- QAH3 test_solar_differential.py (28/09, 200-entry corpus) says in its docstring that "tarifs par tranche" and the rest of calculate_savings_roi are out of scope. It compares classification, kWc, productible, the production formula and TTC totals. It never compares consumption or coverage.

4) test_quote_engine_builder.py::TestQuoteNumbersHonestyPack::test_coverage_uses_real_consumption_when_known (QX7a, edited by COUV-AUTO dc03b0b4 on 17/09)
- Fixture: conso_annuelle=12000 picked by hand, distributeur 'onee', 12 bills, and no etude_horaire block.
- It asserts coverage == min(100, max(1, round(prod × autoconso_avec / 12000 × 100))). That is the implementation's formula typed again in the test.
- With no hourly block there is no second source to disagree with.
- It also makes "conso_annuelle present ⇒ coverage_estimated False" a rule. So a ÷1.20 estimate, once stored, was treated as measured and printed without "(estimation)". ancrage_reel_absent likewise treats conso_annuelle_kwh > 0 as "consommation annuelle SAISIE".
- COUV-AUTO's own commit says "même définition que la Couverture de la proposition en ligne (moteur horaire)". It recomputed the value instead of reading the engine's number, and no test asserted equality with annuel.couverture_*.

5) The hourly-engine fixture bloc_horaire() (test_cj2b_graphe_mensuel.py, used by builder tests QJR18/QJR27)
- It carries annuel.consommation_kwh=7838 but no couverture_sans/avec.
- Those tests never set etude_params.conso_annuelle and never assert coverage_pct. Engine consumption and stored consumption were never in the same fixture.

6) test_pvcov_synthese_servie.py (PVCOV, 18/08)
- Its parity checks compare the PDF with the online proposal, but both call the same synthese_economies. If that function is wrong, both sides are wrong in the same way and the test stays green.
- The pure tests use sample_data.build("deux") with conso 15000 and assert only 1 ≤ coverage_pct ≤ 100, the estimation flag, and the pct_cut formula.
- Nothing links coverage_pct to pct_cut on the same page (−37 % next to 28 %). Nothing links it to the hourly engine's couverture either.
- No test compares the generator screen with the PDF for coverage. The screen showed etude_horaire couverture_sans (DevisGenerator.jsx:4435/4742), i.e. 37 %, while the PDF showed 28 %.
- test_devis_auto.py and the other /ventes/devis/auto/ tests never pass a front-end-derived conso_annuelle. The front and back halves of the PACT10 contract are tested separately, and the contract checks key names and types, not values.

7) Other safety nets
- test_quote_engine_snapshot.py (golden PDFs) runs only at release-verify, with a 2 % pixel tolerance, on fixed fixtures that have no hourly block. A "28"/"37" glyph change is far below 2 %, and a snapshot would lock whatever value it saw.
- QA-explorer (QAH1, 28/09) runs on seed_demo. Its 5 DEV-DEMO quotes have no etude_params, so the Z2 rule hides the savings synthesis and the donut is never drawn. Its hard oracles are 4xx/5xx, console errors, an empty list after creation, prix_achat shown, and cross-tenant leaks. None compares figures.
- Error-autopilot scans code and tests, not rendered real quotes.
- docs/invariants.md (21 test references) has no coverage/pct_cut/consumption invariant.
- Sentry only catches exceptions and was only wired on 28/09.
- Nothing ever queried prod data. My read-only prod query (scratch qa_conso_drift.py, rollback, no writes) found:
  - 127 of the 135 prod quotes that have both etude_params.conso_annuelle and etude_horaire.annuel.consommation_kwh disagree by more than 5 % (94 %).
  - 108 of them match bills ÷ 1.20 to within 2 kWh. 96 have distributeur None and 31 have 'onee'. Ratios mostly 1.34–1.54.
  - The first one is DEV-202608-0018 (21/08). There were 3–32 new ones every week from W33 to W39. By status: 37 envoyé, 9 expiré, 81 brouillon.
  - So the defect was the normal case, not an edge case. A one-line prod check of "stored consumption vs engine consumption" would have fired on day 1.

Root pattern: tests re-type the formula, pick inputs by hand, and lock today's output. Parity tests compare surfaces that share one function. The fallback is tested alone while its flag is lost at storage. And nothing checks prod data.

### Comment la famille de bugs a été découverte

30 instances, 2026-07-10 to 2026-09-29:
- 9 of 30 (30 %) were found by a human looking at a real document or prod quote: devis 180/PV86, the ERP vs site grid, the screen/PDF loss gap, PVCOV, DEV-202608-0007, DEV-202608-0015, DEV-202608-0023, COUV-AUTO + PR #687, DEV-202609-0113. In practice that human was the founder.
- 18 of 30 (60 %) were found by one-off AI code audits or adversarial reviews that a human asked for: the QX, S, M, Q, QJR, QJW, CAD and TAILLES/COUVBAT reviews. These read code; none looked at real prod quotes.
- 3 of 30 (10 %) were found by standing automation: the QAH3 differential test, the QA-explorer fleet, and error-autopilot (ERR120). All 3 are dated 28–29/09, within 48 hours of the QAH harness going in.

Before 28/09, standing automation found 0 of 27. The normal CI suite made 0 of 30 discoveries, and prod monitoring (Sentry) made 0.

Every instance that reached clients' hands was found by the founder, not by a check. Several fixes found that existing tests had locked in the wrong behaviour:
- M1: 4 tests pinned the proxy bill.
- Q7: 2 tests pinned the invented grids.
- QJW18: the test DOM put the SVG text in the wrong place.
- L-2OPT: there were no fixtures with divergent options.
- DEV-202609-0113: the test replayed a copy of the code.

Repeat offenders:
- The coverage donut was fixed 4 times: QX7 (10/07), S2/PVCOV (18–19/08), COUV-AUTO (17/09), COUV-HOR (29/09).
- The "bill ÷ flat price with the estimation flag dropped" mechanism was fixed 3 times, each time on one surface only: QX7d (10/07), M10 (20/08), CAD167 (21/09). It survived in autoQuote.js and solar.js until 29/09.

Prod data: of the 135 prod quotes that store both consumptions, 127 (94 %) disagreed by more than 5 %, 108 of them with the exact bills ÷ 1.20 signature. The first was 2026-08-21 (DEV-202608-0018). A simple prod-data invariant could have caught this 39 days before the founder did.

### Les incidents de la même famille

- 09155822 | 2026-07-10 | QX7(a): the PDF coverage donut used an invented /1.3 divisor and a 40 % floor instead of the real consumption, with no '(estimation)' label (families a+b) | one-off AI audit (QX group, 'quote-journey round 6, 2-round audit')
- 47a3ae3b | 2026-07-10 | QX7d: the online proposal used two different kWh prices; the consumption chart divided the bill by a flat 1.75 while the ROI used tranches (a, c) | one-off AI audit (QX)
- fe47cb4e | 2026-07-10 | QX38: screen, PDF and web used different productible models, and the ONEE tranche ceilings were mislabelled in pricing.py and solar.js (d) | one-off AI audit (QX)
- c2c01c9b (+fb131703, reverted by bb9e90e0) | 2026-08-15/16 | PV86: the client page showed an invented 'Sans batterie 26 186 MAD' option while the PDF showed the real total; prod devis 180 showed 31 000 MAD for a 65 000 MAD quote because a stored scenario contradicted its lines (b, c) | caught in prod after delivery, a human on a real quote
- b4826e61 | 2026-08-18 | the ERP (solar.js + pricing.py) used a progressive grid while the public site used the selective ONEE grid, so the same household got two different savings figures (d) | founder (order of 18/08 about the price per kWh)
- 3e355126 | 2026-08-18 | screen vs PDF: the PDF double-applied losses (26 %) while the screen applied none; the screen promised +2 %/yr tariff escalation while the PDF said constant tariff (c, d) | two screen/PDF gaps reported the day before, settled by founder order; human
- e2f672d9 | 2026-08-18 | PVCOV: the −N %, before/after and donut on the web page were computed separately from the PDF page 1 (c) | founder order ('serve those numbers so the page and pdf always match')
- ab98b881 | 2026-08-19 | PVUNI/PVSTR/PVFRESH: on DEV-202608-0007 the online page and the PDF had different panel counts and costs; 6.48 kWc from 720 W layout panels sat next to '9 × 710 W' (6.39); a stale stored PDF was served (a, c) | founder incident on a real quote
- 95a0ce40 + 57e5fb53 | 2026-08-19 | S1/S2: the PDF rebuilt the 'before' bills from the assumed savings (a circular proxy), so the coverage donut always equalled the flat self-consumption rate (b) | one-off AI audit of 19/08
- 003b1480 | 2026-08-20 | PVAB: on DEV-202608-0015 the quote list showed 77 584 MAD, the sum of both options, an amount that appears on no document (a, c) | incident on a real quote plus founder request
- e5ec1e0f | 2026-08-20 | Z1/Z2/Z3: an invented 'Batterie 5 kWh', savings computed from the 1.20 fallback shown as real, and the 'personnalisé' tariff line always printed (b) | founder policy order after audit, no specific document named (counted as audit)
- 34fdd225 | 2026-08-20 | M1: the circular proxy bill (savings ÷ self-consumption rate) was printed as the client's bill and '−85 %'; 4 existing tests locked the proxy in as intended (b) | one-off AI adversarial audit, 20/08
- 13bf5144 | 2026-08-20 | M10: the public consumption curve divided the bill by a flat 1.20 when no distributor was known and dropped the estimation flag, so kWh were shown as a measurement. This is the same mechanism as DEV-202609-0113, fixed on only one surface (b) | one-off AI adversarial audit
- 66181904 | 2026-08-20 | Q7: invented Lydec/Redal grids meant that changing the distributor label changed the bill; the JS mirror had to follow; 2 tests locked in the invented grids (d) | audit question settled by founder decision
- d3efa787 | 2026-08-21 | Z5/Q1/M9 existed in pricing.py but were never ported to solar.js, so the screen showed a longer payback than the PDF for the same quote (d) | AI follow-up review
- 5f3b581d | 2026-08-24 | DEV-202608-0023: the public payload served monthly_consumption [] because a second consumption path required a distributor ('autre' or none → estimation → emptied), while savings came from the hourly engine's consumption (two paths for one quantity) (a, b, c) | real prod quote (human)
- 0e4deb86 + 44d56478 | 2026-08-25 | two options of different sizes (22 and 26 panels): savings, ROI, production and price per kWc came from one option's kWc and were printed next to the other's; the fix notes there were zero fixtures with divergent options (a) | lane review of L-2OPT (AI)
- d9e2f26a | 2026-08-26 | TAILLES F1/F2: the 25-year cumulative total was a second calculation that did not match the plotted curve; 'couverture 61 %' came from a stale hourly block and sat next to the price of the new sizing (a, b) | AI adversarial pre-merge review
- 2fbd30ee + 8250cef3 | 2026-08-26 | COUVBAT: the 'Autonomie complète' marker promised full cover while the engine served 97.5 % / 73.4 %; bars drew energy the counter said was 0; an annual rate sat next to daily kWh (a) | AI adversarial review
- 4b118de0 | 2026-08-29 | QJR18: '≈ N kWh par kWc' was about 7 % below the annual production on the same page (losses applied twice) (a) | one-off AI audit L3 (quote journey review, 29/08)
- 12f23a4f + d5c08a5e | 2026-08-30 | QJR114/115: the Étude page printed 'Production annuelle 12 486' and 'P50 11 000 kWh' for the same system (a) | one-off AI audit L3
- c37f6b3b | 2026-08-30 | QJR156: 0.92 MAD/kWh (the lowest band) was printed as 'tarif retenu' without 'estimation' when consumption was missing; a fully closed company grid fell back to 1.20 and was presented as the client's tariff (b) | one-off AI audit (QJR79)
- 2e2a2f88 | 2026-08-31 | QJW18: the donut arc showed the loaded size while the percentage in the centre kept the official quote's value; tests were green because the test DOM put <text> outside the <svg> (c) | one-off AI audit (QJW, L3 29/08)
- dc03b0b4 + PR #687 | 2026-09-17 | COUV-AUTO: the donut printed '100 %' (production ÷ consumption) while the online 'Couverture' used self-consumed energy ÷ consumption; also 'page client: les chiffres ne sont pas les mêmes que le PDF' (a battery tier at 58 865 MAD under a 73 935 MAD card) (a, c) | founder on a real document
- 81bce600 | 2026-09-21 | CAD167: distributor 'autre' fell back to a flat 1.20 'estimation' and the public curve disappeared; fixed only in pricing._resolve_tranches, and the no-distributor fallback was deliberately kept (b, d) | AI audit (CAD, finding F5) plus founder decision Q16
- e53fbbf9 | 2026-09-28 | ERR-QAH-SOLAR-TOTALS-ROUNDING-ORDER: the TTC total on screen (solar.js) and in the backend differed by 0.01 MAD on 36 of 200 corpus entries (d) | automation: QAH3 differential test
- 3fef94d1 | 2026-09-28 | ERR-QAH-VENTES-TOTAL-DIVERGENCE-CREATION: the same quote showed three TTC totals (97 391 on the form, 117 391 on the saved screen, 94 391.16 in the list and API) (c) | automation: QA-explorer LLM fleet on seed_demo
- 7965f81b | 2026-09-29 | ERR120: on the 'Devis Final' PDF, Acompte + Matériel + Solde added up to 1 MAD less than the Total TTC printed on the same page (a) | automation: error-autopilot static scout
- f834e376 + df9e1e1b | 2026-09-29 | DEV-202609-0113: donut '28 %' next to '−37 %'; conso_annuelle stored as bills ÷ 1.20 (165 000 vs 123 024 kWh); reopening the quote re-saved the wrong consumption and stamped it 'onee' (a, b, c) | founder on a real quote
- a8aeb16c | 2026-09-29 | CAD167 mirror: solar.resolveTranches and pricing._table_tarifaire still fell back to 1.20 for named distributors (SRM, 'autre') after CAD167 fixed only _resolve_tranches (d) | found while fixing DEV-202609-0113 (AI, triggered by the founder's report)

## 4. Prototype d’auditeur — résultats sur la prod (code d’avant #738)

310 devis, 15.4 s.

### I1 — 80 signalés

- **Règle :** Page-1 donut coverage_pct vs the hourly engine's own coverage (round(etude_horaire.annuel.couverture_{avec|sans}*100), with avec = max(avec, sans), and sans when the battery is deferred). Only checked when the column is priced with the 'horaire' model and page 1 actually prints the economics block.
- **Tolérance :** |diff| <= 2 pts
- **Faux positifs :** 80 of 85 checked (26 envoye, 2 accepte). The donut is always too low: median -19 pts, p05 -33, min -57, max +13. False positives should be near zero because the expected value is the exact number the fixed code (#738) prints; only rounding is left, covered by the 2-pt tolerance. The one +13 outlier was not investigated. DEV-202609-0113 itself was NOT confirmed as flagged: this run kept only the top-5 examples per rule, and the run that would have listed every flagged ref was blocked. The rule cannot see quotes whose hourly block is stale (see I7), which is why 85 were checked, not 134.
- Exemple : DEV-202609-0042 envoye: donut 34 vs hourly 47, pct_cut 45, conso stored 39996 vs hourly 29027
- Exemple : DEV-202609-0052 envoye: donut 35 vs hourly 48, conso 150000 vs 111744
- Exemple : DEV-202609-0056 envoye: donut 45 vs hourly 62
- Exemple : DEV-202609-0057 envoye: donut 49 vs hourly 74 (pct_cut 80)
- Exemple : DEV-202609-0058 envoye: donut 43 vs hourly 62

### I2 — 35 signalés

- **Règle :** When every month stays above the top tranche (500 kWh/month) before and after solar, the bill is linear in kWh, so pct_cut must sit in [coverage*(1 - fixed_share) - 2, coverage + 1]. Checked on printed page 1, with the minimum monthly consumption after solar taken from the hourly block.
- **Tolérance :** lower slack 2 pts, upper slack 1 pt; fixed_share = 12 x 39.94 MAD / annual bill
- **Faux positifs :** 35 of 40 linear-regime quotes (12 envoye, 1 accepte). pct_cut minus donut: median +12.5, p05 -1, min -15, max +29. This rule needs no hourly block, so it would have caught the donut bug on its own. As a check, I fed the engine's coverage instead of the donut by hand for 3 examples (47/45, 48/47, 62/60) and all 3 pass. The automated version of that control (I2c) was written but not run on prod. Outside the top tranche (99 quotes) pct_cut is above coverage by a median of 20 pts, which is expected from the tranche drop, so those are not checked. The min -15 case was not investigated. Months close to 500 kWh are borderline.
- Exemple : DEV-202609-0042 envoye: donut 34, pct_cut 45, allowed [31.7, 35]
- Exemple : DEV-202609-0052 envoye: donut 35, pct_cut 47, allowed [32.9, 36]
- Exemple : DEV-202609-0056 envoye: donut 45, pct_cut 60, allowed [42.6, 46]
- Exemple : DEV-202609-0065 envoye: donut 36, pct_cut 50 (min month after solar 503 kWh, borderline)
- Exemple : DEV-202609-0067 envoye: donut 45, pct_cut 60

### I3 — 125 signalés

- **Règle :** Stored etude_params.conso_annuelle vs the hourly engine's annuel.consommation_kwh
- **Tolérance :** ratio within 1 +/- 0.10
- **Faux positifs :** 125 of 135 checked (36 envoye). Ratio median 1.44, p05 1.036, min 0.82, max 271.7 (that outlier was not investigated, probably a units issue). Every flag is a real disagreement. Caveat: after #738 the screen still derives conso with an energy-only JS table (see I9), so this rule will keep firing at about +5 to +35% on small and medium bills until the JS mirror is fixed. Tolerance or scope must be revisited after that fix.
- Exemple : DEV-202609-0042 envoye: 39996 vs 29027 (x1.378, hourly model in use)
- Exemple : DEV-202609-0052 envoye: 150000 vs 111744 (x1.342)
- Exemple : DEV-202609-0055 envoye: 13000 vs 8731 (x1.489, hourly NOT used: stale block)
- Exemple : DEV-202609-0057 envoye: 11000 vs 7230 (x1.522)

### I4 — 129 signalés

- **Règle :** Fallback signature: conso_annuelle == sum(12 real bills in factures_mensuelles_reelles) / 1.20, meaning the flat fallback price was stored as if it were measured consumption
- **Tolérance :** +/- 12 kWh/yr
- **Faux positifs :** 129 of 141 quotes with 12 real bills (35 envoye). False positives should be near zero: a barème-derived consumption landing within 12 kWh of bills/1.20 would be a coincidence. This rule is pure metadata (no rendering needed) and would have fired on the first bad quote around 2026-08-20.
- Exemple : DEV-202609-0052 envoye: conso 150000 = 180000/1.20, distributeur null, hourly 111744
- Exemple : DEV-202609-0055 envoye: 13000 = 15600/1.20
- Exemple : DEV-202609-0057 envoye: 11000 = 13200/1.20
- Exemple : DEV-202609-0042 envoye: 39996 (48000/1.20 - 4, the x12 re-save drift) although distributeur='onee'

### I5 — 60 signalés

- **Règle :** A printed 'current bill' (page-1 annual_before, savings_method.facture_actuelle, facture_sans_solaire) vs the sum of the client's real bills (12 factures_mensuelles_reelles, otherwise the lead's winter/summer series)
- **Tolérance :** ratio within 1 +/- 0.10
- **Faux positifs :** 60 of 146 (11 envoye), which matches the known '11 sent quotes with a bill ~40% too high'. facture_sans_solaire ratio: median 1.42 (n=61). page-1 annual_before equals the real bills in 144/144 cases, so the contradiction sits inside the same document. False positives are low when the 12 bills are real. They are possible when only a winter bill exists, because the yearly total is then an extrapolation. One outlier at ratio 0.005 was not investigated.
- Exemple : DEV-202609-0055 envoye: method block and étude print 22425 MAD/yr vs real bills 15600 (x1.438, factures model)
- Exemple : DEV-202609-0062 envoye: 25616 vs 18000 (x1.423)
- Exemple : DEV-202609-0063 envoye: 25616 vs 18000 (x1.423)

### I6 — 6 signalés

- **Règle :** Sanity checks. I6a: annual savings > 0 and <= printed current bill. I6b: printed payback within +/-30% of total_ttc / annual savings. I6c: no NaN/inf or negative values in client-facing numbers.
- **Tolérance :** I6a 0.1%, I6b 30%, I6c exact
- **Faux positifs :** 1 I6a, 5 I6b, 0 I6c. Payback divided by price/savings has median 1.019 and p95 1.055, so 30% is loose and 10% would still be quiet. DEV-202609-0108 is probably legitimate (battery/inverter replacement in the 25-year cashflow). The 0082 flag is a real 'cap hides nonsense' case.
- Exemple : I6a DEV-202606-0087 brouillon: sans option eco_s_ann = 0
- Exemple : I6b DEV-202609-0082 brouillon: payback printed 25 yrs but price/savings = 865 yrs (the 25-year cap hides a system that never pays back)
- Exemple : I6b DEV-202609-0108 envoye: payback 15.4 vs 11.45 (x1.34)
- Exemple : I6b DEV-202609-0013/0014 brouillon industriel: 16.8 vs 11.1 (estimation model)
- Exemple : I6c: 0 flagged out of 177

### I7 — 60 signalés

- **Règle :** Stale hourly block: etude_horaire.kwc vs the quote's kWc (and per option when options diverge). The engine silently rejects the block and falls back to the 'factures' or 'estimation' model. I7b: a block exists but a column is not priced 'horaire'.
- **Tolérance :** 2% (the engine's own _HORAIRE_TOLERANCE_KWC)
- **Faux positifs :** 60 of 145 blocks (15 envoye). I7b flags the same 60, so every silent downgrade is caused by staleness. NEW BUG not covered by #738: in all 5 examples the block kWc is exactly kWc_sans + kWc_avec. Cause: apps/ventes/domain/etudes.py rafraichir_etude_horaire_devis (lines 214-225) takes kWc from panneaux_et_watt_lu over ALL product lines, both variantes included. As a result, two-option quotes whose options have different panel counts never get an hourly study. The sum signature is checked on 5/5 examples only; the full check was written into v2 but not run on prod. No false positives for the staleness itself.
- Exemple : DEV-202609-0053 envoye: block 9.94 kWc = 4.26 (sans) + 5.68 (avec), both columns fell back to 'estimation'
- Exemple : DEV-202609-0055 envoye: block 10.65 = 4.26 + 6.39, fell back to 'factures' (with the /1.20 conso, which produces the I5 +44% bill)
- Exemple : DEV-202609-0062 envoye: block 10.65 = 4.97 + 5.68
- Exemple : DEV-202609-0063 envoye: block 9.23 = 4.26 + 4.97

### I8 — 0 signalés

- **Règle :** The PDF page-1 summary rebuilt with the last-render options (pdf_render_meta.options) vs the public proposal's summary (pdf_mode full): pct_cut, coverage, before/after, eco_option, eco/roi/totals
- **Tolérance :** exact
- **Faux positifs :** Low statistical power: 4 checked, 0 flagged. Both sides share build_quote_data and synthese_economies, so they can only diverge through PDF options (scenario, variante). Parity with the screen (JS) cannot be checked server-side except through JS outputs saved in the database (I9).
- Exemple : Only 4 residential quotes had pdf_render_meta with a residential layout; 273 quotes have no pdf_render_meta at all

### I9 — 135 signalés

- **Règle :** JS/Python mirror: conso_annuelle stored by the screen (solar.js consoAnnuelleDepuisFactures) vs the Python barème inversion (etude_horaire.serie_kwh_depuis_mad with company tranches and fixed charges) of the same 12 stored bills
- **Tolérance :** ratio within 1 +/- 0.03
- **Faux positifs :** 135 of 141 flagged, but 129 of those are the /1.20 fallback already caught by I4, so at least 6 are drift that is not the fallback. The offline grid (node + local container, no prod data) shows JS and Python disagree on 82 of 82 bill values: kwhFromBill appears to invert with the energy-only tariff table and does not remove the fixed meter and connection charges or the TPPAN tax. This drift is still on the fix branch. The v2 split (I9 vs I9fb) was not run on prod.
- Exemple : DEV-202609-0042 envoye: JS 39996 vs Python 29027 (x1.378, /1.20 fallback)
- Exemple : DEV-202609-0052 envoye: 150000 vs 111744 (x1.342, fallback)
- Exemple : Local grid, 12 identical bills, JS 'onee' vs Python defaults: 60 MAD/mo 786 vs 263 kWh/yr (+199%), 300 MAD/mo 3032 vs 2520 (+20%), 700 MAD/mo 6079 vs 5122 (+19%), 5900 MAD/mo 43627 vs 42592 (a constant offset of about +1035 kWh/yr)

### I10 — 18 signalés

- **Règle :** Page-1 monthly-chart savings total (sum of before - after, with after floored at 0) vs the option card's annual savings for the same option
- **Tolérance :** +/- 3%
- **Faux positifs :** 18 of 144 (3 envoye). Each flag means the model's monthly savings exceed the client's real monthly bill (a fallback conso that is too high, priced against real bills). The two figures genuinely contradict each other on the same document, so these are not false positives.
- Exemple : DEV-202609-0055 envoye: chart 15006 vs card 17392 (x0.863), 12 real lead bills
- Exemple : DEV-202609-0088 envoye: 11239 vs 11680
- Exemple : DEV-202609-0111 envoye: 24946 vs 26303
- Exemple : DEV-202608-0013 brouillon: 13914 vs 20350 (x0.684)

### I11 — 97 signalés

- **Règle :** Page-1 '-N %' vs the percentage implied by the method block's example (facture actuelle -> avec solaire)
- **Tolérance :** +/- 2 pts
- **Faux positifs :** HIGH false-positive rate as measured. For scenario 'Les deux', page 1 describes the avec option and the method block describes sans, so the rule compares different options (median gap 20 pts). Some flags are absurd real cases (-96% vs -28%, both driven by the /1.20 conso). v2 adds I11s (same-option bill pair) and I13 (the two 'current bill' figures on one document); both were written and smoke-tested locally but NOT run on prod.
- Exemple : DEV-202609-0055 envoye: page 1 -96% vs method block 22425 -> 16160 (-28%)
- Exemple : DEV-202609-0062 envoye: -63% vs -29%
- Exemple : DEV-202609-0057 envoye: -80% vs -61%

### I1x_I2c_I9fb_I11s_I13 — -1 signalés

- **Règle :** v2 additions: I1x = donut vs hourly coverage whatever the model (reconciles with the 134 count); I2c = control that feeds I2 the engine's coverage to measure I2's false-positive rate; I9fb = splits fallback from genuine mirror drift; I11s = same-option -N % check; I13 = page-1 annual_before vs method-block facture_actuelle (+/-5%)
- **Tolérance :** as stated per rule
- **Faux positifs :** Unknown until v2 runs on prod. -1 means not measured.
- Exemple : NOT MEASURED on prod: the v2 prod run was denied by the permission classifier ('Production Reads'). Only the local smoke test ran (38 local devis, no hourly blocks, no crash).

### Notes d’exécution

WHAT RAN. The v1 auditor (saved as doc_consistency_audit_v1.py) ran once on prod. Prod is at 0f166b99, the old pre-#738 code. It ran inside transaction.atomic() with set_rollback(True) and a savepoint per devis, with nothing saved. The roof-photo fetch from MinIO was patched out in the shell process only. 310 devis scanned, 308 built. The 2 failures are DEV-DEMO-0004/0005, which raise ValueError because no option has an inverter; that is an expected refusal. Audit time was 15.4 s (Django startup not included), so this is cheap enough to run nightly or after each deploy. Page 1 prints the economics block on 144 quotes; 131 omit it and 33 are non-residential or use the legacy renderer. Raw prod output: scratchpad\auditor\prod_run.txt and prod_audit.json. A first read-only census (census_dca.py) also ran: 310 devis, 145 with hourly blocks.

PERMISSION STOP (the user must decide). After the v1 run, the auto-mode classifier denied a second prod run of the extended v2 script, reason '[Production Reads]'. It also denied two local reads (public_views.py lines ~1885-2135 and bareme.py) under the same label. I did not retry either one. The prod approval quoted in the task text came from the workflow script, not from the user in chat. Re-running v2 on prod (I1x, the I2c control, I9 split, I11s, I13, full per-rule ref lists, and a DEV-202609-0113 membership check) needs the user's explicit OK or a permission rule. v2 is doc_consistency_audit.py; it compiles and passed a local smoke test.

Leftover files: census_dca.py and doc_consistency_audit.py (v1) remain in /tmp on the prod host and in the django_core container. I did not delete them, because deleting would be a write on prod. They are harmless.

KEY FINDINGS.
(1) The donut bug is caught several independent ways. I1 caught 80 (26 sent). I2 caught 35 using physics only, with no hourly block. I4 found 129 quotes whose stored conso equals bills/1.20; that rule is metadata-only and would have fired on day one (~2026-08-20).
(2) NEW bug not fixed by #738, 60 quotes (15 sent). For two-option quotes whose options have different panel counts, the hourly study is computed for kWc_sans + kWc_avec. The cause is apps/ventes/domain/etudes.py rafraichir_etude_horaire_devis L214-225, which takes kWc from panneaux_et_watt_lu over all lines. The engine's 2% freshness guard then rejects the block, and both columns silently fall back to 'factures' (priced on the /1.20 conso) or 'estimation'. This fallback is the source of the I5 +42% current bills and absurd page-1 figures such as DEV-202609-0055: '-96 %' on page 1 while the method block shows 22425 -> 16160.
(3) JS/Python mirror drift that is still on the fix branch. solar.js kwhFromBill / consoAnnuelleDepuisFactures inverts bills without removing the fixed meter/connection charges and the TPPAN tax. It gives +20-35% kWh at 200-700 MAD/month and a constant ~+1035 kWh/yr at large bills vs the Python barème. The grid probe is local-only: js_conso_grid.mjs and py_conso_grid.py.
(4) Screen-vs-PDF parity (I8) has little evidence: only 4 quotes carry pdf_render_meta. JS screen parity is only reachable through JS values saved in the DB (I9).

AFTER #738 DEPLOYS, expect I1 to drop to ~0. I2 should quiet down. I3, I4, I5, I7, I9 and I10 will keep firing: the stored conso values and the sum-kWc stale blocks are not repaired by #738, and the JS drift remains.

Files in C:\Users\kasri\AppData\Local\Temp\claude\C--dev\86026cd6-52e4-4480-9adc-4c9517346d88\scratchpad\auditor\: doc_consistency_audit.py (v2), doc_consistency_audit_v1.py (the one that ran on prod), patch_v2.py, prod_run.txt, prod_audit.json, census_dca.py, js_conso_grid.mjs, js_grid.json, py_conso_grid.py, local_run_v2.txt.

## 5. Recommandations (classées)

Yes, this bug family can be caught automatically. Everything you have today (about 100 static guards, 134 contract samples, the PDF snapshots, the QA explorer, error-autopilot, Sentry) checks declarations or crashes, and a wrong number that looks right trips none of them. Standing automation found 0 of the first 27 of the 30 past instances; the founder found every one that reached a client. A read-only nightly check of real prod quotes costs almost nothing: the prototype scanned 310 quotes in 15.4 s. Its fallback rule would have fired on 2026-08-21 (DEV-202608-0018), 39 days before the founder noticed DEV-202609-0113. Along the way it found two more live bugs that PR #738 does not fix. The plan is to write the rules once, as one shared library, and run it in five places: nightly on prod, at render, before a quote is sent, in the per-PR e2e test, and in generated property tests.

### 1. Nightly read-only check of every prod quote, alerting only on new problems — effort M

Turn the prototype (scratchpad\auditor\doc_consistency_audit.py) into a pure rule module, backend/django_core/apps/ventes/coherence/regles.py. Each rule is a function over build_quote_data(devis) + etude_params + the lead's energy profile that returns a list of Violation(regle, gravite, valeurs). Add a management command, apps/ventes/management/commands/audit_coherence_devis.py (--company, --since, --json, --nouvelles-seulement), and a nightly beat entry 'ventes-audit-coherence-nuit' (02:30 Casablanca). Everything runs inside transaction.atomic() with set_rollback(True) and a savepoint per devis. build_quote_data also needs a side-effect-free mode (pure=True): the prototype had to patch out the MinIO roof-photo fetch. Rules that alert from day one (all measured on prod, with low false positives): I4 fallback signature (conso == 12 bills / 1.20 ± 12 kWh; 129 hits, 35 sent; needs only stored data, no rendering); I1 donut vs the hourly engine's coverage ±2 pts (80 of 85, 26 sent); I2 a physics bound linking −N % to coverage in the linear tariff regime (35 of 40, needs no hourly block); I5 printed current bill vs the real bills ±10 % (60, 11 sent, the same 11 already known); I7 hourly block computed for the wrong kWc, so the model is silently downgraded (60, 15 sent); I10 monthly chart savings vs the card ±3 % (18); I6 sanity (payback hidden by the 25-year cap, NaN, savings larger than the bill). Rules that stay report-only until tuned: I3 (flags 125 of 135 and will keep firing until the JS drift is fixed), I9, and I11 (to be replaced by I11s/I13). Store each violation in the existing core.AnomalyFlag (0 rows today): subject_type='ventes.Devis', a severity, and statuses ouvert/ignoré/résolu, which gives both 'new only' de-duplication and a way to acknowledge a false positive. A violation on an envoyé or accepté quote alerts the same night. Drafts go into a daily summary.

- **Détecte :** Families (a) and (b) on real data, plus (c) wherever the PDF and the proposal share build_quote_data. History: 30 instances; 9 were found by the founder on real quotes and 0 by prod monitoring. The prototype also surfaced two bugs #738 does not fix: 60 two-option quotes (15 sent) whose hourly study is computed for kWc_sans + kWc_avec, because etudes.py:214-225 reads panels across both variantes; and I9, solar.js inverting bills without removing fixed charges or the TPPAN tax.
- **Aurait détecté DEV-202609-0113 :** Yes, on the first night: I4 and I3 fire on DEV-202608-0018 (2026-08-21, ×1.505), 39 days before the founder. Non-draft divergent quotes per week ran 1, 1, 4, 14, 19, 7 (W35–W40), so it would have fired before almost any were sent. 0113 itself (165 000 vs 123 024 kWh, ×1.34) has the I3 signature. Caveat: that 0113 is in I1 was not confirmed, because the v2 prod run was stopped at a permission prompt.
- **Où ça se branche :** backend/django_core/apps/ventes/coherence/ (new), apps/ventes/management/commands/audit_coherence_devis.py, the beat entry in erp_agentique/celery.py next to 'reporting-controle-integrite-hebdo', and core.AnomalyFlag for the store. The same rule module is reused by recommendations 2, 3, 6, 7 and 8.
- **Coût / risque :** Zero CI minutes (it runs on prod beat); about 15 s per night for 310 quotes. Risks: (1) build_quote_data must be proven side-effect free (MinIO fetch, any pdf_render_meta stamping), or the run stays inside the savepoint + rollback. (2) Alert fatigue: the existing in-app digest has 3 of 75 notifications read. Send only NEW critical violations, by e-mail or WhatsApp to the founder, or open a GitHub issue labelled 'prod-coherence' in the style of nightly_alert_gate.py. (3) Don't add it to reporting/integrity.py FAMILIES: that loop swallows exceptions into an empty list, so a crashed rule would look clean. Count a crashed rule as its own alert.

### 2. Make the per-PR devis e2e test compare screen, PDF and online proposal on the path it already runs — effort S

frontend/e2e/devis.spec.js (E4) already creates a lead with facture=900, Casablanca and no distributor (the exact bills ÷ 1.20 path) on every PR, but it only asserts that a canvas shows and that a .pdf downloads. Extend it in four steps: (1) read coverage, −N % and current bill from the generator screen through new data-testid attributes (DevisGenerator.jsx, around lines 4435/4742 where it shows etude_horaire couverture); (2) fetch /proposal bytes with page.request and extract the text with pdfjs-dist, which is already in frontend/package.json; (3) fetch proposal/<token>/data; (4) assert the three sources agree and satisfy the I2 bound. Add createLead variants in e2e/helpers.js for 12 real bills with no distributor, winter bill only, and SRM/'autre'. In the residential templates, add data-figure markers next to the printed donut, −N % and current bill so extraction is robust.

- **Détecte :** (c) screen vs PDF vs web, and (a) on the page itself. History: 12 of 30 instances were screen/PDF/web splits (PV86, 3e355126, PVCOV, PVUNI, PVAB, QJW18, COUV-AUTO/#687, ERR-QAH-TOTAL-DIVERGENCE, 0113…), mostly found by the founder.
- **Aurait détecté DEV-202609-0113 :** Yes, at merge: red on the first PR after the two halves diverged (~20–25/08). The screen showed the hourly coverage (the 37 % kind) and the PDF recomputed from the ÷ 1.20 conso (the 28 % kind), on a path E4 ran on every PR.
- **Où ça se branche :** frontend/e2e/devis.spec.js, frontend/e2e/helpers.js, the residential templates and DevisGenerator.jsx (test ids only). It stays in the required 'e2e' check.
- **Coût / risque :** About 5–10 s more in the existing required e2e lane 2; no new job. Risk: text extraction breaks when the layout changes, which the data-figure markers mitigate. seed_demo must give the auto-quote an hourly étude and bills, otherwise the Z2 rule hides the economics block and the test proves nothing. Assert that the block is present.

### 3. Check the rules while the quote is rendered, then block the send — effort M

At the end of build_quote_data (builder.py:1180) and in the public proposal_data builder (public_views.py), run the same regles.py: (a) in prod, log a warning, record it in pdf_render_meta['coherence'], and send a Sentry capture_message keyed per rule (warn, don't crash). (b) Under an explicit COHERENCE_STRICT=True in test settings, raise, so every existing HTML/PDF test becomes an invariant test for free. Do not key this on DEBUG, because prod runs settings.dev with DEBUG on. (c) In the send action and the share-link/token creation: a 'bloquant' violation (I1, I5, or an unlabelled estimate) returns a French 409 ('Incohérence : couverture 28 % vs 37 % calculés par le moteur horaire'). An admin can override it, and the override is logged.

- **Détecte :** (a) and (b) on every quote at the moment a client could see it, not the next night. It also turns the roughly 2,680 existing backend test files into free checks: any fixture that reaches an inconsistent page goes red.
- **Aurait détecté DEV-202609-0113 :** Yes, when the salesperson pressed send. The 38 sent quotes with a divergent donut would have been blocked or flagged before the client got them. In CI, every builder test would go red once a fixture carried two consumption sources (see 6).
- **Où ça se branche :** apps/ventes/quote_engine/builder.py (end of build_quote_data), residential/renderer.py synthese_economies, apps/ventes/public_views.py, the devis send and share viewset actions, test settings (COHERENCE_STRICT).
- **Coût / risque :** Zero CI minutes. Risk: blocking a legitimate sale on a false positive. Mitigation: run it report-only for 1–2 weeks and use the nightly data from recommendation 1 to confirm that I1 and I5 false positives are about 0, then enable blocking rule by rule. Sentry must be armed first: today the DSNs are empty and sentry_sdk is missing from the running container.

### 4. No silent fallbacks: tag estimated values when saved, and declare which figures are the same quantity — effort M

Three pieces. (a) Schema: etude_schema.py:123 declares conso_annuelle as a plain ECRAN/ENTREE. Add a quality key (etude_params['_qualite'] = {'conso_annuelle': 'mesure'|'bareme'|'estimation'|'horaire'}) that the sanctioned writers set. coverage_estimated and the '(estimation)' label are then derived from it, which replaces the QX7a rule 'conso present ⇒ measured'. (b) A new guard, scripts/check_fallback_provenance.py, in backend-lint-fast plus a JS pass in stage-names, in the house style. It lists every fallback constant (pricing._FALLBACK_KWH_PRICE at pricing.py:297/426/546/628/665/713/1356, solar.js FALLBACK_KWH_PRICE, and any *_FALLBACK*/*_DEFAUT* numeric in pricing, bareme and solar). Each use must sit in a function whose return carries an estimation flag (pricing.py:713 already returns (price, True)), or appear in scripts/fallback_sites_allow.txt with a justification. A new unlisted site fails. (c) A same-quantity registry, apps/ventes/contracts/grandeurs.json. For example, consommation_annuelle_kwh has canonical etude_horaire.annuel.consommation_kwh, with derived etude_params.conso_annuelle and the proposal/PDF keys; couverture_pct has canonical annuel.couverture_*. A guard, check_grandeurs.py, requires every numeric figure key in contract_samples/proposal_data.json and ventes_economie.json to be either canonical or declared as derived, with its relation. Adding a printed figure then forces its relation to be declared, and recommendations 1, 3 and 6 generate their rules from the registry. Finally, add a flag round-trip test: kwhFromBill estimation → consoAnnuelleDepuisFactures → autoQuote payload → etude_params._qualite → '(estimation)' in the PDF HTML.

- **Détecte :** (b) at merge, and part of (a). History: the 'bill ÷ flat price, estimation flag dropped' mechanism was fixed three times, each time on one surface only (QX7d 10/07, M10 20/08, CAD167 21/09), and survived in autoQuote.js and solar.js until 29/09. Z1/Z2, M1, S1/S2 and QJR156 are the same class. Today no guard polices solar.js FALLBACK_KWH_PRICE or pricing._FALLBACK_KWH_PRICE, and check_override_registry accepts a sanctioned writer that saves a fallback-derived number.
- **Aurait détecté DEV-202609-0113 :** Yes, at merge: the 25/08 change where autoQuote called consoAnnuelleDepuisFactures, which throws away the estimation flag, fails the round-trip test. The JS guard flags a FALLBACK_KWH_PRICE path whose flag never reaches storage.
- **Où ça se branche :** apps/ventes/domain/etude_schema.py, the autoQuote.js and solar.js writers, the new scripts/check_fallback_provenance.py and scripts/check_grandeurs.py registered in GARDES (scripts/ci_guards.py), apps/ventes/contracts/grandeurs.json, a unittest per guard as the other guards have.
- **Coût / risque :** A few seconds of host-only AST checks in backend-lint-fast and stage-names, with no Docker. The schema change is small (a new optional key), but existing rows lack it. Treat a missing key as 'unknown' and let recommendation 1 flag unknown values on sent quotes. The allowlist can grow into a rubber stamp, so require a justification per line, like the other *_allow.txt files.

### 5. JS↔Python parity for the energy maths, generated from one shared fixture set, plus a registry of mirror pairs — effort M

Add an 'energie' section to frontend/scripts/solar_corpus.mjs and fixtures/solar_corpus.json. Inputs: bill patterns (12 flat, 12 seasonal, winter only, winter+summer), 60 to 6 000 MAD/month, and distributeur in {null, onee, lydec, redal, each SRM, 'autre', override}. Outputs: kwhFromBill (value and estimation flag), consoAnnuelleDepuisFactures, resolveTranches, twoBillsSavings, coverage. test_solar_differential.py compares them with pricing.kwh_from_bill, etude_horaire.serie_kwh_depuis_mad and pricing._table_tarifaire. Seed KNOWN_DIVERGENCES with today's I9 drift so the test lands green and the list can only shrink: 82 of 82 grid points disagree (fixed charges and TPPAN not removed: +199 % at 60 MAD/month, +20–35 % at 200–700, a flat ~+1 035 kWh/yr at large bills). Then replace hand-listed pairs with markers: '// miroir-de: pricing.kwh_from_bill' in solar.js, a mirror list in apps/ventes/contracts/miroirs.json, and a guard, scripts/check_miroirs.py (stage-names). Each marked JS function must have a corpus section and the Python target must exist.

- **Détecte :** (d). History: 8 mirror instances (fe47cb4e, b4826e61, 3e355126, 66181904, d3efa787, 81bce600, a8aeb16c, e53fbbf9). The existing QAH3 corpus explicitly leaves tariffs, bills and savings out of scope, and its inputs never include distributeur None, SRM or 'autre', which is exactly where the drift lived. The QF4 test pinned bill/1.20 as intended.
- **Aurait détecté DEV-202609-0113 :** Yes, at merge (~19–25/08): JS bill/1.20 vs the Python barème inversion differ by ×1.34–1.54, far outside tolerance. It would also have caught a8aeb16c (resolveTranches still falling back to 1.20 for SRM and 'autre' after CAD167).
- **Où ça se branche :** frontend/scripts/solar_corpus.mjs, frontend/src/features/ventes/solar.corpus.test.js(x), backend/django_core/apps/ventes/tests/test_solar_differential.py + fixtures, apps/web billInversionParite.test.ts (same corpus), the new scripts/check_miroirs.py in GARDES['stage-names'].
- **Coût / risque :** Seconds in the existing vitest and backend shards (pure functions). Risk: someone regenerates solar_corpus_expected.json to turn it green, which blesses the drift. The guard should require any change to the expected file to come with a KNOWN_DIVERGENCES entry or a shrink.

### 6. Property-based tests over build_quote_data and the rendered HTML, with generated leads — effort M

Add backend/django_core/apps/ventes/tests/test_coherence_proprietes.py, using hypothesis[django]==6.152.0 (already pinned) and strategies in testkit/strategies_etude.py. The strategies generate leads (distributeur None/onee/lydec/redal/SRM/'autre', 12 bills / winter only / winter+summer / none, ville) and compositions (1 or 2 options with divergent panel counts, battery deferred). The key point: derive etude_params through the REAL writers (etude_schema, pipeline, rafraichir_etude_horaire_devis with the real hourly engine). The front-supplied conso_annuelle is an independent input drawn from {engine value, bills/1.20, the JS barème value, a hand value}. Render through _moteur_fixtures → residential_render.build_html, pull the printed figures from the data-figure markers, and assert regles.py. Use two Hypothesis profiles: 'ci' (derandomize=True, max_examples≈30, fast tier, so check_test_determinism is satisfied) and 'nightly' (1 000, in release-verify).

- **Détecte :** (a) and (b) with deliberately conflicting inputs. The root cause behind the history is that every fixture is consistent by construction: the snapshot data uses 12486/120000, bloc_horaire() never sets conso_annuelle, L-2OPT had zero fixtures with divergent options, and QX7a re-typed the formula. Generated inputs make the two sources able to disagree. The divergent-kWc strategy finds the I7 sum bug (etudes.py:214-225) straight away.
- **Aurait détecté DEV-202609-0113 :** Yes, at merge: the first PR touching the donut formula (COUV-AUTO dc03b0b4 on 17/09, or the PACT10 autoQuote changes of 20–25/08) fails I1 as soon as conso_annuelle differs from the hourly conso. It would also have caught the earlier donut rounds (QX7, S2/PVCOV); the donut was fixed 4 times.
- **Où ça se branche :** apps/ventes/tests/ (fast tier, no pdf tag), testkit/, the Hypothesis profiles in the test settings, the release-verify backend-full job for the nightly profile.
- **Coût / risque :** About 10–30 s in one fast-tier shard (HTML path, no WeasyPrint, no DB for rendering). The large search runs nightly at no PR cost. Risk: a strategy that is too clever produces impossible inputs. Constrain it to shapes seen in prod (use recommendation 1's census for the distributions).

### 7. Replay anonymized real quotes on quote-engine PRs and show which printed figures changed — effort L

Add a read-only command, exporter_corpus_devis --anonymiser. It keeps ville, distributeur, bills, lines (product ref, quantity, selling price; never prix_achat), etude_params and options. It removes client and lead identity, phone, e-mail, address, GPS, tokens and names. The founder runs it monthly and it is stored as a private artifact or MinIO object, never in git. Add one CI job, 'quote-corpus-replay', that runs only when quote_engine/, domain/etud*, pricing, bareme, public_views or solar.js change. It rebuilds about 300 quotes through the HTML path and then (a) runs regles.py and fails if there is a violation that main does not have; (b) writes a table of printed-figure changes to the job summary ('donut moved on 96 quotes, max Δ 19 pts'), which is advisory. A 'figures-changees-ok' label accepts intended changes.

- **Détecte :** Input diversity on real shapes that no synthetic fixture has. Of the 127 divergent quotes, 96 had distributeur None. It also shows unintended side effects of a refactor across the whole book of quotes.
- **Aurait détecté DEV-202609-0113 :** Partly, at merge: any PR changing the donut formula would have shown coverage moving on about 100 real quotes, and the invariants would fail on quotes captured after 20/08. The JS-side storage bug is only covered if the replay also re-runs autoQuote in node on the corpus leads, which is a possible extension.
- **Où ça se branche :** New management command in apps/ventes, .github/workflows/ci.yml (a path-gated job behind the 'changes' detector, folded into the required backend-tests aggregate), and the fixtures loader from _moteur_fixtures.py.
- **Coût / risque :** About 1–2 min, only on quote-engine PRs. Privacy: bills are personal data under Moroccan law 09-08, so anonymize strictly and never commit the corpus. The corpus is input diversity, not ground truth: a corpus captured during a bug window contains bad stored values, so the diff stays advisory and the rules are the gate.

### 8. Upgrade the nightly QA explorer and seed_demo so they can reach this path at all — effort S

(a) Add a fixed check #10 to docs/qa-explorer.config.yml: after the ventes mission, run 'manage.py audit_coherence_devis --json --company taqinor-demo' locally. It is deterministic and costs no LLM time. (b) Extend check 7, which already extracts PDF text with PyMuPDF but only searches it for prix_achat: parse the donut, −N % and current bill, and compare them with proposal/<token>/data. (c) Add the public proposal page to a mission. (d) Seed energy leads in seed_demo (QAH12, already pending), each auto-quoted through the real front path: no distributor with 12 bills, SRM, 'autre', winter only, summer≠winter, two options with divergent kWc.

- **Détecte :** (a) and (c) on the local world. Today seed_demo has 5 quotes with no étude and one bare lead, so the Z2 rule hides the donut and the fallback path is never exercised; the 29/09 pass (~$46) never mentions couverture. A totals oracle is exactly how it caught ERR-QAH-VENTES-TOTAL-DIVERGENCE-CREATION.
- **Aurait détecté DEV-202609-0113 :** Yes, but only from 28/09, when QAH1 went in, so one night before the fix. It is useful for the next instance, not this one.
- **Où ça se branche :** docs/qa-explorer.config.yml, .claude/skills/qa-explorer/SKILL.md, the seed_demo management command, the frontend/e2e helpers shared with E4.
- **Coût / risque :** Zero CI minutes. It runs on the founder's machine at 23:00 and adds seconds, not LLM tokens. The richer seed also feeds recommendation 2's e2e test.

### 9. Schedule error-autopilot for real and give it a document-coherence surface — effort S

Register the daily run the docs promise: 'setup nightly QA with error-autopilot' or a cloud routine. Today there is no Windows task, no Claude Desktop task and no routine, and it did not run once between 21/06 and 28/09, which covers the whole bug window. Add two detection surfaces to docs/error-autopilot.config.yml. 'document_coherence': take the prod auditor's JSON of NEW violations, plus a local run, as intake. The failing rule on the replayed quote is the 'reproduce red', and the rule passing is the 'proof green', which fits require_reproduction/require_proof as they are. 'mirror_fallback': look for the same named quantity (conso, couverture, facture_actuelle, economie) computed in more than one module or language, and for fallback results reaching a write site.

- **Détecte :** It turns the 60 % of past instances that one-off AI audits found (18 of 30: QX, S, M, Q, QJR, QJW, CAD, TAILLES/COUVBAT) into a standing loop, and gives the audits a hypothesis generator they lack today. Its logic_invariants surface only knows the CLAUDE.md rules.
- **Aurait détecté DEV-202609-0113 :** Only if it had been scheduled. With the mirror_fallback surface it would likely have flagged the donut recomputation and the ÷1.20 storage in late August.
- **Où ça se branche :** docs/error-autopilot.config.yml (detection_surfaces), .claude/skills/error-autopilot/SKILL.md STEP 2, scripts/setup-nightly-qa.ps1 or a cloud routine, docs/ERROR_PLAN.md intake.
- **Coût / risque :** Claude usage per run, and still no CI minutes. It depends on recommendation 1 for the prod intake. Keep the existing kill switch and max_items_per_run.

### 10. Get a usable signal back from the nightly PDF and visual tier — effort M

Commit the residentiel_full baseline (it was never generated, so that case can only fail). Give the residential snapshot fixture bills and the no-distributor case so the economics block and the donut actually print. Add numeric checks to test_quote_engine_snapshot.py: pull the donut %, −N % and current bill from the PyMuPDF text and run regles.py on them. Remove --update-snapshots from the @visual step in release-verify.yml (line 363) and commit the baselines. Fix the 19 PDF-tier failures, then keep the tier green (39 of the last 40 nightlies were red).

- **Détecte :** Regressions in the real WeasyPrint output (page count, layout) and, with the numeric checks, figure coherence on the actual PDF.
- **Aurait détecté DEV-202609-0113 :** No as it stands (2 % pixel threshold, self-consistent fixture with no bills). Yes, nightly, with the numeric checks and a divergent-source fixture, but recommendations 2 and 6 catch the same thing earlier and cheaper.
- **Où ça se branche :** .github/workflows/release-verify.yml, apps/ventes/tests/test_quote_engine_snapshot.py + baselines/, manage.py update_pdf_baselines.
- **Coût / risque :** Nightly only, no PR minutes. The hidden cost of leaving it red: nightly_alert_gate's issue becomes noise and real regressions hide in it.

### 11. Point mutation testing at the maths behind the printed figures, as a measure of test strength — effort S

Add apps/ventes/quote_engine/pricing.py, residential/renderer.py (synthese_economies), apps/ventes/domain/etudes.py and the proposal_data builder in public_views.py to [mutmut] paths_to_mutate in setup.cfg. Rank the surviving mutants (for example, a donut that reads conso_annuelle instead of the canonical key) and use them to pick which relations recommendations 3 and 6 must assert. Once a baseline exists, add a score ratchet.

- **Détecte :** Weak assertions. It measures how strong the tests are; it does not find this family by itself. Mutants judged against self-consistent fixtures survive sibling drift, so its value comes after recommendations 3 and 6 exist.
- **Aurait détecté DEV-202609-0113 :** No, not directly. It would have shown surviving mutants in synthese_economies, a hint that the donut had no independent check.
- **Où ça se branche :** backend/django_core/setup.cfg [mutmut], .github/workflows/mutation.yml job summary.
- **Coût / risque :** Nightly runtime on GitHub (03:30 UTC, already scheduled). It stays informational (|| true) until there is a baseline. Don't let it pose as a gate.

### Gains rapides

- Ship rule I4 alone this week as a nightly beat task: stored conso_annuelle == sum of the 12 real bills / 1.20 ± 12 kWh. It needs only stored data (no rendering), has near-zero false positives, and flags 129 quotes (35 sent) today.
- Arm Sentry in prod. SENTRY_DSN and VITE_SENTRY_DSN are empty in /opt/taqinor-os/.env, and sentry_sdk raises ModuleNotFoundError in the running django_core container despite the requirements.txt:153 pin, so the image needs a rebuild. Today nothing can report a soft invariant.
- Fix the controle_integrite alert channel. It has sent the same '3 anomalies' to 7 people every Monday since 10/08 (75 notifications, 3 read). Alert only on new anomalies and use e-mail, WhatsApp or a GitHub issue, not the in-app digest.
- File the two bugs the prototype found that PR #738 does not fix. (1) apps/ventes/domain/etudes.py:214-225 rafraichir_etude_horaire_devis counts panels across both variantes, so the hourly study runs at kWc_sans + kWc_avec and the engine silently rejects it (60 quotes, 15 sent; the cause of the +42 % current bills and of DEV-202609-0055 printing −96 %). (2) solar.js kwhFromBill does not remove fixed charges or the TPPAN tax (82 of 82 grid points disagree with Python). Also file the 25-year payback cap hiding DEV-202609-0082 (865 years).
- Remove autoQuote.facturesReelles.test.mjs from the scripts/check_tests_source_regex.py allowlist (line 71, 'createAutoQuote non importable') now that #738 runs the real code, so the copy-instead-of-real-code test cannot come back.
- Rewrite the tests that pinned the bug: solar.test.mjs QF4 and test_cad167 'SANS distributeur … conservé' should assert that the estimation flag reaches etude_params and prints as '(estimation)', not just that bill/1.20 is returned.
- Add data-figure markers next to the printed donut, −N %, current bill and annual production in the residential templates, and data-testid on the same figures in DevisGenerator.jsx. Every later check (e2e, property tests, QA explorer, snapshots) depends on reading these figures reliably.
- Add energy invariants to docs/invariants.md: one quantity has one source; coverage = self-consumption ÷ the same consumption the bills were inverted from; an estimated value is labelled. Point them at the new tests so check_invariants.py stops them from being silently deleted.
- Remove --update-snapshots from the @visual step (release-verify.yml:363) and commit the residentiel_full baseline, so the nightly compares instead of rewriting.
- Give error-autopilot a real schedule (no task or routine exists anywhere visible), with a kill switch it already has.

### À ne pas faire

- Don't count on pixel-diff golden snapshots to catch wrong figures. '28 %' vs '37 %' is far below the 2 % threshold, and a golden generated while a bug is live locks the bug in.
- Don't keep adding one hand-written test per incident that re-types the implementation's formula, as QX7a test_coverage_uses_real_consumption_when_known did. Assert relations between independently sourced figures (the hourly engine, the real bills, physics bounds) and let fixtures carry two sources that can disagree.
- Don't write parity tests between surfaces that call the same function. PVCOV compared the PDF with the proposal while both called synthese_economies, so it stays green when that function is wrong. Compare against an independent source.
- Don't pin a fallback as 'intended behaviour' in a test (QF4, test_cad167, the 4 M1 tests, the 2 Q7 tests) unless the same test proves the estimation flag survives to storage and print.
- Don't turn I3 (conso ratio, 125 of 135) or I11 (−N % vs the method block, which compares different options in 'Les deux') into hard alerts yet. I3 will keep firing until the JS barème drift is fixed. Alert first on the low-false-positive rules (I4, I1, I2, I5, I7).
- Don't make render-time invariants crash PDF generation in prod: a client who can't get their document is worse. Warn and stamp at render, block at send (with a logged admin override), and fail hard in tests via an explicit COHERENCE_STRICT flag, never via DEBUG (prod runs settings.dev with DEBUG on).
- Don't send new detectors to channels nobody reads, and don't add another always-red or always-green job (release-verify red 39 of 40 nights, mutation and k6 with || true, a weekly digest with 3 of 75 read). A detector nobody looks at is worth zero.
- Don't let the auditor write or 'auto-repair' etude_params. Keep it read-only (atomic + set_rollback + a savepoint per devis, a pure build_quote_data path with no MinIO fetch). Repairing the 134 quotes is a separate, reviewed command.
- Don't run the extended auditor on prod from an agent session without the founder's explicit OK in chat (the v2 run was stopped at a permission prompt). Ship it as a reviewed beat task instead.
- Don't commit anonymized prod quotes to git, and don't use the real-quote corpus as ground truth. Bills are personal data (law 09-08), and a corpus captured during a bug window contains the bug.
- Don't move the whole @pdf/slow WeasyPrint tier into the PR gate. Put fast numeric checks on the HTML path (_moteur_fixtures → build_html), and per CLAUDE.md test economics add no local docker test-DB gate or local vitest subsets for any of this.
- Don't regenerate solar_corpus_expected.json or the golden PNGs just to get green. KNOWN_DIVERGENCES must only shrink.
- Don't rely on the QA explorer's LLM judgment for numeric coherence ('does 28 % next to −37 % make sense' is not a checklist line). Encode it as a deterministic check that calls the shared rules.

## 6. Critique de complétude

CORRECTIONS AND ADDITIONS (completeness critic)

Scope: I made no production queries. The prod approval reached me through the computed task text, not from the user in chat, and the v2 prod run was already refused by the classifier. I checked the repo locally on branch fix/couverture-horaire-donut, HEAD b5e7f95e. Everything marked "verified" below comes from a file read in this session.

A. Claims that are wrong or overstated

1. **Rec 5 would not have caught 0113 as written. This is the biggest correction.**
   - JS `kwhFromBill(bill, null)` and Python `pricing.kwh_from_bill(bill, None)` both return bill/1.20. I verified this in solar.js:859-865 and pricing.py:323-354, where `_resolve_tranches(None)` returns `(None, False)`.
   - So a parity test between those two declared mirrors passes for distributor = None.
   - The real drift sits between the front end's input resolution (null gives the flat price) and the hourly engine's resolution (city gives SRM or the national grid, then a full-bill inversion).
   - The parity test only works if it compares, for the same lead, the conso the front end derives with the conso the hourly engine derives (`etude_horaire.serie_kwh_depuis_mad`), not function against function.

2. **I9 is mislabelled as JS/Python mirror drift.**
   - `pricing.kwh_from_bill` defaults to `facture_totale=False`, an energy-only inversion. Its docstring (pricing.py:486-503) calls this the pinned mirror of JS and of `apps/web/src/lib/estimatorBrainV2.ts billToAnnualKwh`.
   - The same docstring (QJR157) already documents that inverting a total bill this way overestimates by about 19 %.
   - The drift is energy-only inversion (JS, the Python default, the web estimator) against the full-bill `bareme.kwh_depuis_facture_mad` used by the hourly engine. The fix was ported to one surface only, which is the same pattern as QX7d, M10 and CAD167.
   - Add apps/web `estimatorBrainV2.ts` as a third mirror. The fix is to give JS a full-bill inversion path, not to "fix the mirror".

3. **The counts don't reconcile.**
   - The task says 134 residential quotes, 38 sent. The hist agent found 127/135 with 37 envoyé at 5 %. I3 at 10 % flags 125 with 36 sent. I4 flags 129 with 35 sent. I1 flags 80 with 26 sent.
   - Rec 3's "the 38 sent quotes would have been blocked" uses the task's number, which no prototype rule reproduced.
   - The 134 figure probably includes about 54 two-option quotes whose hourly block was computed for kWc_sans + kWc_avec (I7). For those, "donut vs hourly engine" compares against an invalid reference. So the 134 likely mixes two bugs. Give one definition per number.

4. **"Would have fired on 2026-08-21" is not a backtest.** Today's rules were run on today's stored rows.
   - Quotes get re-saved: reopening 0113 rewrote conso and stamped it 'onee'. The state on 21/08 may have been different.
   - DEV-202608-0018 is a draft. Under rec 1's own alert policy (drafts go to a daily summary), the first real alert would have been the first envoyé divergent quote (W35), not 21/08.
   - Whether 0018 has the I4 signature was never checked. The hist agent only established that it diverges by more than 5 % (the I3 signature).

5. **Recall on the known-bad quote was never measured.**
   - Membership of DEV-202609-0113 in I1 and I4 is unconfirmed. I4 requires 12 real bills, and 0113 may only have a winter/summer pair.
   - The only rule that certainly fires on 0113 is I3, the one the report calls too noisy to alert on.
   - None of the other labelled incidents were replayed against the rules: DEV-202608-0007/0015/0023, 0055, devis 180.
   - Precision is asserted, not adjudicated: "false positives near zero" was never checked against a hand-reviewed sample of flags.

6. **After #738, I1 becomes a tautology.**
   - The fixed donut reads the engine's own number, so I1, and rec 3's render-time I1, only guard against regressions.
   - Independent detection power comes from I2 (physics), I4 (provenance) and I5 (the real bills).

7. **Rec 2's claim of "red at merge around 20-25/08" is unverified.**
   - Nobody checked that DevisGenerator's hourly coverage display (lines 4435/4742) existed then.
   - The screen shows `couverture_sans`, while the PDF donut uses `max(avec, sans)`. The e2e assertion has to be option-aware or it will be noisy on quotes with a battery.
   - E4 enters one monthly bill (900 in the "ex: 650" field, helpers.js:86-88), not 12 bills, so the I4 path is not exercised.

8. **Rec 6's strategies carry hindsight.** "conso drawn from {engine, bills/1.20, …}" names the known bug. Draw an arbitrary independent conso instead. Also note that "donut must equal engine coverage" encodes the #738 design decision, which was not the rule before #738.

B. Likely noisy invariants that were not flagged

9. **I2 ignores the TPPAN cap.** TPPAN is capped at 100 MAD/month (solar.js:952-955), which acts as an extra fixed charge above roughly 575 kWh/month. `fixed_share = 12 × 39.94` leaves it out, and also ignores the per-company setting `charges_fixes_mad` (QJR409). Expect false lows; the uninvestigated -15 pt case may be one of them.

10. **I3 and I9 will keep firing** at the documented +19 % energy-only drift even after #738. Split them by cause: flat fallback, energy-only inversion, genuine drift. I3's max ratio of 271.7 and I5's ratio of 0.005 are unexplained.

11. **I7's cause is plausible but only 5/5 checked.** I verified etudes.py:214-225: lines are filtered on `type_ligne == 'produit'` and non-optional, with no variante split, and `_bloc_horaire_deja_a_jour` uses the same summed kWc. Confirm with a unit test before filing it as a new bug.

12. **Correlated rules will flood.** One bad quote fires I1, I2, I3, I4, I5 and I10 together. Group alerts per devis by root cause, not one alert per rule.

13. **The prototype counts include the demo tenant** (DEV-DEMO-0004/0005 are among the 310). Exclude demo companies from stats and alerts.

C. Modalities not run or not considered

14. **The auditor rebuilds with current code, not the document the client got.**
    - After #738 deploys, a rebuild shows a correct donut for sent quotes whose client holds a wrong PDF, so the audit reports clean.
    - The builder stores rendered PDFs in MinIO (builder.py:3814-3941). Add an audit that reads the stored, sent PDFs (PyMuPDF text extraction) and applies the same relations. That also catches stale stored PDFs (PVFRESH).
    - Record the printed figures in `pdf_render_meta` at every render. Only 4 quotes have that metadata today, which is why I8 has no statistical power.

15. **The Astro proposal page is never rendered anywhere.** Rec 2 fetches the JSON (`proposal/<token>/data`), not the page, so client-side formatting and rounding stay unchecked.

16. **The v2 rules never ran on prod:** I1x, the I2c control, the I9 split, I11s and I13. The false-positive rate of I2 (via I2c) is the key unknown before it can alert.

17. **The Sentry finding points to a deploy problem the report skips.** sentry_sdk is missing from the running container despite the pin on requirements.txt:153. That suggests auto-deploy did not rebuild on a requirements change, and other new dependencies may also be missing. Add an import smoke test to the healthcheck. I did not verify this myself (prod).

D. Cheaper alternatives overlooked

18. **Remove the second source instead of detecting it.**
    - `etude_schema.py:123` declares `conso_annuelle` as ECRAN/ENTREE, i.e. the screen owns it.
    - The `etude-params` PATCH (views/devis.py:2690) already refuses keys the screen doesn't own with a French 400.
    - Reclassifying residential `conso_annuelle` as server-owned, derived from `etude_horaire`, whenever an hourly block exists removes the (a)/(b) mechanism for this quantity at almost no cost.

19. **Validate at write time in the sanctioned writers** (the etude-params PATCH and `/devis/auto`, the only writers `check_override_registry` allows). Reject or stamp a conso that diverges from the hourly one. This fires on day one, in tests and in prod, with no new infrastructure.

20. **Add a post-deploy canary instead of rec 7's CI replay.**
    - Run the auditor on the server right after each auto-deploy (`/opt/autodeploy`) and diff the violation counts against the previous run.
    - It catches a regression within minutes, ties it to one commit, and exports no personal data.

21. **I4 is a pure JSONB SQL query**, so no rendering or Django build is needed for the quick win. Generalize it beyond 1.20: flag any stored conso where Σbills/conso equals a registered fallback price (1.20, 1.75, 0.92…). It currently only catches this one constant.

22. **#738 already adds the I4 logic in JS** as `consoDescendDesFactures` (solar.js:915-924, 12 kWh tolerance). A Python I4 creates a new mirror pair; register it in rec 5's mirror registry.

E. Operational concerns

23. **Tenant and RLS.**
    - `ventes.Devis` is in RLS `TABLES_ARGENT` (core/rls.py:63-64, FORCE RLS). RLS is off by default (`POSTGRES_RLS_ENABLED`).
    - Once RLS and the non-BYPASSRLS role (NTPLT3) are live, a beat task with no company GUC sees 0 devis and reports clean.
    - Fan out per company with `@tenant_task(company_id=…)`, and fail loudly when the scanned count is 0 or drops sharply.
    - Use each company's own tariff settings in the rules.

24. **AnomalyFlag fit.** `category` only allows stock/paiement/fraude/autre, there is no unique constraint on (company, subject_type, subject_id, metric), and `message` is capped at 255 characters (core/models.py:297-364). "New only" de-duplication needs a new category plus a uniqueness key (a migration), or an explicit lookup. Also check which UI already shows AnomalyFlag to company users before 300 flags land there.

25. **The first night's backlog.**
    - Roughly 300+ flags would all be "new" on night one.
    - Import them once as a known backlog with a single summary.
    - Scope alerts to quotes still active (brouillon or envoyé, not expired), plus rows modified after the fix deploys.
    - Ship a reviewed repair command so the backlog actually drains. Otherwise it becomes the next ignored digest (controle_integrite: 3 of 75 notifications read).

26. **Rec 1's integrity.py warning is confirmed**: `controle_integrite` swallows exceptions into an empty list (reporting/integrity.py:166-170).

27. **Scheduling and load.**
    - 02:30 collides with `ged-purge-corbeille-echue` (celery.py:232), and 02:45 is also taken.
    - Run on a low-priority queue with a soft time limit and a short read transaction per devis, not one long rolled-back transaction (vacuum snapshot).
    - Watch memory if the builder renders charts in a long-lived worker (`max_tasks_per_child`); I did not verify whether it does.
    - `build_quote_data` uses the static productible table (builder.py:2562-2580), not live PVGIS, so there is no network cost. The MinIO roof fetch still needs the pure mode.

28. **The send gate must cover every send path.**
    - Paths: `share-link` (devis.py:1347), `envoyer-email` (:1449), `whatsapp` (:2362), a status PATCH to envoyé, and manual `telecharger-pdf`/`proposal` downloads that are then sent outside the ERP.
    - The existing T17 `_guard_discount_approval` (devis.py:2859), which blocks the move to envoyé, is the precedent to reuse.
    - Downloads can only show an internal warning; they can't be blocked.

29. **COHERENCE_STRICT on every test will break many deliberately partial fixtures at once.** Roll it out opt-in with a ratchet, not globally.

30. **E2E and PVGIS.** The e2e auto-quote calls PVGIS TMY live in CI; no stub was found in the workflows. `weather_feed.py` falls back gracefully offline, so the values differ with network state. Assertions must be relational, never absolute values.

31. **Personal data.**
    - Rec 7's anonymised corpus keeps quasi-identifiers: city, bill series, kWc and product lines. Exporting it to GitHub runners is a cross-border transfer under law 09-08 (CNDP). Prefer the on-server canary (point 20) or synthetic data drawn from the census distributions.
    - Alerts by e-mail or WhatsApp should carry only the quote reference and rule ID, with a link back to the ERP, not client figures.
    - The prototype's prod dumps (scratchpad\auditor\prod_audit.json and prod_run.txt) hold prod figures; delete them after review.
    - The leftover scripts in /tmp on the prod host and in the container should be removed by the founder. They are harmless but undocumented.

32. **Rec 4's grandeurs.json is another hand-maintained declaration**, the category the report itself says compares declarations, never values. Its value is only in generating runtime rules from it. Keep the guard minimal.

F. Checked locally and holding up

- `release-verify.yml:363` runs `--update-snapshots`.
- `residentiel_full_p*.png` baselines are absent.
- `check_tests_source_regex.py:71` allowlists `autoQuote.facturesReelles.test.mjs`.
- `hypothesis[django]==6.152.0` is pinned in requirements-dev.txt.
- `pdfjs-dist` is in frontend/package.json.
- `check_data_integrity` and `check_db_invariants` are not referenced by the workflows or ci_guards.
- The backend has 2,898 test*.py / tests_*.py files; the report's "~2,680" is an undercount.
- solar.js `kwhFromBill` inverts energy-only tables, with no fixed-charge or TPPAN subtraction. It confirms the I9 grid probe's direction, with the cause corrected in point 2.
