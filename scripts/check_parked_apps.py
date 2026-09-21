#!/usr/bin/env python
"""SOLMVP53 — garde CI permanente : plus AUCUNE référence vers une app parquée.

Décision fondateur du 20/09/2026 : 47 apps sortent PHYSIQUEMENT du MVP solaire
(« fully out » : pas de toggle, le code et les tests PARTENT). Leur dossier
``backend/django_core/apps/<label>/`` est réduit à une COQUILLE de migrations
(``docs/parked-modules.md`` §2) et leur source vit, hors PYTHONPATH, sous
``backend/parked/`` (backend) et ``frontend/parked/`` (frontend).

Une coquille n'expose plus rien : le moindre import, la moindre FK par chaîne,
le moindre include d'urls ou la moindre tâche beat qui vise encore un de ces
labels casse le boot ou, pire, passe silencieusement en produisant un écran
mort. Cette garde est le cliquet permanent qui l'empêche de revenir. Elle est
branchée dans le job ``stage-names`` de ``.github/workflows/ci.yml``, à côté de
``check_stages.py`` : stdlib pure, ni base ni Django ni dépendance.

Les 5 règles (toutes en français, chaque échec nommant ``fichier:ligne``)
---------------------------------------------------------------------------
a. **Import / FK / get_model** — un ``.py`` de ``backend/django_core`` qui
   ``from apps.<label> import …`` / ``import apps.<label>`` (import de fonction
   inclus : l'analyse est un ``ast.walk``), qui écrit une FK par chaîne
   ``'<label>.Modele'`` dans un ``models*.py``, ou qui appelle
   ``get_model('<label>', …)`` / ``get_model('<label>.Modele')``.
b. **urls** — ``erp_agentique/urls.py`` qui inclut ``apps.<label>.urls``.
c. **Celery** — ``erp_agentique/celery.py`` (``beat_schedule``) ou les réglages
   ``CELERY_TASK_ROUTES`` / ``ENUM_NAME_OVERRIDES`` de ``settings/base.py`` qui
   nomment ``apps.<label>.`` ou une tâche ``<label>.…``. NB : ``INSTALLED_APPS``
   garde volontairement ``'apps.<label>'`` (sans point final) — c'est le contrat
   de coquille, jamais une violation.
d. **Frontend** — un fichier de ``frontend/src`` qui importe depuis
   ``frontend/parked`` / ``../parked`` (le code parqué est hors build).
e. **Contrat de coquille** — un dossier d'app parquée qui n'est plus une
   coquille. La règle n'est PAS redéclarée ici : la fonction
   ``scripts/parquer_app.py:verifier`` est importée telle quelle (source
   UNIQUE, zéro dérive).

Ce qui est EXEMPT, et pourquoi
------------------------------
``*/migrations/*`` (gelées verbatim, c'est ce qui garde le graphe valide), le
dossier propre à chaque app parquée, ``backend/parked/`` et
``frontend/parked/`` (les miroirs), ``core/parked.py`` (le registre UNIQUE des
labels) et l'outillage de parcage avec ses tests. Les **commentaires et
docstrings ne comptent jamais** : le dépôt documente abondamment ce qui a été
retiré (``# … importe apps.marketing.models``, ``apps.get_model('rh', …)`` dans
un docstring de test) et une garde qui lirait ces phrases serait rouge à vie.
Les ``.py`` sont donc lus par ``ast`` (aucun commentaire n'y survit, et les
littéraux-instruction sont ignorés), les ``.js``/``.jsx`` par un décapeur de
commentaires qui respecte les chaînes, avant de n'accepter que de VRAIES
instructions ``import``/``from``/``require``.

Usage ::

    python scripts/check_parked_apps.py            # depuis la racine du dépôt
    python scripts/check_parked_apps.py --racine /autre/copie
"""
from __future__ import annotations

import argparse
import ast
import fnmatch
import importlib.util
import re
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent

# Fichiers exemptés, en chemin POSIX relatif à la racine : le registre lui-même
# et l'outillage de parcage (ils PARLENT des labels, c'est leur métier).
FICHIERS_EXEMPTS = frozenset({
    'backend/django_core/core/parked.py',
    'backend/django_core/core/management/commands/parquer_app.py',
    'backend/django_core/core/tests/test_parked_registry.py',
    'backend/django_core/core/tests/test_parquer_app.py',
    'scripts/parquer_app.py',
    'scripts/parquer_miroir.py',
    'scripts/check_parked_apps.py',
    'scripts/tests/test_check_parked_apps.py',
})
# Dossiers exemptés (préfixes POSIX) : les deux miroirs de code parqué.
DOSSIERS_EXEMPTS = ('backend/parked/', 'frontend/parked/')
IGNORES = {'__pycache__', '.git', 'node_modules', 'dist', 'build'}

