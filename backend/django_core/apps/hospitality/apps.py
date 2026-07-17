from django.apps import AppConfig


class HospitalityConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.hospitality'
    verbose_name = 'Hôtellerie & restauration'
    module_manifest = {
        'key': 'hospitality',
        'label': 'Hôtellerie',
        'icone': 'bed',
        'depends': [],
        'description': (
            'Plan des chambres, réservations, check-in/check-out, folio '
            'client unifié et housekeeping pour hôtel/riad.'
        ),
        'categorie': 'Verticaux',
    }
