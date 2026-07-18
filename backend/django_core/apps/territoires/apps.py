from django.apps import AppConfig


class TerritoiresConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.territoires'
    verbose_name = 'Territoires commerciaux'
    module_manifest = {
        'key': 'territoires',
        'label': 'Territoires commerciaux',
        'icone': 'map',
        'depends': ['crm'],
        'description': "Règles d'affectation et rotation des leads par territoire.",
        'categorie': 'Ventes',
    }
