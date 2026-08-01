from django.apps import AppConfig


class TrashConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.trash'
    verbose_name = 'Corbeille'
    module_manifest = {
        'key': 'trash',
        'label': 'Corbeille',
        'icone': 'trash-2',
        'depends': [],
        'installable': False,
        'description': 'Corbeille transverse 30 jours (restauration + purge) — fondation NTUX.',
        'categorie': 'Technique',
    }

    def ready(self):
        # NTUX7 — abonnement au bus M6 : `apps.trash` réagit à
        # `record_soft_deleted` sans qu'aucune app métier ne l'importe.
        from . import receivers
        receivers.connect()
