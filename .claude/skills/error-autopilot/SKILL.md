---
name: error-autopilot
description: >-
  Best-in-class daily error-detection autopilot for TAQINOR OS. Sweeps the whole
  repo across a wide defect taxonomy (tests/coverage, static analysis & types,
  security SAST, dependency CVEs, concurrency/atomicity, data-integrity &
  migrations, multi-tenancy, domain-logic invariants, performance/N+1, error
  handling, frontend runtime, web/Astro, deploy hardening) using a three-phase
  parallel pipeline — read-only scout fan-out → isolated git-worktree verify-workers
  → adversarial review. For EVERY candidate it reproduces the bug (red) and PROVES a
  fix turns it green with no regression, scoring severity + confidence, before
  filing it as a tested correction item in docs/ERROR_PLAN.md (OS) or
  docs/WEB_ERROR_PLAN.md (web). No guesses, no half-work. Built to run unattended by
  a Claude Code Routine (docs/error-autopilot.md); honour the kill switch in
  docs/error-autopilot.config.yml.
---

# Error-Autopilot — best-in-class verified-error intake

You are running the error-autopilot. Your job is **not** to fix code and merge
fixes. Your job is to **detect every kind of real, reproducible error, prove a
fix works for each, score it, and file it** as a tested correction item in the
right error-plan file. Landing the fixes is done later by `work on error plan`
(OS) and the web error-plan drain.

The bar is **zero false positives and broad coverage**: be exhaustive about
*where* and *how* you look (Step 2 taxonomy), and ruthless about *what you file*
(Step 3 proof gate). Treat this whole file as your runbook — it is self-contained
because you run unattended. Obey every `CLAUDE.md` non-negotiable rule always.

---

## STEP 0 — Preflight, baseline & kill switch (every run)

You may be launched by a cloud Routine (fresh clone) or a local Desktop
scheduled task (your working copy) — behave identically either way.

**Preconditions (safe abort, make no changes if any fails):** you are inside a
git checkout of `taqinor/taqinor-os`; the primary working tree has no *unrelated*
uncommitted changes (if it does, stop and report — never fold a human's
in-progress edits into the run); and `git`/the shell are usable. If a
precondition fails, print one line saying why and end without writing anything.

