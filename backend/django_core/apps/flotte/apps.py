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

    # ARC14 déclarait Vehicule comme cible PILOTE des champs personnalisés
    # dans ready() (customfields.registry.register('vehicule', ...)). ARC31 a
    # basculé cette déclaration vers apps/flotte/platform.py
    # (customfield_models=['vehicule']) — un chargeur central unique
    # (apps/customfields/apps.py::CustomfieldsConfig.ready()) la lit
    # désormais depuis le manifeste ; ce AppConfig n'a plus besoin de ready().
