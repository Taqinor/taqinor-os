# Taqinor OS — Build Plan & Progress (priority queue, PLAN2)

> **This queue is drained BEFORE `docs/PLAN.md`.** A run works every pending `[ ]` task here first, and only falls through to `docs/PLAN.md` once this file has none left.

This is the **priority queue**, worked **before** `docs/PLAN.md`. A run drains every `[ ]` task
in this file FIRST — the same way (verify it isn't already built, build it completely with
tests, obey every STANDING RULE in `PLAN.md`, then commit it to a worktree branch, tick it `[x]`,
and append a DONE LOG line as it lands; **run `python scripts/plan_lanes.py docs/PLAN2.md` to get
the maximally-parallel cross-category wave plan and build those lanes in parallel with concurrent
worktree subagents up to the session ceiling (default 8, raised as high as the session can sustain
via `--max-lanes`), continuously refilled (work-stealing), coupled tasks in sequence inside a
lane**) — and only
once this file has no pending `[ ]` task left does it fall through to `docs/PLAN.md`. Every
worktree branch is folded into one `dev`, CI runs once over the whole batch, and the run
self-merges `dev` → `main` exactly once at the very end — **no per-agent PR, no per-task merge**.
All the HOW TO RUN and STANDING RULES in `docs/PLAN.md` apply here unchanged — including the
default **workflow-with-review engine** (one worktree subagent per task plus a separate
adversarial review agent that must pass before a change is merge-eligible), the
**parallel-subagent fallback** when no workflow engine is available (never a single serial
one-task-at-a-time agent), and the **sync-safe single merge** (integrate the latest
`origin/main` first, re-run CI, push without forcing). This file only adds tasks.

> Added 2026-06-17 while the field-execution batch (PLAN.md F1–F24) was running on
> `dev-field-exec`. Per the founder's "add to plan" convention, new tasks go here while a
> run is in progress so `PLAN.md` is never touched mid-batch.

---

> **Web session note (2026-06-18):** a world-class audit of the public site (`apps/web`) was run and its
> fixes built — **W62–W66 shipped** (social proof scaffold, homepage guarantee band, founder photo-ready
> block, brand strip +Jinko/Huawei/Nexans, « réponse sous 48 h ») and the **W67 EN/AR i18n foundation**
> laid (Astro i18n + dictionary + switcher + RTL/hreflang, FR byte-identical). Full detail in
> `docs/WEB_PLAN.md` + `docs/DONE.md`; web work stays out of this OS queue per the OS/web split. Logged
> here at the founder's request — this note adds no OS task.

## BUILD QUEUE (do top-down — highest value first)

### TOP PRIORITY — build first (queued 2026-06-20)

- [x] G10 — Lead-source capture (G10 first half): (1) add nullable fields to the lead model — `fbclid`, `utm_source`, `utm_medium`, `utm_campaign`, `utm_content`, `utm_term` (additive / nullable migration, company FK forced server-side); (2) on the marketing-site contact form (`apps/web/`), capture `fbclid` + the UTM params from the landing URL, persist them across the session, submit them with the lead, and store them on the created lead. The Meta Conversions API SEND (G10 second half) STAYS GATED — pending Reda's Meta pixel access token; only the CAPI send remains after this ships. (Note: the apps/web portion crosses into web-plan territory but is intentionally bundled here per Reda's instruction.) [VERIFIED 2026-06-20: already fully built — Lead has fbclid/utm_* (crm migration 0006), the website webhook maps+stores them (`crm/webhooks.py:_map_payload_to_fields`), `apps/web` captures first-touch fbclid+UTM (`Layout.astro`, `lib/lead.ts`), covered by `crm/tests_webhook.py`.]

### Group Q — Devis ↔ Toiture 3D pipeline (backend; founder request 2026-06-21)

*Goal: weld the existing `roofPro11` 3D tool (in `apps/web`) and the premium quote
into ONE loop — client points at their roof → Meriem designs it → client receives a
premium web proposal and e-signs. The expensive engine already exists (3D optimizer,
PVGIS production via `/api/roof-production`, premium quote engine); Group Q adds only
the **backend persistence, storage and wiring**. The matching front-end tasks live in
`docs/WEB_PLAN.md` (W112–W118).*

> **CRITICAL UX RULE (applies to the whole pipeline).** The client does the bare
> minimum and NEVER sees panels auto-fill. The client is **not obliged to draw** — they
> just **point** at their roof (drop a pin / pick the building) and give their bill;
> **Meriem** draws the outline (if needed) and runs the auto-fill/optimizer later,
> privately — so the client believes TAQINOR drew the whole design for them. Backend
> therefore stores the client's *pin (+ optional rough outline)* (Q2) separately from
> the *finalized layout with panels* (Q1); only the finalized layout ever reaches the
> proposal.

