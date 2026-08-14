from django.apps import AppConfig


class TransportConfig(AppConfig):
    """NTLOG1 (Groupe SUPPLY) — ordres de transport, étapes, comparateur
    d'affrètement, coûts de fret réels, litiges transport, émissions CO2
    estimées. Nouvelle app greenfield, multi-société, entièrement additive.
    """

    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.transport'
    verbose_name = 'Transport'
    module_manifest = {
        'key': 'transport',
        'label': 'Transport',
        'icone': 'truck',
        'depends': [],
        'installable': True,
        'description': (
            "Ordres de transport (enlèvement/livraison/inter-site/import/"
            "export), étapes, comparateur d'affrètement, preuve de "
            "livraison, coûts de fret réels, litiges transporteur et "
            "émissions CO2 estimées."
        ),
        'categorie': 'Stock',
    }
