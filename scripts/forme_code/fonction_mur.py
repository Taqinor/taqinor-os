"""Regle FONCTION_MUR — une fonction de plus de 100 lignes logiques ne grossit pas.

Juge les LIGNES LOGIQUES : reformater (une ligne brute de plus, deux
instructions fusionnees) ne leve rien ; ajouter une instruction, si.
"""
from __future__ import annotations

from .socle import Constat

SEUIL = 100


def verifier(ctx) -> list:
    constats = []
    for c, base, tete in ctx.paires_py():
        anciennes = {d.qualname: d for d in base.defs if d.kind == "fonction"} if base else {}
        for d in tete.defs:
            ancienne = anciennes.get(d.qualname)
            if ancienne is None:
                continue
            apres, avant = tete.compter(d.debut, d.fin), base.compter(ancienne.debut, ancienne.fin)
            if apres > SEUIL and apres > avant:
                constats.append(Constat("FONCTION_MUR", c.apres, d.qualname, (
                    f"fonction de {apres} lignes logiques (> {SEUIL}) : +{apres - avant} — extraire, ne pas grossir")))
    return constats
