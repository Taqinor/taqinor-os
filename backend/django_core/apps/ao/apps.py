"""Configuration de l'app « ao » — PARQUÉE (voir ``core.parked``)."""
from django.apps import AppConfig


class AoConfig(AppConfig):
    """Appels d'offres (marchés publics/privés) — app PARQUÉE du MVP solaire (20/09/2026).

    Coquille de migrations : plus aucun modèle, aucune url, aucune
    tâche, aucun écran. Le code complet est dans l'archive
    ``archive/full-erp-2026-09-20`` ; recette de retour : docs/parked-modules.md §5.

    L'app RESTE dans INSTALLED_APPS : c'est ce qui garde valide le
    graphe de migrations des apps gardées (jamais de squash).
    """

    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.ao'
    label = 'ao'
    verbose_name = "Appels d'offres (marchés publics/privés)"
    # SOLMVP — marqueur lu par les gardes (core.parked.est_parquee).
    parked = True
    module_manifest = {
        'key': 'ao',
        'sku': 'solar_core',
        'label': "Appels d'offres",
        'icone': 'gavel',
        'depends': ['crm', 'ventes'],
        'description': "Gestion des appels d'offres publics/privés : bordereaux de prix (BOQ), cautions/garanties de soumission, dossier administratif, échéancier de deadlines et analyse gagné/perdu.",
        'categorie': 'Commercial',
        'parked': True,
    }
