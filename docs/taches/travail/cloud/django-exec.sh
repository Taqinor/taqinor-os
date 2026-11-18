#!/bin/bash
# E2E_DJANGO_EXEC des specs d'acceptation sur cette machine : exécute "$@" dans le backend de la pile
# (worktree TACHES_WT, base TACHES_DB), SOUS L'HORLOGE RÉELLE (les specs figent l'heure elles-mêmes).
set -euo pipefail
. /opt/taches-cloud/env.sh
[ -f /opt/taches-cloud/pile.conf ] && . /opt/taches-cloud/pile.conf
export DJANGO_SETTINGS_MODULE="${TACHES_REGLAGES:-erp_agentique.settings.dev}" PYTHONPATH="/opt/taches-cloud${PYTHONPATH:+:$PYTHONPATH}"; . /opt/taches-cloud/secret.env
export DB_NAME="${TACHES_DB:-erp_acc}"
cd "${TACHES_WT:-/home/user/taqinor-os/.claude/worktrees/f2}/backend/django_core"
exec "$@"
