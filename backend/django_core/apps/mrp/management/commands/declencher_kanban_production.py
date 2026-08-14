"""NTMFG17 — balaie les règles kanban de production ACTIVES et déclenche un
OF brouillon pour chaque produit passé sous son seuil, société par société.
Conçue pour être appelée par un planificateur (cron/Celery beat), ou
manuellement — le déclenchement manuel équivalent existe aussi côté API
(`POST /api/django/mrp/kanban/declencher/`) pour les déploiements sans
Celery beat (dégradation gracieuse).

Multi-société : tout est borné à la société (jamais un OF créé pour une
autre société)."""
from django.core.management.base import BaseCommand

from apps.mrp import services


class Command(BaseCommand):
    help = (
        'NTMFG17 — déclenche les OF kanban de production dus (stock sous '
        'seuil), pour toutes les sociétés actives.')

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
            crees = services.declencher_kanban_toutes_regles(company)
            if crees:
                total += len(crees)
                self.stdout.write(f'{company} : {len(crees)} OF déclenché(s)')

        self.stdout.write(self.style.SUCCESS(f'{total} OF kanban déclenché(s) au total.'))
