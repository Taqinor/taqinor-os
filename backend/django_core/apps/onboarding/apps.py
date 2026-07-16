from django.apps import AppConfig


class OnboardingConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.onboarding'
    verbose_name = 'Onboarding produit'

    def ready(self):
        # NTDMO12 — abonne l'auto-complétion des items de checklist aux
        # événements métier (core.events), sans importer ventes/crm/stock.
        from . import receivers  # noqa: F401
