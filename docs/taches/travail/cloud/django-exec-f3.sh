#!/bin/bash
export TACHES_WT=/home/user/taqinor-os/.claude/worktrees/f3 TACHES_DB=erp_f3 TACHES_REDIS_PORT=6380
exec /opt/taches-cloud/django-exec.sh "$@"
