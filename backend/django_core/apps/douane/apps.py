"""Configuration de l'app « douane » — PARQUÉE (voir ``core.parked``)."""
from django.apps import AppConfig


class DouaneConfig(AppConfig):
    """Douane & Import-Export — app PARQUÉE du MVP solaire (20/09/2026).

    Coquille de migrations : plus aucun modèle, aucune url, aucune
    tâche, aucun écran. Le code complet est dans l'archive
    ``archive/full-erp-2026-09-20`` ; recette de retour : docs/parked-modules.md §5.

    L'app RESTE dans INSTALLED_APPS : c'est ce qui garde valide le
    graphe de migrations des apps gardées (jamais de squash).
    """

    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.douane'
    label = 'douane'
    verbose_name = 'Douane & Import-Export'
    # SOLMVP — marqueur lu par les gardes (core.parked.est_parquee).
    parked = True
    module_manifest = {
        'key': 'douane',
        'sku': 'optional',
        'label': 'Douane',
        'icone': 'ship',
        'depends': [],
        'installable': True,
        'description': "Dossiers d'export (incoterm, ports, pièces, statut douanier) — le volet import attend une réconciliation avec installations.DossierImport (FG315, NTLOG10 BLOCKED).",
        'categorie': 'Stock',
        'parked': True,
    }
