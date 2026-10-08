# Audit X6 « performance » — dossier d'évaluation (L2, piste C14, 08/10/2026)

Unité **X6** (piste sans fichiers propres : tâches routées aux propriétaires), groupe **APRF**, niveau **L2**. Claim : branche `audit-X6`.

Méthode : `docs/audits/METHODE.md` v2. Sorties brutes (lanes, verdicts, sondes) : scratchpad de la session — ici la
commande, le SHA et un extrait court seulement.

## 1. Charte (phase 1)
SHA lu : origin/main (branche audit-X6). Pile locale : checkout `C:\dev\taqinor-os` sur un origin/main récent (dire son SHA).

## Système et frontière
X6 est une PISTE : il ne possède aucun fichier ; chaque tâche va chez le propriétaire des fichiers qu'elle édite
(`python scripts/check_ownership.py --owner-of`). Points chauds du registre : `crm/services.py`, `apps/web/src/pages/proposition/
[...token].astro`, `installations/services.py`, `DevisGenerator.jsx` ; plus les listes et exports des apps conservées
(ventes, crm, installations, stock, sav, ged, reporting). Apps parquées hors périmètre.

## Critère unique : C14 (performance), avec PREUVE MESURÉE
Un constat C14 n'existe que s'il est MESURÉ : nombre de requêtes SQL qui croît avec N (N+1) — mesuré par
`django.test.utils.CaptureQueriesContext` sur la pile locale, à deux tailles de données (données démo, puis N objets
supplémentaires créés DANS une transaction annulée) ; export/liste non paginé (taille de réponse qui croît sans borne) ; boucle
O(n²) prouvée (temps ou compte d'opérations à deux tailles) ; travail lourd refait à chaque requête de lecture (ex. le moteur de
devis appelé par ligne dans une liste — déjà relevé : C-AMOT LBUILD2-1, AMOT13 ; citer). Pas de micro-optimisation, pas
d'« on pourrait mettre un index » sans mesure.

Seuils de décision : S2 = une liste/écran utilisateur dont le nombre de requêtes croît linéairement avec les lignes (N+1) ou
un export sans borne sur une table qui grossit avec l'activité ; S3 = travail redondant mesuré (> 2× le nécessaire) sur un
chemin fréquent ; S4 = le reste (OPTIONNEL).

