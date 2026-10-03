"""AGR112 — besoin en eau FAO-56 CORRIGÉ, dans le noyau pur ``core.pompage``.

DÉPLACÉ depuis ``apps/ventes/quote_engine/agricole/agronomy.py`` (la règle #4
veut que le moteur de devis ne fasse que RENDRE) ; ce dernier n'est plus qu'un
ré-export pour ``public_views.py`` et le rendu.

Corrections AGR112 :

* OLIVIER = Kc MENSUELS FAO-56 (Table 12, note 24 — Pastor et Orgaz, oliveraie
  méditerranéenne à 60 % de couverture) : 0,50 0,50 0,65 0,60 0,55 0,50 0,45
  0,45 0,55 0,60 0,65 0,50 (https://www.fao.org/4/x0490e/x0490e0b.htm, relu le
  02/10/2026) au lieu d'un Kc constant de 0,65 — la pointe olivier Tadla en
  goutte-à-goutte passait à 59,2 m³/ha/j contre « Olivier 35 » chez l'AMEE.
  PAS 0,70 (écarté, W1-12).
* Culture ABSENTE de ``CROP_STAGES`` ⇒ besoin OMIS + alerte (fin du Kc plat de
  0,85 : « maraichage » du menu n'est pas une culture FAO).
* ``tomate-serre`` ⇒ alerte « ET0 extérieure : surestime sous abri », sans
  facteur inventé.
* Plusieurs parcelles sont SOMMÉES (:func:`besoin_agronomique`).
* La sortie est nommée ``nature: agronomique_plein`` et porte la source de son
  ET0 (``EST.`` tant qu'AGR113 n'a pas sourcé la région).
* Constantes mortes supprimées (``CROP_ANNUAL_M3_HA``, ``KC_MID_DEFAUT``).
* Melon-pastèque 1,00 et efficience gravitaire 0,55 conservés (prudents).
  L'équation 62 (correction climatique du Kc) n'est PAS ajoutée (écartée).

Noyau PUR : stdlib seulement, aucune dépendance Django, aucune I/O ; les tables
sont des tuples / vues en lecture seule (aucune globale mutable).
"""
from __future__ import annotations

import math
from types import MappingProxyType

#: Nature du besoin servi (D-AGR-3 : le besoin FAO n'est que le REPLI, nommé).
NATURE_AGRONOMIQUE = "agronomique_plein"

#: Étiquette d'une valeur estimée (même vocabulaire que la table AGR110).
EST = "EST."


def _num(v) -> float:
    try:
        f = float(v)
        return f if f == f else 0.0  # NaN guard
    except (TypeError, ValueError):
        return 0.0


def _jsround(x, digits=0):
    """Réplique EXACTEMENT le Math.round(x*10^d)/10^d du JS (arrondi half-up) —
    indispensable pour la parité front/back (round() Python est banker's)."""
    f = 10 ** digits
    return math.floor(x * f + 0.5) / f


# Irrigation efficiency by technique (FAO). Gravitaire 0,55 conservé (prudent :
# FAO surface 0,60).
IRRIGATION_EFFICIENCY = MappingProxyType(
    {"goutte": 0.90, "aspersion": 0.75, "gravitaire": 0.55})
IRRIGATION_EFFICIENCY_DEFAUT = 0.75

DAYS_IN_MONTH = (31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31)

# ET0 de référence MENSUEL (mm/jour) par région — Penman-Monteith, stations FAO
# CLIMWAT représentatives. Valeurs ESTIMÉES (station proxy) : statut « EST. »
# jusqu'à AGR113.
ET0_MONTHLY = MappingProxyType({
    "souss-massa":    (2.4, 3.0, 4.0, 4.7, 5.4, 5.9, 6.2, 6.0, 5.0, 4.0, 3.0, 2.3),  # Agadir — EST.
    "doukkala":       (2.2, 2.8, 3.8, 4.5, 5.2, 5.8, 6.3, 6.1, 5.0, 3.9, 2.8, 2.1),  # El Jadida — EST.
    "tadla":          (2.0, 2.9, 4.2, 5.4, 6.6, 7.6, 8.2, 7.7, 5.9, 4.2, 2.8, 2.0),  # Béni Mellal — EST.
    "saiss":          (1.8, 2.5, 3.7, 4.8, 6.0, 7.0, 7.6, 7.1, 5.3, 3.7, 2.4, 1.7),  # Fès-Meknès — EST.
    "oriental":       (2.0, 2.7, 3.9, 5.0, 6.2, 7.1, 7.7, 7.2, 5.5, 3.9, 2.6, 1.9),  # Berkane/Oujda — EST.
    "draa-tafilalet": (2.2, 3.1, 4.5, 5.8, 7.0, 8.0, 8.5, 7.9, 6.2, 4.4, 2.9, 2.1),  # Errachidia — EST.
    "gharb-loukkos":  (2.0, 2.6, 3.6, 4.4, 5.3, 6.0, 6.5, 6.2, 5.0, 3.7, 2.6, 1.9),  # Kénitra/Larache — EST.
    "haouz":          (2.3, 3.1, 4.4, 5.6, 6.8, 7.8, 8.4, 7.8, 6.0, 4.3, 2.9, 2.2),  # Marrakech — EST.
})
ET0_MONTHLY_DEFAUT = (2.1, 2.8, 4.0, 5.0, 6.1, 7.0, 7.6, 7.1, 5.5, 4.0, 2.7, 2.0)  # médiane MA — EST.

