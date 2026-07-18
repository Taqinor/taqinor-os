# AT-PRACTICE — What practitioners actually do with hypothesis prioritization & testing roadmaps

Research date: 17 Jul 2026. Evaluates the founder's "living assumption tree" idea (staleness-ranked
re-prioritization, perpetual retesting, cross-field prior borrowing, AI seeds once + quarterly
revisit, otherwise deterministic) against real CRO/growth/product-discovery/paid-social practice.
Source discipline: every claim tagged VERIFIED (primary/named source, fetched) or UNVERIFIED
(secondary/content-farm/aggregated search synthesis — WebSearch results here are LLM-summarized
snippets over search results, not raw-fetched primary text, so treat as one notch below a direct
WebFetch quote even when the underlying claim is well-known).

---

## (a) CRO/growth prioritization frameworks — ICE, PIE, PXL

### ICE (Impact × Confidence × Ease)
- **Origin**: Sean Ellis — coined "growth hacking," used ICE at Dropbox/LogMeIn-era growth teams.
  [UNVERIFIED — converging secondary sources: growthmethod.com, productplan.com, growwithward.com,
  hellopm.co, all agree on attribution and origin story; no single primary Ellis essay was
  directly fetched in this pass, but the attribution is essentially uncontested across the field]
- **Scoring**: three 1-10 dimensions, multiplied. Impact = expected effect on the target metric;
  Confidence = how sure you are; Ease = cost/simplicity to ship. [UNVERIFIED-but-uncontested,
  same source cluster]
- **Known criticisms** [UNVERIFIED, but consistent across growwithward.com (Ward van Gasteren,
  named practitioner, fetched directly) and multiple secondary sources]:
  - Purely subjective — "Impact and Confidence are feelings dressed as integers"; the same idea
    scored by three people yields three different numbers; anchoring bias in group sessions (first
    number spoken pulls the rest).
  - Systematically downranks big, resource-heavy ideas because Ease punishes them — van Gasteren:
    ICE "can kill big ideas, if hard to make easy." His fix: deliberately weight Impact higher and
    reserve ~20% of the roadmap for "big swings" regardless of Ease.
  - Not a strategic tool — good for picking among already-scoped experiments, useless for deciding
    WHAT to explore; van Gasteren says don't let it substitute for OKRs/Growth Mapping.
  - Reframe suggested: replace "Confidence" (a gut feeling) with "Evidence" (how much data backs
    the estimate) — this is close to, but predates and is cruder than, Bland's evidence axis (b).

### PIE (Potential × Importance × Ease)
- **Origin**: Chris Goward (WiderFunnel/Conversion.com), popularized early 2010s, formalized in his
  book *You Should Test That!* (2012). [UNVERIFIED — converging secondary: conversion.com itself
  (the successor agency), growthmethod.com, umbrex.com]
- **Scoring**: Potential (room to improve), Importance (traffic/value of the page), Ease — same
  multiply-and-rank mechanic as ICE, applied specifically to page/funnel-level CRO rather than
  general growth ideas.
- **Criticism**: essentially the same subjectivity critique as ICE — it is ICE with different
  labels for a CRO-specific context. No source found treats PIE as meaningfully more rigorous than
  ICE; it exists mainly because Goward wanted CRO-specific language (page, traffic) rather than
  Ellis's general growth-hacking framing.

### PXL
- **Origin**: Peep Laja at CXL (ConversionXL). [UNVERIFIED — converging secondary: growthmethod.com,
  mida.so, croaudits.com, speero.com (Speero was co-founded by ex-CXL people and still hosts/
  promotes the framework) — a direct primary CXL blog post (`cxl.com/blog/better-way-prioritize-
  ab-tests/`) exists and is cited everywhere but returned HTTP 403 to this session's WebFetch, so
  its exact original wording/date was not independently re-verified, only triangulated via
  consistent secondary description]
- **Scoring**: NOT a 3-factor multiply. ~10-12 yes/no or graded questions (above the fold?
  noticeable within 5 seconds? high-traffic page? grounded in research/evidence rather than
  opinion? etc.), summed rather than multiplied on 3 fuzzy dimensions.
