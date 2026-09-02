from django.apps import AppConfig


class LitigesConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.litiges'
    verbose_name = 'Réclamations & litiges'
    module_manifest = {
        'key': 'litiges',
        'sku': 'generic',
        'label': 'Réclamations & litiges',
        'icone': 'alert-triangle',
        'depends': ['crm'],
        'description': 'Réclamations clients et litiges.',
        'categorie': 'Services',
    }
