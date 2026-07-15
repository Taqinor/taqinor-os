# CODEMAP — TAQINOR OS

Generated from commit `dev` on 2026-06-29, refreshed for the functional-domain expansion wave (5 parallel worktree lanes: apps/compta clôture de période + OD manuelles + à-nouveaux FG115–117; apps/ventes solar string-design + inverter match + tilt/azimut FG246/247/249; apps/installations jalons/modèles-de-projet/réunions FG293/296/298; **NEW app apps/flotte** Vehicule+EnginRoulant FLOTTE1/2/4; **NEW app apps/ged** Cabinet/Folder/Document/Version GED1/2/3 — all additive, company-scoped, tested), on top of the prior `dev-uiwave-20260621` world-class UI wave (34 frontend UI/UX tasks: premium DataTable, calm chrome, foundation hooks/primitives, page redesigns) (PLAN2 priority-queue run — Group Q Devis↔Toiture-3D pipeline backend (Q1–Q7: Devis.roof_layout/roof_image + layout endpoints, Lead roof_point/roof_outline/bill_kwh + per-lead token, build_devis_from_layout() service, MinIO roof-image, layout-aware quote data with byte-identical no-layout path, tokenized /proposal data endpoint + e-sign accept); Group R agentic layer — NEW APP `apps/agent` (in-code action registry + `/api/django/agent/` catalogue, AG1), FastAPI registry-driven tools with propose→confirm (`/sql-agent/confirm`, AG2) surfaced on /query, assistant confirm/result cards (AG3), domain agent actions in ventes/crm/stock/sav/installations `agent_actions.py` (AG4–AG9), Groq-Whisper assistant voice `/sql-agent/transcribe` (AG10) + voice/hands-free chat (AG11/AG12); Group S internal team chat — NEW APP `apps/chat` (Conversation/Member/Message/Attachment/Reaction/Mention, company+membership scoped, `/api/django/chat/`, S1–S9), self-hosted faster-whisper `/chat/transcribe` (NEW dep, `CHAT_TRANSCRIPTION_ENABLED`, S10) + Celery transcription pipeline (S11), full React `features/messaging` UI + `/messages` route (S12–S20); design/UI/reporting polish (F120–F123 OKLCH tokens, G124–G128 primitives, K147/N161/K148/K149/J146/P167 chart kit + dashboard + table unification); P171 DataTable→@tanstack engine swap (API-compatible, full parity). ADDITIVE migrations: ventes/0024, crm/0024, chat/0001, notifications/0007. Founder standing consent recorded in CLAUDE.md lifting the ARCH/AUTH/COST/DECISION/GALLERY/DEP gate. + 2026-06-22 greenfield-foundations run: 7 NEW apps stood up (apps/rh DossierEmploye master FG154/DC29, apps/paie ParametrePaie/BaremeIR PAIE1/2/4, apps/gestion_projet Projet/ProjetChantier PROJ1, apps/contrats Contrat CONTRAT1/2, apps/qhse NCR/CAPA QHSE1/9/10, apps/kb KbArticle KB1, apps/litiges Reclamation LITIGE1) — additive, multi-tenant, admin-gated, tested; INSTALLED_APPS+urls wired; 13 tasks ticked. BLOCKED: S21 WebSocket/Channels (needs provisioned ASGI/nginx-WS infra), I134/I138 ⌘K palette (reconcile with existing providers).) + 2026-06-22 `claude/serene-ptolemy-dj5cs0` wave-1 run: 8 parallel worktree lanes — FG122 (compta consolidated treasury position + AR/AP/payroll/TVA projection, GL-only selector + read endpoint), M4 (last `ventes → audit` back-edge removed — PDF audit capture now flows through the `core.events.document_pdf_generated` bus with an `audit` receiver; new import-linter contract pins it), FG157 (apps/rh `Remuneration` gated by the new `salaires_voir` permission), PAIE3 (apps/paie 2026 Moroccan legal payroll defaults seeded editable + `valide_par_fondateur` flag), PROJ5 (apps/gestion_projet `Tache` WBS with self-FK sub-tasks), QHSE5 (apps/qhse auto-conformity min/max on `PointControleModele`/`ReleveControle`), FG350 (frontend global `CopilotPanel` drawer reusing the FastAPI agent), GED5 (frontend `/ged` arborescent navigator over existing ged endpoints) — all additive, multi-tenant, tested; ADDITIVE migrations rh/0004, paie/0002, qhse/0004, gestion_projet/0005. + wave-2 (same run): FG123 (compta `RapprochementBancaire`/`LigneReleve`/`PointageReleve` — statement↔GL pointing, écart-zero close, no écriture), FG49 (ventes account-coded grand-livre export CGNC 3421/7111/4455, xlsx+csv, configurable codes), FG351 (apps/agent registry guarded write actions `ventes.devis.create`/`crm.client.create`/`crm.lead.create` via propose→confirm + FastAPI dynamic action_tools), FG158 (rh `DossierEmploye` emergency-contact + extended coordinates fields), PAIE5 (paie family-charge deduction params + `compute_ir` helper), GED6 (ged `DocumentLien` generic-target link via `records.ALLOWED_TARGETS` +ventes.boncommande), PROJ6 (gestion_projet `DependanceTache` FS/SS/FF/SF + lag with cycle guards), QHSE6 (qhse hold-point gating selector/endpoint) — all additive, multi-tenant, tested; ADDITIVE migrations compta/0006, rh/0005, paie/0003, ged/0002, gestion_projet/0006 (FG49/FG351/QHSE6 need none); import-linter stays 4/4. + wave-3 (same run, 7 lanes): FG124 (compta `Caisse`/`MouvementCaisse`/`ClotureCaisse` petty-cash with optional GL posting honouring the FG115 period lock), FG50 (ventes acompte transfer/refund on facture cancel — re-point Paiement or reversing negative Paiement, chatter, no migration), FG159 (rh `DocumentEmploye` vault reusing `records.Attachment` MinIO storage + optional expiry), PAIE6 (paie `Rubrique` configurable payslip-line catalogue + idempotent seed), GED7 (ged `migrate_attachments_to_ged` command importing records.Attachment into Documents reusing file_key + DocumentLien), PROJ7 (gestion_projet `Jalon` milestones + `facturation_pct`), QHSE7 (qhse `ReleveCourbeIV` PV string I-V curve + fill factor) — all additive, multi-tenant, tested; ADDITIVE migrations compta/0007, rh/0006, paie/0004, gestion_projet/0007, qhse/0005 (FG50/GED7 need none); import-linter stays 4/4. FG352 (RAG/pgvector, DEP:langchain-textsplitters) intentionally left [ ] for a focused run. + 2026-06-22 `claude/plan-md-completion-ysbchz` drain: 8 parallel worktree lanes off PLAN.md (compta FG125–130, ventes FG51/53/248/250/251, core FG355–359 NoOp-AI, rh FG160–165, paie PAIE7–12, ged GED8–13, gestion_projet PROJ8–13, qhse QHSE8/11–15 — 46 tasks; ADDITIVE migrations across those apps + customfields/0003; new NoOp scaffolds add no external dependency; GED12 semantic embedding OFF by default). + 2026-06-23 PLAN2 **Group U** drain (U1–U14, 10 parallel worktree lanes, one self-merge): lead-modal stays-open UX (U1), mouse-wheel + mobile-header CSS regressions (U2/U3), WhatsApp-send flips devis→envoyé via a NEW `core.events.devis_sent` event (U4), surface generated factures/BC in the devis list + BC-state warning (U5/U8), hide/badge superseded devis revisions (U7), auto-create chantier on devis acceptance via the `devis_accepted` bus (U6), stock reservation on the direct generer-facture path (U9), relance-escalation reset on full payment (U10), phantom-signé flag on post-acceptance refusal (U11, flag-only), direct nullable lead FK on Facture/BonCommande (U12), avatar same-origin proxy fix (U13), GED « Documents » write UI + `documents/televerser/` upload (U14) — additive, multi-tenant, tested; ADDITIVE migrations ventes/0027_devis_date_envoi + 0028_boncommande_lead_facture_lead. + 2026-06-24 PLAN.md batch-1 drain (8 parallel worktree lanes off the FG/module wave plan, adversarial review + local CI incl. makemigrations-check & full affected test run, one self-merge): 7 shipped — FG52 (ventes multi-currency `devise`/`taux_change` + CompanyProfile default), FG166 (rh `Pointage` clock-in/out), CONTRAT6 (contrats `confidentialite` gated on `menu_tier`), FLOTTE5 (flotte `ActifFlotte` unified asset ref), PAIE13 (paie multi-profile base-salary + proration), GED14 (ged inline `apercu` preview), PROJ14 (gestion_projet delay detection). ADDITIVE migrations ventes/0029 + parametres/0025, rh/0008, contrats/0005, flotte/0005, paie/0006. **FG131 (compta 3-way match) DEFERRED/backed-out** — the build duplicated stock's BonCommandeFournisseur/FactureFournisseur (reverse-accessor clash); needs a rebuild reusing stock procurement via selectors/services (left `[ ]`). + 2026-06-27 `claude/lucid-banzai-33af1c` PLAN.md wave-1 drain (5 parallel worktree lanes, one self-merge): PAIE14 (paie heures-sup majorées 25/50/100 %), FG167 (rh `FeuilleTemps` timesheets + labour-hours selector), CONTRAT7 (contrats `ModeleContrat` + `/instancier/`), FLOTTE7 (flotte `Conducteur` + permis), QHSE16 (qhse `Audit`/`ReponseCritere` + score → NCR) — all additive, multi-tenant, tested; ADDITIVE migrations paie/0007, rh/0009, contrats/0006, flotte/0006, qhse/0010. No new external/paid dependency, no auth change. Validated on the docker CI harness (511 affected-app tests green, makemigrations --check clean). + 2026-06-27 same run waves 2+3 (9 more file-disjoint lanes): GED15 (ged document version history + restore, `restored_from` audit), PROJ15 (gestion_projet `RessourceProfil`/`Equipe`, internal cout_horaire), FG39 (crm `ObjectifCommercial` + attainment selector, backend), FG5 (notifications `WorkingHoursConfig`/`Holiday` + calendar helpers + `seed_ma_holidays`, opt-in), FG86 (sav `Ticket.share_token` + public read-only tracking endpoint, allowlist no cout/chatter), KB5 (kb `seed_kb_templates` 5 SOP/ONEE/82-21 gabarits), FG96 (reporting `DashboardConfig` per-user/role, backend), FG102 (publicapi webhook deliveries history + replay + test, backend), FG297 (installations `DocumentProjet`/`RevisionDocument` versioned project-doc register) — all additive, multi-tenant, tested; ADDITIVE migrations ged/0008, gestion_projet/0010, crm/0028, notifications/0010, sav/0009, reporting/0003, installations/0014 (KB5/FG102 need none); import-linter stays 4/4. No new external/paid dependency, no auth change. + 2026-06-29 `claude/relaxed-edison-c91f99` PLAN.md wave-1 drain (8 parallel file-disjoint worktree lanes, adversarial review + local docker CI, one self-merge): FG135 (compta `NoteFrais` notes de frais + remboursements, justificatif photo, écritures équilibrées, verrou de période, réf NDF race-safe), FG291 (installations `Projet` programme multi-chantiers regroupant chantiers/devis/tickets par FK chaînes, machine d'états propre — NEW arch component), FG255 (ventes `ev_charger_sizing` borne VE couplée au PV, math pure), FG361 (core `forecast.py` prévision CA/devis mensuels, Holt-Winters statsmodels + repli pur Python), FG172 (rh `Competence`/`CompetenceEmploye` matrice de compétences), CONTRAT13 (contrats `RegleApprobation` par montant/type + résolveur), FLOTTE13 (flotte conso L/100 km & kWh/100 km depuis pleins+odomètre, endpoint scopé), GED17 (ged `Document.statut` cycle de vie brouillon→…→obsolète, machine d'états gardée, distinct de STAGES.py) — all additive, multi-tenant, tested; ADDITIVE migrations compta/0011, installations/0016, rh/0014, contrats/0010, ged/0011 (FG255/FG361/FLOTTE13 need none). **NEW external dependency `statsmodels==0.14.4`** (FG361, import défensif + repli si absente). Adversarial review fixed 2 CI-red issues pre-merge (FG361 garde NaN avant clamp, FLOTTE13 action `consommation` en lecture tout rôle) + an FG135 reference race; core stays a foundation layer (import-linter 4/4). + 2026-06-29 `claude/relaxed-edison-c91f99` PLAN.md wave-2 drain (8 parallel file-disjoint worktree lanes, adversarial review + local docker CI): FG136 (compta `BaremeIndemnite`+`IndemniteChantier` indemnités km/per-diem, haversine, écritures équilibrées + verrou de période), FG292 (installations `ProjetTache` tâches/sous-tâches + prédécesseur avec gardes anti-cycle — étend l'ARCH Projet FG291), FG256 (ventes `battery_storage_sizing` autoconso-max vs backup-heures, math pure), FG362 (core `win_probability.py` scorer pur fondation + `reporting/pipeline.py` pondéré par lead, repli statique), FG173 (rh `Habilitation` électriques NF C 18-510 + expiry), CONTRAT14 (contrats `EtapeApprobation` workflow depuis `RegleApprobation`, ne touche pas `Contrat.statut`), FLOTTE14 (flotte `CarteCarburant` + détecteur d'anomalies pleins), QHSE19 (qhse `RetourClientQualite` satisfaction 1–5) — all additive, multi-tenant, tested; ADDITIVE migrations compta/0012, installations/0017, rh/0015, contrats/0011, flotte/0012, qhse/0013 (FG256/FG362 need none). No new external/paid dependency, no auth change; import-linter 4/4 (core reste fondation). Fixed an FG136 constraint Q-order migration drift pre-merge (makemigrations --check clean). + 2026-06-29 `claude/relaxed-edison-c91f99` PLAN.md wave-3 drain (8 parallel file-disjoint worktree lanes, adversarial review + local docker CI incl. the 8 wave-3 test modules run green before push): FG137 (compta `DeclarationTVA` préparation TVA collectée−déductible par régime/méthode + export), FG294 (installations `BudgetProjet`/`BudgetEngagement` budget vs réel agrégé cross-app via get_model/selectors, alerte dépassement — ARCH), FG257 (ventes `simulate_bankable_yield` P50/P90 + Performance Ratio, math pure), FG363 (core `churn_risk.py` scorer pur fondation), FG174 (rh `Certification` non-électriques + expiry), CONTRAT15 (contrats `ContratActivity` chatter/journal des transitions), FLOTTE15 (flotte `PlanEntretien` entretien préventif km/date/heures via ActifFlotte), GED18 (ged `DemandeApprobation` workflow réutilisant la machine d'états GED17) — all additive, multi-tenant, tested; ADDITIVE migrations compta/0013, installations/0018, rh/0016, contrats/0012, flotte/0013, ged/0012 (FG257/FG363 need none). No new external/paid dependency, no auth change; import-linter 4/4 (core reste fondation, FG363 stdlib-only). No migration drift. + 2026-06-29 `claude/relaxed-edison-c91f99` PLAN.md wave-4 drain (8 parallel file-disjoint worktree lanes, adversarial review + local docker CI of the 8 wave-4 test modules before push — **ZERO migrations this wave**, all aggregation/pure-math/helper tasks): FG138 (compta `releve_deductions_tva` annexe TVA déductible depuis le GL, réconcilie FG137), FG295 (installations `projet_pnl` P&L consolidé revenu−coûts par Projet, réutilise les agrégats cross-app FG294), FG258 (ventes `hourly_self_consumption` profil autoconso 8760 h + parser xlsx openpyxl déjà présent), FG364 (core `stock_reorder.py` prévision rupture/réappro, stdlib seul), FG175 (rh `echeances_rh` moteur d'alertes d'expiration unifié + commande notifiant via `notifications.notify`), PROJ18 (gestion_projet `plan_de_charge` capacité vs affecté), PAIE20 (paie helper `cimr_salariale` CIMR optionnelle par employé, champs préexistants), QHSE20 (qhse `iso9001_readiness` tableau de bord) — all additive, multi-tenant, tested; NO migrations; no new external/paid dependency, no auth change; import-linter 4/4 (core reste fondation). No migration drift. + 2026-06-29 `claude/relaxed-edison-c91f99` PLAN.md wave-5 drain (8 parallel file-disjoint worktree lanes, adversarial review + local docker CI of the 8 wave-5 test modules before push): FG139 (compta `RetenueSource` RAS retenue à la source + bordereau de versement, export `?export=csv`), FG299 (installations `plan_de_charge_equipes` capacité vs affecté des techniciens/équipes sur interventions), FG259 (ventes `net_metering_savings` valorisation surplus injecté par tranche loi 13-09), FG365 (core `payment_delay.py` prédiction de retard de paiement, stdlib seul), FG176 (rh `verifier_habilitation_requise` garde d'affectation par habilitation, blocage doux), CONTRAT16 (contrats `SignatureContrat` e-sign in-app loi 53-05, preuve serveur, bascule statut signé), FLOTTE16 (flotte `EcheanceEntretien` génération idempotente d'échéances dues + alertes), GED19 (ged `AclGed` ACL par dossier/document héritage+override, rétrocompatible) — all additive, multi-tenant, tested; ADDITIVE migrations compta/0014, contrats/0013, flotte/0014, ged/0013 (FG299/FG259/FG365/FG176 need none). No new external/paid dependency, no auth change; import-linter 4/4. Fixed a GED19 CheckConstraint `condition=` migration drift pre-merge (Django 5.1 deconstruction; Meta.constraints aligned with the migration, makemigrations --check clean). + 2026-06-29 `claude/relaxed-edison-c91f99` PLAN.md wave-6 drain (8 parallel file-disjoint worktree lanes, adversarial review + local docker CI of the 8 wave-6 test modules before push): FG140 (compta aide au calcul de l'IS — barème progressif + cotisation minimale + 4 acomptes + régularisation, selectors-only), FG300 (installations `conflits_affectation` double-booking technicien/camionnette même jour), FG260 (ventes `tariff_escalation_projection` escalade ONEE 20-25 ans + VAN/TRI stdlib), **FG366 (core moteur de workflow BPM générique `WorkflowDefinition/StepDefinition/Instance/StepInstance` cible générique contenttypes + SLA/escalades — NEW ARCH component dans la fondation, import-linter 4/4)**, FG177 (rh `VisiteMedicale` du travail + aptitude + expiry, alimente FG175), PROJ19 (gestion_projet `conflits_affectation` ressources chevauchantes), PAIE21 (paie frais professionnels — déjà présent, tests ajoutés), QHSE21 (qhse `EvaluationRisque`/`LigneEvaluationRisque` document unique, criticité=gravité×probabilité) — all additive, multi-tenant, tested; ADDITIVE migrations core/0002 (BPM), rh/0017, qhse/0014 (FG140/FG300/FG260/PROJ19/PAIE21 need none). No migration drift; no new external/paid dependency, no auth change; import-linter 4/4 (core reste fondation). + 2026-06-29 `claude/relaxed-edison-c91f99` PLAN.md wave-7 drain (8 parallel file-disjoint worktree lanes, adversarial review + local docker CI of 9 wave-7 test modules before push): FG141 (compta `export_fec` export FEC DGI 18 colonnes, `?export=fec`), FG301 (installations `nivellement_charge` rééquilibrage des interventions surchargées sans conflit, lecture seule), FG261 (ventes `optimize_subscribed_power` réduction puissance souscrite post-PV C&I), FG367 (core `rules.py` évaluateur de conditions ET/OU/NON + actions séquentielles, pur fondation), FG178 (rh `EpiCatalogue`/`DotationEpi` dotation EPI nominative), CONTRAT17 (contrats auto signé→actif sur signature), FLOTTE17 (flotte `Garage`/`OrdreReparation` ordres de réparation + coûts), GED20 (ged `PartageGed` partage tokenisé public expiry/password/quota) — all additive, multi-tenant, tested; ADDITIVE migrations rh/0018, flotte/0015, ged/0014 (FG141/FG301/FG261/FG367/CONTRAT17 need none). No migration drift; no new external/paid dependency, no auth change; import-linter 4/4 (core reste fondation). GED20 introduces a PUBLIC AllowAny tokenized document endpoint (token-only resolution, expiry/quota/password-hash, no cross-tenant leak — security model calqué sur ventes.ShareLink). + 2026-06-29 `claude/relaxed-edison-c91f99` PLAN.md wave-8 drain (8 parallel file-disjoint worktree lanes, adversarial review + local docker CI of 8 wave-8 test modules before push): FG142 (compta `liasse_fiscale` trousse liasse fiscale bilan+CPC+balance+annexe-TVA, réutilise les sélecteurs), FG302 (installations `IndisponibiliteRessource` calendrier de disponibilité technicien/camionnette + sélecteur d'exclusion), FG262 (ventes `module_degradation_curve` dégradation modules + planchers de garantie), FG368 (core `core/jobs.py` + `ScheduledJobViewSet` liste/exécution des jobs Celery Beat, admin, câblé `/api/django/core/`), FG179 (rh péremption/contrôle EPI dérivés + alertes, alimente FG175), PROJ20 (gestion_projet `nivellement_charge` rééquilibrage ressources projet), PAIE22 (paie calcul IR — déjà présent PAIE5, 30 tests ajoutés), QHSE22 (qhse `document_unique_valide`/`exiger_document_unique` gate document unique avant pose) — all additive, multi-tenant, tested; ADDITIVE migrations installations/0019, rh/0019 (FG142/FG262/FG368/PROJ20/PAIE22/QHSE22 need none). FG368 added a root-URLConf line (`api/django/core/` → `core.urls`, orchestrator wiring step). No migration drift; no new external/paid dependency, no auth change; import-linter 4/4 (core reste fondation, jobs via celery infra). Wave-9 PLAN.md drain (2026-06-29, 8 parallel file-disjoint worktree lanes): rh `EmargementEpi` (FG180), contrats `VersionContrat` (CONTRAT18), flotte `Pneumatique`/`PieceFlotte` (FLOTTE18), ged watermarking flags `Document.watermark_diffusion`/`PartageGed.watermark` (GED21, lazy PyMuPDF/Pillow — no hard dep), core workflow-template library + `/api/django/core/` workflow-templates route (FG369), plus selector/endpoint-only FG143 (compta état 9421), FG303 (installations van planning), FG263 (ventes PPA model) — all additive & company-scoped, 4 additive migrations (rh 0020, contrats 0014, flotte 0016, ged 0015). Wave-10 PLAN.md drain (2026-06-29, 7 parallel file-disjoint worktree lanes in apps disjoint from wave 9): crm `ConcurrentPerte` (lost-deal competitor capture FG242), gestion_projet `BudgetProjet`/`LigneBudgetProjet` (PROJ21), qhse `PermisTravail` (QHSE23), kb `KbArticleAcl`/`KbLecture` (role ACL + read tracking KB7), sav `AlarmeOnduleur` (inverter alarms FG280), plus paie allocations-familiales employer charge (PAIE23, fields on ParametrePaie/BulletinPaie) and selector-only LITIGE6 (disputes dashboard) — all additive & company-scoped, 6 additive migrations (crm 0029, gestion_projet 0013, kb 0005, paie 0011, qhse 0015, sav 0011). Wave-11 PLAN.md drain (2026-06-29, 6 parallel file-disjoint worktree lanes resuming wave-9 app lanes off the merged base): compta `TimbreFiscal` (droit de timbre cash FG144), rh `AccidentTravail` (HSE/accidents register FG181), installations `SousTraitant` (subcontractor registry FG304), ged `PolitiqueRetention` (non-destructive retention policies GED22), flotte `EcheanceReglementaire` (regulatory deadlines FLOTTE19), plus pure-math FG264 (ventes pumping-cycle water yield) — all additive & company-scoped, 5 additive migrations (compta 0015, rh 0021, installations 0020, ged 0016, flotte 0017). Wave-12 PLAN.md drain (2026-06-29, 3 parallel file-disjoint lanes resuming wave-10 app lanes): qhse `ConsignationLoto` (LOTO on a work permit QHSE24), crm `PointContact` (multi-touch attribution journal FG204), plus paie taxe de formation professionnelle employer charge (PAIE24, BulletinPaie snapshot) — all additive & company-scoped, 3 additive migrations (paie 0012, qhse 0016, crm 0030). Wave-13 PLAN.md drain (2026-06-30, 6 parallel file-disjoint worktree lanes resuming wave-9 app lanes): compta `RetenueGarantie`/`CautionBancaire` (FG145), rh `PresquAccident` (near-miss FG182), installations `OrdreSousTraitance` (subcontractor work orders FG305), ged `ArchivageLegal` (legal write-once GED23), flotte `BaremeVignette` + `Vehicule.puissance_fiscale` (TSAV FLOTTE20), plus selector-only PROJ22 (committed-vs-actual project cost) — all additive & company-scoped, 5 additive migrations (compta 0016, rh 0022, installations 0021, ged 0017, flotte 0018).
Structure fingerprint: c20ce745ee66e4846ed2fe33aa1ceea374d60dfa2befdc0748888f0cd3781861
Plan fingerprint: 70e036aa9ea84a2e2a577b8cae1f8d5fd6fe57c175a2cb56c229c4928ab73ffb

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
├── scripts/check_platform.py     CI guard (ARC52): 8 DB-free source-scan checks — no new bespoke chatter/FileField/weasyprint-import/count()+1-numbering/hand-rolled company-FK model/unscoped ModelViewSet/flat storage key/hardcoded brand string outside their frozen baselines; wired into backend-lint (SCA4/SCA29/SCA37/SCA42 extend the same baselines)
├── scripts/scaffold-module.mjs   ARC43: generates a frontend module.config.jsx + api client + example ListShell page for a new "coquille" module
├── .github/workflows/ci.yml      CI: changes(detector) + backend-lint, backend-tests, frontend-lint, stage-names, web-build-test, e2e + ci-gate(aggregate); per-job path filtering (infra/docs/config → stage-names only); push on main/dev only + all PRs (PR concurrency-cancel)
├── apps/web/                     Marketing website (Astro, deploys via Cloudflare) — separate autopilot scope
├── docs/                         PLAN.md, WEB_PLAN.md, this CODEMAP.md, swap maps, module-playbook.md (ARC51/SCA38 — canonical "add a module" guide)
│
├── backend/
│   ├── django_core/              Django REST API (project: erp_agentique)
│   │   ├── core/                   Foundation layer, NOT under apps/ — TenantModel/SoftDeleteModel (ARC1/ARC15), CompanyScopedModelViewSet (ARC2/ARC55), numbering (ARC6), pdf.render_pdf (ARC11), platform registry + coverage matrix (ARC28/29-34/40/41), documents.DocumentMetier kit (SCA30-33), request_cache (SCA43), benchmarking floor (SCA48), signup_hooks (SCA20/28), events bus, BPM workflow engine (ARC10/FG366+)
│   │   ├── app_template/           ARC42: scaffold source for `manage.py startapp_erp` (models/viewsets/selectors/services/serializers/urls/tests stubs, all `.py-tpl`)
│   │   ├── authentication/         Tenant root: Company + CustomUser, JWT, registration  (NOT under apps/)
│   │   └── apps/
│   │       ├── crm/                Leads (sales funnel) + Clients + chatter + channels/tags/loss-reasons
│   │       ├── ventes/             Quotes (devis), orders (BC), invoices (factures), credit notes, payments, quote_engine
│   │       ├── stock/              Product catalogue, suppliers, movements, locations, supplier POs/returns
│   │       ├── installations/      Chantiers (installation projects), interventions, checklists, field execution
│   │       ├── sav/                After-sales: equipment registry, SAV tickets, maintenance contracts
│   │       ├── reporting/          Dashboards/KPIs/insights/audit-log (read-only; no models of its own)
│   │       ├── parametres/         Company profile + business settings + WhatsApp templates + TauxTVA/ConditionPaiement/UniteMesure referentials (ARC23/24/27)
│   │       ├── roles/              RBAC: per-company roles + permission lists
│   │       ├── records/            Generic activities + file attachments (ContentType-based, cross-module) + platform_guards.py (ARC8/26/SCA4/37 guard logic, consumed by scripts/check_platform.py)
│   │       ├── customfields/       Admin-defined custom fields for Lead/Client/Produit (values in custom_data); registry now data-driven (ARC14) and platform-registry-fed (ARC31)
│   │       ├── tiers/              Cross-app party directory (Odoo `res.partner` equivalent) — bridged additively from crm.Client/Lead, stock.Fournisseur, compta.Partenaire, rh.DossierEmploye (ARC18/19/21/56)
│   │       ├── documents/          Field-execution PDFs (PV réception, bon de livraison, attestation) — no models
│   │       ├── dataimport/         Two-step CSV/XLSX import (dry-run + commit) for leads/clients/products, generic parser (ARC13) + registry-driven targets (ARC32) — no models
│   │       └── contact/            Public landing-page contact form (parked by default) — no models
│   │
│   ├── fastapi_ia/               FastAPI AI service (root_path /api/fastapi)
│   │   └── app/api/endpoints/      ocr.py (Zhipu OCR), sql_agent.py (LangChain NL→SQL)
│   └── nginx/                    Reverse-proxy config
│
└── frontend/                     React/Vite SPA
    └── src/
        ├── router/                 Route table (path → page component) + moduleRoutes.jsx module registry (8 features migrated to module.config.jsx this run — ARC48/54)
        ├── pages/                  Page components grouped by area (crm, ventes, stock, sav, …)
        ├── features/               Redux slices + domain logic per area (see §5)
        ├── api/                    axios modules, one per backend area; resource.js shared CRUD factory (ARC44)
        ├── components/             Shared UI
        ├── hooks/ store/ utils/    Cross-cutting React/Redux helpers, incl. useResource.js (ARC45) and the useHasRole/useHasPermission sweep (ARC47)
        ├── ui/module/              RecordShell.jsx (ARC46) composing DetailShell — detail/form counterpart to ListShell
        └── sw.js                   PWA service worker (auto-update)
