from django.apps import AppConfig


class EinvoiceConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.einvoice'
    verbose_name = 'Facturation électronique DGI'
    module_manifest = {
        'key': 'einvoice',
        'label': 'E-invoicing DGI',
        'icone': 'file-signature',
        'depends': [],
        'description': (
            "Générateur de facture électronique au schéma DGI marocain "
            "(dry-run/réel derrière flag), scaffold de signature électronique "
            "et file d'attente de transmission Simpl inerte tant que la DGI "
            "n'a pas publié son API (Groupe NTMAR)."
        ),
        'categorie': 'Finance',
    }
