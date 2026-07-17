from django.apps import AppConfig


class CreditConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.credit'
    verbose_name = 'Gestion du crédit client'
    module_manifest = {
        'key': 'credit',
        'label': 'Crédit client',
        'icone': 'shield-check',
        'depends': [],
        'description': (
            'Limite de crédit, credit hold, scoring et assurance-crédit '
            'client (NTCRD).'
        ),
        'categorie': 'Ventes',
    }

    def ready(self):
        # NTCRD9/31/33/34 — abonne les récepteurs internes (best-effort,
        # jamais bloquant) une fois l'app chargée.
        from . import receivers  # noqa: F401
