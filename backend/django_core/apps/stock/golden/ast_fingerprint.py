"""SPL110 — outil d'empreinte AST + entrées/sorties des « golden » du bloc
fiche technique (stock).

UN SEUL outil, réutilisé par SPL110 (modèle), SPL111 (sélecteurs) et SPL112
(sérialiseur) : pas de jumeau. Bibliothèque standard seule, pour que le test
backend qui tourne dans l'image Docker (depuis ``backend/django_core``, qui ne
voit pas ``scripts/``) puisse l'importer.

L'empreinte d'un objet est le sha1 de ``ast.dump(..., include_attributes=
False)`` de son source (``inspect.getsource``), donc indépendante du fichier
qui porte le symbole : un déplacement pur d'un module à l'autre ne la change
pas, un changement de logique la change. Les numéros de ligne et les
commentaires n'y figurent pas.

Normalisations (déclarées, appliquées DES DEUX CÔTÉS d'une comparaison) :

  1. les imports locaux de fonction (``import`` / ``from … import`` écrits dans
     le corps d'une fonction) sont retirés : un déplacement vers un module
     dont les imports de tête diffèrent n'en a pas besoin ;
  2. UNE seule différence AST est tolérée : le premier argument d'un
     ``OneToOneField`` / ``ForeignKey`` écrit comme nom de classe nu
     (``Produit``) devient la chaîne ``'stock.Produit'`` — l'édition que le
     déplacement du modèle impose (un module neuf ne peut pas importer
     ``Produit`` en tête sans cycle).

L'empreinte complète le golden de comportement ; elle ne le remplace pas.

Capture : ``GOLDEN_CAPTURE=1`` écrit la section courante dans le JSON. Sans
cette variable le JSON n'est JAMAIS écrit : il est capturé sur le code actuel
et jamais régénéré après un déplacement.
"""
import ast
import hashlib
import inspect
import json
import os
import textwrap
from pathlib import Path

GOLDEN_DIR = Path(__file__).resolve().parent

# Nom de classe nu -> référence « app.Modèle » (normalisation n° 2).
_FK_CLASSES = {'OneToOneField', 'ForeignKey'}
_NOMS_NUS = {'Produit': 'stock.Produit'}


class _Normaliseur(ast.NodeTransformer):
    """Applique les deux normalisations déclarées dans le docstring."""

    def _fonction(self, noeud):
        noeud = self.generic_visit(noeud)
        corps = [n for n in noeud.body
                 if not isinstance(n, (ast.Import, ast.ImportFrom))]
        noeud.body = corps or [ast.Pass()]
        return noeud

    visit_FunctionDef = _fonction
    visit_AsyncFunctionDef = _fonction

    def visit_Call(self, noeud):
        noeud = self.generic_visit(noeud)
        nom = noeud.func.attr if isinstance(noeud.func, ast.Attribute) else (
            noeud.func.id if isinstance(noeud.func, ast.Name) else None)
        if (nom in _FK_CLASSES and noeud.args
                and isinstance(noeud.args[0], ast.Name)
                and noeud.args[0].id in _NOMS_NUS):
            noeud.args[0] = ast.Constant(value=_NOMS_NUS[noeud.args[0].id])
        return noeud


def _parametres(arbre):
    """Noms ordonnés des paramètres d'une fonction (liste vide pour une
    classe) — redondant avec l'AST, mais lisible dans un diff de golden."""
    noeud = arbre.body[0]
    if not isinstance(noeud, (ast.FunctionDef, ast.AsyncFunctionDef)):
        return []
    a = noeud.args
    noms = [x.arg for x in a.posonlyargs + a.args]
    if a.vararg:
        noms.append('*' + a.vararg.arg)
    noms += [x.arg for x in a.kwonlyargs]
    if a.kwarg:
        noms.append('**' + a.kwarg.arg)
    return noms


def fingerprint_source(source):
    """Empreinte (sha1 hex) d'un source de fonction ou de classe."""
    arbre = ast.parse(textwrap.dedent(source))
    arbre = ast.fix_missing_locations(_Normaliseur().visit(arbre))
    texte = ast.dump(arbre, include_attributes=False)
    texte += '|params=' + ','.join(_parametres(arbre))
    return hashlib.sha1(texte.encode('utf-8'), usedforsecurity=False).hexdigest()


def fingerprint(objet):
    """Empreinte d'une fonction ou d'une classe, lue par ``inspect.
    getsource`` : indépendante du fichier qui la porte."""
    return fingerprint_source(inspect.getsource(objet))


def fingerprint_depuis_fichier(chemin, nom):
    """Empreinte du symbole de premier niveau ``nom`` d'un fichier .py, sans
    l'importer (outil de capture hors Django ; même résultat que
    ``fingerprint`` sur l'objet importé)."""
    texte = Path(chemin).read_text(encoding='utf-8')
    for noeud in ast.parse(texte).body:
        if (isinstance(noeud, (ast.FunctionDef, ast.ClassDef))
                and noeud.name == nom):
            return fingerprint_source(ast.get_source_segment(texte, noeud))
    raise LookupError('%s introuvable dans %s' % (nom, chemin))


# ── Entrées/sorties des golden ──────────────────────────────────────────────

def capture_active():
    return os.environ.get('GOLDEN_CAPTURE') == '1'


def chemin_golden(nom):
    return GOLDEN_DIR / ('%s.json' % nom)


def charger_golden(nom):
    chemin = chemin_golden(nom)
    if not chemin.exists():
        return {}
    return json.loads(chemin.read_text(encoding='utf-8'))


def ecrire_golden(nom, donnees):
    """Réécrit le JSON, clés triées, fins de ligne LF (jamais d'octets
    dépendants de la plateforme)."""
    texte = json.dumps(donnees, indent=2, sort_keys=True, ensure_ascii=False)
    with open(chemin_golden(nom), 'w', encoding='utf-8', newline='\n') as f:
        f.write(texte + '\n')


def verifier_section(test, nom, cle, courant):
    """Compare la section ``cle`` du golden ``nom`` à la valeur courante.

    ``GOLDEN_CAPTURE=1`` : capture la valeur courante (code ACTUEL, avant tout
    déplacement). Sinon : section absente = ÉCHEC (jamais un skip silencieux),
    section présente = égalité stricte."""
    # Aller-retour JSON : la valeur comparée est exactement celle qui serait
    # relue du fichier (tuples -> listes, etc.).
    courant = json.loads(json.dumps(courant, sort_keys=True))
    if capture_active():
        donnees = charger_golden(nom)
        donnees[cle] = courant
        ecrire_golden(nom, donnees)
        return
    donnees = charger_golden(nom)
    if cle not in donnees:
        test.fail(
            "Section « %s » absente de %s.json : la capturer UNE fois sur le "
            "code actuel (GOLDEN_CAPTURE=1, voir le docstring du test), "
            "jamais après un déplacement." % (cle, nom))
    test.assertEqual(donnees[cle], courant)
