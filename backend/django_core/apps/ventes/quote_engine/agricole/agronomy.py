# flake8: noqa
"""AGRICOLE agronomy — FAO-56 crop water need (server-side, UN SEUL moteur).

QJR152 — ce module ne porte plus qu'UN moteur agronomique : la série MENSUELLE
FAO-56 (``monthly_water_demand``, QX48, miroir de
``frontend/src/features/ventes/agronomy.js``). Le besoin de POINTE
(``peak_need_m3_day``) en est simplement le maximum mensuel.

POURQUOI. Un second moteur « mois de pointe » (``water_demand_from_farm``,
``KC_MID``, ``ET0_PEAK_MM_J``) coexistait ici : il prenait un ET0 de pointe
estival (7,5 mm/j en Souss-Massa) et ne créditait AUCUNE pluie, là où le moteur
mensuel prend l'ET0 de juillet (6,2) ET crédite la pluie efficace. Sur le
fixture agrumes/Souss-Massa/2 ha/goutte, la page 2 imprimait « au-dessus de
votre besoin de pointe de 108 m³/jour » juste au-dessus d'un graphe dont la plus
haute barre valait ≈ 90 : DEUX besoins de pointe sur la même page. Le v1 est
supprimé ; ses constantes propres (Kc de pointe, ET0 de pointe, abreuvement du
cheptel) partent avec lui. L'abreuvement du cheptel n'était alimenté par aucun
write-path (aucun devis ne porte ``etude.livestock``).

Pur + défensif — ne lève jamais ; rend ``None`` quand la surface manque (on
n'invente jamais un besoin). Les constantes du moteur mensuel restent à tenir en
phase avec ``agronomy.js`` (test de parité ``test_qx48_agronomy_v2``).
"""
from __future__ import annotations

# Kc moyen prudent — culture inconnue (moteur mensuel, cf. crop_kc_monthly).
KC_MID_DEFAUT = 0.85

# Irrigation efficiency by technique (FAO).
IRRIGATION_EFFICIENCY = {"goutte": 0.90, "aspersion": 0.75, "gravitaire": 0.55}
IRRIGATION_EFFICIENCY_DEFAUT = 0.75

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


def peak_need_m3_day(etude: dict) -> int | None:
    """Besoin de POINTE de l'exploitation (m³/jour) depuis un ``etude``, ou None.

    QJR152 — c'est le MAXIMUM de la série mensuelle ``monthly_water_demand``
    (moteur unique), donc exactement la plus haute barre du graphe « besoin de
    la culture vs eau livrée » de la page 2. Un ``besoin_m3j`` explicitement
    SAISI (questionnaire web / surcharge) reste prioritaire : c'est une donnée
    du client, pas un second moteur.
    """
    etude = etude or {}
    explicit = etude.get("besoin_m3j")
    if explicit not in (None, "", 0):
        n = _num(explicit)
        return round(n) if n > 0 else None
    surface = _num(etude.get("surface_ha"))
    if surface <= 0:                     # sans surface, aucun besoin n'est dérivable
        return None
    res = monthly_water_demand(
        crop=(etude.get("crop") or "").strip().lower() or None,
        region=(etude.get("region") or "").strip().lower() or None,
        surface_ha=surface,
        method=(etude.get("irrigation_method") or "").strip().lower() or None,
    )
    peak = _num(res.get("peak_m3_farm_day"))
    return round(peak) if peak > 0 else None


# ═══════════════════════════════════════════════════════════════════════════
# QX48 — Moteur agronomique v2 (FAO-56 réel, série MENSUELLE) — MIROIR de
# frontend/src/features/ventes/agronomy.js. Tout changement ici DOIT être
# répliqué là-bas (test de parité). Le v1 ci-dessus (mois de pointe) reste tel
# quel. CHAQUE constante porte sa source ; « EST. » = estimé (à vérifier).
# Mois indexé 0 = janvier … 11 = décembre.
# ═══════════════════════════════════════════════════════════════════════════
import math  # noqa: E402


def _jsround(x, digits=0):
    """Réplique EXACTEMENT le Math.round(x*10^d)/10^d du JS (arrondi half-up) —
    indispensable pour la parité front/back (round() Python est banker's)."""
    f = 10 ** digits
    return math.floor(x * f + 0.5) / f


DAYS_IN_MONTH = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]

