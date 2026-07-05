"""YOPSB1 — Sauvegarde Postgres réelle, planifiée et hors-serveur.

Lance un ``pg_dump`` (format custom -Fc) de toute l'instance vers un objet
MinIO daté (bucket ``erp-backups``) et journalise l'exécution en
``core.BackupRun`` (kind=db_dump, company=None — système-wide, pas une
société unique).

Sort en code NON NUL si le run finit en échec (``pg_dump`` a échoué ou
l'upload MinIO a échoué), pour que le cron/beat/déploiement puisse détecter
l'échec.

Exemple :
    python manage.py dump_database
"""
from django.core.management.base import BaseCommand, CommandError

from core import backup
from core.models import BackupRun


class Command(BaseCommand):
    help = ('Lance un pg_dump réel de toute la base vers MinIO '
            '(bucket erp-backups) et journalise le résultat en BackupRun.')

    def handle(self, *args, **options):
        run = BackupRun.objects.create(
            kind=BackupRun.KIND_DB_DUMP,
            mode=BackupRun.MODE_MANUEL,
            company=None,
        )
        run = backup.dump_database(run)

        if run.statut != BackupRun.STATUT_TERMINE:
            message = (run.detail or {}).get('message', 'échec inconnu')
            raise CommandError(
                f'dump_database: échec (BackupRun #{run.pk}): {message}')

        self.stdout.write(self.style.SUCCESS(
            f'dump_database: OK — BackupRun #{run.pk}, '
            f'{run.bytes_taille} octets, objet {run.object_key}'))
