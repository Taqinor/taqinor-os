# Runbook — Sauvegarde / restauration Postgres (YOPSB1-3)

Ce document couvre la sauvegarde réelle de la base Postgres de production
(distincte du bundle manifeste FG395 par société, qui reste `core.backup`
`construire_manifeste`/`executer_sauvegarde`).

## YOPSB1 — Dump quotidien (`pg_dump` → MinIO)

- Commande : `python manage.py dump_database`
- Planifié via Celery Beat, tâche `core.dump_database`, tous les jours à
  03:00 (Africa/Casablanca).
- Format `pg_dump -Fc` (custom, compressé, restaurable avec `pg_restore`).
- Destination : bucket MinIO **`erp-backups`**, clé `pg_dumps/<horodatage>.dump`.
- Chaque exécution est journalisée en `core.BackupRun`
  (`kind=db_dump`, `company=None` — système-wide, pas une société unique) :
  `statut` (`termine`/`echec`), `bytes_taille`, `object_key`, `detail`.
- Un `pg_dump` en échec (code retour non nul, binaire absent, timeout) ou un
  échec d'upload MinIO → `BackupRun.statut=echec` **et** la commande de
  gestion sort en code non-nul (`CommandError`), pour être détectée par un
  cron/superviseur externe.

## YOPSB2 — Drill de restauration hebdomadaire

- Commande : `python manage.py restore_drill`
- Planifié via Celery Beat, tâche `core.restore_drill`, chaque lundi 04:00.
- Télécharge le dernier objet `BackupRun` `kind=db_dump` `statut=termine`
  depuis MinIO, le restaure (`pg_restore`) dans une base **JETABLE**
  (`erp_restore_drill` par défaut, configurable via
  `BACKUP_RESTORE_DRILL_DB`), compte quelques tables clés
  (`authentication_customuser`, `ventes_devis`, `crm_lead`), puis **DROP**
  la base scratch.
- Garde dure : la commande **refuse d'écrire** si la base cible calculée
  est égale à `settings.DATABASES['default']['NAME']` (jamais la prod).
- Résultat journalisé en `BackupRun` (`kind=restore_drill`, `statut`, détail
  des comptages comparés au manifeste du dump source).

## ADCG37 — Restauration RÉELLE de la production (base + rôles + fichiers)

L'exercice ci-dessus prouve qu'un dump se relit ; il ne remet RIEN en service
(`--no-owner --no-privileges`, base supprimée). Pour reprendre réellement :

1. Choisir le dump : `object_key` d'un `BackupRun` `kind=db_dump`
   `statut=termine` (ex. `pg_dumps/20261110-030000.dump`). Les fichiers métier
   de ce dump sont sous `erp-backups/fichiers/<bucket>/` (ADCG30).
2. Mettre le script des rôles dans le conteneur (il n'est pas dans l'image) :
   `docker compose cp backend/db/rls_roles.sql django:/tmp/rls_roles.sql`.
3. Restaurer dans une base **neuve** (la commande la crée, ne la supprime jamais) :
   `docker compose exec django python manage.py restaurer_sauvegarde
   --dump <object_key> --base erp_restaure --suffixe-buckets -restaure
   --roles-sql /tmp/rls_roles.sql`
   — `createdb`, rôles `app_rls` / `sql_agent_ro` rejoués (avant et après),
   `pg_restore` AVEC propriétaires et droits, fichiers recopiés vers
   `erp-uploads-restaure` / `erp-pdf-restaure`, `BackupRun` `kind=restore`
   avec comptages. Code non nul en cas d'échec.
4. Vérifier : `DB_NAME=erp_restaure python manage.py check`, puis un GET
   authentifié (ex. `/api/django/crm/leads/`) sur la base restaurée.
5. Poser les mots de passe des rôles (jamais dans le dépôt) :
   `ALTER ROLE app_rls PASSWORD '…'` et `bash backend/db/provision_sql_agent_ro.sh`.
6. Bascule (geste de Reda, jamais automatique) : pointer `DB_NAME` sur
   `erp_restaure` et `MINIO_BUCKET_UPLOADS` / `MINIO_BUCKET_PDF` sur les buckets
   `-restaure` dans `.env`, puis redémarrer la pile.

Garde : `--base` égal à la base de production est refusé (rien n'est écrit)
sans `--remplacer-production <ce nom>` ; un `--suffixe-buckets` vide (écrire
dans les buckets vivants) exige la même confirmation.

## YOPSB3 — Rétention GFS (7 jours / 4 semaines / 12 mois)

- Fonction `core.backup.purger_backups(now=None, apply_=False)`.
- Planifié via Celery Beat, tâche `core.purge_backups`, quotidien 05:00.
- Schéma Grandfather-Father-Son configurable par variables d'environnement :
  `BACKUP_RETENTION_DAILY` (défaut 7), `BACKUP_RETENTION_WEEKLY` (défaut 4),
  `BACKUP_RETENTION_MONTHLY` (défaut 12).
- **DRY-RUN par défaut** : rien n'est supprimé tant que
  `BACKUP_PURGE_AUTO_APPLY` n'est pas explicitement vrai (même convention
  que `GED_PURGE_AUTO_APPLY`, GED25).
- Une fois actif, supprime l'objet MinIO **et** soft-delete le `BackupRun`
  correspondant (jamais un hard-delete direct) pour les dumps hors schéma.

## Hors-site (règle 3-2-1) — GATÉ, étape fondateur

Le stockage MinIO de sauvegarde (bucket `erp-backups`) est sur le **même
serveur** que la base de production. La règle 3-2-1 (3 copies, 2 supports,
1 hors-site) exige une copie **hors-site** — réplication du bucket vers un
second objet-storage (OVH, Backblaze B2, S3 froid…) ou un `rsync`/`mc mirror`
périodique vers une machine distante. Cette étape nécessite un compte/des
identifiants provisionnés par le fondateur et **n'est pas automatisée par ce
plan** : le dump local automatisé (YOPSB1) est livrable dès maintenant, la
copie hors-site reste une action manuelle fondateur à planifier séparément.
