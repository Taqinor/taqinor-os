from django.apps import AppConfig


class AdminopsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.adminops'
    verbose_name = 'Administration enterprise (health score, sandbox, licences)'
    module_manifest = {
        'key': 'adminops',
        'label': 'Administration',
        'icone': 'shield-check',
        'depends': [],
        'description': (
            'Health score, sandbox, packages de configuration, adoption, '
            'annonces produit, diagnostic support (Groupe NTADM).'
        ),
        'categorie': 'Technique',
    }

    def ready(self):
        from . import receivers  # noqa: F401
