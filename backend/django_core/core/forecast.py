"""FG361 — Prévision de ventes / demande (séries temporelles), fondation pure.

Comme :mod:`core.anomaly`, ce module reste une couche de BASE — contrat
import-linter ``core-foundation-is-a-base-layer`` : il n'importe AUCUNE app
métier. L'app appelante (ventes…) agrège son historique via SA couche
``selectors`` (CA mensuel, volume de devis par mois) et passe la série
``(mois, valeur)`` à :func:`forecast_series`. core fournit uniquement le moteur
mathématique générique ; il ne touche jamais la base ni le réseau.

Deux niveaux de modèle, choisis automatiquement :

  1. **statsmodels** (Holt-Winters / lissage exponentiel) lorsque la dépendance
     est installée ET que la série est assez longue. Capte tendance et
     saisonnalité annuelle (période 12) si possible.
  2. **Repli pur Python** (régression linéaire des moindres carrés sur l'index
     temporel, sinon moyenne glissante) lorsque statsmodels est absent ou que la
     série est trop courte. Garantit que le code — et les tests — fonctionnent
     même si l'image n'a pas encore été reconstruite avec statsmodels.

L'import de statsmodels est DÉFENSIF (``try/except ImportError``) : aucune
fonction n'exige que statsmodels soit importable.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Iterable, Sequence

# Import défensif : statsmodels est pré-approuvé et épinglé dans requirements,
# mais le code degrade proprement s'il est absent au runtime (image non encore
# reconstruite). On ne lève jamais : on bascule sur le repli pur Python.
try:  # pragma: no cover - dépend de l'environnement
    from statsmodels.tsa.holtwinters import ExponentialSmoothing as _ExpSmoothing
    _HAS_STATSMODELS = True
except Exception:  # pragma: no cover - ImportError ou échec de dépendance
    _ExpSmoothing = None
    _HAS_STATSMODELS = False


def statsmodels_available() -> bool:
    """Indique si statsmodels a pu être importé (utile pour les tests/diagnostic)."""
    return _HAS_STATSMODELS


@dataclass
class ForecastPoint:
    """Un mois prévu (``YYYY-MM``) avec sa valeur projetée."""

    period: str          # 'YYYY-MM'
    value: float         # valeur prévue (>= 0)


@dataclass
class ForecastResult:
    """Résultat d'une prévision de série mensuelle."""

    history: list[tuple[str, float]] = field(default_factory=list)
    forecast: list[ForecastPoint] = field(default_factory=list)
    method: str = ''     # 'holt-winters' | 'linear-trend' | 'moving-average' | 'flat'
    trend_per_month: float = 0.0   # pente estimée (variation moyenne / mois)


def _coerce_period(raw) -> str | None:
    """Normalise une clé de mois en ``YYYY-MM``.

    Accepte ``date``/``datetime`` (jour ignoré), ``'YYYY-MM'`` ou ``'YYYY-MM-DD'``.
    Renvoie ``None`` si non interprétable (la ligne est alors ignorée).
    """
    if raw is None:
        return None
    if isinstance(raw, date):
        return f'{raw.year:04d}-{raw.month:02d}'
    s = str(raw).strip()
    if len(s) >= 7 and s[4] == '-' and s[:4].isdigit() and s[5:7].isdigit():
        return s[:7]
    return None


def _next_period(period: str) -> str:
    """Mois suivant en ``YYYY-MM`` (gère le passage d'année)."""
    year = int(period[:4])
    month = int(period[5:7])
    month += 1
    if month > 12:
        month = 1
        year += 1
    return f'{year:04d}-{month:02d}'


def _normalize_series(
    points: Iterable,
    *,
    period_key: str = 'period',
    value_key: str = 'value',
) -> list[tuple[str, float]]:
    """Trie/dédoublonne/somme la série en ``[(YYYY-MM, valeur), ...]`` croissante.

    ``points`` est un itérable de dicts ``{period, value}`` ou de tuples
    ``(period, value)``. Les périodes non interprétables ou les valeurs non
    numériques sont ignorées. Les valeurs d'un même mois sont sommées.
    """
    bucket: dict[str, float] = {}
    for p in points or []:
        if isinstance(p, dict):
            raw_period = p.get(period_key)
            raw_value = p.get(value_key)
        else:
            try:
                raw_period, raw_value = p[0], p[1]
            except (TypeError, IndexError, KeyError):
                continue
        period = _coerce_period(raw_period)
        if period is None:
            continue
        try:
            val = float(raw_value)
        except (TypeError, ValueError):
            continue
        bucket[period] = bucket.get(period, 0.0) + val
    return sorted(bucket.items())


