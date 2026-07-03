# CONTENT_SEO_NOTES — verified data for the FAQ / guides / blog (`apps/web`)

**Purpose.** This is the **cited evidence base** for the SEO content expansion (WEB_PLAN
W119–W139): the FAQ, the evergreen guides, the EV-charging pillar, and the dated blog. It exists
so the content tasks can use **real, sourced numbers** instead of inventing them — the web-plan
convention is "method, not client data, is committed" and rationale lives in `apps/web/*_NOTES.md`.

**Compiled 2026-06-21** from a parallel, citation-required research pass (five agents, each
cross-checking ≥2 independent sources, with confidence + freshness flags). **Refreshed 2026-06-21
(W140 lock-and-freshness wave):** residual figures locked from primary sources, volatile figures
date-stamped, refresh-cadence notes added (see §8). Currency: **MAD (DH)**; 1 DH = 100 centimes;
~1 EUR ≈ 10.8 MAD.

## How to use this on the site (honesty rules)

1. **PUBLISH-SAFE vs LOCK-FIRST.** Each figure below is tagged. **PUBLISH-SAFE** = high-confidence,
   well-corroborated, safe to state (as a range). **LOCK-FIRST** = single-source or evolving — a
   build/research step must **lock it from a primary source** (official ONEE/distributor tariff PDF,
   the Bulletin Officiel / ANRE decision, the manufacturer datasheet, a live fuel price) **before**
   it's published as a hard fact; until locked, publish it as a labelled range. **The agent does the
   locking by searching primary sources — never ask the founder to verify a researchable fact.**
2. **Volatile vs stable.** **Stable** physics/spec numbers (irradiation kWh/kWc, optimal tilt,
   panel degradation %, LFP cycle life / DoD / efficiency, EV kWh/100 km) may appear in **evergreen
   guides**. **Volatile** market/regulatory numbers (MAD prices, ONEE tranches, buyback rate, fuel
   prices) belong in **dated blog posts** that signal freshness and get refreshed — link to them
   from the guides rather than hardcoding a price into an undated page.
3. **Ranges, not false precision.** Moroccan price data is installer/blog-sourced, not audited —
   always a range, always "indicatif".
