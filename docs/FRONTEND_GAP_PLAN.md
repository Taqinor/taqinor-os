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
- [ ] FE-XFLT4 — "Cycle de vie" tab in `VehiculeDetail.jsx` (statut transitions + checklist gate); add `changerStatut`/`ceder` to `flotteApi.js`. (@lane: frontend/flotte)
- [ ] FE-XFLT1-3 — "Contrats" + "Grand livre des coûts" tabs in `VehiculeDetail.jsx`; add `contratsVehicule`/`couts`/`vehiculeLedger` to `flotteApi.js`. (@lane: frontend/flotte)
- [ ] FE-XFLT5 — "Signaler un problème" button + open-signalements list on cockpit/detail; add `signalements`(+`convertir_en_or`) to `flotteApi.js`. (@lane: frontend/flotte)
- [ ] FE-XFLT7/15/18 — "Analyse des coûts" tab + cockpit tiles; add `rapportCouts`/`rapportRemplacement`/`rapportBudget`/`budgets` to `flotteApi.js`. (@lane: frontend/flotte)
- [ ] FE-XFLT12/13 — model-select pre-fill on vehicle create + inspection checklist screen; add `modelesVehicule`/`modelesInspection`/`inspections` to `flotteApi.js`. (@lane: frontend/flotte)
- [ ] FE-XFLT14/19 — repair-order approval + `sous_garantie` warning in `EntretienScreen.jsx`; add `garanties`/`ordresReparation.approuver`. (@lane: frontend/flotte)
- [ ] FE-XFLT17 — état-des-lieux e-signature + charte acknowledgment; add `etatsDesLieux.signer`/`chartesVehicule`/`accusesCharte`. (@lane: frontend/flotte)
- [ ] FE-XFLT20 — accessory holders on `VehiculeDetail.jsx`; add `remisesAccessoire`/`detenteurs_courants`. (@lane: frontend/flotte)
- [ ] FE-XFLT22-23 — vehicle CSV import entry + fuel-receipt OCR pre-fill + bulk affectation/plan-entretien rollout; add `pleins.ocr`/`affectations.masse`/`plansEntretien.rollout`. (@lane: frontend/flotte)
- [ ] FE-XFLT24-25/28 — telematics zones/DTC (gated) + constructor recalls; add `zonesGeographiques`/`rappelsConstructeur`. (@lane: frontend/flotte)
- [ ] FE-XFLT26 — verify ICE/IF fields render in the garage form (`EntretienScreen.jsx`). (@lane: frontend/flotte)

## Lane `frontend/qhse` (XQHS — all backend-only; verify XQHS5/6/7/9/10/12 aren't ORPHAN backends first)
- [ ] FE-XQHS16 — public QR signalement: "Générer QR" action + `signalementsPublics`/`liensSignalement` in `qhseApi.js`. (@lane: frontend/qhse)
- [ ] FE-XQHS17 — mobile quick-capture observation form; add `observationsSecurite`. (@lane: frontend/qhse)
- [ ] FE-XQHS2 — dérogations + NCR disposition fields in `NonConformites.jsx`; add `derogations`. (@lane: frontend/qhse)
- [ ] FE-XQHS3 — "Contrôle réception" screen/tab; add `plansControleReception`/`controlesReception`/`pointsControleReception`. (@lane: frontend/qhse)
- [ ] FE-XQHS4 — Pareto défauts chart on `QhseCockpit.jsx`; add `codesDefaut`/`paretoDefauts`. (@lane: frontend/qhse)
- [ ] FE-XQHS1 — CNSS declaration legal-step checklist; add `etapesDeclarationAt`. (@lane: frontend/qhse)
- [ ] FE-XQHS5-13 — recalls/SCAR/5-why-8D/certifications/audit-program/revues/objectifs UIs; add the matching `qhseApi` resources (VERIFY each viewset exists — some may be ORPHAN → `[BLOCKED: needs backend]`). (@lane: frontend/qhse)
- [ ] FE-XQHS14 — enterprise risk/opportunity + stakeholder register in `Risques.jsx`; add `risquesOpportunites`/`partiesInteressees`/`contexteOrganisation`. (@lane: frontend/qhse)
- [ ] FE-XQHS15/18/19 — procedure diffusion + acknowledgment, drill log, environmental-incident fields; add `diffusionsProcedure`/`accusesLecture`/`exercicesUrgence`. (@lane: frontend/qhse)
- [ ] FE-XQHS20-21 — environmental aspects register + monthly consumption entry → bilan carbone; add `aspectsEnvironnementaux`/`relevesConsommation`. (@lane: frontend/qhse)
- [ ] FE-XQHS22 — coût de non-qualité rollup (gated) in cockpit + NCR/CAPA/Incident cost fields; add `coutNonQualite`. (@lane: frontend/qhse)
- [ ] FE-XQHS23-27 — NCR-from-SAV action, MOC screen, IA-assist buttons, veille réglementaire list, bilingual causerie PDF button; add matching `qhseApi` entries. (@lane: frontend/qhse)

