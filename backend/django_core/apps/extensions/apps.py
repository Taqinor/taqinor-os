from django.apps import AppConfig


class ExtensionsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.extensions'
    verbose_name = "Marketplace d'extensions"

    module_manifest = {
        'key': 'extensions',
        'label': 'Extensions',
        'icone': 'puzzle',
        'depends': [],
        'description': (
            "Catalogue global (lecture seule) de packages d'extension "
            "no-code installables sur un tenant."),
        'categorie': 'Plateforme',
    }
