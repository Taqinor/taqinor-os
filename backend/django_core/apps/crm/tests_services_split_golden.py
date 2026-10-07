"""SPL1 — golden du découpage de ``apps/crm/services.py`` (capture seule).

Capturé UNE fois sur le code actuel, AVANT tout déplacement, et JAMAIS édité
ensuite (ni ce fichier, ni ``golden/services_split_ast.json``) : chaque tâche
SPL3 à SPL26 déplace des symboles vers un module ``cible`` et ce module doit
rester vert, à l'identique, à chaque étape de la chaîne.

Ce que le golden fige (``golden/services_split_ast.json``) :

* ``symboles`` — pour chaque nom DÉFINI au premier niveau de services.py
  (def, class, affectation ; ``logger`` exclu, redéfini par module) : genre,
  plage initiale, sha256 de ``ast.dump`` du (des) nœud(s) et module de
  destination ``cible`` — une des 29 cibles nommées par SPL3 à SPL25
  (table relevée sur les tâches du plan) ; ``cible`` vaut ``null`` pour un nom
  apparu après la rédaction des tâches (non encore assigné : il reste dans
  services.py tant que le plan ne lui donne pas de destination) ;
* ``facade`` — les noms que des fichiers d'AUTRES propriétaires que
  lead/crm importent via ``apps.crm.services``, avec leurs fichiers
  appelants (ils restent atteignables par la façade) ;
* ``t_trace`` — les noms T-TRACE réexportés depuis ``apps.crm.visites``.

Invariants vrais à CHAQUE étape (tests ci-dessous) :

1. tout nom est défini dans services.py OU dans son module ``cible``, jamais
   ailleurs parmi les modules du découpage, jamais deux fois ; ``logger`` et
   les alias d'import sont exemptés de l'unicité ;
2. l'empreinte AST de chaque nom est identique (corps octet-identique) ;
3. chaque nom de façade est ``getattr``-able depuis ``apps.crm.services`` et
   ``is`` son objet d'origine ; idem pour les noms T-TRACE ;
4. ORDRE D'IMPORT EN PROCESSUS : chaque module cible existant s'importe EN
   PREMIER, à froid, sans cycle (un sous-processus ne prouverait rien :
   ``crm/apps.py`` charge déjà receivers puis services avant le test) ;
5. RÉSOLVEUR STATIQUE (le filet des imports paresseux que rien n'exécute) :
   pour tout fichier de backend/django_core ET de backend/parked, chaque nom
   importé d'un module ``apps.crm.<m>`` (absolu ou relatif), chaque
   ``<alias>.X`` d'un alias d'un tel module, chaque chaîne passée en premier
   argument de ``patch(...)`` et chaque ``patch.object(<alias>, 'X')`` est lié
   au premier niveau du module visé — jamais les docstrings (seul l'AST est
   lu) ; une seule exception figée (``EXCEPTIONS_RESOLVEUR``) ;
6. auto-test ROUGE d'abord : un corps altéré, une définition dupliquée et un
   nom de patch périmé sont tous signalés.

``modules_definissant_la_fixture()`` est l'aide UNIQUE qui rend les gardes
de lecture de source (tests_cad72, tests_cad145) suiveuses du code déplacé ;
``resoudre(nom)`` rend l'objet d'un nom du golden depuis le module qui le
définit (SPL2 l'utilise : jamais ``services.X``).
"""
import ast
import functools
import hashlib
import importlib
import json
import sys
from pathlib import Path

from django.test import SimpleTestCase

CRM_DIR = Path(__file__).resolve().parent
DJANGO_CORE = CRM_DIR.parents[1]
BACKEND = DJANGO_CORE.parent
PARKED = BACKEND / 'parked'
GOLDEN_PATH = CRM_DIR / 'golden' / 'services_split_ast.json'

#: Noms exemptés de l'unicité (redéfinis par chaque module du découpage).
EXEMPTES_UNICITE = frozenset({'logger'})

#: Seule exception figée du résolveur : importé par backend/parked, absent de
#: services.py avant le découpage (hors périmètre).
EXCEPTIONS_RESOLVEUR = frozenset({
    # (nom découpé : tests_cad72 interdit le nom entier dans django_core)
    ('backend/parked/compta/services.py', 'apps.crm.services',
     'get_or_create_parrainage' + '_template'),
})

