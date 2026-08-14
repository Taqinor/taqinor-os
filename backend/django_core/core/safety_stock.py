"""core/safety_stock.py — NTSCM5, stock de sécurité au niveau de service
(fondation pure, aucun import d'app métier — contrat import-linter
``core-foundation-is-a-base-layer``, comme :mod:`core.demand_forecast`,
:mod:`core.forecast`, :mod:`core.stock_reorder`).

Formule classique du stock de sécurité sous incertitude de la demande, délai
d'approvisionnement supposé constant :

    SS = z(niveau_service) × σ_demande × √délai

``avg_demand``/``std_dev_demand`` sont la consommation moyenne et son
écart-type (mêmes unités — journalières par convention dans cet ERP, voir
``apps.scm.services.appliquer_politique_stock``). ``avg_demand`` sert
UNIQUEMENT à la BORNE BASSE (``min_coverage_days`` jours de couverture) : un
article à demande parfaitement stable (σ≈0) garde quand même un minimum de
stock de sécurité au lieu de tomber à zéro ; un article à demande volatile
croît avec le niveau de service demandé (z plus grand)."""
from __future__ import annotations

import math

# Table z usuelle de la loi normale centrée réduite (pas de dépendance
# scipy — stdlib seulement, comme core.forecast/core.stock_reorder).
Z_TABLE = {
    90.0: 1.282,
    95.0: 1.645,
    97.5: 1.960,
    99.0: 2.326,
}
DEFAULT_SERVICE_LEVEL = 95.0
DEFAULT_MIN_COVERAGE_DAYS = 3.0


def _safe_float(raw, default=0.0):
    """Convertit en float ; ``None``/non numérique/NaN -> ``default`` (garde
    NaN AVANT tout clamp — une leçon FG361 : un NaN qui traverse un `max()`
    Python ne se comporte pas comme attendu selon l'ordre des opérandes)."""
    try:
        v = float(raw)
    except (TypeError, ValueError):
        return default
    if v != v:  # NaN
        return default
    return v


def z_for_service_level(service_level_pct) -> float:
    """z le plus proche de ``Z_TABLE`` pour le niveau de service demandé.

    Valeur non reconnue -> repli sur l'entrée de la table la plus proche
    (aucune interpolation — table stdlib volontairement restreinte à
    90/95/97.5/99%, les paliers usuels de politique de stock)."""
    pct = _safe_float(service_level_pct, DEFAULT_SERVICE_LEVEL)
    if pct in Z_TABLE:
        return Z_TABLE[pct]
    nearest = min(Z_TABLE, key=lambda k: abs(k - pct))
    return Z_TABLE[nearest]


def compute_safety_stock(
    avg_demand,
    std_dev_demand,
    lead_time_days,
    service_level_pct,
    *,
    min_coverage_days=DEFAULT_MIN_COVERAGE_DAYS,
) -> float:
    """Stock de sécurité = ``max(borne_basse, z × σ × √délai)``.

    - ``avg_demand`` / ``std_dev_demand`` : consommation moyenne et
      écart-type (mêmes unités, ex. par jour).
    - ``lead_time_days`` : délai fournisseur, en jours (négatif -> 0).
    - ``service_level_pct`` : 90/95/97.5/99 (voir :data:`Z_TABLE`).
    - ``min_coverage_days`` : nombre de jours de couverture qui définit la
      BORNE BASSE (``min_coverage_days × avg_demand``) — jamais nul même à
      variabilité nulle.

    Renvoie un ``float >= 0``. Pur, déterministe, sans base de données ni
    réseau."""
    avg = max(0.0, _safe_float(avg_demand))
    sigma = max(0.0, _safe_float(std_dev_demand))
    lead_time = max(0.0, _safe_float(lead_time_days))
    floor = max(0.0, _safe_float(min_coverage_days)) * avg

    z = z_for_service_level(service_level_pct)
    ss_statistique = (z * sigma * math.sqrt(lead_time)) if lead_time > 0 else 0.0

    return max(floor, ss_statistique)
