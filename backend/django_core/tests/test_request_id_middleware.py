"""Tests YAPIC4 — `core.middleware.RequestIdMiddleware` (X-Request-Id sur
100% des réponses) + son câblage avec l'enveloppe d'erreur (YAPIC3).

Unitaire sur le middleware directement (``RequestFactory`` + un
``get_response`` factice) — aucune DB, aucune vue métier requise pour
prouver le contrat : id fourni ré-échoé tel quel, absent -> uuid4 généré,
posé sur ``request.request_id`` (lu ensuite par le handler d'erreur), et
présent sur une réponse ERREUR comme sur une réponse succès.
"""
from django.http import HttpResponse
from django.test import RequestFactory, SimpleTestCase

from core.exceptions import taqinor_exception_handler
from core.middleware import RequestIdMiddleware
from rest_framework import exceptions as drf_exceptions


class RequestIdMiddlewareTests(SimpleTestCase):

    def setUp(self):
        self.factory = RequestFactory()

    def test_generates_uuid_when_absent(self):
        request = self.factory.get('/api/django/crm/leads/')
        middleware = RequestIdMiddleware(lambda req: HttpResponse('ok'))
        response = middleware(request)
        self.assertTrue(hasattr(request, 'request_id'))
        self.assertTrue(len(request.request_id) > 0)
        self.assertEqual(response['X-Request-Id'], request.request_id)

    def test_client_supplied_id_is_echoed_verbatim(self):
        request = self.factory.get(
            '/api/django/crm/leads/', HTTP_X_REQUEST_ID='client-req-42')
        middleware = RequestIdMiddleware(lambda req: HttpResponse('ok'))
        response = middleware(request)
        self.assertEqual(request.request_id, 'client-req-42')
        self.assertEqual(response['X-Request-Id'], 'client-req-42')

    def test_invalid_incoming_id_is_replaced_not_rejected(self):
        # Un caractère non imprimable (\x00) rend l'id "invalide" : jamais un
        # rejet de requête, juste une génération comme si absent.
        request = self.factory.get(
            '/api/django/crm/leads/', HTTP_X_REQUEST_ID='bad\x00id')
        middleware = RequestIdMiddleware(lambda req: HttpResponse('ok'))
        response = middleware(request)
        self.assertNotEqual(request.request_id, 'bad\x00id')
        self.assertEqual(response['X-Request-Id'], request.request_id)

    def test_present_on_an_error_response_too(self):
        def _get_response(req):
            resp = HttpResponse('erreur', status=500)
            return resp
        request = self.factory.get('/api/django/crm/leads/')
        middleware = RequestIdMiddleware(_get_response)
        response = middleware(request)
        self.assertEqual(response.status_code, 500)
        self.assertIn('X-Request-Id', response)

    def test_error_envelope_reuses_the_same_request_id(self):
        """YAPIC3+YAPIC4 câblés ensemble : le corps d'erreur unifié porte le
        MÊME id que l'en-tête posé par ce middleware."""
        request = self.factory.get(
            '/api/django/crm/leads/', HTTP_X_REQUEST_ID='corr-99')
        # Simule le middleware posant request.request_id AVANT que la vue
        # (ici, le handler d'erreur) ne s'exécute.
        RequestIdMiddleware(lambda r: HttpResponse('probe'))(request)
        exc = drf_exceptions.NotFound()
        response = taqinor_exception_handler(
            exc, {'request': request, 'view': None})
        self.assertEqual(response.data['error']['request_id'], 'corr-99')
