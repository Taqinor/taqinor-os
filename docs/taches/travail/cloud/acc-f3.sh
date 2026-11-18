#!/bin/bash
# Pile n° 2 (fusion 3) : worktree f3, base erp_f3, Django :8001, front :4174, Redis :6380.
# TACHES_WT_F3 : le worktree dont la pile n° 2 exécute le backend (défaut : f3).
export TACHES_WT="${TACHES_WT_F3:-/home/user/taqinor-os/.claude/worktrees/f3}" TACHES_DB=erp_f3 TACHES_PORT=8001 TACHES_REDIS_PORT=6380
exec /opt/taches-cloud/acc.sh "$@"
