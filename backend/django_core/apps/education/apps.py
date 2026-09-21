"""Configuration de l'app « education » — PARQUÉE (voir ``core.parked``)."""
from django.apps import AppConfig


class EducationConfig(AppConfig):
    """Éducation (établissement scolaire) — app PARQUÉE du MVP solaire (20/09/2026).

    Coquille de migrations : plus aucun modèle, aucune url, aucune
    tâche, aucun écran. Le code complet est dans l'archive
    ``archive/full-erp-2026-09-20`` ; recette de retour : docs/parked-modules.md §5.

    L'app RESTE dans INSTALLED_APPS : c'est ce qui garde valide le
    graphe de migrations des apps gardées (jamais de squash).
    """

    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.education'
    label = 'education'
    verbose_name = 'Éducation (établissement scolaire)'
    # SOLMVP — marqueur lu par les gardes (core.parked.est_parquee).
    parked = True
    module_manifest = {
        'key': 'education',
        'sku': 'vertical_education',
        'label': 'Éducation',
        'icone': 'graduation-cap',
        'depends': [],
        'description': 'Structure année/niveau/classe, dossier famille/élève, inscriptions, scolarité (tarifs/remises/échéancier), présences et matières pour établissements scolaires.',
        'categorie': 'Services',
        'parked': True,
    }
