# AT-BENCHMARKS — Cross-account priors & benchmarks: the "borrow from other fields with no data" piece

Research date 17-18 Jul 2026. Scope: ONE piece of the founder's autonomous-ads-engine idea — "with
no data in a new field, borrow priors from other fields." This dossier does not re-litigate the
tree/staleness/AI-seeding parts of the idea (out of scope for this pass); it answers, with sources,
whether cross-account/cross-tenant prior-borrowing is a real, legal, already-solved pattern.

Source discipline: every claim [VERIFIED] (primary doc, fetched/quoted directly), [INDEPENDENT]
(named trade source / peer-reviewed paper, not primary-fetched but corroborated), or [UNVERIFIED]
(secondary/content-farm or a search-engine synthesis I could not primary-fetch). Context read, not
re-derived: `docs/engine/research/dd-science-core.md` (the MDE/bandit math already speccing an
*intra-account* informative prior option) and `dd-guardian.md`. A referenced `eng-compliance.md`
dossier (cited by `scope-features.md` as "already researched" Meta compliance/Business-Manager
staging) does **not exist in this worktree/branch** — could not be located via Grep/Glob across
`docs/`; flagged, not re-derived from scratch here, treat as missing/unverified provenance.

---

## Bottom line up front

**The founder's instinct is directionally correct AND the literature/product landscape validate it
— but "borrow priors from other fields" is two completely different features hiding under one
sentence, with wildly different risk:**

1. **Cross-*category*, same-tenant** (Taqinor's own résidentiel vs. industriel vs. agricole
   campaigns, all inside Taqinor's own Meta ad account) — **zero legal risk, buildable today**,
   and there is a real, peer-reviewed, production-proven statistical pattern for exactly this
   (hierarchical Bayesian bandits, §3). This is what Taqinor can actually use RIGHT NOW, since
   Taqinor has no other clients yet.
2. **Cross-*tenant*, other companies' data** (the Varos/Triple Whale model — pooling anonymized
   benchmarks across many *different* businesses) — **real, established, and apparently tolerated
   by Meta in practice, but NOT cleanly authorized by Meta's own written terms**, which is a
   materially different risk posture than "this is definitely fine." It is also **irrelevant to
   Taqinor today** — it only matters if/when Taqinor productizes the ads engine for other clients
   (already correctly GATED/"Later" in `docs/engine/research/scope-features.md`).

Do not let the founder believe the Varos precedent gives Taqinor legal cover for pooling data
across *future clients'* Meta accounts. It gives cover for the much narrower, much safer, much more
immediately useful move: sharing statistical strength across Taqinor's *own* different verticals.

---

## (a) Products that pool anonymized benchmarks across a client base

### Varos
[INDEPENDENT — multiple converging secondary sources: moge.ai, varos.com marketing pages,
digitaljournal.com PR, geo.sig.ai, crunchbase; could not primary-fetch Varos's own ToS/privacy text
verbatim — see caveat below]
- **Model: "give-to-get" / data cooperative.** Brands connect their Meta/Google/TikTok ad account;
  their data is "synced, anonymized, and aggregated with the available data set" in order to *unlock*
  access to the cooperative's benchmarks — i.e., **contribution is effectively the price of
  admission**, not a separable opt-in toggle. Claimed scale: 4,500–7,000+ participating companies,
  "$4B+ in annual ad spend."
- **Granularity out**: filtered by vertical, monthly ad-spend band, and AOV; only aggregate
  medians/ranges are ever shown — "impossible to see data for any specific company."
- **Caveat**: I could not get a primary fetch of Varos's own live ToS/privacy page to quote its
  exact consent clause — the page returned described Varos as an "AI agent" business (a 2026
  product-line shift?), not the benchmarking cooperative described in older PR/press pieces. This
  is a **freshness/consistency flag**, not a confirmed fact: treat Varos specifics above as
  [UNVERIFIED as of this exact date] even though widely repeated.

