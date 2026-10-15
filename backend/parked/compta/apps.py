from importlib import import_module

from django.apps import AppConfig


class ComptaConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.compta'
    verbose_name = 'Comptabilité générale'
    module_manifest = {
        'key': 'compta',
        'sku': 'generic',
        'label': 'Comptabilité',
        'icone': 'calculator',
        'depends': [],
        'description': 'Comptabilité générale CGNC et fiscalité.',
        'categorie': 'Finance',
    }

    def ready(self):
        # PACT161/XMKT1 — abonne l'inscription automatique aux séquences de
        # relance à l'événement lead_stage_changed (core.events, M6).
        import_module(f'{self.name}.receivers')
        # ARC19 — miroir one-way compta.Partenaire → répertoire unifié
        # tiers.Tiers (l'import câble le récepteur post_save ; pont réversible,
        # ODX13-compatible).
        import_module(f'{self.name}.tiers_bridge')
        # NTDATA11 — enregistre les adaptateurs de métrique (DSO, marge brute)
        # dans la couche sémantique. Le CALCUL reste ici (grand livre) ;
        # `semantic` ne connaît qu'une clé et une fonction.
        from .selectors import register_metric_adapters
        register_metric_adapters()
