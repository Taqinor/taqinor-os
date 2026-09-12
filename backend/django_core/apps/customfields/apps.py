from django.apps import AppConfig


class CustomfieldsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.customfields'
    module_manifest = {
        'key': 'customfields',
        'sku': 'generic',
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
        # NTEXT21 — contenu d'un onglet custom 'objet_custom_lie' (bouton/
        # onglet UI déclaratifs, core.ui_extensions) : même patron de
        # registre que registry.py ci-dessus, mais pour ``core`` (aucune app
        # métier n'y est importée).
        from core.ui_extensions import register_onglet_resolver
        from .services import resoudre_objet_custom_lie
        register_onglet_resolver('objet_custom_lie', resoudre_objet_custom_lie)
