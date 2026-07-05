from django.apps import AppConfig


class RecordsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.records'
    label = 'records'
    verbose_name = 'Activités & pièces jointes'
    module_manifest = {
        'key': 'records',
        'label': 'Activités & pièces jointes',
        'icone': 'paperclip',
        'depends': [],
        'installable': False,
        'description': 'Chatter, activités et pièces jointes.',
        'categorie': 'Technique',
    }
