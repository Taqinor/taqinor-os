#!/usr/bin/env python3
"""ADEP1 — garde « binaire appele en sous-processus => paquet dans l'image de prod ».

Constat C-ADEP-005 : l'image `backend/django_core/Dockerfile` n'avait pas de client
PostgreSQL ; `core.backup.dump_database` appelait `pg_dump` -> 92 sauvegardes sur 92 en
echec (« No such file or directory: 'pg_dump' »). Cette garde releve, dans le code
backend (hors tests), les binaires nommes par un litteral dans un fichier qui importe
`subprocess`/`shutil`, et exige que le paquet apt correspondant figure dans le
Dockerfile de prod.

Table binaire -> paquet : `BINAIRES`. Un binaire livre par une dependance transitive
d'un paquet deja installe y figure avec des paquets acceptes (ex. fc-match, fourni par
fontconfig, tire par libpango/libcairo) ; un binaire inconnu passe par
`subprocess.*([literal, ...])` => rouge « ajoutez-le a la table ».

Usage : python scripts/check_binaires_image.py [racine_depot]
Sortie 0 = vert ; 1 = au moins un binaire sans paquet (messages en francais).
"""
from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

# binaire -> paquets apt dont UN SEUL suffit (le premier est celui a ajouter)
BINAIRES = {
    'pg_dump': ('postgresql-client-16',),
    'pg_restore': ('postgresql-client-16',),
    'psql': ('postgresql-client-16',),
    'createdb': ('postgresql-client-16',),
    'dropdb': ('postgresql-client-16',),
    # fontconfig est tire par libpango/libcairo (dependance, pas ligne apt propre)
    'fc-match': ('fontconfig', 'libpangocairo-1.0-0', 'libcairo2', 'libpango-1.0-0'),
}
# Executables toujours presents (interpreteur, shell de base) : jamais a lister.
TOUJOURS_PRESENTS = {'python', 'python3', 'sh', 'bash', 'git'}
DOCKERFILE = 'backend/django_core/Dockerfile'
RACINES_CODE = ('backend/django_core', 'backend/fastapi_ia')
_APPELS_SOUS_PROCESSUS = {'run', 'Popen', 'check_output', 'check_call', 'call'}


def paquets_apt(dockerfile_text: str) -> set[str]:
    """Paquets cites dans les `apt-get install` du Dockerfile (continuations incluses)."""
    texte = dockerfile_text.replace('\\\n', ' ')
    paquets: set[str] = set()
    for m in re.finditer(r'apt-get\s+install\b([^\n;&|]*)', texte):
        for tok in m.group(1).split():
            if not tok.startswith('-'):
                paquets.add(tok)
    return paquets


def _litteral(noeud):
    if isinstance(noeud, ast.Constant) and isinstance(noeud.value, str):
        return noeud.value
    return None


def binaires_utilises(source: str) -> dict[str, int]:
    """binaire -> ligne. Retient : litteraux de la table, premier element litteral d'une
    liste passee a subprocess.*, premier argument litteral de shutil.which."""
    try:
        arbre = ast.parse(source)
    except SyntaxError:
        return {}
    importe = any(
        (isinstance(n, ast.Import)
         and any(a.name.split('.')[0] in ('subprocess', 'shutil') for a in n.names))
        or (isinstance(n, ast.ImportFrom)
            and (n.module or '').split('.')[0] in ('subprocess', 'shutil'))
        for n in ast.walk(arbre))
    if not importe:
        return {}
    trouves: dict[str, int] = {}
    for n in ast.walk(arbre):
        valeur = _litteral(n)
        if valeur in BINAIRES:
            trouves.setdefault(valeur, n.lineno)
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute):
            nom = n.func.attr
            premier = n.args[0] if n.args else None
            if (nom in _APPELS_SOUS_PROCESSUS and isinstance(premier, (ast.List, ast.Tuple))
                    and premier.elts):
                v = _litteral(premier.elts[0])
                if v and v not in TOUJOURS_PRESENTS:
                    trouves.setdefault(v, n.lineno)
            if nom == 'which' and premier is not None:
                v = _litteral(premier)
                if v and v not in TOUJOURS_PRESENTS:
                    trouves.setdefault(v, n.lineno)
    return trouves


def verifier(racine: Path) -> list[str]:
    dockerfile = racine / DOCKERFILE
    if not dockerfile.is_file():
        return [f'{DOCKERFILE} introuvable']
    paquets = paquets_apt(dockerfile.read_text(encoding='utf-8'))
    erreurs: list[str] = []
    manquants: dict[str, list[str]] = {}
    for rel in RACINES_CODE:
        base = racine / rel
        if not base.is_dir():
            continue
        for fichier in sorted(base.rglob('*.py')):
            parts = fichier.relative_to(racine).parts
            if (any(p in ('tests', 'migrations', 'parked') for p in parts)
                    or fichier.name.startswith('test_')):
                continue
            try:
                source = fichier.read_text(encoding='utf-8')
            except OSError:
                continue
            for binaire, ligne in binaires_utilises(source).items():
                chemin = f'{fichier.relative_to(racine).as_posix()}:{ligne}'
                if binaire not in BINAIRES:
                    erreurs.append(f'{chemin} : binaire « {binaire} » appele en sous-processus '
                                   f'mais absent de la table BINAIRES de la garde '
                                   f'(ajoutez binaire -> paquet apt).')
                    continue
                if not (set(BINAIRES[binaire]) & paquets):
                    manquants.setdefault(BINAIRES[binaire][0], []).append(binaire)
    for paquet, binaires in sorted(manquants.items()):
        erreurs.append(f'{", ".join(sorted(set(binaires)))} : paquet {paquet} absent de '
                       f'{DOCKERFILE}')
    return erreurs


def main(argv: list[str]) -> int:
    racine = Path(argv[1]) if len(argv) > 1 else Path(__file__).resolve().parent.parent
    erreurs = verifier(racine)
    for e in erreurs:
        print(f'ECHEC check_binaires_image : {e}')
    if not erreurs:
        print('check_binaires_image : OK (chaque binaire de sous-processus a son paquet)')
    return 1 if erreurs else 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
