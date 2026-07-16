"""Service de livraison des webhooks (N89 ; fiabilisé YAPIC8).

POST best-effort, signé HMAC-SHA256, vers chaque webhook activé d'une société
abonnée à l'évènement. Chaque tentative est journalisée dans WebhookDelivery.
Jamais bloquant : toute exception est attrapée et tracée, l'enregistrement
métier d'origine n'est pas affecté.

YAPIC8 — livraison FIABLE :
  * l'émission automatique passe par une tâche Celery (`tasks.deliver_webhook`)
    avec backoff exponentiel + jitter et fenêtre de reprise bornée ;
  * la signature HMAC couvre un horodatage (`X-Taqinor-Timestamp` concaténé au
    corps : ``f"{timestamp}.".encode() + body``) — un rejeu hors tolérance est
    rejetable par le receveur ;
  * un ``event_id`` (uuid4) STABLE est posé dans le payload, réutilisé à
    l'identique par le replay (FG102) et partagé par toutes les tentatives.
"""
import hashlib
import hmac
import json
import logging
import time
import uuid

import httpx

from .models import Webhook, WebhookDelivery
from .validators import UnsafeWebhookURL, validate_webhook_target_url

logger = logging.getLogger(__name__)

# En-tête portant la signature HMAC-SHA256 (hex) de `timestamp.body`.
SIGNATURE_HEADER = 'X-Taqinor-Signature'
EVENT_HEADER = 'X-Taqinor-Event'
# YAPIC8 — horodatage d'émission (epoch secondes) COUVERT par la signature.
TIMESTAMP_HEADER = 'X-Taqinor-Timestamp'
# Clé stable d'identité d'évènement dans le payload (uuid4).
EVENT_ID_KEY = 'event_id'
# NTAPI8 — numéro de la tentative PROGRAMMÉE (long-tail, `retry.py`) en cours,
# posé uniquement par ces reprises (absent de l'envoi original/des reprises
# Celery immédiates YAPIC8).
DELIVERY_ATTEMPT_HEADER = 'X-Taqinor-Delivery-Attempt'
DELIVERY_TIMEOUT = 5.0  # secondes


def sign_payload(secret, body_bytes, timestamp=None):
    """Signature HMAC-SHA256 (hex) du corps brut avec le secret du webhook.

    YAPIC8 : si ``timestamp`` est fourni, la signature couvre
    ``f"{timestamp}.".encode() + body_bytes`` (protection anti-rejeu). Sans
    timestamp, comportement historique (corps seul) — conservé pour compat.
    """
    if timestamp is not None:
        body_bytes = f'{timestamp}.'.encode('utf-8') + body_bytes
    return hmac.new(
        secret.encode('utf-8'), body_bytes, hashlib.sha256
    ).hexdigest()


def ensure_event_id(payload):
    """Retourne un payload portant un ``event_id`` stable (uuid4), sans muter
    l'original s'il en a déjà un. Réutilisé à l'identique par le replay."""
    if isinstance(payload, dict) and payload.get(EVENT_ID_KEY):
        return payload
    new = dict(payload) if isinstance(payload, dict) else {'data': payload}
    new[EVENT_ID_KEY] = str(uuid.uuid4())
    return new


def _record(webhook, event, payload, *, status, response_status, error):
    """Journalise UNE tentative dans WebhookDelivery. Ne lève jamais.

    Renvoie l'instance créée (ou ``None`` si la journalisation elle-même a
    échoué) — NTAPI8 s'en sert pour programmer la première reprise
    long-tail sans dupliquer la requête de lecture."""
    try:
        return WebhookDelivery.objects.create(
            company_id=webhook.company_id,
            webhook=webhook,
            event=event,
            payload=payload,
            event_id=(payload.get(EVENT_ID_KEY, '')
                      if isinstance(payload, dict) else ''),
            status=status,
            response_status=response_status,
            error=(error or '')[:1000],
        )
    except Exception:  # noqa: BLE001 — ne jamais propager
        logger.exception('Could not log webhook delivery')
        return None


