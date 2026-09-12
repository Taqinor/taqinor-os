from django.apps import AppConfig


class StatuspageConfig(AppConfig):
    """NTOBS1 — page de statut publique multi-région (composants + incidents).

    App NEUVE, sans modèle métier importé : lit ``core.health.check_services()``
    via un job Celery beat périodique (jamais un appel synchrone public à la
    DB de prod). Contenu 100% système/tenant-partagé (``ComponentStatus``/
    ``IncidentPublic`` ont un FK ``company`` NULLABLE — la majorité des lignes
    sont système, partagées entre tous les tenants).
    """

    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.statuspage'
    verbose_name = 'Page de statut publique'
    # ODX2/ODX21 — toute app sous ``apps/`` déclare son manifeste de module.
    # `installable=False` : infrastructure d'exploitation (la page de statut ne
    # se désactive pas par tenant, son contenu est SYSTÈME) ; `sku='generic'`
    # (SOL1) : transverse, gardée dans l'édition solaire, jamais un vertical.
    module_manifest = {
        'key': 'statuspage',
        'sku': 'generic',
        'label': 'Page de statut',
        'icone': 'activity',
        'depends': [],
        'installable': False,
        'description': (
            'Page de statut publique : composants, incidents, frise '
            'de disponibilité 90 jours et abonnements (NTOBS1/2/14/15).'),
        'categorie': 'Technique',
    }

    def ready(self):
        # NTOBS15 — abonne les receveurs qui notifient les abonnés publics
        # confirmés à l'ouverture/résolution d'un incident système.
        from . import receivers  # noqa: F401
