#!/usr/bin/env bash
# ADCG9 (C-ADCG-007) — valide la configuration du proxy AVANT le merge : le
# Caddyfile (`caddy validate`, image de docker-compose.prod.yml) et nginx.conf
# (`nginx -t` dans l'image construite depuis backend/nginx). Sans elle, une
# erreur de syntaxe n'apparaissait qu'au rechargement en production.
# Code : 0 = les deux configurations valides ; 1 = l'une est refusée (le message
# nomme le fichier) ; 2 = docker absent — rien n'est validé, jamais un vert.
# VALIDER_PROXY_RACINE : racine du dépôt à valider (tests ; défaut = ce dépôt).
# Builtins seulement hors `docker` : le test tourne avec un PATH réduit au faux docker.
set -u
RACINE="${VALIDER_PROXY_RACINE:-}"
if [ -z "$RACINE" ]; then
  RACINE="$(cd "${BASH_SOURCE[0]%/*}/.." && pwd)"
fi
if ! command -v docker >/dev/null 2>&1; then
  echo "valider-proxy : docker absent — configuration du proxy NON validée" >&2
  exit 2
fi
code=0
# Hôte public factice : `{$PUBLIC_HOSTNAME}` vide laisserait une adresse vide.
if docker run --rm -e PUBLIC_HOSTNAME=validation.invalid -e RELAIS_API_SECRET= \
    -v "$RACINE/backend/caddy:/etc/caddy:ro" caddy:2 \
    caddy validate --config /etc/caddy/Caddyfile --adapter caddyfile; then
  echo "OK backend/caddy/Caddyfile"
else
  echo "ECHEC backend/caddy/Caddyfile : caddy validate refuse la configuration" >&2
  code=1
fi
# nginx.conf monté par-dessus celui de l'image (comme docker-compose.yml) ;
# --add-host : sans eux, « host not found in upstream ».
if docker build -q -t taqinor-valider-nginx "$RACINE/backend/nginx" >/dev/null \
    && docker run --rm --add-host django_core:127.0.0.1 --add-host fastapi_ia:127.0.0.1 \
      --add-host frontend:127.0.0.1 \
      -v "$RACINE/backend/nginx/nginx.conf:/etc/nginx/nginx.conf:ro" \
      taqinor-valider-nginx nginx -t; then
  echo "OK backend/nginx/nginx.conf"
else
  echo "ECHEC backend/nginx/nginx.conf : nginx -t refuse la configuration" >&2
  code=1
fi
exit "$code"
