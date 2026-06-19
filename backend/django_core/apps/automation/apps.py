from django.apps import AppConfig


class AutomationConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.automation'
    label = 'automation'
    verbose_name = 'Automatisations'

    def ready(self):
        from . import signals
        signals.connect()
