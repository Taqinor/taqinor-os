"""NTAPI3 — enveloppe d'erreur normalisée (Stripe-like) sur /api/public/.

Couvre : 403 (scope manquant), 404 (objet hors société — jamais de fuite
cross-tenant même dans le MESSAGE d'erreur), 400 (filtre inconnu → `param`
posé au nom du champ fautif), 409 (conflit d'idempotence sur une écriture),
et l'appel direct du handler pour 429 (throttled, sans dépendre du minutage
réel du throttle). `X-Request-Id` (YAPIC4, middleware global) reste présent
sur toute réponse, y compris ces enveloppes dédiées.
"""
from rest_framework.test import APIClient
from rest_framework import exceptions as drf_exceptions
from django.test import TestCase

from authentication.models import Company

from .constants import SCOPE_READ_LEADS, SCOPE_WRITE_LEADS
from .errors import public_api_exception_handler
from .idempotency import IdempotencyConflict
from .models import ApiKey


def _company(slug, nom):
    co, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return co


def _key_client(raw_key):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Api-Key {raw_key}')
    return api


class Ntapi3ErrorEnvelopeTests(TestCase):
    def setUp(self):
        self.co_a = _company('ntapi3-a', 'NTAPI3 A')
        self.co_b = _company('ntapi3-b', 'NTAPI3 B')
        self.key_a, self.raw_a = ApiKey.issue(
            company=self.co_a, label='A',
            scopes=[SCOPE_READ_LEADS, SCOPE_WRITE_LEADS])

    def _assert_envelope_shape(self, body, *, request_id_expected=True):
        self.assertIn('error', body)
        err = body['error']
        for key in ('type', 'code', 'message', 'param', 'doc_url', 'request_id'):
            self.assertIn(key, err)
        if request_id_expected:
            self.assertTrue(err['request_id'])
        # Le contrat Stripe-like est la SEULE forme du corps : pas de
        # `detail`/champ DRF natif qui traînerait à côté.
        self.assertNotIn('detail', body)

    def test_missing_scope_returns_authentication_error_envelope(self):
        resp = _key_client(self.raw_a).get('/api/public/devis/')
        self.assertEqual(resp.status_code, 403)
        self._assert_envelope_shape(resp.data)
        self.assertEqual(resp.data['error']['type'], 'authentication_error')
        self.assertEqual(resp.data['error']['code'], 'permission_denied')
        self.assertIsNone(resp.data['error']['param'])
        self.assertIn('X-Request-Id', resp)

    def test_object_not_found_never_leaks_cross_tenant(self):
        resp = _key_client(self.raw_a).get('/api/public/leads/999999/')
        self.assertEqual(resp.status_code, 404)
        self._assert_envelope_shape(resp.data)
        self.assertEqual(resp.data['error']['type'], 'invalid_request_error')
        self.assertEqual(resp.data['error']['code'], 'not_found')
        # Le message générique ne révèle jamais si un tel lead existe ailleurs.
        self.assertNotIn(str(self.co_b.id), resp.data['error']['message'])

    def test_unknown_filter_returns_param_of_offending_field(self):
        resp = _key_client(self.raw_a).get('/api/public/leads/?bogus=1')
        self.assertEqual(resp.status_code, 400)
        self._assert_envelope_shape(resp.data)
        self.assertEqual(resp.data['error']['code'], 'validation_error')
        self.assertEqual(resp.data['error']['type'], 'invalid_request_error')
        self.assertEqual(resp.data['error']['param'], 'bogus')

    def test_idempotency_conflict_returns_409_envelope(self):
        client = _key_client(self.raw_a)
        headers = {'HTTP_IDEMPOTENCY_KEY': 'dup-key-1'}
        first = client.post(
            '/api/public/leads-write/', {'nom': 'Premier'},
            format='json', **headers)
        self.assertEqual(first.status_code, 201)
        second = client.post(
            '/api/public/leads-write/', {'nom': 'Different'},
            format='json', **headers)
        self.assertEqual(second.status_code, 409)
        self._assert_envelope_shape(second.data)
        self.assertEqual(second.data['error']['code'], 'idempotency_conflict')
        self.assertEqual(second.data['error']['type'], 'invalid_request_error')

    def test_throttled_maps_to_rate_limit_error(self):
        # Unitaire (handler appelé directement) : indépendant du minutage réel
        # du throttle DRF, comme les autres tests d'enveloppe de ce module.
        exc = drf_exceptions.Throttled(wait=5)
        response = public_api_exception_handler(exc, {'request': None})
        self.assertEqual(response.status_code, 429)
        body = response.data
        self._assert_envelope_shape(body, request_id_expected=False)
        self.assertEqual(body['error']['type'], 'rate_limit_error')
        self.assertEqual(body['error']['code'], 'throttled')

    def test_unhandled_exception_falls_back_to_server_error_envelope(self):
        response = public_api_exception_handler(ValueError('boom'), {'request': None})
        self.assertEqual(response.status_code, 500)
        self._assert_envelope_shape(response.data, request_id_expected=False)
        self.assertEqual(response.data['error']['type'], 'api_error')
        self.assertEqual(response.data['error']['code'], 'server_error')

    def test_idempotency_conflict_code_via_direct_handler_call(self):
        response = public_api_exception_handler(
            IdempotencyConflict(), {'request': None})
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.data['error']['code'], 'idempotency_conflict')
        self.assertEqual(response.data['error']['type'], 'invalid_request_error')
