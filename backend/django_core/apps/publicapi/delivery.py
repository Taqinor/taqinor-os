"""Service de livraison des webhooks (N89).

POST best-effort, signé HMAC-SHA256, vers chaque webhook activé d'une société
abonné à l'évènement. Chaque tentative est journalisée dans WebhookDelivery.
Jamais bloquant : toute exception est attrapée et tracée, l'enregistrement
métier d'origine n'est pas affecté.
"""
import hashlib
import hmac
import json
import logging

import httpx

from .models import Webhook, WebhookDelivery
from .validators import UnsafeWebhookURL, validate_webhook_target_url

logger = logging.getLogger(__name__)

# En-tête portant la signature HMAC-SHA256 (hex) du corps brut.
SIGNATURE_HEADER = 'X-Taqinor-Signature'
EVENT_HEADER = 'X-Taqinor-Event'
DELIVERY_TIMEOUT = 5.0  # secondes


def sign_payload(secret, body_bytes):
    """Signature HMAC-SHA256 (hex) du corps brut avec le secret du webhook."""
    return hmac.new(
        secret.encode('utf-8'), body_bytes, hashlib.sha256
    ).hexdigest()


def _deliver_one(webhook, event, payload):
    """Livre un évènement à UN webhook. Journalise toujours, ne lève jamais."""
    # ERR46 — Garde-fou anti-SSRF AU MOMENT de la livraison (defense-in-depth) :
    # même si une URL interne a été stockée avant ce correctif — ou si le DNS a
    # été ré-pointé depuis (DNS rebinding) — on ne POST jamais vers un hôte
    # interne. On journalise un échec auditable et on s'arrête.
    try:
        validate_webhook_target_url(webhook.target_url)
    except UnsafeWebhookURL as exc:
        logger.warning('Webhook delivery blocked (SSRF) (%s): %s',
                       webhook.target_url, exc)
        try:
            WebhookDelivery.objects.create(
                company_id=webhook.company_id,
                webhook=webhook,
                event=event,
                payload=payload,
                status=WebhookDelivery.Statut.FAILED,
                response_status=None,
                error=f'URL bloquée (SSRF) : {exc}'[:1000],
            )
        except Exception:  # noqa: BLE001 — ne jamais propager
            logger.exception('Could not log blocked webhook delivery')
        return
    body_bytes = json.dumps(payload, default=str, sort_keys=True).encode('utf-8')
    signature = sign_payload(webhook.secret, body_bytes)
    headers = {
        'Content-Type': 'application/json',
        SIGNATURE_HEADER: signature,
        EVENT_HEADER: event,
    }
    try:
        resp = httpx.post(
            webhook.target_url, content=body_bytes,
            headers=headers, timeout=DELIVERY_TIMEOUT)
        ok = 200 <= resp.status_code < 300
        WebhookDelivery.objects.create(
            company_id=webhook.company_id,
            webhook=webhook,
            event=event,
            payload=payload,
            status=(WebhookDelivery.Statut.SUCCESS if ok
                    else WebhookDelivery.Statut.FAILED),
            response_status=resp.status_code,
            error='' if ok else f'HTTP {resp.status_code}',
        )
    except Exception as exc:  # noqa: BLE001 — best-effort, jamais bloquant
        logger.warning('Webhook delivery failed (%s): %s', webhook.target_url, exc)
        try:
            WebhookDelivery.objects.create(
                company_id=webhook.company_id,
                webhook=webhook,
                event=event,
                payload=payload,
                status=WebhookDelivery.Statut.FAILED,
                response_status=None,
                error=str(exc)[:1000],
            )
        except Exception:  # noqa: BLE001 — ne jamais propager
            logger.exception('Could not log webhook delivery failure')


def dispatch_event(company_id, event, payload):
    """Livre `event` à tous les webhooks activés de la société qui y sont
    abonnés. Best-effort, jamais bloquant pour l'appelant."""
    if not company_id:
        return
    try:
        webhooks = list(
            Webhook.objects.filter(company_id=company_id, enabled=True))
    except Exception:  # noqa: BLE001
        logger.exception('Could not load webhooks for company %s', company_id)
        return
    for webhook in webhooks:
        if webhook.subscribes_to(event):
            _deliver_one(webhook, event, payload)
