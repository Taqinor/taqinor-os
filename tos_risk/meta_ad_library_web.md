# Scraper risk file — Meta Ad Library (public website, commercial ads outside the EU and UK)

Status: **NOT APPROVED — no run permitted.** Written 28 September 2026 at the founder's request
(« provider in the client offer, experiment on our side »). Per rule #5, the first request may only
be sent after the founder writes his approval in the last section of this file.

- **Target:** the public Meta Ad Library website, `https://www.facebook.com/ads/library/` and the
  internal data endpoint the page itself calls to list ads (a GraphQL query on `facebook.com`).
  Scope of the experiment: commercial ads for countries that Meta's official Ad Library API does
  not serve (United States, Australia, Morocco). EU and UK ads are NEVER scraped: Meta's official
  API covers « ads of any type delivered to the UK or EU during the past year » and is the only
  path used for those regions.
- **Account used:** none. The Ad Library is readable logged-out and the experiment sends no
  cookie and no token. The experiment runs from a throwaway cloud virtual machine created for it,
  carrying none of TAQINOR's Meta identities (no ad account, no developer app, no CAPI token, no
  WhatsApp/BSP credentials), never from the production server, never from a personal machine or a
  personal connection. Outbound traffic goes through a proxy service paid on a company account.
- **ToS summary:** Meta Terms of Service (effective 1 January 2025), section 3.2: « You may not
  access or collect data from our Products using automated means … regardless of whether such
  automated access or collection is undertaken while logged in ». Meta Automated Data Collection
  Terms (revised 7 October 2024): express written permission required; Meta may revoke it, require
  deletion of collected data and terminate other agreements; the collector indemnifies Meta. These
  are contract terms. Statute: no US federal statute makes reading a public page a crime in itself
  (hiQ v. LinkedIn, 9th Cir. 2022, preliminary injunction; Van Buren fn. 8 leaves contract limits
  open); EU Directive 2013/40 requires « infringing a security measure »; Australian Criminal Code
  s.478.1 covers access-controlled data only; the UK Computer Misuse Act has no public-website
  exception (untested), so the experiment never runs from the UK. Meta v. Bright Data (N.D. Cal.,
  Jan. 2024) held the OLD terms did not bar logged-off scraping of public data; the 2025 terms close
  that gap. Sources: documents/2026-09-28-offre-veille-pubs-meta/sources-verified-2026-09-28.md in
  the memory repository (entries M4, M5, L5, L7, L9, L11, L12, L14).
- **Risk:**
  1. Contractual: whoever collects is the collector under Meta's terms. If the collector can be
     linked to TAQINOR's Meta accounts, Meta may terminate them — the solar lead-ads pipeline, the
     CAPI, the WhatsApp integration. Likelihood low for a small logged-out experiment from unrelated
     infrastructure, impact very high. This is why the infrastructure isolation above is absolute.
  2. Technical: IP blocks, CAPTCHAs, rate limiting and machine-learning bot detection (the
     countermeasures Meta listed in the Bright Data case). Likelihood high at volume, impact = the
     experiment stops. The experiment is deliberately small.
  3. Data protection: an advertiser or payer can be a natural person (sole trader). Mitigated by
     collecting business fields only and deleting the raw dataset after analysis.
  4. Commercial: a collector shipped inside a product sold to a client would make the CLIENT the
     collector on their own server. Therefore this connector is never delivered to a client as a
     feature; client offers use Meta's official API (EU, UK) and a third-party data provider (US,
     Australia).
- **Mitigation:**
  - No run before the founder's written approval below; approval is for this experiment only, not
    for any production use, which would need a second approval and an updated file.
  - Isolated infrastructure (see « Account used »); the VM is destroyed at the end of the day.
  - Volume cap: at most 2,000 ads in total, at most one request every 5 seconds, one worker, no
    parallelism; hard stop on the first CAPTCHA, HTTP 4xx burst or block; a kill switch checked
    before every request.
  - Only public ad fields are stored (archive id, page name and id, page category, ad text, button,
    landing domain, media URLs, dates, platforms); no download of images or videos; no person-level
    enrichment; the dataset is deleted after the measurements are written up.
  - `robots.txt` of facebook.com is read and recorded; the experiment sends a descriptive
    User-Agent; no attempt to defeat a CAPTCHA (a CAPTCHA ends the experiment).
  - Code lives behind the same source interface as the official-API and provider connectors, is
    disabled by default (`ADINTEL_WEB_CONNECTOR_ENABLED=False`), and is excluded from any client
    delivery profile.

## One-day experiment plan (what we want to learn)

1. **Feasibility of the feed.** Can a logged-out request to the page's internal endpoint list ads
   for a keyword and a country (US, AU, MA) and paginate? Record the request shape and the pagination
   cursor behaviour.
2. **Page size and fields.** Ads returned per page (the number assumed at 30 in the pricing example)
   and the exact fields available, in particular `page_categories`, the call-to-action, the landing
   link, dates and platforms. This settles the one unverified number in the client pricing document.
3. **Blocking behaviour.** At one request every 5 seconds from one datacenter IP, then from one
   residential proxy IP: after how many requests does Meta throttle, challenge or block? Record the
   status codes and the time to the first challenge. Stop at the first challenge.
4. **Cost per 1,000 ads if we did it ourselves.** Proxy traffic per page (Apify lists residential
   proxies at $8 per GB) versus the provider prices already verified (ScrapeCreators $1.88 per 1,000
   requests, Apify community actor $0.75 per 1,000 ads). Expected outcome: the provider is cheaper
   than the proxy traffic alone; the experiment measures it.
5. **Morocco.** Same measurements for `country=MA` with solar keywords, TAQINOR's own use case, where
   the official API returns nothing commercial and providers are the only alternative.
6. **Write-up.** A one-page result in the memory repository (volumes, page size, fields, block
   thresholds, cost per 1,000) and a go/no-go on keeping the connector as a dormant fallback. No
   production schedule is created; the VM and the dataset are destroyed.

Go/no-go criteria for keeping the code as a dormant fallback: the feed is readable logged-out with
the fields above; no CAPTCHA within the capped volume; a documented cost per 1,000 ads. Any of the
following ends the idea: a challenge on the first requests, a required login, or any sign that the
activity can be tied to TAQINOR's Meta accounts.

## Founder approval

- **Founder approval:** PENDING. Not approved as of 28 September 2026. To approve, replace this line
  with « approved by founder » and the date, and commit.
