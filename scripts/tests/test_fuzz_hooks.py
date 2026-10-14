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


def _charger_hooks(etat, ids_chemin=None):
    with tempfile.NamedTemporaryFile('w', suffix='.json', delete=False,
                                     encoding='utf-8') as fh:
        json.dump(etat, fh)
    os.environ['FUZZ_STATE_FILE'] = fh.name
    ids_fichier = None
    if ids_chemin is not None:
        with tempfile.NamedTemporaryFile('w', suffix='.json', delete=False,
                                         encoding='utf-8') as fi:
            json.dump(ids_chemin, fi)
        ids_fichier = fi.name
        os.environ['FUZZ_IDS_FILE'] = ids_fichier
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
        os.environ.pop('FUZZ_IDS_FILE', None)
        if ids_fichier:
            os.unlink(ids_fichier)
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


class IdsCheminTests(unittest.TestCase):
    """ENF11 — ids réels pour `{id}`/`{pk}` (1 273 opérations 404-seules)."""

    @classmethod
    def setUpClass(cls):
        cls.hooks = _charger_hooks(
            {'user_id': 4, 'company_id': 2, 'role_id': 7, 'fk_ids': {}},
            ids_chemin={'/api/django/ventes/devis/': [11, 12, 13],
                        '/api/django/docs/': ['aaa', 'bbb']})

    def _appel(self, chemin, params, mode='POSITIVE', methode='GET'):
        cas = _cas(self.hooks, methode, chemin, params=params, mode=mode)
        self.hooks.before_call(None, cas, {})
        return cas

    def _valeurs(self, chemin, nb=200, **kw):
        return [self._appel(chemin, {'id': 10**6 + i}, **kw)
                .path_parameters['id'] for i in range(nb)]

    def test_id_reel_substitue_et_part_invalide_conservee(self):
        vals = self._valeurs('/api/django/ventes/devis/{id}/proposal/')
        reels = [v for v in vals if v in (11, 12, 13)]
        gardes = [v for v in vals if v >= 10**6]
        self.assertEqual(len(reels) + len(gardes), 200)
        self.assertTrue(0.15 < len(gardes) / 200 < 0.35, len(gardes))
        self.assertEqual(set(reels), {11, 12, 13})

    def test_deterministe(self):
        self.assertEqual(self._valeurs('/api/django/ventes/devis/{id}/'),
                         self._valeurs('/api/django/ventes/devis/{id}/'))

    def test_cas_negatifs_jamais_touches(self):
        vals = self._valeurs('/api/django/ventes/devis/{id}/', mode='NEGATIVE')
        self.assertTrue(all(v >= 10**6 for v in vals))

    def test_parametres_non_id_intacts(self):
        for gabarit, nom in (
                ('/api/django/ventes/devis/{token}/', 'token'),
                ('/api/django/ventes/devis/{jeton}/', 'jeton'),
                ('/api/django/ventes/devis/{slug}/', 'slug'),
                ('/api/django/ventes/devis/{key}/', 'key')):
            cas = self._appel(gabarit, {nom: 'abc'})
            self.assertEqual(cas.path_parameters[nom], 'abc')

    def test_sans_inventaire_ou_type_incompatible_intact(self):
        cas = self._appel('/api/django/inconnu/{id}/', {'id': 5})
        self.assertEqual(cas.path_parameters['id'], 5)
        # ids str (uuid) : jamais posés à la place d'un entier généré.
        vals = self._valeurs('/api/django/docs/{id}/')
        self.assertTrue(all(isinstance(v, int) for v in vals))

    def test_id_imbrique_second_parametre_intact(self):
        cas = self._appel('/api/django/ventes/devis/{id}/lignes/{ligne_id}/',
                          {'id': 10**6, 'ligne_id': 77})
        self.assertEqual(cas.path_parameters['ligne_id'], 77)

    def test_fuzz_admin_reste_protege_apres_substitution(self):
        h = _charger_hooks(
            {'user_id': 4, 'company_id': 2, 'role_id': 7, 'fk_ids': {}},
            ids_chemin={'/api/django/users/': [4]})
        for i in range(40):
            cas = _cas(h, 'DELETE', '/api/django/users/{id}/',
                       params={'id': 10**6 + i})
            h.before_call(None, cas, {})
            self.assertNotEqual(cas.path_parameters['id'], 4)


