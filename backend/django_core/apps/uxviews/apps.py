from django.apps import AppConfig


class UxviewsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.uxviews'
    module_manifest = {
        'key': 'uxviews',
        'label': 'Vues UX',
        'icone': 'layout-list',
        'depends': [],
        'installable': False,
        'description': 'Vues sauvegardées serveur (personnelles/partagées) — fondation NTUX.',
        'categorie': 'Technique',
    }
