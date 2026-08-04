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
# ── VERROU PARTAGE AVEC L'AUTO-DEPLOIEMENT (incident du 04/08/2026) ─────────
# Le serveur porte un service `taqinor-autodeploy` qui deploie TOUT SEUL des
# que `origin/main` bouge — donc a CHAQUE fusion. Il prend un verrou
# (`flock -n` sur /opt/autodeploy/deploy.lock) qui empeche deux
# auto-deploiements de se chevaucher, mais le deploiement MANUEL ne le prenait
# pas : rien n'empechait la collision.
#
# CE QUE CA A COUTE, mesure dans /opt/autodeploy/deploy.log : l'auto-deploiement
# de la fusion precedente a tourne de 23h43 a 00h27 (44 min). Un deploiement
# manuel lance a 00h09 a construit la BONNE image (2,71 Go, torch CPU) ;
# l'auto-deploiement, parti d'un commit ANTERIEUR, a fini EN DERNIER et a
# reecrit l'etiquette avec son ancienne image de 9,25 Go. Le dernier arrive
# gagne, meme s'il porte du code plus vieux. Pire : le `git reset --hard`
# ci-dessous change le code SOUS une construction en cours — d'ou la prise du
# verrou AVANT lui, jamais apres.
#
# Ici on ATTEND (45 min max) au lieu de sortir en silence : un deploiement
# manuel est un ordre explicite, on ne l'abandonne pas sans le dire. Si le
# verrou ne vient pas, on sort SANS avoir rien touche.
mkdir -p /opt/autodeploy
exec 9>/opt/autodeploy/deploy.lock
if ! flock -n 9; then
  echo "Un deploiement tourne DEJA (auto-deploiement ou autre session)."
  echo "Dernieres lignes de son journal :"
  tail -3 /opt/autodeploy/deploy.log 2>/dev/null || echo "  (journal indisponible)"
  echo "Attente du verrou (45 min max) — rien n'a encore ete modifie..."
  if ! flock -w 2700 9; then
    echo "VERROU TOUJOURS PRIS APRES 45 MIN -> on n'a RIEN touche."
    echo "Verifier: systemctl status taqinor-autodeploy ; tail /opt/autodeploy/deploy.log"
    exit 1
  fi
  echo "Verrou obtenu, le deploiement precedent est termine. On continue."
fi
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
# NETTOYAGE (incident 2026-07-10 : « no space left on device » en plein build —
# le cache s'accumulait sans borne). L'ANCIEN remede (`docker builder prune -f`
# AVANT le build) effacait TOUT le cache a chaque deploiement -> rebuild a froid
# integral (apt Pango/WeasyPrint + pip Django & FastAPI + npm ci + vite), soit
# 15-25 min par deploiement. NOUVELLE politique (2026-07-16) : cache BORNE, pas
# efface — le prune passe APRES le build (fin de script, chemin succes) avec
# --keep-storage : les couches encore utiles survivent, le vieux cache part, le
# disque reste borne et un deploiement code-seul redevient chaud (~2-4 min).
# Ici, avant build : seulement les images dangling (sans effet sur le cache).
echo "Espace disque avant build :"; df -h / | tail -1
docker image prune -f || true
# FILET « container name already in use » (incident 02/08/2026). Quand un
# conteneur met trop de temps a s'arreter, compose l'a deja RENOMME en
# <hash>_<nom> avant de creer le neuf ; si l'arret echoue, l'ancien garde le
# nom et la creation echoue. La vraie correction est `stop_grace_period` sur
# les services celery (docker-compose.yml) ; ceci est le filet : on retire les
# survivants renommes AVANT de recreer, sinon un seul incident bloque tous les
# deploiements suivants. Ne touche QUE les noms prefixes d'un hash — jamais un
# conteneur sain.
ORPHELINS=$(docker ps -a --format '{{.Names}}' | grep -E '^[0-9a-f]{12}_erp-agentique-' || true)
if [ -n "$ORPHELINS" ]; then
  echo "Conteneurs renommes par un arret rate, on les retire : $ORPHELINS"
  echo "$ORPHELINS" | xargs -r docker rm -f || true
fi
# ── CONSTRUCTION SELECTIVE (03/08/2026) — la plus grosse economie du script ──
# CONSTAT MESURE : en production, le code backend est MONTE par-dessus /app
# (bind `/opt/taqinor-os/backend/django_core -> /app`, verifie sur le conteneur
# en cours). La couche `COPY . /app/` des images Django/FastAPI est donc
# TOTALEMENT IGNOREE a l'execution : reconstruire ces images a chaque
# deploiement de code ne change strictement RIEN a ce qui tourne.
# Elles ne doivent etre reconstruites que si leur Dockerfile ou leurs
# dependances changent. Le FRONTEND, lui, compile ses fichiers DANS l'image
# (aucun montage) : il se reconstruit des que son code bouge.
#
# Politique : on liste ce qui a change entre l'ancien commit et le nouveau, et
# on ne reconstruit que les services concernes. EN CAS DE DOUTE -> tout
# reconstruire (premier deploiement, commit precedent inconnu, comparaison
# impossible) : un deploiement lent est benin, un deploiement qui livre une
# image perimee ne l'est pas.
CHANGES=$(git diff --name-only "$PREV_SHA" HEAD 2>/dev/null || echo "__INCONNU__")
A_CONSTRUIRE=""
if [ "$CHANGES" = "__INCONNU__" ] || [ -z "$PREV_SHA" ]; then
  echo "Commit precedent inconnu -> reconstruction COMPLETE (choix prudent)."
