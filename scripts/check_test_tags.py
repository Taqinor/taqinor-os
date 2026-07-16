#!/usr/bin/env python
"""WOW5 — garde CI : les tests lourds (I/O) DOIVENT porter une étiquette.

Le palier « par-merge » de la CI exclut ``@tag('slow')`` / ``@tag('pdf')`` pour
rester rapide ; ces tests-là tournent dans ``release-verify`` (nightly/manuel).
Sans garde, un nouveau test lourd (weasyprint / matplotlib / boto3-MinIO) non
étiqueté retombe silencieusement dans le gate rapide et le ralentit.

Ce script échoue (exit 1) si un module de test qui importe ``boto3``,
``weasyprint`` ou ``matplotlib`` ne contient AUCUN ``@tag(``. Sans dépendance
(scan texte). Câblé dans le job ``stage-names`` de la CI.

    python scripts/check_test_tags.py
"""
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent / 'backend' / 'django_core'
HEAVY = re.compile(r'^\s*(?:import|from)\s+(?:boto3|weasyprint|matplotlib)\b',
                   re.MULTILINE)
HAS_TAG = re.compile(r'@tag\(')


def is_test_file(p: pathlib.Path) -> bool:
    name = p.name
    return (name.startswith('test') and name.endswith('.py')) or (
        p.parent.name == 'tests' and name.endswith('.py')
        and name != '__init__.py')


def main() -> int:
    offenders = []
    for p in ROOT.rglob('*.py'):
        if 'migrations' in p.parts or not is_test_file(p):
            continue
        try:
            src = p.read_text(encoding='utf-8')
        except Exception:  # noqa: BLE001
            continue
        if HEAVY.search(src) and not HAS_TAG.search(src):
            offenders.append(p.relative_to(ROOT))
    if offenders:
        print('check_test_tags: modules de test LOURDS sans @tag('
              "'slow'/'pdf') — ils tourneraient dans le gate rapide :")
        for o in offenders:
            print(f'  - {o}')
        print("Ajoute `from django.test import tag` + `@tag('slow')` "
              "(ou 'pdf') sur les classes concernées.")
        return 1
    print('check_test_tags: OK — tous les tests lourds sont étiquetés.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