```

---

## 4. Backend, app by app

All multi-tenant models carry a `company` FK → `authentication.Company`. ViewSets
filter `get_queryset()` by `request.user.company` and force-assign `company` in
`perform_create` (never read from the request body). The literal tenant field is
**`company`** — there is no field named `tenant_id`.

> **Contrainte transversale de conception (VX125).** Budget de densité de
> signaux : max 3 signaux ambiants simultanés par écran de liste, jamais deux
> redisant le même chiffre ; badge de maturité `<BetaBadge>` sur les modules
> jeunes avec critère de retrait objectif. Voir `docs/design-density-budget.md`.

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
- **Tenant lifecycle (SCA18-22).** `Company.statut` (actif/suspendu/fermeture, mirrors the historical `actif` bool both ways) gates login/JWT-refresh/API access — enforced in the authenticator (`cookie_auth.py`) and JWT issuance, never a middleware (SCA18, applied where the request already resolves the user — zero extra queries). `selectors.active_companies` (SCA19) is the single source of "sweepable" companies for beat fan-outs. `services.close_company`/soft-close (SCA21) moves a tenant to `fermeture` + timestamps `date_fermeture` (30-day grace before purge). A staff-only founder console (SCA22, `IsSuperuserConsole`) at `auth/console/tenants/` (list + usage counts via other apps' selectors, never their models) + `.../statut/` (change actif/suspendu/fermeture) + `.../note/` (free-text `plan_flag`, never billing). **SCA46** adds `Company.benchmarking_opt_in` (opt-in consent, default False) gating the k-anonymized cross-tenant aggregates (`core.benchmarking`). **SCA23** adds a "day-2" tenant test (`tests/test_day2_tenant.py`) as a CI sellability gate: registers a second company and exercises its full journey (quote→PDF proposal→accept) in isolation from the first, catching cross-tenant regressions the single-company test suite would miss.

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
- **ARC4** sweeps all 13 crm ViewSets onto `CompanyScopedModelViewSet` (behaviour identical, isolation now auto-covered by the generic tenant sweep test). **ARC18/56** add nullable `tiers` FKs mirroring `Client` (migration crm/0050) and `Lead` (migration crm/0051) into the `tiers.Tiers` directory (`tiers_bridge.py`). **ARC28/29/30/33** add `apps/crm/platform.py` (the first platform manifest, alongside `contrats`) declaring `searchable_models`/`record_targets`/`agent_actions_module` — `agent_actions.py` exposes read-only lead/client agent actions.

### ventes — quotes, orders, invoices, credit notes, payments, quote engine
The largest app: full quote→order→invoice→recovery lifecycle plus the vendored
premium quote-PDF engine.
- **Devis** (quote) — `company` FK; `reference` (per company+month); `client` FK→crm.Client; `lead` FK→crm.Lead (nullable, lead-primary quoting); `statut` (**brouillon/envoye/accepte/refuse/expire**); `mode_installation` (residentiel/industriel/agricole); `option_acceptee` (sans_batterie/avec_batterie); `etude_params` JSON (kWc, production, autoconso, payback, pump CV/HMT/débit…); `taux_tva`, `remise_globale`; versioning (`version`, `version_parent`, `superseded_by`, `is_active`); discount approval (`remise_approuvee`, `remise_approuvee_par`); `fichier_pdf` (MinIO key). **FG52** adds `devise` (ISO 4217, default MAD) + `taux_change` to **Devis** and **Facture** (and `parametres.CompanyProfile.devise_defaut`): on API create without an explicit devise, the company default is applied (fallback MAD); the premium PDF `fmt()` and UBL export (`dgi_export.py`/`utils/ubl.py`) emit the document currency. No base-currency conversion (currency is document-borne). **SCA47** adds `prix_par_kwc` (Total TTC ÷ kWc, DecimalField) — derived and FROZEN write-once at first save when a kWc + total exist (null for kWc-less/pompage devis, never recomputed after); internal generator/BI signal ONLY, same regime as `stock.Produit.prix_achat` — never on a PDF or client-facing output. **SCA39** adds `Meta.indexes` `(company, statut)` + `(company, date_creation)` on Devis and Facture (concurrent `AddIndex`, no blocking lock) — the money-path query subset of NTPLT20.
- **LigneDevis** — `devis` FK, `produit` FK→stock.Produit, `designation`, `quantite`, `prix_unitaire`, `remise`, `taux_tva` (nullable → falls back to devis rate; 10% panels / 20% other).
- **BonCommande** (client order) — `devis` OneToOne→Devis (nullable), `client` FK; `statut` (**en_attente/confirme/livre/annule**); marking `livre` decrements stock.
- **Facture** (invoice) — `devis` FK (new échéancier path) **and/or** `bon_commande` OneToOne (legacy path); `client` FK; `type_facture` (**acompte/intermediaire/solde/complete**); `statut` (**brouillon/emise/payee/en_retard/annulee**); `pourcentage`, `libelle`, frozen `montant_ht/tva/ttc`; recovery (`prochaine_relance`, `exclu_relances`); computed `montant_paye`, `avoirs_total`, `montant_du` (= TTC − paid − credits); `fichier_pdf/ubl`. **ARC24** adds an optional `condition_paiement_ref` FK→`parametres.ConditionPaiement` (source of the default `conditions_paiement` label; the TextField stays master/overridable).
- **LigneFacture** — same shape as LigneDevis (`facture` FK).
- **Paiement** — `facture` FK; `montant`, `date_paiement`, `mode` (especes/virement/cheque/carte/prelevement/autre). **SCA45** adds provider-agnostic `provider_ref` + `idempotency_key` (company-scoped uniqueness) so an external payment gateway integration can reconcile/replay-guard without a bespoke field per provider.
- **Avoir** (credit note) + **LigneAvoir** — `facture` FK (PROTECT), `client` FK; `statut` (emise/annulee); `motif`; frozen amounts; offsets the invoice's `montant_du`.
- **DevisActivity** — quote chatter (CREATION/MODIFICATION/NOTE), like LeadActivity.
- **FollowupLevel / RelanceLog** — recovery escalation tiers and per-invoice follow-up trace.
- **ShareLink** — public tokenized link (`token` unique, `devis`/`facture` FK, `expires_at`, 30-day) for WhatsApp PDF delivery without login.
- Endpoints (`/api/django/ventes/`): `devis/`, `devis-lignes/`, `bons-commande/`, `factures/`, `paiements/`, `avoirs/` ViewSets; key custom actions: `devis/{id}/proposal/` (**canonical quote PDF, sync**), `devis/{id}/generer-pdf/` (**async Celery**), `devis/{id}/telecharger-pdf`, `devis/{id}/accepter|reviser|approuver-remise|historique|noter`, `devis/{id}/convertir-bc`, `devis/{id}/generer-facture`; `bons-commande/{id}/confirmer|marquer-livre|annuler|creer-facture`; recovery (`relances/`, `balance-agee/`, `clients/{id}/releve(-pdf)/`, `factures/{id}/lettre-relance-pdf/`, `niveaux-relance/`); accounting (`journal-ventes/` .xlsx, `numerotation-audit/`); public `GET /api/django/public/document/{token}/` (tokenized PDF, no auth, no buy prices).
- **Toiture-3D devis web loop** (`/api/django/ventes/`): `devis/from-layout/` (build a Devis from a finalized roofPro11 layout + mint a proposal `ShareLink`), `devis/{id}/layout/` & `devis/{id}/roof-image/` (store the finalized layout + 3D snapshot); public tokenized proposal channel — `GET proposal/{token}/` (JSON quote data incl. `monthly_production`/`monthly_consumption` + `roof_image_url`), `POST proposal/{token}/accept/` (client e-signature → existing accept service), `GET proposal/{token}/pdf/` (client devis PDF). The website capture page (`/devis/mon-toit`) posts the enriched lead (exact bills, `ete_differente`, `raccordement` incl. `inconnu`, reverse-geocoded `adresse`/GPS) to the CRM webhook; **Meriem designs INSIDE the ERP** (authenticated React route `frontend` `/devis-design/:id`, same-origin cookie session — the roofPro11 builder is Vite-alias-imported from `apps/web`, no second login) and the client signs at the public `/proposition/<token>`. `GET /api/django/ventes/roof-config/` exposes the public MapTiler key same-origin (needs `PUBLIC_MAPTILER_KEY` in the ERP env).
- **quote_engine/** — premium PDF engine. `builder.py` maps an OS Devis → the generator data dict (only sell-side `prix_unitaire`; `prix_achat` excluded) and routes by market mode to one of three renderers: `residential/` (redesigned 3-page residential proposal), `agricole/` (4-page pompage-solaire proposal — cover/at-a-glance, étude+schéma+charts, équipement+prix+FDA+garanties, rentabilité solaire-vs-butane-vs-diesel+signature; modules `renderer/render/theme/cover/study/yield_page/economics_page/charts/schematic/economics/constants/sample_data`), and the legacy `generate_devis_premium.py` (one-page + industriel + fallback). `installations.py` = shared cover-hero photo library that picks the installation photo whose kWc is **nearest** the quote (agricole falls back to residential/industriel of similar power); photos in `assets/installations/<mode>-<kwc>.jpg`. `pricing.py`, `catalog.py`. Buy-price exclusion asserted by `apps/ventes/tests/test_quote_engine.py`; agricole engine by `test_agricole_quote.py`.
- **solar_design.py** (FG246/247/249) — electrical-engineering helpers: `string_design` (distributes N panels across the inverter MPPT inputs, checks string Vmp/Voc at cold temperature vs the MPPT/voltage window, reports the DC/AC ratio), `match_inverter` (picks a compatible catalogue inverter, classification keywords aligned with `builder.py`, never a price-less product), `optimize_orientation` (tilt/azimuth sweep via the existing PVGIS client). Pure + fully tested (`tests/test_solar_design.py`); not yet surfaced in an endpoint. **FG255** adds `ev_charger_sizing` — EV charging-station (borne de recharge VE) sizing: line current (mono 230 V / tri 400 V √3), dedicated breaker calibre, charge duration/window-fit, recommended standard borne (3.7/7.4/11/22 kW), and PV coupling (solar surplus feeds the borne first, reporting solar-covered kWh + the lifted autoconsommation rate). Pure math, input-freedom preserved, no model/endpoint/PDF change. **FG256** adds `battery_storage_sizing` — two objectives: MAX autoconsommation (store daytime surplus, capped by the re-dischargeable night load) vs BACKUP for N critical hours (usable kWh/kW from critical load × hours); returns usable + nominal kWh (÷ DoD×√round-trip), recommended pack and the binding objective. Pure math. **FG257** adds `simulate_bankable_yield` — financial-grade P50/P90: Performance Ratio = Π(1−loss) over temperature/soiling/wiring/inverter/mismatch/availability, P50 = base×PR, P90/P75 via the Gaussian lower-tail quantile (z=1.282/0.674) of an annual-variability σ (default 6 %); returns PR, loss breakdown, P50/P90/P75, optional specific yield. Pure math. **FG258** adds `hourly_self_consumption` — per-hour min(load, production) over an 8760-h (or 24-h) load curve → real autoconsommation rate, coverage rate, injected surplus, grid import; typical residential/commercial load + PV profiles as fallbacks, and `load_curve_from_xlsx` (parses a column via the already-present openpyxl). Pure math, divide-by-zero guarded. **FG259** adds `net_metering_savings` — values the injected hourly surplus (from FG258) under Moroccan net-metering (loi 13-09): compensated only up to same-tranche import × `compensation_ratio` at the tranche tariff (pointe/pleine/creuse), honours the `surplus_injecte_compense` toggle, optional annual cap + residual spill tariff. Pure math. **FG260** adds `tariff_escalation_projection` — a 20–25-year financial model: year-by-year escalated savings (ONEE escalation × module degradation), cumulative + net, simple & discounted payback year, **NPV (VAN)** and **IRR (TRI)** solved by stdlib bisection/Newton (capped iterations, `None` on non-convergence). Pure math. **FG261** adds `optimize_subscribed_power` — for C&I clients: net grid demand (load−PV) → post-PV peak → recommended subscribed power = ceil(peak×margin) (never above current) + the annual capacity-charge saving, optional kW→kVA via power factor. Pure math. **FG262** adds `module_degradation_curve` — per-year PV production factor (compound or linear, with a year-1 LID drop) confronted against manufacturer warranty floors (e.g. 90% @ yr10, 80% @ yr25), flagging the first breach year + shortfall. Pure math.
- **utils/references.py** — numbering = highest-used + 1 per company+month (savepoint + retry on races); never `count()+1`. **ARC6** relocates the algorithm to `core.numbering` (the foundation home ~15 apps import across app boundaries); this module is now a byte-identical re-export shim.
- **Sweep + performance (ARC4/5, SCA39-43/45/47/49).** **ARC5** sweeps all 21 ventes ViewSets onto `CompanyScopedModelViewSet` (unified scoping; the public `/proposal` + `ShareLink` endpoints stay explicitly excluded/documented, asserted by `test_arc5_proposal_public_access.py`). **SCA40** collapses the `par_commercial` reporting aggregate into one grouped query (ends an unbounded N+1). **SCA41** makes xlsx exports async past a row-count threshold (`ventes/export/status/` polling, 202 response, company-scoped MinIO key, pilot NTPLT29/30). **SCA43** wires `core.request_cache` under the devis-list PDF-preview path (QPERF1 landing — the previously-skipped Devis query budget test now passes). **SCA49** freezes the Devis JSON contract (`etude_params` included) with a serializer-keys snapshot test (`docs/devis-json-contract.md`). **ARC28** adds `apps/ventes/platform.py` (searchable/record/import surfaces). **ARC49/53** — see §5 frontend for the DevisList/FactureList migration onto the shared DataTable engine (parity proven, PDF/status flows untouched; see `docs/parity/ARC49-devislist-parite.md` and `ARC53-facturelist-parite.md`).
- **dgi/** (N105, silent DGI capability) — `dgi_export.py` (`build_ubl_xml`, UBL 2.1 invoice via stdlib `xml.etree`, carries seller+client ICE, per-line VAT, totals; no buy price), `dgi_validator.py` (`validate_dgi_conformity` → list of FR problem messages), `toggle.py` (`is_dgi_enabled(company)`). Armed only by `parametres.CompanyProfile.dgi_export_actif` (default **OFF**): the two facture actions `dgi-export`/`dgi-conformite` and the `dgi_export_facture` management command **404/refuse when OFF**, and the Facture model/serializer/lists are byte-identical (no field, badge, status or column added). Simpl-TVA transmission + certified e-signature remain out of scope (G14). **FG263** adds `solar_design.ppa_model(...)` — a PPA / third-party-investor financial model (pure math): applies FG262 degradation, computes investor revenue (production × PPA tariff + escalation − O&M; NPV/IRR/payback reusing FG260) and client savings (grid − PPA tariff), both perspectives. No model; quote-PDF path untouched. **FG264** adds `solar_design.pumping_cycle_yield(...)` — pure-math daily/monthly pumped-water volume by operating cycle (flat mode = byte-parity with `solar.js`; profile mode integrates débit hour-by-hour weighted by a normalized clearsky irradiation profile); curve-less pumps → None. No model; quote-PDF path untouched.

### stock — catalogue, suppliers, inventory, procurement
Product catalogue, multi-supplier sourcing, stock movements/locations, supplier POs
and returns.
- **Produit** — `company` FK; `nom`, `sku` (unique per company); `prix_vente` (sell HT); **`prix_achat`** (buy price — internal/generator-only, **never client-facing**); `quantite_stock` (canonical), `seuil_alerte`; `categorie`/`fournisseur` FK; commercial sheet (`marque`, `description`, `garantie`, `garantie_mois`, `garantie_production_mois`); pump specs (`pompe_cv`, `hmt_m`, `pompe_kw`, `tension_v`, `courbe_pompe` JSON); `is_archived`; `custom_data` JSON. **ARC27** adds an optional `unite` FK→`parametres.UniteMesure`, mirroring the existing free-text `unite_stock` (which stays master; backfilled via `backfill_unites_mesure`).
- **Categorie / Fournisseur / Marque** — referentials (Marque/`archived`). **ARC18** adds a nullable `Fournisseur.tiers` FK (migration stock/0075, `tiers_bridge.py`) mirroring identity one-way into `tiers.Tiers`. **ARC24** adds an optional `Fournisseur.condition_paiement_ref` FK→`parametres.ConditionPaiement` mirroring the existing `delai_paiement_jours`/`fin_de_mois`/`escompte_pct` fields (backfilled via `backfill_conditions_paiement`).
- N14 (reservation-aware availability): `ProduitSerializer` exposes computed `quantite_reservee`, `quantite_disponible` (= stock − active reservations from `installations.StockReservation`) and a reservation-aware low-stock flag; the legacy `is_low_stock` and `compute_besoin_materiel` are preserved (a chantier's own reservation is not double-counted).
- **MouvementStock** — `produit` FK; `type_mouvement` (entree/sortie/transfert/ajustement); `quantite_avant/apres`; `created_by`; the audit trail for every quantity change.
- **EmplacementStock / StockEmplacement / TransfertStock** — stock locations, per-location quantities (principal derived), and transfers between them.
- **PrixFournisseur** — per-supplier `prix_achat` (internal) for cheapest-sourcing.
- **BonCommandeFournisseur** + **LigneBonCommandeFournisseur** — supplier purchase orders; `statut` (brouillon/envoye/recu/annule); receipt increments stock via MouvementStock.
- **RetourFournisseur** + **LigneRetourFournisseur** — supplier returns; `statut` (brouillon/valide/annule); validation decrements stock.
- Endpoints (`/api/django/stock/`): `produits/`, `categories/`, `fournisseurs/`, `marques/`, `mouvements/` (read-only), `bons-commande-fournisseur/`, `emplacements/`, `transferts/`, `prix-fournisseurs/`, `retours-fournisseur/`.
- **ARC4** sweeps all 25 stock ViewSets onto `CompanyScopedModelViewSet`. **ARC22** adds `services.create_sous_traitant` — the entry point `gestion_projet.services.creer_sous_traitant_via_master` calls (function-local import) to create the matching `Fournisseur`(type=service)+`SousTraitantProfile` when a project subcontractor is created via the master path, without a cross-app model import. **ARC28** adds `apps/stock/platform.py`.

### installations — chantiers / field execution
Installation projects spun up once a quote is signed, through to commissioning and
closure; work orders, checklists, regulatory (law 82-21) tracking. **ARC3** sweeps
all 61 installations ViewSets onto `CompanyScopedModelViewSet` (behaviour
identical). **ARC28** adds `apps/installations/platform.py`.
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
- Endpoints (`/api/django/installations/`): `chantiers/` ViewSet + `creer-depuis-devis`, `regime-suggestion`, `{id}/historique|noter|mise-en-service|annuler|reactiver`, `{id}/checklist|cocher-checklist`, `{id}/besoin-materiel|commander-besoin` (now reports a per-SKU `reserve`); `interventions/` (F3: `?statut=`/`?type_intervention=`/`?installation=` filters + `{id}/historique|noter`); `types-intervention/`; `checklist-etapes/` (filterable `?template=`); `checklist-templates/` (N74, named template CRUD, Défaut delete-protected). Frontend route `/interventions` (F4, CHANTIERS menu): list + statut kanban (drag-to-change-status, technicien reassign). **FG303** adds `selectors.planning_camionnettes(company, debut, fin)` — a per-van calendar grouping interventions (via `Intervention.camionnette`) with a daily load, zero-capacity on FG302 indisponibilités (over-reservation visible), at the `planning-camionnettes` read action (IsAnyRole). No model. **FG304** adds **SousTraitant** — a subcontractor registry (métier/contact/ICE/RIB + `actif` archive flag, default True content-type-independent), DISTINCT from material suppliers; company+created_by server-side. ViewSet `sous-traitants/` (métier/actif filters, search). Migration installations/0020. **FG305** adds **OrdreSousTraitance** — subcontractor work orders (FK→SousTraitant FG304 + same-app chantier, race-safe `OST-` ref, prestation/montant/échéance, cycle brouillon→émis→en_cours→réceptionné→clos with lifecycle actions). ViewSet `ordres-sous-traitance/`. Migration installations/0021. **SCA34** converts `OrdreSousTraitance` into the FIRST pilot of the `core.documents.DocumentMetier` kit — a mixed conversion (redeclares `company` byte-identical, gains `created_at`/`updated_at` additively alongside the historical `date_creation`/`date_modification`, widens `statut` 20→32 chars for the abstract field, same 5 choices/default); reference format (`OST-YYYYMM-NNNN`) and the 3 existing lifecycle actions are unchanged (non-regression tested). **SCA36** converts `DemandeAchat` (models_demande_achat.py) into the kit's THIRD pilot (`LigneDocumentMetier` without a totals mixin — a purchase requisition has no money total).

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
- **ARC4** sweeps all 15 sav ViewSets onto `CompanyScopedModelViewSet`. **ARC37** makes `sav` an emitter on the `core.events` bus — `services.emettre_changement_statut_ticket` fires `ticket_resolu`/`equipement_remplace` at the guarded transition site (never a second state machine). **ARC28/29/30/33** add `apps/sav/platform.py`.

### reporting — dashboards, KPIs, insights, audit log  *(no models)*
Read-only aggregation across crm/ventes/installations/sav/stock, role-filtered.
- Endpoints (`/api/django/reporting/`): `dashboard/`, `search/`, `notifications/`, `calendar/` and `calendar/reschedule/` (agenda events + drag-reschedule), `pipeline/` (funnel value by STAGES, weighted forecast), `reports/sales|stock|service/` (+`?export=xlsx`), `insights/recurring-revenue|audit-log|job-costing|analytics|commissions/`, `archive/client/{id}/` and `archive/chantier/{id}/`. `job-costing` (margin via internal `prix_achat`) and `commissions` (sales commission per `CompanyProfile.commission_mode`) are admin-only.

### parametres — company profile, business settings, WhatsApp templates
- **CompanyProfile** (one per company) — identity + Moroccan legal IDs (`ice`, `identifiant_fiscal`, `rc`, `patente`, `cnss`, `rib`); branding (`logo_key`, `signature_key`, `couleur_principale`); `responsable_defaut_leads` FK (default lead owner); quote-gen knobs (`payment_terms` JSON, `quote_validity_days`, `tva_standard/panneaux`, ROI constants `onee_tarif_kwh`/`productible_kwh_kwc`/`rendement_global`, `remise_max_pct`, `discount_approval_threshold`, `agricole_pump_hours`); `default_installer` FK (default technician for new chantiers, N66; NULL = creator is responsable); sales commission (`commission_mode` off/pct_devis/par_kwc + `commission_valeur`, sensitive/admin-only, N99); referral toggle (`referral_enabled` bool + `referral_reward`, N98); silent DGI export master switch (`dgi_export_actif` bool, **default OFF**, N105 — arms the ventes `dgi/` capability, invisible while off); `doc_prefixes`/`doc_numbering` JSON. **SCA27** adds `site_web` (migration 0055) — the tenant's own site URL, consumed by the quote-engine residential PDF footer/legal band instead of a hardcoded founder fallback (byte-identical repli when empty).
- **TauxTVA / ConditionPaiement / UniteMesure** (ARC23/24/27, `models_taxes.py`/`models_payment_terms.py`/`models_units.py`) — per-company referentials, each a `core.TenantModel` subclass (redeclares `company` for its own `related_name`, ARC1 motif): `TauxTVA` (code/libelle/taux, Moroccan rates 20/14/10/7/0, one `defaut=True`) feeds the default rate at devis/facture creation without rewriting an already-frozen document rate; `CompanyProfile.tva_standard` (existing knob, editable in Paramètres) takes PRECEDENCE over the referential's seeded default. `ConditionPaiement` (libellé/délai jours/fin de mois/escompte %) sources the default `Facture.conditions_paiement` label and mirrors `stock.Fournisseur`'s existing numeric fields. `UniteMesure` (code/libellé) mirrors `stock.Produit.unite_stock` (which stays master). All three purely additive/declarative — absent referential falls back to prior hardcoded behaviour; seeded at signup, backfillable via `backfill_conditions_paiement`/`backfill_unites_mesure` management commands.
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
- **ARC30** switches `ALLOWED_TARGETS` from a literal set to a lazy union — `core.platform`'s `record_targets` surface, computed on first use, never at import — with the 19 historical targets migrated into 8 new `platform.py` manifests (outillage/rh/qhse/kb/ged/flotte/gestion_projet/ao) plus crm/contrats/sav/stock/ventes/installations from ARC29; a drop-in replacement (in/iteration/len identical, non-regression tested). **ARC8/26/SCA4/37** guard logic (no new bespoke `*Activity` chatter, no new `FileField` outside `records.Attachment`/`ged.Document`, no hand-rolled `company` FK model, no hand-rolled "document métier" outside the SCA30 kit) lives in `apps/records/platform_guards.py` — pure text/regex scanners against frozen baselines in `apps/records/platform_baselines/`, consumed by both `scripts/check_platform.py` (CI) and the Django test runner.

### customfields — admin-defined custom fields  *( `/api/django/custom-fields/` )*
- **CustomFieldDef** — `module` (LEAD/CLIENT/PRODUIT), `code` (slug), `type` (TEXT/NUMBER/DATE/CHOICE/BOOLEAN), `options` JSON, `obligatoire/visible_liste/actif`. Values live in each target model's `custom_data` JSON (no schema migration).
- **ARC14** adds a data-driven registry (`app_label`/`model` pairs, not a hardcoded module enum) with 2 pilots — `contrats.Contrat`, `flotte.Vehicule` (each own a `custom_data` JSON field, migrations contrats/0038 + flotte/0057). **ARC31** switches the registry's central loader to `register_from_platform_manifests()` (`CustomfieldsConfig.ready()`), reading the `customfield_models` surface off `core.platform` manifests instead of explicit `register()` calls in each app's `ready()` — the 8 native + 2 pilot models are unchanged, non-regression tested.
- Endpoints: `definitions/` ViewSet.

### tiers — cross-app party directory (ARC17, foundation app)  *( `/api/django/tiers/` )*
The Odoo `res.partner` equivalent: one identity record instead of the same name/coordinates/legal-IDs being re-entered in 5+ domain models. A FOUNDATION app (import-linter `tiers-is-a-base-layer` — domain apps depend on it, never the reverse); this run only extends the pre-existing `Tiers` model + `TiersViewSet` (`ARC17`) with bridges and read-side reconciliation.
- **Tiers** — `company` FK; identity fields (`nom`/`prenom`/`raison_sociale`, `telephone`/`whatsapp`/`email`/`adresse`/`ville`/GPS, Moroccan IDs `ice`/`rc`/`identifiant_fiscal`/`cin`/`rib`); role flags `is_client`/`is_fournisseur`/`is_partenaire`/`is_soustraitant`; `type_tiers`.
- **ARC18** adds additive nullable `tiers` FKs (string-FK `'tiers.Tiers'`) mirroring identity ONE-WAY from `crm.Client` and `stock.Fournisseur` (migrations crm/0050, stock/0075) into a `Tiers` row, via `apps/{crm,stock}/tiers_bridge.py` + `attacher_ou_creer_tiers` (dedup by company-scoped email/ICE, else create — never duplicates; also persists the role flags on the create path, a real bug fix landed mid-run). **ARC19** extends the same bridge to `compta.Partenaire` (migration compta/0108) and `rh.DossierEmploye` (migration rh/0082). **ARC56** adds the bridge to `crm.Lead` (migration crm/0051) — pre-conversion identity, so a lead already has a `Tiers` before it becomes a client. In every case the historical model stays the IDENTITY MASTER; `tiers` is a mirror only.
- **ARC20** adds read-only cross-referencing: `selectors.find_by_ice`/`find_by_email` (company-scoped lookups) and `selectors.find_duplicates` — a same-ICE/same-email cluster report (e.g. one party registered as both a Fournisseur and a Partenaire) surfaced at `GET tiers/doublons/` (admin-only, no fusion/write).
- **ARC21** is a DECISION, flag-gated OFF: `TIERS_SOURCE_ECRITURE` would make `Tiers` the write-source of identity instead of a mirror — documented in `docs/decisions/ARC21-tiers-source-ecriture.md`, not flipped in this run.
- `management/backfill_tiers` — idempotent one-off command materializing `Tiers` bridges for existing rows across the four bridged models.
- Endpoints (`/api/django/tiers/`): `tiers/` ViewSet (CRUD, company-scoped, no dedicated fine-grained permission — authenticated + scoped suffices) + `tiers/doublons/` (ARC20 report, admin-only).

### documents — field-execution PDFs  *(no models, `/api/django/documents/`)*
- `GET chantiers/{pk}/pv-reception|bon-livraison|dossier-remise|attestation/` — generates post-delivery PDFs for an installation.

### dataimport — CSV/XLSX import  *(no models, `/api/django/imports/`)*
- `POST dry-run/` (preview + column mapping), `POST commit/` (create-only, duplicates skipped), `GET export/{entity}/`. Targets: leads, clients, products.
- **ARC13** adds `parsing.py` `iter_rows(file_bytes, filename)` — a generic CSV/XLSX row reader (encoding detection utf-8/latin-1, `,`/`;` separator, normalized headers) that `services.parse_rows` now delegates to (zero behaviour change for the 6 historical FIELD_MAPS targets) and that any tabular-file reader outside `dataimport` can reuse instead of hand-rolling `csv.reader`/`openpyxl`; 3 pilot call sites migrated (rh/contrats views). **ARC32** makes `TARGETS` a lazy union of `FIELD_MAPS ∪ declared_import_specs()` — the `import_specs` surface declared by `core.platform` manifests (6 owning apps: crm already declared, stock/sav/flotte/contrats/rh extended), bridged via `export_registry.declared_import_specs()`; a set-literal non-regression test asserts the 8 historical targets plus any newly-declared target.

### contact — public contact form  *(no models, `/api/django/contact/`)*
- `POST /` — landing-page contact form; **parked by default** (returns 404 unless `CONTACT_FORM_ENABLED=1`).

### monitoring — production supervision (N50/N51/N52)  *( `/api/django/monitoring/` )*
- Models: `MonitoringConfig` (per installed-system provider + credentials, enabled), `ProductionReading` (manual/auto yield), `UnderperformanceFlag`, per-company settings (threshold % + auto-ticket toggle, default OFF).
- Swappable provider interface (registry + `NoOpProvider` default + `FusionSolarProvider` skeleton that no-ops without credentials; no new dependency).
- `configs/` (+ `providers/`, `{id}/sync-now/`), `readings/` (list + manual entry), `settings/`. Under-performance auto-creates an idempotent SAV ticket when enabled.

### notifications — unified notification engine (N75)  *( `/api/django/notifications/` )*
- Models: `Notification` (company + recipient-scoped), `NotificationPreference` (per user×event channel toggles in_app/whatsapp/email). Service `notify()` is best-effort, respects preferences, reuses existing channels (no-op when unconfigured).
- `notifications/` (+ `unread-count/`, `{id}/read/`, `read-all/`), `preferences/`. In-app bell in the header + `/parametres/notifications`.
- **ARC35** registers `EventType.CONTRAT_SIGNE` — consumes the `contrat_signe` seam on the `core.events` bus, notifying the contract's creator (fallback managers) when a contract becomes fully signed; `contrats/receivers.py` additionally logs an ARC8 chatter note + a GED deposit on the same transition (best-effort, isolated failures logged separately per hook). **ARC37** makes `sav` and `gestion_projet` bus EMITTERS (not just consumers): `sav.services.emettre_changement_statut_ticket` fires `ticket_resolu`/`equipement_remplace` (→ `EventType.SAV_TICKET_RESOLU`/`SAV_EQUIPEMENT_REMPLACE`), and a project statut change fires `projet_status_change` (→ `PROJET_STATUT_CHANGE`). **ARC38** repatriates `qhse`'s `incident_declared` onto the `core.events` bus (double emission preserved for the existing local publicapi consumer, documented choice) via `qhse/receivers.py`. **ARC39** closes 3 previously-invisible notification gaps: `MONITORING_RAPPORT` (the periodic O&M report send, `monitoring/report.py`, stays a direct `EmailMessage` to the client but now ALSO notifies internal managers via `notifications.services`) and `PAIE_RIB_DIVERGENCE` (the ARC25 RIB-mismatch check already called `notify_many(...)` with this key — it was simply never a registered `EventType`, so it silently dropped; now persisted, zero caller behaviour change) + `PAIE_RUN_PRET` (a payroll run reaching `validee` now notifies payroll managers it is ready for the transfer order/closure).

### automation — no-code rules engine (N72/N73)  *( `/api/django/automation/` )*
- Models: `AutomationRule` (trigger + action config), `AutomationRun` (every run logged), `AutomationApproval` (owner-tier approval step). Fires on the app's own `post_save` signals, best-effort (never breaks the originating save); opt-in.
- `rules/` (+ `{id}/toggle/`), `runs/`, `approvals/` (+ `approve/`, `reject/`). Paramètres → « Automatisations ».
- **ARC34** adds a generic `RECORD_STATE_CHANGE` trigger type — a registry-driven `(model, field)` whitelist read from each app's `platform.py` `automation_state_fields` manifest entry (`record_state_change_targets()`), with French validation at rule-creation time (serializer) and conditions evaluated via `core/rules.py` (FG367, never a second evaluator). 2 pilots emit through their app's `services.py` (`contrats.changer_statut` wrapper, `sav.emettre_changement_statut_ticket` at the guarded transition site) — never a direct model-signal shortcut.

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
- **ARC19** adds a nullable `Partenaire.tiers` FK (migration compta/0108, `tiers_bridge.py`) mirroring identity one-way into `tiers.Tiers`. **ARC28** adds `apps/compta/platform.py` (`kpi_providers`: échéances d'effets 30j/dépassées, consumed by ARC40's federated KPI endpoint; `agent_actions_module` — read-only effets/échéances actions).

### flotte — fleet: vehicles + rolling equipment (FLOTTE1, new app)  *( `/api/django/flotte/` )*
- **Vehicule** (`company` FK; immatriculation, marque, modèle, énergie diesel/essence/électrique/hybride, kilométrage, valeur, statut actif/maintenance/réformé) and **EnginRoulant** (`company` FK; type nacelle/groupe électrogène/chariot, compteur d'heures, marque, modèle, valeur, statut). Company-scoped ViewSets (company forced server-side, an injected body `company` is ignored) at `vehicules/`, `engins/` with énergie/statut/type filters + search. Uses only the `authentication.Company` string FK — no domain-app imports. **FLOTTE3** adds `Vehicule.emplacement_stock_id` (PositiveInteger, NOT a cross-app FK) referencing a `stock.EmplacementStock`; validated same-company + labelled via a function-local `apps.stock.selectors.get_emplacement_scoped` call (degrades to `#id`; never imports stock models). **FLOTTE6** adds **ReferentielFlotte** (editable per-company lookup lists: `domaine` type_vehicule/type_engin/energie/categorie_permis, `code`/`libelle`/`ordre`/`actif`, unique company+domaine+code) — additive (hardcoded choices untouched) — plus an idempotent `seed_referentiels_flotte` command. ViewSet `referentiels/` (`?domaine`/`?actif`). **FLOTTE5** adds **ActifFlotte** — a unified asset reference linking entretien/sinistre/document to EITHER a `Vehicule` OR an `EnginRoulant` via one model (exactly-one-target + same-company enforced in `clean()`/`save()`); company-scoped ViewSet `actifs/` (`?type_actif`) + selectors for cross-app reads. **FLOTTE13** adds fuel/energy consumption: `selectors.consommation_vehicule` computes **L/100 km and kWh/100 km** plein-to-plein from `PleinCarburant` + odometer (per-segment, divide-by-zero guarded, L vs kWh kept separate), surfaced read-only at `pleins/consommation/?vehicule=<id>` (`IsAnyRole`, 400 missing/non-int param, 404 cross-company). No migration. **FLOTTE14** adds **CarteCarburant** (fuel card: `numero`, `plafond`, optional `vehicule`/`conducteur` FK) + `selectors.anomalies_pleins` flagging four families per plein — `km_recul` (odometer decreasing), `km_saut` (>5000 km jump), `conso_aberrante` (>2× the vehicle's median baseline, reusing FLOTTE13's conso), `plafond_depasse` — at `cartes/anomalies/?vehicule=` (read action, `IsAnyRole`). ViewSet `cartes/`. **FLOTTE15** adds **PlanEntretien** (preventive maintenance via an `ActifFlotte` FK — reaches both Vehicule km and EnginRoulant heures): triggers by `intervalle_km`/`intervalle_jours`/`intervalle_heures` + last-done refs + alert margins; `selectors.plans_entretien_status` computes next-due vs current km/date/hours (due/upcoming/ok). ViewSet `plans-entretien/` (+ `echeances/` read action). **FLOTTE16** adds **EcheanceEntretien** (a generated due-maintenance record per plan: `due_le`/`due_km`/`due_heures`, `statut` a_faire/planifie/fait) + `services.generer_echeances_entretien` (idempotent — no duplicate OPEN échéance per plan; best-effort alert via `notifications.notify`) + a `manage.py generer_echeances_entretien` command. ViewSet `echeances-entretien/` (read any role, `generer` write action; POST-create disabled). Migration flotte/0014. **FLOTTE17** adds **Garage** (atelier: nom/adresse/téléphone) + **OrdreReparation** (repair order on an `ActifFlotte`: garage, description, `cout_main_oeuvre`+`cout_pieces`→derived `cout_total`, `statut` ouvert/en_cours/cloture, optional `EcheanceEntretien` link); ViewSets `garages/`, `ordres-reparation/` (+ `couts/` summary, `cloturer/` which solde the linked échéance). Migration flotte/0015. **FLOTTE18** adds **Pneumatique** (tire: position/dimension/montage/dépose/statut/coût) + **PieceFlotte** (part: désignation/réf/quantité/coût, optional OrdreReparation link); ViewSets `pneumatiques/`, `pieces/` + a per-vehicle `synthese/` summary. Migration flotte/0016. **FLOTTE19** adds **EcheanceReglementaire** — generic regulatory deadlines (visite technique/assurance/vignette/carte grise/taxe à l'essieu) on an `ActifFlotte`, with a today-injectable status (a_jour/a_renouveler/expire) and `expirantes/?within=N`; distinct from the FLOTTE16 maintenance échéances. ViewSet `echeances-reglementaires/`. Migration flotte/0017. **FLOTTE20** adds **BaremeVignette** — an editable per-company TSAV grid (énergie × CV bracket → montant, per year) + `Vehicule.puissance_fiscale` + `selectors.calcul_tsav` (electric exempt, no bracket → None) + an idempotent standard-grid seed. ViewSet `baremes-vignette/` + `vehicules/{id}/tsav/`. Migration flotte/0018. **ARC14** adds `Vehicule.custom_data` (JSON), the second `customfields` registry pilot alongside `contrats.Contrat`. **ARC28** adds `apps/flotte/platform.py`.

