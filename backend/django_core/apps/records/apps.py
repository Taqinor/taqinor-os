from importlib import import_module

from django.apps import AppConfig


class RecordsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.records'
    label = 'records'
    verbose_name = 'Activités & pièces jointes'
    module_manifest = {
        'key': 'records',
        'sku': 'generic',
        'label': 'Activités & pièces jointes',
        'icone': 'paperclip',
        'depends': [],
        'installable': False,
        'description': 'Chatter, activités et pièces jointes.',
        'categorie': 'Technique',
    }

    def ready(self):
        # ODY25 — journal d'installation des applications : `records` s'abonne
        # à `core.events.module_toggled` et écrit la bascule dans SON chatter
        # générique (ARC8). Import seul : le décorateur `@receiver` fait le
        # câblage, idempotent au rechargement grâce à son `dispatch_uid`.
        import_module(f'{self.name}.receivers')
        # ADOC193 — détenteur de clés du bucket uploads (registre append-only).
        from django.conf import settings
        from .cles_stockage import enregistrer_detenteur
        enregistrer_detenteur('records.Attachment', 'file_key',
                              settings.MINIO_BUCKET_UPLOADS)