> **Constraints.** All schema additive/nullable, seeded from current defaults; every
> viewset company-scoped server-side (never trust `company` from the body). The legacy
> `/proposal` PDF path stays byte-identical (rule #4): Group Q only *adds* a web
> channel the founder explicitly authorized; the quote document statuses
> (`brouillon→envoye→accepte…`) are preserved 1:1 (rule #4 status preservation).

- [ ] Q1 — **`Devis.roof_layout` storage + endpoints.** Add a nullable `roof_layout`
  JSONField to `Devis` (additive migration) holding the *finalized* serialized
  `AreaRecord[]` (roof vertices, obstacles, roofType, pitch, azimuth, the result
  `{panels,kwc,annualKwh,savings}`, and `renderPlan`). Add company-scoped DRF
  endpoints `POST /api/django/ventes/devis/<id>/layout/` (save — company forced in
  the serializer/`perform_create`, never from body) and `GET …/layout/` (load).
  **Done =** round-trip save/load test + a cross-tenant isolation test pass. Files:
  `apps/ventes/models.py` (+migration), `apps/ventes/views.py`/serializers, tests.

- [ ] Q2 — **Client roof-POINT capture on the Lead (pin, not drawing).** Add nullable
  `roof_point` (lat/lng of the building the client pinned) and `roof_outline` (OPTIONAL
  rough polygon, usually empty — the client need not draw) JSONFields to the CRM Lead,
  plus the bill kWh and a secure unguessable per-lead `token` (UUID) for the Meriem
  hand-off link. First VERIFY the W105–W111 contact-capture work (it may already carry
  part of this) and EXTEND rather than duplicate; wire the lead intake/webhook
  (`apps/crm/webhooks.py`) to accept + persist the pin (+ optional outline) with the
  lead. **Done =** the pin persists on the lead, token resolves the lead, company forced
  server-side; tests cover it. Files: `apps/crm/models.py` (+migration),
  `apps/crm/webhooks.py`/views, tests.

- [ ] Q3 — **`build_devis_from_layout()` service (server-side).** A service that turns a
  finalized layout (kWc, nb panneaux, production, chosen module/onduleur) into Devis
  lines from the seeded catalogue, reusing the SAME composition rules as the quote
  generator (`builder.py` réseau/injection/hybride/batterie/panneau keywords) and the
  reference-numbering util (`apps/ventes/utils/references.py`, never count()+1), with the
  client resolved via `apps/crm/services.resolve_client_for_lead`. Store the layout's
  production into `Devis.etude_params`. **Done =** a sample layout produces a coherent,
  company-scoped Devis with correct kWc/lines/totals and NEVER auto-quotes a price-less
  product (existing guard); tests cover residential réseau + hybride+batterie. Files:
  `apps/ventes/services.py`, `apps/crm/services.py`, tests.

- [ ] Q4 — **Roof-render image storage.** Accept the tool's 3D snapshot PNG (from W115)
  and store it in MinIO reusing the existing PDF bucket/`minio_client` infra, keyed +
  company-scoped, referenced from a nullable `Devis.roof_image` field (additive).
  Endpoint `POST /api/django/ventes/devis/<id>/roof-image/`. **Done =** upload + signed
  retrieval test + company-scoping test pass. Files: `apps/ventes/utils/` (minio),
  `apps/ventes/models.py` (+migration), views, tests.

- [ ] Q5 — **Feed roof render + layout figures into the quote data (additive/guarded).**
  Extend the quote-data builder so a quote CAN show the real roof render as the "votre
  installation" visual and use the layout's kWc/production/savings instead of estimating
  — **only when a layout/render is present**; with none present the existing PDF output
  stays byte-identical (back-compat, rule #4). **Done =** with-layout vs without-layout
  tests both pass and the no-layout render is unchanged. Files: `quote_engine/builder.py`
  (guarded), tests. *(Additive only — does not alter the legacy path.)*

- [ ] Q6 — **Tokenized web-proposal data endpoint.** A read-only
  `GET /api/django/ventes/proposal/<token>/` returning the quote data
  (`build_quote_data` output + roof-image signed URL + option totals) as JSON for the
  client web proposal (W116) to render — authenticated by the signed token, not a login,
  company-scoped, expired/invalid tokens rejected. **Done =** valid token returns the
  payload; invalid/expired rejected; no cross-tenant leakage; tests cover it. Files:
  `apps/ventes/views.py`/urls, token util, tests.

- [ ] Q7 — **E-signature acceptance (reuse the existing stamp).** A tokenized
  `POST /api/django/ventes/proposal/<token>/accept/` that records typed name + timestamp
  + IP into the existing acceptance fields (`accepte_par_nom`/`date_acceptation`, N26) and
  flips the Devis to `accepte` THROUGH the existing acceptance service so the document
  chain (bon-commande/facture) is preserved 1:1 (rule #4). **Done =** accept flips status
  + writes the stamp + is idempotent on double-submit; tests cover it. Files:
  `apps/ventes/services.py` (reuse the acceptance path), views, tests. *(A legal-grade
  eIDAS e-sign provider stays a separate GATED decision — v1 reuses the existing stamp.)*

### Group R — AI assistant: actions across the ERP (registry-driven; founder request 2026-06-21)

*Goal: extend the existing FastAPI assistant (today: read-only NL→SQL Q&A plus three
hard-coded action tools) into a registry-driven agent that can DO things across the whole ERP —
and any future feature — without hand-coding a new tool each time: create a quote, generate its
PDF, prepare the WhatsApp send, run the CRM funnel, invoice, record payments, and operate
stock/SAV/installations. The foundation (AG1–AG3) is built once and proven end-to-end with
quotes (AG4); the rest is mostly catalogue entries (AG5–AG9). Approved in the 2026-06-21
brainstorm with Reda.*

> **Safety model (applies to the whole group).** Every action still runs through the normal
> Django API with the logged-in user's JWT, so company-scoping + permissions are re-checked
> server-side; the agent never writes to the database directly and can only call endpoints that
> are in the catalogue (a whitelist), with inputs validated against the entry. Outward or
> irreversible actions (accept, invoice, record payment) never execute on their own — the agent
> returns a preview the user confirms first. WhatsApp "send" builds a `wa.me` link the user taps
> (the manual tap IS the confirmation); the existing `leads/<id>/whatsapp-devis/` endpoint
> already returns it. Schema changes stay additive/nullable; STAGES.py keys are imported, never
> hardcoded.

> **Gated future upgrade (NOT queued — prose only).** Automatic WhatsApp sending via a WhatsApp
> Business API provider (Meta Cloud API / Twilio) is a new paid dependency plus account setup,
> so it stays a founder decision; v1's `preparer_envoi_whatsapp` only builds the wa.me link to
> tap. A database-backed, admin-editable catalogue is likewise deferred — v1 declares actions in
> code, beside the app that owns them.

- [ ] AG1 — **Agent action-registry framework + catalogue endpoint.** Add a thin `apps/agent` app (no DB model — actions are declared in code) with an `AgentAction` descriptor (`key`, `label`, plain-language `description`, `inputs` json schema, target `endpoint` path-template + `method`, `required_permission`, `risk` ∈ internal/outward/irreversible, optional `confirm_summary`), a `register()` API, and a `for_user(user)` filter; expose `GET /api/django/agent/actions/` (DRF, authenticated, company- + permission-filtered) returning that catalogue, mounted in `erp_agentique/urls.py` and `erp_agentique/settings/` (INSTALLED_APPS). The catalogue is metadata only — execution keeps the existing pattern (FastAPI relays the user JWT to the named endpoint; Django re-checks permission + company). Founder-approved design (2026-06-21 brainstorm). **Done =** the endpoint returns only the actions the caller may run and a cross-tenant test shows no leakage. Files: `apps/agent/{apps,registry,views,urls}.py` (new), `erp_agentique/urls.py`, `erp_agentique/settings/`, tests. (ROUTINE) (@lane: apps/agent)
- [ ] AG2 — **Registry-driven agent tools + propose→confirm protocol (FastAPI).** Build the agent's tools dynamically from the Django catalogue (`GET /api/django/agent/actions/`) instead of the three hard-coded ones: each catalogue entry becomes a LangChain StructuredTool whose inputs/description come from the entry. Execute `internal` actions at once by relaying the user JWT to the entry's endpoint (extend the `_django_post` relay to support GET + path-templated urls); for `outward`/`irreversible` actions return a structured proposal `{action_key, inputs, human_preview}` and stash it signed in Redis (short TTL) instead of executing. Add `POST /api/django/fastapi/sql-agent/confirm` to run a stashed proposal by token after re-validating its inputs against the catalogue. The single-SELECT read security stays unchanged. **Done =** the three legacy actions work via the catalogue, an outward action returns a proposal, confirm runs it, and off-catalogue inputs are rejected; tests cover all three. Files: `backend/fastapi_ia/app/services/action_tools.py`, `app/services/sql_agent_service.py`, `app/api/endpoints/sql_agent.py`, `app/core/config.py`, tests. (ROUTINE) (@lane: backend/fastapi_ia) (@after: AG1, AG8, AG9)
- [ ] AG3 — **Confirmation + result cards in the assistant chat.** Render two new message types from the FastAPI responses: a confirmation card for proposals (human preview + Confirmer/Annuler — Confirmer calls `/sql-agent/confirm`, Annuler discards) and a result card for completed actions (reference number, a « Télécharger le devis » link to `/proposal`, and an « Ouvrir WhatsApp » button built from the `wa_url` of the send action). Reuse the existing Redux/axios plumbing and keep the current DOM/test hooks intact. **Done =** a proposal renders a working Confirmer/Annuler card and a completed action renders its result card with working PDF + WhatsApp links; tests cover both. Files: `frontend/src/pages/ia/AgentChat.jsx`, `frontend/src/features/ia/store/iaSlice.js`, `frontend/src/api/iaApi.js`, tests. (ROUTINE) (@lane: frontend/ia) (@after: AG2)
- [ ] AG4 — **Quote (devis) agent actions.** Declare in `apps/ventes/agent_actions.py` (registered via AG1 in `apps/ventes/apps.py` `ready()`): `creer_devis` (internal → `POST /api/django/ventes/devis/`, may carry `lead` so the client is resolved server-side), `generer_pdf_devis` (internal → `GET /api/django/ventes/devis/<id>/proposal/` with the whitelisted pdf options) and `accepter_devis` (outward → `POST …/accepter/`), each naming its permission (`IsResponsableOrAdmin`) + risk. No new endpoint — all three exist; this only describes them. WhatsApp send is provided by AG6's `preparer_envoi_whatsapp`. **Done =** the catalogue exposes the three quote actions to a responsable/admin and hides them from a read-only user, and a test creates a devis through the relayed call with company forced server-side. Files: `apps/ventes/agent_actions.py` (new), `apps/ventes/apps.py`, tests. (ROUTINE) (@lane: apps/ventes) (@after: AG1)
- [ ] AG5 — **Invoicing & payment agent actions.** Extend `apps/ventes/agent_actions.py`: `convertir_en_bon_commande` (outward → `POST …/convertir-en-bc/`), `generer_facture` (outward → `POST …/generer-facture/`) and `enregistrer_paiement` (irreversible). For payment, first verify a company-scoped payment-recording endpoint exists; if not, add a minimal one (`POST /api/django/ventes/factures/<id>/paiements/`, company forced server-side, amount validated) and declare it. Conversion/facture are outward and payment is irreversible, so all three require confirmation. **Done =** the three actions carry the right risk levels, recording a payment is confirm-gated and writes a company-scoped Paiement, and tests cover the payment path + cross-tenant isolation. Files: `apps/ventes/agent_actions.py`, `apps/ventes/views/`, `apps/ventes/urls.py` (only if the payment endpoint is missing), tests. (ROUTINE) (@lane: apps/ventes) (@after: AG4)
- [ ] AG6 — **CRM lead agent actions.** Declare in `apps/crm/agent_actions.py` (registered in `apps/crm/apps.py` `ready()`): `creer_lead` (internal → `POST /api/django/crm/leads/`), `mettre_a_jour_lead` (internal → `PATCH …/leads/<id>/`, used to advance the pipeline stage via `STAGES.py` keys — never hardcode — and to set a `relance` date), `noter_lead` (internal → `POST …/leads/<id>/noter/`, a chatter note/call log) and `preparer_envoi_whatsapp` (internal → `POST …/leads/<id>/whatsapp-devis/`, returns `{wa_url, message, links}` for the result card). **Done =** the catalogue exposes the lead actions, stage values come from `STAGES.py`, a note posts to the lead chatter through the relayed call with company scoping intact, and tests cover create + note + whatsapp-prep. Files: `apps/crm/agent_actions.py` (new), `apps/crm/apps.py`, tests. (ROUTINE) (@lane: apps/crm) (@after: AG1)
- [ ] AG7 — **Stock agent actions.** Declare in `apps/stock/agent_actions.py` (registered in `apps/stock/apps.py` `ready()`): `ajuster_stock` (internal → `POST /api/django/stock/mouvements/`) and `brouillon_commande_fournisseur` (internal → `POST /api/django/stock/bons-commande-fournisseur/`, a draft purchase order), each naming its permission + company scoping. **Done =** both actions are in the catalogue, a stock movement posts through the relayed call with company forced server-side, and tests cover it. Files: `apps/stock/agent_actions.py` (new), `apps/stock/apps.py`, tests. (ROUTINE) (@lane: apps/stock) (@after: AG1)
- [ ] AG8 — **SAV agent actions (migrate the existing ticket tool).** Declare in `apps/sav/agent_actions.py` (registered in `apps/sav/apps.py` `ready()`): `ouvrir_ticket_sav` (internal → `POST /api/django/sav/tickets/`, permission `sav_gerer`, client required, company forced server-side) — the registry replacement for the hard-coded FastAPI tool of the same name — plus `mettre_a_jour_ticket` (internal → `PATCH …/tickets/<id>/`). **Done =** the catalogue carries the two SAV actions and the open-ticket action reproduces today's behaviour through the relayed call; tests cover it. Files: `apps/sav/agent_actions.py` (new), `apps/sav/apps.py`, tests. (ROUTINE) (@lane: apps/sav) (@after: AG1)
- [ ] AG9 — **Installations agent actions (migrate the chantier/visite tools).** Declare in `apps/installations/agent_actions.py` (registered in `apps/installations/apps.py` `ready()`): `planifier_visite_maintenance` (internal → `POST /api/django/installations/interventions/`) and `brouillon_commande_chantier` (internal → `POST /api/django/installations/chantiers/<id>/commander-besoin/`) — the registry replacements for the two hard-coded FastAPI tools — each with its permission + company scoping. **Done =** the catalogue carries both actions reproducing today's behaviour through the relayed call; tests cover them. Files: `apps/installations/agent_actions.py` (new), `apps/installations/apps.py`, tests. (ROUTINE) (@lane: apps/installations) (@after: AG1)

> **Voice layer (AG10–AG12, founder request 2026-06-21).** Adds a hands-free voice
> conversation to the assistant — speak questions, hear answers, continuous loop.
> Speech→text uses Groq `whisper-large-v3` via the existing `GROQ_API_KEY` (no new paid
> service); text→speech uses the browser's built-in voices (free). Voice never bypasses the
> propose→confirm spine: outward/irreversible actions still require an explicit spoken
> « confirmer » or a tap before anything executes. (Distinct from Group S's self-hosted
> chat-memo transcription — this is the assistant's spoken conversation.)

- [ ] AG10 — **Voice transcription endpoint (Groq Whisper, reuses GROQ_API_KEY).** Add a FastAPI endpoint `POST /api/django/fastapi/sql-agent/transcribe` that accepts a short audio clip (multipart), sends it to Groq `whisper-large-v3` speech-to-text using the existing `GROQ_API_KEY` (no new paid service), and returns the transcript text (French/Arabic/Darija). Reuse the OCR safeguards (per-user rate limit, magic-byte + size validation, fail-closed) and accept the iOS Safari audio format (m4a/mp4) alongside webm/ogg; authenticated, no transcript persisted. **Done =** a sample clip returns its transcript, an oversize/invalid clip is rejected, and a missing key degrades gracefully with a clear message; tests cover it. Files: `backend/fastapi_ia/app/api/endpoints/voice.py` (new), `app/services/transcription_service.py` (new), `app/core/config.py`, `app/main.py`, tests. (ROUTINE) (@lane: backend/fastapi_ia) (@after: AG2)
- [ ] AG11 — **Voice input + spoken answers in the assistant chat.** Add a microphone control to the assistant chat: capture audio with `MediaRecorder`, send it to AG10's `/transcribe`, put the returned text through the existing question flow, and read the assistant's reply aloud with the browser's built-in speech synthesis (pick a French voice when available). Show clear recording/transcribing/speaking states and a stop control; reuse the existing Redux/axios plumbing and keep current DOM/test hooks intact. Outward/irreversible actions still surface the confirmation card and are NEVER auto-confirmed by voice. **Done =** speaking a question transcribes + sends it and the reply is read aloud, with visible states and a working stop, and an unsupported browser falls back to text; tests cover the happy path + the fallback. Files: `frontend/src/pages/ia/AgentChat.jsx`, `frontend/src/features/ia/voice/useVoiceChat.js` (new), `frontend/src/api/iaApi.js`, tests. (ROUTINE) (@lane: frontend/ia) (@after: AG3, AG10)
- [ ] AG12 — **Hands-free conversation mode (continuous listen↔speak loop).** On top of AG11, add a « Mode conversation » toggle running a continuous loop: listen → auto-detect end of speech (silence detection) → transcribe → answer aloud → re-open the mic, until the user stops it; with barge-in (talking interrupts the spoken reply) and an always-visible stop. The loop NEVER auto-confirms an outward/irreversible action — it reads the confirmation preview aloud and waits for an explicit spoken « confirmer » (or a tap) before executing. **Done =** a full spoken back-and-forth works without tapping, stop ends it at once, and a confirm-gated action waits for explicit confirmation; tests cover the loop state machine + the no-auto-confirm guard. Files: `frontend/src/pages/ia/AgentChat.jsx`, `frontend/src/features/ia/voice/useVoiceChat.js`, `frontend/src/features/ia/voice/conversationLoop.js` (new), tests. (ROUTINE) (@lane: frontend/ia) (@after: AG11)

### Group S — Internal team chat ("Discuss") (founder request 2026-06-21)

*Goal: a best-in-class INTERNAL team chat inside the ERP — staff message each other
1-to-1 (DMs) and in named channels, with file/image/voice attachments, @mentions,
reactions, pinned messages, message search, edit/delete, and the ERP superpower of
dropping a record (lead/devis/chantier) into a conversation as a rich clickable card.
New messages arrive by smart polling while a conversation is open and by the existing
Web Push (iPhone/Windows) when the app is backgrounded; per-conversation mute is
supported. Voice memos are transcribed (FR/Arabic/Darija best-effort) by a self-hosted
faster-whisper model in the FastAPI AI service, degrading gracefully when disabled.
Approved in the 2026-06-21 brainstorm with Reda. Full design in
`docs/superpowers/specs/2026-06-21-internal-team-chat-module-design.md`.*

> **Safety model (applies to the whole group).** Strict multi-tenant isolation: every
> model carries a `company` FK forced server-side (never from the body), and every viewset
> is company-scoped AND membership-checked (a user can only read/post in conversations they
> belong to — non-member 403, cross-tenant 404). All migrations additive/nullable. Cross-app
> reads (lead/devis/chantier labels for the share-a-record card) go through the target app's
> `selectors.py` — never importing its models/views (CI import contract). Attachments reuse
> `apps/records/storage.py` (MinIO, type-validated, 10 MB). Notifications reuse the existing
> `notify()` entry point + Web Push. STAGES.py is not involved.

> **Real-time stays polling for v1 (founder choice 2026-06-21).** No WebSocket/Channels in
> v1 — new messages arrive by short-polling the open conversation (~3 s) plus the existing
> Web Push when backgrounded. Typing indicators + live presence + instant delivery are
> deferred to the GATED **S21** WebSocket upgrade (brand-new ASGI/Channels infra), which a
> plan-run must NOT build until the founder provisions it.

> **One founder-approved backend dependency.** S10 adds `faster-whisper` (self-hosted,
> CPU-efficient, no paid service) + a lazily-downloaded model to the FastAPI AI service,
> behind a `CHAT_TRANSCRIPTION_ENABLED` flag so existing deploys are unaffected when off.
> This single dependency is pre-approved (2026-06-21 brainstorm); no other new dependency
> (backend or frontend npm) is authorized — the frontend reuses the existing Radix / lucide /
> sonner / @dnd-kit kit and the browser `MediaRecorder` for voice.

- [ ] S1 — **`apps/chat` app skeleton + core models.** New Django app `apps/chat` (registered in `erp_agentique/settings/` INSTALLED_APPS, mounted at `/api/django/chat/` in `erp_agentique/urls.py`). Models: `Conversation` (company FK, `kind` ∈ dm/channel via TextChoices, `name` for channels, `created_by`, `is_archived`, timestamps), `ConversationMember` (conversation FK, user FK, `role` ∈ member/admin, `last_read_at`, `is_muted`, `joined_at`, unique (conversation,user)), `Message` (conversation FK, `sender`, `body` text, `kind` ∈ text/voice/system/record via TextChoices, `reply_to` self-FK nullable, `created_at`, `edited_at` nullable, `deleted_at` nullable soft-delete, `pinned_at`/`pinned_by` nullable). Additive initial migration; Django admin registrations. **Done =** app installed, models migrate, a company-scoped Conversation + Message round-trip in a unit test. Files: `apps/chat/{__init__,apps,models,admin,urls}.py` (+migrations/0001), `erp_agentique/settings/base.py`, `erp_agentique/urls.py`, `apps/chat/tests/`. (ROUTINE) (@lane: apps/chat)
- [ ] S2 — **Attachment, reaction, mention & pin models.** Extend `apps/chat/models.py`: `MessageAttachment` (message FK, `file_key`/`filename`/`mime`/`size` mirroring `records.storage`, `kind` ∈ image/file/voice, voice fields `duration_s`, `transcript` text, `transcript_lang`, `transcript_status` ∈ pending/done/failed/disabled), `MessageReaction` (message FK, user FK, `emoji`, unique (message,user,emoji)), `MessageMention` (message FK, `mentioned_user` FK), and the generic record-link on Message for share-a-record (`shared_content_type`/`shared_object_id` nullable + `shared_label` snapshot text). Additive migration. **Done =** models migrate and attach to a Message in tests. Files: `apps/chat/models.py` (+migration), tests. (ROUTINE) (@lane: apps/chat) (@after: S1)
- [ ] S3 — **Serializers, viewsets, membership permissions & company scoping.** `apps/chat/serializers.py` + `views.py` + `urls.py`: company forced via `_CurrentCompanyDefault`/`perform_create`; an `IsConversationMember` permission; `ConversationViewSet` (list my conversations with last-message preview + unread count, create DM/channel, archive) and `MessageViewSet` (list a conversation's messages paginated newest-first, create/send, PATCH edit own, soft-delete own). All querysets filtered to `request.user.company` AND to conversations the user is a member of. **Done =** a member can list/post; a non-member is 403; cross-tenant access is 404; create forces company; tests cover all. Files: `apps/chat/{serializers,views,urls,permissions}.py`, tests. (ROUTINE) (@lane: apps/chat) (@after: S2)
- [ ] S4 — **Read-state & unread counts.** Endpoints to mark a conversation read (advance `ConversationMember.last_read_at`) and to return per-conversation + total unread counts for the header badge. **Done =** marking read zeroes that conversation's unread; the total reflects all conversations; tested. Files: `apps/chat/{views,serializers,services}.py`, `urls.py`, tests. (ROUTINE) (@lane: apps/chat) (@after: S3)
- [ ] S5 — **Message search.** A company- + membership-scoped search endpoint (Postgres `icontains`/trigram over message bodies and voice transcripts in the caller's conversations) returning matches with conversation + snippet. **Done =** search finds a seeded message only within the caller's conversations, never cross-tenant; tested. Files: `apps/chat/{views,selectors}.py`, `urls.py`, tests. (ROUTINE) (@lane: apps/chat) (@after: S3)
- [ ] S6 — **Attachment & voice-memo upload.** Upload endpoint(s) that store an image/file/voice attachment via `apps/records/storage.store_attachment` (type-validated, 10 MB) and link a `MessageAttachment`, plus a proxy/signed retrieval endpoint to serve it (reuse the records fetch/presign pattern). Voice uploads set `kind=voice`, `transcript_status=pending` (or `disabled` when transcription is off). **Done =** upload returns a playable/downloadable attachment, company-scoped, rejects bad types/oversize; tested. Files: `apps/chat/{views,serializers,services}.py`, `urls.py`, tests. (ROUTINE) (@lane: apps/chat) (@after: S3)
- [ ] S7 — **Reactions & pinned messages.** Endpoints to add/remove an emoji reaction (toggle, unique per user+emoji) and to pin/unpin a message (member-can-pin for v1; record `pinned_by`/`pinned_at`), plus a list-pinned endpoint. **Done =** toggling a reaction and pin/unpin work, are company+membership scoped and idempotent; tested. Files: `apps/chat/{views,serializers}.py`, `urls.py`, tests. (ROUTINE) (@lane: apps/chat) (@after: S3)
- [ ] S8 — **Share an ERP record into a conversation.** A send path that attaches a lead/devis/chantier to a message (sets the generic record link + a `shared_label` snapshot resolved through the target app's `selectors.py` — e.g. a thin `crm.selectors.lead_card(id, company)` / `ventes.selectors.devis_card(...)` / `installations.selectors.chantier_card(...)` returning `{label, subtitle, url}` — never importing their models). **Done =** sharing a company-scoped devis stores its card snapshot + link and renders read-only to members; a foreign-company record is rejected; tested. Files: `apps/chat/{views,services}.py`, `apps/crm/selectors.py`, `apps/ventes/selectors.py`, `apps/installations/selectors.py`, tests. (ROUTINE) (@lane: apps/chat) (@after: S3)
- [ ] S9 — **Notifications + per-conversation mute (reuse `notify()` + Web Push).** Add `CHAT_MESSAGE` and `CHAT_MENTION` to the notifications `EventType`; on a new message, call `notify()` for every other member whose membership is not muted (a louder `CHAT_MENTION` for @mentioned users via `MessageMention`), with a deep-link to the conversation so the existing service-worker push opens it. Respects existing per-user notification preferences. **Done =** posting a message notifies non-muted members (in-app + push when subscribed), muting suppresses it, an @mention fires `CHAT_MENTION`; tested with the push dispatch stubbed. Files: `apps/notifications/models.py` (EventType), `apps/chat/{services,signals,apps}.py`, tests. (ROUTINE) (@lane: apps/chat) (@after: S3, S8)
- [ ] S10 — **Self-hosted Whisper transcription endpoint (FastAPI).** Add `POST /transcribe` to the FastAPI AI service running `faster-whisper` (founder-approved dependency; small/medium multilingual model, language auto-detect with a FR/AR/Darija hint) over an uploaded audio blob, returning `{text, language}`. Behind a `CHAT_TRANSCRIPTION_ENABLED` setting + lazy model load/download-cache so the service starts (and CI builds) fine when disabled — the model is fetched on first use, never at image build. **Done =** with the flag on, a sample clip returns a transcript; with it off, the endpoint reports disabled; a unit test mocks the model so no real weights are needed in CI. Files: `backend/fastapi_ia/app/api/endpoints/`, `backend/fastapi_ia/app/services/transcription_service.py` (new), `backend/fastapi_ia/app/core/config.py`, `backend/fastapi_ia/requirements*`, tests. (ROUTINE — founder-approved faster-whisper dep) (@lane: backend/fastapi_ia)
- [ ] S11 — **Django voice-transcription pipeline.** On a voice-memo upload (S6), enqueue a Celery task that pulls the audio from MinIO, calls the FastAPI `/transcribe`, and writes `transcript`/`transcript_lang`/`transcript_status=done` (or `failed`) back on the `MessageAttachment`; the frontend polls and shows it. No-op (`transcript_status=disabled`) when transcription is off — voice memos always work. **Done =** with transcription stubbed, a voice upload ends with a stored transcript; with it off, status is `disabled` and the memo still plays; tested. Files: `apps/chat/tasks.py` (new), `apps/chat/{services,signals}.py`, `erp_agentique/celery.py` (register), tests. (ROUTINE) (@lane: apps/chat) (@after: S6, S10)
- [ ] S12 — **Chat API client + Redux slice + smart-polling hook.** `frontend/src/api/messagesApi.js` (conversations, messages, send, mark-read, unread-count, search, reactions, pin, upload, share-record), a `features/messaging/store/messagingSlice.js`, and a `useChatPolling` hook (short-poll the open conversation ~3 s, slower poll for the list + unread badge, paused when the tab is hidden via `visibilitychange`). **Done =** slice + api unit tests pass; polling pauses on `visibilitychange`. Files: `frontend/src/api/messagesApi.js`, `frontend/src/features/messaging/store/messagingSlice.js`, `frontend/src/features/messaging/useChatPolling.js`, tests. (ROUTINE) (@lane: frontend/messaging) (@after: S3)
- [ ] S13 — **`/messages` route, nav entry, header chat icon + two-pane shell.** Lazy `/messages` route (`pages/messaging/ChatPage.jsx`) wrapped in the app layout; a "Messages" sidebar entry; a header chat icon with a total-unread badge (mirroring `NotificationBell`) that links to `/messages` and is the push deep-link target. Two-pane responsive shell (list | thread; single-pane drill-down on mobile). **Done =** route renders, nav + header badge show unread, mobile collapses to one pane; tests. Files: `frontend/src/pages/messaging/ChatPage.jsx`, `frontend/src/router/index.jsx`, `frontend/src/components/layout/{Sidebar,Header}.jsx`, `frontend/src/components/layout/ChatBell.jsx` (new), tests. (ROUTINE) (@lane: frontend/messaging) (@after: S12)
- [ ] S14 — **Conversation list pane.** Left pane: DMs + channels with avatar/last-message/timestamp/unread badge, a search box, a mute indicator, and a "+" to start a DM or create a channel. Built from `@/ui` (Avatar, Input, Badge) — no new dep. **Done =** list renders, unread badges + search work, "+" opens the create flow; tests. Files: `frontend/src/features/messaging/ConversationList.jsx`, tests. (ROUTINE) (@lane: frontend/messaging) (@after: S13)
- [ ] S15 — **Message thread pane.** Right pane: message bubbles (sender avatar/name/time, own vs others), attachment/voice/record-card render slots, reverse-infinite-scroll to load older, auto-scroll to newest on send/arrival, a pinned-messages bar, and read state. **Done =** thread renders, loads older on scroll-up, auto-scrolls on new, pinned bar shows; tests. Files: `frontend/src/features/messaging/MessageThread.jsx`, `frontend/src/features/messaging/MessageBubble.jsx`, tests. (ROUTINE) (@lane: frontend/messaging) (@after: S13)
- [ ] S16 — **Composer: text, @mentions, attachments, edit/delete.** Bottom composer: autosizing text input, @mention autocomplete (company members, inserts a `MessageMention`), attach button (image/file via the existing `FileUpload`), send; inline edit + delete for own messages with an `AlertDialog` confirm. **Done =** typing `@` shows a member picker, attaching + sending works, edit/delete of an own message works; tests. Files: `frontend/src/features/messaging/Composer.jsx`, `frontend/src/features/messaging/MentionAutocomplete.jsx`, tests. (ROUTINE) (@lane: frontend/messaging) (@after: S15)
- [ ] S17 — **Voice memos: record, play, transcript.** A record button using the browser `MediaRecorder` (no new dep) to capture a short clip, upload it as a voice attachment, an audio player in the bubble, and a transcript line that fills in when S11 completes (shows "Transcription…" while pending, hidden when disabled). **Done =** record→send→play works; the transcript appears when available and is absent-but-non-breaking when off; tests with `MediaRecorder` mocked. Files: `frontend/src/features/messaging/VoiceRecorder.jsx`, `frontend/src/features/messaging/VoiceMessage.jsx`, tests. (ROUTINE) (@lane: frontend/messaging) (@after: S16, S11)
- [ ] S18 — **Reactions & pinned UI.** An emoji-reaction control (a small curated emoji set — 👍 ❤️ 😂 🎉 ✅ — no picker library) + reaction chips under a bubble (toggle), and pin/unpin from a message menu feeding the pinned bar. Built from `@/ui` Popover/DropdownMenu. **Done =** reacting toggles a chip, pinning updates the bar; tests. Files: `frontend/src/features/messaging/Reactions.jsx`, `frontend/src/features/messaging/MessageBubble.jsx`, tests. (ROUTINE) (@lane: frontend/messaging) (@after: S15, S7)
- [ ] S19 — **Share-a-record UI.** A "share record" action in the composer opening a picker (lead/devis/chantier, reusing existing search) that sends a message rendering as a clickable card (label/subtitle → opens the record). **Done =** sharing a devis posts a card that navigates to it; tests. Files: `frontend/src/features/messaging/ShareRecord.jsx`, `frontend/src/features/messaging/RecordCard.jsx`, tests. (ROUTINE) (@lane: frontend/messaging) (@after: S15, S8)
- [ ] S20 — **New-DM / new-channel / manage-members modals.** Dialog/Sheet flows to start a DM, create a named channel and add members, and (as channel admin) rename / add / remove members + leave. Built from `@/ui` Dialog/Sheet/MultiSelect. **Done =** creating a channel with members works, an admin can manage membership, a member can leave; tests. Files: `frontend/src/features/messaging/NewConversation.jsx`, `frontend/src/features/messaging/ManageMembers.jsx`, tests. (ROUTINE) (@lane: frontend/messaging) (@after: S14)
- [ ] S21 — **[GATED] Real-time WebSocket upgrade (Django Channels).** Instant message delivery, typing indicators and live presence via Django Channels + a Redis channel layer + an ASGI server (daphne/uvicorn) + an nginx WebSocket proxy, authenticated with the same JWT. STOP-AND-ASK: brand-new architecture/infra the founder must provision; a plan-run must NOT build it until then — it replaces polling transparently when it lands. Files: `erp_agentique/asgi.py`, `apps/chat/consumers.py` (new), settings (`CHANNEL_LAYERS`), nginx config, frontend socket client. (ARCH) (@lane: realtime)

# Taqinor OS — UI/UX overhaul ("prettier than Odoo")

*Goal: a calm, premium, data-first ERP — Linear/Stripe-tier polish, brand-matched to Taqinor, denser and cleaner than Odoo. Built on the existing React 19 + Vite + Tailwind 4 + recharts stack. Positioned ahead of Groups A–D so feature work inherits the new design language. Constraints: do NOT touch the devis/facture PDF templates, the public PDF pages, or the PdfCanvas PDF content (client-facing, gated separately); do NOT touch the apps/web marketing site; STAGES.py stays a fixed CI contract; schema changes additive/nullable only, every new value seeded from current in-code defaults.*

> **Renumbered on intake (2026-06-18):** the source proposal lettered these groups E–O, but `docs/PLAN2.md` already has a **Group E** (the E2E browser-test suite, tasks E1–E16). To keep every group/task id unique, the UI/UX-overhaul groups were shifted one letter to **F–P** (and their task ids re-prefixed to match) before being inserted here. Titles, content, and the running task numbers (14–69) are otherwise verbatim.

> **World-class look-and-feel wave (queued 2026-06-21, founder request "best-looking ERP in the world").**
> The design *foundation* already shipped (tokens.css, ~45 `src/ui` primitives, the hand-rolled
> `DataTable`, the app shell with sidebar/global-search/breadcrumbs/bottom-tab-bar) — so this wave is
> **adoption + refinement to Linear/Stripe/Vercel tier**, grounded in a fresh world-class audit (OKLCH
> tokens, premium tables, ⌘K command palette, restrained charts, tasteful motion, mobile/PWA polish,
> WCAG 2.2 AA). Tasks **F120–P171** fill the previously-empty Group F–P headers (the original 14–69
> series shipped/archived in `docs/DONE.md`; these continue the running number at 120 to stay unique).
> Hard constraints (unchanged): NEVER touch the devis/facture PDF templates, the public PDF pages, the
> `PdfCanvas` content, or the `apps/web` marketing site; import stage names from `STAGES.py` (never
> hardcode); schema changes additive/nullable seeded from current defaults; **no new npm dependency**
> (build on the already-installed Radix / recharts / @tanstack/react-table / @dnd-kit / sonner / lucide
> — anything else is gated). New user-facing text in French.

## Group F — Design foundation & tokens

- [ ] F120 — **Palette de marque en OKLCH (sans régression visuelle).** Re-exprimer les primitives (`brass`, `nuit/encre`, `azur`, `lune`) de `tokens.css` en rampes OKLCH 12 paliers (perceptuellement uniformes, comme la palette Tailwind v4) en conservant chaque couleur rendue aujourd'hui à ΔE quasi nul, pour que tous les écrans existants restent identiques. **Done =** `tokens.css` utilise `oklch()` pour les rampes de marque, la couche sémantique rend les mêmes couleurs, `theme.test.mjs` passe, aucun changement perceptible sur `/ui`. Files: `frontend/src/design/tokens.css`, `frontend/src/design/theme.test.mjs`. (ROUTINE) (@lane: frontend/design)
- [ ] F121 — **Échelle typographique + chiffres tabulaires généralisés.** Ajouter une échelle d'en-têtes documentée (display/h1/h2/h3/body/small/caption : tailles, interlignes, `letter-spacing` négatif croissant) en tokens/utilitaires, et câbler `tabular-nums` + zéro barré (`font-feature-settings`) sur tout contexte monétaire/quantité/référence. **Done =** une échelle `--text-*` existe et est appliquée aux titres, chiffres de tableaux/KPI/totaux tabulaires, test des utilitaires de format vert. Files: `frontend/src/design/tokens.css`, `frontend/src/design/theme.js`. (ROUTINE) (@lane: frontend/design)
- [ ] F122 — **Discipline d'élévation + anneau de focus de marque.** Codifier en tokens quelle ombre/bordure chaque surface utilise (carte = bordure 1px ou « shadow-ring » ; menu/modal/toast = ombre douce multi-couches teintée nuit) et un token d'anneau de focus ≥2px contrasté ≥3:1. **Done =** tokens d'élévation nommés + `--ring` conforme, documentés dans `/ui`. Files: `frontend/src/design/tokens.css`. (ROUTINE) (@lane: frontend/design)
- [ ] F123 — **Mode sombre = élévation par la clarté.** En `.dark`, exprimer la profondeur par la clarté des surfaces (base → carte → popover de plus en plus claires, ~+3–4 pts L par niveau), bannir le noir pur (base ≈ navy très sombre), désaturer l'accent brass ~20–30 %, relever les bordures, et garantir le contraste AA. **Done =** hiérarchie sombre fondée sur la clarté (pas que l'ombre), aucun `#000`, accent lisible non criard. Files: `frontend/src/design/tokens.css`. (ROUTINE) (@lane: frontend/design)

## Group G — Primitive component library (shadcn-based; one "definition of done" per component: states, dark mode, keyboard, ARIA)

- [ ] G124 — **Tooltip thémable.** `Tooltip.jsx` code en dur `bg-nuit` (donc sombre dans les deux thèmes) ; le tokeniser en `popover`/`popover-foreground`, harmoniser délai d'ouverture et flèche. **Done =** tooltip qui s'adapte clair/sombre + test de rendu. Files: `frontend/src/ui/Tooltip.jsx`. (ROUTINE) (@lane: frontend/ui)
- [ ] G125 — **Bouton « six états » + libellés d'icônes.** Garantir default/hover/focus-visible/active/disabled/loading complets et pilotés par tokens sur `Button.jsx` + `IconButton.jsx`, avec un press `active:scale-[0.97]` ~150 ms `cubic-bezier(0.23,1,0.32,1)` réservé via `@media (hover:hover)`, et un `aria-label` obligatoire sur tout bouton à icône seule. **Done =** chaque état présent et testé, press tactile non déclenché par le survol émulé mobile, boutons-icônes étiquetés. Files: `frontend/src/ui/Button.jsx`, `frontend/src/ui/IconButton.jsx`. (ROUTINE) (@lane: frontend/ui)
- [ ] G126 — **États de chargement/erreur des sélecteurs.** `Select` affiche un état chargement (spinner/skeleton) pendant une recherche asynchrone ; `Combobox`/`MultiSelect` affichent une ligne d'erreur explicite (au lieu d'un silence « Aucun résultat »). **Done =** chargement et erreur visibles + tests. Files: `frontend/src/ui/Select.jsx`, `frontend/src/ui/Combobox.jsx`, `frontend/src/ui/MultiSelect.jsx`. (ROUTINE) (@lane: frontend/ui)
- [ ] G127 — **Champ de formulaire : indice + erreur ensemble.** `FormField` masque l'indice dès qu'il y a une erreur ; les afficher ensemble, distinguer « requis » vs « format », et réserver l'espace bas pour les `FormActions` collantes sur mobile. **Done =** indice et erreur coexistent, deux styles d'erreur, pas de chevauchement mobile, tests. Files: `frontend/src/ui/Form.jsx`. (ROUTINE) (@lane: frontend/ui)
- [ ] G128 — **Tokeniser DatePicker / TimePicker / Calendar.** Ces composants utilisent des couleurs/styles inline en dur ; les passer aux tokens (clair/sombre) et aligner les hauteurs sur les tokens de densité. **Done =** rendu correct dans les deux thèmes + densités, tests. Files: `frontend/src/ui/DatePicker.jsx`, `frontend/src/ui/TimePicker.jsx`. (ROUTINE) (@lane: frontend/ui)

## Group H — DataTable engine (TanStack Table, behind every list view)

- [ ] H129 — **Passe visuelle « tableau premium ».** Dans `DataTable` : chiffres tabulaires + alignés à droite sur colonnes numériques, suppression du zébrage, séparateur horizontal 1px très clair (aucune bordure verticale), survol de ligne discret (~3–5 %), en-tête collant, hauteurs de ligne par densité (compact 32 / confort 40 / spacieux 48). **Done =** rendu par défaut conforme + tests. Files: `frontend/src/ui/datatable/DataTable.jsx`, `frontend/src/ui/datatable/datatable.test.mjs`. (ROUTINE) (@lane: frontend/datatable)
- [ ] H130 — **Épinglage de colonnes.** Épingler la colonne entité à gauche et la colonne actions à droite, avec une ombre de bord apparaissant au scroll, persistée par utilisateur dans le bundle de vue sauvegardée existant. **Done =** colonnes épinglées + persistance + tests. Files: `frontend/src/ui/datatable/DataTable.jsx`, `frontend/src/ui/datatable/logic.js`. (ROUTINE) (@lane: frontend/datatable)
- [ ] H131 — **Affordances de ligne.** Actions rapides révélées au survol (`opacity-0 group-hover`) + menu kebab persistant (Radix DropdownMenu), sélection par plage au Shift-clic, et palette d'actions contextuelles ⌘K sur la ligne focalisée. **Done =** ces trois comportements + tests. Files: `frontend/src/ui/datatable/DataTable.jsx`. (ROUTINE) (@lane: frontend/datatable)
- [ ] H132 — **Barre d'actions groupées flottante.** Dès ≥1 ligne sélectionnée, une barre glisse en bas-centre (fixe, persistante au scroll) : « {n} sélectionné(s) », actions, débordement « Plus », « Tout désélectionner ». **Done =** barre live + transition + tests. Files: `frontend/src/ui/datatable/BulkActionBar.jsx`, `frontend/src/ui/datatable/DataTable.jsx`. (ROUTINE) (@lane: frontend/datatable)
- [ ] H133 — **Performance perçue des tableaux.** Lignes-squelettes calquées sur la disposition réelle au chargement (rien sous 300 ms), préchargement des données de la ligne au survol/intention, jamais squelette + spinner simultanés. **Done =** squelettes + préchargement + tests. Files: `frontend/src/ui/datatable/DataTable.jsx`. (ROUTINE) (@lane: frontend/datatable)

## Group I — App shell & navigation

- [ ] I134 — **Palette de commandes ⌘K de premier plan (sans nouvelle dépendance).** Étendre `GlobalSearch` (Radix Dialog existant) en vraie palette : mode « Aller à » (navigation) + « Actions », résultats groupés par entité (Clients/Leads/Devis/Produits/Chantiers/SAV), éléments récents quand vide, navigation clavier, puce de raccourci par ligne. **Done =** ⌘K ouvre la palette, recherche + actions + récents OK, tests. Files: `frontend/src/components/layout/GlobalSearch.jsx`, `frontend/src/components/layout/commandPalette.js` (nouveau). (ROUTINE) (@lane: frontend/shell)
- [ ] I135 — **Sidebar « calme ».** Item actif = pastille discrète teintée (neutre/brass) et non le bleu vif `#1d4ed8` ; libellés inactifs en muted ; séparateurs de section ; anneau focus-visible sur les items (absent aujourd'hui) ; `aria-current="page"`. **Done =** sidebar conforme au standard « quiet », focus clavier visible, tests menu. Files: `frontend/src/components/layout/Sidebar.jsx`, `frontend/src/index.css`. (ROUTINE) (@lane: frontend/css)
- [ ] I136 — **Polissage de l'en-tête.** Repère de marque/logo cliquable, affordance ⌘K renforcée (pastille avec touche `kbd`), hiérarchie de titre resserrée, en-tête collant compact. **Done =** en-tête de marque + ⌘K visible + hiérarchie nette. Files: `frontend/src/components/layout/Header.jsx`, `frontend/src/index.css`. (ROUTINE) (@lane: frontend/css)
- [ ] I137 — **Fil d'Ariane accessible + tronqué.** Envelopper dans `nav[aria-label]`, `aria-current="page"` sur le dernier (non lié), tronquer au milieu les chemins longs vers un débordement « … » et afficher l'intitulé complet en tooltip. **Done =** structure ARIA + troncature + tests. Files: `frontend/src/components/layout/Breadcrumbs.jsx`, `frontend/src/index.css`. (ROUTINE) (@lane: frontend/css)
- [ ] I138 — **Culture des raccourcis clavier.** `?` ouvre une aide-mémoire des raccourcis groupés ; séquences `g`-préfixe (g c CRM, g d Devis, g s Stock, g i Installations, g v SAV, g r Reporting), `j/k` pour parcourir les listes, puces de raccourci dans la palette. **Done =** overlay `?` + séquences + tests. Files: `frontend/src/components/layout/ShortcutsHelp.jsx` (nouveau), `frontend/src/hooks/useShortcuts.js` (nouveau). (ROUTINE) (@lane: frontend/shell)

## Group J — Per-module restyle (each: list → DataTable, forms → new primitives, modals → Dialog/Sheet, statuses → StatusPill, real empty/loading/error states, mobile pass)

- [ ] J139 — **CRM Clients : refonte.** Liste → `DataTable` unifié, `StatusPill` partout, états réels vide/chargement/erreur/squelette, édition en `Sheet` sur mobile, remplacer `window.confirm` par `AlertDialog` + toast. **Done =** écran conforme + tests. Files: `frontend/src/pages/crm/ClientList.jsx`, `frontend/src/pages/crm/ClientForm.jsx`. (ROUTINE) (@lane: frontend/crm)
- [ ] J140 — **CRM Leads : tokens de couleur + vues + STAGES.** Remplacer les palettes `#hex` en dur des vues (Liste/Kanban/Calendrier/Charts) par des tokens, les pastilles d'étape par `StatusPill`/`statusTone`, grouper par les clés `STAGES.py` (jamais en dur), et ajouter une alternative sans glisser au kanban. **Done =** zéro couleur d'étape en dur, regroupement par STAGES, alternative clavier, tests. Files: `frontend/src/pages/crm/leads/`. (ROUTINE) (@lane: frontend/crm)
- [ ] J141 — **Ventes Devis : polissage liste/détail.** Chaîne de statut via `StatusPill`, éditeur de lignes en densité tableau + chiffres tabulaires, primitives cohérentes, squelettes. NE PAS toucher au PDF / `PdfCanvas` / pages publiques (règle #4). **Done =** liste/détail cohérents + tests, PDF intact. Files: `frontend/src/pages/ventes/`. (ROUTINE) (@lane: frontend/ventes)
- [ ] J142 — **Stock : refonte.** Catalogue → `DataTable` (virtualisation des grandes listes via le moteur existant), édition de cellule au contrat clavier, états vide/chargement, cartes mobiles. **Done =** écran conforme + tests. Files: `frontend/src/pages/stock/`. (ROUTINE) (@lane: frontend/stock)
- [ ] J143 — **Installations (chantiers) : refonte.** Kanban + détail aux primitives cohérentes, `StatusPill`, squelettes, passe mobile. **Done =** écrans conformes + tests. Files: `frontend/src/pages/installations/`. (ROUTINE) (@lane: frontend/installations)
- [ ] J144 — **SAV : refonte.** Tickets → `DataTable` + `StatusPill`, états vide/chargement, passe mobile. **Done =** écrans conformes + tests. Files: `frontend/src/pages/sav/`. (ROUTINE) (@lane: frontend/sav)
- [ ] J145 — **Admin Utilisateurs → DataTable.** `UsersManagement.jsx` utilise une grille de cartes ; migrer vers `DataTable` (cellule avatar, pastilles de rôle, actions groupées) et édition en `Sheet` cohérente. **Done =** liste en DataTable + tests. Files: `frontend/src/pages/admin/UsersManagement.jsx`. (ROUTINE) (@lane: frontend/admin)
- [ ] J146 — **Reporting/Journal : tableaux HTML hérités → DataTable.** Remplacer les `.data-table` HTML (Reporting, Journal) par `DataTable`/un primitif `Table` partagé, et les barres de conversion par le composant `Progress`. **Done =** plus de table HTML héritée dans ces pages + tests. Files: `frontend/src/pages/reporting/`, `frontend/src/pages/Reporting.jsx`. (ROUTINE) (@lane: frontend/reporting)

## Group K — Dashboard & reporting

- [ ] K147 — **Kit de primitives graphiques (recharts, marque).** Créer un petit ensemble `src/ui/charts` (AreaSansAxe, BarArrondie, KpiSpark, ChartTooltip, ChartEmpty) stylé marque : pas de lignes d'axe/ticks, dégradé de remplissage (`<linearGradient>` opacité ~0.3→0), `strokeWidth=2`, barres arrondies `radius=[4,4,0,0]`, courbe `monotone`, tooltip tokenisé, `animationDuration≈600` ease-out respectant `prefers-reduced-motion`. **Done =** kit réutilisable + tests. Files: `frontend/src/ui/charts/` (nouveau). (ROUTINE) (@lane: frontend/reporting)
- [ ] K148 — **Dashboard : refonte avec le kit.** Cartes KPI Libellé→Valeur→Δ→Période + sparkline, `signDisplay:"exceptZero"`, delta indiqué par flèche + signe + couleur (jamais la couleur seule), graphiques animés, états vides en contexte, squelettes de graphes. **Done =** dashboard refait sur le kit + tests. Files: `frontend/src/pages/Dashboard.jsx`. (ROUTINE) (@lane: frontend/reporting)
- [ ] K149 — **Formatage des nombres (reporting/dashboard).** Router tout montant/%/date affiché par les utilitaires F19 (`Intl.NumberFormat` `fr-MA` MAD ; notation compacte pour KPI) + `tabular-nums`. **Done =** figures localisées et formatées + tests. Files: `frontend/src/pages/Dashboard.jsx`, `frontend/src/pages/Reporting.jsx`. (ROUTINE) (@lane: frontend/reporting)

## Group L — Global UX behaviors

- [ ] L150 — **Adoption des tokens de mouvement.** Remplacer les durées de transition en dur (0.12/0.15/0.22 s) par les tokens `--motion-*` + courbes ease-out (`cubic-bezier(0.23,1,0.32,1)`), n'animer que `transform`/`opacity`, conserver `prefers-reduced-motion`. **Done =** transitions tokenisées dans `index.css` et composants concernés. Files: `frontend/src/index.css`. (ROUTINE) (@lane: frontend/css)
- [ ] L151 — **UI optimiste + statut d'enregistrement automatique.** Helper d'update optimiste avec rollback à l'échec (React 19 `useOptimistic` / Redux existant) + indicateur inline « Enregistrement… / Enregistré » et ligne en vol à ~50 % d'opacité + spinner ; appliquer à 2 bascules à fort trafic (étape lead, statut client). N'utilise que des endpoints existants (aucune migration). **Done =** helper + 2 adoptions + tests. Files: `frontend/src/hooks/useOptimisticSave.js` (nouveau). (ROUTINE) (@lane: frontend/hooks)
- [ ] L152 — **Helper confirmation + toast sur mutation.** Fournir un `confirmDialog` (AlertDialog) et une convention `toast.success/error` (et `toast.promise` pour les ops longues) pour remplacer `window.confirm`/`alert` ; adopté par les tâches de groupe J. **Done =** helper partagé + tests. Files: `frontend/src/ui/confirm.jsx` (nouveau). (ROUTINE) (@lane: frontend/ui)
- [ ] L153 — **Discipline des états de chargement.** Hook `useDelayedLoading` : rien sous 300 ms, squelette au-delà de ~500 ms calqué sur le contenu, jamais spinner + squelette ensemble ; variantes `Skeleton` par disposition. **Done =** hook + variantes + tests. Files: `frontend/src/hooks/useDelayedLoading.js` (nouveau), `frontend/src/ui/Skeleton.jsx`. (ROUTINE) (@lane: frontend/hooks)

## Group M — Mobile & PWA polish (Meryem is iPhone-primary)

- [ ] M154 — **Repli tableau → cartes sur mobile.** Sous 768 px, chaque ligne `DataTable` devient une carte (titre, métrique clé en grand, chevron vers le détail) ; en-tête masqué. **Done =** repli cartes + tests. Files: `frontend/src/ui/datatable/DataTable.jsx`. (ROUTINE) (@lane: frontend/datatable)
- [ ] M155 — **Passe tactile + zones sûres.** Cibles ≥44 px, padding `env(safe-area-inset-*)` sur la nav basse et les actions collantes, `-webkit-tap-highlight-color: transparent` + état `:active` propre, champs ≥16 px. **Done =** conforme iPhone (encoche / indicateur), tests. Files: `frontend/src/index.css`. (ROUTINE) (@lane: frontend/css)
- [ ] M156 — **Polissage de la nav basse.** Plafonner à 5 onglets ≥44 px, padding bas zone sûre, actif en brass, atteignable au pouce. **Done =** nav basse conforme + tests. Files: `frontend/src/components/layout/BottomTabBar.jsx`, `frontend/src/index.css`. (ROUTINE) (@lane: frontend/css)
- [ ] M157 — **Polissage PWA iOS.** Style de barre d'état par thème, splash `apple-touch-startup-image` (déjà générés), `viewport-fit=cover`, scroll inertiel `-webkit-overflow-scrolling` + `overscroll-behavior: contain`, finitions standalone. **Done =** rendu « natif » iOS vérifié. Files: `frontend/index.html`, `frontend/src/features/pwa/`. (ROUTINE) (@lane: frontend/pwa)
- [ ] M158 — **Sheet sur mobile pour créer/éditer.** Adaptateur : `Dialog` centré sur desktop (≥768 px) / `Sheet` (tiroir bas) sur mobile, à partir des primitives existantes (sans nouvelle dépendance). **Done =** adaptateur réutilisable + tests. Files: `frontend/src/ui/ResponsiveDialog.jsx` (nouveau). (ROUTINE) (@lane: frontend/ui)

## Group N — Accessibility & quality floor (WCAG 2.2 AA)

- [ ] N159 — **Focus jamais masqué + anneaux visibles (WCAG 2.4.11).** Le focus clavier n'est jamais caché derrière l'en-tête collant / la nav basse (`scroll-margin` adéquats), et tout élément interactif hérité porte un anneau focus-visible ≥2px contrasté ≥3:1. **Done =** focus toujours visible et non masqué + tests. Files: `frontend/src/index.css`. (ROUTINE) (@lane: frontend/css)
- [ ] N160 — **Accessibilité du DataTable.** Rôles grille (`role="grid"`, `aria-selected`, `aria-rowindex`), navigation clavier (flèches, Home/End, Entrée = ouvrir), cibles ≥24px. **Done =** rôles + clavier + tests axe. Files: `frontend/src/ui/datatable/DataTable.jsx`. (ROUTINE) (@lane: frontend/datatable)
- [ ] N161 — **Accessibilité des graphiques.** `role`/`aria-label` sur les graphes + repli « Voir le tableau » (table de données masquée) pour lecteurs d'écran et mobile. **Done =** repli tableau + ARIA + tests. Files: `frontend/src/ui/charts/`. (ROUTINE) (@lane: frontend/reporting)
- [ ] N162 — **Alternative au glisser + taille de cible (2.5.7 / 2.5.8).** Le réordonnancement de colonnes dispose d'une alternative sans glisser (boutons déplacer) et de cibles ≥24px. **Done =** alternative non-drag + tests. Files: `frontend/src/ui/datatable/DataTable.jsx`. (ROUTINE) (@lane: frontend/datatable)
- [ ] N163 — **Mouvement réduit correct + tests axe.** Sous `prefers-reduced-motion`, conserver opacité/couleur et supprimer mouvement/échelle (ne pas tout couper) ; ajouter des tests `vitest-axe` (déjà installé) sur les écrans clés. **Done =** comportement reduced-motion vérifié + tests axe verts. Files: `frontend/src/index.css`, `frontend/src/test/a11y.test.jsx` (nouveau). (ROUTINE) (@lane: frontend/css)

## Group O — Performance

- [ ] O164 — **Virtualiser les grandes listes.** Activer la virtualisation du moteur `DataTable` existant pour le catalogue stock et les grandes listes de leads (hauteurs de ligne fixes, seuil ~100 lignes). **Done =** rendu fluide >1000 lignes + tests. Files: `frontend/src/ui/datatable/DataTable.jsx`. (ROUTINE) (@lane: frontend/datatable)
- [ ] O165 — **Découpage des routes + chargement différé.** `React.lazy`/`Suspense` par route et différer les libs lourdes (leaflet, pdfjs, recharts) derrière des squelettes. **Done =** bundle initial réduit, mesures avant/après. Files: `frontend/src/router/`. (ROUTINE) (@lane: frontend/router)
- [ ] O166 — **Largeurs de colonnes mémoïsées (60 fps).** Pousser les largeurs aux cellules via variables CSS au lieu d'appeler la taille par cellule à chaque rendu. **Done =** redimensionnement fluide + tests. Files: `frontend/src/ui/datatable/DataTable.jsx`, `frontend/src/ui/datatable/logic.js`. (ROUTINE) (@lane: frontend/datatable)

## Group P — Consistency & cleanup

- [ ] P167 — **Unifier sur UN seul tableau.** Migrer les derniers tableaux HTML hérités hors reporting vers le moteur partagé. **Done =** un seul moteur de tableau dans l'app + tests. Files: `frontend/src/pages/`. (ROUTINE) (@lane: frontend/reporting)
- [ ] P168 — **Cohérence des icônes.** Remplacer les SVG inline de `Sidebar.jsx` par lucide à une taille/épaisseur unique et standardiser les tailles (3.5 / 4 / 5). **Done =** icônes cohérentes + tests. Files: `frontend/src/components/layout/Sidebar.jsx`. (ROUTINE) (@lane: frontend/css)
- [ ] P169 — **Supprimer les `style={}` inline.** Remplacer les styles inline par Tailwind/tokens dans `ExcelImport.jsx` et `ParrainagePage.jsx`. **Done =** plus de styles inline dans ces fichiers + tests. Files: `frontend/src/components/ExcelImport.jsx`, `frontend/src/pages/crm/ParrainagePage.jsx`. (ROUTINE) (@lane: frontend/crm)
- [ ] P170 — **Guide de style vivant (/ui).** Étendre la page `/ui` pour documenter les nouveaux tokens, l'échelle typo, le kit graphique, la densité, le mouvement et une checklist « definition of done » par composant. **Done =** guide à jour. Files: `frontend/src/pages/ui/`. (ROUTINE) (@lane: frontend/ui)
- [ ] P171 — **Migrer le moteur `DataTable` vers `@tanstack/react-table` (déjà installé) derrière l'API publique existante, avec parité de tests complète.** Refonte interne risquée, invisible pour le rendu — à valider par le founder avant exécution. **Done =** API inchangée, tous les tests existants verts. Files: `frontend/src/ui/datatable/`. (ARCH) (@lane: frontend/datatable)

## Pending Reda (carry these in the plan)
- [x] Group G/H frontend dependencies — RESOLVED 2026-06-20: all installed in frontend/package.json + lockfile and in use (@radix-ui/* primitives, class-variance-authority, tailwind-merge, clsx, lucide-react, sonner). @tanstack/react-table is installed but not yet wired (the current DataTable is hand-rolled) — a build detail, not a dependency-approval blocker. No further Reda approval pending.
- [x] Logo — RESOLVED 2026-06-20 (Reda: the logo already lives in the repo — the one the quote engine/simulator uses — so use it): the OS now uses the official `TAQIN☀R` wordmark (`quote_engine/assets/logo.png`) as product branding. Added `frontend/scripts/gen_brand_assets.py` (reproducible) → trimmed transparent wordmark `public/taqinor-logo.png` (now shown on the Login card, replacing the hand-drawn SVG) + a white variant `public/taqinor-logo-light.png` + the missing **iOS splash screens** `public/splash/apple-splash-*` (light logo on the navy brand bg, 8 common iPhone sizes, wired in index.html; excluded from the SW precache). PWA icons/favicon were already from this logo's sun-bolt glyph (M59). Also fixed the N92 sw.js notification icon path (`/pwa-192x192.png` → `/pwa-192.png`). The sidebar keeps the per-tenant company name (multi-tenant — not overridden).
- [x] Default theme (F18) — RESOLVED 2026-06-20: the app theme FOLLOWS the system/device setting, per user (each user may override). Theme scaffolding already exists in frontend/src/design/ (ThemeProvider, theme.js with prefers-color-scheme).
- Hard constraints (do not violate): never touch the devis/facture PDF templates, the public PDF pages, the PdfCanvas content, or the apps/web marketing site; STAGES.py stays a fixed CI contract; all schema changes additive/nullable, seeded from current in-code defaults.

---

### Group A — Devis acceptance, wired to Signé, facture & chantier (core unblock)

### Group B — Bug: file attachments

### Group C — Bug: navigation menu

### Group D — Paramètres: split + far more editable settings (all in one pass)



### Group E — End-to-end (E2E) browser test suite covering every screen flow

---

## DONE LOG (agent appends one plain-language line per completed task)

- 2026-06-20 — Logo resolved: the OS uses the official Taqinor wordmark (the repo's quote-engine logo) as product branding — real logo on the Login screen + iOS splash screens generated from it (`gen_brand_assets.py`), PWA icons already from its glyph; fixed the web-push notification icon path. Sidebar keeps the per-tenant company name.
- 2026-06-20 — G10 (first half) verified already-present: the lead model already carries `fbclid` + `utm_source/medium/campaign/content/term` (crm migration 0006), the website lead webhook maps and stores them (`apps/crm/webhooks.py`), and `apps/web` captures first-touch fbclid+UTM from the landing URL and submits them (`Layout.astro`, `lib/lead.ts`), covered by `apps/crm/tests_webhook.py`. Ticked `[x] (already present)`. The CAPI SEND (second half) stays gated on Reda's Meta pixel token.

