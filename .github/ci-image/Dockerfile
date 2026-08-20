# ---------------------------------------------------------------------------
# WOW-CI RONDE 5 (20/08/2026) — IMAGE CI BACKEND PRE-CONSTRUITE.
#
# CE FICHIER N'EST PAS L'IMAGE DE PRODUCTION. La prod est construite par
# `backend/django_core/Dockerfile` et n'est PAS touchee par ce fichier. Celle-ci
# ne sert QU'A la CI : elle fige, une fois pour toutes, ce que chaque lane
# backend re-installait a chaque run.
#
# CE QU'ELLE SUPPRIME DU CHEMIN CRITIQUE (mesures du run 32265590843) :
#   - `apt-get install` des bibliotheques WeasyPrint ......... 12 a 100 s / lane
#   - `pip install -r requirements-dev.txt` (ou son cache) ...  0 a  43 s / lane
#   - `actions/setup-python` ................................. ~5 a  10 s / lane
#   - le `docker run` de minio/minio + minio/mc .............. 10 a  18 s / lane
# En echange, une seule chose : le PULL de cette image (~20-40 s, registre GHCR
# situe dans le meme datacentre que les runners).
#
# ELLE PORTE AUSSI LES OUTILS CLIENTS POSTGRES. Sans eux, l'action composite
# `backend-env` lance `pg_restore`/`pg_dump` via `docker run` — impossible dans
# un job `container:` (le socket docker et les chemins /tmp ne coincident plus).
# `postgresql-client-16` vient du depot PGDG parce que Debian bookworm s'arrete
# a la 15, et qu'un pg_dump 15 REFUSE de parler a un serveur 16 (le service CI
# est `pgvector/pgvector:pg16`).
#
# ELLE PORTE ENFIN LES BINAIRES MINIO. Meme raison : dans un job `container:`,
# `docker run -d minio/minio` n'est pas disponible. Le binaire natif rend le
# service local (127.0.0.1:9000) a l'identique, sans docker et sans pull.
#
# ETIQUETTE (tag) = empreinte de TOUT ce qui definit cet environnement :
# les deux fichiers de dependances + CE fichier (qui porte la liste apt ET la
# version de Python). Calcul unique et partage : `.github/ci-image/tag.sh`.
# Editer ce Dockerfile change donc l'etiquette, et le workflow `ci-image.yml`
# reconstruit l'image au prochain push sur `main`.
# ---------------------------------------------------------------------------
# Base EPINGLEE sur bookworm : le tag flottant python:3.11-slim est passe a
# Debian trixie (20/08/2026), or le depot PGDG ci-dessous installe des
# paquets construits pour bookworm (libpq5 pgdg12+ exige libldap-2.5-0,
# absent de trixie) - exit 100 au premier build reel. La base et la ligne
# bookworm-pgdg doivent TOUJOURS bouger ensemble.
FROM python:3.11-slim-bookworm

# MEME version majeure/mineure que la production (backend/django_core/Dockerfile
# et backend/fastapi_ia : python:3.11.x). Une CI en 3.12+ ne verrait pas les
# SyntaxError propres a 3.11 qui font tomber le generateur de PDF en prod.

ENV PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    # Marqueur lu par les gardes bash de `.github/actions/backend-env` (et par
    # tout futur consommateur) : « je tourne DEJA dans l'image CI, n'installe
    # rien ». Les expressions `if:` des workflows, elles, ne voient PAS l'env
    # d'une image — c'est l'entree `prebuilt-image` de l'action composite qui
    # leur sert de signal. Les deux disent la meme chose, volontairement.
    TAQINOR_CI_IMAGE=1

# --- Couche systeme --------------------------------------------------------
# 1. Les bibliotheques WeasyPrint : liste STRICTEMENT identique a l'etape
#    « Install WeasyPrint system libraries » de `.github/actions/backend-env`
#    (et a celle de `backend-openapi`). Si cette liste change la-bas, elle doit
#    changer ici — le tag suit ce fichier, l'image se reconstruit toute seule.
# 2. `git` (actions/checkout refuse de faire un vrai clone sans lui et retombe
#    sur un telechargement d'archive via l'API), `curl`/`ca-certificates`
#    (sondes de sante), `zstd` (actions/cache l'utilise, sinon il retombe en
#    gzip), `gnupg` (cle du depot PGDG), `procps`.
# 3. `postgresql-client-16` depuis PGDG (voir l'en-tete).
RUN set -eux; \
    apt-get update; \
    apt-get install -y --no-install-recommends \
        libpango-1.0-0 libpangoft2-1.0-0 libharfbuzz0b fonts-dejavu-core \
        git curl ca-certificates zstd gnupg procps; \
    install -d /usr/share/keyrings; \
    curl -fsSL https://www.postgresql.org/media/keys/ACCC4CF8.asc \
        | gpg --dearmor -o /usr/share/keyrings/pgdg.gpg; \
    echo 'deb [signed-by=/usr/share/keyrings/pgdg.gpg] http://apt.postgresql.org/pub/repos/apt bookworm-pgdg main' \
        > /etc/apt/sources.list.d/pgdg.list; \
    apt-get update; \
    apt-get install -y --no-install-recommends postgresql-client-16; \
    rm -rf /var/lib/apt/lists/*

# --- MinIO (serveur + client) ----------------------------------------------
# Memes binaires que les images `minio/minio:latest` / `minio/mc:latest`
# utilisees aujourd'hui par `backend-env` — donc AUCUN changement de
# comportement, juste plus de `docker run` a payer par lane.
RUN set -eux; \
    curl -fsSL -o /usr/local/bin/minio https://dl.min.io/server/minio/release/linux-amd64/minio; \
    curl -fsSL -o /usr/local/bin/mc https://dl.min.io/client/mc/release/linux-amd64/mc; \
    chmod +x /usr/local/bin/minio /usr/local/bin/mc; \
    minio --version; mc --version

# --- Environnement Python --------------------------------------------------
# Un venv sur le PATH (et non le site-packages systeme) : le job garde ainsi la
# possibilite d'installer quelque chose sans toucher a l'interpreteur de base.
# On installe requirements-dev.txt, qui commence par `-r requirements.txt` :
# c'est donc le SUR-ENSEMBLE, valable aussi bien pour les shards de tests que
# pour `backend-openapi` (lequel n'a besoin que du sous-ensemble prod).
# Les .pyc sont volontairement CONSERVES (pas de PYTHONDONTWRITEBYTECODE) :
# ils raccourcissent le demarrage de Django, mesure a ~21,6 s par lane.
ENV VIRTUAL_ENV=/opt/venv
ENV PATH="/opt/venv/bin:${PATH}"
RUN python -m venv "$VIRTUAL_ENV"

COPY requirements.txt requirements-dev.txt /tmp/reqs/
RUN set -eux; \
    pip install --upgrade pip; \
    pip install -r /tmp/reqs/requirements-dev.txt; \
    python -c 'import django, rest_framework, weasyprint, numpy, matplotlib; print(django.get_version())'; \
    rm -rf /tmp/reqs

WORKDIR /__w
