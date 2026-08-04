# TAQINOR OS — Done tasks archive (condensed)

> Archive condensée des tâches terminées — juste assez pour comprendre l'histoire.
> Le texte intégral de chaque tâche archivée vit dans l'historique git (les fichiers plan eux-mêmes et l'ancien `docs/DONE.md`).
> Maintenu par la commande « clean the plans » (CLAUDE.md). Dernier passage : 2026-08-04.

<!-- plan-progress-ledger v1 — NE PAS ÉDITER À LA MAIN.
     Compte des tâches [x] archivées par préfixe d'ID, provenant des fichiers scannés par
     scripts/plan_progress.py (PLAN.md, PLAN2.md, new_tasks_plan.md, FRONTEND_GAP_PLAN.md).
     Lu par plan_progress.py : l'archivage ne fait jamais retomber la complétude
     BUILD_ORDER.yml d'un groupe livré. Maintenu par « clean the plans ».
ADSDEEP=66
ADSENG=53
ADSENGINT=3
AGEN=10
AOF=194
APX=36
ARC=56
ASG=8
DC=1
ENG=31
EZ=16
FE-XKB=1
FE-YHARD=1
FG=1
LB=55
LW=45
NTAPI=14
NTEDU=24
NTEXT=3
NTIDE=40
NTMOB=2
NTPLT=41
NTPRT=2
NTSAN=20
NTSEC=21
NTUX=18
ODX=12
ODY=33
PACT=6
PUB=107
QPERF=1
QW=1
QX=52
SCA=49
SIG=4
VAO=1
VX=223
WIR=165
XMFG=3
XMKT=4
XPLT=4
XPOS=1
XSAL=3
XSAV=1
XSTK=2
YAPIC=12
YDATA=20
YHARD=2
YOPSB=1
YRBAC=5
YSERV=4
YTEST=5
ZFAC=1
ZMFG=1
ZSAL=1
ZSTK=2
-->

## Archived from docs/PLAN.md — 2026-08-04

### Active regressions — fix first (added 2026-06-18, top priority)
Two live-production regressions were flagged top-of-queue; the query-budget fix shipped (landed via
SCA43's contextvar company-config cache). Header + prose removed as narrative about now-shipped work.
QPERF1

### N1-N102 / F1-F24 / M1-M7 / FG1-FG106 / FG107-FG399 round 2 / NEW MODULES deep-dives / DATA-CONNECTIVITY / Group UX
Six 2026-06 audit/spec batches drained to zero open tasks: the post-sale/procurement N-series empty
category labels, the field-execution module (F1-F24) intro, modularity/decoupling (M1-M7), two
feature-gap sweeps (FG1-399), the PAIE/COMPTA/PROJ/GED/FLOTTE/QHSE/CONTRAT/KB/LITIGE module deep-dive
specs (rationale only, task IDs live in the domain plan files), the single-source-of-truth audit
(DC1-42), and the backend-only-module frontend Group UX. Headers removed as narrative about archived
or elsewhere-tracked work; only two IDs were directly checked off under these headers.
FG386, DC34

### Groupe ODX + best-ERP-parity X* groups (partial — ODX/XACC/XPOS/XKB headers stay, still hold open work)
ODX1-23 module-split shipped its bulk. XSTK/XMFG/XSAL/XMKT/XSAV/XPLT groups fully drained; their
now-empty headers removed. XFAC/XPUR/XPRJ/XFSM/XCTR/XFLT/XQHS/XRH/XPAI/XGED headers also removed —
zero tasks were ever filed under them (pure gap-analysis rationale, "nothing missing here" prose).
ODX1, ODX5, ODX6, ODX7, ODX11, ODX12, ODX13, ODX15, ODX16, ODX17, ODX19, ODX23
XSTK18, XSTK20 · XMFG17-XMFG19 · XSAL5, XSAL14, XSAL15 · XMKT10, XMKT34-XMKT36 · XSAV22
XPLT12, XPLT19-XPLT21 · XPOS17

### Round 2 — câblage bout-en-bout, bonnes pratiques mondiales, parité Odoo grain fin (Y*/Z*/YHARD)
The 2026-07-03 ~90-agent multi-lane audit closed nearly all of Axis A (end-to-end process wiring),
all of Axis B (RBAC/API/ops/test/data-integrity engineering practices) and all of Axis C (14-app Odoo
fine-grain parity), plus the YHARD platform-hardening critique. Only YCASH (Lead-to-Cash) kept one
open hand-off, so its header and the "Axe A" divider stay; everything else (YPROC, YSERV, YLEDG,
YHIRE, YSTCK, YDOCF, YLEAD, YSUBS, YEVNT, the Axe B + Axe C + Durcissement dividers, YRBAC, YAPIC,
YOPSB, YTEST, YDATA, ZACC, ZFAC, ZSAL, ZPUR, ZSTK, ZMFG, ZPRJ, ZFSM, ZSAV, ZRH, ZPAI, ZMKT, ZGED,
ZCTR, YHARD) fully drained and removed.
YSERV4, YSERV8, YSERV10, YSERV11 · YRBAC3, YRBAC10-YRBAC12 · YAPIC1-YAPIC12 · YOPSB11
YTEST4-YTEST6, YTEST10, YTEST11 · YDATA1-4, YDATA6-8, YDATA10-22 (20 total, YDATA5/9 never existed)
ZFAC11 · ZSAL9 · ZSTK5, ZSTK13 · ZMFG9 · YHARD1, YHARD9

### Groupe ARC — Socle plateforme & simplification d'architecture (ARC1-ARC56)
2026-07-07 Fable-orchestrated audit built the shared tenancy model, base viewset, tiers referential,
platform manifest registry, dev/frontend scaffolders and consolidated governance guards across
sections A-F. Fully shipped; whole section (header, intro, all 6 sub-headers) removed.
ARC1-ARC56 — all 56, sections A (ARC1-16) through F (ARC53-56), all shipped

### Groupe SCA + Meta Ads engine (SCA1-SCA49, ENG, ADSENG, ASG, AGEN, SIG)
2026-07-09 round-2 audit (build-order governance, measured capacity, tenant lifecycle, white-label,
DocumentMetier kit, money-path perf, revenue-loop, data-moat signal) plus the Meta Ads engine work
appended under the same ## header: the ERP-hosted ads engine (mirrors, propose→approve→apply,
creative factory), the autonomous bandit+guardian+treasury+attribution engine, the living assumption
tree, autonomous creative generation (tiers A/B/C), and multi-signal health scores/guardrails. All
fully shipped; entire section removed.
SCA1-SCA49 — all 8 sub-sections A-H
ENG1-ENG31 · ADSENG1-ADSENG53, ADSENGINT1-3, ADSDEEP1-66 (Publicité niveau concurrent) · ASG1-8
AGEN1-10 · SIG1-4

