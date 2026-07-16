#!/bin/sh
# VX200 — CSP par environnement : rend security-headers.conf.template (envsubst)
# vers /etc/nginx/generated/, hors de tout bind mount (docker-compose.yml monte
# UNIQUEMENT nginx.conf en lecture seule ; ce chemin reste donc toujours
# inscriptible, en dev comme en prod). nginx.conf inclut ce fichier genere.
set -e

: "${MINIO_PUBLIC_ORIGIN:=http://localhost:9000}"
export MINIO_PUBLIC_ORIGIN

mkdir -p /etc/nginx/generated
envsubst '${MINIO_PUBLIC_ORIGIN}' \
  < /etc/nginx/templates/security-headers.conf.template \
  > /etc/nginx/generated/security-headers.conf

exec "$@"