else
  # ATTENTION `if ... then` et JAMAIS `grep -q … && VAR=…` : sous `set -e`, un
  # `grep` qui ne trouve RIEN sort en 1, le `&&` propage ce 1 comme statut de la
  # commande, et le script MEURT ICI. C'est exactement l'incident du 2026-07-09
  # (`grep -c` renvoyant 1 quand il comptait zero occurrence) qui tuait le
  # deploiement precisement quand tout allait bien. Ne pas reintroduire.
  if echo "$CHANGES" | grep -qE '^backend/django_core/(Dockerfile|requirements.*\.txt)$'; then
    A_CONSTRUIRE="$A_CONSTRUIRE django_core"
  fi
  if echo "$CHANGES" | grep -qE '^backend/fastapi_ia/(Dockerfile|requirements.*\.txt)$'; then
    A_CONSTRUIRE="$A_CONSTRUIRE fastapi_ia"
  fi
  if echo "$CHANGES" | grep -qE '^(frontend/|apps/web/src/|package(-lock)?\.json)'; then
    A_CONSTRUIRE="$A_CONSTRUIRE frontend"
  fi
  if echo "$CHANGES" | grep -qE '(nginx)'; then
    A_CONSTRUIRE="$A_CONSTRUIRE nginx"
  fi
  # Le compose lui-meme a bouge : on ne parie pas, on reconstruit tout.
  if echo "$CHANGES" | grep -qE '^docker-compose(\.prod)?\.yml$'; then
    A_CONSTRUIRE="__TOUT__"
  fi
fi

# FILET : si l'une des images attendues MANQUE (cache purge, disque nettoye,
# premier deploiement sur une machine neuve), sauter la construction ferait
# tenter un `pull` d'une image qui n'existe sur aucun registre -> echec. On
# reconstruit tout dans ce cas, sans discuter.
for IMG in erp-agentique-django_core erp-agentique-fastapi_ia erp-agentique-frontend erp-agentique-nginx; do
  if ! docker image inspect "$IMG" >/dev/null 2>&1; then
    echo "Image absente : $IMG -> reconstruction COMPLETE (filet)."
    A_CONSTRUIRE="__TOUT__"
  fi
done

if [ "$A_CONSTRUIRE" = "__TOUT__" ] || [ "$CHANGES" = "__INCONNU__" ] || [ -z "$PREV_SHA" ]; then
  echo "Construction COMPLETE."
  docker compose -f docker-compose.yml -f docker-compose.prod.yml build
elif [ -n "$A_CONSTRUIRE" ]; then
  echo "Construction CIBLEE :$A_CONSTRUIRE"
  # shellcheck disable=SC2086
  docker compose -f docker-compose.yml -f docker-compose.prod.yml build $A_CONSTRUIRE
else
  echo "Aucune image a reconstruire (code seul, monte par bind) — on saute la construction."
  RIEN_CONSTRUIT=1
fi
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --remove-orphans
# ── PIEGE DE LA CONSTRUCTION SAUTEE — NE PAS RETIRER ────────────────────────
# Quand on saute la construction, AUCUNE image ne change d'identifiant, donc
# `up -d` ne recree AUCUN conteneur (compose compare la config et l'image, pas
# le contenu d'un bind-mount). Or gunicorn tourne SANS --reload en production :
# le code Python fraichement recupere par `git reset` resterait dans le dossier
# monte sans jamais etre charge. Le deploiement serait RAPIDE ET INERTE — pire
# qu'un deploiement lent, parce qu'il annonce « OK » sans rien livrer.
# AVANT cette optimisation, le probleme n'existait pas par accident : la couche
# `COPY . /app/` changeait a chaque commit, donc l'image changeait, donc
# compose recreait. C'est cet effet de bord qui portait la mise a jour.
# On redemarre donc explicitement les services qui servent du code MONTE.
# Le frontend et nginx ne sont PAS concernes : leur contenu vit dans l'image,
# et si elle a change ils ont deja ete recrees par `up -d` ci-dessus.
if [ "${RIEN_CONSTRUIT:-0}" = "1" ]; then
  echo "Redemarrage des services qui servent du code monte (gunicorn n'a pas de --reload)..."
  docker compose -f docker-compose.yml -f docker-compose.prod.yml restart \
    django_core celery_worker celery_worker_interactive celery_beat fastapi_ia
fi
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
# ATTENTION `|| true` OBLIGATOIRE : `grep -c` sort en 1 quand il compte ZERO
# occurrence. Sous `set -e`, l'affectation mourait donc EXACTEMENT quand tout
# etait applique — c'est-a-dire a chaque deploiement PROPRE. Le script sautait
# alors init_roles / restart nginx / reload caddy / prechauffage / healthcheck,
# sortait non-zero, et l'enveloppe PowerShell annoncait « HEALTHCHECK ECHEC -
# rollback » alors que la sonde n'avait jamais ete interrogee (elle repondait
# « ok »). Diagnostic 2026-08-02 : la sortie SSH s'arretait net apres « No
# migrations to apply ».
UNAPPLIED=$(docker compose -f docker-compose.yml -f docker-compose.prod.yml exec -T django_core python manage.py showmigrations --plan 2>/dev/null | grep -c '\[ \]' || true)
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

# NETTOYAGE POST-BUILD (chemin succes uniquement — un rollback sort avant et
# garde donc son cache chaud pour re-builder vite). Les images des anciens
# conteneurs viennent d'etre orphelinisees par la recreation -> prune ; le
# cache de build est BORNE a 8 Go (les couches du build qu'on vient de faire
# sont les plus recentes, elles survivent ; l'ancien cache part). C'est la
# borne anti « no space left » du 2026-07-10, sans le rebuild a froid.
docker image prune -f || true
docker builder prune -f --keep-storage=8g || true
echo "Espace disque apres nettoyage post-build :"; df -h / | tail -1
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
