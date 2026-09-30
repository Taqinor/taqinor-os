# syntax=docker/dockerfile:1
# ERR-QAH-MINIO-IMAGE-INTROUVABLE — image MinIO MAISON, construite DEPUIS LES
# SOURCES (AGPLv3), décision fondateur du 29/09/2026 (voie b).
#
# Pourquoi : `minio/minio:RELEASE.2025-01-20T14-49-07Z` ne se télécharge plus
# nulle part (Docker Hub « pull access denied », quay.io 401, dl.min.io 410) —
# toute machine NEUVE échouait au `docker compose up`.
#
# Contrat de compatibilité (AUCUNE migration de volume) : même serveur (tag
# RELEASE.2025-01-20T14-49-07Z, commit 827004cd6d3d… vérifié ci-dessous), même
# disposition que l'image officielle de cette release (Dockerfile.release
# amont) : binaire `/usr/bin/minio`, point d'entrée
# `/usr/bin/docker-entrypoint.sh`, utilisateur root, données sous `/data`,
# mêmes variables d'environnement par défaut. Le volume `minio_data` existant
# est donc repris tel quel. Voir backend/minio/README.md.

ARG MINIO_RELEASE_TAG=RELEASE.2025-01-20T14-49-07Z
ARG MINIO_COMMIT=827004cd6d3da8f49a5320c94ae74ae128156ed6

# ── Construction ─────────────────────────────────────────────────────────────
FROM golang:1.23-alpine AS build
ARG MINIO_RELEASE_TAG
ARG MINIO_COMMIT
RUN apk add --no-cache git ca-certificates
WORKDIR /src
# Clone superficiel du TAG exact, puis garde : le commit doit être celui de la
# release (un tag déplacé amont ferait échouer la construction, jamais un
# binaire silencieusement différent).
RUN git clone --depth 1 --branch "${MINIO_RELEASE_TAG}" https://github.com/minio/minio.git . \
 && test "$(git rev-parse HEAD)" = "${MINIO_COMMIT}"
# Mêmes options que la cible `build` du Makefile amont. MINIO_RELEASE=RELEASE
# donne la chaîne de version officielle « RELEASE.2025-01-20T14-49-07Z »
# (gen-ldflags.go la dérive de la date du commit ; sans elle : DEVELOPMENT.*).
ENV CGO_ENABLED=0 MINIO_RELEASE=RELEASE
RUN go build -tags kqueue -trimpath \
      --ldflags "$(go run buildscripts/gen-ldflags.go)" \
      -o /out/minio \
 && /out/minio --version

# ── Image finale : miroir de Dockerfile.release amont ────────────────────────
FROM registry.access.redhat.com/ubi9/ubi-micro:9.5
ARG MINIO_RELEASE_TAG
LABEL name="MinIO (build maison TAQINOR)" \
      version="${MINIO_RELEASE_TAG}" \
      summary="MinIO construit depuis les sources, compatible avec l'image officielle ${MINIO_RELEASE_TAG}." \
      license="AGPL-3.0-or-later" \
      org.opencontainers.image.source="https://github.com/minio/minio" \
      org.opencontainers.image.version="${MINIO_RELEASE_TAG}"

ENV MINIO_ACCESS_KEY_FILE=access_key \
    MINIO_SECRET_KEY_FILE=secret_key \
    MINIO_ROOT_USER_FILE=access_key \
    MINIO_ROOT_PASSWORD_FILE=secret_key \
    MINIO_KMS_SECRET_KEY_FILE=kms_master_key \
    MINIO_UPDATE_MINISIGN_PUBKEY="RWTx5Zr1tiHQLwG9keckT0c45M3AGeHD6IvimQHpyRywVWGbP1aVSGav" \
    MINIO_CONFIG_ENV_FILE=config.env \
    MC_CONFIG_DIR=/tmp/.mc

COPY --from=build /etc/ssl/certs/ca-certificates.crt /etc/ssl/certs/
COPY --from=build /out/minio /usr/bin/minio
COPY --from=build /src/dockerscripts/docker-entrypoint.sh /usr/bin/docker-entrypoint.sh
# AGPLv3 : la licence et les crédits amont voyagent avec le binaire.
COPY --from=build /src/LICENSE /src/CREDITS /licenses/
RUN chmod -R 777 /usr/bin

EXPOSE 9000
VOLUME ["/data"]

ENTRYPOINT ["/usr/bin/docker-entrypoint.sh"]
CMD ["minio"]
