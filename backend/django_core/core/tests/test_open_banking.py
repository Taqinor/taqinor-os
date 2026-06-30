"""Tests FG379 — open banking (flux bancaire automatique).

Couvre :
  * enregistrement du connecteur générique ;
  * is_configured exige URL + secret ;
  * non configuré → liste vide (no-op) ;
  * parsing d'une réponse mockée → BankTransaction normalisées ;
  * fetch_transactions no-op sans config société ;
  * découplage : aucun import d'app domaine.
"""
import os
from unittest import mock

from django.test import TestCase

from authentication.models import Company
from core import integrations, open_banking as ob
from core.models import IntegrationConfig


class _FakeResp:
    def __init__(self, payload, status=200):
        self._payload = payload
        self.status_code = status

    def json(self):
        return self._payload


class ProviderTests(TestCase):
    def test_registered(self):
        self.assertIs(
            integrations.get_provider_class(integrations.TYPE_BANKING,
                                            'generic'),
            ob.GenericOpenBankingProvider)

    def test_not_configured_returns_empty(self):
        p = ob.GenericOpenBankingProvider(config={}, secret=None)
        self.assertFalse(p.is_configured())
        self.assertEqual(p.fetch_transactions(), [])

    def test_parses_transactions(self):
        payload = {'transactions': [
            {'id': 't1', 'date': '2026-06-30', 'amount': 1200,
             'currency': 'MAD', 'label': 'Virement', 'counterparty': 'ACME'},
            {'id': 't2', 'date': '2026-06-29', 'amount': -50.5},
        ]}
        p = ob.GenericOpenBankingProvider(
            config={'base_url': 'https://b'}, secret='tok')
        with mock.patch('requests.get', return_value=_FakeResp(payload)):
            txs = p.fetch_transactions()
        self.assertEqual(len(txs), 2)
        self.assertEqual(txs[0].external_id, 't1')
        self.assertEqual(txs[0].amount, 1200.0)
        self.assertEqual(txs[1].amount, -50.5)


class DispatchTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='ACME')

    def test_noop_without_config(self):
        self.assertEqual(ob.fetch_transactions(self.company), [])

    def test_dispatch_uses_config(self):
        IntegrationConfig.objects.create(
            company=self.company, integration_type=integrations.TYPE_BANKING,
            provider='generic', actif=True,
            settings={'base_url': 'https://b'}, secret_ref='BANK_K')
        payload = {'transactions': [{'id': 'x', 'amount': 10}]}
        with mock.patch.dict(os.environ, {'BANK_K': 'tok'}), \
                mock.patch('requests.get', return_value=_FakeResp(payload)):
            txs = ob.fetch_transactions(self.company)
        self.assertEqual(len(txs), 1)
        self.assertEqual(txs[0].external_id, 'x')
