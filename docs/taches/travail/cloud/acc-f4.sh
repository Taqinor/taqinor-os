#!/bin/bash
# Pile n° 3 (fusion 4) : worktree f4, base erp_f4, Django :8002, front :4175, Redis :6382.
# TACHES_WT_F4 : le worktree dont la pile n° 3 exécute le backend (défaut : f4).
export TACHES_WT="${TACHES_WT_F4:-/home/user/taqinor-os/.claude/worktrees/f4}" TACHES_DB=erp_f4 TACHES_PORT=8002 TACHES_REDIS_PORT=6382
exec /opt/taches-cloud/acc.sh "$@"
