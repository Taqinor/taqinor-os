"""Regle BASELINE_GROSSIT — une baseline ne fait que retrecir (C20).

Baselines : `scripts/*_allow.txt`, `*allowlist*.txt`, `*_exceptions*.txt`, `*_non_branches.txt`,
`exceptions_permanentes.yml`, tout `_dette.yml`. Entree = ligne non vide hors commentaire ;
toute entree absente a la base (fichier neuf compris) est refusee.
"""
from __future__ import annotations

import re

from .socle import Constat

BASELINES = re.compile(r"^scripts/[^/]*(_allow|allowlist|_exceptions|_non_branches)[^/]*\.txt$"
                       r"|^scripts/exceptions_permanentes\.yml$|(^|/)_dette\.yml$")


def _entrees(texte: str | None) -> set:
    return {s for s in (ligne.strip() for ligne in (texte or "").splitlines()) if s and not s.startswith("#")}


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
    return constats
