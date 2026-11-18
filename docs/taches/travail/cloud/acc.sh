#!/bin/bash
# Commande de pile des acceptations « Tâches » (variable E2E_TACHES_PILE des specs) :
#   acc.sh semer <options de seed_taches_demo…>   vide le cache, arrête Django, rejoue le semis (horloge réelle)
#   acc.sh horloge "AAAA-MM-JJ HH:MM" | reel      (re)lance Django à cette heure du Maroc (ou à l'heure réelle)
#   acc.sh manage <commande manage.py…>           une commande manage.py sur la base de la pile
#   acc.sh etat
# Pile = worktree TACHES_WT (défaut : f2), base TACHES_DB (défaut : erp_acc), Django :TACHES_PORT (8000).
set -euo pipefail
. /opt/taches-cloud/env.sh
[ -f /opt/taches-cloud/pile.conf ] && . /opt/taches-cloud/pile.conf
# TACHES_FIDELE=1 : cette pile-ci tourne sur une base MIGRÉE avec les réglages de la CI, quoi que dise pile.conf.
[ "${TACHES_FIDELE:-0}" = 1 ] && unset TACHES_REGLAGES
export DJANGO_SETTINGS_MODULE="${TACHES_REGLAGES:-erp_agentique.settings.dev}" PYTHONPATH="/opt/taches-cloud${PYTHONPATH:+:$PYTHONPATH}"; . /opt/taches-cloud/secret.env
WT="${TACHES_WT:-/home/user/taqinor-os/.claude/worktrees/f2}"; DB="${TACHES_DB:-erp_acc}"; PORT="${TACHES_PORT:-8000}"
# Chaque pile a SON Redis (cache, débits, sessions) : un semis ne vide que le sien.
export REDIS_PORT="${TACHES_REDIS_PORT:-6379}"
cmd="${1:-etat}"; shift || true
case "$cmd" in
  semer)
    /opt/taches-cloud/pile.sh stop django "$PORT" >/dev/null
    redis-cli -p "$REDIS_PORT" flushall >/dev/null
    cd "$WT/backend/django_core"; DB_NAME="$DB" python manage.py seed_taches_demo "$@" ;;
  horloge)
    TACHES_DEMO_PASSWORD="$TACHES_DEMO_PASSWORD" /opt/taches-cloud/pile.sh django "$WT" "$DB" "$PORT" "${1:-reel}" ;;
  manage)
    cd "$WT/backend/django_core"; DB_NAME="$DB" python manage.py "$@" ;;
  etat) /opt/taches-cloud/pile.sh etat ;;
  *) echo "commande inconnue : $cmd" >&2; exit 2 ;;
esac
