"""Glue between an OS Devis and the vendored premium PDF generator.

Builds the data dict that ``generate_premium_pdf`` expects from a real OS quote,
computes the ROI numbers on the fly (no stored fields), renders the 3-page
premium PDF and stores it in MinIO under the same key scheme the old engine used
so the existing download endpoint keeps working.

Nothing here writes new DB columns. Pipeline stages, document statuses, invoices
and orders are untouched.
"""
from __future__ import annotations

import logging
import re
import tempfile
from decimal import Decimal
from pathlib import Path

logger = logging.getLogger(__name__)

_WATT_RE = re.compile(r"(\d{3,4})\s*(?:wc|w)\b", re.IGNORECASE)
# Repli SÛR quand une ligne panneau n'a aucune puissance lisible dans sa
# désignation ni dans le nom du produit lié : on prend le STANDARD du catalogue
# (710 W — « Panneau Canadien Solar 710W »/« Panneau Jinko 710W », cf.
# seed_catalogue + generate_devis_premium.watt_par_panneau), JAMAIS l'ancien 450
# obsolète. Le chemin normal lit la VRAIE puissance via _parse_watt(nom produit).
_DEFAULT_WATT = 710

# ── Conditions de paiement par mode d'installation (SOURCE UNIQUE) ──
# Décision propriétaire 2026-06-12. Tous les formats PDF ET l'échéancier
# devis → factures (acompte/tranches) lisent CE mapping ; plus aucun
# pourcentage de paiement en dur ailleurs. Agricole = défaut résidentiel
# (30/60/10) en attente d'un éventuel veto du fondateur.
PAYMENT_TERMS_BY_MODE = {
    "residentiel": {"acompte": 30, "materiel": 60, "solde": 10},
    "industriel": {"acompte": 50, "materiel": 40, "solde": 10},
    "agricole": {"acompte": 30, "materiel": 60, "solde": 10},
}

# Brand tokens from the simulator catalogue — longest/most specific first so
# 'Deyness' wins over its substring 'Deye'.
_BRAND_TOKENS = [
    "Canadien Solar", "Canadian Solar", "Deyness", "Jinko",
    "Huawei", "Deye", "Lithium", "Gel",
]


def _parse_marque(*texts) -> str:
    """Extract the product brand from designation/product name (one-page badge)."""
    blob = " ".join(t for t in texts if t).lower()
    for brand in _BRAND_TOKENS:
        if brand.lower() in blob:
            return brand
    return ""


def _parse_watt(*texts) -> int | None:
    """Pull a panel wattage (e.g. '450W', '550 Wc') from any of the given strings."""
    for t in texts:
        if not t:
            continue
        m = _WATT_RE.search(str(t))
        if m:
            return int(m.group(1))
    return None


def _is_battery(designation: str) -> bool:
    return "batterie" in (designation or "").lower()


def _is_hybrid_inverter(designation: str) -> bool:
    d = (designation or "").lower()
    return "onduleur" in d and "hybride" in d


def _is_reseau_inverter(designation: str) -> bool:
    d = (designation or "").lower()
    return "onduleur" in d and ("réseau" in d or "reseau" in d or "injection" in d)


def _is_panel(designation: str, produit_nom: str = "") -> bool:
    blob = f"{designation} {produit_nom}".lower()
    return "panneau" in blob or "panneaux" in blob


def _line_to_item(ligne, taux_tva: Decimal) -> dict:
    """Convert an OS LigneDevis (HT prices) into a premium item dict.

    Carries both HT and TTC unit prices (the PDFs show per-line HT with an
    HT → TVA → TTC totals block) plus the product's commercial sheet
    (brand, description lines, warranty) for rich rendering.

    Réforme TVA : le taux de la LIGNE prime quand il existe (10 % panneaux,
    20 % le reste) ; une ligne historique (taux NULL) garde le taux du devis —
    son rendu ne change pas d'un centime.
    """
    ligne_taux = getattr(ligne, "taux_tva", None)
    if ligne_taux is None:
        ligne_taux = taux_tva
    pu_ht = Decimal(ligne.prix_unitaire) * (Decimal(1) - Decimal(ligne.remise) / Decimal(100))
    pu_ttc = pu_ht * (Decimal(1) + Decimal(ligne_taux) / Decimal(100))
    produit = getattr(ligne, "produit", None)
    produit_nom = getattr(produit, "nom", "") or ""
    return {
        "designation": ligne.designation,
        "marque": (getattr(produit, "marque", "") or ""),
        "description": (getattr(produit, "description", "") or ""),
        "garantie": (getattr(produit, "garantie", "") or ""),
        "quantite": float(ligne.quantite),
        "prix_unit_ht": float(round(pu_ht, 2)),
        "prix_unit_ttc": float(round(pu_ttc, 2)),
        "taux_tva": float(ligne_taux),
        "_produit_nom": produit_nom,
    }


