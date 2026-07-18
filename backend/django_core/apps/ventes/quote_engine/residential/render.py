# flake8: noqa
"""Residential render harness — assembles the 3 page modules into one A4 PDF.
Driven by `residential.renderer` from the single quote engine."""
from __future__ import annotations
import re
from pathlib import Path

from . import theme
from . import charts as charts_mod
from . import cover, options, trust

# QRES62 — joints élastiques : marqueurs inertes posés par les gabarits de
# page ; le second passage de rendu les remplace par des espaceurs
# dimensionnés d'après le vide MESURÉ de chaque page.
_QJ_RE = re.compile(r'<div class="qj" data-w="(\d+)"></div>')


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


def _apply_elastic(inner: str, slack_mm: float) -> str:
    """QRES62 — remplace les joints ``.qj`` d'une page par des espaceurs
    proportionnels à leur poids ``data-w`` (somme des poids ≈ 100), pour un
    total de ``slack_mm`` millimètres. ``slack_mm`` ≤ 0 → joints retirés
    (page identique au premier passage)."""
    weights = [int(w) for w in _QJ_RE.findall(inner)]
    if not weights:
        return inner
    total_w = sum(weights) or 1

    def _sub(m):
        if slack_mm <= 0:
            return ""
        h = slack_mm * int(m.group(1)) / total_w
        return f'<div style="height:{h:.1f}mm"></div>' if h >= 0.5 else ""

    return _QJ_RE.sub(_sub, inner)


def _wrap(inner: str, n: int, data: dict, ident: dict, total: int = 3,
          slack_mm: float = 0.0) -> str:
    # QX6 — le pied lit le NOMBRE RÉEL de pages rendues (jamais « / 3 » codé).
    foot = (theme.page_footer(data, ident, total_pages=total)
            .replace("{page}", str(n)))
    inner = _apply_elastic(inner, slack_mm)
    return f'<div class="page">{inner}{foot}</div>'


def build_html(data: dict, elastic: dict | None = None) -> str:
    """``elastic`` (QRES62) : {numéro de page 1-based: mm de vide à répartir
    sur les joints de cette page}. None/absent → joints inertes (passe 1)."""
    ctx = build_ctx(data)
    ident = ctx["ident"]
    # QRES17 — pagination variable : un devis chargé rend 2+ pages
    # « installation » (tableau découpé + page rentabilité dédiée) ; le pied
    # « Page n / N » lit le nombre RÉEL de pages (QX6).
    pages = [cover.build(ctx)] + options.build_pages(ctx) + [trust.build(ctx)]
    total = len(pages)
    elastic = elastic or {}
    body = "".join(
        _wrap(inner, n, data, ident, total,
              slack_mm=float(elastic.get(n, 0.0)))
        for n, inner in enumerate(pages, start=1))
    return (f"<!doctype html><html><head><meta charset='utf-8'>"
            f"<style>{theme.base_css()}</style></head>"
            f"<body>{body}</body></html>")


def render_pdf(out_path, data: dict | None = None) -> str:
    from weasyprint import HTML
    if data is None:
        # QRES12 — le repli d'aperçu passe par le VRAI pipeline (fixture
        # sample_data + renderer._augment) ; l'ancien chemin importait une
        # fixture inexistante (ImportError latent) et sautait l'augmentation.
        from . import renderer, sample_data
        data = renderer._augment(sample_data.build())
    html = build_html(data)
    base = str(Path(__file__).resolve().parent)
    HTML(string=html, base_url=f"file://{base}/").write_pdf(str(out_path))
    return str(out_path)
