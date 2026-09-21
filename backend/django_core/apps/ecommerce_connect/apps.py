"""Configuration de l'app « ecommerce_connect » — PARQUÉE (voir ``core.parked``)."""
from django.apps import AppConfig


class EcommerceConnectConfig(AppConfig):
    """Connecteur e-commerce — app PARQUÉE du MVP solaire (20/09/2026).

    Coquille de migrations : plus aucun modèle, aucune url, aucune
    tâche, aucun écran. Le code complet est dans l'archive
    ``archive/full-erp-2026-09-20`` ; recette de retour : docs/parked-modules.md §5.

    L'app RESTE dans INSTALLED_APPS : c'est ce qui garde valide le
    graphe de migrations des apps gardées (jamais de squash).
    """

    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.ecommerce_connect'
    label = 'ecommerce_connect'
    verbose_name = 'Connecteur e-commerce'
    # SOLMVP — marqueur lu par les gardes (core.parked.est_parquee).
    parked = True
    module_manifest = {
        'key': 'ecommerce_connect',
        'sku': 'vertical_ecommerce',
        'label': 'Connecteur e-commerce',
        'icone': 'shopping-bag',
        'depends': [],
        'installable': True,
        'description': 'Synchronisation catalogue/stock/commandes avec Shopify (NTRET18) et WooCommerce (NTRET19). Sans clé API en .env : intégration totalement no-op (aucun appel réseau).',
        'categorie': 'Technique',
        'parked': True,
    }
