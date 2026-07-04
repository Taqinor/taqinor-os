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
