# Internal Team Chat ("Discuss") — Design Spec

- **Date:** 2026-06-21
- **Status:** Approved (brainstorm with Reda, 2026-06-21) — queued as **PLAN2 Group S (S1–S21)**.
- **Owner module:** new Django app `apps/chat` + `frontend/src/features/messaging` + a FastAPI transcription endpoint.

## 1. Goal & scope

A best-in-class **internal team chat** inside TAQINOR OS: staff message each other
**1-to-1 (DMs)** and in **named channels**, with file/image/voice attachments,
**@mentions**, **reactions**, **pinned messages**, **message search**, **edit/delete**,
and the ERP-specific superpower of **dropping a record (lead/devis/chantier) into a
conversation as a rich clickable card**. Voice memos are **transcribed** (French /
Arabic / Darija best-effort).

Explicitly **out of scope for v1**: client/lead-facing messaging, record-level chatter
(the existing `crm.LeadActivity` already covers that), and true real-time transport
(typing indicators / live presence / instant delivery) — those are deferred to the
gated WebSocket upgrade (S21).

## 2. Key decisions (from the brainstorm)

| Decision | Choice | Why |
|---|---|---|
| Who chats | **Internal team only**, company-scoped | The classic ERP "Discuss" module; reuses existing users/companies. |
| Real-time transport | **Smart polling + Web Push now; WebSocket later (gated)** | No WebSocket infra today; polling + the existing push feels instant for team-chat volume and ships within the current architecture. |
| Feature set | DMs, channels, attachments, unread badges, search, edit/delete, **@mentions, voice memos, share-a-record, reactions + pinned** | Founder selected the full set. |
| Voice transcription | **Self-hosted `faster-whisper`** in the FastAPI service | No per-message cost, audio never leaves the server; FR/AR strong, Darija best-effort. |
| UI naming | "Messages" / "Discuss", French UI | Matches the rest of the app. |
| Channel privacy | **Invite-only** (creator adds members) | Sensible default; no company-wide public firehose. |

## 3. Architecture

### 3.1 Multi-tenancy & access (non-negotiable)
Every model carries a `company` FK **forced server-side** (never from the request body).
Every viewset is **company-scoped AND membership-checked**: a user can only read/post in
conversations they belong to. Cross-tenant access returns 404; non-member access 403.

### 3.2 Data model (`apps/chat`)
- **Conversation** — `company`, `kind` ∈ {`dm`, `channel`} (TextChoices), `name` (channels
  only), `created_by`, `is_archived`, timestamps.
- **ConversationMember** — `conversation`, `user`, `role` ∈ {`member`, `admin`},
  `last_read_at` (drives unread counts), `is_muted` (per-conversation push mute),
  `joined_at`; unique `(conversation, user)`.
- **Message** — `conversation`, `sender`, `body`, `kind` ∈ {`text`, `voice`, `system`,
  `record`}, `reply_to` (self-FK, nullable), `created_at`, `edited_at` (nullable),
  `deleted_at` (nullable soft-delete), `pinned_at`/`pinned_by` (nullable). Generic
  record-link for share-a-record: `shared_content_type`/`shared_object_id` + `shared_label`
  snapshot.
- **MessageAttachment** — wraps `apps/records/storage.py` (MinIO, type-validated, 10 MB):
  `file_key`, `filename`, `mime`, `size`, `kind` ∈ {`image`, `file`, `voice`}; voice extras
  `duration_s`, `transcript`, `transcript_lang`, `transcript_status` ∈ {`pending`, `done`,
  `failed`, `disabled`}.
- **MessageReaction** — `message`, `user`, `emoji`; unique `(message, user, emoji)`.
- **MessageMention** — `message`, `mentioned_user` (targeted @mention push).

All migrations additive/nullable. Endpoints under `/api/django/chat/…`.

### 3.3 Real-time behavior (polling + push)
- **Open conversation:** short-poll new messages (~3 s).
- **Conversation list + header chat badge:** slower poll (like `NotificationBell` today),
  paused when the tab is hidden (`visibilitychange`).