### Groupe WIR — Audit câblage & données 2026-07-18 (WIR1-WIR168)
Wiring/data audit across 4 waves (broken paths & silent loss, built-but-unreachable, data
centralization, dark-backend interfaces) — all 168 tasks shipped across two drain runs (2026-07-18
and 2026-07-19). Whole section removed.
WIR1-WIR168 — all 4 sub-waves P0 (WIR1-11), P1 (WIR12-80), P2 (WIR81-98), P3 (WIR99-168)

### Groupe AOF — App « Appel d'offres » (AOF1-AOF194)
The full 194-task calepinage + submission-dossier build (data model, shared calepinage engine, A3
plate rendering, 3 plan-entry doors + workshop, document factory with inverse price cascade,
economics, integrations, submission screens, tests/e2e) shipped complete 2026-08-01, verified against
the real FRDISI case. The AOF header + its provenance/constraints intro stay — they still carry live
standing conventions (path format, lane plan, build-order gating) plus the one prose mention of the
`[BLOCKED: attend <ID>]` tag convention. The 11 wave sub-headers (W0-W10), now fully drained, removed.
AOF1-AOF194 — all 11 waves, W0 (AOF1-11) through W10 (AOF183-194)

### PACT §A / §C — partial (both headers stay, still hold open work)
Of the front↔back contract guards (§A, PACT1-9) and the verified-defects list (§C, PACT15-27), the
two guard scripts (contract + shape checkers) and two early logged defects shipped. §A still holds
PACT5-9, §C still holds PACT17-27 — headers and intro prose untouched.
PACT1, PACT2, PACT3, PACT4 · PACT15, PACT16

### WOW — COMPLETE (WOW1-26)
The 2026-07-08 way-of-working overhaul (CI gate 2h15 → 45.5min → 41min → ~6-10min via parallel
sharding + migrated-DB cache-restore) is fully shipped and already detailed in docs/DONE.md; the
pointer section (header + summary blockquote) removed as pure narrative about archived work.
(no PLAN.md checkbox IDs here — WOW1-26 were never `- [x]` lines in this file, only narrated)

### MANUAL — one item shipped
YRBAC13 (fine-grain @action permissions for compta/marketing viewsets, batch-4 debt) shipped. The
MANUAL header and Reda's/Meryem's list of outstanding real-world reminders (ICE/IF/RC, OSP pump
prices, stock quantities, Article 33 outreach, DEBUG toggle, etc.) stay untouched — none of those are
code tasks.
YRBAC13

### DONE LOG digest
100+ dated entries spanning 2026-06-18 through 2026-08-03 condensed into the group stories above:
notably the WOW CI-speed overhaul, the M1-M7/ARC/SCA architecture waves, the ADSENG/ADSDEEP/ASG/AGEN/
SIG ads-engine build, the WIR wiring audit (2 waves), the AOF Appel d'offres app (batches 1-2 then
complete), and the 2026-08-03 PACT front↔back contract-guard incident response (the AO dashboard
production crash that spawned PACT1-187). Six entries were left in place verbatim in the active file
(not condensed) because each contains a literal `[BLOCKED` substring that this cleanup's mechanical
pending-line count treats as protected text, even though every one is historical narrative, not an
open task: the 2026-07-16 adsengine batch note, the 2026-07-12 backend/sav union note, the 2026-07-12
ODX7 unblock note, the 2026-07-01 compta batch note, the 2026-07-03 GROS RUN note, and the 2026-07-12
N102-left-open note.

## Archived from docs/PLAN2.md — 2026-08-04

Pure housekeeping pass: relocates every checked (`[x]`) task and the emptied menu headers/prose
that owned zero remaining pending work. No task was built, reworded, reordered, or moved between
queues. All GATED sections, the "NE PAS FAIRE (Groupe VXD)" section, and every still-pending task
were left byte-identical in `docs/PLAN2.md`.

### Groupe PUB — Publicité niveau best-in-class (audit fondateur 2026-07-19)
14-agent audit closing the "founder never reopens Ads Manager" loop across wiring, brain, business
loop, console, growth, creative, science and finance. Shipped in 2 worktree batches (2026-07-19),
107 tasks, one merge each. Remaining GATED items (PUB107-135, PUB-P8) stayed untouched in PLAN2.md.
- P0 wiring: PUB1-14, PUB115
- P1 brain: PUB15-25, PUB39
- P2 business loop: PUB26-38
- P3 console: PUB40-57
- P4 growth: PUB58-69
- P5 creative: PUB70-85
- P6 science: PUB86-95
- P7 finance/platform: PUB96-106

### Group QJ — Quote-journey best-in-world (2026-06-24)
25-task ERP-half build (speed-to-lead, e-sign, seller efficiency, gated WhatsApp/payment/imagery,
3D proposal). All 25 shipped 2026-06-25 in one batch; the file held only narrative + nested DONE
LOG prose (no live `[x]` checkboxes remained to relocate). One residual note (VX203, still `[BLOCKED`
pending elsewhere) was kept in place in PLAN2.md rather than archived, to avoid touching pending work.

### Group QW — Quote-journey wiring completion (2026-07-05 forensic audit)
Closed the gap where the website sent signals (capture fields, callback requests) the ERP never
received. QW7 was a live lead-name data-corruption bug. IDs: QW7, QW8.

### TOP PRIORITÉ — 3 bugs constructibles + 1 alerte sécurité (CANDIDAT BUILD)
Pre-VX-audit priority fixes, all shipped. IDs: VX117-120.