# d. — seule une VRAIE instruction compte (`from`, `import`, `import(`,
# `require(`), jamais une chaîne isolée ni un commentaire (déjà décapé).
SPEC_JS_RE = re.compile(r"""\b(?:from|import|require)\b\s*\(?\s*['"]([^'"]+)['"]""")
PARKED_SPEC_RE = re.compile(r'(?:^|/)parked(?:/|$)')


def charger_module(chemin: Path, nom: str):
    """Charge un module Python PAR CHEMIN (aucun import de paquet)."""
    spec = importlib.util.spec_from_file_location(nom, chemin)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def charger_registre(racine: Path):
    """Le registre UNIQUE des labels parqués — lu par chemin, sans Django."""
    return charger_module(
        racine / 'backend' / 'django_core' / 'core' / 'parked.py',
        '_parked_check')


def rel(racine: Path, chemin: Path) -> str:
    return chemin.relative_to(racine).as_posix()


def est_exempt(chemin_rel: str, labels) -> bool:
    """Vrai si ce chemin relatif échappe à la garde (voir le docstring)."""
    if chemin_rel in FICHIERS_EXEMPTS:
        return True
    if any(chemin_rel.startswith(prefixe) for prefixe in DOSSIERS_EXEMPTS):
        return True
    if 'migrations' in chemin_rel.split('/'):
        return True
    # Le dossier propre à une app parquée (sa coquille) : la règle (e) le juge.
    prefixe = 'backend/django_core/apps/'
    if chemin_rel.startswith(prefixe):
        if chemin_rel[len(prefixe):].split('/')[0] in labels:
            return True
    return False


def fichiers_py(racine: Path, sous_dossier: str, labels):
    """Les ``.py`` scannables sous ``racine/sous_dossier`` (exemptions faites)."""
    base = racine / sous_dossier
    if not base.is_dir():
        return
    for chemin in sorted(base.rglob('*.py')):
        if any(part in IGNORES for part in chemin.parts):
            continue
        chemin_rel = rel(racine, chemin)
        if est_exempt(chemin_rel, labels):
            continue
        yield chemin, chemin_rel


def arbre_de(chemin: Path):
    """``ast`` du fichier, ou ``None`` si illisible (jamais une fausse alerte)."""
    try:
        return ast.parse(chemin.read_text(encoding='utf-8'), filename=str(chemin))
    except (OSError, SyntaxError, UnicodeDecodeError):
        return None


def constantes_texte(arbre):
    """Les chaînes du module, docstrings et littéraux-instruction EXCLUS.

    Un ``Expr`` dont la valeur est une chaîne est de la documentation (docstring
    de module/classe/fonction, ou paragraphe de prose posé entre deux blocs) :
    il ne s'exécute pas et ne doit JAMAIS déclencher la garde.
    """
    docs = set()
    for noeud in ast.walk(arbre):
        if (isinstance(noeud, ast.Expr)
                and isinstance(noeud.value, ast.Constant)
                and isinstance(noeud.value.value, str)):
            docs.add(id(noeud.value))
    for noeud in ast.walk(arbre):
        if (isinstance(noeud, ast.Constant) and isinstance(noeud.value, str)
                and id(noeud) not in docs):
            yield noeud, noeud.value


def _label_vise(texte: str, labels) -> str:
    """Le label parqué qu'une chaîne ``apps.<label>.…`` désigne, sinon ``''``."""
    morceaux = texte.split('.')
    if len(morceaux) >= 3 and morceaux[0] == 'apps' and morceaux[1] in labels:
        return morceaux[1]
    return ''


