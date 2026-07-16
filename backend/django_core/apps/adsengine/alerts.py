"""ENG13 — Alertes moteur WhatsApp-first (rendu + deep-link, envoi gated).

Ce module RÉEND les alertes du moteur en messages FR courts avec un deep-link
``wa.me`` vers les destinataires (Reda / Meryem) — mais **n'ENVOIE rien** :
l'envoi réel via template WhatsApp Business (BSP) est une décision fondateur
GATED (voir la liste GATED ENG de PLAN.md). Ici on rend + on liste seulement.

``create_alert`` est le point d'entrée que le moteur de garde-fous (ENG9) branche
via ``guardrails.emit_alert`` : une violation / anomalie / règle inopérante crée
une ligne ``EngineAlert`` (persistée, listable par le dashboard ENG23).

Destinataires : lus depuis ``ADSENGINE_ALERT_RECIPIENTS`` (numéros séparés par
des virgules) — jamais un numéro personnel codé en dur. Sans destinataire, le
lien ``wa.me`` ouvre WhatsApp sans numéro pré-rempli (choix manuel).
"""
from __future__ import annotations

import os
from urllib.parse import quote


def alert_recipients():
    """Numéros destinataires (WhatsApp) depuis l'environnement, ou liste vide."""
    raw = os.environ.get('ADSENGINE_ALERT_RECIPIENTS', '') or ''
    return [n.strip() for n in raw.split(',') if n.strip()]


def wa_link(message, recipient=None):
    """Deep-link ``wa.me`` avec le message pré-rempli (URL-encodé).

    ``recipient`` fourni → ``https://wa.me/<numéro>?text=…`` ; sinon
    ``https://wa.me/?text=…`` (WhatsApp demande le destinataire). Jamais de
    numéro personnel codé en dur."""
    text = quote(message or '')
    if recipient:
        num = str(recipient).lstrip('+').replace(' ', '')
        return f'https://wa.me/{num}?text={text}'
    return f'https://wa.me/?text={text}'


def wa_links(message):
    """Un deep-link par destinataire configuré (liste). Vide → un lien sans
    numéro (choix manuel du destinataire)."""
    recipients = alert_recipients()
    if not recipients:
        return [wa_link(message)]
    return [wa_link(message, r) for r in recipients]


def create_alert(company, *, alert_type, message, action=None, detail=None):
    """ENG13 — Matérialise une ``EngineAlert`` (branché par ENG9 ``emit_alert``).

    Renvoie l'instance créée. La construction du deep-link ``wa.me`` reste au
    moment du RENDU (serializer / dashboard) — on ne stocke que le message FR."""
    from .models import EngineAlert

    return EngineAlert.objects.create(
        company=company, alert_type=alert_type, message=message,
        action=action, detail=detail or {})
