# AT-SCIENCE — Formal machinery for the "assumption-tree" ads engine, spec-grade

Author target: a mid-level Python dev implements this without further research. Date: 17 Jul 2026.
Scope: the decision-theoretic and non-stationary-bandit machinery behind the founder's idea that a
marketing plan is a *living tree of assumed A/B-test results* — test the most-uncertain first,
re-order by staleness, retest forever, borrow priors across fields, AI only seeds/revisits.
Builds on `dd-science-core.md` (the volume reality: only the top funnel is statistically testable at
100 MAD/day; ~12–17 sequential tests/year of throughput; one live test slot). Every external number
carries a URL + date + [VERIFIED]/[UNVERIFIED]. Where the honest answer is "the field already named
this," it says so.

---

## 0. THE BRUTAL VERDICT FIRST (read this before the formulas)

**The founder independently re-derived three named, published, 15-to-60-year-old algorithms and
believes they are three separate features. They are one.**

1. "Test the most-uncertain assumption first" = a **Value-of-Information / knowledge-gradient
   acquisition rule** (Howard 1966; Frazier–Powell–Dayanik 2008). And as stated ("most uncertain
   first") it is **wrong** — see §A.
2. "Re-order priorities by staleness / retest even long-validated assumptions" = a **forgetting
   factor on the posterior** (discounted Thompson sampling, Raj–Kalyani 2017; discounted-UCB,
   Garivier–Moulines 2011; the discount-factor DLM, West–Harrison 1997). "Staleness" is not a
   separate score you compute — it *falls out* of a forgetting posterior automatically (§B).
3. "Borrow priors from other fields when you have no data" = **empirical-Bayes partial pooling**
   (Robbins/Efron–Morris; and, in exactly this ads setting, Deng's Bing prior-from-past-experiments,
   WWW 2015) (§C).

**The unification (the single most useful thing in this document):** the founder's three mechanisms
collapse into **one loop** — maintain a *discounted (forgetting) Beta posterior per assumption node*,
and each cycle test the node with the **highest Value-of-Information per unit cost**. Staleness
re-prioritization is not code you write; it is the mechanical consequence of the posterior variance
re-inflating on idle nodes, which raises their VoI, which re-selects them. One acquisition function +
one forgetting rule = the whole "living tree."

**The second brutal point:** in the growth-marketing world this same idea already exists as **ICE /
PIE / RICE scoring** (Impact × Confidence × Ease). The founder's tree is a *quantitative, auto-updating
ICE score*. So the idea is novel in **neither** field — decision theory has VoI, growth has ICE. The
only genuine contribution is **wiring them together deterministically and letting the forgetting run
unattended**. Even that is undercut by his own volume ceiling: at ~12–17 tests/year with **one** live
test slot, "which test next?" is a decision made ~15 times a year. A human with a spreadsheet does that
fine. **The machinery's payoff is DISCIPLINE, not optimality** — it stops the engine from ever aiming
its one test at an un-testable money rung, and it auto-resurfaces stale high-stakes nodes months later
when a human would forget. Build the *forgetting posterior + a 50-line VoI score*; do **not** over-build
an EVSI Monte-Carlo cathedral for a decision made fortnightly.

**"Does anybody actually run this?"** The closest deployed things are Google **Vizier**/Meta **Ax**
(Bayesian optimization with transfer priors across studies) and Microsoft **Bing**'s empirical-Bayes
priors from thousands of past experiments — but those optimize *continuous knobs / test sensitivity*,
not a *human-legible tree of marketing assumptions*. A perpetual, forgetting, VoI-scheduled **assumption
tree** as the founder describes it is, as an integrated product, **not something I can find a named
precedent for** — because at real martech volumes people either (a) have enough traffic to run
many parallel bandits and don't need the scheduler, or (b) use hand-scored ICE and don't need the
math. The founder sits in the awkward middle. That is a real (small) niche, not a breakthrough.

---

## A. VALUE OF INFORMATION — the correct "which test next" criterion

### A.1 Why "most uncertain first" is the wrong objective [VERIFIED — decision theory]

Uncertainty is one of **three** multiplicands. The decision-theoretic quantity is the **Expected Value
of Sample Information (EVSI)**: the expected gain in decision value from running the test, *before*
seeing its result (a preposterior quantity). Its ceiling is **EVPI** (value of *perfect* information).
[VERIFIED — EVSI/EVPI: en.wikipedia.org/wiki/Expected_value_of_sample_information, fetched 17 Jul 2026;
Howard, "Information Value Theory," IEEE Trans. SSC, 1966.]

EVSI is **zero** in two cases a pure "most-uncertain-first" rule ignores:
- **Zero stakes.** A maximally-uncertain question whose answer changes no budget decision (button
  colour on a rarely-seen surface) has EVSI ≈ 0. "Most uncertain first" would test it.
- **Zero testability.** The founder's *own* `dd-science-core.md` proves the qualified-lead and
  signature rungs have MDE ≫ 100% and are pure Poisson noise. Those rungs are the **most uncertain
  things in the whole funnel** — so "most uncertain first" sends the engine **straight at the two
  questions it can never answer**. EVSI catches this because information you cannot acquire has no
  value regardless of how uncertain you are.

So the criterion is **EVSI per unit cost**, and it decomposes exactly into the three factors the
founder half-named: **stakes × decision-relevance(uncertainty) × testability**, divided by cost.

### A.2 The operational form: the Knowledge Gradient [VERIFIED]

The computable, one-step version of EVSI is the **Knowledge Gradient (KG)**: measure the alternative
that "would produce the highest value if you only had one more measurement." [VERIFIED — Frazier,
Powell, Dayanik, "A Knowledge-Gradient Policy for Sequential Information Collection," *SIAM J. Control
Optim.* 47(5):2410–2439, 2008; people.orie.cornell.edu/pfrazier/pub/2007_FrazierPowellDayanik.pdf.]
Chick & Frazier's ranking-and-selection indices are explicitly "EVSI of a forward-looking sampling
plan." [VERIFIED — Chick–Gans–Yapar, "Bayesian Sequential Learning for…", Wharton working paper,
faculty.wharton.upenn.edu/wp-content/uploads/2016/11/Chick-Gans-Yapar-Bayesian-Seqential-2021.pdf;
Frazier, "Decision-theoretic foundations of simulation optimization,"
people.orie.cornell.edu/pfrazier/pub/frazier_weor.pdf, both fetched 17 Jul 2026.] The Gittins/Whittle
index is the same family — a value-of-information index derived as a Lagrange multiplier of a
"retirement" problem. [VERIFIED — Whittle 1988; en.wikipedia.org/wiki/Gittins_index, fetched 17 Jul
2026.]

