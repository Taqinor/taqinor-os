<!-- verifie | groupe: ACEL | pct: 96 | ecarts_s1_s2: 1 -->

# Vérifie ACEL — 3e contre-visite des correctifs du parcours PF11 « tâches planifiées », 15/11/2026

Déclencheur : `audit_registre.py --du` (« vérifie dû, contre-visite des correctifs (écarts S1-S2 du 2026-11-15 tous
cochés) », 63/65 = 96 %). Périmètre ÉTROIT (§C.4.6) : la tâche d'écart déposée par la 2e passe (ACEL97, livrée par la
PR #1421), la tâche du constat S2 d'origine encore compté (ACEL1 / C-ACEL-001) et le nœud ACEL1 / ACEL31 / ACEL4. Cette
3e passe REMPLACE celle de l'après-midi (§C.4.5) ; git garde les deux premières. Rien n'a été construit ni déployé.

## 0. Préconditions

- **SHA.** `origin/main` = `5290db5da` (merge de la PR #1421). ACEL97 : commit `29718cc57`, fold `1aa94c09c`, coche
  `7927d0ac3`. Branche : `verifie-1511c`.
- **Registre.** 63 cochées sur 65 constructibles ; ouvertes : ACEL1, ACEL9 ; bloquées « code livré, preuve en direct
  due » : ACEL3, ACEL4, ACEL8, ACEL13, ACEL31, ACEL36, ACEL42, ACEL46.
- **Méthode.** Code et test sur `origin/main`, appelants et jumeaux lus ; corps réels (`run_import_job`,
  `_echec_limite_lecture`, `_fetch_bytes`, `_parse_rows`, `_due_schedules`, `_heure_ok`, `_rapport_est_du`) extraits par ast
  et exécutés sur l'hôte avec un faux `BulkJob` et un faux stockage ; mutant par retrait des deux `except` ACEL97. Aucune
  pile, aucun test Django, aucun conteneur, aucune base, aucun worker, aucune production.

## 1. Verdicts

| Tâche | Constat d'origine | Verdict | Motif |
|---|---|---|---|
| ACEL97 | C-ACEL-VER4-400, VER4-401 (S3) | **ok** | « fini quand » tenu, test au bon niveau, mutant rouge ; jumeau adjacent resté ouvert (§4, VER5-500) |
| ACEL1 | C-ACEL-001 (S2) | **non-fait** (ouverte) | `celery.py` : `'reporting-email-saved-reports-daily'` toujours `crontab(hour=6, minute=0)` ; sonde 001 `repro: true` |
| ACEL31 | C-ACEL-001 (S2) | bloquée (preuve due) | code sur `main` (`_heure_ok` en `>=`, `_deja_journalise_ce_jour`) ; preuve = sonde rejouée APRÈS ACEL1 |
| ACEL4 | C-ACEL-007, 022 (S3) | bloquée (preuve due) | code sur `main` (`celery.py::_expire_dans`) ; preuve = pile avec worker arrêté 20 min et beat |

## 2. ACEL97 en détail

- **Code.** `bulk.py::run_import_job` : `except SoftTimeLimitExceeded: return _echec_limite_lecture(job)` derrière la lecture
  de la source (après `except BulkJobError`) et DEVANT l'`except Exception` de la lecture du journal ; `_echec_limite_lecture`
  appelle `marquer_echec` « Limite de temps atteinte — relancez le job, il reprend à la ligne {cursor + 1} » (même forme que
  ACEL33 et `expirer_jobs_bloques`). 11 lignes nettes.
- **État soldé et relançable.** `marquer_echec` pose `echec` depuis `en_file` ; `relancer_job` accepte `echec` ;
  `expirer_jobs_bloques` n'a plus à le prendre (il ne vise que `en_cours`, le job n'y passe jamais). Exécuté : limite à la
  source ⇒ `echec`, relançable ; limite au journal d'un job relancé (curseur 1) ⇒ `echec`, curseur 1, `erreurs_file_key`
  inchangé.
- **Reprise.** Le journal n'est jamais relu vide : la clé reste posée, la relance le relit ; aucune ligne n'est traitée
  pendant la passe interrompue (retour avant `marquer_progression`), donc rien n'est importé deux fois par CE chemin.
