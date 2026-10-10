"""SPL70 — golden STATIQUE de la scission de `apps/crm` (capture seule).

Aucun filet ne prouvait qu'un déplacement de la famille SPL74-SPL95 garde la
sortie à l'identique. Ce module écrit UN json PAR SURFACE sous
`golden/scission_crm/` (jamais un json unique : une tâche qui ajoute un champ
ou une @action re-capture SES seuls fichiers) :

1. `routes__<ViewSet>.json` — motif, nom, classe de vue et actions_map de
   chaque route de `apps.crm.urls` (vues simples : `routes__vues_simples`).
2. `permissions__<ViewSet>.json` — pour chaque viewset du routeur x (actions
   standard + `get_extra_actions()`) x méthode HTTP : la liste des
   permissions (classe + code fin) rendue par `get_permissions()` ; y compris
   `__action_absente__`, qui prouve le repli final.
3. `serialiseur__<Classe>.json` — champs dans l'ordre (nom, classe de champ,
   read_only, required) de chaque sérialiseur crm.
4. `modele__<Modele>.json` — label, db_table, `deconstruct()` ordonné des
   champs directs, relations inverses (ENSEMBLE) ; plus
   `makemigrations crm --check --dry-run` sans changement.
5. `recepteurs.json` — pour chaque signal, la liste ORDONNÉE des
   `dispatch_uid` `crm_*` ; plus une assertion AST : aucun `@receiver` dans
   apps/crm hors `receivers.py` et `tiers_bridge.py`.
6. `facade__selectors.json`, `facade__models.json` — noms exposés (privés
   compris) avec leur `__qualname__` ; callables référencés par les
   migrations.
7. `ast__<fichier_origine>.json` — sha256 de `ast.dump` de chaque symbole de
   premier niveau (et chaque méthode de LeadViewSet / RelanceEtapeViewSet)
   des fichiers d'origine, retrouvé PAR NOM dans tout module `apps.crm.*`.
   Les `ImportFrom` relatifs sont réduits à leurs noms importés ; pour les
   récepteurs, le nom du `def` et les décorateurs sont exclus ;
   `LeadViewSet.get_permissions` est exclu (la matrice 2 est son filet).

Aucun json ne contient de `__module__` : tout est identifié par nom de
classe, `__qualname__` ou dispatch_uid, pour qu'un déplacement fidèle reste
vert sans y toucher.

Règle : une tâche NON-SPL qui change légitimement une surface capturée
re-capture ses seuls fichiers (`UPDATE_GOLDEN=1`) et le dit dans son commit ;
une tâche SPL ne re-capture JAMAIS. Une surface NOUVELLE (absente de
`_index.json`) n'est pas protégée tant qu'elle n'est pas capturée ; une
surface capturée qui DISPARAÎT fait échouer le test.

Capture : `UPDATE_GOLDEN=1 python manage.py test apps.crm.tests_scission_golden`
(le test d'index échoue tant que les json manquent).
"""
import ast
import copy
import datetime
import decimal
import enum
import hashlib
import importlib
import inspect
import json
import os
import pathlib
import re
import uuid
from io import StringIO

from django.apps import apps as django_apps
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase
from rest_framework import serializers as drf_serializers
from rest_framework.request import Request
from rest_framework.test import APIRequestFactory

from authentication.models import Company
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken
from testkit.time import frozen
from apps.crm import horaires, stages
from apps.crm.models import (
    Appointment, Client, Lead, Playbook, PlaybookEtape, RelanceEtape,
    SalleVente)
from apps.parametres.models import CompanyProfile

User = get_user_model()

_ICI = pathlib.Path(__file__).resolve().parent
_GOLDEN = _ICI / 'golden' / 'scission_crm'
_FICHIERS_ORIGINE = ('views', 'selectors', 'serializers', 'models',
                     'receivers')
_METHODES_UNE_A_UNE = ('LeadViewSet', 'RelanceEtapeViewSet')
_RECEPTEURS_HORS_FICHIER = ('receivers.py', 'tiers_bridge.py')
_METHODES_STANDARD = (('list', 'GET'), ('create', 'POST'),
                      ('retrieve', 'GET'), ('update', 'PUT'),
                      ('partial_update', 'PATCH'), ('destroy', 'DELETE'))
_CAPTURE = os.environ.get('UPDATE_GOLDEN') == '1'


