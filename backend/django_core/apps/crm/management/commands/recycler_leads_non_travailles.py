"""YLEAD14 — Recyclage des leads non travaillés (SLA speed-to-lead), Celery Beat.

FG28 fournit déjà `lead_sla_hours(company)` + l'endpoint LECTURE SEULE
`leads/sla-breach/` : ils LISTENT les leads NEW non contactés au-delà du SLA
mais rien ne les ESCALADE ni ne les rend au pool. Cette commande, destinée à
être planifiée (Celery Beat — voir `erp_agentique/celery.py`
`crm.recycler_leads_non_travailles`), pour CHAQUE société :

  1. calcule les leads SLA-dépassés (`apps.crm.selectors.leads_sla_depasse`,
     réutilise `lead_sla_hours`) ;
  2. journalise une escalade (`LeadActivity`, système) sur chacun et notifie
     le responsable (`notifications.notify`), au plus UNE fois par lead
     (idempotent : une escalade déjà journalisée n'est pas répétée) ;
  3. option — au-delà d'un 2e seuil plus long (`CompanyProfile.
     lead_sla_deassign_hours`, 0 = désactivé par défaut), désassigne le lead
     (`owner` → None) pour le rendre au pool commercial.

Best-effort par lead : un échec (notification, société mal configurée)
n'interrompt jamais le traitement des autres leads. Aucun argument requis :

    python manage.py recycler_leads_non_travailles [--dry-run]
"""
from django.core.management.base import BaseCommand
from django.utils import timezone

#: Corps de note système marquant une escalade déjà traitée (idempotence —
#: recherché parmi les activités du lead avant d'en journaliser une nouvelle).
ESCALATION_MARKER = 'auto — recyclage SLA : lead non travaillé'


class Command(BaseCommand):
    help = ('YLEAD14 — Escalade les leads NEW non contactés au-delà du SLA '
            'société (+ désassignation optionnelle au 2e seuil).')

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run', action='store_true',
            help='Liste ce qui serait fait sans écrire en base.')

    def handle(self, *args, **options):
        dry_run = options.get('dry_run', False)
        escalated, deassigned = recycler_leads_non_travailles(
            dry_run=dry_run)
        if dry_run:
            self.stdout.write(self.style.WARNING(
                f'[dry-run] {escalated} lead(s) seraient escaladé(s), '
                f'{deassigned} désassigné(s).'))
        else:
            self.stdout.write(self.style.SUCCESS(
                f'{escalated} lead(s) escaladé(s), '
                f'{deassigned} désassigné(s).'))


def recycler_leads_non_travailles(now=None, dry_run=False):
    """Cœur de la commande — appelable directement (tests, tâche Celery).

    Renvoie ``(nb_escalades, nb_desassignations)``. ``now`` est injectable
    pour des tests déterministes. Company-scopé : itère TOUTES les sociétés,
    chacune isolée (jamais de fuite cross-tenant). Best-effort par lead.
    """
    from authentication.models import Company

    from apps.crm import selectors
    from apps.crm.models import LeadActivity
    from apps.crm.services import lead_sla_hours

    now = now or timezone.now()
    nb_escalades = 0
    nb_desassignations = 0

    for company in Company.objects.all():
        seuil = lead_sla_hours(company)
        if not seuil:
            continue  # SLA désactivé pour cette société — rien à recycler.

        deassign_hours = _deassign_hours(company)

        leads = selectors.leads_sla_depasse(
            company, now=now, seuil_heures=seuil)
        for lead in leads:
            already_escalated = LeadActivity.objects.filter(
                lead=lead, kind=LeadActivity.Kind.NOTE,
                body__startswith=ESCALATION_MARKER,
            ).exists()
            if not already_escalated:
                nb_escalades += 1
                if not dry_run:
                    _escalate(lead, seuil, now)

            if deassign_hours and lead.owner_id:
                age_hours = (
                    now - lead.date_creation).total_seconds() / 3600.0
                if age_hours >= deassign_hours:
                    nb_desassignations += 1
                    if not dry_run:
                        _deassign(lead)

    return nb_escalades, nb_desassignations


def _deassign_hours(company):
    try:
        from apps.parametres.models import CompanyProfile
        profile = CompanyProfile.objects.filter(company=company).first()
        if profile is not None and profile.lead_sla_deassign_hours:
            return int(profile.lead_sla_deassign_hours)
    except Exception:
        pass
    return 0


def _escalate(lead, seuil, now):
    from apps.crm.models import LeadActivity

    body = (f'{ESCALATION_MARKER} depuis plus de {seuil} h '
            f'(créé le {lead.date_creation:%Y-%m-%d %H:%M}).')
    LeadActivity.objects.create(
        company=lead.company, lead=lead, user=None,
        kind=LeadActivity.Kind.NOTE, body=body)
    try:
        from apps.notifications.services import notify
        from apps.crm.services import lead_notification_recipients
        recipients = lead_notification_recipients(lead)
        for recipient in recipients:
            nom = (lead.nom or '').strip() or 'Lead'
            notify(
                recipient, 'lead_assigned',
                f'Lead non contacté : {nom}',
                body=f'{nom} dépasse le SLA de première prise de contact.',
                link=f'/crm/leads?lead={lead.pk}',
                company=lead.company,
            )
    except Exception:  # noqa: BLE001 — best-effort, jamais bloquant
        pass


def _deassign(lead):
    from apps.crm.models import LeadActivity

    ancien_owner = lead.owner
    lead.owner = None
    lead.save(update_fields=['owner'])
    body = 'auto — recyclage SLA : lead désassigné, rendu au pool'
    if ancien_owner is not None:
        body += f' (précédemment {ancien_owner})'
    LeadActivity.objects.create(
        company=lead.company, lead=lead, user=None,
        kind=LeadActivity.Kind.NOTE, body=body)
