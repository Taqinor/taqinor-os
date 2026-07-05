from django.apps import AppConfig


class FlotteConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.flotte'
    verbose_name = 'Gestion de flotte'
    module_manifest = {
        'key': 'flotte',
        'label': 'Flotte',
        'icone': 'truck',
        'depends': [],
        'description': 'Véhicules, engins et maintenance interne.',
        'categorie': 'Services',
    }
