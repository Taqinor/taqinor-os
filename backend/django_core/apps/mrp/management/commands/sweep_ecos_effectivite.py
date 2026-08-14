"""NTMFG15 — balaie les Ordres de Modification (ECO) `approuve` dont la date
d'effectivité est atteinte et les applique, société par société. Conçue pour
être appelée par un planificateur (cron/Celery beat) à cadence quotidienne, ou
manuellement.

Multi-société : tout est borné à la société (jamais un ECO d'une autre
société appliqué). Une société sans ECO en attente est simplement ignorée."""
from django.core.management.base import BaseCommand

from apps.mrp import services


class Command(BaseCommand):
    help = (
        "NTMFG15 — applique les ECO approuvés dont la date d'effectivité "
        'est atteinte.')

    def add_arguments(self, parser):
        parser.add_argument(
            '--company', type=int, default=None,
            help='Limiter à une société (ID). Par défaut : toutes les sociétés.')

    def handle(self, *args, **options):
        from authentication.models import Company

        company_id = options['company']
        companies = Company.objects.all()
        if company_id is not None:
            companies = companies.filter(pk=company_id)

        total = 0
        for company in companies:
            appliques = services.sweep_ecos_effectivite(company)
            if appliques:
                total += len(appliques)
                self.stdout.write(f'{company} : {len(appliques)} ECO appliqué(s)')

        self.stdout.write(self.style.SUCCESS(f'{total} ECO appliqué(s) au total.'))
