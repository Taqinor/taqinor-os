#!/usr/bin/env python3
"""Repare le mojibake (UTF-8 relu comme cp1252) d'un fichier texte, LIGNE PAR LIGNE (ACAL334).

    python scripts/reparer_mojibake.py            # repare docs/GUIDE_UTILISATEUR_ERP.md
    python scripts/reparer_mojibake.py --check    # lecture seule : exit 1 s'il reste du mojibake
    python scripts/reparer_mojibake.py chemin.md  # autre fichier

Regle deterministe : pour chaque ligne, si
`ligne.encode('cp1252', repli latin-1 pour 0x81/0x8D/0x8F/0x90/0x9D).decode('utf-8')`
reussit ET differe de la ligne, la ligne est remplacee ; sinon elle est laissee
telle quelle (octet-identique) et, si elle porte encore un marqueur de mojibake,
listee. Les fins de ligne (LF/CRLF) sont conservees.
"""
import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAUT = ROOT / "docs" / "GUIDE_UTILISATEUR_ERP.md"

# Marqueurs de mojibake : A-tilde, a-circonflexe + euro (guillemets/tirets cp1252),
# A-circonflexe isole (reste de l'octet 0xC2 devant un caractere latin-1).
MARQUEUR = re.compile("Ã|â€|Â")


def reparer_ligne(ligne):
    """Retourne la ligne reparee, ou None si elle n'est pas reparable (ou deja saine)."""
    if ligne.startswith("﻿"):  # BOM UTF-8 correct en tete de fichier : conserve
        corrigee = reparer_ligne(ligne[1:])
        return None if corrigee is None else "﻿" + corrigee
    octets = bytearray()
    for car in ligne:
        try:
            octets += car.encode("cp1252")
        except UnicodeEncodeError:
            if ord(car) > 0xFF:
                return None
            octets.append(ord(car))  # repli latin-1 (0x81/0x8D/0x8F/0x90/0x9D)
    try:
        corrigee = bytes(octets).decode("utf-8")
    except UnicodeDecodeError:
        return None
    return corrigee if corrigee != ligne else None


def a_du_mojibake(ligne):
    return bool(MARQUEUR.search(ligne))


def separer(lignes_brutes):
    """(texte sans fin de ligne, fin de ligne) pour chaque ligne brute."""
    sortie = []
    for brut in lignes_brutes:
        fin = "\r\n" if brut.endswith("\r\n") else ("\n" if brut.endswith("\n") else "")
        sortie.append((brut[:len(brut) - len(fin)], fin))
    return sortie


def traiter(contenu):
    """Retourne (nouveau contenu, nb de lignes reparees, [(no, ligne) laissees avec marqueur])."""
    texte = contenu.decode("utf-8")
    morceaux = []
    reparees = 0
    laissees = []
    # split sur \n seul : splitlines() couperait aussi sur U+2028/U+0085 etc.
    brutes = texte.split("\n")
    brutes = [b + "\n" for b in brutes[:-1]] + ([brutes[-1]] if brutes[-1] else [])
    for no, (ligne, fin) in enumerate(separer(brutes), start=1):
        nouvelle = reparer_ligne(ligne) if a_du_mojibake(ligne) else None
        if nouvelle is not None:
            ligne = nouvelle
            reparees += 1
        elif a_du_mojibake(ligne):
            laissees.append((no, ligne))
        morceaux.append(ligne + fin)
    return "".join(morceaux).encode("utf-8"), reparees, laissees


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    p.add_argument("fichier", nargs="?", default=str(DEFAUT))
    p.add_argument("--check", action="store_true",
                   help="lecture seule : exit 1 si une ligne est en mojibake")
    args = p.parse_args(argv)
    chemin = Path(args.fichier)
    contenu = chemin.read_bytes()
    nouveau, reparees, laissees = traiter(contenu)
    if args.check:
        restantes = reparees + len(laissees)
        print(f"{chemin}: {restantes} ligne(s) en mojibake "
              f"({reparees} reparables, {len(laissees)} irreductibles)")
        for no, ligne in laissees:
            print(f"  irreductible l.{no}: {ascii(ligne[:120])}")
        return 1 if restantes else 0
    if nouveau != contenu:
        chemin.write_bytes(nouveau)
    print(f"{chemin}: {reparees} ligne(s) reparee(s), {len(laissees)} laissee(s) avec marqueur")
    for no, ligne in laissees:
        print(f"  laissee l.{no}: {ascii(ligne[:120])}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
