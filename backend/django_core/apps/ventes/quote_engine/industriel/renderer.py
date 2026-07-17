# flake8: noqa
"""Industriel renderer selection + data augmentation for the single engine.

``generate_premium_devis_pdf`` builds the quote data once, then asks this module
whether the premium multi-page INDUSTRIEL (CFO) layout applies. If so it renders
PDF bytes; otherwise it raises ``Unsupported`` and the engine falls back to the
legacy renderer (which still serves the industriel one-page format and is the
automatic off-switch). One engine, one data builder.

Renders only — never changes a devis status (CLAUDE.md rule #4).
"""
from __future__ import annotations
from pathlib import Path


class Unsupported(Exception):
    """The devis/options are outside the industriel renderer's scope."""


def is_industrial(devis, options=None) -> bool:
    """True when the premium multi-page INDUSTRIEL layout should render this quote.

    Industriel market mode + the full/premium format. The industriel ONE-PAGE
    format stays on the legacy engine (fast field send), exactly like the
    residential/agricole split.
    """
    mode = (getattr(devis, "mode_installation", None) or "").strip().lower()
    if mode != "industriel":
        return False
    opts = options or {}
    if (opts.get("pdf_mode") or "full") not in ("full", "premium"):
        return False
    return True


def _num(v):
    try:
        f = float(v)
        return f if f == f else None
    except (TypeError, ValueError):
        return None


def _augment(data: dict) -> dict:
    """Add the industriel layout's derived CFO fields onto the built quote data.
    Raises Unsupported when the quote has no priced investment to render."""
    items = data.get("all_items") or []
    if not any((it.get("quantite") or 0) > 0 for it in items):
        raise Unsupported("industriel quote has no priced lines")

    invest = _num(data.get("display_total")) or 0.0
    if invest <= 0:
        # repli sûr : total canonique TTC si display_total absent
        invest = _num((data.get("totaux_all") or {}).get("ttc")) or 0.0
    if invest <= 0:
        raise Unsupported("industriel quote has no investment total")

    etude = data.get("etude") or {}
    d = dict(data)
    d["_invest_ttc"] = round(invest)
    d.setdefault("client_full", d.get("client_name") or "Client")
    d["validity_days"] = d.get("validity_days", 30)

    # KPIs de l'étude (None quand non calculés → la page dégrade proprement).
    d["ind_kwc"] = _num(etude.get("kwc")) or _num(d.get("puissance_kwc"))
    d["ind_prod"] = _num(etude.get("production_annuelle")) or _num(d.get("prod_kwh"))
    d["ind_conso"] = _num(etude.get("conso_annuelle")) or _num(d.get("conso_annuelle_kwh"))
    d["ind_autoconso"] = _num(etude.get("taux_autoconso"))
    d["ind_couverture"] = _num(etude.get("taux_couverture"))
    eco = _num(etude.get("economies_annuelles"))
    if eco is None:
        eco = _num(d.get("eco_s_ann"))
    d["ind_economies"] = round(eco) if eco else 0
    pb = _num(etude.get("payback"))
    if pb is None:
        pb = _num(d.get("roi_s"))
    d["ind_payback"] = pb
    d["ind_prix_kwc"] = _num(etude.get("prix_kwc"))

    # Injection 82-21 (QX50) — rendue UNIQUEMENT si l'étude la porte (net des
    # frais réseau, plafonnée 20 %). Absente aujourd'hui → aucune ligne inventée.
    d["ind_injection_dh"] = _num(etude.get("injection_dh_an"))
    d["ind_injection_kwh"] = _num(etude.get("injection_kwh_an"))
    # O&M annuel : rendu seulement si fourni (sinon note « inclus »).
    d["ind_om_annuel"] = _num(etude.get("om_annuel"))

    # site + liens (repli résidentiel/théme).
    d["site_url"] = d.get("site_url") or "taqinor.ma"
    return d


def render_pdf_bytes(data: dict) -> bytes:
    """Render the premium industriel proposal to PDF bytes, or raise Unsupported."""
    from weasyprint import HTML
    from . import render as industriel_render
    d = _augment(data)
    html = industriel_render.build_html(d)
    base = str(Path(industriel_render.__file__).resolve().parent)
    return HTML(string=html, base_url=f"file://{base}/").write_pdf()
