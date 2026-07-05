from django.apps import AppConfig


class MarketingConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.marketing'
    verbose_name = 'Marketing'
    module_manifest = {
        'key': 'marketing',
        'label': 'Marketing',
        'icone': 'megaphone',
        'depends': ['crm'],
        'description': (
            'Email/SMS marketing, séquences de relance, enquêtes/NPS, '
            'événements et programme de fidélité.'
        ),
        'categorie': 'Commercial',
    }

    def ready(self):
        # XMKT1 — sortie automatique des séquences de relance à
        # l'acceptation/refus d'un devis lié à un lead (core.events, M6).
        from . import receivers  # noqa: F401
