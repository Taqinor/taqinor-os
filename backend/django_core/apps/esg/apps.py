"""Configuration de l'app « esg » — PARQUÉE (voir ``core.parked``)."""
from django.apps import AppConfig


class EsgConfig(AppConfig):
    """ESG / RSE — app PARQUÉE du MVP solaire (20/09/2026).

    Coquille de migrations : plus aucun modèle, aucune url, aucune
    tâche, aucun écran. Le code complet est dans l'archive
    ``archive/full-erp-2026-09-20`` ; recette de retour : docs/parked-modules.md §5.

    L'app RESTE dans INSTALLED_APPS : c'est ce qui garde valide le
    graphe de migrations des apps gardées (jamais de squash).
    """

    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.esg'
    label = 'esg'
    verbose_name = 'ESG / RSE'
    # SOLMVP — marqueur lu par les gardes (core.parked.est_parquee).
    parked = True
    module_manifest = {
        'key': 'esg',
        'sku': 'generic',
        'label': 'ESG / RSE',
        'icone': 'leaf',
        'depends': ['qhse'],
        'description': "Reporting ESG/durabilité consolidé (périodes figées, agrégation cross-app, catalogue GRI-lite, rapports PDF/xlsx, trajectoires d'objectifs).",
        'categorie': 'Services',
        'parked': True,
    }
