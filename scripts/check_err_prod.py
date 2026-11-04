#!/usr/bin/env python3
"""Garde du format des lignes `ERR-PROD-*` de docs/ERROR_PLAN.md (BPQ13).

Les lignes `ERR-PROD-<MODULE>-<SLUG>` sont deposees par le skill `problemes-prod`
(tri quotidien des problemes vecus). Une ligne refusee ici :
  1. id hors `[A-Z0-9-]+` ;
  2. pas de `Signature:` (cle de dedoublonnage du tri) ;
  3. pas de mention « test rouge » dans le module existant ;
  4. cite un fichier `test_err_*.py` (un fichier de test par erreur est interdit :
     le test rouge va dans le module de test existant).
Pur stdlib ; code 1 au moindre ecart, messages en francais.

    python scripts/check_err_prod.py [fichier]
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PLAN = ROOT / "docs" / "ERROR_PLAN.md"

LIGNE = re.compile(r"^\s*- \[[ xX]\]\s+(ERR-PROD[^\s:—–]*)")
ID_VALIDE = re.compile(r"[A-Z0-9-]+")
SIGNATURE = re.compile(r"Signature\s*:")
TEST_ROUGE = re.compile(r"test rouge[^.\n]*module (?:de test )?existant", re.I)
FICHIER_PAR_ERREUR = re.compile(r"\btest_err_[\w]*\.py")


def verifier(texte: str) -> list[str]:
    """Retourne la liste des erreurs (vide = conforme)."""
    erreurs = []
    for n, ligne in enumerate(texte.splitlines(), 1):
        m = LIGNE.match(ligne)
        if not m:
            continue
        ident = m.group(1)
        if not ID_VALIDE.fullmatch(ident):
            erreurs.append(f"ligne {n} : id « {ident} » hors [A-Z0-9-]+")
        if not SIGNATURE.search(ligne):
            erreurs.append(f"ligne {n} ({ident}) : « Signature: » manquante")
        if not TEST_ROUGE.search(ligne):
            erreurs.append(f"ligne {n} ({ident}) : « test rouge dans le module existant » manquant")
        if FICHIER_PAR_ERREUR.search(ligne):
            erreurs.append(f"ligne {n} ({ident}) : fichier test_err_*.py interdit "
                           "(le test rouge va dans le module existant)")
    return erreurs


def main(argv: list[str]) -> int:
    chemin = Path(argv[1]) if len(argv) > 1 else PLAN
    erreurs = verifier(chemin.read_text(encoding="utf-8"))
    for e in erreurs:
        print(f"ERR-PROD : {e}")
    if erreurs:
        return 1
    print("check_err_prod : OK")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
