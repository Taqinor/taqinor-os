from django.apps import AppConfig


class EcommerceConnectConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.ecommerce_connect'
    verbose_name = 'Connecteur e-commerce'
    module_manifest = {
        'key': 'ecommerce_connect',
        'label': 'Connecteur e-commerce',
        'icone': 'shopping-bag',
        'depends': [],
        'installable': True,
        'description': (
            "Synchronisation catalogue/stock/commandes avec Shopify (NTRET18) "
            "et WooCommerce (NTRET19). Sans clé API en .env : intégration "
            "totalement no-op (aucun appel réseau)."
        ),
        'categorie': 'Technique',
    }
