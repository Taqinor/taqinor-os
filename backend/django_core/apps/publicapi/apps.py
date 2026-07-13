from django.apps import AppConfig


class PublicApiConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.publicapi'
    label = 'publicapi'
    verbose_name = 'API publique'
    module_manifest = {
        'key': 'publicapi',
        'label': 'API publique',
        'icone': 'globe',
        'depends': [],
        'installable': False,
        'description': 'Clés API et webhooks (géré par clés API).',
        'categorie': 'Technique',
    }

    def ready(self):
        # Branche les signaux qui déclenchent les webhooks sur les évènements
        # métier (nouveau lead, devis accepté, chantier clôturé, facture payée).
        from . import signals
        signals.connect()
        # YOPSB11 — archivage par lots du journal WebhookDelivery (registre
        # partagé YOPSB10). Fenêtre founder-configurable via
        # WEBHOOK_DELIVERY_ARCHIVE_DAYS (défaut 0 = OFF, comportement inchangé).
        from core.retention import register_retention_policy, setting_days
        from .services import (
            DEFAULT_WEBHOOK_DELIVERY_ARCHIVE_DAYS, archiver_anciens,
        )
        register_retention_policy(
            'publicapi_webhook_delivery_archive',
            lambda now, apply_: archiver_anciens(
                now,
                setting_days('WEBHOOK_DELIVERY_ARCHIVE_DAYS',
                             DEFAULT_WEBHOOK_DELIVERY_ARCHIVE_DAYS),
                apply_,
            ),
        )
