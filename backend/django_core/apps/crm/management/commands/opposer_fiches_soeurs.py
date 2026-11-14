"""AMSG97 (D-AMSG-2) — coche « ne plus contacter » les fiches contactables qui
partagent un contact avec une personne opposée AVANT AMSG3 (la migration 0154
a posé ses empreintes sans les sœurs). Dry-run par défaut : id, société,
nature du contact commun (jamais le numéro ni l'e-mail) ; ``--appliquer``
coche avec la ligne de chatter (jamais de SQL) ; rejouable.

    python manage.py opposer_fiches_soeurs [--societe <slug>] [--appliquer] [--sauf 12,34]
"""
from django.core.management.base import BaseCommand

from apps.crm.leads_doublons import (
    _marquer_lead_ne_plus_contacter, fiches_soeurs_contactables)
from apps.crm.models import Lead
from authentication.models import Company


def _nature(oppose, soeur):
    tels = {oppose.phone_normalise, oppose.whatsapp_normalise} - {'', None}
    if tels & {soeur.phone_normalise, soeur.whatsapp_normalise}:
        return 'téléphone'
    return 'e-mail'


class Command(BaseCommand):
    help = ("Liste (dry-run) puis, avec --appliquer, coche « ne plus "
            "contacter » les fiches sœurs d'une opposition antérieure.")

    def add_arguments(self, parser):
        parser.add_argument('--societe', help='Slug de la société (défaut : toutes).')
        parser.add_argument('--appliquer', action='store_true', help='Écrire (défaut : dry-run).')
        parser.add_argument('--sauf', default='', help='Ids de leads à ne pas cocher (virgules).')

    def handle(self, *args, **opts):
        sauf = {int(x) for x in opts['sauf'].split(',') if x.strip()}
        societes = Company.objects.order_by('pk')
        if opts['societe']:
            societes = societes.filter(slug=opts['societe'])
        soeurs = {}
        for company in societes:
            for oppose in Lead.objects.filter(
                    company=company, ne_plus_contacter=True).order_by('pk'):
                for soeur in fiches_soeurs_contactables(company, oppose):
                    if soeur.pk not in sauf:
                        soeurs.setdefault(soeur.pk, (company.slug, _nature(oppose, soeur)))
        for pk, (slug, nature) in sorted(soeurs.items()):
            self.stdout.write(f'lead #{pk} · société {slug} · contact commun : {nature}')
        if not opts['appliquer']:
            self.stdout.write(f'{len(soeurs)} fiche(s) — dry-run, rien écrit')
            return
        cochees = 0
        for pk in sorted(soeurs):  # relue : une sœur peut être cochée en cascade
            lead = Lead.objects.filter(pk=pk, ne_plus_contacter=False).first()
            cochees += bool(lead and _marquer_lead_ne_plus_contacter(lead, None))
        self.stdout.write(f'{cochees} fiche(s) cochée(s)')
