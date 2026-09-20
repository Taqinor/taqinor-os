# TAQINOR OS — Done tasks archive (condensed)

> Archive condensée des tâches terminées — juste assez pour comprendre l'histoire.
> Le texte intégral de chaque tâche archivée vit dans l'historique git (les fichiers plan eux-mêmes et l'ancien `docs/DONE.md`).
> Maintenu par la commande « clean the plans » (CLAUDE.md). Dernier passage : 2026-09-20.

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
AUD=287
AUDV=28
CAL=219
CHT=28
CKP=7
CRX=40
DC=1
ENG=31
EZ=16
FE-COMPTA=2
FE-CONTRAT=7
FE-FG=3
FE-GED=3
FE-PROJ=1
FE-SCA=1
FE-XACC=3
FE-XCTR=5
FE-XFAC=1
FE-XGED=8
FE-XKB=1
FE-XMFG=1
FE-XPAI=7
FE-XPLT=3
FE-XPRJ=6
FE-XQHS=4
FE-XRH=4
FE-XSAL=2
FE-YHARD=2
FE-YHIRE=1
FE-ZACC=3
FE-ZGED=1
FE-ZPAI=2
FE-ZPRJ=2
FE-ZRH=2
FE-ZSAL=1
FG=1
LB=55
LW=45
MRY=32
N=3
NTAI=32
NTAPI=37
NTDATA=38
NTEDU=24
NTEXT=32
NTGRC=32
NTIDE=50
NTMIG=30
NTMOB=22
NTOBS=32
NTPLT=41
NTPRT=26
NTSAN=20
NTSEC=21
NTUX=39
NTWFL=33
ODX=12
ODY=33
PACT=186
PUB=125
PV=83
PVG=4
QJR=255
QPERF=1
QW=1
QX=52
RLC=3
SCA=49
SIG=4
SOL=16
STKCAT=27
VAO=35
VT=14
VTA=18
VX=223
WIR=280
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

### Active regressions + six 2026-06 audit batches + Groupe ODX/X* (partiel)
QPERF1 (query-budget fix, shipped via SCA43 cache) closed the top-priority regression. Six 2026-06
batches drained to zero: post-sale/procurement N-series, field-execution F1-24, modularity M1-7,
two feature-gap sweeps FG1-399, module deep-dive specs, single-source-of-truth audit, backend-only
Group UX — only FG386 and DC34 were live checkboxes here, rest tracked elsewhere/narrative.
ODX1-23 module-split shipped its bulk; XSTK/XMFG/XSAL/XMKT/XSAV/XPLT fully drained; XFAC/XPUR/XPRJ/
XFSM/XCTR/XFLT/XQHS/XRH/XPAI/XGED headers held zero tasks (removed).
IDs: FG386, DC34 · ODX1,5,6,7,11,12,13,15,16,17,19,23 · XSTK18,20 · XMFG17-19 · XSAL5,14,15 ·
XMKT10,34-36 · XSAV22 · XPLT12,19-21 · XPOS17

### Round 2 câblage bout-en-bout + parité Odoo (Y*/Z*/YHARD) + ARC + SCA/ads
2026-07-03 ~90-agent audit closed Axis A (end-to-end wiring), Axis B (RBAC/API/ops/data-integrity)
and Axis C (14-app Odoo parity) plus YHARD hardening; only YCASH kept one open hand-off (header
stays). 2026-07-07 Fable-orchestrated ARC1-56 (tenancy model, base viewset, tiers referential,
manifest registry, scaffolders, governance guards) fully shipped. 2026-07-09 SCA1-49 (build-order
governance, capacity, tenant lifecycle, white-label, money-path perf, revenue-loop) plus the Meta
Ads engine (mirrors/propose-approve-apply, bandit+guardian+treasury+attribution, creative tiers
A/B/C, health scores) all shipped.
IDs: YSERV4,8,10,11 · YRBAC3,10-12 · YAPIC1-12 · YOPSB11 · YTEST4-6,10,11 · YDATA1-4,6-8,10-22
(YDATA5/9 never existed) · ZFAC11 · ZSAL9 · ZSTK5,13 · ZMFG9 · YHARD1,9 · ARC1-56 (sections A-F) ·
SCA1-49 (sections A-H) · ENG1-31 · ADSENG1-53, ADSENGINT1-3, ADSDEEP1-66 · ASG1-8 · AGEN1-10 · SIG1-4

### Groupe WIR + AOF + PACT (partiel) + WOW + MANUAL
WIR1-168 wiring/data audit (4 waves) shipped across two 2026-07-18/19 drains. AOF1-194 calepinage/
submission-dossier app shipped complete 2026-08-01 (verified against the real FRDISI case); AOF
header/intro kept (live conventions). PACT1-4,15,16 (contract guards + 2 logged defects) shipped;
§A/§C headers stay (PACT5-9, PACT17-27 still open). WOW1-26 (CI gate 2h15→~6-10min) fully shipped,
narrated only, no checkbox IDs. YRBAC13 (fine-grain @action perms) shipped; MANUAL header of
real-world reminders (ICE/IF/RC, OSP prices, etc.) stays untouched.
IDs: WIR1-168 (P0 1-11, P1 12-80, P2 81-98, P3 99-168) · AOF1-194 (W0 1-11 .. W10 183-194) ·
PACT1-4,15,16 · YRBAC13

### DONE LOG digest
100+ dated entries (2026-06-18→08-03) condensed above: WOW CI-speed overhaul, M1-7/ARC/SCA waves,
ads-engine build, WIR audit, AOF app, and the 2026-08-03 PACT incident response (AO dashboard crash
→ PACT1-187). Six entries kept verbatim (contain a literal `[BLOCKED` substring the mechanical
pending-line scan protects, though all are historical narrative): 07-16 adsengine batch,
07-12 backend/sav union, 07-12 ODX7 unblock, 07-01 compta batch, 07-03 GROS RUN, 07-12 N102 note.

## Archived from docs/PLAN2.md — 2026-08-04

Pure housekeeping: relocates checked `[x]` tasks + emptied headers; nothing built/reworded/reordered.
GATED sections, "NE PAS FAIRE (Groupe VXD)", and pending tasks stayed byte-identical in PLAN2.md.

### Groupe PUB — Publicité (audit fondateur 2026-07-19)
14-agent audit closing wiring/brain/business-loop/console/growth/creative/science/finance. 107 tasks
shipped in 2 worktree batches 2026-07-19; PUB107-135/PUB-P8 stayed GATED.
P0 PUB1-14,115 · P1 PUB15-25,39 · P2 PUB26-38 · P3 PUB40-57 · P4 PUB58-69 · P5 PUB70-85 ·
P6 PUB86-95 · P7 PUB96-106

### Groupes QJ / QW / VX117-120 / U-Q-R / QF-QG-QS-QD-QP-CH-QK-MB-WR
QJ1-31 quote-journey best-in-world (speed-to-lead, e-sign, seller efficiency, 3D proposal), shipped
2026-06-25 in one batch (VX203 note kept pending in place). QW7-8 fixed the website→ERP signal gap
(QW7 = live lead-name corruption bug). VX117-120 = pre-VX-audit priority fixes + 1 security alert.
Group U1-14 (field UX/doc-status), Q1-7 (Devis↔Toiture-3D pipeline), AG1-12 (registry AI actions)
shipped 2026-06-21/22. Nine 2026-07-01 founder clusters shipped in the "Big PLAN2 drain" (66 tasks,
one merge): QF1-9, QG1-12, QS1-4, QD1-2, QP1-2, CH1-6, QK1-6, MB1-6, WR1-12.

### Groupe LW / LB / APX + empty design placeholders
LW1-45 rebuilt the lead detail screen (3-zone cockpit, useLeadDraft, autosave, chatter) 2026-07-18.
LB1-56 rebuilt the leads landing page (bounded shell, 4-zone card, KPI-filters, saved views)
2026-07-19/20 + founder retouches. APX1-36 densified CRM/Ventes/Stock/Chantiers/SAV/Compta
interiors 2026-08-01. Two empty design-overhaul header runs (F-P and A-E: tokens/component-lib/
DataTable/shell/restyle/dashboard/a11y/perf, and the older core-unblock/attachments/nav/E2E group)
were superseded by VX/LW/LB/ODY/APX/EZ and held zero tasks — removed, no IDs to cover.

