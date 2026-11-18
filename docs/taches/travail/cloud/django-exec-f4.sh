#!/bin/bash
export TACHES_WT="${TACHES_WT_F4:-/home/user/taqinor-os/.claude/worktrees/f4}" TACHES_DB="${TACHES_DB_F4:-erp_f4}" TACHES_REDIS_PORT=6382
exec /opt/taches-cloud/django-exec.sh "$@"