4. **The only founder-owned thing is Taqinor's actual quote.** Content never states the firm's
   internal MAD quote or margins; it uses the indicative market ranges here + a CTA to the diagnostic
   / quote engine (the existing funnel produces the real number). That is NOT a research gap and
   needs no placeholder asking the founder for data.

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
| Buyback / rachat tariff | **0,21 DH/kWh peak · 0,18 DH/kWh off-peak** (ANRE Décision 04/26) — **scope: MT/HT only. The BT (<11 kW residential déclaration) surplus/net-billing tariff is STILL UNPUBLISHED as of this writing.** Never state this number as settled fact for the residential/BT case — always pair it with the "tarif MT/HT uniquement — BT résidentiel non encore publié" caveat, or omit and describe the mechanism only. | LOCK-FIRST for BT (medium) / PUBLISH-SAFE for MT-HT (high) | Médias24; LesEco; energypartnership; ANRE Décision 04/26 scope confirmed MT/HT-only |
| Net-metering? | **No** — net-billing only; buyback ≪ retail | PUBLISH-SAFE (high) | multiple |
| Penalties — **fines only** (enacted law dropped the draft's prison terms) | **Art. 28** no déclaration **2 000–5 000 DH**; **Art. 29** no raccordement/autorisation **100 000–1 000 000 DH**; **Art. 31** obstructing control **10 000–100 000 DH**; (Art. 30, number unconfirmed) modif. contraire à l'autorisation **10 000–20 000 DH + saisie** | PUBLISH-SAFE (high — verbatim from indexed BO n°7400, except Art. 30 medium) | ANRE Loi 82-21 PDF (BO 7400) |
| Article 33 regularization window | **18 months from the LAW's entry into force** (verbatim Art. 33); dead-letter until the decree, so the operative trigger is now the **9 Jun 2026** decree entry-into-force (Fidal). No clean restated calendar deadline confirmed. | PUBLISH-SAFE on the 18-month text (high); operative date medium | ANRE PDF Art. 33; Fidal |

Primary: ANRE Loi 82-21 PDF (anre.ma/.../Loi-82-21-BO_7400_Fr.pdf); ledesk.ma; fidal.com;
energypartnership.ma; le212news.ma; medias24.com; leseco.ma. *(NB: ONEE/Fidal/distributor portals
403-block automated fetch; figures triangulated from ≥2 independent extractions.)*

---

## 2. Electricity tariffs (what solar offsets)

ONEE residential basse-tension, **TTC**, current in-force grid (this is the long-standing ONEE BT
grid — the rounded figures below ARE the current usable rates):

| Monthly use | DH/kWh (rounded) | Precise grid value | Mode |
|---|---|---|---|
| 0–100 kWh | **0,90** | 0,9010 | progressive |
| 101–150 | 1,07 | 1,0732 | progressive |
| 151–200 | 1,18 | 1,1804 (sélective whole-bill 1,1676 in examples) | sélective |
| 201–300 | **1,18** | 1,1676 (sélective whole-bill, TTC) — **LOCKED 2026-06-21** | sélective |
| 301–500 | **1,45** | 1,4555 | sélective |
| > 500 | **1,66** | 1,6651 (sélective whole-bill 1,5958 in examples) | sélective |

- **Bi-horaire (peak/off-peak), avg >500 kWh/mo or >26 kVA (PUBLISH-SAFE, medium):** pointe
  **1,4157** · pleines **1,0101** · creuses **0,7398** DH/kWh.
- **Key mechanic (PUBLISH-SAFE, high):** at **≤150 kWh/mo** billing is **progressive** (each tranche
  at its own rate); **above 150 kWh/mo** it turns **"sélective"** — the **whole** month is billed at
  the reached tranche's rate, so high consumers pay the high marginal rate on *everything* (a **10
  kWh/mo tolerance** per tranche softens overruns). This is precisely the cost solar removes.
- **CORRECTION (vs first pass):** the often-repeated **"+5,5 % Oct-2025 hike"** could **not** be
  confirmed to any primary source — it is likely conflated with **TVA** changes. The grid above is
  the current usable schedule (press dates its last official revision to ~2015); the real near-term
  change is an **ANRE tariff overhaul targeted ~March 2027**.
- **VAT — RESOLVED 2026-06-21 (PUBLISH-SAFE, high).** The "14 % vs 18 %" split is a *date artefact*,
  not a contradiction. The **statutory** VAT on residential BT electricity was raised by the
  successive Lois de Finances **14 % → 16 % (Jan 2024) → 18 % (Jan 2025) → 20 % (Jan 2026)**
  (le360, Le Matin, distributor pages). **Critically, the TTC retail tariff was held STABLE through
  the transition** — the HT was lowered to absorb each VAT step, so the **TTC DH/kWh grid above is
  unchanged** and remains the usable client-facing figure. This is why consumer/distributor pages
  still display "14 %" or "TVA 18 % comprise": those reflect the price-stable TTC grid, not the live
  statutory rate. **Publish the TTC DH/kWh values; if VAT is ever cited, say "TVA statutaire 20 %
  depuis 2026, prix TTC maintenus stables".** Refresh cadence: re-check at each Loi de Finances
  (annual, ~December) and at the ANRE ~2027 overhaul.
- **Distributors (Lydec/Casablanca, Redal/Rabat, Amendis/Tanger):** **LOCKED 2026-06-21** — they
  bill the **same ONEE grid** (confirmed: RADEEF/RADEM publish the identical tranche values, e.g.
  the 211–310 kWh sélective row = **1,1676 DH/kWh TTC**; Lydec's own page confirms the same
  progressive-≤150 / sélective-&gt;150 structure with tranches 1–100 / 101–150 / 151–210 / …).
  Their interactive per-tranche decimal pages still 401/403-block automated fetch, so **use the ONEE
  grid above as the proxy — it is now confirmed accurate, not merely assumed.** PUBLISH-SAFE.
