# flake8: noqa
"""AGRICOLE economics — solar vs butane vs diesel, ROI, FDA subsidy, CO₂.

Pure computation from the built quote ``data`` dict (pump étude + canonical
totals) plus the founder-editable :mod:`constants` (overridable from company
Paramètres). Returns a flat dict of derived figures and the per-month arrays the
charts consume. Never raises — every figure degrades to 0/None on missing data,
mirroring the engine's "never invent a number" rule (a curve-less pump with no
m³/jour simply yields no water/fuel economics, and the money page omits them).
"""
from __future__ import annotations

from . import constants as K


def _num(v, default=0.0):
    try:
        f = float(v)
        return f if f == f else default  # NaN guard
    except (TypeError, ValueError):
        return default


def load_constants(company_id=None) -> dict:
    """Constants with optional company-Paramètres overrides (by company id).

    Reads the module defaults, then layers any company override stored under the
    Paramètres ``agricole_economics`` JSON setting (best-effort; a missing table
    or key leaves the default untouched). Keeps the engine working before the
    Paramètres UI exists (ERP task) — the defaults are flagged « à confirmer ».
    """
    cfg = {
        "cost_per_m3": dict(K.COST_PER_M3),
        "butane_decomp_multiplier": K.BUTANE_DECOMP_MULTIPLIER,
        "butane_12kg_subventionne": K.BUTANE_12KG_SUBVENTIONNE,
        "butane_12kg_reel": K.BUTANE_12KG_REEL,
        "butane_kg_per_h_per_cv": K.BUTANE_KG_PER_H_PER_CV,
        "butane_kg_co2_per_kg": K.BUTANE_KG_CO2_PER_KG,
        "diesel_l_per_h_per_cv": K.DIESEL_L_PER_H_PER_CV,
        "diesel_mad_per_l": K.DIESEL_MAD_PER_L,
        "diesel_kg_co2_per_l": K.DIESEL_KG_CO2_PER_L,
        "pumping_days_per_year": K.PUMPING_DAYS_PER_YEAR,
        "peak_to_avg": K.PEAK_TO_AVG,
        "specific_yield_kwh_kwc": K.SPECIFIC_YIELD_KWH_KWC,
        "fda_subsidy_pct": K.FDA_SUBSIDY_PCT,
        "fda_subsidy_cap": K.FDA_SUBSIDY_CAP,
        "default_current_fuel": K.DEFAULT_CURRENT_FUEL,
    }
    if not company_id:
        return cfg
    try:
        from apps.parametres.models import Parametre  # type: ignore
        raw = Parametre.objects.filter(
            company_id=company_id, cle="agricole_economics").values_list(
            "valeur", flat=True).first()
        if isinstance(raw, dict):
            for k, v in raw.items():
                if k == "cost_per_m3" and isinstance(v, dict):
                    cfg["cost_per_m3"].update(v)
                elif k in cfg:
                    cfg[k] = v
    except Exception:  # noqa: BLE001 — a PDF must never break on settings
        pass
    return cfg


def _monthly(total, weights):
    s = sum(weights) or 1.0
    return [round(total * w / s) for w in weights]


