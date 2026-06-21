# Taqinor OS — Build Plan & Progress (priority queue, PLAN2)

> **This queue is drained BEFORE `docs/PLAN.md`.** A run works every pending `[ ]` task here first, and only falls through to `docs/PLAN.md` once this file has none left.

This is the **priority queue**, worked **before** `docs/PLAN.md`. A run drains every `[ ]` task
in this file FIRST — the same way (verify it isn't already built, build it completely with
tests, obey every STANDING RULE in `PLAN.md`, then commit it to a worktree branch, tick it `[x]`,
and append a DONE LOG line as it lands; **run `python scripts/plan_lanes.py docs/PLAN2.md` to get
the maximally-parallel cross-category wave plan and build those lanes in parallel with concurrent
worktree subagents up to the session ceiling (default 8, raised as high as the session can sustain
via `--max-lanes`), continuously refilled (work-stealing), coupled tasks in sequence inside a
lane**) — and only
once this file has no pending `[ ]` task left does it fall through to `docs/PLAN.md`. Every
worktree branch is folded into one `dev`, CI runs once over the whole batch, and the run
self-merges `dev` → `main` exactly once at the very end — **no per-agent PR, no per-task merge**.
All the HOW TO RUN and STANDING RULES in `docs/PLAN.md` apply here unchanged — including the
default **workflow-with-review engine** (one worktree subagent per task plus a separate
adversarial review agent that must pass before a change is merge-eligible), the
**parallel-subagent fallback** when no workflow engine is available (never a single serial
one-task-at-a-time agent), and the **sync-safe single merge** (integrate the latest
`origin/main` first, re-run CI, push without forcing). This file only adds tasks.

> Added 2026-06-17 while the field-execution batch (PLAN.md F1–F24) was running on
> `dev-field-exec`. Per the founder's "add to plan" convention, new tasks go here while a
> run is in progress so `PLAN.md` is never touched mid-batch.

---

> **Web session note (2026-06-18):** a world-class audit of the public site (`apps/web`) was run and its
> fixes built — **W62–W66 shipped** (social proof scaffold, homepage guarantee band, founder photo-ready
> block, brand strip +Jinko/Huawei/Nexans, « réponse sous 48 h ») and the **W67 EN/AR i18n foundation**
> laid (Astro i18n + dictionary + switcher + RTL/hreflang, FR byte-identical). Full detail in
> `docs/WEB_PLAN.md` + `docs/DONE.md`; web work stays out of this OS queue per the OS/web split. Logged
> here at the founder's request — this note adds no OS task.

## BUILD QUEUE (do top-down — highest value first)

### TOP PRIORITY — build first (queued 2026-06-20)

- [x] G10 — Lead-source capture (G10 first half): (1) add nullable fields to the lead model — `fbclid`, `utm_source`, `utm_medium`, `utm_campaign`, `utm_content`, `utm_term` (additive / nullable migration, company FK forced server-side); (2) on the marketing-site contact form (`apps/web/`), capture `fbclid` + the UTM params from the landing URL, persist them across the session, submit them with the lead, and store them on the created lead. The Meta Conversions API SEND (G10 second half) STAYS GATED — pending Reda's Meta pixel access token; only the CAPI send remains after this ships. (Note: the apps/web portion crosses into web-plan territory but is intentionally bundled here per Reda's instruction.) [VERIFIED 2026-06-20: already fully built — Lead has fbclid/utm_* (crm migration 0006), the website webhook maps+stores them (`crm/webhooks.py:_map_payload_to_fields`), `apps/web` captures first-touch fbclid+UTM (`Layout.astro`, `lib/lead.ts`), covered by `crm/tests_webhook.py`.]

### Group Q — Devis ↔ Toiture 3D pipeline (backend; founder request 2026-06-21)

*Goal: weld the existing `roofPro11` 3D tool (in `apps/web`) and the premium quote
into ONE loop — client points at their roof → Meriem designs it → client receives a
premium web proposal and e-signs. The expensive engine already exists (3D optimizer,
PVGIS production via `/api/roof-production`, premium quote engine); Group Q adds only
the **backend persistence, storage and wiring**. The matching front-end tasks live in
`docs/WEB_PLAN.md` (W112–W118).*

> **CRITICAL UX RULE (applies to the whole pipeline).** The client does the bare
> minimum and NEVER sees panels auto-fill. The client is **not obliged to draw** — they
> just **point** at their roof (drop a pin / pick the building) and give their bill;
> **Meriem** draws the outline (if needed) and runs the auto-fill/optimizer later,
> privately — so the client believes TAQINOR drew the whole design for them. Backend
> therefore stores the client's *pin (+ optional rough outline)* (Q2) separately from
> the *finalized layout with panels* (Q1); only the finalized layout ever reaches the
> proposal.

