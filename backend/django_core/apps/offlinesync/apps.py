from django.apps import AppConfig


class OfflinesyncConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.offlinesync'
    verbose_name = 'Synchronisation hors-ligne'
    module_manifest = {
        'key': 'offlinesync',
        'label': 'Synchronisation hors-ligne',
        'icone': 'refresh-cw-off',
        'depends': [],
        # Fondation technique : la file hors-ligne n'est pas un module métier
        # qu'on active/désactive — elle sert tous les modules.
        'installable': False,
        'description': (
            "File d'attente hors-ligne multi-module (rejeu idempotent par "
            "clé client) — NTMOB1."),
        'categorie': 'Technique',
    }

    def ready(self):
        # NTMOB1 — l'enregistrement des handlers de rejeu se fait au démarrage
        # (import différé : `handlers` touche les services d'autres apps, il ne
        # doit jamais s'exécuter au chargement des modèles).
        from . import handlers  # noqa: F401