_DEFINITIONS = (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef,
                ast.Assign, ast.AnnAssign)


# ── Golden ────────────────────────────────────────────────────────────────
def charger_golden():
    return json.loads(GOLDEN_PATH.read_text(encoding='utf-8'))


def _noms_definis(noeud):
    """Noms DÉFINIS (jamais importés) par un nœud de premier niveau."""
    if isinstance(noeud, (ast.FunctionDef, ast.AsyncFunctionDef,
                          ast.ClassDef)):
        return [noeud.name]
    if isinstance(noeud, ast.Assign):
        return [n.id for cible in noeud.targets for n in ast.walk(cible)
                if isinstance(n, ast.Name)]
    if isinstance(noeud, ast.AnnAssign) and isinstance(
            noeud.target, ast.Name):
        return [noeud.target.id]
    return []


@functools.lru_cache(maxsize=64)
def definitions_du_texte(texte):
    """``definitions`` d'un texte source (mis en cache : services.py est
    relu par chaque appel de ``resoudre``)."""
    return definitions(ast.parse(texte))


def definitions(arbre):
    """``{nom: [nœuds]}`` des définitions de premier niveau d'un module."""
    out = {}
    for noeud in arbre.body:
        if isinstance(noeud, _DEFINITIONS):
            for nom in _noms_definis(noeud):
                out.setdefault(nom, []).append(noeud)
    return out


def genre(noeud):
    if isinstance(noeud, ast.ClassDef):
        return 'class'
    if isinstance(noeud, (ast.FunctionDef, ast.AsyncFunctionDef)):
        return 'def'
    return 'assign'


def empreinte(noeuds):
    """sha256 de ``ast.dump`` (sans positions) du ou des nœuds définissants."""
    texte = '\n'.join(ast.dump(n) for n in noeuds)
    return hashlib.sha256(texte.encode('utf-8')).hexdigest()


def modules_du_decoupage(golden):
    cibles = {s['cible'] for s in golden['symboles'].values() if s['cible']}
    return ['services'] + sorted(cibles)


def sources_du_decoupage(golden, racine=CRM_DIR):
    """``{module: texte}`` des modules du découpage qui existent déjà."""
    out = {}
    for module in modules_du_decoupage(golden):
        chemin = racine / f'{module}.py'
        if chemin.exists():
            out[module] = chemin.read_text(encoding='utf-8')
    return out


def verifier_definitions(golden, sources):
    """Invariants 1 et 2 sur des TEXTES (l'auto-test leur passe des copies
    altérées). Rend la liste des écarts, vide si tout est conforme."""
    defs = {m: definitions_du_texte(texte) for m, texte in sources.items()}
    ecarts = []
    for nom, attendu in sorted(golden['symboles'].items()):
        if nom in EXEMPTES_UNICITE:
            continue
        autorises = {'services', attendu['cible'] or 'services'}
        hotes = [m for m in defs if nom in defs[m]]
        if not hotes:
            ecarts.append(f'{nom} : défini nulle part (attendu dans '
                          f'{sorted(autorises)})')
            continue
        if len(hotes) > 1:
            ecarts.append(f'{nom} : défini deux fois ({", ".join(hotes)})')
        for module in hotes:
            if module not in autorises:
                ecarts.append(f'{nom} : défini ailleurs ({module}.py), '
                              f'cible = {attendu["cible"]}')
            noeuds = defs[module][nom]
            if len(noeuds) != attendu['noeuds']:
                ecarts.append(f'{nom} : {len(noeuds)} définition(s) dans '
                              f'{module}.py, {attendu["noeuds"]} attendue(s)')
            elif empreinte(noeuds) != attendu['sha256']:
                ecarts.append(f'{nom} : corps modifié dans {module}.py '
                              f'(empreinte AST différente)')
    return ecarts


def module_definissant(nom, golden=None, sources=None):
    golden = golden or charger_golden()
    sources = sources if sources is not None else sources_du_decoupage(golden)
    for module, texte in sources.items():
        if nom in definitions_du_texte(texte):
            return module
    return None


def resoudre(nom):
    """L'objet d'un nom du golden, pris dans le module qui le DÉFINIT."""
    module = module_definissant(nom)
    if module is None:
        raise LookupError(f'{nom} : défini dans aucun module du découpage')
    return getattr(importlib.import_module(f'apps.crm.{module}'), nom)


