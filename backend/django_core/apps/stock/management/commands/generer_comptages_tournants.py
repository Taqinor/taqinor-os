"""NTWMS13 — génère les sessions d'inventaire de comptage tournant DUES.

IDEMPOTENTE : rejouée le même jour elle ne recrée rien. Plannifiable par Celery
beat comme les autres jobs du module.

    python manage.py generer_comptages_tournants                # toutes sociétés
    python manage.py generer_comptages_tournants --company 3
    python manage.py generer_comptages_tournants --creer-plans  # amorce A/B/C
"""
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = ("Crée les sessions d'inventaire ciblées des classes ABC dont "
            "l'échéance de recomptage est atteinte (idempotent).")

    def add_arguments(self, parser):
        parser.add_argument(
            '--company', type=int, default=None,
            help='Limiter à une société (id). Défaut : toutes.')
        parser.add_argument(
            '--creer-plans', action='store_true',
            help='Amorce les plans A/B/C par défaut (30/90/180 j) avant de '
                 'générer. Idempotent : ne réécrit jamais une fréquence '
                 'déjà personnalisée.')

    def handle(self, *args, **options):
        from apps.stock.services import (
            assurer_plans_comptage_tournant, generer_comptages_tournants,
        )
        from authentication.models import Company

        company = None
        if options.get('company'):
            company = Company.objects.filter(id=options['company']).first()
            if company is None:
                self.stderr.write('Société introuvable.')
                return

        if options.get('creer_plans'):
            cibles = [company] if company else list(Company.objects.all())
            for cible in cibles:
                assurer_plans_comptage_tournant(cible)
            self.stdout.write(f'Plans A/B/C assurés pour {len(cibles)} '
                              f'société(s).')

        resultat = generer_comptages_tournants(company=company)
        self.stdout.write(
            f"{len(resultat['sessions'])} session(s) de comptage créée(s) "
            f"sur {resultat['plans_dus']} plan(s) dû(s).")
        for reference in resultat['sessions']:
            self.stdout.write(f'  - {reference}')
