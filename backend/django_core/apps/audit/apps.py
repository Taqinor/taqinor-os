from django.apps import AppConfig


class AuditConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.audit'
    label = 'audit'
    verbose_name = "Journal d'activité"

    def ready(self):
        from . import signals
        signals.connect()
