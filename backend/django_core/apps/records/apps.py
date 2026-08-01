from django.apps import AppConfig


class RecordsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.records'
    label = 'records'
    verbose_name = 'Activités & pièces jointes'
    module_manifest = {
        'key': 'records',
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
        from . import receivers  # noqa: F401
