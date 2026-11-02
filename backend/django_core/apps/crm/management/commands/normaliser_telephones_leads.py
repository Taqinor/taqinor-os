"""CADV4 — ramène ``telephone`` et ``whatsapp`` des leads à ``212XXXXXXXXX``.

L'import Odoo garde le texte brut (``odoo_sync._clean_phone``) alors que l'API
canonise (``LeadSerializer._canonical_phone``) : « 06 12-34 56 78 » reste tel
quel en base et l'analyse le compte invalide. Cette commande applique aux leads
EXISTANTS la même canonisation que l'API (source unique, aucune seconde
normalisation) : un numéro étranger (« +33612345678 ») ou non reconnaissable
est laissé intact.

Dry-run PAR DÉFAUT (« #id avant → après » imprimé) ; ``--apply`` écrit par
``lead.save(update_fields=...)``. Rejouable : un numéro déjà canonique ne change
plus.

    python manage.py normaliser_telephones_leads [--company <slug|id>]
                                                 [--apply] [--ids 1,2,3]
"""
from django.core.management.base import BaseCommand, CommandError

from apps.crm.management.commands.placer_anciens_leads import (
    _resoudre_company,
)
from apps.crm.models import Lead
from apps.crm.serializers import LeadSerializer

CHAMPS = ('telephone', 'whatsapp')


def _changements(lead):
    """[(champ, avant, après)] pour les champs que la canonisation modifie."""
    out = []
    for champ in CHAMPS:
        avant = getattr(lead, champ) or ''
        if not avant:
            continue
        apres = LeadSerializer._canonical_phone(avant)
        if apres and apres != avant:
            out.append((champ, avant, apres))
    return out


class Command(BaseCommand):
    help = ('CADV4 — normalise telephone/whatsapp des leads à 212XXXXXXXXX '
            '(dry-run par défaut ; --apply, --ids).')

    def add_arguments(self, parser):
        parser.add_argument('--company', dest='company', default=None)
        parser.add_argument('--apply', action='store_true')
        parser.add_argument('--ids', default='',
                            help='Ids de leads séparés par des virgules.')

    def handle(self, *args, **options):
        company = _resoudre_company(options.get('company'))
        try:
            ids = [int(i) for i in options['ids'].split(',') if i.strip()]
        except ValueError:
            raise CommandError('--ids : entiers séparés par des virgules.')
        leads = Lead.objects.filter(company=company).order_by('pk')
        if ids:
            leads = leads.filter(pk__in=ids)
        a_ecrire = []
        for lead in leads.iterator():
            changements = _changements(lead)
            if changements:
                a_ecrire.append((lead, changements))
        self.stdout.write(f'{len(a_ecrire)} lead(s) à normaliser.')
        for lead, changements in a_ecrire:
            for champ, avant, apres in changements:
                self.stdout.write(
                    f'  #{lead.pk} {champ} : {avant!r} → {apres!r}')
        if not options['apply']:
            self.stdout.write("Dry-run — rien n'est écrit (--apply).")
            return
        for lead, changements in a_ecrire:
            for champ, _avant, apres in changements:
                setattr(lead, champ, apres)
            lead.save(update_fields=[c for c, _a, _b in changements])
        self.stdout.write(self.style.SUCCESS(
            f'{len(a_ecrire)} lead(s) normalisé(s).'))
