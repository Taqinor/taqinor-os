#!/bin/bash
# Pile locale SANS docker de la session cloud : Postgres + Redis natifs (déjà lancés), Django `runserver`
# (au besoin sous horloge figée par libfaketime) et le front CONSTRUIT servi par `vite preview` (même origine,
# /api/django et /static relayés vers Django — exactement la pile e2e de la CI).
#
#   pile.sh base   <db> [gabarit]                 clone le gabarit migré dans <db> (écrase <db>)
#   pile.sh migrer <worktree> <db>                applique les migrations du worktree sur <db>
#   pile.sh build  <worktree>                     `npm run build` du front (lien node_modules posé si absent)
#   pile.sh django <worktree> <db> <port> [reel | "AAAA-MM-JJ HH:MM[:SS]"]   (heure du Maroc ; défaut : reel)
#   pile.sh front  <worktree> <port_front> <port_django>
#   pile.sh stop   <django|front> <port>
#   pile.sh etat
set -euo pipefail
. /opt/taches-cloud/env.sh
[ -f /opt/taches-cloud/pile.conf ] && . /opt/taches-cloud/pile.conf
export DJANGO_SETTINGS_MODULE="${TACHES_REGLAGES:-erp_agentique.settings.dev}" PYTHONPATH="/opt/taches-cloud${PYTHONPATH:+:$PYTHONPATH}"
RUN=/opt/taches-cloud/run; LOGS=/opt/taches-cloud/logs
NM=/home/user/taqinor-os/.claude/worktrees/f2/frontend/node_modules
cmd="${1:-etat}"; shift || true

existe() { psql -h localhost -U erp_user -d postgres -Atc "select 1 from pg_database where datname='$1'" | grep -q 1; }
tuer() {  # tuer <fichier pid>
  if [ -f "$1" ]; then
    pid=$(cat "$1"); if kill -0 "$pid" 2>/dev/null; then kill -TERM -- "-$pid" 2>/dev/null || kill -TERM "$pid" 2>/dev/null || true; fi
    for _ in 1 2 3 4 5 6 7 8 9 10; do kill -0 "$pid" 2>/dev/null || break; python - <<'PY'
import time; time.sleep(0.3)
PY
    done
    kill -KILL -- "-$pid" 2>/dev/null || true; rm -f "$1"
  fi
}
attendre() {  # attendre <url> <secondes>
  python - "$1" "$2" <<'PY'
import sys, time, urllib.request, urllib.error
url, limite = sys.argv[1], float(sys.argv[2]); fin = time.monotonic() + limite
while time.monotonic() < fin:
    try:
        urllib.request.urlopen(url, timeout=3); sys.exit(0)
    except urllib.error.HTTPError:
        sys.exit(0)   # le serveur répond (401/404…) : il est debout
    except Exception:
        time.sleep(0.5)
print(f"pas de réponse de {url} en {limite:.0f} s", file=sys.stderr); sys.exit(1)
PY
}

case "$cmd" in
  base)
    db="$1"; gabarit="${2:-tpl_test}"
    existe "$gabarit" || { echo "gabarit $gabarit absent" >&2; exit 3; }
    psql -h localhost -U erp_user -d postgres -qc "select pg_terminate_backend(pid) from pg_stat_activity where datname='$db'" >/dev/null
    dropdb -h localhost -U erp_user --if-exists "$db"
    createdb -h localhost -U erp_user -T "$gabarit" "$db"; echo "base $db = clone de $gabarit" ;;
  sync)   # sync <worktree> <db> : base RAPIDE, tables créées depuis les modèles (sans migrations)
    wt="$1"; db="$2"
    psql -h localhost -U erp_user -d postgres -qc "select pg_terminate_backend(pid) from pg_stat_activity where datname='$db'" >/dev/null
    dropdb -h localhost -U erp_user --if-exists "$db"; createdb -h localhost -U erp_user "$db"
    cd "$wt/backend/django_core"; DJANGO_SETTINGS_MODULE=settings_sync DB_NAME="$db" python manage.py migrate --run-syncdb --noinput | tail -2 ;;
  migrer)
    wt="$1"; db="$2"; cd "$wt/backend/django_core"; DB_NAME="$db" python manage.py migrate --noinput | tail -3 ;;
  build)
    wt="$1"; cd "$wt/frontend"; [ -e node_modules ] || ln -s "$NM" node_modules
    npm run build 2>&1 | tail -5 ;;
  django)
    wt="$1"; db="$2"; port="$3"; quand="${4:-reel}"
    tuer "$RUN/django-$port.pid"
    cd "$wt/backend/django_core"
    export DB_NAME="$db" TACHES_DEMO_PASSWORD="${TACHES_DEMO_PASSWORD:-}"
    if [ "$quand" = reel ]; then
      setsid nohup python manage.py runserver "127.0.0.1:$port" --noreload > "$LOGS/django-$port.log" 2>&1 &
    else
      # Heure du Maroc → UTC par la base de fuseaux de Python (celle que Django lit), puis horloge figée au départ
      # (elle avance ensuite normalement). L'horloge monotone reste vraie : les délais réseau ne sont pas faussés.
      utc=$(python - "$quand" <<'PY'
import sys, datetime, zoneinfo
t = sys.argv[1].strip(); fmt = '%Y-%m-%d %H:%M:%S' if t.count(':') == 2 else '%Y-%m-%d %H:%M'
d = datetime.datetime.strptime(t, fmt).replace(tzinfo=zoneinfo.ZoneInfo('Africa/Casablanca'))
print(d.astimezone(datetime.timezone.utc).strftime('%Y-%m-%d %H:%M:%S'))
PY
)
      TZ=UTC DONT_FAKE_MONOTONIC=1 setsid nohup faketime -f "@$utc" python manage.py runserver "127.0.0.1:$port" --noreload > "$LOGS/django-$port.log" 2>&1 &
    fi
    echo $! > "$RUN/django-$port.pid"; echo "$quand" > "$RUN/django-$port.horloge"
    attendre "http://127.0.0.1:$port/api/django/health/" 90 && echo "django :$port prêt (base $db, horloge $quand)" ;;
  front)
    wt="$1"; pf="$2"; pd="$3"
    tuer "$RUN/front-$pf.pid"
    cd "$wt/frontend"; [ -e node_modules ] || ln -s "$NM" node_modules
    E2E_PROXY=1 E2E_API_TARGET="http://127.0.0.1:$pd" setsid nohup npx vite preview --port "$pf" --strictPort > "$LOGS/front-$pf.log" 2>&1 &
    echo $! > "$RUN/front-$pf.pid"
    attendre "http://localhost:$pf/" 60 && echo "front :$pf prêt → django :$pd" ;;
  stop) tuer "$RUN/$1-$2.pid"; echo "arrêté $1 :$2" ;;
  etat)
    for f in "$RUN"/*.pid; do [ -e "$f" ] || continue; pid=$(cat "$f"); n=$(basename "$f" .pid)
      if kill -0 "$pid" 2>/dev/null; then echo "$n vivant (pid $pid) $(cat "$RUN/$n.horloge" 2>/dev/null || true)"; else echo "$n MORT"; fi; done ;;
  *) echo "commande inconnue : $cmd" >&2; exit 2 ;;
esac
