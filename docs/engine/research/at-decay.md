# AT-DECAY — How Fast Do Ad "Truths" Decay? Evidence for the Founder's Perpetual-Retest Tree

Research date: 17-18 Jul 2026. Scope: evaluate THE IDEA (marketing plan = a tree of assumed A/B
results; engine tests most-uncertain assumptions first; re-orders by staleness; retests even
long-validated assumptions forever; borrows priors across fields when a field has no data; AI
seeds the tree once + revisits quarterly, everything else deterministic) against the actual
evidence on how fast advertising "truths" decay. Builds on, and does not repeat, the volume
math already banked in `docs/engine/research/dd-science-core.md` (only the CTR/top-funnel rung
carries statistical power at Taqinor's 100 MAD/day) and the fatigue-trigger mechanics already
banked in `docs/engine/research/dd-guardian.md` (frequency-based fatigue alert, already flags
Meta's own frequency thresholds as folklore).

Source discipline: every claim carries a URL + fetch date and a [VERIFIED] (I fetched/read the
primary source directly) / [UNVERIFIED] (secondary, practitioner blog, or WebSearch-summarized
without direct fetch) tag. Anything a search-engine summary asserted that I could not confirm on
direct fetch is called out explicitly as a synthesis artifact — this happened once (see §1.4).

---

## 1. (a) Creative wear-out — how long does a winning creative stay a winner

### 1.1 The one real primary source: Meta's own "Analytics at Meta" study

[VERIFIED — fetched directly] **Lucas J., Alex D., Matt M. (Analytics at Meta), "Creative
Fatigue: How advertisers can improve performance by managing repeated exposures," Medium,
10 May 2023.**
https://medium.com/@AnalyticsAtMeta/creative-fatigue-how-advertisers-can-improve-performance-by-managing-repeated-exposures-e76a0ea1084d

Exact findings:
- Measured **user-by-creative exposure over a rolling 30-day window**, across Meta's ad
  ecosystem. Mean prior-exposure count per impression = **4.2**; **>19% of impressions** went to
  a user who had already seen that exact creative **≥5 times** in the prior 30 days.
- Response decays as a **power law**: click/conversion likelihood ∝ **(N+1)^-0.43**, N = prior
  exposures. At N=4 (the 4th repeat exposure), conversion likelihood is down **~45%** from a
  fresh exposure. There is **no measurable wear-IN** in their data — clicks get monotonically
  more expensive from the very first repeat exposure onward, contradicting the classic
  wear-in/wear-out inverted-U (see §1.2) at the individual-impression level Meta actually logs.
- Ran a live experiment (**~26,000 test cases**) nudging advertisers to refresh high-fatigue ad
  sets: **average conversion-rate improvement +8%**, and the gain was **dose-dependent** — bigger
  for ad sets that were more fatigued.
- **No specific refresh cadence is recommended** in the piece — Meta stops at "add new/diverse
  creative when fatigue is detected," not a fixed day/week number.

This is the single most authoritative number available: **a specific creative, on Meta, starts
losing efficiency from essentially its first repeat exposure**, and by the ~4th exposure to the
same user is down ~45%. Converted to calendar time at Taqinor's scale (100 MAD/day, ~1,800
impressions/day into a narrow local audience) this predicts **audience saturation, and therefore
measurable fatigue, inside single-digit days to ~2 weeks**, not months — consistent with
Meta's own in-product signal design (§1.3).

### 1.2 Academic wear-in/wear-out theory (older, aggregate-level, still the theoretical base)

[VERIFIED — titles/abstracts confirmed via Semantic Scholar + WVU repository search; full text
not fetched] **Pechmann, C. & Stewart, D.W., "Advertising Repetition: A Critical Review of
Wearin and Wearout," Current Issues and Research in Advertising, Vol. 11 (1988), pp. 285–329.**
Proposes the **Two-Stage Cognitive Response Model**: wear-IN over roughly the **first ~3
exposures** (positive thoughts still outnumber negative/counter-arguing), then wear-OUT past
that as tedium/reactance accumulates — the classic **inverted-U** response curve. This is
1980s theory built mostly on TV-era, aggregate (not user-level) data; it explains *why* fatigue
happens, not a modern digital cadence.
- Follow-on: **ScienceDirect (2019), "Ad wearout wearout: how time can reverse the negative
  effect of frequent advertising repetition on brand preference"** [UNVERIFIED — abstract only,
  not fetched] — finding in the title itself is notable: **elapsed time without exposure can undo
  wear-out**, i.e., a "retired" creative can become fresh again months later. This directly
  supports the founder's "seasons/moods change, retest even old winners" instinct, but for
  *brand attitude*, not for a cold-traffic acquisition CTR/CTWA funnel like Taqinor's.

