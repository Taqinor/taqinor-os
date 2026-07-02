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
