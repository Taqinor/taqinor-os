# Mise à jour de la PRODUCTION (serveur Hetzner) en une commande, depuis ce PC :
#   powershell -File scripts\deploy-prod.ps1
#
# Ce que ça fait, dans l'ordre, sur le serveur :
#   1. git pull de main (la prod ne déploie QUE main, jamais dev)
#   2. rebuild des images + redémarrage des conteneurs (compose prod)
#   3. migrations de base de données
#   4. YHARD11 — healthcheck post-déploiement (core/health.py) ; si le service
#      est DOWN, ROLLBACK automatique au commit précédent (image+code) plutôt
#      que de laisser une prod cassée en place.
# Le serveur est la SOURCE DE VÉRITÉ des données ; ce PC reste le dev.
# Clé SSH dédiée : %USERPROFILE%\.ssh\taqinor_hetzner (jamais dans le dépôt).
#
# YHARD11 — convention expand/contract pour les migrations : voir
# docs/online-migrations.md. Ce script ne change PAS le mécanisme de
# déploiement (toujours manuel, jamais auto sur merge) — il ajoute seulement
# une garde de santé + un filet de rollback autour de l'existant.

$ErrorActionPreference = 'Stop'
$ServerIp = '178.105.192.116'
$Key = "$env:USERPROFILE\.ssh\taqinor_hetzner"

$remote = @'
set -e
cd /opt/taqinor-os
# YHARD11 — capture le commit courant AVANT le reset, pour un rollback exact
# si le healthcheck post-deploiement echoue plus bas.
PREV_SHA=$(git rev-parse HEAD)
echo "Commit precedent (rollback cible si besoin): $PREV_SHA"
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

# YHARD11 — healthcheck post-deploiement : interroge core/health.py cote
# interne au conteneur (pas de dependance reseau externe/DNS, pas de latence
# nginx/Caddy). check_db()/check_services() degradent proprement (jamais
# d'exception) ; on n'echoue le deploiement QUE si l'agregat global est "down".
set +e
# NB: python -c (une seule ligne), PAS un heredoc dans $(...) — un heredoc
# imbrique dans une substitution de commande casse quand tout le script est
# passe en UN SEUL argument SSH (« syntax error near unexpected token ( »
# -> faux rollback). Le one-liner est robuste (aucun delimiteur de heredoc).
HEALTH_STATUS=$(docker compose -f docker-compose.yml -f docker-compose.prod.yml exec -T django_core python -c "import django, os; os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'erp_agentique.settings.prod'); django.setup(); from core import health; print(health.overall_status(health.check_services()))" 2>/dev/null | tail -n 1 | tr -d '\r')
set -e
echo "Healthcheck post-deploiement: $HEALTH_STATUS"

if [ "$HEALTH_STATUS" = "down" ]; then
  echo "HEALTHCHECK ECHEC (down) -> ROLLBACK vers $PREV_SHA"
  git reset --hard "$PREV_SHA"
  docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build
  docker compose -f docker-compose.yml -f docker-compose.prod.yml restart nginx
  docker compose -f docker-compose.yml -f docker-compose.prod.yml exec -T caddy caddy reload --config /etc/caddy/Caddyfile
  echo "ROLLBACK TERMINE. Le code deploye est revenu a $PREV_SHA."
  echo "Migrations : si le nouveau code avait des migrations DESTRUCTIVES non"
  echo "expand/contract (voir docs/online-migrations.md), une intervention"
  echo "manuelle sur le schema peut rester necessaire — le rollback de code"
  echo "seul ne downgrade jamais le schema automatiquement."
  exit 1
fi
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
$deployExitCode = $LASTEXITCODE

# YHARD11 — un exit non-zero du bloc distant signifie que le healthcheck a
# echoue et qu'un rollback automatique a ete effectue cote serveur (voir
# ci-dessus). On le relaie clairement ici plutot que d'afficher le message de
# succes habituel.
if ($deployExitCode -ne 0) {
    Write-Host "`nHEALTHCHECK ECHEC - rollback automatique effectue sur le serveur." -ForegroundColor Red
    Write-Host "Le code deploye est revenu a l'etat precedent. Voir la sortie SSH ci-dessus pour le detail." -ForegroundColor Red
    exit $deployExitCode
}

Write-Host "`nDeploiement termine (healthcheck OK). Verifiez: https://178-105-192-116.sslip.io"
