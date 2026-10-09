"""SPL1 — golden AST + table de destination + résolveur statique des noms de
`crm/services.py` (capture seule : aucun déplacement).

Ce module est la GARDE de la scission de `crm/services.py` en modules
cibles (SPL3 à SPL25). Il est écrit une fois et n'est JAMAIS édité ensuite :
les invariants sont vrais à CHAQUE étape de la chaîne.

Invariants (sur `golden/services_split_ast.json`) :

1. UNICITÉ + EMPREINTE : chacun des noms de la table est défini, au premier
   niveau, soit dans `services.py`, soit dans son module `cible`, jamais
   ailleurs et jamais deux fois ; le sha256 de `ast.dump` du nœud est celui
   capturé avant tout déplacement (aucun corps changé).
2. FAÇADE : chaque nom importé de `services` par un fichier hors `apps/crm`
   (et les noms T-TRACE réexportés) reste `getattr`-able depuis
   `apps.crm.services` et `est` l'objet d'origine.
3. ORDRE D'IMPORT EN PROCESSUS : après `django.setup()`, les modules
   `apps.crm.*` (hors modèles, migrations, apps, tests) sont retirés de
   `sys.modules`, chaque module cible existant est importé EN PREMIER, puis
   `services` ; tout est restauré en `finally`.
4. RÉSOLVEUR STATIQUE : pour tout fichier de `backend/django_core` et
   `backend/parked`, chaque nom importé de `services` (ou d'un module cible),
   chaque `alias.X`, chaque chaîne de `patch(...)` et chaque
   `patch.object(<alias>, 'X')` doit être lié au premier niveau du module visé.
5. AUTO-TEST : un corps altéré, une définition dupliquée et un nom de patch
   périmé sont tous signalés.

Recapture (réservée aux tâches qui ajoutent volontairement un nom au premier
niveau de services.py) : `UPDATE_GOLDEN=1` avec `CIBLES_JSON=<fichier>` pour
une capture initiale.
"""
import ast
import hashlib
import importlib
import json
import os
import pathlib
import sys

from django.test import SimpleTestCase

_ICI = pathlib.Path(__file__).resolve().parent            # apps/crm
_DJANGO = _ICI.parents[1]                                 # backend/django_core
_BACKEND = _DJANGO.parent                                 # backend
_PARKED = _BACKEND / 'parked'
_GOLDEN = _ICI / 'golden' / 'services_split_ast.json'

#: Seule exception figée : importé par backend/parked/compta/services.py,
#: absent de services.py avant le découpage (hors périmètre).
EXCEPTIONS_NOMS = frozenset({'get_or_create_parrainage_template'})

_EXCLUS_REIMPORT = ('models', 'migrations', 'apps', 'management')