# Pluie EFFICACE mensuelle (mm/mois) par région — USDA-SCS simplifiée sur les
# normales pluviométriques MA. Créditée au besoin net. Valeurs ESTIMÉES.
RAIN_EFF_MONTHLY = MappingProxyType({
    "gharb-loukkos":  (60, 55, 50, 40, 20, 5, 0, 0, 10, 40, 60, 65),  # ~405 mm/an eff — EST.
    "saiss":          (45, 42, 45, 40, 22, 6, 1, 1, 10, 30, 48, 50),  # EST.
    "oriental":       (30, 28, 30, 30, 20, 6, 1, 2, 10, 28, 32, 30),  # EST.
    "doukkala":       (35, 30, 28, 18, 8, 1, 0, 0, 5, 20, 35, 40),    # EST.
    "tadla":          (30, 30, 30, 25, 12, 3, 0, 0, 5, 22, 33, 35),   # EST.
    "haouz":          (25, 25, 28, 25, 12, 3, 0, 1, 6, 22, 28, 26),   # EST.
    "souss-massa":    (25, 20, 20, 12, 5, 0, 0, 0, 3, 12, 22, 28),    # EST.
    "draa-tafilalet": (8, 8, 10, 8, 5, 2, 1, 3, 6, 8, 8, 7),          # EST.
})
RAIN_EFF_DEFAUT = (20, 18, 20, 16, 8, 2, 0, 0, 5, 15, 22, 22)  # EST.

#: Source de l'ET0 par région : ``None`` = statut ``EST.`` (aucune station FAO
#: CLIMWAT / DMN lue). AGR113 y pose {station, coordonnees, url, releve_le,
#: methode_pluie} région par région, jamais une valeur devinée.
ET0_SOURCES = MappingProxyType({region: None for region in ET0_MONTHLY})

#: Kc mensuels de l'olivier — FAO-56 Table 12, note 24 (Pastor et Orgaz, 60 %
#: de couverture), https://www.fao.org/4/x0490e/x0490e0b.htm, relu le 02/10/2026.
KC_OLIVIER_MENSUEL = (0.50, 0.50, 0.65, 0.60, 0.55, 0.50,
                      0.45, 0.45, 0.55, 0.60, 0.65, 0.50)


def _spec(**valeurs):
    return MappingProxyType(valeurs)


