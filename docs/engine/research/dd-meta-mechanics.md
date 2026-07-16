# Meta Mechanics Precision Pass — Engine/Meta Boundary

Research date: 16 Jul 2026. Answers Mission S2 flagged in `scope-science.md`. Builds on
`eng-meta-tooling.md` (MCP/CLI/Marketing API access layer — not re-derived here) and
`eng-competitors.md`. Every claim tagged **[VERIFIED]** (primary Meta doc successfully fetched/
quoted), **[VERIFIED-partial]** (primary doc fetched but summarizer truncated/omitted detail —
flagged where it matters), or **[UNVERIFIED]** (secondary/blog sources only, or a primary Meta
page I could not get real content from — see tooling caveat below).

**Tooling caveat, stated once:** `WebFetch` reliably returned real content for
`developers.facebook.com` doc pages (Marketing API reference/guides) but for
`facebook.com/business/help/*` (Meta Business Help Center) it returned **only the page title**
on every attempt (5 tried) — those pages are evidently client-side-rendered and the fetch tool
can't execute JS. Where a claim rests on one of those Help Center pages, I could not quote Meta's
exact wording directly and instead report the converging secondary-source consensus, tagged
**[UNVERIFIED]** even when the underlying claim is near-universal industry canon. This is a real
gap, not a shortcut — flagged explicitly in (j).

---

## (a) Learning phase: reset triggers, exit rule, "significant edit"

**Exit rule** [UNVERIFIED — could not fetch Meta's own "About the Learning Phase" page
(`facebook.com/business/help/112167992830700`) past its title; near-universal, uncontested
secondary-source citation]: a delivering ad set typically exits the learning phase after
accumulating **~50 optimization events (conversions) within a rolling 7-day window**. Below that,
delivery is unstable/exploratory and CPA is typically higher.

**What resets it — "significant edit"** [UNVERIFIED, same caveat — Meta's own
"Significant Edits and Learning Phase" page (`facebook.com/business/help/316478108955072`)
title-only; consistent, non-contradictory secondary consensus across Jon Loomer Digital and
several ad-tech blogs]:
- **Resets**: audience/targeting change; optimization event change; **adding a NEW ad** to an
  existing ad set (regardless of whether that set is still learning); bid-strategy change; budget
  change **>20%** in either direction; pausing the ad set for **>7 days**.
- **Does NOT reset**: budget change **≤20%**; ad-set name changes; schedule tweaks within the
  same period; **editing/refreshing an existing ad's copy or creative in place is reported as
  performance-affecting but not reset-triggering** (distinct from adding a brand-new ad object).
- **Pausing one ad within a multi-ad ad set does NOT reset the ad set's learning phase** — only
  *adding* a new ad does. [UNVERIFIED, recurring/consistent secondary claim, not primary-sourced]
  This is the single most load-bearing fact for the bandit's design: **it can pause/resume
  existing ads inside a set freely without a reset cost, but rotating in a new challenger ad
  always pays a reset.**

**2026 development — treat with real caution** [UNVERIFIED, single-blog-sourced, not
corroborated]: multiple practitioner reports (via search aggregation, one underlying source)
describe Andromeda **tightening reset thresholds around April 2026** — edits previously safe
(small bid nudges, minor audience additions, small creative tweaks) reportedly began triggering
resets that hadn't before. If real, this means the 20%-budget / audience-change thresholds above
may already be stale as of 16 Jul 2026. **This is exactly the kind of fact only a live empirical
test on the real account can currently settle** (see (j)).

**Design implication for the engine**: batch all edits into one daily decision window (already
the cross-cutting synthesis in `scope-science.md`), prefer pausing existing arms over swapping in
new creative when a reset-free action is available, and budget-adjust in steps safely under any
suspected threshold (e.g. ≤10-15% per day) rather than testing the 20% edge.

---

## (b) Split Testing API — current state, usability at ~$10/day, what it randomizes

