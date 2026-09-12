from django.apps import AppConfig


class VisitesConfig(AppConfig):
    """AppConfig du module « apps.visites » (VTA1 — checklist startapp_erp).

    L'app AUTONOME de la visite technique terrain, sortie d'``apps.crm``
    (commande fondateur 2026-09-12) : l'utilisateur qui fait la visite est un
    **commercial terrain** qui n'a probablement AUCUN accès CRM. Tant que la
    visite vivait dans le CRM, lui ouvrir la visite lui ouvrait l'annuaire des
    leads ; l'app séparée rend la frontière structurelle et non déclarative.

    App NEUVE et délibérément DISTINCTE d'``apps.installations`` : la visite
    technique est de la **pré-vente** (rattachée au ``Lead``, avant le devis
    signé) tandis qu'``apps.installations`` est le post-vente, possédé par le
    contrat d'app du domaine PLAN_SERVICE. Les deux ne partagent ni cycle de
    vie, ni permissions, ni route d'accueil.

    Couplage vers le CRM : la FK ``lead`` est une référence **STRING**
    (``'crm.Lead'``) et toute lecture crm/ventes passe par leurs
    ``selectors``/``services`` en import PARESSEUX (frontière M3). Le retour au
    lead après un feu vert passe par l'événement ``visite_validee`` du bus
    ``core.events`` (M6) — jamais un écrit direct de visites vers ``Lead``.

    ODX2 — ``module_manifest`` : déclaré une fois, collecté génériquement par
    ``core.modules.collect_manifests`` (graphe de modules, gatage
    ``ModuleToggle`` et enforcement 404 ``DisabledModuleMiddleware``). La clé
    est IDENTIQUE au 2ᵉ segment d'URL (``api/django/visites/``), donc aucune
    entrée ``core.permissions.PREFIX_TO_MODULE`` n'est nécessaire.
    """

    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.visites'
    verbose_name = 'Visites terrain'
    module_manifest = {
        # Clé ``ModuleToggle`` — IDENTIQUE au 2ᵉ segment d'URL.
        'key': 'visites',
        'sku': 'solar_core',
        'label': 'Visites terrain',
        'icone': 'map-pin',
        # La visite documente un LEAD : dépendance de MODULE (graphe), pas un
        # import Python (la FK reste une référence string).
        'depends': ['crm'],
        'installable': True,
        'description': (
            "Visites techniques terrain : le commercial se déplace, "
            "photographie la toiture, le tableau et l'emplacement onduleur "
            "par emplacement nommé, relève les mesures ; le bureau d'études "
            "donne — ou refuse — le feu vert au calepinage. Le module "
            "n'émet aucun verdict technique : il enregistre ce qui a été "
            "relevé."
        ),
        'categorie': 'Commercial',
    }

    def ready(self):
        # M6 — aucun abonnement au bus ``core.events`` ici : cette app ÉMET
        # (``visite_validee``, VTA5) et n'a besoin de réagir à aucune autre
        # app. C'est ``apps.crm`` qui s'abonne, dans SON ``receivers.py``.
        pass