### ged — document management / DMS (GED1, new app)  *( `/api/django/ged/` )*
- Governed DMS reusing `records.storage` (MinIO `file_key`). **Cabinet** + **Folder** (self-FK tree with a materialized `path` recomputed in `save()`/`services.move_folder`, sub-tree prefix rewrite + cycle refusal), **Document** (lives in a Folder) + **DocumentVersion** (`file_key`, SHA-256 `checksum` for dedupe via `services.find_duplicate`, server-set incremental `version`, `uploaded_by`). All `company`-scoped (company/created_by/uploaded_by forced server-side). Endpoints: `cabinets/`, `folders/` (+ `descendants`), `documents/`, `document-versions/`. **GED4** — move (déplacement) over HTTP: `POST folders/{id}/deplacer/` (body `{parent}`, reparent/to-root, anti-cycle + cross-cabinet refusal via `services.move_folder`) and `POST documents/{id}/deplacer/` (body `{folder}`, via `services.move_document`); destination always resolved inside the caller's company (404 cross-tenant). **GED14** — inline same-origin preview: `GET document-versions/{id}/apercu/` streams the document bytes through Django (PDF/image/text → `Content-Disposition: inline`, else attachment; `X-Content-Type-Options: nosniff`), gated as a READ action (`IsAnyRole`, like list/retrieve) so read-only roles can preview. **GED17** adds a document lifecycle: `Document.statut` (**brouillon→revue→approuvé→archivé→obsolète**, default brouillon) with a guarded `LIFECYCLE_TRANSITIONS` state machine in `services.change_lifecycle_status` (illegal/unknown/same-status → `ValueError`, cross-company → `PermissionError`, `select_for_update`), exposed read-only on the serializer and advanced only via `POST documents/{id}/cycle-vie/` (responsable/admin) + a `?statut=` filter. Local GED statuses — **separate from the STAGES.py funnel**. **GED18** adds **DemandeApprobation** (review/approval workflow): `demandeur`/`approbateur`, `statut` en_attente/approuve/rejete; `services.request_review` opens a demande + moves brouillon→revue, `approve_demande`/`reject_demande` **reuse the GED17 `change_lifecycle_status`** (no duplicate state machine) to advance revue→approuvé / back to brouillon; guards duplicate-pending / already-decided / cross-company. Actions `documents/{id}/demander-revue|demandes` + ViewSet `demandes-approbation/` (`approuver`/`rejeter`). **GED19** adds **AclGed** — per-folder/document ACL: exactly-one target (folder XOR document, two CheckConstraints), principal = `utilisateur` and/or `role`, `niveau` lecture/ecriture/gestion, `herite` flag. `selectors.acl_effective` walks up the materialized `Folder.path` (document override > nearer folder > ancestor only when `herite`; most-permissive at equal scope; admin always gestion), softly wired into `documents_visible_to_user` — **backward-compatible: no ACL rows → behaviour unchanged**. Migration ged/0013. **GED20** adds **PartageGed** — a tokenized public document share (`token` via `secrets`, `expires_at`, hashed `password_hash`, `quota_max` + `telechargements` counter, `actif` kill-switch); a PUBLIC `AllowAny` endpoint `GET /api/django/ged/public/<token>/` resolves **by token only** (never trusts request company/identity), streams the document, atomic quota-conditional increment, and returns 404 (unknown/revoked) / 410 (expired/quota) / 403 (missing/wrong password). Management ViewSet `partages/` (+ `revoquer/`) is fully multi-tenant. Migration ged/0014. **GED21** adds watermarking & diffusion control: flags `Document.watermark_diffusion` + `PartageGed.watermark` and `services.apply_watermark` (image via Pillow — already a dep; PDF via PyMuPDF imported lazily, graceful degrade if absent → original bytes), wired into the GED14 `apercu` + GED20 public download (no-watermark path byte-identical). Category DEP but NO hard new dependency. Migration ged/0015. **GED22** adds **PolitiqueRetention** — document retention policies (durée de conservation + action à l'échéance, default the NON-destructive `signaler`) + `selectors.documents_echus(company, today)` (most-specific policy, today-injectable) + a `lister_documents_echus` command. Never auto-deletes passively. ViewSet `politiques-retention/` (+ `echus`). Migration ged/0016. **GED23** adds **ArchivageLegal** — legal probative-value write-once archiving (SHA-256 integrity hash, best-effort MinIO object-lock with graceful degrade — no hard dep). Once archived, app-layer immutability blocks edit/delete/new-version/move/lifecycle/check-out/check-in (all → 403, never 500); the ArchivageLegal row is create-only. ViewSet `archivages-legaux/` (+ `documents/{id}/archiver-legalement`). Migration ged/0017.

