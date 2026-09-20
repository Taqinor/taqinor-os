"""PUB122 — Upload d'assets AU COMPTE (adimages / advideos) + idempotence.

``CreativeAsset.file_key`` est une clé MinIO : Meta ne sait pas la lire. Sans
``image_hash``/``video_id`` de COMPTE, aucun créatif publicitaire ne peut
référencer un média de la créathèque — le client n'avait que les edges de PAGE.

Prouve :
  * ``upload_ad_image`` poste sur ``act_<id>/adimages`` (octets en base64 ou URL)
    et ``upload_ad_video`` sur ``act_<id>/advideos`` (``file_url``) ;
  * AUCUN statut n'est jamais émis ni accepté (un média uploadé ne diffuse rien) ;
  * le service persiste le hash / l'id, puis est IDEMPOTENT : un second appel ne
    fait AUCUN appel réseau ;
  * une erreur Graph (ou une réponse sans identifiant) laisse l'asset INTACT et
    remonte une raison FR.
"""
import base64
from urllib.parse import parse_qs

import httpx
from django.test import SimpleTestCase, TestCase

from authentication.models import Company
from apps.adsengine import creative_factory as cf
from apps.adsengine import meta_client as mc
from apps.adsengine.models import CreativeAsset

TOKEN = 'tok-90137'
PNG_BYTES = b'\x89PNG\r\n\x1a\nfake-bytes'
IMAGE_OK = {'images': {'photo.png': {'hash': 'h-abc', 'url': 'https://x/y'}}}


def capturing_client(response=None, status_code=200):
    requests = []

    def handler(request):
        requests.append(request)
        return httpx.Response(
            status_code, json=response if response is not None else {'id': 'v1'})

    client = mc.MetaClient(
        access_token=TOKEN, ad_account_id='act_1',
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
        max_retries=0, backoff_base=0)
    return client, requests


def body_of(request):
    return parse_qs(request.content.decode('utf-8'))


class UploadAdImageTests(SimpleTestCase):
    def test_bytes_are_base64_encoded_on_the_adimages_edge(self):
        client, reqs = capturing_client(IMAGE_OK)
        payload = client.upload_ad_image(
            image_bytes=PNG_BYTES, name='photo.png')
        self.assertIn('act_1/adimages', str(reqs[0].url))
        form = body_of(reqs[0])
        self.assertEqual(
            base64.b64decode(form['bytes'][0].encode('ascii')), PNG_BYTES)
        self.assertEqual(form['name'], ['photo.png'])
        self.assertNotIn('status', form)
        self.assertEqual(
            mc.MetaClient.image_hash_from_payload(payload), 'h-abc')

    def test_url_source_is_sent_as_url(self):
        client, reqs = capturing_client(IMAGE_OK)
        client.upload_ad_image(image_url='https://minio/presigned/p.png')
        form = body_of(reqs[0])
        self.assertEqual(form['url'], ['https://minio/presigned/p.png'])
        self.assertNotIn('bytes', form)

    def test_status_is_never_emitted_even_via_extra_fields(self):
        client, reqs = capturing_client(IMAGE_OK)
        client.upload_ad_image(
            image_bytes=PNG_BYTES, extra_fields={'status': 'ACTIVE'})
        self.assertNotIn('status', body_of(reqs[0]))
        self.assertNotIn('ACTIVE', reqs[0].content.decode('utf-8'))

    def test_no_source_is_refused_without_any_network_call(self):
        client, reqs = capturing_client(IMAGE_OK)
        with self.assertRaises(mc.MetaError):
            client.upload_ad_image()
        self.assertEqual(reqs, [])

    def test_hash_parser_degrades_cleanly(self):
        self.assertEqual(mc.MetaClient.image_hash_from_payload({}), '')
        self.assertEqual(mc.MetaClient.image_hash_from_payload(None), '')
        self.assertEqual(
            mc.MetaClient.image_hash_from_payload({'hash': 'plat'}), 'plat')


