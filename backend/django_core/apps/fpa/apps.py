from django.apps import AppConfig


class FpaConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.fpa'
    verbose_name = 'FP&A — Budgets & prévisions'
    module_manifest = {
        'key': 'fpa',
        'label': 'FP&A',
        'icone': 'line-chart',
        'depends': [],
        'description': (
            'Cycles budgétaires par département, prévisions glissantes, '
            'scénarios what-if et analyse des écarts (variance).'
        ),
        'categorie': 'Finance',
    }
