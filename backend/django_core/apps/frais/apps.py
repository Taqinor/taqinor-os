"""Configuration de l'app « frais » — PARQUÉE (voir ``core.parked``)."""
from django.apps import AppConfig


class FraisConfig(AppConfig):
    """Notes de frais — app PARQUÉE du MVP solaire (20/09/2026).

    Coquille de migrations : plus aucun modèle, aucune url, aucune
    tâche, aucun écran. Le code complet est dans l'archive
    ``archive/full-erp-2026-09-20`` ; recette de retour : docs/parked-modules.md §5.

    L'app RESTE dans INSTALLED_APPS : c'est ce qui garde valide le
    graphe de migrations des apps gardées (jamais de squash).
    """

    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.frais'
    label = 'frais'
    verbose_name = 'Notes de frais'
    # SOLMVP — marqueur lu par les gardes (core.parked.est_parquee).
    parked = True
    module_manifest = {
        'key': 'frais',
        'sku': 'generic',
        'label': 'Notes de frais',
        'icone': 'receipt',
        'depends': ['rh', 'compta'],
        'description': 'Notes de frais, rapports de frais, plafonds de politique, barèmes et indemnités kilométriques / per-diem chantier. La validation et le remboursement postent leurs écritures via apps.compta.services.',
        'categorie': 'Finance',
        'parked': True,
    }