def modules_definissant_la_fixture():
    """Chemins des modules du découpage qui définissent au moins un nom du
    golden — l'aide unique des gardes de lecture de source (tests_cad72,
    tests_cad145) : elles suivent ainsi le code déplacé sans s'affaiblir."""
    golden = charger_golden()
    noms = set(golden['symboles'])
    out = []
    for module, texte in sources_du_decoupage(golden).items():
        if noms & set(definitions_du_texte(texte)):
            out.append(CRM_DIR / f'{module}.py')
    return out


# ── Résolveur statique ────────────────────────────────────────────────────
def fichiers_a_resoudre():
    """``{chemin relatif au dépôt: texte}`` de backend/django_core + parked."""
    out = {}
    for racine in (DJANGO_CORE, PARKED):
        if not racine.exists():
            continue
        for chemin in racine.rglob('*.py'):
            if '__pycache__' in chemin.parts or 'node_modules' in chemin.parts:
                continue
            rel = chemin.relative_to(BACKEND.parent).as_posix()
            texte = chemin.read_text(encoding='utf-8')
            # Filtre sûr : viser un module apps.crm exige « apps.crm » ou
            # « crm » importé de « apps » dans le texte, sauf un import
            # relatif depuis apps/crm (pris par chemin).
            if ('apps.crm' in texte or 'import crm' in texte
                    or rel.startswith(_PREFIXE_CRM)):
                out[rel] = texte
    return out


_PREFIXE_CRM = 'backend/django_core/apps/crm/'


def _paquet_du_fichier(rel):
    """Paquet pointé d'un fichier de backend/django_core (imports relatifs)."""
    prefixe = 'backend/django_core/'
    if not rel.startswith(prefixe):
        return None
    parties = rel[len(prefixe):].split('/')
    return '.'.join(parties[:-1])


class LiaisonsCrm:
    """Noms liés au premier niveau des modules ``apps.crm.<m>`` (fichier ou
    paquet). ``surcharges`` remplace un texte (auto-test)."""

    def __init__(self, surcharges=None):
        self.surcharges = surcharges or {}
        self._cache = {}
        self._modules = {}

    def chemin(self, module):
        """Chemin du fichier d'un module pointé ``apps.crm...``, ou None."""
        parties = module.split('.')
        if parties[:2] != ['apps', 'crm'] or len(parties) < 3:
            return None
        base = DJANGO_CORE.joinpath(*parties)
        if base.with_suffix('.py').exists() or (
                module in self.surcharges):
            return base.with_suffix('.py')
        if (base / '__init__.py').exists():
            return base / '__init__.py'
        return None

    def est_module(self, module):
        if module not in self._modules:
            self._modules[module] = (module in self.surcharges
                                     or self.chemin(module) is not None)
        return self._modules[module]

    def noms(self, module):
        """Ensemble des noms liés, ou None si non résoluble statiquement
        (import étoile, ``__getattr__`` de module)."""
        if module in self._cache:
            return self._cache[module]
        if module in self.surcharges:
            texte = self.surcharges[module]
            chemin = None
        else:
            chemin = self.chemin(module)
            texte = chemin.read_text(encoding='utf-8') if chemin else None
        if texte is None:
            self._cache[module] = None
            return None
        noms = set()
        resolvable = True
        for noeud in ast.parse(texte).body:
            if isinstance(noeud, _DEFINITIONS):
                noms.update(_noms_definis(noeud))
            elif isinstance(noeud, ast.Import):
                noms.update((a.asname or a.name.split('.')[0])
                            for a in noeud.names)
            elif isinstance(noeud, ast.ImportFrom):
                for a in noeud.names:
                    if a.name == '*':
                        resolvable = False
                    noms.add(a.asname or a.name)
            elif isinstance(noeud, (ast.If, ast.Try, ast.With, ast.For)):
                for sous in ast.walk(noeud):
                    if isinstance(sous, _DEFINITIONS):
                        noms.update(_noms_definis(sous))
                    elif isinstance(sous, (ast.Import, ast.ImportFrom)):
                        noms.update((a.asname or a.name.split('.')[0])
                                    for a in sous.names)
        if '__getattr__' in noms:
            resolvable = False
        if chemin is not None and chemin.name == '__init__.py':
            for enfant in chemin.parent.iterdir():
                if enfant.suffix == '.py':
                    noms.add(enfant.stem)
                elif (enfant / '__init__.py').exists():
                    noms.add(enfant.name)
        self._cache[module] = noms if resolvable else None
        return self._cache[module]


