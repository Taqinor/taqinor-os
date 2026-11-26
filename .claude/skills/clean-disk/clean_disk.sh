#!/usr/bin/env bash
# « clean the disk » — supprime ce que les sessions Claude laissent sur ce poste.
#
# Usage (Git Bash, depuis n'importe quel dossier du dépôt) :
#   bash .claude/skills/clean-disk/clean_disk.sh          # nettoie
#   bash .claude/skills/clean-disk/clean_disk.sh dry      # montre sans rien supprimer
#
# Sûr par construction : rien de verrouillé, rien qui porte du travail non
# enregistré, rien d'actif récemment, jamais l'arbre de travail courant, jamais
# l'historique des conversations, jamais le dossier de données de l'application.
# Seuils réglables par variables d'environnement (heures) :
#   AGE_AGENT_H=3   arbre d'agent inactif depuis au moins N heures
#   AGE_NM_H=72     node_modules d'une session inactive depuis au moins N heures
#   AGE_TEMP_H=24   dossiers temporaires inactifs depuis au moins N heures
set -u
MODE="${1:-run}"
AGE_AGENT_H="${AGE_AGENT_H:-3}"
AGE_NM_H="${AGE_NM_H:-72}"
AGE_TEMP_H="${AGE_TEMP_H:-24}"
NOW=$(date +%s)
TEMP_WIN="${LOCALAPPDATA:-$HOME/AppData/Local}"
TEMP_WIN=$(cygpath -u "$TEMP_WIN" 2>/dev/null || echo "$TEMP_WIN")

dire() { printf '%s\n' "$*"; }
libre() { df -h /c 2>/dev/null | tail -1 | awk '{print $4}'; }
suppr() {                      # suppr <chemin> — supprime, ou annonce en mode dry
  if [ "$MODE" = dry ]; then dire "   (à blanc) $1"; else rm -rf -- "$1" 2>/dev/null; fi
}
casser_jonctions() {           # casser_jonctions <dossier> — retire les jonctions (node_modules partagés
  # des lanes) SANS suivre leur cible. Mesuré sur le portable (20/09 et 02/11/2026) : `git worktree
  # remove` et `rm -rf` suppriment À TRAVERS une jonction et vident le vrai node_modules d'une autre
  # session. `cmd rmdir` sans /s ne retire que le lien. Renvoie 1 s'il en reste une.
  local j reste=0
  while IFS= read -r j; do
    [ -n "$j" ] || continue
    if [ "$MODE" = dry ]; then dire "   (à blanc) jonction $j"
    else cmd //c rmdir "$(cygpath -w "$j")" >/dev/null 2>&1; [ -L "$j" ] && reste=1
    fi
  done <<EOF_J
$(find "$1" -maxdepth 3 -type l 2>/dev/null)
EOF_J
  return $reste
}
age_h() {                      # âge en heures du fichier le plus récent d'un dossier (2 niveaux)
  local m
  m=$(find "$1" -maxdepth 2 -printf '%T@\n' 2>/dev/null | sort -n | tail -1 | cut -d. -f1)
  echo $(( (NOW - ${m:-0}) / 3600 ))
}

dire "== clean the disk ($MODE) — libre au départ : $(libre)"

