# RESEARCH MAP — Ads-Management Engine Feature Taxonomy (Groupe ENG round 2)

Date: 16 Jul 2026. Scope: enumerate the complete feature taxonomy of the "autonomous Meta-ads
management" category from leaders' own docs/feature pages + Meta's own native docs, so a Round-1
deep-dive wave can spec OUR version. **Groupe ENG (ENG1-ENG31) is already merged** — connection,
mirrors, PAUSED client, propose->approve, cost-per-signature, deterministic brief, creative
library, approval inbox. This map is scoped to what ENG1-31 does NOT yet cover.

Source note: this pass used targeted WebSearch (search-engine AI summaries of vendor/help-center
pages, not always a raw fetch) — good enough to map the territory, NOT a substitute for a deep-dive
agent directly fetching the cited page before spec'ing. Every deep-dive mission below must re-verify
its own domain's cited pages directly. Prior-session research (compliance/competitors/UX/channels/
creative-gen files, paths in the mission preamble) is NOT re-summarized here except where it fills a
domain gap (marked "[from prior research]").

---

## 1. Campaign / Creative Management (the base CRUD layer)

- **(a) Leaders ship**: full hierarchy CRUD (campaign→ad set→ad→creative) with cross-account/
  cross-platform normalization — Smartly.io explicitly supports "nearly every native Meta feature"
  (DPA, DCO, Instant Experience/Form, placement customization) [smartly.io/all-features, G2 Smartly
  reviews]. AdEspresso's differentiator was collapsing Meta's own multi-click flow into one screen
  [G2/Capterra AdEspresso reviews, from ux-adtools.md].
- **(b) Meta gives free**: the entire CRUD hierarchy natively via Ads Manager UI, the Marketing API,
  and now the Ads CLI/MCP (already the basis of ENG1-31) — this is not a domain to rebuild, only to
  keep in sync (mirrors).
- **(c) Deep-dive questions**: Does `AdCampaignMirror`/`AdSetMirror`/`AdMirror` (already spec'd in
  erp-arch.md) need to represent Advantage+ Shopping/App campaign (ASC/AAC) types, which the
  Marketing API stopped allowing creation/update of from v25.0 onward [eng-meta-tooling.md §c]? Does
  the mirror schema need a `campaign_group`/"Experiments" parent object (see domain 3) that Meta's
  hierarchy actually has above Campaign? What fields does Meta's Ads CLI `campaign create`/`update`
  NOT expose that the raw Marketing API does (gap list), so EngineAction payloads know when to fall
  back to raw API calls?
- **(d) Priority**: **Must-have, but already ~90% built by ENG1-31** — this mission is a gap audit,
  not new construction. Not a Round-1 candidate on its own; fold into whichever mission touches
  mirrors deepest (Mission 4 below).

---

## 2. Automation Rules Engine

