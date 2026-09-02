#!/usr/bin/env python3
"""SOL4 - Garde de cloture anti-recouplage des editions (l'actif durable).

Aucune app GARDEE dans l'edition solaire ne doit dependre d'une app PARQUEE :
ni par import Python (module-level OU fonction-local), ni par reference de
modele en chaine ("sante.CycleSterilisation"), ni par une dependance de
migration. Une seule arete oubliee et `migrate` sur une base vierge - ou le
simple demarrage - echoue en edition solaire : c'est le decouplage etabli par
SOL2/SOL3 que cette garde empeche de perdre.

Le sweep est COMPLET (toutes les migrations de TOUTES les apps gardees, pas
seulement qhse/0057) et le message d'echec NOMME l'arete fautive.

Script HOTE : pur AST + lecture de fichiers. Aucun Django, aucune base, aucun
settings charge (le registre d'editions est du Python pur, charge par chemin).

Allowlist : `scripts/editions_decouplage_allow.txt`, une entree par ligne au
format `chemin/relatif.py | jeton   # justification`. Volontairement SANS
numero de ligne : une allowlist file:line se perime des qu'une ligne bouge
(classe de bug #34) - ici, seul le couple (fichier, symbole) compte.

Usage :
    python scripts/check_editions_decouplage.py [--edition solar]
"""
from __future__ import annotations

import argparse
import ast
import importlib.util
import re
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
BACKEND = RACINE / 'backend' / 'django_core'
ALLOWLIST = Path(__file__).resolve().parent / 'editions_decouplage_allow.txt'


def _charger_registre_editions():
    """Charge `settings/editions.py` PAR CHEMIN (aucun import de settings)."""
    chemin = BACKEND / 'erp_agentique' / 'settings' / 'editions.py'
    spec = importlib.util.spec_from_file_location(
        '_sol_editions_registre', chemin)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


editions = _charger_registre_editions()


def _apps_du_depot():
    """Chemins d'app ('apps.<x>', 'core', 'authentication') presents sur disque."""
    trouvees = []
    for chemin in sorted((BACKEND / 'apps').iterdir()):
        if (chemin / 'apps.py').exists():
            trouvees.append(f'apps.{chemin.name}')
    for socle in ('core', 'authentication'):
        if (BACKEND / socle / 'apps.py').exists():
            trouvees.append(socle)
    return trouvees


def _dossier(chemin_app):
    """'apps.mrp' -> Path(.../apps/mrp)."""
    return BACKEND.joinpath(*chemin_app.split('.'))


def _est_fichier_de_test(fichier: Path):
    return (
        'tests' in fichier.parts
        or fichier.name.startswith('test_')
        or fichier.name == 'tests.py'
    )


def _rel(fichier: Path):
    return str(fichier.relative_to(RACINE)).replace('\\', '/')


def charger_allowlist():
    """{(fichier, jeton): justification} - aretes explicitement tolerees."""
    entrees = {}
    if not ALLOWLIST.exists():
        return entrees
    for brute in ALLOWLIST.read_text(encoding='utf-8').splitlines():
        ligne = brute.strip()
        if not ligne or ligne.startswith('#'):
            continue
        corps, _, justification = ligne.partition('#')
        if '|' not in corps:
            continue
        fichier, _, jeton = corps.partition('|')
        entrees[(fichier.strip().replace('\\', '/'), jeton.strip())] = (
            justification.strip())
    return entrees


def _aretes_imports(fichier: Path, source: str, prefixes_parques):
    """Imports Python (module-level ET fonction-locaux) vers une app parquee."""
    aretes = []
    try:
        arbre = ast.parse(source, filename=str(fichier))
    except SyntaxError as exc:  # pragma: no cover - fichier casse
        return [(getattr(exc, 'lineno', 0), 'SYNTAXE', '<illisible>',
                 f'fichier illisible : {exc}')]
    for noeud in ast.walk(arbre):
        if isinstance(noeud, ast.Import):
            cibles = [alias.name for alias in noeud.names]
        elif isinstance(noeud, ast.ImportFrom):
            if noeud.level:  # import relatif : jamais cross-app
                continue
            cibles = [noeud.module or '']
        else:
            continue
        for cible in cibles:
            for parque, chemin_app in prefixes_parques.items():
                if cible == chemin_app or cible.startswith(chemin_app + '.'):
                    aretes.append((
                        noeud.lineno, 'IMPORT', cible,
                        f'importe « {cible} » (app parquée « {parque} »)'))
    return aretes


