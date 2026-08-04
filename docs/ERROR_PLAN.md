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

---

- [ ] ERR114 — [ventes/quote_engine] **Le PDF premium 'full' résidentiel déborde sur 4 pages dans l'image prod (contrat = 3 pages exactement)** — trouvé par le nouveau test golden YTEST10 à son premier run. REPRO (prouvée 2026-07-10, images `taqinor-django-prod:latest` ET `erp-agentique-django_core:latest`) : rendre `BASELINE_CASES[0]` ('residentiel_full', FULL_LINES 10 lignes, mêmes lignes que `test_quote_engine.test_premium_pdf_is_exactly_three_pages`) via `_render_pdf_bytes` → 4 pages ; la page 4 ne contient QUE le bloc CTA e-sign (« Prêt à passer au solaire ? / Signez en ligne → taqinor.ma/signer/… / Scannez pour signer », introduit par XSAL16) + la ligne légale — un débordement du bas de la page 3 (`residential/trust.py`). Le test canonique passe en CI (polices ubuntu ≠ polices image prod) donc la CI ne le voit pas : LES CLIENTS REÇOIVENT AUJOURD'HUI un PDF 4 pages dont la dernière est quasi vide. FIX attendu : resserrer le layout de `residential/trust.py` (ou déplacer le CTA) pour retenir exactement 3 pages DANS L'IMAGE PROD (vérifier avec la repro ci-dessus, pas seulement en CI), sans casser les autres formats ; puis générer le baseline manquant `residentiel_full_p1..p3.png` via `manage.py update_pdf_baselines` (image prod) et le committer. Rule #4 : édition du moteur autorisée pour un fix ; ne toucher à aucun statut. (@lane: backend/ventes-pdf)

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

---

## DONE LOG (agent appends one plain-language line per fixed task)
