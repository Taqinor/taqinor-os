# Guardrails for autonomous generation+publish — research findings
Research date: 2026-07-18. Scope per brief: (a) claim-checking, (b) brand/policy linting,
(c) tiered-autonomy precedent, (d) blast-radius limiters, (e) rollback/audit story.
Tag convention: [VERIFIED] = corroborated by a primary/official source or multiple independent
secondary sources describing a documented mechanism; [UNVERIFIED] = single vendor/blog claim,
promotional source, or my own extrapolation/synthesis not directly sourced.

---

## (a) Automated claim-checking — production patterns

**NLI/entailment checking** — the standard production pattern is: does the retrieved context
*entail* the generated claim? Guardrails AI runs an NLI model per-sentence (long answers are
split into individual claims, one NLI call each). [VERIFIED — icertglobal.com/community,
guardrailsai.com/docs]

**Named validator libraries (Guardrails Hub, guardrailsai.com/hub):**
- `provenance-llm` — embeds generated text and source text, compares embeddings to score whether
  a claim is actually traceable to source. [VERIFIED — guardrailsai.com/hub]
- `qa-relevance` — second LLM call asks "was the response relevant/grounded in the prompt?"
  [VERIFIED]
- `fact-checking` validator — purpose-built for factuality / brand-risk reduction in generated
  content. [VERIFIED]
- `toxic-language` — language-agnostic toxicity screen, usable as a brand-safety net alongside
  policy linting. [VERIFIED]
- **NeMo Guardrails** (NVIDIA, Apache-2.0, Colang DSL) — topical rails + fact-checking rails,
  4,200+ GitHub stars, widely cited as the other major open framework alongside Guardrails AI.
  [VERIFIED — medium.com/data-science-collective, aisecurityandsafety.org]

**Purpose-built groundedness/hallucination scorers (cheaper+faster than LLM-as-judge, viable
per-request):**
- **Vectara HHEM** (Hughes Hallucination Evaluation Model) — outputs a Factual Consistency Score
  0 (hallucination) → 1 (consistent); HHEM 2.1 is a small dedicated model, described as "the most
  production-ready generative-AI hallucination detector." [VERIFIED — vectara.com/blog, official]
- **Patronus Lynx** — small specialized judge model fine-tuned specifically to score whether a
  RAG answer is faithful to its context; positioned as detecting grounding hallucination at a
  fraction of the cost/latency of a frontier-model judge, which is what makes per-request
  checking economically viable. [VERIFIED — bestaiweb.ai citing Patronus/Vectara comparison]
- AWS Bedrock "Contextual Grounding" check is named alongside these as a third production vendor
  in 2026 tooling roundups. [UNVERIFIED — only seen in a secondary aggregator, not fetched from
  AWS directly]

**Anthropic Citations API** (native to our own model family) — chunks source documents to
sentence level, and when enabled, the model's output carries `cited_text` linking each claim to
the exact source passage; official docs note this beats prompt-only "please cite your sources"
in precision, and cited text doesn't count toward output tokens. This is the most directly
applicable building block for TAQINOR: feed the fact-table (prices, kWc, garantie, ROI figures)
as the "source document," require citations, and reject any generated sentence that has no
citation anchor. [VERIFIED — claude.com/blog/introducing-citations-api, platform.claude.com/docs]

**Numeric-claim extraction — regex+NER hybrid (the concrete implementation pattern for
"checked-facts-only"):**
- Documented production pattern: deterministic regex runs first (catches well-formed numbers,
  currencies, percentages, dates, IDs with high precision); an NER/LLM pass is invoked *only* when
  regex returns nothing or a conflict — this cuts token cost and keeps behavior mostly
  deterministic/auditable. [VERIFIED — arxiv 2606.28002 hybrid NLP pipeline pattern, generic not
  ad-specific]
- Academic work exists specifically on numeric/temporal claim fact-checking (CLEF-2026
  CheckThat! Lab has a dedicated task; one method rewrites each numeric claim as a focused
  question, retrieves evidence via dense+BM25 fusion, and issues a verdict). This validates that
  numeric claims are treated as a distinct, harder sub-problem worth its own pipeline stage, not
  lumped into generic hallucination detection. [VERIFIED as an active, named research
  benchmark — arxiv 2602.09516]

