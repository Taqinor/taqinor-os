from django.apps import AppConfig


class CoreConfig(AppConfig):
    """App de FONDATION ``core``.

    Contient des modèles abstraits (``TimestampedModel``), des mixins, le bus
    d'événements (``core.events``), la portée des enregistrements
    (``core.scoping``), la fondation IA (``core.ai``) et la détection
    d'anomalies générique (``core.anomaly`` + le modèle concret ``AnomalyFlag``,
    FG360). Le seul modèle concret est ``AnomalyFlag`` (multi-tenant, sujet
    désigné de façon générique — aucun import d'app métier). Reste une couche de
    base que tout le monde peut importer vers le bas (contrat import-linter).
    """

    default_auto_field = 'django.db.models.BigAutoField'
    name = 'core'
    verbose_name = 'Fondation'
