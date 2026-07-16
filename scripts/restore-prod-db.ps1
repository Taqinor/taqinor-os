# RESTAURATION D'URGENCE (incident 2026-07-10) — AUCUN build, AUCUN reset git.
# Le code et les images sont deja sur la boite ; la SEULE panne restante est
# PostgreSQL qui n'ecoute que sur localhost (ancienne conf en memoire).
# Sequence minimale : restart db (relit backend/db/postgresql.conf, deja
# corrige sur le disque) -> attente du listener TCP -> migrate -> init_roles
# -> restart nginx -> healthcheck. Transport fichier (scp) comme deploy-prod.
$ErrorActionPreference = 'Stop'
$ServerIp = '178.105.192.116'
$Key = "$env:USERPROFILE\.ssh\taqinor_hetzner"

$remote = @'
set -e
cd /opt/taqinor-os
echo "HEAD actuel: $(git rev-parse HEAD)"
grep -n "listen_addresses" backend/db/postgresql.conf || { echo "conf SANS listen_addresses -> STOP"; exit 1; }
docker compose -f docker-compose.yml -f docker-compose.prod.yml restart db
for i in $(seq 1 30); do
  if docker compose -f docker-compose.yml -f docker-compose.prod.yml exec -T db pg_isready -h db -q 2>/dev/null; then
    echo "DB ecoute sur le reseau (tentative $i)"; break
  fi
  if [ "$i" = "30" ]; then echo "DB toujours injoignable apres 90s"; exit 1; fi
  sleep 3
done
docker compose -f docker-compose.yml -f docker-compose.prod.yml exec -T django_core python manage.py migrate --noinput
UNAPPLIED=$(docker compose -f docker-compose.yml -f docker-compose.prod.yml exec -T django_core python manage.py showmigrations --plan 2>/dev/null | grep -c '\[ \]')
echo "Migrations non appliquees restantes: $UNAPPLIED"
if [ "$UNAPPLIED" != "0" ]; then echo "MIGRATIONS INCOMPLETES ($UNAPPLIED)"; exit 1; fi
docker compose -f docker-compose.yml -f docker-compose.prod.yml exec -T django_core python manage.py init_roles
docker compose -f docker-compose.yml -f docker-compose.prod.yml restart nginx
set +e
HEALTH_STATUS=$(docker compose -f docker-compose.yml -f docker-compose.prod.yml exec -T django_core python -c "import django, os; os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'erp_agentique.settings.prod'); django.setup(); from core import health; print(health.overall_status(health.check_services()))" 2>/dev/null | tail -n 1 | tr -d '\r')
set -e
echo "Healthcheck: $HEALTH_STATUS"
docker compose -f docker-compose.yml -f docker-compose.prod.yml ps
'@ -replace "`r`n", "`n"

$tmpScript = Join-Path $env:TEMP 'taqinor-restore-db.sh'
[IO.File]::WriteAllText($tmpScript, $remote)
& scp -i $Key -o StrictHostKeyChecking=accept-new $tmpScript "root@${ServerIp}:/tmp/taqinor-restore-db.sh"
if ($LASTEXITCODE -ne 0) { Write-Error "scp a echoue"; exit 1 }
ssh -i $Key -o StrictHostKeyChecking=accept-new "root@$ServerIp" 'bash /tmp/taqinor-restore-db.sh'
exit $LASTEXITCODE
