"""FG366 — Repère et escalade les étapes de workflow en dépassement SLA.

Parcourt chaque société (ou une seule via ``--company-id``) et marque
``escalade`` toute ``WorkflowStepInstance`` encore ``en_attente`` dont
l'échéance SLA est passée (``sla_echeance < now``). Le « maintenant » par
défaut est ``timezone.now()`` mais peut être figé par ``--now`` (ISO 8601)
pour un test déterministe ou un rattrapage.

À câbler sur Celery Beat / cron pour des escalades périodiques. ``--dry-run``
liste sans rien modifier.

Exemples :
  python manage.py escalate_workflow_sla
  python manage.py escalate_workflow_sla --company-id 3 --dry-run
  python manage.py escalate_workflow_sla --now 2026-06-29T08:00:00
"""
import datetime

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from authentication.models import Company
from core.workflow import escalader_etape, etapes_sla_depassees


class Command(BaseCommand):
    help = (
        "Escalade les étapes de workflow dont le SLA est dépassé "
        "(WorkflowStepInstance en attente, sla_echeance < now)."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--company-id', type=int, default=None,
            help='Limiter à une seule société (sinon : toutes).')
        parser.add_argument(
            '--now', default=None,
            help="Horodatage de référence ISO 8601 (défaut : maintenant).")
        parser.add_argument(
            '--dry-run', action='store_true',
            help='Lister sans escalader.')

    def handle(self, *args, **options):
        now = self._resolve_now(options['now'])
        companies = Company.objects.all()
        if options['company_id'] is not None:
            companies = companies.filter(id=options['company_id'])

        total = 0
        for company in companies:
            overdue = etapes_sla_depassees(company, now)
            if not overdue:
                continue
            for step in overdue:
                label = (
                    f"société={company.id} instance={step.instance_id} "
                    f"étape={step.ordre} échéance={step.sla_echeance}"
                )
                if options['dry_run']:
                    self.stdout.write(f"[dry-run] dépassée : {label}")
                else:
                    escalader_etape(step, now=now)
                    self.stdout.write(f"escaladée : {label}")
                total += 1

        verbe = 'à escalader' if options['dry_run'] else 'escaladée(s)'
        self.stdout.write(self.style.SUCCESS(
            f"{total} étape(s) {verbe} (référence : {now.isoformat()})."))

    def _resolve_now(self, raw):
        if not raw:
            return timezone.now()
        try:
            parsed = datetime.datetime.fromisoformat(raw)
        except ValueError as exc:
            raise CommandError(f"--now invalide : {raw}") from exc
        if timezone.is_naive(parsed):
            parsed = timezone.make_aware(parsed)
        return parsed
