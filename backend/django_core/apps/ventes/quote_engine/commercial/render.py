# flake8: noqa
"""Commercial render harness — assembles the 3 category-aware page modules into
one A4 PDF. Driven by ``commercial.renderer``. Reuses ``residential.theme``."""
from __future__ import annotations
from pathlib import Path

from . import cover, equip, trust
from .. import premium_base


# QJR651 — contexte, enveloppe de page, assemblage HTML et rendu PDF
# vivent dans ``quote_engine/premium_base.py`` ; ce module ne garde que
# SA liste de pages.
def pages(ctx: dict) -> list:
    """Les 3 pages premium commerciales.

    p1 cover catégorie-aware (label + pictogramme + KPIs + accroche) · p2
    équipements + totaux + bloc catégorie · p3 confiance + étapes + signature.
    """
    return [cover.build(ctx), equip.build(ctx), trust.build(ctx)]


def build_html(data: dict) -> str:
    return premium_base.build_html(data, pages)


def render_pdf(out_path, data: dict | None = None) -> str:
    if data is None:
        from . import sample_data
        data = sample_data.build()
    return premium_base.render_pdf(
        out_path, build_html(data), Path(__file__).resolve().parent)
