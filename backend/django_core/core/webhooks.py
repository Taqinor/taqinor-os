"""FG376 — Connecteur Zapier / Make (REST hooks sortants), fondation.

Permet à un outil no-code (Zapier/Make) de s'abonner à un nom d'événement en
enregistrant une URL cible (``WebhookSubscription``), puis de recevoir un POST
quand l'événement se produit — SANS que ``core`` n'importe aucune app métier
(contrat import-linter ``core-foundation-is-a-base-layer``). L'app émettrice
passe un simple dict de payload.

Côté ACTIONS (déclencher une action ERP depuis Zapier) : c'est l'API publique
existante (``apps.publicapi``) qui les expose ; ``core`` ne s'en occupe pas et
ne l'importe pas.

Sécurité : si l'abonnement porte un ``secret``, le payload est signé en HMAC-
SHA256 (en-tête ``X-Taqinor-Signature``) pour que l'abonné vérifie l'origine.
Aucun appel réseau si la lib HTTP est absente (dégradation propre).
"""
from __future__ import annotations

import hashlib
import hmac
import json

from django.utils import timezone


def _sign(secret: str, body: bytes) -> str:
    """Signature HMAC-SHA256 hexadécimale du corps (vide si pas de secret)."""
    if not secret:
        return ''
    return hmac.new(secret.encode('utf-8'), body,
                    hashlib.sha256).hexdigest()


def _active_subscriptions(company, event):
    from .models import WebhookSubscription
    return list(WebhookSubscription.objects
                .filter(company=company, event=event, actif=True)
                .order_by('id'))


def _post(url: str, body: bytes, signature: str) -> int | None:
    """POST le payload ; renvoie le code HTTP ou ``None`` (réseau/lib absente)."""
    try:
        import requests
    except Exception:  # noqa: BLE001
        return None
    headers = {'Content-Type': 'application/json'}
    if signature:
        headers['X-Taqinor-Signature'] = signature
    try:
        resp = requests.post(url, data=body, headers=headers, timeout=10)
        return resp.status_code
    except Exception:  # noqa: BLE001 — réseau/transport.
        return None


def dispatch_event(company, event: str, payload: dict) -> dict:
    """Livre ``payload`` à tous les abonnés webhook actifs de l'événement.

    Multi-tenant : société imposée par l'appelant. Aucun abonné → no-op. Chaque
    livraison met à jour ``last_status`` / ``last_delivery_le`` sur l'abonnement
    (audit léger). Retourne ``{"delivered", "subscriptions"}``.
    """
    subs = _active_subscriptions(company, event)
    if not subs:
        return {'delivered': 0, 'subscriptions': 0}
    body = json.dumps(
        {'event': event, 'data': payload}, default=str).encode('utf-8')
    delivered = 0
    for sub in subs:
        status = _post(sub.target_url, body, _sign(sub.secret, body))
        sub.last_status = status
        sub.last_delivery_le = timezone.now()
        sub.save(update_fields=['last_status', 'last_delivery_le',
                                'updated_at'])
        if status is not None and 200 <= status < 300:
            delivered += 1
    return {'delivered': delivered, 'subscriptions': len(subs)}
