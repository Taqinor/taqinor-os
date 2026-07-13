from django.apps import AppConfig


class AchatsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.achats'
    verbose_name = 'Achats'
    module_manifest = {
        'key': 'achats',
        'label': 'Achats',
        'icone': 'shopping-cart',
        'depends': ['stock'],
        'description': (
            'Bons de commande fournisseur, réceptions, factures et paiements '
            'fournisseur, retours fournisseur (équivalent Odoo Purchase).'
        ),
        'categorie': 'Stock',
    }
