#!/usr/bin/env bash
# TEMPORAIRE (zz-scratch-acceptation-taches-f4) — commande de pile des acceptations « Tâches » sur un runner GitHub,
# l'équivalent de /opt/taches-cloud/acc-f3.sh de la session cloud (variable E2E_TACHES_PILE de tch2.spec.js) :
#   zz-taches-pile.sh semer <options de seed_taches_demo…>   arrête Django et le service d'IA, vide Redis, rejoue le semis
#   zz-taches-pile.sh horloge "AAAA-MM-JJ HH:MM" | reel       (re)lance gunicorn ET uvicorn sous la MÊME horloge figée
#                                                              (libfaketime : LD_PRELOAD + FAKETIME, heure du Maroc)
#   zz-taches-pile.sh manage <commande manage.py…>
# Lit son environnement (celui du pas du job : base, Redis, clés d'IA — JAMAIS affichées ; aucun `set -x` ici) :
#   ZZ_RACINE (défaut $GITHUB_WORKSPACE), ZZ_VENV_IA (défaut /tmp/venv-ia), ZZ_DJANGO_PORT (8000), ZZ_IA_PORT (8100),
#   ZZ_JOURNAUX (défaut /tmp), REDIS_HOST / REDIS_PORT, TACHES_DEMO_PASSWORD (tiré au sort par le job).
# Le service d'IA part de l'heure ACTUELLE de Django + 5 s : un jeton de session émis par Django (`iat`) n'est jamais « dans le
# futur » pour lui (PyJWT refuse un `iat` futur — constaté sur la pile cloud le 18/11/2026).
set -euo pipefail
RACINE="${ZZ_RACINE:-${GITHUB_WORKSPACE:?ZZ_RACINE ou GITHUB_WORKSPACE requis}}"
VENV_IA="${ZZ_VENV_IA:-/tmp/venv-ia}"
PORT_DJANGO="${ZZ_DJANGO_PORT:-8000}"
PORT_IA="${ZZ_IA_PORT:-8100}"
JOURNAUX="${ZZ_JOURNAUX:-/tmp}"
PIDS="$JOURNAUX/zz-taches-pids"
mkdir -p "$PIDS"

libfaketime() {
  local lib
  for lib in /usr/lib/x86_64-linux-gnu/faketime/libfaketime.so.1 /usr/lib/aarch64-linux-gnu/faketime/libfaketime.so.1 \
             /usr/lib/faketime/libfaketime.so.1 /usr/local/lib/faketime/libfaketime.so.1; do
    [ -f "$lib" ] && { echo "$lib"; return 0; }
  done
  echo "libfaketime introuvable (apt-get install -y libfaketime)" >&2; return 1
}

arreter() {  # arreter <nom>
  local f="$PIDS/$1.pid" pid
  [ -f "$f" ] || return 0
  pid=$(cat "$f")
  kill -TERM -- "-$pid" 2>/dev/null || kill -TERM "$pid" 2>/dev/null || true
  for _ in $(seq 1 30); do kill -0 "$pid" 2>/dev/null || break; sleep 0.2; done
  kill -KILL -- "-$pid" 2>/dev/null || kill -KILL "$pid" 2>/dev/null || true
  rm -f "$f"
}

attendre() {  # attendre <url> <secondes>
  local url="$1" limite="$2" code
  for _ in $(seq 1 $((limite * 2))); do
    code=$(curl -s -o /dev/null -w "%{http_code}" "$url" || true)
    if [ -n "$code" ] && [ "$code" != "000" ]; then return 0; fi
    sleep 0.5
  done
  echo "pas de réponse de $url en ${limite} s" >&2; return 1
}

utc_de() {  # utc_de "AAAA-MM-JJ HH:MM" <secondes d'avance> → « AAAA-MM-JJ HH:MM:SS » UTC (heure du Maroc en entrée)
  python - "$1" "$2" <<'PY'
import sys, datetime, zoneinfo
t = sys.argv[1].strip(); fmt = '%Y-%m-%d %H:%M:%S' if t.count(':') == 2 else '%Y-%m-%d %H:%M'
d = datetime.datetime.strptime(t, fmt).replace(tzinfo=zoneinfo.ZoneInfo('Africa/Casablanca'))
d += datetime.timedelta(seconds=int(sys.argv[2]))
print(d.astimezone(datetime.timezone.utc).strftime('%Y-%m-%d %H:%M:%S'))
PY
}

lancer() {  # lancer <nom> <horloge|reel> <avance s> <dossier> <journal> <commande…>
  # Le pid noté est celui du serveur lui-même (setsid → nohup → exec) : son groupe est arrêté par `arreter`, et
  # aucun de ses descripteurs ne garde ouverte la sortie de ce script. Horloge figée : pas de DONT_FAKE_MONOTONIC
  # (avec lui, `time.sleep` de Python 3.11 lève EINVAL sous libfaketime — gunicorn en meurt, constaté le 18/11).
  local nom="$1" quand="$2" avance="$3" dossier="$4" journal="$5"; shift 5
  local lib="" utc=""
  if [ "$quand" != reel ]; then lib=$(libfaketime); utc=$(utc_de "$quand" "$avance"); fi
  (
    cd "$dossier" || exit 1
    if [ -z "$lib" ]; then
      setsid nohup "$@" > "$journal" 2>&1 < /dev/null &
    else
      TZ=UTC LD_PRELOAD="$lib" FAKETIME="@$utc" FAKETIME_DONT_RESET=1 setsid nohup "$@" > "$journal" 2>&1 < /dev/null &
    fi
    echo $! > "$PIDS/$nom.pid"
  )
}

cmd="${1:-}"; shift || true
case "$cmd" in
  semer)
    arreter django; arreter ia
    python - <<'PY'
import os, redis
redis.Redis(host=os.environ.get('REDIS_HOST', 'localhost'), port=int(os.environ.get('REDIS_PORT', '6379'))).flushall()
PY
    cd "$RACINE/backend/django_core" && python manage.py seed_taches_demo "$@" ;;
  horloge)
    quand="${1:-reel}"
    arreter django; arreter ia
    lancer django "$quand" 0 "$RACINE/backend/django_core" "$JOURNAUX/gunicorn-error.log" \
      gunicorn erp_agentique.wsgi:application --bind "127.0.0.1:$PORT_DJANGO" --workers 3 --timeout 300 \
      --worker-class sync --access-logfile "$JOURNAUX/gunicorn-access.log" --capture-output
    attendre "http://127.0.0.1:$PORT_DJANGO/api/django/health/" 90
    if [ -x "$VENV_IA/bin/uvicorn" ]; then
      # L'horloge de Django a démarré à l'écriture de son pid et avance depuis : le service d'IA part de l'heure
      # ACTUELLE de Django + 5 s (un jeton de Django n'a jamais un `iat` futur pour lui).
      avance=$(( $(date +%s) - $(stat -c %Y "$PIDS/django.pid") + 5 ))
      lancer ia "$quand" "$avance" "$RACINE/backend/fastapi_ia" "$JOURNAUX/uvicorn.log" \
        "$VENV_IA/bin/uvicorn" app.main:app --host 127.0.0.1 --port "$PORT_IA" --workers 1
      attendre "http://127.0.0.1:$PORT_IA/health" 180
    fi
    echo "pile prête (horloge $quand)" ;;
  manage)
    cd "$RACINE/backend/django_core" && python manage.py "$@" ;;
  *) echo "commande inconnue : ${cmd:-<vide>} (semer | horloge | manage)" >&2; exit 2 ;;
esac
