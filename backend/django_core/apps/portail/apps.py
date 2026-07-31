from django.apps import AppConfig


class PortailConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.portail'
    verbose_name = 'Portail self-service client'
    module_manifest = {
        'key': 'portail',
        'label': 'Portail client',
        'icone': 'user-circle',
        'depends': ['ventes', 'crm', 'sav'],
        'description': (
            'Portail self-service client : consultation devis/factures/chantiers, '
            "acceptation/e-signature de devis, paiement en ligne, dépôt de "
            'documents, timeline de chantier et ouverture de tickets SAV.'
        ),
        'categorie': 'Commercial',
    }

    def ready(self):
        # WIR94 — câble le dépôt GED canonique de l'upload portail. Cette
        # orchestration cross-app vit dans `receivers.py` (jamais dans
        # `models.py` : un modèle n'orchestre pas d'écriture cross-app, et
        # l'import y cassait le contrat CI `portail-models-decoupled`).
        from . import receivers  # noqa: F401
