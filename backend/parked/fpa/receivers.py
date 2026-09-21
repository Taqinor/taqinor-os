"""NTFPA27 — audit des changements budgétaires FP&A.

Branche les signaux ``pre_save``/``post_save``/``post_delete`` des modèles
budgétaires FP&A sur l'``AuditLog`` EXISTANT via ``apps.audit.recorder`` (aucune
infrastructure nouvelle, même patron que ``apps/audit/signals.py`` mais câblé
DANS l'app FP&A — ``apps/audit/signals.TRACKED_MODELS`` appartient à la
plateforme). Best-effort : une écriture d'audit en échec ne casse jamais la
sauvegarde métier. Ne journalise QUE pendant une requête (``recorder.in_request``),
comme le mécanisme d'audit générique — pas de bruit en migration/seed/test direct.
"""
from django.db.models.signals import post_delete, post_save, pre_save
from django.dispatch import receiver

from .models import LigneBudgetDepartement, ScenarioBudgetaire


def _audit_actif():
    try:
        from apps.audit import recorder
        return recorder.in_request()
    except Exception:
        return False


@receiver(pre_save, sender=LigneBudgetDepartement)
def _ligne_pre_save(sender, instance, **kwargs):
    if not instance.pk:
        return
    try:
        instance._fpa_old_montant = sender.objects.filter(
            pk=instance.pk).values_list('montant_prevu', flat=True).first()
    except Exception:
        instance._fpa_old_montant = None


@receiver(post_save, sender=LigneBudgetDepartement)
def _ligne_post_save(sender, instance, created, **kwargs):
    if not _audit_actif():
        return
    from apps.audit.models import AuditLog
    from apps.audit.recorder import record
    if created:
        record(AuditLog.Action.CREATE, instance=instance, company=instance.company,
               detail=(f'Budget {instance.categorie} M{instance.mois} créé '
                       f'({instance.montant_prevu}).'))
        return
    old = getattr(instance, '_fpa_old_montant', None)
    new = instance.montant_prevu
    changes = None
    if old is not None and old != new:
        changes = [{'field': 'montant_prevu', 'old': str(old), 'new': str(new)}]
    record(AuditLog.Action.UPDATE, instance=instance, company=instance.company,
           detail=(f'Budget {instance.categorie} M{instance.mois} : '
                   f'{old} → {new}.'), changes=changes)


@receiver(post_delete, sender=LigneBudgetDepartement)
def _ligne_post_delete(sender, instance, **kwargs):
    if not _audit_actif():
        return
    from apps.audit.models import AuditLog
    from apps.audit.recorder import record
    record(AuditLog.Action.DELETE, instance=instance, company=instance.company,
           detail=f'Budget {instance.categorie} M{instance.mois} supprimé.')


@receiver(post_save, sender=ScenarioBudgetaire)
def _scenario_post_save(sender, instance, created, **kwargs):
    if not _audit_actif():
        return
    from apps.audit.models import AuditLog
    from apps.audit.recorder import record
    action = AuditLog.Action.CREATE if created else AuditLog.Action.UPDATE
    record(action, instance=instance, company=instance.company,
           detail=f'Scénario « {instance.nom} » {"créé" if created else "modifié"}.')
