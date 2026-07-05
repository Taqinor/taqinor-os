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
