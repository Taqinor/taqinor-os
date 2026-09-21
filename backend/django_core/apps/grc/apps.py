"""Configuration de l'app « grc » — PARQUÉE (voir ``core.parked``)."""
from django.apps import AppConfig


class GrcConfig(AppConfig):
    """GRC & Conformité — app PARQUÉE du MVP solaire (20/09/2026).

    Coquille de migrations : plus aucun modèle, aucune url, aucune
    tâche, aucun écran. Le code complet est dans l'archive
    ``archive/full-erp-2026-09-20`` ; recette de retour : docs/parked-modules.md §5.

    L'app RESTE dans INSTALLED_APPS : c'est ce qui garde valide le
    graphe de migrations des apps gardées (jamais de squash).
    """

    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.grc'
    label = 'grc'
    verbose_name = 'GRC & Conformité'
    # SOLMVP — marqueur lu par les gardes (core.parked.est_parquee).
    parked = True
    module_manifest = {
        'key': 'grc',
        'sku': 'generic',
        'label': 'GRC & Conformité',
        'icone': 'shield-check',
        'depends': [],
        'installable': True,
        'description': 'Gouvernance, risques et conformité : registre des risques, contrôles internes, RGPD/loi 09-08 outillé, rétention et journal de destruction.',
        'categorie': 'Technique',
        'parked': True,
    }
