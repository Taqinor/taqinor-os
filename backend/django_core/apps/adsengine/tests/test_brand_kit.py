"""PUB83 — Kit de marque + vignette choisie.

Prouve : le ``TemplatedAdapter`` lit le kit de marque PERSISTANT (au lieu d'un
payload ad hoc) ; la check-list policy émet un WARNING NON BLOQUANT quand la
vignette d'un reel/explainer est manquante.
"""
from unittest import mock

from django.test import TestCase

from authentication.models import Company

from apps.adsengine import creative_factory, policy
from apps.adsengine.models import BrandKit, CreativeAsset


class BrandKitPayloadTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='Kit Co', slug='kit-co')

    def test_brand_kit_payload_reads_persisted_kit(self):
        BrandKit.objects.create(
            company=self.company, logo_key='logo/abc.png',
            colors={'primary': '#0A6'}, fonts=['Inter'])
        payload = creative_factory.brand_kit_payload(self.company)
        self.assertEqual(payload['logo_key'], 'logo/abc.png')
        self.assertEqual(payload['colors']['primary'], '#0A6')
        self.assertEqual(payload['fonts'], ['Inter'])

    def test_no_kit_returns_empty(self):
        self.assertEqual(
            creative_factory.brand_kit_payload(self.company), {})

    def test_templated_adapter_injects_kit_into_render(self):
        BrandKit.objects.create(
            company=self.company, logo_key='logo/x.png',
            colors={'primary': '#111'})
        adapter = creative_factory.TemplatedAdapter()
        # Sans clé API le run no-ope AVANT l'appel réseau : on patche
        # is_enabled + submit/poll pour observer le payload injecté.
        captured = {}

        def _submit(client, payload):
            captured['input'] = payload.get('input')
            return 'job-1'

        with mock.patch.object(adapter, 'is_enabled', return_value=True), \
                mock.patch.object(adapter, 'submit', side_effect=_submit), \
                mock.patch.object(adapter, 'poll', return_value=b''):
            # poll renvoie b'' → run s'arrête après (aucun asset), mais submit a
            # bien reçu le payload injecté.
            adapter.run(
                self.company, {'input': {'template': 't1'}},
                http_client=object())

        self.assertIn('brand_kit', captured['input'])
        self.assertEqual(
            captured['input']['brand_kit']['logo_key'], 'logo/x.png')
        # Le payload ad hoc d'origine reste présent (fusion, pas remplacement).
        self.assertEqual(captured['input']['template'], 't1')


class ThumbnailChecklistTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='Thumb Co', slug='thumb-co')

    def _asset(self, asset_type, thumbnail_key=''):
        return CreativeAsset.objects.create(
            company=self.company, asset_type=asset_type,
            thumbnail_key=thumbnail_key)

    def test_video_without_thumbnail_warns(self):
        asset = self._asset(CreativeAsset.AssetType.REEL)
        warnings = policy.asset_warnings(asset)
        keys = [w['key'] for w in warnings]
        self.assertIn('thumbnail_missing', keys)

    def test_video_with_thumbnail_no_warning(self):
        asset = self._asset(
            CreativeAsset.AssetType.EXPLAINER, thumbnail_key='thumb/1.png')
        self.assertEqual(policy.asset_warnings(asset), [])

    def test_static_never_warns_on_thumbnail(self):
        asset = self._asset(CreativeAsset.AssetType.STATIC)
        self.assertEqual(policy.asset_warnings(asset), [])

    def test_warning_recorded_but_not_blocking(self):
        asset = self._asset(CreativeAsset.AssetType.REEL)
        forbidden, _ = policy._policy_rules(self.company)
        keys = [r['key'] for r in forbidden]
        policy.record_policy_check(asset, confirmed_keys=keys)
        asset.refresh_from_db()
        # Le warning est consigné MAIS la validation passe (non bloquant).
        self.assertTrue(asset.is_policy_passed)
        self.assertEqual(
            asset.policy_stamp['warnings'][0]['key'], 'thumbnail_missing')
