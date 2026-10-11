"""ENF1b — tests des crochets Schemathesis du job `api-fuzz`
(`scripts/fuzz/schemathesis_hooks.py`). Stdlib pur : le module
`schemathesis` (absent du job stage-names) est remplacé par un bouchon.

Régression du run 37897343514 : le fuzzeur passait la politique réseau de
sa propre société en `enforce` et recevait ensuite 403 sur TOUT (1 760
opérations « Missing authentication », « Authentication stopped working
mid-run »).
"""
import enum
import importlib
import json
import os
import sys
import tempfile
import types
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent


def _bouchon_schemathesis():
    mod = types.ModuleType('schemathesis')

    class GenerationMode(enum.Enum):
        POSITIVE = 'positive'
        NEGATIVE = 'negative'

    def auth(**kw):
        mod.auth_kwargs = kw
        return lambda cls: cls

    def deserializer(*_types):
        return lambda fn: fn

    mod.GenerationMode = GenerationMode
    mod.auth = auth
    mod.deserializer = deserializer
    mod.hook = lambda fn: fn
    return mod


def _charger_hooks(etat):
    with tempfile.NamedTemporaryFile('w', suffix='.json', delete=False,
                                     encoding='utf-8') as fh:
        json.dump(etat, fh)
    os.environ['FUZZ_STATE_FILE'] = fh.name
    precedent = sys.modules.get('schemathesis')
    sys.modules['schemathesis'] = _bouchon_schemathesis()
    sys.modules.setdefault('requests', types.ModuleType('requests'))
    sys.path.insert(0, str(ROOT / 'scripts' / 'fuzz'))
    try:
        sys.modules.pop('schemathesis_hooks', None)
        return importlib.import_module('schemathesis_hooks')
    finally:
        _charger_hooks.auth_kwargs = getattr(
            sys.modules['schemathesis'], 'auth_kwargs', None)
        sys.path.pop(0)
        os.unlink(fh.name)
        os.environ.pop('FUZZ_STATE_FILE', None)
        if precedent is None:
            sys.modules.pop('schemathesis', None)
        else:
            sys.modules['schemathesis'] = precedent


def _cas(hooks, methode, chemin, corps=None, params=None, mode='POSITIVE'):
    operation = types.SimpleNamespace(method=methode, path=chemin)
    meta = types.SimpleNamespace(generation=types.SimpleNamespace(
        mode=getattr(hooks.GenerationMode, mode)))
    return types.SimpleNamespace(operation=operation, body=corps,
                                 path_parameters=params or {}, meta=meta)


class CrochetsFuzzTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.hooks = _charger_hooks(
            {'user_id': 4, 'company_id': 2, 'role_id': 7, 'fk_ids': {}})

    def _appel(self, cas):
        self.hooks.before_call(None, cas, {})
        return cas

    def test_politique_reseau_enforce_ramenee_a_monitor(self):
        for methode, chemin in (
                ('POST', '/api/django/identity/network-policies/'),
                ('PATCH', '/api/django/identity/network-policies/{id}/'),
                ('PUT', '/api/django/identity/network-policies/{id}/')):
            for mode in ('POSITIVE', 'NEGATIVE'):
                with self.subTest(methode=methode, mode=mode):
                    cas = self._appel(_cas(self.hooks, methode, chemin,
                                           {'mode': 'enforce',
                                            'applies_to': 'all'}, mode=mode))
                    self.assertEqual(cas.body['mode'], 'monitor')
                    self.assertEqual(cas.body['applies_to'], 'all')

    def test_politique_reseau_autres_modes_intacts(self):
        for valeur in ('off', 'monitor', 42, None):
            with self.subTest(valeur=valeur):
                cas = self._appel(_cas(
                    self.hooks, 'PATCH',
                    '/api/django/identity/network-policies/{id}/',
                    {'mode': valeur}))
                self.assertEqual(cas.body['mode'], valeur)

    def test_lecture_et_autre_chemin_intacts(self):
        cas = self._appel(_cas(self.hooks, 'GET',
                               '/api/django/identity/network-policies/',
                               {'mode': 'enforce'}))
        self.assertEqual(cas.body['mode'], 'enforce')
        cas = self._appel(_cas(self.hooks, 'POST',
                               '/api/django/sav/tickets/',
                               {'mode': 'enforce'}))
        self.assertEqual(cas.body['mode'], 'enforce')

    def test_corps_non_dict_ignore(self):
        cas = self._appel(_cas(self.hooks, 'POST',
                               '/api/django/identity/network-policies/',
                               ['enforce']))
        self.assertEqual(cas.body, ['enforce'])

    def test_role_du_fuzzeur_protege(self):
        cas = self._appel(_cas(self.hooks, 'PATCH', '/api/django/roles/{id}/',
                               {'permissions': []}, params={'id': 7}))
        self.assertEqual(cas.path_parameters['id'],
                         self.hooks.ID_INEXISTANT)
        cas = self._appel(_cas(self.hooks, 'PATCH', '/api/django/roles/{id}/',
                               {'permissions': []}, params={'id': 8}))
        self.assertEqual(cas.path_parameters['id'], 8)

    def test_compte_et_societe_toujours_proteges(self):
        cas = self._appel(_cas(self.hooks, 'DELETE', '/api/django/users/{id}/',
                               params={'id': 4}))
        self.assertEqual(cas.path_parameters['id'],
                         self.hooks.ID_INEXISTANT)
        cas = self._appel(_cas(self.hooks, 'GET', '/api/django/users/{id}/',
                               params={'id': 4}))
        self.assertEqual(cas.path_parameters['id'], 4)

    def test_aucun_rejeu_sur_401_et_rafraichissement_proactif(self):
        # ENF11 — run 38129616897 : reauth_count 0, reauth_broke true.
        self.assertEqual(_charger_hooks.auth_kwargs,
                         {'refresh_interval': 600, 'retry_on': []})


