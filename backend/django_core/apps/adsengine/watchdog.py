"""ADSENG17 — Watchdog de l'évaluateur du Gardien (heartbeat + méta-alerte).

LE piège Madgicx (dd-guardian §A3/§B6) : « les règles automatisées ne tournent
pas de façon fiable... parfois pas du tout, sans avertissement ni réessai ». Le
watchdog est le méta-garde-fou qui surveille les gardes-fous : à CHAQUE passage
de l'évaluateur (``rules_engine.evaluate_company``), un HEARTBEAT est posé ; si
ce heartbeat vieillit au-delà du seuil (l'évaluateur ne tourne plus — beat/worker
Celery tombé), ``check_and_alert`` lève une alerte 🔴 DÉDIÉE. Une règle qui LÈVE
pendant son évaluation déclenche aussi une alerte 🔴 dédiée (``report_rule_failure``).

Le heartbeat vit dans le cache Django (Redis en prod, partagé entre worker/beat
et les vues web ; LocMem par process sous les tests). La santé est exposée à
l'endpoint de santé du câblage (ENG12) via ``health``.

**Jamais un échec silencieux** : l'indisponibilité est TOUJOURS visible (alerte +
santé), jamais un simple log muet.
"""
from __future__ import annotations

import datetime
import logging

logger = logging.getLogger(__name__)

# Préfixe de clé cache du heartbeat, par société.
_CACHE_PREFIX = 'adsengine:guardian:heartbeat:'

# Une boucle critique tourne toutes les 6 h ; 4 passages manqués (24 h) sans
# heartbeat = l'évaluateur ne tourne manifestement plus.
DEFAULT_MAX_AGE_HOURS = 24


def _cache_key(company):
    return f'{_CACHE_PREFIX}{getattr(company, "pk", company)}'


def record_heartbeat(company, *, now=None):
    """Pose le heartbeat de l'évaluateur pour la société (appelé à chaque passage
    de ``evaluate_company``). Best-effort : une panne de cache ne casse jamais
    l'évaluateur (django-redis dégrade en no-op ; ici on avale défensivement)."""
    from django.core.cache import cache
    from django.utils import timezone

    ts = now or timezone.now()
    try:
        cache.set(_cache_key(company), ts.isoformat(), None)  # sans expiration
    except Exception:  # noqa: BLE001 — best-effort, jamais casser l'évaluateur
        logger.warning('adsengine watchdog: heartbeat non posé', exc_info=True)
    return ts


def last_heartbeat(company):
    """Datetime du dernier heartbeat, ou ``None`` (jamais tourné / cache vide)."""
    from django.core.cache import cache
    from django.utils.dateparse import parse_datetime

    raw = cache.get(_cache_key(company))
    if not raw:
        return None
    try:
        return parse_datetime(raw)
    except (ValueError, TypeError):  # pragma: no cover - valeur cache corrompue
        return None


def is_stale(company, *, max_age_hours=DEFAULT_MAX_AGE_HOURS, now=None):
    """Vrai si aucun heartbeat OU s'il est plus vieux que ``max_age_hours``
    (l'évaluateur ne tourne plus)."""
    from django.utils import timezone

    hb = last_heartbeat(company)
    if hb is None:
        return True
    now = now or timezone.now()
    return (now - hb) > datetime.timedelta(hours=max_age_hours)


def health(company, *, max_age_hours=DEFAULT_MAX_AGE_HOURS):
    """Santé de l'évaluateur pour l'endpoint ENG12 (``wiring-health``). Aucun
    secret — seulement l'horodatage du dernier passage + un booléen."""
    hb = last_heartbeat(company)
    stale = is_stale(company, max_age_hours=max_age_hours)
    return {
        'evaluator_last_run': hb.isoformat() if hb else None,
        'stale': stale,
        'healthy': (hb is not None and not stale),
        'max_age_hours': max_age_hours,
    }


def _emit(company, *, entity_key, message, cooldown_hours=6):
    """Crée une ``EngineAlert`` 🔴 « règle inopérante » dédiée, DÉDUP par
    ``entity_key`` : aucune alerte en double tant qu'une non résolue existe dans
    le cooldown. Renvoie l'alerte (existante ou neuve)."""
    from django.utils import timezone

    from . import guardrails
    from .models import EngineAlert
    from .rules import SEVERITY_CRITICAL

    if company is None:
        return None
    since = timezone.now() - datetime.timedelta(hours=cooldown_hours)
    existing = (EngineAlert.objects
                .filter(company=company, entity_key=entity_key, resolved=False,
                        created_at__gte=since)
                .order_by('-created_at').first())
    if existing is not None:
        return existing
    return EngineAlert.objects.create(
        company=company, alert_type=guardrails.ALERT_INOPERATIVE,
        message=message, severity=SEVERITY_CRITICAL, entity_key=entity_key,
        cooldown_hours=cooldown_hours,
        detail={'source': 'watchdog', 'entity_key': entity_key})


def report_rule_failure(company, *, template_key='', error='', target=None):
    """Une règle N'A PAS PU s'exécuter → alerte 🔴 dédiée (jamais un log muet).
    ``target`` (optionnel) précise la cible. Dédupliquée par (société, règle,
    cible)."""
    from .rules import SEVERITY_CRITICAL, SEVERITY_EMOJI

    tkey = str(template_key or 'regle')
    suffix = f':{target}' if target else ''
    entity_key = (f'watchdog:rule:{tkey}{suffix}')[:80]
    emoji = SEVERITY_EMOJI[SEVERITY_CRITICAL]
    message = (
        f"{emoji} La règle « {tkey} » n'a pas pu s'exécuter ({error}). Aucune "
        f"vérification automatique n'a eu lieu pour cette règle — vérifier la "
        f"connexion Meta.")
    logger.warning('adsengine watchdog: règle %s inopérante: %s', tkey, error)
    return _emit(company, entity_key=entity_key, message=message)


def check_and_alert(company, *, max_age_hours=DEFAULT_MAX_AGE_HOURS, now=None):
    """Si l'évaluateur est en retard (heartbeat périmé / jamais posé), lève une
    alerte 🔴 dédiée « évaluateur arrêté » et renvoie l'alerte ; sinon ``None``.
    C'est le test « évaluateur tué ⇒ alerte watchdog »."""
    if not is_stale(company, max_age_hours=max_age_hours, now=now):
        return None
    from .rules import SEVERITY_EMOJI, SEVERITY_CRITICAL

    emoji = SEVERITY_EMOJI[SEVERITY_CRITICAL]
    message = (
        f"{emoji} L'évaluateur du Gardien n'a pas tourné depuis plus de "
        f"{max_age_hours} h — aucune vérification automatique récente. Vérifier "
        f"le worker/beat Celery.")
    return _emit(company, entity_key='watchdog:evaluator', message=message)
