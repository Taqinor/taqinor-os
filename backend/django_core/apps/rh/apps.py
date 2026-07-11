from django.apps import AppConfig


class RhConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.rh'
    verbose_name = 'Ressources humaines'
    module_manifest = {
        'key': 'rh',
        'label': 'Ressources humaines',
        'icone': 'id-card',
        'depends': [],
        'description': 'Dossier employé, congés et présences.',
        'categorie': 'RH',
    }

    def ready(self):
        # XPLT23 — fournisseur DSR RH (export dossier ; effacement refusé —
        # obligations sociales/paie). Enregistré auprès du registre core.dsr.
        from . import dsr_provider
        dsr_provider.register()
        # ARC19 — miroir one-way (interne) rh.DossierEmploye → répertoire
        # unifié tiers.Tiers (l'import câble le récepteur post_save ; pas de
        # rôle commercial, pas de RIB — voir tiers_bridge).
        from . import tiers_bridge  # noqa: F401
