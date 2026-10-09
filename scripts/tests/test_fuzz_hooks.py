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

    def auth(**_kw):
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


if __name__ == '__main__':
    unittest.main()
