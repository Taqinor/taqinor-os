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
# QX38 — plafonds CUMULATIFS alignés sur les vraies bandes ONEE (le modèle
# progressif lit ces valeurs comme des seuils cumulés) : 0-100, 101-250,
# 251-400, > 400. Avant QX38 les plafonds (150/200) contredisaient leurs propres
# libellés et écrasaient la bande 101-250 → sous-tarification des foyers 150-400
# kWh/mois typiques. Prix inchangés (publics ONEE) ; seuls les seuils sont
# corrigés. Le miroir JS solar.js ONEE_TRANCHES porte les MÊMES valeurs.
ONEE_TRANCHES = [
    (100, 0.9010),    # 0–100 kWh/mois
    (250, 1.0258),    # 101–250 kWh/mois
    (400, 1.2515),    # 251–400 kWh/mois
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
# QRES54 (fondateur, 2026-07-18) — pertes système : la production BRUTE
# (kWc × productible) est réduite de 14 % (ombrage, température, câblage,
# onduleur, salissure) AVANT tout calcul d'économies — le simulateur du
# fondateur raisonne sur cette production NETTE.
PRODUCTION_DERATE = 0.86

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

# Tables de distributeurs privés ESTIMÉES (à confirmer) — tout calcul qui les
# utilise porte le drapeau « approximatif ». ONEE reste le barème public officiel.
APPROX_UTILITIES = {"lydec", "redal"}


def _resolve_tranches(utility=None, tranches_override=None):
    """Résout la table de tranches applicable.

    Returns:
        (table | None, approximatif: bool)
        ``table`` est None quand AUCUNE donnée tarifaire n'existe (l'appelant
        dégrade alors en estimation honnête). ``approximatif`` est True quand la
        table vient d'un distributeur privé estimé (Lydec/Redal, à confirmer).
    """
    if tranches_override:
        return list(tranches_override), False
    if utility and str(utility).lower() in UTILITY_TABLES:
        key = str(utility).lower()
        return UTILITY_TABLES[key], key in APPROX_UTILITIES
    return None, False


def _monthly_bill_from_kwh(kwh_mensuel: float, tranches: list) -> float:
    """Facture mensuelle TTC (MAD) d'une consommation, valorisée PAR TRANCHE
    (barème progressif). 0 kWh → 0 MAD."""
    if kwh_mensuel is None or kwh_mensuel <= 0:
        return 0.0
    return _weighted_kwh_price(kwh_mensuel, tranches) * kwh_mensuel


def kwh_from_bill(bill_mad, utility=None, tranches_override=None) -> dict:
    """QF1 — Inverse du barème progressif : facture mensuelle (MAD TTC) → kWh/mois.

    Parcourt les tranches en accumulant leur coût jusqu'à retrouver la facture,
    puis interpole linéairement DANS la tranche atteinte (l'inversion exacte du
    modèle progressif de ``_weighted_kwh_price``). Fonction pure, sans I/O.

    Returns dict:
        kwh_mensuel   float — consommation mensuelle estimée (kWh).
        approximatif  bool  — True quand la table utilisée est estimée
                              (Lydec/Redal, à confirmer).
        estimation    bool  — True quand AUCUNE table n'est disponible ou que la
                              facture est vide : le chiffre est une estimation
                              (prix plat de repli), jamais présenté comme précis.
        label         str   — ESTIMATION_LABEL quand ``estimation`` est True,
                              « approximatif » quand seule la table est estimée,
                              '' sinon.
    """
    try:
        bill = float(bill_mad or 0)
    except (TypeError, ValueError):
        bill = 0.0
    if bill <= 0:
        # Facture vide/négative → estimation étiquetée, jamais un chiffre précis.
        return {"kwh_mensuel": 0.0, "approximatif": False,
                "estimation": True, "label": ESTIMATION_LABEL}

    table, approx = _resolve_tranches(utility, tranches_override)
    if table is None:
        # Aucune donnée tarifaire → repli plat, étiqueté « estimation ».
        return {"kwh_mensuel": round(bill / _FALLBACK_KWH_PRICE, 1),
                "approximatif": True, "estimation": True,
                "label": ESTIMATION_LABEL}

    prev_ceiling = 0.0
    cost_so_far = 0.0
    kwh = None
    for ceiling, price in table:
        if ceiling is None:
            kwh = prev_ceiling + (bill - cost_so_far) / price
            break
        tranche_cost = (ceiling - prev_ceiling) * price
        if cost_so_far + tranche_cost >= bill:
            kwh = prev_ceiling + (bill - cost_so_far) / price
            break
        cost_so_far += tranche_cost
        prev_ceiling = ceiling
    if kwh is None:
        # Table sans tranche ouverte (dernier plafond fini) : extrapole au
        # dernier prix connu — comportement cohérent avec _weighted_kwh_price.
        kwh = prev_ceiling + (bill - cost_so_far) / table[-1][1]
    return {"kwh_mensuel": round(kwh, 1), "approximatif": approx,
            "estimation": False, "label": "approximatif" if approx else ""}


def annual_bill_from_kwh(monthly_kwh, utility=None, tranches_override=None) -> dict:
    """QF1 — Facture annuelle TTC (MAD) d'une consommation mensuelle, valorisée
    PAR TRANCHE (barème progressif ONEE/Lydec/Redal). Fonction pure.

    Returns dict:
        bill_mensuel  float — facture mensuelle TTC (MAD).
        bill_annuel   float — facture annuelle TTC (MAD) = mensuelle × 12.
        approximatif  bool  — table estimée (Lydec/Redal, à confirmer).
        estimation    bool  — True quand aucune table n'est disponible (repli
                              plat) ou consommation vide : chiffre étiqueté
                              « estimation », jamais présenté comme précis.
        label         str   — même convention que ``kwh_from_bill``.
    """
    try:
        kwh = float(monthly_kwh or 0)
    except (TypeError, ValueError):
        kwh = 0.0
    if kwh <= 0:
        return {"bill_mensuel": 0.0, "bill_annuel": 0.0,
                "approximatif": False, "estimation": True,
                "label": ESTIMATION_LABEL}

    table, approx = _resolve_tranches(utility, tranches_override)
    if table is None:
        mensuel = kwh * _FALLBACK_KWH_PRICE
        return {"bill_mensuel": round(mensuel, 2),
                "bill_annuel": round(mensuel * 12, 2),
                "approximatif": True, "estimation": True,
                "label": ESTIMATION_LABEL}

    mensuel = _monthly_bill_from_kwh(kwh, table)
    return {"bill_mensuel": round(mensuel, 2),
            "bill_annuel": round(mensuel * 12, 2),
            "approximatif": approx, "estimation": False,
            "label": "approximatif" if approx else ""}


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


def two_bills_savings(
    production_kwh,
    conso_annuelle_kwh,
    autoconso_ratio,
    utility=None,
    tranches_override=None,
) -> dict | None:
    """QF2 — Modèle « deux factures » (économies RÉELLES, par tranche).

    facture annuelle SANS solaire  = consommation valorisée par tranche ;
    facture annuelle AVEC solaire = consommation résiduelle (après les kWh
    autoconsommés) valorisée par tranche ;
    économie = facture_sans − facture_avec.

    Self-consumption-first (loi 82-21) : seuls les kWh autoconsommés réduisent
    la facture — le surplus injecté ne vaut rien (tarif ANRE BT non publié).

    Retourne ``None`` quand il manque une VRAIE donnée (pas de table tarifaire,
    pas de consommation, pas de production) : l'appelant dégrade alors vers
    l'ancienne estimation, étiquetée comme telle. Fonction pure.

    Returns dict:
        facture_sans   int  — facture annuelle TTC sans solaire (MAD).
        facture_avec   int  — facture annuelle TTC avec solaire (MAD).
        economie       int  — facture_sans − facture_avec (≥ 0).
        autoconso_kwh  int  — kWh autoconsommés retenus (plafonnés à la conso).
        approximatif   bool — table distributeur estimée (Lydec/Redal).
    """
    table, approx = _resolve_tranches(utility, tranches_override)
    if table is None:
        return None
    try:
        conso = float(conso_annuelle_kwh or 0)
        prod = float(production_kwh or 0)
        ratio = float(autoconso_ratio or 0)
    except (TypeError, ValueError):
        return None
    if conso <= 0 or prod <= 0 or ratio <= 0:
        return None

    facture_sans = round(_monthly_bill_from_kwh(conso / 12, table) * 12)
    autoconso_kwh = min(prod * ratio, conso)
    residuel = max(0.0, conso - autoconso_kwh)
    facture_avec = round(_monthly_bill_from_kwh(residuel / 12, table) * 12)
    # Économie dérivée des factures ARRONDIES : la chaîne affichée
    # facture_sans − facture_avec = économie est exacte au dirham.
    return {
        "facture_sans": facture_sans,
        "facture_avec": facture_avec,
        "economie": max(0, facture_sans - facture_avec),
        "autoconso_kwh": round(autoconso_kwh),
        "approximatif": approx,
    }


# ── QX39 — hypothèses du cashflow 25 ans (source unique, miroir solar.js) ─────
# Documentées et rendues sur le PDF/la proposition ; jamais un chiffre inventé.
CASHFLOW_YEARS = 25
PANEL_DEGRADATION = 0.005        # 0,5 %/an — perte de production annuelle
# QRES54 (fondateur, 2026-07-18) — AUCUNE hausse tarifaire supposée : la
# projection est à tarif constant (la légende du graphe le dit — le modèle
# doit le FAIRE ; l'ancien +2 %/an la contredisait). Seule la dégradation
# panneau (0,5 %/an) érode les économies. Toute hausse réelle du tarif ne
# peut qu'améliorer le résultat.
TARIFF_ESCALATION = 0.0
BATTERY_ROUNDTRIP = 0.90         # rendement aller-retour batterie (option 2)
INVERTER_REPLACE_YEAR = 12       # remplacement onduleur (année) — optionnel
INVERTER_REPLACE_FRACTION = 0.08  # coût ≈ 8 % de l'investissement, à l'année ci-dessus


def compute_cashflow_payback(
    investment: float,
    economie_annee1: float,
    *,
    battery: bool = False,
    years: int = CASHFLOW_YEARS,
    degradation: float = PANEL_DEGRADATION,
    escalation: float = TARIFF_ESCALATION,
    battery_roundtrip: float = BATTERY_ROUNDTRIP,
    inverter_replace_year: int | None = INVERTER_REPLACE_YEAR,
    inverter_replace_fraction: float = INVERTER_REPLACE_FRACTION,
) -> dict:
    """QX39 — cashflow 25 ans honnête + payback par croisement du cumul à zéro.

    Chaque année : l'économie de base (année 1) est érodée par la dégradation
    panneau (0,5 %/an) MAIS améliorée par l'escalade tarifaire documentée ; la
    batterie (option 2) applique son rendement aller-retour. Un remplacement
    onduleur optionnel retranche une fraction de l'investissement l'année dite.
    Le payback = première année où le cumul devient ≥ 0 (interpolé dans l'année).
    Renvoie le cashflow annuel, le cumul, le payback (années) et le gain net.
    """
    inv = float(investment or 0)
    base = float(economie_annee1 or 0)
    if base <= 0 or inv <= 0:
        return {
            "payback_years": 0.0, "cashflow": [], "cumulative": [],
            "net_gain": 0.0, "years": years,
        }

    cashflow, cumulative = [], []
    cumul = -inv
    payback = None
    prev_cumul = -inv
    for y in range(1, years + 1):
        prod_factor = (1 - degradation) ** (y - 1)      # dégradation panneau
        tarif_factor = (1 + escalation) ** (y - 1)      # escalade tarifaire
        year_saving = base * prod_factor * tarif_factor
        if battery:
            year_saving *= battery_roundtrip
        year_cf = year_saving
        if inverter_replace_year and y == inverter_replace_year:
            year_cf -= inv * inverter_replace_fraction
        cashflow.append(round(year_cf))
        prev_cumul = cumul
        cumul += year_cf
        cumulative.append(round(cumul))
        # Croisement à zéro → payback interpolé dans l'année.
        if payback is None and cumul >= 0:
            span = cumul - prev_cumul
            frac = (0 - prev_cumul) / span if span else 0.0
            payback = round((y - 1) + frac, 1)

    if payback is None:
        payback = float(years)  # jamais rentabilisé sur l'horizon
    return {
        "payback_years": payback,
        "cashflow": cashflow,
        "cumulative": cumulative,
        "net_gain": round(cumul),
        "years": years,
    }


def _fr_pct(v) -> str:
    """0.5 -> '0,5' ; 2.0 -> '2' (French decimal comma, no trailing zero)."""
    s = f"{float(v):g}"
    return s.replace(".", ",")


def cashflow_assumptions() -> dict:
    """QX39 — hypothèses documentées du cashflow, rendues sur le PDF/la
    proposition (autoconsommation d'abord ; rachat BT surplus toujours non
    publié ; plafond d'injection 20 % pré-intégré via l'autoconso).

    QRES1 — chaque idée tient en UNE note (la loi 82-21 et le plafond
    d'injection fusionnés ; plus de « performance garantie 25 ans » redondant
    avec les garanties produit) et les pourcentages s'écrivent à la française
    (« 0,5 %/an », jamais « 0.5 »)."""
    return {
        "years": CASHFLOW_YEARS,
        "degradation_pct": round(PANEL_DEGRADATION * 100, 2),
        "escalation_pct": round(TARIFF_ESCALATION * 100, 1),
        "battery_roundtrip_pct": round(BATTERY_ROUNDTRIP * 100),
        "inverter_replace_year": INVERTER_REPLACE_YEAR,
        "notes": [
            "Loi 82-21 : seuls les kWh autoconsommés réduisent la facture — "
            "le surplus injecté n'est pas rémunéré (plafond d'injection 20 % "
            "intégré).",
            f"Dégradation panneau {_fr_pct(round(PANEL_DEGRADATION * 100, 2))} "
            "%/an intégrée ; aucune hausse du tarif électrique supposée — "
            "projection à tarif constant, toute hausse réelle améliore votre "
            "résultat.",
        ],
    }


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
    # QRES54 — pertes système de 14 % déduites de la production brute
    # (PRODUCTION_DERATE) : toute la chaîne (économies, factures par tranches,
    # couverture, cashflow) raisonne sur la production NETTE.
    prod_factor = float(productible) if productible and productible > 0 \
        else _DEFAULT_PRODUCTIBLE
    production_annuelle = round(
        puissance_kwc * prod_factor * PRODUCTION_DERATE)

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

    # QF2 — modèle « deux factures » (réel, par tranche) : quand une VRAIE
    # consommation ET une table tarifaire existent (et qu'aucun prix plat
    # vendeur ne force l'ancien modèle), l'économie devient
    # facture_sans − facture_avec, les deux factures valorisées PAR TRANCHE.
    # Sinon : ancienne approximation production × autoconso × prix, étiquetée
    # « estimation » — aucun chiffre inventé.
    savings_model = "estimation"
    facture_sans = facture_avec_s = facture_avec_a = None
    factures_approximatif = False
    if not (tarif_kwh_override is not None and tarif_kwh_override > 0):
        _tb_s = two_bills_savings(
            production_annuelle, conso_annuelle_kwh, autoconso_sans,
            utility=utility, tranches_override=tranches_override)
        _tb_a = two_bills_savings(
            production_annuelle, conso_annuelle_kwh, autoconso_avec,
            utility=utility, tranches_override=tranches_override)
        if _tb_s and _tb_a:
            savings_model = "factures"
            economie_opt1 = _tb_s["economie"]
            economie_opt2 = _tb_a["economie"]
            facture_sans = _tb_s["facture_sans"]
            facture_avec_s = _tb_s["facture_avec"]
            facture_avec_a = _tb_a["facture_avec"]
            factures_approximatif = _tb_s["approximatif"]

    # ── QX39 — retour sur investissement par CASHFLOW 25 ans (honnête) ────────
    # Le payback n'est plus un simple ratio année-1 (ni conservateur, ni
    # optimiste) : on cumule le cashflow réel avec dégradation panneau 0,5 %/an,
    # une hypothèse DOCUMENTÉE d'escalade tarifaire, le rendement aller-retour
    # de la batterie (option 2), et un remplacement onduleur optionnel. Le
    # payback = première année où le cumul devient positif (interpolée). Repli
    # sûr sur le ratio année-1 quand l'économie est nulle.
    cf_s = compute_cashflow_payback(total_sans, economie_opt1)
    cf_a = compute_cashflow_payback(
        total_avec, economie_opt2, battery=True)
    roi_opt1 = cf_s["payback_years"] if economie_opt1 > 0 else 0.0
    roi_opt2 = cf_a["payback_years"] if economie_opt2 > 0 else 0.0

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
        # QF2 — modèle « deux factures » : 'factures' quand l'économie vient de
        # facture_sans − facture_avec (par tranche), 'estimation' sinon.
        "savings_model":    savings_model,
        "facture_sans":     facture_sans,
        "facture_avec_s":   facture_avec_s,
        "facture_avec_a":   facture_avec_a,
        "factures_approximatif": factures_approximatif,
        # QK4 — productible réellement utilisé (kWh/kWc/an), pour transparence.
        "productible":      prod_factor,
        # QX39 — cashflow 25 ans honnête (dégradation/escalade/batterie/onduleur)
        # + hypothèses documentées, rendus sur le PDF/la proposition.
        "cashflow_sans":    cf_s["cumulative"],
        "cashflow_avec":    cf_a["cumulative"],
        "net_gain_sans":    cf_s["net_gain"],
        "net_gain_avec":    cf_a["net_gain"],
        "cashflow_assumptions": cashflow_assumptions(),
    }