class UploadAdVideoTests(SimpleTestCase):
    def test_file_url_is_posted_on_the_advideos_edge(self):
        client, reqs = capturing_client({'id': 'vid-7'})
        payload = client.upload_ad_video(
            file_url='https://minio/presigned/reel.mp4', name='reel')
        self.assertIn('act_1/advideos', str(reqs[0].url))
        form = body_of(reqs[0])
        self.assertEqual(form['file_url'], ['https://minio/presigned/reel.mp4'])
        self.assertNotIn('status', form)
        self.assertEqual(payload['id'], 'vid-7')

    def test_missing_file_url_is_refused_without_any_network_call(self):
        client, reqs = capturing_client({'id': 'vid-7'})
        with self.assertRaises(mc.MetaError):
            client.upload_ad_video()
        self.assertEqual(reqs, [])


class IdempotentUploadServiceTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='UP Co', slug='up-co')

    def _asset(self, asset_type=CreativeAsset.AssetType.STATIC):
        return CreativeAsset.objects.create(
            company=self.company, asset_type=asset_type,
            file_key='adsengine/1/abc.png', policy_stamp={})

    def test_image_upload_persists_the_hash(self):
        asset = self._asset()
        client, reqs = capturing_client(IMAGE_OK)
        result = cf.upload_asset_to_account(
            self.company, asset, client=client, image_bytes=PNG_BYTES)
        self.assertTrue(result['uploaded'])
        self.assertEqual(result['image_hash'], 'h-abc')
        asset.refresh_from_db()
        self.assertEqual(asset.meta_image_hash, 'h-abc')
        self.assertEqual(asset.meta_video_id, '')
        self.assertEqual(len(reqs), 1)

    def test_second_run_uploads_nothing_at_all(self):
        asset = self._asset()
        client, reqs = capturing_client(IMAGE_OK)
        cf.upload_asset_to_account(
            self.company, asset, client=client, image_bytes=PNG_BYTES)
        result = cf.upload_asset_to_account(
            self.company, asset, client=client, image_bytes=PNG_BYTES)
        self.assertTrue(result['skipped'])
        self.assertFalse(result['uploaded'])
        self.assertEqual(result['image_hash'], 'h-abc')
        self.assertEqual(len(reqs), 1)  # aucun second appel réseau

    def test_video_asset_routes_to_advideos_and_persists_the_id(self):
        asset = self._asset(CreativeAsset.AssetType.REEL)
        client, reqs = capturing_client({'id': 'vid-7'})
        result = cf.upload_asset_to_account(
            self.company, asset, client=client,
            media_url='https://minio/presigned/reel.mp4')
        self.assertTrue(result['uploaded'])
        self.assertEqual(result['video_id'], 'vid-7')
        self.assertIn('act_1/advideos', str(reqs[0].url))
        asset.refresh_from_db()
        self.assertEqual(asset.meta_video_id, 'vid-7')
        self.assertEqual(asset.meta_image_hash, '')

    def test_graph_error_leaves_the_asset_intact_with_a_french_reason(self):
        asset = self._asset()
        client, _ = capturing_client({'error': {'message': 'trop lourd'}},
                                     status_code=400)
        result = cf.upload_asset_to_account(
            self.company, asset, client=client, image_bytes=PNG_BYTES)
        self.assertFalse(result['uploaded'])
        self.assertEqual(result['error'], 'erreur_meta')
        self.assertIn('trop lourd', result['message'])
        asset.refresh_from_db()
        self.assertEqual(asset.meta_image_hash, '')

    def test_response_without_hash_is_an_explicit_failure(self):
        asset = self._asset()
        client, _ = capturing_client({'images': {}})
        result = cf.upload_asset_to_account(
            self.company, asset, client=client, image_bytes=PNG_BYTES)
        self.assertFalse(result['uploaded'])
        self.assertEqual(result['error'], 'sans_hash')
        asset.refresh_from_db()
        self.assertEqual(asset.meta_image_hash, '')

    def test_asset_of_another_company_is_refused(self):
        other = Company.objects.create(nom='OT Co', slug='ot-co')
        asset = self._asset()
        client, reqs = capturing_client(IMAGE_OK)
        result = cf.upload_asset_to_account(
            other, asset, client=client, image_bytes=PNG_BYTES)
        self.assertEqual(result['error'], 'autre_societe')
        self.assertEqual(reqs, [])
