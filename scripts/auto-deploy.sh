#!/usr/bin/env bash
# Auto-déploiement Taqinor OS — LA COPIE DE RÉFÉRENCE, VERSIONNÉE ICI.
#
# ── Pourquoi ce fichier est dans le dépôt (04/08/2026) ──────────────────────
# Il vivait UNIQUEMENT sur le serveur (`/opt/autodeploy/auto-deploy.sh`, créé le
# 16/06). Il n'était donc ni relu, ni sauvegardé, ni versionné — alors qu'il
# pilote la production à chaque fusion. Si le serveur tombait, il était perdu.
# Il est désormais versionné ici, et `scripts/deploy-prod.ps1` l'INSTALLE sur le
# serveur à chaque déploiement manuel : cette copie est la source de vérité.
#
# ── Ce qu'il fait ───────────────────────────────────────────────────────────
# Sonde `origin/main` ~chaque minute (timer systemd `taqinor-autodeploy`) et ne
# déploie QUE si main a bougé depuis le dernier déploiement. Verrou flock
# (jamais deux déploiements simultanés — le déploiement MANUEL prend le MÊME
# verrou depuis l'incident du 04/08), journal horodaté (une ligne par
# déploiement), et saut du rebuild pour les commits purement docs/markdown.
#
# Sortie détaillée (build docker, migrations…) -> journalctl -u taqinor-autodeploy
# Résumé horodaté propre                       -> /opt/autodeploy/deploy.log
#
# ATTENTION : `set -uo pipefail` mais PAS `set -e` (choix d'origine, conservé) —
# chaque étape est testée explicitement via `|| ok=0`. Toute variable doit être
# initialisée avant usage, sinon `set -u` fait sortir le script.
set -uo pipefail

REPO=/opt/taqinor-os
STATE=/opt/autodeploy
LOG="$STATE/deploy.log"
LAST="$STATE/last_deployed_commit"
LOCK="$STATE/deploy.lock"
COMPOSE="docker compose -f docker-compose.yml -f docker-compose.prod.yml"

log() { echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] $*" >> "$LOG"; }

mkdir -p "$STATE"

# Verrou non bloquant : si un déploiement tourne déjà, on sort sans rien faire.
# Le déploiement manuel (`deploy-prod.ps1`) prend CE MÊME verrou — sans quoi les
# deux se marchent dessus : mesuré le 04/08, un manuel avait construit la bonne
# image (2,71 Go) et l'auto, parti d'un commit ANTÉRIEUR, a fini en dernier et
# réécrit l'étiquette avec son ancienne image de 9,25 Go.
exec 9>"$LOCK"
flock -n 9 || exit 0

cd "$REPO" || { log "ERREUR: dépôt $REPO introuvable"; exit 1; }

git fetch origin main --quiet || { log "ERREUR: git fetch a échoué"; exit 1; }
NEW=$(git rev-parse origin/main)
OLD=$(cat "$LAST" 2>/dev/null || echo "")

# Rien de neuf -> sortie silencieuse (pas de bruit dans le journal).
[ "$NEW" = "$OLD" ] && exit 0

SHORT=$(git rev-parse --short "$NEW")

# Changement purement docs/markdown ? (markdown, .txt, ou sous docs/) -> on
# rafraîchit l'arbre de travail mais on saute rebuild/migration/restart/préchauffage.
DOCS_ONLY=0
CHANGES=""
if [ -n "$OLD" ] && git cat-file -e "${OLD}^{commit}" 2>/dev/null; then
  CHANGES=$(git diff --name-only "$OLD" "$NEW" || echo "")
  NONDOC=$(echo "$CHANGES" | grep -vE '(\.(md|markdown|txt)$)|(^docs/)' || true)
  [ -z "$NONDOC" ] && DOCS_ONLY=1
fi

git reset --hard "$NEW" || { log "ERREUR: git reset --hard $SHORT a échoué"; exit 1; }

if [ "$DOCS_ONLY" = "1" ]; then
  log "DEPLOY $SHORT — docs/markdown uniquement : rebuild ignoré"
  echo "$NEW" > "$LAST"
  exit 0
fi

# ── CONSTRUCTION SÉLECTIVE (04/08/2026) ─────────────────────────────────────
# En production le code backend est MONTÉ par-dessus /app (bind vérifié sur le
# conteneur). La couche `COPY . /app/` des images Django/FastAPI est donc
# IGNORÉE à l'exécution : les reconstruire à chaque commit de code ne change
# RIEN à ce qui tourne. Le FRONTEND, lui, compile dans son image (aucun
# montage) : il se reconstruit dès que son code bouge.
# EN CAS DE DOUTE -> tout reconstruire. Un déploiement lent est bénin ; un
# déploiement qui livre une image périmée ne l'est pas.
A_CONSTRUIRE=""
TOUT=0
if [ -z "$CHANGES" ]; then
  TOUT=1   # commit précédent inconnu ou diff impossible : on ne parie pas.