### Group U / Group Q / Group R — founder requests (2026-06-21/22)
Group U (field UX + document-status "connections", U1-14), Group Q (Devis↔Toiture-3D backend
pipeline, Q1-7), Group R (registry-driven AI assistant actions, AG1-12) — all fully shipped per the
final DONE LOG; their checkbox lines had already been cleared in an earlier pass, only narrative
prose remained, now removed as archived-work commentary.

### Group QF/QG/QS/QD/QP/CH/QK/MB/WR — founder requests (2026-07-01)
Nine founder-request clusters (quote fidelity, generator UX, supplier BC, PDF polish, line-product
handling, chantier lifecycle redesign, quote-journey audit gaps, mobile rendering, orphaned-backend
wiring) — all shipped in the "Big PLAN2 drain" batch (2026-07-02, 66 tasks, one merge): QF1-9,
QG1-12, QS1-4, QD1-2, QP1-2, CH1-6, QK1-6, MB1-6, WR1-12. Checkbox lines were already cleared
before this pass; only narrative/constraint prose remained, now removed.

### Groupe LW — Lead Workspace (fondateur 2026-07-18)
Rebuilt the lead detail screen as a 3-zone cockpit (`useLeadDraft` engine, identity rail, context
rail, autosave, pinnable chatter) from a 7-recon + Fable synthesis. IDs: LW1-45.

### Groupe LB — Leads Board & Liste (fondateur 2026-07-19/20)
Rebuilt the leads landing page (bounded shell, 4-zone card, pinned list, KPI-filters, saved views,
"copy the best in the world" cockpit round) from a 5-recon + Fable synthesis, plus founder
retouch waves through 2026-07-20. IDs: LB1-56.

### Groupe APX — L'intérieur des apps (fondateur 2026-08-01)
Gave CRM/Ventes/Stock/Chantiers/SAV/Compta each their own densified, app-specific interior (Odoo-
measured density, product photo via `records.Attachment`, pump curves, cockpit tiles). IDs: APX1-36.

### Group F–P / Group A–E — empty design-overhaul placeholders
Two runs of category headers (design tokens, component library, DataTable engine, shell/nav,
per-module restyle, dashboard, UX behaviors, mobile/PWA, a11y, perf, cleanup; and the older core-
unblock/attachments/nav-menu/paramètres/E2E group) were superseded by the later VX/LW/LB/ODY/APX/EZ
work and never held a single task. Removed as pure empty scaffolding — no IDs to cover.

### Done tasks archived from groups still ACTIVE in docs/PLAN2.md (headers untouched)
These group headers still own pending work and remain fully in place; only their finished tasks
were removed from the file.
- Groupe QX ROUND 7 (split industriel/commercial, 4 renderers, injection 82-21): QX43-52 (QXG6 still pending).
- Groupe QX ROUND 6 (verified defects + conversion loop): QX1-42 (QXG1-5 still pending/GATED).
- Groupe VX ("Le plus bel ERP du monde"): VX1-116.
- AXE 1 — BEAUTÉ: VX121-159.
- AXE 2 — ROBUSTESSE: VX160-206 (VX198, VX203 remain pending, untouched).
- AXE 3 — AMOUR-EMPLOYÉ: VX207-251 (VX252 remains pending, untouched).
- Groupe ODY (paradigme Apps): ODY1-32, ODY34 (ODY33 remains pending).
- Groupe EZ (5 trajets quotidiens): EZ1-16 (EZ17 remains pending — its 5-parcours-verts clause unmet).
- Groupe VAO (Veille appels d'offres): VAO1 (insertion prerequisite; VAO2-42 remain pending).

### DONE LOG digest
Folded ~14 separate `DONE LOG`/`### DONE LOG — …`/`#### DONE LOG — …` sections (Groupe PUB batches,
QX ROUND 7, several PLAN2 verification/vague waves, the QJ batch, Groupe LW, Groupe LB) into the
single bare `## DONE LOG` header kept near the end of `docs/PLAN2.md` for future runs to append to.
The dated entries under that header covered, in chronological order: G-series/Group Q/R/S/U0
foundation work (2026-06-20/23), the "world-class look-and-feel" wave + I134/I138 palette
(2026-06-21/22), the QX ROUND 6 batch (2026-07-10), 10 PLAN2 lane-drain waves covering most of
VX1-160 (2026-07-11/12), the 66-task "Big PLAN2 drain" (QF/QG/QS/QD/QP/CH/QK/MB/WR/QC1, 2026-07-02),
Groupe VAO's insertion (2026-08-01), and the ODY/APX/EZ paradigm-shift waves + founder phone/board
retouches (2026-08-01). Two entries that also referenced a still-`[BLOCKED` pending task (VX246,
VX252) were left in place verbatim rather than folded, so no pending-task line was touched.

## Archived from docs/WEB_PLAN.md — 2026-08-04

### WJ117–WJ126 — 4 modes + règle anti-concurrent (fondateur 2026-07-16)
- WJ117: fixed invisible selected-card state (CSS-layer bug) across 8 journey card groups.
- WJ118: client 3D proposal now drapes the real satellite roof photo.
- WJ119: swapped the generic consumption curve for the real Moroccan evening-peak shape, per mode.
- WJ120: added a live "N batteries" simulator to the client proposal page.
- WJ121: split "Professionnel" into real Industriel/Commercial parcours modes.
- WJ122: built the per-category Commercial questionnaire panel.
- WJ123: built the Industriel v2 panel (shift patterns, MT, honest injection line).
- WJ124: built the agricultural culture→water→pump sizing engine.
- WJ125: enforced the founder's anti-concurrent rule — no detailed estimate during public capture.
- WJ126: made /proposition mode-aware with 4 quote variants (résidentiel/agricole/industriel/commercial).

### WJ110–WJ116 — Quote journey round 6 (2026-07-10)
- WJ110: wired Meta CAPI onto the primary /devis/mon-toit capture endpoint.
- WJ111: stopped showing pompage (agricole) leads a fabricated residential estimate.
- WJ112: made the "affiner" refinement fields actually move the shown number; cut the fake delay.
- WJ113: fixed city-tariff lookup to match real geocoded addresses.
- WJ114: redesigned the proposal's first screen for a decide-in-10-seconds mobile layout.
- WJ115: built the /suivi/<token> post-sign status page.
- WJ116: fixed parrainage copy + wired real referral param passthrough.

### W148–W221 — Website beauty & polish audit
- W187: sourced 6 of 7 real manufacturer brand-logo SVGs for the partner trust strip (Dyness still missing an asset).

### menus retirés (tâches archivées antérieurement — sections déjà vidées, sans tâche restante)
- WJ1–WJ24, WJ39–WJ59, WJ60–WJ94, WJ95–WJ107 — quote-journey rounds 1/3/4/5 (best-in-world elevation)
- 2026-07-02 ROUND 2 — exhaustive deep pass (F0–P0 lanes)
- W70–W97 — 3D builder audit (canonical toiture-3d-pro-11)
- W98–W104 — technical SEO audit & fixes
- W105–W111 — 3D builder multi-zone/overhang/contact capture
- W112–W118 — devis pipeline (roof point → Meriem design → premium proposal + e-sign)
- W119–W131 — SEO content expansion (FAQ/EV pillar/guides library/battery)
- W132–W139 — dated blog (Astro content collection) + cornerstone posts
- W141–W145 — fiches techniques library
- W148–W221 remainder — website beauty & polish audit (all but W187)
- W222–W235 — homepage "the best" elevation v3
- W236–W244 — whole-site elevation EN+AR mirrors
- W245–W252 — journey↔site tie-in (/devis/mon-toit front door)
- W253–W264 — services: complete findable catalogue
- W265–W279 — homepage & site elevation round 4
- W280–W289 — trust & proof engine
- W290–W299 — SEO/AEO/content reach

## Archived from docs/ERROR_PLAN.md — 2026-08-04

Le backlog ERR (bugs vérifiés par l'error-autopilot, trouvés lors d'un audit read-only
en 11 lanes de `main` @ `98e9d23`) a été entièrement corrigé lors du drain du
2026-06-20 : 113 tâches fixées en parallèle (16 lanes, 19 commits), CI verte sur
l'arbre consolidé (backend 1282 tests, flake8, frontend lint + 200 tests + build,
web tsc + 2276 vitest + astro build).

