"""Configuration de l'app « ai_governance » — PARQUÉE (voir ``core.parked``)."""
from django.apps import AppConfig


class AiGovernanceConfig(AppConfig):
    """Gouvernance IA — app PARQUÉE du MVP solaire (20/09/2026).

    Coquille de migrations : plus aucun modèle, aucune url, aucune
    tâche, aucun écran. Le code complet est dans l'archive
    ``archive/full-erp-2026-09-20`` ; recette de retour : docs/parked-modules.md §5.

    L'app RESTE dans INSTALLED_APPS : c'est ce qui garde valide le
    graphe de migrations des apps gardées (jamais de squash).
    """

    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.ai_governance'
    label = 'ai_governance'
    verbose_name = 'Gouvernance IA'
    # SOLMVP — marqueur lu par les gardes (core.parked.est_parquee).
    parked = True
    module_manifest = {
        'key': 'ai_governance',
        'sku': 'generic',
        'label': 'Gouvernance IA',
        'icone': 'cpu',
        'depends': [],
        'installable': True,
        'description': 'Copilotes IA contextuels (brouillons, comptes rendus, descriptions) et surveillance des modèles — sans clé, tout dégrade proprement.',
        'categorie': 'Technique',
        'parked': True,
    }
