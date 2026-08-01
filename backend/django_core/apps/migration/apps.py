from django.apps import AppConfig


class MigrationConfig(AppConfig):
    """Groupe NTMIG — Kits de migration ERP sortants (Odoo/Sage/Excel).

    App CONTENEUR des projets de migration (regroupement de lots par entité),
    du rapport de réconciliation obligatoire et de l'outillage
    d'implémentation. Le chargement effectif des données est TOUJOURS DÉLÉGUÉ
    au moteur ``apps.dataimport`` (dry-run/commit/ExternalRef/ImportJob) —
    jamais un second importateur, jamais un second journal. Multi-société,
    additive, société forcée côté serveur ; aucune écriture SQL vers Odoo
    (règle #1 — JSON-2 en lecture seule ou fichier, rien d'autre).
    """

    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.migration'
    verbose_name = 'Migration ERP (Odoo/Sage/Excel)'

    module_manifest = {
        'key': 'migration',
        'label': 'Migration',
        'icone': 'database',
        'depends': [],
        'description': (
            'Projets de migration ERP sortants (Odoo/Sage/Excel) avec '
            'rapport de réconciliation obligatoire : comptages et totaux '
            'source vs cible avant toute clôture.'),
        # Vocabulaire FERMÉ de `core.modules.CATEGORIES` : pas de catégorie
        # « Administration » (l'app sœur `adminops` est elle aussi 'Technique').
        'categorie': 'Technique',
    }