### Groups still ACTIVE in PLAN2.md (headers untouched, only finished tasks removed)
QX43-52 (round 7, QXG6 pending) · QX1-42 (round 6, QXG1-5 pending/GATED) · VX1-116 · VX121-159
(AXE1) · VX160-206 (AXE2, VX198/203 pending) · VX207-251 (AXE3, VX252 pending) · ODY1-32,34
(ODY33 pending) · EZ1-16 (EZ17 pending) · VAO1 (VAO2-42 pending)

### DONE LOG digest
~14 DONE LOG sections folded into the one bare `## DONE LOG` header in PLAN2.md: G-series/Q/R/S/U0
foundation (06-20/23), world-class look wave + I134/I138 palette (06-21/22), QX round 6 (07-10),
10 lane-drain waves covering VX1-160 (07-11/12), the 66-task Big PLAN2 drain (07-02), VAO insertion
(08-01), ODY/APX/EZ waves + founder retouches (08-01). Two entries referencing still-pending VX246/
VX252 kept verbatim.

## Archived from docs/WEB_PLAN.md — 2026-08-04

### WJ117-126 — 4 modes + règle anti-concurrent (fondateur 2026-07-16)
WJ117 fixed invisible selected-card CSS bug (8 groups); WJ118 draped the real satellite roof photo
on the 3D proposal; WJ119 swapped in the real Moroccan evening-peak consumption curve; WJ120 added
a live "N batteries" simulator; WJ121 split Professionnel into real Industriel/Commercial modes;
WJ122 built the Commercial questionnaire panel; WJ123 the Industriel v2 panel (shifts/MT/injection);
WJ124 the agricole culture→water→pump sizing engine; WJ125 enforced no-detailed-estimate-in-capture;
WJ126 made /proposition mode-aware with 4 quote variants.

### WJ110-116 — Quote journey round 6 (2026-07-10)
Meta CAPI on /devis/mon-toit (WJ110); stopped a fake residential estimate for pompage leads (WJ111);
made "affiner" fields actually move the number (WJ112); fixed city-tariff geocoding (WJ113);
redesigned the proposal's decide-in-10s mobile layout (WJ114); built /suivi/<token> (WJ115); fixed
parrainage passthrough (WJ116).

### W148-221 — Website beauty & polish audit
W187 sourced 6/7 real brand-logo SVGs for the trust strip (Dyness asset still missing).

### Menus retirés (sections déjà vidées, sans tâche restante)
WJ1-24, WJ39-59, WJ60-94, WJ95-107 (quote-journey rounds 1/3/4/5) · 2026-07-02 ROUND 2 (F0-P0) ·
W70-97 (3D builder audit) · W98-104 (SEO technique) · W105-111 (3D multi-zone) · W112-118 (devis
pipeline) · W119-131 (SEO content) · W132-139 (blog) · W141-145 (fiches techniques) · W148-221
remainder (all but W187) · W222-235 (homepage v3) · W236-244 (EN+AR mirrors) · W245-252
(journey↔site) · W253-264 (services catalogue) · W265-279 (elevation round 4) · W280-289 (trust/
proof) · W290-299 (SEO/AEO)

## Archived from docs/ERROR_PLAN.md — 2026-08-04

Le backlog ERR (error-autopilot, audit read-only 11 lanes de `main`@`98e9d23`) entièrement corrigé
le 2026-06-20 : 113 tâches, 16 lanes, 19 commits, CI verte (backend 1282 tests, flake8, frontend
lint+200 tests+build, web tsc+2276 vitest+astro build). ID coverage: ERR1-ERR113 (plage continue,
toutes `[x]`). Correctifs marquants : ERR1-3 agent FastAPI NL→SQL (parseur SELECT-only, isolement
multi-tenant contournable ×4, rôle DB sur-privilégié retiré) · ERR4-5 auth/rôles (is_responsable/
roles_gerer escalade) · ERR7-8 ventes (IDOR cross-tenant lignes/client) · ERR17 quote_engine (race
condition globals mutables → fuite client entre PDFs).

## Archived from docs/new_tasks_plan.md — 2026-08-04

### NTSEC — Sécurité & identité
MFA step-up, politiques session/IP/appareil, détection anomalies, device trust, journal sécurité,
audit hash-chaîné, revues d'accès+SoD+partage+break-glass+permissions champ shippés. SSO SAML/OIDC
(NTSEC2/3/7/8/16/18) restent BLOQUÉS (apps/identity à refaire, SCA4).
IDs: NTSEC1,4-6,9-15,17,19-25,27-28,30

### NTAPI — Plateforme API & intégrations
Enveloppe d'erreur Stripe-like, versioning+en-tête, plans d'usage, webhook programmé+signature v2+
idempotency, OpenAPI ; rotation clés, sandbox, changelog/docs.
IDs: NTAPI3,5,7-10,20-27

### NTEXT — Extensibilité no-code
Endpoints vue-liste/formulaire objets custom + app `extensions` (marketplace lecture-seule).
IDs: NTEXT2-3,13

### NTPLT — Architecture enterprise-scale
RLS Postgres, outbox transactionnel+rejeu, pagination keyset, cache tenant+ETag+résilience Redis+
équité Celery+jobs de fond, registre recherche, partitionnement, observabilité par tenant, SAST+CVE,
mode maintenance, déploiement sans coupure, export/clone/restauration tenant.
IDs: NTPLT1-10,12-16,18-19,21-31,35-37,39-62

### NTUX — UX power-user
SavedView+FilterBuilder, dates relatives, BulkEdit+undo, nav cellule, quick-create, RecentEntities
(r1) ; export/prefs/groupBy/BulkNote/row-peek (r2) ; ViewBuilder+import (r3).
IDs: NTUX2-6,8,10-11,15-20,22-23,25,34

### NTMOB / NTPRT
Mobile: écrans offlinesync accueil+cockpit (NTMOB4-5). Portails: auth primitive `portee`+FK+3 rôles
+ durcissement `IsPortalScopedUser` (NTPRT1,5).

### Verticaux NTSAN / NTEDU
Santé (app `sante`): Praticien/Salle/Patient/RDV/Admission/ActeMedical/Convention/GrilleTarifaire/
PriseEnCharge/FactureSante, agenda multi-praticiens, réception, stats, multi-cabinet, no-show.
IDs: NTSAN1-4,6-10,12-13,15,18,28-32,35,37.
Éducation (app `education`): réinscription masse, liste d'attente FIFO, grille tarifaire, remises,
échéancier, présences+notif, notes/certificat/emploi du temps/cantine/discipline, portail parents,
WhatsApp gated, exports.
IDs: NTEDU4-8,12-15,18-19,21-22,25-27,30-32,34,37-38,40,42

### NTIDE — Innovation & feedback produit
Boîte à idées complète (vote/dashboard/CTA/export xlsx), liaisons idée→devis/ticket/chantier,
campagnes d'innovation, canal feedback+digest.
IDs: NTIDE1-2,4-41

## Archived from docs/plans/PLAN_CRM_VENTES.md — 2026-08-04

NTCPQ (2026-07-17): app `cpq` — OptionProduit/ContrainteCompatibilite, moteur RegleProduitCPQ,
OffreGroupee, ListePrix.segment_client, PrixContractuel, SeuilMargeFamille, matrice d'approbation
remise, configurateur guidé+generer-devis. Couverture : NTCPQ1-10.

NTCRM (2026-07-17): apps `territoires`+`contacts` — moteur territoires race-safe, ForecastEntry+
roll-up+snapshots, ContactClient org-chart, PlanCompte, Playbooks par stage STAGES.py, signal
`lead_stage_changed`. Couverture : NTCRM1-13.

NTMKT (2026-07-17): shell Marketing (9 écrans) + touches marketing sur la fiche lead (backend
déjà existant). Couverture : NTMKT1-11.

NTDMO (2026-07-17): `seed_demo_company` riche (12 mois, 3 modes, cycle complet) + reset +
Company.est_demo/mode_presentation + SerializerMaskMixin + app `onboarding`. Couverture : NTDMO1-13.

