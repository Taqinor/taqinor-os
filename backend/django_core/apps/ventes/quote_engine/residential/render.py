# flake8: noqa
"""Residential render harness — assembles the 3 page modules into one A4 PDF.
Driven by `residential.renderer` from the single quote engine."""
from __future__ import annotations
from pathlib import Path

from . import theme
from . import charts as charts_mod
from . import cover, options, trust


def build_ctx(data: dict) -> dict:
    # QX4 — identité société (multi-tenant) résolue UNE fois et partagée par
    # toutes les pages. Chaque littéral d'identité (footer, bande légale,
    # « Pourquoi … », signature, cover, liens) lit ``ident`` et retombe sur le
    # littéral Taqinor historique quand le champ correspondant est vide → un
    # devis sans profil enrichi reste rendu strictement à l'identique.
    ident = theme.company_identity(data)
    return {
        "d": data,
        "C": theme.C,
        "fmt": theme.fmt,
        "fonts": {"display": theme.FONT_DISPLAY, "serif": theme.FONT_SERIF,
                  "sans": theme.FONT_SANS},
        "logo_dark": theme.logo_dark_b64(),
        "logo_color": theme.logo_color_b64(),
        "hero_img": theme.hero_image_b64(data.get("puissance_kwc"), "residentiel"),
        "charts": charts_mod.build_all(data),
        "ident": ident,
    }


def _wrap(inner: str, n: int, data: dict, ident: dict, total: int = 3) -> str:
    # QX6 — le pied lit le NOMBRE RÉEL de pages rendues (jamais « / 3 » codé).
    foot = (theme.page_footer(data, ident, total_pages=total)
            .replace("{page}", str(n)))
    return f'<div class="page">{inner}{foot}</div>'


def build_html(data: dict) -> str:
    ctx = build_ctx(data)
    ident = ctx["ident"]
    pages = [cover.build(ctx), options.build(ctx), trust.build(ctx)]
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
