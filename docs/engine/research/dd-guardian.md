# THE GUARDIAN — Rules, Alerting, Anomaly Detection (spec-grade)

Research date 16 Jul 2026. Builds ON TOP of the already-merged Groupe ENG plan
(`docs/PLAN.md` ENG1–ENG31, `docs/CODEMAP.md` §"adsengine") — this dossier does not
re-derive `apps/adsengine` architecture, only speccs the **guardrail/alerting/anomaly
layer** (ENG9 "Moteur de garde-fous" + ENG13 "Alertes WhatsApp-first") in enough detail
to build against. Field/model names below (`GuardrailConfig`, `EngineAction`,
`EngineAlert`, `CreativeAsset`, `daily_budget_ceiling_mad`, `weekly_change_pct_max`,
`anomaly_window_hours`, `auto_rotate_creative`, `auto_rebalance_within_band`) are the
REAL names already committed in `docs/PLAN.md` lines 1291–1342 — reused verbatim, not
invented fresh. Hero metric = **coût par signature**, keyed off `STAGES.py` `SIGNED`
(never hardcoded) per ENG10.

**Source-quality note (carried over from the prior meta-tooling/competitor dossiers):**
this space is dominated by the same ~20–30 near-identical "2026 guide" content-farm
sites (get-ryze.ai, adlibrary.com, theoptimizer.io, adamigo.ai, etc.) that recycle
identical numbers with no primary citation. Every claim below is tagged
**[VERIFIED]** (primary vendor doc / official help center / Meta developer doc,
fetched and quoted), **[INDEPENDENT]** (named trade press or a single detailed
practitioner source, corroborated), or **[UNVERIFIED-CLUSTER]** (only the content-farm
cluster says this — directional at best). Statistical folklore (split-test minimums,
frequency thresholds) is explicitly flagged where **primary sources are silent**.

---

## PART (a) — Unified condition/action vocabulary → DSL proposal

### A1. The "47 conditions × 12 actions" claim — traced and downgraded

The task brief's own framing ("the 47 conditions x 12 actions") was checked directly
against primary sources. **Verdict: UNVERIFIED-CLUSTER, do not treat as an exact spec.**

- The exact sentence "The 2026 version supports 47 different conditions and 12 action
  types" traces to **get-ryze.ai** — a site the prior `eng-competitors.md` and
  `ux-adtools.md` dossiers already named as part of the content-farm cluster (both
  independently flagged it before this session ever searched this specific claim).
  [UNVERIFIED-CLUSTER]
- Bïrch's (Revealbot's post-rebrand name) own primary help-center article
  (`help.bir.ch/en/articles/1526011-creating-automated-rules`, fetched directly)
  describes categories — status-based, metric-based, name-based, nested AND/OR,
  ranking/relative-performance conditions, metric-vs-metric comparison — but **never
  states an exact count of 47**. [VERIFIED absence of the claim in the primary doc]
- Bïrch's own marketing page (`bir.ch/features`, fetched directly) states **"more than
  20 actions"**, not 12. [VERIFIED, contradicts the "12 actions" figure]
- **Conclusion**: treat "47×12" as marketing-copy noise, not a spec to replicate. The
  REAL, verifiable vocabulary (below) is what the unified DSL is built from.

### A2. Revealbot/Bïrch — verified vocabulary (primary: `help.bir.ch`, `bir.ch`)

**Conditions** [VERIFIED via `help.bir.ch/en/articles/1526011`]:
- Status-based (e.g. "ad set status is active")
- Metric-based: CPM, CPC, CTR, CPA, ROAS, spend, reach, impressions, conversions,
  custom conversions, app-specific (cost per install/checkout/level-completed/trial
  started) [VERIFIED via `bir.ch/facebook-automated-rules` cheat sheet]
- Name-based filtering (campaign/ad set/ad name contains X)
- **Ranking conditions** — relative performance vs other items in the same set (e.g.
  "bottom 20% by ROAS this week") — the one condition type genuinely absent from
  Meta's native rules (see Part d)
- **Metric-vs-metric comparison** — compare a metric to itself across two time windows,
  or two different metrics to each other
- Nested conditions: **"AND = all conditions must be met... OR = at least one of the
  conditions must be met"**, with `+ Group` nesting for arbitrary depth [VERIFIED,
  direct quote]
- Time windows: **"Today", "Last 3 days incl. today", "Last 7 days incl. today"**
  [VERIFIED] plus custom date ranges under "Show more options"

**Actions** [VERIFIED, `help.bir.ch` + `bir.ch/features`]: pause, start/resume,
increase/decrease budget or bid (fixed amount or %), duplicate, notify (email/Slack).
"More than 20 actions" total per the primary marketing page, but the *categories* are
these six.

**Execution cadence** [VERIFIED, `help.bir.ch`]: **"15 minutes to 72 hours"**
configurable check frequency, plus day/time scheduling and a **per-entity frequency
cap on the action itself** ("prevents actions more often than specified intervals" —
i.e. Revealbot has its own built-in cooldown/dedup concept, directly relevant to
Part (c) below).

