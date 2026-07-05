"""YOPSB10 — exécute TOUTES les politiques de rétention enregistrées.

Dry-run par défaut (``settings.RETENTION_AUTO_APPLY``) : chaque politique
reçoit ``apply_=False`` tant que ``--apply`` n'est pas passé (ou que le
réglage n'est pas explicitement actif).

Exemple :
    python manage.py run_retention             # dry-run
    python manage.py run_retention --apply      # applique réellement
"""
from django.conf import settings
from django.core.management.base import BaseCommand

from core import retention


class Command(BaseCommand):
    help = ('Exécute toutes les politiques de rétention enregistrées '
            '(core.retention). Dry-run par défaut.')

    def add_arguments(self, parser):
        parser.add_argument(
            '--apply', action='store_true', default=False,
            help='Applique réellement les suppressions (sinon dry-run).')

    def handle(self, *args, **options):
        apply_ = options['apply'] or bool(
            getattr(settings, 'RETENTION_AUTO_APPLY', False))
        results = retention.run_all_policies(apply_=apply_)

        if not results:
            self.stdout.write(self.style.WARNING(
                'run_retention: aucune politique enregistrée.'))
            return

        for r in results:
            style = self.style.SUCCESS if r['statut'] == 'ok' else self.style.ERROR
            self.stdout.write(style(
                f"{r['name']}: statut={r['statut']} compte={r['count']}"
                + (f" erreur={r['erreur']}" if r['erreur'] else '')))

        self.stdout.write(self.style.SUCCESS(
            f"run_retention: {len(results)} politique(s) exécutée(s) "
            f"(apply={apply_})."))
