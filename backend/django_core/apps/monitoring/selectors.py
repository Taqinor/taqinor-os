"""
Sélecteurs monitoring (lecture) — agrégations multi-systèmes (FG281).

Vue PARC/FLOTTE : production totale, kWc installés, PR moyen et alertes
ouvertes sur l'ensemble des systèmes actifs d'une société. 100 % lecture,
scoping société assuré par l'appelant (viewset filtre déjà par company).
"""
from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

from django.db.models import Sum
from django.utils import timezone

from .models import (
    MonitoringConfig, ProductionReading, UnderperformanceFlag,
)
from .services import _expected_recent_kwh


def _q(value, places='0.01'):
    return Decimal(str(value)).quantize(Decimal(places)) if value is not None else None


def fleet_overview(company, *, window_days=365, today=None):
    """Synthèse parc d'une société sur la fenêtre récente.

    Renvoie production totale, kWc cumulés, PR moyen pondéré par l'attendu,
    nombre de systèmes actifs, et alertes (drapeaux de sous-performance
    ouverts). Réutilise la logique d'attendu du service N52.
    """
    today = today or timezone.localdate()
    since = today - timedelta(days=window_days)

    # Systèmes actifs supervisés : tout chantier ayant une config monitoring.
    configs = (MonitoringConfig.objects
               .filter(company=company)
               .select_related('installation'))

    total_kwh = Decimal('0')
    total_expected = Decimal('0')
    total_kwc = Decimal('0')
    systems = []
    active_count = 0

    for config in configs:
        inst = config.installation
        if not getattr(inst, 'parc_actif', True):
            continue
        active_count += 1
        kwc = inst.puissance_installee_kwc or Decimal('0')
        total_kwc += Decimal(str(kwc))

        prod = ProductionReading.objects.filter(
            installation=inst, date__gte=since, date__lte=today
        ).aggregate(s=Sum('energy_kwh'))['s'] or Decimal('0')
        prod = Decimal(str(prod))
        total_kwh += prod

        expected = _expected_recent_kwh(inst, config, window_days)
        pr_pct = None
        if expected and expected > 0:
            total_expected += expected
            pr_pct = _q((prod / expected) * Decimal('100'))

        systems.append({
            'installation': inst.id,
            'reference': getattr(inst, 'reference', None),
            'puissance_kwc': _q(kwc),
            'production_kwh': _q(prod),
            'pr_pct': pr_pct,
        })

    fleet_pr = None
    if total_expected > 0:
        fleet_pr = _q((total_kwh / total_expected) * Decimal('100'))

    open_alerts = UnderperformanceFlag.objects.filter(
        company=company, is_open=True).count()

    return {
        'window_days': window_days,
        'systems_active': active_count,
        'total_kwc': _q(total_kwc),
        'total_production_kwh': _q(total_kwh),
        'fleet_pr_pct': fleet_pr,
        'open_alerts': open_alerts,
        'systems': systems,
    }
