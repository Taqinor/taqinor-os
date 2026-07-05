from django.apps import AppConfig


class ChatConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.chat'
    verbose_name = 'Messagerie interne (Discuss)'
    module_manifest = {
        'key': 'chat',
        'label': 'Messagerie',
        'icone': 'message-circle',
        'depends': [],
        'description': "Messagerie interne d'équipe (Discuss).",
        'categorie': 'Technique',
    }

    def ready(self):
        # S9 — branche les notifications (in-app + Web Push) sur l'envoi d'un
        # message. Import différé pour éviter les imports au chargement de l'app.
        from . import signals  # noqa: F401
