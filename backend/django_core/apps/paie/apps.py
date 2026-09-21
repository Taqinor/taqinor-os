"""Configuration de l'app « paie » — PARQUÉE (voir ``core.parked``)."""
from django.apps import AppConfig


class PaieConfig(AppConfig):
    """Paie — app PARQUÉE du MVP solaire (20/09/2026).

    Coquille de migrations : plus aucun modèle, aucune url, aucune
    tâche, aucun écran. Le code complet est dans l'archive
    ``archive/full-erp-2026-09-20`` ; recette de retour : docs/parked-modules.md §5.

    L'app RESTE dans INSTALLED_APPS : c'est ce qui garde valide le
    graphe de migrations des apps gardées (jamais de squash).
    """

    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.paie'
    label = 'paie'
    verbose_name = 'Paie'
    # SOLMVP — marqueur lu par les gardes (core.parked.est_parquee).
    parked = True
    module_manifest = {
        'key': 'paie',
        'sku': 'optional',
        'label': 'Paie',
        'icone': 'banknote',
        'depends': ['rh'],
        'description': 'Paramètres CNSS/AMO/IR et bulletins.',
        'categorie': 'RH',
        'parked': True,
    }
