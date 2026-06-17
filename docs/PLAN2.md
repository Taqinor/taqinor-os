# Taqinor OS — Build Plan & Progress (priority queue, PLAN2)

> **This queue is drained BEFORE `docs/PLAN.md`.** A run works every pending `[ ]` task here first, and only falls through to `docs/PLAN.md` once this file has none left.

This is the **priority queue**, worked **before** `docs/PLAN.md`. A run drains every `[ ]` task
in this file FIRST — the same way (verify it isn't already built, build it completely with
tests, obey every STANDING RULE in `PLAN.md`, CI green, self-merge `dev` → `main`, tick it
`[x]`, append a DONE LOG line) — and only once this file has no pending `[ ]` task left does it
fall through to `docs/PLAN.md`. All the HOW TO RUN and STANDING RULES in `docs/PLAN.md` apply
here unchanged — this file only adds tasks.

> Added 2026-06-17 while the field-execution batch (PLAN.md F1–F24) was running on
> `dev-field-exec`. Per the founder's "add to plan" convention, new tasks go here while a
> run is in progress so `PLAN.md` is never touched mid-batch.

---

## BUILD QUEUE (do top-down — highest value first)

### Group A — Devis acceptance, wired to Signé, facture & chantier (core unblock)

- [x] **A1 — "Marquer comme accepté" control on a devis.** Add the status control that's
  currently missing directly on a devis. Accepting records **which option the client chose**
  (Sans batterie / Avec batterie), the **acceptance date**, and **who accepted**, written to
  the devis/lead **Historique** (chatter). Add the small devis fields needed to store these
  (acceptance date, chosen option, accepted-by). Preserve the existing devis status layer
  (`brouillon`/`envoye`/`accepte`/`refuse`/`expire`) — this sets `accepte` and records the
  option + metadata; it does not invent a new status layer.

