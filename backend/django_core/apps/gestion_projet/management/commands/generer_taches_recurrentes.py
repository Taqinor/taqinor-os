"""Génère la prochaine ``Tache`` de chaque récurrence active à échéance (XPRJ13).

IDEMPOTENT : relancer la commande plusieurs fois le même jour ne crée jamais
deux occurrences pour la même échéance (voir
``services.generer_taches_recurrentes``). Pensé pour être exécuté à la
demande ou par un planificateur (cron / Celery beat).

Run (dans le conteneur django_core ou avec les variables DB) :
  python manage.py generer_taches_recurrentes                      # toutes sociétés
  python manage.py generer_taches_recurrentes --company taqinor-demo
"""
from django.core.management.base import BaseCommand, CommandError

from apps.gestion_projet.services import generer_taches_recurrentes


class Command(BaseCommand):
    help = (
        "Génère la prochaine tâche de chaque récurrence active à échéance, "
        "par société ou pour une seule --company (idempotent : jamais deux "
        "occurrences pour la même échéance)."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--company', default=None,
            help="Slug d'une seule société à traiter (défaut : toutes).",
        )

    def handle(self, *args, **options):
        from authentication.models import Company

        slug = options.get('company')
        if slug:
            try:
                companies = [Company.objects.get(slug=slug)]
            except Company.DoesNotExist:
                raise CommandError(f"Company with slug '{slug}' not found.")
        else:
            companies = list(Company.objects.all())

        if not companies:
            self.stdout.write(self.style.WARNING(
                'No company to process — nothing done.'))
            return

        total_crees = 0
        for company in companies:
            crees = generer_taches_recurrentes(company)
            total_crees += len(crees)

        self.stdout.write(self.style.SUCCESS(
            f'Tâches récurrentes générées sur {len(companies)} société(s) : '
            f'{total_crees} tâche(s) créée(s).'))
