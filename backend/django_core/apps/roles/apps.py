from django.apps import AppConfig


class RolesConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.roles'
    verbose_name = 'Gestion des Rôles'
    module_manifest = {
        'key': 'roles',
        'sku': 'generic',
        'label': 'Rôles & permissions',
        'icone': 'lock',
        'depends': [],
        'installable': False,
        'description': 'Rôles et matrice de permissions.',
        'categorie': 'Technique',
    }

    def ready(self):
        # ASEC11-lint — injecte le registre module→codes dans la fondation
        # ``authentication.permissions`` (IsResponsableOrAdmin) : c'est la
        # fondation qui est APPELÉE, elle n'importe jamais apps.roles.
        from authentication.permissions import enregistrer_registre_modules

        from .permissions_registre import PERMISSION_MODULE
        enregistrer_registre_modules(PERMISSION_MODULE)