**Concrete recommendation for TAQINOR:** maintain a single machine-readable fact table (JSON:
each fact = value + unit + source + verified_date + which product/offer it applies to). At
generation time, ground the model against it via citations (or simple prompt-injection of only
the relevant rows). At validation time, regex-extract every number+unit token in the generated
copy and require an exact (or tolerance-banded) match to a whitelisted row for that offer; zero
matches or a mismatch = hard reject, never soft-flag (this is a harder bar than any of the
sourced tools apply by default — it is the right calibration for a zero-tolerance rule like
CLAUDE.md's checked-facts-only). Add HHEM/Patronus-style groundedness scoring or the Guardrails
`provenance-llm` validator as a *second net* for soft/paraphrased claims regex can't catch
("nos panneaux durent des décennies" has no number to check, but a groundedness score still
flags it as unsupported).

---

## (b) Brand/policy linting layers — Meta ad-policy pre-check practice

**Meta's own review architecture (2026):** two-layer — automated multimodal AI classifier first
(text + image + video + landing page + advertiser trust/history signals, in seconds), then human
review for borderline cases. [VERIFIED — auditsocials.com/blog/meta-ad-policy-updates-2026-guide,
consistent with get-ryze.ai/deepclick.com descriptions]

**Personal-attributes rule:** ads may not assert/imply knowledge of a user's race, religion,
sexual orientation, financial status, or health condition; second-person phrasing ("vous qui...",
"êtes-vous...", "les gens comme vous...") is the classic trigger. [VERIFIED — Meta's own Ad
Standards described consistently across auditsocials.com and Meta Transparency Center summaries]

**Before/after + implied-outcome claims:** before/after imagery for health/weight/cosmetic
outcomes remains banned, including implied-condition second-person language. Solar/ROI claims are
not health claims, but Meta's misleading-claims policy generalizes to unverifiable outcome/return
promises ("récupérez votre investissement garanti en X ans") — this is the same policy family
that would flag an unverified payback-period claim. [VERIFIED for the general policy shape;
application to solar-ROI phrasing specifically is my inference, not a directly cited case —
flag UNVERIFIED for the solar-specific trigger]

**Prohibited-superlatives framing:** absolutes like "garanti," "guéri," "instantané" are flagged;
Meta is described as increasingly requiring "neutral, educational" framing over promise/guarantee
language, even where such claims are industry-common. [UNVERIFIED-strength — sourced from
SEO/ad-agency blogs (auditsocials.com, gripasmarketing.com), not a direct Meta policy-page quote;
directionally consistent with Meta's known "no unrealistic outcome/earnings claims" stance but the
specific word list is vendor-compiled, not Meta's]

**Special Ad Category exposure — a genuine gap to check:** Meta's "Financial Products and
Services" Special Ad Category (introduced Jan 2025, replacing "Credit") now covers banking,
insurance, investment, and explicitly **BNPL/installment credit**. If TAQINOR ever advertises
solar **financing/paiement échelonné** (not just the panels themselves), that ad may fall under
this category, which forces: broad 18-65+ age targeting (no narrower), no gender/postal-code
targeting, no Lookalikes/Advantage+ expansion, and proof of regulatory authorization. Pure
"buy solar panels, pay cash/quote" ads should NOT trigger this, but any future financing message
would. [VERIFIED — Meta Transparency Center /policies/ad-standards/restricted-goods-services/
financial-services/, corroborated by data-axle.com and adamigo.ai; solar itself was NOT found
flagged as a restricted category anywhere in this research]

**Named pre-screening tools:** AdAmigo.ai runs a free "Meta Ad Policy Checker" plus an "AI
Compliance Audit" tool that scans copy against the personal-attributes/superlative rules and
suggests compliant rewrites before submission. [Existence VERIFIED via the vendor's own site;
efficacy/catch-rate claims are vendor-asserted and UNVERIFIED — treat as one example of the
pattern, not an endorsement]

**FR-language / Darija consideration:** no primary source was found describing Meta's ad-review
classifier behavior specifically in French or Moroccan Darija. What IS well documented
independently: Moroccan Darija is a genuinely low-resource NLP setting (no standard orthography,
heavy code-switching, Arabizi transliteration) where even purpose-built classifiers (a Darija
RoBERTa model) sit around 90% accuracy / 85% F1 and are vulnerable to simple adversarial tricks
(character insertion). [VERIFIED — arxiv 2409.17912 Atlas-Chat, mdpi.com robustness study]. The
decision-relevant inference: TAQINOR's ad **copy** is in French (a well-served language for
Meta's classifier), so policy-linting risk there is lower; the exposure is in **WhatsApp
conversation replies** if those ever drift into Darija/Arabizi and get automatically screened —
worth flagging as an open question rather than assuming Meta's classifier handles Darija as
reliably as French. [UNVERIFIED extrapolation — flagged as a finding to watch, not a confirmed risk]

---

## (c) Tiered-autonomy pattern in production — named precedents

**Content moderation (industry-standard three-zone routing):** confidence-score routing into
green (auto-action, no review), yellow (soft-flag → human or secondary-AI review), red (hard
escalate). Tier assignment weighs model confidence, harm severity, reach, account trust, and
appeal probability — a high-reach/high-severity/low-confidence item jumps the queue; a
low-reach/low-severity/high-confidence item is auto-actioned. Thresholds are **adaptive**: they
loosen automatically when queue depth exceeds a limit, to protect throughput without abandoning
the concept of a threshold. [VERIFIED as a widely and consistently described pattern —
checkstep.com, getstream.io, 123ofai.com; not a single named product but a converged industry
practice]

**Programmatic SEO auto-publish (closest structural analogue to "generate then publish"):** a
QA-scoring agent grades each generated page against a weighted multi-dimension quality bar; a
separate publishing-decision agent only auto-publishes pages that clear **all** thresholds, else
queues for human review or sends back for regeneration with specific fix instructions. The
human-review allocation precedent that's directly transferable: **100% human review for the
first ~3 batches of any new template/angle family**, plus 100% review for any high-stakes
category (YMYL/legal/brand-sensitive) forever, dropping to a **10-20% random sample** only once a
template family has a track record. [VERIFIED as a documented practitioner pattern —
venue.cloud/news/insights, webvy.co/blog; secondary/practitioner sources, not academic, but
internally consistent across independent write-ups]

**Email-marketing auto-send thresholds:** the clearest *quantified*, non-vendor-asserted
precedent found. Google's own 2026 bulk-sender guidelines enforce a **hard 0.10% spam-complaint-
rate ceiling** — consistently exceeding it gets ALL of a sender's mail routed to spam for Gmail
recipients, regardless of content quality. Separately, cold IPs/domains must "warm up" — gradual
ramp of sending volume to build reputation before full-volume auto-send is trusted. [VERIFIED —
Google's own bulk-sender policy as reported via Klaviyo's official help center; this is the
single most concrete, quantified auto-send governor found in this research]

**How thresholds get "earned" over time — synthesis, not directly sourced as one precedent:**
every case above shares the same shape: (1) a new template/sender/model starts at max scrutiny
(100% human review, IP warm-up, canary 1%), (2) it earns reduced scrutiny only after a
track record over N cycles with zero or near-zero violation rate, (3) autonomy is revoked
immediately and automatically the moment a hard metric (spam-complaint rate, error rate,
disapproval) crosses a line — it is never a one-way ratchet. [UNVERIFIED as a single named
precedent — this is my synthesis across (c) and (d)'s sourced examples]

---

## (d) Blast-radius limiters for auto-published ads — practical parameterization

**Software canary/progressive-rollout precedent (the general pattern ads should mirror):**
staged exposure 1% → 5% → 25% → 50% → 100% with automated metric analysis at each stage;
automatic rollback triggers on a hard metric threshold (illustrative industry figures: error
rate > 0.1–0.5%, or a latency/business-metric degradation > 20%) — feature flags act as an
instant kill switch, no redeploy needed. [VERIFIED as a standard, widely and consistently
documented DevOps pattern — configcat.com, oneuptime.com, harness.io]

**Meta's own learning-phase mechanics (the ad-specific equivalent of a canary window):**
Meta's algorithm needs a stated minimum of **~50 optimization events (conversions) within a
7-day window** to have "statistical signal" and exit the learning phase; before that, delivery
is unstable/exploratory by design. Practitioner guidance: give a new ad **24–48h minimum** before
any judgment, and **3–7 days** before treating performance as representative. [VERIFIED — this
"50/week" figure is Meta's own widely-cited threshold, corroborated independently across
multiple practitioner sources (leadenforce.com, pigeondigital.com), though I did not fetch Meta's
own help-center page directly in this pass]

**Calibration flag for TAQINOR specifically:** at ~$10/day and Morocco CPMs, TAQINOR will almost
never hit 50 conversions/week per ad set — meaning Meta's own "learning phase" framework is
largely **moot at this budget**; the Thompson bandit on WhatsApp-conversation rate is effectively
substituting a custom, low-volume-tolerant optimization loop for the one Meta's algorithm can't
reach. This matters when parameterizing blast-radius rules below — a 50-event gate would starve
the system; the test-budget/window has to be sized to TAQINOR's real volume, not Meta's own
defaults. [UNVERIFIED — this is a reasoned calibration inference, not a sourced number]

**Concrete practitioner rule parameters found (from a named automation-rules guide, AdAmigo.ai):**
- Test new campaigns at **$20–50 daily budget** for **at least one week** before scaling.
- Auto-pause example rule: cost-per-result above a set ceiling (e.g., "> $50") AND spend has
  already cleared a buffer of ~2–3× target CPA (their example: target CPA $25 → don't judge
  before $50–75 spent) — i.e., never pause purely on "zero conversions yet," always require a
  spend floor first so noise isn't mistaken for failure.
- Re-evaluate on a **24-hour cycle** for normal campaigns, shorter for high-spend ones.
[VERIFIED as one vendor's stated practitioner guidance — adamigo.ai/blog; treat the exact dollar
figures as illustrative industry norms, not a universal rule, and rescale to MAD/TAQINOR's budget]

**Meta's own automation surface — Ad Rules Engine (Marketing API):** a real, official capability
exists: rules with an `evaluation_spec` (trigger condition) and `execution_spec` (action, e.g.
pause) that fire automatically when an ad object's metadata or Insights data changes. This is the
correct API-level mechanism to implement auto-pause programmatically rather than polling and
reacting from TAQINOR's own code. [VERIFIED that the engine exists — developers.facebook.com
official docs — but this pass could not retrieve the exact enumerated trigger fields (e.g.
whether "disapproved" status or a hide-rate metric is a directly available trigger); that needs
a follow-up doc read of the linked `evaluation_spec`/`execution_spec` reference pages before
implementation]

**Explicit gap — the honest "nobody documents this" finding:** no source in this research
describes an out-of-the-box, Meta-provided **automatic pause-on-disapproval-rate-spike** or
**pause-on-hide-rate-spike** feature. Meta's disapproval handling is fundamentally manual/reactive
(you get exactly one appeal per disapproved ad, then must duplicate-with-changes and resubmit as
a new ad — there is no automatic remediation loop). **This means TAQINOR must build its own
disapproval/negative-feedback circuit breaker** (poll ad review-status + insights via the
Marketing API on a schedule; trigger the Ad Rules Engine or an internal scheduler to pause) —
this is not a solved problem elsewhere, it's homework. [VERIFIED as an absence — the "nobody does
this" finding is itself decision-relevant]

---

## (e) Rollback/audit story — what must be logged

**Logging granularity that production AI-agent audit practice converges on:** for every
inference — the prompt as the model actually saw it (post-templating), the raw response, and any
refusal/reject flag; for every tool-call/action — the authorization check, the exact parameters
passed, the result, and **the rollback path if one exists**. Without step-level detail, a bad
outcome can only be diagnosed by "starting from scratch"; with it, the exact point of divergence
is isolatable. [VERIFIED — consistently described across buildmvpfast.com, cyberhaven.com]

**Audit-trail architecture pattern:** treat the audit log as a thin, system-agnostic layer
sitting between the generation/publish pipeline and any governance tooling — emitters hook into
each pipeline stage (generation, claim-check, policy-lint, publish, Meta-status-poll) rather than
being bolted on after the fact. Framed in the literature as ideally **tamper-evident** (append-only/
hash-chained) for accountability. [VERIFIED — emergentmind.com/topics/llm-audit-trails,
consistent with general audit-log best-practice writing]

**Reversibility as a first-class operational primitive, not an afterthought:** the standard
framing is that "rollback must function as an operational primitive" — i.e., reverting a bad
auto-publish to a known-good state must be a designed, tested, one-command path, not an
improvised recovery. The event-sourced/log-as-source-of-truth pattern (replay the log to
reconstruct state deterministically) is the mechanism that makes this cheap: if publish decisions
are derived from a log rather than mutated state, "rollback" is just "stop replaying past point
X" plus an explicit compensating action (e.g., issue Meta's own pause call). [VERIFIED as a
described pattern — augmentcode.com, arxiv 2605.21997 event-sourced reactive graphs; the
event-sourcing framing is more common in general software architecture than ads-specific
literature, so treat the ads application as sound generalization rather than a directly-cited case]

**Concrete log schema for TAQINOR (synthesis, built from the above + our engine's actual
components):** per generated+published creative, log: (1) seed words / recombination slot IDs
used, (2) fact-table version/snapshot the generator was grounded against, (3) full rendered copy,
(4) per-claim claim-check result (which whitelist row matched, or reject reason), (5)
policy-linter result (pass, or which rule + phrase flagged), (6) human-reviewer decision +
timestamp if the tier routed it to a human, (7) Meta ad ID + full review-status history
(approved/disapproved/appealed, with timestamps), (8) spend/WhatsApp-conversation-rate snapshot
at each Ad-Rules-Engine evaluation, (9) bandit-arm ID so a bad creative's contribution to the
Thompson posterior can be excised, not just the ad paused. A "rollback" is then: pause the ad
via the Marketing API, zero out or discount its bandit-arm posterior, and flag its
template/recombination-slot combination as suspect so the recombination engine stops
re-generating variants from it until reviewed. [UNVERIFIED as a single sourced precedent — this
is our own design synthesis, built directly on the sourced logging/reversibility principles above
and TAQINOR's actual architecture]

---

## The concrete safety stack, ordered by implementation priority

1. **Grounded generation against a single fact table** (Anthropic Citations API or equivalent
   prompt-grounding) — prevention beats detection; this is the highest-leverage layer because it
   stops most numeric fabrication before it's generated at all. [VERIFIED mechanism, TAQINOR
   application is our synthesis]
2. **Hard numeric-claim whitelist match (regex+NER extraction → exact/tolerance match, zero
   soft-tier)** — catches anything that slips past grounding; this is the direct implementation of
   CLAUDE.md's checked-facts-only rule and should have near-100% catch rate for well-formed
   numeric claims since it's deterministic, not probabilistic. [VERIFIED pattern; zero-tolerance
   calibration is our synthesis, stricter than any sourced tool's default]
3. **Groundedness/NLI second net for non-numeric soft claims** (Guardrails `provenance-llm` /
   HHEM-style score) — catches paraphrased or qualitative unsupported claims the regex layer
   structurally cannot see. Literature reports these purpose-built scorers as materially cheaper
   and faster than LLM-as-judge, which is what makes running them on every creative viable at
   TAQINOR's low volume. [VERIFIED mechanism]
4. **Policy/brand linter pre-check** (banned-phrase list: superlatives, personal-attributes
   FR-phrasing patterns, before/after-style implied claims) run before any Meta submission — since
   Meta allows only one appeal per disapproved ad, a pre-check meaningfully protects both cycle
   time and account trust score. [VERIFIED that Meta's one-appeal constraint makes pre-screening
   valuable; specific banned-word list is vendor-sourced/UNVERIFIED-strength]
5. **Tiered autonomy gate, calibrated to TAQINOR's real cadence**: given only 12-17 test slots/year,
   effectively every new creative *is* a "new template family" in programmatic-SEO terms — so the
   honest calibration of the sourced "100%-review-for-first-3-batches" pattern is that most new
   angle/template combinations should default to founder review, with only exact re-runs of an
   already-approved template (facts swapped from the same whitelist) eligible for the lighter,
   auto-publish-but-still-PAUSED tier. [UNVERIFIED — our calibration, extrapolated from (c)'s
   sourced precedents]
6. **Blast-radius limiter at the Meta layer**: creative is born PAUSED (existing hard rule) →
   on activation, gets a small fixed test budget before joining the main bandit rotation,
   scaled down from the practitioner "$20-50/week" norm to TAQINOR's ~$10/day reality → minimum
   24-48h observation before any judgment, full week before being trusted → auto-pause rule via
   Meta's own Ad Rules Engine keyed to a spend-without-conversion cap and a CPA multiple, not to
   Meta's 50-events/week default (which TAQINOR's volume will rarely reach). [VERIFIED mechanisms;
   TAQINOR-scale numbers are our synthesis]
7. **Self-built disapproval/negative-feedback circuit breaker** — confirmed gap: Meta does not
   offer this automatically. Must poll ad status via the Marketing API on a schedule and
   auto-pause on disapproval or negative-signal spikes ourselves. [VERIFIED as an absence — a
   genuine "nobody does this for you" finding]
8. **Full audit/rollback logging** across every stage above (fact-table version, claim-check
   verdicts, linter verdicts, human decisions, Meta status history, bandit-arm attribution) so
   that a bad auto-publish is diagnosable and reversible — pause ad + discount its bandit arm +
   quarantine its template — within minutes rather than requiring investigation from scratch.
   [VERIFIED logging principles; TAQINOR-specific schema is our synthesis]

## Sources
- guardrailsai.com/hub, guardrailsai.com/docs/concepts/validators — Guardrails Hub validators
- icertglobal.com/community/hallucination-detection-in-rag-with-guardrails-ai — NLI entailment pattern
- vectara.com/blog/hhem-2-1-a-better-hallucination-detection-model — HHEM groundedness scorer
- bestaiweb.ai/patronus-lynx-vectara-hhem-and-bedrock-contextual-grounding... — Patronus Lynx / vendor comparison
- claude.com/blog/introducing-citations-api, platform.claude.com/docs/en/build-with-claude/citations — Anthropic Citations API
- arxiv.org/pdf/2606.28002 — hybrid regex+NER production entity-extraction pattern
- arxiv.org/pdf/2602.09516 — CLEF-2026 CheckThat! numeric/temporal claim fact-checking task
- auditsocials.com/blog/meta-ad-policy-updates-2026-guide, .../meta-ad-misleading-claims-personal-attributes... — Meta 2026 policy/personal-attributes/superlatives
- transparency.meta.com/policies/ad-standards/restricted-goods-services/financial-services/ — Meta Financial Products Special Ad Category (official)
- data-axle.com/resources/blog/meta-special-ad-categories-rules — Special Ad Category targeting restrictions
- adamigo.ai/free-tools/meta-ad-policy-checker, adamigo.ai/blog/ultimate-guide-to-automated-campaign-pausing-in-meta-ads — named pre-check tool + practitioner auto-pause rule examples
- developers.facebook.com/documentation/ads-commerce/marketing-api/ad-rules — Meta Ad Rules Engine (official, exact field enumeration not retrieved this pass)
- checkstep.com/blog/why-most-platforms-get-the-ai-human-moderation-balance-wrong, getstream.io/blog/automated-content-moderation, 123ofai.com/qnalab/system-design/blocks/human-in-loop — content-moderation tiered-autonomy pattern
- venue.cloud/news/insights/programmatic-seo-you-can-scale-without-spam, webvy.co/blog/claude-code-programmatic-seo-engine — programmatic SEO batch-review/sampling precedent
- help.klaviyo.com/hc/en-us/articles/115005247008, .../20413890435355 — email domain warm-up + Google 0.10% spam-rate threshold
- configcat.com/blog/how-to-implement-a-canary-release-with-feature-flags, oneuptime.com/blog/post/2026-01-30-canary-release-pattern — canary/progressive-rollout pattern
- leadenforce.com/blog/what-happens-inside-metas-optimization-engine-after-50-conversions, pigeondigital.com/insight/facebook-ads-learning-phase-50-conversions-rule-2026 — Meta 50-events/week learning-phase threshold
- buildmvpfast.com/blog/ai-agent-logging-audit-trail-debugging-compliance-2026, cyberhaven.com/blog/llm-access-controls-audit-logging — AI-agent audit-log granularity
- emergentmind.com/topics/llm-audit-trails, augmentcode.com/guides/multi-agent-outputs-n-pass-enterprise-audit, arxiv.org/pdf/2605.21997 — audit-trail architecture, reversibility, event-sourced replay
- arxiv.org/pdf/2409.17912 (Atlas-Chat), mdpi.com/2504-2289/8/12/170 — Moroccan Darija low-resource NLP / offensive-language-detection robustness
