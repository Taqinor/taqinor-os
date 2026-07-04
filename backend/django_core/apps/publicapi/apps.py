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
