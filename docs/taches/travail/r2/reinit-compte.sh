#!/usr/bin/env bash
# Usage : reinit-compte.sh <compte> [heure HH:MM, défaut 09:10] [--vide]
# Remet à neuf la journée d'exemple d'UN compte (jour = aujourd'hui) dans le conteneur taches-r2-django.
set -euo pipefail
export MSYS_NO_PATHCONV=1
ICI="$(cd "$(dirname "$0")" && pwd)"
COMPTE="${1:?compte}"; HEURE="${2:-09:10}"; VIDE=0
[ "${2:-}" = "--vide" ] && { VIDE=1; HEURE=09:10; }
[ "${3:-}" = "--vide" ] && VIDE=1
docker exec -i -e COMPTE="$COMPTE" -e HEURE="$HEURE" -e VIDE="$VIDE" taches-r2-django python manage.py shell < "$ICI/semer_compte.py" 2>&1 | grep -v -E "^\?:|HINT|WARNINGS|System check|^$|objects imported"