ID coverage: ERR1–ERR113 (plage continue, aucune exception — toutes cochées `[x]`).

Correctifs les plus conséquents :
- ERR1–ERR3 — agent FastAPI NL→SQL : validation SELECT-only par parseur, correction
  de l'isolement multi-tenant contournable de 4 façons, retrait du rôle DB
  sur-privilégié utilisé par l'agent.
- ERR4–ERR5 — auth/rôles : `is_responsable` n'accordait plus d'accès par simple
  possession d'un rôle, et un Responsable ne pouvait plus s'auto-octroyer
  `roles_gerer` pour s'escalader en Administrateur.
- ERR7–ERR8 — ventes : fermeture d'un IDOR cross-tenant qui permettait d'injecter
  des lignes ou de re-pointer un devis sur le client/lead d'une autre entreprise.
- ERR17 — quote_engine : correction d'une race condition (globals mutables partagés)
  qui pouvait faire fuiter le nom/adresse/totaux d'un client dans le PDF d'un autre.

## Archived from docs/new_tasks_plan.md — 2026-08-04

### Groupe NTSEC — Sécurité & identité enterprise
MFA step-up, politiques session/IP/appareil, détection d'anomalies (impossible travel, nouvel
appareil), device trust, journal sécurité exportable, rétention audit hash-chaînée, campagnes de
revue d'accès + SoD + partage niveau enregistrement + break-glass + permissions champ shippés.
SSO SAML/OIDC (NTSEC2/3/7/8/16/18) restent BLOQUÉS — app `apps/identity` à refaire aux normes
multi-tenant (SCA4), reste en file d'attente.
IDs: NTSEC1, NTSEC4-6, NTSEC9-15, NTSEC17, NTSEC19-25, NTSEC27-28, NTSEC30

### Groupe NTAPI — Plateforme API & intégrations
Enveloppe d'erreur Stripe-like, versioning API + en-tête, plans d'usage nommés, reprise webhook
programmée + signature v2 + idempotency-key, schéma OpenAPI (batch plateforme) ; rotation clés,
env test-live, sandbox, changelog et docs (batch 4).
IDs: NTAPI3, NTAPI5, NTAPI7-10, NTAPI20-27

### Groupe NTEXT — Extensibilité no-code
Endpoints vue-liste/vue-formulaire objets custom + nouvelle app `extensions` (catalogue
marketplace global lecture-seule, registre exempté tenant après revue).
IDs: NTEXT2-3, NTEXT13

### Groupe NTPLT — Architecture enterprise-scale
Fondation RLS Postgres (GUC/policies/rôle non-BYPASSRLS/tests/Celery), outbox transactionnel +
rejeu, pagination keyset + budgets requêtes, cache tenant + ETag + résilience Redis + équité
Celery + jobs de fond + exports lourds async, registre de recherche + abstraction backend,
partitionnement + séquences, observabilité/logs/métriques par tenant, SAST + audit CVE, mode
maintenance, déploiement sans coupure, export/clone de tenant, drill de restauration par tenant.
IDs: NTPLT1-10, NTPLT12-16, NTPLT18-19, NTPLT21-31, NTPLT35-37, NTPLT39-62

### Groupe NTUX — UX power-user
SavedView + FilterBuilder AND/OR, dates relatives, BulkEdit+undo, nav cellule, quick-create bus,
RecentEntitiesWidget (round 1) ; export/prefs/groupBy/BulkNote/row-peek (round 2) ;
ViewBuilder+import (round 3).
IDs: NTUX2-6, NTUX8, NTUX10-11, NTUX15-20, NTUX22-23, NTUX25, NTUX34

### Groupe NTMOB — Mobile enterprise
Écrans mobiles offlinesync accueil commercial + cockpit, lecture seule sur endpoints existants.
IDs: NTMOB4-5

### Groupe NTPRT — Portails
Primitive auth portail (`CustomUser.portee` + FK portail string-ref + 3 rôles système via
init_roles) + `IsPortalScopedUser` durcissement d'exclusion portail sur les gates internes.
IDs: NTPRT1, NTPRT5

