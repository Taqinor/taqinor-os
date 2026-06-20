from django.apps import AppConfig


class DataImportConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.dataimport'
    label = 'dataimport'
    verbose_name = 'Import / Export de données'