- **(a) Leaders ship**: Meta's own **native Automated Rules** already give AND-only conditional
  logic → action (pause/enable/adjust budget/adjust bid/notify) at one object level per rule, up to
  250 rules/account, 37 months of retained data, a built-in "auction overlap" template
  [facebook.com/business/help/1694779440789213, facebook.com/business/help/644860419002064]. Third
  parties (Bïrch/Revealbot) differentiate on: **nested AND/OR logic** (Meta can't), sub-30-minute
  check cadence, cross-platform rules (Meta+Google+TikTok+Snap in one rule set), and Slack-native
  delivery [Capterra Bïrch reviews, from ux-adtools.md P2/P4]. Optmyzr's Rule Engine adds
  cross-metric bid/budget redistribution across campaigns with "partial or full automation" toggles
  [optmyzr.com/solutions/rule-engine]. Madgicx's "Autonomous Budget Optimizer" is really a
  rules-engine specialization (ROAS/CPA-threshold-driven reallocation, capped %) — see domain 4.
- **(b) Meta gives free**: single-level AND-only rules, pause/notify/budget/bid actions, a
  ready-made overlap-prevention template, native 250-rule ceiling. **This materially shrinks what
  OUR engine needs to build** — a from-scratch rules DSL competing head-on with Meta's own free tier
  is low-value; the wedge is what Meta's native rules structurally cannot do (cross-object nested
  logic, WhatsApp delivery, reasoning-with-the-action per ux-adtools.md's AdAmigo pattern).
- **(c) Deep-dive questions**: Should our `EngineAction`/`GuardrailConfig` layer (already spec'd)
  wrap Meta's own native Automated Rules API (create rules server-side, just with a better UI/WhatsApp
  delivery) rather than re-implement condition evaluation ourselves — is there a documented
  Automated-Rules-creation endpoint in the Marketing API/CLI, and does it support the AND/OR nesting
  gap? What's the exact reactive-only limitation (C7 in ux-adtools.md) and can Claude-driven
  proposal-generation (LLM reasoning over InsightSnapshot data) legitimately fill the "un-anticipated
  pattern" gap Bïrch's own rule builder cannot? What condition/action set does a Moroccan SMB solar
  business actually need (cost-per-signature threshold, WhatsApp-reply-rate threshold — not generic
  ROAS) vs. the 250-rule enterprise-scale menu?
- **(d) Priority**: **Must-have** (WhatsApp-delivered, cost-per-signature-scoped, reasoning-attached
  rules is the differentiator per ux-adtools.md's ranked pattern list #1-3) but **build thin on top
  of Meta's native rule primitives where possible, not a from-scratch engine** — avoid the
  Madgicx-style unreliable-execution trap (C4 in ux-adtools.md: "rules... will not run on schedule...
  with no warning or retries").

---

## 3. Experimentation / A-B Testing

- **(a) Leaders ship**: Meta's own **native "Experiments" (A/B Test)** tool already handles the
  statistically-sound version — select 2-5 campaign/ad-set variations differing in exactly one
  variable, Meta auto-splits audience to prevent overlap/delivery bias during the test window, then
  reverts to normal delivery after [facebook.com/business/help/1738164643098669, Jon Loomer Digital].
  Meta's own recommended minimum: 7-14 days, ≥$100/day per variation for 95% confidence. An Oct 2025
  Meta update specifically hardened creative-test delivery-splitting to stop uneven optimization
  mid-test [multiple 2026 sources via search]. Third parties (AdEspresso legacy) built bulk-variant
  generation feeding INTO Meta's test surface, not a competing test engine.
- **(b) Meta gives free**: the entire statistically-valid A/B test mechanism, natively, for free —
  audience-splitting, overlap prevention, winner determination. This is a **skip-Meta-does-it**
  domain almost entirely.
- **(c) Deep-dive questions**: at Taqinor's actual daily budget (50-100 MAD/day, per eng-channels.md),
  Meta's own $100/day-per-variation guidance is **10-20x too expensive to run a real Experiment** —
  what is the right SMB-budget substitute (sequential testing over longer windows? Bayesian
  early-stopping? a documented minimum-viable-sample-size calculator scaled to solar lead volumes,
  not e-commerce purchase volumes)? Does Meta's CLI/MCP even expose Experiments-creation
  programmatically, or is it Ads-Manager-UI-only (a real gap if so — would force a human to click
  "Experiments" manually even in an otherwise-automated pipeline)? What is the correct STAGES.py-
  aligned "winning" metric for a consultative sale (SIGNED count / cost-per-signature, not ROAS/CPA)
  and how does that map onto Meta's own Experiments key-metric selector?
- **(d) Priority**: **Later** — valuable once ad volume is high enough to make a $100/day/variation
  test affordable (i.e., gated behind Taqinor's own budget growth, not a Round-1 build item), but the
  deep-dive should still spec a lightweight "creative testing without formal Experiments" mode (see
  domain 5) usable at current low budget.

---

## 4. Creative Testing Frameworks (systematic hook/creative iteration, distinct from formal A/B)

- **(a) Leaders ship**: this is the layer BELOW formal Experiments — a repeatable process for
  cycling creative variants at low volume. Madgicx's "Creative Tracker"/"Meta Ad Creative Optimizer"
  surfaces which creative wins and auto-scales it [madgicx.com/blog, G2 Madgicx reviews]. Smartly's
  DCO (domain 6) and AdEspresso's bulk-variant generation both feed this loop. ux-adtools.md P3
  documents the actual praised pattern: "which visual/message got more replies" ranked list, not
  abstract CTR scores.
- **(b) Meta gives free**: partial — native Dynamic Creative (domain 6) auto-tests combinations
  within one ad, and native per-ad/per-creative breakdowns in Insights let you rank creatives
  manually; Meta does NOT give a "which creative should I make next" recommendation engine.
- **(c) Deep-dive questions**: at Taqinor's low creative volume (a handful/month per
  ux-adtools.md's adaptation notes), what's the right cadence/structure (e.g., a fixed weekly
  "1 new hook, 1 new visual, keep 1 control" rotation) that avoids both under-testing and
  over-engineering a nonexistent media-buyer role? Should `CreativeAsset.policy_stamp` (already
  spec'd) grow a `test_cohort`/`retired_reason` field so the WeeklyBrief can report "which creative
  drove the lowest cost-per-signature this week" without a bespoke test infra? How does this
  interact with the no-fake-footage constraint (eng-video.md/eng-ugc-static.md) — i.e., is the
  "creative library" primarily real-photo/template-assembled variants, not generative video, for
  Taqinor's own brand?
- **(d) Priority**: **Must-have** — this is the cheap, low-volume-appropriate substitute for formal
  Experiments (domain 3) and the direct implementation of ux-adtools.md's P3/P7 "ranked, traceable
  creative performance" pattern that reviewers explicitly reward.

---

## 5. Budget Optimization (autonomous allocation, not manual rules)

- **(a) Leaders ship**: Meta's own **native CBO / "Advantage+ campaign budget"** already
  auto-distributes one campaign-level budget across ad sets via ML, toward best performers, with
  Meta's own claimed 12% lower cost-per-purchase / up to 17% ROAS lift figures (self-reported)
  [support.smartly.io CBO explainer, multiple 2026 sources]. Madgicx's "Autonomous Budget Optimizer"
  layers a user-defined reallocation-cap on top of ROAS/CPA signals across ad sets — i.e., a stricter,
  guardrail-bounded version of what CBO already does [madgicx.com/blog]. Optmyzr's Budget Pacing adds
  month-level pacing (auto-pause at monthly-cap, auto-resume next month) plus AI spend forecasting
  [optmyzr.com/solutions/budget-management].
- **(b) Meta gives free**: the core cross-ad-set reallocation algorithm (CBO/Advantage+ budget) is
  entirely native and free. **This is the single clearest "skip-Meta-does-it" case in the whole
  taxonomy** — building a competing ROAS-reallocation ML model would race Andromeda's own
  10,000x-complexity retrieval engine [eng-compliance.md/eng-competitors.md], a race the positioning
  research already concluded Taqinor should not enter.
- **(c) Deep-dive questions**: does `GuardrailConfig` (already spec'd: `max_daily_budget_mad`,
  `max_lifetime_budget_mad`, `require_approval_above_mad`) need a monthly-pacing field
  (Optmyzr-style auto-pause-at-cap) distinct from the daily ceiling, given Taqinor's real budget is
  monthly-envelope-shaped, not daily-rule-shaped? Should the engine simply **turn CBO on** at the
  campaign level (a one-line proposal via EngineAction) rather than build any reallocation logic
  itself — i.e., is "propose enabling Meta's own Advantage+ campaign budget, with a spend ceiling"
  the entire scope of this domain for Taqinor? What does Meta's Ads CLI/MCP actually expose for
  reading/setting the CBO toggle programmatically (confirm against `meta ads campaign create/update`
  flags)?
- **(d) Priority**: **Skip-Meta-does-it for the allocation algorithm itself; must-have for the thin
  guardrail/pacing wrapper** (spend ceiling + monthly pacing + one-click CBO-enable proposal) — this
  is a very small, cheap Round-1 scope, not a big build.

---

## 6. Creative testing framework — DCO / Dynamic Creative

- **(a) Leaders ship**: Smartly.io's DCO auto-assembles images/video/headlines/copy/CTA/price-point
  per audience/placement and reprioritizes winners in-flight, at claimed 30x faster production /
  27% average performance lift vs static [smartly.io/product-features/dynamic-creative-optimization,
  get-ryze.ai Smartly review]. This is enterprise-scale creative-variant assembly, not something an
  SMB engine needs to rebuild.
- **(b) Meta gives free**: native **Dynamic Creative** already does exactly this at ad level — up to
  10 images/videos, 5 headlines, 5 primary-text variants, 5 CTAs, Meta mixes/matches and optimizes
  toward winning combos automatically, plus "Text Combinations" specifically for copy permutation
  [Jon Loomer Digital, adlibrary.com Advantage+ Creative guide]. **This is Meta's free, direct
  equivalent of Smartly's paid DCO product** for a single advertiser (Smartly's value-add is
  cross-account/cross-platform assembly at agency scale, not the core DCO mechanic).
  Advantage+ Creative Enhancements (auto-crop, auto-translate, music, etc.) are a separate,
  further-automated layer on top, individually toggleable.
- **(c) Deep-dive questions**: should the engine simply **populate multiple asset slots per ad
  (image/headline/text/CTA variants) and enable native Dynamic Creative**, rather than build any
  combination-testing logic — confirm whether `meta ads creative create`/`ad create` support
  multi-asset Dynamic Creative payloads via the CLI, or whether that's a Marketing-API-only path not
  yet wrapped by the CLI (a real gap to flag if so)? Which Advantage+ Creative Enhancements are
  safe-by-default vs. must-stay-off for Taqinor's brand control (per the founder's own no-fake-footage/
  checked-facts-only rules) — e.g., auto-generated "expand image"/AI backgrounds could violate the
  no-synthetic-install-footage rule if enabled by default?
- **(d) Priority**: **Skip-Meta-does-it for the DCO mechanic itself; must-have is a thin "upload
  N variants, toggle Dynamic Creative on, with brand-safety enhancement toggles pinned off by
  default" proposal flow** — again a small wrapper, not new ML.

---

## 7. Reporting & Attribution

- **(a) Leaders ship**: Madgicx's "One-Click Report" blends Meta+Google+GA4+Shopify+Klaviyo+TikTok
  into one live net-profit/blended-ROAS/MER dashboard, with per-client report instances for agencies
  [madgicx.com/one-click-report, ux-adtools.md P1]. Northbeam's "Clicks + Deterministic Views" model
  is the trust-maximizing pattern: every number traces back to a real, verifiable event rather than a
  black-box model [G2 Northbeam, ux-adtools.md P7/C3]. Triple Whale's Moby is the plain-language
  chat-query layer on top of the dashboard [ux-adtools.md §2].
- **(b) Meta gives free**: native Insights (impressions/spend/CTR/conversions with full breakdown
  dimensions, date-range, custom metrics) plus the new **Ads MCP's "Comprehensive Reporting" and
  Signal Diagnostics categories** (Pixel/CAPI signal-health tooling) already ship free
  [eng-meta-tooling.md §a]. What Meta does NOT and structurally cannot give free: **CRM-verified,
  cost-per-SIGNATURE attribution** — Meta only sees ad-platform-side events, never Taqinor's own
  quote/invoice pipeline.
- **(c) Deep-dive questions**: the `InsightSnapshot` model (already spec'd, generic FK via
  contenttypes) — does it need a join path to `crm.LeadActivity`/`ventes.Devis` (via selectors only,
  per the cross-app-boundary rule) so "coût par signature" is genuinely traceable click→WhatsApp→
  Lead→signed Devis, matching ux-adtools.md's #7 trust-affordance ("every number must be
  click-through-able to the actual record it came from")? What exact CAPI/Signal-Diagnostics data
  does the Ads MCP/CLI expose that OUR reporting can piggyback on instead of re-building signal-
  quality checks from scratch? Does the dashboard need a Meta-vs-ERP-number reconciliation display
  (per ux-adtools.md C2's "never let the dashboard diverge from Meta's own number without a visible
  caveat")?
- **(d) Priority**: **Must-have — this is the single highest-leverage domain**, per
  eng-competitors.md's positioning-gap conclusion: the CRM-verified attribution loop is the one
  capability no competitor (Meta's own connector included) delivers end-to-end for a MENA
  consultative-sale business. Likely already partially built in ENG1-31's "cost-per-signature"
  primitive — the deep-dive should audit exactly how much of this is done vs. still needed
  (drill-down UI, per-creative/per-campaign breakdown, not just an aggregate number).

---

## 8. Alerting

- **(a) Leaders ship**: Bïrch/Revealbot pushes threshold alerts directly into Slack, checked every
  15-30 min in business hours [ux-adtools.md P4/§1]. Improvado's alerting layer pairs the alert with
  a root-cause label (creative fatigue / pixel break / audience saturation), not just "metric
  crossed X" [improvado.io, ux-adtools.md P4].
- **(b) Meta gives free**: native Automated Rules "send notification" action (email/in-app) is the
  free primitive — but it is single-metric, AND-only, no root-cause reasoning, no WhatsApp delivery.
- **(c) Deep-dive questions**: does `GuardrailConfig.notify_emails` (already spec'd) need to become
  `notify_channels` (WhatsApp number + email), matching ux-adtools.md P4's explicit "swap Slack for
  WhatsApp — matches the existing WhatsApp-first CRM contact channel" adaptation note? Can Claude
  itself generate the root-cause line (from InsightSnapshot + EngineAction history) at alert-send
  time, i.e., is root-cause labeling an LLM-reasoning task rather than a rules table — and if so what
  does the alert payload/prompt need (recent budget-change history, creative-swap history, the
  Advantage+ learning-phase-reset risk from eng-meta-tooling.md) to avoid hallucinating a cause (the
  documented MCP failure mode)? What's the silent-failure guard (C4 in ux-adtools.md — "a rule that
  doesn't fire must itself surface a warning") — does `WeeklyBrief` need a "rules that should have
  fired but didn't" self-check?
- **(d) Priority**: **Must-have** (WhatsApp delivery ties directly to founder's own existing channel
  preference and is a documented, cheap differentiator) but scope is thin — mostly a delivery-channel
  + reasoning-prompt spec, not new infrastructure, and overlaps heavily with domain 2 (rules) and
  domain 15 (anomaly detection).

---

## 9. Bulk Operations

- **(a) Leaders ship**: Smartly.io syncs a spreadsheet/feed to auto-create/archive/update ads at
  scale [smartly.io/all-features]. Bïrch's Bulk Editor makes sweeping cross-campaign/ad-set changes,
  and its bulk uploader auto-generates ad variations from a batch of images/videos
  [g2.com/products/birch-ex-revealbot, adlibrary.com bulk-launcher roundup]. AdEspresso's original
  differentiator was exactly this at SMB scale [ux-adtools.md P5].
- **(b) Meta gives free**: native Ads Manager has its own bulk-edit/duplicate tooling in the UI, and
  the CLI is inherently bulk-friendly (scriptable, loop over a list) — this is largely a
  **CLI-scripting exercise on ENG1-31's existing client, not a new subsystem.**
- **(c) Deep-dive questions**: at Taqinor's actual volume (per ux-adtools.md's adaptation table:
  "duplicate-and-tweak 2-3 variants, not mass generation"), is a real bulk-operations UI even
  justified, or does a simple "duplicate this campaign/ad-set N times with these overrides" proposal
  action inside the existing ApprovalsScreen cover 100% of the real need? Where would a genuine bulk
  need arise first — multi-client productization (domain 10), not Taqinor's own single-account use —
  so should this be explicitly deferred to whichever mission specs multi-account?
- **(d) Priority**: **Later** — low urgency at current single-account, low-volume scale; revisit once
  productized for multiple clients (ties directly to domain 10).

---

## 10. Multi-Account Management

- **(a) Leaders ship**: Bïrch's multi-account dashboard lets an agency manage dozens of clients from
  one view, organized into per-client workspaces [g2.com Bïrch]. Madgicx's One-Click Report supports
  unlimited ad accounts per report, up to 50 report instances on top tiers [madgicx.com/one-click-
  report, ux-adtools.md P1].
- **(b) Meta gives free**: Business Manager itself is Meta's native multi-account/multi-client
  container (Partner access, per-client ad accounts — see eng-compliance.md §a-c for the full
  compliance mechanics already researched), but it has no cross-client blended dashboard or
  cross-client automation UI — that layer is 100% third-party-tool territory.
- **(c) Deep-dive questions**: this domain is really "productize ENG1-31 for other clients" — does
  `MetaConnection`/`GuardrailConfig` (already OneToOne→Company per erp-arch.md) cleanly support
  N clients out of the box, or does the ApprovalsScreen/DashboardScreen need an explicit
  client-switcher UI? How does this interact with the already-researched compliance staging
  (eng-compliance.md's Stage 1→2→3 roadmap: Business Verification, per-client system-user tokens,
  separate-ad-account-per-client rule)? Given CLAUDE.md's multi-tenant `Company` scoping is already
  the ERP's base pattern, is there a real gap here beyond "wire the compliance steps," or is this
  mostly already structurally free?
- **(d) Priority**: **Later** (gated on Taqinor actually onboarding a second client, per
  eng-compliance.md's staged roadmap) — but worth a light Round-1 audit to confirm no
  single-tenant assumption has crept into ENG1-31's models, since retrofitting multi-tenant gaps is
  expensive later and cheap to catch now.

---

## 11. Launch Templates

- **(a) Leaders ship**: Bïrch's template-based workflows define a campaign structure once and
  replicate it across audiences/budgets/creative sets, auto-tagging naming-convention tags onto new
  objects as they're created [g2.com Bïrch, adlibrary.com bulk-launcher roundup].
- **(b) Meta gives free**: nothing directly — Ads Manager has no native "campaign template" concept;
  duplication is the closest native primitive.
- **(c) Deep-dive questions**: does Taqinor's three-market-mode quote structure (Résidentiel/
  Industriel-Commercial/Agricole, per CLAUDE.md's quote-generator rule) map onto 3 distinct campaign
  launch templates (different objective/audience/creative defaults per market)? Should
  `EngineAction`'s `payload` schema support a reusable "template" JSON that a WeeklyBrief-driven
  proposal instantiates with per-run overrides (budget, city, promo), rather than every campaign
  proposal being hand-built from scratch by the LLM each time?
- **(d) Priority**: **Must-have, small scope** — directly reduces LLM-proposal-generation risk
  (a templated skeleton is far less likely to hallucinate a malformed campaign than free-form
  generation) and is cheap to spec given the market-mode structure already exists in `ventes`.

---

## 12. Naming Conventions

- **(a) Leaders ship**: Bïrch auto-applies naming-convention tags to new objects at creation time
  [g2.com Bïrch]. UTM-governance vendors (Terminus, UTM.io, Uplifter) generalize this into a
  "Taxonomy Guardian" role + locked shared builder that only emits approved values
  [terminusapp.com, web.utm.io naming guide, uplifter.ai].
  Three common naming models identified: **Cryptic, Positional, Key-Value**
  [linkutm.com/glossary/utm-naming-convention].
- **(b) Meta gives free**: nothing — naming is just a free-text field; Meta enforces no taxonomy.
- **(c) Deep-dive questions**: what positional naming schema fits Taqinor's own dimensions (market
  mode, city, campaign objective, date, creative-cohort) and can it be a pure string-template
  function (`generate_campaign_name(market, city, objective, date)`) enforced at the `meta_client.py`
  call site — i.e., is this a 20-line utility function, not a "system," given the low object volume?
  Does it need DB-level uniqueness/collision handling analogous to the reference-numbering rule
  (`apps/ventes/utils/references.py` — never count()+1, highest-used+1 per company+month) since
  naming collisions across campaigns could cause the same confusion CLAUDE.md's numbering rule
  already guards against for quotes?
- **(d) Priority**: **Must-have, trivial scope** — this is a naming-convention constant/function,
  reusing the exact pattern already proven for `references.py`; fold into whichever mission builds
  domain 11 (launch templates), not its own mission.

---

## 13. UTM Governance

- **(a) Leaders ship**: a canonical source/medium value list + locked builder + master UTM log with
  an owner/status per value + periodic audits [terminusapp.com, prooflytics.io UTM governance guide].
  The core enforcement insight: **stop letting humans type UTM values by hand** — a shared builder
  normalizes/validates/logs every generated link [web.utm.io naming guide].
- **(b) Meta gives free**: native URL Parameters field at ad level (Meta's own UTM-insertion
  mechanic) exists but enforces no taxonomy — any string is accepted.
- **(c) Deep-dive questions**: does `crm.Lead` already capture `fbclid`/`utm_*` at intake (confirm
  against eng-meta-tooling.md's CAPI recommendation to "store fbclid/fbc against the CRM lead at
  capture time")? Should the engine own UTM generation entirely (server-side, at EngineAction-propose
  time, from the same market/city/objective/date dimensions as domain 12's naming function) so a
  human never hand-types a UTM string, closing the loop directly into `InsightSnapshot`/attribution
  (domain 7)? Is a separate "UTM governance" system needed at all, or is it the SAME function as
  domain 12's naming generator, just also stamped into the ad's URL-parameters field — i.e., are
  domains 11/12/13 actually one small piece of shared code, not three?
- **(d) Priority**: **Must-have, and likely mergeable with domain 12** — the deep-dive's real job is
  confirming `crm.Lead`'s existing fbclid/utm capture (prior research flagged this as unconfirmed)
  and specifying the one shared naming/UTM-generation function, not building three separate systems.

---

## 14. Forecasting & Pacing

- **(a) Leaders ship**: Optmyzr's forecasting projects month/quarter-end spend from account
  history + seasonality via proprietary AI; its Budget Pacing auto-pauses at monthly cap and
  auto-resumes next period [optmyzr.com/solutions/budget-management].
- **(b) Meta gives free**: Ads Manager shows an "estimated daily results" range at ad-set creation
  (a rough native forecast) but nothing month-level or pacing-aware; no native auto-pause-at-monthly-
  cap mechanic distinct from a lifetime-budget field.
- **(c) Deep-dive questions**: given Taqinor's budget is a small, fixed monthly envelope (not a
  large-account pacing problem), is "forecasting" even the right framing, or is the real need just
  a simple `spend_this_month / days_elapsed × days_in_month` projection surfaced in the WeeklyBrief,
  cheap to compute from `InsightSnapshot` with no ML? Does `GuardrailConfig` need a
  `monthly_budget_mad` ceiling distinct from `max_daily_budget_mad`, with an EngineAction-proposed
  "pause for the rest of the month" action when projected spend would exceed it?
- **(d) Priority**: **Must-have, trivial scope** — a simple linear projection + monthly-ceiling
  guardrail is enough at Taqinor's scale; do not build Optmyzr-grade seasonality forecasting. Fold
  into domain 5's (budget) mission.

---

## 15. Anomaly Detection

- **(a) Leaders ship**: purpose-built tools (Ads Anomaly Guard: "13 AI detection signals... within
  minutes, not days" covering CPA spikes, conversion drops, inactive conversion actions, broken
  tracking, budget waste) and Improvado's AI Agent explicitly pairs the anomaly with a stated cause
  and routes it to an owner [adsanomalyguard.com, improvado.io]. Common root causes documented:
  bidding-algorithm updates, competitor entry, landing-page conversion-rate drops, ad disapprovals
  reducing coverage. Best-practice alert-threshold guidance: start broad (35-40% deviation), tighten
  gradually to avoid alert fatigue; a commonly-cited concrete rule is "CPA up >30% AND spend >$200"
  [multiple sources, consistent].
- **(b) Meta gives free**: nothing purpose-built — native Automated Rules can approximate a
  threshold-crossing check (domain 2) but with no anomaly-vs-noise statistical distinction and no
  root-cause labeling.
- **(c) Deep-dive questions**: at Taqinor's low daily spend, do the enterprise-scale thresholds
  above (spend >$200, i.e., ~2,000 MAD) even apply, or does the engine need SMB-scaled thresholds
  (percentage-of-daily-budget-based, not absolute-spend-based)? Is a full statistical
  anomaly-detection model justified at low data volume, or is a simpler "3-day rolling average vs.
  today" comparison (cheap, no ML) sufficient and more honest about its own confidence at low
  sample size — avoiding the MCP's own documented hallucination/confabulation failure mode
  (eng-meta-tooling.md (a)) by never presenting a low-confidence pattern-match as a confident causal
  claim? Does the "root cause" step map cleanly onto data the engine already has (recent
  EngineAction history, CreativeAsset swap timestamps, GuardrailConfig changes) rather than needing
  external signals the engine can't see?
- **(d) Priority**: **Must-have, but SMB-scaled and honest about uncertainty** — this is the natural
  extension of domain 8 (alerting) and shares its mission; the deep-dive should explicitly design
  for low sample size (a handful of leads/week) rather than porting enterprise thresholds unchanged.

---

## Cross-cutting findings that reshape the Round-1 mission list

1. **Meta's own free-native layer is bigger than Groupe ENG's original scope assumed.** CBO
   (budget optimization), Dynamic Creative (DCO), and Experiments (A/B testing) are ALL free,
   native, and already ML/statistically sound — three of the fifteen taxonomy domains are
   "skip-Meta-does-it" outright, and two more (budget, DCO) reduce to a thin "propose enabling the
   native feature, with a guardrail" wrapper rather than new subsystems. This meaningfully shrinks
   Round 2's real build surface vs. a naive "match every competitor feature" reading of the mission.
2. **Domains 11/12/13 (launch templates, naming conventions, UTM governance) are very likely ONE
   small shared function**, not three systems — a deep-dive should resist over-scoping them
   separately.
3. **Domains 8/15 (alerting, anomaly detection) are one mission**, not two — root-cause-labeled,
   WhatsApp-delivered, SMB-scaled alerts is a single coherent deliverable.
4. **Domain 7 (reporting/attribution) is confirmed, again, as the highest-leverage domain** —
   consistent with eng-competitors.md's positioning-gap conclusion — and should get the most
   dedicated deep-dive attention of the whole round, including auditing exactly how much ENG1-31
   already built vs. still needs (drill-down, not just the aggregate number).
5. **Domains 9/10 (bulk ops, multi-account) are genuinely Later**, gated on productization to a
   second client — a light structural audit is worth doing now (cheap), but no real build.

---

## PROPOSED ROUND-1 MISSION LIST (4-6 deep-dive agents, exact scopes)

**Mission A — "Guardian": Automation rules + alerting + anomaly detection (domains 2, 8, 15).**
Scope: (i) confirm whether Meta's Ads CLI/Marketing API exposes native-Automated-Rules creation
programmatically (a direct doc/API check, not a search summary) and whether OUR engine should wrap
that primitive vs. build condition-evaluation itself; (ii) spec the WhatsApp-delivered alert payload
(channel, message shape, root-cause-reasoning prompt sourced from InsightSnapshot/EngineAction
history) and a "silent-failure self-check" for `WeeklyBrief`; (iii) spec an SMB-scaled (not
enterprise-absolute-spend) anomaly threshold model appropriate to Taqinor's low weekly lead volume,
explicitly designed to avoid the MCP's documented hallucination/confabulation failure mode. Output:
concrete model/field additions to `GuardrailConfig`/`EngineAction`/`WeeklyBrief`, a WhatsApp-delivery
integration point, and a short list of Meta-native-rule capabilities to wrap rather than rebuild.

**Mission B — "Treasury": Budget optimization + forecasting/pacing (domains 5, 14).**
Scope: (i) confirm exactly what the Ads CLI/MCP exposes for reading/toggling CBO/"Advantage+ campaign
budget" at the campaign level, and spec the one-click "enable CBO with a spend ceiling" EngineAction
proposal; (ii) spec a `monthly_budget_mad` guardrail field + simple linear month-end spend projection
(no ML) surfaced in `WeeklyBrief`, with an auto-pause-proposal when projected spend would breach the
monthly ceiling. Output: minimal `GuardrailConfig` schema additions, one new EngineAction
`action_type` (enable_cbo / pause_for_month), and confirmation this domain needs no new ML.

**Mission C — "Creative Science": Creative testing framework + DCO + Experiments (domains 3, 4, 6).**
Scope: (i) spec a low-volume-appropriate weekly creative-rotation cadence (not formal Meta
Experiments, which needs ≥$100/day/variation — 10-20x Taqinor's whole budget) with a
cost-per-signature-ranked creative list in `WeeklyBrief`; (ii) confirm whether the CLI/MCP supports
multi-asset Dynamic Creative payloads (image/headline/text/CTA arrays) at ad-creation time, and spec
which Advantage+ Creative Enhancements must default OFF to respect the no-fake-footage/checked-facts
rules; (iii) spec `CreativeAsset` schema additions (test_cohort/retired_reason) needed to support (i)
without new test infrastructure. Output: creative-rotation spec, Dynamic-Creative payload shape,
CreativeAsset field additions, explicit enhancement-toggle default list.

**Mission D — "Attribution Spine": Reporting & attribution deep audit (domain 7, standalone —
the highest-leverage domain).**
Scope: (i) audit exactly what ENG1-31's cost-per-signature primitive already computes vs. what's
still missing (per-campaign/per-creative drill-down, not just an aggregate); (ii) confirm/fix
whether `crm.Lead` currently captures `fbclid`/`utm_*` at intake (flagged unconfirmed in prior
research) and spec the selector-only read path from `adsengine` into `crm`/`ventes` for a genuinely
click-through-able number (ad click → WhatsApp conversation → Lead → signed Devis); (iii) spec a
Meta-number-vs-ERP-number reconciliation display so any divergence is visible, never silent. Output:
a `InsightSnapshot`-to-CRM join spec, a confirmed or newly-added `fbclid`/`fbc` capture point on
`crm.Lead`, and a drill-down UI spec for `DashboardScreen`.

**Mission E — "Launch Kit": Templates + naming + UTM governance, unified (domains 11, 12, 13).**
Scope: spec the ONE shared naming/UTM-generation function (positional schema: market mode × city ×
objective × date × creative-cohort) used both for object naming and for URL-parameter/UTM stamping
at EngineAction-propose time, plus 3 launch-template skeletons (Résidentiel / Industriel-Commercial /
Agricole) matching the existing quote-generator market modes, each pre-filled with objective/audience
defaults an LLM proposal instantiates rather than free-generates from scratch. Output: one utility
function spec (naming+UTM), 3 template JSON skeletons, confirmation this fully replaces what would
otherwise be three separate systems.

**Mission F (light, optional — fold into A or D if the round is capped at 5) — "Scale Check":
Multi-account + bulk-ops structural audit (domains 1 gap-list, 9, 10).**
Scope: a read-only audit (no build) confirming (i) `MetaConnection`/`GuardrailConfig`'s OneToOne→
Company shape has no single-tenant assumption that would break onboarding a second client per
eng-compliance.md's staged roadmap; (ii) a gap-list of Marketing-API-only campaign types (ASC/AAC)
or CLI-missing fields the mirror models don't yet represent (domain 1); (iii) confirm no near-term
bulk-operations build is needed beyond a simple "duplicate with overrides" EngineAction, deferring
real bulk tooling to the second-client stage. Output: a short structural-risk list, not new code.

---

## Sources referenced in this map (in addition to the six prior-research files)

- Meta Automated Rules: https://www.facebook.com/business/help/1694779440789213 ,
  https://www.facebook.com/business/help/644860419002064
- Meta Experiments/A-B test: https://www.facebook.com/business/help/1738164643098669
- Meta CBO/Advantage+ campaign budget: https://support.smartly.io/hc/en-us/articles/360009226833
- Meta Dynamic Creative: Jon Loomer Digital (jonloomer.com/dynamic-creative), adlibrary.com
  Advantage+ Creative guide
- Optmyzr: https://www.optmyzr.com/solutions/rule-engine/ ,
  https://www.optmyzr.com/solutions/budget-management/
- Madgicx: https://madgicx.com/one-click-report , https://madgicx.com/blog (autonomous budget/
  creative optimizer)
- Smartly.io: https://www.smartly.io/all-features ,
  https://www.smartly.io/product-features/dynamic-creative-optimization
- Bïrch/Revealbot: https://www.g2.com/products/birch-ex-revealbot/reviews , https://bir.ch/launch
- UTM governance: https://www.terminusapp.com/ , https://web.utm.io/blog/utm-naming-conventions-guide/ ,
  https://prooflytics.io/blog/utm-governance-guide , https://linkutm.com/glossary/utm-naming-convention
- Anomaly detection: https://adsanomalyguard.com/ , https://improvado.io/blog/marketing-anomaly-
  detection-automated-alerts
- Plus all six prior-session scratchpad files (paths in mission preamble) and erp-arch.md /
  plan-format.md.
