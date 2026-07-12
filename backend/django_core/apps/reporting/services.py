"""Orchestration inter-app de l'app reporting.

VX61 — `WebVitalMetric` grossit vite (une ligne par métrique par
navigation) : purge programmée via le registre partagé YOPSB10
(`core.retention`), enregistrée dans `ReportingConfig.ready()`. Fenêtre par
défaut 30 jours (bien plus court que les 180 j CRM — ce ne sont que des
mesures de performance agrégées, pas des données métier), founder-override
via `WEB_VITALS_RETENTION_DAYS` (settings/.env, même patron que
`apps/crm/services.py`). 0/négatif désactive la purge (conservation
illimitée, comportement actuel inchangé).
"""
from django.utils import timezone

DEFAULT_WEB_VITALS_RETENTION_DAYS = 30


def _retention_days(setting_name, default_days):
    from django.conf import settings
    value = getattr(settings, setting_name, None)
    if value is None:
        return default_days
    try:
        return int(value)
    except (TypeError, ValueError):
        return default_days


def purge_web_vitals(now, apply_) -> int:
    """VX61 — purge les `WebVitalMetric` au-delà de la fenêtre de
    rétention. Contrat `core.retention` : `apply_=False` (dry-run) ne
    supprime rien, renvoie le compte qui SERAIT supprimé."""
    from .models import WebVitalMetric

    days = _retention_days(
        'WEB_VITALS_RETENTION_DAYS', DEFAULT_WEB_VITALS_RETENTION_DAYS)
    if days <= 0:
        return 0
    cutoff = (now or timezone.now()) - timezone.timedelta(days=days)
    qs = WebVitalMetric.objects.filter(created_at__lt=cutoff)
    count = qs.count()
    if apply_ and count:
        qs.delete()
    return count
