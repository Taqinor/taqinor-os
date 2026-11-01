#!/usr/bin/env bash
# AANA64 - provisionne (idempotent) le role Postgres LECTURE SEULE `sql_agent_ro`
# de l'agent SQL apres chaque `migrate` : rejoue la section 4 de rls_roles.sql
# (une seule source des GRANT, rien recopie) puis pose le mot de passe de
# SQL_AGENT_DB_PASSWORD (lu du .env, jamais du depot ; passe a psql par variable
# d'environnement du conteneur, pas par argument). Sans la variable : saute.
# Usage (racine du depot) : [COMPOSE_CMD="docker compose -f ... -f ..."] bash backend/db/provision_sql_agent_ro.sh
set -euo pipefail
COMPOSE_CMD="${COMPOSE_CMD:-docker compose}"
SQL="$(dirname "$0")/rls_roles.sql"
lire() { grep -E "^$1=" .env 2>/dev/null | tail -n 1 | cut -d= -f2- | tr -d '\r' || true; }
ROLE="$(lire SQL_AGENT_DB_USER)"
PW="$(lire SQL_AGENT_DB_PASSWORD)"
if [ "$ROLE" != "sql_agent_ro" ] || [ -z "$PW" ]; then
  echo "provision_sql_agent_ro : SQL_AGENT_DB_USER/PASSWORD absents du .env - saute."
  exit 0
fi
{ sed -n '/^-- 4) AANA30/,$p' "$SQL"; echo "ALTER ROLE sql_agent_ro PASSWORD :'pw';"; } \
  | $COMPOSE_CMD exec -T -e PW="$PW" db sh -c \
    'psql -q -U "$POSTGRES_USER" -d "$POSTGRES_DB" -v ON_ERROR_STOP=1 -v pw="$PW"'
echo "provision_sql_agent_ro : role sql_agent_ro provisionne."
