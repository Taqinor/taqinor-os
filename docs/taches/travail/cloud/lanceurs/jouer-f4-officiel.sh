#!/bin/bash
# jouer-f4-officiel.sh <fichier sortie> [motif -g] — REJEU OFFICIEL sur la fusion 4 : tch.spec.js (fusion 2) et
# tch3.spec.js (fusion 4) en UNE invocation (un seul enregistrement par sha), pile n° 3 depuis le worktree f4,
# base MIGRÉE erp_f4_fidele (clone de tpl_test + migrations + seed_demo + seed_catalogue + init_roles), réglages de la CI.
W=/home/user/taqinor-os/.claude/worktrees/f4
set -a; . /opt/taches-cloud/secret.env; set +a
# comme le job e2e de la CI : débit par société coupé (les specs changent l'horloge du serveur, et un
# historique de débit daté du futur répond 429 pendant des jours), connexion à 1000 par minute
export TENANT_RATE_LIMIT=0 LOGIN_RATE_LIMIT=1000/minute
cd "$W/frontend"; rm -rf test-results playwright-report
export TACHES_WT_F4="$W" TACHES_DB_F4=erp_f4_fidele TACHES_FIDELE=1 E2E_BASE_URL=http://localhost:4175 E2E_ACCEPTATION=1 \
  E2E_DJANGO_EXEC=/opt/taches-cloud/django-exec-f4.sh E2E_TACHES_PILE=/opt/taches-cloud/acc-f4.sh \
  E2E_TACHES_CAPTURES=${CAPTURES:-/opt/taches-cloud/captures/f4-officiel}
# front de la fusion 4 rebâti et servi, cache de la pile vidé, Django relancé sur la base migrée AVANT le login du projet « setup »
{ /opt/taches-cloud/pile.sh build "$W" && /opt/taches-cloud/pile.sh front "$W" 4175 8002
  redis-cli -p 6382 flushall
  /opt/taches-cloud/acc-f4.sh horloge reel; } > "$1.pile" 2>&1
cd "$W/frontend"; rm -rf test-results playwright-report
if [ -n "${2:-}" ]; then
  npx playwright test --config playwright.cloud.config.mjs --project=acceptation e2e/acceptation/tch.spec.js e2e/acceptation/tch3.spec.js --workers 1 --trace off --reporter=line -g "$2" > "$1" 2>&1
else
  npx playwright test --config playwright.cloud.config.mjs --project=acceptation e2e/acceptation/tch.spec.js e2e/acceptation/tch3.spec.js --workers 1 --trace off --reporter=line > "$1" 2>&1
fi
echo "exit=$?" >> "$1"
