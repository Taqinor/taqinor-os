# flake8: noqa
"""Agricole render harness — assembles the 5 page modules into one A4 PDF.
Driven by ``agricole.renderer`` from the single quote engine."""
from __future__ import annotations
from pathlib import Path

from . import theme
from . import charts as charts_mod
from . import schematic as schematic_mod
from . import cover, study, yield_page, economics_page


def build_ctx(data: dict) -> dict:
    return {
        "d": data,
        "C": theme.C,
        "fmt": theme.fmt,
        "fmt_dec": theme.fmt_dec,
        "fonts": {"display": theme.FONT_DISPLAY, "serif": theme.FONT_SERIF,
                  "sans": theme.FONT_SANS, "arabic": theme.FONT_ARABIC},
        "logo_dark": theme.logo_dark_b64(),
        "logo_color": theme.logo_color_b64(),
        "hero_img": theme.hero_image_b64(data.get("puissance_kwc"), "agricole"),
        "charts": charts_mod.build_all(data),
        "schematic": schematic_mod.build(data.get("schematic_params") or {}),
    }


def _wrap(inner: str, n: int, data: dict) -> str:
    foot = theme.page_footer(data).replace("{page}", str(n))
    return f'<div class="page">{inner}{foot}</div>'


def build_html(data: dict) -> str:
    """Assemble the 4-page premium agricole proposal.

    p1 cover · p2 étude + schéma + production/eau · p3 équipement + prix +
    subvention FDA + garanties · p4 rentabilité (carburant + payback + impact)
    + conditions + signature. The 5-page airy version is preserved on the
    `agricole-quote-v5-5pages` tag / locked branch.
    """
    ctx = build_ctx(data)
    p1 = _wrap(cover.build(ctx), 1, data)
    p2 = _wrap(study.build(ctx), 2, data)
    p3 = _wrap(yield_page.build(ctx), 3, data)
    p4 = _wrap(economics_page.build(ctx), 4, data)
    return (f"<!doctype html><html><head><meta charset='utf-8'>"
            f"<style>{theme.base_css()}</style></head>"
            f"<body>{p1}{p2}{p3}{p4}</body></html>")


def render_pdf(out_path, data: dict) -> str:
    from weasyprint import HTML
    html = build_html(data)
    base = str(Path(__file__).resolve().parent)
    HTML(string=html, base_url=f"file://{base}/").write_pdf(str(out_path))
    return str(out_path)
