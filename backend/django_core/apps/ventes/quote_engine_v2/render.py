"""v2 PROTOTYPE render harness — assembles the 3 page modules into one A4 PDF.
Inert: never imported by /proposal or the live engine."""
from __future__ import annotations
from pathlib import Path

from . import theme
from . import charts as charts_mod
from . import cover, options, trust


def build_ctx(data: dict) -> dict:
    return {
        "d": data,
        "C": theme.C,
        "fmt": theme.fmt,
        "fonts": {"display": theme.FONT_DISPLAY, "serif": theme.FONT_SERIF,
                  "sans": theme.FONT_SANS},
        "logo_dark": theme.logo_dark_b64(),
        "logo_color": theme.logo_color_b64(),
        "hero_img": theme.hero_image_b64(),
        "charts": charts_mod.build_all(data),
    }


def _wrap(inner: str, n: int, data: dict) -> str:
    foot = theme.page_footer(data).replace("{page}", str(n))
    return f'<div class="page">{inner}{foot}</div>'


def build_html(data: dict) -> str:
    ctx = build_ctx(data)
    p1 = _wrap(cover.build(ctx), 1, data)
    p2 = _wrap(options.build(ctx), 2, data)
    p3 = _wrap(trust.build(ctx), 3, data)
    return (f"<!doctype html><html><head><meta charset='utf-8'>"
            f"<style>{theme.base_css()}</style></head>"
            f"<body>{p1}{p2}{p3}</body></html>")


def render_pdf(out_path, data: dict | None = None) -> str:
    from weasyprint import HTML
    if data is None:
        from . import sample_data
        data = sample_data.build()
    html = build_html(data)
    base = str(Path(__file__).resolve().parent)
    HTML(string=html, base_url=f"file://{base}/").write_pdf(str(out_path))
    return str(out_path)
