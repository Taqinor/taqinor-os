"""Regle FONCTION_NEUVE — une fonction neuve tient en 60 lignes logiques.

Neuve = `qualname` absent du meme fichier a la base, et pas un deplacement SPL.
"""
from __future__ import annotations

from .socle import Constat

MAX_LIGNES = 60


def verifier(ctx) -> list:
    constats = []
    for c, base, tete in ctx.paires_py():
        anciens = {d.qualname for d in base.defs} if base else set()
        for d in tete.defs:
            if d.kind != "fonction" or d.qualname in anciens or (c.apres, d.qualname) in ctx.deplaces.entres:
                continue
            n = tete.compter(d.debut, d.fin)
            if n > MAX_LIGNES:
                constats.append(Constat("FONCTION_NEUVE", c.apres, d.qualname,
                                        f"fonction neuve de {n} lignes logiques (> {MAX_LIGNES})"))
    return constats