### Vertical NTSAN — Santé (nouvelle app `sante`)
Praticien/Salle/Patient/RendezVous/Admission/ActeMedical/Convention/GrilleTarifaire/
ActeRealise/PriseEnCharge/FactureSante/PaiementSante, agenda multi-praticiens, écran réception,
stats actes/conventions, disponibilités/horaires praticien, alerte J-7 prise en charge,
multi-cabinet, annulation/no-show.
IDs: NTSAN1-4, NTSAN6-10, NTSAN12-13, NTSAN15, NTSAN18, NTSAN28-32, NTSAN35, NTSAN37

### Vertical NTEDU — Éducation (nouvelle app `education`)
Réinscription masse, liste d'attente FIFO, grille tarifaire, remises fratrie/bourse, échéancier
auto, présences bulk + notif absence, matières/coefficients, notes/certificat/emploi du
temps/cantine/discipline, portail parents (auth + factures + liste d'attente), notifications
WhatsApp gated, exports/trombinoscope/relance réinscription.
IDs: NTEDU4-8, NTEDU12-15, NTEDU18-19, NTEDU21-22, NTEDU25-27, NTEDU30-32, NTEDU34, NTEDU37-38,
NTEDU40, NTEDU42

### Groupe NTIDE — Innovation & Boucle de Feedback Produit (nouvelle app `innovation`)
Boîte à idées complète (vote/dashboard/paramètres/CTA flottant/actions groupées/export xlsx),
liaisons idée→devis/ticket/chantier, campagnes d'innovation complètes (segments, incitation,
rapport, clonage, historique), canal feedback produit + digest.
IDs: NTIDE1-2, NTIDE4-41

## Archived from docs/plans/PLAN_CRM_VENTES.md — 2026-08-04

### NTCPQ — Batch 1 foundation (2026-07-17)
App `apps/cpq` créée : OptionProduit/ContrainteCompatibilite, moteur RegleProduitCPQ (via
core.rules), OffreGroupee bundles, ListePrix.segment_client, PrixContractuel,
SeuilMargeFamille (marge interne), matrice d'approbation remise, configurateur guidé +
generer-devis.
Couverture : NTCPQ1-10.

### NTCRM — Batch 1 foundation (2026-07-17)
Apps `territoires` + `contacts` créées : moteur territoires + rotation équitable race-safe,
ForecastEntry/roll-up/snapshots hebdo + écran, ContactClient org-chart + onglet, PlanCompte +
écran, Playbooks par stage STAGES.py + widget lead. Nouveau signal
`core.events.lead_stage_changed`.
Couverture : NTCRM1-13.

