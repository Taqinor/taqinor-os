from django.apps import AppConfig


class AgentConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.agent'
    verbose_name = 'Agent (catalogue d\'actions agentiques)'
    module_manifest = {
        'key': 'agent',
        'label': 'Agent',
        'icone': 'cpu',
        'depends': [],
        'description': "Catalogue d'actions agentiques.",
        'categorie': 'Technique',
    }
