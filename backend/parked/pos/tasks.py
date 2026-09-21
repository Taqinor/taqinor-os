"""AUD231 — job planifié du POS : libération des réservations Click & Collect.

Défaut d'origine : la commande de gestion
``pos/management/commands/liberer_reservations_expirees.py`` annonçait dans sa
docstring « IDEMPOTENTE — sûre à ré-exécuter (Celery beat ou cron manuel) » et
``pos/models.py`` affirmait que les réservations étaient « libérée[s] par
services.liberer_reservations_expirees (Celery beat…) ». Le grep sur
``erp_agentique/`` rendait ZÉRO : aucune entrée de ``beat_schedule``, aucune
tâche Celery. Une réservation Click & Collect expirée n'était donc JAMAIS
libérée — son stock restait réservé indéfiniment tant que personne ne lançait
la commande à la main.

Autodécouvert par ``erp_agentique.celery`` (``autodiscover_tasks()``), comme
``apps.stock.tasks``/``apps.installations.tasks``. L'enveloppe appelle le
SERVICE (jamais la commande, ni une logique dupliquée).
"""
import logging

from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task(name='pos.liberer_reservations_expirees')
def liberer_reservations_expirees_task():
    """NTRET23 (AUD231) — libère les réservations Click & Collect dont le délai
    d'expiration configuré (Paramètres POS) est dépassé : annule la commande et
    ré-incrémente le stock si déjà sorti à la préparation. Toutes sociétés.

    Idempotente : ne sélectionne que les réservations A_PREPARER/PRET expirées
    — un re-run immédiat ne retrouve plus rien (déjà ANNULE). Renvoie le nombre
    de réservations libérées."""
    from . import services
    try:
        return services.liberer_reservations_expirees()
    except Exception:  # noqa: BLE001 — best-effort, jamais bloquant
        logger.warning(
            'pos.liberer_reservations_expirees: échec du balayage',
            exc_info=True)
        return 0
