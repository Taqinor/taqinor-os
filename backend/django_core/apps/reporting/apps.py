from django.apps import AppConfig


class ReportingConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.reporting'
    verbose_name = 'Reporting'
    module_manifest = {
        'key': 'reporting',
        'label': 'Rapports',
        'icone': 'bar-chart',
        'depends': [],
        'description': 'Tableaux de bord et rapports.',
        'categorie': 'Technique',
    }

    def ready(self):
        # VX61 — enregistre la purge des VitalMetric (Web Vitals réels) dans
        # le registre de rétention partagé YOPSB10 (croissance rapide : une
        # ligne par métrique par navigation).
        from core.retention import register_retention_policy
        from .vitals import purge_vital_metrics
        register_retention_policy('reporting_vital_metrics', purge_vital_metrics)
