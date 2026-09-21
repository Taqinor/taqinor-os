"""Configuration de l'app « scm » — PARQUÉE (voir ``core.parked``)."""
from django.apps import AppConfig


class ScmConfig(AppConfig):
    """Planification supply chain — app PARQUÉE du MVP solaire (20/09/2026).

    Coquille de migrations : plus aucun modèle, aucune url, aucune
    tâche, aucun écran. Le code complet est dans l'archive
    ``archive/full-erp-2026-09-20`` ; recette de retour : docs/parked-modules.md §5.

    L'app RESTE dans INSTALLED_APPS : c'est ce qui garde valide le
    graphe de migrations des apps gardées (jamais de squash).
    """

    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.scm'
    label = 'scm'
    verbose_name = 'Planification supply chain'
    # SOLMVP — marqueur lu par les gardes (core.parked.est_parquee).
    parked = True
    module_manifest = {
        'key': 'scm',
        'sku': 'optional',
        'label': 'Planification supply chain',
        'icone': 'trending-up',
        'depends': ['stock'],
        'installable': True,
        'description': "Prévision de demande saisonnière, événements d'impact, classification ABC, politiques de stock (ROP/stock de sécurité au niveau de service), tableau de bord de réappro consolidé et cycle S&OP mensuel (demande/offre/finance).",
        'categorie': 'Stock',
        'parked': True,
    }
