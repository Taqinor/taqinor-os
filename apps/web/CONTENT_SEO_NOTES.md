# CONTENT_SEO_NOTES — verified data for the FAQ / guides / blog (`apps/web`)

**Purpose.** This is the **cited evidence base** for the SEO content expansion (WEB_PLAN
W119–W139): the FAQ, the evergreen guides, the EV-charging pillar, and the dated blog. It exists
so the content tasks can use **real, sourced numbers** instead of inventing them — the web-plan
convention is "method, not client data, is committed" and rationale lives in `apps/web/*_NOTES.md`.

**Compiled 2026-06-21** from a parallel, citation-required research pass (five agents, each
cross-checking ≥2 independent sources, with confidence + freshness flags). Currency: **MAD (DH)**;
1 DH = 100 centimes; ~1 EUR ≈ 10.8 MAD.

## How to use this on the site (honesty rules)

1. **PUBLISH-SAFE vs VERIFY-FIRST.** Each figure below is tagged. **PUBLISH-SAFE** = high-confidence,
   well-corroborated, safe to state (as a range). **VERIFY-FIRST** = single-source, evolving, or
   founder-internal — write it qualitatively and label it *« à confirmer »* / *« fourchette
   indicative »*, or get the founder to confirm, before stating it as fact.
2. **Volatile vs stable.** **Stable** physics/spec numbers (irradiation kWh/kWc, optimal tilt,
   panel degradation %, LFP cycle life / DoD / efficiency, EV kWh/100 km) may appear in **evergreen
   guides**. **Volatile** market/regulatory numbers (MAD prices, ONEE tranches, buyback rate, fuel
   prices) belong in **dated blog posts** that signal freshness and get refreshed — link to them
   from the guides rather than hardcoding a price into an undated page.
3. **Ranges, not false precision.** Moroccan price data is installer/blog-sourced, not audited —
   always a range, always "indicatif".
4. **Taqinor's OWN prices/products stay founder-confirmed.** Market ranges here are context; the
   firm's quoted MAD figures come only from the founder / the quote engine.

---

## 1. Loi 82-21 — self-production framework (the load-bearing differentiator)

The honest core of the whole content cluster: **Morocco has capped net-billing, not net-metering.**
You self-consume on site; only a small surplus may be sold, cheaply. So solar value = **avoiding
the high retail tranches by self-consuming** (and storing / charging an EV from your own midday
surplus), **not** export revenue.

| Fact | Value | Tag | Source |
|---|---|---|---|
| Framework operative since | **9 June 2026** (Décret 2-25-100, B.O. 9 Mar 2026; ANRE Décision 04/26) | PUBLISH-SAFE (high) | energypartnership.ma; Le Desk; Fidal; Médias24 (18 Jun 2026) |
| Regime — **déclaration** | **< 11 kW basse tension** → simple declaration, récépissé within 1 month | PUBLISH-SAFE (high) | Le212; Fidal; energypartnership |
| Regime — accord de raccordement | **11 kW – 5 MW** (SRM/distributor agreement) | PUBLISH-SAFE (high) | same |
| Regime — autorisation | **> 5 MW** (ONEE technical opinion) | PUBLISH-SAFE (high) | same |
| Surplus injection cap | **20 % of annual production** | PUBLISH-SAFE (high) | Médias24; LesEco; Fidal |
| Buyback / rachat tariff | **0,21 DH/kWh peak · 0,18 DH/kWh off-peak** (ANRE 04/26) | PUBLISH-SAFE (high) | Médias24; LesEco; energypartnership |
| Net-metering? | **No** — net-billing only; buyback ≪ retail | PUBLISH-SAFE (high) | multiple |
| Penalties (no authorization) | 3 mo–1 yr + **100 000–1 000 000 DH** fines | VERIFY-FIRST (medium — exact article mapping not confirmed) | ecoactu.ma |
| Article 33 regularization window | transitional regime, **18-month** window anchored to 9 Jun 2026 entry-into-force | VERIFY-FIRST (medium — exact start-trigger) | Fidal; Médias24 |

Primary: ANRE Loi 82-21 PDF (anre.ma/.../Loi-82-21-BO_7400_Fr.pdf); ledesk.ma; fidal.com;
energypartnership.ma; le212news.ma; medias24.com; leseco.ma. *(NB: ONEE/Fidal/distributor portals
403-block automated fetch; figures triangulated from ≥2 independent extractions.)*

