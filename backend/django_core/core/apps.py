from django.apps import AppConfig


class CoreConfig(AppConfig):
    """App de FONDATION ``core``.

    Ne contient que des modèles abstraits (``TimestampedModel``), des mixins, le
    bus d'événements (``core.events``), la portée des enregistrements
    (``core.scoping``) et la fondation IA (``core.ai``). Aucun modèle concret →
    aucune migration. Enregistrée pour que sa suite de tests soit découvrable
    par ``manage.py test core`` et pour rester une couche de base que tout le
    monde peut importer vers le bas (contrat import-linter).
    """

    default_auto_field = 'django.db.models.BigAutoField'
    name = 'core'
    verbose_name = 'Fondation'
