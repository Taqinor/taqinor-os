from django.apps import AppConfig


class SemanticConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.semantic'
    verbose_name = 'Couche sémantique'
    module_manifest = {
        'key': 'semantic',
        'sku': 'generic',
        'label': 'Métriques',
        'icone': 'ruler',
        'depends': [],
        'installable': False,
        'description': 'Métriques nommées et gouvernées (couche sémantique BI).',
        'categorie': 'Technique',
    }
