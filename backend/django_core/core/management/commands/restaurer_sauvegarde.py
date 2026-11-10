"""ADCG37 — Restauration RÉELLE d'un dump nommé (base + rôles + fichiers).

À l'inverse de ``restore_drill`` (base jetable, ``--no-owner
--no-privileges``, supprimée ensuite), restaure le dump ``--dump`` dans une
base CIBLE NEUVE et la CONSERVE : propriétaires et droits restaurés, rôles
``app_rls`` / ``sql_agent_ro`` rejoués depuis ``backend/db/rls_roles.sql``
(avant et après ``pg_restore``), fichiers métier recopiés de
``erp-backups/fichiers/<bucket>/`` (ADCG30) vers ``<bucket><suffixe>``.
Consigné en ``BackupRun`` (kind=restore, toute l'instance). Une cible égale
à la base de production est refusée sans ``--remplacer-production <nom>``.

Exemple (procédure complète : docs/backup-runbook.md) :
    python manage.py restaurer_sauvegarde --dump pg_dumps/20261110-030000.dump \\
        --base erp_restaure --suffixe-buckets -restaure
"""
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from core import backup
from core.models import BackupRun


class Command(BaseCommand):
    help = ('Restaure un dump nommé dans une base neuve avec propriétaires, '
            'droits, rôles et fichiers (procédure de reprise réelle).')

    def add_arguments(self, parser):
        parser.add_argument('--dump', required=True,
                            help="object_key du dump dans erp-backups (ex. pg_dumps/AAAAMMJJ-HHMMSS.dump)")
        parser.add_argument('--base', required=True, help='Base cible NEUVE (créée par la commande).')
        parser.add_argument('--suffixe-buckets', default='-restaure',
                            help='Suffixe des buckets qui reçoivent les fichiers (défaut -restaure).')
        parser.add_argument('--roles-sql', default=str(settings.BASE_DIR.parent / 'db' / 'rls_roles.sql'),
                            help='Chemin de backend/db/rls_roles.sql (à copier dans le conteneur).')
        parser.add_argument('--remplacer-production', default=None, metavar='NOM',
                            help='Confirme une cible égale à la base de production (son nom exact).')

    def handle(self, *args, **options):
        try:
            backup.verifier_cible_restauration(options['base'], options['remplacer_production'])
        except backup.RestoreDrillGuardError as exc:
            raise CommandError(str(exc))
        prod = settings.DATABASES['default']['NAME']
        if not options['suffixe_buckets'] and options['remplacer_production'] != prod:
            raise CommandError('Un suffixe de buckets vide écraserait les fichiers vivants : '
                               'confirmer avec --remplacer-production <nom de la base de production>.')
        run = BackupRun.objects.create(
            kind=BackupRun.KIND_RESTORE, mode=BackupRun.MODE_MANUEL, company=None)
        run = backup.restaurer_sauvegarde(
            run, options['dump'], options['base'], options['suffixe_buckets'],
            options['roles_sql'], options['remplacer_production'])
        if run.statut != BackupRun.STATUT_TERMINE:
            message = (run.detail or {}).get('message', 'échec inconnu')
            raise CommandError(f'restaurer_sauvegarde: échec (BackupRun #{run.pk}): {message}')
        detail = run.detail or {}
        self.stdout.write(self.style.SUCCESS(
            f"restaurer_sauvegarde: OK — BackupRun #{run.pk}, base={detail.get('base')}, "
            f"comptages={detail.get('comptages')}, fichiers={detail.get('fichiers')}"))