def compute(data: dict, company_id=None) -> dict:
    """Return the agricole derived figures + chart inputs for ``data``."""
    cfg = load_constants(company_id)
    etude = data.get("etude") or {}
    totaux = data.get("totaux_all") or {}

    quote_ttc = _num(totaux.get("ttc")) or _num(data.get("display_total"))
    quote_ht = _num(totaux.get("ht_net"))

    pump_cv = _num(etude.get("pompe_cv"))
    pump_kw = _num(etude.get("pompe_kw"))
    hmt = _num(etude.get("hmt_m"))
    heures = _num(etude.get("heures_pompage")) or 7.0
    m3_jour = _num(etude.get("m3_jour"))
    champ_kwc = _num(etude.get("champ_kwc")) or _num(data.get("puissance_kwc"))

    days = _num(cfg["pumping_days_per_year"], 300) or 300
    peak_to_avg = _num(cfg["peak_to_avg"], 0.62) or 0.62

    # Annual water pumped (only when a real m³/jour exists — never invented).
    annual_m3 = round(m3_jour * peak_to_avg * days) if m3_jour > 0 else 0
    has_water = annual_m3 > 0

    rates = cfg["cost_per_m3"]
    mult = _num(cfg["butane_decomp_multiplier"], 2.5) or 2.5

    # ANNUAL CASH fuel spend the farmer pays today. Solar burns NO fuel — the
    # sun is free — so its annual carburant cost is 0 (the capital is the quote,
    # recovered through payback). The 0,44 MAD/m³ solar figure is a *lifecycle*
    # cost (capex amortised) shown only in the cost-per-m³ comparison below.
    solaire = 0
    butane_today = round(annual_m3 * _num(rates.get("butane"))) if has_water else 0
    butane_future = round(butane_today * mult) if has_water else 0
    diesel = round(annual_m3 * _num(rates.get("diesel"))) if has_water else 0

    current_fuel = (etude.get("current_fuel")
                    or cfg.get("default_current_fuel") or "butane")
    if current_fuel == "diesel":
        annual_fuel_now = diesel
    else:  # butane (default) / none → butane baseline
        annual_fuel_now = butane_today

    # The farmer's REAL current fuel bill (MAD/an), when captured, overrides the
    # modelled cost — savings & payback then reflect what he actually pays today.
    fuel_spend = _num(etude.get("fuel_spend_current"))
    if fuel_spend > 0:
        annual_fuel_now = round(fuel_spend)

    # Savings = the whole fuel bill solar eliminates (solar fuel cost = 0).
    saving_vs_butane = butane_today
    saving_vs_diesel = diesel
    annual_saving = annual_fuel_now or saving_vs_butane
    # Cumulative fuel saved over the system life (panels are warrantied 25 yr;
    # use a conservative 20-yr horizon). A big, tangible anchor for the quote.
    savings_20y = annual_saving * 20

    def _payback(total, saving):
        return round(total / saving, 1) if (total > 0 and saving > 0) else None

    payback_butane = _payback(quote_ttc, saving_vs_butane)
    payback_diesel = _payback(quote_ttc, saving_vs_diesel)
    payback = _payback(quote_ttc, annual_saving)

    # FDA 30% subsidy (capped), on acquisition + installation TTC.
    fda_pct = _num(cfg["fda_subsidy_pct"], 30)
    fda_cap = _num(cfg["fda_subsidy_cap"], 30000)
    fda_amount = min(round(quote_ttc * fda_pct / 100), int(fda_cap)) if quote_ttc > 0 else 0
    net_after_fda = max(0, round(quote_ttc - fda_amount))

    # CO₂ avoided (bottom-up from the current fuel) — a calculation, not a stat.
    if current_fuel == "diesel":
        diesel_l_year = pump_cv * _num(cfg["diesel_l_per_h_per_cv"]) * heures * days
        co2_kg = diesel_l_year * _num(cfg["diesel_kg_co2_per_l"])
        fuel_qty_label = (f"{round(diesel_l_year):,}".replace(",", " ") + " L de gasoil")
    else:
        butane_kg_year = pump_cv * _num(cfg["butane_kg_per_h_per_cv"]) * heures * days
        bottles = butane_kg_year / 12.0
        co2_kg = butane_kg_year * _num(cfg["butane_kg_co2_per_kg"])
        fuel_qty_label = (f"{round(bottles):,}".replace(",", " ")
                          + " bonbonnes de butane")
    co2_t = round(co2_kg / 1000.0, 1) if co2_kg > 0 else 0
    trees = max(0, round(co2_kg / 21.0)) if co2_kg > 0 else 0

    # Annual PV production.
    prod_kwh = round(champ_kwc * _num(cfg["specific_yield_kwh_kwc"])) if champ_kwc > 0 else 0

    # Hectares irrigable (tangibility) — surface if known, else from annual m³.
    surface_ha = _num(etude.get("surface_ha"))
    crop = etude.get("crop")
    if surface_ha > 0:
        hectares = round(surface_ha, 1)
    elif has_water:
        from . import constants as _K
        per_ha = {
            "olivier": 7000, "agrumes": 10000, "maraichage": 6000,
            "luzerne": 12000, "dattier": 18000, "cereales": 5500,
            "arganier": 4000,
        }.get((crop or "").lower(), 8000)
        hectares = round(annual_m3 / per_ha, 1) if per_ha else None
    else:
        hectares = None

    # Peak farm water need (FAO-56) — the sizing target the pump must cover.
    from . import agronomy
    besoin_m3j = agronomy.peak_need_m3_day(etude)

    water_monthly = _monthly(annual_m3, K.WATER_MONTHLY_WEIGHTS) if has_water else [0] * 12
    prod_monthly = _monthly(prod_kwh, K.PROD_MONTHLY_WEIGHTS) if prod_kwh > 0 else [0] * 12

    return {
        "has_water": has_water,
        "annual_m3": annual_m3,
        "prod_kwh_year": prod_kwh,
        "fuel_costs": {
            "solaire": solaire, "butane_today": butane_today,
            "butane_future": butane_future, "diesel": diesel,
        },
        "cost_per_m3": {
            "solaire": _num(rates.get("solaire")),
            "butane": _num(rates.get("butane")),
            "diesel": _num(rates.get("diesel")),
        },
        "current_fuel": current_fuel,
        "annual_fuel_now": annual_fuel_now,
        "annual_saving": annual_saving,
        "savings_20y": savings_20y,
        "saving_vs_butane": saving_vs_butane,
        "saving_vs_diesel": saving_vs_diesel,
        "payback": payback,
        "payback_butane": payback_butane,
        "payback_diesel": payback_diesel,
        "fda_pct": int(fda_pct),
        "fda_amount": fda_amount,
        "fda_cap": int(fda_cap),
        "net_after_fda": net_after_fda,
        "co2_t": co2_t,
        "trees": trees,
        "fuel_qty_label": fuel_qty_label,
        "hectares_irrigable": hectares,
        "besoin_m3j": besoin_m3j,
        "butane_12kg_subventionne": _num(cfg["butane_12kg_subventionne"]),
        "butane_12kg_reel": _num(cfg["butane_12kg_reel"]),
        "quote_ttc": quote_ttc,
        "quote_ht": quote_ht,
        # chart inputs
        "water_monthly": water_monthly,
        "prod_monthly": prod_monthly,
        "quote_total": quote_ttc,
    }
