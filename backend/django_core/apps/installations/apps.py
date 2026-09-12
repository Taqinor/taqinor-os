from django.apps import AppConfig


class InstallationsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.installations'
    verbose_name = 'Chantiers / Installations'
    module_manifest = {
        'key': 'installations',
        'sku': 'solar_core',
        'label': 'Chantiers',
        'icone': 'hard-hat',
        'depends': ['ventes'],
        'description': 'Installations et interventions terrain.',
        'categorie': 'Services',
    }

    def ready(self):
        # M6 — abonne Installations aux événements métier (core.events) : crée
        # automatiquement le chantier à l'acceptation d'un devis, sans couplage
        # direct ventes → installations (import local pour éviter les cycles).
        from . import receivers  # noqa: F401
        # AG9 — enregistre les actions agentiques de l'app dans le registre AG1
        # (import function-local pour éviter les cycles au chargement des apps).
        from .agent_actions import register_installation_actions
        register_installation_actions()
        # NTDATA4 — déclare le dataset BI `chantiers` dans `core.data_explorer`
        # (l'app propriétaire déclare, le noyau exécute). Idempotent.
        from . import bi_datasets
        bi_datasets.register_dataset()