# Whitelisted PDF format options (mirroring the simulator's payload). The
# defaults reproduce today's premium 3-page output exactly.
DEFAULT_PDF_OPTIONS = {
    'pdf_mode': 'full',        # 'full' (3 pages) | 'onepage' (1 page)
    'show_monthly': True,      # monthly-savings chart on page 2
    'devis_final': False,      # payment terms + RIB block on page 3
    'payment_mode': 'standard',  # 'standard' (30/60/10) | 'custom'
    'custom_acompte': None,    # MAD down-payment when payment_mode == 'custom'
    'include_etude': False,    # page Étude (industriel) — 4th premium page
    # ── Agricole (pompage) — toggleable persuasion sections (default on) ──
    'show_subsidy': True,          # FDA 30% subsidy block
    'show_fuel_comparison': True,  # solaire vs butane vs diesel + payback
    'show_environmental': True,    # CO₂ / fuel-avoided strip
    'show_schematic': True,        # system schematic on the study page
    'show_water_yield': True,      # water-delivered-per-month chart
    'current_fuel': None,          # 'butane' | 'diesel' | 'none' (else étude/default)
}


def clean_pdf_options(raw) -> dict:
    """Sanitize client-supplied options to the simulator's exact value space."""
    raw = raw or {}
    opts = dict(DEFAULT_PDF_OPTIONS)
    if raw.get('pdf_mode') in ('full', 'onepage'):
        opts['pdf_mode'] = raw['pdf_mode']
    if 'show_monthly' in raw:
        opts['show_monthly'] = bool(raw['show_monthly'])
    if 'devis_final' in raw:
        opts['devis_final'] = bool(raw['devis_final'])
    if 'include_etude' in raw:
        opts['include_etude'] = bool(raw['include_etude'])
    if raw.get('payment_mode') in ('standard', 'custom'):
        opts['payment_mode'] = raw['payment_mode']
    # Agricole toggles — booleans default True; current_fuel a small enum.
    for _flag in ('show_subsidy', 'show_fuel_comparison', 'show_environmental',
                  'show_schematic', 'show_water_yield'):
        if _flag in raw:
            opts[_flag] = bool(raw[_flag])
    if raw.get('current_fuel') in ('butane', 'diesel', 'none'):
        opts['current_fuel'] = raw['current_fuel']
    try:
        acompte = raw.get('custom_acompte')
        # ERR76 — never forward a negative acompte; the engine additionally
        # clamps it to the order total.
        opts['custom_acompte'] = max(0.0, float(acompte)) if acompte not in (None, '') else None
    except (TypeError, ValueError):
        opts['custom_acompte'] = None
    return opts


# ── QJ12 — Financing comparison block ──────────────────────────────────────
# Indicative figures only (no live bank API).  All amounts are MAD TTC.
#
# Green loan parameters (APPROXIMATIF — marché marocain 2026, à confirmer
# avec les banques partenaires). NEVER presented as confirmed prices.
#
# Tatwir Croissance Verte (CIH/BMCE/Attijariwafa — PME):
#   Taux: ~4–5 % an (HT), durée max 7 ans.
# ISTIDAMA (Crédit Agricole du Maroc — agricole):
#   Taux: ~3–4 % an (HTT), durée max 10 ans, FDA subsidy compatible.
#
# Residential / uncategorised fall back to a generic green-mortgage proxy
# (MCMA-style): ~6 % an, 10 ans.
_FINANCING_PROGRAMS = {
    "residentiel": {
        "nom": "Crédit vert résidentiel",
        "taux_annuel": 0.06,          # indicatif
        "duree_mois": 120,
        "programme_label": None,      # no specific named programme
    },
    "industriel": {
        "nom": "Tatwir Croissance Verte (PME)",
        "taux_annuel": 0.045,         # milieu fourchette 4–5 %
        "duree_mois": 84,             # 7 ans
        "programme_label": "Tatwir",
    },
    "agricole": {
        "nom": "ISTIDAMA (Crédit Agricole du Maroc)",
        "taux_annuel": 0.035,         # milieu fourchette 3–4 %
        "duree_mois": 120,            # 10 ans
        "programme_label": "ISTIDAMA",
    },
}
_DEFAULT_FINANCING_KEY = "residentiel"


def _monthly_loan_payment(principal: float, annual_rate: float, n_months: int) -> float:
    """Standard annuity formula.  annual_rate = 0.06 means 6 % per year.
    Returns 0 if inputs are degenerate.
    """
    if principal <= 0 or n_months <= 0:
        return 0.0
    if annual_rate <= 0:
        return round(principal / n_months, 2)
    r = annual_rate / 12
    factor = r * (1 + r) ** n_months / ((1 + r) ** n_months - 1)
    return round(principal * factor, 2)


