# Agricole (pompage solaire) quote redesign — design

**Date:** 2026-06-24 · **Branch:** `feat/agricole-quote-redesign` · **Status:** approved in concept, building.

Owner ask (Reda, founder, non-coder): lift the agriculture quote generator to "the best in
the world". Specific complaints: (1) page-1 KPI cards stack one-on-top-of-another; (2) page 2
has a big empty space; (3) the monthly water bar graph should go; (4) numbers must be clear and
**almost zero-technical** because the audience is farmers; (5) even the minimum technical content
must be fact-checked. Founder authorised: adding new client inputs to the ERP and changing the
calculation. Work stays on a branch, rendered through the prod-identical image, iterated until he
is satisfied, then merged.

Approved scope: **Full — real & personalised.** Redesign the 4-page PDF **and** capture the farm
data (guided/encouraged, not strictly required, every field defaulted) and wire it to the existing
FAO-56 engine so water/hectares/savings become the client's real numbers.

---

## 1. The principle (research-backed)

A farmer feels **water, land, money** — not kWh. Across FAO/IWMI/World-Bank adoption studies and the
best solar-irrigation sellers (SunCulture, Lorentz, Futurepump), energy in kWh is the *least*
meaningful number to a farmer. So:

- **Hero numbers = water/day + money saved/year.** Total solar energy stays small (credibility stat),
  NOT the headline — this deliberately overrides the founder's first instinct ("energy big"), with his
  blessing ("do your due diligence").
- **One big idea per page**; reserve heavy weight for 1 hero number per page; everything else small/grey.
- **Tangible pictograms** (jerrycans 20 L, citernes, butane bottles) using the ISOTYPE discipline:
  repeat identical small icons with a "× N" multiplier — **never scale one icon up** (clip-art tell).
- **Kill the monthly water bar graph.** Replace with: hero water number + jerrycan/citerne equivalence
  + a one-line **payback "crossover"** ("remboursé année N, ensuite l'eau est quasi gratuite à vie").
- **Lorentz's most persuasive line, adopted:** *"Même au mois le moins ensoleillé, votre installation
  donne plus d'eau qu'il n'en faut."* One sentence replaces a spec table.
- **Translate the one surviving technical fact:** HMT → "on monte votre eau à ≈ X m — comme un immeuble
  de N étages"; flow → "remplit un bassin de 1 000 L en ≈ M min". No bare acronyms (HMT/kWc) as headlines.

