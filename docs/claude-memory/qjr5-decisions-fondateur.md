---
name: qjr5-decisions-fondateur
description: Founder decisions of 30/09–01/10/2026 on the QJR5 quote-journey group (gated questions QJR659-669, QJR612 battery floor, client-visible changes)
metadata:
  type: project
---

Reda's decisions on the QJR5 « devis = parcours modifiable » group (docs/PLAN2.md), 30/09–01/10/2026:

- **QJR612** — night EV charging raises the battery floor AND the sizing adds panels so the bigger battery still fills every day (« batteries toujours pleines » is a standing ERP rule for batteries in general).
- **QJR659** — sharing the PDF from the quote list (native share sheet resolved) marks the quote sent.
- **QJR660** — after an in-place correction, follow-ups keep the ORIGINAL cadence (no re-dating).
- **QJR661** — only a draft can be deleted; every other status is archived.
- **QJR662** — industrial/commercial leads: the engine falls back read-only on the website-declared monthly kWh (bill_kwh) when no consumption is typed; never residential.
- **QJR663** — website leads still undelivered after retries go to a Cloudflare KV dead-letter (binding `LEADS_DLQ`, 7-day TTL, cron resend). The KV namespace is created by Reda in the dashboard; until then the code is a no-op.
- **QJR664** — the « Une journée type » chart is shown in FR, EN and AR.
- **QJR665** — the C&I study uses the same national-tariff consumption as the sizing sweep (never bills ÷ 1.75).
- **QJR666** — explicit PDF-dialog options are added to the premium residential template (no fallback to the old engine).
- **QJR667** — multi-site lots and « ajouter le BOQ électrique » get screens (contract first), not deletion.
- **QJR668** — per-deal CGV clauses are wired: frozen at send, re-frozen on each correction, printed.
- **QJR669** — prix/kWc (BI) follows the corrected, sent quote.
- **Client-visible changes** of M1, M2, lots 3-4 (centime amounts, signed copy, discount guard on every send, client identity follows the lead, size cards priced with the quote's kit…) were confirmed by Reda before each merge.

**Why:** these were the open questions of the 30/09 L3 audit; they are now settled.
**How to apply:** don't re-ask them; build on them. See [[devis-parcours-modifiable-qjr5]].