def compute_financing_block(
    display_total: float,
    eco_s_ann: float,
    eco_a_ann: float,
    mode_installation: str = "residentiel",
) -> dict | None:
    """QJ12 — Build the indicative financing comparison block.

    Returns a dict to be embedded in build_quote_data output under the key
    ``financing``, or ``None`` when the total is zero / unknown (degrades cleanly
    — callers must handle None and omit the block).

    The block is PURELY INDICATIVE.  Every figure carries the flag
    ``indicatif=True``.  Never show buy prices or margins — the returned dict
    contains only TTC client-facing numbers.

    Structure:
        {
            indicatif: True,
            cash: {montant_ttc: float, label: str},
            credit: {
                mensualite: float,
                duree_mois: int,
                taux_annuel_pct: float,
                programme_nom: str,
                programme_label: str | None,
            },
            onee_comparison: {
                show: bool,           # mensualité < économie mensuelle ONEE
                message: str,         # French message if show=True
                eco_mensuelle_sans: float,
                eco_mensuelle_avec: float,
            },
            guidance_text: str | None,  # Tatwir / ISTIDAMA text or None
        }
    """
    if not display_total or display_total <= 0:
        return None

    key = mode_installation if mode_installation in _FINANCING_PROGRAMS else _DEFAULT_FINANCING_KEY
    prog = _FINANCING_PROGRAMS[key]

    mensualite = _monthly_loan_payment(
        display_total,
        prog["taux_annuel"],
        prog["duree_mois"],
    )

    # Monthly savings (use option-1 / sans-batterie as the reference for comparison)
    eco_mensuelle_sans = round(eco_s_ann / 12, 2) if eco_s_ann else 0.0
    eco_mensuelle_avec = round(eco_a_ann / 12, 2) if eco_a_ann else 0.0

    # "mensualité < économie ONEE mensuelle" — when the monthly payment is below
    # even the option-1 monthly savings, the system "pays for itself each month".
    onee_ref = eco_mensuelle_sans  # conservative reference (sans batterie)
    shows_comparison = mensualite > 0 and onee_ref > 0 and mensualite < onee_ref
    if shows_comparison:
        comparison_msg = (
            f"La mensualité indicative ({int(mensualite):,} MAD) est inférieure "
            f"à votre économie mensuelle estimée ({int(onee_ref):,} MAD) — "
            "l'installation se rembourse chaque mois."
        ).replace(',', ' ')
    else:
        comparison_msg = ""

    # Programme guidance text
    guidance = None
    if key == "industriel":
        guidance = (
            "Les PME et professionnels peuvent financer cette installation via "
            "Tatwir Croissance Verte (CIH, BMCE, Attijariwafa) — taux préférentiel "
            "réservé aux projets d'efficacité énergétique. Demandez à votre banque."
        )
    elif key == "agricole":
        guidance = (
            "Le programme ISTIDAMA du Crédit Agricole du Maroc propose un financement "
            "dédié au pompage solaire, cumulable avec la subvention FDA 30 %. "
            "Contactez votre agence CAM pour les conditions exactes."
        )

    return {
        "indicatif": True,
        "cash": {
            "montant_ttc": display_total,
            "label": "Paiement comptant (TTC)",
        },
        "credit": {
            "mensualite": mensualite,
            "duree_mois": prog["duree_mois"],
            "taux_annuel_pct": round(prog["taux_annuel"] * 100, 2),
            "programme_nom": prog["nom"],
            "programme_label": prog["programme_label"],
        },
        "onee_comparison": {
            "show": shows_comparison,
            "message": comparison_msg,
            "eco_mensuelle_sans": eco_mensuelle_sans,
            "eco_mensuelle_avec": eco_mensuelle_avec,
        },
        "guidance_text": guidance,
    }


