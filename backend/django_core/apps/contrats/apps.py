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
        # ARC35 — le même module abonne aussi `contrats` à ses propres
        # `contrat_signe`/`contrat_actif` (chatter ARC8 + dépôt GED du
        # contrat signé), sur le patron `qhse.receivers` (émetteur ET
        # abonné = la même app, mais toujours via le bus pour rester
        # ouvert à de futurs abonnés externes).
        from . import receivers  # noqa: F401
        # ARC14 — déclare Contrat comme cible PILOTE des champs personnalisés
        # (customfields.registry, registre data-driven — jamais un import de
        # apps.customfields.models depuis ici, juste l'API de registre).
        from apps.customfields import registry
        registry.register('contrat', 'contrats', 'Contrat', label='Contrat')