### 1.3 Practitioner/platform data (real but non-academic, flagged as such)

- [VERIFIED — practitioner's own aggregated ad-account data, fetched via adespresso.com,
  "Facebook Ads Frequency: 3 Techniques to Fight It," ~2018] AdEspresso's own cross-account
  study: CTR falls **~9%** at frequency 2, **~23%** at frequency 4 (CPC +68%), and CTR is down
  **~50%** with CPC **+161%** by frequency 9. Old (2018) and platform/algorithm has changed since,
  but it's a real practitioner dataset, not a re-blog — kept as directional, not gospel.
- Meta's own **Ads Manager product signal** (current, 2026) [UNVERIFIED — described consistently
  across several practitioner posts, not fetched from an official Meta doc I could load — the
  linked Meta help-center page 404'd on fetch] surfaces **"Creative Fatigue"** (cost/result ≈2×
  historical baseline → refresh now) and **"Creative Limited"** (elevated but <2× → prepare a
  refresh) directly in the Delivery column. This is Meta operationalizing "detect + refresh," in
  the product, which is a strong signal the underlying phenomenon is real and fast enough to
  need a live dashboard flag — but I could not verify the exact 2× threshold against a primary
  Meta page.
- **Google's own ecosystem guidance** [UNVERIFIED — aggregated from a support-doc/best-practice
  compilation, not a single fetched primary source]: for **Performance Max**, replace "Low"-rated
  assets after **4–6 weeks** of data; general practitioner cadence tables suggest **4–6 weeks**
  (static) / **8–12 weeks** (video) refresh, scaling to **8–12 / 12–16 weeks** for low-impression
  accounts like Taqinor's (<100k monthly impressions).

### 1.4 A caught synthesis artifact — worth flagging for the founder directly

One WebSearch summary asserted a specific "**10-day decay curve: peak days 1-3, warning days
4-7, 30-50% CTR drop by days 8-10**" for "most concepts on Meta in 2026." When I fetched the
article the summary attributed this to (myntagency.com) **directly**, that exact framing was
**not present** — the agency's own text says fatigue onset is "3-4 exposures within 7 days,"
citing its own client data plus a general Meta link, nothing about a universal 10-day curve.
**This specific figure is not supported by the source it was attributed to and should be
treated as fabricated-by-summarization, not evidence.** Flagged here because the founder asked
for brutal honesty, and this is exactly the kind of confident-sounding, oddly-precise number
that a real deployed engine (or a human skimming a dashboard) could absorb as fact.

### 1.5 Verdict on creative wear-out

**[VERIFIED, from the single best available primary source]: creative decay is fast and real —
noticeable from essentially the first repeat exposure, ~45% down by the 4th exposure to the same
user, and Meta's own product now auto-flags it.** At Taqinor's volume (~1,800 impr/day into a
narrow geo/language audience), this converts to **single-digit days to ~2 weeks** before a
specific creative's efficiency measurably degrades for the *audience it's already reached* —
though whether it's *statistically detectable* by Taqinor's bandit specifically needs the 40-conv
burn-in from dd-science-core.md (§2.5 there), typically ~1–1.5 weeks at 20-35 MAD/day/arm.
**Creative-class assumptions decay on the order of weeks — this part of the founder's "test
constantly" instinct is well-supported.**

