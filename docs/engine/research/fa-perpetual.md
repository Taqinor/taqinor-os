# THE PERPETUAL CAMPAIGN — does it exist, for whom, how long?

Research date: 18 Jul 2026 (today per session; searches reflect a "current" web dated up to Jul
2026, itself a mix of real and LLM-hallucination-prone future-dated blog content — treated with
extra skepticism, see caveats inline). Builds on `docs/engine/research/dd-meta-mechanics.md`
(learning-phase reset mechanics, Andromeda touch on that) and `dd-science-core.md` (low-volume MDE
math, why Taqinor is capped at 2-4 creative arms) — not re-derived here, only cross-referenced.

**Tooling caveat inherited from dd-meta-mechanics.md, reconfirmed this pass**: Meta's own
`facebook.com/business/help/*` Help Center pages remain unfetchable as real text (WebFetch gets
only the page title — JS-rendered client-side content). Meta's own Newsroom (`about.fb.com`) pages
per **do** return real text — used directly where found. Net effect: every claim about Meta's
*current, exact* published wording on "always-on" is flagged UNVERIFIED for that specific reason,
even though the underlying concept is extremely well attested by converging secondary sources and
by Meta's own product behavior (Advantage+ defaults, Performance 5 Blueprint course).

---

## TL;DR — decision-relevant conclusions

1. **[VERIFIED]** Meta's own official structural doctrine (Performance-5 / Blueprint framework,
   reinforced by the 2024-2025 Andromeda ad-ranking rollout) is explicitly **fewer, longer-lived,
   consolidated campaigns** — "account simplification" is the *first* of Meta's five named
   Performance-5 pillars, and Andromeda's own economics (an ad set needs ~50 optimization events/wk
   to exit the learning phase) mathematically punish frequent recreation/restructuring. This is
   Meta pushing advertisers *toward* perpetual structures, not away from them.
2. **[UNVERIFIED, but multiply-corroborated]** A single continuously-running Meta campaign/ad set
   for 1-2+ years is a real, attested pattern, not a fantasy: independent ad-library-based case
   studies document commercial ads (e.g. Mejuri, 431 consecutive days = ~14 months) running unbroken
   for over a year; agency/practitioner consensus treats 30-90+ days of continuous run time as a
   *routine* profitability signal, implying much longer runs are unremarkable in the wild.
   Taqinor's own prior competitor forensics found a Tecas ad live since Nov 2024 (20+ months as of
   this writing) — **this specific claim is carried over from prior internal research, not
   independently re-verified this pass** (Meta Ad Library is JS-rendered; WebFetch could not load
   it — see Sources).
3. **[VERIFIED-ish, converging]** Always-on is standard for local/lead-gen SMBs (the category
   Taqinor sits in) almost by category-definition — there is no "season" for a dentist, HVAC
   company, or solar installer the way there is for an ecom product drop. Ecommerce itself is
   converging toward the same always-on-base-layer model (continuous prospecting/retargeting +
   seasonal/launch bursts layered on top), per current agency commentary — meaning **the
   distinction is narrowing, not "perpetual" vs "burst," but "what's the base layer vs what's the
   burst layer" for everyone.**
4. **[UNVERIFIED, industry-consensus]** Nothing in Meta's structure or ad-library data suggests a
   hard ceiling on campaign lifespan. What forces restructuring in practice is **creative fatigue**
   (a rotating **creative** inside a stable campaign wears out every ~2-3 months per multiple
   sources; the **campaign/account architecture** is what should be perpetual, not any one ad) and
   discrete **platform shocks** (iOS14/ATT in April 2021 is the one well-documented, dated,
   industry-wide forced-restructure event — nothing of that magnitude has recurred since; Andromeda
   is a rolling algorithm change, not a single forced-restructure event, though several
   single-source/uncorroborated 2026 blog claims describe a "March 2026" attribution/ranking shift —
   flagged UNVERIFIED, not independently corroborated).