# --------------------------------------------------------------------------
# Normalisation JSON
# --------------------------------------------------------------------------
def norm(v):
    """Valeur -> JSON stable (aucune adresse mémoire, aucun __module__)."""
    if v is None or isinstance(v, (bool, int, float)):
        return v
    if isinstance(v, str):
        return str(v)
    if isinstance(v, decimal.Decimal):
        return f'Decimal({v})'
    if isinstance(v, (datetime.date, datetime.time, datetime.timedelta)):
        return repr(v)
    if isinstance(v, uuid.UUID):
        return str(v)
    if isinstance(v, enum.Enum):
        return f'{type(v).__name__}.{v.name}'
    if isinstance(v, dict):
        return {str(k): norm(x) for k, x in sorted(
            v.items(), key=lambda kv: str(kv[0]))}
    if isinstance(v, (list, tuple)):
        return [norm(x) for x in v]
    if isinstance(v, (set, frozenset)):
        return sorted((norm(x) for x in v), key=json.dumps)
    if inspect.isclass(v):
        return f'classe:{v.__qualname__}'
    if callable(v) and hasattr(v, '__qualname__'):
        return f'callable:{v.__qualname__}'
    if hasattr(v, 'deconstruct'):
        try:
            _chemin, args, kwargs = v.deconstruct()[-3:]
            return {'objet': type(v).__qualname__, 'args': norm(args),
                    'kwargs': norm(kwargs)}
        except Exception:  # noqa: BLE001
            pass
    if hasattr(v, '_proxy____cast'):          # chaîne paresseuse
        return str(v)
    return f'objet:{type(v).__qualname__}'


def ecrire(nom, contenu):
    _GOLDEN.mkdir(parents=True, exist_ok=True)
    with open(_GOLDEN / nom, 'w', encoding='utf-8') as f:
        json.dump(contenu, f, indent=1, ensure_ascii=False, sort_keys=True)
        f.write('\n')


def lire(nom):
    with open(_GOLDEN / nom, encoding='utf-8') as f:
        return json.load(f)


def nom_fichier(prefixe, nom):
    return f'{prefixe}__{re.sub(r"[^0-9A-Za-z_.-]", "_", nom)}.json'


# --------------------------------------------------------------------------
# Surfaces (calculées sur l'arbre courant)
# --------------------------------------------------------------------------
def _routes():
    """{viewset: [route]} — vues simples sous la clé `vues_simples`."""
    from apps.crm import urls as crm_urls
    from django.urls import URLPattern, URLResolver
    out = {}

    def visite(patterns, prefixe):
        for p in patterns:
            motif = prefixe + str(p.pattern)
            if isinstance(p, URLResolver):
                visite(p.url_patterns, motif)
            elif isinstance(p, URLPattern):
                cb = p.callback
                cls = getattr(cb, 'cls', None)
                actions = getattr(cb, 'actions', None)
                cle = (cls.__name__ if cls is not None and actions is not None
                       else 'vues_simples')
                out.setdefault(cle, []).append({
                    'motif': motif, 'nom': p.name,
                    'vue': (cls.__name__ if cls is not None
                            else getattr(cb, '__name__', type(cb).__name__)),
                    # DRF ajoute 'head' (= 'get') à ce dict PARTAGÉ au premier GET
                    # servi : l'ignorer, sinon le golden dépend de l'ordre des tests.
                    'actions_map': norm({m: a for m, a in actions.items()
                                         if not (m == 'head' and a == actions.get('get'))})
                    if actions else None})
    visite(crm_urls.urlpatterns, '')
    return {k: sorted(v, key=lambda r: (r['motif'], str(r['nom'])))
            for k, v in out.items()}


def _viewsets():
    from apps.crm import urls as crm_urls
    out = {}
    for p in crm_urls.router.registry:
        out[p[1].__name__] = p[1]
    return dict(sorted(out.items()))


def _rendre_permission(p):
    if hasattr(p, 'op1') and hasattr(p, 'op2'):
        return {'classe': type(p).__name__, 'op1': _rendre_permission(p.op1),
                'op2': _rendre_permission(p.op2)}
    if hasattr(p, 'op1'):
        return {'classe': type(p).__name__, 'op1': _rendre_permission(p.op1)}
    attrs = {k: norm(v) for k, v in sorted(vars(p).items())
             if not k.startswith('__') and not callable(v)}
    return {'classe': type(p).__name__, 'attrs': attrs}


