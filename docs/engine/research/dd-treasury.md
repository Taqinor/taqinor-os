# THE TREASURY + LAUNCH KIT — budget pacing & campaign scaffolding (spec-grade)

Research/spec date: 16 Jul 2026. Scope: (a) pacing engine, (b) ABO-vs-CBO budget mechanics,
(c) Launch Kit (naming + UTM + 3 templates), (d) multi-account readiness paragraph, (e)
forecast/pacing UI screen. This is a **spec layer on top of the already-merged `docs/PLAN.md`
Groupe ENG (ENG1–ENG31)** — nothing in ENG1–31 is rebuilt here; every addition below is either
a new field on an existing ENG model, a new `EngineAction.action_type`, or a new pure-function
module, chosen to be the smallest addition that fits the existing shape. `apps/adsengine` is
**not yet built** (0/31 ENG tasks checked in `docs/PLAN.md` as of this pass) — this doc is
input for whichever future plan run builds ENG + this Treasury layer.

**Source discipline applied**: every number below is tagged `[PRIMARY]` (Meta's own developer
docs, fetched directly), `[VENDOR]` (a named competitor's own docs about their own product —
credible for their own claims, not independently audited), or `[UNVERIFIED-CLUSTER]` (the
SEO-content-farm cluster already flagged in prior research — directional only). Where a primary
source is silent, that is stated explicitly rather than filled in with folklore.

---

## (a) Pacing engine

### A1. The Meta daily-flex number — verified, and it corrects the mission brief's own premise

The mission brief asked to "verify Meta's up-to-2x daily flex" at a primary source. Doing so
surfaces a real discrepancy worth flagging loudly:

- **[PRIMARY]** `developers.facebook.com/docs/marketing-api/bidding/overview/budgets/`
  (Marketing API "Budgets" doc, fetched directly 16 Jul 2026), quoted verbatim:
  > "up to 25% more than your daily budget may be spent" — with a worked example: "If your
  > daily budget is $10, up to $12.50 may be spent."
  This is the **default, no-opt-in** daily delivery-flex ceiling that applies to a plain ad set
  or campaign budget (ABO or CBO, no extra feature enabled). **1.25×, not 2×.**