- [x] **A2 — Moving a lead into Signé prompts for the accepted devis + option.** When a lead
  is moved into the **Signé** stage (kanban drag or stage control), open a short dialog to
  pick **which of the lead's devis was accepted** and **which option** (Sans batterie / Avec
  batterie); confirming marks that devis accepted (reusing A1). If the lead has **no devis**,
  show a message to **create/select one first** — never invent a devis and never move the
  stage without one. Keep it a **user-confirmed prompt**; the lead funnel stage (STAGES.py)
  and the document status stay **separate layers** (rule #2) — moving to Signé does not
  silently rewrite document statuses beyond the one chosen devis the user confirms.

- [ ] **A3 — The chosen option is authoritative downstream.** The **facture échéancier** and
  the **chantier** use **only the accepted option's lines** (battery lines excluded if "Sans
  batterie", included if "Avec batterie"). Totals and TVA must be correct **to the centime**
  for that option (reuse the existing reference/total utilities; never recompute by hand).

- [ ] **A4 — Inline next actions after acceptance.** After a devis is accepted, surface both
  next actions inline on the lead/devis:
  - **"Générer la facture"** — acompte → matériel → solde on repeat clicks, **unchanged**
    behaviour (do not alter the existing échéancier engine, only feed it the accepted option).
  - **"Créer le chantier"** — **pre-filled** from the accepted option, **no duplicate** if a
    chantier already exists for that devis/lead (guard against double-create).

### Group B — Bug: file attachments

- [ ] **B1 — Fix file attachments end-to-end (and the broken devis-PDF icon).** Attaching a
  file to a **lead / client / chantier / SAV ticket** is broken on **both** the upload side
  and the **open/download** side — fix both. This is **likely the same root cause** as the
  broken-file icon on new devis PDFs (storage link not reachable from the browser — MinIO/
  storage URL not resolvable from the client). **Fix both together**: ensure uploads succeed
  and the stored object is afterward **openable/downloadable from the browser**. Add a
  regression test that an uploaded attachment round-trips (upload → fetch a working URL).

### Group C — Bug: navigation menu

- [ ] **C1 — iPhone: menu items cut off / unreachable.** The last menu item(s) are cut off
  and unreachable on iPhone. Make the **whole menu scrollable** and **fully visible inside
  the iOS safe area**, in **both the installed (PWA) app and Safari**. **Verify on real
  iPhone widths** — do **not** assume the earlier responsive/safe-area work covered it.

- [ ] **C2 — Desktop: cold first-load flakiness.** Fix the cold first-load flakiness (needing
  several refreshes) so a **single load works reliably** on desktop. (Related to the
  no-store + PWA service-worker behaviour — investigate the SW/first-paint race rather than
  guessing.)

### Group D — Paramètres: split + far more editable settings (all in one pass)

- [ ] **D1 — Reorganize Paramètres into sections/tabs by domain.** Split the single long
  Paramètres page into tabs/sections: **Société & identité · Leads · Clients · Devis &
  Factures · Stock · Équipe & rôles · Messages & relances · Avancé**. Keep **every existing
  setting working** (no setting dropped or broken). **No horizontal overflow on phones.**

- [ ] **D2 — Quick settings.** Add:
  - editable **conditions générales** + **quote validity** (printed on the devis PDF);
  - **consolidated defaults**: default responsable, default installer, default acompte %;
  - **client ICE** on the client record, surfaced on devis/factures and **carried through
    without re-entry**, with a **non-blocking reminder** when missing on B2B docs;
  - a configurable **RIB + payment-instructions block** on the devis/facture PDFs;
  - **editable warranty texts per product/category**, seeded from the current texts.
  These print through the **existing vendored quote engine** — do **not** edit the premium
  PDF pages; feed the engine new fields (rule #4).

- [ ] **D3 — Per-document numbering configuration.** Add per-document-type numbering config
  (**prefix, padding width, yearly-reset**) per document type, **keeping sequences gap-free
  and race-safe** (reuse `apps/ventes/utils/references.py` — NEVER count()+1), **seeded to
  current behaviour** so existing numbering is unchanged until edited.

- [ ] **D4 — Roles & permissions editor (on the existing roles app).** Grant/restrict
  **per module and action**. **Buy prices and margins visible to owner only by default.** Ship
  a **safe default role set** (owner / commerciale / technicien / viewer) so **current access
  is unchanged**. Add **record-level scoping where feasible**. Margins/buy-price
  (`Produit.prix_achat`) must remain generator-only and never reach any PDF/client output.

- [ ] **D5 — Avancé: editable + versioned quote logic.** Make the implicit quote logic
  **editable and versioned**: margin / target price per kWc, discount limits, auto-remplir
  sizing ratios, per-region production factors, and the **ONEE tariff tables/tranches**.
  **Every value seeded from today's in-code defaults** so default quoting stays **identical**
  until edited. Do **not** touch the PDF templates and do **not** break the lossless
  typed-number behaviour (form `noValidate`, inputs `step="any"` — guarded by tests). Keep
  `solar.js` classification keywords aligned with `quote_engine/builder.py`.

### Group E — End-to-end (E2E) browser test suite covering every screen flow

- [ ] **E1 — Playwright + required CI job.** Add Playwright to the frontend and a new
  CI job that runs the E2E specs headless against a throwaway test database with MinIO
  (reuse the existing test stack; never touch production data). Make this E2E job
  **required for merge**. NOTE for whoever executes this later: this introduces
  Playwright (a new dev/test dependency) and a new CI job — Reda has already approved
  both, so proceed without pausing to re-ask.

- [ ] **E2 — Login is the app entry point.** A valid login lands in the app; an
  invalid login is rejected.

- [ ] **E3 — Lead lifecycle.** Create a lead, confirm it appears in the list and on
  the kanban, open it.

- [ ] **E4 — Devis from a lead.** From a lead, generate a devis (automatic and
  modifiable), confirm the PDF preview actually renders (no broken-file icon), the new
  devis appears in that lead's devis list, and download works.

- [ ] **E5 — Inline bill editing.** Inline bill editing on a lead saves and reflects
  correctly.

- [ ] **E6 — Lead reassignment.** Reassignment works both from the lead view and from
  a kanban card.

- [ ] **E7 — Stage transitions.** Moving a lead between stages works, including into
  Signé.

- [ ] **E8 — Employee management.** Create/edit an employee, upload a photo, and reach
  the password-reset action.

- [ ] **E9 — Typed activities.** Log an activity and see it in the cockpit view.

- [ ] **E10 — File attachments.** Attach a file to a record, confirm the upload
  succeeds and the file can be opened/downloaded afterward.

- [ ] **E11 — Duplicate detection.** The doublons view renders and merging a cluster
  completes.

- [ ] **E12 — Credit notes (avoirs).** An avoir can be created from a posted invoice.

- [ ] **E13 — Payment follow-ups & receivables.** Payment follow-ups, aged
  receivables, and a customer statement all render.

- [ ] **E14 — Paramètres.** Paramètres pages load, and changing a setting saves and is
  reflected.

- [ ] **E15 — Cross-cutting health.** Assert no broken images and no uncaught console
  errors on the key pages.

- [ ] **E16 — Mobile pass.** Run a subset at iPhone viewport width asserting no
  horizontal overflow and that the full navigation menu is reachable.

---

## DONE LOG (agent appends one plain-language line per completed task)

- 2026-06-17 — A2: déplacer un lead dans « Signé » (glisser-déposer kanban ou
  édition en place de l'étape) ouvre désormais un dialogue qui demande QUEL
  devis du lead a été accepté et, pour un devis à deux options, laquelle
  (Sans batterie / Avec batterie). Confirmer marque ce devis « accepté »
  (réutilise A1) ce qui fait avancer le lead en Signé côté serveur. Si le lead
  n'a aucun devis, un message invite à en créer/choisir un d'abord et l'étape
  n'est PAS modifiée — aucun devis inventé. Nouveau filtre serveur
  GET /ventes/devis/?lead=<id> (borné à la société) + composant SigneDialog.
  L'étape du funnel (STAGES.py) et le statut du document restent séparés.
- 2026-06-17 — A1: accepting a devis now records the option the client chose
  (Sans batterie / Avec batterie) alongside the date and accepter name, logged in
  the devis chatter. Two-option devis require an explicit choice; single-option
  devis infer it. New additive field `Devis.option_acceptee` (blank by default →
  behaviour unchanged until used); the « ✓ Accepter » button asks for the option
  on two-option devis and shows it once accepted. CI green, shipped to main.
