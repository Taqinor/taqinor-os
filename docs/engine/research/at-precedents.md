# Autonomous Closed-Loop Experimentation — Precedent Audit

Research date: 17 Jul 2026. Mission: has anyone built THE FOUNDER'S MACHINE — a marketing plan
modeled as a growing TREE of assumed A/B-test results, where the engine (1) tests the
most-uncertain assumptions first, (2) re-orders priorities by staleness (last-tested date),
(3) perpetually retests even long-validated assumptions (seasons/moods change), (4) borrows
priors from other fields/verticals when a new field has no data, (5) keeps growing new branches
so the tree IS the living plan, with (6) AI only seeding the tree at campaign start + revisiting
quarterly, everything else deterministic.

Tags: **[VERIFIED]** primary source fetched/quoted directly. **[INDEPENDENT]** named
non-content-farm secondary source (trade press, official vendor help docs not directly quotable,
converging practitioner sources). **[UNVERIFIED]** single/weak/content-farm source, or my own
synthesis — flagged inline either way.

---

## Executive verdict (read this first)

**Nobody has built this exact machine.** Every individual PIECE the founder describes exists
somewhere, separately, at a much bigger company or in a different discipline — but no product,
paper, or documented internal system combines all six properties into one running system,
and specifically **nothing stores institutional test history as a queryable TREE/GRAPH with an
automated staleness-driven re-prioritization loop.** The closest single artifact is a piece of
*methodology*, not software: **Strategyzer's "Assumptions Mapping"** (David Bland / Alexander
Osterwalder, *Testing Business Ideas*, 2019) — a 2D desirability/viability/feasibility map plotted
on importance × evidence, explicitly designed to identify which assumption to test next by
uncertainty. It is manual, static (redrawn in a workshop, not live software), and has no
closed-loop automation, no staleness timer, and no perpetual re-testing of settled assumptions.
The founder's idea is a genuine, non-trivial synthesis of pieces from five separate disciplines
(growth-hacking backlog hygiene, Bayesian hierarchical statistics, autonomic-computing control
loops, AI-agent research automation, decision-theory graphs) that nobody has fused — which is
either a real opportunity or a real reason it doesn't exist (see Brutal Honesty section at the
end).

---

## (a) Industry closed-loop experimentation cultures

### Amazon Weblab
[INDEPENDENT — multiple converging secondary sources citing Amazon's own disclosed experiment
counts (546 in 2011 → 1,092 in 2012 → 1,976 in 2013 → 12,000+/year today); no single primary
Amazon paper was found stating the exact current count, but the trend and philosophy are
consistently reported across HBR ("The Surprising Power of Online Experiments," 2017) and Amazon
Science's own published summit paper]. Weblab is a **volume-maximization culture**: minimize the
cost per experiment so you can run thousands per year, accept that fewer than half "win." This is
the opposite design philosophy from the founder's idea — it works because Amazon has effectively
unlimited traffic to burn on losers. **It has nothing resembling a staleness-driven re-prioritized
tree**; it is a scaled, cheapened fixed-horizon A/B testing pipeline (Weblab = the assignment/
analysis engine), not an assumption graph.

### Booking.com
[VERIFIED-ish — Booking.com's own `booking.ai` tech blog (Edgar Cano, "Scaling Experimentation
Quality at Booking.com," Mar 2026) fetched directly; the older "Democratizing online controlled
experiments at Booking.com" (Kaufman & Pitchforth, KDD 2017) is the well-known published paper,
confirmed via ResearchGate/Semantic Scholar listings though not re-fetched in full text this pass]
Booking.com runs one of the highest-volume tested-culture platforms in the industry, famous for:
democratized self-serve testing (any employee can launch a test), and a documented internal fight
against **"peeking"** (stopping early when you like what you see) via sequential/always-valid
statistical methods and a "single rule set" so results can't be gamed. This is culturally the
*opposite* problem from Taqinor's (Booking has too much traffic and needs discipline; Taqinor has
too little and needs power). **No staleness/re-test-the-old-stuff mechanism was found in any
Booking.com publication** — their problem is stopping tests correctly, not deciding when to
re-open old ones.