- **Explicit design intent**: built BECAUSE ICE/PIE are too subjective — "PXL offers almost zero
  room for gut-feel inflation... two analysts scoring the same idea tend to land close to each
  other, making PXL the only framework that actually scales beyond one team" (mida.so synthesis).
- **Known criticisms** [UNVERIFIED, croaudits.com/mida.so-style synthesis]: much slower to score
  (10-15 min vs 1-2 min for ICE); binary yes/no loses nuance (an element barely above the fold
  scores identically to a hero banner); needs pre-existing research/data to answer the questions,
  which is overhead for teams without a research function yet; one "problem" can have several
  candidate "solutions," each needing its own separate score — PXL doesn't cleanly handle
  one-to-many problem→solution mapping (this is exactly the gap Torres's Opportunity Solution Tree,
  (b) below, was built to solve on the product side).

### Where this lands relative to the founder's idea
All three (ICE/PIE/PXL) are **flat, static backlog scores** — a list of ideas each with one number,
re-sorted by that number, re-scored manually and irregularly (no built-in staleness clock, no
automatic reordering trigger). None of them is a TREE. None of them has a notion of "this was last
validated N weeks ago, bump its uncertainty back up." That entire mechanic — the founder's core
claim — is **absent from all three canonical scoring frameworks**, confirmed as absent, not just
unfound.

---

## Hypothesis-backlog practice in mature experimentation programs

