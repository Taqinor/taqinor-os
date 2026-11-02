# Vérifie ADEP — seconde contre-visite de clôture du groupe deploy (X5), 02/11/2026

Commande « vérifie ADEP » (METHODE §C.4.2, skill audit §5). Le groupe compte **55 tâches cochées sur 55** (ADEP1-46,
ADEP90-92, ADEP99, ADEP100-104). La première contre-visite de clôture (`docs/audits/2026-10-11-deploy-verifie.md`, 11/10)
était à zéro S1-S2 et ses deux écarts S3 (ADEP100, ADEP101) sont cochés. Celle-ci est la seconde : si elle est aussi à
zéro S1-S2, le groupe sort du cycle (METHODE §C.4.3). `audit_registre.py --du` ne la marque pas due (la règle ne compte
pas le second passage) ; elle est jouée à la demande de l'orchestrateur de la boucle d'audit.

Pour chaque tâche de l'échantillon, on rapproche le texte, le ou les commits, le test nommé et le code ACTUEL, avec les
7 critères de `docs/claude-memory/lecons-construction-qjr5.md`. La contre-visite n'a rien construit, n'a lancé aucun
deploy et n'a rien lu ni écrit en production.

## 0. Préconditions

- **SHA.** Échantillon tiré sur `origin/main` = `1dfa7986c` (PR #1219). Pendant le run `main` a avancé à `ce3356e48`
  (#1221 docs AFAC, #1220 vague 19 CADV : `apps/crm`, `core/numbering.py`, `core/views.py`, `authentication/permissions.py`,
  `frontend/src/api/crmApi.js`, un alias d'énumération dans `settings/base.py`). Fraîcheur (`git diff 1dfa7986c..ce3356e48`) :
  aucun fichier cité par les tâches ADEP échantillonnées n'y change de comportement (seul `settings/base.py` est touché,
  par un nommage `drf-spectacular` hors des réglages ADEP32).
- **Pile.** Conteneur `erp-agentique-django_core-1` (code du dépôt principal à `1dfa7986c`), sondes jouées par le verrou
  machine `sonde-slot.sh`, transaction annulée.
- **Inventaire (déterministe).** 55 tâches ADEP, toutes `[x]`, aucune GATED.
- **Échantillon (graine = SHA `1dfa7986c47f4a44cc20ef25c5e0f805e6c03f8e`).** Toutes les P0 / S1 (ADEP1, ADEP2, ADEP3,
  ADEP99, ADEP102), plus 25 % du reste arrondi au-dessus, tirés par `random.Random(int(sha, 16)).sample` (13 sur 50) :
  ADEP6, 8, 12, 14, 15, 18, 21, 27, 32, 34, 42, 90, 92. Total : **18 tâches**.

## 1. Vérificateurs (3 agents frais, opus, effort élevé, lecture seule, même répertoire)

| Lot | Tâches | ok | partiel |
|---|---|---|---|
| A | ADEP1, ADEP2, ADEP3, ADEP99, ADEP102, ADEP6 | 6 | — |
| B | ADEP8, ADEP12, ADEP14, ADEP15, ADEP18, ADEP21 | 5 | ADEP21 (S3) |
| C | ADEP27, ADEP32, ADEP34, ADEP42, ADEP90, ADEP92 | 4 | ADEP90, ADEP92 (S4) |
| **Total** | **18** | **15** | **3** |

Aucune tâche « non-faite », « fausse », « régression » ni « déjà-présente ».

Points saillants :

- **ADEP1 (P0/S1, client PostgreSQL dans l'image de prod).** `postgresql-client-16` (PGDG) dans `backend/django_core/Dockerfile` ;
  `check_binaires_image.py` rc 0 et son test-du-test rougit si on retire `pg_restore`. Dans le conteneur local :
  `pg_dump`/`pg_restore` 16.15 ; sonde C-ADEP-VER2-001 : BackupRun `db_dump` et `restore_drill` du jour `termine`.
- **ADEP2 / ADEP3.** Parité apt prod ↔ 3 copies CI dans les deux sens (ADEP100 inclus), 9 tests OK ; front de prod en
  `node:22.14-alpine`, `engines` du lock compatibles, nightly `mutation` vert les 30/10-01/11.
- **ADEP102 (P0/S1, IP du signataire derrière Cloudflare).** Caddy `trusted_proxies` et nginx `set_real_ip_from` / `geo`
  portent les mêmes 22 plages (comparées par script) ; `caddy validate` « Valid configuration » ; 14 tests unittest
  (asec52, asec47, adep103) OK. Côté Django, la seule lecture d'IP applicative est `core/throttling.py::ip_de_requete`,
  utilisée par les deux chemins de preuve de signature via `noyau._client_ip`. Sonde C-ADEP-VER2-002 : l'IP visiteur est
  rendue pour « V, nœud CF, V », « V, sortie Worker IPv6, nœud CF, V » et un XFF forgé en direct.
- **ADEP99 (acceptation).** `check_acceptation.py` rc 0 ; `--groupe ADEP` rc 1 parce que ce mode exige une dette vide :
  48 cochées à preuve, 46 couvertes, 2 en dette gelée (ADEP102, ADEP103 : preuve en direct = prod, D-ASAV-VER2-3).
- **ADEP34.** `is_email_configured` exige une clé ET un backend qui envoie ; sonde C-ADEP-VER2-201 : console + clé →
  non configuré, anymail + clé → configuré, sans clé → non configuré.
- **ADEP18.** Texte vieilli : le 5xx compte désormais `attempts` et l'op est marquée au 3ᵉ échec (ACHT69, puis ACHT128),
  décision postérieure, pas une régression ; `node --test src/lib/offlineOutbox.test.mjs` 21/21.
- **ADEP90 / ADEP92 (décisions).** Consignées dans `docs/audits/decisions.yml` et appliquées. Écarts documentaires S4,
  non déposés (§5).

## 2. Tests nommés et gardes rejoués (hôte, sans base de test Django)

`test_check_binaires_image`, `test_check_parite_image_ci` (9 OK), `test_ci_changes_filter` (34 OK),
`test_ci_guards` (17 OK), `test_verifier_sortie_unittest` (6 OK), `test_gardes_depot_deplace` (2 OK),
`tests.test_adep_import_strict` (FastAPI, 4 OK), `offlineOutbox.test.mjs` (21 pass), 231 tests `scripts/tests` des 11
modules d'ADEP21 (OK, 3 sautés attendus : groupe CALX drainé) ; gardes `check_binaires_image`, `check_parite_image_ci`,
`check_settings_declares`, `check_stages`, `check_ownership`, `check_acceptation` rc 0. Rejeu d'ADEP8 : un sous-processus
Django sous l'environnement de `.env.example` charge le backend console. Les tests Django des tâches (ADEP8, 32, 34) ne
sont pas rejoués localement : vert de la CI de `main`.

## 3. Sondes

| Sonde | Tâche | Verdict du lanceur | Observé |
|---|---|---|---|
| C-ADEP-VER2-001 | ADEP1 | ÉCART (repro faux = non-régression) | client 16.15 ; db_dump et restore_drill locaux `termine` ; base inchangée |
| C-ADEP-VER2-002 | ADEP102 | ÉCART (repro faux = non-régression) | IP visiteur rendue dans les 3 chaînes XFF ; base inchangée |
| C-ADEP-VER2-201 | ADEP34 | ÉCART (repro faux = non-régression) | (False, False) / (True, True) / (False, False) ; 0 mail, 0 tâche Celery |

L'écart ADEP21 est un test de garde sans état : sa reproduction est un appel Python pur (§4), pas une sonde Django.

## 4. Écarts retenus

| Tâche | Constat | Écart de | Grav. | Cause | Preuve | Fichier de plan |
|---|---|---|---|---|---|---|
| ADEP105 | C-ADEP-VER2-101 | ADEP21 | S3 | L5 test affaibli : inventaire par sous-chaîne | repro en mémoire (lot B) + grep (orchestrateur) | `PLAN_AUDIT_DEPLOY.md` |

Reproduction : GARDES privé de l'entrée `python -m unittest scripts.tests.test_check_stages -v` ⇒
`ToutEstBrancheTests.test_tout_test_et_garde_est_branche` 0 échec, car `test_check_stages` reste une sous-chaîne de
`scripts.tests.test_check_stages_litteraux` (grep dans `scripts/ci_guards.py` + workflows : 1 + 1). Cinq modules sont
aujourd'hui débranchables sans détection : `test_check_fk_scoping`, `test_check_machine_etats_statut_readonly`,
`test_check_services_appeles`, `test_check_stages`, `test_plan_lanes`. Propriétaire de `scripts/tests/test_ci_guards.py`
: deploy (`check_ownership.py --owner-of`). Aucune tâche ouverte ne le couvrait (grep `ToutEstBranche` dans les plans).

**Constats S1-S2 : 0.** Pas de seconde lentille ni de critique Fable (réservées aux S1 restants).

## 5. Optionnel (non déposé)

- **ADEP90 (S4).** D-ADEP-90 est dans `decisions.yml` et `decisions-audit-0810.md`, pas dans `deploy-decisions-fondateur.md`
  comme le demandait la tâche ; l'id « D-ADEP-1 » cité par ADEP15 n'existe nulle part.
- **ADEP92 (S4).** Le DONE LOG d'ADEP37-39 ne recopie pas « D-ADEP-3 » et le champ `taches` de D-ADEP-3 dans
  `decisions.yml` omet ADEP37-39. Sans effet sur le code.
- **ADEP102.** La parité des plages Cloudflare Caddy ↔ nginx n'est gardée que sur une plage
  (`test_plages_cloudflare_toujours_de_confiance`) ; identiques aujourd'hui.
- **ADEP14.** Plancher nightly FastAPI resté à 218 pour 262-268 tests exécutés ; la tâche dit qu'il « ne fait que monter ».
- **ADEP27.** Six gardes filtrent encore un dossier sur le chemin absolu sous une autre forme (`"tests" in chemin.parts`) :
  `check_echeances_reglementaires`, `check_query_budgets`, `check_test_tags`, `check_api_shapes`, `check_date_jour_utc`,
  `check_services_appeles`.
- **ADEP34.** `EMAIL_BACKENDS_SANS_ENVOI` (`payload_conditions.py`) est morte mais figée dans le golden
  `split_pv_conditions.json`.
- **Hors échantillon (leçon 5).** `backend/fastapi_ia/tests/test_margin_guard.py` fait `except Exception: return` dans un
  test de la garde `prix_achat` : si l'outil SQL lève, le test passe sans rien vérifier.
- **ADEP32.** `.env.example` ne documente ni `GEOIP_PATH`, ni `OPENSEARCH_URL`, ni `CF_CONNECTING_IP_TRUSTED`.

## 6. Couverture et non-couvert

- **Couvert.** 18 tâches sur 55 (toutes les P0/S1 + 25 %). Commits, tests nommés, gardes ; 3 sondes jouées.
- **Non couvert.**
  - Les 37 autres tâches cochées.
  - Preuves en direct en prod (non lues) : un `BackupRun db_dump` `termine` récent en prod (ADEP1 ; la mémoire
    `prod-sans-sauvegarde.md` porte encore l'incident « OUVERT ») ; la prochaine `DevisSignature.ip_address` hors plages
    Cloudflare (ADEP102). L'IP de preuve n'est fiable contre un Worker d'un autre compte Cloudflare qu'une fois
    `RELAIS_API_SECRET` posé côté Worker puis serveur (D-ADEP-103, choix consigné).
  - nginx realip non observé en marche : la sonde reproduit la chaîne XFF qu'il produit.
- **Statut du registre.** Deuxième contre-visite consécutive sans écart S1-S2 : le groupe ADEP **sort du cycle**
  (METHODE §C.4.3). ADEP105 (S3) reste à construire.

## 7. Coût

- 3 vérificateurs opus (effort élevé) : environ 0,53 M de jetons. Aucun appel Fable.
- Orchestrateur : échantillon, revue, reproduction ADEP21, rédaction.

<!-- verifie | groupe: ADEP | pct: 98 | ecarts_s1_s2: 0 -->
