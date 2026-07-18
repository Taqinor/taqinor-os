from django.apps import AppConfig


class OnboardingConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.onboarding'
    verbose_name = 'Onboarding produit'
    module_manifest = {
        'key': 'onboarding',
        'label': 'Onboarding produit',
        'icone': 'check-circle',
        'depends': [],
        'description': 'Checklist « Premiers pas » et avancement utilisateur.',
        'categorie': 'Technique',
    }

    def ready(self):
        # NTDMO12 — abonne l'auto-complétion des items de checklist aux
        # événements métier (core.events), sans importer ventes/crm/stock.
        from . import receivers  # noqa: F401
