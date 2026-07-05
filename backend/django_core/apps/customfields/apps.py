from django.apps import AppConfig


class CustomfieldsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.customfields'
    module_manifest = {
        'key': 'customfields',
        'label': 'Champs personnalisés',
        'icone': 'sliders',
        'depends': [],
        'installable': False,
        'description': 'Champs personnalisés par modèle.',
        'categorie': 'Technique',
    }