### A.3 The per-node scoring formula (implementable) [SYNTHESIS, grounded in A.1–A.2]

For each assumption node *j* controlling a two-arm choice (champion A vs challenger B), with Beta
posteriors `(αA,βA),(αB,βB)`:

```
Score_j  =  S_j · U_j · T_j  /  C_j          # pick argmax; this is EVSI-per-cost, factored

S_j (stakes, MAD/month)  = downstream revenue this node governs
      = budget_share_affected × leads_per_month × MAD_per_lead × elasticity_of_leads_to_this_rate
      (a top-funnel CTR node governs ALL leads → S large; an audience-subsegment node governs a slice)

U_j (decision-relevance / uncertainty, 0..1)
      Var(θ) = αβ / ((α+β)²(α+β+1))                       # Beta posterior variance
      σ_diff = sqrt(Var(θA) + Var(θB))
      U_j    = 1 − |2·P(B best) − 1|                       # 1 at a coin-flip, →0 once you're sure
      (P(B best) via the same Monte-Carlo argmax you already run in dd-science-core §2.3)

T_j (testability, 0..1)  = power to resolve the node's PLAUSIBLE effect in a feasible window
      δ_MDE(n_D) = 2.8016 · sqrt(2·p̂(1−p̂)/n_D)            # dd-science-core §1.2, n_D = events in D weeks
      T_j       = clip(δ_plausible / δ_MDE(n_D), 0, 1)      # →0 when the effect is undetectable (money rungs)

C_j (cost)  = weeks of the single test slot the node consumes (≥ burn-in 3–4 wks, dd-science-core §4)
```

**Reading:** `T_j` is the term that makes this VoI and not "most uncertain first." Drop `T_j` and the
engine chases un-testable money rungs; drop `S_j` and it wastes its ~15 annual slots on trivia. Keep
all three and the ordering is correct *by construction*.

**Cost discipline:** at one slot / ~15 decisions a year, do **not** compute full multi-step EVSI by
nested Monte-Carlo. The one-step `S·U·T/C` score above is enough and is ~50 lines. Reserve real KG/EVSI
for if/when budget scales to several parallel slots.

