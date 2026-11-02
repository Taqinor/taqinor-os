"""CADV5 — archive et étiquette ``archive_odoo`` les contacts Odoo froids sans
trace humaine dans l'ERP (D-CADV-8 : 423 des 721 Froid en production).

Population : ``source`` Odoo, au Froid, non archivé, aucune activité signée d'un
humain, aucune touche traitée (fait / sautée). Une touche encore À FAIRE ne
retient pas le lead : le récepteur de CADV61 l'annule à l'archivage.

Réversible (``restaurer`` rouvre le lead) ; l'étape Odoo reste citée dans la note.
Dry-run PAR DÉFAUT (ids imprimés) ; ``--apply`` écrit, une seule fois :
rejouer ne trouve plus rien. Le pilote d'appels sur les dossiers avancés dans
Odoo est un autre geste (CADV32).

    python manage.py archiver_froids_odoo [--company <slug|id>] [--apply]
                                          [--ids 1,2,3]
"""
import re

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from apps.crm import stages
from apps.crm.activity import log_bulk_note
from apps.crm.fiche_funnel import poser_tag_lead
from apps.crm.management.commands.placer_anciens_leads import (
    _resoudre_company,
)
from apps.crm.models import Lead, LeadActivity, LeadTag, RelanceEtape

TAG_ARCHIVE_ODOO = 'archive_odoo'

#: La ligne écrite par l'import (``odoo_sync.py`` : « Étape Odoo: Cold Lead »).
_ETAPE_ODOO = re.compile(r'Étape Odoo:\s*(.+)')


def _a_archiver(company):
    """Les contacts Odoo froids sans trace humaine de ``company``."""
    humains = LeadActivity.objects.filter(
        company=company, user__isnull=False).values('lead_id')
    traitees = RelanceEtape.objects.filter(
        company=company,
        statut__in=(RelanceEtape.Statut.FAIT, RelanceEtape.Statut.SAUTEE),
    ).values('lead_id')
    return list(
        Lead.objects.filter(
            company=company, source=Lead.Source.ODOO_IMPORT_TEST,
            stage=stages.COLD, is_archived=False,
        ).exclude(pk__in=humains).exclude(pk__in=traitees).order_by('pk'))


def _etape_odoo(lead):
    trouve = _ETAPE_ODOO.search(lead.note or '')
    return trouve.group(1).strip() if trouve else 'inconnue'


class Command(BaseCommand):
    help = ('CADV5 — archive et étiquette archive_odoo les contacts Odoo froids '
            'sans trace humaine (dry-run par défaut ; --apply, --ids).')

    def add_arguments(self, parser):
        parser.add_argument('--company', dest='company', default=None)
        parser.add_argument('--apply', action='store_true')
        parser.add_argument('--ids', default='',
                            help='Ids de leads séparés par des virgules.')

    def handle(self, *args, **options):
        company = _resoudre_company(options.get('company'))
        try:
            ids = {int(i) for i in options['ids'].split(',') if i.strip()}
        except ValueError:
            raise CommandError('--ids : entiers séparés par des virgules.')
        leads = _a_archiver(company)
        if ids:
            leads = [lead for lead in leads if lead.pk in ids]
        self.stdout.write(f'{len(leads)} contact(s) Odoo froid(s) à archiver.')
        for lead in leads:
            self.stdout.write(
                f'  #{lead.pk} {lead.nom} (étape Odoo : {_etape_odoo(lead)})')
        if not options['apply']:
            self.stdout.write("Dry-run — rien n'est écrit (--apply).")
            return
        if leads:
            LeadTag.objects.get_or_create(company=company, nom=TAG_ARCHIVE_ODOO)
        for lead in leads:
            lead.is_archived = True
            lead.archived_by = None
            lead.archived_at = timezone.now()
            lead.save(update_fields=['is_archived', 'archived_by', 'archived_at'])
            poser_tag_lead(lead, None, TAG_ARCHIVE_ODOO)
            log_bulk_note(
                lead, None,
                f'Archivé : contact Odoo froid sans trace dans l’ERP (étape '
                f'Odoo : {_etape_odoo(lead)}) (CADV5). « Restaurer » le rouvre.')
        self.stdout.write(self.style.SUCCESS(
            f'{len(leads)} contact(s) archivé(s).'))
