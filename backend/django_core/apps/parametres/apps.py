from importlib import import_module

from django.apps import AppConfig


class ParametresConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.parametres'
    verbose_name = 'Paramètres'
    module_manifest = {
        'key': 'parametres',
        'sku': 'generic',
        'label': 'Paramètres',
        'icone': 'settings',
        'depends': [],
        'installable': False,
        'description': 'Paramétrage de la société.',
        'categorie': 'Technique',
    }

    def ready(self):
        import_module('apps.parametres.signals')
        # N58 — modèle de config des statuts gardé dans un fichier dédié
        # (indépendance des lanes) ; importé ici pour qu'il soit enregistré
        # auprès du registre d'apps sans toucher à ``models.py``.
        import_module('apps.parametres.models_statuses')
        # D2/N60/N67/N26/N59 — modèles de documents éditables (textes du devis),
        # gardés dans un fichier dédié et enregistrés ici sans toucher models.py.
        import_module('apps.parametres.models_documents')
        # N64/N65 — tarification ONEE + hypothèses ROI/productible, gardées dans
        # un fichier dédié et enregistrées ici sans toucher models.py.
        import_module('apps.parametres.models_tariff')
        # FG17 — modèles d'e-mail éditables (parité WhatsApp), fichier dédié
        # enregistré ici sans toucher models.py.
        import_module('apps.parametres.models_email')
        # FG25 — politiques d'approbation configurables, fichier dédié
        # enregistré ici sans toucher models.py.
        import_module('apps.parametres.models_approvals')
        # N94 — surcharges de traduction de l'interface (par société/langue/clé),
        # fichier dédié enregistré ici sans toucher models.py.
        import_module('apps.parametres.models_translations')
        # ARC23 — référentiel des taux de TVA par société (également ré-exporté
        # par models.py) ; import ici pour l'enregistrement au démarrage.
        import_module('apps.parametres.models_taxes')
        # ARC24 — référentiel des conditions de paiement par société (également
        # ré-exporté par models.py) ; import ici pour l'enregistrement.
        import_module('apps.parametres.models_payment_terms')
        # ARC27 — référentiel des unités de mesure par société (également
        # ré-exporté par models.py) ; import ici pour l'enregistrement.
        import_module('apps.parametres.models_units')
        # Catalogue « Réalisations » (08/09/2026) — installations réelles de la
        # société, source de la preuve de la touche J4 ; également ré-exporté
        # par models.py, import ici pour l'enregistrement au démarrage.
        import_module('apps.parametres.models_realisations')
        # ARC23 — hook de seed « nouvelle société » des taux de TVA usuels.
        from .signup_hooks import register_parametres_signup_hooks
        register_parametres_signup_hooks()
        # SOL9 — branche le PLAN DE LICENCE (NTADM7) sur le chemin d'accès
        # UNIQUE de `core.feature_flags` (même chemin que ModuleToggle : 404 du
        # middleware + `modules_desactives` de /auth/me). C'est l'app métier qui
        # se branche ; `core` reste une fondation qui n'importe rien.
        from .feature_flags import register_plan_access_check
        register_plan_access_check()
