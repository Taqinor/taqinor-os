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

    On top of that legacy JSON override, the two butane bonbonne prices have a
    DEDICATED founder-editable setting (decision 20/08/2026) on
    ``CompanyProfile.agricole_prix_bonbonne`` / ``agricole_cout_reel_bonbonne`` —
    the same home as the pre-existing ``agricole_pump_hours``. When present it
    is the authoritative source and wins over the legacy JSON override.
    """
    cfg = {
        "cost_per_m3": dict(K.COST_PER_M3),
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
    try:
        from apps.parametres.models_company import CompanyProfile  # type: ignore
        profile = CompanyProfile.objects.filter(company_id=company_id).first()
        if profile is not None:
            prix = getattr(profile, "agricole_prix_bonbonne", None)
            if prix is not None:
                cfg["butane_12kg_subventionne"] = prix
            cout = getattr(profile, "agricole_cout_reel_bonbonne", None)
            if cout is not None:
                cfg["butane_12kg_reel"] = cout
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

    pump_kw = _num(etude.get("pompe_kw"))
    hmt = _num(etude.get("hmt_m"))
    m3_jour = _num(etude.get("m3_jour"))
    champ_kwc = _num(etude.get("champ_kwc")) or _num(data.get("puissance_kwc"))

    # QJR151(a) — jours de pompage et ratio pointe/moyenne SAISISSABLES par
    # devis (``etude_params``), exactement comme ``heures_pompage`` : ces deux
    # valeurs pilotent ``annual_m3``, donc la facture carburant d'aujourd'hui,
    # l'économie, le cumul 20 ans, l'amortissement et le graphe carburant — un
    # pompage 5 jours/semaine fausse le tout d'un facteur ~1,5. La valeur du
    # devis prime ; à défaut le réglage société ; à défaut la constante
    # « à confirmer ». L'hypothèse RETENUE est imprimée sous le graphe de la
    # page 4 (``economics_page``), plus jamais implicite.
    days = (_num(etude.get("jours_pompage_an"))
            or _num(cfg["pumping_days_per_year"], 300) or 300)
    _ratio = _num(etude.get("ratio_pointe_moyenne"))
    peak_to_avg = _ratio if 0 < _ratio <= 1 else (
        _num(cfg["peak_to_avg"], 0.62) or 0.62)

    # Annual water pumped (only when a real m³/jour exists — never invented).
    annual_m3 = round(m3_jour * peak_to_avg * days) if m3_jour > 0 else 0
    has_water = annual_m3 > 0

    rates = cfg["cost_per_m3"]
    # Décompensation : rapport réel/subventionné DÉRIVÉ des deux réglages
    # société (plus de multiplicateur codé en dur — décision fondateur
    # 20/08/2026). L'un des deux à 0/None → aucun rapport calculable → la
    # comparaison décompensée est omise (butane_future reste 0), jamais un
    # multiplicateur inventé.
    _b_sub_for_mult = _num(cfg["butane_12kg_subventionne"])
    _b_reel_for_mult = _num(cfg["butane_12kg_reel"])
    mult = (_b_reel_for_mult / _b_sub_for_mult
            if (_b_sub_for_mult > 0 and _b_reel_for_mult > 0) else None)

    # ANNUAL CASH fuel spend the farmer pays today. Solar burns NO fuel — the
    # sun is free — so its annual carburant cost is 0 (the capital is the quote,
    # recovered through payback). The 0,44 MAD/m³ solar figure is a *lifecycle*
    # cost (capex amortised) shown only in the cost-per-m³ comparison below.
    solaire = 0
    butane_today = round(annual_m3 * _num(rates.get("butane"))) if has_water else 0
    butane_future = round(butane_today * mult) if (has_water and mult) else 0
    diesel = round(annual_m3 * _num(rates.get("diesel"))) if has_water else 0

    current_fuel = (etude.get("current_fuel")
                    or cfg.get("default_current_fuel") or "butane")
    # QJR150 — « Aucune énergie actuelle / nouveau forage » est une option RÉELLE
    # du générateur (``etude_params.current_fuel == "none"``). Ce client ne paie
    # AUCUNE facture de carburant aujourd'hui : lui publier une économie annuelle,
    # un amortissement et un cumul 20 ans adossés à une facture de butane qu'il
    # ne paie pas est un chiffre inventé (règle fondateur « zéro chiffre
    # inventé » — OMETTRE, jamais un repli). Tout ce qui dérive de la dépense
    # actuelle vaut donc 0/None, et la page 4 bascule d'elle-même sur sa branche
    # dégradée « Zéro carburant » (``economics_page``), la page 1 sur son héros
    # « Votre carburant · 0 DH » (``cover``). La comparaison de MARCHÉ
    # solaire/butane/diesel (``fuel_costs``) reste calculée : elle ne prétend pas
    # être la facture du client.
    aucun_carburant = current_fuel == "none"
    if aucun_carburant:
        annual_fuel_now = 0
    elif current_fuel == "diesel":
        annual_fuel_now = diesel
    else:  # butane — carburant de référence par défaut
        annual_fuel_now = butane_today

    # The farmer's REAL current fuel bill (MAD/an), when captured, overrides the
    # modelled cost — savings & payback then reflect what he actually pays today.
    # Une dépense saisie CONTREDIT « aucune énergie actuelle » (deux champs
    # indépendants du formulaire) : on n'arbitre pas entre les deux, on n'en
    # publie aucun.
    fuel_spend = _num(etude.get("fuel_spend_current"))
    if fuel_spend > 0 and not aucun_carburant:
        annual_fuel_now = round(fuel_spend)

    # Savings = the whole fuel bill solar eliminates (solar fuel cost = 0).
    saving_vs_butane = 0 if aucun_carburant else butane_today
    saving_vs_diesel = 0 if aucun_carburant else diesel
    annual_saving = 0 if aucun_carburant else (annual_fuel_now or saving_vs_butane)
    # Cumulative fuel saved over the system life (panels are warrantied 25 yr;
    # use a conservative 20-yr horizon). A big, tangible anchor for the quote.
    savings_20y = annual_saving * 20

    def _payback(total, saving):
        return round(total / saving, 1) if (total > 0 and saving > 0) else None

    payback_butane = _payback(quote_ttc, saving_vs_butane)
    payback_diesel = _payback(quote_ttc, saving_vs_diesel)
    payback = _payback(quote_ttc, annual_saving)

    # FDA 30% subsidy — RATE ONLY (sourced, may be shown). Decision 20/08/2026:
    # the real cap can't be confirmed, so no amount is computed/shown/derived
    # from a cap (no "up to X MAD", no net-after-subsidy). See
    # ``constants.FDA_QUALITATIVE_NOTE`` for the qualitative wording.
    fda_pct = _num(cfg["fda_subsidy_pct"], 30)

    # QJR151(b) — CARBURANT ÉVITÉ ET CO₂ : dérivés de la CONSOMMATION ACTUELLE
    # du client — ``annual_fuel_now``, c'est-à-dire sa dépense carburant SAISIE
    # quand elle existe, sinon le coût modélisé sur son volume d'eau RÉEL — et
    # plus jamais modélisés sur ``pump_cv``, le CV de la pompe SOLAIRE NEUVE qui
    # n'a jamais brûlé un litre (via un ``BUTANE_KG_PER_H_PER_CV`` « à
    # confirmer »). Deux conséquences voulues : le bandeau s'omet quand la
    # consommation actuelle est INCONNUE (ni m³/jour, ni dépense saisie — il
    # s'affichait jusqu'ici sur un devis où le moteur refuse de calculer le
    # moindre m³) et il s'omet sur « aucune énergie actuelle » ; et la quantité
    # publiée repose sur la MÊME base que l'économie annoncée juste à côté.
    co2_kg = 0.0
    fuel_qty_label = ""
    if annual_fuel_now > 0:
        if current_fuel == "diesel":
            _prix_l = _num(cfg["diesel_mad_per_l"])
            if _prix_l > 0:
                litres = annual_fuel_now / _prix_l
                co2_kg = litres * _num(cfg["diesel_kg_co2_per_l"])
                fuel_qty_label = (f"{round(litres):,}".replace(",", " ")
                                  + " L de gasoil")
        else:
            _prix_bonbonne = _num(cfg["butane_12kg_subventionne"])
            if _prix_bonbonne > 0:
                bottles = annual_fuel_now / _prix_bonbonne
                co2_kg = (bottles * 12.0) * _num(cfg["butane_kg_co2_per_kg"])
                fuel_qty_label = (f"{round(bottles):,}".replace(",", " ")
                                  + " bonbonnes de butane")
    co2_t = round(co2_kg / 1000.0, 1) if co2_kg > 0 else 0
    # M8 (audit du 19/08/2026) — MÊME constante partagée que le PDF
    # résidentiel et le site (22 kg CO₂/arbre/an) : ce module portait
    # sa propre copie à 21, donc deux nombres d'arbres pour un même
    # ordre de grandeur selon le mode du devis.
    from ..constants import KG_CO2_PAR_ARBRE_AN as _KG_ARBRE
    trees = max(0, round(co2_kg / _KG_ARBRE)) if co2_kg > 0 else 0

    # Annual PV production.
    prod_kwh = round(champ_kwc * _num(cfg["specific_yield_kwh_kwc"])) if champ_kwc > 0 else 0

    # QJR151(c) — Hectares irrigables : UNIQUEMENT la surface RENSEIGNÉE par le
    # client. La pastille « ≈ X ha de cultures irriguées », imprimée en gros
    # dans la bande de tangibilité de la page 1, était sinon dérivée par
    # division inverse d'une table forfaitaire (défaut 8 000 m³/ha/an) sans
    # AUCUNE donnée de surface — et cette branche s'activait dès que
    # ``surface_ha`` était vide, c'est-à-dire sur la majorité des devis
    # (le champ est optionnel). Surface absente ⇒ pastille OMISE.
    surface_ha = _num(etude.get("surface_ha"))
    hectares = round(surface_ha, 1) if surface_ha > 0 else None

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
        # QJR155 (a) — la clé ``cost_per_m3`` a disparu de la SORTIE : son seul
        # lecteur était le graphe ``charts.cost_per_m3``, qu'aucune page ne
        # rendait. Les TARIFS (``cfg['cost_per_m3']``, réglables par société)
        # restent la source des coûts butane/diesel calculés ci-dessus.
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
        "co2_t": co2_t,
        "trees": trees,
        "fuel_qty_label": fuel_qty_label,
        "hectares_irrigable": hectares,
        # QJR151(a) — l'hypothèse de volume annuel, publiée sous le graphe.
        "pumping_days_per_year": int(round(days)),
        "peak_to_avg": round(peak_to_avg, 2),
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