def build_quote_data(devis, pdf_options=None) -> dict:
    """Build the dict consumed by generate_premium_pdf from a Devis instance."""
    from .pricing import calculate_savings_roi
    from .catalog import pick_default_battery

    client = devis.client
    taux_tva = devis.taux_tva or Decimal(20)
    lignes = list(devis.lignes.select_related("produit").all())

    items = [_line_to_item(li, taux_tva) for li in lignes]
    # Mode « réforme » dès qu'une ligne porte son propre taux ; un devis
    # historique (toutes lignes NULL) reste rendu strictement comme avant.
    per_line_tva = any(getattr(li, "taux_tva", None) is not None for li in lignes)

    # ── Derive power from the panel line(s) ──────────────────────────────────
    nb_panneaux = 0
    watt = None
    for it in items:
        if _is_panel(it["designation"], it.get("_produit_nom", "")):
            nb_panneaux += int(round(it["quantite"]))
            watt = watt or _parse_watt(it["designation"], it.get("_produit_nom", ""))
    watt = watt or _DEFAULT_WATT

    # ── Split into the two options ───────────────────────────────────────────
    # Option 1 "Sans batterie": réseau/injection inverter, NO hybrid, NO battery.
    # Option 2 "Avec batterie": hybrid inverter + battery, NO réseau inverter.
    # HARD RULE: an option NEVER renders without an inverter — an option whose
    # equipment lacks one is dropped (single-option document); a quote with no
    # inverter at all cannot produce an option-based PDF at all.
    # Classification sur désignation ET nom du produit lié : une désignation
    # éditée à la main ne peut pas casser silencieusement le découpage.
    def _blob(it):
        return f"{it['designation']} {it.get('_produit_nom', '')}"

    sans_items = [
        it for it in items
        if not _is_battery(_blob(it)) and not _is_hybrid_inverter(_blob(it))
    ]
    avec_items = [
        it for it in items
        if not _is_reseau_inverter(_blob(it))
    ]

    def _has_qty(rows, pred):
        return any(pred(_blob(r)) and r["quantite"] > 0 for r in rows)

    has_reseau = _has_qty(sans_items, _is_reseau_inverter)
    has_hybride = _has_qty(avec_items, _is_hybrid_inverter)
    has_batterie = _has_qty(avec_items, _is_battery)

    # Power: prefer real panels; otherwise estimate from the equipment total.
    if nb_panneaux > 0:
        puissance_kwc = round(nb_panneaux * watt / 1000, 2)
    else:
        _approx = float(sum(r["quantite"] * r["prix_unit_ttc"] for r in sans_items))
        puissance_kwc = max(3.0, round(_approx / 12000, 2))
        nb_panneaux = max(1, round(puissance_kwc * 1000 / watt))

    # Battery synthesis only at residential scale (≤ 15 kWc) where a single
    # default module is sensible — never a token battery on a large plant.
    if has_hybride and not has_batterie and puissance_kwc <= 15:
        synth = dict(pick_default_battery())
        # Une batterie n'est jamais un panneau : 20 % en mode réforme,
        # taux du devis pour les devis historiques.
        synth_taux = 20.0 if per_line_tva else float(taux_tva)
        synth.setdefault("taux_tva", synth_taux)
        synth.setdefault(
            "prix_unit_ht",
            round(synth.get("prix_unit_ttc", 0) / (1 + synth_taux / 100), 2))
        avec_items = avec_items + [synth]
        has_batterie = True

    opts = clean_pdf_options(pdf_options)
    mode = devis.mode_installation or ""
    # Mode agricole : le format à options n'a pas de sens (pas d'onduleur) —
    # la demande « premium » dégrade proprement vers le format une page.
    pdf_mode = opts['pdf_mode']
    if mode == "agricole" and pdf_mode == "full":
        pdf_mode = "onepage"

    sans_ok = has_reseau
    avec_ok = has_hybride and has_batterie
    # Deux VRAIES options (avant tout repli) — pilote la règle d'intégrité :
    # total d'affichage = option 1, et le une-page ne mélange jamais.
    deux_options = sans_ok and avec_ok
    if not sans_ok and not avec_ok and pdf_mode == "full":
        # RÈGLE DURE : une option ne se rend JAMAIS sans onduleur. Un devis
        # sans aucun onduleur ne peut pas produire le document à options.
        raise ValueError(
            f"Devis {devis.reference} : aucune option ne contient d'onduleur — "
            "génération du PDF à options refusée (règle de sécurité).")
    if not sans_ok and not avec_ok:
        # Format une page (liste simple) : pas d'options — valeurs neutres.
        sans_ok = True
    if sans_ok and avec_ok:
        scenario = "Les deux (Sans + Avec)"
        recommended = "Avec batterie"
    elif sans_ok:
        scenario = "Sans batterie"
        recommended = "Sans batterie"
    else:
        scenario = "Avec batterie"
        recommended = "Avec batterie"

    # ── Canonical totals: ONE computation from the stored HT lines ───────────
    # Every page must display these exact values — never re-derive.
    discount_pct = float(devis.remise_globale or 0)
    tva_pct = float(taux_tva)

    def _canonical_totaux(rows):
        """Chaîne HT → remise → TVA (par taux) → TTC, calculée UNE fois.

        Un seul taux présent (tous les devis historiques) : calcul strictement
        identique à l'ancien. Taux mixtes (réforme 10/20) : la remise globale
        s'applique proportionnellement à chaque ligne, donc chaque panier de
        taux se réduit du même % ; les paniers nets sont réconciliés au
        centime avec le HT net global avant de calculer chaque TVA.
        """
        ht_brut = round(sum(r["quantite"] * r["prix_unit_ht"] for r in rows), 2)
        remise = round(ht_brut * discount_pct / 100, 2) if discount_pct > 0 else 0.0
        ht_net = round(ht_brut - remise, 2)

        buckets_brut = {}
        for r in rows:
            rate = float(r.get("taux_tva", tva_pct))
            buckets_brut[rate] = (
                buckets_brut.get(rate, 0.0) + r["quantite"] * r["prix_unit_ht"])

        if len(buckets_brut) <= 1:
            rate = next(iter(buckets_brut), tva_pct)
            tva_amt = round(ht_net * rate / 100, 2)
            tva_par_taux = [{"taux": rate, "montant": tva_amt, "ht_net": ht_net}]
        else:
            rates = sorted(buckets_brut)
            nets = {
                rate: round(buckets_brut[rate] * (1 - discount_pct / 100), 2)
                for rate in rates
            }
            residu = round(ht_net - sum(nets.values()), 2)
            nets[rates[-1]] = round(nets[rates[-1]] + residu, 2)
            tva_par_taux = [
                {"taux": rate, "montant": round(nets[rate] * rate / 100, 2),
                 "ht_net": nets[rate]}
                for rate in rates
            ]
            tva_amt = round(sum(b["montant"] for b in tva_par_taux), 2)

        ttc_exact = round(ht_net + tva_amt, 2)
        ttc = round(ttc_exact)
        if len(buckets_brut) <= 1:
            _rate0 = next(iter(buckets_brut), tva_pct)
            ttc_avant = round(ht_brut * (1 + _rate0 / 100))  # = calcul historique
        else:
            ttc_avant = round(sum(
                buckets_brut[rate] * (1 + rate / 100) for rate in buckets_brut))
        return {"ht_brut": ht_brut, "remise": remise, "ht_net": ht_net,
                "tva": tva_amt, "tva_par_taux": tva_par_taux,
                "ttc": ttc, "ttc_exact": ttc_exact, "ttc_avant": ttc_avant}

    totaux_sans = _canonical_totaux(sans_items)
    totaux_avec = _canonical_totaux(avec_items)
    # Une page : option 1 seule quand deux vraies options, sinon tout le devis
    totaux_all = _canonical_totaux(sans_items if deux_options else items)

    # ── Total d'AFFICHAGE canonique (liste des devis) ────────────────────────
    # Deux options → total de l'option 1 (remise incluse), jamais la somme
    # mensongère des deux. Mono-option → le total de cette option ; devis
    # libre/pompage → le total complet. Identique au PDF au dirham près.
    if deux_options:
        display_total = totaux_sans["ttc"]
        nb_options = 2
    elif avec_ok:
        display_total = totaux_avec["ttc"]
        nb_options = 1
    elif has_reseau:
        display_total = totaux_sans["ttc"]
        nb_options = 1
    else:
        display_total = totaux_all["ttc"]
        nb_options = 1
    total_sans = totaux_sans["ttc"]
    total_avec = totaux_avec["ttc"]
    total_sans_before = totaux_sans["ttc_avant"]
    total_avec_before = totaux_avec["ttc_avant"]

    # ── Q5 — Toiture 3D : figures du layout FINALISÉ (additif, GARDÉ) ─────────
    # Quand le devis porte un layout 3D finalisé (Devis.roof_layout), ses
    # kWc / production / économies réels remplacent l'estimation — UNIQUEMENT
    # quand le layout est présent. Sans layout, RIEN ici ne s'exécute et la
    # sortie reste byte-identique (back-compat, règle #4). On n'écrase jamais
    # une étude déjà saisie : on ne fait que COMPLÉTER les figures manquantes.
    roof_layout = getattr(devis, "roof_layout", None)
    if roof_layout:
        _res = (roof_layout.get("result") or {}) if isinstance(
            roof_layout, dict) else {}
        _kwc = _res.get("kwc")
        if _kwc:
            puissance_kwc = round(float(_kwc), 2)
        _stored = dict(devis.etude_params or {})
        if _res.get("annualKwh") and not _stored.get("production_annuelle"):
            _stored["production_annuelle"] = int(_res["annualKwh"])
        if _res.get("savings") and not _stored.get("economies_annuelles"):
            _stored["economies_annuelles"] = int(_res["savings"])
        devis_etude_override = _stored
    else:
        devis_etude_override = devis.etude_params or {}

    # ── Canonical performance figures: ONE source of truth ───────────────────
    # When the quote carries a stored étude (industrial), its consumption-driven
    # production/savings are canonical; payback and prix/kWc are recomputed from
    # the canonical totals so edited lines can never desynchronize the document.
    etude = dict(devis_etude_override or {})
    # Agricole : le carburant de référence du comparatif peut être forcé par
    # l'option PDF (sinon l'étude / le défaut « butane » s'applique).
    if opts.get('current_fuel'):
        etude['current_fuel'] = opts['current_fuel']
    # QJ13 — tariff / self-consumption overrides from etude_params.
    # Resolves: tarif_kwh_override → tranches_override → utility name → fallback.
    # All are seller-editable via etude_params; nothing is fabricated from thin air.
    _tarif_kwh_override = etude.get("tarif_kwh")  # explicit flat price (seller set)
    _tranches_override = etude.get("tarif_tranches")  # custom schedule [[ceil, price], …]
    _utility = etude.get("distributeur")  # "onee" | "lydec" | "redal"
    _conso_annuelle = etude.get("conso_annuelle")  # from industrial étude if available
    # Autoconsommation overrides (seller/study can refine these)
    _autoconso_sans = float(etude.get("autoconso_sans") or 0) or None
    _autoconso_avec = float(etude.get("autoconso_avec") or 0) or None
    from .pricing import AUTOCONSO_SANS, AUTOCONSO_AVEC
    roi_kwargs = dict(
        conso_annuelle_kwh=float(_conso_annuelle) if _conso_annuelle else None,
        utility=_utility or None,
        tarif_kwh_override=float(_tarif_kwh_override) if _tarif_kwh_override else None,
        tranches_override=_tranches_override or None,
        autoconso_sans=_autoconso_sans if _autoconso_sans else AUTOCONSO_SANS,
        autoconso_avec=_autoconso_avec if _autoconso_avec else AUTOCONSO_AVEC,
    )
    roi = calculate_savings_roi(puissance_kwc, total_sans, total_avec, **roi_kwargs)
    if etude.get("production_annuelle"):
        roi["prod_kwh"] = int(etude["production_annuelle"])
        if etude.get("economies_annuelles"):
            eco = int(etude["economies_annuelles"])
            roi["eco_s_ann"] = eco
            roi["eco_a_ann"] = eco
            roi["eco_a_cumul"] = eco
            _ref_total = total_sans if sans_ok else total_avec
            roi["roi_s"] = round(_ref_total / eco, 1) if eco > 0 else 0.0
            roi["roi_a"] = roi["roi_s"]
            _sf = [0.053, 0.062, 0.083, 0.098, 0.114, 0.116,
                   0.116, 0.101, 0.087, 0.070, 0.052, 0.048]
            roi["eco_s_monthly"] = [round(eco * f) for f in _sf]
            roi["eco_a_monthly"] = list(roi["eco_s_monthly"])
        # L'étude rendue reprend les valeurs canoniques (jamais deux versions)
        etude["production_annuelle"] = roi["prod_kwh"]
        _ref_total = total_sans if sans_ok else total_avec
        if etude.get("economies_annuelles"):
            etude["economies_annuelles"] = roi["eco_s_ann"]
            etude["payback"] = roi["roi_s"]
        if puissance_kwc > 0:
            etude["prix_kwc"] = round(_ref_total / puissance_kwc)

    # ONEE monthly bill proxy (bars sit above the savings curves): full-price bill
    # ≈ Option-2 monthly savings / 0.85 autoconsumption.
    factures_mensuelles = [round(v / 0.85) for v in roi["eco_a_monthly"]]

    client_name = f"{(client.prenom or '').strip()} {(client.nom or '').strip()}".strip()

    # Liste d'articles du format UNE PAGE. RÈGLE D'INTÉGRITÉ : une facture ne
    # mélange JAMAIS deux options — un devis à deux vraies options (réseau ET
    # hybride+batterie) rend l'OPTION 1 (sans batterie) seule, avec une
    # mention discrète vers la proposition complète. Devis mono-option ou sans
    # options (pompage, liste libre) : toutes les lignes, comme avant.
    onepage_source = sans_items if deux_options else items
    onepage_note_batterie = deux_options
    all_items = [
        {
            **{k: v for k, v in it.items() if k != "_produit_nom"},
            "marque": it["marque"] or _parse_marque(
                it["designation"], it.get("_produit_nom", "")),
        }
        for it in onepage_source if it["quantite"] > 0
    ]

    # Strip the internal helper key before handing items to the generator.
    for rows in (sans_items, avec_items):
        for r in rows:
            r.pop("_produit_nom", None)

    inst_type = {
        "residentiel": "Résidentielle",
        "industriel": "Industrielle / Commerciale",
        "agricole": "Agricole",
    }.get(mode, "Résidentielle")

    # Mode industriel : l'étude fait partie du document (page dédiée incluse
    # d'office quand des données d'étude existent).
    include_etude = opts['include_etude'] or (mode == "industriel" and bool(etude))

    # Puces des cartes d'option de la page 1 — générées depuis l'équipement
    # RÉEL de chaque option, jamais du texte boilerplate.
    def _bullets(rows):
        out = []
        panels = [r for r in rows if _is_panel(r["designation"]) and r["quantite"] > 0]
        if panels:
            n = int(sum(r["quantite"] for r in panels))
            out.append(f"{n} panneaux {watt} W")
        for r in rows:
            if r["quantite"] <= 0:
                continue
            d = r["designation"]
            if _is_reseau_inverter(d) or _is_hybrid_inverter(d):
                q = int(r["quantite"]) if r["quantite"] == int(r["quantite"]) else r["quantite"]
                out.append(f"{q} × {d}" if q > 1 else d)
        for r in rows:
            if _is_battery(r["designation"]) and r["quantite"] > 0:
                q = int(r["quantite"]) if r["quantite"] == int(r["quantite"]) else r["quantite"]
                out.append(f"{q} × {r['designation']}" if q > 1 else r["designation"])
        if any("smart meter" in r["designation"].lower() and r["quantite"] > 0 for r in rows):
            out.append("Smart Meter + monitoring")
        out.append("Structures + installation complète")
        return out[:6]

    # Conditions de paiement par mode — réglage éditable de la société, repli
    # sur PAYMENT_TERMS_BY_MODE (défaut historique → PDF identique).
    from apps.ventes.utils.company_settings import (
        payment_terms_for, entreprise_for)
    payment_terms = payment_terms_for(getattr(devis, "company", None), mode)

    # DC1 — identité société (RC/ICE/RIB/banque/adresse/tél/nom) résolue depuis
    # CompanyProfile, en REPLI sur les littéraux historiques. Tant que rien n'est
    # renseigné → valeurs Taqinor d'avant, PDF byte-identique ; une autre société
    # voit SES coordonnées (plus de fuite du RIB Taqinor). Dict JSON-sérialisable.
    entreprise = entreprise_for(getattr(devis, "company", None))

    # DC25 — devise + taux résolus par l'UNIQUE source `selectors.devise_for`
    # (devise document → défaut société → MAD). Sans devise renseignée → MAD,
    # taux 1 (comportement inchangé). JSON-sérialisable.
    from apps.ventes.selectors import devise_for
    _devise, _taux_dec = devise_for(devis)
    _taux_change = float(_taux_dec or 1)

    # D2/N60/N67/N59 — textes éditables du devis (en-têtes/CGV/validité/garanties
    # /BPA/tampon). SURCHARGES non vides seulement ; toute clé absente → le moteur
    # applique son littéral historique, donc le PDF reste byte-identique tant que
    # rien n'est édité. Repli silencieux sur {} si la table n'existe pas encore.
    doc_texts = {}
    try:
        from apps.parametres.models_documents import DocumentTemplates
        doc_texts = DocumentTemplates.get(
            company=getattr(devis, "company", None)).as_doc_texts()
    except Exception:  # noqa: BLE001 — un PDF ne doit jamais casser là-dessus
        doc_texts = {}

    tva_label = int(tva_pct) if tva_pct == int(tva_pct) else tva_pct
    # Texte TVA UNIQUE, partagé par toutes les notes/conditions des PDF.
    # Réforme (taux par ligne) : le texte décrit la règle 10/20 ; devis
    # historiques : l'ancien texte au taux global, rendu inchangé.
    if per_line_tva:
        tva_note = ("TVA : 10% panneaux photovoltaïques · "
                    "20% autres équipements et prestations")
    else:
        tva_note = f"TVA {tva_label} % appliquée sur l'ensemble des équipements et travaux."
    data = {
        "ref": devis.reference,
        "date": devis.date_creation.strftime("%d/%m/%Y"),
        "client_name": client_name or "Client",
        "client_addr": client.adresse or "",
        "client_phone": client.telephone or "",
        "client_ice": (getattr(client, "ice", "") or ""),
        "inst_type": inst_type,
        "puissance_kwc": puissance_kwc,
        "nb_panneaux": nb_panneaux,
        "watt_par_panneau": watt,
        "prod_kwh": roi["prod_kwh"],
        "total_sans": total_sans,
        "total_avec": total_avec,
        "total_sans_before": total_sans_before,
        "total_avec_before": total_avec_before,
        # Totaux canoniques (chaîne HT → remise → TVA → TTC calculée UNE fois)
        "totaux_sans": totaux_sans,
        "totaux_avec": totaux_avec,
        "totaux_all": totaux_all,
        "per_line_tva": per_line_tva,
        "discount_pct": discount_pct,
        "eco_s_ann": roi["eco_s_ann"],
        "eco_a_ann": roi["eco_a_ann"],
        "eco_a_cumul": roi["eco_a_cumul"],
        "roi_s": roi["roi_s"],
        "roi_a": roi["roi_a"],
        "eco_s_monthly": roi["eco_s_monthly"],
        "eco_a_monthly": roi["eco_a_monthly"],
        # QJ13 — honest-number guard: True when savings are an estimate (no tariff data)
        "savings_estimated": roi.get("savings_estimated", False),
        "tarif_kwh": roi.get("tarif_kwh"),
        "factures_mensuelles": factures_mensuelles,
        "sans_items": sans_items,
        "avec_items": avec_items,
        "sans_bullets": _bullets(sans_items),
        "avec_bullets": _bullets(avec_items),
        "scenario": scenario,
        "recommended": recommended,
        "all_items": all_items,
        "onepage_note_batterie": onepage_note_batterie,
        "display_total": display_total,
        "nb_options": nb_options,
        "pdf_mode": pdf_mode,
        "show_monthly": opts['show_monthly'],
        "devis_final": opts['devis_final'],
        "payment_mode": opts['payment_mode'],
        "custom_acompte": opts['custom_acompte'],
        "include_etude": include_etude,
        "taux_tva": tva_pct,
        "tva_note": tva_note,
        "payment_terms": payment_terms,
        "mode_installation": mode,
        "etude": etude,
        # Agricole — toggleable persuasion sections + company (Paramètres
        # economics override). Ignored by every other renderer.
        "show_subsidy": opts['show_subsidy'],
        "show_fuel_comparison": opts['show_fuel_comparison'],
        "show_environmental": opts['show_environmental'],
        "show_schematic": opts['show_schematic'],
        "show_water_yield": opts['show_water_yield'],
        # company id only (JSON-serializable — this dict is also returned by the
        # public proposal-data endpoint; never put the model instance here).
        "_company_id": getattr(devis, "company_id", None),
        # D2/N60/N67/N59 — surcharges de texte éditables (vide → littéral moteur).
        "doc_texts": doc_texts,
        # DC1 — identité société (repli sur littéraux historiques).
        "entreprise": entreprise,
        # N26 — tampon d'acceptation : nom + date posés à l'acceptation du devis
        # (le moteur ne l'affiche QUE si les deux sont présents). Date au format
        # FR jj/mm/aaaa, vide sinon → devis byte-identique à aujourd'hui.
        "accepte_par_nom": (getattr(devis, "accepte_par_nom", "") or ""),
        "date_acceptation": (
            devis.date_acceptation.strftime("%d/%m/%Y")
            if getattr(devis, "date_acceptation", None) else ""),
        # FG52/DC25 — devise + taux portés par le document, résolus par l'UNIQUE
        # source `selectors.devise_for` (devise document → défaut société → MAD).
        # Aucun impact sur les montants en base (stockés en MAD) ; uniquement
        # affiché sur le PDF et porté dans l'export UBL.
        "devise": _devise,
        "taux_change": _taux_change,
    }
    # Q5 — visuel « votre installation » : la clé MinIO du rendu 3D N'EST
    # ajoutée que si le devis en porte un. Sans rendu, aucune clé n'est
    # ajoutée → la sortie reste strictement identique à aujourd'hui.
    roof_image = getattr(devis, "roof_image", None)
    if roof_image:
        data["roof_image_key"] = roof_image
    # QJ12 — financing block (indicatif / à confirmer). Added additively after
    # all other keys so omitting it never changes any existing key's value.
    # Degrades to None when display_total is unavailable — callers omit the block.
    financing = compute_financing_block(
        display_total=display_total,
        eco_s_ann=roi.get("eco_s_ann", 0),
        eco_a_ann=roi.get("eco_a_ann", 0),
        mode_installation=mode,
    )
    if financing is not None:
        data["financing"] = financing
    return data


