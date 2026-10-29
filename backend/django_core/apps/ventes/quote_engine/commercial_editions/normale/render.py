# flake8: noqa
# D-ENF22 : exception de fichier entier signée — moteur de devis vendoré (règle #4 de CLAUDE.md), non réécrit pour le lint.
"""Édition Normale — assemblage des 3 pages."""
from __future__ import annotations

from .. import commun, donnees, harnais
from . import confiance, couverture, offre

JETON = commun.jeton(commun.NORMALE)
#: Variante A (garanties et échéancier en page 2) aux paliers 0-3, puis
#: variante B (l'ordre exact du devis actuel) aux paliers 0-3.
ESSAIS = [(v, pal) for v in ("A", "B") for pal in range(4)]


def pages(ctx: dict) -> list:
    m = donnees.modele(ctx["d"], ctx)
    j = JETON
    css = f"<style>{commun.css_commune(j, 'no')}</style>" + commun.css_densite('no', j, m["palier"])
    return [css + couverture.build(ctx, m, j), css + offre.build(ctx, m, j),
            css + confiance.build(ctx, m, j)]


def build_html(data: dict) -> str:
    return harnais.build_html(data, pages, JETON)