- **Arrêt propre ACEL33.** Rétabli : le job rend la main dès la limite, au lieu de continuer sur un journal vide jusqu'à la
  limite dure.
- **Test.** `tests_aana_reprise_bulk.py::RepriseBulkTest::test_limite_douce_a_la_lecture_du_stockage_solde_le_job` : le
  faux client MinIO lève sur UNE clé, donc SOUS les deux `except` fautifs (vraie `fetch_attachment` d'ACEL96, vraie
  `_fetch_bytes`). Mutant hôte (les deux `except` retirés) : source ⇒ la limite remonte, job `en_file` ; journal ⇒ avalé,
  job `termine` sur journal vide. Le test échoue donc sur les deux. Ligne morte `self.magasin_lire_normal = None` (forme).
- Aucun test Django lancé : la seule preuve d'un vert est la CI de la PR #1421.

## 3. Garde, sondes, jumeaux

- **Garde.** `python scripts/check_beat_active_companies.py` : « OK » (rc 0). `python -m unittest
  scripts.tests.test_check_beat_active_companies` : 44 tests OK. `scripts/beat_limites_allow.txt` : 63 lignes, inchangé.
- **Sondes PF11** (hôte) : 001 `repro: true` (passages {6}) ; 002 plante (`NameError: PieceJointeImportee`) ; 003
  `repro: false`, `inconclusif` (`'QS' object has no attribute 'order_by'`) ; 004 `repro: false`,
  `consigne_dans_le_journal: true`. Inchangé depuis le matin.