**Endpoint/object** [VERIFIED, `developers.facebook.com/docs/marketing-api/guides/split-testing/`
+ `.../reference/ad-study` fetched directly]: lives under **`AdStudy`**, created at
`POST /<BUSINESS_ID>/ad_studies` — a **Business-Manager-level object, not an ad-account-level
one**. Three `type` values: `SPLIT_TEST` (near-term optimization decisions, e.g. creative
comparison), `SPLIT_TEST_V2` (2-5 cells, adds `cooldown_start_time`/`observation_end_time`/
`creative_test_config`, budget split via `daily_budget` or `lifetime_budget_percentage`), and
`LIFT` (incrementality/conversion-lift studies, a different use case). No deprecation notice found
on either page.

**What it randomizes** [VERIFIED]: the API "automates audience division, ensures no overlap
between groups" — mutually exclusive audience cells, no cross-cell contamination — plus, for
creative tests, "one ad (creative variant) per cell." `treatment_percentage` (integer, cells sum
to 100) controls the split for campaign-level tests.

**Minimum budget/duration — primary source silent, confirmed again this pass** [VERIFIED-absence]:
neither the guide nor the AdStudy reference states a minimum budget or duration. The only guidance
is directional: "tests with larger reach, longer schedules, or higher budgets tend to deliver more
statistically significant results." **Primary source silent — folklore says**: $20-50/day per ad
set as a floor, 1,000+ impressions and 50+ clicks per variant for meaningful significance
[UNVERIFIED, secondary aggregation]. Separately, Meta's own native **Experiments** tool
(`facebook.com/business/help/1738164643098669`, not directly fetchable — same Help Center caveat)
is independently reported by multiple sources to recommend **≥$100/day per variation, 7-14 days,
for 95% confidence**.

**Usability at Taqinor's ~$10/day total budget**: even taking the low end of the folklore
guidance ($20-50/day *per variant*, i.e. $40-100/day for a 2-cell test), Taqinor's whole daily
budget is at or below a SINGLE cell's recommended minimum — and Meta's own Experiments guidance
(~$100/day/variation) is **10-20x the entire daily budget**. There is no primary-sourced hard
floor that flatly forbids running a smaller test, but every available signal (folklore minimums,
Meta's own Experiments guidance, general two-proportion-test power math from `scope-science.md`
S1) converges on: **the native Split Testing API / Experiments tool is very likely not a usable
statistical instrument at Taqinor's current budget** — confidence intervals would be enormous, and
the 2-week+ minimum runtime eats a meaningful fraction of a month's whole budget for one test.

**CLI exposure — a real, confirmed gap** [VERIFIED, directly against the official CLI's Command
Reference page]: the `pip install meta-ads` CLI's resource table covers exactly
`adaccount / page / campaign / adset / ad / creative / dataset / catalog / insights` — **no
`study`/`experiment`/`split-test` resource exists in the CLI at all**. To use `ad_studies`
programmatically, the engine **must drop to the raw Marketing API** (the `facebook-business`
Python SDK, or direct REST calls) — same conclusion independently reached for domain (e), below.

**Net for the engine**: do not build on the native Split Testing API given the budget mismatch;
the DIY pattern in (c) is the realistic path at current spend.

---

## (c) The DIY alternative: auction contamination and the cleaner multiple-ads-in-one-ad-set pattern

**Does the auction contaminate "2 ad sets, same audience, different creative"?** [UNVERIFIED for
exact mechanics — Meta's own "Understand auction overlap" Help Center page
(`facebook.com/business/help/537699989762051`) was title-only in my fetch; but the underlying
mechanic is consistently, non-contradictorily described across Jon Loomer Digital (a
well-regarded, long-running independent Meta-ads authority, treated as high-confidence secondary)
and multiple other sources]: **yes, it contaminates it, but not by literal bid-against-yourself
inflation** — when two ad sets with overlapping audiences are both eligible for the same specific
auction event, Meta's system does **not** let both compete; it picks the ONE ad set with the
higher "total value" to enter that auction, and **excludes the other from that auction entirely**.
Net effect: the excluded ad set under-delivers/struggles to spend evenly, and which one "wins" a
given auction is driven by Meta's own opaque value-ranking, not a controlled 50/50 randomized
split. **This directly breaks the naive DIY two-ad-set test**: any CPA/CTR difference you observe
between the two ad sets is confounded by which one Meta's auction let compete more often, not a
clean creative comparison.

