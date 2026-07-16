from django.apps import AppConfig


class ComptaConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.compta'
    verbose_name = 'Comptabilité générale'
    module_manifest = {
        'key': 'compta',
        'label': 'Comptabilité',
        'icone': 'calculator',
        'depends': [],
        'description': 'Comptabilité générale CGNC et fiscalité.',
        'categorie': 'Finance',
    }

    def ready(self):
        # XMKT1 — abonne la sortie automatique des séquences de relance aux
        # événements devis_accepted/devis_refused (core.events, M6).
        from . import receivers  # noqa: F401
        # ARC19 — miroir one-way compta.Partenaire → répertoire unifié
        # tiers.Tiers (l'import câble le récepteur post_save ; pont réversible,
        # ODX13-compatible).
        from . import tiers_bridge  # noqa: F401
