# Mise à jour de la PRODUCTION (serveur Hetzner) en une commande, depuis ce PC :
#   powershell -File scripts\deploy-prod.ps1
#
# Ce que ça fait, dans l'ordre, sur le serveur :
#   1. git pull de main (la prod ne déploie QUE main, jamais dev)
#   2. rebuild des images + redémarrage des conteneurs (compose prod)
#   3. migrations de base de données
# Le serveur est la SOURCE DE VÉRITÉ des données ; ce PC reste le dev.
# Clé SSH dédiée : %USERPROFILE%\.ssh\taqinor_hetzner (jamais dans le dépôt).

$ErrorActionPreference = 'Stop'
$ServerIp = '178.105.192.116'
$Key = "$env:USERPROFILE\.ssh\taqinor_hetzner"

$remote = @'
set -e
cd /opt/taqinor-os
git fetch origin main
git reset --hard origin/main
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build
docker compose -f docker-compose.yml -f docker-compose.prod.yml exec -T django_core python manage.py migrate --noinput
# Synchronise les permissions des roles systeme (Admin/Responsable/Utilisateur)
# avec roles/models.py : indispensable quand un deploiement ajoute de nouveaux
# codes de permission (ex. equipement_*/sav_*). Idempotent, sans effet sinon.
docker compose -f docker-compose.yml -f docker-compose.prod.yml exec -T django_core python manage.py init_roles
# nginx garde l'ancienne adresse de django apres recreation -> 502 sinon
docker compose -f docker-compose.yml -f docker-compose.prod.yml restart nginx
# La Caddyfile est un bind mount : un changement de config ne recree pas le
# conteneur -> reload explicite (zero coupure), sans effet si rien n'a change.
docker compose -f docker-compose.yml -f docker-compose.prod.yml exec -T caddy caddy reload --config /etc/caddy/Caddyfile
# PRECHAUFFAGE : le premier rendu PDF apres deploiement construit les caches
# de polices (fontconfig) et importe matplotlib — 30 s et plus a froid.
# On paie ce cout ICI, pas chez le premier commercial qui clique.
docker compose -f docker-compose.yml -f docker-compose.prod.yml exec -T django_core python <<'PYEOF'
import time; t0 = time.time()
import matplotlib; matplotlib.use('Agg'); import matplotlib.pyplot as plt
from weasyprint import HTML
HTML(string='<p>warmup</p>').write_pdf('/tmp/warmup.pdf')
fig, ax = plt.subplots(); ax.plot([1, 2]); fig.savefig('/tmp/warmup.png'); plt.close(fig)
print('prechauffage PDF/graphiques: %.1fs' % (time.time() - t0))
PYEOF
docker compose -f docker-compose.yml -f docker-compose.prod.yml ps
'@ -replace "`r`n", "`n"

# Pass the script as the ssh command ARGUMENT (normalized to LF). Two gotchas
# this avoids:
#  1. CRLF: the .ps1 is CRLF on Windows; an un-normalized here-string makes the
#     remote shell see `cd /opt/taqinor-os\r` and every command fails. Hence the
#     `-replace "`r`n","`n"` above.
#  2. Do NOT pipe via stdin (`$remote | ssh ... bash -s`): `docker compose exec -T`
#     consumes stdin, which would swallow the rest of the script (init_roles,
#     nginx restart, ...). As an argument, the remote stdin stays free.
ssh -i $Key -o StrictHostKeyChecking=accept-new "root@$ServerIp" $remote

Write-Host "`nDeploiement termine. Verifiez: https://178-105-192-116.sslip.io"