---

## B. NON-STATIONARITY — forgetting, and why "add pseudo-variance per week" is a real technique

### B.1 The named algorithms [VERIFIED]

| Method | What it does | Key parameter | Source |
|---|---|---|---|
| **Discounted TS (dTS)** | discounts Beta counts each step; variance re-inflates, mean ~unchanged | discount γ | Raj & Kalyani 2017, arXiv 1707.09727 |
| **Sliding-Window TS (SW-TS)** | posterior from only the last *w* observations | window w | Trovò et al., *JAIR* 2020, arXiv 2409.05181 |
| **f-dsw TS** | combines a discounted long-term sampler + a windowed short-term sampler | γ and w | Cavenaghi et al. 2021, IEEE (ieeexplore 10622208) |
| **Discounted-UCB / SW-UCB** | the UCB analogues; regret bounds proven | γ resp. w | Garivier & Moulines, *ALT* 2011, arXiv 0805.3415 |
| **KF-MANB / dynamic TS** | Kalman filter per arm; unplayed arms gain variance each step | process var W | Granmo–Berg 2010; Gupta–Granmo–Agrawala 2011 |
| **Restless bandits** | arms' states drift even when not pulled | Whittle index | Whittle 1988 |

The mechanism the founder intuited — *"posterior variance grows the longer since you last tested"* —
is **exactly** the effect of discounting: "exponential filtering … increases the variance of the prior
distribution maintained for all arms while keeping the mean almost constant, thereby increasing the
probability of picking past inferior arms for exploration." [VERIFIED — paraphrase of the dTS
literature, arxiv.org/pdf/2305.10718, fetched 17 Jul 2026.] And in dynamic/Kalman bandits "non-played
arms have variance inflation added to their uncertainty estimate for each time step." [VERIFIED — same
search corpus, Gupta et al., daheekwon.github.io/pdfs/dynamicTS.pdf.]

### B.2 Discounted Thompson sampling — the exact Beta update [VERIFIED form]

Keep discounted success/failure pseudo-counts per arm. Each step, **every** arm is discounted; only the
**played** arm gets new data:

```
S_i ← γ · S_i + 1[played i] · r          # r ∈ {0,1}, the Bernoulli reward (proxy conversion)
F_i ← γ · F_i + 1[played i] · (1 − r)
sample θ_i ~ Beta(S_i + α0, F_i + β0)     # α0,β0 = the (empirical-Bayes) prior, §C
```
[VERIFIED — canonical discounted-TS update, Raj & Kalyani 2017, arXiv 1707.09727; γ∈[0,1].]

**Two facts that give the founder his knobs directly:**
- **Memory (effective sample size) saturates at `n_eff = 1/(1−γ)`** for a continuously-played arm
  (geometric series). γ=0.90→10, γ=0.95→20, γ=0.98→50, γ=0.99→100 observations of memory. [VERIFIED —
  standard geometric-series result for exponential forgetting.]
- **Half-life of an observation = ln(0.5)/ln(γ)** steps. γ=0.95→13.5, γ=0.98→34.3, γ=0.99→69.
- **Idle arms:** with no new data, `S_i,F_i ← γS_i, γF_i` each step → `α+β` shrinks geometrically →
  variance `∝ 1/(α+β)` **inflates**, mean `S/(S+F)` **unchanged**. *This is the founder's "add
  pseudo-variance per week since last test," and it is the recognized, published mechanism — not a hack.*

Garivier–Moulines' D-UCB uses the same γ; a principled setting is `γ = 1 − (4B)^-1·√(Υ_T/T)` where
`Υ_T` = number of change-points, `B` = reward bound, `T` = horizon — i.e. **discount faster when the
world changes more often.** [VERIFIED — arXiv 0805.3415.] Practitioners grid-search γ∈{0.5…0.9} for
fast-changing and use 0.99–0.999 for slow drift. [UNVERIFIED-directional — practitioner reports,
researchgate 379180208, fetched 17 Jul 2026.]

### B.3 "Variance inflation per week" IS a recognized technique: the discount-factor DLM [VERIFIED]

