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
    from django.db import IntegrityError, transaction
    from .models import ProcessedEvent
    try:
        # NTPLT11 — point de sauvegarde propre : la collision ne casse jamais
        # la transaction englobante (livraison verrouillée, émetteur).
        with transaction.atomic():
            ProcessedEvent.objects.create(
                event_id=event_id, handler_name=handler_name)
    except IntegrityError:
        # Course : un autre worker a déjà marqué ce (event_id, handler) →
        # bénin (la dédup a justement fait son travail).
        pass


class EffetsPartiels(Exception):
    """NTPLT11 — levée par un handler durable dont CERTAINS effets ont réussi
    (et sont marqués ``marquer_effet_applique``) et d'autres non : à la
    différence d'une exception ordinaire, ses écritures ne sont PAS annulées
    (les marques restent), mais l'événement repasse en échec pour rejouer
    le reste."""


def effet_deja_applique(event, cle: str) -> bool:
    """NTPLT11 — dédup FINE à l'intérieur d'un handler durable.

    Un handler qui produit PLUSIEURS effets indépendants (ex. une mise en file
    par webhook abonné) marque chacun sous la clé ``cle`` : si l'effet n°2
    échoue, le rejeu ne refait PAS l'effet n°1. Même table/contrainte que la
    dédup par handler (``ProcessedEvent``), la clé tenant lieu de nom."""
    return _already_processed(event.event_id, cle)


def marquer_effet_applique(event, cle: str) -> None:
    """NTPLT11 — pose la marque de ``effet_deja_applique`` (idempotent)."""
    _mark_processed(event.event_id, cle)


def deliver_one(event) -> bool:
    """Livre UN ``OutboxEvent`` à tous ses handlers durables (dédupliqué).

    Renvoie True si TOUS les handlers ont réussi (ou étaient déjà traités) →
    l'événement passe ``delivered`` ; False si au moins un handler a échoué →
    l'appelant applique le backoff / dead-letter.
    """
    from core import events

    from django.db import transaction

    handlers = events.durable_handlers(event.event_name)
    all_ok = True
    for handler_name, handler, _rejouable in handlers:
        if _already_processed(event.event_id, handler_name):
            continue
        try:
            # NTPLT11 — effet + marque de dédup dans UN point de sauvegarde :
            # un handler qui échoue n'y laisse aucune écriture partielle (le
            # rejeu repart propre), un handler qui réussit est marqué avec
            # son effet (exactement-une-fois côté base).
            with transaction.atomic():
                try:
                    handler(event)
                except EffetsPartiels as partiel:
                    # Les effets déjà marqués (``marquer_effet_applique``)
                    # sont GARDÉS ; le handler n'est pas marqué traité : le
                    # rejeu ne refait que le reste.
                    logger.warning(
                        'dispatch_outbox: handler %s partiel sur %s (%s)',
                        handler_name, event.event_id, partiel)
                    all_ok = False
                    continue
                _mark_processed(event.event_id, handler_name)
        except Exception:  # noqa: BLE001 — un handler KO n'arrête pas les autres (D-ENF22-BLE001)
            logger.exception(
                'dispatch_outbox: handler %s a échoué sur %s',
                handler_name, event.event_id)
            all_ok = False
    return all_ok


def _appliquer_resultat(event, ok: bool, now) -> str:
    """Statut / backoff / dead-letter après UNE tentative de livraison.

    Renvoie ``'delivered'``, ``'failed'`` ou ``'dead'``."""
    from .models import OutboxEvent

    if ok:
        event.statut = OutboxEvent.STATUT_DELIVERED
        event.prochaine_tentative = None
        event.save(update_fields=['statut', 'prochaine_tentative',
                                  'updated_at'])
        return 'delivered'
    event.tentatives += 1
    if event.tentatives >= MAX_ATTEMPTS:
        event.statut = OutboxEvent.STATUT_DEAD
        event.prochaine_tentative = None
        resultat = 'dead'
    else:
        event.statut = OutboxEvent.STATUT_FAILED
        event.prochaine_tentative = now + _next_delay(event.tentatives)
        resultat = 'failed'
    event.save(update_fields=['statut', 'tentatives',
                              'prochaine_tentative', 'updated_at'])
    return resultat


def _filtre_livrables(now):
    from django.db.models import Q

    from .models import OutboxEvent

    return (Q(statut=OutboxEvent.STATUT_PENDING)
            | Q(statut=OutboxEvent.STATUT_FAILED,
                prochaine_tentative__lte=now))


