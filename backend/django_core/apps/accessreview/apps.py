from django.apps import AppConfig


class AccessReviewConfig(AppConfig):
    """App de FONDATION gouvernance des accès (NTSEC19/20).

    Campagnes de revue d'accès + attestation manager, et matrices de séparation
    des tâches (SoD). N'importe AUCUNE app métier ; toute écriture de rôle passe
    par ``apps.roles.services``. Données scopées société côté serveur.
    """

    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.accessreview'
    label = 'accessreview'
    verbose_name = 'Revue des accès'
    module_manifest = {
        'key': 'accessreview',
        'label': 'Revue des accès',
        'icone': 'shield-check',
        'depends': [],
        'installable': False,
        'description': "Campagnes de revue d'accès, attestation, SoD.",
        'categorie': 'Technique',
    }
