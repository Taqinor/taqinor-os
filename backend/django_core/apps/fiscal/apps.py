"""Configuration de l'app « fiscal » — PARQUÉE (voir ``core.parked``)."""
from django.apps import AppConfig


class FiscalConfig(AppConfig):
    """Conformité fiscale Maroc — app PARQUÉE du MVP solaire (20/09/2026).

    Coquille de migrations : plus aucun modèle, aucune url, aucune
    tâche, aucun écran. Le code complet est dans l'archive
    ``archive/full-erp-2026-09-20`` ; recette de retour : docs/parked-modules.md §5.

    L'app RESTE dans INSTALLED_APPS : c'est ce qui garde valide le
    graphe de migrations des apps gardées (jamais de squash).
    """

    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.fiscal'
    label = 'fiscal'
    verbose_name = 'Conformité fiscale Maroc'
    # SOLMVP — marqueur lu par les gardes (core.parked.est_parquee).
    parked = True
    module_manifest = {
        'key': 'fiscal',
        'sku': 'optional',
        'label': 'Conformité fiscale',
        'icone': 'calendar-check',
        'depends': [],
        'description': "Calendrier fiscal marocain complet par obligation (TVA/IS/IR/acomptes/timbre/RAS/CNSS/taxe professionnelle), rappels d'échéance, tableau de bord de conformité, attestations tenant avec expirations, registre UBO et veille réglementaire actionnable (Groupe NTMAR).",
        'categorie': 'Finance',
        'parked': True,
    }
