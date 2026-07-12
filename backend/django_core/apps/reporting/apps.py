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
        # VX61 — enregistre la politique de rétention des Web Vitals dans le
        # registre partagé YOPSB10 (core.retention) : la table grossit vite
        # (une ligne par métrique par navigation).
        from core.retention import register_retention_policy
        from .services import purge_web_vitals
        register_retention_policy('reporting_web_vitals', purge_web_vitals)
