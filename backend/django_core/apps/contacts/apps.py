"""Configuration de l'app « contacts » — PARQUÉE (voir ``core.parked``)."""
from django.apps import AppConfig


class ContactsConfig(AppConfig):
    """Contacts multi-rôles — app PARQUÉE du MVP solaire (20/09/2026).

    Coquille de migrations : plus aucun modèle, aucune url, aucune
    tâche, aucun écran. Le code complet est dans l'archive
    ``archive/full-erp-2026-09-20`` ; recette de retour : docs/parked-modules.md §5.

    L'app RESTE dans INSTALLED_APPS : c'est ce qui garde valide le
    graphe de migrations des apps gardées (jamais de squash).
    """

    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.contacts'
    label = 'contacts'
    verbose_name = 'Contacts multi-rôles'
    # SOLMVP — marqueur lu par les gardes (core.parked.est_parquee).
    parked = True
    module_manifest = {
        'key': 'contacts',
        'sku': 'generic',
        'label': 'Contacts multi-rôles',
        'icone': 'address-book',
        'depends': ['crm'],
        'description': "Organigramme d'achat multi-rôles par client.",
        'categorie': 'Ventes',
        'parked': True,
    }
