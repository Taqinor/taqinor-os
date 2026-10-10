#!/usr/bin/env python3
"""ADEV73 - garde de la classe « date du jour calculee en UTC ».

`new Date().toISOString().slice(0, 10)` rend la date UTC : entre minuit et 01 h a Casablanca
elle donne la VEILLE (date d'acceptation, de paiement, de relance fausse d'un jour). La forme
correcte est `todayLocalIso()` de `frontend/src/lib/dateLocale.js`.

Cette garde compte, par fichier de `frontend/src` (hors tests), les occurrences du motif
`toISOString().slice(0, 10)` et exige que chaque fichier reste SOUS son plafond de la liste
figee `scripts/date_jour_utc_allow.txt` (`fichier = N`, jamais un numero de ligne). Un
fichier hors liste qui introduit le motif echoue ; un fichier sous son plafond doit le
baisser (cliquet decroissant : chaque retrait = un correctif chez le proprietaire du site).

Usage : python scripts/check_date_jour_utc.py   (0 vert, 1 rouge)
"""
from __future__ import annotations

import re
import sys
from pathlib import Path
TYPE_DE_CLE = "par_symbole"  # AMET100 — cle de contenu `fichier::symbole` (jamais un numero de ligne)

ROOT = Path(__file__).resolve().parent.parent
ALLOW_REL = "scripts/date_jour_utc_allow.txt"
MOTIF = re.compile(r"toISOString\(\)\s*\.slice\(\s*0\s*,\s*10\s*\)")
SUFFIXES = {".js", ".jsx", ".ts", ".tsx", ".mjs"}


def _est_test(path: Path) -> bool:
    return (".test." in path.name or "__tests__" in path.parts or "tests" in path.parts
            or path.name.endswith((".spec.js", ".spec.ts")))


def compter(racine: Path) -> dict:
    base = racine / "frontend" / "src"
    comptes: dict = {}
    if not base.is_dir():
        return comptes
    for f in sorted(base.rglob("*")):
        if f.suffix not in SUFFIXES or _est_test(f.relative_to(base)):
            continue
        try:
            n = len(MOTIF.findall(f.read_text(encoding="utf-8", errors="replace")))
        except OSError:
            continue
        if n:
            comptes[f.relative_to(racine).as_posix()] = n
    return comptes


def lire_allow(racine: Path) -> dict:
    p = racine / ALLOW_REL
    allow: dict = {}
    if not p.is_file():
        return allow
    for brut in p.read_text(encoding="utf-8").splitlines():
        ligne = brut.strip()
        if ligne and not ligne.startswith("#"):
            rel, _, n = ligne.partition("=")
            allow[rel.strip()] = int(n.strip())
    return allow


def verifier(racine: Path, allow: dict | None = None) -> list:
    allow = lire_allow(racine) if allow is None else allow
    comptes = compter(racine)
    erreurs = []
    for rel, n in sorted(comptes.items()):
        plafond = allow.get(rel, 0)
        if n > plafond:
            erreurs.append(
                f"{rel} : {n} date(s) du jour calculee(s) en UTC (`toISOString().slice(0, 10)`), "
                f"plafond {plafond} - utilisez todayLocalIso() de frontend/src/lib/dateLocale.js")
    for rel, plafond in sorted(allow.items()):
        n = comptes.get(rel, 0)
        if n < plafond:
            erreurs.append(f"{rel} : {n} occurrence(s) restante(s), plafond {plafond} - "
                           f"abaissez scripts/date_jour_utc_allow.txt (cliquet decroissant)")
    return erreurs


def main(argv: list) -> int:
    erreurs = verifier(ROOT)
    for e in erreurs:
        print(f"ECHEC check_date_jour_utc : {e}")
    if not erreurs:
        print("check_date_jour_utc : OK")
    return 1 if erreurs else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
