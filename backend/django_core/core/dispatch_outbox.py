"""NTPLT10 — Worker de livraison de l'outbox + retries + dead-letter.

``dispatch_pending(now, limit)`` livre chaque ``OutboxEvent`` livrable (statut
``pending`` ou ``failed`` dont ``prochaine_tentative`` est échue) aux handlers
DURABLES enregistrés (``core.events.subscribe_durable``). Garanties :

* **at-least-once + dédup consommateur** : chaque (event_id, handler) n'a
  d'effet qu'une fois (contrainte unique ``core.ProcessedEvent``) — un crash
  worker ne double-livre jamais ;
* **retries exponentiels bornés** : 1 min → 1 h, plafonnés à ``MAX_ATTEMPTS``
  (8) tentatives, puis statut ``dead`` (dead-letter) ;
* **idempotent** : ré-exécuter le worker ne rejoue pas un événement déjà livré.

La tâche Celery ``core.dispatch_outbox`` (dans ``core/tasks.py``) n'est qu'une
enveloppe autour de ``dispatch_pending``. ``core`` reste fondation : aucun
import d'app métier (les handlers s'enregistrent eux-mêmes).
"""
from __future__ import annotations

import logging
from datetime import timedelta

logger = logging.getLogger(__name__)

# Retries exponentiels bornés : délai = min(BASE * 2**tentatives, MAX_DELAY).
MAX_ATTEMPTS = 8
_BASE_DELAY = timedelta(minutes=1)
_MAX_DELAY = timedelta(hours=1)


def _next_delay(tentatives: int) -> timedelta:
    """Backoff exponentiel borné : 1 min, 2, 4, … plafonné à 1 h."""
    seconds = _BASE_DELAY.total_seconds() * (2 ** max(0, tentatives))
    return timedelta(seconds=min(seconds, _MAX_DELAY.total_seconds()))


def _already_processed(event_id, handler_name) -> bool:
    from .models import ProcessedEvent
    return ProcessedEvent.objects.filter(
        event_id=event_id, handler_name=handler_name).exists()


def _mark_processed(event_id, handler_name) -> None:
    from django.db import IntegrityError
    from .models import ProcessedEvent
    try:
        ProcessedEvent.objects.create(
            event_id=event_id, handler_name=handler_name)
    except IntegrityError:
        # Course : un autre worker a déjà marqué ce (event_id, handler) →
        # bénin (la dédup a justement fait son travail).
        pass


def deliver_one(event) -> bool:
    """Livre UN ``OutboxEvent`` à tous ses handlers durables (dédupliqué).

    Renvoie True si TOUS les handlers ont réussi (ou étaient déjà traités) →
    l'événement passe ``delivered`` ; False si au moins un handler a échoué →
    l'appelant applique le backoff / dead-letter.
    """
    from core import events

    handlers = events.durable_handlers(event.event_name)
    all_ok = True
    for handler_name, handler, _rejouable in handlers:
        if _already_processed(event.event_id, handler_name):
            continue
        try:
            handler(event)
            _mark_processed(event.event_id, handler_name)
        except Exception:  # noqa: BLE001 — un handler KO n'arrête pas les autres
            logger.exception(
                'dispatch_outbox: handler %s a échoué sur %s',
                handler_name, event.event_id)
            all_ok = False
    return all_ok


def dispatch_pending(now=None, limit: int = 500) -> dict:
    """Livre les événements outbox livrables. Idempotent.

    Sélectionne jusqu'à ``limit`` événements ``pending`` ou ``failed`` dont
    ``prochaine_tentative`` est échue, les livre, et applique statut/backoff/
    dead-letter. Renvoie un compte ``{delivered, failed, dead, scanned}``.
    """
    from django.db.models import Q
    from django.utils import timezone

    from .models import OutboxEvent

    now = now or timezone.now()
    livrables = OutboxEvent.objects.filter(
        Q(statut=OutboxEvent.STATUT_PENDING)
        | Q(statut=OutboxEvent.STATUT_FAILED,
            prochaine_tentative__lte=now)
    ).order_by('created_at')[:limit]

    counts = {'delivered': 0, 'failed': 0, 'dead': 0, 'scanned': 0}
    for event in livrables:
        counts['scanned'] += 1
        ok = deliver_one(event)
        if ok:
            event.statut = OutboxEvent.STATUT_DELIVERED
            event.prochaine_tentative = None
            event.save(update_fields=['statut', 'prochaine_tentative',
                                      'updated_at'])
            counts['delivered'] += 1
            continue
        event.tentatives += 1
        if event.tentatives >= MAX_ATTEMPTS:
            event.statut = OutboxEvent.STATUT_DEAD
            event.prochaine_tentative = None
            counts['dead'] += 1
        else:
            event.statut = OutboxEvent.STATUT_FAILED
            event.prochaine_tentative = now + _next_delay(event.tentatives)
            counts['failed'] += 1
        event.save(update_fields=['statut', 'tentatives',
                                  'prochaine_tentative', 'updated_at'])
    return counts


def replay(event) -> dict:
    """Re-livre un ``OutboxEvent`` (support) : repasse ``pending`` + livre.

    Réinitialise le statut à ``pending`` (sans toucher aux ``ProcessedEvent``
    déjà posés — la dédup empêche un handler déjà réussi de rejouer) puis tente
    une livraison immédiate. Utilisé par l'action ``rejouer`` de l'endpoint."""
    from django.utils import timezone
    from .models import OutboxEvent

    event.statut = OutboxEvent.STATUT_PENDING
    event.prochaine_tentative = None
    event.save(update_fields=['statut', 'prochaine_tentative', 'updated_at'])
    ok = deliver_one(event)
    if ok:
        event.statut = OutboxEvent.STATUT_DELIVERED
        event.save(update_fields=['statut', 'updated_at'])
    return {'event_id': str(event.event_id), 'delivered': ok,
            'at': timezone.now().isoformat()}
