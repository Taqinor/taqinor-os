"""Génère l'échéancier de loyer des baux actifs (NTPRO6).

Parcourt les ``Bail`` ``actif`` de chaque société (ou d'une seule ``--company``
slug) et matérialise leurs ``EcheanceLoyer`` manquantes via
``services.generer_echeancier``. IDEMPOTENT : la relancer ne duplique aucune
échéance déjà générée (unique_together bail + periode_debut).

Pensé pour être exécuté à la demande ou par un planificateur (cron / Celery
beat).

Run (dans le conteneur django_core ou avec les variables DB) :
  python manage.py generer_echeances_loyer
  python manage.py generer_echeances_loyer --company taqinor-demo
"""
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = (
        "Génère l'échéancier de loyer des baux actifs, par société ou pour "
        "une seule --company (idempotent)."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--company', default=None,
            help="Slug d'une seule société à traiter (défaut : toutes).",
        )

    def handle(self, *args, **options):
        from authentication.models import Company

        from apps.immobilier.models import Bail
        from apps.immobilier.services import generer_echeancier

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
        total_baux = 0
        for company in companies:
            baux = Bail.objects.filter(
                company=company, statut=Bail.Statut.ACTIF)
            for bail in baux:
                total_baux += 1
                creees = generer_echeancier(bail)
                total_creees += len(creees)

        self.stdout.write(self.style.SUCCESS(
            f"Échéancier généré pour {len(companies)} société(s), "
            f"{total_baux} bail(aux) actif(s) : "
            f"{total_creees} échéance(s) créée(s) "
            f"(échéances existantes laissées intactes)."))
