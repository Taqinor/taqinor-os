"""Tâches Celery de l'app publicapi — auto-découvertes par
`erp_agentique.celery` (`app.autodiscover_tasks()`), aucun enregistrement
manuel requis.

YAPIC8 — livraison fiable des webhooks : `deliver_webhook` effectue UNE
tentative HTTP signée, journalise le résultat, puis re-tente avec un backoff
exponentiel + jitter dans une fenêtre bornée (`max_retries=8`). Toutes les
tentatives partagent le même `event_id` (porté par le payload). Best-effort :
le broker/HTTP ne bloque jamais l'appelant métier.

NTAPI8 — une fois CETTE fenêtre rapide épuisée (`MaxRetriesExceededError`),
la cascade de reprises PROGRAMMÉES à cadence longue (`retry.py` — 1 min,
5 min, 30 min, 2 h, 6 h, jusqu'à 6 tentatives au total) prend le relais, via
la commande `retry_webhook_deliveries` (Celery-beat ou manuelle). Les deux
mécanismes ne se chevauchent jamais : le second ne démarre qu'après l'échec
DÉFINITIF du premier.
"""
import logging

from celery import shared_task

from . import delivery
from .models import Webhook, WebhookDelivery

logger = logging.getLogger(__name__)


@shared_task(
    name='publicapi.deliver_webhook',
    bind=True,
    max_retries=8,
    retry_backoff=True,        # 1s, 2s, 4s, 8s… (exponentiel)
    retry_backoff_max=600,     # plafonné à 10 min
    retry_jitter=True,         # jitter anti-thundering-herd
    acks_late=True,
)
def deliver_webhook(self, webhook_id, event, payload):
    """Livre `event`/`payload` à UN webhook (par PK) avec reprises bornées.

    Journalise CHAQUE tentative dans `WebhookDelivery` (même `event_id`). Une
    cible SSRF est un échec PERMANENT (aucune reprise). Un non-2xx / erreur
    réseau déclenche une reprise ; après la fenêtre, la dernière tentative
    reste `FAILED`.
    """
    try:
        webhook = Webhook.objects.get(id=webhook_id, enabled=True)
    except Webhook.DoesNotExist:
        logger.info('Webhook %s introuvable/désactivé — livraison ignorée',
                    webhook_id)
        return

    outcome, response_status, error = delivery._send(webhook, event, payload)
    status = (WebhookDelivery.Statut.SUCCESS if outcome == 'success'
              else WebhookDelivery.Statut.FAILED)
    record = delivery._record(webhook, event, payload,
                              status=status, response_status=response_status,
                              error=error)

    if outcome == 'failed':
        try:
            # retry_backoff calcule le délai (countdown) automatiquement.
            raise self.retry(exc=Exception(error or 'webhook delivery failed'))
        except self.MaxRetriesExceededError:
            logger.warning('Webhook %s en échec après %s reprises',
                           webhook_id, self.max_retries)
            # NTAPI8 — la fenêtre RAPIDE (Celery) est épuisée : programme la
            # cascade LONGUE (1 min, 5 min, 30 min, 2 h, 6 h) sur la dernière
            # tentative journalisée, best-effort (jamais bloquant ici).
            if record is not None:
                try:
                    from .retry import schedule_first_retry
                    schedule_first_retry(record)
                except Exception:  # noqa: BLE001
                    logger.exception(
                        'Could not schedule NTAPI8 long-tail retry for '
                        'delivery %s', record.pk)
    return outcome
