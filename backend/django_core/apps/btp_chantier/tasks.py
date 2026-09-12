"""AUD231 — job planifié BTP : alerte quotidienne des RFI en retard (NTCON4).

Défaut d'origine : la commande de gestion ``alertes_rfi_retard`` ouvrait sur
« Sweep quotidien : alerte les RFI en retard (Celery beat) » — et le grep sur
``erp_agentique/`` rendait ZÉRO : aucune entrée de ``beat_schedule``, aucune
tâche Celery. Aucun RFI en retard n'a donc jamais été alerté automatiquement.

Autodécouvert par ``erp_agentique.celery`` (``autodiscover_tasks()``).
L'enveloppe appelle le SERVICE ``services.alerter_rfi_en_retard`` — l'unique
implémentation, partagée avec la commande de gestion.
"""
import logging

from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task(name='btp_chantier.alertes_rfi_retard')
def alertes_rfi_retard_task():
    """NTCON4 (AUD231) — notifie le destinataire ET le créateur de tout RFI
    ouvert dont la date limite de réponse est dépassée. Idempotente : une seule
    alerte par jour et par RFI. Renvoie le nombre d'alertes envoyées."""
    from .services import alerter_rfi_en_retard
    try:
        return alerter_rfi_en_retard()['alertes_envoyees']
    except Exception:  # noqa: BLE001 — best-effort, jamais bloquant
        logger.warning('btp_chantier.alertes_rfi_retard: échec du balayage',
                       exc_info=True)
        return 0


@shared_task(name='btp_chantier.archiver_reserves_levees')
def archiver_reserves_levees_task():
    """NTCON27 — archive (drapeau, jamais suppression) les réserves levées
    depuis plus de N mois (réglage par société, défaut 24). Idempotente :
    une réserve déjà archivée est exclue du balayage. Renvoie le nombre de
    réserves archivées."""
    from .services import archiver_reserves_levees
    try:
        return archiver_reserves_levees()['archivees']
    except Exception:  # noqa: BLE001 — best-effort, jamais bloquant
        logger.warning(
            'btp_chantier.archiver_reserves_levees: échec du balayage',
            exc_info=True)
        return 0


@shared_task(name='btp_chantier.rapport_photo_hebdo')
def rapport_photo_hebdo_task():
    """NTCON18 — envoie le photo-rapport hebdomadaire aux chantiers ABONNÉS
    (opt-in strict). Key-gated : sans clé email configurée, no-op propre.
    Renvoie le nombre de rapports envoyés."""
    from .services import envoyer_rapports_photo_hebdo
    try:
        return envoyer_rapports_photo_hebdo()['envoyes']
    except Exception:  # noqa: BLE001 — best-effort, jamais bloquant
        logger.warning('btp_chantier.rapport_photo_hebdo: échec du balayage',
                       exc_info=True)
        return 0
