"""Configuration de l'app « innovation » — PARQUÉE (voir ``core.parked``)."""
from django.apps import AppConfig


class InnovationConfig(AppConfig):
    """Innovation — app PARQUÉE du MVP solaire (20/09/2026).

    Coquille de migrations : plus aucun modèle, aucune url, aucune
    tâche, aucun écran. Le code complet est dans l'archive
    ``archive/full-erp-2026-09-20`` ; recette de retour : docs/parked-modules.md §5.

    L'app RESTE dans INSTALLED_APPS : c'est ce qui garde valide le
    graphe de migrations des apps gardées (jamais de squash).
    """

    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.innovation'
    label = 'innovation'
    verbose_name = 'Innovation'
    # SOLMVP — marqueur lu par les gardes (core.parked.est_parquee).
    parked = True
    module_manifest = {
        'key': 'innovation',
        'sku': 'generic',
        'label': 'Innovation',
        'icone': 'lightbulb',
        'depends': [],
        'description': "Boîte à idées interne, campagnes d'innovation ciblées et canal de feedback produit in-app.",
        'categorie': 'Services',
        'parked': True,
    }
