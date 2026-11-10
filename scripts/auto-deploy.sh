#!/usr/bin/env bash
# Auto-déploiement Taqinor OS — LA SEULE SÉQUENCE DE DEPLOY, VERSIONNÉE ICI.
#
# ── Pourquoi ce fichier est dans le dépôt (04/08/2026) ──────────────────────
# Il vivait UNIQUEMENT sur le serveur (`/opt/autodeploy/auto-deploy.sh`, créé le
# 16/06). Il n'était donc ni relu, ni sauvegardé, ni versionné — alors qu'il
# pilote la production à chaque fusion. Si le serveur tombait, il était perdu.
#
# ── UNE séquence, deux déclencheurs (ADCG1, 10/11/2026) ─────────────────────
# Le timer systemd `taqinor-autodeploy` le lance ~chaque minute ; le deploy
# MANUEL (`scripts/deploy-prod.ps1`) n'embarque plus sa propre copie : il
# installe CE script depuis `origin/main` dans /opt/autodeploy/ puis lance
# `systemctl start taqinor-autodeploy.service`. Avant, deux copies divergeaient
# (le manuel ne redémarrait pas django quand seul le frontend était reconstruit ;
# l'auto sautait six étapes du manuel). Toute étape du deploy vit ICI.
#
# ── Ce qu'il fait ───────────────────────────────────────────────────────────
# Ne déploie QUE si main a bougé depuis le dernier déploiement. Verrou flock
# (jamais deux déploiements simultanés), journal horodaté (une ligne par
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
# Mesuré le 04/08 : deux deploys simultanés -> le dernier arrivé réécrit
# l'étiquette avec son image, même s'il porte du code plus vieux.
exec 9>"$LOCK"
flock -n 9 || exit 0

cd "$REPO" || { log "ERREUR: dépôt $REPO introuvable"; exit 1; }

git fetch origin main --quiet || { log "ERREUR: git fetch a échoué"; exit 1; }
NEW=$(git rev-parse origin/main)
OLD=$(cat "$LAST" 2>/dev/null || echo "")

# Rien de neuf -> sortie silencieuse (pas de bruit dans le journal).
[ "$NEW" = "$OLD" ] && exit 0
# ADCG3 — un commit déjà en ÉCHEC n'est pas rejoué à chaque minute (reset, build,
# redémarrages, migrate sans fin) : seul un nouveau commit ou le deploy manuel
# (qui efface cet état) le relance.
ECHEC_COMMIT="$STATE/commit_en_echec"
[ "$NEW" = "$(cat "$ECHEC_COMMIT" 2>/dev/null)" ] && exit 0

SHORT=$(git rev-parse --short "$NEW")

# -ZeroDowntime du deploy manuel (NTPLT57, opt-in) : drapeau lu puis effacé.
ZERO_DOWNTIME=0
if [ -f "$STATE/zero_downtime" ]; then
  ZERO_DOWNTIME=1
  rm -f "$STATE/zero_downtime"
fi

# Changement purement docs/markdown ? (*.md / *.markdown, ou sous docs/ HORS
# docs/meryem/) -> on rafraîchit l'arbre de travail mais on saute
# rebuild/migration/restart/préchauffage. ADCG7 : `.txt` n'est PAS de la doc
# (requirements*.txt reconstruit une image) et docs/meryem/** est publié dans la
# GED par publier_documents_meryem : tous deux exigent un deploy complet.
DOCS_ONLY=0
CHANGES=""
if [ -n "$OLD" ] && git cat-file -e "${OLD}^{commit}" 2>/dev/null; then
  CHANGES=$(git diff --name-only "$OLD" "$NEW" || echo "")
  NONDOC=$( { echo "$CHANGES" | grep -vE '(\.(md|markdown)$)|(^docs/)'; \
              echo "$CHANGES" | grep -E '^docs/meryem/'; } || true)
  [ -z "$NONDOC" ] && DOCS_ONLY=1
fi

