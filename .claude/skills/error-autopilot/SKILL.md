---
name: error-autopilot
description: >-
  Daily midday error-flagging autopilot for TAQINOR OS. Scans the whole repo for
  REAL defects, and for each one reproduces the bug and PROVES a fix actually
  resolves it in an isolated git worktree BEFORE filing it as a tested correction
  item in docs/ERROR_PLAN.md (OS: backend + frontend) or docs/WEB_ERROR_PLAN.md
  (web: apps/web). No guesses, no half-work: only verified errors with a known-good
  fix get filed. Uses the "work on the plan" parallel-lane / worktree-subagent model
  for maximum throughput. Built to be run unattended by a Claude Code Routine (see
  docs/error-autopilot.md); honour the kill switch in docs/error-autopilot.config.yml.
---

# Error-Autopilot — daily verified-error intake

You are running the error-autopilot. Your job is **not** to fix code and merge
fixes. Your job is to **find real, reproducible errors, prove a fix works, and
file each as a tested correction item** in the right error-plan file. The actual
fixes are landed later by `work on error plan` (OS) and the web error-plan drain.

Treat this whole file as your runbook. It is self-contained because you run
unattended. Obey every non-negotiable rule in `CLAUDE.md` at all times.

---

## STEP 0 — Preflight & kill switch (do this first, every run)

1. Read `docs/error-autopilot.config.yml`.
2. **If `enabled: false` → STOP immediately.** Make NO file change, NO commit,
   NO merge. Print exactly one line: `ERROR_AUTOPILOT: DISABLED (config flag off)`
   and end the run. (The Claude Routine's own pause toggle is the other off-switch;
   either one being off must stop the run.)
3. If enabled, read `max_lanes`, the two `targets` (os / web), and confirm
   `output: self-merge-to-main`. Read `docs/ERROR_PLAN.md`, `docs/WEB_ERROR_PLAN.md`,
   `CLAUDE.md`, and `docs/CODEMAP.md` so you know the current backlog, the
   non-negotiable rules, and the code map.
4. Compute the next free ids: scan existing `ERR<n>` in `docs/ERROR_PLAN.md` and
   `WEBERR<n>` in `docs/WEB_ERROR_PLAN.md`; new items continue from `max+1` per
   prefix. (Today OS is fully drained through ERR113 → start at ERR114; web is
   empty → start at WEBERR1.)

The two areas **never overlap**:
- **OS area → `docs/ERROR_PLAN.md`** (`ERR` ids): everything under `backend/`
  (Django `django_core` + FastAPI `fastapi_ia`) and `frontend/` (the React OS app).
- **Web area → `docs/WEB_ERROR_PLAN.md`** (`WEBERR` ids): everything under
  `apps/web/` (the Astro site + preview lab) and only that.

---

## STEP 1 — Plan a maximally-parallel audit (the "work on the plan" model)

Do **not** scan top-down or single-threaded. Partition the codebase into
independent **lanes** (one per app / file-set that two auditors would collide on)
and fan them out to **concurrent worktree subagents** (`isolation: worktree`,
each in its own git worktree so two never touch the same files), up to
`max_lanes` (default 8, raise as high as the session sustains), continuously
refilled (work-stealing — a freed slot takes the next lane immediately). Tasks
inside a lane run in sequence.

Independent audit lanes (adjust to the real tree, longest/riskiest first):
- backend: `apps/authentication`, `apps/roles`, `apps/crm`, `apps/ventes`,
  `apps/stock`, `apps/installations`, `apps/sav`, `apps/reporting`,
  `apps/parametres`, `apps/automation`, `apps/dataimport`, `apps/publicapi`,
  `apps/notifications`, `apps/monitoring`, `apps/records`, `apps/core`
- FastAPI IA service: `backend/fastapi_ia/**`
- frontend OS app lanes by feature/page area under `frontend/src/**`
- web lanes under `apps/web/src/**` (pages/api, lib, layouts, worker, preview)

