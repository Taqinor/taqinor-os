# Risk file — Meta Ad Library API (official `ads_archive`, EU + UK, YanBow veille pilot)

Status: **NOT APPROVED — no real call permitted.** Written 4 October 2026 (task VEIL42 of
`docs/plans/PLAN_VEILLE.md`). Rule #5 targets scrapers; the official API is not one, but the
risks under Meta's terms are real, so this file follows the `tos_risk/README.md` template and the
first real call (VEIL41, probe `tools/adlib_probe/`) waits for the founder's signature in the last
section. No token exists today.

- **Target:** Meta's official Ad Library API only: the Graph API edge `ads_archive`
  (`https://graph.facebook.com/v25.0/ads_archive`) and `debug_token` for the probe's token-lifetime
  measurement. Read-only. No page of the Ad Library website, no internal endpoint, no login
  automation, no scraping of any kind, no write path of any kind (campaign creation stays
  forbidden by rule #3; `meta_client.py` is never used here).
- **Account used:** the founder's REAL Facebook account, identity confirmed, owner of a dedicated
  Meta developer application « YanBow Veille » that has NO TAQINOR Business Manager / business
  portfolio attached. Never a second account, never an automated sign-in to the website.
  Decision of 3 October 2026 (D-VEIL-7, D-VEIL-12). Why the « never personal » rule of scraper
  files does not apply here: that rule protects against scrapers breaching terms; Meta REQUIRES a
  confirmed identity to use this API, and creating a second account is the number-one reason for
  bans. Access is reserved to the company « YanBow » in the ERP (setting
  `VEILLE_SOCIETES_AUTORISEES`, default empty = nobody): no other ERP company can start a
  discovery under this token (Platform Terms §7.e.ii).
- **ToS summary** (Meta Platform Terms; clause numbers as read on 3 October 2026):
  - §3.a.iv: platform data may not be sold, licensed or purchased.
  - §12.l: « derived » data is covered by the same restrictions as the data it comes from.
  - §5.a: a Service Provider may process data for a client on the client's own behalf.
  - §6.a.iv: a token may be shared only with a Service Provider acting for the token's owner.
  - §7.e.ii: Meta may sanction the account(s) behind misuse of the API, including the personal
    account of the person who owns the app.
  - §7.e.iii: access is cut after 28 days without use.
  - §3.d.i: data must be deleted when no longer needed, on stopping, at Meta's request, and when a
    client leaves.
- **Risk:**
  1. Sale of data (§3.a.iv, §12.l): handing a client files or lists derived from results obtained
     under the founder's test token would be a sale of derived data. Likelihood: only if D-VEIL-7
     is ignored. Impact: loss of API access.
  2. Sanction on the personal account (§7.e.ii): a breach lands on the founder's real Facebook
     account, which may also administer TAQINOR assets. Impact: very high.
  3. Token exposure (§6.a.iv): the token could leak, for example inside `ad_snapshot_url` links
     (not verified: third-party sites show `…&access_token=…`; probe experiment E7 measures it),
     in logs, or by being shared with anyone other than a Service Provider.
  4. Cut-off after 28 days without use (§7.e.iii): the pilot silently stops working; a measurement
     campaign must finish inside one active window or the token must be re-validated.
  5. Quota blocking: Meta's rate formula (« 200 × users per hour », header `X-App-Usage`, codes
     4/17/32/613) with an unpublished block duration; ignoring it risks a longer block.
  6. Retention (§3.d.i): keeping advertiser data longer than needed.
- **Mitigation / guardrails:**
  - VEIL12: Ad Library settings read ONLY from the environment (`META_AD_LIBRARY_*`), fully
    separate from `MetaConnection` and every TAQINOR campaign token; feature off by default.
  - VEIL13: isolated, read-only `ads_archive` client; it never retries codes 4/17/32/613 and
    reads `X-App-Usage`; no quota-circumvention path.
  - VEIL16: on-demand launch, one Celery task = one call, quota guard, resumable; reserved to the
    allowed companies only (`VEILLE_SOCIETES_AUTORISEES`, D-VEIL-12).
  - VEIL19: configurable retention (`VEILLE_CONSERVATION_PUBS_JOURS`, default 90, a prudence
    choice, no text imposes it) and a `veille_purger --company <id>` command that deletes a
    client's data (§3.d.i).
  - VEIL40: the probe `tools/adlib_probe/` — hard cap of 150 calls, JSONL journal that never
    contains the token, pause at `X-App-Usage` >= 75 %, wait-then-stop on 4/17/32/613, stop on
    10/190; run by the founder locally only.
  - Pilot results obtained under the founder's test access are an ON-SCREEN DEMONSTRATION, free,
    with no file or list handed over (D-VEIL-7). Production at a client runs under THE CLIENT's
    own official access, YanBow as technical service provider (§5.a, §6.a.iv) — never a sale of
    data.
  - `ad_snapshot_url` tokens, if present, are stripped before any storage or display.
  - Keep the pilot used at least once every 28 days while it is live (§7.e.iii), or accept
    re-validation.
- **To verify by the founder BEFORE the first call:** does this Facebook account administer the
  TAQINOR Business Manager or ad accounts? Answer given on 3 October 2026: « I don't know ». If
  yes, FIRST add a second REAL administrator on TAQINOR (so a sanction on this personal account
  cannot orphan the company's ad assets). Also confirm the token comes from the dedicated
  « YanBow Veille » application, never from another source.
- **Founder approval:**
