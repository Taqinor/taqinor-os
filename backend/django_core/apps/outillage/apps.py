from django.apps import AppConfig


class OutillageConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.outillage'
    verbose_name = 'Outillage'
    module_manifest = {
        'key': 'outillage',
        'label': 'Outillage',
        'icone': 'tool',
        'depends': [],
        'description': "Parc d'outillage et prêts.",
        'categorie': 'Services',
    }