**The cleaner pattern — multiple ADS inside ONE ad set** [VERIFIED for the mechanism's existence
via the CLI Command Reference + AdSet docs (see (f)); the allocation-mechanics detail below is
UNVERIFIED/secondary]: putting several distinct ads inside a single ad set avoids the
auction-overlap problem entirely — one audience, one auction pool, Meta's *within-auction* ad
selection (not cross-ad-set exclusion) decides which ad shows each time. Reported allocation
behavior: Meta runs (what practitioner sources call) **"Optimized Rotation" by default** —
delivery concentrates quickly toward the ad with the best predicted engagement/CTR/conversion
probability, commonly reaching 70-80% share for an early "winner" within the learning window,
throttling the rest. A separate **"Even Rotation"** mode (roughly equal delivery across ads, meant
for controlled comparison) is described in secondary material, but **I could not confirm against
any primary Marketing API/AdSet field that this is still an API-settable option in 2026** — treat
its current existence as an open item for (j), not a confirmed lever.

**Can the bandit pause ads inside the set without a learning-phase reset?** [UNVERIFIED, but
consistent, non-contradicted secondary claim — ties directly to (a)]: **yes** — pausing an
existing ad within a multi-ad set is reported as reset-free; only *adding a new ad* to the set
resets learning. This is the key operational fact: **the engine's bandit CAN act by pausing
under-performing ads inside a fixed ad set at zero learning-phase cost**, but **rotating in a
fresh challenger creative always pays a reset** — so the engine should treat "pause a loser" as a
cheap, frequent action and "add a new challenger" as an expensive, rate-limited one (e.g. weekly,
not daily).

