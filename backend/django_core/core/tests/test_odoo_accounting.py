"""Tests FG378 — connecteur Odoo Compta (JSON-2, 2-way).

Couvre :
  * enregistrement du client ;
  * is_configured exige base_url+db+login+secret ;
  * RÈGLE #1 : l'endpoint passe TOUJOURS par /json/2 (jamais de SQL) ;
  * no-op propre sans config société ;
  * push/fetch relaient au client configuré (mocké) ;
  * découplage : aucun import d'app domaine.
"""
import os
from unittest import mock

from django.test import TestCase

from authentication.models import Company
from core import integrations, odoo_accounting as odoo
from core.models import IntegrationConfig


class ClientConfigTests(TestCase):
    def test_registered(self):
        self.assertIs(
            integrations.get_provider_class(odoo.TYPE_ODOO, 'odoo_json2'),
            odoo.OdooJson2Client)

    def test_is_configured_requires_all(self):
        c = odoo.OdooJson2Client(
            config={'base_url': 'https://o', 'db': 'd', 'login': 'l'},
            secret=None)
        self.assertFalse(c.is_configured())
        c2 = odoo.OdooJson2Client(
            config={'base_url': 'https://o', 'db': 'd', 'login': 'l'},
            secret='k')
        self.assertTrue(c2.is_configured())

    def test_endpoint_uses_json2_only(self):
        c = odoo.OdooJson2Client(config={'base_url': 'https://o/'}, secret='k')
        ep = c._endpoint('account.move/create')
        self.assertEqual(ep, 'https://o/json/2/account.move/create')
        self.assertIn('/json/2/', ep)


class DispatchTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='ACME')

    def test_noop_without_config(self):
        res = odoo.push_invoice(self.company, {'ref': 'F-1'})
        self.assertFalse(res['ok'])
        self.assertIn('Aucune', res['detail'])

    def test_push_relays_to_client(self):
        IntegrationConfig.objects.create(
            company=self.company, integration_type=odoo.TYPE_ODOO,
            provider='odoo_json2', actif=True,
            settings={'base_url': 'https://o', 'db': 'd', 'login': 'l'},
            secret_ref='ODOO_K')
        fake = {'ok': True, 'status': 200, 'data': {'id': 5}}
        with mock.patch.dict(os.environ, {'ODOO_K': 'tok'}), \
                mock.patch.object(odoo.OdooJson2Client, '_call',
                                  return_value=fake) as m:
            res = odoo.push_invoice(self.company, {'ref': 'F-1'})
        self.assertTrue(res['ok'])
        m.assert_called_once()
