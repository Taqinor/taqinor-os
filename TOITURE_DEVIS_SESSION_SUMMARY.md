# TAQINOR — Toiture-3D → Devis loop: session summary

_Record of everything built, fixed, deployed and verified in this session (June 2026)._
_Plain-language for the founder; PR numbers + file paths for reference._

---

## 1. The goal

Turn the existing 3D roof builder (`/preview/toiture-3d-pro-11`) and the premium quote
into **one client → seller loop**:

1. **Client** (on the website) points at their roof on a map and gives their bill.
2. **Meriem** (in the ERP) designs the roof and generates a quote in one click.
3. **Client** receives a beautiful web proposal and **signs online**.

---

## 2. How the loop works now (end to end)

| Step | Where | What happens |
|---|---|---|
| 1. Capture | `taqinor.ma/devis/mon-toit` (public website) | Client searches their address → **drops a pin** on their roof (now **required**) → the address is **reverse-geocoded** from the pin → fills contact + bill (exact MAD, summer-≠-winter toggle, monophasé/triphasé/je-ne-sais-pas) → submits → a **Lead** is created in the CRM with the GPS pin + all data. |
| 2. Design | ERP `api.taqinor.ma/devis-design/<lead>` (Meriem, logged in) | She clicks **"🏠 Concevoir la toiture (3D)"** on the lead → the design tool opens **inside the ERP** (her existing session, no second login) → the client's pin is shown as a **brass marker** → she draws the roof → **one button** ("Générer le devis & envoyer au client") creates the quote from the real design + uploads the 3D snapshot + shows a "Prêt à envoyer" panel (WhatsApp / Email / copy). |
| 3. Proposal | `taqinor.ma/proposition/<token>` (public, client) | Premium page: 3D roof render hero, facture avant→après, **production-vs-consumption chart**, options, the explicit HT→TVA→TTC chain, **"Télécharger le devis (PDF)"**, and a **"Signer en ligne"** CTA. |
| 4. Signature | same page | Client types their name + "Bon pour accord" → the quote flips to **accepté** (through the existing acceptance service — the bon-commande/facture chain is preserved). |

---

## 3. What was built / fixed (by PR)

- **PR #235 — the loop foundation.** Backend `Group Q` (Devis↔Toiture-3D) + the website halves W112–W118: client pin-capture page, Meriem design page, the **`POST /api/django/ventes/devis/from-layout/`** endpoint (turns a finished 3D layout into a real quote + mints a public proposal token), the tokenized proposal data + e-sign endpoints, the web proposal page and in-page signature. _(Found & fixed a real CI bug: `from-layout` required admin instead of responsable — Meriem could never have generated a quote.)_

- **PR #243 — richer capture + better client proposal.** Exact bills + summer-toggle + raccordement (incl. "je ne sais pas") on the capture form; **reverse-geocoded address** from the pin; the new fields flow onto the lead; the **CRM "Concevoir la toiture (3D)" button**; the **one-click "Générer & envoyer"**; the client proposal **3D render hero + production-vs-consumption chart + PDF download**; backend `monthly_production`/`monthly_consumption` (real figures only — annual × Morocco GHI weights, bills × the existing 1.75 MAD/kWh — empty when no data, never invented).

- **PR #246 — moved the design tool INTO the ERP.** The tool was wrongly a **public** page with its own login (which could never work: the ERP uses httpOnly session cookies + it was on the wrong domain). Now it's an **authenticated ERP page** (`/devis-design/:id`), same origin as `api.taqinor.ma`, so **Meriem's existing login just works** — and it's not public. The 3D builder is **imported** from `apps/web` (not duplicated); the old broken public page was removed; a same-origin `GET /api/django/ventes/roof-config/` serves the public map key.

- **PR #249 — production build fix.** The ERP frontend image built from only `frontend/`, so on the server `npm run build` failed (it couldn't import the builder from `apps/web`). Switched the frontend prod image to the **repo-root build context** (+ a root `.dockerignore`). Verified with a local docker build.

- **PR #250 — two flow bugs.** (1) The capture form let clients submit **without a pin** → leads had no position → the design tool had nothing to center on. Now the **pin is required**. (2) The ERP's **Content-Security-Policy blocked the map servers** (`api.mapbox.com`/`api.maptiler.com`) → blank map inside the ERP (the website/Cloudflare had no such limit). Added the map providers to the CSP + `worker-src 'self' blob:`.

