#!/usr/bin/env python3
"""ADEP14 - verifie la SORTIE de `python -m unittest` : un test saute ou un
nombre de tests executes sous le plancher est un echec.

POURQUOI. `python -m unittest tests.test_margin_guard` rend `Ran 8 tests ... OK
(skipped=8)` et exit 0 quand une dependance d'`app.*` manque ou qu'un import
casse : la garde de marge `prix_achat` « passe » sans avoir tourne. Le job
nightly `fastapi-tests` (release-verify.yml) pipe donc la sortie ici :

    python -m unittest discover -s tests -v 2>&1 \\
        | python ../../scripts/verifier_sortie_unittest.py --plancher 218

La sortie est recopiee telle quelle sur stdout (le journal du job reste
complet), puis le verdict :

  * pas de ligne `Ran N tests`           -> echec (la suite n'a pas tourne) ;
  * `FAILED (...)`                        -> echec ;
  * `skipped=K` avec K > 0                -> echec « K tests sautes » ;
  * N < `--plancher`                      -> echec (le plancher ne fait que monter).

Usage : <sortie unittest> | python scripts/verifier_sortie_unittest.py [--plancher N]
Code de sortie : 0 si saine, 1 sinon.
"""
from __future__ import annotations

import argparse
import re
import sys

RE_RAN = re.compile(r"^Ran (\d+) tests? in ", re.M)
RE_SKIPPED = re.compile(r"skipped=(\d+)")
RE_FAILED = re.compile(r"^FAILED \(", re.M)


def analyser(sortie: str, plancher: int = 0) -> list:
    """Liste des raisons d'echec (vide = sortie saine)."""
    raisons = []
    ran = RE_RAN.search(sortie)
    if not ran:
        return ["aucune ligne « Ran N tests » : la suite n'a pas tourne"]
    executes = int(ran.group(1))
    if RE_FAILED.search(sortie):
        raisons.append("la suite est FAILED")
    sautes = sum(int(n) for n in RE_SKIPPED.findall(sortie.split(ran.group(0), 1)[1]))
    if sautes:
        raisons.append(f"{sautes} tests sautés (skipped={sautes}) : une dépendance "
                       "ou un import manque, la garde n'a pas tourné")
    if executes < plancher:
        raisons.append(f"{executes} tests exécutés, sous le plancher {plancher}")
    return raisons


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--plancher", type=int, default=0,
                    help="nombre minimal de tests executes (ne fait que monter)")
    args = ap.parse_args(argv)
    try:
        sys.stdin.reconfigure(encoding="utf-8", errors="replace")
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    sortie = sys.stdin.read()
    sys.stdout.write(sortie)
    raisons = analyser(sortie, args.plancher)
    if raisons:
        print("\nverifier_sortie_unittest: ECHEC")
        for raison in raisons:
            print("  - " + raison)
        return 1
    print("\nverifier_sortie_unittest: OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
