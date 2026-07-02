# Estimateur toiture pro-11 — notes moteur WJ20–WJ24

Rationale + sources of the engine extensions landed by the 3D-ESTIMATOR-ENGINE lane
(WJ20–WJ24), on top of WJ19 (shadow-tracing shading). **Every figure below traces to
PVGIS, a founder-confirmed tariff, a documented physics constant, or sound geometry —
no invented numbers.** All engine extensions on `estimatorBrainV2`/`V3` are ADDITIVE and
gated behind an opt-in option so pro-3/4/5 default behaviour is byte-identical.

---

## WJ20 — One-click auto-layout (`fillAll`)

**What it is.** A single « Remplir automatiquement » action that fills the traced roof
with panels in one gesture, so a visitor/seller never hand-places panel-by-panel.

**Why it's pure geometry on data we already have.** The layout editor (W69) already
builds a *lattice* = exactly the list of `PackedPanel` cells produced by the optimizer's
`packConfig`/`packCells`. Each lattice cell is **guaranteed by construction** to be:
inside the traced polygon, inside the perimeter setback, clear of every obstacle no-go
zone (with clearance), non-overlapping, coplanar on pitched roofs. So "fill the whole
roof" is simply: occupy every lattice cell.

`fillAll(state)` (in `src/lib/layoutVariability.ts`) occupies every cell index. Because
the lattice is the geometric packing, the hard footprint bound **Σ panel footprints ≤
usable roof area** holds automatically (you can never occupy more than what physically
packed). The need (bill) does NOT cap this action — it is deliberately "place the maximum
that fits"; the UI note honestly flags when the count exceeds the bill-derived need
(surplus production is not remunerated in Morocco → self-consumption-first savings, see
WJ23), and invites the user to remove panels with « − » to match the need.

No new production number is invented: moving/adding panels in the same plane keeps
per-panel yield identical (same tilt/azimuth/GPS); only the count changes, recomputed via
the existing PVGIS-by-count path.

---

## WJ21 — Sun-path animation + irradiance heatmap

**Sun-path (already present, reused).** The 3D scene already positions a REAL sun by
`ctx.sunHour` (6–18 h) and `ctx.sunDay` (season), driven by the W87 « Heure du soleil »
scrubber + winter/summer toggle. This is a MANUAL scrubber (no auto-play), so it is
`prefers-reduced-motion`-safe by construction — the user drags time/season and shadows
move; nothing animates on its own. WJ21 keeps that and adds the heatmap.

**Irradiance heatmap (« Carte d'accès solaire »).** Colours each roof panel by its REAL
relative annual solar access — not arbitrary colours. Method (pure astronomy + PVGIS,
no API):

- **Solar access of a point** = the fraction of ANNUAL irradiation that actually reaches
  it once traced shading obstructions block the *direct* sun (the diffuse ~25 % stays).
  This is exactly the WJ19 production-derate model, evaluated **per panel** instead of at
  the centroid: `pointSolarAccess` computes the 12×24 hourly shade matrix seen from that
  point (`hourlyShadeFactors`, real astronomy `sunDirection`) and weights each hour by the
  energy it carries using the real PVGIS typical-day profiles (`applyShadeFactors`), then
  divides derated ÷ intact annual kWh.
  - Bounds proven by tests: `diffuseFraction ≤ access ≤ 1`; a fully clear point = 1.0; a
    point far from an obstruction receives ≥ what a near point receives (monotone).
  - No obstruction, or no usable production → access 1 everywhere (uniform "full sun",
    honest — nothing is invented).
- **Colour mapping** (`solarAccessColorRGB`) is a continuous RED (low access) → AMBER →
  GREEN (full sun) gradient, monotone and tied to the true access value: access=1 → green,
  access≈diffuse → red. Applied to panel instances via the existing `instanceColor` buffer
  (W88 mechanism) — `MeshStandardMaterial` multiplies its colour by `instanceColor`.
- After any re-render that recreates the panel instances (sun scrubber, season toggle,
  obstruction change), `refreshHeatmap()` re-applies the tint so the heatmap survives.

Because the heatmap and the annual production derate share the same model, the colours a
seller shows on the roof are consistent with the savings numbers on the card.

---

## WJ22 — Honest climate-loss layer (confidence band)

**Problem.** PVGIS PVcalc already returns production net of a generic 14 % system loss.
But on the Moroccan coast in SUMMER the real yield is over-stated by ~15–20 % because
three losses exceed the PVGIS default: module temperature derate, dust/soiling, and
diffuse/haze (coastal veil). WJ22 applies these documented extra derates and renders the
result as a CONFIDENCE BAND, not a single number.

**Additive + opt-in.** All logic lives in new EXPORTED functions in `estimatorBrainV2.ts`
that NO existing path calls (`recommend`/`productionKwh` untouched) → pro-4/pro-5
regression tests stay byte-identical (verified). The pro-11 card shows the band only when
the « Fourchette réaliste » toggle is on (`ctx.climateBandOn`, default false).

**Derate constants + sources (every figure documented):**
- `TEMP_COEFF_PMAX_PER_C = −0.0034` (%/°C). The real panel (Canadian Solar TOPBiHiKu7,
  `roofPro2`) is ≈ −0.29 %/°C; we use −0.34 %/°C, the conservative c-Si Tier-1 median, so
  we never under-state the thermal loss.
- `SUMMER_CELL_DELTA_T_C = 30` (°C above the 25 °C STC). Cell ~55 °C at summer coastal
  peak irradiance under moderate wind — consistent with a NOCT ~45 °C and the usual NOCT
  cell-temperature model. Conservative.
- `EXTRA_SOILING_LOSS = 0.03` (fraction, on top of PVGIS default). MENA soiling studies
  report 2–5 %/yr without frequent cleaning; 3 % is a prudent low bound.
- `HAZE_LOSS = 0.015` (fraction). Coastal marine veil reduces useful direct irradiance;
  ~1.5 %, documented low bound.
- `climateDerateFactor()` = thermal × (1−soiling) × (1−haze), each clamped to [0,1], ≤ 1
  (never a gain). Default ≈ 0.85 → ~15 % summer loss, matching the observed over-statement.

**Confidence band.** `productionConfidenceBand(annualKwh)` returns
`{ high = the bare PVGIS/estimate number, low = high × derate, point = √(low·high) }` so
`low ≤ point ≤ high` by construction (tested). The card shows production as a range and
savings as a range; the low-bound savings go through `annualSavingsMad(band.low, target)`,
so the low savings are **capped by the avoidable energy cost** — verified by test that even
a 3× over-sized production's low-bound savings never exceed `billMAD(target)` annualised.