## Lane `frontend/ged` (XGED/ZGED — incl. the flagship e-sign ceremony)
- [ ] FE-XGED1 — **CRITICAL** public signing ceremony pages: React routes `/ged/signature/:token` + `/ged/signataire/:token` (no-auth) consuming the existing public endpoints. (@lane: frontend/ged) (opus)
- [ ] FE-XGED7 — public deposit page for `depot/<token>/`. (@lane: frontend/ged)
- [ ] FE-XGED2-3 — multi-signer sequencing + positioned signature fields in the "Nouvelle demande" dialog (`ApprobationPage.jsx`); add `signataires-demande`/`champs-signature`. (@lane: frontend/ged) (opus)
- [ ] FE-GED14/XGED16/XGED24 — document preview modal (click a row) + overlay annotations + redaction zones; add `apercu`/`annotations`/`caviarder`. (@lane: frontend/ged)
- [ ] FE-GED26 — "Corbeille" screen (list/restore/purge); add `corbeille`/`mettre-en-corbeille`/`restaurer-corbeille`/`purger`. (@lane: frontend/ged)
- [ ] FE-GED16 — check-out/check-in lock buttons on document detail. (@lane: frontend/ged)
- [ ] FE-XGED14 — row checkboxes + bulk action toolbar in `GedNavigator.jsx` → `operations-lot`. (@lane: frontend/ged)
- [ ] FE-XGED15 — document detail drawer with timeline/chatter/@mentions; add `planifier`/`timeline`. (@lane: frontend/ged)
- [ ] FE-XGED8/10/13/17 — folder checklist, split/merge UI, OCR validation queue, version-compare screen. (@lane: frontend/ged)
- [ ] FE-XGED19-23 — rule-builder screens (folder auto-actions, approval routing, metadata ACL), effective-access panel, disposition-review gate. (@lane: frontend/ged)
- [ ] FE-XGED26-27/ZGED3 — analytics dashboard cards, bulk signature-request CSV upload, signature kanban. (@lane: frontend/ged)
- [ ] FE-ZGED7-13 — favorites/recents sidebar + saved searches; add `mes-favoris`/`mes-recents`/`vues`. (@lane: frontend/ged)

