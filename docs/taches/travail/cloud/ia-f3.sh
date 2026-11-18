#!/bin/bash
# Service d'IA (FastAPI, backend/fastapi_ia) SANS CLÉ pour la pile n° 2 (fusion 3) — acceptation TCH143.
#   ia-f3.sh demarrer <worktree> [port=8100]   lance uvicorn sous la MÊME horloge que Django :8001
#                                              (lue dans run/django-8001.horloge : « reel » ou « AAAA-MM-JJ HH:MM »)
#   ia-f3.sh arreter [port=8100]
#   ia-f3.sh etat [port=8100]
# Le front construit (:4174, `vite preview`) ne relaie que /api/django : la spec branche /api/fastapi sur ce service par
# une route Playwright (convention de aic.spec.js : E2E_IA_URL=http://127.0.0.1:8100, jeton de session en Bearer).
# Aucune clé d'IA : CLAUDE_API_KEY / GROQ_API_KEY restent vides (le service répond par son message de configuration).
set -euo pipefail
RUN=/opt/taches-cloud/run; LOGS=/opt/taches-cloud/logs
cmd="${1:-etat}"; shift || true
tuer() {
  if [ -f "$1" ]; then
    pid=$(cat "$1"); kill -TERM -- "-$pid" 2>/dev/null || kill -TERM "$pid" 2>/dev/null || true
    for _ in 1 2 3 4 5 6 7 8 9 10; do kill -0 "$pid" 2>/dev/null || break; sleep 0.3; done
    kill -KILL -- "-$pid" 2>/dev/null || true; rm -f "$1"
  fi
}
case "$cmd" in
  demarrer)
    wt="$1"; port="${2:-8100}"
    tuer "$RUN/ia-$port.pid"
    . /opt/taches-cloud/env-ia.sh
    export DB_NAME=erp_f3 REDIS_PORT=6380 DJANGO_INTERNAL_URL=http://127.0.0.1:8001 DJANGO_DEBUG=True \
      SQL_AGENT_PROVIDER=groq SQL_AGENT_FALLBACK_PROVIDER=groq ASSISTANT_MOTEUR=langchain \
      CLAUDE_API_KEY= GROQ_API_KEY= OPENAI_API_KEY= HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1
    quand=$(cat "$RUN/django-8001.horloge" 2>/dev/null || echo reel)
    cd "$wt/backend/fastapi_ia"
    if [ "$quand" = reel ]; then
      setsid nohup uvicorn app.main:app --host 127.0.0.1 --port "$port" > "$LOGS/ia-$port.log" 2>&1 &
    else
      # L'horloge de Django est figée AU DÉMARRAGE de Django puis avance : on part de sa valeur ACTUELLE
      # (horloge + temps écoulé depuis le fichier pid de Django) et on prend 5 s d'avance, pour qu'un jeton
      # émis par Django (`iat`) ne soit jamais « dans le futur » pour le service d'IA (PyJWT : ImmatureSignatureError).
      debut=$(stat -c %Y "$RUN/django-8001.pid")
      utc=$(python - "$quand" "$debut" <<'PY'
import sys, time, datetime, zoneinfo
t = sys.argv[1].strip(); fmt = '%Y-%m-%d %H:%M:%S' if t.count(':') == 2 else '%Y-%m-%d %H:%M'
d = datetime.datetime.strptime(t, fmt).replace(tzinfo=zoneinfo.ZoneInfo('Africa/Casablanca'))
d += datetime.timedelta(seconds=time.time() - float(sys.argv[2]) + 5)
print(d.astimezone(datetime.timezone.utc).strftime('%Y-%m-%d %H:%M:%S'))
PY
)
      /opt/taches-cloud/faketime-nettoyer.sh
      TZ=UTC setsid nohup faketime -f "@$utc" uvicorn app.main:app --host 127.0.0.1 --port "$port" \
        > "$LOGS/ia-$port.log" 2>&1 &
    fi
    echo $! > "$RUN/ia-$port.pid"; echo "$quand" > "$RUN/ia-$port.horloge"
    for _ in $(seq 1 120); do
      if curl -fsS "http://127.0.0.1:$port/health" >/dev/null 2>&1; then echo "ia :$port prêt (horloge $quand)"; exit 0; fi
      sleep 0.5
    done
    echo "ia :$port : pas de réponse (voir $LOGS/ia-$port.log)" >&2; exit 1 ;;
  arreter) tuer "$RUN/ia-${1:-8100}.pid"; echo "arrêté ia :${1:-8100}" ;;
  etat) p="${1:-8100}"; if [ -f "$RUN/ia-$p.pid" ] && kill -0 "$(cat "$RUN/ia-$p.pid")" 2>/dev/null; then echo "ia :$p vivant ($(cat "$RUN/ia-$p.horloge"))"; else echo "ia :$p arrêté"; fi ;;
  *) echo "commande inconnue : $cmd" >&2; exit 2 ;;
esac