def _permissions(cls, user):
    factory = APIRequestFactory()
    lignes = []
    cas = list(_METHODES_STANDARD)
    for extra in cls.get_extra_actions():
        mapping = getattr(extra, 'mapping', None) or {}
        for methode in sorted(mapping) or ['get']:
            cas.append((extra.__name__, methode.upper()))
    cas.append(('__action_absente__', 'GET'))
    cas.append(('__action_absente__', 'POST'))
    for action, methode in sorted(set(cas)):
        vue = cls()
        vue.action = action
        vue.args, vue.kwargs, vue.format_kwarg = (), {}, None
        requete = Request(factory.generic(methode, '/'))
        requete.user = user
        vue.request = requete
        try:
            perms = [_rendre_permission(p) for p in vue.get_permissions()]
        except Exception as exc:  # noqa: BLE001 — l'erreur EST la valeur
            perms = [{'erreur': type(exc).__name__}]
        lignes.append({'action': action, 'methode': methode,
                       'permissions': perms})
    return lignes


def _serialiseurs():
    mod = importlib.import_module('apps.crm.serializers')
    out = {}
    for nom, obj in vars(mod).items():
        if (inspect.isclass(obj)
                and issubclass(obj, drf_serializers.BaseSerializer)
                and obj.__module__.startswith('apps.crm')
                and obj.__name__ == nom):
            out[nom] = obj
    return dict(sorted(out.items()))


def _champs_serialiseur(cls, requete):
    try:
        champs = cls(context={'request': requete}).fields
    except Exception as exc:  # noqa: BLE001
        return {'erreur': type(exc).__name__}
    return {'champs': [{'nom': n, 'classe': type(f).__name__,
                        'read_only': bool(f.read_only),
                        'required': bool(f.required)}
                       for n, f in champs.items()]}


def _modeles():
    return {m.__name__: m for m in sorted(
        django_apps.get_app_config('crm').get_models(),
        key=lambda m: m.__name__)}


def _empreinte_modele(m):
    champs = []
    for f in m._meta.local_fields + m._meta.local_many_to_many:
        _nom, chemin, args, kwargs = f.deconstruct()
        champs.append({'nom': f.name, 'type': chemin.rsplit('.', 1)[-1],
                       'args': norm(args), 'kwargs': norm(kwargs)})
    return {
        'label': m._meta.label, 'db_table': m._meta.db_table,
        'champs': champs,
        'relations_inverses': sorted(
            r.get_accessor_name() or '' for r in m._meta.related_objects),
    }


def _recepteurs():
    """{nom du signal: [dispatch_uid `crm_*` dans l'ordre de connexion]}.

    Les signaux sont nommés d'après leurs décorateurs `@receiver(<signal>)`
    de `receivers.py` / `tiers_bridge.py` (le nom ne dépend donc pas des
    modules déjà chargés) ; l'ordre vient du registre RÉEL du signal."""
    out = {}
    for nom_mod in ('receivers', 'tiers_bridge'):
        mod = importlib.import_module(f'apps.crm.{nom_mod}')
        arbre = ast.parse(pathlib.Path(mod.__file__).read_text(
            encoding='utf-8'))
        for n in ast.walk(arbre):
            if not isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            for d in n.decorator_list:
                if not (isinstance(d, ast.Call) and isinstance(
                        d.func, ast.Name) and d.func.id == 'receiver'
                        and d.args and isinstance(d.args[0], ast.Name)):
                    continue
                nom = d.args[0].id
                signal = getattr(mod, nom)
                uids = []
                for entree in signal.receivers:
                    cle = entree[0]
                    uid = cle[0] if isinstance(cle, tuple) else cle
                    if isinstance(uid, str) and uid.startswith('crm_'):
                        uids.append(uid)
                out[nom] = uids
    return dict(sorted(out.items()))


def _receivers_hors_fichiers():
    """Fichiers apps/crm (hors tests, golden, migrations) qui portent un
    décorateur `@receiver`, hors `receivers.py` et `tiers_bridge.py`."""
    trouves = []
    for chemin in _modules_source():
        if chemin.name in _RECEPTEURS_HORS_FICHIER:
            continue
        for n in ast.walk(ast.parse(chemin.read_text(encoding='utf-8'))):
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
                for d in n.decorator_list:
                    cible = d.func if isinstance(d, ast.Call) else d
                    nom = (cible.id if isinstance(cible, ast.Name)
                           else getattr(cible, 'attr', ''))
                    if nom == 'receiver':
                        trouves.append(f'{chemin.name}:{n.name}')
    return sorted(trouves)


