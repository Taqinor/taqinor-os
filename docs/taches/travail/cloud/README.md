# Machine cloud — remonter l'outillage du chantier « Tâches » en 15 minutes

Une session cloud démarre sur un conteneur Linux VIDE (4 cœurs, 15 Go, pas de docker qui tourne). Tout ce dossier
se recopie dans `/opt/taches-cloud/` ; rien ici n'est lu par le produit ni par la CI.

## Recette (dans l'ordre ; mesurée le 18/11/2026)

```bash
mkdir -p /opt/taches-cloud/{run,logs} && cp docs/taches/travail/cloud/* /opt/taches-cloud/ && chmod +x /opt/taches-cloud/*.sh
apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install -y postgresql-16-pgvector faketime      # 1 min
# Postgres jetable et rapide (fsync coupé), rôle de l'ERP, Redis
printf "fsync = off\nsynchronous_commit = off\nfull_page_writes = off\nmax_connections = 300\nshared_buffers = 1GB\n" > /etc/postgresql/16/main/conf.d/zz-cloud-dev.conf
pg_ctlcluster 16 main start
su postgres -c "psql -c \"CREATE ROLE erp_user LOGIN SUPERUSER PASSWORD 'erp_password'\""
PGPASSWORD=erp_password psql -h localhost -U erp_user -d template1 -c "CREATE EXTENSION IF NOT EXISTS vector; CREATE EXTENSION IF NOT EXISTS pg_trgm; CREATE EXTENSION IF NOT EXISTS unaccent; CREATE EXTENSION IF NOT EXISTS btree_gist; CREATE EXTENSION IF NOT EXISTS btree_gin;"
redis-server --daemonize yes --save '' --appendonly no
# Python 3.11 (celui de la CI et de la prod — PAS le 3.13 du conteneur : numpy 1.26.4 n'a pas de roue 3.13)
/usr/bin/python3.11 -m venv /opt/venv-erp && /opt/venv-erp/bin/pip install -r backend/django_core/requirements-dev.txt   # 3 min
(cd frontend && npm ci --no-audit --no-fund)                                                                            # 15 s
# service d'IA (fusion 3 seulement ; 6 Go avec torch) :
/usr/bin/python3.11 -m venv /opt/venv-ia && /opt/venv-ia/bin/pip install -r backend/fastapi_ia/requirements.txt pytest
# mot de passe du compte de démonstration, jamais dans le dépôt :
echo "export TACHES_DEMO_PASSWORD='<un mot de passe au hasard>'" > /opt/taches-cloud/secret.env && chmod 600 /opt/taches-cloud/secret.env
git fetch --unshallow origin    # le clone est superficiel : check_forme_code / check_test_placement l'exigent complet
```

## Les deux bases

- **Base RAPIDE (18 secondes)** : `pile.sh sync <worktree> <db>` crée les 724 tables d'un coup depuis les modèles
  (`settings_sync.py` coupe les migrations). Il y manque ce que seules les migrations posent (lignes semées par une
  migration de données, SQL à la main). Mesure du 18/11 : la suite `apps.taches` de la fusion 2 (1 407 tests) y passe
  en 71 s avec 2 écarts connus (`test_plafonds.test_aujourdhui_*_familles_erp` : 28 requêtes pour un plafond de 26,
  deux lectures `companyprofile` et `networkpolicy` en plus ici). C'est le PRÉ-CONTRÔLE des lanes et la mise au
  point des specs.
- **Base FIDÈLE (≈ 3 heures à froid)** : `manage.py migrate` rejoue les 2 399 migrations (de plus en plus lentes).
  `createdb tpl_f2 && DB_NAME=tpl_f2 python manage.py migrate` puis `ALTER DATABASE tpl_f2 RENAME TO tpl_test` : dès
  que `tpl_test` existe, `tests-base.sh` clone ce gabarit (mode fidèle) et l'enregistrement d'acceptation se joue
  dessus (`rm /opt/taches-cloud/pile.conf`, `pile.sh base erp_acc tpl_test`).

## Les commandes

| Besoin | Commande |
|---|---|
| Une commande dans l'environnement du backend | `/opt/taches-cloud/run.sh python manage.py check` (`TACHES_ENV=ia` pour le service d'IA) |
| Tests à base d'une lane, sur SA base | `/opt/taches-cloud/tests-base.sh <lane> apps.taches.tests.test_x …` (rapide ou fidèle, voir la bannière) |
| Construire le front d'un worktree | `/opt/taches-cloud/pile.sh build <worktree>` |
| Django à l'heure du scénario | `/opt/taches-cloud/acc.sh horloge "2026-11-24 08:30"` (ou `reel`) — `libfaketime`, heure du Maroc |
| Rejouer le semis | `/opt/taches-cloud/acc.sh semer --reinitialiser --jour 2026-11-24 --heure 15:00 --historique 10` puis `horloge` |
| Servir le front construit | `/opt/taches-cloud/pile.sh front <worktree> 4173 8000` |
| Jouer la spec d'acceptation | depuis `<worktree>/frontend` : `cp /opt/taches-cloud/playwright.cloud.config.mjs .` puis `. /opt/taches-cloud/secret.env && E2E_ACCEPTATION=1 E2E_BASE_URL=http://localhost:4173 E2E_DJANGO_EXEC=/opt/taches-cloud/django-exec.sh E2E_TACHES_PILE=/opt/taches-cloud/acc.sh npx playwright test --config playwright.cloud.config.mjs --project=acceptation e2e/acceptation/tch.spec.js --workers 1` |

## Pièges payés

- Le Playwright du dépôt (1.65) attend un Chromium que la machine n'a pas : `playwright.cloud.config.mjs` pointe le
  Chromium préinstallé (`/opt/pw-browsers/chromium`). Ne jamais lancer `playwright install`.
- Ce Chromium a des fuseaux PÉRIMÉS (Africa/Casablanca à +1) alors que le Maroc est à GMT depuis le 20/09/2026 :
  contextes de navigateur en `timezoneId: 'UTC'`.
- `git push` vers `refs/plan-claims/*` est refusé (403) depuis le cloud : pas de réservation de plan possible.
- Les sous-agents refusent parfois `. env.sh` : leur donner `/opt/taches-cloud/run.sh <commande>`.
- Le cache pip (3,4 Go) et les paquets `nvidia` du service d'IA (3 Go) mangent le disque (≈ 18 Go libres) :
  `rm -rf /root/.cache/pip` après les installations.
