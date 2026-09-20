# FRONTEND_GAP_PLAN.md — wire the round-2 backends to the UI

**Why this plan exists.** A 2026-07-06 code-level audit (not plan-checkbox based) found a
**repo-wide systematic gap**: the round-2 build-outs (X-series `XFLT/XQHS/XGED/XCTR/XPRJ/XPAI/XRH/XSAV/XACC…`
and Z-series `Z*`) shipped **backend-only** — the paired frontend half of each task was never
built, even though most tasks named a `frontend/` file in their own "Files:" line. Backends are
real, tested, and merged (in b4 / batch-3+4); the UI simply never caught up. Each item below is a
**frontend wiring task**: add the `<domain>Api.js` client entries + the screen/tab/button + nav, and
a focused test, calling the EXISTING backend endpoint.

## HOW TO RUN (same model as `work on the plan`)
- Drain this BUILD QUEUE as ONE work-stealing pipeline; land as ONE gated self-merge at the end,
  then `powershell -File scripts/deploy-prod.ps1` (ERP frontend deploys manually — NOT Cloudflare;
  that's `apps/web` only, out of scope here).
- **Lane = one frontend domain.** They are file-disjoint (`features/<domain>/` + `api/<domain>Api.js`
  + the domain's own auto-registered `module.config.jsx`), so up to 8 run in parallel with near-zero
  fold conflict. `python scripts/plan_lanes.py docs/FRONTEND_GAP_PLAN.md` for the graph.
- **Per task:** verify-not-already-wired (grep the api client + component first) → add api entry +
  screen/tab/nav → focused vitest/RTL test that keeps the e2e DOM hooks intact → `npm run lint` +
  targeted vitest → commit that task → next.
- **Per-task model:** haiku = pure api-client one-liners / trivial column adds; sonnet (default) =
  standard screens/tabs/forms/reports; opus = the heavy flows (GED public e-sign ceremony, CONTRAT
  rental module, ATS pipeline, PaieRunWizard safety gates).
- **Fold + local test:** as each lane returns, review vs the STANDING RULES, fold onto the `dev`
  branch, run `npm run lint` + vitest + `npm run build` over the changed areas. Keep e2e green
  (selectors `ap-*/att-*/pp-*`, exactly one Toaster, header title not role=heading).

## STANDING RULES
- Wire to the EXISTING backend endpoint; never change a backend contract from here. If an item is
  actually BACKEND-INCOMPLETE (no viewset/URL — see the two flagged below), mark `[BLOCKED: needs backend]`
  and skip; those go to `docs/PLAN.md`, not here.
- No new frontend dependency without asking (regenerate the lock with `npx npm@10 install
  --package-lock-only` from main's lock if one is ever truly needed — Windows/npm-11 prunes Linux entries).
- Multi-tenant + permission gating: honour the same role/permission gates the backend enforces
  (e.g. `prix_achat_voir`/`salaires_voir` panels stay gated). Never expose `prix_achat`/margin in client output.
- French apostrophes break `.astro`/JS strings — mind escaping. Keep French UI labels consistent with STAGES.py.
- Branch each lane from `origin/claude/sad-euclid-b4` (the backends live there); after the backend
  merges land on `main`, rebase the frontend `dev` onto `main` before the single frontend merge.

## GATED / NOT HERE
- ~~**XACC14 Emprunt** and **XACC19 EtatPersonnalise**~~ — UNGATED by WIR279 (2026-08-26): the
  backend halves now exist (`EmpruntViewSet` + `generer-tableau/`, read-only `EcheanceEmpruntViewSet`
  + `poster/`, `EtatPersonnaliseViewSet` + `evaluer/` on `etats-personnalises/`), with their response
  contracts committed under `apps/compta/contract_samples/`. The frontend halves are ordinary
  frontend tasks again.
- **XRH33 careers public page** — deferred to `WEB_PLAN` (apps/web), not ERP frontend. (An in-app
  "publier" toggle IS in scope — see RH lane.)

---

# BUILD QUEUE

## Lane `frontend/qhse` (XQHS — all backend-only; verify XQHS5/6/7/9/10/12 aren't ORPHAN backends first)
- [BLOCKED: needs backend] FE-XQHS5-13 — recalls/SCAR/5-why-8D/certifications/audit-program/revues/objectifs UIs; add the matching `qhseApi` resources (VERIFY each viewset exists — some may be ORPHAN → `[BLOCKED: needs backend]`). (@lane: frontend/qhse) — SCAR (`demandes-action-fournisseur`) déjà câblé dans `CheckinsSecurite.jsx` et XQHS7 (analyse 5-Pourquoi/8D) livré le 2026-08-13 ; le RESTE est ORPHELIN côté backend (aucun viewset ni URL pour `CampagneRappel`/`ElementRappel`, `Certification`/`AuditCertification`, `ProgrammeAudit`/`AuditPlanifie`, `ReunionQhse`/`DecisionReunion`, `ObjectifQhse`/`RevueObjectif`, ni pour `rendre_analyse_ncr_pdf`) → va dans `docs/PLAN.md`.

## Lane `frontend/reporting` (systemic offender — many [x] reports backend-only)
- [ ] FE-XPLT11 — **BLOCKED: needs pivot/BI-explorer screen (FG382, itself unbuilt frontend)** then expose the formula measure. (@lane: frontend/reporting)

## AUDIT COMPLETE (2026-07-06)
- Domains CLEAN (fully wired, no gaps): **litiges, monitoring, publicapi, audit** baseline screens.
- Legitimately backend-only (no UI ever promised): YAPIC7-10, YHARD1 (versioning/webhooks/idempotency/encryption).
- `ODX5` (Applications catalogue) still `[ ]` in PLAN.md — normal backlog, not a gap.

## DONE LOG
<!-- one dated line per shipped task -->