### NTMKT — Batch 1 foundation (2026-07-17)
Shell frontend Marketing (9 écrans : Dashboard/Campagnes/A-B/Segments/Listes/Séquences/
Événements/Enquêtes/Fidélité/Domaine d'envoi) + touches marketing distinguées sur la fiche
lead. (Backend marketing déjà existant, UI manquante comblée.)
Couverture : NTMKT1-11.

### NTDMO — Batch 1 foundation (2026-07-17)
`seed_demo_company` riche (12 mois d'historique daté, 3 modes marché, cycle complet) +
reset_demo_company + Company.est_demo/mode_presentation + SerializerMaskMixin (masquage PII
démo) + app `apps/onboarding` (checklist « Premiers pas » auto-complétée via core.events).
Couverture : NTDMO1-13.

## Archived from docs/plans/PLAN_FINANCE.md — 2026-08-04

### Groupe NTADM — Administration enterprise
Fondations entités/sandbox/health-score/config-packages/adoption livrées (batch 6, 29 tâches) ; permissions fines et délégation d'admin restent hors périmètre FINANCE.
IDs : NTADM1, 4-6, 10-17, 23-24, 27-28, 30-31, 33-36, 38, 40, 43, 45-48.

### Groupe NTFIN — Finance entreprise (grand groupe)
Consolidation multi-sociétés complète (cycle, matching interco, éliminations, goodwill, minoritaires), multi-référentiel CGNC/IFRS, allocations, close management, rapprochements de bilan, immobilisations avancées, IFRS 15 et états consolidés.
IDs : NTFIN1-56 (toutes).

### Groupe NTFPA — FP&A budgets/prévisions
App `apps/fpa` complète : cycles budgétaires, saisie tableur, prévisions glissantes, drivers effectifs/pipeline, scénarios what-if, variance analysis, dashboard exécutif, permissions.
IDs : NTFPA1-30 (toutes).

### Groupe NTTRE — Trésorerie avancée
Parsers bancaires CFONB/MT940/camt.053, rapprochement apprenant, double validation des paiements, pouvoirs bancaires, endossement/protêt, réglages et beat tasks livrés ; delighters et plusieurs volets round 2 restent ouverts.
IDs : NTTRE1-9, 11, 13-14, 16, 18, 27-29, 31, 36, 38, 41-42.

### Groupe NTCRD — Credit management client
App `apps/credit` : limite de crédit, hold, dérogations, scoring, assurance-crédit, exposition consolidée, wizards, réglages, KPI ; hooks devis/BC et volets publicapi restent hors périmètre.
IDs : NTCRD1-6, 9-13, 15-36, 39-40, 43-46.

### Groupe NTSUB — Revenus récurrents (abonnements)
Catalogue d'offres, add-ons, paliers/compteurs d'usage, essai, changement de plan, dunning multi-étapes, métriques SaaS, export catalogue, import CSV compteurs, e2e cycle de vie, chatter/notifications.
IDs : NTSUB1-5, 7-8, 12, 21, 31-34.

### Groupe NTMAR — Maroc & Afrique (conformité)
Apps `einvoice`+`fiscal` : facture électronique DGI (dry-run), file Simpl inerte, export SIMPL-TVA/IS, calendrier fiscal, RAS étendues, timbre, attestations tenant, registre UBO, veille réglementaire.
IDs : NTMAR5-12, 14-20, 24, 28-33.

### Groupe NTASS — Assurances & sinistres d'entreprise
App `apps/assurances` complète : registre polices/garanties/échéancier de primes, sinistres transverses + indemnisation, attestations, homme-clé/cyber, écrans, permissions RBAC.
IDs : NTASS1-29 (toutes).

## Archived from docs/plans/PLAN_VERTICALS.md — 2026-08-04

### NTCON — Vertical BTP/EPC (chantier)
Batch 1 (2026-07-17) : fondations app `btp_chantier` (réserves/punch-list sur plan, levée avec preuve, RFI, alerte RFI, visas). Batch 2 : avenants chiffrés + e-sign, DGD (notification/contestation/solde), déboursé-vs-facturé, diffusion de plans, alerte plan périmé.
IDs : NTCON1-13.

### NTPRO — Vertical immobilier & facilities
Batch 1 : fondations app `immobilier` (patrimoine hiérarchique, locataires, baux, révision loyer, dépôt garantie, échéancier, quittancement→facture, relances impayés, rentabilité actif). Batch 2 : budget/dépenses/répartition/régularisation de charges, états des lieux + photos comparatives entrée/sortie.
IDs : NTPRO1-16.

### NTHOT — Vertical hôtellerie & restauration
Batch 1 : fondations app `hospitality` (chambres, tarification saisonnière, réservations, check-in fiche de police, check-out, folio unifié, taxe de séjour, housekeeping, dashboard RevPAR/ADR). Batch 2 : main courante, recettes/coût matière, événements/banquets via le devis existant, salles, BEO PDF, pension, calendrier drag & drop.
IDs : NTHOT1-3, 5-9, 11-14, 17-21 (sauf NTHOT4/10 restés `[BLOCKED]` ; sauf NTHOT15-16/22 restés `[ ]`).

### NTAGR — Vertical agriculture
Batch 1 : fondations app `agriculture` (exploitation/parcelle, campagne culturale, étapes de campagne, intrants liés au stock, garde DAR bloquante, registre phytosanitaire ONSSA, main d'œuvre saisonnière). Batch 2 : matériel agricole (pattern flotte), irrigation + coût lié au pompage solaire, lots de récolte + traçabilité amont-aval.
IDs : NTAGR1-9, 11-16 (sauf NTAGR10 resté `[BLOCKED: hors périmètre VERTICALS]`).

### NTESG — Reporting ESG/durabilité consolidé
P1 bloquants vente grands comptes : périodes de reporting figées (snapshot), agrégation cross-app en lecture, catalogue GRI-lite, rapport PDF + export xlsx, cockpit ESG, objectifs de trajectoire pluriannuelle. Batch 2 (P2/P3) : intensité carbone normalisée, alertes de dérive trajectoire, comparateur N vs N-1, matérialité, politiques RSE, export DPEF, badge de maturité, facteurs d'émission.
IDs : NTESG1-7, 9-16 (sauf NTESG8/17 restés `[ ]`).

## Archived from docs/FRONTEND_GAP_PLAN.md — 2026-08-04

### Lane frontend/reporting + frontend/platform (audit câblage 2026-07-06)
Deux tâches vérifiées livrées le 2026-07-18 via WIR79 :
FE-XKB1-3/ZCTR7-9 — inbox Approbations autonome (5 sources non filtrées, décision unitaire+masse, route /approbations) ;
FE-YHARD2 — onglet « Historique / annuler » dans AgentActions.jsx (logs agent + undo, garde is_undoable).

## Legacy archive (ex-docs/DONE.md, condensé 2026-08-04 — texte intégral dans l'historique git)

Neuf passes d'archivage successives (« clean the plans ») ont déplacé les tâches `[x]` hors des
plans actifs vers `docs/DONE.md`. Ce fichier condense ces neuf sections en une seule histoire
lisible. Chaque bloc ci-dessous correspond à un `## Archived from …` de l'ancien fichier.

### PLAN.md — première passe (archive initiale)

2026-06-16/17. Premier lot de fonctionnalités ERP : T1–T17 (aperçu PDF devis cassé corrigé,
PWA installable, actions en masse sur leads, édition inline façon Odoo, recherche globale +
notifications, déblocage des réglages différés, expiration de devis à la volée + dashboard
pipeline, édition en masse du catalogue, import/export réutilisable, révisions de devis, champs
personnalisés, export comptable TVA, hub Rapports, contrats de maintenance récurrents, garde
d'approbation de remise). Puis la grosse vague N1–N99 : objet Chantier + Parc installé (kanban,
checklist, galerie, timeline), bons de commande fournisseur, conformité facture marocaine
(Article 145, ICE, TVA par ligne, numérotation sans trou, aperçu UBL), dossiers réglementaires
loi 82-21/Article 33, tickets SAV + garanties + contrats d'entretien, hub Paramètres structuré,
champs personnalisés, PWA étendue, parrainage + commissions commerciales. Deux réouvertures
notées « déjà livré » : G4 (RBAC 7 rôles) et L7 (factures en retard matérialisées).
**Couverture :** T1–T17 ; N1–N13, N15–N19, N21–N49, N54–N57, N61–N63, N66, N70–N71, N77–N78,
N80–N84, N90, N95, N98–N99 (le reste de la file N — N14, N20, N26, N36, N50–53, N58–60, N64–65,
N67–69, N72–76, N79, N85–89, N91–94, N96–97, N100–102 — gaté ou différé, livré dans les passes
plus bas).

### PLAN2.md — première passe (archive initiale)

2026-06-17/18. Fondation de la refonte UI : extraction de marque + tokens Tailwind 4 (F14–F20),
puis toute la bibliothèque de primitifs shadcn/Radix/TanStack/lucide/sonner (boutons, inputs,
overlays, feedback, états — G21–G30) et une vitrine vivante `/ui` (P68) — le tout additif, zéro
régression sur les écrans existants. Ensuite le flux d'acceptation de devis (A1–A4 : option
choisie + date + qui accepte, dialogue à l'entrée en Signé, l'option devient autoritative pour
facture/chantier, actions inline post-acceptation) ; le correctif pièces-jointes/PDF MinIO (B1) ;
le menu iPhone coupé (C1) et le rechargement à froid du PWA (C2) ; Paramètres réorganisé en
onglets (D1) avec numérotation configurable (D3) et logique de devis éditable/versionnée (D5).
Enfin la suite Playwright E2E (E1–E16, 18 specs, check CI requis) qui a débusqué un vrai bug
(le loader plein écran qui détruisait les modales ouvertes à chaque refetch).
**Couverture :** F14–F20 ; G21–G22, G25, G28–G30 ; P68 ; A1–A4 ; B1 ; C1–C2 ; D1, D3, D5 ; E1–E16.

### WEB_PLAN.md — première passe (archive initiale)

2026-06-17/18. La saga du « cerveau estimateur » du site public, sur routes privées `noindex`
successives (`/preview/toiture-3d-pro-3` → `pro-11`) : azimut réel + PVGIS par configuration,
recherche exhaustive du vrai optimum, modèle de toit en pente/tuiles (panneaux à plat, sans
espacement inter-rangée), puis un optimiseur LIVE contraint (se résout à chaque option, verrous
cumulatifs) pour les deux types de toit, un moteur de production PVGIS côté serveur et une
fenêtre interactive Année/Mois/Jour — jamais le site public ni le formulaire de lead touchés.
En parallèle : 5 pages villes + 5 études de cas + /faq + /guides + /pourquoi-taqinor + /garanties
+ /marocains-du-monde, correction du barème tarifaire ONEE régie (chiffres juin 2026 vérifiés),
refonte de la nav (dropdowns Solutions/Ressources, header/footer partagés partout), un guide de
voix éditoriale STYLE.md suivi d'une réécriture de chaque page pour tuer les formules recyclées,
et un dernier lot « audit world-class » (témoignages vides, bandeau garantie, portrait fondateur,
bandeau marques).
**Couverture :** W1–W66.

### PLAN.md — passe « clean 2026-06-20 »

2026-06-19. D'abord deux régressions live corrigées en priorité : N103 (changement de rôle
bloqué — un rôle système dérivé perdait son niveau d'autorité) et N104 (pièces jointes cassées
partout — le sniffing MIME strict rejetait des PDF/images valides). Puis une série de vagues
« REFINEMENT QUEUE » en lanes worktree parallèles qui ont drainé des centaines de petits
raffinements ROUTINE sur chaque app (ventes/chantiers/CRM/stock/reporting/SAV/paramètres/champs
perso/documents/WhatsApp/notifications), tout en livrant la file N différée : réservation puis
consommation de stock (N14), cadre de supervision + connecteur Huawei FusionSolar (N50–52),
export UBL DGI silencieux (N105), moteur d'automatisation no-code + étape d'approbation
(N72–73), moteur tarifaire ONEE + ROI par PVGIS (N64–65), câblage des littéraux PDF vers des
réglages versionnés (CGV/garanties/tampon d'acceptation — N26, N36, N59–60, N67, D2), intégration
email Brevo + Celery Beat (N87–88/G9), le module terrain F1–F24 (checklists, check-in GPS,
photos guidées, mémos vocaux, vue « Ma journée »), étiquettes QR/code-barres (N20), carte
Leaflet du parc (N85), cadre d'export CSV/XLSX (N97), et la couche RBAC/visibilité
d'enregistrement/audit (N68–69/D4). Le plan s'est retrouvé drainé hors décisions gatées.
**Couverture :** N14, N20, N26, N36, N50–52, N58–60, N64–65, N67–69, N72–75, N85–89, N97,
N103–107, G9 ; F1–F20, F22–F24 (F21 différé à la passe WOW16).

### PLAN2.md — passe « clean 2026-06-20 »

2026-06-18/19. Suite de la refonte UI : groupes de primitifs restants (select/combobox,
date-pickers, upload, formulaires — G23/G24/G26/G27), DataTable (H31–33), shell/nav (I34–38),
puis une grosse vague de restylage module par module J39–J50 (leads, clients, devis, factures,
chantiers, parc, SAV, stock, reporting, paramètres, chrome de l'aperçu PDF), le dashboard +
hub reporting (K51/K52), puis L/M/N/O/P (passe iOS, focus-visible a11y, budgets perf/bundle,
migration des 16 CSS ad-hoc par composant dans index.css, docs). En parallèle : RBAC 7 rôles +
prix d'achat gatés (D4/N68–69), hiérarchie d'équipe + visibilité d'enregistrement + journal
d'audit (features non pré-listées), et le câblage des littéraux côté DEVIS (D2, famille N26/N59/
N60/N67). Ne reste gaté que M59 (logo à fournir par Reda).
**Couverture :** G23, G24, G26, G27 ; H31–H33 ; I34–I38 ; J39–J50 ; K51, K52 ; L53–L57 ;
M58, M60–M62 (M59 gaté) ; N63, N64 ; O65, O66 ; P67, P69 ; D2, D4.

### WEB_PLAN.md — passe « clean 2026-06-20 »

2026-06-19. i18n complète (W67) : FR/EN/AR (RTL intégral) sur les ~34 pages publiques, payload
du formulaire de lead invariant par langue. Puis deux modes « variabilité » sur la page
estimateur pro-11 : édition manuelle des 24 barres horaires de consommation + calculateur
d'appareils (W68), et personnalisation glisser-déposer de la disposition des panneaux sur le
maillage valide de l'optimiseur (W69). Récap narratif des W62–66 déjà livrés (témoignages,
bandeau garantie, portrait fondateur, bandeau marques, délai de réponse 48h).
**Couverture :** W67, W68, W69.

### PLAN.md — passe WOW16 (2026-07-09)

2026-06-20 → 07-09, archivée en un seul lot WOW16. D'abord des correctifs ciblés : un 500 live
sur l'upload de pièces jointes (N108, bucket MinIO manquant), le web push jusque-là dormant
(N109), le diagnostic « changement de rôle » (N110, non reproductible — tests de verrou ajoutés).
Puis un refactor d'architecture (M1–M7) : imports cross-app en FK-string uniquement, frontière
services/selectors généralisée, contrat CI import-linter, carte des couches, un bus d'événements
Django-signal (`core/events.py`), et l'éclatement des « god-files » (installations/ventes/stock).
Ensuite un énorme lot de comblement de manques FG1–FG399 (cockpit RH, déclencheurs temporels de
l'automatisation, champs personnalisés sur devis/chantier/ticket, détection de conflits
d'affectation, changelog in-app, et des centaines d'autres). Cinq modules entièrement nouveaux :
paie (PAIE1–36), comptabilité CGNC (COMPTA1–40), programmes multi-chantiers (PROJ1–38), GED
(GED1–38), flotte (FLOTTE1–35), QHSE (QHSE1–40), base de connaissances (KB1–7), litiges/
réclamations (LITIGE1–6). Un balayage d'intégrité de données (DC1–42 : fuite d'identité société
en dur dans le moteur de devis premium, FK nullable fragiles, consolidation des fiches employé).
Les écrans frontend câblant chaque nouvelle app (UX1–47). Et la suite de la méga-file de parité
Odoo (série ODX puis X-/Y-/Z-) couvrant compta, facturation, achats, stock, fabrication, ventes,
marketing, POS, projets, field-service, SAV, contrats, flotte, QHSE, RH, paie, GED, KB et un
lot de durcissement (YHARD). Complète aussi : capture terrain tolérante au hors-ligne (N91/F21),
cadre i18n+RTL complet (N93–94), et 2FA + sessions actives + rotation forcée de mot de passe
(N96).
**Couverture :** N53, N76, N79, N91–N94, N96, N108–N110, F21, G5 ; M1–M7 ;
FG1–FG385, FG387–FG399 (FG386 absent) ; PAIE1–36 ; COMPTA1–40 ; PROJ1–38 ; GED1–38 ;
FLOTTE1–35 ; QHSE1–40 ; KB1–7 ; LITIGE1–6 ; DC1–33, DC35–42 (DC34 absent) ; UX1–47 ;
ODX2–4, ODX9, ODX10, ODX21 ; série X (chaque préfixe quasi complet, quelques ID isolés
manquants — voir git pour le détail exact) : XACC1–36, XFAC1–29, XPUR1–26, XSTK1–23, XMFG1–16,
XSAL1–17, XMKT1–37, XPOS1–18, XPRJ1–29, XFSM1–24, XSAV3–28, XCTR1–22, XFLT1–30, XQHS1–27,
XRH1–34, XPAI1–26, XGED1–30, XKB1–34, XPLT1–23 ; série Y : YCASH4, YPROC3–10, YSERV1–13,
YLEDG1–13, YHIRE1–14, YSTCK1–8, YDOCF1–7, YLEAD8–14, YSUBS1–9, YEVNT2–12, YRBAC1–9, YOPSB1–14,
YTEST1–17, YDATA9 ; série Z : ZACC1–16, ZFAC1–12, ZSAL1–8, ZPUR1–11, ZSTK1–12, ZMFG1–12,
ZPRJ1–12, ZFSM1–7, ZSAV2–10, ZRH1–18, ZPAI1–12, ZMKT1–20, ZGED1–15, ZCTR1–12 ; YHARD2–12.

