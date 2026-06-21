# Agricultural solar quote engine — design

**Date:** 2026-06-21 · **Branch:** `feat/agricole-quote-engine` (not merged to `main`)
**Author:** Reda (founder) + Claude

## Goal
Bring the agricultural (pompage solaire) quote to the same — and beyond — quality
as the residential quote: a premium multi-page proposal driven by the right
questions, with sizing logic, persuasive economics (incl. the Moroccan butane &
diesel angle) and a beautiful layout. Plus a task list to wire the new questions
into the ERP.

## What shipped on this branch (the engine)
A new `agricole/` renderer package, mirroring the proven `residential/` package,
selected for `mode_installation == "agricole"` in the full/premium format
(`backend/django_core/apps/ventes/quote_engine/agricole/`). The agricole one-page
format stays on the legacy engine (fast WhatsApp/field send).

**Four A4 pages** (consolidated 2026-06-21 from the original airy 5-page layout,
which is frozen on tag `agricole-quote-v5-5pages` / branch
`agricole-quote-v5-5pages-locked` — restore with `git checkout` if ever wanted):
1. **Cover / "En un coup d'œil"** — hero water/day number, "0 carburant",
   6 at-a-glance cards (débit, HMT, pompe, kWc, économie/an, amortissement),
   tangibility ("≈ X ha irrigués"), CO₂.
2. **Étude technique** — labelled system schematic (soleil → panneaux → variateur
   → pompe/forage → bassin → champ), the HMT breakdown, the sizing chain, AND the
   water-delivered + PV-production charts (folded up to fill the page).
3. **Équipement & investissement** — equipment table (brand/description/warranty),
   the transparent HT→remise→TVA→TTC chain + FDA 30 % subsidy side by side, and
   the garanties badges.
4. **Rentabilité & engagement** — **solaire vs butane vs diesel** annual cost +
   payback curve + the décompensation punch line + CO₂/fuel-avoided, then
   conditions + "Bon pour accord" signature + CTA.

Supporting modules:
- `economics.py` + `constants.py` — solar-vs-butane-vs-diesel, FDA subsidy,
  payback, CO₂, water/production monthly series. **Every rate is a founder-editable
  default flagged « à confirmer »** (reads a company Paramètres override when set).
  Solar burns no fuel → annual saving = the whole fuel bill eliminated.
- `charts.py` — matplotlib→PNG (water/month, production/month, fuel comparison,
  cost/m³, payback).
- `schematic.py` — pure inline SVG (immergé borehole with HMT dimension, or
  surface pump beside a well), degrades gracefully.
- `frontend/.../agronomy.js` — FAO-56 water-demand calculator (Kc × ET0 tables,
  livestock, irrigation efficiency) so a quote can be sized from crop + region +
  surface + method instead of a guessed pump CV. **14 vitest tests pass.**

Toggleable persuasion sections (founder choice): `show_subsidy`,
`show_fuel_comparison`, `show_environmental`, `show_schematic`, `show_water_yield`,
+ `current_fuel` (butane/diesel) — whitelisted in `clean_pdf_options`, default on.

## Safety / invariants kept
- `/proposal` stays the only client PDF path; statuses untouched (renders only).
- `prix_achat`/margin never appears in any client output (test-guarded).
- No invented numbers: a curve-less pump (no m³/jour) omits water economics and
  the payback rather than faking them (test-guarded).
- Pompage compositions still carry no battery/grid inverter.
- New deps: none (matplotlib/PIL/weasyprint already used by residential).

## Verification
- 3 real sample PDFs rendered (citrus/Souss-Massa, olive/Saïss surface pump,
  date palm/Drâa diesel) — each exactly 4 pages, no overflow:
  `docs/samples/agricole_4p/` (the locked 5-page set stays in
  `docs/samples/agricole/`).
- Backend tests: `apps/ventes/tests/test_agricole_quote.py` (selection,
  economics, toggles, no-invented-numbers, render content, 5-page WeasyPrint).
  Pure-Python parts verified locally; the WeasyPrint page-count test runs in CI.
- Agronomy: `frontend/src/features/ventes/agronomy.test.jsx` — 14/14 pass.

## Pre-merge (when the founder decides to merge)
- Refresh `docs/CODEMAP.md` + fingerprint (new package is a structural change).
- Add a real hero photo at `quote_engine/agricole/assets/hero.jpg` (optional).
- Wire the ERP questions — see `docs/agricole-quote-erp-tasks.md`.
