"""PUB117 — Écriture de créatifs : ``adcreatives`` + ad à spec DYNAMIQUE.

Le client savait LIRE ``object_story_spec``/``asset_feed_spec`` d'un créatif
diffusé mais ne savait pas en ÉCRIRE un : aucun chemin ne pouvait fabriquer un
créatif neuf ni une ad à spec dynamique (DCO).

Prouve :
  * les specs imbriquées voyagent ENCODÉES JSON dans les paramètres de formulaire ;
  * un adcreative est INERTE — une seule requête, sur ``adcreatives``, et AUCUN
    ``status`` n'est jamais émis (ni accepté, ni en douce via ``extra_fields``) ;
  * l'ad à ``asset_feed_spec`` naît PAUSED (invariant permanent règle #3) et
    passer ``status`` lève ``TypeError``, comme toutes les créations ;
  * une spec absente est refusée LOCALEMENT (aucun aller-retour réseau).

Tests purs → ``SimpleTestCase`` (transport mocké, aucun réseau).
"""
import json
from urllib.parse import parse_qs

import httpx
from django.test import SimpleTestCase

from apps.adsengine import meta_client as mc

TOKEN = 'tok-58412'

OSS = {
    'page_id': '1000',
    'link_data': {
        'message': 'Passez au solaire.',
        'link': 'https://taqinor.ma',
        'call_to_action': {'type': 'LEARN_MORE'},
    },
}

AFS = {
    'images': [{'hash': 'h1'}, {'hash': 'h2'}],
    'titles': [{'text': 'Titre A'}, {'text': 'Titre B'}],
    'bodies': [{'text': 'Corps A'}],
    'ad_formats': ['SINGLE_IMAGE'],
}


def capturing_client():
    requests = []

    def handler(request):
        requests.append(request)
        return httpx.Response(200, json={'id': f'obj-{len(requests)}'})

    client = mc.MetaClient(
        access_token=TOKEN, ad_account_id='act_1',
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
        max_retries=0, backoff_base=0)
    return client, requests


def body_of(request):
    return parse_qs(request.content.decode('utf-8'))


class CreateAdCreativeTests(SimpleTestCase):
    def test_object_story_spec_is_json_encoded_on_adcreatives_edge(self):
        client, reqs = capturing_client()
        result = client.create_adcreative(
            name='Créatif solaire', object_story_spec=OSS)
        self.assertEqual(result, {'id': 'obj-1'})
        self.assertEqual(len(reqs), 1)
        self.assertIn('act_1/adcreatives', str(reqs[0].url))
        form = body_of(reqs[0])
        self.assertEqual(form['name'], ['Créatif solaire'])
        spec = json.loads(form['object_story_spec'][0])
        self.assertEqual(spec['page_id'], '1000')
        self.assertEqual(
            spec['link_data']['call_to_action']['type'], 'LEARN_MORE')

    def test_asset_feed_spec_is_json_encoded(self):
        client, reqs = capturing_client()
        client.create_adcreative(name='DCO', asset_feed_spec=AFS)
        spec = json.loads(body_of(reqs[0])['asset_feed_spec'][0])
        self.assertEqual(len(spec['images']), 2)
        self.assertEqual(spec['titles'][1]['text'], 'Titre B')

    def test_adcreative_alone_is_inert_and_never_carries_a_status(self):
        client, reqs = capturing_client()
        client.create_adcreative(name='Inerte', object_story_spec=OSS)
        # UNE seule requête : un adcreative ne crée aucune ad, donc ne diffuse rien.
        self.assertEqual(len(reqs), 1)
        self.assertNotIn('/ads', str(reqs[0].url))
        self.assertNotIn('status', body_of(reqs[0]))

    def test_status_kwarg_raises_typeerror(self):
        client, _ = capturing_client()
        with self.assertRaises(TypeError):
            client.create_adcreative(
                name='X', object_story_spec=OSS, status='ACTIVE')

    def test_status_smuggled_via_extra_fields_is_dropped(self):
        client, reqs = capturing_client()
        client.create_adcreative(
            name='X', object_story_spec=OSS,
            extra_fields={'status': 'ACTIVE', 'degrees_of_freedom_spec': {
                'creative_features_spec': {}}})
        form = body_of(reqs[0])
        self.assertNotIn('status', form)
        self.assertNotIn('ACTIVE', reqs[0].content.decode('utf-8'))
        # Les autres champs imbriqués passent bien, encodés JSON.
        self.assertIn('degrees_of_freedom_spec', form)

    def test_no_spec_is_refused_locally_without_any_network_call(self):
        client, reqs = capturing_client()
        with self.assertRaises(mc.MetaError):
            client.create_adcreative(name='Vide')
        self.assertEqual(reqs, [])


