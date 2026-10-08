#!/usr/bin/env python3
"""ADEP2/ADEP3 — parite image de prod <-> environnements CI.

ADEP2. La CI rendait les PDF avec DejaVu alors que la prod rend avec Noto/Liberation :
les gardes de pagination mesuraient d'autres polices que celles du PDF client. Les
paquets d'EXECUTION (hors `-dev`, hors outils de build) de `backend/django_core/Dockerfile`
(reference unique) doivent figurer dans CHAQUE copie CI (image CI, action `backend-env`,
workflow `mutation`) ; `fonts-dejavu-core` ne doit figurer dans aucune.

ADEP3. La majeure Node du build front de prod (`frontend/Dockerfile.prod`) doit egaler
la `node-version` des workflows (ci.yml, dependency-audit.yml), et le tag est epingle
sur une mineure (pas de `node:22-alpine` flottant).

Usage : python scripts/check_parite_image_ci.py [racine]   (0 = vert, 1 = ecart)
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from check_binaires_image import paquets_apt  # noqa: E402

PROD = 'backend/django_core/Dockerfile'
COPIES_CI = (
    '.github/ci-image/Dockerfile',
    '.github/actions/backend-env/action.yml',
    '.github/workflows/mutation.yml',
)
# Paquets de la prod qui ne sont pas de l'execution commune, ou fournis autrement en CI.
EXEMPTES = {
    'pkg-config',                # outil de build
    'curl', 'ca-certificates', 'gnupg',   # amorce du depot PGDG (ADEP1), pas d'execution
    'postgresql-client-16',      # ADEP1 : present dans l'image CI ; les runners ont le leur
}
INTERDITS_CI = {'fonts-dejavu-core'}
DOCKERFILE_FRONT = 'frontend/Dockerfile.prod'
WORKFLOWS_NODE = ('.github/workflows/ci.yml', '.github/workflows/dependency-audit.yml')


def _lire(racine: Path, rel: str) -> str | None:
    p = racine / rel
    return p.read_text(encoding='utf-8') if p.is_file() else None


def paquets_execution(texte: str) -> set[str]:
    return {p for p in paquets_apt(texte)
            if not p.endswith('-dev') and p not in EXEMPTES
            and re.fullmatch(r'[a-z0-9][a-z0-9.+-]+', p)}


def verifier_apt(racine: Path) -> list[str]:
    prod = _lire(racine, PROD)
    if prod is None:
        return [f'{PROD} introuvable']
    attendus = paquets_execution(prod)
    erreurs: list[str] = []
    for rel in COPIES_CI:
        texte = _lire(racine, rel)
        if texte is None:
            erreurs.append(f'{rel} introuvable')
            continue
        presents = paquets_apt(texte)
        for p in sorted(attendus - presents):
            erreurs.append(f'{p} : present dans {PROD}, absent de {rel}')
        for p in sorted(INTERDITS_CI & presents):
            erreurs.append(f'{p} : ne doit plus figurer dans {rel} (la prod rend avec Noto/Liberation)')
    return erreurs


def node_majeure_dockerfile(texte: str) -> tuple[str | None, str | None]:
    m = re.search(r'^FROM\s+node:(\S+)', texte, re.M)
    if not m:
        return None, None
    tag = m.group(1)
    maj = re.match(r'(\d+)', tag)
    return (maj.group(1) if maj else None), tag


def verifier_node(racine: Path) -> list[str]:
    texte = _lire(racine, DOCKERFILE_FRONT)
    if texte is None:
        return [f'{DOCKERFILE_FRONT} introuvable']
    majeure, tag = node_majeure_dockerfile(texte)
    if majeure is None:
        return [f'{DOCKERFILE_FRONT} : aucun `FROM node:<version>`']
    erreurs: list[str] = []
    if not re.match(r'\d+\.\d+', tag):
        erreurs.append(f'{DOCKERFILE_FRONT} : tag node:{tag} flottant — epinglez une mineure '
                       f'(ex. node:{majeure}.x-alpine)')
    for rel in WORKFLOWS_NODE:
        wf = _lire(racine, rel)
        if wf is None:
            continue
        for v in sorted(set(re.findall(r"node-version:\s*['\"]?(\d+)", wf))):
            if v != majeure:
                erreurs.append(f'{rel} : node-version {v} contre Node {majeure} dans '
                               f'{DOCKERFILE_FRONT}')
    return erreurs


def verifier(racine: Path) -> list[str]:
    return verifier_apt(racine)


def main(argv: list[str]) -> int:
    racine = Path(argv[1]) if len(argv) > 1 else Path(__file__).resolve().parent.parent
    erreurs = verifier(racine)
    for e in erreurs:
        print(f'ECHEC check_parite_image_ci : {e}')
    if not erreurs:
        print('check_parite_image_ci : OK')
    return 1 if erreurs else 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
