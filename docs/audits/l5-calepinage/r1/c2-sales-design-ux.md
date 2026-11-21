# C2 - Sales-design UX research (2026-11-20)

Budget: 14 WebSearch used (cap 22), ~30 WebFetch. Help centres of Aurora and OpenSolar returned 403 (support.opensolar.com, help.aurorasolar.com), Capterra/G2 review pages 403 -> I used vendor marketing pages, search-result digests and the OpenSolar blog instead. Everything marked "(vendor)" is marketing, "(opinion)" is mine or a reviewer's. "non verifie" = could not confirm. Not covered at all: Sunbase, Google "digital twin" viewers, Mapbox Studio/SketchUp Web/Figma pattern pages (partial or failed).

## 1. Per tool: flow, automation, manual work, time claims

**Aurora Solar** (https://aurorasolar.com/aurora-ai/ , https://aurorasolar.com/sales-mode)
- Flow (Sales Mode): address + one utility bill -> AI 3D roof model -> design/adjust live -> web proposal. Step names/count: non verifie (help article 403).
- Auto: 3D model from HD (Nearmap) imagery + LIDAR shading data; NREL-validated engines (vendor page). Search digest of help centre: needs both HD imagery AND LIDAR at the address, residential only (https://help.aurorasolar.com/hc/en-us/articles/12290612935699 - quoted via search, page itself 403).
- Manual: live design edits with homeowner, price/financing tweaks.
- Time (vendor): "under 10 seconds" for the 3D model; customer testimonials "<5 minutes" proposal (Solaris) and "less than three minutes" (sales lead) - testimonials, not benchmarks. Press release says 30 s (older) - sources disagree.
- Reality check for us: AI mode requires LIDAR + HD imagery -> not usable in Morocco as-is (opinion, consistent with the stated constraint).

**OpenSolar 3.x** (https://www.opensolar.com/auto-design/ , https://www.opensolar.com/3ddesign , blog https://www.opensolar.com/post/quality-improvements-in-opensolar-3-0/)
- Auto Design flow per help-centre digest: open Design tab -> choose imagery (Google Solar 3D / Nearmap 3D, or draw roof facets yourself) -> add systems from panel (from saved template or recommendation) -> edit like a manual design. 4 steps (source: search digest of https://support.opensolar.com/hc/en-us/articles/13780099656719; page 403).
- Auto: rendered 3D, pitch/azimuth/shading, array placement, auto-stringing, shading heatmaps and shade reports, BOM (vendor page). Photogrammetry DSM.
- Manual: with no 3D imagery you sketch on 2D imagery; with no imagery a built-in modelling/measurement tool; roof planes/obstructions; assign panel models per array.
- OS 3.0: "Measure-to-resize for uploaded imagery", overhauled roof/wire drawing with snapping, multiple panel types, refreshed UI language (blog). 
- Time (vendor): Ada designs "in seconds"; customer "a few minutes". Measured by OpenSolar itself: residential 2D imagery flow 107 s -> 73.6 s incl. proposal review; auto-stringing >20 s -> 1-5 s (blog).

**Solargraf (Enphase)** - 3D-oriented, NREL compared its shading against on-site (https://www.nrel.gov/docs/fy24osti/87412.pdf, via search). Flow steps: non verifie. Capterra 3.2/5 from 15 users, "learning curve" (search digest of https://www.capterra.com/p/224635/Solargraf/reviews/, page 403 - opinion).

**Pylon** - Vendor claim: flat 2D design surface "faster than 3D-rotation tools, especially on touch devices"; hi-res proposal "in under 2 minutes" (via search digest of vendor pages; direct URL not fetched -> treat as vendor claim, non verifie). G2: only 2 reviews (https://g2.com/products/pylon-solar-design/reviews).

**Reonic** (https://reonic.com/en-gb/product/360h/planning/) - 6-step planning flow: 1 capture roof (Google Solar 3D, Google Earth 3D tiles, drone photogrammetry, OSM, orthophotos or architect plan; then draw surfaces/obstacles/setbacks) -> 2 module layout (auto-fill then edit) -> 3 3D shading+yield (score 0-10 per panel) -> 4 inverter + auto-routed strings (checks string current) -> 5 single-line diagram -> 6 offer PDF with 3D views, BOM, profitability page. "Optimize Layout" is "typically 80 to 90% of the final layout" (vendor). Drone -> 3D model "15 to 45 minutes". "Quick Planning" priced proposal "in minutes" from few inputs (vendor).

**Eturnity** (https://pv-magazine.com/2025/05/09/eturnity-adds-more-pv-design-automation-energy-system-project-control-to-its-software/ ) - 2D/3D roof layout + new shading analytics; inverter/string tool auto-generates string plans, SLD, roof plans. No time claims. Roof auto-detection: not mentioned.

**ARKA 360** (https://arka360.com/design , https://www.g2.com/products/arka-360/features) - Design Studio for technical sales; "Instant 3D designs", real-time shading feedback, SLD/CAD export, web + PDF proposals. No step list, no time number (only "In Minutes!" marketing). G2 4.3/5 over 137 reviews; top complaint missing features (search digest).

**Scanifly** (https://scanifly.com/?p=9329 , https://scanifly.com/) - drone 150-300+ images -> to-scale 3D model; Viewshed shading "in seconds"; Simple vs Pro Design modes (admins can hide Finalize/report in Simple); keepouts and occluders manipulated in the 3D scene; project report PDF from top-nav Download without leaving the design space. Deliverable turnaround 3-5 business days (vendor, service). Mobile Field Ops app (iOS/Android).

**SolarEdge Designer** (https://www.pv-tech.org/solaredge-bolsters-design-tool-to-streamline-ci-rooftop-planning-process) - automates stringing (auto-string per design rules) and system expansion by duplicating wired blocks; does NOT automate layout generation; multi-select, copy/paste, edge alignment; commercial load profiles. "with one click ... completes the string design" (search digest of SolarEdge page).

**Huawei SmartDesign 2.0** (https://solar.huawei.com/en/smart-design/) - three actions: satellite-based layout with no site survey, automatic module placement, one-click electrical design; 3D site model + design report. Shading, AR, time claims: not mentioned. Layout can sync to installer phone app (vendor).

**PVcase / RatedPower / Virto** - PVcase Roof Mount "reduces design time by a minimum of 80%" (vendor, via search digest of https://pvcase.com/roof-mount); Ideematec "3x faster layout" (customer story). Step flows: non verifie. RatedPower called "fastest cloud feasibility" by a 2026 comparison (opinion, via search). Not relevant to a small residential/C&I team beyond the idea of generating variants.

## 5. Mounting/electrical configurators
- **K2 Base** (https://k2-systems.com/en/digital-services/k2-base/): free, 5 steps (Project, Roof, Draft, Loads, Results). Auto: wind+snow loads, fasteners and ballast; user draws roofs and arrays by hand; outputs: assembly plan, ballast plan, editable BOM, PDF, Excel, share link, export to SolarEdge/SMA/Fronius planning tools and distributor webshop carts. "In just five steps" - no minutes.
- **Sunny Design**: sections general settings / string design / roof planning (https://manuals.sma.de/SDesign/en-US/index.html). K2 Base has a "K2+" button to hand data over. String validation details and SLD automation: non verifie (a competitor-ish installer blog says SLD is weaker than SolarEdge's - opinion).
- **SolarEdge Designer**: see above (auto-stringing).
- **Huawei SmartDesign**: one-click electrical design (vendor).
- Takeaway (opinion): the bar is "draw/auto-fill -> one-click strings -> one export of BOM + plan + SLD", i.e. 3-5 steps.

## 2. Patterns that make them simple (sourced where possible)
1. Address/location first, 3D or layout generated automatically (Aurora, OpenSolar, Huawei, Reonic).
2. Auto-fill then manual correction ("80 to 90% of the final layout", Reonic vendor).
3. Template-driven auto design (OpenSolar saved templates).
4. Simple vs Pro modes with admin-hidden controls (Scanifly Simple/Pro Design).
5. Flat 2D canvas rather than 3D orbiting, touch-friendly (Pylon vendor claim).
6. One-click stringing (SolarEdge, Huawei, Reonic auto-routing).
7. Edit in the 3D scene: move/rotate keepouts directly (Scanifly).
8. Report/PDF without leaving the design screen (Scanifly top-nav Download).
9. Snapping on roof/wire drawing (OpenSolar 3.0 blog).
10. Live design with the client, guardrails keep it valid (Aurora Sales Mode: "guardrails" per search digest of the Sales Mode pages).
11. Imagery fallback ladder: 3D -> 2D sketch -> measure tool (OpenSolar).
12. Speed as a feature: OpenSolar cut auto-stringing from >20 s to 1-5 s and publishes the numbers.
13. Wizard with few named steps (K2 Base 5 steps; Reonic 6).
14. Quick vs full planning split (Reonic: quick priced proposal vs full 3D) - the page I fetched did not describe Quick Planning in detail; claim from the planning page only.
15. Real-time production figure while editing: Arka ("real-time feedback", vendor), Aurora EU page lists "real-time module placement" (search digest). Not independently verified in the UI.
Not verified in any tool: command palette, undo/versions UI, mobile design app for the design step (non verifie).

## 3. Beauty / persuasion features (with URLs)
1. Interactive web proposal with 3D site model, shareable link, any device (Aurora https://aurorasolar.com/sales-mode).
2. Sun-path animation, irradiance, shading analysis shown to homeowner (Aurora EU https://aurorasolar.com/eu/en/sales-mode/ via search).
3. Fully rendered 3D design, heatmaps and shade reports; shading across day/month/year (OpenSolar https://www.opensolar.com/3ddesign). "Photoreal" NOT claimed.
4. Per-panel shading score 0-10 + annual/monthly loss (Reonic planning page).
5. 3D proposal views, BOM, profitability page in the offer PDF (Reonic).
6. "Lifestyle presentations": electrified home vs cost of doing nothing (OpenSolar 3.0, https://www.solarpowerworldonline.com/2025/09/opensolar-3-0-offers-solar-design-lead-gen-and-workflow-services-for-free/).
7. Drone photogrammetry mesh, centimetre-accurate (Reonic; Scanifly).
8. Real-time onsite shading simulation GIF (Scanifly https://www.scanifly.com/shade-analysis).
9. 3D modelling animation and 3D proposal image (Arka https://arka360.com/design).
10. Dark UI, true-colour panels, AR, animated energy flows, typography, micro-animations: non verifie for every tool studied; treat as our own design opportunity (opinion).
Honest note: I found few public details of the visuals; screenshots/videos should be looked at directly in the vendors' demos.

## 4. Poor-imagery workarounds seen
- OpenSolar: sketch on 2D imagery; built-in modelling/measurement tool when no imagery; "measure-to-resize" for uploaded imagery in 3.0 (blog). Scaling help article 11460015672975 returned 403 - details non verifie.
- Reonic: import orthophoto, architect plan, drone photogrammetry, OSM; draw roof surfaces manually.
- Scanifly: drone + keepouts/occluders (tree removal).
- Phone LIDAR/AR: Polycam (HomeLink "cuts rework by 80%", vendor story https://poly.cam/customer-stories/homelink), Solmeus iOS, Azimutis iPad site-survey/roof-measure (https://apps.apple.com/app/id6745228060), Scanifly Mobile. No tool found that explicitly does "photo + reference object scale". NREL: airborne LiDAR within 3.5% of hand measurement (via search; not phone LiDAR).
- Recommended for us (opinion): typed dimensions + sketch-from-dimensions + upload of plan/screenshot with 2-point scale calibration (known distance) + measure-to-resize, plus a "visite" photo checklist.

## 6. Complaints (opinion, thin evidence)
- OpenSolar: interface "functional but outdated", steep learning curve / training needed (https://www.g2.com/products/opensolar/reviews , https://cleanenergyreviews.info/blog/best-solar-design-software-tool); design->proposal felt slow because of 25-year calculations (OpenSolar's own blog).
- Aurora: missing features, hard learning curve (2 reviews) (https://www.g2.com/products/aurora-solar, G2 4.7/121 reviews); no evidence of slowness found.
- Solargraf: initial learning curve, 3.2/5 on 15 reviews (Capterra via search).
- Arka 360: missing features, project sharing, wiring/earthing not shown (G2 via search).
- Pylon: one reviewer found the interface hard to pick up (G2, 2 reviews).
- Sunny Design: SMA-only, weaker SLD (heavily vendor-installer blog, opinion).
Trap list for us (opinion): learning curve, long calculations blocking the proposal, depending on 3D imagery that doesn't exist, Enphase/SMA-only catalogues.

## 7. Outside-solar bar (only what I could verify)
- tldraw https://tldraw.dev/features : multiplayer cursors, built-in undo/redo, align/distribute, smooth pan/zoom, keyboard and screen-reader support, dark mode + reduced motion, themes.
- Linear https://linear.app/docs/search : command menu section + `/` to search (Cmd+K not documented there).
- Figma https://help.figma.com/hc/en-us/articles/360040328653 : actions menu searchable by typing (keyboard-first).
- Arcol https://www.arcol.io/ : shared real-time model, metrics update instantly while comparing options.
- Rayon https://www.rayon.design/ : multiplayer, reusable blocks/templates/libraries, one tool for draw/3D/docs, fluid AI+manual editing.
- Mapbox Studio https://docs.mapbox.com/studio-manual/guides/ : visual interface to preview changes, built-in themes/templates gallery.
- SketchUp Web: page 404 - non verifie.
Ten patterns to copy (opinion, with source where above): 1 command/action search (Figma, Linear); 2 live shared model (Arcol); 3 instant metrics on change (Arcol); 4 undo/redo everywhere (tldraw); 5 align/snap helpers (tldraw, OpenSolar snapping); 6 templates/libraries (Rayon, Mapbox); 7 smooth pan/zoom; 8 dark mode + reduced motion (tldraw); 9 keyboard accessibility (tldraw); 10 preview-before-commit (Mapbox).

## 8. Benchmark proposal
- Time to first valid design (minutes from address/upload to a design with strings) - industry cites vendor numbers: Aurora <10 s model, OpenSolar 73.6-107 s flow incl. proposal (OpenSolar blog). Target (opinion): < 3 min typed-dimension flow.
- Clicks/inputs to quote: count required inputs; Reonic "few inputs", Aurora needs 2 (address + bill) (aurorasolar.com/aurora-ai).
- Task success / first-click success: binary completion with 95% CI (NN/g https://www.nngroup.com/articles/success-rate-the-simplest-usability-metric/).
- SUS: average 68; >80.3 = top 10% (A) (https://measuringu.com/sus/); reliable with very small samples but report the confidence interval.
- WCAG 2.2 AA contrast: 4.5:1 text, 3:1 large text (https://www.w3.org/WAI/WCAG22/Understanding/contrast-minimum.html).
- Responsiveness: INP good <= 200 ms, poor > 500 ms (https://web.dev/articles/inp). Frame rate 60 fps target during drag: non verifie source (opinion).
- Compute time: publish like OpenSolar did (auto-stringing 1-5 s).
- Tablet success on site: same tasks on a tablet.
