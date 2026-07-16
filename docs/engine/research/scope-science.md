# Scope map — the SCIENCE of running ads autonomously at SMB budgets (no AI, deterministic engine)

Research date: 16 Jul 2026. Scope per brief: map territories 1-5, name authoritative sources, state
open questions per territory — do NOT fully answer yet. End with the Round-1 mission list.
Builds on prior research already on disk (Meta CLI/MCP tooling, channel maturity, compliance,
competitor positioning, UX for ad tools/AI-approval, video/UGC creative-gen, ERP arch, plan format) —
not repeated here except where it directly bears on the science layer.

---

## 1. Experimentation methodology for paid ads

**Sources found:**
- Meta Split Testing API docs (`developers.facebook.com/docs/marketing-api/guides/split-testing/`)
  [PRIMARY, fetched directly]: automates mutually-exclusive audience division (no cross-cell
  overlap); budget split via `treatment_percentage` (campaign-level tests) or `daily_budget`/
  `lifetime_budget_percentage` (creative tests); winner picked on the efficiency metric tied to
  campaign objective (e.g. lowest CPA). **No explicit minimum budget/duration is published by
  Meta itself** — the page only says larger reach/longer schedules/higher budgets "tend to
  deliver more statistically significant results." Confidence-threshold mechanics and any
  CBO/Advantage+/learning-phase interaction are **not documented on this page at all** — a real
  gap, not just an omission in this pass.
- Industry secondary sources (get-ryze.ai, benly.ai, adenslab.com, jonloomer.com — UNVERIFIED
  tier, content-farm-adjacent per the existing source-reliability pattern from prior Meta
  research) converge on: 2-week minimum test duration at launch; 7-14 days for creative tests;
  **21-28 days for budget/bid tests** to let the algorithm stabilize; $100/day per variation
  as a rule of thumb ($200/day total for 2 variants) — all **directional, not Meta-confirmed**.
  One source cites a **65% confidence threshold** for Meta declaring a winner in its native
  Experiments tool ("Test and Learn" / A/B Test in Ads Manager) — plausible but not verified
  against a primary Meta doc in this pass.
- Learning phase / CBO mechanics [UNVERIFIED-CLUSTER, consistent across sources]: exits after
  ~50 conversions per ad set within a 7-day rolling window; formula floated: minimum viable daily
  budget ≈ (target CPA × 50) / 7. CBO/Advantage+ Advantage+ shopping/App campaigns dynamically
  reallocate budget across ad sets toward whichever is converting most efficiently — **this is
  exactly the mechanism a DIY bandit/optimizer would duplicate or fight** if it also tries to
  move budget between ad sets inside one CBO campaign. 3-5 creatives per ad set recommended so
  the learning phase doesn't fragment signal thinly.

**Open questions (not yet resolved):**
- Does Meta's native Split Testing API even support the DAILY 100-500 MAD budget tier at all, or
  does its own advice ($100+/day/variation) already exceed it — meaning a DIY/manual split
  structure (two separate ad sets, no native Test tool) may be the only option at this budget?
- What EXACTLY resets the learning phase (edit thresholds — is it any edit, or only
  audience/creative/optimization-event changes; does a budget nudge alone reset it)? This is the
  single most load-bearing fact for how often a deterministic engine may safely act.
- Does CBO's internal reallocation conflict with an external bandit trying to also move budget
  between ad sets — i.e., should the engine bandit operate ACROSS ad accounts/objectives (things
  CBO can't already see) rather than WITHIN one CBO campaign where Meta already owns the decision?
- Is there a still-live native "A/B Test" tool distinct from the Split Testing API/marketing-api
  guide (Ads Manager UI-only, "Test and Learn") with its own separate minimums/confidence math
  that a Python engine can't reach via API at all — meaning the engine must build DIY testing
  regardless of what the native tool offers?

---

## 2. Low-volume statistics (10-100 conversions/month)

**Sources found:**
- Evan Miller, "Simple Sequential A/B Testing" (evanmiller.org) [independent, well-known
  statistics writer, treat as credible secondary/near-primary] — sequential testing avoids the
  "peeking problem" of fixed-horizon tests, valid to stop early on large effects.
- arXiv "Always Valid Inference" (Johari et al., 1512.04922) — the academic basis for
  sequential/anytime-valid testing used by GrowthBook/Statsig/Optimizely-style engines.
- GrowthBook (OSS, MIT core, `github.com/growthbook/growthbook`) [PRIMARY-adjacent, own docs]:
  ships CUPED variance reduction, sequential testing, Bayesian AND frequentist engines,
  bandits, SRM (sample-ratio-mismatch) checks, 24 SDKs incl. Python — this is a **direct
  reference implementation** worth reading the stats-engine source of, even if not adopted
  wholesale.
- Statsig (proprietary but docs-public) — same category, Bayesian+frequentist+CUPED+sequential;
  useful as a second reference for how a production system frames "probability variant B beats
  A" outputs vs raw p-values.
- Springer "Multi-armed bandits for performance marketing" (2023) + arXiv 2502.02920
  (combinatorial bandits for multichannel budget) — MABs "exploiting domain knowledge are
  effective under few clicks/small conversion rates/short horizons/low budgets" — directly
  relevant to the 10-100 conversions/month regime named in the brief.
- Smartly.io's Predictive Budget Allocation [PRIMARY, vendor's own docs] explicitly named as
  **"based on the Bayesian multi-armed bandit method"** — a named, production-proven precedent
  for exactly this problem (reallocating a budget between ad sets to maximize expected future
  conversions and minimize CPA) — the single most directly-relevant "how a real production system
  does this" data point found in this whole pass.
