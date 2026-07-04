from django.apps import AppConfig


class AuthenticationConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'authentication'
    verbose_name = 'Authentification'
    module_manifest = {
        'key': 'authentication',
        'label': 'Authentification',
        'icone': 'key',
        'depends': [],
        'installable': False,
        'description': 'Comptes, sociétés et authentification.',
        'categorie': 'Technique',
    }
