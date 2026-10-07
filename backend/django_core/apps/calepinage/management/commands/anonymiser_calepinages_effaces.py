"""ACAL300 — rattrapage : anonymiser les calepinages des personnes DÉJÀ
effacées (lead anonymisé par le DSR ou la rétention, client ``is_anonymized``)
avant que le calepinage ne soit fournisseur DSR.

DRY-RUN PAR DÉFAUT : liste ``id / ancien titre / nb photos`` sans rien
écrire — la liste est soumise au fondateur AVANT ``--apply`` en production
(le nom de fichier et la page de garde de livrables déjà remis changent).

    python manage.py anonymiser_calepinages_effaces
    python manage.py anonymiser_calepinages_effaces --apply
"""
from __future__ import annotations

from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = ("ACAL300 — anonymise (loi 09-08) les calepinages des leads / "
            "clients déjà anonymisés. Dry-run par défaut ; --apply écrit.")

    def add_arguments(self, parser):
        parser.add_argument('--apply', action='store_true',
                            help='Écrit réellement (sinon : liste seule).')

    def handle(self, *args, **options):
        from django.db.models import Q

        from apps.crm.selectors import (
            client_ids_anonymises, lead_ids_anonymises,
        )
        from authentication.models import Company

        from ...dsr_provider import anonymiser_calepinage
        from ...models import Calepinage

        appliquer = options['apply']
        total = 0
        for company in Company.objects.order_by('pk'):
            leads = lead_ids_anonymises(company)
            clients = client_ids_anonymises(company)
            if not leads and not clients:
                continue
            calepinages = (Calepinage.objects.filter(company=company)
                           .filter(Q(lead_id__in=leads)
                                   | Q(client_id__in=clients))
                           .order_by('pk'))
            for calepinage in calepinages:
                ligne = '%s / %s / %s photo(s)' % (
                    calepinage.pk, calepinage.titre or '—',
                    calepinage.photos_site.count())
                if appliquer:
                    change = anonymiser_calepinage(calepinage)
                    ligne += ' → anonymisé' if change else ' → déjà fait'
                self.stdout.write(ligne)
                total += 1
        self.stdout.write('%s calepinage(s) %s.' % (
            total, 'traités' if appliquer else 'à anonymiser (dry-run)'))
