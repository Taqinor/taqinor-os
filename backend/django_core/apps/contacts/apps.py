from django.apps import AppConfig


class ContactsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.contacts'
    verbose_name = 'Contacts multi-rôles'
    module_manifest = {
        'key': 'contacts',
        'label': 'Contacts multi-rôles',
        'icone': 'address-book',
        'depends': ['crm'],
        'description': "Organigramme d'achat multi-rôles par client.",
        'categorie': 'Ventes',
    }
