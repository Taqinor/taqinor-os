# Error-Autopilot — operator guide

A daily, unattended run that scans both areas of this repo for **real** errors,
**proves a fix actually works** for each, and files the verified ones as tested
correction items:

- OS errors (backend + `frontend/`) → [`docs/ERROR_PLAN.md`](ERROR_PLAN.md)
- Web errors (`apps/web/`) → [`docs/WEB_ERROR_PLAN.md`](WEB_ERROR_PLAN.md)

Fixing those items stays the job of `work on error plan` (OS) and the web
error-plan drain — the autopilot only fills the backlog with high-confidence,
already-verified items, then self-merges that plan update to `main`.

## The pieces (all committed)

| File | Role |
| --- | --- |
| `.claude/skills/error-autopilot/SKILL.md` | The brain — the full scan → reproduce → **verify fix** → file → self-merge runbook. Uses the "work on the plan" parallel worktree-subagent model. |
| `docs/error-autopilot.config.yml` | Settings + **kill switch** (`enabled`), lane ceiling, and the area→file map. |
| `docs/ERROR_PLAN.md` / `docs/WEB_ERROR_PLAN.md` | Where verified items land. Each has an **AUTOPILOT INTAKE LOG** the run appends to. |

## What it detects (a wide, tunable taxonomy)

It doesn't just run the test suite. Each run sweeps a **Surface × Area matrix**
across the whole repo: tests & coverage, static analysis & types (flake8/ruff,
eslint, tsc, mypy), **security SAST** (injection, IDOR, SSRF, XSS, auth bypass,
secrets — via bandit/semgrep), **dependency CVEs** (pip-audit / npm audit / osv +
your Dependabot advisories), concurrency & atomicity races, data-integrity &
missing migrations, multi-tenancy isolation, the domain-logic invariants from
`CLAUDE.md`, performance/N+1, error-handling & PII-in-logs, frontend runtime &
a11y, web/Astro specifics, and deploy hardening. Surfaces, verification rigor,
the confidence floor, and the per-run item cap are all tunable in
`docs/error-autopilot.config.yml`. Nothing is filed unless it's reproduced
red→green with no regression (zero-false-positive bar).

## Wire up the schedule (one-time, ~2 min)

The midday trigger is a **Claude Code Routine** (runs in Anthropic's cloud on
your Claude subscription — no API key, no extra billing). Routines can't be
created from inside a web session, so do this from a **terminal** Claude Code
session or the web UI:

**From a terminal (`/schedule`):**

```
/schedule daily at 12:00, run the error-autopilot skill defined in .claude/skills/error-autopilot/SKILL.md on the taqinor/taqinor-os repo
```

Then confirm these routine settings (the form / `/schedule update` walks them):

- **Prompt:** `Run the error-autopilot skill (.claude/skills/error-autopilot/SKILL.md). Read its STEP 0 kill switch first.`
- **Repository:** `taqinor/taqinor-os`.
- **Permissions → "Allow unrestricted branch pushes": ON** for this repo. The
  run self-merges `dev` → `main`, so without this it can only push `claude/*`
  branches and the merge step can't complete.
- **Environment:** one whose setup can run the test suites the verification step
  needs — backend tests need Postgres **and** MinIO, like CI; web/frontend need
  node. Reuse the same environment your "work on the plan" runs use. The default
  **Trusted** network access reaches the package registries, so the transient
  analyzers (semgrep/bandit/pip-audit/osv-scanner…) install fine; if a scanner
  needs another host, widen the environment's allowed domains. Analyzers are used
  for detection only and are never committed to the project's manifests.
- **Model:** the strongest available (the run orchestrates many lanes + an
  adversarial reviewer).

**From the web UI:** create the same routine at
<https://claude.ai/code/routines> → **New routine** → schedule trigger **daily
12:00**.

## Change the firing time

The time lives on the routine, not in the repo. Either:

- terminal: `/schedule update` (e.g. "change error-autopilot to 09:00"), or
- web UI: <https://claude.ai/code/routines> → the routine → edit the schedule.

Times are entered in your local zone (Africa/Casablanca) and run at that
wall-clock time. Minimum interval is 1 hour; a few-minute stagger is normal.
(The `schedule_note` in the config file is a human reminder only — editing it
does **not** change when the routine fires.)

## Turn it on / off

Two independent switches — either one off stops the run:

1. **Routine toggle** — <https://claude.ai/code/routines> → the routine →
   **Repeats** toggle (pause/resume). Paused keeps the config but never fires.
2. **Committed kill switch** — set `enabled: false` in
   `docs/error-autopilot.config.yml` and commit. On its next run the skill reads
   this first and exits immediately with `ERROR_AUTOPILOT: DISABLED`, making no
   change. Set it back to `true` to re-enable.

## Run it now (without waiting for noon)

On the routine's page click **Run now**, or from a terminal `/schedule run`.

## Safety

- The run only writes the two error-plan files (and `docs/CODEMAP.md` §10 + its
  plan fingerprint when it adds OS `ERR` items). It does **not** land code fixes.
- The single `dev` → `main` self-merge is gated by the four required CI checks
  (backend-lint, backend-tests with MinIO, frontend-lint, stage-names) and
  branch protection, exactly like a normal run — the autopilot never loosens or
  bypasses it and never force-pushes. A run that verifies nothing makes no
  commit and no merge.
- Routine runs draw down your normal subscription usage and count against the
  daily routine-run allowance; a green run status means it started cleanly, not
  that it filed items — open the session/run to see what it did.