def _facade(module):
    mod = importlib.import_module(f'apps.crm.{module}')
    out = {}
    for nom, v in sorted(vars(mod).items()):
        if nom.startswith('__') and nom.endswith('__'):
            continue
        if inspect.ismodule(v):
            out[nom] = 'module'
        else:
            out[nom] = getattr(v, '__qualname__', type(v).__qualname__)
    return out


def _refs_migrations():
    noms = set()
    for chemin in (_ICI / 'migrations').glob('*.py'):
        noms.update(re.findall(
            r'crm\.models\.(\w+)', chemin.read_text(encoding='utf-8')))
    return sorted(noms)


# --------------------------------------------------------------------------
# Empreintes AST
# --------------------------------------------------------------------------
class _Normalise(ast.NodeTransformer):
    def __init__(self, recepteur):
        self.recepteur = recepteur

    def visit_ImportFrom(self, node):
        if node.level:
            return ast.ImportFrom(module=None, names=node.names, level=0)
        return node

    def visit_FunctionDef(self, node):
        self.generic_visit(node)
        if self.recepteur:
            node.name = '_'
            node.decorator_list = []
        return node


def empreinte(noeud, recepteur=False):
    copie = _Normalise(recepteur).visit(copy.deepcopy(noeud))
    return hashlib.sha256(ast.dump(copie).encode('utf-8')).hexdigest()


def _modules_source():
    for chemin in sorted(_ICI.rglob('*.py')):
        rel = chemin.relative_to(_ICI).parts
        if (rel[0] in ('migrations', 'golden', 'management', '__pycache__')
                or chemin.name.startswith(('test_', 'tests'))
                or chemin.name in ('__init__.py',)):
            continue
        yield chemin


def _noms_noeud(n):
    if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
        return [n.name]
    if isinstance(n, ast.Assign):
        return [x.id for t in n.targets for x in ast.walk(t)
                if isinstance(x, ast.Name)]
    if isinstance(n, ast.AnnAssign) and isinstance(n.target, ast.Name):
        return [n.target.id]
    return []


