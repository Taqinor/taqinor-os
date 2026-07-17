from django.apps import AppConfig


class AgricultureConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.agriculture'
    verbose_name = 'Agriculture'
    module_manifest = {
        'key': 'agriculture',
        'label': 'Agriculture',
        'icone': 'leaf',
        'depends': [],
        'description': (
            'Exploitations, parcelles, campagnes culturales, intrants et '
            'traçabilité phytosanitaire pour une exploitation ou coopérative '
            'agricole.'
        ),
        'categorie': 'Verticaux',
    }
