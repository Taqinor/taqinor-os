"""Configuration de l'app « pos » — PARQUÉE (voir ``core.parked``)."""
from django.apps import AppConfig


class PosConfig(AppConfig):
    """Vente comptoir (POS) — app PARQUÉE du MVP solaire (20/09/2026).

    Coquille de migrations : plus aucun modèle, aucune url, aucune
    tâche, aucun écran. Le code complet est dans l'archive
    ``archive/full-erp-2026-09-20`` ; recette de retour : docs/parked-modules.md §5.

    L'app RESTE dans INSTALLED_APPS : c'est ce qui garde valide le
    graphe de migrations des apps gardées (jamais de squash).
    """

    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.pos'
    label = 'pos'
    verbose_name = 'Vente comptoir (POS)'
    # SOLMVP — marqueur lu par les gardes (core.parked.est_parquee).
    parked = True
    module_manifest = {
        'key': 'pos',
        'sku': 'optional',
        'label': 'Vente comptoir',
        'icone': 'shopping-cart',
        'depends': ['stock'],
        'description': 'Point de vente comptoir (accessoires).',
        'categorie': 'Ventes',
        'parked': True,
    }
