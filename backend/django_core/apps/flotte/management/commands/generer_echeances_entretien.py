"""Génère les échéances d'entretien dues depuis les plans (FLOTTE16).

Parcourt les ``PlanEntretien`` actifs de chaque société (ou d'une seule
``--company`` slug), calcule leur statut courant (km / date / heures) et
matérialise une ``EcheanceEntretien`` (statut ``a_faire``) pour chaque plan DUE
qui n'a pas déjà une échéance ouverte. La génération est IDEMPOTENTE : la relancer
ne duplique aucune échéance ouverte. Sauf ``--no-alerte``, une alerte best-effort
(``maintenance_due``) est diffusée pour chaque échéance nouvellement créée.

Pensé pour être exécuté à la demande ou par un planificateur (cron / Celery beat).

Run (dans le conteneur django_core ou avec les variables DB) :
  python manage.py generer_echeances_entretien                       # toutes
  python manage.py generer_echeances_entretien --company taqinor-demo  # une
  python manage.py generer_echeances_entretien --no-alerte             # sans alerte
"""
from django.core.management.base import BaseCommand, CommandError

from apps.flotte.services import generer_echeances_entretien


class Command(BaseCommand):
    help = (
        "Génère les échéances d'entretien dues depuis les plans actifs, par "
        "société ou pour une seule --company (idempotent ; --no-alerte pour ne "
        "pas diffuser d'alerte)."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--company', default=None,
            help="Slug d'une seule société à traiter (défaut : toutes).",
        )
        parser.add_argument(
            '--no-alerte', action='store_true', dest='no_alerte',
            help="Ne diffuse aucune alerte (génère seulement les échéances).",
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
                "No company to process — nothing done."))
            return

        alerter = not options.get('no_alerte')
        total_creees = 0
        for company in companies:
            resultat = generer_echeances_entretien(company, alerter=alerter)
            total_creees += resultat['nb_creees']

        self.stdout.write(self.style.SUCCESS(
            f"Échéances d'entretien générées pour {len(companies)} société(s) : "
            f"{total_creees} échéance(s) créée(s) "
            f"(échéances ouvertes existantes laissées intactes)."))
