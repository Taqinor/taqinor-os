# flake8: noqa
"""Agricole renderer selection + data augmentation for the single engine.

``generate_premium_devis_pdf`` builds the quote data once, then asks this module
whether the premium multi-page AGRICOLE layout applies. If so it renders PDF
bytes; otherwise it raises ``Unsupported`` and the engine falls back to the
legacy renderer (which still serves the agricole one-page format). One engine,
one data builder.

Renders only — never changes a devis status (CLAUDE.md rule #4).
"""
from __future__ import annotations
from pathlib import Path


class Unsupported(Exception):
    """The devis/options are outside the agricole renderer's scope."""


def is_agricultural(devis, options=None) -> bool:
    """True when the premium multi-page agricole layout should render this quote.

    Agricole market mode + the full/premium format. The agricole ONE-PAGE format
    stays on the legacy engine (fast WhatsApp/field send), exactly like the
    residential split.
    """
    mode = (getattr(devis, "mode_installation", None) or "").strip().lower()
    if mode != "agricole":
        return False
    opts = options or {}
    if (opts.get("pdf_mode") or "full") not in ("full", "premium"):
        return False
    return True


# Toggleable persuasion sections (founder choice #3). Defaults: all on. Read
# from pdf_options via the builder's whitelist; absent → on.
_TOGGLES = ("show_subsidy", "show_fuel_comparison", "show_environmental",
            "show_schematic", "show_water_yield")


def _augment(data: dict) -> dict:
    """Add the agricole layout's derived fields (economics, schematic params,
    page count, links) onto the built quote data. Raises Unsupported when the
    quote has nothing to render (no lines)."""
    from . import economics

    items = data.get("all_items") or []
    if not any((it.get("quantite") or 0) > 0 for it in items):
        raise Unsupported("agricole quote has no priced lines")

    d = dict(data)
    eco = economics.compute(d, company_id=d.get("_company_id"))
    d.update(eco)

    # QX47 — série MENSUELLE du besoin de la culture (moteur QX48) pour le
    # graphe « eau livrée vs besoin culture », et bassin recommandé. Dégrade
    # proprement (None) quand la culture/surface manque — aucun chiffre inventé.
    from . import agronomy
    _e = data.get("etude") or {}
    _crop = (_e.get("crop") or "").strip().lower() or None
    _region = (_e.get("region") or "").strip().lower() or None
    _surface = _e.get("surface_ha")
    _method = (_e.get("irrigation_method") or "").strip().lower() or None
    d["monthly_need_m3day"] = None
    d["etc_mm_day"] = None
    try:
        _has_surface = float(_surface or 0) > 0
    except (TypeError, ValueError):
        _has_surface = False
    if _crop and _has_surface:
        _m = agronomy.monthly_water_demand(
            crop=_crop, region=_region, surface_ha=_surface, method=_method)
        d["monthly_need_m3day"] = _m["gross_m3_farm_day"]
        d["etc_mm_day"] = _m["etc_mm_day"]
    d["m3_jour_delivered"] = _e.get("m3_jour")
    # Bassin recommandé : 1-3× le besoin journalier de pointe (2× par défaut →
    # ~2 jours d'autonomie). Source : bonne pratique irrigation (tampon jour/nuit
    # + aléas). Rendu SEULEMENT si le besoin de pointe est connu.
    _besoin = d.get("besoin_m3j")
    d["bassin_reco_m3"] = None
    d["bassin_autonomie_j"] = None
    try:
        _b = float(_besoin or 0)
    except (TypeError, ValueError):
        _b = 0.0
    if _b > 0:
        d["bassin_min_m3"] = round(_b)          # 1× → ~1 jour
        d["bassin_reco_m3"] = round(_b * 2)     # 2× → ~2 jours (recommandé)
        d["bassin_max_m3"] = round(_b * 3)      # 3× → ~3 jours
        d["bassin_autonomie_j"] = 2

    d.setdefault("client_full", d.get("client_name") or "Client")
    d["validity_days"] = d.get("validity_days", 30)
    d["site_url"] = d.get("site_url", "taqinor.ma")
    d["pages_total"] = 4
    # QK5 — /avis n'existe pas sur taqinor.ma : repli sur /realisations
    # (page réelle) pour ne pas produire un lien 404 sur un PDF client.
    d["links"] = d.get("links") or {
        "realisations": "taqinor.ma/realisations",
        "avis": "taqinor.ma/realisations",
        "produits": "taqinor.ma/produits",
        "garanties": "taqinor.ma/garanties",
        "signer": f"taqinor.ma/signer/{d.get('ref', '')}",
    }
    # Toggles default to True.
    for t in _TOGGLES:
        d[t] = bool(d.get(t, True))

    etude = d.get("etude") or {}
    d["schematic_params"] = {
        "kwc": d.get("puissance_kwc"),
        "nb_panneaux": d.get("nb_panneaux"),
        "watt": d.get("watt_par_panneau"),
        "pump_cv": etude.get("pompe_cv"),
        "pump_kw": etude.get("pompe_kw"),
        "type_pompe": etude.get("type_pompe"),
        "hmt_m": etude.get("hmt_m"),
        "debit_m3h": etude.get("debit_hmt_m3h") or etude.get("debit_souhaite_m3h"),
        "m3_jour": etude.get("m3_jour"),
        "profondeur_m": etude.get("profondeur_m"),
        "source": etude.get("source") or etude.get("type_point_eau") or "forage",
        "surface_ha": etude.get("surface_ha"),
        "crop": etude.get("crop"),
    }
    return d


def render_pdf_bytes(data: dict) -> bytes:
    """Render the premium agricole proposal to PDF bytes, or raise Unsupported."""
    from weasyprint import HTML
    from . import render as agricole_render
    d = _augment(data)
    html = agricole_render.build_html(d)
    base = str(Path(agricole_render.__file__).resolve().parent)
    return HTML(string=html, base_url=f"file://{base}/").write_pdf()