def _charger_portee():
    sys.path.insert(0, str(ROOT / 'scripts' / 'fuzz'))
    try:
        sys.modules.pop('api_fuzz_scope', None)
        return importlib.import_module('api_fuzz_scope')
    finally:
        sys.path.pop(0)


def _doc_crud():
    reponse_201 = {'content': {'application/json': {
        'schema': {'$ref': '#/components/schemas/Produit'}}}}
    return {
        'openapi': '3.0.3',
        'paths': {
            '/api/django/stock/produits/': {
                'get': {'operationId': 'liste'},
                'post': {'operationId': 'cree',
                         'responses': {'201': reponse_201}}},
            '/api/django/stock/produits/{id}/': {
                'get': {'operationId': 'lit'},
                'delete': {'operationId': 'supprime'}},
            '/api/django/stock/produits/{id}/archiver/': {
                'post': {'operationId': 'archive'}},
            '/api/django/stock/produits/export/': {
                'get': {'operationId': 'exporte'}},
            '/api/django/ventes/devis/': {
                'post': {'operationId': 'cree_devis',
                         'responses': {'201': {'content': {}}}}},
            '/api/django/ventes/devis/{id}/': {
                'get': {'operationId': 'lit_devis'}},
            '/api/v1/stock/produits/': {'get': {'operationId': 'v1'}},
        },
        'components': {'schemas': {'Produit': {
            'type': 'object', 'properties': {'id': {'type': 'integer'}}}}},
    }


def _refuse(_chemin):
    raise LookupError(_chemin)