- Sources: kherba.com/tarifs (0,9010…1,5958 TTC grid); calculateur.ma (ONEE simulator, 201–300 =
  1,18); radeef.ma/radem.ma (distributor = ONEE grid, 211–310 = 1,1676 TTC); client.lydec.ma
  (tranche structure); le360.ma + lematin.ma (VAT 14→16→18→20 %, TTC held stable); electrosolarplus.ma;
  bati.ma; Médias24 (ANRE 2027 reform, 22 Dec 2025).

---

## 3. Irradiation / specific yield by city (PUBLISH-SAFE — authoritative)

Specific yield = annual kWh per kWc installed. Strong, well-corroborated data (PVGIS / Global Solar
Atlas / Solargis / peer-reviewed).

Realistic PVOUT (~14 % system losses, GSA/PVGIS-aligned) + the **firmly-sourced optimal tilt**
(all due-south):

| City | PVOUT kWh/kWc/yr | Optimal tilt | Confidence |
|---|---|---|---|
| Tanger | ~1 550–1 650 | **31°** (2nd study: 32°) | tilt high; yield est. |
| Casablanca | ~1 620–1 700 | **29°** | tilt high; yield est. |
| Rabat-Salé | ~1 620–1 700 | **29°** | tilt high; yield est. |
| Fès | ~1 650–1 750 | **~32°** | tilt medium; yield est. |
| Marrakech | **1 779** (GTI 2 276, PR 78 %) | **28°** | **high** — one fully-confirmed row |
| Agadir | ~1 750–1 820 | **27°** | tilt high; yield est. |
| Ouarzazate | ~1 850–1 950 (best) | ~28–30° (est.) | yield band medium; tilt est. |

- **Methodology (per-city PVOUT reconciled 2026-06-21 — PUBLISH-SAFE as a range):** *resource-side*
  yields (profileSOLAR / NASA POWER, PR≈1) were re-pulled per city and run ~1 986–2 358 kWh/kWp
  best-case (Tanger 1 986, Casa 2 099, Rabat 2 157, Fès 2 019, Marrakech 2 219, Agadir 2 332,
  Ouarzazate 2 358 — profileSOLAR, optimal tilt). These are **PR≈1 ceilings**; applying real ~14 %
  system losses (GSA/PVGIS PVOUT method) brings them down ~14–18 % onto the **PVOUT bands in the
  table above**, which **Marrakech 1 779 (PR 78 %, the one fully-confirmed datapoint)** calibrates.
  Standardize the site on **PVGIS, 14 % system losses, optimalangles=1**. The GSA/PVGIS *interactive*
  per-coordinate pages still serve only an empty/JS-rendered shell to automated fetch (verified
  2026-06-21), so the **exact per-city PVOUT stays a reconciled range** — locked between the
  profileSOLAR PR≈1 ceiling and the loss-adjusted floor — **not a single decimal**; the tilts are
  fully locked. To pin a single number later, read it manually off globalsolaratlas.info per
  coordinate.
- **National anchors (PUBLISH-SAFE):** GSA PVOUT **1 600–1 900 kWh/kWp/yr**; ~**3 000** sunshine
  hours/yr (3 500+ in the Sahara); GHI ~5,8 kWh/m²/day (~2 100 kWh/m²/yr); use **~5–5,5 peak-sun-
  hours** for daily math. **Installer rule of thumb: 1 500–1 800 kWh/kWc/yr by region.**
- Sources: MDPI Resources 2024 13(10):140 (Marrakech 1 779, confirmed); profileSOLAR (NASA POWER,
  per-city tilts); globalsolaratlas.info; PVGIS; soda-pro.com Morocco Atlas; World Bank.

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

