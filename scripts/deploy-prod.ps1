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

ssh -i $Key -o StrictHostKeyChecking=accept-new "root@$ServerIp" @'
set -e
cd /opt/taqinor-os
git fetch origin main
git reset --hard origin/main
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build
docker compose -f docker-compose.yml -f docker-compose.prod.yml exec -T django_core python manage.py migrate --noinput
# nginx garde l'ancienne adresse de django apres recreation -> 502 sinon
docker compose -f docker-compose.yml -f docker-compose.prod.yml restart nginx
# PRECHAUFFAGE : le premier rendu PDF apres deploiement construit les caches
# de polices (fontconfig) et importe matplotlib — 30 s et plus a froid.
# On paie ce cout ICI, pas chez le premier commercial qui clique.
docker compose -f docker-compose.yml -f docker-compose.prod.yml exec -T django_core python -c "
import time; t0=time.time()
import matplotlib; matplotlib.use('Agg'); import matplotlib.pyplot as plt
from weasyprint import HTML
HTML(string='<p style=\"font-family:DejaVu Sans\">warmup</p>').write_pdf('/tmp/warmup.pdf')
fig, ax = plt.subplots(); ax.plot([1,2]); fig.savefig('/tmp/warmup.png'); plt.close(fig)
print('prechauffage PDF/graphiques: %.1fs' % (time.time()-t0))
"
docker compose -f docker-compose.yml -f docker-compose.prod.yml ps --format "{{.Name}} {{.Status}}"
'@

Write-Host "`nDeploiement termine. Verifiez: https://178-105-192-116.sslip.io"
