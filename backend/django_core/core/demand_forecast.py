"""core/demand_forecast.py — NTSCM2, moteur de prévision saisonnière
(fondation pure).

Comme :mod:`core.forecast`, :mod:`core.stock_reorder` et
:mod:`core.safety_stock`, ce module reste une couche de BASE — contrat
import-linter ``core-foundation-is-a-base-layer`` : il n'importe AUCUNE app
métier. L'app appelante (``apps.scm``) agrège l'historique mensuel de sorties
d'un produit via les sélecteurs/services de l'app propriétaire de la donnée
(``apps.stock``) et passe cet historique en ENTRÉE à :func:`forecast_demand` ;
ce module ne touche jamais la base ni le réseau (librairie standard
seulement).

Algorithme : moyenne mobile pondérée (les mois récents pèsent plus) sur les
``window`` derniers mois, corrigée par un indice saisonnier par
mois-calendaire (12 coefficients = moyenne, sur toutes les années
disponibles, du ratio valeur-du-mois / moyenne-annuelle-de-cette-année).
GARDE-FOU : moins de 12 mois d'historique ⇒ repli sur une moyenne simple sans
saisonnalité (``used_fallback=True``) — un motif saisonnier n'est pas fiable
sur moins d'une année complète.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Iterable, Optional

# En-dessous de ce nombre de mois d'historique, aucun indice saisonnier
# fiable ne peut être calculé (il faudrait plusieurs occurrences de chaque
# mois-calendaire) : repli sur une moyenne simple.
MIN_HISTORY_MONTHS_FOR_SEASONALITY = 12

# Fenêtre par défaut de la moyenne mobile pondérée (derniers N mois).
DEFAULT_WINDOW = 3


@dataclass
class DemandForecastResult:
    """Résultat de :func:`forecast_demand`.

    ``historique`` : ``[(periode, quantite), ...]`` normalisé, trié
    chronologiquement. ``previsions`` : même forme, pour les mois futurs
    demandés. ``used_fallback`` : ``True`` si l'historique était trop court
    pour une saisonnalité fiable (repli moyenne simple). ``indices_saisonniers``
    : ``{mois_calendaire(1-12): coefficient}``, vide si repli.
    ``base_moyenne_mobile`` : le niveau de base (avant coefficient saisonnier)
    utilisé pour projeter."""

    historique: list
    previsions: list
    used_fallback: bool
    indices_saisonniers: dict
    base_moyenne_mobile: float
    factors: dict = field(default_factory=dict)


def _coerce_periode(raw) -> Optional[str]:
    """Normalise en ``'YYYY-MM'``, ou ``None`` si non interprétable."""
    if raw is None:
        return None
    if isinstance(raw, date):
        return f'{raw.year:04d}-{raw.month:02d}'
    s = str(raw).strip()
    if len(s) >= 7 and s[4] == '-':
        try:
            y, m = int(s[:4]), int(s[5:7])
        except ValueError:
            return None
        if 1 <= m <= 12:
            return f'{y:04d}-{m:02d}'
    return None


def _coerce_float(raw, default=None):
    try:
        return float(raw)
    except (TypeError, ValueError):
        return default


def _normalize_history(history) -> list:
    """Normalise + trie chronologiquement l'historique fourni par l'appelant.

    Accepte ``{periode, quantite}`` ou des tuples ``(periode, quantite)``.
    Les doublons de période (ex. deux lignes pour le même mois) sont fusionnés
    par SOMME. Les lignes non interprétables (période/quantité invalide) sont
    silencieusement ignorées (l'appelant garde un résultat exploitable)."""
    buckets: dict[str, float] = {}
    for row in history or []:
        if isinstance(row, dict):
            raw_periode, raw_qty = row.get('periode'), row.get('quantite')
        else:
            try:
                raw_periode, raw_qty = row[0], row[1]
            except (TypeError, IndexError):
                continue
        periode = _coerce_periode(raw_periode)
        if periode is None:
            continue
        qty = _coerce_float(raw_qty)
        if qty is None:
            continue
        buckets[periode] = buckets.get(periode, 0.0) + qty
    return sorted(buckets.items())


def _month_index(periode: str) -> int:
    return int(periode[5:7])


def _next_periode(periode: str, n: int = 1) -> str:
    y, m = int(periode[:4]), int(periode[5:7])
    total = (y * 12 + (m - 1)) + n
    y2, m2 = divmod(total, 12)
    return f'{y2:04d}-{m2 + 1:02d}'


def weighted_moving_average(values: Iterable[float], *, window: int = DEFAULT_WINDOW) -> float:
    """Moyenne mobile pondérée sur les ``window`` dernières valeurs de
    ``values`` (trié chronologique, plus ancien → plus récent). Poids
    linéaires croissants : la valeur la plus récente pèse le plus. Renvoie
    ``0.0`` si ``values`` est vide."""
    values = list(values)
    if not values:
        return 0.0
    window = max(1, int(window))
    recent = values[-window:]
    n = len(recent)
    weights = list(range(1, n + 1))
    total_w = sum(weights)
    if total_w == 0:
        return sum(recent) / n
    return sum(v * w for v, w in zip(recent, weights)) / total_w


def seasonal_indices(history: list) -> dict:
    """Indice saisonnier par mois-calendaire (1-12).

    Pour chaque année représentée dans ``history`` (liste ``(periode, qty)``
    triée), on calcule le ratio ``valeur_du_mois / moyenne_annuelle_de_cette
    année`` ; l'indice d'un mois-calendaire est la MOYENNE de ses ratios sur
    toutes les années disponibles. Un indice de ``1.0`` = mois neutre, ``>1``
    = mois fort, ``<1`` = mois faible. Un mois-calendaire jamais observé
    renvoie ``1.0`` (neutre, pas d'effet)."""
    par_annee: dict[int, list[tuple[str, float]]] = {}
    for periode, qty in history:
        y = int(periode[:4])
        par_annee.setdefault(y, []).append((periode, qty))

    ratios_par_mois: dict[int, list[float]] = {m: [] for m in range(1, 13)}
    for rows in par_annee.values():
        valeurs = [q for _, q in rows]
        moyenne_annee = sum(valeurs) / len(valeurs) if valeurs else 0.0
        if moyenne_annee <= 0:
            continue
        for periode, qty in rows:
            ratios_par_mois[_month_index(periode)].append(qty / moyenne_annee)

    return {
        m: (sum(ratios) / len(ratios)) if ratios else 1.0
        for m, ratios in ratios_par_mois.items()
    }


def forecast_demand(
    history,
    *,
    horizon_mois: int = 3,
    window: int = DEFAULT_WINDOW,
) -> DemandForecastResult:
    """Prévoit la demande des ``horizon_mois`` prochains mois à partir d'un
    historique mensuel de sorties fourni par l'appelant (jamais lu ici).

    GARDE-FOU : moins de :data:`MIN_HISTORY_MONTHS_FOR_SEASONALITY` mois
    d'historique distincts ⇒ repli sur la moyenne simple de tout l'historique
    disponible, projetée à plat sur l'horizon (``used_fallback=True``, aucun
    indice saisonnier). Historique vide ⇒ prévisions vides.

    Pur, déterministe, sans base de données ni réseau."""
    normalized = _normalize_history(history)
    horizon_mois = max(0, int(horizon_mois))

    if len(normalized) < MIN_HISTORY_MONTHS_FOR_SEASONALITY:
        valeurs = [q for _, q in normalized]
        moyenne = (sum(valeurs) / len(valeurs)) if valeurs else 0.0
        previsions = []
        if normalized:
            dernier = normalized[-1][0]
            for i in range(1, horizon_mois + 1):
                previsions.append((_next_periode(dernier, i), round(moyenne, 2)))
        return DemandForecastResult(
            historique=normalized,
            previsions=previsions,
            used_fallback=True,
            indices_saisonniers={},
            base_moyenne_mobile=round(moyenne, 4),
            factors={'nb_mois_historique': len(normalized)},
        )

    indices = seasonal_indices(normalized)

    # Désaisonnalise l'historique AVANT de calculer le niveau de base : une
    # moyenne mobile calculée directement sur les valeurs BRUTES serait
    # biaisée par la saison des derniers mois observés (ex. un historique se
    # terminant en creux hivernal sous-estimerait systématiquement tous les
    # mois futurs, y compris les pics d'été) — c'est la décomposition
    # multiplicative classique : niveau = brut / indice_saisonnier(mois),
    # puis prévision = niveau × indice_saisonnier(mois_futur).
    valeurs_desaisonnalisees = [
        (qty / indices[_month_index(periode)]) if indices[_month_index(periode)] > 0 else qty
        for periode, qty in normalized
    ]
    base = weighted_moving_average(valeurs_desaisonnalisees, window=window)

    previsions = []
    dernier = normalized[-1][0]
    for i in range(1, horizon_mois + 1):
        periode = _next_periode(dernier, i)
        coeff = indices.get(_month_index(periode), 1.0)
        quantite = max(0.0, base * coeff)
        previsions.append((periode, round(quantite, 2)))

    return DemandForecastResult(
        historique=normalized,
        previsions=previsions,
        used_fallback=False,
        indices_saisonniers=indices,
        base_moyenne_mobile=round(base, 4),
        factors={'nb_mois_historique': len(normalized), 'fenetre': window},
    )
