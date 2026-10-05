"""SPL240 — kit de preuve « move only » pour la découpe des fichiers-dieux.

Les tâches SPL241-SPL268 déplacent des symboles de niveau module de
``public_views.py``, ``etude_horaire.py``, ``solar_design.py``,
``domain/cycle_vie.py``, ``domain/pipeline.py`` et ``domain/creation.py`` vers
de nouveaux sous-paquets (``public/``, ``horaire/``…). Ce module fournit la
preuve qu'un déplacement est une COPIE FIDÈLE :

* ``empreintes(chemin_module, symboles)`` — ``{nom: ast.dump(noeud)}`` des
  ``def`` / ``class`` / affectations de niveau module (décorateurs et
  docstrings inclus), ``ImportFrom.level`` NORMALISÉ à 0 avant le dump : une
  copie dans un sous-paquet (``from .x`` devenu ``from ..x``) garde la même
  empreinte, toute autre retouche d'une instruction la change ;
* ``ecrire_golden(nom, d)`` / ``charger_golden(nom)`` — ``tests/golden/<nom>.json``
  (JSON trié, indenté) ;
* ``verifier_deplacement(nom, module_cible, module_source)`` — chaque symbole du
  golden a la MÊME empreinte dans la cible ET est ABSENT du niveau module de la
  source (rouge tant que le déplacement n'a pas eu lieu) ; golden vide = échec ;
* ``fichiers_du_groupe(*specs)`` / ``source_du_symbole(nom, fichiers)`` — pour
  les gardes de source qui lisaient UN fichier : elles lisent désormais le
  groupe (fichier d'origine + nouveau sous-paquet), jamais un ensemble vide
  (piège QJR72 « la garde se vide toute seule ») ;
* ``digest(obj, cles_ids=...)`` — sha256 d'un JSON trié après ``normaliser``
  (ids, uuid, jetons, dates figés) pour les goldens de COMPORTEMENT.

Aucun import d'app métier : bibliothèque standard seulement. Auto-vérifié par
``test_split_golden_kit.py``.
"""
import ast
import copy
import datetime
import decimal
import glob
import hashlib
import importlib.util
import json
import os
import re
import uuid
from pathlib import Path

DOSSIER_GOLDEN = Path(__file__).resolve().parent / 'golden'
DJANGO_CORE = Path(__file__).resolve().parents[3]

CLES_IDS_PAR_DEFAUT = frozenset({
    'id', 'pk', 'uuid', 'token', 'jeton', 'share_token', 'payment_token',
    'created_at', 'updated_at', 'date_creation', 'date_modification',
})


# ── Résolution des modules ────────────────────────────────────────────────
def _chemin(chemin_module):
    """Chemin de fichier d'un module : un chemin ``.py`` ou un nom pointé."""
    chemin = Path(str(chemin_module))
    if chemin.suffix == '.py':
        if not chemin.is_absolute():
            chemin = DJANGO_CORE / chemin
        if not chemin.is_file():
            raise AssertionError(f'Module introuvable : {chemin}')
        return chemin
    spec = importlib.util.find_spec(str(chemin_module))
    if spec is None or not spec.origin:
        raise AssertionError(f'Module introuvable : {chemin_module}')
    return Path(spec.origin)


def _arbre(chemin_module):
    chemin = _chemin(chemin_module)
    return ast.parse(chemin.read_text(encoding='utf-8'), filename=str(chemin))