## Lane `frontend/contrats` (CLM lifecycle actions all unwired)
- [ ] FE-CONTRAT16-17 — **CRITICAL** "Signatures" tab + Signer button in `ContratDetail.jsx` (`getSignatures`/`signer` already in `contratsApi.js`). (@lane: frontend/contrats)
- [ ] FE-CONTRAT13-14 — "Approbation" tab: `lancerApprobation`/`approuverEtape`/`rejeterEtape` + étapes list. (@lane: frontend/contrats)
- [ ] FE-CONTRAT12 — wire `StateMachine.jsx`/actions bar to `getStatutsSuivants`+`changerStatut` (contract can't leave brouillon today). (@lane: frontend/contrats)
- [ ] FE-CONTRAT23-25 — Renouveler / Créer avenant / Résilier buttons in `ContratDetail.jsx`. (@lane: frontend/contrats)
- [ ] FE-CONTRAT7 — create-contract flow: wire `ModelesPage.jsx` row → `instancierModele` (no create path exists today). (@lane: frontend/contrats)
- [ ] FE-CONTRAT15 — note composer (`noter`) in the activity panel. (@lane: frontend/contrats)
- [ ] FE-CONTRAT33 — contracts dashboard (`getTableauBord`/`getReporting`, already in api client, uncalled). (@lane: frontend/contrats)
- [ ] FE-XCTR7-8-11 — MRR waterfall + retention cohorts heatmap + price-revision campaign screen; add `mrr-mouvements`/`cohortes-retention`/`campagne-revision`. (@lane: frontend/contrats)
- [ ] FE-XCTR5 — billing-exceptions card (`cycles-facturation`/`rejouer`). (@lane: frontend/contrats)
- [ ] FE-XCTR17-21 — **CRITICAL** outbound equipment-**rental** module: new `/contrats/location` page wired to `OrdreLocationViewSet` (reservation calendar, caution encaisser/restituer/retenir, inspection, ROI, bons PDF). (@lane: frontend/contrats) (opus)
- [ ] FE-XCTR14 — client portal "Mes contrats" + renew/terminate request buttons (`portail/<token>/` in `ClientPortalPage.jsx`). (@lane: frontend/contrats)
- [ ] FE-XCTR2-3 — "Équipements couverts" panel + "X/Y visites consommées" on `ContratsMaintenance.jsx`. (@lane: frontend/contrats)
- [ ] FE-CONTRAT-config — PlanRecurrent / MotifResiliation / ParametresLocation CRUD screens. (@lane: frontend/contrats)

## Lane `frontend/gestion_projet` (XPRJ/ZPRJ round-2 backend-only)
- [ ] FE-XPRJ4 — "Situations" tab (BTP progress billing) in `ProjetDetailPage.jsx`; add `situations`/`lignes-situation`. (@lane: frontend/gestion_projet)
- [ ] FE-XPRJ5 — task chrono start/stop buttons + active indicator (`demarrer-chrono`/`arreter-chrono`). (@lane: frontend/gestion_projet)
- [ ] FE-XPRJ7-8/ZPRJ5-6 — timesheet approval workflow + manquants/heures-attendues/classement/rapprochement/rapport in `RessourcesPage.jsx`. (@lane: frontend/gestion_projet)
- [ ] FE-XPRJ10-12 — Tâches CRUD screen (filters assigné/priorité/statut) + kanban + "Mes tâches" page/route. (@lane: frontend/gestion_projet)
- [ ] FE-PROJ11 — drag-to-reschedule in `GanttChart.jsx` (`reprogrammer`). (@lane: frontend/gestion_projet)
- [ ] FE-XPRJ14-17 — checklist toggle, RAG/point-avancement, ETC/EAC in `BudgetPage.jsx`, burndown chart. (@lane: frontend/gestion_projet)
- [ ] FE-ZPRJ1-4 — réglages temps + publier/copier-semaine/auto-affecter buttons in `PlanningPage.jsx`. (@lane: frontend/gestion_projet)
- [ ] FE-ZPRJ7-9/ZPRJ8 — CSAT evaluation link, status-report PDF button, risk heatmap in `RisquesPage.jsx`. (@lane: frontend/gestion_projet)
- [ ] FE-XPRJ21/29/27 — "Créer projet depuis devis" button on devis list, AI plan propose→confirm, marché-public fields + pénalités. (@lane: frontend/gestion_projet)

## Lane `frontend/paie` (XPAI/ZPAI/YHIRE round-2 backend-only)
- [ ] FE-XPAI1-2 — **CRITICAL** Solde de tout compte (STC) action/screen from the sortie flow; add `stc`/`stcPdf`. (@lane: frontend/paie)
- [ ] FE-YHIRE3/XPAI15/ZPAI2 — **CRITICAL** pre-run warnings panel (`controle-completude`/`controle-ecarts`/`avertissements`) at top of `PaieRunWizard.jsx` (safety gate silently skipped today). (@lane: frontend/paie)
- [ ] FE-XPAI3 — "Mutuelle" tab in `PaieParametres.jsx`; add `regimes-mutuelle`/`adhesions-mutuelle`. (@lane: frontend/paie)
- [ ] FE-XPAI4 — "Run hors-cycle / 13e mois" button (`run-gratification`). (@lane: frontend/paie)
- [ ] FE-XPAI5/11-13/26 — new PaieDeclarations tabs: état des charges, rapprochement GL/AFFEBDS, BDS complémentaire, XML SIMPL-IR, registre congés, historique carrière. (@lane: frontend/paie)
- [ ] FE-XPAI8-9 — virement format selector (CSV/SIMT) + ligne-virement reject/reissue. (@lane: frontend/paie)
- [ ] FE-XPAI16/18 — net↔brut simulator tab + exemption-regime fields on profile form. (@lane: frontend/paie)
- [ ] FE-XPAI22 — cumuls go-live import wizard (`reprise-dry-run`/`reprise-commit`). (@lane: frontend/paie)
- [ ] FE-ZPAI1/3 — paie analyse pivot (rubrique×mois×dept) + coût employeur report. (@lane: frontend/paie)
- [ ] FE-ZPAI4-7 — cancel bulletin, batch-print bulletins, saisie-arret annuler/creer-lot. (@lane: frontend/paie)

## Lane `frontend/rh` (XRH/ZRH round-2 backend-only — 33 orphaned viewsets)
- [ ] FE-XRH17-23/ZRH7-9 — **CRITICAL** full ATS in `Recrutement.jsx`: interviews (`entretiens-recrutement`), email templates, offer letters (`promesses-embauche`), talent pool (`vivier`), analytics, CV parsing (`parser-cv`), evaluation templates + 360 feedback. (@lane: frontend/rh) (opus)
- [ ] FE-YHIRE2/ZRH12 — **CRITICAL** offboarding: `sortir` action button/modal + `comptes-actifs-sortis` security report + `certificat-travail` PDF in `EmployeDetail.jsx`. (@lane: frontend/rh)
- [ ] FE-XRH1/4-6 — onboarding checklist + essai/CNSS-entry widgets + chatter timeline tab in `EmployeDetail.jsx`. (@lane: frontend/rh)
- [ ] FE-XRH9/28/ZRH13 — self-service portal: "Mes demandes"/attestation, directory (`annuaire`), allocations in `Portail.jsx`. (@lane: frontend/rh)
- [ ] FE-XRH28b — wire the already-written dead `getMesEpi`/`getMesHabilitations` into "Mes EPI"/"Mes habilitations" Portail tabs. (@lane: frontend/rh)
- [ ] FE-XRH34/XRH26/XRH32 — quiz-taking flow + auto-évaluation + eNPS pulse in `Portail.jsx`; quiz builder in `Competences.jsx`. (@lane: frontend/rh)
- [ ] FE-XRH10/13 — kiosk fullscreen page (device-token) + device-token admin + CSV pointeuse import in `Temps.jsx`. (@lane: frontend/rh)
- [ ] FE-XRH11-12 — pointage correction history + geofence flag in `Temps.jsx`. (@lane: frontend/rh)
- [ ] FE-XRH15-16/ZRH10 — competence gap-analysis/evolution + salary-band compa-ratio (gated) + internal candidates. (@lane: frontend/rh)
- [ ] FE-XRH29/27/31 — dependents/benefits tab, org-tree, attrition-risk widget. (@lane: frontend/rh)
- [ ] FE-ZRH3-6/11/18 — congé/absence/turnover/présence reports in `Conges.jsx`/`RhCockpit.jsx`/`Temps.jsx`; jours-bloqués mgmt. (@lane: frontend/rh)
- [ ] FE-ZRH14-17 — reconnaissance badges, career timeline, weekly location, skills search on `EmployeDetail.jsx`. (@lane: frontend/rh)

## Lane `frontend/sav` (XSAV/XCTR/ZSAV/ZMFG round-2 backend-only)
- [ ] FE-XSAV19/XSAV10 — **CRITICAL** public pages: QR problem-report `/e/:token` + ticket-tracking + CSAT `/suivi/:token` (both are JSON dead-ends today). (@lane: frontend/sav) (opus)
- [ ] FE-XSAV3/XFSM1/XCTR4 — "Créer un devis"/"Générer facture"/"Facturer" buttons on ticket detail (`creer-devis`/`generer-facture`/`facturer` + `couverture`). (@lane: frontend/sav)
- [ ] FE-SAV-warranty — supplier-RMA screen (`warranty-claims`, FG83). (@lane: frontend/sav)
- [ ] FE-XSAV15-17/XSAV9 — MTBF/MTTR/downtime/disponibilité/meter-readings + write-off buttons on `EquipementDetail`. (@lane: frontend/sav)
- [ ] FE-XSAV8 — SLA compliance report screen (`insights/sav-sla/`). (@lane: frontend/sav)
- [ ] FE-XSAV12/27/ZSAV8-9 — merge duplicate ticket, loaner tracking, ticket→lead, follow/unfollow. (@lane: frontend/sav)
- [ ] FE-ZSAV2-3-6 — ticket categories filter + Paramètres CRUD, scheduled activities panel, "Action requise" board. (@lane: frontend/sav)
- [ ] FE-SAV-kb/macros — KB article screen + "Résolutions similaires"/macro-picker on ticket (`kb-articles`/`reponses-type`/`pieces-compatibles`). (@lane: frontend/sav)
- [ ] FE-SAV-alarmes — inverter-alarms panel (list/acquitter/escalader, FG280). (@lane: frontend/sav)
- [ ] FE-XSAV14/ZMFG6/11 — cause/remède + Pareto pannes, worksheet UI, predicted-failure estimations. (@lane: frontend/sav)

## Lane `frontend/litiges`
- [ ] FE-LITIGE4 — render `rec.ncr`/`rec.audit` (NCR/Audit linked) in `ReclamationDetail.jsx` + linking control in `ReclamationEditor.jsx` (data already fetched). (@lane: frontend/litiges)

## Lane `frontend/compta` (XACC/ZACC round-2 — <half of accounting reachable)
- [ ] FE-FG122/126/132 — wire the already-written uncalled `positionTresorerie`/`previsionnelTresorerie`/`balanceAgeeFournisseurs` (cheapest wins) into `TresoreriePage.jsx`/`EtatsPage.jsx`. (@lane: frontend/compta)
- [ ] FE-ZACC1-2 — "Export PDF" + "Comparer N-1" controls on `EtatsPage.jsx` (backend accepts `?export=pdf`/`?comparer=1`). (@lane: frontend/compta)
- [ ] FE-ZACC3-4/12/16 — add tableau-flux, journal-items, tableau-immobilisations, dossier-de-clôture to the `ETATS` array + buttons. (@lane: frontend/compta)
- [ ] FE-XACC9 — "Échéances fiscales" tab in `FiscalitePage.jsx` (`obligations-fiscales`). (@lane: frontend/compta)
- [ ] FE-notes-frais — compta.NoteFrais validation/comptable screen (distinct from RH self-service): `notes-frais`/`rapports`/`plafonds`/`baremes-indemnite`/`indemnites-chantier` + soumettre/valider/rejeter/rembourser/recu-pdf. (@lane: frontend/compta)
- [ ] FE-effets — "Effets à recevoir/payer" page + bordereaux + escompte/endossement actions. (@lane: frontend/compta)
- [ ] FE-payment-runs — PaymentRun screen + `fichier-virement` bank export (FG133-134). (@lane: frontend/compta)
- [ ] FE-FG145 — RetenueGarantie + CautionBancaire tabs (+ attestation-annuelle). (@lane: frontend/compta)
- [ ] FE-FG146-148 — revenue-recognition/WIP (ContratAvancement/TravauxEnCours) + CommissionPayoutRun screens. (@lane: frontend/compta)
- [ ] FE-XFAC14/XACC26 — AR/AP netting (compensations) + Provision/ModeleRapprochement/BalanceOuverture read+action screens. (@lane: frontend/compta)
- [ ] FE-COMPTA39 — read-only audit-trail viewer (`pistes-audit`, admin-only). (@lane: frontend/compta)
- [ ] FE-rapprochement-detail — bank-reconciliation drill-down dialog (`lignes-gl`/`pointer`/`suggestions`/`ocr-import`) in `RapprochementsPage.jsx`. (@lane: frontend/compta)
- [ ] FE-immo-caisse-actions — Immobilisations `ceder`/`poster` row actions + Caisse mouvement/clôture drawer + Virement `poster`. (@lane: frontend/compta)
- [ ] FE-ZACC14/XACC29 — contrôle ICE/IF + continuité des séquences as `ETATS` entries. (@lane: frontend/compta)

## Lane `frontend/stock` (ZPUR/ZSTK round-2 backend-only)
- [ ] FE-XPUR25 — **BLOCKED: needs backend** (`fournisseurs/{id}/vue-360/` action never built) then route the orphan `pages/stock/FournisseurFiche360.jsx` (add lazy route + nav + row link). (@lane: frontend/stock)
- [ ] FE-ZPUR1/4/6/11 — BCF actions: `facturer`, `dupliquer`, `fusionner` (multi-select), `rouvrir` + motif-required `annuler` on `BonsCommandeFournisseur.jsx`; add to `stockApi.js`. (@lane: frontend/stock)
- [ ] FE-ZPUR3/8 — Modèles BCF screen (`modeles-bcf`/`generer`) + BCF header fields (acheteur/ref_fournisseur/note_bas_page/incoterm). (@lane: frontend/stock)
- [ ] FE-ZPUR10/ZSTK3 — product-detail screen with "en commande" qty + `previsionnel` forecast tab. (@lane: frontend/stock)
- [ ] FE-ZSTK7 — "Vue groupée / pivot" toggle on `MouvementsPage.jsx` (`mouvements/agregation`). (@lane: frontend/stock)
- [ ] FE-ZSTK6/12 — lot/série label printing on reception + barcode-nomenclature CRUD (Paramètres). (@lane: frontend/stock)
- [ ] FE-ZPUR9 — purchase-analysis PDF button next to the XPUR24 xlsx export. (@lane: frontend/stock)

## Lane `frontend/installations` (XMFG kitting/atelier — whole subsystem backend-only)
- [ ] FE-XMFG1-16 — **atelier/kitting UI**: new `pages/installations/AteliersPage.jsx` (OrdreAssemblage/OrdreDemontage list/detail/close, backflush, reservations, QC gate, bon-pdf) + route/nav; add `ordres-assemblage`/`kits-produit/{id}/structure`/`ordres-demontage` to `installationsApi.js`. (@lane: frontend/installations) (opus)

## Lane `frontend/compta` (additional round-2 orphans — fold into the compta lane above)
- [ ] FE-XACC33 — "Immobiliser" button on `pages/stock/FacturesFournisseur.jsx` (`immobilisations/depuis-facture-fournisseur`). (@lane: frontend/compta)
- [ ] FE-XACC3-4 — bank-recon "Suggestions" panel + "Modèles rapprochement" CRUD in `RapprochementsPage.jsx`. (@lane: frontend/compta)
- [ ] FE-COMPTA21 — consume the uncalled `balanceAgeeFournisseurs` + add `releveFournisseur` drill-down. (@lane: frontend/compta)

## SAV lane additions (fold into `frontend/sav`)
- [ ] FE-XSAV5/21/28 — attente-client SLA pause/resume, similar-ticket panel, AI triage banner on `TicketsPage.jsx`. (@lane: frontend/sav)
- [ ] FE-ZMFG1-2/4/5-12 — SAV teams + equipment categories (Paramètres + ticket/equipment filters), instructions tab, worksheet form, unified pièces, scrap action, estimations, bon-pdf. (@lane: frontend/sav)

## Lane `frontend/kb` (XKB8-22 + ZGED10-12 backend-only; XKB23 already wired)
- [ ] FE-XKB19 — **CRITICAL** public unauthenticated article route `/kb/public/:token` + `PublicArticlePage.jsx` + "Share on web" action (`partages`/`depublier`). (@lane: frontend/kb) (opus)
- [ ] FE-XKB8/21 — article tree sidebar (`arbre`, drag-reorder parent/ordre) + move/duplicate row actions. (@lane: frontend/kb)
- [ ] FE-XKB9/13/14 — visibility+ACL selector, `<ChatterWidget model="kb.kbarticle">` comments, verified badge + lock (`verifier`/`verrouiller`), stale-content report. (@lane: frontend/kb)
- [ ] FE-XKB10/18 — markdown render + attachments + `sommaire` TOC; language switcher + RTL + `traduire`. (@lane: frontend/kb)
- [ ] FE-XKB11/12/17 — backlinks panel, templates gallery (`gabarits`/`depuis-gabarit`), export PDF/MD + import MD + ZIP. (@lane: frontend/kb)
- [ ] FE-XKB15/16/22 — favorites/recents, KB stats reports, onboarding "Parcours" screen (`KbParcours` assign+progression). (@lane: frontend/kb)
- [ ] FE-ZGED10-12 — emoji + cover image, custom properties + kanban/cards/list/calendar item views, reusable-block insert picker. (@lane: frontend/kb)

## Lane `frontend/pos` (entire apps/pos backend orphaned — FE built against ventes.Facture)
- [ ] FE-XPOS1-18 — **CRITICAL** rewrite `posApi.js` to call `/pos/ventes|sessions|retraits|config-materiel/`; add routes `/pos/session` (ouverture/clôture + rapport-z, XPOS4), `/pos/dashboard` (XPOS11), `/pos/retraits` (click-and-collect, XPOS15); wire ticket-escpos/share-link + serial capture (XPOS9) into `CaisseScreen.jsx`. (@lane: frontend/pos) (opus)

## Lane `frontend/ventes` (XSAL/ZSAL round-2 — mostly cheap NOT_WIRED stubs)
- [ ] FE-XSAL6 — **BLOCKED: needs backend** (`PlanCommission` has no viewset/URL + not consumed by reporting/insights.py) then a "Plans de commission" screen under parametres. (@lane: frontend/ventes)
- [ ] FE-XSAL1-3 — price-list admin CRUD + `liste_prix` field on `ClientForm.jsx` + call `getPrixApplicable` (remove the stale "ne pas appeler" comment) in `DevisGenerator.jsx`/`ProduitPicker.jsx` with a "Tarif" badge. (@lane: frontend/ventes)
- [ ] FE-XSAL12 — partial-delivery dialog + reliquat column in `VentesKanban.jsx` (`livrer-partiel`). (@lane: frontend/ventes)
- [ ] FE-ZSAL8/XSAL16 — BC PDF button + proposal `engagement` summary on `DevisList.jsx` (already serialized). (@lane: frontend/ventes)
- [ ] FE-ZSAL5 — keyed email-template editor (`envoi_devis`) in `EmailSection.jsx`. (@lane: frontend/ventes)

## Lane `frontend/crm` (ZSAL round-2 — api client stubs defined, never called)
- [ ] FE-ZSAL2 — "Appliquer un plan" button + plan picker on lead detail + PlanActivite CRUD (`getPlansActivite`/`appliquerPlanActivite` already in `crmApi.js`). (@lane: frontend/crm)
- [ ] FE-ZSAL4 — "Convertir en client" button + modal on lead detail (`convertirClient`). (@lane: frontend/crm)
- [ ] FE-ZSAL3/ZSAL6 — "Mes équipes" dashboard cards + EquipeCommerciale CRUD + "Attribution des leads" section in `Rapports.jsx`. (@lane: frontend/crm)
- [ ] FE-ZSAL1/XSAL17 — suggested follow-up activity prompt in `MesActivitesPage.jsx` + `{lien_rdv}` placeholder in template editor. (@lane: frontend/crm)

## Lane `frontend/reporting` (systemic offender — many [x] reports backend-only)
- [ ] FE-XKB1-3/ZCTR7-9 — **standalone Approvals inbox** `pages/approbations/ApprobationsPage.jsx` calling `reporting/approbations-en-attente/` UNFILTERED (all 5 sources: automation/contrats/ged/installations/workflow) + decide/bulk/filter/sort + route/nav (today only the narrow `source=workflow` slice is shown). (@lane: frontend/reporting) (opus)
- [ ] FE-XPLT6 — "Alertes KPI" CRUD under parametres (`reporting/kpi-alertes/`). (@lane: frontend/reporting)
- [ ] FE-XPLT10 — dashboard share/revoke UI + `/dashboards-tv` public kiosk route (`core/dashboards-partages`). (@lane: frontend/reporting)
- [ ] FE-XPLT22 — `ClasseurPage.jsx` (live-data spreadsheet) + `reportingApi.js` client. (@lane: frontend/reporting)
- [ ] FE-XPLT9 — mount the already-built-but-unused `DashboardFilterBar.jsx` in `DashboardConfigPage.jsx`. (@lane: frontend/reporting)
- [ ] FE-XPLT11 — **BLOCKED: needs pivot/BI-explorer screen (FG382, itself unbuilt frontend)** then expose the formula measure. (@lane: frontend/reporting)
- [ ] FE-XSAV8/XFSM16-17 — SAV SLA report + field-service analytics + technician scorecard pages under `pages/reporting/`. (@lane: frontend/reporting)

## Lane `frontend/platform` (agent / dataimport / audit / privacy)
- [ ] FE-XPLT18 — propose→confirm "Générer une règle" UI in `AutomatisationsSection.jsx` (`agent/actions/automation-draft`). (@lane: frontend/platform)
- [ ] FE-YHARD2 — "Historique / annuler" tab in `AgentActions.jsx` (`agent logs/` + undo). (@lane: frontend/platform)
- [ ] FE-XPLT1-2 — import upsert mode + saved-mapping picker + error-CSV link in `ExcelImport.jsx` (`importApi.js` mode/external_id/saveMapping/jobErreursCsv). (@lane: frontend/platform)
- [ ] FE-XPLT23 — "Confidentialité" tab under parametres: CNDP `registre-traitements` CRUD + `dsr-requests` (DSR) submission/tracking. (@lane: frontend/platform)
- [ ] FE-YHARD3 — "Historique à cette date" (as-of) view on record detail / `Journal.jsx` (admin/Directeur). (@lane: frontend/platform)
- [ ] FE-SCA41 — Exports ventes : gérer la réponse 202 des exports xlsx volumineux (journal-ventes / export-comptable) : afficher « génération en arrière-plan », poller GET /api/django/ventes/export/status/<job_id>/ (payload {status, download_url, filename}) puis déclencher le téléchargement via download_url (URL pré-signée 1 h). Sous le seuil (2 000 lignes, env), rien ne change.

## AUDIT COMPLETE (2026-07-06)
- Domains CLEAN (fully wired, no gaps): **litiges, monitoring, publicapi, audit** baseline screens.
- Legitimately backend-only (no UI ever promised): YAPIC7-10, YHARD1 (versioning/webhooks/idempotency/encryption).
- `ODX5` (Applications catalogue) still `[ ]` in PLAN.md — normal backlog, not a gap.

## DONE LOG
<!-- one dated line per shipped task -->


## DONE LOG
<!-- one dated line per shipped task -->
