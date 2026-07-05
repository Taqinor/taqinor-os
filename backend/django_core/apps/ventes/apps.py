from django.apps import AppConfig


class VentesConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.ventes'
    verbose_name = 'Ventes'
    module_manifest = {
        'key': 'ventes',
        'label': 'Ventes',
        'icone': 'file-text',
        'depends': ['crm'],
        'description': 'Devis, bons de commande et facturation.',
        'categorie': 'Ventes',
    }

    def ready(self):
        # AG4/AG5 — enregistre les actions agentiques Ventes (flux devis →
        # facture → encaissement) dans le registre AG1. Import local pour
        # éviter les effets de bord à l'import et d'éventuels cycles au
        # démarrage. Idempotent si ready() est appelé plusieurs fois.
        from .agent_actions import register_ventes_actions
        register_ventes_actions()
        # YLEDG12 — abonne ventes à `payment_captured` (core FG370) : câble
        # les récepteurs du bus d'événements (M6). Import local, jamais
        # d'effet de bord à l'import du module.
        from . import receivers  # noqa: F401