def _aretes_migrations(fichier: Path, source: str, labels_parques):
    """Dependances de migration (`dependencies`/`run_before`) vers une app parquee."""
    aretes = []
    try:
        arbre = ast.parse(source, filename=str(fichier))
    except SyntaxError:  # pragma: no cover
        return aretes
    for noeud in ast.walk(arbre):
        if not isinstance(noeud, ast.Assign):
            continue
        noms = {c.id for c in noeud.targets if isinstance(c, ast.Name)}
        if not (noms & {'dependencies', 'run_before'}):
            continue
        for element in ast.walk(noeud.value):
            if not isinstance(element, (ast.Tuple, ast.List)) or not element.elts:
                continue
            premier = element.elts[0]
            if not (isinstance(premier, ast.Constant)
                    and isinstance(premier.value, str)):
                continue
            if premier.value in labels_parques:
                aretes.append((
                    getattr(element, 'lineno', noeud.lineno), 'MIGRATION',
                    premier.value,
                    f'dépend du nœud de migration « {premier.value} » (app '
                    f'parquée) — `migrate` échouerait sur une base vierge en '
                    f'édition solaire'))
    return aretes


def _aretes_refs_chaine(fichier: Path, source: str, labels_parques):
    """References de modele en chaine : 'sante.CycleSterilisation', to='mrp.…'."""
    if not labels_parques:
        return []
    aretes = []
    motif = re.compile(
        r'''['"](?P<label>%s)\.(?P<modele>[A-Za-z_][A-Za-z0-9_]*)['"]'''
        % '|'.join(sorted(re.escape(x) for x in labels_parques)))
    for numero, ligne in enumerate(source.splitlines(), 1):
        for m in motif.finditer(ligne):
            jeton = f'{m.group("label")}.{m.group("modele")}'
            aretes.append((
                numero, 'REF_CHAINE', jeton,
                f'référence en chaîne « {jeton} » vers une app parquée'))
    return aretes


def analyser(edition):
    """Renvoie (violations, nb_fichiers, allowlist_inutilisee)."""
    parquees = editions.apps_parquees(edition)          # {'apps.mrp': libellé}
    labels_parques = {chemin.rsplit('.', 1)[-1] for chemin in parquees}
    prefixes_parques = {
        chemin.rsplit('.', 1)[-1]: chemin for chemin in parquees}
    if not parquees:
        return [], 0, set()

    allowlist = charger_allowlist()
    utilisees = set()
    gardees = [a for a in _apps_du_depot() if a not in parquees]

    violations = []
    fichiers_lus = 0
    for chemin_app in gardees:
        dossier = _dossier(chemin_app)
        if not dossier.exists():
            continue
        for fichier in sorted(dossier.rglob('*.py')):
            if '__pycache__' in fichier.parts:
                continue
            est_migration = 'migrations' in fichier.parts
            if _est_fichier_de_test(fichier) and not est_migration:
                continue
            source = fichier.read_text(encoding='utf-8', errors='replace')
            fichiers_lus += 1
            aretes = _aretes_imports(fichier, source, prefixes_parques)
            aretes += _aretes_refs_chaine(fichier, source, labels_parques)
            if est_migration:
                aretes += _aretes_migrations(fichier, source, labels_parques)
            rel = _rel(fichier)
            for numero, genre, jeton, message in aretes:
                if (rel, jeton) in allowlist:
                    utilisees.add((rel, jeton))
                    continue
                violations.append(
                    (f'{rel}:{numero}', chemin_app, genre, message))
    return violations, fichiers_lus, set(allowlist) - utilisees


def main(argv=None):
    parseur = argparse.ArgumentParser(description=__doc__)
    parseur.add_argument(
        '--edition', default=editions.EDITION_SOLAR,
        choices=list(editions.EDITIONS),
        help="Édition dont le périmètre parqué sert de référence "
             "(défaut : solar).")
    args = parseur.parse_args(argv)

    parquees = editions.apps_parquees(args.edition)
    if not parquees:
        print(f"check_editions_decouplage: edition '{args.edition}' ne parque "
              f"aucune app - rien a verifier.")
        return 0

    violations, fichiers, orphelines = analyser(args.edition)

    if violations:
        print(
            f"check_editions_decouplage: {len(violations)} arete(s) de "
            f"recouplage vers une app PARQUEE de l'edition "
            f"'{args.edition}' :\n")
        for cle, app_gardee, genre, message in violations:
            print(f'  - [{genre}] {cle} (app gardee « {app_gardee} ») : '
                  f'{message}')
        print(
            "\nCorriger l'arete (reference non contrainte, selecteur, branche "
            "rendue inatteignable...) ou, si elle est reellement inoffensive, "
            f"l'inscrire avec sa justification dans {_rel(ALLOWLIST)} "
            "(format : chemin.py | jeton  # pourquoi).")
        return 1

    if orphelines:
        print("check_editions_decouplage: entree(s) d'allowlist devenues "
              "inutiles (l'arete n'existe plus) - a supprimer :")
        for fichier, jeton in sorted(orphelines):
            print(f'  - {fichier} | {jeton}')
        return 1

    print(f"check_editions_decouplage: OK - {fichiers} fichier(s) analyse(s), "
          f"aucune arete des apps gardees vers les {len(parquees)} app(s) "
          f"parquee(s) de l'edition '{args.edition}'.")
    return 0


if __name__ == '__main__':
    sys.exit(main())
