---
name: prod-sans-sauvegarde
description: INCIDENT OUVERT 08/10/2026 — aucune sauvegarde de la base de prod n'a jamais réussi (pg_dump absent de l'image django)
metadata:
  type: project
---

**Constat (lecture seule de la prod, 08/10/2026, audit X5).** `core.BackupRun` en prod : **105 exécutions, 105 en échec, 0 réussite**
(première = id 1, dernière = id 105 le 08/10/2026 à 03:00 UTC), message `pg_dump: exception: [Errno 2] No such file or directory: 'pg_dump'`.
`command -v pg_dump` dans `erp-agentique-django_core-1` → absent (rc 127) ; présent dans `erp-agentique-db-1` (`/usr/bin/pg_dump`).
Aucun autre mécanisme de sauvegarde de la base sur l'hôte (cron.d, cron.daily, timers systemd : rien hors `dpkg-db-backup`). Seul
dump trouvé : `/root/taqinor_dump.sql` du 12/06/2026 (manuel). Les exercices de restauration planifiés échouent pour la même raison.

**Why:** une perte du volume Postgres aujourd'hui = perte de toutes les données saisies depuis juin.

**How to apply:** tâche `ADEP1` (P0, `docs/plans/PLAN_AUDIT_DEPLOY.md`) : client PostgreSQL 16 dans l'image de prod + garde
binaire. En attendant, la mesure conservatoire (dump manuel depuis le conteneur `db`, copie hors serveur) est un geste du fondateur —
Claude ne touche pas la prod (règle Deploys + accord de lecture seule `prod-read-access.md`). Clore ce fichier quand une
`BackupRun` réussie existe en prod. Lié : [[prod-read-access]].