class CreateAdWithAssetFeedSpecTests(SimpleTestCase):
    # PUB-P8/C2 — l'ACTEUR est obligatoire : toute ad à spec dynamique déclare
    # la Page qui publie (``object_story_spec.page_id``).
    ACTOR = {'page_id': '1000'}

    def test_ad_is_born_paused_and_carries_the_spec(self):
        client, reqs = capturing_client()
        result = client.create_ad_with_asset_feed_spec(
            name='DCO-1', adset_id='as-1', asset_feed_spec=AFS,
            object_story_spec=self.ACTOR)
        self.assertEqual(result, {'id': 'obj-1'})
        self.assertIn('act_1/ads', str(reqs[0].url))
        form = body_of(reqs[0])
        # INVARIANT #3 : née PAUSED, jamais ACTIVE.
        self.assertEqual(form['status'], ['PAUSED'])
        self.assertNotIn('ACTIVE', reqs[0].content.decode('utf-8'))
        self.assertEqual(form['adset_id'], ['as-1'])
        creative = json.loads(form['creative'][0])
        self.assertEqual(creative['asset_feed_spec']['ad_formats'],
                         ['SINGLE_IMAGE'])
        # L'acteur voyage AVEC la spec dynamique.
        self.assertEqual(creative['object_story_spec'], {'page_id': '1000'})

    def test_status_kwarg_raises_typeerror(self):
        client, _ = capturing_client()
        with self.assertRaises(TypeError):
            client.create_ad_with_asset_feed_spec(
                name='X', adset_id='as-1', asset_feed_spec=AFS,
                object_story_spec=self.ACTOR, status='ACTIVE')

    def test_status_smuggled_via_extra_fields_is_forced_paused(self):
        client, reqs = capturing_client()
        client.create_ad_with_asset_feed_spec(
            name='X', adset_id='as-1', asset_feed_spec=AFS,
            object_story_spec=self.ACTOR,
            extra_fields={'status': 'ACTIVE'})
        self.assertEqual(body_of(reqs[0])['status'], ['PAUSED'])

    def test_empty_spec_is_refused_locally_without_any_network_call(self):
        client, reqs = capturing_client()
        with self.assertRaises(mc.MetaError):
            client.create_ad_with_asset_feed_spec(
                name='X', adset_id='as-1', asset_feed_spec={},
                object_story_spec=self.ACTOR)
        self.assertEqual(reqs, [])

    def test_missing_actor_is_refused_locally_without_any_network_call(self):
        # PUB-P8/C2 — sans Page, Graph rejette le créatif : on le refuse ICI,
        # avant tout aller-retour réseau (raison FR explicite).
        client, reqs = capturing_client()
        for actor in (None, {}, {'page_id': ''}, {'page_id': '   '}):
            with self.assertRaises(mc.MetaError) as ctx:
                client.create_ad_with_asset_feed_spec(
                    name='X', adset_id='as-1', asset_feed_spec=AFS,
                    object_story_spec=actor)
            self.assertIn('object_story_spec.page_id', str(ctx.exception))
        self.assertEqual(reqs, [])


class NoUnpausePathTests(SimpleTestCase):
    def test_new_write_methods_add_no_activation_path(self):
        client, _ = capturing_client()
        for forbidden in ('activate', 'unpause', 'resume', 'enable',
                          'set_status', 'update_status_active'):
            self.assertFalse(
                hasattr(client, forbidden),
                f'Aucune méthode « {forbidden} » ne doit exister (règle #3).')
