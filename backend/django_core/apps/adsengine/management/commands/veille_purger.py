"""VEIL19 — ``manage.py veille_purger --company <id> [--simulation]``.

Fin de contrat (Platform Terms §3.d.i) : efface TOUTES les données de veille
d'UNE société et affiche les comptes avant/après. Les autres sociétés ne sont
jamais touchées. ``--simulation`` : rien n'est supprimé, comptes exacts.
"""
from django.core.management.base import BaseCommand, CommandError

from authentication.models import Company

from apps.adsengine import veille_conservation


class Command(BaseCommand):
    help = ("Efface toutes les données de veille publicitaire d'une société "
            "(fin de contrat).")

    def add_arguments(self, parser):
        parser.add_argument('--company', type=int, required=True,
                            help='Identifiant de la société visée.')
        parser.add_argument('--simulation', action='store_true',
                            help='Compter sans rien supprimer.')

    def handle(self, *args, **options):
        company_id = options['company']
        if not Company.objects.filter(pk=company_id).exists():
            raise CommandError(f'Société introuvable : {company_id}.')
        resultat = veille_conservation.purger_societe(
            company_id, apply_=not options['simulation'])
        mode = 'SIMULATION' if options['simulation'] else 'RÉEL'
        self.stdout.write(f'veille_purger ({mode}) — société {company_id}')
        for cle, avant in resultat['avant'].items():
            self.stdout.write(
                f'  {cle} : {avant} → {resultat["apres"][cle]}')
        return None