git reset --hard "$NEW" || { log "ERREUR: git reset --hard $SHORT a échoué"; exit 1; }

if [ "$DOCS_ONLY" = "1" ]; then
  log "DEPLOY $SHORT — docs/markdown uniquement : rebuild ignoré"
  echo "$NEW" > "$LAST"
  rm -f "$ECHEC_COMMIT"
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
# Le code BACKEND a-t-il bougé ? Monté en bind, seul un restart le charge
# (cf. piège n° 2 plus bas). Diff impossible -> on suppose que oui.
BACKEND_TOUCHE=0
if [ -z "$CHANGES" ] || echo "$CHANGES" | grep -qE '^backend/'; then
  BACKEND_TOUCHE=1
fi
if [ -z "$CHANGES" ]; then
  TOUT=1   # commit précédent inconnu ou diff impossible : on ne parie pas.
else
  if echo "$CHANGES" | grep -qE '^backend/django_core/(Dockerfile|requirements.*\.txt)$'; then
    A_CONSTRUIRE="$A_CONSTRUIRE django_core"
  fi
  if echo "$CHANGES" | grep -qE '^backend/fastapi_ia/(Dockerfile|requirements.*\.txt)$'; then
    A_CONSTRUIRE="$A_CONSTRUIRE fastapi_ia"
  fi
  # ADCG10 : apps/web/worker/ est copié par frontend/Dockerfile.prod.
  if echo "$CHANGES" | grep -qE '^(frontend/|apps/web/src/|apps/web/worker/|package(-lock)?\.json)'; then
    A_CONSTRUIRE="$A_CONSTRUIRE frontend"
  fi
  if echo "$CHANGES" | grep -qE '^backend/minio/'; then   # ADCG10 : build: ./backend/minio
    A_CONSTRUIRE="$A_CONSTRUIRE minio"
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

# Avant construction : seulement les images dangling (sans effet sur le cache
# de build, borné après le build — incident « no space left » du 2026-07-10).
echo "Espace disque avant build :"; df -h / | tail -1
docker image prune -f || true
# FILET « container name already in use » (incident 02/08/2026) : un conteneur
# lent à s'arrêter a déjà été RENOMMÉ <hash>_<nom> par compose ; s'il survit, la
# recréation échoue. On retire ces survivants renommés — jamais un conteneur sain.
ORPHELINS=$(docker ps -a --format '{{.Names}}' | grep -E '^[0-9a-f]{12}_erp-agentique-' || true)
if [ -n "$ORPHELINS" ]; then
  echo "Conteneurs renommés par un arrêt raté, on les retire : $ORPHELINS"
  echo "$ORPHELINS" | xargs -r docker rm -f || true
fi

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

# GARDE DB (incident 2026-07-10) : un fichier bind-monté (postgresql.conf) qui
# change ne recrée pas db ; si la base ne répond pas, on redémarre db (relit la
# conf montée) et on ré-attend. `-h db` teste le LISTENER TCP (la socket locale
# répond même quand Postgres n'écoute que sur localhost).
wait_db() {
  for _ in $(seq 1 30); do
    $COMPOSE exec -T db pg_isready -h db -q 2>/dev/null && return 0
    sleep 3
  done
  return 1
}
if [ "$ok" = "1" ] && ! wait_db; then
  log "AVERTISSEMENT: db injoignable après 90 s -> restart db"
  $COMPOSE restart db || ok=0
  [ "$ok" = "1" ] && { wait_db || ok=0; }
fi

# ADCG2 — `migrate` AVANT tout redémarrage ou recréation : l'image juste
# construite (`run --rm --no-deps`, code monté) migre la base PUIS le code neuf
# est servi (docs/online-migrations.md). Un migrate en échec ne redémarre rien.
# ADCG93 — des migrations en attente ? Dump (core/backup.py, `dump_database`)
# AVANT de migrer ; un dump en échec = pas de migrate. Un seul dump par commit
# (marqueur) : un migrate qui échoue puis est retenté ne remplit pas le disque.
if [ "$ok" = "1" ] \
   && ! $COMPOSE run --rm --no-deps django_core python manage.py migrate --check >/dev/null 2>&1 \
   && [ "$(cat "$STATE/dump_avant_migrate" 2>/dev/null)" != "$NEW" ]; then
  if $COMPOSE exec -T django_core python manage.py dump_database; then
    echo "$NEW" > "$STATE/dump_avant_migrate"
  else
    log "AVERTISSEMENT: dump avant migrate en échec -> migrate non lancé"; ok=0
  fi