### Messaging guardrail (legal/reputational, Morocco 2024-2026)
90% of Moroccan wells are unauthorised; selling "free unlimited water" is reputationally and legally
risky. Frame solar as an **energy swap that LOCKS the pumping cost**, paired with drip — *"same water,
far cheaper, locked for 25 years"*, never "pump as much as you want for free". The quote states it
**assumes a valid ABH forage authorisation** (client's responsibility).

### Trust block (what closes a Moroccan farmer)
Taqa-Pro Pompage Solaire label (if held), named warranties (panneaux 25 ans · pompe 7–10 · variateur
10–12), explicit SAV / local presence, and a *"nous montons votre dossier de subvention FDA"* offer.
French body; **Arabic gloss on the 3 decision numbers** (total TTC, économie/an, amortissement).

---

## 2. Fact-check of the engine (what's already right vs. what to fix)

Read of `apps/ventes/quote_engine/agricole/constants.py` + `economics.py` (the real code, not the
research's guess): **the engine is sound and already on the 2026 research base.** Validated by research:

| Item | In code | Verdict |
|---|---|---|
| Solar array oversize 1.4× | `solar.js` champFromKw | ✅ industry-standard (1.2–1.5×) |
| Hydraulic sizing / HMT | debitAtHmt curve interp | ✅ correct (ensure HMT includes friction) |
| FAO-56 Kc (olivier .70, agrumes .65, maraîchage 1.05, dattier .95, céréales 1.15) | agronomy.js | ✅ FAO-matched |
| Drip/aspersion/gravitaire eff. 0.90/0.75/0.55 | agronomy.js | ✅ (FAO surface 0.60; 0.55 is safe) |
| Diesel 13.5 MAD/L | constants.py | ✅ ≈ today's 13.55 avg (overridable) |
| Butane 50 subv / 128 réel / 78 subvention | constants.py | ✅ honest real-cost framing |
| Cost/m³ solaire .44 / butane .76 / diesel 1.67 | constants.py | ✅ 2016-vintage ratios; hold & widen |
| FDA 30% / cap 30 000 MAD | constants.py | ✅ correct (per project, coupled w/ drip) |
| Specific yield 1650 kWh/kWc | constants.py | ✅ conservative (Maroc 1600–1900) |

**Actionable (small):**
- A1. Label **arganier Kc 0.55** and **luzerne 0.95** as *engineering estimates* (arganier has no FAO
  entry; luzerne 0.95 is the season-average, not the instantaneous peak). Copy/labelling only.
- A2. Keep butane copy on the honest framing (*"coût réel ~128 DH, subvention en cours de
  décompensation, gel temporaire et fragile"*). Do **NOT** print "70 DH en 2026" as fact (frozen twice).
- A3. Optional: bump diesel default 13.5 → live (it's flagged "à relever"; overridable from Paramètres).
- A4. FDA wording on PDF: *"30 %, plafonnée à 30 000 MAD par projet, pompage couplé à l'irrigation
  localisée, sous réserve d'éligibilité"*; surface the stackable drip subsidy (80–100%, ~23 000 MAD/ha)
  as a separate informational line.

**The real gap (not a wrong number):** `economics.compute` already *reads* `surface_ha`, `crop`,
`current_fuel`, `irrigation_method`, `region`, HMT breakdown from `etude` — **but the frontend form
never writes them**, so it silently uses generic fallbacks. Capturing them is the lever.

### Water tangibility anchors (new — to add)
1 m³ = 1 000 L = **50 bidons de 20 L** = 1 cuve IBC. Camion-citerne ≈ 10–20 m³. 1 mm sur 1 ha = 10 m³.
Peak crop demand 5–8 mm/j = 50–80 m³/ha/j → ≈ **150 m² par m³/jour** au pic (label "au pic, approx.").
1 m³/jour ≈ eau de boisson de ~50 bovins / ~200 ovins. (These are *new* display devices; the existing
`hectares_irrigable = annual_m3 / crop_m3_per_ha` is sound and stays.)

---

## 3. Data model — new farm inputs (capture → store → consume)

The capture layer is the new work. `etude_params` is the contract `economics.compute` already consumes.

**New form fields (agricole mode), guided/encouraged, all defaulted:**

| Field | etude_params key | Default | Drives |
|---|---|---|---|
| Région | `region` | from address / souss-massa | ET0, crop default, sun |
| Culture | `crop` | region default | Kc → water need; framing |
| Surface irriguée (ha) | `surface_ha` | — (nudge) | water volume, hectares, savings |
| Mode d'irrigation | `irrigation_method` | goutte | efficiency → gross water |
| Source d'énergie actuelle | `current_fuel` | butane | savings & payback baseline |
| Dépense carburant (DH/mois ou /an) | `fuel_spend_current` (new) | derived | real savings vs. their bill |
| Profondeur forage/puits (m) | `profondeur_m` | region typ. | HMT, schematic |
| Niveau statique (m) | `hmt_static` | — | HMT breakdown |
| Niveau dynamique / rabattement (m) | `hmt_drawdown` | ~15% static | HMT breakdown |
| (existing) HMT, débit, CV, heures, type, alim, distance | unchanged | | sizing |

- `fuel_spend_current` is a **new** optional input: when given, savings are computed against the
  farmer's *actual* bill (strongest close) rather than the modelled fuel cost. Add it to
  `economics.compute` as an override of `annual_fuel_now`.
- FAO-56 readout on screen: surface the computed peak water need (m³/jour) from `agronomy.js` next to
  the chosen pump's m³/jour so the salesperson sees coverage ("la pompe couvre le besoin").
- Storage path unchanged: `autoQuote.js buildEtudePompage()` → `Devis.etude_params` (JSON). No new
  Devis columns required; all new keys live inside the existing `etude_params` JSON.

---

## 4. Page-by-page redesign (target: 4 pages)

Page count decision: **4** (cramming into 3 is a documented "cheap" tell; the content needs room).
Enforced in `tests/test_quote_engine.py` — keep the assertion at 4.

**Page 1 — La promesse (≈ zero technical).**
Cover: client name + the **two hero numbers** in serif display 64–96pt:
- Eau/jour (huge) → tangibility row: ≈ N bidons 20 L · ≈ K citernes · ≈ X ha (au pic).
- Économie/an (huge, accent) vs current fuel; small Arabic gloss.
Stat row = **clean 3-across grid** (fixes the "stacked cards"). Small credibility chips: kWc, garanties.

**Page 2 — Pourquoi ça marche (fills the empty space; no bar graph).**
- Payback **crossover** one-liner + simple cost-vs-savings cross marker ("profit dès l'année N").
- Reassurance card: *"même au mois le moins ensoleillé, plus d'eau qu'il n'en faut."*
- Clean **sun → panneaux → pompe → bassin → champ** schematic (reuse `schematic.py`, simplify: uniform
  flat line icons, ≤2 colours, no crossing lines, one-word labels).
- The single translated technical block (lift height "comme un immeuble de N étages", fill basin in M min).

**Page 3 — Équipement, prix & confiance.**
Equipment table + transparent chain (Sous-total HT → Remise → Total HT → TVA → **Total TTC**). Around it:
warranties row, SAV/local-presence line, FDA subsidy line (A4 wording) + stackable drip note, Taqa-Pro
badge if held. Price shown calmly (anti-pattern: don't shout the lump sum).

**Page 4 — L'engagement (close).**
Conditions (validité, paiement, TVA), the 4 next steps, signature "Bon pour accord" block, CTA with
sign URL + Arabic gloss on the 3 decision numbers.

### Design system (print CSS / WeasyPrint 62.3)
- Type: serif display (Playfair, bundled) for hero numbers/titles; humanist sans (DM Sans) body/tables.
  Scale: hero 64–96 · title 28–34 · subhead 18–21 · body 10.5–12 · caption 8–9 pt.
  `font-variant-numeric: tabular-nums lining-nums` on every figure/price column.
- Spacing: 8-pt scale {4,8,12,16,24,32,48,64}; internal ≤ external; **keep 6–8 mm clearance above the
  fixed footer** (known WeasyPrint footer-collision; never full-height pack).
- Colour: 60-30-10. White canvas, ink/grey structure, **one** accent (brand Majorelle blue) on hero
  outcome / payback marker / CTA only. No rainbow, no 3D, no glossy droplets.
- Charts/visuals: replace matplotlib monthly bars with flat SVG pictograms + a single payback crossover.
  Keep matplotlib only where a clean comparison helps (solar vs butane vs diesel annual cash) — flat,
  zero-baseline, single colour per category, value labels, no gridline clutter.

---

## 5. Implementation phases

1. **Render harness (parity):** render `sample_data` scenarios via `renderer.render_pdf_bytes` inside
   the `taqinor-django-prod` image (Python 3.11.11 / WeasyPrint 62.3); rasterise pages to PNG (PyMuPDF)
   for self-QA. Non-committed scratch script. Baseline-render the CURRENT PDF first.
2. **PDF presentation redesign** (the bulk, self-contained in `agricole/`): theme/spacing, cover (hero +
   3-across grid + tangibility), study (payback crossover + reassurance + schematic + translated spec,
   NO bar graph), yield (trust block), economics_page (close), charts→pictograms. Iterate via harness +
   self-QA, then show founder. Keep page count = 4.
3. **Farm-data capture (frontend):** add the §3 guided inputs to the agricole creation screen
   (`DevisGenerator.jsx`), store via `autoQuote.js` into `etude_params`; surface the FAO-56 coverage
   readout from `agronomy.js`.
4. **Calc wiring (backend):** `fuel_spend_current` override + A1/A2/A4 copy/label honesty in
   `economics.py`/constants/agronomy; ensure new etude keys flow through `compute`.
5. **Tests:** page-count (=4) per format, "no bar graph" / pictogram invariants, curve-less degrade path
   still clean, new economics override, Kc-label honesty. Run `apps.ventes.tests.test_quote_engine` in
   the prod image. CODEMAP refresh if models/endpoints/routes move (likely none — JSON-only).
6. **Self-QA pass** over every rendered page (all 3 scenarios + curve-less + no-farm-data fallback)
   before showing founder; then merge once he's satisfied (single PR, 4 CI checks green).

## 6. Risks / guardrails
- WeasyPrint footer collisions → enforce bottom clearance token; self-QA every page bottom.
- "Never invent a number" rule: curve-less pump (no m³/jour) must still degrade cleanly (no water hero,
  no fuel chart) — preserve existing degrade path.
- Status preservation (CLAUDE.md rule #4): engine RENDERS only, never changes devis status.
- Multi-tenant: new inputs live in `etude_params` JSON; no company-scoping change.
- Legal: ABH-authorisation assumption line on the PDF; no "free unlimited water" copy.