The founder asked whether "add pseudo-variance per week" is a real, named thing. **Yes — it is the
prediction/evolution step of a Kalman filter / Dynamic Linear Model.** Between observations the state
evolves `θ_t = θ_{t−1} + w_t`, so the variance grows `V_t = V_{t−1} + W`. West & Harrison's **discount
formulation** sets that inflation as a *percentage* per step: uncertainty rises by **`100·(1−δ)/δ %`**
each step, with **δ ∈ [0.97, 0.99]** the standard, robust range. [VERIFIED — West & Harrison, *Bayesian
Forecasting and Dynamic Models*, 2nd ed. 1997; sciencedirect.com/science/article/pii/S0169207022001376,
fetched 17 Jul 2026.] So the founder's instinct maps to a 25-year-old textbook method; the only design
choice is δ (Gaussian) or the equivalent γ (Beta).

### B.4 Concrete parameterization for MONTHLY-scale ad assumptions with seasonal half-lives

**Critical design point — TWO clocks.** The within-test bandit (`dd-science-core.md`) runs on a
**daily/impression** clock. The **tree/staleness layer runs on a WEEKLY node clock** — one "step" =
one week since the node was last actively tested. Do **not** discount node beliefs per impression; that
would forget within a single flight. Apply forgetting at the node level, weekly.

Pick a **seasonal half-life H (weeks)** = how fast the *truth* of this assumption drifts, then set the
weekly retention `ρ = 0.5^(1/H)`:

| Assumption class | Drift driver | H (wks) | weekly ρ=0.5^(1/H) | node memory 1/(1−ρ) |
|---|---|---:|---:|---:|
| Creative hook / format | ad fatigue, audience mood | **8** | 0.917 | ~12 wks |
| Value-prop / angle | market sentiment, competitor moves | **13** (a quarter) | 0.948 | ~19 wks |
| Audience / geo | slow structural | **26** (half-year) | 0.974 | ~38 wks |
| Hard seasonal (Ramadan, summer AC→solar) | calendar | — | **use a covariate, not ρ** | — |

Per week idle, update `S_node ← ρ·S_node, F_node ← ρ·F_node` (shrinks effective evidence toward the
prior; variance re-inflates). Recompute `U_j` (§A.3) from the inflated posterior — a validated
high-stakes node's `U_j` climbs back toward 1 over ~H/2 weeks and re-enters the argmax against fresh
branches. **That is the entire "re-order by staleness / retest forever" feature, for free.**

**Do NOT use a forgetting factor for known calendar seasonality** (Ramadan, summer). A forgetting
factor models *unknown* drift; a *known* recurring shift is better handled by a seasonal **covariate /
separate node per season** (West–Harrison seasonal DLM component). Blindly discounting through Ramadan
throws away last year's Ramadan data exactly when it is most relevant.

---

## C. COLD START — empirical-Bayes priors that borrow across fields/accounts

### C.1 Industry precedent this is real [VERIFIED]

