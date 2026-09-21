"""Configuration de l'app « juridique » — PARQUÉE (voir ``core.parked``)."""
from django.apps import AppConfig


class JuridiqueConfig(AppConfig):
    """Affaires juridiques — app PARQUÉE du MVP solaire (20/09/2026).

    Coquille de migrations : plus aucun modèle, aucune url, aucune
    tâche, aucun écran. Le code complet est dans l'archive
    ``archive/full-erp-2026-09-20`` ; recette de retour : docs/parked-modules.md §5.

    L'app RESTE dans INSTALLED_APPS : c'est ce qui garde valide le
    graphe de migrations des apps gardées (jamais de squash).
    """

    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.juridique'
    label = 'juridique'
    verbose_name = 'Affaires juridiques'
    # SOLMVP — marqueur lu par les gardes (core.parked.est_parquee).
    parked = True
    module_manifest = {
        'key': 'juridique',
        'sku': 'generic',
        'label': 'Juridique',
        'icone': 'scale',
        'depends': [],
        'description': "Dossiers juridiques (contentieux, précontentieux, consultatif, recouvrement) : parties, audiences, délais de prescription, cabinets d'avocats et honoraires, budget et provisions proposées.",
        'categorie': 'Services',
        'parked': True,
    }
