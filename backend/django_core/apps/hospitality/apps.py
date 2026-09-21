"""Configuration de l'app « hospitality » — PARQUÉE (voir ``core.parked``)."""
from django.apps import AppConfig


class HospitalityConfig(AppConfig):
    """Hôtellerie & restauration — app PARQUÉE du MVP solaire (20/09/2026).

    Coquille de migrations : plus aucun modèle, aucune url, aucune
    tâche, aucun écran. Le code complet est dans l'archive
    ``archive/full-erp-2026-09-20`` ; recette de retour : docs/parked-modules.md §5.

    L'app RESTE dans INSTALLED_APPS : c'est ce qui garde valide le
    graphe de migrations des apps gardées (jamais de squash).
    """

    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.hospitality'
    label = 'hospitality'
    verbose_name = 'Hôtellerie & restauration'
    # SOLMVP — marqueur lu par les gardes (core.parked.est_parquee).
    parked = True
    module_manifest = {
        'key': 'hospitality',
        'sku': 'vertical_hospitality',
        'label': 'Hôtellerie',
        'icone': 'bed',
        'depends': [],
        'description': 'Plan des chambres, réservations, check-in/check-out, folio client unifié et housekeeping pour hôtel/riad.',
        'categorie': 'Verticaux',
        'parked': True,
    }
