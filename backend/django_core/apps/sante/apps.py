"""Configuration de l'app « sante » — PARQUÉE (voir ``core.parked``)."""
from django.apps import AppConfig


class SanteConfig(AppConfig):
    """Santé (cabinet/clinique) — app PARQUÉE du MVP solaire (20/09/2026).

    Coquille de migrations : plus aucun modèle, aucune url, aucune
    tâche, aucun écran. Le code complet est dans l'archive
    ``archive/full-erp-2026-09-20`` ; recette de retour : docs/parked-modules.md §5.

    L'app RESTE dans INSTALLED_APPS : c'est ce qui garde valide le
    graphe de migrations des apps gardées (jamais de squash).
    """

    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.sante'
    label = 'sante'
    verbose_name = 'Santé (cabinet/clinique)'
    # SOLMVP — marqueur lu par les gardes (core.parked.est_parquee).
    parked = True
    module_manifest = {
        'key': 'sante',
        'sku': 'vertical_sante',
        'label': 'Santé',
        'icone': 'stethoscope',
        'depends': [],
        'description': 'Agenda multi-praticiens, admission, nomenclature des actes, facturation patient/tiers payant pour cabinets et cliniques.',
        'categorie': 'Services',
        'parked': True,
    }
