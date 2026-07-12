from django.apps import AppConfig


class VoipConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.voip'
    verbose_name = 'Softphone VoIP'
    module_manifest = {
        'key': 'voip',
        'label': 'Téléphonie',
        'icone': 'phone-call',
        'depends': [],
        'description': (
            'Softphone intégré (SIP/WebRTC, gated) — appel navigateur, '
            'call-pop, journal automatique.'
        ),
        'categorie': 'Services',
    }
