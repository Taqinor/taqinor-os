# Taqinor OS — Build Plan & Progress (overflow queue, PLAN2)

This is the **overflow queue**. A run that finishes every `[ ]` task in `docs/PLAN.md`
continues here and works through every `[ ]` task in this file the same way (verify it
isn't already built, build it completely with tests, obey every STANDING RULE in `PLAN.md`,
CI green, self-merge `dev` → `main`, tick it `[x]`, append a DONE LOG line). All the HOW TO
RUN and STANDING RULES in `docs/PLAN.md` apply here unchanged — this file only adds tasks.

> Added 2026-06-17 while the field-execution batch (PLAN.md F1–F24) was running on
> `dev-field-exec`. Per the founder's "add to plan" convention, new tasks go here while a
> run is in progress so `PLAN.md` is never touched mid-batch.

---

## BUILD QUEUE (do top-down — highest value first)

### Group A — Devis acceptance, wired to Signé, facture & chantier (core unblock)

- [ ] **A1 — "Marquer comme accepté" control on a devis.** Add the status control that's
  currently missing directly on a devis. Accepting records **which option the client chose**
  (Sans batterie / Avec batterie), the **acceptance date**, and **who accepted**, written to
  the devis/lead **Historique** (chatter). Add the small devis fields needed to store these
  (acceptance date, chosen option, accepted-by). Preserve the existing devis status layer
  (`brouillon`/`envoye`/`accepte`/`refuse`/`expire`) — this sets `accepte` and records the
  option + metadata; it does not invent a new status layer.

- [ ] **A2 — Moving a lead into Signé prompts for the accepted devis + option.** When a lead
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

---

## DONE LOG (agent appends one plain-language line per completed task)

- *(none yet — appended as Group A–D tasks land)*