- **Microsoft Bing** learns priors from **thousands of past experiments** (empirical Bayes) to improve
  new-test sensitivity — the exact "borrow from other fields" idea, deployed. [VERIFIED — Deng,
  "Objective Bayesian Two Sample Hypothesis Testing for Online Controlled Experiments," *WWW* 2015,
  exp-platform.com/Documents/BayesianAB.pdf; and Deng–Xu–Kohavi–Walker, "Improving the Sensitivity of
  Online Controlled Experiments by Utilizing Pre-Experiment Data," *WSDM* 2013.]
- **Hierarchical empirical Bayes in online advertising** for sparse cold-start ads is published.
  [VERIFIED — "Dynamic Hierarchical Empirical Bayes: A Predictive Model Applied to Online Advertising,"
  arXiv 1809.02213.] Multi-task / random-effect bandits formalize "borrow strength across arms/tasks."
  [VERIFIED — "Metadata-based Multi-Task Bandits with Bayesian Hierarchical Models," arXiv 2108.06422;
  "Random Effect Bandits," arXiv 2106.12200.]
- **Meta / Google exact internal ad-prior recipes: UNVERIFIED** (proprietary). Ax/BoTorch and Vizier
  support transfer priors across studies, but the specific ad cold-start priors are not published.

### C.2 The recipe: fit a Beta prior from category aggregates, then CAP its strength [VERIFIED method]

Given related fields/accounts with observed rates `p_1…p_k` (e.g. other Taqinor creatives, or a
category CTWA benchmark), fit `Beta(α0,β0)` by **method of moments**:

```
m  = mean(p_i)                         # category-level mean rate
s2 = var(p_i)                          # dispersion ACROSS fields (not within)
κ  = m·(1−m)/s2 − 1                     # implied prior "sample size" (precision)
α0 = m·κ ;   β0 = (1−m)·κ
```
[VERIFIED — canonical Beta-binomial empirical Bayes; Efron–Morris shrinkage; the standard
method-of-moments fit, e.g. Robinson, "Understanding empirical Bayes estimation," varianceexplained.org.]

**Effective-sample-size cap (the piece the mission asked for).** A borrowed prior must be *overwhelmable*
by ~1 week of real local data, or a wrong cross-field prior poisons the new field. Cap the prior
strength at `κ_max`:

```
κ_max = min(50, one_week_of_events_for_this_node)      # dd-science-core §2.2 uses 30–50
if α0+β0 > κ_max:  α0,β0 ← α0,β0 · κ_max/(α0+β0)        # rescale, keep the mean m
```
`κ_max ≈ 30–50` pseudo-obs ≈ "worth a few hundred impressions," so ~1 week of delivery dominates it
(consistent with dd-science-core's informative-prior option). For a brand-new vertical with **no**
sibling data at all, fall back to the category CTWA benchmark as `m` with `κ_max = 30`, or to
`Beta(1,1)` if even that is unknown.

**Hierarchy for "borrow across accounts":** partial pooling — each field's rate shrinks toward the
grand mean by `κ/(κ+n_field)`. New field (n=0) sits at the grand mean; as its own data arrives it
detaches. This is exactly "borrow priors from other fields, then let local data take over." [VERIFIED —
partial pooling / shrinkage, Gelman *BDA*; the ads application, arXiv 1809.02213.]

---

## D. INTERACTION STRUCTURE — when the OFAT tree lies, and is it defensible here?

### D.1 The real statistical objection [VERIFIED]

The founder's tree tests **one variable at a time, holding the current champion of the others fixed**
= **OFAT (one-factor-at-a-time)**, a.k.a. coordinate ascent / hill-climbing. The textbook fact: *"When
the effect of one factor differs across levels of another, it cannot be detected by an OFAT design.
Factorial designs are required to detect such interactions; OFAT under interactions can lead to serious
misunderstanding."* [VERIFIED — Box, Hunter & Hunter, *Statistics for Experimenters*, 2005;
en.wikipedia.org/wiki/Factorial_experiment, fetched 17 Jul 2026.] Factorial designs also estimate main
effects **more efficiently** (every run informs every factor) and reveal interactions in the *same*
runs. [VERIFIED — NBER w26562, "Factorial Designs, Model Selection, and (Incorrect) Inference,"
nber.org/system/files/working_papers/w26562.pdf.]

The classic failure mode for the founder's engine: a **hook that only wins in video format**. OFAT
tests hooks (in static), picks hook-A, then tests format and picks video — and never discovers that
hook-B + video beats everything. Coordinate ascent gets stuck at a local optimum under interaction.

### D.2 Why the OFAT tree is nonetheless DEFENSIBLE at 100 MAD/day [SYNTHESIS — the honest answer]

Not because interactions don't exist, but because **he cannot afford to estimate them**:
1. **Interactions are typically smaller than main effects**, and his detection floor is already
   **±18–35% relative on the ONE testable rung** (dd-science-core §1.3). A 2×2 factorial splits his
   tiny volume across 4 cells → MDE per main effect worsens ~√2, and the interaction term (usually a
   fraction of a main effect) lands **far below the floor**. He would run a factorial and detect
   *nothing, less powerfully.* [VERIFIED reasoning from dd-science-core MDE math + factorial power.]
   (The "interactions are usually small" heuristic is widely asserted from large-scale online
   experimentation — Kohavi et al., *Trustworthy Online Controlled Experiments*, 2020 — but I did not
   fetch the exact passage: treat as [UNVERIFIED-directional].)
2. **Testing against the full champion absorbs the interactions that matter most.** Because each new
   branch is tested as *champion + new-variable* (not against an abstract baseline), interactions with
   **already-fixed** factors are implicitly captured. The only blind spot is interactions with factors
   tested in the **future** — mitigated by revisiting (§B) and by testing *categorically different*
   whole-creative challengers, not 5% tweaks.
3. **At ~15 tests/year, a full/fractional factorial program is a non-starter** on calendar alone.

**Recommendation:** keep OFAT-around-the-champion. When (and only when) budget scales enough that a
rung's MDE drops below ~15%, insert an occasional **2×2 factorial "interaction probe"** on the two
highest-stakes factors (4 arms, one phase) to check for a sign-flipping interaction. Until then, OFAT
is defensible **by necessity, not by correctness** — say that plainly to the founder.

---

## E. THE EXPLORATION TAX — a principled cap on perpetual retesting

### E.1 What the literature gives [VERIFIED + folk]

- **Folk default:** ε-greedy with **ε ≈ 0.10** (10% of traffic to exploration) is the standard
  production starting point; ε≈0.1 is reported "Pareto-optimal across a wide budget/dimensionality
  range." [UNVERIFIED-directional — practitioner/《survey》summaries, emergentmind exploration-exploitation,
  fetched 17 Jul 2026.] dd-science-core already sets a **20%-per-arm floor** (in MAD, to clear Meta's
  ~$1/day delivery minimum) — so the *within-test* exploration tax is already fixed at ~20%.