def _resoudre_relatif(paquet, niveau, module):
    if paquet is None:
        return None
    parties = paquet.split('.') if paquet else []
    if niveau > 1:
        parties = parties[:len(parties) - (niveau - 1)]
    base = '.'.join(parties)
    if module:
        return f'{base}.{module}' if base else module
    return base


def _nom_pointe(noeud):
    parties = []
    while isinstance(noeud, ast.Attribute):
        parties.append(noeud.attr)
        noeud = noeud.value
    if isinstance(noeud, ast.Name):
        parties.append(noeud.id)
        return '.'.join(reversed(parties))
    return None


def _est_appel_patch(func):
    """``patch(...)`` / ``mock.patch(...)`` (pas ``patch.object``)."""
    if isinstance(func, ast.Name):
        return func.id == 'patch'
    return isinstance(func, ast.Attribute) and func.attr == 'patch'


def _est_patch_object(func):
    return (isinstance(func, ast.Attribute) and func.attr == 'object'
            and _est_appel_patch(func.value))


class _Visiteur(ast.NodeVisitor):
    """Parcourt un fichier ; ``portees`` = pile de ``{alias: module|None}``."""

    def __init__(self, rel, liaisons, ecarts):
        self.rel = rel
        self.paquet = _paquet_du_fichier(rel)
        self.liaisons = liaisons
        self.ecarts = ecarts
        self.portees = [{}]

    # — liaisons —
    def _lier(self, alias, module):
        self.portees[-1][alias] = module

    def _module_de(self, alias):
        for portee in reversed(self.portees):
            if alias in portee:
                return portee[alias]
        return None

    def _exiger(self, module, nom, ligne, comment):
        if nom.startswith('__') and nom.endswith('__'):
            return  # attribut de module (__file__, __doc__…)
        noms = self.liaisons.noms(module)
        if noms is None or nom in noms:
            return
        if (self.rel, module, nom) in EXCEPTIONS_RESOLVEUR:
            return
        self.ecarts.append(
            f'{self.rel}:{ligne} : {comment} `{module}.{nom}` — non lié au '
            f'premier niveau de {module}')

    def visit_Import(self, noeud):
        for a in noeud.names:
            if a.asname and self.liaisons.est_module(a.name):
                self._lier(a.asname, a.name)
            elif not a.asname:
                self._lier(a.name.split('.')[0], None)

    def visit_ImportFrom(self, noeud):
        if noeud.level:
            module = _resoudre_relatif(self.paquet, noeud.level, noeud.module)
        else:
            module = noeud.module
        if not module:
            return
        for a in noeud.names:
            alias = a.asname or a.name
            if a.name == '*':
                continue
            sous_module = f'{module}.{a.name}'
            if self.liaisons.est_module(sous_module):
                self._lier(alias, sous_module)
                continue
            self._lier(alias, None)
            if self.liaisons.est_module(module):
                self._exiger(module, a.name, noeud.lineno, 'import de')

    def _portee(self, noeud):
        self.portees.append({})
        args = getattr(noeud, 'args', None)
        if args is not None:
            for arg in (args.posonlyargs + args.args + args.kwonlyargs):
                self._lier(arg.arg, None)
        self.generic_visit(noeud)
        self.portees.pop()

    visit_FunctionDef = visit_AsyncFunctionDef = visit_Lambda = _portee

    def visit_ClassDef(self, noeud):
        self.portees.append({})
        self.generic_visit(noeud)
        self.portees.pop()

    def visit_Name(self, noeud):
        if isinstance(noeud.ctx, ast.Store):
            self._lier(noeud.id, None)

    def visit_Attribute(self, noeud):
        if isinstance(noeud.ctx, ast.Load):
            pointe = _nom_pointe(noeud)
            if pointe and isinstance(noeud.value, ast.Name):
                module = self._module_de(noeud.value.id)
                if module:
                    self._exiger(module, noeud.attr, noeud.lineno, 'accès')
            elif pointe and pointe.startswith('apps.crm.'):
                self._verifier_chaine(pointe, noeud.lineno, 'accès')
        self.generic_visit(noeud)

    def _verifier_chaine(self, pointe, ligne, comment):
        """``apps.crm.<m>[.<sous>].<nom>[...]`` : ``nom`` lié dans ``<m>``."""
        parties = pointe.split('.')
        module = None
        i = 2
        while i < len(parties):
            candidat = '.'.join(parties[:i + 1])
            if self.liaisons.est_module(candidat):
                module = candidat
                i += 1
            else:
                break
        if module is None or i >= len(parties):
            return
        self._exiger(module, parties[i], ligne, comment)

    def visit_Call(self, noeud):
        if _est_appel_patch(noeud.func) and noeud.args:
            premier = noeud.args[0]
            if isinstance(premier, ast.Constant) and isinstance(
                    premier.value, str) and premier.value.startswith(
                    'apps.crm.'):
                self._verifier_chaine(premier.value, noeud.lineno,
                                      'cible de patch')
        elif _est_patch_object(noeud.func) and len(noeud.args) >= 2:
            cible, attr = noeud.args[0], noeud.args[1]
            if isinstance(cible, ast.Name) and isinstance(
                    attr, ast.Constant) and isinstance(attr.value, str):
                module = self._module_de(cible.id)
                if module:
                    self._exiger(module, attr.value, noeud.lineno,
                                 'patch.object sur')
        self.generic_visit(noeud)


