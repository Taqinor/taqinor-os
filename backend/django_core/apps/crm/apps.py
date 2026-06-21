from django.apps import AppConfig


class CrmConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.crm'
    verbose_name = 'CRM'

    def ready(self):
        # M6 — abonne le CRM aux événements métier (core.events) : avance
        # l'étape du lead à l'acceptation d'un devis sans couplage direct.
        from . import receivers  # noqa: F401
        # AG6 — enregistre les actions agentiques CRM dans le registre AG1.
        from .agent_actions import register_crm_actions
        register_crm_actions()
