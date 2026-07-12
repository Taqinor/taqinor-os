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

### Group QJ — Quote-journey best-in-world (ERP backend + frontend; research-driven, 2026-06-24)

*From a June-2026 deep audit of TAQINOR's quote journey (website pin+bill capture → CRM lead →
seller designs the roof in 3D → premium quote → tokenized web proposal + e-sign) against the best
solar platforms in the world (Aurora, OpenSolar, Solargraf, Pylon, Tesla, Otovo, Demand IQ, Solo,
EnergySage, Bodhi) + Morocco market + conversion-science research. These are the **ERP half**; the
matching website tasks are **WJ1–WJ24 in `docs/WEB_PLAN.md`** (cross-referenced per task). Goal: make
the journey the best in the world for the CLIENT and the COMMERCIAL user.*

> **Constraints (every QJ task).** Rule #4 status preservation (the quote engine only RENDERS; the
> document chain `brouillon→envoye→accepte…` + BonCommande/Facture preserved 1:1; `/proposal` stays
> the only client PDF path). STAGES.py keys imported, never hardcoded. All migrations
> additive/nullable + company-scoped server-side (never trust `company` from the body). Cross-app
> reads/writes go through `selectors.py`/`services.py` + the `core/events.py` bus — never another
> app's models/views. **Savings stay self-consumption-first (loi 82-21): value only self-consumed
> kWh; the surplus-injection line stays OFF until the founder confirms ANRE's BT residential
> net-billing tariff (unpublished).** A simple typed-name e-signature is legally valid in Morocco
> (loi 53-05/43-20) — harden the evidence, no certified provider required for ordinary sales.

> **Three gated items need a founder-provisioned account/credential (→ NEEDS YOUR INPUT, build the
> rest):** QJ23 (WhatsApp Business API / BSP), QJ24 (CMI/PayZone payment merchant), QJ25 (paid
> imagery provider or self-built roof segmentation). The Meta CAPI *send* in QJ9 stays gated on
> Reda's Meta token (everything up to the send is buildable).

**A — Speed-to-lead, follow-up & engagement tracking (the highest-ROI cluster):**

**B — E-signature strength & proposal data:**

**C — Commercial-user efficiency:**

**D — Gated (need a founder-provisioned account/decision → NEEDS YOUR INPUT; build behind a flag):**

**E — Client 3D proposal, superior notifications & multi-property quotes (founder request 2026-07-01):**

*From Reda: (1) when the client opens the returned quote he must see HIS OWN HOME in interactive 3D with the panels (zoom/rotate) — the web viewer is WEB_PLAN WJ25–WJ28, this QJ26 is the backend unlock; (2) when the client asks to be contacted, the lead's HANDLER and the handler's SUPERIOR must both be notified; (3) a « contacter mon supérieur » button on quote generation notifies the creator's superior; (4) support multi-villa quotes — multiply one villa ×N (identical) OR add different villas one by one, all in ONE quote document. Research confirmed the pieces exist: `CustomUser.supervisor` self-FK (added 2026-06-18), `Lead.owner` (handler), `Devis.created_by` (creator), the `notify()` service + extensible EventType (QJ2), and the `roof_layout` JSON already stored on the Devis — the public proposal payload just doesn't expose it, and no server-side contact-request endpoint exists yet.*


#### DONE LOG — Vague 2 (VX terrain/finance/CRM + QX groupe) (2026-07-12)

Vague 2 du plan-run (23 tâches VX + tagging de tous les plans, un seul merge). Lanes drainées en parallèle : **finance/terrain** VX44 (photos chantier en rafale + partage WhatsApp), VX88 (Ma journée → tournée géo), VX94 (Enter-pour-ajouter capture), VX105 (statut technicien + persistance + toasts hors-ligne), VX106 (signature client terrain), VX107 (résumé client lecture seule), VX52 (avertissements conformité tactiles), VX63 (erreurs FR lisibles DevisList/FactureList), VX114 (déjà présent, export daté), VX116 (relance groupée + aperçu WhatsApp). **ventes** VX222 (relancer devis), VX230 (encaisser depuis Relances), VX231 (navigation finance vers la cible). **UI/data** VX41 (data-viz marque + comparaison période), VX33 (Pilotage stock tour de contrôle), VX66 (anti-double-soumission Button), VX26 (couleurs stage dérivées tokens), VX81 (exports XLSX/CSV horodatés), VX61 (Web Vitals réels + endpoint reporting), VX110 (copier TSV), VX246 (queue interop iOS), VX19 (zéro popup navigateur, +réparation FactureList post-refactor VX230). Backend DoD à suivre : VX105 (`ajouter-reserve` gated admin), VX106 (signature dans `intervention_pdf.py`). GATED (non buildé) : QXG1/QXG2/QXG4 (compte/contenu fondateur). Tagging : les 10 fichiers de plan (PLAN/PLAN2/new_tasks + 7 domaines) reçoivent un tag `@lane:`/`Files:` visible par le planner sur la 1ʳᵉ ligne (append-only vérifié).

#### DONE LOG — Vague 1 (VX beauté/robustesse/pardon + seams) (2026-07-11)

Vague 1 du plan-run (66 tâches, un seul merge). VX design/marque : VX1-7 (jetons or/navy, sidebar/header, typo, dark mode, num tabulaires, radii/liseré, listes calmes), VX27/VX28/VX36 (cockpit par rôle, langage graphique unique, onboarding). VX robustesse/seams : VX62/VX90 (brouillon auto + focus ligne), VX68/69/70 (e2e mobile-safari/tablette/zoom/visuel), VX140/142/188/216 (DevisList/FactureList densité + DevisLineRow mémoïsé + seams devis↔chantier), VX192/221 (kanban a11y + score expliqué), VX199 (fix sur-permission `IsResponsableOrAdmin`→`ventes_valider`/`crm_modifier`). VX CRM : VX22-25/45/87/89/111 (route lead dédiée, ChatterTimeline, carte kanban 2 niveaux, MonthGrid, microcopie, CallLogPopover, dialog Escape, pièce jointe note). VX pardon/shell : VX91/93/97/98 (ProduitPicker+quick-create facture, smart defaults, historique modifs, puce fraîcheur + journal), VX14/56/82 (onglets NotificationBell, polling visibilité, titres d'onglet). VX admin/reporting : VX29/38/40/47/103/104 (dashboard commercial, ports DataTable, célébration devis signé, HelpTip contextuels, délégations absence, superviseur direct). VX227/251 (seams achat↔chantier, tableau dispatch drag-drop). Déjà présents : VX160.

#### DONE LOG — QJ batch (2026-06-25)

All 25 QJ tasks built, locally validated against Postgres+MinIO, and merged in one batch.
- QJ1 — ShareLink open-tracking (first_viewed_at/view_count/last_viewed_at, chatter event, devis-list badge). SCHEMA: ventes 0030.
- QJ2 — Instant seller notifications on new-lead / first-open / e-sign acceptance (in-app + Web Push + wa.me link). NEW EventTypes lead_new/devis_opened (notifications 0009).
- QJ3 — Already present (Celery beat scheduler from G9/N76); no rebuild.
- QJ4 — Automated devis follow-up cadence (j+2/5/10, FR+AR, beat-scheduled, idempotent). SCHEMA: ventes 0035 DevisNudgeLog.
- QJ5 — Auto quote-expiry (envoye→expire) + funnel hygiene (QUOTE_SENT→FOLLOW_UP→COLD), beat-scheduled, no-regress guards.
- QJ6 — Rule-based lead scoring + hot-list sort. SCHEMA: crm 0026 Lead.score.
- QJ7 — Auto NEW→CONTACTED on first contact (events bus, idempotent).
- QJ8 — Webhook dedupe beyond 60 s (email/phone fingerprint, cross-company safe).
- QJ9 — First-touch UTM/fbclid copied at signature (lossless) + Meta CAPI SignedQuote wired. AUTH/DEP: CAPI send GATED on META_CAPI_ACCESS_TOKEN/META_CAPI_PIXEL_ID.
- QJ10 — Immutable e-sign record (loi 53-05: UA+content hash+consent+IP+ts) + locked-PDF email, best-effort. SCHEMA: ventes 0031.
- QJ11 — Toggleable OTP confirmation before acceptance (ESIGN_OTP_ENABLED, default OFF = unchanged).
- QJ12 — Indicative financing block in the quote (cash vs green-loan vs ONEE, Tatwir/ISTIDAMA), flagged « indicatif ».
- QJ13 — Self-consumption-first 82-21 savings + ONEE/Lydec/Redal tranche tables; surplus-injection kept OFF; no invented numbers.
- QJ14 — Server-side « Envoyer par e-mail » (PDF + tokenized link + EmailLog), marks envoye via status service.
- QJ15 — Quote size-variants (dupliquer-variante) + side-by-side comparison.
- QJ16 — Reusable quote presets (DevisPreset save/apply + ViewSet). SCHEMA: ventes 0033.
- QJ17 — from-layout idempotency (lead+layout hash) + pre-flight composition check (422, no PDF 500). SCHEMA: ventes 0034 layout_hash.
- QJ18 — Commercial dashboard (funnel %, time-in-stage, velocity, win rate, seller leaderboard).
- QJ19 — Win/loss + close-rate-by-source report.
- QJ20 — Self-booking site-visit scheduler + reminder (beat), Ramadan-aware pacing flag. SCHEMA: crm 0027 Appointment.
- QJ21 — Richer layout fidelity (full multi-pan geometry + per-pan azimuth in roof_layout).
- QJ22 — Signed-proposal PDF artifact + prominent « Proposition signée » surfacing + seller notification.
- QJ23 — WhatsApp Business API SCAFFOLD (flag-gated, default manual wa.me). DEP/COST: live BSP send GATED on a founder BSP account + Meta-verified number. SCHEMA: notifications 0008.
- QJ24 — Online deposit SCAFFOLD (acompte calc + CMI/PayZone provider seam, flag-gated). DEP/COST: live deposit GATED on a founder merchant account; accept-flow wiring is a follow-up.
- QJ25 — Built FREE per founder: OSM/Overpass building-footprint auto-detection from the client's pin (no key, no cost). Automatic OBSTACLE detection stays out of scope (needs paid imagery).

---

### Group QW — Quote-journey wiring completion: catch the signals the site already sends (founder forensic audit, 2026-07-05)

*A 6-agent read-only forensic audit of the whole web→ERP quote journey found the pattern behind
"it's a mess": the website half (WEB_PLAN WJ39–94) shipped and diligently SENDS the signals, but
the ERP RECEIVERS were never built — so ~10 capture fields, the "call me" preference, and every
proposal-stage callback/question/revision request are silently DROPPED. This group builds the
receiving half. The website-side counterparts are **WEB_PLAN WJ95–WJ107** (cross-referenced per
task). Callback alerts use FREE in-app + email now (founder decision 2026-07-05); the
automated-WhatsApp-send path stays behind the existing QJ23 flag. Do NOT touch the `/proposal` PDF
engine (rule #4).*

> **2026-07-05 Fable completeness-critic pass — CORRECTIONS + additions (all verified against real code).**
> The critic corrected two things in this group and found a live bug + more gaps: (1) the
> proposal-contact/OTP endpoints ALREADY EXIST at the `public/` mount — QW5 is an ALIAS + contract fix,
> NOT a rebuild; the client does NOT see a false success (an honest "Service momentanément indisponible"
> shows on failure). (2) **QW7 is a LIVE data-corruption bug** — the proposal-view beacon overwrites real
> lead names with "Lead site web". (3) QW8 — QW4's email leg is config-dead by default. (4) QW9/QW10 —
> webhook replay + dedup hardening. QW2 amended (reuse `Lead.societe`, add more dropped keys).

- [x] QW7 **(already present)** — **[LIVE BUG] Stop the proposal-view beacon corrupting real leads.** **[Founder decision 2026-07-05: the corruption is being fixed at the WEB SOURCE via WEB_PLAN WJ109 (auto-deploys, no ERP deploy). This backend QW7 is now an OPTIONAL defensive backstop — do NOT prioritize/deploy it just for this bug; WJ109 already stops it. Keep only as belt-and-suspenders webhook hardening.]** `apps/web/src/pages/api/proposition-track.ts` POSTs engagement pings (`event_type`, `phoneE164`, `qualified:false`, `utm_source:'proposal_engagement'`) to the SAME CRM lead webhook. `_map_payload_to_fields` ignores `event_type`, sets `nom='Lead site web'` (no fullName — `webhooks.py:182`) and `tags='Sous le seuil 1 000 MAD'`; the layer-2 dedup then finds the real lead by phone and the update loop writes every non-empty value (`webhooks.py:373-383`) — so a client merely OPENING their proposal OVERWRITES their real lead name with "Lead site web" and stamps it below-threshold. Fix: when `event_type` is present, log ONLY a chatter note + notification on the matched lead (by phone, company-scoped) and SKIP the field merge entirely — never write nom/tags/utm/canal from an engagement ping, never create a Lead from one. Also fix the merge-loop contract (the comment `webhooks.py:369-371` claims "sans jamais écraser" but non-empty values DO overwrite — at minimum never overwrite a real `nom` with the `'Lead site web'` fallback; add a regression test). **Done =** an engagement ping never mutates a lead's nom/tags/attribution and never creates a lead; a real capture still does; tests cover both. Files: `apps/crm/webhooks.py`, `apps/crm/tests_webhook.py`. (ROUTINE — note in DONE LOG; this is a live data-integrity fix) (@lane: backend/crm-webhook) (@after: QW1)
- [x] QW8 — **Make QW4's email leg actually fire (today it's config-dead by default).** `is_email_configured()` gates on `settings.ANYMAIL.get('BREVO_API_KEY')` (`email_service.py:39`) but `ANYMAIL` only ever holds `SENDGRID_API_KEY`/`SENDINBLUE_API_KEY` (`settings/base.py:287-290`) — that key check is dead; email works only if `EMAIL_BACKEND` is an explicit non-console backend (`email_service.py:41-51`). AND `notifications.services.DEFAULT_PREFS['email']=False` (`services.py:31-35`) — so even when configured, `notify()` won't email a user without a `NotificationPreference` opt-in. Fix: correct the key lookup (honor `SENDINBLUE_API_KEY`/`SENDGRID_API_KEY`), default the email channel ON for the callback event type (per-event override or a `NotificationRoutingRule`), document the required prod env (`EMAIL_BACKEND` + `BREVO_API_KEY` + `DEFAULT_FROM_EMAIL`), and add a test asserting a phone_ok callback produces an outbound `EmailMessage` when configured. **Done =** a configured prod fires the callback email; a test proves it; docs updated. Files: `apps/ventes/email_service.py`, `apps/notifications/services.py`, `docs/production.md`, tests. (ROUTINE — note in DONE LOG) (@lane: backend/crm-callback) (@after: QW4) **Why:** the founder chose "free email now" — without this the email silently no-ops.

---

### Groupe QX — Quote journey best-in-world ROUND 6: verified defects + conversion loop (2 audit rounds × 24 agents, adversarially verified + Fable design pass, 2026-07-10)

*A 2-round deep audit of the whole web→ERP quote journey (10 code lanes + 4 researchers, then 10
adversarial verifiers + Fable completeness critic + Fable target-state designer). 52 of 53 round-1
findings were CONFIRMED or PARTIAL under adversarial re-verification against real code; every task
below carries a verified fix spec. Three cross-cutting truths the whole group serves: (1) there is
NO single owner of the money number — six independent computations of a quote's value coexist and
three ignore `remise_globale`; (2) the dominant failure mode is UNWIRED features — built, tested,
then never scheduled/routed/linked; (3) client-facing URLs are minted ad hoc with two confirmed
404s at moments of maximum client intent. Rule #4 intact throughout: PDF fixes go INSIDE the
vendored engine; the engine only renders. Research anchors: Storydoc 1.3M sessions (82% of opens
happen <1h; 46% of signers sign <48h of open; losing proposals get viewed 3.5×), Proposify 2025
(e-sign path = 4× close, images +72%), MIT/Oldroyd speed-to-lead (21× qualification <5 min).
E-signature legal basis: cite **Law 43-20 (2020, BO n°6970 2021)** which superseded loi 53-05.*

**A — ONE MONEY MODEL (the critical: client sees discounted TTC, is billed full price)**
- [x] QX1 — **[CRITICAL] `remise_globale` reaches the ENTIRE billing chain.** Verified end-to-end trace: the discount is applied on the client-facing path (`quote_engine/builder.py:534-585` canonical HT→remise→TVA→TTC, `public_views.py:400-403`) and DROPPED by every billing consumer: `Devis.total_ht/tva/ttc` (`apps/ventes/models.py:199-230` — pure line sums), `utils/options.py:83-104 option_totaux` (BOTH branches), `utils/echeancier.py:129-147` + `:208-210` (acompte/matériel/solde tranches billed on the undiscounted total), `views/bon_commande.py:379-397 creer_facture` (copies lines, drops the global discount; `Facture.remise_globale` field exists at `models.py:650` but is NEVER read in `Facture.total_*`), and `templates/pdf/bon_commande.html:143-161` (VISIBLY shows a remise line then bills the full pre-discount TTC — an internally-inconsistent over-billing document; on a 200 000 MAD quote at 15% remise the client is over-billed ~30 000 MAD). Fix: route `option_totaux` through `selectors._canonical_totaux(lines, remise_globale_pct=devis.remise_globale, fallback_taux=devis.taux_tva)` in BOTH branches so échéancier/solde/BC inherit the discount; set + read `Facture.remise_globale` on the BC→facture path (or distribute the discount into copied line prices); fix `bon_commande.html` to treat the passed totals as already-net (pass gross+net so the remise line = the delta). CAUTION (verified): do NOT naïvely change `Devis.total_ht` semantics — the BC template re-applies remise on top of it today (double-subtract risk); land template + consumers together. **Done =** regression test asserting quote PDF total == BC total == Σ échéancier factures == accepted-option discounted TTC to the centime, for both 1-option and 2-option quotes, with and without per-line remise. Files: `apps/ventes/utils/options.py`, `utils/echeancier.py`, `views/bon_commande.py`, `templates/pdf/bon_commande.html`, `apps/ventes/models.py`, tests. (ROUTINE — data-integrity fix; note in DONE LOG) (@lane: ventes-money)
- [x] QX2 — **Fix the discount's OTHER consumers: founder KPIs, Meta CAPI value, DGI/UBL export.** Verified: `apps/reporting/commercial.py:221` + `apps/reporting/insights.py:676` aggregate leaderboard/CA on undiscounted `Devis.total_ht` (the founder steers on inflated revenue); the Meta CAPI conversion value uses undiscounted `devis.total_ttc` (mis-scaled on 2-option quotes); `apps/ventes/utils/ubl.py:120-141` builds `LegalMonetaryTotal` from the same undiscounted chain — a BLOCKER for ever arming `CompanyProfile.dgi_export_actif` (DGI clearance model pre-validates amounts with the tax authority; the SME/TPE phase hits 2027-01-01). Fix all three to consume the canonical discounted total (accepted option where applicable). **Done =** leaderboard CA == accepted discounted totals (test); CAPI value == display total; UBL `PayableAmount` == discounted TTC (test). Files: `apps/reporting/commercial.py`, `apps/reporting/insights.py`, CAPI emitter in `apps/crm` or `apps/ventes`, `apps/ventes/utils/ubl.py`, tests. (ROUTINE) (@lane: ventes-money) (@after: QX1)
- [x] QX3 — **[CRITICAL] Fail-closed payments: no free "PAID".** Verified reachable in prod: `erp_agentique/urls.py:50` mounts `public_urls` unconditionally; `PaymentLink.provider` defaults `'noop'` everywhere (`models.py:1974`, `services.py:2373`, `email_service.py:259`, `views/facture.py:930`); `NoOpProvider.verify_webhook` (`apps/ventes/payments/providers.py:91-105`) returns `{'paid': True}` for ANY payload — so `POST {}` to `/api/django/public/pay/<token>/webhook/` records a fabricated `Paiement`, flips the Facture to PAYEE and fires `facture_paid`. Fix: NoOp returns `paid: False` (mirror `HostedGatewayProvider`'s no-credentials branch); `montant` must come from server-side `link.montant`, never the payload; per-token throttle on the webhook. **Done =** unauthenticated `POST {}` can never mark a facture paid (test); a real provider path still works. Files: `apps/ventes/payments/providers.py`, new test. (ROUTINE — security fix; note in DONE LOG) (@lane: ventes-pay)

**B — THE CLIENT PDF (rule #4 — all fixes INSIDE the vendored engine)**
- [x] QX4 — **[CRITICAL] De-Taqinorize the residential renderer (multi-tenant identity leak).** The DEFAULT residential proposal hardcodes TAQINOR's legal identity for every tenant — verified inventory: `residential/theme.py:246` (footer TAQINOR·email·phone), `theme.py:50` (bundled logo), `trust.py:228-232` (legal band: TAQINOR Solutions SARLAU / capital 100 000 MAD / RC 691213 / ICE 003799642000067 / « Gérant : M. Reda Kasri »), `trust.py:363` (« Pourquoi TAQINOR »), `trust.py:403` (signature block), `cover.py:292/317/354`, `renderer.py:72-76` (taqinor.ma links), plus `theme.py:164-200` + `options.py:33/51/71/144` (`produits_base='taqinor.ma/produits'`). The legacy engine is already tenant-aware via `_apply_entreprise` (`generate_devis_premium.py:335-431`) — the DC1 fix never reached the residential renderer. Fix: thread `data['entreprise']` into `build_ctx` and drive every identity literal from it, falling back to the current literals ONLY when empty (mirror `_apply_entreprise` exactly); add `CompanyProfile.capital` + `CompanyProfile.gerant` (additive migration) for the two facts with no home. **Done =** rendering the residential PDF for a second Company shows THAT company's identity everywhere (test greps rendered HTML/PDF context); Taqinor output byte-equivalent-in-content for Taqinor. Files: `quote_engine/residential/{render,renderer,theme,trust,cover,options}.py`, `apps/parametres` (CompanyProfile migration), `apps/ventes/tests/test_quote_engine.py`. (SCHEMA — additive migration; note in DONE LOG) (@lane: quote-engine)
- [x] QX5 — **Never print a phantom option: gate the two option cards on the real scenario.** Verified: a battery-only/hybrid residential quote prints a fabricated cheaper « Option 1 — Sans batterie » missing the inverter, on page 1 (`residential/cover.py`) AND page 2 (`residential/options.py:364` fixed « Équipement commun aux deux options » heading, `:378-391` both delta cards, `:150-156`+`:397-400` both totals chains — all unconditional). Fix: thread `data['scenario']`/`sans_ok`/`avec_ok` flags (already locals in `builder.py`) into the renderer; single-option quotes render ONE full-width card, page 2 drops the delta split and renames the heading. **Done =** battery-only quote shows exactly one option everywhere; 2-option quotes unchanged; page-count tests still pass. Files: `quote_engine/residential/{renderer,render,cover,options}.py`, `builder.py`, tests. (ROUTINE) (@lane: quote-engine)
- [x] QX6 — **Fix the strongest CTA: PDF sign QR → live proposal; real page numbers.** Verified: the QR/« Signez en ligne » points at invented `taqinor.ma/signer/<ref>` (404, `residential/renderer.py:71-77`) and the footer hardcodes « Page X / 3 » (`theme.py:247`). Fix: in the builder, mint/reuse `ShareLink.for_devis(devis)` and set `data['links']['signer'] = f"{SITE_URL}/proposition/{token}"`; footer uses the real rendered page total; drive `produits_base`/realisations/avis links from company `site_url` (suppress when absent). Proposify 2025: an e-sign path = 4× close rate, 40% faster. **Done =** QR on a fresh residential PDF opens the live tokenized proposal; no hardcoded page count. Files: `quote_engine/builder.py`, `residential/renderer.py`, `residential/theme.py`, tests. (ROUTINE) (@lane: quote-engine) (@after: QX4)
- [x] QX7 — **PDF numbers honesty pack.** Verified defects, all in-engine: (a) coverage donut fabricates a plausible figure — floored 40 / capped 99 with an invented `/1.3` divisor (`residential/renderer.py:56-57`) → compute from real annual consumption via a thin crm selector when bills exist, honest « estimation » label otherwise, drop the floor; (b) `custom_acompte` clamp prints a dead 0% « Matériel » box with mislabelled percentages (`generate_devis_premium.py:~1620-1668`) → collapse to a two-box schedule summing to 100%; (c) `client_city` read but never set (`cover.py:59`) → resolve from `lead.ville` or drop the dead field; (d) TWO avoided-kWh prices contradict each other on one proposal (`constants.KWH_PRICE=1.75` in `public_views._monthly_consumption` vs the ROI `tarif_kwh` ~1.20/tranche) → thread the ROI tarif everywhere; (e) equipment-brand chips claim « Canadian Solar · Huawei · Deye » + « 3 000 h/an » + « 87,4 % » regardless of the quote's real lines (`trust.py:106/116-121`, `generate_devis_premium.py:1434`) → derive brands from the quote's real `item['marque']` values (fallback « équipements certifiés IEC »), make the marketing figures tenant-editable copy. **Done =** each sub-item has a test; no fabricated number survives. Files: `quote_engine/residential/{renderer,cover,trust}.py`, `generate_devis_premium.py`, `builder.py`, `apps/ventes/public_views.py`, tests. (ROUTINE) (@lane: quote-engine) (@after: QX4)
- [x] QX8 — **Engine warm path: stop re-doing pure work per render.** Verified: per-render font/logo reload incl. a per-pixel logo recolor loop + 4 matplotlib charts, serialized under one global lock — a burst of clients opening proposal links queues single-file. Fix: `functools.lru_cache` the recolored-logo b64 + font-face CSS (`residential/theme.py` — pure functions); cache rendered PDF bytes keyed by the existing render-fingerprint (complements the queued ERR74 /proposal-persist fix — do not duplicate it); shrink the global-lock surface where safe. **Done =** second render of an unchanged devis skips font/logo/chart work (timed test or call-count assert); output byte-identical. Files: `quote_engine/residential/theme.py`, `quote_engine/builder.py`. (ROUTINE) (@lane: quote-engine)

**C — E-SIGN & ACCEPTANCE (the decision moment)**
- [x] QX9 — **Real e-sign evidence + the promised signed PDF (Law 43-20).** Verified end-to-end: the canvas signature (`[token].astro:2650` `canvas.toDataURL`), `consent_esign`, `signed_at_client` and `on_behalf_of` travel through `proposition-accept.ts:85-102` and are ALL discarded by `public_views.proposal_accept:743-789` (reads only nom/option/`consentement` — a key the frontend never sends, so consent silently defaults True; `DevisSignature` has no fields for any of it). AND the confirmation email promises « ci-joint votre exemplaire signé » but frequently ships without it: `accept_devis` holds a stale in-memory Devis while `_store_signed_pdf` persists `fichier_pdf` on a SEPARATE instance (`services.py:1238` vs `builder.py:1257-1259`), and the blank-attachment branch logs nothing (`email_service.py:93-95`). Fix: additive migration on `DevisSignature` (`signature_image` stored to MinIO or TextField data-URL, `consent_esign` bool, `signed_at_client`, `on_behalf_of`); `proposal_accept` reads the real keys and returns 400 when consent is not truthy (mirror the `nom` guard); `devis.refresh_from_db(fields=['fichier_pdf'])` before `_send_acceptance_emails`, prefer `DevisSignature.signed_pdf_key` as the attachment source, log the blank branch. **Done =** a signed acceptance persists all four artifacts (test), the confirmation email provably carries the signed PDF (test), consent is server-enforced. Files: `apps/ventes/public_views.py`, `services.py`, `models.py` (+migration), `email_service.py`, tests. (SCHEMA — additive migration; note in DONE LOG) (@lane: ventes-esign)
- [x] QX10 — **OTP: honest channel + brute-force lockout.** Verified: `_send_otp_whatsapp` (`services.py:723-737`) is a log-only stub that returns True (so enabling `ESIGN_OTP_ENABLED` today locks phone-only clients out of signing entirely), and `validate_esign_otp` (`services.py:695-720`) has NO attempt counter — 6-digit space, 10-min TTL, unlimited tries. Fix: stub returns False until a real send path exists (fallback then routes to email); per-token failed-attempt counter in cache, lockout ≥5 wrong tries (« trop de tentatives, redemandez un code »); startup/system-check warning when `ESIGN_OTP_ENABLED` is on while the WhatsApp stub is the only channel. **Done =** tests for lockout + honest-stub routing. Files: `apps/ventes/services.py`, tests. (ROUTINE) (@lane: ventes-esign)

**D — WIRE THE DEAD AUTOMATION (built, tested, never scheduled/linked)**
- [x] QX11 — **Schedule ALL built-but-dead periodic jobs + a reachability guard.** Verified sweep: 10 built periodic tasks are absent from `erp_agentique/celery.py` beat_schedule — headline: `ventes.devis_a_facturer_reminder` (ZFAC12 — « accepted but never invoiced » sits forever un-nudged) and `ventes.pre_echeance_reminders` (XFAC7); add the other verified absentees at sensible off-peak crontab slots following the file's per-app comment convention. Also switch `expire_stale_devis` (`services.py:2880`) to the Casablanca-aware date helper its siblings use. Add a GUARD TEST: every `@shared_task` that looks periodic (name-listed) is either in beat_schedule or on an explicit on-demand allowlist — so this bug class (the codebase's dominant failure mode) can never silently recur. **Done =** beat runs all 10 (test asserts schedule entries); guard test in place. Files: `erp_agentique/celery.py`, `apps/ventes/services.py`, new test. (ROUTINE — note in DONE LOG) (@lane: backend-beat)
- [x] QX12 — **Notification deep-links that actually land.** Verified: « Devis accepté »/« Devis expiré » notifications link `/devis/{pk}` — a route that doesn't exist (`apps/notifications/signals.py:94/117`), and `Dashboard.jsx:369`'s `?statut=accepte` link is equally dead because `DevisList.jsx` reads NEITHER `devis` nor `statut` search params (verified: only `variantes`/`design3d`). Fix both producers to `/ventes/devis?devis={pk}` AND teach DevisList to consume `devis` (open/highlight that quote) + `statut` (pre-set filter) on mount. **Done =** clicking each notification/dashboard link lands on the intended quote/filter (component test). Files: `apps/notifications/signals.py`, `frontend/src/pages/ventes/DevisList.jsx`, tests. (ROUTINE) (@lane: frontend-devislist)
- [x] QX13 — **Follow-up nudges the seller can actually SEE — and that respect reality.** Verified: the j+2/j+5/j+10 devis cadence's default `wa_draft` branch produces ONLY a server log line (`services.py:2803-2813`) — no Notification, no UI surface; its message embeds `taqinor.ma/proposal/<token>` which 404s (the page is `/proposition/`, `services.py:2772` — every other producer uses the right form); and the cadence is BLIND to seller/client activity (`services.py:2728-2765` — no check of manual `LeadActivity`, future `lead.relance_date`, or recent proposal engagement). Fix: (a) one-line URL fix + a SHARED client-URL builder helper used by ALL producers, with a test asserting each emitted path exists in the website's route table (two 404s were found at moments of maximum client intent); (b) `wa_draft` branch creates a real `Notification` (new `EventType`, e.g. `devis_nudge_due`) with title/body/prefilled wa.me draft + deep-link; (c) suppression rules: skip/defer a nudge level when a manual contact activity exists since the last level, `relance_date` is set in the future, or proposal engagement was recorded in the last N days. **Done =** a due nudge is visible in-app with a working link; suppression tests for all three signals. Files: `apps/ventes/services.py`, `apps/notifications/models.py` (EventType — additive), a new shared URL helper (e.g. `apps/ventes/utils/client_links.py`), tests. (ROUTINE) (@lane: backend-nudges) (@after: QX11)

**E — WEBHOOK & CRM INTAKE FIDELITY**
- [x] QX14 — **Persist `Lead.score` on webhook leads → auto-MQL finally fires for the #1 source.** Verified: EVERY other lead-creation path calls `recompute_lead_score` (views.py:561/574, services.py:1088/1366/1429/2782) EXCEPT `apps/crm/webhooks.py` (lines 595 create-branch / 620 update-branch) — the serializer recomputes for display, masking that `?ordering=-score` and `maybe_assign_mql` (XMKT21 hot-lead auto-routing) silently never work for website leads. Fix: call `recompute_lead_score(lead)` in both branches (best-effort try/except like `notify_new_lead`). **Done =** webhook lead lands with persisted score; MQL auto-assign test. Files: `apps/crm/webhooks.py`, `tests_webhook.py`. (ROUTINE) (@lane: crm-webhook)
- [x] QX15 — **Callback SLA clock measures the right thing.** Verified: `escalader_rappels_demandes` uses `Lead.date_creation` (`apps/crm/selectors.py:867`) so any old lead whose callback preference is set NOW is instantly « SLA-breached » — false-urgent noise that teaches sellers to ignore escalations. Fix: additive `Lead.contact_preference_set_at` (migration), stamped at BOTH write sites (webhook mapping + `services.py:1740-1742`); selector uses it with `date_creation` fallback. **Done =** fresh phone_ok on an old lead does not escalate (test). Files: `apps/crm/models.py` (+migration), `webhooks.py`, `services.py`, `selectors.py`, tests. (SCHEMA — additive migration) (@lane: crm-webhook)
- [x] QX16 — **« Jamais perdre un lead » becomes operational: payload replay surface.** Verified: `WebsiteLeadPayload` is write-only — no admin, no endpoint, no management command reads it; a mapping-failed payload is a silently lost customer despite the module's own guarantee (`webhooks.py:7-8`). Fix: read-only admin registration (list: company/processed/error/received_at/lead) + a small CRM surface listing failed/lead-less payloads with one-click replay through `_map_payload_to_fields` + founder notification on mapping failure. **Done =** a forced mapping failure is visible and replayable to a real Lead (test). Files: `apps/crm/admin.py`, `views.py`/serializer, small frontend list, tests. (ROUTINE) (@lane: crm-webhook)
- [x] QX17 — **Client dedup by phone, not just email.** Verified: `resolve_client_for_lead._find_existing` (`services.py:881`) matches by email only — a repeat client with no/different email gets a duplicate `crm.Client`, fragmenting history and `plafond_credit`. Fix: after email miss, match on `normalize_phone` equality within the company (Python-side compare; document the perf bound). Phone-first identity is the norm in Morocco. **Done =** same-phone lead reuses the existing client (test). Files: `apps/crm/services.py`, tests. (ROUTINE) (@lane: crm-services)
- [x] QX18 — **Arabic doesn't die at the document layer.** Verified: the AR web journey + trilingual proposal page exist, but `Lead.langue_preferee='darija'` never seeds `Client.langue_document` (default FR) — the arabophone client gets a French flagship PDF at the decision moment. Fix: `resolve_client_for_lead` seeds `langue_document='ar'` when the lead prefers darija; surface the field in the client form; (AR gloss on residential PDF headline numbers = follow-up, in-engine). **Done =** darija lead → client with `langue_document='ar'` (test). Files: `apps/crm/services.py`, `frontend` client form, tests. (ROUTINE) (@lane: crm-services)

**F — SELLER QUOTE CREATION (the generator)**
- [x] QX19 — **Auto-quote consumes everything the client already told us.** Verified: `createAutoQuote` hardcodes `structureType:'acier'` at BOTH `autoQuote.js:81` (agricole) and `:101`, ignoring `Lead.structure_pref=ALUMINIUM`; ignores `taille_souhaitee_kwc` (size from bills only) and `batterie_souhaitee`; and `solar.js autoFillLines` (~:602) silently substitutes catalogue panel wattage while the screen kWc is computed from the TYPED wattage — a 550W-for-710W substitution ships a 7.7 kWc system labelled 9.94 kWc. Fix: derive panel count from `taille_souhaitee_kwc` when set (reuse `panneauxPourKwc`); respect `structure_pref` in both branches; seed the battery scenario from `batterie_souhaitee`; surface `actualPanelW` from autoFillLines and either recompute the displayed kWc from ACTUAL lines or block with a visible warning on mismatch; harden the Huawei Smart-Meter/Dongle free-text match. **Done =** each consumed field has a test; a wattage substitution can never change kWc silently. Files: `frontend/src/features/ventes/autoQuote.js`, `solar.js`, `DevisGenerator.jsx`, tests. (ROUTINE) (@lane: frontend-generator)
- [x] QX20 — **A solar quote must contain solar equipment.** Verified: `validate()` (`DevisGenerator.jsx:935`) never requires a panel/inverter line — a « quote » of one manual line « Installation, 500 MAD » passes and can be sent. Fix: mode-specific equipment gate — résidentiel/industriel require ≥1 panel line AND ≥1 inverter line (classification helpers exist in solar.js); agricole requires a pump; clear French error naming what's missing. **Done =** zero-equipment quote blocked with explicit message (test); legitimate edge cases (accessories-only avenant) get a documented escape hatch decision. Files: `frontend/src/pages/ventes/DevisGenerator.jsx`, `frontend/src/features/ventes/solar.js` (export `isPompe`), tests. (ROUTINE) (@lane: frontend-generator)
- [x] QX21 — **Atomic quote save (create AND edit) + honest PDF progress.** Verified: creation is 1+N unguarded round-trips (`DevisGenerator.jsx:1026`) leaving invisible orphan/partial brouillons a seller can later send; the EDIT path is worse — delete-all-lines with swallowed errors THEN recreate (`:1015-1021`), able to leave a devis with fewer/no lines; nothing ever cleans zero-line drafts (verified: `expire_stale_devis` touches only ENVOYE). The atomic pattern already exists server-side (`build_devis_from_layout`, `services.py:395-527`) but no general endpoint exposes it. Fix: transactional nested-write endpoint (create devis+lignes in one commit) + `replace-lines` action for edits; generator uses both; PDF polling (`DevisList.jsx:593`) shows a resumable « toujours en cours » state past 30 s instead of giving up (no duplicate Celery jobs). **Done =** kill-the-connection mid-save leaves either nothing or a complete devis (test); edit failure preserves old lines. Files: `apps/ventes/views/devis.py`, `serializers.py`, `frontend .../DevisGenerator.jsx`, `DevisList.jsx`, tests. (ROUTINE) (@lane: ventes-devis-api)
- [x] QX22 — **Truthful « Envoyé » on the WhatsApp path.** Verified frontend-side: `handleEnvoyer` (`DevisList.jsx:410`) flips status when the modal OPENS — closing without sending leaves a phantom-sent quote whose validity clock started. (Server no-phone case REFUTED — `views/devis.py:1032-1038` already 400s before `mark_devis_sent`; don't touch.) Fix: split preview vs send — a read-only preview action populates the modal; `mark_devis_sent` fires only on actual wa.me click-through. **Done =** open-then-close leaves brouillon (test); click-through marks Envoyé exactly once. Files: `apps/ventes/views/devis.py` (preview action), `frontend .../DevisList.jsx`, tests. (ROUTINE) (@lane: frontend-devislist)
- [x] QX23 — **Mode-switch guard + persisted margin snapshot.** Verified: switching market mode after data entry silently discards the étude/ROI chart with no warning and no restore (`DevisGenerator.jsx:410`); and margin/prix-kWc indicators are screen-only — once saved, nobody can see what margin a sent quote carried. Fix: blocking confirm when auto-filled lines exist for another mode; server-side `marge_snapshot` Decimal on Devis computed at save/send (additive migration) shown ONLY in the generator/DevisList manager view — **NEVER in any PDF or client-facing output (prix_achat rule)**. **Done =** mode switch warns; saved quote's margin visible internally; `test_quote_engine.py` still asserts no `prix_achat` in any PDF context. Files: `frontend .../DevisGenerator.jsx`, `apps/ventes/models.py` (+migration), `views/devis.py`, `DevisList.jsx`, tests. (SCHEMA — additive migration) (@lane: ventes-devis-api)
- [x] QX24 — **`etude_params` can't silently go stale.** Verified: production/économies freeze at creation while line edits float — payback = new_total / old_économies is internally inconsistent on the proposal. Fix (option b from verification): recompute+repersist the study whenever lignes/remise/prix change (service hook on LigneDevis save/delete + remise_globale change), keeping seller-entered overrides flagged. **Done =** editing a line updates économies/payback coherently (test); proposal shows consistent numbers. Files: `apps/ventes/services.py`, `models.py`/signals, tests. (ROUTINE) (@lane: ventes-devis-api) (@after: QX21)

**G — SELLER DAY-IN-THE-LIFE**
- [x] QX25 — **Call-ready rows everywhere.** Verified three dead ends: « Mes activités » (the literal daily call list) has no phone/tel:/wa.me on any row (needs a `target_phone` SerializerMethodField via the crm selector); the mobile Leads List view hides the phone column entirely with no tap-to-call fallback (`ListView.jsx:251-260` name cell is never hidden — put the compact tel/wa icons there); and « Planifier une relance » on every Kanban card has ALWAYS been dead — the prop is never passed (`LeadsPage.jsx` viewProps `:327-340` lacks `onPlanifierRelance`; `LeadCard.jsx:43-47` falls back to inert text). Fix all three (wire the handler to the existing setEditLead/setShowForm machinery). **Done =** every activity row and mobile lead row is one tap from call/WhatsApp; the relance shortcut opens the lead with relance focus (tests). Files: `apps/records/serializers.py`, `frontend .../MesActivites`, `crm/leads/{LeadsPage,views/ListView,LeadCard}.jsx`, tests. (ROUTINE) (@lane: frontend-crm)
- [x] QX26 — **Structured loss reasons — learn WHY quotes die.** Verified: refusal reason is an OPTIONAL `window.prompt` free-text (`DevisList.jsx:448-461`), disconnected from the managed `MotifPerte` taxonomy — win/loss data is unusable. Fix: mandatory modal with a MotifPerte select (company-scoped endpoint exists) + optional detail note; write to `Devis.motif_refus` + lead + chatter; feed the existing loss reporting. **Done =** refusing requires a structured reason (test); reporting groups by motif. Files: `frontend .../DevisList.jsx` (+small modal), `apps/ventes` serializer if needed, tests. (ROUTINE) (@lane: frontend-devislist)
- [x] QX27 — **Action-row sanity + typed-interaction rendering.** Verified: DevisList renders 10-14 ungrouped buttons per row (worst on mobile); and `LeadActivity` kinds `appel`/`email` (FG30) render as BLANK chatter items (no conditional branch in `LeadForm.jsx:~1217`). Fix: keep 1-2 status-primary actions inline, rest in a ⋯ DropdownMenu (pattern exists in ListView.jsx); add 📞/✉️ chatter branches with outcome labels. **Done =** ≤3 visible actions per row; appel/email activities render with body+outcome (tests). Files: `frontend .../DevisList.jsx`, `crm/LeadForm.jsx`, tests. (ROUTINE) (@lane: frontend-crm)
- [x] QX28 — **Lead readiness chips — surface what the website already captured.** Verified: the seller cannot tell a lead has a GPS pin/roof outline (`roof_point` reaches ONLY the ToitureDesign 3D path; DevisGenerator never reads it; both quote buttons look identical). Fix: chips on LeadCard/LeadForm from existing fields (« Toit épinglé (GPS) », « Facture saisie », « Prêt à deviser en 1 clic »); badge the 3D button when roof data exists; DevisGenerator shows a « repère toit disponible → Concevoir en 3D » shortcut when set. **Done =** a data-rich lead is visually distinct and routes the seller to the path that uses its data (test). Files: `frontend .../LeadCard.jsx`, `LeadForm.jsx`, `DevisGenerator.jsx`. (ROUTINE) (@lane: frontend-crm)
- [x] QX29 — **« Relances du jour » — the devis work-queue.** Verified: no « quotes needing action today » surface exists (Dashboard is analytics-only; DevisList's only proactive surface is a 7-day expiry banner). Fix: `DevisActionBoardPage` mirroring `SavActionBoardPage`: sent-no-response per cadence level, accepted-not-invoiced (reuse the ZFAC12 selector), refused-without-motif, expiring-soon; every row deep-links via the fixed `?devis=` param with tel/wa shortcuts. **Done =** one page answers « which quotes need me today ». Files: new `frontend/src/pages/ventes/DevisActionBoardPage.jsx`, route, reuse `apps/ventes/selectors.py`. (ROUTINE) (@lane: frontend-devislist) (@after: QX11, QX12)

**H — THE CONVERSION LOOP (research-anchored)**
- [x] QX30 — **Engagement-triggered follow-up engine.** Replace blind day-counting with behavior triggers from data the system already records (ShareLink first-view + `proposal_engagement` sections/time): not-opened-24h → resend nudge; opened-not-signed-48h → call task (46% of signers sign <48 h of open); reopened-3× → « hésite — appelez maintenant » (losing proposals get viewed 3.5×). Also fix the verified lost-update bug: `proposal_engagement` JSON read-modify-write is non-atomic (concurrent section beacons last-write-win) — use `select_for_update`/F-style merge. All triggers land as Notifications + QX29 queue rows with prefilled wa.me drafts. **Done =** each trigger has a test; engagement updates are race-safe. Files: `apps/ventes/services.py`, `public_views.py`, `apps/notifications`, tests. (ROUTINE) (@lane: backend-nudges) (@after: QX13, QX29)
- [x] QX31 — **Speed-to-lead: minutes, not hours.** MIT/Oldroyd: 21× qualification contacting <5 min vs 30; 78% buy from the first responder; industry average is ~42-47 h. Fix pack: first-touch timer on NEW-column kanban cards (« il y a 12 min, non contacté »); unread-hot-lead escalation — if the new-lead notification of a high-score lead is unread after N minutes, escalate (in-app + email now; WhatsApp behind the existing QJ23 flag); instrument time-to-first-touch (lead creation → first outbound LeadActivity) as a reporting metric per seller. **Done =** escalation fires on unread hot leads (test); the metric appears in reporting. Files: `apps/notifications/sweeps.py` or `apps/crm/tasks.py`, `apps/reporting`, `frontend .../LeadCard.jsx`, tests. (ROUTINE) (@lane: crm-speedtolead) (@after: QX14)
- [x] QX32 — **Unified lead timeline.** Verified gap: a seller preparing a call must open two screens (lead chatter vs devis list) to see « proposal viewed 3×, 2 min on price ». Fix: thin `apps/ventes/selectors.py::devis_events_for_lead(lead_id, company)` (sent/opened/signed/refused + engagement summary) merged into the crm `historique` timeline per the cross-app boundary rule; render in LeadForm chatter with distinct icons. **Done =** lead timeline shows quote lifecycle + engagement inline (test). Files: `apps/ventes/selectors.py`, `apps/crm/views.py`, `frontend .../LeadForm.jsx`, tests. (ROUTINE) (@lane: crm-timeline) (@after: QX30)
- [x] QX33 — **Deposit at the moment of signature (degraded no-PSP mode now).** Verified: `deposit.py` + `payment_providers.py` are fully built and completely unreachable from the accept flow — the founder chases payment by phone at peak intent. Fix: post-sign success screen + confirmation email show the acompte (échéancier tranche 1 on the DISCOUNTED total per QX1) with RIB/virement instructions + a « j'ai effectué le virement » declaration that notifies the seller and stamps the devis; a card-payment-link slot activates when a PSP provider is configured (QXG2). Solo's pattern: sign-and-pay in one sitting removes the « I'll get back to you » exit. **Done =** signing shows payment instructions; the declaration reaches the seller (tests); zero behavior change when nothing configured upstream of accept. Files: `apps/ventes/public_views.py`, `services.py`, `deposit.py`, proposal success-state payload, tests. (ROUTINE) (@lane: ventes-esign) (@after: QX1, QX9)
- [x] QX34 — **Post-sign status endpoint `/suivi/<token>` (ERP half; web page = WEB_PLAN WJ115).** Tokenized public read-only endpoint deriving the milestone timeline from existing rows: Devis accepté → Acompte reçu (Paiement) → Matériel commandé (BC) → Installation planifiée/posée (Installation statut) → Facture. Same token discipline as ShareLink (`secrets.token_urlsafe(32)`, expiry, company-bound). Research: post-sign portals (myFreedom, Yes Solar 2025) are the emerging installer differentiator — pure internal engineering, no paid dep, becomes the referral surface. **Done =** endpoint returns the correct milestone state for a devis at each lifecycle stage (tests); no PDF/status behavior touched (rule #4). Files: `apps/ventes/public_views.py`, `public_urls.py`, selector, tests. (ROUTINE) (@lane: ventes-public) (@after: QX33)
- [x] QX35 — **Wire the parrainage promise.** Verified: `parrainage.astro` promises « vous êtes récompensé — sans rien à gérer » but NOTHING connects `utm_source=parrainage` to the `Parrainage` model — no auto-create, no conversion detection, no reward trigger. Fix: webhook auto-creates `Parrainage(filleul_lead=lead, statut='en_attente')` on `utm_source=parrainage` + manager notification; deterministic referral codes on Client (surface in the client form + web link generator later); `devis_accepted` subscriber flips converti when the filleul signs. **Done =** referred lead → visible Parrainage; signature → converti (tests). Files: `apps/crm/webhooks.py`, `receivers.py`, `models.py` (code field — additive migration), tests. (SCHEMA — additive migration) (@lane: crm-webhook)
- [x] QX36 — **Inbound email: replies stop landing in a void.** Verified: FOUR inbound-email subsystems exist, ZERO run — `core/email_intake.py::poll_mailbox` has no beat entry (which also leaves SAV email-to-ticket dead), `apps/ventes/inbound_email.py::capture_inbound_email` has no live caller, and outbound quote emails set no `reply_to`. Fix: schedule `poll_mailbox` in beat (env-gated on mailbox creds); register a ventes handler routing reference-matched replies to `capture_inbound_email` (chatter + notification on the devis); set `reply_to` on outbound quote/facture emails. **Done =** a reply to a quote email surfaces on the devis + notifies the seller (test with stubbed mailbox). Files: `erp_agentique/celery.py`, `core/email_intake.py` wiring, `apps/ventes/inbound_email.py`, `email_service.py`, tests. (ROUTINE) (@lane: backend-beat) (@after: QX11)
- [x] QX37 — **One webhook surface.** Verified: `core.WebhookSubscription`/`core/webhooks.py::dispatch_event` is a dead duplicate of the live `publicapi` webhook layer — configured subscriptions never fire, and its help_text promises exactly the event names the OTHER system delivers. Fold or delete it so exactly one subscription surface exists (keep publicapi). **Done =** no dead subscription model remains; migration removes or repurposes cleanly. Files: `core/webhooks.py`, `core/models.py` (+migration), tests. (SCHEMA — destructive but revertable migration; note in DONE LOG) (@lane: core-cleanup)

**I — ONE TRUE MATH (screen == PDF == proposal)**
- [x] QX38 — **One canonical solar-math model.** Verified: three divergent productibles (solar.js GHI ~1247, engine 1600/1240) = ~28% swing screen-vs-PDF; two avoided-kWh prices; the ONEE tranche table collapses the 101-250 band (mis-prices typical 150-400 kWh/mo homes); `monthlyBillFromKwh`/`_monthly_bill_from_kwh` double-count overflow on finite-ceiling custom tables; 1-MAD per-option rounding divergence. A FOURTH, most-defensible model already exists stranded in `apps/web` (`yieldTable.ts` — PVGIS TMY per-city lat×tilt×aspect, e.g. Agadir ~1687). Fix: promote the PVGIS yield lookup into ONE shared committed asset consumed by `builder.py`/`pricing.py` AND `solar.js` (per-city static values, no paid API); CompanyProfile 1600 becomes an editable override, not a competing physics model; ONE avoided-kWh price threaded everywhere (QX7d); corrected ONEE tranche table aligned across `kwhFromBill`/`two_bills_savings`/both bill-from-kWh functions (fix the overflow double-count); align the rounding chain to kill the 1-MAD divergence. **[DECISION — founder adjudicates the canonical productible; PVGIS recommended.]** **Done =** one committed table; generator screen, PDF and web proposal show the SAME production/économies for the same inputs (cross-engine test). Files: shared asset (e.g. `quote_engine/productible.py` + mirrored JS/TS), `solar.js`, `builder.py`, `pricing.py`, `constants.py`, tests. (DECISION + ROUTINE) (@lane: solar-math)
- [x] QX39 — **Honest 25-year cashflow.** Payback today is a single Year-1 ratio — neither conservative nor best-case. Fix in-engine (+ mirrored in solar.js via QX38): 0.5%/yr panel degradation, documented tariff-escalation hypothesis, battery round-trip efficiency, optional inverter-replacement year; payback = cumulative cashflow zero-crossing; assumptions block rendered on PDF + web proposal (source of ensoleillement, dégradation, hypothèse tarifaire — self-consumption-first, BT surplus tariff still unpublished as of 2026-06-18 checks, 20% injection cap pre-baked). **Done =** payback from a real cashflow with stated assumptions (tests); charts stop implying flat savings for 25 years. Files: `quote_engine/pricing.py`, `residential` charts, `solar.js`, tests. (ROUTINE) (@lane: solar-math) (@after: QX38)
- [x] QX40 — **Pompage electrical + data sanity.** Verified: curve-mode can pair a 380V triphasé pump with a 220V variateur (no phase/voltage cross-check in `selectPompeByCurve`, `solar.js:795-816`) — latent until OSP pumps get priced (QXG3), then live; plus suspicious HMT seeds (7.5CV@220m, 10CV@250m — likely shutoff head, not duty point). Fix: phase-compatibility filter before selection + assert pump tension == variateur tension in compose; degrade to the CV path with a visible warning when no phase-compatible priced curve pump exists; seed values corrected under QXG3 (founder data). **Done =** a mono/220V request can never return a 380V pump (test). Files: `frontend/src/features/ventes/solar.js`, tests. (ROUTINE) (@lane: solar-math)

**J — PUBLIC SURFACE HARDENING & RETENTION**
- [x] QX41 — **Public hardening pack.** Verified: `open_chat_session` is completely unthrottled (unbounded anonymous row creation); e-catalogue « demander devis » has no idempotency (double-click floods seller with duplicate brouillons + notifications); the public accept path lacks row-level locking (double-accept race can double-fire `devis_accepted` side effects). Fix: per-IP throttle on chat-open (+ register the hardcoded throttle scopes in `DEFAULT_THROTTLE_RATES` as the single source of truth); cache.add idempotency lock on the cart submission keyed token+contact-hash (mirror `proposal_contact_request`); `select_for_update` around accept. **Done =** tests for all three. Files: `apps/crm/public_chat_views.py`, `apps/ventes/public_views.py`, `services.py`, `settings/base.py`, tests. (ROUTINE) (@lane: ventes-public)
- [x] QX42 — **PII retention for the raw intake copies.** Verified: `WebsiteLeadPayload` (raw PII + IP, SET_NULL from Lead so erasure never reaches it) and `ChatSessionPublique` accumulate FOREVER; the generic `core.retention` framework + its beat job exist but the registry is EMPTY — no app registers a policy. Fix: register retention policies in `CrmConfig.ready()` (purge processed payloads after N days — founder-configurable, default 180; stale chat sessions similarly); document in the privacy page's terms. GDPR-relevant: marocains-du-monde deliberately targets EU diaspora. **Done =** sweep purges old rows (test); unprocessed/error payloads exempt until QX16's replay surface has aged them. Files: `apps/crm/apps.py`, `services.py`, tests. (ROUTINE) (@lane: crm-retention) (@after: QX16)

**GATED — founder decisions/accounts/data (queue, do NOT build the gated part)**
- [ ] QXG1 — **[GATED: founder account]** WhatsApp BSP evaluation, 360dialog-first (flat $59/€49/mo, zero markup on Meta per-template pricing — 2026 model is per-template-message, the old free tier is gone). Needs Meta Business verification + Morocco rate confirmation from the dashboard (not blogs). Unlocks: automated template sends for QX30's nudges, real OTP channel (QX10), proposal delivery. Until then everything ships degraded via wa.me drafts. (@lane: whatsapp-bsp)
- [ ] QXG2 — **[GATED: founder account]** PayZone-first merchant onboarding (reported 5-10 day onboarding, no deposit, ~2-3% fees — verify primary-source), CMI later if volume justifies. Activates QX33's card-payment slot + facture PaymentLinks with a REAL provider (QX3 keeps everything fail-closed meanwhile). (@lane: ventes-pay)
- [ ] QXG3 — **[GATED: founder data]** Price the 11 OSP 30-series curve pumps (today ALL curve pumps are seeded price=0, so the intended HMT+débit agricole flow can never quote a buyable pump — the highest-impact single data entry in the journey) + verify/correct the suspicious HMT seeds (7.5CV@220m, 10CV@250m must be nominal duty points, not shutoff head) + confirm/replace the archived estimated coffrets. Land QX40's phase check first. (@lane: backend/stock)
- [ ] QXG4 — **[GATED: founder content]** Real proof pack for the trust page: selected installation photos, named testimonials, certifications (checked-facts-only rule — omit what doesn't exist). Proposify 2025: images +72% close rate, testimonials near the price +73% win probability. Lands inline in `residential/trust.py` after QX4. (@lane: quote-engine)
- [ ] QXG5 — **[GATED: founder ops check, 10 minutes]** Production env sanity: confirm `WEBSITE_LEADS_COMPANY_ID` is set (else `_resolve_company()` falls back to first Company by pk — silent misrouting risk if a second Company row ever exists); confirm the outbound email backend keys (`EMAIL_BACKEND`/`SENDGRID_API_KEY` vs `SENDINBLUE_API_KEY`) so QW8/QX13's email legs are live; confirm `PUBLIC_MAPTILER_KEY` naming on Cloudflare. (@lane: ops-config)

---

### TOP PRIORITY — build first (queued 2026-06-20)


### Group U — Field UX bugs + document-status "connections" (founder request 2026-06-22)

*Live issues Reda is hitting in the field, plus the family of "connection"
gaps found while investigating #4 (an action in one place that should flip a
document status or surface it in another menu, but doesn't). U1–U3 are UX/layout
bugs; U4–U5 are the two Reda named; U6–U12 are the similar disconnects an audit
turned up. Hard constraints stay in force: rule #4 status preservation (the quote
PDF engine only RENDERS, `/proposal` is the only client PDF path), STAGES.py keys
are imported never hardcoded, all migrations additive/nullable + company-scoped
server-side, cross-app reads/writes go through `selectors.py`/`services.py` and
the `core/events.py` bus (never another app's models/views).*


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

  JSONField to `Devis` (additive migration) holding the *finalized* serialized
  `AreaRecord[]` (roof vertices, obstacles, roofType, pitch, azimuth, the result
  `{panels,kwc,annualKwh,savings}`, and `renderPlan`). Add company-scoped DRF
  endpoints `POST /api/django/ventes/devis/<id>/layout/` (save — company forced in
  the serializer/`perform_create`, never from body) and `GET …/layout/` (load).
  **Done =** round-trip save/load test + a cross-tenant isolation test pass. Files:
  `apps/ventes/models.py` (+migration), `apps/ventes/views.py`/serializers, tests.

  `roof_point` (lat/lng of the building the client pinned) and `roof_outline` (OPTIONAL
  rough polygon, usually empty — the client need not draw) JSONFields to the CRM Lead,
  plus the bill kWh and a secure unguessable per-lead `token` (UUID) for the Meriem
  hand-off link. First VERIFY the W105–W111 contact-capture work (it may already carry
  part of this) and EXTEND rather than duplicate; wire the lead intake/webhook
  (`apps/crm/webhooks.py`) to accept + persist the pin (+ optional outline) with the
  lead. **Done =** the pin persists on the lead, token resolves the lead, company forced
  server-side; tests cover it. Files: `apps/crm/models.py` (+migration),
  `apps/crm/webhooks.py`/views, tests.

  finalized layout (kWc, nb panneaux, production, chosen module/onduleur) into Devis
  lines from the seeded catalogue, reusing the SAME composition rules as the quote
  generator (`builder.py` réseau/injection/hybride/batterie/panneau keywords) and the
  reference-numbering util (`apps/ventes/utils/references.py`, never count()+1), with the
  client resolved via `apps/crm/services.resolve_client_for_lead`. Store the layout's
  production into `Devis.etude_params`. **Done =** a sample layout produces a coherent,
  company-scoped Devis with correct kWc/lines/totals and NEVER auto-quotes a price-less
  product (existing guard); tests cover residential réseau + hybride+batterie. Files:
  `apps/ventes/services.py`, `apps/crm/services.py`, tests.

  and store it in MinIO reusing the existing PDF bucket/`minio_client` infra, keyed +
  company-scoped, referenced from a nullable `Devis.roof_image` field (additive).
  Endpoint `POST /api/django/ventes/devis/<id>/roof-image/`. **Done =** upload + signed
  retrieval test + company-scoping test pass. Files: `apps/ventes/utils/` (minio),
  `apps/ventes/models.py` (+migration), views, tests.

  Extend the quote-data builder so a quote CAN show the real roof render as the "votre
  installation" visual and use the layout's kWc/production/savings instead of estimating
  — **only when a layout/render is present**; with none present the existing PDF output
  stays byte-identical (back-compat, rule #4). **Done =** with-layout vs without-layout
  tests both pass and the no-layout render is unchanged. Files: `quote_engine/builder.py`
  (guarded), tests. *(Additive only — does not alter the legacy path.)*

  `GET /api/django/ventes/proposal/<token>/` returning the quote data
  (`build_quote_data` output + roof-image signed URL + option totals) as JSON for the
  client web proposal (W116) to render — authenticated by the signed token, not a login,
  company-scoped, expired/invalid tokens rejected. **Done =** valid token returns the
  payload; invalid/expired rejected; no cross-tenant leakage; tests cover it. Files:
  `apps/ventes/views.py`/urls, token util, tests.

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


> **Voice layer (AG10–AG12, founder request 2026-06-21).** Adds a hands-free voice
> conversation to the assistant — speak questions, hear answers, continuous loop.
> Speech→text uses Groq `whisper-large-v3` via the existing `GROQ_API_KEY` (no new paid
> service); text→speech uses the browser's built-in voices (free). Voice never bypasses the
> propose→confirm spine: outward/irreversible actions still require an explicit spoken
> « confirmer » or a tap before anything executes. (Distinct from Group S's self-hosted
> chat-memo transcription — this is the assistant's spoken conversation.)


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

- [BLOCKED: waits on founder-provisioned WS infra (ASGI server process + Redis channel layer + nginx WebSocket proxy) — a real external prerequisite a run can't satisfy] S21 — **Real-time WebSocket upgrade (Django Channels).** Instant message delivery, typing indicators and live presence via Django Channels + a Redis channel layer + an ASGI server (daphne/uvicorn) + an nginx WebSocket proxy, authenticated with the same JWT. (UNGATED from category-gating 2026-06-21; held only by the infra prerequisite. **MY RECOMMENDATION: DEFER — "Discuss" chat already works via 3 s short-polling (`useChatPolling.js`); the WS stack adds real ops complexity (sticky sessions, connection draining on deploy) for a marginal gain on a small internal team. Build it only on a concrete need (live dispatch / many concurrent users).** Files: `erp_agentique/asgi.py`, `apps/chat/consumers.py` (new), settings `CHANNEL_LAYERS`, nginx config, frontend socket client.) (ARCH) (@lane: realtime)

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

### Groupe VX — « Le plus bel ERP du monde » : signature visuelle, expérience Apps & craft + perfection technique (audits 16+11 agents, 2026-07-07/08)

*Provenance : demande du fondateur (2026-07-07) « make my ERP the best looking in the world + les modules
sont-ils mieux découpés façon Odoo ? ». Audit multi-agents à modèles étagés : 9 lanes de lecture du repo
(design-core, shell-nav, écrans CRM/ventes/ops/insight/fondation, mobile-PWA, scan de cohérence) + 5
recherches web best-in-class (Odoo 18/19, Linear/Attio/Stripe/Notion, data-viz, délice/motion,
field-service) + une carte anti-duplication sur TOUS les plans, puis synthèse Fable. Chaque constat est
vérifié dans le code (fichier:ligne) et re-vérifié par l'orchestrateur avant intégration.*

**VERDICT MODULES — la réponse à la question du fondateur.** Le découpage façon Odoo est le BON choix et il
est déjà à moitié fait : GARDER et TERMINER le plan ODX tel que queued (PLAN.md ODX1–23 — manifests, catalogue
+ fermeture de dépendances et enforcement déjà livrés ; les moves restants facturation/achats/ao/portail/frais
sont des migrations state-only, sûres et révertables) — ne jamais re-fusionner, revenir en arrière coûterait
plus cher que finir. MAIS le découpage backend seul ne donnera jamais l'effet « apps » perçu : ce que
l'utilisateur ressent comme des modules est une expérience de NAVIGATION. Aujourd'hui la sidebar empile ~106
destinations plates (45 codées en dur + 61 items de 16 `module.config.jsx`) toutes du même gris avec le même
accent — Compta, RH, QHSE et Litiges sont visuellement interchangeables. Ce groupe construit la couche
frontend manquante (accent par module, lanceur d'apps, favoris épinglés, breadcrumb→cockpit) en s'ADOSSANT à
ODX5/6/7 (queued), jamais en les dupliquant.

**Vision « Lumière sur Nuit ».** Un fond calme bleu nuit ; la lumière (brass) dépensée avec parcimonie
exactement là où l'énergie circule. Diagnostic central vérifié : la fondation de tokens (F120–P171) est
world-class sur le papier, mais l'app RENDUE est une installation shadcn slate générique — ~604 hex codés en
dur dans `index.css` (top : la palette slate par défaut de Tailwind, pas la marque), coquille Sidebar/Header
100 % figée hors tokens, QUATRE « ors » et TROIS « navys » concurrents, `<body>` en system-ui + `#f1f5f9`,
dark mode à moitié réel. Cette vague est de l'ADOPTION et de la SIGNATURE, pas une refonte de la fondation.

> **Contraintes (chaque tâche VX).** Zéro nouvelle dépendance npm (Radix / Tailwind 4 / recharts /
> @tanstack / @dnd-kit / sonner / lucide déjà installés suffisent — sinon flag [GATED: new dep]). Ne JAMAIS
> toucher les templates PDF devis/facture, les pages PDF publiques, PdfCanvas, `/proposal` (règle #4) ni
> `apps/web`. Clés de stage importées de STAGES.py, jamais codées (règle #2 — seules des COULEURS peuvent
> être tokenisées). UI en français ; hooks e2e (`ap-*`, `att-*`, `pp-*`) préservés et déplacés AVEC leurs
> éléments ; garde `noValidate`/`step="any"` du générateur intacte ; `prix_achat`/marge JAMAIS client-facing.
> Frontend-only — DEUX exceptions round 2, flaggées dans leur tâche : VX61 (endpoint de collecte web-vitals
> dans l'app `reporting` existante) et VX76 (templates d'email HTML, zéro logique) ; `prefers-reduced-motion` respecté partout ;
> contraste AA en clair ET en sombre. Le modèle conseillé par tâche est indicatif (l'orchestrateur arbitre).
> **Coordination inter-plans :** `docs/FRONTEND_GAP_PLAN.md` (câblage fonctionnel des backends X*/Z*, ajouté
> 2026-07-07 via fe-dev) partage trois fichiers avec ce groupe — `GedNavigator.jsx` (FE-XGED14 ↔ VX38),
> `TicketsPage.jsx` (FE-XSAV5/21/28 ↔ VX31), `DevisList.jsx` (FE-ZSAL8/XSAL16 ↔ VX7/20/40/44). Le run qui
> passe en second rebase sur le premier ; les deux plans sont complémentaires (câblage vs design), jamais
> en conflit d'intention.

**A — La signature : la coquille devient TAQINOR (le meilleur ratio qualité perçue ÷ effort de la vague) :**
- [x] VX1 — **Un seul or, un seul navy : fusion des jetons de marque.** Éliminer les quatre « ors » (`--primary #e8b54a`, `--cat-gold #f5a623`, `#F5C100` sidebar/bolt, `#f28e2b` gen-btn) et les trois « navys » (`--nuit`, `--cat-navy #0b1f3a`, `#0f172a`) : redéfinir `--cat-gold: var(--primary)` et `--cat-navy: var(--color-nuit)` dans `frontend/src/design/tokens.css`, retirer les redéclarations locales (`frontend/src/index.css` ~1520-1525 et bloc `.lv-wrap` ~4469) et les constantes JS `NAVY`/`GOLD` de `frontend/src/features/pwa/PwaPrompts.jsx` (→ `var(--…)`). Une signature exige UNE couleur signature (discipline Linear). **Done =** un seul or et un seul navy à travers catalogue/kanban/générateur/sidebar/bannière PWA, grep des valeurs mortes vide hors token source, CI stage-names verte. Files: frontend/src/design/tokens.css, frontend/src/index.css, frontend/src/features/pwa/PwaPrompts.jsx. (ROUTINE — M, sonnet) (@lane: frontend/design)
- [x] VX2 — **Re-signer la coquille permanente (Sidebar + Header) aux couleurs de marque.** Réécrire les blocs `.sidebar*` (19 classes) et `.header*` (16 classes) de `frontend/src/index.css` pour consommer les tokens : fond sidebar `var(--color-nuit)` au lieu de `#0f172a`, labels sur la rampe encre/lune, item actif via `--primary` au lieu de `#F5C100` figé, header en `var(--card)` + `border-color: var(--border)` (il suit ENFIN le dark mode), avatar en `var(--primary)`. Au passage regrouper les 8 boutons de `.header-right` en 3 grappes visuelles (Recherche / Communication / Préférences+compte) par des wrappers `header-cluster` dans `frontend/src/components/layout/Header.jsx` — CSS + wrappers uniquement, aucun changement de comportement. C'est le cadre vu 100 % du temps : le levier n°1 de reconnaissance. **Done =** coquille en nuit/brass en clair ET en sombre, grep `#0f172a|#3b82f6|#ffffff|#94a3b8` vide dans les blocs sidebar/header, e2e mobile + `.sidebar-nav-item.active` inchangés. Files: frontend/src/index.css, frontend/src/components/layout/Header.jsx. (ROUTINE — L, sonnet) (@lane: frontend/design) (@after: VX1)
- [x] VX3 — **La typo de marque et le fond tokenisé au niveau `<body>`.** Porter `font-family: var(--font-brand)` et un fond piloté par `var(--background)` sur le `<body>` (`frontend/src/index.css:24-29`, aujourd'hui system-ui + `#f1f5f9`), rendre `.ui-root` no-op hérité et retirer progressivement les wrappers par page (Dashboard.jsx:413, Journal, AgentChat, OcrUpload, Rapports…). Une app « la plus belle du monde » ne rend pas son texte courant en police système. **Done =** Hanken en corps + Archivo en titres sur tout écran sans wrapper, fond suivant le thème partout, contraste AA vérifié sur les surfaces legacy claires. Files: frontend/src/index.css, frontend/src/design/tokens.css, frontend/src/pages/Dashboard.jsx, frontend/src/pages/Journal.jsx, frontend/src/pages/Rapports.jsx, frontend/src/pages/ia/ (retrait des wrappers `.ui-root`). (ROUTINE — M, sonnet) (@lane: frontend/design) (@after: VX2)
- [x] VX4 — **Finir le dark mode sur la surface legacy.** Passer les blocs encore en clair figé (`.btn-primary`, `.data-table`/`th`/`td`, `.gen-card`, `.modal`, `.form-control`, `.agent-*`, `.status-tab`, `.search-input`) de `frontend/src/index.css` sur les tokens sémantiques (`--card`, `--border`, `--foreground`, `--primary`, `--muted`). Un dark mode à moitié réel (header/tables/boutons clairs sur ~51 fichiers legacy) est pire que pas de dark mode — l'erreur « négatif photo non fini » reprochée à Odoo 18. **Done =** basculer `.dark` rend header, tables, boutons, formulaires et chat agent sombres et cohérents ; contraste AA ; captures clair/sombre d'un écran liste + une fiche. Files: frontend/src/index.css. (ROUTINE — L, sonnet) (@lane: frontend/design) (@after: VX3)
- [x] VX5 — **Data typography « .num » : les chiffres deviennent les héros.** Créer un utilitaire `.num` (font-display + `tabular-nums slashed-zero` + tracking resserré) dans `frontend/src/design/tokens.css` et l'appliquer aux montants MAD, kWc, production, références et totaux : `frontend/src/ui/Stat.jsx` (déjà partiel), totaux devis `.devis-total-ttc`, `.gen-metric-value`, `.kb-col-money`, colonnes numériques DataTable. Le « numeric story » Stripe/Mercury — `lib/format.js` reste l'unique source de formatage fr/MAD. **Done =** tout chiffre monétaire/énergie aligne ses colonnes (même graisse, zéro barré), capture d'un tableau devis prouvant l'alignement. Files: frontend/src/design/tokens.css, frontend/src/ui/Stat.jsx, frontend/src/index.css. (ROUTINE — M, sonnet) (@lane: frontend/design) (@after: VX4)
- [x] VX6 — **Un seul langage de rayon et d'élévation.** Remplacer les rayons legacy en dur (cartes 14px, modale 14px, boutons 8px, `.gen-card`) par l'échelle dérivée de `--radius`, et aligner l'ombre au repos sur la discipline F122 : cartes = liseré (`shadow-card`), retirer l'ombre au repos de `.data-table` (index.css ~836), réserver `shadow-menu/modal/toast` aux calques flottants, pointer `frontend/src/ui/Card.jsx` sur `shadow-card`. **Done =** aucun `border-radius: 14px|8px` en dur hors token, cartes non « flottantes » au repos, menus/modales seuls porteurs d'ombre. Files: frontend/src/index.css, frontend/src/ui/Card.jsx. (ROUTINE — M, sonnet) (@lane: frontend/design) (@after: VX5)
- [x] VX7 — **Passe « calm color » : hiérarchie de poids visuel sur les écrans denses.** Une passe d'audit-ajustement (pas de refonte) sur DevisList, leads ListView, StockList et FactureList : bordures/séparateurs adoucis (~60 % d'opacité), métadonnées secondaires (dates, IDs, canaux) en muted, contraste plein réservé aux données primaires (nom client, montant TTC, statut) et aux signaux (retard, expiré) ; actions de survol en `opacity-0 group-hover:opacity-100` sans reflow. Recette « chrome désaturé / signal saturé » de Linear — le plus fort levier ressenti au plus bas coût sur un écran B2B dense. **Done =** capture avant/après des 3 listes, aucun test cassé, aucune info supprimée — seulement re-pesée. Files: frontend/src/pages/ventes/DevisList.jsx, frontend/src/pages/crm/leads/views/ListView.jsx, frontend/src/pages/stock/StockList.jsx, frontend/src/index.css. (ROUTINE — M, sonnet) (@lane: frontend/design) (@after: VX6)

**B — L'expérience « Apps » (la réponse frontend au verdict module-split ; s'adosse à ODX5/6/7, ne les duplique pas) :**
- [x] VX8 — **Un accent de couleur par module (le bout manquant du découpage Odoo).** Étendre le contrat `module.config.jsx` (et les sections encore codées en dur de `Sidebar.jsx` en attendant ODX7) d'un champ optionnel `accent` choisi parmi 6-8 teintes DÉRIVÉES des rampes OKLCH existantes (Finance=nuit, Ventes=brass, RH=azur, Terrain=lune…), posé en `--module-accent` sur `.sidebar-section` pour teinter liseré + icône active de CE module. Aucune couleur inventée, contraste AA clair et sombre, VENTES garde le brass ; conçu pour survivre à ODX7 (l'accent vivra dans le registre). L'orientation périphérique d'Odoo sans son incohérence — l'œil doit pouvoir dire « je suis dans QHSE » sans lire. **Done =** chaque section de nav a une couleur perceptible distincte, AA vérifié, e2e nav vertes. Files: frontend/src/index.css, frontend/src/components/layout/Sidebar.jsx, frontend/src/features/*/module.config.jsx, frontend/src/design/tokens.css. (ROUTINE — M, sonnet) (@lane: frontend/shell) (@after: VX2)
- [x] VX9 — **Le Lanceur d'applications TAQINOR (grille légère, pas une page).** La surface « toutes mes apps » qui manque : un overlay léger (Radix Dialog, bouton grille dans le header + raccourci `g a`) affichant les modules en grille par catégorie — icône + accent VX8 + label FR — favoris en tête, 3 récents, clic = navigation vers le cockpit du module. Données : `moduleConfigs` de `frontend/src/router/moduleRoutes.jsx` (et le catalogue ODX3 pour l'état actif quand ODX6 aura livré le filtrage — coordonner, ne pas dupliquer ODX6). Différence assumée avec Odoo : un overlay ~150 ms, PAS une re-navigation pleine page (jugée lourde par les utilisateurs Odoo eux-mêmes) ; quand ODX5 livrera l'écran Paramètres→Applications, lui appliquer le même langage de carte (extension design d'ODX5, pas un double). **Done =** ouvrir/naviguer/épingler au clavier et à la souris, reduced-motion respecté, aucun chevauchement fonctionnel avec ODX5/6. Files: frontend/src/components/layout/AppLauncher.jsx (nouveau), frontend/src/components/layout/Header.jsx, frontend/src/providers/ShortcutsProvider.jsx, frontend/src/index.css. (ROUTINE — L, sonnet) (@lane: frontend/shell) (@after: VX8)
- [x] VX10 — **Apps épinglées personnelles dans la Sidebar.** Une bande fine sous `.sidebar-role` listant 4-6 icônes de modules épinglés (clic = cockpit du module), bouton « + » pour épingler/désépingler depuis `moduleConfigs`, persistance `localStorage` (`taqinor.sidebar.pinned`, motif `COLLAPSE_KEY` de `Layout.jsx:16`), état partagé avec le lanceur VX9 (même clé). La densité à ~106 destinations se gère par la personnalisation (convergence Odoo 17 / Notion favorites / Attio pinned), pas par la réduction de police. **Done =** épingler/désépingler persiste au rechargement, aria-labels corrects, aucune régression des hooks `sidebar-nav-item`. Files: frontend/src/components/layout/PinnedApps.jsx (nouveau), frontend/src/components/layout/Sidebar.jsx, frontend/src/index.css. (ROUTINE — M, sonnet) (@lane: frontend/shell) (@after: VX9)
- [x] VX11 — **Fil d'Ariane cliquable vers le cockpit du module + mémoire du dernier module.** Étendre `moduleSectionLabels` pour porter `{label, to}` et rendre le premier segment du breadcrumb cliquable quand un cockpit existe (`rh`→`/rh`, `compta`→`/comptabilite`…), repli `to: null` conservé (routes.meta.js:178) ; persister `taqinor.lastModule` à chaque navigation. Chaque module a déjà son cockpit, rien ne les relie — et l'état de navigation doit survivre au refresh (leçon breadcrumb-URL d'Odoo 18). **Done =** cliquer « RH » depuis `/rh/employes/42` ramène à `/rh`, sections sans cockpit inchangées, tests Breadcrumbs verts. Files: frontend/src/components/layout/routes.meta.js, frontend/src/components/layout/Breadcrumbs.jsx, frontend/src/router/moduleRoutes.jsx. (ROUTINE — S, haiku) (@lane: frontend/shell)
- [x] VX12 — **« Plus » mobile = sélecteur d'apps en grille, pas le tiroir de 100 items.** Remplacer l'ouverture du tiroir sidebar complet par un tiroir compact affichant d'abord la grille de modules (3-4 colonnes, icône + accent VX8, façon apps Odoo mobile) ; taper un module déroule ses items en second niveau, retour possible à la grille. Réutilise `NAV_SECTIONS` + `moduleNavSections`, seule la présentation change. **Done =** « Plus » affiche la grille en premier, navigation deux niveaux fluide, tests Playwright mobile adaptés/verts. Files: frontend/src/components/layout/BottomTabBar.jsx, frontend/src/components/layout/Layout.jsx, frontend/src/index.css. (ROUTINE — M, sonnet) (@lane: frontend/shell) (@after: VX10)
- [x] VX13 — **Une seule recherche : hook partagé GlobalSearch + CommandPalette, pastilles de module.** Extraire `ROUTE`/`LIST_ROUTE`/`TYPE_LABEL` + debounce/état dans `frontend/src/lib/search/entityRoutes.js` + `useEntitySearch(term)`, consommé identiquement par `GlobalSearch.jsx` et `CommandPalette.jsx` (leurs tables divergent DÉJÀ : `bon_commande`/`contrat`/`dossier` connus d'un seul côté, ~150 lignes dupliquées chacun) ; chaque `module.config.jsx` peut déclarer un `searchType` ; pastille d'accent du module d'origine (VX8) sur chaque résultat des deux surfaces. **Done =** les deux composants passent par le même hook (comportement byte-identique aux tests existants), un seul endroit pour ajouter un type d'entité, pastilles visibles avec repli neutre. Files: frontend/src/lib/search/entityRoutes.js (nouveau), frontend/src/components/layout/GlobalSearch.jsx, frontend/src/providers/CommandPalette.jsx. (ROUTINE — M, sonnet) (@lane: frontend/shell) (@after: VX12)
- [x] VX14 — **Centre de notifications : onglets + config déclarative (delta mince, vérifié).** Le panneau de `frontend/src/components/layout/NotificationBell.jsx` groupe DÉJÀ par domaine en sections empilées (« Activités en retard » ~297, « Garanties ≤ 90 j » ~311, « Factures impayées » ~325, « Contrats à renouveler » ~339) — le delta réel est plus mince que prévu : passer ces groupes empilés en 2-3 onglets internes avec compteurs (« Échéances », « Financier », « Activités ») et rendre la config d'onglets DÉCLARATIVE (ajouter un domaine = une entrée de config, pas du JSX copié). Priorité basse dans la lane. **Done =** onglets + compteur total correct (somme), clavier/clic inchangés, tests notifications verts. Files: frontend/src/components/layout/NotificationBell.jsx. (ROUTINE — M, sonnet) (@lane: frontend/shell) (@after: VX13)
- [x] VX15 — **Identité de cockpit : ModuleHero + accent + sparklines dans ModuleDashboard.** Créer `frontend/src/ui/module/ModuleHero.jsx` (titre `--text-h1`, sous-titre, actions, liseré gradient brass→transparent ≤8 % d'opacité coupé sous reduced-motion, slot KPI) et l'adopter sur `frontend/src/pages/Dashboard.jsx:416` (remplace le `<h2>` nu) ; étendre `frontend/src/ui/module/ModuleDashboard.jsx` d'un prop `trend` par stat (mini-sparkline via `ui/charts/KpiSpark`) et d'une pastille d'accent de module (VX8), avec `features/magasin/MagasinCockpit.jsx` en consommateur exemple. Casse la monotonie « 4 boîtes grises copiées-collées sur ~10 modules » ; le seul gradient de marque autorisé à l'intérieur de l'app (« lumière à travers le verre »). **Done =** Dashboard ouvre sur un hero de marque (heading e2e conservé), prop sparkline rétrocompatible, `module.test.jsx` étendu vert. Files: frontend/src/ui/module/ModuleHero.jsx (nouveau), frontend/src/ui/module/ModuleDashboard.jsx, frontend/src/pages/Dashboard.jsx. (ROUTINE — M, sonnet) (@lane: frontend/insight) (@after: VX8)

**C — Le chemin de l'argent (générateur, devis, factures — l'écran le plus stratégique doit être le plus soigné) :**
- [x] VX16 — **Rail de résumé permanent du générateur de devis (desktop).** Ajouter un `<aside className="gen-summary-rail">` sticky (`top: var(--header-h)`, visible dès `lg:`) à côté du `<form>` de `frontend/src/pages/ventes/DevisGenerator.jsx`, affichant en continu : total TTC de l'option retenue, marge indicative (GENERATOR-ONLY — jamais dans un PDF ni côté client), système résumé (kWc/panneaux), boutons Annuler/Créer — aujourd'hui un vendeur scrolle 3 000+ px sans jamais voir le total (`gen-actions-sticky` n'est sticky qu'en mobile, index.css ~2160, à ne pas toucher). Le rail de configurateur « à la Stripe ». **Done =** total + bouton visibles à tout moment du scroll desktop, comportement mobile inchangé, garde `noValidate`/`step="any"` intacte (test existant vert). Files: frontend/src/pages/ventes/DevisGenerator.jsx, frontend/src/index.css. (ROUTINE — M, sonnet) (@lane: frontend/ventes-gen) (@after: VX4)
- [x] VX17 — **Générateur : le cœur visuel passe aux tokens (dark mode réparé sur l'écran le plus stratégique).** Remplacer les hex en dur : `.gen-metric*`/`.lines-table*` dans `frontend/src/index.css` (~1178-1210, 2665-2701) → `var(--card)/var(--muted)/var(--warning)/var(--muted-foreground)` ; dans `DevisGenerator.jsx`, les `style={{color:'#16a34a'}}`/`#b91c1c`/`#b45309` (~2059, 2091-2129) → `text-success`/`text-destructive`/`text-warning` (déjà utilisés ailleurs dans le MÊME fichier) ; le chart Recharts `#1A2B4A`/`#F5A623` (~1810/1816) → tokens de marque. **Done =** `/ventes/devis/nouveau` en thème sombre sans aucun fond clair figé ni texte illisible, vérifié dans les deux thèmes. Files: frontend/src/index.css, frontend/src/pages/ventes/DevisGenerator.jsx. (ROUTINE — S, sonnet) (@lane: frontend/ventes-gen) (@after: VX16)
- [x] VX18 — **Brancher la fonctionnalité fantôme : modèles de devis (DevisPresetPanel).** `frontend/src/pages/ventes/DevisPresetPanel.jsx` (273 lignes, endpoints save-preset/apply-preset/presets complets — QJ16) n'est importé NULLE PART (vérifié) — une réduction directe de friction déjà codée et invisible. L'importer dans `DevisGenerator.jsx` (sous la carte Lignes de Produits ou en tiroir depuis l'en-tête), câbler `onApplied` → `setLines(withKeys(...))`, remplacer son `StatusBadge` local en Tailwind dur (lignes 35-39) par `Badge`/`StatusPill` du kit. **Done =** sauvegarder un devis type et le réappliquer en un clic, testé en clair et sombre. Files: frontend/src/pages/ventes/DevisGenerator.jsx, frontend/src/pages/ventes/DevisPresetPanel.jsx. (ROUTINE — S, sonnet) (@lane: frontend/ventes-gen) (@after: VX17)
- [x] VX19 — **Zéro popup navigateur : éradiquer les `window.alert/confirm/prompt` (~65 appels, 40 fichiers).** Remplacer partout dans `frontend/src/pages` (pires zones : `FactureList.jsx` ~20, `RelancesPage.jsx` 7, `ParametresEntreprise.jsx` 9, `VentesKanban.jsx` 3, stock, sections paramètres…) : résultats/erreurs → `toast.success/error` (pattern DevisList), confirmations destructives → `AlertDialog` (poids de feedback = poids d'action), saisies `prompt()` (export comptable, motifs) → petites `ResponsiveDialog` + `Input`. C'est l'anti-signature : des popups OS non stylées au milieu d'une app de marque. À exécuter EN DERNIER de la vague (touche 40 fichiers — après les lanes écrans pour éviter les conflits ; recoupements vérifiés : ParametresEntreprise.jsx = fichier de VX35, StockList.jsx = VX7/VX33). **Done =** `git grep -E '(^|[^.\w])(confirm|alert|prompt)\('` vide dans `frontend/src/pages` (les appels NUS comptent : FactureList en a 17 nus contre 5 préfixés `window.` — un grep `window.` seul passerait à tort), tests FactureList/DevisList adaptés verts. Files: ~40 fichiers frontend/src/pages/** (commencer par ventes). (ROUTINE — L, sonnet) (@lane: frontend/sweep) (@after: VX21, VX25, VX29, VX31, VX32, VX33, VX35, VX38, VX45, VX63, VX79)
- [x] VX20 — **Fin de la « soupe d'actions » : menus Plus sur DevisList, RelancesPage et BulkActionBar CRM.** DevisList affiche jusqu'à 10 boutons par ligne (~1376-1644), RelancesPage 7, la BulkActionBar CRM 12 : garder 2-3 actions primaires contextuelles visibles (PDF, Envoyer, Accepter/Refuser selon statut) et déplacer le reste dans `DropdownMenu` (déjà utilisé par FactureList.jsx:29 et ListView.jsx:427) ; même traitement pour `frontend/src/pages/crm/leads/BulkActionBar.jsx` (garder Responsable/Étape/Archiver/Export + menu). Anatomie de rangée Linear/Attio — actions révélées, jamais empilées. **Done =** hauteur de ligne stable sans débordement tablette, TOUS les hooks e2e `ap-*` déplacés avec leurs boutons, `DevisList.test.jsx` vert, specs Playwright e2e ADAPTÉES (ouvrir le menu avant de cliquer les `ap-*` déplacés — ils quittent le DOM statique) + gate e2e verte. Files: frontend/src/pages/ventes/DevisList.jsx, frontend/src/pages/ventes/RelancesPage.jsx, frontend/src/pages/crm/leads/BulkActionBar.jsx. (ROUTINE — M, sonnet) (@lane: frontend/ventes-list) (@after: VX7) — DONE 2026-07-11 : PDF/Envoyer/Accepter/Refuser/Générer facture restent visibles sur DevisList, le reste (Éditer, lien interne, variante, design 3D, aperçu, télécharger, BC, chantier, projet, réviser, remise, supérieur, email, supprimer) vit dans UN menu « Plus d'actions » (destructive item pour Supprimer, window.confirm conservé — AlertDialog retiré, plus utilisable proprement dans un DropdownMenuItem). RelancesPage garde Relancer + WhatsApp visibles, menu « Plus » pour Historique/Lettre/Relevé/Relance premium/Exclure. BulkActionBar CRM garde Responsable/Étape/Archiver/Export, menu « Plus » pour Canal/Priorité/Tag/Relance/Planifier activité/Perdu/Restaurer/Supprimer. NOTE — aucun hook e2e réel `ap-*` (data-testid) n'existe sur ces 3 fichiers ni dans les specs Playwright actuelles (`.ap-*` en CSS n'existe que pour l'assignee-picker CRM activities/leads, sans rapport) ; les specs `devis.spec.js`/`receivables.spec.js` ne touchent pas ces boutons de ligne — rien à adapter côté e2e réel. `DevisList.test.jsx` + `DevisListCreerProjet.test.jsx` adaptés pour ouvrir le menu avant de cliquer les actions déplacées (Variante, Design 3D, Copier le lien, Créer projet).
- [x] VX21 — **FactureList à parité de polish avec DevisList (squelette + cockpit trésorerie).** Porter le pattern `DevisTableSkeleton`/`useDelayedLoading` + en-tête stable pendant chargement (DevisList ~39-65, 740-765) vers `frontend/src/pages/ventes/FactureList.jsx` (spinner nu actuel, ~571-577), et remplacer l'unique carte « Encaissé ce mois » (~845) par une rangée de 4 cartes de trésorerie (Encaissé ce mois / Total dû / En retard / À échoir ≤7 j) dérivées des factures déjà chargées — anatomie KPI complète valeur+delta+période, « 4 cartes max, détail sous le pli » (Stripe). **Done =** plus de saut de layout au chargement, un directeur voit la santé de trésorerie d'un coup d'œil, `FactureList.test.jsx` vert. Files: frontend/src/pages/ventes/FactureList.jsx. (ROUTINE — M, sonnet) (@lane: frontend/ventes-list) (@after: VX20) — DONE 2026-07-11 : `FactureTableSkeleton` (8 colonnes) + `useDelayedLoading` portés, en-tête de page (`pageHeader`) désormais toujours visible pendant chargement/erreur (parité DevisList). La carte unique « Encaissé ce mois » devient une rangée de 4 cartes KPI (Encaissé ce mois avec delta vs mois précédent, Total dû, En retard avec nombre de factures, À échoir ≤7 j) — toutes dérivées de `factures` déjà chargé, aucun appel réseau ajouté.

**D — CRM niveau Attio :**
- [x] VX22 — **Une vraie page lead : route `/crm/leads/:id`.** Ajouter la route dédiée qui rend le même `LeadForm` mais adressable : deep-link partageable, F5 rouvre la même fiche (charger via `crmApi.getLead` si pas en mémoire — le `?lead=<id>` actuel dépend du cache de liste), précédent/suivant navigateur fonctionnels, ctrl-clic « ouvrir dans un nouvel onglet » depuis Kanban/Liste ; le flux overlay rapide reste pour le kanban (l'URL se met à jour). L'échelle hover→peek→page d'Attio exige que la « page » existe ; l'état de navigation doit survivre au refresh. **Done =** ouvrir `/crm/leads/42` dans un onglet neuf affiche la fiche sans passer par la liste. Files: frontend/src/router/, frontend/src/pages/crm/leads/LeadsPage.jsx, frontend/src/pages/crm/LeadForm.jsx. (ROUTINE — M, sonnet) (@lane: frontend/crm)
- [x] VX23 — **ChatterTimeline : battre le chatter d'Odoo, pas le sous-imiter.** Remplacer le journal texte plat (`LeadForm.jsx` ~1188-1206) par un composant réutilisable `frontend/src/components/ChatterTimeline.jsx` : regroupement par jour (« Aujourd'hui »/« Hier »/date), `Avatar` par entrée, notes manuelles visuellement distinctes (fond plein) des logs auto de champ (texte discret + icône crayon), pièces jointes récentes injectées dans le fil au lieu d'un onglet séparé. Le chatter est ce qu'Odoo fait le mieux et TAQINOR est aujourd'hui EN DESSOUS ; garder le panneau repliable (l'erreur du chatter toujours-ouvert qui mange l'écran). **Done =** avatars + groupes temporels + distinction note/log visibles, test LeadForm couvrant le rendu. Files: frontend/src/components/ChatterTimeline.jsx (nouveau), frontend/src/pages/crm/LeadForm.jsx. (ROUTINE — M, sonnet) (@lane: frontend/crm) (@after: VX22)
- [x] VX24 — **Anatomie de carte Kanban à 2 niveaux + bandeau résumé de fiche.** Dans `frontend/src/pages/crm/leads/views/LeadCard.jsx` (~112-163) : UNE seule pilule d'alerte prioritaire au premier plan (perdu > rappel > expiré), « Inactif N j » + horloge relégués en pied discret, `ScoreBadge` (extrait de ListView vers `frontend/src/features/crm/ScoreBadge.jsx`) à côté du nom — le score n'existe aujourd'hui QUE dans la vue Liste. Ajouter un `LeadSummaryBar` en tête de `LeadForm.jsx` (~712) : score, montant estimé, prochaine activité, jours depuis dernière modification — le bandeau de faits clés d'Attio. Cartes courtes plafonnées délibérément. **Done =** au plus 2 pilules + score par carte (capture d'un lead cumulant 4 alertes), les 4 faits visibles sans scroller en fiche. Files: frontend/src/pages/crm/leads/views/LeadCard.jsx, frontend/src/features/crm/ScoreBadge.jsx (nouveau), frontend/src/pages/crm/LeadForm.jsx. (ROUTINE — M, sonnet) (@lane: frontend/crm) (@after: VX23)
- [x] VX25 — **MonthGrid partagé + résurrection du calendrier transverse.** Extraire la grille mensuelle (cellules lundi-dimanche, navigation mois, « Aujourd'hui ») en `frontend/src/components/MonthGrid.jsx` paramétré par `renderCell`, puis restyler `frontend/src/pages/CalendarPage.jsx` — le pire écran du CRM : 100 % inline `style={{}}`, ~20 hex codés, boutons `btn btn-light` pré-design-system — sur les mêmes primitives que `leads/views/CalendarView.jsx` (`IconButton`/`Segmented`/tokens sémantiques `--info/--success/--warning`). « Deux calendriers, deux générations de design dans la même app — la preuve la plus nette du gap. » **Done =** plus aucun hex dans CalendarPage, dark mode correct, les deux calendriers importent MonthGrid. Files: frontend/src/components/MonthGrid.jsx (nouveau), frontend/src/pages/CalendarPage.jsx, frontend/src/pages/crm/leads/views/CalendarView.jsx. (ROUTINE — M, sonnet) (@lane: frontend/crm) (@after: VX24)
- [x] VX26 — **Couleurs de stage dérivées des tokens (STAGES.py intact — règle #2 à la lettre).** Ajouter dans `frontend/src/design/tokens.css` les variables `--stage-new/--stage-contacted/--stage-quote-sent/--stage-follow-up/--stage-signed/--stage-cold` dérivées de la palette de marque, et faire pointer `STAGE_COLORS` (`frontend/src/features/crm/stages.js:30-37`), `SCORE_COLORS` (ListView:77-81), `NAVY`/`GOLD` (ChartsView:24-25) et `OWNER_PALETTE` (CalendarView:36-39) vers ces tokens (chaînes `var(--…)` ou résolution `getComputedStyle` pour recharts). Les 6 CLÉS restent importées du module stages aligné STAGES.py — seules les COULEURS changent de source. **Done =** grep hex vide dans les 4 fichiers (hors commentaires), changer un token de marque change visiblement kanban + charts, CI stage-names verte. Files: frontend/src/design/tokens.css, frontend/src/features/crm/stages.js, frontend/src/pages/crm/leads/views/. (ROUTINE — M, sonnet) (@lane: frontend/crm) (@after: VX1)

**E — Cockpits & monitoring vivants :**
- [x] VX27 — **Le cockpit du matin : Dashboard par rôle + bandeau « aujourd'hui ».** Le Directeur, le Commercial et le Technicien SAV voient aujourd'hui EXACTEMENT le même mur de KPI — la lacune la plus stratégique. Brancher un layout par rôle dans `frontend/src/pages/Dashboard.jsx` sur le rôle déjà en store : commercial → « mes leads à relancer / mes devis qui expirent sous 7 j » en tête ; SAV → « mes tickets urgents / SLA en retard » (réutiliser `statusCounts`/`ticketSlaLevel` de `features/sav/ticketStatuses.js`, carte SAV aujourd'hui absente du Dashboard) ; directeur → vue macro actuelle + un métrique héros promu en haut à gauche (pattern F Mercury/Ramp). Ajouter le bandeau compact « 3 interventions aujourd'hui · 2 relances en retard · 1 devis expire » cliquable — aucun nouvel endpoint BACKEND, mais ajouter les fetchs frontend manquants (Dashboard.jsx:187-192 ne charge aujourd'hui ni leads ni tickets SAV — les endpoints existent). **Done =** trois rôles de test affichent des sections de tête différentes, bandeau cliquable correct, test de rendu conditionnel ajouté. Files: frontend/src/pages/Dashboard.jsx. (ROUTINE — L, opus) (@lane: frontend/insight) (@after: VX15)
- [x] VX28 — **Un seul langage de graphique + un seul PageHeader.** Migrer les recharts « à la main » de `Reporting.jsx` (CHART_INFO ~39-49), `Rapports.jsx` (CHART_PRIMARY ~21-23) et `Journal.jsx` (~20-34) vers le kit `frontend/src/ui/charts/` (AreaSansAxe/BarArrondie/ChartTooltip — même easing, mêmes coins, même palette) ; remplacer le composant `Table` local de Rapports.jsx (~64-91) par le `Table` partagé de `pages/reporting/Table.jsx` ; créer `frontend/src/ui/PageHeader.jsx` (titre+sous-titre+actions) et l'adopter sur les 3 idiomes divergents (Dashboard font-display vs `<h2>` nu vs `.page-title` monitoring) sur ~10 écrans. L'incohérence inter-modules est l'erreur Odoo n°6. **Done =** plus aucune constante de couleur recharts locale dans les 3 fichiers, un seul composant Table dans reporting/, PageHeader adopté, e2e headings verts. Files: frontend/src/ui/PageHeader.jsx (nouveau), frontend/src/pages/Reporting.jsx, frontend/src/pages/Rapports.jsx, frontend/src/pages/Journal.jsx. (ROUTINE — M, sonnet) (@lane: frontend/insight) (@after: VX27)
- [x] VX29 — **CommercialDashboard : le restyle « star » de l'écran le plus waouh.** Réécrire `frontend/src/pages/reporting/CommercialDashboard.jsx` — 91 `style={{}}` inline, 13 hex, l'écran le plus daté de l'app — sur les primitives du kit (`Card`/`Badge`/`BarArrondie` pour l'entonnoir au lieu du `<div style={{width: pct%}}>` fait main), et corriger le bug `<EmptyState message="..."/>` (API réelle : `title`/`description` — le texte ne s'affiche probablement pas, ~189/250/283). Son contenu (entonnoir de vélocité par étape, classement commerciaux, gains/pertes par canal) est le candidat parfait au « investor demo gasp » une fois restylé. **Done =** zéro `style={{}}` restant, EmptyState rendu, export xlsx fonctionnel, dark mode correct. Files: frontend/src/pages/reporting/CommercialDashboard.jsx. (ROUTINE — M, sonnet) (@lane: frontend/reporting)
- [x] VX30 — **Le mur de flotte vivant (cartes par centrale + pouls temps réel).** Sur `frontend/src/pages/monitoring/FleetPage.jsx` : un mode grille de cartes par installation (référence, badge statut vert/orange/rouge dérivé du PR déjà calculé ~99-105, kWc, production, mini-sparkline `KpiSpark`) basculable avec le tableau via `Segmented` ; un badge de fraîcheur « Actualisé il y a X min » (extraire le `timeAgo` de TicketsPage.jsx:66-73 en util partagé) + auto-poll léger 5 min sur les écrans monitoring — via `useVisibilityAwarePolling` (VX56) si livré, jamais un `setInterval` nu qui polle un onglet caché (@coord VX56) ; l'état « stale/hors-ligne » visuellement DISTINCT de « production 0 » (un « 0 » peut être un nuage OU un onduleur mort — ils ne doivent jamais se ressembler). **Done =** bascule table/cartes, cartes cliquables vers OmAnalytics, fraîcheur visible et mise à jour, stale ≠ zéro. Files: frontend/src/pages/monitoring/FleetPage.jsx, frontend/src/pages/monitoring/Co2Page.jsx, util timeAgo partagé. (ROUTINE — L, sonnet) (@lane: frontend/monitoring)
- [x] VX31 — **SAV en boîte de réception : split-view liste + détail.** Sur desktop ≥1280px, remplacer le `Sheet` plein-tiroir de `TicketDetail` (`frontend/src/pages/sav/TicketsPage.jsx:453-848`) par un panneau latéral persistant à côté de la DataTable — cliquer un autre ticket met à jour le panneau sans réouverture, la liste reste visible (pattern inbox Linear/Plain) ; `Sheet` conservé en fallback mobile, toutes les `CollapsibleSection` gardées à l'identique. **Done =** sur grand viewport la sélection n'ouvre plus de tiroir, mobile inchangé, `TicketsPage.test.jsx`/`TicketCalendarView.test.jsx` verts. Files: frontend/src/pages/sav/TicketsPage.jsx. (ROUTINE — L, sonnet) (@lane: frontend/sav)

**F — Opérations (les îlots non migrés) :**
- [x] VX32 — **CartePage + MapView rejoignent le design system (la « control room » géographique).** Remplacer tous les `style={{...}}` inline et hex de `frontend/src/pages/CartePage.jsx:84-128` par tokens + composants (`Badge`/`Segmented` pour la légende cliquable, `Select` Radix pour le filtre au lieu du `<select>` natif fond `#fff` figé même en sombre) ; dans `frontend/src/components/MapView.jsx`, thémer les tuiles pour le dark mode (filtre CSS `invert()/hue-rotate()` sur le tileLayer — pattern standard, zéro dépendance) et enrichir le popup d'un vrai bouton « Ouvrir la fiche » (`Button size="sm"`). « L'îlot visuel le plus net de la lane — un prototype 2019 sur l'écran qui devrait incarner la salle de contrôle. » **Done =** zéro `style={{` hors hauteur du conteneur Leaflet, dark mode sans fond blanc figé, légende alignée sur le reste de l'app. Files: frontend/src/pages/CartePage.jsx, frontend/src/components/MapView.jsx. (ROUTINE — M, sonnet) (@lane: frontend/carte)
- [x] VX33 — **Le Pilotage stock devient la tour de contrôle qu'il prétend être.** Ouvrir `PilotageStock` par défaut (aujourd'hui replié derrière un bouton secondaire, StockList.jsx ~1058-1060), migrer ses 4 `SectionRapport` du `<table>` HTML brut (`frontend/src/pages/stock/PilotageStock.jsx:39-74`) vers mini-`DataTable`, ajouter deux graphiques du kit `ui/charts` (barres horizontales « top 5 à réapprovisionner », donut rotation actif/ralenti/immobile) ; en bonus la mini-jauge « santé catalogue » (% avec prix / % avec SKU depuis `noPriceCount`/`noSkuCount`, StockList.jsx ~753-754) au-dessus du rail de catégories. **Done =** pilotage visible par défaut avec 2 charts du kit, jauge santé rendue, tests stock verts. Files: frontend/src/pages/stock/PilotageStock.jsx, frontend/src/pages/stock/StockList.jsx. (ROUTINE — L, sonnet) (@lane: frontend/stock) (@after: VX7)

**G — Fondation, délice, mobile, voix :**
- [x] VX34 — **Login signature (le premier pixel de la marque).** Garder le moment de marque (fond wordmark bondissant) mais le faire entrer dans le système : couleurs `#1863DC`/`#F5C100`/`#050e1f` → tokens OKLCH de `design/tokens.css`, emojis 🙈/👁️/⚠️ → `Eye`/`EyeOff`/`AlertCircle` lucide, `BouncingBackground` statique sous `prefers-reduced-motion`. (PAS de lookup société-par-email AVANT authentification — vecteur d'énumération de comptes + exigerait un endpoint backend nouveau ; si on veut le nom de la société, l'afficher dans la transition POST-login.) **Done =** mêmes teintes via tokens, reduced-motion respecté, aucun emoji-icône restant, flow 2FA inchangé. Files: frontend/src/pages/Login.jsx. (ROUTINE — M, sonnet) (@lane: frontend/login)
- [x] VX35 — **Paramètres : de 22 onglets plats à une vraie architecture d'information.** Remplacer le `TabsList` plat scrollable (`frontend/src/pages/parametres/peConstants.js:27-50`, rendu ParametresEntreprise.jsx ~795-803) par une sidebar verticale groupant les clés en 5-6 familles (Général / Ventes & Devis / Terrain & Stock / Équipe & Sécurité / Automatisation / Avancé — champ `group` par tab), la recherche existante (~L790) en tête de sidebar (`searchSettings` inchangé). Settings-as-sitemap ≤2 niveaux (Stripe/Linear) ; jamais gater un réglage courant derrière un mode caché (erreur Odoo n°3). **Done =** les clés d'onglets inchangées (aucune renommée), la recherche saute au bon endroit, tests sections verts sans modification. Files: frontend/src/pages/parametres/peConstants.js, frontend/src/pages/parametres/ParametresEntreprise.jsx, frontend/src/pages/parametres/SettingsSidebar.jsx (nouveau). (ROUTINE — M, sonnet) (@lane: frontend/parametres)
- [x] VX36 — **L'onboarding sort de sa cachette (bannière Dashboard + first-run).** La checklist « Prise en main » (OnboardingSection, FG16 : profil société / premier produit / inviter un coéquipier) est enterrée dans l'onglet 1 de 24 des Paramètres — invisible au premier login. Extraire les 3 étapes dans un hook `useOnboardingSteps()` partagé et afficher une `OnboardingBanner` (progression + lien direct) en haut de `frontend/src/pages/Dashboard.jsx` tant que `doneCount < steps.length`, masquable définitivement (« Ne plus afficher », persisté par société). « Créer un artefact réel dans la première minute. » (NB vérifié : OnboardingSection calcule ses étapes via `api.get('/users/')` + stock/profil — le hook partagé refera ces appels sur le Dashboard.) **Done =** bannière au premier login, disparaît après complétion/refus, au plus les MÊMES appels que l'onglet Prise en main (une seule fois, réutilisant le store quand présent). Files: frontend/src/pages/Dashboard.jsx, frontend/src/components/OnboardingBanner.jsx (nouveau), frontend/src/features/onboarding/onboardingHelpers.js (nouveau). (ROUTINE — S, sonnet) (@lane: frontend/insight) (@after: VX28)
- [x] VX37 — **L'IA qui « pense » : streaming visuel + preuve lisible par un humain.** Dans `frontend/src/pages/ia/AgentChat.jsx`, remplacer le loader 3-points statique (~360-371) par une révélation incrémentale du texte (le texte complet est déjà côté client — `requestAnimationFrame` mot à mot, aucun changement backend), et rendre la preuve consommable par un non-développeur : quand le payload agent porte des lignes structurées, un mini-tableau de données inline à la place du seul `<details><pre>` SQL brut. La sensation « produit IA 2026 » vient du reveal progressif + citation de données. **Done =** `AgentChat.test.jsx`/voice verts, `data-testid` proposal/result-card inchangés, reduced-motion = texte instantané. Files: frontend/src/pages/ia/AgentChat.jsx. (ROUTINE — M, sonnet) (@lane: frontend/ia)
- [x] VX38 — **Admin cohérent : RolesManagement + documents GED sur DataTable, matrice de permissions.** Porter le `<table>` fait main de `frontend/src/pages/admin/RolesManagement.jsx:489-579` et le tableau documents legacy de `frontend/src/features/ged/GedNavigator.jsx:306-333` vers le moteur `DataTable` (le même que UsersManagement un écran à côté) ; transformer l'éditeur de rôle (12 cartes de checkboxes) en matrice modules × actions (Voir/Créer/Modifier/Supprimer/Exporter, « — » si absent), logique `buildGroups`/`togglePerm` inchangée ; en GED, fil d'Ariane Armoire›Dossier et icônes par type de fichier (`FileImage`/`FileSpreadsheet`… lucide). L'audit « qui peut faire quoi » scannable. **Done =** aucune perte fonctionnelle, tri/recherche gagnés, tests admin/GedNavigator adaptés verts. Files: frontend/src/pages/admin/RolesManagement.jsx, frontend/src/features/ged/GedNavigator.jsx. (ROUTINE — L, sonnet) (@lane: frontend/admin)
- [x] VX39 — **OCR : source et extraction côte à côte + correction inline.** Dans `AnalyseTab` (`frontend/src/pages/ia/OcrUpload.jsx:68-378`), afficher le document source (`URL.createObjectURL(currentFile)`) en aperçu à gauche et la table de champs extraits ÉDITABLE à droite (chaque valeur → `Input` inline, « Valider et enregistrer » envoie les valeurs corrigées) — la boucle de confiance vérifier-puis-corriger est le standard de tout produit OCR sérieux (Klippa/Rossum) et manque totalement. **Done =** la sauvegarde envoie les valeurs corrigées, un test couvre l'édition d'un champ avant sauvegarde. Files: frontend/src/pages/ia/OcrUpload.jsx. (ROUTINE — M, sonnet) (@lane: frontend/ia)
- [x] VX40 — **Le délice mesuré : célébration « devis signé » + états vides illustrés.** Une SEULE célébration dans toute l'app : au passage `envoye→accepte` d'un devis (rare, significatif, lié au revenu), un burst CSS-only (spans absolus animés translate/rotate/fade, AUCUNE lib confetti) autour du toast sonner existant, une fois par transition, jamais au rechargement, statique sous reduced-motion (règle Asana : honorer le rare, jamais gamifier la routine). Et une variante `illustrated` d'`frontend/src/ui/EmptyState.jsx` : pictogramme solaire SVG inline (panneau/soleil stylisé, tons brass/lune) ou cluster d'icônes lucide 48-64px basse opacité, adoptée sur les 4-5 empty states les plus vus (leads, devis, catalogue, GED, carte). **Done =** célébration visible une fois sur acceptation, empty states illustrés en clair+sombre, reduced-motion = toast seul. Files: frontend/src/ui/EmptyState.jsx, frontend/src/ui/celebrate.js (nouveau), point d'appel SigneDialog/DevisList. (ROUTINE — M, sonnet) (@lane: frontend/ui) (@after: VX20)
- [x] VX41 — **Craft data-viz : palette catégorielle de marque, comparaison de période, annotations.** Étendre `frontend/src/ui/charts/chart-theme.js` d'une échelle catégorielle dérivée de la marque (brass, azur, nuit-soft, lune + accents sémantiques) pour les séries multiples (elles retombent aujourd'hui sur un seul ton) et d'un style de grille signature (pointillés très légers, horizontaux seuls, pas de ligne d'axe — data-ink Tufte) ; ajouter la série « période précédente » en pointillé togglable sur le CA mensuel de `Dashboard.jsx` (~484-492) et `Reporting.jsx` (~327-349) (mêmes données décalées, zéro appel API — une référence superposée bat deux graphiques) ; supporter `ReferenceLine` annotée pour les événements (marqueur maintenance sur une courbe de production). **Done =** un chart multi-séries montre la palette distincte en clair+sombre, comparaison togglable avec légende claire, test chart-theme à jour. Files: frontend/src/ui/charts/chart-theme.js, frontend/src/ui/charts/ChartFrame.jsx, frontend/src/pages/Dashboard.jsx, frontend/src/pages/Reporting.jsx. (ROUTINE — M, sonnet) (@lane: frontend/insight) (@after: VX36)
- [x] VX42 — **Terrain un-tap : appeler/naviguer sur Ma journée + FAB + retour haptique.** Trois gestes natifs à coût quasi nul : (1) deux boutons directs ≥44px (téléphone, navigation maps universelle) sur chaque carte de `frontend/src/pages/interventions/MaJourneePage.jsx:78-112` — l'action la plus fréquente d'un technicien garé est aujourd'hui à 3 taps dans l'onglet Trajet ; remplacer les 9 `TabsTrigger` icône-seule par un rail scrollable icône+libellé court avec bandeau « Prochaine action » (pattern `ch6-next-action` de ChantierGateTimeline) ; (2) un `frontend/src/ui/FloatingActionButton.jsx` (fixed, safe-area + hauteur BottomTabBar) posé sur NumeriserPage, leads mobile (« Nouveau lead ») et Ma journée (« Photo rapide ») — le pouce vit dans le tiers bas de l'écran ; (3) `navigator.vibrate?.(10)` défensif après capture photo validée, signature, changement de statut, scan réussi (`CameraCapture.jsx`, `SignaturePad.jsx`, `InterventionsPage.jsx`, `useBarcodeScanner.js`). **Done =** boutons visibles sans ouvrir le sheet (masqués si donnée absente), FAB sous 768px au-dessus de la tab bar, vibration silencieuse si API absente, tests Playwright mobile. Files: frontend/src/pages/interventions/MaJourneePage.jsx, frontend/src/ui/FloatingActionButton.jsx (nouveau), + points haptiques cités. (ROUTINE — L, sonnet) (@lane: frontend/terrain)
- [x] VX43 — **Gestes natifs : swipe-to-action, pull-to-refresh, sheets cohérents.** (1) Swipe horizontal maison (`touchstart/move/end`, seuil de distance anti-scroll, zéro dépendance) sur `LeadCard.jsx` et les cartes mobiles du `DataTable` (`data-dt-cards`, prop `swipeActions` rétrocompatible) révélant Appeler/WhatsApp ≥44px — LE geste iOS attendu, les liens tel:/wa.me existent déjà (LeadCard.jsx:79-80) mais en texte 12px noyé. (2) Pull-to-refresh maison (hook `usePullToRefresh`, transform CSS quand scroll=0) sur Ma journée, Interventions et le kanban leads — `overscroll-behavior: contain` a coupé le rubber-band sans rien mettre à la place. (3) Aligner les sheets terrain (`MaJourneePage` `side="right"`, InterventionsPage) sur le bottom-sheet mobile via `ResponsiveDialog`/`Sheet side="bottom"` + glisser-vers-le-bas-pour-fermer dans `frontend/src/ui/Sheet.jsx`, et un repli « changer le statut au menu » sans drag sur `InterventionCard` sous 768px. Ressort sous le doigt uniquement. **Done =** swipe sans conflit avec le scroll vertical, pull relance les fetch existants, sheets terrain s'ouvrent du bas et se ferment au glissé, gate Playwright mobile verte. Files: frontend/src/pages/crm/leads/views/LeadCard.jsx, frontend/src/ui/datatable/DataTable.jsx, frontend/src/ui/usePullToRefresh.js (nouveau), frontend/src/ui/Sheet.jsx, frontend/src/pages/interventions/. (ROUTINE — L, sonnet) (@lane: frontend/terrain) (@after: VX42, VX45)
- [x] VX44 — **Photos chantier en rafale + partage natif WhatsApp.** (1) Porter le pattern multi-pages de `NumeriserPage.jsx` (`pages: [{id, file, rotation}]`, vignettes retirer/tourner avant envoi groupé) vers `PhotosPanel` de `frontend/src/features/installations/InterventionFieldExecution.jsx` — un technicien prend 3-6 photos de suite sans rouvrir la caméra ; enrichir `frontend/src/pages/installations/ChantierPhotos.jsx` d'un compteur de complétion (« 12 photos · 3 phases couvertes ») + badge sur les phases vides via `photos_obligatoires_manquantes` déjà exposé. (2) Préférer `navigator.share({files})` (Web Share API, iOS 15+) au lien de téléchargement pour envoyer le PDF de devis/rapport droit dans WhatsApp, avec repli téléchargement — et généraliser les liens `wa.me` PRÉ-REMPLIS contextuels sur les actions « contacter le client ». N'ajoute AUCUN chemin PDF : on partage le PDF `/proposal` existant (règle #4). **Done =** rafale + réordonnancement avant upload vers l'endpoint existant, share sheet natif quand disponible, messages wa.me pré-remplis en français. Files: frontend/src/features/installations/InterventionFieldExecution.jsx, frontend/src/pages/installations/ChantierPhotos.jsx, frontend/src/pages/ventes/DevisList.jsx (action partager). (ROUTINE — M, sonnet) (@lane: frontend/terrain) (@after: VX43, VX40)
- [x] VX45 — **La voix TAQINOR : microcopie FR premium + fin des emojis-icônes.** Deux passes fines : (1) copy-only sur les toasts/dialogs/empty-states les plus visibles au registre Doctolib — la chaleur par la clarté (« Devis enregistré. » pas « Opération réussie ! » ; erreurs = quoi + prochaine étape ; chargements nommés « Génération du PDF… ») + une section « Voix & microcopie » documentée dans `frontend/src/pages/ui/UIShowcase.jsx` ; (2) remplacer les emojis fonctionnels 💡🏠⚡📝📎🕐📈👤💧 de `frontend/src/pages/crm/LeadForm.jsx` et `LeadCard.jsx` (+ boutons de LeadsPage ⚡🔀) par les lucide équivalents (`Zap`, `Home`, `FileText`, `Paperclip`, `Clock`, `Phone`, `MessageCircle`…) — le rendu emoji varie par OS et casse le système d'icônes. **Done =** titres de section avec prop `icon` lucide, aucun emoji fonctionnel restant dans crm/, 6+ chaînes clés relues, e2e textes verts. Files: frontend/src/pages/crm/LeadForm.jsx, frontend/src/pages/crm/leads/views/LeadCard.jsx, frontend/src/pages/ui/UIShowcase.jsx. (ROUTINE — S, haiku) (@lane: frontend/crm) (@after: VX25)

**H — Compléments (critique de complétude Fable, 2026-07-07 — deux espaces blancs confirmés absents de TOUS les plans) :**
- [x] VX46 — **« Mes préférences » : un centre de personnalisation par utilisateur.** La personnalisation existe mais est éparpillée et sans surface : thème (ThemeToggle header), apps épinglées (VX10, localStorage), densité (tokens F120 sans aucune UI), vues sauvegardées DataTable (par table), module d'atterrissage au login (n'existe pas). Créer une petite surface « Mes préférences » (entrée du menu utilisateur du header) regroupant : thème clair/sombre/système, densité par défaut (compact/confort/spacieux appliquée aux DataTable), module d'atterrissage au login (liste depuis `moduleConfigs`, réutilise `taqinor.lastModule` de VX11), réduction de mouvement (override app du media query) — persistance `localStorage` par utilisateur (motif `COLLAPSE_KEY`), AUCUN nouvel endpoint backend. **Done =** chaque préférence persiste au rechargement, le module d'atterrissage redirige au login, la densité s'applique aux tables, tests de la logique pure. Files: frontend/src/pages/preferences/ (nouveau, ou section du menu utilisateur), frontend/src/components/layout/Header.jsx. (ROUTINE — M, sonnet) (@lane: frontend/shell) (@after: VX14)
- [x] VX47 — **Aide contextuelle intégrée : popovers « ? » sur les écrans difficiles.** L'overlay `?` (I138) n'explique que les raccourcis et `/ui` est développeur-facing ; aucun écran métier n'explique ses concepts à un nouvel employé. Créer un composant `HelpTip` (petit `IconButton` « ? » discret + `Popover` du kit, contenu FR concis de 2-4 phrases, jamais de doc externe) et le poser sur les 5-6 zones les plus dures : grille d'écriture comptable (débit=crédit), assistant de paie (review-before-commit), gates de chantier (bloquant vs consultatif), score de lead (d'où vient le chiffre — pose VX24), distributeur/tranches du générateur de devis, et l'écran Applications quand ODX5 livrera. **Done =** `HelpTip` réutilisable + ≥5 poses réelles, aucun re-layout au clic, tests de rendu. Files: frontend/src/ui/HelpTip.jsx (nouveau), les écrans cités. (ROUTINE — M, sonnet) (@lane: frontend/ui) (@after: VX40)

---

**ROUND 2 (2026-07-08) — « le meilleur dans TOUS les aspects » : perfection appareils, vitesse, résilience, locale, portes CI.**
*Le fondateur a challengé : « êtes-vous sûrs qu'avec ces tâches ce sera le meilleur ? je veux le meilleur dans TOUS
les aspects, y compris marcher parfaitement sur téléphones et ordinateurs ». Réponse honnête : VX1-47 rend l'app la
plus belle et la mieux organisée — mais « belle » et « marche parfaitement partout » sont deux chantiers. Un second
balayage (11 agents : matrice appareils/Safari, performance réelle, résilience, locale, surfaces secondaires, portes
CI + recherche best-practices + carte anti-duplication + synthèse Fable) a trouvé des CASSES réelles prouvées dans le
code : sur iPhone Safari AUCUN PDF ne s'ouvre (window.open après un await = bloqué en silence, ~10 écrans) et la CI
mobile ne teste que Chrome donc ne peut pas l'attraper ; au-delà de 100 lignes les listes stock/devis/factures/clients
et les KPI du Dashboard MENTENT (troncature silencieuse page 1 DRF) ; le formulaire de devis (20 min de saisie) n'a
ni brouillon ni garde de sortie ; la liste factures sur téléphone empile des valeurs SANS étiquettes ; le sélecteur
de langue promet EN/AR mais ~2 % de l'app est traduite ; les emails partent en texte brut sans logo ; zéro style
d'impression. VX48-82 répare tout cela ET installe les portes CI (WebKit/iPad/zoom/régression visuelle/axe dynamique)
pour que « parfait » le RESTE. Dédupliqué contre YHARD7/8, YTEST, YAPIC, YDATA, FG386, QPERF1 (chacun cité là où on
s'y adosse). Les vérifs de l'orchestrateur ont corrigé les chemins des slices (`features/*/store/*Slice.js`).*

*Coordination avec le **Groupe ARC** (PLAN.md, ajouté 2026-07-08 via PR #333 — socle plateforme) : ARC a dédupliqué
contre VX1-47 nommément ; les points de contact round 2 sont (a) **ARC49/ARC53** (DevisList/FactureList → moteur
DataTable) possèdent désormais la migration que le NE PAS FAIRE round 1 différait — elles doivent atterrir APRÈS
les tâches VX touchant ces fichiers (VX7/20/21/40/44/48/50/52/63/79/80) et préserver leurs comportements ;
(b) **ARC45** (`useResource` fetch/état mutualisé) est la généralisation architecturale des fixes ciblés VX54/55/67 —
les fixes passent d'abord, ARC45 les absorbe ; (c) **ARC39** (plus d'email brut interne, routage notifications) est
complémentaire de VX76 (le TEMPLATE que les deux goulots rendent).*

**I — Cassé AUJOURD'HUI sur téléphone / Safari / tactile :**
- [x] VX48 — **[BUG iOS] Ouvrir tous les PDF via un onglet pré-ouvert AVANT l'await (le bug le plus grave du parc).** Safari iOS bloque en silence tout `window.open()`/clic programmatique qui suit un `await` : aujourd'hui sur iPhone, AUCUN PDF ne s'ouvre depuis l'app (prouvé sur ~10 écrans). Créer `openPdfInGesture()` dans `frontend/src/utils/pdfBlob.js` : ouvrir synchroniquement un onglet vide dans le handler de tap, puis `w.location = objectUrl` quand le blob arrive. Câbler dans `DevisList.jsx:494-496`, `LeadDevisPanel.jsx:214-215`, `features/contrats/LocationPage.jsx:84` + `ContratDetail.jsx:86`, `stock/StockList.jsx:681`, `ReceptionsFournisseur.jsx:279`, `features/rh/EmployeDetail.jsx:125`, `installations/InstallationDetail.jsx:603`, `OmReportPage.jsx:61` ; dans `FactureList.jsx`, remplacer le CLONE LOCAL `openPdfBlob` (`:106`, utilisé aux `:357/:417/:456/:519`) par le helper partagé — et traiter aussi le lien de paiement `:503` (un `window.open` après await, pas un PDF) ou l'exclure explicitement avec raison. **NE PAS régresser QG1** (plainte fondateur « second clic » — l'auto-open `DevisList.jsx:593-622` reste l'expérience par défaut) : tenter l'auto-open existant D'ABORD et n'afficher le toast d'action « PDF prêt — Ouvrir » (tap = geste frais) QUE quand l'ouverture est bloquée (détection null/fenêtre-inerte fournie par VX49). **Done =** `pdfBlob.test` couvre le helper (geste→onglet, blocage→toast) ; l'auto-open desktop est inchangé (test QG1 vert) ; zéro changement au rendu PDF ni à `/proposal` (règle #4 — déclenchement client uniquement). La preuve WebKit rouge/vert vit dans VX68. Files: frontend/src/utils/pdfBlob.js + les écrans cités. (ROUTINE — M, opus : chemin de l'argent) (@lane: frontend/pdf-open) *(@coord VX20/VX44/VX63/VX79/VX80 touchent DevisList/FactureList — rebase.)*
- [x] VX49 — **Détection réelle du blocage popup + gestion d'erreur des ~49 téléchargements blob.** Durcir `ouvrirPdfBlob` (`pdfBlob.js:4-11`, vérifié) : Safari renvoie parfois un objet fenêtre inerte non-null → tester `w == null || w.closed || typeof w.closed === 'undefined'` et afficher un toast d'action « Ouverture bloquée — Télécharger le PDF » au lieu d'échouer en silence (aujourd'hui seul `null` déclenche le repli). Au même passage, envelopper les téléchargements blob sans gestion d'erreur (~49 sites, patron `URL.createObjectURL`) d'un `try/catch` → toast FR + `revokeObjectURL` en `finally` (fuite mémoire sur échecs répétés). **Done =** vitest : `window.open` renvoyant `null` PUIS un objet inerte déclenche le repli dans les deux cas ; un blob invalide produit un toast et zéro URL orpheline. Files: frontend/src/utils/pdfBlob.js, frontend/src/utils/downloadBlob.js. (ROUTINE — S, sonnet) (@lane: frontend/pdf-open) (@after: VX48)
- [x] VX50 — **[BUG mobile] `data-label` sur les tables financières + garde CI anti-régression.** Sous 768px `.data-table` se replie en cartes qui n'affichent le nom du champ que via `content: attr(data-label)` — or `FactureList.jsx` (tables ~770 et ~955, grep vérifié : ZÉRO data-label) et `RelancesPage.jsx:265` n'en ont aucun : sur iPhone une facture est une pile de valeurs nues. Ajouter `data-label` sur chaque `<td>` (patron DevisList), `m-hide` sur les colonnes décoratives ; puis un test statique `data-label.guard.test.js` (fs+regex, zéro dépendance) qui échoue si un fichier de `pages/**` contenant `className="data-table"` a des `<td>` mais zéro `data-label`. **Done =** Playwright mobile 390px sur `/ventes/factures` et `/ventes/relances` : au moins une carte affiche un libellé visible ; la garde est rouge avant le fix, verte après. Files: frontend/src/pages/ventes/FactureList.jsx, frontend/src/pages/ventes/RelancesPage.jsx, frontend/src/ui/datatable/data-label.guard.test.js (nouveau). (ROUTINE — S, haiku) (@lane: frontend/ventes-list) (@after: VX21) — DONE 2026-07-11 : `data-label` ajouté sur chaque `<td>` de `FactureRow` (Client/Émission/Échéance/Total TTC/Statut) + la mini-table avoir (Désignation/Qté facturée/Qté à créditer), et sur `RelancesPage` (Client/Échéance/Dû/Retard/Niveau, `m-hide` sur Âge/Relances décoratifs). Garde `data-label.guard.test.js` (Node natif, `node --test`, zéro dépendance) scanne tout `pages/**` ; confirmée rouge (2 offenders détectés) puis verte après le fix. Le scan a aussi trouvé 2 fichiers préexistants avec le même bug hors périmètre de cette tâche (`admin/TenantsConsole.jsx`, `ventes/VentesKanban.jsx`) — whitelistés explicitement dans la garde avec commentaire + tâche de suivi spawnée (task_b32ff05e) pour les corriger séparément.
- [x] VX51 — **Le champ focalisé ne passe plus SOUS le clavier iOS (VisualViewport).** `grep visualViewport` = néant : sur LeadForm/DevisGenerator, un champ bas de page reste caché derrière le clavier iOS — on tape sans voir. Créer `frontend/src/hooks/useKeyboardAwareScroll.js` : sur `visualViewport` `resize`/`scroll`, si `document.activeElement` est sous le bord du clavier → `scrollIntoView({block:'center'})` (lecture en `requestAnimationFrame`) ; no-op silencieux si l'API est absente. Monter dans LeadForm + DevisGenerator. **Done =** Playwright WebKit : focus d'un champ bas + réduction simulée du viewport → le champ reste dans le cadre — rouge avant, vert après ; vitest no-op sans API ; noté que le clavier RÉEL reste un contrôle manuel. Files: frontend/src/hooks/useKeyboardAwareScroll.js (nouveau), frontend/src/pages/crm/LeadForm.jsx, frontend/src/pages/ventes/DevisGenerator.jsx. (ROUTINE — M, sonnet) (@lane: frontend/forms) (@after: VX62, VX24)
- [x] VX52 — **Les avertissements de conformité en `title=` seul deviennent visibles au tactile.** Quatre informations légales/critiques de `FactureList.jsx` ne vivent QUE dans l'attribut `title` (survol souris) : « Mentions légales manquantes (Art. 145) » (~1018), l'édition d'échéance (~1040), le statut de télédéclaration (~1066), « Facture échue » (~1086) — sur iPhone/iPad l'utilisateur ne peut PAS les lire. Badge mentions → `Popover` Radix tapable ; échéance → bouton à label accessible ; télédéclaration/échue → texte explicite dans la carte mobile. Étendre si le grep retrouve le même patron ailleurs. **Done =** Playwright mobile : taper le badge révèle la liste sans survol ; `getByText` trouve la télédéclaration sans hover ; hooks e2e intacts. Files: frontend/src/pages/ventes/FactureList.jsx. (ROUTINE — S, sonnet) (@lane: frontend/ventes-list) (@after: VX50)
- [x] VX53 — **Balayage compat mécanique : garde `@media (hover:hover)`, dvh d'AgentChat, `loading="lazy"`, feedback clipboard.** En une passe : (1) envelopper les `:hover` porteurs d'affordance de `index.css` + `records-panels.css` (~85 non gardés) dans `@media (hover: hover)` avec état permanent en pointeur grossier — jamais gater l'UNIQUE chemin d'une action derrière un survol ; (2) `AgentChat.jsx` : `h-[calc(100vh-7rem)]` → équivalent dvh (la barre d'URL iOS le rétrécit) ; (3) `loading="lazy"` sur les ~22 `<img>` hors-écran (GED/pièces jointes/KB) ; (4) toast succès/échec sur les copies presse-papiers silencieuses. NE PAS toucher les révélations que VX7 re-pèse (design) — ici seule la joignabilité tactile compte. **Done =** projet tactile (VX68) : les actions autrefois hover-only sont atteignables sans survol ; grep des `:hover` non gardés ≈ 0 hors liste blanche ; AgentChat ne déborde plus. Files: frontend/src/index.css, frontend/src/styles/records-panels.css, frontend/src/pages/ia/AgentChat.jsx + les `<img>` cités. (ROUTINE — M, sonnet) (@lane: frontend/css-compat) (@after: VX7)

**J — Vitesse réelle sur 3G/4G marocaine (et chiffres JUSTES) :**
- [x] VX54 — **[BUG données] Fin de la troncature silencieuse à 100 lignes + pagination PARALLÈLE partout.** Le bug de données le plus grave du frontend : `fetchProduits`/`fetchDevis`/`fetchFactures`/`fetchClients` prennent `payload.results` de la page 1 DRF (PAGE_SIZE=100) et jettent le reste (vérifié : `features/stock/store/stockSlice.js:190/215/225/233` + équivalents ventes/crm) — StockList, DevisList, FactureList ET les KPI/graphiques du Dashboard sont FAUX dès 101 enregistrements, sans indicateur. Corriger : page 1 → lire `count`, puis `Promise.all` borné et concaténer en ordre — concurrence ~20 par défaut MAIS **~3-5 MAX pour les DEVIS** tant que QPERF1 (N+1 backend : ~38-109 requêtes SQL PAR page de devis) n'est pas corrigé, sinon ~20 pages parallèles = ~2 000 requêtes SQL quasi simultanées auto-infligées au Postgres à chaque montage de DevisList (@coord QPERF1 — relever la borne quand il atterrit). Au même passage, corriger les QUATRE while sériels identiques : `fetchLeads` (`features/crm/store/crmSlice.js:49`, vérifié), `installationsSlice.js:8-20`, `sav/ticketsSlice.js:8-24` et `sav/equipementsSlice.js` — les écrans des TECHNICIENS TERRAIN gèlent plusieurs secondes à 250-500 ms de RTT — même forme parallèle bornée. **Done =** vitest slices : payload final = total d'une réponse multi-pages mockée ; test timing : les pages 2/3 partent sans s'attendre ; la borne devis ≤5 est testée ; vérif Slow-3G : requêtes concurrentes, pas un escalier. Files: frontend/src/features/stock/store/stockSlice.js, frontend/src/features/ventes/store (slices devis/factures), frontend/src/features/crm/store/crmSlice.js, frontend/src/features/installations/installationsSlice.js, frontend/src/features/sav/ticketsSlice.js + equipementsSlice.js. (ROUTINE — M, sonnet) (@lane: frontend/data)
- [x] VX55 — **Discipline réseau : timeout axios global + annulation des requêtes obsolètes.** Aucun `timeout` sur l'instance axios (`api/axios.js`, vérifié) et ZÉRO `AbortController` dans l'app : sur 3G qui cale, un écran gèle indéfiniment, et une réponse tardive peut écraser l'état d'un AUTRE écran après navigation. Ajouter `timeout: 20000` + `ECONNABORTED` dans l'intercepteur → toast FR « La connexion a expiré » distinct de l'échec générique ; câbler l'annulation via `createAsyncThunk` `{signal}` + `thunk.abort()` au cleanup d'effet sur LeadsPage, DevisList, ClientList (RTK natif, zéro dépendance). **Done =** vitest : requête jamais résolue → interception à 20 s ; monter/démonter LeadsPage → `meta.aborted === true` ; deux requêtes rapprochées → l'état affiché = la plus récente DEMANDÉE. Files: frontend/src/api/axios.js, les 3 écrans cités. (ROUTINE — M, sonnet) (@lane: frontend/data) (@after: VX54)
- [x] VX56 — **NotificationBell cesse de poller un onglet caché.** `NotificationBell.jsx:140-152` installe deux `setInterval` (30 s + 3 min) sans écoute `visibilitychange` — radio/batterie/données gaspillées sur le 4G des techniciens, alors que le patron correct existe dans `useChatPolling.js:91-104`. Extraire un hook `useVisibilityAwarePolling` partagé (stop caché, refresh immédiat au retour) utilisé par les deux features. Ne touche PAS le monitoring (VX30) ni les onglets du panneau (VX14). **Done =** test miroir de `useChatPolling.test` : les deux intervalles s'arrêtent sur hidden et reprennent avec refresh au retour. Files: frontend/src/hooks/useVisibilityAwarePolling.js (nouveau), frontend/src/components/layout/NotificationBell.jsx, frontend/src/features/messaging/useChatPolling.js. (ROUTINE — S, sonnet) (@lane: frontend/shell) (@after: VX14)
- [x] VX57 — **Alléger le chemin froid : `sora.css` hors du rendu-bloquant + CopilotPanel paresseux.** (1) `sora.css` est une ressource bloquante de `index.html:14` (vérifié) pour une police utilisée uniquement par `/landing` — retirer le `<link>` et importer depuis le module Landing (Vite le rattache au chunk lazy) ; (2) `CopilotPanel` est monté en dur sur chaque écran authentifié (`Layout.jsx:84`) — passer en `React.lazy` + rendu seulement quand `copilotOpen` a été vrai une fois (patron AgentChat). **Done =** `dist/index.html` sans lien sora ; trace réseau de `/login` : zéro requête sora ; `/landing` rend toujours Sora ; chaîne distinctive de CopilotPanel absente des chunks pré-interaction ; tests copilot verts. Files: frontend/index.html, frontend/src/pages/Landing.jsx, frontend/src/components/layout/Layout.jsx. (ROUTINE — S, sonnet) (@lane: frontend/boot)
- [x] VX58 — **Préchargement au survol/focus des destinations chaudes de la Sidebar (adaptatif).** Zéro prefetch : chaque clic Sidebar paie le chunk lazy PUIS le fetch, en série. Exposer `router/prefetchMap.js` (les MÊMES imports dynamiques que `router/index.jsx` — une seule source) et déclencher sur `onMouseEnter`/`onFocus` des 5-8 liens les plus fréquents. Garde adaptative : rien si `navigator.connection?.saveData` ou `effectiveType` ∈ {2g, slow-2g} (feature-detect, no-op Safari). **Done =** vitest : hover → import mocké invoqué ; `saveData:true` → zéro invocation ; devtools : le chunk part au `mouseenter`. Files: frontend/src/router/prefetchMap.js (nouveau), frontend/src/components/layout/Sidebar.jsx. (ROUTINE — M, sonnet) (@lane: frontend/boot) (@after: VX57)
- [x] VX59 — **Nom de chunk roof-tool indépendant de la machine (hygiène du gate YHARD7).** Le plugin `roofBuilderTsPlugin` (`vite.config.js:44-86`) encode le chemin ABSOLU du disque dans l'id de module virtuel, qui fuit dans le nom du chunk émis — non portable entre machines/CI et structure du disque local publiée dans un asset. Encoder un chemin RELATIF à `WEB_SRC`, décodage par re-jointure. **Done =** build depuis deux chemins différents → même préfixe de nom ; `check-bundle-budget` passe et étiquette toujours le bucket roof-tool. Files: frontend/vite.config.js. (ROUTINE — S, sonnet) (@lane: frontend/build)
- [x] VX60 — **Gate e2e « comptes justes » : >100 enregistrements affichés en entier (sans polluer la base e2e partagée).** Verrouiller VX54 pour toujours : un spec Playwright qui seed >100 produits et >100 devis via `page.request` + cookie admin (patron `receivables.spec.js:14`), ouvre `/stock` et `/ventes/devis`, et asserte que le compteur rendu et le KPI Dashboard = le total réel (pas 100). ATTENTION : la suite roule sur UNE base `seed_demo` partagée, `workers:1` — les +200 lignes persisteraient pour tous les specs suivants ET fausseraient les baselines `@visual` de release-verify. **Done =** le spec NETTOIE en `afterAll` (suppression des lignes créées) OU vit dans un projet dédié exécuté en dernier et exclu de release-verify ; rouge si on ré-introduit l'appel single-page ; vert sur le code corrigé ; les autres specs restent verts après son passage. Files: frontend/e2e/ (nouveau spec). (ROUTINE — M, sonnet) (@lane: frontend/e2e-data) (@after: VX54)
- [x] VX61 — **[GATED: new dep web-vitals ~2KB] [backend-collection] Mesure des Web Vitals RÉELS (INP/LCP/CLS) → reporting maison.** YHARD7 mesure le BUILD, rien ne mesure le TERRAIN. Frontend : capter INP/LCP/CLS/TTFB, envoyer via `navigator.sendBeacon` (repli `fetch keepalive`) — la lib `web-vitals` (Google, MIT, ~2KB — GATED) OU un hand-roll `PerformanceObserver` si refusée. Backend (exception autorisée) : `POST /api/django/reporting/vitals/` dans l'app reporting existante (une ligne par métrique, company-scopée serveur) + un agrégat p75 par route. Cible : INP ≤ 200 ms / LCP ≤ 2,5 s au p75. **Done =** beacon visible à la navigation ; test backend : POST → ligne créée, scoping forcé ; la table est ENREGISTRÉE au registre de rétention (YOPSB10, livré — une ligne par métrique par navigation = croissance rapide, purge programmée) ; impact bundle ≤ 3 KB gzip (budget YHARD7 inchangé). Files: frontend/src/lib/vitals.js (nouveau), apps/reporting/ (endpoint), tests. (DEP — M, sonnet ; noter au DONE LOG) (@lane: frontend/vitals)

**K — Ne JAMAIS perdre le travail :**
- [x] VX62 — **Brouillon auto + garde de sortie sur DevisGenerator (le formulaire à 20 minutes).** `/ventes/devis/nouveau` (2 319 lignes, 64 `useState`) n'a NI `useDirtyGuard` NI brouillon : un clic malheureux, un swipe retour, un onglet fermé = 20 minutes perdues sans confirmation. Créer `frontend/src/ui/useDraftAutosave.js` (debounce 800 ms → localStorage, clé scopée lead/client/editDevis), bandeau « Reprendre le brouillon du [date] » Restaurer/Ignorer au montage, purge au succès ; câbler AUSSI `useDirtyGuard(dirty)` ; étendre au bouton « Aller à la page de connexion » de `SessionProvider.jsx:77-80` (confirmation si un formulaire dirty est monté). Garde `noValidate`/`step="any"` intacte. **Done =** vitest fake-timers : remplir → recharger → brouillon restauré ; submit réussi → clé vidée ; navigation pendant saisie → confirmation. Files: frontend/src/ui/useDraftAutosave.js (nouveau), frontend/src/pages/ventes/DevisGenerator.jsx, frontend/src/providers/SessionProvider.jsx. (ROUTINE — M, sonnet) (@lane: frontend/ventes-gen) (@after: VX18)
- [x] VX63 — **Fin du JSON brut à l'écran : erreurs lisibles + Réessayer sur DevisList (et chasse aux clones).** `DevisList.jsx:806-812` affiche `JSON.stringify(error)` sur un échec — un vendeur voit littéralement `{"detail":"Authentication credentials..."}` sans bouton Réessayer. Remplacer par `errorMessageFrom(error)` (déjà exporté de `lib/toast.js:92-107`) + un bouton relançant le thunk ; grep `JSON.stringify(err` sous `pages/` et corriger les jumeaux. **Done =** vitest : rejet `{detail}` → texte FR lisible, Réessayer relance. Files: frontend/src/pages/ventes/DevisList.jsx + occurrences jumelles. (ROUTINE — S, haiku) (@lane: frontend/ventes-list) (@after: VX52)
- [x] VX64 — **Error boundaries sur les routes nues : `/ui`, `/`, `/login` et TOUTES les pages publiques tokenisées.** Les routes sans layout (`/rdv/:token`, `/portail-contrats/:token`, `/ged/signature/:token`, `/kiosque`, `/e/:token`, `/suivi/:token`… `router/index.jsx:209-234`) n'ont AUCUNE boundary : un throw de rendu = page blanche — montrée à des CLIENTS externes sur des flux de signature légale. Envelopper chaque élément avec le `RouteErrorBoundary` existant, sans layout ERP autour. **Done =** vitest : chaque route avec un enfant qui throw → écran de récupération FR ; vérif manuelle `/ui`. Files: frontend/src/router/index.jsx. (ROUTINE — S, sonnet) (@lane: frontend/router)
- [x] VX65 — **Le lien profond survit à la connexion : `?next=` au redirect `/login`.** `authLoader`/`roleLoader` redirigent vers `/login` sans capturer l'URL d'origine, et `Login.jsx:165` navigue en dur vers `/dashboard` : un lien WhatsApp/email vers un devis précis perd sa destination si la session avait expiré. Capturer `?next=` (depuis le `Request` du loader) ; au succès, suivre `next` SEULEMENT s'il commence par `/` et pas `//` (garde anti-open-redirect). **Done =** vitest : connexion avec `?next=/crm/leads` → `/crm/leads` ; `next=//evil.com` → ignoré. Files: frontend/src/router/index.jsx, frontend/src/pages/Login.jsx. (ROUTINE — S, sonnet) (@lane: frontend/router) (@after: VX64)
- [x] VX66 — **Filet anti-double-soumission au niveau du composant `Button`.** La protection dépend de la discipline `loading={saving}` écran par écran (fenêtre d'un rendu React) : deux taps rapides peuvent créer deux devis/paiements. Dans `frontend/src/ui/Button.jsx`, garde interne (défaut sur `type="submit"`, prop opt-out) qui désactive IMPÉRATIVEMENT au premier `click` (avant le prochain rendu), ré-armée quand `loading` redescend. **Done =** vitest : deux clics synchrones → `onClick` UNE fois ; non-régression des tests Button. Files: frontend/src/ui/Button.jsx. (ROUTINE — S, sonnet : composant central) (@lane: frontend/ui-core)
- [x] VX67 — **Déployer `StateBlock` (chargement/vide/erreur + Réessayer) sur les 5 listes principales.** `components/StateBlock.jsx` existe, se documente comme « déploiement différé », et n'est importé que dans 2 fichiers (AgentChat, CopilotPanel) : ~30 pages gèrent l'erreur chacune à sa façon, souvent sans retry. Migrer DevisList, ClientList, Dashboard, Rapports, BalanceAgeePage vers `<StateBlock loading error empty onRetry />`, chaque `onRetry` relançant le thunk d'origine. **Done =** vitest par écran : 3 états + retry ; e2e rejouée sans régression. Files: les 5 pages + frontend/src/components/StateBlock.jsx. (ROUTINE — M, sonnet) (@lane: frontend/states) (@after: VX63)

**L — Les portes CI qui verrouillent tout pour toujours (WORTH-IT uniquement, per recherche) :**
- [x] VX68 — **Le gate e2e apprend Safari et l'iPad : projets WebKit + tablet dans Playwright.** `playwright.config.js` : le projet « mobile » est Chromium + UA iPhone (vérifié :61) — AUCUN moteur WebKit, aucun viewport 768-1024, donc rien de ce qui casse sur Safari n'est jamais capté. Ajouter (a) un projet `mobile-safari` `...devices['iPhone 13']` (WebKit RÉEL) exécutant le spec mobile, (b) un projet `tablet` `...devices['iPad (gen 7) landscape']` + `e2e/tablet.spec.js` : pas de débordement + affordances tri/actions atteignables SANS survol sur `/ventes/factures`, `/crm/leads`, `/chantiers`. Chromium actuel = smoke rapide ; PR-only ; PAS de Firefox. `ci.yml` : `npx playwright install webkit`. **Done =** les deux projets verts en CI ; le projet WebKit fait échouer VX48 si on le régresse. Files: frontend/playwright.config.js, frontend/e2e/tablet.spec.js (nouveau), .github/workflows/ci.yml. (ROUTINE — M, sonnet) (@lane: frontend/e2e) (@after: VX48)
- [x] VX69 — **Contrat de zoom : e2e à 150 % et 200 % sur les flux clés (WCAG 1.4.10).** `index.css:182-188` admet que le zoom 200 % est un contrôle « manuel » — jamais gardé, alors que les laptops Windows tournent à 125-150 %. `e2e/zoom.spec.js` : sur `/login`, `/ventes/factures`, `/crm/leads`, `/parametres`, forcer 150/200 % et asserter zéro débordement (`scrollWidth - innerWidth <= 1`) + boutons primaires cliquables. **Done =** spec verte ; une largeur fixe non-responsive la fait échouer. Files: frontend/e2e/zoom.spec.js (nouveau). (ROUTINE — M, sonnet) (@lane: frontend/e2e) (@after: VX68)
- [x] VX70 — **Régression visuelle ÉTROITE : ÉTENDRE `e2e/visual.spec.js` (il existe déjà) à 6-8 écrans clés, clair + sombre.** CORRECTION du critic : une comparaison de pixels EXISTE déjà — `frontend/e2e/visual.spec.js` (Dashboard, `toHaveScreenshot` + `maxDiffPixelRatio:0.02`, tag `@visual`, exécuté dans `release-verify.yml:227-247` avec workflow de ré-approbation des baselines) ; MB6 = overflow seulement, YTEST10 = PDF seulement. ÉTENDRE ce spec (jamais l'écraser) : ajouter DevisList, Kanban leads, DevisGenerator (en-tête+totaux), FactureList, Login — clair ET sombre, animations off, contenus dynamiques masqués — en GARDANT le tag `@visual` et le tier release-verify (manuel+nightly, jamais dans le smoke par-merge : décision livrée, ne pas la renverser sans raison). IMPÉRATIF : lancer APRÈS l'atterrissage des tâches design VX1-47 (sinon toutes les baselines sont invalidées) ; PAS de couverture exhaustive. **Done =** les nouveaux écrans passent en release-verify ; un changement CSS volontaire échoue avec diff lisible ; la procédure de ré-approbation existante couvre les nouvelles baselines. Files: frontend/e2e/visual.spec.js (extension). (ROUTINE — M, sonnet) (@lane: frontend/e2e) (@after: VX69) *(à exécuter en dernier de la vague.)*
- [x] VX71 — **[GATED: new dev-dep @axe-core/playwright] a11y dynamique : scans axe DANS les parcours e2e (extension de YHARD8).** YHARD8 = scans statiques ; seul un scan en VRAI parcours attrape les états dynamiques : modal ouvert, menu ouvert, formulaire en erreur, toast. Ajouter `@axe-core/playwright` (dev-only, gratuit) + UN `AxeBuilder.analyze()` après 4-5 interactions clés des specs existants (dialog PDF DevisList, lead en édition, formulaire invalide, kebab DataTable). Échec sur `serious`/`critical` uniquement (anti-flake). **Done =** scans verts sur main ; retirer un `aria-label` d'un dialog échoue ; zéro nouveau job. Files: frontend/e2e/ (extension des specs), frontend/package.json (dev-dep). (DEP — S, sonnet ; noter au DONE LOG) (@lane: frontend/e2e) (@after: VX70)
- [x] VX72 — **[DECISION] [GATED: new dep @sentry/react] Sentry frontend en no-op DSN-gaté, miroir du backend.** Le backend a `core/monitoring.py` DSN-gaté ; le frontend n'a RIEN : un crash React chez un employé n'a ni trace ni breadcrumbs. Ajouter `@sentry/react` derrière le MÊME patron (aucun envoi sans `VITE_SENTRY_DSN`, no-op total par défaut), câblé au `RouteErrorBoundary` avec `captureException` → `eventId` affiché (« code erreur à transmettre »). La tâche ne livre QUE le no-op câblé — l'ACTIVATION est une décision de Reda (dépendance externe, tier gratuit plafonné). **Done =** sans DSN : zéro requête sortante (assertion e2e) ; avec DSN de test : event + ID affiché ; budget YHARD7 respecté (SDK lazy). Files: frontend/src/lib/monitoring.js (nouveau), frontend/src/ui/ErrorBoundary.jsx. (DEP/DECISION — M, sonnet ; noter au DONE LOG) (@lane: frontend/monitoring)

**M — Honnêteté de la langue et de la locale :**
- [x] VX73 — **Le sélecteur de langue arrête de mentir + label `Ctrl K` sur Windows.** Le sélecteur EN/AR est réel mais ne couvre que ~121 clés de chrome (~2 % de l'app) : l'utilisateur choisit « English », obtient une sidebar anglaise puis des pages 100 % françaises — rien ne le lui dit. Dans `LanguageSwitcher.jsx`, quand `locale !== 'fr'` : notice persistante « Seuls les menus sont traduits — le contenu des pages reste en français » (clé ajoutée aux 3 catalogues). Au même passage : `providers/shortcuts.js:20` remplace le glyphe `'⌘ K'` codé en dur par une détection plateforme → `'Ctrl K'` sur Windows/Linux (la plateforme RÉELLE de l'ERP) ; mini-tripwire vitest anti-régression de couverture i18n. **Done =** switch EN → notice présente ; `navigator.platform='Win32'` → `Ctrl K` ; tripwire prouvé rouge sur une branche synthétique. Files: frontend/src/components/layout/LanguageSwitcher.jsx, frontend/src/providers/shortcuts.js, les 3 catalogues i18n. (ROUTINE — S, sonnet) (@lane: frontend/i18n)
- [x] VX74 — **[DECISION — ZÉRO build] L'arabe : interface complète RTL, ou langue de documents seulement ? Estimation chiffrée pour Reda.** Choisir AR aujourd'hui donne une app visuellement CASSÉE (1 seule règle CSS RTL ; 76 fichiers en utilitaires physiques `ml-*/mr-*` non retournés ; dropdowns/drawers non miroirés) — pire qu'untranslated. Or les documents clients arabes existent déjà (XSAL13/XSTK18…) et les techniciens reçoivent l'AR par WhatsApp (QJ4). Produire (PAS implémenter) une note chiffrée : (a) taille du dictionnaire à extraire + coût de maintien de 3 catalogues ; (b) audit RTL des 76 fichiers physiques→logiques + direction des primitives ; (c) recommandation AR = documents seulement (le champ `langue_document` le modélise déjà) vs UI complète vs « coquille seulement » ; si le verdict est « documents seulement », retirer AR du switcher UI (honnêteté > promesse). **Done =** note écrite livrée au fondateur avec les 3 chiffrages ; décision consignée au DONE LOG ; aucun fichier produit modifié. Files: docs/ (note). (DECISION — S, sonnet) (@lane: frontend/i18n) (@after: VX73)
- [x] VX75 — **Un seul format d'argent et de date : consolidation des ~90 contournements de `lib/format.js` + garde CI.** `format.js` se dit « une seule source de vérité » mais ~90 appels dans ~45 fichiers roulent leur propre `toLocaleString` avec DEUX tags concurrents (`fr-FR` vs `fr-MA`) — et un bug VISIBLE : `pages/stock/CatalogueTable.jsx:142/150` affiche `450.00 HT` (point) là où le devis affiche `450,00 MAD` (virgule) — même produit, deux formats dans la même session. Migrer les sites monétaires vers `formatMAD`/`formatNumber`, les ~25 dates vers `formatDate`/`formatDateTime`, les `.toFixed` restants vers `formatNumber`/`formatPercent` ; garde statique : échec sur tout nouveau `toLocaleString` hors `lib/format`. **Done =** grep hors format.js = 0 non-test ; CatalogueTable et DevisList rendent le même `1 234,56 MAD` (capture) ; `format.test.mjs` vert. *(Complémentaire de VX5 : VX5 = typographie du chiffre, ici = la VALEUR formatée.)* Files: ~45 fichiers cités par le grep, frontend/src/lib/format.js (garde). (ROUTINE — M, sonnet) (@lane: frontend/format) (@after: VX5)

**N — Surfaces secondaires (emails, impression, chrome navigateur, liens, fichiers) :**
- [x] VX76 — **[backend-template] Emails de marque : wrapper HTML unique sur les DEUX points d'envoi.** 100 % des emails transactionnels (relances devis, alertes rappel, confirmations e-signature, reçus) partent en texte brut sans logo — l'air d'un spam à côté du PDF premium. UN template additif `templates/email/base.html` (logo + en-tête navy + pied) et basculer les deux goulots — `apps/ventes/email_service.py:68-85` et `apps/notifications/services.py:89-109` — vers `EmailMultiAlternatives` : le texte existant rendu DANS le wrapper, texte brut conservé en repli MIME (additif, non cassant). Aucune logique métier, EmailLog/chatter identiques. **Done =** tests : l'envoi porte une alternative `text/html` avec le wrapper pour `send_document_email` ET `notify()` ; une commande `manage.py preview_email` rend le wrapper + un corps type en fichier HTML relu AVANT qu'un client ne reçoive le premier email brandé (boucle de validation visuelle — pas seulement la console) ; suites ventes/notifications vertes. Files: backend/django_core/templates/email/base.html (nouveau), apps/ventes/email_service.py, apps/notifications/services.py, tests. (ROUTINE — M, sonnet ; exception backend-template) (@lane: backend/email-templates)
- [x] VX77 — **Compression photo côté client AVANT upload sur les 3 écrans de capture terrain.** `ChantierPhotos.jsx:130-133`, `InterventionFieldExecution.jsx:347` et `InterventionCapturePanels.jsx` envoient la photo BRUTE (4-8 Mo routiniers) — minutes ou timeout par photo sur la 3G rurale. Helper pur `<canvas>`+`toBlob` (zéro dépendance) dans `frontend/src/ui/file-utils.js` : bord long ≤1600px, JPEG q0.75, `image/*` uniquement (PDF intouchés) ; idéalement via `FileUpload.jsx` pour centraliser. Garde serveur 20 Mo conservée. *(VX77 RÉTROFITTE la compression dans les écrans que VX44 vient de toucher — rafale/partage restent à VX44 ; le helper vit dans file-utils pour que tout futur écran en hérite.)* **Done =** vitest : blob de N Mo → plus petit, dimensions plafonnées, PDF passthrough ; payload réseau réduit vérifié. Files: frontend/src/ui/file-utils.js (nouveau), les 3 écrans cités. (ROUTINE — M, sonnet) (@lane: frontend/upload) (@after: VX44)
- [x] VX78 — **Brancher le 404 déjà construit : fini la redirection silencieuse vers le dashboard.** `ui/NotFound.jsx` est complet, exporté, jamais importé par le router (vérifié) : le catch-all (`router/index.jsx:357`) fait `<Navigate to="/dashboard" replace />` — un favori périmé rebondit sans explication. Remplacer par `{ path: '*', element: <WithLayout><NotFound /></WithLayout> }`. **Done =** test : `/nexiste-pas` rend « Page introuvable » ; e2e verte. Files: frontend/src/router/index.jsx. (ROUTINE — S, haiku) (@lane: frontend/router) (@after: VX65)
- [x] VX79 — **Liens internes partageables : `?id=` + « Copier le lien » pour devis, chantier et ticket SAV.** Seuls les leads ont une URL partageable (VX22 ajoute la route) ; devis/chantier/ticket s'ouvrent en panneaux d'état jamais reflétés dans l'URL — impossible d'envoyer à un collègue « regarde CE devis » (le seul lien existant est la proposition PUBLIQUE, règle #4, intouchée). Refléter le détail ouvert dans l'URL (patron `?lead=` de LeadsPage, `useSearchParams`) pour `/ventes/devis`, `/chantiers`, `/sav` + bouton « Copier le lien » (patron clipboard DevisList, pointé vers l'URL INTERNE) ; id invalide → l'`EmptyState` inline, jamais une page blanche. **Done =** pour chaque entité : id valide ouvre le bon panneau, id invalide → EmptyState ; le lien copié rouvre le même enregistrement dans un onglet neuf. Files: frontend/src/pages/ventes/DevisList.jsx, frontend/src/pages/installations/InstallationsPage.jsx, frontend/src/pages/sav/TicketsPage.jsx. (ROUTINE — L, sonnet) (@lane: frontend/deeplinks) (@after: VX31, VX67) *(@coord VX20/VX48/VX63 sur DevisList — rebase.)*
- [x] VX80 — **Feuille de style d'impression + bouton « Imprimer » sur devis-liste, factures et checklist chantier.** Zéro `@media print` dans tout le SPA (grep vérifié) : Ctrl+P imprime la sidebar, le dark mode qui boit l'encre, des tables tronquées. UN bloc global `styles/print.css` : masquer sidebar/header/boutons, tables `overflow: visible; width:auto`, noir-sur-blanc, `@page { margin: 2cm }`, `page-break-inside: avoid` ; + bouton « Imprimer » (`window.print()`) sur DevisList, FactureList, checklist d'InstallationDetail. Totalement distinct des PDF WeasyPrint (règle #4 — jamais touchés). **Done =** `page.emulateMedia({media:'print'})` sur les 3 écrans : table complète, zéro chrome, fond clair ; vitest smoke bouton. Files: frontend/src/styles/print.css (nouveau), les 3 écrans. (ROUTINE — M, sonnet) (@lane: frontend/print) (@after: VX52) *(@coord VX50 sur FactureList — rebase.)*
- [x] VX81 — **Noms de fichiers d'export XLSX/CSV horodatés (parité avec le fix PDF QD2).** ~9 exports tableur codent un nom nu (`PilotageStock.jsx:140` `analyse-achats.xlsx`, `MouvementsPage.jsx:96/146`, `FiscalitePage.jsx:118-122` — 5 CSV fiscaux envoyés au comptable !, `EngagementsPage.jsx:416`, `EtatsPage.jsx:191/202`) : deux exports le même jour = `(1)`,`(2)` indistinguables. Étendre `utils/downloadBlob.js` d'un `stampedFilename(base, ext)` → `base_societe_AAAAMMJJ.ext`, préférer `Content-Disposition` serveur quand présent. **Done =** vitest par site : le nom contient la date ; double export = deux noms distincts. Files: frontend/src/utils/downloadBlob.js + les sites cités. (ROUTINE — S, haiku) (@lane: frontend/export)
- [x] VX82 — **Chrome navigateur vivant : titre d'onglet par page + préfixe `(N)` non-lus + theme-color clair/sombre.** Un seul `<title>` statique pour toute la vie du SPA : 6 onglets ERP = devinette, et le compteur non-lus (`NotificationBell.jsx:179-182`) n'est jamais reflété dans l'onglet. Hook `useDocumentTitle.js` (zéro dépendance) sur DevisList/FactureList/InstallationDetail/TicketsPage/LeadsPage (`Titre · TAQINOR`) ; NotificationBell préfixe `(N)` quand `total > 0` ; `index.html` : second `<meta name="theme-color" media="(prefers-color-scheme: light)">` (aujourd'hui le chrome OS reste navy autour d'une app claire). **Done =** vitest : monter DevisList → `document.title` mis à jour ; préfixe `(N)` posé/retiré ; preview clair/sombre : le bon meta actif. Files: frontend/src/hooks/useDocumentTitle.js (nouveau), frontend/src/components/layout/NotificationBell.jsx, frontend/index.html. (ROUTINE — S, sonnet) (@lane: frontend/shell) (@after: VX56)

---

**ROUND 3 (2026-07-09) — « le meilleur outil avec lequel un employé ait travaillé » : ergonomie par métier, vitesse de saisie, file de travail, droit à l'erreur, interop.**
*Le fondateur a re-challengé : « êtes-vous sûrs ? je veux que les EMPLOYÉS le classent comme le meilleur outil — couvrez TOUS les angles et pour chacun la MEILLEURE solution ». Rounds 1-2 = beau + techniquement parfait ; round 3 = au service de l'employé. Sweep 12 agents (journées du technicien/commercial/directeur/comptable ; vitesse de saisie ; file de travail personnelle ; droit à l'erreur ; interop Excel/WhatsApp/téléphone ; 2 recherches externes G2/Capterra/NN-g/Odoo/Linear/Superhuman ; carte anti-duplication) + synthèse Fable + dédup adversariale contre les 2 084 tâches NT (`docs/new_tasks_plan.md`, PR #345), VX1-82, ARC, FE-*. **L'insight n°1, tracé dans le code : l'intelligence déjà construite et payée n'atteint jamais un écran qui dit « fais ça maintenant »** — la tournée géo-optimisée (endpoint complet, jamais appelée par l'écran du technicien), la signature client (modèle+endpoint+offline construits, zéro UI), le journal d'appel typé du commercial (backend livré, zéro site d'appel), la file de relances FG31, le toast « Annuler » `toastWithUndo` (0 appelant), la délégation d'absence — tous orphelins côté écran. La majorité du round 3 est donc du CÂBLAGE, pas de la construction : le meilleur ratio valeur/effort des trois rounds. Dédup NT appliquée : 5 seeds réécrites/abandonnées (voir NE PAS FAIRE round 3). **Ce qu'aucun audit ne remplace — noté pour Reda, PAS une tâche : une vraie boucle de retour employés** (3 chiffres mesurés avant/après : temps « nouveau lead → 1er appel », taps pour clôturer une intervention, minutes de patrouille matinale ; 30 min d'observation/persona/mois ; un canal « signaler une friction » à un tap + les web-vitals réels de VX61).*

**O1 — La file, la confiance, les gestes quotidiens (tous les employés, plusieurs fois/jour) :**
- [x] VX83 — **« Ma file » : LA file de travail unique (décision d'architecture — flagship).** Chaque employé patrouille 4 surfaces déconnectées dans 3 sections (Mes activités sous CRM, Approbations sous ANALYSE, la cloche, Ma journée) — ~2-4 min de « ai-je raté quelque chose ? » par session/personne, plus des approbations/mentions qui dorment. **Décision (UNE architecture) : faire évoluer `MesActivitesPage` en « Ma file » cross-module — jamais une nouvelle app inbox, jamais une page par persona (6ᵉ silo).** `[BACKEND additif]` action `GET /records/activities/ma-file/` à côté de `mine` (`apps/records/views.py:155-172`) rendant les 3 buckets existants PLUS : approbations décidables par moi (réutiliser l'agrégateur `_SOURCE_LOADERS`, `apps/reporting/approbations.py:129-135` — jamais le forker), mentions non lues avec leur `link` (cf. VX85), et pour le rôle commercial : relances dues via FG31 déjà livré jamais consommé — EXTRAIRE la logique de `LeadViewSet.relances` (`apps/crm/views.py:969-994`) vers `apps/crm/selectors.py` puis l'appeler (jamais forker/appeler une vue, convention selectors) — leads chauds jamais contactés (via `selectors.py`) et devis `envoye` proches d'expiration — chaque item `{kind, title, due, link, urgency, montant?}`. **Inclure le quick-add « + À faire »** (créer une `records.Activity` personnelle assignée à soi) — la promesse XKB4 `[x]` est absente du code (vérifié : zéro « à faire » dans `MesActivitesPage.jsx` alors que le serializer expose le champ `records/serializers.py:83`) ; une file où on ne peut pas s'ajouter une tâche est une demi-file. Frontend : `MesActivitesPage.jsx` rend l'union classée plus-urgent-d'abord, en-tête « 3 en retard · 2 aujourd'hui · 1 approbation », verbes Fait / Plus tard / Déléguer / Ouvrir + « + À faire ». Promouvoir l'entrée nav hors de CRM (`Sidebar.jsx`) vers le groupe de tête. `/ma-journee` reste l'écran d'exécution terrain — Ma file y pointe. Alternatives rejetées : page « ma journée commerciale » dédiée (silo), extension Dashboard (VX27 possède les KPI par rôle et LIE vers Ma file), nouvelle app inbox. **Done =** l'endpoint agrège les 3+ familles company-scopées (≤2 requêtes/source) via selectors ; la page affiche la liste unifiée classée + total unique + « + À faire » fonctionnel ; décider une approbation depuis la file passe par le `decider` existant ; hooks e2e préservés. Files: `apps/records/views.py`, `apps/crm/selectors.py`, `frontend/src/pages/activities/MesActivitesPage.jsx`, `Sidebar.jsx`. (ARCH — L, sonnet ; revue orchestrateur obligatoire) (@lane: backend/records + frontend/queue) *(@coord VX27/VX14 ; ARC10 = moteur SOUS la file.)* **⚠ Directive de dédup (critic Fable) : `NTMOB19` (`docs/new_tasks_plan.md`, « widget à faire aujourd'hui ») construit la MÊME union cross-module de sélecteurs — à corriger AVANT que sa lane ne bâtisse un 2ᵉ agrégateur : NTMOB19 doit CONSOMMER l'endpoint `ma-file/` de VX83, pas le refaire (idem NTMOB5 « Mes approbations » mobile / NTWFL28).**
- [x] VX84 — **[BUG] La cloche arrête de compter le travail des AUTRES.** `[BACKEND one-liner]` Le badge « Activités en retard » est calculé company-wide (`apps/reporting/search.py:169-172`, `**co` sans `assigned_to`, vérifié) : le commercial voit les retards de TOUTE la boîte dans SON badge, pendant que `/activites` ne montre que les siens — deux chiffres qui se contredisent à chaque page. Un badge auquel on ne croit plus est pire que pas de badge. Ajouter `assigned_to=request.user` au filtre, faire dériver le total de la cloche et celui de « Ma file » (VX83) de la même source, étiqueter « pour moi » vs « information société » (garanties/contrats restent des alertes société légitimes). **Done =** test de régression — l'activité en retard d'un collègue est exclue du badge ; total cloche == total actionnable de Ma file. Files: `apps/reporting/search.py`, `frontend/src/components/layout/NotificationBell.jsx`. (ROUTINE — S, sonnet) (@lane: backend/records) (@after: VX83)
- [x] VX85 — **Plomberie de la file dans `apps/records` : snooze non destructif + mentions cliquables + réaffectation notifiée.** `[BACKEND additif]` Trois trous, une lane. (a) « Reporter » réécrit `due_date` de façon destructive — ajouter `snoozed_until` nullable sur `records.Activity` (`models.py:98`, migration additive), exclu de `mine`/`ma-file` tant que non échu, picker « ⏰ Plus tard » (ce soir / demain / lundi / +1 semaine / perso — vocabulaire convergent Outlook/Superhuman/Linear) à côté de « Fait » ; « Reporter » reste pour les vrais changements d'échéance. (b) `_notify_mentions` (`views.py:300-323`) notifie SANS `link` → mention non cliquable, absente de toute file : passer le `link` (même mapping que `MesActivitesPage.jsx:56-62`) ; idem `notify_followers`. (c) Changer `assigned_to` (`serializers.py:82`) ne notifie personne — le travail tombe entre deux personnes : détecter le changement dans `perform_update` (`views.py:214`), `notify()` le nouveau propriétaire avec `link`, bouton « Déléguer à… » (réutiliser `AssigneePicker`). **Done =** item snoozé revient à l'heure dite avec sa `due_date` d'origine intacte ; clic mention → navigation ; réaffectation → notification + l'item change de file ; tests sur les trois. Files: `apps/records/{models,views,serializers}.py` + migration, `frontend/src/components/ActivitiesPanel.jsx`. (SCHEMA — M, sonnet) (@lane: backend/records) (@after: VX83) *(@coord NTCOL17 = l'inbox mentions dédiée AU-DESSUS de ce fix `link`.)*
- [x] VX86 — **Signal ambiant sur les approbations (badge sidebar + carte Dashboard + rangée cloche).** L'inbox 5-sources `/approbations` (XKB1/ZCTR7-9) est excellente et fonctionnellement INVISIBLE : 6ᵉ item de la section ANALYSE (`Sidebar.jsx:189`), zéro badge, zéro carte Dashboard, zéro entrée cloche — des réquisitions dorment. Hook partagé `useApprobationsCount()` (total de `approbations-en-attente/`, polling via `useVisibilityAwarePolling` de VX56 quand livré) alimentant : badge numérique sur l'item nav, carte « Attend votre décision » en tête de `Dashboard.jsx` (si `total>0`, top-3 via `?trier=urgence` déjà supporté, lien direct), rangée « N approbations » en tête de la cloche. MINIMAL pour ne pas empiéter sur VX27 (dashboards par rôle — fusionner la carte à son build) ni VX14. **Done =** badge/carte/rangée affichent le même chiffre, disparaissent à 0, clic → `/approbations` ; testé ≥1 source non vide. Files: `frontend/src/hooks/useApprobationsCount.js` (nouveau), `Sidebar.jsx`, `Dashboard.jsx`, `NotificationBell.jsx`. (ROUTINE — S/M, sonnet) (@lane: frontend/queue) *(@coord NTWFL15 = polish inbox mobile ; NTMOB5 = cockpit mobile dirigeant — même source.)*
- [x] VX87 — **Journal d'appel en un geste : ressusciter `log-interaction` (mort UI) + relance dans le même geste + nudge post-appel.** L'action la plus fréquente du commercial (15-30 appels/jour) coûte ~6 interactions dans 3 zones de la modale, et l'issue (joint/non joint/à rappeler/refus/intéressé) est INCAPTURABLE — alors que le backend livre tout (FG30 `views.py:1163-1206`, `OUTCOMES` `models.py:739-745`, pose `first_contacted_at`) et que `crmApi.logInteraction` a **ZÉRO site d'appel (vérifié)**. Mini-composant « Journaliser un appel » (boutons issue + note + « prochaine action J+0/1/3/7 » → `relance_date`) dans la section Historique de `LeadForm.jsx` (~:1194) et sur les lignes de Ma file (VX83) ; après un tap `tel:` sur `LeadCard`/`ListView`, au retour dans l'onglet (`visibilitychange`), proposer « Appel terminé — noter le résultat ? » pré-rempli `kind='appel'`. Garder `noter` (note libre) — on l'augmente. **Done =** appel journalisé avec issue en ≤2 clics + relance posée dans le même geste ; entrée typée au chatter ; `logInteraction` a ≥1 consommateur ; nudge dismissable, hook `data-*` nouveau uniquement. Files: `frontend/src/pages/crm/LeadForm.jsx`, `leads/views/LeadCard.jsx`, `ListView.jsx`, nouveau `features/crm/CallLogPopover.jsx`. (ROUTINE — M, sonnet) (@lane: frontend/crm) *(@coord NTSRV5 = le futur log-appel SAV réutilisera CE composant.)*
- [x] VX88 — **Ma journée branche la tournée géo-optimisée déjà payée.** Le technicien voit ses arrêts en ordre priorité-puis-insertion, sans sens géographique — 15-40 min de trajet perdues/jour/technicien — alors que `ma-tournee` (tri plus-proche-voisin + lien Google Maps par arrêt, `apps/installations/views/intervention.py:1846-1900`) est construit, testé, et consommé uniquement par un onglet bureau. Dans `MaJourneePage.jsx`, remplacer `getInterventions({date_prevue: today})` par `installationsApi.getMaTournee` (déjà défini, `installationsApi.js:246-248`, vérifié) et afficher « Itinéraire » (`stop.itineraire_url`) par carte. Coordonner VX42 : son bouton « navigation » DOIT pointer `itineraire_url` (une seule logique de lien maps). **Done =** `/ma-journee` affiche l'ordre `ma-tournee` + lien Itinéraire cliquable si GPS connu ; `getInterventions` inchangé ailleurs. Files: `frontend/src/pages/interventions/MaJourneePage.jsx`. (ROUTINE — S, sonnet) (@lane: frontend/terrain) (@after: VX42) *(@coord NTFSM3 = optimiseur 2-opt plus avancé — s'il atterrit, il remplace ma-tournee ; re-mesurer.)*

**O2 — La vitesse de saisie (commerciaux + comptable, dizaines de fois/jour) :**
- [x] VX89 — **LeadForm : Escape + autofocus via `ResponsiveDialog` (et corriger le « done » menteur de MB4).** Le modal n°1 de l'ERP (20-40 ouvertures/jour/commercial) est le SEUL à ne pas répondre à Escape ni focuser son champ requis : shell brut `div.modal-overlay` (`LeadForm.jsx:588-589`), zéro `autoFocus` — alors que MB4 est marqué `[x]` en prétendant la migration faite (fact-check : faux pour ce fichier — noter au DONE LOG). Envelopper le shell externe dans `ResponsiveDialog` (comme `ClientForm`), garder le `lead-form-layout` interne, `autoFocus` sur Nom. Le composant existe, est utilisé par 4/6 formulaires audités, donne Escape + focus-trap + bottom-sheet mobile gratuits. **Done =** ouverture → Nom focus ; Escape → `onClose` ; largeur desktop équivalente ; e2e LeadForm verts. Files: `frontend/src/pages/crm/LeadForm.jsx`. (ROUTINE — M, sonnet) (@lane: frontend/crm) (@after: VX22) *(@coord VX51 clavier iOS — fichier partagé, rebase.)*
- [x] VX90 — **« Ajouter ligne » déplace enfin le focus sur la nouvelle ligne (devis + facture).** Dans les trois grilles de lignes (`DevisGenerator.jsx addLine:820`, `DevisForm.jsx`, `FactureForm.jsx:170`), ajouter une ligne laisse le curseur où il était : sur un devis de 8 lignes, 8 trajets souris inutiles sur le document le plus stratégique. Poser `data-line-key` sur chaque `<tr>` + `pendingFocusKey` dans `addLine`, `.focus()` du `ProduitPicker` de la nouvelle ligne + `scrollIntoView`. Un ref-walk DOM, pas une réécriture `useFieldArray`. **Done =** clic « Ajouter ligne » → `activeElement` dans la nouvelle ligne, les trois fichiers ; tests totaux inchangés ; garde `noValidate`/`step="any"` intacte. Files: les 3 fichiers. (ROUTINE — S, sonnet) (@lane: frontend/ventes-gen) (@after: VX16)
- [x] VX91 — **Convergence FactureForm : `ProduitPicker` + « + Nouveau client ».** Régression réelle : la colonne Produit de `FactureForm.jsx:430-440` est un `<Select>` natif non filtrable sur 50+ SKU, là où DevisForm/DevisGenerator utilisent le `ProduitPicker` recherche-d'abord. Swap à l'identique de `DevisForm.jsx:317-321`. Ajouter « + Nouveau client » (réutiliser `ClientQuickCreateModal`, câblage QG3 prouvé) sur le select client de `FactureForm.jsx:293-307` et `DevisForm.jsx:231-245` — aujourd'hui facturer un client absent = abandonner la facture. Pure convergence : supprime une implémentation dupliquée pire. **Done =** colonne produit = popover recherchable ; création client inline sélectionne le nouveau ; `onProduitChange` inchangé. Files: `FactureForm.jsx`, `DevisForm.jsx`. (ROUTINE — S/M, sonnet) (@lane: frontend/ventes)
- [x] VX92 — **« Enregistrer et créer un autre » + mort du `window.alert` du paiement.** Aucun « save & new » dans le repo : 10 leads après un salon, 5 paiements après un relevé, 20 produits à seeder = un cycle fermer/rouvrir par enregistrement (~10-30 s chacun). Toggle « Créer un autre » (persisté `localStorage`, défaut OFF → identique) sur `ProduitForm.jsx`, `ClientForm.jsx`, le dialog paiement de `FactureList.jsx:676-711` : succès → reset + refocus champ 1 au lieu de `onClose()`. Au même passage : `alert('Paiement enregistré.')` (:265) → `toast.success`, `autoFocus` sur `pay-montant`. **Done =** toggle ON → le dialog ne ferme pas, formulaire vidé, focus champ 1 ; OFF → identique. Files: `ProduitForm.jsx`, `ClientForm.jsx`, `FactureList.jsx`. (ROUTINE — M, sonnet) (@lane: frontend/forms) *(@coord VX19 possède le sweep GLOBAL alert/confirm — créditer les 2 sites réécrits ici.)*
- [x] VX93 — **Défauts intelligents : propriétaire = moi, dernière ville, dernière TVA, dernier mode de paiement.** Quatre valeurs parmi les plus re-saisies n'ont aucun défaut : `owner` vide sur chaque lead (`LeadForm.jsx:230` — le créateur est presque toujours le propriétaire), `ville` sans mémoire, TVA figée `'20'` (`ProduitForm.jsx:275`, `DevisGenerator emptyLine:74`), `payMode` figé `'virement'` (`FactureList.jsx:228`). Étendre le pattern `canal: DEFAULT_CANAL` déjà livré : owner = utilisateur courant (création seulement), ville/TVA/payMode = dernier utilisé via `localStorage`, toujours modifiables, jamais bloquants. Un réglage backend « TVA société » serait de la sur-ingénierie. **Done =** nouveau lead pré-rempli owner+ville, nouveau produit/ligne dernière TVA, paiement dernier mode ; l'édition d'un existant intacte. Files: `LeadForm.jsx`, `ProduitForm.jsx`, `DevisGenerator.jsx`, `FactureList.jsx`. (ROUTINE — S, haiku) (@lane: frontend/forms)
- [x] VX94 — **Enter-pour-ajouter + refocus sur les panneaux de capture terrain (surface 100 % pouces).** Sur téléphone, chaque relevé de série / ligne consommée force à lâcher le clavier, viser « Ajouter », re-taper — ×8 composants sérialisés par pose. Dans `InterventionCapturePanels.jsx` : `onKeyDown` Enter → `add()` sur les inputs de `SerialsPanel:71-74` et du bloc extra de `ConsommationPanel:180-184`, + `firstFieldRef.focus()` après succès (recette `newCatRef` prouvée dans `ProduitForm.jsx:294-300`) ; `ReservesPanel` (Textarea) reste clic-only. **Done =** Enter dans le dernier champ = clic « Ajouter » ; succès → focus au premier champ ; test simule Enter. Files: `frontend/src/features/installations/InterventionCapturePanels.jsx`. (ROUTINE — S, sonnet) (@lane: frontend/terrain)

**O3 — Le droit à l'erreur (tous, la confiance au quotidien) :**
- [x] VX95 — **Câbler `toastWithUndo` (0 appelant) : archivage leads + drop kanban en avant.** Le primitive undo parfait existe (`frontend/src/lib/toast.js:60-89`, commit différé + « Annuler ») et a ZÉRO consommateur (vérifié). (a) Archive/désarchive lead (`ListView.jsx`), archive bulk (`BulkActionBar.jsx:94-105`), delete/unarchive stock (`StockList.jsx:792-825`) → `toastWithUndo`. (b) Kanban : un drop en avant d'une colonne de trop est instantané, non annulable (`KanbanView.jsx:186-200`) — après un drop réussi, toast « Annuler » 6 s restaurant l'étape précédente EXACTE en contournant le recul-guard (undo de sa propre action) ; `SIGNED` reste gardé par `SigneDialog` ; clés de stage importées de `features/crm/stages` (règle #2). Un confirm bloquant par drag est rejeté (tuerait le kanban). **Done =** archive + drop avant montrent « Annuler » 6 s ; le clic restaure l'état antérieur ; recul-guard inchangé pour les drags manuels ; hooks e2e préservés. Files: `ListView.jsx`, `BulkActionBar.jsx`, `StockList.jsx`, `KanbanView.jsx`. (ROUTINE — M, sonnet) (@lane: frontend/forgiveness) *(@coord NTUX6 = undo de l'édition en masse, primitive partagée.)*
- [x] VX96 — **Le delete de lead cesse d'être « irréversible » : `Lead` premier adoptant du soft-delete.** `[BACKEND]` La fondation FG388 (SoftDeleteModel + `core/trash.py` fenêtre 30 min + `TrashViewSet` `/core/corbeille/` en ligne, vérifié) est adoptée par ZÉRO modèle métier — pendant que `LeadViewSet.destroy()` (`apps/crm/views.py:698`) fait un vrai DELETE confirmé par un `window.confirm` avouant « irréversible ». Faire hériter `Lead` de `SoftDeleteModel` (migration additive), `destroy()` → `soft_delete(user)` ; frontend : `confirmDelete()` + `toastWithUndo` (VX95), copy « irréversible » supprimée. **PÉRIMÈTRE RÉDUIT (dédup NT) : ne PAS construire de composant `<CorbeillePanel>` générique ni d'écran corbeille — `NTUX7` (`docs/new_tasks_plan.md`) possède la Corbeille transverse (app `apps/trash`, event-bus, `/parametres/corbeille`, purge/permissions/audit).** Cette tâche = uniquement faire de `Lead` le premier adoptant du soft-delete + l'undo-toast ; la restauration passe par le `TrashViewSet` existant en attendant l'écran NTUX7. **⚠ Piège à signaler (critic Fable) : NTUX7 (`docs/new_tasks_plan.md`) bâtit une SECONDE pile de corbeille inconsciente de FG388** — nouvelle app `apps/trash` + `ElementSupprime` + son propre endpoint corbeille, alimenté par un événement `record_soft_deleted` que RIEN n'émet (`SoftDeleteModel.soft_delete` n'écrit que `DeletionRecord`) → un Lead soft-deleted via FG388 n'apparaîtrait JAMAIS dans la corbeille NTUX7, et l'OS finirait avec DEUX magasins de corbeille + deux endpoints. **AVANT que la lane NTUX7 ne build, la re-baser sur FG388** (émettre `record_soft_deleted` depuis `SoftDeleteModel.soft_delete`, ou lire `DeletionRecord`). **Done =** supprimer un lead le sort des querysets par défaut, restaurable 30 min (toast) ; copy « irréversible » supprimée ; tests crm restore + scoping company. Files: `apps/crm/models.py`+migration, `apps/crm/views.py`, `ListView.jsx`, `BulkActionBar.jsx`. (SCHEMA — M, sonnet ; escalader opus si l'import-linter core bronche) (@lane: backend/crm) (@after: VX95)
- [x] VX97 — **La facture (et le devis) montrent enfin « qui a fait quoi ».** `FactureActivity`/`DevisActivity` existent et s'écrivent (migrations ventes 0020/0017) mais la facture — le document au plus gros blast-radius financier — n'a AUCUN historique visible ; le seul « Historique » de DevisList est la chaîne de versions, pas le journal des changements. Monter le feed existant en section « Historique » repliable dans le détail Facture (`FactureList.jsx`) et Devis (`DevisList.jsx`), convention `<Sec id="historique">` prouvée dans `LeadForm.jsx:1193`. Rendre via `ChatterTimeline` (VX23) quand il atterrit ; jamais une 14ᵉ classe `*Activity` (ARC8). `prix_achat` jamais affiché. **Done =** ouvrir une facture/un devis montre qui/quand/ancien→nouveau. Files: `FactureList.jsx`, `DevisList.jsx`. (ROUTINE — M, sonnet) (@lane: frontend/forgiveness) (@after: VX92) *(@coord VX23 ChatterTimeline / ARC9 lecture uniforme ; VX92/VX93/VX114 touchent aussi FactureList — rebase en séquence.)*
- [x] VX98 — **Confiance en 2 clics : lien « Historique » sur la fiche + puce de fraîcheur.** « Qui a changé ce prix ? » = quitter la fiche → Journal global (gaté Directeur) → re-filtrer à la main. (a) Bouton « Historique » sur `DevisForm.jsx` et `ProduitDetail.jsx` → `/journal?model=devis&object_id={id}` (apprendre à `Journal.jsx` à lire ces params), visible avec `journal_activite_voir` — réutilise `AuditLog`+Journal qui couvrent TOUS les modèles. (b) `[BACKEND additif]` `<FreshnessChip>` « modifié par X il y a N min » sur Lead/Devis/Facture : `updated_at` existe, ajouter `updated_by` posé dans `perform_update` (pattern `archived_by`) ; rien si null ou si c'est moi. Le verrou optimiste complet reste territoire YDATA — ceci est la mitigation 80/20. **Done =** 1 clic fiche → Journal pré-filtré sur CET objet ; puce rendue, silencieuse sur son propre edit ; tests avec/sans permission. Files: `DevisForm.jsx`, `ProduitDetail.jsx`, `Journal.jsx`, backend `perform_update` (2 apps crm+ventes, 3 modèles Lead/Devis/Facture). (SCHEMA — M, sonnet) (@lane: frontend/forgiveness)

**O4 — Le directeur décide vite et juste (Reda + Meryem, quotidien) :**
- [x] VX99 **(partiel 2/3 — contrats.EtapeApprobation bloqué : bulk_create sans signal)** — **Les 3 sources d'approbation muettes se mettent à sonner.** `[BACKEND]` `APPROVAL_REQUESTED`/`REMINDER`/`ESCALATED` existent (YEVNT8/9) mais des 5 sources de l'agrégateur (`approbations.py:129-135` : automation/contrats/ged/installations/workflow), le câblage `apps/notifications/signals.py:154-234` n'en notifie qu'UNE (automation ; le `workflow` FG366 est couvert par NTWFL5) : soumettre une `DemandeAchat` (`installations/views/demande_achat.py:83-94` — vérifié : zéro `notify()`), une `EtapeApprobation` (contrats) ou une `DemandeApprobation` (GED) n'alerte personne. Étendre le câblage existant (même pattern que `automation.AutomationApproval`), import fonction-local. **Done =** soumettre chacune des 3 sources crée une notification pour le(s) approbateur(s) ; test additif par source. Files: `apps/notifications/signals.py`. (ROUTINE — M, sonnet) (@lane: backend/notify) *(@coord NTWFL5 notifie le NOUVEAU moteur FG366 — sources disjointes ; ARC10 ne re-câble pas en double.)*
- [x] VX100 — **Fin de la décision à l'aveugle : montant + lien source dans l'inbox d'approbations.** `[BACKEND additif]` L'agrégateur supporte `?trier=montant` (`approbations.py:180,198-202`) mais aucune source ne remplit jamais `montant` — code mort — et `ApprobationsPage.jsx:139` n'a aucun lien vers la pièce : Reda approuve sans voir le montant ni le chantier. Exposer `montant` (depuis `DemandeAchat.montant_estime`, `models_demande_achat.py:103`) et `lien` (`/chantiers/{id}` ; `None` si pas de cible — jamais fabriqué) dans `_installations_items()` (:96-110) et équivalents ; colonne cliquable. Contrat d'API inchangé. **Done =** colonne Montant réelle pour les DemandeAchat, tri `montant` change l'ordre, clic → la pièce. Files: `apps/reporting/approbations.py`, `ApprobationsPage.jsx`. (ROUTINE — M, sonnet) (@lane: backend/reporting) (@after: VX99)
- [x] VX101 — **[BUG AUTH] Seul le bon tier peut approuver.** `[BACKEND]` `decider_approbation` est gardé par `IsAnyRole` (`approbations.py:207/337`, vérifié) et `decider_demande_achat` (`installations/services.py`) ne vérifie AUCUN rôle : **aujourd'hui un commercial ou un technicien peut approuver une réquisition d'achat ou une étape de contrat.** Dans `_decider_approbation_core` (`approbations.py:254-333`) — point d'ancrage unique des 5 sources — exiger le tier Responsable/Admin pour les sources `installations` et `contrats` ; la LECTURE reste ouverte. Si ARC10 atterrit avant, ré-évaluer sur le nouveau moteur. Noter AUTH au DONE LOG. **Done =** test — un rôle normal reçoit 403 en décidant une DemandeAchat/EtapeApprobation, la lecture reste 200 ; non-régression automation/ged/workflow. Files: `apps/reporting/approbations.py`, `apps/installations/services.py`. (AUTH — M, opus : contrôle d'accès cross-app) (@lane: backend/reporting) *(@coord NTWFL1 = matrice unifiée future.)*
- [x] VX102 — **(CONSTRUIT 2026-07-09, demande directe du fondateur) Le terrain peut CRÉER une réquisition d'achat — page dédiée `/chantiers/demandes-achat`.** Livré au-delà du périmètre réduit initial : une PAGE dédiée (liste DataTable + dialogue de création chantier/lignes/priorité/date-besoin + « Soumettre » + Approuver/Refuser inline gardés au palier responsable/admin), pas seulement des points de montage. Endpoints FG310 réutilisés, AUCUN changement backend (un technicien porteur d'un rôle passe déjà la permission de création ; le sous-gate `IsAnyRole`/`is_responsable` reste la dette systémique VX101). RESTE ouvert comme raffinement : points de montage mobile « il me manque du matériel » dans `/ma-journee` + `InstallationDetail.jsx` (peuvent réutiliser cette page/ses composants). **NB futur run NT :** `NTP2P3` (formulaire DemandeAchat + recherche-catalogue) est désormais LARGEMENT satisfait — vérifier-non-déjà-construit avant de le bâtir. Livré : `frontend/src/pages/installations/DemandesAchatList.jsx` (+test), `api/installationsApi.js`, `router/index.jsx`, `Sidebar.jsx`. (ROUTINE — M, sonnet) (@lane: frontend/terrain) *(@coord NTP2P3/NTP2P4/NTP2P23.)*
- [x] VX103 — **Écran de délégation d'absence (backend XKB3 complet, 0 UI).** `automation.ApprovalDelegation` (modèle + `ApprovalDelegationViewSet` + `active_delegation_for()` + tests) n'a AUCUNE UI (grep « delegation » dans `frontend/src` : zéro). Si Reda part en congé, rien ne bascule vers Meryem sans passer par l'admin Django. Onglet « Délégations » dans `ApprobationsPage.jsx` : suppléant + plage de dates, liste actives/à venir, révocation — pur câblage sur l'API existante (`automation/urls.py:16`). **Done =** créer/voir/révoquer une délégation depuis l'UI ; le suppléant voit les items du délégant pendant la plage. Files: `frontend/src/pages/approbations/ApprobationsPage.jsx`. (ROUTINE — M, sonnet) (@lane: frontend/reporting) *(@coord NTWFL3 étend la COUVERTURE backend de cette même délégation au moteur WorkflowStepInstance — l'UI ici ne doit pas supposer la seule couverture ApprovalRequest.)*
- [x] VX104 — **Le superviseur se règle à la création de l'employé.** L'onboarding traverse 3 écrans jamais reliés ; le formulaire « Nouvel utilisateur » (`UsersManagement.jsx:342-418`) n'a pas de champ superviseur (seul `EquipeSection.jsx:108-125` le permet) → hiérarchie oubliée en silence, visibilité des dossiers cassée sans erreur. Ajouter le select `supervisor` (mêmes options que `EquipeSection.jsx:198-211`) au formulaire de création ; si vide, toast « Pensez à définir son responsable direct » + lien Paramètres → Équipe. **Done =** superviseur réglable dès la création ; création sans superviseur → toast avec lien. Files: `frontend/src/pages/admin/UsersManagement.jsx`. (ROUTINE — S, sonnet) (@lane: frontend/admin)

**O5 — Le technicien finit sa boucle (1-3 employés, chaque intervention) :**
- [x] VX105 — **Finir l'écran du technicien : statut + onglets persistants + honnêteté hors-ligne des photos.** Trois trous du même écran, une lane. (a) `MaJourneePage` n'expose AUCUN changement de statut : le technicien qui finit ne peut pas marquer « Terminée » — ajouter le Select statut du `DetailSheet` d'`InterventionsPage.jsx:399-411`, la garde serveur `transition_block_reason` existe (afficher le 400, ne JAMAIS la dupliquer). (b) Les 9 onglets remontent-refetchent à chaque re-visite et une app backgroundée (appel entrant — constant en chantier) perd tout : `forceMount` sur les `TabsContent` (`ui/Tabs.jsx:38-46`, natif Radix) + persister onglet/intervention en `sessionStorage`. (c) Un upload photo/mémo échoué hors-ligne affiche un `toast.error` jumeau du « mis en file » de succès du panneau voisin (`InterventionFieldExecution.jsx:312-322`) : la photo obligatoire est PERDUE sans le comprendre — message d'échec DISTINCT et persistant (« Photo NON envoyée — reprenez-la au retour du réseau ») ; la file binaire IndexedDB reste territoire de FG386 (jamais un 2ᵉ outbox). DoD aussi : vérifier qu'un rôle Technicien réel passe `ajouter-reserve` (`views/intervention.py:1286`, `IsResponsableOrAdmin`) — sinon flag `[BACKEND]` one-liner. **Done =** statut modifiable depuis /ma-journee avec blocage serveur lisible ; re-visite d'onglet sans spinner ; reprise après backgrounding au même endroit ; échec photo distinct + test réseau coupé. Files: `MaJourneePage.jsx`, `InterventionFieldExecution.jsx`, `InterventionCapturePanels.jsx`, `ui/Tabs.jsx`. (ROUTINE — M, sonnet) (@lane: frontend/terrain)
- [x] VX106 — **La signature client sort de sa tombe (FG69 : modèle + endpoint + offline construits, 0 écran).** `signature_client`/`signataire_nom`/`signe_le` (`models_intervention.py:168-170`), POST `signer-client` (`views/intervention.py:1823-1844`), l'op offline `SIGNER_CLIENT` (`fieldOutbox.js:24`) + handler (`field_sync.py:202-217`) existent tous — un seul fichier frontend les référence (vérifié). Chaque « c'est signé ? » redevient un appel ; le compte-rendu ne vaut pas preuve. Nouveau `SignatureClientPanel` réutilisant `SignaturePad` (`features/logistique/SignaturePad.jsx` — canvas Pointer Events, zéro dépendance), envoyé via `withOfflineFallback(FIELD_OPS.SIGNER_CLIENT)`, onglet dans `MaJourneePage` + `InterventionsPage` ; référencer la signature dans le compte-rendu d'intervention (`intervention_pdf.py` — PDF d'intervention, PAS le moteur `/proposal`, hors règle #4). **Done =** capturer/envoyer (ou mettre en file hors-ligne), afficher « Signé par X le … » ; compte-rendu montre la signature si présente. Files: `frontend/src/features/installations/SignatureClientPanel.jsx` (nouveau) + points de montage. (ROUTINE — M, sonnet) (@lane: frontend/terrain) *(⚠ NT `NTFSM11` propose de RE-créer des champs signature (`signature_client_key`/`nom_signataire`/`date_signature`) apparemment sans savoir que FG69 existe — probable doublon du plan NT à corriger AVANT que sa lane ne bâtisse un schéma parallèle ; CETTE tâche consomme les champs RÉELS existants.)*
- [x] VX107 — **Résumé client en lecture seule dans le flux terrain (garantie + dernier ticket SAV).** « C'est encore sous garantie ? Vous êtes déjà venus ? » sur site = appel bureau ou navigation vers la page bureau de 1 604 lignes — 3-5 min/occurrence, plusieurs fois/semaine. Petite section « Infos client » lecture SEULE dans le Sheet d'intervention : garantie du matériel principal, dernier ticket SAV ouvert, date de mise en service — mêmes appels `savApi` déjà en prod dans `InstallationDetail.jsx:280-286`, aucune route nouvelle. Quand ARC46 (`RecordShell`) atterrira, cette section y migrera. **Done =** garantie + dernier ticket visibles sans quitter le Sheet ; zéro écriture. Files: `frontend/src/features/installations/InterventionFieldExecution.jsx`. (ROUTINE — M, sonnet) (@lane: frontend/terrain)

**O6 — L'harmonie avec le monde extérieur (Excel / WhatsApp / téléphone) :**
- [x] VX108 — **`tel:`/`wa.me` partout où un numéro s'affiche (pas seulement les leads).** Le tap-to-call n'existe QUE sur les leads CRM ; `ClientDetailPanel` n'affiche même pas le téléphone, `FournisseurFiche360` non plus, le contact site d'`InstallationDetail.jsx:976-977` est un `<Input>` non cliquable, SAV rien — chaque rappel = recomposition manuelle, plusieurs fois/jour sur 4 rôles. Extraire `telHref`/`waHref` de `LeadCard.jsx:49-60` en util partagé `lib/contactLinks.js` et câbler les 4 écrans (l'input reste éditable en mode édition ; l'affichage devient un lien). **Done =** les 4 écrans rendent un lien `tel:` tapable partout où un numéro s'affiche ; hooks e2e intacts. Files: `frontend/src/lib/contactLinks.js` (nouveau), les 4 écrans. (ROUTINE — S, haiku) (@lane: frontend/interop)
- [x] VX109 — **Importer fournisseurs & équipements : brancher les cibles orphelines d'ExcelImport.** Le pipeline `dataimport` supporte 6 cibles (`services.py:20-70` : dry-run, commit, mémoire de mapping, CSV d'erreurs ré-importable) mais `ExcelImport.jsx` n'est monté que sur 3 (leads/clients/products) : onboarder une liste fournisseurs ou un inventaire d'équipements = saisie manuelle (des heures). Ajouter le bouton « Importer » + `<ExcelImport target=…>` (déjà générique) sur `FournisseursStock.jsx` et `EquipementsPage.jsx` — **`vehicules` est possédé par FE-XFLT22, ne pas doubler.** **Done =** entrée d'import visible sur les 2 pages, un dry-run+commit manuel par cible. Files: `FournisseursStock.jsx`, `EquipementsPage.jsx`. (ROUTINE — S, haiku) (@lane: frontend/interop)
- [x] VX110 — **« Copier » vers le presse-papiers depuis toute liste DataTable (TSV → colle propre dans Excel/WhatsApp).** Zéro copie presse-papiers de données (14 hits `clipboard` = secrets/liens, jamais des lignes) : coller 15 noms filtrés dans un groupe WhatsApp = Exporter → retrouver le .csv → ouvrir Excel → re-copier. Ajouter `rowsToTSV` à côté de `rowsToCSV` (`ui/datatable/csv.js` — réutiliser la garde anti-injection `escapeCSVCell`, délimiteur `\t`, sans BOM) + action bulk « Copier » dans `BulkActionBar.jsx` (sélection, sinon lignes filtrées), toast ; pilote sur `ClientList.jsx`. Le TSV est ce qu'Excel produit au copier — collage aligné gratuit. **Done =** « Copier » copie la sélection en TSV collable en colonnes dans Excel ; test du sérialiseur. Files: `frontend/src/ui/datatable/csv.js`, `BulkActionBar.jsx`, `ClientList.jsx`. (ROUTINE — M, sonnet) (@lane: frontend/interop) *(@coord ARC49/53 : DevisList/FactureList migrées hériteront de l'action.)*
- [x] VX111 — **[PRÉMISSE CORRIGÉE] Lier une pièce jointe à une NOTE du chatter lead + la remonter dans le flux mobile.** *Correction du critic Fable : le Lead a DÉJÀ un point d'entrée pièce-jointe fonctionnel — `records.Attachment` whiteliste `('crm','lead')` (`records/models.py:21`), `AttachmentViewSet` est routé, et `LeadForm.jsx:1155-1158` rend un `<AttachmentsPanel model="crm.lead">` avec dropzone FileUpload + progression. Ce n'est donc PAS « aucun point d'entrée / perte de données ».* Le vrai manque, étroit : (a) une pièce jointe n'est pas RATTACHABLE à une note du chatter (le composer Historique de `LeadForm.jsx:521` poste `/crm/leads/{id}/noter/` en texte pur) — ajouter une affordance d'attache au composer (multipart `noter`, réutiliser `FileUpload`) ; (b) surfacer l'`AttachmentsPanel` existant dans le flux MOBILE (aujourd'hui présent surtout desktop). **DÉCISION à trancher dans la tâche : un seul magasin** — réutiliser `records.Attachment` (déjà en place, whitelisté) OU le dépôt GED cross-app — JAMAIS deux magasins parallèles pour la photo d'un lead (c'est exactement la fragmentation qu'ARC26 existe pour arrêter). NE PAS toucher `ChatterWidget` (son seul conscommateur prod est `features/kb/ArticleDetail.jsx` — l'attache y mettrait le bouton sur les articles KB, pas les leads). **Done =** attacher 1 photo à une note lead depuis mobile via le magasin RETENU ; `AttachmentsPanel` atteignable sur mobile ; aucun 2ᵉ magasin créé ; non-régression KB. Files: `frontend/src/pages/crm/LeadForm.jsx`, `apps/crm/views.py` (`noter` multipart), tests. (ROUTINE — M, sonnet) (@lane: frontend/crm) *(@coord NTSRV3 = canal WhatsApp entrant SAV via webhook — mécanisme différent ; ARC26 = politique magasin-unique.)*

**O7 — Le comptable reste dans l'app (persona finance, wiring polish) :**
- [x] VX112 — **La balance âgée cesse d'être un cul-de-sac : drill-down « Relancer » vers les relances filtrées.** `BalanceAgeePage.jsx`'s seule action de ligne ouvre un PDF « Relevé » (:125-133) — aucun chemin pour AGIR sur la dette. Ajouter une 2ᵉ action de ligne `<Link to="/ventes/relances?client={id}">` + lire `?client=` dans `RelancesPage.jsx` (`load()` :50-54) pour pré-filtrer côté client (miroir du `niveauFilter` :167-178, aucun endpoint). **Done =** cliquer la nouvelle icône « Relancer » d'une ligne atterrit sur `/ventes/relances` pré-filtré sur ce client ; PDF « Relevé » intact. Files: `frontend/src/pages/reporting/BalanceAgeePage.jsx`, `frontend/src/pages/ventes/RelancesPage.jsx`. (ROUTINE — S, sonnet) (@lane: frontend/finance)
- [x] VX113 — **FiscalitePage : sélecteur d'exercice (fin de la saisie « Exercice (ID) » à la main).** Le bloc export de `FiscalitePage.jsx:337-353` utilise un `<Input>` brut (placeholder « ex. 3 ») pour l'exercice des exports FEC/liasse/IS, là où `EtatsPage.jsx:249-260` a déjà un `<select>` alimenté par le même `comptaApi.exercices.list()` — un ID d'exercice tapé de travers = un export fiscal faux. Reprendre le `useEffect`+`<select>` d'`EtatsPage`, en gardant le `needsExercice` gating. Zéro backend (`exercices.list()` déjà appelé dans le même fichier). **Done =** le picker d'exercice du bloc export est un `<select>` de libellés réels ; `runExport` inchangé. Files: `frontend/src/features/compta/pages/FiscalitePage.jsx`. (ROUTINE — S, haiku) (@lane: frontend/finance)
- [x] VX114 — **Fin des `window.prompt()` de l'« Export comptable » : vrai sélecteur de dates.** `FactureList.jsx:346-365` (`handleExportComptable`) enchaîne deux `window.prompt()` pour début/fin — aucune validation, dialog navigateur moche incohérent avec le reste. Remplacer par un petit `Dialog` (réutiliser Dialog/FormField/Input déjà importés :26-30) à deux `Input type="date"` défaut mois-en-cours/aujourd'hui, appelant le même `dl()` au submit. **Done =** plus aucun `window.prompt` dans `handleExportComptable` ; dates via inputs `date` ; double-download xlsx+csv inchangé ; `required` sur les deux. Files: `frontend/src/pages/ventes/FactureList.jsx`. (ROUTINE — S, sonnet) (@lane: frontend/finance) (@after: VX97) *(@coord VX19 sweep prompt — créditer ce site ; VX92/VX93/VX97 touchent aussi FactureList — rebase en séquence.)*
- [x] VX115 — **Les KPI du cockpit comptable pointent vers l'écran d'ACTION, + un index « Où trouver mes exports ».** (a) Les cartes `CockpitPage.jsx:45-97` envoient « Créances clients »/« DSO » vers `/comptabilite/etats` (un état, pas une action) — repointer vers `/reporting/balance-agee` (et `/ventes/relances`), garder `/comptabilite/etats` pour Résultat/Trésorerie où c'est juste. (b) Le handoff mensuel au comptable externe est éparpillé sur 4 écrans (FactureList, FiscalitePage, EtatsPage, BalanceAgeePage) : ajouter au Cockpit une petite carte « Où trouver mes exports » = index de navigation (liens vers les 4 destinations, ZÉRO logique d'export dupliquée). **Done =** clic « Créances clients » → balance âgée ; carte index affiche les 4 destinations avec liens. Files: `frontend/src/features/compta/pages/CockpitPage.jsx`. (ROUTINE — S, haiku) (@lane: frontend/finance)
- [x] VX116 — **Relance en lot : proposer « Consigner + aperçu WhatsApp » sans jamais auto-envoyer.** `RelancesPage.jsx:81-93` (`relancerSelection`) ne fait que `relancerFacture` par ligne (consigne une note) — jamais le `whatsapp()` par-ligne (:134-151). Étendre le bouton en petit `DropdownMenu` (pattern « Relance premium » :331-348) : « Consigner uniquement » (inchangé) et « Consigner + aperçu WhatsApp pour chacun » qui ouvre le MÊME dialog aperçu-puis-confirmer par client en séquence (jamais `wa.me` sans clic explicite — règle manuel-wa.me du fondateur, [[agent_actions_plan]]). Coupe le « 10 clics de chasse aux lignes » sans envoi silencieux. **Done =** le dropdown offre les deux options ; « consigner uniquement » byte-identique ; l'option WhatsApp montre l'aperçu par client en séquence, jamais d'auto-envoi. Files: `frontend/src/pages/ventes/RelancesPage.jsx`. (ROUTINE — M, sonnet) (@lane: frontend/finance) *(@coord vérifier non-doublon avec NTTRE12/NTCRD si un envoi-relance-multicanal y est queué avant build.)*

**NE PAS FAIRE (rejets délibérés de l'audit — ne pas re-proposer sans nouveau contexte) :**
- Ne pas rebâtir la fondation design (F120–P171 livrés et bons) — cette vague est de l'ADOPTION et de la signature.
- Ne pas dupliquer ODX5/6/7 (écran Applications, nav filtrée, extraction registre) — queued ; VX8/9/13 s'y adossent.
- Ne pas remettre en cause le découpage backend ODX ni re-fusionner des modules (verdict : continuer tel que planifié).
- Pas de grille d'apps pleine page à la Odoo comme navigation obligatoire (transition lourde critiquée par les utilisateurs Odoo) — le lanceur VX9 est un overlay léger.
- Aucune nouvelle dépendance npm : pas de framer-motion (CSS + Radix suffisent), pas de cmdk (palette maison livrée), pas de lib confetti (CSS-only), pas de leaflet-markercluster.
- Ne jamais toucher les templates PDF devis/facture, PdfCanvas, `/proposal`, `apps/web` (règle #4).
- Pas de funnel-chart branché sur un modèle de pipeline (règle #2 : le funnel STAGES.py n'a pas encore de modèle Lead/Opportunity backing) — seules les COULEURS de stage sont tokenisées (VX26).
- Pas de migration DevisList/FactureList vers le moteur `ui/datatable` dans cette vague (1 720/1 195 lignes, hooks e2e `ap-*` massivement accrochés au DOM actuel ; le gain ne vaut pas le risque sur le chemin de l'argent) — **désormais possédée par ARC49/ARC53 (PLAN.md, 2026-07-08)** : elles s'exécutent APRÈS les tâches VX touchant ces fichiers et en préservent les comportements.
- Pas de son (le silence est le bon choix pour un back-office partagé) ; l'haptique mobile (VX42) tient ce rôle.
- Pas de moteur de theming par tenant (coût élevé, un seul tenant dominant) ; le nom de société au login (VX34) suffit.
- Pas de WebSockets/indicateurs de frappe (précédent S21 [BLOCKED] — infra fondateur) ; le polling 3 s suffit.
- Pas de badges compteurs sur la BottomTabBar (exige un agrégat backend nouveau) — le bandeau « aujourd'hui » (VX27) couvre le besoin.
- Pas de refonte de Landing.jsx (page vitrine interne à faible trafic — la vraie vitrine est `apps/web`, intouchable).
- Pas de photo produit sur le catalogue dans cette vague (exige champ modèle + migration + pipeline d'upload — candidat à une future tâche BACKEND+UI dédiée).
- Pas de clustering cartographique fait main ni d'endpoint de données de démo (hors périmètre frontend-first).

*Rejets round 2 (2026-07-08) :*
- Verrou optimiste Devis/Lead (409 concurrent) — vrai besoin mais exige modèle+serializer backend : territoire YDATA (PLAN.md), pas de doublon ici.
- Lighthouse CI sur le SPA authentifié — OVERKILL (personne ne « bounce » sur un outil interne) ; YHARD7 l'a déjà volontairement laissé optionnel ; VX61 (vitals RÉELS terrain) répond mieux.
- Second gate de budget bundle (BundleMon/size-limit) — YHARD7 possède déjà `check_bundle_budget.mjs` dans le job frontend-perf.
- Matrice Firefox toujours-active — aucun utilisateur Firefox connu ; VX68 = Chromium+WebKit PR-only, le bon ratio.
- Snapshots dark/RTL en matrice dédiée — OVERKILL tant que VX74 n'a pas tranché l'arabe ; si l'AR UI devient réel, ÉTENDRE VX70.
- Serveur de feature-flags + dashboard qualité BI — OVERKILL à 2-5 utilisateurs ; les toggles env existants suffisent.
- Couverture screenshot exhaustive — la taxe de baselines dépasse la valeur ; VX70 reste à 6-8 écrans.
- `useTransition`/virtualisation supplémentaire — aucun long-task MESURÉ ne le justifie (les gels prouvés sont réseau-sériels → VX54/55) ; attendre les données RUM de VX61.
- Service worker de cache API — interdit sur données authentifiées (fuite inter-sessions) ; le precache d'app-shell existe déjà.
- File offline nouvelle — N91/F21 livrés, FG386 possède l'extension ; jamais un second outbox. Snapshot visuel du PDF devis — YTEST10. N+1 devis — QPERF1. Enveloppe d'erreur API/X-Request-Id/429 — YAPIC.

*Rejets round 3 (2026-07-09 — dédup contre les 2 084 tâches NT `docs/new_tasks_plan.md`) :*
- **2FA « se souvenir de cet appareil »** — ABANDONNÉ : `NTSEC14` (« Device trust ») construit la MÊME feature avec un design STRICTEMENT MEILLEUR (modèle `TrustedDevice` révocable + gate société `allow_device_trust` + audit) ; bâtir une version cookie-only ici créerait un 2ᵉ mécanisme parallèle. Attendre/construire NTSEC14.
- **Composant Corbeille générique `<CorbeillePanel>` + écran `/parametres/corbeille`** — possédé par `NTUX7` (app `apps/trash`, `ElementSupprime`, hook event-bus, purge/permissions/audit) ; VX96 ne fait que rendre `Lead` premier adoptant du soft-delete + l'undo-toast.
- **Formulaire de saisie DemandeAchat avec recherche-catalogue** — possédé par `NTP2P3` ; VX102 se limite aux points de montage mobile.
- **Refonte du chatter / 14ᵉ classe `*Activity`** — VX23 (ChatterTimeline) + ARC8/ARC9 ; VX97/VX111 ne font que consommer/monter.
- **Unifier le moteur d'approbation / matrice objet×montant×département** — ARC10 + `NTWFL1` ; VX86/99/100/101/103 câblent l'inbox/signaux AU-DESSUS des 5 sources actuelles et se ré-évaluent si le moteur unifié passe d'abord.
- **Page « Ma journée commerciale » dédiée / bandeau SLA séparé** — 6ᵉ silo ; VX83 « Ma file » absorbe ces sources (relances FG31, leads chauds/SLA, devis expirants).
- **Inbox mentions dédiée `/mentions`** — `NTCOL17` ; VX85 ne fait que réparer le `link` manquant que NTCOL17 exige.
- **Optimiseur de tournée 2-opt avancé** — `NTFSM3` ; VX88 ne fait que consommer l'endpoint `ma-tournee` déjà livré.
- **Undo de l'édition en masse** — `NTUX6` ; VX95 câble `toastWithUndo` sur archive/kanban seulement.
- **Paste-grid Excel (coller 5 lignes)** — différé : à 2-10 employés, l'import fichier (VX109) + « Copier » TSV (VX110) couvrent le volume réel.
- **KPI perso « mes-stats » pour le rôle normal, classement inter-pairs** — différé : vraie motivation mais exige endpoint + RBAC ; re-proposer une fois « Ma file » prouvée, jamais de classement au rôle normal.
- **Correction de ligne de paiement / suppression** — DECISION fondateur (implications GL sous le verrou de période FG115) : logguer la décision (immutable-par-avoir vs endpoint de correction) avant tout build ; détail dans `persona-finance.md`.
- **Client-360 complet, import relevé bancaire OCR, recompute TVA depuis le GL** — logés dans `persona-finance.md`, différés : croisent NTFIN/NTTRE/NTCRD (146 tâches finance NT) → passer une dédup dédiée avant de construire.
- **Re-surfacer l'abonnement iCal (FG6)** — une ligne dans VX46 « Mes préférences » (extension par référence), pas une tâche : le feed + le bouton « Copier » existent déjà sur CalendarPage.
- **Attention fold cross-lane (critic Fable)** — `FactureList.jsx` (VX92/93/97/114), `NotificationBell.jsx` (VX84/86 + VX14/56), `Dashboard.jsx` (VX86/VX27) sont édités par plusieurs lanes : rebaser en séquence (les `@after`/`@coord` posés) ou fusionner par fichier au build — jamais deux lanes concurrentes sur le même fichier.

### Groupe VXD — approfondissement forensique (rework 3 axes, 2026-07-10)

Provenance : rework forensique en 3 axes (beauté / robustesse / amour-employé), ~30 lanes
d'audit + synthèses Fable par axe + une méta-critique Fable finale (`grand-verdict.md`) qui a
contre-vérifié ~20 claims dans le code réel, tué/fusionné/rogné les seeds en collision avec
VX1-116, et corrigé les constats survendus avant transcription. Verdict honnête du méta-critique :
cette passe ne « rapetisse » pas les 3 rounds précédents en VOLUME, mais l'axe robustesse (VXD-A/B)
trouve des bugs d'une gravité qu'aucun round n'avait atteinte — doublon fiscal au retry, paie qui
valide une période avec des bulletins avalés, signature client hors-ligne qui s'évapore, deux
intercepteurs de refresh concurrents qui déconnectent des sessions valides — et la famille
« surfaces fantômes » (VXD-D) prouve que deux features entières (chat Discuss, LeadExpressModal)
rendent sans un seul octet de CSS, qu'un kiosque TV affiche du JSON brut, et qu'un token de focus
soigné est du code mort — des angles morts qu'une lecture JSX-only ne peut pas voir. Axes 2 et 3
ont été livrés partiellement au premier passage (21/45 puis 11/45) et complétés après le
grand-verdict depuis les rapports de lane bruts (`r2-*`, `r3-*`) ; ce qui suit est l'état complet
tel que livré, corrections du grand-verdict déjà appliquées seed par seed. Contraintes héritées à
l'identique du bloc VX : frontend-first, aucune dépendance npm nouvelle sauf tâche taguée
[GATED], ne jamais toucher `apps/ventes/quote_engine/`, `/proposal`, PdfCanvas ni `apps/web`
(règle #4), toute clé de stage vient de `STAGES.py`/`features/crm/stages.js`, jamais un littéral
(règle #2), UI française partout, hooks e2e `ap-*/att-*/pp-*` préservés, `prix_achat`/marge jamais
client-facing, tout scoping multi-tenant côté serveur (`request.user.company`, `perform_create`
force `company`).

---

## TOP PRIORITÉ — 3 bugs constructibles + 1 alerte sécurité (CANDIDAT BUILD)

- [ ] VX117 — **[BUG] CANDIDAT BUILD : `resilientMutation` — fin du doublon fiscal au retry (@lane: frontend/data)
  (devis/facture/paie/rôles).** Trois flux « parent + N lignes en `Promise.all` » laissent des
  documents financiers mi-sauvés et permettent un doublon fiscal silencieux au retry :
  `DevisGenerator.jsx:1019-1020` a un `.catch(() => {})` explicite sur `deleteLigneDevis`, et
  `DevisForm.jsx:40` (`const isEdit = !!devis`, jamais réassigné après un create réussi — idem
  `FactureForm.jsx:41`) fait qu'un retry après échec partiel repart en CREATE et crée un SECOND
  devis/facture. `PaieRunWizard.jsx:127` (`.catch(() => {})`) et `:135` (`catch { /* on continue */
  }`) avalent chaque échec de bulletin puis avancent inconditionnellement la période en VALIDÉE.
  `RolesManagement.jsx:328-338` réassigne en masse sans rapport nominatif sur le chemin
  permissions. Fix (le bon patron existe déjà, payé une fois en ERR63
  `ParametresEntreprise.jsx:470-486`) : extraire `frontend/src/lib/resilientMutation.js`
  (`allSettled` + rapport nominatif `{succeeded, failed:[{item,error}], allOk}` + `resumeId` — le
  parent créé reste exposé, la relance passe en ÉDITION, jamais un second POST) et n'avancer
  l'état parent (VALIDÉE, `deleteRole`, fermeture) que si `allOk`. Files :
  `frontend/src/lib/resilientMutation.js` (nouveau), `DevisGenerator.jsx`, `DevisForm.jsx`,
  `FactureForm.jsx`, `PaieRunWizard.jsx`, `RolesManagement.jsx`. DoD : mock 1 ligne/3 en échec → 2
  persistées, message nomme la ligne, « Réessayer » ne renvoie QUE la fautive et jamais un second
  `createDevis` ; 1 bulletin en échec → période NON avancée + employé nommé ; 1 PATCH rôle en
  échec → rôle non supprimé + liste migrés/en-échec + reprise ciblée. (T1 — M/L, sonnet ; review
  opus : paie + rôles = surfaces finance/auth) (@lane: frontend/data)

- [x] VX118 — **[BUG] CANDIDAT BUILD : surfaces fantômes — deux features entières rendent sans (@lane: frontend/orphans)
  AUCUN CSS + kiosque TV en JSON brut.** (a) le chat interne Discuss — `chat-list-*`, `chat-shell`,
  `chat-thread-*`, `chat-pinned-*`, `chat-composer-*` (11+ noms, 4 fichiers
  `features/messaging/*` : `ConversationList.jsx`, `MessageThread.jsx`, `Composer.jsx`,
  `pages/messaging/ChatPage.jsx`) ont **0 règle** dans les 5 fichiers CSS du repo — la barre des
  messages épinglés, les états active/unread/muted, la liste de conversations retombent sur les
  styles navigateur ; (b) `LeadExpressModal.jsx` — 23 références `lem-*` sans aucun CSS depuis sa
  création, le raccourci « ⚡ Express » mis en avant s'affiche en HTML nu au milieu d'une app
  tokenisée ; (c) `DashboardsTvPage.jsx:76` — page explicitement documentée « pensée pour un écran
  dédié affiché en continu » — rend `<pre>{JSON.stringify(current.layout)}</pre>` : du texte
  développeur monospace sur l'écran que le bureau regarde toute la journée, alors que la rotation
  15s et le refresh 60s sont déjà câblés, seul le renderer manque. Fix : (a)/(b) migrer sur les
  primitives existantes (`cn()` conditionnel + Tailwind pour Discuss dont Avatar/Badge/Input sont
  déjà importés ; `Dialog`+`FormField` pour LeadExpress) — PAS écrire le CSS manquant ; (c)
  consommer `current.layout` avec le kit existant (`Stat`/`ModuleDashboard`/`ui/charts` en mise en
  page plein écran, grands chiffres `text-6xl`, sparklines en grand, contraste lisible à 3 mètres),
  lire la forme réelle du layout retourné par `coreApi.dashboardsTv.list()` avant mapping. Files :
  `features/messaging/ConversationList.jsx`, `MessageThread.jsx`, `Composer.jsx`,
  `pages/messaging/ChatPage.jsx`, `pages/crm/leads/LeadExpressModal.jsx`,
  `pages/reporting/DashboardsTvPage.jsx`. DoD : grep des classes fantômes `chat-*`/`lem-*` = 0 (ou
  chacune couverte par du Tailwind co-listé) ; bandeau épinglé avec fond/bordure visibles
  (capture) ; le modal Express partage le langage des autres dialogues CRM ; test de rendu
  DashboardsTvPage avec layout mock stats/charts → aucun `<pre>`/JSON.stringify dans le DOM ;
  vérification visuelle 1920×1080. (T1 — M, sonnet) (@lane: frontend/orphans)

- [x] VX119 — **[BUG] CANDIDAT BUILD : outbox terrain — une op rejetée par le serveur disparaît en
  silence (incl. signature client).** `offline/outbox.js:117-122` purge un batch 100 % en statut
  `error` sans jamais lire le champ `.error` que le backend renvoie pourtant par opération
  (`field_sync.py:263/266/293/313`) ; l'unique affichage (`OfflineSyncIndicator.jsx:14-23`) rend
  « Connexion rétablie. » dans les deux cas — une SIGNATURE CLIENT capturée hors-ligne
  (`FIELD_OPS.SIGNER_CLIENT`) peut s'évaporer sans trace. Fix : trois classes de résultat dans
  `flush()` (done retirés / `error` GARDÉS en file avec message serveur + compteur de tentatives /
  échec réseau déjà géré), méthode `fieldOutbox.failed()`, indicateur à 3 états (badge rouge « N
  action(s) en échec — voir détail », abandon par op UNIQUEMENT explicite). Le message serveur
  affiché EST le signal de conflit — pas de moteur CRDT, pas une 2ᵉ file offline. Files :
  `offline/outbox.js`, `offline/useFieldOutbox.js`, `offline/OfflineSyncIndicator.jsx`. DoD : batch
  mock 100 % `error` → ops gardées + message par op accessible ; badge distinct rendu ;
  non-régression `applied`/`replayed`. (T1 — M, sonnet) (@lane: frontend/data)

- [x] VX120 — **[BUG] [GATED: génération QR] La graine TOTP 2FA est exfiltrée vers
  `api.qrserver.com` — et la CSP casse l'écran d'activation.** [BACKEND additif]
  `pages/parametres/SecuriteCompteSection.jsx:360-363` construit
  `https://api.qrserver.com/v1/create-qr-code/?...data=${encodeURIComponent(setup.otpauth_uri)}` —
  l'URI `otpauth://` CONTIENT `secret=<graine TOTP>` : le facteur 2FA part en clair chez un tiers
  non contrôlé (logs, MITM, opérateur). Aggravant : la CSP `img-src` (`nginx.conf:78`) n'autorise
  PAS ce domaine → en prod le QR ne s'affiche JAMAIS, l'activation 2FA est cassée
  fonctionnellement. Le repo possède DÉJÀ un générateur QR serveur (`apps/stock/labels.py:368`,
  `qr_svg`). Fix : [BACKEND additif] l'endpoint `2fa/setup/` renvoie un `qr_svg` inline (réutiliser
  `labels.qr_svg` via un helper `authentication` — aucune migration) ; le client le rend via un
  helper `renderTrustedSvg`/`lib/trustedSvg.js` (refuse `<script`/`on*=`/`javascript:`) ; supprimer
  totalement l'appel tiers. Files : `frontend/src/pages/parametres/SecuriteCompteSection.jsx` ;
  `[BACKEND]` `authentication/views` (payload setup). DoD : activer le 2FA n'émet AUCUNE requête
  hors-origine (Playwright `page.on('request')` filtré = 0) ; le QR s'affiche sous la CSP de prod ;
  la graine n'apparaît dans aucune URL. (T1 — M, opus : auth/2FA) (@lane: backend/auth)

**Note d'extension (ne pas double-compter) :** l'audit a confirmé que
`IsResponsableOrAdmin` (`authentication/permissions.py:14-21`, 614 usages / 156 fichiers) laisse
n'importe quelle permission d'écriture ouvrir TOUS les endpoints qu'il garde — le frontend gate
finement mais l'API directe réussit. C'est la MÊME classe de bug que **VX101** corrige côté
`decider_approbation`/`IsAnyRole` (endpoints disjoints, même remède `HasPermissionOrLegacy`) : ce
constat ÉTEND VX101, il n'est pas transcrit comme tâche séparée ici — voir VXD-J / `@coord VX101`
sous VX193 (VXD SEED transcrit avec la même classe de garde) pour le détail d'audit des viewsets
restants.

---

## AXE 1 — BEAUTÉ (VX121–VX158, 38 tâches survivantes sur 44 seeds ; 6 tuées + 1 fusionnée par le
grand-verdict — voir NE PAS FAIRE en fin de section pour le détail des kills/rognages)

**Sous-groupe VXD-E — Craft-physics & tokens (les fondations que 3 rounds n'ont pas atteintes)**

- [ ] VX121 — **Zéro couleur hors token : le sweep CSS et JS, avec garde CI.** Trois strates de (@lane: frontend/ui-core)
  couleur échappent encore à tout token : (a) ~500 hex slate au niveau composant dans `index.css`
  (`.form-control`/`.modal-*` L900-1156, `.lines-table` L1184-1220, `.data-table` L830-862,
  `.lead-nav` L1002-1006, `.page-loading/.page-error` L727-739) ; (b) les 6 ombres d'épinglage
  `rgba(0,0,0,0.25)` du moteur `DataTable.jsx` L477/478/519/627/628/640 — seul noir pur de tout
  `ui/`, bande noire dure en dark mode sur la surface qui portera DevisList/FactureList ; (c) les
  constantes hex JS invisibles à tout grep CSS : `SCORE_COLORS` (`ListView.jsx:77-81`),
  `OWNER_PALETTE` (`CalendarView.jsx:36-39`), les 5 jalons hex de `ChantierTimeline.jsx:6-21`, la
  famille orpheline `--color-*` d'`AppointmentBooker.jsx:81-96` (fallbacks silencieux = rupture de
  theming), les Tailwind bruts `emerald/red` de `ProductionPage.jsx:228`. **Rogné (grand-verdict) :**
  retirer `SCORE_COLORS`/`OWNER_PALETTE`/`NAVY-GOLD` ChartsView (déjà couverts par VX26) et
  NAVY/GOLD PwaPrompts (déjà VX1). Survit : sweep ~500 hex composant d'index.css, ombres pin
  DataTable, hex JS ChantierTimeline/AppointmentBooker/ProductionPage, suppression du bloc CSS mort
  `.agent-*` (`index.css:2209-2270`, 0 consommateur JSX — **@coord VX4**, qui prévoyait de le
  re-tokeniser : la suppression prime, amender le Done= de VX4 d'une note), garde
  `scripts/check_hex.mjs` (grep hex hors `:root`/tokens, branchée dans frontend-lint — script
  maison, zéro dépendance). Files : `index.css`, `design/tokens.css`, `ui/datatable/DataTable.jsx`,
  `features/crm/stages.js`, `ChantierTimeline.jsx`, `AppointmentBooker.jsx`, `ProductionPage.jsx`,
  `scripts/check_hex.mjs` (nouveau). DoD : grep hex hors `:root` = 0 sur les blocs cités ; `grep
  rgba(0,0,0 ui/` = 0 ; dark mode cohérent sur 6 écrans témoins ; garde CI verte puis rouge sur un
  hex injecté. (T2 — L, sonnet) (@lane: frontend/ui-core)

- [ ] VX122 — **La voix typographique : police de marque par défaut + échelle F121 réellement (@lane: frontend/ui-core)
  branchée + finesse française.** Quatre défauts d'une même cause : (a) `index.css:26` rend tout
  le legacy en `font-family: system-ui` alors qu'Archivo/Hanken Grotesk sont préchargées
  (`brand.css`) ; **rogné (grand-verdict) :** ce point (a) est déjà VX3 mot pour mot, ne pas le
  refaire. Survivent : (b) l'échelle F121 (`tokens.css:103-115`) a 4 usages, tous dans UIShowcase —
  câbler `.page-header h2` sur `--text-h1`/`--font-display`, classe `.text-eyebrow` unique
  consommant `--text-caption` (13+ recopies inline avec trackings divergents 0.04 vs 0.05em) ; (c)
  116 sites de libellés FR sans espace fine insécable avant `:`/`;`/`!`/`?` — helper `nbsp()` dans
  `lib/format.js` posé sur les 5 libellés les plus visibles (LeadCard tooltip, EcrituresPage,
  BudgetPage) ; (d) `max-w-prose` sur l'article KB (`ArticleDetail.jsx:321`, 0 `max-w`
  aujourd'hui). Files : `index.css:683-688,840-851`, `design/tokens.css`, `lib/format.js`,
  `features/kb/ArticleDetail.jsx:321`. DoD : les 3 écrans témoins (DevisList/CommercialDashboard/
  Reporting) rendent le même titre sans toucher leur JSX ; `nbsp('Priorité')` vérifiable par
  `codePointAt` ; e2e verts. (T2 — M, sonnet) (@lane: frontend/ui-core)

- [ ] VX123 — **Plancher d'accessibilité visuelle : anneau de focus token-isé consommé partout + (@lane: frontend/ui-core)
  modes de contraste système.** Le token `--focus-ring` (`tokens.css:98`) et l'utilitaire
  `shadow-focus-ring` (L248) sont du code mort décoratif : **24 fichiers** primitifs (corrigé par
  le grand-verdict : pas « 40+ ») répètent en dur `focus-visible:ring-2 ring-ring
  ring-offset-2`, et 6 `outline:none` legacy orphelins subsistent dans `index.css` ; par ailleurs
  `grep forced-colors` = 0 et `prefers-contrast` = 0 — en mode contraste élevé Windows les
  bordures-ombres `--elevation-card` (box-shadow) disparaissent entièrement. Fix : une classe
  utilitaire unique `focus-ring` remplaçant les 24 chaînes (un seul point de vérité du halo), purge
  des `outline:none` non remplacés, puis `@media (forced-colors: active)` mappant carte/bouton/
  focus sur `CanvasText/Highlight/ButtonBorder` et `@media (prefers-contrast: more)` durcissant
  `--border`/`--muted-foreground`. Files : `design/tokens.css`, tous les primitifs `ui/*`
  (remplacement mécanique), `index.css`. DoD : `grep 'focus-visible:ring-2 focus-visible:ring-ring'
  ui/` ≈ 0 ; halo visible au Tab sur chaque contrôle ; émulation forced-colors → cartes/boutons
  délimités ; émulation prefers-contrast → bordures plus marquées ; scan axe (VX71) sans
  régression. (T2 — M, sonnet) (@lane: frontend/ui-core)

- [x] VX124 — **Craft-physics pack : les 4 micro-détails qui signent un produit investi.** Quatre
  absences prouvées par grep (0 résultat chacune) : (a) `caret-color` jamais posé — le curseur de
  saisie reste noir système sur le champ le plus regardé de l'ERP (générateur de devis) ; (b)
  toutes les ombres sont gris-nuit neutre — aucune ombre teintée brass au survol du CTA primaire ;
  (c) le tracking négatif fixe (-0.025em) sur-comprime les montants à 7 chiffres en grande taille ;
  (d) la police variable est chargée (`font-weight: 100 900`, `brand.css:9-17`) mais
  `font-variation-settings` = 0 dans tout le repo — le chiffre KPI de `Stat.jsx:26` pourrait « se
  solidifier » (wght 500→600 sur 400ms au montage, saut direct sous reduced-motion). Fix :
  `caret-color: var(--primary)` sur Input/Textarea/NumberInputs ; token `--shadow-primary-hover`
  (color-mix brass 35%) sur le seul variant `default` de Button ; règle
  `.tabular-nums.text-display/.text-h1 { letter-spacing: -0.01em }` ; transition wght sur Stat.
  Files : `ui/Input.jsx`, `ui/NumberInputs.jsx`, `ui/Textarea.jsx`, `ui/Button.jsx:27`,
  `ui/Stat.jsx`, `design/tokens.css`. DoD : curseur teinté visible au focus ; ombre du CTA ≠ gris
  neutre (preview_inspect) ; montant 7 chiffres moins collé (capture) ; `getComputedStyle` du Stat
  montre la transition de wght, neutralisée sous reduced-motion. (T3 — S/M, sonnet) (@lane:
  frontend/ui-core)

- [ ] VX125 — **[DECISION] Gouvernance anti-monday : budget de densité de signaux + badge de (@lane: frontend/brand)
  maturité de module.** La plainte structurelle n°1 de monday.com 2026 (« density of statuses,
  colors, and columns… overwhelming ») est la trajectoire que VX construit un badge à la fois
  (VX84 cloche, VX86 approbations, VX98 fraîcheur, VX27 KPI) sans qu'aucune tâche ne pose de règle
  d'arbitrage ; la leçon Ramp-Travel (un module neuf médiocre contamine la perception du cœur
  mature) n'a aucun équivalent. Fix : un document court (< 30 lignes)
  `docs/design-density-budget.md` posant le plafond « 3 signaux ambiants simultanés par écran de
  liste, jamais deux signaux répétant le même chiffre », référencé depuis CODEMAP §4 comme
  contrainte transversale ; plus un `<BetaBadge>` discret optionnel sur la nav des modules jeunes
  avec critère objectif de retrait. Files : `docs/design-density-budget.md` (nouveau),
  `design/tokens.css` (commentaire), option `components/layout/Sidebar.jsx`. DoD : le document
  existe, cite le plafond, est référencé ; le CODEMAP est re-fingerprinté dans le même commit ;
  aucune tâche existante modifiée. (T3 — S, sonnet) (@lane: frontend/brand)

**Sous-groupe VXD-F — Primitives last-mile (la mécanique d'état que Button seul possède)**

- [x] VX126 — **L'état PRESSÉ propagé : 12+ contrôles cessent d'être morts au clic, courbes
  unifiées.** `grep active:` = Button uniquement : Switch, Slider, Segmented, Tabs, Checkbox,
  Radio, items Select/Combobox/MultiSelect/DropdownMenu/ContextMenu, cellules DatePicker — aucun
  retour pressé ; sur mobile 4G l'absence de feedback tactile fait re-taper. En plus :
  Checkbox/Radio sans `hover:` (cibles « froides » dans les listes denses), le pouce du Switch sans
  squish et le thumb du Slider sans halo au grab, et Switch/Progress héritent du défaut Tailwind
  `150ms ease` linéaire-ish pendant que Button câble `cubic-bezier(0.23,1,0.32,1)` — deux vitesses
  de mouvement côte à côte, Checkbox sans aucune transition de coche. Fix : utilitaire partagé
  `press` calqué sur le pattern prouvé `Button.jsx:20`
  (`[@media(hover:hover)]:active:scale-[0.98]` + assombrissement), posé sur tous les
  triggers/items ; `hover:border-primary/60` sur cases/radios ; squish Switch + halo/scale thumb
  Slider ; alignement de la courbe Button sur Switch/Progress + scale-in de coche Checkbox. Files :
  les 12 primitifs `ui/*` cités + un utilitaire partagé. DoD : test de rendu par contrôle
  assertant la classe pressée ; courbes identiques par `transition-timing-function` calculée ;
  rien sous `hover:none` ; e2e inchangés. (T2 — M, sonnet) (@lane: frontend/ui-core)

- [ ] VX127 — **L'état LECTURE-SEULE existe enfin + EditableCell honnête (pending/erreur (@lane: frontend/ui-core)
  serveur/readOnly).** Aucun primitif ne distingue `readOnly` de `disabled` : une référence de
  devis ou un total TTC affiché en Input apparaît soit éditable soit grisé opacité 60 % (illisible,
  non copiable). Et `EditableCell.jsx:108` commit au blur sans état « enregistrement en cours »,
  sans rendu d'un rejet serveur (seule la validation locale L45-54 est gérée), sans mode
  lecture-seule par rôle — une perte de confiance silencieuse au cœur du DataTable. Fix : variant
  Tailwind natif `read-only:` sur Input/Textarea/Select (fond `bg-muted/40`, curseur default,
  texte pleine opacité, pas de ring éditable) ; EditableCell gagne un spinner discret pendant
  l'`await onSave`, rouvre avec message sur rejet, et une prop `readOnly` (double-clic sans effet).
  Files : `ui/Input.jsx`, `ui/Textarea.jsx`, `ui/Select.jsx`, `ui/datatable/EditableCell.jsx`. DoD :
  `<Input readOnly>` visuellement ≠ disabled, sélectionnable ; `onSave` lent → spinner ; `onSave`
  rejeté → cellule rouverte + message ; tests unitaires des trois états. (T2 — M, sonnet) (@lane:
  frontend/ui-core)

- [ ] VX128 — **Comboboxes audibles : `aria-activedescendant` câblé (0 occurrence dans tout le (@lane: frontend/ui-core)
  repo).** `Combobox.jsx`, `MultiSelect.jsx`, `TimePicker.jsx` gèrent un curseur visuel
  (`data-cursor`, flèches) mais l'input `role="combobox"` ne pointe jamais l'option active — un
  utilisateur NVDA/VoiceOver entend « zone de liste » puis RIEN en parcourant ; c'est LE trou du
  pattern combobox selon WAI-ARIA APG, purement additif à corriger. Fix : id stable par option
  (`${listId}-opt-${i}`), `aria-activedescendant` posé sur l'input suivant le curseur,
  `aria-selected` déjà présent. Files : `ui/Combobox.jsx`, `ui/MultiSelect.jsx`,
  `ui/TimePicker.jsx`. DoD : test — ouvrir, flèche bas, `input.getAttribute('aria-activedescendant')`
  === id de la 2ᵉ option ; le scan axe (VX71) le détecte corrigé. (T2 — S/M, sonnet) (@lane:
  frontend/ui-core)

- [ ] VX129 — **Primitives complétées : menus pro, Textarea adulte, Progress indéterminé, Avatar (@lane: frontend/ui-core)
  riche, UNE grammaire de chip.** Pack de complétude sur 6 primitifs, tous prouvés incomplets par
  grep : (a) menus sans `RadioItem`/`Sub`/`SubTrigger` (0 occurrence) ni slot raccourci —
  ContextMenu n'a même pas CheckboxItem ; (b) Textarea nu : resize navigateur, ni autoResize ni
  compteur `maxLength` ; (c) Progress sans état indéterminé, Stat avec glyphes texte `▲/▼` au lieu
  de lucide et sa propre mini-map de tons ; (d) Avatar taille fixe sans statut de présence,
  AvatarGroup sans « +N » ; (e) QUATRE grammaires de chip divergentes — Badge rounded-full, Tag
  rounded-md, StatusPill, jetons inline MultiSelect L144-158 ; (f) Popover/HoverCard sans flèche
  d'ancrage alors que Tooltip en a une (prop `arrow` opt-in). Fix : ajouts Radix habillés sur le
  pattern `menuContent`/`menuItem` existant, props additives, alignement des rayons/hauteurs de
  chip sur une base commune consommée par MultiSelect. Files : `ui/DropdownMenu.jsx`,
  `ui/ContextMenu.jsx`, `ui/Textarea.jsx`, `ui/Progress.jsx`, `ui/Stat.jsx`, `ui/Avatar.jsx`,
  `ui/Tag.jsx`, `ui/Badge.jsx`, `ui/MultiSelect.jsx`, `ui/Popover.jsx`, `ui/HoverCard.jsx`. DoD :
  menu radio exclusif + sous-menu + shortcut aligné à droite (tests de rôles) ; autoResize +
  compteur ; `<Progress indeterminate>` balaie et se fige sous reduced-motion ; `<AvatarGroup
  max={3}>` de 5 → « +2 » ; jetons MultiSelect et Tag partagent rayon/hauteur (inspection). (T2 —
  L, sonnet) (@lane: frontend/ui-core)

- [ ] VX130 — **Le toast devient un objet de marque : tokens, icônes lucide, durées motion, (@lane: frontend/ui-core)
  registres réels.** `Toaster.jsx:13` délègue tout à sonner `richColors` : couleurs génériques hors
  tokens `--success/--warning/--info` (divergentes en dark), icônes internes sonner alors que TOUT
  le reste de l'app est lucide, durées indépendantes de `--motion-*`, et un vocabulaire binaire —
  503 `toast.error` / 360 `toast.success` / 1 info / 1 warning dans tout le repo, aucun registre
  destructif à délai d'annulation prolongé. Fix : retirer `richColors`, styler par type via
  `toastOptions.classNames` + tokens, injecter les icônes lucide
  (`CheckCircle2/AlertTriangle/Info`), surcharger la durée via `--motion-base`, formaliser
  `toastInfo`/`toastWarning` stylés + un registre destructif ≥ 6s, avec ≥ 8 poses réelles
  d'avertissement. Files : `ui/Toaster.jsx`, `lib/toast.js`, `index.css` (règle
  `[data-sonner-toast]`). DoD : toast succès dérivé de `--success` en clair ET sombre (parité
  Badge) ; même glyphe AlertTriangle que l'EmptyState d'erreur ; changer `--motion-base` affecte
  les toasts ; 4 variantes distinctes testées. (T2 — M, sonnet) (@lane: frontend/ui-core)

- [ ] VX131 — **Des états qui disent vrai : `tone` sur EmptyState, CTA sur les listes principales, (@lane: frontend/orphans)
  page 403.** Trois trous du même système : (a) les 267 poses d'EmptyState partagent le wrapper
  gris neutre — un ÉCHEC de chargement est visuellement identique à « rien à afficher » ; pire,
  `DataTable.jsx:385` (erreur) garde l'icône grise quand `ErrorBoundary.jsx:38` la colore ; (b)
  ~207/267 EmptyState n'ont pas de CTA, y compris sur des listes qui ONT un bouton « Nouveau » dans
  leur toolbar (modèle parfait : `ClientList.jsx:347-356`) ; (c) `ui/NotFound.jsx` existe mais
  AUCUN `Forbidden`/403 — un refus de rôle retombe sur un toast technique ou rien. Fix : prop
  `tone` (`neutral|error|warning`) sur EmptyState calquée sur ErrorBoundary, migration de
  DataTable/ModuleDashboard ; passe CTA sur les ~15 listes principales (Stock, Tickets SAV,
  Installations…) ; `ui/Forbidden.jsx` jumeau de NotFound, câblé aux gardes de permission. Files :
  `ui/EmptyState.jsx`, `ui/datatable/DataTable.jsx:381-388`, `ui/Forbidden.jsx` (nouveau), ~15
  écrans de liste. DoD : `<EmptyState tone="error">` = icône sur fond destructif (3 tons testés) ;
  liste vide → même CTA que la toolbar (test) ; route refusée → écran 403 dédié (pas le 404). (T1 —
  M, sonnet) (@lane: frontend/orphans)

- [ ] VX132 — **L'attente premium : shimmer, crossfade, squelettes honnêtes, anti-scintillement (@lane: frontend/ui-core)
  propagé, chargement long conscient.** Cinq défauts d'une même expérience : (a) `Skeleton.jsx:11`
  est le pulse Tailwind par défaut — pas de balayage lumineux directionnel (CSS pur, motion-safe
  gardé) ; (b) le passage squelette→contenu est un swap sec partout — pas de `<FadeSwap>`
  générique ; (c) le squelette DataTable affiche 6 lignes fixes quel que soit `pageSize` → saut
  brutal vers 50 lignes réelles (dériver `Math.min(pageSize, 12)`) ; (d) `useDelayedLoading` —
  fini, documenté, testé — n'est utilisé que sur 6 fichiers/265 pendant que 73 écrans affichent un
  Spinner nu qui scintille (propager aux ~15 listes principales) ; (e) la génération PDF premium
  (latence connue, la plus longue de l'app) montre un spinner muet — un hook `useRotatingLabel` fait
  tourner 3-4 libellés honnêtes (« Mise en page des schémas… ») toutes les ~2.5s, sans fausse barre
  de progression (ne touche QUE le bouton côté client, jamais le moteur — règle #4). Files :
  `ui/Skeleton.jsx`, `ui/FadeSwap.jsx` (nouveau), `ui/datatable/DataTable.jsx` (~L540-550),
  `hooks/useRotatingLabel.js` (nouveau), les call-sites `generer-pdf` de DevisList/FactureList, ~15
  écrans Spinner. DoD : shimmer visible clair+sombre, pulse identique sous reduced-motion ;
  chargement <300ms → aucun spinner (test promesse 100ms) ; squelette ∝ pageSize sans saut de
  scroll ; ≥ 2 libellés visibles sur le chemin PDF long. (T2 — L, sonnet) (@lane: frontend/ui-core)

**Sous-groupe VXD-F (suite) — Chorégraphie de mouvement**

- [ ] VX133 — **Grammaire directionnelle des surfaces : chaque overlay entre par où il vit.** Un (@lane: frontend/motion)
  seul keyframe `pop-in` (translateY 4px + scale 0.97, conçu pour un popover ancré) sert 14
  primitifs aux géométries incompatibles : le `Sheet` latéral de 26rem « pop » du centre au lieu de
  glisser de son bord (`Sheet.jsx:32`, 13 consommateurs), alors que la preuve du bon glissement
  existe déjà en bespoke (`.ldp-panel`/`@keyframes ldpIn`, `index.css:3393-3407` — 2 usages,
  dupliqués par copier-coller) ; `BulkActionBar.jsx:23` fait `if (!count) return null` → JAMAIS
  d'animation de sortie malgré le commentaire qui prétend « glisser depuis le bas » ;
  `AccordionContent` n'anime pas sa hauteur (`--radix-accordion-content-height` = 0 occurrence) ;
  `TabsContent` swap sans crossfade. Fix : 4 keyframes `slide-in/out-{right,left,top,bottom}` +
  `accordion-down/up` dans tokens.css (mappés `--motion-*` donc annulés par reduced-motion),
  mapping `SIDE → animationClass` dans Sheet, migration de LeadDevisPanel/InstallationDetail sur
  `SheetContent side="right"` + suppression de `.ldp-*`, BulkActionBar monté en permanence avec
  état `visible` retardé (pattern exit-sans-lib) + slide-up, fondu court `--motion-fast` sur
  TabsContent. Files : `design/tokens.css`, `ui/Sheet.jsx`, `ui/Accordion.jsx`, `ui/Tabs.jsx`,
  `ui/datatable/BulkActionBar.jsx`, `pages/crm/leads/LeadDevisPanel.jsx`,
  `pages/installations/InstallationDetail.jsx`, `index.css` (−25 lignes ldp). DoD : Sheet
  `side="right"` translate en X ; grep `ldp-panel` = 0 ; désélectionner la dernière ligne montre
  une sortie glissée ; accordéon anime sa hauteur ; reduced-motion = instantané partout ; tests de
  rendu par côté. **@coord VX43** (Sheet.jsx partagé / bottom-sheets mobile). (T2/T3 — M/L, sonnet)
  (@lane: frontend/motion)

- [ ] VX134 — **Chorégraphie de coquille : ⌘K, sidebar, route, badge, thème — cinq (@lane: frontend/motion)
  téléportations soignées.** Cinq surfaces de la coquille bougent « sec » : (a) la palette ⌘K
  réutilise le Dialog générique centré-zoomé — s'ancrer en haut avec un slide-down rapide
  `--motion-fast` ; (b) le liseré doré actif de la sidebar (`index.css:396-412`, pseudo-élément par
  item, 0 transition) téléporte entre items au lieu de glisser (fallback fondu si la mesure DOM est
  jugée invasive) ; (c) le contenu de route post-Suspense apparaît en cut dur — un fondu
  `key={pathname}` (pattern déjà utilisé par RouteErrorBoundary juste à côté,
  `router/index.jsx:198`) suffit, View Transition API notée en option future ; (d) le badge
  non-lus de `ChatBell.jsx:38` change de valeur toutes les 30s sans aucun signal — pulse scale
  1→1.25 UNIQUEMENT quand le total augmente ; (e) `applyTheme` bascule `.dark` d'un coup — le mode
  sombre OKLCH mérite une transition ≤ 200ms via classe transitoire, sans FOUC. Files :
  `providers/CommandPalette.jsx`, `ui/Dialog.jsx` (variante `command`),
  `components/layout/Sidebar.jsx`, `router/index.jsx`, `components/layout/ChatBell.jsx`,
  `design/theme.js`, `index.css`, `design/tokens.css` (keyframe `command-in`, `badge-pulse`). DoD :
  ⌘K ancrée haut plus rapide qu'un modal ; naviguer fait glisser/fondre le repère sidebar ;
  changement de route = fondu doux ; badge pulse seulement à l'incrément (test mock store) ;
  bascule de thème fluide, instantanée sous reduced-motion, classe transitoire retirée (test).
  **@coord axe3-VX190** (refonte cloche — ce seed ne touche que l'animation du compteur, pas son
  contenu). (T2/T3 — M, sonnet) (@lane: frontend/motion)

- [ ] VX135 — **Mouvement piloté par JS rendu accessible + FLIP des listes.** La garde globale (@lane: frontend/motion)
  reduced-motion (`index.css:67-77`) ne neutralise QUE les animations CSS déclaratives : les
  transforms posés en JS par dnd-kit y échappent structurellement — le tilt `rotate(2deg)
  scale(1.02)` de la carte kanban tenue reste actif pour un utilisateur vestibulaire, aucun des 3
  kanbans ne passe `dropAnimation` (timing dnd-kit par défaut, désaligné des tokens), et la carte
  saute au tilt sans transition de grab ; le `Spinner` tourne en `animate-spin` nu pendant que
  Skeleton est correctement `motion-safe` ; et AUCUNE liste de l'app n'anime tri/filtre/ajout (0
  framer-motion, télé-portation des lignes). Fix : hook partagé `usePrefersReducedMotion()`
  (matchMedia + listener) consommé par les 3 kanbans (tilt désactivé, dropAnimation
  `{duration:180, easing:cubic-bezier(0.23,1,0.32,1)}` ou 1ms) ; `transition: transform 120ms
  var(--ease-out)` sur `.kb-drag-overlay .kb-card` ; `motion-safe:` sur Spinner avec repli
  statique lisible ; FLIP minimal sans dépendance dans DataTable (mesure
  getBoundingClientRect avant/après tri/filtre, translateY transitionné, plafonné < 200 lignes,
  désactivé par le hook). Files : `hooks/usePrefersReducedMotion.js` (nouveau),
  `pages/crm/leads/views/KanbanView.jsx`, `pages/installations/views/KanbanView.jsx`,
  `features/gestion_projet/components/TachesKanbanView.jsx`, `index.css`, `ui/Spinner.jsx`,
  `ui/datatable/DataTable.jsx` (hook `useRowFlip`). DoD : reduced-motion émulé → plus de
  tilt/rotation pendant le drag, spinner figé ; dépose calée sur les tokens ; trier une colonne
  fait glisser les lignes (test non-régression `datatable.test.mjs`). (T2/T3 — M/L, sonnet ; opus
  si le hook FLIP doit se partager avec ARC49/53 — coordonner, ne pas dupliquer) (@lane:
  frontend/motion)

- [ ] VX136 — **Scroll-timeline natif : reveal des cockpits + progression des formulaires (@lane: frontend/motion)
  longs.** `grep view-timeline|animation-timeline` = 0 : aucun usage du mécanisme 2026 (compositor
  thread, zéro JS d'orchestration, progressive enhancement pur). Deux poses à haute valeur : (a)
  les cartes KPI de `ModuleDashboard` se révèlent (translateY 8px→0 + fondu) via `@supports
  (animation-timeline: view())`, fallback état final statique ; (b) une barre `ScrollProgress` de
  2px en haut des deux formulaires-fleuves (LeadForm 1297 l., DevisGenerator 2319 l.) via
  `animation-timeline: scroll(nearest)`. Files : `ui/module/ModuleDashboard.jsx`,
  `ui/ScrollProgress.jsx` (nouveau), `pages/crm/LeadForm.jsx`, `pages/ventes/DevisGenerator.jsx`,
  `index.css` (`.reveal-on-scroll`). DoD : Chromium — reveal au scroll + barre qui grandit
  0→100 % ; Firefox/Safari <18 — apparition instantanée, aucune erreur ni layout cassé ;
  reduced-motion désactive la timeline. (T2/T3 — M, sonnet) (@lane: frontend/motion)

**Sous-groupe VXD-G — Ventes : le chemin de l'argent (l'écran vendeur le plus vu du produit)**

- [x] VX137 — **La table de lignes du générateur sort du HTML brut. @after VX17.** `DevisGenerator.jsx`
  L1965-2091 : `<input className="form-control form-control-sm">` natifs alors que le MÊME fichier
  utilise Input/Select/Textarea du design system dans ses 9 autres cartes ; hex codés dans le JSX
  restants après VX17 (le sweep tokens/couleurs `.gen-metric*`/`.lines-table*` est déjà fait par
  **VX17** — ce delta ne recouvre QUE le remplacement `<input class="form-control">` natif par
  `ui/Input` dans la table). Attention absolue : le formulaire reste `noValidate`/`step="any"`
  (règle CLAUDE.md, gardé par test) et l'indicateur de marge (`prix_achat`) reste generator-only.
  Files : `pages/ventes/DevisGenerator.jsx` (L2000-2192). DoD : `grep "style={{ color:"
  DevisGenerator.jsx` = 0 ; capture dark mode avant/après ; test « saisie jamais rejetée » vert.
  (T2 — S, sonnet) (@lane: frontend/ventes)

- [ ] VX138 — **L'aperçu de simulation devient un comparateur : Sans/Avec groupés, chiffres héros (@lane: frontend/ventes)
  stables, totaux hiérarchisés, CTA sticky, cartes selon le mode.** Le moment de vente en direct
  souffre de cinq défauts convergents : (a) jusqu'à 12 `MetricCard` dans UNE grille homogène — les
  paires Sans/Avec batterie ne sont reliées que par une étoile noyée → 2 colonnes nommées « Option
  1/2 », recommandation en liseré de colonne ; (b) les chiffres ROI héros
  (`.gen-metric-value`/`.gen-kwp`, `index.css:2577-2586/2692-2697`) n'ont AUCUN `tabular-nums` — ils
  tremblent horizontalement pendant la frappe devant le client, et `fmtNum` local (L79) duplique
  `formatNumber` sans jamais importer `lib/format.js` ; (c) la chaîne Sous-total→Remise→Total
  HT→TVA→TTC est plate à l'écran alors que le PDF la hiérarchise — appliquer une progression
  `text-small`→`text-body medium`→`text-h3 semibold+primary` avec les paliers F121 existants ; (d)
  `.gen-actions-sticky` n'est sticky QUE sous media query mobile — bandeau sticky desktop affichant
  le TTC courant (dérivé de `totals` déjà en mémoire) + bouton condensé ; (e) les cartes non
  pertinentes pour le mode actif gardent le même poids — « Multi-propriétés » développée par défaut
  même en agricole : accordéon replié, jamais masqué. Files : `pages/ventes/DevisGenerator.jsx`
  (L79, L1810-1844, L2093-2194, L2251-2273, L1886-1961), `index.css` (blocs `.gen-*`). DoD : mode
  « Les deux » → 2 colonnes alignées ; les chiffres ne tremblent plus (glyphes à largeur fixe, test
  rendu) ; 3 paliers visuels sur les totaux, TTC point focal ; barre sticky au scroll desktop, même
  handler de soumission ; bloc multi-propriétés replié par défaut en agricole. (T2 — L, sonnet)
  (@lane: frontend/ventes)

- [x] VX139 — **Deux éditeurs de devis, UNE présentation des totaux et UNE devise. @coord VX75.**
  Le même métier (lignes + remise + TVA + totaux) rend différemment selon le point d'entrée :
  `DevisForm.jsx` L372-395 (propre, tokens, suffixe « DH » codé en dur `toFixed(2)`) vs
  `DevisGenerator` `.gen-total-*` (hex inline, suffixe « MAD ») — le vendeur qui crée puis édite
  voit deux présentations de prix du même document. Fix : extraire
  `features/ventes/QuoteTotalsSummary.jsx` (props lines/totals/discountPct/tauxTva) consommé par
  les deux écrans, formaté par `formatMAD` de `lib/format.js` (une seule devise affichée), hérite
  de la hiérarchie de poids de VX138. Files : `features/ventes/QuoteTotalsSummary.jsx` (nouveau),
  `pages/ventes/DevisForm.jsx` (L372-395), `pages/ventes/DevisGenerator.jsx` (L2093-2194). DoD :
  `grep '"DH"\| DH' DevisForm.jsx` = 0 ; les deux écrans rendent le même bloc de totaux (mêmes
  valeurs, même libellé de devise) ; tests de rendu des deux écrans verts. (T2 — M, sonnet) (@lane:
  frontend/ventes)

- [x] VX140 — **DevisList : 14 boutons deviennent 4 + un menu, la cellule Référence respire.**
  Deux défauts jumeaux de la liste la plus dense : (a) jusqu'à 14 boutons d'action de poids
  identique par ligne brouillon (L1428-1707) alors que sa liste sœur FactureList a DÉJÀ résolu le
  problème avec un `DropdownMenu` Actions (L1140-1181) ; (b) la cellule Référence empile jusqu'à 7
  éléments hétérogènes (L1240-1331) en colonne verticale de 6-8 lignes. Fix : 3-4 actions primaires
  visibles selon statut + menu « Plus d'actions » (même primitive que FactureList) ; cellule à 2
  niveaux — ligne 1 référence+badges de version en `text-sm` gras, ligne 2 métadonnées en `text-xs
  muted` séparées par ` · `, chips de documents liés dans une info-bulle au survol. Files :
  `pages/ventes/DevisList.jsx` (L1240-1331, L1428-1707). DoD : ≤ 5 boutons visibles par ligne +
  menu ; un devis à historique complet tient sur 2 lignes visuelles (snapshot) ; e2e clic
  Éditer/Envoyer/PDF verts avec les mêmes sélecteurs `ap-*`. (T2 — M/L, sonnet) (@lane:
  frontend/ventes)

- [ ] VX141 — **`DocumentStageTrack` : le statut devient un parcours.** `StatusPill` est un fait (@lane: frontend/ventes)
  isolé (point + badge) ; rien dans DevisList/FactureList ne visualise la CHAÎNE
  brouillon→envoyé→accepté→BC→facturé→chantier — un devis accepté sans BC n'est signalé qu'en
  texte. Fix : petit composant `<DocumentStageTrack current stages>` — piste horizontale de 5-6
  puces reliées, franchies cochées, courante remplie, bloquée en rouge — posé dans la cellule
  Statut de DevisList à côté du StatusPill existant. Strictement la couche statuts DOCUMENT (règle
  #4) ; jamais les stages STAGES.py (règle #2) — les deux couches ne se mélangent pas. Files :
  `ui/DocumentStageTrack.jsx` (nouveau), `pages/ventes/DevisList.jsx` (L1375-1425). DoD : devis
  accepté avec BC annulé → point « BC » rouge sur la piste ; test de rendu par statut ; aucune clé
  de stage CRM importée. (T2 — M, sonnet) (@lane: frontend/ventes)

- [x] VX142 — **FactureList & cousins : toolbar rangée, action recommandée trouvable, primitives
  cohérentes.** Quatre finitions du même sous-module : (a) la toolbar FactureList aligne 8
  contrôles dont 4 variantes d'export à plat, et « Journal comptable » passe par un
  `window.prompt()` texte libre (L625-629) — un menu « Exporter » (primitive DropdownMenu déjà dans
  le même fichier) + un petit Dialog mois/trimestre ; (b) `nextBestAction()` (L98-104) est calculé
  mais rendu seulement par `variant=default` sur des boutons à position mouvante — lui réserver le
  PREMIER slot de la rangée avec icône + halo tokenisé, ordre stable ; (c) `RelancesPage.jsx`
  L217-227 contient le SEUL `<select>` HTML natif de tout `pages/ventes/` → composant `Select` ;
  (d) `FactureKanbanBoard.jsx` L47 répète le StatusPill sur chaque carte d'une colonne qui EST le
  statut → remplacer par une info utile (échéance ou montant dû). Files :
  `pages/ventes/FactureList.jsx` (L596-667, L1084-1182), `pages/ventes/RelancesPage.jsx`,
  `pages/ventes/FactureKanbanBoard.jsx`. DoD : toolbar à 5 groupes ; plus de `window.prompt` ;
  l'action recommandée est toujours en position 1 avec style distinct (test par statut) ; 0 select
  natif dans le dossier ; carte kanban sans statut redondant (snapshot). (T2 — M, sonnet) (@lane:
  frontend/ventes)

**Note d'exécution (annexe de VX75, jamais une tâche séparée — grand-verdict §d, S23) :** en plus de
son propre périmètre, VX75 doit aussi couvrir ces sites de niveau CELLULE, invisibles aux audits
d'écran : sous-ligne `Facturé {d.solde.facture} / Payé … / Restant … MAD` (`DevisList.jsx:1371`)
rendue en montants BRUTS ; colonne prix des produits archivés (`StockList.jsx:846-848`, `12500.00
DH` — point décimal anglais, zéro séparateur) ; 31 appels directs `toLocaleDateString` qui
contournent `formatDate` sur les écrans ventes/stock ; `fmtNum2` local (`StockList.jsx:49`) qui
duplique `formatNumber` ; la référence `DEV-202607-0012` (lue à voix haute au client) sans
`tabular-nums`/slashed-zero (`DevisList.jsx:1241`, `FactureList` idem) alors que `.tabular-nums`
inclut déjà `slashed-zero` (`tokens.css:296-299`). Files à ajouter au Done= de VX75 :
`pages/ventes/DevisList.jsx` (1241, 1283, 1315-1327, 1353-1394, 1371, 1734),
`pages/ventes/FactureList.jsx` (722, 742, 1026, 1047), `pages/stock/StockList.jsx` (49, 515, 843,
846-848). [DECISION] option non retenue par défaut : police mono auto-hébergée (~15KB woff2
subset) pour les identifiants (`--font-mono`) — à soumettre au fondateur avant tout build.

**Sous-groupe VXD-H — CRM : l'écran le plus fréquenté**

- [x] VX143 — **LeadForm refondu : un seul langage de formulaire dans le module CRM. @after
  VX89.** Le plus gros formulaire du repo (1297 l., 9-11 sections) redéfinit ses propres
  `Sec`/`Txt`/`Sel` locaux (L74-118) sur des classes hex-brutes, quand `ClientForm.jsx:244-497` — à
  un clic — compose proprement `FormSection`/`FormField` (a11y `aria-invalid`/`aria-describedby`
  automatique). S'y ajoutent : sections sans AUCUNE frontière visuelle, distinguées par la seule
  emoji 👤📈💡 (`.form-section` = flex nu, `index.css:1159-1163`) ; rail de navigation gauche en hex
  figés `#dbeafe/#1d4ed8` (`index.css:1002-1006`), sans barre d'accent, sans écho des icônes de
  section, sans indicateur de contenu (« Doublons » n'affiche jamais son compte) ; et le bouton
  « Concevoir la toiture (3D) » dupliqué verbatim aux L685-691 ET L994-1001. Fix : migration
  `Sec/Txt/Sel → FormSection/FormField/Input/Select` (pattern démontré par ClientForm, présentation
  pure — scroll-spy `data-nav-id` et verrouillages métier intacts) ; traitement de carte sur
  `.form-section` + icônes lucide au lieu d'emoji ; rail tokenisé `border-left: 3px solid
  var(--primary)` + même icône que la section + badges de contenu ; suppression du doublon 3D.
  Files : `pages/crm/LeadForm.jsx` (L74-118 + ~60 usages + L685-691/994-1001 + rail L733-741),
  `index.css` (`.form-section*`, `.lead-nav`). DoD : `grep "Txt fields=" LeadForm.jsx` = 0 ; chaque
  section a une séparation visible (preview_inspect) ; grep `#dbeafe|#1d4ed8` = 0 ; le bouton 3D
  apparaît une fois quel que soit le scroll ; `LeadForm.test.jsx` vert. (T2 — L, sonnet) (@lane:
  frontend/crm)

- [x] VX144 — **Hiérarchie de lecture des cartes et vues CRM : montrer moins pour dire plus.
  @coord VX89/VX45/VX51.** Cinq défauts « tout est montré, rien n'est priorisé » : (a) `LeadCard`
  empile jusqu'à 9 modules/6 badges simultanés sur 272px — fusionner les 3 badges de statut
  (perdu/expiré/inactif) en UN emplacement par priorité, reléguer le secondaire au survol (le
  pattern « +N autres » existe déjà dans `CalendarView.jsx:237-244`, jamais appliqué à la carte) ;
  (b) `ListView` rend 12-13 colonnes au poids identique — modificateur `.lv-col-secondary` (muted,
  non gras) sur Score/Canal/Ville/Tags ; (c) la cellule Client de `ClientList` (L157-168) wrap
  nom+pastille+badge ICE sans ordre garanti à 200px — empilement 2 lignes déterministe ; (d) les
  « leads sans date » sont présentés en note de bas de page neutre (`CalendarView.jsx:261-283`) —
  accent `--warning` + icône ; (e) `ChartsView` rend 4 graphiques au poids strictement égal —
  l'entonnoir par étape passe en pleine largeur. **Rogné (grand-verdict) :** retirer la fusion des
  badges LeadCard en une pilule prioritaire (déjà VX24) ; réduire la démotion des colonnes
  secondaires ListView (recoupe déjà VX7 calm-color) — survivent (c), (d), (e) intégralement + (a)
  et (b) réduits à leur delta non couvert. Files : `pages/crm/leads/views/LeadCard.jsx` (L113-137),
  `pages/crm/leads/views/ListView.jsx`, `pages/crm/ClientList.jsx` (L157-168),
  `pages/crm/leads/views/CalendarView.jsx` (L261-266), `pages/crm/leads/views/ChartsView.jsx`
  (L139-286), `index.css` (`.kb-badge-*`, `.lv-col-secondary`, `.cal-undated-label`,
  `.ch-card-wide`). DoD : fixture triple-drapeau → exactement 1 badge (`querySelectorAll` === 1) ;
  couleur calculée des colonnes secondaires plus claire ; à 200px le badge passe sous le nom
  (bounding box) ; `.cal-undated-label` porte `var(--warning)` ; la carte entonnoir est plus large
  que les 3 autres en desktop, empilée en mobile. (T2 — M, sonnet) (@lane: frontend/crm — @after
  VX89)

- [x] VX145 — **Barres d'action CRM : groupes, risque perçu, désencombrement. @after VX89.** Trois
  toolbars du même module sans hiérarchie : (a) `BulkActionBar` leads rend 11-12 boutons
  identiques — grouper en 3 clusters séparés (éditions de champ / cycle de vie / export+destructif)
  par `border-left` + gap ; **rogné (grand-verdict) :** le regroupement en clusters de
  BulkActionBar recoupe déjà VX20 — ne pas refaire ce point isolément, seuls (b) et (c) survivent.
  (b) DONE — l'en-tête `LeadsPage` montrait 6 actions de même poids pour des fréquences très
  différentes ; Doublons/Importer/Exporter démotés dans un menu « ⋯ » (`DropdownMenu`, même pattern
  que `ListView.jsx`), l'en-tête ne garde que « + Nouveau lead », « ⚡ Express », le bouton « ⭐
  Enregistrer cette vue » et le ViewSwitcher, séparés par `.lp-header-sep` qui isole le ViewSwitcher
  comme cluster de mode. (c) DONE — le bloc « vues enregistrées » était copié-collé entre
  `ClientList.jsx` et `LeadsPage.jsx` et occupait une rangée pleine largeur même vide ; extrait en
  `components/SavedViewsBar.jsx` (chips, rend `null` si `savedViews.length === 0` → 0 rangée dédiée)
  + `SaveViewButton` (déclencheur, placé par chaque écran dans SA rangée déjà existante — en-tête
  pour LeadsPage, rangée Segmented pour ClientList — jamais dans une rangée à lui seul) ; le hook
  `useSavedViews` client reste inchangé dans chaque écran (formes différentes : filters+view vs
  typeFilter). Files : `pages/crm/leads/LeadsPage.jsx`, `pages/crm/ClientList.jsx`,
  `components/SavedViewsBar.jsx` (nouveau), `components/SavedViewsBar.test.mjs` (nouveau),
  `index.css`. DoD : en-tête = 3 contrôles + 1 menu ⋯ dont chaque action reste déclenchable (test de
  source `node --test` — pas de RTL installé dans ce lane, cf. convention `MesEquipesCard.test.mjs`) ;
  0 rangée dédiée quand `savedViews.length === 0`. (T2 — M, sonnet) (@lane: frontend/crm — @after VX89)

- [ ] VX146 — **`/calendrier` rejoint le design system : un seul calendrier mensuel dans l'app.** (@lane: frontend/crm)
  `pages/CalendarPage.jsx` (292 l., l'agenda global qui agrège poses/interventions/maintenance/
  activités) est construit à 100 % en `style={{}}` avec hex bruts (`#0d1b3e`, `#e2e8f0`,
  `#dc2626`…) et n'importe AUCUN composant `ui/` — alors qu'une grille mensuelle tokenisée existe
  littéralement dans le même repo (`.cal-grid/.cal-cell/.cal-weekday`, `index.css:3845-3891`,
  consommée par `leads/views/CalendarView.jsx`) : deux calendriers, un poli, un brut. Fix : porter
  le balisage sur le vocabulaire `.cal-*` existant (l'étendre pour les 5 types d'événements +
  légende + panneau d'abonnement), les hex de `TYPES` (L11-17) deviennent des classes par type
  analogues à `STAGE_COLORS`. Files : `pages/CalendarPage.jsx` (entier), `index.css` (extension du
  bloc `.cal-*`). DoD : grep hex littéral dans le fichier = 0 hors constantes mappées ; rendu
  visuel équivalent (preview_screenshot avant/après) ; dark mode correct. (T2 — M, sonnet) (@lane:
  frontend/crm)

- [ ] VX147 — **LeadsPage et ses 4 vues parlent enfin le même langage d'état.** L'écran le plus (@lane: frontend/crm)
  fréquenté du CRM rend son chargement/erreur en `<p className="page-loading/page-error">` brut,
  stylé en hex codés en dur (`index.css:727-739`) — hors de tout le système d'états ; et ses 4 vues
  traitent « 0 lead » de 4 façons (Kanban/List/Carte en texte brut, ChartsView seule en
  `EmptyState` correct). Fix : remplacer L313-325 par `StateBlock`/`EmptyState`+`Skeleton`,
  supprimer `.page-loading/.page-error` d'index.css, unifier les 3 vues texte-brut sur `EmptyState`
  (calqué sur ChartsView:105-118, la seule déjà correcte). Files :
  `pages/crm/leads/LeadsPage.jsx` (L313-325), `pages/crm/leads/views/KanbanView.jsx` (L147),
  `ListView.jsx` (L484), `CarteView.jsx` (L99), `index.css` (L727-739). DoD : `grep
  page-loading|page-error src/` = 0 ; les 4 vues montent le même composant pour `leads=[]` (test
  rôle status/alert) ; sélecteurs e2e intacts. (T2 — M, sonnet) (@lane: frontend/crm)

**Sous-groupe VXD-D — Ops & insight : les nombres sont le héros**

- [ ] VX148 — **Le kit `ui/charts` réellement adopté : fin des 3 thèmes recopiés et des rapports (@lane: frontend/orphans)
  sans graphique.** Le kit maison (AreaSansAxe/BarArrondie/KpiSpark/ChartTooltip/ChartEmpty, thémé,
  testé, reduced-motion géré) est contourné par les écrans d'insight les plus importants :
  `Reporting.jsx` (L7-10, 39-49, radius codé `[0,6,6,0]` L384, KPI sans sparkline), `Rapports.jsx`
  et `Journal.jsx` redéclarent chacun leur objet tooltip quasi identique — 3 copies du même
  dictionnaire de style ; `PilotageStock.jsx` (L189-284) et 5 des 6 rapports de `Rapports.jsx`
  rendent des données comparatives en `<table>` pures ; `ProductionPage.jsx` — l'écran le plus
  consulté du dossier monitoring — n'a AUCUN graphique quand ses 4 voisins directs en ont un ; et
  `ChartEmpty` a 0 site d'appel dans tout `pages/**`. Fix : migrer les 3 fichiers sur le kit
  (supprimer les tooltips locaux, `BAR_RADIUS_H` partout), ajouter un `BarArrondie`/`AreaSansAxe`
  AU-DESSUS des tables de PilotageStock/Rapports (la table garde le détail), une courbe de
  tendance kWh sur ProductionPage (pattern `OmAnalyticsPage.jsx:151-162`), brancher `ChartEmpty`
  sur les cartes de graphes vides de Dashboard/CommercialDashboard/Cohorts. La palette
  catégorielle elle-même reste VX41 — ce seed APPLIQUE le kit existant. Files : `pages/Reporting.jsx`,
  `pages/Rapports.jsx`, `pages/Journal.jsx`, `pages/stock/PilotageStock.jsx`,
  `pages/monitoring/ProductionPage.jsx`, `pages/Dashboard.jsx`,
  `pages/reporting/CommercialDashboard.jsx`. DoD : `grep "from 'recharts'"` sur les 3 fichiers ne
  montre plus que les formes non couvertes ; une seule définition de tooltip dans `pages/` ;
  chaque section citée affiche graphe + table ; `ChartEmpty` rendu quand dataset vide (tests). (T2
  — L, sonnet) (@lane: frontend/orphans)

- [x] VX149 — **Un seul accent de statut : `StatusAccentCard` + le terrain + le micro-pack ops.**
  La « carte à accent coloré par statut » est réinventée en parallèle :
  `InterventionsPage.jsx:68-145` (`.kb-*/.kc-*`, `--kb-accent` — le bon craft de référence) vs la
  `CalendarView` inline d'`InstallationsPage.jsx:58-217` (`.cal-*`, `style={{background: dot}}`) —
  extraire `ui/StatusAccentCard.jsx` consommé par les deux ; « Ma journée » technicien
  (`MaJourneePage.jsx:77-113`) reste une liste plate sans différenciation par `type_intervention` —
  poser le même accent + `text-amber-600` → `text-warning`. Micro-pack de dédup dans la même
  passe : `FournisseurFiche360.jsx:43-62` redéfinit Card/Stat localement → imports `ui/` ;
  `ChantierPhotos.jsx:141-190` vignettes `size-16` fixes → bascule densité compact/confortable en
  Segmented ; `BulkProductBar.jsx:27-37` réinvente un bouton-onglet sur fond sombre → variant
  `Segmented` partagé ; `ChantierGateTimeline.jsx:36-38` double mécanisme classe+style inline
  redondant → suppression. Files : `ui/StatusAccentCard.jsx` (nouveau),
  `pages/interventions/InterventionsPage.jsx`, `pages/installations/InstallationsPage.jsx`,
  `pages/interventions/MaJourneePage.jsx`, `pages/stock/FournisseurFiche360.jsx`,
  `pages/installations/ChantierPhotos.jsx`, `pages/stock/BulkProductBar.jsx`,
  `pages/installations/ChantierGateTimeline.jsx`. DoD : les deux écrans kanban/calendrier
  consomment le même composant (tests non régressés) ; chaque ligne de Ma journée porte un accent
  par type ; fiche 360 sur primitives partagées ; 40+ photos lisibles en densité compacte ;
  `data-testid="ch6-stage"` intact. (T2 — M/L, sonnet) (@lane: frontend/orphans)

**Sous-groupe VXD-J — Fondation & âme de marque**

- [ ] VX150 — **Le login re-signé : la première impression cesse de contredire le système.** (@lane: frontend/brand — delta sur VX34)
  `Login.jsx` est une île : 100 % `style={{}}` inline avec les hex d'une ANCIENNE marque
  (`#1863DC`/`#F5C100`), fond animé « TAQINOR » en `Arial Black` (L46) au lieu de la police de
  marque, œil mot-de-passe et alerte en émojis bruts `👁️/🙈/⚠️` (L240, L292), et un
  `requestAnimationFrame` PERMANENT (`BouncingBackground` L71-85) sans garde
  `prefers-reduced-motion` ni throttle `visibilitychange`. **Rogné (grand-verdict) :** VX34 possède
  déjà la MISE EN PAGE cockpit du login (mêmes hex, mêmes emojis→lucide, même garde reduced-motion
  sur BouncingBackground) — ne conserver que le delta non couvert : wordmark `Arial Black` → police
  de marque, et pause `visibilitychange` du rAF (2 lignes ajoutées au Done= de VX34, pas un
  chantier séparé). Files : `pages/Login.jsx` uniquement. DoD : le wordmark utilise la police de
  marque ; le rAF de fond se met en pause hors onglet actif (test mock `visibilitychange`).
  (T3 — S, sonnet) (@lane: frontend/brand — delta sur VX34)

- [ ] VX151 — **Paramètres : 24 onglets deviennent une surface de réglages navigable.** `TABS` (@lane: frontend/brand)
  (`peConstants.js` L27-50) + 3 onglets locaux = 24 onglets plats dans UN `<TabsList
  overflow-x-auto>` (L801) — ~9-10 visibles à 1280px, scroll horizontal à l'aveugle sans
  fade/chevron ; et le bouton « Enregistrer » n'existe que sur 4/24 onglets, chaque section ayant
  SA convention de persistance sans aucune affordance préalable. Fix : champ `group` par entrée de
  TABS (4-5 méta-catégories : Identité & documents / Vente & CRM / Terrain & stock / Sécurité &
  système / Avancé) rendues en navigation à 2 niveaux, CHAQUE clé `tab` existante conservée
  (routing/tests intacts) ; badge/ligne contextuelle par section (« Modifications enregistrées
  immédiatement » vs bouton visible). Files : `pages/parametres/ParametresEntreprise.jsx`
  (L799-808, L829-872), `pages/parametres/peConstants.js`. DoD : les 24 clés restent accessibles
  (`tab===…` inchangé) ; hiérarchie 2 niveaux visible ; chaque onglet annonce son modèle de
  sauvegarde avant édition ; recherche fonctionnelle. (T2 — M, sonnet) (@lane: frontend/brand)

- [x] VX152 — **Fin des moteurs de table parallèles : GED, Admin, ClientDetail, OCR
  convergent.** Quatre modules contiennent chacun DEUX systèmes de table à deux clics l'un de
  l'autre : le point d'entrée GED (`GedNavigator.jsx:391-470`, `GedSearch.jsx:147-181`) rend en
  `<table class="data-table">` hex-legacy pendant que les écrans avancés du MÊME module
  (Approbation/Corbeille) utilisent `ListShell` moderne ; `RolesManagement.jsx:489` est une table
  HTML brute (constante `th` répétée 16×) pendant que `UsersManagement.jsx:438` — même dossier
  admin — a le DataTable complet ; `ClientDetailPanel.jsx:19-55` fabrique un TROISIÈME moteur
  `DocTable` à la main pour Devis/Factures/Chantiers ; `OcrUpload.jsx` L222-235/248-267 duplique
  deux `<table>` Tailwind répétitives. Fix : porter chaque surface sur le moteur déjà utilisé par
  son voisin direct (ListShell pour GED, DataTable pour les rôles — liste seulement, la grille de
  permissions reste —, `Table` partagée pour ClientDetail, `KeyValueTable` partagé pour OCR).
  Files : `features/ged/GedNavigator.jsx`, `features/ged/GedSearch.jsx`,
  `pages/admin/RolesManagement.jsx` (L460-582), `pages/crm/ClientDetailPanel.jsx`,
  `pages/ia/OcrUpload.jsx`. DoD : grep `data-table` = 0 sur les 2 fichiers GED ; recherche/tri
  disponibles sur les rôles, dialogue de réassignation intact ; `grep "<table"
  ClientDetailPanel.jsx` = 0 ; un seul point de rendu FIELD_LABELS dans OcrUpload ; tests existants
  verts. (T2 — L, sonnet) (@lane: frontend/brand)

- [ ] VX153 — **GED/IA micro-pack : navigation réunifiée, tailles sémantiques, temps lisible.** (@lane: frontend/brand)
  Trois finitions du même périmètre : (a) « Documents » et « GESTION DOCUMENTAIRE » sont deux
  sections de menu pour UN espace conceptuel — un contournement technique de collision de clé
  assumé en commentaire (`module.config.jsx:36`) — fusionner/adjacenter les deux groupes sans
  toucher au routing `/ged/*` ; (b) `GedNavigator/GedSearch` utilisent `text-[13px]`/`text-[11px]`
  arbitraires au lieu de `text-sm`/`text-xs` ; (c) l'onglet Historique d'`AgentActions.jsx`
  (L118-198) liste des logs chronologiques en cartes plates — grouper par jour
  (Aujourd'hui/Hier/date), `confirmed_at` est déjà servi. Files : `features/ged/module.config.jsx`,
  `features/ged/GedNavigator.jsx`, `features/ged/GedSearch.jsx`, `pages/ia/AgentActions.jsx`. DoD :
  les deux groupes de nav adjacents/fusionnés ; grep `text-\[1[0-9]px\]` = 0 sur les 2 fichiers ;
  logs groupés par jour (`AgentActions.historique.test.jsx` vert). (T2 — S/M, haiku ; sonnet pour
  la décision de nav) (@lane: frontend/brand)

- [ ] VX154 — **`TaqinorMark` + `SolarLoader` : le mot-symbole soleil-éclair porté dans l'app, (@lane: frontend/brand)
  chaque attente signée.** Le glyphe le plus distinctif de la marque — le soleil rayonnant à
  éclair azur de `public/favicon.svg` — n'existe dans l'app React NULLE PART (grep = 0) : le header
  porte un `<Zap>` lucide générique sur carré jaune (`Header.jsx:60-62`), et chaque attente est
  anonyme (Spinner cercle gris, RouteFallback silhouette). Fix : composant `<TaqinorMark>` SVG
  inline tokenisé (rayons `var(--primary)`, éclair `var(--info)`, props size/animate) remplaçant
  le Zap du header ; `<SolarLoader>` — le mark dont les rayons s'illuminent en séquence, CSS pur,
  statique sous reduced-motion — posé sur `RouteFallback` et les chargements plein-écran (JAMAIS
  les spinners inline de bouton) ; shimmer skeleton légèrement teinté brass (@coord VX132). Files :
  `ui/TaqinorMark.jsx` (nouveau), `ui/SolarLoader.jsx` (nouveau), `components/layout/Header.jsx`,
  `components/RouteFallback.jsx`, `index.css` (keyframe `sun-rise`). DoD : header = soleil-éclair
  (snapshot, aria/data-* intacts) ; transition de route = petit soleil animé, figé sous
  reduced-motion ; rendu correct clair/sombre via tokens. (T3 — M, sonnet) (@lane: frontend/brand)

- [ ] VX155 — **La gradation émotionnelle du funnel : signé célébré, envoyé/payé reconnus.** (@lane: frontend/brand — @with VX40)
  Le moment le plus important de tout l'ERP — un devis solaire SIGNÉ — est muet :
  `SigneDialog.jsx:190-213` appelle `accepterDevis` puis les 2 appelants (`LeadForm.jsx:1274`,
  `LeadsPage.jsx:485`) ferment la modale + refetch, zéro reconnaissance pour une affaire de 150 000
  MAD ; et les jalons intermédiaires (devis envoyé, facture payée) sont des `toast.success`
  identiques à « ligne supprimée ». **Fusionné (grand-verdict) :** ce seed enrichit directement le
  Done= de **VX40** (qui câble déjà SigneDialog/DevisList) — ne pas créer de tâche séparée pour la
  carte de victoire, l'ajouter au périmètre VX40. Fix (delta à ajouter au Done= de VX40) :
  `<DealSignedCelebration>` — burst de confetti canvas maison (brass+azur, 0 dépendance), carte de
  victoire avec montant TTC + kWc (déjà calculés dans `SigneDialog` `optionsDetail` L59) + « ≈ X t
  CO₂ évitées/an » dérivée, TaqinorMark qui pulse ; dégrade en toast riche sous reduced-motion ;
  câblé sur les DEUX chemins d'appel. Survit comme tâche autonome : `toastMilestone` dans
  `lib/toast.js` — un cran au-dessus du succès plat (icône soleil + description réf/client/montant)
  posé sur devis envoyé (event `devis_sent`) et facture payée (`PaiementsPage`). Files :
  `ui/DealSignedCelebration.jsx` (nouveau, ≤120 l., @coord VX40), `pages/crm/leads/SigneDialog.jsx`,
  `pages/crm/leads/LeadsPage.jsx`, `pages/crm/LeadForm.jsx`, `lib/toast.js`,
  `pages/ventes/DevisList.jsx:476`, `pages/ventes/PaiementsPage.jsx`. DoD : accepter → carte de
  victoire avec montant + kWc réels (test mock accepterDevis) ; reduced-motion → carte sans
  mouvement ; devis envoyé/facture payée → toast visuellement distinct du toast générique (test du
  helper). (T3 — M, sonnet) (@lane: frontend/brand — @with VX40)

- [ ] VX156 — **Une voix avec un point de vue + le moment d'accueil.** La microcopie est correcte (@lane: frontend/brand)
  mais interchangeable avec n'importe quel SaaS — aucun ton « fier du solaire », aucun vocabulaire
  métier aux moments émotionnels ; et la première connexion atterrit sur le Dashboard brut (les
  coachmarks FG16 sont un tour FONCTIONNEL, pas un accueil). Fix : (a) module `lib/voice.js` (~20
  chaînes FR, vouvoiement, vocabulaire kWc/chantier/mise en service) + guide d'une page, posé sur
  les 5-6 moments à forte charge : première connexion, file vide (« Tout est à jour — belle journée
  pour poser des panneaux. »), devis envoyé, affaire signée, chantier terminé, erreur réseau — PAS
  un rewrite massif (VX45 possède la microcopie générale) ; (b) `<WelcomeMoment>` one-shot à la
  première connexion : TaqinorMark animé, phrase de mission, bouton « Commencer », flag
  localStorage défensif (@coord `safeStorage`, VXD-B), skippable, une seule fois. Files :
  `lib/voice.js` (nouveau), `components/WelcomeMoment.jsx` (nouveau), `main.jsx`, poses sur ~6
  écrans. DoD : les 6 moments portent une chaîne voice.js (test aucune chaîne vide) ; accueil
  affiché une fois puis plus jamais (test du flag) ; revue de ton « ça sonne Taqinor ». (T3 — M,
  sonnet) (@lane: frontend/brand)

- [x] VX157 — **Le langage d'impact : icônes métier unifiées + la fierté ambiante du parc.**
  Aucun vocabulaire d'icône partagé pour les grandeurs métier (kWc, production, CO₂ évité,
  économies) — chaque écran choisit la sienne (`Co2Page` importe Leaf/Sprout/Zap ad hoc) ; et
  l'impact cumulé du parc (déjà servi par `monitoringApi.getCo2Fleet()`) est enterré dans un
  sous-écran monitoring. Fix : map `ui/metricIcons.js` (soleil=production, éclair=kWc,
  feuille=CO₂, portefeuille=économies, HardHat=chantier) + variante `Stat tone="impact"` à accent
  brass pour les grandeurs d'impact positif ; « pastille d'impact » discrète en pied de Sidebar
  (« X MWh · Y t CO₂ évitées » cumulés), chargée paresseusement, MASQUÉE si aucune donnée — jamais
  un « 0 » inventé (scoping company côté serveur ; [BACKEND] additif si l'endpoint manque). Files :
  `ui/metricIcons.js` (nouveau), `ui/Stat.jsx`, `components/layout/Sidebar.jsx`, poses
  Co2Page/Dashboard/monitoring. DoD : les KPI kWc/production/CO₂ partagent les mêmes icônes partout
  (test de la map) ; pastille = vraies valeurs du parc, absente si vide (test conditionnel). (T3 —
  M, sonnet) (@lane: frontend/brand)

- [ ] VX158 — **Confiance et clarté : les valeurs suggérées se déclarent, le jargon fiscal se (@lane: frontend/brand — @after VX93)
  traduit.** Deux leçons de produits finis (Ramp, Pennylane) : (a) VX93 pré-remplira
  owner/ville/TVA/mode de paiement depuis localStorage sans qu'AUCUN signal ne distingue une
  SUPPOSITION d'une donnée confirmée — un style réutilisable discret (contour pointillé + micro-
  libellé « suggéré » au focus, retiré dès modification) posé sur les 4 champs VX93 — jamais un
  « confidence score » générique (à livrer AVEC ou juste après VX93) ; (b)
  `FiscalitePage.jsx`/`EtatsPage.jsx` exposent « FEC », « liasse », « IS » sans un mot d'aide — une
  phrase grise par bouton d'export (« FEC — fichier requis par l'administration fiscale en cas de
  contrôle »), zéro logique. Files : mêmes fichiers que VX93 (LeadForm, ProduitForm,
  DevisGenerator, FactureList) + `features/compta/pages/FiscalitePage.jsx`,
  `features/compta/pages/EtatsPage.jsx`. DoD : champ pré-rempli non touché → indice « suggéré »
  visible, disparaît à la modification (snapshot 1 champ) ; chaque export fiscal porte sa phrase
  d'aide sans clic. (T3 — S, sonnet ; haiku pour le volet fiscal) (@lane: frontend/brand — @after
  VX93)

- [ ] VX159 — **`RelationCounters` : le seul bon réflexe d'Odoo, systématisé. @coord ARC46.** (@lane: frontend/brand)
  Chaque fiche 360 (Lead, Client, Fournisseur, Produit) affiche ses relations à sa façon — aucune
  convention « compteurs cliquables en tête de fiche » (« 3 devis · 1 facture impayée · 2 tickets
  SAV »). Fix : composant `ui/RelationCounters.jsx` posé en tête des 4 fiches, lisant les selectors
  existants par domaine (JAMAIS une nouvelle agrégation cross-app — frontière `selectors.py`
  respectée), clic → liste cible pré-filtrée (`?client=`, même pattern que VX112). Files :
  `ui/RelationCounters.jsx` (nouveau), `pages/crm/ClientDetailPanel.jsx`,
  `pages/stock/FournisseurFiche360.jsx`, `ProduitDetail.jsx`, `pages/crm/LeadForm.jsx`. DoD : les 4
  fiches affichent les mêmes badges cliquables ; clic → liste pré-filtrée (test) ; zéro nouvelle
  route cross-app. [coordonner ARC46 — construisible avant `RecordShell`, migrable dedans ensuite]
  (T3 — M, sonnet) (@lane: frontend/brand)

---

## AXE 2 — ROBUSTESSE (VX160–VX208, 49 tâches survivantes sur 49 seeds ; 0 tuée, 2 rognées —
SEED-14 re-scopé/SEED-17 rogné, corrections déjà appliquées dans le texte transcrit ci-dessous)

**Sous-groupe VXD-A — Intégrité des mutations & résilience réseau (le niveau sous la
présentation d'erreur)**

*Note : VX117 (au sommet de ce document) EST la transcription de SEED-01 de cette section — ne
pas la dupliquer ici, la numérotation continue directement à SEED-02.*

- [x] VX160 — **Outbox terrain : une op rejetée par le serveur ne disparaît plus en silence.**
  *(Transcription intégrale de SEED-02 — le résumé de tête figure déjà en VX119 au sommet du
  document comme bug candidat-build ; cette entrée porte le detail complet pour la lane VXD-A.)*
  `offline/outbox.js:117-122` purge un batch 100 % en statut `error` sans jamais lire le champ
  `.error` que le backend renvoie pourtant par op (`field_sync.py:263/266/293/313`) ; l'unique
  affichage (`OfflineSyncIndicator.jsx:14-23`) rend « Connexion rétablie. » dans les deux cas — une
  SIGNATURE CLIENT capturée hors-ligne (`FIELD_OPS.SIGNER_CLIENT`) peut s'évaporer sans trace. Fix :
  trois classes de résultat dans `flush()` (done retirés / `error` GARDÉS en file avec message
  serveur + compteur de tentatives / échec réseau déjà géré), méthode `fieldOutbox.failed()`,
  indicateur à 3 états (badge rouge « N action(s) en échec — voir détail », abandon par op
  UNIQUEMENT explicite). Le message serveur affiché EST le signal de conflit — pas de moteur CRDT.
  Files : `offline/outbox.js`, `offline/useFieldOutbox.js`, `offline/OfflineSyncIndicator.jsx`.
  DoD : batch mock 100 % `error` → ops gardées + message par op accessible ; badge distinct rendu ;
  non-régression `applied`/`replayed`. (T1 — M, sonnet) (@lane: frontend/data)

- [ ] VX161 — **`refreshCoordinator` : un seul refresh 401 partagé entre `axios.js` et (@lane: frontend/data)
  `iaApi.js`.** `axios.js:29-53` pose `_retry` PAR REQUÊTE : N requêtes 401 simultanées = N `POST
  /token/refresh/` parallèles (stampede) ; `iaApi.js:28-53` duplique en plus son PROPRE
  intercepteur — une page métier + le Copilote au même instant lancent deux refresh concurrents
  contre le même refresh_token ; en rotation à usage unique, le second échoue →
  `emitSessionExpired()` intempestif sur une session valide. Fix : `api/refreshCoordinator.js` —
  promesse de refresh UNIQUE partagée (le premier appelant POST, tout suivant `await` la MÊME
  promesse, reset en `finally`), consommée par les deux intercepteurs. Files :
  `api/refreshCoordinator.js` (nouveau), `api/axios.js`, `api/iaApi.js`. DoD : 5 requêtes 401
  simultanées (mix des deux instances) → exactement UN POST refresh, les 5 rejouées après. (T1 —
  S, sonnet) (@lane: frontend/data)

- [ ] VX162 — **`BroadcastChannel` de session : le logout se propage à tous les onglets.** (@lane: frontend/data)
  `authSlice.js:17-28` ne notifie que l'onglet courant ; grep cross-tab exhaustif = 1 hit
  cosmétique (`GlobalSearch.jsx:144`). Sur un poste partagé (accueil/atelier), l'onglet B continue
  de MUTER des données au nom d'un utilisateur délibérément déconnecté jusqu'à son premier 401
  tardif. Fix : `BroadcastChannel('taqinor-session')` dans `providers/session-bridge.js` —
  `logoutUser.fulfilled` publie, chaque onglet s'abonne dans `SessionProvider` et dispatch le
  logout local + `/login` sans attendre un échec réseau ; feature-detect no-op. Files :
  `providers/session-bridge.js`, `authSlice.js`, `providers/SessionProvider.jsx`. DoD : logout
  onglet A → onglet B simulé passe `isAuthenticated:false` sans appel réseau. (T2 — S, sonnet)
  (@lane: frontend/data)

- [ ] VX163 — **Infrastructure thunk : annulation `{signal}` + dé-duplication en vol des 4 thunks (@lane: frontend/data — @with/after VX54)
  chauds.** 79 `createAsyncThunk` identiques, ZÉRO `{signal}` (grep) — un démontage laisse la
  requête vivre et réduire un écran disparu ; et zéro dédup : deux montages simultanés = deux GET
  identiques. Fix (0 dép — le « RTK Query sans RTK Query ») : `lib/thunkHelpers.js` —
  `createCancellableThunk(type, apiCall)` injecte `thunkAPI.signal` dans axios et normalise
  `CanceledError` (jamais toasté) ; + une `Map<clé, Promise>` in-flight (~15 lignes) sur
  `fetchProduits`/`fetchDevis`/`fetchLeads`/`fetchFactures` — les MÊMES 4 slices que VX54 touche
  (séquencer `@with/after VX54`). Files : `lib/thunkHelpers.js` (nouveau), les 4 slices
  (stock/ventes/crm). DoD : dispatch double avant résolution → 1 seul appel réseau, 2 promesses
  même payload ; démontage → `meta.aborted === true`, 0 toast. (T2 — M, sonnet) (@lane:
  frontend/data — @with/after VX54)

- [ ] VX164 — **Plancher anti-course : séquence (messaging), fraîcheur (réducteurs `update*`), (@lane: frontend/data)
  verrou `InlineEdit`.** (a) `messagingSlice.js:200-205` protège le changement de conversation mais
  pas l'ORDRE — le poll 3 s (`useChatPolling.js:51-55`) n'annule pas le tick précédent : un tick
  N-1 lent écrase la page plus fraîche (un message reçu DISPARAÎT jusqu'au tick suivant). (b)
  `crmSlice.js:159-162`, `ventesSlice.js:300-307`, `stockSlice.js:196-199` : remplacement TOTAL au
  `.fulfilled` — deux PATCH rapides du même utilisateur résolus dans l'ordre inverse font régresser
  l'écran. (c) `InlineEdit.jsx:30-48` : Enter puis blur = deux `onSave` (le verrou `saving` ne
  pilote que l'AFFICHAGE). Fix : compteur monotone par ressource appliqué au `fulfilled` (no-op si
  obsolète — même mécanique pour a et b) ; `committingRef` vérifié EN TÊTE de `commit()` pour (c).
  Files : `messagingSlice.js`, `useChatPolling.js`, les 3 slices (réducteurs
  `update*/patch*.fulfilled`), `components/InlineEdit.jsx`. DoD : résolutions inversées → l'état
  final contient LES DEUX changements / le payload le plus récent DEMANDÉ ; Enter+blur synchrone →
  `onSave` 1×. (T2 — M, sonnet) (@lane: frontend/data)

- [ ] VX165 — **Chargement par-ressource : le spinner ne ment plus (prérequis silencieux de (@lane: frontend/data)
  VX67).** `ventesSlice.js:288-298/316-321/353-358` (miroirs crm/stock) : UN `state.loading`
  partagé par `fetchDevis`/`fetchBonsCommande`/`fetchFactures` — le premier résolu éteint le
  spinner pendant que les requêtes sœurs chargent encore. Fix : `pendingCount`
  incrémenté/décrémenté par chaque `pending`/settled (une ligne par builder, rétrocompatible avec
  les sélecteurs existants), spinner tant que `> 0`. Files : `ventesSlice.js`, `crmSlice.js`,
  `stockSlice.js`. DoD : `fetchDevis` + `fetchFactures` parallèles, factures résout d'abord →
  `loading` reste `true` (test rouge avant/vert après). (T2 — S, sonnet) (@lane: frontend/data)

**Sous-groupe VXD-B — Formulaires : ne jamais perdre une saisie**

- [ ] VX166 — **Câbler `confirmLeaveIfDirty` chez les 7 adoptants existants + `CrudDialog` (8 (@lane: frontend/forms)
  écrans compta d'un coup).** Les 7 formulaires qui calculent DÉJÀ `dirty` + `useDirtyGuard`
  (`ClientForm.jsx:240`, `ProduitForm.jsx:402`, `DevisForm.jsx:222`, `FactureForm.jsx:263`,
  `InstallationDetail.jsx:725`, `EquipementsPage.jsx:229`, `TicketsPage.jsx:529`) gardent
  `onOpenChange={(o)=>{if(!o) onClose()}}` — Radix ferme sur Escape ET clic-overlay et jette la
  saisie ; `confirmLeaveIfDirty` (`useDirtyGuard.js:27-33`) a 0 appelant dans tout le repo (grep).
  Et `features/compta/components/CrudDialog.jsx:67` (partagé par 8 pages compta) n'a AUCUNE notion
  de dirty. Fix : gater la fermeture par `confirmLeaveIfDirty(dirty)` dans les 7 fichiers + snapshot
  à l'ouverture + garde dans `CrudDialog` (zéro changement d'API pour les 8 appelants). Files : les
  7 fichiers + `CrudDialog.jsx`. DoD : modifier → Escape → `confirm` invoqué (mock) ; annuler →
  modale ouverte, champs intacts ; non-dirty inchangé ; smoke 2 pages compta. (T1 — S/M, sonnet)
  (@lane: frontend/forms)

- [ ] VX167 — **LeadForm : dirty-tracking + garde de fermeture (le modal n°1 — complément direct (@lane: frontend/forms — @with/after VX89)
  de VX89). @with/after VX89.** `LeadForm.jsx:588` (overlay `onClick={onClose}`) et `:639` (bouton
  ✕) : ZÉRO notion de dirty dans tout le fichier (grep) — 15 champs (bien+GPS+relance+tags) perdus
  sur un mis-clic, à 20-40 ouvertures/jour/commercial. VX89 (Escape+autofocus via ResponsiveDialog)
  rendra même la perte PLUS facile : Escape marchera enfin, et fermera sans rien demander. Fix :
  snapshot initial (patron `isDirty` prouvé dans `ProduitForm.jsx:286`) + `useDirtyGuard(dirty)` +
  `confirmLeaveIfDirty` sur ✕/overlay/futur `onOpenChange`. Files : `pages/crm/LeadForm.jsx`. DoD :
  modifier un champ → toute fermeture demande confirmation ; e2e leads verts. (T1 — M, sonnet)
  (@lane: frontend/forms — @with/after VX89)

- [ ] VX168 — **Balayage garde+autoFocus : 13 dialogues flotte/gestion_projet + (@lane: frontend/forms)
  `EmployeDetail`/`Recrutement` + autoFocus top-20.** 9 dialogues `features/flotte/*` (dont
  `PleinDialog` 11 useState, `SignalementDialog` saisie terrain) + 4
  `features/gestion_projet/components/*Dialog.jsx` : 0 dirty-guard (grep) ;
  `features/rh/Recrutement.jsx` (31 useState — 2ᵉ plus long formulaire du repo après
  DevisGenerator) et `EmployeDetail.jsx` (19) : 0 garde ; `autoFocus` ne couvre que 12/93
  fichiers-formulaire. Fix : même recette snapshot+garde posée mécaniquement (1ᵉʳ fichier = patron
  validé, puis répétition), et `autoFocus` posé dans la MÊME passe + sur ~20 formulaires fréquents
  (UsersManagement, RolesManagement, KpiAlertesPage, écrans compta). Files : les 15 fichiers cités +
  ~20 autoFocus. DoD : par fichier — modifier→fermer → confirmation ; ouverture →
  `document.activeElement` = premier champ. (T1 — L, sonnet ; haiku après le patron) (@lane:
  frontend/forms)

- [ ] VX169 — **`useBlocker` : garde de navigation IN-APP des formulaires route-level.** (@lane: frontend/forms)
  `useDirtyGuard` ne couvre que `beforeunload` — un clic sidebar pendant la saisie navigue
  instantanément (pushState, pas un déchargement) ; `useBlocker` de react-router v7
  (`createBrowserRouter` confirmé `router/index.jsx:207`) = 0 usage dans le repo. Fix :
  `hooks/useNavigationGuard.js` fin au-dessus de `useBlocker` (fallback no-op), monté sur
  `ParametresEntreprise`, `EquipementSignalerPage`, `DashboardConfigPage`, `ArticleEditor`,
  `ReclamationEditor` ; dialogue design-system, pas `window.confirm` brut. Files : le hook
  (nouveau) + les 5 écrans. DoD : modifier ParametresEntreprise → clic lien sidebar →
  confirmation ; accepter navigue, annuler reste. (T2 — M, sonnet) (@lane: frontend/forms)

- [ ] VX170 — **`useFormSafety` : LA primitive qui rend le mauvais câblage impossible (incl. (@lane: frontend/forms)
  réparation WebKit du hook + `safeStorage`).** Le repo n'a pas de convention : chaque formulaire
  réinvente son snapshot (`isDirty` / `JSON.stringify` diff / `useMemo` custom) et personne ne
  branche les 3 mécanismes ensemble (tab-close + in-app-close + router) — les 7 « meilleurs
  élèves » n'en branchent que 1 sur 3. Pire : `useDirtyGuard.js:20` n'écoute QUE `beforeunload`,
  quasi muet sur iOS (swipe-back/bascule d'app sautent l'événement ; le fiable WebKit est
  `pagehide`) → toute la pile B est aveugle iPhone. Fix : `ui/useFormSafety.js` — `{dirty,
  guardedClose, snapshot}` composant (a) diff générique, (b) `useDirtyGuard`, (c)
  `confirmLeaveIfDirty` wrappé, (d) flag route-level → VX169 ; réparer le hook sous-jacent avec
  `pagehide` (+ `visibilitychange→hidden`) qui PERSISTE un brouillon défensif — on ne peut pas
  bloquer un pagehide, la bonne UX WebKit = sauver, pas bloquer — via un `lib/safeStorage.js`
  défensif (try/catch + éviction sur `QuotaExceededError`, Safari privé) que VX62/VX46/VX10/NTUX16
  consommeront aussi. Files : `ui/useFormSafety.js` (nouveau), `ui/useDirtyGuard.js`,
  `lib/safeStorage.js` (nouveau), migration d'au moins 3 formulaires (ClientForm, CrudDialog, un
  dialogue flotte). DoD : test du hook isolé ; `pagehide` dirty → persistance appelée ; `setItem`
  en quota plein ne crash pas et évince le plus ancien ; 3 formulaires migrés avec moins de code.
  (T2 — M, sonnet) (@lane: frontend/forms)

- [ ] VX171 — **Vérité des erreurs de champ : serveur → champ (`useServerFieldErrors`) + erreurs (@lane: frontend/forms)
  locales effacées à la frappe.** (a) DRF renvoie `{champ:[msg]}` mais 12 fichiers seulement posent
  `aria-invalid` — tout est écrasé en UN toast opaque ; `FormField` (`ui/Form.jsx:56-77`) est
  correctement câblé et sous-consommé. (b) `ClientForm.jsx:170-180`, `DevisForm.jsx:147/215`,
  `FactureForm.jsx:184/256` : `setErrors` n'est jamais nettoyé au `onChange` — le rouge MENT
  pendant que l'utilisateur corrige, jusqu'au prochain submit. Fix : `hooks/useServerFieldErrors.js`
  (mapping DRF → `errors{champ}` consommé par `FormField error=`) posé sur
  Client/Lead/Devis/Facture/Produit ; dans chaque `set(field, …)`, `delete errors[field]`. Files :
  le hook (nouveau) + les 5 formulaires. DoD : soumettre invalide → LE champ vire rouge avec son
  message (pas un toast anonyme) ; taper dans le champ fautif → l'erreur disparaît avant re-submit ;
  tests des formes DRF (detail / `{champ:[…]}` / array). (T2 — M, sonnet) (@lane: frontend/forms)

**Sous-groupe VXD-C — iOS Safari / WebKit / PWA (la longue traîne au-delà de VX48-53/68)**

- [ ] VX172 — **Exports blob (xlsx/csv/json/png) fiables sur iOS/standalone : routage par geste + (@lane: frontend/ios)
  pending visible + repli PDF réparé. @after VX48/49 — RE-SCOPÉ par le grand-verdict.**
  `downloadBlob.js:2-11` et ~20 call-sites posent `a.download` sur un `blob:` (`ClientList.jsx:138`,
  `LeadsPage.jsx:124/219`, `StockList.jsx:191/669/771`, `ClientRgpdActions.jsx:35`,
  `DocumentsArchive.jsx:89/111`, `PaieDeclarations.jsx:67/578/886`, `Risques.jsx:73`,
  `comptaApi.js:16`, `importApi.js:55/74`…). **Constat corrigé (grand-verdict) :** Safari iOS ≥13
  SUPPORTE `a.download` sur les URL blob — le risque réel est le mode PWA STANDALONE + les vieux
  iOS + une UX de fichier téléchargé invisible (gestionnaire de téléchargements indécouvrable en
  coquille installée), PAS un échec universel. Le repli terminal `pdfBlob.js:88-92` combine
  `download`+`_blank` — fragile dans les mêmes conditions. La gestion d'erreur des ~49 sites blob
  (try/catch + toast + `revokeObjectURL`) appartient à **VX49** — ne PAS la refaire ici. Fix :
  `downloadBlobInGesture` (patron `openPdfInGesture` de VX48 : onglet pré-ouvert dans le handler
  de tap quand iOS/standalone, `a.download` ailleurs) + routage des ~20 sites ; état
  `loading`/désactivé sur les 6 boutons Excel (`DevisList.jsx:772`, `FactureList.jsx:620`,
  `InstallationsPage.jsx:353`, `Rapports.jsx:523`, `EquipementsPage.jsx:551`,
  `TicketsPage.jsx:1396` — VX49 pose le toast, jamais le pending) ; brancher le repli `pdfBlob` vers
  `openPdfInGesture` ou `location.assign` (uniquement le chemin d'OUVERTURE, jamais le moteur
  `/proposal`, règle #4). Files : `utils/downloadBlob.js`, `utils/pdfBlob.js`, `api/importApi.js`,
  les call-sites. DoD : vitest UA iOS/standalone → le helper passe par le chemin geste (l'inverse
  ailleurs) ; bouton Exporter désactivé + spinner pendant l'attente ; vérification APPAREIL
  RÉEL/standalone notée au DoD (le simulateur ne suffit pas) ; e2e WebKit (VX189) : « Exporter »
  aboutit. (T2 — M, sonnet) (@lane: frontend/ios)

- [ ] VX173 — **`VoiceRecorder` : mimeType négocié (fin du blob mp4 étiqueté « webm »).** (@lane: frontend/ios)
  `VoiceRecorder.jsx:64` : `new MediaRecorder(stream)` sans mimeType, `:70` étiquette
  `rec.mimeType || 'audio/webm'` — WebKit ne supporte pas webm et produit `audio/mp4` ⇒ message
  vocal mal typé, lecture/serveur KO sur iPhone. Le voisin
  `features/ia/voice/useVoiceChat.js:55` a DÉJÀ `pickAudioMimeType()` propre (webm/opus → mp4).
  Fix : exporter `pickAudioMimeType` (source unique), passer `{mimeType}` au constructeur,
  étiqueter le blob du vrai type négocié. Files : `features/messaging/VoiceRecorder.jsx`,
  `features/ia/voice/useVoiceChat.js`. DoD : mock MediaRecorder mp4-only → blob `audio/mp4`,
  jamais « webm » en dur ; un vocal WebKit se relit. (T2 — S, sonnet) (@lane: frontend/ios)

- [ ] VX174 — **Politique de saisie iOS sur les primitives (`sanitize`) + `DatePicker` là où (@lane: frontend/ios)
  `min`/`max` porte une règle métier.** `ui/Input.jsx`/`Textarea.jsx` : ZÉRO défaut
  `autoCapitalize`/`autoCorrect` (29 fichiers overrident au coup par coup) — références
  `DEV-202607-…`, emails, ICE/IF, SKU, plaques auto-capitalisés/corrigés au clavier iPhone. Et 93
  `<input type="date">` natifs : la roue iOS IGNORE `min={todayStr()}`
  (`ActivitiesPanel.jsx:125`, `MesActivitesPage.jsx:278`) — contrainte métier contournable sur
  iPhone. Fix : prop `sanitize` (`'code'|'email'|'name'|'off'`) sur Input/Textarea forçant
  `autoCapitalize/autoCorrect/spellCheck/autoComplete/inputMode` cohérents, appliquée aux champs
  référence/ICE/IF/SKU/email des formulaires clés ; remplacer par `ui/DatePicker` (custom
  existant, borne en JS) UNIQUEMENT les dates à contrainte métier (relances, échéances, activités à
  venir). Files : `ui/Input.jsx`, `ui/Textarea.jsx`, `ActivitiesPanel.jsx`,
  `MesActivitesPage.jsx`, formulaires clés. DoD : `<Input sanitize="code">` rend les 4 attributs
  off ; WebKit : impossible de choisir une date < `min` sur un champ borné. (T2 — M, sonnet)
  (@lane: frontend/ios)

- [ ] VX175 — **Plancher CSS tactile/viewport : `touch-action` global, momentum horizontal, (@lane: frontend/ios)
  `.modal` dvh, ellipse sidebar.** Quatre oublis mécaniques prouvés : (a) `touch-action:
  manipulation` n'existe que sur `.kb-drag-wrap` (`index.css:4180`) — double-tap-zoom parasite +
  délai 300 ms partout ailleurs : l'étendre au sélecteur global du tap-highlight
  (`index.css:148`). (b) ≥5 conteneurs `overflow-x:auto` sans `-webkit-overflow-scrolling:touch`
  ni `overscroll-behavior-x:contain` (`.lines-table-wrap:1179`, `.lv-wrap:4472`, kanban `:4087`,
  `.lead-nav:1012` — `.agent-sql` RETIRÉ : CSS mort, 0 consommateur, sa suppression appartient à
  VX121) — classe utilitaire `.scroll-x-touch`. (c) `.modal` (`index.css:899-905`) est le SEUL
  bloc `100vh` du fichier sans repli `100dvh` (bas de modale rogné sous barre d'adresse
  dynamique) — ajouter la paire comme partout ailleurs. (d) `Sidebar.jsx:312` : `title=` seulement
  si `collapsed` + `.sidebar-nav-label` sans `text-overflow` (`index.css:427`) — libellé
  silencieusement COUPÉ à texte-zoom élevé : ellipsis + `title` inconditionnel. Files :
  `index.css`, `components/layout/Sidebar.jsx`. DoD : WebKit — scroll de lignes inertiel,
  double-tap sans zoom ; `modal-viewport.test` étendu à `dvh` ; libellé tronqué → `…` + `title`
  présent en état déplié. (T2 — S, haiku/sonnet) (@lane: frontend/ios)

- [ ] VX176 — **Safe-area complète : overlays plein écran + barres fixes (encoche/Dynamic Island (@lane: frontend/ios)
  en PWA standalone).** `black-translucent` (`index.html`) fait passer le contenu SOUS la barre
  d'état ; le header réserve `env(safe-area-inset-top)` (`index.css:467`) mais les overlays Radix
  `fixed inset-0` (`ui/Sheet.jsx:26`, `Dialog.jsx:40`, `AlertDialog.jsx:23`) n'ont AUCUN inset
  haut — un Sheet latéral colle son bord sous l'encoche en standalone ; `safe-area-inset` = 2
  fichiers dans tout le repo (les barres fixes/bottom-tab/FAB VX42 non couvertes non plus). Fix :
  classe `safe-top` (`padding-top: env(safe-area-inset-top)`) sur les overlays plein écran +
  application aux surfaces fixes globales + `viewport-fit=cover` vérifié. Files : `ui/Sheet.jsx`,
  `ui/Dialog.jsx`, `ui/AlertDialog.jsx`, `index.css`, `index.html`. DoD : simulateur iPhone
  standalone — l'en-tête d'un Sheet/AlertDialog n'est jamais sous l'encoche ; extension de
  `modal-viewport.test.jsx`. (T2 — S, sonnet) (@lane: frontend/ios)

- [ ] VX177 — **`ExternalLink` : navigation standalone PWA maîtrisée.** En mode `standalone` iOS, (@lane: frontend/ios)
  ~18 `<a target="_blank">` externes (GED/KB/RH/wa.me/`verifierIceUrl`) ouvrent un
  SFSafariViewController sans retour naturel ; un lien interne nu peut ÉJECTER hors de la coquille
  installée. `PwaPrompts.jsx:17` détecte `isStandalone()` sans jamais l'exploiter. Fix : un
  `<ExternalLink>`/`openExternal(url)` centralisant `_blank`+`noopener` pour l'EXTERNE et
  react-router pour l'INTERNE (jamais de `<a href>` nu pour une route interne) ; ne touche PAS
  `/proposal` ni les pages publiques GED (règle #4). Files : `ui/ExternalLink.jsx` (nouveau) + les
  call-sites externes. DoD : en standalone simulé, lien externe → nouvel onglet sans quitter la
  coquille ; lien interne → routeur ; test de rendu. (T2 — M, sonnet) (@lane: frontend/ios)

- [ ] VX178 — **`backdrop-blur` retiré des surfaces sticky scrollées (jank WebKit du (@lane: frontend/ios — avant ARC49/53)
  DataTable).** `ui/datatable/DataTable.jsx:436` (thead `sticky top-0` + `backdrop-blur`) + `:669`
  (tfoot sticky) + `BulkActionBar.jsx:39` : `backdrop-filter` recomposé à CHAQUE frame de scroll —
  jank et scintillement connus WebKit sur les grandes listes ; ARC49/53 vont migrer
  DevisList/FactureList SUR ce composant fragile. Fix : fond opaque token-isé (`bg-muted` plein)
  sur les barres sticky — le blur n'apporte rien sur une barre déjà pleine et coûte cher ; blur
  conservé sur les overlays STATIQUES. Files : `ui/datatable/DataTable.jsx`,
  `ui/datatable/BulkActionBar.jsx`. DoD : grep confirme `backdrop-blur` retiré des thead/tfoot
  sticky ; rendu visuel équivalent ; scroll 100+ lignes fluide en WebKit. (T2 — S, sonnet) (@lane:
  frontend/ios — avant ARC49/53)

- [ ] VX179 — **Service worker : cache runtime `StaleWhileRevalidate` des images/médias (@lane: frontend/ios)
  dynamiques.** `sw.js:41-65` : précache build-time + navigations network-first SEULEMENT — zéro
  `registerRoute` runtime : photos d'installation/GED et images KB re-téléchargées à chaque
  visite, et CASSÉES hors-ligne alors que la coquille, elle, marche. Fix : `registerRoute`
  `StaleWhileRevalidate` same-origin `/media/` + images KB/GED avec `ExpirationPlugin` borné (max
  entries + max age — les paquets `workbox-*` sont déjà des dépendances via vite-plugin-pwa, 0
  dép nouvelle). Files : `frontend/src/sw.js` uniquement. DoD : Playwright — article KB avec
  images visité online → `setOffline(true)` → reload → images rendues du cache ; nombre d'entrées
  ≤ max configuré. (T2 — S, sonnet) (@lane: frontend/ios)

**Sous-groupe VXD-C (suite) — Viewport & performance réelle**

- [ ] VX180 — **`DataTable`/`ListShell` : le seuil documenté (768px) n'est PAS le seuil réel (@lane: frontend/ios — avant ARC49/53)
  (Tailwind `sm` = 640px) — 42 pages affectées, indétectable par les tests actuels. AVANT
  ARC49/53.** `ui/datatable/DataTable.jsx:396` (`hidden … sm:block`) et `:702` (`sm:hidden`)
  utilisent l'utilitaire Tailwind par défaut (640px) alors que le code ET son test affirment 768px
  en toutes lettres (commentaires `:697/:701`, `DataTable.test.jsx:253-271`) — vérifié : AUCUN
  override de `--breakpoint-sm` dans `design/tokens.css` `@theme`. Entre 640 et 767px (petite
  tablette portrait, Android paysage, fenêtre redimensionnée), la TABLE DESKTOP s'affiche à la
  place des cartes que le code croit garantir. Le test ne vérifie qu'une SOUS-CHAÎNE de classe
  (jsdom n'applique aucune media query) — il ne peut structurellement PAS le détecter ; aucun
  projet Playwright ne couvre cette bande (mobile=390, desktop=1280). 42 pages via
  `ui/module/ListShell.jsx` (compta ×9, flotte ×8, paie ×5, rh ×5, ged ×4…) + 4 usages directs
  héritent du bug. Fix : variante Tailwind DÉDIÉE `dt-desktop:` mappée à 768px, réservée au
  DataTable (option sûre — l'option globale `--breakpoint-sm: 48rem` traverse tout `sm:` du
  projet → opus si retenue) ; corriger le test pour PROUVER le seuil (Playwright réel à 700px,
  `toBeVisible()`, jamais une classe). Files : `ui/datatable/DataTable.jsx`, `DataTable.test.jsx`,
  `e2e/datatable-breakpoint.spec.js` (nouveau), `design/tokens.css` (si option globale). DoD : à
  700px réels, les cartes sont visibles et la table ne l'est pas ; les 42 pages `ListShell` non
  régressées. (T1 — M, sonnet ; opus si option globale) (@lane: frontend/ios — avant ARC49/53)

- [ ] VX181 — **`.header-right` : 9 cibles interactives sans garde de largeur — débordement à (@lane: frontend/ios)
  320-375px.** `index.css:1943-1946` fige `.header-right { flex-shrink:0; flex:0 0 auto }` sur
  mobile alors qu'il empile : loupe repliée, `LanguageSwitcher`, 3 boutons `ThemeToggle` jamais
  masqués (rendu inconditionnel `Header.jsx:87`, seul le LIBELLÉ est `hidden sm:inline` —
  `ThemeToggle.jsx:16-52`), Copilote, `ChatBell`, `NotificationBell`, avatar. Avec le padding
  `max(1.25rem, safe-area)`, l'espace utile à 320px ≈ 280px pour TOUT le header. Fix : `ThemeToggle`
  en `hidden md:flex` + les 3 options ajoutées au `DropdownMenu` du menu utilisateur ; si le budget
  reste tendu, regrouper Copilote/ChatBell/NotificationBell derrière un menu « Activité » mobile.
  Files : `design/ThemeToggle.jsx`, `components/layout/Header.jsx`. DoD : à 320 et 375px,
  `scrollWidth <= clientWidth` sur `.header` (Playwright) ; les 3 thèmes restent accessibles via le
  menu ; e2e mobile vert. (T2 — S/M, sonnet) (@lane: frontend/ios)

- [ ] VX182 — **7 modales fait-main hors LeadForm : le même défaut que VX89 corrige, sur 7 (@lane: frontend/forms — @after VX89)
  surfaces qu'il ne cite pas. @after VX89.** Grep négatif vérifié
  (`Escape|autoFocus|role="dialog"|aria-modal|ResponsiveDialog` = 0) sur 7 fichiers au même shell
  `.modal-overlay` brut que `LeadForm.jsx:588` : `features/logistique/PodCaptureDialog.jsx`,
  `features/logistique/TransfertsScreen.jsx`, `pages/crm/ClientDetailPanel.jsx`,
  `pages/crm/leads/ConvertirClientDialog.jsx`, `LeadInsightsDialog.jsx`, `PlanActiviteDialog.jsx`,
  `SigneDialog.jsx` — Tab passe SOUS le voile, Escape ne ferme rien, dont deux flux terrain
  photo/signature à forte fréquence tactile. Fix : envelopper chaque shell dans
  `ResponsiveDialog` (Dialog Radix bureau / Sheet bas mobile, hook `matchMedia` réactif — déjà
  4/11 adoptants), `autoFocus` sur le premier contrôle, en LOT mécanique une fois le patron VX89
  posé. Files : les 7 fichiers. DoD : chacun répond à Escape, autofocus posé, largeur desktop
  équivalente, e2e leads/logistique verts. Complément de VX168 (dirty-guard flotte/GP — fichiers
  disjoints, préoccupation différente). (T2 — M, sonnet) (@lane: frontend/forms — @after VX89)

- [x] VX183 — **Densité par palier : colonnes kanban 272px fixes (pipeline à moitié invisible sur
  iPad) + calendrier 7 colonnes illisible sous 400px.** (a) DONE — `index.css` `.kb-col { flex: 0 0
  272px }`, aucune media query 768-1024 : sur l'iPad 1024×768 paysage, 6 étapes STAGES.py ≈ 1670px →
  ~3,7 colonnes visibles, défilement horizontal permanent. Fix livré : `@media (max-width: 1024px)
  and (min-width: 900px)` → `.kb-col` 150px (calcul incluant sidebar 240px + kb-board padding/gaps,
  garantit ≥5 des 6 colonnes visibles à 1024px même sidebar dépliée) ; bureau >1024px inchangé.
  Partagé par CRM leads/installations/interventions (même classe `.kb-col`). (b) BLOCKED : `@after
  VX147` — dépend de l'extraction `MonthGrid` que VX147 doit produire (`MonthGrid.jsx` n'existe pas
  encore dans `pages/CalendarPage.jsx`/`crm/leads/views/CalendarView.jsx`) ; composition guard —
  ne pas hand-roll cette extraction ici. Reste à faire une fois VX147 mergé : vue « agenda » (liste
  verticale jour-par-jour) sous ~400px pour la grille `repeat(7, minmax(0,1fr))` illisible à 320px.
  Files : `index.css` (fait), `components/MonthGrid.jsx`/`CalendarPage.jsx`/
  `crm/leads/views/CalendarView.jsx` (en attente de VX147). (T2 — M, sonnet)
  (@lane: frontend/ios — @after VX147)

- [x] VX184 — **Un seul comportement mobile pour les lignes-produit : `data-label` + bascule
  carte sur DevisForm/FactureForm. @coord VX146 (FactureForm).** `pages/ventes/DevisForm.jsx:292-303`
  et `FactureForm.jsx:407-419` : `<table min-w-[640px]>` dans un `overflow-x-auto` — scroll
  horizontal permanent sur téléphone, alors que `.lines-table` du générateur bascule en cartes
  empilées sous 768px (`index.css:2122-2154`, patron `data-label` complet). Fix : poser les
  `data-label` manquants + étendre les règles `.lines-table` à ces deux tableaux (ou migrer vers la
  classe partagée si les colonnes correspondent). Files : `DevisForm.jsx`, `FactureForm.jsx`,
  `index.css`. DoD : à 375px, éditer un devis existant affiche des cartes empilées comme le
  générateur ; e2e non régressé. La garde `data-label` de VX50 ne couvre que les tables
  `.data-table` de LISTE, pas ces modales. (T2 — M, sonnet) (@lane: frontend/ios)

- [ ] VX185 — **Le barrel `ui/index.js` fuit `datatable`/`recharts`/`pdfjs-dist` dans le preload (@lane: frontend/ios)
  du BOOT (~350 Ko gzip avant l'écran de connexion) + garde CI étendue.** Build réel :
  `dist/index.html` contient 21 `<link rel="modulepreload">` dont `pdfjs-dist` (125,6 Ko gzip),
  `recharts` (110,3), `datatable` (29,2) — chargés sur TOUTE page, `/login` inclus, sur le 4G
  marocain. Origine tracée : `Header.jsx:8` importe depuis le barrel `'../../ui'` dont la
  DERNIÈRE ligne (`ui/index.js:57`) exporte `datatable` ; Header est statique dans `Layout.jsx:7`
  → `router/index.jsx:8` → `main.jsx`. La garde YHARD7 (`check_bundle_budget.mjs`, 2 161,8/2 200
  Ko — 98,3 % consommé) mesure chaque chunk ISOLÉMENT, jamais ce que `index.html` précharge au
  boot. Fix : imports DIRECTS (`../../ui/Avatar`, `../../ui/DropdownMenu`) dans `Header.jsx` +
  `LanguageSwitcher.jsx:5` ; étendre `check_bundle_budget.mjs` (additif) : échec si un vendor
  lourd nommé (`recharts`/`pdfjs-dist`/`datatable`/`roof-tool`) figure en `modulepreload`
  (allowlist commentée) + plafond/métrique du NOMBRE de chunks. Files :
  `components/layout/Header.jsx`, `LanguageSwitcher.jsx`, `frontend/scripts/check_bundle_budget.mjs`.
  DoD : après build, `grep modulepreload dist/index.html` sans recharts/pdfjs/datatable ; la garde
  est rouge si on les réintroduit ; `Header.test.jsx` vert. (T2 — M, sonnet) (@lane:
  frontend/ios)

- [ ] VX186 — **Code-splitting intra-écran : les 5 vues de LeadsPage + `MapView`/leaflet enfin (@lane: frontend/ios)
  lazy.** `pages/crm/leads/LeadsPage.jsx:22-26` importe STATIQUEMENT les 5 vues, le rendu
  (`:437-449`) ne fait qu'en choisir une : `CarteView` embarque leaflet (150,7 Ko/44,4 gzip, plus
  gros composant non-vendor), `ChartsView` embarque recharts → LeadsPage = PLUS GROS chunk de
  route du repo (137,9 Ko/38 gzip). `MapView` est aussi statique dans `CartePage.jsx` et
  `ParcInstallePage.jsx:467`. Fix : `React.lazy` + `<Suspense>` autour du switch de vue (motif
  standard du router, 0 dép) ; `lazy(MapView)` aux 3 sites. Files : `LeadsPage.jsx`,
  `CartePage.jsx`, `views/CarteView.jsx`, `installations/ParcInstallePage.jsx`. DoD : `npm run
  build` → `LeadsPage-*.js` chute (~40 Ko gzip, shell + vues par défaut) ;
  MapView/ChartsView/CalendarView = chunks séparés chargés au premier clic d'onglet ; tests
  LeadsPage/KanbanView verts. (T2 — S/M, sonnet) (@lane: frontend/ios)

- [ ] VX187 — **LeadsPage runtime : `useDeferredValue` sur le filtre + `React.memo` sur les (@lane: frontend/ios)
  cartes (l'exception MESURÉE au différé round-2).** `LeadsPage.jsx:76/:82` :
  `filterLeads(leads, filters)` recalcule en SYNCHRONE dans un `useMemo` à chaque frappe de la
  recherche ; et zéro `memo(` dans `LeadCard.jsx`/`ListView.jsx` : chaque frappe re-rend toutes
  les cartes visibles. Fix : `useDeferredValue(filters)` pour dériver la liste (input dans la lane
  urgente, `isStale` → dim) ; `React.memo(LeadCard)` + rangée ListView + `useCallback` sur les 2-3
  handlers parents (sinon le memo ne tient pas) ; option (c) `<Activity mode>` (React 19.2
  confirmé `^19.2.5`) pour préserver scroll/état local à la bascule kanban↔liste — API récente :
  vérifier la sémantique des effets avant de shipper, abandonner proprement si elle ne convient
  pas. Files : `LeadsPage.jsx`, `views/LeadCard.jsx`, `views/ListView.jsx` (+ call-sites
  KanbanView). DoD : vitest — frappes rapides : `filterLeads` ne re-tourne pas en synchrone dans
  le commit de la frappe ; spy : une carte non concernée ne re-rend pas ; (c) bascule → scroll
  préservé. (T2 — M, sonnet) (@lane: frontend/ios)

- [x] VX188 — **DevisGenerator : extraire `DevisLineRow` mémoïsé + `startTransition` sur les
  cascades de recalcul. @with/after VX62 — même fichier.** `DevisGenerator.jsx` : 64 `useState` ;
  les agrégats lourds sont DÉJÀ bien mémoïsés (`totals` :336-339, `roi`/`chartData` en
  `useDeferredValue` :354-358) MAIS le tableau de lignes (`lines.map` :1979) est du JSX inline :
  chaque frappe dans `note`/`farmSurfaceHa`/n'importe lequel des 63 autres états réconcilie N
  `<ProduitPicker>` (filtrage interne `ProduitPicker.jsx:44-66` tournant à vide) ; et
  `onProduitChange`/`onProduitCreated` sont recréés à chaque rendu. Fix : extraire `DevisLineRow`
  en `React.memo` + stabiliser les callbacks (clé de ligne en ARGUMENT, pas en fermeture) ;
  envelopper les 2-3 cascades de recalcul solar.js dans `startTransition` avec `isPending` sur le
  bloc TOTAUX — jamais sur l'input : la règle fondateur « ne jamais snapper/rejeter un nombre
  tapé » est un invariant absolu, ceci n'est qu'un changement d'ORDONNANCEMENT. Files :
  `pages/ventes/DevisGenerator.jsx`. DoD : taper dans « Note » sur un devis à 15 lignes ne re-rend
  PAS les ProduitPicker inchangés (spy) ; le test noValidate/step="any" reste vert. (T2 — M,
  sonnet) (@lane: frontend/ventes — @with/after VX62)

- [ ] VX189 — **Pack micro-perf mécanique : chunk `icons` unique, Sidebar `useMemo`, (@lane: frontend/ios)
  `content-visibility`, LoAF dev-warning.** Quatre gains prouvés, tous S, zéro dépendance : (a)
  126 chunks JS < 1 Ko gzip (icônes lucide individuelles, sur 345 chunks au total) —
  `manualChunks` dédié dans `vite.config.js:203-211` (`lucide-react` → chunk `icons` unique). (b)
  `Sidebar.jsx:238-246` recalcule la fusion `NAV_SECTIONS`+`moduleNavSections` et re-filtre par
  rôle À CHAQUE rendu — `useMemo` sur la fusion (statique) et le filtrage (`[role, permissions]`).
  (c) `content-visibility: auto; contain-intrinsic-size` sur les sections hors-écran de
  Dashboard/Rapports (paint sauté sans JS — vérifier que recharts ne casse pas sous
  content-visibility). (d) `lib/devPerfWarn.js` dev-only : `PerformanceObserver`
  `long-animation-frame` → `console.warn` formaté, gardé par `import.meta.env.DEV`, zéro octet en
  prod. **Note de coordination :** quand VX61 se construit, utiliser `web-vitals/attribution` et
  inclure `longAnimationFrameEntries` (top-3 scripts) dans le beacon — amendement du Done= de
  VX61, même fichier `vitals.js`, ne pas transcrire comme tâche. Files : `vite.config.js`,
  `components/layout/Sidebar.jsx`, CSS Dashboard/Rapports, `lib/devPerfWarn.js` (nouveau),
  `main.jsx`. DoD : chunks < 1 Ko ≈ 0-5 + un chunk `icons` unique, budget YHARD7 vert ; profiler :
  Sidebar ne recalcule que sur changement de rôle ; zéro saut de scrollbar ; tâche synthétique
  250 ms → table console en dev, zéro référence au module en build prod. Sora/`/landing` EXCLU —
  VX57 le possède. (T2 — S, haiku ; sonnet pour le c) (@lane: frontend/ios)

- [ ] VX190 — **Garde CI WebKit étendue : exports blob + sticky DataTable + standalone. @after (@lane: frontend/ios — @after VX68)
  VX68 + VX172/176/178.** VX68 ajoute les projets `mobile-safari` (WebKit réel) + `tablet` mais ne
  teste NI l'export blob (VX172), NI le rendu sticky/`backdrop-blur` du DataTable (VX178), NI la
  navigation standalone (VX176/177). Fix : 3 assertions ajoutées au spec WebKit une fois VX68
  mergé : (a) clic « Exporter » aboutit par le chemin geste (pas d'échec silencieux) ; (b) scroll
  d'un DataTable large garde thead/tfoot lisibles (pas de détachement) ; (c) un `Sheet` en
  standalone simulé respecte l'inset haut. Files : `frontend/e2e/mobile-safari.spec.js` (ou le
  spec de VX68), `playwright.config.js`. DoD : les 3 assertions vertes en CI WebKit ; rouges si on
  régresse VX172/176/178. (T2 — S/M, sonnet) (@lane: frontend/ios — @after VX68)

**Sous-groupe VXD-C (suite) — Accessibilité forensique (WCAG 2.2 prouvée file:line)**

*Acquis vérifiés à NE PAS refaire : Radix (focus-trap/Échap/flèches), sonner déjà
`aria-live=polite`, anneau `:focus-visible` global + `scroll-margin` (`index.css:89-132`),
reduced-motion (`:67-87`), cibles 44px `pointer:coarse` (`:156-173`), DataTable exemplaire
(`aria-sort`/`scope`/live).*

- [ ] VX191 — **`useActiveDescendant` : brancher `aria-activedescendant` sur les 10 (@lane: frontend/ios — @coord VX128)
  autocomplétions (grep = 0 partout).** *(Note : recoupe partiellement VX128 axe1 sur
  Combobox/MultiSelect/TimePicker — ce seed ÉTEND la couverture à `ProduitPicker.jsx`/
  `BcfProduitPicker.jsx`, `ToitureDesign.jsx`, `MentionAutocomplete.jsx`,
  `SlashCommandPicker.jsx`, `ShareRecord.jsx`, `GlobalSearch.jsx` — coordonner l'ordre
  d'implémentation avec VX128, ne pas dupliquer le hook.)* Le motif « champ texte → listbox avec
  curseur visuel » est réimplémenté 10 fois — et `aria-activedescendant` = 0 fichier dans tout le
  repo : flécher au clavier n'annonce RIEN (WCAG 4.1.2). Fix : hook
  `hooks/useActiveDescendant.js` (id stable par option, `aria-activedescendant` sur l'input,
  `id`/`aria-selected` sur l'option active), adopté d'abord dans `Combobox` + `MultiSelect`, puis
  `MentionAutocomplete` (+ le `Composer` qui la pilote) et `GlobalSearch`. Files : le hook
  (nouveau) + les 4 primitives citées. DoD : test RTL — l'input porte un `aria-activedescendant`
  pointant l'option `aria-selected` à chaque ↑/↓ ; VoiceOver/NVDA annonce le libellé. (T2 — M,
  sonnet) (@lane: frontend/ios — @coord VX128)

- [x] VX192 — **Kanbans accessibles : `StageMover` porté au kanban chantiers + `KeyboardSensor` +
  annonces FR sur les 3 kanbans + fin du `window.alert`.** Les 3 `<DndContext>` montent
  `useSensors(PointerSensor, TouchSensor)` sans `KeyboardSensor` ni
  `accessibility.announcements` (`crm/leads/views/KanbanView.jsx:173-209`,
  `installations/views/KanbanView.jsx:136-173`,
  `gestion_projet/…/TachesKanbanView.jsx:119-122`). Le kanban leads compense avec `StageMover`
  (`:31-53`, select clavier) ; le kanban CHANTIERS n'a RIEN : carte ouverte par `<div onClick>`
  non focalisable (`:178`), refus de déplacement en `window.alert()` bloquant (`:161`). Fix :
  porter `StageMover` au kanban chantiers, carte → `<button>`, `window.alert` → bandeau
  `role="status"` (patron leads `:211-218`) ; + `useSensor(KeyboardSensor)` (0 dép) et un helper
  d'annonces FR partagé sur les 3 kanbans. Files : les 3 `KanbanView`,
  `features/*/kanbanA11y.js` (helper nouveau). DoD : au clavier seul — Tab atteint le sélecteur
  d'étape et le change ; Espace saisit une carte, flèches déplacent, Entrée dépose, chaque étape
  annoncée en FR ; plus aucun `window.alert` (assert). (T2 — M, sonnet ; opus si l'entonnoir+clavier
  se complique) (@lane: frontend/ios)

- [ ] VX193 — **LeadForm : labels associés + validation client annoncée ; AppointmentBooker : (@lane: frontend/crm — @with VX144)
  disclosure + tokens morts. @with VX144 + `ma-file` (même passe fichier).** Le plus gros
  formulaire CRM rend tous ses labels SANS `htmlFor` et ses inputs SANS `id` (helpers `Txt`/`Sel`
  `LeadForm.jsx:101-118` ; champs `:763-987`) ; les erreurs `form-feedback` (`:766,780`) n'ont ni
  `role="alert"` ni `aria-describedby`, l'input invalide pas d'`aria-invalid` (`:764`).
  `AppointmentBooker.jsx` : bouton révélateur sans `aria-expanded`/`aria-controls` (`:125-133`),
  labels nus (`:140,153`), erreur muette (`:163-167`), et des variables CSS INEXISTANTES
  (`--color-text-muted`, `--color-danger`… `:73-164`) qui cassent le dark mode. Fix : `id` (via
  `useId`) + `htmlFor` dans `Txt`/`Sel` — idéalement pointer le primitif `FormField` déjà correct
  (`ui/Form.jsx:93-104`) ; `aria-invalid` + `aria-describedby` → `form-feedback` avec `id` +
  `role="alert"` ; `aria-expanded`/`aria-controls` sur la disclosure ; migrer les `--color-*`
  morts vers les vrais tokens. Files : `pages/crm/LeadForm.jsx`,
  `pages/crm/leads/AppointmentBooker.jsx`. DoD : cliquer un label focalise son champ ; soumettre
  « Nom » vide → message annoncé + `aria-invalid` ; le bouton annonce réduit/développé ; dark mode
  réparé ; e2e leads verts. `DevisGenerator` fait correctement `htmlFor`, preuve que c'est un
  défaut d'écran. (T2 — M, sonnet) (@lane: frontend/crm — @with VX144)

- [ ] VX194 — **Plancher visuel WCAG 2.2 : texte accent brass 1.8:1 → ≥4.5:1 + cibles 24px (@lane: frontend/ios)
  desktop + test de contraste.** (a) `tokens.css:70` `--primary:#e8b54a` : en REMPLISSAGE de
  bouton c'est conforme, mais `Button` variant `link` = `text-primary` (`ui/Button.jsx:33`) rend
  le brass EN TEXTE sur `--background:#f6f8fc` ≈ 1.8:1 (échec 1.4.3 — 4.5:1 requis), consommé
  dans ≥10 pages et `text-primary` dans 48 fichiers ; `--warning:#c8870f` en texte ≈ 3.3:1. Fix :
  token dédié `--primary-text` (brass ASSOMBRI ≥4.5:1 — brass-600/700 déjà dans
  `tokens.css:36-37`) pour le variant `link` + les utilitaires de texte accent, idem warning ; test
  de contraste en calcul pur (0 dép) sur les paires Button des DEUX thèmes. (b) le plancher 44px
  n'existe que sous `pointer:coarse` — WCAG 2.5.8 (AA, 2.2) exige 24×24 px indépendamment du
  pointeur : cas prouvés `ChatterWidget.jsx:114` (Trash2 size=12), `chat-mention-item` → plancher
  24×24 via `IconButton` + les cas cités. Files : `design/tokens.css`, `ui/Button.jsx`,
  `ui/contrast.test.*` (nouveau), `ui/IconButton.jsx`, `components/ChatterWidget.jsx`. DoD : tout
  texte accent ≥4.5:1 clair ET sombre (le test échoue sinon) ; chaque bouton-icône ≥24×24 en
  pointeur fin. (T2 — M, sonnet) (@lane: frontend/ios)

- [x] VX195 — **Carte Leaflet accessible : rôle + liste clavier parallèle.**
  `components/MapView.jsx:115-121` : le conteneur n'a ni `role`, ni `aria-label`, ni fallback ; les
  marqueurs (`marker.on('click')` :102) ne sont pas focalisables — un technicien au
  clavier/lecteur d'écran n'a AUCUN accès aux leads/chantiers géolocalisés (CartePage,
  ParcInstallePage). Fix : `role="application"` + `aria-label` FR (« carte, N points ») ; liste
  clavier PARALLÈLE (chaque marqueur = un `<button>` dans une liste repliable/sr-only appelant le
  même `onMarkerClick`). 0 dép, Leaflet reste impératif. Files : `components/MapView.jsx`
  (CartePage/ParcInstallePage héritent). DoD : au clavier, Tab atteint chaque point via la liste et
  déclenche la même action ; VoiceOver annonce « carte, N points » ; test de la liste de boutons.
  (T2 — M, sonnet) (@lane: frontend/ios)

- [x] VX196 — **Régions live : chat/chatter annoncés + scroll clavier + erreurs toast en
  `assertive`.** (a) `MessageThread.jsx:104-135` : un message entrant pousse dans un `<div>`
  scrollable sans `aria-live` (WCAG 4.1.3) et sans `tabIndex`/`role`. (b)
  `ChatterWidget.jsx:100-126` : liste sans live ; bouton supprimer avec `title` seul (`:117`). (c)
  le succès d'un déplacement kanban n'émet aucun `role="status"` (seul l'échec en a un). (d)
  toutes les erreurs sonner partent en `polite` — une erreur bloquante devrait interrompre. Fix :
  `aria-live="polite"` + `aria-relevant="additions"` (n'annoncer QUE le dernier message) ;
  scroll-container `role="log"` + `tabIndex={0}` ; `aria-label="Supprimer le commentaire"` (le
  `title` reste pour VX52) ; `role="status"` sur le succès kanban ; dans `lib/toast.js`,
  `toastError` pose l'option sonner `assertive`/`important`, succès/info restent `polite`. Files :
  `features/messaging/MessageThread.jsx`, `components/ChatterWidget.jsx`, `lib/toast.js` (+
  `ui/Toaster.jsx` si région séparée). DoD : un message entrant est annoncé UNE fois ; le fil est
  défilable au clavier ; une erreur interrompt (assertive), un succès non ; tests RTL. (T2 — S,
  sonnet) (@lane: frontend/ios)

- [ ] VX197 — **`RouteFocus` : skip-link + focus `<main>` + navigation annoncée. @coord VX82 (@lane: frontend/ios)
  pour le titre.** `Layout.jsx:68-78` : `<main>` sans `id`/`tabIndex` ; la barre de progression de
  route (`role="progressbar"` :71-75) n'a pas d'`aria-live` ; 0 skip-link, 0 focus déplacé, 0
  repère après navigation SPA (WCAG 2.4.1/2.4.3). Fix : `<RouteFocus>` monté dans Layout — à
  chaque `location` : focus sur `<main id="contenu" tabIndex={-1}>`, annonce du nom d'écran via
  une région `aria-live="polite"` dédiée (source `routes.meta.js`, déjà là) ; skip-link « Aller au
  contenu » premier focalisable ; `aria-live` sur la barre de progression. NE PAS re-créer la
  gestion du titre d'onglet : **VX82 possède `useDocumentTitle`** — RouteFocus ANNONCE ce que VX82
  AFFICHE (consommer le même méta). Files : `components/layout/Layout.jsx`,
  `components/layout/RouteFocus.jsx` (nouveau), `routes.meta.js`. DoD : après navigation, Tab part
  du contenu (pas du header) ; le nom d'écran est annoncé une fois ; skip-link visible au premier
  Tab ; e2e clavier. (T2 — M, sonnet) (@lane: frontend/ios)

- [ ] VX198 — **[GATED si dev-dep à ajouter] Garde statique jsx-a11y ciblée : empêcher d'ÉCRIRE (@lane: frontend/ios)
  la régression (complément build du scan runtime VX71).** Rien n'empêche la réintroduction des
  trous ci-dessus (label sans contrôle, rôle sans props ARIA requises, interactif non
  focalisable) — `eslint-plugin-jsx-a11y` absent de la config (à confirmer ; sinon [GATED]
  dev-dep). Fix : sous-ensemble ciblé en warn→error : `label-has-associated-control`,
  `role-has-required-aria-props`, `interactive-supports-focus`, `click-events-have-key-events`,
  `img-redundant-alt`. Files : `frontend/eslint.config.js` (aucun code métier). DoD : `npm run
  lint` signale un `<label>` sans contrôle associé ; `frontend-lint` échoue sur une régression
  neuve ; le build actuel reste vert. (T2 — S, sonnet) (@lane: frontend/ios)

**Sous-groupe VXD-A (suite) — Sécurité frontend & observabilité (les échecs que personne ne
voit)**

*Non-défauts vérifiés à NE PAS re-signaler : auth par cookie httpOnly (aucun jeton en
localStorage, `AUTH_LOCALSTORAGE_KEYS=[]`), rendus chat/KB/copilote en arbres React (pas
d'injection), `rel=noopener` présent (faux positif multi-ligne), `prix_achat` correctement masqué
partout côté client.*

*Note : la graine TOTP 2FA exfiltrée vers `api.qrserver.com` (SEED-41) est déjà transcrite en
détail en tête de document — voir **VX120**. Ne pas la reconstruire ici.*

- [x] VX199 — **[BACKEND] `IsResponsableOrAdmin` : n'importe quelle permission d'écriture ouvre
  TOUS les endpoints qu'il garde (+ test d'alignement front↔back). ÉTEND VX101, ne pas
  double-compter.** `authentication/permissions.py:14-21` : la classe passe si
  `user.is_responsable` ; or depuis ERR4 (`models.py:211-234`), `is_responsable` = « le rôle
  accorde AU MOINS UNE permission d'écriture ». Un rôle « Commercial » (écrire des leads) passe
  donc les endpoints de validation de devis, émission de facture, mouvements de stock partout où
  cette classe grossière garde seule (famille = 614 occurrences / 156 fichiers ; le code
  documente lui-même le piège, `permissions.py:31-34`). Le frontend gate FINEMENT
  (`useHasPermission`) : l'écran CACHE le bouton mais l'API directe RÉUSSIT — la classe VX101, à
  l'envers et systémique. Fix : audit des viewsets en `IsResponsableOrAdmin` PUR → permission ERP
  fine (`HasPermissionOrLegacy('<domaine>_<action>')`, mécanique existante
  `permissions.py:54-121`) sur les actions sensibles UNIQUEMENT ; + test d'ALIGNEMENT : la liste
  blanche frontend (`useHasPermission.js:29-36`, `PRODUIT_CREATE_ROLES`) comparée au comportement
  backend réel, idéalement dérivée de `/auth/me` plutôt que d'une constante en dur. Files :
  `[BACKEND]` `ventes/views/{devis,facture,bon_commande}.py`, `stock/views/mouvement.py`,
  `crm/views.py` (remplacements de classe, additifs) ; `frontend/src/hooks/useHasPermission.js`.
  DoD : un compte « lecture + une écriture » reçoit 403 en appelant directement la validation de
  devis / l'émission de facture (étendre `tests_role_tier.py`) ; un test échoue si front et back
  divergent. **@coord VX101** (il corrige `decider_approbation`/`IsAnyRole` — même classe de bug,
  endpoints disjoints ; ne pas doubler). (T1 — L, opus : auth/permissions) (@lane: backend/auth)

- [ ] VX200 — **[BACKEND infra] CSP figée sur des valeurs de DEV + zéro header de repli côté (@lane: backend/auth)
  SPA : templater la prod, décommenter HSTS.** `backend/nginx/Dockerfile` copie `nginx.conf`
  VERBATIM (pas d'envsubst) or `nginx.conf:78` code en dur `http://localhost:9000` (MinIO dev)
  dans `img-src`/`connect-src`/`frame-src` : en prod, les URL MinIO présignées réelles sont
  potentiellement BLOQUÉES ; HSTS est commenté (`:80`) alors que Caddy termine déjà le TLS ;
  `script-src` garde `'unsafe-inline' 'unsafe-eval'` (objectif : retirer `unsafe-eval` si maplibre
  le permet). Et `frontend/nginx.conf:1-41` (le serveur du SPA) ne pose AUCUN header. Fix : CSP
  par environnement (`envsubst` à l'entrypoint ou `map` nginx), retrait de `localhost:9000`, HSTS
  décommenté ; défense en profondeur : meta CSP de base dans `index.html` +
  `X-Frame-Options` répliqué dans `frontend/nginx.conf` (`frame-ancestors` est ignoré en meta —
  garder le header). Files : `backend/nginx/nginx.conf`, `backend/nginx/Dockerfile`,
  `docker-compose.prod.yml`, `frontend/index.html`, `frontend/nginx.conf`. DoD : en prod, `curl
  -I` → CSP sans `localhost:9000`, avec l'origine MinIO réelle, avec HSTS ; les aperçus MinIO
  s'affichent ; le SPA servi hors proxy garde CSP + anti-framing. (T2 — M, opus : headers
  sécurité) (@lane: backend/auth)

- [ ] VX201 — **Pack durcissement client : DevTools coupé en prod, garde SVG + CI (@lane: backend/auth)
  anti-`dangerouslySetInnerHTML`, jeton kiosque expirant, presse-papier 2FA vidé.** Quatre petites
  failles prouvées, un lot : (a) `store/index.js:46-48` — `configureStore` sans `devTools:
  import.meta.env.DEV` : en prod, l'extension Redux DevTools expose TOUT l'état (PII, matrice de
  permissions, leads/devis/factures) → une ligne. (b) le SEUL `dangerouslySetInnerHTML` réel
  (`InterventionCapturePanels.jsx:476`, `qr_svg`) est sûr AUJOURD'HUI mais sans garde contre une
  régression serveur → helper `lib/trustedSvg.js` (commence par `<svg`, refuse
  `<script`/`on*=`/`javascript:`, repli neutre) + règle eslint `react/no-danger` en error avec UN
  disable documenté (ou `scripts/check_no_danger.mjs` dans `frontend-lint`). (c)
  `features/rh/Kiosque.jsx:16-47` : jeton de device (`X-Kiosque-Token`) en localStorage CLAIR et
  PERMANENT sur une tablette en libre-service → timeout d'inactivité qui `oublierToken()` +
  `safeStorage` (VX170) ; `[BACKEND]` rotation si retenue. (d)
  `SecuriteCompteSection.jsx:270-277` : codes de secours 2FA copiés en clair (presse-papier
  souvent synchronisé cloud) → vidage best-effort à ~60 s + micro-avertissement. Files :
  `store/index.js`, `lib/trustedSvg.js` (nouveau), `InterventionCapturePanels.jsx`,
  `eslint.config.js` OU `scripts/check_no_danger.mjs`, `features/rh/Kiosque.jsx`,
  `SecuriteCompteSection.jsx`. DoD : build prod → DevTools n'affiche aucun store ; un `qr_svg`
  contenant `<script>` est refusé ; un `dangerouslySetInnerHTML` non whitelisté fait échouer
  `frontend-lint` ; le kiosque redemande le jeton après inactivité ; le presse-papier est vidé au
  délai (mock). (T2 — M, sonnet) (@lane: backend/auth)

- [ ] VX202 — **[BACKEND nginx] Pages publiques tokenisées : `noindex` + throttle client + (@lane: backend/auth)
  rate-limit des préfixes publics.** 10 routes `:token` publiques sans auth
  (`router/index.jsx:216-235` : `/rdv`, `/portail-contrats`, `/ged/signature|signataire|depot`,
  `/e`, `/suivi`, `/kb/public`…). Aucune page ne pose `<meta name="robots" content="noindex">` ;
  le rate-limit nginx n'existe QUE sur login/contact/register (`nginx.conf:86-118`) — rien sur
  `/ged/`, `/suivi/`, `/rdv/`, `/e/` ; le dépôt public (`PublicDepotPage.jsx:42-58`) n'a aucun
  throttle de re-soumission. Fix : composant `<NoIndex/>` partagé monté par toutes les pages
  publiques tokenisées ; throttle client de re-soumission sur le dépôt ; `[BACKEND]` étendre les
  zones `limit_req` aux préfixes publics. Files : `pages/ged/PublicDepotPage.jsx`,
  `PublicSignaturePage.jsx`, `pages/sav/TicketSuiviPage.jsx`, `pages/crm/PublicBookingPage.jsx`,
  `pages/kb/PublicArticlePage.jsx`, composant `NoIndex` (nouveau) ; `[BACKEND]`
  `backend/nginx/nginx.conf`. DoD : chaque page publique émet le meta noindex ; une re-soumission
  est throttlée ; `/ged/depot/<t>/` répond 429 sous rafale. (T2 — M, sonnet) (@lane:
  backend/auth)

- [ ] VX203 — **Contrat d'erreur UNIQUE : fin du double-toast (35 pages), `getApiError` (@lane: frontend/data)
  canonique (259 clones), `iaApi` aligné (le 403 IA n'est plus muet).** Trois moitiés du même
  contrat, explicitement renvoyées à l'axe robustesse par la synthèse beauté : (a)
  `api/axios.js:63-70` toaste DÉJÀ toute erreur ≠401/404, mais ~35 pages re-toastent dans leur
  `catch` (3 fichiers seulement posent `suppressErrorToast`) → DOUBLE toast sur des centaines de
  chemins. Contrat : l'intercepteur est la source par défaut ; tout `catch` qui gère INLINE passe
  `{suppressErrorToast:true}` ; garde grep `scripts/check_double_toast.mjs` dans frontend-lint.
  (b) 259 extractions inline `.response?.data?.detail` ré-implémentent une version PARTIELLE du
  helper existant (`lib/toast.js:92-107`) — promouvoir `lib/apiError.js` (`{message,
  fieldErrors}`, cas `non_field_errors`/tableaux/429/500 HTML/timeout), codemod des sites vers
  l'import unique (VX171 en consomme `fieldErrors`). (c) `iaApi.js` ne toaste RIEN globalement
  hors 401 : un 403 du catalogue d'actions agentiques ou un 500 FastAPI est INVISIBLE — aligner
  sur le contrat (a) en préservant les dégradations volontaires (`available:false`) via
  `suppressErrorToast`. Files : `api/axios.js`, `api/iaApi.js`, `lib/apiError.js` (extrait de
  toast.js), les ~35 pages fautives, `scripts/check_double_toast.mjs` (nouveau). DoD : un 500
  forcé = EXACTEMENT un toast (test) ; grep `.response?.data?.detail` hors helper = 0 ; un 403 IA
  surface un toast FR ; tests des formes DRF. (T2 — M/L, sonnet) (@lane: frontend/data)

- [x] VX204 — **Fin des veuves silencieuses : ChatterWidget, ActivitiesPanel, Journal +
  détection de panne prolongée des polls.** Quatre silences prouvés hors des 5 listes de VX67 :
  (a) `ChatterWidget.jsx:66-80` — l'échec d'envoi d'un commentaire est `catch { /* ignore */ }` ;
  l'intercepteur ne toaste pas les 404 → zéro signal. (b) `ActivitiesPanel.jsx:32-42` — `load()` +
  types en `.catch(() => {})` : un échec de chargement est INDISCERNABLE de « aucune relance
  due » (le state `error` existe ligne 26, jamais alimenté). (c) `Journal.jsx:235` —
  `getMeta().catch(() => {})` : les filtres de L'OUTIL D'AUDIT rendent des menus vides sans dire
  qu'ils sont cassés. (d) `useChatPolling.js:51-63` (aucun `.catch`) et
  `NotificationBell.jsx:115-138` : rien ne détecte une SÉRIE d'échecs. Fix : états d'erreur locaux
  + « Réessayer » (patron ActivitiesPanel) sur a/b/c ; compteur d'échecs consécutifs (≥3 →
  indicateur discret « Mise à jour interrompue » + reprise manuelle, reset au premier succès) sur
  la cloche et le chat. Files : `components/ChatterWidget.jsx`, `components/ActivitiesPanel.jsx`,
  `pages/Journal.jsx`, `features/messaging/useChatPolling.js`,
  `components/layout/NotificationBell.jsx`. DoD : par widget — un rejet rend un message +
  Réessayer (jamais une liste vide muette) ; 3 échecs simulés → indicateur, un succès →
  disparition. Distinct du rejet « refonte chatter » (VX23/ARC8-9) — correctif d'erreur, pas une
  refonte. (T2 — M, sonnet ; haiku sur a/b) (@lane: frontend/data)

- [ ] VX205 — **Déployer la `SectionBoundary` DÉJÀ CONSTRUITE : un panneau meurt, l'écran (@lane: frontend/data)
  survit.** `ui/ErrorBoundary.jsx:7-59` est un composant COMPLET (fallback custom, `reset()`,
  `onError`) monté dans UN SEUL fichier réel : la page de démo (`UIShowcase.jsx:507-553`). VX64 ne
  couvre que le niveau ROUTE ; mémoire projet : « /ui crashes whole-page on render throw ». Fix :
  pure tâche de DÉPLOIEMENT (rien à construire) — poser `<ErrorBoundary>` autour des zones
  indépendantes à risque : chaque `TabsContent` de `LeadForm.jsx`, cartes cockpit
  `Dashboard`/`CommercialDashboard`, `InterventionCapturePanels.jsx` ; câbler `onError` sur le
  `console.error` structuré de VX206. Files : `pages/crm/LeadForm.jsx`, `pages/Dashboard.jsx` (+
  cockpit), `InterventionCapturePanels.jsx`. DoD : un enfant qui throw dans UN onglet ne fait
  disparaître QUE cet onglet, le reste reste utilisable ; la RouteErrorBoundary parente n'intercepte
  plus ces cas. (T2 — M, sonnet) (@lane: frontend/data)

- [ ] VX206 — **Socle local d'observabilité : `console.error` des boundaries + (@lane: frontend/data — @with VX72)
  `unhandledrejection` global + identifiant support. @with VX72 (mêmes fichiers).** Zéro
  télémétrie locale : `console.error` = 1 hit dans tout `src/` ; les DEUX boundaries
  (`ui/ErrorBoundary.jsx`, `RouteErrorBoundary.jsx` — qui n'a même pas de `componentDidCatch`)
  n'écrivent RIEN. Et aucun `window.addEventListener('unhandledrejection'|'error')` : une promesse
  rejetée dans un handler d'événement, une chaîne `.then()`, ou le `sender()` de l'outbox échoue
  en silence TOTAL — invisible même après VX72, qui ne câble QUE
  `RouteErrorBoundary→captureException`. Fix : `console.error('[ErrorBoundary]', error,
  info?.componentStack)` dans les deux boundaries (ajouter `componentDidCatch` à
  RouteErrorBoundary) ; `lib/globalErrors.js` — les deux listeners globaux canalisés vers le MÊME
  chemin captureException-ou-no-op que VX72 établit + un `toastError` générique ; afficher un
  identifiant support sur l'écran de récupération (l'`eventId` VX72 quand DSN actif, sinon un
  horodatage court). Files : `ui/ErrorBoundary.jsx`, `components/RouteErrorBoundary.jsx`,
  `lib/globalErrors.js` (nouveau), `main.jsx` (+ `lib/monitoring.js` de VX72). DoD : un throw →
  `console.error` avec stack ; une promesse rejetée non gérée → toast + capture (DSN de test) ;
  sans DSN → zéro requête sortante ; l'écran de récupération montre un identifiant transmissible.
  (T2 — S, sonnet) (@lane: frontend/data — @with VX72)

---

## AXE 3 — AMOUR-EMPLOYÉ (VX207–VX252, 46 tâches survivantes sur 47 seeds ; 1 tuée par le
grand-verdict — SEED-03 — dont le delta est reporté en note sur VX56/VX86, jamais transcrit
comme tâche)

**Sous-groupe VXD-I — Attention & handoffs (le badge redevient CROYABLE). @after
VX83-86/99-101 (round 3, non construit) — transcrire chaque @after tel quel.**

- [ ] VX207 — **[BACKEND additif] Une seule vérité de comptage : endpoint canonique (@lane: backend/notify — @after VX83/VX86)
  `attention-summary`. @after VX83/VX86.** Après VX83/84/86 il existera ≥4 dérivations de
  compteur calculées par des chemins différents (badge cloche = `derivedTotal + feedUnread`
  `NotificationBell.jsx:182`, en-tête Ma file, `useApprobationsCount` VX86, badge sidebar) — rien
  ne garantit qu'elles convergent, et un badge qui ment tue tout le système d'attention. Fix :
  `GET /notifications/attention-summary/` renvoyant le décompte canonique `{actions_dues,
  en_retard, aujourdhui, approbations, mentions_non_lues}` scopé `recipient`/`assigned_to`,
  réutilisant les MÊMES selectors que « Ma file » (VX83) ; cloche, badge sidebar et en-tête Ma
  file consomment tous ce seul endpoint. Files : `apps/notifications/views.py`+`selectors.py`,
  `NotificationBell.jsx`, `useApprobationsCount.js` (VX86). DoD : test de contrat — forcer 5 items
  → les 3 surfaces affichent 5 ; aucune dérivation client parallèle restante. (T2 — M, sonnet)
  (@lane: backend/notify — @after VX83/VX86)

- [ ] VX208 — **[BACKEND additif] La cloche cesse d'être une liste plate : sévérité, regroupement (@lane: backend/notify — @with VX14)
  par entité, digest hors badge, et undo. @with VX14 (même fichier — la mise en onglets appartient
  à VX14, cette seed apporte la taxonomie/dédoublonnage/compteurs/undo).** Trois défauts prouvés
  sur la même surface : (a) `EventType` a 42 valeurs sans rang de sévérité ni catégorie — la
  cloche affiche un incident QHSE critique noyé sous des digests, 5 notifs même facture = 5
  lignes ; (b) `DIGEST` passe par `notify()` → `feedUnread` → badge (`digests.py:169`), donc le
  badge gonfle chaque matin d'un non-travail ; (c) `read-all` est irréversible et `mark_unread`
  (`views.py:68`, `notificationsApi.js:11`) a zéro consommateur. Fix : dict statique
  `EVENT_SEVERITY`/`EVENT_CATEGORY` (`apps/notifications/severity.py`, exposé en lecture dans le
  serializer, pas de migration) ; frontend — groupement par catégorie + dédoublonnage par `link`,
  liseré `critique`, deux compteurs (badge rouge ACTIONS / point gris INFOS, digests dans un
  onglet plié), `read-all` → `toastWithUndo` restaurant via `mark_unread`, bouton « Marquer
  non-lu ». Files : `apps/notifications/{severity.py,serializers.py,views.py}`,
  `NotificationBell.jsx`. DoD : un `INCIDENT_CRITICAL` remonte au-dessus de 10 `DIGEST` ; un
  digest n'incrémente pas le badge d'actions ; « Tout lu » puis « Annuler » restaure l'état exact ;
  3 notifs même lien = 1 ligne pliée. (T2 — L, sonnet) (@lane: backend/notify — @with VX14)

- [ ] VX209 — **[BACKEND] `notify()` devient humain : heures calmes, bon event de mention, (@lane: backend/notify)
  purge, émetteurs manquants.** Quatre défauts du même moteur : (a) `est_hors_fenetre_silence()`
  (`selectors.py:23`) n'est consulté que par le marketing ET la compta (`compta/services.py:6083`),
  jamais par `notify()` lui-même — un push/email de `sweep_daily` ou d'escalade part à 23 h ou un
  jour férié ; (b) `_notify_mentions` (`records/views.py:315`) émet `ET.LEAD_ASSIGNED` pour une
  @mention : couper la préférence `lead_assigned` coupe silencieusement ses mentions, et le
  libellé ment — `CHAT_MENTION` (`models.py:69`) existe ; (c) la table `Notification` grossit sans
  borne (zéro `.delete()` repo-wide, `list()` renvoie tout) ; (d)
  `SAV_ACTIVITE_DUE`/`STOCK_EXPIRATION_SOON` sont déclarés jamais émis, et warranty/maintenance
  notifient les managers même quand un owner existe (`sweeps.py:104,146`). Fix : flag
  `respect_quiet_hours` (défaut on) différant les canaux hors-app non-critiques via le calendrier
  ouvré FG5 (in-app toujours immédiat) ; one-liner `CHAT_MENTION` (@coord VX85, même fonction) ;
  tâche Celery `purge_notifications_anciennes` (lues > 60 j supprimées, non-lues archivées,
  `list()` borné 90 j) ; étendre `sweep_daily` aux 2 events morts + routage owner-d'abord. Files :
  `apps/notifications/{models,services,selectors,sweeps,views}.py` + migration additive,
  `apps/records/views.py`, `NotificationsPreferences.jsx` (toggle). DoD : un `notify()`
  non-critique à 23 h ne part pas en email (in-app créé) ; une mention crée `chat_mention` ; une
  notif lue de 61 j est purgée ; un lot proche péremption émet `STOCK_EXPIRATION_SOON` ; tests.
  (T2 — L, sonnet) (@lane: backend/notify)

- [ ] VX210 — **[BACKEND additif] Le snooze devient un rappel actif, généralisé, et déclenché par (@lane: backend/notify — @after VX85)
  l'événement métier. @after VX85.** VX85 pose `snoozed_until` + exclusion passive sur
  `records.Activity` seulement — rien ne RÉVEILLE l'item ni ne re-notifie à l'échéance. Fix : (a)
  sweep Celery `reveiller_snoozes` — à échéance, l'item revient dans la file ET émet une
  `notify()` légère « ⏰ De retour : {titre} » ; (b) table générique `SnoozedItem` (content-type,
  pattern `ApprovalReminderState`) pour snoozer aussi une approbation/facture depuis la file ; (c)
  champ optionnel `snooze_trigger_event` (choix fermés : `client_reply:<lead>`,
  `devis_signed:<devis>`, `stock_arrive:<produit>`) abonné sur `core/events.py` — le premier de
  l'horloge ou de l'événement gagne ; le picker VX85 gagne 1-2 options contextuelles « jusqu'à… ».
  Files : `apps/records/{models,services}.py`, `apps/notifications/{models,sweeps}.py` +
  migrations, `ActivitiesPanel.jsx`, `MesActivitesPage.jsx`. DoD : un item snoozé « ce soir »
  réapparaît + notifie au sweep suivant ; un item « jusqu'à réponse client » revient dès la
  `LeadActivity` entrante même avant l'échéance ; snoozer une approbation la masque puis la
  ramène ; tests des 2 chemins de sortie. (T2/T3 — M/L, sonnet ; opus si le générique cross-source
  dérape) (@lane: backend/notify — @after VX85)

- [ ] VX211 — **« Ma file » par persona + départage « victoires rapides ». @after VX83.** VX83 (@lane: backend/notify — @after VX83)
  construit UNE union triée par urgence globale, identique pour tous — or
  commercial/comptable/technicien/directeur ont des priorités radicalement différentes. Fix
  frontend : `queueViewForRole(role)` (rôle déjà dans le store, `MesActivitesPage.jsx:66`) posant
  l'ORDRE des sections par défaut (commercial : relances → leads chauds → devis expirants ;
  comptable : factures échues → approbations ; terrain : interventions du jour ; direction :
  approbations → escalades), surcharge persistée `localStorage`, jamais un mur (« Tout voir »
  reste) ; + [BACKEND léger] champ `effort_estime` déterministe par `kind` sur `ma-file/` (table
  statique, pas de ML) alimentant un tri secondaire optionnel « Victoires rapides d'abord » —
  uniquement un DÉPARTAGE entre items d'urgence égale. Files :
  `frontend/src/features/queue/queueViews.js` (nouveau), `MesActivitesPage.jsx`,
  `apps/records/views.py` (serializer). DoD : un commercial voit Relances en tête, un comptable
  Factures échues ; à urgence égale l'item `faible` précède l'`eleve` quand l'option est active ;
  le tri par défaut reste inchangé sinon ; STAGES.py importé pour toute clé de stage. (T2 — M,
  sonnet) (@lane: backend/notify — @after VX83)

- [ ] VX212 — **[BACKEND additif léger] Transparence « pourquoi je reçois ça » + contexte (@lane: backend/notify — @after VX99/VX100)
  décisionnel dans l'email d'approbation. @after VX99/VX100.** `resolve_recipients`
  (`services.py:275`) applique des règles invisibles — des notifs « pourquoi moi ? » qu'on ne peut
  couper qu'en fouillant la grille des 42 événements ; et l'email de demande d'approbation
  n'embarque pas le montant/contexte. Fix : (a) `reason` court sur la ligne Notification
  (`'assigné à vous'|'manager'|'règle de routage'|'vous suivez'`), rendu sous chaque notif avec
  « Régler » → deep-link `/parametres/notifications#<event>` ; (b) enrichir le template email
  d'approbation avec montant + 1-2 lignes de contexte (déjà exposés par VX100 côté API) — jamais
  de bouton « Approuver » par lien email (pas de mutation non-authentifiée). Files :
  `apps/notifications/{models,services,serializers}.py` + migration, templates email
  notifications, `NotificationBell.jsx`, `NotificationsPreferences.jsx`. DoD : une notif montre sa
  raison et « Régler » ouvre la bonne ligne de préférence ; l'email d'approbation contient montant
  + résumé dans le corps (snapshot test). (T2 — M, sonnet) (@lane: backend/notify — @after
  VX99/VX100)

**Sous-groupe VXD-I (suite) — Handoffs cross-persona (la main gauche apprend ce que fait la
droite)**

- [x] VX213 — **[BACKEND] Notifier les handoffs AVAL : chantier créé, chantier réassigné,
  réquisition (2 bords), + SLA ballon-perdu. @after VX99.** Le motif systémique prouvé : l'amont
  (lead→vendeur, approbations compta) notifie, l'aval (exécution) est muet. (a)
  `create_installation_from_devis` (`installations/services.py:205`) assigne
  `technicien_responsable` avec ZÉRO `notify()` — le plus gros transfert de l'entreprise est
  silencieux ; (b) réassigner un chantier (`InstallationsPage.jsx:259`) ne notifie pas le nouveau
  technicien alors que `_notifier_reassignation` (`services.py:2296`) le fait déjà pour la
  replanification d'intervention ; (c) **rogné (grand-verdict) :** la notif de SOUMISSION d'une DA
  vers les approbateurs = VX99, ne pas la re-câbler — seul le bord RETOUR reste muet :
  `approuver`/`refuser` (`demande_achat.py:96/113`) ne notifient jamais le DEMANDEUR de la
  décision ; (d) aucun SLA sur une DA restée SOUMISE. Fix : notify idempotent à `created=True`
  (« Nouveau chantier assigné », lien `?installation=<id>`), diff pre/post sur
  `technicien_responsable`, notify du demandeur à la décision (motif si refus ; montant estimé
  client-safe, jamais dérivé de `prix_achat`), et `_sweep_da_soumise_stale` miroir de
  `_sweep_sav_breaching`. Files :
  `apps/installations/{services.py,receivers.py,views/demande_achat.py,views/installation.py}`,
  `apps/notifications/sweeps.py`, `apps/installations/selectors.py`. DoD : accepter un devis →
  notif dans la cloche de l'installateur (ré-accepter n'en recrée pas) ; réassigner → notif au
  nouveau ; décider une DA → le demandeur notifié ; une DA soumise > seuil relance les
  approbateurs ; tests des transitions. (T1 — M, sonnet) (@lane: backend/notify — @after VX99)

- [ ] VX214 — **[BACKEND additif] [RESHAPÉE — grand-verdict] Les kinds d'EXÉCUTION entrent dans (@lane: backend/notify — @after VX83)
  « Ma file » (jamais une 2ᵉ boîte). @after VX83.** `MesActivitesPage` n'agrège que
  `records.Activity` et `ApprobationsPage` que les approbations — un chantier assigné, une
  intervention à faire, une DA approuvée à commander, un ticket transféré n'apparaissent dans
  AUCUNE boîte. Fix (reshape imposé) : ne PAS créer d'endpoint `mes-affectations-entrantes/` ni de
  page `MesAffectationsPage` parallèles — étendre l'endpoint `ma-file/` de VX83 avec les kinds
  d'exécution (`chantier_assigne`, `intervention_du_jour`, `da_approuvee_a_commander`,
  `ticket_transfere`) via une fonction lecture-seule `selectors.affectations_pour(user)` par app
  cible (scopé company+user serveur), et laisser VX211 (vues par persona) ordonner ces sections —
  sinon l'ERP finit avec DEUX boîtes de réception concurrentes, l'anti-pattern que VX83 a été
  conçu pour tuer. Files : `apps/records/views.py` (l'action `ma-file/` de VX83),
  `apps/{installations,sav}/selectors.py` (une fonction chacun),
  `frontend/src/pages/activities/MesActivitesPage.jsx` (rendu des nouveaux kinds). DoD : un
  installateur ouvre Ma file et voit son chantier fraîchement assigné + interventions + tickets à
  côté de ses activités, triés urgence ; scoping company/user testé serveur ; aucun endpoint ni
  écran parallèle créé. (T3 — L, opus : agrégateur cross-app = jugement frontières) (@lane:
  backend/notify — @after VX83)

- [ ] VX215 — **Boucle de retour « pris en charge » : l'émetteur sait que le ballon est (@lane: backend/notify)
  attrapé.** Grep `accuser|prise en charge|acknowledge|seenBy` = 0 hit métier — le système est
  100 % push unidirectionnel. Fix frontend-first : version minimale = afficher l'état `read` déjà
  persisté de la notification liée là où l'action a été initiée (ex. « avis lu par le directeur »
  sur le devis après `contacterSuperieur`) ; version complète [BACKEND minime] = flag
  `acknowledged` + bouton « Je prends en charge » dans la cloche sur les notifs de handoff à fort
  enjeu, l'émetteur voyant « Pris en charge par X ». Files : `NotificationBell.jsx`,
  `pages/ventes/DevisList.jsx`, `api/notificationsApi.js`, `[BACKEND]` serializer léger exposant
  l'état de la notif liée. DoD : après « demander l'avis du supérieur », le vendeur voit passer
  « vu » quand le directeur ouvre la notif ; test de rendu. (T2 — M, sonnet ; S en version lecture
  seule) (@lane: backend/notify)

- [x] VX216 — **Rendre les seams VISIBLES des deux côtés : divergence devis↔chantier, ticket
  résolu par intervention, fil de responsabilité.** Trois lacunes de lecture jumelles : (a)
  `InstallationDetail.jsx:252-271` détecte `devisDivergent` (bom gelé ≠ devis actuel) côté
  installateur SEULEMENT ; (b) `sav/receivers.py` (YSERV2) avance le ticket à RESOLU quand
  l'intervention se termine, mais le ticket ne montre jamais QUELLE intervention l'a résolu
  (`TicketsPage.jsx:579` lie vers `/chantiers` générique) ; (c) personne ne voit la CHAÎNE de
  responsabilité du client quand il rappelle. Fix : badge « Chantier en cours (compo gelée) » +
  `toastWarning` à l'édition sur DevisList ; « Résolu par l'intervention #X du {date} par {tech} »
  avec lien profond sur le détail ticket ; mini-composant `<OwnerChain>` (avatars + rôle + étape)
  sur InstallationDetail et fiche client. Files : `DevisList.jsx`, `TicketsPage.jsx`,
  `components/OwnerChain.jsx` (nouveau), `InstallationDetail.jsx` ; `[BACKEND]` éventuels flags
  légers de serializer si un lien manque. DoD : éditer un devis lié à un chantier avec bom →
  avertissement ; ticket résolu par intervention → lien vers elle ; un chantier montre « Lead : A ·
  Devis : B · Chantier : C · SAV : D » cliquable ; tests de rendu. (T2 — M, sonnet) (@lane:
  backend/notify)

- [ ] VX217 — **La cloche finit le travail : aperçu sans naviguer, actions par entité, (@lane: backend/notify — @after VX208)
  bottom-sheet mobile. @after VX208.** Trois compléments du même organe : (a) chaque item de
  cloche/file est un cul-de-sac de navigation (`NotificationBell.jsx:272-275`, `goto(n.link)`) —
  traiter 8 relances = 8 allers-retours d'écran ; (b) les actions sont 100 % unitaires ; (c)
  `.nb-panel` (`NotificationBell.jsx:218`) est un panneau absolu desktop qui déborde sur mobile,
  sans safe-area, alors que `ResponsiveDialog` existe (VX89 l'adopte). Fix : `<AttentionPeek>`
  (popover survol desktop / tap-and-hold mobile : client, montant si pertinent — jamais
  `prix_achat` —, échéance, dernière action, bouton « Ouvrir ») rendu depuis les données déjà dans
  la notif ; une fois le regroupement par entité de VX208 posé, actions de groupe « Tout marquer
  lu » / « Reporter le lot » (boucle sur les mutations unitaires + `toastWithUndo` global, aucune
  mutation serveur nouvelle) ; sur breakpoint mobile la cloche s'ouvre en bottom-sheet
  (`env(safe-area-inset-bottom)`, desktop inchangé). Files :
  `frontend/src/features/queue/AttentionPeek.jsx` (nouveau), `NotificationBell.jsx`,
  `MesActivitesPage.jsx`, `index.css` (`.nb-panel` responsive). DoD : survoler une relance montre
  son aperçu sans changer d'URL ; 3 notifs même entité → « Tout marquer lu » en un clic avec
  undo ; sur WebKit mobile (projet VX68) la cloche respecte l'encoche ; `prix_achat` jamais rendu ;
  e2e verts. (T2 — M, sonnet) (@lane: backend/notify — @after VX208)

- [x] VX218 — **Le handoff se voit aussi CÔTÉ RÉCEPTION et DANS LE TEMPS : « Nouveau pour moi » +
  état d'escalade lisible.** Deux trous jumeaux de VX213/VX215 : (a)
  `InstallationsPage.jsx:40` a un filtre `mine=only` mais rien ne distingue un chantier
  NOUVELLEMENT confié d'un ancien ; (b) `APPROVAL_ESCALATED`/`APPROVAL_REMINDER` (YEVNT9)
  notifient, mais le DEMANDEUR ne voit nulle part un état persistant « votre demande a été
  escaladée à N+2, relancée le … » sur sa propre vue. Fix : badge « Nouveau » sur les chantiers
  assignés à l'utilisateur depuis sa dernière visite (timestamp `lastSeenChantiers` en
  localStorage via le helper défensif `safeStorage` — VX170, @coord) + raccourci de filtre « Mes
  nouveaux chantiers » ; colonne/ligne état d'escalade (niveau + dernière relance) côté demandeur
  dans `ApprobationsPage`, [BACKEND léger] exposer le niveau dans
  `reporting/approbations.py` si absent. Files : `pages/installations/InstallationsPage.jsx`,
  `pages/approbations/ApprobationsPage.jsx`, `apps/reporting/approbations.py`. DoD : un chantier
  assigné après ma dernière visite affiche « Nouveau », ouvrir l'écran l'efface ; une approbation
  escaladée montre son niveau au demandeur ; tests. (T2 — S/M, sonnet) (@lane: backend/notify)

**Sous-groupe VXD-K — Le commercial : chaque job compté en clics**

- [ ] VX219 — **« Mes chiffres » : le vendeur `normal` voit ENFIN sa propre performance. @coord (@lane: frontend/crm — @coord VX27)
  VX27.** Défaut prouvé : `/reporting` ET `/reporting/commercial` sont gatés
  `roleLoader(['responsable','admin'])` (`router/index.jsx:319,322`) ; `Dashboard.jsx` est
  company-wide ; le seul KPI perso (FG39, `CrmInsightsPanel`) n'est rendu QUE dans
  `ChartsView.jsx:288` (l'onglet graphique des leads, ouvert 1×/semaine). Fix frontend-first :
  carte « Mes chiffres » en tête de `Dashboard.jsx`, tous rôles — devis envoyés/acceptés du mois,
  taux de signature, CA signé, atteinte d'objectif (réutiliser `crmApi.getObjectifsAttainment`
  FG39 déjà livré) + 3 leads chauds à traiter ; dériver des slices déjà chargés filtrés
  `owner===me` côté client ; [BACKEND additif] `?owner=me` seulement si la justesse l'exige ; ne
  JAMAIS dé-gater `/reporting/commercial` (reste l'outil manager). Files :
  `frontend/src/pages/Dashboard.jsx`, `CrmInsightsPanel.jsx` (extraire la carte en composant),
  éventuellement `apps/crm/selectors.py`. DoD : un `normal` ouvre `/dashboard` et voit SES
  métriques (test : la carte n'agrège que `owner==user`) ; le gate manager inchangé. (T2 — M,
  sonnet) (@lane: frontend/crm — @coord VX27)

- [ ] VX220 — **⌘K atterrit sur le RECORD (pas la liste) + créations au clavier. @after VX79, (@lane: frontend/crm — @after VX79)
  @coord NTUX9/10.** Défaut prouvé : `CommandPalette.jsx:24-33` route
  `devis/client/facture/chantier/equipement/ticket` vers leur LISTE — seul `lead` ouvre la fiche.
  Et `shortcuts.js` = 8 `g x` de nav, 0 action « créer » (`commandActions.js:13`). Fix : (a)
  réutiliser la convention de deep-link `?id=` de VX79 dans le mapping `ROUTE` de la palette, et
  étendre la lecture du param à `FactureList.jsx`/`ClientList.jsx` — une seule convention de
  param, jamais deux ; (b) 2-3 raccourcis `c l`/`c d`/`c c` (créer lead/devis/client) dans
  `shortcuts.js` + section « Créer » de la palette — périmètre réduit : NTUX possède le
  quick-create palette générique, ici SEULEMENT les raccourcis clavier directs et le câblage
  `?new=1`, @coord NTUX9/10 (vérifier-non-déjà-construit avant build) ; (c) vérifier
  l'exhaustivité `GOTO_SHORTCUTS` vs routes de premier niveau (`/planification`,
  `/approbations`). Files : `providers/CommandPalette.jsx`, `providers/shortcuts.js`,
  `commandActions.js`, lecteurs `?id=`/`?open=` des listes citées. DoD : chercher une référence
  dans ⌘K ouvre le record exact ; `c l` ouvre le form lead ; toute route de premier niveau a son
  `g x` ; tests du mapping. (T2 — M, sonnet) (@lane: frontend/crm — @after VX79)

- [x] VX221 — **Le score de lead dit enfin POURQUOI (tooltip de raisons + tri).** Défaut prouvé :
  `ListView.jsx:83-99` affiche `score`/100 nu ; `serializers.py:240` calcule `score_label` via
  `compute_score(obj)` mais aucune décomposition n'est exposée. Fix : [BACKEND additif léger]
  exposer `score_reasons` (liste `{facteur, points}`) depuis `apps/crm/scoring.py` (pure exposition
  des composantes déjà calculées, zéro recalcul) ; tooltip riche sur `ScoreBadge` (« +30 facture
  élevée · +20 récent · +15 canal web ») + badge score sur `LeadCard` (absent aujourd'hui) +
  colonne triable. Files : `apps/crm/{scoring,serializers}.py`,
  `frontend/src/pages/crm/leads/views/ListView.jsx`, `LeadCard.jsx`. DoD : survoler le badge
  montre les 2-3 facteurs dominants ; test serializer company-scopé. (T2 — S/M, sonnet) (@lane:
  frontend/crm)

- [x] VX222 — **« Relancer ce devis » : le pendant devis de la relance facture.** Défaut prouvé :
  `DevisList.jsx:736-741` calcule `expiringSoon` (envoyés expirant ≤7 j) et affiche un bandeau —
  mais AUCUNE action : la relance structurée n'existe QUE pour les factures (`RelancesPage`). Fix :
  bouton « 🔔 Relancer » sur les lignes `statut==='envoye'` qui rouvre le flux WhatsApp/email
  EXISTANT (`handleEnvoyer:410`, `openEmailModal:238`) avec un message « relance » (pas « envoi
  initial ») + consigne au chatter du devis (`DevisActivity`, cf. VX97) ; aperçu-puis-clic, jamais
  d'envoi auto (règle manuel-wa.me fondateur). Files : `frontend/src/pages/ventes/DevisList.jsx`.
  DoD : un devis envoyé propose « Relancer » → même modale en mode relance + entrée chatter ;
  l'action n'apparaît que sur `envoye` ; test. (T2 — S/M, sonnet) (@lane: frontend/ventes)

- [ ] VX223 — **[BACKEND léger] Actions de carte en 2 clics : « ✗ Perdu (motif) », file (@lane: frontend/crm — @after VX83)
  « Rappels demandés », « ⚡ indisponible » cliquable. @after VX83.** Trois gestes quotidiens
  enfermés dans la fiche : (a) marquer perdu = ouvrir la fiche → scroller → cocher « Perdu ? » +
  motif — ~5 interactions ; (b) `contact_preference==='phone_ok'` rend un badge passif « ☎ Rappel
  demandé » (`LeadCard.jsx:114-121`) — le signal le plus chaud n'alimente aucune file ; (c) le ⚡
  devis-auto désactivé cache sa raison dans un `title` sans action de correction. Fix : action
  « ✗ Perdu » dans le menu de ligne/carte → mini-popover motif (datalist `motifs-perte` déjà
  chargée) → PATCH `perdu`+`motif_perte` ; chip filtre « Rappels demandés » sur `FilterBar` (pur
  client) + famille `{kind:'rappel', urgency:'high'}` dans `ma-file/` via `crm/selectors.py`
  (@after VX83 — famille que VX83 n'énumère pas) ; le texte `factureManquante`
  (`LeadCard.jsx:209-216`) devient un bouton « → Renseigner la facture » qui ouvre la fiche ET
  focus le champ bloquant. Files : `LeadCard.jsx`, `views/ListView.jsx`, `FilterBar.jsx`,
  `LeadForm.jsx`, `apps/crm/selectors.py`. DoD : perdu + motif en 2 clics depuis une ligne (motif
  alimente le win/loss du CommercialDashboard) ; chip « Rappels demandés » liste les `phone_ok` ;
  cliquer « devis auto indisponible » ouvre la section énergie en édition ; tests. (T2 — M,
  sonnet) (@lane: frontend/crm — @after VX83)

- [ ] VX224 — **La session de qualification en rafale : ◀▶ prev/next, « créer un autre », (@lane: frontend/crm — @after VX89/VX92/VX93)
  « Mes leads » par défaut. @after VX89 (même fichier — rebase), VX92, VX93.** Trois
  multiplicateurs de la même session (20-40 leads/j) : (a) `LeadForm` reçoit UN lead — passer au
  suivant = fermer, re-viser la ligne, recliquer ; (b) VX92 câble « Créer un autre » sur
  ProduitForm/ClientForm/paiement mais PAS sur `LeadForm` ; (c) `LeadsPage` charge TOUS les leads
  de l'équipe, le filtre owner n'est jamais pré-réglé. Fix : passer à `LeadForm` la liste filtrée
  courante + index (déjà en mémoire, `filtered`), boutons ◀▶ + touches `J`/`K` façon Gmail (garde
  de saisie si dirty — @coord VXD-B/VX167) ; étendre le toggle VX92 à `LeadForm` (création seule :
  succès → reset + refocus Nom, défauts VX93 réappliqués) ; toggle « Mes leads » défaut ON pour le
  rôle `normal` (persisté `localStorage`, le manager bascule OFF). Files :
  `frontend/src/pages/crm/leads/LeadsPage.jsx`, `LeadForm.jsx`, `FilterBar.jsx`,
  `features/crm/stages.js`. DoD : `J`/`K` charge le lead voisin sans fermer (confirmation si
  dirty) ; toggle ON → créer vide le form et refocus Nom ; un `normal` ouvre `/crm/leads` sur SES
  leads ; tests. (T2 — M, sonnet) (@lane: frontend/crm — @after VX89/VX92/VX93)

**Sous-groupe VXD-L — Le technicien terrain**

- [ ] VX225 — **La raison de blocage de statut cesse d'être jetée à la poubelle (@lane: frontend/ios — @coord VX105)
  (InterventionsPage). @coord VX105.** Défaut prouvé : le backend calcule un message FR précis et
  actionnable — `transition_block_reason` (`field_services.py:405-423`, « Photos obligatoires
  manquantes avant "Terminée" : Toiture avant, Câblage. ») — mais `InterventionsPage.jsx:262-272`
  (`DetailSheet.setStatut`) fait `catch { toast.error('Impossible de changer le statut.') }` : le
  corps du 400 (`{statut:[raisons]}`) n'est JAMAIS lu. Le patron de rendu existe DÉJÀ un niveau
  au-dessus : `ChantierGateTimeline.jsx:54-58` affiche les `raisons[]` en `<ul>` inline. Fix : lire
  `err?.response?.data?.statut` et rendre la liste inline sous le Select de statut (patron
  GateTimeline), toast détaillé en repli. Files :
  `frontend/src/pages/installations/InterventionsPage.jsx` (`DetailSheet.setStatut`). DoD :
  forcer un 400 → le message exact du serveur s'affiche sous le sélecteur ; test. VX105 AJOUTE un
  contrôle de statut à MaJourneePage en affichant le 400 — ceci répare le DetailSheet EXISTANT
  d'InterventionsPage, l'autre moitié du même défaut. (T2 — S, sonnet) (@lane: frontend/ios —
  @coord VX105)

- [ ] VX226 — **« Ma journée » dit l'urgence et reste fraîche.** Deux défauts du même (@lane: frontend/ios)
  écran-pivot : (a) `priorite` existe, est ANNOTÉ et TRIÉ serveur (`views/intervention.py:129-144`)
  mais `MaJourneePage.jsx` ne le rend JAMAIS ; (b) `load()` n'est appelé qu'au montage (`:57`) —
  aucun bouton refresh, aucun `visibilitychange`, et le pull-to-refresh natif est coupé
  (`overscroll-behavior: contain`) : une réaffectation dispatch de 10 h est invisible jusqu'au
  rechargement manuel de l'onglet. Fix : puce `Badge tone="danger"/"warning"` quand
  `priorite==='urgente'/'haute'` ; bouton « Actualiser » discret (`RefreshCw`, cohérent
  `OfflineSyncIndicator`) + refetch throttlé sur `visibilitychange` (retour visible après ≥2 min —
  jamais un poll actif). Files : `frontend/src/pages/interventions/MaJourneePage.jsx`, vérif
  `apps/installations/serializers.py`. DoD : une intervention urgente porte une puce distincte du
  rang ; revenir sur l'onglet après 2 min déclenche un refetch silencieux ; tests. (T2 — S,
  sonnet) (@lane: frontend/ios)

- [x] VX227 — **Les coutures chantier↔intervention : pont Demande d'achat, photos reliées,
  séries dédoublonnées. @coord ARC26.** Trois seams du même chantier : (a) `DemandesAchatList.jsx`
  n'a aucun pré-remplissage `chantier` ; (b) deux systèmes de photos avant/pendant/après jamais
  reliés : `PhotosPanel` vs `ChantierPhotos` ; (c) deux captures de n° de série indépendantes : le
  garde-doublon de `ChantierChecklist.jsx:26-30` ne voit pas les séries saisies côté intervention
  et vice-versa. Fix : lien « Autre besoin non prévu → Nouvelle demande d'achat » dans
  `PreparationPanel` naviguant vers `/chantiers/demandes-achat?chantier={id}&intervention={id}` +
  lecture des query params dans `DemandesAchatList` ; liens croisés discrets « Voir aussi les
  photos du chantier / de cette intervention » (jamais de fusion de magasins — @coord ARC26
  politique magasin-unique) ; enrichir le `Set` de déduplication des séries par l'union des deux
  sources. Files : `DemandesAchatList.jsx`, `InterventionFieldExecution.jsx` (`PreparationPanel`,
  `PhotosPanel`), `pages/installations/{ChantierPhotos,ChantierChecklist}.jsx`,
  `InterventionCapturePanels.jsx` (`SerialsPanel`). DoD : depuis une intervention, un tap ouvre la
  DA avec le chantier pré-sélectionné ; chaque écran photo lie vers l'autre ; une série saisie
  côté F9 est détectée en doublon côté N9 et réciproquement ; tests. (T2 — M, sonnet) (@lane:
  frontend/ios — @coord ARC26)

**Sous-groupe VXD-M — Le comptable : le mois compté en clics**

- [x] VX228 — **Le rapprochement bancaire ligne-à-ligne : le contrat d'interaction complet. (@lane: frontend/compta)
  @coord FE-rapprochement-detail (cette seed EST sa spécification d'interaction — une seule
  tâche, jamais deux).** Défaut prouvé : `comptaApi.rapprochements.{lignesGl,resume,
  ajouterLigneReleve,pointer}` (`comptaApi.js:180-186`) n'ont AUCUN consommateur réel —
  `RapprochementsPage.jsx` n'offre que `SuggestionsDialog` (lot) et `cloturer` : une ligne non
  suggérée est IMPOSSIBLE à apparier, et rien ne dit si le mois est bouclé. Fix :
  `RapprochementDetailDialog` à 2 volets côte à côte (relevé | grand-livre), ligne relevé
  cliquable → candidates GL pré-filtrées montant/date (`lignesGl`) → « Pointer » (`pointer`),
  bandeau `resume()` en tête (solde relevé / pointé / écart restant, même langage visuel que
  l'équilibre d'`EcrituresPage.jsx:170-181`) qui décroît EN DIRECT à chaque pointage ;
  « Suggestions » devient une action DE ce dialog. Files :
  `frontend/src/features/compta/pages/RapprochementsPage.jsx` (nouveau
  `RapprochementDetailDialog`), consomme les 4 méthodes API déjà écrites. DoD : ouvrir un
  rapprochement en cours montre l'écart ; pointer une ligne le réduit en direct ; écart 0 →
  clôturable ; test du flux pointer→resume. (T2 — L, sonnet ; opus si scores de confiance à
  rendre) (@lane: frontend/compta)

- [x] VX229 — **`CrudDialog` apprend le Combobox : fin des champs FK « (ID) » tapés à la main.** (@lane: frontend/compta)
  Défaut prouvé : `CrudDialog.jsx:76-96` (la plomberie CRUD des 8 écrans compta) ne rend que
  `<Input>` ou `<select>` statique — résultat : `NotesDeFraisPage.jsx:104/110/123` (« Employé
  (ID) » ×3), `RapprochementsPage.jsx:285` (« Compte de contrepartie (ID) »), et PIRE,
  `EngagementsPage.jsx:75-82/148-155` capture `tiers_nom`/`marche_ref` en TEXTE LIBRE — une
  retenue de garantie part désynchronisée du référentiel tiers dès sa création. Le bon patron
  existe DANS LE MÊME module : `EcrituresPage.jsx:35-40` (`Combobox` + `comptesOpts`). Fix : type
  de champ `{name, label, async: () => Promise<{value,label}[]>}` dans le schéma `CrudDialog`
  (options chargées au montage, memoïsées) ; migrer les 2 champs ID et les champs texte libre
  d'Engagements vers un `tiers_id` réel (`tiers_nom` dérivé lecture seule). Files :
  `features/compta/components/CrudDialog.jsx`, `NotesDeFraisPage.jsx`,
  `RapprochementsPage.jsx`, `EngagementsPage.jsx`. DoD : créer une note de frais montre un
  Combobox « Nom Prénom » ; une retenue de garantie référence un tiers réel traçable vers sa
  fiche ; test de rendu du nouveau type. (T2 — M, sonnet) (@lane: frontend/compta)

- [x] VX230 — **Encaisser LÀ où on chasse l'impayé + total « reste à encaisser » visible. @after
  VX92/VX93 (même dialog — rebase).** Deux moitiés du même job : (a) `RelancesPage.jsx` n'a AUCUNE
  action « Enregistrer un paiement » — le chèque décroché après relance force à quitter, rouvrir
  Factures, re-chercher la même facture ; (b) `FactureList` montre « Encaissé ce mois » mais
  JAMAIS le total dû de la sélection filtrée courante (onglet « Partiellement payées »). Fix :
  extraire la modale paiement de `FactureList.jsx:676-752` en `PaiementDialog` partagé
  (props facture/onSaved) monté depuis les 2 pages + bouton « Encaisser » à côté de « Relancer » ;
  carte « Reste à encaisser (onglet) » calculée sur `filtered` (déjà en mémoire, zéro appel
  réseau). Files : `frontend/src/pages/ventes/PaiementDialog.jsx` (extrait), `FactureList.jsx`,
  `RelancesPage.jsx`. DoD : depuis Relances, « Encaisser » ouvre la même modale et retire la
  ligne des impayés ; l'onglet « Partiellement payées » affiche son total dû ; non-régression du
  flux FactureList. (T2 — M, sonnet) (@lane: frontend/compta — @after VX92/VX93)

- [x] VX231 — **La navigation finance atterrit sur la CIBLE : `?facture=`, lien client, onglet
  persistant, TVA↔Grand-livre. @coord VX79, VX113 (sélecteur d'exercice, même fichier —
  rebase).** Quatre liens cassés du même mois comptable : (a) `PaiementsPage.jsx:127` émet
  `to="/ventes/factures?facture={id}"` mais `FactureList.jsx` n'a AUCUN `useSearchParams` ; (b)
  `client_nom` (`PaiementsPage.jsx:133`) est du texte brut ; (c) AUCUNE des 7 pages compta à
  onglets ne persiste son onglet ; (d) vérifier une déclaration TVA contre le GL = 2 écrans, 2
  chiffres notés à la main. Fix : lire `?facture=` au montage de FactureList (basculer d'onglet
  si besoin, scroll + surbrillance 2-3 s) ; `client_nom` cliquable + filtre `?client=` local sur
  PaiementsPage ; hook partagé `useTabParam(defaultTab)` synchronisant le `Segmented` avec
  `?onglet=` (7 adoptions d'une ligne) ; action « Comparer au Grand-livre » sur une déclaration
  TVA → `EtatsPage` `?etat=grand-livre&date_debut=…&date_fin=…`. Files : `FactureList.jsx`,
  `PaiementsPage.jsx`, `features/compta/components/useTabParam.js` (nouveau) + les 7 pages,
  `FiscalitePage.jsx`, `EtatsPage.jsx`. DoD : cliquer une facture depuis Encaissements atterrit
  sur la ligne surlignée ; recharger restaure l'onglet ; « Comparer au GL » ouvre le grand-livre
  pré-filtré ; tests MemoryRouter. (T2 — M, sonnet) (@lane: frontend/compta — @coord VX79/VX113)

- [x] VX232 — **Les états financiers deviennent LISIBLES : noms réels, tableaux exploitables, (@lane: frontend/compta)
  exports hiérarchisés et traduits.** Quatre défauts de lisibilité du même module : (a) le KPI n°1
  du Cockpit affiche `Tiers #42` (`CockpitPage.jsx:101-104`) ; (b) les états CGNC
  (`EtatsPage.jsx:55-96`, `GenericTable`) sont des `<table>` HTML nus ; (c) les 6 boutons d'export
  fiscaux ont le même poids visuel — routine mensuelle mélangée à l'annuel ; (d) « FEC »/
  « liasse »/« IS » sans un mot d'aide. Fix : résoudre `tiers_id` en nom réel ([BACKEND additif]
  enrichir le selector serveur `top_encours_clients[].tiers_nom`, fallback « Tiers #N » si
  supprimé) ; migrer `GenericTable` vers le `Table` partagé (garder `KeyValue` pour les
  scalaires) ; grouper les exports en 2 rangées sous-titrées « Mensuel » / « Annuel — exercice
  requis » ; sous-libellé gris d'une phrase par export. Files :
  `features/compta/pages/{CockpitPage,EtatsPage,FiscalitePage}.jsx`, `apps/compta/selectors.py`
  [BACKEND]. DoD : le graphique montre des noms de clients ; une balance rendue trie au clic ;
  les 2 groupes d'exports sont distincts et chaque bouton porte sa phrase d'aide ; exports
  serveur inchangés ; tests de rendu. (T2 — M, sonnet) (@lane: frontend/compta)

**Sous-groupe VXD-N — Le directeur/admin : contrôle et supervision**

- [ ] VX233 — **[BACKEND 1 ligne] Le journal des paramètres montre TOUTES ses sections + la (@lane: frontend/brand)
  tarification a son historique.** Défaut prouvé : `SettingsAuditLog` journalise déjà 6+ sections
  côté serveur et l'endpoint `settings_audit_sections` (`views_audit.py:53-68`) EXISTE — mais
  `parametresApi.js` ne l'expose pas et le seul consommateur (`AvanceSection.jsx:304-307`)
  hardcode un `<Select>` à 2 options (`profil`, `messages`). Fix : ajouter `'tarification'` à
  `KNOWN_AUDIT_SECTIONS` ; exposer `parametresApi.getAuditSections()` et construire le `<Select>`
  dynamiquement ; extraire le feed en `SettingsAuditFeed` paramétrable par section, lien « Voir
  l'historique » sur TarificationSection. Files : `apps/parametres/views_audit.py`,
  `frontend/src/api/parametresApi.js`, `pages/parametres/{AvanceSection,TarificationSection,
  SettingsAuditFeed}.jsx`. DoD : le filtre propose ≥6 sections réelles ; changer le barème ONEE
  puis filtrer `tarification` montre qui/quand/ancien→nouveau ; « Voir l'historique » depuis
  Tarification affiche sa section seule ; tests. (T2 — M, sonnet) (@lane: frontend/brand)

- [x] VX234 — **[BACKEND] L'audit des rôles au grain de la PERMISSION + garde de
  réassignation.** Deux trous du même écran de pouvoir : (a) `roles/views.py:64-74` stocke
  `"{nom} ({N} permissions)"` — retirer `crm_supprimer` et ajouter `ventes_export` (net zéro)
  produit un journal illisible ; (b) le dialogue de réassignation avant suppression
  (`RolesManagement.jsx:583-629`) liste TOUS les rôles sans tri ni annotation — réassigner 5
  commerciaux vers « Administrateur » d'un clic hâtif leur donne tous les droits sans
  avertissement. Fix : stocker le diff structuré (`permissions_ajoutees`/`retirees` par
  set-difference dans `old_value`/`new_value` JSON existants) ; rendu frontend en badges +/-
  (le `fmtVal` d'`AvanceSection:48-49` détecte un tableau au lieu de JSON.stringify brut) ; trier
  le `<Select>` de réassignation par nombre de permissions croissant + badge « ⚠ plus large »
  quand la cible dépasse l'original. Files : `apps/roles/views.py`,
  `pages/parametres/AvanceSection.jsx`, `pages/admin/RolesManagement.jsx`. DoD : un échange
  net-neutre de permissions journalise les 2 codes exacts ; le sélecteur annote les rôles plus
  larges ; tests. (T2 — M, sonnet) (@lane: backend/auth)

- [ ] VX235 — **[BACKEND] Gardes-fous du pouvoir admin : motif par item en bulk-refus, cycle de (@lane: backend/auth)
  hiérarchie, import-écraser confirmé, dernier admin protégé en masse. Noter AUTH au DONE LOG.**
  Quatre trous d'intégrité prouvés : (a) `ApprobationsPage.deciderEnMasse` (:106-131) applique UN
  `window.prompt` de motif à N demandes HÉTÉROGÈNES (VX19 remplacera le prompt mais pas la
  sémantique « un motif menteur pour tous ») ; (b) `validate_supervisor`
  (`authentication/serializers.py:226-228`) ne bloque que l'auto-supervision — un cycle A→B→C→A
  corrompt silencieusement `records_scope_sous_arbre` ; (c) `ExportSauvegarde.importConfig`
  (:41-56) exécute `config-import/?mode=overwrite` au choix de fichier, gardé par une case à
  cocher HTML native — zéro `AlertDialog`, zéro aperçu des 6 catégories écrasées ; (d)
  `UsersManagement.bulkActions` (:310-321) « Désactiver » ne vérifie jamais `isLastAdmin`. Fix :
  `ResponsiveDialog` de refus listant chaque item avec motif PROPRE (motif commun optionnel
  « appliquer à tous », modifiable par ligne) ; [BACKEND] remonter la chaîne de superviseurs
  (borne 20 sauts) et rejeter le cycle avec message clair + filtrer les descendants du `<select>`
  d'EquipeSection ; `AlertDialog destructive` récapitulant les catégories du bundle AVANT le
  POST ; exclure de la désactivation groupée le(s) compte(s) gardant au moins un admin actif +
  toast des comptes sautés. Files : `pages/approbations/ApprobationsPage.jsx`,
  `authentication/serializers.py`, `pages/parametres/{EquipeSection,ExportSauvegarde}.jsx`,
  `pages/admin/UsersManagement.jsx`. DoD : refus en lot = motif distinct par ligne possible ;
  cycle à 3 nœuds → 400 clair ; import-écraser demande confirmation listée ; désactivation
  groupée laisse ≥1 admin actif ; tests des 4 gardes. (T2 — L, opus : auth/hiérarchie) (@lane:
  backend/auth)

- [ ] VX236 — **Fin des culs-de-sac de pilotage : équipes cliquables, Journal deep-linké, seuils (@lane: frontend/brand — @after VX79)
  avec retour. @after VX220 (Journal — la palette ⌘K de VX79 ne liste PAS Journal.jsx dans ses
  Files).** Quatre écrans de supervision qui montrent sans jamais mener : (a)
  `MesEquipesCard.jsx` (monté `Dashboard.jsx:662` — vu par CHAQUE directeur à chaque connexion) :
  zéro lien sur pipeline/retards/CA ; (b) `Journal.jsx` `MODEL_ROUTES` (:50-64) pointe vers des
  LISTES nues ; (c) `KpiAlertesPage.jsx` affiche `derniere_valeur` sans lier vers la source ; (d)
  `MonitoringSection.jsx` (:80-92) règle le seuil de sous-perf à l'aveugle, sans aperçu du nombre
  de systèmes signalés. Fix : `<Link>` sur chaque métrique d'équipe
  (`/crm/leads?equipe=`, `/activites?equipe=`, `/ventes/devis?statut=accepte&equipe=`) ;
  `MODEL_ROUTES` en fonctions `(objectId) => path` (`?lead=` marche dès aujourd'hui,
  devis/chantier/ticket s'activent avec VX79) ; mapper `kpi → route` sur KpiAlertes ; [BACKEND
  additif] `GET /parametres/monitoring/apercu/?seuil=N` affiché au blur du champ. Files :
  `components/MesEquipesCard.jsx`, `pages/Journal.jsx`,
  `pages/parametres/{KpiAlertesPage,MonitoringSection}.jsx`, endpoint léger `apps/parametres` ou
  `apps/sav`. DoD : chaque chiffre d'équipe ouvre la liste filtrée ; cliquer un objet « lead » du
  Journal ouvre CE lead ; la valeur d'une alerte DSO ouvre la balance âgée ; changer le seuil
  affiche « N systèmes seraient signalés » avant sauvegarde ; tests. (T2 — M, sonnet) (@lane:
  frontend/brand — @after VX79)

**Sous-groupe VXD-O — La vélocité de saisie**

- [ ] VX237 — **Collage intelligent : le presse-papiers du monde réel entre proprement.** Défaut (@lane: frontend/crm)
  prouvé : 0 `onPaste` dans tout le frontend — un numéro WhatsApp collé, un montant Excel, une
  carte de visite texte tombent bruts dans l'`<input>`. Le « paste-grid Excel » multi-cellules
  reste DIFFÉRÉ (dedup-map) — ceci est le collage UNITAIRE, jamais proposé ni rejeté. Fix : hook
  partagé `usePasteClean(parser)` posé en `onPaste` sur les champs téléphone (parse via
  `canonicalPhoneMA`/`normalizeMaPhone` déjà écrits, `lib/format.js:132,154`), montant (strip
  espaces/virgules/« DH »), et un mode carte-WhatsApp sur le Nom de
  `LeadExpressModal`/`LeadForm` (motif `Nom … Tel …` → bouton « Répartir » après collage,
  confirmation, jamais silencieux). Zéro dépendance, regex pures. Files :
  `frontend/src/hooks/usePasteClean.js` (nouveau), poses sur `LeadForm.jsx`,
  `LeadExpressModal.jsx`, `ClientForm.jsx`, `ClientQuickCreateModal.jsx`, champs montant
  `DevisGenerator.jsx`/`FactureForm.jsx`. DoD : coller `+212 6-12.34.56.78` stocke la forme
  canonique ; coller « 12 500,00 » donne `12500` ; test du parseur sur 8 formats réels. (T2 — M,
  sonnet) (@lane: frontend/crm)

- [ ] VX238 — **Primitives « mains rapides » : Segmented au clavier, Tab-qui-choisit, focus (@lane: frontend/ventes — @after VX90/VX91)
  post-sélection. @after VX90/VX91.** Trois défauts de primitives partagées : (a)
  `ui/Segmented.jsx` (57 fichiers consommateurs) déclare `role="radiogroup"` mais n'implémente
  AUCUNE navigation flèches ; (b) `ProduitPicker.jsx:89-101`/`Combobox.jsx:97-110` gèrent
  flèches/Enter/Escape mais pas Tab — Tab blur à vide ; (c) `ProduitPicker.pick()` (:84-87) rend
  le focus au bouton déclencheur — encore un Tab avant de taper la quantité. Fix : roving
  tabindex + `ArrowLeft/Right/Home/End` sur le conteneur radiogroup ; `Tab` (sans shift) =
  `pick(cursor)` sans `preventDefault` ; callback `onPicked` → `.focus()` sur l'input Qté de la
  même ligne (réutilise le `data-line-key` de VX90). Files : `ui/Segmented.jsx`,
  `ui/Combobox.jsx`, `components/ProduitPicker.jsx`, `DevisGenerator.jsx`/`DevisForm.jsx`/
  `FactureForm.jsx`. DoD : Tab arrive UNE fois sur le groupe, flèches changent la sélection ;
  taper une recherche puis Tab sélectionne ET avance ; choisir un produit focus la Qté de LA
  ligne ; tests `document.activeElement`. (T2 — M, sonnet) (@lane: frontend/ventes — @after
  VX90/VX91)

- [ ] VX239 — **Doublons : prévenir à la création CLIENT + le geste de FUSION. @coord F-E5.** (@lane: frontend/crm)
  Deux moitiés manquantes du même système : (a) `crmApi.checkDuplicates` n'est câblé que sur
  `LeadForm.jsx:330-346` — `ClientForm`/`ClientQuickCreateModal` n'ont que l'autocomplete NOM ;
  et le formatage téléphone (`canonicalPhoneMA`) n'est consommé que par UN champ ; (b) la
  DÉTECTION backend existe (`apps/crm/tests_doublons.py`, `services.py`) mais aucun composant
  frontend `merge/fusion` trouvé — VÉRIFIER-D'ABORD, puis dialogue de fusion 2 colonnes (garder
  A/garder B par champ, JAMAIS perdre le chatter). Fix : extraire
  `useDuplicateCheck(phone, email, {exclude})` de LeadForm, poser sur ClientForm +
  ClientQuickCreateModal ; extraire `<PhoneHint>` de ClientForm, poser sur
  LeadForm/LeadExpressModal ; geste de fusion en second temps. Files :
  `hooks/useDuplicateCheck.js` + `components/PhoneHint.jsx` (extraits), `ClientForm.jsx`,
  `ClientQuickCreateModal.jsx`, `LeadForm.jsx`, `LeadExpressModal.jsx`, `apps/crm/services.py` +
  `LeadMergeDialog.jsx`/`ClientMergeDialog.jsx` (si confirmé manquant). DoD : créer un client
  avec un téléphone connu avertit AVANT soumission ; taper un numéro dans LeadForm affiche la
  forme normalisée ; fusionner 2 doublons préserve les deux chatters + redirige les documents.
  (T2 — M, sonnet ; opus si fusion cross-app) (@lane: frontend/crm)

- [ ] VX240 — **Parité mécanique des formulaires : autofocus, mémoire des défauts, (@lane: frontend/ventes — @after VX90)
  multi-fichiers, focus de ligne achats. @after VX90, @coord VX92/VX93.** Sept incohérences
  prouvées entre formulaires jumeaux : (a) `FactureForm.jsx:293-307`/`DevisForm.jsx:231-245`
  s'ouvrent SANS aucun autofocus ; (b) `ProduitForm.jsx:413-416` Nom sans autofocus ; (c) dialog
  paiement : `pay-montant` sans autofocus + `payReference` sans mémoire ; (d) création ticket
  SAV (`TicketsPage.jsx:1092-1150`) : zéro autofocus + `type` reset à `'correctif'` ; (e)
  `LeadExpressModal.jsx:35` reset `canal='walk_in'` en dur ; (f) `AttachmentsPanel.jsx:85` fait
  `upload(files[0])` sans passer `multiple` à `FileUpload` (qui le supporte) — 5 photos = 5
  cycles complets ; (g) `BonsCommandeFournisseur.jsx:260-268` n'avance jamais le focus à l'ajout
  de ligne. Fix : chaque dialog nommé focus son premier champ utile ; type ticket/canal
  express/payMode mémorisés (localStorage, modifiables) ; itérer séquentiellement les fichiers
  avec « i/N », échec partiel n'annule pas les autres ; répliquer le patch VX90
  (`data-line-key` + `pendingFocusKey`) côté achats. Files : `FactureForm.jsx`, `DevisForm.jsx`,
  `ProduitForm.jsx`, `FactureList.jsx`, `pages/sav/TicketsPage.jsx`, `LeadExpressModal.jsx`,
  `components/AttachmentsPanel.jsx`, `pages/stock/BonsCommandeFournisseur.jsx`. DoD : chaque
  dialog nommé focus son premier champ utile à l'ouverture ; type ticket/canal express/payMode
  mémorisés ; 5 fichiers s'uploadent en une sélection ; « Ajouter ligne » BCF focus la nouvelle
  ligne ; tests de rendu. (T2 — M, haiku ; revue sonnet) (@lane: frontend/ventes — @after VX90)

**Sous-groupe VXD-P — Forgiveness / historique / confiance**

- [ ] VX241 — **[BACKEND] Le journal d'audit dit VRAI : cascade KB avouée, destroys (@lane: backend/auth)
  gardés+journalisés, Timesheet tracé, diffs automatiques.** Quatre défauts prouvés du même
  système : (a) `KbArticle.parent` est `on_delete=CASCADE` (`apps/kb/models.py:87-89`) et le
  confirm (`KbPage.jsx:104-105`) ment par omission — supprimer un parent détruit tout le
  sous-arbre sans le dire ; (b) 23 `destroy()` recensés : `KitOutillage`/`Litige` (dossier légal)
  n'ont AUCUN override, et les 7 modèles gardés « en usage »
  (LeadTag/MotifPerte/Canal/ChecklistTemplate/ChecklistEtape/SafetyChecklistSlot/StageModele)
  n'écrivent AUCUNE ligne `AuditLog` — `TRACKED_MODELS` (`audit/signals.py:18-58`, 31 modèles) ne
  liste aucun d'eux, ni `Timesheet` (`gestion_projet/views.py:2136`) ; (c) le paramètre
  `changes=` (diff structuré alimentant `reconstruct_as_of` YHARD3) n'est peuplé qu'à 2
  call-sites dans tout le backend. Fix : confirm KB avec le compte réel de descendants (pattern
  `ForceDeleteModal`) + `('kb','KbArticle')` et `('gestion_projet','Timesheet')` dans
  `TRACKED_MODELS` ; mixin réutilisable `UsageGuardedDestroyMixin` (usage_count + message FR +
  ligne AuditLog via `recorder.record()` en UN endroit) appliqué aux 7 gardés + gardes neufs
  Kit/Litige ; snapshot complet du row dans `_on_pre_save` → diff automatique `changes=` pour
  chaque UPDATE tracé. Files : `frontend/src/features/kb/KbPage.jsx`, `apps/kb/views.py`
  (annotation compte), `apps/audit/signals.py`, `apps/core/destroy_mixins.py` (nouveau),
  `apps/{crm,installations,outillage,litiges}/views*.py`. DoD : supprimer un parent KB affiche le
  vrai compte + écrit une ligne DELETE visible au Journal ; supprimer un Kit utilisé → 409 FR ;
  supprimer un Timesheet trace ; éditer `total_ttc` d'un devis écrit `changes=[{field,old,new}]`
  sans toucher une seule vue ; tests YHARD3 verts. (T2/T3 — L, sonnet ; opus si l'import-linter
  core bronche sur le mixin) (@lane: backend/auth)

- [x] VX242 — **[BACKEND+AUTH — noter au DONE LOG] Sécurité de session digne de confiance : le
  changement de mot de passe révoque, le secret 2FA ne fuit plus.** Deux trous dans une feature
  par ailleurs finie (N96, hors périmètre VX/NT) : (a) `ChangePasswordView.post()`
  (`authentication/views.py:855-904`) ne touche jamais `UserSession`/blacklist — après
  compromission, l'attaquant garde son refresh 7 j alors que TOUTE la machinerie de révocation
  existe (`SessionRevokeView`, `_blacklist_refresh_jti`, :823-851), juste jamais invoquée depuis
  ce chemin ; (b) `SecuriteCompteSection.jsx:363` rend le QR d'enrôlement 2FA via
  `api.qrserver.com` — le SECRET TOTP brut part en clair. *(Note : (b) est la MÊME faille que
  VX120 en tête de document — ne pas la reconstruire deux fois, ce seed la référence pour le
  contexte de la révocation de session (a) qui l'accompagnait dans le rapport source.)* Fix :
  révoquer toutes les sessions SAUF la courante après `user.save()` (boucle sur la logique
  SessionRevoke existante), réponse `sessions_revoked: N` + message « … {N} autre(s) session(s)
  déconnectée(s) » ; pour (b) voir VX120. Files : `authentication/views.py`
  (`ChangePasswordView`). DoD : changer le mot de passe avec 2 autres sessions actives blackliste
  leurs refresh (test à 2 logins). (T1 — S/M, sonnet — noter AUTH au DONE LOG) (@lane:
  backend/auth)

- [ ] VX243 — **[BACKEND] La confiance au niveau du DOSSIER : « archivé par X », historique de (@lane: backend/auth — @after VX98)
  MON enregistrement, garde d'édition périmée. @after VX98 (réutilise `updated_by`/`updated_at` —
  ne jamais dupliquer le champ).** Trois lectures de confiance au grain du record : (a)
  `Lead.archived_by`/`archived_at` sont capturés serveur (`crm/models.py:602-608`) et JAMAIS
  rendus (0 hit frontend) ; (b) le Journal est gaté `can_view_activity_log` tout-ou-rien
  (`audit/views.py:32-41`) : un commercial ne peut pas voir qui a modifié SON propre lead sans
  recevoir la visibilité sur TOUTE la boîte — ajouter un chemin de lecture record-scopé ; (c)
  aucune détection d'édition périmée au moment du SAVE (le verrou 409 backend reste territoire
  YDATA ; VX98(b) = puce passive à la LECTURE) — hook `useStaleGuard` : au submit, re-GET léger de
  `updated_at`, si différent de la valeur d'ouverture → bannière non bloquante « Modifié par {X}
  pendant votre édition — vérifiez avant d'enregistrer » avec choix revoir/forcer. Files :
  `pages/crm/leads/views/ListView.jsx` + `apps/crm/serializers.py` (exposer archived_by/at si
  absents — additif), `apps/audit/views.py` (action de lecture scopée objet),
  `hooks/useStaleGuard.js` (nouveau) câblé sur Lead/Devis/Facture. DoD : une ligne archivée
  montre « Archivé par X le … » ; un commercial sans permission Journal voit l'historique de SON
  lead et rien d'autre (test des 2 bornes) ; éditer dans 2 onglets → le 2ᵉ save affiche la
  bannière AVANT le PATCH ; tests. (T2 — M, sonnet ; revue attentive de la borne de permission)
  (@lane: backend/auth — @after VX98)

- [ ] VX244 — **Le poids de la confirmation devient proportionné au dégât : primitive (@lane: frontend/data — @coord VX19/VX95/VX96)
  `ConfirmDialog` à sévérité. @coord VX19, VX95/96.** Défaut prouvé : 68 `window.confirm` dans 44
  fichiers, UNE seule gravité — supprimer un litige client (dossier légal), un article KB avec
  sous-arbre, un secret webhook et un preset UI passent par le même dialog natif ; le repo SAIT
  faire mieux (le `ForceDeleteModal` typé de `StockList.jsx:507-560`, le « maison, jamais
  window.confirm » d'`UsersManagement.jsx:189`) sans jamais l'avoir généralisé. Fix : primitive
  `ui/ConfirmDialog.jsx` (vérifier-d'abord qu'elle n'existe pas sous un autre nom) avec prop
  `severity` (`low/medium/high`) pilotant couleur + confirmation tapée ; sémantique clavier
  délibérée (Escape annule TOUJOURS ; Entrée ne confirme JAMAIS un destructif `high`) ; migrer les
  ~10 sites au plus fort blast-radius (litiges, webhook-secret, templates checklist/safety,
  KB-avec-enfants de VX241, bulk ≥5 leads via `<BulkDestructiveConfirm count>` extrait de
  ForceDeleteModal) — jamais les 68 d'un coup. Files : `ui/ConfirmDialog.jsx` +
  `ui/BulkDestructiveConfirm.jsx` (extraits), les ~10 sites cités. DoD : les 10 sites à fort enjeu
  utilisent le dialog pondéré (confirmation tapée pour litiges/webhook/KB-enfants) ; bulk ≥5
  leads montre le compte tapé ; Entrée ne déclenche pas un `high` ; tests. (T2 — M, sonnet)
  (@lane: frontend/data — @coord VX19/VX95/VX96)

**Sous-groupe VXD-Q — Interop & onboarding→maîtrise**

- [ ] VX245 — **[BACKEND] Le cycle client sortant se boucle : `.ics` d'événement unique, (@lane: backend/notify — @coord VX116/VX46)
  confirmation WhatsApp de RDV, relance de facture riche. @coord VX116, VX46 (re-surface
  l'ABONNEMENT — distinct).** Trois maillons du même canal : (a) `AppointmentBooker.jsx` crée un
  RDV sans JAMAIS produire de `.ics` — le seul générateur (`reporting/calendar.py:366-392`,
  `build_ics`) ne fait que le flux d'ABONNEMENT complet ; (b) une fois le `.ics` livré, rien ne
  relie le RDV au message WhatsApp de confirmation ; (c) le flux WhatsApp RICHE
  (`LeadForm.jsx:179-207`) est un MONOPOLE du devis→lead — VX108 rend les numéros cliquables NUS
  sans message pré-rempli. Fix : extraire `build_ics` en fonction pure, endpoint `GET
  /crm/appointments/<id>/ics/` (1 VEVENT RFC 5545, scopé company) + bouton « Ajouter à mon
  agenda (.ics) » ; bouton « Confirmer par WhatsApp » post-RDV (aperçu date/heure + lien .ics,
  jamais automatique) ; extraire la construction message+wa_url en service paramétré par contexte
  (`crm/services.py` ; la variante facture vit côté `ventes/services.py`) et l'appliquer à la
  relance de facture depuis `FactureList`/`ClientDetailPanel`. Files :
  `apps/reporting/calendar.py`, `apps/crm/{views,services}.py`, `apps/ventes/services.py`,
  `crmApi.js`, `AppointmentBooker.jsx`, `FactureList.jsx`/`ClientDetailPanel.jsx`. DoD : « Ajouter
  à mon agenda » télécharge un .ics valide qui s'ouvre dans Google Agenda (RDV d'une autre
  société → 404) ; confirmer un RDV propose le message WhatsApp avec lien ; « Relancer par
  WhatsApp » sur une facture en retard affiche l'aperçu du message ; tests. (T3 — M, sonnet)
  (@lane: backend/notify — @coord VX116/VX46)

- [x] VX246 — **Queue de couverture interop : compression POD/chatter, Imprimer RH/contrats,
  Copier TSV partout, vCard, tel: terrain. @after VX77/VX80/VX110/VX108.** Cinq extensions
  mécaniques de patrons que VX pose sur des listes nommées en laissant des orphelins prouvés :
  (a) compression photo VX77 = 3 écrans terrain — `PodCaptureDialog.jsx:120` et
  `AttachmentsPanel.jsx:79` envoient brut ; (b) VX80 pose `print.css` + bouton sur 3 écrans —
  ajouter le MÊME bouton sur `EmployeDetail.jsx` et `ContratDetail.jsx` (PAS le PDF WeasyPrint
  contrat existant, hors règle #4 mais un seul mécanisme) ; (c) VX110 pilote « Copier » TSV sur
  ClientList — restent orphelins : `installations/views/ListView.jsx`, `sav/TicketsPage.jsx`,
  `stock/BonsCommandeFournisseur.jsx` ; (d) aucun `.vcf` nulle part — util pur `lib/vcard.js`
  (vCard 3.0, zéro dép) + bouton discret à côté des liens VX108 ; (e) `TrajetPanel`
  (`InterventionFieldExecution.jsx:247-251`) affiche le téléphone du contact site en texte brut →
  lien `tel:`. Files : `features/logistique/PodCaptureDialog.jsx`,
  `components/AttachmentsPanel.jsx`, `features/rh/EmployeDetail.jsx`,
  `features/contrats/ContratDetail.jsx`, les 3 listes TSV, `lib/vcard.js` (nouveau),
  `InterventionFieldExecution.jsx`. DoD : une photo POD de 6 Mo compresse avant upload, un PDF
  passe intact ; `emulateMedia print` propre sur RH/contrat ; « Copier » TSV sur les 3 listes ; un
  `.vcf` téléchargé s'importe ; le numéro du contact site est tapable ; tests. (T3 — M,
  haiku/sonnet) (@lane: frontend/ios — @after VX77/VX80/VX110/VX108)

- [ ] VX247 — **[GATED-founder pour le volet (e)] Onboarding→maîtrise : le guide connaît le (@lane: frontend/brand — @coord NTMOB33/VX47)
  rôle, annonce le clavier, se voit dans le shell, a une mémoire — et l'ERP peut se peupler
  d'exemple. @coord NTMOB33/VX47.** Le rapport prouve qu'un système d'onboarding ENTIER (FG16 :
  279 lignes de coachmarks + checklist réelle) est absent à 100 % de la carte VX1-116. Cinq
  trous : (a) `OnboardingCoachmarks.jsx:20-52` montre la MÊME séquence à tous → filtrer `STEPS`
  par prédicat de rôle + 1-2 étapes par rôle non-admin (desktop ; NTMOB33 possède le MOBILE) ; (b)
  le tour ne mentionne JAMAIS `⌘K` ni `?` → +1 étape finale sourcée de `GLOBAL_SHORTCUTS` ; (c) la
  progression (`OnboardingSection.jsx:71`) n'existe QUE dans Paramètres → badge `2/3` sur l'item
  Sidebar Paramètres tant que <100 % ; (d) aucun glossaire métier → page statique
  `/aide/lexique` (15-25 termes), les HelpTip VX47 y POINTENT au lieu de dupliquer (@after VX47) ;
  (e) [GATED-founder][BACKEND] `seed_demo.py` (326 lignes, jeu complet, CLI/DEBUG-only) n'est
  exposé nulle part — endpoint protégé (flag explicite, société fraîche ET vide uniquement) +
  bouton conditionnel dans OnboardingSection — PROPOSER, ne jamais activer sans accord fondateur.
  Files : `features/onboarding/{OnboardingCoachmarks.jsx,onboardingHelpers.js}`,
  `hooks/useOnboardingProgress.js` (nouveau), `components/layout/Sidebar.jsx`,
  `pages/aide/LexiquePage.jsx` (nouveau + route),
  `authentication/management/commands/seed_demo.py` (extraction service), endpoint léger,
  `pages/parametres/OnboardingSection.jsx`. DoD : un compte Technicien ne voit jamais « Invitez
  votre équipe » ; le tour finit sur `⌘K`/`?` ; badge Sidebar disparaît à 100 % ; lexique ≥15
  termes ; une société neuve se peuple/se vide d'exemple derrière le flag (2 sens testés, garde
  prod) ; non-régression du parcours Admin. (T3 — L, sonnet) (@lane: frontend/brand — @coord
  NTMOB33/VX47)

**Sous-groupe VXD-R — L'âme au quotidien**

- [ ] VX248 — **Raccourcis d'ACTION à une touche sur le record focalisé + cheatsheet filtrée par (@lane: frontend/crm — @coord NTUX9/18)
  rôle. @coord NTUX9/18 (palette = chercher-puis-exécuter ; cheatsheet-recherche = trouver un
  raccourci CONNU — mécanismes disjoints, vérifier avant build).** La vélocité perçue vient des
  raccourcis d'ACTION sur l'objet affiché, pas de la navigation — `shortcuts.js` ne connaît que
  `GOTO_SHORTCUTS` (nav), et la cheatsheet `?` est une liste statique identique pour tous les
  rôles. Fix : registre `focusedRecordShortcuts.js` par écran de détail (LeadForm, détail
  DevisList/FactureList, Ticket) — une touche = une action fréquente (`a` archiver, `d` déléguer,
  `1..4` changer de stage via les CLÉS DE STAGES.py, règle #2 — jamais de littéraux) derrière la
  garde `isTypingTarget` existante (`shortcuts.js:29-38`) ; apprentissage passif : le raccourci
  s'affiche en tooltip sur le bouton équivalent (@coord VX129 — même slot `kbd`) ; la cheatsheet
  gagne un champ `roles: []` optionnel et groupe « Pour votre rôle » d'abord, « Autres » en repli
  (filtre d'AFFICHAGE seulement, jamais de désactivation fonctionnelle). Files :
  `providers/{shortcuts.js,ShortcutsProvider.jsx}`, `focusedRecordShortcuts.js` (nouveau), points
  de montage LeadForm/DevisList/FactureList, composant cheatsheet. DoD : sur LeadForm ouvert, `a`
  (hors champ) archive sans clic, une frappe DANS un `<Input>` ne déclenche jamais ; un
  Technicien ouvrant `?` voit ses raccourcis en tête ; la cheatsheet liste les nouveaux par écran
  actif ; tests `isTypingTarget` + rendu par rôle. (T3 — M, sonnet) (@lane: frontend/crm — @coord
  NTUX9/18)

- [ ] VX249 — **Le langage des micro-états : pulse de champ sauvé, valeur « suggérée », pastille (@lane: frontend/crm — @after/with VX93)
  « pour moi » vs « société ». @after/with VX93, @coord VX83/84/86 + VX208.** Trois micro-signaux
  systémiques qu'aucune tâche par-écran ne peut poser : (a) aucun micro-accusé au grain du champ
  pour les sauvegardes silencieuses (édition inline DataTable, statut, note chatter) → primitive
  `ui/FieldSavedPulse.jsx` (pulse vert 300-400 ms sur LA cellule, `prefers-reduced-motion` →
  changement statique), intégrée d'abord à l'édition inline DataTable ; (b) VX93 pré-remplit
  (owner/ville/TVA/payMode) sans dire que c'est une SUPPOSITION → style discret « suggéré »
  (contour pointillé + micro-libellé au focus, retiré dès modification) sur les 4 champs VX93
  exactement, jamais un système de confidence générique ; (c) VX83/84/86 posent 3 surfaces de
  signal sans convention visuelle commune « assigné à moi » vs « information société » → UN
  token (pastille pleine = pour moi/action, contour = info passive) consommé à l'identique par
  cloche, Ma file et Dashboard. Files : `ui/FieldSavedPulse.jsx` (nouveau),
  `ui/datatable/DataTable.jsx`, les 4 fichiers VX93, `design/tokens.css`, `NotificationBell.jsx`,
  `MesActivitesPage.jsx`, `Dashboard.jsx`. DoD : valider une cellule inline pulse LA cellule (pas
  un toast) ; les champs pré-remplis affichent « suggéré » jusqu'au premier toucher ; un item
  société n'emprunte jamais le style « pour moi » (test des 3 surfaces) ; reduced-motion dégrade.
  (T3 — M, sonnet) (@lane: frontend/crm — @after/with VX93)

- [ ] VX250 — **La fiche annonce son état et ses relations : « en attente de… » + compteurs (@lane: frontend/crm — @coord VX159/ARC46)
  cliquables. @coord ARC46 (`RecordShell` — construire indépendant, migrer dedans plus tard).**
  Deux lectures ambiantes au niveau du record : (a) rien ne montre, DANS le document ouvert, ce
  qui reste à faire ailleurs → `<PendingStepsIndicator>` sur le détail Devis/Facture, dérivé des
  statuts déjà chargés (devis `envoye` non signé → « En attente de signature client » ; facture à
  acompte partiel → « Solde restant : X MAD ») — lecture PURE, ne change jamais un statut (chaîne
  Devis/BonCommande/Facture préservée 1:1, règle #4) ; (b) chaque fiche 360 affiche ses relations
  à sa façon → `<RelationCounters>` réutilisable (« 3 devis · 1 facture impayée · 2 tickets SAV »)
  en tête de Lead/Client/Fournisseur/Produit *(note : composant déjà introduit en VX159 côté axe1
  — cette entrée en spécifie l'usage sur DevisForm/FactureList également, coordonner un seul
  `ui/RelationCounters.jsx`, ne jamais en construire un second)*, chaque compteur lu via le
  selector du domaine CIBLE, clic → liste pré-filtrée `?client=`/`?id=`. Files :
  `pages/ventes/{DevisForm,FactureList}.jsx` (détail), `ui/RelationCounters.jsx` (voir VX159),
  montage `ClientDetailPanel.jsx`, `FournisseurFiche360.jsx`, `ProduitDetail.jsx`,
  `LeadForm.jsx`. DoD : un devis envoyé non signé affiche son bandeau qui disparaît à la
  signature ; une facture d'acompte affiche le solde ; les 4 fiches montrent les mêmes compteurs
  cliquables vers des listes pré-filtrées ; `prix_achat` jamais rendu ; zéro appel réseau nouveau
  pour (a) ; tests. (T3 — M, sonnet) (@lane: frontend/crm — @coord VX159/ARC46)

- [x] VX251 — **Le dispatch au glisser-déposer : réaffecter une intervention comme
  ServiceTitan. @after VX95, @coord NTFSM3 (optimiseur 2-opt = l'ORDRE d'une tournée, pas le
  geste de réaffectation — disjoint ; vérifier avant build).** Le geste cœur d'un dispatch board
  (glisser un job d'un technicien à l'autre) n'existe pas — `PlanificationPage.jsx` (calendrier
  dispatch) n'a aucun `onDrop`/`draggable`, alors que `KanbanView.jsx:186-200` (CRM) prouve déjà
  le pattern drag+recul-guard dans le repo. Fix : répliquer le pattern Kanban sur l'onglet
  dispatch — glisser une carte intervention d'une colonne-technicien à une autre déclenche
  l'update `technicien`/`date` EXISTANT + `toastWithUndo` 6 s (VX95, jamais un 2ᵉ primitif undo) ;
  le Gantt FG74 reste lecture seule ; la notif au nouveau technicien arrive par
  `_notifier_reassignation` déjà câblé (XFSM3) — zéro backend. Files :
  `pages/installations/PlanificationPage.jsx`, réutilise `lib/toast.js:60-89`. DoD : le drag
  réaffecte réellement (persistance vérifiée), « Annuler » restaure l'affectation ; la
  notification part au réassigné ; test du drop + undo. (T3 — M, sonnet) (@lane: frontend/ios —
  @after VX95)

- [BLOCKED: attend VX156 — celebrate.js non construit] VX252 — **[BACKEND additif léger] Maîtrise personnelle : milestones non comparatifs, KPI
  d'adoption clavier, garde anti-backfire de la gamification. @after VX156 (célébration devis
  signé), @coord NTCRM23/24/28, NTUX40.** Recherche 2026 (Trophy.so, Carnegie Mellon) : ~10 % des
  employés sont motivés par la compétition ; les 90 % restants sont ACTIVEMENT démotivés par un
  classement. Trois pièces : (a) étendre `celebrate.js` (VX156, CSS-only) d'un déclencheur
  « milestone personnel » à seuils déterministes et espacés (50ᵉ intervention signée, 25ᵉ devis
  signé) — célébré UNE fois, jamais visible d'un collègue/manager, reduced-motion → toast simple ;
  (b) KPI interne d'adoption clavier (« % actifs ayant utilisé ⌘K 1×/semaine », signal `POST
  /ux/usage-signal/` best-effort jamais bloquant) — gate Directeur/Admin, JAMAIS montré au
  commercial (@coord NTUX40 — métriques disjointes, vérifier) ; (c) garde anti-backfire à
  INSCRIRE sur NTCRM23/24 avant leur build : `metrique_qualite_associee` affichée à côté du score
  brut + participation réellement opt-in invisible — jamais un score de vitesse seul. Files :
  `ui/celebrate.js`, points d'appel `MaJourneePage.jsx`/`SigneDialog`, `apps/reporting/models.py`
  + endpoint léger, `providers/CommandPalette.jsx` (compteur), note sur NTCRM23/24. DoD : la 50ᵉ
  intervention signée célèbre une fois (pas au 51ᵉ, pas au reload) ; le KPI calcule un % réel et
  échoue gracieusement à 0 ; la note NTCRM est posée dans le plan ; tests. (T3 — M, sonnet)
  (@lane: backend/notify — @after VX156)

---

## NE PAS FAIRE (Groupe VXD) — fusion dédupliquée des trois axes

**Déjà possédé par VX1-116 (couches design/coquille/cockpits) :**
- Re-signature coquille/marque, accents module, lanceur, cockpits → VX1-8, VX9-12/ODX5-7,
  VX15/27/29-34. Couleurs de stage StatusPill → VX26 (règle #2).
- Palette catégorielle data-viz + annotations → VX41 (danger zone) ; la rampe « solaire »
  d'un rapport source est versée comme INPUT à VX41, jamais re-proposée.
- Illustrations SVG d'états vides + confetti générique → VX40 (« délice mesuré ») ; VX156 (axe1
  S40b, ex-« signé célébré ») ne câble QUE le moment signé, jamais le système d'illustration.
- Photo produit catalogue, theming par tenant, refonte Landing, grille d'apps pleine page à la
  Odoo → rejets fondateur explicites (rounds 1-3, PLAN2 NE PAS FAIRE).
- Grain `feTurbulence` sur la sidebar, `@starting-style` (pattern de référence, pas un défaut),
  `content-visibility` sur les listes non virtualisées (territoire perf, pas beauté) → rejetés/
  hors-axe, non repris.
- Badge persistant d'échec PDF sur la ligne, identifiant support dans ErrorBoundary → possédés
  par VX172 / VX206 respectivement.

**Déjà possédé par VX48-72 (appareils/Safari/perf nommés) :**
- PDF iOS (onglet pré-ouvert), popup-block detection, `data-label` tables, clavier iOS
  VisualViewport, `title=` tactile, balayage compat → VX48/49/50/51/52/53.
- Troncature 100 lignes + pagination parallèle, timeout axios + annulation, poll onglet caché,
  cold-path, préchargement, chunk-name, e2e comptes-justes, Web Vitals → VX54-VX61.
- Brouillon auto DevisGenerator + garde de sortie → VX62 ; JSON brut DevisList → VX63 ; error
  boundaries routes nues → VX64 ; `?next=` login → VX65 ; anti-double-submit Button → VX66.
- Safari/iPad/zoom/visual-regression/axe/Sentry e2e → VX68/69/70/71/72.
- `.agent-sql` momentum-scroll → CSS mort (0 consommateur), retiré de VX175 ; sa suppression
  appartient à VX121.
- Rejets round 2 toujours en vigueur : verrou optimiste 409 (→YDATA), Lighthouse-CI sur le SPA
  authentifié, BundleMon 2ᵉ gate, Firefox en matrice, service-worker cache des RÉPONSES API, 2ᵉ
  outbox offline, virtualisation sans mesure. VX187/VX188 sont les seules exceptions MESURÉES
  (DoD Profiler à l'appui) ; VX179 cache des ASSETS/médias en lecture, jamais des réponses API.
  `animation-timeline: scroll()` non confirmé dans le code → ne pas construire spéculativement ;
  attribution LoAF dans le beacon → amendement du build de VX61 (même fichier `vitals.js`), pas
  une tâche séparée ; note HMR du singleton `fieldOutbox` → un commentaire de code, pas une
  tâche ; moteur de conflit offline / CRDT → le signal de conflit EST le message serveur par op de
  VX119.
- Gate visuel bloquant par PR → contredit la décision LIVRÉE de VX70, jamais un amendement sans
  raison.

**Déjà possédé par VX73-116 (locale, files, saisie, argent, amour-employé) :**
- Sélecteur de langue menteur + `Ctrl K` → VX73 ; arabe RTL décision → VX74 ; format
  argent/date + garde CI → VX75 (VX143 en est l'annexe d'exécution, pas un doublon) ; compression
  photo → VX77 ; 404 branché → VX78.
- « Ma file » unique + cloche AUTRES + plomberie records + signaux approbation → VX83-86,
  VX99-101 ; jamais un 2ᵉ agrégateur ni une 2ᵉ boîte de réception parallèle (VX214 l'atteste par
  reshape) ; jamais de hook de polling séparé pour la cloche (VX56 possède
  `useVisibilityAwarePolling`, cloche incluse).
- Journal d'appel un-geste + tournée géo + délégation absence + technicien + signature client +
  résumé client → VX87/88/103/105/106/107.
- LeadForm Escape/autofocus, « Ajouter ligne » focus, convergence FactureForm, « enregistrer et
  créer un autre », défauts intelligents, Enter-pour-ajouter → VX89-94.
- `toastWithUndo` câblé (archive/kanban), soft-delete Lead, « qui a fait quoi », lien Historique,
  `tel:`/`wa.me`, import fournisseurs, « Copier » TSV, pièce jointe note chatter → VX95-98,
  VX108-111.
- Drill-down relances, exercice fiscal, sélecteur dates export, KPI compta, relance en lot →
  VX112-116.
- « Mes préférences » (thème/densité/module d'atterrissage/mouvement) → VX46 ; HelpTip
  contextuel → VX47 ; emails de marque wrapper → VX76 ; export XLSX horodaté → VX81 ; liens
  partageables `?id=` → VX79 ; impression → VX80 ; chrome onglet + non-lus → VX82.
- Rejets round 3 : 2FA remember-device (→NTSEC14), Corbeille générique (→NTUX7), formulaire
  DemandeAchat catalogue (→NTP2P3), refonte chatter (→VX23/ARC8-9), moteur d'approbation unifié
  (→ARC10/NTWFL1), « Ma journée commerciale » silo (→VX83 absorbe), inbox mentions dédiée
  (→NTCOL17), optimiseur 2-opt (→NTFSM3), undo bulk-edit (→NTUX6), paste-grid Excel multi-cellules
  (différé — VX237 est le collage UNITAIRE), KPI perso PUBLIC/classement (différé — VX219 est
  privé, VX252 non-comparatif), correction de ligne de paiement (DECISION), iCal abonnement
  (VX46), Client-360/OCR relevé (persona-finance).

**Frontières NT/ARC intouchables (les trois axes) :**
- Vues serveur partagées / FilterBuilder ET/OU / bulk-edit preview-undo / corbeille transverse
  (`apps/trash`) / quick-create palette générique / favoris / peek-hover de LIGNE / densité par
  vue → NTUX (frontière explicite « pas de changement visuel/shell (Groupe VX) »,
  `new_tasks_plan.md:2436`).
- Boîte email par user / RDV Calendly / boîte partagée / inbox mentions `/mentions` / digest
  personnel → NTCOL.
- Offline multi-module / accueils mobiles par rôle / géofence / scan QR / onboarding mobile
  « Ma journée » → NTMOB, NTMOB33.
- i18n/RTL/langue par user/polices arabes → NTI18N (attention : NTI18N5/17/30 touchent le moteur
  `/proposal` — règle #4, ne jamais y toucher côté client).
- Leaderboard/défis d'équipe → NTCRM23/24 (seul le garde-fou de VX252 s'y greffe, jamais le
  système lui-même).
- Moteur d'approbation unifié → ARC10/NTWFL1 ; migration DataTable DevisList/FactureList →
  ARC49/53 (VX180/VX178/VX184 se corrigent AVANT que la migration n'hérite du défaut) ;
  `useResource` → ARC44/45 ; RecordShell → ARC46 (VX159/VX250 construits indépendants, migrables
  dedans ensuite) ; politique magasin-unique → ARC26.
- Verrou optimiste backend 409 → YDATA ; file photo binaire offline → FG386 (« jamais un 2ᵉ
  outbox », VX119 ne construit PAS de moteur CRDT).

**Mécanique transversale (toujours vraie, tous les VXD) :**
- Frontend-first ; aucune dépendance npm nouvelle sauf tâche taguée [GATED] (VX120 QR 2FA,
  VX198 jsx-a11y, VX247(e) seed_demo — tous soumis au fondateur avant tout build).
- Jamais toucher `apps/ventes/quote_engine/`, `/proposal`, PdfCanvas, `apps/web` (règle #4) — le
  moteur RESTITUE, ne change jamais un statut (VX250(a) est une LECTURE) ; les PDF
  d'intervention/contrat (WeasyPrint) sont hors règle #4 mais on n'y crée jamais un 2ᵉ mécanisme
  concurrent (VX246(b)).
- Toute clé de stage vient de `STAGES.py`/`features/crm/stages.js` (règle #2) — jamais un
  littéral (VX224, VX248 raccourcis `1..4`, VX211 `queueViews`).
- `prix_achat`/marge jamais client-facing ni dans un peek/notification/WhatsApp/milestone
  (VX213 montants DA, VX217 AttentionPeek, VX156 messages — tous montants client-safe).
- Jamais d'envoi WhatsApp/email automatique — aperçu-puis-clic partout (règle manuel-wa.me
  fondateur, VX222/VX245/VX252) ; jamais de mutation via lien email non authentifié (VX212).
  `api.qrserver.com` et tout rendu tiers de secrets sont interdits (VX120).
- Ne pas dé-gater `/reporting/commercial` (VX219 ajoute une carte personnelle, le reporting
  manager reste manager) ; ne pas élargir le Journal global (VX243 = lecture record-scopée,
  jamais un grant company-wide) ; ne JAMAIS déverrouiller un accès nav/rôle sans décision
  fondateur.
- Hooks e2e `ap-*/att-*/pp-*` préservés partout ; UN seul Toaster ; scoping tenant TOUJOURS
  serveur (`request.user.company`, `perform_create` force `company`) ; jamais `count()+1` pour
  une référence ; migrations additives/révertables ; noter AUTH au DONE LOG pour
  VX235/VX242/VX243 ; FR partout.

### Group QF — Quote fidelity: real-bill tranche savings, battery-scenario honesty, Huawei-only accessories (founder request 2026-07-01)

*From Reda: the devis currently shows savings numbers unrelated to the client's real bill; selecting « sans batterie » (and likely « avec batterie ») does not produce the right option; and the Smart Meter + Clé Wifi accessories are being attached to every inverter when they only belong on a Huawei. Three clusters below. Research pinned the exact code: residential on-screen savings (`solar.js computeROI`) use a FIXED 1.75 MAD/kWh and ignore the entered bills (bills are chart-only); the backend `pricing.py` already has ONEE/Lydec/Redal tranche tables from QJ13 but they only fire when `distributeur`+consumption are passed; `builder.py` (~L414-422) auto-derives the avec/sans scenario from line items and IGNORES the seller's stored `etude_params['scenario']`; and `solar.js autoFillLines` (~L445-465) attaches Smart Meter + Wifi to ANY réseau inverter, not Huawei-only (the correct guard exists in the old simulator and was never ported).*

> **Constraints (every QF task).** Rule #4 — the quote engine only RENDERS; the document status chain
> (`brouillon→envoye→accepte…`) + BonCommande/Facture are preserved 1:1 and `/proposal` stays the only
> client-facing quote-PDF path. **Self-consumption-first (QJ13 / loi 82-21): value only self-consumed
> kWh; the surplus-injection line stays OFF** until the founder confirms ANRE's BT tariff. **No invented
> numbers** — when the client's bill / utility is absent, degrade to a clearly-labelled estimate, never a
> fabricated one. Build ON QJ13's `pricing.py` tranche tables (extend, don't duplicate). New keys go into
> the existing `Devis.etude_params` JSONField (additive, no migration). **Front and back must agree on the
> math (one shared source of truth) so the on-screen number equals the PDF.** New user-facing text in French.

**A — Real-bill, two-bills, par-tranche savings + the method shown in the quote:**

**B — Battery-scenario honesty (avec / sans batterie):**

**C — Huawei-only Smart Meter + Clé Wifi:**

### Group QG — Quote generator UX, workflow & 3D viewer (founder request 2026-07-01)

*From Reda, on the devis experience: (1) clicking the PDF button never opens the PDF — after a wait only a green button appears (you must click AGAIN to download); (2) editing a quote via « Éditer » doesn't show up in the regenerated PDF; (3) creating a quote should be simpler — add a new client AND a new product directly from the quote screen; (4) but creating products anywhere must be restricted to Directeur + Commercial responsable; (5) the quote must carry the CREATOR's name + phone, not always the founder's; (6) « Envoyer » on a devis must behave exactly like « Envoyer via WhatsApp » in the leads; (7) the « Variante » button must actually show the quote with 3 variantes and let Reda + Meryem set the percentage (20 % default, changeable); (8) show the 3D roof viewer inside quotes AND as a separate window openable on its own. Research pinned every cause — see each task.*

> **Constraints (every QG task).** Rule #4 — the quote engine only RENDERS; the document status chain
> (`brouillon→envoye→accepte…`) + BonCommande/Facture preserved 1:1; `/proposal` stays the only
> client-facing quote-PDF path; NEVER touch the devis/facture PDF *templates*/public PDF pages beyond the
> data fed in. Multi-tenant: all reads/writes company-scoped server-side; `company` never from the body.
> Cross-app reads/writes via `selectors.py`/`services.py` + the `core/events.py` bus — never another app's
> models/views. Keep the generator's input freedom (form `noValidate`, inputs `step="any"`). New
> user-facing text in French. Reuse existing endpoints/patterns where research found them (e.g. the leads
> `whatsapp_devis` flow, `LeadExpressModal` quick-capture, the `ToitureDesign` roof builder).

**A — PDF generation & edit bugs (make creating a quote simple):**

**B — Simpler creation: inline client & product (product creation role-gated):**

**C — Creator identity & sending:**

**D — Variantes (3 variants, configurable %):**

**E — 3D roof viewer in quotes + standalone window:**

### Group QS — Supplier purchase-order (bon de commande fournisseur) UX & sending (founder request 2026-07-01)

*From Reda, on ordering products from a fournisseur (the SUPPLIER-side `BonCommandeFournisseur` in `apps/stock`, distinct from the client `ventes.BonCommande`): (1) add a product directly inside the bon de commande when ordering; (2) the PDF button doesn't work; (3) « Envoyer au fournisseur » only marks it sent and it's unclear what it did — he wants a WhatsApp button that sends the PDF to the supplier + an email-send button nearby, each greyed out when the supplier has no number / no email. Research: the BCF PDF endpoint (`/stock/bons-commande-fournisseur/<id>/pdf/`) EXISTS and works (WeasyPrint blob) — the button fails on the frontend and swallows the error into a generic « PDF indisponible »; `envoyer` (`bon_commande_fournisseur.py` ~L84) only flips BROUILLON→ENVOYE with no send; `Fournisseur` has nullable `telephone` + `email`; and the wa.me (`build_wa_url`/`normalize_ma_phone`) + `ShareLink` + `send_document_email`/`EmailLog` infra is all reusable.*

> **Constraints (every QS task).** Multi-tenant: everything company-scoped server-side; `company` never from the body. The BCF PDF is the supplier's own order and shows BUY prices (`prix_achat`) — it is legitimately sent to the FOURNISSEUR, but it must NEVER reach an end client: any tokenized link stays unguessable + expiring and is never surfaced client-side. WhatsApp `wa.me` can only carry text + a link (no file attachment) — so « envoyer par WhatsApp » sends a message with a tokenized link to the BCF PDF (mirroring the leads flow); email attaches the actual PDF. Cross-app reads via `selectors.py`/string-FK — never another app's models/views. Reuse the existing whatsapp/email/ShareLink infra; product creation stays gated to Directeur + Commercial responsable (QG4/QG5). New user-facing text in French.


### Group QD — Document PDF polish: logo size & file naming (founder request 2026-07-01)

*From Reda, looking at a real facture (`FAC-202607-0001`): (1) the company logo on the bill renders far too small; (2) the download filename `Facture_FAC-202607-0001.pdf` reads wrong — « Facture_FAC » is redundant and it carries no client/company context. Confirmed by inspecting the logo asset + the rendered invoice.*

> **Constraints.** Rule #4 — the facture keeps its own legacy WeasyPrint PDF (editable; NOT a quote-PDF path). Multi-tenant: the bill logo is the per-company `CompanyProfile.logo_key`. Keep aspect ratio (never distort). French UI.


### Group QP — Quote line product handling: picker filter, rename & create-in-stock (founder request 2026-07-01)

*From Reda, in the quote generator: (1) when picking the inverter for the HYBRID INVERTER slot, only inverters should show — not every product; (2) rename a product's line directly in the quote; (3) on rename, the ERP should ask « just change the name here (this quote) » vs « add a new product with the new name in stock ». Research: the generator is a FLAT line table (no typed slots) — a line's type is inferred from its designation via `classifyProduct` in `frontend/src/features/ventes/solar.js` (keys `onduleur_hybride` / `onduleur_reseau` / `panneau` / `batterie`…); `ProduitPicker` takes NO filter prop today (`ProduitPicker.jsx` ~L28-46, invoked at `DevisGenerator.jsx` ~L1563 with ALL products); the line `designation` is already inline-editable with a « désignation modifiée » warning when it diverges from the product name (`DevisGenerator.jsx` ~L1544-1560); `stockApi.createProduit` exists and is role-gated (QG4).*

> **Constraints.** Reuse the `solar.js` classifiers and keep them aligned with `quote_engine/builder.py` keywords (CLAUDE.md). Product creation stays gated to Directeur + Commercial responsable (QG4/QG5). `prix_achat` is never exposed client-side. Keep generator input freedom (`noValidate`, `step="any"`). French UI.


### Group CH — Chantier (installation) workflow redesign: international PV gates, director-configurable (founder request 2026-07-01)

*From Reda: the chantier/installation follow-up is weak — the steps are « kind of weird ». Redesign it to follow the internationally-recognized solar-PV installation lifecycle with proper gates, best-in-class UX, and let the DIRECTOR add/remove gates. Research: `Installation.statut` is a HARDCODED 7-step enum (SIGNÉ→MATERIEL_COMMANDE→PLANIFIE→EN_COURS→INSTALLE→RECEPTIONNE→CLOTURE); richer pieces already exist but aren't wired to it — a director-configurable execution checklist (`ChecklistTemplate`/`ChecklistEtapeModele`: add/remove/reorder, photo-required, serial-capture, `protege`), project milestones (`JalonProjet`: ETUDE/APPRO/POSE/MES/RECEPTION), and QHSE inspection HOLD POINTS (`PlanInspection`/`hold_point`) that block work but DON'T gate installation status; readiness (FG77) is advisory, not enforced — a chantier can reach RECEPTIONNE without passing any gate (the « weird » part). International lifecycle (IEC 62446-1 + EPC best practice): site survey → design/engineering → permitting & grid approval (loi 82-21 dossier) → procurement → mechanical install → electrical install → commissioning & testing (IEC 62446-1: documentation, visual inspection, electrical tests, performance & safety verification) → inspection / PTO & grid connection → handover (handover pack) → O&M.*

> **Constraints (every CH task).** Multi-tenant/company-scoped server-side. BUILD ON the existing configurable checklist pattern (`ChecklistTemplate`/`ChecklistEtapeModele`) — do NOT rip out `Installation.statut`; MAP it onto the new stages (no data loss). Preserve the existing side-effects: stock reservation at INSTALLE, warranty/parc handover at RECEPTIONNE (FG70). QHSE is a separate app — read hold-points via `selectors.py` / loose `chantier_id`, never import its models. `STAGES.py` is the CRM funnel (a permanent separate layer — do NOT touch). Gate CONFIGURATION is Directeur-only. French UI; keep e2e DOM hooks.


### Group QK — Quote-journey best-in-world audit gaps (ERP/backend; 2026-07-01)

*From a fresh 3-axis best-in-world audit of the client quote journey (content collected / content delivered / UX) benchmarked against Aurora, OpenSolar, Otovo, Tesla, EnergySage, Sunrun, 1KOMMA5°, Enpal, Bodhi + Morocco reality. These are the ERP/backend gaps NOT already covered by QJ/QF/QG/WJ. The website half is WEB_PLAN WJ30–WJ35. Morocco facts confirmed this pass: ANRE DEFERRED the BT-residential surplus buy-back tariff (savings stay self-consumption-only, injection line OFF); agricole financing = CAM « Saquii Solaire » (~5–6 %, 10 yr, 1-yr grace) + FDA 30 % pumping subsidy, NOT ISTIDAMA; typed-name e-sign valid (loi 43-20 art. 7). Honesty rule: no fabricated numbers.*


### Group MB — Mobile rendering root-cause fix (phone) (founder request 2026-07-01)

*From Reda: on the phone the ERP « does not render well at all » — stuff on top of each other, sometimes oversized pages. Two-agent diagnosis found the FOUNDATION is mostly sound (viewport `viewport-fit=cover` OK; the 768px breakpoint, `ResponsiveDialog` M158, DataTable→card M154, U2/U3 all shipped) — the real causes are a SMALL set of foundation bugs + incomplete adoption, so the right fix is systematic (fix the foundation once → sweep the un-adapted screens → add a mobile gate), not per-page patching. Root causes: (1) mobile `.layout-content` (`index.css` ~L2014) reserves NO space for the 52px sticky header (+notch) or the 52px bottom-tabbar → content scrolls BEHIND them (the overlap); (2) horizontal overflow from `.pp-pop { width: max(100%,380px) }` (380px on a 375px phone), a rigid catalogue `.cat-row` grid, and legacy fixed-pixel widths with no mobile `@media`; (3) z-index chaos — a `--z-*` scale EXISTS in `tokens.css` but ad-hoc magic numbers collide (`.pp-pop` set to 300 then overridden to 1 → sinks behind modals; `.gs-wrap` z-index 50 below the header; bottom-tabbar 1300 == modal); (4) `ResponsiveDialog` is used in ONE screen — the DevisList PDF/accept/email modals + the LeadForm modal are fixed-width Dialogs that overflow phones (can't accept/email a devis or edit a lead on mobile); (5) ~60% of legacy pages have no mobile CSS.*

> **Constraints.** Do NOT regress the shipped mobile work (M154–M158, U2/U3, J139–J144). Keep the e2e DOM hooks. Use the existing `--z-*` tokens + `ResponsiveDialog`/`useIsMobile` primitives — don't invent parallel ones. French UI. Frontend-only (no backend).


### Group WR — Wire orphaned backend features to the UI (whole-app audit, founder request 2026-07-01)

*From Reda: « a lot of non-working features built with no front end or not well wired ». A 7-agent evidence-based audit (verified by grepping the frontend for real callers) swept every app. RESULT: the pure frontend is sound (no dead routes / no-op buttons / calls to missing endpoints); the 9 backend-only MODULES (compta/paie/rh/gestion_projet/contrats/qhse/kb/litiges/ged) are ALREADY covered by PLAN.md Group UX (UX1–47) — EXCLUDED here; foundation/config (auth/roles/records/customfields/parametres) is fully wired. The real debt = individual features shipped BACKEND-ONLY inside modules that DO have a UI (ventes/stock/monitoring/crm/installations/sav) — their FG task was ticked done with no frontend task. These are those wire-ups. NOTE: installations readiness/handover (FG70/FG77) are folded into Group CH, so excluded here. Each task below: the backend ALREADY EXISTS (cited) — this is UI + api-client wiring only, no backend rebuild.*

> **Constraints (every WR task).** Backend already shipped — do NOT rebuild it; add the frontend surface + the api-client wrapper only. Multi-tenant/company-scoped (server already enforces). `prix_achat`/buy-price + margins NEVER shown client-side. Reuse the existing DataTable / ResponsiveDialog / recharts primitives (and the Group UX `ModuleDashboard`/`ListShell` kit where it helps). French UI; keep e2e hooks.


### Group QC — Moroccan company autocomplete on client creation (founder request 2026-07-01)

*From Reda: « in Odoo I can easily find Moroccan companies when I start typing their name as new clients — add this to my ERP. » Research verdict: Odoo's Partner Autocomplete is a paid IAP service backed by Clearbit WEB data — it does NOT return ICE/RC/IF for Morocco (Moroccan Odoo integrators install manual `partner_ice`/`l10n_ma_legal` field modules). There is NO free official API or open dataset (OMPIC DirectInfo has no API and its legal notice bans data reproduction; ice.gov.ma is CAPTCHA-gated; data.gov.ma has no company register). The ONLY compliant registry-backed API with Morocco depth is the paid Inforisk/Charika offer (~950k companies, licensed OMPIC data, quote-only pricing). Scraping any of these violates their ToS → rule #5 (risk file + founder approval) and is NOT pursued. Code side is ready: `Client` already has `ice`/`if_fiscal`/`rc` (and `Fournisseur` the identical trio — no migration), the generic async `Combobox` (`frontend/src/ui/Combobox.jsx`) is the typeahead, and the PVGIS proxy (`apps/parametres/pvgis.py`) is the cached-external-lookup pattern for the gated provider.*

- [BLOCKED: paid — needs founder-provisioned Inforisk/Charika account] QC2 — **[GATED: paid — Inforisk/Charika API] Registry-backed autocomplete (the true Odoo-style experience).** Behind a flag (default OFF), plug a licensed Moroccan-registry provider into the QC1 seam: type a name → provider suggestions (ICE/RC/IF/adresse from licensed OMPIC data) → pick → auto-fill, with server-side caching (24 h, PVGIS-proxy pattern), rate limiting, and a clean no-key degrade to QC1's own-data mode. NEEDS FOUNDER: an Inforisk/Charika account + contract/budget (pricing is quote-only) — OR a founder-led OMPIC licensed-feed inquiry. Never scrape OMPIC/ice.gov.ma/Charika (ToS-prohibited; rule #5). **Done =** with a provider key the autocomplete returns registry-backed Moroccan companies and fills the legal IDs; without it, behaviour is exactly QC1; tests cover the provider seam + the degrade + the never-leak of the key client-side. Files: a provider client in `apps/crm/` (or `apps/parametres/` beside pvgis), `apps/crm/views.py`, settings flag, tests. (DEP/COST — needs founder-provisioned Inforisk/Charika account; note in DONE LOG) (@lane: backend/crm) (@after: QC1)

## Group F — Design foundation & tokens


## Group G — Primitive component library (shadcn-based; one "definition of done" per component: states, dark mode, keyboard, ARIA)


## Group H — DataTable engine (TanStack Table, behind every list view)


## Group I — App shell & navigation


## Group J — Per-module restyle (each: list → DataTable, forms → new primitives, modals → Dialog/Sheet, statuses → StatusPill, real empty/loading/error states, mobile pass)


## Group K — Dashboard & reporting


## Group L — Global UX behaviors


## Group M — Mobile & PWA polish (Meryem is iPhone-primary)


## Group N — Accessibility & quality floor (WCAG 2.2 AA)


## Group O — Performance


## Group P — Consistency & cleanup


## Pending Reda (carry these in the plan)
- Hard constraints (do not violate): never touch the devis/facture PDF templates, the public PDF pages, the PdfCanvas content, or the apps/web marketing site; STAGES.py stays a fixed CI contract; all schema changes additive/nullable, seeded from current in-code defaults.

---

### Group A — Devis acceptance, wired to Signé, facture & chantier (core unblock)

### Group B — Bug: file attachments

### Group C — Bug: navigation menu

### Group D — Paramètres: split + far more editable settings (all in one pass)



### Group E — End-to-end (E2E) browser test suite covering every screen flow

---

## DONE LOG (agent appends one plain-language line per completed task)

- 2026-07-12 — **VX118 — [BUG] surfaces fantômes : Discuss + LeadExpress + kiosque TV migrées sur le kit existant, zéro CSS ajouté.** (a) Discuss (`ConversationList.jsx`, `MessageThread.jsx`, `Composer.jsx`) : les 11+ classes `chat-list-*`/`chat-thread-*`/`chat-pinned-*`/`chat-composer-*` sans AUCUNE règle CSS migrées vers `cn()`+Tailwind (bandeau épinglé désormais fond/bordure visibles, item actif/non-lu distincts) ; `ChatPage.jsx` déjà co-listait du Tailwind réel, non touché. (b) `LeadExpressModal.jsx` : les 23 références `lem-*` (0 CSS depuis sa création) remplacées par `Dialog`+`Form`/`FormField`/`FormActions` (le langage des autres dialogues CRM) ; le handler Échap manuel retiré (Radix Dialog le gère nativement). (c) `DashboardsTvPage.jsx` : `<pre>{JSON.stringify(current.layout)}</pre>` remplacé par un rendu réel avec le kit existant (`Card`+`ui/charts`) — grands chiffres `text-6xl` pour les widgets scalaires, `AreaSansAxe`/`KpiSpark` en grand pour les séries, `ChartEmpty` pour un widget sans donnée exploitable, `EmptyState` si le dashboard n'a aucun widget ; forme réelle du layout lue depuis `dashboardFilters.js` (`layout.widgets[]`, seule convention déjà établie dans le repo — aucun schéma de widget-type préexistant ailleurs). Tests : DashboardsTvPage.test.jsx (nouveau cas stats/charts + garde `<pre>`=0).

- 2026-07-12 — **VX232 — Les états financiers deviennent LISIBLES : noms réels, tableaux exploitables, exports hiérarchisés et traduits.** (a) `CockpitPage.jsx` KPI n°1 : `Tiers #42` résolu en nom réel — SCOPE ADAPTÉ EN FRONTEND-ONLY (le lane build-only ne touche pas le backend) : au lieu d'enrichir `apps/compta/selectors.py`, le cockpit charge une fois le répertoire unifié `apps/tiers` (`GET /tiers/tiers/`, timeout 4 s dédié, purement décoratif) et résout `tiers_id` côté client via `resolveTiersLabel` (export nommé, testé unitairement) ; repli « Tiers #N » identique si le tiers a été supprimé/pas encore chargé. (b) `EtatsPage.jsx` `GenericTable` migré du `<table>` HTML nu vers le primitif partagé `pages/reporting/Table.jsx`, plus tri au clic d'en-tête (ascendant/descendant, icônes lucide) — une balance rendue trie désormais au clic. (c)(d) `FiscalitePage.jsx` : les 6 exports fiscaux regroupés en 2 rangées sous-titrées « Mensuel » / « Annuel — exercice requis », chaque bouton (FEC/liasse/IS compris) porte désormais une phrase d'aide grise dédiée. Tests : `resolveTiersLabel` (unitaire) + `etats-page-sort.test.jsx` (rendu `report-table` + tri au clic). Backend inchangé — `apps/compta/selectors.py` non touché (hors périmètre de ce lane).

- 2026-07-12 — **VX229 — `CrudDialog` apprend le Combobox : fin des champs FK « (ID) » tapés à la main.** Nouveau type de champ `{name, label, async: () => Promise<{value,label}[]>, deriveFields?: (opt) => object}` dans `CrudDialog.jsx` — options chargées une fois à l'ouverture, mémoïsées, rendu en `Combobox` de recherche. Migré : `NotesDeFraisPage.jsx` 3× « Employé (ID) » → Combobox « Nom Prénom » (`rhApi.getEmployes`) ; `RapprochementsPage.jsx` « Compte de contrepartie (ID) » → Combobox comptes (`comptaApi.comptes.list`) ; `EngagementsPage.jsx` retenue de garantie : `tiers_nom` texte libre → Combobox du répertoire unifié `apps/tiers` (`tiers_id`/`tiers_type` réels, `tiers_nom` dérivé lecture seule via `deriveFields`, traçable vers la fiche tiers). `marche_ref`/Cautions bancaires laissés tels quels (string-ref intentionnel, aucun modèle tiers dédié côté backend — zéro migration). Tests `crud-dialog-combobox.test.jsx` (rendu Combobox + dérivation tiers_id/tiers_type/tiers_nom à la création). Frontend pur, zéro migration.

- 2026-07-12 — **VX228 — `RapprochementDetailDialog` : le contrat d'interaction complet du rapprochement bancaire.** `RapprochementsPage.jsx` gagne un dialog 2 volets (relevé | grand-livre pré-filtré montant) ouvert par clic de ligne (`bancaires`), consommant les 4 méthodes API déjà écrites (`lignesGl`/`resume`/`ajouterLigneReleve`/`pointer`) ; bandeau `resume()` en tête (solde relevé/pointé, écart) qui décroît EN DIRECT à chaque pointage, même langage visuel que le bandeau d'équilibre d'`EcrituresPage` ; « Suggestions » déplacée DANS le dialog (retirée des actions de ligne) ; « Clôturer » apparaît dans le dialog une fois l'écart à 0. Test `rapprochement-detail.test.jsx` (flux pointer→resume, écart 500→0). Frontend pur, zéro migration.

- 2026-07-11 — **VX152 — fin des moteurs de table parallèles (dernier volet, landé seul).** GED (`GedNavigator`/`GedSearch`), `ClientDetailPanel` et OCR (`OcrUpload`) rejoignent le moteur de table déjà utilisé par leur voisin direct : GedNavigator/GedSearch → moteur `DataTable` partagé (GedNavigator via l'échappatoire `renderRow`/`renderHeaderRow` ARC49 pour préserver le DOM testé ; GedSearch en colonnes), `ClientDetailPanel` → primitif `Table` partagé (fin du 3e moteur maison `DocTable` ; plus aucune `<table>` HTML), OcrUpload → NOUVEAU primitif partagé `ui/KeyValueTable` alimenté par un point de rendu UNIQUE de `FIELD_LABELS` (helper `ocrFieldRows`). + volet `RolesManagement` (liste des rôles → `DataTable`, grille de permissions inchangée). Tests de source `node --test` par surface ; tests comportementaux existants (GedNavigator/GedSearch/OcrUpload) verts par préservation du DOM (cases/actions/testids conservés). Frontend pur, zéro migration. Landé SEUL par cherry-pick sur `main` (les autres commits VX de la branche — VX141/146/147/148 — restent en attente : VX141 introduit `DEVIS_TRACK_STAGES` qui fait échouer `check_stages.py`, à traiter séparément). (ROUTINE)

- 2026-07-11 — **PLAN2 clean-lane wave 2 (8 lane-drainers) — 10 tasks folded onto batch, ~15 conflict-heavy tasks dropped+requeued to keep the batch clean.** LANDED : VX61 Web Vitals maison (INP/LCP/CLS/TTFB → endpoint reporting, AUCUNE dépendance) ; VX77 compression photo canvas avant upload terrain ; VX67 StateBlock+Réessayer sur 5 listes ; VX8 accent de couleur par module (7 jetons OKLCH AA) ; VX9 lanceur d'applications (overlay grille, `g a`) ; VX10 apps épinglées Sidebar ; VX11 fil d'Ariane cliquable ; VX12 « Plus » mobile = grille d'apps 2 niveaux ; VX13 hook `useEntitySearch` partagé (GlobalSearch+CommandPalette) ; VX46 « Mes préférences ». Fold-time : Login VX46↔VX65 réconcilié (`?next=` prioritaire sinon atterrissage) ; index.css VX9↔VX15 keep-both ; 6 lints react-hooks/react-refresh corrigés ; 2 tests réparés (vrais timers pour le rejet entityRoutes, requête `/Devis/` ambiguë BottomTabBar). DROPPED+REQUEUED (conflits lourds — reconstruire sur base fusionnée) : lane design VX1–7, crm VX192/VX221, grappe NotificationBell VX14/VX56/VX82, VX19 (sweep ~40 fichiers). Tout validé (eslint + vitest verts).

- 2026-07-11 — **PLAN2 clean-lane wave (8 time-balanced lane-drainers) — 17 tasks folded onto batch.** VX65 lien profond survit à la connexion (`?next=` sûr) ; VX78 vraie page 404 (ui/NotFound) ; VX57 CopilotPanel/Sora paresseux hors chemin froid ; VX58 préchargement au survol des destinations chaudes ; VX37 AgentChat reveal incrémental + mini-tableaux ; VX39 OCR source+extraction côte à côte, édition inline ; VX73 notice i18n honnête (chrome-only) + ⌘/Ctrl K réel ; VX74 [DECISION] note AR = documents-seulement (pas d'UI RTL) ; VX85 file records : snooze non destructif + notifs mentions/réassignation avec deep-link ; **VX101 [AUTH] seul Responsable/Admin décide une approbation installations/contrats (corrige un trou : un rôle normal pouvait décider)** ; **VX72 [DEP/DECISION] Sentry frontend no-op DSN-gaté — AUCUNE dépendance ajoutée (import à specifier variable, activé seulement si Reda installe @sentry/react + pose VITE_SENTRY_DSN)** ; VX115 KPI cockpit → écrans d'action + index des exports ; VX48 [BUG iOS] tous les PDF via onglet pré-ouvert (Safari) ; VX49 détection réelle du blocage popup + gestion d'erreur ; VX30 mur de flotte vivant (statut PR 3 paliers, pouls temps réel visibility-aware) ; VX84 cloche bornée à mes retards (assigned_to=moi) ; VX95 toastWithUndo câblé (archivage leads/stock, drop kanban). Fold-time (orchestrateur) : 5 lints react-hooks corrigés (setState-en-effet→phase de rendu sur Layout/AgentChat/OcrUpload, écriture de ref→effet sur FleetPage/Co2Page) ; **VX72 réparé** (le bare `import('@sentry/react')` cassait le build+6 suites → specifier variable) ; conflits imports LeadsPage/StockList/FactureList résolus en gardant les deux côtés. RE-MIS EN FILE (rebuild propre sur la base fusionnée) : VX97 (conflit massif avec la refonte menu VX20 de DevisList), VX114 (ma résolution take-ours a laissé tomber sa modale d'export → revert), VX116 (bug réel : annuler un aperçu WhatsApp le déclenchait quand même → revert). VX246 [BLOCKED: mal étiqueté @lane apps/records — c'est du frontend/iOS]. VX98 (agent mort erreur API) à reprendre.

- 2026-07-11 — **PLAN2 lane-drain wave (8 time-balanced agents) + tooling — folded onto accumulating batch (target ~60/merge, no per-wave merge).** `plan_lanes.py` gained LPT time-balancing across N workers (task `— S/M/L/XL` size → cost, whole lanes bin-packed so the 8 agents finish together; `--workers` flag; +8 tests). Then 17 tasks recovered from the lane-drainers (a mid-run Claude Code process restart killed the live agents; their COMMITTED work survived on the worktree branches and was cherry-picked): VX213 handoffs AVAL notifiés ; VX195 MapView role=application+liste clavier ; VX234 audit rôles au grain permission + garde réassignation ; VX242 ChangePassword révoque les autres sessions ; VX108 `lib/contactLinks` partagé (tel/wa) + câblage ; VX109 Importer/ExcelImport fournisseurs/équipements ; VX51 champ focalisé au-dessus du clavier iOS (VisualViewport) ; VX92 « Créer un autre » + mort du window.alert paiement ; VX183 densité kb-col iPad ; VX145 header CRM en menu d'actions + SavedViewsBar partagé ; VX218 badge « Nouveau » réception + escalade demandeur ; VX15 ModuleHero+sparklines ; VX137 table de lignes générateur en `ui/Input` ; VX139 `QuoteTotalsSummary` partagé (une seule devise MAD) ; VX20 menus Plus DevisList/RelancesPage/BulkActionBar ; VX21 squelette+cockpit trésorerie FactureList ; VX50 `data-label` FactureList/RelancesPage + garde CI. Fold-time (orchestrateur) : conflits FournisseurFiche360 (VX108↔VX149) et FactureList imports (VX21↔VX184) résolus en gardant les deux ; corrigé le test VX137 (assertion `12.` = artefact jsdom de `type=number`, remis sur le vrai contrat step="any" anti-arrondi) + polyfill ResizeObserver au test VX15. VX252 [BLOCKED: attend VX156 celebrate.js]. VX183 note : part agenda-view reste bloquée sur VX147 (MonthGrid). Reliquats de lanes (tâche en cours à la mort de chaque agent + non démarrées) re-dispatchés.

- 2026-07-11 — **PLAN2 wave 10 (VX113/VX204/VX149/VX43) — folded onto accumulating batch branch (no per-wave merge).** VX113 FiscalitePage : champ exercice = vrai `<select>` (comptaApi.exercices.list). VX204 quatre surfaces d'échec silencieux réparées (ChatterWidget/ActivitiesPanel/Journal getMeta + polling chat/cloche → bannière « Mise à jour interrompue »/Réessayer). VX149 `StatusAccentCard` partagé (kanban+terrain) + micro-pack dédup (InterventionsPage/InstallationsPage/MaJourneePage/FournisseurFiche360/ChantierPhotos/BulkProductBar/ChantierGateTimeline). VX43 gestes terrain : swipe-to-action (LeadCard/DataTable), pull-to-refresh (`usePullToRefresh`+`pullToRefreshMath`), bottom-sheet drag-to-close (Sheet) + MaJourneePage/InterventionsPage side="bottom" <768px. Fold-time : corrigé 5 lints invisibles aux agents sans node_modules — **hook `usePullToRefresh` appelé après un early-return dans InterventionsPage (rules-of-hooks, crash potentiel) hissé avant les returns**, `StatusAccentCard as:Comp`→`const Comp=as`, helpers swipe LeadCard dé-`export`és (react-refresh) + `SWIPE_OPEN_THRESHOLD` mort supprimé, directive `exhaustive-deps` inutile retirée de Journal. Conflits index.css (VX149↔VX204) + MaJourneePage/InterventionsPage (VX43↔VX149) auto-mergés.

- 2026-07-11 — **PLAN2 wave 9 (VX64/VX184/VX126/VX144), 4 lanes.** VX64 error boundaries sur les routes nues (/, /landing, /login, /ui, + flux publics tokenisés e-sign/kiosque/portail) → écran FR de récupération au lieu d'une page blanche sur un throw de rendu. VX184 tables produit de DevisForm/FactureForm migrées vers le pattern responsive partagé `.lines-table`/`data-label` (fin du scroll horizontal permanent mobile ; carte empilée <768px comme le générateur ; aucun changement >768px). VX126 utilitaire `press` partagé (mirroir de la courbe cubic-bezier de Button) appliqué à 12 primitives (Switch/Slider/Segmented/Tabs/Checkbox/RadioGroup/Select/Combobox/MultiSelect/DropdownMenu/ContextMenu/DatePicker) + Progress, halos/squish gated `hover:hover`, indicateurs `animate-pop-in`. VX144 (scope « rogné » (c)(d)(e), (a)(b) exclus car recoupent VX24/VX7) : cellule Client empilée déterministe à 200px (nom+toggle ligne 1, badge ICE ligne 2), note « non datés » du CalendarView en `var(--warning)`+AlertTriangle, carte funnel « Leads par étape » pleine largeur ≥1100px. Fold-time (orchestrateur) : corrigé la régression QX28 (VX143 avait dédupliqué le bouton 3D → test source-grep « deux occurrences » ramené à une) et ajouté un polyfill `ResizeObserver` au test interaction (Radix Slider). 3 agents morts d'erreur API (VX184/VX126/VX144, 0 commit) re-dispatchés à neuf — état partiel non fiable jeté. Conflits ClientList.jsx/index.css auto-mergés proprement (abort VX55 + cellule VX144 préservés).

- 2026-07-11 — **PLAN2 wave 8 (VX119/VX100/VX143/VX196), 4 lanes.** VX119 outbox terrain : une op rejetée par le serveur est désormais RETENUE (marquée `serverError`+`attempts`, jamais purgée en silence), badge rouge « N action(s) en échec » avec message par op + bouton Abandonner (`failed()`/`discard()`). VX100 approbations : montant réel (`DemandeAchat.montant_estime`) + lien non-fabriqué exposés dans l'agrégateur, `?trier=montant` réordonne vraiment, colonne Montant (`formatMAD`) + libellé cliquable dans ApprobationsPage. VX143 LeadForm refondu sur le langage composable FormSection/FormField/Input (comme ClientForm), rail tokenisé + badge Doublons, bouton toiture-3D dédupliqué, `STAGE_LABELS/PRIORITE_LABELS/TYPE_INSTALLATION_LABELS` importés de features/crm/stages.js (miroir STAGES.py) au lieu d'un doublon local. VX196 a11y WCAG 4.1.3 : régions live `role="log"`/`aria-live` + thread scrollable au clavier sur MessageThread & ChatterWidget, toasts d'erreur `assertive` (pont pub-sub vers une région `role="alert"` montée par Toaster, sonner n'exposant qu'une seule région polite). Fold conflict-free (seul index.css de VX143 auto-mergé vs wave 7). NOTE VX196 : item (c) drag-kanban `role="status"` hors périmètre (KanbanView/LeadsPage non nommés) — laissé pour un suivi.

- 2026-07-11 — **PLAN2 wave 7 (VX120/VX124/VX112/VX42), 4 lanes.** VX120 2FA : QR rendu serveur en SVG inline (via `apps/stock/labels.qr_svg`, aucune migration) au lieu d'un `<img src="api.qrserver.com">` tiers qui fuitait le secret TOTP + était bloqué par la CSP prod ; helper `lib/trustedSvg.js` (validation anti-script/on*/javascript:) + fallback gracieux. VX124 finitions design (caret brass sur Input/Textarea, ombre primary-hover, tabular-nums serrés, keyframe stat-solidify neutralisée sous reduced-motion). VX112 balance âgée : action ligne « Relancer » → `/ventes/relances?client=<id>` (RelancesPage lit `?client=`, badge « filtré » effaçable), PDF « Relevé » intact. VX42 terrain un-tap : boutons appeler/naviguer ≥44px, rail d'onglets icône+libellé + bandeau « Prochaine action », `FloatingActionButton` (safe-area) sur Ma journée/Numériser/Leads, retour haptique défensif (`lib/haptics.js`). Fold-time (orchestrateur, opus) : **corrigé un bug latent APP-WIDE — `<Button asChild>` crashait sous react-slot 1.3.0** (Slot exige `Children.count===1`, or Button passait `[false, enfant]`) ; le fragment spinner+enfants n'est désormais émis que hors-asChild — surfacé par le test « Relancer » de VX112. Corrigé aussi 3 défauts VX42 (EmptyState attend un composant pas un élément ; hoisting via `vi.hoisted` ; setState-en-effet → remount par `key`). Conflits LeadsPage.jsx/index.css (vs wave 6) auto-mergés proprement.

- 2026-07-11 — **PLAN2 wave 6 (VX55/VX60/VX86/VX31), 4 lanes file-disjoint.** VX55 discipline réseau : `timeout:20000` + branche `ECONNABORTED` (toast FR « La connexion a expiré ») sur l'instance axios, annulation native via `createAsyncThunk {signal}` + `thunk.abort()` au cleanup sur LeadsPage/DevisList/ClientList (RTK natif, câblage rétro-compatible des call-sites getLeads/getClients/getDevis). VX60 gate e2e « comptes justes » : seed >100 produits + >100 devis via `page.request`+cookie admin, asserte badge catalogue / KPI Dashboard / « N devis au total » = total réel (verrouille VX54), nettoyage `afterAll` pour ne pas polluer la base seed_demo. VX86 signal ambiant approbations : hook partagé `useApprobationsCount()` → badge sidebar + carte Dashboard « Attend votre décision » (top-3 urgence) + rangée cloche, tout masqué à 0. VX31 SAV boîte de réception : split-view liste+détail persistant ≥1280px (aside sticky), `Sheet` conservé en fallback mobile via `useIsMobile`, contenu factorisé identique. Folded conflict-free (frontend pur, zéro migration).

- 2026-07-11 — **PLAN2 wave (VX54/VX75/VX35/VX80).** VX54 pagination bornée-parallèle partagée (fin de la troncature page-1 silencieuse sur stock/ventes/crm/installations/sav) — débloque VX60. VX75 consolidation formatage argent/date sur lib/format.js (~90 sites / 51 fichiers) + garde CI toLocaleString ; bug CatalogueTable 450.00 vs 450,00 MAD corrigé (test mis à jour). VX35 Paramètres en barre latérale groupée (6 familles). VX80 feuille d'impression globale + boutons Imprimer (Devis/Facture/Chantier ; CSS print seulement, rule #4 intacte).

- 2026-07-11 — **PLAN2 wave (VX34/VX79).** VX34 Login tokenisé (OKLCH/lucide/reduced-motion). VX79 deep-links internes + « Lien interne » (Chantiers/SAV/Devis ; aria-label distinct du bouton WR2 « Copier le lien » de proposition — pas de collision de rôle ; rule #4 préservée). VX81 (noms d'export horodatés) re-mis en file : son mock global de document.createElement casse le DOM React (HierarchyRequestError) et régresse des tests PilotageStock existants — à reprendre avec un spy ciblé HTMLAnchorElement.

- 2026-07-11 — **PLAN2 wave (VX83/VX53).** VX83 « Ma file » file de travail unifiée reconstruite ADDITIVEMENT (ZSAL1/QX25/P167 préservés, node --test 8/0). VX53 compat hover (@media hover:hover ×68), dvh, images lazy hors-écran, toasts de copie. VX199 (AUTH ventes_valider) re-mis en file : la garde échoue encore (rôle read+write reçoit 200/400 au lieu de 403) — nécessite un test DB réel, HasPermissionOrLegacy à déboguer (has_erp_permission vs is_responsable).

- 2026-07-11 — **PLAN2 drain wave (6 lanes): VX76/VX157/VX96/VX59/VX32 + VX99 partial.** VX76 email HTML brandé, VX157 dashboards/monitoring tokenisés, VX96 Lead soft-delete réversible (+crm 0054), VX59 fuite chemin absolu chunk roof-tool corrigée (vite), VX32 CartePage tokenisée + tuiles dark-mode, VX99 notifications d'approbation installations.DemandeAchat + ged.DemandeApprobation (2/3). VX199 (AUTH accepter/emettre) et VX83 (« Ma file ») re-mis en file : VX199 a un bug de garde (403 manquant pour rôle read+write) et VX83 a régressé MesActivites (ZSAL1/QX25/P167) — à reprendre.

- 2026-07-10 — **Quote-journey ROUND 6 batch (QW8 + QX1–QX42 + QX7d + VX16/17/18) — 46 tasks shipped in one batch, 4 parallel worktree lanes.** Scoped run over the whole quote journey. Verified every task against real code first: **QW7 was already built** (webhook engagement-ping guard) → ticked « already present »; QF/QG/QP/QK/QJ were already drained (in DONE.md). QXG1–5 stay GATED (founder account/data/content). Lanes: (1) CRM intake — QX14 persist Lead.score on webhook leads, QX15 callback SLA clock on contact_preference_set_at, QX35 parrainage end-to-end, QX16 payload-replay surface, QX17 phone dedup, QX18 darija→langue_document, QX42 PII retention. (2) Ventes backend — **QX1 [CRITICAL] remise_globale now reaches the whole billing chain** (over-billing fixed, Facture totals gate on remise so 0-discount invoices stay byte-identical), QX2 discount in reporting/CAPI/UBL, **QX3 [SECURITY] fail-closed payments** (NoOp verify_webhook returns paid:False), QX9 real e-sign evidence + consent-400, QX10 OTP honest stub + lockout, QX11 scheduled 11 dead beat jobs + reachability guard, QX36 inbound-email wiring, QX13 visible nudges + shared client-links helper, QX30 engagement-triggered follow-up (race-safe), QX31 hot-lead escalation + time-to-first-touch, QX41 public hardening, QX33 deposit-at-signature, QX34 /suivi milestone endpoint, QX21 atomic devis save, QX22 truthful Envoyé, QX23 marge_snapshot (manager-only, never client), QX24 étude no longer goes stale, QX32/QX12/QX25 backend halves. (3) Quote engine (rule #4 — engine only renders) — QX4 de-Taqinorized residential PDF (+CompanyProfile capital/gerant/site_url), QX5 phantom-option gating, QX6 sign-QR→live proposal + real page numbers, QX7 numbers honesty (a/b/c/e) + **QX7d** unified avoided-kWh price (tranche-aware, not flat 1.75), QX8 warm-path caching, QX38 ONE canonical PVGIS productible (screen==PDF==web), QX39 honest 25-yr cashflow, QX40 pompage phase/voltage sanity, QX19/QX20 generator consumes lead data + equipment gate, VX16 summary rail, VX17 dark-mode tokens, VX18 DevisPresetPanel wired. (4) Frontend — QX12 deep-links, QX21/QX22 devis flows, QX26 structured loss reasons, QX27 action menu + typed chatter, QX28 readiness chips, QX29 « Relances du jour » board, QX25 call-ready rows, QX31 first-touch timer, QX30/QX32 timelines. Folded conflict-free (linear migrations: crm 0050-51, ventes 0075-77, notifications 0031-33, core 0027, parametres 0055). Adversarial review of the critical money/security/e-sign/webhook changes passed. NOTE: QX13 manual-contact suppression uses an optional crm selector `lead_recent_manual_contact` not yet added — inert until then (relance_date + engagement suppression work now).
- 2026-07-09 — **VX102 (built directly, founder request): « Demandes d'achat » frontend (FG310).** New `/chantiers/demandes-achat` page — DataTable list + create dialog (chantier, lines produit/désignation/quantité/prix estimé, priorité, date besoin), « Soumettre » on drafts, inline Approuver/Refuser shown only to the responsable/admin tier — reusing the existing installations endpoints (no backend change; a role-bearing technicien already passes create). Wired into router + Sidebar CHANTIERS; 4 vitest cases green, ESLint clean, vite build green. The FG310 approval box now receives real installations-sourced items. NOTE: the loose `IsResponsableOrAdmin`/`is_responsable` backend gate remains the systemic under-gating tracked by VX101; NTP2P3 (DemandeAchat form) is now largely satisfied — verify-not-already-built before a future NT run.
- 2026-06-20 — Logo resolved: the OS uses the official Taqinor wordmark (the repo's quote-engine logo) as product branding — real logo on the Login screen + iOS splash screens generated from it (`gen_brand_assets.py`), PWA icons already from its glyph; fixed the web-push notification icon path. Sidebar keeps the per-tenant company name.
- 2026-06-20 — G10 (first half) verified already-present: the lead model already carries `fbclid` + `utm_source/medium/campaign/content/term` (crm migration 0006), the website lead webhook maps and stores them (`apps/crm/webhooks.py`), and `apps/web` captures first-touch fbclid+UTM from the landing URL and submits them (`Layout.astro`, `lib/lead.ts`), covered by `apps/crm/tests_webhook.py`. Ticked `[x] (already present)`. The CAPI SEND (second half) stays gated on Reda's Meta pixel token.
- 2026-06-21 — Group Q (Q1–Q7) shipped: Devis↔Toiture-3D pipeline backend — Devis.roof_layout + layout endpoints, Lead roof_point/outline/bill_kwh + per-lead token, build_devis_from_layout() service, roof-image MinIO storage, layout-aware quote data (no-layout path byte-identical, rule #4), tokenized /proposal data endpoint + tokenized e-sign accept (reuses the existing acceptance service).
- 2026-06-21 — Group R agent framework (AG1–AG12) shipped: apps/agent registry + catalogue endpoint (AG1, NEW APP), FastAPI registry-driven tools with propose→confirm + signed-Redis stash + /confirm (AG2) and proposal/result surfaced on /query, assistant confirm/result cards (AG3), quote/invoice/payment + CRM/stock/SAV/installations agent actions (AG4–AG9), and the voice layer — Groq-Whisper transcribe endpoint (AG10, reuses GROQ_API_KEY) + voice input & hands-free conversation mode with a tested no-auto-confirm guard (AG11/AG12).
- 2026-06-21 — Group S internal team chat 'Discuss' (S1–S20) shipped: apps/chat (NEW APP) models/serializers/viewsets with strict company+membership scoping, read-state/unread, search, attachments+voice upload, reactions, pins, share-a-record via selectors, notifications+mute; self-hosted faster-whisper transcribe (S10, NEW founder-approved dep) + Django transcription pipeline (S11); full React UI (API client+slice+smart-polling, route/nav/bell, conversation list, thread, composer+@mentions, voice memos, reactions+pin UI, share-record cards, new-DM/channel/manage-members). Frontend↔backend API contract reconciled + mute/members/leave endpoints + mention persistence added.
- 2026-06-21 — Design & UI polish: F120–F123 (OKLCH brand ramps at ΔE≈0, type scale + tabular/slashed-zero numerals, elevation tokens + focus ring, dark-mode lightness ladder), G124–G128 (Tooltip/Button/IconButton/selectors/Form/DatePicker/TimePicker states+tokens, backward-compatible), and reporting K147/N161/K148/K149/J146/P167 (token-only accessible chart kit, dashboard KPI cards, fr-MA compact MAD formatting, unified table primitive).
- 2026-06-21 — P171 (ARCH): DataTable engine migrated to @tanstack/react-table behind an unchanged public API with full test parity (36 logic tests unchanged + 10 new engine-parity tests).
- 2026-06-21 — Policy: recorded founder standing consent (Reda) in CLAUDE.md lifting the ARCH/AUTH/COST/DECISION/GALLERY/DEP auto-skip gate (the five non-negotiable rules preserved).
- 2026-06-21 — BLOCKED & carried: S21 (real-time WebSocket/Channels) needs founder-provisioned ASGI+nginx-WS+Redis-channel-layer infra; I134/I138 (⌘K palette + shortcuts) need an architectural decision to reconcile with the already-wired providers/CommandPalette layer.
- 2026-06-21 — World-class look-and-feel wave (34 tasks) shipped in 2 tiers of parallel worktree lanes. Tier 1 (foundation): H129–H133+M154+N160+N162+O164+O166 premium DataTable (tabular nums, column pinning, row affordances + kebab/⌘K, floating bulk bar, perceived-perf skeletons, mobile card fallback, role=grid a11y, non-drag reorder, virtualization, memoised widths); I135–I137+L150+M155+M156+N159+N163+P168 calm sidebar/header/breadcrumbs + motion-token adoption + touch/safe-area pass + bottom-nav polish + never-hidden focus + reduced-motion + vitest-axe a11y tests + lucide icons; L151 useOptimisticSave + L153 useDelayedLoading + Skeleton variants; L152 confirm/toast helper (wraps existing ConfirmProvider); M158 ResponsiveDialog (Dialog↔Sheet); M157 PWA iOS polish; O165 route code-splitting (already lazy — locked with a contract test).
- 2026-06-21 — Tier 2 (page adoptions): J139 Clients + J140 Leads (STAGES-keyed, tokenised palettes, StatusPill, no-drag keyboard stage move, optimistic stage/status saves) + P169 inline-style removal; J141 Devis list/detail polish (skeletons, StatusPill, PDF + generator input-freedom untouched); J142 Stock catalogue → virtualised DataTable; J143 Installations skeletons + mobile; J144 SAV test coverage + StatusPill; J145 Admin Users → DataTable (ResponsiveDialog edit); P170 living /ui style guide. All e2e DOM-hook contracts preserved; ESLint 0 errors; node:test 322 pass; vitest 54 files/302 pass.
- 2026-06-22 — I134 (⌘K palette) shipped: reconciled with the live `providers/CommandPalette.jsx` (KEEP BOTH per founder note — no rebuild). Added a « Actions » navigation mode (derived from the `g x` shortcuts, single source of truth) + a « Récents » section of opened entities + a per-row shortcut chip. Pure logic extracted to `providers/commandActions.js` and unit-tested (`commandActions.test.mjs`, node:test, 5 cases). ⌘K stays single-bound (Header button + global shortcut only).
- 2026-06-22 — I138 ticked `[x] (already present)`: the live `providers/ShortcutsProvider.jsx` + `shortcuts.js` already deliver the Done bar — `?` help overlay + `g`-prefix navigation sequences + tests (`shortcuts.test.mjs`). The palette shortcut chips it referenced now ship via I134; `j/k` list traversal was a prose extra, not part of the Done bar.
- 2026-06-23 — Group U (U1–U14) shipped in 10 parallel worktree lanes, one self-merge. Per-task:
- 2026-06-23 — U1: lead edit modal now keeps the window open on « Mettre à jour » (in-place re-hydrate + « Enregistré » confirm), so a devis generated right after appears inline in LeadDevisPanel without reopening. (ROUTINE)
- 2026-06-23 — U2: fixed the ERP-wide mouse-wheel scroll regression — root cause was `overflow-x:hidden` creating an implicit scroll container + an unbounded `min-height:100vh` chain; switched to `overflow-x:clip` + bounded `#root`/`.layout` height + `min-height:0` on `.layout-content`, guard comments added. (ROUTINE)
- 2026-06-23 — U3: fixed mobile header overlap/stacking — `isolation:isolate` + `env(safe-area-inset-top)` + flex alignment so the header is one clean row under the notch; ⌘K hidden on mobile (duplicates the search loupe). (ROUTINE)
- 2026-06-23 — U4 (AUTH — a CRM action now changes a document status): WhatsApp-sharing a brouillon devis flips it to « envoyé » through the one status path (new `mark_devis_sent` service), stamps `date_envoi`, and advances the lead funnel to QUOTE_SENT via a NEW `core/events.py` `devis_sent` event (crm subscribes) — idempotent, never downgrades accepté/refusé. Additive migration `0027_devis_date_envoi`. (AUTH)
- 2026-06-23 — U5: the Devis list now surfaces the generated facture(s) + bon-de-commande inline as clickable chips (read-only serializer fields, no new write path). (ROUTINE)
- 2026-06-23 — U6 (ARCH — new cross-app event reaction): accepting a devis now auto-creates its chantier once (idempotent, company-scoped) via `apps/installations` subscribing to the existing `devis_accepted` event — no ventes→installations import. (ARCH)
- 2026-06-23 — U7: superseded devis revisions (`is_active=false`) are hidden by default with a « Voir les versions remplacées » toggle; shown rows are badged « Remplacé » + linked to the current version. (ROUTINE)
- 2026-06-23 — U8: the devis detail now shows its bon-commande status and warns when a devis is `accepté` but its BC is `annulé`/missing. (ROUTINE)
- 2026-06-23 — U9 (SCHEMA — stock side-effects on a new trigger): invoicing a devis directly via the échéancier `generer-facture` path now reserves/consumes stock once (mirrors the BC delivery path, same insufficient-stock guard), never double-counting when a BC already delivered. No migration. (SCHEMA)
- 2026-06-23 — U10: fully paying a facture now resets its relance/dunning escalation (clears `prochaine_relance`, neutralises the automatic RelanceLog counter, history preserved) so a paid invoice stops looking overdue. (ROUTINE)
- 2026-06-23 — U11 (DECISION — founder call, built FLAG-ONLY): a lead left at SIGNED whose only accepted devis is later refused is now flagged (`lead_signe_sans_devis_actif` derived flag + a chatter note via a `devis_refused` receiver) rather than silently receded — per rule #2 the funnel stays a separate layer. FOUNDER: confirm whether you want the stage to actually recede instead of just flag. (DECISION)
- 2026-06-23 — U12 (SCHEMA — additive nullable FK): Facture + BonCommande now carry a direct nullable `lead` FK (`crm.Lead`, SET_NULL, string-FK, snapshotted at creation), so a lead's documents are directly queryable even if the devis is deleted. Additive migration `0028_boncommande_lead_facture_lead` (renumbered from 0027 at fold to chain after U4's migration). related_names `factures_directes`/`bons_commande_directs`. (SCHEMA)
- 2026-06-23 — U13: profile-picture upload fixed end-to-end — avatars were served on an unreachable internal `minio:9000` presigned URL; now streamed through a new same-origin Django proxy `GET /api/django/users/avatar-image/` (mirrors the records attachment proxy), with an initials fallback on error. (ROUTINE)
- 2026-06-23 — U14: the « Documents (GED) » menu is now usable — create-cabinet/folder, rename/move, and document upload affordances + empty-state CTAs, wired to a thin company-scoped multipart action `POST /ged/documents/televerser/` reusing `records.storage`. (ROUTINE)
- 2026-07-02 — **Big PLAN2 drain (66 tasks) shipped in ONE run, one self-merge.** Groups: **QF1–9** (real-bill two-bills par-tranche savings screen==PDF, avec/sans-batterie honesty, Huawei-only Smart-Meter/Wifi), **QG1–12** (auto-open PDF, edit-invalidates-cache, inline new client/product role-gated, creator name+phone on quote, « Envoyer »=WhatsApp flow, configurable variante %, 3-variante dialog, embedded + standalone 3D RoofViewer), **QK1–6** (webhook keeps all captured lead data + new qualif fields, scoring uses them, financing block on PDF, « Nos hypothèses » transparency, dead /avis link→/realisations, bill-photo OCR), **QD1–2** (bigger invoice logo + clean client-bearing filenames), **QP1–2** (picker slot-type filter, role-gated line rename vs clone-to-stock), **QS1–4** (BCF PDF fix, inline product, WhatsApp+email supplier send), **QJ26–31** (roof-layout in proposal, «être contacté»/«contacter mon supérieur» notify handler+superior, multi-villa ×N/grouped one-document quote), **CH1–6** (international PV lifecycle gate model, blocking gates, IEC 62446-1 commissioning, handover pack, Directeur config, guided timeline UI), **MB1–6** (mobile shell clearance/overflow/z-index tokens, responsive modals, page sweep, Playwright mobile gate), **WR1–12** (funnel-integrity Refuser fix + surfaced ventes/stock/monitoring/CRM/SAV/paramètres orphaned backend features), **QC1** (own-data Moroccan company autocomplete + registry deep-links, provider seam). SCHEMA/AUTH highlights: ventes 0046 (multi-villa) + 0047 (BCF ShareLink), crm 0034 (lead qualif), parametres 0030 (variante %), notifications 0011/0012, installations 0049–0051 (gates) + 0052 (DC34), stock 0028 (DC34). **DC34** = destructive sous-traitant AP unification onto stock.Fournisseur(type)+SousTraitantProfile via FactureFournisseur/PaiementFournisseur (reversible data migration). **QG4** (AUTH) restricted product-create to Directeur + Commercial responsable — **FOUNDER: confirm Administrateur should lose product-create**. GATED/not built: **QC2** (paid Inforisk/Charika registry API — needs founder account). Validated pre-merge: makemigrations --check clean, flake8 + compileall clean, frontend eslint + vite build + 480 node tests green, combined docker test over affected apps.
