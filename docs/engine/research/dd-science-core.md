# DD-SCIENCE-CORE — The Decision Engine (the math heart), spec-grade

Deep-dive S1. Author target: a mid-level Python dev implements this without further research.
Date: 16 Jul 2026. Scope: the deterministic (no-AI-in-loop) statistics that decide how the ads
engine shifts budget between creative arms, kills losers, rotates challengers, and when it must
stop and ask a human. Wires into the already-merged Groupe ENG models
(`apps/adsengine`: `InsightSnapshot`, `EngineAction`, `GuardrailConfig`, `CreativeAsset`,
`WeeklyBrief`, `AdMirror` — see erp-arch.md).

Source discipline: every external number carries a URL + date and a [VERIFIED]/[UNVERIFIED] flag.
Where primary sources are silent (split-test minimums, bandit priors in production), that is stated
outright. The arithmetic in §1–§2 is deterministic and reproducible (script in the appendix); the
*rates* it is fed are grounded illustrative assumptions, flagged as such.

---

## 0. The two hard anchors (founder-given, treat as ground truth)

- Budget: **100 MAD/day** today (~$9.5–10.6/day; MAD/USD ≈ 10.0–10.6, MAD/EUR ≈ 10.6), scaling
  maybe to 500 MAD/day. → ~**700 MAD/week**, ~**3,000 MAD/month** (~€66/wk, ~€285/mo).
- Volumes: **5–15 qualified leads/week** (CRM), **a handful of signatures/month** (take 3/mo).

Everything else in the funnel is derived to be consistent with these two anchors + published MENA
Click-to-WhatsApp (CTWA) benchmarks. This is a LOW-DATA regime — that single fact drives the whole
design.

---

## 1. The MDE reality table — what is even detectable at these volumes

### 1.1 The anchored funnel model (assumptions flagged)

Benchmarks used (MENA CTWA), all [UNVERIFIED — single aggregator, getkanal.com "CTWA Benchmarks
2026", fetched 16 Jul 2026; directional, cross-checked against WordStream 2025 + a $2 CPMCS cold
target that recurs across sources]:
- CPM MENA: €3–7 → take **55 MAD** (~€5.2). CTR median **2%** (benchmark 1.5–2.5%).
  Click-to-opt-in (≈ click→conversation-started) median **60–75%** → take **65%**.
- Conversation→qualified-lead and qualified→signature are Taqinor-specific (solar, consultative,
  many price-curious chats). Set **conversation→qualified = 7%** and **qualified→signature = 6%**
  — chosen so the funnel *reproduces the two hard anchors* (11–12 qualified leads/wk, ~3 sig/mo).
  These two rates are the model's free parameters, flagged [ASSUMPTION, back-solved from anchors].

Resulting per-rung volume (100 MAD/day), rounded:

| Rung | Pass-through | /day | /week | /month |
|---|---|---:|---:|---:|
| Impressions | — | 1,800 | 12,700 | 55,000 |
| Link clicks (outbound) | CTR 2% | 36 | 254 | 1,100 |
| CTWA conversations started | opt-in 65% | 24 | 165 | 715 |
| **Qualified leads (CRM)** | 7% | 1.6 | **11.5** | 50 |
| **Signatures (CRM)** | 6% | 0.1 | 0.7 | **3** |

Internal check: cost/conversation = 700/165 = **4.2 MAD (~€0.40)**, inside the MENA €0.30–0.80
band → the model is self-consistent. Qualified 11.5/wk ∈ [5,15] ✓; signatures 3/mo ✓.

### 1.2 The formula (state it once)

Two independent proportions, two-sided **α = 0.05**, power **1−β = 0.80**, equal split (n per arm),
2 arms. Sample size to detect a difference between baseline p and p+δ:

```
n_per_arm = (z_{1-α/2} + z_{1-β})² · [p₁(1-p₁) + p₂(1-p₂)] / (p₂-p₁)²
z_{0.975}=1.9600 , z_{0.80}=0.8416 , (1.9600+0.8416)² = 7.849
```

