"""Configuration de l'app « assurances » — PARQUÉE (voir ``core.parked``)."""
from django.apps import AppConfig


class AssurancesConfig(AppConfig):
    """Assurances d'entreprise — app PARQUÉE du MVP solaire (20/09/2026).

    Coquille de migrations : plus aucun modèle, aucune url, aucune
    tâche, aucun écran. Le code complet est dans l'archive
    ``archive/full-erp-2026-09-20`` ; recette de retour : docs/parked-modules.md §5.

    L'app RESTE dans INSTALLED_APPS : c'est ce qui garde valide le
    graphe de migrations des apps gardées (jamais de squash).
    """

    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.assurances'
    label = 'assurances'
    verbose_name = "Assurances d'entreprise"
    # SOLMVP — marqueur lu par les gardes (core.parked.est_parquee).
    parked = True
    module_manifest = {
        'key': 'assurances',
        'sku': 'generic',
        'label': 'Assurances',
        'icone': 'shield',
        'depends': [],
        'description': "Registre des polices d'assurance d'entreprise (RC pro, décennale, multirisque, cyber, homme-clé), échéancier de primes, sinistres transverses (hors véhicule) et attestations d'assurance.",
        'categorie': 'Finance',
        'parked': True,
    }
