from django.apps import AppConfig


class FideliteConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.fidelite'
    verbose_name = 'Fidélité'
    module_manifest = {
        'key': 'fidelite',
        'label': 'Fidélité',
        'icone': 'star',
        'depends': [],
        'installable': True,
        'description': (
            "Programme de fidélité par points (gain automatique à la vente, "
            "paliers Bronze/Argent/Or, carte dématérialisée QR)."
        ),
        'categorie': 'Ventes',
    }

    def ready(self):
        # NTRET9 — abonne fidelite à core.events (crédit de points sur vente
        # validée), même patron que crm/apps.py (ready -> import receivers).
        from . import receivers  # noqa: F401
