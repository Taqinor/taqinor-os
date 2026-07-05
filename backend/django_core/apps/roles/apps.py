from django.apps import AppConfig


class RolesConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.roles'
    verbose_name = 'Gestion des Rôles'
    module_manifest = {
        'key': 'roles',
        'label': 'Rôles & permissions',
        'icone': 'lock',
        'depends': [],
        'installable': False,
        'description': 'Rôles et matrice de permissions.',
        'categorie': 'Technique',
    }
