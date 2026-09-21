"""NTCRD24 — recalcule et journalise en masse les lettres de score + pct
utilisé pour tous les clients d'une société. AUCUNE écriture métier (rapport/
log seulement) : idempotent, sûr à rejouer.

Usage :
    python manage.py credit_recalcul_scores [--company <id>]
"""
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = ('NTCRD24 — recalcule (lecture seule) score + pct utilisé par '
            'client ; journalise, ne modifie aucune donnée métier.')

    def add_arguments(self, parser):
        parser.add_argument(
            '--company', type=int, default=None,
            help='Limiter à une société (id). Sinon toutes les sociétés.')

    def handle(self, *args, **options):
        from apps.crm.selectors import client_base_qs

        from ...selectors import score_credit

        company_id = options.get('company')

        from authentication.models import Company
        companies = Company.objects.all()
        if company_id:
            companies = companies.filter(id=company_id)

        total = 0
        for company in companies:
            for client in client_base_qs(company):
                data = score_credit(client)
                total += 1
                self.stdout.write(
                    f"[{company.id}] client={client.id} "
                    f"lettre={data['lettre']} "
                    f"pct={data['pct_utilise']} "
                    f"disponible={data['disponible']}")
        self.stdout.write(self.style.SUCCESS(
            f'{total} client(s) recalculé(s) (lecture seule, aucune écriture).'))
        return None
