"""ACEL73 — Déclenche à la main la tâche ``adsengine.emit_capi_signatures``.

    python manage.py emit_capi_signatures

Pousse au CRM Dataset Meta les événements « lead reçu » / « contrat signé »
(idempotents, marqueurs ``CapiOdooEvent`` tenus par ``capi_odoo``). La tâche
n'est plus au planning (synchro Odoo MANUELLE, AACQ97) : sans configuration
(``CAPI_CRM_DATASET_ID`` + jeton) aucun appel réseau n'est fait.
"""
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = ("Émet à la main les événements CAPI « lead reçu » / « contrat "
            "signé » (no-op sans CRM Dataset configuré).")

    def handle(self, *args, **options):
        from apps.adsengine.tasks import emit_capi_signatures

        result = emit_capi_signatures()
        if not result['configured']:
            self.stdout.write("CRM Dataset non configuré — rien émis.")
            return
        self.stdout.write(
            f"{result['received']} reçu(s), {result['signed']} signé(s)")
