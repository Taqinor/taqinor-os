# Experimentation & measurement policy (WJ93)

**Why this doc exists.** The site currently runs cookie-free (no analytics
cookie, no experiment cookie, no persisted visitor ID anywhere) — that is
precisely what keeps it consent-banner-free for EU visitors under GDPR (no
Set-Cookie means no "non-essential cookie" consent gate is legally required).
The alternative — a conventional cookie-based A/B testing tool — would
silently drag in that banner and, at current traffic, would mostly produce
noise dressed up as a "winner." This doc is the written policy; the
substrate it authorizes is `apps/web/src/lib/edgeVariant.ts`.

## Rule 1 — no cookies, no persisted IDs, anywhere in analytics/experiments

- No `Set-Cookie` header, no `localStorage`/`sessionStorage`-based visitor
  ID, no fingerprinting, is ever used for analytics or experimentation
  purposes on this site.
- This applies to every current and future measurement surface: the
  WJ55/WJ59 funnel telemetry event stream, WJ94's Cloudflare Web Analytics
  beacon, and any staged rollout built on `edgeVariant.ts`.
- Consequence: no cross-session visitor identity exists for
  analytics/experiments. Every request/session is measured independently.
  This is the trade we accept in exchange for staying consent-banner-free.
- This rule is scoped to analytics/experimentation. It does not change lead
  capture (`lead.ts`), which already collects consented contact data through
  a completely separate, explicit-consent path (`consent: true` required in
  `validateLead`) — that data is never used to stitch analytics identity.

## Rule 2 — no inferential A/B below ~50 conversions/variant/week

Classic A/B testing (two variants, statistical-significance winner) needs
enough weekly conversions per variant (rule of thumb: ~50/variant/week) to
produce a signal that isn't just noise. Below that volume, a measured
"winner" is very likely a coin flip that happened to land heads.

At the site's current traffic, **do not run inferential A/B tests**. Use
these two techniques instead:

1. **Staged rollout.** Ship the change to 100% of traffic (or a fixed,
   non-random slice for a monitoring period) and watch the funnel metrics
   before/after. No variant comparison, no statistics — just "did the
   numbers get worse."
2. **Funnel comparison.** Compare step-to-step conversion (journey_step_viewed
   → journey_step_completed → estimate_rendered → whatsapp_clicked →
   proposal_viewed → proposal_signed, per the WJ91 telemetry vocabulary)
   across time periods or traffic sources that already naturally exist
   (e.g. `meta` vs `google` per the UTM vocabulary in
   `docs/utm-governance.md`), rather than manufacturing a synthetic split.

Once weekly conversions per variant genuinely clear ~50, a true randomized
A/B primitive can be reconsidered — as a deliberate future decision, not the
default today.

## Rule 3 — `edgeVariant.ts` is the staged-rollout substrate, not an A/B tool

`apps/web/src/lib/edgeVariant.ts` provides a per-request variant draw with:

- **No `Set-Cookie`.** The caller decides what to do with the returned
  variant (e.g. render one branch server-side for this response); nothing
  persists it for the next request.
- **No persisted ID.** The draw is either a deterministic hash of a
  per-request value the caller already has (e.g. a request header), or a
  stateless random draw — either way, nothing is stored, and the same
  visitor is free to get a different draw on their next request. That is
  intentional: it is what keeps the mechanism cookie-free, at the cost of
  not supporting classic sticky-per-visitor A/B (see Rule 2 — we don't want
  that anyway, at this volume).
- **Zero dependencies.** Pure TypeScript, usable at build time or at the
  edge (Cloudflare Workers), with no external service.

Use it to gate a staged rollout (e.g. "50% of requests see the new hero
copy this week") whose effect is then read via funnel comparison (Rule 2),
never via a cookie-tracked per-visitor split.

## Scope

This policy governs `apps/web` analytics and experimentation only. It does
not apply to authenticated ERP sessions (a different product, different
consent model) and does not restrict the lead-capture consent flow, which
is explicit, purpose-specific, and already GDPR/loi 09-08-compliant on its
own terms.