5. **Practical answer for Taqinor** — a genuinely 1-2-year "campaign that never ends" is realistic
   **at the structural level** (one campaign, one ad set, perpetual), but **not** at the individual-
   ad level (creatives inside it must rotate on the cadence `dd-science-core.md` already specifies:
   ~3-4 week test phases, burn-in before kill, 2-4 arms). See §(e) for the concrete architecture.

---

## (a) Always-on vs. burst: how common, Meta's own guidance, typical structure

**Prevalence — always-on is now the default recommended posture, converging across ecom AND
local/service**, not a niche tactic:
- Agency commentary (2026): *"The days of running campaigns 'in season' and going dark the rest of
  the year are over. The brands winning in ecommerce now think in terms of always-on
  infrastructure: a base layer of performance campaigns running continuously, layered with seasonal
  and promotional bursts, layered with product launch and lifecycle campaigns."* [zen.agency,
  fetched 18 Jul 2026 — UNVERIFIED/secondary, single-agency framing, but consistent with every other
  source found this pass] — this is exactly the "evergreen core + seasonal bursts + retargeting
  layers" structure named in the mission brief; it is the converged industry description, not one
  agency's idiosyncratic take.
- **[UNVERIFIED]** *"Instead of planning 'a campaign,' you're maintaining a campaign ecosystem. Your
  creative pipeline is never empty."* — same source, capturing the organizational-mindset shift away
  from discrete campaigns entirely.

**Meta's own published guidance — what I could and couldn't confirm directly:**
- **[VERIFIED]** Meta's **Performance 5** framework (official Blueprint course,
  `facebookblueprint.com/student/path/253157-performance-5` — course description text fetched
  directly) states its five pillars are **"account simplification, automation, creative
  diversification, data quality and results validation"** — account simplification named FIRST and,
  per every secondary source describing the course content in more depth (Tiger Pistol, Overt
  Digital, 2ten Marketing — course lesson content itself is behind a login, so the depth sources are
  secondary), is treated as **foundational**: *"simplifying your account and consolidating ad
  creative in a central campaign enables the campaign to exit the learning phase quicker."*
  [UNVERIFIED for the exact quoted wording — paraphrase from secondary sources describing the
  Blueprint course, not independently fetchable — but converges across three independent
  secondary write-ups, so treated as high-confidence].
- **[VERIFIED]** Reported quantified benefit, same secondary cluster: *"Ad sets with more than 50
  events per week demonstrate a substantial 28% lower cost per purchase; ad sets that successfully
  exit the learning phase show a significant 19% lower CPA."* [tigerpistol.com / overtdigitalmarketing.com.au,
  fetched 18 Jul 2026 — UNVERIFIED primary attribution but Meta-sourced-benchmark framing, consistent
  across both].
- **I could NOT find Meta's own text using the literal phrase "always-on"** despite direct attempts
  (`about.fb.com` full-text fetch of the Aug 2022 Advantage+ Shopping Campaigns launch post
  contains NO instance of "always-on" — checked directly) and several targeted searches
  (`site:about.fb.com "always-on"` returned nothing on-topic). Secondary sources describe
  Advantage+ Shopping/Sales/Leads campaigns as functioning as an *"always-on solution"* but I could
  not trace that exact phrase back to a literal Meta sentence — **flagged UNVERIFIED, a real
  negative finding**, not a confirmed Meta quote. What IS confirmed: Advantage+ is the **default**
  audience/budget/placement mode for Sales, App, and Leads objectives (Meta Business Help Center,
  title/existence confirmed, full text not fetchable), meaning Meta's *product default* is a
  continuously-running, non-expiring automation layer — functionally always-on even if Meta never
  markets it with that exact word.
- Cross-platform corroboration that "always-on" is established *paid-social industry vocabulary*
  (not Meta-specific): LinkedIn Marketing Solutions publishes its own dedicated always-on guide,
  *"Always-On: How to Embrace Evergreen Content"* [linkedin.com/business, PDF located and its
  existence confirmed 18 Jul 2026, though the fetched PDF returned as unreadable binary — its
  *existence* as a named, official platform guide is the useful fact here, not its body text].

