"""Tests YAPIC3 — enveloppe d'erreur DRF unifiée (`core.exceptions`).

Unitaire sur `taqinor_exception_handler` directement (aucune vue HTTP, aucune
DB) : les 4 formes (400 validation, 401, 404, 500 non géré) doivent TOUTES
porter la même clé racine ``error`` avec un ``code`` énuméré stable, et le
``request_id`` du contexte est propagé sans jamais changer le statut HTTP.
"""
from types import SimpleNamespace

from django.test import SimpleTestCase
from rest_framework import exceptions as drf_exceptions
from rest_framework import status

from core.exceptions import taqinor_exception_handler


def _context(request_id=None):
    request = SimpleNamespace(request_id=request_id) if request_id else None
    return {'request': request, 'view': None}


class ErrorEnvelopeTests(SimpleTestCase):

    def test_validation_error_400_has_fields_and_stable_code(self):
        exc = drf_exceptions.ValidationError(
            {'email': ['Ce champ est requis.']})
        response = taqinor_exception_handler(exc, _context())
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        body = response.data
        self.assertIn('error', body)
        self.assertEqual(body['error']['code'], 'validation_error')
        self.assertEqual(
            body['error']['fields'], {'email': ['Ce champ est requis.']})

    def test_not_authenticated_401_same_root_key(self):
        exc = drf_exceptions.NotAuthenticated()
        response = taqinor_exception_handler(exc, _context())
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertIn('error', response.data)
        self.assertEqual(response.data['error']['code'], 'not_authenticated')
        self.assertIsNone(response.data['error']['fields'])

    def test_not_found_404_same_root_key(self):
        exc = drf_exceptions.NotFound()
        response = taqinor_exception_handler(exc, _context())
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertIn('error', response.data)
        self.assertEqual(response.data['error']['code'], 'not_found')

    def test_unhandled_exception_folds_to_500_server_error(self):
        exc = RuntimeError('boom — détail interne jamais exposé')
        response = taqinor_exception_handler(exc, _context())
        self.assertEqual(
            response.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)
        self.assertIn('error', response.data)
        self.assertEqual(response.data['error']['code'], 'server_error')
        # Le message générique ne fuite jamais le détail de l'exception.
        self.assertNotIn('boom', response.data['error']['message'])

    def test_request_id_propagated_without_changing_status(self):
        exc = drf_exceptions.PermissionDenied()
        response = taqinor_exception_handler(
            exc, _context(request_id='req-abc-123'))
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(response.data['error']['request_id'], 'req-abc-123')

    def test_request_id_absent_is_none_not_an_error(self):
        exc = drf_exceptions.PermissionDenied()
        response = taqinor_exception_handler(exc, _context())
        self.assertIsNone(response.data['error']['request_id'])

    def test_throttled_maps_to_throttled_code(self):
        exc = drf_exceptions.Throttled(wait=5)
        response = taqinor_exception_handler(exc, _context())
        self.assertEqual(response.status_code, status.HTTP_429_TOO_MANY_REQUESTS)
        self.assertEqual(response.data['error']['code'], 'throttled')
