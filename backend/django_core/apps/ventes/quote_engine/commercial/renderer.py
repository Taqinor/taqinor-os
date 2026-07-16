# flake8: noqa
"""Commercial renderer selection + data augmentation for the single engine.

``generate_premium_devis_pdf`` builds the quote data once, then asks this module
whether the premium multi-page COMMERCIAL (category-aware) layout applies. If so
it renders PDF bytes; otherwise it raises ``Unsupported`` and the engine falls
back to the legacy renderer (the off-switch / one-page path).

Renders only — never changes a devis status (CLAUDE.md rule #4).
"""
from __future__ import annotations
from pathlib import Path


class Unsupported(Exception):
    """The devis/options are outside the commercial renderer's scope."""


def is_commercial(devis, options=None) -> bool:
    """True when the premium multi-page COMMERCIAL layout should render this quote.

    Commercial market mode + the full/premium format. The one-page format stays
    on the legacy engine, exactly like the residential/agricole/industriel split.
    """
    mode = (getattr(devis, "mode_installation", None) or "").strip().lower()
    if mode != "commercial":
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
    """Add the commercial layout's derived fields onto the built quote data.
    Raises Unsupported when the quote has no priced investment to render."""
    items = data.get("all_items") or []
    if not any((it.get("quantite") or 0) > 0 for it in items):
        raise Unsupported("commercial quote has no priced lines")

    invest = _num(data.get("display_total")) or 0.0
    if invest <= 0:
        invest = _num((data.get("totaux_all") or {}).get("ttc")) or 0.0
    if invest <= 0:
        raise Unsupported("commercial quote has no investment total")

    etude = data.get("etude") or {}
    d = dict(data)
    d["_invest_ttc"] = round(invest)
    d.setdefault("client_full", d.get("client_name") or "Client")
    d["validity_days"] = d.get("validity_days", 30)

    d["com_category"] = (etude.get("categorie_commerciale") or "").strip().lower() or None
    d["com_kwc"] = _num(etude.get("kwc")) or _num(d.get("puissance_kwc"))
    d["com_prod"] = _num(etude.get("production_annuelle")) or _num(d.get("prod_kwh"))
    d["com_conso"] = _num(etude.get("conso_annuelle")) or _num(d.get("conso_annuelle_kwh"))
    d["com_autoconso"] = _num(etude.get("taux_autoconso"))
    d["com_couverture"] = _num(etude.get("taux_couverture"))
    eco = _num(etude.get("economies_annuelles"))
    if eco is None:
        eco = _num(d.get("eco_s_ann"))
    d["com_economies"] = round(eco) if eco else 0
    pb = _num(etude.get("payback"))
    if pb is None:
        pb = _num(d.get("roi_s"))
    d["com_payback"] = pb

    d["site_url"] = d.get("site_url") or "taqinor.ma"
    return d


def render_pdf_bytes(data: dict) -> bytes:
    """Render the premium commercial proposal to PDF bytes, or raise Unsupported."""
    from weasyprint import HTML
    from . import render as commercial_render
    d = _augment(data)
    html = commercial_render.build_html(d)
    base = str(Path(commercial_render.__file__).resolve().parent)
    return HTML(string=html, base_url=f"file://{base}/").write_pdf()