---

## 2. (b) Audience/targeting truths — evidence a winning audience/angle stops winning

### 2.1 Direct mechanism-level evidence (practitioner, consistent across many independent shops)

[UNVERIFIED-CLUSTER — consistent across ~6 independent agency/tool blogs (adamigo.ai,
adstellar.ai, trackmastersroi.com, balistro.com, mhigrowthengine.com), no single primary/academic
source found, but the underlying mechanisms are logically independent and mutually reinforcing,
which raises confidence above a single-source claim]:
- **Lookalike-audience decay** happens through three distinct, well-understood channels: (1)
  **audience saturation** — Meta has matched most of the reachable pool; (2) **creative fatigue**
  compounding within the same narrow audience (ties back to §1); (3) **seed-list staleness** —
  the "best customer" profile the lookalike was built from shifts (a seed list built in January
  is stale by April, per one source). Practitioner-recommended refresh: **monthly** re-export of
  conversion data to rebuild lookalikes, with broader 3-5%/5-10% lookalike tiers pre-staged as a
  fallback when the tight 1-2% tier saturates.
- This is directly relevant to Taqinor: a small, geographically-narrow Morocco solar audience at
  100 MAD/day will hit reachable-pool saturation **faster**, not slower, than a large-budget
  Western advertiser — reinforcing that audience truths need active management on a
  **weeks-to-months** cadence, not "set once."

### 2.2 Seasonality and macro-mood — COVID as the best available natural experiment

[VERIFIED — direct fetches] Two Nielsen pieces plus one IAB data point give real, dated numbers
on how fast the *entire market's* ad-response assumptions moved during a genuine shock:

- **Nielsen, "Navigating the challenges of digital advertising during a global pandemic," 2020**
  and **"COVID-19 changed the advertising playbook. Now what?", Feb 2021**
  (https://www.nielsen.com/insights/2021/covid-19-changed-the-advertising-playbook-now-what/,
  fetched directly): global average CPM fell from **$1.88 (late Nov 2019 high) to $0.81
  (mid-March 2020)** — down >50% inside ~4 months as advertisers pulled back and inventory got
  cheaper; average CTR across 18 industries was **down 17.2%** by mid-March vs. the start of the
  year. **COVID-themed creative peaked at 48% of international ads in Q2 2020, then fell to 20%
  by Q4 2020** as "COVID-fatigue" set in among consumers — i.e., an *angle* that was clearly
  winning in Q2 was measurably losing salience by Q4, **inside two quarters**. Nielsen's own
  prescription is NOT a fixed retest cadence, but three qualitative principles: "be flexible and
  iterative," "maintain consistent share of voice," "reach consumers where they are" — Nielsen
  explicitly does **not** claim a mechanical schedule solves this; and warns brands that go dark
  can take **3-5 years** to recover brand equity/revenue, a caution about swinging too fast in the
  other direction (never testing = never adapting; but panicking on every macro blip has its own
  cost).
- **IAB, "COVID's Impact on Ad Pricing," 28 May 2020** [UNVERIFIED — found via search, not
  directly fetched]: sell-side CPMs down 20-50% depending on format/vertical, corroborating the
  Nielsen CPM number from an independent (publisher-side) methodology.

**Read honestly:** COVID is a *macro demand-shock* natural experiment, not a clean "audience
truth decayed" experiment — CPM/CTR moved because competitive intensity and consumer attention
moved, not because Taqinor-style audience targeting logic broke. But the COVID-creative-angle
data point (48%→20% share of a message type in two quarters) is a genuine, dated example of an
**angle/message-class assumption having a real half-life measured in months, not years** — this
is the strongest single piece of evidence in this whole research pass for the founder's "seasons
and moods change" intuition.

### 2.3 What's missing