**Typical structure (evergreen core + seasonal bursts + retargeting), confirmed converging pattern**:
Every source found this pass — agency commentary, the Performance-5 doctrine, and the Andromeda
consolidation guides in (d) — describes the same layered shape: **one stable, always-funded
prospecting layer** (broad audience, many creatives, CBO or simplified ABO) + **retargeting as a
separate, permanent layer** + **seasonal/launch bursts layered temporarily on top, never replacing
the base**. No source described a mature, well-run account as ALL burst or ALL evergreen — it is
always a base-plus-layers model.

---

## (b) Longevity evidence — how long do real campaigns/ads actually run?

**Documented long-running individual ads** (evidence the "years, unbroken" pattern is real, not
theoretical):
- **[UNVERIFIED-secondary, but directly ad-library-sourced]** A Mejuri (jewelry, ecom DTC) ad —
  copy: "Make your own milestones," two product images, no discount code — has run **431
  consecutive days** (≈14 months) per an ad-library-based case-study breakdown [adkit.so /
  socioh.com, fetched 18 Jul 2026, citing Meta Ad Library "days active" data directly]. This is the
  single most concrete, dated, sourceable "how long" data point found this pass.
- **Taqinor's own prior finding**: a Tecas (Moroccan solar competitor) ad live since Nov 2024
  (20+ months) — **carried over from the mission brief / prior internal competitor forensics, NOT
  independently re-confirmed this pass.** I attempted a direct Meta Ad Library fetch
  (`facebook.com/ads/library/?...q=Tecas...`) — it returned a socket error (the Ad Library is a
  heavy JS SPA, consistent with the known WebFetch limitation on Meta-owned interactive pages). This
  claim should be treated as **[UNVERIFIED this pass]**, standing entirely on the prior internal
  research's credibility, not on anything freshly checked here.
- **Non-Meta but instructive precedent (Kantar, a primary market-research firm, not a content-farm
  blog)**: Twinings' "Tealand" creative *"maintained effectiveness for nearly a decade"* and
  remained "enjoyable and distinctive" with strong brand-equity scores after almost 10 years;
  Marmite's "Love it or hate it" brand asset has anchored different executions since at least 2013
  through 2024 [kantar.com/inspiration/advertising-media/the-art-of-creating-ads-that-last, fetched
  18 Jul 2026 — **[VERIFIED]**, direct fetch, real research-firm content, TV/brand-campaign context
  though, not Meta performance-marketing — flagged as a different genre of "long-running" (brand
  continuity, not identical media buy) but directly relevant to the *concept-can-outlive-the-ad*
  question in (d)]. Same source: Kantar's own digital-ad wear-out data shows only ~6% of digital
  ads retain unchanged "enjoyability" on a second test vs. the first, with over half rated less
  enjoyable — i.e. the **specific execution** fatigues fast even when the underlying **concept**
  (Twinings, Marmite) does not; this is the empirical basis for the concept-vs-execution split used
  in the recommendation below.

**"Continuous run time = profitability signal" — the practitioner heuristic, well corroborated
across multiple independent sources**: *"An ad that has been active for 30-90+ days is almost
certainly generating positive returns — otherwise the budget would have been redirected... by
filtering for specific advertisers or keywords and sorting by run duration, you can identify which
creatives an advertiser has chosen to keep spending behind."* [adriselab.com / multiple corroborating
sources, fetched 18 Jul 2026 — UNVERIFIED/secondary but this exact heuristic recurs, worded almost
identically, across at least 4 independent practitioner sources found this pass, which is itself a
form of corroboration even absent a single primary citation]. Caveat stated by the same cluster:
*"an ad running for duration doesn't confirm the ad is currently profitable... and it doesn't
control for brand-specific factors — a well-funded brand can afford to run break-even awareness
campaigns for months."* — a fair caution against over-reading Taqinor's own competitor forensics.

