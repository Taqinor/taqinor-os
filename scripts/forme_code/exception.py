"""Regle EXCEPTION — `Exception C20 : <REGLE> <chemin> car : <raison>` sur une ligne COCHEE par la PR.

Exempte <REGLE> pour <chemin> (fichier exact, `fichier::symbole`, ou dossier
terminant par `/` ; memes alias que le budget). Comptee PAR LIGNE DE TACHE : le rapport dit combien de
constats chaque tache a exemptes ; une exception d'une tache non cochee par
la PR n'exempte rien. Une exception qui n'exempte rien est signalee.
"""
from __future__ import annotations

import re

from .socle import alias

MOTIF = re.compile(r"Exception C20\s*:\s*([A-Z_]+)\s+`?([^`\s]+)`?\s+car\s*:")


def _vise(chemin: str, constat) -> bool:
    """Fichier exact, `fichier::symbole`, ou dossier terminant par `/` (ex. amorcage des `_dette.yml`)."""
    fichier, _, symbole = chemin.partition("::")
    if fichier.endswith("/"):
        return any(a.startswith(fichier) for a in alias(constat.fichier))
    return any(a == fichier for a in alias(constat.fichier)) and symbole in ("", constat.symbole)


def verifier(ctx, constats: list) -> tuple:
    """(constats restants, {tache: [constats exemptes]}, [exceptions inutilisees])."""
    exceptions = [(ident, regle, chemin) for ident, ligne in ctx.taches for regle, chemin in MOTIF.findall(ligne)]
    restants, exemptes, utilisees = [], {}, set()
    for c in constats:
        porteuse = next((e for e in exceptions if e[1] == c.regle and _vise(e[2], c)), None)
        if porteuse is None:
            restants.append(c)
            continue
        utilisees.add(porteuse)
        exemptes.setdefault(porteuse[0], []).append(c)
    inutiles = [f"{i} : {r} {ch}" for i, r, ch in exceptions if (i, r, ch) not in utilisees]
    return restants, exemptes, inutiles
