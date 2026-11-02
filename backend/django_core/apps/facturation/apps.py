from django.apps import AppConfig


class FacturationConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.facturation'
    verbose_name = 'Facturation'
    module_manifest = {
        'key': 'facturation',
        'sku': 'solar_core',
        'label': 'Facturation',
        'icone': 'receipt',
        'depends': ['ventes', 'crm'],
        'description': (
            'Factures, paiements, avoirs et niveaux de relance — équivalent '
            'Odoo Invoicing, séparé de Sales (ODX17).'
        ),
        'categorie': 'Ventes',
    }

    def ready(self):
        # AMET4 — abonnés du bus M6 (acompte provisoire à l'acceptation,
        # retiré à la dés-acceptation). Import local, sans effet de bord.
        from . import receivers  # noqa: F401
