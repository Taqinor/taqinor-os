# THE ATTRIBUTION SPINE — spec-grade dossier

Research/spec date: 16 Jul 2026. Scope: TAQINOR autonomous Meta ads engine, attribution layer only
(parts a-e per mission brief). Everything under "Ground truth" was verified by reading the actual
repo at `C:/dev/taqinor-os/.claude/worktrees/great-neumann-fc8b39` (not assumed from the scope
docs). Everything under "Primary-source research" was verified against Meta's own developer docs
via WebFetch on 16 Jul 2026, with URL + extraction quoted. Folklore/UNVERIFIED is flagged inline.

---

## 0. Headline findings (read this first)

1. **[VERIFIED]** `crm.Lead` already has `fbclid`/`utm_source`/`utm_medium`/`utm_campaign`/
   `utm_content`/`utm_term` (models.py:614-619) AND a `stage` field carrying canonical `STAGES.py`
   keys with an index on `(company, stage)` (models.py:556-557, 771) — **the CLAUDE.md line "the
   funnel stage is NOT wired to any table yet" is stale**; it is already wired on `crm.Lead`. Flag
   this discrepancy to the founder; it does not change anything in this spec, but any future rule
   change should be reconciled against real repo state, not the other way round.
2. **[VERIFIED — CONCRETE BUG]** For Meta Lead Ads leads, `create_lead_from_meta_lead_ads` sets
   `utm_content = adset_name` — but Meta's leadgen webhook **never sends `campaign_name` or
   `adset_name`** (confirmed against the primary docs, §"Ground truth" below). The current code
   reads `value.get('campaign_name', '')` / `value.get('adset_name', '')` from a webhook payload
   that structurally cannot contain those keys. Result: **every Meta Lead Ads lead today has
   `utm_campaign=None` and `utm_content=None`** — the variant/campaign join for this channel is
   silently empty, not degraded. This is the single highest-priority fix for part (a).
3. **[VERIFIED — CONCRETE BUG]** `ad_id` and `adgroup_id` (ad-set id) **are** delivered in the
   leadgen webhook `value` object (confirmed against primary docs) and are also directly
   requestable on the lead node itself — but the current code never reads or stores them. This is
   the fix: real per-ad (variant) attribution for Lead Ads is one Graph API hop away, using data
   Meta already pushes today, unused.
