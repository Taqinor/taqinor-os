"""Registre GÉNÉRIQUE du notifieur (``core`` reste fondation, contrat
import-linter ``core-foundation-is-a-base-layer``) : ``core`` ne connaît
AUCUNE app métier, y compris ``apps.notifications`` — un import direct de
``notify()``/``EventType``, même fonction-local, est une arête interdite
(grimp voit tout import statique quel que soit son emplacement dans le
fichier — confirmé par ``lint-imports`` sur ce dépôt).

Même pattern ADDITIF que ``core.limits.register_limit_notifier`` /
``core.workflow.register_business_day_advance`` : ``apps.notifications``
enregistre son ``notify()`` réel dans SON PROPRE ``ready()`` ; ``core`` ne
connaît que ce callable, jamais l'app. ``event_type`` est passé en STRING
LITTÉRAL (la valeur brute d'``apps.notifications.models.EventType``, jamais
l'enum importé) — les appelants ``core`` documentent quelle constante
``EventType`` chaque littéral reflète.
"""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

# Callable(user, event_type, title, body='', link=None, company=None) -> Notification|None.
# Peuplé par apps.notifications dans son ready() ; None = no-op silencieux
# (app notifications absente/désactivée — jamais une exception).
_NOTIFY = None


def register_notify(fn) -> None:
    """Enregistre le notifieur réel (idempotent : remplace l'existant)."""
    global _NOTIFY
    _NOTIFY = fn


def unregister_notify() -> None:
    """Retire le notifieur (test uniquement — isole le registre)."""
    global _NOTIFY
    _NOTIFY = None


def notify(user, event_type, title, body='', link=None, company=None):
    """Relaie vers le notifieur enregistré. No-op silencieux (jamais une
    exception) si aucun notifieur n'est enregistré ou si l'appel échoue."""
    if _NOTIFY is None:
        logger.debug(
            'core.notify_registry.notify: aucun notifieur enregistré (%s).',
            event_type)
        return None
    try:
        return _NOTIFY(
            user, event_type, title, body=body, link=link, company=company)
    except Exception:  # noqa: BLE001 — best-effort, jamais bloquant
        logger.exception(
            'core.notify_registry.notify: échec pour %s.', event_type)
        return None