class PorteePRTests(unittest.TestCase):
    """ENF11 — sous-ensemble PR : fichiers modifiés -> opérations fuzzées."""

    @classmethod
    def setUpClass(cls):
        cls.m = _charger_portee()

    def test_fichiers_d_app_donnent_le_paquet(self):
        self.assertEqual(self.m.proprietaires_modifies([
            'backend/django_core/apps/ventes/views/facture.py',
            'backend/django_core/apps/stock/serializers.py',
            'backend/django_core/apps/stock/migrations/0101_x.py',
        ]), ['apps.stock', 'apps.ventes'])

    def test_tests_docs_et_hors_backend_ignores(self):
        self.assertEqual(self.m.proprietaires_modifies([
            'backend/django_core/apps/ventes/tests/test_x.py',
            'backend/django_core/apps/crm/tests_parsers.py',
            'backend/django_core/apps/sav/README.md',
            'frontend/src/App.jsx',
            'docs/PLAN.md',
            '',
        ]), [])

    def test_plateforme_et_harnais_donnent_core_et_authentication(self):
        for fichier in ('backend/django_core/erp_agentique/urls.py',
                        'backend/django_core/requirements.txt',
                        'scripts/fuzz/schemathesis_hooks.py',
                        'schemathesis.toml'):
            with self.subTest(fichier=fichier):
                self.assertEqual(self.m.proprietaires_modifies([fichier]),
                                 ['authentication', 'core'])
        self.assertEqual(self.m.proprietaires_modifies(
            ['backend/django_core/core/exceptions.py']), ['core'])
        self.assertEqual(self.m.proprietaires_modifies(
            ['backend/django_core/authentication/views.py']), ['authentication'])

    def test_proprietaire_du_module(self):
        self.assertEqual(self.m.proprietaire_du_module('apps.stock.views.produit'),
                         'apps.stock')
        self.assertEqual(self.m.proprietaire_du_module('core.views'), 'core')
        self.assertEqual(self.m.proprietaire_du_module(
            'authentication.views'), 'authentication')
        self.assertIsNone(self.m.proprietaire_du_module(
            'rest_framework_simplejwt.views'))
        self.assertIsNone(self.m.proprietaire_du_module(None))

    def test_module_de_vue_essaie_les_valeurs_jusqu_a_resolution(self):
        def resoudre(chemin):
            if '00000000' not in chemin:
                raise LookupError(chemin)
            return 'apps.ged.views'
        self.assertEqual(self.m.module_de_vue('/api/django/ged/x/{uuid}/', resoudre),
                         'apps.ged.views')
        self.assertIsNone(self.m.module_de_vue('/api/django/ged/x/{uuid}/', _refuse))

    def test_schema_filtre_par_proprietaire_sans_miroir_v1(self):
        modules = {'stock': 'apps.stock.views', 'ventes': 'apps.ventes.views'}

        def resoudre(chemin):
            return modules[chemin.split('/')[3]]
        sortie, stats = self.m.preparer_schema(_doc_crud(), ['apps.stock'], resoudre)
        self.assertEqual(sorted(sortie['paths']), [
            '/api/django/stock/produits/',
            '/api/django/stock/produits/export/',
            '/api/django/stock/produits/{id}/',
            '/api/django/stock/produits/{id}/archiver/'])
        self.assertEqual(stats['operations'], 6)
        self.assertIn('components', sortie)

    def test_sans_proprietaire_tout_est_garde_sauf_v1(self):
        sortie, _ = self.m.preparer_schema(_doc_crud())
        self.assertNotIn('/api/v1/stock/produits/', sortie['paths'])
        self.assertIn('/api/django/ventes/devis/{id}/', sortie['paths'])

    def test_liens_crud_declares_depuis_le_201_avec_id(self):
        doc = _doc_crud()
        sortie, stats = self.m.preparer_schema(doc)
        liens = sortie['paths']['/api/django/stock/produits/']['post'][
            'responses']['201']['links']
        self.assertEqual(sorted(liens), [
            'DELETE /api/django/stock/produits/{id}/',
            'GET /api/django/stock/produits/{id}/',
            'POST /api/django/stock/produits/{id}/archiver/'])
        self.assertEqual(liens['GET /api/django/stock/produits/{id}/'], {
            'operationId': 'lit', 'parameters': {'id': '$response.body#/id'}})
        # 201 sans `id` (devis) : aucun lien ; l'action de collection
        # `export/` n'est pas un élément : aucun lien.
        self.assertNotIn('links', sortie['paths']['/api/django/ventes/devis/'][
            'post']['responses']['201'])
        self.assertEqual(stats['liens'], 3)
        # Le document d'entrée n'est jamais modifié.
        self.assertNotIn('links', doc['paths']['/api/django/stock/produits/'][
            'post']['responses']['201'])

    def test_lien_existant_jamais_ecrase(self):
        doc = _doc_crud()
        doc['paths']['/api/django/stock/produits/']['post']['responses']['201'][
            'links'] = {'GET /api/django/stock/produits/{id}/': {'operationId': 'x'}}
        sortie, stats = self.m.preparer_schema(doc)
        self.assertEqual(sortie['paths']['/api/django/stock/produits/']['post'][
            'responses']['201']['links']['GET /api/django/stock/produits/{id}/'],
            {'operationId': 'x'})
        self.assertEqual(stats['liens'], 2)

    def test_verdict_rouge_sur_constat_hors_dette_seulement(self):
        rapport = {'failures': [
            {'title': 'Server error', 'operations': ['GET /a/', 'POST /b/']},
            {'title': 'Undocumented HTTP status code', 'operations': ['GET /a/']},
        ]}
        nouveaux, revus = self.m.verdict(rapport, {'Server error|GET /a/'})
        self.assertEqual(nouveaux, ['Server error|POST /b/',
                                    'Undocumented HTTP status code|GET /a/'])
        self.assertEqual(revus, ['Server error|GET /a/'])
        self.assertEqual(self.m.verdict({'failures': []}, set()), ([], []))

    def test_dette_versionnee_bien_formee(self):
        dette = self.m.charger_dette()
        self.assertTrue(dette)
        for ligne in dette:
            with self.subTest(ligne=ligne):
                titre, _, operation = ligne.partition('|')
                methode, _, chemin = operation.partition(' ')
                self.assertTrue(titre)
                self.assertIn(methode, {'GET', 'POST', 'PUT', 'PATCH', 'DELETE',
                                        'HEAD', 'OPTIONS', 'TRACE'})
                self.assertTrue(chemin.startswith('/'))

    def test_commande_verdict_code_retour(self):
        with tempfile.TemporaryDirectory() as tmp:
            rapport = Path(tmp) / 'r.json'
            dette = Path(tmp) / 'd.txt'
            rapport.write_text(json.dumps({'failures': [
                {'title': 'Server error', 'operations': ['GET /a/']}]}),
                encoding='utf-8')
            dette.write_text('# raison\nServer error|GET /a/\n', encoding='utf-8')
            args = ['verdict', '--rapport', str(rapport), '--dette', str(dette)]
            self.assertEqual(self.m.main(args), 0)
            dette.write_text('# raison\n', encoding='utf-8')
            self.assertEqual(self.m.main(args), 1)


if __name__ == '__main__':
    unittest.main()

