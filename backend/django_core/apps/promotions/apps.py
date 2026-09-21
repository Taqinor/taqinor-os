"""Configuration de l'app « promotions » — PARQUÉE (voir ``core.parked``)."""
from django.apps import AppConfig


class PromotionsConfig(AppConfig):
    """Promotions panier — app PARQUÉE du MVP solaire (20/09/2026).

    Coquille de migrations : plus aucun modèle, aucune url, aucune
    tâche, aucun écran. Le code complet est dans l'archive
    ``archive/full-erp-2026-09-20`` ; recette de retour : docs/parked-modules.md §5.

    L'app RESTE dans INSTALLED_APPS : c'est ce qui garde valide le
    graphe de migrations des apps gardées (jamais de squash).
    """

    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.promotions'
    label = 'promotions'
    verbose_name = 'Promotions panier'
    # SOLMVP — marqueur lu par les gardes (core.parked.est_parquee).
    parked = True
    module_manifest = {
        'key': 'promotions',
        'sku': 'optional',
        'label': 'Promotions',
        'icone': 'percent',
        'depends': ['pos'],
        'description': 'Moteur de promotions panier (règles configurables), coupons à code unique, cartes cadeaux.',
        'categorie': 'Ventes',
        'parked': True,
    }
