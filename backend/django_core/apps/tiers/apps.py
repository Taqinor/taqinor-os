from django.apps import AppConfig


class TiersConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.tiers'
    verbose_name = 'Tiers (parties prenantes)'
    module_manifest = {
        'key': 'tiers',
        'label': 'Tiers',
        'icone': 'users',
        'depends': [],
        'description': "Répertoire unifié des parties prenantes (clients, "
                       "fournisseurs, partenaires, sous-traitants).",
        'categorie': 'Technique',  # couche foundation (même catégorie que records/roles)
    }
