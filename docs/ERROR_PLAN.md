# Taqinor OS — Error Plan & Bug Backlog

This file is the bug/error backlog **drained by the `work on error plan` command**
(defined in `CLAUDE.md`). That command is identical to `work on the plan` in every
respect — same `scripts/plan_lanes.py`-driven maximally-parallel cross-category lane
plan (run it on `docs/ERROR_PLAN.md`), same concurrent worktree subagents up to the
session ceiling continuously refilled (work-stealing), same dynamic-workflow-with-
review engine, same stop conditions, same per-task commit/tick/DONE-LOG, same
sync-safe single self-merge `dev` → `main` — **with exactly one difference: it
works through THIS file** instead of `docs/PLAN.md` / `docs/PLAN2.md`. There is no
`.running` lock (same as `work on the plan`). Tasks use `ERR*` ids so their states
feed the plan fingerprint and CODEMAP §10 exactly like the other plan files
(`scripts/codemap_fingerprint.py` → `PLAN_FILES`).

This file is the single source of truth + memory between sessions for known bugs.
Each run **verifies a task isn't already fixed before building it** (mark
`[x] (already present)` if it is), fixes it with tests on its lane's worktree
branch, ticks it `[x]`, adds a DONE LOG line, refreshes CODEMAP §10 + re-runs
`--write` in the same commit as the tick, and the run self-merges once at the end.

**Provenance.** Seeded 2026-06-20 from a read-only 11-lane audit of `main`
@ `98e9d23` (backend apps, FastAPI IA service, React frontend, and the apps/web
Astro site). `main` advanced to `24b0cb5` during the audit, so a handful of items
may already be fixed (notably the notifications-engine wiring) — the verify-step
catches those and ticks them `[x] (already present)`. Severities are the auditors'
ratings; the build run re-confirms each on the live tree.

---

## HOW TO RUN (read this every session)

Follow the `work on error plan` rules in `CLAUDE.md` (they mirror `docs/PLAN.md`'s
HOW TO RUN verbatim, only the drain file changes). One-line starter:

> Read `docs/ERROR_PLAN.md`. Work through EVERY unchecked `[ ]` ERR task: first
> run `python scripts/plan_lanes.py docs/ERROR_PLAN.md` to get the maximally-parallel
> cross-category wave plan, then build those lanes in parallel with concurrent worktree
> subagents (each in its own git worktree) up to the session ceiling (default 8, raised
> as high as the session can sustain via `--max-lanes`), continuously refilled
> (work-stealing), coupled fixes in sequence
> inside a lane (default: dynamic workflow with a separate adversarial review agent
> that must pass each change before it's merge-eligible; fall back to plain parallel
> worktree subagents — never a single serial one-task-at-a-time agent). For each
> task: verify it isn't already fixed, build the fix with tests, commit it to its
> worktree branch, tick it `[x]`, add a dated DONE LOG line, refresh CODEMAP §10 and
> re-run `python scripts/codemap_fingerprint.py --write` in the same commit, then
> continue to the next. Skip-and-note any blocker (`[BLOCKED: reason]` → GATED) and
> keep going. At the very end, fold every worktree branch into one `dev`, integrate
> the latest `origin/main` first (merge it in, never force-push), get the four
> required CI checks green over the whole batch (with MinIO) and self-merge `dev` →
> `main` exactly once (auto-deploys — no deploy command; no per-agent PR, no
> per-task merge). Report once, in plain language, including the lane plan. Finally
> print `PLAN_STATUS: EMPTY` if no `[ ]` task remains, else `PLAN_STATUS: MORE`.

---

## BUILD QUEUE (fix highest-severity first)

### Critical

