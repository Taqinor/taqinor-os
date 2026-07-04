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
