# Mise à jour de la PRODUCTION (serveur Hetzner) en une commande, depuis ce PC :
#   powershell -File scripts\deploy-prod.ps1
#   powershell -File scripts\deploy-prod.ps1 -ZeroDowntime   # NTPLT57 (opt-in)
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

# NTPLT57 — déploiement ERP SANS coupure (opt-in, DÉFAUT OFF).
#   -ZeroDowntime : après migrations (compatibles N-1, expand/contract, voir
#   docs/online-migrations.md), démarre un NOUVEAU conteneur django à côté de
#   l'ancien (compose --scale django_core=2), attend son healthcheck interne,
#   recharge nginx, puis retire l'ancien (scale=1). Rollback = re-pointer
#   l'ancien conteneur (le scale-down laisse l'ancien tourner jusqu'au OK).
#   PRÉREQUIS : l'upstream nginx doit résoudre le service django par son NOM
#   compose (round-robin sur les réplicas) — sinon la bascule n'a aucun effet.
#   Sans le flag, le CHEMIN HISTORIQUE éprouvé est byte-identique (0 changement).
param(
    [switch]$ZeroDowntime
)

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
# WOW26 --remove-orphans : sans lui, un conteneur fastapi_ia orphelin bloquait
# la recreation ("Conflict. The container name is already in use") et, sous
# `set -e`, le script SORTAIT ICI -> migrate/init_roles/nginx SKIP -> 502 +
# migrations non appliquees (arrive sur les 2 deploiements du 2026-07-07).
# NETTOYAGE PRE-BUILD (incident 2026-07-10 : « no space left on device » en
# plein build apres plusieurs deploiements — chaque rebuild orphelinise les
# couches precedentes et le cache de build s'accumule sans borne). Dangling
# images + cache de build UNIQUEMENT : jamais les conteneurs qui tournent,
# jamais les volumes de donnees, jamais les images utilisees.
echo "Espace disque avant nettoyage :"; df -h / | tail -1
docker image prune -f || true
docker builder prune -f || true
echo "Espace disque apres nettoyage :"; df -h / | tail -1
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build --remove-orphans
# GARDE DB (incident 2026-07-10) : un changement du CONTENU d'un fichier
# bind-monte (ex. backend/db/postgresql.conf) ne change PAS le hash de config
# compose -> le conteneur db n'est PAS recree et Postgres tourne avec
# l'ANCIENNE conf en memoire. On attend pg_isready ; si la base ne repond
# pas, on redemarre db (relit la conf montee) et on re-attend. Sans cette
# garde, migrate echouait « Connection refused » et, sous set -e, le script
# MOURAIT AVANT le bloc healthcheck/rollback (fausse alerte « rollback
# effectue » alors que rien n'avait ete restaure).
wait_db() {
  # -h db : teste le LISTENER TCP via le reseau compose — sans -h, pg_isready
  # passe par la socket locale du conteneur et repond OK meme quand Postgres
  # n'ecoute QUE sur localhost (exactement le mode de panne qu'on guette).
  for i in $(seq 1 30); do
    if docker compose -f docker-compose.yml -f docker-compose.prod.yml exec -T db pg_isready -h db -q 2>/dev/null; then
      return 0
    fi
    sleep 3
  done
  return 1
}
if ! wait_db; then
  echo "DB injoignable apres 90s -> restart du conteneur db (relecture de la conf montee)"
  docker compose -f docker-compose.yml -f docker-compose.prod.yml restart db
  if ! wait_db; then
    echo "DB toujours injoignable apres restart -> ROLLBACK vers $PREV_SHA"
    git reset --hard "$PREV_SHA"
    docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build --remove-orphans
    docker compose -f docker-compose.yml -f docker-compose.prod.yml restart db nginx
    echo "ROLLBACK TERMINE (db injoignable). Code revenu a $PREV_SHA."
    exit 1
  fi
fi
# migrate sous filet : sous `set -e` nu, un echec ici TUAIT le script AVANT
# le bloc healthcheck/rollback (les « rollback effectue » des tentatives du
# 2026-07-10 etaient des faux positifs — rien n'avait ete restaure).
set +e
docker compose -f docker-compose.yml -f docker-compose.prod.yml exec -T django_core python manage.py migrate --noinput
MIGRATE_RC=$?
set -e
if [ "$MIGRATE_RC" != "0" ]; then
  echo "MIGRATE ECHEC (rc=$MIGRATE_RC) -> ROLLBACK vers $PREV_SHA"
  git reset --hard "$PREV_SHA"
  docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build --remove-orphans
  docker compose -f docker-compose.yml -f docker-compose.prod.yml restart db nginx
  echo "ROLLBACK TERMINE (migrate). Code revenu a $PREV_SHA."
  exit 1