- **Jumeaux du schéma `en_file → en_cours → terminé/échec`.** `run_export_job` : seul `queryset.count()` précède
  `marquer_progression`, puis l'`except Exception` solde `echec` ; aucun stockage lu. `adsengine/veille_decouverte.py::
  executer_etape` : étape dans une transaction atomique (annulée par la limite), `reprendre` accepte tout statut non
  final. `stock/tasks.py::export_mouvements_xlsx_task` : passe `running` d'abord, `except Exception` ⇒ échec.
  `dataimport.ImportJob` : synchrone, pas de tâche. Aucun ne reste bloqué. Le seul trou est dans `run_import_job` (§4).

## 4. Écarts retenus

| C-id | Tâche d'origine | Grav. | Écart | Preuve | Tâche |
|---|---|---|---|---|---|
| C-ACEL-VER5-500 | ACEL97 (jumeau) | S3 | `publicapi/bulk.py::run_import_job` : `_parse_rows` hors de tout `try`, avant le premier `marquer_progression` ; une limite douce au découpage laisse le job `en_file` (1er passage, ou après `relancer_job`), ni expiré ni relançable, compté « en cours » par `monitoring.py::jobs_recents` | hôte | ACEL98 |
| C-ACEL-VER5-501 | — (même site) | S3 | `publicapi/bulk.py::_parse_rows` n'attrape que `ValueError`/`TypeError` : une cellule CSV de plus de 131 072 caractères (`csv.Error`) ou un JSONL trop imbriqué (`RecursionError`) sort de `run_import_job`, job `en_file` à vie ; déclenchable par le fichier de l'intégrateur, sans limite douce | hôte | ACEL99 |
| C-ACEL-VER5-502 | ACEL1 / ACEL31 | S4 | nœud `@after` : proposition de déblocage (§5) | `plan_lanes` | — |
| C-ACEL-VER5-503 | ACEL1 | S4 | ACEL1 prescrit `crontab(minute=0)` (0-23 h, test `set(range(24))`) ; l'écran livré par ACEL31 dit « Vide : 6 h ; de 0 à 5 h, part à 6 h » (`EnvoisProgrammesPage.jsx`) et le « Hors périmètre » d'ACEL31 dit « de 6 h à 23 h » | hôte | amender ACEL1 (§5) |
| C-ACEL-VER5-504 | ACEL33 / ACEL83 (antérieur) | S4 | `publicapi/bulk.py::run_import_job` : `succes += 1` est dans le `try` APRÈS le commit de la ligne et `marquer_progression` hors de la transaction ; une limite (ou un arrêt) entre les deux rejoue la ligne à la relance (lead doublé en mode `create`) ; fenêtre de quelques ms | lecture | optionnel |

**Preuves hôte.** VER5-500 : `run_import_job` réel avec un découpage qui lève ⇒ la limite remonte, job `en_file`,
`expirable` et `relançable` faux (1er passage et après relance). VER5-501 : vrai `_parse_rows` ⇒ `Error field larger than
field limit (131072)` sur une cellule de 200 000 caractères, `RecursionError` sur 100 000 crochets imbriqués.

**Pourquoi S3.** Aucune ligne perdue ni doublée ; l'intégrateur peut redéposer un import. Mais le job reste « en file »
sans message, refusé par `relancer`, et l'écran de supervision le compte « en cours » à vie. VER5-501 est déterministe.

**Routage** (`check_ownership.py --owner-of`) : `publicapi/bulk.py`, `publicapi/tests_aana_reprise_bulk.py` → analyse.
Deux tâches : ACEL98, ACEL99 (`@after: ACEL98`, même fichier), dans `docs/plans/PLAN_AUDIT_ANALYSE.md`.

## 5. Nœud ACEL1 / ACEL31 / ACEL4 — proposition (C-ACEL-VER5-502, VER5-503)

- **Constat du nœud.** `plan_lanes.py` (rejoué ce soir) : « REFUSÉ (@after externe, OWN) : ACEL1 — attend ACEL31 … pas
  encore cochée ; attend ACEL4 … pas encore cochée ». ACEL31 ne peut être cochée qu'avec la « sonde rejouée APRÈS la
  moitié planning » (= ACEL1 construite) ; ACEL4 attend une pile avec worker et beat. Cycle ACEL1 ↔ ACEL31.
- **Proposition (à porter par l'orchestrateur, plan non modifié ici).** RETIRER `(@after: ACEL31, ACEL4)` de ACEL1
  (`docs/plans/PLAN_AUDIT_DEPLOY.md`), sans l'inverser : les deux codes dont ACEL1 dépend sont sur `main`
  (`scheduled_reports.py::_deja_journalise_ce_jour` d'ACEL31, `celery.py::_expire_dans` d'ACEL4), et un `@after` vers une
  tâche ouverte d'un autre plan est interdit par §C.2 hors moitié de contrat M0. Remplacer dans son Given « la tâche analyse
  de C-ACEL-001 cochée » par « le code d'ACEL31 sur `main` (`_deja_journalise_ce_jour`) ». Puis : ACEL1 construite ⇒ sonde
  001 rejouée ⇒ preuve d'ACEL31 jouée sur la pile, les deux cochées ensemble. ACEL4 reste bloquée sur sa propre preuve.
- **Amendement d'ACEL1 dans le même geste (VER5-503).** Exécuté sur les corps réels : avec 0-23 h, un rapport sans heure
  part à 0 h et un rapport réglé à 3 h part à 3 h ; avec 6-23 h, 6 h et 6 h, comme l'écran le promet (et la règle N4 « rien
  la nuit »). Écrire `crontab(minute=0, hour='6-23')` + `'options': _expire_dans(3600)`, test `schedule.hour ==
  set(range(6, 24))`, et faire lire les plages `a-b` à `heures_de` de la sonde 001 (aujourd'hui « 6-23 » donne un ensemble
  vide ⇒ `repro` resterait vrai). La sonde doit aussi extraire ou simuler `_deja_journalise_ce_jour` (VER3-302, ouvert).

## 6. Optionnel (non déposé)

- VER5-504 : faire avancer le curseur DANS la transaction de la ligne (`marquer_progression` sous `transaction.atomic()`)
  fermerait la fenêtre post-commit ; antérieur à ACEL97, hors de ses `Files:` de fait.
- `_capture_depuis_minio`, `_roof_photo_data_uri` (règle #4), `_send_report_email`, `diffuser_whatsapp`,
  `watch_graph_version_eol` : inchangés depuis la 2e passe (rappel ci-dessous).
- Repli inline de `_dispatch_import` (broker injoignable) : `csv.Error` y remonterait dans la requête `POST /imports/`.
  Non rejoué.

## 7. Couverture et sortie de cycle

- **Couvert.** ACEL97 : code, commits, test nommé (niveau de la panne, mutant hôte), appelants, statuts de job, jumeaux de
  schéma ; ACEL1 / ACEL31 / ACEL4 : planning, code sur `main`, `plan_lanes` ; garde et ses tests ; 4 sondes PF11.
- **Non couvert sans pile.** Aucun test Django lancé ; aucun worker, beat ni limite douce réelle ; preuves en direct
  d'ACEL31 et ACEL4 ; écran « Envois programmés » non ouvert (indication lue dans le source).
- **Constats d'origine.** C-ACEL-VER4-400 : **fermé** pour la lecture de la source ; le même motif reste au découpage
  (VER5-500). C-ACEL-VER4-401 : **fermé**. C-ACEL-001 (S2) : **non fermé** (ACEL1 ouverte, sonde `repro: true`).
- **Statut.** Aucun écart S1-S2 nouveau. Le marqueur compte 1 : C-ACEL-001, dont les tâches ne sont pas cochées (§C.4.6).
  Le groupe reste « construit ». Sortie de cycle : 0 `vérifie` consécutif à zéro S1-S2 (14/11 : 1 ; 15/11 : 1, 1, 1).

## 8. Coût

- H0 S0 O1 F0 · jetons sous-agents ≈ 0 M — 1 vérificateur (opus), rédacteur compris ; aucun appel Fable, aucun sous-agent.

## Rappel des passes précédentes du jour

**1re passe (matin, `8fc408bf6`, PR #1415).** ACEL90 et ACEL91 **partielles** (limite douce avalée sous elles, dans
`sync_breakdowns_for_campaign_detailed` et `records/storage.py::fetch_attachment` ; test d'ACEL91 patché au-dessus de
l'`except` fautif) → C-ACEL-VER3-300, 301 (S3), tâches ACEL95, ACEL96 ; ACEL92-94 **ok** ; ACEL1 **non-fait**.
Optionnels : sonde 001 périmée (VER3-302), étapes 1-3 de `backfill_complet` non testées, `_dispatch` IMAP qui avale la limite.

**2e passe (après-midi, `d9164c12e`, PR #1419).** ACEL95 **ok** ; ACEL96 **régression** S3 (import en masse resté
`en_file`) → C-ACEL-VER4-400, 401 (S3), tâche ACEL97 ; ACEL1 **non-fait**. Marqueur : `pct: 96`, `ecarts_s1_s2: 1`.

**Relevé ast de référence (2e passe).** Toutes les `@shared_task` de `backend/django_core` (hors tests) et leurs appelés
directs résolus : 232 `except` nus / `Exception` / `BaseException` sans relève (ni `raise`, ni `degrader`, ni
`relever_si_delai`, ni `except SoftTimeLimitExceeded` antérieur), dont 45 autour d'un appel réseau ou stockage.

- *Avale et fausse un résultat :* `apps/publicapi/bulk.py:363` (journal d'erreurs — FERMÉ par ACEL97) ;
  `apps/portail/receivers.py:98` (`_capture_depuis_minio`, rend `None`, cause consignée fausse) ;
  `apps/reporting/scheduled_reports.py:363` (`_send_report_email`) ; `apps/reporting/diffusion_views.py:136`
  (`diffuser_whatsapp`) ; `apps/adsengine/tasks.py:2262` (`watch_graph_version_eol`).
- *Avale sans conséquence :* `core/backup.py:249`, `:959` ; `core/tasks.py:456`, `:460`, `:464`, `:498`, `:578` ;
  `core/email_intake.py:217` ; `apps/publicapi/delivery.py:153`, `:210` ; `apps/reporting/journal_problemes.py:456` ;
  `apps/ventes/tasks.py:73` ; `apps/ventes/scheduled.py:250`, `:932` ; `apps/installations/tasks.py:153` ; 6 sites de
  `apps/notifications/sweeps.py`, 10 de `apps/stock/`, 4 de `apps/crm/` autour de `notify_many` (classés par nom d'appel).
- *Isolation par société au passif gelé* (`scripts/beat_limites_allow.txt`) : `adsengine/tasks.py:685`, `:2000`,
  `monitoring/tasks.py:90`, `reporting/rapport_abonnements.py:322`, `reporting/scheduled_reports.py:539`.
- Numéros de ligne relevés sur `d9164c12e` ; ceux de `bulk.py` ont bougé de +2 à +11 avec ACEL97.