# ── 1. Arbres de travail du dépôt ────────────────────────────────────────────
COMMUN=$(git rev-parse --path-format=absolute --git-common-dir 2>/dev/null)
if [ -n "$COMMUN" ]; then
  RACINE=$(dirname "$COMMUN")
  WT="$RACINE/.claude/worktrees"
  ICI=$(git rev-parse --show-toplevel 2>/dev/null)
  git -C "$RACINE" worktree prune 2>/dev/null
  git -C "$RACINE" worktree list --porcelain > /tmp/cd_wt.txt 2>/dev/null
  awk '/^worktree /{p=$2} /^locked/{print p}' /tmp/cd_wt.txt | sed 's#.*/##' > /tmp/cd_verrou.txt
  grep '^worktree ' /tmp/cd_wt.txt | sed 's#^worktree ##; s#.*/##' | sort > /tmp/cd_reg.txt
  if [ -d "$WT" ]; then
    # 1a. débris : entrées que git ne connaît pas et qui ne sont pas un arbre (.git absent)
    n=0
    for e in "$WT"/*; do
      nom=$(basename "$e")
      grep -qx "$nom" /tmp/cd_reg.txt && continue
      [ -e "$e/.git" ] && { dire "   laissé (arbre hors registre, à regarder) : $nom"; continue; }
      casser_jonctions "$e" || { dire "   laissé (jonction non retirée) : $nom"; continue; }
      suppr "$e"; n=$((n+1))
    done
    dire "1a. débris hors registre git : $n"
    # 1b. arbres d'agents terminés : non verrouillés, propres, inactifs
    n=0; laisses=0
    for e in "$WT"/agent-*; do
      [ -d "$e" ] || continue
      nom=$(basename "$e"); adm="$COMMUN/worktrees/$nom"
      [ "$e" = "$ICI" ] && continue
      grep -qx "$nom" /tmp/cd_verrou.txt && { laisses=$((laisses+1)); continue; }
      m=$(stat -c %Y "$adm/index" 2>/dev/null || stat -c %Y "$adm/HEAD" 2>/dev/null || echo "$NOW")
      [ $(( (NOW - m) / 3600 )) -lt "$AGE_AGENT_H" ] && { laisses=$((laisses+1)); continue; }
      etat=$(git -C "$e" status --porcelain 2>/dev/null)
      if [ -n "$etat" ]; then
        # Arbre à moitié supprimé (suppression interrompue) : rien que des
        # suppressions, par dizaines — ce n'est pas du travail, on le retire.
        autres=$(printf '%s\n' "$etat" | grep -vcE '^( D|D ) ')
        if [ "$autres" -ne 0 ] || [ "$(printf '%s\n' "$etat" | wc -l)" -lt 50 ]; then
          dire "   laissé (travail non enregistré) : $nom"; laisses=$((laisses+1)); continue
        fi
      fi
      casser_jonctions "$e" || { dire "   laissé (jonction non retirée) : $nom"; laisses=$((laisses+1)); continue; }
      if [ "$MODE" = dry ]; then dire "   (à blanc) arbre d'agent $nom"
      else
        git -C "$RACINE" worktree remove "$e" >/dev/null 2>&1 \
          || git -C "$RACINE" worktree remove --force "$e" >/dev/null 2>&1 \
          || { rm -rf -- "$e" 2>/dev/null; git -C "$RACINE" worktree prune 2>/dev/null; }
      fi
      n=$((n+1))
    done
    dire "1b. arbres d'agents supprimés : $n (branches conservées) ; laissés : $laisses"
    # 2. node_modules des sessions arrêtées depuis longtemps (se réinstallent par npm ci)
    n=0
    for nm in "$WT"/*/frontend/node_modules "$WT"/*/apps/web/node_modules; do
      [ -d "$nm" ] || continue
      arbre=${nm#"$WT"/}; arbre=${arbre%%/*}
      [ "$WT/$arbre" = "$ICI" ] && continue
      grep -qx "$arbre" /tmp/cd_verrou.txt && continue
      m=$(stat -c %Y "$COMMUN/worktrees/$arbre/index" 2>/dev/null || echo "$NOW")
      [ $(( (NOW - m) / 3600 )) -lt "$AGE_NM_H" ] && continue
      if [ -L "$nm" ]; then casser_jonctions "$(dirname "$nm")"   # une jonction : le lien seul, jamais sa cible
      else suppr "$nm"; fi
      n=$((n+1))
    done
    dire "2.  node_modules de sessions arrêtées : $n"
    [ "$MODE" = dry ] || git -C "$RACINE" worktree prune 2>/dev/null
  fi
else
  dire "1.  hors d'un dépôt git : arbres de travail non traités"
fi

# ── 3. Dossiers temporaires des sessions (Temp/claude/<projet>/<session>) ────
n=0
for p in "$TEMP_WIN"/Temp/claude/*/; do
  for s in "$p"*/; do
    [ -d "$s" ] || continue
    [ "$(age_h "$s")" -ge "$AGE_TEMP_H" ] && { suppr "$s"; n=$((n+1)); }
  done
  [ "$MODE" = dry ] || rmdir "$p" 2>/dev/null