fi
# WOW26 — verifie que TOUTES les migrations sont appliquees (un up -d partiel /
# un set -e interrompu laissait des migrations non appliquees + un 502 silencieux).
UNAPPLIED=$(docker compose -f docker-compose.yml -f docker-compose.prod.yml exec -T django_core python manage.py showmigrations --plan 2>/dev/null | grep -c '\[ \]')
echo "Migrations non appliquees restantes: $UNAPPLIED"
if [ "$UNAPPLIED" != "0" ]; then echo "MIGRATIONS INCOMPLETES ($UNAPPLIED) -> echec deploiement (relancer deploy-prod.ps1)"; exit 1; fi
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
  docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build --remove-orphans
  docker compose -f docker-compose.yml -f docker-compose.prod.yml restart nginx
  docker compose -f docker-compose.yml -f docker-compose.prod.yml exec -T caddy caddy reload --config /etc/caddy/Caddyfile
  echo "ROLLBACK TERMINE. Le code deploye est revenu a $PREV_SHA."
  echo "Migrations : si le nouveau code avait des migrations DESTRUCTIVES non"
  echo "expand/contract (voir docs/online-migrations.md), une intervention"
  echo "manuelle sur le schema peut rester necessaire — le rollback de code"
  echo "seul ne downgrade jamais le schema automatiquement."
  exit 1
fi

# NTPLT57 — bascule SANS coupure (opt-in ZERO_DOWNTIME=1). Le healthcheck
# ci-dessus a deja valide la nouvelle image ; ici on remplace l'ancien
# conteneur django par un neuf SANS fenetre de coupure : scale a 2 (l'ancien
# continue de servir), on attend le healthcheck du 2e, on recharge nginx
# (round-robin sur les 2), puis on retire l'ancien (scale a 1). Rollback : si
# le 2e conteneur ne devient pas sain, on redescend a 1 (l'ancien, toujours
# vivant, n'a jamais cesse de servir) et on sort en echec. Sans le flag, ce
# bloc est entierement saute (chemin historique inchange).
if [ "$ZERO_DOWNTIME" = "1" ]; then
  echo "NTPLT57 — bascule sans coupure : scale django_core=2"
  docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --no-deps --no-recreate --scale django_core=2 django_core
  echo "Attente du healthcheck du nouveau conteneur (max 90s)..."
  ZD_OK=0
  for i in $(seq 1 30); do
    ZD_STATUS=$(docker compose -f docker-compose.yml -f docker-compose.prod.yml exec -T django_core python -c "import django, os; os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'erp_agentique.settings.prod'); django.setup(); from core import health; print(health.overall_status(health.check_services()))" 2>/dev/null | tail -n 1 | tr -d '\r')
    if [ "$ZD_STATUS" != "down" ] && [ -n "$ZD_STATUS" ]; then ZD_OK=1; break; fi
    sleep 3
  done
  if [ "$ZD_OK" != "1" ]; then
    echo "NTPLT57 — nouveau conteneur NON sain -> redescente a 1 (l'ancien sert toujours), pas de coupure"
    docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --no-deps --scale django_core=1 django_core
    docker compose -f docker-compose.yml -f docker-compose.prod.yml restart nginx
    echo "NTPLT57 — bascule sans coupure ANNULEE (rollback vers l'ancien conteneur)."
    exit 1
  fi
  # Les deux repliques sont saines : recharge nginx (round-robin) puis retire
  # l'ancien conteneur (retour a une seule replique neuve).
  docker compose -f docker-compose.yml -f docker-compose.prod.yml restart nginx
  docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --no-deps --scale django_core=1 django_core
  docker compose -f docker-compose.yml -f docker-compose.prod.yml restart nginx
  echo "NTPLT57 — bascule sans coupure TERMINEE (ancien conteneur retire)."
fi
'@ -replace "`r`n", "`n"

# NTPLT57 — injecte l'etat du flag -ZeroDowntime en tete du script distant
# (le here-string ci-dessus est LITTERAL : on prefixe l'affectation ici).
$zdFlag = if ($ZeroDowntime) { '1' } else { '0' }
$remote = "ZERO_DOWNTIME=$zdFlag`n" + $remote

# Transport du script : FICHIER (scp) puis execution — jamais en argument ssh
# ni via stdin. Trois gotchas que ce choix evite :
#  1. CRLF: the .ps1 is CRLF on Windows; an un-normalized here-string makes the
#     remote shell see `cd /opt/taqinor-os\r` and every command fails. Hence the
#     `-replace "`r`n","`n"` above.
#  2. Do NOT pipe via stdin (`$remote | ssh ... bash -s`): `docker compose exec -T`
#     consumes stdin, which would swallow the rest of the script (init_roles,
#     nginx restart, ...). With a file, the remote stdin stays free.
#  3. Do NOT pass the script as the ssh command ARGUMENT: Windows PowerShell 5.1
#     mangles native-command quoting on embedded double quotes in a multi-line
#     argument — the remote bash received a script split mid-line
#     (« syntax error near unexpected token ( » at the first $(...), rien
#     n'etait execute, et le message rollback etait un faux positif).
$tmpScript = Join-Path $env:TEMP 'taqinor-deploy-remote.sh'
[IO.File]::WriteAllText($tmpScript, $remote)  # LF, sans BOM
& scp -i $Key -o StrictHostKeyChecking=accept-new $tmpScript "root@${ServerIp}:/tmp/taqinor-deploy-remote.sh"
if ($LASTEXITCODE -ne 0) {
    Write-Error "scp du script de deploiement a echoue (code $LASTEXITCODE)."
    exit 1
}
ssh -i $Key -o StrictHostKeyChecking=accept-new "root@$ServerIp" 'bash /tmp/taqinor-deploy-remote.sh'
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
