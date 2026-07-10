"""FG397 — Page d'état / santé système (santé des services + incidents).

Couche de FONDATION : agrège la santé des services d'infrastructure (base de
données, cache/Redis, broker Celery, stockage objets, monitoring) et un fil des
incidents récents, SANS importer aucune app métier (contrat import-linter
``core-foundation-is-a-base-layer``). Tous les contrôles sont DÉFENSIFS : une
sonde qui échoue renvoie ``down`` avec un message, jamais une exception qui
planterait la page d'état.

Conception
----------

* ``check_services()`` — renvoie une liste de ``{name, status, detail}`` :
  base de données (SELECT 1), cache (set/get sentinelle), broker Celery
  (ping best-effort), stockage par défaut (présence), monitoring (DSN configuré).
* ``recent_incidents(limit=10)`` — incidents récents tirés des
  ``BackupRun``/``ScheduledExport`` en échec/non-configurés (signaux d'infra
  génériques portés par core, pas de modèle métier).
* ``overall_status(services)`` — agrège : ``ok`` / ``degraded`` / ``down``.

Aucune importation d'app domaine.
"""
from __future__ import annotations

from django.core.cache import cache
from django.db import connection

STATUS_OK = 'ok'
STATUS_DOWN = 'down'
STATUS_DEGRADED = 'degraded'
STATUS_UNKNOWN = 'unknown'


CONN_SATURATION_DEGRADED_RATIO = 0.8


def _check_db_connections(cur):
    """YOPSB7 — remonte le nombre de connexions actives vs ``max_connections``
    (``pg_stat_activity``/``SHOW max_connections``). ``degraded`` au-delà de
    80 %. Best-effort : une erreur ici ne fait jamais échouer ``_check_db``
    (déjà validé par le SELECT 1 qui précède)."""
    try:
        cur.execute('SELECT count(*) FROM pg_stat_activity')
        active = cur.fetchone()[0]
        cur.execute('SHOW max_connections')
        max_conn = int(cur.fetchone()[0])
        ratio = (active / max_conn) if max_conn else 0
        return {
            'active': active,
            'max': max_conn,
            'ratio': round(ratio, 3),
            'saturated': ratio >= CONN_SATURATION_DEGRADED_RATIO,
        }
    except Exception:  # noqa: BLE001 — best-effort, jamais bloquant
        return None


def _check_db():
    try:
        with connection.cursor() as cur:
            cur.execute('SELECT 1')
            cur.fetchone()
            conn_info = _check_db_connections(cur)
    except Exception as exc:  # noqa: BLE001
        return {'name': 'database', 'status': STATUS_DOWN, 'detail': str(exc)}

    if conn_info and conn_info['saturated']:
        return {
            'name': 'database', 'status': STATUS_DEGRADED,
            'detail': (
                f"Connexions proches de la saturation : {conn_info['active']}"
                f"/{conn_info['max']} ({conn_info['ratio']:.0%})."),
        }
    return {'name': 'database', 'status': STATUS_OK, 'detail': ''}


# YOPSB14 — alias public pour /api/django/core/health/ready/ (core.views).
# Le probe readiness n'a besoin QUE de la sonde DB (pas du reste de
# check_services()) — exposé explicitement plutôt que d'accéder au nom
# préfixé « privé » depuis un autre module.
check_db = _check_db


def _check_cache():
    try:
        cache.set('core_health_probe', '1', 5)
        ok = cache.get('core_health_probe') == '1'
        return {
            'name': 'cache',
            'status': STATUS_OK if ok else STATUS_DEGRADED,
            'detail': '' if ok else 'Lecture/écriture cache incohérente.',
        }
    except Exception as exc:  # noqa: BLE001
        return {'name': 'cache', 'status': STATUS_DOWN, 'detail': str(exc)}


def _check_broker():
    """Ping best-effort du broker Celery (no-op propre si indisponible)."""
    try:
        from celery import current_app
        replies = current_app.control.ping(timeout=0.5)
        if replies:
            return {'name': 'broker', 'status': STATUS_OK, 'detail': ''}
        return {
            'name': 'broker', 'status': STATUS_DEGRADED,
            'detail': 'Aucun worker Celery n\'a répondu au ping.',
        }
    except Exception as exc:  # noqa: BLE001
        return {'name': 'broker', 'status': STATUS_UNKNOWN, 'detail': str(exc)}


def _check_storage():
    try:
        from django.core.files.storage import default_storage
        # On ne fait qu'une présence de backend — aucun I/O réseau bloquant.
        name = type(default_storage).__name__
        return {'name': 'storage', 'status': STATUS_OK, 'detail': name}
    except Exception as exc:  # noqa: BLE001
        return {'name': 'storage', 'status': STATUS_UNKNOWN, 'detail': str(exc)}


def _check_monitoring():
    from . import monitoring
    if monitoring.is_enabled():
        return {'name': 'monitoring', 'status': STATUS_OK, 'detail': 'Sentry'}
    return {
        'name': 'monitoring', 'status': STATUS_UNKNOWN,
        'detail': 'Aucun DSN — monitoring désactivé.',
    }


