#!/usr/bin/env bash
# La SEULE façon canonique de lancer les tests Django backend en local contre
# la pile docker (jumeau POSIX de scripts/test-backend.ps1 — même commande,
# même garde single-writer). Voir test-backend.ps1 pour les commentaires
# détaillés / rationale complet.
#
# The ONE canonical way to run backend Django tests locally against the docker
# stack (POSIX twin of scripts/test-backend.ps1 — same command, same
# single-writer guard). See test-backend.ps1 for the full detailed rationale.
#
# Usage:
#   bash scripts/test-backend.sh
#   MODULES="apps.crm apps.ventes" PARALLEL=8 bash scripts/test-backend.sh
#   REBUILD_DB=1 bash scripts/test-backend.sh   # see WARNING below
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

MODULES="${MODULES:-apps authentication core}"
PARALLEL="${PARALLEL:-4}"
REBUILD_DB="${REBUILD_DB:-0}"

COMPOSE_PROJECT="erp-agentique"
DB_CONTAINER="erp-agentique-db-1"
DB_USER="erp_user"
ADMIN_DB="erp_db"
TEST_DB="test_erp_db"
RUN_NAME_PATTERN="erp-agentique-django_core-run"

# ── GARDE SINGLE-WRITER / SINGLE-WRITER GUARD ──────────────────────────────
# test_erp_db est une base unique partagée — pas de writer concurrent. Deux
# runs simultanés l'ont déjà corrompue par le passé. Refuse de démarrer si un
# run backend-tests est déjà actif.
#
# test_erp_db is a single shared database — no concurrent writer. Two
# simultaneous runs have already corrupted it. Refuse to start if a
# backend-tests run container is already active.
echo "→ Vérification qu'aucun autre run de tests backend n'est actif…"
existing="$(docker ps --filter "name=${RUN_NAME_PATTERN}" --format '{{.Names}}')"
if [ -n "$existing" ]; then
  echo ""
  echo "REFUS DE DEMARRER : un run de tests backend est deja actif :"
  echo "  $existing"
  echo ""
  echo "test_erp_db est single-writer -- deux runs simultanes l'ont deja"
  echo "corrompue par le passe. Attendez la fin de l'autre run, ou tuez-le :"
  echo "  docker rm -f $existing"
  echo ""
  exit 1
fi
echo "  OK — aucun run concurrent détecté."

# ── REBUILD_DB=1 : DROP + AVERTISSEMENT / DROP + WARNING ───────────────────
if [ "$REBUILD_DB" = "1" ]; then
  echo ""
  echo "=============================================================="
  echo " AVERTISSEMENT -- REBUILD COMPLET DE test_erp_db"
  echo " Un rebuild complet peut prendre PLUSIEURS HEURES sur ce PC."
  echo " Ne lancez ceci QUE seul, de nuit, sans autre run en parallele."
  echo ""
  echo " WARNING -- FULL REBUILD OF test_erp_db"
  echo " A full rebuild can take HOURS on this box. Run this ALONE,"
  echo " overnight, with no other run in parallel."
  echo "=============================================================="
  echo ""

  echo "→ DROP DATABASE test_erp_db (avec terminaison des connexions actives)…"
  docker exec "$DB_CONTAINER" psql -U "$DB_USER" -d "$ADMIN_DB" -c \
    "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = '${TEST_DB}' AND pid <> pg_backend_pid(); DROP DATABASE IF EXISTS ${TEST_DB};"
  echo "  test_erp_db supprimee -- sera recreee a froid par ce run."
  KEEPDB_FLAG=()
else
  KEEPDB_FLAG=(--keepdb)
fi

# ── Commande de test / test command ─────────────────────────────────────────
# shellcheck disable=SC2206
MODULES_LIST=($MODULES)

echo ""
echo "→ docker compose -p ${COMPOSE_PROJECT} run --rm --no-deps -e DJANGO_SETTINGS_MODULE=erp_agentique.settings.dev django_core python manage.py test ${MODULES} ${KEEPDB_FLAG[*]} --parallel ${PARALLEL} -v1"
echo ""

set +e
docker compose -p "$COMPOSE_PROJECT" run --rm --no-deps \
  -e DJANGO_SETTINGS_MODULE=erp_agentique.settings.dev \
  django_core \
  python manage.py test "${MODULES_LIST[@]}" "${KEEPDB_FLAG[@]}" --parallel "$PARALLEL" -v1
test_exit_code=$?
set -e

echo ""
if [ "$test_exit_code" -eq 0 ]; then
  echo "✓ Tests backend : SUCCES (modules: $MODULES)"
else
  echo "✗ Tests backend : ECHEC (code $test_exit_code, modules: $MODULES)"
fi

exit "$test_exit_code"