---

## 2. Electricity tariffs (what solar offsets)

ONEE residential basse-tension, **TTC**, current/2025 schedule:

| Monthly use | DH/kWh | Mode |
|---|---|---|
| 0–100 kWh | **0,9010** | progressive |
| 101–150 | 1,0732 | progressive |
| 151–200 | 1,0732 | sélective |
| 201–300 | 1,1676 | sélective |
| 301–500 | 1,3817 | sélective |
| > 500 | **1,5958** | sélective |

- **Key mechanic (PUBLISH-SAFE, high):** above **150 kWh/month** the bill turns **"sélective"** — the
  **whole** month is billed at the reached tranche's rate, so high consumers pay the high marginal
  rate on *everything*. This is precisely the cost solar removes. Above 500 kWh, **bi-horaire**
  (peak/off-peak) applies.
- **VERIFY-FIRST (evolving):** a **+5,5 % increase ~Oct 2025** may have moved the top tranches to
  **≈1,45 and ≈1,66 DH/kWh**; the decimals 1,0732/1,1676/1,3817 are medium-confidence. ANRE tariff
  reform may push further 2027 changes. **Re-check a current bill before quoting.**
- **Distributors (Lydec/Casablanca, Redal/Rabat, Amendis/Tanger):** same **structure** as ONEE;
  exact per-tranche decimals **NOT verified** (portals 403-blocked) → VERIFY-FIRST.
- Sources: kherba.com/tarifs; RADEEF/RADEEJ tariff tables; globalpetrolprices (electricity); Médias24
  (ANRE reform, 22 Dec 2025).

---

## 3. Irradiation / specific yield by city (PUBLISH-SAFE — authoritative)

Specific yield = annual kWh per kWc installed. Strong, well-corroborated data (PVGIS / Global Solar
Atlas / Solargis / peer-reviewed).

| City | kWh/kWc/yr | Confidence |
|---|---|---|
| Tanger | ~1 450–1 550 | medium-low (cloudiest coast) |
| Casablanca | 1 500–1 600 | medium-high |
| Rabat-Salé | ~1 550–1 650 | medium |
| Fès | ~1 600–1 700 | medium |
| Marrakech | **1 700–1 780** (Solargis PVOUT **1 779**, PR 78 %) | high |
| Agadir | 1 700–1 800 | medium-high |
| Ouarzazate | ~1 850–1 950 (best in country) | high |

- **National PVOUT band: 1 600–1 900 kWh/kWp/yr** (Global Solar Atlas / World Bank). **~3 000
  sunshine hours/yr** (3 500+ in the Sahara); daily GHI ~5,0–5,3 kWh/m², >5,5 in the south. Use
  **~5–5,5 peak-sun-hours** for daily math.
- **Installer rule of thumb (PUBLISH-SAFE): 1 500–1 800 kWh/kWc/yr by region.**
- **Optimal tilt:** ~**28–32° south** central/north, ~**25–28°** south (Agadir/Ouarzazate) —
  latitude-based estimate, VERIFY per-site in PVGIS.
- Sources: globalsolaratlas.info/download/morocco; MDPI Resources 2024 13(10):140 (Marrakech 1 779);
  solaratlas.masen.ma; soda-pro.com Morocco Atlas; World Bank.

---

## 4. Sizing (PUBLISH-SAFE — consistent across installers)

- **~5–6 m² of roof per kWc**; modern **550–600 W panels → ~2 panels per kWc**.
- A 550 W panel under 5–5,5 PSH with ~80 % system derate ≈ **2,0–2,4 kWh/day** (≈ 800–880
  kWh/yr/panel).
- Practical mapping (derived, medium): household **4 000–6 000 kWh/yr → 3–5 kWc**; **6 000–10 000
  kWh/yr → 5–8 kWc**.
- Note (medium): ~80 % of ONEE households are **low consumers** (~75 DH/mo) — but the solar-buying
  segment (villas) consumes far more, so size from the *actual* bill, not the national median.
- Sources: facilitysolutiongroup.ma; electrosolarplus.ma (2026 guides).

---

## 5. Installed price — residential rooftop PV (VERIFY-FIRST — installer/blog-sourced, indicative)