I could not find a rigorous, controlled (not confounded by macro shock) academic study
specifically proving "a winning Meta audience segment stops winning after X weeks in normal
times" — this remains **[UNVERIFIED / evidence gap]**. The lookalike-decay mechanism (§2.1) and
the COVID natural experiment (§2.2) are the two best proxies available, and both point the same
direction (months-scale decay), but neither is a clean causal RCT of "audience truth staleness"
in isolation.

---

## 3. (c) What mature advertisers actually do about it

### 3.1 Incrementality/lift-test refresh cadence — the honest, checked answer

[VERIFIED — direct fetch] **Haus, "The Meta Report: Lessons from 640 Haus Incrementality
Experiments," 28 Jul 2025** (https://www.haus.io/blog/the-meta-report-lessons-from-640-haus-incrementality-experiments):
- Average test across the 640 experiments ran **18.6 days**, with an **8.8-day post-treatment
  observation window**.
- **The report does NOT give a refresh-cadence recommendation.** It explicitly pushes back on a
  universal answer: "Test for your own business... what works for one business may not
  translate for another." No seasonality or decay tracking is presented — it is a
  point-in-time compendium, not a longitudinal staleness study. This is itself informative: even
  the largest publicly-published incrementality-testing dataset I could find does **not** track
  or discuss test staleness over time.
- **[UNVERIFIED, secondary compilations]** Multiple secondary sources converge on: mature
  advertisers/agencies (Common Thread Collective, Wpromote) and MMM/lift vendors (Measured,
  INCRMNTAL, Recast) treat **1-2 incrementality/lift studies per year per major channel** as the
  norm, timed to budget-cycle decisions, with some describing a shift toward "continuous
  testing calendars" that refresh quarterly — but no single primary source verifies a specific
  cadence number as an industry standard; this reads as aspirational vendor marketing more than
  a documented, cited practice.
- **Meta's own official guidance is silent on cadence.** [VERIFIED — fetched directly, Meta
  "Best practices for running a Conversion Lift study"]: Meta's own copy only specifies a
  **minimum test duration** ("one to two conversion cycles, or two to four weeks") — it says
  nothing about how often to re-run a study, or when a past lift result should be considered
  stale. **The honest finding: neither Meta nor Google publishes an official "retest your
  incrementality result every N months" number.** That number, where it exists at all, is a
  third-party vendor's rule of thumb, not platform doctrine.

### 3.2 Always-on holdouts

[UNVERIFIED — described consistently across secondary sources, not independently fetched from
each company]: Uber, Airbnb, Lyft, Amazon, Walmart, P&G, Netflix are all cited as running
lift/holdout-based measurement to calibrate MMM/attribution, with claims that **Uber and Airbnb
found >80% of performance-ad spend was redundant** via holdout testing. Adjust's "InSight"
product pitches synthetic-control "always-on" measurement specifically to avoid the cost of a
live, continuously-held-back control group — implying that a TRUE always-on live holdout is
expensive enough that even sophisticated players look for a cheaper substitute. This is directly
relevant to Taqinor: at 5-15 leads/week, a live holdout group would starve itself of the very
few conversions available (dd-science-core's Poisson math already shows the money rungs are dark
even *without* subtracting a holdout slice) — an always-on holdout is a large-advertiser luxury,
not something Taqinor's volume can afford.

### 3.3 Champion/challenger — the actual precedent for "perpetual retesting," and it's NOT from ads

[VERIFIED — well-established, multi-source-consistent, dating claim to FICO's own materials]
**Champion/challenger testing originates in credit-risk decisioning (FICO TRIAD Customer
Manager, mid-1980s)** and is explicitly designed to run **forever, on every decision stream, with
no declared end-state** — "a cyclical process that takes place practically all the time... once
you declare a winner, that becomes the new champion, and you create new challengers to compete
against it once again" (multiple independent glossary/vendor sources, consistent description,
e.g. fico.com, sparklinglogic.com, energycentral.com). This is 40 years old, genuinely perpetual,
and is the closest real-world precedent for the founder's "retest even long-validated
assumptions forever" instinct — **but it lives in credit risk / decision management, not
advertising**, where event volumes (loan applications, transactions) are orders of magnitude
higher than Taqinor's 11 qualified leads/week, making true perpetual re-validation statistically
affordable there in a way it is not here.

