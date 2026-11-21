from django.apps import AppConfig


class AgentConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.agent'
    verbose_name = 'Agent (catalogue d\'actions agentiques)'
    module_manifest = {
        'key': 'agent',
        'sku': 'generic',
        'label': 'Agent',
        'icone': 'cpu',
        'depends': [],
        'description': "Catalogue d'actions agentiques.",
        'categorie': 'Technique',
    }

    def ready(self):
        # ARC33 — auto-découverte des actions agent : importe chaque module
        # ``agent_actions_module`` déclaré par un manifeste plateforme
        # (apps/<x>/platform.py, ARC28) et appelle sa ``register_actions()``
        # (convention idempotente). Déclarer le module dans le manifeste
        # SUFFIT désormais à brancher une app sur l'agent — plus besoin d'un
        # appel explicite dans son AppConfig.ready(). Import différé (aucun
        # effet de bord à l'import du module apps).
        from .registry import autodiscover_from_platform_manifests
        autodiscover_from_platform_manifests()

        # Décision fondateur 21/11/2026 — chaque appel IA de ``core.ai`` laisse
        # sa ligne ``UsageIA`` : on branche le puits ici (``core`` n'importe
        # jamais d'app ; ``ai_governance`` reste parquée). Idempotent.
        from core.ai.usage import register_usage_sink

        from .services import enregistrer_usage_ia
        register_usage_sink(enregistrer_usage_ia)
