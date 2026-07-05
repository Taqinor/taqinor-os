from django.apps import AppConfig


class SavConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.sav'
    verbose_name = 'Après-vente (parc équipements & SAV)'
    module_manifest = {
        'key': 'sav',
        'label': 'Après-vente',
        'icone': 'wrench',
        'depends': ['crm'],
        'description': 'Parc équipements clients, tickets SAV et O&M.',
        'categorie': 'Services',
    }

    def ready(self):
        # AG8 — enregistre les actions agentiques SAV dans le registre AG1.
        from . import agent_actions
        agent_actions.register_actions()
        # ZSAV7 — déclare le dataset BI `sav_tickets` (pivot/explorateur core).
        from . import bi_datasets
        bi_datasets.register_dataset()
        # YSUBS5 — abonne sav aux événements métier (core.events) : de-
        # provisioning de la maintenance liée à la résiliation d'un contrat.
        from . import receivers  # noqa: F401
        # ZMFG7 — abonne sav au bus e-mail entrant (core.email_intake,
        # FG373) : route un message reçu à l'alias d'une catégorie
        # d'équipement vers un ticket correctif pré-catégorisé.
        from .services import register_email_alias_handler
        register_email_alias_handler()
