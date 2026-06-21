# flake8: noqa
"""Wire the redesigned (v2) quote PDF into the live /proposal path — FAIL-SAFE.

`render_pdf_bytes(devis, options)` renders the redesigned 3-page proposal for the
standard residential two-option quote. For anything it does not cover yet
(one-page format, the étude page, single-option / pompage quotes, missing bill
baseline) it raises `V2Unsupported`, and the caller falls back to the proven
premium engine — so a client PDF is never broken.

This only RENDERS; it never changes a devis status (CLAUDE.md rule #4
STATUS PRESERVATION). `/proposal` stays the single client-facing path.
"""
from __future__ import annotations
import os


class V2Unsupported(Exception):
    """The current devis/options are outside the redesigned engine's scope."""


def v2_enabled() -> bool:
    """On by default; set USE_QUOTE_ENGINE_V2=0 to force the legacy engine."""
    return os.getenv("USE_QUOTE_ENGINE_V2", "1").strip().lower() not in (
        "0", "false", "no", "off", "")


def _build_data(devis, options) -> dict:
    options = options or {}
    mode = options.get("pdf_mode") or "full"
    if mode not in ("full", "premium"):
        raise V2Unsupported(f"pdf_mode={mode!r} handled by legacy engine")
    if options.get("include_etude"):
        raise V2Unsupported("étude page handled by legacy engine")

    from ..quote_engine.builder import build_quote_data
    qd = build_quote_data(devis, {"pdf_mode": "full"})

    need = ("sans_items", "avec_items", "totaux_sans", "totaux_avec",
            "roi_s", "roi_a", "total_sans", "total_avec",
            "eco_s_ann", "eco_a_ann", "factures_mensuelles", "eco_a_monthly",
            "puissance_kwc", "prod_kwh", "nb_panneaux", "watt_par_panneau",
            "ref", "date")
    for k in need:
        v = qd.get(k)
        if v in (None, "", [], 0):
            raise V2Unsupported(f"missing quote field: {k}")

    before = list(qd["factures_mensuelles"])
    if len(before) != 12:
        raise V2Unsupported("need 12 monthly bills for the avant/après chart")
    after = [max(0, round(b - s)) for b, s in zip(before, qd["eco_a_monthly"])]
    annual_before, annual_after = sum(before), sum(after)
    if annual_before <= 0:
        raise V2Unsupported("no bill baseline")
    conso = max(1, round(annual_before / 1.3))
    coverage = max(40, min(99, round(qd["prod_kwh"] / conso * 100)))

    qd.setdefault("client_full", qd.get("client_name") or "Client")
    qd.update({
        "bills_before": before, "bills_after": after,
        "annual_before": annual_before, "annual_after": annual_after,
        "coverage_pct": coverage,
        "validity_days": qd.get("validity_days", 30),
        "site_url": qd.get("site_url", "taqinor.ma"),
        "links": qd.get("links") or {
            "realisations": "taqinor.ma/realisations",
            "avis": "taqinor.ma/avis",
            "produits": "taqinor.ma/produits",
            "garanties": "taqinor.ma/garanties",
            "signer": f"taqinor.ma/signer/{qd.get('ref', '')}",
        },
    })
    return qd


def render_pdf_bytes(devis, options=None) -> bytes:
    """Render the redesigned proposal to PDF bytes, or raise V2Unsupported."""
    from pathlib import Path
    from weasyprint import HTML
    from . import render as v2_render
    data = _build_data(devis, options)
    html = v2_render.build_html(data)
    base = str(Path(v2_render.__file__).resolve().parent)
    return HTML(string=html, base_url=f"file://{base}/").write_pdf()
