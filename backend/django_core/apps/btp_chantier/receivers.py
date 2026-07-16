"""Abonnements de ``btp_chantier`` aux signaux d'autres apps.

NTCON5 — ré-ouvre automatiquement tout ``VisaDocument`` (statut → soumis)
quand une nouvelle ``ged.DocumentVersion`` est déposée sur le document visé.
Connexion PARESSEUSE via ``django.apps.apps.get_model`` dans
``connect_signals()`` (appelé depuis ``apps.py::ready()``) : aucun import
statique de ``ged.models`` (frontière cross-app, CLAUDE.md), signal Django
natif (``post_save``, ``sender=`` résolu par le registre d'apps) — ``ged``
n'émet pas encore d'événement dédié sur ``core/events.py`` pour ce cas.
"""
import logging

logger = logging.getLogger(__name__)


def _on_document_version_created(sender, instance, created, **kwargs):
    """NTCON5 — ré-ouvre les visas du document sur une NOUVELLE version."""
    if not created:
        return
    document_id = instance.document_id
    if not document_id:
        return
    try:
        from .services import resoumettre_visas_pour_document
        resoumettre_visas_pour_document(document_id)
    except Exception:  # pragma: no cover - défensif, jamais bloquant pour GED
        logger.warning(
            'btp_chantier: resoumission de visa échouée pour document %s',
            document_id, exc_info=True)


def connect_signals():
    """Point d'entrée appelé depuis ``BtpChantierConfig.ready()``."""
    from django.apps import apps as django_apps
    from django.db.models.signals import post_save

    try:
        DocumentVersion = django_apps.get_model('ged', 'DocumentVersion')
    except LookupError:  # pragma: no cover - ged non installé (jamais en prod)
        return
    post_save.connect(
        _on_document_version_created, sender=DocumentVersion,
        dispatch_uid='btp_chantier_resoumission_visa')


connect_signals()