- **Principled version (non-stationary):** the cost you pay to stay fresh scales with the **change
  rate**. Garivier–Moulines' regret is `O(√(Υ_T · T))` where `Υ_T` = number of change-points — i.e.
  **re-exploration effort should scale with how often the world changes, no more.** [VERIFIED — arXiv
  0805.3415.] This is the rigorous form of "retest as often as the truth drifts, and no oftener."

### E.2 The retest-share cap for the assumption tree [SYNTHESIS]

At the tree level the scarce resource is not budget-% but **test slots** (~15/year, one at a time). The
tax is: *what fraction of your ~15 annual slots do you spend re-confirming known-good nodes vs. growing
new branches?*

**Principled cap:** a node with half-life `H` weeks needs re-validation about every `H/2 … H` weeks. If
you have `N_validated` nodes each costing a `D`-week slot, the retest load is
`Σ D / retest_interval`. **Hold total retest load ≤ ~20–30% of slot capacity** (mirrors the 10–20% folk
band and the 20% within-test floor). Concretely: with D≈4 wks, H≈13 wks, retest every ~10 wks → each
node eats 4/10 = 40% of a slot's time *while due*; so **at most ~1 high-stakes node** can be on a
perpetual-retest cadence before it crowds out exploration. That is the real ceiling — spell it out:
**at this throughput the engine can perpetually re-validate essentially ONE champion assumption; every
other "retest" competes one-for-one with a new branch.**

