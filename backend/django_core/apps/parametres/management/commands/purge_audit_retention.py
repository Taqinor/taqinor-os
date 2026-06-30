"""FG26 — commande de purge de rétention du journal d'audit (RGPD).

Purge, pour chaque société ayant fixé ``CompanyProfile.audit_retention_days``
(> 0), les lignes de journal au-delà de la fenêtre. Idempotent ; sans fenêtre,
rien n'est supprimé. Conçue pour un déclenchement planifié (Celery beat / cron).
"""
from django.core.management.base import BaseCommand

from apps.parametres.retention import purge_all_companies


class Command(BaseCommand):
    help = "Purge le journal d'audit au-delà de la fenêtre de rétention RGPD."

    def handle(self, *args, **options):
        result = purge_all_companies()
        self.stdout.write(self.style.SUCCESS(
            f"Purge terminée : {result['audit_deleted']} entrées d'audit, "
            f"{result['settings_deleted']} entrées de paramètres supprimées."))