### A3. Madgicx — 4 named tactics, not a free rule-builder

[VERIFIED via `academy.madgicx.com/lessons/madgicx-automation-tactics`, fetched
directly] Madgicx ships **four pre-built automation "tactics"** (plus a custom
rule option, less documented):

| Tactic | Metric(s) | Threshold logic | Action | Reset |
|---|---|---|---|---|
| **Stop Loss** | cost/conversion, ROAS | pauses when spend > threshold without meeting conversion target, OR ROAS below floor | pause ad set/ad | daily (midnight, customizable) |
| **Revive** | conversion count, ROAS | reactivates when performance ≥ minimum (e.g. 1+ purchase at 2.5+ ROAS) — accounts for delayed attribution | unpause | never (performance-window triggered) |
| **Surf** | conversion events, daily spend | "if EVENT occurs X+ times and spend < Y" | scale budget proportionally by performance tier (top/good/medium/worst) | daily |
| **Sunsetting** | ROAS (7d + 3d trailing), cost/conversion | reduces budget at threshold 1, permanently pauses at threshold 2 if still poor | gradual budget cut → pause | never (progressive) |

**The Madgicx silent-failure trap (already known from `ux-adtools.md` C4, reconfirmed
here)** [INDEPENDENT, G2 reviews]: *"Automated rules are very unreliable and will not
run on schedule, or sometimes not even run at all, with no warning or retries."* This
is the single most important negative lesson for the Guardian's design: **every rule
execution must be logged, and every non-execution must alert** — never silent.

### A4. Smartly.io — feed-driven triggers, enterprise-scale, thin public docs