**Distinguishing creative shelf-life from campaign/account longevity — the key nuance**:
- **[UNVERIFIED, single-source, different channel — CTV not Meta]** MNTN Research: *"an evergreen ad
  has an average shelf life of 59-64 days"* — this is Connected-TV data, not Meta, and is about the
  individual **creative asset**, not the campaign/account structure. Cited here only because it is
  the one source with an actual number, and because it lines up almost exactly with the general
  "refresh creative every 2-3 months" consensus found across the unrelated Meta-specific fatigue
  searches too (frequency-threshold sources in `dd-meta-mechanics.md`'s companion research already
  converge on similar timeframes for Meta specifically).
- **Net reconciliation**: the "creative wears out in ~2-3 months" and "campaigns run unbroken for
  1-2 years" findings are **not in tension** — they describe two different layers. The *campaign/
  ad-set container* is what goes perpetual; the *ad objects inside it* are what rotate on a matter
  of weeks-to-months. This is also exactly the shape `dd-science-core.md` already specifies for
  Taqinor's bandit (§4's 6-month phased flight plan, each phase 3-6 weeks, feeding a slowly-evolving
  creative backlog) — the perpetual-campaign question and the already-designed bandit cadence are
  the SAME answer looked at from two angles, not a new constraint.

---

## (c) Who runs perpetual: local/lead-gen vs. launch-driven ecom

