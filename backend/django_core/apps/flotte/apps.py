from django.apps import AppConfig


class FlotteConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.flotte'
    verbose_name = 'Gestion de flotte'
    module_manifest = {
        'key': 'flotte',
        'label': 'Flotte',
        'icone': 'truck',
        'depends': [],
        'description': 'Véhicules, engins et maintenance interne.',
        'categorie': 'Services',
    }

    def ready(self):
        # ARC14 — déclare Vehicule comme cible PILOTE des champs personnalisés
        # (customfields.registry, registre data-driven — jamais un import de
        # apps.customfields.models depuis ici, juste l'API de registre).
        from apps.customfields import registry
        registry.register('vehicule', 'flotte', 'Vehicule', label='Véhicule')
