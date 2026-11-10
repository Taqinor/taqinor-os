#!/usr/bin/env bash
# ADCG96 — installe l'auto-déploiement sur un serveur (neuf ou existant), depuis
# le dépôt cloné dans /opt/taqinor-os. IDEMPOTENT : un second passage réécrit
# les mêmes fichiers et ne change rien. Procédure complète d'un serveur neuf :
# docs/production.md § « Reconstruire le serveur ».
#   sudo bash /opt/taqinor-os/scripts/serveur/installer-serveur.sh
# RACINE (vide par défaut) : racine système de remplacement, pour le banc de test.
set -euo pipefail

RACINE="${RACINE:-}"
DEPOT="$(cd "$(dirname "$0")/../.." && pwd)"
UNITES="$RACINE/etc/systemd/system"
ETAT="$RACINE/opt/autodeploy"

install -d "$UNITES" "$ETAT"
install -m 0644 "$DEPOT/scripts/serveur/taqinor-autodeploy.service" "$UNITES/taqinor-autodeploy.service"
install -m 0644 "$DEPOT/scripts/serveur/taqinor-autodeploy.timer" "$UNITES/taqinor-autodeploy.timer"
install -m 0755 "$DEPOT/scripts/auto-deploy.sh" "$ETAT/auto-deploy.sh"

systemctl daemon-reload
systemctl enable taqinor-autodeploy.timer
echo "Auto-deploiement installe : systemctl list-timers taqinor-autodeploy.timer"