def _livrer_verrouille(pk, now):
    """Livre UN événement sous verrou de ligne (``SKIP LOCKED``).

    NTPLT11 — le worker et la tentative immédiate (``livrer_maintenant``) ne
    livrent jamais la même ligne en même temps : celui qui ne prend pas le
    verrou passe son tour. Renvoie le résultat de ``_appliquer_resultat`` ou
    ``None`` (ligne verrouillée ailleurs / plus livrable)."""
    from django.db import transaction

    from .models import OutboxEvent

    with transaction.atomic():
        event = (OutboxEvent.objects.select_for_update(skip_locked=True)
                 .filter(_filtre_livrables(now), pk=pk).first())
        if event is None:
            return None
        return _appliquer_resultat(event, deliver_one(event), now)


def livrer_maintenant(pk, now=None):
    """NTPLT11 — tentative IMMÉDIATE de livraison d'un événement outbox.

    Appelée par ``core.events.enqueue_durable`` (dans la transaction de
    l'émetteur, ou à son commit) : l'effet part tout de suite comme avant ;
    s'il échoue (Redis/broker coupé, panne d'un service), la ligne reste
    ``failed`` avec son backoff et le worker ``dispatch_pending`` la
    re-livre au redémarrage — rien n'est perdu. Ne lève que si la base
    elle-même lève (les erreurs de handler sont absorbées par
    ``deliver_one``)."""
    from django.utils import timezone

    return _livrer_verrouille(pk, now or timezone.now())


def livrer_maintenant_sans_erreur(pk):
    """Variante ``on_commit`` de ``livrer_maintenant`` : ne lève JAMAIS (un
    rappel ``on_commit`` qui lève casserait les rappels suivants). Un échec
    laisse la ligne au worker."""
    try:
        return livrer_maintenant(pk)
    except Exception:  # noqa: BLE001 — le worker re-livrera (D-ENF22-BLE001)
        logger.exception('dispatch_outbox: livraison immédiate %s échouée', pk)
        return None


def dispatch_pending(now=None, limit: int = 500) -> dict:
    """Livre les événements outbox livrables. Idempotent.

    Sélectionne jusqu'à ``limit`` événements ``pending`` ou ``failed`` dont
    ``prochaine_tentative`` est échue, les livre, et applique statut/backoff/
    dead-letter. Renvoie un compte ``{delivered, failed, dead, scanned}``.
    """
    from django.utils import timezone

    from .models import OutboxEvent

    now = now or timezone.now()
    ids = list(OutboxEvent.objects.filter(_filtre_livrables(now))
               .order_by('created_at').values_list('pk', flat=True)[:limit])

    counts = {'delivered': 0, 'failed': 0, 'dead': 0, 'scanned': 0}
    for pk in ids:
        # NTPLT11 — une ligne à la fois, sous verrou : une tentative immédiate
        # concurrente (ou un 2e worker) ne la double-livre pas.
        resultat = _livrer_verrouille(pk, now)
        if resultat is None:
            continue
        counts['scanned'] += 1
        counts[resultat] += 1
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


class HandlerNotReplayable(Exception):
    """Levée quand on tente de rejouer vers un handler non déclaré rejouable."""


def replay_one_to_handler(event, handler_name: str) -> bool:
    """NTPLT13 — re-livre UN ``OutboxEvent`` vers UN SEUL handler nommé.

    Réparation support ciblée : après le bug d'un abonné, on rejoue les
    événements déjà livrés vers CE handler uniquement (les autres handlers ne
    sont pas retouchés). GARDE-FOU : le handler doit être enregistré pour cet
    événement ET déclaré ``rejouable=True`` au subscribe, sinon
    ``HandlerNotReplayable``. La ligne de dédup ``ProcessedEvent`` du couple
    ``(event_id, handler_name)`` est supprimée AVANT l'appel pour que le
    handler se ré-exécute réellement (le rejeu est volontaire, la dédup ne doit
    pas le bloquer). Renvoie True si le handler a réussi.
    """
    from core import events
    from .models import ProcessedEvent

    match = None
    for hname, handler, rejouable in events.durable_handlers(event.event_name):
        if hname == handler_name:
            match = (hname, handler, rejouable)
            break
    if match is None:
        raise HandlerNotReplayable(
            f"Handler '{handler_name}' non abonné à "
            f"'{event.event_name}'.")
    hname, handler, rejouable = match
    if not rejouable:
        raise HandlerNotReplayable(
            f"Handler '{handler_name}' n'est pas déclaré rejouable=True — "
            f"rejeu refusé (garde-fou NTPLT13).")

    ProcessedEvent.objects.filter(
        event_id=event.event_id, handler_name=hname).delete()
    try:
        handler(event)
    except Exception:  # noqa: BLE001 — remonté au caller (la commande logge) (D-ENF22-BLE001)
        logger.exception(
            'replay_events: handler %s a échoué sur %s',
            hname, event.event_id)
        return False
    _mark_processed(event.event_id, hname)
    return True
