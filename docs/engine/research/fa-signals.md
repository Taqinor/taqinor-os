# FA-SIGNALS — Multi-Signal Weighted Rewards (spec-grade)

Research date: 17 Jul 2026. Mission: "all signals at once, each with its own weight."
Builds on `dd-science-core.md` (the bandit + MDE reality) and `dd-meta-mechanics.md` (what Meta's
API actually exposes per ad). Every external number carries a URL + date + [VERIFIED]/[UNVERIFIED].
Funnel volumes are taken from `dd-science-core.md` §1.1 (100 MAD/day ≈ $10/day anchor).

---

## 0. Bottom line up front

**The founder's 3-layer prior is correct — it is, almost exactly, what both the academic literature
and the ad industry actually do — but it needs one addition and several precisions.** Refined design:

- **Layer 1 — Bandit reward = ONE scalar proxy** (conversation-per-impression). This is the
  *scalar-collapse* pattern the whole ad industry runs on (Meta's own auction and value-based
  bidding both collapse many signals into one scalar and hand it to one optimizer). Keep it.
- **Layer 2 — a fixed-weight HEALTH SCORE** for ranking/alerting/human display, weights set by
  design and reviewed quarterly, **never learned at our n**. This is the "composite index," and the
  Goodhart literature is explicit that a composite belongs *here* (human display), not inside an
  autonomous optimizer. Keep it — but **split it into a CREATIVE score and an OPERATIONS score**
  (below) so slow sales never taints creative allocation.
- **Layer 3 — CRM-truth divergence veto** (already designed, `dd-science-core.md` §2.7). Keep it.
- **NEW Layer 0 — hard GUARDRAIL constraints that throttle DOWN only** (frequency cap,
  negative-feedback floor, CPL ceiling, account-quality drop). This is the *constrained-bandit*
  layer; it is safe to automate precisely because it only ever reduces spend or pauses, never scales
  up (respects the born-PAUSED rule). The founder's design implied this in the guardrails but it
  should be named as its own quadrant.

**Learning the weights is fantasy at our volume — confirmed with a hard number:** the canonical
method (surrogate index) needed **200 experiments / 1,098 arms** at Netflix and *still* missed
21–35% of good launches. We have ~150 leads and 3–9 signatures per quarter. Not close. Nobody learns
composite ad-weights at small-advertiser scale — the industry hand-weights or scalar-collapses.

---

## 1. (a) The signal inventory — volume / latency / noise / API reality / role

Volumes at 100 MAD/day from `dd-science-core.md` §1.1. "Latency" = time from the impression to when
the signal is trustworthy. "Role" is the recommendation this dossier lands on.

| Signal | /day | /week | Latency (maturation) | Noise at $10/day | API availability | **Role** |
|---|---:|---:|---|---|---|---|
| Impressions | 1,800 | 12,700 | instant | negligible (huge n) | ad-level daily [VERIFIED] | bandit **denominator** |
| Link clicks / CTR (0.02) | 36 | 254 | seconds | moderate (MDE ±25%/14d) | ad-level daily [VERIFIED] | health input; alt bandit numerator |
| Landing events (LPV) | ~28* | ~200* | seconds | moderate | ad-level (pixel) [VERIFIED] | **N/A for CTWA** — see note | 
| **CTWA conversations started** | 24 | 165 | minutes–hrs (7-day attrib.) | moderate (~165 ev/wk) | `onsite_conversion.messaging_conversation_started_7d`, per-ad daily [VERIFIED existence] | **BANDIT REWARD numerator** |
| Reply-within-SLA | — | ~165 | minutes | low, but **ops not creative** | internal (WhatsApp/CRM) | **OPERATIONS** score only |
| Qualified lead (CRM) | 1.6 | 11.5 | hours–days | high (MDE ≫100%) | internal (crm/selectors) | health input + divergence veto |
| Devis sent | ~0.7 | ~5 | days | high | internal (ventes/selectors) | OPERATIONS score |
| Devis opened (tracked) | ~0.5 | ~3 | days | high | internal (tracked open) | OPERATIONS score |
| **Signature** | 0.1 | 0.7 (≈3/mo) | **weeks** (solar cycle) | Poisson noise (CI [0.62, 8.77] on 3) | internal (signed Devis) | **inform / veto only** — quarterly |
| CPL variants (spend/lead) | derived | — | = lead latency | high | derived | health input |
| Frequency | daily | — | daily | low | ad-set daily [VERIFIED] | **guardrail** (fatigue) |
| Quality / relevance diagnostics | — | — | **35-day window, point-in-time** | ordinal, 3 levels | `quality_ranking`, `engagement_rate_ranking`, `conversion_rate_ranking`, per-ad, **appears after ~500 impressions**, **only last 35 days** [VERIFIED] | health input + guardrail; **NOT a reward** |
| Negative signals (hide/report) | — | — | daily-ish | very sparse at our volume | **packaged inside `quality_ranking`**; raw per-ad hide/report counts largely deprecated (Aug-2024 metric purge) — treat raw counts as **[UNVERIFIED / unreliable]** | guardrail (via quality_ranking) |

