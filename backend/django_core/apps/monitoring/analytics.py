"""
Analytique O&M (FG279) — indicateurs de supervision par système installé.

Calcule, à partir des `ProductionReading` d'UN système, les indicateurs
classiques d'exploitation-maintenance :

  * Performance Ratio (PR) — production réelle / production attendue sur la
    fenêtre (l'attendu vient de `MonitoringConfig.expected_annual_kwh`, sinon
    estimé depuis la puissance × productible conservateur, comme le service
    de sous-performance).
  * Disponibilité — part des jours de la fenêtre couverts par au moins un
    relevé (proxy raisonnable sans télémétrie d'onduleur dédiée).
  * Soiling (salissure) — dérive du PR mensuel : un PR mensuel qui décroît
    régulièrement signale un encrassement progressif (estimation, pas une
    mesure d'irradiance).
  * Dégradation annualisée — pente du PR sur les 12 derniers mois ramenée en
    %/an (proxy de la dégradation des modules + dérive d'encrassement).

100 % LECTURE : aucune écriture, aucun appel réseau. Réutilise la logique
d'attendu du service N52 sans la dupliquer.
"""
from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

from django.db.models import Sum
from django.db.models.functions import TruncMonth
from django.utils import timezone

from core.analytics_db import analytics_queryset

from .models import CleaningEvent, ProductionReading
from .services import _expected_recent_kwh, get_or_create_config

# Fenêtre par défaut (jours) d'analyse O&M.
DEFAULT_WINDOW_DAYS = 365

# FG283 — perte de PR (points de %) au-delà de laquelle on recommande un
# nettoyage, et nombre de jours sans nettoyage déclenchant aussi la reco
# (régions poussiéreuses).
SOILING_PR_DROP_PCT = Decimal('5')
SOILING_MAX_DAYS_SINCE_CLEAN = 120


def _q(value, places='0.01'):
    return Decimal(str(value)).quantize(Decimal(places)) if value is not None else None


def _monthly_series(installation, since, today):
    """Série mensuelle [(month_date, kwh_decimal)] triée croissant."""
    # YHARD9 — agrégat BI lourd (série mensuelle) : route vers le réplica
    # analytique si configuré (no-op strict sinon). 100 % lecture.
    qs = (analytics_queryset(ProductionReading.objects)
          .filter(installation=installation, date__gte=since, date__lte=today)
          .annotate(month=TruncMonth('date'))
          .values('month')
          .annotate(total=Sum('energy_kwh'))
          .order_by('month'))
    return [(row['month'], Decimal(str(row['total'] or 0))) for row in qs]


def _linear_slope(points):
    """Pente d'une régression linéaire simple sur [(x_int, y_float)].

    Renvoie None si moins de 2 points ou variance nulle.
    """
    n = len(points)
    if n < 2:
        return None
    sx = sum(p[0] for p in points)
    sy = sum(p[1] for p in points)
    sxx = sum(p[0] * p[0] for p in points)
    sxy = sum(p[0] * p[1] for p in points)
    denom = (n * sxx) - (sx * sx)
    if denom == 0:
        return None
    return ((n * sxy) - (sx * sy)) / denom


