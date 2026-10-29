# flake8: noqa
# D-ENF22 : exception de fichier entier signée — moteur de devis vendoré (règle #4 de CLAUDE.md), non réécrit pour le lint.
"""Édition Directe — assemblage des 3 pages."""
from __future__ import annotations

from .. import commun, donnees, harnais
from . import accord, gagnez, recevez

JETON = commun.jeton(commun.DIRECTE)


def css_directe(j: dict) -> str:
    """Surcharges de l'édition : corps plus grand, libellés doublés FR/AR."""
    return f"""
.dr-root{{font-size:9.6pt;}}
.dr-lab2{{font-size:8.4pt;font-weight:500;color:{j['ink']};}}
.dr-lab2 .dr-fr{{display:inline-block;}}
.dr-lab2 .dr-ar{{display:inline-block;margin-left:7px;color:{j['muted']};font-weight:400;font-size:9pt;}}
.dr-h2 .dr-ar{{display:inline-block;font-family:{j['arabe']};font-size:11.5pt;color:{j['muted']};margin-left:10px;vertical-align:baseline;}}
.dr-tbl td{{font-size:9pt;}}
"""


def pages(ctx: dict) -> list:
    m = donnees.modele(ctx["d"], ctx)
    j = JETON
    css = f"<style>{commun.css_commune(j, 'dr')}{css_directe(j)}</style>" + commun.css_densite('dr', j, m["palier"])
    return [css + gagnez.build(ctx, m, j), css + recevez.build(ctx, m, j),
            css + accord.build(ctx, m, j)]


def build_html(data: dict) -> str:
    return harnais.build_html(data, pages, JETON)
