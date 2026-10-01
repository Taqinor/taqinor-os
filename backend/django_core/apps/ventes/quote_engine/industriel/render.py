# flake8: noqa
"""Industriel render harness — assembles the 4 CFO page modules into one A4 PDF
(QJR620 : + la page équipements/totaux partagée avec le commercial).
Driven by ``industriel.renderer`` from the single quote engine. Reuses
``residential.theme`` (fonts, logo, footer, company identity, base CSS)."""
from __future__ import annotations
from pathlib import Path

from . import cover, finance, trust
from .. import premium_base


# QJR651 — contexte, enveloppe de page, assemblage HTML et rendu PDF
# vivent dans ``quote_engine/premium_base.py`` ; ce module ne garde que
# SA liste de pages.
def pages(ctx: dict) -> list:
    """Les 4 pages premium industrielles (D-QJR5-12, QJR620).

    p1 baseline énergétique + KPIs (CFO cover) · p2 équipements + chaîne de
    totaux Sous-total HT → Remise → Total HT → TVA → Total TTC (la page
    ``commercial.equip`` RÉUTILISÉE telle quelle : lignes en HT, sections,
    notes et options proposées) · p3 cashflow 15 ans + payback + TRI (+
    injection 82-21 si calculée) · p4 tranches phasées + normes ISO
    50001/CBAM + garanties + signature.
    """
    from ..commercial import equip

    return [cover.build(ctx), equip.build(ctx), finance.build(ctx),
            trust.build(ctx)]


def build_html(data: dict) -> str:
    return premium_base.build_html(data, pages)


def render_pdf(out_path, data: dict | None = None) -> str:
    if data is None:
        from . import sample_data
        data = sample_data.build()
    return premium_base.render_pdf(
        out_path, build_html(data), Path(__file__).resolve().parent)
