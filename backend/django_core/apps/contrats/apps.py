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
        # ARC14 déclarait Contrat comme cible PILOTE des champs personnalisés
        # ici même (customfields.registry.register('contrat', ...)). ARC31 a
        # basculé cette déclaration vers apps/contrats/platform.py
        # (customfield_models=['contrat']) — un chargeur central unique
        # (apps/customfields/apps.py::CustomfieldsConfig.ready()) la lit
        # désormais depuis le manifeste, plus depuis ce ready().