### rh — human resources: employee master (FG154, new app)  *( `/api/django/rh/` )*
- **DossierEmploye** (`company` FK; employee record). **FG155** adds the employment-contract layer: `type_contrat` (TextChoices CDI/CDD/ANAPEC/stage/intérim) + `contrat_date_debut`/`contrat_date_fin` (nullable dates; empty `date_fin` = open-ended/CDI). Company-scoped ViewSet (`employes/`) with `@action cdd-a-echeance/?within=N` (default 30 days) returning only same-company CDDs whose `contrat_date_fin` falls within the window. **FG156** adds the mandatory Moroccan payroll identity fields to `DossierEmploye`: `cnss`/`cimr`/`amo`, `situation_familiale` (célibataire/marié/divorcé/veuf), `nombre_enfants` (IR deductions) — all nullable (CIN/RIB already existed). **FG166** adds **Pointage** (clock-in/out: `company`+`employe` FK, `type_pointage` arrivée/départ/complet, server-set `heure_arrivee`/`heure_depart`, optional GPS, computed `duree_minutes`) with actions `pointages/pointager-arrivee` + `pointages/{id}/pointager-depart` (server timestamp; → COMPLET + duration once arrival is set). `IsResponsableOrAdmin`-gated. **FG172** adds the skills matrix: **Competence** (per-company catalogue, `domaine` pose_structure/raccordement_dc/raccordement_ac/mes_onduleur/pompage/soudure/autre, unique `(company, code)`) + **CompetenceEmploye** (one row per `(employe, competence)`, `niveau` 0–4 Non-acquis→Expert, server-set `evalue_par`/`evalue_le`). ViewSets `competences/`, `competences-employe/` (+ `matrice/` grid action, `?domaine`/`?niveau_min` filters), admin-gated, company forced server-side; duplicate-code → clean 400. **FG173** adds **Habilitation** — electrical authorizations (NF C 18-510: B0/H0/B1V/B2V/BR…) per employee with `organisme`, `date_obtention`, `date_validite` (expiry) and a computed `valide` flag; ViewSet `habilitations/` + `expirantes/?expire_within=N` (expiring-soon + already-expired), unique `(employe, type_habilitation)`. Distinct from the FG172 competence matrix. **FG174** adds **Certification** — the non-electrical family (travail_hauteur/harnais/caces_nacelle/secourisme_sst/conduite/autre) per employee with `organisme`, `date_validite` + computed `valide`; ViewSet `certifications/` (+ `expirantes/?expire_within=N`), unique `(employe, type_certification)`. Modelled distinctly from the FG173 electrical Habilitation. **FG175** adds `selectors.echeances_rh` — a unified expiry-alert engine unioning expiring Habilitations + Certifications + DocumentEmploye within X days (normalized `{type, employe, libelle, date_validite, jours_restants}`, `today` a param) at `echeances/?within=N`, plus a `manage.py alertes_expiration_rh` command dispatching one notification per échéance via the shared `notifications.notify` service (function-local import). No model. **FG176** adds `selectors.verifier_habilitation_requise(company, employe, type_requis)` → `{autorise, manquantes, expirees, message}` (reuses FG173's validity rule; `INTERVENTION_HABILITATIONS` map) + endpoint `employes/{id}/verifier-habilitation/?type=&intervention=`. A SOFT guard (reports; enforcement at assignment stays in installations). No model. **FG177** adds **VisiteMedicale** (occupational-health visits per employee: `date_visite`, `prochaine_visite`, `aptitude` apte/restrictions/inapte, médecin/organisme, computed `a_jour`); ViewSet `visites-medicales/` (+ `expirantes/?expire_within=N`), and feeds FG175's `echeances_rh` with a `visite_medicale` family. Migration rh/0017. **FG178** adds **EpiCatalogue** (PPE catalogue: `type_epi` casque/harnais/gants_isolants/chaussures/lunettes/autre) + **DotationEpi** (nominative issue: `employe`, `epi`, `taille`, `date_dotation`, `date_renouvellement`, `quantite`); ViewSets `epi-catalogue/`, `dotations-epi/` (+ `a-renouveler/`, `employe/`), feeds FG175. Migration rh/0018. **FG179** adds EPI life/expiry tracking: `EpiCatalogue.duree_vie_mois`/`intervalle_controle_mois` → derived `DotationEpi.date_peremption`/`date_prochain_controle` (end-of-month-clamped month math), computed `perime`/`a_controler` (`today`-injectable), endpoint `dotations-epi/a-remplacer-controler/?expire_within=N`; feeds FG175 with `epi_peremption`/`epi_controle` families. Migration rh/0019. **FG180** adds **EmargementEpi** (signed EPI-handover acknowledgement, loi 53-05 typed name + server-side IP/user-agent evidence) + `accuse_remise`/`date_accuse` on DotationEpi; `services.emarger_dotation` records it (company + acting user server-side, accusé frozen at first signature); actions `dotations-epi/{id}/emarger|emargements`. No external e-sign dep. Migration rh/0020. **FG181** adds **AccidentTravail** — workplace-accident register (race-safe `AT-` reference, date/lieu/employé/gravité/arrêt+jours/photo, CNSS declaration flags) + a CNSS CSV export (`?export=csv`). ViewSet `accidents-travail/`. Migration rh/0021. **FG182** adds **PresquAccident** — a lightweight near-miss register (race-safe `NM-` ref, lieu/gravité potentielle/mesure corrective, server-side declarant; no injured person/CNSS — distinct from FG181) + a stats-by-gravité selector. ViewSet `presqu-accidents/`. Migration rh/0022.
- **ARC19** adds a nullable `DossierEmploye.tiers` FK (migration rh/0082, `tiers_bridge.py`) mirroring identity one-way into `tiers.Tiers`. **ARC28/33/40** add `apps/rh/platform.py` — `agent_actions_module` (read-only employés + demandes de congé actions) and `kpi_providers` (effectif actif + absences en cours, consumed by the ARC40 federated KPI endpoint).

### gestion_projet — project management (PROJ1, new app)  *( `/api/django/gestion-projet/` )*
- **Projet** + **ProjetChantier** (`company`-scoped). **PROJ2** adds **ProjetLien** (`company` + `projet` FK; `type_cible` devis/facture/ticket/achat, `cible_id` target PK, cached `libelle`) linking a project to other apps' documents by **string-FK only** (no real cross-app FK). Endpoints: `projet-liens/` (CRUD, `?projet=`/`?type_cible=` filters) + `projets/{id}/liens/` (enriched). `selectors.liens_enrichis` enriches devis links via a function-local `apps.ventes.selectors.devis_card` call and degrades to the stored label otherwise (cross-app boundary respected; import-linter clean). **PROJ3** adds a project-lifecycle state machine on `Projet` (`statut` brouillon→planifie→en_cours⇄en_pause→termine, annule from any non-terminal — **independent of `STAGES.py`**, rule #2) via actions `planifier`/`demarrer`/`mettre-en-pause`/`reprendre`/`terminer`/`annuler` (illegal → 400; statut read-only outside actions) + a **ProjetActivity** transition log (`historique/`). **PROJ4** adds **PhaseProjet** (project WBS: `type_phase` etude/appro/pose/mes/reception — own enum, not STAGES; prévu/réel dates, `statut`, `avancement_pct` 0-100; unique projet+type_phase) + `services.instancier_phases_standard` (5 ordered phases, idempotent). ViewSet `phases/` + action `projets/{id}/instancier-phases`. **PROJ14** adds delay detection: `selectors.retards_projet` + `GET projets/{id}/retards/` classifying unfinished tasks and unreached milestones as `en_retard` (past due) or `a_risque` (due within `seuil_jours`, default 7) with `retard_jours` (no migration). **PROJ18** adds `selectors.plan_de_charge` — per-resource capacity (working days − Indisponibilité × hours/day) vs allocated (AffectationRessource charge, direct + team-split, pro-rated to the window) over a period with a `surcharge` flag + `utilisation_pct` (None when capacity 0); endpoint `ressources/plan-de-charge/?debut=&fin=`. No model. **PROJ19** adds `selectors.conflits_affectation` — double-booking: same `RessourceProfil` allocated to ≥2 `AffectationRessource` whose windows overlap (direct + via équipe; bonus: allocation during an Indisponibilité), at `ressources/conflits-affectation/?debut=&fin=`. No model. **PROJ20** adds `selectors.nivellement_charge` (resource levelling) — proposes moving direct affectations off over-allocated RessourceProfil to under-loaded ones without creating a PROJ19 conflict (read-only), at `ressources/nivellement-charge/`. No model. **PROJ21** adds **BudgetProjet** + **LigneBudgetProjet** (categorie materiel/main_oeuvre/sous_traitance/divers, montant_prevu, optional quantite/pu) + `selectors.budget_total` (total + par_categorie, all 4 categories present); ViewSets `budgets/`, `lignes-budget/` + a `/total/` action. Migration gestion_projet/0013. **PROJ22** adds `selectors.couts_engages_vs_reels` — committed/actual project cost vs the PROJ21 budget per category (labour from internal AffectationRessource quantized to 2dp; matériel/sous-traitance via ProjetLien with graceful degrade — no cross-app amount selector exists yet), écart + écart % (divide-by-zero guarded), at `projets/{id}/couts-engages-reels/`. No model. **ARC22** adds an additive nullable `SousTraitant.fournisseur` FK (migration gestion_projet/0042) bridging the project's local subcontractor notebook to the DC34 unified `stock.Fournisseur` master; `services.creer_sous_traitant_via_master` is the recommended creation path (calls `stock.services.create_sous_traitant` via a function-local import, never `apps.stock.models`) + `management/backfill_sous_traitant_fournisseur` for existing rows.

### qhse — quality / health / safety / environment (QHSE1, new app)  *( `/api/django/qhse/` )*
- NCR/CAPA (non-conformities + corrective/preventive actions), `company`-scoped. **QHSE2** adds the ITP (inspection & test plan) templates: **PlanInspectionModele** (code/nom/actif) + **PointControleModele** (FK plan; `phase`, `type_releve` mesure/visuel/document/essai, `hold_point` bool, `ordre`). ViewSets `plans-inspection/`, `points-controle/` (company forced server-side; a point is validated to share its plan's company → 400 otherwise). **QHSE3** adds an idempotent `seed_itp_solaire` management command (per-company or `--company`) seeding 3 solar ITP templates (résidentiel réseau / autoconsommation indus-com / pompage agricole), 7 points each, hold-points on Raccordement + Mise en service. **QHSE4** adds the APPLIED instance: **PlanInspectionChantier** (FK template `PlanInspectionModele`, `chantier_id` string-FK, `statut`) + **ReleveControle** (FK point; `valeur`, `conforme` NullBoolean, `photo_key` MinIO, `releve_par`); `services.instancier_plan_chantier` materialises one relevé per template point (idempotent, backfills). ViewSets `plans-chantier/` (+ `instancier`), `releves/`. `IsResponsableOrAdmin`-gated. **QHSE19** adds **RetourClientQualite** (client quality satisfaction): `note_satisfaction` 1–5 + `commentaire`, string-id cross-app links `chantier_id`/`client_id` (no model import), `traite` bool, `selectors.satisfaction_moyenne` + ViewSet `retours-client/` (+ `moyenne/` action, `?chantier_id`/`?traite` filters). **QHSE20** adds `selectors.iso9001_readiness` — a read-only « ISO 9001 readiness » dashboard: weighted global score + 6 criteria mapped to ISO 9001:2015 clauses (NCR closed 10.2, CAPA on-time 10.2, audits 9.2, procedures published 7.5, ITP coverage 8.5/8.6, client satisfaction 9.1.2), divide-by-zero guarded, at `iso9001-readiness/` (responsable/admin). No model. **QHSE21** adds **EvaluationRisque** (document unique d'évaluation des risques: `reference` `DUER-` race-safe, `statut` brouillon/validee/archivee, string-ref `chantier_id`) + **LigneEvaluationRisque** (poste/activité/danger, `gravite`×`probabilite` (1–5) = stored `criticite`, mesures, risque résiduel). ViewSets `evaluations-risque/` (+ `criticite/` summary), `lignes-evaluation-risque/`, role-gated. Migration qhse/0014. **QHSE22** adds the document-unique gate: `selectors.document_unique_valide(company, chantier_id)` (True iff ≥1 validated EvaluationRisque with lines) + `services.exiger_document_unique` (raises `ValidationError` — consumed by `installations` to gate the pose transition) + endpoint `evaluations-risque/document-unique-statut/?chantier_id=`. chantier_id is a string-ref (no installations import). No model. **QHSE23** adds **PermisTravail** (work permit: hauteur/consignation_elec/point_chaud/espace_confine, server-set race-safe `PT-` reference, string-ref `chantier_id`, validity dates, `valider`/`cloturer` actions). ViewSet `permis-travail/`. Migration qhse/0015. **QHSE24** adds **ConsignationLoto** — a lockout-tagout electrical-isolation record on a QHSE23 `PermisTravail` (point de consignation, cadenas/étiquette, vérif absence tension, server-set race-safe ref, statut consignée/déconsignée) with a `deconsigner` action. ViewSet `consignations-loto/`. Migration qhse/0016.
- **ARC10** makes NCR closure the pilot domain consumer of the generic `core` BPM engine: `services.demarrer_workflow_cloture_ncr` installs the FG369 `cloture_ncr` template idempotently per company and attaches a `WorkflowInstance` to the NCR via contenttypes (qhse drives the engine; `core` never imports qhse) — a two-step agent→responsable approval cycle; the rule going forward is any NEW multi-step approval uses this engine, never an ad hoc one. **ARC38** repatriates `incident_declared` onto the `core.events` bus (see notifications paragraph). **ARC28** adds `apps/qhse/platform.py`.

### contrats — contracts (CONTRAT1, new app)  *( `/api/django/contrats/` )*
- **Contrat** (`company`-scoped). **CONTRAT3** adds **PartieContrat** (`company` + `contrat` FK `related_name='parties'`; `type_partie` client/prestataire/temoin/garant/autre, `nom`, `fonction`, `email`, `telephone`, `ordre`) — the parties/signatories of a contract. ViewSet `parties/` (CRUD, `?contrat=` filter; a party is validated same-company as its contract → 400). The "≥2 signatories" rule lives in `Contrat.valider_parties()` for finalization (not enforced at create). **CONTRAT4** adds **ContratLien** (string-FK devis/lead/installation/maintenance, like ProjetLien) with `selectors.liens_enrichis` enriching via function-local `ventes`/`crm`/`installations` selectors (sav degrades to stored label). **CONTRAT5** adds `Contrat.sav_contrat_maintenance_id` (PositiveInteger, string-id to `sav.ContratMaintenance` — additive, no sav import, validation deferred until a sav selector exists). **CONTRAT6** adds `Contrat.confidentialite` (public/interne/confidentiel, default interne) — CONFIDENTIEL contracts are visible only to Administrators, gated in `get_queryset` on the authoritative `user.menu_tier` (not the unreliable `role_legacy`/Role-FK divergence). `IsResponsableOrAdmin`-gated. **CONTRAT13** adds **RegleApprobation** (approval rule by `type_contrat` and/or `montant_min`/`montant_max` bounds + `niveau_approbation`/`nombre_approbateurs`/`priorite`/`actif`) with `selectors.resoudre_regle_approbation` (most-specific wins: exact type > narrowest bounded interval > priorité > id). ViewSet `regles-approbation/` + `GET /resoudre/?montant=&type_contrat=`, company forced server-side (never body-set). **CONTRAT14** adds **EtapeApprobation** (internal approval workflow): `services.lancer_workflow_approbation` instantiates one step per the matching RegleApprobation's `nombre_approbateurs` (via the `resoudre_regle_approbation` selector), and `approuver_etape`/`rejeter_etape` advance it sequentially (out-of-order → 400, relaunch refused). Statuses are local (en_attente/approuve/rejete) and the workflow **never mutates `Contrat.statut`**. Actions `contrats/{id}/lancer-approbation|etapes-approbation|approuver-etape|rejeter-etape`. **CONTRAT15** adds **ContratActivity** (chatter/journal): auto-logs statut/confidentialité transitions + the approval-workflow steps (LOG, with `field`/`old_value`/`new_value` snapshots in TextField) plus manual notes; actions `contrats/{id}/historique` (most-recent-first timeline) + `noter`. Acting user + company always server-side. **CONTRAT16** adds **SignatureContrat** (in-app e-sign, loi 53-05 typed name): `signataire_nom` + server-side evidence (`ip_adresse`/`user_agent`/acting user), `role_signataire`, `methode`; `services.signer_contrat` records it, logs via the chatter, and flips `Contrat.statut`→signé through the existing state machine **only when all required parties (client+prestataire) have signed**. Unique `(contrat, role_signataire)`. Actions `contrats/{id}/signer|signatures`. No external e-sign provider. Migration contrats/0013. **CONTRAT17** chains an auto signé→actif: once all required parties have signed, `signer_contrat` advances the contract to `actif` via the existing state machine **iff `date_debut` is null or ≤ today** (future start stays `signe`), logged in the CONTRAT15 chatter (`today` injectable). No model. **CONTRAT18** adds **VersionContrat** (immutable contract-render versioning): server-incremented `version` (`select_for_update` max+1, never count()+1), frozen `contenu` + optional MinIO `fichier_key`; `services.creer_version` snapshots on demand + auto-snapshots on the signé transition (best-effort, CONTRAT16/17 preserved); read-only retrieval viewset `versions/` (paginated). Migration contrats/0014.
- **SCA35** adopts the `core.documents` kit's TRANSITIONS read-contract on `Contrat` WITHOUT inheriting `DocumentMetier` itself: `Contrat` keeps its own `company` FK (historical `related_name='contrats'`) and `date_creation` rather than switching to `TenantModel`'s generic accessor (no functional gain, would break the historical accessor); a read-only `TRANSITIONS`/`transitions_permises` property exposes the EXISTING `machine_etats._transitions()` state graph (CONTRAT12) in the kit's expected shape — `services.changer_statut` (the `machine_etats.changer_statut` alias) stays the one write path, still enforcing the "≥2 parties" guard the generic kit doesn't know about. **ARC14** adds `Contrat.custom_data` (JSON), the first `customfields` pilot alongside `flotte.Vehicule`. **ARC28/33/40** add `apps/contrats/platform.py` (`agent_actions_module` — read-only list + `contrat_voir`; `kpi_providers`).

### kb — knowledge base (KB1, new app)  *( `/api/django/kb/` )*
- **KbArticle** (`company`-scoped; `statut` brouillon/publie/obsolete). **KB2** adds **KbArticleVersion** (`company` + `article` FK `related_name='versions'`; server-incremented `version` via `select_for_update` — never count()+1; `titre`/`contenu`/`auteur` snapshot). Actions `articles/{id}/publier/` (statut→publie + snapshot) and `articles/{id}/nouvelle-version/`; a version is also snapshotted on every article update. Read-only `versions/` viewset (company-scoped, `?article=` filter). **KB3** adds full-text-ish search (`?search=` over titre/corps/categorie/tags) + `?categorie=`/`?tag=`/`?statut=` filters on the article viewset, applied after company scoping (no cross-tenant leak; reuses existing fields, no migration). **KB4** adds **KbArticleLien** (string-FK produit/equipement/type_intervention, like ContratLien) with selector enrichment (produit via `stock.selectors`; others degrade) + a reverse lookup `article-liens/articles/?type_cible=&cible_id=`. **KB7** adds **KbArticleAcl** (role-tier ACL, niveau lecture/edition) + **KbLecture** (read tracking). `selectors.visible_articles_qs` filters the article queryset by ACL — **backward-compatible: an article with no ACL row stays visible to all, admin always sees all**; `marquer-lu` (idempotent) + `resume-lecture` actions + ACL management viewset `article-acls/`. Migration kb/0005.

### litiges — disputes / claims (LITIGE1, new app)  *( `/api/django/litiges/` )*
- **Reclamation** (`company`-scoped; `statut` ouverte/en_traitement/resolue/rejetee). **LITIGE2** adds a server-enforced state machine (actions `prendre-en-charge`/`resoudre`/`rejeter`, illegal transitions → 400; statut read-only outside actions) plus a chatter **ReclamationActivity** (`company` + `reclamation` FK; `type` log/note, `old_value`/`new_value`/`message`/`auteur`) — auto-logs each transition and manual notes via `noter/`; timeline via `historique/`. Acting user + company always server-side. **LITIGE6** adds `selectors.tableau_bord_litiges(company, debut, fin)` — a disputes dashboard aggregating existing Reclamation data: counts by statut, total `montant_conteste`, and average resolution delay (from the `resolue` chatter log, divide-by-zero guarded → None), at `reclamations/tableau-bord/`. No model.

### core — foundation layer (events bus, signing, AI scorers, BPM engine, platform kernel)  *(`backend/django_core/core`, NOT under apps/)*
The base layer everything depends on and that imports no domain app (import-linter `core-foundation-is-a-base-layer`). Holds `events.py` (the Django-signal domain-event bus, M6), `signing`, and PURE stateless scorers fed data as input — `forecast.py` (FG361), `win_probability.py` (FG362), `churn_risk.py` (FG363), `stock_reorder.py` (FG364), `payment_delay.py` (FG365), `anomaly.py` (FG360 `AnomalyFlag`). **FG366** adds a generic **BPM/workflow engine**: `WorkflowDefinition` + `WorkflowStepDefinition` (templates), `WorkflowInstance` (runs on ANY model via a `contenttypes` GenericForeignKey — no domain import) + `WorkflowStepInstance` (per-step statut, `sla_echeance` = start + `sla_heures`, assignee). `core/workflow.py` services `demarrer_workflow`/`avancer`/`approuver_etape`/`rejeter_etape`/`escalader_etape` + selector `etapes_sla_depassees(company, now)` (now injected) + a `escalate_workflow_sla` management command. All `company`-scoped. Migration core/0002. **ARC10** makes this the SAME engine any app attaches an approval chain to, not a bespoke one per app — pilot: `qhse` NCR closure routes through `core.workflow` rather than a local approval flag. **FG367** adds `core/rules.py` — a generic multi-criteria rule engine (no model): `evaluate_condition_group(group, context)` (nested AND/OR/NOT tree; 11 leaf operators eq/ne/gt/gte/lt/lte/in/not_in/contains/startswith/exists; short-circuit; missing-field tolerant; never raises), `validate_condition_group` (structural errors), `sequential_actions` (ordered stop-on-error helper). Reusable by `apps/automation`'s rules (wiring deferred); **ARC34**'s `RECORD_STATE_CHANGE` trigger evaluates its conditions through it (never a second evaluator). **FG368** adds `core/jobs.py` + **ScheduledJobViewSet** (`/api/django/core/jobs/`) — introspects the Celery `current_app.conf.beat_schedule` (+ optional django-celery-beat) into a normalized job list, with an admin-only `jobs/run/` manual trigger (`send_task`, broker-down → 503). Jobs are global infra (no company scoping), `IsAdminRole`-gated, no new dependency. core's first URLConf (`core/urls.py`, wired into the root). **FG369** adds `core/workflow_templates.py` — a pure-data catalogue of pre-built workflow templates (relance devis, onboarding chantier, rappel garantie) + idempotent `installer_modele_workflow(company, code)` materializing the FG366 `WorkflowDefinition`/`WorkflowStepDefinition` per company, exposed via `WorkflowTemplateViewSet` (list any-auth / `installer` admin-responsable) on `core/urls.py`. No new dependency; core stays foundation.
- **Multi-tenant + viewset socle.** **ARC1** adds `core/models.py` `TenantModel` — an abstract `company` FK (→ `authentication.Company`, `related_name='%(app_label)s_%(class)s_set'`) + `TimestampedModel` (`created_at`/`updated_at`) in one mixin; the PLAYBOOK rule is every NEW multi-tenant model inherits it instead of hand-rolling the pair, and a model CONVERTED from a hand-written FK redeclares `company` in its own body to keep its historical `related_name` (never a renamed accessor). **ARC15** records the adoption census for `core.SoftDeleteModel` (FG388, `is_deleted`/`deleted_at`/`deleted_by` + `SoftDeleteManager` hiding deleted rows + `DeletionRecord` trash journal): zero business models inherit it yet — it is the acted-upon socle that the future YDATA17 soft-delete wave builds pilots on (never a second mixin). **ARC2/ARC55** add `core/viewsets.py` `CompanyScopedModelViewSet` — `TenantMixin` + `ModelViewSet` with `ScopedPermission` as the unified DEFAULT `permission_classes` (no `read_permission`/`write_permission`/`get_permissions` of its own ⇒ authenticated-only, strictly equivalent to the prior project default); the single new base a domain viewset inherits from, with named-but-unimplemented extension points reserved for pagination (YAPIC1) and filter backends (YAPIC2).
- **Numbering, PDF, audit funnel.** **ARC6** relocates the race-safe reference factory (highest-used+1 per company+period, savepoint+retry, never `count()+1`) to `core/numbering.py`; `apps/ventes/utils/references.py` becomes a byte-identical re-export shim so existing importers are untouched. **ARC11** adds `core/pdf.py` `render_pdf(html=None, *, template=None, context=None, company=None, header=False, footer=False, upload_to=None, upload_bucket=None)` — the shared WeasyPrint plumbing (lazy import, optional branded header/footer from `parametres.CompanyProfile` resolved via `apps.get_model`, optional MinIO upload) that ~45 internal PDF call sites (rh/compta/qhse/pos/paie/reporting…) converge on; rule #4 EXCLUDES `apps/ventes/quote_engine/**` and the legacy Facture PDF permanently (never migrated here). **ARC16** adds `apps/audit/recorder.py` `record_field_change` — the single funnel that writes both the `AuditLog` entry and (opt-in) the `records.Activity` chatter line for one field change in one call, replacing two independently-drifting call sites.
- **Platform registry (the "declare once, appear everywhere" kernel).** **ARC28** adds `core/platform.py` — each app declares a `PLATFORM` dict in its own `apps/<x>/platform.py` across 7 surfaces (`searchable_models`, `record_targets`, `customfield_models`, `import_specs`, `agent_actions_module`, `automation_state_fields`, `kpi_providers`); `core` collects them generically via `get_app_configs()` + `importlib` at runtime (never a static `import apps.x` — import-linter stays green), gated per company by `ModuleToggle` (extends ODX23: an OFF module vanishes from every surface at once). 15 apps now carry a `platform.py` (ao/compta/contrats/crm/flotte/ged/gestion_projet/installations/kb/outillage/qhse/rh/sav/stock/ventes). Surfaces switched to read the registry in follow-on tasks: **ARC29** `reporting/search.py` global search iterates `searchable_models` (gated); **ARC30** `records.ALLOWED_TARGETS` becomes a lazy union of `record_targets` (19 historical targets migrated in, drop-in set-identical); **ARC31** `customfields` registry loads `customfield_models` centrally in `CustomfieldsConfig.ready()`; **ARC32** `dataimport`'s `TARGETS` becomes `FIELD_MAPS ∪ import_specs`; **ARC33** `apps/agent/registry.py` auto-discovers `agent_actions_module` in `AgentConfig.ready()` (convention `register_actions()`, idempotent, gated by `ModuleToggle` in `for_user`); **ARC40** adds a federated KPI endpoint `GET reporting/kpi-federes/` resolving `kpi_providers` dotted callables into normalized `{id,label,valeur,unite?}` tiles (3 pilot providers: rh/compta/gestion_projet). **ARC41** adds `core/platform_coverage.py` — a drift matrix cross-referencing `record_targets` vs `searchable_models` (a chatter-ised-but-unsearchable model, and the inverse), baseline-frozen with a "red only on regression" policy, extending `event_coverage.py` (YEVNT7) to the declarative surfaces.
- **Document kit, request cache, misc foundation.** **SCA30-33** add `core/documents.py` — the `DocumentMetier` kit composing the ARC1/2/6/11 bricks for any NEW "header + statut + lignes + totaux + reference + PDF + chatter" document type: `DocumentMetierMeta` (a metaclass, not `__init_subclass__`, so each subclass gets its OWN `statut` field/choices instead of mutating the shared abstract field), `LigneDocumentMetier` + `TotauxDocumentMixin` (line/totals factoring), `document_viewset()` (scoping+numbering+chatter in one declaration), `render_document_pdf()` (the ARC11 PDF hook). Rule #4 EXCLUSION is permanent and named: Devis/Facture/BonCommande/Avoir never retrofit onto this kit. Pilots: `installations.OrdreSousTraitance` (SCA34), `installations.DemandeAchat` (SCA36), `contrats.Contrat` (SCA35, adopts the kit's read contract without forced renumbering). **SCA43** adds `core/request_cache.py` — a per-request `contextvar` memo for config accessors (`CompanyProfile`, tax/payment-terms referentials) that de-duplicates the ~6 identical config queries `quote_engine.build_quote_data` re-issued per Devis in a list (N+1 fix, pilot NTPLT16/QPERF1); outside a request scope (Celery, shell, tests) it degrades to calling the producer every time — byte-identical rendering. **SCA48** adds `core/benchmarking.py` `BENCHMARK_MIN_COMPANIES = 5` — the legal k-anonymity floor any cross-tenant aggregate (NTDATA46/47) must respect before publishing a stratum. **SCA20/28** add `core/signup_hooks.py` (`register_signup_hook`/`run_signup_hooks`, the same producer/subscriber pattern as the M6 event bus, best-effort per-hook isolation) + `core/services.py` `seed_tenant_branding` — seeds a neutral `TenantTheme` + default `BrandedTemplate` rows (e.g. the email signature) idempotently at company signup, alongside the pre-existing roles/catalogue seeds.

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
| `/chantiers/demandes-achat` | DemandesAchatList (FG310 réquisitions d'achat → approbation; create/soumettre/approuver/refuser) |
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
  Separator/DefinitionList/KeyValueTable (VX152 — table partagée « libellé → valeur »),
  Skeleton/EmptyState/ErrorBoundary/NotFound/Offline.
  **`ui/datatable/`** — reusable `<DataTable>` engine (TanStack Table): sort/filter/
  column-management/pagination/inline-edit/bulk-bar/saved-views/URL-persistence/
  virtualization/CSV+XLSX-export/mobile-cards. Demoed at `/ui`
  (`pages/ui/UIShowcase.jsx`, `pages/ui/DataTableDemo.jsx`). Deps (all already
  present): @radix-ui/*, @tanstack/react-table, lucide-react, sonner,
  cva/clsx/tailwind-merge. **ARC49/53** wire the FIRST two money-path list screens
  onto it — `renderRow`/`renderHeaderRow`/`tableClassName`/`tableRole`/
  `hideToolbar`/`hideMobileCards`/`hidePagination`/`expandedPanels` are ADDITIVE
  opt-in escapes (undocumented/unused ⇒ byte-identical rendering for the ~79 other
  consumer screens) added specifically so a custom `<tr>` (loading-state buttons,
  AlertDialog, independently-toggled expandable panels) can sit inside the engine's
  chrome (pagination/sort/column-mgmt/saved-views) without a rewrite: **DevisList**
  (`DevisRow`/`DevisPdfDialog` split out, parity proven in
  `docs/parity/ARC49-devislist-parite.md`, PDF/status flows untouched) and
  **FactureList** (`FactureRow` split out, `docs/parity/ARC53-facturelist-parite.md`,
  legacy facture PDF + statuts/avoirs untouched).

### Module architecture (`frontend/src/router/moduleRoutes.jsx`, `api/resource.js`, `hooks/useResource.js`, `ui/module/`)
A "coquille" module (Compta/Paie/RH/Flotte/QHSE/Contrats/Projet/GED/KB/Litiges…)
registers itself by dropping a `features/<module>/module.config.jsx` file — the
router glob-imports every one (`moduleRoutes.jsx`) with zero edits to
`router/index.jsx` per new module. **ARC48/54** migrate 8 EXISTING areas onto this
registry in this run — CRM, Stock, SAV, Ventes, Installations/Production,
Reporting, Admin, Parametres — each a new `features/<x>/module.config.jsx`
(nav + routes + role gate), shrinking `router/index.jsx` 366→201 lines. **ARC44**
adds `api/resource.js` — `makeResourceFactory(client, basePath)` (the shared
`{list,get,create,update,remove}` CRUD factory, replacing 3 near-identical local
copies in `comptaApi.js`/`flotteApi.js`/`rhApi.js`, migrated onto it) + `unwrapList()`
(normalizes the 3 real response-envelope shapes seen across the codebase — raw
array, DRF-paginated, or the common `Array.isArray(data) ? data : data?.results`
combo). **ARC45** adds `hooks/useResource.js` — a dependency-free
`useResource(fetcher, params?, options?)` hook centralizing the
loading/error/refetch/mounted-guard/stale-response-ignore cycle every screen used
to hand-roll (9 `useState` + effect boilerplate), 2 pilots migrated. **ARC46** adds
`ui/module/RecordShell.jsx` — the detail/form counterpart to `ListShell` (UX1),
composing `DetailShell` with zero duplicated markup: a `chatter` alias for the
`activity` slot, and an opt-in save-bar wired to `useOptimisticSave` (only renders
when both `record` + `onSave` are passed — otherwise behaves exactly like
`DetailShell`). **ARC43** adds `scripts/scaffold-module.mjs` (see §3) generating
the 3 files (`module.config.jsx`, `<name>Api.js` on the ARC44 factory, an example
`ListShell` page) for a brand-new module in one command. **ARC47** sweeps 24 files
onto `useHasRole`/`useHasPermission` — zero inline gating check reads
`state.auth` directly anymore (feeds the future YRBAC10 front↔back parity work).
**SCA24** adds `design/tenantTheme.js` — applies a per-company white-label theme
(`TenantTheme`, FG392: logo/primary/secondary color/display name) as CSS variables
on `<html>`, consumed by `Header.jsx` and a neutralized `Login.jsx` (no hardcoded
product name — `VITE_PRODUCT_NAME`); empty/absent theme is a no-op fallback to the
default tokens (no flash, no exception).

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

**Done (564)**

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
- `ARC1` — Modèle de base `core.TenantModel`
- `ARC2` — `CompanyScopedModelViewSet` : le viewset de base unique
- `ARC3` — Sweep TenantMixin : installations
- `ARC4` — Sweep TenantMixin : crm + sav + stock
- `ARC5` — Sweep TenantMixin : ventes (chemin de l argent, avec précaution)
- `ARC6` — Service de numérotation unique `core.numbering` (relogement fondation)
- `ARC7` — Sweep numérotation : vérifier puis migrer les boucles locales restantes
- `ARC8` — Chatter unique via `records.Activity` (le mixin `mail.thread` maison)
- `ARC9` — DECISION : convergence des 13 chatters historiques
- `ARC10` — Le moteur BPM `core` devient LE moteur d approbation (étend FG25)
- `ARC11` — Service de rendu PDF partagé `core.pdf` (hors devis)
- `ARC12` — Sweep PDF : compta + rh + paie + pos + marketing + reporting
- `ARC13` — Parser d import générique + extension `FIELD_MAPS`
- `ARC14` — Customfields sur n importe quel modèle (fin de l enum fermé)
- `ARC15` — Vérifier puis désigner `core.SoftDeleteModel` comme socle de YDATA17
- `ARC16` — Entonnoir unique de journalisation des changements (étend FG18)
- `ARC17` — App foundation `tiers` : le `res.partner` de TAQINOR
- `ARC18` — Ponts additifs Client & Fournisseur → Tiers
- `ARC19` — Ponts Tiers : Partenaire (+ survie ODX13) et DossierEmploye
- `ARC20` — Selectors de recoupement : « qui est ce tiers ? »
- `ARC21` — DECISION : Tiers devient la source d écriture de l identité
- `ARC22` — Régression DC34 : `gestion_projet.SousTraitant` re-pointé sur le master
- `ARC23` — Référentiel de taux de TVA
- `ARC24` — Référentiel conditions de paiement
- `ARC25` — Cohérence RIB paie ↔ RH (lecture seule)
- `ARC26` — Pièces jointes : élargir `records.ALLOWED_TARGETS` + convention « plus de FileField…
- `ARC27` — Référentiel unités de mesure
- `ARC28` — Le registre plateforme : `platform.py` par app (la leçon Odoo)
- `ARC29` — Recherche globale pilotée par le registre + trous immédiats
- `ARC30` — `records.ALLOWED_TARGETS` lit le registre
- `ARC31` — Cibles customfields depuis le registre
- `ARC32` — `dataimport` lit le registre
- `ARC33` — Auto-découverte des actions agent (étend Groupe R AG1-9)
- `ARC34` — Trigger automation générique `RECORD_STATE_CHANGE`
- `ARC35` — Abonner les événements contrats orphelins
- `ARC36` — Abonner facture_payee / bon_commande_cree / abonnement_monitoring_resilie
- `ARC37` — SAV et gestion_projet deviennent émetteurs du bus
- `ARC38` — Rapatrier les signaux locaux sur le bus
- `ARC39` — Couverture notifications : plus d email brut interne
- `ARC40` — KPI providers par registre pour reporting
- `ARC41` — Matrice de dérive des surfaces plateforme (étend l infra YEVNT7 existante)
- `ARC42` — Scaffolder `manage.py startapp_erp`
- `ARC43` — Scaffolder frontend : module.config + module api
- `ARC44` — Factory `resource()` partagée + unwrap de réponse unique
- `ARC45` — Hook `useResource` : le fetch/état enfin mutualisé
- `ARC46` — `RecordShell` : le pendant détail/formulaire de ListShell
- `ARC47` — Sweep `useHasPermission` (alimente YRBAC10)
- `ARC48` — Routes legacy dans le registre (là où ODX7 s arrête)
- `ARC49` — DevisList sur DataTable (dette n°1, chemin de l argent — 1/2)
- `ARC50` — Types TS générés depuis l OpenAPI (étend YAPIC5)
- `ARC51` — `docs/module-playbook.md` : le guide canonique « ajouter un module »
- `ARC52` — `scripts/check_platform.py` : les garde-fous du socle en un seul job CI
- `ARC53` — FactureList sur DataTable (chemin de l argent — 2/2, isolé d ARC49)
- `ARC54` — Routes legacy dans le registre — phase 2 (le reste, après les pilotes ARC48)
- `ARC55` — Unifier les DEUX schémas de permission viewset concurrents
- `ARC56` — Pont Tiers : crm.Lead (l identité pré-conversion)
- `DC34` — Sous-traitant : pas de master fournisseur parallèle
- `FG386` — Mode terrain hors-ligne (offline queue)
- `ODX1` — Carte des modules cible (docs/module-map.md)
- `ODX5` — Écran Paramètres → « Applications » (catalogue de modules)
- `ODX6` — Nav filtrée par modules actifs
- `ODX7` — Regrouper la nav legacy en « apps » via le registre UX1
- `ODX11` — Sortir les appels d'offres de compta → `apps/ao`
- `ODX12` — Sortir le portail client de compta → `apps/portail`
- `ODX13` — Rapatrier partenaires & territoires dans le CRM
- `ODX16` — Reloger AbonnementMonitoring (revenu récurrent)
- `ODX17` — App Facturation — étape 1 (modèles, state-only)
- `ODX19` — App Achats — étape 1 (modèles, state-only)
- `ODX23` — Gating transversal des surfaces pilotées par registre
- `QPERF1` — DevisSerializer list N+1 (query budget déféré)
- `SCA1` — `docs/BUILD_ORDER.yml` : le DAG de vagues machine-lisible
- `SCA2` — `scripts/plan_progress.py` : complétude mesurée par groupe
- `SCA3` — `plan_lanes.py` refuse les lanes hors-ordre
- `SCA4` — Conformité noyau au niveau du CODE : extension de `check_platform.py` (ARC52)
- `SCA5` — Validation CI de `BUILD_ORDER.yml`
- `SCA6` — CLAUDE.md § Workflow pointe les plan-runs sur BUILD_ORDER.yml
- `SCA7` — Baseline de capacité mesurée sur la vraie boîte
- `SCA8` — Limites de ressources conteneurs
- `SCA9` — Deuxième worker Celery dédié `interactive` (le trou YOPSB9, niveau compose)
- `SCA10` — Split Redis broker/cache + politiques d'éviction
- `SCA11` — `postgresql.conf` tuné et monté
- `SCA12` — nginx : gzip + timeout `/api/django/` aligné
- `SCA13` — Copie de sauvegarde hors-boîte (key-gated OFF)
- `SCA14` — `docs/scale-runway.md` : les étapes de découpage gâchées par métrique
- `SCA15` — Santé : mémoire Redis + profondeur des queues Celery
- `SCA16` — Dimensionnement gunicorn/celery par variables d'env
- `SCA17` — Vérifier puis documenter le module de settings prod (contradiction DEBUG)
- `SCA18` — `Company.statut` (actif/suspendu/fermeture) appliqué au JWT et à l'API
- `SCA19` — Vérifier puis appliquer le statut tenant à tous les fan-outs beat
- `SCA20` — Registre de seed hooks « on new company » (catalogue inclus)
- `SCA21` — Fermeture & purge de tenant (soft-close d'abord, purge gâchée)
- `SCA22` — Console fondateur des tenants (liste/suspendre/annoter — sans billing)
- `SCA23` — Test « jour-2 » du tenant #2 (la porte de sellability en CI)
- `SCA24` — `TenantTheme` consommé par le login et le shell applicatif
- `SCA25` — `BrandedTemplate` câblé dans les 5 emails transactionnels
- `SCA26` — Fallback neutre dans `extra_docs._logo_block` (fix règle-#4-permis)
- `SCA27` — Pied de page et liens du PDF devis pilotés par CompanyProfile
- `SCA28` — Thème et templates neutres seedés à l'inscription
- `SCA29` — Garde CI anti-branding hardcodé
- `SCA30` — `core.documents.DocumentMetier` : le bundle abstrait statut+transitions
- `SCA31` — `LigneDocumentMetier` + mixin de totaux
- `SCA32` — Factory viewset du kit : scoping + numérotation + chatter en une déclaration
- `SCA33` — Hook PDF du kit via `core.pdf` (allowlist ARC11 héritée verbatim)
- `SCA34` — Pilote 1 : `OrdreSousTraitance` sur le kit (anatomie partielle → coût marginal visible)
- `SCA35` — Pilote 2 : `Contrat` de bout en bout
- `SCA36` — Pilote 3 : `DemandeAchat` (dégradation gracieuse sans totaux)
- `SCA37` — Garde CI kit pour le code NOUVEAU
- `SCA38` — Playbook : « déclarer un document métier en 1 fichier » (étend ARC51)
- `SCA39` — Index Devis/Facture : exécution anticipée du sous-ensemble chemin-de-l'argent de…
- `SCA40` — `par_commercial` en un seul agrégat
- `SCA41` — Exports xlsx asynchrones au-delà d'un seuil (pilote nommé de NTPLT29/30)
- `SCA42` — Clés de stockage préfixées company pour les NOUVEAUX uploads (motif ERR75 généralisé)
- `SCA43` — Dé-skipper le budget requêtes Devis : cache config par requête, côté serializer…
- `SCA44` — `AbonnementMonitoring` rejoint la facturation récurrente automatique
- `SCA45` — Champs provider-agnostiques sur le chemin Paiement (le sol de QJ24/NTSUB)
- `SCA46` — `Company.benchmarking_opt_in` : le consentement comme donnée
- `SCA47` — `prix_par_kwc` dérivé sur le Devis à la création
- `SCA48` — Plancher k-anonymat encodé dans core
- `SCA49` — Contrat JSON gelé du Devis (`etude_params` inclus) : la future API partenaires sans…
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
- `XSAL15` — Vue kanban « Prévision » avec glisser-déposer entre mois
- `XSAV22` — Déflection KB sur le portail client + tracking d'usage des articles
- `XSTK18` — Bon de livraison & liste de colisage bilingues FR/AR (RTL)
- `XSTK20` — Réappro kanban / deux-bacs par scan de carte
- `YAPIC1` — Classe de pagination partagée avec plafond dur (`max_page_size`)
- `YAPIC2` — Backends de filtre/tri/recherche par défaut + garde-fou anti-`ordering_fields` manquant
- `YAPIC3` — Enveloppe d'erreur unifiée via un `EXCEPTION_HANDLER` global
- `YAPIC4` — Middleware d'identifiant de corrélation (`X-Request-Id`) sur 100 % des réponses
- `YAPIC5` — Schéma OpenAPI 3 auto-généré + docs interactives (drf-spectacular)
- `YAPIC7` — Stratégie de versionnement d'API unique et documentée (namespace de transition)
- `YAPIC8` — Livraison webhook fiable : Celery + retries exponentiels + timestamp signé + `event_id`
- `YAPIC9` — Mixin d'idempotence réutilisable pour TOUT endpoint de création interne…
- `YAPIC10` — Purge à fenêtre de rétention des clés d'idempotence (tâche Beat)
- `YAPIC11` — Sonde CI de parité de surface API par module
- `YAPIC12` — En-têtes de limitation de débit + 429 + `Retry-After` uniformisés
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
- `YOPSB11` — Sweep d'archivage des tables à forte croissance (chatter/logs/webhooks)
- `YRBAC3` — Fine-grainer les apps gatées seulement par `IsResponsableOrAdmin` …
- `YRBAC10` — Vérification de parité gating frontend↔backend (source unique + test de dérive)
- `YRBAC11` — Sweep object-level : les vues fonctionnelles/actions custom touchant un objet par ID…
- `YRBAC12` — Test générique d'isolation multi-tenant sur tous les viewsets `TenantMixin`
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
- `QW8` — Make QW4's email leg actually fire (today it's config-dead by default)
- `QX1` — [CRITICAL] `remise_globale` reaches the ENTIRE billing chain
- `QX2` — Fix the discount's OTHER consumers: founder KPIs, Meta CAPI value, DGI/UBL export
- `QX3` — [CRITICAL] Fail-closed payments: no free "PAID"
- `QX4` — [CRITICAL] De-Taqinorize the residential renderer (multi-tenant identity leak)
- `QX5` — Never print a phantom option: gate the two option cards on the real scenario
- `QX6` — Fix the strongest CTA: PDF sign QR → live proposal; real page numbers
- `QX7` — PDF numbers honesty pack
- `QX8` — Engine warm path: stop re-doing pure work per render
- `QX9` — Real e-sign evidence + the promised signed PDF (Law 43-20)
- `QX10` — OTP: honest channel + brute-force lockout
- `QX11` — Schedule ALL built-but-dead periodic jobs + a reachability guard
- `QX12` — Notification deep-links that actually land
- `QX13` — Follow-up nudges the seller can actually SEE — and that respect reality
- `QX14` — Persist `Lead.score` on webhook leads → auto-MQL finally fires for the #1 source
- `QX15` — Callback SLA clock measures the right thing
- `QX16` — « Jamais perdre un lead » becomes operational: payload replay surface
- `QX17` — Client dedup by phone, not just email
- `QX18` — Arabic doesn't die at the document layer
- `QX19` — Auto-quote consumes everything the client already told us
- `QX20` — A solar quote must contain solar equipment
- `QX21` — Atomic quote save (create AND edit) + honest PDF progress
- `QX22` — Truthful « Envoyé » on the WhatsApp path
- `QX23` — Mode-switch guard + persisted margin snapshot
- `QX24` — `etude_params` can't silently go stale
- `QX25` — Call-ready rows everywhere
- `QX26` — Structured loss reasons — learn WHY quotes die
- `QX27` — Action-row sanity + typed-interaction rendering
- `QX28` — Lead readiness chips — surface what the website already captured
- `QX29` — « Relances du jour » — the devis work-queue
- `QX30` — Engagement-triggered follow-up engine
- `QX31` — Speed-to-lead: minutes, not hours
- `QX32` — Unified lead timeline
- `QX33` — Deposit at the moment of signature (degraded no-PSP mode now)
- `QX34` — Post-sign status endpoint `/suivi/<token>` (ERP half; web page = WEB_PLAN WJ115)
- `QX35` — Wire the parrainage promise
- `QX36` — Inbound email: replies stop landing in a void
- `QX37` — One webhook surface
- `QX38` — One canonical solar-math model
- `QX39` — Honest 25-year cashflow
- `QX40` — Pompage electrical + data sanity
- `QX41` — Public hardening pack
- `QX42` — PII retention for the raw intake copies
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
- `VX48` — [BUG iOS] Ouvrir tous les PDF via un onglet pré-ouvert AVANT l'await (le bug le plus…
- `VX49` — Détection réelle du blocage popup + gestion d'erreur des ~49 téléchargements blob
- `VX50` — [BUG mobile] `data-label` sur les tables financières + garde CI anti-régression
- `VX51` — Le champ focalisé ne passe plus SOUS le clavier iOS (VisualViewport)
- `VX52` — Les avertissements de conformité en `title=` seul deviennent visibles au tactile
- `VX53` — Balayage compat mécanique : garde `@media (hover:hover)`, dvh d'AgentChat…
- `VX54` — [BUG données] Fin de la troncature silencieuse à 100 lignes + pagination PARALLÈLE…
- `VX55` — Discipline réseau : timeout axios global + annulation des requêtes obsolètes
- `VX56` — NotificationBell cesse de poller un onglet caché
- `VX57` — Alléger le chemin froid : `sora.css` hors du rendu-bloquant + CopilotPanel paresseux
- `VX58` — Préchargement au survol/focus des destinations chaudes de la Sidebar (adaptatif)
- `VX59` — Nom de chunk roof-tool indépendant de la machine (hygiène du gate YHARD7)
- `VX60` — Gate e2e « comptes justes » : >100 enregistrements affichés en entier (sans polluer la…
- `VX61` — [GATED: new dep web-vitals ~2KB] [backend-collection] Mesure des Web Vitals RÉELS…
- `VX62` — Brouillon auto + garde de sortie sur DevisGenerator (le formulaire à 20 minutes)
- `VX63` — Fin du JSON brut à l'écran : erreurs lisibles + Réessayer sur DevisList (et chasse aux…
- `VX64` — Error boundaries sur les routes nues : `/ui`, `/`, `/login` et TOUTES les pages…
- `VX65` — Le lien profond survit à la connexion : `?next=` au redirect `/login`
- `VX66` — Filet anti-double-soumission au niveau du composant `Button`
- `VX67` — Déployer `StateBlock` (chargement/vide/erreur + Réessayer) sur les 5 listes principales
- `VX68` — Le gate e2e apprend Safari et l'iPad : projets WebKit + tablet dans Playwright
- `VX69` — Contrat de zoom : e2e à 150 % et 200 % sur les flux clés (WCAG 1.4.10)
- `VX70` — Régression visuelle ÉTROITE : ÉTENDRE `e2e/visual.spec.js` (il existe déjà) à 6-8…
- `VX71` — [GATED: new dev-dep @axe-core/playwright] a11y dynamique : scans axe DANS les parcours…
- `VX72` — [DECISION] [GATED: new dep @sentry/react] Sentry frontend en no-op DSN-gaté, miroir du…
- `VX73` — Le sélecteur de langue arrête de mentir + label `Ctrl K` sur Windows
- `VX74` — [DECISION — ZÉRO build] L'arabe : interface complète RTL, ou langue de documents…
- `VX75` — Un seul format d'argent et de date : consolidation des ~90 contournements de…
- `VX76` — [backend-template] Emails de marque : wrapper HTML unique sur les DEUX points d'envoi
- `VX77` — Compression photo côté client AVANT upload sur les 3 écrans de capture terrain
- `VX78` — Brancher le 404 déjà construit : fini la redirection silencieuse vers le dashboard
- `VX79` — Liens internes partageables : `?id=` + « Copier le lien » pour devis, chantier et…
- `VX80` — Feuille de style d'impression + bouton « Imprimer » sur devis-liste, factures et…
- `VX81` — Noms de fichiers d'export XLSX/CSV horodatés (parité avec le fix PDF QD2)
- `VX82` — Chrome navigateur vivant : titre d'onglet par page + préfixe `(N)` non-lus +…
- `VX83` — « Ma file » : LA file de travail unique (décision d'architecture — flagship)
- `VX84` — [BUG] La cloche arrête de compter le travail des AUTRES
- `VX85` — Plomberie de la file dans `apps/records` : snooze non destructif + mentions cliquables…
- `VX86` — Signal ambiant sur les approbations (badge sidebar + carte Dashboard + rangée cloche)
- `VX87` — Journal d'appel en un geste : ressusciter `log-interaction` (mort UI) + relance dans le…
- `VX88` — Ma journée branche la tournée géo-optimisée déjà payée
- `VX89` — LeadForm : Escape + autofocus via `ResponsiveDialog` (et corriger le « done » menteur…
- `VX90` — « Ajouter ligne » déplace enfin le focus sur la nouvelle ligne (devis + facture)
- `VX91` — Convergence FactureForm : `ProduitPicker` + « + Nouveau client »
- `VX92` — « Enregistrer et créer un autre » + mort du `window.alert` du paiement
- `VX93` — Défauts intelligents : propriétaire = moi, dernière ville, dernière TVA, dernier mode…
- `VX94` — Enter-pour-ajouter + refocus sur les panneaux de capture terrain (surface 100 % pouces)
- `VX95` — Câbler `toastWithUndo` (0 appelant) : archivage leads + drop kanban en avant
- `VX96` — Le delete de lead cesse d'être « irréversible » : `Lead` premier adoptant du…
- `VX97` — La facture (et le devis) montrent enfin « qui a fait quoi »
- `VX98` — Confiance en 2 clics : lien « Historique » sur la fiche + puce de fraîcheur
- `VX100` — Fin de la décision à l'aveugle : montant + lien source dans l'inbox d'approbations
- `VX101` — [BUG AUTH] Seul le bon tier peut approuver
- `VX102` — (CONSTRUIT 2026-07-09, demande directe du fondateur) Le terrain peut CRÉER une…
- `VX103` — Écran de délégation d'absence (backend XKB3 complet, 0 UI)
- `VX104` — Le superviseur se règle à la création de l'employé
- `VX105` — Finir l'écran du technicien : statut + onglets persistants + honnêteté hors-ligne des…
- `VX106` — La signature client sort de sa tombe (FG69 : modèle + endpoint + offline construits, 0…
- `VX107` — Résumé client en lecture seule dans le flux terrain (garantie + dernier ticket SAV)
- `VX108` — `tel:`/`wa.me` partout où un numéro s'affiche (pas seulement les leads)
- `VX109` — Importer fournisseurs & équipements : brancher les cibles orphelines d'ExcelImport
- `VX110` — « Copier » vers le presse-papiers depuis toute liste DataTable (TSV → colle propre dans…
- `VX111` — [PRÉMISSE CORRIGÉE] Lier une pièce jointe à une NOTE du chatter lead + la remonter dans…
- `VX112` — La balance âgée cesse d'être un cul-de-sac : drill-down « Relancer » vers les relances…
- `VX113` — FiscalitePage : sélecteur d'exercice (fin de la saisie « Exercice (ID) » à la main)
- `VX114` — Fin des `window.prompt()` de l'« Export comptable » : vrai sélecteur de dates
- `VX115` — Les KPI du cockpit comptable pointent vers l'écran d'ACTION, + un index « Où trouver…
- `VX116` — Relance en lot : proposer « Consigner + aperçu WhatsApp » sans jamais auto-envoyer
- `VX118` — [BUG] CANDIDAT BUILD : surfaces fantômes — deux features entières rendent sans (@lane…
- `VX119` — [BUG] CANDIDAT BUILD : outbox terrain — une op rejetée par le serveur disparaît en
- `VX120` — [BUG] [GATED: génération QR] La graine TOTP 2FA est exfiltrée vers
- `VX121` — Zéro couleur hors token : le sweep CSS et JS, avec garde CI
- `VX122` — La voix typographique : police de marque par défaut + échelle F121 réellement (@lane…
- `VX123` — Plancher d'accessibilité visuelle : anneau de focus token-isé consommé partout +…
- `VX124` — Craft-physics pack : les 4 micro-détails qui signent un produit investi
- `VX126` — L'état PRESSÉ propagé : 12+ contrôles cessent d'être morts au clic, courbes
- `VX127` — L'état LECTURE-SEULE existe enfin + EditableCell honnête (pending/erreur (@lane…
- `VX128` — Comboboxes audibles : `aria-activedescendant` câblé (0 occurrence dans tout le (@lane…
- `VX129` — Primitives complétées : menus pro, Textarea adulte, Progress indéterminé, Avatar…
- `VX130` — Le toast devient un objet de marque : tokens, icônes lucide, durées motion, (@lane…
- `VX131` — Des états qui disent vrai : `tone` sur EmptyState, CTA sur les listes principales…
- `VX132` — L'attente premium : shimmer, crossfade, squelettes honnêtes, anti-scintillement (@lane…
- `VX133` — Grammaire directionnelle des surfaces : chaque overlay entre par où il vit
- `VX134` — Chorégraphie de coquille : ⌘K, sidebar, route, badge, thème — cinq (@lane…
- `VX135` — Mouvement piloté par JS rendu accessible + FLIP des listes
- `VX136` — Scroll-timeline natif : reveal des cockpits + progression des formulaires (@lane…
- `VX137` — La table de lignes du générateur sort du HTML brut
- `VX138` — L'aperçu de simulation devient un comparateur : Sans/Avec groupés, chiffres héros…
- `VX139` — Deux éditeurs de devis, UNE présentation des totaux et UNE devise
- `VX140` — DevisList : 14 boutons deviennent 4 + un menu, la cellule Référence respire
- `VX141` — `DocumentStageTrack` : le statut devient un parcours
- `VX142` — FactureList & cousins : toolbar rangée, action recommandée trouvable, primitives
- `VX143` — LeadForm refondu : un seul langage de formulaire dans le module CRM
- `VX144` — Hiérarchie de lecture des cartes et vues CRM : montrer moins pour dire plus
- `VX145` — Barres d'action CRM : groupes, risque perçu, désencombrement
- `VX146` — `/calendrier` rejoint le design system : un seul calendrier mensuel dans l'app
- `VX147` — LeadsPage et ses 4 vues parlent enfin le même langage d'état
- `VX148` — Le kit `ui/charts` réellement adopté : fin des 3 thèmes recopiés et des rapports…
- `VX149` — Un seul accent de statut : `StatusAccentCard` + le terrain + le micro-pack ops
- `VX150` — Le login re-signé : la première impression cesse de contredire le système
- `VX152` — Fin des moteurs de table parallèles : GED, Admin, ClientDetail, OCR
- `VX155` — La gradation émotionnelle du funnel : signé célébré, envoyé/payé reconnus
- `VX156` — Une voix avec un point de vue + le moment d'accueil
- `VX157` — Le langage d'impact : icônes métier unifiées + la fierté ambiante du parc
- `VX158` — Confiance et clarté : les valeurs suggérées se déclarent, le jargon fiscal se (@lane…
- `VX160` — Outbox terrain : une op rejetée par le serveur ne disparaît plus en silence
- `VX163` — Infrastructure thunk : annulation `{signal}` + dé-duplication en vol des 4 thunks…
- `VX166` — Câbler `confirmLeaveIfDirty` chez les 7 adoptants existants + `CrudDialog` (8 (@lane…
- `VX167` — LeadForm : dirty-tracking + garde de fermeture (le modal n°1 — complément direct…
- `VX168` — Balayage garde+autoFocus : 13 dialogues flotte/gestion_projet + (@lane: frontend/forms)
- `VX169` — `useBlocker` : garde de navigation IN-APP des formulaires route-level
- `VX170` — `useFormSafety` : LA primitive qui rend le mauvais câblage impossible (incl
- `VX171` — Vérité des erreurs de champ : serveur → champ (`useServerFieldErrors`) + erreurs…
- `VX172` — (déjà présent)
- `VX173` — (déjà présent)
- `VX174` — (déjà présent)
- `VX175` — (déjà présent)
- `VX176` — (déjà présent)
- `VX177` — (déjà présent)
- `VX178` — `backdrop-blur` retiré des surfaces sticky scrollées (jank WebKit du (@lane…
- `VX179` — (déjà présent)
- `VX180` — `DataTable`/`ListShell` : le seuil documenté (768px) n'est PAS le seuil réel (@lane…
- `VX181` — (déjà présent)
- `VX182` — 7 modales fait-main hors LeadForm : le même défaut que VX89 corrige, sur 7 (@lane…
- `VX183` — Densité par palier : colonnes kanban 272px fixes (pipeline à moitié invisible sur
- `VX184` — Un seul comportement mobile pour les lignes-produit : `data-label` + bascule
- `VX185` — (déjà présent)
- `VX186` — (déjà présent)
- `VX187` — (déjà présent)
- `VX188` — DevisGenerator : extraire `DevisLineRow` mémoïsé + `startTransition` sur les
- `VX189` — (déjà présent)
- `VX190` — Garde CI WebKit étendue : exports blob + sticky DataTable + standalone
- `VX191` — `useActiveDescendant` : brancher `aria-activedescendant` sur les 10 (@lane…
- `VX192` — Kanbans accessibles : `StageMover` porté au kanban chantiers + `KeyboardSensor` +
- `VX193` — LeadForm : labels associés + validation client annoncée ; AppointmentBooker : (@lane…
- `VX194` — (déjà présent)
- `VX195` — Carte Leaflet accessible : rôle + liste clavier parallèle
- `VX196` — Régions live : chat/chatter annoncés + scroll clavier + erreurs toast en
- `VX197` — (déjà présent)
- `VX199` — [BACKEND] `IsResponsableOrAdmin` : n'importe quelle permission d'écriture ouvre
- `VX204` — Fin des veuves silencieuses : ChatterWidget, ActivitiesPanel, Journal +
- `VX206` — Socle local d'observabilité : `console.error` des boundaries + (@lane: frontend/data —…
- `VX209` — [BACKEND] `notify()` devient humain : heures calmes, bon event de mention, (@lane…
- `VX213` — [BACKEND] Notifier les handoffs AVAL : chantier créé, chantier réassigné,
- `VX215` — Boucle de retour « pris en charge » : l'émetteur sait que le ballon est (@lane…
- `VX216` — Rendre les seams VISIBLES des deux côtés : divergence devis↔chantier, ticket
- `VX218` — Le handoff se voit aussi CÔTÉ RÉCEPTION et DANS LE TEMPS : « Nouveau pour moi » +
- `VX219` — « Mes chiffres » : le vendeur `normal` voit ENFIN sa propre performance
- `VX220` — ⌘K atterrit sur le RECORD (pas la liste) + créations au clavier
- `VX221` — Le score de lead dit enfin POURQUOI (tooltip de raisons + tri)
- `VX222` — « Relancer ce devis » : le pendant devis de la relance facture
- `VX223` — [BACKEND léger] Actions de carte en 2 clics : « ✗ Perdu (motif) », file (@lane…
- `VX224` — La session de qualification en rafale : ◀▶ prev/next, « créer un autre », (@lane…
- `VX225` — La raison de blocage de statut cesse d'être jetée à la poubelle (@lane: frontend/ios —…
- `VX226` — (déjà présent)
- `VX227` — Les coutures chantier↔intervention : pont Demande d'achat, photos reliées,
- `VX228` — Le rapprochement bancaire ligne-à-ligne : le contrat d'interaction complet
- `VX229` — `CrudDialog` apprend le Combobox : fin des champs FK « (ID) » tapés à la main
- `VX230` — Encaisser LÀ où on chasse l'impayé + total « reste à encaisser » visible
- `VX231` — La navigation finance atterrit sur la CIBLE : `?facture=`, lien client, onglet
- `VX232` — Les états financiers deviennent LISIBLES : noms réels, tableaux exploitables, (@lane…
- `VX234` — [BACKEND] L'audit des rôles au grain de la PERMISSION + garde de
- `VX236` — Fin des culs-de-sac de pilotage : équipes cliquables, Journal deep-linké, seuils…
- `VX237` — Collage intelligent : le presse-papiers du monde réel entre proprement
- `VX238` — Primitives « mains rapides » : Segmented au clavier, Tab-qui-choisit, focus (@lane…
- `VX239` — Doublons : prévenir à la création CLIENT + le geste de FUSION
- `VX240` — Parité mécanique des formulaires : autofocus, mémoire des défauts, (@lane…
- `VX242` — [BACKEND+AUTH — noter au DONE LOG] Sécurité de session digne de confiance : le
- `VX243` — [BACKEND] La confiance au niveau du DOSSIER : « archivé par X », historique de (@lane…
- `VX244` — Le poids de la confirmation devient proportionné au dégât : primitive (@lane…
- `VX246` — Queue de couverture interop : compression POD/chatter, Imprimer RH/contrats,
- `VX247` — [GATED-founder pour le volet (e)] Onboarding→maîtrise : le guide connaît le (@lane…
- `VX248` — Raccourcis d'ACTION à une touche sur le record focalisé + cheatsheet filtrée par…
- `VX249` — Le langage des micro-états : pulse de champ sauvé, valeur « suggérée », pastille…
- `VX250` — La fiche annonce son état et ses relations : « en attente de… » + compteurs (@lane…
- `VX251` — Le dispatch au glisser-déposer : réaffecter une intervention comme

**Open — to build (23)**

- `ERR114` — [ventes/quote_engine]
- `N100` — Build out multi-tenant operation on the existing tenant_id foundation (strict…
- `N101` — Tenant administration console (manage tenants/plans/usage/support) + self-serve signup…
- `N102` — After the modules above are built, update the master project document + PLAN + DONE log…
- `ODX14` — Rapatrier la config de vente dans ventes
- `ODX15` — Sortir les notes de frais de compta → `apps/frais`
- `ODX18` — App Facturation — étape 2 (vues/urls/recouvrement/frontend)
- `ODX20` — App Achats — étape 2 (vues/urls/flux stock/frontend)
- `ODX22` — Étendre les contrats import-linter au graphe post-découpage
- `XACC12` — Position fiscale des tiers (exonérations avec attestation)
- `XPOS19` — E-commerce transactionnel : checkout direct des petits articles (panier → paiement CMI…
- `XSAL5` — Lignes optionnelles sur devis + ajout self-service dans la proposition web
- `XSAL14` — Lignes de section et de note dans le devis
- `YAPIC6` — Contrôle CI « schéma OpenAPI sans avertissement » + snapshot versionné
- `YCASH5` — Annulation d'une facture après acompte : réversion de l'acompte tracée mais AUCUNE…
- `YHARD1` — Chiffrement au repos des champs sensibles (mixin `EncryptedField` réutilisable…
- `YHARD9` — Fondation analytique : séparation du store OLTP (réplica de lecture, optionnel) +…
- `YRBAC13` — Fine-grainer les @action de compta/marketing (dette YRBAC4 rehaussée batch-4)
- `QXG1` — [GATED: founder account]
- `QXG2` — [GATED: founder account]
- `QXG3` — [GATED: founder data]
- `QXG4` — [GATED: founder content]
- `QXG5` — [GATED: founder ops check, 10 minutes]

**Blocked — awaiting founder decision (5)**

- `XKB35` — Appels audio/vidéo internes (huddles)
- `QC2` — [GATED: paid — Inforisk/Charika API] Registry-backed autocomplete (the true Odoo-style…
- `S21` — Real-time WebSocket upgrade (Django Channels)
- `VX203` — Contrat d'erreur UNIQUE : fin du double-toast (35 pages), `getApiError` (@lane…
- `VX252` — [BACKEND additif léger] Maîtrise personnelle : milestones non comparatifs, KPI
