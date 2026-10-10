#!/usr/bin/env python3
"""APDF51 — garde « aucun @font-face au nom d'une police systeme de l'image ».

Constat C-APDF-002 : des `@font-face` vendorises portaient le nom d'une police deja
installee dans l'image de prod (« Noto Sans Arabic »). WeasyPrint ne retombait alors
plus sur la police systeme, qui couvre tout le bloc arabe : lettres manquantes.

Les familles systeme viennent des paquets `fonts-*` du `backend/django_core/Dockerfile`
(`fonts-liberation` -> « Liberation », `fonts-noto-core` -> « Noto ») ; « DejaVu » est
ajoute car fontconfig-config tire `fonts-dejavu-core`. Un `@font-face` dont le
`font-family` commence par l'un de ces noms, dans un `.py` ou `.html` du backend, est rouge.

Usage : python scripts/check_pdf_polices.py [racine_depot]
Sortie 0 = vert ; 1 = au moins un homonyme (chemin:ligne, en francais).
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

DOCKERFILE = 'backend/django_core/Dockerfile'
RACINE_CODE = 'backend/django_core'
FAMILLES_TRANSITIVES = ('DejaVu',)
_FONT_FACE = re.compile(r'@font-face\s*\{+([^}]*)', re.IGNORECASE)
_FAMILLE = re.compile(r'font-family\s*:\s*\\?["\']?\s*([^;"\'}\\]+)', re.IGNORECASE)
_PAQUET_POLICE = re.compile(r'\bfonts-([a-z0-9]+)(?:-[a-z0-9-]+)?\b')


def familles_systeme(dockerfile_text: str) -> list[str]:
    """Prefixes de familles deduits des paquets `fonts-*` du Dockerfile."""
    texte = dockerfile_text.replace('\\\n', ' ')
    noms = {m.group(1).capitalize() for m in _PAQUET_POLICE.finditer(texte)}
    return sorted(noms | set(FAMILLES_TRANSITIVES))


def homonymes(source: str, familles: list[str]) -> list[tuple[int, str]]:
    """(ligne, famille) de chaque `@font-face` dont la famille porte un nom systeme."""
    trouves = []
    for bloc in _FONT_FACE.finditer(source):
        m = _FAMILLE.search(bloc.group(1))
        if not m:
            continue
        famille = m.group(1).strip()
        if any(famille.lower().startswith(f.lower()) for f in familles):
            trouves.append((source.count('\n', 0, bloc.start()) + 1, famille))
    return trouves


def verifier(racine: Path) -> list[str]:
    dockerfile = racine / DOCKERFILE
    if not dockerfile.is_file():
        return [f'{DOCKERFILE} introuvable : impossible de deduire les polices systeme.']
    familles = familles_systeme(dockerfile.read_text(encoding='utf-8'))
    erreurs = []
    for chemin in sorted((racine / RACINE_CODE).rglob('*')):
        if chemin.suffix not in ('.py', '.html') or not chemin.is_file():
            continue
        texte = chemin.read_text(encoding='utf-8', errors='replace')
        for ligne, famille in homonymes(texte, familles):
            erreurs.append(
                f'{chemin.relative_to(racine).as_posix()}:{ligne} : @font-face « {famille} » '
                "homonyme d'une police systeme de l'image (WeasyPrint ne retombe plus "
                'dessus) — retirez la declaration et laissez la police systeme.')
    return erreurs


def main(argv: list[str]) -> int:
    racine = Path(argv[1]) if len(argv) > 1 else Path(__file__).resolve().parent.parent
    erreurs = verifier(racine)
    for e in erreurs:
        print(e)
    if erreurs:
        print(f'{len(erreurs)} @font-face homonyme(s) de police systeme (APDF51).')
        return 1
    print("Aucun @font-face homonyme d'une police systeme (APDF51).")
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
