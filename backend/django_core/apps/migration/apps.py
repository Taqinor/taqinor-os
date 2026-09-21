"""Configuration de l'app « migration » — PARQUÉE (voir ``core.parked``)."""
from django.apps import AppConfig


class MigrationConfig(AppConfig):
    """Migration ERP (Odoo/Sage/Excel) — app PARQUÉE du MVP solaire (20/09/2026).

    Coquille de migrations : plus aucun modèle, aucune url, aucune
    tâche, aucun écran. Le code complet est dans l'archive
    ``archive/full-erp-2026-09-20`` ; recette de retour : docs/parked-modules.md §5.

    L'app RESTE dans INSTALLED_APPS : c'est ce qui garde valide le
    graphe de migrations des apps gardées (jamais de squash).
    """

    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.migration'
    label = 'migration'
    verbose_name = 'Migration ERP (Odoo/Sage/Excel)'
    # SOLMVP — marqueur lu par les gardes (core.parked.est_parquee).
    parked = True
    module_manifest = {
        'key': 'migration',
        'sku': 'generic',
        'label': 'Migration',
        'icone': 'database',
        'depends': [],
        'description': 'Projets de migration ERP sortants (Odoo/Sage/Excel) avec rapport de réconciliation obligatoire : comptages et totaux source vs cible avant toute clôture.',
        'categorie': 'Technique',
        'parked': True,
    }