- Convert.com's frequentist-vs-Bayesian explainer — practical framing: Bayesian posteriors give
  "probability variant B is best" (intuitive at low N); sequential methods need a pre-set
  "horizon" (max sample size) and trade power on small effects for early-stopping power on large
  ones.

**Open questions:**
- At Taqinor's own actual scale (a handful of leads/week), is even a well-tuned MAB fast enough
  to converge before a creative naturally goes stale (weeks), or does the sample size make ANY
  statistical method underpowered — meaning the real design might be "loose heuristics + human
  judgment gate," not a rigorous test at all? Needs the MDE math worked through concretely at
  Taqinor's real numbers, not just cited abstractly.
- Which rung of the CTR → CTWA conversation → qualified lead → signature ladder has enough
  monthly volume to run ANY statistical test, and which rungs must instead lean on a cruder
  n-of-a-few decision rule (e.g., "3 conversations vs 0 conversations is not noise, act on it")?
  This ladder-to-decision mapping does not exist yet in any source found — likely a
  build-it-ourselves synthesis, not something to keep searching for verbatim.
- Epsilon-greedy vs Thompson sampling: is the simpler epsilon-greedy "good enough" at these
  volumes given engineering-simplicity matters for a from-scratch deterministic Python engine, or
  does Thompson's built-in exploration/exploitation balance materially outperform at n<100?
- When does a bandit beat a fixed-horizon test at THIS budget — is there a concrete threshold
  (e.g. "below N conversions/week, always bandit; above, fixed test is fine") cited anywhere
  authoritative, or is this a judgment call the mission must derive itself?

---

## 3. Creative testing frameworks agencies use

**Sources found (framework names + who claims them):**
- **3-2-2 method** (multiple agency blogs: 7milemedia, pipiads, adsmanagement.co, pigeondigital) —
  3 creatives × 2 primary-text variants × 2 headlines = 12 ad combinations, typically run via
  Meta's own Dynamic Creative (DCT) at the ad-set level so Meta's delivery system finds the best
  combination itself rather than the advertiser pre-picking winners.