Run `python scripts/plan_lanes.py docs/ERROR_PLAN.md` and
`python scripts/plan_lanes.py docs/WEB_ERROR_PLAN.md` to see the planner's view;
both files may be empty/drained, so for the AUDIT you also lane by the source
tree above. Default engine: a dynamic workflow with a **separate adversarial
review agent** that must pass each filed item against this runbook before it
counts; fall back to plain parallel worktree subagents (you review each lane
yourself) — **never a single serial one-at-a-time agent.**

Keep subagents lean: each gets only its lane + this runbook and returns a SHORT
summary (candidate errors, what was reproduced, what the proven fix was) — never
a full diff — so your orchestration context stays light across many waves.

---

## STEP 2 — Find REAL errors (evidence required, no guesses)

A "candidate error" must have concrete evidence, from any of:
- a **failing test / lint / type / build / check**: run the real suites —
  `python manage.py test apps` (backend, needs Postgres + MinIO like CI),
  `flake8` and `lint-imports` (backend lint), `npm run lint` + `npm test` +
  `npm run build` (frontend), `npm run check`/`tsc` + vitest + astro build (web),
  `python scripts/check_stages.py`, `python scripts/codemap_fingerprint.py --check`;
- a **concrete logic/security defect** in the same classes already catalogued in
  `docs/ERROR_PLAN.md` (tenant isolation / IDOR, missing `perform_create`
  company scoping, mass-assignment, race conditions needing `select_for_update`,
  `int()` truncation of Decimal quantities, missing input validation, unescaped
  HTML/XSS, formula injection, fail-open guards, naive-datetime TZ bugs,
  swallowed errors / silent empty data, never-reject-number form rule, etc.) —
  but only when you can **reproduce** it (a test or a precise trigger), not from
  reading alone.

Discard anything you cannot reproduce. Style nits, hypotheticals, "could maybe"
findings, and pure preferences are **not** errors — do not file them.

---

## STEP 3 — VERIFY the fix actually works (the whole point of this autopilot)

This is the rule the founder cares about most: **prove the solution before
filing it.** For each candidate, inside its own isolated worktree:

1. **Reproduce (red):** write or identify a test/check that fails *because of*
   the bug. If you cannot make it fail, the bug is not real — drop it.
2. **Fix:** implement the smallest correct fix in that worktree.
3. **Prove (green):** the previously-red test/check now passes **and** the four
   required CI checks still pass with no regression — backend-lint,
   backend-tests (with MinIO), frontend-lint, stage-names. For a web item, also
   run the web suites (tsc + vitest + astro build).
4. **Only if all of the above hold** is the error CONFIRMED. Record, for the
   item: the file:line, the defect, the exact reproduction, and the **proven fix
   approach** (concise — enough that `work on error plan` re-applies it directly,
   a short patch sketch is ideal).
