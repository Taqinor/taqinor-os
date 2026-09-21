"""Configuration de l'app « litiges » — PARQUÉE (voir ``core.parked``)."""
from django.apps import AppConfig


class LitigesConfig(AppConfig):
    """Réclamations & litiges — app PARQUÉE du MVP solaire (20/09/2026).

    Coquille de migrations : plus aucun modèle, aucune url, aucune
    tâche, aucun écran. Le code complet est dans l'archive
    ``archive/full-erp-2026-09-20`` ; recette de retour : docs/parked-modules.md §5.

    L'app RESTE dans INSTALLED_APPS : c'est ce qui garde valide le
    graphe de migrations des apps gardées (jamais de squash).
    """

    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.litiges'
    label = 'litiges'
    verbose_name = 'Réclamations & litiges'
    # SOLMVP — marqueur lu par les gardes (core.parked.est_parquee).
    parked = True
    module_manifest = {
        'key': 'litiges',
        'sku': 'generic',
        'label': 'Réclamations & litiges',
        'icone': 'alert-triangle',
        'depends': ['crm'],
        'description': 'Réclamations clients et litiges.',
        'categorie': 'Services',
        'parked': True,
    }