done
dire "3.  dossiers temporaires de sessions terminées : $n"

# ── 4. Restes d'outils à la racine du dossier temporaire de Windows ──────────
# (profils de navigateur de test, dossiers pip, scripts de sonde, tmp*)
avant=$(ls -A "$TEMP_WIN/Temp" 2>/dev/null | wc -l)
if [ "$MODE" = dry ]; then
  dire "4.  (à blanc) $(find "$TEMP_WIN/Temp" -mindepth 1 -maxdepth 1 ! -name claude -mmin +$((AGE_TEMP_H*60)) 2>/dev/null | wc -l) entrées de plus de ${AGE_TEMP_H} h sur $avant"
else
  find "$TEMP_WIN/Temp" -mindepth 1 -maxdepth 1 ! -name claude -mmin +$((AGE_TEMP_H*60)) -exec rm -rf -- {} + 2>/dev/null
  dire "4.  dossier temporaire de Windows : $avant → $(ls -A "$TEMP_WIN/Temp" 2>/dev/null | wc -l) entrées"
fi

# ── 5. Caches qui se retéléchargent ──────────────────────────────────────────
if [ "$MODE" != dry ]; then
  npm cache clean --force >/dev/null 2>&1 && dire "5a. cache npm vidé"
  python -m pip cache purge >/dev/null 2>&1 && dire "5b. cache pip vidé"
fi
# 5c. navigateurs Playwright qu'aucun projet ne référence plus
PW="$TEMP_WIN/ms-playwright"
if [ -d "$PW" ] && [ -n "${RACINE:-}" ]; then
  : > /tmp/cd_pw.txt
  for f in "$RACINE"/frontend/node_modules/playwright-core/browsers.json \
           "$RACINE"/apps/web/node_modules/playwright-core/browsers.json \
           "$WT"/*/frontend/node_modules/playwright-core/browsers.json \
           "$WT"/*/apps/web/node_modules/playwright-core/browsers.json \
           "$TEMP_WIN"/npm-cache/_npx/*/node_modules/playwright-core/browsers.json; do
    [ -f "$f" ] && grep -o '"revision": *"[0-9]*"' "$f" | grep -o '[0-9]\+' >> /tmp/cd_pw.txt
  done
  if [ -s /tmp/cd_pw.txt ]; then
    n=0
    for d in "$PW"/chromium-* "$PW"/chromium_headless_shell-* "$PW"/webkit-* "$PW"/firefox-* "$PW"/ffmpeg-*; do
      [ -d "$d" ] || continue
      rev=${d##*-}
      grep -qx "$rev" /tmp/cd_pw.txt || { suppr "$d"; n=$((n+1)); }
    done
    dire "5c. versions de navigateur Playwright sans projet : $n"
  else
    dire "5c. aucune version Playwright référencée trouvée : rien supprimé"
  fi
fi

# ── 6. Docker (seulement si le démon répond) ─────────────────────────────────
if docker info >/dev/null 2>&1; then
  if [ "$MODE" = dry ]; then
    docker system df 2>/dev/null | sed 's/^/   /'
  else
    dire "6a. cache de construction : $(docker builder prune -f 2>/dev/null | tail -1)"
    dire "6b. images sans étiquette : $(docker image prune -f 2>/dev/null | tail -1)"
    dire "6c. volumes anonymes détachés : $(docker volume prune -f 2>/dev/null | tail -1)"
    # conteneurs ARRÊTÉS depuis plus de 24 h seulement (jamais ceux d'une session en cours)
    dire "6d. conteneurs arrêtés depuis 24 h : $(docker container prune -f --filter until=24h 2>/dev/null | tail -1)"
  fi
  dire "6e. conteneurs en cours (non touchés) : $(docker ps --format '{{.Names}}' | tr '\n' ' ')"
else
  dire "6.  Docker ne répond pas : rien fait de ce côté"
fi

dire "== terminé — libre à l'arrivée : $(libre)"
