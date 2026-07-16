"""NTPLT43 — contexte tenant + logs JSON structurés."""
import json
import logging

from django.http import HttpResponse
from django.test import RequestFactory, SimpleTestCase

from core import observability
from core.logging_ext import JSONFormatter, TenantLogFilter
from core.observability import RequestObservabilityMiddleware


class RequestIdMiddlewareTests(SimpleTestCase):
    def setUp(self):
        self.rf = RequestFactory()

    def _run(self, request):
        captured = {}

        def get_response(req):
            captured['ctx'] = dict(observability.current_context())
            return HttpResponse('ok')

        mw = RequestObservabilityMiddleware(get_response)
        return mw(request), captured['ctx']

    def test_generates_and_returns_request_id(self):
        resp, ctx = self._run(self.rf.get('/api/x/'))
        self.assertIn('X-Request-ID', resp)
        self.assertEqual(resp['X-Request-ID'], ctx['request_id'])
        self.assertEqual(ctx['path'], '/api/x/')

    def test_propagates_incoming_request_id(self):
        req = self.rf.get('/api/x/', HTTP_X_REQUEST_ID='abc-123')
        resp, ctx = self._run(req)
        self.assertEqual(resp['X-Request-ID'], 'abc-123')
        self.assertEqual(ctx['request_id'], 'abc-123')

    def test_context_cleared_outside_request(self):
        self._run(self.rf.get('/api/x/'))
        # Hors requête, current_context est vide (contextvar par défaut None).
        self.assertEqual(observability.current_context(), {})


class TenantLogFilterTests(SimpleTestCase):
    def test_filter_injects_fields_and_formatter_emits_json(self):
        rf = RequestFactory()

        def get_response(req):
            record = logging.LogRecord(
                'app', logging.INFO, __file__, 1, 'hello', None, None)
            TenantLogFilter().filter(record)
            line = JSONFormatter().format(record)
            data = json.loads(line)
            self.assertEqual(data['message'], 'hello')
            self.assertIn('request_id', data)
            self.assertEqual(data['path'], '/api/y/')
            return HttpResponse('ok')

        RequestObservabilityMiddleware(get_response)(rf.get('/api/y/'))