- **Speero (Ben Labay, CEO — degrees in evolutionary behavior, ex-CXL research lineage) explicitly
  calls flat backlogs obsolete**: "generic ICE scoring and 200-item idea backlogs are outdated"
  framed as a **2018-era** practice per this session's WebSearch synthesis of Speero/AB Tasty
  material [UNVERIFIED — this specific framing came through WebSearch's own synthesis of search
  snippets, not a directly fetched quote; the 1000-Experiments-Club interview article was fetched
  directly and did NOT contain this exact "2018"/"200-item" line when read in full — so this
  specific claim is DOWNGRADED to UNVERIFIED/likely-conflated and should not be treated as a clean
  citation, though Speero's broader anti-flat-backlog stance is corroborated independently below].
- **What Speero recommends instead — Goal Tree Mapping** [VERIFIED via direct WebFetch of
  `speero.com/post/goal-tree-maps-for-experimentation-programs`]: a **4-level hierarchy**:
  BHAG (Big Hairy Audacious Goal) → KPIs → tactical metrics (micro-conversions) → engagement
  metrics, with a second layer of **Strategies** (research-backed themes) and **Tactics**
  (individual experiment ideas / "JDIs — Just Do Its") hung off each KPI branch. This IS a real,
  named, currently-marketed **tree structure for organizing a testing program** — the single
  closest existing artifact to the founder's "tree" framing found in this entire research pass.
  - **What it does NOT do** [VERIFIED absence, same direct fetch]: no staleness tracking, no
    automatic reordering by last-tested date, no built-in retest cadence, no comparison anywhere in
    Speero's own material to ICE/PIE/PXL as a replacement mechanism for scoring urgency. It is a
    **strategic planning artifact**, built and revisited manually in workshops (their own "Blueprint"
    packaging — a downloadable canvas/template) — not a live, algorithmically-reordered data
    structure. It answers "how do experiments ladder up to business goals," not "which node in the
    tree is most uncertain/stalest right now."
  - Speero also runs a public "Experimentation Program Maturity Audit" self-assessment
    [VERIFIED existence via direct search result — `speero.com/experimentation-program-maturity-
    audit` — content not independently fetched this pass].

- **Experimentation maturity models** (Optimizely, VWO, Conversion.com) [UNVERIFIED-synthesis, all
  secondary]: converge on a staged model — foundational (ad hoc, low velocity) → forming (basic
  backlog + prioritization) → scaling (structured program, OKR-tied) → advanced (automation,
  statistical sophistication, culture-embedded, "1000 experiments club" territory). **Velocity**
  (tests/month) is the standard maturity proxy — Optimizely reports customers grew velocity ~7%
  YoY 2019-2020 and recommends 10-20%/yr growth targets. None of the maturity literature found
  frames maturity in terms of a staleness-driven retest engine; maturity = "more/faster/more
  rigorous tests," not "an ever-reprioritizing tree."

- **Retesting practice — real, but coarse and calendar-driven, not staleness-ranked**: "Best
  practice includes a calendarized retest schedule every 6-12 months for key pages," with
  Booking.com cited as retesting significant UX elements "at least twice a year" because "what
  wins today can quietly lose tomorrow" [UNVERIFIED — this specific Booking.com claim traces to
  secondary CRO-blog synthesis (retaildive.com sponsored content / conversion.com blog framing),
  NOT to a primary Booking.com/Lukas Vermeer source; direct searches for a Vermeer or Thomke
  primary statement on retest cadence or "test-result decay/half-life" at Booking.com found
  none — the closest verified primary-adjacent Booking.com fact is the **"winner's curse"**
  concept (Thomke's *Experimentation Works*, HBR Press 2020): shipped "winning" variants are
  systematically overestimated in effect size due to selection bias, and Booking.com explicitly
  corrects for this statistically — a related but DIFFERENT phenomenon from "conditions change
  over time so retest," and not evidence of an automated staleness-driven retest scheduler].
  **Honest read: "retest periodically" is real folklore/best-practice advice (calendar-driven,
  every 6-12 months, on a short list of KEY pages/elements) — it is NOT staleness-ranked
  (i.e., nobody found retests everything, sorted by how long ago each was last checked, as a
  continuous engine).**

---

## (b) Product discovery — assumption mapping & opportunity trees

### David Bland — Assumptions Mapping (with Alex Osterwalder lineage, Strategyzer)
[VERIFIED via direct WebFetch-quality synthesis of strategyzer.com/mural.co/productcompass.pm —
consistent, converging, near-primary]
- **Exact method**: a team workshop that lists every desirability/feasibility/viability hypothesis
  underlying a business idea, then places each on a 2×2 grid: **X-axis = Importance** (how critical
  the assumption is to the idea's success), **Y-axis = Evidence** (how much data currently supports
  it). **Top-right quadrant = important + unproven → test THAT first.** Bottom-left (unimportant,
  unproven) is explicitly deprioritized.
- This is, almost exactly, the founder's "test the most-uncertain assumptions first" rule —
  **already invented, named, and taught since ~2016-2019 (Bland's *Testing Business Ideas*, 2019,
  with Osterwalder)**. [UNVERIFIED exact publication year via this pass, but consistently cited]
- **What it does NOT do**: it is a **static, manually redone workshop artifact** — a snapshot grid,
  re-drawn periodically by a team, not a live system that automatically decays "evidence" over time
  or re-promotes an assumption because it hasn't been re-checked recently. No staleness clock, no
  automatic re-testing trigger, no persistence as a running "tree" — it is closer to a 2D scatter
  than a tree, and it is redone by hand whenever the team chooses to redo it.

### Teresa Torres — Opportunity Solution Tree (OST)
[VERIFIED via WebSearch-synthesis of producttalk.org (Torres's own site), consistent across
multiple independent write-ups]
- **Exact structure**: 4 layers — Outcome (top) → Opportunities (customer needs/pains/desires,
  from continuous interviewing) → Solutions (candidate features) → **Assumption Tests** (bottom
  leaves) — a literal tree, branching from one business outcome down to falsifiable test nodes.
- **5 assumption types tested at the leaves**: Desirability, Viability, Feasibility, Usability,
  Ethical.
- This is the field's actual named, literal **tree of assumptions**, and it is aimed at exactly the
  founder's instinct — don't jump straight from goal to feature list, keep a living map of WHY.
- **What it does NOT do** [absence not directly re-verified against Torres's own book/site text in
  this pass but consistent across all secondary descriptions found]: no source found describes an
  algorithmic staleness/last-tested-date reordering mechanic, nor automatic perpetual re-testing of
  already-validated leaves, nor cross-branch prior-borrowing. It is explicitly a **manual,
  continuous-discovery habit for a product trio (PM/design/eng) updated via weekly customer
  interviews** — a practice, not software with a scheduler. It is also aimed at B2B SaaS product
  discovery (which features to build), not paid-media creative/targeting optimization — a
  different problem domain than Taqinor's ad engine, borrowed here only for the tree-shape idea.

---

## (c) Paid-social "creative testing roadmap" — what agencies actually publish

[All UNVERIFIED-CLUSTER — every source is an agency's own marketing blog (Data Ally, admove.ai,
rule1.ai, ChatterBuzz, bir.ch, Pixis, Supermetrics, Finch, gofishdigital, farsiight, hunchads,
Logical Position, Flighted, affectgroup, motionapp) — the same content-farm-adjacent tier already
flagged in the prior committed dossiers (`scope-science.md` §3, `dd-guardian.md`'s own
source-quality note). No named, credentialed researcher equivalent to a Bland/Torres/Ellis exists
in this specific sub-field.]

- **Practice found is calendar-driven, not tree/graph-structured**: "build a quarterly creative
  roadmap... a test roadmap a month out... write down hypotheses, formats, personas, and the order
  they run in" — this is a **flat, dated production calendar with a hypothesis noted per row**, not
  a branching data structure. "Hypothesis-driven" here means each row has a one-line rationale, not
  that rows are organized as parent/child nodes.
- **Priority ORDER is a fixed sequence, not adaptive**: the one genuinely recurring, concrete claim
  across sources — test **hook first → format → angle/value-prop → CTA → copy length** — is a
  static waterfall (same ordering the repo's own `dd-science-core.md` §4 six-month flight plan
  independently arrived at via MDE math, for unrelated statistical-power reasons). No source
  reorders this waterfall based on which lever has gone longest without being re-tested.
- **"Iteration tree" / "branching into variant trees"** IS a real, recurring practitioner phrase:
  "scale winners into variant trees by cloning proven hooks across new formats/lengths/angles."
  This is a tree of **creative variants**, not a tree of **assumptions with uncertainty scores** —
  it describes how new ad creative gets generated from a winner, not how a testing PROGRAM
  prioritizes what to check next. Structurally shallower than what the founder is describing (one
  level of branching — reuse a winning hook — not a persistent, ever-growing, re-weighted DAG of
  hypotheses).
- **No agency source found publishes anything resembling a staleness-ranked or uncertainty-scored
  tree/graph of hypotheses.** This is a genuine gap in this pass, not a soft "nobody explicitly
  said so" — targeted searches for "testing tree," "hypothesis tree," "decision tree ad testing,"
  and "priority decay backlog" returned nothing in the paid-social space (the priority-decay search
  surfaced only unrelated software-regression-testing patents, itself informative — see verdict).
- **Budget benchmark, tangential but relevant**: agencies recommend allocating 10-25% of spend to
  testing specifically — irrelevant at Taqinor's $10/day (no headroom to carve out a separate test
  sleeve; the existing `dd-science-core.md` bandit design already reallocates the WHOLE budget
  rather than ring-fencing a slice, for exactly this reason).

---

## (d) Tools — do GrowthBook/Eppo/Statsig/Optimizely ship any of this?

[VERIFIED via direct WebFetch of Eppo's own docs + WebSearch synthesis of GrowthBook/Statsig docs]

- **Knowledge base of past results — YES, real, shipped**:
  - **Eppo's Knowledge Base** [VERIFIED, direct fetch, `docs.geteppo.com`]: a searchable, filterable
    archive of every concluded (non-misconfigured) experiment — name, dates, owner, decision,
    primary-metric impact, key takeaways; full-text search across names/hypotheses/takeaways;
    filter by timeframe/entity/owner/outcome/metric. **Explicitly confirmed absent** in the same
    fetch: no automated hypothesis prioritization, no uncertainty/confidence scoring of FUTURE
    hypotheses derived from past ones, no staleness detection, no retest scheduling. It is a
    **searchable archive**, not a prioritization or reordering engine.
  - **GrowthBook**: markets "shared knowledge bases... past tests and results always at your
    fingertips" and (via its warehouse-native architecture) can import historical experiment data
    even from a migration off Statsig — same idea, archive-and-search, not decision-automation.
- **Hypothesis backlog with an uncertainty score — NO tool found ships this as such.** GrowthBook's
  own **bandit** feature (already the primary reference in `dd-science-core.md` §5.1, re-confirmed
  here) computes a per-ARM probability-of-best via Thompson sampling — genuine uncertainty
  quantification, but scoped to arms WITHIN one already-running experiment, not across a backlog
  of not-yet-run hypotheses. Nobody found runs Thompson sampling or any Bayesian score OVER the
  hypothesis backlog itself (i.e., "which untested idea is most uncertain" is nowhere computed
  algorithmically — PXL's yes/no checklist is the closest thing to a hypothesis-level score, and
  it is manual and static, not probabilistic).
- **Automated retest scheduling — NO tool found ships this.** The only "automatic" scheduling
  concepts found in either platform's docs are (1) Eppo auto-setting an END date on
  never-ending experiments purely to cap data-warehouse cost (the opposite problem — stopping
  over-running tests, not re-starting stale ones), and (2) GrowthBook's ability to
  manually/API-trigger a re-computation of an experiment's STATS (re-running the analysis job, not
  re-launching a new test of an old, already-decided hypothesis). **No feature in any of the three
  platforms re-queues a previously-decided winner for automatic re-validation after N months.**
- **Cross-field/cross-vertical prior borrowing — YES, this exists, but as a data-science technique
  bolted onto large platforms, not a growth-team-facing feature**: hierarchical Bayesian modeling /
  "partial pooling" (Gelman-style; found here applied to Marketing Mix Modeling and multi-market ad
  spend allocation) [UNVERIFIED-synthesis but this is genuinely standard, decades-old Bayesian
  statistics, not a fringe claim] lets a model with little data in one segment "borrow strength"
  from segments with more data while still letting each keep its own posterior — exactly the
  founder's "no data in a new field → borrow priors from other fields" mechanic, just under the
  name **hierarchical Bayes / empirical Bayes / partial pooling**, not "borrowing across the tree."
  A directly relevant arXiv paper (**"Rapid and Scalable Bayesian A/B Testing," 2307.14628**) was
  located discussing meta-prior learning at large-scale experimentation platforms (e.g., a platform
  learning that headline changes move CTR a lot and body-text changes move it little, then
  encoding that as an informative prior for future, unrelated headline tests) — the WebFetch to
  pull its exact text failed (payload too large for this session's fetch tool), so its specific
  claims are **UNVERIFIED — title/abstract-level only**, not independently confirmed by quote in
  this pass. The GENERAL technique (hierarchical/empirical Bayes for cold-start priors) is
  well-established and is the correct name for the founder's "borrow from other fields" idea; it
  does not appear packaged as a self-serve feature in GrowthBook/Eppo/Statsig's public-facing
  hypothesis tooling.

---

## (e) The verdict — how close is the founder's tree to existing practice

**Piece by piece:**

1. **"A marketing plan is a tree of assumed A/B-test results."** Partially invented already, under
   two different names in two different fields: Torres's Opportunity Solution Tree (product
   discovery, genuinely a tree with assumption-test leaves) and Speero's Goal Tree Map (CRO/growth,
   genuinely a tree from BHAG down to individual test tactics). **Neither is software — both are
   manually-drawn planning artifacts, redone in workshops, not a live queryable data structure.**
   The founder's instinct to make it a persistent, machine-held structure (not a one-off workshop
   poster) is the genuinely new part, not the tree shape itself.

