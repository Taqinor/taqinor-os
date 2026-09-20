from django.apps import AppConfig


class CalepinageConfig(AppConfig):
    """AppConfig du module « apps.calepinage » (CAL4 — généré par startapp_erp).

    Le module Calepinage est AUTONOME : on y conçoit une toiture pour un lead,
    un client, un devis ou une affaire d'appel d'offres. Il ne REMPLACE rien —
    le geste « Concevoir la toiture (3D) » de la fiche lead garde exactement sa
    sémantique, et l'atelier 2D opposable des appels d'offres garde ses modèles.
    Le module est une PORTE SUPPLÉMENTAIRE (décision fondateur du 19/09/2026).

    ODX2 — ``module_manifest`` : déclaré une fois, collecté génériquement par
    ``core.modules.collect_manifests`` (graphe de modules, gatage
    ``ModuleToggle`` et enforcement 404 ``DisabledModuleMiddleware``).
    """

    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.calepinage'
    verbose_name = 'Calepinage (conception de toiture)'
    module_manifest = {
        # Clé ``ModuleToggle`` (unique dans tout le dépôt, obligatoire) ; elle
        # est AUSSI le 2ᵉ segment d'URL (``/api/django/calepinage/…``), donc
        # aucune entrée ``PREFIX_TO_MODULE`` n'est nécessaire.
        'key': 'calepinage',
        # SOL1 — cœur métier solaire, comme ``apps.ao`` (`'sku': 'solar_core'`).
        'sku': 'solar_core',
        'label': 'Calepinage',
        'icone': 'grid_on',
        # La création part d'un lead/client (crm) ou d'un devis (ventes).
        'depends': ['crm', 'ventes'],
        'installable': True,
        'description': (
            "Conception de toiture et calepinage photovoltaïque : implantation "
            "des modules, variantes comparées, versions horodatées et "
            "rattachement à un lead, un client, un devis ou une affaire "
            "d'appel d'offres."
        ),
        'categorie': 'Commercial',
    }

    def ready(self):
        # M6 / CAL39 — abonnement au bus ``core.events`` : chaque
        # enregistrement de conception côté VENTES (``from-layout``,
        # ``sync-layout``, action ``layout``) émet ``layout_finalise``, et le
        # récepteur alimente le calepinage canonique. Sans lui, un calepinage
        # créé depuis la fiche lead resterait gelé à sa création pendant que le
        # devis continue d'être redessiné. Import ICI (et pas en tête de
        # module) : ``ready()`` est le seul moment où les modèles sont chargés.
        #
        # CAL110 — le MÊME module porte l'abonnement à ``lead_created`` : un
        # lead issu du parcours public « mon toit » ouvre un calepinage
        # pré-tracé. C'est l'app CONSOMMATRICE qui s'abonne (patron M6) :
        # ``apps/crm/receivers.py`` n'a aucune connaissance de ce module.
        from . import receivers  # noqa: F401

        # CAL208 — enregistre le restaurateur dédié de la corbeille
        # transverse (``apps.trash.registry``) : ``Calepinage`` ne porte
        # aucun drapeau de soft-delete, donc le repli GÉNÉRIQUE de
        # ``apps.trash`` échouerait (``RestaurationImpossible``). Restaurer
        # ne modifie rien sur l'objet : l'état archivé/actif est
        # entièrement porté par la corbeille elle-même.
        from apps.trash.registry import enregistrer_restaurateur

        from .services.archivage import CLE_MODELE, restaurateur_calepinage

        enregistrer_restaurateur(CLE_MODELE, restaurateur_calepinage)