Inverted to get the **Minimum Detectable Effect** given the n we actually accumulate
(pooled-variance approximation, valid for small δ):

```
δ_MDE ≈ (z_{1-α/2}+z_{1-β}) · √( 2·p(1-p) / n )  = 2.8016 · √(2p(1-p)/n)
relative_MDE = δ_MDE / p
```

Worked example, CTR rung, 14-day window (n = 12,600 impressions/arm, p = 0.02):
`2·0.02·0.98 = 0.0392; 0.0392/12600 = 3.11e-6; √ = 1.764e-3; ×2.8016 = 4.94e-3`
→ δ = **0.49 percentage points**, relative = 0.00494/0.02 = **24.7%**. A challenger creative must
beat control's CTR by ≥ ~25% *relative* to be caught in two weeks.

### 1.3 The reality table (2 arms, 50/50 split)

Per-arm trials = half the funnel volume over the window. **rel** = smallest relative lift a
fixed-horizon test can detect at 80% power.

| Rung (p) | 7 days (n/arm → rel MDE) | 14 days | 28 days | Verdict |
|---|---|---|---|---|
| **Imp→click / CTR** (0.02) | 6,300 → **±35%** | 12,600 → **±25%** | 25,200 → **±18%** | Testable, LARGE effects only |
| **Click→conversation** (0.65) | 126 → ±26% | 252 → ±18% | 504 → ±13% | Testable-ish, but that's an 8–17-**point** swing on a 65% rate = huge |
| **Conv→qualified** (0.07) | 84 → ±158% | 168 → ±111% | 336 → **±79%** | NOT testable (rate must ~double–triple) |
| **Qual→signature** (0.06) | 5.7 → ±657% | 11.5 → ±462% | 23 → ±327% | NOT testable at all |

Signature rung, the honest version: monthly signatures ~ **Poisson(3)**. Exact 95% CI for an
observed count of 3 is **[0.62, 8.77]** — a single creative's monthly signature count is
indistinguishable from anything between "barely working" and "3× better." Splitting 3 sig/mo across
2 arms (1.5 each) and running even 6 months (~9 events/arm) still only resolves a **~2× rate ratio**.
Signature-level A/B is not a test; it is quarterly human review.

### 1.4 Conclusion — which rungs are testable

- **Only the top of the funnel carries statistical power.** CTR (imp→click) is the one rung with a
  real, if coarse, test: it can catch challengers that are **≥18–35% relatively better** over
  2–4 weeks. Click→conversation is borderline (only big absolute swings).
- **The two money rungs are statistically dark.** Qualified-lead rate needs the rate to nearly
  double; signature rate is pure Poisson noise. No autonomous A/B decision may ever be made on
  these — they can only accumulate as *directional* signal over quarters and gate a **human**.
- **Design consequence (drives everything below):** the engine optimizes a **cheap top-funnel proxy
  with a bandit**, and treats the money rungs as a slow, human-read *sanity check* that can veto but
  never drive. Fine-tuning is invisible here — the engine should only ever test **big swings**
  (radically different hook/format), never 5–10% creative tweaks, because it physically cannot see
  them.

---

## 2. The bandit — beta-binomial Thompson sampling, spec-grade

### 2.1 Why a bandit, not a fixed test

At <15 qualified leads/week a fixed-horizon test wastes half the budget on the loser for the whole
window and still only detects huge effects (§1.3). A bandit shifts spend toward the leader *while*
learning, which is strictly better when (a) effects are large or (b) you'll never reach significance
anyway — both true here. Caveat, stated by GrowthBook itself: bandits "can even perform worse at
selecting the best variation more quickly than traditional experiments in some cases, such as when
there are only two arms" [VERIFIED — docs.growthbook.io/bandits/overview, 16 Jul 2026]. So the
bandit's job is **budget allocation + loser-killing**, NOT "declare a statistically-clean winner."