# ET0 de référence MENSUEL (mm/jour) par région — Penman-Monteith, stations FAO
# CLIMWAT représentatives. Valeurs ESTIMÉES (station proxy), à vérifier fondateur.
ET0_MONTHLY = {
    "souss-massa":    [2.4, 3.0, 4.0, 4.7, 5.4, 5.9, 6.2, 6.0, 5.0, 4.0, 3.0, 2.3],  # Agadir — EST.
    "doukkala":       [2.2, 2.8, 3.8, 4.5, 5.2, 5.8, 6.3, 6.1, 5.0, 3.9, 2.8, 2.1],  # El Jadida — EST.
    "tadla":          [2.0, 2.9, 4.2, 5.4, 6.6, 7.6, 8.2, 7.7, 5.9, 4.2, 2.8, 2.0],  # Béni Mellal — EST.
    "saiss":          [1.8, 2.5, 3.7, 4.8, 6.0, 7.0, 7.6, 7.1, 5.3, 3.7, 2.4, 1.7],  # Fès-Meknès — EST.
    "oriental":       [2.0, 2.7, 3.9, 5.0, 6.2, 7.1, 7.7, 7.2, 5.5, 3.9, 2.6, 1.9],  # Berkane/Oujda — EST.
    "draa-tafilalet": [2.2, 3.1, 4.5, 5.8, 7.0, 8.0, 8.5, 7.9, 6.2, 4.4, 2.9, 2.1],  # Errachidia — EST.
    "gharb-loukkos":  [2.0, 2.6, 3.6, 4.4, 5.3, 6.0, 6.5, 6.2, 5.0, 3.7, 2.6, 1.9],  # Kénitra/Larache — EST.
    "haouz":          [2.3, 3.1, 4.4, 5.6, 6.8, 7.8, 8.4, 7.8, 6.0, 4.3, 2.9, 2.2],  # Marrakech — EST.
}
ET0_MONTHLY_DEFAUT = [2.1, 2.8, 4.0, 5.0, 6.1, 7.0, 7.6, 7.1, 5.5, 4.0, 2.7, 2.0]  # médiane MA — EST.

# Pluie EFFICACE mensuelle (mm/mois) par région — USDA-SCS simplifiée sur les
# normales pluviométriques MA. Créditée au besoin net. Valeurs ESTIMÉES.
RAIN_EFF_MONTHLY = {
    "gharb-loukkos":  [60, 55, 50, 40, 20, 5, 0, 0, 10, 40, 60, 65],  # ~405 mm/an eff — EST.
    "saiss":          [45, 42, 45, 40, 22, 6, 1, 1, 10, 30, 48, 50],  # EST.
    "oriental":       [30, 28, 30, 30, 20, 6, 1, 2, 10, 28, 32, 30],  # EST.
    "doukkala":       [35, 30, 28, 18, 8, 1, 0, 0, 5, 20, 35, 40],    # EST.
    "tadla":          [30, 30, 30, 25, 12, 3, 0, 0, 5, 22, 33, 35],   # EST.
    "haouz":          [25, 25, 28, 25, 12, 3, 0, 1, 6, 22, 28, 26],   # EST.
    "souss-massa":    [25, 20, 20, 12, 5, 0, 0, 0, 3, 12, 22, 28],    # EST.
    "draa-tafilalet": [8, 8, 10, 8, 5, 2, 1, 3, 6, 8, 8, 7],          # EST.
}
RAIN_EFF_DEFAUT = [20, 18, 20, 16, 8, 2, 0, 0, 5, 15, 22, 22]  # EST.