def _check_beat():
    """YHARD6 — santé du Celery Beat via le heartbeat périodique
    (``core.beat_heartbeat``, cf. ``core/metrics.py``). ``unknown`` si le
    heartbeat n'a jamais été reçu (beat jamais démarré / pas encore de tick) —
    ne dégrade pas agressivement un environnement fraîchement démarré ;
    ``degraded`` seulement au-delà du seuil de péremption."""
    from . import metrics as metrics_infra
    try:
        age = metrics_infra.beat_heartbeat_age_seconds()
    except Exception as exc:  # noqa: BLE001 — best-effort
        return {'name': 'beat', 'status': STATUS_UNKNOWN, 'detail': str(exc)}
    if age is None:
        return {
            'name': 'beat', 'status': STATUS_UNKNOWN,
            'detail': 'Aucun heartbeat reçu pour le moment.',
        }
    if age > metrics_infra.BEAT_HEARTBEAT_STALE_SECONDS:
        return {
            'name': 'beat', 'status': STATUS_DEGRADED,
            'detail': f'Dernier heartbeat il y a {int(age)}s (beat probablement arrêté).',
        }
    return {'name': 'beat', 'status': STATUS_OK, 'detail': f'Heartbeat il y a {int(age)}s.'}


def _check_queue():
    """YHARD6 — longueur de la file Redis du broker Celery. ``unknown`` si le
    broker n'est pas Redis ou injoignable ; pas de seuil de saturation fixe ici
    (dépend de la charge normale de chaque déploiement) — exposé pour que
    l'alerting externe (documenté, non déployé ici) applique son propre seuil."""
    from . import metrics as metrics_infra
    try:
        length = metrics_infra.redis_queue_length()
    except Exception as exc:  # noqa: BLE001 — best-effort
        return {'name': 'queue', 'status': STATUS_UNKNOWN, 'detail': str(exc)}
    if length is None:
        return {
            'name': 'queue', 'status': STATUS_UNKNOWN,
            'detail': 'Broker non-Redis ou injoignable.',
        }
    return {'name': 'queue', 'status': STATUS_OK, 'detail': f'{length} tâche(s) en attente.'}


REDIS_MEMORY_DEGRADED_RATIO = 0.8

# SCA9 — les 3 queues Celery isolées au niveau compose (default/interactive/
# scheduled, voir YOPSB9 dans settings/base.py et docker-compose.yml). Seuil
# de profondeur PAR QUEUE, surchargeable par variable d'env dédiée
# (QUEUE_DEPTH_DEGRADED_<QUEUE EN MAJUSCULES>) — défaut 500 par queue, valeur
# de bon sens NON mesurée sur un volume réel de production (à recalibrer une
# fois un volume de tâches réel observé, voir docs/scale-runway.md).
QUEUE_DEPTH_DEGRADED_DEFAULT = 500
MONITORED_QUEUES = ['default', 'interactive', 'scheduled']


def _redis_urls_to_check():
    """URLs des instances Redis à sonder pour la mémoire (SCA10 : broker +
    cache, potentiellement deux instances distinctes désormais). Renvoie une
    liste de ``(label, url)`` — jamais vide même sans configuration
    spécifique (retombe sur les mêmes défauts que ``settings/base.py``)."""
    import os

    from django.conf import settings

    broker_url = getattr(settings, 'CELERY_BROKER_URL', '') or ''
    cache_host = os.environ.get(
        'REDIS_CACHE_HOST', os.environ.get('REDIS_HOST', 'redis'))
    cache_port = os.environ.get(
        'REDIS_CACHE_PORT', os.environ.get('REDIS_PORT', '6379'))
    cache_url = f'redis://{cache_host}:{cache_port}/1'
    return [('broker', broker_url), ('cache', cache_url)]


def _redis_memory_ratio(url):
    """``(used_memory, maxmemory, ratio)`` pour l'instance Redis à ``url``.
    ``None`` si non-Redis, injoignable, ou ``maxmemory`` non posé (0 — pas de
    limite, un ratio ne peut pas être calculé, jamais une fausse alerte)."""
    if not url.startswith('redis'):
        return None
    import redis as redis_lib
    client = redis_lib.Redis.from_url(url, socket_timeout=0.5)
    info = client.info('memory')
    used = info.get('used_memory', 0)
    maxmem = info.get('maxmemory', 0)
    if not maxmem:
        return None
    return used, maxmem, used / maxmem


