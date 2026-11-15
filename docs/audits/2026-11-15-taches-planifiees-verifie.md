<!-- verifie | groupe: ACEL | pct: 96 | ecarts_s1_s2: 1 -->

# Vérifie ACEL — 2e contre-visite des correctifs du parcours PF11 « tâches planifiées », 15/11/2026

Déclencheur : `audit_registre.py --du` (« vérifie dû, contre-visite des correctifs (écarts S1-S2 du 2026-11-15 tous
cochés) », 62/64 = 96 %). Périmètre ÉTROIT (§C.4.6) : les deux tâches d'écart déposées par la passe du matin (ACEL95,
ACEL96, livrées par la PR #1419) et la tâche du constat S2 d'origine encore compté (ACEL1 / C-ACEL-001). Cette 2e passe
du jour REMPLACE le compte rendu du matin (§C.4.5) ; git garde la 1re. Rien n'a été construit ni déployé.

## 0. Préconditions

- **SHA.** `origin/main` = `d9164c12e` (merge de la PR #1419, CI verte : 8 tranches `backend-tests`, `backend-lint`,
  `frontend-lint`, `stage-names` SUCCESS, mergée le 15/11 à 04:12 UTC). Branche : `verifie-1511b`.
- **Registre.** 62 cochées sur 64 constructibles ; ouvertes : ACEL1, ACEL9 ; 8 bloquées « code livré, preuve en direct
  due » (ACEL3, ACEL4, ACEL8, ACEL13, ACEL31, ACEL36, ACEL42, ACEL46).
- **Échantillon.** ACEL95 (commit `bc2d5a782`), ACEL96 (commit `1a8e848bf`), ACEL1.
- **Méthode.** Code sur `origin/main`, tests nommés, appelants et jumeaux lus ; corps réels exécutés sur l'hôte par
  extraction ast avec de faux clients ; relevé ast des `except` larges des tâches Celery et de leurs appelés directs.
  Aucune pile, aucun test Django, aucun conteneur, aucune base, aucun worker, aucune production.

## 1. Verdicts

| Tâche | Constat d'origine | Verdict | Motif |
|---|---|---|---|
| ACEL1 | C-ACEL-001 (S2) | **non-fait** (ouverte) | `celery.py` : `'reporting-email-saved-reports-daily'` toujours `crontab(hour=6, minute=0)` ; sonde 001 `repro: true` |
| ACEL95 | C-ACEL-VER3-300 (S3) | **ok** | `degrader(exc)` dans l'`except` par dimension ; la limite remonte à l'étape 2 de `backfill_complet` ; aucune autre conséquence |
| ACEL96 | C-ACEL-VER3-301 (S3) | **régression** (S3) | « fini quand » tenu, test au bon niveau ; mais un appelant nommé par la tâche reste bloqué `en_file` (§4, VER4-400) |

## 2. Tests nommés

- ACEL95 `test_datapub4_audience.py::BreakdownDiagnosticsTests::test_limite_douce_d_une_dimension_remonte` : faux client
  dont `get_insights` lève, donc SOUS l'`except` par dimension ; mutant « retirer `degrader` » ⇒ la fonction rend un dict,
  `assertRaises` échoue. La branche « autre exception rangée dans `error` » reste tenue par
  `::test_detailed_surfaces_per_dimension_error`. Correct. `MetaClient._request` n'attrape que des exceptions `httpx` :
  rien n'avale la limite entre l'appel réseau et l'`except` corrigé.
- ACEL96 `test_xged6_controle_integrite.py::IntegrityCheckTests::test_limite_douce_au_stockage_n_accuse_pas_l_archive` :
  `apps.records.storage.get_minio_client` patché, la VRAIE `fetch_attachment` exécutée (le défaut du test d'ACEL91 est
  corrigé) ; affirme la remontée, 1 seule alerte (archive A), aucun contrôle pour B, et `RuntimeError` ⇒ « Fichier
  introuvable. ». Mutant « retirer `except SoftTimeLimitExceeded: raise` » ⇒ rouge. Correct.
- Preuve hôte : `fetch_attachment` réelle avec un client levant la limite ⇒ `SoftTimeLimitExceeded` remonte.
- Aucun test Django lancé : la seule preuve d'un vert est la CI de la PR #1419.

## 3. Sondes, calendrier, gardes, relevé

- **Garde.** `python scripts/check_beat_active_companies.py` : « OK » (rc 0). `python -m unittest
  scripts.tests.test_check_beat_active_companies` : 44 tests OK. `scripts/beat_limites_allow.txt` inchangé (63 lignes).
