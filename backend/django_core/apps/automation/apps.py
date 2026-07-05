from django.apps import AppConfig


class AutomationConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.automation'
    label = 'automation'
    verbose_name = 'Automatisations'
    module_manifest = {
        'key': 'automation',
        'label': 'Automatisations',
        'icone': 'zap',
        'depends': [],
        'description': 'Règles et approbations sans code.',
        'categorie': 'Technique',
    }

    def ready(self):
        from . import signals
        signals.connect()
