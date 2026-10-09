"""Récepteurs d'événements métier (M6) — ZGED6.

Abonne ``ged`` à l'événement ``document_produit`` exposé par ``core.events``,
pour centraliser un fichier produit par une autre app (paie/rh/sav/ventes…)
SANS que ``ged`` importe cette app ni l'inverse. Câblé au démarrage par
``GedConfig.ready``.

WIR165 — premier ÉMETTEUR RÉEL : ``apps/ventes/utils/pdf.py``
``generate_facture_pdf`` émet ``document_produit(source='ventes_facture', …)``
juste après avoir stocké le PDF de facture (best-effort, ne bloque jamais la
génération). Ce récepteur reste no-op tant qu'aucun ``RoutageDocumentaire``
actif n'existe pour cette ``source`` — un admin l'active en créant un
``RoutageDocumentaire(source='ventes_facture', …)`` pour sa société.
"""
import logging

from django.db.models.signals import post_save, pre_delete
from django.dispatch import receiver

from core.events import document_produit

logger = logging.getLogger(__name__)


@receiver(post_save, sender='authentication.Company',
          dispatch_uid='ged_adoc75_routages_defaut_societe')
def _semer_routages_defaut_societe(sender, instance, created, raw=False,
                                   **kwargs):
    """ADOC75 — une société NOUVELLE reçoit les routages ventes par défaut
    (factures/avoirs/notes de débit/remises arrivent en GED sans réglage
    manuel). Best-effort : ne bloque jamais la création de la société."""
    if not created or raw:
        return
    try:
        from . import services

        services.semer_routages_defaut(instance)
    except Exception:  # pragma: no cover - défensif (best-effort)
        logger.exception(
            "ADOC75 — échec du semis des routages par défaut (société %s)",
            getattr(instance, 'pk', None))


@receiver(pre_delete, sender='ged.Document',
          dispatch_uid='ged_adoc2_garde_suppression_document')
def _garde_suppression_document(sender, instance, **kwargs):
    """ADOC2 — même garde que ``Document.delete`` sur le chemin CASCADE
    (suppression d'un dossier, d'une armoire, d'une société…) : un document
    archivé légalement ou sous legal hold ne disparaît jamais ; l'exception
    annule la transaction de la cascade entière."""
    from .models import (
        ARCHIVE_LEGALE_MESSAGE, LEGAL_HOLD_MESSAGE, ArchivageLegalError,
        LegalHoldError,
    )
    if instance.pk is None:
        return
    if instance.est_archive_legalement:
        raise ArchivageLegalError(ARCHIVE_LEGALE_MESSAGE)
    if instance.est_sous_legal_hold:
        raise LegalHoldError(LEGAL_HOLD_MESSAGE)


@receiver(pre_delete, sender='ged.DocumentVersion',
          dispatch_uid='ged_adoc2_garde_suppression_version')
def _garde_suppression_version(sender, instance, **kwargs):
    """ADOC2 — miroir de ``DocumentVersion.delete`` sur le chemin CASCADE."""
    from .models import (
        ARCHIVE_LEGALE_MESSAGE, LEGAL_HOLD_MESSAGE, ArchivageLegal,
        ArchivageLegalError, LegalHold, LegalHoldError,
    )
    if instance.document_id is None:
        return
    if ArchivageLegal.objects.filter(document_id=instance.document_id).exists():
        raise ArchivageLegalError(ARCHIVE_LEGALE_MESSAGE)
    if LegalHold.objects.filter(
            document_id=instance.document_id, actif=True).exists():
        raise LegalHoldError(LEGAL_HOLD_MESSAGE)


@receiver(document_produit, dispatch_uid="ged_router_on_document_produit")
def _router_document_on_document_produit(
        sender, source, company, file, filename='', reference='',
        contexte=None, uploaded_by=None, **kwargs):
    """ZGED6 — centralise le fichier émis dans le dossier GED configuré pour
    cette ``source`` (via ``RoutageDocumentaire``), si un réglage existe.

    No-op silencieux sans réglage pour cette source (comportement actuel
    inchangé). Best-effort : une erreur ne doit jamais remonter à
    l'émetteur (son propre traitement est déjà acté)."""
    try:
        from . import services

        services.router_document_module(
            source, company=company, file=file, filename=filename,
            reference=reference, contexte=contexte or {},
            uploaded_by=uploaded_by)
    except Exception:  # pragma: no cover - défensif (best-effort)
        logger.exception(
            "ZGED6 — échec du routage documentaire pour source=%s", source)
