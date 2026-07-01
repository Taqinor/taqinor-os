"""ROI / savings math — loi 82-21 self-consumption-first model.

Pure formulas (Morocco GHI irradiance + per-utility tariff tranches). No I/O,
no network, no Django — safe to call on the fly when generating a quote PDF.

TARIFF POLICY (loi 82-21, June 2026)
--------------------------------------
Savings are SELF-CONSUMPTION-FIRST: only self-consumed kWh are valued.
Surplus injected to the grid is NOT valued — the ANRE BT residential
net-billing tariff is unpublished/unconfirmed; including it would be
fabricating income.

Tranche tables for ONEE, Lydec, Redal are provided as module-level
constants, clearly flagged as APPROXIMATIF and subject to revision.
They can be overridden per quote via ``etude_params`` passed to
``calculate_savings_roi``.

All tables are TTC tariffs (the customer pays TTC, so the avoided cost
is the TTC tariff).
"""
from __future__ import annotations

# ── Utility tranche tables ─────────────────────────────────────────────────────
# APPROXIMATIF / À CONFIRMER — tarifs TTC (MAD/kWh, TVA incluse) au 2026.
# Source: barèmes ONEE/distributeurs publiés (résidentiel BT, compteur monophasé).
# Ces constantes sont les SEULS prix de référence ; aucun autre fichier ne doit
# porter de prix kWh en dur. Le vendeur peut les surcharger via etude_params.
#
# Format : liste de (plafond_kWh_mensuel, prix_MAD_kWh_TTC).
# La dernière tranche n'a pas de plafond (None = tranche supérieure).
#
# ONEE (tarif BT résidentiel 2025 — public, officiels ONEE)
ONEE_TRANCHES = [
    (100, 0.9010),    # 0–100 kWh/mois
    (150, 1.0258),    # 101–250 kWh/mois  (tranche 101–150 incluse ici)
    (200, 1.2515),    # 251–400 kWh/mois  (tranche 201–400 incluse ici)
    (None, 1.4017),   # > 400 kWh/mois
]

# Lydec (Casablanca / Grand Casablanca) — APPROXIMATIF, à confirmer avec tarif Lydec
LYDEC_TRANCHES = [
    (100, 0.9500),
    (200, 1.1500),
    (None, 1.4500),
]

# Redal (Rabat / Salé / Kénitra) — APPROXIMATIF, à confirmer avec tarif Redal
REDAL_TRANCHES = [
    (100, 0.9300),
    (200, 1.1200),
    (None, 1.4200),
]

# Mapping distributer name → tranche table (alias-tolerant)
UTILITY_TABLES = {
    "onee": ONEE_TRANCHES,
    "lydec": LYDEC_TRANCHES,
    "redal": REDAL_TRANCHES,
}

# Taux d'autoconsommation par option (estimation documentée, pas de netting)
# Sans batterie : résidentiel marocain typique (pas d'injection valorisée)
AUTOCONSO_SANS = 0.60   # estimation — à affiner avec une étude de consommation
AUTOCONSO_AVEC = 0.85   # avec batterie de stockage — idem

# Prix kWh ONEE de référence (FLAT) — utilisé quand AUCUNE donnée de conso n'est
# disponible. Valeur « raisonnable » de milieu de gamme ONEE ; le résultat est
# présenté comme une ESTIMATION approximative, jamais comme un chiffre précis.
_FALLBACK_KWH_PRICE = 1.20   # MAD/kWh — tranche milieu ONEE (à confirmer)

# Productible annuel de repli (kWh/kWc/an) — GHI moyen Maroc. Défaut historique
# 1240 CONSERVÉ pour byte-identité ; le builder peut le surcharger avec
# CompanyProfile.productible_kwh_kwc (DC2), auquel cas la production annuelle et
# le ROI suivent le repère de la société.
_DEFAULT_PRODUCTIBLE = 1240

# Label affiché quand on dégrade en estimation (pas de données tarifaires)
ESTIMATION_LABEL = "estimation"


def _weighted_kwh_price(kwh_mensuel: float, tranches: list) -> float:
    """Compute a weighted average TTC kWh price given monthly consumption and a
    tariff schedule.

    Uses a progressive-tranche model: each tranche is weighted by the share of
    consumption that falls into it.  When ``kwh_mensuel`` is 0, returns the
    first tranche price (floor).

    Args:
        kwh_mensuel: Monthly kWh consumption.
        tranches:    List of (ceiling_kWh | None, price_MAD_kWh).
                     None ceiling means "no upper bound."

    Returns:
        Weighted average price in MAD/kWh, or first-tranche price if no
        consumption.
    """
    if kwh_mensuel <= 0:
        return tranches[0][1] if tranches else _FALLBACK_KWH_PRICE

    total_cost = 0.0
    remaining = kwh_mensuel
    prev_ceiling = 0.0
    for ceiling, price in tranches:
        if ceiling is None:
            # Dernière tranche : tout le reste
            total_cost += remaining * price
            remaining = 0.0
            break
        tranche_width = ceiling - prev_ceiling
        consumed_in_tranche = min(remaining, tranche_width)
        total_cost += consumed_in_tranche * price
        remaining -= consumed_in_tranche
        prev_ceiling = ceiling
        if remaining <= 0:
            break
    if remaining > 0:
        # Consommation dépasse toutes les tranches définies → dernière tranche
        total_cost += remaining * tranches[-1][1]
    return total_cost / kwh_mensuel


