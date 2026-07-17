from django.apps import AppConfig


class FiscalConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.fiscal'
    verbose_name = 'Conformité fiscale Maroc'
    module_manifest = {
        'key': 'fiscal',
        'label': 'Conformité fiscale',
        'icone': 'calendar-check',
        'depends': [],
        'description': (
            "Calendrier fiscal marocain complet par obligation (TVA/IS/IR/"
            "acomptes/timbre/RAS/CNSS/taxe professionnelle), rappels "
            "d'échéance, tableau de bord de conformité, attestations tenant "
            "avec expirations, registre UBO et veille réglementaire "
            "actionnable (Groupe NTMAR)."
        ),
        'categorie': 'Finance',
    }
