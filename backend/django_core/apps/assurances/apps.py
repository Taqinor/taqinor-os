from django.apps import AppConfig


class AssurancesConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.assurances'
    verbose_name = "Assurances d'entreprise"
    module_manifest = {
        'key': 'assurances',
        'label': 'Assurances',
        'icone': 'shield',
        'depends': [],
        'description': (
            "Registre des polices d'assurance d'entreprise (RC pro, décennale, "
            "multirisque, cyber, homme-clé), échéancier de primes, sinistres "
            "transverses (hors véhicule) et attestations d'assurance."
        ),
        'categorie': 'Finance',
    }
