---
name: prod-sans-sauvegarde
description: INCIDENT CLOS le 10/11/2026 — la base de prod est sauvegardée chaque nuit depuis le 09/10 ; restent ouverts : aucune copie hors serveur, fichiers jamais sauvegardés
metadata:
  type: project
---

**Incident du 08/10/2026 (audit X5) : clos.** `core.BackupRun` comptait 105 exécutions en échec (`pg_dump` absent de l'image).
Corrigé par `ADEP1` (client PostgreSQL 16 dans l'image). Lecture seule de la prod le 10/11/2026 (audit PF3) : **38 réussites**
(33 dumps, 5 exercices de restauration), une par nuit depuis le 09/10, la dernière le 10/11 à 03:00 (26 Mo, 6 à 10 s) ; dernier
exercice de restauration : 1 640 lignes restaurées pour 1 640 en base.

**Ce qui reste ouvert (audit PF3, groupe ADCG, `docs/audits/2026-11-10-parcours-PF3.md`).**
- **Aucune copie hors du serveur** : les dumps sont rangés dans MinIO sur le même disque que la base ; la copie distante est
  « off » (aucune variable `BACKUP_OFFSITE_*` dans le `.env` de prod). Décision `D-ADCG-1` ouverte : où envoyer la copie.
- **Les fichiers ne sont pas sauvegardés** : pièces et PDF (271 Mo le 10/11) n'ont aucune copie.
- Non vérifié : l'option « Backups » de l'hébergeur (image entière du serveur) ; si elle est active, elle couvre les deux points.

**Why:** une perte du serveur aujourd'hui = perte de la base ET de ses sauvegardes ; une perte du volume de fichiers = perte de
tous les documents.

**How to apply:** ne plus traiter les sauvegardes comme « en échec » ; les tâches ADCG de sauvegarde sont P0 ; poser les variables
de copie distante reste un geste du fondateur (Claude ne touche pas la prod). Lié : [[prod-read-access]].
