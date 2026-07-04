"""Génère les échéances récurrentes des contrats véhicule dus (XFLT2).

Parcourt les ``ContratVehicule`` (XFLT1) actifs sur une ``period`` donnée
(``'YYYY-MM'``, mois courant par défaut) de chaque société (ou d'une seule
``--company`` slug), et matérialise une ``EcheanceContrat`` par contrat dû.
La génération est IDEMPOTENTE : la relancer sur la même période ne duplique
aucune échéance.

Pensé pour être exécuté à la demande ou par un planificateur (cron / Celery
beat).

Run (dans le conteneur django_core ou avec les variables DB) :
  python manage.py generer_couts_contrats                          # mois courant, toutes sociétés
  python manage.py generer_couts_contrats --period 2026-07          # période explicite
  python manage.py generer_couts_contrats --company taqinor-demo    # une société
"""
import datetime

from django.core.management.base import BaseCommand, CommandError

from apps.flotte.services import generer_couts_contrat


class Command(BaseCommand):
    help = (
        "Génère les échéances récurrentes des contrats véhicule dus pour "
        "une période (défaut : mois courant), par société ou pour une seule "
        "--company (idempotent)."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--company', default=None,
            help="Slug d'une seule société à traiter (défaut : toutes).",
        )
        parser.add_argument(
            '--period', default=None,
            help="Période 'YYYY-MM' à générer (défaut : mois courant).",
        )

    def handle(self, *args, **options):
        from authentication.models import Company

        period = options.get('period') or datetime.date.today().strftime(
            '%Y-%m')

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

        total_creees = 0
        for company in companies:
            resultat = generer_couts_contrat(company, period)
            total_creees += resultat['nb_creees']

        self.stdout.write(self.style.SUCCESS(
            f"Échéances de contrat générées pour {len(companies)} société(s) "
            f"({period}) : {total_creees} échéance(s) créée(s) "
            f"(échéances déjà générées laissées intactes)."))
