"""ADSDEEP37 — Duplication d'un ad set (+ 1 ad réutilisant le créatif LIVE).

Couvre : ``MetaClient.duplicate_adset_with_ad`` — les DEUX créations internes
naissent TOUJOURS PAUSED (invariant permanent règle #3), la 2e réutilise le
``creative_id`` fourni (jamais un nouveau créatif) et le NOUVEL ``adset_id``
renvoyé par la 1re création ; ``services.propose_duplicate`` — construit le
payload depuis le miroir source (budget copié, créatif LIVE de la première ad
portant un ``AdCreativeMirror`` — un ``AdMirror`` seul ne suffit pas) et refuse
de proposer une action à moitié quand la donnée manque ; le cycle complet
propose→approuve→applique.
"""
from urllib.parse import parse_qs
from unittest.mock import Mock

import httpx
from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase

from authentication.models import Company

from apps.adsengine import meta_client as mc
from apps.adsengine import services
from apps.adsengine.models import (
    AdCampaignMirror, AdCreativeMirror, AdMirror, AdSetMirror, EngineAction,
)

User = get_user_model()

TOKEN = 'tok-dup'


def make_client(handler, **kwargs):
    transport = httpx.MockTransport(handler)
    http_client = httpx.Client(transport=transport)
    return mc.MetaClient(
        access_token=TOKEN, ad_account_id='act_1', http_client=http_client,
        max_retries=0, backoff_base=0, **kwargs)


def body_of(request):
    return parse_qs(request.content.decode('utf-8'))


class MetaClientDuplicationTests(SimpleTestCase):
    def test_duplicate_adset_with_ad_born_paused_and_reuses_creative(self):
        captured = []

        def handler(request):
            captured.append(request)
            if len(captured) == 1:
                return httpx.Response(200, json={'id': 'new-adset-1'})
            return httpx.Response(200, json={'id': 'new-ad-1'})

        client = make_client(handler)
        result = client.duplicate_adset_with_ad(
            campaign_id='camp-1', new_adset_name='AdSet (copie)',
            new_ad_name='Ad (copie)', creative_id='cr-live-9',
            adset_extra_fields={'daily_budget': 5000})

        self.assertEqual(result, {
            'adset': {'id': 'new-adset-1'}, 'ad': {'id': 'new-ad-1'}})
        self.assertEqual(len(captured), 2)

        adset_body = body_of(captured[0])
        self.assertEqual(adset_body['status'], ['PAUSED'])
        self.assertEqual(adset_body['campaign_id'], ['camp-1'])
        self.assertEqual(adset_body['daily_budget'], ['5000'])

        ad_body = body_of(captured[1])
        self.assertEqual(ad_body['status'], ['PAUSED'])
        # La 2e création cible le NOUVEL adset_id renvoyé par la 1re — jamais
        # la source, jamais un id inventé.
        self.assertEqual(ad_body['adset_id'], ['new-adset-1'])
        # RÉUTILISE le créatif LIVE fourni (jamais un nouveau créatif créé).
        self.assertIn('cr-live-9', captured[1].content.decode('utf-8'))

    def test_raises_if_adset_creation_returns_no_id(self):
        client = make_client(lambda r: httpx.Response(200, json={}))
        with self.assertRaises(mc.MetaError):
            client.duplicate_adset_with_ad(
                campaign_id='camp-1', new_adset_name='X', new_ad_name='Y',
                creative_id='cr-1')

    def test_status_kwarg_smuggled_via_ad_extra_fields_stays_paused(self):
        captured = []

        def handler(request):
            captured.append(request)
            if len(captured) == 1:
                return httpx.Response(200, json={'id': 'adset-x'})
            return httpx.Response(200, json={'id': 'ad-x'})

        client = make_client(handler)
        client.duplicate_adset_with_ad(
            campaign_id='c1', new_adset_name='A', new_ad_name='B',
            creative_id='cr-2', ad_extra_fields={'status': 'ACTIVE'})
        ad_body = body_of(captured[1])
        self.assertEqual(ad_body['status'], ['PAUSED'])


class ProposeDuplicateTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='Dup Co', slug='dup-co')
        self.user = User.objects.create_user(
            username='dup-approver', password='x', company=self.company)
        self.campaign = AdCampaignMirror.objects.create(
            company=self.company, meta_id='camp-42', name='Campagne source')
        self.adset = AdSetMirror.objects.create(
            company=self.company, meta_id='adset-42', name='AdSet source',
            campaign=self.campaign, budget=15000)
        self.ad = AdMirror.objects.create(
            company=self.company, meta_id='ad-42', name='Ad source',
            adset=self.adset)
        AdCreativeMirror.objects.create(
            company=self.company, ad=self.ad, creative_meta_id='cr-live-42',
            body='Texte diffusé')

    def test_propose_duplicate_builds_payload_from_mirror(self):
        action = services.propose_duplicate(self.company, adset=self.adset)
        self.assertEqual(action.kind, services.KIND_DUPLICATE)
        self.assertEqual(action.payload['campaign_id'], 'camp-42')
        self.assertEqual(action.payload['creative_id'], 'cr-live-42')
        self.assertEqual(
            action.payload['adset_extra_fields']['daily_budget'], 15000)
        self.assertIn('copie', action.payload['new_adset_name'])

    def test_propose_duplicate_fails_without_creative_mirror(self):
        AdCreativeMirror.objects.filter(ad=self.ad).delete()
        with self.assertRaises(ValueError):
            services.propose_duplicate(self.company, adset=self.adset)
        self.assertEqual(EngineAction.objects.count(), 0)

    def test_propose_duplicate_fails_without_campaign(self):
        orphan = AdSetMirror.objects.create(
            company=self.company, meta_id='adset-orphan', name='Orphelin')
        with self.assertRaises(ValueError):
            services.propose_duplicate(self.company, adset=orphan)

    def test_full_cycle_reaches_client_born_paused_compatible(self):
        action = services.propose_duplicate(self.company, adset=self.adset)
        services.approve_action(action, user=self.user)
        client = Mock()
        client.duplicate_adset_with_ad.return_value = {
            'adset': {'id': 'new-1'}, 'ad': {'id': 'new-2'}}
        services.apply_action(action, client=client)
        action.refresh_from_db()
        self.assertEqual(action.status, EngineAction.Statut.APPLIQUEE)
        client.duplicate_adset_with_ad.assert_called_once_with(
            campaign_id='camp-42', new_adset_name='AdSet source (copie)',
            new_ad_name='Ad source (copie)', creative_id='cr-live-42',
            adset_extra_fields={'daily_budget': 15000}, ad_extra_fields=None)
        self.assertEqual(
            action.result, {'adset': {'id': 'new-1'}, 'ad': {'id': 'new-2'}})