def _avg_kwh_price_from_tranches(
    conso_annuelle_kwh: float | None,
    utility: str | None,
    tranches_override: list | None,
) -> tuple[float, bool]:
    """Return (prix_moyen_MAD_kWh, is_estimated).

    Priority:
      1. Caller-supplied ``tranches_override`` list.
      2. ``utility`` name matched in UTILITY_TABLES.
      3. Fallback flat price (_FALLBACK_KWH_PRICE) — ``is_estimated = True``.

    When annual consumption is available, converts it to monthly average for the
    weighted-tranche calculation.
    """
    if tranches_override:
        table = tranches_override
    elif utility and utility.lower() in UTILITY_TABLES:
        table = UTILITY_TABLES[utility.lower()]
    else:
        # No tariff data → honest fallback
        return _FALLBACK_KWH_PRICE, True

    kwh_mensuel = (conso_annuelle_kwh / 12) if conso_annuelle_kwh else 0.0
    prix = _weighted_kwh_price(kwh_mensuel, table)
    return prix, False


def calculate_savings_roi(
    puissance_kwc: float,
    total_sans: float,
    total_avec: float,
    *,
    conso_annuelle_kwh: float | None = None,
    utility: str | None = None,
    tarif_kwh_override: float | None = None,
    tranches_override: list | None = None,
    autoconso_sans: float = AUTOCONSO_SANS,
    autoconso_avec: float = AUTOCONSO_AVEC,
    productible: float | None = None,
    fallback_tarif_kwh: float | None = None,
) -> dict:
    """Auto-compute annual production, savings and ROI — loi 82-21 model.

    SELF-CONSUMPTION-FIRST (loi 82-21): savings = self-consumed kWh × avoided
    tariff.  Surplus injected to the grid is NOT valued (ANRE BT net-billing
    tariff is unpublished; adding it would fabricate income).

    Tariff resolution order (first wins):
      1. ``tarif_kwh_override`` (explicit flat price — seller sets it)
      2. ``tranches_override`` (caller-supplied schedule)
      3. ``utility`` name → ONEE / Lydec / Redal table
      4. _FALLBACK_KWH_PRICE (flat 1.20 MAD/kWh) — labelled ESTIMATION

    When the fallback fires, the returned dict carries ``savings_estimated=True``
    so callers can label the figure « estimation » and never show it as precise.

    Formulas:
      production_annuelle   = kwc × 1 240 kWh/kWc/an  (GHI moyen Maroc)
      economie_opt1 (sans)  = production × autoconso_sans × prix_kWh
      economie_opt2 (avec)  = production × autoconso_avec × prix_kWh
      roi                   = total_option / economie_annuelle
      monthly               = economie_annuelle × facteur_saisonnier

    Returns a dict directly usable to fill the premium PDF data dict.
    Additional keys vs. the legacy dict:
      ``savings_estimated``   True when tariff data was absent → degrade honestly.
      ``autoconso_sans``      Self-consumption ratio used for option 1.
      ``autoconso_avec``      Self-consumption ratio used for option 2.
      ``tarif_kwh``           Effective kWh price used for the calculation.
      ``utility``             Distributor name resolved (or None).
    """
    # DC2 — productible : repère société (CompanyProfile.productible_kwh_kwc)
    # quand fourni, sinon défaut historique 1240 (byte-identique).
    prod_factor = float(productible) if productible and productible > 0 \
        else _DEFAULT_PRODUCTIBLE
    production_annuelle = round(puissance_kwc * prod_factor)

    # Tariff resolution
    if tarif_kwh_override is not None and tarif_kwh_override > 0:
        prix_kwh = float(tarif_kwh_override)
        savings_estimated = False
    else:
        prix_kwh, savings_estimated = _avg_kwh_price_from_tranches(
            conso_annuelle_kwh, utility, tranches_override)
        # DC2 — quand aucune donnée tarifaire n'existe (repli 1.20 « estimation »),
        # préférer le tarif ONEE de la société (CompanyProfile.onee_tarif_kwh) s'il
        # est fourni. Reste marqué « estimation » (pas de données de conso).
        if savings_estimated and fallback_tarif_kwh and fallback_tarif_kwh > 0:
            prix_kwh = float(fallback_tarif_kwh)

    # Self-consumption-first savings (loi 82-21: only self-consumed kWh valued)
    economie_opt1 = round(production_annuelle * autoconso_sans * prix_kwh)
    economie_opt2 = round(production_annuelle * autoconso_avec * prix_kwh)

    # Retour sur investissement (années)
    roi_opt1 = round(total_sans / economie_opt1, 1) if economie_opt1 > 0 else 0.0
    roi_opt2 = round(total_avec / economie_opt2, 1) if economie_opt2 > 0 else 0.0

    # Répartition mensuelle saisonnière (12 facteurs, somme = 1,000)
    _SF = [0.053, 0.062, 0.083, 0.098, 0.114, 0.116,
           0.116, 0.101, 0.087, 0.070, 0.052, 0.048]
    eco_s_monthly = [round(economie_opt1 * f) for f in _SF]
    eco_a_monthly = [round(economie_opt2 * f) for f in _SF]

    return {
        "prod_kwh":         production_annuelle,
        "eco_s_ann":        economie_opt1,
        "eco_a_ann":        economie_opt2,
        "eco_a_cumul":      economie_opt2,   # même taux utilisé pour la courbe ROI
        "roi_s":            roi_opt1,
        "roi_a":            roi_opt2,
        "eco_s_monthly":    eco_s_monthly,
        "eco_a_monthly":    eco_a_monthly,
        # Metadata for honest rendering
        "savings_estimated": savings_estimated,
        "autoconso_sans":   autoconso_sans,
        "autoconso_avec":   autoconso_avec,
        "tarif_kwh":        prix_kwh,
        "utility":          utility,
    }