## Archived from docs/plans/PLAN_FINANCE.md — 2026-08-04

NTADM — fondations entités/sandbox/health-score/config-packages/adoption (batch 6, 29 tâches) ;
permissions fines/délégation restent hors périmètre. IDs : NTADM1,4-6,10-17,23-24,27-28,30-31,33-36,38,40,43,45-48.

NTFIN — consolidation multi-sociétés complète, multi-référentiel CGNC/IFRS, allocations, close
management, rapprochements bilan, immobilisations avancées, IFRS15, états consolidés.
IDs : NTFIN1-56 (toutes).

NTFPA — app `fpa` : cycles budgétaires, saisie tableur, prévisions glissantes, drivers, what-if,
dashboard exécutif, permissions. IDs : NTFPA1-30 (toutes).

NTTRE — parsers bancaires CFONB/MT940/camt.053, rapprochement apprenant, double validation
paiements, pouvoirs bancaires, endossement/protêt ; delighters/round 2 restent ouverts.
IDs : NTTRE1-9,11,13-14,16,18,27-29,31,36,38,41-42.

NTCRD — app `credit` : limite, hold, dérogations, scoring, assurance-crédit, exposition
consolidée, wizards, KPI ; hooks devis/BC + publicapi hors périmètre.
IDs : NTCRD1-6,9-13,15-36,39-40,43-46.

NTSUB — offres/add-ons/paliers/usage/essai/changement plan/dunning/métriques SaaS/import CSV/
e2e/chatter. IDs : NTSUB1-5,7-8,12,21,31-34.

NTMAR — apps `einvoice`+`fiscal` : facture électronique DGI (dry-run), Simpl inerte, export
SIMPL-TVA/IS, calendrier fiscal, RAS étendues, timbre, attestations, UBO, veille réglementaire.
IDs : NTMAR5-12,14-20,24,28-33.

NTASS — app `assurances` complète : polices/garanties/primes, sinistres+indemnisation,
attestations, homme-clé/cyber, écrans, RBAC. IDs : NTASS1-29 (toutes).

## Archived from docs/plans/PLAN_VERTICALS.md — 2026-08-04

NTCON (BTP/EPC) — fondations app `btp_chantier` (réserves/punch-list, RFI, visas) + avenants
e-sign, DGD, déboursé-vs-facturé, diffusion plans. IDs : NTCON1-13.

NTPRO (immobilier/facilities) — app `immobilier` (patrimoine, locataires, baux, révision loyer,
quittancement→facture, relances, rentabilité) + budget/charges, états des lieux photos.
IDs : NTPRO1-16.

NTHOT (hôtellerie) — app `hospitality` (chambres, tarification saisonnière, réservations,
check-in/out, folio, taxe séjour, housekeeping, RevPAR/ADR) + main courante, recettes/coût
matière, événements/BEO, calendrier drag&drop. IDs : NTHOT1-3,5-9,11-14,17-21 (NTHOT4/10 restés
`[BLOCKED]`, NTHOT15-16/22 restés `[ ]`).

