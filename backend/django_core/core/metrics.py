"""YHARD6 — métriques Prometheus + santé Celery/beat.

Couche de FONDATION : expose un jeu de métriques au format texte Prometheus
(https://prometheus.io/docs/instrumenting/exposition_formats/) SANS importer
aucune app métier. ``django-prometheus`` (OSS, cf. ``requirements.txt``) reste
la dépendance de RÉFÉRENCE pour les métriques HTTP/DB standard quand elle est
installée ; ce module fournit en plus des COLLECTEURS CUSTOM (succès/échec des
tâches Celery, âge du dernier heartbeat du beat, longueur de la file Redis)
et un rendu texte minimal en pur stdlib qui fonctionne MÊME SANS
``django-prometheus`` installé — l'endpoint ne casse jamais si le paquet
optionnel est absent (import paresseux + repli).

Compteurs Celery : incrémentés par des signaux ``task_success``/
``task_failure`` enregistrés (best-effort, en mémoire process — un compteur
process-local est suffisant pour une jauge de santé, pas pour de l'analytics
fine ; un vrai backend d'observabilité agrège across-process si besoin).

Heartbeat du beat : la tâche ``core.beat_heartbeat`` (cf. ``core/tasks.py``),
planifiée fréquemment dans ``erp_agentique/celery.py``, écrit un timestamp
dans le cache à chaque tick. ``beat_heartbeat_age_seconds()`` en dérive l'âge ;
``core/health.py`` s'en sert pour signaler un beat arrêté.
"""
from __future__ import annotations

import threading
import time

from django.core.cache import cache

BEAT_HEARTBEAT_CACHE_KEY = 'core_beat_heartbeat_ts'
# Au-delà de cet âge (secondes), le beat est considéré arrêté/dégradé. Le
# heartbeat tourne toutes les 5 minutes (voir celery.py) — 15 min = 3 ticks
# manqués de marge avant de déclarer un problème.
BEAT_HEARTBEAT_STALE_SECONDS = 15 * 60

# Compteurs process-local (best-effort, jamais persistés). Un redémarrage de
# worker remet à zéro — attendu pour une jauge de santé "depuis le dernier
# démarrage", pas un cumul historique (voir apps.audit / apps.reporting pour
# l'historique durable).
_lock = threading.Lock()
_task_counters = {'success': 0, 'failure': 0}

# NTPLT44 — compteurs Celery PAR QUEUE (best-effort, process-local). Clé = nom
# de queue → {'success': n, 'failure': n}.
_task_by_queue: dict = {}

# NTPLT44 — métriques HTTP PAR TENANT avec garde-fou de CARDINALITÉ. Sans garde,
# `company` comme label Prometheus exploserait la cardinalité (1 série par
# société × statut × bucket) à 1000+ tenants — coût mémoire/scrape prohibitif.
# On plafonne à TOP-N sociétés RÉELLES ; au-delà, tout est agrégé sous `other`.
_CARDINALITY_CAP = 20
# Buckets de latence (secondes) — échelle standard Prometheus.
_LATENCY_BUCKETS = (0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0)
# label company → {'count','sum','buckets':[...],'status':{class:n}}
_http_by_tenant: dict = {}
_http_real_companies: set = set()


def record_task_success():
    with _lock:
        _task_counters['success'] += 1


def record_task_failure():
    with _lock:
        _task_counters['failure'] += 1


def record_task_queue(queue, ok):
    """NTPLT44 — incrémente le compteur Celery de la queue nommée."""
    queue = queue or 'default'
    with _lock:
        slot = _task_by_queue.setdefault(queue, {'success': 0, 'failure': 0})
        slot['success' if ok else 'failure'] += 1


def task_counters():
    with _lock:
        return dict(_task_counters)


def task_queue_counters():
    with _lock:
        return {q: dict(v) for q, v in _task_by_queue.items()}


def _tenant_label(company_id):
    """Résout le label company avec garde de cardinalité (top-N, sinon other)."""
    if company_id is None:
        return 'system'
    key = str(company_id)
    if key in _http_real_companies:
        return key
    if len(_http_real_companies) < _CARDINALITY_CAP:
        _http_real_companies.add(key)
        return key
    return 'other'


def record_http_request(company_id, status, duration_ms):
    """NTPLT44 — enregistre une requête HTTP (compteur + histogramme) par tenant.

    Best-effort, process-local, jamais bloquant. La cardinalité `company` est
    bornée (top-20 sociétés par volume observé, le reste → `other`)."""
    try:
        seconds = float(duration_ms) / 1000.0
    except (TypeError, ValueError):
        seconds = 0.0
    status_class = f'{int(status) // 100}xx' if status else 'unknown'
    with _lock:
        label = _tenant_label(company_id)
        slot = _http_by_tenant.setdefault(label, {
            'count': 0, 'sum': 0.0,
            'buckets': [0] * len(_LATENCY_BUCKETS),
            'status': {},
        })
        slot['count'] += 1
        slot['sum'] += seconds
        slot['status'][status_class] = slot['status'].get(status_class, 0) + 1
        for i, edge in enumerate(_LATENCY_BUCKETS):
            if seconds <= edge:
                slot['buckets'][i] += 1


def http_tenant_metrics():
    with _lock:
        return {
            label: {
                'count': v['count'], 'sum': v['sum'],
                'buckets': list(v['buckets']), 'status': dict(v['status']),
            }
            for label, v in _http_by_tenant.items()
        }


def mark_beat_heartbeat():
    """Appelé par la tâche périodique ``core.beat_heartbeat`` à chaque tick."""
    cache.set(BEAT_HEARTBEAT_CACHE_KEY, time.time(), None)