**Let VoI arbitrate it automatically (don't hand-tune a separate retest scheduler).** Because §B
re-inflates `U_j` on stale nodes and §A multiplies by stakes `S_j`, the argmax **naturally** spends
slots on retesting only when a *high-stakes* node has gone *stale enough* that its `S·U·T/C` beats every
new branch. Set the forgetting `ρ` (§B.4) and the cap emerges — no separate exploration-budget knob.
If retests are crowding out all exploration, `ρ` is too aggressive (H too short): lengthen H.

---

## F. CONSOLIDATED PARAMETER DEFAULTS (what a dev types in)

| Layer | Parameter | Default | Source / tag |
|---|---|---|---|
| VoI score | `Score = S·U·T/C` (argmax) | one-step, not nested EVSI | §A.3 [SYNTHESIS/VERIFIED] |
| VoI | `T_j = clip(δ_plausible/δ_MDE, 0,1)` | kills un-testable nodes | §A.3 + dd-science-core §1.2 |
| Within-test bandit | prior, reward, window | Beta(1,1)+EB option, conv/imp, 28d | dd-science-core (unchanged) |
| Node forgetting clock | **weekly**, not per-impression | two-clock rule | §B.4 [SYNTHESIS] |
| Node forgetting | seasonal half-life `H` | 8 wk (creative), 13 wk (angle), 26 wk (geo) | §B.4 |
| Node forgetting | weekly retention `ρ=0.5^(1/H)` | 0.917 / 0.948 / 0.974 | §B.4 [VERIFIED math] |
| (Gaussian alt) DLM discount | `δ` | 0.97–0.99 (inflate 1–3%/wk) | §B.3 [VERIFIED W&H] |
| Known seasonality | covariate, **not** ρ | separate seasonal node | §B.4 [VERIFIED] |
| Cold-start prior | `Beta(α0,β0)` method-of-moments | from sibling/category rates | §C.2 [VERIFIED] |
| Cold-start cap | `κ_max = min(50, 1 wk events)` | overwhelmable in ~1 wk | §C.2 [VERIFIED] |
| Design | OFAT-around-champion | keep; 2×2 probe only if MDE<15% | §D.2 [SYNTHESIS] |
| Exploration tax | retest load ≤ 20–30% of slots | ≈1 perpetual-retest node at this volume | §E.2 [SYNTHESIS] |
| AI role | seed tree once + quarterly revisit | everything else deterministic | founder spec — endorsed |

---

## G. Sources (URL + date + evidence tag)

Primary / near-primary:
- [EVSI/EVPI — Wikipedia](https://en.wikipedia.org/wiki/Expected_value_of_sample_information) — 17 Jul 2026 [VERIFIED]
- [Frazier, Powell, Dayanik — A Knowledge-Gradient Policy for Sequential Information Collection, SIAM JCO 2008](https://people.orie.cornell.edu/pfrazier/pub/2007_FrazierPowellDayanik.pdf) — 17 Jul 2026 [VERIFIED]
- [Frazier — Decision-theoretic foundations of simulation optimization](https://people.orie.cornell.edu/pfrazier/pub/frazier_weor.pdf) — 17 Jul 2026 [VERIFIED]
- [Chick–Gans–Yapar — Bayesian sequential learning (EVSI indices)](https://faculty.wharton.upenn.edu/wp-content/uploads/2016/11/Chick-Gans-Yapar-Bayesian-Seqential-2021.pdf) — 17 Jul 2026 [VERIFIED]
- [Gittins index / Whittle retirement — Wikipedia](https://en.wikipedia.org/wiki/Gittins_index) — 17 Jul 2026 [VERIFIED]
- [Raj & Kalyani — Taming Non-stationary Bandits (discounted TS), arXiv 1707.09727](https://arxiv.org/pdf/1707.09727) — 17 Jul 2026 [VERIFIED existence; update rule = canonical dTS]
- [Discounted TS for Non-Stationary Bandit Problems, arXiv 2305.10718](https://arxiv.org/pdf/2305.10718) — 17 Jul 2026 [VERIFIED — variance-inflation mechanism]
- [Trovò et al. — Sliding-Window Thompson Sampling, arXiv 2409.05181](https://arxiv.org/html/2409.05181v3) — 17 Jul 2026 [VERIFIED]
- [Garivier & Moulines — UCB for Non-Stationary/Switching Bandits (D-UCB, SW-UCB), arXiv 0805.3415, ALT 2011](https://arxiv.org/abs/0805.3415) — 17 Jul 2026 [VERIFIED — γ rule, O(√(Υ_T·T)) regret]
- [Gupta, Granmo, Agrawala — Thompson Sampling for Dynamic MAB (Kalman variance inflation)](https://daheekwon.github.io/pdfs/dynamicTS.pdf) — 17 Jul 2026 [VERIFIED]
- [West & Harrison — DLM discount factor, variance inflation 100(1−δ)/δ%, δ∈0.97–0.99](https://www.sciencedirect.com/science/article/pii/S0169207022001376) — 17 Jul 2026 [VERIFIED]
- [Deng — Objective Bayesian Two-Sample Testing (Bing empirical-Bayes priors), WWW 2015](https://www.exp-platform.com/Documents/BayesianAB.pdf) — 17 Jul 2026 [VERIFIED]
- [Dynamic Hierarchical Empirical Bayes for Online Advertising, arXiv 1809.02213](https://arxiv.org/pdf/1809.02213) — 17 Jul 2026 [VERIFIED]
- [Metadata-based Multi-Task Bandits (hierarchical), arXiv 2108.06422](https://arxiv.org/pdf/2108.06422) — 17 Jul 2026 [VERIFIED]
- [NBER w26562 — Factorial Designs, Model Selection, and (Incorrect) Inference](https://www.nber.org/system/files/working_papers/w26562.pdf) — 17 Jul 2026 [VERIFIED]
- [Factorial experiment / OFAT interaction failure — Wikipedia](https://en.wikipedia.org/wiki/Factorial_experiment) — 17 Jul 2026 [VERIFIED]

Secondary / directional (flagged in-text):
- Discount-factor tuning grid-search reports — researchgate 379180208 [UNVERIFIED-directional]
- ε≈0.1 exploration folk default — emergentmind exploration-exploitation-tradeoff [UNVERIFIED-directional]
- Kohavi et al. 2020 "interactions usually small" — asserted, passage not fetched [UNVERIFIED-directional]
- Meta/Google internal ad cold-start prior recipes — proprietary [UNVERIFIED]
