from django.apps import AppConfig


class PublicApiConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.publicapi'
    label = 'publicapi'
    verbose_name = 'API publique'

    def ready(self):
        # Branche les signaux qui déclenchent les webhooks sur les évènements
        # métier (nouveau lead, devis accepté, chantier clôturé, facture payée).
        from . import signals
        signals.connect()
