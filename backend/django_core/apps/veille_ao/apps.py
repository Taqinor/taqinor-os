from django.apps import AppConfig


class VeilleAoConfig(AppConfig):
    """AppConfig du module « apps.veille_ao » (VAO6 — généré par startapp_erp).

    Le SAS de la veille appels d'offres : la table où atterrissent TOUS les
    avis de marché, quelle que soit la porte d'entrée (portail public, tuyau
    partenaire, import de fichier). **Aucun avis ne devient automatiquement un
    `AppelOffre`** — le portail contient beaucoup de bruit, c'est un humain qui
    tranche.

    App NEUVE et délibérément SÉPARÉE d'``apps.ao`` : la chaîne de migrations
    d'``apps.ao`` est mono-écrivain et réservée au groupe AOF (`docs/PLAN.md`,
    migrations déjà nommées `0002_tenantmodel`…`0009_administratif`) — poser
    une migration VAO dedans décalerait toute la chaîne déclarée. Le couplage
    vers l'AO se fait par entier OPAQUE (`appel_offre_id`), jamais par FK, ce
    qui garde les deux apps découplées et le contrat import-linter vert.

    ODX2 — ``module_manifest`` : déclaré une fois, collecté génériquement par
    ``core.modules.collect_manifests`` (graphe de modules, gatage
    ``ModuleToggle`` et enforcement 404 ``DisabledModuleMiddleware``).
    """

    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.veille_ao'
    verbose_name = "Veille appels d'offres"
    module_manifest = {
        # Clé ``ModuleToggle`` — IDENTIQUE au 2ᵉ segment d'URL
        # (`api/django/veille_ao/`), sinon il faudrait une entrée
        # ``core/permissions.PREFIX_TO_MODULE``.
        'key': 'veille_ao',
        'label': "Veille appels d'offres",
        'icone': 'radar',
        # La veille ALIMENTE le module Appels d'offres : « retenir » un avis y
        # crée l'affaire. Dépendance de MODULE (graphe), pas d'import Python.
        'depends': ['ao'],
        'installable': True,
        'description': (
            "Veille des avis de marché : le sas où atterrissent les avis "
            "collectés sur le portail public, signalés par un partenaire ou "
            "importés d'un fichier. Un humain trie ; les avis retenus "
            "deviennent des appels d'offres. Ne promet jamais l'exhaustivité."
        ),
        'categorie': 'Commercial',
    }

    def ready(self):
        # M6 — aucun abonnement au bus ``core.events`` pour l'instant : le
        # dépôt fait rougir la CI sur tout signal sans abonné réel, et rien
        # ici n'a besoin d'un abonné cross-app.

        # VAO26 — politique de rétention du sas, déclarée dans le registre
        # PARTAGÉ (``core.retention``, YOPSB10) sur le patron d'``apps/crm``.
        # Purge les avis « nouveau »/« ignoré » dont la date limite est
        # dépassée depuis VEILLE_AO_RETENTION_MOIS (défaut 12) ; un avis
        # RETENU, CONVERTI ou lié à un appel d'offres n'est JAMAIS purgé — il
        # porte l'historique commercial et la mesure d'attribution (VAO31).
        from core.retention import register_retention_policy

        from .retention import purger_avis

        register_retention_policy('veille_ao_avis_perimes', purger_avis)
