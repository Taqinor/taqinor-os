<!-- verifie | groupe: ACEL | pct: 98 | ecarts_s1_s2: 0 | faits: 74 -->

# Vérifie ACEL — 6e contre-visite des correctifs du parcours PF11 « tâches planifiées », 17/11/2026

Déclencheur : `audit_registre.py --du` (« vérifie dû, contre-visite des correctifs (écarts S1-S2 du 2026-11-16 tous cochés) »,
74/75 = 98 %). Périmètre ÉTROIT (§C.4.6) : les tâches cochées depuis le 15/11 — ACEL1 (constat S2 d'origine C-ACEL-001),
ACEL101 (tâche d'écart du 16/11), ACEL31 (moitié logique de C-ACEL-001) — et ce qu'elles ont pu casser ; ACEL4, 13, 36, 42,
46, cochées par la vague d'acceptation 6, sont relues sur leur seul enregistrement. Rien n'a été construit ni déployé.

## 0. Préconditions

- **SHA.** `origin/main` = `0d834aa12` (merge de la PR #1458). ACEL1 : commit `37b0034bd` ; ACEL101 : `365fa0d99` ; tous deux
  sur `main` par la PR #1443 (mergée le 17/11 03:30 UTC, `backend-tests` 8 shards, `backend-lint`, `frontend-lint`,
  `stage-names` : SUCCESS, lu par `gh pr view 1443`). ACEL31 : coche `68172d199` (acceptation vague 8). Branche : `verifie-1711`.
- **Registre.** 74 cochées sur 75 constructibles ; ouverte : ACEL9 (`@acceptation`) ; bloquées « code livré, preuve en direct
  due » : ACEL3, ACEL8.
- **Méthode.** Code et tests sur `origin/main`, appelants lus (grep `email_saved_reports`, `journaliser_envoi`,
  `_send_report_email`, `derniere_verifie`) ; sonde 001 rejouée sur le vrai `celery.py` ; planning beat relu par ast (126
  entrées) contre les `@shared_task` et `CELERY_TASK_ROUTES` ; tests du dépôt lancés sur l'hôte. Aucune pile, aucun test
  Django, aucun worker ni beat, aucune production, aucun Docker.

## 1. Verdicts

| Tâche | Constat d'origine | Verdict | Motif |
|---|---|---|---|
| ACEL1 | C-ACEL-001 (S2) | **ok** | entrée `reporting-email-saved-reports` = `crontab(minute=0, hour='6-23')` + `_expire_dans(3600)` ; sonde 001 `repro: false` ; test rouge sur l'ancien planning, vert en CI |
| ACEL31 | C-ACEL-001 (S2) | **ok** | `_heure_ok` = heure atteinte, `_deja_journalise_ce_jour` = une ligne par rapport et par jour local, filtre société du rapport ; test à passages horaires |
| ACEL101 | C-ACEL-VER7-702 (S3) | **ok** | `faits:` lu dans le marqueur ; contre-visite tue tant qu'aucune coche nouvelle ; 21 tests verts sur l'hôte |
| ACEL4, 13, 36, 42, 46 | (dossier PF11) | ok (relecture légère) | cochées sur l'enregistrement `6a7a93452` (ACEL4 : vrai beat + vrai worker, `acel2.spec.js`) ; test « rouge d'abord » de chacune présent sur `main` ; code non relu en détail ici |

## 2. ACEL1 + ACEL31 : la règle de l'écran contre le planning

- **Planning.** `erp_agentique/celery.py` : une seule entrée lance `reporting.email_saved_reports` ; `app.conf.timezone =
  'Africa/Casablanca'`, `enable_utc = False` (l. 41-42) : les heures 6-23 sont celles de Casablanca. Route `scheduled`
  (`settings/base.py`, clé `reporting.email_saved_reports`).
- **Heure choisie (D-ACEL-1 = heure_respectee).** `scheduled_reports.py::_rapport_est_du` = cadence ⇒ `_heure_ok` (`heure
  is None or now.hour >= heure`) ET pas de `EnvoiRapport` depuis minuit local (`_deja_journalise_ce_jour`, filtre
  `company_id` + `saved_report` du rapport). Toute branche normale de la boucle après « dû » journalise (envoyé, échec, non
  configuré, sans destinataire, WhatsApp) : le marqueur de déduplication est posé à chaque passage dû ; seule une exception
  hors des `try` internes (attrapée l. 539) ou un `journaliser_envoi` qui échoue laisse le rapport sans marqueur, donc repris
  au passage suivant (hypothétique, non retenu).
- **Sonde 001 rejouée** (hôte, vraies `_due_schedules` / `_heure_ok` / `_rapport_est_du`, journal du jour simulé) :
  passages lus = 6…23 ; 7 h → [7], 8 h → [8], 9 h → [9], 3 h → [6], vide → [6] ; `plus_d_un_envoi_par_jour` : [] ;
  `conforme_a_l_ecran_3h_et_vide_a_6h` : vrai, vrai ; `repro: false`. La sonde est à jour du code : la substitution de
  `_deja_journalise_ce_jour` par un journal en mémoire reproduit la règle (une ligne posée à chaque passage dû).
- **Écran.** `EnvoisProgrammesPage.jsx` : « Heure d'envoi (0-23, heure de Casablanca) », aide « Vide : 6 h ; de 0 à 5 h, part
  à 6 h. » — conforme au planning et à la sonde. Seul le résumé de liste dit « à 3 h » pour un rapport qui part à 6 h (S4, §5).
- **Tests.** `test_qx11_beat_reachability.py::Qx11BeatReachabilityTests::test_rapports_programmes_passent_chaque_heure` :
  une seule entrée, `hour == set(range(6, 24))`, `minute == {0}`, `0 < expires <= 3600` ; les deux mutants (`hour=6`, `hour`
  retiré) le font échouer (par lecture : `{6}` et `set(range(24))` ≠ 6…23 ; non exécuté, pas de Celery sur l'hôte) ; `test_passages_frequents_expirent` ignore l'entrée (heure bornée), inchangé.
  `tests_ntdata38_cadences.py::FenetreHoraireTests::test_passages_horaires_une_ligne_par_jour_a_l_heure_atteinte` : lundi A
  [8] B [6], mardi sans passage de 8 h A [9] B [6], 4 messages, passe rejouée sans ligne de plus. Verts en CI (#1443).
- **Ce que le passage horaire pouvait casser — relu.** Idempotence à la re-livraison (`acks_late`) : un rapport déjà
  journalisé n'est pas repris. Expiration 3 600 s : un passage expiré est rattrapé au suivant (heure atteinte). Limite douce
  avalée par `_send_report_email` / `_rendre_*` : rapport journalisé en échec, pas renvoyé dans la journée (déjà relevé le
  15/11, « avale et fausse un résultat » ; `email_saved_reports` reste au passif de `beat_limites_allow.txt`). Cloisonnement :
  `company__in=active_companies()` + filtre société du journal. Pas de verrou de balayage : deux exécutions simultanées
  (lancement manuel de l'écran des jobs pendant un passage) pourraient doubler un envoi — préexistant, hypothétique, non retenu.

## 3. ACEL101 en détail

- **Code.** `scripts/audit_registre.py::derniere_verifie` lit `faits:\s*(\d+)` (None si absent) ; la branche « contre-visite
  des correctifs » de `cmd_du` exige `v['faits'] is None or u['faits'] > v['faits']`. Marqueur sans `faits:` : inchangé.
- **Test.** `scripts/tests/test_audit_registre.py::RegistreTests::test_du_contre_visite_attend_une_coche_nouvelle` : faits 20
  + ZZTST21 ouverte ⇒ absent ; ZZTST21 cochée ⇒ annoncé ; sans `faits:` ⇒ annoncé. Le mutant `>=` échoue au premier cas (par lecture ; le constructeur l'a exécuté, message de `365fa0d99`).
  `python -m unittest scripts.tests.test_audit_registre` : Ran 21, OK (hôte, ce jour).
- **Rejeu réel.** `cmd_du` (garde d'acceptation neutralisée) : ACEL annoncé à 74/75 contre `faits: 66` au 16/11 — c'est cette
  passe ; `audit_registre.py --check` : cohérent. Ce compte rendu porte `faits: 74`.

## 4. Garde et cohérence du planning beat

- `python scripts/check_beat_active_companies.py` : OK (rc 0) ; `python -m unittest scripts.tests.test_check_beat_active_companies` :
  Ran 44, OK.
- Relevé ast de `app.conf.beat_schedule` : 126 entrées ; tâche définie par un `@shared_task(name=…)` : 126/126 ; route
  `CELERY_TASK_ROUTES` (fnmatch) : 126/126, toutes vers `scheduled`.
- Sondes 002-004 rejouées : état du 15/11 inchangé (002 plante, 003 inconclusive, 004 périmée — VER6-603, S4 optionnel).

## 5. Écarts retenus

| C-id | Tâche d'origine | Grav. | Écart | Preuve | Tâche |
|---|---|---|---|---|---|
| C-ACEL-VER8-800 | ACEL1 / ACEL31 | S4 | textes dérivés de l'ancien passage unique : docstring de `scheduled_reports.py::_due_schedules` (« planifiée chaque jour (06:00) et le lundi (06:00) »), `help_text` de `SavedReport.heure_envoi` (« Vide = à l'heure de passage du planificateur ») et commentaire NTDATA38 de `models.py` (« borne l'envoi à cette heure-là ») ; résumé `EnvoisProgrammesPage.jsx::resume` « à 3 h » pour un rapport qui part à 6 h | lecture | optionnel |
| C-ACEL-VER8-801 | ACEL4 (jumeau) | S4 | `ventes-engagement-followup-engine` (`hour='*/3'`) et `adsengine-evaluate-guardrails` (`hour='*/6'`) passent plusieurs fois par jour sans `expires` : hors du filtre de `test_passages_frequents_expirent` (heure bornée), rafale possible au retour d'une longue panne du worker | ast du planning | optionnel |
| C-ACEL-VER8-802 | ACEL1 (preuve) | S4 | la clause « pile locale : un rapport réglé à l'heure suivante crée son `EnvoiRapport` à cette heure-là » n'est jouée que simulée (`acel3.spec.js` appelle la vraie tâche à chaque heure lue dans le planning) ; aucun vrai beat n'a déclenché l'envoi | enregistrements `62e0212df`, `cda73ef1e` | ACEL9 |

Aucune tâche nouvelle. Les S4 antérieurs (VER5-504, VER6-601, 602, 603) restent optionnels.

## 6. Couverture et sortie de cycle

- **Couvert.** ACEL1, ACEL31 : planning, fuseau, route, code, appelants, tests nommés et mutants, sonde 001, écran ; ACEL101 :
  code, test hôte, rejeu `--du` et `--check` ; garde beat et ses 44 tests ; cohérence des 126 entrées.
- **Non couvert sans pile.** Aucun test Django lancé ici (la preuve d'un vert est la CI de #1443) ; aucun vrai beat sur le
  passage horaire (VER8-802) ; preuves en direct dues d'ACEL3 (Celery en PID 1 au redéploiement) et ACEL8 (montages i18n
  dans le conteneur), puis ACEL9 (`@acceptation` du groupe).
- **Constats d'origine.** C-ACEL-001 (S2) : **fermé** (ACEL1 et ACEL31 cochées, sonde `repro: false`). C-ACEL-VER7-702 :
  **fermé**.
- **Statut.** Aucun écart S1-S2 nouveau ni d'origine ouvert : marqueur à 0. Sortie de cycle : 1 `vérifie` consécutif à zéro
  S1-S2 (14/11 : 1 ; 15/11 : 1 ×4 ; 16/11 : 1 ; 17/11 : 0) — il en faut un second. Prochaine contre-visite utile : après la
  coche d'ACEL3, ACEL8 ou ACEL9.

## 7. Coût

- H0 S0 O1 F0 · jetons sous-agents ≈ 0 M — un vérificateur (opus) seul ; aucun appel Fable, aucun sous-agent.