### PLAN2.md — passe WOW16 (2026-07-09)

Le lot « Quote Journey » (QJ) : ingénierie de croissance sur le tunnel de vente — suivi
d'ouverture de proposition, notification vendeur instantanée, ordonnanceur Celery Beat, cadence
de relance automatisée, expiration de devis + hygiène de funnel automatiques, scoring de leads,
avancement auto NEW→CONTACTED, dédoublonnage webhook, attribution Meta CAPI (envoi gaté sur le
token du founder), piste légale e-signature renforcée (loi 53-05) + confirmation OTP, données
de financement dans le devis, tables tarifaires 82-21 par autoconsommation, envoi email
serveur, variantes/modèles de devis réutilisables, dashboard commercial + rapport gagné/perdu,
prise de rendez-vous en self-service — plus (gaté) une intégration WhatsApp Business API payante.
En parallèle : d'autres groupes de plan (U, Q, AG « actions d'agent IA », S, sous-flux devis
QF/QG/QS/QD/QP, CH, QK, MB, WR) et une seconde vague de refonte UI reprenant les lettres F–P
pour de nouveaux écrans (F120–P171).
**Couverture :** QJ1–QJ31 ; QW1–QW6, QW9, QW10 ; G10 ; U1–U14 ; Q1–Q7 ; AG1–AG12 ; S1–S20 ;
QF1–QF9 ; QG1–QG12 ; QS1–QS4 ; QD1–QD2 ; QP1–QP2 ; CH1–CH6 ; QK1–QK6 ; MB1–MB6 ; WR1–WR12 ;
QC1 ; F120–F123 ; G124–G128 ; H129–H133 ; I134–I138 ; J139–J146 ; K147–K149 ; L150–L153 ;
M154–M158 ; N159–N163 ; O164–O166 ; P167–P171.

