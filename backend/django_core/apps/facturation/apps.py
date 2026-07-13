from django.apps import AppConfig


class FacturationConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.facturation'
    verbose_name = 'Facturation'
    module_manifest = {
        'key': 'facturation',
        'label': 'Facturation',
        'icone': 'receipt',
        'depends': ['ventes', 'crm'],
        'description': (
            'Factures, paiements, avoirs et niveaux de relance — équivalent '
            'Odoo Invoicing, séparé de Sales (ODX17).'
        ),
        'categorie': 'Ventes',
    }
