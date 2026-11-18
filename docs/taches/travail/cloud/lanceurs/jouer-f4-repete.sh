#!/bin/bash
# jouer-f4-repete.sh <sortie> <motif> <n>  — rejoue <n> fois les étapes du motif (pile n° 3, worktree f4, base rapide)
W=/home/user/taqinor-os/.claude/worktrees/f4
set -a; . /opt/taches-cloud/secret.env; set +a
cd "$W/frontend"; rm -rf test-results playwright-report
export TACHES_WT_F4="$W" E2E_BASE_URL=http://localhost:4175 E2E_ACCEPTATION=1 \
  E2E_DJANGO_EXEC=/opt/taches-cloud/django-exec-f4.sh E2E_TACHES_PILE=/opt/taches-cloud/acc-f4.sh \
  E2E_TACHES_CAPTURES=/opt/taches-cloud/captures/f4-repete
npx playwright test --config playwright.cloud.config.mjs --project=acceptation e2e/acceptation/tch3.spec.js --workers 1 --trace off --reporter=line -g "$2" --repeat-each "$3" > "$1" 2>&1
echo "exit=$?" >> "$1"
