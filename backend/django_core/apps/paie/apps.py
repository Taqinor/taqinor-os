from django.apps import AppConfig


class PaieConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.paie'
    verbose_name = 'Paie'
    module_manifest = {
        'key': 'paie',
        'label': 'Paie',
        'icone': 'banknote',
        'depends': ['rh'],
        'description': 'Paramètres CNSS/AMO/IR et bulletins.',
        'categorie': 'RH',
    }

    def ready(self):
        # YHIRE2 — abonne paie à l'événement métier employe_sorti (rh) :
        # coupe ProfilPaie.actif sans que paie importe rh directement ni
        # l'inverse (pattern M6, comme devis_accepted → crm).
        from . import receivers  # noqa: F401
