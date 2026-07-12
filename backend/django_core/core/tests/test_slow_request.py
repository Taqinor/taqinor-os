"""NTPLT51 — trace des requêtes HTTP lentes (activable par SLOW_REQUEST_MS)."""
import time

from django.http import HttpResponse
from django.test import RequestFactory, SimpleTestCase, override_settings

from core.observability import RequestObservabilityMiddleware


class SlowRequestTraceTests(SimpleTestCase):
    def setUp(self):
        self.rf = RequestFactory()

    @override_settings(SLOW_REQUEST_MS=0)
    def test_disabled_by_default_no_warning(self):
        mw = RequestObservabilityMiddleware(lambda r: HttpResponse('ok'))
        # Aucun log 'core.slow_request' quand le seuil est 0 (désactivé).
        with self.assertNoLogs('core.slow_request', level='WARNING'):
            mw(self.rf.get('/x/'))

    @override_settings(SLOW_REQUEST_MS=1)
    def test_slow_request_logs_warning(self):
        def slow(_req):
            time.sleep(0.01)  # 10 ms > seuil 1 ms
            return HttpResponse('ok')

        mw = RequestObservabilityMiddleware(slow)
        with self.assertLogs('core.slow_request', level='WARNING') as cm:
            mw(self.rf.get('/lente/'))
        self.assertTrue(any('Requête lente' in m for m in cm.output))
        self.assertTrue(any('/lente/' in m for m in cm.output))
