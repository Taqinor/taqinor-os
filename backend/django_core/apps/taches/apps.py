from django.apps import AppConfig


class TachesConfig(AppConfig):
    """AppConfig du module « apps.taches » (généré par startapp_erp — ARC42).

    ODX2 — ``module_manifest`` : déclaré une fois, collecté génériquement par
    ``core.modules.collect_manifests`` (apparaît dans le graphe de modules, le
    gatage ``ModuleToggle`` et l'enforcement 404 ``DisabledModuleMiddleware``).
    Ajuster ``label`` / ``categorie`` / ``depends`` / ``icone`` au vrai module.
    Une app de FONDATION ou purement technique met ``installable=False``.
    """

    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.taches'
    verbose_name = 'Taches'
    module_manifest = {
        # Clé ``ModuleToggle`` (unique dans tout le dépôt, obligatoire).
        'key': 'taches',
        # SOL1 — appartenance à l'édition : solar_core (cœur métier solaire) /
        # generic (ERP transverse) / optional (ModuleToggle off à la création
        # d'un tenant) / vertical_<x> (sorti du build de l'édition solaire —
        # à inscrire AUSSI dans erp_agentique/settings/editions.py).
        'sku': 'generic',
        'label': 'Taches',
        'icone': '',
        'depends': [],
        # TCH131 — activation (fin de F2, donnees.md inv. 28) : le module devient installable.
        'installable': True,
        'description': 'Module taches (à décrire).',
        # Ventes/Finance/RH/Stock/Services/Marketing/Technique/Commercial.
        'categorie': 'Technique',
    }

    def ready(self):
        # M6 — abonnements au bus d'événements ``core.events`` (import local pour
        # éviter les cycles au chargement des apps). Décommenter quand l'app
        # réagit à l'état d'une autre app (ex. ``ventes`` émet ``devis_accepted``).
        # from . import receivers  # noqa: F401
        #
        # TCH74 — effacement 09-08, les DEUX portes (reference/donnees.md §5) : le récepteur
        # `lead_erased` (abonné à l'import de `receivers`) et le fournisseur DSR `taches`.
        from apps.taches import dsr, receivers  # noqa: F401
        dsr.register()
