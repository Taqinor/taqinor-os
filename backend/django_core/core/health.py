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


def check_services():
    """Liste normalisée de l'état de chaque service d'infrastructure."""
    return [
        _check_db(),
        _check_cache(),
        _check_broker(),
        _check_storage(),
        _check_monitoring(),
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
