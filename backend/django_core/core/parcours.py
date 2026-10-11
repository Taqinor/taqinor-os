"""Tables de parcours (METHODE v3 §D.1) — chargement et résolution STATIQUE des symboles.

Une table = ``backend/django_core/apps/<pilote>/parcours/<PA>.json`` (un fichier, un
propriétaire). Chaque étape porte exactement 1 déclencheur, 1 fonction d'entrée,
1 checkpoint et ≥ 1 règle aval ; chaque référence ``chemin/fichier.py::Symbole`` (ou
``::Classe.methode``) résout par AST, sans base ni import du module visé.

Seule implémentation du dépôt (« aucune seconde implémentation ») : les gardes
``apps/<x>/…/test_parcours_pa<n>.py`` (AMET11, AMET13, AMET15, AMET24) l'importent, et
``scripts/check_parcours.py`` / ``scripts/rejouer_parcours.py`` (AMET98) la réutilisent.
``core`` ne dépend d'aucune app (contrat import-linter) : tout est chemin + texte.
"""

from __future__ import annotations

import ast
import json
import re
from pathlib import Path

RACINE_DJANGO = Path(__file__).resolve().parents[1]
# Arbre complet : <depot>/backend/django_core ; image docker : /app (sans parent) -> on retombe sur la racine Django.
RACINE_DEPOT = RACINE_DJANGO.parents[1] if len(RACINE_DJANGO.parents) > 1 else RACINE_DJANGO

TYPES_DECLENCHEUR = frozenset({'clic', 'evenement', 'beat', 'manuel'})
REGLES_AVAL = frozenset({
    'recalcul', 'preserve_manuel', 'fige', 'reference', 'choix_explicite',
    'refus_409', 'ecrase', 'non_propage',
})
CHAMPS_ETAPE = ('id', 'nom', 'proprietaire', 'declencheur', 'fonction_entree',
                'checkpoint', 'regle_aval')
CHAMPS_CHECKPOINT = ('modifiable', 'champs', 'persistance')
EXTENSIONS_AST = ('.py',)
EXTENSIONS_TEXTE = ('.js', '.jsx', '.ts', '.tsx', '.mjs', '.astro', '.json', '.ps1', '.yml', '.yaml')
# Une référence est un symbole à résoudre si elle nomme un fichier (avec ou sans ``::``).
_REF_FICHIER = re.compile(r'^[\w./\-]+\.(py|js|jsx|ts|tsx|mjs|astro|json|ps1|yml|yaml)(::[\w.]+)?$')


def charger_table(chemin: Path | str) -> dict:
    """Lit une table JSON (UTF-8) et la renvoie telle quelle."""
    with open(chemin, encoding='utf-8') as fh:
        return json.load(fh)


def etapes(table: dict) -> list[dict]:
    """Les étapes d'une table (clé ``etapes``), dans l'ordre du fichier."""
    return list(table.get('etapes') or [])


def chemin_du_fichier(ref_fichier: str) -> Path | None:
    """Résout un chemin de référence : relatif à la racine du dépôt d'abord, puis à
    ``backend/django_core`` (les tables écrivent ``apps/…`` sans le préfixe)."""
    for base in (RACINE_DEPOT, RACINE_DJANGO):
        candidat = base / ref_fichier
        if candidat.is_file():
            return candidat
    return None


