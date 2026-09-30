"""ERR-QAC-MULTIVILLA-TOTAL-XN — liste les devis « ×N villas identiques » dont
l'argent change avec la décision fondateur du 30/09/2026 (« ×N everywhere ») :
``Devis.total_*``, la liste, le Kanban, le CA, l'échéancier, le BC et l'acompte
public lisent désormais le total ×N imprimé, plus le total d'UNE villa.

LECTURE SEULE. Aucun total n'est stocké (``Devis.total_*`` sont calculés) et
``prix_par_kwc`` ne bouge pas (TTC ×N ÷ kWc ×N = le même ratio) : il n'y a rien
à recalculer en base. La commande sert à REVOIR les devis concernés avant de
les réenvoyer — séparés en brouillons et devis déjà sortis (envoyés, acceptés,
…), avec le nombre de factures actives déjà émises (émises au total d'une
villa : un document légal, jamais réécrit ici).

``--dry-run`` est le défaut ET le seul mode : il n'existe aucun mode écriture.

    python manage.py lister_devis_multivilla [--company <slug>]
"""
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = ('ERR-QAC-MULTIVILLA-TOTAL-XN — liste (lecture seule) les devis ×N '
            'villas identiques : brouillons / devis sortis, total 1 villa vs ×N.')

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run', action='store_true', default=True,
            help='Défaut et seul mode : rien n\'est jamais écrit.')
        parser.add_argument(
            '--company', default=None,
            help='Slug de société (défaut : toutes les sociétés).')

    def handle(self, *args, **options):
        from apps.ventes.domain.argent import Vue, totaux
        from apps.ventes.models import Devis
        from apps.ventes.selectors import factures_du_devis, nombre_proprietes

        qs = (Devis.objects.filter(etude_params__has_key='nombre_proprietes')
              .select_related('company').order_by('company_id', 'reference'))
        if options.get('company'):
            qs = qs.filter(company__slug=options['company'])

        brouillons, sortis = [], []
        for devis in qs.iterator():
            n = nombre_proprietes(devis)
            if n <= 1:
                continue
            unite = totaux(devis, vue=Vue.NET, unitaire=True).ttc
            projet = totaux(devis, vue=Vue.NET).ttc
            nb_factures = factures_du_devis(devis).count()
            ligne = (f'{devis.company.slug:<20} {devis.reference:<22} '
                     f'{devis.statut:<10} N={n:<3} 1 villa={unite} MAD  '
                     f'×N={projet} MAD  factures actives={nb_factures}')
            (brouillons if devis.statut == Devis.Statut.BROUILLON
             else sortis).append(ligne)

        self.stdout.write('DRY-RUN (lecture seule) — aucune écriture.')
        self.stdout.write(f'Brouillons ×N : {len(brouillons)}')
        for ligne in brouillons:
            self.stdout.write(f'  {ligne}')
        self.stdout.write(f'Devis sortis ×N (envoyés/acceptés/…) : {len(sortis)}')
        for ligne in sortis:
            self.stdout.write(f'  {ligne}')
