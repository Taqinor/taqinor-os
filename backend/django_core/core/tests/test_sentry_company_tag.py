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
