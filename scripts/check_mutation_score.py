#!/usr/bin/env python3
"""ENF12 — garde BLOQUANTE du score de mutation (mutmut 3, job nocturne).

Lit ``mutants/mutmut-cicd-stats.json`` (``mutmut export-cicd-stats``) et rend 1
si :
  * moins de ``MIN_EVALUES`` mutants ont réellement été jugés (« n'a pas
    tourné » n'est JAMAIS un vert — les nuits du 28/09 au 08/10/2026 ont toutes
    fini à 0 tué / 0 survivant, masquées par ``continue-on-error``) ;
  * le score ``(tués + timeouts + segfaults) / jugés`` est sous ``PLANCHER``.

Une passe bornée par ``timeout`` (5 608 mutants mesurés le 28/09/2026) reste
valable : le score porte sur les mutants jugés avant la borne.

PLANCHER : aucune passe n'a encore produit de score (toutes interrompues) —
plancher CONSERVATEUR de 50 % fixé le 09/10/2026, à recalibrer sur la première
nuit verte (le monter par paliers de 5 points, jamais le baisser).

Usage : python scripts/check_mutation_score.py chemin/mutmut-cicd-stats.json
"""
from __future__ import annotations

import json
import sys

PLANCHER = 50.0
MIN_EVALUES = 100


def evaluer(stats: dict) -> tuple[bool, str]:
    attrapes = sum(int(stats.get(k, 0) or 0) for k in ("killed", "timeout", "segfault"))
    rates = sum(int(stats.get(k, 0) or 0) for k in ("survived", "suspicious"))
    juges = attrapes + rates
    if juges < MIN_EVALUES:
        return False, (f"ECHEC : {juges} mutant(s) jugé(s) sur {stats.get('total', '?')} "
                       f"(minimum {MIN_EVALUES}) — la passe n'a pas réellement tourné.")
    score = attrapes / juges * 100
    message = (f"score de mutation {score:.1f} % ({attrapes} attrapés / {juges} jugés, "
               f"plancher {PLANCHER:.0f} %)")
    if score < PLANCHER:
        return False, "ECHEC : " + message
    return True, "OK — " + message


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print(__doc__)
        return 2
    try:
        with open(argv[1], encoding="utf-8") as fh:
            stats = json.load(fh)
    except (OSError, ValueError) as exc:
        print(f"ECHEC : statistiques mutmut illisibles ({exc}).")
        return 1
    ok, message = evaluer(stats)
    print(message)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
