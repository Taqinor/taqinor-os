"""Regle GARDE_NEUVE — 0 garde hors des 6 familles (C20 ; groupe AMET, NE PAS FAIRE).

Familles : migrations, argent, societe, construit-non-consomme, dates, hygiene des tests. La famille
se tranche AU PLAN : un nouveau `scripts/check_*.py` n'est admis que si une tache COCHEE par la PR
le cite par son chemin EXACT entre backticks (« sauf ceux listes ici ») ; sinon etendre la garde existante.
"""
from __future__ import annotations

import re

from .socle import Constat, cite

GARDE = re.compile(r"^scripts/check_[^/]+\.py$")


def verifier(ctx) -> list:
    constats = []
    for c in ctx.changements:
        if not (c.apres and GARDE.match(c.apres)) or (c.avant and GARDE.match(c.avant)):
            continue
        if not any(cite(ligne, c.apres) for _, ligne in ctx.taches):
            constats.append(Constat("GARDE_NEUVE", c.apres, "", (
                "nouvelle garde : aucune tâche cochée par la PR ne la cite (chemin exact entre backticks) "
                "— étendre la garde existante de sa famille (migrations, argent, société, "
                "construit-non-consommé, dates, hygiène des tests)")))
    return constats