5. **Throw the fix worktree away.** The autopilot files the *item*, it does not
   land the code fix. (Landing fixes is the drain command's job.)

If a candidate's verified fix would require a **gated** change — a destructive /
schema migration, a new external dependency, an auth or cost policy change, a
new Cloudflare secret, or anything conflicting with a `CLAUDE.md` non-negotiable
— do NOT pretend it is landed-ready: file it under **GATED** with a
`[BLOCKED: <reason>]` tag and a note of what decision is needed.

---

## STEP 4 — Dedup & number

Before filing, check the candidate is **not already covered** by an existing
`ERR`/`WEBERR` item (open, done, or gated) — match on file + symptom. If it is,
skip it (do not refile). Assign the next free id per prefix (Step 0).

---

## STEP 5 — File the verified items

Append each confirmed item to the correct file under the correct severity
heading in the BUILD QUEUE (Critical / High / Medium / Low), using the exact
existing one-line format, with the proven fix appended:

```
- [ ] ERR114 — [app] <defect> (`path/to/file.py:line`): <symptom / impact>. FIX (verified): <proven fix, repro test name>.
```

- OS errors → `docs/ERROR_PLAN.md` (`ERR` ids).
- Web errors → `docs/WEB_ERROR_PLAN.md` (`WEBERR` ids).
- Gated items → the GATED section of the matching file with `[BLOCKED: …]`.

Append one dated line to each touched file's **AUTOPILOT INTAKE LOG** section:
`- YYYY-MM-DD — filed N new verified items (ERRxxx–ERRyyy): <one-line theme>.`

If a run confirms **nothing**, file nothing, make **no commit**, **no merge**,
and just report "no new verified errors" (Step 8/9). Do not pad the backlog.

---

## STEP 6 — CODEMAP fingerprint (OS file only)

`docs/ERROR_PLAN.md` is in the plan-fingerprint surface
(`scripts/codemap_fingerprint.py` `PLAN_FILES`), so **if and only if you added /
changed `ERR` task lines**, in the SAME commit as the file edit:
1. refresh §10 "Plan status" of `docs/CODEMAP.md` (paste
   `python scripts/codemap_fingerprint.py --print-plan-status`, update the
   `Generated from commit` stamp + cross-check notes), then
2. run `python scripts/codemap_fingerprint.py --write`, then confirm
   `python scripts/codemap_fingerprint.py --check` and
   `python scripts/check_stages.py` are green.

`docs/WEB_ERROR_PLAN.md` is **not** in the fingerprint surface (it mirrors
`docs/WEB_PLAN.md`), so web-only changes need **no** CODEMAP refresh.

You changed no models/endpoints/routes/structure, so the **structure**
fingerprint does not move — do not regenerate the CODEMAP body.

---

## STEP 7 — Land it (one sync-safe self-merge to main)

`output: self-merge-to-main`. Fold every worktree branch's plan-file commits
into one `dev` branch. Then make the single merge **sync-safe**:
1. fetch and integrate the latest `origin/main` into `dev` (merge it in —
   **never rebase published history, never force-push**);
2. if integrating `main` moved the structural surface, recompute the CODEMAP
   structure fingerprint on the integrated tree;
3. run the four required CI checks once over the whole batch (with MinIO) and
   self-merge `dev` → `main` **exactly once** (one merge commit, 0 approvals,
   no per-item PR, no per-item merge);
4. if the push is rejected because `main` advanced, repeat fetch → integrate →
   (refresh fingerprint if needed) → CI → push. Never force, never overwrite
   another run's commits.

Keep branch protection exactly as configured — never loosen or bypass it. The
merge auto-deploys; never run a deploy command.

---

## STEP 8 — Report & status

Report once, in plain language, including the **lane plan**: how many lanes ran
in parallel, what each surfaced, how many candidates were dropped for failing
verification, and the exact new item ids filed into each file. No diffs, no
hashes.

Finally print both status lines so a headless loop can read them:
- `ERROR_PLAN_STATUS: EMPTY` if `docs/ERROR_PLAN.md` has no `[ ]` task left,
  else `ERROR_PLAN_STATUS: MORE`.
- `WEB_ERROR_STATUS: EMPTY` if `docs/WEB_ERROR_PLAN.md` has no `[ ]` task left,
  else `WEB_ERROR_STATUS: MORE`.

---

## STANDING SAFETY RULES (always)

- Obey every `CLAUDE.md` non-negotiable rule (Odoo JSON-2 only; `STAGES.py`
  stage names; Meta Ads campaigns born paused; `/proposal` the only client quote
  PDF path; scraper policy). The autopilot **never runs scrapers** and never
  starts external scraping.
- Never weaken, bypass, or add approval steps to branch protection. Never
  force-push. Never overwrite a concurrent run's commits.
- `prix_achat` / margins never appear in any output.
- The autopilot only ever writes `docs/ERROR_PLAN.md`, `docs/WEB_ERROR_PLAN.md`,
  and (for OS intake) `docs/CODEMAP.md` §10 + its plan fingerprint. It does
  **not** land code fixes — every filed item is verified but its fix is left for
  the drain commands.
- Fewest steps, no ceremony, no adjacent/unrequested work.