def _linear_trend(values: Sequence[float]) -> tuple[float, float]:
    """Régression linéaire moindres carrés sur l'index 0..n-1.

    Renvoie ``(pente, ordonnée)`` (``y = pente * x + ordonnée``). Pente nulle si
    moins de deux points ou variance d'index nulle.
    """
    n = len(values)
    if n < 2:
        return 0.0, (values[0] if values else 0.0)
    xs = list(range(n))
    mean_x = sum(xs) / n
    mean_y = sum(values) / n
    denom = sum((x - mean_x) ** 2 for x in xs)
    if denom == 0:
        return 0.0, mean_y
    num = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, values))
    slope = num / denom
    intercept = mean_y - slope * mean_x
    return slope, intercept


def _forecast_pure_python(
    values: Sequence[float],
    horizon: int,
) -> tuple[list[float], str, float]:
    """Prévision de repli sans dépendance : tendance linéaire, sinon moyenne.

    Renvoie ``(valeurs_prévues, méthode, pente)``. Les valeurs sont bornées à
    ``>= 0`` (un CA / volume de devis ne peut être négatif).
    """
    n = len(values)
    if n == 0:
        return [0.0] * horizon, 'flat', 0.0
    if n == 1:
        return [max(0.0, values[0])] * horizon, 'flat', 0.0

    slope, intercept = _linear_trend(values)
    if slope == 0.0:
        # Aucune tendance : moyenne glissante des derniers points (max 3).
        window = values[-3:]
        avg = sum(window) / len(window)
        return [max(0.0, avg)] * horizon, 'moving-average', 0.0

    out = []
    for h in range(1, horizon + 1):
        projected = slope * (n - 1 + h) + intercept
        out.append(max(0.0, projected))
    return out, 'linear-trend', slope


def _forecast_holt_winters(
    values: Sequence[float],
    horizon: int,
) -> tuple[list[float], str, float] | None:
    """Prévision statsmodels (Holt-Winters). ``None`` si indisponible/échec.

    Saisonnalité annuelle (12) activée seulement avec >= 24 points ; sinon
    tendance additive simple. Tout échec numérique retombe sur ``None`` pour que
    l'appelant bascule sur le repli pur Python.
    """
    if not _HAS_STATSMODELS or len(values) < 4:
        return None
    try:
        seasonal_periods = 12 if len(values) >= 24 else None
        kwargs = {'trend': 'add'}
        if seasonal_periods:
            kwargs['seasonal'] = 'add'
            kwargs['seasonal_periods'] = seasonal_periods
        model = _ExpSmoothing(
            list(values),
            initialization_method='estimated',
            **kwargs,
        )
        fitted = model.fit()
        predicted = fitted.forecast(horizon)
        raw = [float(v) for v in predicted]
        # Garde NaN AVANT le clamp : max(0.0, nan) renvoie 0.0 (0.0 > nan est
        # False), donc tester le NaN après clamp ne déclencherait jamais le repli.
        if len(raw) != horizon or any(v != v for v in raw):  # NaN guard
            return None
        out = [max(0.0, v) for v in raw]
        # Pente moyenne estimée sur l'horizon prévu.
        slope = (out[-1] - out[0]) / (horizon - 1) if horizon > 1 else 0.0
        return out, 'holt-winters', slope
    except Exception:
        return None


def forecast_series(
    points: Iterable,
    *,
    horizon: int = 6,
    period_key: str = 'period',
    value_key: str = 'value',
) -> ForecastResult:
    """Prévoit les ``horizon`` prochains mois d'une série mensuelle historique.

    ``points`` : itérable de ``{period, value}`` (ou tuples ``(period, value)``)
    fourni par l'app appelante depuis SES selectors (jamais importés ici) — p.ex.
    CA mensuel ou volume de devis par mois. ``period`` accepte ``date`` ou
    ``'YYYY-MM'``. Utilise statsmodels (Holt-Winters) si disponible et série
    suffisante, sinon une tendance linéaire / moyenne glissante pure Python.

    Renvoie un :class:`ForecastResult` (historique normalisé + prévision + méthode
    employée). Pur, déterministe pour le repli, sans base de données.
    """
    horizon = max(0, int(horizon))
    history = _normalize_series(
        points, period_key=period_key, value_key=value_key,
    )

    if horizon == 0 or not history:
        return ForecastResult(history=history, forecast=[], method='flat')

    values = [v for _, v in history]

    result = _forecast_holt_winters(values, horizon)
    if result is None:
        result = _forecast_pure_python(values, horizon)
    predicted, method, slope = result

    last_period = history[-1][0]
    forecast_points: list[ForecastPoint] = []
    period = last_period
    for val in predicted:
        period = _next_period(period)
        forecast_points.append(ForecastPoint(period=period, value=round(val, 2)))

    return ForecastResult(
        history=history,
        forecast=forecast_points,
        method=method,
        trend_per_month=round(slope, 4),
    )
