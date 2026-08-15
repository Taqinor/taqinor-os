from django.apps import AppConfig


class CoreConfig(AppConfig):
    """App de FONDATION ``core``.

    Contient des modèles abstraits (``TimestampedModel``), des mixins, le bus
    d'événements (``core.events``), la portée des enregistrements
    (``core.scoping``), la fondation IA (``core.ai``) et la détection
    d'anomalies générique (``core.anomaly`` + le modèle concret ``AnomalyFlag``,
    FG360). Le seul modèle concret est ``AnomalyFlag`` (multi-tenant, sujet
    désigné de façon générique — aucun import d'app métier). Reste une couche de
    base que tout le monde peut importer vers le bas (contrat import-linter).
    """

    default_auto_field = 'django.db.models.BigAutoField'
    name = 'core'
    verbose_name = 'Fondation'
    module_manifest = {
        'key': 'core',
        'label': 'Fondation',
        'icone': 'layers',
        'depends': [],
        'installable': False,
        'description': 'Couche de fondation (modèles abstraits, bus, DSR…).',
        'categorie': 'Technique',
    }

    def ready(self):
        # FG396 — supervision d'erreurs (Sentry), gardée par DSN. No-op total
        # sans ``SENTRY_DSN`` (aucune dépendance chargée, aucun appel réseau).
        from . import monitoring
        monitoring.init_sentry()

        # SCA28 — hook signup « branding neutre » (thème + modèles brandés par
        # défaut) enregistré dans le registre core.signup_hooks. Idempotent :
        # le ré-enregistrement remplace, jamais de doublon d'exécution.
        from .signup_hooks import register_core_signup_hooks
        register_core_signup_hooks()

        # NTAI24 — index sémantique cross-module : branchement ``post_save``/
        # ``post_delete`` sur les modèles déclarés indexables PAR CHAÎNE (aucun
        # import d'app métier ici). No-op complet tant que
        # ``AI_SEMANTIC_INDEX_ENABLED`` est éteint (défaut) : le receiver rend
        # la main immédiatement, aucune ligne n'est écrite.
        from .ai.search import connect_signals
        connect_signals()
