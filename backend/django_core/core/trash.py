"""FG388 — Corbeille / restauration (soft-delete + undo), services.

Couche de FONDATION : pilote la corbeille par société et la fenêtre d'« annuler »
globale à partir du journal ``DeletionRecord`` (keyé via ``contenttypes``) et du
mixin ``SoftDeleteModel``. ``core`` n'importe AUCUNE app métier (contrat
import-linter ``core-foundation-is-a-base-layer``) : il restaure l'objet
d'origine en le résolvant dynamiquement par ``content_type`` (fondation Django).
"""
from __future__ import annotations

from datetime import timedelta

from django.utils import timezone

# Fenêtre d'« annuler » globale par défaut (minutes). Un undo reste possible
# tant que l'entrée n'est pas restaurée ; cette fenêtre sert au bandeau « annuler
# la suppression » côté UI.
UNDO_WINDOW_MINUTES = 30


def corbeille(company):
    """Entrées de corbeille NON restaurées d'une société (les plus récentes
    d'abord). Multi-tenant : toujours filtré par société."""
    from .models import DeletionRecord
    return (DeletionRecord.objects
            .filter(company=company, restored_at__isnull=True)
            .order_by('-id'))


def dans_fenetre_undo(company, *, minutes=UNDO_WINDOW_MINUTES, now=None):
    """Entrées encore « annulables » (supprimées dans la fenêtre d'undo)."""
    now = now or timezone.now()
    seuil = now - timedelta(minutes=minutes)
    return corbeille(company).filter(created_at__gte=seuil)


def restaurer(record):
    """Restaure l'objet d'origine d'une entrée de corbeille + ferme l'entrée.

    Résout dynamiquement le modèle cible via ``content_type`` (aucun import
    métier). Renvoie l'objet restauré, ou ``None`` si l'objet n'existe plus.
    """
    from .models import DeletionRecord

    if record.restored_at is not None:
        return None
    model = record.content_type.model_class()
    if model is None:
        return None
    manager = getattr(model, 'all_objects', model._default_manager)
    obj = manager.filter(pk=record.object_id).first()
    if obj is None:
        # L'objet a disparu (purge dure) : on ferme l'entrée proprement.
        record.restored_at = timezone.now()
        record.save(update_fields=['restored_at', 'updated_at'])
        return None
    if hasattr(obj, 'restore'):
        obj.restore()  # ferme déjà l'entrée via SoftDeleteModel.restore()
    else:  # pragma: no cover - cibles non-SoftDelete : on ferme juste l'entrée.
        DeletionRecord.objects.filter(pk=record.pk).update(
            restored_at=timezone.now())
    record.refresh_from_db()
    return obj
