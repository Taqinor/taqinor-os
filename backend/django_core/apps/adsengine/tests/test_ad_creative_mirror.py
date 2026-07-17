"""ADSDEEP11 — Tests du miroir de créatif : peuplé en mock (champs directs ET
object_story_spec), re-sync idempotent (OneToOne), asset_feed_spec incomplet
toléré.
"""
from django.test import TestCase

from authentication.models import Company

from apps.adsengine import sync
from apps.adsengine.models import AdCreativeMirror, MetaConnection
from apps.adsengine.tasks import sync_ad_creatives

CREATIVE_DIRECT = {
    'id': 'cr1', 'body': 'Passez au solaire', 'title': 'Devis gratuit',
    'description': 'Économisez dès le 1er mois', 'call_to_action_type':
    'MESSAGE_PAGE', 'video_id': 'v99', 'instagram_permalink_url':
    'https://instagram.com/p/x', 'effective_object_story_id': '123_456',
}

CREATIVE_OSS = {
    'id': 'cr2',
    'object_story_spec': {
        'page_id': 'p1',
        'link_data': {
            'message': 'Texte via link_data', 'name': 'Titre OSS',
            'description': 'Desc OSS', 'link': 'https://taqinor.ma',
            'image_hash': 'abc123',
            'call_to_action': {'type': 'LEARN_MORE'},
        },
    },
    'asset_feed_spec': {'bodies': [{'text': 'A'}]},  # partiel/incomplet toléré
}


class SyncAdCreativeTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='CR Co', slug='cr')
        self.ad = sync.sync_ads(self.company, [{'id': 'ad1', 'name': 'AD'}])[0]

    def test_direct_fields_mirrored(self):
        sync.sync_ad_creative(self.company, self.ad, CREATIVE_DIRECT)
        m = AdCreativeMirror.objects.get(company=self.company, ad=self.ad)
        self.assertEqual(m.creative_meta_id, 'cr1')
        self.assertEqual(m.body, 'Passez au solaire')
        self.assertEqual(m.title, 'Devis gratuit')
        self.assertEqual(m.cta_type, 'MESSAGE_PAGE')
        self.assertEqual(m.video_id, 'v99')
        self.assertEqual(m.effective_object_story_id, '123_456')
        self.assertIsNotNone(m.fetched_at)

    def test_object_story_spec_fallback(self):
        sync.sync_ad_creative(self.company, self.ad, CREATIVE_OSS)
        m = AdCreativeMirror.objects.get(company=self.company, ad=self.ad)
        self.assertEqual(m.body, 'Texte via link_data')
        self.assertEqual(m.title, 'Titre OSS')
        self.assertEqual(m.link_url, 'https://taqinor.ma')
        self.assertEqual(m.image_hash, 'abc123')
        self.assertEqual(m.cta_type, 'LEARN_MORE')
        self.assertEqual(m.asset_feed_spec, {'bodies': [{'text': 'A'}]})

    def test_resync_idempotent_onetoone(self):
        sync.sync_ad_creative(self.company, self.ad, CREATIVE_DIRECT)
        sync.sync_ad_creative(
            self.company, self.ad, {**CREATIVE_DIRECT, 'body': 'Nouveau texte'})
        self.assertEqual(
            AdCreativeMirror.objects.filter(company=self.company).count(), 1)
        m = AdCreativeMirror.objects.get(company=self.company, ad=self.ad)
        self.assertEqual(m.body, 'Nouveau texte')


class SyncAdCreativesLoopTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='CR2 Co', slug='cr2')
        MetaConnection.objects.create(
            company=self.company, enabled=True,
            credentials={'access_token': 'tok'}, ad_account_id='act_1')
        sync.sync_ads(self.company, [{'id': 'ad1'}, {'id': 'ad2'}])

    def test_loop_mirrors_each_ad(self):
        class FakeClient:
            def get_ad_creative(self, ad_id):
                return {'id': f'cr-{ad_id}', 'body': f'texte {ad_id}'}

        written = sync_ad_creatives(self.company, FakeClient())
        self.assertEqual(written, 2)
        self.assertEqual(
            AdCreativeMirror.objects.filter(company=self.company).count(), 2)

    def test_loop_noop_when_client_lacks_method(self):
        class OldClient:
            pass
        self.assertEqual(sync_ad_creatives(self.company, OldClient()), 0)
