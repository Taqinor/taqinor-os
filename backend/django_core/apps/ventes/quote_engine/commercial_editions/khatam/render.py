# flake8: noqa
# D-ENF22 : exception de fichier entier signée — moteur de devis vendoré (règle #4 de CLAUDE.md), non réécrit pour le lint.
"""Édition Khatam — assemblage des 3 pages (le devis actuel, habillé)."""
from __future__ import annotations

from .. import commun, donnees, harnais
from . import confiance, couverture, offre

JETON = commun.jeton(commun.KHATAM)
#: Paliers de densité 0-3 (CIQ317), une seule variante de placement.
ESSAIS = [("A", 0), ("A", 1), ("A", 2), ("A", 3)]


def pages(ctx: dict) -> list:
    m = donnees.modele(ctx["d"], ctx)
    j = JETON
    css = f"<style>{commun.css_commune(j, 'kh')}</style>" + commun.css_densite('kh', j, m["palier"])
    return [css + couverture.build(ctx, m, j), css + offre.build(ctx, m, j),
            css + confiance.build(ctx, m, j)]


def build_html(data: dict) -> str:
    return harnais.build_html(data, pages, JETON)
