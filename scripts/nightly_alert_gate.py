#!/usr/bin/env python3
"""CAD177 — decide si `release-verify` doit ALERTER (2 nuits de suite non
vertes).

Le 12/09/2026, `release-verify.yml` a echoue CHAQUE nuit pendant DOUZE nuits
(image `minio/minio` refusee au pull) sans qu'aucun signal n'alerte (constat
CAD86/CAD177, voir docs/crm/messages_meryem.md). Ce script isole la DECISION
pure que le job `alert-on-repeated-failure` de `.github/workflows/
release-verify.yml` appelle : etant donne les resultats des jobs de CE run
nocturne et la conclusion du run nocturne PRECEDENT (deja termine, lu par le
workflow via `gh run list --event schedule --status completed`), faut-il
ouvrir/mettre a jour une issue GitHub et faire echouer le job franchement ?

Isoler la decision ici (plutot que de l'ecrire inline en bash+jq dans le
YAML) la rend testable en HOTE, sans docker ni API GitHub — voir
scripts/tests/test_nightly_alert_gate.py.

Regle : alerter ssi CE run n'est pas entierement vert (`success` sur CHAQUE
job attendu) ET que le run nocturne precedent n'etait pas non plus un succes
complet — y compris quand l'historique est absent/ambigu (fail-safe : on
n'alerte JAMAIS moins que necessaire par defaut, seulement plus si le doute
existe).

Usage (depuis le workflow) :
    python scripts/nightly_alert_gate.py \\
        --job-result success --job-result failure \\
        --previous-conclusion success
Sortie : imprime "true" ou "false" sur STDOUT (jamais dans le code de
retour — le workflow lit stdout ; un code de sortie non nul refleterait un
BUG du script lui-meme, jamais la decision "faut-il alerter").
"""
from __future__ import annotations

import argparse
import sys
from typing import Optional, Sequence

SUCCESS = "success"


def is_run_green(job_results: Sequence[str]) -> bool:
    """Vrai ssi TOUS les jobs valent 'success'.

    Une liste VIDE n'est jamais verte (fail-safe : un job oublie dans le
    cablage du workflow ne doit jamais se lire comme "tout est vert").
    `skipped`/`failure`/`cancelled` comptent tous comme "pas vert" : un job
    saute parce qu'un prerequis (ex. `ci-image-check`) a echoue est un run
    nocturne qui n'a PAS valide la matrice complete.
    """
    return len(job_results) > 0 and all(r == SUCCESS for r in job_results)


def should_alert(
    job_results: Sequence[str], previous_conclusion: Optional[str],
) -> bool:
    """Vrai ssi CE run n'est pas vert ET le run nocturne precedent non plus.

    `previous_conclusion` est None (aucun historique) ou toute valeur
    differente de "success" (echec, annulation, ou timeout) pour un
    precedent non-vert.
    """
    if is_run_green(job_results):
        return False
    return previous_conclusion != SUCCESS


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--job-result", dest="job_results", action="append", default=[],
        metavar="RESULT",
        help="Resultat ('success'/'failure'/'skipped'/'cancelled') d'un job "
             "de CE run — repeter une fois par job surveille.")
    parser.add_argument(
        "--previous-conclusion", dest="previous_conclusion", default=None,
        metavar="CONCLUSION",
        help="Conclusion du run nocturne PRECEDENT deja termine (omis ou "
             "vide si aucun historique).")
    args = parser.parse_args(argv)

    previous = args.previous_conclusion or None
    alerte = should_alert(args.job_results, previous)
    print("true" if alerte else "false")
    return 0


if __name__ == "__main__":
    sys.exit(main())
