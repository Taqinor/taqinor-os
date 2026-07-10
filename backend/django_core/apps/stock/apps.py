from django.apps import AppConfig


class StockConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.stock'
    verbose_name = 'Gestion de Stock'
    module_manifest = {
        'key': 'stock',
        'label': 'Stock',
        'icone': 'package',
        'depends': [],
        'description': 'Gestion des stocks, mouvements et fournisseurs.',
        'categorie': 'Stock',
    }

    def ready(self):
        # AG7 — enregistre les actions agentiques Stock dans le registre AG1.
        # Import local pour éviter les effets de bord à l'import du module et
        # contourner d'éventuels cycles d'import au démarrage.
        from .agent_actions import register_stock_actions
        register_stock_actions()
        # SCA20 — enregistre le hook de seed catalogue « nouvelle société »
        # (le signup seede désormais le catalogue produit). Idempotent.
        from .signup_hooks import register_stock_signup_hooks
        register_stock_signup_hooks()
        # ARC18 — miroir one-way stock.Fournisseur → répertoire unifié
        # tiers.Tiers (l'import câble le récepteur post_save ; pont réversible).
        from . import tiers_bridge  # noqa: F401