- **3-3-3 approach** (Pilothouse Digital, a named agency, cited 30% outbound-CTR YoY improvement
  claim — agency's own case-study number, not independently audited) — 3 concepts × 3 variations
  × 3 hooks.
- **Testing Grid Framework** (admove.ai) — Hook × Angle × Proof × Format × CTA, a 5-dimension
  matrix, broader than 3-2-2/3-3-3.
- **Angle Mapping** (Jordan Glickman, independent practitioner blog) — framework specifically for
  reducing creative waste by mapping value-prop angles before producing variants.
- **Hook Matrix** pattern cited generically (5 hooks × 2 angles = 10 variants from one concept
  "in under an hour") — priority testing order given as: hook first → visual format → value-prop
  angle → CTA → copy length. This ordering claim recurs across sources and is the most
  actionable/concrete "which lever first" guidance found.
- **Iteration tree** concept: clone the WINNING hook across new formats/lengths/angles rather than
  just increasing budget on the winner — matches the brief's "winner's hook × challenger's visual"
  framing almost verbatim, suggesting this is indeed a real, named practitioner pattern, not
  something the brief invented.

**Open questions:**
- All of these are agency-blog-sourced (UNVERIFIED tier, same content-farm-adjacent ecosystem
  flagged in prior Meta research) — none traces to a named, credentialed source with an audited
  before/after; a deep-dive should look for the ORIGINAL source of "3-2-2"/"3-3-3" (they may be
  the same practitioner lineage renamed) and whether Meta itself has ever endorsed a specific
  cadence, vs these being agency marketing collateral for their own services.
- At Taqinor's ad volume (a handful of creatives, small budget), does a 12-combination DCT test
  even get enough impressions per cell to mean anything, or does the framework need to be
  compressed (e.g., 2×1×1 = 2 creatives only) to fit the real budget — this compression math is
  not addressed by any source found and needs its own working.
- Is there a real difference between "framework for a $50k/mo DTC ecom brand" (where all these
  sources' case studies live) and "framework for a $10-50/day B2B-ish solar lead-gen SMB" — every
  source found skews ecommerce; zero home-services/solar-specific creative-testing-cadence source
  was found in this pass (mirrors the same gap noted in prior channel research for TikTok/Snap).

---

## 4. Incumbent optimizers' mechanical rules vocabulary

**Sources found:**
- **Revealbot/Birch** [help.revealbot.com, bir.ch — vendor's own docs, treat as primary for their
  own product]: condition-action rules engine, **47 condition types across 5 categories**
  (Performance: CPA/ROAS/CTR; Spend: daily budget/lifetime spend; Time: day-of-week/hour;
  Frequency: ad-fatigue indicators; Custom metrics), **12+ action types** (pause/activate, budget
  change, bid adjustment, notify, duplicate campaign), AND/OR grouping, metric-vs-metric
  comparison across time periods, execution cadence as tight as **15 minutes (Facebook's own API
  floor)** up to 72 hours, campaign/ad-set/ad-level granularity. This is the single most complete,
  directly-reusable **rules vocabulary** found — a strong candidate to mirror/beat for the
  engine's own condition-action DSL.
- **Madgicx** [madgicx.com — vendor's own docs/blog, primary for their own product]: framed as
  "rules engine layered with ML signals" — user sets a budget cap + target ROAS/CPA, optimizer
  redistributes daily budget toward ad sets trending above target; explicitly claims
  explainability ("glass house," documents the trigger + expected outcome per change) — a good
  UX precedent for the engine's own change-log/approval-inbox pattern (ties to prior
  ux-ai-assist.md research). **Named minimum**: "works best with at least 8-10 ad sets with
  consistent spend history; on thin data it tends to over-concentrate budget in one location" —
  directly relevant warning for Taqinor's likely small ad-set count.
- **Smartly.io Predictive Budget Allocation** [smartly.io — vendor's own docs, primary for their
  own product]: reallocates budget **every midnight** between delivering ad sets; explicitly
  Bayesian-multi-armed-bandit-based (see §2); two-phase — a data-learning phase then an
  "acceleration mode." The midnight/once-daily reallocation cadence is a concrete, adoptable
  number consistent with CLAUDE.md's existing "batch changes once daily rather than reactive
  micro-adjustments" guidance already recorded in the Meta-tooling research.

**Open questions:**
- None of the three vendors publish their actual decision thresholds (what CPA delta triggers a
  move, what statistical confidence gates a budget shift) — only the vocabulary/category
  structure is public; the actual numeric thresholds are proprietary IP the deep-dive cannot
  fully recover, so Round-1 should aim to DERIVE reasonable thresholds from the stats research
  (§2) rather than expect to find Madgicx's/Smartly's real numbers.
- Do any of these three tools publish (even informally, in a blog/webinar) their actual
  statistical test underneath the "rule," or is it genuinely opaque business logic dressed as
  "AI"? Worth one more targeted look before concluding "build our own from first principles."
- Revealbot's 47-condition/12-action taxonomy is Meta/Google/TikTok-generic — does it need
  adaptation for CTWA-specific signals (WhatsApp conversation started, qualified by rep) that
  don't exist as native ad-platform metrics and would have to come from the ERP/CRM side instead?

---

## 5. Python building blocks

**Sources found:**
- **`facebook-business` (official Python Business SDK)** [PyPI + GitHub, PRIMARY]:
  `github.com/facebook/facebook-python-business-sdk`, actively released (latest tag tracked
  8 Jun 2026 per search), supports current Graph/Marketing API versions, some deprecated
  `AbstractCrudObject` methods flagged for future removal. This is the lower-level SDK the
  `meta-ads` CLI (from prior research) itself likely wraps — relevant as a fallback if the CLI's
  command surface doesn't cover something (e.g. Split Testing API objects), since the CLI's
  documented command list didn't obviously include split-test creation.
- **GrowthBook** (OSS, MIT core) — Python SDK among 24 official SDKs; full stats engine
  (Bayesian/frequentist/sequential/CUPED/bandits/SRM) is open-source and warehouse-native — a
  serious candidate to either vendor-in directly or read as a reference implementation for the
  engine's own stats module, rather than reinventing sequential-testing math from scratch.
- **`meta-ads-kit`** (GitHub, `TheMattBerman/meta-ads-kit`) — "open source AI ad manager,"
  explicitly built on top of Meta's own official Ads CLI + an agent framework (OpenClaw) —
  directly comparable in spirit to what Taqinor is building; worth reading its source for
  patterns (how it wraps the CLI, what its briefing schema looks like) even if not reused.
- **scipy.stats** — standard for basic two-proportion z-tests / t-tests if a lightweight
  frequentist check is ever needed alongside a Bayesian primary engine; no dedicated search was
  run on scipy specifically this pass (well-known stdlib-adjacent tool, doesn't need sourcing).
- No dedicated lightweight "pymc-lite" was identified — PyMC itself is the standard Python
  Bayesian-modeling library but is heavyweight for a simple beta-binomial bandit; a from-scratch
  beta-binomial Thompson sampler (few dozen lines, `numpy.random.beta`) is likely sufficient and
  was not found to need an external framework — flag this as a Round-1 build decision, not a
  research gap.

**Open questions:**
- Does the official `meta-ads` CLI (from prior eng-meta-tooling.md research) expose Split-Testing-
  API objects at all, or does the engine need to drop to the raw `facebook-business` SDK / REST
  calls for that one feature? Not confirmed in prior research or this pass — needs a direct check
  against the CLI's documented command list.
- Is GrowthBook's stats engine usable STANDALONE as a Python library (import the stats module
  without running their whole warehouse/feature-flag platform), or is it only usable via their
  hosted/self-hosted app with a SQL warehouse behind it — this materially changes whether it's
  "vendor a library" or "stand up a service," and wasn't resolved in this pass.
- `meta-ads-kit`'s actual code quality/activity level (stars, last commit, whether it's a toy repo
  or real) wasn't checked — worth one look before citing it as a serious pattern reference.

---

## Cross-cutting synthesis (not a full answer — flagging where territories 1-5 interact)

- Territory 1 (Meta's own learning-phase/CBO mechanics) and Territory 2 (low-volume stats) and
  Territory 4 (incumbent rule vocabularies) all point toward the SAME architecture: **a
  once-daily (not real-time) batch decision loop**, reading yesterday's Meta insights, applying a
  Bayesian/bandit-style allocation rule ACROSS ad sets Meta doesn't already fully own the
  reallocation for (or across CTWA/proxy-metric rungs Meta can't see at all), gated by an approval
  inbox (per ENG's already-merged approval-inbox pattern) before any live write. This isn't a
  finding to over-claim yet — it's the shape Round-1 should go test against real numbers.
- Territory 3 (creative frameworks) is the one area where NOTHING found is Taqinor-volume-
  appropriate or vertical-appropriate (all ecom-scale, all agency self-promotion) — this is the
  weakest evidence base of the five and the strongest case for a dedicated deep-dive that also
  tries to falsify the frameworks, not just catalog them.

---

## ROUND-1 mission list — science deep-dives

**Mission S1 — Low-volume test design math, worked at Taqinor's real numbers.**
Scope: take Taqinor's actual/plausible monthly volumes at each ladder rung (impressions → clicks →
CTWA conversations → qualified leads → signatures) and compute: (a) minimum detectable effect at
each rung for a fixed-horizon two-proportion test at 80% power/95% confidence — show the MDE is
probably huge at the bottom rungs; (b) a concrete beta-binomial Thompson-sampling bandit spec
(prior, update rule, arm-selection rule, minimum-exploration floor) sized for 2-4 creative arms at
10-100 conversions/month; (c) an explicit rung-to-decision-authority table (which rung can trigger
an autonomous budget/pause action vs which rung only ever informs a human-approved decision) —
this table is the actual deliverable the engine's rule logic will be built from. Read: GrowthBook's
open-source stats-engine source (not just docs) for a reference sequential/Bayesian implementation;
Evan Miller + the arXiv "Always Valid Inference" paper for the sequential-testing math itself.

**Mission S2 — Meta mechanics precision pass: learning-phase reset triggers, Split Testing API
real limits, and CBO-vs-external-bandit boundary.** Scope: resolve, against Meta's OWN docs (not
secondary blogs) or one live empirical test if docs are silent: exactly which edit types reset the
learning phase; whether the Split Testing API/native Experiments tool is usable at all at a
100-500 MAD/day total budget or must be abandoned in favor of a DIY two-ad-set structure; and a
crisp rule for which budget-allocation decisions the deterministic engine should make (across
CBO campaigns / across objectives / across the CTWA-proxy-metric layer Meta can't see) vs which
Meta's own CBO/Advantage+ already owns and the engine must NOT fight. Deliverable: a one-page
decision boundary the engine's budget-mover code is built against, plus a flagged list of
mechanics that can only be resolved empirically (with the exact live-test recipe to run once
Taqinor's ad account is wired).

**Mission S3 — Rules-vocabulary spec matching/beating Revealbot + Madgicx + Smartly.** Scope:
design the engine's own condition-action DSL (conditions: CPA/ROAS/CTR/spend/time/frequency/
custom incl. CTWA-conversation-rate and lead-qualification-rate pulled from the CRM side; actions:
pause/resume/budget-delta/creative-rotate/notify/escalate-to-approval-inbox) at parity with
Revealbot's 47/12 taxonomy but extended with the ERP-side proxy metrics no ad platform exposes
natively; specify execution cadence (propose once-daily batch per the cross-cutting synthesis
above, not Revealbot's 15-minute floor) and an explainability log format (mirroring Madgicx's
"glass house" trigger+outcome record) that feeds the existing ENG approval-inbox. This mission
is spec-writing over what's already been found, not further open web research — mark it
lower-priority/last if Round-1 needs trimming.

**Mission S4 (optional/lighter, could fold into S1 or S2) — Creative-testing cadence
right-sized for Taqinor's actual scale.** Scope: stress-test the 3-2-2/hook-matrix frameworks
against Taqinor's real monthly ad-spend and creative-production capacity; produce a compressed,
Taqinor-appropriate creative iteration cadence (how many arms, what changes between rounds, how
long each round runs) explicitly grounded in the Mission S1 MDE math rather than agency-blog
folklore, since Territory 3's evidence base is the weakest of the five.

---

## Sources (consolidated, all territories)

Primary/near-primary:
- [Meta Split Testing API — Marketing API guide](https://developers.facebook.com/docs/marketing-api/guides/split-testing/) (fetched directly)
- [facebook/facebook-python-business-sdk — GitHub](https://github.com/facebook/facebook-python-business-sdk)
- [facebook-business — PyPI](https://pypi.org/project/facebook-business/)
- [GrowthBook — GitHub](https://github.com/growthbook/growthbook) + [growthbook.io/products/experimentation](https://www.growthbook.io/products/experimentation)
- [Smartly Predictive Budget Allocation](https://www.smartly.io/product-features/predictive-budget-allocation)
- [Revealbot/Birch — Creating automated rules (Help Center)](https://help.revealbot.com/en/articles/1526011-creating-automated-rules)
- [Bïrch (Revealbot) — Automated Rules](https://bir.ch/facebook-ads/automated-rules)
- [Madgicx — Autonomous Budget Optimizer](https://madgicx.com/products/autonomous-budget-optimizer)
- [Evan Miller — Simple Sequential A/B Testing](https://www.evanmiller.org/sequential-ab-testing.html)
- [arXiv 1512.04922 — Always Valid Inference](https://arxiv.org/pdf/1512.04922)
- [Springer — Multi-armed bandits for performance marketing](https://link.springer.com/article/10.1007/s41060-023-00493-7)
- [arXiv 2502.02920 — Adaptive Budget Optimization, Combinatorial Bandits](https://arxiv.org/html/2502.02920)
- [TheMattBerman/meta-ads-kit — GitHub](https://github.com/TheMattBerman/meta-ads-kit)

Secondary/agency (UNVERIFIED tier, directional only, same caution as prior Meta-tooling research):
- get-ryze.ai, benly.ai, adenslab.com, jonloomer.com (split-test duration/budget folklore)
- adstellar.ai, cropink.com, superscale.ai (learning-phase/CBO mechanics folklore)
- 7milemedia.com, pipiads.com, adsmanagement.co, pigeondigital.com (3-2-2 method)
- pilothouse.co (3-3-3 approach, named agency case-study claim)
- admove.ai (Testing Grid Framework: Hook×Angle×Proof×Format×CTA)
- jordanglickman.com (Angle Mapping)
- adlibrary.com, syntermedia.ai (Revealbot/Madgicx competitive reviews, cross-checked against vendor docs)
