"""ADSDEEP30 — Méthodes d'ÉCRITURE du client Meta (agir sur des objets existants).

Couvre ``swap_ad_creative`` (créer un NOUVEAU adcreative puis rattacher via
``POST /<ad>`` — AdCreative write-once, dossier §4), ``rename_object`` et
``set_campaign_spend_cap``. INVARIANT PERMANENT (règle #3) prouvé ici : aucune
de ces méthodes n'envoie de ``status`` (ni ACTIVE ni PAUSED — une édition ne
touche pas le statut), aucune n'accepte un kwarg ``status`` (TypeError), et un
``status`` glissé via ``extra_fields`` est SILENCIEUSEMENT retiré. Tests purs →
``SimpleTestCase`` (aucune base de données), MockTransport (aucun réseau).
"""
from urllib.parse import parse_qs

import httpx
from django.test import SimpleTestCase

from apps.adsengine import meta_client as mc

TOKEN = 'tok-write-1'


def make_client(handler, **kwargs):
    transport = httpx.MockTransport(handler)
    http_client = httpx.Client(transport=transport)
    return mc.MetaClient(
        access_token=TOKEN, ad_account_id='act_1', http_client=http_client,
        max_retries=0, backoff_base=0, **kwargs)


def body_of(request):
    return parse_qs(request.content.decode('utf-8'))


class SwapAdCreativeTests(SimpleTestCase):
    def test_creates_new_creative_then_attaches_to_ad(self):
        """Deux appels : POST adcreatives (nouveau créatif) puis POST /<ad> avec
        le nouveau creative_id — même ad_id (historique conservé)."""
        calls = []

        def handler(request):
            calls.append(request)
            if str(request.url).endswith('/act_1/adcreatives'):
                return httpx.Response(200, json={'id': 'cr-999'})
            return httpx.Response(200, json={'id': 'ad-1', 'success': True})

        client = make_client(handler)
        result = client.swap_ad_creative(
            ad_id='ad-1',
            creative_spec={'name': 'Nouveau texte',
                           'object_story_spec': {'page_id': 'p1'}})
        # 1er appel = création du créatif ; 2e = rattachement à l'ad.
        self.assertTrue(str(calls[0].url).endswith('/act_1/adcreatives'))
        self.assertTrue(str(calls[1].url).endswith('/ad-1'))
        # object_story_spec (dict imbriqué) part encodé JSON dans le formulaire.
        cr_body = body_of(calls[0])
        self.assertEqual(cr_body['object_story_spec'], ['{"page_id": "p1"}'])
        # Le rattachement porte le NOUVEAU creative_id.
        ad_body = body_of(calls[1])
        self.assertEqual(ad_body['creative'], ['{"creative_id": "cr-999"}'])
        self.assertEqual(result['creative_id'], 'cr-999')

    def test_reuses_existing_creative_id_no_creation(self):
        """``creative_id`` fourni → aucun POST adcreatives, juste le rattachement."""
        calls = []

        def handler(request):
            calls.append(request)
            return httpx.Response(200, json={'id': 'ad-2'})

        client = make_client(handler)
        client.swap_ad_creative(ad_id='ad-2', creative_id='cr-existing')
        self.assertEqual(len(calls), 1)
        self.assertTrue(str(calls[0].url).endswith('/ad-2'))
        self.assertEqual(
            body_of(calls[0])['creative'], ['{"creative_id": "cr-existing"}'])

    def test_never_sends_status_even_smuggled(self):
        captured = []

        def handler(request):
            captured.append(request)
            if str(request.url).endswith('/act_1/adcreatives'):
                return httpx.Response(200, json={'id': 'cr-1'})
            return httpx.Response(200, json={'id': 'ad-3'})

        client = make_client(handler)
        client.swap_ad_creative(
            ad_id='ad-3',
            creative_spec={'name': 'X', 'status': 'ACTIVE'},
            extra_fields={'status': 'ACTIVE'})
        for req in captured:
            raw = req.content.decode('utf-8')
            self.assertNotIn('status', body_of(req))
            self.assertNotIn('ACTIVE', raw)

    def test_status_kwarg_raises_typeerror(self):
        client = make_client(lambda r: httpx.Response(200, json={'id': '1'}))
        with self.assertRaises(TypeError):
            client.swap_ad_creative(ad_id='ad-1', creative_id='c1',
                                    status='ACTIVE')

    def test_requires_spec_or_id(self):
        client = make_client(lambda r: httpx.Response(200, json={}))
        with self.assertRaises(mc.MetaError):
            client.swap_ad_creative(ad_id='ad-1')


class RenameObjectTests(SimpleTestCase):
    def test_sends_only_name(self):
        captured = {}

        def handler(request):
            captured['request'] = request
            return httpx.Response(200, json={'success': True})

        client = make_client(handler)
        result = client.rename_object(object_id='c1', name='Campagne 2026')
        self.assertEqual(result, {'success': True})
        req = captured['request']
        form = body_of(req)
        self.assertEqual(form['name'], ['Campagne 2026'])
        self.assertNotIn('status', form)
        self.assertTrue(str(req.url).endswith('/c1'))

    def test_status_kwarg_raises_and_smuggled_status_stripped(self):
        captured = {}

        def handler(request):
            captured['request'] = request
            return httpx.Response(200, json={})

        client = make_client(handler)
        with self.assertRaises(TypeError):
            client.rename_object(object_id='c1', name='X', status='ACTIVE')
        client.rename_object(object_id='c1', name='X',
                             extra_fields={'status': 'ACTIVE'})
        raw = captured['request'].content.decode('utf-8')
        self.assertNotIn('ACTIVE', raw)
        self.assertNotIn('status', body_of(captured['request']))


class SetCampaignSpendCapTests(SimpleTestCase):
    def test_sends_spend_cap_never_status(self):
        captured = {}

        def handler(request):
            captured['request'] = request
            return httpx.Response(200, json={'success': True})

        client = make_client(handler)
        client.set_campaign_spend_cap(campaign_id='c1', spend_cap=500000)
        form = body_of(captured['request'])
        self.assertEqual(form['spend_cap'], ['500000'])
        self.assertNotIn('status', form)
        self.assertTrue(str(captured['request'].url).endswith('/c1'))

    def test_status_kwarg_raises(self):
        client = make_client(lambda r: httpx.Response(200, json={}))
        with self.assertRaises(TypeError):
            client.set_campaign_spend_cap(
                campaign_id='c1', spend_cap=0, status='ACTIVE')


class NoActivationMethodStillHoldsTests(SimpleTestCase):
    def test_write_methods_do_not_expose_activation(self):
        """ADSDEEP30 n'introduit AUCUNE méthode d'activation / dé-pause."""
        client = make_client(lambda r: httpx.Response(200, json={}))
        for forbidden in (
            'activate', 'activate_campaign', 'unpause', 'resume', 'enable',
            'enable_campaign', 'set_active', 'set_status',
        ):
            self.assertFalse(hasattr(client, forbidden))
        # Les 3 nouvelles méthodes d'écriture EXISTENT bien.
        for present in (
                'swap_ad_creative', 'rename_object', 'set_campaign_spend_cap'):
            self.assertTrue(callable(getattr(client, present)))
