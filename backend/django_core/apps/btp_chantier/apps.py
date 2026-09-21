"""Configuration de l'app « btp_chantier » — PARQUÉE (voir ``core.parked``)."""
from django.apps import AppConfig


class BtpChantierConfig(AppConfig):
    """BTP / Chantier — app PARQUÉE du MVP solaire (20/09/2026).

    Coquille de migrations : plus aucun modèle, aucune url, aucune
    tâche, aucun écran. Le code complet est dans l'archive
    ``archive/full-erp-2026-09-20`` ; recette de retour : docs/parked-modules.md §5.

    L'app RESTE dans INSTALLED_APPS : c'est ce qui garde valide le
    graphe de migrations des apps gardées (jamais de squash).
    """

    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.btp_chantier'
    label = 'btp_chantier'
    verbose_name = 'BTP / Chantier'
    # SOLMVP — marqueur lu par les gardes (core.parked.est_parquee).
    parked = True
    module_manifest = {
        'key': 'btp_chantier',
        'sku': 'solar_core',
        'label': 'BTP Chantier',
        'icone': 'hard-hat',
        'depends': [],
        'description': 'Vertical BTP/EPC : réserves géo-localisées sur plan, RFI, visas de documents techniques, journal de chantier, avenants, DGD.',
        'categorie': 'Verticaux',
        'parked': True,
    }
