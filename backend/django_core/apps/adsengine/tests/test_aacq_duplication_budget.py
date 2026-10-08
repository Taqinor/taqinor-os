"""AACQ16 — Le type de budget d'un ad set miroir est conservé ; une duplication
ne transforme plus un budget à vie en budget quotidien et ne contourne plus le
plafond quotidien. Vrai ``MetaClient`` en transport simulé (aucun appel réel).
"""
from urllib.parse import parse_qs

import httpx
from django.test import TestCase

from authentication.models import Company

from apps.adsengine import guardrails, services, sync
from apps.adsengine.meta_client import MetaClient
from apps.adsengine.models import (
    AdCampaignMirror, AdCreativeMirror, AdMirror, AdSetMirror, EngineAction,
    GuardrailConfig,
)


class DuplicationBudgetTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='Dup', slug='aacq16-dup')
        GuardrailConfig.objects.create(
            company=self.company, daily_budget_ceiling_mad=100)
        AdCampaignMirror.objects.create(
            company=self.company, meta_id='cmp-16', name='CAMP',
            status='ACTIVE')
        self.requests = []

    def _adset(self, meta_id, budget_payload):
        sync.sync_adsets(self.company, [{
            'id': meta_id, 'name': f'AS {meta_id}', 'status': 'ACTIVE',
            'campaign_id': 'cmp-16', **budget_payload}])
        adset = AdSetMirror.objects.get(company=self.company, meta_id=meta_id)
        ad = AdMirror.objects.create(
            company=self.company, meta_id=f'ad-{meta_id}', name='AD',
            adset=adset)
        AdCreativeMirror.objects.create(
            company=self.company, ad=ad, creative_meta_id=f'cr-{meta_id}')
        return adset

    def _client(self):
        def handler(request):
            self.requests.append(request)
            return httpx.Response(200, json={'id': str(90 + len(self.requests))})
        return MetaClient(
            access_token='tok', ad_account_id='act_x',
            http_client=httpx.Client(transport=httpx.MockTransport(handler)),
            max_retries=0, backoff_base=0)

    def _approuver(self, action):
        EngineAction.objects.filter(pk=action.pk).update(
            status=EngineAction.Statut.APPROUVEE)
        action.refresh_from_db()
        return action

    def test_source_a_vie_refusee(self):
        adset = self._adset('as-life', {'lifetime_budget': '300000'})
        self.assertEqual(adset.budget_type, AdSetMirror.BUDGET_TYPE_LIFETIME)
        with self.assertRaises(ValueError) as ctx:
            services.propose_duplicate(self.company, adset=adset)
        self.assertIn('Budget à vie : dupliquez dans Meta', str(ctx.exception))
        self.assertFalse(EngineAction.objects.exists())
        self.assertEqual(self.requests, [])
        # Seconde synchro : type identique.
        sync.sync_adsets(self.company, [{
            'id': 'as-life', 'name': 'AS as-life', 'status': 'ACTIVE',
            'campaign_id': 'cmp-16', 'lifetime_budget': '300000'}])
        adset.refresh_from_db()
        self.assertEqual(adset.budget_type, AdSetMirror.BUDGET_TYPE_LIFETIME)

    def test_daily_zero_lifetime_refusee(self):
        adset = self._adset(
            'as-d0', {'daily_budget': '0', 'lifetime_budget': '300000'})
        self.assertEqual(adset.budget_type, AdSetMirror.BUDGET_TYPE_LIFETIME)
        with self.assertRaises(ValueError):
            services.propose_duplicate(self.company, adset=adset)
        self.assertFalse(EngineAction.objects.exists())

    def test_source_quotidienne_reprise(self):
        adset = self._adset('as-day', {'daily_budget': '5000'})
        self.assertEqual(adset.budget_type, AdSetMirror.BUDGET_TYPE_DAILY)
        action = self._approuver(
            services.propose_duplicate(self.company, adset=adset))
        services.apply_action(action, client=self._client())
        action.refresh_from_db()
        self.assertEqual(action.status, EngineAction.Statut.APPLIQUEE)
        first = self.requests[0]
        self.assertTrue(first.url.path.endswith('/act_x/adsets'), first.url)
        form = parse_qs(first.content.decode('utf-8'))
        self.assertEqual(form['daily_budget'], ['5000'])
        self.assertEqual(form['status'], ['PAUSED'])

    def test_plafond_applique_au_duplicata(self):
        # 20 000 centimes = 200 MAD > plafond 100 MAD.
        adset = self._adset('as-big', {'daily_budget': '20000'})
        action = self._approuver(
            services.propose_duplicate(self.company, adset=adset))
        with self.assertRaises(guardrails.GuardrailViolation):
            services.apply_action(action, client=self._client())
        self.assertEqual(self.requests, [])
        action.refresh_from_db()
        self.assertEqual(action.status, EngineAction.Statut.ECHOUEE)
