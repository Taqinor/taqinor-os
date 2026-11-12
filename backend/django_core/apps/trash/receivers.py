"""NTUX7 — abonnement de `apps.trash` au bus d'événements M6.

`apps.trash` n'est importée par AUCUNE app métier : ce sont les apps qui
ÉMETTENT `core.events.record_soft_deleted` quand elles soft-suppriment un
enregistrement, et la corbeille s'y abonne ici (câblé depuis `apps.py`
`ready()`), exactement comme `crm` s'abonne à `devis_accepted`.
"""
from core.events import record_soft_deleted, record_soft_restored


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


def on_record_soft_restored(sender, instance=None, **kwargs):
    """ASUP15 — « Annuler » (``SoftDeleteModel.restore``) ferme aussi l'entrée ACTIVE de la corbeille commune."""
    from django.contrib.contenttypes.models import ContentType
    from django.utils import timezone

    from .models import ElementSupprime
    maintenant = timezone.now()
    return 0 if instance is None or instance.pk is None else ElementSupprime.objects.filter(
        content_type=ContentType.objects.get_for_model(type(instance)), object_id=instance.pk,
        restaure_le__isnull=True).update(restaure_le=maintenant, updated_at=maintenant)


def connect():
    """Câble les récepteurs (appelé par `TrashConfig.ready`)."""
    record_soft_deleted.connect(
        on_record_soft_deleted, dispatch_uid='trash.on_record_soft_deleted')
    record_soft_restored.connect(
        on_record_soft_restored, dispatch_uid='trash.on_record_soft_restored')
