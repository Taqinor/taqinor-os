#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# Lance EN UNE COMMANDE la pile e2e en local (la même que le job CI `e2e`), pour
# écrire des parcours Playwright avec des sélecteurs FIABLES via codegen.
#
#   bash scripts/e2e-local.sh up      # services + migrate + seed + Django + preview
#   bash scripts/e2e-local.sh stop    # arrête preview/Django + services
#
# Une fois "up", l'app tourne sur http://localhost:4173 (preview, proxy /api/django
# vers Django :8000) — base DÉMO jetable (seed_demo : demo_admin / Demo@2026!).
#   • Enregistrer un parcours :  npx playwright codegen http://localhost:4173/stock
#   • Lancer les specs        :  (cd frontend && npx playwright test)
#
# Dev only — n'est PAS appelé par la CI. Docker requis (db/redis/minio).
# ─────────────────────────────────────────────────────────────────────────────
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

ETAT="${E2E_ETAT_DIR:-/tmp}"   # surchargeable par les tests (scripts/tests/test_e2e_local.py)
DJANGO_PIDFILE="$ETAT/taqinor-e2e-django.pid"
PREVIEW_PIDFILE="$ETAT/taqinor-e2e-preview.pid"
# ADCG23 — services que `up` a lui-même démarrés : `stop` n'arrête qu'eux, jamais
# la pile partagée du poste (db/redis/minio déjà en marche avant `up`).
SERVICES_FILE="$ETAT/taqinor-e2e-services.txt"
DJANGO_LOG=/tmp/taqinor-e2e-django.log
PREVIEW_LOG=/tmp/taqinor-e2e-preview.log

stop() {
  echo "→ Arrêt preview/Django…"
  for pf in "$PREVIEW_PIDFILE" "$DJANGO_PIDFILE"; do
    if [ -f "$pf" ]; then kill "$(cat "$pf")" 2>/dev/null || true; rm -f "$pf"; fi
  done
  if [ -s "$SERVICES_FILE" ]; then
    a_arreter="$(tr '\n' ' ' < "$SERVICES_FILE")"
    echo "→ Arrêt des services démarrés par up : $a_arreter"
    # shellcheck disable=SC2086 — un nom de service par mot
    docker compose stop $a_arreter 2>/dev/null || true
  else
    echo "→ db/redis/minio : services laissés en marche (non démarrés par up)"
  fi
  rm -f "$SERVICES_FILE"
  echo "✓ Stoppé."
}

up() {
  [ -f .env ] || { echo "→ .env absent : copie depuis .env.example"; cp .env.example .env; }

  echo "→ Démarrage des services (db/redis/minio)…"
  deja="$(docker compose ps --services --status running 2>/dev/null || true)"
  : > "$SERVICES_FILE"
  for s in db redis minio; do grep -qx "$s" <<< "$deja" || echo "$s" >> "$SERVICES_FILE"; done
  docker compose up -d db redis minio

  # Crédentiels depuis .env, mais hôtes forcés en localhost (Django tourne sur
  # l'hôte, pas dans le réseau compose).
  set -a; . ./.env; set +a
  export DB_HOST=localhost DB_PORT="${DB_PORT:-5432}"
  export REDIS_HOST=localhost REDIS_PORT="${REDIS_PORT:-6379}"
  export MINIO_ENDPOINT=localhost:9000
  export DJANGO_SETTINGS_MODULE=erp_agentique.settings.dev
  export DJANGO_SECRET_KEY="${DJANGO_SECRET_KEY:-dev-only-secret}"
  export DJANGO_DEBUG=True
  # NTPLT42/PACT8 — même règle que le job `e2e` de ci.yml : ce runserver n'est
  # pas sous TESTING, donc sans ça le throttle tenant (1200/min) rend 429 sur
  # /auth/me/ pendant la fumée PACT8 → faux « page blanche ».
  export TENANT_RATE_LIMIT=0

  echo "→ Attente de Postgres…"
  for i in $(seq 1 30); do
    if python3 -c "import socket;s=socket.socket();s.settimeout(1);s.connect(('localhost',int('${DB_PORT:-5432}')))" 2>/dev/null; then
      echo "  Postgres prêt"; break
    fi
    sleep 2; [ "$i" = "30" ] && { echo "✗ Postgres indisponible (les services exposent-ils leurs ports ?)"; exit 1; }
  done

  echo "→ Backend : install + migrate + seed (idempotent)…"
  ( cd backend/django_core
    pip install -q -r requirements.txt
    python manage.py migrate --noinput
    python manage.py seed_demo
    python manage.py seed_catalogue )

  echo "→ Démarrage de Django (:8000)…"
  ( cd backend/django_core
    nohup python manage.py runserver 127.0.0.1:8000 >"$DJANGO_LOG" 2>&1 & echo $! >"$DJANGO_PIDFILE" )

  echo "→ Frontend : install + build (VITE_E2E) + preview (:4173)…"
  ( cd frontend
    npm ci
    VITE_E2E=1 npm run build
    E2E_PROXY=1 E2E_API_TARGET=http://127.0.0.1:8000 \
      nohup npm run preview -- --port 4173 --strictPort >"$PREVIEW_LOG" 2>&1 & echo $! >"$PREVIEW_PIDFILE" )

  echo "→ Attente du preview (http://localhost:4173)…"
  for i in $(seq 1 40); do
    if curl -sf http://localhost:4173/ >/dev/null 2>&1; then echo "  Preview prêt"; break; fi
    sleep 2; [ "$i" = "40" ] && { echo "✗ Preview indisponible — voir $PREVIEW_LOG"; exit 1; }
  done

  cat <<MSG

✓ Pile e2e prête.  App : http://localhost:4173   (demo_admin / Demo@2026!)
  • Enregistrer un parcours :  npx playwright codegen http://localhost:4173/stock
  • Lancer les specs        :  (cd frontend && npx playwright test)
  • Arrêter                 :  bash scripts/e2e-local.sh stop
  Logs : $DJANGO_LOG  |  $PREVIEW_LOG
MSG
}

case "${1:-up}" in
  up) up ;;
  stop) stop ;;
  *) echo "usage: bash scripts/e2e-local.sh [up|stop]"; exit 2 ;;
esac
