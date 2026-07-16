# Creative Science — variants without AI (spec-grade)

Deep-dive for TAQINOR's autonomous Meta-ads engine. Date: 16 Jul 2026. Builds on prior dossiers
already on disk (paths in the mission preamble) — not re-derived here except where load-bearing.
Groupe ENG (ENG1-31, `docs/PLAN.md`) is spec'd/merged as PLAN TEXT but **all 31 tasks are still
unbuilt `[ ]`** (confirmed in `scope-repo.md` §5) — every field/model addition below is proposed
as an EXTENSION to that not-yet-built spec, not a change to running code.

**Sibling dossier note.** Part (a)'s exit criterion depends on a Bayesian bandit posterior
("the bandit signal") that is the subject of a **separate, parallel mission (`dd-science-core`,
not yet on disk as of this writing — see `scope-science.md` Missions S1-S3)**. This dossier
defines the **interface contract** the rotation protocol needs from that signal (what question
it must answer, at what confidence, how often) and proposes an **interim, self-consistent design**
grounded in `scope-science.md`'s own findings (beta-binomial Thompson sampling, GrowthBook as
reference implementation) so this spec is usable standalone — but the exact confidence thresholds
are `dd-science-core`'s to finalize, not this dossier's.

Taqinor reality used throughout: 100 MAD/day ceiling today (~$10/day), scaling to maybe 500
MAD/day; 5-15 leads/week; a handful of signatures/month. All Meta-side numbers below are tagged
[VERIFIED] (fetched directly from a Meta-owned page in this pass) or [UNVERIFIED] (secondary/
practitioner, tagged with source).

---

## (a) Weekly-rotation protocol — the low-volume substitute for formal split tests

### Why not a formal test
Meta's own Split Testing API guide publishes **no minimum budget/duration** [PRIMARY,
`developers.facebook.com/docs/marketing-api/guides/split-testing/`, confirmed in `scope-science.md`
§1]; secondary practitioner consensus converges on ≥$100/day **per variation** for a
meaningful formal Experiment [UNVERIFIED-CLUSTER, `scope-science.md` §1, §3 of
`scope-features.md`'s Domain 3]. At 100-500 MAD/day TOTAL (~$10-50/day), a 2-variant formal test
would need 10-20× Taqinor's entire budget. Formal Experiments are therefore **out of scope until
budget grows**; the engine needs its own light rotation instead.

### N ads live per ad set: **3** (1 champion + 2 challengers)
- Meta's own `asset_feed_spec` hard caps (bodies/titles/descriptions/CTAs ≤5, images/videos ≤10,
  30 assets total) [VERIFIED, `developers.facebook.com/docs/marketing-api/ad-creative/
  asset-feed-spec/options/`, fetched directly] apply to a single Dynamic-Creative AD, not to how
  many separate ADS an ad set should hold — that number is secondary/practitioner-only: "6 or
  fewer, 3-5 is the sweet spot" [UNVERIFIED, multiple practitioner sources, could not confirm
  against a directly-fetched Meta help page in this pass — `facebook.com/business/help/
  1346816142327858` exists but returned only its title, not body text, to WebFetch].
- At Taqinor's real budget, thinner is better: 3 ads/ad set means each ad gets roughly a third of
  the ad set's daily spend — already thin for a bandit to read cleanly. **2 challengers, not 4-5**,
  keeps each arm's weekly impression count high enough to say anything at all, per `scope-science.md`
  §2's MDE concern (small-N regime, likely underpowered on cost-per-signature specifically — see
  the rung table below).
- **1 slot is always the champion** (current best-known arm) and is NEVER swapped out purely on a
  calendar tick — only on a bandit-losing signal (below). This guarantees the ad set never goes
  to zero live creative and never fully "restarts" its delivery signal every week.

### Challenger cadence: weekly clock **+** frequency-triggered early refresh, whichever comes first
- **Primary cadence**: the Monday `WeeklyBrief` generation (ENG11, already spec'd, Celery
  `adsengine.generate_weekly_brief`) is the fixed evaluation point — not necessarily a fixed swap
  point. Every Monday, the engine evaluates the bandit signal (below) for every live challenger.