# Stades culturaux FAO-56 (Table 11 durées / Table 12 Kc), calendrier MA.
# evergreen=True → Kc ~constant. Sinon start (mois 1-12), stages en MOIS
# [ini, dev, mid, late], Kc ini/mid/end. kc_estimated=True = hors FAO / estimé.
CROP_STAGES = {
    "agrumes":   {"evergreen": True, "kc_mid": 0.65},  # FAO-56 T12 citrus (no ground cover)
    "olivier":   {"evergreen": True, "kc_mid": 0.65},  # FAO-56 T12 olive
    "dattier":   {"evergreen": True, "kc_mid": 0.95},  # FAO-56 T12 date palm ; MA 51 m³/arbre/an
    "avocatier": {"evergreen": True, "kc_mid": 0.85},  # FAO-56 T12 avocado ; MA Gharb 8-12 000 m³/ha/an
    "arganier":  {"evergreen": True, "kc_mid": 0.55, "kc_estimated": True},  # EST.
    "banane-serre": {"evergreen": True, "kc_mid": 1.10},  # FAO-56 T12 banana
    "luzerne":   {"evergreen": True, "kc_mid": 0.95, "kc_estimated": True},  # EST. (moyenne inter-coupes)
    "myrtille":  {"evergreen": True, "kc_mid": 1.05, "kc_estimated": True},  # EST. ; MA pics ~80 m³/ha/j
    "amandier":  {"start": 3, "stages": [1, 1, 5, 2], "kc_ini": 0.40, "kc_mid": 0.90, "kc_end": 0.65},  # FAO-56 T12 almond
    "vigne":     {"start": 4, "stages": [1, 1, 3, 2], "kc_ini": 0.30, "kc_mid": 0.70, "kc_end": 0.45},  # FAO-56 T12 grape (table)
    "grenadier": {"start": 3, "stages": [1, 2, 4, 2], "kc_ini": 0.35, "kc_mid": 0.85, "kc_end": 0.55, "kc_estimated": True},  # EST.
    "figuier":   {"start": 3, "stages": [1, 2, 4, 2], "kc_ini": 0.35, "kc_mid": 0.70, "kc_end": 0.50, "kc_estimated": True},  # EST.
    "tomate-serre":  {"start": 9, "stages": [1, 2, 3, 1], "kc_ini": 0.60, "kc_mid": 1.10, "kc_end": 0.80},  # FAO-56 T12 tomato
    "poivron-serre": {"start": 9, "stages": [1, 2, 3, 1], "kc_ini": 0.60, "kc_mid": 1.05, "kc_end": 0.90},  # FAO-56 T12 bell pepper
    "pomme-de-terre": {"start": 1, "stages": [1, 1, 2, 1], "kc_ini": 0.50, "kc_mid": 1.15, "kc_end": 0.75},  # FAO-56 T12 potato
    "oignon":    {"start": 10, "stages": [1, 2, 3, 1], "kc_ini": 0.70, "kc_mid": 1.05, "kc_end": 0.75},  # FAO-56 T12 onion (dry)
    "melon-pasteque": {"start": 3, "stages": [1, 1, 2, 1], "kc_ini": 0.50, "kc_mid": 1.00, "kc_end": 0.75},  # FAO-56 T12 melon/watermelon
    "cereales":  {"start": 11, "stages": [1, 2, 2, 1], "kc_ini": 0.40, "kc_mid": 1.15, "kc_end": 0.40},  # FAO-56 T12 wheat
    "fraise":    {"start": 10, "stages": [1, 2, 3, 1], "kc_ini": 0.40, "kc_mid": 1.00, "kc_end": 0.75, "kc_estimated": True},  # EST.
    "cannabis":  {"start": 5, "stages": [1, 1, 2, 1], "kc_ini": 0.40, "kc_mid": 1.00, "kc_end": 0.60, "kc_estimated": True},  # EST. (cannabis licite, flag ANRAC)
}

# Valeurs Maroc CITÉES (recherche 2026-07-16) — référence de CALAGE, sourcées.
CROP_CITED = {
    "avocatier": {"annual_m3_ha": [8000, 12000], "region": "gharb-loukkos",
                  "source": "MA Gharb 8-12 000 m³/ha/an (recherche 2026-07-16)"},
    "myrtille":  {"peak_m3_ha_day": 80,
                  "source": "MA pics ~80 m³/ha/j (recherche 2026-07-16)"},
    "dattier":   {"m3_per_tree_year": 51, "trees_per_ha": 100,
                  "source": "MA 51 m³/arbre/an (recherche 2026-07-16)"},
}


