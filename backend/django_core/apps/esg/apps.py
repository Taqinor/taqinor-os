from django.apps import AppConfig


class EsgConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.esg'
    verbose_name = 'ESG / RSE'
    module_manifest = {
        'key': 'esg',
        'label': 'ESG / RSE',
        'icone': 'leaf',
        # Lit qhse (indicateurs ESG bruts QHSE40, bilan carbone QHSE39) en
        # lecture seule via des sélecteurs — jamais un import de modèle. Pas
        # une dépendance dure de démarrage (qhse peut être absent), documentée
        # ici pour le manifeste de modules.
        'depends': ['qhse'],
        'description': (
            'Reporting ESG/durabilité consolidé (périodes figées, '
            'agrégation cross-app, catalogue GRI-lite, rapports PDF/xlsx, '
            "trajectoires d'objectifs)."
        ),
        'categorie': 'Services',
    }
