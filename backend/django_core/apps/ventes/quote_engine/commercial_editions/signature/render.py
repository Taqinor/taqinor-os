# flake8: noqa
# D-ENF22 : exception de fichier entier signée — moteur de devis vendoré (règle #4 de CLAUDE.md), non réécrit pour le lint.
"""Édition Signature — assemblage des 3 pages."""
from __future__ import annotations

from .. import commun, donnees, harnais
from . import couverture, devis, energie

JETON = commun.jeton(commun.SIGNATURE)
#: Essais de mise en page (variante, palier) dans l'ordre (synthèse §6).
ESSAIS = [("A", 0), ("A", 1), ("A", 2), ("A", 3)]


def pages(ctx: dict) -> list:
    m = donnees.modele(ctx["d"], ctx)
    j = JETON
    css = f"<style>{commun.css_commune(j, 'sg')}</style>" + commun.css_densite('sg', j, m["palier"])
    return [css + couverture.build(ctx, m, j), css + energie.build(ctx, m, j),
            css + devis.build(ctx, m, j)]


def build_html(data: dict) -> str:
    return harnais.build_html(data, pages, JETON)