class IdsFkImbriquesTests(unittest.TestCase):
    """ENF11 (achats) — les FK des LIGNES imbriquées reçoivent des ids réels."""

    @classmethod
    def setUpClass(cls):
        cls.hooks = _charger_hooks({
            'user_id': 4, 'company_id': 2, 'role_id': 7,
            'fk_ids': {'produit': [11, 12], 'fournisseur': [5]}})

    def _corps(self, mode='POSITIVE'):
        cas = _cas(self.hooks, 'POST', '/api/django/achats/retours-fournisseur/',
                   {'fournisseur': 99999, 'motif': 'x',
                    'lignes': [{'produit': 0, 'quantite': 3},
                               {'produit': 12, 'quantite': 1}]}, mode=mode)
        self.hooks.before_call(None, cas, {})
        return cas.body

    def test_produit_de_ligne_remplace_par_un_id_reel(self):
        corps = self._corps()
        self.assertEqual(corps['fournisseur'], 5)
        self.assertIn(corps['lignes'][0]['produit'], (11, 12))
        self.assertEqual(corps['lignes'][1]['produit'], 12)
        self.assertEqual(corps['lignes'][0]['quantite'], 3)

    def test_cas_negatif_jamais_touche(self):
        corps = self._corps(mode='NEGATIVE')
        self.assertEqual(corps['fournisseur'], 99999)
        self.assertEqual(corps['lignes'][0]['produit'], 0)


class IdsFkParCheminTests(unittest.TestCase):
    """ENF11 (seed) — une règle par chemin donne les ids du BON modèle
    (``lot`` de stock = LotEntrepot), dans le corps ET la query."""

    @classmethod
    def setUpClass(cls):
        cls.hooks = _charger_hooks({
            'user_id': 4, 'company_id': 2, 'role_id': 7,
            'fk_ids': {'lot': [900, 901], 'activity_type': [3]},
            'fk_ids_chemin': [
                {'motif': r'^/api/django/stock/', 'champs': ['lot'],
                 'ids': [40], 'max': None},
                {'motif': r'/comparer/', 'champs': ['ids'],
                 'ids': [1, 2, 3], 'max': 2}]})

    def _appel(self, chemin, corps, mode='POSITIVE', query=None):
        cas = _cas(self.hooks, 'POST', chemin, corps, mode=mode)
        cas.query = query
        self.hooks.before_call(None, cas, {})
        return cas

    def test_regle_du_chemin_prioritaire_sur_la_table_par_nom(self):
        cas = self._appel('/api/django/stock/alertes-rappel/',
                          {'lot': 0, 'motif': 'x'})
        self.assertEqual(cas.body['lot'], 40)
        autre = self._appel('/api/django/ventes/x/', {'lot': 0})
        self.assertIn(autre.body['lot'], (900, 901))

    def test_query_remplacee_entier_et_texte(self):
        cas = self._appel('/api/django/stock/x/', None,
                          query={'lot': 7, 'q': 'abc'})
        self.assertEqual(cas.query, {'lot': 40, 'q': 'abc'})
        cas = self._appel('/api/django/stock/x/', None, query={'lot': '7'})
        self.assertEqual(cas.query['lot'], '40')

    def test_liste_bornee_et_objet_imbrique(self):
        cas = self._appel('/api/django/x/comparer/', {'ids': [7, 8, 9]})
        self.assertEqual(len(cas.body['ids']), 2)
        self.assertTrue(set(cas.body['ids']) <= {1, 2, 3})
        cas = self._appel('/api/django/records/activities/{id}/done/',
                          {'next': {'activity_type': 0}})
        self.assertEqual(cas.body['next']['activity_type'], 3)

    def test_cas_negatif_jamais_touche(self):
        cas = self._appel('/api/django/stock/x/', {'lot': 0},
                          mode='NEGATIVE', query={'lot': 7})
        self.assertEqual((cas.body['lot'], cas.query['lot']), (0, 7))


