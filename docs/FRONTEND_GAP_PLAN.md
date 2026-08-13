# FRONTEND_GAP_PLAN.md — wire the round-2 backends to the UI

**Why this plan exists.** A 2026-07-06 code-level audit (not plan-checkbox based) found a
**repo-wide systematic gap**: the round-2 build-outs (X-series `XFLT/XQHS/XGED/XCTR/XPRJ/XPAI/XRH/XSAV/XACC…`
and Z-series `Z*`) shipped **backend-only** — the paired frontend half of each task was never
built, even though most tasks named a `frontend/` file in their own "Files:" line. Backends are
real, tested, and merged (in b4 / batch-3+4); the UI simply never caught up. Each item below is a
**frontend wiring task**: add the `<domain>Api.js` client entries + the screen/tab/button + nav, and
a focused test, calling the EXISTING backend endpoint.

## HOW TO RUN (same model as `work on the plan`)
- Drain this BUILD QUEUE as ONE work-stealing pipeline; land as ONE gated self-merge at the end,
  then `powershell -File scripts/deploy-prod.ps1` (ERP frontend deploys manually — NOT Cloudflare;
  that's `apps/web` only, out of scope here).
- **Lane = one frontend domain.** They are file-disjoint (`features/<domain>/` + `api/<domain>Api.js`
  + the domain's own auto-registered `module.config.jsx`), so up to 8 run in parallel with near-zero
  fold conflict. `python scripts/plan_lanes.py docs/FRONTEND_GAP_PLAN.md` for the graph.
- **Per task:** verify-not-already-wired (grep the api client + component first) → add api entry +
  screen/tab/nav → focused vitest/RTL test that keeps the e2e DOM hooks intact → `npm run lint` +
  targeted vitest → commit that task → next.
- **Per-task model:** haiku = pure api-client one-liners / trivial column adds; sonnet (default) =
  standard screens/tabs/forms/reports; opus = the heavy flows (GED public e-sign ceremony, CONTRAT
  rental module, ATS pipeline, PaieRunWizard safety gates).
- **Fold + local test:** as each lane returns, review vs the STANDING RULES, fold onto the `dev`
  branch, run `npm run lint` + vitest + `npm run build` over the changed areas. Keep e2e green
  (selectors `ap-*/att-*/pp-*`, exactly one Toaster, header title not role=heading).

## STANDING RULES
- Wire to the EXISTING backend endpoint; never change a backend contract from here. If an item is
  actually BACKEND-INCOMPLETE (no viewset/URL — see the two flagged below), mark `[BLOCKED: needs backend]`
  and skip; those go to `docs/PLAN.md`, not here.
- No new frontend dependency without asking (regenerate the lock with `npx npm@10 install
  --package-lock-only` from main's lock if one is ever truly needed — Windows/npm-11 prunes Linux entries).
- Multi-tenant + permission gating: honour the same role/permission gates the backend enforces
  (e.g. `prix_achat_voir`/`salaires_voir` panels stay gated). Never expose `prix_achat`/margin in client output.
- French apostrophes break `.astro`/JS strings — mind escaping. Keep French UI labels consistent with STAGES.py.
- Branch each lane from `origin/claude/sad-euclid-b4` (the backends live there); after the backend
  merges land on `main`, rebase the frontend `dev` onto `main` before the single frontend merge.

## GATED / NOT HERE
- **XACC14 Emprunt** and **XACC19 EtatPersonnalise** — marked `[x]` but have NO Django viewset/URL at
  all (model+service only). BACKEND-INCOMPLETE → build the viewset/serializer/url in `docs/PLAN.md`
  first, then the frontend. Not a frontend-only task.
- **XRH33 careers public page** — deferred to `WEB_PLAN` (apps/web), not ERP frontend. (An in-app
  "publier" toggle IS in scope — see RH lane.)

---

# BUILD QUEUE

## Lane `frontend/flotte` (XFLT — all backend-only)
- [x] (déjà présent) FE-XFLT4 — "Cycle de vie" tab in `VehiculeDetail.jsx` (statut transitions + checklist gate); add `changerStatut`/`ceder` to `flotteApi.js`. (@lane: frontend/flotte)
- [x] (déjà présent) FE-XFLT1-3 — "Contrats" + "Grand livre des coûts" tabs in `VehiculeDetail.jsx`; add `contratsVehicule`/`couts`/`vehiculeLedger` to `flotteApi.js`. (@lane: frontend/flotte)
- [x] (déjà présent) FE-XFLT5 — "Signaler un problème" button + open-signalements list on cockpit/detail; add `signalements`(+`convertir_en_or`) to `flotteApi.js`. (@lane: frontend/flotte)
- [x] (déjà présent) FE-XFLT7/15/18 — "Analyse des coûts" tab + cockpit tiles; add `rapportCouts`/`rapportRemplacement`/`rapportBudget`/`budgets` to `flotteApi.js`. (@lane: frontend/flotte)
- [x] (déjà présent) FE-XFLT12/13 — model-select pre-fill on vehicle create + inspection checklist screen; add `modelesVehicule`/`modelesInspection`/`inspections` to `flotteApi.js`. (@lane: frontend/flotte)
- [x] (déjà présent) FE-XFLT14/19 — repair-order approval + `sous_garantie` warning in `EntretienScreen.jsx`; add `garanties`/`ordresReparation.approuver`. (@lane: frontend/flotte)
- [x] (déjà présent) FE-XFLT17 — état-des-lieux e-signature + charte acknowledgment; add `etatsDesLieux.signer`/`chartesVehicule`/`accusesCharte`. (@lane: frontend/flotte)
- [x] (déjà présent) FE-XFLT20 — accessory holders on `VehiculeDetail.jsx`; add `remisesAccessoire`/`detenteurs_courants`. (@lane: frontend/flotte)
- [x] (déjà présent) FE-XFLT22-23 — vehicle CSV import entry + fuel-receipt OCR pre-fill + bulk affectation/plan-entretien rollout; add `pleins.ocr`/`affectations.masse`/`plansEntretien.rollout`. (@lane: frontend/flotte)
- [x] (déjà présent) FE-XFLT24-25/28 — telematics zones/DTC (gated) + constructor recalls; add `zonesGeographiques`/`rappelsConstructeur`. (@lane: frontend/flotte)
- [x] (déjà présent) FE-XFLT26 — verify ICE/IF fields render in the garage form (`EntretienScreen.jsx`). (@lane: frontend/flotte)

## Lane `frontend/qhse` (XQHS — all backend-only; verify XQHS5/6/7/9/10/12 aren't ORPHAN backends first)
- [x] (déjà présent) FE-XQHS16 — public QR signalement: "Générer QR" action + `signalementsPublics`/`liensSignalement` in `qhseApi.js`. (@lane: frontend/qhse)
- [x] FE-XQHS17 — mobile quick-capture observation form; add `observationsSecurite`. (@lane: frontend/qhse)
- [x] (déjà présent) FE-XQHS2 — dérogations + NCR disposition fields in `NonConformites.jsx`; add `derogations`. (@lane: frontend/qhse)
- [x] (déjà présent) FE-XQHS3 — "Contrôle réception" screen/tab; add `plansControleReception`/`controlesReception`/`pointsControleReception`. (@lane: frontend/qhse)
- [x] (déjà présent) FE-XQHS4 — Pareto défauts chart on `QhseCockpit.jsx`; add `codesDefaut`/`paretoDefauts`. (@lane: frontend/qhse)
- [x] (déjà présent) FE-XQHS1 — CNSS declaration legal-step checklist; add `etapesDeclarationAt`. (@lane: frontend/qhse)
- [BLOCKED: needs backend] FE-XQHS5-13 — recalls/SCAR/5-why-8D/certifications/audit-program/revues/objectifs UIs; add the matching `qhseApi` resources (VERIFY each viewset exists — some may be ORPHAN → `[BLOCKED: needs backend]`). (@lane: frontend/qhse) — SCAR (`demandes-action-fournisseur`) déjà câblé dans `CheckinsSecurite.jsx` et XQHS7 (analyse 5-Pourquoi/8D) livré le 2026-08-13 ; le RESTE est ORPHELIN côté backend (aucun viewset ni URL pour `CampagneRappel`/`ElementRappel`, `Certification`/`AuditCertification`, `ProgrammeAudit`/`AuditPlanifie`, `ReunionQhse`/`DecisionReunion`, `ObjectifQhse`/`RevueObjectif`, ni pour `rendre_analyse_ncr_pdf`) → va dans `docs/PLAN.md`.
- [x] FE-XQHS14 — enterprise risk/opportunity + stakeholder register in `Risques.jsx`; add `risquesOpportunites`/`partiesInteressees`/`contexteOrganisation`. (@lane: frontend/qhse) — registre risques/opportunités SMQ livré ; `PartieInteressee`/`ContexteOrganisation` restent ORPHELINS (modèles sans viewset) → `docs/PLAN.md`.
- [x] FE-XQHS15/18/19 — procedure diffusion + acknowledgment, drill log, environmental-incident fields; add `diffusionsProcedure`/`accusesLecture`/`exercicesUrgence`. (@lane: frontend/qhse) — journal d'exercices déjà présent ; « Mes lectures en attente » + champs incident environnemental livrés ; la CRÉATION d'une diffusion reste ORPHELINE (`DiffusionProcedure` sans viewset) → `docs/PLAN.md`.
- [x] (déjà présent) FE-XQHS20-21 — environmental aspects register + monthly consumption entry → bilan carbone; add `aspectsEnvironnementaux`/`relevesConsommation`. (@lane: frontend/qhse)
- [x] (déjà présent) FE-XQHS22 — coût de non-qualité rollup (gated) in cockpit + NCR/CAPA/Incident cost fields; add `coutNonQualite`. (@lane: frontend/qhse)
- [x] FE-XQHS23-27 — NCR-from-SAV action, MOC screen, IA-assist buttons, veille réglementaire list, bilingual causerie PDF button; add matching `qhseApi` entries. (@lane: frontend/qhse) — MOC/IA/veille/causerie PDF déjà présents ; le pont ticket SAV → NCR livré le 2026-08-13.

## Lane `frontend/ged` (XGED/ZGED — incl. the flagship e-sign ceremony)
- [x] FE-XGED1 — **CRITICAL** public signing ceremony pages: React routes `/ged/signature/:token` + `/ged/signataire/:token` (no-auth) consuming the existing public endpoints. (@lane: frontend/ged) (opus) (déjà présent)
- [x] FE-XGED7 — public deposit page for `depot/<token>/`. (@lane: frontend/ged) (déjà présent)
- [x] FE-XGED2-3 — multi-signer sequencing + positioned signature fields in the "Nouvelle demande" dialog (`ApprobationPage.jsx`); add `signataires-demande`/`champs-signature`. (@lane: frontend/ged) (opus) (déjà présent)
- [x] FE-GED14/XGED16/XGED24 — document preview modal (click a row) + overlay annotations + redaction zones; add `apercu`/`annotations`/`caviarder`. (@lane: frontend/ged)
- [x] FE-GED26 — "Corbeille" screen (list/restore/purge); add `corbeille`/`mettre-en-corbeille`/`restaurer-corbeille`/`purger`. (@lane: frontend/ged) (déjà présent)
- [x] FE-GED16 — check-out/check-in lock buttons on document detail. (@lane: frontend/ged) (déjà présent)
- [x] FE-XGED14 — row checkboxes + bulk action toolbar in `GedNavigator.jsx` → `operations-lot`. (@lane: frontend/ged) (déjà présent)
- [x] FE-XGED15 — document detail drawer with timeline/chatter/@mentions; add `planifier`/`timeline`. (@lane: frontend/ged)
- [x] FE-XGED8/10/13/17 — folder checklist, split/merge UI, OCR validation queue, version-compare screen. (@lane: frontend/ged)
- [x] FE-XGED19-23 — rule-builder screens (folder auto-actions, approval routing, metadata ACL), effective-access panel, disposition-review gate. (@lane: frontend/ged) (déjà présent)
- [x] FE-XGED26-27/ZGED3 — analytics dashboard cards, bulk signature-request CSV upload, signature kanban. (@lane: frontend/ged)
- [x] FE-ZGED7-13 — favorites/recents sidebar + saved searches; add `mes-favoris`/`mes-recents`/`vues`. (@lane: frontend/ged)

## Lane `frontend/contrats` (CLM lifecycle actions all unwired)
- [x] FE-CONTRAT16-17 — **CRITICAL** "Signatures" tab + Signer button in `ContratDetail.jsx` (`getSignatures`/`signer` already in `contratsApi.js`). (@lane: frontend/contrats) (déjà présent)
- [x] FE-CONTRAT13-14 — "Approbation" tab: `lancerApprobation`/`approuverEtape`/`rejeterEtape` + étapes list. (@lane: frontend/contrats) (déjà présent)
- [x] FE-CONTRAT12 — wire `StateMachine.jsx`/actions bar to `getStatutsSuivants`+`changerStatut` (contract can't leave brouillon today). (@lane: frontend/contrats) (déjà présent)
- [x] FE-CONTRAT23-25 — Renouveler / Créer avenant / Résilier buttons in `ContratDetail.jsx`. (@lane: frontend/contrats) (déjà présent)
- [x] FE-CONTRAT7 — create-contract flow: wire `ModelesPage.jsx` row → `instancierModele` (no create path exists today). (@lane: frontend/contrats) (déjà présent)
- [x] FE-CONTRAT15 — note composer (`noter`) in the activity panel. (@lane: frontend/contrats) (déjà présent)
- [x] FE-CONTRAT33 — contracts dashboard (`getTableauBord`/`getReporting`, already in api client, uncalled). (@lane: frontend/contrats) (déjà présent)
- [x] FE-XCTR7-8-11 — MRR waterfall + retention cohorts heatmap + price-revision campaign screen; add `mrr-mouvements`/`cohortes-retention`/`campagne-revision`. (@lane: frontend/contrats) (déjà présent)
- [x] FE-XCTR5 — billing-exceptions card (`cycles-facturation`/`rejouer`). (@lane: frontend/contrats) (déjà présent)
- [x] FE-XCTR17-21 — **CRITICAL** outbound equipment-**rental** module: new `/contrats/location` page wired to `OrdreLocationViewSet` (reservation calendar, caution encaisser/restituer/retenir, inspection, ROI, bons PDF). (@lane: frontend/contrats) (opus)
- [x] FE-XCTR14 — client portal "Mes contrats" + renew/terminate request buttons (`portail/<token>/` in `ClientPortalPage.jsx`). (@lane: frontend/contrats) (déjà présent)
- [x] FE-XCTR2-3 — "Équipements couverts" panel + "X/Y visites consommées" on `ContratsMaintenance.jsx`. (@lane: frontend/contrats)
- [x] FE-CONTRAT-config — PlanRecurrent / MotifResiliation / ParametresLocation CRUD screens. (@lane: frontend/contrats) (déjà présent)

## Lane `frontend/gestion_projet` (XPRJ/ZPRJ round-2 backend-only)
- [x] FE-XPRJ4 — "Situations" tab (BTP progress billing) in `ProjetDetailPage.jsx`; add `situations`/`lignes-situation`. (@lane: frontend/gestion_projet) (déjà présent)
- [x] FE-XPRJ5 — task chrono start/stop buttons + active indicator (`demarrer-chrono`/`arreter-chrono`). (@lane: frontend/gestion_projet) (déjà présent)
- [x] FE-XPRJ7-8/ZPRJ5-6 — timesheet approval workflow + manquants/heures-attendues/classement/rapprochement/rapport in `RessourcesPage.jsx`. (@lane: frontend/gestion_projet)
- [x] FE-XPRJ10-12 — Tâches CRUD screen (filters assigné/priorité/statut) + kanban + "Mes tâches" page/route. (@lane: frontend/gestion_projet) (déjà présent)
- [x] FE-PROJ11 — drag-to-reschedule in `GanttChart.jsx` (`reprogrammer`). (@lane: frontend/gestion_projet) (déjà présent)
- [x] FE-XPRJ14-17 — checklist toggle, RAG/point-avancement, ETC/EAC in `BudgetPage.jsx`, burndown chart. (@lane: frontend/gestion_projet) (déjà présent)
- [x] FE-ZPRJ1-4 — réglages temps + publier/copier-semaine/auto-affecter buttons in `PlanningPage.jsx`. (@lane: frontend/gestion_projet) (déjà présent, écran = `RessourcesPage.jsx`)
- [x] FE-ZPRJ7-9/ZPRJ8 — CSAT evaluation link, status-report PDF button, risk heatmap in `RisquesPage.jsx`. (@lane: frontend/gestion_projet) (déjà présent)
- [x] FE-XPRJ21/29/27 — "Créer projet depuis devis" button on devis list, AI plan propose→confirm, marché-public fields + pénalités. (@lane: frontend/gestion_projet) (déjà présent)

## Lane `frontend/paie` (XPAI/ZPAI/YHIRE round-2 backend-only)
- [x] FE-XPAI1-2 — **CRITICAL** Solde de tout compte (STC) action/screen from the sortie flow; add `stc`/`stcPdf`. (@lane: frontend/paie) (déjà présent)
- [x] FE-YHIRE3/XPAI15/ZPAI2 — **CRITICAL** pre-run warnings panel (`controle-completude`/`controle-ecarts`/`avertissements`) at top of `PaieRunWizard.jsx` (safety gate silently skipped today). (@lane: frontend/paie) (déjà présent)
- [x] FE-XPAI3 — "Mutuelle" tab in `PaieParametres.jsx`; add `regimes-mutuelle`/`adhesions-mutuelle`. (@lane: frontend/paie) (déjà présent)
- [x] FE-XPAI4 — "Run hors-cycle / 13e mois" button (`run-gratification`). (@lane: frontend/paie) (déjà présent)
- [x] FE-XPAI5/11-13/26 — new PaieDeclarations tabs: état des charges, rapprochement GL/AFFEBDS, BDS complémentaire, XML SIMPL-IR, registre congés, historique carrière. (@lane: frontend/paie) (déjà présent)
- [x] FE-XPAI8-9 — virement format selector (CSV/SIMT) + ligne-virement reject/reissue. (@lane: frontend/paie) (déjà présent)
- [x] FE-XPAI16/18 — net↔brut simulator tab + exemption-regime fields on profile form. (@lane: frontend/paie) (déjà présent)
- [x] FE-XPAI22 — cumuls go-live import wizard (`reprise-dry-run`/`reprise-commit`). (@lane: frontend/paie) (déjà présent)
- [x] FE-ZPAI1/3 — paie analyse pivot (rubrique×mois×dept) + coût employeur report. (@lane: frontend/paie) (déjà présent)
- [x] FE-ZPAI4-7 — cancel bulletin, batch-print bulletins, saisie-arret annuler/creer-lot. (@lane: frontend/paie) (déjà présent)

## Lane `frontend/rh` (XRH/ZRH round-2 backend-only — 33 orphaned viewsets)
- [x] (déjà présent) FE-XRH17-23/ZRH7-9 — **CRITICAL** full ATS in `Recrutement.jsx`: interviews (`entretiens-recrutement`), email templates, offer letters (`promesses-embauche`), talent pool (`vivier`), analytics, CV parsing (`parser-cv`), evaluation templates + 360 feedback. (@lane: frontend/rh) (opus)
- [x] (déjà présent) FE-YHIRE2/ZRH12 — **CRITICAL** offboarding: `sortir` action button/modal + `comptes-actifs-sortis` security report + `certificat-travail` PDF in `EmployeDetail.jsx`. (@lane: frontend/rh)
- [x] (déjà présent) FE-XRH1/4-6 — onboarding checklist + essai/CNSS-entry widgets + chatter timeline tab in `EmployeDetail.jsx`. (@lane: frontend/rh)
- [x] FE-XRH9/28/ZRH13 — self-service portal: "Mes demandes"/attestation, directory (`annuaire`), allocations in `Portail.jsx`. (@lane: frontend/rh)
- [x] (déjà présent) FE-XRH28b — wire the already-written dead `getMesEpi`/`getMesHabilitations` into "Mes EPI"/"Mes habilitations" Portail tabs. (@lane: frontend/rh)
- [x] (déjà présent) FE-XRH34/XRH26/XRH32 — quiz-taking flow + auto-évaluation + eNPS pulse in `Portail.jsx`; quiz builder in `Competences.jsx`. (@lane: frontend/rh)
- [x] (déjà présent) FE-XRH10/13 — kiosk fullscreen page (device-token) + device-token admin + CSV pointeuse import in `Temps.jsx`. (@lane: frontend/rh)
- [x] FE-XRH11-12 — pointage correction history + geofence flag in `Temps.jsx`. (@lane: frontend/rh)
- [x] FE-XRH15-16/ZRH10 — competence gap-analysis/evolution + salary-band compa-ratio (gated) + internal candidates. (@lane: frontend/rh)
- [x] FE-XRH29/27/31 — dependents/benefits tab, org-tree, attrition-risk widget. (@lane: frontend/rh)
- [x] FE-ZRH3-6/11/18 — congé/absence/turnover/présence reports in `Conges.jsx`/`RhCockpit.jsx`/`Temps.jsx`; jours-bloqués mgmt. (@lane: frontend/rh)
- [x] FE-ZRH14-17 — reconnaissance badges, career timeline, weekly location, skills search on `EmployeDetail.jsx`. (@lane: frontend/rh)

## Lane `frontend/sav` (XSAV/XCTR/ZSAV/ZMFG round-2 backend-only)
- [x] (déjà présent) FE-XSAV19/XSAV10 — **CRITICAL** public pages: QR problem-report `/e/:token` + ticket-tracking + CSAT `/suivi/:token` (both are JSON dead-ends today). (@lane: frontend/sav) (opus)
- [x] (déjà présent) FE-XSAV3/XFSM1/XCTR4 — "Créer un devis"/"Générer facture"/"Facturer" buttons on ticket detail (`creer-devis`/`generer-facture`/`facturer` + `couverture`). (@lane: frontend/sav)
- [x] (déjà présent) FE-SAV-warranty — supplier-RMA screen (`warranty-claims`, FG83). (@lane: frontend/sav)
- [x] (déjà présent) FE-XSAV15-17/XSAV9 — MTBF/MTTR/downtime/disponibilité/meter-readings + write-off buttons on `EquipementDetail`. (@lane: frontend/sav)
- [x] (déjà présent) FE-XSAV8 — SLA compliance report screen (`insights/sav-sla/`). (@lane: frontend/sav)
- [x] (déjà présent) FE-XSAV12/27/ZSAV8-9 — merge duplicate ticket, loaner tracking, ticket→lead, follow/unfollow. (@lane: frontend/sav)
- [x] (déjà présent) FE-ZSAV2-3-6 — ticket categories filter + Paramètres CRUD, scheduled activities panel, "Action requise" board. (@lane: frontend/sav)
- [x] (déjà présent) FE-SAV-kb/macros — KB article screen + "Résolutions similaires"/macro-picker on ticket (`kb-articles`/`reponses-type`/`pieces-compatibles`). (@lane: frontend/sav)
- [x] (déjà présent) FE-SAV-alarmes — inverter-alarms panel (list/acquitter/escalader, FG280). (@lane: frontend/sav)
- [x] (déjà présent) FE-XSAV14/ZMFG6/11 — cause/remède + Pareto pannes, worksheet UI, predicted-failure estimations. (@lane: frontend/sav)

## Lane `frontend/litiges`
- [x] (déjà présent) FE-LITIGE4 — render `rec.ncr`/`rec.audit` (NCR/Audit linked) in `ReclamationDetail.jsx` + linking control in `ReclamationEditor.jsx` (data already fetched). (@lane: frontend/litiges)

## Lane `frontend/compta` (XACC/ZACC round-2 — <half of accounting reachable)
- [x] FE-FG122/126/132 — wire the already-written uncalled `positionTresorerie`/`previsionnelTresorerie`/`balanceAgeeFournisseurs` (cheapest wins) into `TresoreriePage.jsx`/`EtatsPage.jsx`. (déjà présent) (@lane: frontend/compta)
- [x] FE-ZACC1-2 — "Export PDF" + "Comparer N-1" controls on `EtatsPage.jsx` (backend accepts `?export=pdf`/`?comparer=1`). (déjà présent) (@lane: frontend/compta)
- [x] FE-ZACC3-4/12/16 — add tableau-flux, journal-items, tableau-immobilisations, dossier-de-clôture to the `ETATS` array + buttons. (déjà présent) (@lane: frontend/compta)
- [x] FE-XACC9 — "Échéances fiscales" tab in `FiscalitePage.jsx` (`obligations-fiscales`). (déjà présent) (@lane: frontend/compta)
- [x] FE-notes-frais — compta.NoteFrais validation/comptable screen (distinct from RH self-service): `notes-frais`/`rapports`/`plafonds`/`baremes-indemnite`/`indemnites-chantier` + soumettre/valider/rejeter/rembourser/recu-pdf. (déjà présent) (@lane: frontend/compta)
- [x] FE-effets — "Effets à recevoir/payer" page + bordereaux + escompte/endossement actions. (@lane: frontend/compta)
- [x] FE-payment-runs — PaymentRun screen + `fichier-virement` bank export (FG133-134). (déjà présent) (@lane: frontend/compta)
- [x] FE-FG145 — RetenueGarantie + CautionBancaire tabs (+ attestation-annuelle). (déjà présent) (@lane: frontend/compta)
- [x] FE-FG146-148 — revenue-recognition/WIP (ContratAvancement/TravauxEnCours) + CommissionPayoutRun screens. (déjà présent) (@lane: frontend/compta)
- [x] FE-XFAC14/XACC26 — AR/AP netting (compensations) + Provision/ModeleRapprochement/BalanceOuverture read+action screens. (déjà présent) (@lane: frontend/compta)
- [x] FE-COMPTA39 — read-only audit-trail viewer (`pistes-audit`, admin-only). (déjà présent) (@lane: frontend/compta)
- [x] FE-rapprochement-detail — bank-reconciliation drill-down dialog (`lignes-gl`/`pointer`/`suggestions`/`ocr-import`) in `RapprochementsPage.jsx`. (@lane: frontend/compta)
- [x] FE-immo-caisse-actions — Immobilisations `ceder`/`poster` row actions + Caisse mouvement/clôture drawer + Virement `poster`. (@lane: frontend/compta)
- [x] FE-ZACC14/XACC29 — contrôle ICE/IF + continuité des séquences as `ETATS` entries. (déjà présent) (@lane: frontend/compta)

## Lane `frontend/stock` (ZPUR/ZSTK round-2 backend-only)
- [x] (déjà présent) FE-XPUR25 — **BLOCKED: needs backend** (`fournisseurs/{id}/vue-360/` action never built) then route the orphan `pages/stock/FournisseurFiche360.jsx` (add lazy route + nav + row link). (@lane: frontend/stock) — **repris par WIR27** (`docs/PLAN.md`, `[x]` livré : `vue-360` action + route/nav construits — WIR79 vérifié 2026-07-18, ne pas rebuilder ici).
- [x] (déjà présent) FE-ZPUR1/4/6/11 — BCF actions: `facturer`, `dupliquer`, `fusionner` (multi-select), `rouvrir` + motif-required `annuler` on `BonsCommandeFournisseur.jsx`; add to `stockApi.js`. (@lane: frontend/stock)
- [x] (déjà présent) FE-ZPUR3/8 — Modèles BCF screen (`modeles-bcf`/`generer`) + BCF header fields (acheteur/ref_fournisseur/note_bas_page/incoterm). (@lane: frontend/stock)
- [x] (déjà présent) FE-ZPUR10/ZSTK3 — product-detail screen with "en commande" qty + `previsionnel` forecast tab. (@lane: frontend/stock)
- [x] (déjà présent) FE-ZSTK7 — "Vue groupée / pivot" toggle on `MouvementsPage.jsx` (`mouvements/agregation`). (@lane: frontend/stock)
- [x] (déjà présent) FE-ZSTK6/12 — lot/série label printing on reception + barcode-nomenclature CRUD (Paramètres). (@lane: frontend/stock)
- [x] (déjà présent) FE-ZPUR9 — purchase-analysis PDF button next to the XPUR24 xlsx export. (@lane: frontend/stock)

## Lane `frontend/installations` (XMFG kitting/atelier — whole subsystem backend-only)
- [x] FE-XMFG1-16 — **atelier/kitting UI**: new `pages/installations/AteliersPage.jsx` (OrdreAssemblage/OrdreDemontage list/detail/close, backflush, reservations, QC gate, bon-pdf) + route/nav; add `ordres-assemblage`/`kits-produit/{id}/structure`/`ordres-demontage` to `installationsApi.js`. (déjà présent) (@lane: frontend/installations) (opus)

## Lane `frontend/compta` (additional round-2 orphans — fold into the compta lane above)
- [x] FE-XACC33 — "Immobiliser" button on `pages/stock/FacturesFournisseur.jsx` (`immobilisations/depuis-facture-fournisseur`). (déjà présent) (@lane: frontend/compta)
- [x] FE-XACC3-4 — bank-recon "Suggestions" panel + "Modèles rapprochement" CRUD in `RapprochementsPage.jsx`. (déjà présent) (@lane: frontend/compta)
- [x] FE-COMPTA21 — consume the uncalled `balanceAgeeFournisseurs` + add `releveFournisseur` drill-down. (@lane: frontend/compta)

## SAV lane additions (fold into `frontend/sav`)
- [x] (déjà présent) FE-XSAV5/21/28 — attente-client SLA pause/resume, similar-ticket panel, AI triage banner on `TicketsPage.jsx`. (@lane: frontend/sav)
- [x] (déjà présent) FE-ZMFG1-2/4/5-12 — SAV teams + equipment categories (Paramètres + ticket/equipment filters), instructions tab, worksheet form, unified pièces, scrap action, estimations, bon-pdf. (@lane: frontend/sav)

## Lane `frontend/kb` (XKB8-22 + ZGED10-12 backend-only; XKB23 already wired)
- [x] (déjà présent) FE-XKB19 — **CRITICAL** public unauthenticated article route `/kb/public/:token` + `PublicArticlePage.jsx` + "Share on web" action (`partages`/`depublier`). (@lane: frontend/kb) (opus)
- [x] (déjà présent) FE-XKB8/21 — article tree sidebar (`arbre`, drag-reorder parent/ordre) + move/duplicate row actions. (@lane: frontend/kb)
- [x] (déjà présent) FE-XKB9/13/14 — visibility+ACL selector, `<ChatterWidget model="kb.kbarticle">` comments, verified badge + lock (`verifier`/`verrouiller`), stale-content report. (@lane: frontend/kb)
- [x] (déjà présent) FE-XKB10/18 — markdown render + attachments + `sommaire` TOC; language switcher + RTL + `traduire`. (@lane: frontend/kb)
- [x] (déjà présent) FE-XKB11/12/17 — backlinks panel, templates gallery (`gabarits`/`depuis-gabarit`), export PDF/MD + import MD + ZIP. (@lane: frontend/kb)
- [x] (déjà présent) FE-XKB15/16/22 — favorites/recents, KB stats reports, onboarding "Parcours" screen (`KbParcours` assign+progression). (@lane: frontend/kb)
- [x] (déjà présent) FE-ZGED10-12 — emoji + cover image, custom properties + kanban/cards/list/calendar item views, reusable-block insert picker. (@lane: frontend/kb)

## Lane `frontend/pos` (entire apps/pos backend orphaned — FE built against ventes.Facture)
- [x] (déjà présent) FE-XPOS1-18 — **CRITICAL** rewrite `posApi.js` to call `/pos/ventes|sessions|retraits|config-materiel/`; add routes `/pos/session` (ouverture/clôture + rapport-z, XPOS4), `/pos/dashboard` (XPOS11), `/pos/retraits` (click-and-collect, XPOS15); wire ticket-escpos/share-link + serial capture (XPOS9) into `CaisseScreen.jsx`. (@lane: frontend/pos) (opus)

## Lane `frontend/ventes` (XSAL/ZSAL round-2 — mostly cheap NOT_WIRED stubs)
- [BLOCKED: needs backend] FE-XSAL6 — `PlanCommission` has no viewset/URL + not consumed by reporting/insights.py; a "Plans de commission" screen under parametres cannot be wired until the backend exposes it. (@lane: frontend/ventes)
- [x] (déjà présent) FE-XSAL1-3 — price-list admin CRUD (`ListesPrixPage.jsx`, routed) + `liste_prix` field on `ClientForm.jsx` + `getPrixApplicable` called from `DevisGenerator.jsx` (XSAL3 "Tarif" badge already wired). (@lane: frontend/ventes)
- [x] (déjà présent) FE-XSAL12 — partial-delivery dialog + reliquat column already in `BonCommandeList.jsx` (`LivraisonPartielleDialog`, `livrer-partiel`); no `VentesKanban.jsx` exists, this is the real implementation location. (@lane: frontend/ventes)
- [x] FE-ZSAL8/XSAL16 — engagement summary already present (`engagementSummary()` in `DevisList.jsx`); added the missing BC PDF menu item (`handleBonCommandePdf` wired to the orphaned `ventesApi.getBonCommandePdf`) shown when `d.bon_commande_etat.exists`. (@lane: frontend/ventes)
- [x] (déjà présent) FE-ZSAL5 — keyed email-template editor (`envoi_devis`) already in `EmailSection.jsx` (ZSAL5 tag), backend model/migration + `envoi_devis` key confirmed. (@lane: frontend/ventes)

## Lane `frontend/crm` (ZSAL round-2 — api client stubs defined, never called)
- [x] (déjà présent) FE-ZSAL2 — "Appliquer un plan" button + plan picker on lead detail + PlanActivite CRUD (`getPlansActivite`/`appliquerPlanActivite` already in `crmApi.js`). (@lane: frontend/crm)
- [x] (déjà présent) FE-ZSAL4 — "Convertir en client" button + modal on lead detail (`convertirClient`). (@lane: frontend/crm)
- [x] (déjà présent) FE-ZSAL3/ZSAL6 — "Mes équipes" dashboard cards + EquipeCommerciale CRUD + "Attribution des leads" section in `Rapports.jsx`. (@lane: frontend/crm)
- [x] (déjà présent) FE-ZSAL1/XSAL17 — suggested follow-up activity prompt in `MesActivitesPage.jsx` + `{lien_rdv}` placeholder in template editor. (@lane: frontend/crm)

## Lane `frontend/reporting` (systemic offender — many [x] reports backend-only)
- [x] (déjà présent) FE-XPLT6 — "Alertes KPI" CRUD under parametres (`reporting/kpi-alertes/`). (@lane: frontend/reporting)
- [x] (déjà présent) FE-XPLT10 — dashboard share/revoke UI + `/dashboards-tv` public kiosk route (`core/dashboards-partages`). (@lane: frontend/reporting)
- [x] (déjà présent) FE-XPLT22 — `ClasseurPage.jsx` (live-data spreadsheet) + `reportingApi.js` client. (@lane: frontend/reporting)
- [x] (déjà présent) FE-XPLT9 — mount the already-built-but-unused `DashboardFilterBar.jsx` in `DashboardConfigPage.jsx`. (@lane: frontend/reporting)
- [ ] FE-XPLT11 — **BLOCKED: needs pivot/BI-explorer screen (FG382, itself unbuilt frontend)** then expose the formula measure. (@lane: frontend/reporting)
- [x] (déjà présent) FE-XSAV8/XFSM16-17 — SAV SLA report + field-service analytics + technician scorecard pages under `pages/reporting/`. (@lane: frontend/reporting)

## Lane `frontend/platform` (agent / dataimport / audit / privacy)
- [x] FE-XPLT18 — propose→confirm "Générer une règle" UI in `AutomatisationsSection.jsx` (`agent/actions/automation-draft`). (@lane: frontend/platform) (déjà présent)
- [x] FE-XPLT1-2 — import upsert mode + saved-mapping picker + error-CSV link in `ExcelImport.jsx` (`importApi.js` mode/external_id/saveMapping/jobErreursCsv). (@lane: frontend/platform) (déjà présent)
- [x] FE-XPLT23 — "Confidentialité" tab under parametres: CNDP `registre-traitements` CRUD + `dsr-requests` (DSR) submission/tracking. (@lane: frontend/platform) (déjà présent)
- [x] FE-YHARD3 — "Historique à cette date" (as-of) view on record detail / `Journal.jsx` (admin/Directeur). (@lane: frontend/platform) (déjà présent)
- [ ] FE-SCA41 — Exports ventes : gérer la réponse 202 des exports xlsx volumineux (journal-ventes / export-comptable) : afficher « génération en arrière-plan », poller GET /api/django/ventes/export/status/<job_id>/ (payload {status, download_url, filename}) puis déclencher le téléchargement via download_url (URL pré-signée 1 h). Sous le seuil (2 000 lignes, env), rien ne change.
- [ ] FE-XPLT18 — propose→confirm "Générer une règle" UI in `AutomatisationsSection.jsx` (`agent/actions/automation-draft`). (@lane: frontend/platform)
- [ ] FE-XPLT1-2 — import upsert mode + saved-mapping picker + error-CSV link in `ExcelImport.jsx` (`importApi.js` mode/external_id/saveMapping/jobErreursCsv). (@lane: frontend/platform)
- [ ] FE-XPLT23 — "Confidentialité" tab under parametres: CNDP `registre-traitements` CRUD + `dsr-requests` (DSR) submission/tracking. (@lane: frontend/platform)
- [ ] FE-YHARD3 — "Historique à cette date" (as-of) view on record detail / `Journal.jsx` (admin/Directeur). (@lane: frontend/platform)
- [x] FE-SCA41 — Exports ventes : gérer la réponse 202 des exports xlsx volumineux (journal-ventes / export-comptable) : afficher « génération en arrière-plan », poller GET /api/django/ventes/export/status/<job_id>/ (payload {status, download_url, filename}) puis déclencher le téléchargement via download_url (URL pré-signée 1 h). Sous le seuil (2 000 lignes, env), rien ne change.

## AUDIT COMPLETE (2026-07-06)
- Domains CLEAN (fully wired, no gaps): **litiges, monitoring, publicapi, audit** baseline screens.
- Legitimately backend-only (no UI ever promised): YAPIC7-10, YHARD1 (versioning/webhooks/idempotency/encryption).
- `ODX5` (Applications catalogue) still `[ ]` in PLAN.md — normal backlog, not a gap.

## DONE LOG
<!-- one dated line per shipped task -->
- 2026-08-13 (lane frontend/crm) — les 4 tâches taguées `@lane: frontend/crm` étaient DÉJÀ construites
  et câblées : FE-ZSAL2 (`PlanActiviteDialog.jsx` ouvert depuis `LeadWorkspace.jsx`, appelle
  `crmApi.getPlansActivite`/`appliquerPlanActivite`), FE-ZSAL4 (`ConvertirClientDialog.jsx` +
  bouton « Convertir en client » dans `IdentityRail.jsx`, appelle `crmApi.convertirClient`),
  FE-ZSAL3/ZSAL6 (`MesEquipesCard.jsx` sur `Dashboard.jsx` + CRUD `EquipesCommercialesSection.jsx`
  sous Paramètres + section « Attribution des leads » dans `Rapports.jsx`, lignes ~700-710),
  FE-ZSAL1/XSAL17 (prompt de suivi suggéré dans `MesActivitesPage.jsx` lignes 155-385 + placeholder
  `{lien_rdv}` documenté dans `MessageTemplatesCrmSection.jsx` et résolu côté serveur via
  `PublicBookingPage.jsx`). Aucun code écrit, pas de commit de fonctionnalité (seule mise à jour de
  ce fichier).
- 2026-08-13 (lane frontend/reporting) — les 5 tâches actionnables taguées `@lane: frontend/reporting` étaient DÉJÀ construites et câblées bout-en-bout (endpoint backend + client `reportingApi.js`/`coreApi.js` + page + route `module.config.jsx` + entrée de nav) : FE-XPLT6 (`KpiAlertesPage.jsx` sous `/parametres/alertes-kpi`), FE-XPLT10 (`DashboardSharePage.jsx` + `DashboardsTvPage.jsx` sous `/dashboards-tv`), FE-XPLT22 (`ClasseursListPage.jsx`/`ClasseurPage.jsx` sous `/reporting/classeurs`), FE-XPLT9 (`DashboardFilterBar` déjà montée dans `DashboardConfigPage.jsx`), FE-XSAV8/XFSM16-17 (`SavSlaPage.jsx`/`FieldServiceReportPage.jsx`/`TechnicienScorecardPage.jsx`). Aucun code écrit, seule mise à jour de ce fichier. FE-XPLT11 reste `[BLOCKED]` (dépendance FG382 non construite), inchangé.
- 2026-08-13 (lane frontend/litiges) — FE-LITIGE4 déjà entièrement construite : `ReclamationDetail.jsx` a un onglet « NCR / Audit lié » rendant `rec.ncr`/`rec.audit` (états vides gérés) ; `ReclamationEditor.jsx` expose les champs `ncr_id`/`audit_id` postés à l'enregistrement ; couverte par `litiges.test.jsx` (8 tests verts). Aucun code écrit, seule mise à jour de ce fichier. Gates : eslint vert, vitest 8/8 vert.
- 2026-08-13 — Lane `frontend/platform` drainée (aucun code écrit, seule mise à jour de ce
  fichier). Les 4 tâches taguées `@lane: frontend/platform` étaient DÉJÀ construites et câblées :
  FE-XPLT18 (propose→confirm "Générer une règle (IA)" dans `AutomatisationsSection.jsx`, appelle
  `automationApi.proposeDraft` → `agent/actions/automation-draft/`, règle toujours créée désactivée) ;
  FE-XPLT1-2 (mode d'import creer/maj/upsert + sélecteur de mapping sauvegardé + téléchargement du
  CSV des lignes en échec dans `ExcelImport.jsx`/`importApi.js`) ; FE-XPLT23 (onglet Confidentialité
  `ConfidentialiteSection.jsx` : registre CNDP CRUD+export CSV, demandes DSR soumission/traitement,
  plus registre de consentement et benchmarking déjà présents en bonus) ; FE-YHARD3 (dialog
  "Historique à cette date" dans `Journal.jsx`, `auditApi.getObjectAsOf` reconstruit champ par
  champ). Gates vérifiés : eslint propre sur les 5 fichiers, `vitest run` 4/4 fichiers de test
  (15 tests) verts, `vite build` vert.
- 2026-08-13 (lane frontend/pos) — FE-XPOS1-18 était DÉJÀ entièrement construite et câblée : `posApi.js` appelle `/pos/ventes|sessions|retraits|config-materiel/` (aucun résidu `ventes.Facture`) ; `module.config.jsx` monte `/pos`, `/pos/session`, `/pos/dashboard`, `/pos/retraits`, `/pos/config-materiel` ; `CaisseScreen.jsx` câble ticket-PDF, ticket-ESC/POS, lien partageable et capture des numéros de série (XPOS9) sur la vente validée. Vérifié : `npx eslint`, `npx vitest run src/features/pos` (6 fichiers, 30 tests verts) et `npx vite build` tous verts. Aucun code écrit, seule mise à jour de ce fichier.
- 2026-08-13 — Lane `frontend/installations` drainée (FE-XMFG1-16, tâche unique). Déjà entièrement construite et câblée : `pages/installations/AteliersPage.jsx` (liste/détail assemblage+démontage, démarrer/terminer/annuler, backflush quantité produite, disponibilité par composant, gate qualité QC bloquant la clôture, chatter noter/historique, bon PDF), `installationsApi.js` (`getOrdresAssemblage`/`getOrdreAssemblage`/`create...`/`update...`/`delete...`, `getDisponibiliteAssemblage`, `demarrerAssemblage`/`terminerAssemblage`/`annulerAssemblage`, `getHistoriqueAssemblage`/`noterAssemblage`, `getControleQualiteAssemblage`/`enregistrerControleQualiteAssemblage`, `getEtapesAssemblage`, `bonAssemblageUrl`, lignes assemblage/démontage, `getOrdresDemontage`/`terminerDemontage`, `getKitsAssemblage`), route `/atelier` + nav « Atelier » dans `features/installations/module.config.jsx`, endpoints backend `kits`/`ordres-assemblage`/`ordres-demontage` dans `apps/installations/urls.py`. Aucun export API orphelin ni vocabulaire désynchronisé trouvé. Aucun code écrit — cochée `(déjà présent)`. Gates : `eslint` vert, `vitest run AteliersPage.test.jsx` vert (3/3), `vite build` vert.
- 2026-08-13 (lane frontend/ventes) — FE-XSAL1-3 et FE-XSAL12 vérifiées déjà entièrement construites
  (`ListesPrixPage.jsx` routé + badge « Tarif » dans `DevisGenerator.jsx` ; dialogue
  `LivraisonPartielleDialog` + colonne Reliquat déjà dans `BonCommandeList.jsx` — `VentesKanban.jsx`
  n'existe pas, c'est le vrai emplacement de la fonctionnalité). Aucun code écrit. FE-XSAL6 confirmée
  bloquée (`PlanCommission` sans viewset/URL côté backend) — marquée `[BLOCKED: needs backend]`.
- 2026-08-13 (lane frontend/ventes) — FE-ZSAL8/XSAL16 : le résumé d'engagement (`engagementSummary()`)
  était déjà présent dans `DevisList.jsx`. Écart réel trouvé et corrigé : `ventesApi.getBonCommandePdf`
  était un export API orphelin (endpoint backend `GET .../bons-commande/<id>/pdf/` complet, jamais
  appelé côté client) — ajouté un item de menu « Bon de commande (PDF) » sur `DevisList.jsx` (visible
  quand `bon_commande_etat.exists`) qui l'appelle, avec test source `DevisListBcPdf.test.mjs`.
- 2026-08-13 (lane frontend/ventes) — FE-ZSAL5 vérifiée déjà entièrement construite (éditeur de
  modèles d'e-mail par clé dans `EmailSection.jsx`, clé `envoi_devis` confirmée côté backend
  modèle+migration). Aucun code écrit. Lane `frontend/ventes` drainée entièrement (5 tâches : 3
  déjà présentes, 1 bloquée backend, 1 écart réel corrigé).
- 2026-08-13 — lane `frontend/contrats` drained: FE-CONTRAT16-17/13-14/12/23-25/7/15/33, FE-XCTR7-8-11, FE-XCTR5, FE-XCTR14, FE-CONTRAT-config already fully built (ContratDetail.jsx tabs+actions, ModelesPage.jsx instancier, DashboardPage.jsx, PortailContratsPage.jsx, ConfigLocationPage.jsx) — ticked `(déjà présent)`, no code change. FE-XCTR2-3: added "Équipements couverts" + "X/Y visites" columns to `ContratsMaintenance.jsx` (data was already serialized server-side, just unrendered). FE-XCTR17-21: `LocationPage.jsx` had caution/inspection/bons PDF already; added the missing disponibilité (reservation-window) warning in the create dialog and an admin-only "Utilisation & ROI" card, both using contratsApi calls that existed but were never invoked from the UI.
- 2026-08-13 (lane frontend/sav) — les 12 tâches taguées `@lane: frontend/sav` étaient DÉJÀ construites et câblées (savApi.js + pages/sav/*.jsx + router public /e/:token /suivi/:token) : FE-XSAV19/XSAV10, FE-XSAV3/XFSM1/XCTR4, FE-SAV-warranty, FE-XSAV15-17/XSAV9, FE-XSAV8, FE-XSAV12/27/ZSAV8-9, FE-ZSAV2-3-6, FE-SAV-kb/macros, FE-SAV-alarmes, FE-XSAV14/ZMFG6/11, FE-XSAV5/21/28, FE-ZMFG1-2/4/5-12. Aucun code écrit, pas de commit de fonctionnalité (seule mise à jour de ce fichier).
- 2026-08-13 — Lane `frontend/compta` drainée (agent-acf554ffb8d774ac6). Vérifiées déjà construites
  (aucun code requis) : FE-FG122/126/132, FE-ZACC1-2, FE-ZACC3-4/12/16, FE-XACC9, FE-notes-frais,
  FE-payment-runs, FE-FG145, FE-FG146-148, FE-XFAC14/XACC26, FE-COMPTA39, FE-ZACC14/XACC29,
  FE-XACC33, FE-XACC3-4 — toutes déjà entièrement câblées (TresoreriePage/EtatsPage/FiscalitePage/
  NotesDeFraisPage/EffetsPage/EngagementsPage/RapprochementsPage/FacturesFournisseur.jsx). Réels
  écarts trouvés et construits : FE-effets (escompte/endossement affichaient un message au lieu
  d'appeler le backend — actions réelles ajoutées + « Apurer l'escompte »), FE-immo-caisse-actions
  (action « Poster » manquante sur les virements internes — `comptaApi.virements.poster` +
  TresoreriePage), FE-rapprochement-detail (action `ocr-import` du backend jamais exposée —
  panneau d'import OCR ajouté à RapprochementDetailDialog), FE-COMPTA21 (`releveFournisseur`
  jamais appelé — drill-down « Relevé » ajouté sur l'état balance âgée fournisseurs d'EtatsPage).
  eslint + `npx vite build` verts sur tous les fichiers touchés ; suites vitest compta existantes
  toutes vertes (aucune régression).
- 2026-08-13 — Lane `frontend/flotte` (FE-XFLT4, FE-XFLT1-3, FE-XFLT5, FE-XFLT7/15/18, FE-XFLT12/13, FE-XFLT14/19, FE-XFLT17, FE-XFLT20, FE-XFLT22-23, FE-XFLT24-25/28, FE-XFLT26): verified all 11 tasks already wired end-to-end (flotteApi.js entries, VehiculeDetail.jsx tabs, EntretienScreen.jsx/AnalyseCoutsScreen.jsx/InspectionsScreen.jsx/ZonesRappelsScreen.jsx screens all registered in module.config.jsx) — no code changes needed; 14/14 vitest files (56 tests) pass.
- 2026-08-13 — FE-XQHS17 : formulaire de capture rapide d'observation BBS (dialogue mobile-friendly, date du jour par défaut) sur l'onglet « Observations BBS » de `Risques.jsx` ; le registre était en lecture + conversion seulement.
- 2026-08-13 — FE-XQHS14 : registre « Risques & opportunités (SMQ) » (ISO 6.1) — nouvel onglet de `Risques.jsx`, bascule « Revues dues », création sans jamais poster de criticité (calcul serveur) ; `risquesOpportunites` ajouté à `qhseApi.js`.
- 2026-08-13 — FE-XQHS15/18/19 : panneau « Mes lectures en attente » (accusés de lecture des procédures) dans `Inspections.jsx` ; champs environnement (substance/quantité/unité/milieu/notification) sur la déclaration d'incident, colonne « Notification » (retard calculé serveur), action « Clôturer » gatée et relance des notifications dans `Risques.jsx`.
- 2026-08-13 — FE-XQHS7 (part de FE-XQHS5-13) : onglet « Analyse 5-Pourquoi / 8D » sur le détail NCR — l'action `analyse/`, seule surface d'`AnalyseNcr`, n'avait aucun appelant.
- 2026-08-13 — FE-XQHS23 : pont ticket SAV → NCR (`depuis-ticket-sav/`, idempotent) exposé depuis le registre NCR ; seul des deux ponts encore sans appelant.
- 2026-08-13 — FE-XQHS1/2/3/4/16/20/21/22 vérifiés déjà construits (dérogations + disposition, contrôle réception, Pareto défauts, checklist CNSS, signalement QR, aspects environnementaux, relevés de consommation, coût de non-qualité gaté) ; cochés « déjà présent » sans nouveau code.

- 2026-08-13 — lane `frontend/paie` : les 10 tâches (FE-XPAI1-2, FE-YHIRE3/XPAI15/ZPAI2, FE-XPAI3,
  FE-XPAI4, FE-XPAI5/11-13/26, FE-XPAI8-9, FE-XPAI16/18, FE-XPAI22, FE-ZPAI1/3, FE-ZPAI4-7) étaient
  déjà entièrement câblées (écrans/onglets/boutons + appels `paieApi.js` réels, commentaires
  d'annotation par ID de tâche déjà présents dans le code : XPAI1/XPAI3/XPAI4/ZPAI4/ZPAI5/ZPAI6,
  YHIRE3/XPAI15/ZPAI2, WIR38/WIR39) — cochées `[x] (déjà présent)`, aucune modification de code.
- 2026-08-13 — Lane `frontend/kb` : FE-XKB19, FE-XKB8/21, FE-XKB9/13/14, FE-XKB10/18, FE-XKB11/12/17,
  FE-XKB15/16/22, FE-ZGED10-12 — toutes déjà présentes (KbPage/ArticleDetail/ArticleTree/
  TemplatesGallery/KbStatsPanel/FavorisRecentsPanel/KbParcoursPage/ItemsCollectionView/
  BlocInsertPicker/PublicArticlePage, kbApi.js complet), vérifiées sur le vrai code, marquées
  `[x] (déjà présent)`, aucun changement de code.
- 2026-08-13 — lane frontend/stock: audit du code, aucun écart trouvé — les 7 tâches (FE-XPUR25, FE-ZPUR1/4/6/11, FE-ZPUR3/8, FE-ZPUR10/ZSTK3, FE-ZSTK7, FE-ZSTK6/12, FE-ZPUR9) étaient déjà entièrement câblées (stockApi.js + composants stock/paramètres) ; marquées `[x] (déjà présent)`, aucun fichier de code touché.
- 2026-08-13 — lane `frontend/ged` drained (12 tasks). Already fully wired on audit (no change needed): FE-XGED1 (public /ged/signature/:token + /ged/signataire/:token routes), FE-XGED7 (public /ged/depot/:token page), FE-XGED2-3 (multi-signataires + champs de signature in ApprobationPage.jsx), FE-GED26 (CorbeillePage.jsx), FE-GED16 (check-out/check-in in GedNavigator.jsx), FE-XGED14 (bulk toolbar/operations-lot), FE-XGED19-23 (ReglesDossierPage/ReglesAclPage/effective-access panel/RetentionPage Dispositions tab). Built: FE-GED14/XGED16/XGED24 (bouton "Caviarder…" + zones de rédaction dans la modale d'aperçu GED14), FE-XGED15 (onglet "Notes" chatter générique/@mentions dans GedDocumentInsights.jsx, timeline déjà présente), FE-XGED8/10/13/17 (scinder/fusionner/comparer les versions — checklist+OCR déjà couverts par ChecklistPage.jsx), FE-XGED26-27/ZGED3 (onglets "Tableau de bord" kanban + "Analytique" dans ApprobationPage.jsx — envoi en masse déjà présent), FE-ZGED7-13 (favoris/récents + vues enregistrées dans GedSearch.jsx). eslint + vitest + vite build verts sur tous les fichiers touchés.
- 2026-08-13 — Lane `frontend/gestion_projet` drainée : FE-XPRJ4, FE-XPRJ5, FE-XPRJ10-12,
  FE-PROJ11, FE-XPRJ14-17, FE-ZPRJ1-4, FE-ZPRJ7-9/ZPRJ8, FE-XPRJ21/29/27 étaient déjà entièrement
  câblés (Situations tab, ChronoWidget, TachesPage/kanban/Mes tâches, drag-to-reschedule Gantt,
  checklist/RAG/ETC-EAC/burndown, réglages-temps+publier/copier-semaine/auto-affecter — construits
  dans `RessourcesPage.jsx` plutôt que `PlanningPage.jsx` comme le nommait la tâche, fonctionnellement
  correct puisque les affectations vivent avec les ressources —, CSAT/PDF/heatmap risques, création
  projet depuis devis + plan IA + champs marché public/pénalités) : `[x] (déjà présent)`.
  FE-XPRJ7-8/ZPRJ5-6 avait un écart réel : `gestionProjetApi.getHeuresAttendues` (ZPRJ5, écart
  heures attendues vs saisies PAR ressource) n'était appelé par aucun composant — ajouté un onglet
  « Heures attendues » (sélecteur de ressource) dans `TimesheetsTab.jsx`, `ressources` transmis
  depuis `RessourcesPage.jsx`, test vitest ajouté. Gates : eslint / vitest (45 tests) / vite build
  verts.
- 2026-08-13 - FE-ZRH14-17 : onglet Parcours & localisation dans EmployeDetail.jsx (timeline ZRH15 + carte hebdomadaire ZRH16), encart Ou travaille l'equipe aujourd'hui dans RhCockpit.jsx (ZRH16) et recherche par competence dans Competences.jsx (ZRH17, wrapper getEmployesParCompetence) ; les badges de reconnaissance (ZRH14) etaient deja presents.
- 2026-08-13 — FE-ZRH3-6/11/18 : vue « Rapport » congés (ZRH3) dans `Conges.jsx`, onglets « Absents du jour » (ZRH6, avec création d'incident) et « Rapport de présence » (ZRH18) dans `Temps.jsx`, encart « Rétention & turnover » annuel (ZRH11) dans `RhCockpit.jsx` ; wrappers `getRapportConges`/`getAbsentsNonJustifies`/`genererIncidentAbsence`/`getRapportPresence` ajoutés à `rhApi.js` ; la gestion des jours bloqués existait déjà (`JoursBloquesConge.jsx`).
- 2026-08-13 — FE-XRH29/27/31 : onglet « Ayants droit & avantages » (XRH29) dans `EmployeDetail.jsx` et widget « Risque d'attrition — top 5 » (XRH31) dans `RhCockpit.jsx` (+ `RhCockpit.test.jsx`) ; l'organigramme (XRH27) était déjà présent dans `Competences.jsx`.
- 2026-08-13 — FE-XRH15-16/ZRH10 : panneau « Écarts de compétences » + création de besoin de formation en un clic dans `EmployeDetail.jsx`, vue « Évolution » (ZRH10) dans `Competences.jsx`, dialogue « Candidats internes » sur les ouvertures dans `Recrutement.jsx` ; le compa-ratio (XRH16) lisait des clés inexistantes (`compa_ratio`/`salaire`/`mediane`) — recâblé sur les vraies (`compa_ratio_pct`/`salaire_actuel`/`salaire_min`/`salaire_max`/`statut`).
- 2026-08-13 — FE-XRH11-12 : action « Historique des corrections » (audit immuable `getCorrectionsPointage`) sur les pointages et colonne géofence « Hors zone » sur les présences chantier, dans `Temps.jsx`.
- 2026-08-13 — FE-XRH17-23/ZRH7-9 (déjà présent) : l'ATS complet est câblé dans `Recrutement.jsx` (entretiens, gabarits d'email, promesses d'embauche + PDF, vivier, statistiques, `parserCv`, modèles d'évaluation, feedback 360°).
- 2026-08-13 — FE-YHIRE2/ZRH12 (déjà présent) : `sortirEmploye` + certificat de travail dans `EmployeDetail.jsx` et rapport `comptes-actifs-sortis` dans `EmployeList.jsx`.
- 2026-08-13 — FE-XRH1/4-6 (déjà présent) : checklist d'intégration, encarts période d'essai + déclaration CNSS/AMO et onglet chatter dans `EmployeDetail.jsx`.
- 2026-08-13 — FE-XRH9/28/ZRH13 : onglet « Annuaire » (XRH28, `getAnnuaire` + filtre client) et liste de mes demandes d'allocation (ZRH13, `getMesAllocations`) ajoutés à `Portail.jsx` ; « Mes demandes »/attestation étaient déjà en place.
- 2026-08-13 — FE-XRH28b (déjà présent) : onglets « Mes EPI » et « Mes habilitations » du portail consomment `getMesEpi`/`getMesHabilitations`.
- 2026-08-13 — FE-XRH34/XRH26/XRH32 (déjà présent) : passage de quiz, auto-évaluation et baromètre eNPS dans `Portail.jsx` ; constructeur de quiz dans `Competences.jsx`.
- 2026-08-13 — FE-XRH10/13 (déjà présent) : page kiosque plein écran `/kiosque`, administration des devices kiosque et import CSV pointeuse dans `Temps.jsx`.
- 2026-08-13 — FE-SCA41 : le backend async (journal_view.py/tasks.py, testé par test_sca41_async_exports.py) était déjà en place mais aucun appelant front ne gérait le 202 — `journalVentes`/`export-comptable` xlsx renvoyaient alors une réponse blob illisible (le JSON du job encapsulé dans un Blob) sur les périodes volumineuses. Ajouté `ventesApi.exportStatus(jobId)` (GET /ventes/export/status/<job_id>/) et, dans `FactureList.jsx`, `asyncExportPayload()` (détecte le 202) + `pollExportJobAndDownload()` (sonde toutes les 2 s, timeout 5 min, télécharge via `download_url` dès `status:'ready'`) branchés sur `handleExportComptable` (xlsx uniquement — le CSV reste toujours synchrone) et `handleJournalComptable`, avec `toast.info('Export volumineux — génération en arrière-plan.')`. Sous le seuil, `res.status` reste 200 et le chemin existant est inchangé. Test focalisé ajouté (`FactureListFE_SCA41.test.mjs`, 5/5 verts, patron source-level déjà utilisé par `FactureListVX92.test.mjs`). Gates : eslint + `npx vite build` verts.

