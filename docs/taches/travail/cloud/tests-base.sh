#!/bin/bash
# Usage : /opt/taches-cloud/tests-base.sh <nom-de-lane> <labels de test Django…> [options de manage.py test]
# Lance des tests À BASE depuis le worktree courant, sur la base PRIVÉE de la lane.
#   MODE FIDÈLE  (quand le gabarit migré `tpl_test` existe) : clone du gabarit, réglages de la CI. Fait foi.
#   MODE RAPIDE  (tant que le gabarit se construit, ou TACHES_BASE=rapide) : tables créées d'un coup depuis les
#                modèles, SANS migrations (donc sans les lignes semées par une migration de données, ex. types de
#                notification). PRÉ-CONTRÔLE seulement : un échec qui sent « donnée de référence absente » se
#                signale, il ne se « corrige » pas ; le mode fidèle ou la CI tranchent.
set -euo pipefail
if [ $# -lt 2 ]; then echo "usage: $0 <nom-de-lane> <labels…>" >&2; exit 2; fi
LANE="$1"; shift
. /opt/taches-cloud/env.sh
ROOT=$(git rev-parse --show-toplevel)
SAFE=$(printf '%s' "$LANE" | tr -c 'a-zA-Z0-9' '_' | tr 'A-Z' 'a-z')
GABARIT="${TACHES_GABARIT:-tpl_test}"
existe() { psql -h localhost -U erp_user -d postgres -Atc "select 1 from pg_database where datname='$1'" | grep -q 1; }
MODE="${TACHES_BASE:-auto}"
if [ "$MODE" = auto ]; then if existe "$GABARIT"; then MODE=fidele; else MODE=rapide; fi; fi
cd "$ROOT/backend/django_core"
if [ "$MODE" = rapide ]; then
  export DB_NAME="erp_${SAFE}_sync" PYTHONPATH="/opt/taches-cloud${PYTHONPATH:+:$PYTHONPATH}" DJANGO_SETTINGS_MODULE=settings_sync
  echo "=== tests-base : MODE RAPIDE (sans migrations — pré-contrôle ; base test_${DB_NAME}) ===" >&2
  exec python manage.py test "$@" --keepdb --noinput
fi
export DB_NAME="erp_${SAFE}"
TESTDB="test_${DB_NAME}"
if ! existe "$TESTDB"; then
  existe "$GABARIT" || { echo "Gabarit $GABARIT absent (mode fidèle demandé)." >&2; exit 3; }
  for essai in 1 2 3 4 5 6 7 8 9 10; do
    if createdb -h localhost -U erp_user -T "$GABARIT" "$TESTDB" 2>/tmp/createdb.$$.err; then break; fi
    if [ "$essai" = 10 ]; then cat /tmp/createdb.$$.err >&2; exit 4; fi
    python -c "import time; time.sleep(3)"
  done
  rm -f /tmp/createdb.$$.err
fi
echo "=== tests-base : MODE FIDÈLE (clone du gabarit migré ; base ${TESTDB}) ===" >&2
exec python manage.py test "$@" --keepdb --noinput
