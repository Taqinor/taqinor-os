from django.apps import AppConfig


class GedConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.ged'
    verbose_name = 'Gestion documentaire (GED)'
    module_manifest = {
        'key': 'ged',
        'label': 'GED',
        'icone': 'folder',
        'depends': [],
        'description': 'Gestion électronique documentaire.',
        'categorie': 'Technique',
    }

    def ready(self):
        # ZGED6 — abonne ged aux événements métier (core.events) : centralise
        # les fichiers d'autres apps (paie/rh/sav/ventes…) selon les réglages
        # RoutageDocumentaire, sans jamais importer ces apps directement.
        from . import receivers  # noqa: F401
