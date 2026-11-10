#!/bin/sh
# VX200 — CSP par environnement : rend security-headers.conf.template (envsubst)
# vers /etc/nginx/generated/, hors de tout bind mount (docker-compose.yml monte
# UNIQUEMENT nginx.conf en lecture seule ; ce chemin reste donc toujours
# inscriptible, en dev comme en prod). nginx.conf inclut ce fichier genere.
set -e

: "${MINIO_PUBLIC_ORIGIN:=http://localhost:9000}"
export MINIO_PUBLIC_ORIGIN
# ADCG53 — hote d'ingestion Sentry (connect-src) derive du DSN du front quand il
# est arme : https://cle@o1.ingest.de.sentry.io/2 -> https://o1.ingest.de.sentry.io.
SENTRY_CONNECT_ORIGIN=""
if [ -n "${VITE_SENTRY_DSN:-}" ]; then
  reste=${VITE_SENTRY_DSN#*://}
  hote=${reste#*@}
  SENTRY_CONNECT_ORIGIN="${VITE_SENTRY_DSN%%://*}://${hote%%/*}"
fi
export SENTRY_CONNECT_ORIGIN

mkdir -p /etc/nginx/generated
envsubst '${MINIO_PUBLIC_ORIGIN} ${SENTRY_CONNECT_ORIGIN}' \
  < /etc/nginx/templates/security-headers.conf.template \
  > /etc/nginx/generated/security-headers.conf

exec "$@"