1. Read `docs/error-autopilot.config.yml`.
2. **If `enabled: false` → STOP immediately.** Make NO file change, NO commit,
   NO merge. Print exactly `ERROR_AUTOPILOT: DISABLED (config flag off)` and end.
   (The Routine's own pause toggle is the other off-switch; either off → stop.)
3. Load the knobs: `max_lanes`, `targets` (os / web), `detection_surfaces`,
   `verification` gates, `min_confidence`, `max_items_per_run`,
   `transient_analyzers`, and confirm `output: self-merge-to-main`.
4. Read `docs/ERROR_PLAN.md`, `docs/WEB_ERROR_PLAN.md`, `CLAUDE.md`,
   `docs/CODEMAP.md` so you know the backlog, the rules, and the code map.
5. **Capture a clean baseline on the starting `main` tree** (so newly-found
   failures are attributable and you never refile a pre-existing/known state):
   run the four required checks once — backend-lint (`flake8 backend
   --max-line-length=120 --extend-ignore=E501 --exclude=migrations` + `lint-imports`),
   backend-tests (`python manage.py test apps`, Postgres + MinIO like CI),
   frontend-lint (`npm run lint`), stage-names (`python scripts/check_stages.py`
   + `python scripts/codemap_fingerprint.py --check`), plus web `npm run check`
   & build. Record what is already green; any check that is *already red on a
   clean main* is itself a real error to file (with the fix that greens it).
6. Compute next free ids per prefix from the backlog (today: OS → ERR114, web →
   WEBERR1).

The two areas **never overlap**:
- **OS → `docs/ERROR_PLAN.md`** (`ERR`): everything under `backend/` (Django
  `django_core` + FastAPI `fastapi_ia`) and `frontend/` (the React OS app).
- **Web → `docs/WEB_ERROR_PLAN.md`** (`WEBERR`): everything under `apps/web/`.

---

## STEP 1 — The parallel pipeline (three phases, maximum safe parallelism)

Never scan top-down or single-threaded. Run a **fan-out → verify → review**
pipeline. Default engine: a dynamic workflow with a separate adversarial review
agent; fall back to lane-planned parallel worktree subagents (you review each
lane yourself) — **never a single serial one-at-a-time agent.** Keep every
subagent lean: hand it only its slice + this runbook; it returns a SHORT
structured summary (candidates / confirmed items), never a full diff, so your
orchestration context stays light across many waves.

### Phase A — DETECT (broad, read-only fan-out → candidate ledger)
Build a **Surface × Area matrix**: the Step-2 detection surfaces crossed with the
code areas (each backend app, the FastAPI service, frontend feature/page areas,
each `apps/web` area). Fan out **read-only scout subagents** (no worktree needed
for read-only scanning), area-major so each scout owns one area and sweeps every
applicable surface over it. In parallel, run the repo-wide analyzers once
(Step 2 / Appendix A) and route their hits into the same ledger. Each scout
appends **candidate** entries to a shared **candidate ledger**:

> `{cand-id, surface, area, location(file:line), hypothesis, repro-idea,
>  suspected-severity, suspected-confidence}`

Immediately drop candidates that dedup against the existing backlog or the
known-good baseline (Step 0.5). Rank the survivors **highest-severity ×
highest-confidence first**.

### Phase B — VERIFY (deep, isolated git worktrees, work-stealing)
Each surviving candidate → one **verify-worker in its OWN git worktree**
(`isolation: worktree`, so two workers never touch the same files). Assign by
**file-ownership lanes**: candidates whose fixes would touch the same files share
a lane and run in sequence; different lanes run concurrently up to `max_lanes`
(default 8, raised as high as the session sustains via `--max-lanes`),
**continuously refilled (work-stealing)** — a freed slot takes the next ranked
candidate immediately, never idling for a wave to finish. Each worker runs the
Step-3 proof gate and returns either a **CONFIRMED item** (with evidence, proven
fix, severity, confidence) or a **DROP** (with the reason it failed the gate).
`python scripts/plan_lanes.py docs/ERROR_PLAN.md` / `… docs/WEB_ERROR_PLAN.md`
shows the planner's lane view; for the audit also lane by source-tree ownership
since the backlog may be empty.

### Phase C — REVIEW (adversarial gate before anything is filed)
A separate reviewer agent re-checks every CONFIRMED item against this runbook:
the reproduction really fails without the fix and passes with it, no regression,
not a dup, severity + confidence justified, respects all rules, and the fix
isn't gated. **Only review-passed items are eligible to file.** Anything the
reviewer rejects goes back as a DROP or a re-verify.

### Budget & stop
Cap a run at `max_items_per_run` filed items (longest/riskiest lanes first; the
rest carry to the next run — the run is idempotent). Stop on queue-empty, the
item cap, or a usage/length cap; re-firing resumes cleanly.

---

## STEP 2 — Detection taxonomy (sweep EVERY enabled surface)

Cover each surface in `detection_surfaces`. For each: the technique/tools and the
signals to hunt. Tool commands are in **Appendix A**. Transient analyzers
(bandit/semgrep/ruff/mypy/pip-audit/osv-scanner/knip/vulture…) may be installed
**just for a run's detection pass when `transient_analyzers: true`** and the
environment allows it — they are **never added to the project's dependency
manifests** (that would be a gated change). When an analyzer isn't installable,
fall back to disciplined manual review for that surface.

**A. Tests & coverage.** Run all suites (Appendix A). Treat every failing test as
a candidate. For uncovered critical paths, *write a reproduction test* that
exposes a real defect. Use mutation testing on hot pure modules (money/decimal
math, references, solar/pompage sizing) to find missing/weak assertions, and
property-based tests (hypothesis) on pure math to find edge cases.

**B. Static analysis & types.** `flake8` + `lint-imports` (the CI gate) plus a
broader `ruff` ruleset (bugbear `B`, security `S`, comprehensions `C4`,
simplify `SIM`, `PERF`, `RUF`), `mypy`/`pyright` on typed surfaces; `eslint`
(`npm run lint`) + `tsc` (`npm run check`). Hunt: undefined names, shadowing,
unused/var-misuse, mutable defaults, broad excepts, `==` vs `is`, unreachable
code, type mismatches, missing `await`, React hook-deps mistakes.

**C. Security SAST.** `bandit` (Python) + `semgrep` (rulesets `p/security-audit`,
`p/owasp-top-ten`, `p/django`, `p/react`, `p/javascript`, `p/secrets`); secret
scanning (`gitleaks`/`trufflehog`) for committed credentials. Hunt the classes
already proven real in this repo and the OWASP top-10: SQL/NoSQL/command
injection, SSRF, IDOR / cross-tenant access, mass-assignment
(`fields='__all__'` + writable FK), missing authz on viewsets/endpoints, broken
JWT validation (missing `exp`/`aud`), CORS/`DEBUG` fail-open, stored/reflected
XSS (`dangerouslySetInnerHTML`, unescaped HTML in PDF/templates), CSV/formula
injection, insecure deserialization (`pickle`, `yaml.load`), path traversal,
open redirect, weak crypto, hardcoded secrets, prompt-injection paths into
write-capable tools.

**D. Dependency & supply-chain CVEs.** `pip-audit` (both `requirements.txt`),
`npm audit` / `osv-scanner` on `frontend` and `apps/web`, and the repo's
Dependabot advisories. File each exploitable known-vulnerable pin. (A safe
in-range patch bump that the proof gate greens is filable; a major/breaking or
new transitive bump is **gated** — see Step 6.)

**E. Concurrency & atomicity.** Read-modify-write without `select_for_update`,
check-then-create races (unique constraint → 500), non-atomic multi-row writes,
idempotency under Celery `acks_late`+retry, signal/automation recursion. Prove
with a concurrency repro test where feasible.

**F. Data integrity & migrations.** `python manage.py makemigrations --check
--dry-run` (a missing migration is a real error), `manage.py check` /
`check --deploy`; Decimal truncation via `int()`/bad rounding, money-rounding
drift, `unique_together`/constraint gaps (e.g. missing `company`), nullability &
default mismatches, range validators (GPS, %, TVA).

**G. Multi-tenancy.** Every viewset queryset filters by `request.user.company`;
`perform_create` force-assigns `company` (never from the body); FKs validated
against the company on **create AND update**; cross-app reads/writes go through
the target app's `selectors.py`/`services.py`, never its `models`/`views`.

**H. Domain-logic invariants (from `CLAUDE.md`).** Stage names only from
`STAGES.py`; quote/invoice status preservation; `/proposal` the only
client-facing quote-PDF path; Meta Ads campaigns born `PAUSED`; references via
`apps/ventes/utils/references.py` (never `count()+1`); pompage rules (no
inverter/battery, m³/jour only for curve pumps, never quote a price-less
product); never-reject/snap typed numbers on quote/parametres forms;
`prix_achat`/margin never client-facing.

**I. Performance.** N+1 queries (missing `select_related`/`prefetch_related`),
unbounded `.all()`/exports without pagination, unbounded request/file reads
(memory DoS), missing indexes on filtered FKs, O(n²) loops, React effect/render
storms and missing memoization.

**J. Error handling & observability.** Swallowed exceptions (`except: pass`,
`.catch(()=>{})`), silent empty-data on fetch failure (no error/retry state),
fail-open security/rate-limit guards, generic 500s leaking internals, **PII in
logs**, dishonest success status (e.g. `fail_silently` reported as delivered).

**K. Frontend runtime (OS React app).** Stale state snapshots, optimistic writes
without rollback/toast, missing async cancellation (late-response overwrite),
controlled-vs-uncontrolled input bugs, error-state vs empty-state confusion,
basic a11y (labels/roles/focus), French-message consistency (no raw
`JSON.stringify(err)` to users).

**L. Web / Astro (`apps/web`).** Redirect method preservation (301 vs 308 on
POST), hreflang/canonical/trailing-slash consistency, **lead-PII logging** in
workers, CAPI SHA-256 hashing before Meta, rate-limit/anti-spam on public
endpoints, CSP/security headers, secret handling, broken links, build warnings,
a11y/Lighthouse regressions.

**M. Config & deploy hardening.** Prod settings (`SECURE_SSL_REDIRECT`,
`SECURE_PROXY_SSL_HEADER`, HSTS, `SESSION/CSRF_COOKIE_SECURE`,
`CORS_ALLOWED_ORIGINS`), `DEBUG` fail-open, required-env-var presence checks,
docker/compose & Caddy/nginx drift, `manage.py check --deploy` warnings.

Add any surface not listed if you can detect a real, reproducible defect class —
the taxonomy is a floor, not a ceiling.

---

## STEP 3 — Proof gate: severity, confidence, and zero false positives

Every item must clear **all** enabled `verification` gates inside its worktree:

1. **Reproduce (red)** — `require_reproduction`: a test/check that fails
   *because of* the bug. If you cannot make it fail, the bug is not real → DROP.
2. **Fix** — the smallest correct fix in that worktree.
3. **Prove (green)** — `require_proof`: the previously-red signal now passes.
4. **No regression** — `require_no_regression`: the four required CI checks stay
   green (web items also: tsc + vitest + astro build). A fix that breaks
   anything else is not a fix → DROP or re-do.
5. **Flake guard** — if `run_proof_twice`, run the red→green proof twice (and on
   a clean re-applied worktree) so the result is deterministic, not flaky.
6. **Score** — assign **severity** (Appendix B) for BUILD-QUEUE placement and
   **confidence** (Appendix C). File only items at or above `min_confidence`
   (default `high`). Lower-confidence findings are DROPPED, not filed as guesses.
7. **Record** — file:line, defect, the exact reproduction, the **proven fix**
   (concise patch sketch so the drain re-applies it directly), and the detection
   surface/tool that found it.
8. **Discard the fix worktree.** The autopilot files the *item*, not the code fix.

Style nits, hypotheticals, "could maybe", and preferences are **not** errors.
When in doubt, DROP.

---

## STEP 4 — Dedup & number

Skip any candidate already covered by an existing `ERR`/`WEBERR` item (open,
done, or gated) — match on file + symptom. Assign the next free id per prefix.

---

## STEP 5 — File the verified items

Append each review-passed item to the correct file under the correct **severity**
heading in the BUILD QUEUE (Critical / High / Medium / Low), matching the
existing one-line style and carrying its proof:

```
- [ ] ERR114 — [app] <defect> (`path/to/file.py:line`): <symptom / impact>. FIX (verified): <proven fix> — repro: <failing test/check>; found via: <surface/tool>.
```

- OS errors → `docs/ERROR_PLAN.md` (`ERR`). Web errors → `docs/WEB_ERROR_PLAN.md`
  (`WEBERR`). Gated items → the GATED section of the matching file with
  `[BLOCKED: <reason>]`.
- Append one dated line to each touched file's **AUTOPILOT INTAKE LOG**:
  `- YYYY-MM-DD — filed N verified items (ERRxxx–ERRyyy): <themes; surfaces swept>.`

If a run confirms **nothing**, file nothing, make **no commit / no merge**, and
report "no new verified errors". Never pad the backlog.

---

## STEP 6 — Gated fixes (don't pretend they're landed-ready)

If a verified fix would require a **destructive/schema migration, a new external
dependency or a breaking/major version bump, an auth or cost policy change, a new
Cloudflare/worker secret, or anything conflicting with a `CLAUDE.md`
non-negotiable**, file it under **GATED** with `[BLOCKED: <reason>]` and the
decision needed — never under the normal queue as if drain-ready. Safe in-range
security patch bumps that fully green the proof gate may be filed normally
(noting the version), since landing still goes through the gated drain + CI.

---

## STEP 7 — CODEMAP fingerprint (OS file only)

`docs/ERROR_PLAN.md` is in the plan-fingerprint surface, so **iff you added/
changed `ERR` task lines**, in the SAME commit as the edit: refresh §10 "Plan
status" of `docs/CODEMAP.md` (paste `python scripts/codemap_fingerprint.py
--print-plan-status`, update the `Generated from commit` stamp + cross-check
notes), run `python scripts/codemap_fingerprint.py --write`, then confirm
`--check` and `python scripts/check_stages.py` are green.
`docs/WEB_ERROR_PLAN.md` is **not** in the fingerprint surface — web-only changes
need no CODEMAP refresh. You change no models/endpoints/routes, so the
**structure** fingerprint does not move — do not regenerate the CODEMAP body.

---

## STEP 8 — Land it (one sync-safe self-merge to main)

`output: self-merge-to-main`. Fold every worktree branch's plan-file commits into
one `dev`. Make the single merge sync-safe: (1) integrate the latest
`origin/main` into `dev` (merge it in — never rebase published history, never
force-push); (2) recompute the CODEMAP structure fingerprint if integrating
`main` moved the structural surface; (3) run the four required CI checks once over
the whole batch (with MinIO) and self-merge `dev` → `main` **exactly once** (one
merge commit, 0 approvals, no per-item PR/merge); (4) if the push is rejected
because `main` advanced, repeat fetch → integrate → (refresh fingerprint) → CI →
push. Keep branch protection exactly as configured. The merge auto-deploys; never
run a deploy command.

---

## STEP 9 — Report & status

Report once, in plain language, including: the **pipeline plan** (scouts run,
surfaces swept, lanes in parallel), candidates found vs filed vs dropped (with a
one-line why-dropped tally), and the exact new ids filed into each file. No diffs,
no hashes. Then print both status lines for the headless loop:
- `ERROR_PLAN_STATUS: EMPTY` / `MORE` (from `docs/ERROR_PLAN.md` `[ ]` count).
- `WEB_ERROR_STATUS: EMPTY` / `MORE` (from `docs/WEB_ERROR_PLAN.md` `[ ]` count).

---

## STANDING SAFETY RULES (always)

- Obey every `CLAUDE.md` non-negotiable (Odoo JSON-2 only; `STAGES.py` stage
  names; Meta Ads campaigns paused; `/proposal` the only client quote PDF path;
  scraper policy). **Never run scrapers**, never start external scraping.
- Never weaken/bypass/add approvals to branch protection. Never force-push. Never
  overwrite a concurrent run's commits.
- `prix_achat`/margins never appear in any output.
- Transient analyzers are for detection only — **never** add them to
  `requirements.txt`, `package.json`, or any committed manifest.
- The autopilot only writes `docs/ERROR_PLAN.md`, `docs/WEB_ERROR_PLAN.md`, and
  (for OS intake) `docs/CODEMAP.md` §10 + its plan fingerprint. It does **not**
  land code fixes — every filed item is verified, its fix left for the drain.
- Be exhaustive in detection, ruthless in filing. No ceremony, no unrequested
  adjacent work.

---

## Appendix A — Detection tool cheat-sheet (commands)

Required CI checks (the merge gate and the no-regression bar):
- backend-lint: `flake8 backend --max-line-length=120 --extend-ignore=E501 --exclude=migrations` and `lint-imports` (needs `import-linter==2.11`)
- backend-tests: `python manage.py test apps` (Postgres + MinIO env, like CI)
- frontend-lint: `cd frontend && npm run lint`; tests: `node --test --experimental-test-coverage "src/**/*.test.mjs"` and `npm run test:coverage`
- web: `cd apps/web && npm run check` (tsc) + `npm run build` (astro) + vitest
- stage-names: `python scripts/check_stages.py` and `python scripts/codemap_fingerprint.py --check`

Deeper analyzers (transient install for detection only; skip if unavailable):
- Python: `ruff check backend`, `bandit -r backend - q`, `mypy backend` / `pyright`,
  `pip-audit -r backend/django_core/requirements.txt` and `… fastapi_ia/requirements.txt`,
  `vulture backend`, `python manage.py makemigrations --check --dry-run`,
  `python manage.py check --deploy`
- JS/TS: `npx semgrep --config p/security-audit --config p/owasp-top-ten --config p/react --config p/django .`,
  `npm audit --omit=dev` (in `frontend` and `apps/web`), `npx osv-scanner -r .`,
  `npx knip` / `npx depcheck`
- Secrets: `gitleaks detect` / `trufflehog filesystem .`
- Edge cases: `hypothesis` property tests on pure math; `mutmut`/`cosmic-ray` on hot modules

## Appendix B — Severity rubric (BUILD-QUEUE section)
- **Critical** — data loss/corruption, cross-tenant read/write, auth bypass /
  privilege escalation, RCE/injection, secret/PII exposure, money miscalculation.
- **High** — security/IDOR with preconditions, race corrupting data, broken core
  workflow, silent financial/stock drift, DoS.
- **Medium** — incorrect-but-recoverable behaviour, missing validation, poor
  error handling with user impact, perf problems under load.
- **Low** — minor correctness/UX, cosmetic, defensive hardening with low impact.

## Appendix C — Confidence rubric (file only ≥ `min_confidence`, default high)
- **high** — reproduced red→green with a deterministic test/check and no
  regression (the only level filed by default).
- **medium** — strong static/SAST signal but the repro is environment-dependent
  or partial → keep verifying or DROP; do not file at default settings.
- **low** — heuristic/uncertain → DROP.