- **Local/lead-gen SMBs (dentists, HVAC, roofing, solar — Taqinor's own category) are the
  textbook case for always-on**, close to definitionally: there is no "season" or "drop" for
  ongoing local demand generation the way there is for a product launch. Every dentist/HVAC/roofing
  case study found this pass (LocaliQ, Invoca, Marketing 360, Profit Roofing Systems, Built Right
  Digital, Contractor Marketing Pros) describes an ongoing, continuously-running lead-gen program,
  not a launch-and-retire campaign — **[UNVERIFIED-secondary, content-farm-adjacent sources, but
  unanimous in framing]** none of them frame the engagement as anything but continuous/retainer-based
  management, which is itself indirect evidence that "always-on" is the assumed default for this
  category, to the point that no source bothered to argue for it explicitly.
- **I could not find one single case study explicitly stating "we ran the identical campaign,
  untouched, for N years" for a local lead-gen business** — a genuine negative finding. What exists
  instead is retainer-style "ongoing management" framing (implicitly perpetual, with rolling
  creative refresh) rather than a documented, static, N-year-long campaign. This slightly weakens
  claim (b)'s Mejuri/Tecas precedent as applied to THIS specific vertical — the precedent is real
  for ecom brand creative, less directly documented (though plausible by category logic) for local
  lead-gen specifically.
- **Ecommerce is bifurcated**: launch/drop campaigns remain real and distinct (new product, seasonal
  promotion), but current agency commentary (2026) describes even ecom converging toward an
  always-on **base layer** underneath the launch bursts — the "campaign ecosystem," not "the
  campaign," framing from (a). So the honest read is: **the dichotomy in the mission brief
  (always-on for local/lead-gen vs. launch-driven for ecom) is real but softening — it is now a
  matter of what proportion of the account is base-layer vs. burst-layer, not an either/or.**
- **CTWA/WhatsApp specifically**: 2026 practitioner material explicitly frames Click-to-WhatsApp as
  built for an *"always-on lead generation funnel,"* names MENA as one of the fastest-growing CTWA
  regions, and reports Meta-published/advertiser-published performance deltas (92% lower CPL, 94%
  more conversions vs. landing-page destination) [go4whatsup.com, fetched 18 Jul 2026 — UNVERIFIED,
  secondary, numbers not independently traced to a specific named Meta case study, but the
  always-on framing for CTWA specifically directly supports Taqinor's own channel choice].

---

## (d) The "campaign that never ends" — named concept, and Meta's current consolidation doctrine

**"Evergreen"/"always-on" as a named marketing concept**: well-established, decades-old vocabulary
(evergreen content marketing, evergreen sales funnels), now explicitly applied to Meta paid social.
The phrase *"the campaign that never ends"* does not appear to be an official platform term of art
(no dedicated Meta or agency framework found using those exact words) — it best matches the
**evergreen campaign / always-on marketing** literature, where the defining trait is: *"can exist at
any time because [it's] not specifically tied to a timely event, season, or limited product."*
[multiple converging sources, e.g. salesfunnelprofessor.com, brafton.com — UNVERIFIED-secondary,
generic marketing-glossary consensus, low individual-source authority but essentially uncontested].

**Is a 1-2 year continuously-optimized single campaign realistic on Meta, or does the account
naturally re-architect every N months?** The evidence assembled this pass says: **realistic at the
architecture level, actively encouraged by Meta's own current doctrine** — but "continuously
optimized" does NOT mean "untouched." Specifically:

- **[VERIFIED]** Andromeda (Meta's AI ad-ranking/retrieval system) began internal testing Dec 2024,
  rolled out across Facebook/Instagram feeds through 2025, reported as fully deployed/default by
  early-to-mid 2026 [converging dating across multiple secondary sources this pass; the underlying
  Andromeda system itself is independently corroborated in engineering-press coverage per
  `dd-meta-mechanics.md`'s own research window]. Its structural implication, consistent across
  every source found: **"fewer, larger ad sets with more creative diversity per ad set... simplified
  structures perform best: 1-3 ad sets maximum per campaign instead of 5-10."**
  [flighted.co / multiple corroborating 2026 agency blogs — UNVERIFIED-secondary, content-farm
  cluster, but internally consistent and consistent with the independently-verified Performance-5
  doctrine in (a), which predates Andromeda and points the same direction].
- **[UNVERIFIED, single-cluster, treat cautiously]** Several 2026 blog sources describe an even more
  extreme "Andromeda-era" structure for ecommerce specifically: *"one campaign, one ad set, many
  creatives... 15 to 50 creatives stacked inside"*, with brands *"testing 20+ new ads per month"*
  seeing materially higher ROAS. **This entire volume/velocity claim is scaled for ecommerce
  accounts spending far more than Taqinor's ~$10/day** — `dd-science-core.md` already independently
  derived (from first-principles MDE statistics, not from these blogs) that Taqinor is capped at
  **2-4 creative arms**, because anything wider thins each arm below a usable event rate. **This is
  a real tension worth flagging explicitly**: Andromeda's doctrine and the low-volume math both say
  "fewer campaigns, simpler structure," but they disagree on **creative count** — resolve in favor
  of the already-derived, first-principles math (2-4 arms), not the ecom-scaled blog folklore. The
  STRUCTURAL lesson (one campaign, one ad set, forever) transfers across budget scales; the
  CREATIVE-COUNT lesson (15-50 creatives) does not.
- **What forces a restructure, evidence-based**:
  1. **Platform shocks** — the one well-documented, precisely-dated, industry-wide example is
     **iOS 14.5 ATT, April 26 2021** [VERIFIED-well-known/multiply-corroborated: Flurry Analytics'
     May 2021 finding of up to 88% global opt-out (96% in the US); Meta's own default attribution
     window change to 7-day-click/1-day-view for campaigns launched on/after 26 Apr 2021; measured
     ROAS drop from 3.13 to 1.93 (-38%) Feb-Sep 2021 per one cited analysis]. **Nothing of comparable,
     independently-confirmed magnitude has recurred since** in the sources found this pass — the
     "March 2026 algorithm update" claims are single-blog-cluster and NOT independently corroborated;
     treat as UNVERIFIED, possibly overstated/content-farm noise, not a second confirmed iOS14-style
     shock.
  2. **Creative fatigue** — well-attested, but this forces **rotating the ad inside the structure**,
     not restructuring the campaign/ad-set architecture itself. Practitioner frequency thresholds
     (2.5 early-warning, 3.0 prospecting-decay, 6.0+ warm-retargeting-fatigue) are UNVERIFIED/Meta-
     silent-on-exact-numbers per this pass's searches (consistent with `dd-meta-mechanics.md`'s
     "Meta does not publish frequency thresholds" framing) but industry-consensus.
  3. **Learning-phase-reset economics** (already established in `dd-meta-mechanics.md`) is itself a
     structural FORCE FOR perpetuity: every "significant edit" (new ad added, >20% budget change,
     audience change, >7-day pause) restarts the learning phase and costs real performance — so the
     mechanically cheapest path is exactly "leave the container alone, swap creative in/out
     carefully" rather than periodic wholesale rebuilds. Meta's own incentive structure and the
     evergreen-architecture recommendation are the same conclusion from two directions.

---

## (e) Practical answer for Taqinor: recommended perpetual architecture

Synthesizing (a)-(d) against Taqinor's own already-specified engine design
(`dd-science-core.md` §2-4, `dd-meta-mechanics.md` (c)/(d)):

**What lives forever (the perpetual layer)**:
- **One campaign, ABO** (per `dd-meta-mechanics.md` (d)'s existing recommendation to keep
  allocation logic in the engine's own bandit rather than Meta's CBO black box) — this is the
  single container that should never be deleted/recreated. Evidence basis: Meta's own Performance-5
  "account simplification" pillar + Andromeda's "1-3 ad sets max" doctrine + the learning-phase-
  reset economics all independently point to minimizing container churn.
- **One (or at most 2-3, per market-mode: résidentiel/industriel/agricole) ad set(s) inside it**,
  each holding **2-4 creative arms** (per `dd-science-core.md`'s MDE-derived ceiling, NOT the
  ecom-scaled "15-50 creatives" folklore in (d) — that volume assumes an event rate Taqinor does not
  have). These ad sets are the "evergreen core."
- **A permanent retargeting layer** (per the universally-converging "base + retargeting + bursts"
  structure in (a)) — even at Taqinor's tiny scale, a standing retargeting ad set for CTWA-conversation-
  started-but-not-yet-qualified is consistent with every source's described architecture, and costs
  little given Meta's ad-set delivery floor is already assumed at ~20 MAD/day per
  `dd-science-core.md` §2.4.

**What rotates (the burst/refresh layer)**:
- **Individual creative assets**, on the cadence already specified in `dd-science-core.md` §4 (each
  test phase 3-6 weeks, exit at P(best)≥80% or a 4-week cap, loser retired to `archived` with a
  `retired_reason`) — this maps directly onto the "creative wears out every ~2-3 months" evidence in
  (b)/(d) without needing a new rule; the phased flight plan the engine already has IS the fatigue-
  management mechanism the perpetual-campaign literature calls for.
- **Seasonal/opportunistic bursts** (e.g. a Ramadan-timing angle, an end-of-summer-bill-shock angle)
  can be layered in as an additional short-lived creative arm inside the SAME perpetual ad set,
  never as a new campaign — consistent with (a)'s "layered on top, never replacing the base" model,
  and avoiding a fresh learning-phase reset for the whole structure.

**What would force a genuine restructure (rare, and worth pre-committing to NOT overreacting to
routine noise)**: a confirmed platform-level shock on the scale of iOS14/ATT (none independently
confirmed since 2021 in this pass's research); a hard Meta policy/API deprecation forcing a new
object type (the Advantage+ campaign-type retirement already tracked in `dd-meta-mechanics.md` (d)
is exactly this category, and Taqinor's engine already accounts for it); or the CRM-truth divergence
override already specified in `dd-science-core.md` §2.7 (money-rung signal disagreeing sharply with
the proxy) — that is a human-gated decision point, not an autonomous restructure trigger.

**Bottom line**: Taqinor's already-designed engine (bandit + phased creative flight plan + ABO
container + CRM-divergence human gate) is **already, without further changes, a correctly-shaped
perpetual-campaign architecture** by the evidence assembled here — the "campaign that never ends" is
the container-plus-bandit the engine already specifies; nothing in this research suggests adding a
scheduled full-restructure cadence, and several independent lines of evidence (learning-phase-reset
cost, Andromeda's consolidation doctrine, Meta's own Performance-5 framework) argue explicitly
against ever doing one on a fixed calendar.

---

## Sources

**Primary (Meta-owned or genuine research-firm, fetched/quoted directly this pass):**
- [Meta — Introducing New Automation Tools to Increase Sales and Drive Growth](https://about.fb.com/news/2022/08/introducing-new-automation-tools-to-increase-sales-and-drive-growth/) (about.fb.com, 15 Aug 2022 — fetched directly; confirmed NO literal "always-on" phrase present, a stated negative finding)
- [Facebook Blueprint — Performance 5 course page](https://www.facebookblueprint.com/student/path/253157-performance-5) (course description fetched directly; lesson bodies behind login, not fetchable)
- [Kantar — The art of creating ads that last](https://www.kantar.com/inspiration/advertising-media/the-art-of-creating-ads-that-last) (fetched directly; Twinings/Marmite longevity data, digital ad wear-out %)

**Independent trade press / ad-library-based case studies:**
- [adkit.so — 15 Proven Facebook Ad Examples to Copy](https://adkit.so/resources/ads-examples/facebook-ad-examples) (Mejuri 431-day ad, Ad Library "days active" sourced)
- [Flurry Analytics iOS14 opt-out data / WordStream / Supermetrics / Target Internet iOS14 coverage] (multiply-corroborated April 2021 ATT shock, cited via aggregated search results, 18 Jul 2026)

**Secondary/practitioner (explicitly flagged UNVERIFIED in-text; used only for directional/converging claims):**
- zen.agency (ecom always-on-infrastructure framing), tigerpistol.com, overtdigitalmarketing.com.au,
  2tenmarketing.com, amandaai.com (Performance-5 secondary description)
- flighted.co, adstellar.ai, fiveninestrategy.com, jetfuel.agency, 1clickreport.com, ppcblogpro.com
  (Andromeda consolidation-doctrine cluster — internally consistent, single-genre content-farm risk)
- adriselab.com, foreplay.co, marpipe.com (ad-library "days active = profitability signal" heuristic)
- research.mountain.com / MNTN Research (evergreen creative 59-64 day shelf life — CTV channel, not Meta)
- go4whatsup.com (CTWA "always-on lead generation funnel" framing, MENA growth claim)
- LocaliQ, Invoca, Marketing 360, Profit Roofing Systems, Built Right Digital, Contractor Marketing
  Pros (local/lead-gen vertical case-study cluster — content-farm-adjacent, unanimous in framing
  continuous/retainer management as the default, but none document an explicit N-year single
  campaign)
- linkedin.com/business Always-On/Evergreen PDF (existence confirmed; body text not retrievable —
  cross-platform corroboration that "always-on" is named platform vocabulary, just not Meta's)

**Attempted, not retrievable (real negative findings, not skipped)**:
- `facebook.com/ads/library/?...q=Tecas...` — direct fetch attempt returned a socket error (JS SPA,
  same class of limitation as Meta Help Center pages); Tecas 20+-month claim NOT independently
  re-verified this pass, stands only on the prior internal research cited in the mission brief.
- `facebook.com/business/success/sand-cloud` — 404 on direct fetch; could not confirm this specific
  Meta-published small-budget success story's content this pass.
- Multiple `facebook.com/business/help/*` pages (Learning Phase, Significant Edits, Advantage+
  Audience, Advantage+ Sales) — titles confirmed reachable, body text not (same known limitation
  documented in `dd-meta-mechanics.md`).
