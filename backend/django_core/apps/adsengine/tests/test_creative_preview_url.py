"""ADSDEEP15 — Tests : CreativeAssetSerializer expose preview_url (URL signée
MinIO depuis file_key) + is_video (reel/explainer → <video>).
"""
from unittest.mock import patch

from django.test import TestCase

from authentication.models import Company

from apps.adsengine.models import CreativeAsset
from apps.adsengine.serializers import CreativeAssetSerializer


class PreviewUrlTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='PU Co', slug='pu')

    @patch('apps.records.storage.presign_attachment')
    def test_preview_url_from_file_key(self, mock_presign):
        mock_presign.return_value = 'https://minio/signed/key.mp4'
        asset = CreativeAsset.objects.create(
            company=self.company, asset_type=CreativeAsset.AssetType.REEL,
            file_key='company/1/key.mp4')
        data = CreativeAssetSerializer(asset).data
        self.assertEqual(data['preview_url'], 'https://minio/signed/key.mp4')
        mock_presign.assert_called_once_with('company/1/key.mp4')

    def test_preview_url_none_without_file_key(self):
        asset = CreativeAsset.objects.create(
            company=self.company, asset_type=CreativeAsset.AssetType.STATIC,
            file_key='')
        data = CreativeAssetSerializer(asset).data
        self.assertIsNone(data['preview_url'])

    def test_is_video_for_reel_and_explainer(self):
        reel = CreativeAsset.objects.create(
            company=self.company, asset_type=CreativeAsset.AssetType.REEL)
        explainer = CreativeAsset.objects.create(
            company=self.company, asset_type=CreativeAsset.AssetType.EXPLAINER)
        static = CreativeAsset.objects.create(
            company=self.company, asset_type=CreativeAsset.AssetType.STATIC)
        self.assertTrue(CreativeAssetSerializer(reel).data['is_video'])
        self.assertTrue(CreativeAssetSerializer(explainer).data['is_video'])
        self.assertFalse(CreativeAssetSerializer(static).data['is_video'])