def crop_kc_monthly(crop_key):
    """Kc mensuel (0=janv…11=déc) depuis les stades FAO-56. Miroir de
    cropKcMonthly(). Culture inconnue → KC_MID_DEFAUT plat ; évergreen → constant."""
    kc = [0.0] * 12
    spec = CROP_STAGES.get(crop_key)
    if not spec:
        return [KC_MID_DEFAUT] * 12
    if spec.get("evergreen"):
        return [spec["kc_mid"]] * 12
    start = spec.get("start", 1)
    stages = spec.get("stages", [1, 1, 1, 1])
    kc_ini = spec.get("kc_ini", 0.4)
    kc_mid = spec.get("kc_mid", 1.0)
    kc_end = spec.get("kc_end", 0.6)
    ini, dev, mid, late = stages
    m = (start - 1) % 12

    def put(v):
        nonlocal m
        kc[m] = _jsround(v, 3)
        m = (m + 1) % 12

    for _ in range(ini):
        put(kc_ini)
    for i in range(dev):
        put(kc_ini + (kc_mid - kc_ini) * ((i + 1) / (dev + 1)))
    for _ in range(mid):
        put(kc_mid)
    for i in range(late):
        put(kc_mid + (kc_end - kc_mid) * ((i + 1) / (late + 1)))
    return kc


def monthly_water_demand(crop=None, region=None, surface_ha=None, method=None):
    """Besoin en eau MENSUEL d'une culture (le graphe QX47). Miroir strict de
    monthlyWaterDemand(). Défensif : jamais d'exception."""
    surface = _num(surface_ha)
    et0 = ET0_MONTHLY.get(region, ET0_MONTHLY_DEFAUT)
    rain = RAIN_EFF_MONTHLY.get(region, RAIN_EFF_DEFAUT)
    eff = IRRIGATION_EFFICIENCY.get(method, IRRIGATION_EFFICIENCY_DEFAUT)
    kc = crop_kc_monthly(crop)
    etc_mm_day, crop_need_mm_month, net_mm_month = [], [], []
    gross_m3_ha_month, gross_m3_farm_day = [], []
    for m in range(12):
        etc = et0[m] * kc[m]
        gross_mm = etc * DAYS_IN_MONTH[m]
        net_mm = max(0.0, gross_mm - rain[m])
        gross_ha = (net_mm * 10) / eff if eff > 0 else 0.0
        etc_mm_day.append(_jsround(etc, 3))
        crop_need_mm_month.append(_jsround(gross_mm, 1))
        net_mm_month.append(_jsround(net_mm, 1))
        gross_m3_ha_month.append(_jsround(gross_ha, 1))
        gross_m3_farm_day.append(
            _jsround(gross_ha * surface / DAYS_IN_MONTH[m], 1) if surface > 0 else 0)
    annual_net_m3_ha = _jsround(sum(net_mm_month) * 10)
    annual_gross_m3_ha = _jsround(sum(gross_m3_ha_month))
    annual_gross_m3_farm = _jsround(annual_gross_m3_ha * surface) if surface > 0 else 0
    peak_m3_ha_day = _jsround(
        max(v / DAYS_IN_MONTH[m] for m, v in enumerate(gross_m3_ha_month)), 1)
    peak_m3_farm_day = _jsround(max([0] + gross_m3_farm_day), 1)
    return {
        "kc": kc, "etc_mm_day": etc_mm_day,
        "crop_need_mm_month": crop_need_mm_month, "net_mm_month": net_mm_month,
        "gross_m3_ha_month": gross_m3_ha_month, "gross_m3_farm_day": gross_m3_farm_day,
        "annual_net_m3_ha": annual_net_m3_ha, "annual_gross_m3_ha": annual_gross_m3_ha,
        "annual_gross_m3_farm": annual_gross_m3_farm,
        "peak_m3_ha_day": peak_m3_ha_day, "peak_m3_farm_day": peak_m3_farm_day,
        "kc_estimated": bool(CROP_STAGES.get(crop, {}).get("kc_estimated")),
        "inputs": {"crop": crop, "region": region, "surface_ha": surface,
                   "method": method, "efficiency": eff},
    }


def annual_water_from_monthly(monthly):
    """(e) Annualisation par INTÉGRALE de la série mensuelle. Miroir de
    annualWaterFromMonthly() — remplace le forfait plat sur le chemin agricole v2."""
    if not monthly or not isinstance(monthly.get("gross_m3_farm_day"), list):
        return 0
    total = sum(_num(monthly["gross_m3_farm_day"][m]) * d
                for m, d in enumerate(DAYS_IN_MONTH))
    return _jsround(total)


def date_palm_cited_per_tree():
    """Volume annuel CITÉ par arbre (dattier) — valeur MA de référence."""
    return CROP_CITED["dattier"]["m3_per_tree_year"]
