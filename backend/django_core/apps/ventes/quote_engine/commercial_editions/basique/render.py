# flake8: noqa
# D-ENF22 : exception de fichier entier signée — moteur de devis vendoré (règle #4 de CLAUDE.md), non réécrit pour le lint.
"""Édition Basique — assemblage : 1 page (variante « une »), sinon 2."""
from __future__ import annotations

from .. import commun, donnees, harnais
from . import devis, essentiel

JETON = commun.jeton(commun.BASIQUE)
#: 1 page aux paliers 0-2, puis 2 pages au palier 0 puis 1 (jamais 3).
ESSAIS = [("une", 0), ("une", 1), ("une", 2), ("deux", 0), ("deux", 1)]


def pages(ctx: dict) -> list:
    m = donnees.modele(ctx["d"], ctx)
    j = JETON
    css = f"<style>{commun.css_commune(j, 'ba')}</style>" + commun.css_densite('ba', j, m["palier"])
    out = [css + essentiel.build(ctx, m, j)]
    if m["variante"] == "deux":
        out.append(css + devis.build(ctx, m, j))
    return out


def build_html(data: dict) -> str:
    return harnais.build_html(data, pages, JETON)
