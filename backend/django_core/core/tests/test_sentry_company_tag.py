"""NTPLT46 — Sentry key-gated : tag company + no-op sans DSN.

On ne teste PAS un vrai envoi réseau (le SDK est optionnel/non installé en CI) :
on vérifie que (a) sans DSN, l'init est un no-op ; (b) le processeur before_send
injecte le tag `company` depuis le contexte tenant.
"""
import os
from unittest import mock

from django.test import SimpleTestCase

from core import monitoring


class SentryKeyGatingTests(SimpleTestCase):
    def test_no_dsn_means_disabled(self):
        with mock.patch.dict(os.environ, {'SENTRY_DSN': ''}, clear=False):
            self.assertFalse(monitoring.is_enabled())
            # init retourne False et ne charge aucune dépendance.
            self.assertFalse(monitoring.init_sentry())

    def test_before_send_injects_company_tag(self):
        token = monitoring._company_id_ctx.set(42)
        try:
            event = monitoring._before_send({}, {})
            self.assertEqual(event['tags']['company'], '42')
        finally:
            monitoring._company_id_ctx.reset(token)

    def test_before_send_without_company_is_untouched(self):
        token = monitoring._company_id_ctx.set(None)
        try:
            event = monitoring._before_send({'level': 'error'}, {})
            self.assertNotIn('company', event.get('tags', {}))
        finally:
            monitoring._company_id_ctx.reset(token)

    def test_bind_company_is_noop_without_sentry(self):
        # Sans init, bind_company ne doit pas lever même si sentry_sdk absent.
        monitoring.bind_company(7)
        self.assertEqual(monitoring._company_id_ctx.get(), 7)
        monitoring._company_id_ctx.set(None)


class SentryRequestIdTagTests(SimpleTestCase):
    """BPQ9 — chaque évènement Sentry porte le `request_id` que Django renvoie au
    navigateur (en-tête X-Request-Id + enveloppe 500), pour relier une ligne
    `serveur` du journal des problèmes à sa pile d'appel."""

    def test_before_send_injects_request_id_tag(self):
        token = monitoring._request_id_ctx.set('a1b2c3d4e5f6')
        try:
            event = monitoring._before_send({}, {})
            self.assertEqual(event['tags']['request_id'], 'a1b2c3d4e5f6')
        finally:
            monitoring._request_id_ctx.reset(token)

    def test_before_send_without_request_id_is_untouched(self):
        token = monitoring._request_id_ctx.set(None)
        try:
            event = monitoring._before_send({'level': 'error'}, {})
            self.assertNotIn('request_id', event.get('tags', {}))
        finally:
            monitoring._request_id_ctx.reset(token)

    def test_bind_request_id_is_noop_without_sentry(self):
        monitoring.bind_request_id('deadbeef')
        self.assertEqual(monitoring._request_id_ctx.get(), 'deadbeef')
        monitoring._request_id_ctx.set(None)

    def test_request_id_middleware_binds_the_id_for_sentry(self):
        from django.http import HttpResponse
        from django.test import RequestFactory

        from core.middleware import RequestIdMiddleware

        vu = {}

        def vue(request):
            vu['pendant'] = monitoring._request_id_ctx.get()
            return HttpResponse('ok')

        request = RequestFactory().get('/api/django/x/')
        request.META['HTTP_X_REQUEST_ID'] = 'req-0042'
        RequestIdMiddleware(vue)(request)
        # Le tag est posé AVANT la vue (une 500 levée dedans le voit)…
        self.assertEqual(vu['pendant'], 'req-0042')
        # …et retiré après : la requête suivante du même worker ne l'hérite pas.
        self.assertIsNone(monitoring._request_id_ctx.get())