- **Backgrounded/closed:** existing **Web Push** fires via two new EventTypes —
  `CHAT_MESSAGE` and a louder `CHAT_MENTION` — routed through the existing `notify()`,
  deep-linking the service worker to the conversation. **Per-conversation mute** suppresses
  pushes for noisy channels; existing per-user notification preferences are respected.

### 3.4 Attachments & voice transcription
Uploads go through `records.storage.store_attachment` (reuse: validation, MinIO, 10 MB).
Voice flow: record in browser (`MediaRecorder`, no new npm dep) → upload as a voice
attachment (`transcript_status=pending`) → a Django **Celery** task pulls the audio and
calls a new FastAPI **`POST /transcribe`** endpoint running **`faster-whisper`** (lazy
model load/cache; FR/AR/Darija language hint) → transcript + language written back on the
attachment → the frontend polls and shows it. Behind a `CHAT_TRANSCRIPTION_ENABLED` flag:
**when off, voice memos still send and play**, `transcript_status=disabled`.

### 3.5 Share-a-record (cross-app boundary)
A message can carry a lead/devis/chantier. The label/subtitle/url snapshot is resolved
through the **target app's `selectors.py`** (e.g. `crm.selectors.lead_card`,
`ventes.selectors.devis_card`, `installations.selectors.chantier_card`) — never importing
their models/views (CI import contract). The card renders read-only and navigates to the
record on click.

### 3.6 Frontend (`frontend/src/features/messaging`)
A `/messages` route + sidebar entry + a header chat icon with a total-unread badge.
Two-pane layout (conversation list | message thread; single-pane drill-down on mobile),
composer with @mention autocomplete + attach + voice-record + share-record. Built entirely
from the existing `@/ui` kit (Avatar, Dialog, Sheet, FileUpload, Popover, MultiSelect,
Badge) and Redux/axios plumbing. **No new npm dependency** (reactions use a small curated
emoji set, not a picker library; voice uses the browser `MediaRecorder`).

## 4. Reuse map (build on what exists)
- **Notifications:** `notify(user, event_type, …)` + Web Push (VAPID) + service worker
  deep-link — add two EventTypes only.
- **Storage:** `apps/records/storage.py` (MinIO) for all attachments — no new bucket/infra.
- **Background jobs:** existing Celery app (`erp_agentique/celery.py`) for transcription.
- **Auth:** existing JWT-cookie auth; viewsets default to `IsAuthenticated` + a new
  `IsConversationMember`.
- **UI:** the `@/ui` design system + the `NotificationBell` polling pattern.

## 5. Deferred / gated
- **S21 — WebSocket upgrade (Django Channels):** instant delivery, typing indicators, live
  presence. Needs **new infra** (ASGI server, Redis channel layer, nginx WS proxy) the
  founder must provision — STOP-AND-ASK; a plan-run must not build it until then. It
  replaces polling transparently when it lands.
- Client/lead messaging and WhatsApp inbound/outbound integration — a separate future
  module.

## 6. Task breakdown
Queued as **PLAN2 Group S, S1–S21**, lane-partitioned for parallel build:
- **Backend core lane `apps/chat` (S1–S9):** app+models → attachments/reactions/mentions →
  serializers/viewsets/permissions → read-state → search → uploads → reactions/pin →
  share-record → notifications+mute.
- **Transcription:** S10 FastAPI `faster-whisper` endpoint (lane `backend/fastapi_ia`,
  founder-approved dependency, flag-gated) → S11 Django Celery pipeline (lane `apps/chat`).
- **Frontend lane `frontend/messaging` (S12–S20):** api+slice+polling → route/nav/header
  shell → list pane → thread pane → composer/@mentions/edit-delete → voice+transcript →
  reactions/pin → share-record → new-conversation/manage-members modals.
- **Gated:** S21 WebSocket upgrade (ARCH).

Each task is company-scoped, ships with tests, and obeys every STANDING RULE in
`docs/PLAN.md`.
