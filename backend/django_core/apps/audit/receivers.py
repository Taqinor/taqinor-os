"""Récepteurs d'événements métier pour le Journal d'activité (M4).

Le satellite ``audit`` s'abonne aux événements du cœur métier exposés par
``core.events`` plutôt que d'être appelé directement par ``ventes`` — ce qui
supprime la dernière arête montante ``ventes → audit`` (``ventes`` n'importe
plus ``apps.audit``). Câblé au démarrage par ``AuditConfig.ready``.

Le signal ``document_pdf_generated`` est émis SYNCHRONEMENT depuis la vue
``generer_pdf`` de ventes (même requête) : l'acteur et la société sont donc
résolus paresseusement par ``recorder.record`` depuis la requête courante,
exactement comme l'ancien appel direct. Les lignes ``AuditLog`` produites sont
identiques 1:1 (même action ``PDF``, même cible, même détail, même acteur).
"""
from django.dispatch import receiver

from core.events import document_pdf_generated, devis_expired

from . import recorder
from .models import AuditLog

# Détail journalisé par type de document (identique à l'ancien appel direct).
_PDF_DETAIL = {
    'devis': 'PDF devis généré',
    'facture': 'PDF facture généré',
}


@receiver(document_pdf_generated,
          dispatch_uid='audit_record_on_document_pdf_generated')
def _record_pdf_generation(sender, instance, kind, **kwargs):
    """Journalise une entrée ``AuditLog.Action.PDF`` à la génération d'un PDF.

    Remplace, à l'identique, l'appel direct ``ventes → audit.recorder.record``
    qui se faisait aux sites de génération PDF (devis et facture). Best-effort :
    ``record`` n'élève jamais.
    """
    detail = _PDF_DETAIL.get(kind, 'PDF généré')
    recorder.record(AuditLog.Action.PDF, instance=instance, detail=detail)


@receiver(devis_expired,
          dispatch_uid='audit_record_on_devis_expired_system')
def _record_devis_expiration_systeme(sender, devis, ancien_statut, **kwargs):
    """YEVNT10 — journalise « système » (user=None) l'expiration AUTOMATIQUE
    d'un devis par le cron ``expire_stale_devis`` (hors requête HTTP), que
    l'audit par signaux request-scopé ne capte pas.

    Remplace l'ancien appel direct ``ventes → audit.recorder.record`` : ventes
    émet désormais ``devis_expired`` via ``core.events`` et l'audit s'y abonne
    ici (M4 — plus aucune arête montante ventes→audit). Best-effort : ``record``
    n'élève jamais.

    ARC16 (pilote #1) — passe par l'entonnoir ``record_field_change`` : la ligne
    ``AuditLog`` reste 1:1 (action STATUS, même devis, user=None, même détail)
    et gagne un diff structuré ``statut: ancien → expire``. ``chatter=False`` :
    expiration système hors requête, pas d'acteur — aucune note de chatter à
    poser (comportement inchangé).
    """
    recorder.record_field_change(
        devis, 'statut', ancien_statut, 'expire', user=None,
        field_label='Statut', action=AuditLog.Action.STATUS, chatter=False,
        detail='Expiration automatique (job : expire_stale_devis).')