> All MAD prices are **advertised/indicative from Moroccan installer blogs, not audited**. Publish as
> ranges labelled « fourchette indicative 2026 ». Taqinor's real quote comes from the founder.

| System | Turnkey (MAD) | Confidence |
|---|---|---|
| 3 kWc | 28 000–42 000 | medium |
| 5 kWc | 45 000–65 000 | medium |
| 6 kWc | ~55 000–80 000 | low (interpolated) |
| 10 kWc | 85 000–120 000 | medium |

- **Per-kWc turnkey 2026: ~10 000–14 000 DH/kWc** (material + labour). The widely-repeated
  **"4 700 DH/kWc"** is **implausibly low for turnkey** (likely kit/equipment-only) → do **not** use
  as the headline. Confidence medium / low.
- Equipment: panels ~1,0–1,5 DH/Wc; Huawei SUN2000-5K inverter ~12 500 DH (10-yr).
- Roof surcharges: tiles/corrugated +6 000–12 000 DH; steep (>30°) +4 000–8 000 DH.
- **Battery add-on: +22 000 to +60 000 MAD** (5–15 kWh), lengthening payback 1–3 yr.
- On-grid (no battery) = cheaper, higher-ROI, recommended for **~80 % of urban homes** ("grid as
  virtual battery") — though the 82-21 buyback being cheap shifts the case toward self-consumption +
  storage vs export.
- **Payback: 5–7 years** residential (most-cited, consistent); +1–3 yr with battery. 25-yr savings
  ">200 000 DH" cited but low-confidence (assumption-dependent).
- Sources: solaropeak.com; ecovolt.ma; electrosolarplus.ma; lechantier.ma; fnh.ma.

---

## 6. EV charging with solar + petrol economics

**Fuel (PUBLISH-SAFE but biweekly — date-stamp it):** essence **14,27 MAD/L**, gasoil **13,55
MAD/L** (mid-June 2026; liberalized, revised ~twice/month, ±0,3–0,5 DH by station). Sources:
Médias24; le360; Infomédiaire; globalpetrolprices.

**Technical anchors (PUBLISH-SAFE, high):**
- Compact EV consumption **~15 kWh/100 km** (Dacia Spring ~13,9 WLTP; BYD Dolphin 14,5). +~10 %
  charge loss → ~16,5 kWh drawn/100 km.
- Typical battery: small EV ~24–27 kWh (Dacia Spring); compact 44–60 kWh (BYD Dolphin).
- Commute **~30–40 km/day → ~5 kWh/day** (LOW-MEDIUM — commute distance is a stated assumption, no
  HCP stat found). A daily top-up, **not** a 0→100 % charge.
- **Panels per EV: ~2–4 × 550 W** cover a typical commuter's daily need (≈1,1–2,2 kWc) — a small
  add-on. (5 kWh ÷ ~2,3 kWh/panel/day ≈ 2–3 panels; 7,5 kWh ≈ 3–4.)

**Cost per 100 km (COMPUTED — show the assumptions):**
- Petrol car 6,5 L/100 km × 14,27 = **~93 MAD/100 km**.
- EV on grid 16,5 kWh × ~1,40 DH (marginal tranche) = **~23 MAD/100 km** (range 19–27) — **~¼ of
  petrol**.
- EV on own solar ≈ **~0 MAD/100 km marginal** (3–13 MAD if solar priced at its 0,2–0,8 DH/kWh
  levelized cost) — **~10–25× cheaper than petrol**.
- Confidence: **HIGH on the ordering/magnitude** (solar ≫ grid ≫ petrol), MEDIUM on exact MAD
  (assumption-driven; state: petrol 6,5 L/100 km, EV 15 kWh/100 km +10 % loss, grid 1,40 DH/kWh).

**Charging / supply (PUBLISH-SAFE, high):**
- Moroccan homes are typically **monophasé 220–230 V, 30 A** → a **7,4 kW wallbox is the sweet
  spot** (≈50 kWh overnight in 7–8 h). **11/22 kW needs triphasé** (power-upgrade request to
  ONEE/régie).
- "Solar-aware" chargers (myenergi **Zappi**, Wallbox **Pulsar/Quasar** solar mode) divert PV
  surplus to the car — the key honesty point: dumb full-power solar-only charging is impractical
  without grid/battery/throttling.
- Wallbox installed **~7 000–25 000 MAD** (VERIFY-FIRST — installer-blog estimate; get a live quote).
  Brands sold in MA: Wallbox, Schneider EVlink, Legrand, V2C, Circontrol.

**EV market (VERIFY-FIRST — automotive press):** >15 000 EVs (2025), fast growth; ADM + TotalEnergies
motorway fast-charge corridor (incl. A3 Casa–Marrakech); ~2 500 bornes planned by end-2026; TVA
exemption + no vignette; **~50 000 MAD purchase prime (individuals)** — verify against an official
source. Common models: Dacia Spring, BYD Dolphin/Atto 3, Renault Mégane E-Tech, Citroën ë-C3, MG4.
Sources: evccat.ma; autoactu.ma; ftmservices.ma; storeaccess.ma; voiturenet.ma.

---

## 7. Batteries — chemistry, Dyness specs, sizing (mostly PUBLISH-SAFE)

**LFP vs lead-acid vs NMC (PUBLISH-SAFE on ranking; numbers as ranges):**

| | LFP (LiFePO4) | Lead-acid AGM/GEL | NMC |
|---|---|---|---|
| Cycle life | ~3 000–6 000 (vendor claims 6 000–10 000 = lab) | ~500–1 000 (3–7 yr) | ~1 000–3 000 |
| Usable DoD | ~80–90 % | ~50 % daily | ~80–90 % |
| Round-trip eff. | ~92–98 % | ~80–85 % | ~92–96 % |
| Thermal-runaway onset | ~270 °C (often **no TR <350 °C at low SOC**) | n/a (but VRLA overcharge runaway exists) | ~150–210 °C (releases oxygen) |
| Hot-climate fit | **best** (still keep <35–45 °C) | worst (life halves per +8 °C) | poor on safety |

- **Why LFP is safer (mechanism, peer-reviewed):** olivine P–O bonds resist breakdown → cathode
  doesn't release oxygen; NMC layered oxide decomposes and releases oxygen → lower, more dangerous
  onset. LFP = correct default for hot Moroccan residential storage.
- Conflict flag: "270 vs 210 °C" is a reasonable consumer summary but method-dependent; LFP's real
  advantage is *less heat/gas, no oxygen, survives low-SOC abuse*. Cite the ranking, not a single
  exact onset.
- Sources: Clean Energy Reviews; Battery University (BU-201a/b, BU-202, BU-403); MDPI Batteries
  2023 9(5):237; MDPI Electronics 2023 12(7):1603; pv-magazine.

**Dyness LFP lineup (the brand Taqinor uses) — PUBLISH-SAFE family facts:**
- Chemistry **LiFePO4** across the range; headline **≥6 000 cycles**; **10-year warranty to ~70 %
  retention** (family standard); marketed **≥95 %** round-trip (DC-level — cite as "≈" / medium).
- Models: **B4850** 2,4 kWh (90 % DoD, 0–55 °C); **B3** 3,6 kWh rack; **A5/PowerBox** 4,8 kWh;
  **PowerDepot H5B** 5,12 kWh (built-in heating — good for cold mountain installs; warranty 10 yr
  *conditional* on registration else 7 yr); **PowerBrick** 14,34 kWh (95 % DoD); **Tower T7/T10/T14**
  HV stacked (6,7 / 10,1 / 13,5 kWh usable).
- VERIFY-FIRST: exact round-trip %, PowerBrick 6 000-vs-8 000 cycles & 55-vs-60 °C, H5B 7-vs-10-yr,
  Tower original-vs-2.0 capacity. Open the official Dyness PDFs to lock precise figures.
- Sources: dyness.com datasheets/warranty PDFs; solarquotes.com.au; enfsolar; distributor pages.

**Hybrid inverters (Deye / Huawei) — PUBLISH-SAFE concept facts:** support **EPS/backup**, **off-peak
grid-charging** (both have time-of-use scheduling), and **"battery-ready"** operation (run solar-only
now, add batteries later — cheaper than AC-coupling a string inverter retrofit). Key **backup
difference** (great differentiator for a Moroccan home riding through grid cuts):
- **Deye SG-series** (SG03LP1 1-phase / SG04LP3 3-phase): **near-seamless UPS backup (~4–10 ms)**,
  **no extra box**, **48 V low-voltage LFP**, **6 configurable TOU charge/discharge windows**. The
  ~4 ms figure is forum-corroborated, not byte-confirmed off the (403-blocked) PDF → cite as "≈".
- **Huawei SUN2000 L1/M1 + LUNA2000** (HV string LFP, ~350–980 V): clean, well-integrated, excellent
  monitoring, TOU night-grid-charging — **but** backup needs a separate **Backup Box** and changes
  over in **< 3 s** (brief outage, not UPS-grade); the **three-phase M0 supports no backup at all**.
- Both are genuinely **battery-ready** (sell solar-only now, retrofit batteries later). Confirm exact
  per-kW switchover/charge numbers on the unit's datasheet before quoting.
- Sources: deye.com / deyeinverter.com datasheets; solar.huawei.com L1/M1 specs; Huawei Backup Box
  B0/B1 datasheet.

**LFP lifespan drivers (PUBLISH-SAFE — for the durability/maintenance content):**
- **Calendar life ~10–15 years** (warranties target ~10 yr to 70 % retention, e.g. Tesla Powerwall 3
  LFP 70 %@10 yr); **calendar fade ~1–2 %/yr even idle** (SEI growth), worsened by heat + high SOC.
- For typical home cycling (~1 cycle/day, low C-rate) **calendar aging usually limits life before the
  cycle budget** (4 000–6 000 cycles ÷ 365 ≈ 11–16 yr) → plan ~12–15 yr.
- **Heat:** optimal **15–35 °C**; **+10 °C ≈ halves life** (Battery University quotes a stricter +8 °C,
  but that originates from lead-acid — cite "+10 °C" as the rule of thumb, order-of-magnitude). Install
  shaded/ventilated.
- **Cold:** **never charge LFP below 0 °C** (lithium-plating, permanent damage); capacity drops
  temporarily ~20–30 % near 0–10 °C (recovers on warming). The Dyness **PowerDepot H5B has built-in
  heating** → relevant for Moroccan mountain/winter installs.
- Sources: Battery University BU-806a/BU-808; Tesla Powerwall warranty; NREL LFP/graphite model;
  MDPI Appl. Sci. 15(23):12749; LiTime temperature range.

**Sizing (PUBLISH-SAFE rules of thumb):** backup-only **5–10 kWh**; evening self-consumption
**10–20 kWh**; near-autonomy **20 kWh+**; off-grid = **2–3 days** autonomy + winter margin. Quote
**usable** kWh (DoD), not nameplate. **Battery price ~3 000–4 000 DH/kWh generic LFP** (VERIFY-FIRST;
the Huawei LUNA 62 050 DH/5 kWh ≈ 12 400 DH/kWh listing is an outlier — do **not** benchmark on it).

**Battery economics — the Morocco angle (PUBLISH-SAFE logic):** with export capped at 20 % and bought
back at 0,18–0,21 DH while you *buy* at 0,90–1,66 DH, a stored-and-self-used kWh is worth your retail
avoided cost, an exported one only the low buyback. **Order of value: (1) consume in daylight (free) →
(2) store for the evening peak → (3) export the 20 % (lowest).** Don't oversize batteries for loads
that could simply run at midday.

---

## 8. Source-quality caveats (read before publishing any number)

- ONEE/Fidal/Le Desk/distributor portals and PVGIS/Global Solar Atlas interactive pages **403-block
  automated fetch** — figures were triangulated from ≥2 independent search extractions, not always a
  fetched primary PDF. Confidence tags reflect this.
- **Re-verify before publishing as fact:** current ONEE top-tranche rates (post-Oct-2025 +5,5 %),
  distributor per-tranche decimals, exact penalty articles, Article 33 start-trigger, fuel prices
  (biweekly), wallbox/battery MAD prices, the EV purchase prime, and exact Dyness efficiency/cycle
  conflicts.
- **Strongest, publish-now data:** irradiation/yield by city, sizing rules, EV kWh/100 km and
  panels-per-EV, the cost-per-100 km *ordering*, LFP-vs-lead-vs-NMC ranking, the 82-21 regimes +
  20 % cap + 0,18–0,21 DH buyback + net-billing fact, panel degradation (~0,5 %/yr, ~80–85 % at 25
  yr).
