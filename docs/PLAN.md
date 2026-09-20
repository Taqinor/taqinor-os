# Taqinor OS — Build Plan & Progress

This file is the **single source of truth** for the Taqinor OS build backlog and the
**memory between Claude Code sessions**. Each run first works through EVERY unchecked task in `docs/PLAN2.md` (if that file exists) from top to bottom — not just one — ticking each off as it lands, then does the same for this file, and only stops when both queues are clear (or a usage limit pauses it, in which case re-running resumes from the next unchecked task). The next session reads this file and
continues. Nothing relies on the agent's own memory — the file on disk is the memory.
Each run partitions its unchecked tasks into independent **lanes** (grouped by which real
source files they write) and builds them with **up to 8 concurrent worktree subagents**, in
waves of 8 when there are more lanes — see HOW TO RUN.

---

## HOW TO RUN · STANDING RULES · ALREADY LIVE → `docs/PLAN_HOWTO.md`

The run procedure (HOW TO RUN), the STANDING RULES every task obeys, and the
ALREADY-LIVE “do not rebuild” inventory now live in **`docs/PLAN_HOWTO.md`** —
read it once per session before draining this queue. The five non-negotiable
rules (#1–#5) live in `CLAUDE.md`; `docs/LANE_BRIEF.md` is the per-lane-agent
distillate. This file keeps the BUILD QUEUE + DONE LOG below.

## BUILD QUEUE (do top-down — highest value first)

### EVERY CATEGORY IS BUILDABLE (auto-gating OFF, 2026-06-21)

> **Founder standing consent (2026-06-21, Reda).** The former auto-skip of
> `ARCH` / `DECISION` / `AUTH` / `COST` / `GALLERY` / `DEP` is **LIFTED**. A run builds tasks of
> EVERY category without pausing — including brand-new greenfield modules (compta, paie, flotte,
> qhse, contrats, gestion_projet, ged, kb, litiges), auth changes, new paid/external dependencies,
> additive **and** destructive-but-revertable migrations, and new architecture. `scripts/plan_lanes.py`
> reflects this in code (`GATED_KEYWORDS` is empty → it reports `0 gated`). The planner still LABELS
> each category, and the run **NOTES in the DONE LOG** whenever a built task introduced a new
> paid/external dependency, an auth change, a destructive migration, or a brand-new architectural
> component — so you keep visibility. The five non-negotiable rules (#1–#5) are unaffected and still
> bind (rule #5's `tos_risk/` process still applies to any scraping task). Every change must stay
> revertable via `git revert` and pass the four required CI checks before merge.

A task is held back ONLY by a genuine **external prerequisite a run cannot satisfy** — a credential /
secret / account / real-world data **you** must provide, or a conflict with a non-negotiable rule.
Those are parked under **NEEDS YOUR INPUT** (below) each with a recommendation; everything else
builds. (Historical note: the long list of "specifically pre-approved" deps — Leaflet, Celery Beat,
Brevo, the additive columns, ONEE seeds, the stock-reserve rule, the silent DGI export, the devis
literal→setting wiring — all shipped; they are now just instances of the general rule above.)


---

## BUILD QUEUE — Parité « best ERP du monde » + découpage modules façon Odoo — audit 2026-07-02 (ODX1–ODX23 + groupes X*)

Provenance : audit multi-agents du 2026-07-02 (62 agents — recherche web par domaine sur Odoo 18/19,
SAP Business One, Dynamics 365 Business Central, NetSuite, ERPNext + leaders spécialisés de chaque
domaine ; gap-analysis contre le code réel ET tous les plans — tout ce qui figure dans
PLAN/PLAN2/DONE/ERROR_PLAN, coché ou non, a été compté comme déjà couvert ; revue adversariale
anti-doublon par domaine, dédoublonnage inter-domaines, puis critique de complétude). **489 tâches**
= les vrais manques restants sur ~1 100 features benchmarkées (l'écrasante majorité est déjà couverte
par l'existant + les plans). Règles du lot : contenu/fonctionnel uniquement (le câblage frontend
fonctionnel est inclus ; le design visuel viendra dans le chantier UI dédié) ; tout est
additif / multi-tenant / frontières services-selectors ; intégrations externes key-gated OFF par
défaut ; `/proposal` et le moteur premium intouchés. Les tags (DECISION)/(COST) marquent les appels
du fondateur mais restent dans la file. **Groupe ODX en premier** (découpage modules façon Odoo — ses
étapes -1/-2 sont ordonnées par (@after)) ; les groupes X* sont indépendants par app et
lane-drainables comme d'habitude.

### Groupe ODX — Découpage en modules façon Odoo (ODX1–ODX23)

Constats vérifiés dans le repo (2026-07-02) :
- `apps/compta/models.py` = monolithe de 6 084 lignes / ~85 classes : la vraie compta CGNC y cohabite avec le marketing (Campagne, SequenceRelance…), les appels d'offres (AppelOffre…), le portail client (ComptePortailClient…), les partenaires/territoires, la config de vente (CodePromotion, ModeleDevis…), les notes de frais.
- La facturation (Facture/Paiement/Avoir/relances) vit dans `ventes` ; les achats fournisseurs (BCF/réceptions/FactureFournisseur/PaiementFournisseur/retours/PrixFournisseur) vivent dans `stock` — Odoo les sépare (Invoicing, Purchase).
- FG391 existe : `core.ModuleToggle` + `core/feature_flags.module_actif` + ViewSet `core/module-toggles/` — mais AUCUN manifest par app, aucune fermeture de dépendances, aucun usage frontend (grep = 0 appel).
- UX1 a livré le registre frontend `router/moduleRoutes.jsx` + `features/<module>/module.config.jsx` — mais seulement pour les 10 modules récents ; STOCK/CRM/VENTES/CHANTIERS/SAV… restent codés en dur dans `Sidebar.jsx`.
- La maintenance interne a déjà ses foyers Odoo-conformes (flotte = PlanEntretien/EcheanceEntretien, outillage = statut EN_REPARATION) ; `sav` = Helpdesk+Repairs (équipements CLIENTS + O&M) — pas de move nécessaire, à documenter dans la carte.

- [ ] ODX14 — **Rapatrier la config de vente dans ventes.** Déplacer de compta vers `apps/ventes` (chez Odoo : Sales — quotation templates, pricelists, online quotes) : CodePromotion, ModeleDevis, SessionGuidedSelling, DemandeApprobationConfig, ECatalogue, DocumentProposition, SimulationPublique, SimulationFinancement, OffreFinancement, LigneIncitation, EcheancierPaiement, TranchePaiement (FG209–221) — recette state-only ODX9 (db_table figé, SeparateDatabaseAndState, shims compta), puis vues/urls sous `/api/django/ventes/…` avec anciennes routes compta conservées. Invariants : `/proposal` reste l'unique voie PDF devis (les DocumentProposition sont des ANNEXES du même moteur, pas un second chemin) ; l'e-catalogue n'expose JAMAIS `prix_achat` ; toute numérotation reste sur `apps/ventes/utils/references.py`. **Done =** données intactes, doubles URLs vertes, tests devis/PDF existants verts (pages counts inchangés), garde no-prix_achat testée, import-linter vert. Files: apps/ventes/ + migrations, apps/compta/{models,urls}.py + migrations, tests. (ARCH) (@lane: backend/ventes) (@after: ODX2) (@blocked: app-split state-only migration needs live makemigrations verification — no docker/DB in this lane, local Django 6.x incompatible with pinned 5.1.4; matches 2026-07-11 precedent 'ODX14/17-22 — à valider en DB')
- [ ] ODX18 — **App Facturation — étape 2 (vues/urls/recouvrement/frontend).** Déplacer vers `apps/facturation` les serializers/views/services du périmètre ODX17 + le recouvrement (relances, balance âgée, relevés clients, lettres de relance PDF, niveaux de relance) et l'export UBL/DGI facture : nouvelles routes `/api/django/facturation/…`, les routes historiques `/api/django/ventes/factures|paiements|avoirs|relances|balance-agee|niveaux-relance/…` RESTENT servies à l'identique (mêmes ViewSets inclus sous les deux préfixes) — aucun client cassé, `/api/django/public/document/{token}/` intouché. Le flux devis→facture reste orchestré par `apps/facturation/services.py` appelé depuis l'action ventes existante (frontière services). Frontend : `features/facturation/` + `module.config.jsx` (section « Facturation » : Factures, Avoirs, Encaissements, Recouvrement) extraite de la section VENTES — regroupement fonctionnel only. **Done =** doubles URLs byte-identiques (tests des deux préfixes), génération facture depuis devis verte, PDFs facture inchangés, nav montre Ventes et Facturation comme deux modules, e2e vertes. Files: apps/facturation/{views,serializers,services,urls}.py, apps/ventes/{views,urls}.py, frontend/src/features/facturation/, tests. (ARCH) (@lane: backend/facturation) (@after: ODX17) (@blocked: app-split state-only migration needs live makemigrations verification — no docker/DB in this lane, local Django 6.x incompatible with pinned 5.1.4; matches 2026-07-11 precedent 'ODX14/17-22 — à valider en DB')
- [ ] ODX20 — **App Achats — étape 2 (vues/urls/flux stock/frontend).** Déplacer les serializers/views/services/urls du périmètre ODX19 vers `apps/achats` : nouvelles routes `/api/django/achats/…`, routes historiques `/api/django/stock/bons-commande-fournisseur|receptions-fournisseur|factures-fournisseur|retours-fournisseur|prix-fournisseurs/…` conservées à l'identique. Les MOUVEMENTS DE STOCK à la réception/au retour passent désormais par une fonction de `apps/stock/services.py` (entrée/sortie + MouvementStock) appelée par achats — jamais d'import direct des modèles stock (hors shims transitoires) ; l'intégration compta (écritures fournisseurs) continue via `apps/compta/services.py`. Frontend : `features/achats/` + `module.config.jsx` (section « Achats » : Commandes fournisseur, Réceptions, Factures fournisseur, Retours, Import OCR) extraite de la section STOCK — fonctionnel only, hooks e2e préservés. **Done =** doubles URLs vertes, réception incrémente le stock à l'identique (test bout-en-bout), nav montre Stock et Achats séparés, import-linter vert, e2e vertes. Files: apps/achats/{views,serializers,services,urls}.py, apps/stock/{views,urls,services}.py, frontend/src/features/achats/, tests. (ARCH) (@lane: backend/achats) (@after: ODX19) (@blocked: app-split state-only migration needs live makemigrations verification — no docker/DB in this lane, local Django 6.x incompatible with pinned 5.1.4; matches 2026-07-11 precedent 'ODX14/17-22 — à valider en DB')
- [ ] ODX22 — **Étendre les contrats import-linter au graphe post-découpage.** Mettre à jour `backend/django_core/.importlinter` : ajouter les nouvelles apps (marketing, ao, portail, frais, facturation, achats) au contrat d'indépendance mutuelle des MODÈLES de domaine (string-FKs only, pin M1), garder `core-foundation-is-a-base-layer` intact, et ajouter un contrat « les apps satellites n'importent pas les views d'une autre app ». Retirer les shims de ré-export transitoires devenus sans référence (grep prouvant zéro appelant avant chaque retrait — étape par étape, révertable). **Done =** `lint-imports` vert avec les nouveaux contrats, chaque shim retiré n'a plus aucun référent (grep committé dans le message), tests complets verts. Files: backend/django_core/.importlinter, apps/{compta,ventes,stock}/models.py (retrait shims). (ROUTINE) (@lane: backend/core) (@after: ODX10, ODX18, ODX20) (@blocked: app-split state-only migration needs live makemigrations verification — no docker/DB in this lane, local Django 6.x incompatible with pinned 5.1.4; matches 2026-07-11 precedent 'ODX14/17-22 — à valider en DB')

Notes de non-duplication (vérifié dans docs/PLAN.md, docs/PLAN2.md, docs/DONE.md) :
- FG391 (ModuleToggle + feature_flags) est DÉJÀ construit — ODX2/3 n'ajoutent que le manifest, le catalogue et la fermeture de dépendances manquants.
- UX1–47 ont DÉJÀ livré le registre frontend `module.config.jsx` + les écrans des 10 modules récents — ODX7 ne fait qu'y raccorder les sections legacy hardcodées ; aucun écran n'est reconstruit.
- WR12 (flags métier dans Paramètres) et QC1/QC2 (autocomplete sociétés) sont distincts et non dupliqués.
- DC34 (refonte AP sous-traitant) interagit avec ODX19/20 — noté dans ODX19.
- La maintenance interne (Odoo Maintenance) existe déjà dans flotte (PlanEntretien/EcheanceEntretien/OrdreReparation) et outillage — aucun move nécessaire, documenté dans ODX1.

### Groupe XACC — Comptabilité & Finance (compta : TVA, trésorerie, budgets, immobilisations, multi-devise, fiscalité DGI)

Le socle compta est très complet (COMPTA1–40, FG107–153, DC20–DC30, écrans UX2–UX9, G14 gaté pour la télétransmission DGI) — les tâches ci-dessous couvrent UNIQUEMENT les vrais manques identifiés face au benchmark best-in-world (Odoo/SAP B1/BC/NetSuite/Sage 100 Maroc), du plus prioritaire au moins prioritaire.

- [ ] XACC12 — **Position fiscale des tiers (exonérations avec attestation).** Aucune substitution de taxe par tiers : ajouter une position fiscale sur Client/Fournisseur (assujetti par défaut / exonéré avec attestation n°+date de validité / hors champ / zone franche) qui substitue automatiquement le taux TVA (0 %) et les comptes à la création du devis/facture, avec mention légale d'exonération sur le document et attestation jointe (records). Très pertinent : clients agricoles (pompage solaire exonéré) et exports. **Done =** un client exonéré (attestation valide) produit une facture à TVA 0 % avec la mention, attestation expirée → warning et taux normal, la compta mappe sur les bons comptes via `MappingCompte`, tests. Files: apps/crm + apps/ventes (champ + application), apps/compta (mapping), migrations additives. (SCHEMA) (@lane: backend/ventes) (@blocked: money/GL path needs DB validation + founder decision — matches 2026-07-11 precedent 'XACC12/XPOS19/YCASH5/XPLT20 — validation DB + décision fondateur')

### Groupe XPOS — Point de vente comptoir & commerce client (accessoires solaires)

Combler l'écart « vente au comptoir » : aujourd'hui vendre un simple câble/disjoncteur au magasin exige la chaîne devis→BC→facture ; rien n'encaisse en 30 secondes, aucune grille tarifaire revendeur, pas de retour client re-stocké ni de n° série capturé à la vente comptoir. Tout réutilise l'existant (Facture classique sans devis, Paiement multi-modes, `compta.Caisse`/`ClotureCaisse` FG124, étiquettes QR N20, e-catalogue FG214, portail FG228, PaymentLink FG53, timbre fiscal FG144) — jamais de doublon.

- [ ] XPOS19 — **E-commerce transactionnel : checkout direct des petits articles (panier → paiement CMI → commande → expédition).** Aujourd'hui le parcours public s'arrête à « Demander un devis » (XPOS14 : e-catalogue FG214 → lead + devis brouillon) : aucun achat direct des petits articles vendables (MC4, coffrets, chauffe-eau). Côté ERP UNIQUEMENT (la vitrine/panier web = tâche WEB_PLAN séparée, à queuer là-bas) : modèle `CommandeEnLigne` + lignes dans `apps/ventes` (company résolue par le token du catalogue FG214, client rapproché/créé via `crm.services` — pattern `resolve_client_for_lead`, jamais de doublon ; seuls les produits marqués `vendable_en_ligne`, bool additif sur `stock.Produit`, avec stock disponible) ; paiement par la passerelle CMI EXISTANTE et gated (FG370/FG53 : `apps/ventes/payments/providers.py` `HostedGatewayProvider`/NoOp + `PaymentLink` — réutiliser `create_session`/`verify_webhook`, AUCUN nouveau code passerelle) ; à la confirmation vérifiée du webhook : `Facture` via `ventes.services` (référence via `utils/references.py`, jamais count()+1) + `Paiement` rapproché, décrément stock via `stock.services`, puis suivi d'expédition `a_preparer → expediee → livree` (n° de suivi transporteur libre) avec notifications client aux transitions ; sans clé CMI = endpoint checkout 404/no-op (le catalogue reste devis-only) ; jamais `prix_achat` dans aucune réponse publique. **Done =** un panier public payé (webhook mock) crée commande+facture+paiement+mouvement stock et traverse les 3 statuts d'expédition avec notifications, webhook non vérifié → aucune commande, sans clé → no-op, produit non `vendable_en_ligne` ou stock insuffisant refusé, tests multi-tenant + test d'absence de prix d'achat. Files: `apps/ventes/models.py` (+migration additive) + `public_views.py` + `services.py`, `apps/stock/models.py` (`vendable_en_ligne` +migration additive) + `services.py`, tests. (DECISION) (COST) (@lane: backend/ventes) (@after: XPOS14) (@blocked: money/GL path needs DB validation + founder decision — matches 2026-07-11 precedent 'XACC12/XPOS19/YCASH5/XPLT20 — validation DB + décision fondateur')

### Groupe XKB — Connaissance & collaboration interne (base de connaissances, chat d'équipe, approbations, annonces, to-dos)

Combler les vrais manques face à Odoo Knowledge/Discuss/Approvals, Notion, Confluence et Slack — en s'appuyant sur l'existant (apps/kb KB1–KB7, apps/chat Groupe S1–S20, apps/notifications N75/N92/BSP, records.Activity + « Mes activités », chatter FG7, approbations éparses contrats/GED/automation/achats, agent AG1–AG12) sans jamais le reconstruire.

- [BLOCKED: décision fondateur requise — construire (WebRTC auto-hébergé) vs s'en tenir aux memos vocaux + WhatsApp] XKB35 — **Appels audio/vidéo internes (huddles).** Appels voix/vidéo WebRTC depuis un DM/canal (partage d'écran, invitation par lien) — grosse brique d'infra temps réel du même ordre que S21 (signalisation, TURN/STUN, sessions collantes au déploiement) pour une petite équipe interne qui a déjà les memos vocaux transcrits et WhatsApp. À trancher par le fondateur : construire (auto-hébergé, pas de service payant par défaut) ou s'en tenir aux memos vocaux + WhatsApp. **Done =** décision fondateur documentée ; si oui, spec dédiée puis découpage en tâches. Files: n/a (décision). (DECISION) (@lane: backend/chat)

## BUILD QUEUE — Round 2 : câblage bout-en-bout, bonnes pratiques mondiales & parité profonde Odoo — audit 2026-07-03 (groupes Y* / Z*)

Provenance : 2ᵉ audit multi-agents (2026-07-03, ~90 agents sur Opus/Fable — 29 lanes recherche→audit→revue
adversariale + dédoublonnage inter-lanes + critique de complétude). Là où le round 1 (section ci-dessus,
ODX*/X*) faisait l'inventaire des **features** manquantes, ce round attaque ce qu'une checklist ne voit pas :
comment les processus sont **CÂBLÉS** de bout en bout, les **bonnes pratiques d'ingénierie** de niveau
mondial, et la parité Odoo à **grain fin** (rapports, assistants, réglages, actions planifiées, documents
imprimables). Chaque tâche cite le code RÉEL vérifié (modèle/service/événement/fichier). **336 tâches** =
les vrais manques après recoupement contre tout l'existant ET tous les plans (round 1 inclus). Mêmes règles :
additif / multi-tenant / frontières services-selectors / bus d'événements `core/events.py` / intégrations
key-gated OFF / `/proposal` intouché ; (DECISION)/(COST)/(AUTH)/(DEP) marquent les appels du fondateur.

**Trois axes + un durcissement :**
- **Axe A — Câblage bout-en-bout (Y\*, 10 processus)** : Lead-to-Cash, Procure-to-Pay, Install-to-Service,
  Record-to-Report (exhaustivité comptable), Hire-to-Retire, Intégrité des flux de stock, Machines d'états
  des documents, Marketing-to-Lead, Revenu récurrent, Couverture bus d'événements/notifications/approbations/audit.
- **Axe B — Bonnes pratiques mondiales (Y\*, 5 lanes)** : couverture RBAC (matrice endpoint×rôle + masquage
  champ-niveau), cohérence & complétude de l'API (OpenAPI/idempotence/webhooks), ops/perf/résilience
  (sauvegardes testées, N+1, Celery), stratégie de test (e2e par processus), patterns d'intégrité des données.
- **Axe C — Parité profonde Odoo (Z\*, 14 apps)** : le grain fin que le round 1 a manqué, app par app.
- **Durcissement plateforme & gouvernance IA (YHARD)** : les 11 écarts transverses trouvés par la critique
  de complétude (chiffrement au repos, i18n du contenu, reconstruction temporelle, secrets/rotation,
  observabilité/SLO, perf & a11y du front ERP, staging anonymisé, déploiement sans coupure, audit/rollback IA).


### — Axe A : câblage des processus bout-en-bout —

### Groupe YCASH — Câblage Lead-to-Cash

Le socle Lead-to-Cash est déjà remarquablement câblé de bout en bout via le bus `core/events.py` (M6) : la capture (webhook site, OCR FG106, simulateur, dédup QJ8, SLA première réponse FG28, round-robin XSAL11 planifié), le funnel STAGES.py (chatter LeadActivity, expiration/hygiène QJ5, scoring FG27/QJ6), le devis (générateur, révisions, variantes, `resolve_client_for_lead`), l'acceptation (`devis_accepted` → CRM avance le lead SIGNED, `installations` auto-crée le chantier ET réserve le stock `seed_reservations`), l'envoi (`devis_sent` → QUOTE_SENT), le refus (`devis_refused` → COLD/perdu), la réception (`_apply_reception_handover` FG70 → équipements au parc SAV + garantie), la facturation par tranches (échéancier avec cumul « déjà facturé », acompte/solde, avoirs, PV de livraison FG51), l'encaissement (FG53 `PaymentLink` → `Paiement` rapproché, liens CMI gated FG370), les relances cadencées (`relance_reminders` beat, reset sur solde U10), et la comptabilité GL (FG107-153 : auto-écritures, TVA, clôture de période, lettrage, FEC). Les situations de travaux BTP (XPRJ4), le blocage crédit dur (XFAC28), l'e-invoicing DGI sortant (XFAC29), la TVA sur encaissement (XACC1) et les écritures de stock (XACC6) sont déjà planifiés. Les écarts ci-dessous sont les rares hand-offs RÉELLEMENT non câblés que j'ai vérifiés dans le code — surtout deux systèmes de paiement/écriture parallèles jamais reliés à leur consommateur.


- [ ] YCASH5 — **Annulation d'une facture après acompte : réversion de l'acompte tracée mais AUCUNE contre-passation comptable ni ré-ouverture du chantier.** FG50 (fait) gère déjà, à l'annulation d'une facture, le transfert/remboursement de l'acompte (re-pointe le `Paiement` ou pose un `Paiement` négatif de contre-passation + chatter) — MAIS le blueprint « cancellation cascade » et « refund flow » exige que (a) l'écriture d'acompte (4191/avance) soit contre-passée au GL et (b) le chantier lié soit ré-ouvert/annulé avec motif. Vérifié : l'annulation `views/facture.py::annuler` ne poste aucune écriture (dépend de YCASH1) et n'émet aucun événement vers `installations` (le chantier auto-créé sur `devis_accepted` reste en l'état). Après YCASH1, abonner l'annulation de facture (nouvel événement `facture_annulee` sur `core/events.py`) côté compta (contre-passation idempotente de l'écriture d'acompte, avance 4191 soldée) ET côté installations (récepteur qui, si le chantier n'a pas démarré, le repasse en attente/annulé avec motif chatter — garde : jamais si des équipements sont déjà posés). **Done =** annuler une facture d'acompte réglée contre-passe l'écriture d'avance (équilibrée, idempotente, verrou de période respecté) et, si le chantier n'a pas démarré, le ré-ouvre avec un motif au chatter ; un chantier déjà en pose n'est pas touché ; toggle compta OFF = pas d'écriture ; tests. Files: `core/events.py`, `apps/ventes/views/facture.py` (émission), `apps/compta/receivers.py`, `apps/installations/receivers.py`. (ARCH) (@after: YLEDG1) (@lane: backend/ventes) (@blocked: money/GL path needs DB validation + founder decision — matches 2026-07-11 precedent 'XACC12/XPOS19/YCASH5/XPLT20 — validation DB + décision fondateur')

## GROUPE AUD5 — Audit ERP R5 : SAV, contrats, qualité & imports
Base : campagne d'audit L3 round 5 (SAV, contrats, QHSE, litiges/ESG, monitoring) + ronde bis machines d'états/imports — 25 constats confirmés (triage_table) + 5 gaps critiques de la critique adversariale (R5-CRIT-A/B/C, R5-MAJ-D, R5-MAJ-E), dédupliqués (R5-CTR-4=R5-3, QHSE-R5-2=R5-4 → une tâche chacun) ; R5-LE-3 (litiges jamais alimenté depuis sav) n'est PAS baké par le fondateur, volontairement absent de ce groupe.
NE PAS FAIRE : facturation contrats/SAV = AUD149-151/181-184 (déjà tâchée, ne pas retoucher) ; réactivation échéanciers = AUD182 (AUD501 filtre le sélecteur MRR, ne touche pas la réactivation) ; coexistence ContratMaintenance/contrats.Contrat documentée, ne pas fusionner les deux modèles ; ingestion automatique des alarmes onduleur/connecteurs fournisseurs = backlog NTNRG assumé, jamais une tâche ici ; backlogs NTSRV/NTFSM non repris ; machines d'états chantier/intervention déjà tâchées en AUD316/AUD317, seulement référencées si besoin.
Décisions fondateur bakées (ne pas re-demander) : D11 (PDF contrat = étiquetage honnête du niveau de signature OTP simple loi 43-20 ; signature QUALIFIÉE DGSSI = option GATÉE, coût prestataire) ; D13 03/09/2026 (expiration ContratMaintenance = date_debut+duree_mois avec grâce 30j) ; Resiliation.ANNULEE/EFFECTIVE → câbler une vraie annulation dans la fenêtre de préavis (besoin métier, pas retirer les états morts) ; QHSE-R5-3+R5-6+R5-1 rejoignent le beat transverse AUD231 (crossref, pas de doublon, seul le câblage au-delà du beat se taske ici) ; VENTES-DEVIS coordonné avec la vague QJR400-432 au drain (frontière acceptation, ne pas double-tasker) ; dataimport leads coordonné avec la campagne CRM en cours (frontière apps/crm/services).
Ordre : argent/légal contrats et ventes d'abord (machine d'états, expiration, PDF, garantie, avenant), puis légal/sécurité structurel (DELETE, admin, machines d'états qhse/sav + garde CI transverse opus), puis dataimport comme source d'écriture de masse, puis SAV/monitoring, puis litiges/ESG/beat/perf N+1 en dernier.
- [ ] AUD504 — [GATED: coût prestataire — décision fondateur] Intégration signature QUALIFIÉE DGSSI en option pour les contrats à enjeu. En complément d'AUD503 (étiquetage honnête du niveau OTP simple actuel), certains contrats à fort enjeu justifieraient une signature électronique qualifiée (DGSSI, loi 43-20) plutôt que la preuve OTP simple d'aujourd'hui — implique un prestataire tiers payant, à trancher par le fondateur (devis, choix de prestataire) avant tout développement. Done = N/A tant que non dégagé par le fondateur — ne rien construire, seulement documenter le point de décision. Files: apps/contrats/services.py, apps/contrats/models.py (SignatureContrat.methode). (@lane: backend/contrats, model: sonnet)

## NEEDS YOUR INPUT — ungated; each waits on something only you can give (with my recommendation)

**Auto-gating is OFF (2026-06-21).** Per your standing consent, NO task is gated by category any
more — `ARCH` / `AUTH` / `COST` / `DECISION` / `GALLERY` / `DEP` are now just **labels**, never a
stop-and-ask, and `scripts/plan_lanes.py` schedules them like any other task (the planner reports
`0 gated` by design). The only things that still hold a task are the five non-negotiable rules
(#1–#5) and a genuine **external prerequisite a run cannot satisfy** — a credential / account /
paid service **you** must provide, real-world data only you have, or a taste / strategic call that
is yours to make.

The items below are no longer auto-skipped; they are parked here **with my recommendation** because
each genuinely needs you. To act on one: provide the credential/data, or say "build it" and a run
ships the safe **no-op scaffold now** (it lights up the moment the key/data lands). Effort tags:
S/M/L. The cross-app safety rules (#1–#5, multi-tenant, buy-prices-never-client-facing) still bind.

- **G1 — Real email sending** (devis/facture/relance by email). **UNGATED 2026-06-18 → BUILD QUEUE
  (N87/N88, Brevo).** Provider chosen = **Brevo** (SDK or SMTP), key from settings/env, no-op
  without a key; pre-approved (see the PRE-APPROVED block). No longer a blocker.
- **G2 — WhatsApp Business Cloud API** (true auto-send + PDF *attached*, message templates).
  Needs: Meta Business **verification** + a WhatsApp Cloud API **access token** + **phone-number
  ID** + an **approved template name**. Today WhatsApp is link-only (`wa.me`, manual tap) and works
  well. **MY RECOMMENDATION: defer until you provision the Meta token — the manual link covers the
  daily need; don't pre-build a dead scaffold. FG207 (inbound WhatsApp → lead) is the SAME Meta
  credential — bundle the two.** Effort M once unblocked. Use Meta Cloud API directly (skip BSP
  resellers/their markup). Verification can take days–weeks; that, not code, is the bottleneck.
- **G3 — Full document visual redesign** (facture + bon de commande; the premium **devis** engine
  `generate_devis_premium.py` / `/proposal` stays OFF-LIMITS per rule #4). The facture/BC still use
  the plainer legacy WeasyPrint templates, which undercut the brand next to the premium devis.
  Needs: a **gallery review** (taste) — I generate 2–3 redesigned facture/BC drafts in the premium
  visual vocabulary, you pick one. **MY RECOMMENDATION: worth doing — clients see the facture as
  often as the devis. Say the word and I'll produce the gallery; keep `PDF_ENGINE=legacy` working.**
  Effort M. (N106 relances + handover sheet already shipped in the premium language.)
- **G5 — Supplier procurement module** (bons de commande fournisseur, goods-in/receiving, supplier
  invoices / accounts payable). **UNGATED 2026-06-20 → BUILD QUEUE (G5, under « Procurement & inventory »).** Approved as a dedicated multi-session module.
- **G6 — Stock auto-decrement on installation** (a chantier consumes its equipment from stock).
  **UNGATED 2026-06-18 → folded into BUILD QUEUE N14.** The exact rule is now confirmed and
  pre-approved: **reserve on chantier create → decrement on « Installé » → release on
  cancel/close** (see the PRE-APPROVED block). No longer a blocker.
- **G7 — Quote e-signature (certified third-party).** Needs your choice of a **paid e-signature
  provider**. The lightweight in-OS acceptance already shipped (Q7: tokenized public accept stamps
  name + timestamp + IP, flips the devis to `accepte`, renders on the PDF) — that is legally
  adequate for residential/SME solar quotes and effectively satisfies FG229. **MY RECOMMENDATION:
  defer — only add a certified provider (Yousign > DocuSign for an MA/FR SME: cheaper, EU-based,
  simpler API) when a high-ticket contract or dispute actually needs eIDAS-grade signing.** Effort M.
- **G8 — 2FA / SSO.** 2FA shipped (N96, opt-in TOTP). **SSO** still needs your choice of an IdP
  (Google Workspace / Microsoft Entra / Okta) + that tenant's app credentials. **MY RECOMMENDATION:
  defer — opt-in 2FA already covers the security need for a small internal team; add SSO only if you
  standardise on one IdP (and then it pairs naturally with G12 if that IdP is Microsoft).** Effort M.
- **G9 — Automation engine / scheduler.** **UNGATED 2026-06-18 → BUILD QUEUE (G9).** Decision made:
  **Celery Beat (in-app)**, two scheduled jobs in Africa/Casablanca time — scheduled relance
  reminders + a daily facture-overdue check (overdue = échéance passed & not fully paid → « En
  retard »; default échéance = issue + 30 days). Pre-approved (see the PRE-APPROVED block). The
  broader no-code automation engine (N72/N73) and n8n workflows stay separate.
- **G10 — CAPI send** (Meta Conversions API, sends `SignedQuote` on Signé, EMQ ≥ 7.0). Capture half
  shipped (fbclid + UTM on the lead + apps/web). The send hook is a stub at two known sites
  (`apps/crm/services.py` SIGNED transition). Needs your **Meta pixel/dataset access token**. CAPI
  itself is **free** (ad-attribution signal, not messaging). **MY RECOMMENDATION: low effort to
  finish (M) and the hook + hashable lead data already exist — provide the pixel token and I'll wire
  the SHA-256-hashed event POST; or build the no-op scaffold now (it's nearly free risk).**
- **G11 — Chatbot / AI assistant → LLM provider.** The chatbot (NL→SQL agent) AND the cross-app AI
  assistant (PLAN2 Group R, already built) run on a multi-provider factory (`SQL_AGENT_PROVIDER` =
  `groq` | `openai` | `claude` | `ollama`). **MY RECOMMENDATION: stay on the default — Groq's FREE
  tier (`llama-3.3-70b-versatile`) — it already works and costs nothing.** The SAME free Groq key
  also powers FG352 (RAG synthesis), FG353 (summarise), FG354 (reply drafts), and the assistant's
  voice (Groq Whisper). `openai`/`claude` are **optional PAID quality upgrades** (better
  reasoning/French, only if Groq's quality/limits prove insufficient); `ollama` is **fully free but
  self-hosted** (needs your own GPU/CPU) if you ever outgrow Groq's free rate limits. FG358 photo QA
  needs a **vision** model — reuse the already-configured Zhipu key, not a new one. **No new paid key
  is required.** FG357 voice and FG361 forecasting aren't LLM-gated at all (free faster-whisper /
  `statsmodels`).
- **💰 AI running costs (verified in code, 2026-06-21).** The whole AI stack runs **FREE by design** —
  no paid key required. Groq's free tier powers the chatbot, the Group R assistant, and assistant
  voice (`whisper-large-v3`, same Groq key); embeddings (`sentence-transformers all-MiniLM-L6-v2`)
  and chat voice memos (`faster-whisper`) are **local/free**; pgvector is free. The **only
  externally-billed AI is OCR via Zhipu GLM** (`ZHIPU_API_KEY`, `glm-4.5v`/`glm-4.7`) — usage-billed
  but very cheap, with free trial credits, and a **pure no-op without a key** (OCR just doesn't run;
  nothing else is affected). `claude`/`openai` are **optional paid quality upgrades**; `ollama` is a
  **free self-hosted fallback** if Groq's free rate limits are ever hit.
- **G12 — Microsoft 365** (Entra ID, Outlook, OneDrive, Teams). Needs an **Entra app registration**
  in your tenant (client id/secret + admin-consented Graph scopes). **MY RECOMMENDATION: confirm
  your team's mail/file stack first — if you live in Google Workspace, skip M365 and prioritise
  Google (calendar/email) instead; only invest here (L) if the team actually runs on M365.**
- **G13 — Import the 619 real Odoo leads.** The idempotent importer is **already built**
  (`apps/crm/management/commands/import_odoo_leads.py` — 3-way match, fills empty fields only, maps
  to `STAGES.py`, `--dry-run`). Needs a **fresh Odoo export of `crm.lead`** (CSV/JSON, holds PII →
  **never committed**, gitignored). **MY RECOMMENDATION: zero dev work — export `crm.lead`, then run
  `manage.py import_odoo_leads <file> --company <slug> --dry-run` first, then for real.** Effort S to
  operate.
- **G14 — DGI e-invoicing readiness (Morocco).** Mandatory ~**Jan 2027** for businesses with CA >
  500k DH — likely Taqinor's wave. **PARTIAL UNGATE 2026-06-18 → BUILD QUEUE (N105):** only the
  **silent, backend-only local capability** was ungated — on-demand **UBL 2.1 / CII** XML export
  (recipient ICE on every line) + a conformity validator, both behind a master toggle that defaults
  OFF and is completely invisible while off. **STILL GATED here** (blocked on the unpublished DGI
  implementing decree — no API spec exists yet, not a decision of Reda's): the **Simpl-TVA portal
  transmission** and the **certified e-signature** (a PDF is explicitly NOT compliant; clearance
  needs the live DGI platform). CONFIRMED — the silent local UBL/XML export already shipped (N105).
  **MY RECOMMENDATION: WAIT for the spec — there is no published Simpl-TVA API to code against, so
  building the portal half now would be guesswork. Mandatory ~Jan 2027 gives runway; the local UBL
  export already positions the data model. Revisit the day DGI publishes the technical spec.** This
  one is blocked by an external SPEC, not by anything you can provide today. Effort L when it lands.
- **G15 — Arabic / Darija UI** (full interface localization, not just message templates). **UNGATED
  2026-06-20 → BUILD QUEUE (N93/N94)** — i18n framework approved. SEQUENCING: run as the FINAL step of
  the UI/UX overhaul (after the component restyle); not prioritized — pull forward only on Reda's
  explicit instruction.
- **G16 — Heavy modularity options.** (a) extract a bounded context into its own deployable service
  (like `fastapi_ia`), (b) per-app pip packaging. **MY RECOMMENDATION: KEEP DEFERRED.** M1–M7
  already delivered the modularity benefit (CI-enforced decoupled boundaries + the `core/events.py`
  bus). Both moves are large, risky migrations against a shared Postgres + the ubiquitous `company`
  FK with ~zero payoff for a single-installer ERP. Defer until a module genuinely needs independent
  scaling/deploy. No founder action needed — this is a "don't burn weeks on it" call. Effort L.

### Strategic calls (ungated, but I recommend holding until you decide)

- **N100 / N101 / N102 — Multi-tenant SaaS platform** (per-tenant billing, tenant admin console,
  self-serve signup). The `company` foundation is already threaded everywhere and isolation is
  enforced, so **no debt accrues by waiting**. **MY RECOMMENDATION: KEEP DEFERRED until there is a
  2nd paying installer.** Self-serve signup is the single biggest auth surface in the app; building
  SaaS billing/console for zero customers adds cost + risk for no return. Decide on a *demand
  signal*, not a date. (The cheap, reversible bit with standalone value — per-tenant white-label of
  client docs via `CompanyProfile` — can be a small separate task if you want it.) These three are
  flipped to `[ ]` in the BUILD QUEUE per your "ungate all", but **do not let a drain build them yet
  unless you've decided to sell TAQINOR as a product** — tell me and I'll re-park them.
- **S21 — Real-time WebSocket chat** (Django Channels + Redis layer + ASGI + nginx WS proxy). Chat
  already works via 3 s polling. **MY RECOMMENDATION: DEFER — polling is plenty for a small internal
  team; the WS stack adds real ops complexity (sticky sessions, connection draining on deploy) for a
  marginal UX gain.** Build only on a concrete need (live dispatch, many concurrent users).

### From the 2026-06-18 refinement audit — gated copies

_All cleared. The former SCHEMA / DEP / DECISION / GALLERY mirrors of the REFINEMENT QUEUE held
nothing pending even before this change, and auto-gating is now OFF entirely (the labels remain on
the tasks for visibility but no run skips them)._

---

## MANUAL — Reda's / Meryem's tasks (NOT code; agent never does these)

Tracked here so they aren't lost:
- Enter the real **ICE / IF / RC** on the server (Paramètres → Identifiants légaux) — live invoices
  currently lack the legally-required seller ICE until then.
- Enter the **11 OSP pump prices** on the server (the agricole pump box stays red; don't send an agri
  quote before).
- Enter **real stock quantities** on the server (the ~283 M DH dashboard value is demo quantities).
- **Article 33 / Loi 82-21 outreach** to the install portfolio (decree in force since 9 June —
  overdue, still sendable; Meryem sends; tag replies « Régularisation 82-21 »).
- **Confirm Sami's GitHub org access is removed.**
- **Confirm the PC cleanup ran** (taqinor-secrets.txt + test-leads JSON deleted).
- **Set the default lead responsable** to Meryem (Paramètres → Leads).
- **Personalize the WhatsApp templates** (Paramètres → Messages WhatsApp).
- Optional: add `PUBLIC_BASE_URL=https://api.taqinor.ma` to the server `.env` for cleaner WhatsApp
  links (they already work via auto-redirect).
- **DEBUG:** turn it off when you decide the OS is ready (your call — the agent will not raise it).


---

## DONE LOG (agent appends one plain-language line per completed task)