4. **[VERIFIED — CONCRETE BUG, latent]** The Meta CAPI SignedQuote call
   (`ventes/services.py:_fire_capi_signed_quote`) is hardcoded to
   `https://graph.facebook.com/v19.0/{pixel_id}/events`. **v19.0 expired 4 Feb 2025** (confirmed
   against Meta's own version changelog) — it has been retired for ~17 months as of today. The
   call is currently a silent no-op (`pixel_id` not configured yet → early return, log only), so
   this bug has never fired — but it **will 400 the instant a founder configures
   `META_CAPI_PIXEL_ID`**, silently breaking the whole offline-feedback loop unless fixed first.
5. **[VERIFIED]** `ctwa_clid` (Click-to-WhatsApp click id) has **zero code path anywhere in this
   repo** — no field, no webhook receiver. `Lead.Canal.WHATSAPP_CTWA` exists only as a manual
   dropdown choice a human can select; nothing sets it automatically. TAQINOR's WhatsApp usage
   today is plain `wa.me/<number>?text=...` deep links (`ventes/services.py:_build_acceptance_wa_url`),
   which structurally **cannot** carry or receive `ctwa_clid` (see part (a) §CTWA for why).
6. **[VERIFIED]** `apps/ventes/quote_engine`'s CAPI event has **no `event_id`** in its payload —
   safe today (no browser Pixel exists to double-fire against, and `accept_devis` is guarded
   against double-accept), but a one-line, zero-risk fix that forecloses a whole class of future
   double-counting bugs the moment anyone adds a browser Pixel to `/proposal`.
7. **[VERIFIED]** ENG1-31 (the "already merged" basic layer) is **spec text merged into
   `docs/PLAN.md`, all 31 tasks still `[ ]` unbuilt** — nothing to audit against running code, only
   against the spec. ENG10 ("cost-per-signature service") is specced at **campaign/channel
   granularity only** (`blend spend × leads by canal/utm_campaign × SIGNED counts`) — it does
   **not** spec variant/ad-level granularity. That is the delta this dossier fills; see part (e).

---

## 1. Ground truth — what already exists in the repo (verified 16 Jul 2026)

### 1.1 `crm.Lead` attribution fields (`backend/django_core/apps/crm/models.py`)
```
fbclid       CharField(500)   # first-touch, site webhook only
utm_source   CharField(300)
utm_medium   CharField(300)
utm_campaign CharField(300)
utm_content  CharField(300)
utm_term     CharField(300)
canal        Canal enum: meta_ads | whatsapp_ctwa | site_web | reference | telephone | walk_in | autre
source       Source enum: os_native | odoo_import_test | site_web | meta_lead_ads
external_system / external_id   # dedup key for imports incl. Meta leadgen_id
stage        CharField, canonical STAGES.py keys (NEW/CONTACTED/QUOTE_SENT/FOLLOW_UP/SIGNED/COLD)
```
Indexes today: `(company, source)`, `(company, stage)`, `(company, score)`,
`(company, phone_normalise)`, `(company, email_normalise)`. **No index touches
utm_campaign/utm_content/canal** — a gap for part (a)/(d) rollup queries.

### 1.2 Two independent ingestion paths, two different attribution qualities
- **Site webhook** (`crm/webhooks.py:website_lead_webhook`, calls `_map_payload_to_fields`) —
  reads `data.utm.{source,medium,campaign,content,term}` and `data.fbclid` verbatim from the
  Cloudflare Worker's payload (`apps/web`, out of scope here). **This path works correctly** —
  whatever UTM values the ad's destination URL carries reach `crm.Lead` unmodified, including
  `utm_content` at true ad/creative granularity **if and only if** the person who built the ad in
  Ads Manager typed a distinct `utm_content` per ad. First-touch fields are protected on
  visitor-revisit (`_FIRST_TOUCH_FIELDS`, never overwritten by a later touch) — correct dedup
  design already in place (QJ8).
- **Meta Lead Ads webhook** (`crm/webhooks.py:meta_lead_ads_webhook` → `fetch_meta_lead_data` →
  `crm/services.py:create_lead_from_meta_lead_ads`) — **structurally broken for
  campaign/variant attribution** per finding #2/#3 above. `utm_source='facebook'` is the only
  reliable field; `utm_campaign`/`utm_content` are always `None` in production today.

### 1.3 The QJ9 attribution→CAPI hook (`apps/ventes/services.py:1050-1233`)
- Fires on **Devis acceptance** (`Devis.statut → accepte`), a rule #4 *document-status* event —
  **not** on the `crm.Lead.stage → SIGNED` *pipeline* event (rule #2, a separate permanent layer
  that "never merges" with rule #4 per CLAUDE.md). These are two different conversion definitions
  that happen to usually coincide but are not the same trigger. See part (c) for why this matters.
- `_persist_attribution` snapshots `fbclid`/`utm_*` from `devis.lead` into
  `devis.etude_params['attribution']` at acceptance time — lossless even if the lead is later
  merged/archived/deleted. Good design, keep as-is.
- `_fire_capi_signed_quote` sends `event_name=SignedQuote`, `action_source=website`,
  `user_data={em, ph, fbc}`, `custom_data={currency, value, order_id, utm_source, utm_campaign}`.
  Gated on `META_CAPI_ACCESS_TOKEN`; no-ops (log only) without `META_CAPI_PIXEL_ID`. **Missing**:
  `event_id`, `client_ip_address`, `client_user_agent` (both already available as `accept_devis`
  params but not threaded through), correct API version (see finding #4).
- `value` = `option_totaux(devis)['ttc']` (remised total of the accepted option) — correctly
  avoids `prix_achat` (rule #4: margin data never client-facing/never in external payloads either,
  by extension) — no change needed here.

### 1.4 STAGES.py conversion marker
```python
SIGNED_QUOTE_CAPI_HOOK = "fire on transition INTO SIGNED"   # sentinel comment
CONVERSION_STAGE = SIGNED
```
This sentinel's own docstring is **aspirational, not descriptive of current wiring**: today
nothing fires on `Lead.stage → SIGNED`; the actual wired CAPI hook fires on `Devis` acceptance
(§1.3). ENG10's spec text also measures "comptage SIGNED (clés STAGES.py)" — i.e. it plans to
count by the **pipeline** stage, not the **document** status. Both are legitimate, different
numbers; a dashboard that shows "cost per signature" must be explicit about which one it means
(see part (d)).

### 1.5 Future adsengine mirrors (ENG5, unbuilt, spec only)
`AdCampaignMirror.meta_campaign_id`, `AdSetMirror.meta_adset_id`, `AdMirror.meta_ad_id` — real
Meta numeric IDs, one row per object, `created_via_engine` bool. `InsightSnapshot` — generic FK
(content_type + object_id) covering campaign/adset/ad levels uniformly, `spend`/`impressions`/
`clicks`/`conversions`/`raw` JSON, unique per `(target, date_start, date_stop)`. This is the right
shape to join against; part (a) below specs exactly how.

---

## 2. Part (a) — Variant-level attribution join path

### 2.1 The join path, end to end
```
adsengine.AdMirror (meta_ad_id, name)
        │  [ENG5 sync, already specced]
        ▼
crm.Lead (utm_content OR meta_ad_id, canal, stage, company)
        │  [Devis.lead FK — already exists]
        ▼
ventes.Devis (statut, date_creation, date_acceptation, etude_params.attribution)
        │  [reward = signed ? 1 : 0, cost = spend / count]
        ▼
adsengine.InsightSnapshot (spend, target=AdMirror, date_start/date_stop)
```
The reward for the bandit at variant granularity is:
```
cost_per_qualified_lead(ad) = InsightSnapshot.spend(ad, window)
                             / count(Lead WHERE <ad-match> AND stage reached qualifying stage)
```
where `<ad-match>` is the crux of this spec.

### 2.2 Schema additions needed on `crm.Lead` (additive, nullable — no destructive migration)
```python
meta_ad_id       = CharField(max_length=40, blank=True, null=True, db_index=True)
meta_adset_id    = CharField(max_length=40, blank=True, null=True)
meta_campaign_id = CharField(max_length=40, blank=True, null=True)
```
Rationale: numeric Meta IDs are the **only** stable join key to `adsengine.AdMirror.meta_ad_id`.
`utm_campaign`/`utm_content` are human-typed strings — fine for a human-readable label, unusable
as a hard join key (renames, duplicate names across campaigns, typos). Populate `meta_ad_id` from:
- **Lead Ads path**: `value.get('ad_id')` — already in the webhook payload today, currently
  discarded. Zero extra Graph API call needed to get the ID itself; one *optional* extra call
  (`GET /{ad_id}?fields=name,adset{id,name},campaign{id,name}`, cacheable by `ad_id` since names
  rarely change) to also backfill `utm_content`/`utm_campaign` as human-readable labels for display.
- **Site/Traffic-ad path**: cannot get a numeric `meta_ad_id` from a URL UTM param a human typed.
  Two options, not mutually exclusive:
  1. **(Recommended, forward-looking)** When `adsengine`'s own `meta_client.py` creates an ad
     (ENG4/ENG5), it should **auto-set the destination URL's `utm_content` to the ad's own
     `meta_ad_id`** (or `ad-<meta_ad_id>`) server-side at creation time — never leave it to a
     human to type correctly. This makes every AI-managed ad self-tagging by construction; the
     site webhook's existing `utm.content` capture then needs zero change and yields a hard ID.
  2. For ads created directly in Ads Manager (outside the engine, which will remain common early
     on), `utm_content` stays a human-typed string; store it as-is and match against
     `AdMirror.name` (fuzzy, best-effort) only for **display grouping**, never for the reward
     computation the bandit trusts — an unmatched string bucket ("attribution non résolue") must
     be a first-class, visible category, not silently dropped or silently merged into "organic".

### 2.3 Index additions
```python
models.Index(fields=['company', 'meta_ad_id']),
models.Index(fields=['company', 'utm_campaign']),
models.Index(fields=['company', 'canal', 'date_creation']),
```
The first two serve the variant/campaign rollup query; the third serves reconciliation (part b)
and cohort views (part d), all of which group/filter by `canal` + a date window.

### 2.4 Edge cases (explicit handling required, never silent)

**Organic leads.** Any `Lead` with `canal` not in `{meta_ads, whatsapp_ctwa}` and no
`utm_source`/`meta_ad_id` must be **excluded from the variant reward denominator entirely** — not
counted at zero cost (which would make every ad look infinitely efficient by comparison) and not
silently dropped from the *total* lead count shown elsewhere. Two denominators, always: "leads
attributable to this ad spend" (bandit input) vs "all leads this period" (business reality, part d).

**Missing/partial UTM.** Define an explicit attribution-resolution ladder, applied in this order,
first match wins, and the **resolution tier itself must be a stored/displayed field** (never
silently coerced to "best guess" with no trace):
1. `meta_ad_id` present → exact variant match (highest confidence).
2. `utm_content` present, matches an `AdMirror.name` → fuzzy variant match (medium confidence,
   flagged as such in the UI).
3. `utm_campaign` present, no ad-level match → campaign-level only, bucketed under
   "variante non identifiée" for that campaign — still counted, never dropped.
4. `canal ∈ {meta_ads, whatsapp_ctwa}` but no UTM at all (e.g. very old test leads, or a CTWA lead
   — see below) → campaign-unknown bucket, counted in the channel total, excluded from any
   variant/campaign ranking.
5. Anything else → organic, excluded per above.

**CTWA leads — precise capability statement.**
- **Without the WhatsApp Business Platform (Cloud API)** — i.e. TAQINOR's current setup, plain
  `wa.me/<number>?text=...` links opened from a personal/Business App number — **`ctwa_clid`
  cannot be captured at all, structurally, by design of Meta's product**: the click id is
  injected by Meta into a `referral` object that is delivered **only** inside the webhook payload
  of an inbound message received via the WhatsApp Business Platform (Cloud API), or a BSP built on
  top of it (360dialog, Twilio, Sinch, etc.). The free WhatsApp Business App has no webhook/API
  surface whatsoever — there is nothing to receive the referral object into, even in principle. A
  `wa.me` link itself carries no click-id parameter visible to the recipient device or app; the
  id only ever exists server-side, on Meta's infra, delivered to whoever owns the Cloud API
  subscription for that number. **Conclusion: today, TAQINOR's only possible CTWA signal is the
  manual `canal='whatsapp_ctwa'` tag a human sets** — real per-ad, per-click attribution for
  WhatsApp is categorically unavailable without adopting the Cloud API.
- **Interim, non-Meta-mechanised workaround (folklore, not a documented Meta feature; my own
  recommendation)**: CTWA ads support a per-ad "customized" prefilled message text set in Ads
  Manager. Setting a visibly distinct prefilled phrase per campaign/creative (e.g. "Bonjour, je
  suis intéressé — Offre Toit A") lets a human agent manually infer which ad drove a given
  WhatsApp thread and tag `canal`/`utm_campaign` by hand at lead-creation time. This is process
  discipline, not code — cheap to adopt now, but it is a labeled guess, not attribution; never
  represent it in the console with the same confidence tier as a real `meta_ad_id` match (tier 5
  above, at best a manually-corrected tier 3/4).
- **With the WhatsApp Business Platform (Cloud API)** — a real architecture change, not a small
  add: TAQINOR would register the WhatsApp number on the Cloud API (directly with Meta or via a
  BSP), stand up a webhook receiver (new endpoint, new app surface — `apps/crm/webhooks.py` is the
  natural home, mirroring `meta_lead_ads_webhook`'s shape), capture `referral.ctwa_clid` +
  `referral.source_id` (= `ad_id`, real variant granularity) from the **first inbound message** of
  a new conversation, store both on `Lead` (`ctwa_clid` + `meta_ad_id`, same field as §2.2), and
  — for the *feedback* half of the loop — send qualifying events back via **Conversions API for
  Business Messaging** with `action_source='business_messaging'`, `messaging_channel='whatsapp'`,
  and `user_data.ctwa_clid` (documented as "should not be hashed", unlike email/phone). This is a
  clean, well-documented, fully-supported Meta capability — the blocker is entirely operational
  (giving up the free personal-app WhatsApp workflow for a Cloud-API-backed one, likely via a BSP,
  a cost + workflow-change decision only the founder can make) not technical. **Recommendation**:
  treat "adopt WhatsApp Cloud API" as its own gated decision (COST/DECISION-tagged plan task,
  founder sign-off required per CLAUDE.md's "Stop ONLY when..." clause), separate from and not a
  blocker to shipping the rest of this attribution spine, which works fully without it.

### 2.5 Field addition to `crm.Lead` for the future Cloud-API path (build later, spec now)
```python
ctwa_clid = models.CharField(max_length=500, blank=True, null=True)
```
Additive, harmless to add now even before the Cloud API decision is made — costs nothing, and
having the column ready removes one step from that future migration. **Do not build the webhook
receiver or any code path that writes to it until the Cloud API adoption decision is made** — an
empty, unused nullable column is fine; unused webhook plumbing pointed at infrastructure that
does not exist yet is not.

---

## 3. Part (b) — Meta-vs-ERP reconciliation

### 3.1 The principle (already correctly identified in prior research, `ux-adtools.md` §5)
> "Never let the dashboard number diverge from Meta's own reported number without a visible
> caveat" — if the ERP computes a number differently from what Meta Ads Manager shows, **label
> the difference explicitly**, always, never let it be discovered later.

### 3.2 What gets compared, and what must NOT be pooled together
Two denominators must be shown, never merged into one "leads" figure:
1. **Meta-attributable leads** — `Lead.canal ∈ {meta_ads, whatsapp_ctwa}` (form leads via
   `source=meta_lead_ads`, and site/Traffic-ad leads via `utm_source` matching a known Meta value)
   for the period/campaign — this is the side compared against Meta's own reported number.
2. **All ERP leads** — includes `telephone`/`walk_in`/`reference`/`autre` (manual channels) that
   Meta has and will never have any knowledge of. These must be visible in the ERP's own totals
   (business reality — founder needs true weekly lead volume) but **excluded** from any
   Meta-comparison cell; showing them blended into a "Meta result" number is exactly the trust
   failure the reviewed tools (Triple Whale, C2 in `ux-adtools.md`) are criticized for.

Within (1), further split by **capture mechanism**, since each has a different failure mode:
- **Form leads** (Meta Lead Ads Instant Forms) — 1:1 matchable via `leadgen_id` = `external_id`
  (already the dedup key, `_META_LEAD_ADS_SYSTEM`). A missing form lead means either (a) the
  webhook never fired (subscription/token issue — visible via ENG12's wiring-health endpoint) or
  (b) `fetch_meta_lead_data` failed silently (already logged, `webhooks.py:917-922`, but never
  surfaced to a human today — this is a real gap: **a failed Lead Ads fetch today is swallowed
  with only a `logger.warning`, no `WeeklyBrief`/`EngineAlert` visibility** — the reconciliation
  view is the natural place to surface "N leadgen_ids received, M failed to fetch").
- **Site leads driven by Meta ads** (Traffic/Conversion objective, `utm_source` matches a Meta
  value) — matched via UTM only, inherits every UTM-tagging-discipline risk from part (a).
- **Manual channel leads tagged `whatsapp_ctwa`** — per §2.4, these are a *human's best guess*,
  not a Meta-confirmed attribution; the reconciliation view should visibly separate "confirmed
  Meta-side" leads from "self-reported CTWA" leads, since only the former can ever be checked
  against Meta's own count.

### 3.3 Dedup rules — reuse, do not reinvent
`find_duplicates_by_contact` (phone/email normalized) plus the existing first-touch-protection
rule (`_FIRST_TOUCH_FIELDS`, `crm/webhooks.py:43-49`) already correctly handle the cross-channel
duplicate case (e.g. someone clicks a Meta Lead Ads form, then also fills the site form, then also
calls): the record collapses to ONE `Lead` row, keeping the FIRST channel's attribution. This is
the right behavior for reconciliation too — **do not build a second dedup mechanism for
adsengine**; the reconciliation query should count deduplicated `Lead` rows (what already exists),
never re-count raw webhook payloads (`WebsiteLeadPayload` count would double-count revisits).

### 3.4 Tolerance logic — what a primary source will and will not tell you
**Primary source silent** on a numeric tolerance threshold — Meta does not publish an expected
delta between its own "Results" column and any third party's server-side count. Practitioner
reports (independent research already gathered, `ux-adtools.md` C2, Trustpilot Triple Whale
reviews) describe **15-25% real-world attribution gaps** as commonplace between an ad platform's
own reported results and a merchant's server-side count — **UNVERIFIED / folklore-grade
directional signal only**, not a number to hard-code as "correct."

Recommendation for TAQINOR's actual volume (5-15 leads/week, scaling to maybe 500 MAD/day): a
**percentage-only** threshold is unusable noise at this scale — a single lead swings the
percentage by 7-20% on any given day. Use a **combined rule**: flag a day/campaign cell only when
`|delta| ≥ 2 leads AND |delta| / max(meta_count, erp_count) ≥ 20%` — small enough to catch real
breakage (a dead webhook, a token expiry), large enough not to alarm-fatigue the founder on normal
day-to-day noise at this volume. **Tune this empirically once 4-8 weeks of real dual-counted data
exists** — do not treat the 20%/2-lead numbers above as final, they are a reasonable starting
point derived from folklore, not a measured TAQINOR baseline.

### 3.5 Display contract (the actual UX requirement)
Every campaign/day cell in the reconciliation view shows **both numbers side by side**, never one
number silently chosen. When the delta crosses the tolerance rule (§3.4): a visible badge, plus a
one-line French cause hypothesis drawn from a fixed taxonomy (webhook non reçu / fetch échoué /
attribution UTM manquante / lead manuel non-Meta inclus par erreur / fenêtre de comptage Meta
différente) — never a bare number with no explanation — and a link straight to the underlying
`Lead`/`WebsiteLeadPayload` rows behind the count, so a human can inspect in one click (the
Northbeam-praised pattern already flagged in `ux-adtools.md` P7).

### 3.6 A schema nuance this reconciliation depends on getting right
Meta's Insights API `actions` array reports many action types per campaign objective (`lead`,
`onsite_conversion.messaging_conversation_started_7d` for CTWA/messaging objectives, `link_click`,
etc.) — `InsightSnapshot.conversions` (ENG5) must map to the **objective-appropriate** action type,
not a single hardcoded key, or the Meta-side number being compared will itself be wrong before any
ERP-side comparison even starts. This belongs inside ENG5's "idempotent upsert service," flagged
here because reconciliation (b) is the first consumer that will notice if it's wrong.

---

## 4. Part (c) — Offline/CAPI feedback quality

### 4.1 Immediate fixes to the existing QJ9 hook (before touching anything new)
1. **Bump the API version.** `v19.0` → `v25.0` (current as of 16 Jul 2026, per Meta's own
   changelog) or better, a `META_CAPI_API_VERSION` setting with a sane default — hardcoding a
   version number that silently expires on a schedule is itself a recurring-maintenance bug class.
2. **Add `event_id`.** Deterministic, e.g. `f"signedquote:{devis.reference}"` — costs nothing,
   forecloses double-counting the moment any browser-side Pixel is ever added to `/proposal`.
   Meta's own dedup rule: same `event_name` + `event_id` within a 48-hour window → deduplicated
   automatically; after 48h, treated as distinct. `devis.reference` is unique and already the
   natural idempotency key elsewhere in this codebase (references.py) — reuse it.
3. **Thread `client_ip_address`/`client_user_agent` through.** `accept_devis(..., ip=None,
   user_agent='')` already receives both; `_fire_capi_signed_quote` currently drops them. Both are
   Meta-recommended `user_data` parameters for Event Match Quality — free EMQ improvement, no new
   data collection needed (the data is already captured for the chatter/consent log).

### 4.2 Event dedup, generally
`event_id` (per event) is the mechanism, 48-hour window, applies whenever the SAME logical
conversion could be reported from more than one source (browser Pixel + server CAPI being the
textbook case Meta's docs describe). TAQINOR has no browser Pixel today (verified: no Pixel/fbq
snippet found in the researched flow — `/proposal` is server-rendered), so the practical risk
today is near-zero, but §4.1.2 above is cheap insurance for when that changes (e.g. if a future
`WEB_PLAN` task adds client-side tracking to the tokenized proposal page).

### 4.3 Match-quality (EMQ) monitoring
EMQ (0-10 score, Meta's `Dataset Quality API`) is **not** returned inline in the `/events` POST
response — it must be pulled separately and periodically. Recommendation: fold this into ENG12
("wiring-health endpoint," already specced to track present/absent keys + last-webhook/last-CAPI
timestamps) rather than inventing a new model — extend it with a weekly Celery pull of the Dataset
Quality API score, stored on a small `company`-scoped row, surfaced on the same dashboard tile.
Do not attempt to reverse-engineer EMQ from the event payload alone; it genuinely requires the
separate API call.

### 4.4 Qualified-lead event definition — which STAGES.py transition fires it
This is the crux of the "future Conversion Leads optimization" ask, and where two currently-real,
currently-different conversion definitions need to be reconciled, not merged (per CLAUDE.md rule
#2's explicit "these two never merge" instruction — the fix below **respects** that instruction,
it does not violate it):

- **Keep the existing QJ9 hook exactly where it is** (fires on `Devis.statut → accepte`, the rule
  #4 document layer) — it is automatic, reliable, already-wired, and is the correct trigger for a
  `Purchase`-shaped conversion (`SignedQuote`, used for standard ROAS-style ad optimization).
- **Add a second, independent CAPI emitter for the CRM/Conversion-Leads integration**, hooked to
  `crm.Lead.stage` transitions (rule #2's pipeline layer) — this is what Meta's Conversion Leads
  product actually consumes; per the primary payload spec, `event_name` is a **free-form string**
  Meta explicitly says should mirror "the stages you use within your CRM" (their own example:
  Initial Lead → Marketing Qualified Lead → Sales Opportunity → Converted) — so the natural,
  zero-invention choice is to fire it with `event_name` = the STAGES.py **English key itself**
  (`CONTACTED`, `QUOTE_SENT`, `SIGNED`, …) on every forward transition, letting Meta's own CRM
  integration UI map whichever stage(s) the founder decides constitute "qualified" — no code-side
  guessing about which single stage is "the" qualifying one.
  - **Required payload shape** (primary-sourced): `action_source='system_generated'`,
    `custom_data.event_source='crm'`, `custom_data.lead_event_source='TAQINOR OS'`, `user_data`
    keyed by **`lead_id`** — and TAQINOR already stores exactly this value today, at zero schema
    cost: `Lead.external_id` when `Lead.external_system == 'meta_lead_ads'` **is** the Meta
    leadgen_id, the documented preferred matching key (15-17 digit Facebook-generated id).
  - **Only fires for leads that have a Meta-origin `external_id`** — a lead with no `lead_id` and
    no `fbclid`/hashed contact falls back to hashed email/phone (already computed in QJ9's
    `_sha256` helper — reusable, do not duplicate) or is simply not eligible for this integration
    (organic/manual leads, correctly excluded, matching the exclusion rule in part (a) §2.4).
  - **Gate this behind its own settings flag** (e.g. `META_CRM_STAGE_CAPI_ENABLED`), separate from
    `META_CAPI_ACCESS_TOKEN`/`META_CAPI_PIXEL_ID` — Meta's docs describe CRM/Conversion-Leads as
    "a separate integration...because the required parameters are different," and it typically
    needs its own opt-in step inside Meta Events Manager (connecting a CRM data source) — **flag
    this as a founder action item**, not something code alone can turn on.
  - **Timing constraint** (primary-sourced): event timestamp can be up to 7 days before send, but
    must be **after** the lead's generation time or Meta discards it — trivially satisfied by
    firing synchronously on the stage-transition signal (no backdating risk).

### 4.5 Net effect
Two CAPI event families, cleanly separated, matching CLAUDE.md's "never merge" instruction exactly
because they serve two different Meta products (standard conversion optimization vs. Conversion
Leads/CRM-stage optimization) and two different existing ERP layers (document status vs. pipeline
stage) — this is not new architecture, it is wiring both existing, correctly-separated layers to
the two Meta integrations that were built for that exact separation.

---

## 5. Part (d) — Reporting drill-downs beyond ENG23's dashboard

ENG23 specs one hero number (cost-per-signature) + spend/CPL/frequency tiles + a click-through to
the leads behind any number + an alert banner. What it does **not** spec, needed for this mission:

### 5.1 Per-variant table
Columns: creative/ad name (from `AdMirror.name`, falling back to raw `utm_content` string per the
attribution-tier ladder in §2.4, tier visibly marked), spend, leads (split by resolution tier),
cost-per-lead, cost-per-qualified-lead (using whichever `STAGES.py` transition the founder has
picked as "qualified," §4.4), a simple reply-rate proxy for WhatsApp-heavy creatives (matches
`ux-adtools.md` P3's adaptation note — "reply count and cost-per-reply per creative," not an
abstract CTR score). Sortable by cost-per-qualified-lead ascending — this table **is** the
bandit's reward function made visible, so it must show exactly the numbers the bandit consumes,
not a prettified approximation.

### 5.2 Per-campaign funnel
`NEW → CONTACTED → QUOTE_SENT → FOLLOW_UP → SIGNED` counts (+ `COLD`/`perdu` off to the side, per
STAGES.py's own model — "Perdu" is a flag, not a stage) for leads attributed to one campaign,
alongside Meta's own funnel-adjacent metrics (CTR, CPM) where available from `InsightSnapshot.raw`.
This is the view that answers "is this campaign bringing bad-fit leads that never move, or good
leads that are just slow" — a question neither ENG10's single blended number nor Meta's own UI
answers directly.

### 5.3 Cohort view — leads by week → signature lag
Group `Lead` by `date_creation` week, plot forward: what fraction reached `SIGNED` (or the chosen
qualifying stage) by week 1/2/4/8/12 after creation, using `Devis.date_acceptation - Lead.date_creation`
where a `Devis.lead` link exists. At TAQINOR's volume (a handful of signatures/month), this is
better shown as a simple table (cohort week × lag bucket × count) than a chart — smoothing curves
over single-digit counts is actively misleading. This view is what lets the founder distinguish
"this month's campaign looks bad" from "this month's campaign is just still in its lag window" —
directly relevant given "a handful of signatures/month" means most cohorts will still be incomplete
at reporting time; the UI must show incomplete cohorts as visibly incomplete (e.g. greyed/dotted
for weeks not yet elapsed), never as a final zero.

### 5.4 Export
CSV export of the per-variant table and the reconciliation table (§3), same columns as displayed —
no separate export-only schema, no server-side Excel generation dependency (avoid adding a new
paid/heavy dependency for something a plain CSV response satisfies; flag as DEP only if a founder
specifically asks for formatted Excel later).

---

## 6. Part (e) — ENG10 delta: what it already covers vs. what ADSENG must add

| Capability | ENG10 (specced, unbuilt) | ADSENG delta this dossier specs |
|---|---|---|
| Granularity | Campaign/channel (`canal`/`utm_campaign`) | **Ad/variant level** (`meta_ad_id`, §2.2) — the actual bandit reward signal |
| Conversion definition | `SIGNED` stage count (STAGES.py) | Same, **but explicitly separate from** the already-wired `Devis.accepte` CAPI trigger (§4.4) — ENG10's number and QJ9's CAPI event are not currently the same event, and the dashboard must say which one it's showing |
| Data source read path | `apps/crm/selectors.py` (read-only, correct pattern — keep) | Same pattern, extended to read `meta_ad_id`/`ctwa_clid` once added |
| Attribution join key | Implicit (whatever `utm_campaign` happens to hold) | Explicit resolution-tier ladder (§2.4) — **never silently pools** organic/unresolved/confirmed leads |
| Meta Lead Ads UTM population | **Broken today** (finding #2/#3) — not ENG10's fault, it's upstream in `crm/webhooks.py`/`services.py` | **Must be fixed before ENG10's own numbers are trustworthy for the Lead Ads channel** — flag as a prerequisite, not a parallel task |
| CTWA | Not addressed | Precise capability boundary specced (§2.4) — no code to build until the Cloud API decision is made; `ctwa_clid` column ready when it is |
| Reconciliation vs Meta's own reported numbers | Not addressed — ENG10 computes an ERP-side number only | Full spec in part (b): two denominators, dedup reuse, tolerance rule, display contract |
| CAPI feedback loop / EMQ | Not addressed (ENG10 is CRM→dashboard, one-directional) | Full spec in part (c): version-bump + `event_id` fix, EMQ pull folded into ENG12, second CRM-stage CAPI emitter |
| Reporting depth | One dashboard, hero number + tiles + drill-to-leads (ENG23) | Adds: per-variant table, per-campaign funnel, cohort/lag view, export (part d) |
| Schema | None new specced beyond existing `Lead` fields | Additive-only: `Lead.meta_ad_id`, `meta_adset_id`, `meta_campaign_id`, `ctwa_clid` (nullable, §2.2/§2.5) + 3 new indexes (§2.3) |

**Bottom line**: ENG10 is the right shape (blend spend × CRM leads × SIGNED count, read-only via
selectors, lead-id traceability) — this dossier does not replace it, it specs the missing
dimension (variant, not just campaign) plus the three adjacent systems ENG's spec text does not
mention at all: reconciliation-vs-Meta, CAPI feedback quality, and the reporting drill-downs an
"AI ads engine that runs unattended for months" actually needs to be trustworthy at TAQINOR's
low-volume, cost-per-signature-not-ROAS scale.

---

## Sources

Primary (Meta-owned, fetched/verified 16 Jul 2026):
- [Leads - Webhooks from Meta](https://developers.facebook.com/docs/graph-api/webhooks/getting-started/webhooks-for-leadgen/) — exact leadgen webhook `value` field list (`leadgen_id`, `page_id`, `form_id`, `adgroup_id`, `ad_id`, `created_time`; campaign_name/adset_name NOT included)
- [Retrieving Leads guide](https://developers.facebook.com/documentation/ads-commerce/marketing-api/guides/lead-ads/retrieving) — lead-node requestable fields (`ad_id`, `form_id`, `field_data`, `custom_disclaimer_responses`; campaign/adset names require a separate call)
- [Conversions API for Business Messaging](https://developers.facebook.com/docs/marketing-api/conversions-api/business-messaging/) and [Ads that Click to WhatsApp](https://developers.facebook.com/documentation/ads-commerce/marketing-api/ad-creative/messaging-ads/click-to-whatsapp) — `ctwa_clid`, `action_source=business_messaging`, "should not be hashed"
- [Conversion Leads integration — Payload Specification](https://developers.facebook.com/docs/marketing-api/conversions-api/conversion-leads-integration/payload-specification/) — required fields (`action_source=system_generated`, `custom_data.event_source=crm`, `custom_data.lead_event_source`), `lead_id` as recommended matching key (15-17 digit), free-form `event_name`, 7-day pre-dating window, must-be-after-lead-creation constraint
- [Marketing API versions changelog](https://developers.facebook.com/docs/marketing-api/marketing-api-changelog/versions/) — confirmed v19.0 released 23 Jan 2024, **expired 4 Feb 2025**, retired as of Jul 2026; v25.0 current
- [messages webhook reference](https://developers.facebook.com/documentation/business-messaging/whatsapp/webhooks/reference/messages) (partial — full referral-object schema not retrievable from this page alone; corroborated via independent sources below)

Independent/practitioner (used only where explicitly flagged, cross-checked against the primary
CTWA/business-messaging docs above for internal consistency):
- WhatsApp Cloud API `referral` object field list (`ctwa_clid`, `source_id`, `source_type`,
  `headline`, `body`, `media_type`, `source_url`) and the Cloud-API-only requirement — converged
  across multiple independent integrator docs (Twilio, Sinch, Woztell, 360dialog, GitHub issue
  threads for Typebot/openclaw) in the WebSearch pass; no single primary Meta page fully quoted
  the schema in this session's fetch, but the requirement itself ("free WhatsApp Business App
  cannot receive webhooks/referral data; Cloud API or a BSP is required") is stated identically and
  independently by every source checked — treated as reliable, not single-sourced folklore.
- Triple Whale 15-25% attribution-gap figure (Trustpilot reviews, already gathered in
  `ux-adtools.md` C2) — UNVERIFIED/folklore-grade, used only to justify starting-point tolerance
  values in §3.4, explicitly not treated as a TAQINOR-applicable measured number.

Repo (ground truth, read directly, 16 Jul 2026, path prefix
`C:/dev/taqinor-os/.claude/worktrees/great-neumann-fc8b39/`):
- `STAGES.py`, `backend/django_core/apps/crm/models.py`, `backend/django_core/apps/crm/webhooks.py`,
  `backend/django_core/apps/crm/services.py` (`create_lead_from_meta_lead_ads`),
  `backend/django_core/apps/ventes/services.py` (QJ9 block, `_persist_attribution`,
  `_fire_capi_signed_quote`, `accept_devis`), `backend/django_core/apps/ventes/models.py` (Devis
  fields), `docs/PLAN.md` (ENG1-31 block, lines ~1291-1360)

Prior dossiers consulted, not re-derived: `erp-arch.md` (adsengine app-placement architecture,
model shapes for `AdCampaignMirror`/`AdSetMirror`/`AdMirror`/`InsightSnapshot`/`EngineAction`),
`ux-adtools.md` (reconciliation/trust UX lessons, P7/C2/C3), `eng-meta-tooling.md` (Marketing API
version cadence, CLI/MCP context), `scope-repo.md` (verified ENG1-31 task list + status).
