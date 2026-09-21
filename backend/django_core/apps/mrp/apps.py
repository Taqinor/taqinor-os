"""Configuration de l'app « mrp » — PARQUÉE (voir ``core.parked``)."""
from django.apps import AppConfig


class MrpConfig(AppConfig):
    """Production (MRP) — app PARQUÉE du MVP solaire (20/09/2026).

    Coquille de migrations : plus aucun modèle, aucune url, aucune
    tâche, aucun écran. Le code complet est dans l'archive
    ``archive/full-erp-2026-09-20`` ; recette de retour : docs/parked-modules.md §5.

    L'app RESTE dans INSTALLED_APPS : c'est ce qui garde valide le
    graphe de migrations des apps gardées (jamais de squash).
    """

    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.mrp'
    label = 'mrp'
    verbose_name = 'Production (MRP)'
    # SOLMVP — marqueur lu par les gardes (core.parked.est_parquee).
    parked = True
    module_manifest = {
        'key': 'mrp',
        'sku': 'vertical_manufacturing',
        'label': 'Production (MRP)',
        'icone': 'wrench',
        'depends': [],
        'installable': True,
        'description': 'Postes de charge, gammes opératoires, ordres de fabrication capacitaires, calcul des besoins nets (MRP), ordonnancement à capacité finie, terminal atelier et coût de revient standard (Groupe NTMFG).',
        'categorie': 'Stock',
        'parked': True,
    }
