from django.apps import AppConfig


class CustomfieldsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.customfields'
    module_manifest = {
        'key': 'customfields',
        'label': 'Champs personnalisés',
        'icone': 'sliders',
        'depends': [],
        'installable': False,
        'description': 'Champs personnalisés par modèle.',
        'categorie': 'Technique',
    }

    def ready(self):
        # ARC31 — chargeur central unique : peuple le registre pilote
        # (contrats.contrat, flotte.vehicule…) depuis les manifestes
        # core.platform (surface customfield_models), à la place d'un
        # AppConfig.ready() par app pilote. Import différé (le registre lui-
        # même est déjà chargé — _register_native_modules() tourne à l'import
        # du module) pour éviter tout effet de bord au chargement des apps.
        from . import registry
        registry.register_from_platform_manifests()