def _noms_definis(noeud):
    """Noms qu'une instruction de niveau module DÉFINIT (def/class/affectation)."""
    if isinstance(noeud, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
        return [noeud.name]
    if isinstance(noeud, ast.Assign):
        noms = []
        for cible in noeud.targets:
            if isinstance(cible, ast.Name):
                noms.append(cible.id)
            elif isinstance(cible, (ast.Tuple, ast.List)):
                noms.extend(e.id for e in cible.elts if isinstance(e, ast.Name))
        return noms
    if isinstance(noeud, ast.AnnAssign) and isinstance(noeud.target, ast.Name):
        return [noeud.target.id]
    return []


def _definitions(chemin_module):
    """``{nom: noeud}`` des définitions de niveau module (la dernière gagne)."""
    defs = {}
    for noeud in _arbre(chemin_module).body:
        for nom in _noms_definis(noeud):
            defs[nom] = noeud
    return defs


def _empreinte(noeud):
    noeud = copy.deepcopy(noeud)
    for sous in ast.walk(noeud):
        if isinstance(sous, ast.ImportFrom):
            sous.level = 0
    return ast.dump(noeud, include_attributes=False)


# ── (a) empreintes ────────────────────────────────────────────────────────
def empreintes(chemin_module, symboles):
    """``{nom: ast.dump}`` normalisé des ``symboles`` de niveau module.

    Un symbole absent du module est une erreur (une capture incomplète ne
    prouve rien).
    """
    defs = _definitions(chemin_module)
    manquants = [s for s in symboles if s not in defs]
    if manquants:
        raise AssertionError(
            f'Symboles absents du niveau module de {chemin_module} : {manquants}')
    return {nom: _empreinte(defs[nom]) for nom in symboles}


def symboles_de_niveau_module(chemin_module):
    """Ensemble des noms définis au niveau module (def/class/affectation)."""
    return set(_definitions(chemin_module))


# ── (b) fichiers golden ───────────────────────────────────────────────────
def _fichier_golden(nom, dossier=None):
    return Path(dossier or DOSSIER_GOLDEN) / f'{nom}.json'


def ecrire_golden(nom, donnees, dossier=None):
    chemin = _fichier_golden(nom, dossier)
    chemin.parent.mkdir(parents=True, exist_ok=True)
    chemin.write_text(
        json.dumps(donnees, sort_keys=True, indent=2, ensure_ascii=False) + '\n',
        encoding='utf-8')
    return chemin


def charger_golden(nom, dossier=None):
    chemin = _fichier_golden(nom, dossier)
    if not chemin.is_file():
        raise AssertionError(f'Golden introuvable : {chemin}')
    return json.loads(chemin.read_text(encoding='utf-8'))


# ── (c) vérification d'un déplacement ─────────────────────────────────────
def ecarts_deplacement(nom, module_cible, module_source, dossier=None):
    """Liste des écarts (vide = déplacement fidèle et complet)."""
    golden = charger_golden(nom, dossier)
    if not golden:
        return [f'Golden {nom!r} vide : il ne prouve rien.']
    cible = _definitions(module_cible)
    source = _definitions(module_source)
    ecarts = []
    for symbole in sorted(golden):
        if symbole not in cible:
            ecarts.append(f'{symbole} : absent de la cible {module_cible}')
        elif _empreinte(cible[symbole]) != golden[symbole]:
            ecarts.append(f'{symbole} : empreinte différente dans {module_cible}')
        if symbole in source:
            ecarts.append(f'{symbole} : encore défini dans la source {module_source}')
    return ecarts


def verifier_deplacement(nom, module_cible, module_source, dossier=None):
    ecarts = ecarts_deplacement(nom, module_cible, module_source, dossier)
    if ecarts:
        raise AssertionError(
            f'Déplacement {nom!r} non fidèle :\n  ' + '\n  '.join(ecarts))


# ── (d) gardes de source tolérantes au découpage ──────────────────────────
def fichiers_du_groupe(*specs, base=None):
    """Fichiers triés d'un groupe (chemins ou globs relatifs à ``base``).

    ``base`` vaut par défaut ``apps/ventes``. Un groupe vide est un échec
    bruyant : une garde qui ne scanne rien passerait en silence.
    """
    racine = Path(base) if base else DJANGO_CORE / 'apps' / 'ventes'
    fichiers = set()
    for spec in specs:
        motif = spec if os.path.isabs(str(spec)) else str(racine / spec)
        fichiers.update(Path(p) for p in glob.glob(motif) if p.endswith('.py'))
    fichiers = sorted(fichiers)
    if not fichiers:
        raise AssertionError(f'Groupe de fichiers vide pour {specs} (base {racine})')
    return fichiers


def source_du_symbole(nom, fichiers):
    """Source exacte du symbole ``nom`` de niveau module, cherché dans ``fichiers``."""
    trouves = []
    for fichier in fichiers:
        texte = Path(fichier).read_text(encoding='utf-8')
        lignes = texte.splitlines(keepends=True)
        for noeud in ast.parse(texte).body:
            if nom in _noms_definis(noeud):
                debut = min([noeud.lineno] + [
                    d.lineno for d in getattr(noeud, 'decorator_list', [])])
                trouves.append(''.join(lignes[debut - 1:noeud.end_lineno]))
    if not trouves:
        raise AssertionError(f'{nom} introuvable dans {[str(f) for f in fichiers]}')
    if len(trouves) > 1:
        raise AssertionError(f'{nom} défini {len(trouves)} fois dans le groupe (jumeau)')
    return trouves[0]


# ── (e) digest de comportement ────────────────────────────────────────────
_RE_UUID = re.compile(
    r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}', re.I)


def normaliser(obj, cles_ids=CLES_IDS_PAR_DEFAUT):
    """Copie de ``obj`` où ids, uuid, jetons et dates sont figés."""
    if isinstance(obj, dict):
        return {
            str(k): ('<id>' if str(k) in cles_ids and v is not None
                     else normaliser(v, cles_ids))
            for k, v in obj.items()
        }
    if isinstance(obj, (list, tuple)):
        return [normaliser(v, cles_ids) for v in obj]
    if isinstance(obj, (datetime.datetime, datetime.date, datetime.time)):
        return '<date>'
    if isinstance(obj, uuid.UUID):
        return '<uuid>'
    if isinstance(obj, decimal.Decimal):
        return str(obj)
    if isinstance(obj, str) and _RE_UUID.search(obj):
        return _RE_UUID.sub('<uuid>', obj)
    return obj


def digest(obj, cles_ids=CLES_IDS_PAR_DEFAUT):
    texte = json.dumps(normaliser(obj, cles_ids), sort_keys=True, default=str)
    return hashlib.sha256(texte.encode('utf-8')).hexdigest()