### WEB_PLAN.md — passe WOW16 (2026-07-09)

Un audit adversarial profond (24 agents) du site public et du vrai tunnel de conversion
`/devis/mon-toit` : WJ39–59 a corrigé le parcours EN/AR cassé (pages non traduites, CTA/
placeholders en dur en français, chaîne carte/géocodeur non localisée, fuite de langue sur le
tampon de signature), ajouté un bascule comptant/échelonné sur la proposition, une demande de
modification structurée, la télémétrie d'engagement, le partage WhatsApp, des badges de délai
de réponse honnêtes, l'analytique de funnel par étape. W245–381 a ensuite balayé le reste du
site : indexation du tunnel (retrait du noindex), retrait du DiagnosticForm parallèle au profit
d'un tunnel unique, widget d'estimation instantanée sur la home, refonte de /nos-solutions et
des pages financement/pompage/maintenance, passe de fraîcheur datée sur la loi 82-21, et des
dizaines d'autres correctifs conversion/SEO/confiance. Puis deux règles explicites du founder
appliquées : WA1–37 retire le portrait/la signature à la première personne du fondateur de
CHAQUE accueil (FR/EN/AR), gardé uniquement sur /à-propos ; WB1–35 corrige une exposition de
rendement uniforme — les quatre chiffres de production « mesurée » dérivaient tous du même
facteur kWc, falsifiable en 30 secondes, désormais relabellisés honnêtement au cas par cas.
WC1–12 a vérifié les correctifs mobile/RTL du 04/07 sur de vrais viewports iPhone en FR/EN/AR.
WN1–8 a corrigé un blog qui se lisait comme tout juste inauguré/vide. WJ1–38 et W70–244/W222–235
couvrent le reste de cette même vague croissance/SEO/i18n/recharge-véhicule/loi-82-21.
**Couverture :** WJ1–WJ109 ; W70–W381 (quelques ID isolés renumérotés/absents — ex. W140,
W186–187 — voir git) ; WA1–WA37 (WA12 absent) ; WB1–WB35 (WB5 absent) ; WC1–WC12 ; WN1–WN8.

