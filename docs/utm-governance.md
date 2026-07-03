# UTM governance (W381)

**Why this doc exists.** `apps/web/src/lib/lead.ts` forwards `utm_source`,
`utm_medium`, `utm_campaign`, `utm_content`, `utm_term` **verbatim** to the CRM
webhook (see `UTM_KEYS` in `lead.ts` and `validateLead`'s pass-through loop —
each value is only length-capped via `cleanStr`, never normalized or
validated against a vocabulary). Nothing in code enforces casing or a closed
value set today. Without a written convention, values drift within a quarter
(`Facebook` vs `facebook` vs `fb`, `Cpc` vs `cpc`) and attribution reports in
the CRM silently fragment. This doc is the single reference every campaign
builder (Meta Ads, Google Ads, WhatsApp/social bio links, partner embeds)
must follow. It does not change any code — `lead.ts` keeps accepting
whatever arrives and forwarding it as-is; this is the discipline for what we
*put into* the links we control.

## Rule 0 — casing

All UTM values are **lowercase, snake_case, ASCII only** (no accents, no
spaces — use `_`). This matches the existing param keys themselves
(`utm_source`, not `UTM_Source`) and is the universal GA4/Meta/most-ad-tools
convention, so campaign builders elsewhere don't need a second mental model.

## Rule 1 — `utm_source`: closed vocabulary

The traffic sources the site already implies today:

| Value | Where it comes from |
|---|---|
| `meta` | Meta Ads (Facebook/Instagram) campaigns — pairs with `fbclid` capture (CAPI, see WJ92) |
| `google` | Google Ads |
| `instagram` | Organic Instagram bio/post links (not paid — paid Instagram is `meta`) |
| `tiktok` | Organic TikTok bio/post links |
| `whatsapp` | Links shared via WhatsApp (Channel, forwarded messages, Status) |
| `liens` | The `/liens` link-in-bio hub itself (W350), when the hub page is the referring surface rather than a specific network |
| `partner` | Partner-site embeds (W358's `/embed/estimation`) |
| `direct_qr` | Printed materials / QR codes (flyers, vehicle decals, site signage) |
| `newsletter` | Any future email send |

Do not invent a new `utm_source` value without adding it to this table first.
If a genuinely new channel appears (a new ad network, a new social platform),
add one row here in the same commit that starts using it.

## Rule 2 — `utm_medium`: closed vocabulary

| Value | Meaning |
|---|---|
| `cpc` | Paid click (Meta Ads, Google Ads) |
| `social` | Organic social post/bio link |
| `referral` | Partner or third-party site link |
| `print` | Offline / printed / QR |
| `email` | Newsletter or transactional-adjacent email |

`utm_source`/`utm_medium` pairs should stay coherent — e.g. `meta` + `cpc` for
paid Meta campaigns, `instagram` + `social` for an organic bio link. A
`meta` + `social` pairing (organic Meta) is valid too; what's invalid is
mixing a paid source with the `social`/`referral` mediums or vice versa.

## Rule 3 — `utm_campaign`, `utm_content`, `utm_term`: free text, but disciplined

These three stay free-form (campaign names change constantly and a closed
list would be immediately stale), but still follow Rule 0's casing:
lowercase, snake_case, ASCII. Suggested shape:

- `utm_campaign` — short campaign slug, e.g. `ete_2026`, `agricole_pompage_q3`.
- `utm_content` — distinguishes creatives/placements within one campaign,
  e.g. `video_a`, `carousel_b`, `story`.
- `utm_term` — paid-search keyword only (Google Ads); leave unset elsewhere.

## Rule 4 — where this is consumed

- `apps/web/src/lib/lead.ts` reads all five keys from the request query
  string, keeps only non-empty ones (`Partial<Record<UtmKey, string>>`), and
  forwards them to the CRM webhook untouched — see `UTM_KEYS` and the
  `utm` field on `LeadRecord`.
- `redactLeadForLog` in the same file logs only the **key names present**
  (`utmKeys: Object.keys(record.utm).sort()`), never the values — so casing
  drift wouldn't even surface in logs; it only surfaces later, in the CRM's
  attribution reporting, which is exactly why this has to be enforced at the
  link-creation step, not the code.
- Nothing in `lead.ts` validates values against this vocabulary (by design —
  the webhook must never reject a lead over a malformed UTM param). This doc
  is the process control; there is no code gate.

## Change process

Adding a new `utm_source` or `utm_medium` value: update the table above in
the same change that starts using it. Do not add a new value silently in an
ad platform without a corresponding row here.
