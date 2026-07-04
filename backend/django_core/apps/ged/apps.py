from django.apps import AppConfig


class GedConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.ged'
    verbose_name = 'Gestion documentaire (GED)'
    module_manifest = {
        'key': 'ged',
        'label': 'GED',
        'icone': 'folder',
        'depends': [],
        'description': 'Gestion électronique documentaire.',
        'categorie': 'Technique',
    }