- **Minimum exploration floor before any exit decision**: a challenger must be live **≥7 days
  AND ≥1,000 impressions** before it is eligible to be judged a loser — below that floor, the
  bandit signal is definitionally too thin to trust (an untested arm should never be starved
  before it's had a fair look; this mirrors GrowthBook/Thompson-sampling's own
  minimum-exploration-floor concept, `scope-science.md` §2/S1). 1,000 impressions is a
  provisional floor sized for Taqinor's current reach, not a sourced constant — `dd-science-core`
  should replace it with a derived number once the MDE math (Mission S1) is worked through.
- **Early-refresh override**: if a live ad's **frequency** (avg impressions/person) crosses ~3-4
  before the weekly clock ticks, propose a swap immediately rather than waiting — this is the
  standard "creative fatigue" leading indicator [UNVERIFIED-CLUSTER, practitioner consensus,
  `scope-features.md` Domain 4/15], and matters more at Taqinor's small local audience where
  frequency can climb fast on a small budget.
- **Maximum lifespan cap**: even an ad the bandit hasn't yet flagged a clear loser must be
  force-reviewed after **3 weeks** live — avoids a "no signal either way" ad lingering forever by
  default (ties to the anomaly-detection domain's silent-failure guard, `scope-features.md`
  Domain 15).

### How a challenger enters: from `CreativeBacklog`, gated
Every Monday evaluation that frees a slot (a loser retired, or an empty challenger slot) pulls the
next eligible item from `CreativeBacklog` (schema in part c) in priority order, filtered to:
`status='queued'`, `earliest_launch_date <= today`, `asset.policy_stamp.passed = True`,
`target_campaign` matching the ad set's market mode. This becomes a **proposed** `EngineAction`
(`action_type='launch_challenger'`) in the existing approve→apply flow (ENG7) — **never auto-applied**
even if `GuardrailConfig.auto_rotate_creative` (ENG8) is on, unless that toggle is explicitly set;
default is proposal-only, matching ENG's existing default-off automation posture.

### How a loser exits: the bandit-signal interface + a rung-gated authority table
**Interface contract with `dd-science-core`**: the rotation protocol needs, per live ad, a single
number — **P(this arm is best)**, a posterior probability from a beta-binomial Thompson sampler
over the ad set's live arms (interim design per `scope-science.md` §2/§5: `numpy.random.beta`
posterior draws, no external stats library needed at this scale). A challenger is eligible to be
retired when, past the minimum-exploration floor, its P(best) has been **below 15%** for **2
consecutive weekly evaluations** (a two-strike rule — a single bad week is noise at this volume,
not a verdict) **and** at least one other live arm has a higher P(best). The champion slot itself
can also lose its "champion" status this way (a challenger that overtakes it is promoted; the
former champion becomes a normal challenger next round, not necessarily instantly retired — gives
it one more evaluation cycle before elimination, an extra hedge against noise given the small-N
regime). **These exact thresholds (15%, two-strike) are this dossier's interim proposal — treat
as provisional until `dd-science-core`'s MDE math (Mission S1) either confirms or replaces them.**

**Which metric feeds the bandit — the rung-gated authority table** (this is the actual governing
rule, because at Taqinor's volume different rungs of the funnel have wildly different sample
sizes):

| Funnel rung | Approx. weekly volume/ad set | Bandit-autonomous? | Notes |
|---|---|---|---|
| Impressions → CTR/CPC | Hundreds-low thousands | **Yes** — routine bandit input | Only rung with enough weekly N for the Thompson sampler to say anything with real confidence at 3 arms. |
| Ad click → WhatsApp conversation started | Single/low double digits | **Gated** — bandit computes it, but the resulting `launch_challenger`/retire proposal still needs human approval before apply | Volume too thin for full autonomy; still directionally useful ("3 conversations vs 0 is not noise"), per `scope-science.md` §2's own framing. |
| Conversation → qualified lead → SIGNED (cost-per-signature) | A handful/month, **not** per ad set/week | **Never autonomous** | Reported in `WeeklyBrief` for human judgment only; too sparse to ever gate an automatic pause/retire decision. Retiring an ad on a cost-per-signature swing at this N would very likely be reacting to pure noise. |

