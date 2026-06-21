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

## Wire up the schedule

Two supported ways to fire the skill daily at noon. The skill behaves the same
either way (it reads STEP 0's kill switch first); the difference is *where* it
runs and *which* checkout it sees.

### Path A — Desktop scheduled task (local; runs against `C:\dev\taqinor-os`)

This is the path set up as **`daily-error-autopilot`**. It runs on your machine
while the Claude desktop app is open, against your **local working copy**, so:

- **The skill must exist in that local checkout.** It lives on `main` once this
  change is merged — make sure `C:\dev\taqinor-os` is on `main` and pulled
  (`git checkout main && git pull`). If the file is missing when the task fires,
  the run reports "skill not created yet" and does nothing (by design).
- **Pre-approve tools once:** in the Scheduled sidebar click **Run now** the
  first time and approve git/shell on the repo, so future noon runs don't pause
  on permission prompts.
- **Only fires while the app is open.** If the app is closed at noon, it runs on
  next launch. (Use Path B if you need it to run with the laptop closed.)
- **Self-merge needs local push rights** to `origin` (your normal git auth).
- **Deeper analyzers need network + tooling** locally (Python with
  Postgres/MinIO for backend tests, Node for frontend/web, and the transient
  analyzers semgrep/bandit/pip-audit/osv-scanner). Anything it can't run that
  day it skips for that surface and notes in the report — it never guesses.

The few-minutes-after-noon start (e.g. 12:08) is normal scheduler jitter and is
harmless for a daily sweep.

### Path B — Cloud Routine (runs in Anthropic's cloud, even with the laptop closed)

A **Claude Code Routine** runs on your Claude subscription (no API key, no extra
billing) and clones the repo fresh each run, so it always sees `main`. Create it
from a **terminal** Claude Code session or the web UI (not from inside a web
session):

```
/schedule daily at 12:00, run the error-autopilot skill defined in .claude/skills/error-autopilot/SKILL.md on the taqinor/taqinor-os repo
```

Then confirm these routine settings (the form / `/schedule update` walks them):

- **Prompt:** `Run the error-autopilot skill (.claude/skills/error-autopilot/SKILL.md). Read its STEP 0 kill switch first.`
- **Repository:** `taqinor/taqinor-os`.
- **Permissions → "Allow unrestricted branch pushes": ON** — the run self-merges
  `dev` → `main`, so without this it can only push `claude/*` branches.
- **Environment:** one whose setup can run the suites — backend tests need
  Postgres **and** MinIO like CI; web/frontend need node. Reuse the environment
  your "work on the plan" runs use. The default **Trusted** network reaches the
  package registries, so the transient analyzers install fine; widen allowed
  domains if a scanner needs another host. Analyzers are detection-only and are
  never committed to the project's manifests.
- **Model:** the strongest available (it orchestrates many lanes + a reviewer).

Web UI alternative: <https://claude.ai/code/routines> → **New routine** →
schedule trigger **daily 12:00**.

## Change the firing time

- **Desktop task:** edit the schedule in the Scheduled sidebar (its cron is
  `0 12 * * *` for noon).
- **Cloud routine:** `/schedule update` (e.g. "change error-autopilot to 09:00")
  or <https://claude.ai/code/routines>. Times are local (Africa/Casablanca);
  minimum interval 1 hour; a few-minute stagger is normal.

The `schedule_note` in the config file is a human reminder only — editing it does
**not** change when anything fires.

## Turn it on / off

Switches — **any one** off stops the run:

1. **Scheduler toggle** — pause the Desktop task in the Scheduled sidebar, or
   the cloud routine's **Repeats** toggle. Paused keeps the config but never
   fires.
2. **Committed kill switch** — set `enabled: false` in
   `docs/error-autopilot.config.yml` and commit. On its next run the skill reads
   this first and exits immediately with `ERROR_AUTOPILOT: DISABLED`, making no
   change. Set it back to `true` to re-enable.

## Run it now (without waiting for noon)

Desktop task: **Run now** in the Scheduled sidebar. Cloud routine: **Run now** on
its page, or `/schedule run` from a terminal.

## Safety

- The run only writes the two error-plan files (and `docs/CODEMAP.md` §10 + its
  plan fingerprint when it adds OS `ERR` items). It does **not** land code fixes.
- The single `dev` → `main` self-merge is gated by the four required CI checks
  (backend-lint, backend-tests with MinIO, frontend-lint, stage-names) and
  branch protection, exactly like a normal run — the autopilot never loosens or
  bypasses it and never force-pushes. A run that verifies nothing makes no
  commit and no merge.
- Runs draw down your normal Claude usage (cloud routines also count against the
  daily routine-run allowance). A green/finished run status means it started
  cleanly, not that it filed items — open the session/run to see what it did.
