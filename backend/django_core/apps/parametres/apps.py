from django.apps import AppConfig


class ParametresConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.parametres'
    verbose_name = 'Paramètres'

    def ready(self):
        import apps.parametres.signals  # noqa: F401
        # N58 — modèle de config des statuts gardé dans un fichier dédié
        # (indépendance des lanes) ; importé ici pour qu'il soit enregistré
        # auprès du registre d'apps sans toucher à ``models.py``.
        import apps.parametres.models_statuses  # noqa: F401
        # D2/N60/N67/N26/N59 — modèles de documents éditables (textes du devis),
        # gardés dans un fichier dédié et enregistrés ici sans toucher models.py.
        import apps.parametres.models_documents  # noqa: F401
        # N64/N65 — tarification ONEE + hypothèses ROI/productible, gardées dans
        # un fichier dédié et enregistrées ici sans toucher models.py.
        import apps.parametres.models_tariff  # noqa: F401
        # FG17 — modèles d'e-mail éditables (parité WhatsApp), fichier dédié
        # enregistré ici sans toucher models.py.
        import apps.parametres.models_email  # noqa: F401
        # FG25 — politiques d'approbation configurables, fichier dédié
        # enregistré ici sans toucher models.py.
        import apps.parametres.models_approvals  # noqa: F401
        # N94 — surcharges de traduction de l'interface (par société/langue/clé),
        # fichier dédié enregistré ici sans toucher models.py.
        import apps.parametres.models_translations  # noqa: F401