- [x] ERR1 — [FastAPI] NL→SQL agent has no SELECT-only enforcement in code (`sql_agent_service.py:266-327,333-347`): only an LLM-prompt sentence forbids INSERT/UPDATE/DELETE/DROP, so a prompt injection or model error runs arbitrary DML/DDL against the shared live DB. Add parser-based single-SELECT validation that rejects every other statement.
- [x] ERR2 — [FastAPI] NL→SQL tenant isolation is defeatable four ways (`sql_agent_service.py:73-93,276-327`): the `company_id = N` substring check is bypassed by `OR 1=1`; the filter is injected on only one table so any JOIN/multi-table FROM reads other tenants; tables without a `company_id` column (`authentication_company`, `roles_role`) are fully unscoped; and subquery/UNION halves are mis-scoped. Replace the regex rewrite with per-tenant DB views or a parser-driven rewrite.
- [x] ERR3 — [FastAPI] The SQL agent connects as the table-owner Postgres role (`docker-compose.yml:87-88` + `core/config.py:38-47`), giving the "read-only" agent full INSERT/UPDATE/DELETE/DDL. Use a dedicated role with `SELECT` only on the allowlisted tables and no DDL.
- [x] ERR4 — [auth] `is_responsable` returns True for ANY user that merely has a role (`authentication/models.py:152-159`), so every endpoint gated by `IsResponsableOrAdmin` is reachable by roles meant to be read-only/limited — incl. ventes (validate quote, emit invoice, `marquer_livre` stock moves, `creer_facture`), crm (lead edit/reassign/notes/merge/bulk), installations, records uploads, and monitoring (write configs/credentials, `sync-now`, create readings that auto-create SAV tickets). Fix `is_responsable` to consult the role's permissions/tier, or migrate the business endpoints to `HasPermissionOrLegacy(<code>)`.
- [x] ERR5 — [roles/auth] Responsable-tier users can self-grant any permission and escalate to Administrator (`roles/views.py:23,46` + `roles/serializers.py:13,26-32`): `validate_permissions` accepts any code incl. `roles_gerer`/`prix_achat_voir`, `perform_update` has no system-role guard, and `UserSerializer.role` is writable — so a Responsable can add `roles_gerer` to their own role.
- [x] ERR6 — [automation] Automation actions re-fire their own triggers with no recursion guard (`automation/actions.py:163-164,181-182` + `signals.py:53-130`): SET_FIELD/ASSIGN_RECORD call `instance.save()` synchronously inside the `post_save` that triggered them, so a rule that writes the field its trigger watches recurses to `RecursionError` and wedges any save of Lead/Devis/Installation/Facture/Produit.
- [x] ERR7 — [ventes] `LigneDevisViewSet`/`LigneFactureViewSet` allow cross-tenant line injection (IDOR write) (`ventes/views.py:462-483,1206-1228`): no `perform_create` + serializer `fields='__all__'` with a writable `devis`/`facture` FK, so a user can POST a line onto another company's document and mutate its totals.
- [x] ERR8 — [ventes] `DevisViewSet.perform_update` mass-assignment lets a devis be re-pointed at another company's `client`/`lead` (`ventes/views.py:285-300`): `perform_create` validates lead/client company but `perform_update` does not, leaking the foreign record through the read serializer.
- [x] ERR9 — [sav] `ContratMaintenanceViewSet` has no `_check_tenant` and its serializer no `validate` (`sav/maintenance.py:46-66`): writable `client`/`installation` FKs let a contract bind another company's records, and the generated visits/PDF then leak the foreign installation.
- [x] ERR10 — [stock] The `MouvementStock` write endpoint accepts arbitrary negative/zero/overflow quantities with no validation (`stock/views.py:443-496`): no `validate_quantite`, a bare `IntegerField`, a SORTIE subtracts with no floor, and a negative SORTIE silently increases stock — trivial inventory corruption/fraud.
- [x] ERR11 — [reporting/exports] CSV/Excel formula injection in the shared `build_xlsx_response` (`crm/exports.py:36-37`): cells are written verbatim with no neutralization of leading `=` `+` `-` `@`, and user fields (lead/client names, tags, note bodies) flow into every xlsx export, executing as formulas when an admin opens the file. Prefix risky leading chars with `'`.
- [x] ERR12 — [frontend] `OcrStockImport` BCF reception reads `lignes` off the create response and sends stock from a possibly-empty source (`pages/stock/OcrStockImport.jsx:469-472`): if the serializer doesn't echo `lignes`, no reception is sent, the BCF stays "envoyé" and stock is never incremented while the UI logs "Reçu" — silent stock desync.

### High