NTAGR (agriculture) — app `agriculture` (exploitation/parcelle, campagne, intrants stock, garde
DAR, registre ONSSA, main d'œuvre) + matériel agricole, irrigation+pompage solaire, lots/traçabilité.
IDs : NTAGR1-9,11-16 (NTAGR10 resté `[BLOCKED: hors périmètre VERTICALS]`).

NTESG (reporting ESG) — périodes figées, agrégation cross-app, catalogue GRI-lite, rapport PDF+
export xlsx, cockpit, objectifs trajectoire + intensité carbone, alertes dérive, comparateur N/N-1,
matérialité, politiques RSE, export DPEF, badge maturité, facteurs d'émission.
IDs : NTESG1-7,9-16 (NTESG8/17 restés `[ ]`).

## Archived from docs/FRONTEND_GAP_PLAN.md — 2026-08-04

Deux tâches vérifiées livrées le 2026-07-18 via WIR79 : FE-XKB1-3/ZCTR7-9 (inbox Approbations
autonome, route /approbations) ; FE-YHARD2 (onglet Historique/annuler dans AgentActions.jsx).

## Archived from docs/PLAN.md — 2026-09-20

### N100–N102 — clôture du lot post-vente/plateforme
Multi-tenant threadé sur `company` (N100, gardé volontairement DÉSACTIVÉ pour vente SaaS — cf. NEEDS YOUR INPUT), console tenant (N101), mise à jour de la doc de clôture (N102).
**Couverture :** N100–N102.

### Groupe PACT — pacte front↔back + écrans manquants
Gardes anti-régression posées (§A PACT1-9), méthode de construction contrat-d'abord (§B PACT10-14), passif corrigé (§C PACT15-27), 206 ressources/599 endpoints cartographiés puis câblés en écrans (§E-E4 PACT28-147 : finance/ventes/crédit/achats/fiscal, chantier/AO/BTP/agricole/éducation, RH/paie/portail/CRM/marketing/santé, socle/config/CPQ/GED/IA), puis l'audit du 03/08/2026 traité (§F PACT148-187 : AO, angles morts des gardes, capacités injoignables, champs fantômes). Atelier de toiture/calepinage AO monté et branché dans la foulée (PACT166-179).
**Couverture :** PACT5–PACT187.

### Groupe WIR (suite) — recâblage post-FRONTEND_GAP (audit 2026-08-14)
Zéro route appelée sans backend après le drain FRONTEND_GAP_PLAN (13/08) : fonctions serveur sans écran raccordées, doublons résorbés.
**Couverture :** WIR169–WIR283.

### Groupe SOL — spécialisation ERP solaire (décision fondateur 02/09/2026, plan V5b)
Éditions ERP, parcage des verticaux non-solaires, produit vendable.
**Couverture :** SOL1–SOL16.

### Groupe AUD1 — audit L3 « argent client » (rounds R1-R3, 02-03/09/2026)
96 constats R1 sur 8 lanes (facture-avoir, paiement-relances, devis→BC→facture, compta-GL, trésorerie, portail-argent, crédit-frais-einvoice, transverse) + Moitié B (compta/trésorerie/projets/contrats) — tout corrigé et testé.
**Couverture :** AUD101–AUD190.

### Groupe AUD2 — audit L3 stock & flux physiques (R2, 02-03/09/2026)
5 lanes (valorisation, mouvements-intégrité, achats-fournisseur, POS/WMS, e-commerce) : argent-faux corrigé en premier, puis sécurité/tenant, robustesse/courses concurrentes, structure.
**Couverture :** AUD201–AUD233.

### Groupe AUD3 — audit L3 installations/projets/documents terrain (R3, 02-03/09/2026)
6 lanes (chantier-lifecycle, interventions-terrain, docs-terrain-client, gestion-projet, BTP-programme-imports, transverse) : valeur légale des documents, sécurité/tenant, machines d'états, robustesse/N+1, structure.
**Couverture :** AUD301–AUD329.

### Groupe AUD4 — audit L3 sécurité, accès & multi-tenance (R4, 02-03/09/2026)
6 lanes (authentication-jwt, roles-rbac, publicapi-webhooks, celery-tenant-sweep, notifications-records, transverse-tenant-rls), dont l'activation ciblée de Row Level Security Postgres sur les tables argent (AUD422).
**Couverture :** AUD401–AUD422.

### Groupe AUD5 — audit L3 SAV, contrats, qualité & imports (R5)
25 constats + 5 gaps critiques de la critique adversariale, dédupliqués. Machines d'états contrat/QHSE/SAV réparées (statut non-décoratif, DELETE gardé), expiration ContratMaintenance câblée (décision D13), PDF contrat étiqueté « signature OTP simple loi 43-20 » (décision D11), imports dataimport (contrats/parc/leads) réparés, N+1 et cadences monitoring/beat corrigés, escalade SAV→litiges câblée. AUD504 (signature qualifiée DGSSI) RESTE, gaté coût prestataire — voir le fichier.
**Couverture :** AUD501–AUD503, AUD505–AUD529 (AUD504 non archivé, toujours en attente).

### Groupe AUDV — menu fondateur, features invisibles (14 items, 03/09/2026)
Exposition des 14 items cochés du « menu des features serveur sans écran » (source docs/rapport-orphelines.md, DRAFT165-*), dont le versionnement des plans AO (AUDV24, ex-AOF140).
**Couverture :** AUDV01–AUDV28.

### Groupe AUD6 — audit L3 avant-vente : AO, veille, CPQ, marketing (R6)
6 lanes (ao-argent-dossier, ao-fabrique-pipeline, veille-ao, cpq, marketing-moteur, transverse), dont le montage de 2 des 3 producteurs de pièces de la fabrique AO (bordereau des prix, acte d'engagement — AUD603).
**Couverture :** AUD601–AUD622.

### Groupe AUD7 — audit L3 RH, paie marocaine & flotte (R7)
6 lanes (paie-moteur, paie-déclaratif, rh-core, flotte, rh-paie-frontières, transverse).
**Couverture :** AUD701–AUD730.

### Groupe AUD8 — audit L3 fondation, reporting/paramètres, GED/chat, automation & méta-gardes CI (R8)
5 lanes de constats (core C1-13, reporting/paramètres F1-3, GED/KB/chat, dataimport/automation AUD-DIA-1..5, sweep FileField 17 champs bruts).
**Couverture :** AUD801–AUD836.

### Groupe RLC — relances : retour arrière, journal & état client (fondateur 08/09/2026)
Relevés de Reda du 08/09 sur le lead test1 aa : annulation d'une touche « Fait »/« Sautée » <24h avec effets défaits (RLC1), journal chronologique unifié du plan de relance (RLC2), confirmation douce avant de marquer « Fait » un message pas réellement ouvert (RLC3). PR #689, mergé 20/09/2026.
**Couverture :** RLC1–RLC3.

### Groupe CHT — module chantier : intégrité, connexions ERP (audit L3 du 12/09/2026)
8 lanes R1 + 4 lanes R2 + 2 vérificateurs R3, tout vérifié contre le code. Règle fondatrice : le module chantier ne garde que son cœur métier, le reste passe par les frontières services/selectors des autres apps. Cockpit « Pilotage chantiers » livré (CHT27) et intégrité/connexions ERP réparées.
**Couverture :** CHT1–CHT28.

### Groupe STKCAT — catalogue = référentiel unique (audit L3 « Pergola introuvable », 16/09/2026)
Sélecteur de structures piloté par le stock (StructureSelector remplace le Segmented acier/aluminium codé en dur), page Stock réparée, une seule donnée stock/CRM/devis, recherche insensible aux accents (migration stock/0148, sûre en échec), rôle de ligne stocké et propagé partout (pipeline 3D/kit inclus). Passe Fable finale : 1 bloquant + 5 défauts réels corrigés avant merge.
**Couverture :** STKCAT1–STKCAT27.

### Groupes déjà entièrement drainés, condensés sans reste
Sections retirées avec leurs menus vidés (toutes tâches `[x]`, aucune tâche en attente) : REFINEMENT QUEUE (3 tâches isolées CRM/Facturation/Chantiers, audit 2026-06-18) ; le préambule du groupe « App Appel d'offres » (AOF1-194, conception 2026-08-01) dont le travail réel a été livré sous les tâches PACT166-179/AUDV24/AUD603 ci-dessus, sans tâche AOF restante dans ce fichier.

### DONE LOG digest
Le journal ne conservait que les entrées récentes (RLC1-3, CHT27, STKCAT8/9/10/24/27, passe Fable STKCAT) ; les entrées plus anciennes des groupes ci-dessus avaient déjà été condensées lors de passes de nettoyage précédentes ou vivaient uniquement dans le corps des tâches (constats + fichiers vérifiés). Historique complet : git log sur docs/PLAN.md.

## Archived from docs/PLAN2.md — 2026-09-20

### Groupe CAL — Module Calepinage autonome (lots A-D)
Demande fondateur du 19/09/2026 : module de calepinage standalone, réutilisable depuis la fiche
lead CRM et depuis l'AO, sans dupliquer les deux systèmes existants (AO 2D, atelier 3D ventes).
219 tâches livrées (fondation, conception géométrie/imagerie/pose/ombrage, ingénierie électrique/
production/conso/pompage/mécanique, sorties documentaires/devis/réglementaire/bibliothèque/API).
CAL51 (Google Solar, gated fondateur) reste `[ ]` dans le fichier.
**Couverture :** CAL1–CAL224 (moins CAL51, gardée pendante ; quelques IDs fusionnés/supprimés à
la vérification du 19/09 n'ont jamais existé comme tâches), CAL231–CAL248.

### Groupe VTA — App VISITES autonome
Fondateur 12/09/2026 : sortie du CRM, app terrain "Ma journée" sans accès CRM ; PACT10 + passe
Fable R4 (3 bloquants corrigés) + enquête L3 R1-R3.
**Couverture :** VTA0–VTA17 (VTAG1 gardée pendante, décision fondateur).

### Groupe VT — Visite technique terrain
Fondateur 09/09/2026, PR #654 : checklist photos/mesures guidée, feu vert bureau d'études, toit
assemblé par photos drapées sur la carte (OpenCV Stitcher, dépendance `opencv-python-headless`).
**Couverture :** VT0–VT13 (VTG1 gardée pendante, gated coût/infra).

### Groupe CKP — Cockpit CRM "suivre les étapes"
Fondateur 10/09/2026 : vérité des sautées d'étape, cadence réactive, adhérence à deux vues.
**Couverture :** CKP0–CKP6.

### Groupe PV / PVG — Toiture 3D + Outil de calepinage
Fondateur 14/08/2026 : direction PVsyst, départ du devis, édition manuelle, schéma électrique.
87 tâches livrées.
**Couverture :** PV1–PV83, PVG1–PVG4.

### Groupe PUB-P8 — Le moteur AGIT
Synthèse décisive 20/07/2026 (5 enquêtes vérifiées adversarialement), dé-gaté par le fondateur le
20/09/2026 ("lance PUB-P8"), drainé en 4 phases opus séquentielles (18/18), PR #689. Multiplication
des gagnants, chaîne de création réelle, portes d'autonomie. PUB132/133 restent `[ ]` (budget
fondateur fal.ai / template-vidéo).
**Couverture :** PUB116–PUB135 (moins PUB132, PUB133).

### Groupe QJR — Reconstruction du parcours devis (M0–M6 + post-programme)
Audit L3 du 29/08/2026, décisions fondateur D1-D12 tranchées. Contrats seuls d'abord (PACT10),
gardes/corrections client-facing, entrées canoniques + API monnaie, décomposition de services.py,
étapes du pipeline, bascules golden-identiques (passes Fable pré-merge à chaque bascule), contrats
de parcours + conversions de tests, puis 52 tâches post-programme (sécurité OTP, chiffres client,
structure, PDF). QJR113 (moteur serveur indus/commercial/agricole) reste `[ ]` — chantier séparé
post-programme, décision fondateur D10 (à ouvrir sur le mot "lance le chantier D10").
**Couverture :** QJR1–QJR168 (moins QJR113, gardée pendante ; quelques IDs jamais attribués).

### Groupe QJR2 — Contre-visite du parcours devis
Vérification post-build du 30/08/2026, 0 constat réfuté, décisions fondateur DV1-DV3. Corrections
client (test rouge d'abord), câblage, garde-fous, dette technique.
**Couverture :** QJR200–QJR246.

### Groupe QJR3 — Ronde 3 du parcours devis
Vérification du 31/08/2026, 2 constats forts prouvés par exécution + 7 résidus confirmés.
**Couverture :** QJR300–QJR309.

### Groupe QJR4 — Ronde 4 du parcours devis
Fin de série, décisions fondateur DR1-DR8 tranchées le 31/08/2026 : argent/chiffres client,
sécurité, hygiène/câblage/honnêteté des textes.
**Couverture :** QJR400–QJR432.

### Groupe EZ — L'ERP le plus FACILE
Fondateur 01/08/2026. Seule EZ17 restait à construire (gate CI des budgets de clics des 5
trajets quotidiens) ; les autres tâches EZ étaient déjà archivées lors d'une passe précédente.
**Couverture :** EZ17.

### Groupe VAO — Veille appels d'offres
Fondateur 01/08/2026 : voir tous les avis publics du Maroc, porte automatique + porte manuelle.
Socle (app + SAS des avis), collecteur portail pur testable hors ligne, collecte/planification/
alarme, porte manuelle (leçon FRDISI), écrans. VAO1/2/4/5/39-44 restent `[ ]` (décisions/dépenses
fondateur, règle #5).
**Couverture :** VAO3, VAO6–VAO38.

### Groupe CRX — Radiographie du CRM
Audit L3 du 02/09/2026, 29 agents / 4 rondes, décisions fondateur D-CRX1-4. Correctness + sécurité
du CRM ; le volet architecture (CRXB1-8) reste gated au mot fondateur "lance CRXB".
**Couverture :** CRX1–CRX41 (CRX6 jamais attribué).

### Groupe MRY — Moteur de relances de Meryem
Sessions des 03-04/09/2026 (Guide de Meryem v2.1, Protocole de rappel v3) : arrivée des leads
consolidée, cadences automatiques (6 appels/14 jours), arrêts, messages FR/darija, Cockpit, KPI.
**Couverture :** MRY0–MRY33 (MRY24, MRY27 jamais attribués).

### DONE LOG digest
Les en-têtes `#### DONE LOG` propres à CAL/VTA/VT/CKP/PV/PUB-P8/PUB-dépendances et le `## DONE LOG`
de fin de fichier ont été vidés de leurs entrées narratives (dates/PR/détails techniques déjà dans
git) ; un en-tête vide reste par section encore active pour les prochains runs.

## Archived from docs/WEB_PLAN.md — 2026-09-20

### WJ127–WJ130 — finitions revue Fable (parcours 3D + proposition), 2026-08/09
Teaser honnête sans estimation, robustesse simulateur batterie, durcissements mineurs, clé d'idempotence CSPRNG.
**Couverture :** WJ127–WJ130

### Groupe QJW — parcours devis côté site (tunnel unifié + page proposition), 29/08–06/09/2026
Registre de champs + buildBody unique + bascule FR/EN/AR (16 champs jusque-là non collectés en EN/AR) ;
moteur de liaison générique pour la page proposition (finit les ~500 lignes câblées à la main) ; gardes
de parité (tunnel/liste blanche/couverture) ; contrats PACT10 web ; alignement tarif T5 site↔ERP ;
finitions diagnostic + décision CAPI/consentement ; contre-visite 30/08 et ronde 4 (IP signataire).
**Couverture :** QJW1–QJW15, QJW17–QJW23, QJW24–QJW25 (QJW16 reste en attente)

## Archived from docs/ERROR_PLAN.md — 2026-09-20

### BUILD QUEUE
Débordement PDF résidentiel absorbé par les retouches juillet (paginée auto-calibrée, 6/6 tests OK, prouvé 4→3 pages image prod). **Couverture:** ERR114

## Archived from docs/new_tasks_plan.md — 2026-09-20

Tier PLATEFORME du backlog NT (2 084 tâches d'origine). 475 tâches `[x]` archivées ici en 4
vagues : 2026-08-13/14 (drain mobile/data/AI massif), 2026-08-31 (couche sémantique), 2026-09-12
(4 vagues NT : obs/ux/grc/mobile-tail), 2026-09-20 (PR #689, drain plateforme final 114 tâches).
65 tâches `[BLOCKED…]`/`[ ]` restent dans le fichier, byte-identiques.

### Groupe NTGRC — GRC & Privacy
Entièrement livré (2026-09-12) : socle privacy loi 09-08/RGPD, pilier GRC, incidents sécurité +
cockpit DPO + e-discovery. **Couverture :** NTGRC1–9, 13–35.
### Groupe NTAPI — Plateforme API & intégrations
Versioning, quotas/débit/webhooks, endpoints bulk/évènements, OAuth2/portail dev, connecteurs
no-code, EDI, monitoring livrés ; SDK JS/n8n/EDI EDIFACT-ORDERS restent gated (pending).
**Couverture :** NTAPI1,2,4,6,11–19,28,30,32,35–43.
### Groupe NTEXT — Extensibilité no-code
Objets custom, automatisations, marketplace, vues partagées, gabarits livrés ; quotas plateforme
(NTEXT32, décision fondateur) reste pending. **Couverture :** NTEXT1,4–12,14–31,33–40.
### Groupe NTDATA — Plateforme data & BI
Catalogue datasets, couche sémantique (2026-08-31), qualité données, MDM léger, entrepôt,
dashboard builder, abonnements rapports livrés. Reste : conso métriques aval, benchmarks tenant.
**Couverture :** NTDATA1–9,11,13–24,26,27,29–34,36–43.
### Groupe NTAI — ERP AI-native
Gouvernance/socle AI, copilotes contextuels, document AI, onboarding data livrés (2026-08-13/14).
Boucle correction (NTAI18), extraction appel (NTAI22), RAG global (NTAI25) restent pending.
**Couverture :** NTAI1–13,15–25,27–37 (dont versions livrées de 18,22,25).
### Groupe NTWFL — BPM & case management
Approbation d'entreprise unifiée, designer visuel, formulaires/inbox, case management, délices
livrés (2026-09-20). Historique de version (NTWFL26) reste pending.
**Couverture :** NTWFL1–25,27–34.
### Groupe NTOBS — Fiabilité vendue au client
Status page, SLA, réversibilité, transparence limites, mode dégradé, rapports, celery beat,
API/webhooks, e2e, résilience livrés (2026-09-12). Budgets CI (NTOBS12) et écran
ReliabilitySettings (NTOBS21) restent pending. **Couverture :** NTOBS1–11,13–20,22–34.
### Groupe NTP2P — Procure-to-Pay & spend management
Plan d'approbation, catalogue interne, budgets, onboarding fournisseur, scoring risque,
rapprochement 3-voies, dashboard spend, wizards, réglages tenant, celery beat, API/webhooks,
imports/exports, e2e, chatter, KPI livrés. Per-diem RH/paie, cartes d'achat gated, doublons
bloqués (SoD, favoris, budget) restent pending. **Couverture :** NTP2P2–4,7–11,14,17–23,25–47.
### Groupe NTUX — UX power-user
Entièrement livré (2026-09-12) : permissions vues, webhooks, API publique favoris/vues, audit,
notifications, KPI adoption, drag-and-drop, export/import CSV, e2e.
**Couverture :** NTUX1,7,9,12–13,21,24,26–33,35–40.
### Groupe NTMOB — Mobile enterprise
Entièrement livré (2026-08-13) : offline-first, accueils par rôle, approbations/géo-workflows,
capture terrain, confort terrain, délices, cache hors-ligne.
**Couverture :** NTMOB1–3,6–9,11–13,15–33.
### Groupe NTPRT — Portails
Fondation auth portail, portail client complet, portail fournisseur complet livrés. "Mon
équipe", leads distribués, domaine personnalisé (COST) restent pending.
**Couverture :** NTPRT2–4,6–16,18–23,25–28,30–32,34–38.
### Groupe NTI18N — Internationalisation profonde
RTL/langue utilisateur, calendrier fériés, adresses structurées, plusieurs volets « round 2 »
(wizards, réglages tenant, celery beat, imports/exports) livrés. Devise tenant, pack pays FR, PV
RTL, restrictions rôle et d'autres volets round-2 restent pending.
**Couverture :** NTI18N1–8,10–15,17–20,22–29,31–40,43,45–47,49,51–52.
### SECTION C — Verticaux (résidu)
NTSAN/NTEDU déménagés le 2026-09-02 vers `docs/backlog/FULL_SAAS_PLAN.md` ; les 4 tâches déjà
livrées ici sont archivées, la section (vide) est retirée.
**Couverture :** NTSAN24, NTSAN40, NTEDU24, NTEDU33.
### Groupe NTIDE — Innovation & Boucle de Feedback Produit
Sur les 67 tâches proposées, 27 lignes `[x]` existaient dans ce fichier (chatter idée, canal
feedback in-app, intégrations/admin, tests+docs) — toutes livrées ; section + Context/Summary/
Key Decisions/Buildability/Notes dédiées retirées (échafaudage devenu obsolète).
**Couverture :** NTIDE3, NTIDE42–67.
### Groupe NTMIG — Kits de migration ERP sortants
Socle projet de migration, kits par source, écrans migration, playbooks versionnés, fiabilité
livrés. Annuaire partenaires certifiés et alerte expiration (NTMIG29–31, doublons bloqués)
restent pending. **Couverture :** NTMIG1–38.

### DONE LOG digest
En-tête vidé, remis à zéro pour les prochains runs (historique détaillé : git log de ce fichier
avant 2026-09-20).

## Archived from docs/FRONTEND_GAP_PLAN.md — 2026-09-20

### Round-2 frontend wiring drain (2026-08-13, most audit-only, no code needed)
19 lanes drained: flotte, qhse, ged, contrats, gestion_projet, paie, rh, sav, litiges, compta (×2
groups), stock, installations, SAV additions, kb, pos, ventes, crm, reporting (partial), platform.
Vast majority were already fully wired (ticked `(déjà présent)`); real gaps found and built in
ventes (FE-effets, FE-immo-caisse-actions, FE-rapprochement-detail, FE-COMPTA21, FE-ZSAL8/XSAL16
BC-PDF menu item), gestion_projet (FE-XPRJ7-8/ZPRJ5-6 heures-attendues tab), qhse (FE-XQHS17/14/
15-18-19/23-27 new screens), installations (later corrected by WIR247), and SCA41 async export
polling. FE-XSAL6/XSAL1-3 unblocked later by WIR281/WIR226 (2026-08-26).
**Couverture :** FE-COMPTA21,39 ; FE-CONTRAT7,12,13,15,16,23,33 ; FE-FG122,145,146 ; FE-GED14,16,26 ; FE-PROJ11 ; FE-SCA41 ; FE-XACC3,9,33 ; FE-XCTR2,5,7,14,17 ; FE-XFAC14 ; FE-XGED1,2,7,8,14,15,19,26 ; FE-XMFG1 ; FE-XPAI1,3–5,8,16,22 ; FE-XPLT1,18,23 ; FE-XPRJ4,5,7,10,14,21 ; FE-XQHS14,15,17,23 ; FE-XRH9,11,15,29 ; FE-XSAL1,6 ; FE-YHARD3 ; FE-YHIRE3 ; FE-ZACC1,3,14 ; FE-ZGED7 ; FE-ZPAI1,4 ; FE-ZPRJ1,7 ; FE-ZRH3,14 ; FE-ZSAL8.
(un ID par ligne de tâche, comme les compte plan_progress.py ; chaque ligne pouvait nommer des frères en plus.)

## Archived from docs/plans/PLAN_CRM_VENTES.md — 2026-09-20

### Groupe NTCPQ — CPQ enterprise (P1/P2/P3 + round 2)
Vagues 2026-08-13/14 (5+3 lanes, 2 merges) : clauses CGV, renouvellement/avenant devis, variantes,
paliers remise cascade, multi-lots, cross-sell, config, paramètres/permissions, jobs beat, imports/exports, chatter/audit, KPI.
**Couverture :** NTCPQ11, NTCPQ13–14, NTCPQ16–22, NTCPQ24–26, NTCPQ28–34, NTCPQ36–37, NTCPQ41–42, NTCPQ45–49.

### Groupe NTCRM — CRM enterprise (P2+P3, groupe entier livré)
Vague 2026-08-13 (5 lanes) : comptes dormants, score d'engagement, salle de vente digitale + analytics,
apporteurs d'affaires + commission, défis/leaderboard, playbook, revue de compte.
**Couverture :** NTCRM14–30 (17 tâches).

### Groupe NTMKT — Marketing automation (P1–P3 + round 2 partiel)
Vagues 2026-08-13/14 : journeys en graphe, progressive profiling, score de maturité, attribution
multi-touch, préférences self-service, wizards/rapports, purge/relances beat, exports, audit.
**Couverture :** NTMKT12–35, NTMKT39–42, NTMKT44–45.

### Groupe NTDMO — Démo/onboarding (P2 + round 2 partiel)
Vague 2026-08-14 : tours contextuels, données démo Faker/notifs/champs perso, kit démo, wizards
démo/first-run, réglages tenant, purge démo beat, garde présentation, e2e, chatter/audit.
**Couverture :** NTDMO14–20, NTDMO22–28, NTDMO30, NTDMO33, NTDMO37–40.

## Archived from docs/plans/PLAN_DOCS_JURIDIQUE.md — 2026-09-20

### Groupe NTDOC — CLM enterprise (24 tâches, drainées 12/09 en 3 vagues NT)
Négociation par redlines (contrepartie/diff/commentaires/cycle), clauses obligatoires + déviation, app `datarooms` (salles multi-viewer, watermark, journal, fermeture+audit), durcissement signature publique + certificat vérifiable, matrice obligations/pipeline renouvellement/préavis configurable, templates conditionnels, TSA de secours, réglages CLM société, purge beat contreparties, wizard clauses manquantes.
NTDOC1–7, NTDOC9–16, NTDOC18–22, NTDOC26, NTDOC29, NTDOC32, NTDOC44 — tout livré (contrats/ged/datarooms).
**Couverture :** NTDOC1-7, NTDOC9-16, NTDOC18-22, NTDOC26, NTDOC29, NTDOC32, NTDOC44.

### Groupe NTJUR — app `apps/juridique` (22 tâches, batch 2 drain NT 12/09)
Nouvelle app contentieux : DossierJuridique + machine à états, parties, audiences, cabinets/mandats/notes d'honoraires, budget engagé/consommé, provisions compta proposées (jamais auto), workflow d'approbation, écrans registre/détail/dashboard, timeline, permissions fines mandats/approbation, scope publicapi `juridique:read`, KPI reporting, escalade depuis litiges.
NTJUR1,2,5,6,9-12,14,15,19,20,22-24,26,28,32,39-41,48 — tout livré.
**Couverture :** NTJUR1, NTJUR2, NTJUR5, NTJUR6, NTJUR9-12, NTJUR14, NTJUR15, NTJUR19, NTJUR20, NTJUR22-24, NTJUR26, NTJUR28, NTJUR32, NTJUR39-41, NTJUR48.

### DONE LOG digest
4 entrées 2026-09-12 (vagues 1-4 drain NT) : lane docs-juridique, docs-tail, juridique, jur-tail — PR/migrations contrats 0047-0057.

## Archived from docs/plans/PLAN_FINANCE.md — 2026-09-20
### Groupe NTADM — Administration enterprise (clos, 0 tâche restante)
Livré en 3 lanes plateforme multitenant (2026-08-05) + drain finance 2026-09-12 : entités/périmètre rôle, flags/plans/licences+sièges, notifications produit, admin délégué, impersonation auditée, vue groupe, rapports/wizards/beat/permissions/webhooks/API/e2e round 2.
**Couverture :** NTADM2, NTADM3, NTADM7, NTADM8, NTADM9, NTADM18, NTADM19, NTADM20, NTADM21, NTADM22, NTADM25, NTADM26, NTADM29, NTADM32, NTADM37, NTADM39, NTADM41, NTADM42, NTADM44.
### Groupe NTTRE — profondeur round 2 (partiel)
Widget cash du jour, exports xlsx/PDF, wizards rapprochement/paiement/effet, rapports journal/effets/pouvoir bancaire, import CSV plafonds (drain 2026-09-12). Reste ouvert : parsers formats, 4-yeux, KPI.
**Couverture :** NTTRE17, NTTRE19–20, NTTRE21–23, NTTRE24–26, NTTRE37.
### Groupe NTSUB — profondeur round 2 (partiel)
Relevé d'abonnement PDF, wizard migration plan rétroactif, réglages tenant, purge/recalcul beat métriques (drain 2026-09-12). Catalogue/dunning/PCA/self-service restent ouverts.
**Couverture :** NTSUB20, NTSUB23, NTSUB24, NTSUB26–27.
### DONE LOG digest
NTCRD 39 tâches (PR batch 1, 07/17) ; NTSUB 13 tâches (PR batch 4, 07/17) ; NTMAR 22 tâches (PR batch 7 finale, 07/17, apps einvoice/fiscal) ; NTASS 29 tâches (PR batch 1, 07/17, app assurances) — groupe NTASS sans tâche restante, section retirée.

## Archived from docs/plans/PLAN_RH_PAIE.md — 2026-09-20

### Groupe NTHCM — HCM talents (Workday/Rippling/Lattice/BambooHR)
4 lanes livrées 2026-09-12 (drain NT) : manager/organigramme/headcount, cycles de révision
salariale + enveloppes, OKR entreprise, 9-box, succession + risque, enquêtes d'engagement,
feedback continu, parcours de formation + assignation + certifications, onboarding/offboarding
multi-acteurs, analytics diversité/absentéisme/corrélation formation-performance.
**Couverture :** NTHCM1–10, NTHCM12–17, NTHCM19, NTHCM21, NTHCM23–25, NTHCM27–29.
### Groupe NTPAY — Paie conformité industrielle & multi-pays (ADP/PayFit/Deel/Sage)
3 lanes livrées 2026-09-12 (drain NT) : rappels rétroactifs de barème, schéma comptable
configurable, bordereau CNSS/télépaiement, dépôts déclaratifs, certificat de travail art.72,
moteur multi-pays (PaysPaie + dispatcher + barèmes, hors packs FR/SN/CI GATED fondateur),
multi-devise, simulateur coût d'embauche + lettre d'offre, cockpit conformité, comparateur de
barèmes, rapports charges/masse salariale/registre annuel, wizards barème + clôture, paramétrage
société, gabarits déclaratifs versionnés, rappels d'échéances + recalcul cumuls.
**Couverture :** NTPAY1–8, NTPAY12–26.

## Archived from docs/plans/PLAN_SERVICE.md — 2026-09-20
### Groupe NTSRV — service client omnicanal (drainé 2026-09-12)
Boîte omnicanale (email/portail/WhatsApp gated), routage compétences/SLA heures
ouvrées/escalades, gestion Problème+wizard, CSAT/FCR/perf agent, fiche PDF interne,
wizard clôture, réglages tenant, permissions, beat SLA, import compétences, KB↔ticket.
**Couverture :** NTSRV1–3, NTSRV5–8, NTSRV11–12, NTSRV16–20, NTSRV23–24, NTSRV27–28,
NTSRV30–31, NTSRV33–34, NTSRV38–40, NTSRV43.
### Groupe NTFSM — van-stock & zone : seuils/réappro + onglet mobile ; zone équipe.
**Couverture :** NTFSM18–20, NTFSM26.
### Groupe NTNRG — énergie : rapport garantie perf+SLA dispo ; carbone attestation+
registre ; pertes catégorisées+benchmark. **Couverture :** NTNRG11, NTNRG14,
NTNRG26–27, NTNRG32–33.
### Groupe NTPRJ — PSA : WIP/PCA auto-alimenté projets→compta. **Couverture :** NTPRJ3.

## Archived from docs/plans/PLAN_SUPPLY.md — 2026-09-20

### Groupe NTWMS — Entrepôt & logistique
Vagues 2-3 (14/08, toutes datées ainsi, aucun PR# noté) : casiers/put-away/picking FIFO-FEFO, cockpit entrepôt, scanner mobile, quais/RDV transporteur, cross-dock, traçabilité lot, 3PL, RMA, comptage ABC ; kitting `installations` jamais dupliqué.
**Couverture :** NTWMS1–NTWMS43 sauf NTWMS14 (inexistant) et NTWMS22 (en attente).

### Groupe NTSCM — Planification supply chain
Vagues 1-3 (14/08) : prévision demande, classification ABC, cycle S&OP complet, réappro groupé MOQ, scorecards OTIF/qualité/TCO, simulation pénurie ; toute la profondeur round 2 (rapports/réglages/beat/API/tests/KPI) livrée.
**Couverture :** NTSCM1–NTSCM47 sauf NTSCM10/17/23 (en attente).

### Groupe NTDST — Négoce/distribution
Vague 3 (14/08), livraisons isolées : consignation, RFA→avoir, ATP daté, stock véhicule, catalogue B2B, relevé+export XLSX, paramètres société.
**Couverture :** NTDST3, 5, 10, 14, 18, 24, 30, 31, 41.

### Groupe NTRET — Retail & e-commerce
Vagues 2-3 (14/08) : caisse offline, X/Z officiels, PIN multi-caissier, arrhes, transfert magasin 2 temps, étiquette EAN, connecteurs Shopify/WooCommerce (`ecommerce_connect`). App `fidelite` construite PUIS REVERTÉE (doublon `marketing.CompteFidelite` FG240) — décision fondateur requise avant reprise.
**Couverture :** NTRET1–NTRET32 sauf NTRET4/6/9/10/11/14/21/26/27 (en attente).

### Groupe NTLOG — Transport & douane
Nouvelles apps `transport` (ordres, coûts fret, litiges, POD) et `douane` (dossiers export, paramètres, permissions) (14/08). Volet import bloqué par doublon `installations.DossierImport` (FG315, garde WIR80).
**Couverture :** NTLOG1–NTLOG51 sauf NTLOG5 (inexistant) et NTLOG6/10/11/12/13/15/21/22/23/26/28/30/33/37/40/41/42/45/46 (en attente).

### Groupe NTMFG — Production / MRP II
Nouvelle app `mrp` quasi complète (14/08) : postes de charge, gammes, OF à capacité finie, backflush, MRP net, terminal atelier MES, coûts standards versionnés, TRS/OEE, profondeur round 2.
**Couverture :** NTMFG1–NTMFG40 sauf NTMFG13/21/25/34 (en attente).

## Archived from docs/plans/PLAN_VERTICALS.md — 2026-09-20

### NTCON — Vertical BTP/EPC (suite, round 2)
2026-09-12, 2 lanes (verticals-btp + verticals-tail) : lots/Gantt/pénalités par lot, PPSPS↔QHSE avec guard sous-traitance, registre intervenants, photo-rapport hebdo, checklist réception, export dossier ZIP, cockpit BTP, rapport avancement PDF, wizards création/clôture chantier, paramètres tenant, permissions fines, purge/cache Celery beat, imports/exports, API publique+webhooks, chatter/audit/notifications, KPI, capture terrain offline, alertes visas.
NTCON14–34, 36–37 — tout livré (NTCON35 reste bloquée, cf. tâche en attente).
**Couverture :** NTCON14–34, 36–37

### NTESG — Reporting ESG
2026-09-12 (lane verticals-tail) : wizards guidés clôture de période et création d'objectif de trajectoire, réglages ESG par société (seuils, pilote, pondération maturité).
NTESG18, NTESG19, NTESG20.
**Couverture :** NTESG18–20

## Legacy archive (ex-docs/DONE.md, condensé 2026-08-04 — texte intégral dans l'historique git)

Neuf passes d'archivage (« clean the plans ») ont déplacé les tâches `[x]` des plans actifs vers
l'ancien `docs/DONE.md` ; condensé ici en une seule histoire par plan/passe.

### PLAN.md — première passe
2026-06-16/17. T1-17 (PDF devis, PWA, actions masse, édition inline, recherche globale+notifs,
réglages différés, expiration devis+dashboard, édition masse catalogue, import/export, révisions
devis, champs perso, export TVA, hub Rapports, contrats maintenance, garde remise). Puis N1-99 :
Chantier+Parc installé, BC fournisseur, conformité facture marocaine (Art.145/ICE/TVA/numérotation/
UBL), dossiers 82-21/Art.33, SAV+garanties+contrats entretien, hub Paramètres, PWA étendue,
parrainage+commissions. G4/L7 réouverts « déjà livré ».
**Couverture :** T1-T17 ; N1-N13, N15-N19, N21-N49, N54-N57, N61-N63, N66, N70-N71, N77-N78,
N80-N84, N90, N95, N98-N99 (reste N — N14,N20,N26,N36,N50-53,N58-60,N64-65,N67-69,N72-76,N79,
N85-89,N91-94,N96-97,N100-102 — livré dans les passes plus bas).

### PLAN2.md — première passe
2026-06-17/18. Extraction marque+tokens Tailwind4 (F14-20), bibliothèque shadcn/Radix/TanStack
(G21-30), vitrine `/ui` (P68). Flux acceptation devis (A1-4), correctif pièces-jointes MinIO (B1),
menu iPhone (C1)+rechargement PWA (C2), Paramètres en onglets (D1)+numérotation (D3)+devis
éditable/versionné (D5). Suite Playwright E1-16 (a débusqué le bug loader/modales).
**Couverture :** F14-F20 ; G21-G22,G25,G28-G30 ; P68 ; A1-A4 ; B1 ; C1-C2 ; D1,D3,D5 ; E1-E16.

### WEB_PLAN.md — première passe
2026-06-17/18. Cerveau estimateur (routes noindex `/preview/toiture-3d-pro-3`→`pro-11`) : azimut
réel+PVGIS, optimum exhaustif, toit en pente/tuiles, optimiseur LIVE contraint, moteur production
serveur, fenêtre Année/Mois/Jour. Plus 5 pages villes+5 études de cas+FAQ/guides/pourquoi-taqinor/
garanties/marocains-du-monde, barème ONEE régie corrigé, refonte nav, guide STYLE.md+réécriture,
audit world-class (témoignages/garantie/portrait/marques).
**Couverture :** W1-W66.

### PLAN.md — passe « clean 2026-06-20 »
2026-06-19. Régressions live N103 (changement rôle bloqué) et N104 (pièces jointes cassées).
Vagues REFINEMENT QUEUE (raffinements ROUTINE tous modules) + file N différée : réservation/
consommation stock (N14), supervision+Huawei FusionSolar (N50-52), export UBL DGI (N105),
automatisation no-code+approbation (N72-73), tarifaire ONEE+ROI PVGIS (N64-65), littéraux PDF→
réglages versionnés (N26,N36,N59-60,N67,D2), email Brevo+Celery Beat (N87-88/G9), module terrain
F1-24, étiquettes QR (N20), carte Leaflet parc (N85), export CSV/XLSX (N97), RBAC/visibilité/audit
(N68-69/D4).
**Couverture :** N14,N20,N26,N36,N50-52,N58-60,N64-65,N67-69,N72-75,N85-89,N97,N103-107,G9 ;
F1-F20,F22-F24 (F21 différé WOW16).

### PLAN2.md — passe « clean 2026-06-20 »
2026-06-18/19. Primitifs restants (select/date-picker/upload/formulaires G23/24/26/27), DataTable
H31-33, shell/nav I34-38, restylage module J39-50, dashboard+hub reporting K51-52, puis L/M/N/O/P
(iOS, a11y, perf/bundle, migration CSS→index.css, docs). Plus RBAC 7 rôles+prix d'achat gatés
(D4/N68-69), hiérarchie équipe+visibilité+audit, littéraux DEVIS (D2). M59 (logo) reste gaté.
**Couverture :** G23,G24,G26,G27 ; H31-H33 ; I34-I38 ; J39-J50 ; K51,K52 ; L53-L57 ; M58,M60-M62
(M59 gaté) ; N63,N64 ; O65,O66 ; P67,P69 ; D2,D4.

### WEB_PLAN.md — passe « clean 2026-06-20 »
2026-06-19. i18n complète FR/EN/AR RTL sur ~34 pages (W67). Estimateur pro-11 : édition manuelle
24 barres conso+calculateur appareils (W68), disposition panneaux glisser-déposer (W69).
**Couverture :** W67, W68, W69.

### PLAN.md — passe WOW16 (2026-07-09)
2026-06-20→07-09. Correctifs : 500 upload MinIO (N108), web push dormant (N109), diagnostic
changement rôle (N110). Refactor M1-7 (FK-string cross-app, services/selectors, import-linter,
bus d'événements, éclatement god-files). Comblement FG1-399 (RH, automatisation, champs perso,
conflits affectation, changelog). Cinq nouvelles apps : paie (PAIE1-36), CGNC (COMPTA1-40),
programmes multi-chantiers (PROJ1-38), GED (GED1-38), flotte (FLOTTE1-35), QHSE (QHSE1-40), KB
(KB1-7), litiges (LITIGE1-6). Audit intégrité DC1-42 (fuite identité société, FK nullable,
consolidation fiche employé). Écrans UX1-47. Suite parité Odoo ODX/X-/Y-/Z-. Capture terrain
offline (N91/F21), i18n+RTL complet (N93-94), 2FA+sessions+rotation mdp (N96).
**Couverture :** N53,N76,N79,N91-N94,N96,N108-N110,F21,G5 ; M1-M7 ; FG1-FG385,FG387-FG399
(FG386 absent) ; PAIE1-36 ; COMPTA1-40 ; PROJ1-38 ; GED1-38 ; FLOTTE1-35 ; QHSE1-40 ; KB1-7 ;
LITIGE1-6 ; DC1-33,DC35-42 (DC34 absent) ; UX1-47 ; ODX2-4,ODX9,ODX10,ODX21 ; XACC1-36,XFAC1-29,
XPUR1-26,XSTK1-23,XMFG1-16,XSAL1-17,XMKT1-37,XPOS1-18,XPRJ1-29,XFSM1-24,XSAV3-28,XCTR1-22,
XFLT1-30,XQHS1-27,XRH1-34,XPAI1-26,XGED1-30,XKB1-34,XPLT1-23 ; YCASH4,YPROC3-10,YSERV1-13,
YLEDG1-13,YHIRE1-14,YSTCK1-8,YDOCF1-7,YLEAD8-14,YSUBS1-9,YEVNT2-12,YRBAC1-9,YOPSB1-14,YTEST1-17,
YDATA9 ; ZACC1-16,ZFAC1-12,ZSAL1-8,ZPUR1-11,ZSTK1-12,ZMFG1-12,ZPRJ1-12,ZFSM1-7,ZSAV2-10,ZRH1-18,
ZPAI1-12,ZMKT1-20,ZGED1-15,ZCTR1-12 ; YHARD2-12.

### PLAN2.md — passe WOW16 (2026-07-09)
Lot Quote Journey (QJ) : suivi ouverture, notif vendeur, Celery Beat, relance auto, expiration
devis, scoring leads, avancement auto NEW→CONTACTED, dédup webhook, Meta CAPI, e-signature loi
53-05+OTP, financement, tables 82-21, email serveur, variantes devis, dashboard commercial,
RDV self-service (+ WhatsApp gaté). Plus groupes U/Q/AG/S/QF-QG-QS-QD-QP/CH/QK/MB/WR et 2e vague
refonte UI (F-P, F120-P171).
**Couverture :** QJ1-QJ31 ; QW1-QW6,QW9,QW10 ; G10 ; U1-U14 ; Q1-Q7 ; AG1-AG12 ; S1-S20 ; QF1-QF9 ;
QG1-QG12 ; QS1-QS4 ; QD1-QD2 ; QP1-QP2 ; CH1-CH6 ; QK1-QK6 ; MB1-MB6 ; WR1-WR12 ; QC1 ; F120-F123 ;
G124-G128 ; H129-H133 ; I134-I138 ; J139-J146 ; K147-K149 ; L150-L153 ; M154-M158 ; N159-N163 ;
O164-O166 ; P167-P171.

### WEB_PLAN.md — passe WOW16 (2026-07-09)
Audit adversarial 24 agents : WJ39-59 corrige EN/AR (traductions, CTA FR en dur, géocodeur, fuite
langue signature) + comptant/échelonné + demande modif structurée + télémétrie + partage WhatsApp +
badges délai + analytique funnel. W245-381 balaie le reste (indexation tunnel, DiagnosticForm
retiré, widget estimation home, /nos-solutions+financement/pompage/maintenance, fraîcheur 82-21,
correctifs SEO/confiance). WA1-37 retire portrait fondateur des accueils (garde /à-propos). WB1-35
corrige l'exposition rendement falsifiable (relabellisée au cas par cas). WC1-12 vérifie mobile/RTL
iPhone réel. WN1-8 corrige un blog vide. WJ1-38 et W70-244/W222-235 couvrent le reste vague
croissance/SEO/i18n/recharge-véhicule/82-21.
**Couverture :** WJ1-WJ109 ; W70-W381 (quelques ID isolés absents — W140,W186-187 — voir git) ;
WA1-WA37 (WA12 absent) ; WB1-WB35 (WB5 absent) ; WC1-WC12 ; WN1-WN8.