def om_metrics(installation, *, window_days=DEFAULT_WINDOW_DAYS, today=None):
    """Indicateurs O&M d'un système sur la fenêtre récente.

    Renvoie un dict prêt à sérialiser. No-op gracieux (champs None) si aucune
    donnée de production ou aucun attendu n'est disponible.
    """
    today = today or timezone.localdate()
    since = today - timedelta(days=window_days)
    config = get_or_create_config(installation)

    # YHARD9 — lecture BI (relevés de production sur la fenêtre) : réplica si
    # configuré, no-op strict sinon. 100 % lecture.
    readings = analytics_queryset(ProductionReading.objects).filter(
        installation=installation, date__gte=since, date__lte=today)
    total_kwh = Decimal('0')
    days_with_data = set()
    for r in readings.values_list('energy_kwh', 'date', 'period_days'):
        total_kwh += Decimal(str(r[0]))
        days_with_data.add(r[1])

    expected = _expected_recent_kwh(installation, config, window_days)
    pr_pct = None
    if expected and expected > 0:
        pr_pct = _q((total_kwh / expected) * Decimal('100'))

    # Disponibilité : jours couverts / jours de la fenêtre.
    availability_pct = _q(
        (Decimal(len(days_with_data)) / Decimal(window_days)) * Decimal('100'))

    # PR mensuel pour soiling + dégradation.
    monthly = _monthly_series(installation, since, today)
    expected_monthly = (Decimal(str(config.expected_annual_kwh)) / Decimal('12')
                        if config.expected_annual_kwh else None)
    if expected_monthly is None and expected and expected > 0:
        # Estimé : attendu fenêtre ramené au mois.
        expected_monthly = expected / (Decimal(window_days) / Decimal('30'))

    monthly_pr = []
    pr_points = []
    for idx, (month, kwh) in enumerate(monthly):
        ratio = None
        if expected_monthly and expected_monthly > 0:
            ratio = (kwh / expected_monthly) * Decimal('100')
            pr_points.append((idx, float(ratio)))
        monthly_pr.append({
            'month': month.strftime('%Y-%m'),
            'kwh': _q(kwh),
            'pr_pct': _q(ratio) if ratio is not None else None,
        })

    # Dégradation/soiling : pente du PR mensuel (points/mois) → %/an.
    slope = _linear_slope(pr_points)
    degradation_pct_per_year = _q(slope * 12) if slope is not None else None
    # Soiling probable si la pente est négative et significative (> 0,5 %/mois).
    soiling_suspected = bool(slope is not None and slope < -0.5)

    return {
        'installation': installation.id,
        'window_days': window_days,
        'production_kwh': _q(total_kwh),
        'expected_kwh': _q(expected) if expected is not None else None,
        'pr_pct': pr_pct,
        'availability_pct': availability_pct,
        'degradation_pct_per_year': degradation_pct_per_year,
        'soiling_suspected': soiling_suspected,
        'monthly_pr': monthly_pr,
    }


def soiling_assessment(installation, *, window_days=DEFAULT_WINDOW_DAYS,
                       today=None):
    """FG283 — estime la perte par salissure et recommande un nettoyage.

    Compare le PR mensuel le PLUS RÉCENT à la meilleure baseline de PR mensuel
    de la fenêtre (proxy de l'état « propre »). La chute = perte estimée par
    salissure (points de %). Recommande un nettoyage si la chute dépasse le
    seuil OU si trop de jours se sont écoulés depuis le dernier nettoyage.
    100 % lecture.
    """
    today = today or timezone.localdate()
    metrics = om_metrics(installation, window_days=window_days, today=today)
    monthly_pr = [m for m in metrics['monthly_pr'] if m['pr_pct'] is not None]

    last_clean = (CleaningEvent.objects
                  .filter(installation=installation, date__lte=today)
                  .order_by('-date').first())
    days_since_clean = (
        (today - last_clean.date).days if last_clean else None)

    pr_drop = None
    current_pr = None
    baseline_pr = None
    if monthly_pr:
        current_pr = monthly_pr[-1]['pr_pct']
        baseline_pr = max(m['pr_pct'] for m in monthly_pr)
        pr_drop = _q(baseline_pr - current_pr)

    recommend = False
    reasons = []
    if pr_drop is not None and pr_drop >= SOILING_PR_DROP_PCT:
        recommend = True
        reasons.append('chute de PR significative')
    if (days_since_clean is not None
            and days_since_clean >= SOILING_MAX_DAYS_SINCE_CLEAN):
        recommend = True
        reasons.append('délai depuis le dernier nettoyage')
    if last_clean is None and (days_since_clean is None) and monthly_pr:
        # Jamais nettoyé et PR dégradé : on recommande aussi.
        if pr_drop is not None and pr_drop >= SOILING_PR_DROP_PCT:
            reasons.append('aucun nettoyage enregistré')

    return {
        'installation': installation.id,
        'current_pr_pct': current_pr,
        'baseline_pr_pct': baseline_pr,
        'estimated_soiling_loss_pct': pr_drop,
        'last_cleaning_date': (
            last_clean.date.isoformat() if last_clean else None),
        'days_since_cleaning': days_since_clean,
        'recommend_cleaning': recommend,
        'reasons': reasons,
    }
