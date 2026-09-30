#!/usr/bin/env python3
"""Garde CI : aucun instantané anonymisé de production n'est suivi par git.

`manage.py qa_export_anonymise` produit un fichier CONFIDENTIEL (montants réels,
prix d'achat, études) qui ne doit JAMAIS entrer dans le dépôt : `.gitignore`
ignore `var/anon/` et `*.anon.json.gz`, mais un `git add -f` passerait outre.
Cette garde échoue si `git ls-files` liste un tel fichier.

Usage : python scripts/check_no_anon_snapshot.py   (0 = propre, 1 = fichier suivi)
"""
from __future__ import annotations

import subprocess
import sys


def offending(paths):
    """Chemins suivis qui ressemblent à un instantané anonymisé."""
    bad = []
    for p in paths:
        norm = p.replace('\\', '/')
        if norm.endswith('.anon.json.gz') or norm.startswith('var/anon/') \
                or '/var/anon/' in norm:
            bad.append(norm)
    return bad


def main():
    try:
        out = subprocess.run(['git', 'ls-files', '-z'], check=True,
                             capture_output=True).stdout
    except (OSError, subprocess.CalledProcessError) as exc:
        print(f'check_no_anon_snapshot : git ls-files impossible ({exc})')
        return 1
    paths = [p for p in out.decode('utf-8', 'replace').split('\0') if p]
    bad = offending(paths)
    if bad:
        print('ECHEC : instantane(s) anonymise(s) suivi(s) par git -- '
              'CONFIDENTIEL, a retirer (git rm --cached) :')
        for p in bad:
            print(f'  {p}')
        return 1
    print(f'OK : aucun instantane anonymise suivi ({len(paths)} fichiers vus).')
    return 0


if __name__ == '__main__':
    sys.exit(main())