def regle_a(racine: Path, labels):
    """Imports, FK par chaîne dans un ``models*.py``, ``get_model``."""
    echecs = []
    for chemin, chemin_rel in fichiers_py(racine, 'backend/django_core', labels):
        arbre = arbre_de(chemin)
        if arbre is None:
            continue
        for noeud in ast.walk(arbre):
            cibles = []
            if (isinstance(noeud, ast.ImportFrom) and not noeud.level
                    and noeud.module):
                cibles = [noeud.module]
            elif isinstance(noeud, ast.Import):
                cibles = [alias.name for alias in noeud.names]
            for cible in cibles:
                morceaux = cible.split('.')
                if (len(morceaux) >= 2 and morceaux[0] == 'apps'
                        and morceaux[1] in labels):
                    echecs.append((chemin_rel, noeud.lineno,
                                   'importe apps.%s — cette app est parquée '
                                   '(coquille sans code)' % morceaux[1]))
        modele_py = fnmatch.fnmatch(Path(chemin_rel).name, 'models*.py')
        if modele_py:
            for noeud, texte in constantes_texte(arbre):
                if (re.fullmatch(r'[a-z_][a-z0-9_]*\.[A-Z]\w*', texte)
                        and texte.split('.')[0] in labels):
                    echecs.append((chemin_rel, noeud.lineno,
                                   "FK par chaîne vers '%s' — cette app est "
                                   "parquée (son modèle n'existe plus)" % texte))
        for noeud in ast.walk(arbre):
            if not isinstance(noeud, ast.Call) or not noeud.args:
                continue
            nom = (noeud.func.attr if isinstance(noeud.func, ast.Attribute)
                   else noeud.func.id if isinstance(noeud.func, ast.Name)
                   else '')
            premier = noeud.args[0]
            if (nom != 'get_model' or not isinstance(premier, ast.Constant)
                    or not isinstance(premier.value, str)):
                continue
            if premier.value.split('.')[0] in labels:
                echecs.append((chemin_rel, noeud.lineno,
                               "get_model('%s'…) — cette app est parquée"
                               % premier.value))
    return echecs


def regle_b(racine: Path, labels):
    """``erp_agentique/urls.py`` n'inclut plus l'urlconf d'une app parquée."""
    echecs = []
    chemin = racine / 'backend' / 'django_core' / 'erp_agentique' / 'urls.py'
    if not chemin.is_file():
        return echecs
    arbre = arbre_de(chemin)
    if arbre is None:
        return echecs
    chemin_rel = rel(racine, chemin)
    for noeud, texte in constantes_texte(arbre):
        if _label_vise(texte, labels) and texte.split('.')[-1] in {
                'urls', 'api', 'routers'}:
            echecs.append((chemin_rel, noeud.lineno,
                           "include('%s') — cette app est parquée (aucune url)"
                           % texte))
    return echecs


def _sous_arbres_du_reglage(arbre, nom):
    """Le(s) sous-arbre(s) du réglage ``nom``, qu'il soit racine ou imbriqué."""
    trouves = []
    for noeud in ast.walk(arbre):
        if isinstance(noeud, ast.Assign):
            for cible in noeud.targets:
                plat = (cible.id if isinstance(cible, ast.Name)
                        else cible.attr if isinstance(cible, ast.Attribute)
                        else '')
                if plat == nom:
                    trouves.append(noeud.value)
        elif isinstance(noeud, ast.Dict):
            for cle, valeur in zip(noeud.keys, noeud.values):
                if isinstance(cle, ast.Constant) and cle.value == nom:
                    trouves.append(valeur)
    return trouves


def _echecs_celery(chemin_rel, sous_arbres, labels, quoi):
    """Chaîne ``apps.<label>.…`` ou nom de tâche ``<label>.…`` dans ce réglage."""
    echecs = []
    for sous_arbre in sous_arbres:
        for noeud, texte in constantes_texte(sous_arbre):
            label = _label_vise(texte, labels)
            if not label and '.' in texte and texte.split('.')[0] in labels:
                label = texte.split('.')[0]
            if label:
                echecs.append((chemin_rel, noeud.lineno,
                               "%s vise '%s' — l'app %s est parquée (aucune "
                               'tâche, aucun modèle)' % (quoi, texte, label)))
    return echecs


def regle_c(racine: Path, labels):
    """``beat_schedule`` / ``CELERY_TASK_ROUTES`` / ``ENUM_NAME_OVERRIDES``."""
    echecs = []
    agentique = racine / 'backend' / 'django_core' / 'erp_agentique'
    celery = agentique / 'celery.py'
    if celery.is_file():
        arbre = arbre_de(celery)
        if arbre is not None:
            echecs += _echecs_celery(
                rel(racine, celery),
                _sous_arbres_du_reglage(arbre, 'beat_schedule'),
                labels, 'une entrée beat')
    base = agentique / 'settings' / 'base.py'
    if base.is_file():
        arbre = arbre_de(base)
        if arbre is not None:
            chemin_rel = rel(racine, base)
            echecs += _echecs_celery(
                chemin_rel, _sous_arbres_du_reglage(arbre, 'CELERY_TASK_ROUTES'),
                labels, 'une route Celery')
            echecs += _echecs_celery(
                chemin_rel,
                _sous_arbres_du_reglage(arbre, 'ENUM_NAME_OVERRIDES'),
                labels, 'une surcharge ENUM_NAME_OVERRIDES')
    return echecs


