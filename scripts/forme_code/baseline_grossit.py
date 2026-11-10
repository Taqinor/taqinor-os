"""Regle BASELINE_GROSSIT — une baseline ne fait que retrecir (C20).

Baselines : `scripts/*_allow.txt`, `*allowlist*.txt`, `*_exceptions*.txt`, `*_non_branches.txt`,
`exceptions_permanentes.yml`, tout `_dette.yml`, et (ADCG76, par cle = 1er mot)
`scripts/liste_page1_non_paginees.txt`, `scripts/taches_audit_v2.txt`, `platform_baselines/*.txt`.
Entree = ligne non vide hors commentaire ;
toute entree absente a la base (fichier neuf compris) est refusee.
AMET100 - CLE_LIGNE : une entree ajoutee dont la cle (1er mot) porte un numero de ligne nu
(`fichier.py:123`, `#L123`) est refusee : une cle se nomme par symbole (`fichier::symbole[#n]`).
"""
from __future__ import annotations

import re

from .socle import Constat

# ADCG76 — listes gelées qui échappaient au cliquet ; jugées PAR CLÉ (1er mot) : corriger
# la citation d'une entrée existante n'est pas grossir.
GELEES = re.compile(r"^scripts/(liste_page1_non_paginees|taches_audit_v2)\.txt$|/platform_baselines/[^/]+\.txt$")
BASELINES = re.compile(r"^scripts/[^/]*(_allow|allowlist|_exceptions|_non_branches)[^/]*\.txt$"
                       r"|^scripts/exceptions_permanentes\.yml$|(^|/)_dette\.yml$|" + GELEES.pattern)


DETTE = re.compile(r"(^|/)_dette\.yml$")
ID_DETTE = re.compile(r"^-\s*([^\s#,\[\]]+)|^ids:\s*\[([^\]]*)\]")


def _entrees(texte: str | None, chemin: str = "") -> set:
    lignes = [s for s in (ligne.strip() for ligne in (texte or "").splitlines()) if s and not s.startswith("#")]
    if not DETTE.search(chemin):
        return set(lignes)
    # `_dette.yml` : une entree = un id de `ids:` (bloc `- X` ou flux `[X, Y]`), jamais
    # une ligne d'en-tete — `ids: []` ecrit par check_acceptation quand la dette est vide.
    ids = set()
    for m in filter(None, map(ID_DETTE.match, lignes)):
        ids.update([m.group(1)] if m.group(1) else (x.strip() for x in m.group(2).split(",") if x.strip()))
    return ids


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
        tete, base = _entrees(ctx.texte("tete", c.apres), c.apres), _entrees(ctx.texte("base", c.avant), c.apres)
        if GELEES.search(c.apres):
            tete, base = ({e.split()[0] for e in s} for s in (tete, base))
        neuves = tete - base
        if neuves:
            exemples = " ; ".join(sorted(neuves)[:3])
            constats.append(Constat("BASELINE_GROSSIT", c.apres, "", (
                f"+{len(neuves)} entrée(s) gelée(s) ({exemples}) : une baseline ne fait que rétrécir")))
        constats.extend(_cles_par_ligne(c.apres, neuves))
    return constats