class CiblesRecordsTests(unittest.TestCase):
    """ENF11 (records) — ``{model, id}`` désigne une ligne réelle."""

    @classmethod
    def setUpClass(cls):
        cls.hooks = _charger_hooks({
            'user_id': 4, 'company_id': 2, 'role_id': 7, 'fk_ids': {},
            'cibles': {'crm.lead': [21, 22]}})

    def test_corps_et_query(self):
        cas = _cas(self.hooks, 'POST', '/api/django/records/tagged-items/',
                   {'model': 'crm.lead', 'id': 0, 'tag': 1})
        cas.query = {'model': 'sav.ticket', 'id': '5'}
        self.hooks.before_call(None, cas, {})
        self.assertIn(cas.body['id'], (21, 22))
        self.assertEqual(cas.query['model'], 'crm.lead')
        self.assertIn(cas.query['id'], ('21', '22'))


class IdsFkParCheminStockTests(unittest.TestCase):
    """ENF11 (stock/achats) — ``lot``/``retour`` du corps = ids du BON modèle
    sous /stock/ et /achats/ seulement ; ailleurs, comportement inchangé."""

    @classmethod
    def setUpClass(cls):
        regle = {'motif': r'^/api/django/(stock|achats)/', 'champs': ['lot'],
                 'ids': [40]}
        cls.hooks = _charger_hooks({
            'user_id': 4, 'company_id': 2, 'role_id': 7,
            'fk_ids': {'lot': [900, 901]},
            'fk_ids_chemin': [regle, dict(regle, champs=['retour'], ids=[7])]})

    def _corps(self, chemin, corps, mode='POSITIVE'):
        cas = _cas(self.hooks, 'POST', chemin, corps, mode=mode)
        self.hooks.before_call(None, cas, {})
        return cas.body

    def test_stock_et_achats(self):
        self.assertEqual(self._corps('/api/django/stock/alertes-rappel/',
                                     {'lot': 0})['lot'], 40)
        self.assertEqual(self._corps('/api/django/achats/x/',
                                     {'retour': 3})['retour'], 7)

    def test_autres_routes_et_negatif_inchanges(self):
        self.assertIn(self._corps('/api/django/core/x/', {'lot': 0})['lot'],
                      (900, 901))
        self.assertEqual(self._corps('/api/django/core/x/',
                                     {'retour': 3})['retour'], 3)
        self.assertEqual(self._corps('/api/django/stock/x/', {'lot': 0},
                                     mode='NEGATIVE')['lot'], 0)


def _charger_inventaire():
    sys.path.insert(0, str(ROOT / 'scripts' / 'fuzz'))
    try:
        sys.modules.pop('inventorier_ids_chemin', None)
        return importlib.import_module('inventorier_ids_chemin')
    finally:
        sys.path.pop(0)


