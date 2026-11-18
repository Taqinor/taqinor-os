#!/bin/bash
# Reproduction locale du serveur de production (mêmes réglages, même commande gunicorn).
# usage : prod-local.sh <worktree> <port> [variables supplémentaires...]
set -euo pipefail
WT="$1"; PORT="$2"; shift 2
. /opt/taches-cloud/env.sh
export DJANGO_SETTINGS_MODULE=erp_agentique.settings.prod
unset DJANGO_DEBUG
export DJANGO_SECRET_KEY=reproduction-locale-sans-valeur-0123456789abcdefghijklmnopqrstuvwxyz
export DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1
export DB_NAME=erp_f3 REDIS_PORT=6390
for v in "$@"; do export "$v"; done
cd "$WT/backend/django_core"
exec gunicorn erp_agentique.wsgi:application --bind 127.0.0.1:$PORT --workers 3 --threads 4 --preload --timeout 120 --max-requests 0 --max-requests-jitter 0