This table is the Round-1 synthesis this dossier owes `scope-science.md`'s open question ("which
ladder rung has enough volume to run ANY statistical test") — it is the actual deliverable the
retirement logic is built from, pending `dd-science-core`'s confirmation/replacement of the
specific thresholds.

### Naming that encodes variant lineage
Two encodings, serving different consumers — a human-readable string (for Meta's own UI/Ads
Manager, where Taqinor staff will actually look at names) and a queryable FK (for the engine).

**String** (extends `scope-features.md` Domain 12's positional-naming proposal with a lineage
segment):
```
{market}-{city}-{objective}-{yyyymm}-H{hook_id}-V{visual_id}-G{generation}
e.g.  RES-CASA-LEADS-202607-H03-V11-G1
```
`G0` = an original, human-uploaded creative; `G1+` = a machine-recombined variant (part b),
incrementing per recombination hop. A single positional-naming utility function (already proposed
in `scope-features.md`'s cross-cutting synthesis as likely shared code across Domains 11-13)
should own this format so it's generated once, at `EngineAction`-propose time, never hand-typed.

**FK/fields on `CreativeAsset`** (new fields, additive to the model already spec'd in
`erp-arch.md`/ENG15 — `kind`, `file_key`, `title`, `policy_stamp`, `uploaded_by`, `status` stay
unchanged):
- `hook_id` (str/int — groups every asset sharing the same headline/hook line, across visuals)
- `visual_id` (str/int — groups every asset sharing the same image/footage, across hooks)
- `generation` (int, default 0)
- `parent_asset_id` (self-FK, nullable — the specific asset a recombination was generated from)
- `test_cohort` (str — this week's/this batch's rotation-round identifier, so `WeeklyBrief` can
  report "which cohort is live now")
- `retired_reason` (str, nullable — `bandit_loss` / `manual` / `expired_3wk` / `policy_revoked`)

The FK chain (`parent_asset_id` self-joins) is what actually makes lineage queryable ("show me
every descendant of hook H03") — the string is for humans reading Ads Manager, not for the engine
to parse back.

---

## (b) Recombination without AI — the variant matrix

### Component decomposition on `CreativeAsset`
New fields (additive, alongside the lineage fields above): `hook_text` (the headline/hook line),
`primary_text` (body copy), `headline` (Meta's short-title field), `description` (Meta's
description field), `cta_type` (one of Meta's `call_to_action_types` enum values). These map
1:1 onto Meta's own `asset_feed_spec` field names [VERIFIED, same fetch as above] — not a
made-up taxonomy, the actual fields Meta's API expects, which keeps the mapping from
`CreativeAsset` → Meta ad-creative payload trivial and avoids a translation layer.

### Deterministic recombination = winning hook × other visuals, via the already-specced adapters
This is genuinely a **template-substitution operation, not generation** — no new pixels, no new
spoken words, only re-assembly of already-approved, already-real material. That property is what
lets it satisfy CLAUDE.md's/ENG16's no-fake-footage/checked-facts-only compliance rule by
construction: the adapters never synthesize anything, they only re-lay-out or re-caption an
already-real asset.

**Static path — Templated.io** [VERIFIED, `templated.io/docs/renders/create/`, fetched directly]:
`POST /v1/render` with `template` = Taqinor's own pre-built brand template (logo/price-frame/CTA
positions fixed once by a human designer) and a `layers` object substituting only `text`/
`image_url`/`color` fields per call. Response returns a rendered image URL **synchronously in
~2 seconds**, or via `webhook_url` for a bulk/async batch. This is exactly the "hook × visual"
cross-product operation: for winning `hook_id=H03`, call render once per candidate `visual_id`,
substituting `layers.text = hook_text`, `layers.image_url = candidate_visual.file_key public URL`,
`layers.cta_text = cta_type` label — each call produces one new, fully deterministic
`CreativeAsset` row.

**Video path — ZapCap** [VERIFIED, `platform.zapcap.ai/docs/guides/tasks/`, fetched directly]:
ZapCap's own documented mechanic — `transcriptTaskId` lets you **"use the same transcript for
multiple videos"** without re-transcribing — is the deterministic recombination primitive for
video "cut variants": same real footage, same real spoken transcript, different `templateId`
(caption visual style) = a legitimate new variant, never synthetic content. This is a narrower
recombination than the static path (you can vary the CAPTION TEMPLATE deterministically, not the
underlying footage/hook — a genuinely new spoken hook on different footage still needs a human to
shoot/select real content, which is correct: ENG's own policy already restricts video sourcing to
real footage).

### The generation task
Propose `apps/adsengine/tasks.py`: `generate_recombination_batch(company_id, winning_hook_asset_id,
visual_ids=None, cap=2)` (Celery task, triggered from a `EngineAction`-approved proposal, never
automatically):
1. Load the winning hook's `CreativeAsset` (must be `status='approved'`,
   `policy_stamp.passed=True`).
2. Candidate visuals: explicit `visual_ids`, or auto-selected —
   `CreativeAsset.objects.filter(company=company, status='approved').exclude(hook_id=winning
   hook's hook_id)` — i.e. visuals not already paired with this hook, so the batch always adds
   genuinely new combinations, never duplicates.
3. **Cap the batch at 2** per run (matches part (a)'s 2-challenger-slot design — a recombination
   batch should produce exactly enough new challengers for the next rotation round, not a flood
   that outpaces what the engine can ever test).
4. Dispatch to the Templated or ZapCap adapter per `visual.kind` (static/real_footage), landing
   each result as a new `CreativeAsset(status='pending_policy_review', generation=parent.generation
   +1, parent_asset_id=winning_hook_asset.id, hook_id=winning_hook_asset.hook_id,
   visual_id=candidate.visual_id, batch_id=<new CreativeGenerationBatch>)`.

### Policy-stamp flow for machine-generated variants — human approves the BATCH once
New model `CreativeGenerationBatch` (`company` FK, `source_hook_asset` FK, `visual_ids` list,
`created_at`, `status` [pending/approved/rejected], `reviewed_by` FK, `reviewed_at`). Every
`CreativeAsset` produced by one `generate_recombination_batch()` call shares one `batch_id`. The
approval-inbox extension (built on ENG25's existing pattern) shows the **whole batch as one card**
— all 2 variants side by side (they are template-driven and visually predictable, unlike a
free-form AI-generation batch, so a single human glance suffices) — with **one** approve/reject
action that, in a single transaction, flips every member `CreativeAsset.policy_stamp.passed` from
pending to `True` (approve) and moves them to `CreativeBacklog` as `status='queued'`, or discards
the whole batch (reject). This satisfies the mission's "human approves each batch ONCE before it
enters the backlog" requirement literally — batch-level, not per-variant, which is what keeps the
2-variants-a-week cadence genuinely cheap for a human to review.

---

## (c) `CreativeBacklog` + `FlightPlan` as data — the 3-6 month autonomous supply

### `CreativeBacklog` item schema (new model, `apps/adsengine/models.py`)
- `company` FK
- `asset` FK → `CreativeAsset` (the ad-ready creative)
- `target_campaign` FK → `AdCampaignMirror`, nullable (a queued item may target a market mode in
  general — Résidentiel/Industriel-Commercial/Agricole, per `scope-features.md` Domain 11 — before
  a specific live campaign exists to assign it to)
- `earliest_launch_date` (date — respects seasonal timing; an item is never eligible before this)
- `seasonal_tag` (str/enum, e.g. `ete_pointe_solaire` / `rentree_agricole` / `evergreen`)
- `priority` (int — tie-break ordering among simultaneously-eligible items)
- `status` (`queued` / `launched` / `retired`)
- `launched_at`, `retired_at`, `retired_reason`
- `source` (`manual_upload` or FK → `CreativeGenerationBatch`, so every backlog item's provenance
  is traceable back to a human upload or an approved recombination batch — no untraceable origin)

### `FlightPlan` schema (new model + child `FlightPlanPhase`)
`FlightPlan`: `company` FK, `name`, `start_date`, `end_date`, `autonomy_enabled` bool (default
False — the actual gate that turns the weekly-rotation loop on for this plan's campaigns).
`FlightPlanPhase` (FK → FlightPlan): `phase_start`, `phase_end`, `test_roadmap_phase` (enum —
`exploration` (early, no prior winner: broader native-DCO bootstrap, see part e) or `exploitation`
(a rough winner exists: our own discrete-ad rotation, part a)), `template_id` (references the
launch-template skeleton per market mode, `scope-features.md` Domain 11), `budget_mad_daily`,
`target_campaign` FK (nullable until launched).

### Validation before autonomy can start — two checks, not one
The mission's example ("≥12 approved creatives for 3 months") is a **floor**, sized to roughly
one new creative a week — appropriate as a MINIMUM below which autonomy must not enable, but not
a healthy target on its own, because a floor built entirely from recombinations of one hook gives
no real message diversity. Two checks, both required:

1. **Volume floor**: `CreativeBacklog.objects.filter(company=company, status='queued',
   asset__policy_stamp__passed=True, earliest_launch_date__lte=plan.end_date).count() >= ceil(
   weeks_in_plan × 1)` — i.e. roughly 12 for a 13-week/3-month plan, matching the mission's own
   example exactly, derived here from "at least one ready item per week of the plan," which is
   the true minimum needed for the weekly rotation (part a) to never run dry.
2. **Hook-diversity floor**: `CreativeBacklog...values('asset__hook_id').distinct().count() >= 4`
   for the same 3-month window — prevents a backlog that is technically ≥12 items but is really
   12 visual recombinations of a single hook, which would let the rotation cycle visuals forever
   without ever testing a genuinely new message, quietly defeating the point of "weekly rotation."

`FlightPlan.autonomy_enabled` may only be set True when both checks pass for every phase in the
plan (checked at save-time in the serializer/service layer, not just documented) — this is the
gate the mission explicitly asked for ("validation that a flight plan has enough material before
autonomy starts").

### "Backlog low" alert threshold
A leading-indicator check, not a "hit zero" lagging one: fires a WhatsApp `EngineAlert` (ENG13)
when `CreativeBacklog.objects.filter(status='queued', earliest_launch_date__lte=today).count()`
covers **fewer than 3 weeks** of the plan's weekly challenger-introduction rate (i.e., fewer than
~2-3 ready items remain, given the 2-challenger-per-week design in part a) — gives roughly 3 weeks
of runway to produce or approve more material (via part b's recombination batches or a fresh
manual upload) before the rotation protocol would actually run dry and be forced to re-run a
stale champion indefinitely.

---

## (d) Page-post creation via Graph API (`pages_manage_posts`) — verdict: **gated, not now**

### Feasibility findings
- **App Review is required** [PRIMARY, `developers.facebook.com/docs/permissions/`, fetched
  directly — "App Review Required: Yes"], with hard dependencies on `pages_read_engagement` and
  `pages_show_list`. This is a genuinely separate compliance step from `ads_management`
  (Marketing API scope), which per prior research (`eng-meta-tooling.md`) needed **no App Review**
  to reach via the Ads MCP/CLI OAuth path for basic use.
- Meta's stated #1 rejection reason for App Review is **vague justification** [UNVERIFIED, search-
  synthesized from Meta's own review guidance]; a submission needs a concrete, demonstrable
  page-posting FEATURE and a <2-minute screencast of it working — this does not exist yet for
  Taqinor and would be new build work, not a config flag.
- Business Verification's exact requirement for THIS specific permission was not confirmed
  ("not mentioned" on the fetched permissions page) [UNVERIFIED — the general Marketing API
  Access-Tier Business-Verification requirement already confirmed in `eng-meta-tooling.md` may or
  may not extend identically to the Pages API surface; not independently checked in this pass].

### The narrower path that likely covers the actual named use case
The mission's own framing — "boosted-post style tests or content cadence" — is achievable WITHOUT
`pages_manage_posts` at all: creating a normal Marketing-API ad with an `object_story_spec`
(message + `page_id`) makes Meta **create the underlying page post as a side effect** of ad
creation [PRIMARY, confirmed the `/page/ads_posts` reference endpoint exists at Graph API v25.0,
`developers.facebook.com/docs/graph-api/reference/page/ads_posts/`] — entirely inside the
`ads_management` scope ENG already has, no second App Review. This covers "boosted-post style
tests" completely; it does NOT cover organic, spend-free content-cadence posting (a post that
exists with no ad attached, ever) — that residual use case is the only thing `pages_manage_posts`
would actually add.

### Verdict
**Gated, not Round-1.** Reasons: (1) a new, distinct App Review submission with its own
justification/screencast burden that nothing in ENG1-31 or this mission's other parts needs;
(2) the concretely-named use case (boosted-post tests) is already reachable via the existing
`object_story_spec` mechanic inside the ads-engine's current scope; (3) organic-only publishing is
adjacent-but-separate from an ADS engine, and CLAUDE.md's fewest-steps discipline argues against
opening a new publishing surface no part of ENG1-31 asked for. If Taqinor later wants genuine
spend-free organic posting as its own feature, that should be scoped as its own future mission
with its own App Review request — not folded into Creative Science.

---

## (e) Dynamic Creative fit — when to hand Meta a multi-asset DCO ad instead

### Confirmed native limits [VERIFIED, `developers.facebook.com/docs/marketing-api/ad-creative/
asset-feed-spec/options/`, fetched directly]
`asset_feed_spec`: images ≤10, videos ≤10, bodies ≤5, titles ≤5, descriptions ≤5,
`call_to_action_types` ≤5, **max 30 total assets** across all fields combined. This resolves
`scope-features.md` Domain 6's open question with a confirmed primary number (previously only
UNVERIFIED-CLUSTER via Jon Loomer Digital).

### Decision rule
**Use native Dynamic Creative when:**
- Bootstrapping a brand-new campaign/`FlightPlanPhase` with **no prior winner data** — Meta's own
  delivery-optimization needs signal volume itself and can explore combinations faster than a
  human-sequenced weekly rotation, and there is nothing yet for our bandit to condition on.
  This is the `test_roadmap_phase='exploration'` case in part (c)'s `FlightPlanPhase` schema.
- The component counts fit inside the caps above.
- Per-combination attribution is NOT needed for this phase — only "did the campaign perform,
  overall."

**Use our own discrete-ad weekly rotation (parts a/b) when:**
- The bandit needs **per-arm attribution** to compute `P(best)` per hook/visual combination —
  DCO pools all impressions into ONE ad object; whether Meta's Insights API exposes a genuine
  per-sub-combination performance breakdown inside a single Dynamic-Creative ad was **not
  confirmed in this pass** (the asset-feed-spec pages found describe the CREATION shape, not a
  reporting breakadown) — flag this explicitly as an **open question**, not a confirmed gap: if
  `dd-science-core` or a future check confirms Meta DOES expose that breakdown, DCO's attribution
  weakness may be smaller than assumed here; until then, treat discrete ads as the safer, provably-
  attributable default.
- A rough winner already exists and the goal is now to iterate ON it (test its hook against a new
  visual, part b) — this is precisely the `test_roadmap_phase='exploitation'` case, where the
  question is "does this specific new combination beat the specific current champion," which is a
  per-arm question DCO isn't built to answer back to us.
- Budget is thin (100-500 MAD/day): running DCO's own internal exploration AND our discrete bandit
  simultaneously on the same ad set would split an already-small signal two ways for no benefit —
  **pick one mechanism per ad set, never both at once.**

**Practical rule for Taqinor**: default to discrete-ad rotation everywhere the bandit is meant to
learn something actionable (hook-vs-hook, visual-vs-visual decisions feeding part-b recombination);
reserve native Dynamic Creative for a single bootstrap pass at the start of a `FlightPlanPhase`
with zero prior data, then hand off to the discrete rotation once ANY signal exists — never run
both continuously on the same ad set.

---

## Consolidated model/field additions (for a future `ADSENG` plan task, not built here)

- **`CreativeAsset`** (extends ENG15's existing model): + `hook_id`, `visual_id`, `hook_text`,
  `primary_text`, `headline`, `description`, `cta_type`, `generation`, `parent_asset_id` (self-FK),
  `test_cohort`, `retired_reason`, `batch_id` (FK → `CreativeGenerationBatch`, nullable).
- **`CreativeGenerationBatch`** (new): `company`, `source_hook_asset` FK, `visual_ids`,
  `created_at`, `status`, `reviewed_by`, `reviewed_at`.
- **`CreativeBacklog`** (new): schema in part (c).
- **`FlightPlan`** + **`FlightPlanPhase`** (new): schema in part (c), incl. `autonomy_enabled`
  gate + the two-check validation (volume floor + hook-diversity floor).
- **`EngineAction.action_type`**: + `launch_challenger`, `retire_challenger`,
  `generate_recombination_batch`.
- **Celery task**: `adsengine.generate_recombination_batch(company_id, winning_hook_asset_id,
  visual_ids, cap)` — proposal-triggered only, never on a schedule.
- **`creative_factory.py`** (ENG17, already spec'd as key-gated adapters incl. Templated/ZapCap):
  extend with the deterministic `layers`-substitution call shape (static) and
  `transcriptTaskId`-reuse call shape (video) described in part (b) — still NO-OP without a key,
  still no new pip dependency (both are plain `httpx` calls, matching ENG17's own existing
  no-new-dependency constraint).

---

## Sources

Primary (fetched directly in this pass):
- [Asset Feed Spec — Options (limits)](https://developers.facebook.com/docs/marketing-api/ad-creative/asset-feed-spec/options/) — images/videos ≤10, bodies/titles/descriptions/CTAs ≤5, 30 total assets
- [Permissions Reference — `pages_manage_posts`](https://developers.facebook.com/docs/permissions/) — App Review required, dependencies
- [Graph API v25.0 Reference — Page `ads_posts`](https://developers.facebook.com/docs/graph-api/reference/page/ads_posts/) — confirms the object_story_spec/boosted-post mechanic exists
- [Templated API — Create a render](https://templated.io/docs/renders/create/) — `POST /v1/render`, `layers`, `webhook_url`, sync ~2s
- [ZapCap Docs — Captioning Tasks](https://platform.zapcap.ai/docs/guides/tasks/) — `transcriptTaskId` reuse mechanic
- [Meta Split Testing API guide](https://developers.facebook.com/docs/marketing-api/guides/split-testing/) (re-confirmed via `scope-science.md`)

Secondary/UNVERIFIED (flagged inline where relied upon):
- Practitioner "6 or fewer / 3-5 sweet spot" ads-per-ad-set guidance, creative-fatigue frequency
  thresholds (~3-4) — could not corroborate against Meta's own help-center page body in this pass
  (`facebook.com/business/help/1346816142327858` returned only its title to WebFetch)
- Meta App-Review "#1 rejection reason = vague justification" — search-synthesized, not a direct
  Meta-owned quote

Prior-session dossiers relied on (not re-fetched): `scope-science.md`, `scope-features.md`,
`scope-repo.md`, `erp-arch.md`, `eng-ugc-static.md` (ZapCap/Templated pricing/BOM context),
`eng-meta-tooling.md` (Access Tier / App Review baseline).
