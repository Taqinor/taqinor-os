# tos_risk/ — scraper risk-file gate

This directory is the gate for any scraper that carries Terms-of-Service (ToS)
risk. It is enforced by founder rule #5 in `CLAUDE.md`.

## The rule

Scrapers must **never** run from personal accounts. Any scraping with ToS risk
requires **both** of the following before the first run:

1. **A committed risk file** in this directory (`tos_risk/`) describing:
   - **Target** — the site/service being scraped and the specific endpoints.
   - **Risk** — what the target's ToS says, and what could go wrong (account
     ban, IP block, legal exposure, rate-limit retaliation).
   - **Mitigation** — how the risk is reduced (dedicated account, rate limits,
     caching, respect for `robots.txt`, backoff, kill switch).

2. **Explicit manual approval from the founder** before the first run. Approval
   is per-target; approving one scraper does not approve another.

## How to add a scraper

1. Copy the template below into a new file named for the target, e.g.
   `tos_risk/<target-slug>.md`.
2. Fill in every section honestly.
3. Commit it, then get the founder's explicit go-ahead. Only then may the
   scraper run — and never from a personal account.

## Template

```markdown
# Scraper risk file — <target name>

- **Target:** <domain + endpoints>
- **Account used:** <dedicated service account — never personal>
- **ToS summary:** <what the target's terms say about automated access>
- **Risk:** <ban / block / legal / other, and likelihood>
- **Mitigation:** <rate limits, caching, backoff, kill switch, robots.txt>
- **Founder approval:** <date + "approved by founder">
```

No scraper exists in this repo today. This gate binds the first one that lands.
