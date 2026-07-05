"""YOPSB2 — Drill de restauration testé + vérification d'intégrité des dumps.

Télécharge le dernier objet ``BackupRun`` (kind=db_dump, statut=termine)
depuis MinIO (YOPSB1), le restaure dans une base JETABLE (``pg_restore``,
jamais la production — garde dure sur le nom de base), compte des tables
clés et consigne le résultat en ``BackupRun`` (kind=restore_drill).

Sort en code NON NUL si le drill échoue.

Exemple :
    python manage.py restore_drill
"""
from django.core.management.base import BaseCommand, CommandError

from core import backup
from core.models import BackupRun


class Command(BaseCommand):
    help = ('Restaure le dernier dump réussi dans une base scratch et '
            'vérifie des comptages de tables clés (jamais la production).')

    def handle(self, *args, **options):
        run = BackupRun.objects.create(
            kind=BackupRun.KIND_RESTORE_DRILL,
            mode=BackupRun.MODE_MANUEL,
            company=None,
        )
        run = backup.restore_drill(run)

        if run.statut != BackupRun.STATUT_TERMINE:
            message = (run.detail or {}).get('message', 'échec inconnu')
            raise CommandError(
                f'restore_drill: échec (BackupRun #{run.pk}): {message}')

        comptages = (run.detail or {}).get('comptages', {})
        self.stdout.write(self.style.SUCCESS(
            f'restore_drill: OK — BackupRun #{run.pk}, comptages={comptages}'))
