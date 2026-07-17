"""NTAPI8 — reprises PROGRAMMÉES (long-tail) à backoff exponentiel des
livraisons webhook en échec.

Distinct des reprises Celery immédiates (YAPIC8, `tasks.deliver_webhook`,
backoff court borné à ~10 min) : ce mécanisme prend le relais UNE FOIS ces
reprises rapides épuisées, à une cadence humaine — 1 min, 5 min, 30 min, 2 h,
6 h — jusqu'à 6 tentatives au TOTAL (l'envoi original + 5 reprises
programmées). Rejoué par la commande `retry_webhook_deliveries`
(idempotente : ne retraite QUE les tentatives dont `prochain_essai_at` est
échu ET `statut='en_attente'`).

Le succès final marque la `WebhookDelivery` d'origine `SUCCESS` (aucun
doublon métier créé — un seul enregistrement canonique par livraison) ; un
abandon après 6 tentatives la marque `EN_ECHEC` (distinct de `FAILED`,
encore retentable).
"""
from __future__ import annotations

from datetime import timedelta

from django.utils import timezone

from .delivery import DELIVERY_ATTEMPT_HEADER, _send
from .models import WebhookDelivery, WebhookDeliveryAttempt

# Délai AVANT la tentative N (N = 2..6), indexé par (N - 2) : 1 min, 5 min,
# 30 min, 2 h, 6 h. 5 délais → 5 reprises programmées → 6 tentatives au total
# avec l'envoi original (tentative 1, déjà journalisé sur `WebhookDelivery`).
RETRY_DELAYS_SECONDS = [60, 300, 1800, 7200, 21600]
MAX_ATTEMPTS = 1 + len(RETRY_DELAYS_SECONDS)  # 6


def schedule_first_retry(webhook_delivery, *, now=None):
    """Programme la tentative 2 après l'échec de l'envoi ORIGINAL (tentative
    1, déjà journalisé sur `webhook_delivery`). No-op (idempotent) si une
    reprise existe déjà pour cette livraison, ou si elle n'est pas en échec
    retentable (`FAILED` — ni `SUCCESS` ni `EN_ECHEC`, ni bloqué SSRF, qui
    n'est jamais journalisé comme `FAILED` par `delivery._record`... en
    réalité SI, cf. `_send` 'blocked' → outcome mappé sur FAILED côté
    appelant historique ; ce module ne peut pas distinguer un blocage SSRF
    a posteriori et retentera — la garde anti-SSRF de `_send` s'applique de
    toute façon à CHAQUE tentative, donc un hôte bloqué échoue encore et finit
    par s'arrêter après `MAX_ATTEMPTS`, jamais bloquant indéfiniment)."""
    if webhook_delivery.status != WebhookDelivery.Statut.FAILED:
        return None
    if WebhookDeliveryAttempt.objects.filter(delivery=webhook_delivery).exists():
        return None
    now = now or timezone.now()
    return WebhookDeliveryAttempt.objects.create(
        company_id=webhook_delivery.company_id,
        delivery=webhook_delivery,
        numero_tentative=2,
        prochain_essai_at=now + timedelta(seconds=RETRY_DELAYS_SECONDS[0]),
        statut=WebhookDeliveryAttempt.Statut.EN_ATTENTE,
    )


def run_due_retries(now=None):
    """Traite TOUTE tentative programmée échue (idempotent — un run répété
    sans nouvelles tentatives dues ne fait rien). Renvoie la liste des
    `WebhookDeliveryAttempt` traitées (pour logging/tests)."""
    now = now or timezone.now()
    due = list(
        WebhookDeliveryAttempt.objects.select_related('delivery', 'delivery__webhook')
        .filter(statut=WebhookDeliveryAttempt.Statut.EN_ATTENTE,
                prochain_essai_at__lte=now)
    )
    return [_process_attempt(attempt, now=now) for attempt in due]


def _process_attempt(attempt, *, now):
    wh_delivery = attempt.delivery
    webhook = wh_delivery.webhook

    if webhook is None or not webhook.enabled:
        # Cible désactivée entre-temps : abandon propre, jamais de reprise
        # vers une cible qu'un admin a désactivée explicitement.
        attempt.statut = WebhookDeliveryAttempt.Statut.ECHEC
        attempt.prochain_essai_at = None
        attempt.save(update_fields=['statut', 'prochain_essai_at'])
        return attempt

    extra_headers = {DELIVERY_ATTEMPT_HEADER: str(attempt.numero_tentative)}
    outcome, response_status, error = _send(
        webhook, wh_delivery.event, wh_delivery.payload,
        extra_headers=extra_headers)

    if outcome == 'success':
        attempt.statut = WebhookDeliveryAttempt.Statut.SUCCES
        attempt.prochain_essai_at = None
        attempt.save(update_fields=['statut', 'prochain_essai_at'])
        WebhookDelivery.objects.filter(pk=wh_delivery.pk).update(
            status=WebhookDelivery.Statut.SUCCESS,
            response_status=response_status, error='')
        return attempt

    attempt.statut = WebhookDeliveryAttempt.Statut.ECHEC
    attempt.prochain_essai_at = None
    attempt.save(update_fields=['statut', 'prochain_essai_at'])

    if attempt.numero_tentative >= MAX_ATTEMPTS:
        # Cible morte : abandon définitif après la cascade complète.
        WebhookDelivery.objects.filter(pk=wh_delivery.pk).update(
            status=WebhookDelivery.Statut.EN_ECHEC, error=(error or '')[:1000])
        return attempt

    next_numero = attempt.numero_tentative + 1
    delay_seconds = RETRY_DELAYS_SECONDS[attempt.numero_tentative - 1]
    WebhookDeliveryAttempt.objects.create(
        company_id=attempt.company_id,
        delivery=wh_delivery,
        numero_tentative=next_numero,
        prochain_essai_at=now + timedelta(seconds=delay_seconds),
        statut=WebhookDeliveryAttempt.Statut.EN_ATTENTE,
    )
    return attempt
