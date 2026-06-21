from django.apps import AppConfig


class StockConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.stock'
    verbose_name = 'Gestion de Stock'

    def ready(self):
        # AG7 — enregistre les actions agentiques Stock dans le registre AG1.
        # Import local pour éviter les effets de bord à l'import du module et
        # contourner d'éventuels cycles d'import au démarrage.
        from .agent_actions import register_stock_actions
        register_stock_actions()