fi
if [ "$ok" = "1" ]; then
  $COMPOSE run --rm --no-deps django_core python manage.py migrate --noinput || ok=0
fi

# ADCG19 — le commit servi rejoint l'environnement des services Django
# (core/health.py::sha_deploye -> health/ready `dernier_demarrage.sha`). La
# valeur change à chaque commit : `up -d` recrée ces quatre services (le restart
# RESTART_BACKEND plus bas devient redondant, gardé).
export DEPLOYED_SHA="$NEW"
if [ "$ok" = "1" ]; then
  $COMPOSE up -d --remove-orphans || ok=0
fi

# ADCG10 — backend/db/postgresql.conf est MONTÉ et lu au seul démarrage : on le
# recharge (pg_reload_conf) ; un réglage qui exige un redémarrage est SIGNALÉ,
# jamais appliqué par un redémarrage automatique de db.
if [ "$ok" = "1" ] && echo "$CHANGES" | grep -qE '^backend/db/postgresql\.conf$'; then
  psql_db() { $COMPOSE exec -T db sh -c "psql -U \"\$POSTGRES_USER\" -d \"\$POSTGRES_DB\" -tAc \"$1\""; }
  psql_db "SELECT pg_reload_conf()" || ok=0
  if [ "$(psql_db "SELECT count(*) FROM pg_settings WHERE pending_restart" | tr -d '[:space:]')" != "0" ]; then
    log "AVERTISSEMENT : postgresql.conf exige un redémarrage de db"
  fi
fi

# ── PIÈGE DE LA CONSTRUCTION SAUTÉE — NE PAS RETIRER ────────────────────────
# Quand aucune image n'est reconstruite, aucune ne change d'identifiant, donc
# `up -d` ne recrée AUCUN conteneur (compose compare la config et l'image, pas
# le contenu d'un bind-mount). Or gunicorn tourne SANS --reload en production :
# le code fraîchement récupéré resterait dans le dossier monté sans jamais être
# chargé. Le déploiement serait RAPIDE ET INERTE — pire que lent, parce qu'il
# annonce « OK » sans rien livrer.
# ── PIÈGE N° 2 — LA CONSTRUCTION CIBLÉE QUI SAUTE LE BACKEND (07/09/2026) ──
# Quand SEUL le frontend est reconstruit alors que du code backend a bougé
# (le cas ordinaire d'un lot complet : écran + API), l'image Django n'a pas
# changé, `up -d` ne recrée pas django_core : gunicorn servait l'ANCIEN code
# (route neuve en 404) sous un « DEPLOY — OK » (fusion 2873e029). Le backend
# est donc redémarré dès que son code a bougé SANS que son image ait été
# reconstruite — une image reconstruite est, elle, recréée par `up -d`.
RESTART_BACKEND=0
if [ "$RIEN_CONSTRUIT" = "1" ]; then
  RESTART_BACKEND=1
elif [ "$TOUT" != "1" ] && [ "$BACKEND_TOUCHE" = "1" ] \
     && ! echo " $A_CONSTRUIRE " | grep -q ' django_core '; then
  RESTART_BACKEND=1
fi
if [ "$ok" = "1" ] && [ "$RESTART_BACKEND" = "1" ]; then
  $COMPOSE restart django_core celery_worker celery_worker_interactive \
                   celery_beat fastapi_ia || ok=0
fi

