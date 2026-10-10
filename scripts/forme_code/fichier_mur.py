"""Regle FICHIER_MUR — un fichier de code >= 2 000 lignes ne grossit pas.

Croissance = lignes LOGIQUES nettes (tete - base - lignes deplacees vers lui).
Budget = somme des `lignes nettes attendues ≤ N` des lignes de tache COCHEES
par la PR qui citent ce chemin EXACT entre backticks (`backend/django_core/apps/
crm/services.py` ou `apps/crm/services.py`, jamais `services.py` nu) ; 0 sinon.
"""
from __future__ import annotations

from .socle import Constat, budget, cite, est_code

SEUIL = 2000


def verifier(ctx) -> list:
    constats = []
    for c in ctx.changements:
        tete = ctx.fichier("tete", c.apres) if est_code(c.apres) else None
        if tete is None or tete.brutes < SEUIL:
            continue
        base = ctx.fichier("base", c.avant)
        net = len(tete.lignes) - (len(base.lignes) if base else 0) - ctx.deplaces.lignes_entrees.get(c.apres, 0)
        taches = [(ident, budget(ligne)) for ident, ligne in ctx.taches if cite(ligne, c.apres)]
        total = sum(b for _, b in taches if b is not None)
        if net <= total:
            continue
        source = ", ".join(f"{i} ≤ {b}" if b is not None else f"{i} sans budget" for i, b in taches)
        constats.append(Constat("FICHIER_MUR", c.apres, "", (
            f"fichier de {tete.brutes} lignes : +{net} lignes logiques nettes > budget {total} "
            f"({source or 'aucune tâche cochée par la PR ne cite ce chemin exact'})")))
    return constats