- **Sondes PF11** (rejouées sur l'hôte) : 001 `repro: true` (passages {6}) ; 002 plante (`NameError: PieceJointeImportee`) ;
  003 `repro: false` avec `inconclusif` (`'QS' object has no attribute 'order_by'`) ; 004 `consigne_dans_le_journal: true`.
  Inchangé depuis le matin. La sonde 001 n'extrait toujours pas `_deja_journalise_ce_jour` (0 occurrence) : avec un
  planning horaire, `_heure_ok` devient vrai et l'appel non extrait plante (lu, non rejoué ce soir).
- **Relevé ast.** Toutes les fonctions `@shared_task` de `backend/django_core` (hors tests) et leurs appelés directs
  résolus (même module ou import) : 232 `except` nus / `Exception` / `BaseException` sans relève (ni `raise`, ni
  `degrader`, ni `relever_si_delai`, ni `except SoftTimeLimitExceeded` antérieur), dont 45 autour d'un appel réseau ou
  stockage ; puis suivi à la main des 20 appels de `fetch_attachment` hors tests, la seule primitive que la PR modifie.
- **Preuves hôte des écarts** (corps réels, faux objets) : `bulk.py::run_import_job` avec une `_fetch_bytes` qui passe par
  la vraie `fetch_attachment` levant la limite ⇒ la limite remonte, job resté `en_file`, `marquer_echec` jamais appelé ;
  `portail/receivers.py::_capture_depuis_minio` dans le même cas ⇒ rend `None`.

### 3.1 Excepts réseau / stockage qui avalent encore la limite douce

**Avale et fausse un résultat :**
- `backend/django_core/apps/publicapi/bulk.py:363` (`run_import_job`, lecture du journal d'erreurs) — reprise repartie
  d'un journal vide, arrêt propre ACEL33 contourné → VER4-401.
- `backend/django_core/apps/portail/receivers.py:98` (`_capture_depuis_minio`) — rend `None` ; `deposer_document_ged`
  relance avec `OSError` « octets illisibles », dont l'`except SoftTimeLimitExceeded: raise` (ACEL65) n'est jamais
  atteint ; cause consignée fausse, aucune perte (3 relances). Optionnel (§5).
- `backend/django_core/apps/reporting/scheduled_reports.py:363` (`_send_report_email`) — journal « échec : Envoi refusé
  par le backend email » ; `backend/django_core/apps/reporting/diffusion_views.py:136` (`diffuser_whatsapp`) — numéro non
  compté. Cause faussée ; tâche `email_saved_reports` déjà au passif gelé « à trier ». Optionnel.
- `backend/django_core/apps/adsengine/tasks.py:2262` (`watch_graph_version_eol`) — vigie EOL hebdomadaire sautée sans trace
  d'échec. Optionnel.

**Avale sans conséquence** (statut honnête, best-effort ou repris au passage suivant) : `core/backup.py:249` (run `echec`)
et `:959` (objet repris à la purge suivante) ; `core/tasks.py:456`, `:460`, `:464` (export `echec`), `:498`, `:578` (ligne
gardée et retentée) ; `core/email_intake.py:217` (message re-relevé) ; `apps/publicapi/delivery.py:153` et `:210`
(livraison `failed` retentée, clé d'idempotence) ; `apps/reporting/journal_problemes.py:456` ; `apps/ventes/tasks.py:73` ;
`apps/ventes/scheduled.py:250`, `:932` ; `apps/installations/tasks.py:153` ; 6 sites de `apps/notifications/sweeps.py`,
10 de `apps/stock/` et 4 de `apps/crm/` autour de `notify_many` (classés par le nom de l'appel, non lus un à un).
**Isolation par société au passif gelé** (`scripts/beat_limites_allow.txt`) : `adsengine/tasks.py:685`, `:2000`,
`monitoring/tasks.py:90`, `reporting/rapport_abonnements.py:322`, `reporting/scheduled_reports.py:539`.

### 3.2 Relever la limite a-t-il cassé un comportement voulu ?

- ACEL95 : aucun verrou ni statut ; `sync_breakdowns_weekly` l'avale encore par société (passif gelé), comme avant.
- ACEL96, appelants en tâche : GED (`_hash_constate_pour_archivage` relève, puis `verifier_integrite_archives_task` au
  passif gelé) ; visites (`assembler_photos_toit_task` ne rattrape plus : la visite reste « en cours » mais
  `services.py::expirer_assemblage_perime` (ACEL77) la passe « échec — relancez » après 10 min) ; calepinage, installations
  (lecture hors `try` dans la fonction appelante ; plus haut, non suivi) ; portail (avalé, §3.1) ; **import en masse :
  cassé** (VER4-400).

## 4. Écarts retenus

| C-id | Tâche d'origine | Grav. | Écart | Preuve | Tâche |
|---|---|---|---|---|---|
| C-ACEL-VER4-400 | ACEL96 | S3 | `publicapi/bulk.py::run_import_job` n'attrape que `BulkJobError` à la lecture de la source (l. 344-348) : la limite sort avant `marquer_progression`, le job reste `en_file`, ni soldé par `expirer_jobs_bloques` ni relançable (`relancer_job`) ; avant : `echec` relançable | hôte | ACEL97 |
| C-ACEL-VER4-401 | ACEL96 (jumeau) | S3 | l'`except Exception` autour de la lecture du journal d'erreurs (`backend/django_core/apps/publicapi/bulk.py::run_import_job`, l. 357-365) avale la limite : la reprise repart d'un journal vide, l'arrêt propre ACEL33 n'arrive plus ; un job qui finit dans les 60 s restantes écrit un journal sans les erreurs des passes précédentes | lecture | ACEL97 |

**Pourquoi S3.** Latents : il faut une lecture MinIO de plus de 120 s ; aucune ligne importée n'est perdue ni doublée
(curseur persistant, une transaction par ligne). VER4-400 est un vecteur introduit par la correction : il bloque un
job jusqu'à un nouvel import.

**Routage** (`check_ownership.py --owner-of`) : `publicapi/bulk.py` et `publicapi/tests_aana_reprise_bulk.py` → analyse.
Une tâche : ACEL97 (`docs/plans/PLAN_AUDIT_ANALYSE.md`).

## 5. Optionnel (non déposé)

- `_capture_depuis_minio` (S4) : poser `except SoftTimeLimitExceeded: raise` devant son `except Exception` rendrait à
  `deposer_document_ged` l'arrêt prévu par ACEL65 (propriétaire documents).
- Plus loin qu'un appel direct : `ventes/quote_engine/artefacts_rendu.py::_roof_photo_data_uri` (tâche
  `task_generate_devis_pdf` → moteur → constructeur) avale la limite autour de `fetch_attachment` et rend `""` : le PDF
  client part avec le schéma au lieu de la photo du toit, puis est mis en cache (`_remember_render`). Latent, règle #4 ;
  à trancher par l'orchestrateur.
- Sonde 001 périmée (C-ACEL-VER3-302, S4, toujours ouvert) : ajouter `_deja_journalise_ce_jour` à l'extraction.
- `_send_report_email` / `diffuser_whatsapp` / `watch_graph_version_eol` : cause faussée seulement (§3.1).
- Le relevé suit un seul saut d'appel ; les `except` plus profonds (ex. `calepinage/tasks.py`, élément par élément)
  n'ont pas été classés.

## 6. Couverture et sortie de cycle

- **Couvert.** ACEL95, ACEL96 : code, commits, tests nommés (niveau de la panne, mutant), appelants, jumeaux, statuts de
  job, CI ; ACEL1 : planning ; garde et ses tests ; 4 sondes PF11.
- **Non couvert sans pile.** Aucun test Django lancé ; aucun worker, beat ni limite douce réelle ; les 8 tâches bloquées.
- **Constats d'origine.** C-ACEL-VER3-300 : **fermé**. C-ACEL-VER3-301 : **fermé** (la GED n'accuse plus l'archive), avec
  une régression sur un autre appelant (VER4-400). C-ACEL-001 (S2) : **non fermé** (ACEL1 ouverte, sonde `repro: true`).
- **Ce qui manque pour conclure.** (1) ACEL4 : preuve en direct sur pile locale avec worker et beat (worker arrêté 20 min ;
  le runner GitHub n'a ni Celery ni beat, §C.4.7). (2) ACEL31 et ACEL1 se tiennent mutuellement : ACEL1 porte
  `@after: ACEL31, ACEL4`, et la preuve d'ACEL31 exige « sonde rejouée APRÈS la moitié planning » (= ACEL1) ; ce cycle se
  rompt en construisant ACEL1 (une ligne de planning, le code d'ACEL31 est sur `main`) puis en prouvant les deux ensemble.
  (3) Rafraîchir la sonde 001 (VER3-302), sans quoi `repro: false` est injouable. (4) ACEL97 construite.
- **Statut.** Aucun écart S1-S2 nouveau. Le marqueur compte 1 : C-ACEL-001, dont la tâche n'est pas cochée (§C.4.6). Le
  groupe reste « construit ». Sortie de cycle : 0 `vérifie` consécutif à zéro S1-S2 (14/11 : 1, 15/11 : 1, 15/11 bis : 1).

## 7. Coût

- H0 S0 O1 F0 · jetons sous-agents ≈ 0 M — 1 vérificateur (opus), rédacteur compris ; aucun appel Fable, aucun sous-agent.

## Rappel de la passe du matin

Passe sur `8fc408bf6` (PR #1415) : ACEL90 et ACEL91 **partielles** (la limite douce restait avalée sous elles, dans
`sync_breakdowns_for_campaign_detailed` et `records/storage.py::fetch_attachment` ; le test d'ACEL91 patchait au-dessus
de l'`except` fautif) → C-ACEL-VER3-300 et 301 (S3), tâches ACEL95 et ACEL96 ; ACEL92, ACEL93, ACEL94 **ok** ; ACEL1
**non-fait**. Optionnels : sonde 001 périmée (VER3-302), étapes 1-3 de `backfill_complet` non testées, `_dispatch` de la
relève IMAP qui avale la limite. Marqueur : `pct: 96`, `ecarts_s1_s2: 1` (C-ACEL-001).