# Stades culturaux FAO-56 (Table 11 durées / Table 12 Kc), calendrier MA.
# evergreen=True → Kc ~constant ; kc_mensuel → profil mensuel publié. Sinon
# start (mois 1-12), stages en MOIS [ini, dev, mid, late], Kc ini/mid/end.
# kc_estimated=True = hors FAO / estimé.
CROP_STAGES = MappingProxyType({
    "agrumes":   _spec(evergreen=True, kc_mid=0.65),  # FAO-56 T12 citrus (no ground cover)
    "olivier":   _spec(kc_mensuel=KC_OLIVIER_MENSUEL,
                       source="FAO-56 Table 12 note 24 (Pastor et Orgaz)"),
    "dattier":   _spec(evergreen=True, kc_mid=0.95),  # FAO-56 T12 date palm ; MA 51 m³/arbre/an
    "avocatier": _spec(evergreen=True, kc_mid=0.85),  # FAO-56 T12 avocado ; MA Gharb 8-12 000 m³/ha/an
    "arganier":  _spec(evergreen=True, kc_mid=0.55, kc_estimated=True),  # EST.
    "banane-serre": _spec(evergreen=True, kc_mid=1.10),  # FAO-56 T12 banana
    "luzerne":   _spec(evergreen=True, kc_mid=0.95, kc_estimated=True),  # EST. (moyenne inter-coupes)
    "myrtille":  _spec(evergreen=True, kc_mid=1.05, kc_estimated=True),  # EST. ; MA pics ~80 m³/ha/j
    "amandier":  _spec(start=3, stages=(1, 1, 5, 2), kc_ini=0.40, kc_mid=0.90, kc_end=0.65),  # FAO-56 T12 almond
    "vigne":     _spec(start=4, stages=(1, 1, 3, 2), kc_ini=0.30, kc_mid=0.70, kc_end=0.45),  # FAO-56 T12 grape (table)
    "grenadier": _spec(start=3, stages=(1, 2, 4, 2), kc_ini=0.35, kc_mid=0.85, kc_end=0.55, kc_estimated=True),  # EST.
    "figuier":   _spec(start=3, stages=(1, 2, 4, 2), kc_ini=0.35, kc_mid=0.70, kc_end=0.50, kc_estimated=True),  # EST.
    "tomate-serre":  _spec(start=9, stages=(1, 2, 3, 1), kc_ini=0.60, kc_mid=1.10, kc_end=0.80, sous_abri=True),  # FAO-56 T12 tomato
    "poivron-serre": _spec(start=9, stages=(1, 2, 3, 1), kc_ini=0.60, kc_mid=1.05, kc_end=0.90),  # FAO-56 T12 bell pepper
    "pomme-de-terre": _spec(start=1, stages=(1, 1, 2, 1), kc_ini=0.50, kc_mid=1.15, kc_end=0.75),  # FAO-56 T12 potato
    "oignon":    _spec(start=10, stages=(1, 2, 3, 1), kc_ini=0.70, kc_mid=1.05, kc_end=0.75),  # FAO-56 T12 onion (dry)
    "melon-pasteque": _spec(start=3, stages=(1, 1, 2, 1), kc_ini=0.50, kc_mid=1.00, kc_end=0.75),  # FAO-56 T12 melon/watermelon (1,00 prudent)
    "cereales":  _spec(start=11, stages=(1, 2, 2, 1), kc_ini=0.40, kc_mid=1.15, kc_end=0.40),  # FAO-56 T12 wheat
    "fraise":    _spec(start=10, stages=(1, 2, 3, 1), kc_ini=0.40, kc_mid=1.00, kc_end=0.75, kc_estimated=True),  # EST.
    "cannabis":  _spec(start=5, stages=(1, 1, 2, 1), kc_ini=0.40, kc_mid=1.00, kc_end=0.60, kc_estimated=True),  # EST. (cannabis licite, flag ANRAC)
})

# Valeurs Maroc CITÉES (recherche 2026-07-16) — référence de CALAGE, sourcées.
CROP_CITED = MappingProxyType({
    "avocatier": _spec(annual_m3_ha=(8000, 12000), region="gharb-loukkos",
                       source="MA Gharb 8-12 000 m³/ha/an (recherche 2026-07-16)"),
    "myrtille":  _spec(peak_m3_ha_day=80,
                       source="MA pics ~80 m³/ha/j (recherche 2026-07-16)"),
    "dattier":   _spec(m3_per_tree_year=51, trees_per_ha=100,
                       source="MA 51 m³/arbre/an (recherche 2026-07-16)"),
})


def crop_kc_monthly(crop_key):
    """Kc mensuel (0=janv…11=déc) depuis les stades FAO-56, ou ``None`` pour
    une culture ABSENTE de ``CROP_STAGES`` (AGR112 : plus de Kc plat)."""
    spec = CROP_STAGES.get(crop_key)
    if not spec:
        return None
    if spec.get("kc_mensuel"):
        return list(spec["kc_mensuel"])
    if spec.get("evergreen"):
        return [spec["kc_mid"]] * 12
    kc = [0.0] * 12
    start = spec.get("start", 1)
    ini, dev, mid, late = spec.get("stages", (1, 1, 1, 1))
    kc_ini = spec.get("kc_ini", 0.4)
    kc_mid = spec.get("kc_mid", 1.0)
    kc_end = spec.get("kc_end", 0.6)
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


def source_et0(region):
    """La source de l'ET0 d'une région (dict complet) ou ``"EST."``."""
    return ET0_SOURCES.get(region) or EST


def _alerte_culture_absente(crop):
    return {
        "code": "culture_sans_profil",
        "champ": "besoin.culture",
        "message": ("Culture « %s » sans profil Kc FAO-56 : besoin "
                    "agronomique non calculé — saisir le volume d'eau "
                    "déclaré par le client." % (crop or "non renseignée")),
    }


