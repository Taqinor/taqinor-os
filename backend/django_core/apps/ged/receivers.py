"""Récepteurs d'événements métier (M6) — ZGED6.

Abonne ``ged`` à l'événement ``document_produit`` exposé par ``core.events``,
pour centraliser un fichier produit par une autre app (paie/rh/sav/ventes…)
SANS que ``ged`` importe cette app ni l'inverse. Câblé au démarrage par
``GedConfig.ready``.
"""
import logging

from django.dispatch import receiver

from core.events import document_produit

logger = logging.getLogger(__name__)


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
