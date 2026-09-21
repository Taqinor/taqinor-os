from django.apps import AppConfig


class DataqualityConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.dataquality'
    verbose_name = 'Qualité des données'
    module_manifest = {
        'key': 'dataquality',
        'sku': 'generic',
        'label': 'Qualité des données',
        'icone': 'shield-check',
        'depends': [],
        'installable': False,
        'description': 'Règles de validation, complétude et dédoublonnage.',
        'categorie': 'Technique',
    }
