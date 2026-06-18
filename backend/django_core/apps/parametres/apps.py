from django.apps import AppConfig


class ParametresConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.parametres'
    verbose_name = 'Paramètres'

    def ready(self):
        import apps.parametres.signals  # noqa: F401
        # N58 — modèle de config des statuts gardé dans un fichier dédié
        # (indépendance des lanes) ; importé ici pour qu'il soit enregistré
        # auprès du registre d'apps sans toucher à ``models.py``.
        import apps.parametres.models_statuses  # noqa: F401
