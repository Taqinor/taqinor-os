"""Tests FG371 — passerelle SMS (fondation, branchable) + registre d'intégrations.

Couvre :
  * le registre ``core.integrations`` (enregistrement, lookup, listing) ;
  * ``GenericHttpSmsProvider.is_configured`` (URL + secret requis) ;
  * ``send_sms`` no-op propre quand aucune config (sent=False, pas d'exception) ;
  * ``send_sms`` résout la config société et appelle le connecteur (mocké) ;
  * découplage : aucun import d'app domaine.
"""
import os
from unittest import mock

from django.test import TestCase

from authentication.models import Company
from core import integrations, sms


class IntegrationRegistryTests(TestCase):
    def test_generic_sms_provider_is_registered(self):
        cls = integrations.get_provider_class(integrations.TYPE_SMS,
                                              'generic_http')
        self.assertIs(cls, sms.GenericHttpSmsProvider)

    def test_list_providers_includes_sms(self):
        listed = integrations.list_providers(integrations.TYPE_SMS)
        codes = {p['code'] for p in listed}
        self.assertIn('generic_http', codes)

    def test_register_provider_requires_type_and_code(self):
        with self.assertRaises(ValueError):
            integrations.register_provider(type('X', (), {}))

    def test_resolve_secret_from_env(self):
        with mock.patch.dict(os.environ, {'MY_SMS_KEY': 'sek'}):
            self.assertEqual(integrations.resolve_secret('MY_SMS_KEY'), 'sek')
        self.assertIsNone(integrations.resolve_secret(''))


class GenericHttpSmsProviderTests(TestCase):
    def test_not_configured_without_url_or_secret(self):
        self.assertFalse(
            sms.GenericHttpSmsProvider(config={}, secret='k').is_configured())
        self.assertFalse(
            sms.GenericHttpSmsProvider(
                config={'base_url': 'https://x'}, secret=None).is_configured())

    def test_configured_with_url_and_secret(self):
        p = sms.GenericHttpSmsProvider(
            config={'base_url': 'https://x'}, secret='k')
        self.assertTrue(p.is_configured())

    def test_send_noop_when_not_configured(self):
        p = sms.GenericHttpSmsProvider(config={}, secret=None)
        res = p.send('+212600000000', 'bonjour')
        self.assertFalse(res.sent)
        self.assertEqual(res.provider, 'generic_http')


class SendSmsDispatchTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='ACME')

    def test_no_config_returns_noop(self):
        res = sms.send_sms(self.company, '+212600000000', 'salut')
        self.assertFalse(res.sent)
        self.assertIn('Aucune', res.detail)

    def test_unknown_provider_returns_noop(self):
        from core.models import IntegrationConfig
        IntegrationConfig.objects.create(
            company=self.company, integration_type=integrations.TYPE_SMS,
            provider='inconnu', actif=True)
        res = sms.send_sms(self.company, '+212600000000', 'salut')
        self.assertFalse(res.sent)
        self.assertIn('inconnu', res.detail)

    def test_dispatch_calls_provider(self):
        from core.models import IntegrationConfig
        IntegrationConfig.objects.create(
            company=self.company, integration_type=integrations.TYPE_SMS,
            provider='generic_http', actif=True,
            settings={'base_url': 'https://x'}, secret_ref='SMS_TEST_KEY')
        with mock.patch.dict(os.environ, {'SMS_TEST_KEY': 'abc'}), \
                mock.patch.object(
                    sms.GenericHttpSmsProvider, 'send',
                    return_value=sms.SmsResult(sent=True, provider='generic_http')) as m:
            res = sms.send_sms(self.company, '+212600000000', 'salut')
        self.assertTrue(res.sent)
        m.assert_called_once()