class InventaireIdsTests(unittest.TestCase):
    def setUp(self):
        self.inv = _charger_inventaire()

    def test_liste_paginee_et_nue(self):
        self.assertEqual(
            self.inv.parser_ids({'count': 2, 'results': [{'id': 3}, {'id': 5}]}),
            [3, 5])
        self.assertEqual(self.inv.parser_ids([{'id': 'u1'}, {'pk': 2}, {}]),
                         ['u1', 2])
        self.assertEqual(self.inv.parser_ids({'detail': 'x'}), [])
        self.assertEqual(self.inv.parser_ids([{'id': True}, 5]), [])

    def test_collections_et_inventaire(self):
        doc = {'paths': {
            '/api/django/a/': {'get': {}},
            '/api/django/a/{id}/': {'get': {}},
            '/api/django/a/{id}/sub/': {'get': {}},
            '/api/django/b/': {'post': {}},
            '/api/django/b/{pk}/': {'get': {}},
            '/api/django/c/{token}/': {'get': {}}}}
        self.assertEqual(self.inv.collections_du_schema(doc),
                         ['/api/django/a/'])
        table = self.inv.inventorier(
            doc, lambda p: {'results': [{'id': 9}]})
        self.assertEqual(table, {'/api/django/a/': [9]})


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

    def test_contrats_et_dette_gelee_n_elargissent_pas_le_perimetre(self):
        # VNT M0 (12/10/2026) : un échantillon de contrat (PACT10) et la dette
        # gelée ne changent aucun comportement HTTP ; les compter relançait
        # crm/core/authentication à chaque tour (treadmill de gels).
        self.assertEqual(self.m.proprietaires_modifies([
            'backend/django_core/apps/crm/contract_samples/lead_devis_ligne.json',
            'backend/django_core/apps/ventes/contract_samples/README.md',
            'scripts/fuzz/api_fuzz_dette.txt',
        ]), [])
        self.assertEqual(self.m.proprietaires_modifies([
            'scripts/fuzz/api_fuzz_dette.txt',
            'backend/django_core/apps/ventes/domain/facturation_ops.py',
        ]), ['apps.ventes'])

    def test_proprietaire_du_module(self):
        self.assertEqual(self.m.proprietaire_du_module('apps.stock.views.produit'),
                         'apps.stock')
        self.assertEqual(self.m.proprietaire_du_module('core.views'), 'core')
        self.assertEqual(self.m.proprietaire_du_module(
            'authentication.views'), 'authentication')
        self.assertIsNone(self.m.proprietaire_du_module(
            'rest_framework_simplejwt.views'))
        self.assertIsNone(self.m.proprietaire_du_module(None))

    def test_modules_de_vue_essaie_les_valeurs_jusqu_a_resolution(self):
        def resoudre(chemin):
            if '00000000' not in chemin:
                raise LookupError(chemin)
            return 'apps.ged.views'
        self.assertEqual(self.m.modules_de_vue('/api/django/ged/x/{uuid}/', resoudre),
                         ('apps.ged.views',))
        self.assertEqual(self.m.modules_de_vue('/api/django/ged/x/{uuid}/', _refuse), ())

    def test_urlconf_traverse_compte_comme_proprietaire(self):
        # facturation monte des vues définies dans ventes (re-export).
        def resoudre(chemin):
            return ('apps.ventes.views', 'erp_agentique.urls', 'apps.facturation.urls')
        doc = {'paths': {'/api/django/facturation/factures/': {'get': {'operationId': 'f'}}}}
        sortie, _ = self.m.preparer_schema(doc, ['apps.facturation'], resoudre)
        self.assertEqual(list(sortie['paths']), ['/api/django/facturation/factures/'])
        sortie, _ = self.m.preparer_schema(doc, ['apps.stock'], resoudre)
        self.assertEqual(sortie['paths'], {})

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

    def test_erreur_du_moteur_toujours_rouge_jamais_gelable(self):
        # Rapport JSON Schemathesis 4.28 : `errors: [{title, count}]`, sans
        # opération — une opération en erreur n'a pas été testée.
        rapport = {'failures': [], 'errors': [{'title': "Unsupported type: 'Binary'",
                                               'count': 1}],
                   'operations': {'errored': 1}}
        nouveaux, _ = self.m.verdict(
            rapport, {"Erreur du moteur|Unsupported type: 'Binary'"})
        self.assertEqual(nouveaux, ["Erreur du moteur|Unsupported type: 'Binary'"])
        # Compteur seul (liste absente) : rouge quand même.
        nouveaux, _ = self.m.verdict({'operations': {'errored': 2}}, set())
        self.assertEqual(nouveaux, ['Erreur du moteur|2 opération(s) en erreur'])

    def test_run_inexploitable_rouge(self):
        self.assertEqual(self.m.verdict({'complete': False, 'stop_reason': 'interrupted'},
                                        set())[0],
                         ['Run incomplet|stop_reason=interrupted'])
        self.assertEqual(self.m.verdict({'auth': {'reauth_broke': True}}, set())[0],
                         ['Authentification perdue|reauth_broke'])
        # Fin normale ou plafond --max-time : run exploitable.
        for raison in ('completed', 'max_time'):
            rapport = {'complete': True, 'stop_reason': raison,
                       'auth': {'reauth_broke': False}, 'errors': [],
                       'operations': {'errored': 0}}
            self.assertEqual(self.m.verdict(rapport, set()), ([], []))

    def test_resume_d_alerte_nomme_les_regressions(self):
        texte = self.m.resume_markdown(['Server error|POST /b/'], ['Server error|GET /a/'])
        self.assertIn('1 constat(s) api-fuzz HORS de la dette gelée', texte)
        self.assertIn('- `Server error|POST /b/`', texte)
        self.assertIn('Aucune régression', self.m.resume_markdown([], ['x']))
        long = self.m.resume_markdown([f'Server error|GET /{i}/' for i in range(70)], [])
        self.assertIn('… et 10 autre(s)', long)

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
            resume = Path(tmp) / 'alerte.md'
            self.assertEqual(self.m.main(args + ['--resume', str(resume)]), 1)
            self.assertIn('Server error|GET /a/', resume.read_text(encoding='utf-8'))


if __name__ == '__main__':
    unittest.main()