- [x] ERR13 — [ventes] `BonCommandeViewSet.perform_create` doesn't validate body `client`/`devis` against the company (`ventes/views.py:510-515`): a BC can be created bound to another tenant's client/devis.
- [x] ERR14 — [ventes] `FactureViewSet.perform_create` doesn't validate body `client`/`bon_commande`/`devis` against the company (`ventes/views.py:680-689`): a facture can bind another tenant's records.
- [x] ERR15 — [ventes] `BonCommandeViewSet.marquer_livre` does `int(ligne.quantite)`, truncating fractional quantities (`ventes/views.py:547`): a DecimalField quantity like 3.5 decrements stock by 3 and records a wrong `MouvementStock` — silent inventory drift on cable/metre lines.
- [x] ERR16 — [ventes] The legacy BC→Facture path ignores `Devis.option_acceptee` and bills BOTH options (`ventes/views.py:589-638`): the échéancier path honors the chosen option, but `creer_facture` copies every devis line, over-billing two-option quotes.
- [x] ERR17 — [quote_engine] `generate_premium_pdf` mutates ~40 module globals (`generate_devis_premium.py:1946-2039`); the synchronous `/proposal` and public-share endpoints render inside a Gunicorn thread (prod runs `--threads 4`), so two concurrent requests race and one client can receive a PDF with another client's name/address/totals — cross-tenant leak.
- [x] ERR18 — [FastAPI] JWT verification doesn't require `exp` (or `iss`/`aud`) (`core/security.py:42-43`): a token minted without an expiry never expires. Add `options={"require":["exp"]}` + audience/issuer binding.
- [x] ERR19 — [FastAPI] The raw user question is concatenated into the agent prompt that drives the write-capable action tools (`sql_agent_service.py:167-249,626-637`): prompt injection can attempt cross-record writes that rely entirely on Django rejecting them.
- [x] ERR20 — [FastAPI] `prix_achat`/margin confidentiality is only a prompt instruction (`sql_agent_service.py:586-588`): `stock_produit.prix_achat_ht` stays fully selectable by the SQL tool, so injection or "donne-moi le prix d'achat" leaks buy prices. Enforce at the query layer, not the prompt.
- [x] ERR21 — [auth] `UserViewSet`/`RegisterView` accept an arbitrary `role` PK with no company or tier check (`authentication/serializers.py:34-41,99-107` + `views.py:300-324`): a manager can assign another tenant's role, or the local admin role, to escalate a user.
- [x] ERR22 — [auth] `prod.py` omits production hardening (`erp_agentique/settings/prod.py`): `SESSION_COOKIE_SECURE`, `CSRF_COOKIE_SECURE`, `SECURE_SSL_REDIRECT`, `SECURE_PROXY_SSL_HEADER`, HSTS preload are unset and `CORS_ALLOWED_ORIGINS` isn't overridden — session/CSRF cookies can travel over HTTP and `request.is_secure()` can misevaluate behind the proxy.
- [x] ERR23 — [stock] `MouvementStockViewSet.perform_create` isn't atomic and uses `refresh_from_db()` without `select_for_update()` (`stock/views.py:472-496`): concurrent SORTIEs lose an update and corrupt the `quantite_avant`/`quantite_apres` audit columns.
- [x] ERR24 — [stock] `recevoir` and `apply_retour_fournisseur` read `quantite_stock` without `select_for_update()` inside their atomic block (`stock/views.py:804-829`, `services.py:457-472`): concurrent receptions/returns of the same product lose an increment/decrement.
- [x] ERR25 — [parametres] `CompanyProfileSerializer` uses `fields='__all__'` with `company` writable (`parametres/serializers_company.py:21-24`): a PATCH `{"company": <other_id>}` re-points the caller's profile company FK — tenant-integrity violation / 500. Add `company` to `read_only_fields`.
- [x] ERR26 — [frontend] The map popup injects unescaped `popupHtml` (`components/MapView.jsx:92-95`) built from server fields by its callers (`pages/CartePage.jsx:73-76`, `ParcInstallePage.jsx:128-130`): a client/lead/status name containing markup executes as stored XSS when the popup opens. HTML-escape the fields before building the string.
- [x] ERR27 — [frontend] Route guards enforce authentication but not role/permission (`router/index.jsx:88-91,121-176`): a `normal` user can deep-link admin routes (`/admin/users`, `/admin/roles`, `/parametres`, `/journal`, `/reporting`) and the page mounts. Add a role/permission check in the loader.
- [x] ERR28 — [frontend] The `ParametresEntreprise` `<form>` lacks `noValidate` while wrapping `type="number"` inputs with `min`/`max`/`step` (`ParametresEntreprise.jsx:507` + Avance/Devis/Leads/Messages sections): a step-mismatched or out-of-range value makes the field `:invalid` and aborts submit, violating the "never reject/snap typed numbers" rule. Use `step="any"`/`noValidate`.
- [x] ERR29 — [frontend] `InstallationsPage` kanban status/reschedule writes have no rejection handling/rollback, and a stale/background `error` blanks the whole board (`InstallationsPage.jsx:248-262,268-276`): failed drags don't roll back or toast, and any truthy `error` unmounts the board, open modals, and scroll position.
- [x] ERR30 — [frontend] `EquipementsPage` shows raw `JSON.stringify(err.response.data)` on save failure (`pages/sav/EquipementsPage.jsx:87`) instead of a French message.
- [x] ERR31 — [frontend] `MouvementsPage.validate()` requires quantity `> 0` for all types incl. `ajustement` (`pages/stock/MouvementsPage.jsx:314-323`), so zeroing a product's stock is impossible even though the preview shows `previewApres = 0`.
- [x] ERR32 — [web] `simulate.ts`/`preview-lead.ts` log full lead PII (name/phone/city/consent) via `JSON.stringify(record)` on the CRM-forward failure path (`apps/web/src/pages/api/simulate.ts:50` + `preview-lead.ts:64`), and `observability.enabled = true`; with `LEAD_WEBHOOK_URL` unset (today's default) every qualified lead's PII is persisted in Cloudflare logs. Redact before logging.

### Medium

- [x] ERR33 — [ventes] `DevisViewSet.accepter` forces `ACCEPTE` with no guard on the current status (`ventes/views.py:171-208`): a `refuse`/`expire`/already-`accepte` devis is accepted unconditionally, advancing the funnel and enabling BC/échéancier from a dead quote.
- [x] ERR34 — [ventes] `FactureViewSet.creer_avoir` swallows all per-line errors and silently drops lines (`ventes/views.py:998-1010`): `designation: null` raises `TypeError`, quantite/prix_unitaire are unvalidated, and `except Exception: continue` creates the credit note short of its amount with no error.
- [x] ERR35 — [ventes] `task_generate_devis_pdf` isn't idempotent under `acks_late` + retry (`ventes/tasks.py:18-39`): a crash after MinIO upload but before ack re-renders, and every click fires a fresh `.delay()`, racing the `fichier_pdf` write.
- [x] ERR36 — [ventes] `relance_reminders` scheduling is destructive/lossy (`ventes/scheduled.py:80-126`): it nulls `prochaine_relance` after sending instead of advancing to the next level, so a multi-level dunning sequence only ever sends once, and `niveau` can jump straight to the harshest configured level.
- [x] ERR37 — [quote_engine] User-controlled text (client name/address/phone/ICE; line designation/marque/description/garantie) is interpolated raw into the PDF HTML with no escaping (`generate_devis_premium.py`, multiple lines): markup breaks the table layout or injects styled content into the document. Escape before render.
- [x] ERR38 — [crm] `resolve_client_for_lead`'s check-then-create isn't transactional (`crm/services.py:395-421`): two concurrent quote creations sharing an email both create a Client, hitting the `unique_together` and surfacing an unhandled 500 instead of the documented reuse.
- [x] ERR39 — [crm] `Lead.gps_lat`/`gps_lng` have no range validation (`crm/models.py:181-184`): a latitude outside ±90 / longitude outside ±180 persists silently, breaking downstream mapping/distance logic.
- [x] ERR40 — [installations] `mise_en_service` sets `statut` directly and skips `_stamp_statut_dates`/`_apply_stock_statut_effects` (`installations/views.py:324-361`): a chantier driven to mise-en-service never stamps `date_reception` yet counts as parc, desyncing the milestone timeline and parc reporting.
- [x] ERR41 — [installations] `field_capture.validate_consommation` truncates fractional real-consumption via `int(qte)` (`installations/field_capture.py:159`): a 0.5 line records a SORTIE of 0, marks `stock_applique`, and loses the consumption forever (the idempotency flag blocks re-apply).
- [x] ERR42 — [FastAPI] CORS `allow_credentials=True` with a default origin and `_DEBUG` defaulting True (`main.py:9,25-31`): `/docs` and `/redoc` are exposed unless `DJANGO_DEBUG=0` is explicitly set — a fail-open schema disclosure.
- [x] ERR43 — [FastAPI] `sql_db_schema`/`sql_db_list_tables` tools and `sample_rows_in_table_info=2` run on the privileged connection with no tenant filter (`sql_agent_service.py:556-560`), feeding 2 real rows of each table into the LLM context — incidental cross-tenant leakage.
- [x] ERR44 — [FastAPI] The sql_agent endpoint reads `company_id` from the JWT with no presence check; `company_id=0` disables all SQL scoping (`api/endpoints/sql_agent.py:42-51`): unlike OCR (which 403s on missing company), a token without a company claim reads across all tenants.
- [x] ERR45 — [auth] JWT auth cookies use `SameSite=Strict` with cross-origin credentialed CORS and no DRF CSRF enforcement (`authentication/views.py:21-22,33-49`): CSRF protection on cookie-authenticated mutations rests solely on SameSite, which is brittle and silently disappears if ever relaxed to Lax. Define an explicit CSRF strategy.
- [x] ERR46 — [publicapi] `WebhookViewSet` allows CRUD of `target_url` and `delivery._deliver_one` POSTs to it server-side with no scheme/host allowlist (`publicapi/views.py:70-74` + `delivery.py:41-44`): an admin/Responsable can point a webhook at internal addresses (169.254.169.254, minio, db) — SSRF. Require https and block private/loopback hosts.
- [x] ERR47 — [monitoring] `evaluate_underperformance` does read-then-create on `UnderperformanceFlag` with no `select_for_update` (`monitoring/services.py:131-139`): concurrent readings for one installation both insert, violating the partial-unique constraint and surfacing a 500 that fails the business action.
- [x] ERR48 — [automation] `run_approved` resolves the deferred target by raw PK with no company filter (`automation/engine.py:174-183`): a latent cross-tenant write primitive if `target_model`/`target_id` ever cross. Add `company=approval.company` to the lookup.
- [x] ERR49 — [automation] SEND_EMAIL uses `send_mail(fail_silently=True)` and always returns SUCCESS (`automation/actions.py:107-114`): a dropped email is logged as delivered, undermining the AutomationRun journal.
- [x] ERR50 — [notifications] VERIFY whether the notification engine is actually invoked by business events (`notifications/services.py`): at 98e9d23 `notify()` was called only from tests with no signal wiring (feature inert); the N75/N76 work merged at 24b0cb5 may have wired it — confirm, and if still gapped wire the LEAD_ASSIGNED/DEVIS_ACCEPTED/FACTURE_OVERDUE producers.
- [x] ERR51 — [dataimport] `commit` imports rows one-by-one with no `transaction.atomic` (`dataimport/services.py:107-181`): a mid-loop error returns 400 while earlier rows are committed and the counter is lost — silent half-imports; re-upload re-imports survivors.
- [x] ERR52 — [dataimport] Product import sets `quantite_stock` directly with no `MouvementStock` audit row and no non-negative guard (`dataimport/services.py:151-178`): imported products can carry negative/unaudited opening stock, bypassing the movement ledger.
- [x] ERR53 — [dataimport] Import dry-run/commit swallow all exceptions into a generic 400 and read the whole upload into memory with no size/row cap (`dataimport/views.py:31-33,45-49`): poor diagnostics plus an unbounded-memory DoS on a crafted upload.
- [x] ERR54 — [stock] `compute_besoin_materiel` truncates Decimal devis quantities via `int()` (`stock/services.py:558-565`): a 2.5-unit line becomes a requirement of 2, under-ordering on the drafted BCF.
- [x] ERR55 — [parametres] `CompanyProfile` has no validation on `tva_standard`/`tva_panneaux`/`remise_max_pct`/thresholds or the `doc_prefixes`/`doc_numbering`/`payment_terms` JSON (`serializers_company.py` + `models_company.py:108-141`): a negative or >100 TVA flows straight into invoice/quote math.
- [x] ERR56 — [records] `resolve_target` lets `Model.DoesNotExist` (and a bad-type pk) escape as a 500 (`records/serializers.py:24`): callers only catch `ValueError`, so a valid `model` + non-existent `id` 500s on activity/attachment list, create, and count.
- [x] ERR57 — [reporting] `stock_report`'s low-stock list doesn't exclude `seuil_alerte=0` (`reporting/reports.py:147-149`), unlike the dashboard, so every default-threshold zero-stock product is falsely reported low — noisy and inconsistent.
- [x] ERR58 — [frontend] The `iaApi` interceptor reads `error.config` unguarded and hard-redirects to `/login` on refresh failure (`api/iaApi.js:27-28`): it can throw inside the interceptor on setup errors and wipes in-progress OCR/agent forms instead of the graceful session-expired flow.
- [x] ERR59 — [frontend] Logout does `localStorage.clear()`, wiping theme, sidebar state, saved lead views/filters and PWA flags (`store/index.js:27-32`) — auth is cookie-based so none of this needs eviction. Scope the removal to app-data keys.
- [x] ERR60 — [frontend] `fetchMe.fulfilled` stores only `{username}`, dropping email/other user fields (`features/auth/store/authSlice.js:65`): after any reload the header email row and other consumers get `undefined`, differing from the login path.
- [x] ERR61 — [frontend] Raw error objects are shown to users via `JSON.stringify` on `LeadsPage` (`leads/LeadsPage.jsx:332`) and `InstallationDetail` (`InstallationDetail.jsx:373`) — translate to French like the rest of the app (see also ERR30).
- [x] ERR62 — [frontend] Swallowed fetch errors masquerade as empty data on `BalanceAgeePage` (`BalanceAgeePage.jsx:25-27`), `MonitoringSection` (`MonitoringSection.jsx:35`, which also keeps a stale success badge), and the parametres section `load()` helpers — users can't tell "server down" from "empty". Show an error/retry state.
- [x] ERR63 — [frontend] `ParametresEntreprise.saveNiveaux` fires per-row PATCHes in `Promise.all` with `.catch(()=>{})` (`ParametresEntreprise.jsx:281-289`): one failing row rejects the batch silently while earlier rows already saved — partial save, no feedback.
- [x] ERR64 — [frontend] `TicketsPage` bulk PATCH is non-atomic and doesn't reload on partial failure (`TicketsPage.jsx:877-884`): some tickets change server-side, others don't, and the table shows stale state until a manual refresh.
- [x] ERR65 — [frontend] `MouvementsPage` "Transferts" tab never shows its `(n)` count (`MouvementsPage.jsx:102-112`): `counts` omits the `transfert` key — inconsistent with the other tabs.
- [x] ERR66 — [frontend] `InterventionsPage` reassign doesn't refetch on failure and isn't optimistic (`InterventionsPage.jsx:507-511`): a failed reassign leaves the Select showing the picked technician while the server holds the old one.
- [x] ERR67 — [frontend] The voice-memo recorder leaks the mic stream on unmount (`features/installations/InterventionCapturePanels.jsx:216-224`): tracks are stopped only in `onstop`, so closing the sheet while recording leaves the microphone active. Add a `useEffect` cleanup.
- [x] ERR68 — [frontend] `Reporting` destructures the dashboard payload unconditionally after a null check (`Reporting.jsx:257-258`): a partial/`{}` 200 throws "Cannot read properties of undefined" and blanks the whole report. Add per-key guards.
- [x] ERR69 — [frontend] The `Journal` data effect depends on both `filterParams` and `page` while each filter setter also resets `page` (`Journal.jsx:154,158-164`): on page ≥2 a filter change fires two paired request rounds.
- [x] ERR70 — [web] hreflang/x-default alternates have mismatched trailing slashes between locales (`apps/web/src/layouts/Layout.astro:30,37,79` via `i18n/utils.ts:15-21`): FR keeps the slash, EN/AR strip it, so search engines see conflicting alternates and the slash-less ones hit the trailing-slash 301. Make `stripLocale` slash-consistent.

### Low

- [x] ERR71 — [ventes] `Devis.total_tva` sums per-line TVA without quantize while `Facture`/échéancier quantize per rate bucket (`ventes/models.py:129-132` vs `447-481`): a mixed 10/20 quote's devis and facture totals can differ by a centime.
- [x] ERR72 — [ventes] `enregistrer_paiement`'s overpayment guard reads `montant_du` outside any row lock (`ventes/views.py:753-807`): concurrent payments can each pass the guard and overpay the invoice.
- [x] ERR73 — [ventes] `recouvrement._releve_data` pulls `Facture.objects.filter(client=client)` ignoring the owner visibility scope (`ventes/recouvrement.py:152-157`): a restricted-scope user sees invoices created outside their scope (company isolation still holds).
- [x] ERR74 — [quote_engine] `/proposal` is a GET that re-renders and persists `fichier_pdf` on every call (`ventes/views.py:329-359`; `public_views.py:39`) — a write side-effect on a safe method, compounding the global-state race (ERR17).
- [x] ERR75 — [quote_engine] The legacy fallback PDF key is not company-scoped (`utils/pdf.py:155` vs `builder.py:528`): `devis/{reference}.pdf` can collide across tenants when `USE_PREMIUM_QUOTE_ENGINE=False`.
- [x] ERR76 — [quote_engine] An unbounded `custom_acompte` can make a negative "Matériel" amount / >100% on the devis-final PDF (`generate_devis_premium.py:1268-1276` + `builder.py:139-143`). Clamp it.
- [x] ERR77 — [crm] `merge_leads`'s `_MERGE_FILL_FIELDS` omits several lead fields incl. `regularisation_8221` (the 82-21 flag), `relance_date`, `priorite`, the `visite_*` fields and site-intake (`crm/services.py:148-156,363-368`): merging loses those into the archived absorbed lead.
- [x] ERR78 — [crm] bulk/whatsapp endpoints don't coerce/validate `ids` element types (`crm/services.py:518` + `views.py:307-309`): non-integer ids raise a 500 instead of a clean 400, and the whatsapp duplicate-count check is distorted by string/duplicate ids.
- [x] ERR79 — [crm] The website webhook's idempotent re-POST within `DEDUP_WINDOW` blindly `setattr`s every mapped field incl. `None` (`crm/webhooks.py:133-144`): a sparser second POST can null out data captured by the first.
- [x] ERR80 — [installations/sav] Three SORTIE paths drive stock negative with no floor guard (`installations/services.py:343-355` consume_reservations, `field_capture.py:157-170`, `sav/views.py:333-343` ticket pieces): consuming more than on hand yields a negative `quantite_stock`.
- [x] ERR81 — [installations] `tool_return` is a GET that creates `ToolReturn` rows (`installations/views.py:1605-1618`): a read-only GET writes DB rows and concurrent GETs can race the `unique_together`. Make it POST/idempotent.
- [x] ERR82 — [outillage] No checkout step exists; a tool is only marked busy at return time inside `confirmer_tool_return` (`installations/views.py:1644-1669`): the same tool can sit in two interventions' prep lists at once with no double-booking detection.
- [x] ERR83 — [sav] `ContratMaintenance.is_due`/`renouvellement_du` default to naive `date.today()` (`sav/models.py:318-320,327`) instead of `timezone.localdate()`, so "due today" can be off by a day at TZ boundaries.
- [x] ERR84 — [FastAPI] The generated SQL (with real table names) is returned to the client in `SQLResponse.sql_query` (`sql_agent_service.py:619` + `api/endpoints/sql_agent.py`): schema disclosure despite the prompt's table-hiding intent.
- [x] ERR85 — [FastAPI] `create_tables()` runs unconditional `ALTER TABLE`/`CREATE INDEX` DDL on every boot as the owner role (`core/database.py:29-37`): an ad-hoc migration path outside any framework that reinforces the over-privileged role (ERR3).
- [x] ERR86 — [FastAPI] The OCR rate-limit fails open on any Redis error (`api/endpoints/ocr.py:54-77`): if Redis is down the 20/hour cap is silently disabled, allowing unbounded paid Zhipu calls (cost/DoS).
- [x] ERR87 — [auth] Logout blacklists only the refresh token; the access token stays valid up to its 8h lifetime (`authentication/views.py:273-297`): a stolen access token can't be revoked before expiry. Consider a shorter access lifetime or server-side revocation.
- [x] ERR88 — [auth] `seed_demo` creates `demo_admin`/`demo_resp` with the hardcoded password `Demo@2026!` (`seed_demo.py:72,89,305-306`): if ever run against production these become live known-credential accounts. Keep the command out of prod / force rotation.
- [x] ERR89 — [auth/publicapi] One-time-reveal secrets (webhook secret, API key) are returned without `Cache-Control: no-store` (`publicapi/views.py:70-101`). Harden the response headers.
- [x] ERR90 — [automation] The overdue-facture check compares `echeance` against the UTC date (`automation/signals.py:97-99`) while the app buckets in Africa/Casablanca; near midnight FACTURE_OVERDUE can fire a day early/late. Use `timezone.localdate()`.
- [x] ERR91 — [notifications] The in-app notification `body` is written unbounded while `title`/`link` are truncated (`notifications/services.py:135-138`) — an inconsistency; bound it.
- [x] ERR92 — [auth/audit] The login audit `actor_username` comes from the client-supplied `request.data['username']` (`authentication/views.py:73-76`): a spoofed string on a successful-login row (the FK `user` is authoritative). Normalize from the resolved user.
- [x] ERR93 — [stock] `StockEmplacement.unique_together` omits `company` and `quantite` allows negatives (`stock/models.py:238-257`): safe today (produit/emplacement are company-scoped, transfer guards balance) but it diverges from the company-in-constraint convention.
- [x] ERR94 — [stock] The per-emplacement breakdown derives the principal location as `total − sum(non-principal)` (`stock/services.py:188-212,234-244`): if the total drops below the allocated non-principal stock it shows a negative principal quantity with no rebalancing.
- [x] ERR95 — [stock] `ProduitSerializer` uses `fields='__all__'` with a runtime `prix_achat` pop keyed on permission (`stock/serializers.py:48-100`): correct today, but any new sensitive field is exposed by default — fragile vs the prix_achat-never-client-facing law. Use an explicit allowlist like the export path.
- [x] ERR96 — [frontend] The DataTable default `getRowId` mixes a page-local index for keys with a global index for `selectedRows` (`ui/datatable/useDataTable.js:117-121` + `DataTable.jsx:427-428`): rows without an `id` select the wrong rows for bulk actions/export — a latent footgun (every current caller passes an explicit `getRowId`).
- [x] ERR97 — [frontend] `datatable/csv.js`'s `escapeCSVCell` does RFC-4180 quoting but no formula-injection guard for `=` `+` `-` `@` (`ui/datatable/csv.js:14-21`): low-risk client-side export, but add a leading-quote guard.
- [x] ERR98 — [frontend] `ProduitForm` `prix_vente` validation accepts 0 and negatives (`pages/stock/ProduitForm.jsx:297`): a zero/negative sale price is sent to the server (the margin indicator flags it but doesn't block submit).
- [x] ERR99 — [frontend] `StockList` reads `r.data.results ?? r.data` without the `?? []` fallback used elsewhere (`pages/stock/StockList.jsx:718-721`): a 204/empty response throws a TypeError (swallowed → silently empty).
- [x] ERR100 — [frontend] `ProductionPage.reloadReadings` (from addReading/syncNow) fetches with no cancellation guard (`pages/monitoring/ProductionPage.jsx:64-91`): switching the selected system right after adding a reading can land a late response and overwrite the wrong installation.
- [x] ERR101 — [frontend] `RolesManagement` reassign-on-blocked-delete requires both `users_count>0` and `role.users?.length>0` (`pages/admin/RolesManagement.jsx:308`): if the list serializer omits the nested `users` array, the documented reassignment dialog never appears.
- [x] ERR102 — [frontend] Several parametres section name inputs are uncontrolled `defaultValue` with stable keys + a post-mutation `load()` (Checklist/Kits/ShotList/Avance/Leads/SecuriteTerrain sections): a server-normalized rename keeps showing the un-normalized text until remount.
- [x] ERR103 — [frontend] `MaJourneePage` renders the flow sheet from a stale `active` snapshot captured at tap time (`pages/installations/MaJourneePage.jsx:110-117`): in-sheet status/photo changes don't reflect until reopen (InterventionsPage solves the analogous case).
- [x] ERR104 — [frontend] `NotificationBell` optimistically marks read in `.finally()` regardless of server outcome (`components/layout/NotificationBell.jsx:80-91`): a failed `markRead` still drops the counter until the next poll self-heals.
- [x] ERR105 — [frontend] `InlineEdit` resets `draft` to `value` while not editing on save failure (`components/InlineEdit.jsx:30-44`) — dead state; confirm the rollback display is correct.
- [x] ERR106 — [frontend] `lib/format.js`'s `toNumber` strips a dot followed by exactly 3 digits as a thousands separator (`lib/format.js:18-23`): a technical decimal like `1.234` silently becomes `1234` if ever used on non-money values.
- [x] ERR107 — [frontend] Per-line vs total rounding can disagree by 1 MAD on the devis screen (`features/ventes/autoQuote.js:34` + DevisGenerator totals): screen-only (the backend PDF is authoritative).
- [x] ERR108 — [frontend] `Login`'s `BouncingBackground` captures window W/H once with no resize listener (`pages/Login.jsx:50-104`): blobs drift offscreen on resize/rotate until reload (cosmetic).
- [x] ERR109 — [web] The `*.workers.dev` 301 redirect applies to all methods incl. POST (`apps/web/worker/redirect-entry.mjs:17-25`): a `POST /api/simulate` to the workers.dev host gets a 301 (body may be dropped). Use 308 or skip `/api/*`.
- [x] ERR110 — [web] The lead webhook uses a static `x-webhook-secret` with no HMAC/timestamp/nonce (`apps/web/src/lib/lead.ts:160-186`): by design per the receiver, but unsigned bodies allow replay if the secret leaks.
- [x] ERR111 — [web] The CAPI relay receives un-hashed phone/city PII (`apps/web/src/lib/lead.ts:204-214`): confirm the downstream relay SHA-256-hashes before sending to Meta.
- [x] ERR112 — [web] The public lead endpoint has no rate limit/CAPTCHA (`apps/web/src/pages/api/simulate.ts`, `preview-lead.ts`): scriptable spam into the CRM/CAPI/WhatsApp pipeline.
- [x] ERR113 — [web] `roof.ts`'s `annualSavingsBandMad` uses a flat 1.4 MAD/kWh tariff with no bill cap (`apps/web/src/lib/roof.ts:162-168`): can overstate savings for low-consumption roofs (preview-only tool).

---

- [ ] ERR114 — [ventes/quote_engine] **Le PDF premium 'full' résidentiel déborde sur 4 pages dans l'image prod (contrat = 3 pages exactement)** — trouvé par le nouveau test golden YTEST10 à son premier run. REPRO (prouvée 2026-07-10, images `taqinor-django-prod:latest` ET `erp-agentique-django_core:latest`) : rendre `BASELINE_CASES[0]` ('residentiel_full', FULL_LINES 10 lignes, mêmes lignes que `test_quote_engine.test_premium_pdf_is_exactly_three_pages`) via `_render_pdf_bytes` → 4 pages ; la page 4 ne contient QUE le bloc CTA e-sign (« Prêt à passer au solaire ? / Signez en ligne → taqinor.ma/signer/… / Scannez pour signer », introduit par XSAL16) + la ligne légale — un débordement du bas de la page 3 (`residential/trust.py`). Le test canonique passe en CI (polices ubuntu ≠ polices image prod) donc la CI ne le voit pas : LES CLIENTS REÇOIVENT AUJOURD'HUI un PDF 4 pages dont la dernière est quasi vide. FIX attendu : resserrer le layout de `residential/trust.py` (ou déplacer le CTA) pour retenir exactement 3 pages DANS L'IMAGE PROD (vérifier avec la repro ci-dessus, pas seulement en CI), sans casser les autres formats ; puis générer le baseline manquant `residentiel_full_p1..p3.png` via `manage.py update_pdf_baselines` (image prod) et le committer. Rule #4 : édition du moteur autorisée pour un fix ; ne toucher à aucun statut. (@lane: backend/ventes-pdf)

## GATED — needs founder decision before fixing (agent does NOT auto-build)

Move any task here with a `[BLOCKED: <reason>]` tag when fixing it would require a
destructive migration, a new external dependency, an auth/cost policy change, or a
conflict with a non-negotiable rule. (none yet)

---

## AUTOPILOT INTAKE LOG (the error-autopilot appends one line per run)

The daily error-autopilot (`.claude/skills/error-autopilot/SKILL.md`) appends
one dated line per run summarising how many NEW verified `ERR` items it filed
into the BUILD QUEUE above (a run that finds nothing verified appends nothing
and makes no commit). Fixing those items stays the job of `work on error plan`.

- *(intake log started 2026-06-21 — daily autopilot now files verified items here.)*

---

## DONE LOG (agent appends one plain-language line per fixed task)

- *(seeded baseline 2026-06-20 — backlog created from the read-only 11-lane audit of `main` @ 98e9d23.)*
- 2026-06-20 — **Full drain: all 113 ERR tasks fixed** across 19 commits, run in parallel lanes (16 lanes over two waves of worktree/main-checkout subagents + adversarial central review). CI gates green on the consolidated tree: backend 1282 tests OK, backend flake8 clean, frontend lint (0 errors) + 200 node tests + build, web tsc + 2276 vitest + astro build.
- ERR1-3,18-20,42-44,84-86 — FastAPI: parser-based single-SELECT enforcement, fail-closed tenant isolation, read-only-role plumbing, JWT `exp` required, prix_achat blocked at query layer, CORS/docs fail-closed, no sample rows, require company_id, no SQL disclosure, gated boot DDL, rate-limit fail-closed.
- ERR4-5,21-22,45,87-88,92 — auth/roles: `is_responsable` now capability-based (read-only roles excluded), role-escalation guards, company/tier-checked role assignment, prod cookie/HSTS/SSL hardening, explicit CSRF stance, 30-min access token, seed_demo prod guard, authoritative login-audit username.
- ERR7-8,13-16,33-36,71-74 — ventes: cross-tenant line/FK validation, decimal qty, option-aware billing, accepter status guard, loud avoir errors, idempotent PDF task, level-by-level dunning, quantized devis TVA, locked payment, owner-scoped relevé, no-persist /proposal GET.
- ERR9,40-41,80-83 — installations/sav: contract tenant checks, status-transition stamping, decimal consumption (note: MouvementStock.quantite stays IntegerField — true fractional stock needs a future decimal migration), stock floor guards, POST+idempotent tool_return, double-booking detection, TZ-aware contract dates.
- ERR10,23-24,54,93-95 — stock: movement quantity validation + SORTIE floor, atomic select_for_update, ceil decimal needs, company in unique_together + non-negative constraint (migration 0022), clamped principal, explicit serializer allowlist.
- ERR6,48-49,90 — automation: recursion guard, company-scoped target lookup, honest SEND_EMAIL status, TZ-aware overdue date.
- ERR11,38-39,77-79 — crm: xlsx formula-neutralization (moved to the shared `records.xlsx` builder so ALL downloaded exports are protected), atomic client resolve, GPS range validators (migration 0020), full merge field set, id coercion → 400, webhook null-guard.
- ERR17,37,75,76 — quote_engine (premium edit-ban lifted by founder): thread-safe render lock, HTML-escaped user text, company-scoped legacy key, clamped custom acompte.
- ERR25,47,55-57 — parametres/records/reporting/monitoring: read-only company FK, threshold/JSON validation, clean resolve_target errors, zero-threshold low-stock exclusion, atomic underperformance flag.
- ERR46,50-53,89,91 — publicapi/dataimport/notifications: SSRF allowlist (write + delivery), atomic import + opening-stock audit + size/row caps, no-store reveal headers, bounded notification body, and **ERR50 wired** (LEAD_ASSIGNED + DEVIS_ACCEPTED producers; FACTURE_OVERDUE left as a scheduled-job follow-up).
- ERR12,26-31,58-69,96-108 — frontend: BCF reception source, ajustement-zero, map-popup XSS escaping, role/permission route guards, never-reject-number forms, optimistic-write rollback/toasts, mic-stream cleanup, French error messages, datatable row-identity, CSV/format/number safety, stale-response guards. (ERR30 was already fixed in-tree — verified, no change.)
- ERR32,70,109-113 — web: redacted lead-PII logs, slash-consistent hreflang, 308 method-preserving redirect, SHA-256 CAPI hashing, in-memory rate limit, bill-capped savings.