def _send(webhook, event, payload, extra_headers=None):
    """Effectue UNE tentative HTTP signée. Retourne
    ``(outcome, response_status, error)`` avec ``outcome`` ∈
    {'success', 'failed', 'blocked'}. Ne lève jamais.

    'blocked' = cible SSRF (permanent, ne pas retenter) ; 'failed' =
    non-2xx ou erreur réseau (retentable) ; 'success' = 2xx.

    ``extra_headers`` (NTAPI8) : en-têtes additionnels fusionnés APRÈS les
    en-têtes standards (ex. ``X-Taqinor-Delivery-Attempt`` posé par les
    reprises programmées `retry.py`) — jamais utilisé par l'envoi original.
    """
    # ERR46 — garde-fou anti-SSRF AU MOMENT de la livraison (defense-in-depth) :
    # même si une URL interne a été stockée avant, ou si le DNS a été ré-pointé
    # (rebinding), on ne POST jamais vers un hôte interne.
    try:
        validate_webhook_target_url(webhook.target_url)
    except UnsafeWebhookURL as exc:
        logger.warning('Webhook delivery blocked (SSRF) (%s): %s',
                       webhook.target_url, exc)
        return 'blocked', None, f'URL bloquée (SSRF) : {exc}'

    body_bytes = json.dumps(payload, default=str, sort_keys=True).encode('utf-8')
    timestamp = str(int(time.time()))
    signature = sign_payload(webhook.secret, body_bytes, timestamp=timestamp)
    headers = {
        'Content-Type': 'application/json',
        SIGNATURE_HEADER: signature,
        TIMESTAMP_HEADER: timestamp,
        EVENT_HEADER: event,
    }
    if extra_headers:
        headers.update(extra_headers)
    try:
        resp = httpx.post(
            webhook.target_url, content=body_bytes,
            headers=headers, timeout=DELIVERY_TIMEOUT)
    except Exception as exc:  # noqa: BLE001 — best-effort
        logger.warning('Webhook delivery failed (%s): %s',
                       webhook.target_url, exc)
        return 'failed', None, str(exc)
    ok = 200 <= resp.status_code < 300
    return ('success' if ok else 'failed'), resp.status_code, (
        '' if ok else f'HTTP {resp.status_code}')


def _deliver_one(webhook, event, payload):
    """Livre un évènement à UN webhook, de façon SYNCHRONE, en journalisant une
    tentative. Ne lève jamais. Utilisé par le replay/test manuels (FG102) —
    l'émission automatique passe par la tâche Celery `tasks.deliver_webhook`."""
    payload = ensure_event_id(payload)
    outcome, response_status, error = _send(webhook, event, payload)
    status = (WebhookDelivery.Statut.SUCCESS if outcome == 'success'
              else WebhookDelivery.Statut.FAILED)
    _record(webhook, event, payload,
            status=status, response_status=response_status, error=error)
    return outcome


def dispatch_event(company_id, event, payload):
    """Livre `event` à tous les webhooks activés de la société abonnés, via la
    tâche Celery `deliver_webhook` (retries + backoff). Best-effort, jamais
    bloquant pour l'appelant. Le même `event_id` est partagé par toutes les
    cibles et toutes les tentatives."""
    if not company_id:
        return
    try:
        webhooks = list(
            Webhook.objects.filter(company_id=company_id, enabled=True))
    except Exception:  # noqa: BLE001
        logger.exception('Could not load webhooks for company %s', company_id)
        return
    payload = ensure_event_id(payload)
    from .tasks import deliver_webhook
    for webhook in webhooks:
        if not webhook.subscribes_to(event):
            continue
        try:
            deliver_webhook.delay(webhook.id, event, payload)
        except Exception:  # noqa: BLE001 — broker indisponible ne bloque jamais
            logger.exception('Could not enqueue webhook delivery %s', webhook.id)
