<!-- verifie | groupe: ACEL | pct: 96 | ecarts_s1_s2: 1 -->

# Vérifie ACEL — contre-visite des correctifs du parcours PF11 « tâches planifiées », 15/11/2026

Déclencheur : `audit_registre.py --du` (« vérifie dû, contre-visite des correctifs (écarts S1-S2 du 2026-11-14 tous
cochés) », 60/62 = 96 %). Périmètre ÉTROIT (§C.4.6) : les tâches d'écart déposées par la passe de clôture du 14/11
(ACEL90 à ACEL94) et la tâche du constat S2 d'origine encore compté (ACEL1 / C-ACEL-001). Rien n'a été construit ni
déployé.

## 0. Préconditions

- **SHA.** `origin/main` = `8fc408bf6` (merge de la PR #1415). Branche : `verifie-1511`.
- **Registre.** 60 cochées sur 62 constructibles ; ouvertes : ACEL1, ACEL9 ; 8 bloquées « code livré, preuve en direct
  due » (dont ACEL4 et ACEL31, `@after` d'ACEL1).
- **Échantillon.** Les 5 tâches d'écart du 14/11 (ACEL90 à 94, toutes S3) + ACEL1. Commits lus : `aed87a288` (ACEL90),
  `5aba59293` + `cea851ab3` (ACEL91), `55cf1b1ea` (ACEL92), `8c261c7d5` + `1ff50b094` (ACEL93), `7a9afe720` (ACEL94).
- **Méthode.** Code sur `origin/main`, tests nommés, appelants et jumeaux lus ; corps réels exécutés sur l'hôte par
  extraction ast quand un doute portait sur un chemin réel. Aucune pile, aucun test Django, aucun conteneur, aucune base,
  aucun worker, aucune production.

## 1. Verdicts

| Tâche | Constat d'origine | Verdict | Motif |
|---|---|---|---|
| ACEL1 | C-ACEL-001 (S2) | **non-fait** (ouverte) | `celery.py` : entrée `'reporting-email-saved-reports-daily'` toujours `crontab(hour=6, minute=0)` ; `@after` ACEL31 et ACEL4 bloquées (preuve en direct due) |
| ACEL90 | C-ACEL-VER2-200 (S3) | **partiel** | « fini quand » tenu (solde, relevé des leads) ; l'étape 2 du backfill reste aveugle (§4, VER3-300) |
| ACEL91 | C-ACEL-VER2-201 (S3) | **partiel** | alerte dans la boucle et ordre par id tenus ; le faux « introuvable » subsiste sur le chemin réel (§4, VER3-301) |
| ACEL92 | C-ACEL-VER2-202 (S3) | **ok** | `ged` posée après un routage réussi (`_emettre_document_produit` rend vrai si une réponse n'est pas `None`) |
| ACEL93 | C-ACEL-VER2-203 (S3) | **ok** | `_sauver_en_pause` repasse le job `queued` aux trois sorties `attendre` ; `marquer_progression` le remet `running` |
| ACEL94 | C-ACEL-VER2-204 (S3) | **ok** | handler GED inscrit sur le bus ; relève, tâche, entrée de planning, route et clé d'allowlist retirées |

## 2. Tests nommés

- ACEL90 `test_tasks.py::SyncInsightsRunTests::test_limite_douce_dans_la_lecture_du_solde_fait_echouer_la_synchro` et
  `::test_limite_douce_au_releve_des_leads_fait_echouer_backfill_complet` : comportementaux, échouent si `degrader` est
  retiré du solde ou de l'étape 4. **Non couverts** : `check_account_health` (le faux client lève dès le solde, appelé avant
  la santé dans `_sync_company`, l. 446-455 : un mutant sur la santé reste vert) et les étapes 1 à 3 du backfill.
- ACEL91 `test_xged6_controle_integrite.py::IntegrityCheckTests::test_limite_douce_n_efface_pas_l_alerte_deja_due` :
  patche `apps.records.storage.fetch_attachment` lui-même pour lever, donc AU-DESSUS de l'`except Exception` qui avale
  (`records/storage.py:120`). Il reste vert avec le défaut réel (§4).
- ACEL92 `test_wir165_document_produit_facture.py::DocumentProduitFactureTests::test_routage_en_echec_repris_au_rendu_suivant` :
  vrai routeur en 2e appel, `freeze_time` + `tick(60)`, affirme 0 → (1, 1) → (1, 1) et `ged == empreinte` ; mutant
  « `ged` avant l'émission » rouge. Correct.
- ACEL93 `test_veille_tache.py::QuotaEtRepriseTests::test_job_en_pause_de_quota_jamais_solde_par_le_balayage` : nommé par
  la tâche, non rejoué ici.
- ACEL94 `test_xged9_mail_intake.py::GatingTests::test_une_seule_releve_pour_la_ged_et_le_sav` : passe par le vrai
  `poll_mailbox` et `_dispatch`, handlers restaurés par `addCleanup` (l. 142-145), rejeu sans doublon. Correct.
- Aucun test Django lancé : la seule preuve d'un vert est la CI de la PR #1415 (mergée).

## 3. Sondes, calendrier, gardes

- **Garde.** `python scripts/check_beat_active_companies.py` : « OK » (rc 0). `python -m unittest
  scripts.tests.test_check_beat_active_companies` : 44 tests OK.
- **Calendrier** (script hôte, `beat_schedule` lu par ast, `@shared_task(name=…)` et `CELERY_TASK_ROUTES` par regex) :
  126 entrées (127 hier, moins `ged-poll-mail-intake`), 126 tâches distinctes, toutes définies et routées ; aucune route
  vers une tâche disparue ; `ged.poll_mail_intake` absente du planning, des routes et des définitions ; `git grep
  poll_mail_intake` hors plans/audits : 0. Fuseau : `CELERY_TIMEZONE` et `app.conf.timezone` = Africa/Casablanca,
  `CELERY_ENABLE_UTC = False` ; `visibility_timeout` 5 400 s.
- **Sondes PF11** (rejouées sur l'hôte) :
  - 001 : `repro: true` (passages {6}, rapports à 7/8/9 h jamais dus). **Périmée pour la suite** : elle n'extrait pas
    `_deja_journalise_ce_jour`, qu'ACEL31 appelle désormais dans `_rapport_est_du` ; simulée avec un planning à chaque heure
    (ce que livrera ACEL1), elle plante `NameError: _deja_journalise_ce_jour`. La « preuve en direct » d'ACEL1 (« sonde
    rejouée ⇒ repro False ») est injouable en l'état (§5) ;
  - 002 : plante encore (`NameError: PieceJointeImportee`), 003 inconclusive (`'QS' object has no attribute
    'order_by'`), 004 rend `consigne_dans_le_journal: true` ; inchangé depuis hier, rafraîchissement porté par ACEL9.
- **Preuves hôte des deux écarts** (corps réels extraits par ast, scripts jetables, non déposés) :
  - `records/storage.py::fetch_attachment` avec un faux client MinIO dont `get_object` lève `SoftTimeLimitExceeded` ⇒
    rend `(None, 'Fichier introuvable.')` ; enchaîné à `ged/services.py::_fetch_version_bytes` puis
    `::_hash_constate_pour_archivage` ⇒ rend `None` (archive comptée « indisponible ») ;
  - `adsengine/tasks.py::sync_breakdowns_for_campaign_detailed` avec un faux client dont `get_insights` lève
    `SoftTimeLimitExceeded` ⇒ rend `{'age_gender': {'rows': 0, 'error': 'SoftTimeLimitExceeded: …'}}`, sans lever.

## 4. Écarts retenus

| C-id | Tâche d'origine | Grav. | Écart | Preuve | Tâche |
|---|---|---|---|---|---|
| C-ACEL-VER3-300 | ACEL90 | S3 | `sync_breakdowns_for_campaign_detailed` avale la limite douce par dimension (`except Exception as exc:` → `detail[dimension]['error']`, `continue`, `backend/django_core/apps/adsengine/tasks.py:616`) : l'étape 2 de `backfill_complet` (où ACEL90 a posé `degrader`, l. 1165) ne la voit jamais ; le titre d'ACEL90 promettait « les quatre étapes du backfill » | hôte (corps réel exécuté) | ACEL95 |
| C-ACEL-VER3-301 | ACEL91 | S3 | `fetch_attachment` avale la limite douce (`except Exception:` → `(None, 'Fichier introuvable.')`, `backend/django_core/apps/records/storage.py:120`) : l'`except SoftTimeLimitExceeded: raise` d'ACEL91 dans `_hash_constate_pour_archivage` n'est jamais atteint ; l'archive est comptée « indisponible », `alerter_archives_compromises` envoie une fausse alerte « introuvable » (`alertes_integrite.py:25`) et la boucle continue jusqu'à la limite dure. Le test d'ACEL91 patche au-dessus de l'`except`. Même effet sur `publicapi/bulk.py::_fetch_bytes` (import soldé « Fichier introuvable. » au lieu de la reprise ACEL33) | hôte (corps réels exécutés) | ACEL96 |

**Pourquoi S3.** Même classe que les constats qu'ils prolongent, latents : il faut une lecture réseau qui dépasse 120 s ;
la limite dure (180 s) reste consignée par `task_failure`. VER3-301 produit une fausse alerte de sécurité, sans perte
(l'archive est recontrôlée au passage suivant).

**Routage** (`check_ownership.py --owner-of`) :
- ACEL95 → acquisition (`adsengine/tasks.py`, `adsengine/tests/test_datapub4_audience.py`) ;
- ACEL96 → transverse (`records/storage.py` → securite, `ged/tests/test_xged6_controle_integrite.py` → documents).

**Réfuté ou écarté.**
- ACEL92, factures déjà rendues avant le correctif : leur `pdf_render_meta` vaut `{'empreinte': …}` sans `ged` ; le premier
  rendu explicite après déploiement (bouton, lot) crée une version GED de plus à données inchangées. Une seule fois par
  facture, et seulement sur rendu demandé (`cle_facture_pdf_a_jour` ne re-rend pas à empreinte égale) : optionnel (§5).
- ACEL92, autre récepteur de `document_produit` qui répondrait non-`None` : un seul récepteur (`ged/receivers.py:80`).
- ACEL92, cloisonnement : `RoutageDocumentaire` filtré par `company` ; dédoublonnage `(société, référence)` intact.
- ACEL93, autre balayage des jobs `queued` : aucun (`'queued'` filtré nulle part hors du modèle ; le balayage ne vise que
  `STATUT_RUNNING`, `core/tasks.py:747`).
- ACEL94, re-livraison : si le handler GED lève, le message reste non lu et repasse à TOUS les handlers ; SAV
  (`TicketEmailThread.message_id`, marqueur `[email:<id>]`), ventes (`dedupe_event`) et GED (Message-ID) sont idempotents.
  Aucune autre lecture IMAP dans le code (`imaplib` : `core/email_intake.py` seul).

## 5. Optionnel (non déposé)

- **Sonde 001 périmée** (C-ACEL-VER3-302, S4, outillage) : ajouter `_deja_journalise_ce_jour` (avec un faux
  `EnvoiRapport`) à l'extraction, sinon ACEL1 et ACEL9 ne peuvent pas montrer `repro: false`. À joindre au rafraîchissement
  des sondes 002 à 004 porté par ACEL9.
- ACEL90 : aucun test ne couvre `check_account_health` ni les étapes 1 à 3 de `backfill_complet`.
- ACEL91 : l'`except` par société de `ged/tasks.py::verifier_integrite_archives_task` avale encore la limite (passif gelé
  « à trier » de `scripts/beat_limites_allow.txt`) ; « le passage suivant contrôle les archives restantes » repart de
  l'id le plus bas : si un passage dépasse toujours la limite, la queue n'est jamais contrôlée (volume non mesuré).
- ACEL93 : une chaîne d'étapes perdue pendant une pause (worker tué, message expiré) n'est plus signalée par le balayage ;
  la découverte reste « en pause » au-delà de `reprise_a`, relançable à la main (`veille_decouverte.py::reprendre`).
- ACEL94 : `_dispatch` avale la limite douce d'un handler (`core/email_intake.py:93`) et le marquage lu se fait en fin de
  lot : sous un gros arriéré, la relève peut être tuée avant tout marquage (handlers idempotents, convergence par dédoublonnage).
  Un message qu'un handler refuse toujours reste non lu et revient toutes les 10 min.
- Outillage du registre : `audit_registre.py --du` annonce « écarts S1-S2 tous cochés » alors que le seul S1-S2 compté
  (C-ACEL-001) dépend d'ACEL1, ouverte dans le bloc d'origine et non dans un bloc « ÉCARTS » (`ecarts_tous_coches` ne lit
  que ces blocs) : la contre-visite reviendra sans pouvoir conclure tant qu'ACEL1 n'est pas cochée.

## 6. Couverture et sortie de cycle

- **Couvert.** ACEL1 et les 5 tâches d'écart du 14/11 : code, commits, tests nommés, appelants, jumeaux, idempotence à la
  re-livraison (ACEL92, ACEL94), cloisonnement (ACEL92, ACEL94), planning, routes, fuseau, garde.
- **Non couvert sans pile.** Aucun test Django lancé (ACEL93 non rejoué) ; aucun worker, aucun beat, aucune limite douce
  réelle déclenchée ; volumes réels (archives légales, pauses de quota, boîte IMAP de production) non mesurés ; les 8
  tâches bloquées en attente de preuve en direct.
- **Constats d'origine.** C-ACEL-001 (S2) : **non fermé** (ACEL1 ouverte, sonde `repro: true`). C-ACEL-VER2-202, 203,
  204 : fermés. C-ACEL-VER2-200 et 201 : partiellement fermés (VER3-300, VER3-301).
- **Statut.** Aucun écart S1-S2 nouveau. Le marqueur compte 1 : C-ACEL-001, dont la tâche n'est pas cochée (§C.4.6). Le
  groupe reste « construit », pas « vérifié ». Sortie de cycle : 0 `vérifie` consécutif à zéro S1-S2 (14/11 : 1, 15/11 : 1).
  Il faut ACEL31 et ACEL4 acceptées, puis ACEL1 construite (une ligne de planning) et la sonde 001 rafraîchie ; la
  prochaine contre-visite pourra alors compter 0.

## 7. Coût

- 1 vérificateur (opus, effort de session), rédacteur compris ; jetons non mesurés. Aucun appel Fable, aucun sous-agent.
