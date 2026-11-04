from importlib import import_module

from django.apps import AppConfig


class GedConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.ged'
    verbose_name = 'Gestion documentaire (GED)'
    module_manifest = {
        'key': 'ged',
        'sku': 'generic',
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
        import_module(f'{self.name}.receivers')
        # ADOC193 — une version GED tient la clé de la pièce jointe importée
        # (migrate_attachments_to_ged) : registre des détenteurs de records.
        from django.conf import settings
        from apps.records.cles_stockage import enregistrer_detenteur
        enregistrer_detenteur('ged.DocumentVersion', 'file_key',
                              settings.MINIO_BUCKET_UPLOADS)
