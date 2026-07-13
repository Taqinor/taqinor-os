"""Tâches Celery de l'app publicapi — auto-découvertes par
`erp_agentique.celery` (`app.autodiscover_tasks()`), aucun enregistrement
manuel requis.

YAPIC8 — livraison fiable des webhooks : `deliver_webhook` effectue UNE
tentative HTTP signée, journalise le résultat, puis re-tente avec un backoff
exponentiel + jitter dans une fenêtre bornée (`max_retries=8`). Toutes les
tentatives partagent le même `event_id` (porté par le payload). Best-effort :
le broker/HTTP ne bloque jamais l'appelant métier.
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
    delivery._record(webhook, event, payload,
                     status=status, response_status=response_status,
                     error=error)

    if outcome == 'failed':
        try:
            # retry_backoff calcule le délai (countdown) automatiquement.
            raise self.retry(exc=Exception(error or 'webhook delivery failed'))
        except self.MaxRetriesExceededError:
            logger.warning('Webhook %s en échec après %s reprises',
                           webhook_id, self.max_retries)
    return outcome
