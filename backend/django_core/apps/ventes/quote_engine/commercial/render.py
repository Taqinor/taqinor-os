# flake8: noqa
"""Commercial render harness — assembles the 3 category-aware page modules into
one A4 PDF. Driven by ``commercial.renderer``. Reuses ``residential.theme``."""
from __future__ import annotations
from pathlib import Path

from ..residential import theme
from . import cover, equip, trust


def build_ctx(data: dict) -> dict:
    ident = theme.company_identity(data)
    return {
        "d": data,
        "C": theme.C,
        "fmt": theme.fmt,
        "fonts": {"display": theme.FONT_DISPLAY, "serif": theme.FONT_SERIF,
                  "sans": theme.FONT_SANS},
        "logo_dark": theme.logo_dark_b64(),
        "logo_color": theme.logo_color_b64(),
        "ident": ident,
        "theme": theme,
    }


def _wrap(inner: str, n: int, data: dict, ident: dict, total: int = 3) -> str:
    foot = (theme.page_footer(data, ident, total_pages=total)
            .replace("{page}", str(n)))
    return f'<div class="page">{inner}{foot}</div>'


def build_html(data: dict) -> str:
    """Assemble the 3-page premium commercial proposal.

    p1 cover catégorie-aware (label + pictogramme + KPIs + accroche) · p2
    équipements + totaux + bloc catégorie · p3 confiance + étapes + signature.
    """
    ctx = build_ctx(data)
    ident = ctx["ident"]
    pages = [cover.build(ctx), equip.build(ctx), trust.build(ctx)]
    total = len(pages)
    body = "".join(
        _wrap(inner, n, data, ident, total)
        for n, inner in enumerate(pages, start=1))
    return (f"<!doctype html><html><head><meta charset='utf-8'>"
            f"<style>{theme.base_css()}</style></head>"
            f"<body>{body}</body></html>")


def render_pdf(out_path, data: dict | None = None) -> str:
    from weasyprint import HTML
    if data is None:
        from . import sample_data
        data = sample_data.build()
    html = build_html(data)
    base = str(Path(__file__).resolve().parent)
    HTML(string=html, base_url=f"file://{base}/").write_pdf(str(out_path))
    return str(out_path)