- **[PRIMARY]** `developers.facebook.com/docs/marketing-api/bidding/guides/adset-budget-sharing/`
  (fetched directly) describes a **separate, opt-in** feature, "Ad Set Budget Sharing," which
  only applies to ABO campaigns and must be explicitly turned on ("Ad set budget sharing will
  only affect new and duplicated campaigns. Existing campaigns will not be impacted"). This page
  quotes a larger "daily flexibility value (75%)" as the baseline for THIS feature, with a
  further "up to 20%" shared from other ad sets on top. **Caution**: the numeric table this same
  fetch returned (a $10 ad set showing a "$21 maximum daily spend") does not reconcile cleanly
  with 75%+20% math (75%+20%=95%→$19.50, not $21≈110%) — WebFetch summarizes HTML through a
  small model, and prior research already documented Meta-adjacent numeric hallucination as a
  real failure mode ([`eng-meta-tooling.md`](file://C:/Users/kasri/AppData/Local/Temp/claude/C--dev-taqinor-os--claude-worktrees-great-neumann-fc8b39/10cd2506-bf9c-44fb-a165-940cdd07048c/scratchpad/eng-meta-tooling.md) §a). Treat the "75%" figure and its table as
  **[PRIMARY but arithmetically unreconciled — re-verify with a raw HTML fetch or a live account
  test before relying on the exact number]**; the "20% shared" figure is self-consistent and
  higher-confidence.
  **This almost certainly is the origin of the "up to 2x" folklore** — someone conflated the
  opt-in Budget Sharing feature's escalated ~1.75–1.95× ceiling with the platform default, or
  rounded loosely. Taqinor will not enable Ad Set Budget Sharing at 2–4 ad sets (see §b — it is
  designed for larger ABO fleets), so it is out of scope for the invariant below.
- **Weekly-average cap ("total spend won't exceed 7× daily budget")**: **primary source
  silent** — not stated on either fetched page. Folklore (`leadenforce.com`,
  `digitalposition.com`, both `[UNVERIFIED-CLUSTER]`) repeats "7× daily budget per week," which
  is arithmetically consistent with a 25%-average-overspend-that-nets-out story, but no Meta doc
  confirming it directly was retrieved in this pass. **Do not hard-code a weekly multiplier
  into the pacing engine** — design against the confirmed daily 1.25× ceiling and let the
  monthly-envelope math (A3) absorb the rest via observed spend, not an assumed weekly formula.
- **Verdict for the "ceiling never exceeded" invariant**: design against **1.25× (the confirmed
  PRIMARY number)** as the single worst-case daily multiplier, with the multiplier stored as one
  named constant (`META_DAILY_FLEX_MULTIPLIER = 1.25`) in `apps/adsengine/pacing.py`, not a
  per-company config field — same reasoning CLAUDE.md already applies to the PAUSED-only rule:
  a safety invariant is a hard-coded constant, never a caller-supplied knob. Cite the source URL
  in the constant's docstring so a future re-verification is one click away.

### A2. Linear + weekday-seasonality-aware projection

No new table. `InsightSnapshot` (ENG5, already spec'd: generic FK via contenttypes, date, spend,
results, frequency, CPL) already carries one row per day per mirror level — the pacing engine is
a **pure-function read layer** (`apps/adsengine/pacing.py`) over existing rows plus one new
`GuardrailConfig` field (A4), following the same "no new ML, cheap-to-compute" verdict
`scope-features.md` domain 14 already reached ("a simple linear projection + monthly-ceiling
guardrail is enough at Taqinor's scale; do not build Optmyzr-grade seasonality forecasting").

**Formula set** (company + month scoped, `days_in_month` = calendar days in the month):

1. **Naive linear target curve** (fallback, always computable):
   `expected_spend_to_date = monthly_budget_ceiling_mad × (days_elapsed / days_in_month)`
2. **Weekday-seasonality-aware target curve** (used once enough history exists):
   - Cold-start guard: uniform 1/7 per weekday until ≥28 days (4 full weeks) of
     `InsightSnapshot` history exist for the company — an explicit, honest low-data floor,
     matching the "SMB-scaled, honest about uncertainty" lesson already banked from
     `scope-science.md` Mission S1.
   - Once ≥28 days exist: `weekday_share[d] = mean(spend on weekday d, trailing 8 weeks) /
     sum(all 7 weekday means)` — normalizes to 1.0 across the week.
   - `expected_spend_to_date = monthly_budget_ceiling_mad × Σ(weekday_share[d] for each elapsed
     day d in the month)`.
3. **Pacing ratio**: `pacing_ratio = actual_spend_to_date / expected_spend_to_date` (guard:
   `expected_spend_to_date` floored at 1 MAD to avoid divide-by-zero on day 1).
4. **End-of-month forecast (run-rate, distinct from the target curve)**:
   `trailing_daily_run_rate = mean(spend, trailing 7 days)`
   `forecast_spend = actual_spend_to_date + trailing_daily_run_rate × days_remaining`
   This is "if today's pace continues," not "if we perfectly hit the envelope" — the UI (§e)
   shows both curves so the two questions ("are we on pace?" vs "will we blow the budget if
   nothing changes?") are never conflated into one number.

### A3. Over/under-pacing bands + state table

One new `GuardrailConfig` field: **`pacing_band_pct`** (int, default **15**) — deliberately a
*separate* number from the existing `weekly_change_pct_max` (default 20, ENG3), because they
answer different questions: `weekly_change_pct_max` bounds how much an **engine-authored budget
edit** may move a live ad set in one step; `pacing_band_pct` bounds how far **organic spend
drift** (Meta's own delivery variance, not our edits) may wander from the target curve before
it is worth a proposal. Reusing one field for both would silently couple two independently-tuned
thresholds.

| State | Condition | Action |
|---|---|---|
| `on_track` | `pacing_band_pct` within ±15% of 1.0 (i.e. 0.85 ≤ pacing_ratio ≤ 1.15) | none — WeeklyBrief line only |
| `under_pacing` | pacing_ratio < 0.85 | `EngineAction(action_type='increase_pace')` proposed — small daily-budget nudge within `weekly_change_pct_max`, `reason_fr` states the gap in MAD |
| `over_pacing` | pacing_ratio > 1.15 AND `forecast_spend` ≤ `monthly_budget_ceiling_mad` | flagged in WeeklyBrief only (still projected to land inside the envelope — no action forced) |
| `breach_imminent` | `forecast_spend` > `monthly_budget_ceiling_mad` **or** `actual_spend_to_date + (daily_budget_ceiling_mad × META_DAILY_FLEX_MULTIPLIER)` would exceed `monthly_budget_ceiling_mad` if tomorrow hits the 1.25× ceiling | `EngineAction(action_type='pause_for_month')` proposed immediately (not batched to the weekly brief — this is the invariant-protection path) + `EngineAlert` (WhatsApp, ENG13 pattern) same day |
| `paused_for_month` | a `pause_for_month` action has been applied this month | no further pacing actions proposed until the 1st of next month; WeeklyBrief still reports actuals |

The `breach_imminent` test is the literal "ceiling never exceeded" invariant: it fires **before**
a single max-flex day could push the account over the monthly envelope, using the confirmed
1.25× constant from A1, not a guessed 2×. This is deliberately more conservative than assuming
2× would have made it, and deliberately not more paranoid than the confirmed number justifies.

### A4. Field/action additions (delta on already-merged ENG models)

- `GuardrailConfig` (ENG3) gains: `monthly_budget_ceiling_mad` (nullable int; if unset, derived
  as `daily_budget_ceiling_mad × 30` so no company is ever unconfigured by omission) and
  `pacing_band_pct` (default 15, see A3).
- `EngineAction.action_type` (ENG7) gains two values: `pause_for_month` (breach-imminent path,
  A3) and `increase_pace` (under-pacing nudge, A3) — both flow through the existing
  propose→approve→apply lifecycle and guardrail engine (ENG9), nothing new is auto-applied.
- No new Celery task: pacing state is computed **inside the existing
  `adsengine.sync_insights_daily`** job (ENG6), immediately after that day's `InsightSnapshot`
  rows land — one extra pure-function call, not a second daily job. `breach_imminent` detection
  therefore fires same-day, at the existing ~06:10 heure-creuse cadence.
- No new table for pacing state itself — it is derived on every read from `InsightSnapshot` +
  `GuardrailConfig`, matching the volume reality (a company has at most ~30 `InsightSnapshot`
  rows/month per mirror level; a stored cache table would be premature).

---

## (b) Budget reallocation mechanics at Taqinor's scale ($10–50/day)

### B1. What each primitive actually is, at the primary source

- **[PRIMARY]** `developers.facebook.com/docs/marketing-api/bidding/guides/advantage-campaign-budget/`
  (Advantage Campaign Budget = CBO): "Facebook automatically and continuously finds the best
  available opportunities for results across your ad sets and distributes your campaign budget
  in real time." When enabled, **individual ad-set budgets are not set at all**
  (`adset_budgets` is only used to *disable* it and fall back to ABO). No minimum ad-set count
  is documented by Meta itself; the one hard number found is structural, not a floor: **campaigns
  with more than 70 ad sets under CBO cannot edit bid strategy or disable the feature** — an
  upper-bound edge case irrelevant at Taqinor's scale, not a minimum.
- **ABO** (plain per-ad-set daily/lifetime budgets) is the default when CBO/Advantage+ campaign
  budget is off — each ad set spends roughly its own set amount, subject only to the A1 1.25×
  daily flex, no cross-ad-set reallocation at all unless Ad Set Budget Sharing (A1, opt-in,
  ABO-only) is separately turned on.

### B2. Madgicx's over-concentration warning, and what it means as a floor rule

**[VENDOR]** Madgicx's own product docs (`madgicx.com`, previously captured in
`scope-science.md` §4): their Autonomous Budget Optimizer "works best with at least 8-10 ad sets
with consistent spend history; on thin data it tends to over-concentrate budget in one location."
This is Madgicx describing their own ML layer, not Meta's native CBO directly — but the
underlying mechanism (an allocator chasing early signal toward one "winner") is exactly what
CBO's own real-time reallocation does, and the failure mode generalizes: **at low ad-set count
and low weekly conversion volume, any automatic budget allocator (Meta's CBO or a third-party
optimizer) will lock onto early noise as if it were signal**, because the sample size needed to
tell a real winner from noise is large relative to Taqinor's actual weekly lead volume (this is
the same minimum-detectable-effect problem `scope-science.md` Mission S1 flags at the low-N
regime — not re-derived here, just applied).

**Translated into Taqinor's floor rules**:
- **Never enable CBO (Advantage+ campaign budget) below 8 concurrently-running ad sets with
  ≥2 weeks of consistent spend history.** Below that floor, CBO's own black-box reallocation is
  more likely to be over-concentrating on noise than on a genuine signal — and once concentrated,
  the starved ad sets stop generating the very data that would prove the concentration wrong
  (a self-reinforcing failure with no native circuit-breaker).
- **Never run the engine's own ABO reallocation logic (§B3) across fewer than 2 ad sets** —
  nothing to reallocate between with one.
- At Taqinor's real ad-set count today (2–4 ad sets per market-mode campaign, per the launch
  templates in §c), **Taqinor sits below the CBO floor by construction** — this is not a
  hypothetical guardrail, it is the actual starting state.

### B3. Recommendation: ABO with engine-controlled ad-set budgets, as the default

**ABO + the engine proposing daily budget deltas per ad set (via `EngineAction`, gated through
the existing approve→apply loop, ENG7) is the recommended default at $10–50/day**, for three
compounding reasons:

1. **Below the CBO floor** (B2) — enabling CBO today would hand budget control to an allocator
   Madgicx's own experience says will over-concentrate at Taqinor's ad-set count.
2. **CBO is blind to Taqinor's real success metric.** CBO optimizes toward whatever the ad
   objective's own conversion event is (a click, a message-start) — it structurally cannot see
   cost-per-**signature** (the STAGES.py `SIGNED` event, weeks downstream, verified only in the
   ERP). An engine-side ABO reallocation, reading `InsightSnapshot` joined to CRM `SIGNED` counts
   via the already-spec'd cost-per-signature service (ENG10), can weight ad sets by the metric
   Meta cannot see at all — this is the same "operate on what CBO can't already see" principle
   `scope-features.md` domain 5 and `scope-science.md`'s cross-cutting synthesis both converged
   on independently.
3. **Avoids two allocators fighting.** If CBO were enabled AND the engine also tried to move
   ad-set-level budgets, the two would be blind to each other and could oscillate (CBO
   reallocating live while the engine's proposal assumes yesterday's split) — `scope-science.md`
   Mission S2 named this exact risk. Running ABO with the engine as the SOLE allocator removes
   the conflict entirely; there is nothing else moving money underneath it.

**When CBO becomes the right call**: once a market-mode campaign genuinely reaches ≥8 ad sets
with consistent spend (realistically: after productizing to a second/third client, or after a
much larger budget than 100–500 MAD/day makes many concurrent ad sets viable) — at that point,
CBO's own real-time reallocation across a genuinely large, fast-signal set is likely to
outperform a hand-built bandit, and fighting it would be the mistake (this restates
`scope-features.md` domain 5's "skip-Meta-does-it for the allocation algorithm itself" verdict,
now bounded by the concrete ad-set-count floor from B2).

### B4. New `EngineAction.action_type` values

- **`rebalance_adset_budget`** — the ABO bandit's daily proposal: a bounded per-ad-set budget
  delta (`payload` carries `{adset_id, delta_mad, new_daily_budget_mad}`), magnitude capped by
  `weekly_change_pct_max` (ENG3, already exists — reused, not duplicated), `reason_fr` states
  which proxy metric moved (e.g. "3 signatures cette semaine sur l'ensemble A contre 0 sur B").
  Full statistical design (which bandit, what prior, what minimum-exploration floor) is the
  `scope-science.md` Mission S1 deliverable — out of scope for this Treasury doc, which only
  fixes where the proposal plugs into the existing model (`EngineAction`) and the existing
  guardrail (`weekly_change_pct_max`).
- **`enable_cbo`** — the one-click "hand this campaign to Meta's own allocator" proposal
  (`scope-features.md` Mission B already named this action_type; formalized here). The guardrail
  engine (ENG9) must refuse to let this proposal even reach the approval inbox below the 8-ad-set
  floor (B2) — a service-layer check, not a UI-only warning, mirroring how PAUSED-only is
  enforced at the service layer regardless of config (ENG3's own stated pattern).

---

## (c) Launch Kit — one unified naming + UTM function, 3 templates as data

`scope-features.md`'s own audit (domains 11/12/13) already concluded naming conventions,
launch templates, and UTM governance collapse into **one shared function** rather than three
systems — confirmed here and specced concretely.

### C1. `crm.Lead`'s UTM/fbclid capture is already built — confirmed, not a gap

Prior research flagged this as unconfirmed. It is not a gap: **[VERIFIED against source]**
`backend/django_core/apps/crm/models.py:614-617` already carries `fbclid`, `utm_source`,
`utm_medium`, `utm_campaign` on `Lead`; `apps/crm/services.py:493-494` includes
`utm_content`/`utm_term` in the auditable-field list; and `apps/crm/services.py` already has a
dedicated Meta Lead Ads ingestion path (around line 1368-1429) that stamps
`canal=Lead.Canal.META_ADS`, `utm_source='facebook'`, and `utm_campaign`/`utm_content` from the
campaign/adset name — first-touch preserved, never overwritten on a later touch. `Lead.Canal`
already has `META_ADS` and `WHATSAPP_CTWA` as first-class values, and `Lead.TypeInstallation`
already has `RESIDENTIEL` / `COMMERCIAL` / `INDUSTRIEL` / `AGRICOLE` — i.e. the three CLAUDE.md
market modes (Industriel+Commercial collapse to one quote-generator mode, but are two distinct
`TypeInstallation` values on `Lead`, both usable in the naming schema below). **The Launch Kit
does not need to add any capture field to `crm.Lead` — it needs to add the generation function
on the `adsengine` side that populates the ad's UTM parameters at propose-time**, closing the
loop `docs/utm-governance.md` Rule 4 already flags ("Nothing in `lead.ts` validates values...
this is exactly why this has to be enforced at the link-creation step, not the code").

### C2. `generate_launch_identity()` — the one shared function

New module: `apps/adsengine/naming.py`. One pure function, no DB writes:

```
generate_launch_identity(market, objective, city, launch_date, variant, company) -> {
    "campaign_name":  f"TQ-{launch_date:%Y%m%d}-{market}-{objective}-{city}-{variant}",
    "adset_name_tmpl": "{campaign_name}-AS-{n:02d}",       # n = 1, 2, 3… filled at ad-set creation
    "ad_name_tmpl":     "{campaign_name}-AS-{n:02d}-AD-{creative_asset_id}",
    "utm_source":   "meta",                                 # already in utm-governance.md Rule 1
    "utm_medium":   "cpc",                                  # already in utm-governance.md Rule 2
    "utm_campaign": f"{market}_{objective}_{city}_{variant}".lower(),   # Rule 0 casing
    "utm_content":  None,   # filled per-ad-set/creative at ad-creation time, same slug shape
}
```

- `market` ∈ `{resid, indcom, agri}` — maps 1:1 from `Lead.TypeInstallation`
  (`residentiel`→`resid`, `commercial`/`industriel`→`indcom`, `agricole`→`agri`), so a lead that
  lands with `utm_campaign=resid_ctwa_casa_a` is trivially joinable back to the market mode
  without a lookup table.
- `objective` ∈ short Meta-objective codes used consistently across campaign name and UTM:
  `ctwa` (Click-to-WhatsApp / OUTCOME_ENGAGEMENT-messages), `leadform` (native Lead Ads /
  OUTCOME_LEADS), `traffic` (OUTCOME_TRAFFIC, rarely used).
- `variant` — single letter (A/B/C…) or short cohort id, feeding directly into the creative
  rotation cadence `scope-features.md` domain 4 already scoped (a future `CreativeAsset` field
  addition, out of this doc's scope) — the naming function is what STAMPS that cohort onto the
  live Meta objects and the UTM string in one place, so "which cohort won" is answerable by
  grepping campaign/UTM names, no join required.
- **Collision handling**: the `{n:02d}` ad-set/ad suffix is assigned by **highest-used-suffix +1
  per exact `campaign_name` prefix**, queried against `AdSetMirror`/`AdMirror` — explicitly NOT
  `count()+1`, mirroring the exact bug class CLAUDE.md's own reference-numbering rule already
  warns about (`apps/ventes/utils/references.py` — a deleted mirror row must never cause a
  collision by shrinking the count).

### C3. `docs/utm-governance.md` extension — one new rule, additive only

Add a **Rule 5** to the existing doc (no existing rule changes; `utm_source=meta` and
`utm_medium=cpc` already exist in Rules 1–2 and need no new values):

> **Rule 5 — adsengine-generated values are authoritative, never hand-typed.** Once
> `apps/adsengine` is built, every Meta campaign/ad-set/ad created through the engine has its
> `utm_campaign`/`utm_content` generated by `apps/adsengine/naming.py`'s
> `generate_launch_identity()` at `EngineAction`-propose time — the SAME function that names the
> Meta objects themselves (§C2) — and stamped into the ad's native URL Parameters field by
> `meta_client.py`. A human should never hand-type a UTM value into Ads Manager for a
> Taqinor-engine-managed campaign; if a campaign is created outside the engine (manual Ads
> Manager work), Rules 0–3 still apply by hand.

### C4. Three launch templates, as DATA (not code) — `apps/adsengine/templates.py` or a seeded fixture

Each template is a plain dict an `EngineAction` proposal instantiates with per-run overrides
(budget within ceiling, city, launch date) rather than the LLM/brief generator free-building a
campaign from scratch every time — directly reducing malformed-proposal risk, per
`scope-features.md` domain 11's own conclusion.

**Template 1 — Résidentiel CTWA**
| Field | Value |
|---|---|
| `market` / `objective` | `resid` / `ctwa` (Click-to-WhatsApp, OUTCOME_ENGAGEMENT) |
| Structure | 1 campaign, **ABO** (below the 8-ad-set CBO floor, §B2), 2–3 ad sets: broad + city-narrowed |
| Default budget | Split within `daily_budget_ceiling_mad` (default 100 MAD/day) across the 2–3 ad sets, e.g. 40/40/20 |
| Placements | Advantage+ (automatic) placements ON by default — **[PRIMARY-adjacent]** Meta's own Business Help Center: "Meta recommends using automatic placements for most advertisers" (`facebook.com/business/help/196554084569964`, confirmed via direct search-result quote; full-text fetch was blocked by the page's client-side rendering, same limitation noted throughout this pass for `facebook.com/business/help/*` pages — flag as PRIMARY-sourced-but-not-directly-fetched) |
| Qualifying question (WhatsApp opener) | "Bonjour, je suis intéressé par un projet solaire résidentiel à {ville}. Quelle est votre facture mensuelle d'électricité ?" — deliberately reuses `Lead.bill_range_bucket`'s existing bucket vocabulary (`backend/django_core/apps/crm/services.py` CHOICES list) so the WhatsApp rep's qualifying question maps straight onto an existing CRM field, no new intake mapping needed |
| Creative slots (from `CreativeAsset.type`, ENG15: `reel`/`static`/`explainer`) | ≥1 `reel` (real install footage — no-fake-footage rule), ≥1 `static` (offer/price anchor), ≥1 `explainer` (how it works); populate as Dynamic Creative multi-asset slots (`scope-features.md` domain 6) with Advantage+ Creative Enhancements (auto-background, auto-generate) pinned **OFF by default** — a synthetic background on a "real install" reel would violate the founder's no-fake-footage / checked-facts-only rule |

**Template 2 — Pompage agricole (seasonal)**
| Field | Value |
|---|---|
| `market` / `objective` | `agri` / `ctwa` |
| Structure | 1 campaign, ABO, 1–2 ad sets by agricultural region; **flight is front-loaded**, not flat — the monthly-envelope pacing curve (§A2) must be told this campaign is seasonal (a per-campaign weekday/week-of-month weight override, not the account-wide seasonality index) so the pacing engine does not flag deliberate front-loading as `over_pacing` |
| Default budget | Concentrated in the 4–6 weeks pre-irrigation-season; near-zero the rest of the year — this is a scheduling decision for the founder, not an engine-derived one; the template only carries the *shape* (front-loaded), not a hardcoded calendar date, since Morocco's irrigation season varies by crop/region |
| Placements | Same Advantage+ default as Template 1 |
| Qualifying question | "Quelle est votre HMT (hauteur manométrique totale) et le débit souhaité (m³/h) ?" — mirrors the exact sizing dimensions already in the quote engine's Pompage mode (`frontend/src/features/ventes/solar.js`, HMT + débit souhaité) so the WhatsApp qualifying answer maps directly onto the eventual devis inputs |
| Creative slots | `static` (payback/ROI card for the pump — **no inverter, no battery** in a Pompage composition per CLAUDE.md's pompage-sizing rule, so the creative must not show either), `explainer` (pump sizing logic) — no `reel` requirement (less visually distinctive than a residential rooftop install) |

**Template 3 — B2B form (Industriel/Commercial)**
| Field | Value |
|---|---|
| `market` / `objective` | `indcom` / `leadform` (native Meta Lead Ads — **not** WhatsApp; a more formal qualification flow fits a B2B buyer, and the ingestion path already exists: `apps/crm/services.py`'s Meta Lead Ads webhook handler, `Lead.Canal.META_LEAD_ADS`) |
| Structure | 1 campaign, ABO, 1–2 ad sets (industrial zones / company-size proxy targeting) |
| Default budget | Within ceiling, lower priority than Résidentiel today given Taqinor's stated volume skew (per `eng-channels.md`) — the template does not hardcode a split, it is a proposal input |
| Placements | Advantage+ default |
| Qualifying questions (native Lead Ads form fields) | "Facture mensuelle moyenne (MAD) ?", "Type de site (usine / entrepôt / bureaux) ?", "Surface de toiture disponible (m²) ?" — feed directly into the Industriel/Commercial quote mode's autoconsommation étude inputs (taux de couverture, économies, payback — CLAUDE.md quote-generator rule) |
| Creative slots | `explainer` (autoconsommation economics — taux d'autoconsommation/couverture explained), `static` (payback chart) |

---

## (d) Multi-account/bulk readiness — one paragraph, no build

Nothing needs to change in the models spec'd by ENG1–31 to support a second client later,
because they already follow the ERP's base multi-tenant pattern (CLAUDE.md's non-negotiable
Company-scoping rule): `MetaConnection`, `GuardrailConfig` are OneToOne→`Company` (ENG2/ENG3),
`CreativeAsset`/`AdCampaignMirror`/etc. carry a `company` FK, every ViewSet force-assigns
`company` server-side in `perform_create` — the exact same shape `core.TenantTheme` already
uses for per-tenant branding. Concretely: **onboarding a second client requires zero migrations**
— it is "create another `Company` row + another `MetaConnection` row with that client's own
`ad_account_id`/credentials," because ad-account identity already lives per-company on
`MetaConnection.ad_account_id` (ENG2) rather than a single global env var the way the pre-ENG
QJ9 CAPI hook does (that one-off, env-global token stays explicitly out of scope — CLAUDE.md/
`erp-arch.md` both already flag it as a separate, untouched integration). The only genuinely
NEW work for multi-account is process, not schema — `docs/adsengine-tenant-onboarding.md`
(already spec'd as ENG30's deliverable: Business Portfolio Partner-access sharing, one ad
account per client, a written-agreement checklist, never pooling data between clients) — so
this Treasury doc adds nothing to ENG30's scope, it only confirms the Launch Kit's naming
function (§C2) already takes `company` as a parameter and needs no per-client special-casing:
the `TQ-` name prefix would become configurable per white-label tenant (via `core.TenantTheme`,
already the pattern for tenant branding) only if/when a second tenant is actually onboarded —
not built now, per the mission's "no build" instruction for this section.

---

## (e) Forecast/pacing UI spec — one screen

**Recommendation: a second tab on the existing `DashboardScreen` (ENG23), not a new nav item.**
ENG23 is already spec'd as the "one number" hero dashboard (cost-per-signature); the pacing view
answers a genuinely different question (money-over-time, not lead-attribution), but adding a
whole new top-level screen for a company running 2–4 ad sets at 100–500 MAD/day is more chrome
than the volume justifies — a tab keeps the nav flat, matching `scope-features.md`'s repeated
"do not over-build for current volume" verdict across multiple domains.

**Screen contents** (`features/adsengine/DashboardScreen.jsx`, new `PacingTab` sub-component,
DOM hooks `ae-pacing-*` per the existing `ae-*` contract, ENG29):

1. **Monthly envelope header** — `monthly_budget_ceiling_mad`, current pacing state badge
   (on_track / under_pacing / over_pacing / breach_imminent / paused_for_month, §A3 table),
   days elapsed / days remaining in the month.
2. **Spend-to-date vs target curve** — a line chart with two series over the month's days:
   (i) the weekday-seasonality-aware target curve (§A2 formula 2), (ii) actual cumulative spend
   (from `InsightSnapshot`) — the ±15% `pacing_band_pct` band shown as a shaded region around
   the target line so "on track" is visually obvious without reading a number.
3. **Projection curve** — a third, dashed series: `forecast_spend` (§A2 formula 4, "if today's
   run-rate continues") extended to month-end, with the `monthly_budget_ceiling_mad` shown as a
   hard horizontal line — the moment the dashed line crosses that ceiling is exactly the visual
   the `breach_imminent` state (§A3) is warning about; this is the one place a Taqinor founder
   glancing at the screen sees the invariant, not just reads it in an alert.
4. **Per-campaign burn table** — one row per `AdCampaignMirror`, columns: spend this month,
   % of monthly envelope consumed, pacing state (same badge vocabulary as the header, computed
   per-campaign not just account-wide), cost-per-signature (reuses ENG10's existing metric,
   clickable through to the lead list — same Northbeam-style traceability ENG23 already commits
   to, never a black-box number).
5. **Alert banner** — reuses ENG13's existing `EngineAlert` list component (already spec'd for
   the main Dashboard), filtered to pacing-originated alerts (`pause_for_month` proposals,
   breach-imminent warnings) so a pacing problem is visible in the same place a guardrail
   violation already is, not a third alert surface.

No new backend endpoint beyond one addition to the existing metrics surface: `GET
/api/django/adsengine/pacing/?month=YYYY-MM` returning the computed state (§A2–A3 formulas,
company-scoped, no new persisted table per §A4) — everything else (per-campaign burn, alerts)
reuses ENG10/ENG13's already-spec'd endpoints.

---

## Summary — concrete deltas on already-merged ENG models

| Model (already spec'd) | New field(s) | Why |
|---|---|---|
| `GuardrailConfig` (ENG3) | `monthly_budget_ceiling_mad` (nullable, derived default `daily×30`), `pacing_band_pct` (default 15) | monthly envelope + drift band, distinct from `weekly_change_pct_max` |
| `EngineAction.action_type` (ENG7) | `pause_for_month`, `increase_pace`, `rebalance_adset_budget`, `enable_cbo` | pacing breach response, under-pacing nudge, ABO bandit proposal, CBO opt-in (gated ≥8 ad sets) |
| — | `apps/adsengine/pacing.py` (new, pure functions, no new table) | §A2–A3 |
| — | `apps/adsengine/naming.py` (new, pure functions) | §C2 |
| — | `apps/adsengine/templates.py` or seeded fixture (new, DATA only) | §C4 |
| `docs/utm-governance.md` | + Rule 5 (additive) | §C3 |
| `features/adsengine/DashboardScreen.jsx` (ENG23) | + `PacingTab` sub-component | §e |

No change needed to: `MetaConnection`, `CreativeAsset`, `CreativePolicy`, `WeeklyBrief`,
`InsightSnapshot`, or the multi-tenant shape of any ENG model (§d).

---

## Sources

Primary (Meta-owned, fetched directly this pass):
- [Budgets — Marketing API, Meta for Developers](https://developers.facebook.com/docs/marketing-api/bidding/overview/budgets/) — confirmed "up to 25% more than your daily budget may be spent," $10→$12.50 example. **[PRIMARY]**
- [Ad Set Budget Sharing — Marketing API, Meta for Developers](https://developers.facebook.com/docs/marketing-api/bidding/guides/adset-budget-sharing/) — confirmed opt-in, ABO-only, "up to 20%... shared budget," a "75%" baseline flex figure whose paired table example did not arithmetically reconcile in this fetch — re-verify before hard-coding. **[PRIMARY, partially unreconciled]**
- [Advantage Campaign Budget — Marketing API, Meta for Developers](https://developers.facebook.com/docs/marketing-api/bidding/guides/advantage-campaign-budget/) — confirmed CBO mechanics, no ad-set-count minimum documented, the 70-ad-set upper-bound edge case. **[PRIMARY]**
- [About Advantage+ Placements — Meta Business Help Center](https://www.facebook.com/business/help/196554084569964) — "Meta recommends using automatic placements for most advertisers," confirmed via search-result quote; direct full-text fetch blocked by client-side rendering (same limitation as every other `facebook.com/business/help/*` page attempted in this pass). **[PRIMARY-adjacent, not directly fetched]**

Vendor (own product docs, credible for their own product only):
- Madgicx Autonomous Budget Optimizer (`madgicx.com`) — "works best with at least 8-10 ad sets with consistent spend history," already captured in `scope-science.md`. **[VENDOR]**

Repo (verified directly this pass):
- `backend/django_core/apps/crm/models.py:614-617` (`Lead.fbclid`/`utm_source`/`utm_medium`/`utm_campaign` fields, already present)
- `backend/django_core/apps/crm/services.py:493-494, 1368-1429` (UTM audit-field list; Meta Lead Ads ingestion attribution logic)
- `backend/django_core/apps/crm/models.py:262-300` (`Lead.Canal`, `Lead.TypeInstallation` choices)
- `docs/PLAN.md` lines 1291-1343 (Groupe ENG, ENG1-31, full text read for this spec)
- `docs/utm-governance.md` (existing UTM rules, extended not replaced)
- `STAGES.py` (canonical pipeline stages, `SIGNED` = conversion event)

Prior-session scratchpad dossiers consulted (not re-summarized, cited where they directly bear
on a claim above): `eng-meta-tooling.md`, `erp-arch.md`, `scope-features.md`, `scope-science.md`.

Unresolved / flagged for a future live check (not resolvable from docs alone):
- The "7× daily budget per week" cap — **primary source silent**, folklore only.
- The exact "75%+20%" Ad Set Budget Sharing ceiling — **primary source found but arithmetic
  unreconciled in this fetch**; irrelevant to Taqinor's near-term design (§B2 floor already
  keeps Taqinor off ABO Budget Sharing at 2-4 ad sets) but worth a clean re-fetch before ANY
  future feature depends on the exact number.