### Triple Whale (Benchmarks / Trends)
[INDEPENDENT — kb.triplewhale.com article title + triplewhale.com blog posts corroborated across
search; the KB article itself 403'd on direct fetch]
- Computed **daily**, cross-brand **median**, from **60,000+ ecommerce brands** connected to Triple
  Whale. Raw storage is one row per shop/day/channel; only **aggregated statistics leave the
  system** (medians + percentile ranges) — "no individual business's metric value is ever exposed."
- **Minimum peer-group size enforced**: a benchmark is only returned once the cohort has **≥5
  similar brands**.
- Peer group ("cohort") is auto-built by similarity — no manual configuration needed by the user.
- Mixes two data sources: pixel/attributed order data (Blended ROAS, CPA, New-Customer %, AOV) +
  **connected ad-account data** (CPM, CTR) — the latter is literally Meta/Google Ads-Manager-API
  data, which matters for §(b).
- "Collected...with consent from their customer base" — could not pin down whether this is opt-out
  (default-on, contractual ToS consent) or an explicit opt-in toggle; treat as [UNVERIFIED] on that
  specific mechanic.

### Databox Benchmark Groups
[VERIFIED-ish via search-engine synthesis of Databox's own help-center pages, not a raw primary
fetch — direct WebFetch on the specific how-it's-calculated article returned an unrelated
chart-types article, so treat the exact wording below as INDEPENDENT/high-confidence, not a literal
quote]
- **Explicit opt-in, and explicitly revocable**: "only accounts who have opted-in will be able to
  anonymously compare performance," and "users have the option to opt-out at any time." This is the
  most clearly documented opt-in mechanic of the three.
- **Minimum cohort size: ≥15 different data sources** in the selected cohort before a benchmark is
  shown — the tightest/most conservative floor of the three found.
- Cohort defined by industry × business type × employee size × revenue (combinable).
- Private "Benchmark Groups" exist too — invited/contributing-members-only cohorts, same
  aggregation logic, smaller circle.

### Pattern across all three
Opt-in or give-to-get (never silent), **aggregate-only egress** (raw data never leaves the vendor's
walls to another customer), **an enforced minimum-cohort floor** (5–15+) before any number is shown
— this last point is the one Taqinor should copy hardest given how thin Taqinor's own future client
base would be (a floor of 15 is unreachable for years at Taqinor's likely client count; see §(e)).

---

## (b) Meta's Platform Terms — what is actually forbidden vs. permitted

Two primary documents fetched directly and quoted verbatim.

**Meta Advertising Standards** [VERIFIED — fetched `transparency.meta.com/policies/ad-standards/`
directly, 17 Jul 2026]:
> "Don't use Meta advertising data for any purpose (including retargeting, **commingling data
> across multiple advertisers' campaigns**, or allowing piggybacking or redirecting with tags),
> **except on an aggregate and anonymous basis (unless authorized by Meta) and only to assess the
> performance and effectiveness of your Meta advertising campaigns.**"

> "Don't transfer any Meta advertising data (including anonymous, aggregate, or derived data) to
> any ad network, ad exchange, data broker or **other advertising or monetization related
> service**."

**Meta Business Tools Terms** (`facebook.com/legal/technology_terms`) [VERIFIED — fetched directly,
English via `?locale=en_US`, 17 Jul 2026], §2.a.ii:
> "We grant to you a non-exclusive and non-transferable licence to use the Campaign Reports and
> Analytics for your internal business purposes only and solely on an aggregated and anonymous
> basis for measurement purposes."
> "You will not disclose the Campaign Reports or Analytics, or any portion thereof, to any third
> party, unless otherwise agreed to in writing by us."

### What this actually means — the honest reading, not the marketing reading

- **What it clearly forbids, no ambiguity**: reselling/transferring Meta ad data (even aggregate
  or derived) to an ad network, exchange, data broker, or "other advertising/monetization related
  service" — this is an absolute, no-consent-cures-it prohibition. A benchmarking SaaS is arguably
  itself an "advertising-related service," which is not a comfortable place for a Varos/Triple
  Whale-style product to sit; no primary source resolves whether "monetization related service"
  was drafted with benchmarking tools in mind or squarely at DSPs/data brokers.
- **What creates the real tension**: the license each advertiser gets to its OWN Campaign
  Reports/Analytics is "internal business purposes only," and the advertiser "will not disclose"
  those reports "to any third party" absent Meta's written agreement. Handing your Campaign Reports
  to a benchmarking vendor **is** a disclosure to a third party. The aggregate-and-anonymous
  exception in the Advertising Standards is scoped to "assess the performance and effectiveness of
  **your** Meta advertising campaigns" (singular company) — it does not, on its face, say "and you
  may also let a vendor blend it with other companies' data for comparison."
- **Verdict: this is an unresolved, tolerated grey area — not an expressly authorized practice.**
  No primary Meta document I could find explicitly blesses third-party cross-advertiser benchmark
  pooling. What's actually happening in the market (Varos running since ~2021, Triple Whale funded
  and Shopify-partnered, both operating for years at real scale with no public sign of Meta
  enforcement action) is best read as: **Meta tolerates it as long as (1) only aggregates leave the
  vendor, (2) no advertiser can ever re-identify another's raw numbers, and (3) nothing is resold
  onward to ad networks/brokers** — the same three guardrails these vendors already implement in
  §(a). That is a *practice consensus born of tolerance*, not a documented legal green light. Flag
  this explicitly to the founder: **"everybody does it and nobody's been punished" is not the same
  claim as "Meta's terms permit it."**
- One possible legal cover this research could **not** verify either way: whether being a **Meta
  Business Partner** (the certified partner program — Smartly, Madgicx, Revealbot, AdEspresso are
  members) carries any different/looser data terms via a separate partner agreement not published
  publicly. Could not confirm Varos/Triple Whale/Databox partner-badge status from public sources.
  [UNVERIFIED — flagged, not resolved].
- **Separately, and NOT the same issue**: Meta announced (28 Apr 2026, effective 3 Feb 2027) new
  Developer Policy transparency rules explicitly naming **"multitenant SaaS tools"** among the
  ad-buying solutions that must disclose ad spend vs. fees and full campaign configuration to end
  advertisers on request [INDEPENDENT — socialmediatoday.com + almcorp.com summaries of Meta's own
  developer-blog post by Nicholas Medina, could not primary-fetch the Meta developer blog post
  itself]. This is about spend/fee transparency TO the client, not data pooling ACROSS clients — but
  it is Meta explicitly naming "multitenant SaaS tools running Meta ads on a client's behalf" as a
  regulated category, which is exactly what a productized, multi-client Taqinor ads engine would be.
  Relevant context for whenever Taqinor productizes ENG1-31 for other clients — not an action item
  today.

---

## (c) The statistical pattern — hierarchical priors across tenants: real, named, peer-reviewed

This is the strongest, cleanest finding of the whole pass, and it directly validates the founder's
statistical instinct (separate from the legal question in (b)).

**Hierarchical Bayesian Bandits (HierTS)** — Hong, Kveton, Zaheer, Ghavamzadeh, *AISTATS 2022*
[VERIFIED — abstract fetched via arXiv:2111.06929 / proceedings.mlr.press/v151/hong22c, peer-reviewed
conference proceedings, real authors at Google/DeepMind-affiliated research]:
> "Meta-, multi-task, and federated learning can be all viewed as solving similar tasks, drawn from
> a distribution that reflects task similarities. [We provide] a unified view of all these problems
> as learning to act in a hierarchical Bayesian bandit... The regret bounds hold for many variants
> of the problems, including when the tasks are solved sequentially or in parallel, and show that
> the regret decreases with a more informative prior... the theory is complemented by experiments
> which show that the hierarchy helps with knowledge sharing among the tasks."
This is **exactly** "a new task/account with no data borrows a prior from a hierarchy of similar
tasks, and provably learns faster" — the founder's idea, as a named, proven, general-purpose
algorithm (HierTS), applicable to Taqinor's bandit design in `dd-science-core.md` §2 essentially
as-is (a "task" = a campaign category/vertical; the hierarchy's top level = Taqinor's own
account-wide rate; a brand-new vertical inherits that top-level prior until it accumulates its own
data — precisely the "informative prior, Beta(α₀,β₀)" option already sketched, undeveloped, in
`dd-science-core.md` §2.2).

**Multi-Task Combinatorial Bandits for Budget Allocation** — Amazon, *KDD 2024*
[VERIFIED — abstract/results corroborated via amazon.science + arXiv:2409.00561 + ACM DL record;
could not extract the full PDF text but the abstract/venue/authorship are independently confirmed]:
- Framed explicitly around **"today's top advertisers typically manage hundreds of campaigns
  simultaneously"** needing to allocate budget under **"huge uncertainty in return outcomes."**
- Solution: **"integrates a Bayesian hierarchical model to intelligently utilize the metadata of
  campaigns"** (category, budget size) **"ensuring efficient information sharing"** + Thompson
  sampling for the exploration/exploitation trade-off.
- **Measured result: 12.7% cost-per-click reduction vs. standard practice after three weeks**, in a
  real deployment.
- This is the closest production-scale precedent to "a new field with no data borrows from a
  category-level metadata prior" — but note the honest caveat: this is **Amazon's own internal
  advertising system pooling across many campaigns it already fully owns/operates**, not a
  third-party SaaS pooling different *companies'* private data for each other's mutual benefit. It
  validates the STATISTICS, not the cross-company legal pattern.

**What was NOT found — say so plainly.** No agency-scale ad-tech platform (Smartly.io searched
specifically, given the brief's own question) **publicly claims** "your account gets smarter because
of what we learned managing other clients' accounts in the same category" as a customer-facing
feature. Smartly's own public docs describe per-account predictive budget allocation and creative
automation, not cross-client statistical transfer. **Honest answer: nobody publishes this as a named,
marketed feature at agency scale.** It may exist as an unadvertised internal capability somewhere,
but no primary or independent source surfaced one. Treat "Smartly does cross-account learning" as
unconfirmed if the founder has heard that claim informally.

---

## (d) Cold-start practice — what benchmarks do real media buyers actually reach for

**WordStream — Google Ads Benchmarks 2026** [VERIFIED — fetched `wordstream.com/blog/2026-google-ads-benchmarks`
directly, 17 Jul 2026]: 13,474 US search-ad campaigns, **Apr 2025–Mar 2026**, min. 52 campaigns/subcategory,
figures are medians (outlier-resistant). Relevant category: **"Home & Home Improvement"** — CTR 6.47%,
CPC $8.33, CVR 8.05%, **CPL $90.92**. No solar/renewable-energy category exists.

**LocaliQ — 2025 Search Ad Benchmarks for Home Services** [VERIFIED — fetched
`localiq.com/blog/home-services-search-advertising-benchmarks/` directly, 17 Jul 2026]: 3,211 US
search campaigns, **Apr 2024–Mar 2025**, min. 103 campaigns/subcategory, medians. Relevant
categories:
| Category | CTR | CPC | CVR | CPL |
|---|---|---|---|---|
| Landscaping | 4.69% | $8.76 | 6.42% | $117.92 |
| Roofing & Gutters | 5.66% | $10.70 | 3.70% | $228.15 |
| A/C Install & Repair | 6.43% | $9.68 | 6.56% | $127.74 |
| Home Services (overall) | 6.37% | $7.85 | 7.33% | **$90.92** |

**Two honest catches, worth surfacing to the founder directly:**
1. **These are Google/Microsoft SEARCH ads benchmarks — not Meta, not Click-to-WhatsApp.** They are
   the best-known, most-cited industry cold-start source (this is genuinely what practitioners
   reach for — WordStream/LocaliQ are the standard citation across the ad-tech content ecosystem),
   but the *funnel shape is structurally different* from Taqinor's actual channel (Meta CTWA →
   WhatsApp conversation, no landing page, no traditional "conversion" event). Borrowing a CPL
   number from a Google Search report into a Meta-CTWA bandit prior is an order-of-magnitude
   sanity-check at best, not a plug-in Beta(α,β) parameter — this matches `dd-science-core.md`'s own
   existing caveat about the MENA-CTWA numbers it uses being a single, unverified aggregator.
2. **LocaliQ's "Home Services" overall CPL ($90.92) is numerically identical to WordStream's 2026
   "Home & Home Improvement" CPL ($90.92)** despite different report years/methodologies/sample
   windows. That is either a genuine coincidence, a shared upstream data source between the two
   (LocaliQ and WordStream are both owned by the same parent, Gannett/LocaliQ family — plausible),
   or evidence the "2026 update" reused stale figures for that row. Flag this as a reason not to
   over-trust the precision of any single number from this report family — treat them as directional,
   consistent with how `dd-science-core.md` already treats its own benchmark inputs.
3. **No solar category exists in either report**, confirming what `dd-science-core.md` already
   found — there is no off-the-shelf published benchmark for Taqinor's actual vertical at any
   granularity. "Home & Home Improvement" / "Landscaping" are the nearest available proxies, and even
   those are Search, not Meta CTWA.

---

## (e) Design pattern — a consent-gated benchmark scheme that stays inside Meta's terms

Synthesizing (a)-(d) into a concrete pattern **for if/when Taqinor productizes the ads engine for
other clients** (per `scope-features.md`'s own "Later" gate — this is NOT needed for Taqinor's
current single-tenant solar account):

1. **Two-tier consent, not one.** (i) Taqinor's own SaaS Terms with each client must carry an
   explicit, separately-flagged clause ("your aggregated, anonymized performance metrics may be
   pooled with other Taqinor clients to build category benchmarks; you may opt out at any time") —
   this is the layer that legitimizes Taqinor acting as the client's *service provider* processing
   their Meta Campaign Reports, mirroring how Varos/Databox/Triple Whale structure their own
   customer-facing consent. (ii) Default **opt-in, not opt-out** (Databox's model, the most cleanly
   documented and most defensible given the unresolved Meta-terms tension in §(b)) — do NOT default
   every client into the pool silently.
2. **Aggregate-only egress, enforced in code, not policy.** No client, including Taqinor's own
   dashboard, may ever query a cohort below a hard minimum size. Given Taqinor's own likely client
   count for years (a handful of SMB solar/landscaping accounts, not Databox's/Triple Whale's tens
   of thousands), **a Databox-style floor of 15 is realistically unreachable** — this whole feature
   is genuinely gated on Taqinor having enough same-category clients to make a benchmark
   statistically meaningful at all, independent of the legal question. Until then, showing "your CPL
   vs. the pool" with n=3 would be worse than showing nothing (exactly the MDE-table lesson already
   in `dd-science-core.md` §1).
3. **Never forward raw or re-identifiable data outward.** Satisfies Meta's absolute, no-exception
   ban on transferring Meta advertising data (even aggregate/derived) to "any ad network, ad
   exchange, data broker or other advertising or monetization related service" — Taqinor's own
   benchmark pool must stay a closed loop shown back only to Taqinor's own clients, never resold,
   never exported to a DSP/broker.
4. **Keep the two layers of "borrowing" architecturally separate.** Cross-*category*-same-tenant
   pooling (Taqinor's own résidentiel/industriel/agricole campaigns) needs NONE of the above — it's
   one advertiser's own data under its own "internal business purposes" license, cleanly legal today,
   and is where the HierTS/hierarchical-Bayes pattern in §(c) should be spent first. Cross-*tenant*
   pooling is the separate, later, riskier feature that needs the consent scheme above. Don't conflate
   them in the build — the founder's "borrow from other fields" sentence should be read as item 1
   today, item 2 only after there are enough real other clients to make it statistically or legally
   worth the complexity.

---

## Sources

Primary (fetched directly, quoted where noted):
- [Meta Advertising Standards — Transparency Center](https://transparency.meta.com/policies/ad-standards/) — fetched 17 Jul 2026
- [Meta Business Tools Terms](https://www.facebook.com/legal/technology_terms) (English via `?locale=en_US`) — fetched 17 Jul 2026
- [WordStream — Google Ads Benchmarks 2026](https://www.wordstream.com/blog/2026-google-ads-benchmarks) — fetched 17 Jul 2026
- [LocaliQ — 2025 Search Ad Benchmarks for Home Services](https://localiq.com/blog/home-services-search-advertising-benchmarks/) — fetched 17 Jul 2026

Independent / peer-reviewed (corroborated, not always directly PDF-extractable):
- [Hierarchical Bayesian Bandits — arXiv:2111.06929](https://arxiv.org/abs/2111.06929) / [AISTATS 2022 proceedings](https://proceedings.mlr.press/v151/hong22c.html) (Hong, Kveton, Zaheer, Ghavamzadeh)
- [Multi-Task Combinatorial Bandits for Budget Allocation — Amazon Science / KDD 2024](https://www.amazon.science/publications/multi-task-combinatorial-bandits-for-budget-allocation) ([arXiv:2409.00561](https://arxiv.org/abs/2409.00561))
- [Triple Whale — Benchmarks Dashboard / "see how your business stacks up"](https://kb.triplewhale.com/en/articles/15483220-benchmarks-see-how-your-business-stacks-up-against-brands-like-yours) (title + secondary corroboration; direct fetch 403'd)
- [Databox — Benchmark Groups](https://databox.com/databox-benchmark-groups), [How data is calculated in Benchmark Groups](https://help.databox.com/how-is-data-being-calculated-in-the-benchmark-groups) (secondary-corroborated, direct fetch of the specific article failed)
- [Meta transparency rules for third-party ad platforms — Social Media Today](https://www.socialmediatoday.com/news/meta-updates-transparency-rules-for-third-party-ad-platforms/818775/), [ALM Corp summary](https://almcorp.com/blog/meta-third-party-ad-platform-transparency-rules/) (secondary summaries of an Apr 2026 Meta developer-blog post, not primary-fetched)

Unverified / flagged directly in text:
- Varos's own current benchmarking-cooperative claims (7,000+ companies, "$4B+ ad spend," give-to-get
  mechanics) — only secondary/PR sources found; direct fetch of varos.com's live page returned
  content describing a different ("AI agent") product line, an unresolved freshness/consistency flag
- Whether Meta Business Partner status carries different/looser data-sharing terms for
  Varos/Triple Whale/Databox specifically — could not confirm partner-badge status or any
  partner-specific contract terms from public sources
- `docs/engine/research/eng-compliance.md`, referenced by `scope-features.md` as prior research on
  Meta compliance staging — not present in this worktree/branch, could not be read or verified
