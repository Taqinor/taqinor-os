"""NTUX7 — abonnement de `apps.trash` au bus d'événements M6.

`apps.trash` n'est importée par AUCUNE app métier : ce sont les apps qui
ÉMETTENT `core.events.record_soft_deleted` quand elles soft-suppriment un
enregistrement, et la corbeille s'y abonne ici (câblé depuis `apps.py`
`ready()`), exactement comme `crm` s'abonne à `devis_accepted`.
"""
from core.events import record_soft_deleted


def on_record_soft_deleted(sender, **kwargs):
    """Journalise un enregistrement soft-supprimé dans la corbeille 30 jours.

    Sans `instance` ou sans `company` il n'y a rien de scopable : on ignore
    (un émetteur mal câblé ne doit pas créer une entrée hors société).
    """
    from .services import journaliser_suppression

    instance = kwargs.get('instance')
    company = kwargs.get('company') or getattr(instance, 'company', None)
    if instance is None or company is None or instance.pk is None:
        return None
    return journaliser_suppression(
        instance=instance,
        company=company,
        user=kwargs.get('user'),
        type_libelle=kwargs.get('type_libelle') or '',
        libelle=kwargs.get('libelle') or '',
        donnees=kwargs.get('donnees') or {},
    )


def connect():
    """Câble les récepteurs (appelé par `TrashConfig.ready`)."""
    record_soft_deleted.connect(
        on_record_soft_deleted, dispatch_uid='trash.on_record_soft_deleted')