def verifier_resolution(fichiers, liaisons=None):
    """Invariant 5 sur ``{chemin: texte}`` ; rend la liste des écarts."""
    liaisons = liaisons or LiaisonsCrm()
    ecarts = []
    for rel, texte in sorted(fichiers.items()):
        try:
            arbre = ast.parse(texte)
        except SyntaxError:
            continue
        _Visiteur(rel, liaisons, ecarts).visit(arbre)
    return ecarts


# ── Tests ─────────────────────────────────────────────────────────────────
class ServicesSplitGoldenTests(SimpleTestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.golden = charger_golden()

    def test_definitions_uniques_dans_services_ou_leur_cible(self):
        ecarts = verifier_definitions(
            self.golden, sources_du_decoupage(self.golden))
        self.assertEqual(ecarts, [], '\n'.join(ecarts))

    def test_facade_atteignable_et_identique(self):
        services = importlib.import_module('apps.crm.services')
        for nom in sorted(self.golden['facade']):
            with self.subTest(nom=nom):
                self.assertTrue(hasattr(services, nom),
                                f'{nom} absent de la façade apps.crm.services')
                if nom in self.golden['symboles']:
                    self.assertIs(getattr(services, nom), resoudre(nom))

    def test_noms_t_trace_reexportes(self):
        services = importlib.import_module('apps.crm.services')
        visites = importlib.import_module('apps.crm.visites')
        for nom in self.golden['t_trace']:
            with self.subTest(nom=nom):
                self.assertIs(getattr(services, nom), getattr(visites, nom))

    def test_ordre_d_import_en_processus(self):
        """Chaque module cible existant s'importe EN PREMIER, à froid."""
        paquet = sys.modules['apps.crm']

        def garde(nom):
            return (nom == 'apps.crm' or nom == 'apps.crm.models'
                    or nom.startswith('apps.crm.models.')
                    or '.migrations' in nom)

        de_cote = {n: m for n, m in sys.modules.items()
                   if n.startswith('apps.crm.') and not garde(n)}
        attributs = dict(vars(paquet))
        try:
            for nom in de_cote:
                del sys.modules[nom]
                court = nom[len('apps.crm.'):]
                if '.' not in court and court in vars(paquet):
                    delattr(paquet, court)
            existants = [m for m in modules_du_decoupage(self.golden)
                         if m != 'services'
                         and (CRM_DIR / f'{m}.py').exists()]
            for module in existants + ['services']:
                with self.subTest(module=module):
                    importlib.import_module(f'apps.crm.{module}')
        finally:
            for nom in [n for n in sys.modules
                        if n.startswith('apps.crm.') and not garde(n)]:
                del sys.modules[nom]
            sys.modules.update(de_cote)
            for cle in list(vars(paquet)):
                if cle not in attributs:
                    delattr(paquet, cle)
            for cle, valeur in attributs.items():
                setattr(paquet, cle, valeur)

    def test_resolveur_statique_tous_les_appelants(self):
        ecarts = verifier_resolution(fichiers_a_resoudre())
        self.assertEqual(ecarts, [], '\n'.join(ecarts))

    def test_aide_des_gardes_de_source(self):
        chemins = modules_definissant_la_fixture()
        self.assertIn(CRM_DIR / 'services.py', chemins)
        self.assertNotIn(CRM_DIR / 'models.py', chemins)


class ServicesSplitAutoTestRouge(SimpleTestCase):
    """(d) Le golden ROUGIT sur une copie altérée : corps modifié, définition
    dupliquée, nom de patch périmé."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.golden = charger_golden()
        cls.sources = sources_du_decoupage(cls.golden)
        # Un nom assigné à une cible, défini par une fonction.
        cls.nom, cls.cible = next(
            (n, s['cible']) for n, s in sorted(cls.golden['symboles'].items())
            if s['cible'] and s['genre'] == 'def')

    def _segment(self, nom):
        texte = self.sources['services']
        noeud = definitions_du_texte(texte)[nom][0]
        return ast.get_source_segment(texte, noeud)

    def test_le_code_actuel_est_vert(self):
        self.assertEqual(verifier_definitions(self.golden, self.sources), [])

    def test_corps_altere_signale(self):
        segment = self._segment(self.nom)
        altere = segment.replace('\n', '\n    _altere = 1\n', 1)
        sources = dict(self.sources,
                       services=self.sources['services'].replace(
                           segment, altere, 1))
        ecarts = verifier_definitions(self.golden, sources)
        self.assertTrue(any(e.startswith(f'{self.nom} : corps modifié')
                            for e in ecarts), ecarts)

    def test_definition_dupliquee_signalee(self):
        sources = dict(self.sources)
        sources[self.cible] = self._segment(self.nom) + '\n'
        ecarts = verifier_definitions(self.golden, sources)
        self.assertTrue(any(e.startswith(f'{self.nom} : défini deux fois')
                            for e in ecarts), ecarts)

    def test_definition_ailleurs_signalee(self):
        autre = next(c for c in modules_du_decoupage(self.golden)
                     if c not in ('services', self.cible))
        segment = self._segment(self.nom)
        sources = dict(self.sources,
                       services=self.sources['services'].replace(
                           segment, '', 1))
        sources[autre] = segment + '\n'
        ecarts = verifier_definitions(self.golden, sources)
        self.assertTrue(any(e.startswith(f'{self.nom} : défini ailleurs')
                            for e in ecarts), ecarts)

    def test_nom_de_patch_perime_signale(self):
        fichiers = {
            'backend/django_core/apps/crm/tests_faux.py': (
                'from unittest import mock\n'
                'from unittest.mock import patch\n'
                'from apps.crm import services as crm_services\n'
                "@patch('apps.crm.services.nom_perime_spl1')\n"
                'def test_a():\n'
                "    with mock.patch.object(crm_services, 'autre_perime'):\n"
                '        crm_services.troisieme_perime()\n'
                '    from .services import quatrieme_perime  # noqa\n'),
        }
        ecarts = verifier_resolution(fichiers)
        for perime in ('nom_perime_spl1', 'autre_perime', 'troisieme_perime',
                       'quatrieme_perime'):
            self.assertTrue(any(perime in e for e in ecarts),
                            (perime, ecarts))

    def test_docstrings_ignorees(self):
        fichiers = {
            'backend/django_core/apps/crm/tests_faux.py': (
                '"""Voir apps.crm.services.nom_inexistant et '
                "patch('apps.crm.services.nom_inexistant')\"\"\"\n"),
        }
        self.assertEqual(verifier_resolution(fichiers), [])

    def test_deplacement_fidele_reste_vert(self):
        """Un déplacement conforme (nom retiré de services.py, recopié
        à l'identique dans sa cible) garde les invariants 1-2."""
        segment = self._segment(self.nom)
        sources = dict(self.sources,
                       services=self.sources['services'].replace(
                           segment, '', 1))
        sources[self.cible] = segment + '\n'
        self.assertEqual(verifier_definitions(self.golden, sources), [])
