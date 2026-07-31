"""NTUX7 — purge de rétention de la corbeille transverse (30 jours).

Supprime DÉFINITIVEMENT les `ElementSupprime` dont `expire_le` est dépassé et
journalise le nombre purgé par société. Idempotent ; `--dry-run` ne supprime
rien. La planification Celery beat (quotidienne) est NTUX29.
"""
from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.trash.selectors import expirees
from apps.trash.services import purger_expires


class Command(BaseCommand):
    help = "Purge les entrées de corbeille dont la rétention (30 j) est dépassée."

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true')
        parser.add_argument('--company', type=int, default=None)

    def handle(self, *args, **options):
        now = timezone.now()
        company_id = options['company']

        if options['dry_run']:
            qs = expirees(now=now)
            if company_id:
                qs = qs.filter(company_id=company_id)
            total = qs.count()
            self.stdout.write(f'{total} entrée(s) purgeable(s) au {now:%Y-%m-%d %H:%M}.')
            return

        company = None
        if company_id:
            from authentication.models import Company
            company = Company.objects.filter(pk=company_id).first()
            if company is None:
                self.stdout.write(f'Société {company_id} introuvable.')
                return

        par_company = purger_expires(now=now, company=company)
        for cid, nombre in sorted(par_company.items()):
            self.stdout.write(f'société {cid} : {nombre} entrée(s) purgée(s).')
        self.stdout.write(f'Total purgé : {sum(par_company.values())}.')
