from django.apps import AppConfig


class ImmobilierConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.immobilier'
    verbose_name = 'Immobilier'
    module_manifest = {
        'key': 'immobilier',
        'label': 'Immobilier',
        'icone': 'building',
        'depends': [],
        'description': (
            'Patrimoine, baux, quittancement et GMAO bâtiment pour '
            'foncières/syndics/facility managers.'
        ),
        'categorie': 'Services',
    }
