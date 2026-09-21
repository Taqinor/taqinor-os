#!/usr/bin/env python
"""SOLMVP2 — enveloppe HÔTE de ``manage.py parquer_app`` (+ vérificateur).

L'hôte (Windows) n'a PAS de Django : la commande de parcage tourne dans l'image
docker de prod. Ce script ne fait donc que deux choses, sans aucune dépendance
(Python pur, ni Django ni docker requis pour ``--verifier``) :

* ``--commande <label> [--dry-run]`` — imprime le one-off docker EXACT à lancer
  depuis la racine du dépôt (recette unique, pour qu'aucune lane SOLMVP30-36 ne
  la réinvente) ;
* ``--verifier <label…>`` / ``--verifier-tout`` — vérifie SUR L'HÔTE qu'un
  dossier d'app est bien une COQUILLE au sens de
  ``core/tests/test_parked_registry.py`` (seuls ``__init__.py``, ``apps.py``,
  ``models.py`` vide et ``migrations/``), + ``parked = True`` dans ``apps.py``.
  Sort 1 si une app parquée n'est pas conforme : c'est la preuve qu'une lane
  peut montrer sans ouvrir docker.

Usage ::

    python scripts/parquer_app.py --commande statuspage --dry-run
    python scripts/parquer_app.py --verifier statuspage ged
    python scripts/parquer_app.py --verifier-tout

La liste des labels vient du registre UNIQUE ``backend/django_core/core/
parked.py`` (lu par chemin : il est en Python pur, sans import Django).
"""
from __future__ import annotations

import argparse
import ast
import importlib.util
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
DJANGO_CORE = RACINE / 'backend' / 'django_core'
APPS_DIR = DJANGO_CORE / 'apps'
CONTENU_COQUILLE = {'__init__.py', 'apps.py', 'models.py', 'migrations',
                    '__pycache__'}

# Le one-off docker : MÊME image/réseau/env que le harnais de test local.
COMMANDE_DOCKER = r"""export MSYS_NO_PATHCONV=1
docker run --rm --network erp-agentique_default \
  -v "$PWD/backend/django_core:/app" -v "$PWD/STAGES.py:/opt/STAGES.py" \
  -e DJANGO_SETTINGS_MODULE=erp_agentique.settings.dev \
  -e DJANGO_SECRET_KEY=ci -e DJANGO_DEBUG=True \
  -e DB_HOST=db -e DB_PORT=5432 -e DB_NAME=erp_db -e DB_USER=erp_user \
  -e DB_PASSWORD=local-dev-pg-Vq7mK2xT9rW4 \
  -e REDIS_HOST=redis -e REDIS_PORT=6379 \
  -e MINIO_ENDPOINT=minio:9000 -e MINIO_ROOT_USER=erp_admin \
  -e MINIO_ROOT_PASSWORD=local-dev-minio-Hs3pL8nB6cQ1 \
  -e MINIO_ACCESS_KEY=erp_admin -e MINIO_SECRET_KEY=local-dev-minio-Hs3pL8nB6cQ1 \
  -e MINIO_BUCKET_PDF=erp-pdf -e MINIO_BUCKET_UPLOADS=erp-uploads \
  erp-agentique-django_core python manage.py parquer_app {label}{options}"""


def registre():
    """Charge ``core/parked.py`` par CHEMIN (aucun import Django)."""
    chemin = DJANGO_CORE / 'core' / 'parked.py'
    spec = importlib.util.spec_from_file_location('_parked_solmvp', chemin)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def models_py_vide(chemin: Path) -> bool:
    corps = ast.parse(chemin.read_text(encoding='utf-8')).body
    return not corps or (
        len(corps) == 1 and isinstance(corps[0], ast.Expr)
        and isinstance(corps[0].value, ast.Constant)
        and isinstance(corps[0].value.value, str))


def verifier(label: str):
    """Renvoie la liste des écarts au contrat de coquille (vide = conforme)."""
    dossier = APPS_DIR / label
    if not dossier.is_dir():
        return ['dossier absent de backend/django_core/apps/']
    ecarts = []
    extra = sorted(p.name for p in dossier.iterdir()
                   if p.name not in CONTENU_COQUILLE)
    if extra:
        ecarts.append('fichiers interdits : %s' % ', '.join(extra))
    for attendu in ('__init__.py', 'apps.py', 'models.py'):
        if not (dossier / attendu).is_file():
            ecarts.append('%s manquant' % attendu)
    if not (dossier / 'migrations').is_dir():
        ecarts.append('migrations/ doit être conservé verbatim')
    modeles = dossier / 'models.py'
    if modeles.is_file() and not models_py_vide(modeles):
        ecarts.append('models.py non vide (docstring seul toléré)')
    apps_py = dossier / 'apps.py'
    if apps_py.is_file():
        source = apps_py.read_text(encoding='utf-8')
        if 'parked = True' not in source:
            ecarts.append("apps.py sans `parked = True`")
        if "'parked': True" not in source:
            ecarts.append("manifeste sans `'parked': True`")
        if 'def ready(' in source:
            ecarts.append('apps.py garde un ready() (imports supprimés)')
    return ecarts


def main(argv=None) -> int:
    analyseur = argparse.ArgumentParser(
        description='Enveloppe hôte de manage.py parquer_app (SOLMVP2).')
    analyseur.add_argument('--commande', metavar='LABEL',
                           help='imprime le one-off docker pour ce label')
    analyseur.add_argument('--dry-run', action='store_true',
                           help='avec --commande : ajoute --dry-run')
    analyseur.add_argument('--verifier', nargs='+', metavar='LABEL',
                           help='vérifie que ces apps sont des coquilles')
    analyseur.add_argument('--verifier-tout', action='store_true',
                           help='vérifie les 49 labels de APPS_PARQUEES')
    args = analyseur.parse_args(argv)
    parked = registre()

    if args.commande:
        if not parked.est_parquee(args.commande):
            print('%s n\'est pas dans APPS_PARQUEES (core/parked.py) : '
                  'seules les apps parquées se coquillent.' % args.commande)
            return 1
        print(COMMANDE_DOCKER.format(
            label=args.commande,
            options=' --dry-run' if args.dry_run else ''))
        print('\n# Puis, sur l\'hôte, la preuve du résultat :')
        print('#   python scripts/parquer_app.py --verifier %s'
              % args.commande)
        return 0

    labels = list(args.verifier or [])
    if args.verifier_tout:
        labels = list(parked.APPS_PARQUEES)
    if not labels:
        analyseur.print_help()
        return 1

    fautifs = {}
    for label in labels:
        ecarts = verifier(label)
        if ecarts:
            fautifs[label] = ecarts
    if fautifs:
        print('parquer_app --verifier : %d app(s) NON conforme(s) au contrat '
              'de coquille :' % len(fautifs))
        for label, ecarts in sorted(fautifs.items()):
            print('  - %s : %s' % (label, ' ; '.join(ecarts)))
        print('\nContrat : __init__.py + apps.py (parked=True) + models.py vide '
              '+ migrations/ — docs/parked-modules.md §2.')
        return 1
    print('parquer_app --verifier : OK — %d app(s) conforme(s) au contrat de '
          'coquille.' % len(labels))
    return 0


if __name__ == '__main__':
    sys.exit(main())
