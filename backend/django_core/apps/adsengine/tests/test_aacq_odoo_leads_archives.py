"""AACQ35 — ``OdooClient.read_leads`` lit aussi les leads ARCHIVÉS.

Un lead perdu (archivé, ``active=False``) reste un lead pour le coût par lead
du moteur publicitaire : le ``search_read`` de ``crm.lead`` porte le contexte
``active_test: False`` (comme ``crm/odoo_sync.py``). Le transport simulé
reproduit Odoo : SANS ce contexte, les archives ne sont pas renvoyées. Aucun
appel réseau ; ``is_won_lead`` exige toujours ``active`` pour une signature
par ``date_closed``.
"""
import json

import httpx
from django.test import SimpleTestCase, TestCase

from authentication.models import Company

from apps.adsengine import odoo_client, odoo_selectors
from apps.adsengine.odoo_leads import leads_by_day, odoo_leads_by_ad

LEADS = [
    {'id': 1, 'name': 'TAQINOR FORM vivant', 'phone': '+212611000001',
     'mobile': False, 'probability': 20, 'stage_id': [1, 'New'],
     'date_closed': False, 'active': True,
     'create_date': '2026-03-20 09:00:00'},
    {'id': 2, 'name': 'TAQINOR FORM perdu', 'phone': '+212611000002',
     'mobile': False, 'probability': 0, 'stage_id': [1, 'New'],
     'date_closed': '2026-03-25 09:00:00', 'active': False,
     'create_date': '2026-03-21 09:00:00'},
]


def _transport(calls):
    def handler(request):
        params = json.loads(request.content.decode('utf-8'))['params']
        if params['service'] == 'common':
            return httpx.Response(200, json={'result': 7})
        args = params['args']
        model, method = args[3], args[4]
        kwargs = args[6] if len(args) > 6 else {}
        calls.append((model, method, kwargs))
        if model == 'crm.lead' and method == 'search_read':
            ctx = kwargs.get('context') or {}
            rows = (LEADS if ctx.get('active_test') is False
                    else [r for r in LEADS if r['active']])
            if kwargs.get('offset'):
                rows = []
            return httpx.Response(200, json={'result': rows})
        return httpx.Response(200, json={'result': []})
    return handler


def _client(calls):
    return odoo_client.OdooClient(
        url='https://exemple.odoo.com', db='db', username='u',
        api_key='k', max_retries=0, backoff_base=0,
        http_client=httpx.Client(transport=httpx.MockTransport(
            _transport(calls))))


class ReadLeadsArchivesTests(SimpleTestCase):
    def test_read_leads_inclut_les_archives(self):
        for since in (None, '2026-03-01'):
            with self.subTest(since=since):
                calls = []
                leads = _client(calls).read_leads(since)
                self.assertEqual({r['id'] for r in leads}, {1, 2})
                lectures = [kw for (m, meth, kw) in calls
                            if m == 'crm.lead' and meth == 'search_read']
                self.assertTrue(lectures)
                for kw in lectures:
                    self.assertEqual(kw.get('context'), {'active_test': False})

    def test_signature_exige_toujours_active(self):
        self.assertFalse(odoo_selectors.is_won_lead(LEADS[1]))
        self.assertTrue(odoo_selectors.is_won_lead(
            {**LEADS[1], 'active': True}))


class CplPerdusTests(TestCase):
    def test_cpl_compte_les_perdus(self):
        company = Company.objects.create(nom='AACQ35', slug='aacq35')
        res = odoo_leads_by_ad(company, client=_client([]))
        self.assertEqual(res['total'], 2)
        jours = leads_by_day(company, client=_client([]))
        self.assertEqual(sum(d['total'] for d in jours['days']), 2)
