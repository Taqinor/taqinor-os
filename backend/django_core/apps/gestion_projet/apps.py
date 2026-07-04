from django.apps import AppConfig


class GestionProjetConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.gestion_projet'
    verbose_name = 'Gestion de projet'
    module_manifest = {
        'key': 'gestion_projet',
        'label': 'Gestion de projet',
        'icone': 'kanban',
        'depends': [],
        'description': 'Projets multi-chantiers et ressources.',
        'categorie': 'Services',
    }

    def ready(self):
        # M6/XPRJ9 — abonne gestion_projet aux événements métier (core.events) :
        # synchronise l'Indisponibilite planning à la validation/annulation
        # d'une rh.DemandeConge, sans couplage direct vers rh.
        from . import receivers  # noqa: F401
