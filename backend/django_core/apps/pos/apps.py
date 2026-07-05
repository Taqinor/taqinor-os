from django.apps import AppConfig


class PosConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.pos'
    verbose_name = 'Vente comptoir (POS)'
    module_manifest = {
        'key': 'pos',
        'label': 'Vente comptoir',
        'icone': 'shopping-cart',
        'depends': ['stock'],
        'description': 'Point de vente comptoir (accessoires).',
        'categorie': 'Ventes',
    }
