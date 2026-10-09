#!/usr/bin/env python3
"""ADEP4 — garde des motifs `.dockerignore` racine-seul.

Semantique .dockerignore : un motif sans `**/` ni `/` initial ne vaut QU'A LA RACINE du
contexte (`__pycache__/` n'exclut pas `apps/foo/__pycache__/`, `*.log` n'exclut pas
`apps/foo/x.log`). Constat C-ADEP-006 : les 199 dossiers __pycache__ du backend sont tous
imbriques, donc tous embarques. Cette garde signale tout motif racine-seul de TOUT
`.dockerignore` versionne, sauf :
  - motif ancre `**/...` ;
  - motif volontairement racine, ecrit `/motif` ;
  - negation `!...` ;
  - ligne de la base decroissante `scripts/exceptions_permanentes.yml (dockerignore_racine)`
    (format `chemin/.dockerignore::motif`, cliquet : une ligne qui ne correspond plus a
    aucun motif racine-seul est elle-meme une erreur — la base ne fait que SE VIDER).

Usage : python scripts/check_dockerignore.py [racine]   (0 vert, 1 rouge)
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import _exceptions_permanentes  # ENF14 — exceptions permanentes signées

ALLOW = 'scripts/exceptions_permanentes.yml'


def motifs_racine_seul(texte: str) -> list[tuple[int, str]]:
    sortie = []
    for i, brut in enumerate(texte.splitlines(), 1):
        m = brut.strip()
        if not m or m.startswith('#') or m.startswith('!'):
            continue
        if m.startswith('**/') or m.startswith('/'):
            continue
        sortie.append((i, m))
    return sortie


def fichiers_dockerignore(racine: Path) -> list[Path]:
    try:
        res = subprocess.run(['git', 'ls-files'], cwd=racine, capture_output=True,
                             text=True, check=True)
        listes = [racine / p for p in res.stdout.splitlines()
                  if p.rsplit('/', 1)[-1] == '.dockerignore']
        if listes:
            return sorted(listes)
    except (OSError, subprocess.CalledProcessError):
        pass
    return sorted(p for p in racine.rglob('.dockerignore') if 'node_modules' not in p.parts)


def lire_allow(racine: Path) -> set[str]:
    return _exceptions_permanentes.charger('dockerignore_racine', racine / ALLOW)


def verifier(racine: Path) -> list[str]:
    allow = lire_allow(racine)
    vus: set[str] = set()
    erreurs: list[str] = []
    for f in fichiers_dockerignore(racine):
        rel = f.relative_to(racine).as_posix()
        for ligne, m in motifs_racine_seul(f.read_text(encoding='utf-8')):
            cle = f'{rel}::{m}'
            vus.add(cle)
            if cle not in allow:
                erreurs.append(f'{rel}:{ligne} : motif racine-seul « {m} » (n\'exclut pas les '
                               f'fichiers imbriques) — ecrivez `**/{m}` ou `/{m}` si la racine '
                               f'est voulue')
    for cle in sorted(allow - vus):
        erreurs.append(f'{ALLOW} : ligne obsolete « {cle} » — retirez-la (la base ne fait que '
                       f'decroitre)')
    return erreurs


def main(argv: list[str]) -> int:
    racine = Path(argv[1]) if len(argv) > 1 else Path(__file__).resolve().parent.parent
    erreurs = verifier(racine)
    for e in erreurs:
        print(f'ECHEC check_dockerignore : {e}')
    if not erreurs:
        print('check_dockerignore : OK')
    return 1 if erreurs else 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
