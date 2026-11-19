#!/usr/bin/env bash
# (Re)crée le conteneur taches-r2-django (port hôte 8010) sur la base erp_taches_r2 et un Redis à part (taches-r2-redis).
# Ne touche à AUCUN conteneur erp-agentique-*. Le mot de passe vient de scratchpad/r2/env.local (non suivi).
export MSYS_NO_PATHCONV=1
S='C:\Users\kasri\AppData\Local\Temp\claude\75bbe857427ccce5\b797bc27-f912-4ba8-a54b-d982221d7224\scratchpad\r2'
W='C:\dev\taqinor-os\.claude\worktrees\taches-r2'
docker start taches-r2-redis >/dev/null 2>&1 || docker run -d --name taches-r2-redis --network erp-agentique_default redis:7-alpine >/dev/null
docker rm -f taches-r2-django >/dev/null 2>&1
# DB_CONN_MAX_AGE=0 : sinon runserver garde ~1 connexion/thread et le Postgres partagé (max 100) sature
# (« too many clients already » -> 500 -> l'appli affiche « Hors ligne »).
docker run -d --name taches-r2-django --network erp-agentique_default -p 8010:8000 \
 --env-file 'C:\dev\taqinor-os\.env' --env-file "$S\env.local" \
 -e DB_NAME=erp_taches_r2 -e DB_CONN_MAX_AGE=0 -e REDIS_HOST=taches-r2-redis -e REDIS_CACHE_HOST=taches-r2-redis \
 -e DJANGO_SETTINGS_MODULE=erp_agentique.settings.dev -e DJANGO_DEBUG=True -e DJANGO_ALLOWED_HOSTS='*' \
 -e TENANT_RATE_LIMIT=0 -e LOGIN_RATE_LIMIT=1000/minute \
 -v "$W\backend\django_core:/app" -v "$W\STAGES.py:/opt/STAGES.py:ro" \
 erp-agentique-django_core:latest bash -c "python manage.py migrate --noinput && python manage.py init_roles && python manage.py runserver 0.0.0.0:8000"