- **PR #251 — pin marker + real wattage** _(merged + deployed)._ (1) The design map centered on the client's pin but drew **no marker** → now drops a **brass marker** at the client's spot. (2) The auto-quote could show **"450 W"** panels (a stale `_DEFAULT_WATT` fallback); the real seeded catalogue panel is **710 W** (Canadian Solar / Jinko), so the fallback is now **710** — the quote reflects the real catalogue, never an invented 450.

- **PR #252 — reliable auto-centering on the client's pin** _(merged + deployed)._ The ERP design map opened **Morocco-wide** instead of landing on the client's roof (the camera move raced the React container layout and a late resize reset it to the default). Now it `resize()`s, `jumpTo`s to the pin instantly, and re-asserts on map `idle` — so **Meriem lands right on the client's roof with the pin marker visible, every time**. Verified live.

### ✅ Final verified state (live)
The full loop works end to end on production: client pin-capture → CRM lead with GPS →
Meriem opens the lead and **the map auto-lands on the roof with the pin marker** →
she draws the roof → **solar panels render in 3D on the roof** → one button generates the
quote (real 710 W catalogue panels) → the panels-on-roof image + the proposal go to the
client → the client signs online.

---

## 4. Deploys & configuration

- **Website** (`apps/web`) auto-deploys on merge via **Cloudflare** — no action needed.
- **ERP** (Django + React on Hetzner) does **NOT** auto-deploy — brought live with
  **`scripts/deploy-prod.ps1`** (run several times this session).
- **MapTiler / Mapbox keys** were added to the ERP server `.env`
  (`PUBLIC_MAPTILER_KEY`, `PUBLIC_MAPBOX_TOKEN`) — the same **public** keys the website
  uses (verified valid on the `api.taqinor.ma` domain). The map config is served
  same-origin by `GET /api/django/ventes/roof-config/`.

---

## 5. What was verified live (in the browser / on prod)

- ✅ Full **end-to-end** once: website capture → Lead in CRM → `from-layout` → real Devis
  (DEV-202606-0085, real catalogue lines) → public proposal renders → **signed online**
  → quote flipped to *accepté* (through the real Cloudflare-Worker → backend path).
- ✅ The **design tool renders inside the ERP** (logged in as Reda, lead + pin loaded,
  no second login).
- ✅ The **ERP map now loads satellite tiles** (after the CSP fix) and navigates.
- ✅ The website→ERP **lead pipe works** when the form is fully filled (a name-only
  submit is correctly rejected with field errors).

---

## 6. Known follow-ups / notes

- **Auto-center:** ✅ RESOLVED (PR #252) — the map now reliably lands on the client's
  pin at building zoom with the marker visible (verified live).
- **`_DEFAULT_WATT` = 710** is a *fallback*; the normal auto-quote already writes the
  real product designation, so the true wattage is read from the catalogue line.
- A separate `apps/ventes/solar_design.py` keeps `puissance_w = 450` for DC-string
  voltage math only (not the client-facing panel) — intentionally left.
- **Test data:** a demo lead **"PIPE TEST Reda"** (id 34, TAQINOR Démo company) + its
  quote DEV-202606-0085 were created to test/verify — delete them when convenient.

---

## 7. Key locations (for reference)

- Website pages: `apps/web/src/pages/devis/mon-toit.astro`,
  `apps/web/src/pages/proposition/[token].astro`, `apps/web/src/pages/api/capture-lead.ts`,
  `apps/web/src/pages/api/proposition-accept.ts`.
- 3D builder (shared): `apps/web/src/scripts/roof-tool-pro11.ts` + `apps/web/src/scripts/roofPro11/*`.
- ERP design page: `frontend/src/pages/ventes/ToitureDesign.jsx` (route `/devis-design/:id`),
  CRM button in `frontend/src/pages/crm/LeadForm.jsx`.
- Backend: `apps/ventes/views/devis.py` (`from-layout`, `share-link`, `roof-image`, `layout`),
  `apps/ventes/services.py` (`build_devis_from_layout`), `apps/ventes/public_views.py`
  (`proposal_data`, `proposal_accept`, `proposal_pdf`), `apps/crm/webhooks.py` (lead intake),
  `apps/ventes/quote_engine/builder.py` (quote data + the wattage default),
  `apps/ventes/views/roof_config.py` (map key).
- ERP CSP: `backend/nginx/nginx.conf`. Frontend prod build: `frontend/Dockerfile.prod`
  + root `.dockerignore`.
