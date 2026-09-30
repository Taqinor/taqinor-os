# MinIO — image maison construite depuis les sources

Ce dossier construit l'image MinIO utilisée par le service `minio` de
`docker-compose.yml` (la prod la reprend, `docker-compose.prod.yml` ne change
que les ports et les limites).

## Pourquoi

L'image officielle `minio/minio:RELEASE.2025-01-20T14-49-07Z` ne se télécharge
plus (constaté le 28/09/2026) : Docker Hub renvoie « pull access denied »,
quay.io renvoie 401 et dl.min.io renvoie 410. Les machines qui l'avaient en cache
tournaient encore, mais toute machine neuve échouait au `docker compose up`.
Décision du fondateur (29/09/2026, voie b) : construire MinIO depuis ses sources
(licence AGPLv3) dans une image maison. Suivi : `ERR-QAH-MINIO-IMAGE-INTROUVABLE`.

## Ce qui est garanti

- **Même serveur.** Le tag `RELEASE.2025-01-20T14-49-07Z` est cloné, et la
  construction échoue si le commit n'est pas `827004cd6d3da8f49a5320c94ae74ae128156ed6`.
  `minio --version` affiche exactement la même chaîne que l'image officielle :
  `minio version RELEASE.2025-01-20T14-49-07Z (commit-id=827004cd…)`.
- **Aucune migration de volume.** L'image reprend la disposition du
  `Dockerfile.release` amont : `/usr/bin/minio`, point d'entrée
  `/usr/bin/docker-entrypoint.sh`, utilisateur root, `VOLUME /data`, et les mêmes
  variables d'environnement par défaut. La commande du compose
  (`server /data --console-address ":9001"`) et les variables
  `MINIO_ROOT_USER`/`MINIO_ROOT_PASSWORD` sont inchangées : le volume `minio_data`
  existant est repris tel quel.
- **Licence.** `LICENSE` (AGPLv3) et `CREDITS` amont sont copiés dans
  `/licenses/` de l'image. Le binaire n'est pas modifié ; le code source est
  celui du tag amont public.

## Différences avec l'image officielle

- Le client `mc` n'est **pas** inclus : aucun script du dépôt ne lance `mc` dans
  ce conteneur. La CI a ses propres binaires (`.github/ci-image/Dockerfile`).
- Go 1.23 (dernier correctif de la branche 1.23, soit la version de ce `go.mod`)
  au lieu de la chaîne d'outils utilisée par MinIO pour la version officielle.

## Construire / vérifier

```sh
docker compose build minio
docker compose run --rm --entrypoint minio minio --version
```

La construction prend environ 4 minutes : la compilation Go seule en prend à peu
près 3 à 4 sur un poste de développement. Elle n'a lieu que lorsque l'image
manque ou que ce dossier change. Sur le serveur, le premier déploiement qui
modifie `docker-compose.yml` reconstruit tout (règle de `deploy-prod.ps1`),
**y compris cette image** : il faut prévoir quelques minutes de plus et environ
2 Go de mémoire pour la compilation, une seule fois.

## Changer de version

Mettez à jour ensemble `MINIO_RELEASE_TAG` et `MINIO_COMMIT` dans le
`Dockerfile`. Le commit s'obtient avec
`git ls-remote https://github.com/minio/minio "refs/tags/<TAG>^{}"`. Avant de
passer à une autre release, vérifiez dans les notes de version amont qu'elle est
compatible avec le format des données de `minio_data`.