## 5. Installed price — residential rooftop PV (LOCK-FIRST — installer/blog-sourced, indicative)

> All MAD prices are **advertised/indicative from Moroccan installer blogs, not audited**. Publish as
> ranges labelled « fourchette indicative 2026 ». Taqinor's real quote comes from the diagnostic /
> quote engine (the existing funnel) — content links to it, it is not a number to ask anyone for.

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

**Fuel (PUBLISH-SAFE but biweekly — date-stamped 2026-06-21):** essence **~14,27 MAD/L**, gasoil
**~13,55 MAD/L** (figures as of mid-June 2026; liberalized, revised ~twice/month, ±0,3–0,5 DH by
station). **Refresh cadence: re-pull every ~2 weeks (1st & 16th) before publishing any dated EV-vs-
petrol cost post.** Sources: Médias24; le360; Infomédiaire; globalpetrolprices.

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
- Wallbox pricing **LOCKED 2026-06-21 against live Moroccan listings** (PUBLISH-SAFE as a range,
  « fourchette indicative 2026 »): **hardware only ~4 000–12 000 MAD** (basic 7 kW vs smart/connected),
  **installed turnkey ~12 000–25 000 MAD** for a 7 kW monophasé setup incl. electrician + protections
  (storeaccess.ma; autovolt.ma 2026 guide: ~15 000–28 000 DH for a full 7 kW install). The hardware
  is ~40–60 % of the total. Brands sold/installed in MA (live distributors): Schneider EVlink
  (securite212.ma), Legrand (legrand.ma), Wallbox, V2C, Circutor/Circontrol, ABL (binaa.ma, kver.ma,
  bornerecharge.ma). Refresh cadence: re-check a live listing at each price post (~quarterly).

**EV policy (CORRECTED 2026 — the honesty fix):**
- ⚠️ **The "50 000 / 100 000 MAD prime à l'achat" is NOT a confirmed Moroccan measure.** It appears
  only in commercial secondary blogs and is **Tunisia bleed-through** (the "TVA 19→7 %, prime, 50 000
  véhicules d'ici 2030" package is *Tunisia's*, per the African Manager article repeatedly mis-cited
  as Moroccan). Authoritative LF-2026 summaries (Deloitte, DGI, CGI-2026) list **no EV cash bonus**.
  The only real cash help is a **private manufacturer promo** (Stellantis Maroc "ECO BONUS", ~30 000
  DH, not state, not EV-specific). **Do NOT publish the prime as Moroccan policy.** (Med-high it is
  NOT real MA policy.)
- **Real, citable Moroccan EV measures (PUBLISH-SAFE):** **TVA exemption** (0 % vs 20 %),
  **customs/import-duty waiver** on qualifying 100 %-electric vehicles, and **vignette/TSAVA
  exemption** (EV **and** PHEV; non-plug-in HEV generally **not** exempt) — long-standing (2014/2017
  finance laws). The "7 % TVA / 2,5 % customs" variants are **Tunisian** — not Morocco.
- **Charger/wallbox/inverter import-duty cut: UNVERIFIED** — LF-2026 actually *raised* duties on
  several electronics; do not assume a cut.
- **Charging network (medium):** ~**632** public points now (~**142** fast up to 150 kW); target
  **2 500 stations by end-2026**, ~5 000 by 2028; flagship corridor = **TotalEnergies + ADM** on the
  motorway **A1/A3 Casablanca–Rabat–Tanger**; ONEE in cities/malls.
- **EV parc:** >15 000 EVs (2025), fast growth. Common models: Dacia Spring, BYD Dolphin/Atto 3,
  Renault Mégane E-Tech, Citroën ë-C3, MG4.
