#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# WOW-CI RONDE 5 — ETIQUETTE DE L'IMAGE CI BACKEND, SOURCE UNIQUE.
#
# Appele par DEUX workflows qui doivent tomber d'accord au caractere pres :
#   - `.github/workflows/ci-image.yml`  (construit et pousse l'image)
#   - `.github/workflows/ci.yml`, job `ci-image-check` (verifie sa presence)
# Si les deux calculaient l'etiquette chacun de leur cote, la moindre
# divergence ferait reconstruire l'image a CHAQUE run — c'est exactement le
# genre de dedoublement que ce depot paie cher. D'ou ce fichier unique.
#
# L'etiquette est une empreinte de TOUT ce qui definit l'environnement :
#   - backend/django_core/requirements.txt      (deps prod)
#   - backend/django_core/requirements-dev.txt  (deps de test)
#   - .github/ci-image/Dockerfile               (liste apt + version Python +
#                                                binaires MinIO/pg_client)
# Rien d'autre ne doit y entrer : une etiquette couplee a un fichier sans
# rapport se ferait invalider pour rien (la faute exacte corrigee en ronde 4
# sur la cle du cache apt, cf. WOW-CI7).
#
# Sortie (une paire cle=valeur par ligne, prete pour $GITHUB_OUTPUT) :
#   tag=<16 hex>
#   image=ghcr.io/<owner>/<repo>/ci-backend:<16 hex>
#
# Usage : bash .github/ci-image/tag.sh <owner/repo>   (depuis la racine du depot)
# ---------------------------------------------------------------------------
set -euo pipefail

REPO="${1:-${GITHUB_REPOSITORY:-}}"
if [ -z "$REPO" ]; then
  echo "tag.sh : depot manquant (argument 1 ou GITHUB_REPOSITORY)." >&2
  exit 1
fi
# GHCR n'accepte que des minuscules dans le chemin du depot ; `Taqinor/taqinor-os`
# doit donc devenir `taqinor/taqinor-os`.
REPO_LC="$(printf '%s' "$REPO" | tr '[:upper:]' '[:lower:]')"

FILES=(
  backend/django_core/requirements.txt
  backend/django_core/requirements-dev.txt
  .github/ci-image/Dockerfile
)
for f in "${FILES[@]}"; do
  # Echec BRUYANT si un fichier manque : une empreinte calculee sur un fichier
  # absent serait stable et FAUSSE — l'image ne serait jamais reconstruite.
  test -f "$f" || { echo "tag.sh : fichier introuvable — $f" >&2; exit 1; }
done

# `sha256sum` sur la liste ORDONNEE ci-dessus (jamais un glob : l'ordre doit
# etre le meme partout), puis une empreinte de ces empreintes. On tronque a
# 16 caracteres hexadecimaux — 64 bits, largement assez pour un tag d'image.
TAG="$(sha256sum "${FILES[@]}" | sha256sum | cut -c1-16)"

echo "tag=${TAG}"
echo "image=ghcr.io/${REPO_LC}/ci-backend:${TAG}"
