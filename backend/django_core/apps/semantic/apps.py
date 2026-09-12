from django.apps import AppConfig


class SemanticConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.semantic'
    verbose_name = 'Couche sémantique'
    module_manifest = {
        'key': 'semantic',
        'sku': 'generic',
        'label': 'Métriques',
        'icone': 'ruler',
        'depends': [],
        'installable': False,
        'description': 'Métriques nommées et gouvernées (couche sémantique BI).',
        'categorie': 'Technique',
    }

    def ready(self):
        # NTDATA9 — le versionnage écoute les enregistrements de
        # `MetricDefinition` (API, admin, seeder, script : les quatre chemins
        # d'édition). Import LOCAL : `ready()` est le seul endroit où les
        # modèles sont chargés.
        from . import receivers  # noqa: F401

        # NTDATA34 — c'est SEMANTIC qui vient se brancher sur la fondation,
        # jamais l'inverse : `core` ne peut pas importer une app (contrat
        # import-linter `core-foundation-is-a-base-layer`). Même patron que le
        # registre de datasets de `core.data_explorer`.
        from core.dashboard_data import register_metric_resolver

        from .services import resolve_widget_metrique
        register_metric_resolver(resolve_widget_metrique)