def _symbole_dans_ast(arbre: ast.AST, nom: str) -> bool:
    for noeud in ast.walk(arbre):
        if isinstance(noeud, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and noeud.name == nom:
            return True
        if isinstance(noeud, ast.Assign):
            for cible in noeud.targets:
                if isinstance(cible, ast.Name) and cible.id == nom:
                    return True
        if isinstance(noeud, ast.AnnAssign) and isinstance(noeud.target, ast.Name) and noeud.target.id == nom:
            return True
    return False


def _methode_dans_classe(arbre: ast.AST, classe: str, methode: str) -> bool:
    for noeud in ast.walk(arbre):
        if isinstance(noeud, ast.ClassDef) and noeud.name == classe:
            for membre in noeud.body:
                if isinstance(membre, (ast.FunctionDef, ast.AsyncFunctionDef)) and membre.name == methode:
                    return True
                if isinstance(membre, ast.Assign) and any(
                    isinstance(c, ast.Name) and c.id == methode for c in membre.targets
                ):
                    return True
    return False


def est_une_reference(valeur) -> bool:
    """Vrai si ``valeur`` a la forme ``fichier[::Symbole]`` (à résoudre) ; faux pour un
    texte libre (``manuel``, ``n/a``, une route)."""
    return isinstance(valeur, str) and bool(_REF_FICHIER.match(valeur.strip()))


def resoudre_symbole(ref: str) -> tuple[bool, str]:
    """``(True, '')`` si ``ref`` résout ; sinon ``(False, motif en français)``.

    - ``chemin/fichier.py`` : le fichier existe.
    - ``chemin/fichier.py::Symbole`` : def / class / affectation de module nommée ``Symbole``.
    - ``chemin/fichier.py::Classe.methode`` : méthode (ou attribut) de la classe.
    - fichiers non Python : le symbole apparaît comme mot entier dans le texte.
    """
    ref = ref.strip()
    fichier, _, symbole = ref.partition('::')
    chemin = chemin_du_fichier(fichier)
    if chemin is None:
        return False, f'fichier introuvable : {fichier}'
    if not symbole:
        return True, ''
    if chemin.suffix in EXTENSIONS_AST:
        try:
            arbre = ast.parse(chemin.read_text(encoding='utf-8'), filename=str(chemin))
        except SyntaxError as exc:  # pragma: no cover — un fichier cassé casse déjà compileall
            return False, f'{fichier} : syntaxe invalide ({exc})'
        if '.' in symbole:
            classe, _, methode = symbole.partition('.')
            if _methode_dans_classe(arbre, classe, methode):
                return True, ''
            return False, f'{fichier} : {classe}.{methode} introuvable'
        if _symbole_dans_ast(arbre, symbole):
            return True, ''
        return False, f'{fichier} : symbole {symbole} introuvable'
    texte = chemin.read_text(encoding='utf-8', errors='replace')
    dernier = symbole.rsplit('.', 1)[-1]
    if re.search(r'\b' + re.escape(dernier) + r'\b', texte):
        return True, ''
    return False, f'{fichier} : {symbole} absent du texte'


def problemes_de_l_etape(etape: dict) -> list[str]:
    """Les manquements d'UNE étape (liste vide = étape complète et résolue)."""
    ident = etape.get('id') or '?'
    erreurs: list[str] = []
    for champ in CHAMPS_ETAPE:
        if champ not in etape or etape[champ] in (None, '', [], {}):
            erreurs.append(f'{ident} : champ `{champ}` manquant')
    declencheur = etape.get('declencheur')
    if isinstance(declencheur, dict):
        if declencheur.get('type') not in TYPES_DECLENCHEUR:
            erreurs.append(f'{ident} : declencheur.type hors de {sorted(TYPES_DECLENCHEUR)}')
        source = declencheur.get('source')
        if not source:
            erreurs.append(f'{ident} : declencheur.source manquant')
        elif est_une_reference(source):
            ok, motif = resoudre_symbole(source)
            if not ok:
                erreurs.append(f'{ident} : declencheur.source — {motif}')
        elif declencheur.get('type') != 'manuel':
            erreurs.append(f'{ident} : declencheur.source doit être `fichier::symbole` ({source!r})')
    elif declencheur is not None:
        erreurs.append(f'{ident} : declencheur doit être un objet')
    entree = etape.get('fonction_entree')
    if isinstance(entree, str) and entree:
        if est_une_reference(entree):
            ok, motif = resoudre_symbole(entree)
            if not ok:
                erreurs.append(f'{ident} : fonction_entree — {motif}')
        else:
            erreurs.append(f'{ident} : fonction_entree doit être `fichier::symbole` ({entree!r})')
    checkpoint = etape.get('checkpoint')
    if isinstance(checkpoint, dict):
        for champ in CHAMPS_CHECKPOINT:
            if champ not in checkpoint:
                erreurs.append(f'{ident} : checkpoint.{champ} manquant')
        persistance = checkpoint.get('persistance')
        if est_une_reference(persistance):
            ok, motif = resoudre_symbole(persistance)
            if not ok:
                erreurs.append(f'{ident} : checkpoint.persistance — {motif}')
        elif not persistance:
            erreurs.append(f'{ident} : checkpoint.persistance vide')
    elif checkpoint is not None:
        erreurs.append(f'{ident} : checkpoint doit être un objet')
    regles = etape.get('regle_aval')
    if isinstance(regles, list):
        if not regles:
            erreurs.append(f'{ident} : au moins une règle aval')
        for regle in regles:
            nom = regle.get('type') if isinstance(regle, dict) else regle
            if nom not in REGLES_AVAL:
                erreurs.append(f'{ident} : règle aval `{nom}` hors de {sorted(REGLES_AVAL)}')
    elif regles is not None:
        erreurs.append(f'{ident} : regle_aval doit être une liste')
    return erreurs


def problemes_de_la_table(table: dict) -> list[str]:
    """Tous les manquements d'une table : identifiants uniques, étapes complètes et
    résolues, ``portes[]`` non vide (au niveau de la table)."""
    erreurs: list[str] = []
    vus: set[str] = set()
    liste = etapes(table)
    if not liste:
        erreurs.append('table sans étape')
    for etape in liste:
        ident = etape.get('id')
        if ident in vus:
            erreurs.append(f'{ident} : identifiant en double')
        vus.add(ident)
        erreurs.extend(problemes_de_l_etape(etape))
    if not table.get('portes'):
        erreurs.append('`portes[]` vide : lister les entrées de création du parcours')
    return erreurs
