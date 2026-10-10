"""Regle BASELINE_GROSSIT — une baseline ne fait que retrecir (C20).

Baselines : `scripts/*_allow.txt`, `*allowlist*.txt`, `*_exceptions*.txt`, `*_non_branches.txt`,
`exceptions_permanentes.yml`, tout `_dette.yml`. Entree = ligne non vide hors commentaire ;
toute entree absente a la base (fichier neuf compris) est refusee.
AMET100 - CLE_LIGNE : une entree ajoutee dont la cle (1er mot) porte un numero de ligne nu
(`fichier.py:123`, `#L123`) est refusee : une cle se nomme par symbole (`fichier::symbole[#n]`).
"""
from __future__ import annotations

import re

from .socle import Constat

BASELINES = re.compile(r"^scripts/[^/]*(_allow|allowlist|_exceptions|_non_branches)[^/]*\.txt$"
                       r"|^scripts/exceptions_permanentes\.yml$|(^|/)_dette\.yml$")


def _entrees(texte: str | None) -> set:
    return {s for s in (ligne.strip() for ligne in (texte or "").splitlines()) if s and not s.startswith("#")}


CLE_PAR_LIGNE = re.compile(r"(?<!:):\d+(?::\d+)?$|#L\d+$")


def _cle_par_ligne(entree: str) -> bool:
    """Vrai si le 1er mot de l'entree finit par un numero de ligne nu (ni `::symbole`, ni `#n`)."""
    return bool(CLE_PAR_LIGNE.search(entree.split()[0]))


def _cles_par_ligne(chemin: str, neuves: set) -> list:
    lignes = sorted(e for e in neuves if _cle_par_ligne(e))
    if not lignes:
        return []
    return [Constat("CLE_LIGNE", chemin, "", (
        f"+{len(lignes)} clé(s) par numéro de ligne ({' ; '.join(e.split()[0] for e in lignes[:3])}) : "
        "nommer le symbole (`fichier::symbole[#n]`), jamais la ligne"))]


def verifier(ctx) -> list:
    constats = []
    for c in ctx.changements:
        if not (c.apres and BASELINES.search(c.apres)):
            continue
        neuves = _entrees(ctx.texte("tete", c.apres)) - _entrees(ctx.texte("base", c.avant))
        if neuves:
            exemples = " ; ".join(sorted(neuves)[:3])
            constats.append(Constat("BASELINE_GROSSIT", c.apres, "", (
                f"+{len(neuves)} entrée(s) gelée(s) ({exemples}) : une baseline ne fait que rétrécir")))
        constats.extend(_cles_par_ligne(c.apres, neuves))
    return constats
