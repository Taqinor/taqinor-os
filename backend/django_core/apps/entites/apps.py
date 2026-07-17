from django.apps import AppConfig


class EntitesConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.entites'
    verbose_name = 'Entités (structure organisationnelle intra-tenant)'
    module_manifest = {
        'key': 'entites',
        'label': 'Entités',
        'icone': 'network',
        'depends': [],
        'description': (
            'Hiérarchie d\'entités intra-tenant (holding/filiale/agence) — '
            'NTADM1, foundation d\'administration enterprise.'
        ),
        'categorie': 'Technique',
    }
