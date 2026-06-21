from django.apps import AppConfig


class InstallationsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.installations'
    verbose_name = 'Chantiers / Installations'

    def ready(self):
        # AG9 — enregistre les actions agentiques de l'app dans le registre AG1
        # (import function-local pour éviter les cycles au chargement des apps).
        from .agent_actions import register_installation_actions
        register_installation_actions()