def _alertes_culture(crop):
    spec = CROP_STAGES.get(crop) or {}
    if spec.get("sous_abri"):
        return [{
            "code": "et0_exterieure_sous_abri",
            "champ": "besoin.culture",
            "message": ("ET0 extérieure : surestime le besoin d'une culture "
                        "sous abri (%s)." % crop),
        }]
    return []


def monthly_water_demand(crop=None, region=None, surface_ha=None, method=None):
    """Besoin en eau MENSUEL d'une culture. Défensif : jamais d'exception.

    Culture absente de ``CROP_STAGES`` ⇒ ``None`` (AGR112 : le besoin est
    omis, jamais un Kc plat)."""
    kc = crop_kc_monthly(crop)
    if kc is None:
        return None
    surface = _num(surface_ha)
    et0 = ET0_MONTHLY.get(region, ET0_MONTHLY_DEFAUT)
    rain = RAIN_EFF_MONTHLY.get(region, RAIN_EFF_DEFAUT)
    eff = IRRIGATION_EFFICIENCY.get(method, IRRIGATION_EFFICIENCY_DEFAUT)
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
        "nature": NATURE_AGRONOMIQUE,
        "source_et0": source_et0(region),
        "alertes": _alertes_culture(crop),
        "inputs": {"crop": crop, "region": region, "surface_ha": surface,
                   "method": method, "efficiency": eff},
    }


def besoin_agronomique(parcelles, region=None):
    """AGR112 — besoin agronomique PLEIN de l'exploitation : les parcelles
    (``[{culture, surface_ha, methode}]``) sont SOMMÉES mois par mois.

    Une parcelle sans profil Kc est OMISE avec une alerte qui la nomme ; si
    AUCUNE parcelle n'est calculable, ``m3_jour_mois`` vaut ``None`` (jamais un
    besoin inventé). Rend ``{m3_jour_mois, m3_ha_jour_mois, surface_ha,
    nature, source_et0, alertes, parcelles}`` — ``m3_ha_jour_mois`` = besoin
    par hectare (total ÷ surface calculée), pour les hectares irrigables."""
    alertes = []
    total = None
    surface_calculee = 0.0
    detail = []
    for parcelle in parcelles or ():
        culture = (parcelle.get("culture") or "").strip().lower() or None
        surface = _num(parcelle.get("surface_ha"))
        methode = (parcelle.get("methode") or "").strip().lower() or None
        if surface <= 0:
            alertes.append({
                "code": "surface_manquante", "champ": "besoin.surface_ha",
                "message": "Parcelle « %s » sans surface : besoin non calculé."
                           % (culture or "non renseignée")})
            continue
        res = monthly_water_demand(crop=culture, region=region,
                                   surface_ha=surface, method=methode)
        if res is None:
            alertes.append(_alerte_culture_absente(culture))
            continue
        alertes.extend(res["alertes"])
        serie = res["gross_m3_farm_day"]
        total = (list(serie) if total is None
                 else [a + b for a, b in zip(total, serie)])
        surface_calculee += surface
        detail.append({"culture": culture, "surface_ha": surface,
                       "methode": methode, "m3_jour_mois": list(serie),
                       "kc_estime": res["kc_estimated"]})
    if total is None:
        return {"m3_jour_mois": None, "m3_ha_jour_mois": None,
                "surface_ha": None, "nature": NATURE_AGRONOMIQUE,
                "source_et0": source_et0(region), "alertes": alertes,
                "parcelles": detail}
    return {
        "m3_jour_mois": [round(v, 1) for v in total],
        "m3_ha_jour_mois": [round(v / surface_calculee, 1) for v in total],
        "surface_ha": surface_calculee,
        "nature": NATURE_AGRONOMIQUE,
        "source_et0": source_et0(region),
        "alertes": alertes,
        "parcelles": detail,
    }


def peak_need_m3_day(etude: dict) -> int | None:
    """Besoin de POINTE de l'exploitation (m³/jour) depuis un ``etude``, ou None.

    QJR152 — c'est le MAXIMUM de la série mensuelle ``monthly_water_demand``.
    Un ``besoin_m3j`` explicitement SAISI reste prioritaire (donnée client).
    AGR112 : une culture sans profil Kc ⇒ ``None`` (besoin omis)."""
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
    if res is None:
        return None
    peak = _num(res.get("peak_m3_farm_day"))
    return round(peak) if peak > 0 else None


def annual_water_from_monthly(monthly):
    """Annualisation par INTÉGRALE de la série mensuelle."""
    if not monthly or not isinstance(monthly.get("gross_m3_farm_day"), list):
        return 0
    total = sum(_num(monthly["gross_m3_farm_day"][m]) * d
                for m, d in enumerate(DAYS_IN_MONTH))
    return _jsround(total)
