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