- Sources: IEA Policies (vignette/circulation exemption); PwC Morocco tax summary; Deloitte LF-2026;
  Le Matin / Médias24 (vignette 2026); laquotidienne.ma (2 500 bornes); TotalEnergies Maroc. Tunisia
  bleed-through traced to africanmanager.com.

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
- Models (locked from official datasheets): **B4850** 2,4 kWh (90 % DoD, 0–55 °C); **B3** 3,6 kWh
  rack (90 % DoD); **A5/PowerBox** 4,8 kWh; **PowerDepot H5B** 5,12 kWh (~95 % DoD, **built-in
  heating**, **−20–55 °C**, warranty **7 yr base / 10 yr on registration** to 70 %); **PowerBrick**
  14,34 kWh (95 % DoD, **≥8 000 cycles** latest datasheet / ≥6 000 @ 80 % warranty basis, **55 °C**
  ceiling, **>95 %** round-trip — the one efficiency datasheet-confirmed); **Tower T7/T10/T14** HV
  stacked (7,10 / 10,66 / 14,21 kWh nominal, 95 % DoD, charge 0–50 °C / discharge −10–50 °C).
- **Resolved conflicts (was LOCK-FIRST):** PowerBrick ≥8 000 cycles & 55 °C; H5B 7/10-yr & −20–55 °C
  w/ heating — all locked above. **Round-trip efficiency for the non-PowerBrick models — RE-CHECKED
  2026-06-21, CONFIRMED ABSENT:** the official B4850, B3, A5/PowerBox, PowerDepot H5B and Tower
  T7/T10/T14 datasheets publish DoD, cycle life, chemistry and temperature **but no round-trip /
  energy-efficiency figure** (only the PowerBrick datasheet carries >95 %). The Tower page only says
  "higher round-trip efficiency" qualitatively. → This is a genuine datasheet gap, not a research
  miss: state **"≈95 % (classe LFP, valeur PowerBrick datasheet)"** as a labelled class range, or
  omit; never cite the lone aggregator "90 %".
- Sources: dyness.com datasheets/warranty PDFs (PowerBrick 20250228, H5B, B4850, B3, Tower);
  solarquotes.com.au; enfsolar; bimblesolar; distributor spec mirrors.

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
**usable** kWh (DoD), not nameplate. **Battery price ~2 700–3 800 DH/kWh generic LFP — LOCKED
2026-06-21 against live Moroccan distributor listings** (PUBLISH-SAFE as a range): Dyness 5,12 kWh
≈ **14 000–16 000 DH** (≈2 700–3 100 DH/kWh, mrelec.ma / electrosolarplus.ma / cptechmaroc.ma);
Dyness Stack100 HV from ~12 500 DH; Pylontech 3,6–4,8 kWh from ~18 600 DH (≈3 900–5 200 DH/kWh — the
small-capacity premium). The Huawei LUNA 62 050 DH/5 kWh ≈ 12 400 DH/kWh listing remains an outlier —
do **not** benchmark on it. Refresh cadence: re-check a live listing at each storage post (~quarterly).

**Battery economics — the Morocco angle (PUBLISH-SAFE logic, buyback figure LOCK-FIRST for BT):** with
export capped at 20 % and bought back at 0,18–0,21 DH (MT/HT tariff; **the BT/residential surplus
tariff is not yet published** — caveat whenever this number is cited for a home/villa case) while you
*buy* at 0,90–1,66 DH, a stored-and-self-used kWh is worth your retail avoided cost, an exported one
only the low buyback (or an unknown one, pending BT publication). **Order of value: (1) consume in
daylight (free) → (2) store for the evening peak → (3) export the 20 % (lowest, exact rate pending for
BT).** Don't oversize batteries for loads that could simply run at midday.

---

## 8. Source-quality caveats (read before publishing any number)