def sans_commentaires_js(source: str) -> str:
    """Décape les commentaires JS en PRÉSERVANT chaînes et numéros de ligne."""
    sortie = []
    i, n = 0, len(source)
    while i < n:
        c = source[i]
        if c in '"\'`':
            guillemet = c
            sortie.append(c)
            i += 1
            while i < n:
                d = source[i]
                if d == '\\' and i + 1 < n:
                    sortie.append(source[i:i + 2])
                    i += 2
                    continue
                sortie.append(d)
                i += 1
                if d == guillemet or (d == '\n' and guillemet != '`'):
                    break
            continue
        if c == '/' and i + 1 < n and source[i + 1] == '/':
            while i < n and source[i] != '\n':
                i += 1
            continue
        if c == '/' and i + 1 < n and source[i + 1] == '*':
            i += 2
            while i + 1 < n and not (source[i] == '*' and source[i + 1] == '/'):
                if source[i] == '\n':
                    sortie.append('\n')
                i += 1
            i = min(i + 2, n)
            continue
        sortie.append(c)
        i += 1
    return ''.join(sortie)


def regle_d(racine: Path, labels):
    """Aucun fichier de ``frontend/src`` n'importe depuis un dossier parqué."""
    echecs = []
    base = racine / 'frontend' / 'src'
    if not base.is_dir():
        return echecs
    suffixes = {'.js', '.jsx', '.mjs', '.ts', '.tsx'}
    for chemin in sorted(base.rglob('*')):
        if chemin.is_dir() or chemin.suffix not in suffixes:
            continue
        if any(part in IGNORES for part in chemin.parts):
            continue
        chemin_rel = rel(racine, chemin)
        if est_exempt(chemin_rel, labels):
            continue
        try:
            source = sans_commentaires_js(chemin.read_text(encoding='utf-8'))
        except (OSError, UnicodeDecodeError):
            continue
        for trouve in SPEC_JS_RE.finditer(source):
            if PARKED_SPEC_RE.search(trouve.group(1)):
                ligne = source.count('\n', 0, trouve.start()) + 1
                echecs.append((chemin_rel, ligne,
                               "importe '%s' — le code parqué est hors build "
                               '(frontend/parked/README.md)' % trouve.group(1)))
    return echecs


def regle_e(racine: Path, parked):
    """Chaque app parquée est bien une COQUILLE (règle de parquer_app.py)."""
    parquer = charger_module(RACINE / 'scripts' / 'parquer_app.py',
                             '_parquer_check')
    ancien = parquer.APPS_DIR
    parquer.APPS_DIR = racine / 'backend' / 'django_core' / 'apps'
    try:
        echecs = []
        for label in parked.APPS_PARQUEES:
            for ecart in parquer.verifier(label, parked):
                echecs.append(('backend/django_core/apps/%s/' % label, 0,
                               "n'est plus une coquille : %s" % ecart))
        return echecs
    finally:
        parquer.APPS_DIR = ancien


def verifier_tout(racine: Path):
    """Les 5 règles, dans l'ordre. Renvoie la liste des échecs."""
    parked = charger_registre(racine)
    labels = parked.APPS_PARQUEES_SET
    return (regle_a(racine, labels) + regle_b(racine, labels)
            + regle_c(racine, labels) + regle_d(racine, labels)
            + regle_e(racine, parked))


def main(argv=None) -> int:
    analyseur = argparse.ArgumentParser(
        description='SOLMVP53 — aucune référence vers une app parquée.')
    analyseur.add_argument('--racine', default=str(RACINE),
                           help='racine du dépôt à scanner (défaut : ce dépôt)')
    args = analyseur.parse_args(argv)
    racine = Path(args.racine).resolve()

    echecs = verifier_tout(racine)
    if echecs:
        print('check_parked_apps : %d référence(s) vers une app PARQUÉE :'
              % len(echecs))
        for chemin_rel, ligne, raison in echecs:
            print('  - %s:%d — %s' % (chemin_rel, ligne, raison))
        print('\nCes apps sont sorties du MVP solaire (décision fondateur du '
              '20/09/2026) : leur dossier est une coquille de migrations, leur '
              'code vit sous backend/parked/ et frontend/parked/. Retirer la '
              'référence AVEC la fonctionnalité — jamais une garde '
              '`is_installed`. Registre : backend/django_core/core/parked.py ; '
              'recette de retour : docs/parked-modules.md §5.')
        return 1
    parked = charger_registre(racine)
    print('check_parked_apps : OK — aucune référence vers les %d apps parquées '
          '(imports, FK, urls, beat, frontend, contrat de coquille).'
          % len(parked.APPS_PARQUEES))
    return 0


if __name__ == '__main__':
    sys.exit(main())
