from django.apps import AppConfig


class EducationConfig(AppConfig):
    """NTEDU1 — App `education` : structure année scolaire/niveau/classe,
    dossier famille/élève, inscriptions, scolarité (tarification, remises,
    échéancier), présences, matières/coefficients.

    App satellite (comme ``apps.sante``/``apps.innovation``) : multi-société,
    additive, scopée société côté serveur. Aucune donnée médicale ; les
    coordonnées famille (téléphone/WhatsApp/email) restent des données
    personnelles ADMINISTRATIVES standard (même famille de sensibilité que
    ``crm.Client``, pas de (DECISION) requise).
    """

    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.education'
    verbose_name = 'Éducation (établissement scolaire)'

    module_manifest = {
        'key': 'education',
        'label': 'Éducation',
        'icone': 'graduation-cap',
        'depends': [],
        'description': (
            'Structure année/niveau/classe, dossier famille/élève, '
            'inscriptions, scolarité (tarifs/remises/échéancier), '
            'présences et matières pour établissements scolaires.'),
        'categorie': 'Services',
    }

    def ready(self):
        from . import signals  # noqa: F401
