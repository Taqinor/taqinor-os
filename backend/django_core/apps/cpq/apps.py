from django.apps import AppConfig


class CpqConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.cpq'
    verbose_name = 'CPQ'
    module_manifest = {
        'key': 'cpq',
        'label': 'CPQ',
        'icone': 'sliders',
        'depends': [],
        'description': 'Configuration, prix et devis (CPQ enterprise).',
        'categorie': 'Ventes',
    }

    def ready(self):
        # NTCPQ11 — fige les clauses/CGV applicables au moment de l'envoi du
        # devis (événement métier découplé core.events.devis_sent). cpq
        # s'abonne ici sans coupler ventes à cpq (miroir du récepteur CRM).
        from . import receivers  # noqa: F401
