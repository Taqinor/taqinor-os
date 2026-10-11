# Vérifie ADEP — contre-visite de clôture du groupe deploy (X5), 11/10/2026

Commande « vérifie ADEP » (METHODE §C.4.2, skill audit §7). Le groupe compte **50 tâches cochées sur 50** constructibles
(100 %) : la contre-visite de **clôture** (≥ 95 %) est due. C'est la première contre-visite du groupe.

Pour chaque tâche de l'échantillon, on rapproche le texte de la tâche, le ou les commits et le test rouge nommé, avec les
7 critères de `docs/claude-memory/lecons-construction-qjr5.md`. Les écarts confirmés sont déposés en tâches v3 dans le plan
du propriétaire des fichiers (`scripts/**` → `PLAN_AUDIT_DEPLOY.md`).

La contre-visite n'a rien construit, n'a lancé aucun deploy (`deploy-prod.ps1` jamais lancé) et n'a rien écrit en
production. Les seules actions sur le serveur sont des lectures (ssh, `docker exec … manage.py shell` en lecture, `grep`
masqué du `.env`), faites par l'orchestrateur et annoncées dans le chat.

## 0. Préconditions

- **SHA.** `origin/main` = `6f3191ad7` (PR #948). Branche de claim : `verifie-adep` (commit vide `44fdc77af`, poussé).
  CI « CI » de `6f3191ad7` en `push` : verte (run 38059434594, 10 shards backend-tests en succès).
- **Prod.** `/opt/taqinor-os` est à `6f3191ad7` ; 12 conteneurs « Up ».
- **Registre.** X5 `deploy`, groupe ADEP, dossier `docs/audits/2026-10-08-deploy.md` (PR #873). 10 plans alimentés.
- **Inventaire (déterministe).** 50 tâches ADEP (ADEP1-46, ADEP90-92, ADEP99), toutes `[x]`, aucune GATED.
- **Échantillon (graine = SHA `6f3191ad7f9437e786a6144a7d7ebc47408da545`).** Toutes les P0 et S1 (ADEP1, ADEP2, ADEP3,
  ADEP99), plus 25 % du reste tirées par `random.Random(int(sha, 16)).sample` (12 sur 46). Total : **16 tâches**.
  Par fichier : DEPLOY 9, SECURITE 3, PARAMETRES 1, DOCUMENTS 1, FACTURATION 1, ANALYSE 1.

## 1. Vérificateurs (3 agents frais, opus, effort élevé, lecture seule, même répertoire)

| Lot | Tâches | ok | partiel |
|---|---|---|---|
| 1 | ADEP1, ADEP2, ADEP3, ADEP7, ADEP99 | 4 | ADEP2 |
| 2 | ADEP8, ADEP11, ADEP13, ADEP14, ADEP16 | 4 | ADEP13 |
| 3 | ADEP25, ADEP32, ADEP36, ADEP37, ADEP39, ADEP41 | 6 | — |
| **Total** | **16** | **14** | **2** |

Aucune tâche « non-faite », « fausse », « régression » ni « déjà-présente ». ADEP36 : texte vieilli (le test vit à
`apps/notifications/tests_adep36_whatsapp_reglages.py`, un paquet `tests/` aurait masqué `tests.py`) ; code juste.

Points saillants des tâches jugées ok :

- **ADEP1 (P0, S1 — pas de `pg_dump` dans l'image de prod).** Corrigé et vrai en prod : `pg_dump`, `pg_restore`, `psql`
  16.15 dans `erp-agentique-django_core-1` ; BackupRun `db_dump` **terminés** les 09/10 (21,7 Mo) et 10/10 (21,8 Mo) à
  03:00, après 105 échecs « No such file or directory: 'pg_dump' » jusqu'au 08/10. La garde
  `check_binaires_image.py` rougit sur le Dockerfile d'avant ADEP1 (rejoué par le lot 1).
- **ADEP99 (acceptation).** `docs/audits/acceptation/ADEP/2026-10-10-88603ba7a.md` PASS ; `check_acceptation.py --groupe ADEP`
  : 46 cochées à preuve, 46 couvertes, dette 0.
- **ADEP7 (rôle BDD par process).** Sonde de chargement des réglages sans base : celery, beat et commandes owner restent
  propriétaires, gunicorn/runserver passent `app_rls` sous drapeau ; drapeau OFF en prod ⇒ owner partout.
- **ADEP32/36/37/39 (clés inertes, D-ADEP-3).** Prod lue : 0 des clés ciblées dans `.env` ; les réglages chargés valent
  tous `False`/vides. Rien ne s'est allumé.
- **ADEP41 (`.dockerignore` FastAPI).** Code juste sur main (motifs `**/`). Observé en prod : l'image `fastapi_ia` en
  service date du 09/10 03:45 UTC, AVANT le correctif (841b4aa48, 04:01) ; elle contient encore 23 `.pyc`. Sans effet
  (le code est monté par-dessus `/app`) ; l'image se nettoiera au prochain rebuild. Pas de tâche.

## 2. Tests nommés

- **Exécutés (Python pur, sans base).** `test_check_binaires_image` (4 OK), `test_check_parite_image_ci` (7 OK),
  `test_ci_changes_filter` (29 passed), `test_check_filtre_chemins_ci`, `test_verifier_sortie_unittest`,
  `offlineOutbox.test.mjs` (21 pass), gardes `check_naive_datetime`, `check_money_fields`, `check_test_determinism`,
  `check_dockerignore`, `check_settings_declares` (rc 0) et leurs tests (27 OK).
- **Raisonnés, non rejoués localement.** Les tests Django (ADEP7, 8, 32, 36, 37, 39) : vert de la CI de `6f3191ad7` ;
  aucune base de test locale construite.
- Les deux écarts ne viennent pas de tests rouges : les gardes sont vertes, elles ne couvrent pas toute leur classe.

## 3. Sondes

Aucune sonde Django : les deux écarts portent sur des gardes CI, sans argent, chiffre client, persistance ni
multi-société. Les reproductions sont des appels Python purs, rejoués par l'orchestrateur :

| Constat | Écart de | Reproduction | Sortie |
|---|---|---|---|
| C-ADEP-VER-001 | ADEP2 | arbre copié, `fonts-noto-core` retiré du seul `backend/django_core/Dockerfile`, `verifier_apt` | `[]` (rc 0), paquet toujours dans l'image CI |
| C-ADEP-VER-002 | ADEP13 | `candidats(frontend/src/features/ventes/solar.corpus.test.jsx)` puis `_resolve` du fixture | `set()` ; `frontend: False` |

## 4. Écarts retenus

| Tâche | Constat | Écart de | Grav. | Cause | Preuve | Fichier de plan |
|---|---|---|---|---|---|---|
| ADEP100 | C-ADEP-VER-001 | ADEP2 | S3 | clause-manquante : la parité ne se vérifie que prod → CI | repro §3 | `PLAN_AUDIT_DEPLOY.md` |
| ADEP101 | C-ADEP-VER-002 | ADEP13 | S3 | clause-manquante : `join` composé et `frontend/scripts/` non relevés ; gardes de `backend-openapi`/`frontend-static` non rejouées | repro §3 | `PLAN_AUDIT_DEPLOY.md` |

**Constats S1-S2 : 0.** Pas de critique Fable (réservée aux S1 restants).

## 5. Optionnel (non déposé)

- ADEP3 : `release-verify.yml` (Node '22') et `.github/ci-image/Dockerfile.e2e` (`node:22-bookworm-slim`, tag flottant) hors
  de la garde Node ; cohérents aujourd'hui.
- ADEP1 : la garde compare aussi `backend/fastapi_ia` au Dockerfile Django (aucun binaire appelé côté IA).
- ADEP13 : docstring de `check_filtre_chemins_ci.py` qui annonce `--profond` et une fonction absente ; alias `@rooflib`
  non suivis (couverts par ADEP11).
- ADEP14 : échantillons écrits à la main au lieu de sorties capturées (comportement confirmé sur le nightly du 10/10).
- ADEP16 : clause « recharger la file » tenue par construction, non testée explicitement.
- ADEP39 : test au niveau du réglage, pas de la vue ; si `PAYMENT_PROVIDER` est un jour posé, `/pay-card/` n'existe pas
  (déjà tracé ADEV53, ouvert : à faire avant d'ajouter la clé).
- DONE LOG d'ADEP37 et ADEP39 sans la mention « D-ADEP-3 : aucune clé présente ».

## 6. Couverture et non-couvert

- **Couvert.** 16 tâches sur 50 (toutes les P0/S1 + 25 %). Commits, tests et gardes ; lectures prod ciblées.
- **Non couvert.**
  - Les 34 autres tâches cochées.
  - Le `restore_drill` hebdomadaire (lundi 04:00) n'a pas encore tourné depuis ADEP1 (dernier : 05/10, échec faute de
    dump). À relire après le 12/10 04:00 UTC.
  - Copie hors site des sauvegardes : `offsite: off` (non requis par les tâches échantillonnées).
  - Preuves en direct d'origine (`x5/…`) : scripts restés dans le scratchpad de l'audit, remplacés par des équivalents.
- **Statut du registre.** Après ce dépôt : 50/52 cochées (96 %), dernière contre-visite sans écart S1-S2 ⇒ calculé
  `vérifié`. Sortie du cycle (METHODE §C.4.3) au second passage à zéro S1-S2, en contre-visite par différence.

## 7. Coût

- 3 vérificateurs opus (effort élevé) : environ 0,56 M de jetons. Aucun appel Fable.
- Orchestrateur : échantillon, lectures prod, reproductions, rédaction.

<!-- verifie | groupe: ADEP | pct: 100 | ecarts_s1_s2: 0 -->
