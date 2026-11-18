#!/bin/bash
# Pile n° 3 (fusion 4) : worktree f4, base erp_f4, Django :8002, front :4175, Redis :6382.
# TACHES_WT_F4 : le worktree dont la pile n° 3 exécute le backend (défaut : f4).
# TACHES_DB_F4 : la base de la pile n° 3 (défaut : erp_f4 ; rejeu officiel : erp_f4_fidele avec TACHES_FIDELE=1).
export TACHES_WT="${TACHES_WT_F4:-/home/user/taqinor-os/.claude/worktrees/f4}" TACHES_DB="${TACHES_DB_F4:-erp_f4}" TACHES_PORT=8002 TACHES_REDIS_PORT=6382
exec /opt/taches-cloud/acc.sh "$@"
