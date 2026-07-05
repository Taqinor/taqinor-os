from django.apps import AppConfig


class KbConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.kb'
    verbose_name = 'Base de connaissances'
    module_manifest = {
        'key': 'kb',
        'label': 'Base de connaissances',
        'icone': 'book',
        'depends': [],
        'description': 'Articles et procédures internes.',
        'categorie': 'Technique',
    }

    def ready(self):
        # KB6 — branche le récepteur qui (ré)indexe un article dans le RAG/DocQA
        # à chaque enregistrement (no-op sans clé d'embedding).
        from . import signals
        # XKB13 — branche le récepteur qui notifie l'auteur d'un article KB
        # commenté (records.Comment est une app fondation, chargée avant kb).
        signals._kb_comment_receiver()
