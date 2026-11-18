#!/bin/bash
# jouer-f4.sh <fichier sortie> <fichier json> [motif -g]   — spec tch3 sur la pile n° 3, worktree f4
W=${TACHES_WT_F4:-/home/user/taqinor-os/.claude/worktrees/f4}
set -a; . /opt/taches-cloud/secret.env; set +a
# comme le job e2e de la CI : débit par société coupé (les specs changent l'horloge du serveur, et un
# historique de débit daté du futur répond 429 pendant des jours), connexion à 1000 par minute
export TENANT_RATE_LIMIT=0 LOGIN_RATE_LIMIT=1000/minute
cd "$W/frontend"
rm -rf test-results playwright-report
export TACHES_WT_F4="$W" E2E_BASE_URL=http://localhost:4175 E2E_ACCEPTATION=1 \
  E2E_DJANGO_EXEC=/opt/taches-cloud/django-exec-f4.sh E2E_TACHES_PILE=/opt/taches-cloud/acc-f4.sh \
  E2E_TACHES_CAPTURES=${E2E_TACHES_CAPTURES:-/opt/taches-cloud/captures/f4} PLAYWRIGHT_JSON_OUTPUT_NAME="$2"
if [ -n "${3:-}" ]; then
  npx playwright test --config playwright.cloud.config.mjs --project=acceptation e2e/acceptation/tch3.spec.js --workers 1 --trace off --reporter=line,json -g "$3" > "$1" 2>&1
else
  npx playwright test --config playwright.cloud.config.mjs --project=acceptation e2e/acceptation/tch3.spec.js --workers 1 --trace off --reporter=line,json > "$1" 2>&1
fi
echo "exit=$?" >> "$1"
