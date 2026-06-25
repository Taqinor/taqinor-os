# flake8: noqa
"""AGRICOLE agronomy — FAO-56 peak crop water need (server-side port).

Faithful port of ``frontend/src/features/ventes/agronomy.js`` so the premium PDF
can state the farm's REAL peak water need (m³/jour) without depending on the
frontend. Method: ETc = ET0_peak × Kc (mid-season), 1 mm over 1 ha = 10 m³, gross
pumped volume = net ÷ irrigation efficiency, plus livestock drinking water.

Pure + defensive — never raises; returns ``None`` only when neither a positive
surface nor any livestock is given (we never invent a need). Keep the constants
in sync with agronomy.js. Per the 2026 research base they are FAO-matched, EXCEPT
``arganier`` (0.55, no FAO entry) and ``luzerne`` (0.95, season-average not the
instantaneous peak) — both are ENGINEERING ESTIMATES, flagged here and labelled
as such on the PDF.
"""
from __future__ import annotations

# Kc mid-season (FAO-56, Morocco). FAO-matched except arganier/luzerne (estimates).
KC_MID = {
    "olivier": 0.70, "agrumes": 0.65, "maraichage": 1.05, "luzerne": 0.95,
    "dattier": 0.95, "cereales": 1.15, "arganier": 0.55,
}
KC_MID_DEFAUT = 0.85
# Crop coefficients that are engineering estimates, NOT FAO-certified.
KC_ESTIMATED = {"arganier", "luzerne"}

# Peak summer ET0 (mm/day) by Moroccan agricultural region.
ET0_PEAK_MM_J = {
    "souss-massa": 7.5, "doukkala": 7.0, "tadla": 8.0, "saiss": 7.0,
    "oriental": 7.5, "draa-tafilalet": 8.0,
}
ET0_PEAK_DEFAUT = 7.5

# Irrigation efficiency by technique (FAO).
IRRIGATION_EFFICIENCY = {"goutte": 0.90, "aspersion": 0.75, "gravitaire": 0.55}
IRRIGATION_EFFICIENCY_DEFAUT = 0.75

# Livestock drinking water (L/head/day, peak heat).
LIVESTOCK_L_PER_DAY = {
    "vache_laitiere": 150, "bovin": 55, "mouton": 12, "chevre": 10, "volaille": 0.35,
}

# Typical gross annual consumption (m³/ha/yr) — for the inverse ha-from-volume calc.
CROP_ANNUAL_M3_HA = {
    "olivier": 7000, "agrumes": 10000, "maraichage": 6000, "luzerne": 12000,
    "dattier": 18000, "cereales": 5500, "arganier": 4000,
}
CROP_ANNUAL_M3_HA_DEFAUT = 8000


def _num(v) -> float:
    try:
        f = float(v)
        return f if f == f else 0.0  # NaN guard
    except (TypeError, ValueError):
        return 0.0


def water_demand_from_farm(crop=None, region=None, surface_ha=None, method=None,
                           trees=None, livestock=None) -> dict | None:
    """Peak-month farm water need. Mirrors agronomy.js waterDemandFromFarm()."""
    surface = _num(surface_ha)
    livestock = livestock if isinstance(livestock, dict) else {}

    livestock_m3 = 0.0
    for key, count in livestock.items():
        per_head = LIVESTOCK_L_PER_DAY.get(key)
        if not per_head or per_head <= 0:
            continue
        c = _num(count)
        if c > 0:
            livestock_m3 += c * per_head / 1000.0

    if not (surface > 0) and livestock_m3 <= 0:
        return None

    et0 = ET0_PEAK_MM_J.get(region, ET0_PEAK_DEFAUT)
    kc = KC_MID.get(crop, KC_MID_DEFAUT)
    etc_peak_mm = et0 * kc
    net_m3_ha_day = etc_peak_mm * 10.0
    eff = IRRIGATION_EFFICIENCY.get(method, IRRIGATION_EFFICIENCY_DEFAUT)
    gross_m3_ha_day = net_m3_ha_day / eff if eff > 0 else 0.0
    crop_m3_day = gross_m3_ha_day * (surface if surface > 0 else 0.0)
    m3_day_peak = round(crop_m3_day + livestock_m3)

    return {
        "etc_peak_mm": round(etc_peak_mm, 3),
        "net_m3_ha_day": round(net_m3_ha_day, 2),
        "gross_m3_ha_day": round(gross_m3_ha_day, 2),
        "crop_m3_day": round(crop_m3_day, 2),
        "livestock_m3_day": round(livestock_m3, 2),
        "m3_day_peak": m3_day_peak,
        "kc": kc,
        "kc_estimated": crop in KC_ESTIMATED,
        "et0_peak": et0,
        "efficiency": eff,
    }


def peak_need_m3_day(etude: dict) -> int | None:
    """Convenience: peak farm water need (m³/jour) from an ``etude`` dict, or None.

    Prefers an explicit ``besoin_m3j`` (e.g. computed/overridden on the frontend);
    otherwise derives it from crop/region/surface/method/livestock.
    """
    etude = etude or {}
    explicit = etude.get("besoin_m3j")
    if explicit not in (None, "", 0):
        n = _num(explicit)
        return round(n) if n > 0 else None
    res = water_demand_from_farm(
        crop=(etude.get("crop") or "").strip().lower() or None,
        region=(etude.get("region") or "").strip().lower() or None,
        surface_ha=etude.get("surface_ha"),
        method=(etude.get("irrigation_method") or "").strip().lower() or None,
        trees=etude.get("trees"),
        livestock=etude.get("livestock"),
    )
    if not res:
        return None
    return res["m3_day_peak"] or None