### 2.2 The model

- **Arms**: 2–3 active creatives (hard max 4). At our volume, 4 arms already thins each below a
  usable event rate — see §4.
- **Reward (Bernoulli)**: `success = an impression that led to a CTWA conversation started` (within
  the ad's attribution window). This composite proxy = CTR × opt-in in one number; it is the
  cheapest metric that still reflects creative quality AND correlates with cost-per-lead. Trials =
  impressions; successes = conversations. (Alternative if conversation attribution is noisy: reward
  = plain CTR, trials = impressions, successes = link-clicks — even higher event count, but ignores
  post-click quality. Default to conversation-per-impression.)
- **Prior**: **Beta(1, 1)** per arm (uniform; GrowthBook's Bayesian default is a weak prior). Honest
  and simple at low volume. *Optional* informative prior: Beta(α₀, β₀) with mean = the account's
  historical conversation-per-impression rate and total strength α₀+β₀ ≈ 30–50 ("worth ~a few
  hundred impressions"), so ~1 week of data overwhelms it. Ship Beta(1,1); expose the informative
  option as config.
- **Posterior update** (conjugate; exact, no MCMC): over the chosen window, for arm *i*
  ```
  α_i = α₀ + Σ conversations_i
  β_i = β₀ + Σ (impressions_i − conversations_i)
  ```
  Data source = daily `InsightSnapshot` rows (impressions, and conversations from `raw`/derived),
  keyed to the arm's `AdMirror`→`CreativeAsset`. **Window**: rolling **28 days** (or full flight if
  shorter). Optional recency: exponential decay with ~14-day half-life on older days to let a fatigued
  creative fall — ship without decay first (simpler, and creatives are swapped on fatigue anyway).

### 2.3 Allocation rule (Thompson sampling by probability-of-best)

Once per day (not per draw — more stable for money): draw **K = 10,000** Monte-Carlo samples
`θ_i ~ Beta(α_i, β_i)` for each arm; the raw weight is the **fraction of draws in which arm i is the
maximum**:
```
w_i = P(arm i is best) ≈ (1/K) Σ_k 1[ θ_i^(k) = max_j θ_j^(k) ]
```
This is exactly GrowthBook's method (`Thompson sampling allocates traffic proportionally to the
probability that an arm is best`) [VERIFIED — docs.growthbook.io/bandits/overview]. Then apply the
exploration floor (below) and convert weights → per-arm daily budget in MAD.

### 2.4 Exploration floor — in ABSOLUTE MAD, not percent (key correction)

GrowthBook's floor is **1% of traffic per variation** [VERIFIED — same page]. **Do not copy the
percentage** at our budget: 1% of 100 MAD = 1 MAD/day = below Meta's per-ad-set delivery minimum
(~$1/day ≈ 10 MAD), so a floored arm would simply stop delivering and never accrue data. Instead:
```
floor_per_arm = max( 20% of daily_budget , 20 MAD/day )
```
20 MAD/day (~$1.9) clears Meta's delivery floor and accrues ~360 impressions/day = enough to keep a
posterior alive. With 3 arms at 100 MAD/day: 3 × 20 = 60 MAD floored, remaining **40 MAD allocated
by w_i**. Store the floor on `GuardrailConfig` (new fields: `min_arm_daily_budget_mad` default 20,
`bandit_arm_floor_pct` default 0.20; effective floor = the max).

### 2.5 Minimum spend before an arm may be KILLED (burn-in)

GrowthBook: **≥100 users/variation before it updates weights**, and **≥40 conversions/variation**
recommended before trusting the optimizer [VERIFIED — docs.growthbook.io/bandits/config,
16 Jul 2026]. Ported to us:
- **No autonomous kill** until the arm has BOTH: `≥ 7 days live` AND `≥ 40 proxy conversions`
  (≈ what 20–35 MAD/day buys in ~1–1.5 weeks). Before that, the engine may only *rebalance within
  the band*, never pause.
- **Kill trigger** (after burn-in): `P(arm i is best) < 5%` sustained for **3 consecutive daily
  updates** (guards against one fluky day — GrowthBook's own warning against sub-daily updates).
- Weight updates themselves: don't move weights until each arm has `≥ 100 impressions` in the window
  (GrowthBook's 100-user gate); until then, hold at the floor/even split.

### 2.6 Decision cadence

- **Budget reweight: once daily.** Runs in the existing `adsengine.sync_insights_daily` Celery task
  (~06:10) → a new `adsengine.recompute_bandit` step (~06:20, after insights land). Meta's 15-minute
  API floor is irrelevant; Smartly reallocates "every midnight" [PRIMARY — smartly.io predictive
  budget allocation] and GrowthBook recommends "daily or even longer" to avoid "a fluky day of
  traffic" [VERIFIED]. Daily it is.
- **Kill / promote-challenger: weekly**, in `adsengine.generate_weekly_brief` (Mon ~07:30), so a
  human sees it in the `WeeklyBrief` inbox.

### 2.7 The reward is a LADDER — bandit on proxy + human-gated CRM-truth override

The bandit runs on the **cheap frequent proxy** (conversation-per-impression, ~165 events/wk — enough
to move a Beta). The **expensive rare truth** (cost-per-qualified-lead, cost-per-signature) can never
feed a bandit (§1.4). So:
1. Bandit allocates daily on the proxy — this is **autonomous** (auto-approved below the guardrail).
2. Weekly, `WeeklyBrief` pulls the CRM truth per creative via **selectors only**
   (`crm/selectors.py` for qualified-lead counts by `fbclid`/utm→`Lead`; `ventes/selectors.py` for
   signed `Devis`), computes **cost-per-qualified-lead** and, when ≥ a handful exist,
   **cost-per-signature** per arm.
3. **Divergence gate:** if the proxy-winner's CRM-cost rank disagrees with its proxy rank by
   more than one position AND ≥ ~10 qualified leads have accumulated for the comparison, the engine
   does **NOT** act — it raises a **human-gated `EngineAction`** ("Proxy favours creative A;
   signatures favour creative B — the cheap metric is attracting tire-kickers. Override allocation
   toward B?"). Below that evidence bar, the proxy rules and the CRM number is shown as context only.
   This is the "bandit on the proxy + human override when CRM truth diverges" design, made concrete.

This cleanly respects the rule that money rungs may veto but never autonomously drive (§3).

---

## 3. Rung → decision-authority table (the table the rule logic is built from)

"Autonomous" = the engine writes an auto-approved `EngineAction` when the change stays under
`GuardrailConfig.require_approval_above_mad`; otherwise it downgrades to *propose*. Rule #3 is
absolute: any *activation* of a creative/campaign is always born **PAUSED** and its go-live is a
human approval — so "promote challenger" is never fully autonomous.

| Rung | Weekly events | Test power | Autonomous authority | Only-propose / inform |
|---|---:|---|---|---|
| Imp→click (CTR) | ~250 clicks | Real (large fx) | **Rebalance budget within band** (bandit weights) | — |
| Click→conversation (proxy) | ~165 | Weak | **Rebalance**; **kill loser** once burn-in met (§2.5) | budget change > guardrail → propose |
| Conv→qualified (CRM) | ~11 | None (MDE≫100%) | *none* | **Propose-only**: any reallocation justified by lead-quality → human approves |
| Qual→signature (CRM) | ~0.7 | None (Poisson) | *none* | **Inform-only**: monthly/quarterly signal; can trigger the §2.7 divergence override, never a direct action |

Autonomous action set (all still logged as `EngineAction`, all reversible):
`rebalance_budget` (daily, within band) • `pause_arm` (weekly, burn-in + P(best)<5%×3d) •
`promote_challenger` (create next backlog `CreativeAsset` as an ad, **PAUSED**, + propose activation).
Everything above the guardrail ceiling, and everything driven by a CRM-rung signal, is **propose →
human approve**.

---

## 4. Six-month flight plan — sequential tests, each sized by the MDE math (not folklore)

Folklore frameworks (3-2-2 = 12 combos, 3-3-3 = 27) [UNVERIFIED — agency blogs, all ecom-scale;
see scope-science.md §3] are **too wide for our volume**: 12 arms at 100 MAD/day = ~1,060
impressions/arm/week → CTR MDE ≈ **±90% relative** = useless. Right-sized rule: **one variable at a
time, 2–3 arms, ≥3–4 weeks/phase** (the window §1.3 shows is needed to detect a ≥20–30% CTR effect
AND clear the 40-conversion burn-in). ~26 weeks:

| Phase | Weeks | Variable (arms) | Bandit reward | Exit condition |
|---|---|---|---|---|
| 0 Baseline | 1–2 | 1 creative, no test | — | account funnel rates measured & stored |
| 1 **Hook** | 3–6 | 2–3 hooks, same visual/offer | CTR + conv/imp | one arm P(best)>80% or 4 wks up |
| 2 **Format** | 7–10 | winner-hook × {static, short video} | conv/imp | as above |
| 3 **Angle/offer** | 11–15 | winner × 2 value-props (économie vs autonomie vs pompage) | conv/imp; **watch CRM cost** | longer — angle effects surface at the lead rung, which is slow |
| 4 **Audience/geo** | 16–20 | winner × 2 city/segment targetings | conv/imp | as above |
| 5 **Consolidate + CRM reconcile** | 21–26 | champion only | — | retire fatigued creatives, feed cost-per-signature back, refill backlog |

Guardrails on the plan itself: never run a phase < ~3 weeks (below burn-in the "winner" is noise);
only advance a phase when the current bandit has an arm at **P(best) ≥ 80%** *or* the 4-week cap hits
(then keep the leader, don't force a call). Only ever test **big, categorically-different** variants —
the engine cannot see subtle ones. Each phase's loser feeds `CreativeAsset.status=archived` with a
`retired_reason`; the challenger backlog is the queue Phase N+1 draws from.

---

## 5. Off-the-shelf verdicts

### 5.1 GrowthBook `gbstats` — **REFERENCE, do not vendor**

Facts [VERIFIED — pypi.org/project/gbstats 16 Jul 2026; github.com/growthbook/growthbook
packages/stats/gbstats 16 Jul 2026]:
- IS a real standalone PyPI package: `pip install gbstats`, **MIT**, deps `numpy/scipy/pandas`,
  Python **≥3.8,<4.0** (wheel tested 3.8–3.11). Latest **v0.8.0, 20 Jun 2024**, classifier
  **"Pre-Alpha"**, author Jeremy Dorn.
- Package modules: `bayesian/`, `frequentist/`, `models/`, `power/`, `devtools/`, `gbstats.py`,
  `utils.py`, `gen_notebook.py`. **There is NO `bandits.py` in the published package** — the
  Thompson-sampling bandit lives in the GrowthBook *app/back-end* (TypeScript + the `gbstats`
  Bayesian primitives), not in the pip wheel. So `pip install gbstats` does **not** give you a
  ready bandit.
- It is built to consume **warehouse-materialized, user-level experiment DataFrames**, not our tiny
  daily aggregate `InsightSnapshot` rows.

Verdict: **READ it as a correctness reference** (the `bayesian/` module for how to compute
"probability variant B beats A" / probability-of-best, and `power/` for MDE), but **implement
in-house**. Our bandit is ~40 lines of `numpy.random.beta` + an argmax count (§2.3). Vendoring a
Pre-Alpha, Python-≤3.11-pinned, warehouse-oriented package for 40 lines is a net liability (extra
dep, version-pin risk — flag as DEP if ever added, per erp-arch.md's "avoid the heavy SDK" stance).
Optionally lift ONE helper (probability-of-best via Monte Carlo) but write it ourselves.

### 5.2 Evan Miller sequential testing / "Always Valid Inference" — **mostly MOOT for us**

Evan Miller's *Simple Sequential A/B Testing* [PRIMARY — evanmiller.org/sequential-ab-testing.html,
fetched 16 Jul 2026]: pick N up front; stop & call treatment the winner when successes
`T − C ≥ 2√N`; stop for "no winner" when `T + C ≥ N`. Controls Type-I at α; boundary `d* ≈
z_{α/2}·√N` (≈ `2√N` at α=0.05). Explicit limits (his words): performs **worse than a fixed test
under the null** (i.e. in the *majority* of tests where nothing wins), is inefficient at high
conversion rates, and **inferences are invalid if extended past N**.

"Always Valid Inference" (Johari et al., arXiv 1512.04922) / mSPRT is the rigorous anytime-valid
version GrowthBook/Statsig offer as a "sequential" toggle — it exists to make **frequentist peeking**
safe.

Practicality verdict for Taqinor: **we are not running a peeked frequentist test, so the problem AVI
solves does not arise.** A Bayesian Thompson bandit's posterior is valid at every n by construction —
there is no multiple-testing/peeking penalty to correct. So AVI is a nice-to-have **only if/when**
Taqinor grows budget enough to run a formal frequentist *confirmation* test at the CTR rung; today it
adds machinery for a problem the bandit design sidesteps. Keep Evan Miller's `T−C ≥ 2√N` rule in the
back pocket as a **cheap, legible 2-arm "is B clearly ahead?" gate** for a human reading the
`WeeklyBrief` (it's one line of code and easy to explain) — but the bandit, not a sequential test, is
the primary decision mechanism. Bottom line: at 3 sig/mo, **no** frequentist method — fixed or
sequential — is adequately powered on the money rungs; honesty about that beats importing an
anytime-valid framework that still can't see the effect.

---

## 6. Implementation skeleton (daily bandit loop)

```python
# apps/adsengine/bandit.py  — pure functions, deterministic, no external ML dep
import numpy as np

def posteriors(arms, alpha0=1.0, beta0=1.0):
    # arms: list of dicts {impressions, conversions} aggregated over the window
    return [(alpha0 + a["conversions"],
             beta0 + max(a["impressions"] - a["conversions"], 0)) for a in arms]

def prob_best(post, k=10_000, rng=None):
    rng = rng or np.random.default_rng(0)              # seed => reproducible/deterministic
    draws = np.column_stack([rng.beta(a, b, k) for a, b in post])
    winners = draws.argmax(axis=1)
    return np.bincount(winners, minlength=len(post)) / k   # w_i

def allocate(prob, daily_budget_mad, floor_pct=0.20, min_arm_mad=20.0):
    n = len(prob)
    floor = max(floor_pct * daily_budget_mad, min_arm_mad)
    floored = floor * n
    free = max(daily_budget_mad - floored, 0.0)
    return [floor + free * w for w in prob]                # MAD per arm/day

def killable(arm, prob_i, days_live, streak_below_5pct):
    return days_live >= 7 and arm["conversions"] >= 40 \
           and prob_i < 0.05 and streak_below_5pct >= 3
```

Wiring: `recompute_bandit` (Celery, ~06:20) reads `InsightSnapshot` (28-day window per `AdMirror`),
computes `allocate()`, writes an auto-approved `EngineAction(action_type="rebalance_budget")` if the
delta is under `GuardrailConfig.require_approval_above_mad` else a proposed one; `generate_weekly_brief`
runs `killable()` + the §2.7 CRM divergence check and files `pause_arm` / `promote_challenger` /
divergence-override actions into `WeeklyBrief.proposed_actions`. Determinism: seed the RNG so the same
`InsightSnapshot` data always yields the same allocation (auditability, and matches the "deterministic
engine, no AI" mandate).

## 7. Config defaults (all on `GuardrailConfig` unless noted)

| Param | Default | Source |
|---|---|---|
| arms active | 2–3 (max 4) | §1.3 MDE thinning |
| prior | Beta(1,1) | GrowthBook Bayesian default [VERIFIED] |
| reward | conversation-started / impression | §2.2 |
| window | rolling 28 days | GrowthBook "daily or longer" [VERIFIED] |
| reweight cadence | daily (~06:20) | Smartly midnight [PRIMARY] / GrowthBook [VERIFIED] |
| kill/promote cadence | weekly (Mon) | ties to `WeeklyBrief` |
| MC draws K | 10,000 | §2.3 |
| `bandit_arm_floor_pct` | 0.20 | §2.4 |
| `min_arm_daily_budget_mad` | 20 | Meta ~$1/day delivery floor [UNVERIFIED-folklore, ~$1/adset] |
| min impressions before reweight | 100/arm | GrowthBook 100-user gate [VERIFIED] |
| burn-in before kill | 7 days AND 40 conv/arm | GrowthBook ≥40 conv [VERIFIED] |
| kill trigger | P(best)<5% for 3 consecutive days | §2.5 |
| phase advance | P(best)≥80% or 4-week cap | §4 |
| CRM divergence gate | rank disagree >1 AND ≥10 qualified | §2.7 |

---

## Appendix — reproduce the MDE table

```python
import math
z = 1.9600 + 0.8416
mde = lambda p, n: (d := z*math.sqrt(2*p*(1-p)/n), d/p*100)
# 2-arm 50/50; n/arm over 7/14/28d at 100 MAD/day funnel:
# CTR p=.02  -> 6300/12600/25200  -> 34.9/24.7/17.5 %
# clk->conv .65 -> 126/252/504    -> 25.9/18.3/13.0 %
# conv->qual .07 -> 84/168/336    -> 157.6/111.4/78.8 %
# qual->sig  .06 -> 5.7/11.5/23   -> 656.9/462.4/327.0 %
# Poisson 95% CI for 3 monthly signatures = [0.62, 8.77]
```

## Sources

Primary / near-primary:
- [gbstats — PyPI](https://pypi.org/project/gbstats/) (v0.8.0, 20 Jun 2024, MIT) — fetched 16 Jul 2026
- [growthbook/packages/stats/gbstats — GitHub](https://github.com/growthbook/growthbook/tree/main/packages/stats/gbstats) — fetched 16 Jul 2026
- [GrowthBook Bandits — overview](https://docs.growthbook.io/bandits/overview) & [config](https://docs.growthbook.io/bandits/config) — fetched 16 Jul 2026
- [Evan Miller — Simple Sequential A/B Testing](https://www.evanmiller.org/sequential-ab-testing.html) — fetched 16 Jul 2026
- [Evan Miller — How Not To Run an A/B Test](https://www.evanmiller.org/how-not-to-run-an-ab-test.html) (N=16σ²/δ² rule)
- [arXiv 1512.04922 — Always Valid Inference (Johari et al.)](https://arxiv.org/abs/1512.04922)
- [arXiv 1707.02038 — A Tutorial on Thompson Sampling (Russo et al.)](https://arxiv.org/abs/1707.02038) — beta-Bernoulli TS
- [Smartly Predictive Budget Allocation](https://www.smartly.io/product-features/predictive-budget-allocation) (Bayesian MAB, midnight cadence)

Secondary (UNVERIFIED, directional — used only to ground funnel rates, all flagged in-text):
- [getkanal.com — Click-to-WhatsApp Ads Benchmarks 2026](https://getkanal.com/blog/click-to-whatsapp-ads-benchmarks-2026) — MENA CPM/CTR/opt-in/cost-per-conversation
- [WordStream — Facebook Ads Benchmarks 2025](https://www.wordstream.com/blog/facebook-ads-benchmarks-2025)
- Agency creative-framework blogs (3-2-2 / 3-3-3) — enumerated in scope-science.md §3
```
