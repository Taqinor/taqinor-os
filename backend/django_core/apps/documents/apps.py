from django.apps import AppConfig


class DocumentsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.documents'
    label = 'documents'
    verbose_name = 'Documents après-vente'
    module_manifest = {
        'key': 'documents',
        'label': 'Documents après-vente',
        'icone': 'file',
        'depends': ['sav'],
        'description': 'Documents liés au parc et au SAV.',
        'categorie': 'Services',
    }
