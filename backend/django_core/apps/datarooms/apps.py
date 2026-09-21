"""Configuration de l'app « datarooms » — PARQUÉE (voir ``core.parked``)."""
from django.apps import AppConfig


class DataroomsConfig(AppConfig):
    """Salles de données — app PARQUÉE du MVP solaire (20/09/2026).

    Coquille de migrations : plus aucun modèle, aucune url, aucune
    tâche, aucun écran. Le code complet est dans l'archive
    ``archive/full-erp-2026-09-20`` ; recette de retour : docs/parked-modules.md §5.

    L'app RESTE dans INSTALLED_APPS : c'est ce qui garde valide le
    graphe de migrations des apps gardées (jamais de squash).
    """

    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.datarooms'
    label = 'datarooms'
    verbose_name = 'Salles de données'
    # SOLMVP — marqueur lu par les gardes (core.parked.est_parquee).
    parked = True
    module_manifest = {
        'key': 'datarooms',
        'sku': 'generic',
        'label': 'Salles de données',
        'icone': 'folder-lock',
        'depends': ['ged'],
        'description': 'Salles de données sécurisées : une collection thématique de documents GED ouverte à des viewers nommés, avec lien et expiration par personne, filigrane par viewer et journal de consultation.',
        'categorie': 'Services',
        'parked': True,
    }
