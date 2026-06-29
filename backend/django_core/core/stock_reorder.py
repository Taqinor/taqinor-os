"""FG364 — Prévision de réappro stock, fondation pure.

Comme :mod:`core.anomaly`, :mod:`core.forecast`, :mod:`core.win_probability` et
:mod:`core.churn_risk`, ce module reste une couche de BASE — contrat import-linter
``core-foundation-is-a-base-layer`` : il n'importe AUCUNE app métier. L'app
appelante (stock…) agrège l'historique de mouvements d'un produit via SA couche
``selectors`` (sorties de stock par date, ou simplement la consommation moyenne
journalière déjà calculée) et passe ces ENTRÉES à :func:`predict_reorder` ; core
fournit uniquement le moteur de calcul générique et ne touche jamais la base ni
le réseau (librairie standard seulement).

À partir de l'historique de sorties (ou d'une conso moyenne fournie), du stock
actuel, du délai de réapprovisionnement (``lead_time_days``) et d'un stock de
sécurité (``safety_stock``), le module renvoie :

  * la **date de rupture** prévue (``today + stock_actuel / conso_journalière``) ;
  * la **quantité suggérée** de réappro (couvre ``lead_time + cycle`` au-delà du
    stock de sécurité : ``conso × (lead_time + review_period) + safety − on_hand``,
    bornée à >= 0, arrondie à l'unité supérieure) ;
  * le **point de commande** (ROP = ``conso × lead_time + safety``) ;
  * un drapeau **reorder_now** : ``True`` si le stock actuel est <= ROP (la rupture
    surviendra avant qu'un réappro lancé aujourd'hui n'arrive).

GARDE-FOUS : conso journalière nulle (ou négative, ou aucun historique) ⇒ pas de
rupture prévisible (``rupture_date = None``, ``days_until_rupture = None``), aucune
suggestion de réappro et ``reorder_now = False`` — l'appelant garde un résultat
exploitable plutôt qu'une division par zéro. ``today`` est passé en paramètre
(``date.today()`` n'est jamais appelé ici) : le module reste pur et déterministe,
sans base de données ni réseau.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Iterable, Optional

# Fenêtre de réapprovisionnement par défaut (jours) ajoutée au délai
# fournisseur quand on calcule la quantité suggérée : on couvre le délai PLUS un
# cycle de commande, pour ne pas recommander à chaque mouvement.
DEFAULT_REVIEW_PERIOD_DAYS = 30.0

# Nombre maximal de jours d'historique récent pris en compte pour estimer la
# consommation moyenne journalière (les très vieux mouvements ne reflètent plus
# la demande courante). 0 ou négatif = pas de filtre.
DEFAULT_LOOKBACK_DAYS = 90


@dataclass
class ReorderResult:
    """Résultat de :func:`predict_reorder`.

    ``avg_daily_consumption`` est la conso journalière estimée (>= 0).
    ``rupture_date`` est la date de rupture prévue, ou ``None`` si la conso est
    nulle (jamais de rupture prévisible). ``days_until_rupture`` est le nombre de
    jours d'ici la rupture (``None`` si pas de rupture). ``reorder_point`` est le
    point de commande (ROP). ``suggested_quantity`` est la quantité de réappro
    suggérée (>= 0, entière). ``reorder_now`` indique s'il faut commander
    maintenant (stock <= ROP). ``used_fallback`` vaut ``True`` si aucune conso
    exploitable n'a pu être estimée (pas d'historique / conso nulle)."""

    avg_daily_consumption: float
    rupture_date: Optional[date] = None
    days_until_rupture: Optional[float] = None
    reorder_point: float = 0.0
    suggested_quantity: int = 0
    reorder_now: bool = False
    used_fallback: bool = False
    factors: dict = field(default_factory=dict)


def _coerce_float(raw, default=None):
    """Convertit en ``float`` ou renvoie ``default`` si non numérique/absent."""
    if raw is None:
        return default
    try:
        return float(raw)
    except (TypeError, ValueError):
        return default


def _coerce_date(raw) -> Optional[date]:
    """Normalise une entrée en :class:`datetime.date`.

    Accepte ``date``/``datetime`` (jour conservé), ou ``'YYYY-MM-DD'``. Renvoie
    ``None`` si non interprétable (la ligne est alors ignorée).
    """
    if raw is None:
        return None
    if isinstance(raw, date):
        # datetime est une sous-classe de date : on garde juste la part date.
        return date(raw.year, raw.month, raw.day)
    s = str(raw).strip()
    if len(s) >= 10 and s[4] == '-' and s[7] == '-':
        try:
            return date(int(s[:4]), int(s[5:7]), int(s[8:10]))
        except ValueError:
            return None
    return None


def average_daily_consumption(
    movements: Iterable,
    *,
    today: date,
    lookback_days: int = DEFAULT_LOOKBACK_DAYS,
    date_key: str = 'date',
    qty_key: str = 'qty_out',
) -> float:
    """Consommation moyenne journalière à partir d'un historique de sorties.

    ``movements`` : itérable de ``{date, qty_out}`` (ou tuples ``(date, qty_out)``)
    fourni par l'app appelante depuis SES selectors. Seules les sorties (quantité
    > 0) des ``lookback_days`` derniers jours sont prises en compte. La moyenne se
    fait sur la durée de la fenêtre réellement observée (du premier mouvement
    retenu à ``today``), avec un minimum de 1 jour pour éviter toute division par
    zéro. Renvoie ``0.0`` si aucun mouvement exploitable.
    """
    cutoff: Optional[date] = None
    if lookback_days and lookback_days > 0:
        cutoff = today - timedelta(days=lookback_days)

    total_out = 0.0
    earliest: Optional[date] = None
    for m in movements or []:
        if isinstance(m, dict):
            raw_date = m.get(date_key)
            raw_qty = m.get(qty_key)
        else:
            try:
                raw_date, raw_qty = m[0], m[1]
            except (TypeError, IndexError, KeyError):
                continue
        d = _coerce_date(raw_date)
        qty = _coerce_float(raw_qty)
        if d is None or qty is None or qty <= 0:
            continue
        if cutoff is not None and d < cutoff:
            continue
        if d > today:
            continue
        total_out += qty
        if earliest is None or d < earliest:
            earliest = d

    if earliest is None or total_out <= 0:
        return 0.0

    span_days = (today - earliest).days
    if span_days < 1:
        span_days = 1
    return total_out / span_days


def predict_reorder(
    *,
    current_stock,
    today: date,
    avg_daily_consumption: Optional[float] = None,
    movements: Optional[Iterable] = None,
    lead_time_days=0,
    safety_stock=0,
    review_period_days: float = DEFAULT_REVIEW_PERIOD_DAYS,
    lookback_days: int = DEFAULT_LOOKBACK_DAYS,
) -> ReorderResult:
    """Prévoit la rupture de stock et suggère un réappro pour un produit.

    Entrées (toutes passées par l'appelant — JAMAIS d'import d'app métier ici) :

      * ``current_stock``        — stock actuel en main (on-hand) ;
      * ``today``                — date de référence (``date.today()`` n'est PAS
        appelé ici, le module reste pur et déterministe) ;
      * ``avg_daily_consumption``— conso moyenne journalière déjà calculée ; si
        absente, elle est estimée depuis ``movements`` ;
      * ``movements``            — historique de sorties ``{date, qty_out}`` (ou
        tuples) utilisé seulement si ``avg_daily_consumption`` n'est pas fourni ;
      * ``lead_time_days``       — délai de réapprovisionnement fournisseur ;
      * ``safety_stock``         — stock de sécurité à préserver ;
      * ``review_period_days``   — cycle de commande couvert en plus du délai ;
      * ``lookback_days``        — fenêtre d'historique pour estimer la conso.

    Calculs :

      * date de rupture = ``today + current_stock / conso_journalière`` ;
      * point de commande (ROP) = ``conso × lead_time + safety_stock`` ;
      * quantité suggérée = ``conso × (lead_time + review_period) + safety
        − current_stock``, bornée à >= 0 et arrondie à l'unité supérieure ;
      * ``reorder_now`` = ``current_stock <= ROP``.

    GARDE-FOU division par zéro : si la conso journalière est nulle/négative (ou
    aucun historique exploitable), il n'y a PAS de rupture prévisible
    (``rupture_date = None``), aucune suggestion de réappro et
    ``reorder_now = False`` ; ``used_fallback`` vaut alors ``True``.

    Pur, déterministe, sans base de données ni réseau.
    """
    on_hand = _coerce_float(current_stock, 0.0) or 0.0
    lead_time = _coerce_float(lead_time_days, 0.0) or 0.0
    if lead_time < 0:
        lead_time = 0.0
    safety = _coerce_float(safety_stock, 0.0) or 0.0
    if safety < 0:
        safety = 0.0
    review = _coerce_float(review_period_days, DEFAULT_REVIEW_PERIOD_DAYS)
    if review is None or review < 0:
        review = 0.0

    # Conso journalière : fournie directement, sinon estimée depuis l'historique.
    daily = _coerce_float(avg_daily_consumption)
    if daily is None and movements is not None:
        daily = average_daily_consumption(
            movements, today=today, lookback_days=lookback_days,
        )
    if daily is None:
        daily = 0.0

    factors: dict = {
        'avg_daily_consumption': round(daily, 4),
        'lead_time_days': round(lead_time, 4),
        'safety_stock': round(safety, 4),
    }

    # ── GARDE-FOU : conso nulle/négative ⇒ aucune rupture prévisible ─────────
    if daily <= 0:
        return ReorderResult(
            avg_daily_consumption=0.0,
            rupture_date=None,
            days_until_rupture=None,
            reorder_point=round(safety, 4),
            suggested_quantity=0,
            reorder_now=False,
            used_fallback=True,
            factors=factors,
        )

    # ── Date de rupture : stock actuel / conso journalière ──────────────────
    days_until = on_hand / daily
    # Un stock déjà négatif/nul ⇒ rupture aujourd'hui (0 jour).
    if days_until < 0:
        days_until = 0.0
    rupture_date = today + timedelta(days=int(days_until))

    # ── Point de commande (ROP) et quantité suggérée ────────────────────────
    reorder_point = daily * lead_time + safety
    cover_target = daily * (lead_time + review) + safety
    suggested = cover_target - on_hand
    if suggested < 0:
        suggested = 0.0
    # Arrondi à l'unité supérieure : on ne commande jamais une fraction de pièce.
    suggested_qty = int(suggested) + (1 if suggested > int(suggested) else 0)

    reorder_now = on_hand <= reorder_point

    factors['reorder_point'] = round(reorder_point, 4)
    factors['cover_target'] = round(cover_target, 4)

    return ReorderResult(
        avg_daily_consumption=round(daily, 4),
        rupture_date=rupture_date,
        days_until_rupture=round(days_until, 2),
        reorder_point=round(reorder_point, 4),
        suggested_quantity=suggested_qty,
        reorder_now=reorder_now,
        used_fallback=False,
        factors=factors,
    )
