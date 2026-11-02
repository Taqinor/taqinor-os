"""CADV1 — remet au Froid les leads REBONDIS par l'alignement Odoo.

L'alignement Odoo du 17/09-08/10 (``odoo_sync.align_stages_from_rows``, Froid =
rang -1) a repoussé vers leur ancienne étape, 20 min plus tard, des leads qu'un
humain venait de ranger au Froid. Signature : les DEUX dernières activités
``field='stage'`` sont [X → Froid, par un humain] puis [Froid → X, sans auteur].

Dry-run PAR DÉFAUT (les ids sont imprimés) ; ``--apply`` remet l'étape Froid par
``avancer_stage_lead_vers`` (jamais de SQL), pose l'étiquette de parc et une
note « Réparation du <date> ». Rejouable : une fois réparé, la dernière activité
d'étape n'est plus celle de la machine.

    python manage.py reparer_rebonds_froid [--company <slug|id>] [--apply]
                                           [--limite N] [--ids 1,2,3]
"""
import datetime

from django.core.management.base import BaseCommand, CommandError

from apps.crm import stages
from apps.crm.activity import log_bulk_note
from apps.crm.cadence_plan import ISSUES_CLIENT_JOINT, arreter_cadence
from apps.crm.cadence_selectors import leads_reveil_sans_historique
from apps.crm.fiche_funnel import avancer_stage_lead_vers, poser_tag_lead
from apps.crm.management.commands.placer_anciens_leads import (
    _resoudre_company,
)
from apps.crm.models import Lead, LeadActivity
from apps.ventes.selectors import leads_ayant_recu_un_devis

TAG_INJOIGNABLE = 'Parc — injoignable'
TAG_PAS_MAINTENANT = 'Parc — pas maintenant (sans date)'
MOTIF_REVEIL_AVEUGLE = 'réveil sans historique : jamais joint ni chiffré'


def _est_froid(valeur):
    return valeur in (stages.COLD, stages.STAGE_LABELS.get(stages.COLD))


def _rebonds(company, ids=None):
    """Leads non Froid dont la dernière bascule d'étape est celle de la machine
    et l'avant-dernière un parcage humain au Froid."""
    activites = (LeadActivity.objects
                 .filter(company=company, field='stage')
                 .order_by('lead_id', 'id')
                 .values_list('lead_id', 'user_id', 'old_value', 'new_value'))
    if ids:
        activites = activites.filter(lead_id__in=ids)
    derniers = {}
    for lead_id, user_id, ancien, nouveau in activites.iterator():
        derniers.setdefault(lead_id, []).append((user_id, ancien, nouveau))
    candidats = []
    for lead_id, lignes in derniers.items():
        if len(lignes) < 2:
            continue
        (u_avant, _a1, n_avant), (u_der, a_der, n_der) = lignes[-2:]
        if (u_avant is not None and _est_froid(n_avant)
                and u_der is None and _est_froid(a_der)
                and not _est_froid(n_der)):
            candidats.append(lead_id)
    return list(Lead.objects.filter(
        company=company, pk__in=candidats, is_archived=False,
    ).exclude(stage=stages.COLD).order_by('pk'))


def _jamais_joint(lead):
    return not lead.activites.filter(
        outcome__in=ISSUES_CLIENT_JOINT).exists()


class Command(BaseCommand):
    help = ('CADV1 — remet au Froid les leads rebondis par l\'alignement Odoo '
            '(dry-run par défaut ; --apply, --limite N, --ids).')

    def add_arguments(self, parser):
        parser.add_argument('--company', dest='company', default=None)
        parser.add_argument('--apply', action='store_true')
        parser.add_argument('--limite', type=int, default=None)
        parser.add_argument('--ids', default='',
                            help='Ids de leads séparés par des virgules.')
        parser.add_argument(
            '--population', choices=('rebonds', 'reveils'), default='rebonds',
            help="rebonds (défaut) : remise au Froid ; reveils (CADV3) : "
                 "annule les réveils ouverts des leads jamais joints ni "
                 "chiffrés.")

    def _reveils(self, company, ids, options):
        """CADV3 — annule les touches ``reveil`` des réveils « aveugles »."""
        leads = leads_reveil_sans_historique(company)
        if ids:
            leads = leads.filter(pk__in=ids)
        leads = list(leads)
        if options.get('limite'):
            leads = leads[:max(1, options['limite'])]
        self.stdout.write(
            f'{len(leads)} lead(s) à réveil sans historique à arrêter.')
        for lead in leads:
            self.stdout.write(f'  #{lead.pk} {lead.nom}')
        if not options['apply']:
            self.stdout.write("Dry-run — rien n'est écrit (--apply).")
            return
        for lead in leads:
            arreter_cadence(lead, user=None, motif=MOTIF_REVEIL_AVEUGLE,
                            cadences=['reveil'])
        self.stdout.write(self.style.SUCCESS(
            f'{len(leads)} lead(s) : réveils annulés.'))

    def handle(self, *args, **options):
        company = _resoudre_company(options.get('company'))
        try:
            ids = [int(i) for i in options['ids'].split(',') if i.strip()]
        except ValueError:
            raise CommandError('--ids : entiers séparés par des virgules.')
        if options['population'] == 'reveils':
            return self._reveils(company, ids, options)
        leads = _rebonds(company, ids or None)
        if options.get('limite'):
            leads = leads[:max(1, options['limite'])]
        devis = leads_ayant_recu_un_devis(company, [x.pk for x in leads])
        self.stdout.write(
            f'{len(leads)} lead(s) rebondi(s) à remettre au Froid.')
        plan = []
        for lead in leads:
            chiffre = lead.pk in devis
            tag = (TAG_INJOIGNABLE if not chiffre and _jamais_joint(lead)
                   else TAG_PAS_MAINTENANT)
            plan.append((lead, tag))
            self.stdout.write(f'  #{lead.pk} {lead.nom} : {lead.stage} → '
                              f'{stages.COLD} ({tag})')
        if not options['apply']:
            self.stdout.write("Dry-run — rien n'est écrit (--apply).")
            return
        aujourd_hui = datetime.date.today().strftime('%d/%m/%Y')
        for lead, tag in plan:
            avancer_stage_lead_vers(lead, None, stages.COLD)
            poser_tag_lead(lead, None, tag)
            log_bulk_note(
                lead, None,
                f'Réparation du {aujourd_hui} : rebond de l\'alignement Odoo '
                f'annulé, remis au Froid ({tag}).')
        self.stdout.write(self.style.SUCCESS(
            f'{len(plan)} lead(s) remis au Froid.'))
