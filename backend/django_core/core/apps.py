from importlib import import_module

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
        'sku': 'generic',
        'label': 'Fondation',
        'icone': 'layers',
        'depends': [],
        'installable': False,
        'description': 'Couche de fondation (modèles abstraits, bus, DSR…).',
        'categorie': 'Technique',
    }

    def ready(self):
        # QJR423 / DR8 — contrôles système des réglages de PRODUCTION
        # (DEBUG interdit, ALLOWED_HOSTS explicite exigé). L'import suffit :
        # les contrôles s'enregistrent par décorateur. NO-OP TOTAL hors
        # production — en dev et en CI (settings.dev), ils rendent [].
        import_module(f'{self.name}.checks')

        # Heure légale marocaine (décret 2.26.530 : UTC+0 depuis le
        # 20/09/2026) — ERREUR bloquante si la base de fuseaux de Python est
        # périmée, AVERTISSEMENT (étiqueté `database`, jamais bloquant) si
        # c'est celle de Postgres. Même mécanique : l'import enregistre les
        # contrôles par décorateur.
        import_module(f'{self.name}.checks_tz')

        # FG396 — supervision d'erreurs (Sentry), gardée par DSN. No-op total
        # sans ``SENTRY_DSN`` (aucune dépendance chargée, aucun appel réseau).
        from . import monitoring
        monitoring.init_sentry()

        # BPQ2 - marqueur de demarrage (horodatage + sha deploye dans la liste
        # Redis bornee ``erp:demarrages``) : jamais pour une commande de gestion
        # (migrate, test, shell...), seulement pour un process serveur/worker.
        # Best-effort, no-op si Redis est injoignable.
        import sys
        argv = sys.argv
        commande_gestion = (
            len(argv) > 1 and argv[0].endswith('manage.py')
            and argv[1] != 'runserver')
        if not commande_gestion and 'test' not in argv[1:2]:
            from .health import enregistrer_demarrage
            enregistrer_demarrage()

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

        # NTPLT32 — colonnes plein-texte ``search_vector`` des 7 entités de la
        # recherche globale, recalculées après chaque écriture (libellés par
        # CHAÎNE : aucun import d'app métier ici).
        from .recherche_fts import connecter as connecter_recherche_fts
        connecter_recherche_fts()

        # ENFP (décision fondateur D1, 09/10/2026) — un paramètre de requête
        # non déclaré au schéma OpenAPI est refusé (400). Enveloppe UNE fois
        # ``APIView.initial`` ; le réglage ``API_QUERY_PARAMS_STRICT`` est lu
        # à chaque requête (no-op quand il est faux). Voir
        # ``core.parametres_requete``.
        from .parametres_requete import installer
        installer()

        # api-fuzz-full 24/10/2026 — date-heure à décalage LMT (secondes)
        # rendue en UTC : voir ``core.champs_stricts.installer_dates_rfc3339``.
        from .champs_stricts import installer_dates_rfc3339
        installer_dates_rfc3339()

        # ADCG61 — DRF 3.18 garde le contrat API de 3.15 (mapping des entiers,
        # options d'unicité) : voir ``core.drf_compat``.
        from .drf_compat import appliquer as appliquer_drf_compat
        appliquer_drf_compat()

        # APFS103 — créateur supprimé ⇒ ses extraits planifiés suspendus
        # (référence paresseuse : aucun import d'app ici).
        from django.conf import settings
        from django.db.models.signals import pre_delete
        from .scheduled_export import suspendre_exports_du_createur
        pre_delete.connect(suspendre_exports_du_createur, sender=settings.AUTH_USER_MODEL,
                           dispatch_uid='core_apfs103_suspendre_exports_du_createur')