- ONEE/Fidal/Le Desk/distributor portals and PVGIS/Global Solar Atlas interactive pages **403/401-block
  automated fetch** (re-confirmed 2026-06-21) — figures were triangulated from ≥2 independent search
  extractions, not always a fetched primary PDF. Confidence tags reflect this. A **second wave**
  (2026-06-21) and a **third W140 freshness-and-lock wave (2026-06-21)** were run to LOCK the open
  items from primary sources; promoted figures are folded in above.
- **LOCKED by the 2nd wave (now PUBLISH-SAFE, folded in above):** the current ONEE BT grid + the
  "+5,5 % hike" correction; loi 82-21 penalty articles (28/29/31, fines-only — prison was dropped);
  Article 33 = 18 months from the law's entry into force; per-city optimal tilts (Casa/Rabat 29°,
  Marrakech 28°, Agadir 27°, Tanger 31°); Dyness conflicts (PowerBrick ≥8 000 cyc/55 °C/>95 %, H5B
  7-/10-yr & heating); fuel mid-Jun-2026; and the **EV-prime correction** (50 000 MAD prime = Tunisia
  bleed-through, NOT Moroccan — only TVA/vignette/customs exemptions are real).
- **LOCKED by the W140 3rd wave (2026-06-21, now PUBLISH-SAFE, folded in above):** the **201–300 kWh
  tranche = 1,18 DH/kWh TTC** (calculateur.ma + kherba 1,1676 sélective); the **BT VAT question**
  (statutory 14→16→18→20 %, **20 % since Jan 2026**, but **TTC grid held stable** — publish the TTC
  values; le360 + Le Matin + RADEEF); **distributors bill the same ONEE grid** (RADEEF/RADEM 211–310
  = 1,1676 TTC; Lydec structure confirmed) — use ONEE as a now-*confirmed* proxy; **live wallbox MAD**
  (hardware ~4 000–12 000, installed ~12 000–25 000); **live battery MAD** (Dyness 5,12 kWh
  ~14 000–16 000 DH ≈2 700–3 100 DH/kWh); per-city resource-side PVOUT re-pulled (profileSOLAR 1 986–
  2 358 PR≈1, reconciled to the table's loss-adjusted bands); EV-prime correction re-confirmed intact.
- **Residual gaps that remain LABELLED RANGES (structural — the data is genuinely not published, NOT a
  research miss; never ask the founder):** (a) **exact per-city PVOUT as a single decimal** — the
  GSA/PVGIS interactive pages serve only an empty JS shell to automated fetch; the figure is a
  reconciled range between the profileSOLAR PR≈1 ceiling and the 14 %-loss floor (tilts fully locked);
  (b) **round-trip efficiency for the non-PowerBrick Dyness models** — re-checked at source, the
  official datasheets simply don't print it (only PowerBrick's >95 %) → state "≈95 % (classe LFP)".
  Volatile (fuel, tariffs, prices) = date-stamped 2026-06-21 + a refresh-cadence note per block above.
- **Strongest, publish-now data:** per-city optimal tilt + national PVOUT band, sizing rules, EV
  kWh/100 km and panels-per-EV, the cost-per-100 km *ordering*, LFP-vs-lead-vs-NMC ranking, the 82-21
  regimes + 20 % cap + net-billing fact + the locked penalty bands, panel degradation (~0,5 %/yr,
  ~80–85 % at 25 yr — Taqinor's own warranty goes further, ≥ 84,8 % at 25 yr, see §5).
- **W300 correction (2026-07-03):** the 0,18–0,21 DH/kWh buyback/rachat figure is ANRE Décision 04/26's
  **MT/HT** rate. It was being stated across the guides/blog as if it applied to the **BT (<11 kW
  residential déclaration)** case too — that case's surplus tariff is **not yet published**. Every
  citation of 0,18–0,21 DH/kWh in residential/BT content must now carry the
  « tarif MT/HT uniquement — BT résidentiel non encore publié » caveat (see the guides + blog posts +
  regularization-article-33.astro, fixed 2026-07-03). This was the one place the site's "no invented
  numbers" rule was broken.
