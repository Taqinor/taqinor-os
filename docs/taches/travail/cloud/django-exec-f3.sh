#!/bin/bash
export TACHES_WT="${TACHES_WT_F3:-/home/user/taqinor-os/.claude/worktrees/f3}" TACHES_DB=erp_f3 TACHES_REDIS_PORT=6380
exec /opt/taches-cloud/django-exec.sh "$@"
