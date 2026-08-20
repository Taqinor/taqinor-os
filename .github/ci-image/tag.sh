#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# WOW-CI RONDE 5 — ETIQUETTES DES IMAGES CI, SOURCE UNIQUE.
#
# Appele par DEUX workflows qui doivent tomber d'accord au caractere pres :
#   - `.github/workflows/ci-image.yml`  (construit et pousse les images)
#   - `.github/workflows/ci.yml`, job `ci-image-check` (verifie leur presence)
# Si les deux calculaient les etiquettes chacun de leur cote, la moindre
# divergence ferait reconstruire les images a CHAQUE run — c'est exactement le
# genre de dedoublement que ce depot paie cher. D'ou ce fichier unique.
#
# DEUX IMAGES, DEUX ETIQUETTES :
#   - `ci-backend` — les lanes backend (tests shardes, rls, openapi). Empreinte
#     de ce qui definit l'environnement Python : les deux requirements + le
#     Dockerfile (qui porte la liste apt et la version de Python).
#   - `ci-e2e` — la lane e2e. CONSTRUITE PAR-DESSUS `ci-backend`, elle ajoute
#     les navigateurs Playwright et leurs dependances systeme. Son empreinte
#     porte donc l'etiquette backend (si la base bouge, elle bouge) PLUS
#     `frontend/package-lock.json` (qui fixe la version de Playwright, donc la
#     version des binaires de navigateur) et son propre Dockerfile.
#
# Rien d'autre ne doit y entrer : une etiquette couplee a un fichier sans
# rapport se ferait invalider pour rien (la faute exacte corrigee en ronde 4
# sur la cle du cache apt, cf. WOW-CI7).
#
# Sortie (une paire cle=valeur par ligne, prete pour $GITHUB_OUTPUT) :
#   tag=<16 hex>
#   image=ghcr.io/<owner>/<repo>/ci-backend:<16 hex>
#   tag_e2e=<16 hex>
#   image_e2e=ghcr.io/<owner>/<repo>/ci-e2e:<16 hex>
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

exiger() {
  # Echec BRUYANT si un fichier manque : une empreinte calculee sur un fichier
  # absent serait stable et FAUSSE — l'image ne serait jamais reconstruite.
  for f in "$@"; do
    test -f "$f" || { echo "tag.sh : fichier introuvable — $f" >&2; exit 1; }
  done
}

FICHIERS_BACKEND=(
  backend/django_core/requirements.txt
  backend/django_core/requirements-dev.txt
  .github/ci-image/Dockerfile
)
FICHIERS_E2E=(
  frontend/package-lock.json
  .github/ci-image/Dockerfile.e2e
)
exiger "${FICHIERS_BACKEND[@]}" "${FICHIERS_E2E[@]}"

# `sha256sum` sur la liste ORDONNEE ci-dessus (jamais un glob : l'ordre doit
# etre le meme partout), puis une empreinte de ces empreintes. On tronque a
# 16 caracteres hexadecimaux — 64 bits, largement assez pour un tag d'image.
TAG="$(sha256sum "${FICHIERS_BACKEND[@]}" | sha256sum | cut -c1-16)"

# L'etiquette e2e DERIVE de l'etiquette backend : `ci-e2e` etant construite
# `FROM ci-backend:<TAG>`, tout changement de la base doit la faire bouger.
TAG_E2E="$( { echo "$TAG"; sha256sum "${FICHIERS_E2E[@]}"; } | sha256sum | cut -c1-16)"

echo "tag=${TAG}"
echo "image=ghcr.io/${REPO_LC}/ci-backend:${TAG}"
echo "tag_e2e=${TAG_E2E}"
echo "image_e2e=ghcr.io/${REPO_LC}/ci-e2e:${TAG_E2E}"
