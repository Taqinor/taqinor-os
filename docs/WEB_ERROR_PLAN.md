# Taqinor WEB — Error Plan & Bug Backlog (`apps/web` site + preview lab)

This file is the **web-side twin of [`docs/ERROR_PLAN.md`](ERROR_PLAN.md)**: the
bug/error backlog for the public **Astro** marketing site and its private
preview lab, everything under **`apps/web/**`**. `docs/ERROR_PLAN.md` stays
**OS-only** (Django/FastAPI backend + the React OS app under `frontend/`) and
excludes `apps/web`; anything wrong with the Astro site or a `/preview/*` route
is filed here, not there.

It is populated automatically by the **error-autopilot** (the daily
midday run defined in `.claude/skills/error-autopilot/SKILL.md`,
config in `docs/error-autopilot.config.yml`, operator guide
`docs/error-autopilot.md`). The autopilot only files an item after it has
**reproduced the bug and proven a fix actually resolves it** in an isolated
worktree — so every `[ ]` here is a real, verified defect with a known-good fix,
not a guess.

Tasks use `WEBERR*` ids. Like `docs/WEB_PLAN.md`, this file is **not** part of
the CODEMAP plan-fingerprint surface (`scripts/codemap_fingerprint.py`
`PLAN_FILES`), so adding/ticking a `WEBERR` task does **not** require a CODEMAP
§10 refresh — web-only changes never move the fingerprint.

This file is the single source of truth + memory between sessions for known web
bugs.

---

## HOW TO RUN (drain this backlog)

Drained exactly like `docs/ERROR_PLAN.md`, with the **one** difference that
scope stays strictly inside `apps/web/**` (plus this file):

> Read this whole file. Work through EVERY unchecked `[ ]` WEBERR task: first run
> `python scripts/plan_lanes.py docs/WEB_ERROR_PLAN.md` to get the
> maximally-parallel cross-category wave plan, then build those lanes in parallel
> with concurrent worktree subagents (`isolation: worktree`, each in its own git
> worktree) up to the session ceiling (default 8, raised as high as the session
> can sustain via `--max-lanes`), continuously refilled (work-stealing), coupled
> fixes in sequence inside a lane (default: dynamic workflow with a separate
> adversarial review agent that must pass each change before it's merge-eligible;
> fall back to plain parallel worktree subagents — never a single serial
> one-task-at-a-time agent). For each task: verify it isn't already fixed (mark
> `[x] (already present)` if it is), build the fix with tests, commit it to its
> worktree branch, tick it `[x]`, add a dated DONE LOG line, then continue. Skip
> -and-note any blocker (`[BLOCKED: reason]` → GATED) and keep going. At the very
> end, fold every worktree branch into one `dev`, integrate the latest
> `origin/main` first (merge it in, never force-push), get CI green over the whole
> batch and self-merge `dev` → `main` exactly once (this auto-deploys the site via
> Cloudflare — no deploy command). Report once, in plain language, including the
> lane plan. Finally print `WEB_ERROR_STATUS: EMPTY` if no `[ ]` task remains,
> else `WEB_ERROR_STATUS: MORE`.

**Scope guard.** Edit ONLY `apps/web/**` and this file. Anything outside
`apps/web` is an OS error — file it in `docs/ERROR_PLAN.md` instead.

**Deploy is automatic.** Merging to `main` auto-deploys via Cloudflare Workers
Builds — never run `wrangler deploy`, never ask for a Cloudflare token. Worker
secrets / dashboard variables are a manual founder step; list them under MANUAL,
never block silently.

---

## BUILD QUEUE (fix highest-severity first)

### Critical

_(none yet — the error-autopilot appends verified items here)_

### High

_(none yet)_

### Medium

_(none yet)_

### Low

_(none yet)_

---

## GATED — needs founder decision before fixing (agent does NOT auto-build)

Move any task here with a `[BLOCKED: <reason>]` tag when fixing it would require a
new external dependency, an auth/cost policy change, a new Cloudflare secret the
founder hasn't set, anything touching the public lead-data flow, or a conflict
with a non-negotiable rule. (none yet)

---

## AUTOPILOT INTAKE LOG (the error-autopilot appends one line per run)

- *(file created 2026-06-21 — web error backlog, populated by the daily
  error-autopilot.)*

---

## DONE LOG (one plain-language line per fixed task)

- *(none yet)*
