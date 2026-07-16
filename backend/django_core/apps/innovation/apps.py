from django.apps import AppConfig


class InnovationConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.innovation'
    verbose_name = 'Innovation'
    module_manifest = {
        'key': 'innovation',
        'label': 'Innovation',
        'icone': 'lightbulb',
        'depends': [],
        'description': (
            "Boîte à idées interne, campagnes d'innovation ciblées et canal "
            'de feedback produit in-app.'),
        'categorie': 'Services',
    }
