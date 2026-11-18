#!/bin/bash
export TACHES_WT="${TACHES_WT_VE:?TACHES_WT_VE requis}" TACHES_DB=erp_ve TACHES_REDIS_PORT=6383
exec /opt/taches-cloud/django-exec.sh "$@"