def display_totals(devis) -> dict:
    """Total d'affichage canonique pour la liste des devis — calculé par le
    MÊME chemin que les PDF (mode une-page, qui ne lève jamais), donc identique
    au document au dirham près. Repli sûr sur le total stocké."""
    try:
        data = build_quote_data(devis, {"pdf_mode": "onepage"})
        return {"total": data["display_total"], "nb_options": data["nb_options"]}
    except Exception:  # noqa: BLE001 — une liste ne doit jamais casser
        logger.exception("display_totals: repli sur total_ttc (devis %s)",
                         getattr(devis, "reference", "?"))
        return {"total": float(devis.total_ttc), "nb_options": 1}


def _pdf_key(devis) -> str:
    """MinIO key, scoped by company to avoid cross-tenant collisions."""
    company_id = getattr(devis, "company_id", None) or "0"
    return f"devis/{company_id}/{devis.reference}.pdf"


def _ensure_pdf_bucket() -> None:
    """Create the PDF bucket if it does not exist yet (idempotent, best-effort)."""
    from django.conf import settings
    from apps.ventes.utils.minio_client import get_minio_client

    client = get_minio_client()
    bucket = settings.MINIO_BUCKET_PDF
    try:
        client.head_bucket(Bucket=bucket)
    except Exception:
        try:
            client.create_bucket(Bucket=bucket)
            logger.info("Created MinIO bucket: %s", bucket)
        except Exception as exc:
            logger.warning("Could not ensure MinIO bucket %s: %s", bucket, exc)


