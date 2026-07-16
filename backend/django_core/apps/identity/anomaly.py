"""NTSEC12 — Détection « impossible travel » sur les connexions.

Compare une nouvelle connexion à la dernière session connue de l'utilisateur :
si la distance géographique et le délai impliquent une vitesse physiquement
impossible (> seuil), on lève une ``SECURITY_ALERT`` + notification Directeur —
SANS JAMAIS bloquer la connexion (purement informatif).

Géolocalisation KEY-GATED : nécessite la lib OSS ``geoip2`` ET une base
GeoLite2 locale (``settings.GEOIP_PATH``). Sans base, le module est totalement
INERTE (no-op) — aucune connexion n'est jamais affectée.
"""
from __future__ import annotations

import logging
from math import asin, cos, radians, sin, sqrt

logger = logging.getLogger(__name__)

# Vitesse au-delà de laquelle un déplacement est jugé impossible (km/h).
SPEED_THRESHOLD_KMH = 900.0


def _geolocate(ip):
    """(lat, lon) pour ``ip`` via GeoLite2, ou ``None`` si indisponible.

    Best-effort et key-gated : absence de ``geoip2``, de ``GEOIP_PATH``, IP
    privée/introuvable → ``None`` (le module reste inerte)."""
    if not ip:
        return None
    try:
        from django.conf import settings
        path = getattr(settings, 'GEOIP_PATH', None) or getattr(
            settings, 'GEOIP2_CITY_DB', None)
        if not path:
            return None
        import geoip2.database  # type: ignore
        with geoip2.database.Reader(path) as reader:
            resp = reader.city(ip)
            if resp.location.latitude is None:
                return None
            return (resp.location.latitude, resp.location.longitude)
    except Exception:
        return None


def _haversine_km(a, b):
    """Distance grand-cercle (km) entre deux points (lat, lon)."""
    lat1, lon1 = radians(a[0]), radians(a[1])
    lat2, lon2 = radians(b[0]), radians(b[1])
    dlat, dlon = lat2 - lat1, lon2 - lon1
    h = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
    return 2 * 6371.0 * asin(sqrt(h))


def detect_impossible_travel(user, ip, at=None):
    """Détecte un « voyage impossible » pour ``user`` se connectant depuis ``ip``.

    Compare à la dernière ``UserSession`` de l'utilisateur portant une IP. Si la
    vitesse implicite dépasse ``SPEED_THRESHOLD_KMH``, crée une ``SECURITY_ALERT``
    (audit) + notifie les Directeurs, et renvoie le dict de l'anomalie. Jamais
    bloquant. Renvoie ``None`` si inerte (pas de base géo, pas d'historique,
    vitesse plausible, ou toute erreur).
    """
    try:
        if user is None or not getattr(user, 'pk', None):
            return None
        from django.utils import timezone
        at = at or timezone.now()

        here = _geolocate(ip)
        if here is None:
            return None  # key-gated : sans base géo, module inerte.

        from authentication.models import UserSession
        last = UserSession.objects.filter(
            user=user, ip_address__isnull=False,
        ).exclude(ip_address=ip).order_by('-last_seen_at').first()
        if last is None:
            return None
        there = _geolocate(last.ip_address)
        if there is None:
            return None

        prev_at = last.last_seen_at or last.created_at
        if prev_at is None:
            return None
        hours = (at - prev_at).total_seconds() / 3600.0
        if hours <= 0:
            return None
        distance = _haversine_km(here, there)
        speed = distance / hours
        if speed <= SPEED_THRESHOLD_KMH:
            return None

        company = getattr(user, 'company', None)
        detail = ('Voyage impossible : %.0f km en %.1f h (%.0f km/h) — '
                  'connexion %s vs %s') % (
                      distance, hours, speed, ip, last.ip_address)
        try:
            from apps.audit.recorder import record
            from apps.audit.models import AuditLog
            record(AuditLog.Action.SECURITY_ALERT, user=user, company=company,
                   detail=detail)
        except Exception:
            pass
        _notify_directeurs(company, user, detail)
        return {'distance_km': distance, 'hours': hours, 'speed_kmh': speed}
    except Exception:
        logger.debug('detect_impossible_travel a échoué', exc_info=True)
        return None


def _notify_directeurs(company, user, detail):
    """Notifie les Directeurs de la société (best-effort, jamais bloquant)."""
    try:
        from apps.notifications.models import EventType
        from apps.notifications.services import notify, resolve_recipients
        for recipient in resolve_recipients(
                company, EventType.SECURITY_ALERT):
            notify(recipient, EventType.SECURITY_ALERT,
                   'Connexion suspecte détectée',
                   body=f'{getattr(user, "username", "?")} : {detail}',
                   company=company, respect_quiet_hours=False)
    except Exception:
        pass
