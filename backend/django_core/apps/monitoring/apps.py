from django.apps import AppConfig


class MonitoringConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.monitoring'
    verbose_name = 'Monitoring (supervision production)'
    module_manifest = {
        'key': 'monitoring',
        'label': 'Supervision',
        'icone': 'activity',
        'depends': [],
        'description': 'Supervision de la production installée.',
        'categorie': 'Services',
    }

    def ready(self):
        # ARC36 — abonne l'arrêt de supervision automatique à l'événement
        # abonnement_monitoring_resilie (core.events, M6).
        from . import receivers  # noqa: F401
