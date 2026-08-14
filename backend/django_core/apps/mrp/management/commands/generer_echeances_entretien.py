"""NTMFG14 — génère les échéances de maintenance préventive dues pour tous
les plans d'entretien de poste (`PlanEntretienPoste`) actifs, société par
société. Conçue pour être appelée par un planificateur (cron/Celery beat) à
cadence raisonnable, ou manuellement.

Multi-société : tout est borné à la société (jamais une échéance générée
pour une autre). Une société sans plan actif est simplement ignorée (aucune
exception, aucune notification — NTMFG14 ne pousse aucune alerte proactive,
cf. NTMFG32 hors périmètre de ce ticket)."""
from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.mrp import services


class Command(BaseCommand):
    help = (
        'NTMFG14 — génère les échéances de maintenance préventive dues pour '
        "les postes de charge (plans d'entretien actifs).")

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

        today = timezone.localdate()
        total = 0
        for company in companies:
            creees = services.generer_echeances_entretien(company, today=today)
            if creees:
                total += len(creees)
                self.stdout.write(f'{company} : {len(creees)} échéance(s) générée(s)')

        self.stdout.write(self.style.SUCCESS(
            f'{total} échéance(s) de maintenance de poste générée(s) au total.'))