def beat_heartbeat_age_seconds():
    """Âge (secondes) du dernier heartbeat, ou ``None`` si jamais reçu."""
    ts = cache.get(BEAT_HEARTBEAT_CACHE_KEY)
    if ts is None:
        return None
    return max(0.0, time.time() - float(ts))


def beat_is_stale():
    age = beat_heartbeat_age_seconds()
    if age is None:
        return True
    return age > BEAT_HEARTBEAT_STALE_SECONDS


def redis_queue_length(queue_name='celery'):
    """Longueur best-effort de la file Redis du broker Celery.

    ``None`` si le broker n'est pas Redis ou injoignable (ne bloque jamais)."""
    try:
        from django.conf import settings
        broker_url = getattr(settings, 'CELERY_BROKER_URL', '') or ''
        if not broker_url.startswith('redis'):
            return None
        import redis as redis_lib
        client = redis_lib.Redis.from_url(broker_url, socket_timeout=0.5)
        return client.llen(queue_name)
    except Exception:  # noqa: BLE001 — best-effort
        return None


def _django_prometheus_available():
    try:
        import django_prometheus  # noqa: F401
        return True
    except Exception:  # noqa: BLE001 — dépendance optionnelle non installée
        return False


def render_prometheus_text():
    """Rend le jeu de métriques au format texte d'exposition Prometheus.

    Toujours disponible (stdlib pur) — les métriques HTTP/DB fines de
    ``django-prometheus`` s'ajoutent séparément côté middleware quand le
    paquet est installé (voir ``erp_agentique/settings/base.py``). Ce rendu
    garantit AU MINIMUM les collecteurs custom YHARD6, jamais une 500."""
    lines = []

    lines.append('# HELP taqinor_up Process Django actif (toujours 1).')
    lines.append('# TYPE taqinor_up gauge')
    lines.append('taqinor_up 1')

    counters = task_counters()
    lines.append('# HELP taqinor_celery_tasks_total Tâches Celery par issue '
                 '(depuis le démarrage du worker).')
    lines.append('# TYPE taqinor_celery_tasks_total counter')
    lines.append(f'taqinor_celery_tasks_total{{status="success"}} {counters["success"]}')
    lines.append(f'taqinor_celery_tasks_total{{status="failure"}} {counters["failure"]}')

    age = beat_heartbeat_age_seconds()
    lines.append('# HELP taqinor_beat_heartbeat_age_seconds Âge du dernier '
                 'heartbeat Celery Beat (secondes).')
    lines.append('# TYPE taqinor_beat_heartbeat_age_seconds gauge')
    lines.append(f'taqinor_beat_heartbeat_age_seconds {age if age is not None else -1}')

    lines.append('# HELP taqinor_beat_stale Beat considéré arrêté (1) ou '
                 'sain (0).')
    lines.append('# TYPE taqinor_beat_stale gauge')
    lines.append(f'taqinor_beat_stale {1 if beat_is_stale() else 0}')

    qlen = redis_queue_length()
    if qlen is not None:
        lines.append('# HELP taqinor_broker_queue_length Longueur de la file '
                     'Redis du broker Celery (file "celery").')
        lines.append('# TYPE taqinor_broker_queue_length gauge')
        lines.append(f'taqinor_broker_queue_length {qlen}')

    lines.append('# HELP taqinor_django_prometheus_available django-prometheus '
                 'installé (1) ou absent (0) — métriques HTTP/DB additionnelles.')
    lines.append('# TYPE taqinor_django_prometheus_available gauge')
    lines.append(f'taqinor_django_prometheus_available {1 if _django_prometheus_available() else 0}')

    # NTPLT44 — compteurs Celery PAR QUEUE.
    queues = task_queue_counters()
    if queues:
        lines.append('# HELP taqinor_celery_queue_tasks_total Tâches Celery par '
                     'queue et issue (depuis le démarrage du worker).')
        lines.append('# TYPE taqinor_celery_queue_tasks_total counter')
        for queue, slot in sorted(queues.items()):
            for status_ in ('success', 'failure'):
                lines.append(
                    f'taqinor_celery_queue_tasks_total'
                    f'{{queue="{queue}",status="{status_}"}} {slot[status_]}')

    # NTPLT44 — requêtes HTTP PAR TENANT (compteur + histogramme de latence),
    # cardinalité `company` bornée (top-20 + `other`).
    tenants = http_tenant_metrics()
    if tenants:
        lines.append('# HELP taqinor_http_requests_total Requêtes HTTP par '
                     'société (label borné : top-20 + other) et classe de statut.')
        lines.append('# TYPE taqinor_http_requests_total counter')
        for label, v in sorted(tenants.items()):
            for status_class, n in sorted(v['status'].items()):
                lines.append(
                    f'taqinor_http_requests_total'
                    f'{{company="{label}",status="{status_class}"}} {n}')
        lines.append('# HELP taqinor_http_request_duration_seconds Latence des '
                     'requêtes HTTP par société (histogramme).')
        lines.append('# TYPE taqinor_http_request_duration_seconds histogram')
        for label, v in sorted(tenants.items()):
            cumulative = 0
            for i, edge in enumerate(_LATENCY_BUCKETS):
                cumulative += v['buckets'][i]
                lines.append(
                    f'taqinor_http_request_duration_seconds_bucket'
                    f'{{company="{label}",le="{edge}"}} {cumulative}')
            lines.append(
                f'taqinor_http_request_duration_seconds_bucket'
                f'{{company="{label}",le="+Inf"}} {v["count"]}')
            lines.append(
                f'taqinor_http_request_duration_seconds_sum'
                f'{{company="{label}"}} {v["sum"]:.4f}')
            lines.append(
                f'taqinor_http_request_duration_seconds_count'
                f'{{company="{label}"}} {v["count"]}')

    return '\n'.join(lines) + '\n'
