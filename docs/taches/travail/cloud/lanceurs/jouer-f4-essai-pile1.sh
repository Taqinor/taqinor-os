#!/bin/bash
# jouer-f4-essai-pile1.sh <fichier sortie> [motif -g] — ESSAI (pas l'officiel) : tch.spec.js + tch3.spec.js en une invocation
# sur la pile n° 1 (Django 8000, front 4173, Redis 6379) servie depuis le worktree f4, base MIGRÉE erp_f4_fidele.
W=/home/user/taqinor-os/.claude/worktrees/f4
set -a; . /opt/taches-cloud/secret.env; set +a
export TENANT_RATE_LIMIT=0 LOGIN_RATE_LIMIT=1000/minute
export TACHES_WT="$W" TACHES_DB=erp_f4_fidele TACHES_FIDELE=1 TACHES_PORT=8000 TACHES_REDIS_PORT=6379
{ /opt/taches-cloud/pile.sh build "$W" && /opt/taches-cloud/pile.sh front "$W" 4173 8000
  redis-cli -p 6379 flushall
  # le projet « setup » se connecte AVANT que la spec ne relance Django : le serveur doit déjà être le bon
  /opt/taches-cloud/acc.sh horloge reel; } > "$1.pile" 2>&1
cd "$W/frontend"; rm -rf test-results playwright-report
export E2E_BASE_URL=http://localhost:4173 E2E_ACCEPTATION=1 E2E_DJANGO_EXEC=/opt/taches-cloud/django-exec.sh E2E_TACHES_PILE=/opt/taches-cloud/acc.sh \
  E2E_TACHES_CAPTURES=/opt/taches-cloud/captures/f4-essai
if [ -n "${2:-}" ]; then
  npx playwright test --config playwright.cloud.config.mjs --project=acceptation e2e/acceptation/tch.spec.js e2e/acceptation/tch3.spec.js --workers 1 --trace off --reporter=line -g "$2" > "$1" 2>&1
else
  npx playwright test --config playwright.cloud.config.mjs --project=acceptation e2e/acceptation/tch.spec.js e2e/acceptation/tch3.spec.js --workers 1 --trace off --reporter=line > "$1" 2>&1
fi
echo "exit=$?" >> "$1"