else
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
  if echo "$CHANGES" | grep -qE '^docker-compose(\.prod)?\.yml$'; then
    TOUT=1
  fi
fi
# Filet : une image attendue absente (cache purgé, machine neuve) -> sauter la
# construction ferait tenter un `pull` d'une image qui n'existe nulle part.
for IMG in erp-agentique-django_core erp-agentique-fastapi_ia \
           erp-agentique-frontend erp-agentique-nginx; do
  docker image inspect "$IMG" >/dev/null 2>&1 || TOUT=1
done

ok=1
RIEN_CONSTRUIT=0
if [ "$TOUT" = "1" ]; then
  log "DEPLOY $SHORT — début (rebuild complet)"
  $COMPOSE build || ok=0
elif [ -n "$A_CONSTRUIRE" ]; then
  log "DEPLOY $SHORT — début (rebuild ciblé :$A_CONSTRUIRE)"
  # shellcheck disable=SC2086
  $COMPOSE build $A_CONSTRUIRE || ok=0
else
  log "DEPLOY $SHORT — début (code seul : aucune image à reconstruire)"
  RIEN_CONSTRUIT=1
fi

if [ "$ok" = "1" ]; then
  $COMPOSE up -d --remove-orphans || ok=0
fi

# ── PIÈGE DE LA CONSTRUCTION SAUTÉE — NE PAS RETIRER ────────────────────────
# Quand aucune image n'est reconstruite, aucune ne change d'identifiant, donc
# `up -d` ne recrée AUCUN conteneur (compose compare la config et l'image, pas
# le contenu d'un bind-mount). Or gunicorn tourne SANS --reload en production :
# le code fraîchement récupéré resterait dans le dossier monté sans jamais être
# chargé. Le déploiement serait RAPIDE ET INERTE — pire que lent, parce qu'il
# annonce « OK » sans rien livrer. Avant la construction sélective, la mise à
# jour était portée PAR ACCIDENT : `COPY . /app/` changeait à chaque commit,
# donc l'image changeait, donc compose recréait.
if [ "$ok" = "1" ] && [ "$RIEN_CONSTRUIT" = "1" ]; then
  $COMPOSE restart django_core celery_worker celery_worker_interactive \
                   celery_beat fastapi_ia || ok=0
fi

if [ "$ok" = "1" ]; then
  $COMPOSE exec -T django_core python manage.py migrate --noinput   || ok=0
  $COMPOSE exec -T django_core python manage.py init_roles          || ok=0
  # nginx garde l'ancienne adresse de django après recréation -> 502 sinon.
  $COMPOSE restart nginx                                            || ok=0
  # Caddyfile est un bind mount : reload explicite (zéro coupure), inoffensif sinon.
  $COMPOSE exec -T caddy caddy reload --config /etc/caddy/Caddyfile || true
  # PRÉCHAUFFAGE OBLIGATOIRE : construit les caches de polices (fontconfig) et
  # importe matplotlib/weasyprint -> évite le gel à froid du premier rendu PDF.
  $COMPOSE exec -T django_core python - <<'PYEOF' || log "AVERTISSEMENT: préchauffage en échec (app servie, mais premier PDF lent)"
import time; t0 = time.time()
import matplotlib; matplotlib.use('Agg'); import matplotlib.pyplot as plt
from weasyprint import HTML
HTML(string='<p>warmup</p>').write_pdf('/tmp/warmup.pdf')
fig, ax = plt.subplots(); ax.plot([1, 2]); fig.savefig('/tmp/warmup.png'); plt.close(fig)
print('prechauffage PDF/graphiques: %.1fs' % (time.time() - t0))
PYEOF
fi

if [ "$ok" = "1" ]; then
  echo "$NEW" > "$LAST"
  # AUTO-MISE À JOUR : la copie de référence est celle du dépôt. On l'installe
  # pour le PROCHAIN cycle — jamais en cours de route (on ne se réécrit pas
  # sous les pieds). Le déploiement manuel l'installe aussi, ce qui amorce le
  # mécanisme la première fois.
  if [ -f "$REPO/scripts/auto-deploy.sh" ] \
     && ! cmp -s "$REPO/scripts/auto-deploy.sh" "$STATE/auto-deploy.sh"; then
    cp "$REPO/scripts/auto-deploy.sh" "$STATE/auto-deploy.sh" \
      && chmod +x "$STATE/auto-deploy.sh" \
      && log "auto-deploy.sh mis à jour depuis le dépôt (actif au prochain cycle)"
  fi
  log "DEPLOY $SHORT — OK"
  exit 0
else
  log "DEPLOY $SHORT — ECHEC (commit non enregistré ; nouvelle tentative au prochain cycle)"
  exit 1
fi