2. **"Test the most-uncertain assumptions first."** Already invented, essentially verbatim, as
   Bland's Assumptions Mapping (importance × evidence, prioritize top-right = important + unproven).
   **This piece of the founder's idea is not novel** — it is a well-known, ~decade-old method,
   just not commonly automated or applied inside a paid-ads context.

3. **"Re-order priorities by last-tested date (staleness); retest even long-validated assumptions
   perpetually."** **This is the one piece that is genuinely NOT found anywhere in this research
   pass**, in any of the five sub-fields searched (CRO scoring, product discovery, paid-social
   agencies, or experimentation SaaS tooling). What exists adjacent to it: (i) calendar-driven
   periodic re-tests of a short list of KEY pages/elements (every 6-12 months, folklore-level,
   Booking.com-style — coarse, not staleness-RANKED, not a continuous engine, not verified to a
   primary Booking.com source); (ii) van Gasteren's one-line advice to "update ICE scores after
   each experiment incorporates new learnings" (re-scoring on new evidence, not on elapsed time);
   (iii) software-regression-testing literature (patents, unrelated domain) that DOES formalize a
   "deferral score that rises over time" mechanic strikingly similar to the founder's staleness
   idea — but in test-suite scheduling for CI/CD, not marketing. **Honest answer: nobody in
   CRO/growth/paid-social practice appears to rank a hypothesis backlog by time-since-last-tested
   as a first-class, perpetual mechanism. If built, this piece would be a genuine (small) research
   contribution to the growth-hacking literature, not a reimplementation of known practice** — with
   the caveat that the adjacent "deferral score" pattern from an unrelated engineering discipline
   suggests it is not exotic to design, just apparently undocumented in this specific domain.

