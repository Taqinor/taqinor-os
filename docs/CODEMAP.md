# CODEMAP — TAQINOR OS

Generated from commit `dev` on 2026-06-29, refreshed for the functional-domain expansion wave (5 parallel worktree lanes: apps/compta clôture de période + OD manuelles + à-nouveaux FG115–117; apps/ventes solar string-design + inverter match + tilt/azimut FG246/247/249; apps/installations jalons/modèles-de-projet/réunions FG293/296/298; **NEW app apps/flotte** Vehicule+EnginRoulant FLOTTE1/2/4; **NEW app apps/ged** Cabinet/Folder/Document/Version GED1/2/3 — all additive, company-scoped, tested), on top of the prior `dev-uiwave-20260621` world-class UI wave (34 frontend UI/UX tasks: premium DataTable, calm chrome, foundation hooks/primitives, page redesigns) (PLAN2 priority-queue run — Group Q Devis↔Toiture-3D pipeline backend (Q1–Q7: Devis.roof_layout/roof_image + layout endpoints, Lead roof_point/roof_outline/bill_kwh + per-lead token, build_devis_from_layout() service, MinIO roof-image, layout-aware quote data with byte-identical no-layout path, tokenized /proposal data endpoint + e-sign accept); Group R agentic layer — NEW APP `apps/agent` (in-code action registry + `/api/django/agent/` catalogue, AG1), FastAPI registry-driven tools with propose→confirm (`/sql-agent/confirm`, AG2) surfaced on /query, assistant confirm/result cards (AG3), domain agent actions in ventes/crm/stock/sav/installations `agent_actions.py` (AG4–AG9), Groq-Whisper assistant voice `/sql-agent/transcribe` (AG10) + voice/hands-free chat (AG11/AG12); Group S internal team chat — NEW APP `apps/chat` (Conversation/Member/Message/Attachment/Reaction/Mention, company+membership scoped, `/api/django/chat/`, S1–S9), self-hosted faster-whisper `/chat/transcribe` (NEW dep, `CHAT_TRANSCRIPTION_ENABLED`, S10) + Celery transcription pipeline (S11), full React `features/messaging` UI + `/messages` route (S12–S20); design/UI/reporting polish (F120–F123 OKLCH tokens, G124–G128 primitives, K147/N161/K148/K149/J146/P167 chart kit + dashboard + table unification); P171 DataTable→@tanstack engine swap (API-compatible, full parity). ADDITIVE migrations: ventes/0024, crm/0024, chat/0001, notifications/0007. Founder standing consent recorded in CLAUDE.md lifting the ARCH/AUTH/COST/DECISION/GALLERY/DEP gate. + 2026-06-22 greenfield-foundations run: 7 NEW apps stood up (apps/rh DossierEmploye master FG154/DC29, apps/paie ParametrePaie/BaremeIR PAIE1/2/4, apps/gestion_projet Projet/ProjetChantier PROJ1, apps/contrats Contrat CONTRAT1/2, apps/qhse NCR/CAPA QHSE1/9/10, apps/kb KbArticle KB1, apps/litiges Reclamation LITIGE1) — additive, multi-tenant, admin-gated, tested; INSTALLED_APPS+urls wired; 13 tasks ticked. BLOCKED: S21 WebSocket/Channels (needs provisioned ASGI/nginx-WS infra), I134/I138 ⌘K palette (reconcile with existing providers).) + 2026-06-22 `claude/serene-ptolemy-dj5cs0` wave-1 run: 8 parallel worktree lanes — FG122 (compta consolidated treasury position + AR/AP/payroll/TVA projection, GL-only selector + read endpoint), M4 (last `ventes → audit` back-edge removed — PDF audit capture now flows through the `core.events.document_pdf_generated` bus with an `audit` receiver; new import-linter contract pins it), FG157 (apps/rh `Remuneration` gated by the new `salaires_voir` permission), PAIE3 (apps/paie 2026 Moroccan legal payroll defaults seeded editable + `valide_par_fondateur` flag), PROJ5 (apps/gestion_projet `Tache` WBS with self-FK sub-tasks), QHSE5 (apps/qhse auto-conformity min/max on `PointControleModele`/`ReleveControle`), FG350 (frontend global `CopilotPanel` drawer reusing the FastAPI agent), GED5 (frontend `/ged` arborescent navigator over existing ged endpoints) — all additive, multi-tenant, tested; ADDITIVE migrations rh/0004, paie/0002, qhse/0004, gestion_projet/0005. + wave-2 (same run): FG123 (compta `RapprochementBancaire`/`LigneReleve`/`PointageReleve` — statement↔GL pointing, écart-zero close, no écriture), FG49 (ventes account-coded grand-livre export CGNC 3421/7111/4455, xlsx+csv, configurable codes), FG351 (apps/agent registry guarded write actions `ventes.devis.create`/`crm.client.create`/`crm.lead.create` via propose→confirm + FastAPI dynamic action_tools), FG158 (rh `DossierEmploye` emergency-contact + extended coordinates fields), PAIE5 (paie family-charge deduction params + `compute_ir` helper), GED6 (ged `DocumentLien` generic-target link via `records.ALLOWED_TARGETS` +ventes.boncommande), PROJ6 (gestion_projet `DependanceTache` FS/SS/FF/SF + lag with cycle guards), QHSE6 (qhse hold-point gating selector/endpoint) — all additive, multi-tenant, tested; ADDITIVE migrations compta/0006, rh/0005, paie/0003, ged/0002, gestion_projet/0006 (FG49/FG351/QHSE6 need none); import-linter stays 4/4. + wave-3 (same run, 7 lanes): FG124 (compta `Caisse`/`MouvementCaisse`/`ClotureCaisse` petty-cash with optional GL posting honouring the FG115 period lock), FG50 (ventes acompte transfer/refund on facture cancel — re-point Paiement or reversing negative Paiement, chatter, no migration), FG159 (rh `DocumentEmploye` vault reusing `records.Attachment` MinIO storage + optional expiry), PAIE6 (paie `Rubrique` configurable payslip-line catalogue + idempotent seed), GED7 (ged `migrate_attachments_to_ged` command importing records.Attachment into Documents reusing file_key + DocumentLien), PROJ7 (gestion_projet `Jalon` milestones + `facturation_pct`), QHSE7 (qhse `ReleveCourbeIV` PV string I-V curve + fill factor) — all additive, multi-tenant, tested; ADDITIVE migrations compta/0007, rh/0006, paie/0004, gestion_projet/0007, qhse/0005 (FG50/GED7 need none); import-linter stays 4/4. FG352 (RAG/pgvector, DEP:langchain-textsplitters) intentionally left [ ] for a focused run. + 2026-06-22 `claude/plan-md-completion-ysbchz` drain: 8 parallel worktree lanes off PLAN.md (compta FG125–130, ventes FG51/53/248/250/251, core FG355–359 NoOp-AI, rh FG160–165, paie PAIE7–12, ged GED8–13, gestion_projet PROJ8–13, qhse QHSE8/11–15 — 46 tasks; ADDITIVE migrations across those apps + customfields/0003; new NoOp scaffolds add no external dependency; GED12 semantic embedding OFF by default). + 2026-06-23 PLAN2 **Group U** drain (U1–U14, 10 parallel worktree lanes, one self-merge): lead-modal stays-open UX (U1), mouse-wheel + mobile-header CSS regressions (U2/U3), WhatsApp-send flips devis→envoyé via a NEW `core.events.devis_sent` event (U4), surface generated factures/BC in the devis list + BC-state warning (U5/U8), hide/badge superseded devis revisions (U7), auto-create chantier on devis acceptance via the `devis_accepted` bus (U6), stock reservation on the direct generer-facture path (U9), relance-escalation reset on full payment (U10), phantom-signé flag on post-acceptance refusal (U11, flag-only), direct nullable lead FK on Facture/BonCommande (U12), avatar same-origin proxy fix (U13), GED « Documents » write UI + `documents/televerser/` upload (U14) — additive, multi-tenant, tested; ADDITIVE migrations ventes/0027_devis_date_envoi + 0028_boncommande_lead_facture_lead. + 2026-06-24 PLAN.md batch-1 drain (8 parallel worktree lanes off the FG/module wave plan, adversarial review + local CI incl. makemigrations-check & full affected test run, one self-merge): 7 shipped — FG52 (ventes multi-currency `devise`/`taux_change` + CompanyProfile default), FG166 (rh `Pointage` clock-in/out), CONTRAT6 (contrats `confidentialite` gated on `menu_tier`), FLOTTE5 (flotte `ActifFlotte` unified asset ref), PAIE13 (paie multi-profile base-salary + proration), GED14 (ged inline `apercu` preview), PROJ14 (gestion_projet delay detection). ADDITIVE migrations ventes/0029 + parametres/0025, rh/0008, contrats/0005, flotte/0005, paie/0006. **FG131 (compta 3-way match) DEFERRED/backed-out** — the build duplicated stock's BonCommandeFournisseur/FactureFournisseur (reverse-accessor clash); needs a rebuild reusing stock procurement via selectors/services (left `[ ]`). + 2026-06-27 `claude/lucid-banzai-33af1c` PLAN.md wave-1 drain (5 parallel worktree lanes, one self-merge): PAIE14 (paie heures-sup majorées 25/50/100 %), FG167 (rh `FeuilleTemps` timesheets + labour-hours selector), CONTRAT7 (contrats `ModeleContrat` + `/instancier/`), FLOTTE7 (flotte `Conducteur` + permis), QHSE16 (qhse `Audit`/`ReponseCritere` + score → NCR) — all additive, multi-tenant, tested; ADDITIVE migrations paie/0007, rh/0009, contrats/0006, flotte/0006, qhse/0010. No new external/paid dependency, no auth change. Validated on the docker CI harness (511 affected-app tests green, makemigrations --check clean). + 2026-06-27 same run waves 2+3 (9 more file-disjoint lanes): GED15 (ged document version history + restore, `restored_from` audit), PROJ15 (gestion_projet `RessourceProfil`/`Equipe`, internal cout_horaire), FG39 (crm `ObjectifCommercial` + attainment selector, backend), FG5 (notifications `WorkingHoursConfig`/`Holiday` + calendar helpers + `seed_ma_holidays`, opt-in), FG86 (sav `Ticket.share_token` + public read-only tracking endpoint, allowlist no cout/chatter), KB5 (kb `seed_kb_templates` 5 SOP/ONEE/82-21 gabarits), FG96 (reporting `DashboardConfig` per-user/role, backend), FG102 (publicapi webhook deliveries history + replay + test, backend), FG297 (installations `DocumentProjet`/`RevisionDocument` versioned project-doc register) — all additive, multi-tenant, tested; ADDITIVE migrations ged/0008, gestion_projet/0010, crm/0028, notifications/0010, sav/0009, reporting/0003, installations/0014 (KB5/FG102 need none); import-linter stays 4/4. No new external/paid dependency, no auth change. + 2026-06-29 `claude/relaxed-edison-c91f99` PLAN.md wave-1 drain (8 parallel file-disjoint worktree lanes, adversarial review + local docker CI, one self-merge): FG135 (compta `NoteFrais` notes de frais + remboursements, justificatif photo, écritures équilibrées, verrou de période, réf NDF race-safe), FG291 (installations `Projet` programme multi-chantiers regroupant chantiers/devis/tickets par FK chaînes, machine d'états propre — NEW arch component), FG255 (ventes `ev_charger_sizing` borne VE couplée au PV, math pure), FG361 (core `forecast.py` prévision CA/devis mensuels, Holt-Winters statsmodels + repli pur Python), FG172 (rh `Competence`/`CompetenceEmploye` matrice de compétences), CONTRAT13 (contrats `RegleApprobation` par montant/type + résolveur), FLOTTE13 (flotte conso L/100 km & kWh/100 km depuis pleins+odomètre, endpoint scopé), GED17 (ged `Document.statut` cycle de vie brouillon→…→obsolète, machine d'états gardée, distinct de STAGES.py) — all additive, multi-tenant, tested; ADDITIVE migrations compta/0011, installations/0016, rh/0014, contrats/0010, ged/0011 (FG255/FG361/FLOTTE13 need none). **NEW external dependency `statsmodels==0.14.4`** (FG361, import défensif + repli si absente). Adversarial review fixed 2 CI-red issues pre-merge (FG361 garde NaN avant clamp, FLOTTE13 action `consommation` en lecture tout rôle) + an FG135 reference race; core stays a foundation layer (import-linter 4/4). + 2026-06-29 `claude/relaxed-edison-c91f99` PLAN.md wave-2 drain (8 parallel file-disjoint worktree lanes, adversarial review + local docker CI): FG136 (compta `BaremeIndemnite`+`IndemniteChantier` indemnités km/per-diem, haversine, écritures équilibrées + verrou de période), FG292 (installations `ProjetTache` tâches/sous-tâches + prédécesseur avec gardes anti-cycle — étend l'ARCH Projet FG291), FG256 (ventes `battery_storage_sizing` autoconso-max vs backup-heures, math pure), FG362 (core `win_probability.py` scorer pur fondation + `reporting/pipeline.py` pondéré par lead, repli statique), FG173 (rh `Habilitation` électriques NF C 18-510 + expiry), CONTRAT14 (contrats `EtapeApprobation` workflow depuis `RegleApprobation`, ne touche pas `Contrat.statut`), FLOTTE14 (flotte `CarteCarburant` + détecteur d'anomalies pleins), QHSE19 (qhse `RetourClientQualite` satisfaction 1–5) — all additive, multi-tenant, tested; ADDITIVE migrations compta/0012, installations/0017, rh/0015, contrats/0011, flotte/0012, qhse/0013 (FG256/FG362 need none). No new external/paid dependency, no auth change; import-linter 4/4 (core reste fondation). Fixed an FG136 constraint Q-order migration drift pre-merge (makemigrations --check clean). + 2026-06-29 `claude/relaxed-edison-c91f99` PLAN.md wave-3 drain (8 parallel file-disjoint worktree lanes, adversarial review + local docker CI incl. the 8 wave-3 test modules run green before push): FG137 (compta `DeclarationTVA` préparation TVA collectée−déductible par régime/méthode + export), FG294 (installations `BudgetProjet`/`BudgetEngagement` budget vs réel agrégé cross-app via get_model/selectors, alerte dépassement — ARCH), FG257 (ventes `simulate_bankable_yield` P50/P90 + Performance Ratio, math pure), FG363 (core `churn_risk.py` scorer pur fondation), FG174 (rh `Certification` non-électriques + expiry), CONTRAT15 (contrats `ContratActivity` chatter/journal des transitions), FLOTTE15 (flotte `PlanEntretien` entretien préventif km/date/heures via ActifFlotte), GED18 (ged `DemandeApprobation` workflow réutilisant la machine d'états GED17) — all additive, multi-tenant, tested; ADDITIVE migrations compta/0013, installations/0018, rh/0016, contrats/0012, flotte/0013, ged/0012 (FG257/FG363 need none). No new external/paid dependency, no auth change; import-linter 4/4 (core reste fondation, FG363 stdlib-only). No migration drift. + 2026-06-29 `claude/relaxed-edison-c91f99` PLAN.md wave-4 drain (8 parallel file-disjoint worktree lanes, adversarial review + local docker CI of the 8 wave-4 test modules before push — **ZERO migrations this wave**, all aggregation/pure-math/helper tasks): FG138 (compta `releve_deductions_tva` annexe TVA déductible depuis le GL, réconcilie FG137), FG295 (installations `projet_pnl` P&L consolidé revenu−coûts par Projet, réutilise les agrégats cross-app FG294), FG258 (ventes `hourly_self_consumption` profil autoconso 8760 h + parser xlsx openpyxl déjà présent), FG364 (core `stock_reorder.py` prévision rupture/réappro, stdlib seul), FG175 (rh `echeances_rh` moteur d'alertes d'expiration unifié + commande notifiant via `notifications.notify`), PROJ18 (gestion_projet `plan_de_charge` capacité vs affecté), PAIE20 (paie helper `cimr_salariale` CIMR optionnelle par employé, champs préexistants), QHSE20 (qhse `iso9001_readiness` tableau de bord) — all additive, multi-tenant, tested; NO migrations; no new external/paid dependency, no auth change; import-linter 4/4 (core reste fondation). No migration drift. + 2026-06-29 `claude/relaxed-edison-c91f99` PLAN.md wave-5 drain (8 parallel file-disjoint worktree lanes, adversarial review + local docker CI of the 8 wave-5 test modules before push): FG139 (compta `RetenueSource` RAS retenue à la source + bordereau de versement, export `?export=csv`), FG299 (installations `plan_de_charge_equipes` capacité vs affecté des techniciens/équipes sur interventions), FG259 (ventes `net_metering_savings` valorisation surplus injecté par tranche loi 13-09), FG365 (core `payment_delay.py` prédiction de retard de paiement, stdlib seul), FG176 (rh `verifier_habilitation_requise` garde d'affectation par habilitation, blocage doux), CONTRAT16 (contrats `SignatureContrat` e-sign in-app loi 53-05, preuve serveur, bascule statut signé), FLOTTE16 (flotte `EcheanceEntretien` génération idempotente d'échéances dues + alertes), GED19 (ged `AclGed` ACL par dossier/document héritage+override, rétrocompatible) — all additive, multi-tenant, tested; ADDITIVE migrations compta/0014, contrats/0013, flotte/0014, ged/0013 (FG299/FG259/FG365/FG176 need none). No new external/paid dependency, no auth change; import-linter 4/4. Fixed a GED19 CheckConstraint `condition=` migration drift pre-merge (Django 5.1 deconstruction; Meta.constraints aligned with the migration, makemigrations --check clean). + 2026-06-29 `claude/relaxed-edison-c91f99` PLAN.md wave-6 drain (8 parallel file-disjoint worktree lanes, adversarial review + local docker CI of the 8 wave-6 test modules before push): FG140 (compta aide au calcul de l'IS — barème progressif + cotisation minimale + 4 acomptes + régularisation, selectors-only), FG300 (installations `conflits_affectation` double-booking technicien/camionnette même jour), FG260 (ventes `tariff_escalation_projection` escalade ONEE 20-25 ans + VAN/TRI stdlib), **FG366 (core moteur de workflow BPM générique `WorkflowDefinition/StepDefinition/Instance/StepInstance` cible générique contenttypes + SLA/escalades — NEW ARCH component dans la fondation, import-linter 4/4)**, FG177 (rh `VisiteMedicale` du travail + aptitude + expiry, alimente FG175), PROJ19 (gestion_projet `conflits_affectation` ressources chevauchantes), PAIE21 (paie frais professionnels — déjà présent, tests ajoutés), QHSE21 (qhse `EvaluationRisque`/`LigneEvaluationRisque` document unique, criticité=gravité×probabilité) — all additive, multi-tenant, tested; ADDITIVE migrations core/0002 (BPM), rh/0017, qhse/0014 (FG140/FG300/FG260/PROJ19/PAIE21 need none). No migration drift; no new external/paid dependency, no auth change; import-linter 4/4 (core reste fondation). + 2026-06-29 `claude/relaxed-edison-c91f99` PLAN.md wave-7 drain (8 parallel file-disjoint worktree lanes, adversarial review + local docker CI of 9 wave-7 test modules before push): FG141 (compta `export_fec` export FEC DGI 18 colonnes, `?export=fec`), FG301 (installations `nivellement_charge` rééquilibrage des interventions surchargées sans conflit, lecture seule), FG261 (ventes `optimize_subscribed_power` réduction puissance souscrite post-PV C&I), FG367 (core `rules.py` évaluateur de conditions ET/OU/NON + actions séquentielles, pur fondation), FG178 (rh `EpiCatalogue`/`DotationEpi` dotation EPI nominative), CONTRAT17 (contrats auto signé→actif sur signature), FLOTTE17 (flotte `Garage`/`OrdreReparation` ordres de réparation + coûts), GED20 (ged `PartageGed` partage tokenisé public expiry/password/quota) — all additive, multi-tenant, tested; ADDITIVE migrations rh/0018, flotte/0015, ged/0014 (FG141/FG301/FG261/FG367/CONTRAT17 need none). No migration drift; no new external/paid dependency, no auth change; import-linter 4/4 (core reste fondation). GED20 introduces a PUBLIC AllowAny tokenized document endpoint (token-only resolution, expiry/quota/password-hash, no cross-tenant leak — security model calqué sur ventes.ShareLink). + 2026-06-29 `claude/relaxed-edison-c91f99` PLAN.md wave-8 drain (8 parallel file-disjoint worktree lanes, adversarial review + local docker CI of 8 wave-8 test modules before push): FG142 (compta `liasse_fiscale` trousse liasse fiscale bilan+CPC+balance+annexe-TVA, réutilise les sélecteurs), FG302 (installations `IndisponibiliteRessource` calendrier de disponibilité technicien/camionnette + sélecteur d'exclusion), FG262 (ventes `module_degradation_curve` dégradation modules + planchers de garantie), FG368 (core `core/jobs.py` + `ScheduledJobViewSet` liste/exécution des jobs Celery Beat, admin, câblé `/api/django/core/`), FG179 (rh péremption/contrôle EPI dérivés + alertes, alimente FG175), PROJ20 (gestion_projet `nivellement_charge` rééquilibrage ressources projet), PAIE22 (paie calcul IR — déjà présent PAIE5, 30 tests ajoutés), QHSE22 (qhse `document_unique_valide`/`exiger_document_unique` gate document unique avant pose) — all additive, multi-tenant, tested; ADDITIVE migrations installations/0019, rh/0019 (FG142/FG262/FG368/PROJ20/PAIE22/QHSE22 need none). FG368 added a root-URLConf line (`api/django/core/` → `core.urls`, orchestrator wiring step). No migration drift; no new external/paid dependency, no auth change; import-linter 4/4 (core reste fondation, jobs via celery infra). Wave-9 PLAN.md drain (2026-06-29, 8 parallel file-disjoint worktree lanes): rh `EmargementEpi` (FG180), contrats `VersionContrat` (CONTRAT18), flotte `Pneumatique`/`PieceFlotte` (FLOTTE18), ged watermarking flags `Document.watermark_diffusion`/`PartageGed.watermark` (GED21, lazy PyMuPDF/Pillow — no hard dep), core workflow-template library + `/api/django/core/` workflow-templates route (FG369), plus selector/endpoint-only FG143 (compta état 9421), FG303 (installations van planning), FG263 (ventes PPA model) — all additive & company-scoped, 4 additive migrations (rh 0020, contrats 0014, flotte 0016, ged 0015). Wave-10 PLAN.md drain (2026-06-29, 7 parallel file-disjoint worktree lanes in apps disjoint from wave 9): crm `ConcurrentPerte` (lost-deal competitor capture FG242), gestion_projet `BudgetProjet`/`LigneBudgetProjet` (PROJ21), qhse `PermisTravail` (QHSE23), kb `KbArticleAcl`/`KbLecture` (role ACL + read tracking KB7), sav `AlarmeOnduleur` (inverter alarms FG280), plus paie allocations-familiales employer charge (PAIE23, fields on ParametrePaie/BulletinPaie) and selector-only LITIGE6 (disputes dashboard) — all additive & company-scoped, 6 additive migrations (crm 0029, gestion_projet 0013, kb 0005, paie 0011, qhse 0015, sav 0011). Wave-11 PLAN.md drain (2026-06-29, 6 parallel file-disjoint worktree lanes resuming wave-9 app lanes off the merged base): compta `TimbreFiscal` (droit de timbre cash FG144), rh `AccidentTravail` (HSE/accidents register FG181), installations `SousTraitant` (subcontractor registry FG304), ged `PolitiqueRetention` (non-destructive retention policies GED22), flotte `EcheanceReglementaire` (regulatory deadlines FLOTTE19), plus pure-math FG264 (ventes pumping-cycle water yield) — all additive & company-scoped, 5 additive migrations (compta 0015, rh 0021, installations 0020, ged 0016, flotte 0017). Wave-12 PLAN.md drain (2026-06-29, 3 parallel file-disjoint lanes resuming wave-10 app lanes): qhse `ConsignationLoto` (LOTO on a work permit QHSE24), crm `PointContact` (multi-touch attribution journal FG204), plus paie taxe de formation professionnelle employer charge (PAIE24, BulletinPaie snapshot) — all additive & company-scoped, 3 additive migrations (paie 0012, qhse 0016, crm 0030). Wave-13 PLAN.md drain (2026-06-30, 6 parallel file-disjoint worktree lanes resuming wave-9 app lanes): compta `RetenueGarantie`/`CautionBancaire` (FG145), rh `PresquAccident` (near-miss FG182), installations `OrdreSousTraitance` (subcontractor work orders FG305), ged `ArchivageLegal` (legal write-once GED23), flotte `BaremeVignette` + `Vehicule.puissance_fiscale` (TSAV FLOTTE20), plus selector-only PROJ22 (committed-vs-actual project cost) — all additive & company-scoped, 5 additive migrations (compta 0016, rh 0022, installations 0021, ged 0017, flotte 0018).
Structure fingerprint: dbc9de58cc21717ae6235d3685e72fb9ce4f0a820914fead7eccc14b2b082d27
Plan fingerprint: 9f5218d50e2b066224c44c469f2fd3fc231d565ff1552a9f8f11990dbf4456c7

> This file is **regenerated by the build pipeline**. It is derived by reading the
> actual source (models, urls, serializers, settings, docker-compose, requirements,
> package.json, the CI workflow, frontend feature folders) — never from prose docs,
> which are known to drift. Where prose and code disagree, the code wins and the
> gap is logged in §9. Treat the commit hash above as the provenance: anything
> merged after it may not be reflected yet.

---

## Table of contents

1. [System overview](#1-system-overview)
2. [Verified stack](#2-verified-stack)
3. [Repository map](#3-repository-map)
4. [Backend, app by app](#4-backend-app-by-app)
5. [Frontend, feature by feature](#5-frontend-feature-by-feature)
6. [Core data flow (one record, end to end)](#6-core-data-flow-one-record-end-to-end)
7. [Hard contracts and policies](#7-hard-contracts-and-policies)
8. [Known discrepancies (prose vs code)](#8-known-discrepancies-prose-vs-code)
9. [Staleness markers](#9-staleness-markers)
10. [Plan status](#10-plan-status)

---

## 1. System overview

TAQINOR OS is a multi-tenant ERP for a Moroccan solar installer. A browser loads a
**React/Vite single-page app** (`frontend/`). All traffic enters through **nginx**
(ports 80/443), which reverse-proxies three upstreams: the SPA static bundle, the
**Django REST API** (`backend/django_core`, served by gunicorn on :8000), and a
**FastAPI AI/OCR service** (`backend/fastapi_ia`, uvicorn on :8001). The SPA calls
the Django API under the prefix `/api/django/…` and the AI service under
`/api/fastapi/…`. Django persists everything to **PostgreSQL 16 (pgvector)** and
uses **Redis** as cache plus Celery broker; a **Celery worker** (same Django image)
runs async jobs such as quote-PDF generation. Generated PDFs and uploads live in
**MinIO** (S3-compatible object storage, buckets `erp-pdf` and `erp-uploads`).
Authentication is cookie-based JWT (httpOnly refresh cookie); every API request is
scoped to the caller's `company` (the tenant). The FastAPI service shares the same
Postgres for its OCR (Zhipu) and natural-language-SQL-agent (LangChain) features,
both JWT-protected and key-gated.

```
            ┌──────────────┐
  Browser → │    nginx     │  :80 / :443  (+127.0.0.1:8090 lead webhook listener)
            └──────┬───────┘
        ┌──────────┼───────────────┬───────────────────┐
        ▼          ▼               ▼                   ▼
   frontend   django_core      fastapi_ia          (static SPA)
   (Vite SPA) gunicorn :8000   uvicorn :8001
   /api/django/*               /api/fastapi/*
        │          │               │
        │          ▼               ▼
        │     PostgreSQL 16 (pgvector)  ◄── shared DB
        │          │
        │          ├── Redis  (cache + Celery broker)
        │          ├── Celery worker (async PDFs, same Django image)
        │          └── MinIO  (erp-pdf, erp-uploads)
```

Request flow, front to back: SPA dispatches a Redux thunk → axios `GET/POST
/api/django/<app>/…` with the JWT cookie → nginx → gunicorn/Django → DRF ViewSet
(queryset filtered to `request.user.company`) → Postgres → JSON back. Quote PDFs
are the exception: the ViewSet hands off to the vendored premium engine (sync via
`/proposal`, or async via Celery) which renders with WeasyPrint and stores the file
in MinIO.

---

## 2. Verified stack

Versions below are the **pinned** values found in `requirements.txt`,
`package.json`, and `docker-compose.yml`. Items not pinned anywhere are marked
**unconfirmed**.

### Backend — Django API (`backend/django_core/requirements.txt`)
- Python **3.12** (CI runner; not pinned in repo otherwise)
- Django **5.1.4**, djangorestframework **3.15.2**, djangorestframework-simplejwt **5.3.1**, django-cors-headers **4.6.0**
- psycopg2-binary **2.9.10**, pgvector **0.3.6**
- redis **5.2.1**, django-redis **5.4.0**, celery **5.4.0**
- weasyprint **62.3**, pydyf **0.11.0**, Jinja2 **3.1.5** (PDF rendering)
- numpy **1.26.4**, matplotlib **3.9.2** (premium quote-PDF charts)
- segno **1.6.6** (scan-to-sign QR on the residential quote PDF; imported defensively)
- django-anymail[sendgrid] **10.3** (email), django-storages[s3] **1.14.4**, boto3 **1.35.99** (MinIO/S3)
- openpyxl **3.1.5** (.xlsx export), Pillow **10.4.0**, httpx **0.28.1**
- gunicorn **22.0.0** (WSGI server; 4 sync workers per compose)

### Backend — FastAPI AI service (`backend/fastapi_ia/requirements.txt`)
- fastapi **0.115.6**, uvicorn[standard] **0.34.0**, pydantic **2.10.4**, python-multipart **0.0.20**, PyJWT **2.10.1**
- sqlalchemy **2.0.36**, psycopg2-binary **2.9.10**, pgvector **0.3.6**, redis **5.2.1**
- langchain **0.3.14**, langchain-community **0.3.14**, langchain-groq **0.2.3**, langchain-openai **0.2.14**, langchain-anthropic **0.3.3**, openai **1.59.6**, sentence-transformers **>=2.0,<4.0**
- pypdf **>=4.0,<6.0**, Pillow **>=10.0,<12.0**, pymupdf **>=1.23,<2.0** (OCR utilities)
- OCR provider = **Zhipu AI / GLM vision**, key-gated by `ZHIPU_API_KEY` — called over HTTP, **not a pinned SDK** in requirements (unconfirmed which client).

### Frontend (`frontend/package.json`)
- Node **22** (CI runner)
- React **19.2.5**, react-dom **19.2.5**, react-router-dom **7.14.2**
- @reduxjs/toolkit **2.11.2**, react-redux **9.2.0**
- axios **1.15.2**, pdfjs-dist **6.0.227**, recharts **2.15.3**, @dnd-kit/core **6.3.1**
- Build/tooling: vite **8.0.9**, @vitejs/plugin-react **6.0.1**, tailwindcss **4.2.4**, @tailwindcss/vite **4.2.4**, eslint **9.39.4**, vite-plugin-pwa **1.3.0**

### Datastores & infra (`docker-compose.yml`)
- PostgreSQL **16** with pgvector — image `pgvector/pgvector:pg16`
- Redis **7.4-alpine**
- MinIO — image `minio/minio:RELEASE.2025-01-20T14-49-07Z` (CI uses `minio/minio:latest`)
- nginx (reverse proxy, custom build at `backend/nginx`)
- Django project package: **`erp_agentique`** (settings module `erp_agentique.settings.dev` in CI/compose)

---

## 3. Repository map

Vendored/generated dirs (`.venv_test`, `node_modules`, `migrations`,
`quote_engine/assets`, build output) are skipped.

```
taqinor-os/
├── STAGES.py                     Canonical pipeline stages — single source of truth (rule #2)
├── CLAUDE.md                     Founder's enforced rules (overrides assistant defaults)
├── docker-compose.yml            Local full stack (nginx, django, fastapi, celery, db, minio, redis)
├── docker-compose.prod.yml       Production compose
├── scripts/check_stages.py       CI guard: fails if any stage list diverges from STAGES.py
├── scripts/codemap_fingerprint.py CI guard: fails if this CODEMAP is stale vs the structural surface
├── .github/workflows/ci.yml      CI: changes(detector) + backend-lint, backend-tests, frontend-lint, stage-names, web-build-test, e2e + ci-gate(aggregate); per-job path filtering (infra/docs/config → stage-names only); push on main/dev only + all PRs (PR concurrency-cancel)
├── apps/web/                     Marketing website (Astro, deploys via Cloudflare) — separate autopilot scope
├── docs/                         PLAN.md, WEB_PLAN.md, this CODEMAP.md, swap maps
│
├── backend/
│   ├── django_core/              Django REST API (project: erp_agentique)
│   │   ├── authentication/         Tenant root: Company + CustomUser, JWT, registration  (NOT under apps/)
│   │   └── apps/
│   │       ├── crm/                Leads (sales funnel) + Clients + chatter + channels/tags/loss-reasons
│   │       ├── ventes/             Quotes (devis), orders (BC), invoices (factures), credit notes, payments, quote_engine
│   │       ├── stock/              Product catalogue, suppliers, movements, locations, supplier POs/returns
│   │       ├── installations/      Chantiers (installation projects), interventions, checklists, field execution
│   │       ├── sav/                After-sales: equipment registry, SAV tickets, maintenance contracts
│   │       ├── reporting/          Dashboards/KPIs/insights/audit-log (read-only; no models of its own)
│   │       ├── parametres/         Company profile + business settings + WhatsApp templates + settings audit
│   │       ├── roles/              RBAC: per-company roles + permission lists
│   │       ├── records/            Generic activities + file attachments (ContentType-based, cross-module)
│   │       ├── customfields/       Admin-defined custom fields for Lead/Client/Produit (values in custom_data)
│   │       ├── documents/          Field-execution PDFs (PV réception, bon de livraison, attestation) — no models
│   │       ├── dataimport/         Two-step CSV/XLSX import (dry-run + commit) for leads/clients/products — no models
│   │       └── contact/            Public landing-page contact form (parked by default) — no models
│   │
│   ├── fastapi_ia/               FastAPI AI service (root_path /api/fastapi)
│   │   └── app/api/endpoints/      ocr.py (Zhipu OCR), sql_agent.py (LangChain NL→SQL)
│   └── nginx/                    Reverse-proxy config
│
└── frontend/                     React/Vite SPA
    └── src/
        ├── router/                 Route table (path → page component)
        ├── pages/                  Page components grouped by area (crm, ventes, stock, sav, …)
        ├── features/               Redux slices + domain logic per area (see §5)
        ├── api/                    axios modules, one per backend area
        ├── components/             Shared UI
        ├── hooks/ store/ utils/    Cross-cutting React/Redux helpers
        └── sw.js                   PWA service worker (auto-update)
```

---

## 4. Backend, app by app

All multi-tenant models carry a `company` FK → `authentication.Company`. ViewSets
filter `get_queryset()` by `request.user.company` and force-assign `company` in
`perform_create` (never read from the request body). The literal tenant field is
**`company`** — there is no field named `tenant_id`.

API prefixes (from `erp_agentique/urls.py`, all under `/api/django/`):
`authentication` → root, `stock/`, `crm/`, `ventes/`, `parametres/`, `roles/`,
`reporting/`, `contact/`, `installations/`, `sav/`, `records/`, `imports/`
(dataimport), `custom-fields/`, `documents/`, `public/` (tokenized PDFs, no login).
JWT lives at `token/`, `token/refresh/`, `token/verify/`.

### authentication — tenant root, users, JWT  *(path: `backend/django_core/authentication`, NOT under apps/)*
Owns the tenant (`Company`), the user model, registration, and JWT issuance.
- **Company** — `nom`, `slug` (unique), `actif` (bool), `date_creation`. The tenant every other model points at.
- **CustomUser** (extends AbstractUser) — `company` FK→Company; `role` FK→roles.Role (nullable); `role_legacy` (deprecated CharField admin/responsable/normal, now kept in sync with `role`'s tier on create/update + a one-off additive data backfill); derived `menu_tier` property = the **authoritative** menu tier read from the *new* Role (Administrateur→admin, Responsable→responsable, Utilisateur/custom→normal; superuser→admin; legacy fallback only when role-less), exposed on `/auth/me/` and the JWT and used by the sidebar; `tier_for_role` + the pure `authentication/role_tiers.py` are the single source of truth; `poste`, `phone_number`, `avatar_key` (MinIO); `is_protected` (owner-account guard), `is_active`, `is_superuser`; **`supervisor`** self-FK (nullable, Feature E) driving team/subtree record-visibility. Record-visibility scoping lives in `authentication/scoping.py` (`record_scope_for`, `visible_user_ids`, `scope_queryset`) and is applied opt-in on the list+detail querysets of crm/ventes/installations/sav (only the new scoped roles narrow; admins/legacy/custom roles see all; users always keep their own records). Buy prices gated by `can_view_buy_prices` (`prix_achat_voir`).
- Endpoints (mounted at `/api/django/`): `POST /auth/register-company/` (public onboarding: new company + admin) · `POST /register/` (admin adds user to own company) · `GET /auth/me/` · `POST /auth/logout/` · `POST /auth/token/refresh/` · `GET/POST/PATCH/DELETE /users/…` + `POST /users/{id}/avatar/` (Administrateur + Responsable tier — `IsAdminOrResponsableTier`, limited tier blocked) · `GET/POST/PATCH/DELETE /companies/…` (superuser).

### crm — sales funnel + clients
Leads from creation through funnel stages, client records, Odoo-style chatter,
duplicate detection/merge, reversible archive.
- **Client** — `company` FK; `type_client` (PARTICULIER/ENTREPRISE); `nom/prenom`, `email` (optional), `telephone`, `adresse`; Moroccan IDs `cin/ice/if_fiscal/rc`; `custom_data` JSON. Unique `(company, email)` when email set.
- **Lead** — `company` FK; `client` FK→Client (nullable); `owner` FK→CustomUser; `stage` (**STAGES.py keys**: NEW/CONTACTED/QUOTE_SENT/FOLLOW_UP/SIGNED/COLD, default NEW); `perdu` (bool lost-flag) + `motif_perte`; `canal` (META_ADS/WHATSAPP_CTWA/SITE_WEB/REFERENCE/TELEPHONE/WALK_IN/AUTRE); `priorite`, `tags`, `relance_date`; `type_installation` (RESIDENTIEL/COMMERCIAL/INDUSTRIEL/AGRICOLE); energy profile (`facture_hiver/ete`, `ete_differente` bool, `regularisation_8221` bool); roof/site + pump fields; `source` (OS_NATIVE/ODOO_IMPORT_TEST/SITE_WEB); `is_archived` (bool) + `archived_by/at`; `custom_data` JSON.
- **LeadActivity** — `lead` FK; `kind` (CREATION/MODIFICATION/NOTE); field-change log (`field/old_value/new_value`) or manual `body`; `user` FK; `bulk` bool.
- **LeadTag / Canal / MotifPerte** — per-company managed lists for tags, channels, loss reasons (each has `archived` bool; Canal has `protege`).
- **WebsiteLeadPayload** — raw webhook capture from taqinor.ma; `payload` JSON, `processed` bool, `lead` FK (never loses inbound data).
- **Parrainage** (referral program, N98) — `company` FK; `parrain` FK→Client (the referrer); `filleul_lead` FK→Lead and/or `filleul_client` FK→Client (the referred) + free-text `filleul_nom`; `statut` (en_attente/converti/recompense_versee); `recompense` (Decimal, pre-filled from `parametres.CompanyProfile.referral_reward`); `notes`; `created_by`. Feature on/off via `CompanyProfile.referral_enabled`.
- Endpoints (`/api/django/crm/`): `clients/` and `leads/` ViewSets (CRUD) plus `leads/{id}/archiver|restaurer|whatsapp-devis|devis-auto|noter|merge|bulk`, `leads/{id}/duplicates`, `leads/doublons`, `leads/historique`, `leads/export-xlsx`, `clients/export-xlsx`; managed-list ViewSets `tags/`, `canaux/`, `motifs-perte/`; `parrainages/` (referrals); `assignable-users/`; `POST webhooks/website-leads/` (public, static secret).
- **management/import_odoo_leads** (N107) — `manage.py import_odoo_leads <path> --company <slug|id> [--dry-run]`: idempotent Odoo `crm.lead` importer reusing the `dataimport` parser (CSV/XLSX) + JSON; forces company server-side, reconciles on normalized email/phone + the existing `(company, external_system, external_id)` unique key (never duplicates), stage names from STAGES.py (unknown → NEW). No-op without a file. The real 619-lead extraction stays manual/gated on the actual Odoo backup (PII, never committed). **FG242** adds **ConcurrentPerte** — on a LOST lead, captures the winning competitor + price/devise/motif (reuses the existing `Lead.perdu` flag, no hardcoded STAGES.py stage); acting user + company server-side, optional LeadActivity chatter note; ViewSet `concurrents-perte/` (`?lead=`). Migration crm/0029. **FG204** adds **PointContact** — a per-lead multi-touch attribution journal (canal reusing `Lead.Canal`, source, date, ordre, optional paid-channel cost) with a timeline + first/last-touch summary selector; endpoints `points-contact/` (+ `attribution/`) and a `leads/{id}/points-contact/` read action. Migration crm/0030.

### ventes — quotes, orders, invoices, credit notes, payments, quote engine
The largest app: full quote→order→invoice→recovery lifecycle plus the vendored
premium quote-PDF engine.
- **Devis** (quote) — `company` FK; `reference` (per company+month); `client` FK→crm.Client; `lead` FK→crm.Lead (nullable, lead-primary quoting); `statut` (**brouillon/envoye/accepte/refuse/expire**); `mode_installation` (residentiel/industriel/agricole); `option_acceptee` (sans_batterie/avec_batterie); `etude_params` JSON (kWc, production, autoconso, payback, pump CV/HMT/débit…); `taux_tva`, `remise_globale`; versioning (`version`, `version_parent`, `superseded_by`, `is_active`); discount approval (`remise_approuvee`, `remise_approuvee_par`); `fichier_pdf` (MinIO key). **FG52** adds `devise` (ISO 4217, default MAD) + `taux_change` to **Devis** and **Facture** (and `parametres.CompanyProfile.devise_defaut`): on API create without an explicit devise, the company default is applied (fallback MAD); the premium PDF `fmt()` and UBL export (`dgi_export.py`/`utils/ubl.py`) emit the document currency. No base-currency conversion (currency is document-borne).
- **LigneDevis** — `devis` FK, `produit` FK→stock.Produit, `designation`, `quantite`, `prix_unitaire`, `remise`, `taux_tva` (nullable → falls back to devis rate; 10% panels / 20% other).
- **BonCommande** (client order) — `devis` OneToOne→Devis (nullable), `client` FK; `statut` (**en_attente/confirme/livre/annule**); marking `livre` decrements stock.
- **Facture** (invoice) — `devis` FK (new échéancier path) **and/or** `bon_commande` OneToOne (legacy path); `client` FK; `type_facture` (**acompte/intermediaire/solde/complete**); `statut` (**brouillon/emise/payee/en_retard/annulee**); `pourcentage`, `libelle`, frozen `montant_ht/tva/ttc`; recovery (`prochaine_relance`, `exclu_relances`); computed `montant_paye`, `avoirs_total`, `montant_du` (= TTC − paid − credits); `fichier_pdf/ubl`.
- **LigneFacture** — same shape as LigneDevis (`facture` FK).
- **Paiement** — `facture` FK; `montant`, `date_paiement`, `mode` (especes/virement/cheque/carte/prelevement/autre).
- **Avoir** (credit note) + **LigneAvoir** — `facture` FK (PROTECT), `client` FK; `statut` (emise/annulee); `motif`; frozen amounts; offsets the invoice's `montant_du`.
- **DevisActivity** — quote chatter (CREATION/MODIFICATION/NOTE), like LeadActivity.
- **FollowupLevel / RelanceLog** — recovery escalation tiers and per-invoice follow-up trace.
- **ShareLink** — public tokenized link (`token` unique, `devis`/`facture` FK, `expires_at`, 30-day) for WhatsApp PDF delivery without login.
- Endpoints (`/api/django/ventes/`): `devis/`, `devis-lignes/`, `bons-commande/`, `factures/`, `paiements/`, `avoirs/` ViewSets; key custom actions: `devis/{id}/proposal/` (**canonical quote PDF, sync**), `devis/{id}/generer-pdf/` (**async Celery**), `devis/{id}/telecharger-pdf`, `devis/{id}/accepter|reviser|approuver-remise|historique|noter`, `devis/{id}/convertir-bc`, `devis/{id}/generer-facture`; `bons-commande/{id}/confirmer|marquer-livre|annuler|creer-facture`; recovery (`relances/`, `balance-agee/`, `clients/{id}/releve(-pdf)/`, `factures/{id}/lettre-relance-pdf/`, `niveaux-relance/`); accounting (`journal-ventes/` .xlsx, `numerotation-audit/`); public `GET /api/django/public/document/{token}/` (tokenized PDF, no auth, no buy prices).
- **Toiture-3D devis web loop** (`/api/django/ventes/`): `devis/from-layout/` (build a Devis from a finalized roofPro11 layout + mint a proposal `ShareLink`), `devis/{id}/layout/` & `devis/{id}/roof-image/` (store the finalized layout + 3D snapshot); public tokenized proposal channel — `GET proposal/{token}/` (JSON quote data incl. `monthly_production`/`monthly_consumption` + `roof_image_url`), `POST proposal/{token}/accept/` (client e-signature → existing accept service), `GET proposal/{token}/pdf/` (client devis PDF). The website capture page (`/devis/mon-toit`) posts the enriched lead (exact bills, `ete_differente`, `raccordement` incl. `inconnu`, reverse-geocoded `adresse`/GPS) to the CRM webhook; **Meriem designs INSIDE the ERP** (authenticated React route `frontend` `/devis-design/:id`, same-origin cookie session — the roofPro11 builder is Vite-alias-imported from `apps/web`, no second login) and the client signs at the public `/proposition/<token>`. `GET /api/django/ventes/roof-config/` exposes the public MapTiler key same-origin (needs `PUBLIC_MAPTILER_KEY` in the ERP env).
- **quote_engine/** — premium PDF engine. `builder.py` maps an OS Devis → the generator data dict (only sell-side `prix_unitaire`; `prix_achat` excluded) and routes by market mode to one of three renderers: `residential/` (redesigned 3-page residential proposal), `agricole/` (4-page pompage-solaire proposal — cover/at-a-glance, étude+schéma+charts, équipement+prix+FDA+garanties, rentabilité solaire-vs-butane-vs-diesel+signature; modules `renderer/render/theme/cover/study/yield_page/economics_page/charts/schematic/economics/constants/sample_data`), and the legacy `generate_devis_premium.py` (one-page + industriel + fallback). `installations.py` = shared cover-hero photo library that picks the installation photo whose kWc is **nearest** the quote (agricole falls back to residential/industriel of similar power); photos in `assets/installations/<mode>-<kwc>.jpg`. `pricing.py`, `catalog.py`. Buy-price exclusion asserted by `apps/ventes/tests/test_quote_engine.py`; agricole engine by `test_agricole_quote.py`.
- **solar_design.py** (FG246/247/249) — electrical-engineering helpers: `string_design` (distributes N panels across the inverter MPPT inputs, checks string Vmp/Voc at cold temperature vs the MPPT/voltage window, reports the DC/AC ratio), `match_inverter` (picks a compatible catalogue inverter, classification keywords aligned with `builder.py`, never a price-less product), `optimize_orientation` (tilt/azimuth sweep via the existing PVGIS client). Pure + fully tested (`tests/test_solar_design.py`); not yet surfaced in an endpoint. **FG255** adds `ev_charger_sizing` — EV charging-station (borne de recharge VE) sizing: line current (mono 230 V / tri 400 V √3), dedicated breaker calibre, charge duration/window-fit, recommended standard borne (3.7/7.4/11/22 kW), and PV coupling (solar surplus feeds the borne first, reporting solar-covered kWh + the lifted autoconsommation rate). Pure math, input-freedom preserved, no model/endpoint/PDF change. **FG256** adds `battery_storage_sizing` — two objectives: MAX autoconsommation (store daytime surplus, capped by the re-dischargeable night load) vs BACKUP for N critical hours (usable kWh/kW from critical load × hours); returns usable + nominal kWh (÷ DoD×√round-trip), recommended pack and the binding objective. Pure math. **FG257** adds `simulate_bankable_yield` — financial-grade P50/P90: Performance Ratio = Π(1−loss) over temperature/soiling/wiring/inverter/mismatch/availability, P50 = base×PR, P90/P75 via the Gaussian lower-tail quantile (z=1.282/0.674) of an annual-variability σ (default 6 %); returns PR, loss breakdown, P50/P90/P75, optional specific yield. Pure math. **FG258** adds `hourly_self_consumption` — per-hour min(load, production) over an 8760-h (or 24-h) load curve → real autoconsommation rate, coverage rate, injected surplus, grid import; typical residential/commercial load + PV profiles as fallbacks, and `load_curve_from_xlsx` (parses a column via the already-present openpyxl). Pure math, divide-by-zero guarded. **FG259** adds `net_metering_savings` — values the injected hourly surplus (from FG258) under Moroccan net-metering (loi 13-09): compensated only up to same-tranche import × `compensation_ratio` at the tranche tariff (pointe/pleine/creuse), honours the `surplus_injecte_compense` toggle, optional annual cap + residual spill tariff. Pure math. **FG260** adds `tariff_escalation_projection` — a 20–25-year financial model: year-by-year escalated savings (ONEE escalation × module degradation), cumulative + net, simple & discounted payback year, **NPV (VAN)** and **IRR (TRI)** solved by stdlib bisection/Newton (capped iterations, `None` on non-convergence). Pure math. **FG261** adds `optimize_subscribed_power` — for C&I clients: net grid demand (load−PV) → post-PV peak → recommended subscribed power = ceil(peak×margin) (never above current) + the annual capacity-charge saving, optional kW→kVA via power factor. Pure math. **FG262** adds `module_degradation_curve` — per-year PV production factor (compound or linear, with a year-1 LID drop) confronted against manufacturer warranty floors (e.g. 90% @ yr10, 80% @ yr25), flagging the first breach year + shortfall. Pure math.
- **utils/references.py** — numbering = highest-used + 1 per company+month (savepoint + retry on races); never `count()+1`.
- **dgi/** (N105, silent DGI capability) — `dgi_export.py` (`build_ubl_xml`, UBL 2.1 invoice via stdlib `xml.etree`, carries seller+client ICE, per-line VAT, totals; no buy price), `dgi_validator.py` (`validate_dgi_conformity` → list of FR problem messages), `toggle.py` (`is_dgi_enabled(company)`). Armed only by `parametres.CompanyProfile.dgi_export_actif` (default **OFF**): the two facture actions `dgi-export`/`dgi-conformite` and the `dgi_export_facture` management command **404/refuse when OFF**, and the Facture model/serializer/lists are byte-identical (no field, badge, status or column added). Simpl-TVA transmission + certified e-signature remain out of scope (G14). **FG263** adds `solar_design.ppa_model(...)` — a PPA / third-party-investor financial model (pure math): applies FG262 degradation, computes investor revenue (production × PPA tariff + escalation − O&M; NPV/IRR/payback reusing FG260) and client savings (grid − PPA tariff), both perspectives. No model; quote-PDF path untouched. **FG264** adds `solar_design.pumping_cycle_yield(...)` — pure-math daily/monthly pumped-water volume by operating cycle (flat mode = byte-parity with `solar.js`; profile mode integrates débit hour-by-hour weighted by a normalized clearsky irradiation profile); curve-less pumps → None. No model; quote-PDF path untouched.

### stock — catalogue, suppliers, inventory, procurement
Product catalogue, multi-supplier sourcing, stock movements/locations, supplier POs
and returns.
- **Produit** — `company` FK; `nom`, `sku` (unique per company); `prix_vente` (sell HT); **`prix_achat`** (buy price — internal/generator-only, **never client-facing**); `quantite_stock` (canonical), `seuil_alerte`; `categorie`/`fournisseur` FK; commercial sheet (`marque`, `description`, `garantie`, `garantie_mois`, `garantie_production_mois`); pump specs (`pompe_cv`, `hmt_m`, `pompe_kw`, `tension_v`, `courbe_pompe` JSON); `is_archived`; `custom_data` JSON.
- **Categorie / Fournisseur / Marque** — referentials (Marque/`archived`).
- N14 (reservation-aware availability): `ProduitSerializer` exposes computed `quantite_reservee`, `quantite_disponible` (= stock − active reservations from `installations.StockReservation`) and a reservation-aware low-stock flag; the legacy `is_low_stock` and `compute_besoin_materiel` are preserved (a chantier's own reservation is not double-counted).
- **MouvementStock** — `produit` FK; `type_mouvement` (entree/sortie/transfert/ajustement); `quantite_avant/apres`; `created_by`; the audit trail for every quantity change.
- **EmplacementStock / StockEmplacement / TransfertStock** — stock locations, per-location quantities (principal derived), and transfers between them.
- **PrixFournisseur** — per-supplier `prix_achat` (internal) for cheapest-sourcing.
- **BonCommandeFournisseur** + **LigneBonCommandeFournisseur** — supplier purchase orders; `statut` (brouillon/envoye/recu/annule); receipt increments stock via MouvementStock.
- **RetourFournisseur** + **LigneRetourFournisseur** — supplier returns; `statut` (brouillon/valide/annule); validation decrements stock.
- Endpoints (`/api/django/stock/`): `produits/`, `categories/`, `fournisseurs/`, `marques/`, `mouvements/` (read-only), `bons-commande-fournisseur/`, `emplacements/`, `transferts/`, `prix-fournisseurs/`, `retours-fournisseur/`.

### installations — chantiers / field execution
Installation projects spun up once a quote is signed, through to commissioning and
closure; work orders, checklists, regulatory (law 82-21) tracking.
- **Installation** (chantier) — `company` FK; `reference`; `client` FK; `devis` FK→ventes.Devis; `bon_commande` FK→ventes.BonCommande; `lead` FK→crm.Lead; `statut` (SIGNE/MATERIEL_COMMANDE/PLANIFIE/EN_COURS/INSTALLE/RECEPTIONNE/CLOTURE + legacy values); `puissance_installee_kwc`; `type_installation`; `technicien_responsable` FK; `bom` JSON (frozen BoM from devis); `regime_8221` + `dossier_statut` (regulatory); `annule` bool + `motif_annulation`; milestone dates.
- **StockReservation** (N14) — `company` FK; `installation` FK; `produit` FK→stock.Produit; `quantite`; `consomme` bool (`unique_together (installation, produit)`). Seeded from the chantier's frozen `bom` at creation; consumed exactly once when the chantier reaches the canonical INSTALLE statut (one `MouvementStock` SORTIE per SKU, idempotent under `select_for_update()`/atomic — re-entering INSTALLE emits nothing); cancel/close releases the remaining (un-consumed) reservation. Drives the reservation-aware availability on the stock serializer (réservé vs disponible) and low-stock alerts.
- **Intervention** (sortie chantier, F3) — `installation` FK; `ticket` FK→sav.Ticket (nullable); `type_intervention` (POSE/RACCORDEMENT/MISE_EN_SERVICE/CONTROLE/DEPANNAGE); `technicien` FK; `equipe` M2M→users (default = chantier installer, set server-side); `camionnette` FK→stock.EmplacementStock (nullable); `date_prevue/realisee`; **`statut`** — its OWN ordered state machine (`a_preparer/prete/en_route/sur_site/terminee/validee` + `STATUT_ORDER`, default `a_preparer`) **completely separate from the chantier statut and the STAGES.py contract** (changing it never touches either). Réf/client/devis/ville/GPS are read-only, pulled from the chantier.
- **InterventionActivity** (F3) — per-intervention chatter (same pattern as InstallationActivity), helper `intervention_activity.py` (creation + tracked-field changes incl. statut + manual notes; user/company server-side).
- **ChecklistTemplate** (N74) — `company` FK; `nom`; `type_installation` (nullable; auto-selects the template for a chantier of that market); `ordre`; `actif`; `protege` (the per-company "Défaut" fallback that carries today's 7 steps). **ChecklistEtapeModele / ChantierChecklistItem** — template steps (now FK→ChecklistTemplate, `unique_together (company, template, cle)`) and per-chantier checklist state; `capture_serie` flags serial-number capture steps (feeds the equipment registry); `fait` bool. Auto-selection (`template_for_installation`, services.py) matches by `type_installation`, falls back to Défaut — behaviour preserved.
- **TypeIntervention / InstallationActivity** — configurable intervention types and chantier chatter.
- **JalonProjet / ModeleProjet (+ ModeleProjetJalon, ModeleProjetBomLigne) / ReunionChantier** (FG293/296/298, `models_projet.py`) — project milestones/phases (étude/appro/pose/MES/réception with `date_cible`/`date_reelle`/`atteint`), chantier-type templates (`services.instantiate_modele_projet` pre-creates standard jalons + appends BoM-type lines to the frozen `bom`, idempotent + additive), and timestamped site-meeting minutes (ordre du jour/présents/décisions/actions, author + company server-side). Endpoints `jalons-projet/`, `modeles-projet/` (+ `{id}/instancier/`), `reunions-chantier/`.
- **FG291 — Projet (programme multi-chantiers, `models_program.py`)** — a `Projet` regrouping the chantiers + devis + tickets of one client/site (ferme à 4 forages, toiture par tranches), with link tables **ProjetChantier/ProjetDevis/ProjetTicket** referencing other apps by **string FK only** (`ventes.Devis`/`sav.Ticket`/`crm.Client` — resolved via FK metadata + tenant-checked, never imported). Its OWN status machine (`brouillon/actif/en_pause/termine/annule`) — **independent of STAGES.py and of devis/ticket document statuses** (attachment never touches them). Reference `PRG-` via the race-safe factory; company/created_by forced server-side. Idempotent `attacher_chantier|devis|ticket` actions (get_or_create); ViewSets `programmes/`, `programme-chantiers/`, `programme-devis/`, `programme-tickets/`. NEW architectural component.
- **FG292 — ProjetTache** (project tasks/sub-tasks with dependencies, on `models_program.py`): `projet` FK→Projet (same-app), `parent` self-FK (sub-tasks), `predecesseur` self-FK (dependency), `assigne` FK→user, `date_echeance`, own `Statut` (a_faire/en_cours/termine — NOT STAGES.py), `ordre`. `clean()` cycle-guards BOTH `parent` and `predecesseur` (rollback in an atomic block). ViewSet `programme-taches/` (`?projet`/`?statut`/`?parent`/`?assigne` filters, tenant checks on every FK).
- **FG294 — BudgetProjet + BudgetEngagement** (budget projet vs réel): `BudgetProjet` (1-to-1 with Projet; HT envelopes matériel/main-d'œuvre/sous-traitance/divers + `tarif_jour_mo` + `seuil_alerte_pct`) and `BudgetEngagement` (attaches a supplier cost — BCF/facture — by string-FK). `selectors.budget_projet_synthese` aggregates ACTUALS — devis via `apps.get_model('ventes','Devis')`, BCF/FactureFournisseur via function-local `apps.stock.selectors`, labour from same-app Installation — vs budget with an over-budget flag (no cross-app model import; import-linter 4/4). ViewSets `programme-budgets/` (+ `synthese`), `programme-engagements/`. INTERNE (responsable/admin — exposes purchase costs). **FG295** adds `selectors.projet_pnl` — consolidated project P&L: REVENUE (client factures on the project's devis, cancelled excluded) − COSTS (matériel/sous-traitance/imports via FG294 engagements + main-d'œuvre) → `marge_brute` + `marge_pct`; action `programmes/{id}/pnl/` (responsable/admin, cross-app reads reuse FG294's `get_model`/selector helpers — import-linter safe). No model. **FG299** adds `selectors.plan_de_charge_equipes` — the FIELD-TEAM workload view: per-technicien capacity (working days × hours) vs allocated Interventions (principal `technicien` OR `equipe` member, de-duped, windowed) with a `sur_reservation` flag + `charge_pct`; endpoint `interventions/plan-de-charge/?debut=&fin=`. Distinct from gestion_projet's PROJ18 and STAGES.py. No model. **FG300** adds `selectors.conflits_affectation` — double-booking detection: same technicien (principal/équipe) or same camionnette on ≥2 interventions the same day (de-duped, material assets excluded), at `interventions/conflits-affectation/?debut=&fin=`. No model. **FG301** adds `selectors.nivellement_charge` (resource levelling) — proposes moving interventions off overloaded technicians to under-loaded ones **without creating an FG300 same-day conflict** (read-only proposal, mutates nothing), at `interventions/nivellement-charge/`. No model. **FG302** adds **IndisponibiliteRessource** (`models_indispo.py`) — a field-resource unavailability calendar: a `technicien` XOR `camionnette` absent over `[date_debut, date_fin]`, `type_indispo` congé/formation/arrêt/autre; ViewSet `indisponibilites-ressource/` + `selectors.ressource_indisponible` that FG299/FG300/FG301 can call to exclude unavailable resources. Migration installations/0019.
- Endpoints (`/api/django/installations/`): `chantiers/` ViewSet + `creer-depuis-devis`, `regime-suggestion`, `{id}/historique|noter|mise-en-service|annuler|reactiver`, `{id}/checklist|cocher-checklist`, `{id}/besoin-materiel|commander-besoin` (now reports a per-SKU `reserve`); `interventions/` (F3: `?statut=`/`?type_intervention=`/`?installation=` filters + `{id}/historique|noter`); `types-intervention/`; `checklist-etapes/` (filterable `?template=`); `checklist-templates/` (N74, named template CRUD, Défaut delete-protected). Frontend route `/interventions` (F4, CHANTIERS menu): list + statut kanban (drag-to-change-status, technicien reassign). **FG303** adds `selectors.planning_camionnettes(company, debut, fin)` — a per-van calendar grouping interventions (via `Intervention.camionnette`) with a daily load, zero-capacity on FG302 indisponibilités (over-reservation visible), at the `planning-camionnettes` read action (IsAnyRole). No model. **FG304** adds **SousTraitant** — a subcontractor registry (métier/contact/ICE/RIB + `actif` archive flag, default True content-type-independent), DISTINCT from material suppliers; company+created_by server-side. ViewSet `sous-traitants/` (métier/actif filters, search). Migration installations/0020. **FG305** adds **OrdreSousTraitance** — subcontractor work orders (FK→SousTraitant FG304 + same-app chantier, race-safe `OST-` ref, prestation/montant/échéance, cycle brouillon→émis→en_cours→réceptionné→clos with lifecycle actions). ViewSet `ordres-sous-traitance/`. Migration installations/0021.

### outillage — durable field tools & kits (F1/F2)
Durable tooling (drills, ladders, meters…), tracked **strictly separate from the consumable stock catalogue** — never sellable, never consumed, never on a client-facing document.
- **Outillage** (F1) — `company` FK; `nom`; `categorie` (free text); `asset_tag`; `numero_serie`; `emplacement` FK→stock.EmplacementStock (nullable; the tool's home location among the existing dépôt/camionnette); `statut` (DISPONIBLE/EN_INTERVENTION/EN_REPARATION/PERDU); `date_achat`; `note`. Optional photo via the generic `records.Attachment` (`outillage.outillage` whitelisted in `records.ALLOWED_TARGETS`).
- **KitOutillage / KitOutillageItem** (F2) — named, reusable tooling kit templates editable in Paramètres; each an ordered list of catalogue tools (`KitOutillageItem.outil` FK→Outillage, `ordre`, `unique_together (kit, outil)`); `type_intervention` (TypeIntervention key) pre-selects a kit; `actif` toggle. Three defaults (pose structure / raccordement / mise en service) seeded on first list (idempotent), fully editable.
- Endpoints (`/api/django/outillage/`): `outils/` (read any role, write responsable/admin; filter `?statut=`/`?emplacement=`, search nom/asset_tag/numero_serie/categorie), `kits/` (seed-on-list, write admin), `kit-items/` (write admin, item company follows its kit). Frontend route `/outillage` (CHANTIERS menu) + Paramètres → « Kits d'outillage » tab.

### sav — after-sales: equipment registry, tickets, maintenance contracts
Tracks installed equipment + warranty clocks and the SAV ticket lifecycle.
- **Equipement** — `company` FK; `produit` FK→stock.Produit; `installation` FK→installations.Installation; `numero_serie`; `date_pose`; `date_fin_garantie(_production)` (computed from `date_pose` + product warranty); `statut` (EN_SERVICE/REMPLACE/HORS_SERVICE); `remplace_par_ticket` FK→Ticket.
- **Ticket** (SAV) — `company` FK; `reference`; `client` FK; `installation` FK (nullable); `equipement` FK (nullable); `type` (CORRECTIF/PREVENTIF); `statut` (NOUVEAU/PLANIFIE/EN_COURS/RESOLU/CLOTURE); `priorite`; `sous_garantie` (OUI/NON/A_DETERMINER, computed from equipment warranty if linked); `cout` (internal, never client-facing); `annule` bool + `motif_annulation`.
- **TicketActivity** — ticket chatter. **ContratMaintenance** — preventive contracts (`periodicite`, `date_debut`, `derniere_visite`, `actif`, `duree_mois`, `date_renouvellement`).
- **PieceConsommee** (N46) — parts consumed on a SAV ticket: `company` FK; `ticket` FK→Ticket; `produit` FK→stock.Produit; `quantite`; `stock_decremente` (guards double stock moves). Shown on the intervention report by designation/marque/quantité only — never buy price or margin; recording it can decrement stock via `MouvementStock`.
- Endpoints (`/api/django/sav/`): `equipements/`, `tickets/` (+ `{id}/historique|noter|annuler|reactiver|rapport-pdf`), `contrats-maintenance/`. **FG280** adds **AlarmeOnduleur** — inverter alarms/faults DISTINCT from the SAV ticket (code/gravité info-warning-critique/équipement, statut active/acquittee/resolue/escaladee), with `acquitter` (server-side user+date, idempotent) and `escalader` (links or opens a SAV ticket) actions; ViewSet `alarmes-onduleur/`. Migration sav/0011.

### reporting — dashboards, KPIs, insights, audit log  *(no models)*
Read-only aggregation across crm/ventes/installations/sav/stock, role-filtered.
- Endpoints (`/api/django/reporting/`): `dashboard/`, `search/`, `notifications/`, `calendar/` and `calendar/reschedule/` (agenda events + drag-reschedule), `pipeline/` (funnel value by STAGES, weighted forecast), `reports/sales|stock|service/` (+`?export=xlsx`), `insights/recurring-revenue|audit-log|job-costing|analytics|commissions/`, `archive/client/{id}/` and `archive/chantier/{id}/`. `job-costing` (margin via internal `prix_achat`) and `commissions` (sales commission per `CompanyProfile.commission_mode`) are admin-only.

### parametres — company profile, business settings, WhatsApp templates
- **CompanyProfile** (one per company) — identity + Moroccan legal IDs (`ice`, `identifiant_fiscal`, `rc`, `patente`, `cnss`, `rib`); branding (`logo_key`, `signature_key`, `couleur_principale`); `responsable_defaut_leads` FK (default lead owner); quote-gen knobs (`payment_terms` JSON, `quote_validity_days`, `tva_standard/panneaux`, ROI constants `onee_tarif_kwh`/`productible_kwh_kwc`/`rendement_global`, `remise_max_pct`, `discount_approval_threshold`, `agricole_pump_hours`); `default_installer` FK (default technician for new chantiers, N66; NULL = creator is responsable); sales commission (`commission_mode` off/pct_devis/par_kwc + `commission_valeur`, sensitive/admin-only, N99); referral toggle (`referral_enabled` bool + `referral_reward`, N98); silent DGI export master switch (`dgi_export_actif` bool, **default OFF**, N105 — arms the ventes `dgi/` capability, invisible while off); `doc_prefixes`/`doc_numbering` JSON.
- **MessageTemplate** — WhatsApp templates by `cle` (devis/facture/relance), `corps_fr` + `corps_darija`.
- **EmailTemplate** (FG17, in `models_email.py`) — editable e-mail templates by `cle` (devis/facture/relance/notification): `sujet` + `corps` with the same placeholder whitelist as WhatsApp (`{civilite}{nom}{reference}{lien}{n}`), `unique_together company+cle`. Helpers `EmailTemplate.get_template`/`render` (tolerant) for the future automation-email rewire (intentionally NOT wired yet). Endpoints `email-templates/` (CRUD) + `email-templates/effective/` (defaults⊕overrides) + `email-templates/bulk/` (upsert), writes audited.
- **SettingsAuditLog** — who changed which setting field.
- **StatutConfig** (N58, in `models_statuses.py`) — per-company display overlay for chantier/SAV/bon-de-commande statuses: `domaine` + canonical `cle` + `libelle` + `ordre` + `actif` (`unique_together company+domaine+cle`). Display-only — canonical keys & state machines stay in their source models; defaults read live from `Installation.STATUT_ORDER`/`Ticket.STATUT_ORDER`/`BonCommande.Statut` (`statuses_defaults.py`), so output is byte-identical until edited.
- Endpoints (`/api/django/parametres/`): `GET /`, `PUT/PATCH /update/`, `POST /upload-logo|upload-signature/`, `DELETE /delete-logo|delete-signature/`, `GET+PUT/PATCH /messages/`, `GET /audit/`; `statuts/` ViewSet (N58) + `statuts/effective/?domaine=` (full ordered effective list) + `statuts/bulk/` (upsert a domaine). Reads `GET /` and `GET /messages/` are open to any role; every write/audit endpoint (incl. `statuts/` writes) is the Administrateur + Responsable tier (`IsAdminOrResponsableTier`), limited tier blocked.

### roles — RBAC  *( `/api/django/roles/` )*
- **Role** — `company` FK; `nom` (unique per company); `permissions` JSON (validated against canonical `ALL_PERMISSIONS`); `est_systeme` bool (system roles undeletable). Linked from `CustomUser.role`.
- 2026-06-18 (Feature D): `ALL_PERMISSIONS` expanded to a module×action grid + governance codes (`*_export`, `crm/ventes/sav_reassign`, `technicien_assign`, `prix_achat_voir`, `journal_activite_voir`, scope markers `records_scope_equipe`/`records_scope_sous_arbre`). `CANONICAL_SYSTEM_ROLES` seeds **seven** roles per company — Directeur, Administrateur (=Admin), Commercial responsable, Commercial, Technicien responsable, Technicien, Viewer — plus the legacy Responsable/Utilisateur kept for existing accounts. Seeder: `init_roles` (also maps owners→Directeur, custom commercial→Commercial; N103: self-heals a drifted same-named system role to `est_systeme=True`). `role_tiers.py` now derives the tier from the authoritative permission signal first (`roles_gerer`→admin, `users_voir`→responsable) with the name mapping as fallback — so a Directeur/Administrateur whose seeded row drifted to `est_systeme=False` still resolves to the admin tier and keeps access to `/users/` and `/roles/` (N103 regression fix), without widening Commercial/Technicien/Viewer.
- Endpoints: Role ViewSet (CRUD, open to the Administrateur + Responsable tier via `IsAdminOrResponsableTier` — limited tier blocked; delete blocked if system or in-use) + `permissions-disponibles/`.

### audit — activity log (audit trail)  *( `/api/django/audit/` )*
- **AuditLog** — company-scoped (server-forced, nullable for failed login); `user` FK (null=system) + `actor_username` snapshot; `action` (create/update/delete/status/login/logout/login_failed/pdf/email/whatsapp/export/accept/refuse); `content_type` + `object_id` + `object_repr` (link-back snapshot); `detail`; `timestamp` (UTC, bucketed in Africa/Casablanca at read time).
- Capture: `apps/audit/signals.py` (post_save/post_delete + status-change via pre_save cache) on the main business models, gated by `apps/audit/middleware.py` (records only inside a request → no seed/migration noise); login/logout in `authentication/views.py`, failed login via `user_login_failed`; key actions (PDF/export/WhatsApp) via explicit `recorder.record` calls. Best-effort — never blocks the request.
- Endpoints (gated on `journal_activite_voir`, Directeur-only by default): `stats/` (hourly buckets for a day, per-day for week/month, Casablanca, filterable), `entries/` (paginated filterable list, newest first), `meta/` (filter-bar data).

### records — generic activities + attachments  *( `/api/django/records/` )*
ContentType-based, attachable to Lead/Client/Installation/Ticket.
- **ActivityType** — configurable types (Appel/Email/Relance…), `delai_defaut_jours`.
- **Activity** — generic FK target; `activity_type` FK; `due_date`; `assigned_to` FK; `done` bool + `done_at/by`; `auto_relance` bool (auto-synced from `Lead.relance_date`).
- **Attachment** — generic FK target; `file_key` (MinIO); `phase` (avant/pendant/après for field photos).
- Endpoints: `activity-types/`, `activities/` (+ `mine/`, `{id}/done/`), `attachments/` (+ `{id}/download`, `attachments-count/`).

### customfields — admin-defined custom fields  *( `/api/django/custom-fields/` )*
- **CustomFieldDef** — `module` (LEAD/CLIENT/PRODUIT), `code` (slug), `type` (TEXT/NUMBER/DATE/CHOICE/BOOLEAN), `options` JSON, `obligatoire/visible_liste/actif`. Values live in each target model's `custom_data` JSON (no schema migration).
- Endpoints: `definitions/` ViewSet.

### documents — field-execution PDFs  *(no models, `/api/django/documents/`)*
- `GET chantiers/{pk}/pv-reception|bon-livraison|dossier-remise|attestation/` — generates post-delivery PDFs for an installation.

### dataimport — CSV/XLSX import  *(no models, `/api/django/imports/`)*
- `POST dry-run/` (preview + column mapping), `POST commit/` (create-only, duplicates skipped), `GET export/{entity}/`. Targets: leads, clients, products.

### contact — public contact form  *(no models, `/api/django/contact/`)*
- `POST /` — landing-page contact form; **parked by default** (returns 404 unless `CONTACT_FORM_ENABLED=1`).

### monitoring — production supervision (N50/N51/N52)  *( `/api/django/monitoring/` )*
- Models: `MonitoringConfig` (per installed-system provider + credentials, enabled), `ProductionReading` (manual/auto yield), `UnderperformanceFlag`, per-company settings (threshold % + auto-ticket toggle, default OFF).
- Swappable provider interface (registry + `NoOpProvider` default + `FusionSolarProvider` skeleton that no-ops without credentials; no new dependency).
- `configs/` (+ `providers/`, `{id}/sync-now/`), `readings/` (list + manual entry), `settings/`. Under-performance auto-creates an idempotent SAV ticket when enabled.

### notifications — unified notification engine (N75)  *( `/api/django/notifications/` )*
- Models: `Notification` (company + recipient-scoped), `NotificationPreference` (per user×event channel toggles in_app/whatsapp/email). Service `notify()` is best-effort, respects preferences, reuses existing channels (no-op when unconfigured).
- `notifications/` (+ `unread-count/`, `{id}/read/`, `read-all/`), `preferences/`. In-app bell in the header + `/parametres/notifications`.

### automation — no-code rules engine (N72/N73)  *( `/api/django/automation/` )*
- Models: `AutomationRule` (trigger + action config), `AutomationRun` (every run logged), `AutomationApproval` (owner-tier approval step). Fires on the app's own `post_save` signals, best-effort (never breaks the originating save); opt-in.
- `rules/` (+ `{id}/toggle/`), `runs/`, `approvals/` (+ `approve/`, `reject/`). Paramètres → « Automatisations ».

### publicapi — public REST API + webhooks (N89)  *( `/api/public/` data, `/api/django/publicapi/` management )*
- Models: `ApiKey` (hashed, scoped), `Webhook`, `WebhookDelivery`. `Api-Key` auth + per-key DRF throttle; read-only company-scoped `leads/devis/factures/chantiers` (never buy prices); HMAC-SHA256-signed webhooks on lead.created / devis.accepted / chantier.completed / facture.paid (httpx, best-effort). Paramètres → « API & Webhooks ».

### agent — agentic action catalogue (Group R, AG1)  *( `/api/django/agent/` )*
- No DB model — actions are declared in code via `apps/agent/registry.py` (`AgentAction`: key/label/description/inputs-schema/endpoint/method/required_permission/risk∈internal·outward·irreversible/confirm_summary). `GET actions/` returns the per-caller, company+permission-filtered catalogue (cross-tenant leakage tested). Domain apps register their actions in `ready()` (ventes/crm/stock/sav/installations `agent_actions.py`, AG4–AG9). Execution stays the JWT-relay pattern (Django re-checks permission+company); outward/irreversible actions go through the FastAPI propose→confirm protocol.

### chat — internal team messaging « Discuss » (Group S)  *( `/api/django/chat/` )*
- Models: `Conversation` (dm/channel), `ConversationMember` (role/last_read_at/is_muted), `Message` (text/voice/system/record kinds, soft-delete, pin, reply_to), `MessageAttachment` (image/file/voice + transcript fields), `MessageReaction`, `MessageMention`, + generic shared-record link. Company **and** membership scoped everywhere (non-member 403, cross-tenant 404; company forced server-side). Endpoints: conversations (list/create/archive/read/unread/search/mute/members/leave), messages (`list?conversation=`/create/edit/delete/upload/react/pin/unpin/attachments-download/share-record via selectors). Notifications reuse `notify()` (CHAT_MESSAGE/CHAT_MENTION, mute-aware). Voice memos transcribed by a Celery task → FastAPI faster-whisper (S10/S11), flag `CHAT_TRANSCRIPTION_ENABLED`; v1 real-time is polling (WebSocket upgrade S21 is gated on provisioned infra).

### compta — Moroccan accounting (CGNC): chart, journals, ledger, statements  *( `/api/django/compta/` )*
- Double-entry bookkeeping on the CGNC plan comptable: journaux, **EcritureComptable**/**LigneEcriture** (grand livre), balance/CPC/bilan statements, lettrage. All `company`-scoped.
- **ExerciceComptable** (fiscal year) + **PeriodeComptable** (lockable month/period via `date_verrouillee`) — `services.cloturer_periode`/`rouvrir_periode` lock/unlock. Once a period is locked, `EcritureComptable`/`LigneEcriture` `save()/delete()` raise `ValidationError` (immutability), and `services.verifier_facture_modifiable` is a value-only guard ventes can call (no cross-app model import). **OD manuelles** — `services.creer_ecriture_od` posts a balanced entry with no source document, refused when the period is locked. **À-nouveaux** — `cloturer_exercice` + `reporter_a_nouveaux` carry class 1–5 balance-sheet balances into the new exercise as one balanced opening entry (idempotent via `an_reporte`). Endpoints: `periodes/{id}/cloturer|rouvrir`, `exercices/ecriture-od`, `exercices/{id}/reporter-a-nouveaux`.
- **FG118 — Immobilisation** (fixed-asset register): `company` FK, `libelle`, `categorie` (vehicule/outillage/materiel/mobilier/informatique/autre), `cout` HT, `taux_tva`, `date_acquisition`, `actif`; read-only `montant_tva`/`cout_ttc` props. Company-scoped ViewSet `immobilisations/` (category filter + search).
- **FG119 — Amortissement**: **PlanAmortissement** (OneToOne→Immobilisation; `mode` lineaire/degressif, `duree_annees`, `base_amortissable`, frozen Moroccan CGI `coefficient_degressif`) + **DotationAmortissement** (per-year `montant`/`cumul`/`valeur_nette`, `posted`, FK `ecriture`). `services.generer_plan_amortissement` (idempotent; degressive switches to straight-line-of-residual) and `services.poster_dotation` (balanced écriture debit class-6 / credit class-28 — **respects the period lock**). Actions `immobilisations/{id}/plan-amortissement`, `dotations/{id}/poster`.
- **FG120 — Cession/rebut**: **CessionImmobilisation** (`type_cession` vente/rebut, `prix_cession`, computed `valeur_nette_comptable` = cost − cumulated FG119 amortization, signed `resultat_cession` plus/moins-value, `posted` + FK `ecriture`). `services.poster_cession` posts the balanced disposal écriture (reprise amortissements + sortie class-2 + résultat 6513/7513 + 3481 on sale) — **respects the period lock** and marks the asset inactive. Actions `immobilisations/{id}/ceder`, `cessions/{id}/poster`.
- **FG135 — NoteFrais** (notes de frais & remboursements employés): `company`+`employe` FK, `justificatif` photo (MinIO FileField), cycle `brouillon→soumise→validée→remboursée`(+`rejetée`), réf `NDF-YYYYMM-NNNN` via the race-safe reference factory. `services` post balanced écritures — validation (debit charge 6143 / credit personnel 4432) and reimbursement (debit 4432 / credit treasury GL, BNK/CSH journal), both idempotent and **respecting the FG115 period lock**; distinct `source_type` avoids the EcritureComptable unique-source collision. Company-scoped multipart ViewSet `notes-frais/` (`IsResponsableOrAdmin`) + actions `soumettre|valider|rejeter|rembourser`.
- **FG136 — BaremeIndemnite + IndemniteChantier** (indemnités kilométriques & per-diem chantier): `BaremeIndemnite` (per-company km rate + per-diem rate, one default-active barème) and `IndemniteChantier` (employee site-trip: GPS départ + chantier, distance via a local haversine copy — keeps compta decoupled from installations/sav — × rate × aller-retour + per-diem × jours, all frozen at calc). Validation/reimbursement post the same balanced écritures as FG135 (charge 6143 / 4432, then 4432 / treasury), idempotent and **respecting the period lock**. ViewSets `baremes-indemnite/` (auto-demotes prior default), `indemnites-chantier/` + lifecycle actions.
- **FG137 — DeclarationTVA** (préparation de la déclaration de TVA): `selectors.preparer_declaration_tva` aggregates from the GL over a period — TVA collectée (4455/44552, crédit−débit) − déductible (3455/34552, débit−crédit) → `tva_a_declarer` = max(0, collectée−déductible−crédit antérieur) with the excess as `credit_reportable`; carries `regime` (mensuel/trimestriel) + `methode` (débit/encaissement). `services.preparer_declaration_tva` freezes a `DeclarationTVA` snapshot (reference `TVA-` race-safe). ViewSet `declarations-tva/` (`preparer` action derives amounts from the GL — body can't impose them — + CSV `export`), Admin/Responsable. **FG138** adds `selectors.releve_deductions_tva` — the DGI line-by-line deductible-VAT annex (one row per pièce: date/réf/journal/tiers/base HT/TVA/taux, reconciles 1:1 with FG137's `tva_deductible`) at `etats/releve-deductions-tva/` (JSON or `?export=csv`, role-gated). No model — reuses the GL. **FG139** adds **RetenueSource** (Moroccan withholding tax / retenue à la source on fees: `taux` × `base` = `montant`, per pièce/tiers, ref `RAS-` race-safe) + `selectors.bordereau_versement_ras` (totals per prestataire + `total_a_verser`). ViewSet `retenues-source/` (`verser`/`bordereau`/`export` CSV via `?export=csv`), role-gated, montant server-side. Migration compta/0014. **FG140** adds an IS (corporate-tax) aid: `selectors.estimer_is` (CPC résultat ± réintégrations/déductions → résultat fiscal → IS dû = max(progressive barème, cotisation minimale 0.25%/3000 floor)) + `echeancier_acomptes` (4 × 25% at month-end 3/6/9/12) + `regularisation_is`, at `etats/aide-is/` (JSON / `?export=csv`, admin). No model — reuses the CPC. **FG141** adds `selectors.export_fec` — the DGI FEC (fichier des écritures comptables): the 18 standard columns, one ordered row per LigneEcriture (date→pièce→entry order), exercice-bounded, balance-verified, at `etats/export-fec/?exercice=` (JSON / `?export=fec` tab-delimited / `?export=csv`). No model. **FG142** adds `selectors.liasse_fiscale` — the trousse liasse fiscale: assembles bilan + CPC + balance + the FG138 TVA annexe into one package (**reuses the standalone selectors, no recompute**), at `etats/liasse-fiscale/?exercice=` (JSON / `?export=csv` multi-section). No model. **FG143** adds `selectors.declaration_honoraires(company, annee)` — the DGI annual état 9421 (fees paid to third parties), aggregated per-bénéficiaire from the FG139 RAS ledger (brut/retenue/net + IF/ICE + nb pièces), at `etats/declaration-honoraires/?annee=` (JSON / `?export=csv`, role-gated). No model. **FG144** adds **TimbreFiscal** — Moroccan droit de timbre (0.25% + statutory minimum) auto-computed on CASH-settled invoices (non-cash règlements exonérés → None); the origin payment is a string-id ref (no ventes import) and no GL entry is posted (snapshot, FG139 pattern). ViewSet `timbres-fiscaux/` (+ `verser`, `?export=csv`). Migration compta/0015. **FG145** adds **RetenueGarantie** (RG % withheld on a marché, race-safe ref, released at maturity) + **CautionBancaire** (provisoire/définitive/restitution bank guarantees with mainlevée); marché/facture by string-ref (no ventes import); `liberer`/`mainlevee` actions + maturity selectors. ViewSets `retenues-garantie/`, `cautions-bancaires/`. Migration compta/0016.

### flotte — fleet: vehicles + rolling equipment (FLOTTE1, new app)  *( `/api/django/flotte/` )*
- **Vehicule** (`company` FK; immatriculation, marque, modèle, énergie diesel/essence/électrique/hybride, kilométrage, valeur, statut actif/maintenance/réformé) and **EnginRoulant** (`company` FK; type nacelle/groupe électrogène/chariot, compteur d'heures, marque, modèle, valeur, statut). Company-scoped ViewSets (company forced server-side, an injected body `company` is ignored) at `vehicules/`, `engins/` with énergie/statut/type filters + search. Uses only the `authentication.Company` string FK — no domain-app imports. **FLOTTE3** adds `Vehicule.emplacement_stock_id` (PositiveInteger, NOT a cross-app FK) referencing a `stock.EmplacementStock`; validated same-company + labelled via a function-local `apps.stock.selectors.get_emplacement_scoped` call (degrades to `#id`; never imports stock models). **FLOTTE6** adds **ReferentielFlotte** (editable per-company lookup lists: `domaine` type_vehicule/type_engin/energie/categorie_permis, `code`/`libelle`/`ordre`/`actif`, unique company+domaine+code) — additive (hardcoded choices untouched) — plus an idempotent `seed_referentiels_flotte` command. ViewSet `referentiels/` (`?domaine`/`?actif`). **FLOTTE5** adds **ActifFlotte** — a unified asset reference linking entretien/sinistre/document to EITHER a `Vehicule` OR an `EnginRoulant` via one model (exactly-one-target + same-company enforced in `clean()`/`save()`); company-scoped ViewSet `actifs/` (`?type_actif`) + selectors for cross-app reads. **FLOTTE13** adds fuel/energy consumption: `selectors.consommation_vehicule` computes **L/100 km and kWh/100 km** plein-to-plein from `PleinCarburant` + odometer (per-segment, divide-by-zero guarded, L vs kWh kept separate), surfaced read-only at `pleins/consommation/?vehicule=<id>` (`IsAnyRole`, 400 missing/non-int param, 404 cross-company). No migration. **FLOTTE14** adds **CarteCarburant** (fuel card: `numero`, `plafond`, optional `vehicule`/`conducteur` FK) + `selectors.anomalies_pleins` flagging four families per plein — `km_recul` (odometer decreasing), `km_saut` (>5000 km jump), `conso_aberrante` (>2× the vehicle's median baseline, reusing FLOTTE13's conso), `plafond_depasse` — at `cartes/anomalies/?vehicule=` (read action, `IsAnyRole`). ViewSet `cartes/`. **FLOTTE15** adds **PlanEntretien** (preventive maintenance via an `ActifFlotte` FK — reaches both Vehicule km and EnginRoulant heures): triggers by `intervalle_km`/`intervalle_jours`/`intervalle_heures` + last-done refs + alert margins; `selectors.plans_entretien_status` computes next-due vs current km/date/hours (due/upcoming/ok). ViewSet `plans-entretien/` (+ `echeances/` read action). **FLOTTE16** adds **EcheanceEntretien** (a generated due-maintenance record per plan: `due_le`/`due_km`/`due_heures`, `statut` a_faire/planifie/fait) + `services.generer_echeances_entretien` (idempotent — no duplicate OPEN échéance per plan; best-effort alert via `notifications.notify`) + a `manage.py generer_echeances_entretien` command. ViewSet `echeances-entretien/` (read any role, `generer` write action; POST-create disabled). Migration flotte/0014. **FLOTTE17** adds **Garage** (atelier: nom/adresse/téléphone) + **OrdreReparation** (repair order on an `ActifFlotte`: garage, description, `cout_main_oeuvre`+`cout_pieces`→derived `cout_total`, `statut` ouvert/en_cours/cloture, optional `EcheanceEntretien` link); ViewSets `garages/`, `ordres-reparation/` (+ `couts/` summary, `cloturer/` which solde the linked échéance). Migration flotte/0015. **FLOTTE18** adds **Pneumatique** (tire: position/dimension/montage/dépose/statut/coût) + **PieceFlotte** (part: désignation/réf/quantité/coût, optional OrdreReparation link); ViewSets `pneumatiques/`, `pieces/` + a per-vehicle `synthese/` summary. Migration flotte/0016. **FLOTTE19** adds **EcheanceReglementaire** — generic regulatory deadlines (visite technique/assurance/vignette/carte grise/taxe à l'essieu) on an `ActifFlotte`, with a today-injectable status (a_jour/a_renouveler/expire) and `expirantes/?within=N`; distinct from the FLOTTE16 maintenance échéances. ViewSet `echeances-reglementaires/`. Migration flotte/0017. **FLOTTE20** adds **BaremeVignette** — an editable per-company TSAV grid (énergie × CV bracket → montant, per year) + `Vehicule.puissance_fiscale` + `selectors.calcul_tsav` (electric exempt, no bracket → None) + an idempotent standard-grid seed. ViewSet `baremes-vignette/` + `vehicules/{id}/tsav/`. Migration flotte/0018.

### ged — document management / DMS (GED1, new app)  *( `/api/django/ged/` )*
- Governed DMS reusing `records.storage` (MinIO `file_key`). **Cabinet** + **Folder** (self-FK tree with a materialized `path` recomputed in `save()`/`services.move_folder`, sub-tree prefix rewrite + cycle refusal), **Document** (lives in a Folder) + **DocumentVersion** (`file_key`, SHA-256 `checksum` for dedupe via `services.find_duplicate`, server-set incremental `version`, `uploaded_by`). All `company`-scoped (company/created_by/uploaded_by forced server-side). Endpoints: `cabinets/`, `folders/` (+ `descendants`), `documents/`, `document-versions/`. **GED4** — move (déplacement) over HTTP: `POST folders/{id}/deplacer/` (body `{parent}`, reparent/to-root, anti-cycle + cross-cabinet refusal via `services.move_folder`) and `POST documents/{id}/deplacer/` (body `{folder}`, via `services.move_document`); destination always resolved inside the caller's company (404 cross-tenant). **GED14** — inline same-origin preview: `GET document-versions/{id}/apercu/` streams the document bytes through Django (PDF/image/text → `Content-Disposition: inline`, else attachment; `X-Content-Type-Options: nosniff`), gated as a READ action (`IsAnyRole`, like list/retrieve) so read-only roles can preview. **GED17** adds a document lifecycle: `Document.statut` (**brouillon→revue→approuvé→archivé→obsolète**, default brouillon) with a guarded `LIFECYCLE_TRANSITIONS` state machine in `services.change_lifecycle_status` (illegal/unknown/same-status → `ValueError`, cross-company → `PermissionError`, `select_for_update`), exposed read-only on the serializer and advanced only via `POST documents/{id}/cycle-vie/` (responsable/admin) + a `?statut=` filter. Local GED statuses — **separate from the STAGES.py funnel**. **GED18** adds **DemandeApprobation** (review/approval workflow): `demandeur`/`approbateur`, `statut` en_attente/approuve/rejete; `services.request_review` opens a demande + moves brouillon→revue, `approve_demande`/`reject_demande` **reuse the GED17 `change_lifecycle_status`** (no duplicate state machine) to advance revue→approuvé / back to brouillon; guards duplicate-pending / already-decided / cross-company. Actions `documents/{id}/demander-revue|demandes` + ViewSet `demandes-approbation/` (`approuver`/`rejeter`). **GED19** adds **AclGed** — per-folder/document ACL: exactly-one target (folder XOR document, two CheckConstraints), principal = `utilisateur` and/or `role`, `niveau` lecture/ecriture/gestion, `herite` flag. `selectors.acl_effective` walks up the materialized `Folder.path` (document override > nearer folder > ancestor only when `herite`; most-permissive at equal scope; admin always gestion), softly wired into `documents_visible_to_user` — **backward-compatible: no ACL rows → behaviour unchanged**. Migration ged/0013. **GED20** adds **PartageGed** — a tokenized public document share (`token` via `secrets`, `expires_at`, hashed `password_hash`, `quota_max` + `telechargements` counter, `actif` kill-switch); a PUBLIC `AllowAny` endpoint `GET /api/django/ged/public/<token>/` resolves **by token only** (never trusts request company/identity), streams the document, atomic quota-conditional increment, and returns 404 (unknown/revoked) / 410 (expired/quota) / 403 (missing/wrong password). Management ViewSet `partages/` (+ `revoquer/`) is fully multi-tenant. Migration ged/0014. **GED21** adds watermarking & diffusion control: flags `Document.watermark_diffusion` + `PartageGed.watermark` and `services.apply_watermark` (image via Pillow — already a dep; PDF via PyMuPDF imported lazily, graceful degrade if absent → original bytes), wired into the GED14 `apercu` + GED20 public download (no-watermark path byte-identical). Category DEP but NO hard new dependency. Migration ged/0015. **GED22** adds **PolitiqueRetention** — document retention policies (durée de conservation + action à l'échéance, default the NON-destructive `signaler`) + `selectors.documents_echus(company, today)` (most-specific policy, today-injectable) + a `lister_documents_echus` command. Never auto-deletes passively. ViewSet `politiques-retention/` (+ `echus`). Migration ged/0016. **GED23** adds **ArchivageLegal** — legal probative-value write-once archiving (SHA-256 integrity hash, best-effort MinIO object-lock with graceful degrade — no hard dep). Once archived, app-layer immutability blocks edit/delete/new-version/move/lifecycle/check-out/check-in (all → 403, never 500); the ArchivageLegal row is create-only. ViewSet `archivages-legaux/` (+ `documents/{id}/archiver-legalement`). Migration ged/0017.

### rh — human resources: employee master (FG154, new app)  *( `/api/django/rh/` )*
- **DossierEmploye** (`company` FK; employee record). **FG155** adds the employment-contract layer: `type_contrat` (TextChoices CDI/CDD/ANAPEC/stage/intérim) + `contrat_date_debut`/`contrat_date_fin` (nullable dates; empty `date_fin` = open-ended/CDI). Company-scoped ViewSet (`employes/`) with `@action cdd-a-echeance/?within=N` (default 30 days) returning only same-company CDDs whose `contrat_date_fin` falls within the window. **FG156** adds the mandatory Moroccan payroll identity fields to `DossierEmploye`: `cnss`/`cimr`/`amo`, `situation_familiale` (célibataire/marié/divorcé/veuf), `nombre_enfants` (IR deductions) — all nullable (CIN/RIB already existed). **FG166** adds **Pointage** (clock-in/out: `company`+`employe` FK, `type_pointage` arrivée/départ/complet, server-set `heure_arrivee`/`heure_depart`, optional GPS, computed `duree_minutes`) with actions `pointages/pointager-arrivee` + `pointages/{id}/pointager-depart` (server timestamp; → COMPLET + duration once arrival is set). `IsResponsableOrAdmin`-gated. **FG172** adds the skills matrix: **Competence** (per-company catalogue, `domaine` pose_structure/raccordement_dc/raccordement_ac/mes_onduleur/pompage/soudure/autre, unique `(company, code)`) + **CompetenceEmploye** (one row per `(employe, competence)`, `niveau` 0–4 Non-acquis→Expert, server-set `evalue_par`/`evalue_le`). ViewSets `competences/`, `competences-employe/` (+ `matrice/` grid action, `?domaine`/`?niveau_min` filters), admin-gated, company forced server-side; duplicate-code → clean 400. **FG173** adds **Habilitation** — electrical authorizations (NF C 18-510: B0/H0/B1V/B2V/BR…) per employee with `organisme`, `date_obtention`, `date_validite` (expiry) and a computed `valide` flag; ViewSet `habilitations/` + `expirantes/?expire_within=N` (expiring-soon + already-expired), unique `(employe, type_habilitation)`. Distinct from the FG172 competence matrix. **FG174** adds **Certification** — the non-electrical family (travail_hauteur/harnais/caces_nacelle/secourisme_sst/conduite/autre) per employee with `organisme`, `date_validite` + computed `valide`; ViewSet `certifications/` (+ `expirantes/?expire_within=N`), unique `(employe, type_certification)`. Modelled distinctly from the FG173 electrical Habilitation. **FG175** adds `selectors.echeances_rh` — a unified expiry-alert engine unioning expiring Habilitations + Certifications + DocumentEmploye within X days (normalized `{type, employe, libelle, date_validite, jours_restants}`, `today` a param) at `echeances/?within=N`, plus a `manage.py alertes_expiration_rh` command dispatching one notification per échéance via the shared `notifications.notify` service (function-local import). No model. **FG176** adds `selectors.verifier_habilitation_requise(company, employe, type_requis)` → `{autorise, manquantes, expirees, message}` (reuses FG173's validity rule; `INTERVENTION_HABILITATIONS` map) + endpoint `employes/{id}/verifier-habilitation/?type=&intervention=`. A SOFT guard (reports; enforcement at assignment stays in installations). No model. **FG177** adds **VisiteMedicale** (occupational-health visits per employee: `date_visite`, `prochaine_visite`, `aptitude` apte/restrictions/inapte, médecin/organisme, computed `a_jour`); ViewSet `visites-medicales/` (+ `expirantes/?expire_within=N`), and feeds FG175's `echeances_rh` with a `visite_medicale` family. Migration rh/0017. **FG178** adds **EpiCatalogue** (PPE catalogue: `type_epi` casque/harnais/gants_isolants/chaussures/lunettes/autre) + **DotationEpi** (nominative issue: `employe`, `epi`, `taille`, `date_dotation`, `date_renouvellement`, `quantite`); ViewSets `epi-catalogue/`, `dotations-epi/` (+ `a-renouveler/`, `employe/`), feeds FG175. Migration rh/0018. **FG179** adds EPI life/expiry tracking: `EpiCatalogue.duree_vie_mois`/`intervalle_controle_mois` → derived `DotationEpi.date_peremption`/`date_prochain_controle` (end-of-month-clamped month math), computed `perime`/`a_controler` (`today`-injectable), endpoint `dotations-epi/a-remplacer-controler/?expire_within=N`; feeds FG175 with `epi_peremption`/`epi_controle` families. Migration rh/0019. **FG180** adds **EmargementEpi** (signed EPI-handover acknowledgement, loi 53-05 typed name + server-side IP/user-agent evidence) + `accuse_remise`/`date_accuse` on DotationEpi; `services.emarger_dotation` records it (company + acting user server-side, accusé frozen at first signature); actions `dotations-epi/{id}/emarger|emargements`. No external e-sign dep. Migration rh/0020. **FG181** adds **AccidentTravail** — workplace-accident register (race-safe `AT-` reference, date/lieu/employé/gravité/arrêt+jours/photo, CNSS declaration flags) + a CNSS CSV export (`?export=csv`). ViewSet `accidents-travail/`. Migration rh/0021. **FG182** adds **PresquAccident** — a lightweight near-miss register (race-safe `NM-` ref, lieu/gravité potentielle/mesure corrective, server-side declarant; no injured person/CNSS — distinct from FG181) + a stats-by-gravité selector. ViewSet `presqu-accidents/`. Migration rh/0022.

### gestion_projet — project management (PROJ1, new app)  *( `/api/django/gestion-projet/` )*
- **Projet** + **ProjetChantier** (`company`-scoped). **PROJ2** adds **ProjetLien** (`company` + `projet` FK; `type_cible` devis/facture/ticket/achat, `cible_id` target PK, cached `libelle`) linking a project to other apps' documents by **string-FK only** (no real cross-app FK). Endpoints: `projet-liens/` (CRUD, `?projet=`/`?type_cible=` filters) + `projets/{id}/liens/` (enriched). `selectors.liens_enrichis` enriches devis links via a function-local `apps.ventes.selectors.devis_card` call and degrades to the stored label otherwise (cross-app boundary respected; import-linter clean). **PROJ3** adds a project-lifecycle state machine on `Projet` (`statut` brouillon→planifie→en_cours⇄en_pause→termine, annule from any non-terminal — **independent of `STAGES.py`**, rule #2) via actions `planifier`/`demarrer`/`mettre-en-pause`/`reprendre`/`terminer`/`annuler` (illegal → 400; statut read-only outside actions) + a **ProjetActivity** transition log (`historique/`). **PROJ4** adds **PhaseProjet** (project WBS: `type_phase` etude/appro/pose/mes/reception — own enum, not STAGES; prévu/réel dates, `statut`, `avancement_pct` 0-100; unique projet+type_phase) + `services.instancier_phases_standard` (5 ordered phases, idempotent). ViewSet `phases/` + action `projets/{id}/instancier-phases`. **PROJ14** adds delay detection: `selectors.retards_projet` + `GET projets/{id}/retards/` classifying unfinished tasks and unreached milestones as `en_retard` (past due) or `a_risque` (due within `seuil_jours`, default 7) with `retard_jours` (no migration). **PROJ18** adds `selectors.plan_de_charge` — per-resource capacity (working days − Indisponibilité × hours/day) vs allocated (AffectationRessource charge, direct + team-split, pro-rated to the window) over a period with a `surcharge` flag + `utilisation_pct` (None when capacity 0); endpoint `ressources/plan-de-charge/?debut=&fin=`. No model. **PROJ19** adds `selectors.conflits_affectation` — double-booking: same `RessourceProfil` allocated to ≥2 `AffectationRessource` whose windows overlap (direct + via équipe; bonus: allocation during an Indisponibilité), at `ressources/conflits-affectation/?debut=&fin=`. No model. **PROJ20** adds `selectors.nivellement_charge` (resource levelling) — proposes moving direct affectations off over-allocated RessourceProfil to under-loaded ones without creating a PROJ19 conflict (read-only), at `ressources/nivellement-charge/`. No model. **PROJ21** adds **BudgetProjet** + **LigneBudgetProjet** (categorie materiel/main_oeuvre/sous_traitance/divers, montant_prevu, optional quantite/pu) + `selectors.budget_total` (total + par_categorie, all 4 categories present); ViewSets `budgets/`, `lignes-budget/` + a `/total/` action. Migration gestion_projet/0013. **PROJ22** adds `selectors.couts_engages_vs_reels` — committed/actual project cost vs the PROJ21 budget per category (labour from internal AffectationRessource quantized to 2dp; matériel/sous-traitance via ProjetLien with graceful degrade — no cross-app amount selector exists yet), écart + écart % (divide-by-zero guarded), at `projets/{id}/couts-engages-reels/`. No model.

### qhse — quality / health / safety / environment (QHSE1, new app)  *( `/api/django/qhse/` )*
- NCR/CAPA (non-conformities + corrective/preventive actions), `company`-scoped. **QHSE2** adds the ITP (inspection & test plan) templates: **PlanInspectionModele** (code/nom/actif) + **PointControleModele** (FK plan; `phase`, `type_releve` mesure/visuel/document/essai, `hold_point` bool, `ordre`). ViewSets `plans-inspection/`, `points-controle/` (company forced server-side; a point is validated to share its plan's company → 400 otherwise). **QHSE3** adds an idempotent `seed_itp_solaire` management command (per-company or `--company`) seeding 3 solar ITP templates (résidentiel réseau / autoconsommation indus-com / pompage agricole), 7 points each, hold-points on Raccordement + Mise en service. **QHSE4** adds the APPLIED instance: **PlanInspectionChantier** (FK template `PlanInspectionModele`, `chantier_id` string-FK, `statut`) + **ReleveControle** (FK point; `valeur`, `conforme` NullBoolean, `photo_key` MinIO, `releve_par`); `services.instancier_plan_chantier` materialises one relevé per template point (idempotent, backfills). ViewSets `plans-chantier/` (+ `instancier`), `releves/`. `IsResponsableOrAdmin`-gated. **QHSE19** adds **RetourClientQualite** (client quality satisfaction): `note_satisfaction` 1–5 + `commentaire`, string-id cross-app links `chantier_id`/`client_id` (no model import), `traite` bool, `selectors.satisfaction_moyenne` + ViewSet `retours-client/` (+ `moyenne/` action, `?chantier_id`/`?traite` filters). **QHSE20** adds `selectors.iso9001_readiness` — a read-only « ISO 9001 readiness » dashboard: weighted global score + 6 criteria mapped to ISO 9001:2015 clauses (NCR closed 10.2, CAPA on-time 10.2, audits 9.2, procedures published 7.5, ITP coverage 8.5/8.6, client satisfaction 9.1.2), divide-by-zero guarded, at `iso9001-readiness/` (responsable/admin). No model. **QHSE21** adds **EvaluationRisque** (document unique d'évaluation des risques: `reference` `DUER-` race-safe, `statut` brouillon/validee/archivee, string-ref `chantier_id`) + **LigneEvaluationRisque** (poste/activité/danger, `gravite`×`probabilite` (1–5) = stored `criticite`, mesures, risque résiduel). ViewSets `evaluations-risque/` (+ `criticite/` summary), `lignes-evaluation-risque/`, role-gated. Migration qhse/0014. **QHSE22** adds the document-unique gate: `selectors.document_unique_valide(company, chantier_id)` (True iff ≥1 validated EvaluationRisque with lines) + `services.exiger_document_unique` (raises `ValidationError` — consumed by `installations` to gate the pose transition) + endpoint `evaluations-risque/document-unique-statut/?chantier_id=`. chantier_id is a string-ref (no installations import). No model. **QHSE23** adds **PermisTravail** (work permit: hauteur/consignation_elec/point_chaud/espace_confine, server-set race-safe `PT-` reference, string-ref `chantier_id`, validity dates, `valider`/`cloturer` actions). ViewSet `permis-travail/`. Migration qhse/0015. **QHSE24** adds **ConsignationLoto** — a lockout-tagout electrical-isolation record on a QHSE23 `PermisTravail` (point de consignation, cadenas/étiquette, vérif absence tension, server-set race-safe ref, statut consignée/déconsignée) with a `deconsigner` action. ViewSet `consignations-loto/`. Migration qhse/0016.

### contrats — contracts (CONTRAT1, new app)  *( `/api/django/contrats/` )*
- **Contrat** (`company`-scoped). **CONTRAT3** adds **PartieContrat** (`company` + `contrat` FK `related_name='parties'`; `type_partie` client/prestataire/temoin/garant/autre, `nom`, `fonction`, `email`, `telephone`, `ordre`) — the parties/signatories of a contract. ViewSet `parties/` (CRUD, `?contrat=` filter; a party is validated same-company as its contract → 400). The "≥2 signatories" rule lives in `Contrat.valider_parties()` for finalization (not enforced at create). **CONTRAT4** adds **ContratLien** (string-FK devis/lead/installation/maintenance, like ProjetLien) with `selectors.liens_enrichis` enriching via function-local `ventes`/`crm`/`installations` selectors (sav degrades to stored label). **CONTRAT5** adds `Contrat.sav_contrat_maintenance_id` (PositiveInteger, string-id to `sav.ContratMaintenance` — additive, no sav import, validation deferred until a sav selector exists). **CONTRAT6** adds `Contrat.confidentialite` (public/interne/confidentiel, default interne) — CONFIDENTIEL contracts are visible only to Administrators, gated in `get_queryset` on the authoritative `user.menu_tier` (not the unreliable `role_legacy`/Role-FK divergence). `IsResponsableOrAdmin`-gated. **CONTRAT13** adds **RegleApprobation** (approval rule by `type_contrat` and/or `montant_min`/`montant_max` bounds + `niveau_approbation`/`nombre_approbateurs`/`priorite`/`actif`) with `selectors.resoudre_regle_approbation` (most-specific wins: exact type > narrowest bounded interval > priorité > id). ViewSet `regles-approbation/` + `GET /resoudre/?montant=&type_contrat=`, company forced server-side (never body-set). **CONTRAT14** adds **EtapeApprobation** (internal approval workflow): `services.lancer_workflow_approbation` instantiates one step per the matching RegleApprobation's `nombre_approbateurs` (via the `resoudre_regle_approbation` selector), and `approuver_etape`/`rejeter_etape` advance it sequentially (out-of-order → 400, relaunch refused). Statuses are local (en_attente/approuve/rejete) and the workflow **never mutates `Contrat.statut`**. Actions `contrats/{id}/lancer-approbation|etapes-approbation|approuver-etape|rejeter-etape`. **CONTRAT15** adds **ContratActivity** (chatter/journal): auto-logs statut/confidentialité transitions + the approval-workflow steps (LOG, with `field`/`old_value`/`new_value` snapshots in TextField) plus manual notes; actions `contrats/{id}/historique` (most-recent-first timeline) + `noter`. Acting user + company always server-side. **CONTRAT16** adds **SignatureContrat** (in-app e-sign, loi 53-05 typed name): `signataire_nom` + server-side evidence (`ip_adresse`/`user_agent`/acting user), `role_signataire`, `methode`; `services.signer_contrat` records it, logs via the chatter, and flips `Contrat.statut`→signé through the existing state machine **only when all required parties (client+prestataire) have signed**. Unique `(contrat, role_signataire)`. Actions `contrats/{id}/signer|signatures`. No external e-sign provider. Migration contrats/0013. **CONTRAT17** chains an auto signé→actif: once all required parties have signed, `signer_contrat` advances the contract to `actif` via the existing state machine **iff `date_debut` is null or ≤ today** (future start stays `signe`), logged in the CONTRAT15 chatter (`today` injectable). No model. **CONTRAT18** adds **VersionContrat** (immutable contract-render versioning): server-incremented `version` (`select_for_update` max+1, never count()+1), frozen `contenu` + optional MinIO `fichier_key`; `services.creer_version` snapshots on demand + auto-snapshots on the signé transition (best-effort, CONTRAT16/17 preserved); read-only retrieval viewset `versions/` (paginated). Migration contrats/0014.

### kb — knowledge base (KB1, new app)  *( `/api/django/kb/` )*
- **KbArticle** (`company`-scoped; `statut` brouillon/publie/obsolete). **KB2** adds **KbArticleVersion** (`company` + `article` FK `related_name='versions'`; server-incremented `version` via `select_for_update` — never count()+1; `titre`/`contenu`/`auteur` snapshot). Actions `articles/{id}/publier/` (statut→publie + snapshot) and `articles/{id}/nouvelle-version/`; a version is also snapshotted on every article update. Read-only `versions/` viewset (company-scoped, `?article=` filter). **KB3** adds full-text-ish search (`?search=` over titre/corps/categorie/tags) + `?categorie=`/`?tag=`/`?statut=` filters on the article viewset, applied after company scoping (no cross-tenant leak; reuses existing fields, no migration). **KB4** adds **KbArticleLien** (string-FK produit/equipement/type_intervention, like ContratLien) with selector enrichment (produit via `stock.selectors`; others degrade) + a reverse lookup `article-liens/articles/?type_cible=&cible_id=`. **KB7** adds **KbArticleAcl** (role-tier ACL, niveau lecture/edition) + **KbLecture** (read tracking). `selectors.visible_articles_qs` filters the article queryset by ACL — **backward-compatible: an article with no ACL row stays visible to all, admin always sees all**; `marquer-lu` (idempotent) + `resume-lecture` actions + ACL management viewset `article-acls/`. Migration kb/0005.

### litiges — disputes / claims (LITIGE1, new app)  *( `/api/django/litiges/` )*
- **Reclamation** (`company`-scoped; `statut` ouverte/en_traitement/resolue/rejetee). **LITIGE2** adds a server-enforced state machine (actions `prendre-en-charge`/`resoudre`/`rejeter`, illegal transitions → 400; statut read-only outside actions) plus a chatter **ReclamationActivity** (`company` + `reclamation` FK; `type` log/note, `old_value`/`new_value`/`message`/`auteur`) — auto-logs each transition and manual notes via `noter/`; timeline via `historique/`. Acting user + company always server-side. **LITIGE6** adds `selectors.tableau_bord_litiges(company, debut, fin)` — a disputes dashboard aggregating existing Reclamation data: counts by statut, total `montant_conteste`, and average resolution delay (from the `resolue` chatter log, divide-by-zero guarded → None), at `reclamations/tableau-bord/`. No model.

### core — foundation layer (events bus, signing, AI scorers, BPM engine)  *(`backend/django_core/core`, NOT under apps/)*
The base layer everything depends on and that imports no domain app (import-linter `core-foundation-is-a-base-layer`). Holds `events.py` (the Django-signal domain-event bus, M6), `signing`, and PURE stateless scorers fed data as input — `forecast.py` (FG361), `win_probability.py` (FG362), `churn_risk.py` (FG363), `stock_reorder.py` (FG364), `payment_delay.py` (FG365), `anomaly.py` (FG360 `AnomalyFlag`). **FG366** adds a generic **BPM/workflow engine**: `WorkflowDefinition` + `WorkflowStepDefinition` (templates), `WorkflowInstance` (runs on ANY model via a `contenttypes` GenericForeignKey — no domain import) + `WorkflowStepInstance` (per-step statut, `sla_echeance` = start + `sla_heures`, assignee). `core/workflow.py` services `demarrer_workflow`/`avancer`/`approuver_etape`/`rejeter_etape`/`escalader_etape` + selector `etapes_sla_depassees(company, now)` (now injected) + a `escalate_workflow_sla` management command. All `company`-scoped. Migration core/0002. **FG367** adds `core/rules.py` — a generic multi-criteria rule engine (no model): `evaluate_condition_group(group, context)` (nested AND/OR/NOT tree; 11 leaf operators eq/ne/gt/gte/lt/lte/in/not_in/contains/startswith/exists; short-circuit; missing-field tolerant; never raises), `validate_condition_group` (structural errors), `sequential_actions` (ordered stop-on-error helper). Reusable by `apps/automation`'s rules (wiring deferred). **FG368** adds `core/jobs.py` + **ScheduledJobViewSet** (`/api/django/core/jobs/`) — introspects the Celery `current_app.conf.beat_schedule` (+ optional django-celery-beat) into a normalized job list, with an admin-only `jobs/run/` manual trigger (`send_task`, broker-down → 503). Jobs are global infra (no company scoping), `IsAdminRole`-gated, no new dependency. core's first URLConf (`core/urls.py`, wired into the root). **FG369** adds `core/workflow_templates.py` — a pure-data catalogue of pre-built workflow templates (relance devis, onboarding chantier, rappel garantie) + idempotent `installer_modele_workflow(company, code)` materializing the FG366 `WorkflowDefinition`/`WorkflowStepDefinition` per company, exposed via `WorkflowTemplateViewSet` (list any-auth / `installer` admin-responsable) on `core/urls.py`. No new dependency; core stays foundation.

### FastAPI AI service (`backend/fastapi_ia`, root_path `/api/fastapi`)
JWT-protected, key-gated. `GET /health`; `/ocr/*` (Zhipu bill/invoice OCR →
structured data, `ZHIPU_API_KEY`); `/sql-agent/*` (LangChain natural-language→SQL,
SELECT-only, tenant-filtered, pgvector table routing, Redis history; `GROQ_API_KEY`
or OpenAI/Anthropic via `SQL_AGENT_PROVIDER`). Group R/S additions: `/sql-agent/confirm` (run a stashed propose→confirm action by signed token), registry-driven agent tools built from the Django `/api/django/agent/actions/` catalogue with proposals surfaced on `/query`, `/sql-agent/transcribe` (Groq `whisper-large-v3` assistant voice, reuses `GROQ_API_KEY`), and `/chat/transcribe` (self-hosted `faster-whisper` for chat voice memos, behind `CHAT_TRANSCRIPTION_ENABLED`, lazy model load).

---

## 5. Frontend, feature by feature

SPA built with React 19 + Redux Toolkit + react-router 7 + Tailwind 4. `features/`
holds Redux slices and domain logic; `pages/` holds screens; `api/` holds one axios
module per backend area. The **design system** (refonte UI) lives in `design/`
(tokens + theme), `lib/` (cn + format utils), and `ui/` (primitives) — see below.

### Routes (`frontend/src/router`)
| Path | Page |
|---|---|
| `/` , `/login` | Login |
| `/landing` | Landing (marketing) |
| `/ui` | UIShowcase — design-system reference (refonte UI, public, no auth) |
| `/dashboard` | Dashboard |
| `/crm` | ClientList |
| `/crm/leads` | LeadsPage (kanban / list / calendar / charts) |
| `/activites` | MesActivitesPage |
| `/calendrier` | CalendarPage (agenda) |
| `/crm/parrainage` | ParrainagePage (referrals) |
| `/ventes/devis` | DevisList |
| `/ventes/devis/nouveau` | DevisGenerator (quote creation) |
| `/ventes/bons-commande` | VentesKanban |
| `/ventes/factures` | FactureList |
| `/ventes/avoirs` | AvoirsPage |
| `/ventes/relances` | RelancesPage |
| `/chantiers` | InstallationsPage |
| `/interventions` | InterventionsPage (field-execution list + kanban) |
| `/ma-journee` | MaJourneePage (technician day view — F22) |
| `/outillage` | OutillagePage (durable tools) |
| `/production` | ProductionPage (monitoring readings — N51) |
| `/parc` | ParcInstallePage (installed fleet) |
| `/equipements` | EquipementsPage |
| `/sav` | TicketsPage |
| `/sav/contrats` | ContratsMaintenance |
| `/stock` | StockList |
| `/stock/mouvements` | MouvementsPage |
| `/stock/bons-commande-fournisseur` | BonsCommandeFournisseur |
| `/stock/ocr-import` | OcrStockImport |
| `/ia/agent` | AgentChat |
| `/ia/ocr` | OcrUpload |
| `/reporting`, `/rapports` | Reporting / Rapports |
| `/reporting/balance-agee` | BalanceAgeePage |
| `/reporting/archive/client|chantier/:id` | Archive pages |
| `/admin/users`, `/admin/roles` | UsersManagement / RolesManagement |
| `/parametres` | ParametresEntreprise |
| `/parametres/notifications` | NotificationsPreferences (per-event channel toggles — N75) |
| `/journal` | Journal (activity log — nav item & page gated on `journal_activite_voir`) |

### Features (`frontend/src/features`)
- **auth** — session/JWT; `authSlice.js` (fetchMe, login/logout thunks).
- **crm** — leads/clients state; `crmSlice.js`, `bulk.js` (selection logic), `stages.js` (mirrors STAGES.py + CONVERSION_STAGE — CI-checked).
- **ventes** — quotes/invoices/credit notes; `ventesSlice.js`, **`solar.js`** (solar math + auto-fill for the quote generator: GHI/ONEE/ROI, panel/inverter/battery sizing, pompage HMT+débit→pump+VEICHI variateur, all TTC), `autoQuote.js`, `PdfCanvas.jsx`, `previewPdf.js`.
- **installations** — chantiers; `installationsSlice.js`, `statuses.js` (stage constants).
- **stock** — catalogue/inventory/procurement; `stockSlice.js`, `catalogue.js`, `emplacements.js`, `procurement.js`.
- **sav** — equipment + tickets; `equipementsSlice.js`, `ticketsSlice.js`, `ticketStatuses.js`.
- **reporting** — dashboards/insights; `reportingSlice.js`.
- **parametres** — settings/templates; `parametresSlice.js`.
- **ia** — AI assistant chat (registry-driven actions with propose→confirm + result cards, voice input + hands-free « Mode conversation » with a no-auto-confirm guard) + OCR; `iaSlice.js`, `voice/useVoiceChat.js`, `voice/conversationLoop.js`.
- **messaging** — internal team chat « Discuss »; `store/messagingSlice.js`, `useChatPolling.js` (visibility-aware smart polling), conversation-list/thread/composer/voice/reactions/share-record components.
- **pwa** — auto-update service worker UI; `PwaPrompts.jsx`.

### Pages (`frontend/src/pages`)
- **crm/** — ClientList, LeadForm, LeadsPage, ParrainagePage + `leads/` (ViewSwitcher, FilterBar, BulkActionBar, DoublonsPanel, SigneDialog, views/Kanban|List|Calendar|Charts).
- **ventes/** — DevisList, DevisGenerator, DevisForm, FactureList, FactureForm, AvoirsPage, RelancesPage, VentesKanban.
- **stock/** — StockList, ProduitForm, MouvementsPage, BonsCommandeFournisseur, OcrStockImport.
- **installations/** — InstallationsPage, ParcInstallePage, InstallationDetail, ChantierChecklist/Photos/Timeline.
- **sav/** — EquipementsPage, TicketsPage, ContratsMaintenance.
- **reporting/** — ArchiveClientPage, ArchiveChantierPage, BalanceAgeePage, DocumentsArchive.
- **admin/** — UsersManagement, RolesManagement. **parametres/** — ParametresEntreprise (Société tab now carries the editable RIB/Instructions de paiement/Conditions générales block; Équipe tab is the supervisor/team editor). **activities/** — MesActivitesPage. **ia/** — AgentChat (actions cards + voice/conversation mode), OcrUpload. **messaging/** — ChatPage (two-pane « Discuss »). Top-level: Dashboard (incl. "Chantiers par statut" chart), **Journal** (activity log), CalendarPage, Landing, Login, Reporting, Rapports.

### API modules (`frontend/src/api`)
`ventesApi`, `crmApi`, `stockApi`, `installationsApi`, `savApi`, `reportingApi`,
`iaApi` (→ FastAPI), `parametresApi`, `rolesApi`, `customFieldsApi`,
`documentsApi`, `recordsApi`, `messagesApi` (→ `/api/django/chat/`) — one per backend area listed in §4.

### Design system — refonte UI (`frontend/src/design`, `lib`, `ui`)
"Prettier-than-Odoo" overhaul (PLAN2 groups F+G). **Additive — existing screens
unchanged** until migrated screen-by-screen (groups J/P); custom token names, no
Tailwind default or global body font overridden, no `dark:` used elsewhere.
- **`design/`** — `tokens.css` (Tailwind 4 `@theme`: brand brass/nuit/azur/lune →
  semantic light+dark tokens + density), brand fonts (Archivo/Hanken via
  `public/fonts/brand.css`), `theme.js` + `ThemeProvider`/`ThemeToggle`
  (clair/sombre/système, défaut système).
- **`lib/`** — `cn.js` (clsx+tailwind-merge), `format.js` (MAD / fr-FR / dates /
  tél. MA — one source of truth).
- **`ui/`** — shadcn/Radix primitives: Button/IconButton/Spinner, Input/Textarea/
  Label/Number·Currency·Percent·Phone, Checkbox/Radio/Switch/Segmented/Slider,
  Select/Combobox/MultiSelect, DatePicker/DateRangePicker/TimePicker (calcul de
  dates maison, sans librairie), FileUpload/dropzone, Form system (Form/FormSection/
  FormField/FormActions + useDirtyGuard),
  Dialog/Sheet/AlertDialog/Popover/Tooltip/DropdownMenu/HoverCard/ContextMenu,
  Toaster(sonner)/Badge/StatusPill/Tag/Avatar/Card/Stat/Tabs/Accordion/Progress/
  Separator/DefinitionList, Skeleton/EmptyState/ErrorBoundary/NotFound/Offline.
  **`ui/datatable/`** — reusable `<DataTable>` engine (TanStack Table): sort/filter/
  column-management/pagination/inline-edit/bulk-bar/saved-views/URL-persistence/
  virtualization/CSV+XLSX-export/mobile-cards — engine only, demoed at `/ui`, not yet
  wired into list screens (that is Group J). Living reference at route `/ui`
  (`pages/ui/UIShowcase.jsx`, `pages/ui/DataTableDemo.jsx`). Deps (all already
  present): @radix-ui/*, @tanstack/react-table, lucide-react, sonner,
  cva/clsx/tailwind-merge.

---

## 6. Core data flow (one record, end to end)

```
crm.Lead ──(devis.lead, devis.client)──▶ ventes.Devis ──┬─(bon_commande.devis)─▶ ventes.BonCommande
   │ stage: NEW…SIGNED                  statut: accepte │                          statut: livre → stock−
   │ perdu/motif_perte                                  └─(facture.devis)────────▶ ventes.Facture
   │                                                                                type: acompte/solde/…
   │                                                          Paiement.facture ─────┤  montant_du = TTC−paid−avoirs
   │                                                          Avoir.facture ────────┘
   ▼
ventes.Devis ──(installation.devis / .lead / .bon_commande / .client)──▶ installations.Installation
                                                                          statut: SIGNE…CLOTURE, bom(JSON)
                                                                                   │
                          (equipement.installation, equipement.produit→stock.Produit, numero_serie)
                                                                                   ▼
                                                                          sav.Equipement (warranty clock)
                                                                                   │
                                  (ticket.equipement / .installation / .client)    ▼
                                                                          sav.Ticket  statut: NOUVEAU…CLOTURE
```

1. **Lead** (`crm.Lead`) — captured (native, import, or website webhook). Funnel via `stage` (STAGES.py); lost via `perdu` + `motif_perte` independent of stage.
2. **Devis** (`ventes.Devis`) — carries `lead` FK→Lead **and** `client` FK→Client; the client is resolved from the lead server-side (`apps/crm/services.resolve_client_for_lead` — reuse, else company-scoped email match, else create). `statut` walks brouillon→envoye→accepte. Accepting captures `option_acceptee` and advances the lead's `stage` to **SIGNED** (the conversion event).
3. **BonCommande** (`ventes.BonCommande`) — `devis` OneToOne→Devis; marking it `livre` decrements stock via `MouvementStock`.
4. **Facture** (`ventes.Facture`) — linked by `devis` FK (échéancier path) and/or `bon_commande` OneToOne (legacy). `type_facture` = acompte / intermediaire / solde / complete. **Paiement.facture** records payments; **Avoir.facture** records credit notes; `montant_du = total_ttc − montant_paye − avoirs_total`.
5. **Installation/Chantier** (`installations.Installation`) — created from the quote (`creer-depuis-devis`); links back via `devis`, `bon_commande`, `lead`, `client` FKs; freezes the quote's bill of materials into `bom` (JSON); `statut` SIGNE→…→CLOTURE.
6. **Equipement** (`sav.Equipement`) — registered during the chantier checklist (steps with `capture_serie`); links `installation` FK and `produit` FK→stock.Produit with `numero_serie`; warranty end dates computed from `date_pose`.
7. **SAV Ticket** (`sav.Ticket`) — links `equipement` FK (and/or `installation`, `client`); `statut` NOUVEAU→…→CLOTURE; `sous_garantie` computed from the equipment's warranty clock.

---

## 7. Hard contracts and policies

All verified against source, not prose.

- **Pipeline stages come from `STAGES.py`** (repo root) — the canonical 6 keys are
  `NEW, CONTACTED, QUOTE_SENT, FOLLOW_UP, SIGNED, COLD` (French labels in the same
  file: Nouveau/Contacté/Devis envoyé/Relance/Signé/Froid). `crm.Lead.stage` uses
  these keys; the frontend mirror is `features/crm/stages.js`. CI job `stage-names`
  runs `scripts/check_stages.py` and fails on any divergence.
- **"Perdu" is a lost-flag, not a stage** — `crm.Lead.perdu` (bool) + `motif_perte`
  can be set from any stage, independent of `stage` (documented in STAGES.py lines
  8–10).
- **Entering SIGNED is the conversion event** — STAGES.py marks `CONVERSION_STAGE =
  SIGNED` and reserves the `SIGNED_QUOTE_CAPI_HOOK` sentinel for the future Meta
  CAPI "SignedQuote" emitter.
- **Buy prices never appear on client-facing PDFs** — `stock.Produit.prix_achat`
  (and `PrixFournisseur.prix_achat`, `BonCommandeFournisseur` buy lines) are
  internal/generator-only. The quote engine's `builder.py` passes only sell-side
  `prix_unitaire`; `apps/ventes/tests/test_quote_engine.py` asserts `prix_achat`
  never appears in rendered PDF HTML. `Produit.prix_achat` also powers the
  admin-only `reporting/insights/job-costing/` margin view — never a client output.
- **`/proposal` is the only client-facing quote-PDF path** — canonical endpoint
  `GET /api/django/ventes/devis/<id>/proposal/`, rendered by the vendored
  `quote_engine/generate_devis_premium.py`. `generer-pdf` (async Celery) routes
  through the same engine (toggle `USE_PREMIUM_QUOTE_ENGINE`). The legacy
  WeasyPrint quote PDF remains only as the off-switch fallback. (Invoices keep
  their own separate legacy PDF.)
- **Multi-tenant scoping** — the tenant field is **`company`** (FK →
  `authentication.Company`) on every business model; there is **no** field named
  `tenant_id`. ViewSets filter `get_queryset()` by `request.user.company` and
  force-assign `company` in `perform_create`/`perform_update` (never from the
  request body).
- **CI status checks that gate a merge** — `.github/workflows/ci.yml` defines
  **eight** jobs. It triggers on every `pull_request` and on pushes to
  **`main`/`dev`** only: feature/PR branches run once via their PR (where the
  `changes` detector diffs against the base, so config/docs-only changes skip
  the heavy jobs), and a `pull_request`-scoped `concurrency` group cancels a
  superseded PR run while pushes to `main`/`dev` always finish. A `changes`
  detector (pure-git, fails open) resolves which
  surfaces a push/PR touched and exposes `backend`/`frontend`/`web`/`code`
  outputs; the heavy/lint jobs are then **path-filtered per-job** via `if:` on
  those outputs (a skipped *job* reports "Success" to branch protection, so it
  never deadlocks — unlike a top-level `on: paths` filter, which is
  deliberately NOT used). A change that touches only CI/infra/docs/config
  (`.github/**`, `docker-compose*`, docs, `*.md`, `.gitignore`, `.claude/**`,
  top-level state) triggers **none** of the heavy jobs — only the always-on
  `stage-names` guard runs; the detector still falls open to the FULL suite when
  the diff range is unresolvable (new branch / force-push / shallow clone). The
  work jobs are: `backend-lint` (flake8) and
  `backend-tests` (Postgres+pgvector + Redis + MinIO; runs
  `python manage.py test apps authentication`) — both run when `backend/**` or
  `STAGES.py` changed; `frontend-lint` (eslint + node `--test`
  solar/catalogue/stages parity) — runs when `frontend/**` or `STAGES.py`
  changed; `web-build-test` (apps/web astro build + vitest) — runs when
  `apps/web/**` changed; `e2e` (Playwright, 16 flows) — the cross-surface net,
  runs whenever **any** application code changed (`backend/**`, `frontend/**`,
  or `STAGES.py`), skips on website-only, docs-only, and CI/infra/config-only
  changes. `stage-names`
  (`scripts/check_stages.py` **plus** `scripts/codemap_fingerprint.py --check`,
  which fails the build when this CODEMAP is stale vs the structural surface) is
  **ungated** — it is fast and is the broad drift guard, so it runs on every PR
  and on every push to `main`/`dev` (docs/plan, STAGES.py, structural). Finally `ci-gate` is an
  **always-running aggregate** (`if: always()`, `needs:` all jobs) that fails
  only when a job that actually ran failed or was cancelled — a skipped job is
  acceptable — so a single required status check can be pinned on `main` without
  deadlocking on path-filtered skips. CLAUDE.md designates the four
  lint/test/stage-name jobs as the required merge gate (0 approvals,
  merge-commit self-merge); see §9 for the `web-build-test`/branch-protection
  caveat.

---

## 8. Known discrepancies (prose vs code)

Each line is a place a prose doc says something the **code contradicts**. Code wins.

1. **App inventory is understated.** `CLAUDE.md` repo-facts lists apps
   "authentication, stock, crm, ventes, reporting, parametres, roles, contact" (8),
   and `README.md` frames the system as "five core modules + extras." The code has
   **13 apps under `apps/`** plus the top-level `authentication` package — including
   full **`installations`** (chantiers/field execution), **`sav`** (equipment +
   tickets + maintenance contracts), **`records`**, **`customfields`**,
   **`documents`**, and **`dataimport`** that the headline lists omit.
2. **`authentication` is not under `apps/`.** Prose lists it alongside the other
   apps, but it actually lives at `backend/django_core/authentication/` (top-level
   package), and the backend-tests CI command runs `test apps authentication`
   specifically because it sits outside `apps`.
3. **Quote engine swap already landed.** `README.md` says the quote-generation
   logic is "slated for replacement by an external tool." In the code the swap is
   **done**: the premium engine is vendored at `apps/ventes/quote_engine/` and
   `/proposal` is already the canonical path (matching CLAUDE.md rule #4, which is
   current; the README line is stale).
4. **CI has eight jobs, not four.** CLAUDE.md and README describe four checks
   (lint/tests/frontend-lint/stage-names). `ci.yml` actually defines eight: those
   four plus `web-build-test` (Astro build + vitest for `apps/web`), `e2e`
   (Playwright browser suite), a `changes` path-detector, and an always-on
   `ci-gate` aggregate. The four named checks are still the policy merge gate;
   whether any are branch-protection-*required* is not visible from the repo
   (see §9), but all eight jobs exist and run subject to per-job path filtering.
5. **README CI description is incomplete.** README says CI "runs flake8, eslint, the
   Django test suite, and a stage-name check" — it omits the frontend node `--test`
   parity suite and the `web-build-test` job that the workflow actually runs.
6. **"tenant_id" is not a real field.** Any reference to a `tenant_id` column is
   nominal only — the actual multi-tenant field everywhere is `company`.
7. **Reporting "no models" — confirmed, not a discrepancy.** README's claim that the
   reporting app has no models of its own is **correct** against the code (listed
   here so a reader doesn't re-flag it).

If you find no discrepancy in an area not listed above, assume none was found there
rather than that it was checked and cleared.

---

## 9. Staleness markers

Things this map could not fully verify from source — do not over-trust:

- **Which CI jobs are "required".** The eight job names come from `ci.yml`, but the
  GitHub **branch-protection** "required status checks" set is configured in
  GitHub, not in the repo, so it is not verifiable here. This map repeats CLAUDE.md's
  "first four are required" claim as policy, not as a code-verified fact. The
  `ci-gate` aggregate is built so the founder *can* later pin one always-running
  required check safely; whether they have is likewise not visible from the repo.
- **Per-app endpoint spellings.** Model names, FK targets, status/flag values, the
  root URL prefixes, the CI workflow, STAGES.py, compose, and the version pins were
  read directly. The **custom `@action` endpoint paths in §4** were collected by
  reading each app's `urls.py` via exploration agents; the high-impact ones
  (`/proposal`, `generer-pdf`, root prefixes) were double-checked, but exact
  spellings of less-critical actions should be re-confirmed against the relevant
  `urls.py` before relying on them programmatically.
- **OCR provider client.** OCR is key-gated by `ZHIPU_API_KEY` and uses Zhipu/GLM
  vision per config, but no Zhipu SDK is pinned in `fastapi_ia/requirements.txt`
  (called over HTTP) — the exact client is unconfirmed.
- **Provenance window.** Generated from `main` at commit `3267341`. Work merged
  after that commit (and any in-flight feature branches) is not reflected until this
  file is regenerated. Regeneration is wired into the plan-execution rules in
  `CLAUDE.md` (regenerate when a run changed models, endpoints, routes, or module
  structure) and is now self-enforcing: the `Structure fingerprint:` header above is
  a SHA-256 over the structural surface, recomputed by the required `stage-names` CI
  job (`scripts/codemap_fingerprint.py --check`); a structural change that does not
  refresh this map — and re-run `--write` — fails CI and cannot merge.
- **Plan-status freshness.** §10 (Plan status) is a *second* self-enforcing surface:
  the `Plan fingerprint:` header is a SHA-256 over every `docs/PLAN.md` /
  `docs/PLAN2.md` task's `(file, id, done/open/blocked)` state, recomputed by the
  same `stage-names` CI job. Ticking, adding, or removing a plan task without
  refreshing §10 (and re-running `--write`) fails CI. The Done/Open/Blocked lists
  themselves are produced verbatim by `codemap_fingerprint.py --print-plan-status`;
  the cross-check-vs-`main` notes are the agent's, refreshed in the same pass.

---

## 10. Plan status

Live build state of the execution queues — `docs/PLAN.md` (T*, N*, F*, M*, **FG*** module-gap +
functional-domain expansion audit, **PAIE*/COMPTA*/PROJ*/GED*/FLOTTE*/QHSE*/CONTRAT*/KB*/LITIGE***
new-module deep-dive backlogs, **DC*** data-connectivity / single-source-of-truth audit, **ENG*** Meta-ads engine in-ERP),
`docs/PLAN2.md` (A*–E*, F*–P* UI/UX, G*/Q*/R-AG*/S* feature groups, **U*** field-UX + document-status "connection" fixes), and `docs/ERROR_PLAN.md` (ERR* bug backlog) — read from their
BUILD QUEUE task boxes and cross-checked against `main`; completed tasks are archived verbatim in
`docs/DONE.md`. Refreshed by the `claude/sad-euclid-12071c` run on 2026-07-03 (226 PLAN.md
tasks in ONE merge: backend lane-drain across ~25 apps — compta/rh/paie/qhse/ged/flotte/
gestion_projet/kb/sav/ventes/stock/installations/crm/notifications/pos/contrats/reporting/
automation/customfields — via parallel worktree lanes + per-app 2nd-round continuations;
combined local docker test of 1948 tests caught 106 failures → 67 real bugs fixed by 8 repair
agents; added PyMuPDF==1.28.0 for GED PDF features; ODX13 + XFSM16/17 left `[ ]` as blocked),
on top of the prior `claude/lucid-banzai-33af1c` PLAN.md drain. This section is guarded by the
`Plan fingerprint:` header at the top of the file: the required `stage-names` CI job runs
`scripts/codemap_fingerprint.py --check`, which recomputes a SHA-256 over every task's
`(file, id, done/open/blocked)` state — so ticking, adding, or removing a plan task without
refreshing this section fails CI, exactly like the structure fingerprint guards the body. The
Done/Open/Blocked lists below are produced verbatim by `python scripts/codemap_fingerprint.py
--print-plan-status`; regenerate them and re-run `--write` whenever task states change.

**Totals: 1982 tasks — 1833 done · 147 open · 2 blocked.** (2026-07-07 `claude/sleepy-haibt-df777f` ADD-TO-PLAN « Groupe VX — le plus bel ERP du monde » — appended PLAN2 **Groupe VX (VX1–VX47) : +47 open tasks** from a 16-agent model-tiered audit (9 repo-read lanes over the design system / shell / every screen area + 5 web-research lanes on Odoo 18/19, Linear/Attio/Stripe, data-viz craft, delight/motion, field-service UX + an anti-duplication coverage map over ALL plans — Opus/Sonnet/Haiku fleet, ONE Fable synthesis, ONE Fable completeness critic whose 10 confirmed fixes + 2 white-space finds VX46/VX47 were drafted in). The founder's « modules façon Odoo ? » question is answered in the group header: KEEP + FINISH the queued ODX split (never re-merge) — the missing piece is the frontend « apps » experience the group builds (per-module OKLCH accents, light app launcher, pinned apps, breadcrumb→cockpit, module-aware search/notifications) ON TOP of ODX5/6/7, never duplicating them. Vision « Lumière sur Nuit »: one gold + one navy (today FOUR golds/THREE navys coexist), the shell becomes the brand, brand type reaches <body>, full legacy dark mode, calm-color weighting, data-typography `.num`, money-path polish (generator summary rail, the orphaned DevisPresetPanel finally wired, zero browser popups, action menus), CRM at Attio level (real `/crm/leads/:id` page, ChatterTimeline beating Odoo's chatter, 2-level kanban cards, tokenized stage COLORS with STAGES.py keys untouched), role-aware morning dashboard + living solar-fleet wall (stale ≠ zero), operations islands (CartePage/MapView, Pilotage stock), signature login, 22-tab settings → grouped IA, streaming AI chat, permissions matrix, OCR side-by-side correction, ONE measured celebration (devis signé) + illustrated empty states, native field gestures (one-tap call/navigate, FAB, haptics, swipe, pull-to-refresh, burst photos, native WhatsApp share of the EXISTING /proposal PDF), premium French microcopy, per-user preferences center, contextual HelpTips. All frontend-only, zero new npm deps, PDF templates / PdfCanvas / `/proposal` / apps/web untouched (rule #4), e2e hooks preserved. This refresh also regenerated the §10 Done/Open/Blocked lists below verbatim from --print-plan-status — they had lagged at 1091/830/2 while the header fingerprint stayed correct. Backlog additions only — nothing built or ticked; done/blocked unchanged, open 100 → 147.) (2026-07-03 `claude/objective-wozniak-d6ddcf` ADD-TO-PLAN « Round 2 — câblage, bonnes pratiques & parité profonde » — appended a 2nd PLAN.md BUILD QUEUE section: **+336 open tasks** from a ~90-agent audit pipeline (29 lanes research→audit→adversarial-review + cross-lane dedupe of 16 collisions + a completeness critic whose 11 findings were drafted in as YHARD). Where round 1 (below) inventoried missing FEATURES, round 2 attacks what a checklist can't see. **Axe A — câblage bout-en-bout (Y*, 10 processus)**: Lead-to-Cash (YCASH), Procure-to-Pay (YPROC), Install-to-Service (YSERV), Record-to-Report/exhaustivité comptable (YLEDG), Hire-to-Retire (YHIRE), intégrité des flux de stock (YSTCK), machines d'états des documents (YDOCF), Marketing-to-Lead (YLEAD), revenu récurrent (YSUBS), couverture bus d'événements/notifications/approbations/audit (YEVNT). **Axe B — bonnes pratiques mondiales (Y*, 5 lanes)**: couverture RBAC + masquage champ-niveau (YRBAC), cohérence/complétude API OpenAPI/idempotence/webhooks (YAPIC), ops/perf/résilience — sauvegardes testées/N+1/Celery (YOPSB), stratégie de test e2e-par-processus (YTEST), patterns d'intégrité des données (YDATA). **Axe C — parité profonde Odoo à grain fin (Z*, 14 apps)**: ZACC/ZFAC/ZSAL/ZPUR/ZSTK/ZMFG/ZPRJ/ZFSM/ZSAV/ZRH/ZPAI/ZMKT/ZGED/ZCTR (rapports, assistants, réglages, actions planifiées, documents imprimables manqués au round 1). **Durcissement (YHARD1-12)**: chiffrement au repos des champs sensibles, i18n du contenu saisi, reconstruction temporelle as-of, secrets/rotation, observabilité/SLO/alerting, budget perf + a11y du front ERP, clone anonymisé de staging, déploiement sans coupure, audit/rollback des actions IA + harnais d'éval. Chaque tâche cite le code réel vérifié ; additif/multi-tenant/frontières services-selectors/bus d'événements ; intégrations key-gated OFF ; `/proposal` intouché. Backlog additions only — nothing built or ticked; done/blocked unchanged, open 561 → 897.) (2026-07-02 `claude/objective-wozniak-d6ddcf` ADD-TO-PLAN « Odoo-parity audit » — appended the new PLAN.md BUILD QUEUE section « Parité best ERP du monde + découpage modules façon Odoo » : **+489 open tasks** from a 62-agent research pipeline (per-domain web research on Odoo 18/19 / SAP B1 / Dynamics 365 BC / NetSuite / ERPNext, gap-analysis against the real code AND all plans — everything in PLAN/PLAN2/DONE/ERROR_PLAN counted as already covered — per-domain adversarial anti-duplicate review, cross-domain dedupe of 36 collisions, completeness critic whose 7 findings were drafted in, incl. the stale G14 DGI e-invoicing gate → XFAC29). Groups: **ODX1–23** module split façon Odoo (module manifests/catalogue/nav-apps + sortir marketing/AO/portail/frais de compta, facturation hors de ventes, achats hors de stock — state-only 2-step moves, behavior-preserving) ; **XACC/XFAC/XPUR/XSTK/XMFG/XSAL/XMKT/XPOS/XPRJ/XFSM/XSAV/XCTR/XFLT/XQHS/XRH/XPAI/XGED/XKB/XPLT** per-domain best-ERP feature gaps (each additive, multi-tenant, selectors/services boundaries, external integrations key-gated OFF, DECISION/COST tagged for founder calls). Backlog additions only — nothing built or ticked; done/blocked unchanged, open 72 → 561.) (2026-07-01 `claude/festive-stonebraker-90495e` ADD-TO-PLAN — appended the founder's quote/journey/supplier/chantier/mobile/wiring backlog, +67 open tasks in PLAN2: **QF1–9** real-bill two-factures par-tranche savings + battery avec/sans honesty + Huawei-only Smart-Meter/Clé-Wifi; **QG1–12** PDF auto-open + « Éditer » stale-PDF cache fix, inline new-client + role-gated new-product (Directeur + Commercial responsable everywhere), creator name+phone on the quote PDF, « Envoyer » = leads-WhatsApp flow, configurable variante % (default 20), 3D roof viewer in-quote + standalone route; **QJ26–31** sanitized roof_layout in the public proposal payload (client 3D unlock for WEB_PLAN WJ25–28), client « être contacté » notifies handler + supervisor, « contacter mon supérieur » on quote generation, multi-villa quotes in ONE document (×N + grouped lines); **QS1–4** BCF PDF-button fix + inline product + real WhatsApp/email send to the fournisseur (buttons greyed when contact absent); **QD1–2** facture logo auto-trim/enlarge + clean client-bearing document filenames; **QP1–2** typed product-picker filter (inverter slots show only inverters) + line-rename restricted to Directeur/Commercial responsable with « renommer ici » vs « créer un produit » prompt; **CH1–6** chantier redesign onto the international PV lifecycle (IEC 62446-1 commissioning, handover pack) with director-configurable ENFORCED gates + a gate-timeline UX; **QK1–6** fresh 3-axis best-in-world quote-journey audit gaps (stop discarding captured lead data at the webhook, render the computed financing block, « Nos hypothèses » line, fix the dead taqinor.ma/avis PDF link, bill-photo OCR at capture); **MB1–6** mobile rendering root-cause fix (shell header/bottom-nav padding + safe-area, horizontal-overflow kills, z-index token adoption, ResponsiveDialog migration of the devis/lead modals, per-screen sweep, mobile e2e gate); **WR1–12** wire orphaned backend features from a 7-agent whole-app audit (the « Refuser » mis-wire funnel BUG, payment-link/share-link/DGI/bulk, stock intelligence FG54–66 + N97, monitoring O&M FG279–289, reporting config/cohorts + agent catalogue, RGPD FG26 + attainment FG39, installations scheduling FG74/68/73/299–301, SAV FG81/86, backend-only settings flags — the nine backend-only modules were EXCLUDED as Group-UX territory, since built via PR #300); **QC1–2** Moroccan company autocomplete on client creation (own-data fuzzy + « Vérifier » registry deep-links now; gated Inforisk/Charika licensed API later — Odoo's autocomplete is Clearbit-backed and returns no ICE/RC/IF for Morocco; scraping OMPIC is ToS-prohibited, not pursued). Website halves **WJ25–38** in `docs/WEB_PLAN.md` (not in the fingerprint surface): interactive client 3D on `/proposition/[token]` + guided explanations + perf/fallback + v3 trust elevation, « être contacté » server wiring, capture-data pass-through + best-in-world capture questions, journey i18n/a11y fixes, and the quote-button rewire — every « obtenir un devis / étude gratuite » CTA → `/devis/mon-toit`, ONE brass primary CTA + reassurance strip + EN/AR journey routes. Backlog additions only — nothing built or ticked in this batch.) (2026-07-01 `claude/plan-dsoru4` ADD-TO-PLAN — appended **Group UX (UX1–UX47)** to `docs/PLAN.md`: the frontend/React build-out for the modules that shipped BACKEND-ONLY (compta, paie, flotte, rh, qhse, contrats, gestion_projet, kb, litiges + GED advanced) and so have no screen in the ERP nav today. Research-grounded (existing `/ui` design-system anatomy + real per-module REST endpoints + 2026 best-ERP UX: KPI cockpits w/ drill-down, review-before-commit payroll run, échéance centers, master-detail + chatter, recharts). Frontend over EXISTING endpoints, additive, French, role-gated; reaches the live ERP only via `scripts/deploy-prod.ps1`. Backlog additions only — nothing built/ticked; done/blocked unchanged, open +47.) (2026-07-01 `claude/plan-dsoru4` DC-RELIQUAT — the 6 remaining `DC*` single-source tasks the prior run deferred as « prématuré » were re-checked: their consumer modules (FG56/FG131/FG228/FG304-306/FG67/FG316/FG169/299/303/FG174/176/198) are ALL built now, so the deferral was stale. **3 built + 1 already-present → ONE merge** (buildable queue genuinely exhausted): DC16 (stock — FF liée à un BCF passe par facturer-réception FG56, montants non modifiables à la main avant le rapprochement 3 voies), DC38 (stock+installations — le coût débarqué FG316 se replie dans le SEUL `average_cost_with_source` via `frais_annexes`, setter stock pur + orchestration installations→stock, action `appliquer-cout-stock`), DC32 (compta — `ComptePortailClient` lié à `crm.Client` PAR FK string-FK + email lu du client, migration 0043 réversible), DC41 (déjà présent — Conducteur/Habilitation/Certification foyers uniques, gardes FG176/198 référencent sans re-saisir). DC34/DC40 LAISSÉS `[ ]` : DECISION founder-gated (réécriture destructive de features livrées — AP sous-traitant FG304-306 ; modèle Equipe + API roster FG169), pas un ajout additif ; feu vert explicite requis. 11 tests neufs ; `/proposal` + premium PDF untouched ; core reste foundation. Détail dans DONE LOG.) (2026-07-01 `claude/keen-volhard-e65936` MEGA-DRAIN-2 — lane-draining + second-round same-app lanes (each `git merge`-inherits the integration branch to chain migrations) → **108 built + 46 verified-already-present = 154 tasks moved to done → ONE merge**. Merge floor raised to ≥200 mid-run by Reda; the whole remaining buildable backlog is < 200, so this merges under the documented exhausted-queue exception (every remaining open task is deferred-by-note / DECISION-gated / cross-app / frontend / subsumed). Built: compta FG201-241/244 + COMPTA2/3/4/9/10/11/15/16/29/39 (27 marketing/CPQ + 10 accounting; the rest of COMPTA2-40 subsumed by existing FG135-153), installations FG319-333 (warehouse/logistics), core FG370/382-399 + DC26 (payment/BI/soft-delete/formula/flags/theme/DSR/backup/health/api-usage/changelog/Moroccan-calendar), monitoring FG279-289 (O&M analytics), ventes FG276-278/287 (commissioning) + DC23, paie DC20/21/39/42, crm DC11/13, stock DC35, misc FG103/DC27/DC33/DC37/FG15. ONE combined FRESH-DB prod-docker test — real bugs fixed: serie-entrepot dup-serial 500→400, RelanceDevisAbandonne paginated-isolation assert, DC11 provenance stringified-Decimal false-positive, monitoring no-recipient fixture. REVERTED + requeued: DC1/DC25 (quote-engine regressions — RULE #4 sensitive) + DC10 (broke product-less refund lines). Local-only false-fails ignored (all green in CI's fresh per-run DB): openpyxl-missing (~32), the June→July midnight rollover freezing tests' module-level MONTH (~15), keepdb slug/PK pollution. New gated integrations (default OFF, no hard dep): BREVO/WHATSAPP/CMI/PUBLIC_SIM_LEAD/GOOGLE_REVIEW/Sentry/SolarEdge-Sungrow-Solis. `/proposal` + premium PDF untouched; core stayed foundation (import-linter 5/5); ~50 additive migrations.) (2026-06-30 `claude/keen-volhard-e65936` ULTRA-DRAIN — lane-draining method, 11 worktree agents each drained ONE app's WHOLE pending lane in sequence → **81 tasks → ONE merge** (merge floor ≥80 honored): core FG371-381, ventes FG265-275, installations FG306-318, gestion_projet PROJ23-38, parametres FG18-26, stock FG66/67+DC15/28/30/36, crm DC12/14, publicapi FG104-106, kb KB6, litiges LITIGE5, plus DC31. ~35 additive migrations; ONE combined prod-docker test (743 tests) — the review + combined test caught & fixed 11 bugs that flake8/check/import-linter passed (crm double `source=`; crm OCR-bridge `Canal` model vs `Lead.Canal`; stock `cout_achat_courant` tuple-vs-scalar; ventes missing `url_path` 404s; gestion_projet risque criticité assert; crm migration 0031 dup-leaf renumber→0032; core dashboard pagination vs flat-list; `required_documents(None)`→[]; publicapi `updated_since` ISO `+`→space 400; parametres approvals unique→400 not 500; OCR-bridge note logged with user → QJ7 advanced NEW→CONTACTED, fixed to system note). 5 openpyxl "failures" are local-only false-negatives (green in CI). NOTE FG151 left open; new cross-app reads via selectors only; `/proposal` untouched; no new external dependency.) (2026-06-30 `claude/keen-volhard-e65936` MEGA-DRAIN — lane-draining method: 6 worktree agents each drained ONE app's WHOLE pending lane in sequence → **57 tasks → ONE merge** (paie PAIE25-36, rh FG191-200, contrats CONTRAT26-35, qhse QHSE33-40, flotte FLOTTE28-35, ged GED25+31-38). 35 additive migrations; ~446 tests green in ONE combined prod-docker build; makemigrations --check + import-linter 5/5 green; the orchestrator's combined test caught + fixed 5 pre-merge bugs (paie payroll CGNC accounts 6171/6174/4432/4441/4443/4452 not seeded → added to compta seed_plan_comptable; flotte eco-conduite iterated the anomalies dict instead of `['anomalies']`; contrat obligation created `faite` had no date → stamp on marquer-faite; ged extraction invented `numero_facture='sans'` → require a digit). NOTE new cross-app write contrats→ventes.Facture + contrats→crm (function-local, import-linter green); ged Celery beat purge entry + gated settings flags (off); `/proposal` untouched; no new external dependency. This run also rewrote CLAUDE.md "How a plan run works" to make lane-draining + ONE-merge-per-run the explicit method [d4e4989f].) (2026-06-30 `claude/keen-volhard-e65936` PLAN.md drain — batch 7, 5 parallel file-disjoint worktree lanes (apps still disjoint from the concurrent session compta/gestion_projet/installations): rh FG190 (entretiens & évaluations annuelles), flotte FLOTTE27 (point d'intégration télématique, no-op sans fournisseur), qhse QHSE32 (événement incident_declared sur le bus + escalade des incidents critiques), contrats CONTRAT25 (Resiliation via la machine d'états gardée), ged GED30 (signature électronique — point d'intégration + stub no-op). 5 tasks open→done, additive & revertable, multi-tenant, tested locally (73-test combined build) + review; orchestrator folded then ran ONE combined test which caught + fixed 1 bug (QHSE32: `Incident` manquait dans la table cible du chatter → note d'escalade silencieusement avalée); 4 additive migrations (rh/0028, flotte/0024, contrats/0019, ged/0022), QHSE32 migration-free; FLOTTE27/GED30 no-op gated (aucune dépendance). NOTE: ce run a corrigé la cadence — le reste du drain passe en mode lane-draining (un agent draine toute la file d'une app) + UN seul merge par run, au lieu d'un merge par vague.) (2026-06-30 `claude/keen-volhard-e65936` PLAN.md drain — batch 6, 5 parallel file-disjoint worktree lanes (apps still disjoint from the concurrent session compta/gestion_projet/installations): rh FG189 (recrutement ATS-lite — postes/candidatures/pipeline + embauche → DossierEmploye, ARCH), flotte FLOTTE26 (Infraction / PV de circulation), qhse QHSE31 (AnalyseIncident arbre des causes → CAPA via NC-pont), contrats CONTRAT24 (Avenant → nouvelle VersionContrat, numéro max+1 verrouillé), ged GED29 (filage des PDF après-vente — service ged-only, sav/documents/proposal non touchés). 5 tasks open→done, additive & revertable, multi-tenant, tested locally (75-test combined build, GREEN first try) + review; agents did lightweight static checks only, orchestrator folded then ran ONE combined test; 4 additive migrations (rh/0027, flotte/0023, qhse/0021, contrats/0018), GED29 migration-free; no new dependency, no auth change.) (2026-06-30 `claude/keen-volhard-e65936` PLAN.md drain — batch 5, 5 parallel file-disjoint worktree lanes (apps still disjoint from the concurrent session compta/gestion_projet/installations): rh FG188 (plan & registre de formation, OFPPT/CSF), flotte FLOTTE25 (Sinistre accident/constat/assurance), qhse QHSE30 (déclaration CNSS de l'accident du travail — échéance légale, string-FK rh.AccidentTravail), contrats CONTRAT23 (renouvellement manuel + reconduction tacite — l'ACTION, ≠ CONTRAT20/21), ged GED28 (génération → classement automatique sur GED27). 5 tasks open→done, additive & revertable, multi-tenant, tested locally (108-test combined build, GREEN first try — no bug) + review; agents did lightweight static checks only, orchestrator folded then ran ONE combined test; 5 additive migrations (rh/0026, flotte/0022, qhse/0020 [dép. rh.0021], contrats/0017, ged/0021); no new dependency, no auth change.) (2026-06-30 `claude/keen-volhard-e65936` PLAN.md drain — batch 4, 5 parallel file-disjoint worktree lanes + 1 already-present (apps still disjoint from the concurrent session compta/gestion_projet/installations): rh FG187 (gestion de la formation → matrice de compétences), flotte FLOTTE24 (moteur d'alertes d'échéances J-7/15/30/échu agrégeant 5 sources), qhse QHSE29 (registre Incident, distinct des modèles RH), contrats CONTRAT22 (AlerteContrat + rappels via notifications.services, import-linter 4/4), ged GED27 (modèles de documents → PDF WeasyPrint, /proposal NON touché) + FG186 already-present (couvert par qhse PermisTravail/ConsignationLoto). 6 tasks open→done, additive & revertable, multi-tenant, tested locally (75-test combined build) + review + lint-imports 4/4; agents did lightweight static checks only, orchestrator folded then ran ONE combined test which caught + fixed 1 test-only assertion (GED27 unknown-token literal-space); 4 additive migrations (rh/0025, qhse/0019, contrats/0016, ged/0020), FLOTTE24 migration-free; no new dependency, no auth change.) (2026-06-30 `claude/keen-volhard-e65936` PLAN.md drain — batch 3, 5 parallel file-disjoint worktree lanes + 1 already-present (apps still disjoint from the concurrent session compta/gestion_projet/installations): rh FG185 (tableau de bord HSE — agrégation taux fréquence/gravité BIT/INRS), flotte FLOTTE23 (carte grise & autorisation de circulation, FileFields côté flotte), contrats CONTRAT21 (échéances & contrats à renouveler), qhse QHSE28 (plan d'urgence / premiers secours), ged GED26 (corbeille & restauration soft-delete préservant les guards GED23/GED24) + QHSE27 already-present (couvert par FG183). 6 tasks open→done, additive & revertable, multi-tenant, tested locally (combined build incl. full ged suite 332 tests + 4 new modules) + review; agents did lightweight static checks only, orchestrator folded then ran ONE combined test which caught + fixed 2 pre-existing ged tests that assumed hard-delete (updated for GED26's soft-delete); 3 additive migrations (flotte/0021, qhse/0018, ged/0019), FG185/CONTRAT21 migration-free; no new dependency, no auth change.) (2026-06-30 `claude/keen-volhard-e65936` PLAN.md drain — batch 2, 5 parallel file-disjoint worktree lanes (apps still disjoint from the concurrent session's in-flight tree compta/ventes/installations/gestion_projet): rh FG184 (analyse de risques chantier / plan de prévention), flotte FLOTTE22 (visite technique validité paramétrable), qhse QHSE26 (induction sécurité accueil site, incl. sous-traitants), contrats CONTRAT20 (dates clés début/fin/préavis + tacite reconduction), ged GED24 (rétention légale / legal hold, blocage suppression → 403) — 5 tasks open→done, additive & revertable, multi-tenant, tested locally (92 tests green in the prod docker image, one combined build) + review; agents did lightweight static checks only (flake8/compileall), orchestrator folded then ran ONE combined test which caught + fixed 2 CI-red issues pre-merge (FLOTTE22 `date_prochaine` computed only in `clean()` which DRF `save()` skips → moved to `save()`; CONTRAT20 selector `.annotate(echeance_preavis=…)` shadowed the homonymous model method → renamed `echeance_preavis_calc`); 5 additive migrations (rh/0024, flotte/0020, qhse/0017, contrats/0015, ged/0018); no new dependency, no auth change.) (2026-06-30 `claude/keen-volhard-e65936` PLAN.md drain — 4 parallel file-disjoint worktree lanes, apps deliberately disjoint from a concurrent session's in-flight tree (compta/ventes/installations/gestion_projet): rh FG183 (causeries sécurité / toolbox talks), flotte FLOTTE21 (assurance véhicule police/échéance/franchise/attestation), qhse QHSE25 (alerte expiration permis de travail), contrats CONTRAT19 (dépôt GED des versions & PDF signés) — 4 tasks open→done, additive & revertable, multi-tenant, tested locally (56 tests green in the prod docker image) + review; the review caught + fixed 1 CI-red issue pre-merge (CONTRAT19 `ged.services` missing `Cabinet` import → NameError silently swallowed by the best-effort deposit); 2 additive migrations (rh/0023, flotte/0019), QHSE25/CONTRAT19 migration-free; CONTRAT19 cross-app write routes through `ged.services` only; no new dependency, no auth change.) (2026-06-30 `claude/relaxed-edison-c91f99` PLAN.md drain — wave 13, 6 parallel file-disjoint worktree lanes resuming wave-9 app lanes (off the merged wave-9..12 base, pipelined during wave-12 CI): compta FG145 (retenue de garantie & cautions), rh FG182 (presqu'accidents), installations FG305 (ordres de travaux sous-traitant), gestion_projet PROJ22 (coûts engagés vs réels), ged GED23 (archivage légal write-once, DECISION), flotte FLOTTE20 (vignette/TSAV) — 6 tasks open→done, additive & revertable, multi-tenant, tested locally + adversarial review; the review caught + fixed 2 pre-merge issues (PROJ22 4-dp Decimal serialization → quantize; GED23 archived-doc restaurer/check-out/check-in returning 500 instead of 403 → translate ArchivageLegalError); GED23 adds NO hard dependency (object-lock best-effort + degrade); FG145/FG305 race-safe references; no auth change.) (2026-06-29 `claude/relaxed-edison-c91f99` PLAN.md drain — wave 12, 3 parallel file-disjoint worktree lanes resuming wave-10 app lanes (off the merged wave-9+10+11 base): paie PAIE24 (taxe de formation professionnelle patronale), qhse QHSE24 (consignation LOTO sur permis), crm FG204 (attribution multi-touch / points de contact) — 3 tasks open→done, additive & revertable, multi-tenant, tested locally (paie/qhse/crm suites, 1009 tests) + adversarial review (3/3 merge_ready); the local CI caught + fixed 1 CI-red issue pre-merge (FG204 `leads/{id}/points-contact/` read action 403 → added to the IsAnyRole read-action list); PAIE24 reuses the existing `taux_formation_pro` field (no migration-drift duplicate); FG204 reuses `Lead.Canal`, no hardcoded STAGES.py stage; QHSE24 builds on QHSE23 PermisTravail; no new dependency, no auth change.) (2026-06-29 `claude/relaxed-edison-c91f99` PLAN.md drain — wave 11, 6 parallel file-disjoint worktree lanes resuming wave-9 app lanes (off the merged wave-9 base, pipelined during wave-10 CI): compta FG144 (droit de timbre encaissements espèces), rh FG181 (registre HSE & accidents du travail), ventes FG264 (rendement pompage par cycle), installations FG304 (référentiel sous-traitants), ged GED22 (politiques de rétention), flotte FLOTTE19 (EcheanceReglementaire) — 6 tasks open→done, additive & revertable, multi-tenant, tested locally (full affected-app suites) + adversarial review; the review + local CI caught and fixed 3 CI-red issues pre-merge (FG181 false delete-reclaim assertion, FG264 clearsky profile summing to 0.99, FG304 form-data BooleanField defaulting actif to False) plus hardened a pre-existing flaky publicapi safety test (prix_achat substring vs timestamp microseconds, which had also reddened the wave-10 CI re-run); no migration drift, 5 additive migrations (compta/0015, rh/0021, installations/0020, ged/0016, flotte/0017); GED22 retention non-destructive by default; FG264 quote-PDF path untouched; no new dependency, no auth change.) (2026-06-29 `claude/relaxed-edison-c91f99` PLAN.md drain — wave 10, 7 parallel file-disjoint worktree lanes (apps disjoint from wave 9, pipelined during wave-9 CI): crm FG242 (suivi concurrents deals perdus), gestion_projet PROJ21 (budget projet par catégorie), qhse QHSE23 (PermisTravail), kb KB7 (droits d'accès par rôle + suivi de lecture), sav FG280 (alarmes/défauts onduleur), paie PAIE23 (allocations familiales patronales), litiges LITIGE6 (tableau de bord litiges) — 7 tasks open→done, additive & revertable, multi-tenant, tested locally (full affected-app suites, 1597 tests) + adversarial review (7/7 merge_ready, 1 harmless filter nit on FG242); no migration drift, 6 additive migrations (crm/0029, gestion_projet/0013, kb/0005, paie/0011, qhse/0015, sav/0011); KB7 backward-compatible (no ACL → article visible to all); FG242 reuses Lead.perdu, no hardcoded STAGES.py stage; no new dependency, no auth change.) (2026-06-29 `claude/relaxed-edison-c91f99` PLAN.md drain — wave 9, 8 parallel file-disjoint worktree lanes: compta FG143 (déclaration honoraires/état 9421), installations FG303 (planning des camionnettes), ventes FG263 (modèle financier PPA/tiers-investisseur, DECISION), core FG369 (bibliothèque de modèles de workflow), rh FG180 (émargement remise EPI), contrats CONTRAT18 (VersionContrat immuable), flotte FLOTTE18 (pneumatiques & pièces), ged GED21 (watermarking & contrôle de diffusion, DEP) — 8 tasks open→done, additive & revertable, multi-tenant, tested locally (full affected-app suites, 3267 tests) + adversarial review (8/8 merge_ready); fixed 2 test-only assertions pre-merge (FG369 401-vs-403 anon auth, CONTRAT18 paginated count vs len); no migration drift, 4 additive migrations (rh/0020, contrats/0014, flotte/0016, ged/0015); GED21 is category DEP but adds NO hard dependency — image watermark via Pillow (already present), PDF watermark via PyMuPDF imported lazily with graceful degrade; FG369 core stays foundation (import-linter), core.urls extended; no auth change.) (2026-06-29 `claude/relaxed-edison-c91f99` PLAN.md drain — wave 8, 8 parallel file-disjoint worktree lanes: compta FG142 (liasse fiscale), installations FG302 (calendrier de disponibilité ressources), ventes FG262 (dégradation modules + garantie), core FG368 (backend jobs Celery Beat), rh FG179 (péremption/contrôle EPI), gestion_projet PROJ20 (nivellement de charge), paie PAIE22 (calcul IR — already present, tests added), qhse QHSE22 (gate document unique avant pose) — 8 tasks open→done, additive & revertable, multi-tenant, tested locally (8 wave-8 test modules) + adversarial review; no migration drift, import-linter 4/4 (FG368 jobs stay foundation via celery infra); FG368 `core.urls` wired into the root URLConf (orchestrator step); no new external dependency, no auth change.) (2026-06-29 `claude/relaxed-edison-c91f99` PLAN.md drain — wave 7, 8 parallel file-disjoint worktree lanes: compta FG141 (export FEC DGI), installations FG301 (nivellement de charge), ventes FG261 (optimisation puissance souscrite C&I), core FG367 (évaluateur conditions ET/OU + actions séquentielles), rh FG178 (catalogue & dotation EPI), contrats CONTRAT17 (auto signé→actif), flotte FLOTTE17 (ordres de réparation + garage), ged GED20 (partage par lien tokenisé expiry/password/quota) — 8 tasks open→done, additive & revertable, multi-tenant, tested locally (9 wave-7 test modules) + adversarial review (incl. the GED20 public tokenized endpoint security review); no migration drift, import-linter 4/4 (FG367 stays foundation); no new external dependency, no auth change.) (2026-06-29 `claude/relaxed-edison-c91f99` PLAN.md drain — wave 6, 8 parallel file-disjoint worktree lanes: compta FG140 (aide IS + acomptes), installations FG300 (conflits d'affectation chantier), ventes FG260 (escalade ONEE 20-25 ans + VAN/TRI), core FG366 (moteur BPM + SLA, ARCH), rh FG177 (visite médicale du travail), gestion_projet PROJ19 (conflits d'affectation), paie PAIE21 (frais professionnels — already present, tests added), qhse QHSE21 (évaluation des risques / document unique) — 8 tasks open→done, additive & revertable, multi-tenant, tested locally (8 wave-6 test modules) + adversarial review; no migration drift (FG366 BPM + QHSE21 constraints byte-matched), import-linter 4/4 (FG366 BPM stays foundation via contenttypes); no new external dependency, no auth change.) (2026-06-29 `claude/relaxed-edison-c91f99` PLAN.md drain — wave 5, 8 parallel file-disjoint worktree lanes: compta FG139 (RAS + bordereau), installations FG299 (plan de charge équipes), ventes FG259 (net-metering surplus loi 13-09), core FG365 (prédiction retard paiement), rh FG176 (garde affectation par habilitation), contrats CONTRAT16 (SignatureContrat e-sign in-app), flotte FLOTTE16 (génération échéances entretien), ged GED19 (ACL dossier/document héritage+override) — 8 tasks open→done, additive & revertable, multi-tenant, tested locally (8 wave-5 test modules) + adversarial review; fixed a GED19 CheckConstraint condition= migration drift pre-merge; import-linter 4/4; no new external dependency, no auth change; core stays a foundation layer.) (2026-06-29 `claude/relaxed-edison-c91f99` PLAN.md drain — wave 4, 8 parallel file-disjoint worktree lanes: compta FG138 (annexe TVA déductions), installations FG295 (P&L projet consolidé, ARCH), ventes FG258 (autoconso horaire 8760), core FG364 (prévision réappro stock), rh FG175 (alertes d'expiration), gestion_projet PROJ18 (plan de charge), paie PAIE20 (CIMR optionnelle), qhse QHSE20 (ISO 9001 readiness) — 8 tasks open→done, all aggregation/pure-math (ZERO migrations), multi-tenant, tested locally (8 wave-4 test modules) + adversarial review; no migration drift, import-linter 4/4; no new external dependency, no auth change; core stays a foundation layer.) (2026-06-29 `claude/relaxed-edison-c91f99` PLAN.md drain — wave 3, 8 parallel file-disjoint worktree lanes: compta FG137 (déclaration TVA), installations FG294 (budget projet vs réel, ARCH), ventes FG257 (bankable P50/P90), core FG363 (score de churn), rh FG174 (certifications), contrats CONTRAT15 (chatter/journal), flotte FLOTTE15 (entretien préventif), ged GED18 (workflow d'approbation) — 8 tasks open→done, additive & revertable, multi-tenant, tested locally (8 wave-3 test modules) + adversarial review; no migration drift, import-linter 4/4; no new external dependency, no auth change; core stays a foundation layer.) (2026-06-29 `claude/relaxed-edison-c91f99` PLAN.md drain — wave 2, 8 parallel file-disjoint worktree lanes: compta FG136 (indemnités km/per-diem), installations FG292 (ProjetTâche + dépendances, ARCH), ventes FG256 (étude batterie/dispatch), core FG362 (win-probability + reporting), rh FG173 (habilitations électriques), contrats CONTRAT14 (workflow d'approbation), flotte FLOTTE14 (cartes carburant + anomalies), qhse QHSE19 (retour client qualité) — 8 tasks open→done, additive & revertable, multi-tenant, tested; adversarial review + local docker CI (flake8/check/makemigrations-check/import-linter 4/4); fixed an FG136 constraint Q-order migration drift pre-merge; no new external dependency, no auth change; core stays a foundation layer.) (2026-06-29 `claude/relaxed-edison-c91f99` PLAN.md drain — wave 1, 8 parallel file-disjoint worktree lanes, one self-merge: compta FG135 (notes de frais & remboursements), installations FG291 (projet multi-chantiers, NEW arch), ventes FG255 (borne de recharge VE), core FG361 (prévision de ventes, +statsmodels), rh FG172 (matrice de compétences), contrats CONTRAT13 (règle d'approbation), flotte FLOTTE13 (conso L/kWh-100 km), ged GED17 (cycle de vie documentaire) — 8 tasks open→done, additive & revertable, multi-tenant, tested; adversarial review caught and fixed 2 CI-red issues pre-merge (FG361 NaN fallback guard, FLOTTE13 read-permission) + an FG135 reference race; NOTE new external dependency statsmodels==0.14.4 (imported defensively, pure-Python fallback); core stays a foundation layer.) (2026-06-29 `claude/determined-haslett-31e594` PLAN.md drain — wave 1, 8 parallel file-disjoint worktree lanes, one self-merge: compta FG132/133/134, installations FG70/71/77, ventes FG252/253/254, core FG353/354/360 (FG360 = first concrete core model AnomalyFlag), rh FG169/170/171, contrats CONTRAT10/11/12, flotte FLOTTE10/11/12, paie PAIE17/18/19 — 24 tasks open→done, all additive & revertable, multi-tenant, tested; no new external/paid dependency, no auth change; core stays a foundation layer.) (2026-06-29 `claude/crazy-goodall-89884e` PLAN.md drain — 2 parallel worktree waves (7+8 file-disjoint lanes), one self-merge: wave 1 FG131 (compta 3-way match REBUILT reusing stock procurement via selectors), FG168 (rh overtime), PAIE16 (paie benefits-in-kind), QHSE18 (qhse versioned quality procedure), CONTRAT9 (contract clauses), FLOTTE9 (driver-licence check at assignment), FG245 (ventes roof-layout editor), FG352 (ged RAG DocQA — new open-source dep langchain-text-splitters); wave 2 PROJ17 (resource unavailability), FG88 (sav preventive-tour planning), LITIGE4 (litige↔QHSE NCR link), FG6 (per-user iCal feed), DC17 (CustomUser.poste → rh.Poste référentiel, reversible data migration), DC18 (automation email-template store), N91+F21 (offline-tolerant field capture). 16 tasks moved open→done — additive (one reversible data migration), multi-tenant, tested; validated on the docker CI harness (compta 215 + automation 46 green, makemigrations --check clean, backend flake8 clean). (2026-06-24 add-to-plan: appended PLAN2 **Group QJ** (QJ1–QJ25) — best-in-world quote-journey ERP tasks: proposal open-tracking, Celery scheduler + relance cadence + auto quote-expiry, lead scoring, e-sign evidence hardening (loi 53-05), financing data, self-consumption tariff engine, commercial dashboard, + gated WhatsApp-API / CMI-deposit / auto-roof-detection. The matching website tasks WJ1–WJ24 live in docs/WEB_PLAN.md, which is NOT in the plan-fingerprint surface. Backlog additions only — nothing built or ticked; done/blocked counts unchanged.) (2026-06-22 add-to-plan: appended PLAN2 **Group U** (U1–U14) — field-UX bugs Reda is hitting + the family of document-status "connection" gaps found while investigating his WhatsApp/facture report: U1 lead-modal stays open on « Mettre à jour » + inline devis, U2 mouse-wheel scroll regression, U3 mobile header overlap, U4 WhatsApp-send flips devis → envoyé + advances funnel, U5 surface generated factures/BC in the devis list, U6 auto-create chantier on devis acceptance, U7 hide/badge superseded devis revisions, U8 reflect BC state in the devis detail, U9 stock reservation on the direct generer-facture path, U10 reset relance escalation on full payment, U11 lead-funnel sanity on post-signed refusal (DECISION), U12 direct lead FK on facture/BC, U13 user-picture upload bug, U14 GED « Documents » menu unusable (read-only nav, no create/upload). All 14 BUILT & ticked 2026-06-23 in 10 parallel worktree lanes (one self-merge) — see DONE LOG; category notes: U4 AUTH (CRM action changes a document status; new `devis_sent` event), U6 ARCH (new cross-app event reaction), U9 SCHEMA (stock side-effects on a new trigger), U12 SCHEMA (additive nullable lead FK, migration 0028), U11 DECISION (built FLAG-ONLY — founder to confirm whether the funnel should recede). ADDITIVE migrations ventes/0027_devis_date_envoi + 0028_boncommande_lead_facture_lead. Prior context below.) (2026-06-22 `claude/plan-md-completion-ysbchz` functional-domain drain — PLAN2 already drained; that run drained 8 parallel worktree lanes off PLAN.md: compta FG125–130 (trésorerie/effets), ventes FG51/FG53/FG248/FG250/FG251 (POD gate, NoOp PaymentLink, toiture-3D/ombrage/BOQ), core FG355–359 (OCR/voix/photo-QA/next-best-action — NoOp AI foundation, aucune dépendance), rh FG160–165 (postes, congés Maroc, workflow), paie PAIE7–12 (rubriques→bulletin CNSS/AMO/CIMR/IR), ged GED8–13 (coffre-fort/tags/plein-texte/sémantique), gestion_projet PROJ8–13 (CPM/Gantt/baseline), qhse QHSE8/11–15 (photos/réserve→NCR/CAPA/chatter/grilles). 46 moved open→done this run, all additive & tested. FG52 (multi-devise) left [ ] for a focused run.)
added the FG1–FG399 feature-gap + functional-domain backlog, 275 new-module deep-dive tasks across
nine modules (PAIE/COMPTA/PROJ/GED/FLOTTE/QHSE/CONTRAT/KB/LITIGE), and DC1–DC42 data-connectivity
tasks to `docs/PLAN.md`. No task was built or ticked — backlog additions only; done/blocked counts
are unchanged from the prior batch.)

> Note: only **S21** (real-time WebSocket chat) remains blocked — it waits on founder-provisioned WS
> infra (ASGI server + Redis channel layer + nginx WS proxy) and I recommend deferring it (3 s
> polling is enough). The previously-blocked tasks are unblocked: **N91/F21** (offline capture — the
> dev-field-exec routing was stale: the field-exec backend is already on `main` and worktree
> isolation prevents collisions), **M4** (do it via the M6 `core/events.py` bus — reuse
> `AuditLog.Action.PDF`), **I134/I138** (already shipped under other IDs — reconcile only), and
> **N100/N101/N102** (multi-tenant SaaS — ungated per "ungate all" but I recommend keeping them
> deferred until a 2nd paying installer; do not let a drain build them yet). See the **NEEDS YOUR
> INPUT** sections of `docs/PLAN.md` / `docs/WEB_PLAN.md` for the credential/data/taste items.

**Done (1833)**

- `ERR1` — [FastAPI] NL→SQL agent has no SELECT-only enforcement in code…
- `ERR2` — [FastAPI] NL→SQL tenant isolation is defeatable four ways…
- `ERR3` — [FastAPI] The SQL agent connects as the table-owner Postgres role…
- `ERR4` — [auth] `is_responsable` returns True for ANY user that merely has a role…
- `ERR5` — [roles/auth] Responsable-tier users can self-grant any permission and escalate to…
- `ERR6` — [automation] Automation actions re-fire their own triggers with no recursion guard…
- `ERR7` — [ventes] `LigneDevisViewSet`/`LigneFactureViewSet` allow cross-tenant line injection…
- `ERR8` — [ventes] `DevisViewSet.perform_update` mass-assignment lets a devis be re-pointed at…
- `ERR9` — [sav] `ContratMaintenanceViewSet` has no `_check_tenant` and its serializer no…
- `ERR10` — [stock] The `MouvementStock` write endpoint accepts arbitrary negative/zero/overflow…
- `ERR11` — [reporting/exports] CSV/Excel formula injection in the shared `build_xlsx_response`…
- `ERR12` — [frontend] `OcrStockImport` BCF reception reads `lignes` off the create response and…
- `ERR13` — [ventes] `BonCommandeViewSet.perform_create` doesn't validate body `client`/`devis`…
- `ERR14` — [ventes] `FactureViewSet.perform_create` doesn't validate body…
- `ERR15` — [ventes] `BonCommandeViewSet.marquer_livre` does `int(ligne.quantite)`, truncating…
- `ERR16` — [ventes] The legacy BC→Facture path ignores `Devis.option_acceptee` and bills BOTH…
- `ERR17` — [quote_engine] `generate_premium_pdf` mutates ~40 module globals…
- `ERR18` — [FastAPI] JWT verification doesn't require `exp` (or `iss`/`aud`)…
- `ERR19` — [FastAPI] The raw user question is concatenated into the agent prompt that drives the…
- `ERR20` — [FastAPI] `prix_achat`/margin confidentiality is only a prompt instruction…
- `ERR21` — [auth] `UserViewSet`/`RegisterView` accept an arbitrary `role` PK with no company or…
- `ERR22` — [auth] `prod.py` omits production hardening (`erp_agentique/settings/prod.py`)…
- `ERR23` — [stock] `MouvementStockViewSet.perform_create` isn't atomic and uses…
- `ERR24` — [stock] `recevoir` and `apply_retour_fournisseur` read `quantite_stock` without…
- `ERR25` — [parametres] `CompanyProfileSerializer` uses `fields='__all__'` with `company` writable…
- `ERR26` — [frontend] The map popup injects unescaped `popupHtml` (`components/MapView.jsx:92-95`)…
- `ERR27` — [frontend] Route guards enforce authentication but not role/permission…
- `ERR28` — [frontend] The `ParametresEntreprise` `<form>` lacks `noValidate` while wrapping…
- `ERR29` — [frontend] `InstallationsPage` kanban status/reschedule writes have no rejection…
- `ERR30` — [frontend] `EquipementsPage` shows raw `JSON.stringify(err.response.data)` on save…
- `ERR31` — [frontend] `MouvementsPage.validate()` requires quantity `> 0` for all types incl
- `ERR32` — [web] `simulate.ts`/`preview-lead.ts` log full lead PII (name/phone/city/consent) via…
- `ERR33` — [ventes] `DevisViewSet.accepter` forces `ACCEPTE` with no guard on the current status…
- `ERR34` — [ventes] `FactureViewSet.creer_avoir` swallows all per-line errors and silently drops…
- `ERR35` — [ventes] `task_generate_devis_pdf` isn't idempotent under `acks_late` + retry…
- `ERR36` — [ventes] `relance_reminders` scheduling is destructive/lossy…
- `ERR37` — [quote_engine] User-controlled text (client name/address/phone/ICE; line…
- `ERR38` — [crm] `resolve_client_for_lead`'s check-then-create isn't transactional…
- `ERR39` — [crm] `Lead.gps_lat`/`gps_lng` have no range validation (`crm/models.py:181-184`): a…
- `ERR40` — [installations] `mise_en_service` sets `statut` directly and skips…
- `ERR41` — [installations] `field_capture.validate_consommation` truncates fractional…
- `ERR42` — [FastAPI] CORS `allow_credentials=True` with a default origin and `_DEBUG` defaulting…
- `ERR43` — [FastAPI] `sql_db_schema`/`sql_db_list_tables` tools and `sample_rows_in_table_info=2`…
- `ERR44` — [FastAPI] The sql_agent endpoint reads `company_id` from the JWT with no presence…
- `ERR45` — [auth] JWT auth cookies use `SameSite=Strict` with cross-origin credentialed CORS and…
- `ERR46` — [publicapi] `WebhookViewSet` allows CRUD of `target_url` and `delivery._deliver_one`…
- `ERR47` — [monitoring] `evaluate_underperformance` does read-then-create on…
- `ERR48` — [automation] `run_approved` resolves the deferred target by raw PK with no company…
- `ERR49` — [automation] SEND_EMAIL uses `send_mail(fail_silently=True)` and always returns SUCCESS…
- `ERR50` — [notifications] VERIFY whether the notification engine is actually invoked by business…
- `ERR51` — [dataimport] `commit` imports rows one-by-one with no `transaction.atomic`…
- `ERR52` — [dataimport] Product import sets `quantite_stock` directly with no `MouvementStock`…
- `ERR53` — [dataimport] Import dry-run/commit swallow all exceptions into a generic 400 and read…
- `ERR54` — [stock] `compute_besoin_materiel` truncates Decimal devis quantities via `int()`…
- `ERR55` — [parametres] `CompanyProfile` has no validation on…
- `ERR56` — [records] `resolve_target` lets `Model.DoesNotExist` (and a bad-type pk) escape as a…
- `ERR57` — [reporting] `stock_report`'s low-stock list doesn't exclude `seuil_alerte=0`…
- `ERR58` — [frontend] The `iaApi` interceptor reads `error.config` unguarded and hard-redirects to…
- `ERR59` — [frontend] Logout does `localStorage.clear()`, wiping theme, sidebar state, saved lead…
- `ERR60` — [frontend] `fetchMe.fulfilled` stores only `{username}`, dropping email/other user…
- `ERR61` — [frontend] Raw error objects are shown to users via `JSON.stringify` on `LeadsPage`…
- `ERR62` — [frontend] Swallowed fetch errors masquerade as empty data on `BalanceAgeePage`…
- `ERR63` — [frontend] `ParametresEntreprise.saveNiveaux` fires per-row PATCHes in `Promise.all`…
- `ERR64` — [frontend] `TicketsPage` bulk PATCH is non-atomic and doesn't reload on partial failure…
- `ERR65` — [frontend] `MouvementsPage` "Transferts" tab never shows its `(n)` count…
- `ERR66` — [frontend] `InterventionsPage` reassign doesn't refetch on failure and isn't optimistic…
- `ERR67` — [frontend] The voice-memo recorder leaks the mic stream on unmount…
- `ERR68` — [frontend] `Reporting` destructures the dashboard payload unconditionally after a null…
- `ERR69` — [frontend] The `Journal` data effect depends on both `filterParams` and `page` while…
- `ERR70` — [web] hreflang/x-default alternates have mismatched trailing slashes between locales…
- `ERR71` — [ventes] `Devis.total_tva` sums per-line TVA without quantize while…
- `ERR72` — [ventes] `enregistrer_paiement`'s overpayment guard reads `montant_du` outside any row…
- `ERR73` — [ventes] `recouvrement._releve_data` pulls `Facture.objects.filter(client=client)`…
- `ERR74` — [quote_engine] `/proposal` is a GET that re-renders and persists `fichier_pdf` on every…
- `ERR75` — [quote_engine] The legacy fallback PDF key is not company-scoped (`utils/pdf.py:155` vs…
- `ERR76` — [quote_engine] An unbounded `custom_acompte` can make a negative "Matériel" amount /…
- `ERR77` — [crm] `merge_leads`'s `_MERGE_FILL_FIELDS` omits several lead fields incl
- `ERR78` — [crm] bulk/whatsapp endpoints don't coerce/validate `ids` element types…
- `ERR79` — [crm] The website webhook's idempotent re-POST within `DEDUP_WINDOW` blindly `setattr`s…
- `ERR80` — [installations/sav] Three SORTIE paths drive stock negative with no floor guard…
- `ERR81` — [installations] `tool_return` is a GET that creates `ToolReturn` rows…
- `ERR82` — [outillage] No checkout step exists; a tool is only marked busy at return time inside…
- `ERR83` — [sav] `ContratMaintenance.is_due`/`renouvellement_du` default to naive `date.today()`…
- `ERR84` — [FastAPI] The generated SQL (with real table names) is returned to the client in…
- `ERR85` — [FastAPI] `create_tables()` runs unconditional `ALTER TABLE`/`CREATE INDEX` DDL on…
- `ERR86` — [FastAPI] The OCR rate-limit fails open on any Redis error…
- `ERR87` — [auth] Logout blacklists only the refresh token; the access token stays valid up to its…
- `ERR88` — [auth] `seed_demo` creates `demo_admin`/`demo_resp` with the hardcoded password…
- `ERR89` — [auth/publicapi] One-time-reveal secrets (webhook secret, API key) are returned without…
- `ERR90` — [automation] The overdue-facture check compares `echeance` against the UTC date…
- `ERR91` — [notifications] The in-app notification `body` is written unbounded while…
- `ERR92` — [auth/audit] The login audit `actor_username` comes from the client-supplied…
- `ERR93` — [stock] `StockEmplacement.unique_together` omits `company` and `quantite` allows…
- `ERR94` — [stock] The per-emplacement breakdown derives the principal location as `total −…
- `ERR95` — [stock] `ProduitSerializer` uses `fields='__all__'` with a runtime `prix_achat` pop…
- `ERR96` — [frontend] The DataTable default `getRowId` mixes a page-local index for keys with a…
- `ERR97` — [frontend] `datatable/csv.js`'s `escapeCSVCell` does RFC-4180 quoting but no…
- `ERR98` — [frontend] `ProduitForm` `prix_vente` validation accepts 0 and negatives…
- `ERR99` — [frontend] `StockList` reads `r.data.results ?? r.data` without the `?? []` fallback…
- `ERR100` — [frontend] `ProductionPage.reloadReadings` (from addReading/syncNow) fetches with no…
- `ERR101` — [frontend] `RolesManagement` reassign-on-blocked-delete requires both `users_count>0`…
- `ERR102` — [frontend] Several parametres section name inputs are uncontrolled `defaultValue` with…
- `ERR103` — [frontend] `MaJourneePage` renders the flow sheet from a stale `active` snapshot…
- `ERR104` — [frontend] `NotificationBell` optimistically marks read in `.finally()` regardless of…
- `ERR105` — [frontend] `InlineEdit` resets `draft` to `value` while not editing on save failure…
- `ERR106` — [frontend] `lib/format.js`'s `toNumber` strips a dot followed by exactly 3 digits as a…
- `ERR107` — [frontend] Per-line vs total rounding can disagree by 1 MAD on the devis screen…
- `ERR108` — [frontend] `Login`'s `BouncingBackground` captures window W/H once with no resize…
- `ERR109` — [web] The `*.workers.dev` 301 redirect applies to all methods incl
- `ERR110` — [web] The lead webhook uses a static `x-webhook-secret` with no HMAC/timestamp/nonce…
- `ERR111` — [web] The CAPI relay receives un-hashed phone/city PII…
- `ERR112` — [web] The public lead endpoint has no rate limit/CAPTCHA…
- `ERR113` — [web] `roof.ts`'s `annualSavingsBandMad` uses a flat 1.4 MAD/kWh tariff with no bill…
- `COMPTA1` — Plan comptable CGNC paramétrable + `seed_plan_comptable` idempotent
- `COMPTA2` — Mapping document→compte par société (familles/TVA/modes de paiement → comptes)
- `COMPTA3` — Comptes auxiliaires tiers (dérivés de `crm.Client`/`stock.Fournisseur` via selectors)
- `COMPTA4` — Journaux paramétrables (VTE/ACH/BNK/CSH/OD/AN) + séquences
- `COMPTA5` — Multi-exercice & périodes comptables
- `COMPTA6` — Validation légale du plan/format CGNC (fiduciaire)
- `COMPTA7` — Écriture en partie double équilibrée (Σ débit = Σ crédit)
- `COMPTA8` — Saisie d'OD manuelle (régularisations/provisions/corrections)
- `COMPTA9` — Numérotation séquentielle des pièces (via `references.py`, jamais count()+1)
- `COMPTA10` — Pièces justificatives sur écriture
- `COMPTA11` — Extourne / contre-passation (jamais supprimer une écriture validée)
- `COMPTA12` — Auto-écriture depuis facture client (3421/71xx/4455x), réconcilie au journal-ventes
- `COMPTA13` — Auto-écriture depuis avoir
- `COMPTA14` — Auto-écriture depuis paiement client (514x/516x/caisse)
- `COMPTA15` — Auto-écriture depuis facture fournisseur (61xx/3455x/4411)
- `COMPTA16` — Auto-écriture depuis paiement fournisseur
- `COMPTA17` — Contrat de posting paie & immobilisations (signatures de service)
- `COMPTA18` — Statut-préservation & idempotence du posting (test-guarded)
- `COMPTA19` — Grand livre (détail par compte + solde courant + lettrage, export xlsx)
- `COMPTA20` — Balance générale (trial balance — distincte de la balance âgée existante)
- `COMPTA21` — Balance auxiliaire clients/fournisseurs
- `COMPTA22` — Lettrage clients/fournisseurs (manuel + auto-suggest)
- `COMPTA23` — Référentiel `CompteTresorerie` (banque/caisse/RIB/devise) lié au GL
- `COMPTA24` — Journal de caisse (petty cash) + clôture de caisse
- `COMPTA25` — Virements internes (écriture à deux jambes)
- `COMPTA26` — Import relevé bancaire & rapprochement
- `COMPTA27` — CPC (Compte de Produits et Charges)
- `COMPTA28` — Bilan (format CGNC)
- `COMPTA29` — ESG / états de synthèse + ETIC
- `COMPTA30` — Tableau de bord financier directeur (P&L/cash/DSO/DPO/marge)
- `COMPTA31` — Clôture mensuelle & verrouillage de période
- `COMPTA32` — Clôture d'exercice & génération des à-nouveaux
- `COMPTA33` — Réouverture / correction d'exercice clos (audité)
- `COMPTA34` — Préparation déclaration TVA (régime débit/encaissement)
- `COMPTA35` — Relevé de déductions détaillé (annexe TVA)
- `COMPTA36` — Export FEC (format DGI auditable)
- `COMPTA37` — Liasse fiscale & export fiduciaire (Sage/CEGID ; Odoo JSON-2 only)
- `COMPTA38` — Comptabilité analytique / centres de coût (axe chantier/agence/marché/commercial)
- `COMPTA39` — Piste d'audit comptable inaltérable (écritures hash-chaînées)
- `COMPTA40` — Séparation des tâches (saisie vs validation vs clôture)
- `CONTRAT1` — App `contrats` + modèle `Contrat` socle (référence via `references.py`)
- `CONTRAT2` — Enum `type_contrat` (12 types) + lifecycle statut
- `CONTRAT3` — `PartieContrat` (parties/signataires, ≥2)
- `CONTRAT4` — Liens inter-apps (devis/lead/installation/maintenance) en string-FK
- `CONTRAT5` — Wrap de `sav.ContratMaintenance` (lecture/lien, ne casse pas)
- `CONTRAT6` — Niveaux de confidentialité + droits d'accès par type
- `CONTRAT7` — `ModeleContrat` (bibliothèque de modèles)
- `CONTRAT8` — `Clause` (bibliothèque de clauses réutilisables)
- `CONTRAT9` — `ClauseContrat` (clauses résolues, ordonnées, surchargeables)
- `CONTRAT10` — Génération du contrat par fusion (merge tokens)
- `CONTRAT11` — Rendu PDF interne du contrat (hors `/proposal`)
- `CONTRAT12` — Machine d'états du cycle de vie + transitions gardées
- `CONTRAT13` — `RegleApprobation` (par montant/type)
- `CONTRAT14` — `EtapeApprobation` + workflow d'approbation interne
- `CONTRAT15` — Chatter/journal du contrat (audit des transitions)
- `CONTRAT16` — `SignatureContrat` (point e-sign + statut signé)
- `CONTRAT17` — Transition automatique signé→actif sur signature
- `CONTRAT18` — `VersionContrat` (versionnage immuable des rendus)
- `CONTRAT19` — Dépôt en GED des versions & PDF signés
- `CONTRAT20` — Dates clés (début/fin/préavis) + tacite reconduction
- `CONTRAT21` — Calcul des échéances & contrats « à renouveler »
- `CONTRAT22` — `AlerteContrat` + rappels via notifications
- `CONTRAT23` — Renouvellement (manuel + reconduction tacite)
- `CONTRAT24` — `Avenant` (amendements → nouvelle version)
- `CONTRAT25` — `Resiliation` (motif/préavis/solde)
- `CONTRAT26` — `Obligation`/`JalonContrat` (livrables & jalons)
- `CONTRAT27` — SLA & pénalités (taux SLA, valeur pénalité)
- `CONTRAT28` — Retenue de garantie (suivi de libération)
- `CONTRAT29` — Registre des cautions/garanties liées
- `CONTRAT30` — `EcheancierContrat` + `LigneEcheance`
- `CONTRAT31` — Lien facturation récurrente (via `ventes.services`)
- `CONTRAT32` — `IndexationPrix` (indexation/révision de prix)
- `CONTRAT33` — Tableau de bord contrats (actifs/à renouveler/en risque/valeur·MRR)
- `CONTRAT34` — `PieceConformite` (pièces obligatoires & attestations)
- `CONTRAT35` — Reporting valeur contractuelle & taux de renouvellement
- `DC1` — Le moteur de devis premium imprime l'identité société en dur
- `DC2` — Constantes ROI en dur dans le moteur
- `DC3` — L'étude industrielle ignore les constantes injectées
- `DC4` — `CompanyProfile.tva_panneaux` est un champ mort
- `DC5` — Tarif ONEE/productible en double
- `DC6` — TVA 10/20 hardcodée dans `solar.js`
- `DC7` — `Produit.tva` doit être la source autoritaire du taux de ligne
- `DC8` — Triplication de la classification produit + règle 10/20
- `DC9` — Tableau GHI dupliqué
- `DC10` — `LigneAvoir.produit` nullable (SET_NULL)
- `DC11` — `Devis.etude_params` sans provenance
- `DC12` — Profil site/énergie re-saisi à chaque devis
- `DC13` — Chantier sans lead : `site_adresse`/GPS non repris
- `DC14` — Parrainage : `filleul_nom` peut diverger du FK
- `DC15` — `Fournisseur` n'a ni ICE/IF/RC/RIB
- `DC16` — Montants `FactureFournisseur` saisis à la main
- `DC17` — `CustomUser.poste` en texte libre
- `DC18` — Sujet email hardcodé « Notification Taqinor »
- `DC19` — Dates relance/maintenance non « jours ouvrés »
- `DC20` — UN référentiel `CompteTresorerie`
- `DC21` — UN plan comptable `CompteComptable` (CGNC)
- `DC22` — UNE table de mapping comptable
- `DC23` — UN référentiel de taux de TVA + un selector `tva_par_taux` unique
- `DC24` — UN référentiel d'axes analytiques
- `DC25` — UNE source devise + taux de change
- `DC26` — UN référentiel calendrier : jours ouvrés + fériés marocains
- `DC27` — UNE taxonomie de tags transversale
- `DC28` — UN résolveur `cout_achat_courant`
- `DC29` — UN master employé : `DossierEmploye` OneToOne→`CustomUser`
- `DC30` — Compta comptes auxiliaires tiers
- `DC31` — Contrats
- `DC32` — Portail client (FG228)
- `DC33` — GED
- `DC35` — Datasheet/fiches techniques (FG254)
- `DC36` — Kit/BOM (FG66) & kitting (FG328)
- `DC37` — Serial-at-goods-in (FG61)
- `DC38` — Landed cost (FG316/FG67)
- `DC39` — Référence unique pour tout nouveau module
- `DC40` — Décision modèle `Equipe`
- `DC41` — Permis & habilitations : un seul foyer
- `DC42` — Personnes dans QHSE/Paie/Projet
- `F21` — Offline-tolerant field capture
- `FG1` — Activate the dead notification EventTypes via Celery-Beat sweeps
- `FG2` — Wire the automation engine's time-based triggers
- `FG3` — Automation rule template library (no-code presets)
- `FG4` — Admin-configurable notification routing rules
- `FG5` — Working-hours + Moroccan public-holiday calendar feeding planning/relance
- `FG6` — ICS/iCal calendar feed per user
- `FG7` — Generic comments + @mentions across all records
- `FG8` — Unified, role-scoped cross-record activity feed ("Fil d'activité")
- `FG9` — Shared cross-module tag taxonomy
- `FG10` — Tenant-wide document/attachment center
- `FG11` — Generalize saved filters/views to all list screens
- `FG12` — Wire the existing dark-mode/theme toggle into the app shell
- `FG13` — Surface a push-notification opt-in toggle in settings
- `FG14` — Bulk import for more entities
- `FG15` — Broaden audit-trail coverage + a generic soft-delete/restore standard
- `FG16` — In-app onboarding / setup checklist + contextual help
- `FG17` — Email template management (parity with WhatsApp templates)
- `FG18` — Settings-audit completeness
- `FG19` — Read-only org-chart / team hierarchy view
- `FG20` — Per-field / sensitive-data role permissions
- `FG21` — User invite / self-set-password onboarding
- `FG22` — Per-company password policy & account lockout
- `FG23` — Security-events view + failed-login alerting
- `FG24` — Settings config export/import between companies
- `FG25` — Configurable approval workflows beyond discount
- `FG26` — Data-retention / GDPR tooling
- `FG27` — Lead scoring
- `FG28` — First-response SLA + "lead non contacté" alert
- `FG29` — Time-in-stage age + funnel-velocity analytics
- `FG30` — Unified communication log (calls/emails) in the chatter
- `FG31` — "File de relance du jour" consolidated queue
- `FG32` — Client segmentation (RFM / dormant / top)
- `FG33` — Bulk WhatsApp outreach
- `FG34` — Source/campaign ROI analytics
- `FG35` — "Lead express" quick capture
- `FG36` — Reusable WhatsApp message templates in CRM
- `FG37` — Lead pipeline map view
- `FG38` — Lead↔Client duplicate match at creation
- `FG39` — Sales objectives & KPI targets vs actuals
- `FG40` — Recurring maintenance-contract billing
- `FG41` — Client credit limit / encours gate
- `FG42` — Bank-statement payment import & reconciliation
- `FG43` — Invoice bulk operations
- `FG44` — Quote refusal with motif
- `FG45` — Ventes quote-to-cash finance dashboard
- `FG46` — Flexible échéancier + stored acompte
- `FG47` — Cash-flow / receivables forecast
- `FG48` — On-screen two-option quote comparison
- `FG49` — Account-coded accounting export (PCG/Sage layout)
- `FG50` — Acompte transfer/refund on invoice cancel
- `FG51` — Proof-of-delivery gate before invoicing
- `FG52` — Multi-currency quoting/invoicing
- `FG53` — E-payment "Payer en ligne" link
- `FG54` — Reorder-point auto-PO suggestions
- `FG55` — Supplier-invoice PDF (facture fournisseur)
- `FG56` — "Facturer cette réception" line-driven supplier invoice
- `FG57` — Dead-stock / rotation aging report
- `FG58` — Supplier price-list comparison UI
- `FG59` — Supplier performance scorecard
- `FG60` — Stock-movement filters + xlsx export
- `FG61` — Serial/lot capture at goods-in
- `FG62` — Per-location min/max + van replenishment
- `FG63` — Inventory-count session workflow
- `FG64` — Battery/sealant expiry tracking
- `FG65` — Demand forecasting reorder quantities
- `FG66` — Kit/BOM as a sellable catalogue product
- `FG67` — FIFO / landed-cost valuation option
- `FG68` — Crew dispatch calendar + technician capacity for interventions
- `FG69` — Captured client signature (sign-off) on compte-rendu / PV de réception
- `FG70` — Auto warranty handover at RECEPTIONNE
- `FG71` — Per-chantier job-costing roll-up
- `FG72` — Multi-day chantier planning
- `FG73` — Technician day route/itinerary
- `FG74` — Cross-chantier Gantt / milestone timeline
- `FG75` — Roof/drone site-survey attachment surface on the chantier
- `FG76` — Photo-required gate on chantier checklist steps
- `FG77` — Pre-pose readiness check
- `FG78` — Intervention RDV confirmation + reschedule/no-show tracking
- `FG79` — Auto-scaffold the standard intervention chain from chantier type
- `FG80` — Outillage calibration/inspection tracking
- `FG81` — Server-side ticket SLA (response/resolution clocks + breach)
- `FG82` — Maintenance-visit checklist / structured visit report
- `FG83` — Supplier warranty-claim (RMA) workflow
- `FG84` — Per-system production history chart + expected-vs-actual + CSV
- `FG85` — Equipment QR labels + scan-to-equipment/ticket
- `FG86` — Public tokenized "track your SAV request" link
- `FG87` — SAV knowledge base (resolution playbooks)
- `FG88` — Maintenance route/day planning for preventive visits
- `FG89` — Spare-parts forecasting from PieceConsommee history
- `FG90` — Chronic/repeat-failure equipment flag
- `FG91` — SavedReport frontend (CRUD + schedule + optional dashboard pin)
- `FG92` — Period comparison (MoM/YoY) on dashboard & reports
- `FG93` — Sales-rep leaderboard
- `FG94` — Activate custom-field reporting
- `FG95` — PDF export for reports (branded)
- `FG96` — Configurable / per-role dashboard
- `FG97` — Audit-log analytics
- `FG98` — Cohort / seasonality conversion analysis
- `FG99` — Profitability by segment
- `FG100` — Custom fields for Devis / Chantier / Ticket
- `FG101` — Drill-down from report rows/charts to filtered lists
- `FG102` — Webhook delivery log + retry/replay + test ping UI
- `FG103` — More webhook events
- `FG104` — Public API filtering, ordering & incremental sync
- `FG105` — Public API documentation page
- `FG106` — OCR → draft lead / draft devis action
- `FG107` — Plan comptable CGNC
- `FG108` — Journaux + écritures (comptabilité en partie double)
- `FG109` — Auto-génération des écritures depuis factures/paiements/avoirs/factures fournisseur
- `FG110` — Grand livre
- `FG111` — Balance générale (trial balance)
- `FG112` — Lettrage & rapprochement client/fournisseur
- `FG113` — Compte de Produits et Charges (CPC / P&L marocain)
- `FG114` — Bilan comptable (format CGNC)
- `FG115` — Clôture & verrouillage de période comptable
- `FG116` — Écritures de régularisation / OD manuelles
- `FG117` — À-nouveaux / réouverture d'exercice
- `FG118` — Registre des immobilisations
- `FG119` — Plan d'amortissement (linéaire/dégressif)
- `FG120` — Cession / mise au rebut d'immobilisation
- `FG121` — Référentiel comptes bancaires & caisses
- `FG122` — Position de trésorerie consolidée + projection
- `FG123` — Rapprochement bancaire (relevé ↔ écritures)
- `FG124` — Caisse / petty cash (journal d'espèces)
- `FG125` — Virements internes entre comptes
- `FG126` — Prévisionnel de trésorerie roulant 13 semaines
- `FG127` — Portefeuille d'effets à recevoir (chèques/traites clients)
- `FG128` — Effets à payer fournisseurs
- `FG129` — Bordereau de remise en banque (chèques/effets)
- `FG130` — Gestion des impayés / rejets d'effets
- `FG131` — Rapprochement 3 voies (BC ↔ réception ↔ facture fournisseur)
- `FG132` — Échéancier & relevé fournisseur (aged payables + statement)
- `FG133` — Campagnes de règlement fournisseurs (payment run)
- `FG134` — Génération de fichier de virement bancaire
- `FG135` — Notes de frais & remboursements employés
- `FG136` — Indemnités kilométriques & per-diem chantier
- `FG137` — Préparation de la déclaration TVA
- `FG138` — Relevé de déductions détaillé (annexe TVA)
- `FG139` — Retenue à la source (RAS) sur honoraires/prestations
- `FG140` — Aide au calcul de l'IS
- `FG141` — Export FEC (fichier des écritures comptables)
- `FG142` — Trousse liasse fiscale (états de synthèse)
- `FG143` — Déclaration des honoraires / état 9421
- `FG144` — Calcul du timbre fiscal sur encaissements espèces
- `FG145` — Retenue de garantie & cautions sur marchés (RG / bonne fin)
- `FG146` — Reconnaissance du revenu par avancement (% completion)
- `FG147` — Produits constatés d'avance & travaux en cours (WIP)
- `FG148` — Campagnes de versement des commissions (payout run)
- `FG149` — Budgets annuels & suivi budget-vs-réalisé
- `FG150` — Comptabilité analytique / centres de coût
- `FG151` — Tableau de bord financier directeur
- `FG152` — Provisions pour créances douteuses
- `FG153` — Inter-sociétés / consolidation multi-entités
- `FG154` — Module RH (app dédiée) + dossier employé
- `FG155` — Type de contrat & dates
- `FG156` — Identité & numéros légaux employé
- `FG157` — Rémunération de base (gated rôle RH)
- `FG158` — Contact d'urgence & coordonnées étendues
- `FG159` — Coffre documents employé
- `FG160` — Référentiels Poste & Département
- `FG161` — Cycle de vie & offboarding
- `FG162` — Soldes & droits à congés (Maroc)
- `FG163` — Demande & validation de congés (workflow)
- `FG164` — Typologie d'absences
- `FG165` — Calendrier d'absences d'équipe → planning
- `FG166` — Pointage / clock-in–out
- `FG167` — Feuilles de temps par chantier (timesheets)
- `FG168` — Heures supplémentaires & calcul majoré
- `FG169` — Planning d'équipes / roster (shifts)
- `FG170` — Registre de présence chantier journalier (émargement)
- `FG171` — Retards & absences injustifiées
- `FG172` — Matrice de compétences
- `FG173` — Habilitations électriques (B1V/BR/B2V/H0…)
- `FG174` — Certifications spécifiques
- `FG175` — Alertes d'expiration (habilitations/certifs/docs)
- `FG176` — Garde d'affectation par habilitation
- `FG177` — Visite médicale du travail
- `FG178` — Catalogue & dotation EPI
- `FG179` — Suivi péremption/contrôle des EPI
- `FG180` — Émargement de remise EPI (signature)
- `FG181` — Registre HSE & accidents du travail
- `FG182` — Presqu'accidents (near-miss)
- `FG183` — Causeries sécurité / toolbox talks
- `FG184` — Analyse de risques chantier (plan de prévention)
- `FG185` — Tableau de bord HSE
- `FG186` — Permis de travail (hauteur/électrique/consignation)
- `FG187` — Gestion de la formation
- `FG188` — Plan & registre de formation
- `FG189` — Recrutement (ATS-lite)
- `FG190` — Entretiens & évaluations annuelles
- `FG191` — Disciplinaire & sanctions
- `FG192` — Éléments variables de paie (export)
- `FG193` — Primes & indemnités
- `FG194` — Ordre de mission (déplacement chantier)
- `FG195` — Avances sur salaire
- `FG196` — Bulletin de paie (lecture seule)
- `FG197` — Suivi des permis de conduire & habilitation à conduire
- `FG198` — Affectation conducteur ↔ véhicule
- `FG199` — Portail self-service employé
- `FG200` — Cockpit RH (effectifs & coûts)
- `FG201` — Campagnes email & SMS
- `FG202` — Séquences de relance automatisées (drip/nurture)
- `FG203` — Récupération des devis abandonnés
- `FG204` — Tableau d'attribution multi-touch
- `FG205` — Tracking d'ouverture des ShareLink devis/facture
- `FG206` — Constructeur de formulaires / landing pages multiples
- `FG207` — Capture de leads via WhatsApp (catalogue/chatbot)
- `FG208` — Journal d'appels & click-to-call
- `FG209` — Promotions & campagnes de remise
- `FG210` — Bibliothèque de modèles de devis
- `FG211` — Configurateur d'options guidé (guided selling)
- `FG212` — Comparateur de versions de devis (UI)
- `FG213` — Routage d'approbation des configurations non-standard
- `FG214` — E-catalogue à prix publics
- `FG215` — Bibliothèque de documents de proposition
- `FG216` — Simulateur public « configurez votre kit » → lead
- `FG217` — Simulation de financement dans le devis (crédit/leasing)
- `FG218` — Offres de banques/partenaires de financement
- `FG219` — Ligne d'incitation / subvention (Tatwir/MASEN)
- `FG220` — Paiement échelonné (type Tayssir) sur facture
- `FG221` — Comparateur cash vs financement
- `FG222` — Gestion des appels d'offres (public/privé)
- `FG223` — Bordereau des prix (BOQ) d'appel d'offres
- `FG224` — Suivi des cautions & garanties de soumission
- `FG225` — Dossier de soumission (pièces administratives)
- `FG226` — Échéancier & alertes de deadline d'AO
- `FG227` — Analyse gagné/perdu des appels d'offres
- `FG228` — Portail self-service client
- `FG229` — Acceptation/e-signature de devis dans le portail
- `FG230` — Paiement en ligne des factures (portail)
- `FG231` — Téléchargement docs & dépôt factures ONEE par le client
- `FG232` — Suivi d'avancement du chantier côté client
- `FG233` — Ouverture de ticket SAV depuis le portail
- `FG234` — Portail apporteurs / sous-revendeurs
- `FG235` — Suivi des commissions partenaires
- `FG236` — Gestion des territoires / zones commerciales
- `FG237` — Annuaire & onboarding des installateurs partenaires
- `FG238` — Enquêtes NPS / satisfaction post-installation
- `FG239` — Capture d'avis/témoignages + push Google Reviews
- `FG240` — Programme de fidélité / parrainage étendu
- `FG241` — Moteur d'upsell / cross-sell
- `FG242` — Suivi des concurrents sur deals perdus
- `FG243` — Pipeline de renouvellement de contrats O&M
- `FG244` — Abonnements de monitoring
- `FG245` — Éditeur de calepinage toiture (placement panneaux)
- `FG246` — Calcul de chaînes (string design) & vérif ratio DC/AC
- `FG247` — Appariement module–onduleur depuis le catalogue
- `FG248` — Pont 3D toiture web → ERP
- `FG249` — Optimisation inclinaison/azimut
- `FG250` — Analyse d'ombrage & profil d'horizon
- `FG251` — Générateur de nomenclature électrique (BOQ)
- `FG252` — Brouillon de schéma unifilaire (SVG)
- `FG253` — Aide au calcul de charge structure toiture
- `FG254` — Bibliothèque de fiches techniques modules/onduleurs (PAN/OND)
- `FG255` — Dimensionnement borne de recharge VE
- `FG256` — Étude de stockage & dispatch batterie (backup)
- `FG257` — Simulation bankable P50/P90 avec modèle de pertes
- `FG258` — Profil d'autoconsommation horaire depuis courbe de charge
- `FG259` — Économie net-metering / injection surplus (loi 13-09/MT)
- `FG260` — Modélisation escalade tarifaire ONEE sur 20–25 ans
- `FG261` — Optimisation puissance souscrite (C&I)
- `FG262` — Modélisation dégradation modules sur la durée
- `FG263` — Modèle financier PPA / tiers-investisseur
- `FG264` — Rendement pompage par cycle de marche
- `FG265` — Flux d'irradiance/météo pour simulations
- `FG266` — Comparateur de scénarios de devis
- `FG267` — Packs documentaires réglementaires par régime
- `FG268` — Checklists & échéances de soumission ONEE/raccordement
- `FG269` — Suivi de soumission & navette opérateur
- `FG270` — Éligibilité & suivi des subventions/incitations
- `FG271` — Workflow de régularisation Article 33 / déclarations 82-21
- `FG272` — Générateur de déclaration de raccordement BT/MT
- `FG273` — Calendrier réglementaire & alertes d'expiration de dossiers
- `FG274` — Protocole d'essais de mise en service IEC 62446
- `FG275` — Capture de courbe I-V par string
- `FG276` — Pack documentaire « as-built »
- `FG277` — Attestation/certificat de conformité électrique
- `FG278` — Test de performance de réception (PR initial)
- `FG279` — Analytique O&M : PR, disponibilité, soiling, dégradation
- `FG280` — Gestion fine des alarmes/défauts onduleur
- `FG281` — Tableau de bord parc/flotte multi-systèmes
- `FG282` — Suivi de garantie de production & compensation de manque
- `FG283` — Détection & suivi de pertes par salissure
- `FG284` — Suivi garantie vs courbe de dégradation fabricant
- `FG285` — Adaptateurs monitoring supplémentaires (SolarEdge/Sungrow/Solis)
- `FG286` — Reporting CO₂ évité par système & cumulé
- `FG287` — Certificats d'énergie renouvelable / attestations RE
- `FG288` — Tableau de bord environnemental client (portail)
- `FG289` — Rapport O&M périodique automatisé (PDF + email)
- `FG290` — Registre des garanties matériel & échéancier de fin par parc
- `FG291` — Programme / Projet multi-chantiers
- `FG292` — Tâches & sous-tâches de projet avec dépendances
- `FG293` — Jalons & phases de projet
- `FG294` — Budget projet vs réel (engagé/dépensé)
- `FG295` — P&L de projet consolidé
- `FG296` — Modèles de projet (templates de chantier-type)
- `FG297` — Contrôle documentaire de projet (plans & révisions)
- `FG298` — Comptes-rendus de réunion de chantier
- `FG299` — Plan de charge des équipes (capacité vs affecté)
- `FG300` — Détection de conflits d'affectation
- `FG301` — Nivellement de charge (resource levelling)
- `FG302` — Calendrier de disponibilité ressources
- `FG303` — Planning des camionnettes (capacité véhicule)
- `FG304` — Référentiel sous-traitants
- `FG305` — Ordres de travaux sous-traitant
- `FG306` — Factures & règlements sous-traitant
- `FG307` — Attestations & assurances sous-traitant
- `FG308` — Évaluation de performance sous-traitant
- `FG309` — Retenue de garantie sur sous-traitant
- `FG310` — Demande d'achat (réquisition) → approbation
- `FG311` — RFQ multi-fournisseurs & comparatif d'offres
- `FG312` — Paliers d'approbation de BCF par seuil
- `FG313` — Contrôle budgétaire à la commande
- `FG314` — Commandes-cadres / contrats annuels (blanket orders)
- `FG315` — Suivi import / dédouanement
- `FG316` — Frais d'import & coût de revient débarqué (landed cost)
- `FG317` — Réceptionné-non-facturé (GR/IR)
- `FG318` — Contrats & accords de prix fournisseur
- `FG319` — Emplacements fins zone/allée/casier (bin locations)
- `FG320` — Rangement guidé (put-away)
- `FG321` — Bons de prélèvement (pick list) par chantier
- `FG322` — Colisage / préparation (pack)
- `FG323` — Suivi du stock par numéro de série en entrepôt
- `FG324` — Sessions de comptage tournant (cycle count ABC)
- `FG325` — Demande de transfert inter-emplacements (workflow)
- `FG326` — Réapprovisionnement multi-dépôts
- `FG327` — Stock en consignation / emballages consignés
- `FG328` — Pré-assemblage / kitting magasin
- `FG329` — Planification des livraisons (dépôt → site)
- `FG330` — Preuve de livraison (POD)
- `FG331` — Transporteurs & tarifs de transport
- `FG332` — Optimisation de tournée de livraison multi-sites
- `FG333` — Réservation à la livraison (dépôt vs site)
- `FG334` — Référentiel véhicules (flotte)
- `FG335` — Échéances réglementaires véhicule
- `FG336` — Carnet de carburant (suivi gasoil)
- `FG337` — Planning d'entretien véhicule
- `FG338` — Journal kilométrique & affectation conducteur
- `FG339` — Coût total de possession du véhicule
- `FG340` — Parc de machines & équipements propres
- `FG341` — Compteur d'heures & maintenance des machines
- `FG342` — Location de matériel (interne & externe)
- `FG343` — Plans d'inspection (ITP / plan de contrôle)
- `FG344` — Points d'arrêt (hold points)
- `FG345` — Non-conformités (NCR)
- `FG346` — Actions correctives & préventives (CAPA)
- `FG347` — Registre de conformité électrique / essais
- `FG348` — Inductions sécurité / accueil sur site
- `FG349` — Audit qualité de fin de chantier (scoring)
- `FG350` — Copilote in-app (CopilotPanel)
- `FG351` — Actions en langage naturel — « crée un devis pour… »
- `FG352` — RAG sur documents & manuels (DocQA)
- `FG353` — Résumé automatique d'un fil (lead/chantier/ticket)
- `FG354` — Brouillon de réponse email/WhatsApp
- `FG355` — OCR CIN / contrat / pièce d'identité
- `FG356` — OCR bon de livraison enrichi → réception stock
- `FG357` — Voice-to-text notes terrain
- `FG358` — Photo AI QA sur photos d'installation
- `FG359` — Next-best-action recommandée
- `FG360` — Détection d'anomalies (stock/paiements/fraude)
- `FG361` — Prévision de ventes / demande
- `FG362` — Score de probabilité de gain (win-probability)
- `FG363` — Score de churn / risque client
- `FG364` — Prévision de réappro stock
- `FG365` — Prédiction de retard de paiement
- `FG366` — Moteur de workflow multi-étapes (BPM) + SLA/escalades
- `FG367` — Conditions multi-critères & branches dans les règles
- `FG368` — UI de gestion des tâches planifiées (jobs)
- `FG369` — Bibliothèque de modèles de workflow
- `FG370` — Passerelle de paiement CMI / Payzone
- `FG371` — Passerelle SMS marocaine
- `FG372` — E-signature (Yousign/DocuSign)
- `FG373` — Email entrant IMAP → leads/tickets
- `FG374` — Sync calendrier Google/Outlook (2-way)
- `FG375` — Géocodage & cartes (Maps)
- `FG376` — Connecteur Zapier / Make
- `FG377` — Pont comptable Sage / CEGID (one-way)
- `FG378` — Connecteur Odoo Compta (JSON-2, 2-way)
- `FG379` — Open banking (flux bancaire automatique)
- `FG380` — Constructeur de tableau croisé (pivot)
- `FG381` — Constructeur de graphiques/dashboards sans-code
- `FG382` — BI embarqué — explorateur de données
- `FG383` — Extraits planifiés vers entrepôt/SFTP/S3
- `FG384` — Scan code-barres / QR (BarcodeDetector)
- `FG385` — Capture photo caméra en direct
- `FG387` — Application mobile native (Capacitor)
- `FG388` — Corbeille / restauration (soft-delete + undo)
- `FG389` — Édition en masse partout (bulk edit)
- `FG390` — Champs personnalisés calculés (formules)
- `FG391` — Flags de fonctionnalités / modules par tenant
- `FG392` — Thème white-label par tenant
- `FG393` — Éditeur de modèles imprimables/brandés
- `FG394` — Consentement & DSR (loi 09-08 / CNDP)
- `FG395` — Sauvegarde/restauration en libre-service
- `FG396` — Monitoring d'erreurs (Sentry)
- `FG397` — Page d'état / santé système
- `FG398` — Plans de tarif API & analytics d'usage
- `FG399` — Journal des nouveautés in-app (changelog)
- `FLOTTE1` — Nouvelle app `apps/flotte` (squelette multi-tenant)
- `FLOTTE2` — Modèle `Vehicule` (immat/marque/énergie/km/valeur/statut)
- `FLOTTE3` — Lien `Vehicule.emplacement_stock` ↔ `stock.EmplacementStock` (via selector)
- `FLOTTE4` — `EnginRoulant` (compteur d'heures, nacelle/groupe/chariot)
- `FLOTTE5` — Référence d'actif commune (Vehicule|Engin) pour entretien/sinistre/doc
- `FLOTTE6` — Référentiels listes (type véhicule/engin, énergie, catégorie permis)
- `FLOTTE7` — `Conducteur` + permis (lien `authentication.User`)
- `FLOTTE8` — `AffectationConducteur` (conducteur↔véhicule datée)
- `FLOTTE9` — Contrôle permis valide/catégorie à l'affectation
- `FLOTTE10` — `ReservationVehicule` + détection de conflit
- `FLOTTE11` — Check-list état des lieux départ/retour (photos)
- `FLOTTE12` — Carnet de carburant (`PleinCarburant`)
- `FLOTTE13` — Calcul conso L/100 km (et kWh/100 km)
- `FLOTTE14` — Cartes carburant & alertes anomalie (km incohérent/fraude)
- `FLOTTE15` — Plans d'entretien préventif (km/date/heures)
- `FLOTTE16` — Génération d'échéances d'entretien dues + alertes
- `FLOTTE17` — Ordres de réparation + atelier/garage + coûts
- `FLOTTE18` — Pneumatiques & pièces
- `FLOTTE19` — `EcheanceReglementaire` (modèle générique)
- `FLOTTE20` — Vignette / TSAV (barème CV/énergie, référentiel éditable)
- `FLOTTE21` — Assurance auto (police/échéance/attestation/franchise)
- `FLOTTE22` — Visite technique (validité paramétrable)
- `FLOTTE23` — Carte grise & autorisation de circulation (GED)
- `FLOTTE24` — Moteur d'alertes d'échéances réglementaires (J-30/15/7/échu)
- `FLOTTE25` — `Sinistre` (accident/constat/assurance)
- `FLOTTE26` — `Infraction` / PV de circulation
- `FLOTTE27` — Point d'intégration télématique (no-op sans fournisseur)
- `FLOTTE28` — Suivi de position & trajets télématiques
- `FLOTTE29` — Journal kilométrique & trajets par chantier (via `installations.selectors`)
- `FLOTTE30` — Amortissement (lien immobilisations)
- `FLOTTE31` — Coût total de possession (TCO) par véhicule (interne)
- `FLOTTE32` — Pool de véhicules & demandes
- `FLOTTE33` — Éco-conduite & CO₂
- `FLOTTE34` — Documents véhicule (GED)
- `FLOTTE35` — Tableau de bord flotte (dispo/échéances/coûts/conso)
- `G5` — Supplier procurement module (a dedicated multi-session module): bons de commande…
- `GED1` — Squelette de l'app `apps/ged` (services/selectors, scoping société)
- `GED2` — Cabinet + Folder arborescent (path matérialisé)
- `GED3` — Document + DocumentVersion (file_key MinIO, checksum/dedupe)
- `GED4` — CRUD dossiers/documents + déplacement (scopé société)
- `GED5` — Navigateur arborescent FR (frontend)
- `GED6` — Liaison polymorphe Document↔objet métier (étend `records.ALLOWED_TARGETS`)
- `GED7` — Migration des `records.Attachment` existants (réutilise file_key)
- `GED8` — Coffre-fort par employé/client (ACL owner+admin)
- `GED9` — Taxonomie de tags
- `GED10` — Métadonnées typées configurables (réutilise `customfields`)
- `GED11` — Recherche plein-texte Postgres (SearchVector + GIN)
- `GED12` — Index OCR + recherche sémantique (pgvector, key-gated no-op)
- `GED13` — Filtres & recherche avancée (frontend)
- `GED14` — Aperçu inline multi-format (proxy même-origine)
- `GED15` — Versionnage + historique + restauration de version
- `GED16` — Check-out / check-in (verrouillage)
- `GED17` — Cycle de vie documentaire (brouillon→revue→approuvé→archivé→obsolète)
- `GED18` — Workflow d'approbation/revue
- `GED19` — ACL par dossier/document (héritage + override)
- `GED20` — Partage par lien tokenisé (expiry/mot de passe/quota)
- `GED21` — Watermarking & contrôle de diffusion
- `GED22` — Politiques de rétention
- `GED23` — Archivage légal à valeur probante (write-once/object-lock)
- `GED24` — Rétention légale / legal hold
- `GED25` — Purge automatique & tâche planifiée (dry-run d'abord)
- `GED26` — Corbeille & restauration
- `GED27` — Modèles de documents (fusion/mailing → PDF WeasyPrint, hors /proposal)
- `GED28` — Génération de document → classement automatique
- `GED29` — Filage des PDF après-vente générés (depuis `documents`)
- `GED30` — Signature électronique (point d'intégration + stub no-op)
- `GED31` — Numérisation par lot (scan-to-DMS) + OCR
- `GED32` — Import en masse (zip/CSV de métadonnées)
- `GED33` — OCR de pièces (CIN/factures/BL) → métadonnées
- `GED34` — Classification automatique (IA, no-op sans clé)
- `GED35` — Journal d'audit d'accès aux documents (lectures)
- `GED36` — Quotas de stockage par société
- `GED37` — Permissions & garde-prix sur tous les endpoints
- `GED38` — Contrats d'import + CODEMAP + tests
- `KB1` — App `kb` + `KbArticle` (titre/corps/catégorie/tags, company FK)
- `KB2` — Versionnage des articles + statut (brouillon/publié/obsolète)
- `KB3` — Recherche plein-texte + filtres par catégorie/tag
- `KB4` — Lien article ↔ produit/équipement/type d'intervention (contextuel sur SAV/chantier)
- `KB5` — Procédures/SOP d'installation & dossiers ONEE/82-21 (gabarits seedés)
- `KB6` — Source de contenu pour le RAG/DocQA (FG352) — indexation pgvector
- `KB7` — Droits d'accès par rôle + suivi de lecture
- `LITIGE1` — App `litiges` + modèle `Reclamation` (type, gravité, source FK polymorphe, statut)
- `LITIGE2` — Workflow statut (ouverte→en_traitement→résolue/rejetée) + chatter
- `LITIGE3` — Litige financier ↔ recouvrement : suspendre les relances d'une facture en litige
- `LITIGE4` — Litige qualité ↔ QHSE : lien NCR + audit fin de chantier
- `LITIGE5` — Capture du concurrent/motif sur deal perdu (étend FG242)
- `LITIGE6` — Tableau de bord litiges (ouverts/montant contesté/délai de résolution)
- `M1` — Replace every load-time cross-app model import in the core apps with Django string FK…
- `M2` — Make `services.py` / `selectors.py` the only cross-app entry point: route cross-app…
- `M3` — Add an `import-linter` contract run in CI that forbids import cycles among the core…
- `M4` — Formalise the three layers (foundation: authentication/roles/records/customfields/core…
- `M5` — Use the empty `core/` app for shared primitives: move the tenant base mixin and the…
- `M6` — Replace the hottest direct cross-app calls with a small domain-event layer (e.g. emit…
- `M7` — Split the god-files (no behaviour change): turn the large `views.py` into a `views/`…
- `N53` — Client energy-yield report PDF (French) from ESTIMATED / MANUAL data (nameplate kWc +…
- `N76` — Daily & weekly digest notification for Reda & Meryem (jobs to plan, quotes awaiting…
- `N79` — Saved-reports & custom-views capability: save filtered/grouped views of any major…
- `N91` — Offline-tolerant field capture for the chantier checklist, photos, and PV de réception…
- `N92` — PWA web push notifications for high-priority events from the notification engine
- `N93` — Full Arabic & Darija localisation as a selectable interface language with RTL layout…
- `N94` — Translation-management surface in settings so interface strings can be…
- `N96` — Account security: optional 2FA, visible active sessions with revoke, forced…
- `N108` — Attachment upload crashes with NoSuchBucket (HTTP 500)
- `N109` — Activate Web Push end-to-end (complete N92)
- `N110` — Admin cannot change a user's role manually (Administration → Utilisateurs → edit…
- `ODX2` — Manifest de module par app (façon __manifest__.py)
- `ODX3` — Catalogue de modules + fermeture de dépendances sur activer/désactiver
- `ODX4` — Enforcement API des modules désactivés
- `ODX9` — Sortir le marketing de compta — étape 1 (modèles, state-only)
- `ODX10` — Sortir le marketing de compta — étape 2 (vues/urls/frontend)
- `ODX21` — Test de cohérence registre ↔ apps (garde CI légère)
- `PAIE1` — App `paie` + permissions `paie_voir`/`paie_gerer`
- `PAIE2` — `ParametrePaie` : constantes par société versionnées (SMIG/SMAG, plafond CNSS, taux…
- `PAIE3` — Valeurs légales par défaut (taux/plafonds 2026) + validation fondateur
- `PAIE4` — `BaremeIR` : tranches + somme à déduire, versionné par date d'effet
- `PAIE5` — Barème IR officiel + déductions charges de famille
- `PAIE6` — `Rubrique` paramétrable (gain/retenue/cotisation, flags imposable/CNSS/AMO/CIMR, compte)
- `PAIE7` — Catalogue de rubriques standard (transport/panier/ancienneté/HS…) — seed idempotent
- `PAIE8` — `ProfilPaie` (OneToOne→DossierEmploye) : type rémunération, salaire base, affiliations…
- `PAIE9` — `RubriqueEmploye` : rubriques récurrentes par employé
- `PAIE10` — `PeriodePaie` : run mensuel + statuts brouillon→calculée→validée→clôturée
- `PAIE11` — `ElementVariable` + import depuis RH (heures/HS/absences/primes)
- `PAIE12` — Moteur de calcul du bulletin (`services.calculer_bulletin`)
- `PAIE13` — Salaire de base multi-profils (mensuel/journalier/forfait/horaire) + proration
- `PAIE14` — Heures supplémentaires majorées (25/50/100 % jour/nuit/férié)
- `PAIE15` — Prime d'ancienneté barème (5/10/15/20/25 %)
- `PAIE16` — Avantages en nature & indemnités imposables vs non-imposables (plafonds)
- `PAIE17` — `BulletinPaie` + `LigneBulletin` (snapshot immuable une fois validé)
- `PAIE18` — CNSS plafonnée (part salariale & patronale)
- `PAIE19` — AMO (sans plafond) salariale & patronale
- `PAIE20` — CIMR optionnelle (taux par employé adhérent)
- `PAIE21` — Frais professionnels & net imposable
- `PAIE22` — Calcul IR (barème progressif + charges de famille)
- `PAIE23` — Allocations familiales (info patronale)
- `PAIE24` — Taxe de formation professionnelle (1,6 % patronal)
- `PAIE25` — Provision congés payés (consomme les soldes RH)
- `PAIE26` — Paiement & décompte des congés/absences sur le bulletin
- `PAIE27` — `CumulAnnuel` (brut/net imposable/IR/CNSS/congés)
- `PAIE28` — `Avance`/`PretSalarie` + déduction mensuelle
- `PAIE29` — Saisie-arrêt / cession sur salaire (quotité saisissable)
- `PAIE30` — `OrdreVirement` + fichier de virement banque
- `PAIE31` — Déclaration CNSS (BDS / format DAMANCOM)
- `PAIE32` — État IR 9421 + retenues à la source
- `PAIE33` — Livre de paie + journal de paie → écritures (via `compta.services`)
- `PAIE34` — PDF bulletin conforme + attestations (salaire/travail/domiciliation) via `documents`
- `PAIE35` — Coffre-fort bulletins (self-service employé, scopé à l'utilisateur)
- `PAIE36` — Clôture mensuelle + verrouillage + bulletins rectificatifs/rappels
- `PROJ1` — Modèle `Projet`/Programme multi-chantiers + `ProjetChantier`
- `PROJ2` — Liens projet → devis/factures/tickets/achats (string-FK via selectors)
- `PROJ3` — Machine à états du projet (propre, jamais STAGES.py)
- `PROJ4` — Phases de projet (étude/appro/pose/MES/réception)
- `PROJ5` — Tâches & sous-tâches (WBS)
- `PROJ6` — Dépendances de tâches FS/SS/FF/SF + lag
- `PROJ7` — Jalons (+ `facturation_pct`)
- `PROJ8` — Calcul du chemin critique (CPM) + marges
- `PROJ9` — Roll-up d'avancement (pondéré par charge)
- `PROJ10` — API planning Gantt
- `PROJ11` — Drag-reschedule des tâches (recalcule les successeurs)
- `PROJ12` — Calendrier projet (jours ouvrés/fériés)
- `PROJ13` — Baseline de planning (plan vs réel)
- `PROJ14` — Détection des retards (tâches/jalons à risque)
- `PROJ15` — Profil ressource & équipes (RH-léger, `cout_horaire` interne)
- `PROJ16` — Affectation des ressources (User/équipe/camionnette/machine)
- `PROJ17` — Indisponibilités ressources (congé/formation/arrêt)
- `PROJ18` — Plan de charge (capacité vs affecté)
- `PROJ19` — Détection de conflits d'affectation
- `PROJ20` — Nivellement de charge (levelling)
- `PROJ21` — Budget projet (lignes : matériel/MO/sous-traitance/divers)
- `PROJ22` — Coûts engagés vs réels (factures fournisseur + MO + sous-traitance)
- `PROJ23` — Alertes de dépassement budgétaire
- `PROJ24` — Suivi des temps (timesheets imputés au projet)
- `PROJ25` — Consommation matière vs BoM (via selectors)
- `PROJ26` — P&L de projet consolidé (interne/admin)
- `PROJ27` — Jalons de facturation liés à l'avancement (via `ventes.services`)
- `PROJ28` — Suivi avancement vs facturé
- `PROJ29` — EVM léger (valeur acquise) — optionnel
- `PROJ30` — Registre des risques
- `PROJ31` — Registre d'actions
- `PROJ32` — Comptes-rendus de réunion de chantier
- `PROJ33` — Documents & plans versionnés
- `PROJ34` — Commentaires & @mentions
- `PROJ35` — Templates de projet par type d'installation
- `PROJ36` — Tableau de bord portefeuille (avancement/retards/marge/charge)
- `PROJ37` — Portail d'avancement client (sans coûts/marges)
- `PROJ38` — Sous-traitance & clôture + retour d'expérience
- `QHSE1` — App QHSE + socle multi-tenant
- `QHSE2` — ITP : `PlanInspectionModele` + `PointControleModele` (phase/type relevé/hold-point)
- `QHSE3` — Seed ITP solaire par type d'installation
- `QHSE4` — `PlanInspectionChantier` + `ReleveControle` (valeur/conforme/photo)
- `QHSE5` — Auto-conformité des relevés mesurés (vs min/max attendu)
- `QHSE6` — Points d'arrêt bloquants (hold points) gating l'avancement chantier
- `QHSE7` — Relevé courbe I-V par string
- `QHSE8` — Photos de contrôle (avant/pendant/après) via `records.Attachment`
- `QHSE9` — `NonConformite` (NCR : gravité/origine/source/photos)
- `QHSE10` — `ActionCorrectivePreventive` (CAPA) + cause racine
- `QHSE11` — Pont réserve (`installations.Reserve`) → NCR
- `QHSE12` — Relances CAPA en retard (notifications/digest)
- `QHSE13` — Vérification d'efficacité CAPA (clôture conditionnée)
- `QHSE14` — Chatter QHSE (NCR/CAPA/Incident/Audit)
- `QHSE15` — `GrilleAudit` + `CritereAudit` pondérés
- `QHSE16` — `Audit` + `ReponseCritere` + score (→ NCR)
- `QHSE17` — Grille de notation fin de chantier (gate clôture)
- `QHSE18` — `ProcedureQualite` versionnée (docs qualité GED)
- `QHSE19` — `RetourClientQualite` (satisfaction qualité)
- `QHSE20` — Tableau de bord « ISO 9001 readiness »
- `QHSE21` — `EvaluationRisque` (document unique / plan de prévention) + lignes
- `QHSE22` — Document unique requis avant pose (gate statut chantier)
- `QHSE23` — `PermisTravail` (hauteur/élec-consignation/point chaud)
- `QHSE24` — Consignation électrique (LOTO) sur permis électrique
- `QHSE25` — Alerte expiration de permis
- `QHSE26` — `InductionSecurite` (accueil sécurité site, incl
- `QHSE27` — `CauserieSecurite` (toolbox talks + émargement)
- `QHSE28` — `PlanUrgence` / premiers secours (contacts/secouristes/point de rassemblement)
- `QHSE29` — Registre `Incident` (accident/presqu'accident/incident)
- `QHSE30` — Déclaration CNSS de l'accident du travail (échéance légale)
- `QHSE31` — `AnalyseIncident` (arbre des causes) → CAPA
- `QHSE32` — Événement `incident_declared` sur le bus (escalade)
- `QHSE33` — `InspectionSecurite` planifiée (→ NCR)
- `QHSE34` — Statistiques TF / TG (heures travaillées depuis RH)
- `QHSE35` — Inspections/permis dans le digest + calendrier
- `QHSE36` — `Dechet` + `BordereauSuiviDechet` (BSD, loi 28-00 déchets dangereux)
- `QHSE37` — `RecyclageModule` (fin de vie des modules PV)
- `QHSE38` — `ConformiteEnvironnementale` + relances
- `QHSE39` — `BilanCarbone` interne (scopes 1/2/3)
- `QHSE40` — `IndicateurESG` + export reporting
- `UX1` — Kit « ERP module shell » + standard de design
- `UX2` — Cockpit financier
- `UX3` — Plan comptable + journaux
- `UX4` — Saisie d'écriture (grille débit=crédit)
- `UX5` — États financiers CGNC
- `UX6` — Trésorerie & prévisionnel
- `UX7` — Fiscalité & déclarations
- `UX8` — Immobilisations & amortissements
- `UX9` — Rapprochements, budgets & analytique
- `UX10` — Assistant de run de paie
- `UX11` — Bulletin de paie (aperçu)
- `UX12` — Paramètres & barèmes de paie
- `UX13` — Déclarations & virements de paie
- `UX14` — Self-service « Mes bulletins »
- `UX15` — Cockpit flotte (4 KPI north-star)
- `UX16` — Véhicules & engins (liste + fiche)
- `UX17` — Conducteurs & affectations
- `UX18` — Entretien & réparations
- `UX19` — Conformité & documents
- `UX20` — Carburant, sinistres & télématique
- `UX21` — Cockpit RH + centre d'échéances
- `UX22` — Dossier employé (master)
- `UX23` — Congés & absences
- `UX24` — Temps & présence
- `UX25` — Compétences, habilitations & formation
- `UX26` — EPI, recrutement & évaluations
- `UX27` — HSE RH
- `UX28` — Portail self-service employé
- `UX29` — Cockpit QHSE + calendrier
- `UX30` — Non-conformités & CAPA
- `UX31` — Inspections & audits
- `UX32` — Risques, permis & incidents
- `UX33` — Environnement & ESG
- `UX34` — Contrats (liste + fiche cycle de vie)
- `UX35` — Modèles, clauses & versions
- `UX36` — Échéances & alertes contrats
- `UX37` — Finances de contrat
- `UX38` — Projets (liste + machine à états)
- `UX39` — Planning Gantt
- `UX40` — Ressources & capacité
- `UX41` — Budget & P&L projet
- `UX42` — Risques, actions & CR
- `UX43` — Base de connaissances
- `UX44` — Litiges & réclamations
- `UX45` — GED : approbation & signature
- `UX46` — GED : rétention, archivage légal & partage
- `UX47` — GED : tags & liens transverses
- `XACC1` — TVA sur encaissement : mécanique du compte d'attente
- `XACC2` — Import balance d'ouverture & reprise des existants (migration tooling)
- `XACC3` — Auto-suggestion de rapprochement bancaire
- `XACC4` — Modèles de rapprochement (règles de contrepartie automatique)
- `XACC6` — Écritures de stock automatiques (inventaire permanent)
- `XACC7` — Provisions FNP / FAE de fin de période
- `XACC8` — Modèles d'écriture, écritures récurrentes & extourne automatique
- `XACC9` — Calendrier des obligations fiscales
- `XACC10` — Checklist de clôture de période + écriture de solde TVA
- `XACC11` — Prorata de déduction TVA & TVA non déductible
- `XACC14` — Emprunts & crédits-bails (financements de la société)
- `XACC15` — Charges constatées d'avance (étalement des charges prépayées)
- `XACC16` — Amortissements dérogatoires (double plan comptable / fiscal)
- `XACC17` — Table de taux de change + contre-valeur MAD au grand livre
- `XACC18` — Écarts de change réalisés & réévaluation de clôture
- `XACC19` — Générateur d'états financiers personnalisés
- `XACC20` — Ventilation analytique en % multi-sections & règles d'auto-imputation
- `XACC21` — Contrôle du budget COMPTABLE à l'engagement (warning/blocage)
- `XACC22` — Révisions & scénarios budgétaires
- `XACC24` — Validation RIB marocain + approbation des changements de coordonnées bancaires
- `XACC26` — Provisions pour risques & charges + dépréciation des stocks
- `XACC27` — Politique de notes de frais : plafonds par catégorie + OCR du justificatif
- `XACC28` — Refacturation des frais au client (billable expenses)
- `XACC29` — Rapport de continuité des séquences (gap detection)
- `XACC30` — OCR de relevé bancaire
- `XACC32` — Prorata temporis sur la 1re annuité d'amortissement linéaire
- `XACC33` — « Immobiliser » une ligne de facture fournisseur (capitalisation)
- `XACC34` — Remise à l'escompte & endossement des effets
- `XACC35` — Attestations de retenue à la source par prestataire (PDF)
- `XACC36` — OCR facture fournisseur → brouillon de facture d'achat (côté Django)
- `XCTR1` — Produit récurrent → conversion devis-accepté en contrat (quote-to-subscription)
- `XCTR2` — Registre des équipements couverts par contrat
- `XCTR3` — Droits inclus (entitlements) du contrat de maintenance
- `XCTR4` — Routage de couverture d'une intervention : garantie / contrat O&M / facturable
- `XCTR5` — Journal des cycles de facturation récurrente + file d'exceptions
- `XCTR6` — Prorata temporis sur avenant en cours de période
- `XCTR7` — Cascade MRR (new / expansion / contraction / churn / net) + churn par motif
- `XCTR8` — Cohortes de rétention contrats (logo + revenu, NRR/GRR)
- `XCTR9` — CLV (valeur vie client) sur revenu récurrent
- `XCTR10` — Responsable (owner) sur le contrat + MRR par commercial
- `XCTR11` — Campagne de révision tarifaire en masse
- `XCTR12` — Devis de renouvellement généré avant échéance
- `XCTR13` — Unification sav.ContratMaintenance ↔ apps/contrats (validation CONTRAT5 différée + MRR…
- `XCTR14` — Portail client : section « Mes contrats & abonnements »
- `XCTR16` — Facturation à l'usage depuis le monitoring (kWh supervisés / m³ pompés)
- `XCTR17` — Location de matériel SORTANTE (aux clients) — fondation
- `XCTR18` — Caution (dépôt de garantie) sur location
- `XCTR19` — Retour de location : retards, frais automatiques, inspection
- `XCTR20` — Location longue durée en facturation récurrente + prolongation/écourtage
- `XCTR21` — Utilisation & ROI du parc de location
- `XCTR22` — Encaissement récurrent automatique des abonnements (tokenisation carte / mandat) +…
- `XFAC1` — Avances client (paiement sans facture) + affectation multi-factures
- `XFAC2` — Conformité loi 69-21 — délais de paiement légaux (60/120 jours) + amende + données de…
- `XFAC4` — Retenue à la source subie côté client (RAS TVA 2024 / RAS sur honoraires) sur factures…
- `XFAC5` — Promesse de paiement (promise-to-pay) + pause de relance à expiration
- `XFAC6` — Pénalités & intérêts de retard par niveau de relance
- `XFAC7` — Rappel de courtoisie pré-échéance (J-N avant échéance)
- `XFAC8` — Canal par niveau de relance (email / WhatsApp / courrier / tâche d'appel)
- `XFAC9` — Reçu de paiement (quittance) PDF + envoi automatique
- `XFAC10` — Facture pro-forma
- `XFAC11` — Facture consolidée multi-devis/BC d'un même client
- `XFAC12` — Escompte pour règlement anticipé (ex
- `XFAC13` — Abandon de créance (write-off) avec motifs + tolérance petits écarts
- `XFAC14` — Compensation AR/AP (netting) pour un tiers à la fois client et fournisseur
- `XFAC15` — Câbler le scorer de retard de paiement FG365 : score client agrégé + date…
- `XFAC18` — Workflow de revue facture (ségrégation des tâches, style Odoo 19)
- `XFAC19` — QR code de paiement/vérification sur le PDF facture
- `XFAC21` — Dossier contentieux / passage en recouvrement externe
- `XFAC23` — Conditions de paiement par client (délai / fin de mois) pilotant l'échéance des…
- `XFAC24` — Immutabilité de la facture émise (opt-in) — correction par avoir uniquement
- `XFAC25` — Envoi programmé des relevés de compte clients (mensuel, opt-in)
- `XFAC26` — Portail client : relevé de compte, solde courant et balance âgée self-service
- `XFAC27` — Portail client : contester une facture (crée un litige qui suspend les relances)
- `XFAC28` — Blocage crédit dur configurable avec déblocage autorisé (étend FG41)
- `XFAC29` — Facturation électronique DGI SORTANTE — re-vérifier le gate G14 (périmé) puis…
- `XFLT1` — Contrats véhicule (leasing/LLD/location/entretien)
- `XFLT2` — Génération des coûts récurrents de contrat
- `XFLT3` — Grand livre des coûts par véhicule
- `XFLT4` — Fiche véhicule enrichie + cycle de vie complet
- `XFLT5` — Signalement d'anomalie véhicule par le conducteur
- `XFLT6` — Import relevé carte carburant / Jawaz (CSV) + rapprochement
- `XFLT7` — Rapport d'analyse des coûts (pivot + benchmark)
- `XFLT8` — TVA carburant : récupérable vs non déductible
- `XFLT9` — Plafond CGI d'amortissement des véhicules de tourisme
- `XFLT10` — Périodicité visite technique NARSA auto-calculée
- `XFLT11` — Imputation automatique du conducteur sur les infractions
- `XFLT12` — Catalogue de modèles véhicule
- `XFLT13` — Inspections périodiques paramétrables (check-lists DVIR)
- `XFLT14` — Garanties véhicule & pièces + alerte réparation sous garantie
- `XFLT15` — Analyse de remplacement (fin de vie économique)
- `XFLT16` — Cession / sortie de parc
- `XFLT17` — Charte véhicule + signatures sur l'état des lieux
- `XFLT18` — Budget flotte annuel vs réalisé
- `XFLT19` — Approbation des devis de réparation externe
- `XFLT20` — Registre de remise clés / carte / badge / tag Jawaz
- `XFLT21` — Journal d'audit flotte
- `XFLT22` — Import CSV du parc + opérations en masse
- `XFLT23` — OCR reçu carburant → pré-remplissage du plein
- `XFLT24` — Géofencing sur les données télématiques
- `XFLT25` — Codes défaut moteur (DTC) sur les relevés télématiques
- `XFLT26` — ICE/IF fournisseurs flotte (préparation e-facturation DGI)
- `XFLT27` — Conformité transport lourd (chronotachygraphe & conducteur professionnel)
- `XFLT28` — Rappels constructeur (recall)
- `XFLT29` — Avantage en nature véhicule → paie
- `XFLT30` — Ventilation d'une facture fournisseur sur plusieurs véhicules
- `XFSM1` — Facturation SAV hors garantie depuis le ticket (réels → facture)
- `XFSM2` — Assistant de planification : meilleur créneau + technicien suggéré
- `XFSM3` — Replanification en masse d'une journée (pluie / technicien malade)
- `XFSM4` — Priorité sur l'Intervention (urgence/normale) pilotant le dispatch
- `XFSM5` — Fenêtres de RDV promises + taux de ponctualité
- `XFSM6` — Rappel client J-1 automatique avec lien de confirmation
- `XFSM7` — Lien public « technicien en route » (suivi de visite)
- `XFSM8` — Notes d'accès site réutilisées à chaque visite
- `XFSM10` — Astreinte / rotation après-heures
- `XFSM12` — Trace d'étalonnage de l'instrument sur le PV de recette
- `XFSM13` — Re-vérification périodique IEC 62446-2 avec comparaison à la baseline
- `XFSM14` — Thermographie IR : points chauds classés + baseline/suivi
- `XFSM15` — Suivi des récidives (callbacks / retour sur panne)
- `XFSM16` — Rapport analytics field service (FTF, MTTR, ponctualité, récidive)
- `XFSM17` — Scorecard technicien (coaching)
- `XFSM18` — Réserve/déficience → devis de réparation
- `XFSM19` — Rapprochement des encaissements terrain par technicien
- `XFSM21` — Météo sur le planning (travaux toiture)
- `XFSM22` — Durée & pièces suggérées par l'historique (heuristique)
- `XFSM23` — Géolocalisation temps réel + géofencing techniciens (opt-in)
- `XFSM24` — Check-in travailleur isolé avec escalade
- `XGED1` — Cérémonie de signature in-app sur document GED (lien public tokenisé, loi 53-05)
- `XGED2` — Circuit multi-signataires (séquentiel/parallèle) + relances + expiration + annulation
- `XGED3` — Zones de champs positionnées sur le PDF à signer (modèles de signature)
- `XGED4` — Certificat de complétion + classement automatique des documents signés
- `XGED5` — Scellement cryptographique des PDF signés + horodatage qualifié (gated)
- `XGED6` — Vérification périodique d'intégrité des archives légales + dossier de preuve (loi…
- `XGED7` — Lien public de DÉPÔT (upload-request)
- `XGED8` — Checklist de pièces requises par dossier + demandes de documents manquants avec…
- `XGED9` — Ingestion par email → GED (alias par cabinet/dossier)
- `XGED10` — Outils PDF : scission et fusion
- `XGED11` — Séparation automatique des lots scannés + reconnaissance code-barres/QR
- `XGED12` — Capture mobile photo → PDF multi-pages classé en GED
- `XGED13` — File de validation d'extraction OCR (scores de confiance + lignes de tableaux)
- `XGED14` — Opérations par lot (multi-sélection)
- `XGED15` — Chatter documentaire (notes, @mentions, activités planifiées)
- `XGED16` — Annotations et tampons sur l'image du document (couche séparée)
- `XGED17` — Comparaison de versions
- `XGED18` — Documents-liens (URL externes comme entrées GED)
- `XGED19` — Actions automatiques par dossier (règles à l'upload)
- `XGED20` — Routage conditionnel des approbations par métadonnées
- `XGED21` — ACL automatiques pilotées par métadonnées
- `XGED22` — Rapport de permissions effectives (« qui voit ce document et pourquoi »)
- `XGED23` — Workflow de disposition fin de rétention avec approbation + certificat de destruction
- `XGED24` — Outil de caviardage (redaction)
- `XGED26` — Analytique workflow & signature
- `XGED27` — Envoi en masse de demandes de signature
- `XGED30` — Co-édition Office (Collabora/OnlyOffice self-host, gated)
- `XKB1` — Boîte d'approbations centralisée
- `XKB2` — Types de demandes d'approbation configurables
- `XKB3` — Délégation d'approbation (suppléant)
- `XKB4` — To-do personnel (à-faire privés)
- `XKB5` — Annonces internes ciblées et programmées
- `XKB6` — Accusé de lecture obligatoire des annonces + rapport de conformité
- `XKB7` — Lecture obligatoire d'articles KB
- `XKB8` — Arborescence d'articles (pages imbriquées)
- `XKB9` — Sections Espace de travail / Privé / Partagé + ACL par utilisateur
- `XKB10` — Éditeur Markdown + pièces jointes + sommaire auto
- `XKB11` — Liens internes article↔article + rétroliens
- `XKB12` — Gabarits d'articles utilisateur
- `XKB13` — Commentaires sur articles KB
- `XKB14` — Vérification, péremption & verrou d'article
- `XKB15` — Favoris & récents KB
- `XKB16` — Statistiques KB & recherches infructueuses
- `XKB17` — Export/import & sauvegarde KB
- `XKB18` — Articles multilingues FR/AR
- `XKB19` — Partage web public d'article
- `XKB20` — Récupération RAG des articles KB, respectueuse des ACL
- `XKB21` — Dupliquer / déplacer un article
- `XKB22` — Parcours de lecture d'intégration
- `XKB23` — Assistant IA d'écriture & résumé dans l'éditeur KB
- `XKB24` — Fils de discussion dans le chat
- `XKB25` — Niveau de notification par conversation
- `XKB26` — Statut personnalisé & Ne pas déranger
- `XKB27` — Messages programmés, rappels & signets
- `XKB28` — Réponses enregistrées (snippets)
- `XKB29` — Formatage léger des messages
- `XKB30` — Sondages dans les canaux
- `XKB31` — Commandes / dans le composer
- `XKB32` — Rétention & export des conversations (loi 09-08)
- `XKB33` — WhatsApp entrant → fil de l'enregistrement
- `XKB34` — S'abonner aux enregistrements (followers)
- `XMFG1` — Consommation & production de stock à la clôture d'un ordre d'assemblage (backflush)
- `XMFG2` — Réservation & contrôle de disponibilité des composants sur l'ordre d'assemblage
- `XMFG3` — Assembler-à-la-commande : ordre d'assemblage depuis un devis/chantier + suggestion…
- `XMFG4` — Cycle de vie complet de l'ordre d'assemblage : dates, responsable, annulation, chatter
- `XMFG5` — Coût de revient du kit : roll-up + rapport de nomenclature + stock potentiel (INTERNE)
- `XMFG6` — Composants personnalisables par ordre (kit sur-mesure à la commande)
- `XMFG7` — Capture des numéros de série à l'assemblage + étiquette du composite
- `XMFG10` — Pièces retirées / récupérées sur ticket SAV (lignes Remove & Recycle)
- `XMFG11` — Gestion des rebuts de production + taux de perte par composant
- `XMFG12` — Ordre de démontage (unbuild) : composite → composants
- `XMFG13` — Contrôle qualité de fin d'assemblage (gate avant clôture)
- `XMFG14` — Gamme légère : étapes d'assemblage avec instructions et temps
- `XMFG15` — Analyse d'écarts par ordre + tableau de bord atelier (INTERNE)
- `XMFG16` — Assemblage sous-traité (façon) avec suivi des composants confiés
- `XMKT1` — Moteur d'exécution réel des séquences de relance
- `XMKT2` — Journal d'envoi par destinataire (trace de campagne)
- `XMKT3` — Désinscription un clic + liste de suppression globale
- `XMKT4` — Application du consentement marketing par canal + double opt-in + listes d'opposition…
- `XMKT5` — Listes de diffusion nommées + abonnements
- `XMKT6` — Segments dynamiques enregistrés et réutilisables
- `XMKT7` — Planification, throttling et fenêtres de silence d'envoi
- `XMKT8` — Variables de fusion dans les campagnes avec fallback
- `XMKT9` — Tracker de liens + auto-tag UTM
- `XMKT11` — Campagnes multilingues FR/AR/Darija avec variantes par contact
- `XMKT12` — Gestion des rebonds hard/soft
- `XMKT13` — Envoi test + aperçu fusionné + pré-check santé avant envoi
- `XMKT14` — Test A/B avec gagnant automatique
- `XMKT15` — Conformité SMS Maroc : comptage, coût, sender-ID, STOP
- `XMKT16` — Touches marketing sur le chatter du lead (vue 360°)
- `XMKT17` — Coût & ROI MAD par campagne
- `XMKT18` — Branches d'engagement dans les séquences
- `XMKT19` — Actions CRM dans les étapes de séquence
- `XMKT20` — Recettes de séquences prêtes à l'emploi (seed)
- `XMKT21` — Passage MQL automatique sur seuil de score
- `XMKT22` — Politique « sunset » d'engagement
- `XMKT23` — Approbation avant envoi de masse + journal d'audit
- `XMKT25` — Suivi d'approbation Meta des gabarits WhatsApp + variantes arabes
- `XMKT27` — Constructeur d'enquêtes avec logique conditionnelle + analytics
- `XMKT28` — Événements marketing légers (salons, portes ouvertes, webinaires)
- `XMKT29` — Ponts QR pour supports offline (flyers, bâches, véhicules)
- `XMKT30` — Calendrier marketing unifié
- `XMKT31` — Conteneur de campagne multi-canal
- `XMKT32` — Sync Meta Lead Ads → leads CRM (gated)
- `XMKT33` — Assistant d'authentification du domaine d'envoi (SPF/DKIM/DMARC)
- `XMKT37` — Livechat / assistant IA de qualification sur taqinor.ma — côté ERP uniquement
- `XPAI1` — Solde de tout compte (STC)
- `XPAI2` — Régularisation IR annuelle (12e bulletin / sortie)
- `XPAI3` — Mutuelle / prévoyance / assurance groupe
- `XPAI4` — 13e mois & gratifications + runs hors-cycle
- `XPAI5` — État des charges sociales + rapprochement paie↔GL
- `XPAI6` — Échéancier déclaratif paie
- `XPAI7` — Permissions paie dédiées `paie_voir`/`paie_gerer`
- `XPAI8` — Fichier de virement SIMT
- `XPAI9` — Modes de paiement & suivi des rejets de virement
- `XPAI10` — Télédéclaration CIMR (fichier préétabli)
- `XPAI11` — AFFEBDS + déclarations de mouvement CNSS
- `XPAI12` — BDS complémentaire/rectificative + format DAMANCOM strict
- `XPAI13` — Export XML EDI SIMPL-IR (état 9421)
- `XPAI14` — Indemnités journalières CNSS (maladie/maternité)
- `XPAI15` — Contrôle des écarts avant validation (M vs M-1)
- `XPAI16` — Simulateur de bulletin + calcul net→brut
- `XPAI17` — Ventilation analytique de la masse salariale + coût global employé
- `XPAI18` — Régimes stagiaire / ANAPEC / TAHFIZ
- `XPAI20` — Provisions gratifications & IFC
- `XPAI21` — Distribution des bulletins : notification + accusé de lecture
- `XPAI22` — Reprise des cumuls (go-live en cours d'année)
- `XPAI23` — Piste d'audit paie
- `XPAI24` — Structures de paie par catégorie (modèles de rubriques)
- `XPAI25` — Notes de frais remboursées sur le bulletin
- `XPAI26` — Registres d'inspection du travail
- `XPLT1` — Mode « mise à jour / upsert » + identifiant externe dans l'import générique
- `XPLT2` — Modèles de mapping d'import sauvegardés + rapport d'erreurs ligne à ligne + ré-import…
- `XPLT3` — Déclencheur temporel GÉNÉRIQUE (champ date ± N jours) dans les règles d'automatisation
- `XPLT4` — Webhook ENTRANT générique alimentant une règle d'automatisation
- `XPLT5` — API publique en ÉCRITURE (scopes write) + clés d'idempotence
- `XPLT6` — Alertes de seuil sur KPI AGRÉGÉS configurables
- `XPLT8` — Écrans d'administration workflow & jobs (câbler FG366/368/369)
- `XPLT9` — Filtre global de dashboard en cascade
- `XPLT10` — Partage de dashboard : lien public tokenisé lecture seule + mode TV + partage interne…
- `XPLT11` — Mesures calculées (formules) dans le pivot et l'explorateur BI
- `XPLT14` — Champs personnalisés : types relation & fichier + couverture des modules récents
- `XPLT15` — Conditions dynamiques sur champs (visible/requis/lecture seule) sans code
- `XPLT16` — Objets personnalisés no-code (mini-modèles créés par l'admin)
- `XPLT17` — Champs IA (valeur générée par LLM)
- `XPLT18` — Créer une règle d'automatisation en langage naturel (propose→confirm)
- `XPLT22` — Classeur léger embarqué avec données live (mini-spreadsheet BI)
- `XPLT23` — Registre des traitements CNDP + exécution DSR transverse (loi 09-08)
- `XPOS1` — Nouvelle app `apps/pos` : vente comptoir (backend)
- `XPOS2` — Écran caisse React (vente rapide)
- `XPOS3` — Ticket de caisse conforme (PDF 80 mm) + envoi WhatsApp
- `XPOS4` — Sessions de caisse POS (ouverture/clôture avec contrôle des espèces)
- `XPOS6` — Encaisser un devis/une facture existants au comptoir
- `XPOS7` — Retour client avec re-stockage (contre ticket/facture d'origine)
- `XPOS9` — Capture des n° de série à la vente → garantie SAV automatique
- `XPOS11` — Reporting ventes comptoir
- `XPOS14` — E-catalogue → « Demander un devis » (panier de demande)
- `XPOS15` — [DECISION fondateur] Click-and-collect (retrait en magasin)
- `XPOS18` — Pont matériel comptoir : impression ticket ESC/POS 80 mm + tiroir-caisse +…
- `XPRJ1` — Workflow d'approbation des feuilles de temps + verrouillage de période
- `XPRJ2` — Classification facturable + type d'activité sur les temps
- `XPRJ3` — Facturation en régie (T&M) depuis les temps approuvés
- `XPRJ4` — Situations de travaux (décomptes progressifs) — pratique BTP marocaine
- `XPRJ5` — Chrono start/stop sur tâche
- `XPRJ6` — Grille hebdomadaire de saisie des temps
- `XPRJ7` — Détection des temps manquants + rappels
- `XPRJ8` — Rapprochement pointages RH ↔ temps projet
- `XPRJ9` — Congés RH approuvés → indisponibilités planning
- `XPRJ10` — Assigné, priorité et étiquettes sur les tâches
- `XPRJ11` — Vue kanban + calendrier des tâches
- `XPRJ12` — Vue « Mes tâches » transverse
- `XPRJ13` — Tâches récurrentes
- `XPRJ14` — Checklist d'une tâche
- `XPRJ15` — Point d'avancement périodique (statut RAG)
- `XPRJ16` — Prévision fin de projet (ETC/EAC)
- `XPRJ17` — Burndown du projet
- `XPRJ18` — Rapport des temps multi-dimensions + export xlsx
- `XPRJ20` — Jours fériés marocains pré-remplis (depuis `core/calendar.py`)
- `XPRJ21` — Créer un projet depuis un devis accepté
- `XPRJ22` — Alertes automatiques de retard planning
- `XPRJ23` — Notifications client aux étapes du projet (via le moteur `apps.automation` existant)
- `XPRJ24` — Export/import du plan de tâches
- `XPRJ26` — Journal des modifications de tâches et jalons
- `XPRJ27` — Marché public : champs & pénalités de retard
- `XPRJ29` — Génération IA d'un plan de tâches depuis le devis (key-gated)
- `XPUR1` — Documents de conformité fournisseur + gate d'achat/paiement
- `XPUR2` — RAS-TVA sur paiements fournisseurs (LF 2024, en vigueur 01/07/2024)
- `XPUR3` — Multi-devises sur les achats (imports panneaux/onduleurs)
- `XPUR4` — Statuts fournisseur actif / bloqué commandes / bloqué paiements
- `XPUR5` — Fiche fournisseur enrichie : contacts multiples, catégorie/tags, devise/incoterm par…
- `XPUR6` — Conditions de paiement fournisseur & échéancier multi-tranches
- `XPUR7` — Dates de livraison prévues, accusé fournisseur & OTD réel
- `XPUR8` — Acomptes / avances fournisseur sur BCF
- `XPUR9` — Avoir fournisseur (note de crédit AP)
- `XPUR10` — Tolérances par société & file d'exceptions sur le rapprochement 3 voies + blocage réel…
- `XPUR11` — Détection de doublons facture fournisseur & BCF
- `XPUR13` — Garde-fous prix sur la ligne BCF (accords + historique)
- `XPUR14` — PrixFournisseur enrichi : code article fournisseur, paliers de quantité, validité…
- `XPUR16` — Lignes libres / services sur le BCF (achats hors stock)
- `XPUR17` — TVA par ligne sur la facture fournisseur (taux marocains)
- `XPUR18` — Révision de BCF tracée + ré-approbation
- `XPUR20` — Envoi de la RFQ aux fournisseurs consultés (email + WhatsApp)
- `XPUR21` — Réponse fournisseur en ligne à la RFQ (sans login)
- `XPUR22` — Portail fournisseur lecture seule + confirmation de date d'arrivée
- `XPUR23` — Destination de réception : dépôt/emplacement cible ou chantier (livraison directe)
- `XPUR24` — Tableau de bord achats (analyse des dépenses)
- `XPUR25` — Fiche fournisseur 360
- `XPUR26` — Réception e-facture fournisseur (préparation mandat DGI 2026, entrant)
- `XQHS1` — Workflow complet déclaration AT/MP loi 18-12
- `XQHS2` — Disposition des non-conformités + dérogation à durée limitée
- `XQHS3` — Contrôle qualité à la réception fournisseur + quarantaine
- `XQHS4` — Catalogue de codes de défauts + Pareto qualité
- `XQHS5` — Campagne de rappel / containment par produit-lot-série
- `XQHS6` — SCAR — demande d'action corrective fournisseur
- `XQHS7` — Analyse structurée 5-Pourquoi / 8D sur NCR + export PDF interne
- `XQHS8` — Registre des exigences légales toutes thématiques + pack Maroc
- `XQHS9` — Registre des certifications (ISO / IMANOR NM) + audits de certification
- `XQHS10` — Programme d'audit interne annuel
- `XQHS11` — Mapping clauses ISO multi-référentiel + heatmap + readiness 14001/45001
- `XQHS12` — Revue de direction (ISO 9.3) + comité de sécurité et d'hygiène (Code du travail)
- `XQHS13` — Objectifs & cibles QHSE/ESG avec revues périodiques
- `XQHS14` — Registre des risques & opportunités SMQ (ISO 6.1) + contexte/parties intéressées…
- `XQHS15` — Diffusion & accusé de lecture des procédures qualité
- `XQHS16` — Signalement QR public sans compte (danger/incident chantier)
- `XQHS17` — Observations sécurité comportementales (BBS)
- `XQHS18` — Exercices d'urgence (drills) rattachés aux plans d'urgence
- `XQHS19` — Incidents environnementaux (déversement/rejet) + obligation de notification
- `XQHS20` — Registre des aspects & impacts environnementaux (ISO 14001 6.1.2)
- `XQHS21` — Relevés de consommation par site (élec/eau/carburant) alimentant le bilan carbone
- `XQHS22` — Coût de la non-qualité (CoQ) — interne uniquement
- `XQHS23` — Pont SAV ↔ NCR (boucle défaillances terrain/garantie)
- `XQHS24` — Gestion du changement (MOC léger)
- `XQHS25` — Assistance IA QHSE (classification + brouillon d'analyse) — key-gated
- `XQHS26` — Veille réglementaire QHSE Maroc (revue périodique assistée)
- `XQHS27` — Documents terrain QHSE imprimables bilingues FR/AR
- `XRH1` — Période d'essai (suivi + alerte)
- `XRH2` — Types d'absence légaux Maroc pré-configurés (seed)
- `XRH3` — Congés demi-journée + justificatif maladie
- `XRH4` — Checklist d'intégration (onboarding) du nouvel embauché
- `XRH5` — Déclaration d'entrée CNSS/AMO (suivi de conformité à l'embauche)
- `XRH6` — Historique d'emploi (timeline auditée du dossier)
- `XRH8` — Horaires de travail par gabarit (44 h, Ramadan, saisonnier)
- `XRH9` — Guichet de demandes RH self-service (les attestations PDF existent déjà — PAIE34)
- `XRH10` — Kiosque de pointage partagé (PIN/QR, tablette dépôt)
- `XRH11` — Audit immuable des corrections de pointage
- `XRH12` — Géofence de pointage chantier (optionnelle)
- `XRH13` — Import de pointages externes (pointeuse biométrique, CSV)
- `XRH14` — Fermetures collectives / congés imposés
- `XRH15` — Compétences requises par poste + analyse d'écart
- `XRH16` — Grille salariale par poste (bandes min/max, compa-ratio)
- `XRH17` — Entretiens de recrutement (planification + grille d'évaluation)
- `XRH18` — Chatter candidature + détection de doublons
- `XRH19` — Emails candidats automatiques par étape
- `XRH20` — Promesse d'embauche / lettre d'offre PDF + e-sign interne
- `XRH21` — Vivier de candidats (talent pool)
- `XRH22` — Analytics recrutement (délai d'embauche, entonnoir, sources)
- `XRH23` — Parsing de CV par OCR (key-gated)
- `XRH24` — Rétention & anonymisation des candidats (loi 09-08)
- `XRH25` — Entretien de sortie (exit interview) + motifs de turnover
- `XRH26` — Auto-évaluation + issues d'évaluation structurées
- `XRH27` — Hiérarchie de départements
- `XRH28` — Annuaire interne des employés (trombinoscope)
- `XRH29` — Ayants droit & avantages sociaux
- `XRH31` — Score de risque d'attrition (scorer pur, sans IA externe)
- `XRH32` — Baromètre interne eNPS anonyme (pulse)
- `XRH33` — Publication publique des offres d'emploi (careers, flag-gated OFF)
- `XRH34` — eLearning léger : quiz d'évaluation + parcours de certification (re-certification sur…
- `XSAL1` — Listes de prix clients (détail / revendeur / export)
- `XSAL2` — Règles de prix + paliers de quantité (remises volume automatiques)
- `XSAL3` — Câbler la tarification dans le générateur + endpoint prix-applicable
- `XSAL6` — Plans de commission par commercial (au-delà du mode société unique)
- `XSAL7` — Montant estimé + date de clôture prévue sur le lead (pipeline pondéré pré-devis)
- `XSAL8` — Scan de carte de visite → lead (OCR, clé existante)
- `XSAL9` — Hiérarchie de comptes (société mère / filiales) avec consolidation
- `XSAL11` — Affectation round-robin équilibrée des leads entrants
- `XSAL12` — Livraisons partielles et reliquats sur le bon de commande client
- `XSAL13` — Documents client en arabe (facture + devis one-page) selon `Client.langue_document`
- `XSAL16` — Analytics d'engagement par section de la proposition web
- `XSAL17` — Placeholder `{lien_rdv}` : le lien de réservation de visite dans les messages sortants
- `XSAV3` — Devis de réparation hors garantie depuis le ticket
- `XSAV4` — Notifications client aux transitions du ticket (reçu / planifié / résolu)
- `XSAV5` — SLA en jours ouvrés + état de pause « en attente client »
- `XSAV6` — Pré-alerte SLA + escalade à la violation
- `XSAV7` — SLA différencié par contrat / segment client
- `XSAV8` — Rapport de conformité SLA + KPI SAV avancés
- `XSAV9` — Affectation automatique des tickets (round-robin / équilibrage de charge)
- `XSAV10` — Enquête de satisfaction (CSAT) à la clôture du ticket
- `XSAV11` — Suivi des réouvertures + taux de réouverture
- `XSAV12` — Fusion de tickets doublons
- `XSAV13` — Garantie légale de conformité (loi 31-08)
- `XSAV14` — Taxonomie panne / cause / remède + Pareto des défaillances
- `XSAV15` — MTBF / MTTR / coût cumulé par équipement et par modèle
- `XSAV16` — Journal d'immobilisation (downtime) + disponibilité %
- `XSAV17` — Relevés compteur (heures / kWh) + entretien conditionnel
- `XSAV18` — Rentabilité par contrat de maintenance
- `XSAV19` — Page publique « Signaler un problème » via QR équipement
- `XSAV21` — Suggestion de tickets similaires résolus
- `XSAV23` — Réponses types (macros) SAV
- `XSAV24` — Auto-clôture des tickets résolus dormants
- `XSAV25` — Catalogue de pièces compatibles par modèle d'équipement
- `XSAV26` — WhatsApp entrant → ticket SAV (gated BSP)
- `XSAV27` — Prêt / échange anticipé d'équipement (loaner)
- `XSAV28` — Triage IA du ticket + brouillon de réponse (clé-gated, propose→confirme)
- `XSTK1` — UI Magasin : réception → rangement → picking → colisage
- `XSTK2` — UI Logistique : livraisons, transporteurs, tournée, POD, comptages cycliques, demandes…
- `XSTK3` — Code-barres fabricant (EAN/UPC) sur Produit + résolution au scan
- `XSTK4` — Parsing GS1-128 / DataMatrix (GTIN + lot + péremption + série en un scan)
- `XSTK5` — Opérations pilotées par scan : réception, picking, comptage
- `XSTK6` — Registre de lots en entrepôt + sortie FEFO + blocage du périmé
- `XSTK7` — Rapport de traçabilité bout-en-bout (rappel fabricant)
- `XSTK8` — Contrôle du stock négatif (garde configurable)
- `XSTK10` — Flux de casse / mise au rebut du stock
- `XSTK13` — Valorisation à date (as-of) + inventaire annuel légal archivé
- `XSTK14` — Revalorisation manuelle du stock (document tracé)
- `XSTK15` — Unités de mesure & conditionnements (acheter en touret/carton, stocker en unité/mètre)
- `XSTK16` — Découpe / reconditionnement (touret → coupes) avec coût et lot préservés
- `XSTK17` — Profils saisonniers de seuils min/max (saison pompage)
- `XSTK19` — Code SH (HS) + pays d'origine sur Produit → dossier d'import
- `XSTK22` — Suivi de livraison côté client : numéro de suivi + notification + section portail
- `XSTK23` — API publique stock + webhooks inventaire
- `YCASH4` — Feedback recouvrement → front du funnel : aucun câblage entre le retard de paiement et…
- `YDATA9` — Test-garde : les `DecimalField` sérialisent en string via DRF (précision préservée à la…
- `YDOCF1` — Ticket SAV : machine d'états GARDÉE (transitions illégales → 400)
- `YDOCF2` — Devis accepté : gel du contenu commercial (verrou d'édition)
- `YDOCF3` — Variantes de devis : effondrement des sœurs à l'acceptation
- `YDOCF4` — Événement métier `facture_paid` sur le bus core à l'encaissement complet
- `YDOCF5` — Contrat signé/actif : émission d'un événement métier sur le bus core
- `YDOCF7` — BonCommande confirmé : réservation de stock (au lieu du seul décrément à la livraison)
- `YEVNT2` — L'expiration automatique des devis (QJ5) ne pose aucun événement sur le bus
- `YEVNT3` — `EventType.FACTURE_OVERDUE` est un type de notification sans producteur — les factures…
- `YEVNT4` — `EventType.SAV_TICKET_OPENED` est déclaré mais jamais émis
- `YEVNT5` — Aucune trace d'audit sur les envois de notification (in-app / email / WhatsApp) —…
- `YEVNT6` — Les changements de statut de Facture (émise→payée/annulée) et de BonCommande n'émettent…
- `YEVNT7` — Aucun test de couverture du bus/notifications — les orphelins (YEVNT1/3/4) ont pu…
- `YEVNT8` — Les demandes d'approbation ne notifient personne et n'atterrissent nulle part — les…
- `YEVNT9` — Aucune relance/escalade des approbations en attente — une approbation oubliée bloque…
- `YEVNT10` — `expire_stale_devis`, les sweeps et les jobs beat n'écrivent aucune ligne d'audit…
- `YEVNT11` — Aucune garantie de séparation demandeur ≠ approbateur (SOD) côté serveur
- `YEVNT12` — L'escalade d'incident critique QHSE n'alerte que le chatter — ni notification ni audit
- `YHARD2` — Garde-fou IA : journal d'audit + rollback des actions proposées/exécutées par l'agent
- `YHARD3` — Reconstruction d'un enregistrement « à une date » (as-of générique) + capture de diff…
- `YHARD4` — Traduction du CONTENU saisi (i18n des données maîtres, ≠ i18n de l'UI)
- `YHARD5` — Gouvernance des secrets & suivi de rotation (registre + politique, sans vendor lock)
- `YHARD6` — Observabilité : exposition de métriques (Prometheus) + santé Celery/beat
- `YHARD7` — Budget de performance & garde Web Vitals en CI pour le SPA ERP
- `YHARD8` — Accessibilité fonctionnelle du SPA ERP + garde axe élargie en CI
- `YHARD10` — Environnement de staging : commande d'export anonymisé du parc de données (clone UAT)
- `YHARD11` — Déploiement sans coupure : convention expand/contract + healthcheck & rollback dans…
- `YHARD12` — Harnais d'évaluation des sorties IA (eval harness NL→SQL & agent)
- `YHIRE1` — Câbler réellement l'import RH → paie des éléments variables (le stub importe 0)
- `YHIRE2` — Orchestration de sortie : un événement `employe_sorti` qui déclenche tout (checklist…
- `YHIRE3` — Contrôle de complétude pré-paie (l'analogue « pas de CNSS = pas de paie »)
- `YHIRE5` — Réconcilier les DEUX systèmes d'avances (rh.AvanceSalaire ↔ paie.AvanceSalarie)
- `YHIRE6` — Une seule source du salaire : Remuneration (rh, datée) ↔ ProfilPaie.salaire_base (paie…
- `YHIRE7` — Propager les effets des sanctions (mise à pied → retenue paie ; licenciement → sortie)
- `YHIRE8` — Inscrire les alertes RH au planificateur (aujourd'hui 100 % manuelles)
- `YHIRE9` — Faire consommer la garde d'habilitation par les affectations d'intervention
- `YHIRE10` — Un accident du travail avec arrêt doit produire l'absence correspondante
- `YHIRE11` — Relier le conducteur flotte au dossier employé (3e master de personne + 2 registres de…
- `YHIRE12` — Portail employé : UNE surface bulletins (dépôt FG196 + coffre-fort PAIE35 fusionnés)
- `YHIRE13` — Dotation EPI → décrément de stock (optionnel, par produit lié)
- `YHIRE14` — Approbation de réquisition avant ouverture au recrutement
- `YLEAD8` — Rattacher l'inbound WhatsApp à un lead OUVERT existant au lieu de toujours créer un…
- `YLEAD10` — Fast-lane comportemental : avancer le funnel à FOLLOW_UP à l'ouverture du devis
- `YLEAD11` — Réactivation d'un lead perdu/COLD sur nouvelle touche entrante (site/WhatsApp)
- `YLEAD14` — Recyclage des leads non travaillés (SLA speed-to-lead → escalade automatique)
- `YLEDG1` — Émettre les événements documentaires ventes et abonner compta (câbler COMPTA12-14)
- `YLEDG2` — Émettre les événements documentaires achats (stock) et abonner compta (câbler…
- `YLEDG3` — Appliquer le verrou de période compta aux documents ventes et achats
- `YLEDG4` — Extourne automatique quand un document déjà comptabilisé est annulé
- `YLEDG5` — Chemin d'exception « paiement rejeté » (chèque impayé / virement rejeté) côté ventes
- `YLEDG6` — Auto-lettrage à l'encaissement + service de délettrage
- `YLEDG7` — Écriture de règlement des salaires (OV) et des organismes sociaux — solder…
- `YLEDG8` — Relier le PaymentRun compta (FG133) aux factures fournisseurs stock : proposition des…
- `YLEDG9` — Encaissements espèces → mouvement de caisse (COMPTA24) + timbre fiscal automatique…
- `YLEDG10` — Chèques et effets clients reçus → portefeuille d'effets (comptes d'étapes)
- `YLEDG11` — Factures d'acompte comptabilisées en avances clients (4421), jamais en produits
- `YLEDG12` — Abonner ventes à `payment_captured` (core FG370) — transaction carte capturée →…
- `YLEDG13` — États de rapprochement auxiliaires ↔ GL (tie-out AR/AP) — le contrôle de non-divergence…
- `YOPSB1` — Sauvegarde Postgres réelle, planifiée et hors-serveur (pg_dump → MinIO)
- `YOPSB2` — Drill de restauration testé + vérification d'intégrité des dumps
- `YOPSB3` — Rétention + purge automatique des sauvegardes (7j/4sem/12mois)
- `YOPSB4` — Garde CI « migrations sûres » (bloque DDL dangereuse avant merge)
- `YOPSB5` — `makemigrations --check` dans la CI (anti-dérive modèle↔migration)
- `YOPSB6` — Mixin d'index concurrent + `lock_timeout` pour les migrations d'index
- `YOPSB7` — `CONN_MAX_AGE` + garde de connexions bornées (pooling)
- `YOPSB8` — Réglages Celery de production durcis (time limits + reject_on_worker_lost)
- `YOPSB9` — Isolation des queues Celery par classe de travail
- `YOPSB10` — Registre de rétention partagé + sweep beat unifié (généralise FG26/XRH24/XKB32)
- `YOPSB12` — Détecteur N+1 en développement (nplusone) + zone sans requête sur les serializers…
- `YOPSB13` — Garde N+1 en CI via mixin `AssertQueryBudgetMixin`
- `YOPSB14` — Endpoint santé readiness distinct + garde upload cohérente (Django ↔ nginx)
- `YPROC3` — GR/IR automatique : provision à la confirmation de réception, lettrage à la facturation
- `YPROC4` — L'approbation par palier (FG312) doit BLOQUER l'envoi du BCF — elle est décorative…
- `YPROC5` — Demande d'achat approuvée → génération du BCF (conversion manquante, traçabilité…
- `YPROC6` — Adjudication RFQ : l'offre retenue doit produire le BCF et mémoriser le prix gagnant
- `YPROC7` — Annulation d'un BCF : cascade sur les réceptions ouvertes + garde à la confirmation
- `YPROC8` — Le retour fournisseur doit rouvrir le « reçu » de la ligne BCF (le 3-voies et le statut…
- `YPROC9` — Réappro net du forecast : déduire les BCF ouverts + réservations et fusionner au lieu…
- `YPROC10` — BCF « besoin chantier » : lien structurel au chantier d'origine + réservation…
- `YRBAC1` — Test-inventaire : tout endpoint DRF a une permission explicite ≠ défaut fourre-tout
- `YRBAC2` — Matrice endpoint×rôle canonique + test qui l'assert
- `YRBAC4` — Convention documentée + garde CI : toute `@action` custom déclare sa propre permission
- `YRBAC5` — Mixin partagé `WriteScopedPermissionMixin` : lecture ≠ écriture par méthode HTTP
- `YRBAC6` — Balayage anti-fuite champ-sensible : test pan-sérialiseur/export/PDF
- `YRBAC7` — Registre de champs sensibles + mixin sérialiseur de masquage réutilisable
- `YRBAC8` — Garde write-side anti-mass-assignment : les champs de gouvernance ne se posent jamais…
- `YRBAC9` — Garantir throttle + expiry sur TOUT endpoint public tokenisé (garde CI)
- `YSERV1` — Gate « acompte encaissé » avant planification du chantier (override responsable…
- `YSERV2` — Handoff ticket SAV ↔ intervention : création en un clic + avancée auto à la clôture +…
- `YSERV3` — Planificateur monitoring : synchro fournisseur + évaluation sous-performance (services…
- `YSERV5` — Génération automatique planifiée des visites préventives dues (beat, opt-in)
- `YSERV6` — Annulation de chantier : solder les interventions ouvertes (chemin de réversion…
- `YSERV7` — Jalons atteints & réception → rappel de facturation d'échéancier (le milestone billing…
- `YSERV9` — Chemin d'exception : annulation client après signature (réversion partielle seulement)
- `YSERV12` — Canal de résolution du ticket (à distance / sur site) + taux de résolution à distance
- `YSERV13` — Contrôles d'intégrité inter-documents planifiés (rapport des états orphelins)
- `YSTCK1` — FG324 comptage cyclique : la validation ne poste JAMAIS l'écart en AJUSTEMENT (document…
- `YSTCK2` — FG325 demande de transfert : `executer` ne déplace jamais le stock (workflow déconnecté…
- `YSTCK3` — Les SORTIE ne décrémentent JAMAIS `StockEmplacement` : grand livre aveugle à…
- `YSTCK4` — Aucun RETOUR chantier : la consommation est à sens unique (matériel non posé perdu du…
- `YSTCK5` — FG329 livraison : `expedier`/`livrer` ne bougent aucun stock (planification déconnectée…
- `YSTCK6` — Annulation d'une réception CONFIRMÉE : bloquée en dur, aucune contre-passation…
- `YSTCK7` — Réception BCF : la série capturée (`numeros_serie`/`SerieEntrepot`) n'alimente pas…
- `YSTCK8` — FG327 matériel consigné : pas d'exclusion explicite de la valorisation (risque de…
- `YSUBS1` — Beat quotidien : facturation récurrente auto (échéanciers contrats + maintenance)
- `YSUBS2` — Beat quotidien : reconduction tacite + diffusion des alertes contrat
- `YSUBS3` — `AbonnementMonitoring` ne génère AUCUNE facture : brancher la facturation récurrente
- `YSUBS4` — Transitions `AbonnementMonitoring` sans effet de bord : machine d'états gardée +…
- `YSUBS5` — Résiliation de contrat sans propagation aval (de-provisioning)
- `YSUBS6` — Aucune écriture comptable ni revenu différé sur une facture récurrente
- `YSUBS7` — Indexation de prix qui ne re-tarife pas l'échéancier de facturation
- `YSUBS8` — Activation à la signature ne génère pas le plan de facturation (billing schedule dérivé…
- `YSUBS9` — Période de service (du/au) absente des factures récurrentes
- `YTEST1` — Base de test partagée + factories cohérentes (factory_boy)
- `YTEST2` — Mixin de base multi-tenant/auth pour APITestCase + convention documentée
- `YTEST9` — Mutation testing léger (mutmut) sur les modules à haut risque + score suivi
- `YTEST14` — Test de charge léger (k6) sur les endpoints critiques avec seuils p95/p99 + smoke CI
- `YTEST15` — Discipline de déterminisme : freezegun + seed Faker + garde anti-sleep/anti-real-now
- `YTEST16` — Registre d'invariants métier + garde « bug corrigé = test de régression » outillé
- `YTEST17` — Accélération du gate : réutilisation de la DB de test + parallélisme (documenté et…
- `ZACC1` — Rendu PDF imprimable des états de synthèse & légaux (bilan / CPC / balance / grand…
- `ZACC2` — Colonne comparative N-1 sur les états de synthèse STANDARD (bilan / CPC / balance /…
- `ZACC3` — Tableau de financement / des flux de trésorerie CGNC (méthode indirecte)
- `ZACC4` — Vue « Journal Items » : ledger ligne-à-ligne filtrable/exportable de toutes les lignes…
- `ZACC6` — Note de frais MULTI-LIGNES : regrouper N dépenses en UN rapport de frais soumis en une…
- `ZACC7` — Rapport d'analyse des frais (pivot par employé × catégorie × période)
- `ZACC8` — Attestation / reçu PDF de remboursement de note de frais pour l'employé
- `ZACC9` — Comptabilisation + garde de sur-paiement du règlement fournisseur (parité Register…
- `ZACC10` — Déclaration TVA : comparatif M-1 / N-1 + rendu PDF du bordereau
- `ZACC12` — Rapport des immobilisations (tableau des immos & amortissements pour la…
- `ZACC14` — Vérification du n° d'identifiant fiscal / ICE des tiers (miroir marocain du VIES)
- `ZACC16` — Export xlsx multi-onglets du dossier de clôture (liasse + états + balance âgée + immos)…
- `ZCTR1` — Plan de facturation récurrente réutilisable (RecurringPlan config)
- `ZCTR2` — Action planifiée : expiration/clôture automatique des contrats impayés (délai de…
- `ZCTR3` — Référentiel éditable des motifs de résiliation (close reasons) + branchement churn
- `ZCTR4` — Réglages de location : durée minimale, temps de sécurité (padding) & frais de retard…
- `ZCTR5` — Bons d'enlèvement et de restitution de location (imprimés PDF)
- `ZCTR6` — Devis/commande portant des lignes de location (Rental order via ventes)
- `ZCTR7` — Options de catégorie d'approbation : nombre minimum d'approbations + pièce jointe…
- `ZCTR8` — Action « demander un complément d'information » sur une approbation (request-info) +…
- `ZCTR9` — Filtre « Mes approbations » : priorité, catégorie, ancienneté + tri urgence
- `ZCTR10` — Référentiel des types de service/entretien flotte + regroupement dans les rapports de…
- `ZCTR11` — Enrichissement fiscal du catalogue de modèles véhicule (carte mobilité, valeur…
- `ZCTR12` — Canal comme liste de diffusion e-mail (poster/recevoir par e-mail)
- `ZFAC1` — Remise en brouillon d'une facture émise (Reset to Draft, opt-in période ouverte)
- `ZFAC4` — Note de débit (majoration d'une facture émise) — pendant de l'avoir
- `ZFAC5` — Mode « annuler & contre-passer » sur l'assistant d'avoir (reverse-and-cancel)
- `ZFAC6` — Encaissement groupé : un paiement couvrant plusieurs factures d'un même client (Group…
- `ZFAC7` — Numéro de chèque / banque tirée sur un paiement par chèque
- `ZFAC8` — Responsable de relance + mode manuel/automatique par client (Follow-up responsible &…
- `ZFAC9` — Vue kanban des factures par statut (pipeline visuel brouillon / émise / en retard /…
- `ZFAC10` — Analyse de facturation (rapport dédié CA facturé par période/client/statut)
- `ZFAC12` — Rappel de courtoisie pré-échéance côté DEVIS accepté non facturé (backlog à facturer)
- `ZFSM1` — Gabarit de fiche d'intervention configurable par type (worksheet template Odoo)
- `ZFSM2` — Lien public tokenisé du compte-rendu d'intervention signé (customer worksheet report…
- `ZFSM3` — Interventions récurrentes autonomes (recurring tasks Odoo)
- `ZFSM4` — Facturer une intervention hors contrat directement (T&M draft invoice Odoo)
- `ZFSM5` — Devis d'upsell créé sur place depuis l'intervention (field quotation Odoo)
- `ZFSM7` — Export xlsx de la liste des interventions (list export Odoo)
- `ZGED1` — Catalogue de rôles signataires réutilisables (couleur + auth
- `ZGED2` — Authentification extra du signataire par SMS/OTP email (key-gated, no-op sans…
- `ZGED3` — Tableau de bord des demandes de signature (kanban par statut + suivi de progression)
- `ZGED4` — Éditeur de types de champs de signature personnalisés
- `ZGED5` — Champ propriétaire/responsable + contact assigné sur le document (panneau…
- `ZGED6` — Centralisation des fichiers par module vers un dossier de destination configurable
- `ZGED7` — Favoris de dossiers/documents + accès rapide
- `ZGED8` — Recherches/filtres GED enregistrés et partageables
- `ZGED9` — Verrouillage/déverrouillage manuel d'un document (« en cours d'édition »)
- `ZGED10` — Image de couverture + emoji/icône sur l'article KB
- `ZGED11` — Propriétés d'article (champs personnalisés) + vues d'items…
- `ZGED12` — Presse-papiers Knowledge (blocs de texte insérables réutilisables)
- `ZGED13` — Section « Récents » de la GED (documents récemment consultés/déposés)
- `ZGED14` — Renouvellement/rappel d'échéance des demandes de signature en attente (relance…
- `ZGED15` — Numérotation de référence lisible des documents GED (par société + mois)
- `ZMFG1` — Équipes de maintenance (Configuration > Maintenance Teams)
- `ZMFG2` — Catégories d'équipement (Configuration > Equipment Categories) + regroupement/filtre du…
- `ZMFG3` — Vue calendrier des visites de maintenance / tickets planifiés
- `ZMFG4` — Tableau de bord maintenance découpé par équipe/stage (kanban Odoo)
- `ZMFG5` — Onglet « Instructions » structuré sur le ticket (comment réaliser l'intervention)
- `ZMFG6` — Feuilles de maintenance (worksheets) remplies par le technicien — gate réglage
- `ZMFG7` — Alias e-mail par catégorie d'équipement → création auto de demande
- `ZMFG8` — Typage opérationnel des pièces sur ticket : Ajout / Retrait / Recyclage (parité Repair…
- `ZMFG10` — Bon d'assemblage imprimable (worksheet atelier PDF)
- `ZMFG11` — Prochaine défaillance estimée + prochain entretien dû sur la fiche équipement (parité…
- `ZMFG12` — Motif de mise au rebut d'un équipement + statut « au rebut » dans le parc
- `ZMKT1` — Statuts de pipeline mailing (Brouillon / En file / Envoi / Envoyée) + vue Kanban
- `ZMKT2` — Colonnes de performance + Group By + favoris sur la liste des campagnes
- `ZMKT3` — Enregistrer une campagne comme modèle réutilisable (étoile)
- `ZMKT4` — Actions Renvoyer les échecs / Dupliquer / Annuler sur une campagne
- `ZMKT5` — Traces d'activité de séquence (planifié / traité / rejeté) + compteurs Succès/Rejeté…
- `ZMKT6` — Bouton intelligent Participants d'une séquence + désinscription manuelle
- `ZMKT7` — Recettes de séquence Odoo-style manquantes (double opt-in, tag hot contacts, prioriser…
- `ZMKT8` — Reporting SMS/campagnes multi-vue (Graph / Cohorte / Pivot) avec mesures…
- `ZMKT9` — Options de mise en page & anti-biais d'enquête (pagination, limite de temps, ordre…
- `ZMKT10` — Scoring d'enquête + mode certification + score requis
- `ZMKT11` — Mode d'accès, connexion requise et nombre de tentatives d'enquête + entrée de test
- `ZMKT12` — Partage d'enquête par lien / email / QR + descriptif d'accueil et message de fin
- `ZMKT13` — Tableau de bord résultats d'enquête + liste des participations
- `ZMKT14` — Types d'événements + modèles + étapes de pipeline (salons / portes ouvertes /…
- `ZMKT15` — Billets d'événement (types, prix MAD, quotas, fenêtre de vente)
- `ZMKT16` — Questions d'inscription par événement (capture de données à l'inscription)
- `ZMKT17` — Communications programmées d'événement (rappels avant / relance après)
- `ZMKT18` — Borne de check-in événement (scan QR / recherche par nom) + statuts présent/absent
- `ZMKT19` — Badge d'inscrit imprimable (PDF)
- `ZMKT20` — Reporting événement (participants & billetterie)
- `ZPAI1` — Rapport d'analyse de paie (pivot rubrique × mois × département)
- `ZPAI2` — Panneau d'avertissements pré-run (blocages de paie)
- `ZPAI3` — Rapport « Coût employeur » consolidé de la période
- `ZPAI4` — Bulletin d'annulation / reprise (refund payslip négatif)
- `ZPAI5` — Impression en lot des bulletins d'une période (PDF fusionné)
- `ZPAI6` — Cycle de vie explicite des saisies-arrêt (en cours / soldée / annulée + bulletins liés)
- `ZPAI7` — Éclatement d'une saisie-arrêt multi-employés en fiches individuelles
- `ZPAI8` — Règles d'arrondi des jours/heures par type d'absence
- `ZPAI9` — Catalogue de types d'entrées ponctuelles (Other Input Types)
- `ZPAI10` — Assistant « Ajouter des bulletins existants à une période »
- `ZPAI11` — Duplication des rubriques récurrentes vers une nouvelle période / report auto
- `ZPAI12` — Action planifiée : alerte de clôture de paie en retard
- `ZPRJ1` — Réglages société : arrondi & unité d'encodage des temps
- `ZPRJ2` — Plan de ressources : cycle brouillon → publié + notification
- `ZPRJ3` — Copier le plan de ressources de la semaine précédente
- `ZPRJ4` — Auto-affectation : appliquer les propositions de nivellement
- `ZPRJ5` — Heures attendues & heures supplémentaires dans la synthèse temps
- `ZPRJ6` — Classement de saisie des temps (leaderboard interne)
- `ZPRJ7` — Enquête de satisfaction client par projet (CSAT)
- `ZPRJ8` — Matrice des risques imprimable (heatmap P × I)
- `ZPRJ9` — PDF « Point d'avancement projet » (project status report)
- `ZPRJ10` — Politique de facturation par projet (forfait / jalons / régie)
- `ZPRJ11` — Conversion d'une tâche de projet en ticket SAV
- `ZPRJ12` — Création de tâches par e-mail entrant (alias projet)
- `ZPUR1` — Politique de facturation par produit/fournisseur (à la commande vs à la réception)
- `ZPUR3` — Modèle de BCF réutilisable (purchase template) pour commandes récurrentes
- `ZPUR4` — Duplication d'un bon de commande fournisseur
- `ZPUR6` — Regroupement de plusieurs demandes/besoins en un seul BCF par fournisseur (merge RFQ)
- `ZPUR7` — Brouillon de relance programmé + compteur pour les BCF en retard
- `ZPUR8` — Champs « Other Information » Odoo au niveau du BCF : acheteur, référence fournisseur…
- `ZPUR9` — Rapport imprimable « analyse d'achats » exportable PDF (au-delà du dashboard XPUR24)
- `ZPUR10` — Section « Bons de commande envoyés » (engagements) sur la fiche produit + réservation…
- `ZPUR11` — Motif d'annulation obligatoire + réouverture d'un BCF annulé
- `ZRH1` — Câbler le décompte des congés sur les jours fériés configurés (fériés mobiles Aïd…
- `ZRH2` — Action planifiée d'acquisition mensuelle + report janvier des congés (cron Odoo «…
- `ZRH3` — Rapport congés par type et par employé (Odoo « Time Off Reporting by Type / by Employee…
- `ZRH4` — Jours de blocage congés (« Mandatory / Stress Days » Odoo)
- `ZRH5` — Clôture automatique des pointages oubliés (« Automatic check-out » Odoo)
- `ZRH6` — Détection des absences non justifiées (« Absence management » Odoo)
- `ZRH7` — Gabarits de questions d'évaluation réutilisables (« Appraisal templates » Odoo)
- `ZRH8` — Plans d'appréciation automatiques (« Appraisal plans » Odoo — création après N mois…
- `ZRH9` — Feedback 360° (avis multi-sources sur un entretien)
- `ZRH10` — Rapport d'évolution des compétences (« Skills Evolution » Odoo)
- `ZRH11` — Rapport de rétention / turnover annuel détaillé (« Employee retention report » Odoo)
- `ZRH12` — Certificat de travail légal (art
- `ZRH13` — Demande d'allocation de congés self-service (« My Allocations / request allocation »…
- `ZRH14` — Badges de reconnaissance interne (« Employee badges » Odoo — gamification)
- `ZRH15` — Types de lignes de CV / parcours (« Resume Line Types » + timeline…
- `ZRH16` — Localisation de télétravail par jour de semaine (« Remote Work » Odoo)
- `ZRH17` — Recherche transverse d'employés par compétence et niveau (« Skills search/filter »…
- `ZRH18` — Rapport de présence & heures supp
- `ZSAL1` — Enchaînement d'activités (suggérer/déclencher la suivante) sur les types d'activité
- `ZSAL2` — Plans d'activité (séquences de tâches pré-définies lançables en un clic)
- `ZSAL3` — Équipes commerciales + tableau de bord d'équipe (« Mes équipes »)
- `ZSAL4` — Assistant de conversion lead→client explicite (choix : nouveau client / lier existant /…
- `ZSAL5` — Reçu/accusé d'envoi de devis : gabarit d'email de devis éditable + trace d'envoi dans…
- `ZSAL6` — Rapport d'attribution des leads par source + par commercial (lead distribution report)
- `ZSAL8` — PDF imprimable du bon de commande CLIENT (`ventes.BonCommande`)
- `ZSAV2` — Types de ticket configurables (au-delà de correctif/préventif)
- `ZSAV3` — Activités planifiées à échéance sur le ticket (rappeler / rappel visite)
- `ZSAV6` — Vue « activité » : file d'action suivante par ticket
- `ZSAV7` — Analyse croisée des tickets (pivot / graphique)
- `ZSAV8` — Convertir un ticket en opportunité CRM
- `ZSAV9` — Suiveurs de ticket (followers) + « suivre tous les tickets »
- `ZSAV10` — Endpoint d'actions groupées atomique + opérations priorité/annulation
- `ZSTK1` — Action planifiée : recompute réappro + alertes de rupture (cron)
- `ZSTK2` — Action planifiée : alertes de péremption des lots (cron)
- `ZSTK3` — Rapport prévisionnel par produit (disponible + entrant + sortant → projeté)
- `ZSTK4` — Bon de livraison imprimable depuis une Livraison planifiée (packing/delivery slip)
- `ZSTK6` — Étiquette lot/série scannable + intégration au registre entrepôt
- `ZSTK7` — Rapport « historique des mouvements » groupable/croisé (moves history)
- `ZSTK8` — Retour / transfert inverse depuis une Livraison validée (returns)
- `ZSTK9` — Capacité & compatibilité d'emplacement + règle de rangement configurable (storage…
- `ZSTK10` — Regroupement de prélèvements en lot (batch transfer) pour une passe magasin
- `ZSTK11` — Réglage société : méthode de réservation du stock (à la confirmation / manuelle)
- `ZSTK12` — Nomenclature de code-barres configurable (Default/GS1) par société
- `AG1` — Agent action-registry framework + catalogue endpoint
- `AG2` — Registry-driven agent tools + propose→confirm protocol (FastAPI)
- `AG3` — Confirmation + result cards in the assistant chat
- `AG4` — Quote (devis) agent actions
- `AG5` — Invoicing & payment agent actions
- `AG6` — CRM lead agent actions
- `AG7` — Stock agent actions
- `AG8` — SAV agent actions (migrate the existing ticket tool)
- `AG9` — Installations agent actions (migrate the chantier/visite tools)
- `AG10` — Voice transcription endpoint (Groq Whisper, reuses GROQ_API_KEY)
- `AG11` — Voice input + spoken answers in the assistant chat
- `AG12` — Hands-free conversation mode (continuous listen↔speak loop)
- `CH1` — Configurable installation stage/gate model seeded with the international PV lifecycle
- `CH2` — Enforce the gates (blocking) instead of free status jumps
- `CH3` — Commissioning & testing gate per IEC 62446-1
- `CH4` — Handover-pack gate
- `CH5` — Director settings: configure installation stages/gates per company
- `CH6` — Best-in-class installation UX: a stage/gate timeline replacing the « weird » status
- `F120` — Palette de marque en OKLCH (sans régression visuelle)
- `F121` — Échelle typographique + chiffres tabulaires généralisés
- `F122` — Discipline d'élévation + anneau de focus de marque
- `F123` — Mode sombre = élévation par la clarté
- `G10` — Lead-source capture (G10 first half): (1) add nullable fields to the lead model —…
- `G124` — Tooltip thémable
- `G125` — Bouton « six états » + libellés d'icônes
- `G126` — États de chargement/erreur des sélecteurs
- `G127` — Champ de formulaire : indice + erreur ensemble
- `G128` — Tokeniser DatePicker / TimePicker / Calendar
- `H129` — Passe visuelle « tableau premium »
- `H130` — Épinglage de colonnes
- `H131` — Affordances de ligne
- `H132` — Barre d'actions groupées flottante
- `H133` — Performance perçue des tableaux
- `I134` — Palette de commandes ⌘K de premier plan (sans nouvelle dépendance)
- `I135` — Sidebar « calme »
- `I136` — Polissage de l'en-tête
- `I137` — Fil d'Ariane accessible + tronqué
- `I138` — Culture des raccourcis clavier (déjà présent)
- `J139` — CRM Clients : refonte
- `J140` — CRM Leads : tokens de couleur + vues + STAGES
- `J141` — Ventes Devis : polissage liste/détail
- `J142` — Stock : refonte
- `J143` — Installations (chantiers) : refonte
- `J144` — SAV : refonte
- `J145` — Admin Utilisateurs → DataTable
- `J146` — Reporting/Journal : tableaux HTML hérités → DataTable
- `K147` — Kit de primitives graphiques (recharts, marque)
- `K148` — Dashboard : refonte avec le kit
- `K149` — Formatage des nombres (reporting/dashboard)
- `L150` — Adoption des tokens de mouvement
- `L151` — UI optimiste + statut d'enregistrement automatique
- `L152` — Helper confirmation + toast sur mutation
- `L153` — Discipline des états de chargement
- `M154` — Repli tableau → cartes sur mobile
- `M155` — Passe tactile + zones sûres
- `M156` — Polissage de la nav basse
- `M157` — Polissage PWA iOS
- `M158` — Sheet sur mobile pour créer/éditer
- `MB1` — Fix the app-shell overlap: reserve header + bottom-nav space (the #1 cause)
- `MB2` — Kill horizontal overflow (« big pages »)
- `MB3` — Adopt the z-index token scale everywhere (stop the stacking collisions)
- `MB4` — Migrate the remaining fixed-width modals to `ResponsiveDialog` (Dialog↔Sheet)
- `MB5` — Per-screen responsive sweep for the un-adapted (legacy) pages
- `MB6` — Mobile visual/e2e regression gate
- `N159` — Focus jamais masqué + anneaux visibles (WCAG 2.4.11)
- `N160` — Accessibilité du DataTable
- `N161` — Accessibilité des graphiques
- `N162` — Alternative au glisser + taille de cible (2.5.7 / 2.5.8)
- `N163` — Mouvement réduit correct + tests axe
- `O164` — Virtualiser les grandes listes
- `O165` — Découpage des routes + chargement différé
- `O166` — Largeurs de colonnes mémoïsées (60 fps)
- `P167` — Unifier sur UN seul tableau
- `P168` — Cohérence des icônes
- `P169` — Supprimer les `style={}` inline
- `P170` — Guide de style vivant (/ui)
- `P171` — Migrer le moteur `DataTable` vers `@tanstack/react-table` (déjà installé) derrière…
- `Q1` — `Devis.roof_layout` storage + endpoints
- `Q2` — Client roof-POINT capture on the Lead (pin, not drawing)
- `Q3` — `build_devis_from_layout()` service (server-side)
- `Q4` — Roof-render image storage
- `Q5` — Feed roof render + layout figures into the quote data (additive/guarded)
- `Q6` — Tokenized web-proposal data endpoint
- `Q7` — E-signature acceptance (reuse the existing stamp)
- `QC1` — Own-data company autocomplete + assisted verification (ship now, zero cost/risk)
- `QD1` — Fix the too-small company logo on the invoice/document PDFs
- `QD2` — Clean, consistent, professional document filenames
- `QF1` — Reverse-tranche bill↔kWh helper (`pricing.py`)
- `QF2` — Two-bills real-savings model (`pricing.py`/`builder.py`)
- `QF3` — « Comment nous calculons vos économies » method block + small worked example (PDF +…
- `QF4` — Capture the client's REAL bill + utility on the generator and wire it into savings
- `QF5` — On-screen savings use the SAME two-bills par-tranche method (screen == PDF) + reconcile…
- `QF6` — Respect the seller's stored avec/sans-batterie choice in the PDF (`builder.py`)
- `QF7` — Make the avec/sans choice reliable for every mode + preview matches the PDF
- `QF8` — Attach Smart Meter + Clé Wifi ONLY to a Huawei inverter (`solar.js`)
- `QF9` — Never emit Smart Meter / Clé Wifi on a non-Huawei quote in the PDF…
- `QG1` — Auto-open the PDF after « Générer » (stop the two-click flow)
- `QG2` — « Éditer » edits must appear in the regenerated PDF (kill the stale-PDF cache)
- `QG3` — Add a new client directly from the quote generator
- `QG4` — Restrict product creation everywhere to Directeur + Commercial responsable (backend)
- `QG5` — Hide product-create UI for unauthorized roles (frontend)
- `QG6` — Add a new product directly from the quote generator (role-gated)
- `QG7` — Print the quote CREATOR's name + phone (not always the founder's)
- `QG8` — « Envoyer » on a devis = the leads WhatsApp flow (not just a status flip)
- `QG9` — Configurable variante percentage (default 20 %), company-scoped (backend)
- `QG10` — Make « Variante » actually show the 3 variantes + a set-% dialog (frontend)
- `QG11` — Reusable read-only 3D roof viewer embedded in the quote (frontend)
- `QG12` — Open the 3D viewer as a separate window (frontend)
- `QJ1` — Proposal open-tracking
- `QJ2` — Instant seller notification
- `QJ3` — Scheduler infra (Celery beat)
- `QJ4` — Automated devis follow-up cadence (relance)
- `QJ5` — Auto quote-expiry + funnel hygiene
- `QJ6` — Rule-based lead scoring + hot-list sort
- `QJ7` — Auto-advance NEW→CONTACTED
- `QJ8` — Webhook dedupe beyond 60 s + secondary key
- `QJ9` — Conversion attribution + Meta CAPI wiring
- `QJ10` — Stronger e-sign legal trail (loi 53-05)
- `QJ11` — Bind the signature to the lead contact
- `QJ12` — Financing data in the quote
- `QJ13` — 82-21 self-consumption savings + tariff tables in the quote engine
- `QJ14` — Server-side proposal email send (SendGrid)
- `QJ15` — Quote variants / multi-option comparison
- `QJ16` — Reusable quote templates / presets
- `QJ17` — `from-layout` idempotency + pre-flight composition check
- `QJ18` — Commercial dashboard
- `QJ19` — Win/loss + per-source close-rate report
- `QJ20` — Self-booking site-visit scheduler
- `QJ21` — Richer layout payload fidelity
- `QJ22` — Signed-proposal artifact + prominent "signé" surfacing
- `QJ23` — [GATED: paid — WhatsApp Business API]
- `QJ24` — [GATED: paid — payment gateway]
- `QJ25` — [GATED: research — auto roof detection]
- `QJ26` — Expose the roof layout in the public proposal payload (the 3D unlock)
- `QJ27` — Client « être contacté » notifies the handler AND their superior
- `QJ28` — « Contacter mon supérieur » button on quote generation
- `QJ29` — Multi-property quote — data model + totals engine (one document)
- `QJ30` — Multi-property quote — sectioned PDF + proposal rendering (one document)
- `QJ31` — Multi-property quote — generator UI (one quote)
- `QK1` — Stop discarding captured lead data (webhook mapping + new Lead fields)
- `QK2` — Feed the new qualification signals into lead scoring (QJ6)
- `QK3` — Render the computed financing block (PDF) + make the web consume it
- `QK4` — Client-facing « Nos hypothèses » transparency line
- `QK5` — Fix the dead `taqinor.ma/avis` link in the quote PDF
- `QK6` — Bill/meter-photo OCR at capture → lead attachment
- `QP1` — Filter the product picker by slot type (only inverters for the inverter slots)
- `QP2` — Renaming a line's product is Directeur/Commercial-responsable-only, with « renommer ici…
- `QS1` — Fix the BCF « PDF (interne) » button
- `QS2` — Add a new product directly inside the bon de commande (role-gated)
- `QS3` — Backend: WhatsApp + email send actions for the BCF (real sending)
- `QS4` — Frontend: WhatsApp + Email send buttons on the BCF, greyed when contact absent
- `QW1` — Map every dropped capture field in the website-lead webhook
- `QW2` — Add Lead columns for the site fields with nowhere to land (reuse existing columns…
- `QW3` — First-class "call me" vs "WhatsApp only" on the Lead
- `QW4` — Actioned callback obligation, distinct from WhatsApp (FREE channels now; WhatsApp-API…
- `QW5` — [REVISED] Alias the EXISTING QJ27 proposal endpoints under the `ventes/` mount + fix…
- `QW6` — Speed-to-lead assurance: no orphaned, silent lead
- `QW9` — Validate the webhook replay/freshness header the site already sends
- `QW10` — Index-backed dedup + concurrent-POST guard
- `S1` — `apps/chat` app skeleton + core models
- `S2` — Attachment, reaction, mention & pin models
- `S3` — Serializers, viewsets, membership permissions & company scoping
- `S4` — Read-state & unread counts
- `S5` — Message search
- `S6` — Attachment & voice-memo upload
- `S7` — Reactions & pinned messages
- `S8` — Share an ERP record into a conversation
- `S9` — Notifications + per-conversation mute (reuse `notify()` + Web Push)
- `S10` — Self-hosted Whisper transcription endpoint (FastAPI)
- `S11` — Django voice-transcription pipeline
- `S12` — Chat API client + Redux slice + smart-polling hook
- `S13` — `/messages` route, nav entry, header chat icon + two-pane shell
- `S14` — Conversation list pane
- `S15` — Message thread pane
- `S16` — Composer: text, @mentions, attachments, edit/delete
- `S17` — Voice memos: record, play, transcript
- `S18` — Reactions & pinned UI
- `S19` — Share-a-record UI
- `S20` — New-DM / new-channel / manage-members modals
- `U1` — Lead modal: « Mettre à jour » keeps the window open + generate-devis stays inline
- `U2` — Regression: mouse-wheel scrolling broke across the ERP
- `U3` — Mobile: the top of the app overlaps (header stacks on itself / on content)
- `U4` — WhatsApp-send a devis flips it to « envoyé » (and advances the lead funnel)
- `U5` — Surface generated factures (and the bon-commande) in the Devis list/detail
- `U6` — Auto-create the chantier (installation) when a devis is accepted
- `U7` — Hide/badge superseded devis revisions in the list
- `U8` — Reflect the bon-commande state in the devis detail
- `U9` — Stock reservation on the direct generer-facture (échéancier) path
- `U10` — Reset the relance (dunning) escalation when a facture is fully paid
- `U11` — Lead-funnel sanity when a post-acceptance devis is later refused (DECISION)
- `U12` — Direct lead link for factures & bons-commande (efficient lead-document view)
- `U13` — Bug: uploading a user profile picture does not work
- `U14` — Bug: the new « Documents (GED) » menu does nothing usable
- `WR1` — [BUG] Fix the devis « Refuser » mis-wiring
- `WR2` — Wire the invisible ventes power-features
- `WR3` — Stock intelligence dashboard
- `WR4` — Procurement & supplier UI
- `WR5` — Stock operations + data export UI
- `WR6` — Monitoring O&M suite — fleet, analytics & warranty
- `WR7` — Monitoring O&M suite — client portal, environment & reports
- `WR8` — Reporting + AI-agent surfaces
- `WR9` — CRM compliance + sales-ops UI
- `WR10` — Installations scheduling & logistics UI
- `WR11` — SAV SLA + client-transparency UI
- `WR12` — Expose the backend-only settings flags in Paramètres

**Open — to build (178)**

- `DC34` — Sous-traitant : pas de master fournisseur parallèle
- `ENG1` — Scaffold `apps/adsengine`
- `ENG2` — Modèle `MetaConnection`
- `ENG3` — Modèle `GuardrailConfig`
- `ENG4` — `meta_client.py` — client Marketing API v25
- `ENG5` — Miroirs
- `ENG6` — Celery `adsengine.sync_insights_daily`
- `ENG7` — Modèle `EngineAction` — la colonne vertébrale propose→approuve→applique
- `ENG8` — Toggles de capacités par société
- `ENG9` — Moteur de garde-fous
- `ENG10` — Service coût-par-signature (l'héro-métrique)
- `ENG11` — `WeeklyBrief` modèle + générateur déterministe v1 (FR)
- `ENG12` — Endpoint santé du câblage
- `ENG13` — Alertes WhatsApp-first
- `ENG14` — `seed_adsengine` idempotent
- `ENG15` — Modèle `CreativeAsset`
- `ENG16` — `CreativePolicy` par société
- `ENG17` — `creative_factory.py` — adaptateurs key-gated
- `ENG18` — Tâche « variantes »
- `ENG19` — Permissions `adsengine_view` / `adsengine_manage` / `adsengine_approve`
- `ENG20` — Contrat import-linter
- `ENG21` — Module `features/adsengine`
- `ENG22` — Écran Connexion & garde-fous
- `ENG23` — Dashboard « un chiffre »
- `ENG24` — Écran Campagnes
- `ENG25` — Boîte d'approbation — l'écran-vaisseau-amiral
- `ENG26` — Écran Brief hebdo
- `ENG27` — Bibliothèque créative
- `ENG28` — Journal d'actions
- `ENG29` — Hooks e2e + a11y
- `ENG30` — Audit multi-tenant + runbook d'onboarding client
- `ENG31` — Branding TenantTheme dans les écrans/briefs ENG
- `FG386` — Mode terrain hors-ligne (offline queue)
- `N100` — Build out multi-tenant operation on the existing tenant_id foundation (strict…
- `N101` — Tenant administration console (manage tenants/plans/usage/support) + self-serve signup…
- `N102` — After the modules above are built, update the master project document + PLAN + DONE log…
- `ODX1` — Carte des modules cible (docs/module-map.md)
- `ODX5` — Écran Paramètres → « Applications » (catalogue de modules)
- `ODX6` — Nav filtrée par modules actifs
- `ODX7` — Regrouper la nav legacy en « apps » via le registre UX1
- `ODX11` — Sortir les appels d'offres de compta → `apps/ao`
- `ODX12` — Sortir le portail client de compta → `apps/portail`
- `ODX13` — Rapatrier partenaires & territoires dans le CRM
- `ODX14` — Rapatrier la config de vente dans ventes
- `ODX15` — Sortir les notes de frais de compta → `apps/frais`
- `ODX16` — Reloger AbonnementMonitoring (revenu récurrent)
- `ODX17` — App Facturation — étape 1 (modèles, state-only)
- `ODX18` — App Facturation — étape 2 (vues/urls/recouvrement/frontend)
- `ODX19` — App Achats — étape 1 (modèles, state-only)
- `ODX20` — App Achats — étape 2 (vues/urls/flux stock/frontend)
- `ODX22` — Étendre les contrats import-linter au graphe post-découpage
- `ODX23` — Gating transversal des surfaces pilotées par registre
- `QPERF1` — DevisSerializer list N+1 (query budget déféré)
- `XACC12` — Position fiscale des tiers (exonérations avec attestation)
- `XKB35` — Appels audio/vidéo internes (huddles)
- `XMFG17` — Nomenclature multi-niveaux (sous-kits)
- `XMFG18` — Révisions de nomenclature + duplication de kit
- `XMFG19` — Remplacement de masse d'un composant dans toutes les nomenclatures
- `XMKT10` — Canal WhatsApp dans les campagnes (opt-in, gated)
- `XMKT34` — Génération IA de contenu de campagne (FR/AR), gated
- `XMKT35` — Planification de posts réseaux sociaux (calendrier de contenu, publication gated)
- `XMKT36` — [DECISION] Export de segments vers audiences publicitaires Meta
- `XPLT12` — Rapport de revue d'accès & comptes dormants
- `XPLT19` — Accès multi-sociétés pour un utilisateur + sélecteur de société
- `XPLT20` — Écritures inter-sociétés miroir (vente A → achat B)
- `XPLT21` — Softphone VoIP intégré (SIP/WebRTC, gated)
- `XPOS17` — QR showroom → fiche produit publique
- `XPOS19` — E-commerce transactionnel : checkout direct des petits articles (panier → paiement CMI…
- `XSAL5` — Lignes optionnelles sur devis + ajout self-service dans la proposition web
- `XSAL14` — Lignes de section et de note dans le devis
- `XSAL15` — Vue kanban « Prévision » avec glisser-déposer entre mois
- `XSAV22` — Déflection KB sur le portail client + tracking d'usage des articles
- `XSTK18` — Bon de livraison & liste de colisage bilingues FR/AR (RTL)
- `XSTK20` — Réappro kanban / deux-bacs par scan de carte
- `YAPIC1` — Classe de pagination partagée avec plafond dur (`max_page_size`)
- `YAPIC2` — Backends de filtre/tri/recherche par défaut + garde-fou anti-`ordering_fields` manquant
- `YAPIC3` — Enveloppe d'erreur unifiée via un `EXCEPTION_HANDLER` global
- `YAPIC4` — Middleware d'identifiant de corrélation (`X-Request-Id`) sur 100 % des réponses
- `YAPIC5` — Schéma OpenAPI 3 auto-généré + docs interactives (drf-spectacular)
- `YAPIC6` — Contrôle CI « schéma OpenAPI sans avertissement » + snapshot versionné
- `YAPIC7` — Stratégie de versionnement d'API unique et documentée (namespace de transition)
- `YAPIC8` — Livraison webhook fiable : Celery + retries exponentiels + timestamp signé + `event_id`
- `YAPIC9` — Mixin d'idempotence réutilisable pour TOUT endpoint de création interne…
- `YAPIC10` — Purge à fenêtre de rétention des clés d'idempotence (tâche Beat)
- `YAPIC11` — Sonde CI de parité de surface API par module
- `YAPIC12` — En-têtes de limitation de débit + 429 + `Retry-After` uniformisés
- `YCASH5` — Annulation d'une facture après acompte : réversion de l'acompte tracée mais AUCUNE…
- `YDATA1` — Garde CI : tout `ForeignKey`/`OneToOneField` déclare `on_delete` explicitement +…
- `YDATA2` — Sweep outillé : les FK vers les modèles porteurs d'argent/audit doivent être `PROTECT`…
- `YDATA3` — Sweep : `SET_NULL` seulement sur colonnes nullable, jamais sur les FK d'identité/tenant…
- `YDATA4` — Garde CI : complétude multi-tenant — tout modèle métier porte une FK `company`
- `YDATA6` — Garde CI : les champs monétaires sont `DecimalField`, jamais `FloatField`
- `YDATA7` — Sweep : chaque `DecimalField` monétaire déclare `max_digits` et `decimal_places`…
- `YDATA8` — Convention outillée + test : arrondi monétaire centralisé (une seule politique…
- `YDATA10` — Garde CI : `timezone.now()` partout, jamais de `datetime` naïf en code applicatif
- `YDATA11` — Sweep : pas d'`auto_now`/`auto_now_add` sur un `DateField` (ambiguïté fuseau) …
- `YDATA12` — Infra idempotence webhooks : modèle `ProcessedEvent` + insertion dans la transaction…
- `YDATA13` — Convention Celery : `acks_late` + `max_retries` bornés + time limits sur les tâches à…
- `YDATA14` — Garde CI : les tâches Celery à effets externes reçoivent des ids et re-lisent l'état…
- `YDATA15` — Sweep : `get_or_create`/`update_or_create` sur clés partagées doivent être adossés à…
- `YDATA16` — Sweep : read-modify-write sur compteurs/stock partagés sous `select_for_update` (ou…
- `YDATA17` — Décision + base outillée : politique soft-delete vs hard-delete unifiée (mixin +…
- `YDATA18` — Garde CI : contraintes uniques sur données tenant scopées par `company` ; unique sur…
- `YDATA19` — Sweep : défense en profondeur DB — `CHECK`/`NOT NULL` reflètent les invariants métier…
- `YDATA20` — Sweep : ajout d'une contrainte `unique`/`NOT NULL` sur table peuplée = backfill 3 temps…
- `YDATA21` — Garde CI : isolation tenant — chaque viewset filtre par `request.user.company` et…
- `YDATA22` — Sweep : montant + devise voyagent ensemble (invariant mono-devise MAD documenté et…
- `YHARD1` — Chiffrement au repos des champs sensibles (mixin `EncryptedField` réutilisable…
- `YHARD9` — Fondation analytique : séparation du store OLTP (réplica de lecture, optionnel) +…
- `YOPSB11` — Sweep d'archivage des tables à forte croissance (chatter/logs/webhooks)
- `YRBAC3` — Fine-grainer les apps gatées seulement par `IsResponsableOrAdmin` …
- `YRBAC10` — Vérification de parité gating frontend↔backend (source unique + test de dérive)
- `YRBAC11` — Sweep object-level : les vues fonctionnelles/actions custom touchant un objet par ID…
- `YRBAC12` — Test générique d'isolation multi-tenant sur tous les viewsets `TenantMixin`
- `YRBAC13` — Fine-grainer les @action de compta/marketing (dette YRBAC4 rehaussée batch-4)
- `YSERV4` — Événement `chantier_receptionne` sur le bus + création auto de l'enquête NPS à la…
- `YSERV8` — Semer la référence de production attendue du monitoring depuis l'étude/la recette (le…
- `YSERV10` — Réception sans contrat O&M → offre de contrat automatique (taux d'attache)
- `YSERV11` — NPS promoteur → demande de parrainage au moment de l'enchantement
- `YTEST4` — E2E processus lead-to-cash complet (backend, un seul test) asservissant la vraie…
- `YTEST5` — E2E chemins malheureux du processus commercial (devis refusé, expiré, avoir)
- `YTEST6` — E2E processus procure-to-pay complet (achat → réception → facture fournisseur →…
- `YTEST10` — Snapshots golden PDF (devis premium) : diff visuel à tolérance + assertions…
- `YTEST11` — Workflow revu de mise à jour des baselines PDF (pas d'auto-accept en CI)
- `ZFAC11` — Arrondi de caisse (cash rounding) sur factures réglées en espèces
- `ZMFG9` — Disponibilité multi-niveaux du kit (combien assemblables en traversant les sous-kits)
- `ZSAL9` — Avertissements de vente configurables par produit / par client (sale warnings)
- `ZSTK5` — Étiquette de colis (contenu + code-barres colis)
- `ZSTK13` — Réglages société stock (barcode / lots-séries / multi-emplacements / colis) — surface…
- `QW7` — [LIVE BUG] Stop the proposal-view beacon corrupting real leads
- `QW8` — Make QW4's email leg actually fire (today it's config-dead by default)
- `VX1` — Un seul or, un seul navy : fusion des jetons de marque
- `VX2` — Re-signer la coquille permanente (Sidebar + Header) aux couleurs de marque
- `VX3` — La typo de marque et le fond tokenisé au niveau `<body>`
- `VX4` — Finir le dark mode sur la surface legacy
- `VX5` — Data typography « .num » : les chiffres deviennent les héros
- `VX6` — Un seul langage de rayon et d'élévation
- `VX7` — Passe « calm color » : hiérarchie de poids visuel sur les écrans denses
- `VX8` — Un accent de couleur par module (le bout manquant du découpage Odoo)
- `VX9` — Le Lanceur d'applications TAQINOR (grille légère, pas une page)
- `VX10` — Apps épinglées personnelles dans la Sidebar
- `VX11` — Fil d'Ariane cliquable vers le cockpit du module + mémoire du dernier module
- `VX12` — « Plus » mobile = sélecteur d'apps en grille, pas le tiroir de 100 items
- `VX13` — Une seule recherche : hook partagé GlobalSearch + CommandPalette, pastilles de module
- `VX14` — Centre de notifications : onglets + config déclarative (delta mince, vérifié)
- `VX15` — Identité de cockpit : ModuleHero + accent + sparklines dans ModuleDashboard
- `VX16` — Rail de résumé permanent du générateur de devis (desktop)
- `VX17` — Générateur : le cœur visuel passe aux tokens (dark mode réparé sur l'écran le plus…
- `VX18` — Brancher la fonctionnalité fantôme : modèles de devis (DevisPresetPanel)
- `VX19` — Zéro popup navigateur : éradiquer les `window.alert/confirm/prompt` (~65 appels, 40…
- `VX20` — Fin de la « soupe d'actions » : menus Plus sur DevisList, RelancesPage et BulkActionBar…
- `VX21` — FactureList à parité de polish avec DevisList (squelette + cockpit trésorerie)
- `VX22` — Une vraie page lead : route `/crm/leads/:id`
- `VX23` — ChatterTimeline : battre le chatter d'Odoo, pas le sous-imiter
- `VX24` — Anatomie de carte Kanban à 2 niveaux + bandeau résumé de fiche
- `VX25` — MonthGrid partagé + résurrection du calendrier transverse
- `VX26` — Couleurs de stage dérivées des tokens (STAGES.py intact — règle #2 à la lettre)
- `VX27` — Le cockpit du matin : Dashboard par rôle + bandeau « aujourd'hui »
- `VX28` — Un seul langage de graphique + un seul PageHeader
- `VX29` — CommercialDashboard : le restyle « star » de l'écran le plus waouh
- `VX30` — Le mur de flotte vivant (cartes par centrale + pouls temps réel)
- `VX31` — SAV en boîte de réception : split-view liste + détail
- `VX32` — CartePage + MapView rejoignent le design system (la « control room » géographique)
- `VX33` — Le Pilotage stock devient la tour de contrôle qu'il prétend être
- `VX34` — Login signature (le premier pixel de la marque)
- `VX35` — Paramètres : de 22 onglets plats à une vraie architecture d'information
- `VX36` — L'onboarding sort de sa cachette (bannière Dashboard + first-run)
- `VX37` — L'IA qui « pense » : streaming visuel + preuve lisible par un humain
- `VX38` — Admin cohérent : RolesManagement + documents GED sur DataTable, matrice de permissions
- `VX39` — OCR : source et extraction côte à côte + correction inline
- `VX40` — Le délice mesuré : célébration « devis signé » + états vides illustrés
- `VX41` — Craft data-viz : palette catégorielle de marque, comparaison de période, annotations
- `VX42` — Terrain un-tap : appeler/naviguer sur Ma journée + FAB + retour haptique
- `VX43` — Gestes natifs : swipe-to-action, pull-to-refresh, sheets cohérents
- `VX44` — Photos chantier en rafale + partage natif WhatsApp
- `VX45` — La voix TAQINOR : microcopie FR premium + fin des emojis-icônes
- `VX46` — « Mes préférences » : un centre de personnalisation par utilisateur
- `VX47` — Aide contextuelle intégrée : popovers « ? » sur les écrans difficiles

**Blocked — awaiting founder decision (2)**

- `QC2` — [GATED: paid — Inforisk/Charika API] Registry-backed autocomplete (the true Odoo-style…
- `S21` — Real-time WebSocket upgrade (Django Channels)
