# Vérifie AANA — contre-visite de clôture du groupe analyse (X7), 01/11/2026

Commande `vérifie AANA` (METHODE §C.4.2, skill audit §5), lancée par `loop audit` (quatrième itération). Après les
contre-visites ACHT, AMOT et ASEC (PR #1180, #1185, #1187, toutes mergées), `audit_registre.py --du` liste trois
groupes dus en clôture : AANA 51/51, AGNR 47/48 et ATOT 35/35. Ils se jouent par nombre de tâches cochées
décroissant, donc AANA passe en premier. La contre-visite précédente date du 11/10
(`docs/audits/2026-10-11-analyse-verifie.md`, 20/20 ok).

Pour chaque tâche de l'échantillon, on rapproche le texte de la tâche, ses commits, le test nommé et le code de
`main`, puis on applique les 7 critères de `docs/claude-memory/lecons-construction-qjr5.md`. Chaque écart S1-S2 est
prouvé par une sonde jouée en transaction annulée, ou par une fonction pure (validateur SQL, rendu du front). Les
écarts confirmés deviennent des tâches v3 dans le plan du propriétaire des fichiers.

La contre-visite n'a rien construit, n'a lancé aucun deploy et n'a rien lu ni écrit en production.

## 0. Préconditions

- **SHA.** `origin/main` = `32375fe65` (PR #1185), re-fetch en début d'itération. Branche de claim :
  `verifie-aana-cloture`, commit vide poussé.
- **Registre.** X7 `analyse`, groupe AANA, dossier `docs/audits/2026-10-05-analyse.md`, 51/51 cochées.
- **Inventaire.** 51 tâches AANA `[x]` : 46 dans `PLAN_AUDIT_ANALYSE.md`, 3 dans `PLAN_AUDIT_DEPLOY.md`, 2 dans
  `PLAN_AUDIT_LEAD.md`.
- **Échantillon (graine = SHA `32375fe65`, déterministe) : 21 tâches.**
  - Les 11 tâches cochées portant S1 ou P0 : AANA2, 3, 4, 6, 9, 12, 15, 19, 20, 30, 52.
  - 25 % du reste, soit 10 sur 40, tirées par `random.Random(int(sha, 16)).sample` sur les ids triés : AANA1, 18, 21,
    27, 28, 29, 32, 44, 45, 51.
- **Pile des sondes.**
  - Sondes Django : conteneur jetable `sonde-verifie-aana` (code de `main` copié par `git archive`), en transaction
    annulée.
  - Sonde du validateur SQL : image `fastapi_ia`, réseau coupé.
  - Sonde du front : Node.
  - Contrôles faits : 0 mail, 0 tâche Celery. Après la sonde d'import, une vérification directe a confirmé qu'aucun
    produit ni aucune société de sonde n'a survécu. Le compte de lignes a bougé pendant l'exécution parce que la pile
    d'une autre session écrivait dans la même base.

## 1. Vérificateurs (5 agents frais, opus, effort élevé, lecture seule, même répertoire)

| Verdict | Nombre | Tâches |
|---|---|---|
| ok | **14** | AANA1, 3, 4, 6, 9, 15, 18, 27, 28, 32, 44, 45, 51, 52 |
| partiel | **7** | AANA2 (S1), AANA12 (S2), AANA19 (S2, jumeau crm), AANA20 (S2), AANA21 (S2), AANA29 (S2), AANA30 (S3) |
| non-fait / faux / régression / déjà-présent | 0 | — |

Changements postérieurs jugés voulus, donc pas des régressions :
- 404 au lieu de 400 (ERR-ENF11) ;
- VNT22 : « signé » = dernier accepté de chaque chaîne de révision ;
- AANA45 : routes branchées selon D-AANA-036-BRANCHER ;
- EDI parqué selon D-AANA51 ;
- `X-Forwarded-Proto: https` ajouté aux appels internes le 30/10.

## 2. Sondes (6 REPRO)

| Sonde | Tâche | Observé (code de `main`) |
|---|---|---|
| `docs/audits/sondes/AANA/C-AANA-VER-005.py` | AANA2 | `WITH "CRM_LEAD" AS (SELECT 1 AS id) SELECT * FROM crm_lead` **acceptée et renvoyée telle quelle**, sans filtre société et hors liste blanche. Idem pour `django_session`, et dans un EXISTS d'une requête par ailleurs filtrée par société |
| `docs/audits/sondes/AANA/C-AANA-VER-001.py` | AANA12 | import produit, prix `12.345` → commit 200, `skipped` vide, prix relu **12.35** (arrondi muet) |
| `docs/audits/sondes/AANA/C-AANA-VER-002.py` | AANA20 | facture 1000 HT émise, avoir total sans paiement → statut « payee », **`ca_paye` 1000.0** (attendu 0) |
| `docs/audits/sondes/AANA/C-AANA-VER-003.py` | AANA21 | 1 lead signé + 1 lead perdu → `win_rate_pct` **100.0** contre `overall_close_rate_pct` **50.0**, sur la même page |
| `docs/audits/sondes/AANA/C-AANA-VER-004.py` | AANA19 | V1 acceptée puis révisée en V2 brouillon → `_devis_signes` compte V1, mais **`ca_signe_periode` crm = 0** |
| `docs/audits/sondes/AANA/C-AANA-VER-006.mjs` | AANA29 | conversion {10 devis, 3 acceptés, 15 factures} → barre « Factures émises » **150 %**, et la barre « Devis acceptés » recalcule le taux à l'écran |

## 3. Écarts retenus

| Constat | Tâches | Écart de | Crit. | Grav. | Emplacement | Observé → attendu |
|---|---|---|---|---|---|---|
| C-AANA-VER-005 | AANA53, AANA72 | AANA2 | C5 | S1 | `backend/fastapi_ia/app/services/sql_agent_service.py::_rewrite_node` | noms de CTE comparés en minuscules, alors que Postgres respecte la casse entre guillemets → aucune relation hors liste blanche (`pg_*` compris) n'est jamais lue ; le test qui sert d'oracle est corrigé |
| C-AANA-VER-001 | AANA54 | AANA12 | C6 | S2 | `apps/dataimport/services.py::_valider_ligne_produit` | prix à plus de 2 décimales arrondi en silence → ligne refusée avec sa raison |
| C-AANA-VER-002 | AANA55, AANA60 | AANA20 | C7 | S2 | `apps/reporting/views.py::_ht_encaisse` | facture soldée par avoir comptée comme encaissée → encaissé = paiements reçus ; en attente = `montant_du` |
| C-AANA-VER-003 | AANA56, AANA65 | AANA21 | C3 | S2 | `apps/reporting/commercial.py::win_loss_by_source` | taux de gain calculé sur tous les leads, perdus compris → `taux_gain` partout (`roi_sources` crm inclus) |
| C-AANA-VER-004 | AANA75, AANA76 | AANA19 | C3 | S2 | `apps/crm/clients_selectors.py::_devis_compte_comme_signe` | règle « accepté ET is_active » au lieu de `devis_signes_en_vigueur` (VNT22) → CA signé crm aligné (objectifs, défis, attribution) |
| C-AANA-VER-006 | AANA57 | AANA29 | C1 | S2 | `frontend/src/pages/Reporting.jsx::ConversionBar` | 150 % et taux recalculé à l'écran → aucun pourcentage recalculé à l'écran ; test de rendu |
| C-AANA-VER-007 | AANA58, AANA59, AANA60 | critique (D-AANA-VER-1) | C3 | S2 | `apps/ventes/selectors.py` (nouveau sélecteur) | trois définitions du taux d'acceptation → une seule : acceptés ÷ devis envoyés de la période |
| C-AANA-VER-008 | AANA66, AANA67 | critique (D-AANA-VER-2) | C3 | S2 | `frontend/src/pages/crm/leads/views/KanbanView.jsx::STAGE_PROBABILITY` | deux tables de probabilités (25/50/70 contre 20/40/60) → une seule table, servie par l'API |
| C-AANA-VER-009 | AANA61 | critique | C7 | S2 | `apps/semantic/management/commands/seed_metriques.py::Command` | métrique `ca_ht` qui compte les brouillons → brouillon et annulée exclus |
| C-AANA-VER-010 | AANA62 | critique | C3 | S2 | `apps/reporting/insights.py::sales_leaderboard` | deux populations pour le classement → une seule |
| C-AANA-VER-011 | AANA63 | critique | C1 | S2 | `backend/fastapi_ia/app/services/sql_agent_service.py` (prompt) | colonnes inexistantes et 4ᵉ définition du CA → prompt aligné sur le schéma réel |
| C-AANA-VER-012 | AANA68 | critique | C7 | S2 | `apps/ventes/selectors.py::resultats_devis_periode` | acceptés comptés sans statut ni révision → `devis_signes_en_vigueur` |
| C-AANA-VER-013 | AANA69 | critique | C6 | S2 | `apps/ventes/paiement_import.py::_normaliser_mode` | mode inconnu → « virement » en silence → mode signalé |
| C-AANA-VER-014 | AANA70, AANA73 | critique | C6 | S2 | `apps/ventes/domain/imports.py::_statut_facture` | statut inconnu → brouillon ; montants source jamais lus → statut refusé, champ retiré du mapping |
| C-AANA-VER-015 | AANA71 | critique | C6 | S2 | `apps/stock/services.py::import_prix_fournisseur_xlsx` | `quantize` muet, segments et lignes sautés sans rapport → un rapport par ligne |
| C-AANA-VER-016 | AANA64 | AANA30 | C12 | S3 | `backend/db/rls_roles.sql` | rôle `sql_agent_ro` jamais provisionné automatiquement → provisionnement idempotent au déploiement |

**Constats S1-S2 : 15** (1 S1, 14 S2). Les 6 portés par une tâche échantillonnée sont prouvés par sonde (C-AANA-VER-001
à -006). Les 9 issus de la critique sont prouvés par lecture du code : un vérificateur frais rejoue la reproduction à la
fermeture de leur tâche (METHODE §C.4.4). AANA74 clôt les sections : c'est l'acceptation en direct, à deux sociétés,
jamais confiée à une lane.

Routage :

| Propriétaire | Plan | Tâches |
|---|---|---|
| analyse | `PLAN_AUDIT_ANALYSE.md` | AANA53-58, 61-63, 66, 73, 74 |
| devis | `PLAN_AUDIT_DEVIS.md` | AANA59, 68, 70 |
| deploy | `PLAN_AUDIT_DEPLOY.md` | AANA60, 64, 72 |
| lead | `PLAN_AUDIT_LEAD.md` | AANA65, 67, 75 |
| facturation | `PLAN_AUDIT_FACTURATION.md` | AANA69 |
| stock | `PLAN_AUDIT_STOCK.md` | AANA71 |
| acquisition | `PLAN_AUDIT_ACQUISITION.md` | AANA76 |

Les consommateurs portent un `@after` sur la moitié qui produit leurs données (PACT11).

**Décisions du fondateur (01/11/2026).**
- D-AANA-VER-1 = `envoyes_periode` : UN taux d'acceptation, acceptés ÷ devis envoyés dans la période. Le contrat AANA1
  change donc de sens.
- D-AANA-VER-2 = `serveur` : UNE table de probabilités, `core/win_probability.py::STAGE_BASE_PROBABILITY`, servie par
  l'API.

## 4. Seconde lentille et critique de complétude

- **Seconde lentille sur le S1 (opus, effort élevé, contexte frais, voies différentes de la sonde).** C-AANA-VER-005
  est **MAINTENU S1**.
  - Résolution des noms : vérifiée par la règle de casse de Postgres et, indépendamment, par `build_scope` de sqlglot.
  - Chaîne d'exécution : `_SecureQueryTool._run` puis `SQLDatabase._execute`, sans aucun autre contrôle. La RLS
    Postgres est éteinte par défaut.
  - En prod, les droits (GRANT) de `sql_agent_ro` arrêtent les tables Django hors liste. En revanche,
    `WITH "PG_STATS" AS (SELECT 1) SELECT attname, most_common_vals FROM pg_stats WHERE tablename='crm_client'` est
    ACCEPTÉE. Selon la documentation Postgres (non exécuté contre une base), `pg_stats` est lisible par tous pour toute
    table que le rôle peut lire : la requête rendrait les valeurs fréquentes et les histogrammes de toutes les sociétés,
    et `prix_achat` via un littéral.
  - En dev, ou sur une machine neuve sous le propriétaire superuser, tout est lisible, `pg_shadow` compris.
  - L'état réel des GRANT sur le serveur n'a pas été vérifié.
- **Critique de complétude (1 appel Fable, effort élevé).**
  - Elle étend la portée de C-AANA-VER-005 aux vues `pg_catalog` lisibles par tous (`pg_roles`, `pg_settings`,
    `pg_stat_activity`). Elle clôt aussi les formes non exploitables : schéma qualifié, colonnes et alias entre
    guillemets.
  - Elle a relevé 9 trous qui donnent des tâches : C-AANA-VER-007 à -015.
  - Relevés de seconde main par un sous-agent, non relus, donc non déposés : `date_pose` illisible retirée, troncatures
    `_borne` de l'import Odoo, booléen de jour férié, `parseInt(q)||1` de l'import OCR, `int()` du nombre de MPPT,
    « impayées » du cockpit des ventes.

## 5. Optionnel (non déposé)

- **AANA2, AANA6.** Le validateur accepte des formes entre parenthèses que Postgres refuse (sans impact). Le
  commentaire « Retombe sur DATABASE_URL » est périmé.
- **AANA12.** Le jumeau `ventes/domain/imports.py::ajouter_lignes_facture_import` n'a aucun appelant en production :
  à reprendre avant de le brancher.
- **AANA15.** Une vue enregistrée privée d'un collègue de la même société peut être mise en favori, et son libellé
  s'affiche.
- **AANA18.** La preuve HMAC n'a ni nonce ni horodatage (elle n'est jamais exposée).
- **AANA19.** Seau « accepté » à 0 pendant une révision. `pipeline.gagnes.valeur` lit le devis le plus récent, pas le
  devis signé.
- **AANA20.** Aucun cas avec avoir dans le test nommé (AANA55 le comble).
- **AANA30.** Un GRANT sur une table absente fait échouer toute l'instruction, et toute nouvelle table autorisée exige
  un nouveau GRANT manuel en prod.
- **AANA32.** `WebhookDelivery.payload` n'a pas d'encodeur (aucun émetteur `Decimal` aujourd'hui).
- **AANA44.** `core/win_probability.py` garde des littéraux d'étape tolérés par la baseline de `check_stages`
  (AANA46).
- **AANA45.** L'archive `backend/parked/chat/tasks.py` appelle encore `/chat/transcribe`.
- **AANA64.** `/opt/autodeploy/auto-deploy.sh` (hors dépôt) doit appeler le script de provisionnement : à confirmer
  par Reda.
- **Critique de complétude.** Le taux de conversion d'attribution (`taux_conversion_pct`, propriétaire acquisition)
  et la métrique `taux_conversion` sont un AUTRE indicateur, non planifié.

## 6. Couverture et non-couvert

- **Couvert.** 21 tâches sur 51 cochées (toutes les S1/P0 et 25 % du reste) : commits, tests nommés, code de `main`,
  décisions D-AANA-*.
  - Tests joués par les vérificateurs : unittest `test_agent_sql_role` 5/5, `test_internal_host` 8/8,
    `PreuveConfirmationTests` 3/3, `test_sql_security` (31 tests) et `reporting-format.test.mjs` 6/6.
  - Gardes exécutées : `check_stages.py`, `check_api_shapes.py`, `check_parked_apps.py`.
  - Sondes : 6, jouées par l'orchestrateur.
- **Non couvert.**
  - Les 30 autres tâches cochées.
  - Les TestCase Django : une base est requise ; la CI de `main` est verte.
  - Aucune exécution contre une vraie base Postgres pour la variante `pg_stats`.
  - Aucune lecture de la production : les GRANT réels de `sql_agent_ro` et l'état de l'agent SQL en prod ne sont pas
    vérifiés.
  - Aucune preuve en direct à l'écran (AANA74 reste ouverte).
- **Statut du registre.** Après ce dépôt : 51 cochées sur 75 constructibles (68 %), AANA53 à AANA76 ajoutées.
  Contre-visite de clôture **avec 15 écarts S1-S2** : le statut calculé est `audité`, le cycle n'est pas sorti.

## 7. Coût

- 5 vérificateurs opus (effort élevé) : environ 0,93 M de jetons.
- 1 seconde lentille opus : environ 0,14 M.
- 1 critique Fable (effort élevé) : environ 0,19 M. Elle a étendu le S1 aux vues `pg_catalog` et ajouté 9 constats
  S2, tous déposés (AANA58-63, 66-73).
- 1 rédacteur opus : environ 0,46 M, 24 tâches v3.
- H0 S0 O7 F1 · jetons sous-agents environ 1,8 M

<!-- verifie | groupe: AANA | pct: 100 | ecarts_s1_s2: 15 -->
