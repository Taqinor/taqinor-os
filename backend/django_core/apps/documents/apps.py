from django.apps import AppConfig


class DocumentsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.documents'
    label = 'documents'
    verbose_name = 'Documents après-vente'
    module_manifest = {
        'key': 'documents',
        'sku': 'generic',
        'label': 'Documents après-vente',
        'icone': 'file',
        'depends': ['sav'],
        'description': 'Documents liés au parc et au SAV.',
        'categorie': 'Services',
    }

    def ready(self):
        # Dossier contractuel — abonne documents aux événements du devis et du
        # chantier (core.events) : préparation des actes, annulation.
        from importlib import import_module
        import_module(f'{self.name}.receivers')
