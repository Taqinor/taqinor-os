"""Configuration de l'app « veille_ao » — PARQUÉE (voir ``core.parked``)."""
from django.apps import AppConfig


class VeilleAoConfig(AppConfig):
    """Veille appels d'offres — app PARQUÉE du MVP solaire (20/09/2026).

    Coquille de migrations : plus aucun modèle, aucune url, aucune
    tâche, aucun écran. Le code complet est dans l'archive
    ``archive/full-erp-2026-09-20`` ; recette de retour : docs/parked-modules.md §5.

    L'app RESTE dans INSTALLED_APPS : c'est ce qui garde valide le
    graphe de migrations des apps gardées (jamais de squash).
    """

    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.veille_ao'
    label = 'veille_ao'
    verbose_name = "Veille appels d'offres"
    # SOLMVP — marqueur lu par les gardes (core.parked.est_parquee).
    parked = True
    module_manifest = {
        'key': 'veille_ao',
        'sku': 'solar_core',
        'label': "Veille appels d'offres",
        'icone': 'radar',
        'depends': ['ao'],
        'installable': True,
        'description': "Veille des avis de marché : le sas où atterrissent les avis collectés sur le portail public, signalés par un partenaire ou importés d'un fichier. Un humain trie ; les avis retenus deviennent des appels d'offres. Ne promet jamais l'exhaustivité.",
        'categorie': 'Commercial',
        'parked': True,
    }
