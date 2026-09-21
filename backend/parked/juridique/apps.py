from django.apps import AppConfig


class JuridiqueConfig(AppConfig):
    """Groupe NTJUR — Gestion des affaires juridiques (contentieux d'entreprise).

    App DÉDIÉE au contentieux/précontentieux : dossiers, parties, audiences,
    délais de prescription, conseils externes (cabinets/mandats/honoraires),
    provisions PROPOSÉES vers la comptabilité. Distincte de ``litiges`` (la
    réclamation client opérationnelle, reliée ici par une simple référence
    d'id) et de ``contrats`` (le cycle de vie contractuel). Multi-société :
    chaque modèle hérite de ``core.models.TenantModel`` (FK ``company`` posée
    côté serveur, jamais lue du corps de requête).

    ODX2 — ``module_manifest`` collecté génériquement par
    ``core.modules.collect_manifests`` (graphe de modules, gatage
    ``ModuleToggle``, 404 ``DisabledModuleMiddleware``).
    """

    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.juridique'
    verbose_name = 'Affaires juridiques'

    module_manifest = {
        'key': 'juridique',
        # ERP transverse (toute PME finit par avoir un contentieux) — jamais
        # un vertical : gardé actif dans l'édition solaire.
        'sku': 'generic',
        'label': 'Juridique',
        'icone': 'scale',
        'depends': [],
        'description': (
            "Dossiers juridiques (contentieux, précontentieux, consultatif, "
            "recouvrement) : parties, audiences, délais de prescription, "
            "cabinets d'avocats et honoraires, budget et provisions proposées."),
        # Vocabulaire FERMÉ de ``core.modules.CATEGORIES``. Même catégorie que
        # ``contrats``/``litiges``, ses deux voisins de domaine.
        'categorie': 'Services',
    }

    def ready(self):
        # M6 — abonnements au bus ``core.events`` (import fonction-local pour
        # éviter les cycles au chargement des apps).
        from . import receivers  # noqa: F401  (branché par NTJUR26)
