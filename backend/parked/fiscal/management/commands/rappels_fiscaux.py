"""NTMAR15 — Rappels d'échéance fiscale (in-app, best-effort, idempotent).

Notifie N jours avant chaque ``EcheanceFiscale`` à préparer, pour TOUTES les
sociétés. Idempotent (``EcheanceFiscale.rappel_envoye_le``) : relancer la
commande le même jour ne renotifie jamais. Appelable par Celery beat quand
disponible (patron ``compta.envoyer_rappels_j7``)."""
from django.core.management.base import BaseCommand

from authentication.models import Company

from apps.fiscal.services import envoyer_rappels_fiscaux


class Command(BaseCommand):
    help = (
        "NTMAR15 — notifie N jours avant chaque échéance fiscale à préparer "
        "(idempotent, toutes sociétés)."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--jours-avant', type=int, default=7,
            help="Horizon d'alerte en jours (défaut 7).")

    def handle(self, *args, **options):
        jours_avant = options['jours_avant']
        total = 0
        for company in Company.objects.all():
            notifiees = envoyer_rappels_fiscaux(company, jours_avant=jours_avant)
            total += len(notifiees)
        self.stdout.write(self.style.SUCCESS(
            f'{total} rappel(s) d\'échéance fiscale envoyé(s).'))
