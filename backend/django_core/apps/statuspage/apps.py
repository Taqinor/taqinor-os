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