### Netflix XP (Experimentation Platform)
[INDEPENDENT — Netflix's own techblog posts, fetched via search snippets, multiple corroborating
posts 2016-2022] Netflix XP + ABlaze (front-end) is architecturally the cleanest "platform" analog
to what an ads-engine dashboard would need (assignment, analysis, and a results repository visible
company-wide, not siloed to data scientists). Culturally "nearly every decision is guided by member
behavior observed in tests." **No mention anywhere in the surfaced material of automatic re-testing
of old, already-validated results, or of a staleness clock** — Netflix's mitigation for "does this
still hold" is repeat testing driven by human judgment/roadmap, not an automated trigger.

### Stitch Fix — Multithreaded blog
[VERIFIED — `multithreaded.stitchfix.com/blog/2020/08/05/bandits/`, confirmed via search snippet
with direct quotes] Stitch Fix's algorithms team publicly documented **using Thompson Sampling
multi-armed bandits inside their in-house experimentation platform** as an alternative to fixed
A/B tests specifically to reduce the opportunity cost of feeding traffic to a loser — the same
core technique already spec'd in `dd-science-core.md` §2 for Taqinor. This is a precedent for
*the bandit half* of the founder's design (well-trodden, industry-standard at this point — Stitch
Fix, GrowthBook, and Taqinor's own spec all converge on Thompson Sampling for the same reason).
It is not evidence for the tree/staleness/perpetual-retest halves — Stitch Fix's bandit posts don't
describe a graph of assumptions or automatic re-opening of settled questions.