def _check_redis_memory():
    """SCA15 — ``used_memory`` vs ``maxmemory`` sur CHAQUE instance Redis
    configurée (broker + cache, SCA10). ``degraded`` si l'une des deux
    dépasse ``REDIS_MEMORY_DEGRADED_RATIO`` (défaut 80 % — même convention
    que ``CONN_SATURATION_DEGRADED_RATIO``). Best-effort : une sonde
    injoignable ne fait jamais planter les autres."""
    import os

    seuil = float(os.environ.get(
        'REDIS_MEMORY_DEGRADED_RATIO', str(REDIS_MEMORY_DEGRADED_RATIO)))
    details = []
    degraded = False
    any_reached = False
    for label, url in _redis_urls_to_check():
        try:
            result = _redis_memory_ratio(url)
        except Exception as exc:  # noqa: BLE001 — best-effort
            details.append(f'{label}: injoignable ({exc})')
            continue
        if result is None:
            details.append(f'{label}: maxmemory non posé (ratio indisponible).')
            continue
        any_reached = True
        used, maxmem, ratio = result
        details.append(f'{label}: {ratio:.0%} ({used}/{maxmem} octets)')
        if ratio >= seuil:
            degraded = True

    if not any_reached:
        return {
            'name': 'redis_memory', 'status': STATUS_UNKNOWN,
            'detail': 'Aucune instance Redis avec maxmemory joignable.',
        }
    return {
        'name': 'redis_memory',
        'status': STATUS_DEGRADED if degraded else STATUS_OK,
        'detail': '; '.join(details),
    }


def _queue_depth_threshold(queue_name):
    import os

    env_key = f'QUEUE_DEPTH_DEGRADED_{queue_name.upper()}'
    return int(os.environ.get(env_key, str(QUEUE_DEPTH_DEGRADED_DEFAULT)))


def _check_queue_depth():
    """SCA15 — ``LLEN`` par queue Celery nommée (SCA9 : default/interactive/
    scheduled). ``degraded`` si l'une des queues dépasse son seuil
    (``QUEUE_DEPTH_DEGRADED_<QUEUE>``, défaut 500). ``unknown`` si le broker
    n'est pas Redis ou injoignable (même best-effort que ``_check_queue``)."""
    from . import metrics as metrics_infra

    details = []
    degraded = False
    any_reached = False
    for queue_name in MONITORED_QUEUES:
        try:
            length = metrics_infra.redis_queue_length(queue_name)
        except Exception as exc:  # noqa: BLE001 — best-effort
            details.append(f'{queue_name}: injoignable ({exc})')
            continue
        if length is None:
            details.append(f'{queue_name}: broker non-Redis ou injoignable.')
            continue
        any_reached = True
        seuil = _queue_depth_threshold(queue_name)
        details.append(f'{queue_name}: {length} (seuil {seuil})')
        if length >= seuil:
            degraded = True

    if not any_reached:
        return {
            'name': 'queue_depth', 'status': STATUS_UNKNOWN,
            'detail': 'Broker non-Redis ou injoignable.',
        }
    return {
        'name': 'queue_depth',
        'status': STATUS_DEGRADED if degraded else STATUS_OK,
        'detail': '; '.join(details),
    }


def check_services():
    """Liste normalisée de l'état de chaque service d'infrastructure."""
    return [
        _check_db(),
        _check_cache(),
        _check_broker(),
        _check_storage(),
        _check_monitoring(),
        _check_beat(),
        _check_queue(),
        _check_redis_memory(),
        _check_queue_depth(),
    ]


def overall_status(services):
    """Agrège l'état global à partir des sondes de service.

    ``down`` si une sonde critique (db/cache) est ``down`` ; ``degraded`` si une
    sonde est ``down``/``degraded`` ; sinon ``ok``. Les états ``unknown`` (ping
    best-effort) n'abaissent pas le global.
    """
    critiques = {'database', 'cache'}
    if any(s['status'] == STATUS_DOWN and s['name'] in critiques
           for s in services):
        return STATUS_DOWN
    if any(s['status'] in (STATUS_DOWN, STATUS_DEGRADED) for s in services):
        return STATUS_DEGRADED
    return STATUS_OK


def recent_incidents(company=None, limit=10):
    """Incidents d'infra récents (sauvegardes/extraits en échec).

    Génériques (portés par core) : pas de modèle métier. Si ``company`` est
    fourni, on borne aux incidents de cette société.
    """
    from .models import BackupRun, ScheduledExport

    incidents = []

    backups = BackupRun.objects.filter(
        statut__in=[BackupRun.STATUT_ECHEC, BackupRun.STATUT_NON_CONFIGURE])
    if company is not None:
        backups = backups.filter(company=company)
    for run in backups.order_by('-updated_at')[:limit]:
        incidents.append({
            'source': 'backup',
            'reference': run.pk,
            'statut': run.statut,
            'message': (run.detail or {}).get('message', ''),
            'survenu_le': run.updated_at.isoformat() if run.updated_at else None,
        })

    exports = ScheduledExport.objects.exclude(dernier_statut='')
    if company is not None:
        exports = exports.filter(company=company)
    for exp in exports.exclude(
            dernier_statut__in=['', 'ok']).order_by('-updated_at')[:limit]:
        incidents.append({
            'source': 'scheduled_export',
            'reference': exp.pk,
            'statut': exp.dernier_statut,
            'message': exp.titre,
            'survenu_le': (exp.derniere_execution_le.isoformat()
                           if exp.derniere_execution_le else None),
        })

    incidents.sort(key=lambda i: i['survenu_le'] or '', reverse=True)
    return incidents[:limit]
