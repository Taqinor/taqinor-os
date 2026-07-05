from django.apps import AppConfig


class ContratsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.contrats'
    verbose_name = 'Gestion des contrats'
    module_manifest = {
        'key': 'contrats',
        'label': 'Contrats',
        'icone': 'file-signature',
        'depends': [],
        'description': 'Gestion des contrats (CLM).',
        'categorie': 'Services',
    }

    def ready(self):
        # XCTR12 (M6) — abonne `contrats` à l'événement `devis_accepted`
        # (core.events) pour marquer le renouvellement proposé accepté sans
        # couplage direct ventes -> contrats (import local pour éviter les
        # cycles au chargement des apps, même schéma que crm/installations).
        from . import receivers  # noqa: F401