def generate_premium_devis_pdf(devis_id, pdf_options=None, persist=True) -> str:
    """Render the quote PDF for a Devis in the requested format and store it
    in MinIO. pdf_options (see DEFAULT_PDF_OPTIONS) selects the simulator
    format: full 3-page premium (default) or one-page, with the monthly-chart
    and devis-final modifiers. Returns the stored MinIO key.

    ERR74 — ``persist`` controls the ``devis.fichier_pdf`` write. The PDF is
    always rendered and uploaded to its (deterministic, company-scoped) MinIO
    key, but on a safe GET path (``/proposal``, public share link) we pass
    ``persist=False`` so the read does not also write the model row when the
    column already points at that same key — avoiding a write side-effect on a
    safe method and a redundant re-persist. With ``persist=True`` (default,
    used by the Celery generate task) the column is refreshed only when it
    actually changed.
    """
    from apps.ventes.models import Devis
    from apps.ventes.utils.pdf import _upload_pdf
    from .generate_devis_premium import generate_premium_pdf

    devis = (
        Devis.objects
        .select_related("client", "company")
        .prefetch_related("lignes__produit")
        .get(pk=devis_id)
    )

    data = build_quote_data(devis, pdf_options)

    # ONE engine, two renderers. The redesigned 3-page layout renders
    # residential quotes (full format); the legacy renderer serves every other
    # market mode / format (industriel, agricole, one-page, étude) and is also
    # the automatic fall-back, so a client PDF is never broken.
    pdf_bytes = None
    # Agricole premium multi-page proposal (full format). One-page agricole and
    # every other mode/format stay on the legacy engine / residential renderer.
    from .agricole import renderer as agricole
    if agricole.is_agricultural(devis, pdf_options):
        try:
            pdf_bytes = agricole.render_pdf_bytes(data)
        except agricole.Unsupported:
            pdf_bytes = None
        except Exception:
            logger.warning(
                "Agricole renderer failed for %s; using legacy engine",
                getattr(devis, "reference", devis_id), exc_info=True)
            pdf_bytes = None
    from .residential import renderer as residential
    if pdf_bytes is None and residential.is_residential(devis, pdf_options):
        try:
            pdf_bytes = residential.render_pdf_bytes(data)
        except residential.Unsupported:
            pdf_bytes = None
        except Exception:
            logger.warning(
                "Residential renderer failed for %s; using legacy engine",
                getattr(devis, "reference", devis_id), exc_info=True)
            pdf_bytes = None
    if pdf_bytes is None:
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tf:
            tmp_path = tf.name
        try:
            generate_premium_pdf(data, tmp_path)
            pdf_bytes = Path(tmp_path).read_bytes()
        finally:
            Path(tmp_path).unlink(missing_ok=True)

    key = _pdf_key(devis)
    _ensure_pdf_bucket()
    _upload_pdf(pdf_bytes, key)

    # Persist the key only when asked AND when it actually changed: a safe GET
    # (persist=False) never writes; the default path writes once.
    if persist and devis.fichier_pdf != key:
        devis.fichier_pdf = key
        devis.save(update_fields=["fichier_pdf"])

    logger.info("Premium quote PDF generated: %s (%d bytes)", key, len(pdf_bytes))
    return key