if [ "$ok" = "1" ]; then
  # AANA64 — rôle Postgres lecture seule de l'agent SQL (idempotent, mot de passe
  # lu du .env serveur). Non bloquant : sans lui, l'agent SQL est désactivé.
  COMPOSE_CMD="$COMPOSE" bash backend/db/provision_sql_agent_ro.sh \
    || log "AVERTISSEMENT: provisionnement sql_agent_ro en échec"
  # WOW26 — TOUTES les migrations appliquées (un up -d partiel laissait des
  # migrations en attente + un 502 silencieux).
  # ADCG4 : un showmigrations en échec est un échec (jamais compté « 0 en attente »).
  PLAN_MIG=$($COMPOSE exec -T django_core python manage.py showmigrations --plan 2>/dev/null) \
    || { log "AVERTISSEMENT: showmigrations en échec"; ok=0; }
  UNAPPLIED=$(printf '%s\n' "$PLAN_MIG" | grep -c '\[ \]' || true)
  if [ "$UNAPPLIED" != "0" ]; then
    log "AVERTISSEMENT: migrations non appliquées restantes : $UNAPPLIED"
    ok=0
  fi
fi
if [ "$ok" = "1" ]; then
  $COMPOSE exec -T django_core python manage.py init_roles          || ok=0
  # Publie (versionné) le Guide de Meryem/Protocole de rappel/Carte one-page
  # dans la GED — best-effort : docs/meryem/ absent ou inchangé ne doit jamais
  # faire échouer un déploiement.
  $COMPOSE exec -T django_core python manage.py publier_documents_meryem || true
  # PVOND (18/08/2026) — ré-applique les fiches catalogue (strictement additif :
  # ne touche jamais un prix ni une quantité). Non bloquant.
  $COMPOSE exec -T django_core python manage.py seed_catalogue \
      --company-slug "${SEED_COMPANY_SLUG:-taqinor-demo}" \
    || log "AVERTISSEMENT: seed_catalogue en échec (fiches catalogue non rafraîchies)"
  # nginx garde l'ancienne adresse de django après recréation -> 502 sinon.
  $COMPOSE restart nginx                                            || ok=0
  # Caddyfile est un bind mount : reload explicite (zéro coupure), inoffensif sinon.
  # ADCG8 — validée AVANT le reload ; un refus (validation ou reload) est un ÉCHEC.
  if $COMPOSE exec -T caddy caddy validate --config /etc/caddy/Caddyfile --adapter caddyfile; then
    $COMPOSE exec -T caddy caddy reload --config /etc/caddy/Caddyfile || ok=0
  else
    log "AVERTISSEMENT: Caddyfile invalide (caddy validate)"; ok=0
  fi
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

# ── CONTRÔLE DE SANTÉ (ADCG4) — rouge quand il ne s'exécute pas ─────────────
# 1. Sonde interne (core/health.py) : sortie ∈ {ok, degraded}, sinon ÉCHEC (un
#    `exec` en échec rendait une chaîne vide, prise pour un succès).
# 2. Le CHEMIN SERVI : `health/ready` à travers Caddy (--resolve sur 127.0.0.1),
#    200 exigé en ≤ 5 essais à 6 s (503 si db down ou beat arrêté ; le seuil beat
#    BEAT_HEARTBEAT_STALE_SECONDS = 15 min dépasse la durée d'un redémarrage).
sante_interne() {
  $COMPOSE exec -T django_core python -c "import django, os; os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'erp_agentique.settings.prod'); django.setup(); from core import health; print(health.overall_status(health.check_services()))" 2>/dev/null | tail -n 1 | tr -d '\r'
}
URL_SANTE="${URL_SANTE:-https://api.taqinor.ma/api/django/core/health/ready/}"
HOTE_SANTE=${URL_SANTE#https://}; HOTE_SANTE=${HOTE_SANTE%%/*}
if [ "$ok" = "1" ]; then
  STATUT=$(sante_interne)
  case "$STATUT" in
    ok|degraded) ;;
    *) log "AVERTISSEMENT: sonde de santé interne « ${STATUT:-vide} »"; ok=0 ;;
  esac