**Recommended shape for the engine**: one ad set per audience/market-mode segment, several ads
inside it (within Dynamic-Creative's mutual-exclusivity constraint — see (f)), bandit reads
per-ad Insights breakdowns (h) daily, pauses losers freely, and only introduces a new ad from the
creative backlog on a slower cadence to bound reset frequency.

---

## (d) CBO / Advantage+ boundary — what to use for engine-controlled allocation

**How CBO is represented in the API — no explicit toggle** [VERIFIED, directly against the
Campaign object reference]: there is **no boolean field**. CBO ("Advantage campaign budget") is
**implicit**: set `daily_budget`/`lifetime_budget` at the **Campaign** level → CBO is on, and
Meta's ML reallocates spend across that campaign's ad sets toward predicted best performers. Set
budgets at the **ad-set** level instead → ABO. **"You can either set budget at the campaign level
or at the adset level, not both."** At CBO scale ≥70 ad sets, you additionally lose the ability to
edit bid strategy or turn CBO off — irrelevant at Taqinor's tiny ad-set count but a real ceiling
if ever scaled.

**2026 structural change — the Advantage+ unification** [VERIFIED via direct fetch of two ppc.land
pieces reporting Meta's own Sept–Oct 2025 developer announcements + the v24.0/v25.0 changelog
already independently confirmed in `eng-meta-tooling.md`]: Meta retired the separate
Advantage+ Shopping (ASC) / Advantage+ App (AAC) **campaign types** and their dedicated legacy
APIs — creation blocked from **v24.0 (8 Oct 2025)**, fully deprecated across **all** API versions
from **v25.0 (Q1 2026)**. In their place, **any** campaign can independently enter Advantage+
state via **three separately-togglable automation levers**: Advantage+ **budget** (= CBO, at
campaign level), Advantage+ **audience** targeting, and Advantage+ **placement**. A new
`advantage_state_info` field reports the resulting state (`ADVANTAGE_PLUS_SALES` /
`ADVANTAGE_PLUS_APP` / `ADVANTAGE_PLUS_LEADS` / `DISABLED`). This matters for the engine's mirror
schema (per `scope-features.md` domain 1's open question) — **CBO is no longer bundled with a
campaign "type," it is one independent lever the engine can read/set on its own**, cleanly
separate from audience/placement automation.

**Recommendation, confirming `scope-features.md` domain 5's prior hypothesis**: **use ABO
(ad-set-level budgets), not CBO, for the engine's own controlled ad sets.** CBO hands the
cross-ad-set allocation decision to Meta's own opaque, ML-driven reallocation — exactly the
decision layer the engine's own bandit (per `scope-science.md` S1/S2) wants to own at Taqinor's
scale, where the whole point is a deterministic, auditable, WhatsApp-reportable allocation logic,
not a black box. Running ABO keeps every ad set's budget explicitly under the engine's own daily
batch-decision loop. (Enabling Meta's own CBO with a spend ceiling remains a legitimate
"skip-Meta-does-it" fallback proposal per `scope-features.md` domain 5(d), but is not the
recommended default given the engine's stated purpose is to own the allocation decision.)

---

## (e) Automated Rules API — creatable programmatically? Vocabulary? CLI exposure?

**Yes, creatable via the Marketing API** [VERIFIED, direct fetch of
`.../ad-account/adrules_library/`, v25.0]: `POST /<AD_ACCOUNT_ID>/adrules_library` — "When posting
to this edge, an AdRule will be created."

**Condition vocabulary (`evaluation_spec`)** [VERIFIED]: `evaluation_type` (`SCHEDULE` /
`TRIGGER`), `filters` list of `{field, value, operator}`, operator enum:
`GREATER_THAN, LESS_THAN, EQUAL, NOT_EQUAL, IN_RANGE, NOT_IN_RANGE, IN, NOT_IN, CONTAIN,
NOT_CONTAIN, ANY, ALL, NONE`.

**Action vocabulary (`execution_spec`)** [VERIFIED]: `execution_type` enum —
`DCO, PING_ENDPOINT, NOTIFICATION, PAUSE, REBALANCE_BUDGET, CHANGE_BUDGET, CHANGE_BID, ROTATE,
UNPAUSE, CHANGE_CAMPAIGN_BUDGET, ADD_INTEREST_RELAXATION, ADD_QUESTIONNAIRE_INTERESTS,
INCREASE_RADIUS, UPDATE_CREATIVE, UPDATE_LAX_BUDGET, UPDATE_LAX_DURATION, AUDIENCE_CONSOLIDATION,
AUDIENCE_CONSOLIDATION_ASK_FIRST, AD_RECOMMENDATION_APPLY` — notably richer than the AND-only,
pause/enable/budget/bid/notify vocabulary `scope-features.md` domain 2 assumed from secondary
sources (it includes `PING_ENDPOINT`, a webhook-style callout, which is directly useful: **a
native Meta rule could ping the engine's own endpoint on a threshold crossing, rather than the
engine having to poll**).

**Schedule vocabulary** [VERIFIED]: `schedule_type` (`DAILY, HOURLY, SEMI_HOURLY, CUSTOM`),
`schedule` list with `start_minute`/`end_minute`/`days`.

**CLI exposure — confirmed absent** [VERIFIED, same Command Reference fetch as (b)]: the
`meta-ads` CLI has **no `rule`/`adrules` resource**. Same conclusion as Split Testing: **automated
rules are a raw-Marketing-API-only capability**, not reachable through the CLI Meta shipped for
agent use. The engine's `MetaConnection`/System User token (already the right token type per
`eng-meta-tooling.md`) needs `ads_management` scope regardless, so this is additional integration
surface, not a new credential requirement.

**Design implication**: `scope-features.md`'s open question ("should `GuardrailConfig`/
`EngineAction` wrap Meta's native Automated Rules primitive?") can now be answered — **yes, it's
mechanically feasible** (rules ARE creatable server-side with rich conditions/actions), but doing
so means writing directly against the raw REST/SDK layer alongside the CLI, not instead of it —
worth doing selectively (e.g. a `PING_ENDPOINT` safety-net rule that notifies the engine
immediately on a CPA spike between the engine's own daily batch runs) rather than replacing the
engine's own condition evaluation wholesale.

---

## (f) Dynamic Creative via API — flags, asset feed, per-asset breakdowns

**Enable flag** [VERIFIED, `.../ad-creative/asset-feed-spec/dynamic-creative/`]: `is_dynamic_creative
= true` set at the **AD SET** level (not the creative). Campaign `objective` restricted to one of
`OUTCOME_SALES, OUTCOME_ENGAGEMENT, OUTCOME_LEADS, OUTCOME_AWARENESS, OUTCOME_TRAFFIC,
OUTCOME_APP_PROMOTION`; `buying_type` must be `AUCTION` or blank; `optimization_goal` typically
`OFFSITE_CONVERSIONS` (APP_INSTALLS needs `link_url` in `asset_feed_spec` matching
`object_store_url`).

**Asset limits** [VERIFIED]: ≤10 images, ≤10 videos, ≤5 bodies (primary text), ≤5 CTAs, ≤5 titles
(headlines), ≤5 links, ≤5 descriptions — **max 30 total assets**. Supports all placements except
Messenger `sponsored_messages`; a WhatsApp CTA button is addable via
`message_extensions: {"type": "whatsapp"}` in `asset_feed_spec` — directly relevant to Taqinor's
CTWA-first channel strategy.

**Critical architectural constraint — confirmed** [VERIFIED]: **"You can only create one ad per
ad set" when Dynamic Creative is on.** This means Dynamic Creative and the (c) "multiple distinct
ads in one ad set, bandit pauses losers" pattern are **mutually exclusive within a single ad set**
— the engine must pick one mechanism per ad set, not layer them: (i) Dynamic Creative — one ad
object, Meta auto-mixes asset combinations, engine reads per-asset breakdowns; or (ii) several
whole, independently-pausable ad objects, engine's own bandit picks winners. This is a genuine
fork `scope-features.md` domain 6 did not resolve and should be decided per use case (Dynamic
Creative is likely the right default for the hook/visual/copy-permutation layer given its native
per-asset read-back; the multi-ad pattern is right when testing whole creative *concepts*, not
components).

**Per-asset breakdowns readable** [VERIFIED, `.../insights/breakdowns/`]: yes — 8 dedicated
breakdown dimensions: `image_asset, video_asset, title_asset, body_asset, call_to_action_asset,
link_url_asset, description_asset, ad_format_asset`, each returning the specific asset-variant ID
tied to the impression/click/action. **Restriction**: these breakdowns only support a limited
metric set (impressions, clicks, spend, reach, actions, action_values) and are **not available at
the ad-account level** for Dynamic-Creative assets — must query at ad or ad-set level. This is
exactly the granularity the reward signal needs (per `scope-science.md` S1's rung-to-decision
table) for a within-ad "which hook/visual/CTA won" read, without a separate Split Test.

---

## (g) Advantage+ creative enhancements — flags and which must be forced OFF

**The flag surface exists and is large** [VERIFIED-partial — `AdCreativeFeaturesSpec` fetched
directly, but the summarizer captured explicit `enroll_status`/default values for only 4 of the
~44 named fields; the rest returned as field-name-only, "not specified" — a real fetch-completeness
gap, not a doc gap, flagged for follow-up]: confirmed field names include (non-exhaustive, as
captured): `standard_enhancements`, `standard_enhancements_catalog`, `image_animation`,
`image_background_gen`, `image_touchups`, `image_templates`, `music_generation`,
`video_highlights`, `video_to_image`, `multi_photo_to_video`, `replace_media_text`,
`text_extraction_for_headline`, `text_extraction_for_tap_target`, `text_optimizations`,
`text_translation`, `text_overlay_translation`, `translate_voiceover`, `generate_cta`,
`add_text_overlay`, `adapt_to_placement`, `description_automation`, `inline_comment`,
`site_extensions`, `profile_card`, `creative_stickers`, `biz_ai`, plus several catalog/ads-with-
benefits/placement-tag fields not relevant to Taqinor's non-catalog creative. Confirmed with
explicit `OPT_IN`/`OPT_OUT` enum and a stated **opt-in default**: `adapt_to_placement`,
`description_automation`, `inline_comment`; `add_text_overlay` confirmed to take
`OPT_IN`/`OPT_OUT` but default not captured.

**Directional policy read for CLAUDE.md's no-fake-footage / checked-facts-only posture**
[my own synthesis, not a verified Meta-published "recommended off" list — treat as a starting
policy draft, not a settled spec]: flags that **generate or synthetically alter the real
photo/video content** should default to `OPT_OUT` for Taqinor's real solar-install photography:
`image_background_gen` (fabricates new background), `image_animation` (adds synthetic motion to a
static photo), `music_generation`, `video_highlights` (auto-re-edits video, risk of
misrepresenting the installation), `video_to_image`, `multi_photo_to_video`, `replace_media_text`,
`image_touchups` (could smooth/alter real install details), and likely `standard_enhancements`/
`standard_enhancements_catalog` (Meta's umbrella auto-brightness/contrast/crop bucket — borderline,
but color-accuracy of real installs argues for OFF). Flags that are pure **read/reformat, not
generative alteration** are lower-risk and plausibly safe to leave on: `text_extraction_for_
headline`/`_tap_target` (extracts existing text), `text_translation`/`text_overlay_translation`/
`translate_voiceover` (translation, not alteration), `adapt_to_placement` (crop-to-fit, not
generative). **This entire list needs either a fuller doc re-fetch (the page clearly has more
detail than what came through) or an empirical test — do not treat it as final before wiring
`degrees_of_freedom_spec` into the engine's ad-creation payload.**

---

## (h) Per-ad insights granularity — what can feed the bandit's reward

**Confirmed readable at ad level, daily** [VERIFIED]: standard metrics (spend, impressions,
clicks, reach, CTR, CPC, CPM) via date-range queries at any hierarchy level including `ad`;
Dynamic-Creative asset breakdowns (8 dimensions, listed in (f)); device/placement breakdowns
(`device_platform`, `impression_device`, `platform_position`, `publisher_platform`); geographic
(`region`, `dma`); temporal (hourly); and `action_device`/`action_destination`/`product_id` — with
**Type 1/Type 2 combination-restriction classes** noted in the docs and a documented practical
friction: **Meta does not publish the full breakdown-combination compatibility matrix**
[secondary, but consistent with the primary doc's own restriction notes] — an unsupported
combination returns a generic error, so the engine's insights-fetching code needs defensive
per-combination trial/fallback logic, not an assumed-valid matrix.

**CTWA/WhatsApp signal — the reward proxy the bandit actually needs** [VERIFIED for the action
type's existence; UNVERIFIED for full guarantees around it]: `onsite_conversion.messaging_
conversation_started_7d` is a real, queryable `action_type` in Insights — a WhatsApp/Messenger
conversation started, attributable per ad, per day. This is the concrete metric that closes the
gap `scope-features.md` domain 7 flagged (Meta-side proxy for "did this ad/creative drive a real
conversation," before the CRM/Lead side of the funnel). **Operational constraint on the
CAPI-feedback side** [UNVERIFIED, secondary/vendor doc]: for CTWA ads, only **1 CAPI event per ad
click event** is accepted, and it **must arrive within 7 days of the click** — relevant to
`eng-competitors.md`'s planned close-the-loop CAPI feedback (a signature closing weeks later,
common for solar, falls outside this window and cannot be sent as a CTWA-linked CAPI event —
worth flagging to whoever eventually builds the CAPI feedback path).

---

## (i) Rate limits, batch API, async insights — practical notes

**Async insights workflow** [VERIFIED, `.../insights/best-practices/`]: `POST <object>/insights` →
returns `report_run_id` → poll `async_status`/`async_percent_completion` on
`<AD_REPORT_RUN_ID>` → `GET <AD_REPORT_RUN_ID>/insights` for results. **`report_run_id` expires
after 30 days** — do not persist it long-term as a stable reference.

**Throttle headers** [VERIFIED]: `x-fb-ads-insights-throttle` exposes `app_id_util_pct`,
`acc_id_util_pct`, `ads_api_access_tier` — back off before either hits 100% (error code 4,
subcode `1504022` on breach). A **separate, low, hard ceiling**: `x-Fb-Ads-Insights-Reach-Throttle`
caps **reach-breakdown async requests at 10/ad-account/day** — a real constraint if the engine
ever wants dedup/reach-based breakdowns, though not central to the current metric set.

**Business Use Case (BUC) header** [VERIFIED-partial]: `X-Business-Use-Case-Usage` carries
`call_count`, `total_cputime`, `total_time`, `estimated_time_to_regain_access`, `type`,
`ads_api_access_tier`, `business-id`; throttling triggers when `total_cputime`/`total_time` reach
100%. **Discrepancy flagged, unresolved**: `eng-meta-tooling.md` (prior dossier) cited a
read=1-point/write=3-point BUC cost split from an earlier pass; this pass's fetch of the
rate-limiting overview did not surface that same point-cost breakdown (the excerpt returned
suggested undifferentiated call-counting). **Do not treat either version as settled** — needs one
more direct, careful fetch of the specific BUC-scoring subsection (likely a different anchor/
page than what was hit this time) or an empirical usage-header comparison between a read and a
write call on the real account.

**Batch API** [VERIFIED, `developers.facebook.com/docs/graph-api/batch-requests`]: **max 50
sub-requests per batch**; **each sub-request is counted separately against rate limits** —
batching saves round-trips, not quota. Large/complex batches can partially time out: succeeded
sub-requests return `200`, failed ones return `null`, so the engine must handle partial-batch
failure and retry only the `null` entries. **Marketing-API-specific gotcha**: a single batch
**cannot include multiple ad sets under the same campaign** — a script that wants to bulk-pause
several ad sets in one campaign must split that across separate batch calls or sequential calls,
not one batch.

---

## (j) Things only resolvable by a live empirical test on the real account

Being honest about the boundary of what documentation research can settle:

1. **The current exact learning-phase-reset thresholds** (the specific % budget-change figure,
   the exact conversion count) — neither of Meta's own two canonical Help Center pages could be
   fetched as real text by any tool in this pass; only secondary sources back the ~50-conversions/
   7-day and >20%-budget figures, and one (single-sourced, uncorroborated) report claims Andromeda
   tightened these in April 2026. **Test**: on the real ad account, make one small, isolated edit
   (e.g. a 10% budget bump) mid-flight and watch the ad set's delivery/learning status field
   (`effective_status`, or the "Learning" label surfaced via Insights/Ads Manager) before and
   after — repeat at 15%, 25% to bracket the real current threshold.
2. **Whether "Even Rotation" between multiple ads in one ad set is still an API-settable field in
   2026** — only found in secondary material, not confirmed against a primary AdSet field. **Test**:
   create 2 ads in one ad set with no rotation setting touched, run for several days, and observe
   whether spend splits evenly or concentrates — this alone will show current default behavior
   even without finding the field name.
3. **The real minimum viable budget for the Split Testing API / native Experiments to return a
   non-degenerate result** — Meta's docs are silent on a hard floor; folklore minimums (~$20-50/
   day/variant) and Meta's own Experiments guidance (~$100/day/variant) both exceed Taqinor's
   whole daily budget. **Test**: run one real `SPLIT_TEST_V2` at Taqinor's actual budget for two
   weeks and read the confidence/power numbers Meta itself reports back — this directly answers
   whether the tool is usable at all, cheaper than continuing to search for a documented floor
   that evidently doesn't exist.
4. **The exact default `enroll_status` per Advantage+ creative-enhancement flag** — the
   `AdCreativeFeaturesSpec` fetch this pass captured field names but not most defaults. **Test**:
   create one `AdCreative` via the CLI/API with `degrees_of_freedom_spec` entirely omitted, then
   read the object back and inspect what Meta assumed — cheaper and more reliable than re-fetching
   the doc repeatedly.
5. **Whether a native Automated Rule's own actions (`CHANGE_BUDGET`, `ROTATE`, etc.) count as a
   "significant edit" that resets learning the same way a manual edit does** — undocumented
   anywhere found. **Test**: trigger a rule-driven `CHANGE_BUDGET` and watch the learning-phase
   status the same way as item 1.
6. **The real BUC point-cost table** (read vs. write cost, if any) — flagged as an unresolved
   discrepancy with the prior dossier in (i). **Test**: compare the `X-Business-Use-Case-Usage`
   header's `call_count`/`total_cputime` delta after one read call vs. one write call on the real
   account.
7. **Whether Business Verification / access-tier level gates `adrules_library` or `ad_studies`
   specifically** (as opposed to just standard campaign CRUD, which is confirmed reachable at
   Limited/Full Access per `eng-meta-tooling.md`) — not found in any source this pass. **Test**:
   attempt one `adrules_library` POST and one `ad_studies` POST on Taqinor's actual account/token
   before assuming either is available once basic CRUD works.

---

## Sources

Primary (Meta-owned, fetched directly and quoted from in this pass):
- [Split Testing API guide](https://developers.facebook.com/docs/marketing-api/guides/split-testing/)
- [AdStudy reference](https://developers.facebook.com/docs/marketing-api/reference/ad-study)
- [Ad Account adrules_library reference](https://developers.facebook.com/docs/marketing-api/reference/ad-account/adrules_library/) (v25.0)
- [Ad Campaign Group (Campaign) reference](https://developers.facebook.com/docs/marketing-api/reference/ad-campaign-group/)
- [Dynamic Creative via asset_feed_spec](https://developers.facebook.com/docs/marketing-api/ad-creative/asset-feed-spec/dynamic-creative/)
- [AdCreativeFeaturesSpec reference](https://developers.facebook.com/docs/marketing-api/reference/ad-creative-features-spec/)
- [Insights Breakdowns reference](https://developers.facebook.com/docs/marketing-api/insights/breakdowns/)
- [Insights Best Practices (async workflow, throttling)](https://developers.facebook.com/docs/marketing-api/insights/best-practices/)
- [Graph API Batch Requests](https://developers.facebook.com/docs/graph-api/batch-requests)
- [Graph API Rate Limiting overview](https://developers.facebook.com/docs/graph-api/overview/rate-limiting)
- [Meta Ads CLI Command Reference (official)](https://developers.facebook.com/documentation/ads-commerce/ads-ai-connectors/ads-cli/command-reference)
- Meta Business Help Center page **titles only** confirmed reachable (content not retrievable via
  available tooling this pass): "About the Learning Phase" (112167992830700), "Significant Edits
  and Learning Phase" (316478108955072), "Understand auction overlap" (537699989762051), "About
  Budget Optimization Tests" (299600627522144), "About Advantage+ Placements" (196554084569964),
  "About Targeting and Reporting for Advantage+ App Campaigns" (1153577308409919).

Independent trade press (fetched directly):
- [Meta launches unified API structure for Advantage+ campaigns — ppc.land](https://ppc.land/meta-launches-unified-api-structure-for-advantage-campaigns/) (21 Sep 2025)
- [Meta deprecates legacy campaign APIs for Advantage+ structure — ppc.land](https://ppc.land/meta-deprecates-legacy-campaign-apis-for-advantage-structure/) (26 Oct 2025)

Secondary/practitioner (used only where explicitly tagged UNVERIFIED above):
- Jon Loomer Digital (jonloomer.com) — "This is Auction Overlap," "Facebook Ads Edits that
  Trigger the Learning Phase," treated as higher-confidence independent practitioner authority but
  still secondary, not primary
- respond.io help docs (CTWA CAPI 7-day/1-event constraint)
- Aggregated 2026 ad-tech blog cluster (admanage.ai, adstellar.ai, cropink.com, get-ryze.ai,
  growwithsakib.com, superscale.ai, lebesgue.io, wevion.ai, flighted.co, madgicx.com blog,
  niblin.com, modernmarketinginstitute.com, roaspig.com, napolify.com, coinis.com, adenslab.com,
  convert.com) — same content-farm-adjacent caution as `eng-meta-tooling.md`'s source-reliability
  warning; used only for directional/folklore figures explicitly marked UNVERIFIED.