> **Constraints.** All schema additive/nullable, seeded from current defaults; every
> viewset company-scoped server-side (never trust `company` from the body). The legacy
> `/proposal` PDF path stays byte-identical (rule #4): Group Q only *adds* a web
> channel the founder explicitly authorized; the quote document statuses
> (`brouillon→envoye→accepte…`) are preserved 1:1 (rule #4 status preservation).

- [ ] Q1 — **`Devis.roof_layout` storage + endpoints.** Add a nullable `roof_layout`
  JSONField to `Devis` (additive migration) holding the *finalized* serialized
  `AreaRecord[]` (roof vertices, obstacles, roofType, pitch, azimuth, the result
  `{panels,kwc,annualKwh,savings}`, and `renderPlan`). Add company-scoped DRF
  endpoints `POST /api/django/ventes/devis/<id>/layout/` (save — company forced in
  the serializer/`perform_create`, never from body) and `GET …/layout/` (load).
  **Done =** round-trip save/load test + a cross-tenant isolation test pass. Files:
  `apps/ventes/models.py` (+migration), `apps/ventes/views.py`/serializers, tests.

- [ ] Q2 — **Client roof-POINT capture on the Lead (pin, not drawing).** Add nullable
  `roof_point` (lat/lng of the building the client pinned) and `roof_outline` (OPTIONAL
  rough polygon, usually empty — the client need not draw) JSONFields to the CRM Lead,
  plus the bill kWh and a secure unguessable per-lead `token` (UUID) for the Meriem
  hand-off link. First VERIFY the W105–W111 contact-capture work (it may already carry
  part of this) and EXTEND rather than duplicate; wire the lead intake/webhook
  (`apps/crm/webhooks.py`) to accept + persist the pin (+ optional outline) with the
  lead. **Done =** the pin persists on the lead, token resolves the lead, company forced
  server-side; tests cover it. Files: `apps/crm/models.py` (+migration),
  `apps/crm/webhooks.py`/views, tests.

- [ ] Q3 — **`build_devis_from_layout()` service (server-side).** A service that turns a
  finalized layout (kWc, nb panneaux, production, chosen module/onduleur) into Devis
  lines from the seeded catalogue, reusing the SAME composition rules as the quote
  generator (`builder.py` réseau/injection/hybride/batterie/panneau keywords) and the
  reference-numbering util (`apps/ventes/utils/references.py`, never count()+1), with the
  client resolved via `apps/crm/services.resolve_client_for_lead`. Store the layout's
  production into `Devis.etude_params`. **Done =** a sample layout produces a coherent,
  company-scoped Devis with correct kWc/lines/totals and NEVER auto-quotes a price-less
  product (existing guard); tests cover residential réseau + hybride+batterie. Files:
  `apps/ventes/services.py`, `apps/crm/services.py`, tests.

- [ ] Q4 — **Roof-render image storage.** Accept the tool's 3D snapshot PNG (from W115)
  and store it in MinIO reusing the existing PDF bucket/`minio_client` infra, keyed +
  company-scoped, referenced from a nullable `Devis.roof_image` field (additive).
  Endpoint `POST /api/django/ventes/devis/<id>/roof-image/`. **Done =** upload + signed
  retrieval test + company-scoping test pass. Files: `apps/ventes/utils/` (minio),
  `apps/ventes/models.py` (+migration), views, tests.

- [ ] Q5 — **Feed roof render + layout figures into the quote data (additive/guarded).**
  Extend the quote-data builder so a quote CAN show the real roof render as the "votre
  installation" visual and use the layout's kWc/production/savings instead of estimating
  — **only when a layout/render is present**; with none present the existing PDF output
  stays byte-identical (back-compat, rule #4). **Done =** with-layout vs without-layout
  tests both pass and the no-layout render is unchanged. Files: `quote_engine/builder.py`
  (guarded), tests. *(Additive only — does not alter the legacy path.)*

- [ ] Q6 — **Tokenized web-proposal data endpoint.** A read-only
  `GET /api/django/ventes/proposal/<token>/` returning the quote data
  (`build_quote_data` output + roof-image signed URL + option totals) as JSON for the
  client web proposal (W116) to render — authenticated by the signed token, not a login,
  company-scoped, expired/invalid tokens rejected. **Done =** valid token returns the
  payload; invalid/expired rejected; no cross-tenant leakage; tests cover it. Files:
  `apps/ventes/views.py`/urls, token util, tests.

- [ ] Q7 — **E-signature acceptance (reuse the existing stamp).** A tokenized
  `POST /api/django/ventes/proposal/<token>/accept/` that records typed name + timestamp
  + IP into the existing acceptance fields (`accepte_par_nom`/`date_acceptation`, N26) and
  flips the Devis to `accepte` THROUGH the existing acceptance service so the document
  chain (bon-commande/facture) is preserved 1:1 (rule #4). **Done =** accept flips status
  + writes the stamp + is idempotent on double-submit; tests cover it. Files:
  `apps/ventes/services.py` (reuse the acceptance path), views, tests. *(A legal-grade
  eIDAS e-sign provider stays a separate GATED decision — v1 reuses the existing stamp.)*

# Taqinor OS — UI/UX overhaul ("prettier than Odoo")

*Goal: a calm, premium, data-first ERP — Linear/Stripe-tier polish, brand-matched to Taqinor, denser and cleaner than Odoo. Built on the existing React 19 + Vite + Tailwind 4 + recharts stack. Positioned ahead of Groups A–D so feature work inherits the new design language. Constraints: do NOT touch the devis/facture PDF templates, the public PDF pages, or the PdfCanvas PDF content (client-facing, gated separately); do NOT touch the apps/web marketing site; STAGES.py stays a fixed CI contract; schema changes additive/nullable only, every new value seeded from current in-code defaults.*

> **Renumbered on intake (2026-06-18):** the source proposal lettered these groups E–O, but `docs/PLAN2.md` already has a **Group E** (the E2E browser-test suite, tasks E1–E16). To keep every group/task id unique, the UI/UX-overhaul groups were shifted one letter to **F–P** (and their task ids re-prefixed to match) before being inserted here. Titles, content, and the running task numbers (14–69) are otherwise verbatim.

## Group F — Design foundation & tokens
## Group G — Primitive component library (shadcn-based; one "definition of done" per component: states, dark mode, keyboard, ARIA)
## Group H — DataTable engine (TanStack Table, behind every list view)

## Group I — App shell & navigation

## Group J — Per-module restyle (each: list → DataTable, forms → new primitives, modals → Dialog/Sheet, statuses → StatusPill, real empty/loading/error states, mobile pass)

## Group K — Dashboard & reporting

## Group L — Global UX behaviors

## Group M — Mobile & PWA polish (Meryem is iPhone-primary)

## Group N — Accessibility & quality floor (WCAG 2.2 AA)

## Group O — Performance

## Group P — Consistency & cleanup

## Pending Reda (carry these in the plan)
- [x] Group G/H frontend dependencies — RESOLVED 2026-06-20: all installed in frontend/package.json + lockfile and in use (@radix-ui/* primitives, class-variance-authority, tailwind-merge, clsx, lucide-react, sonner). @tanstack/react-table is installed but not yet wired (the current DataTable is hand-rolled) — a build detail, not a dependency-approval blocker. No further Reda approval pending.
- [x] Logo — RESOLVED 2026-06-20 (Reda: the logo already lives in the repo — the one the quote engine/simulator uses — so use it): the OS now uses the official `TAQIN☀R` wordmark (`quote_engine/assets/logo.png`) as product branding. Added `frontend/scripts/gen_brand_assets.py` (reproducible) → trimmed transparent wordmark `public/taqinor-logo.png` (now shown on the Login card, replacing the hand-drawn SVG) + a white variant `public/taqinor-logo-light.png` + the missing **iOS splash screens** `public/splash/apple-splash-*` (light logo on the navy brand bg, 8 common iPhone sizes, wired in index.html; excluded from the SW precache). PWA icons/favicon were already from this logo's sun-bolt glyph (M59). Also fixed the N92 sw.js notification icon path (`/pwa-192x192.png` → `/pwa-192.png`). The sidebar keeps the per-tenant company name (multi-tenant — not overridden).
- [x] Default theme (F18) — RESOLVED 2026-06-20: the app theme FOLLOWS the system/device setting, per user (each user may override). Theme scaffolding already exists in frontend/src/design/ (ThemeProvider, theme.js with prefers-color-scheme).
- Hard constraints (do not violate): never touch the devis/facture PDF templates, the public PDF pages, the PdfCanvas content, or the apps/web marketing site; STAGES.py stays a fixed CI contract; all schema changes additive/nullable, seeded from current in-code defaults.

---

### Group A — Devis acceptance, wired to Signé, facture & chantier (core unblock)

### Group B — Bug: file attachments

### Group C — Bug: navigation menu

### Group D — Paramètres: split + far more editable settings (all in one pass)



### Group E — End-to-end (E2E) browser test suite covering every screen flow

---

## DONE LOG (agent appends one plain-language line per completed task)

- 2026-06-20 — Logo resolved: the OS uses the official Taqinor wordmark (the repo's quote-engine logo) as product branding — real logo on the Login screen + iOS splash screens generated from it (`gen_brand_assets.py`), PWA icons already from its glyph; fixed the web-push notification icon path. Sidebar keeps the per-tenant company name.
- 2026-06-20 — G10 (first half) verified already-present: the lead model already carries `fbclid` + `utm_source/medium/campaign/content/term` (crm migration 0006), the website lead webhook maps and stores them (`apps/crm/webhooks.py`), and `apps/web` captures first-touch fbclid+UTM from the landing URL and submits them (`Layout.astro`, `lib/lead.ts`), covered by `apps/crm/tests_webhook.py`. Ticked `[x] (already present)`. The CAPI SEND (second half) stays gated on Reda's Meta pixel token.

