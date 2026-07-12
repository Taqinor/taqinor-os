"""NTPLT28 — Décorateur d'idempotence Celery (étend YDATA14).

Certaines tâches beat ont des effets EXTERNES non rejouables (envoi de
relances, digests e-mail, factures récurrentes). Un double déclenchement
(retry Celery, worker qui redémarre, beat qui tire deux fois) ne doit produire
l'effet QU'UNE seule fois. ``idempotent_task`` pose un verrou nommé, dérivé des
arguments de la tâche, avant l'exécution :

* ``SETNX`` Redis (``cache.add``) — pose atomique d'une clé qui n'existe pas ;
  si la clé existe déjà, un autre appel a déjà (ou est en train de) traité
  cette exécution → on SKIP.
* Repli DB si Redis est indisponible : une ligne ``IdempotencyKey`` (contrainte
  unique) jouée dans une transaction ``get_or_create`` — le second appel voit
  ``created=False`` et SKIP.

Contrat
-------
    @shared_task(name=...)          # nom de tâche réel de VOTRE app
    @idempotent_task(key_fn=lambda company_id, **k: f'relances:{company_id}',
                     ttl=3600)
    def relances(company_id):
        ...  # exécutée AU PLUS UNE FOIS par (clé, fenêtre ttl)

Le décorateur renvoie ``{'skipped': True, 'key': ...}`` quand il court-circuite
un doublon, sinon le résultat de la tâche. ``core`` reste fondation (le repli
DB importe son propre modèle paresseusement).
"""
from __future__ import annotations

import functools
import logging

from django.core.cache import cache

logger = logging.getLogger(__name__)

# Préfixe de toutes les clés d'idempotence dans le cache.
_PREFIX = 'idem'


def _acquire_cache(key: str, ttl: int) -> bool:
    """SETNX via ``cache.add`` : True si la clé a été POSÉE (première fois).

    Lève si le backend cache est indisponible (le décorateur bascule alors sur
    le repli DB).
    """
    return bool(cache.add(f'{_PREFIX}:{key}', 1, ttl))


def _acquire_db(key: str, ttl: int) -> bool:
    """Repli DB : True si la clé a été créée (première fois), False sinon.

    Utilise ``IdempotencyKey`` (contrainte unique sur ``cle``). Une clé expirée
    (au-delà de ``ttl``) est réutilisable : on la recrée après purge.
    """
    from django.utils import timezone
    from datetime import timedelta
    from .models import IdempotencyKey

    now = timezone.now()
    # Purge d'une éventuelle clé expirée avant la tentative de création.
    IdempotencyKey.objects.filter(
        cle=key, created_at__lt=now - timedelta(seconds=ttl)).delete()
    _, created = IdempotencyKey.objects.get_or_create(cle=key)
    return created


def acquire(key: str, ttl: int) -> bool:
    """Tente d'acquérir le verrou d'idempotence ``key`` (Redis, repli DB).

    Renvoie True si CET appel est le premier (doit exécuter), False si un autre
    appel a déjà réservé cette exécution (doit SKIP).
    """
    try:
        return _acquire_cache(key, ttl)
    except Exception:  # noqa: BLE001 — Redis down → repli DB
        logger.warning('idempotent_task: cache KO, repli DB pour %s', key)
        try:
            return _acquire_db(key, ttl)
        except Exception:  # noqa: BLE001 — DB KO aussi → fail-open (exécute)
            logger.exception('idempotent_task: repli DB KO pour %s', key)
            return True


def idempotent_task(key_fn, ttl: int = 3600):
    """Décorateur d'idempotence : exécute la tâche AU PLUS UNE FOIS par clé.

    ``key_fn(*args, **kwargs)`` doit renvoyer une chaîne stable identifiant
    l'exécution logique (p. ex. ``f'digest:{company_id}:{jour}'``). ``ttl`` est
    la fenêtre (secondes) pendant laquelle un doublon est court-circuité.
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            key = key_fn(*args, **kwargs)
            if not acquire(key, ttl):
                logger.info('idempotent_task: doublon ignoré (%s)', key)
                return {'skipped': True, 'key': key}
            return func(*args, **kwargs)
        return wrapper
    return decorator
