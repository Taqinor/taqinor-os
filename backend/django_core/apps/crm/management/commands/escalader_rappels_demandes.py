"""QW4 — Escalade des rappels demandés (contact_preference=phone_ok) non
actionnés au-delà du SLA rappel, Celery Beat.

Réutilise EXACTEMENT le patron de
``recycler_leads_non_travailles`` (YLEAD14) : company-scopé, idempotent (un
marqueur chatter empêche une double escalade), best-effort par lead. Distinct
du SLA générique premier-contact — un rappel demandé a un SLA plus SERRÉ
(``apps.crm.services.callback_sla_hours``, la moitié du SLA générique).

    python manage.py escalader_rappels_demandes [--dry-run]
"""
from django.core.management.base import BaseCommand
from django.utils import timezone

#: Corps de note système marquant une escalade déjà traitée (idempotence).
ESCALATION_MARKER = 'auto — escalade SLA rappel : rappel non actionné'


class Command(BaseCommand):
    help = ('QW4 — Escalade les rappels demandés (phone_ok) non actionnés '
            'au-delà du SLA rappel (plus serré que le SLA générique).')

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run', action='store_true',
            help='Liste ce qui serait fait sans écrire en base.')

    def handle(self, *args, **options):
        dry_run = options.get('dry_run', False)
        escalated = escalader_rappels_demandes(dry_run=dry_run)
        if dry_run:
            self.stdout.write(self.style.WARNING(
                f'[dry-run] {escalated} rappel(s) seraient escaladé(s).'))
        else:
            self.stdout.write(self.style.SUCCESS(
                f'{escalated} rappel(s) escaladé(s).'))


def escalader_rappels_demandes(now=None, dry_run=False):
    """Cœur de la commande — appelable directement (tests, tâche Celery).

    Renvoie ``nb_escalades``. ``now`` injectable pour des tests déterministes.
    Company-scopé : itère TOUTES les sociétés, chacune isolée. Best-effort par
    lead : un échec de notification n'interrompt jamais le traitement des
    autres leads."""
    from authentication.models import Company

    from apps.crm import selectors
    from apps.crm.models import LeadActivity
    from apps.crm.services import callback_sla_hours, lead_notification_recipients

    now = now or timezone.now()
    nb_escalades = 0

    for company in Company.objects.all():
        seuil = callback_sla_hours(company)
        if not seuil:
            continue  # SLA rappel désactivé (SLA générique désactivé aussi).

        leads = selectors.leads_callback_sla_depasse(
            company, now=now, seuil_heures=seuil)
        for lead in leads:
            already_escalated = LeadActivity.objects.filter(
                lead=lead, kind=LeadActivity.Kind.NOTE,
                body__startswith=ESCALATION_MARKER,
            ).exists()
            if already_escalated:
                continue
            nb_escalades += 1
            if dry_run:
                continue
            _escalate(lead, seuil, now, lead_notification_recipients)

    return nb_escalades


def _escalate(lead, seuil, now, recipients_fn):
    from apps.crm.models import LeadActivity

    body = (f'{ESCALATION_MARKER} depuis plus de {seuil} h '
            f'(rappel demandé le {lead.date_creation:%Y-%m-%d %H:%M}).')
    LeadActivity.objects.create(
        company=lead.company, lead=lead, user=None,
        kind=LeadActivity.Kind.NOTE, body=body)
    try:
        from apps.notifications.services import notify_many
        recipients = recipients_fn(lead)
        if recipients:
            nom = (lead.nom or '').strip() or 'Un prospect'
            notify_many(
                recipients, 'lead_callback_sla_breach',
                f'☎ Rappel non actionné : {nom}',
                body=(f'{nom} a demandé un rappel il y a plus de {seuil} h '
                      f'sans être contacté.'),
                link=f'/crm/leads?lead={lead.pk}',
                company=lead.company,
            )
    except Exception:  # noqa: BLE001 — best-effort, jamais bloquant
        pass