def _symboles(chemin, recepteur):
    """{cle: sha} des symboles de premier niveau (méthodes de LeadViewSet et
    RelanceEtapeViewSet une à une) d'un fichier."""
    out = {}
    for n in ast.parse(chemin.read_text(encoding='utf-8')).body:
        if isinstance(n, ast.ClassDef) and n.name in _METHODES_UNE_A_UNE:
            for m in n.body:
                if isinstance(m, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    if (n.name, m.name) == ('LeadViewSet', 'get_permissions'):
                        continue
                    out[f'{n.name}.{m.name}'] = empreinte(m)
            continue
        for nom in _noms_noeud(n):
            out.setdefault(nom, empreinte(n, recepteur))
    return out


def _index_courant():
    """{nom ou Classe.methode: set(sha)} sur tous les modules crm ; une
    variante 'récepteur' (nom/décorateurs exclus) est indexée à part."""
    normal, recepteur = {}, {}
    for chemin in _modules_source():
        for n in ast.parse(chemin.read_text(encoding='utf-8')).body:
            if isinstance(n, ast.ClassDef):
                for m in n.body:
                    if isinstance(m, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        normal.setdefault(f'{n.name}.{m.name}', set()).add(
                            empreinte(m))
                        normal.setdefault(f'*.{m.name}', set()).add(
                            empreinte(m))
            for nom in _noms_noeud(n):
                normal.setdefault(nom, set()).add(empreinte(n))
                if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    recepteur.setdefault(nom, set()).add(
                        empreinte(n, recepteur=True))
    return normal, recepteur


# --------------------------------------------------------------------------
# Capture
# --------------------------------------------------------------------------
class _Base(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.company = Company.objects.create(
            nom='Scission Golden', slug='scission-golden')
        cls.user = User.objects.create_user(
            username='scission-resp', password='x',
            role_legacy='responsable', company=cls.company)


class CaptureTests(_Base):

    def test_capture_si_demandee(self):
        if not _CAPTURE:
            self.skipTest('UPDATE_GOLDEN=1 requis')
        index = {'routes': [], 'permissions': [], 'serialiseurs': [],
                 'modeles': [], 'ast': []}
        for nom, routes in _routes().items():
            ecrire(nom_fichier('routes', nom), routes)
            index['routes'].append(nom)
        for nom, cls in _viewsets().items():
            ecrire(nom_fichier('permissions', nom),
                   _permissions(cls, self.user))
            index['permissions'].append(nom)
        requete = Request(APIRequestFactory().get('/'))
        requete.user = self.user
        for nom, cls in _serialiseurs().items():
            ecrire(nom_fichier('serialiseur', nom),
                   _champs_serialiseur(cls, requete))
            index['serialiseurs'].append(nom)
        for nom, m in _modeles().items():
            ecrire(nom_fichier('modele', nom), _empreinte_modele(m))
            index['modeles'].append(nom)
        ecrire('recepteurs.json', {
            'par_signal': _recepteurs(),
            'hors_fichiers': _receivers_hors_fichiers()})
        ecrire('facade__selectors.json', {'noms': _facade('selectors')})
        ecrire('facade__models.json', {
            'noms': _facade('models'), 'refs_migrations': _refs_migrations()})
        for fichier in _FICHIERS_ORIGINE:
            symboles = _symboles(_ICI / f'{fichier}.py',
                                 fichier == 'receivers')
            ecrire(f'ast__{fichier}.py.json', {
                'recepteur': fichier == 'receivers', 'symboles': symboles})
            index['ast'].append(fichier)
        ecrire('_index.json', index)


# --------------------------------------------------------------------------
# Vérification
# --------------------------------------------------------------------------
class ScissionGoldenTests(_Base):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.index = lire('_index.json')       # absent = échec (rouge d'abord)

    def _comparer(self, nom_json, courant):
        self.assertEqual(
            courant, lire(nom_json), msg=f'{nom_json} a changé')

    def test_routes(self):
        courant = _routes()
        for nom in self.index['routes']:
            self.assertIn(nom, courant, f'surface routes {nom} disparue')
            self._comparer(nom_fichier('routes', nom), courant[nom])

    def test_permissions(self):
        courant = _viewsets()
        for nom in self.index['permissions']:
            self.assertIn(nom, courant, f'viewset {nom} disparu')
            self._comparer(nom_fichier('permissions', nom),
                           _permissions(courant[nom], self.user))

    def test_repli_final_isadminrole_capture(self):
        """Le repli `[IsAdminRole()]` d'une action absente est dans le golden
        d'au moins un viewset (la matrice 2 est le filet de SPL75)."""
        vu = False
        for nom in self.index['permissions']:
            for ligne in lire(nom_fichier('permissions', nom)):
                if ligne['action'] == '__action_absente__' and any(
                        p.get('classe') == 'IsAdminRole'
                        for p in ligne['permissions']):
                    vu = True
        self.assertTrue(vu)

    def test_serialiseurs(self):
        courant = _serialiseurs()
        requete = Request(APIRequestFactory().get('/'))
        requete.user = self.user
        for nom in self.index['serialiseurs']:
            self.assertIn(nom, courant, f'sérialiseur {nom} disparu')
            self._comparer(nom_fichier('serialiseur', nom),
                           _champs_serialiseur(courant[nom], requete))

    def test_modeles(self):
        courant = _modeles()
        for nom in self.index['modeles']:
            self.assertIn(nom, courant, f'modèle {nom} disparu')
            self._comparer(nom_fichier('modele', nom),
                           _empreinte_modele(courant[nom]))

    def test_aucune_migration_en_attente(self):
        sortie = StringIO()
        try:
            call_command('makemigrations', 'crm', '--check', '--dry-run',
                         stdout=sortie, stderr=sortie)
        except SystemExit:
            self.fail(f'migrations crm en attente :\n{sortie.getvalue()}')

    def test_recepteurs(self):
        attendu = lire('recepteurs.json')
        self.assertEqual(_recepteurs(), attendu['par_signal'])
        self.assertEqual(_receivers_hors_fichiers(),
                         attendu['hors_fichiers'])
        self.assertEqual(_receivers_hors_fichiers(), [])
        total = sum(len(v) for v in attendu['par_signal'].values())
        self.assertEqual(total, 26)             # 25 + crm_client_mirror_tiers

    def test_facades(self):
        for module in ('selectors', 'models'):
            attendu = lire(f'facade__{module}.json')
            courant = _facade(module)
            for nom, qualname in attendu['noms'].items():
                self.assertIn(nom, courant,
                              f'{module}.{nom} n\'est plus exposé')
                self.assertEqual(courant[nom], qualname, f'{module}.{nom}')
        models = importlib.import_module('apps.crm.models')
        for nom in lire('facade__models.json')['refs_migrations']:
            self.assertTrue(hasattr(models, nom),
                            f'models.{nom} référencé par une migration')

    def test_empreintes_ast(self):
        normal, recepteur = _index_courant()
        erreurs = []
        for fichier in self.index['ast']:
            golden = lire(f'ast__{fichier}.py.json')
            index = recepteur if golden['recepteur'] else normal
            for cle, sha in golden['symboles'].items():
                candidats = index.get(cle) or (
                    normal.get(cle) if golden['recepteur'] else None)
                if candidats is None and '.' in cle:
                    candidats = normal.get('*.' + cle.split('.', 1)[1])
                if not candidats:
                    erreurs.append(f'{fichier}: {cle} introuvable')
                elif sha not in candidats:
                    erreurs.append(f'{fichier}: {cle} corps modifié')
        self.assertEqual(erreurs, [])


# SPL71 — golden HTTP des écrans crm déplacés (capture seule).
#
# Les inventaires de SPL70 (ci-dessus) comparent des surfaces
# statiques ; aucun ne compare les RÉPONSES JSON lues par le cockpit des
# relances, la fiche lead, les clients, les rendez-vous, les playbooks et les
# salles de vente. Ce module rejoue ces appels sur une fixture déterministe et
# écrit UN json PAR APPEL sous `golden/scission_crm_http/` :
# `{"appel": "GET leads", "statut": 200, "corps": …}`.
#
# Déterminisme :
# - horloge gelée sur `GEL` (mercredi 30/09/2026 10 h Africa/Casablanca, la
#   constante de `tests_cockpit_gardes.py`) — seule l'horloge est gelée, aucune
#   vue, aucun sélecteur ni service crm n'est remplacé ;
# - noms, téléphones et dates fixes ;
# - normalisation : identifiants remappés dans l'ordre de création de la
#   fixture (`lead#1`, `etape#2`…), horodatages automatiques masqués, jeton de
#   la salle de vente masqué.
#
# Règle : une tâche NON-SPL qui change légitimement une réponse re-capture ses
# seuls fichiers (`UPDATE_GOLDEN=1`) et le dit dans son commit ; une tâche SPL ne
# re-capture JAMAIS. Un json manquant en mode normal FAIT ÉCHOUER le test.
#
# Capture : `UPDATE_GOLDEN=1 python manage.py test apps.crm.tests_scission_golden.ScissionGoldenHttpTests`
# (`scripts/test-backend.ps1 -RestoreDb -Modules "apps.crm.tests_scission_golden.ScissionGoldenHttpTests"`).


GEL = datetime.datetime(2026, 9, 30, 10, 0, tzinfo=horaires.CASABLANCA)
BASE = '/api/django/crm/'
_GOLDEN_HTTP = pathlib.Path(__file__).resolve().parent / 'golden' / 'scission_crm_http'
_CAPTURE_HTTP = os.environ.get('UPDATE_GOLDEN') == '1'
_MASQUE = '<masque>'

#: Clés dont la valeur est un horodatage posé par le serveur (auto_now*).
_CLES_HORODATAGE = frozenset({
    'created_at', 'updated_at', 'date_creation', 'date_modification',
    'created', 'modified'})
#: Clé -> famille d'identifiants (voir `_Fixture.familles`).
_FAMILLE_PAR_CLE = {
    'lead': 'lead', 'lead_id': 'lead', 'client': 'client',
    'client_id': 'client', 'etape': 'etape', 'etape_id': 'etape',
    'owner': 'user', 'owner_id': 'user', 'assigned_to': 'user',
    'responsable': 'user', 'user': 'user', 'created_by': 'user',
    'traite_par': 'user', 'playbook': 'playbook',
    'playbook_id': 'playbook', 'company': 'company',
    'company_id': 'company'}
_CLES_ID = {'id', 'pk'}


class _Fixture:
    """Table pk -> étiquette stable, par famille, dans l'ordre de création."""

    def __init__(self):
        self.familles = {}

    def noter(self, famille, objet):
        table = self.familles.setdefault(famille, {})
        table[objet.pk] = f'{famille}#{len(table) + 1}'
        return objet


class _Normaliseur:
    def __init__(self, fixture, defaut, secrets):
        self.fixture = fixture
        self.defaut = defaut
        self.secrets = [s for s in secrets if s]
        self.vus = {}

    def _etiquette(self, famille, valeur):
        table = self.fixture.familles.get(famille, {})
        if valeur in table:
            return table[valeur]
        vus = self.vus.setdefault(famille, {})
        if valeur not in vus:
            vus[valeur] = f'{famille}?#{len(vus) + 1}'
        return vus[valeur]

    def __call__(self, valeur, cle=None):
        if isinstance(valeur, dict):
            return {k: self(v, k) for k, v in valeur.items()}
        if isinstance(valeur, list):
            return [self(v, cle) for v in valeur]
        if cle in _CLES_HORODATAGE and valeur is not None:
            return _MASQUE
        if cle in ('token', 'code_parrainage', 'tiers', 'tiers_id') and valeur:
            return _MASQUE
        if isinstance(valeur, str):
            for secret in self.secrets:
                valeur = valeur.replace(secret, _MASQUE)
            return valeur
        if isinstance(valeur, int) and not isinstance(valeur, bool):
            if cle in _CLES_ID:
                return self._etiquette(self.defaut, valeur)
            if cle in _FAMILLE_PAR_CLE:
                return self._etiquette(_FAMILLE_PAR_CLE[cle], valeur)
        return valeur


def _nom_fichier(libelle):
    return re.sub(r'[^0-9A-Za-z_.-]+', '_', libelle).strip('_') + '.json'


def _ecrire(nom, contenu):
    _GOLDEN_HTTP.mkdir(parents=True, exist_ok=True)
    with open(_GOLDEN_HTTP / nom, 'w', encoding='utf-8') as f:
        json.dump(contenu, f, indent=1, ensure_ascii=False, sort_keys=True)
        f.write('\n')


def _lire(nom):
    with open(_GOLDEN_HTTP / nom, encoding='utf-8') as f:
        return json.load(f)


class ScissionGoldenHttpTests(TestCase):

    def setUp(self):
        gel = frozen(GEL)
        gel.start()
        self.addCleanup(gel.stop)
        self.fx = _Fixture()
        self.company = self.fx.noter('company', Company.objects.create(
            nom='Golden HTTP crm', slug='golden-http-crm'))
        CompanyProfile.objects.get_or_create(company=self.company)
        self.resp = self.fx.noter('user', User.objects.create_user(
            username='golden-http-resp', password='x',
            role_legacy='responsable', company=self.company))
        self.commerciale = self.fx.noter('user', User.objects.create_user(
            username='golden-http-comm', password='x',
            role_legacy='commercial', company=self.company))
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.resp)}')

        def lead(i, nom, stage, owner):
            return self.fx.noter('lead', Lead.objects.create(
                company=self.company, nom=nom, stage=stage, owner=owner,
                telephone=f'+212661000{i:03d}'))

        self.lead1 = lead(1, 'Prospect Golden Un', stages.NEW, self.resp)
        self.lead2 = lead(
            2, 'Prospect Golden Deux', stages.CONTACTED, self.commerciale)
        self.lead3 = lead(
            3, 'Prospect Golden Trois', stages.QUOTE_SENT, self.commerciale)

        self.etapes = []
        for i, (lead_, libelle) in enumerate((
                (self.lead1, 'Premier appel'),
                (self.lead2, 'Appel de suite'),
                (self.lead2, 'Appel à reporter'),
                (self.lead3, 'Appel à sauter'),
                (self.lead3, 'Appel de relance'))):
            quand = GEL + datetime.timedelta(hours=i + 1)
            self.etapes.append(self.fx.noter('etape', (
                RelanceEtape.objects.create(
                    company=self.company, lead=lead_, cadence='contact',
                    ordre=i + 1, canal=RelanceEtape.Canal.APPEL, cle='',
                    libelle=libelle, due_at=quand,
                    due_date=quand.astimezone(horaires.CASABLANCA).date(),
                    cadence_depart=GEL))))

        self.client_ = self.fx.noter('client', Client.objects.create(
            company=self.company, nom='Client Golden', prenom='Un',
            email='client.golden@example.test', telephone='+212661999001',
            adresse='1 rue du Golden, Casablanca'))
        self.fx.noter('rdv', Appointment.objects.create(
            company=self.company, lead=self.lead2,
            scheduled_at=GEL + datetime.timedelta(days=2)))
        self.playbook = self.fx.noter('playbook', Playbook.objects.create(
            company=self.company, nom='Playbook Golden'))
        PlaybookEtape.objects.create(
            playbook=self.playbook, stage=stages.NEW, ordre=1)
        self.salle = self.fx.noter('salle', SalleVente.objects.create(
            company=self.company, lead=self.lead3, titre='Salle Golden',
            created_by=self.resp))

    def _appels(self):
        """(libellé, méthode, chemin, famille de l'`id` racine, corps)."""
        l1, l2 = self.lead1.pk, self.lead2.pk
        e = [x.pk for x in self.etapes]
        periode = 'date_debut=2026-09-28&date_fin=2026-10-04'
        gets = [
            ('GET leads', 'leads/', 'lead'),
            ('GET leads detail', f'leads/{l2}/', 'lead'),
            ('GET leads historique', f'leads/{l2}/historique/', 'lead'),
            ('GET leads panneau-appel', f'leads/{l2}/panneau-appel/', 'lead'),
            ('GET leads kpi-cadences', 'leads/kpi-cadences/', 'lead'),
            ('GET leads mesure-cadence', 'leads/mesure-cadence/', 'lead'),
            ('GET leads kpi-premier-contact',
             'leads/kpi-premier-contact/', 'lead'),
            ('GET leads visites', f'leads/{l1}/visites/', 'lead'),
            ('GET leads doublons', 'leads/doublons/', 'lead'),
            ('GET relance-etapes', 'relance-etapes/', 'etape'),
            ('GET relance-etapes suivi',
             f'relance-etapes/suivi/?{periode}', 'etape'),
            ('GET relance-etapes journal',
             f'relance-etapes/journal/?lead={l2}', 'etape'),
            ('GET relance-etapes controle',
             'relance-etapes/controle/?jours=7', 'etape'),
            ('GET relance-etapes cadences-echues',
             'relance-etapes/cadences-echues/?jours=0', 'etape'),
            ('GET relance-etapes kpi-adherence',
             'relance-etapes/kpi-adherence/', 'etape'),
            ('GET relance-etapes mes-stats',
             'relance-etapes/mes-stats/', 'etape'),
            ('GET relance-etapes chaine-commerciale',
             'relance-etapes/chaine-commerciale/', 'etape'),
            ('GET clients', 'clients/', 'client'),
            ('GET clients detail', f'clients/{self.client_.pk}/', 'client'),
            ('GET appointments', 'appointments/', 'rdv'),
            ('GET playbooks', 'playbooks/', 'playbook'),
            ('GET salles-vente', 'salles-vente/', 'salle'),
        ]
        # Les écritures viennent APRÈS les lectures (elles changent la file).
        posts = [
            ('POST relance-etapes fait',
             f'relance-etapes/{e[1]}/fait/', 'etape', {'outcome': 'joint'}),
            ('POST relance-etapes sauter',
             f'relance-etapes/{e[3]}/sauter/', 'etape',
             {'note': 'sauté pour le golden'}),
            ('POST relance-etapes reporter',
             f'relance-etapes/{e[0]}/reporter/', 'etape',
             {'mode': 'decaler', 'note': 'report golden',
              'due_at': '2026-10-02T10:00:00+01:00'}),
        ]
        return ([(n, 'get', p, f, None) for n, p, f in gets]
                + [(n, 'post', p, f, corps) for n, p, f, corps in posts])

    def _jouer(self, methode, chemin, corps):
        if methode == 'get':
            return self.api.get(BASE + chemin)
        return self.api.post(BASE + chemin, corps, format='json')

    def _reponse_normalisee(self, resp, famille):
        try:
            corps = (json.loads(resp.content.decode('utf-8'))
                     if resp.content else None)
        except ValueError:
            corps = {'brut': resp.content.decode('utf-8', 'replace')}
        norm = _Normaliseur(self.fx, famille, [self.salle.token])
        return {'statut': resp.status_code, 'corps': norm(corps)}

    def test_golden_http(self):
        appels = self._appels()
        attendus = {_nom_fichier(a[0]) for a in appels}
        if not _CAPTURE_HTTP:
            manquants = sorted(
                n for n in attendus if not (_GOLDEN_HTTP / n).is_file())
            self.assertFalse(
                manquants,
                'Golden HTTP absent — capturer avec UPDATE_GOLDEN=1 '
                '(python manage.py test apps.crm.tests_scission_golden.ScissionGoldenHttpTests) '
                f': {manquants}')
        for libelle, methode, chemin, famille, corps in appels:
            nom = _nom_fichier(libelle)
            with self.subTest(appel=libelle):
                resp = self._jouer(methode, chemin, corps)
                # Le libellé (jamais l'URL) : aucun id brut dans le json.
                obtenu = {'appel': libelle,
                          **self._reponse_normalisee(resp, famille)}
                if _CAPTURE_HTTP:
                    _ecrire(nom, obtenu)
                else:
                    self.assertEqual(obtenu, _lire(nom), libelle)
        if not _CAPTURE_HTTP:
            en_trop = sorted(
                p.name for p in _GOLDEN_HTTP.glob('*.json')
                if p.name not in attendus)
            self.assertFalse(en_trop, f'Golden HTTP orphelin : {en_trop}')