## NE PAS REFAIRE
Tâches ouvertes de performance déjà déposées (grep « N+1 », « select_related », « prefetch », « pagination », « assertNumQueries »
dans docs/plans/*, PLAN*.md, ERROR_PLAN.md, new_tasks_plan.md) : CITER. La chaîne SPL déplace le code : nommer le SYMBOLE.

## Étapes (identifiants stables)
- P1 listes API : P1.1 ventes (devis, factures, BC), P1.2 crm (leads, clients, cockpit, relances du jour), P1.3 installations /
  stock / sav / ged.
- P2 détails lourds : P2.1 fiche lead, P2.2 devis (overrides, historique, offres-tailles), P2.3 chantier.
- P3 exports et rapports : P3.1 xlsx/csv, P3.2 reporting/pilotage, P3.3 tâches Celery périodiques.
- P4 front : P4.1 DevisGenerator (recalculs à chaque frappe), P4.2 page publique proposition (charge, scripts), P4.3 listes
  qui lisent toutes les pages.

## Détecteurs (scout)
grep `pagination_class = None` et ViewSets sans pagination dans les apps conservées ; grep des SerializerMethodField qui
appellent un service/sélecteur (requête par ligne) ; liste des `@action(detail=False)` qui renvoient `Response(serializer(qs,
many=True).data)` sans pagination ; grep `fetchAllPages(` côté front ; grep `.objects.all()` dans les tâches périodiques ;
taille de `[...token].astro` et du bundle (`ls -la C:\dev\taqinor-os\frontend\dist\assets` si présent) ;
`python scripts/check_parked_apps.py`.

## 2. Plan des lanes et coût (phase 3)
| Ronde | Lanes (modèle / effort) |
|---|---|
| Scouts | détecteurs, dédoublonnage (haiku / low) |
| R2 jugement | LQVENTES listes ventes · LQCRM listes crm/cockpit · LQINST installations/stock/sav/ged (sonnet/high) · LEXPORT exports/rapports/tâches · LFRONTPERF générateur/listes/proposition (sonnet/medium) |
| R3 porte empirique | VA (opus/high : LQVENTES, LQCRM) · VB (opus/high : LQINST, LEXPORT, LFRONTPERF) — mesures à deux tailles en transaction ANNULÉE |
| Tâches | 1 rédacteur (opus/high) |
| Critique | 1 critique de complétude (opus/high) — aucun appel Fable |

11 agents, ≈ 2,9 M jetons de sous-agents.

## 3. Manifeste de couverture (phase 4)
**Détecteurs** (scout) : 9 exécutés — 3 ViewSets sans pagination (calepinage, crm, statuspage) ; 28+ appels `fetchAllPages` côté
front ; SerializerMethodField nombreux (adsengine) ; tailles des points chauds (DevisGenerator 5 545 l. ; proposition 11 734 l. /
735 Ko de source) ; aucune boucle `.objects.all()` réelle en Celery ; 862 `select_related`/`prefetch_related` existants ;
`check_parked_apps` OK. Aucun bundle `dist` présent localement (non mesuré). Réserve : les tests de budget de requêtes
(`test_yopsb13_devis_query_budget.py`, budget produits) sont `@unittest.skip` alors que `docs/query-budgets.yml` les déclare appliqués.

**Fichiers lus / non lus par lane** (extrait ; liste complète au scratchpad) :
- **LEXPORT** :
  LU (plages ou fichiers entiers) :
  - `apps/crm/exports.py` (entier), `apps/crm/views.py` l.376-392, 3245-3296 (export leads/clients)
  - `apps/ventes/exports.py` (l.1-330, 453-500, 635-749 + index des fonctions), `apps/ventes/journal_view.py` (l.1-140)
  - `apps/records/xlsx.py` (l.49-82 + index), `apps/records/storage.py` l.293-345
  - `apps/dataimport/exporters.py` (entier), `exports_view.py` (entier), `export_registry.py` (entier), `export_views.py` l.60-125
  - `apps/stock/views/mouvement.py` l.40-116, `views/produit.py` l.530-566, `views/negoce.py` l.225-260, `views/fournisseur.py` l.465-500 (début), `stock/services.py` l.140-175, 630-660, 710-740, 829-960, 3866-3890
  - `apps/reporting/views.py` l.60-340 (dashboard, `_ht_encaisse`, `_ca_*`), `pipeline.py` (entier), `commercial.py` l.40-205, 295-320, `reports.py` l.120-175, `reports_field.py` l.140-185, `insights.py` l.318-392, 625-660, 985-1050, `integrity.py` l.100-135, `balance_export.py` l.25-60, `scheduled_reports.py` l.50-110, 405-445, `tasks.py`, `rapport_builder.py` l.150-260, `rapport_abonnements.py` l.178-200 (+ index)
- **LFRONTPERF** :
  LU : `frontend/src/pages/ventes/DevisGenerator.jsx` l.1-152 (imports), 925-1020, 1105-1300, 1355-1640, 3650-3700 + greps de tous les hooks/`produits.find`/`lines.map` ; `frontend/src/utils/fetchAllPages.js` (entier) ; `features/ventes/store/ventesSlice.js` l.20-60,160-175 ; `features/crm/store/crmSlice.js` l.1-110 ; `features/stock/store/stockSlice.js` l.20-40 ; installations/sav slices (extraits) ; `features/ventes/etudeHorairePreview.js` (entier) ; `features/ventes/solar.js` signatures + `computeROI`, `optionTotalsTTC`, `computeBuyCostDetail` (début) + exécution ; `pages/Dashboard.jsx` l.500-600 ; `features/stock/StructureSelector.jsx` l.25-60 ; `api/axios.js` l.55-100 ; `backend/django_core/core/pagination.py` l.1-100 ; `erp_agentique/settings/base.py` l.655-735, 1665-1680 ; `backend/nginx/nginx.conf` l.45-120, 340-400 (+ grep `limit_req_status`) ; `backend/caddy/Caddyfile` (grep) ; `apps/web/.../[...token].astro` l.1-40, 360-420, 8530-8730, 11010-11140 + greps (script/style/fetch/import/setInterval/scroll) et découpage en octets.
  NON LU : `DevisGenerator.jsx` l.153-930, 1020-1105, 1640-3650, 3700-5545 (JSX du rendu et handlers : vérifié seulement par grep) ; `DevisList.jsx`/`FactureList.jsx`/`StockList.jsx` (sites `dispatch(fetchX)` comptés par grep, corps non lus) ; `useApercuServeur.js` (débounce lu via le commentaire de `etudeHorairePreview.js`) ; `ui/useDraftAutosave.js` (grep du délai seulement) ; les ~11 000 lignes restantes de `[...token].astro` (gabarit, scripts 8730-11010) ; `apps/web/src/lib/*` ; coût serveur par page de liste (pas de sonde DB dans cette lane : à la charge du vérificateur LFRONTPERF-1/3 sonde c).
- **LQCRM** :
  LUS (plages) :
  - `backend/django_core/apps/crm/views.py` : 286-420, 415-745 (ClientViewSet complet), 744-1000 (LeadViewSet : list, retrieve, cartes, get_queryset,
  `_annoter_prochaine_touche`), 2245-2305 (`placement_cadences`), 2520-2700 (`relances`, `roi_sources`, `client_match`), 2767-2800 (`sla_breach`),
  3213-3312 (`bulk`, `export_xlsx`, `panneau_appel` signature), 3699-4090 (`RelanceEtapeViewSet` : permissions, queryset, list, suivi, journal,
  cadences_echues, kpi_adherence, mes_stats, chaine_commerciale, controle), 4885-4940 (`AppointmentViewSet`). Grep de structure sur tout le fichier (classes/actions).
  - `apps/crm/serializers.py` : 74-110 (en-têtes), 225-510 (`RelanceEtapeSerializer` entier), 586-735 (`ClientSerializer`), 847-1000 (en-tête `LeadSerializer`),
  1060-1195, 1536-1810 (méthodes `get_*`, `get_devis`), 2019-2050 (`AppointmentSerializer`).
- **LQINST** :
  LUS (plages) :
  - `docs/audits/METHODE.md` §C.1 (313-360) ; BRIEF.md ; CHARTE.md.
  - `apps/sav/serializers.py` 1-125, 405-480, 655-735, 855-905 ; `apps/sav/views.py` 86-175, 578-660, 2660-2684 ;
  `apps/sav/models.py` 970-1130, 1601-1616, 1746-1755 ; `apps/sav/selectors.py` 334-377, 1944-1962 ;
  `apps/sav/tests_perf_n1_tickets.py` 1-40, `tests_yopsb13_ticket_query_budget.py` 1-110.
  - `apps/installations/serializers.py` 305-380, 570-672, 1212-1216, 1376-1380, 1568-1572, 1695-1736, 1806-1810, 1957-1990,
  2023-2105, 2141-2146, 2199-2230, 2269-2273, 2366-2407 (+ listes `class`/`SerializerMethodField` complètes) ;
- **LQVENTES** :
  Fichiers / plages LUS (par Read ou sed/grep ciblés) :
  - `docs/audits/METHODE.md` §A.4 (l.105-135) et §C.1 (l.315-360) ; BRIEF.md ; CHARTE.md.
  - `apps/ventes/views/devis.py` 40-300 (queryset, get_queryset, permissions, perform_create) ; `views/devis_cycle.py` 310-360, 395-445, 650-675 ; `views/devis_cadence.py` entier ; `views/devis_etudes.py` 48-90, 125-250, 345-385 ; `views/facture.py` 88-180, 1774-1830, 1940-2050 ; `views/bon_commande.py` 95-125 (queryset) ; liste des `@action` de `devis*.py`.
  - `apps/ventes/serializers.py` 56-195 (LigneDevisSerializer), 360-850 (DevisSerializer en entier) ; `serializers_facturation.py` 16-105, extraction des `SerializerMethodField` jusqu'à l.600.
  - `apps/ventes/quote_engine/builder.py` 90-160, 200-316, 1428-1460, 1518-1630, 2488-2535, 3240-3262, 3510-3660, 4025-4100, 4657-4685 (+ grep des requêtes sur tout le fichier) ; `etude_horaire.py` 1723-1765 ; `utils/options.py` 85-110, 383-480 ; `utils/echeancier.py` 285-320, 584-617, 905-953 ; `utils/expiry.py` entier ; `domain/modifiabilite.py` 80-135 ; `domain/argent.py` 103-175 ; `models.py` 496-600, 800-835 ; `models_facturation.py` 318-395 ; `selectors.py` 659-700, 870-895, 977-1035 ; `selectors_cadence.py` 17-200, 307-335 ; `selectors_facturation.py` 399-470, 566-590, 626-700, 749-838 ; `offres_tailles.py` 1310-1430, 1506-1556 + grep des fonctions ; `parametres/models_tariff.py` 180-190 ; `parametres/models_company.py` 1077-1103 ; `parametres/selectors.py` 24-70, 181-275 ; `parametres/models_documents.py` (get) ; `facturation/models.py` 380-540 ; `facturation/totaux.py` 36-165 ; `core/request_cache.py` 1-80 ; `core/pagination.py` 1-40 ; `core/mixins.py` 135-165 ; `tests/test_yopsb13_devis_query_budget.py` 1-200 ; `tests/test_perf_n1_devis.py` 1-120 ; `frontend/src/pages/ventes/devisList/DevisRow.jsx` (grep `roof_layout`) ; docs : `docs/plans/PLAN_AUDIT_MOTEUR.md:130` (AMOT13), grep des plans.
  Fichiers de ma surface NON lus (ou lus partiellement) :
  - `apps/ventes/serializers.py` 195-360 (échéancier / tiers payeur), 853-1420 (DevisWriteSerializer, presets, listes de prix, offres tailles, plan commission) ; `serializers_facturation.py` 106-596 hors extraction des méthodes (le détail de `FactureSerializer.get_avoirs/tva_par_taux` n'a pas été relu, je m'appuie sur AUD157 et `test_aud157_factures_kpis.py` non ouvert).

## 4. Run live (phase 4-c/4-d)
Piste C14 : la preuve est la MESURE. Les deux vérificateurs (V_VA, V_VB) ont rejoué chaque constat sur la pile locale à deux
tailles de données (démo, puis objets ajoutés dans une transaction ANNULÉE) avec `CaptureQueriesContext` / `EXPLAIN ANALYZE`,
et des bancs node sur le vrai `fetchAllPages` ; leurs sorties chiffrées sont citées par constat (§5). Aucun parcours écran
supplémentaire n'a été joué par l'orchestrateur pour cette piste.

## 5. Registre des constats (phase 4 → 6)
Rédacteur : fusion des lanes LQVENTES, LQCRM, LQINST, LEXPORT, LFRONTPERF ; **les verdicts V_VA / V_VB priment** (gravités
re-graduées par eux appliquées). Critère unique C14 (charte). Pile locale = `C:\dev\taqinor-os` à `d096f2233` ; diff vers
`8a2bfcffd` (origin/main lu) vide sur tous les chemins mesurés (V_VA, V_VB), sauf `stock_breakdown` qui sur main ajoute
`quantite_en_transit` (+1 requête/produit : C-APRF-029 mesuré SOUS-estime main). Priorité : S2 → P1, S3 → P2 (aucun S1).
Confiance : REPRO = croissance mesurée à deux tailles par une sonde exécutée (scripts `va/*.py`, `vb/*.py|mjs`) ;
STATIQUE = défaut entièrement déterminé par le code (grep exécuté + fonction réelle rejouée).

**Incident de sonde (V_VB, à connaître avant toute preuve en direct).** `vb/f3.py` a fait deux `GET /api/django/ventes/devis/`
HORS transaction : le GET de liste ÉCRIT (`ShareLink.for_devis`, AMOT13) et a prolongé `expires_at` de 14 liens de partage
de la société démo 1 (pile locale, pas la production ; aucune création). Toute preuve qui touche la liste des devis se fait
dans une transaction annulée tant qu'AMOT13 n'est pas livrée.

**QPERF1** (`docs/done_task.md:119`, « shipped via SCA43 ») est contredit par la mesure : 205 requêtes SQL pour une page de
15 devis (V_VB, LFRONTPERF-3), +9,8 par ligne (V_VA). `ventesSlice.js:22-25` garde `DEVIS_PAGE_CONCURRENCY = 5` « tant que
QPERF1 n'atterrit pas » : c'est C-APRF-001.

## Tableau

| ID | étape | crit. | gravité | confiance | prio. | titre | tâche(s) |
|---|---|---|---|---|---|---|---|
| C-APRF-001 | P1.1 | C14 | S2 | REPRO | P1 | Liste des devis : moteur de devis rejoué par ligne, lectures hors préchargement (+9,8 req/ligne) et second passage pour `comparaison_options` (22 passages / 15 lignes) | APRF2 (PARAMETRES), APRF3 (MOTEUR), APRF5 (DEVIS) ; écriture ShareLink sur GET = déjà couvert par AMOT13 |
| C-APRF-002 | P1.1 | C14 | S3 | REPRO | P2 | `DevisViewSet` ne charge pas ce que `DevisSerializer` lit : `updated_by`, `company`, `factures__affectations_paiement` (1 req/ligne chacun) | APRF4 (DEVIS) |
| C-APRF-003 | P1.1 | C14 | S3 | REPRO | P2 | `electrical_design` = 55 % des octets de la liste des devis, jamais lu par l'écran liste | APRF6 (DEVIS) |
| C-APRF-004 | P1.1 / P3.1 / P3.2 | C14 | S2 | REPRO | P1 | `Devis.total_ttc` lu en boucle sans `lignes__produit` préchargé (2 req/devis deux options, 1/devis mono) : sélecteurs CA, Relances du jour, pipeline/commercial Reporting, export devis | APRF7 (DEVIS), APRF9 (LEAD), APRF12 (FACTURATION), APRF14, APRF15 (ANALYSE) |
| C-APRF-005 | P1.1 | C14 | S3 | REPRO | P2 | « Relances du jour » (`action-requise`) : paniers sans borne, +199 octets par devis refusé sans motif | APRF1 (DEVIS, M0 contrat), APRF9 (LEAD) |
| C-APRF-006 | P1.2 | C14 | S2 | REPRO | P1 | `ClientViewSet` : liste clients à 4 + 3·F requêtes par client, toutes les pages lues au montage | APRF17 (TRANSVERSE) |
| C-APRF-007 | P1.2 | C14 | S2 | REPRO | P1 | Cockpit « Comptes dormants », « Portefeuille », `engagement-bulk` : 14 / 19 / 18 requêtes par client, tous les clients | APRF22 (TRANSVERSE) |
| C-APRF-008 | P1.2 | C14 | S2 | REPRO | P1 | `RelanceEtapeSerializer` : 1 requête par touche WhatsApp à faire (`get_message_ouvert_le`) et par touche traitée de la frise (`traite_par`) | APRF21 (TRANSVERSE) |
| C-APRF-009 | P1.2 | C14 | S2 | REPRO | P1 | Jumeaux de `LeadViewSet.list()` (`relances`, `sla_breach`) sans les cartes de préchargement : 10 et 5 req/lead | APRF18 (TRANSVERSE) |
| C-APRF-010 | P1.2 | C14 | S2 | REPRO | P1 | `roi_sources` : boucles canal × campagne + requête par lead signé (+60 pour +10 campagnes/+10 signés) | APRF19 (TRANSVERSE) |
| C-APRF-011 | P1.2 | C14 | S2 | REPRO | P1 | « Ma file » `devis_expirant_bientot` : charge tous les leads et tous leurs devis puis filtre en Python, 2 req/devis listé | APRF23 (TRANSVERSE) |
| C-APRF-012 | P1.2 | C14 | S3 | REPRO | P2 | `scope_client_queryset` : 4 jointures multi-valuées + `DISTINCT` (225 lignes jointes pour 1 client rendu) | APRF16 (SECURITE) |
| C-APRF-013 | P1.2 | C14 | S3 | REPRO | P2 | `nb_tentatives = Count('activites', distinct=True)` joint et trie tout le chatter avant `LIMIT` (2,6 → 19,5 ms) | APRF20 (TRANSVERSE) |
| C-APRF-014 | P1.3 | C14 | S2 | REPRO | P1 | Parc d'équipements SAV : 2 COUNT par ligne (2,2 req/ligne) | APRF30 (SAV) |
| C-APRF-015 | P1.3 | C14 | S2 | REPRO | P1 | Tickets SAV : +4 req/ticket dès que le client a un contrat (budget YOPSB13 mesuré sans contrat) | APRF31 (SAV) |
| C-APRF-016 | P1.3 | C14 | S2 | REPRO | P1 | Liste des chantiers : régime, calepinage, dossier 82-21 calculés par chantier et par ligne de nomenclature (25,95 req/chantier) | APRF37 (CHANTIERS) |
| C-APRF-017 | P1.3 | C14 | S2 | REPRO | P1 | Catalogue produits : 2,98 req/produit, test de budget `@unittest.skip`, manifeste `enforced: true` faussement vert | APRF32 (STOCK) |
| C-APRF-018 | P1.3 | C14 | S2 | REPRO (2 listes) + STATIQUE (9) | P1 | `prefetch_related('lignes')` sans `lignes__produit` : +1 req par LIGNE dans 11 listes d'installations | APRF38 (CHANTIERS) |
| C-APRF-019 | P1.3 | C14 | S2 | REPRO | P1 | Ordres d'assemblage : 12 req/ordre (services de détail appelés par le sérialiseur de liste) | APRF39 (CHANTIERS) |
| C-APRF-020 | P1.3 | C14 | S2 | REPRO | P1 | Bons de commande fournisseur : acomptes + annonces de livraison par BCF (1,9 req/BCF) | APRF33 (STOCK) |
| C-APRF-021 | P1.3 | C14 | S2 | REPRO | P1 | Documents GED : 3,96 req/document (versions ×3, tags) | APRF36 (DOCUMENTS) |
| C-APRF-022 | P1.3 | C14 | S2 | REPRO | P1 | Interventions : `records_attachment` (photos) et `authentication_company` 1 req par intervention (résidu AUD324) | APRF40 (CHANTIERS) |
| C-APRF-023 | P2.3 | C14 | S2 | REPRO | P1 | Replanification en masse : `suggerer_creneau` bouclé, 101 req par intervention (= 2 + 14·(1+2T)) | APRF41 (CHANTIERS) |
| C-APRF-024 | P2.3 | C14 | S2 | REPRO | P1 | « Chantiers à facturer » : 1 `Facture.exists()` par jalon atteint, historique complet | APRF24 (TRANSVERSE) |
| C-APRF-025 | P3.2 / P3.3 | C14 | S2 | REPRO | P1 | `Facture.montant_du` lu en boucle sans le préchargement d'AUD158 : Reporting +15 req/facture payée, intégrité (beat) +6 | APRF11 (FACTURATION), APRF13 (ANALYSE) |
| C-APRF-026 | P3.2 | C14 | S2 | REPRO | P1 | Vélocité du funnel : 1 requête `LeadActivity` par lead (pipeline + commercial, deux copies) | APRF14 (ANALYSE) |
| C-APRF-027 | P3.3 | C14 | S3 | REPRO | P2 | Tâches SLA CRM : 1 `.exists()` par lead dormant à chaque passage, même déjà escaladé | APRF10 (LEAD) |
| C-APRF-028 | P3.1 | C14 | S2 | REPRO (mouvements) + STATIQUE (clients, sauvegarde, CSV) | P1 | Exports xlsx synchrones et non bornés (15 137 lignes : 20,5 s, pic 80,6 Mo) ; `should_async_export` sans appelant | APRF34 (STOCK), APRF15 (ANALYSE), APRF28 (DEPLOY, garde M3) |
| C-APRF-029 | P3.1 | C14 | S2 | REPRO | P1 | Valorisation du stock : 7 req/produit (8 sur main) | APRF35 (STOCK) |
| C-APRF-030 | P4.3 | C14 | S3 | REPRO (node) | P2 | Listes complètes lues par pages de 50 alors que le serveur accepte 200 : 210 appels au Dashboard au lieu de 60 | APRF25 (TRANSVERSE), APRF29 (DEPLOY, garde M3) |
| C-APRF-031 | P4.3 | C14 | S2 | REPRO (mécanisme) | P1 | Rafale de lectures parallèles contre `limit_req` nginx (503 sans reprise) : un 503 fait perdre toute la liste | APRF26 (DEPLOY) |
| C-APRF-032 | P4.3 | C14 | S3 | STATIQUE | P2 | Chaque action unitaire sur un devis relit TOUTES les pages (21 sites, 40 appels à 2 000 devis) | APRF8 (DEVIS) |
| C-APRF-033 | P1.* | C14 | S3 | REPRO | P2 | `check_query_budgets.py` aveugle au skip : un budget `enforced: true` dont le test est sauté passe (exit 0) | APRF27 (DEPLOY, garde M3) |
| — | P1–P4 | — | — | — | — | Acceptation live unique du groupe | APRF42 (DEVIS) |

## RÉFUTÉS (avec argument)

- **LQCRM-7 en S3** : la lane exigeait > 0,5 s à 500 étapes ; mesuré 0,199 s (44 911 appels `couvre()`, 21 requêtes) — pas O(n²),
  linéaire en étapes × jours → OPTIONNEL.
- **C-LQINST-11 en S3** : (1) « +1 `stock_produit` par équipement » : +10 équipements ⇒ +0 requête ; (2) redondance ≥ 3× :
  mesurée 2× (checklist ×2, dossier ×2, pack ×1) → sous le seuil charte S3 (« > 2× ») → OPTIONNEL.
- **Correction de C-LQVENTES-2 (« `comparaison_options` → None en liste »)** : la liste LIT ce champ (`DevisRow.jsx:385-393`,
  `DevisList.test.jsx:196`) ; la couper casserait les deux totaux A/B. Le constat de redondance tient (C-APRF-001), la correction
  retenue est la mémoïsation.
- **Sous-claim C-LQINST-3 « `CompanyProfile.get` par chantier »** : 1 requête quelle que soit la taille (cache de requête).
- **Prémisse de LEXPORT-8 « requêtes constantes, seul le CPU croît »** : 2 requêtes par devis (`total_ttc` relit les lignes malgré
  `prefetch_related('lignes')`) → fusionné dans C-APRF-004.
- **LFRONTPERF P4.1 (DevisGenerator recalcule à chaque frappe)** : banc node, `solar.js` réel : tous les calculs non mémoïsés
  d'un rendu = 0,41 ms ; garde-fous en place (`useMemo`, `useDeferredValue`, `React.memo`, débounces).
- **C-LQINST-2 fourchette « 4 à 8 req/ticket »** : 4,0 mesuré ; les `.count()` de `droits_restants` ne sortent pas sur ces tickets
  (gravité tenue).

## PLAUSIBLES (non promus en tâche)

- **C-LQVENTES-9** (`offres-tailles` refait `build_quote_data('full')` + dérivation à chaque appel) : 0 devis dérivable sur 120
  testés (sociétés 1/40/43) ; chemin coûteux `_carte_moteur` jamais exécuté ; appels 2-3 = 0,08 s. Seuil de la lane non atteint.
- **C-LQVENTES-3, volet `lignes`/avoirs non figés** : non rejoué (`montant_ttc` figé sur les factures sondées). Le préchargement
  d'APRF4 le couvre sans assertion dédiée.
- **C-LQINST-4, « 4 cartes société recalculées par page »** : 1 requête constante chacune ; coût en temps non démontré.
- **C-LQINST-6, écriture `instancier_etapes_ordre` depuis un GET de liste** : non observée (kit sans étapes modèles, aucun INSERT) ;
  hors C14.
- **LFRONTPERF-4** (catalogue relu par 7 écrans hors store) : comptage STATIQUE (6 sites `fetchAllPages(getProduits)` + 1 clients),
  mais la redondance dépend de l'état du store à l'ouverture, non rejouée en navigateur → pas entièrement statique ; son coût
  réseau baisse ×4 avec APRF25 (page de 200).
- **LQCRM-8, terme leads** : 225 = 15 × 15 et non 3 375 — multiplication par les leads non élucidée.
- **LFRONTPERF-2 en production** : mécanisme reproduit en local (HTTP/1.1 + nginx), navigateur h2 authentifié de prod non rejoué.
- ~~**C-LQINST-5, 8 listes**~~ : promu STATIQUE par la critique (sérialiseurs `produit.nom` + vues `prefetch_related('lignes')`
  relus) — voir C-APRF-018.

## OPTIONNEL (S4 / style / hors seuil — aucune tâche)

- LQCRM-7 « Contrôle du suivi » : `couvre()` ×7,2 entre 50 et 500 étapes mais 0,20 s à 500 (< 0,5 s, seuil de la lane) ;
  linéaire en étapes × jours, requêtes constantes (V_VA). Voir RÉFUTÉS.
- C-LQINST-11 `/etapes/` du chantier : 56 requêtes constantes pour 10 étapes, redondance 2× (< seuil S3 « > 2× ») (V_VB).
- C-LQVENTES-9 `offres-tailles` : rétrogradé S4 (source dérivable absente, voir PLAUSIBLES).
- LQVENTES O-1 (5 passages CPU de la chaîne d'argent par ligne, sans requête), O-2 (`variantes` bornées 2-5), O-3 (`kpis_factures`
  mémoire linéaire en l'encours), O-4 (`FactureViewSet.bulk` sans plafond, non sondable sans envoi), O-5 (`historique` non paginé,
  borné par la vie d'un devis).
- LQCRM O-1 (`segments` : route morte, C-ACRM-039), O-2 (`export_xlsx` clients sans ids — couvert par la garde APRF28), O-3
  (`kpi_adherence`/`mes_stats` sans appelant), O-4 (3 COUNT fixes de `file_du_cockpit`), O-5 (`historique`/`chatter`), O-6
  (`presign_avatar` CPU par ligne), O-7 (sélecteurs non lus).
- LQINST O1 (réservations : linéaires, un passage par événement), O2 (`compute_besoin_materiel` 1 req/produit distinct), O3
  (`?avec_disponibilite=1`, aucun appelant front).
- LEXPORT O-1 (`scan_sla_breaches` filtre société en Python), O-2/O-3 (rapports e-mail quotidiens), O-4 (`Company.objects.all()`
  au lieu d'`active_companies()` dans 3 tâches CRM), O-6 (doublon `_lead_value`, absorbé par APRF14).
- LFRONTPERF O1 (rendu React de DevisGenerator non profilé), O2 (page proposition : taille servie non mesurée), O3 (bundle ERP
  455 Ko gzip, sans anomalie), O5 (DevisGenerator lit clients/leads en page 1 seulement : exhaustivité, hors C14).
- **HORS CRITÈRE, à signaler à l'orchestrateur (pas C14, non vérifié par R3)** : LFRONTPERF O4 — `apps/web/src/pages/proposition/
  [...token].astro:8681-8688` : le pad de signature réaffecte `c.width/c.height` sur `window.resize` (efface le dessin) alors que
  `hasInk` reste vrai (l.8670/8699) et que `toDataURL` part si `hasInk` (l.9045-9047) : risque de signature blanche sur mobile.
  STATIQUE, gravité lane S2. Propriétaire `apps/web` (pas de PLAN_AUDIT) → non déposé ici.
- Troncature silencieuse de `fetchAllPages` au-delà de 200 pages (10 000 lignes, `console.warn` seul) : exhaustivité (C13),
  hors C14.

## 6. Couverture non atteinte et limites (phase 6)
Voir l’en-tête du groupe (Non couvert) dans le plan du propriétaire.

## 7. Tâches hors `PLAN_AUDIT_*` non déposées
Consigne du fondateur pour ce run : n'ajouter des tâches que dans les `docs/plans/PLAN_AUDIT_*.md`. À déposer sur son accord :

# APRF — tâches hors plan (propriétaire sans PLAN_AUDIT)

Aucune tâche APRF n'a de propriétaire dépourvu de `docs/plans/PLAN_AUDIT_*.md` (`python scripts/check_ownership.py --owner-of`
exécuté sur chaque `Files:`). Le seul défaut d'un propriétaire sans plan d'audit (`apps/web` : pad de signature de
`apps/web/src/pages/proposition/[...token].astro:8681-8688`, LFRONTPERF O4) est HORS critère C14, non vérifié par R3, et n'a
donc pas de tâche APRF : il est signalé à l'orchestrateur dans CONSTATS.md (OPTIONNEL) et GROUPE_HEADER.md (Non couvert).