# --------------------------------------------------------------------------
# Lecture du premier niveau d'un module
# --------------------------------------------------------------------------
def _cibles_de_cible(noeud):
    """Noms liés par un nœud de premier niveau (def, class, affectation)."""
    if isinstance(noeud, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
        return [noeud.name]
    if isinstance(noeud, ast.Assign):
        return [x.id for t in noeud.targets for x in ast.walk(t)
                if isinstance(x, ast.Name)]
    if isinstance(noeud, ast.AnnAssign) and isinstance(noeud.target, ast.Name):
        return [noeud.target.id]
    return []


def noeuds_definis(source):
    """[(nom, genre, noeud)] pour chaque définition de premier niveau."""
    out = []
    for n in ast.parse(source).body:
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
            genre = 'def'
        elif isinstance(n, ast.ClassDef):
            genre = 'class'
        else:
            genre = 'assign'
        for nom in _cibles_de_cible(n):
            out.append((nom, genre, n))
    return out


def noms_lies(source):
    """Ensemble des noms liés au premier niveau (def, class, affectation,
    import), y compris dans les blocs `if`/`try` de premier niveau."""
    lies = set()

    def visite(corps):
        for n in corps:
            lies.update(_cibles_de_cible(n))
            if isinstance(n, ast.Import):
                for a in n.names:
                    lies.add(a.asname or a.name.split('.')[0])
            elif isinstance(n, ast.ImportFrom):
                for a in n.names:
                    if a.name != '*':
                        lies.add(a.asname or a.name)
            elif isinstance(n, ast.If):
                visite(n.body)
                visite(n.orelse)
            elif isinstance(n, ast.Try):
                visite(n.body)
                visite(n.orelse)
                visite(n.finalbody)
                for h in n.handlers:
                    visite(h.body)
    visite(ast.parse(source).body)
    return lies


def empreinte(noeud):
    return hashlib.sha256(ast.dump(noeud).encode('utf-8')).hexdigest()


def empreintes(source):
    """{nom: (genre, sha256, debut, fin)} — le premier nom rencontré gagne ;
    les doublons sont détectés par `noms_definis_plus_une_fois`."""
    out = {}
    for nom, genre, n in noeuds_definis(source):
        out.setdefault(nom, (genre, empreinte(n), n.lineno, n.end_lineno))
    return out


def noms_definis_plus_une_fois(source):
    vus, doubles = set(), set()
    for nom, _g, _n in noeuds_definis(source):
        if nom == 'logger':
            continue
        (doubles if nom in vus else vus).add(nom)
    return sorted(doubles)


# --------------------------------------------------------------------------
# Golden
# --------------------------------------------------------------------------
def charger_golden():
    with open(_GOLDEN, encoding='utf-8') as f:
        return json.load(f)


def _chemin_module(cible):
    return _ICI / ('services.py' if cible == 'services' else f'{cible}.py')


def modules_definissant_la_fixture():
    """Chemins des modules crm qui définissent (aujourd'hui) un nom de la
    fixture : `services.py` + chaque module cible déjà créé. Aide unique
    pour les gardes qui lisent le source de services."""
    golden = charger_golden()
    cibles = {v['cible'] for v in golden['noms'].values()}
    chemins = [_chemin_module('services')]
    chemins += [_chemin_module(c) for c in sorted(cibles)
                if _chemin_module(c).exists()]
    return chemins


def modules_cibles_existants():
    golden = charger_golden()
    return sorted({v['cible'] for v in golden['noms'].values()
                   if _chemin_module(v['cible']).exists()})


# --------------------------------------------------------------------------
# Résolveur statique
# --------------------------------------------------------------------------
def _paquet_du_fichier(chemin):
    """Paquet dotted du fichier (pour résoudre les imports relatifs)."""
    chemin = pathlib.Path(chemin).resolve()
    try:
        rel = chemin.relative_to(_DJANGO)
        parts = list(rel.parts)
    except ValueError:
        try:
            rel = chemin.relative_to(_PARKED)
        except ValueError:
            return ''
        parts = ['apps'] + list(rel.parts)
    parts = parts[:-1]
    return '.'.join(parts)


def references(source, paquet, cibles):
    """Références à `cibles` (dict module dotted -> ensemble de noms liés).

    Retourne [(module, nom, genre)] ; `genre` décrit l'origine (import,
    attribut, patch). Les docstrings ne sont jamais lues (AST)."""
    tree = ast.parse(source)
    alias = {}          # nom local -> module dotted visé
    refs = []

    def abs_module(noeud):
        if noeud.level:
            base = paquet.split('.') if paquet else []
            base = base[:len(base) - (noeud.level - 1)] if noeud.level > 1 else base
            return '.'.join(base + ([noeud.module] if noeud.module else []))
        return noeud.module or ''

    for n in ast.walk(tree):
        if isinstance(n, ast.ImportFrom):
            mod = abs_module(n)
            for a in n.names:
                if a.name == '*':
                    continue
                if mod in cibles:
                    refs.append((mod, a.name, 'import'))
                sous = f'{mod}.{a.name}' if mod else a.name
                if sous in cibles:
                    alias[a.asname or a.name] = sous
        elif isinstance(n, ast.Import):
            for a in n.names:
                if a.name in cibles and a.asname:
                    alias[a.asname] = a.name
    # chemins complets `apps.crm.services.X` utilisés directement

    def dotted(noeud):
        parts = []
        while isinstance(noeud, ast.Attribute):
            parts.append(noeud.attr)
            noeud = noeud.value
        if isinstance(noeud, ast.Name):
            parts.append(noeud.id)
            return '.'.join(reversed(parts))
        return None

    for n in ast.walk(tree):
        if isinstance(n, ast.Attribute):
            if isinstance(n.value, ast.Name) and n.value.id in alias:
                refs.append((alias[n.value.id], n.attr, 'attribut'))
            else:
                d = dotted(n.value)
                if d in cibles:
                    refs.append((d, n.attr, 'attribut'))
        elif isinstance(n, ast.Call):
            f = n.func
            est_patch = (isinstance(f, ast.Name) and f.id == 'patch') or (
                isinstance(f, ast.Attribute) and f.attr == 'patch')
            est_patch_object = (
                isinstance(f, ast.Attribute) and f.attr == 'object'
                and ((isinstance(f.value, ast.Name) and f.value.id == 'patch')
                     or (isinstance(f.value, ast.Attribute)
                         and f.value.attr == 'patch')))
            if est_patch and n.args and isinstance(n.args[0], ast.Constant) \
                    and isinstance(n.args[0].value, str):
                chaine = n.args[0].value
                for mod in cibles:
                    if chaine.startswith(mod + '.'):
                        reste = chaine[len(mod) + 1:]
                        refs.append((mod, reste.split('.')[0], 'patch'))
            if est_patch_object and len(n.args) >= 2:
                cible, nom = n.args[0], n.args[1]
                if isinstance(nom, ast.Constant) and isinstance(nom.value, str):
                    if isinstance(cible, ast.Name) and cible.id in alias:
                        refs.append((alias[cible.id], nom.value, 'patch.object'))
                    else:
                        d = dotted(cible)
                        if d in cibles:
                            refs.append((d, nom.value, 'patch.object'))
    return refs


def references_non_liees(source, paquet, cibles):
    """Références dont le nom n'est pas lié au premier niveau du module visé."""
    return sorted({
        (mod, nom, genre) for mod, nom, genre in references(source, paquet, cibles)
        if nom not in cibles[mod] and nom not in EXCEPTIONS_NOMS
        and not (nom.startswith('__') and nom.endswith('__'))
    })


def _fichiers_backend():
    racines = [_DJANGO] + ([_PARKED] if _PARKED.exists() else [])
    for racine in racines:
        for p in racine.rglob('*.py'):
            if '__pycache__' in p.parts or 'node_modules' in p.parts:
                continue
            yield p


def _cibles_dotted():
    """{module dotted: ensemble de noms liés} pour services + cibles existants."""
    out = {'apps.crm.services': noms_lies(
        _chemin_module('services').read_text(encoding='utf-8'))}
    for c in modules_cibles_existants():
        out[f'apps.crm.{c}'] = noms_lies(
            _chemin_module(c).read_text(encoding='utf-8'))
    return out


def noms_facade():
    """{nom: [fichiers hors apps/crm]} importés de `services` (sans les
    exceptions figées) — calculé sur l'arbre courant."""
    cibles = {'apps.crm.services': set()}
    facade = {}
    crm = _ICI.resolve()
    for p in _fichiers_backend():
        if crm in p.resolve().parents:
            continue
        try:
            src = p.read_text(encoding='utf-8')
        except (OSError, UnicodeDecodeError):
            continue
        if 'crm' not in src or 'services' not in src:
            continue
        try:
            refs = references(src, _paquet_du_fichier(p), cibles)
        except SyntaxError:
            continue
        for _mod, nom, _g in refs:
            if nom in EXCEPTIONS_NOMS:
                continue
            facade.setdefault(nom, set()).add(
                p.resolve().relative_to(_BACKEND).as_posix())
    return {k: sorted(v) for k, v in sorted(facade.items())}


def noms_t_trace():
    src = _chemin_module('services').read_text(encoding='utf-8')
    out = []
    for n in ast.parse(src).body:
        if isinstance(n, ast.ImportFrom) and n.level == 1 and n.module == 'visites':
            out += [a.name for a in n.names]
    return sorted(out)


def capturer(table_cibles):
    """Construit le golden depuis l'arbre courant (capture initiale)."""
    src = _chemin_module('services').read_text(encoding='utf-8')
    emp = empreintes(src)
    noms = {}
    for cible, liste in table_cibles.items():
        for nom in liste:
            genre, sha, debut, fin = emp[nom]
            noms[nom] = {'genre': genre, 'sha256': sha, 'debut': debut,
                         'fin': fin, 'cible': cible}
    return {
        'version': 1,
        'noms': dict(sorted(noms.items())),
        'facade': noms_facade(),
        't_trace': noms_t_trace(),
    }


# --------------------------------------------------------------------------
# Tests
# --------------------------------------------------------------------------
def _definitions_courantes():
    """{nom: [(module, genre, sha)]} pour services + cibles existants."""
    out = {}
    for mod in ['services'] + modules_cibles_existants():
        src = _chemin_module(mod).read_text(encoding='utf-8')
        for nom, genre, n in noeuds_definis(src):
            out.setdefault(nom, []).append((mod, genre, empreinte(n)))
    return out


class GoldenCaptureTests(SimpleTestCase):

    def test_capture_si_demandee(self):
        if os.environ.get('UPDATE_GOLDEN') != '1':
            self.skipTest('UPDATE_GOLDEN=1 requis')
        with open(os.environ['CIBLES_JSON'], encoding='utf-8') as f:
            table = json.load(f)
        _GOLDEN.parent.mkdir(parents=True, exist_ok=True)
        with open(_GOLDEN, 'w', encoding='utf-8') as f:
            json.dump(capturer(table), f, indent=1, ensure_ascii=False,
                      sort_keys=True)
            f.write('\n')


class ScissionServicesGoldenTests(SimpleTestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.golden = charger_golden()

    def test_la_table_couvre_553_noms(self):
        self.assertEqual(len(self.golden['noms']), 553)

    def test_chaque_nom_defini_une_fois_au_bon_endroit_corps_identique(self):
        courant = _definitions_courantes()
        erreurs = []
        for nom, info in self.golden['noms'].items():
            defs = courant.get(nom, [])
            if len(defs) != 1:
                erreurs.append(f'{nom}: défini {len(defs)} fois {defs}')
                continue
            mod, genre, sha = defs[0]
            if mod not in ('services', info['cible']):
                erreurs.append(f'{nom}: dans {mod}, attendu services ou '
                               f"{info['cible']}")
            if sha != info['sha256']:
                erreurs.append(f'{nom}: corps modifié (empreinte AST)')
            if genre != info['genre']:
                erreurs.append(f'{nom}: genre {genre} != {info["genre"]}')
        self.assertEqual(erreurs, [])

    def test_aucun_doublon_dans_chaque_module(self):
        for mod in ['services'] + modules_cibles_existants():
            src = _chemin_module(mod).read_text(encoding='utf-8')
            with self.subTest(module=mod):
                self.assertEqual(noms_definis_plus_une_fois(src), [])

    def test_facade_getattr_et_identite(self):
        from apps.crm import services
        golden = self.golden
        for nom in list(golden['facade']):
            with self.subTest(nom=nom):
                self.assertTrue(hasattr(services, nom),
                                f'{nom} absent de apps.crm.services')
                info = golden['noms'].get(nom)
                if info and _chemin_module(info['cible']).exists():
                    origine = importlib.import_module(
                        f"apps.crm.{info['cible']}")
                    self.assertIs(getattr(services, nom),
                                  getattr(origine, nom))
        visites = importlib.import_module('apps.crm.visites')
        for nom in golden['t_trace']:
            with self.subTest(t_trace=nom):
                self.assertIs(getattr(services, nom), getattr(visites, nom))

    def test_ordre_d_import_en_processus(self):
        """R3 : un sous-processus ne prouve rien ; on rejoue le chargement à
        froid dans CE processus, modules cibles d'abord."""
        crm = importlib.import_module('apps.crm')
        sauvegarde = {}
        for cle in list(sys.modules):
            if not cle.startswith('apps.crm.'):
                continue
            court = cle.split('.')[2]
            if court in _EXCLUS_REIMPORT or court.startswith('tests'):
                continue
            sauvegarde[cle] = sys.modules.pop(cle)
            if cle.count('.') == 2:
                try:
                    delattr(crm, cle.split('.')[2])
                except AttributeError:
                    pass
        try:
            for cible in modules_cibles_existants():
                importlib.import_module(f'apps.crm.{cible}')
            neuf = importlib.import_module('apps.crm.services')
            for nom in self.golden['facade']:
                self.assertTrue(hasattr(neuf, nom), nom)
        finally:
            for cle in list(sys.modules):
                if cle.startswith('apps.crm.') and cle not in sauvegarde:
                    court = cle.split('.')[2]
                    if not (court in _EXCLUS_REIMPORT
                            or court.startswith('tests')) \
                            and cle.count('.') == 2:
                        # sera remplacé ci-dessous si une version d'origine existe
                        sys.modules.pop(cle, None)
            for cle, mod in sauvegarde.items():
                sys.modules[cle] = mod
                if cle.count('.') == 2:
                    setattr(crm, cle.split('.')[2], mod)

    def test_resolveur_statique_toutes_les_references_sont_liees(self):
        cibles = _cibles_dotted()
        non_liees = []
        for p in _fichiers_backend():
            try:
                src = p.read_text(encoding='utf-8')
            except (OSError, UnicodeDecodeError):
                continue
            est_crm = _ICI.resolve() in p.resolve().parents
            if not (est_crm or 'crm' in src):
                continue
            try:
                manques = references_non_liees(
                    src, _paquet_du_fichier(p), cibles)
            except SyntaxError:
                continue
            for mod, nom, genre in manques:
                non_liees.append(
                    f'{p.resolve().relative_to(_BACKEND).as_posix()}: '
                    f'{mod}.{nom} ({genre})')
        self.assertEqual(non_liees, [])


class AutoTestResolveurTests(SimpleTestCase):
    """(d) Le garde-fou se prouve lui-même : trois dérives synthétiques sont
    signalées."""

    SOURCE = (
        "import logging\n"
        "logger = logging.getLogger(__name__)\n"
        "def f(x):\n    return x + 1\n"
        "VALEUR = 3\n"
    )

    def test_corps_altere_signale(self):
        avant = empreintes(self.SOURCE)['f'][1]
        apres = empreintes(self.SOURCE.replace('x + 1', 'x + 2'))['f'][1]
        self.assertNotEqual(avant, apres)

    def test_definition_dupliquee_signalee(self):
        dup = self.SOURCE + "def f(x):\n    return x\n"
        self.assertEqual(noms_definis_plus_une_fois(self.SOURCE), [])
        self.assertEqual(noms_definis_plus_une_fois(dup), ['f'])

    def test_logger_exempte_de_l_unicite(self):
        dup = self.SOURCE + "logger = logging.getLogger('autre')\n"
        self.assertEqual(noms_definis_plus_une_fois(dup), [])

    def test_nom_de_patch_perime_signale(self):
        cibles = {'apps.crm.services': noms_lies(self.SOURCE)}
        client = (
            "from unittest.mock import patch\n"
            "from apps.crm import services\n"
            "from apps.crm.services import f, disparu\n"
            "def t():\n"
            "    patch('apps.crm.services.f')\n"
            "    patch('apps.crm.services.perime')\n"
            "    patch.object(services, 'perime2')\n"
            "    services.VALEUR\n"
            "    services.perime3\n"
        )
        manques = {(m, n) for m, n, _g in
                   references_non_liees(client, 'apps.crm', cibles)}
        self.assertEqual(manques, {
            ('apps.crm.services', 'disparu'),
            ('apps.crm.services', 'perime'),
            ('apps.crm.services', 'perime2'),
            ('apps.crm.services', 'perime3'),
        })

    def test_import_relatif_resolu(self):
        cibles = {'apps.crm.services': noms_lies(self.SOURCE)}
        client = "from .services import f, inconnu\n"
        manques = {n for _m, n, _g in
                   references_non_liees(client, 'apps.crm', cibles)}
        self.assertEqual(manques, {'inconnu'})
