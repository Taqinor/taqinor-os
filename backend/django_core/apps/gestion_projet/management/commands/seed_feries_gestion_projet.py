"""Pré-remplit les jours fériés marocains de TOUS les calendriers (XPRJ20).

Source EXCLUSIVE : le référentiel calendrier UNIQUE ``core/calendar.py``
(``MOROCCAN_FIXED_HOLIDAYS`` + ``MOROCCAN_MOVABLE_HOLIDAYS`` de l'année
demandée) — voir ``services.seeder_feries_calendrier``. IDEMPOTENT : relancer
la commande plusieurs fois ne crée jamais de doublon
(``unique (calendrier, date)``).

Run (dans le conteneur django_core ou avec les variables DB) :
  python manage.py seed_feries_gestion_projet --annee 2026
  python manage.py seed_feries_gestion_projet --annee 2026 --company taqinor-demo
"""
from django.core.management.base import BaseCommand, CommandError

from apps.gestion_projet.models import CalendrierProjet
from apps.gestion_projet.services import seeder_feries_calendrier


class Command(BaseCommand):
    help = (
        "Pré-remplit les jours fériés marocains de tous les calendriers de "
        "projet pour une année (idempotent, source core/calendar.py)."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--annee', type=int, required=True,
            help='Année à pré-remplir (ex. 2026).',
        )
        parser.add_argument(
            '--company', default=None,
            help="Slug d'une seule société à traiter (défaut : toutes).",
        )

    def handle(self, *args, **options):
        from authentication.models import Company

        annee = options['annee']
        slug = options.get('company')
        calendriers = CalendrierProjet.objects.select_related(
            'company', 'projet')
        if slug:
            try:
                company = Company.objects.get(slug=slug)
            except Company.DoesNotExist:
                raise CommandError(f"Company with slug '{slug}' not found.")
            calendriers = calendriers.filter(company=company)

        total_crees = 0
        for calendrier in calendriers:
            resultat = seeder_feries_calendrier(calendrier, annee)
            total_crees += len(resultat['crees'])

        self.stdout.write(self.style.SUCCESS(
            f'Fériés {annee} pré-remplis sur {calendriers.count()} '
            f'calendrier(s) : {total_crees} jour(s) créé(s).'))
