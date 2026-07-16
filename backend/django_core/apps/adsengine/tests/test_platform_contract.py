"""ADSENG48 — Tests de contrat golden de l'interface ``AdsPlatform``.

Prouve : ``MetaPlatform`` implémente le contrat SANS aucun changement de
comportement (mêmes requêtes émises que l'appel direct au ``MetaClient`` — zéro
diff), et l'INVARIANT PERMANENT (règles #3/#4) SURVIT à l'extraction :

  * aucune méthode de création n'accepte ``status`` (``TypeError``) ;
  * il n'existe AUCUN chemin de création ACTIVE (aucune méthode d'activation) ;
  * toute création émet ``status=PAUSED`` ; ``update_status_paused`` = PAUSED-only.
"""
from urllib.parse import parse_qs

import httpx
from django.test import SimpleTestCase

from apps.adsengine import meta_client as mc
from apps.adsengine.platforms import AdsPlatform, normalize_insight_row
from apps.adsengine.platforms.meta import MetaPlatform

TOKEN = 'tok-contract'


def _capture_client():
    captured = []

    def handler(request):
        captured.append(request)
        return httpx.Response(200, json={'id': 'x', 'data': []})

    http = httpx.Client(transport=httpx.MockTransport(handler))
    client = mc.MetaClient(
        access_token=TOKEN, ad_account_id='act_1', http_client=http,
        max_retries=0, backoff_base=0)
    return client, captured


def _body(request):
    return parse_qs(request.content.decode('utf-8'))


class InterfaceShapeTests(SimpleTestCase):
    def test_meta_platform_is_an_adsplatform(self):
        client, _ = _capture_client()
        platform = MetaPlatform.from_client(client)
        self.assertIsInstance(platform, AdsPlatform)
        self.assertEqual(platform.name, 'meta')

    def test_capabilities_paused_by_default(self):
        client, _ = _capture_client()
        platform = MetaPlatform.from_client(client)
        caps = platform.capabilities()
        self.assertTrue(caps.get('paused_by_default'))
        self.assertTrue(platform.paused_by_default())

    def test_normalized_insights_are_agnostic_floats(self):
        rows = normalize_insight_row(
            {'spend': '12.50', 'results': '5', 'frequency': '1.3'})
        self.assertEqual(rows['spend'], 12.5)
        self.assertEqual(rows['results'], 5.0)
        self.assertEqual(rows['cpl'], 2.5)  # dérivé spend/results
        self.assertEqual(rows['raw']['spend'], '12.50')


class ZeroBehaviorDiffTests(SimpleTestCase):
    """Golden : la plateforme émet EXACTEMENT les mêmes requêtes que le client."""

    def _assert_same_request(self, a, b):
        self.assertEqual(a.method, b.method)
        self.assertEqual(a.url.path, b.url.path)
        self.assertEqual(str(a.url), str(b.url))
        self.assertEqual(a.content, b.content)
        self.assertEqual(a.headers.get('Authorization'),
                         b.headers.get('Authorization'))

    def test_create_campaign_identical(self):
        client, cap = _capture_client()
        platform = MetaPlatform.from_client(client)
        client.create_campaign(name='Solar', objective='OUTCOME_LEADS')
        platform.create_campaign(name='Solar', objective='OUTCOME_LEADS')
        self.assertEqual(len(cap), 2)
        self._assert_same_request(cap[0], cap[1])
        # …et ce payload identique porte bien status=PAUSED.
        self.assertEqual(_body(cap[1])['status'], ['PAUSED'])

    def test_create_adset_and_ad_identical(self):
        client, cap = _capture_client()
        platform = MetaPlatform.from_client(client)
        client.create_adset(name='AS', campaign_id='c1')
        platform.create_adset(name='AS', campaign_id='c1')
        self._assert_same_request(cap[0], cap[1])
        cap.clear()
        client.create_ad(name='AD', adset_id='a1')
        platform.create_ad(name='AD', adset_id='a1')
        self._assert_same_request(cap[0], cap[1])

    def test_update_status_paused_identical_and_paused_only(self):
        client, cap = _capture_client()
        platform = MetaPlatform.from_client(client)
        client.update_status_paused(object_id='c1', level='campaign')
        platform.update_status_paused(object_id='c1', level='campaign')
        self._assert_same_request(cap[0], cap[1])
        self.assertEqual(_body(cap[1])['status'], ['PAUSED'])

    def test_get_campaigns_identical(self):
        client, cap = _capture_client()
        platform = MetaPlatform.from_client(client)
        client.get_campaigns()
        platform.get_campaigns()
        self._assert_same_request(cap[0], cap[1])


class InvariantSurvivesExtractionTests(SimpleTestCase):
    def test_no_create_path_accepts_status(self):
        client, _ = _capture_client()
        platform = MetaPlatform.from_client(client)
        with self.assertRaises(TypeError):
            platform.create_campaign(
                name='X', objective='OUTCOME_LEADS', status='ACTIVE')
        with self.assertRaises(TypeError):
            platform.create_adset(name='X', campaign_id='1', status='ACTIVE')
        with self.assertRaises(TypeError):
            platform.create_ad(name='X', adset_id='1', status='ACTIVE')

    def test_no_active_creation_path_exists(self):
        # « aucun chemin de création ACTIVE » : aucune méthode d'activation/
        # dé-pause n'existe, ni sur la plateforme ni via sa délégation au client.
        client, _ = _capture_client()
        platform = MetaPlatform.from_client(client)
        for forbidden in (
            'activate', 'activate_campaign', 'unpause', 'resume', 'enable',
            'enable_campaign', 'set_active', 'set_status', 'go_live',
            'update_status_active',
        ):
            self.assertFalse(
                hasattr(platform, forbidden),
                f'Aucune méthode « {forbidden} » ne doit exister (invariant #3).')

    def test_status_smuggled_via_extra_fields_still_forced_paused(self):
        client, cap = _capture_client()
        platform = MetaPlatform.from_client(client)
        platform.create_campaign(
            name='X', objective='OUTCOME_LEADS',
            extra_fields={'status': 'ACTIVE', 'daily_budget': 5000})
        self.assertEqual(_body(cap[0])['status'], ['PAUSED'])

    def test_object_story_spec_create_delegates_and_is_paused(self):
        # La méthode déléguée (via __getattr__) reste PAUSED-forcée.
        client, cap = _capture_client()
        platform = MetaPlatform.from_client(client)
        platform.create_ad_with_object_story_spec(
            name='Boosted', adset_id='a1',
            object_story_spec={'page_id': 'p1', 'message': 'x'})
        self.assertEqual(_body(cap[0])['status'], ['PAUSED'])
