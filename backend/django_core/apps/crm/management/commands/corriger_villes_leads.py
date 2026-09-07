"""VREF — rattrapage : corrige les villes des leads EXISTANTS.

Applique aux leads déjà en base le même résolveur que les chemins
d'écriture (formulaire, webhook site) : graphie connue, raccourci unique
(« belksiri » → Mechraa Bel Ksiri) ou faute de frappe sûre → nom canonique
du gazetier, avec une note chatter par correction. Ambigu/inconnu : rien
n'est touché — l'écran « Vérifier la ville » de Meryem s'en charge (le
rapport les liste).

Dry-run PAR DÉFAUT ; ``--apply`` écrit, borné par ``--limite`` (défaut 200).
"""
from django.core.management.base import BaseCommand

from apps.crm.models import Lead, LeadActivity
from apps.parametres.villes_resolution import resoudre_ville


class Command(BaseCommand):
    help = ("VREF — corrige les villes des leads existants via le résolveur "
            "du gazetier (dry-run par défaut ; --apply, --limite N).")

    def add_arguments(self, parser):
        parser.add_argument('--apply', action='store_true')
        parser.add_argument('--limite', type=int, default=200)

    def handle(self, *args, **options):
        leads = (Lead.objects.exclude(ville__isnull=True).exclude(ville='')
                 .order_by('-id'))
        corrections, douteuses = [], []
        for lead in leads.iterator():
            resultat = resoudre_ville(lead.ville)
            if resultat['statut'] == 'corrigee':
                corrections.append((lead, resultat['ville']))
            elif resultat['statut'] in ('ambigue', 'inconnue'):
                douteuses.append((lead, resultat['statut']))

        limite = max(1, options['limite'])
        lot = corrections[:limite]
        self.stdout.write(
            f'{len(corrections)} ville(s) corrigeable(s), '
            f'{len(douteuses)} à vérifier sur la carte (ambiguës/inconnues).')
        for lead, canon in lot:
            self.stdout.write(
                f'  - #{lead.pk} {lead.nom} : « {lead.ville} » → « {canon} »')
        for lead, statut in douteuses[:20]:
            self.stdout.write(
                f'  ? #{lead.pk} {lead.nom} : « {lead.ville} » ({statut})')

        if not options['apply']:
            self.stdout.write('Dry-run — rien n\'est écrit '
                              '(--apply pour corriger).')
            return
        for lead, canon in lot:
            avant = lead.ville
            lead.ville = canon
            lead.save(update_fields=['ville'])
            LeadActivity.objects.create(
                company=lead.company, lead=lead, user=None,
                kind=LeadActivity.Kind.NOTE,
                body=f'Ville corrigée automatiquement : '
                     f'« {avant} » → « {canon} » (gazetier).')
        self.stdout.write(self.style.SUCCESS(
            f'{len(lot)} ville(s) corrigée(s), '
            f'{max(0, len(corrections) - len(lot))} restante(s).'))
