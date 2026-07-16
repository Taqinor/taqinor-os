"""ADSENG30 — Tests de l'ad « style post » via object_story_spec (mocked).

Prouve : la nouvelle méthode crée l'ad TOUJOURS PAUSED (comme toute création —
règle #3), transporte le ``object_story_spec`` encodé JSON dans ``creative``,
n'accepte AUCUN ``status`` (``TypeError``), et force PAUSED même si un ``status``
est glissé via ``extra_fields``. Tests purs → ``SimpleTestCase`` (aucun réseau).
"""
import json
from urllib.parse import parse_qs

import httpx
from django.test import SimpleTestCase

from apps.adsengine import meta_client as mc

TOKEN = 'tok-73951'

OSS = {
    'page_id': '1000',
    'link_data': {
        'message': 'Passez au solaire.',
        'link': 'https://taqinor.ma',
        'call_to_action': {'type': 'LEARN_MORE'},
    },
}


def make_client(handler, **kwargs):
    transport = httpx.MockTransport(handler)
    http_client = httpx.Client(transport=transport)
    return mc.MetaClient(
        access_token=TOKEN, ad_account_id='act_1', http_client=http_client,
        max_retries=0, backoff_base=0, **kwargs)


def body_of(request):
    return parse_qs(request.content.decode('utf-8'))


class ObjectStorySpecAdTests(SimpleTestCase):
    def test_object_story_spec_ad_is_created_paused(self):
        captured = {}

        def handler(request):
            captured['request'] = request
            return httpx.Response(200, json={'id': 'ad-1'})

        client = make_client(handler)
        result = client.create_ad_with_object_story_spec(
            name='Post-style', adset_id='as-1', object_story_spec=OSS)
        self.assertEqual(result, {'id': 'ad-1'})
        form = body_of(captured['request'])
        # INVARIANT #3 : né PAUSED, jamais ACTIVE.
        self.assertEqual(form['status'], ['PAUSED'])
        self.assertNotIn('ACTIVE', captured['request'].content.decode('utf-8'))
        # Le object_story_spec voyage encodé JSON dans ``creative``.
        creative = json.loads(form['creative'][0])
        self.assertEqual(creative['object_story_spec']['page_id'], '1000')

    def test_status_kwarg_raises_typeerror(self):
        client = make_client(lambda r: httpx.Response(200, json={'id': '1'}))
        with self.assertRaises(TypeError):
            client.create_ad_with_object_story_spec(
                name='X', adset_id='as-1', object_story_spec=OSS,
                status='ACTIVE')

    def test_status_smuggled_via_extra_fields_is_forced_paused(self):
        captured = {}

        def handler(request):
            captured['request'] = request
            return httpx.Response(200, json={'id': '9'})

        client = make_client(handler)
        client.create_ad_with_object_story_spec(
            name='X', adset_id='as-1', object_story_spec=OSS,
            extra_fields={'status': 'ACTIVE'})
        form = body_of(captured['request'])
        self.assertEqual(form['status'], ['PAUSED'])
