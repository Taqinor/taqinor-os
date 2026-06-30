from django.apps import AppConfig


class KbConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.kb'
    verbose_name = 'Base de connaissances'

    def ready(self):
        # KB6 — branche le récepteur qui (ré)indexe un article dans le RAG/DocQA
        # à chaque enregistrement (no-op sans clé d'embedding).
        from . import signals  # noqa: F401
