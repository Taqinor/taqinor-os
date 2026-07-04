from django.apps import AppConfig


class NotificationsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.notifications'
    verbose_name = 'Notifications'
    module_manifest = {
        'key': 'notifications',
        'label': 'Notifications',
        'icone': 'bell',
        'depends': [],
        'description': 'Moteur de notifications unifié.',
        'categorie': 'Technique',
    }

    def ready(self):
        # ERR50 — câble les producteurs (LEAD_ASSIGNED / DEVIS_ACCEPTED) pour que
        # le moteur ne soit plus inerte sur les évènements métier.
        from . import signals
        signals.connect()
