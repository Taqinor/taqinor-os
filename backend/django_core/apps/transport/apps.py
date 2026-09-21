"""Configuration de l'app « transport » — PARQUÉE (voir ``core.parked``)."""
from django.apps import AppConfig


class TransportConfig(AppConfig):
    """Transport — app PARQUÉE du MVP solaire (20/09/2026).

    Coquille de migrations : plus aucun modèle, aucune url, aucune
    tâche, aucun écran. Le code complet est dans l'archive
    ``archive/full-erp-2026-09-20`` ; recette de retour : docs/parked-modules.md §5.

    L'app RESTE dans INSTALLED_APPS : c'est ce qui garde valide le
    graphe de migrations des apps gardées (jamais de squash).
    """

    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.transport'
    label = 'transport'
    verbose_name = 'Transport'
    # SOLMVP — marqueur lu par les gardes (core.parked.est_parquee).
    parked = True
    module_manifest = {
        'key': 'transport',
        'sku': 'optional',
        'label': 'Transport',
        'icone': 'truck',
        'depends': [],
        'installable': True,
        'description': "Ordres de transport (enlèvement/livraison/inter-site/import/export), étapes, comparateur d'affrètement, preuve de livraison, coûts de fret réels, litiges transporteur et émissions CO2 estimées.",
        'categorie': 'Stock',
        'parked': True,
    }
