from django.apps import AppConfig


class CrmConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.crm'
    verbose_name = 'CRM'
    module_manifest = {
        'key': 'crm',
        'label': 'CRM',
        'icone': 'users',
        'depends': [],
        'description': 'Pistes, opportunités et clients.',
        'categorie': 'Ventes',
    }

    def ready(self):
        # M6 — abonne le CRM aux événements métier (core.events) : avance
        # l'étape du lead à l'acceptation d'un devis sans couplage direct.
        from . import receivers  # noqa: F401
        # AG6 — enregistre les actions agentiques CRM dans le registre AG1.
        from .agent_actions import register_crm_actions
        register_crm_actions()
        # XPLT23 — fournisseur DSR CRM (export/anonymisation loi 09-08).
        from . import dsr_provider
        dsr_provider.register()
        # QX42 — enregistre les politiques de rétention CRM dans le registre
        # partagé YOPSB10 (core.retention) : le framework existait, son
        # registre était VIDE (aucune app n'y enregistrait de politique).
        # Purge les WebsiteLeadPayload traités + les ChatSessionPublique
        # inactives au-delà de la fenêtre founder-configurable (défaut
        # 180 j) — les payloads en erreur/non traités restent exemptés
        # (voir services.purge_website_lead_payloads).
        from core.retention import register_retention_policy
        from .services import (
            purge_stale_chat_sessions, purge_website_lead_payloads,
        )
        register_retention_policy(
            'crm_website_lead_payloads', purge_website_lead_payloads)
        register_retention_policy(
            'crm_chat_sessions_publiques', purge_stale_chat_sessions)
