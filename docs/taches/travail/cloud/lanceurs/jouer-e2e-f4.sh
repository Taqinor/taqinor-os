#!/bin/bash
# jouer-e2e-f4.sh <fichier sortie> [specs…] — les specs e2e « chromium » de Tâches (celles du shard 2 de la CI) sur la
# pile n° 4 (Django 8003, front 4176, base erp_ve, Redis 6383) servie depuis le worktree f4, heure réelle.
W=/home/user/taqinor-os/.claude/worktrees/f4
SORTIE="$1"; shift
SPECS="${*:-e2e/taches-saisie.spec.js e2e/taches-journee.spec.js e2e/taches-projets.spec.js e2e/taches-bureau.spec.js e2e/taches-a11y.spec.js}"
set -a; . /opt/taches-cloud/secret.env; set +a
# comme le job e2e de la CI : débit par société coupé (les specs changent l'horloge du serveur, et un
# historique de débit daté du futur répond 429 pendant des jours), connexion à 1000 par minute
export TENANT_RATE_LIMIT=0 LOGIN_RATE_LIMIT=1000/minute
export TACHES_WT_VE="$W"
{
  /opt/taches-cloud/pile.sh front "$W" 4176 8003
  redis-cli -p 6383 flushall
  /opt/taches-cloud/acc-ve.sh manage migrate --run-syncdb --noinput 2>&1 | tail -1
  /opt/taches-cloud/acc-ve.sh horloge reel
} > "$SORTIE.pile" 2>&1
cd "$W/frontend"; rm -rf test-results playwright-report
export E2E_BASE_URL=http://localhost:4176 E2E_DJANGO_EXEC=/opt/taches-cloud/django-exec-ve.sh E2E_TACHES_PILE=/opt/taches-cloud/acc-ve.sh
npx playwright test --config playwright.cloud.config.mjs --project=chromium $SPECS --workers 1 --trace off --reporter=line > "$SORTIE" 2>&1
echo "exit=$?" >> "$SORTIE"
