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
