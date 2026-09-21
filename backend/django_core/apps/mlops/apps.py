"""Configuration de l'app « mlops » — PARQUÉE (voir ``core.parked``)."""
from django.apps import AppConfig


class MlopsConfig(AppConfig):
    """MLOps (scorers par tenant) — app PARQUÉE du MVP solaire (20/09/2026).

    Coquille de migrations : plus aucun modèle, aucune url, aucune
    tâche, aucun écran. Le code complet est dans l'archive
    ``archive/full-erp-2026-09-20`` ; recette de retour : docs/parked-modules.md §5.

    L'app RESTE dans INSTALLED_APPS : c'est ce qui garde valide le
    graphe de migrations des apps gardées (jamais de squash).
    """

    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.mlops'
    label = 'mlops'
    verbose_name = 'MLOps (scorers par tenant)'
    # SOLMVP — marqueur lu par les gardes (core.parked.est_parquee).
    parked = True
    module_manifest = {
        'key': 'mlops',
        'sku': 'generic',
        'label': 'MLOps (scorers par tenant)',
        'icone': 'cpu',
        'depends': [],
        'installable': False,
        'description': "Versionne par société les paramètres des scorers prédictifs (churn, probabilité de gain, retard de paiement…) et matérialise les signaux (features) qu'ils consomment.",
        'categorie': 'Technique',
        'parked': True,
    }