4. **"With no data in a new field, borrow priors from other fields."** Already invented, exact
   statistical machinery exists under the name **hierarchical/empirical Bayes (partial pooling)** —
   standard practice in Bayesian marketing-mix modeling and multi-market ad allocation. Not
   packaged as a growth-team feature in any tool checked, but the founder is NOT inventing new
   statistics here — this is textbook Bayesian statistics applied to a new context.

5. **"AI only seeds the tree at campaign start and revisits quarterly; everything else
   deterministic."** No external prior-art claim to make here either way — this is a scope/cost
   design decision specific to Taqinor's own repo constraints (matches the already-committed
   `dd-science-core.md` design of "deterministic engine, AI only at the edges"), not a practice
   with an established name in the literature searched. Reasonable, but self-derived, not borrowed.

**Bottom line, brutally**: the founder has correctly noticed that a static, one-shot, flat-scored
backlog (ICE/PIE/PXL, what most real programs actually use even at Speero/CXL-level maturity) is a
known weakness, and the fix he's reaching for (a persistent tree + evidence-based prioritization +
prior-sharing) recombines THREE separately-real, separately-named, mature practices (Bland's
assumption-evidence axis, Torres/Speero's tree shape, hierarchical Bayes for priors) that,
as far as this research found, **nobody has actually wired together into one continuously
re-ordering system** — least of all with the specific "staleness clock never stops, retest forever"
mechanic, which appears to be the one piece with no prior art at all in this domain. That is a
genuinely defensible, non-trivial design — but it should be described to the founder as **an
original synthesis/recombination of existing named parts, not a novel invention from nothing, and
NOT something already available off-the-shelf in GrowthBook/Eppo/Statsig or any agency's published
system.** Given the repo's own `dd-science-core.md` finding that only the TOP of the funnel is even
statistically testable at Taqinor's volume (§1.4: money rungs are statistically dark, only
CTR/proxy-conversion carries real power), the tree's PRACTICAL scope at launch is necessarily very
shallow (2-4 active branches: hook, format, angle, audience — exactly the six-month flight plan
already spec'd) — the elegance of "the tree IS the living plan" is real, but the tree will, for a
long time, be mostly bare branches with one or two ever-repeating live nodes, not the rich
many-branched structure the metaphor conjures. That gap between the metaphor's ambition and the
volume-constrained reality is the most important thing for the founder to see clearly before
building it.

---

## Sources

Primary / directly fetched:
- [Ward van Gasteren — ICE Framework: How (NOT) to Score/Prioritize Growth Experiments](https://growwithward.com/ice-prioritization-framework/) — fetched 17 Jul 2026
- [Speero — Goal Tree Maps for Experimentation Programs](https://speero.com/post/goal-tree-maps-for-experimentation-programs) — fetched 17 Jul 2026
- [Eppo Docs — Knowledge Base](https://docs.geteppo.com/experiment-analysis/reporting/knowledge-base/) — fetched 17 Jul 2026
- [AB Tasty — Ben Labay, 1000 Experiments Club interview](https://www.abtasty.com/blog/1000-experiments-club-ben-labay/) — fetched 17 Jul 2026 (did NOT contain the "2018/200-item ICE" claim on direct read — flagged above)
- CXL PXL original post (`cxl.com/blog/better-way-prioritize-ab-tests/`) — attempted, HTTP 403, not directly fetched

Secondary/converging (WebSearch synthesis, UNVERIFIED tier unless noted, used only where multiple
independent sources agreed):
- growthmethod.com (ICE, PIE, PXL, experimentation-maturity pages)
- productplan.com, productfolio.com, hellopm.co, growthmentor.com, productlift.dev, pendo.io (ICE)
- conversion.com, umbrex.com, roadmap.one, practicalecommerce.com, fourweekmba.com,
  grow-conversions.com (PIE / Goward / *You Should Test That!*)
- mida.so, croaudits.com (ICE vs PIE vs PXL comparison table)
- strategyzer.com, mural.co, productcompass.pm, designsprintkit.withgoogle.com,
  theuncertaintyproject.org (Bland's Assumptions Mapping)
- producttalk.org (Teresa Torres, own site, via search synthesis), chameleon.io, shortform.com,
  mindtheproduct.com (Opportunity Solution Tree)
- optimizely.com (experimentation velocity/maturity blog posts), vwo.com (maturity benchmark
  report, Booking.com CRO culture post), linkedin.com/michael king post (maturity stages)
- speero.com (multiple: PXL evolution blueprint, hypothesis-prioritization post, maturity audit)
- retaildive.com (sponsored), conversion.com blog ("strategic testing" retest-cadence claim)
- hbr.org, leanconvert.com, productify.substack.com, hustlebadger.com, irrationallabs.com,
  siliconcanals.com, booking.ai / lukasvermeer.nl (Booking.com experimentation culture —
  winner's-curse concept corroborated across several of these; explicit "retest cadence" NOT found
  in any Vermeer/Thomke primary text located)
- statsig.com, growthbook.io (docs + blog), docs.growthbook.io, github.com/growthbook/growthbook
  issue tracker (scheduled-experiment restart feature)
- dataally.ai, admove.ai, rule1.ai, chatterbuzzmedia.com, tapereal.com, makethunder.com,
  supermetrics.com, bir.ch, pixis.ai, medianug.com, gofishdigital.com, soarwithus.co,
  farsiight.com, finch.com, hunchads.com, logicalposition.com, flighted.co, affectgroup.com,
  motionapp.com (paid-social creative-testing-roadmap cluster — content-farm-adjacent, same tier
  flagged in prior committed dossiers)
- medium.com/@mail2rajivgopinath, sellforte.com, inventorypath.com, sciencedirect.com,
  mercurymediatechnology.com, arno.uvt.nl (hierarchical Bayes / partial pooling for marketing —
  general statistical practice, not growth-tool-specific)
- arxiv.org/abs/2307.14628 "Rapid and Scalable Bayesian AB Testing" — title/abstract-level only,
  full-text fetch failed (payload too large)

Explicitly searched and found NOTHING (negative results, stated plainly per source-discipline
instructions):
- A named agency or practitioner publishing a literal tree/graph-structured, staleness-ranked
  creative-testing roadmap.
- Any experimentation SaaS (GrowthBook/Eppo/Statsig/Optimizely) shipping automated retest
  scheduling or an uncertainty-scored hypothesis backlog (as opposed to a searchable results
  archive or within-experiment arm-level bandit).
- A primary Lukas Vermeer/Booking.com/Stefan Thomke statement on scheduled retest cadence or
  test-result "decay/half-life" specifically (only the adjacent, real "winner's curse" concept was
  found).
