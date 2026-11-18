#!/bin/bash
# Pile n° 4 (lane V-E) : worktree TACHES_WT_VE (obligatoire), base erp_ve, Django :8003, front :4176, Redis :6383.
export TACHES_WT="${TACHES_WT_VE:?TACHES_WT_VE requis}" TACHES_DB=erp_ve TACHES_PORT=8003 TACHES_REDIS_PORT=6383
exec /opt/taches-cloud/acc.sh "$@"