[VERIFIED via `smartly.io/product-features/triggers`, `docs.smartly.io`, both fetched
directly] Smartly's triggers are **data-feed-driven, not a condition/operator UI** —
"triggers can switch ads on or off depending on any set of criteria that you can reduce
to a data feed: stock prices, weather, time of day, traffic speed... and performance."
Documented actions: pause underperforming, scale budget for high performers,
**refresh/rotate creative** to combat fatigue (Smartly is the ONLY one of the three
competitors with a documented native "rotate creative" action — directly maps to the
brief's `rotate_in_challenger`). Technical detail (operators, AND/OR, rule caps,
dry-run, cadence) is **not publicly documented** — Smartly gates this behind
onboarding/CSM, consistent with the C5/C6 complaints already logged in `ux-adtools.md`
(steep learning curve, support-gated). [The 404 on `docs.smartly.io/docs/scale-across-
channels-with-automation` and the thin content on the use-cases page are themselves
evidence of this — Smartly's automation depth is real but not self-serve-documented.]

### A5. Unified condition/action taxonomy — merged into ONE vocabulary

| Category | Revealbot/Bïrch | Madgicx | Smartly | → Taqinor DSL field |
|---|---|---|---|---|
| Cost efficiency | CPA, ROAS | cost/conversion, ROAS | performance feed | `cost_per_lead_mad`, `cost_per_signature_mad`, `roas` (if ever revenue-tied) |
| Delivery health | CPM, CTR, frequency, reach | — | — | `cpm_mad`, `ctr_pct`, `frequency`, `reach` |
| Volume | spend, impressions, conversions | spend, conversion count | spend feed | `spend_mad`, `impressions`, `leads_count` |
| App-specific | cost/install etc. | — | — | N/A (Taqinor has no app funnel) |
| Relative/ranking | ranking conditions, metric-vs-metric | 7d-vs-3d ROAS trend | — | `*_vs_baseline` operators (Part b) |
| Status | ad/adset status | delivery status | — | `effective_status`, `review_status` |
| Time | today/3d/7d/custom | daily reset windows | — | `window.trailing_days` |
| Non-ad-platform signal | — | — | stock/weather/traffic feeds | **CRM-side fields (new — no competitor has these)** |

**CRM-side condition fields — the genuine differentiator, none of the three
competitors expose these because none of them own a CRM:**

- `ctwa_conversation_rate` — WhatsApp conversations started ÷ link clicks, per
  campaign/adset/ad. Numerator from Meta's own `messaging_conversation_started_7d`
  insights metric [VERIFIED metric name exists — WhatsApp Business Help Center,
  `faq.whatsapp.com/785493319976156`: *"each time a unique user initiates a WhatsApp
  chat... Meta records a Messaging Conversation Started event"*, 7-day dedup window],
  denominator from the mirror's `clicks`/`link_clicks` insight field.
- `lead_qualification_rate` — CRM leads attributed to a campaign (via
  `crm/selectors.py`, per ENG10's existing pattern) that reach at least `CONTACTED`
  ÷ total leads created for that campaign in the window. Reads STAGES.py keys, never
  hardcoded (repo rule #2).
- `cost_per_qualified_lead` — `spend_mad` ÷ count of leads reaching `CONTACTED` (a
  lighter-weight sibling of ENG10's `cost_per_signature`, useful earlier in the funnel
  since signatures are rare — a handful/month — and qualification happens weekly).
- `cost_per_signature` — **already the ENG10 hero metric**, reused as-is, keyed off
  `STAGES.py SIGNED`. The Guardian's rules read it via `apps/adsengine/metrics.py`
  (ENG10), never recompute it independently (single source of truth).

### A6. Proposed JSON schema — `RulePolicy` (new model, sibling to `GuardrailConfig`)

`GuardrailConfig` (ENG3, already merged) is the **company-wide safety ceiling**
(one row per company: daily budget cap, max weekly change %, anomaly window,
capability toggles). `RulePolicy` is the **rule instance layer** underneath it — one
row per *active template instantiation*, matching the founder's own standing
direction in the merged ENG plan: **"règles templatisées plutôt qu'un rule-builder
libre (leçon Revealbot)"** — i.e. a small fixed catalogue of parameterized FR
templates, not a free-form condition builder exposed to a non-technical founder.
Templates themselves live in code (`apps/adsengine/rule_templates.py`, a
`STAGES.py`-style single source of truth — see A7), `RulePolicy` rows only carry the
per-company parameter overrides + on/off state.

```jsonc
// apps/adsengine/models.py — RulePolicy (new)
{
  "id": "uuid",
  "company_id": "fk → authentication.Company",           // server-forced, never from request body
  "template_key": "cost_per_signature_ceiling",           // must exist in RULE_TEMPLATES registry
  "enabled": false,                                        // default OFF — founder opts in per template
  "mode": "propose",                                        // "propose" | "auto" — "auto" only legal if
                                                             // template.capability_gate points at a
                                                             // GuardrailConfig toggle that is True
  "dry_run": true,                                          // forces "propose" + [SIMULATION] prefix
                                                             // regardless of mode, no WhatsApp send —
                                                             // founder must explicitly flip False
  "params": {                                                // whitelisted per template, validated against
    "threshold_mad": 250,                                    // template.editable_params — never arbitrary
    "window_days": 7,
    "min_samples": 5
  },
  "cooldown_hours": 6,                                       // dedup window (Part c) — defaults per severity
                                                               // if unset, from EngineAlert severity table
  "last_evaluated_at": "2026-07-16T06:15:00Z",
  "last_result": {                                           // audit trail — written EVERY evaluation,
    "condition_true": false,                                 // even when nothing fires (Madgicx-trap fix)
    "computed": {"cost_per_signature_mad": 187.4, "leads": 6},
    "insufficient_data": false
  },
  "created_by_id": "fk → CustomUser",
  "updated_at": "..."
}
```

```jsonc
// Condition DSL — stored inside RULE_TEMPLATES (code), instantiated with RulePolicy.params
{
  "logic": "all",                          // "all" (AND) | "any" (OR) — nestable
  "conditions": [
    {
      "field": "cost_per_signature_mad",   // from the A5 taxonomy
      "scope": "campaign",                 // "account" | "campaign" | "adset" | "ad"
      "operator": "gt",                    // gt|lt|gte|lte|eq | gt_pct_baseline|lt_pct_baseline
      "value_param": "threshold_mad",       // resolved from RulePolicy.params at eval time
      "window": {"type": "trailing_days", "param": "window_days"},
      "min_samples_param": "min_samples",   // below this → condition = "insufficient_data", NOT false
      "on_insufficient_data": "alert_info"  // never silently skipped (ties to Part b/c)
    }
  ]
}
```

```jsonc
// Action spec — also in RULE_TEMPLATES, resolved against the SAME EngineAction/
// EngineAlert models already merged in ENG7/ENG13 — RulePolicy never talks to
// meta_client.py directly, only ever through services.propose_action()
{
  "action_type": "pause_ad",   // maps 1:1 to EngineAction.kind — see A8 for the full enum
  "reason_fr_template": "Coût par signature de {target_name} = {value} MAD sur {window_days} j, au-dessus du plafond {threshold_mad} MAD.",
  "alert_severity": "critical",
  "requires_capability": null   // null = always requires approval; else "auto_rotate_creative" etc (ENG8)
}
```

### A7. `rule_templates.py` — the fixed catalogue (STAGES.py-style single source of truth)

Following the repo's own precedent (rule #2 — canonical values live in ONE file,
imported everywhere, CI-checked against divergence), propose
`apps/adsengine/rule_templates.py` as the **only** place condition/action DSL shapes
are defined. `RulePolicy.template_key` is a `choices=` field validated against this
registry (mirrors how `STAGES.py` keys are validated). A minimal starter catalogue
(8 templates — covers Part b's 5 anomaly detectors + 3 optimization tactics):

| `template_key` | FR label (UI) | Default action | Default `mode` |
|---|---|---|---|
| `cost_per_signature_ceiling` | "Coût par signature au-dessus du plafond" | `alert` → `propose_action(pause_ad)` | propose |
| `zero_delivery` | "Zéro diffusion malgré dépense" | `alert` (critical) | propose (no auto — needs human to check Meta account health) |
| `zero_results` | "Zéro résultat malgré diffusion" | `propose_action(pause_ad)` | propose |
| `frequency_runaway` | "Fréquence en fuite / lassitude créative" | `propose_action(rotate_in_challenger)` | propose (auto legal if `auto_rotate_creative`) |
| `disapproved_ad` | "Annonce refusée par Meta" | `alert` (critical) | propose (nothing to approve — informational, human must fix in Meta) |
| `spend_spike` | "Pic de dépense anormal vs médiane 7j" | `alert` (warning) | propose |
| `spend_collapse` | "Chute de dépense anormale" | `alert` (critical) | propose |
| `rule_execution_failed` | "Règle indisponible" (meta-alert) | `alert` | always propose, never auto, cannot be disabled by capability toggle |

### A8. `EngineAction.kind` enum extension (backward-compatible with ENG7)

`pause_ad` / `pause_adset` / `pause_campaign` / `resume_ad` / `adjust_budget_pct` /
`rotate_in_challenger` / `rebalance_budget_within_band` — all route through the
already-specced `services.apply_action()` (ENG7), which itself routes to
`meta_client.py` (ENG4) **only from an approved action**, and `meta_client.py` has
**no method that can ever set status=ACTIVE** (ENG4, hardcoded, tested). `alert` and
`propose_action` are NOT `EngineAction.kind` values — they are DSL-level verbs that
resolve to either "write an `EngineAlert` only" (pure `alert`) or "write an
`EngineAction(status=proposée)` AND an accompanying `EngineAlert`" (`propose_action`,
the default for anything actionable). This keeps the two already-merged models doing
exactly what they were designed for (ENG7 = mutation audit trail, ENG13 = notification)
without inventing a third audit table.

### A9. Execution cadence — deliberately NOT sub-hourly

Revealbot polls as often as every 15 minutes (A2). **This is the wrong cadence for
Taqinor and should NOT be copied**, for two compounding reasons already established in
the merged `eng-meta-tooling.md` dossier:

1. **Nothing meaningful changes in 15 minutes at 100 MAD/day.** That ceiling is ~4
   MAD/hour of spend — sub-hourly evaluation adds API calls and operational complexity
   for signal that doesn't exist yet at this volume (5-15 leads/**week**, a handful of
   signatures/**month**).
2. **Meta's Business Use Case rate limiting scales the hourly call quota with an
   account's trailing spend** [per `eng-meta-tooling.md`, PRIMARY: `developers.facebook.
   com/docs/marketing-api/overview/rate-limiting`] — **a low-spend account has a
   SMALLER quota ceiling**, so aggressive polling penalizes exactly the accounts that
   can least afford it.

**Proposed cadence (extends, does not replace, ENG6/ENG11's existing Celery beat
entries):**

| Task | Cadence | Covers | Rationale |
|---|---|---|---|
| `adsengine.evaluate_guardrails` (**new**) | every 6h, queue `scheduled` | `zero_delivery`, `disapproved_ad`, `spend_spike`, `spend_collapse`, `rule_execution_failed` | These are safety-critical (money burning with no result, or an ad literally not running) — 6h catches same-day problems without sub-hourly API pressure |
| `adsengine.sync_insights_daily` (**ENG6, already merged**) | 06:10 daily | fresh `InsightSnapshot` feeds the optimization templates | unchanged |
| `adsengine.evaluate_optimization_rules` (**new**, or folded into ENG6) | daily, right after sync | `cost_per_signature_ceiling`, `zero_results`, `frequency_runaway` | needs a full day of fresh data, not urgent to the minute |
| `adsengine.generate_weekly_brief` (**ENG11, already merged**) | Mon 07:30 | trend-level proposals (creative rotation candidates, budget rebalancing) | unchanged |

### A10. Dry-run mode

`RulePolicy.dry_run=True` is the **default for every newly-enabled template** (a
"burn-in" period — matches this repo's existing pattern of `enabled=False`-by-default
connectors, e.g. `MonitoringConfig`). While `dry_run=True`:
- The condition still evaluates on the real cadence, against real data.
- If true, an `EngineAction(status=proposée)` is still written, with `reason_fr`
  prefixed `"[Simulation] "` — so the founder can see in the Actions Log (ENG28) what
  the rule WOULD have proposed, before trusting it.
- **No WhatsApp `EngineAlert` is sent** for a dry-run firing (avoid noise on a rule
  still being tuned) — it's visible in-app only.
- `mode="auto"` is **structurally impossible while `dry_run=True`** (enforced in
  `services.py`, not just a UI hint) — a simulated rule can never auto-apply.
- The founder flips `dry_run=False` explicitly per template once they trust it. This
  directly avoids Revealbot's C5 complaint ("assumes media-buying expertise") by
  making the trust-building step a first-class state, not tribal knowledge.

---

## PART (b) — SMB-relative anomaly detection

**Core principle:** every threshold below is defined RELATIVE to Taqinor's own recent
history, never as an enterprise absolute number (a "spend > 5,000 MAD/day" rule is
meaningless at a 100 MAD/day ceiling). Every formula includes a **minimum-sample
floor** — at 5-15 leads/week, a naive statistical band computed on n=2 is worse than
useless, so below the floor the condition returns `insufficient_data`, which per A6/A9
**always alerts (informational), never silently no-ops and never triggers a pause
action**.

### B1. `spend_vs_7day_median` — spend spike/collapse

```
median_7d = median(daily_spend for the 7 days before today, excluding today)
ratio = spend_today / median_7d   (guard: if median_7d == 0, use spend_floor_mad instead)

SPIKE  if ratio > 3.0   AND spend_today > spend_floor_mad (default 20 MAD)
COLLAPSE if ratio < 0.2 AND median_7d > spend_floor_mad
```
- **Default multipliers 3.0× / 0.2×** [reasoned default, no primary source states an
  exact multiplier for SMB accounts — primary sources are silent here; the 3×/0.2×
  band is a conservative starting point deliberately wider than Revealbot/Madgicx's
  enterprise-tuned defaults, meant to be tightened once Taqinor has 8+ weeks of real
  history]. `spend_floor_mad` prevents false positives when spend is near-zero (e.g.
  ratio of 4 MAD → 1 MAD is a 4x "spike" that's operationally meaningless).
- COLLAPSE is the more urgent case in practice — it usually means a payment failure,
  Advantage+ auto-pause, or account restriction (per `ux-adtools.md` §3.4: "account
  disablement resets everything") — spec it as `severity=critical`, SPIKE as
  `warning`.

### B2. `cpl_vs_trailing_band` — cost-per-lead relative band

```
window = trailing 14 days (longer than spend's 7d — lead events are sparser)
n_leads_14d = count of CRM leads attributed to the campaign in that window
if n_leads_14d < min_samples (default 5): return insufficient_data

median_cpl_14d = median(daily cpl over the window, days with ≥1 lead only)
band = [0.5 × median_cpl_14d, 2.0 × median_cpl_14d]   # simple ratio band, NOT stddev/MAD

FLAG if cpl_today (or cpl_trailing_3d, smoother) outside band
```
- **Ratio band, not a statistical (MAD/stddev) band, is the deliberate choice** for
  this volume: standard-deviation-based bands need enough samples to be stable, and
  Taqinor's weekly lead count (5-15) is too small for a stddev to mean anything most
  weeks. A simple ±2× ratio band is honest about the noise level and explainable to a
  non-technical founder in one sentence (which the repo's own FR `reason_fr` convention
  demands). [UNVERIFIED — this is a reasoned design choice, not a documented industry
  standard; folklore for enterprise split-testing (see B-note below) explicitly does
  NOT apply at this scale and should not be borrowed.]
- **Primary source silent — folklore says X**: multiple secondary blogs (get-ryze.ai,
  benly.ai, coreppc.com — none primary) claim Meta "recommends 50-100 conversions per
  variant" and "$100/day per test cell" for A/B-test statistical significance
  [UNVERIFIED-CLUSTER — no Meta help-center or developer-doc page was found stating
  these numbers directly]. **This threshold is structurally unreachable for Taqinor**
  (a handful of signatures/month, ~$10/day total budget) — which is exactly why B2
  uses a loose ratio band with a `min_samples` gate instead of borrowing enterprise
  A/B-test minimums that assume 10-100x Taqinor's volume.

### B3. `zero_delivery_detection` — two tiers

```
Tier 1 (CRITICAL) — spend with literally nothing happening:
  spend_in_window(anomaly_window_hours, default 48h from GuardrailConfig) > 0
  AND impressions_in_window == 0

Tier 2 (WARNING) — delivering but converting nothing:
  impressions_in_window > 0 AND clicks_in_window > 0
  AND leads_in_window == 0
  AND hours_since_campaign_launch > 24   # exclude brand-new campaigns still ramping
```
Tier 1 usually means a delivery/policy/payment problem (the ad literally isn't
running) — CRITICAL, immediate alert, `propose_action(pause_ad)` NOT auto (a human
needs to look at the Meta account, not just retry). Tier 2 usually means a
creative/targeting/offer problem — WARNING, feeds into `zero_results` template (A7).
`anomaly_window_hours` reuses the ENG3 `GuardrailConfig` field (default 48h) rather
than inventing a new one — single source of truth for "how long is too long."

### B4. `frequency_runaway`

```
FLAG if frequency_trailing_7d > freq_ceiling (default 3.0)
   OR frequency_slope_7d > 0  AND  frequency_trailing_7d > (freq_ceiling × 0.7)
```
- **Primary source silent — folklore says X**: no Meta help-center or developer-doc
  page states an official "fatigue" frequency number. Every number found (2.5, 3.0,
  3.5, "CTR drops 28% past 3.5", "cost/purchase rises 41% past 5.0") comes from
  secondary/practitioner blogs (adamigo.ai, wittelsbach.ai, roaspig.com — none
  primary) [UNVERIFIED-CLUSTER]. **Default of 3.0 chosen deliberately conservative**
  (lower than the "3.5 cliff" folklore) because Morocco/solar-SMB audiences are small
  and low-budget, so frequency climbs faster per MAD spent than a large-audience
  enterprise account — an assumption, not a verified fact, flagged for founder review
  once real data exists.
- The `frequency_slope_7d > 0` term (is frequency still climbing) catches the
  early-warning case even before the absolute ceiling is crossed — cheap to compute
  from `InsightSnapshot` history already stored (ENG5), no new API surface needed.

### B5. `disapproved_ad_detection`

```
FLAG if AdMirror.status (synced from Meta's ad-level review/effective_status field)
     == "DISAPPROVED"  (or equivalent rejection state)
```
Checked on every sync (part of the 6h `evaluate_guardrails` cadence, A9) since a
disapproved ad delivers ZERO impressions — this is the fastest-acting failure mode and
deserves the tightest loop of anything in this spec. Alert should surface Meta's own
human-readable rejection reason where the API returns one (an `issues_info`-style
field) — pass it through verbatim in the WhatsApp message (Part c) rather than making
the founder log into Meta to find out why.

### B6. The Madgicx anti-pattern, operationalized

Every formula above has an explicit `insufficient_data` / evaluation-failure branch
that resolves to **alert, never silent skip** — this is not a suggestion, it's wired
into A6's schema (`on_insufficient_data: "alert_info"`) and A9's dedicated
`rule_execution_failed` template, which is the one template that **cannot be disabled
by a capability toggle** (A7) — the meta-rule that watches the other rules.

---

## PART (c) — WhatsApp alert payloads

### C1. Severity tiers

| Tier | Emoji/label | Default cooldown | Auto-resolve message? |
|---|---|---|---|
| CRITICAL | 🔴 Urgent | 6h | Yes (short "c'est réglé" follow-up) |
| WARNING | 🟠 Attention | 24h | No (silently marked resolved in-app only) |
| INFO | 🔵 Info | 72h | No |

Severity is a property of the **template** (A7 table), not user-configurable per rule
instance — keeps the founder's mental model simple (matches the repo's own "règles
templatisées, pas de builder libre" direction).

### C2. Eight concrete templates (FR)

Each message follows the shape: **[emoji] root cause in one line → recommended action
in one line → deep link**. `wa.me` delivery itself is gated (ENG13: "envoi template
gated BSP = plus tard" — WhatsApp Business Solution Provider account needed for
template-message sending; these payloads are the CONTENT spec, ready the day that
gate opens, and meanwhile render identically in the in-app alert feed).

1. **`cost_per_signature_ceiling`** (CRITICAL):
   > 🔴 Urgent — Campagne "{campaign_name}" : coût par signature = {value} MAD sur
   > {window_days} j (plafond {threshold} MAD). Recommandation : mettre en pause ou
   > revoir le ciblage. Voir et approuver → {deep_link_approvals}

2. **`zero_delivery`** Tier 1 (CRITICAL):
   > 🔴 Urgent — "{campaign_name}" dépense ({spend} MAD depuis {hours}h) mais 0
   > diffusion. Probable souci Meta (paiement/révision/compte). Recommandation :
   > vérifier le compte Meta directement. Détails → {deep_link_dashboard}

3. **`zero_results`** Tier 2 (WARNING):
   > 🟠 Attention — "{ad_name}" diffuse et reçoit des clics mais 0 résultat depuis
   > {hours}h. Recommandation : tester une nouvelle création. Voir et approuver →
   > {deep_link_approvals}

4. **`frequency_runaway`** (WARNING):
   > 🟠 Attention — Fréquence de "{adset_name}" = {frequency} (seuil {ceiling}),
   > signe de lassitude créative. Recommandation : faire tourner une nouvelle
   > création. Voir et approuver → {deep_link_approvals}

5. **`disapproved_ad`** (CRITICAL):
   > 🔴 Urgent — "{ad_name}" refusée par Meta : « {rejection_reason} ». Recommandation :
   > corriger et resoumettre dans Meta directement. Détails → {deep_link_campaign}

6. **`spend_spike`** (WARNING):
   > 🟠 Attention — Dépense de "{campaign_name}" = {spend_today} MAD aujourd'hui,
   > {ratio}× la médiane des 7 derniers jours. Recommandation : vérifier qu'aucun
   > changement involontaire n'a eu lieu. Détails → {deep_link_dashboard}

7. **`spend_collapse`** (CRITICAL):
   > 🔴 Urgent — Dépense de "{campaign_name}" quasi nulle ({spend_today} MAD, médiane
   > {median} MAD/j). Probable paiement échoué ou compte suspendu. Recommandation :
   > vérifier le compte Meta immédiatement. Détails → {deep_link_dashboard}

8. **`rule_execution_failed`** (WARNING → escalates to CRITICAL after 3 consecutive
   failures):
   > 🟠 Attention — La règle « {template_label_fr} » n'a pas pu s'exécuter
   > ({error_summary}). Aucune vérification automatique n'a eu lieu depuis {hours}h.
   > Recommandation : vérifier la connexion Meta. Détails → {deep_link_connection}

### C3. Dedup / cooldown logic

```
dedup_key = (company_id, template_key, target_type, target_id)
```
- On a fresh firing where no open (unresolved) `EngineAlert` exists for `dedup_key`:
  create it, send.
- On a repeat firing while an alert for the same `dedup_key` is still open AND inside
  `cooldown_hours` (C1 defaults, overridable via `RulePolicy.cooldown_hours`): **update
  the existing row's `last_seen_at` and computed values, do NOT re-send** — this is
  what stops the exact Revealbot-documented "per-entity frequency cap on the action"
  pattern (A2) from becoming WhatsApp spam.
- On a repeat firing AFTER `cooldown_hours` has elapsed and the condition is STILL
  true: re-send, but **do not reset the alert's `first_seen_at`** — the WhatsApp
  message should be able to say "depuis {total_hours}h" using the original first
  detection, not just the latest resend, so the founder can see how long a problem has
  persisted.
- When a subsequent evaluation finds the condition now false: mark `resolved_at`, and
  for CRITICAL only, send a one-line follow-up ("✅ Résolu — {template_label_fr} pour
  {target_name}").
- **Escalation, not fatigue**: if a WARNING-tier alert re-fires past 3 consecutive
  evaluation cycles without resolving, bump it to CRITICAL **once** (never repeatedly)
  — surfaces genuinely persistent problems without turning every recheck into a new
  urgent ping.

---

## PART (d) — Wrap-vs-build verdict on Meta native Automated Rules

### D1. What Meta's own Automated Rules actually offer [VERIFIED, primary + independently corroborated]

- **250-rule cap per ad account** (active + inactive combined) [INDEPENDENT via
  multiple secondary sources converging on the same figure, sourced from Meta's own
  Business Help Center "Limits to Automated Rules" article — page title confirmed
  directly (`facebook.com/business/help/222640851458826`), but the WebFetch tool could
  not extract the numeric body text from that specific help page (JS-rendered); the
  250 figure is corroborated across independent secondary write-ups referencing that
  same page, not independently re-verified against raw HTML in this pass — tag as
  **[INDEPENDENT, high-confidence, not a raw primary quote]**]. Irrelevant at
  Taqinor's scale (a handful of campaigns) — not a constraint that matters here.
- **AND-only logic within a single rule, one condition per metric type** — stacking
  two thresholds on the same metric requires two separate rules [INDEPENDENT,
  multiple converging secondary sources describing the same UI behavior]. This is a
  REAL structural gap vs. the unified DSL (A6), which supports arbitrary AND/OR
  nesting per Revealbot's pattern.
- **Four action categories**: turn off (pause), adjust budget (fixed/%),
  adjust bid (manual-bid campaigns only), send notification (no automatic action)
  [INDEPENDENT, multiple converging secondary sources].
- **Programmatic access exists**: the Marketing API's **Ad Rules Engine**
  (`POST act_<id>/adrules_library` with `evaluation_spec` + `execution_spec`)
  [VERIFIED — `developers.facebook.com/docs/marketing-api/ad-rules`, page structure
  and endpoint confirmed directly, though the tool could not extract the full field
  enum from the JS-rendered reference pages]. Two evaluation modes:
  **SCHEDULE-based** (checked at a set interval) and **TRIGGER-based** (evaluated the
  moment underlying insights/metadata change) [VERIFIED, direct quote from the fetched
  overview page]. This means a native Meta rule could in principle be created via the
  SAME `httpx`-based `meta_client.py` already planned for ENG4 — no new dependency.

### D2. What Meta native categorically CANNOT do — the case for building

1. **No CRM-side conditions.** `cost_per_signature`, `ctwa_conversation_rate`,
   `lead_qualification_rate` are invisible to Meta — Meta has no concept of a signed
   quote or a WhatsApp conversation that turned into a lead. The entire ENG10 hero
   metric (the reason this engine exists) cannot be expressed as a native rule,
   period. This alone rules out native rules as the primary mechanism.
2. **No relative/statistical conditions.** AND-only, one-condition-per-metric, purely
   absolute thresholds — cannot express the B1/B2 relative-band logic this dossier
   argues is REQUIRED at Taqinor's volume (an absolute "spend > 5,000 MAD" rule is as
   useless here as at enterprise scale in the other direction).
3. **No propose→approve gate.** Native rules either fire the action immediately or
   only notify — there is no middle "propose, human approves, then applies" state.
   That state is a hard repo requirement (rule #3's spirit, ENG7's whole design) and
   simply doesn't exist natively.
4. **No WhatsApp.** Native notification goes to email/in-app only.
5. **No creative rotation / challenger-swap action.** Native actions are
   pause/budget/bid/notify only — `rotate_in_challenger` has no native equivalent.
6. **Same silent-failure risk class as third-party tools.** Nothing in Meta's own
   documentation contradicts the general pattern (Madgicx A3, Revealbot's built-in
   per-entity cooldown existing specifically because rules DO sometimes not fire
   cleanly) that ANY rules engine — including a first-party one — can silently not
   execute on a given cycle. Meta's docs do not claim otherwise, and no evidence was
   found either way in this research pass; treating native rules as more reliable than
   third-party ones would be an unverified assumption, not a documented fact.

### D3. Verdict — build the Guardian, wrap ONE native rule as a dead-man's-switch

**Do not build the guardrail/anomaly engine on top of Meta's native Automated Rules.**
The gaps in D2 are not edge cases — points 1-3 are the entire reason this system
exists (CRM-tied hero metric, SMB-relative thresholds, human-approval gate are all
non-negotiable repo requirements already baked into the merged ENG plan).

**Do, as a GATED (founder-decision, not auto-build) addition**, consider creating
**exactly one native Meta rule per connected ad account** via the `adrules_library`
API endpoint, purely as an infrastructure-independent safety net: *"if daily spend on
this campaign exceeds 1.5× `daily_budget_ceiling_mad`, turn it off."* Rationale: this
fires even if Taqinor's own Django/Celery/server is down, is a pure absolute-threshold
case (no CRM data needed, so D2's gaps don't apply to it), and costs nothing extra to
implement since `meta_client.py` (ENG4) already wraps the same Marketing API with
`httpx`. This is a genuine belt-and-suspenders backstop, not a replacement for the
Guardian — flag it as a candidate GATED task for a future ENG plan addendum, not
something to build unattended (it touches money-safety logic and should get a founder
nod first, consistent with the existing "GATED ENG" section in `docs/PLAN.md`).

---

## Sources

Primary (fetched directly, quoted where noted):
- `help.bir.ch/en/articles/1526011-creating-automated-rules` (Revealbot/Bïrch rule
  builder — official help center, redirected from `help.revealbot.com`)
- `bir.ch/features`, `bir.ch/facebook-ads/automated-rules`, `bir.ch/facebook-
  automated-rules` (official marketing/cheat-sheet pages)
- `academy.madgicx.com/lessons/madgicx-automation-tactics` (official Madgicx Academy)
- `smartly.io/product-features/triggers`, `docs.smartly.io/docs/use-cases-for-
  campaign-automation-with-example-feeds-1` (official Smartly site/docs)
- `developers.facebook.com/docs/marketing-api/ad-rules`,
  `developers.facebook.com/docs/marketing-api/ad-rules/ad-rules-specs` (Meta Marketing
  API official docs — Ad Rules Engine, `evaluation_spec`/`execution_spec` structure,
  SCHEDULE vs TRIGGER modes)
- `faq.whatsapp.com/785493319976156` (WhatsApp Business Help Center — Messaging
  Conversation Started metric definition, 7-day dedup window)
- `facebook.com/business/help/222640851458826` (Meta Business Help Center — "Limits to
  Automated Rules"; page title confirmed, numeric body not directly extractable via
  WebFetch — 250-rule figure corroborated only via independent secondary sources)

Independent/secondary (used cautiously, tagged inline):
- Multiple converging secondary sources on Meta's 250-rule cap, AND-only logic,
  4 action categories (cropink.com, netpeak.us, topgrowthmarketing.com and others —
  no single source treated as authoritative alone, cross-checked for convergence)
- G2 Madgicx reviews (silent-failure complaint, already logged in `ux-adtools.md` C4)
- get-ryze.ai, adlibrary.com, theoptimizer.io, adamigo.ai, wittelsbach.ai, roaspig.com,
  benly.ai, coreppc.com — content-farm-cluster tier, used ONLY for explicitly-flagged
  UNVERIFIED-CLUSTER/folklore claims (the "47×12" figure, A/B-test minimums, frequency
  fatigue thresholds), never as a basis for a spec decision

Repo sources (not external research, ground truth for field/model names):
- `docs/PLAN.md` lines 1291–1342 (Groupe ENG, already merged)
- `docs/CODEMAP.md` (adsengine app index)
- `STAGES.py` (canonical pipeline stage keys)
- Prior dossiers this session read but did not re-derive: `eng-meta-tooling.md`
  (Marketing API rate-limiting, PAUSED-by-default confirmation), `eng-competitors.md`
  (competitive landscape), `ux-adtools.md` (UX praise/complaint patterns incl. the
  Madgicx C4 silent-failure trap), `erp-arch.md` (adsengine app architecture)