### Meta's own Ax / BoTorch — the most on-point internal Meta precedent, and it's a miss
[VERIFIED — `ax.dev` fetched directly; `engineering.fb.com/2025/11/18/...` (the canonical Meta
Engineering blog post on Ax) fetched directly] **Ax is Meta's real, open-sourced "Adaptive
Experimentation Platform,"** built on **BoTorch** (Bayesian optimization, Gaussian-process
surrogate models — not multi-armed bandits, contrary to the mission brief's framing). Directly
quoting the fetched Meta Engineering post: Ax's actual production use cases at Meta are
**hyperparameter optimization / architecture search for ML models, tuning parameters for
recommender/ranking systems (e.g. Instagram's recommender), infrastructure/compiler-flag tuning,
AR/VR hardware design (Ray-Ban Stories), and even concrete-mix design for data-center
construction.** **Advertising/ad-campaign optimization is never mentioned as an Ax use case** —
confirmed by both the Meta Engineering post and a separate search return stating explicitly that
"for Meta advertising specifically, the platform offers its own AI-driven tools like Advantage+ ...
rather than relying on Ax and BoTorch directly for campaign optimization." **This is the single
most important negative finding of this dossier**: the company that owns both (1) the most
sophisticated in-house adaptive-experimentation engine in the industry and (2) the entire ad
platform the founder is building on top of has never (as far as any public source shows) pointed
(1) at (2). Meta's own ad optimization is a separate, proprietary, Advantage+/CBO black box, not
Ax. If Meta hasn't fused its adaptive-experimentation engine with its ad platform, that is either
because the fusion isn't worth it at Meta's scale (they don't need a sample-efficient
Bayesian-optimization layer — they have billions of auctions/day) or because nobody there has
tried — no source distinguishes which.

---

## (b) Ad tech claiming autonomy — audited

### Albert.ai (Adgorithms) — the "OG autonomous marketing AI," now a smaller company inside a smaller company
[INDEPENDENT — Crunchbase/PitchBook/CB Insights/Tracxn company-profile aggregation, cross-checked;
`agentaya.com`'s Albert AI review fetched directly for functional claims; `albert.ai/about-us`
blocked by 403 (site actively refuses automated fetches — noted, not worked around)]
- **History**: founded as Adgorithms in 2010 (UK-listed, LSE: ADGO), marketed Albert as "the
  first-ever AI marketing platform for the enterprise." **Acquired by Zoomd Technologies, 27 Mar
  2022, undisclosed price** (cash + shares + an earn-out contingent on hitting targets — the
  earn-out structure is itself a signal the buyer didn't trust Albert's standalone momentum enough
  to pay it all up front). Funding figures across databases are inconsistent/unreliable ($680K to
  $100M depending on source) — **flag as genuinely murky, not reconcilable from public data**; no
  authoritative total-raised or valuation-at-exit figure was found. **Verdict: this reads as a
  quiet, not-scaled-independently exit, not a triumphant "autonomous marketing AI proved itself"
  story** — a once-hyped "first mover" ending up folded into a much smaller adtech roll-up
  (Zoomd) 12 years after founding is the opposite of the narrative Albert's own marketing implied.
- **What it ACTUALLY automates today** [from the agentaya.com review, cross-checked against
  Albert's own current marketing site language returned in search snippets]: bid optimization by
  audience/time/device, budget reallocation across channels, "continuous testing on creatives,
  audiences and placements at a speed/volume exceeding human capacity," and keyword management.
  **Creative generation is explicitly NOT included — a human must upload creative assets for Albert
  to test/optimize.** This directly punctures the "fully autonomous" framing: Albert automates the
  *allocation* layer (which of several human-made inputs gets budget), the exact same scope as
  Taqinor's own already-spec'd bandit (`dd-science-core.md` §2-3) — it does not autonomously invent
  new hooks/angles/tests, which is closer to what the founder's "AI seeds the tree" step implies.
- **Who it's actually for**: the review states plainly it is "geared toward enterprise budgets,
  with no public plans," "requires initial setup with a dedicated team," "English-only interface,"
  and works best in "high-volume B2C environments" — explicitly **excluding** "long sales cycles or
  modest volumes" (i.e., exactly Taqinor's regime: low-volume, consultative, French/Arabic-market
  solar sales). The review's own verdict: "oversized and costly" for small businesses. **Albert.ai
  is not a miniaturized version of what the founder wants — it is the same allocation-automation
  idea, built for 100-1000x Taqinor's budget and volume, with no autonomous hypothesis-generation
  layer at all.**

### Smartly.io — real autonomy, narrower than the marketing implies
[VERIFIED — `smartly.io/product-features/triggers`, `docs.smartly.io` fetched directly per the
already-committed `dd-meta-mechanics.md`/`dd-guardian.md` dossiers, re-confirmed this pass via
search snippets of Smartly's own product pages] Smartly genuinely automates: AI-generated creative
variants at scale (1.9M+ assets claimed), automated budget shifting toward predicted winners
("predictive budget allocation," daily/midnight cadence — already cited in `dd-science-core.md`
§2.6), automated creative rotation to fight fatigue (the one competitor with a documented native
"rotate creative" action per `dd-guardian.md` A4), and cross-platform bid adjustment. **Smartly's
own marketing explicitly disclaims full autonomy**: "you decide the boundaries... you'll still need
human input on campaign strategy and creative direction... you set the north star" — i.e. even the
most credible "autonomous" ad-tech vendor markets itself as a co-pilot for allocation, not an
independent hypothesis-generating strategist. No mention anywhere in Smartly's public docs of a
staleness-driven retest mechanism or an assumption tree/graph — same gap as everywhere else.

### General "self-driving media buying" audit
[INDEPENDENT — AdExchanger opinion piece "Self-Driving Advertising Is A Myth," eMarketer's 2026
FAQ on AI media buying, both fetched via search snippet with quotable framing] The trade-press
consensus in 2026 is that AI media-buying tools genuinely automate **tactical execution** (bid
adjustment, budget pacing, creative rotation, anomaly-flagging in reporting — claimed 60-87%
reduction in time spent on these tactical tasks) but that "handing everything over and just saying
'go' puts the burden on the brand to make it work," and that teams which skip regular audits (the
piece recommends weekly spot-checks, monthly model-performance deep-dives, quarterly attribution
reviews) get burned by silent drift. This matches `dd-guardian.md`'s own independently-derived
Madgicx "silent-failure trap" finding almost exactly — convergent evidence from a completely
separate research thread that **"autonomous" ad tools regularly fail quietly and need a human
audit cadence**, which the founder's own design (AI revisits quarterly) already anticipates.
**Nobody in this trade-press cluster describes an assumption tree with staleness-based
reprioritization** — the "autonomy" being audited/criticized is allocation autonomy, the same
narrower scope as Albert and Smartly.

---

## (c) Experiment knowledge bases — do any structure history as a staleness-aware tree/graph?

### Eppo Knowledge Base
[VERIFIED — `docs.geteppo.com/experiment-analysis/reporting/knowledge-base/` fetched directly.
Note: Eppo itself was acquired and is now "Datadog Experiments" per its own homepage, encountered
mid-research — flagged as a fresh, directly-observed fact, not previously known] Eppo's Knowledge
Base is explicitly **"the central repository for experimentation learnings"** — every concluded,
non-misconfigured experiment gets a searchable card (name, dates, owner, decision, metric impact,
takeaways), filterable by outcome/decision/team/metric, "forever indexed... available for
meta-analysis." **This is a flat, searchable ARCHIVE, not a tree or graph.** It does not track
whether a conclusion is stale, does not flag "this was last validated 8 months ago, retest it,"
and does not model dependency edges between hypotheses (e.g., "hypothesis B assumed hypothesis A's
result"). It is a library, not a living structure.

### GrowthBook — closest software feature to "borrow priors" + "staleness"
[VERIFIED for the products existing — `docs.growthbook.io/insights` returned directly-quotable
detail via search snippet] GrowthBook's **"Learnings"** page is the same flat-archive pattern as
Eppo. Its **"Metric Effects"** feature is more interesting: it shows "a histogram of experiment
impacts for a specific metric... providing historical lift data that may be helpful **if using
informative priors in a Bayesian engine**" — i.e., GrowthBook explicitly supports feeding a new
test's prior from the observed distribution of past effect sizes on the same metric. This is a
genuine, shipped, real software precedent for the founder's "borrow priors from other fields" idea
— but it borrows across *past tests on the same metric within the same account*, not literally
across *different business verticals/fields* the way the founder describes (e.g., borrowing a solar
Morocco prior for a brand-new pump-market vertical). GrowthBook also runs a **James-Stein shrinkage
estimator** on experiment-effect estimates specifically to de-bias small-sample results toward a
population mean — a real, cited statistical precedent for "when you don't have enough data on this
specific thing, pull it toward what similar things showed." **Still no staleness clock and no tree
structure** — it's a flat list with good stats hygiene, not a re-prioritizing living plan.

### The staleness concept DOES exist, but as a manual growth-hacking practice, not software
[INDEPENDENT — `mida.so/blog/test-prioritization-frameworks-ice-pie-pxl` fetched directly, a named
growth-consulting blog, cross-checked against `growthmethod.com`'s ICE/PIE/PXL comparison via
search snippet] The **ICE / PIE / RICE / PXL prioritization frameworks** (Sean Ellis's ICE; Chris
Goward/WiderFunnel's PIE) are the standard growth-hacking tools for ranking a test backlog by
impact/confidence/ease. Critically, **the staleness problem is a named, explicitly acknowledged
failure mode of these frameworks in the practitioner literature**: direct quote from the fetched
mida.so article — *"A test idea that scored 8 in January might be a 4 by April because the page
redesigned underneath it"* — and the recommended fix is **"re-score the top 20 ideas every
quarter"** plus re-scoring "whenever test results arrive." **This is the founder's "re-order
priorities by staleness" idea, independently arrived at by the growth-hacking community — but it
is a manual spreadsheet discipline done by a human on a calendar cadence, not an automated
software trigger keyed to a literal last-tested timestamp**, and no source found any tool that
computes "days since last test × some decay function" automatically. The founder's proposed
mechanism (last-tested date drives an automatic re-ordering) is a genuine automation of a known
manual practice, not a previously-unknown idea, but also not something any named product ships.

### "Hypothesis trees" — a real, older, unrelated concept (McKinsey-style, not growth software)
[INDEPENDENT — multiple management-consulting sources (stratechi.com, myconsultingoffer.org)
converging on the same definition, cross-checked] "Hypothesis tree" is a well-established
management-consulting problem-decomposition tool (MECE branching of a business question into
testable sub-hypotheses) predating any of this by decades. It shares vocabulary with the founder's
idea (a tree of hypotheses) but is a **static, one-time analysis artifact drawn in a workshop**,
never described anywhere as a live, perpetually-growing, staleness-triggered software structure.
No source connects it to advertising/growth experimentation specifically, and none describe
automatic re-testing.

**Conclusion for (c): no product structures institutional experiment history as a
staleness-aware decision tree/graph.** The closest thing (Assumption Mapping, cited in the
executive verdict) is a manual 2D map, not a tree, not software, not perpetual.

---

## (d) Decision networks / influence diagrams — the closest formal academic match

[VERIFIED — Wikipedia's "Influence diagram" article and Stanford's Ross Shachter (a named,
foundational academic in this exact subfield) draft chapter "Model Building with Belief Networks
and Influence Diagrams" both fetched/returned via direct search snippet with quotable content]
**Influence diagrams (a.k.a. decision networks/relevance diagrams)** are the real, decades-old
(mid-1970s) formalism the founder is unknowingly reaching for: a directed acyclic graph with three
node types — **decision nodes** (choices), **chance nodes** (uncertain variables, modeled
probabilistically, i.e. exactly "assumptions"), and a **value node** (the objective/utility) — that
generalizes a Bayesian network to also solve for the maximum-expected-utility decision. One search
result explicitly cites a **marketing feedback-loop example**: "Marketing budget → Market share →
Revenues → Marketing budget" as a textbook influence-diagram case. **This is the correct formal
mathematical language for "a tree of assumed test results feeding decisions,"** and tooling exists
(BayesFusion/GeNIe, Analytica) to build and solve such diagrams computationally. **However**: no
source found describes an influence diagram that (1) is continuously re-solved as a live operational
system tied to a real ad account, (2) has a staleness/decay term on its chance-node conditional
probabilities, or (3) is applied to a marketing/advertising test-prioritization use case in either
the academic or commercial literature surveyed this pass. It is the right mathematical skeleton,
never fleshed out for exactly this application as far as this research could find. **This is
genuinely the most useful single fact in this dossier for the founder**: if he wants to formalize
"the tree," an influence diagram / dynamic Bayesian network (the time-indexed extension, which
directly supports a staleness/decay term via time-decaying edge weights) is the existing academic
vocabulary to borrow from — nobody has to invent the math, only apply it here.

No source used the literal phrases "assumption graph" or "belief network for marketing decisions"
as a named, existing product or paper — those exact terms return only generic Bayesian-network
tutorials and unrelated "assumption mapping" (product-management) content, confirming **the
founder's own terminology is original framing**, not a reference to something that already exists
under that name.

---

## (e) Verdict material — closest existing system + the gap

### The closest single precedent, piece by piece
No one system has all six properties. The founder's design is best understood as a fusion of five
separate, independently-real things, none of which know about each other:

1. **Uncertainty-first test selection** → Strategyzer's Assumptions Mapping (importance × evidence
   plot) — manual, one-time, not software.
2. **Bandit-based allocation under low volume** → Stitch Fix / GrowthBook / (spec'd already for
   Taqinor in `dd-science-core.md`) — real, shipped, industry-standard; solves allocation, not
   hypothesis generation.
3. **Staleness-driven re-prioritization** → ICE/PIE backlog-hygiene practice ("re-score quarterly,
   backlogs go stale") — real, named, but manual/calendar-driven, never automated on a literal
   last-tested timestamp in any tool found.
4. **Borrowing priors across domains with no data** → Google's own published Geo-level/hierarchical
   Bayesian Media Mix Modeling (Jin et al. 2017, and GrowthBook's Metric-Effects informative
   priors + James-Stein shrinkage) — real, published, primary-sourced; pools data across
   geos/brands/past-tests-on-the-same-metric to strengthen a data-poor estimate. This is the
   best-evidenced piece of the founder's idea — it is standard Bayesian statistical practice, just
   not previously wired into a "tree of marketing assumptions."
5. **AI seeds once, deterministic loop runs continuously, AI reviews quarterly** → Sakana AI's
   "AI Scientist" (v2, Nature-published Mar 2026) is the closest STRUCTURAL analog anywhere found
   — an agentic system that runs "generate hypothesis → run experiment → measure → refine" as a
   genuinely closed, self-improving loop — but for **automated scientific research**, not
   marketing/advertising, and it re-invokes the LLM every cycle (expensive, non-deterministic)
   rather than seeding once and running deterministic statistics after, which is the opposite of
   what the founder wants (cheap, auditable, AI-light). The formal control-theory ancestor of "a
   perpetual monitor→analyze→plan→execute loop over a persistent knowledge store" is IBM's
   **MAPE-K autonomic-computing loop** (Kephart & Chess, ~2003) — a genuinely on-point 20+-year-old
   academic framework (Monitor/Analyze/Plan/Execute over a shared Knowledge base) that nobody
   appears to have applied to marketing-test prioritization specifically, but which is exactly the
   right shape for "deterministic loop, AI touches it rarely."

### The honest gap
The founder's idea is not "already invented and he doesn't know it" — it's closer to **"every
ingredient already exists in a cookbook nobody has combined."** The one component genuinely absent
from ALL literature surveyed — commercial, trade-press, and academic — is the specific combination
of **(a tree/graph structure) + (staleness-timestamp-driven automatic re-ordering) + (perpetual
retesting of settled nodes)** as a single running system. Every experimentation platform found
(Eppo, GrowthBook, Statsig, Netflix XP) treats "done" experiments as a closed, searchable archive to
learn from, never as a live node that gets automatically re-opened by a clock. That silence across
so many well-documented platforms is itself a data point: either nobody has needed it (most of
these companies have EITHER enough volume to just keep testing everything continuously (Amazon,
Booking, Netflix — they don't need a staleness trigger because they never stopped testing in the
first place) OR so little that a formal graph is overkill for a human PM to manage by hand),
or it's harder to get right than it sounds (a wrongly-tuned decay function reopens settled
questions before they're actually stale, burning exactly the tiny budget Taqinor can't spare).

---

## Brutal honesty section (explicitly requested)

1. **The bandit/allocation half of the founder's idea is not novel — it is table stakes.**
   Thompson Sampling for creative rotation is what Stitch Fix, GrowthBook, and (per the
   already-committed `dd-science-core.md`) Taqinor's own spec all converge on independently. If the
   founder believes the bandit itself is the innovation, that part is solved, well-understood,
   ~40 lines of code (already scoped) — the innovation claim has to rest entirely on the
   tree/staleness/perpetual-retest layer sitting on top of it.

2. **The volume math from `dd-science-core.md` does not go away because the plan is a tree.**
   Restructuring the SAME 11.5 qualified-leads/week and 3-signatures/month into a fancier data
   structure does not manufacture more statistical power. A tree with staleness-driven
   re-prioritization will spend its scarce "test slots" (already MDE-constrained to big, coarse,
   top-funnel swings per the existing dossier) choosing WHICH assumption to re-test, but it cannot
   make the money-rung tests (qualified-lead rate, signature rate) any more testable than they
   already are — they remain Poisson-noise-dominated regardless of how prettily the plan is
   modeled. **The tree is a prioritization/bookkeeping layer, not a statistics-power layer** — it
   should be scoped and sold to the founder as exactly that, not as a way around the MDE ceiling.

3. **Perpetual re-testing of "long-validated" assumptions is the part most likely to actively
   hurt Taqinor specifically**, for a reason unique to this account: at ~$10/day and 2-4 arms max
   (per `dd-science-core.md` §2.2), EVERY test slot spent re-confirming something already settled
   is a test slot NOT spent exploring a genuinely new hook/angle/audience — and the account has
   enough live budget for roughly one meaningful new test track at a time (§4's own 26-week,
   5-phase flight plan). A "perpetually retest everything, seasons change" policy, applied naively,
   competes directly with Phase 1-4's forward progress through hook→format→angle→audience. No
   precedent found anywhere (Amazon, Booking, Netflix included) perpetually re-tests SETTLED
   questions at a volume this low — those companies can afford to because they have effectively
   unlimited traffic; Taqinor cannot, and this is the single biggest place the founder's idea
   should be tightened before it's built: retesting cadence for "settled" nodes needs to be
   explicitly budget-gated (e.g., only after the active exploration queue is empty), not a
   parallel perpetual process, or it will silently starve the exploration the account actually
   needs.

4. **"AI seeds the tree once, then deterministic forever, AI revisits quarterly" is sound and
   matches how the trade press says autonomous ad tools actually fail** (silent drift, per the
   Madgicx finding in `dd-guardian.md` and the AdExchanger/eMarketer audit above) — this part of
   the design is genuinely well-calibrated to the failure mode real practitioners report, and nobody
   should talk the founder out of it.

5. **If the founder wants to claim a real, defensible "first," it is not "autonomous ad testing"**
   (Albert.ai owned that framing in 2010 and it didn't produce lasting independent scale) **— it is
   "a marketing test backlog modeled and automatically maintained as a staleness-aware influence
   diagram / decision network, at SMB budget."** That specific framing appears genuinely absent from
   the market this research could find. Whether it is absent because it's a good unclaimed idea or
   because it is harder to make work reliably than it sounds (Meta itself, with Ax sitting right
   there, never pointed it at ads) is the open question this dossier cannot resolve from documents
   alone — only building a minimal version and watching whether the staleness/retest layer earns
   its keep against the MDE ceiling will answer it.

---

## Sources

Primary (fetched directly, quoted):
- [Ax: Adaptive Experimentation Platform](https://ax.dev/) — Meta, OSS platform overview
- [Efficient Optimization With Ax — Meta Engineering blog](https://engineering.fb.com/2025/11/18/open-source/efficient-optimization-ax-open-platform-adaptive-experimentation/) (18 Nov 2025)
- [Eppo Knowledge Base docs](https://docs.geteppo.com/experiment-analysis/reporting/knowledge-base/)
- [ICE/PIE/PXL test-prioritization comparison — mida.so](https://www.mida.so/blog/test-prioritization-frameworks-ice-pie-pxl)
- [Stitch Fix — Multi-Armed Bandits and the Stitch Fix Experimentation Platform](https://multithreaded.stitchfix.com/blog/2020/08/05/bandits/) (5 Aug 2020)
- [Sakana AI — The AI Scientist](https://sakana.ai/ai-scientist/)
- [Influence diagram — Wikipedia](https://en.wikipedia.org/wiki/Influence_diagram)
- [Stanford — Ross Shachter, "Model Building with Belief Networks and Influence Diagrams"](https://stanford.edu/~shachter/pubs/AdvancesDraft.pdf)

Independent / named secondary (trade press, official vendor docs not directly re-quotable,
company-profile aggregators cross-checked across 2-3 independent databases):
- Zoomd Technologies — [Acquisition of Albert announcement](https://zoomd.com/the-acquisition-of-albert/) (27 Mar 2022)
- Crunchbase / PitchBook / CB Insights / Tracxn — Albert Technologies / Adgorithms company profiles (funding figures inconsistent across sources, flagged)
- [Albert AI review — agentaya.com](https://agentaya.com/ai-review/albert-ai/)
- [Smartly.io — Predictive Budget Allocation / Triggers product pages](https://www.smartly.io/product-features/triggers)
- AdExchanger — "Self-Driving Advertising Is A Myth: Why Automation Can't Replace Creative Judgment"
- eMarketer — "FAQ on AI media buying: Platform tools, agency strategy, and how to win in 2026"
- Harvard Business Review (2017) — "The Surprising Power of Online Experiments" (Amazon Weblab figures)
- Amazon Science — "Top Challenges from the first Practical Online Controlled Experiments Summit" (PDF)
- Booking.ai (Booking.com's own tech blog) — Edgar Cano, "Scaling Experimentation Quality at Booking.com" (Mar 2026)
- Kaufman & Pitchforth, "Democratizing online controlled experiments at Booking.com" (KDD 2017) — listing corroborated via ResearchGate/Semantic Scholar
- Netflix TechBlog — multiple posts, "It's All A/Bout Testing," "Reimagining Experimentation Analysis at Netflix," "Netflix: A Culture of Learning"
- GrowthBook docs — [Insights / Metric Effects / Learnings](https://docs.growthbook.io/insights)
- growthmethod.com — ICE/RICE/PIE/PXL framework comparison
- Strategyzer — [How Assumptions Mapping Can Focus Your Teams On Running Experiments That Matter](https://www.strategyzer.com/library/how-assumptions-mapping-can-focus-your-teams-on-running-experiments-that-matter); Testing Business Ideas (Bland & Osterwalder, Wiley, 2019)
- Jin, Wang, Sun, Chan & Koehler — "Geo-level Bayesian Hierarchical Media Mix Modeling" (Google Research, 2017) — [research.google listing](https://research.google/pubs/geo-level-bayesian-hierarchical-media-mix-modeling/)
- Kephart & Chess — IBM autonomic computing / MAPE-K loop (foundational ~2003 concept), corroborated via multiple academic surveys (Springer, arXiv) citing the original IBM framing

Repo context read (not re-derived, per mission instructions):
- `docs/engine/research/dd-science-core.md` — MDE/bandit math, volume reality
- `docs/engine/research/dd-meta-mechanics.md` — Meta API/learning-phase mechanics
- `docs/engine/research/dd-guardian.md` — guardrail/alerting design, Madgicx silent-failure finding
