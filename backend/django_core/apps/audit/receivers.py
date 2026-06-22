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

from core.events import document_pdf_generated

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