\* Landing-page views only exist for website/lead-form ad variants. **For CTWA ads the click opens
WhatsApp — there is no website landing event.** So "landing events" is not a funnel-wide signal for
us; it applies only to the non-CTWA creative variants. (Source: CTWA mechanics, `dd-meta-mechanics.md` (h).)

**Three API facts that change the design (all [VERIFIED] via search 17 Jul 2026):**
1. **Relevance diagnostics are a snapshot, not a time series.** `quality_ranking` /
   `engagement_rate_ranking` / `conversion_rate_ranking` are only available for the **last 35 days**,
   are **comparative** (vs competitors on the same audience), appear only **after ~500 impressions**,
   and are 3-level ordinal (Above/Average/Below). → They can inform a *current-state* health flag and
   drive a guardrail, but they **cannot** be a bandit reward (no per-day numeric history, laggy,
   competitor-relative). Source: [supermetrics — FB field changes/historical limits](https://community.supermetrics.com/product-updates/facebook-ads-field-changes-historical-data-limitations-732) (2026); [Meta — About Quality Ranking](https://www.facebook.com/business/help/303639570334185).
2. **Raw per-ad hide/report COUNTS are not a reliable API signal.** Meta deprecated 100+ Insights
   metrics in Aug 2024 and de-emphasises granular negative feedback in favour of the diagnostics.
   The usable negative signal is `quality_ranking = Below Average`, not a hide-rate you can regress
   on. Source: [ppc.land — Meta to deprecate 100+ metrics](https://ppc.land/meta-to-deprecate-over-100-unique-metrics-from-ads-insights-api-on-october-30/); [Jon Loomer — relevance score / feedback](https://www.jonloomer.com/facebook-ads-relevance-score/).
3. **Signature can never be a CTWA CAPI value event.** For CTWA ads, only 1 CAPI event per click,
   inside 7 days (`dd-meta-mechanics.md` (h)); a signature closing weeks later is outside that window.
   → We physically cannot feed money-truth back to Meta's optimizer the way an e-com store feeds
   purchase value. This is *why* our design keeps signature as a human-read veto, not an optimizer
   input.

---

## 2. (b) The formal options — what the literature and industry actually use

### 2.1 Scalarized composite reward (fixed weights) — *the industry default*
Linear (or Chebyshev) scalarization collapses a vector of objectives into one scalar the optimizer
maximises. It is the popular choice in multi-objective RL and is what every industry "campaign score"
is. Caveats from the literature: linear scalarization **cannot reach concave regions of the Pareto
front**, and the weights are a subjective modelling choice. Source: [Designing multi-objective MAB
algorithms (Drugan & Nowé)](https://ai.vub.ac.be/sites/default/files/MO_MAB_IJCNN_Accepted_v2.pdf).
**Industry precedent is overwhelming and it is scalarized, not multi-objective:**
- **Meta's own auction is a fixed-form scalar composite:** `Total Value = Bid × Estimated Action
  Rate + Ad Quality`. A value estimate plus a quality/negative-feedback term, hand-designed weights,
  one winner. Source: [Meta — About ad auctions](https://www.facebook.com/business/help/430291176997542); [mohitdave.com — Total Value](https://mohitdave.com/facebook-ads-total-value/) (2026).
- **Value-based bidding / pLTV** collapses *all* downstream value into ONE scalar per event
  (contribution margin or predicted-LTV score) fed via CAPI; Meta optimises "toward whatever value
  you send." Source: [AdZeta — pLTV bidding Meta 2026](https://www.adzeta.io/blog/pltv-bidding-meta-ads-what-actually-works-2026); [servoad — value-based bidding 2026](https://servoad.com/blog/value-based-bidding-meta-ads).
  → The industry answer to "many signals" is **collapse to one scalar value, then run one optimizer**
  — exactly our Layer-1 proxy design. Multi-objective machinery is conspicuously absent in production.

### 2.2 Multi-objective bandits (Pareto / lexicographic) — *academic, wrong scale for us*
Two families: **Pareto** (estimate the non-dominated arm set) and **lexicographic** (optimize a
priority order — money first, then engagement). Regret scales with #objectives × #arms; lexicographic
explicitly **cannot** be reduced to a scalarization (scalarized optima needn't be lexicographic
optima). Sources: [Pareto Regret Analyses in MO-MAB (arXiv 2212.00884)](https://arxiv.org/pdf/2212.00884); [MO-MAB with lexicographic & satisficing objectives (Springer)](https://link.springer.com/article/10.1007/s10994-021-05956-1); [Lexicographic bandits (arXiv 2511.05802)](https://arxiv.org/html/2511.05802). **Verdict:** at 2–3 arms and ~165 proxy events/wk we cannot even resolve ONE objective's Pareto front; adding objectives multiplies the data we don't have. Skip.

### 2.3 Constrained bandits (optimize proxy s.t. guardrail constraints) — *the right SPIRIT*
Formal safe-bandit work (Safe-LUCB, stage-wise/knapsack/return-on-spend constraints) maximises one
reward subject to keeping other quantities within bounds with high probability. Sources: [Linear
Stochastic Bandits under Safety Constraints (arXiv 1908.05814)](https://arxiv.org/pdf/1908.05814); [Contextual Bandits with Stage-wise Constraints (arXiv 2401.08016)](https://arxiv.org/html/2401.08016v2); [MABs with Minimum Aggregated Revenue Constraints (arXiv 2510.12523)](https://arxiv.org/html/2510.12523v1). This is the closest formal match to what we want ("maximise conversation-per-impression, but keep frequency ≤ cap, quality_ranking ≥ floor, CPL ≤ ceiling"). We adopt the **spirit** — proxy reward + hard guardrail thresholds that throttle down — **without** the formal regret machinery (the safety guarantees need many samples/arm we don't have). This is Layer 0.

### 2.4 Learned weights (regress proxies → signature) — *fantasy at our n, with the receipts*
This is exactly the **surrogate index** (Athey, Chetty, Imbens, Kang) — combine short-term proxies
to estimate a long-term outcome under the Prentice surrogacy assumption. Source: [NBER w26463](https://www.nber.org/papers/w26463) (2019). The honest, decision-relevant benchmark is Netflix's
evaluation: **1,098 test arms across 200 A/B tests**, a *linear auto-surrogate* on 14→63-day data;
statistical inferences ~95% consistent, **but launch-decision recall was only 65–79%** — i.e. it
still missed a fifth-to-a-third of genuinely good treatments. Source: [Evaluating the Surrogate Index
… 200 A/B Tests at Netflix (arXiv 2311.11922)](https://arxiv.org/abs/2311.11922) (2023). **Taqinor's
reality:** ~150 qualified leads and **3–9 signature events** per quarter, no corpus of completed
creative experiments to fit a mapping. You cannot regress a 6–8-signal weight vector onto 3–9 noisy
binary outcomes without pure overfitting. **Verdict: learning weights is not feasible now; it is a
research item that unlocks only at ~10× volume plus a multi-dozen-experiment corpus (see §4.4).**
"Nobody does this at our scale" is the correct finding.

---

## 3. (c) Goodhart / gaming risks of composite indices

**The four types** (Manheim & Garrabrant taxonomy, widely cited): **regressional** (the proxy omits
factors, so optimizing it drifts from the goal), **extremal** (the proxy–goal link breaks at
extremes), **causal** (correlation mistaken for a lever), **adversarial** (agents actively game the
target). Sources: [KPI Tree — Goodhart's Law](https://kpitree.co/guides/frameworks/goodharts-law); [practical-devsecops — Goodhart in AI](https://www.practical-devsecops.com/glossary/goodharts-law/). Core warning: **single-number governance breeds single-number gaming**; a portfolio "raises the cost of manipulation … by triangulating the construct from multiple angles" but is **still gameable**.

**Documented cases (general):** a velocity/deploy-frequency KPI tied to bonuses produced a **+40%
increase in post-deployment incidents**; sales call-volume/deal-quantity targets bred high-volume
low-quality interactions; Average-Handle-Time targets caused premature call closure. Source:
[academia.edu — Goodhart, Metric Gaming, Reality Drift](https://www.academia.edu/165121608/Goodhart_s_Law_Metric_Gaming_and_Reality_Drift_When_Measures_Become_Targets).

**Ads-specific, directly relevant to our candidate weights:**
- **A weight on CTR breeds clickbait/engagement-bait creative** — and Meta *penalises* it through
  `quality_ranking`, so CTR-chasing can lower the very score that protects delivery. (This is why CTR
  gets a *capped* weight and is paired with the quality_ranking guardrail below.)
- **A weight on conversation-rate breeds low-intent "tire-kicker" conversations** — already named in
  `dd-science-core.md` §2.7 as the exact pathology the CRM-divergence veto exists to catch. This is a
  textbook *regressional* Goodhart: conversation-per-impression omits intent, so maximizing it drifts
  toward cheap chatter unless the money rung vetoes.

**Mitigations the literature prescribes — and how our design already uses each:**
- **Paired shadow/guardrail metrics** → our hard-guardrail layer (quality_ranking floor, frequency
  cap, CPL ceiling) and the CREATIVE-vs-OPERATIONS split.
- **Metric trees** (game one node → visible distortion in a linked node) → the CRM-divergence veto is
  precisely this: if the proxy winner and the signature winner disagree, the tree lights up.
- **Quarterly review / rotation + qualitative checks** → weights reviewed quarterly, never learned;
  the WeeklyBrief is the human qualitative check.
- **Keep the composite OUT of the autonomous loop** → this is the single most important consequence:
  because a composite is gameable, it drives *display and alerting*, never the bandit. The optimizer
  runs on the single hardest-to-game, highest-volume proxy.

---

## 4. (d) THE RECOMMENDATION — confirmed and specified

**Confirm the 3-layer design; add the guardrail quadrant; split the health score in two.** Full
architecture:

```
Layer 0  HARD GUARDRAILS      autonomous, THROTTLE-DOWN only      (constrained-bandit spirit)
Layer 1  BANDIT REWARD        single scalar proxy = conv/impr     (autonomous up + down, §dd-science-core)
Layer 2  HEALTH SCORES        fixed weights, human display        (creative score + operations score)
Layer 3  CRM DIVERGENCE VETO  escalate to human                   (metric-tree guardrail, §2.7)
```

### 4.1 The CREATIVE health score (per ad, weekly, 0–100)
Purpose: rank creatives for the WeeklyBrief and fire alerts. Never feeds the bandit.
```
H_creative = 100 · Σ_i w_i · s_i(x_i)      s_i ∈ [0,1],  Σ w_i = 1
```
| Signal x_i | weight w_i | Rationale for the weight |
|---|---:|---|
| proxy conv/impr vs account median | **0.30** | The money-correlated top signal AND the bandit's own north star; highest weight so the human score tracks what the optimizer optimizes. |
| CTR vs benchmark | **0.15** | Cheap, high-volume, but the most gameable (clickbait) → deliberately *capped*, and cross-checked by quality_ranking. |
| cost-per-conversation (CPWA) vs target | **0.15** | Efficiency; ties spend to the proxy. |
| cost-per-qualified-lead (CRM) vs target | **0.20** | Money-truth pull, but laggy/noisy → moderate; only counted once the cohort is ≥14 days mature, else weight is renormalized out. |
| quality_ranking (ordinal → score) | **0.12** | Packages hides/reports/negative feedback; also a delivery-health guardrail. |
| frequency health | **0.08** | Fatigue penalty. |

Normalization `s_i` (piecewise-linear to a benchmark stored on `GuardrailConfig`, mirroring the
industry template's linear interpolation):
- **ratio signals** (proxy, CTR): `s = clip((x/benchmark − 0.5)/(1.3 − 0.5), 0, 1)` → 0 at ≤0.5×, 1 at ≥1.3× the benchmark.
- **cost signals** (CPWA, CPL): inverted → `s = clip((1.5 − x/target)/(1.5 − 1.0), 0, 1)` → 1 at ≤target, 0 at ≥1.5× target (the exact shape of the industry template's CPA rule: ≤target→100, 1.5×→50, 2×→0). Source template: [adlibrary — Meta Ads Campaign Scoring System](https://adlibrary.com/posts/meta-ads-campaign-scoring-system).
- **quality_ranking**: Above=1.0, Average=0.6, Below=0.0; if unavailable (<500 impr) drop it and renormalize the remaining weights.
- **frequency**: 1.0 at ≤2, 0.0 at ≥4, linear.

Action bands (copied from the industry template): **≥70 green** (healthy, eligible to scale within
guardrails), **45–69 yellow** (audit), **<45 red** (pause/replace).

### 4.2 The OPERATIONS / funnel health score (per segment, weekly, SEPARATE)
This is the **improvement on the single-score prior.** Reply-within-SLA, devis-sent-per-qualified,
devis-open rate, and the signature cohort measure **sales/ops, not the creative.** Mixing them into
the creative score is itself a Goodhart trap — a great creative would score badly because sales was
slow to reply. Keep a separate ops score so the two never cross-contaminate; the WeeklyBrief shows
both side by side.

### 4.3 Latency handling — alignment windows (the hard part, specified)
Signals mature at different speeds, so **anchor every signal on the impression/click date and only
fold a signal into the composite for cohorts older than that signal's maturation window** ("cohort
watermark"). Never compare a mature number against an immature cohort.

| Signal group | maturation age | trailing window used | in weekly score? |
|---|---|---|---|
| impressions, CTR, frequency, quality_ranking | ~0–1 day | 7-day trailing | yes |
| CTWA conversations (7-day attrib.) | 7 days | conversations on impressions ≥7 days old | yes |
| qualified lead, CPL | 14 days | 14–28-day cohort | yes, if cohort ≥14 d old |
| devis sent/opened | ~21 days | 21–28-day cohort | ops score |
| **signature** | **60–90 days** | quarterly cohort | **quarterly only, never weekly** |

Mechanics: for a cohort younger than a signal's maturation age, that signal is not yet in →
**renormalize the weights over the mature signals** and mark the score **"provisional."** The slow
money rungs appear on their own slower cadence (monthly/quarterly), not forced into the weekly number.
This is also why Layer 1 (the bandit) runs only on the 7-day proxy — it is the fastest signal that
still correlates with money.

### 4.4 Update path when volume grows 10× (~1,000 MAD/day; ~115 leads/wk; ~30 sig/mo)
- **CTR/proxy MDE tightens** (n ~10×) → add a 3rd–4th arm, shorten phases; proxy bandit unchanged in
  form, just faster.
- **Conv→qualified becomes weakly testable** (~500 leads/mo) → promote qualified-lead-rate from
  veto-only to a **second constrained objective** (maximise proxy s.t. qualified-rate ≥ floor) — the
  Layer-0 constraint gains teeth. Still not a second bandit reward until MDE < ~30%.
- **Signature ~30/mo** is still borderline-Poisson → remains veto/inform; do **not** promote to a
  reward.
- **Learned weights become a *pilot*, not production, only when BOTH hold:** (i) ≥ ~200–300 matured
  signature events accumulated, AND (ii) a corpus of ≥ a few dozen distinct creatives with fully
  matured funnels (the Netflix bar, scaled down). Until then keep fixed weights. Fit a **linear**
  surrogate first (per Netflix), validate on held-out creatives, and use it only for **directional
  ranking with human oversight** — never as the autonomous reward.

---

## 5. (e) Incumbent composite scores — copy / avoid

| Incumbent | What it is | Copy | Avoid |
|---|---|---|---|
| **Meta Total Value** (`Bid × EAR + Ad Quality`) | The auction's own fixed-form scalar composite with a quality/negative-feedback term | **The architecture**: fixed-weight scalar + a quality guardrail term is the production-proven answer — strongest evidence that fixed weights (not learned, not Pareto) win | — |
| **Meta value-based bidding / pLTV (CAPI)** | Collapse all downstream value into ONE scalar per event, feed the optimizer | The *idea* of scalar-collapse (= our Layer-1 proxy) | Using it now: needs volume + a value event **inside the 7-day CTWA CAPI window** — our signature closes weeks later and cannot be sent (`dd-meta-mechanics.md` (h)) |
| **Meta relevance diagnostics** (quality/engagement/conversion ranking) | 3-level ordinal, competitor-relative, 35-day, ≥500-impr | As a **health input + guardrail** | As a **reward** (ordinal, laggy, no per-day history, competitor-relative) |
| **Meta "Account Quality"** (accountquality.facebook.com) | An **integrity/compliance** score (policy adherence, rejection rate), NOT performance | Only as a **delivery-health veto** — if it drops, delivery throttles → pause/alert | Copying anything performance-wise (it measures trust, not results). Source: [Meta account quality guide](https://www.graphed.com/blog/how-to-check-facebook-ad-account-quality) |
| **Madgicx "Opportunity Score"** (0–100, gap-to-potential) | Where the biggest wins hide | The single-number + **green/yellow/red action band** UX | The "opportunity/potential" framing (speculative, opaque — it's a sales hook). Source: [Madgicx — performance scoring](https://madgicx.com/blog/meta-ads-performance-scoring) |
| **adlibrary "Campaign Scoring System"** | `Σ sub_score×weight`, piecewise-linear normalization, action bands, quarterly recalibration | **The mechanics** (our §4.1 is modelled on it): weighted sub-scores, linear interpolation to benchmark, green/yellow/red bands, quarterly recalibration, and its explicit "six traps" gaming warnings (don't over-weight raw CTR; adjust for placement) | Its **ecom weights** (ROAS 30–35%, CPA-heavy) — we have no ROAS; reweight for the CTWA/lead funnel. Source: [adlibrary](https://adlibrary.com/posts/meta-ads-campaign-scoring-system) |
| **Triple Whale** | No public "TW score" composite exists. Creative Cockpit = per-creative metric *aggregation*; "Creative Diversity Score" = **average of 6 human-tagged dimensions** (themes/formats/angles/creators/hooks/personas) — a *qualitative diversity audit*, not a performance metric | The **diversity-audit idea** as a creative-backlog health signal (avoid over-fitting one hook) | Treating diversity as a performance score. Source: [Triple Whale — Creative Diversity](https://www.triplewhale.com/creative-diversity); [Creative Cockpit KB](https://kb.triplewhale.com/en/articles/6362638-analyze-creative-performance-with-creative-cockpit) |

**Cross-cutting finding:** every production incumbent either (a) **hand-weights** a composite
(Madgicx, adlibrary, the whole "campaign scoring" cottage industry) or (b) **scalar-collapses** to
one value and lets one optimizer work (Meta's auction, value-based bidding). **None learns
composite-signal weights against the money outcome at small-advertiser scale.** That only appears at
Netflix/big-tech scale with hundreds of experiments. Our design is squarely in the mainstream.

---

## 6. Config additions (on `GuardrailConfig` unless noted)

| Param | Default | Source |
|---|---|---|
| health-score weights (creative) | 0.30/0.15/0.15/0.20/0.12/0.08 | §4.1 |
| health bands | green ≥70 / yellow 45–69 / red <45 | adlibrary template |
| CPL sub-score shape | 1.0 at ≤target, 0.0 at ≥1.5× | adlibrary CPA rule |
| frequency guardrail | reduce/rotate at freq > cap (default 3) | fatigue |
| quality_ranking guardrail | pause+alert on Below-Average sustained | negative-feedback veto |
| CPL guardrail ceiling | cap+propose at CPL > X× target for ≥14 d | Layer 0 |
| account-quality veto | pause+alert on account-quality drop | delivery health |
| cohort watermark per signal | 7 / 7 / 14 / 21 / 60–90 days | §4.3 |
| weight review cadence | quarterly, human | Goodhart mitigation |
| learned-weights trigger | ≥200–300 sig events AND ≥ dozens of matured creatives | Netflix bar, §4.4 |

---

## Sources

Academic / primary:
- [The Surrogate Index (NBER w26463)](https://www.nber.org/papers/w26463) — Athey, Chetty, Imbens, Kang, 2019
- [Evaluating the Surrogate Index … 200 A/B Tests at Netflix (arXiv 2311.11922)](https://arxiv.org/abs/2311.11922) — 1,098 arms, 65–79% launch recall, 2023
- [Designing multi-objective MAB algorithms (Drugan & Nowé)](https://ai.vub.ac.be/sites/default/files/MO_MAB_IJCNN_Accepted_v2.pdf) — scalarized vs Pareto
- [Pareto Regret Analyses in MO-MAB (arXiv 2212.00884)](https://arxiv.org/pdf/2212.00884)
- [MO-MAB with lexicographic & satisficing objectives (Springer 2021)](https://link.springer.com/article/10.1007/s10994-021-05956-1)
- [Lexicographic Bandits (arXiv 2511.05802)](https://arxiv.org/html/2511.05802)
- [Linear Stochastic Bandits under Safety Constraints (arXiv 1908.05814)](https://arxiv.org/pdf/1908.05814)
- [Contextual Bandits with Stage-wise Constraints (arXiv 2401.08016)](https://arxiv.org/html/2401.08016v2)
- [MABs with Minimum Aggregated Revenue Constraints (arXiv 2510.12523)](https://arxiv.org/html/2510.12523v1)

Meta primary / near-primary:
- [Meta — About ad auctions](https://www.facebook.com/business/help/430291176997542)
- [Meta — About Quality Ranking](https://www.facebook.com/business/help/303639570334185)
- [Meta — About Ad Relevance Diagnostics](https://www.facebook.com/business/help/403110480493160)
- [ppc.land — Meta deprecates 100+ Insights metrics](https://ppc.land/meta-to-deprecate-over-100-unique-metrics-from-ads-insights-api-on-october-30/)
- [supermetrics — FB field/historical limitations](https://community.supermetrics.com/product-updates/facebook-ads-field-changes-historical-data-limitations-732)

Goodhart:
- [KPI Tree — Goodhart's Law & metric design](https://kpitree.co/guides/frameworks/goodharts-law)
- [practical-devsecops — Goodhart's Law in AI](https://www.practical-devsecops.com/glossary/goodharts-law/)
- [academia.edu — Goodhart, Metric Gaming, Reality Drift](https://www.academia.edu/165121608/Goodhart_s_Law_Metric_Gaming_and_Reality_Drift_When_Measures_Become_Targets)

Industry composite scores (secondary, directional):
- [adlibrary — Meta Ads Campaign Scoring System](https://adlibrary.com/posts/meta-ads-campaign-scoring-system) (weights + normalization template)
- [Madgicx — Meta Ads performance scoring](https://madgicx.com/blog/meta-ads-performance-scoring)
- [Triple Whale — Creative Diversity](https://www.triplewhale.com/creative-diversity) & [Creative Cockpit KB](https://kb.triplewhale.com/en/articles/6362638-analyze-creative-performance-with-creative-cockpit)
- [AdZeta — pLTV bidding Meta 2026](https://www.adzeta.io/blog/pltv-bidding-meta-ads-what-actually-works-2026); [servoad — value-based bidding 2026](https://servoad.com/blog/value-based-bidding-meta-ads)
- [mohitdave.com — FB Total Value / quality score](https://mohitdave.com/facebook-ads-total-value/)
- [graphed.com — check FB ad account quality](https://www.graphed.com/blog/how-to-check-facebook-ad-account-quality)