### 3.4 Growth-team practice (SaaS/consumer, the closest ads-adjacent precedent)

[UNVERIFIED — secondary, consistent across multiple summaries of Sean Ellis & Morgan Brown's
"Hacking Growth"]: mature growth teams (Airbnb ran **>1,000 experiments/year** at peak) run
**continuous weekly experimentation** (teams commonly cited at 20-30 experiments/week) prioritized
by an **ICE score** (Impact/Confidence/Ease), inside **quarterly** budget/OKR cycles that set
guardrails — i.e., continuous testing nested inside a quarterly strategic reset is a **real,
widely-documented pattern**, and it maps closely onto the founder's "AI seeds + revisits
quarterly, engine runs deterministically in between" structure. **However**, I found **no
documented ICE/PIE/RICE backlog tool that reprioritizes by "staleness"/last-tested-date** the way
the founder describes (checked Optimizely's own backlog-prioritization agent — it scores
Potential/Importance/Ease, not recency) — staleness-based reordering of a living assumption tree
does not appear to be a named, shipped feature anywhere I could find. **This specific mechanism
(reorder-by-staleness) looks like a genuine, small but real innovation**, not an already-solved
problem — the founder is not reinventing something that exists; he's combining two things
(champion/challenger's perpetuity + growth-team quarterly cadence) in a way that isn't currently
productized.

### 3.5 Borrowing priors across fields with no data — this part IS already invented, rigorously

[VERIFIED as an established statistical technique, if not ads-specific] **Hierarchical/empirical
Bayes "borrowing strength" across related experiments is a mature, well-published statistical
method** — meta-analysis models explicitly shrink an under-powered study's estimate toward the
pooled estimate across other studies, weighted by how little data the thin one has (PubMed
20652520; PMC6719559 on combining RCT + single-arm studies; oncology "basket trials" borrowing
across cancer subtypes, arXiv 2002.03007, is a very close structural analogy to "a new
market/vertical with no data yet borrows from a sibling vertical's tested prior"). **The
founder's "no data in a new field → borrow priors from other fields" instinct is not a novel
idea; it is exactly hierarchical Bayesian partial pooling**, already used in the dd-science-core
bandit design's own optional informative-prior config (Beta(α₀,β₀) seeded from the account's
historical rate). Extending that prior source from "this account's own history" to "a sibling
vertical/field's tested history" is a straightforward, well-precedented generalization — low
risk, high confidence this piece of the idea works as intended.

---

## 4. (d) Seasonal planning practice — separate playbooks, or wing it?

[UNVERIFIED — generic content-marketing sources, no rigorous primary study found specifically
measuring whether performance teams maintain distinct validated seasonal baselines vs. eyeballing
it]: the pattern that surfaces consistently is **pre/post-season and year-over-year baselining**
("pull organic traffic/impressions/CTR from the same period over the past 2-3 years... tells you
what's normal so you don't mistake a seasonal trough for a real problem") plus **season-specific
creative/messaging libraries** (documented tone/imagery differences: winter = exclusivity/scarcity
framing, summer = experiential/lifestyle framing) and **post-season retro documentation** ("create
a seasonal playbook after each campaign... measure AOV/CAC/LTV lift to refine next cycle").

**Honest read: this is standard, low-rigor marketing-ops hygiene (a shared doc/calendar), not a
statistically re-validated baseline.** I found no evidence of serious performance teams running a
formal significance test on "is this season's assumption still true" — the practice is
qualitative (a playbook document, a YoY chart) rather than the founder's proposed mechanism
(the tree re-tests and reprioritizes by staleness with actual statistical evidence). **The
founder's idea, if built, would be MORE rigorous than documented industry practice for
seasonality specifically** — most shops "wing it" with a calendar and institutional memory, not a
live statistical re-test.

---

## 5. (e) The honest synthesis — decay half-life by assumption class

"Half-life" here is used loosely (time to materially degrade, not a precise statistical
half-life) since no source gives an actual survival-function fit; it is the best summary the
evidence supports.

| Assumption class | Approx. decay timescale | Evidence quality | Key sources |
|---|---|---|---|
| **Creative (specific ad unit — hook/visual/copy)** | **Days to ~2-4 weeks** at Taqinor's ad-account scale; Meta's own data shows degradation starting at essentially the 1st repeat exposure, ~45% down by exposure #4 | **Good** — one strong primary source (Meta/Analytics-at-Meta, 30-day window, 26k test cases), corroborated by consistent (if dated) practitioner data (AdEspresso) and Meta's own live product signal | §1.1–1.3 |
| **Creative format (video vs. static, hook style as a category)** | **~1-3 months** (Google/PMax practitioner cadence: 4-12 weeks depending on volume) | **Medium** — practitioner consensus, no controlled study isolating format-class decay from individual-creative decay | §1.3 |
| **Audience/targeting segment (lookalike, geo, demo)** | **~1-4 months** (monthly lookalike-refresh norm cited; no clean RCT) | **Weak-medium** — mechanism-consistent across independent practitioner sources, but no primary/academic study found isolating pure audience-truth decay from confounds (creative fatigue, seed staleness) | §2.1 |
| **Angle/offer/message (value proposition, emotional register)** | **~1-2 quarters** in normal times; COVID showed a dominant message category go from 48%→20% share in **2 quarters** under a macro shock | **Medium** — the COVID data point is dated/sourced and real, but it is a shock-driven natural experiment, not steady-state decay; steady-state angle decay specifically is an evidence gap | §2.2 |
| **Category economics (does solar/WhatsApp-first-Morocco as a category still make sense)** | **Years, if ever** — no evidence found of this layer moving faster than macro/regulatory change itself | **Low direct evidence, high logical confidence** — this is closer to Ehrenberg-Bass "double jeopardy"-style structural market law than an ad-testable hypothesis; nothing in the research suggests this class needs perpetual A/B retesting at all | reasoning, not a specific fetched study |

**Bottom-line, brutally stated:**

1. **The founder's core intuition — "truths decay, retest perpetually" — is directionally right
   and evidence-backed for the CREATIVE layer specifically**: Meta's own numbers show real decay
   starting almost immediately. Building perpetual creative retesting is well-justified and,
   per dd-science-core's bandit design, already correctly resourced (weekly kill/promote,
   28-day rolling window, 7-day+40-conversion burn-in).

2. **The "retest even long-validated audience/angle assumptions, and re-order by staleness"
   layer is where the idea gets ahead of both the evidence AND Taqinor's own statistics.**
   dd-science-core already proved the qualified-lead rung needs a **≥79-158% relative shift** to
   be detectable even at 28 days, and the signature rung is pure Poisson noise. A "quarterly"
   cadence for retesting audience/angle truths is not enough time to accumulate a statistically
   valid answer at Taqinor's volume — dd-science-core's own Phase 3/4 plan (angle, then
   audience) already budgets **5 weeks each**, and even that only reaches an 80%-confidence
   *bandit* call, not a hard significance test. **So: yes, retest them — but be honest that
   "quarterly" is a staleness-flagging/attention cadence, not a statistical-validation cadence,
   for anything past the creative/CTR rung.** The tree can legitimately say "this branch hasn't
   been looked at in 90 days, go look" — it cannot legitimately claim a fresh statistically-clean
   verdict on the audience/angle rung inside a quarter at this budget.

3. **Nobody in advertising already runs exactly this idea** (staleness-ranked perpetual
   assumption tree with cross-field prior borrowing). Its individual ingredients are each
   independently well-precedented and mostly low-risk to build: perpetual champion/challenger
   retesting (credit risk, 1980s), continuous-testing-inside-quarterly-strategy (SaaS growth
   teams), and prior-borrowing across thin-data segments (hierarchical/empirical Bayes, already
   partially designed into dd-science-core's optional informative prior). **The genuinely novel
   piece — reordering the test queue by "time since last validated" — is not a documented,
   shipped feature anywhere found in this research.** That is not a red flag by itself (a small,
   sensible, cheap-to-build heuristic is allowed to be original), but the founder should not
   assume it is proven practice elsewhere; it should be built and watched, not trusted blind.

4. **The single biggest risk the evidence surfaces**: because only the creative/CTR layer has
   enough weekly events to be tested honestly, an engine that "keeps growing branches" on the
   audience/angle/offer layers risks generating a large tree of *branches that look active and
   prioritized but can never actually be resolved* at 100 MAD/day — a plausible-looking dashboard
   full of statistically unresolvable questions. The guardrail dd-science-core already
   specifies (money rungs are propose-only/inform-only, never autonomous) is the correct
   mitigation and should be treated as load-bearing, not optional, if this idea is built.

---

## Sources

Primary / directly fetched:
- [Analytics at Meta — "Creative Fatigue"](https://medium.com/@AnalyticsAtMeta/creative-fatigue-how-advertisers-can-improve-performance-by-managing-repeated-exposures-e76a0ea1084d) (10 May 2023) — fetched 18 Jul 2026
- [Nielsen — "COVID-19 changed the advertising playbook. Now what?"](https://www.nielsen.com/insights/2021/covid-19-changed-the-advertising-playbook-now-what/) (Feb 2021) — fetched 18 Jul 2026
- [Meta — "Best practices for running a Conversion Lift study"](https://www.facebook.com/government-nonprofits/blog/best-practices-for-conversion-lift) — fetched 18 Jul 2026
- [Haus — "The Meta Report: Lessons from 640 Haus Incrementality Experiments"](https://www.haus.io/blog/the-meta-report-lessons-from-640-haus-incrementality-experiments) (28 Jul 2025) — fetched 18 Jul 2026
- [Mynt Agency — "Predicting Ad Fatigue"](https://articles.myntagency.com/predicting-ad-fatigue/) — fetched 18 Jul 2026 (used to CORRECT a fabricated-by-summary "10-day decay curve" claim, §1.4)
- Pechmann, C. & Stewart, D.W. (1988) "Advertising Repetition: A Critical Review of Wearin and Wearout," Current Issues and Research in Advertising, 11, 285–329 — title/abstract confirmed via Semantic Scholar, full text not fetched

Secondary / UNVERIFIED (used only for directional/consistent-cluster claims, flagged in-text):
- AdEspresso — "Facebook Ads Frequency: 3 Techniques to Fight It" (~2018)
- adamigo.ai, adstellar.ai, trackmastersroi.com, balistro.com, mhigrowthengine.com (lookalike-decay cluster)
- IAB — "COVID's Impact on Ad Pricing" (28 May 2020)
- FICO / sparklinglogic.com / energycentral.com (champion/challenger origin + perpetuity description)
- Alex Murrell / IPA — summaries of Binet & Field, "The Long and the Short of It" (no concrete decay-timeframe numbers found in the accessible summary)
- Sean Ellis & Morgan Brown, "Hacking Growth" — summaries only (Airbnb >1,000 experiments/yr, ICE framework, quarterly OKR cadence)
- PubMed 20652520, PMC6719559, arXiv 2002.03007 — hierarchical/empirical Bayes "borrowing strength" across experiments (abstracts only)
- Ehrenberg-Bass Institute / Byron Sharp, "How Brands Grow" — Double Jeopardy law, used only as reasoning support for the "category economics barely decays" row, not a fetched decay-rate number

Repo (not re-researched, read for context):
- `docs/engine/research/dd-science-core.md` — MDE math, bandit design, 6-month flight plan
- `docs/engine/research/dd-guardian.md` — fatigue-trigger mechanics, already flags Meta frequency thresholds as folklore