fi
if [ "$ok" = "1" ]; then
  CODE_HTTP=""
  for _ in 1 2 3 4 5; do
    CODE_HTTP=$(curl -sS -o /dev/null -w '%{http_code}' --resolve "$HOTE_SANTE:443:127.0.0.1" \
                "$URL_SANTE" 2>/dev/null || true)
    [ "$CODE_HTTP" = "200" ] && break
    sleep "${PAUSE_SANTE:-6}"
  done
  [ "$CODE_HTTP" = "200" ] || { log "AVERTISSEMENT: health/ready HTTP ${CODE_HTTP:-aucune réponse}"; ok=0; }
fi

# NTPLT57 — bascule SANS coupure (opt-in, drapeau du deploy manuel) : scale à 2
# (l'ancien sert toujours), attente de la santé du neuf, recharge nginx, retour à
# 1. Le neuf non sain -> redescente à 1, ECHEC (l'ancien n'a jamais cessé de servir).
if [ "$ok" = "1" ] && [ "$ZERO_DOWNTIME" = "1" ]; then
  $COMPOSE up -d --no-deps --no-recreate --scale django_core=2 django_core || ok=0
  ZD_OK=0
  for _ in $(seq 1 30); do
    ZD_STATUS=$(sante_interne)
    if [ -n "$ZD_STATUS" ] && [ "$ZD_STATUS" != "down" ]; then ZD_OK=1; break; fi
    sleep 3
  done
  [ "$ZD_OK" = "1" ] && $COMPOSE restart nginx
  $COMPOSE up -d --no-deps --scale django_core=1 django_core || ok=0
  $COMPOSE restart nginx || ok=0
  [ "$ZD_OK" = "1" ] || { log "AVERTISSEMENT: bascule sans coupure annulée (nouveau conteneur non sain)"; ok=0; }
fi

if [ "$ok" = "1" ]; then
  echo "$NEW" > "$LAST"
  rm -f "$ECHEC_COMMIT"
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
  # NETTOYAGE POST-BUILD (succès seulement) : cache de build BORNÉ à 8 Go — les
  # couches du build qui vient de tourner survivent, le vieux cache part.
  docker image prune -f || true
  docker builder prune -f --keep-storage=8g || true
  log "DEPLOY $SHORT — OK"
  exit 0
else
  echo "$NEW" > "$ECHEC_COMMIT"
  log "DEPLOY $SHORT — ECHEC (commit non enregistré ; retenté au prochain commit ou par deploy-prod.ps1)"
  # ADCG5 — RETOUR ARRIÈRE EFFECTIF vers le dernier commit sain (le contenu de
  # last_deployed_commit, jamais `git rev-parse HEAD` déjà avancé) : code, mêmes
  # images reconstruites, conteneurs, redémarrage backend + nginx. Le SCHÉMA n'est
  # jamais rétrogradé (expand/contract, docs/online-migrations.md::BASCULE).
  if [ -n "$OLD" ] && git cat-file -e "${OLD}^{commit}" 2>/dev/null; then
    rb=1
    export DEPLOYED_SHA="$OLD"
    git reset --hard "$OLD" || rb=0
    if [ "$TOUT" = "1" ]; then
      $COMPOSE build || rb=0
    elif [ -n "$A_CONSTRUIRE" ]; then
      # shellcheck disable=SC2086
      $COMPOSE build $A_CONSTRUIRE || rb=0
    fi
    $COMPOSE up -d --remove-orphans || rb=0
    $COMPOSE restart django_core celery_worker celery_worker_interactive \
                     celery_beat fastapi_ia nginx || rb=0
    if [ "$rb" = "1" ]; then
      log "ROLLBACK vers $(git rev-parse --short "$OLD") effectué"
    else
      log "ROLLBACK vers $(git rev-parse --short "$OLD") EN ÉCHEC — intervention manuelle"
    fi
  else
    log "ECHEC sans retour arrière (aucun commit sain)"
  fi
  exit 1
fi
