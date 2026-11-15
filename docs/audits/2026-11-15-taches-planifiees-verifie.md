<!-- verifie | groupe: ACEL | pct: 97 | ecarts_s1_s2: 1 -->

# Vérifie ACEL — 4e contre-visite des correctifs du parcours PF11 « tâches planifiées », 15/11/2026

Déclencheur : `audit_registre.py --du` (« vérifie dû, contre-visite des correctifs », 65/67 = 97 %). Périmètre ÉTROIT
(§C.4.6) : les deux tâches d'écart déposées par la 3e passe (ACEL98, ACEL99, livrées par la PR #1423), la tâche du constat
S2 d'origine encore compté (ACEL1 / C-ACEL-001) et le nœud ACEL1 / ACEL31 / ACEL4 ; en marge, ACNC76 (même PR, hors
groupe). Cette 4e passe REMPLACE celle du soir (§C.4.5) ; git garde les trois premières. Rien n'a été construit ni déployé.

## 0. Préconditions

- **SHA.** `origin/main` = `767f1c955` (merge de la PR #1423). ACEL98 : commit `899f1d48f`, ACEL99 : `be86a0064`, fold
  `39dc168a1`, coche `33d533b3e`. ACNC76 : `fbc478cbd`, fold `ffc842a2c`. Branche : `verifie-1511d`.
- **Registre.** 65 cochées sur 67 ; ouvertes : ACEL1, ACEL9 ; bloquées « code livré, preuve en direct due » : ACEL3, ACEL4,
  ACEL8, ACEL13, ACEL31, ACEL36, ACEL42, ACEL46 (compte relu dans `docs/plans/*.md`).
- **Méthode.** Code et tests sur `origin/main`, appelants et jumeaux lus ; corps réels (`run_import_job`, `_parse_rows`,
  `_echec_limite_lecture`, `run_export_job`) extraits par ast et exécutés sur l'hôte avec un faux `BulkJob`, un faux stockage
  et une fausse transaction ; mutants par retrait de chaque `except`. Aucune pile, aucun test Django, aucun conteneur, aucune
  base, aucun worker, aucune production.

## 1. Verdicts

| Tâche | Constat d'origine | Verdict | Motif |
|---|---|---|---|
| ACEL98 | C-ACEL-VER5-500 (S3) | **ok** | `_parse_rows` dans le `try` de la lecture ; limite douce ⇒ `echec` relançable, curseur 0 ; mutant rouge |
| ACEL99 | C-ACEL-VER5-501 (S3) | **ok** | `except (csv.Error, RecursionError)` ⇒ `echec` « Fichier illisible » ; n'avale pas la limite douce ; branche `RecursionError` non testée (S4) |
| ACEL1 | C-ACEL-001 (S2) | **non-fait** (ouverte) | `celery.py` : `'reporting-email-saved-reports-daily'` toujours `crontab(hour=6, minute=0)` ; sonde 001 `repro: true` |
| ACEL31 | C-ACEL-001 (S2) | bloquée (preuve due) | code sur `main` ; preuve = sonde rejouée APRÈS ACEL1 |
| ACEL4 | C-ACEL-007, 022 (S3) | bloquée (preuve due) | code sur `main` (`celery.py::_expire_dans`) ; preuve = pile avec worker arrêté et beat |
| ACNC76 (marge) | C-ACNC-VER2-203 (S3) | **ok** | voir « En marge — ACNC76 » |

## 2. ACEL98 et ACEL99 en détail

- **Code.** `bulk.py::run_import_job` : `rows = _parse_rows(raw, fmt)` déplacé dans le `try` de `_fetch_bytes` (2 lignes) ;
  troisième `except (csv.Error, RecursionError) as exc: return job.marquer_echec(f"Fichier illisible : {exc}")` (2 lignes).
  Ordre : `BulkJobError`, `SoftTimeLimitExceeded`, puis `(csv.Error, RecursionError)`. `issubclass(SoftTimeLimitExceeded,
  csv.Error)` et `issubclass(…, RecursionError)` : faux tous deux (exécuté) — l'`except` neuf n'avale pas la limite douce.
  Aucun `except` élargi : ACEL96/97 intacts (`fetch_attachment` relève, `_echec_limite_lecture` inchangé).
- **Rejeu hôte (corps réels).** Limite douce au découpage ⇒ `echec` « Limite de temps atteinte … ligne 1 », curseur 0 ;
  vraie cellule CSV de 200 000 caractères ⇒ `echec` « Fichier illisible : field larger than field limit (131072) » ; vrai
  JSONL de 100 000 crochets ⇒ `echec` « Fichier illisible : maximum recursion depth exceeded … » ; aucune ligne importée.
- **Mutants hôte.** ACEL98 retiré ⇒ la limite sort, job `en_file`. ACEL99 retiré ⇒ `csv.Error` sort, job `en_file`. Seule
  `RecursionError` retirée du tuple ⇒ la cellule géante reste `echec` (le test d'ACEL99 reste vert) mais le JSONL imbriqué
  sort, job `en_file` : la moitié `RecursionError` du « fini quand » n'a pas de test (VER6-602, S4).
- **Tests** (`tests_aana_reprise_bulk.py::RepriseBulkTest`). `test_limite_douce_au_decoupage_de_la_source_solde_le_job` :
  `bulk._parse_rows` patché pour lever — patch au site même de l'appel (une vraie limite douce exige un worker), puis
  `relancer_job` accepté et reprise sans patch : 2 lignes. `test_source_indecoupable_solde_le_job` : VRAI `_parse_rows`, vraie
  cellule de 200 000 caractères, vrai `_store_import_source` sur magasin en mémoire. Les deux échouent si le correctif saute.
  Aucun test Django lancé : la seule preuve d'un vert est la CI de la PR #1423.
- **Repli inline.** `_dispatch_import` (broker injoignable) : `csv.Error` ne remonte plus dans `POST /imports/` (optionnel
  de la 3e passe fermé).

## 3. Toutes les sorties de `run_import_job` et de son jumeau d'export

Rejoué sur l'hôte pour chaque ligne marquée « R » ; `expirer_jobs_bloques` (beat `*/10`, délai 10 min) solde un `en_cours`
en `echec` « Traitement interrompu (arrêt du serveur) » en 10 à 20 min. `bulk.py` n'envoie aucune notification (grep : 0).

| Point de sortie (import) | Exception | État final |
|---|---|---|
| `BulkJob.objects.get` | `DoesNotExist` / panne base | retour sans job / `en_file` (infrastructure) |
| `_fetch_bytes(source)` | panne stockage, clé absente | `fetch_attachment` rend un message ⇒ `BulkJobError` ⇒ `echec` (R) |
| `_fetch_bytes(source)` | limite douce | `echec` relançable (ACEL97, R) |
| `_parse_rows` | limite douce / `csv.Error` / `RecursionError` | `echec` (ACEL98/99, R) |
| `_parse_rows` | `MemoryError` | sort, `en_file` (non rejoué, S4) |
| lecture du journal précédent | limite douce / autre | `echec` (ACEL97) / journal vide consigné |
| 1er `marquer_progression` | panne base ou limite dans l'écriture | `en_file` (fenêtre de quelques ms, S4) |
| boucle : `row.get` sur valeur JSON non-objet | `AttributeError` | **`en_cours` ⇒ balai ⇒ `echec` faux, relance rejoue la même ligne sans fin (VER6-600, S3, R)** |
| ligne : limite douce | — | journal écrit, `echec` relançable (ACEL33) ; si ce dépôt lève : `en_cours` ⇒ balai |
| ligne : autre exception | — | ligne en erreur, on continue |
| `marquer_progression` par ligne | limite douce | `en_cours` ⇒ balai ; la ligne commise est rejouée à la relance (VER5-504, R : B importée deux fois) |
| `_ecrire_journal` final | limite douce / panne MinIO | `en_cours` ⇒ balai ⇒ relance ⇒ `termine` avec `erreurs = N` et journal vide (VER6-601, S4, R) |
| `marquer_termine` | panne base | `en_cours` ⇒ balai |

**Export** (`run_export_job`) : `queryset.count()` hors `try` avant `marquer_progression` ⇒ `en_file` sur panne base (S4) ;
la boucle est sous `except Exception` (limite douce comprise) ⇒ `echec` ; `store_export_result` final hors `try` ⇒ `en_cours`
⇒ balai ⇒ relance qui réécrit tout (AANA35). Aucun `en_file` à vie déclenchable par le contenu.

**Verdict de l'énumération.** Depuis ACEL98/99, aucun fichier de l'intégrateur ne laisse plus un job `en_file` à vie. Reste
un chemin déclenchable par le fichier qui laisse le job `en_cours` puis le solde faussement : VER6-600.

## 4. Écarts retenus

| C-id | Tâche d'origine | Grav. | Écart | Preuve | Tâche |
|---|---|---|---|---|---|
| C-ACEL-VER6-600 | — (site d'ACEL99) | S3 | `publicapi/bulk.py::run_import_job` : `row.get` hors du `try` de ligne, `_parse_rows` accepte toute valeur JSON ; une ligne non-objet (`[1, 2]`, `5`, `null`) lève `AttributeError` : `en_cours`, suite jamais traitée, balai ⇒ `echec` faux, relance ⇒ boucle | hôte | ACEL100 |
| C-ACEL-VER6-601 | ACEL33 / ACEL97 (principe) | S4 | `run_import_job` : le journal d'erreurs n'existe qu'en mémoire jusqu'à `marquer_termine(erreurs_file_key=_ecrire_journal())` ; une limite douce ou une panne MinIO pendant ce dépôt finit, après balai et relance, en `termine` avec `erreurs = 1` et aucun journal | hôte | optionnel |
| C-ACEL-VER6-602 | ACEL99 | S4 | branche `RecursionError` sans test : mutant `except (csv.Error,)` survit au test d'ACEL99 | hôte | optionnel |
| C-ACEL-VER6-603 | — (sonde) | S4 | sonde 004 périmée : les deux tâches stock lèvent `NameError: active_companies` dans la sonde (non injecté) ; son `defaut: false` ne prouve plus rien | hôte | optionnel |

**Preuve hôte VER6-600.** Fichier `{"nom":"A"}` / ligne non-objet / `{"nom":"C"}` : sortie `AttributeError: 'list' object has
no attribute 'get'` (et `int`, `NoneType`, `str`), statut `en_cours`, curseur 1, importés `['A']`, `C` jamais traité. Correctif
proposé rejoué (valeur non-dict ⇒ `{'__parse_error__': 'objet JSON attendu'}` dans `_parse_rows`) : `termine`, curseur 3,
`erreurs = 1`, journal posé, importés `['A', 'C']`, pour les quatre formes. Le journal de la passe est perdu ; en repli
inline l'`AttributeError` remonte dans `POST /imports/` (500) ; la docstring promet « une ligne en erreur n'arrête JAMAIS
les suivantes ».

**Pourquoi S3.** Déterministe et déclenché par le fichier de l'intégrateur, comme VER5-501 ; aucun lead perdu ni doublé, mais
l'import ne finit jamais, le message est faux et la relance est un piège. VER6-601 reste S4 : fenêtre étroite (dépôt final),
le correctif demande un journal persisté au fil de l'eau (choix de conception, non déposé).

**Routage** (`check_ownership.py --owner-of`) : `publicapi/bulk.py`, `publicapi/tests_aana_reprise_bulk.py` → analyse.
Une tâche : ACEL100, dans `docs/plans/PLAN_AUDIT_ANALYSE.md`.

## 5. Nœud ACEL1 / ACEL31 / ACEL4 (C-ACEL-VER5-502, VER5-503 — toujours valables)

- `plan_lanes.py docs/plans/PLAN_AUDIT_DEPLOY.md` (rejoué ce soir) : « REFUSÉ (@after externe, OWN) : ACEL1 — attend ACEL31 …
  pas encore cochée ; attend ACEL4 … pas encore cochée ». Le cycle ACEL1 ↔ ACEL31 est intact ; la Given d'ACEL1 dit encore
  « la tâche analyse de C-ACEL-001 cochée ».
- Proposition inchangée (à porter par l'orchestrateur) : retirer `(@after: ACEL31, ACEL4)` d'ACEL1, réécrire sa Given sur « le
  code d'ACEL31 sur `main` (`_deja_journalise_ce_jour`) », et dans le même geste l'amender en `crontab(minute=0, hour='6-23')`
  + `'options': _expire_dans(3600)` (l'écran dit toujours « Vide : 6 h ; de 0 à 5 h, part à 6 h »,
  `EnvoisProgrammesPage.jsx`), test `set(range(6, 24))`, sonde 001 qui lit les plages `a-b`.

## 6. Garde, sondes

- `python scripts/check_beat_active_companies.py` : « OK » (rc 0). `python -m unittest
  scripts.tests.test_check_beat_active_companies` : 44 tests, OK. `scripts/beat_limites_allow.txt` : 63 lignes, inchangé.
- Sondes PF11 (hôte) : 001 `repro: true` (rapports réglés à 7, 8, 9 h jamais dus) ; 002 plante (`NameError:
  PieceJointeImportee`) ; 003 `repro: false`, `inconclusif` (`'QS' object has no attribute 'order_by'`) ; 004 `repro: false`
  mais périmée (VER6-603).

## En marge — ACNC76 (hors groupe, ne compte pas dans le marqueur)

- **Code.** `facture_portes.py::refuser_portes_sous_verrou` relit le BC par `type(bc).objects.select_for_update().get(pk=…)`
  (aucun import de modèle ventes) et rejoue `refuser_portes_fermees` sur la copie fraîche ; `FactureViewSet.perform_create`
  ouvre `transaction.atomic()` autour de cet appel ET de `create_provisoire` : le verrou est tenu jusqu'au commit de l'INSERT.
- **Gardes rejouées sur la ligne relue.** Les deux portes BC (`devis_id` ⇒ 409 `bon_commande_de_devis`, `statut == annule` ⇒
  409 `bon_commande_annule`) et celle du `devis` du corps. Le premier appel sans verrou reste (échec rapide, sans effet).
- **Ordre des verrous.** Le formulaire ne verrouille QUE le BC, et seulement un BC sans devis (un BC de devis est refusé avant
  la transaction) ; `create_provisoire` ne prend aucun verrou (lu). `BonCommandeViewSet.annuler` : verrou BC puis lecture des
  factures — même ordre, le perdant voit l'autre. `facturer_vente` verrouille le devis puis SON BC (de devis) : ressource
  disjointe du formulaire, aucun cycle possible. Pas d'inversion.
- **Test.** `test_aud118_annuler_bc_facture.py::AnnulerBcConcurrenceTests::test_creer_facture_crud_croise_annuler` (deux
  connexions) : écrivain bloqué puis 409, aucune facture. Mutant sans `select_for_update` : l'INSERT bloque encore sur la clé
  étrangère (FOR KEY SHARE contre FOR UPDATE) mais aboutit en 201 après le commit ⇒ l'assertion 409 échoue : le test
  discrimine. Non exécuté ici (pas de pile).
- **Verdict : ok.** Aucun écart `C-ACNC-VER6-6NN`.

## 7. Couverture et sortie de cycle

- **Couvert.** ACEL98/99 : code, commits, tests nommés (niveau de la panne, mutants hôte), appelants, statuts de job,
  énumération des sorties d'import et d'export ; ACEL1 / ACEL31 / ACEL4 : planning, `plan_lanes` ; garde et tests ; 4 sondes ;
  ACNC76 en marge.
- **Non couvert sans pile.** Aucun test Django lancé (y compris le test à deux connexions d'ACNC76) ; aucune limite douce
  réelle, aucun worker ni beat ; preuves en direct d'ACEL31 et ACEL4.
- **Constats d'origine.** C-ACEL-VER5-500 : **fermé**. C-ACEL-VER5-501 : **fermé** (test partiel, VER6-602). C-ACEL-001 (S2) :
  **non fermé** (ACEL1 ouverte, sonde `repro: true`).
- **Statut.** Aucun écart S1-S2 nouveau. Le marqueur compte 1 : C-ACEL-001, dont les tâches ne sont pas cochées (§C.4.6).
  Le groupe reste « construit ». Sortie de cycle : 0 `vérifie` consécutif à zéro S1-S2 (14/11 : 1 ; 15/11 : 1, 1, 1, 1).

## 8. Coût

- H0 S0 O1 F0 · jetons sous-agents ≈ 0 M — 1 vérificateur (opus), rédacteur compris ; aucun appel Fable, aucun sous-agent.

## Rappel des passes précédentes du jour

**1re passe (matin, `8fc408bf6`, PR #1415).** ACEL90 et ACEL91 **partielles** (limite douce avalée sous elles, dans
`sync_breakdowns_for_campaign_detailed` et `records/storage.py::fetch_attachment`) → C-ACEL-VER3-300, 301 (S3), tâches ACEL95,
ACEL96 ; ACEL92-94 **ok** ; ACEL1 **non-fait**. Optionnels : sonde 001 périmée (VER3-302), étapes 1-3 de `backfill_complet` non
testées, `_dispatch` IMAP qui avale la limite.

**2e passe (après-midi, `d9164c12e`, PR #1419).** ACEL95 **ok** ; ACEL96 **régression** S3 (import en masse resté `en_file`) →
C-ACEL-VER4-400, 401 (S3), tâche ACEL97 ; ACEL1 **non-fait**.

**3e passe (soir, `5290db5da`, PR #1421).** ACEL97 **ok** ; jumeau adjacent → C-ACEL-VER5-500, 501 (S3), tâches ACEL98, ACEL99 ;
VER5-502 (nœud `@after` ACEL1 ↔ ACEL31) et VER5-503 (ACEL1 doit viser 6-23 h) en S4, toujours valables (§5) ; VER5-504 (ligne
rejouée si la limite tombe entre le commit d'une ligne et l'avance du curseur), S4 optionnel, toujours ouvert (§3, rejoué).
Marqueur des trois passes : `ecarts_s1_s2: 1` (C-ACEL-001).

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
- Numéros de ligne relevés sur `d9164c12e` ; ceux de `bulk.py` ont bougé de +2 à +15 avec ACEL97-99.
