"""ENG18 — Tests de la tâche « variantes » (mocked, aucun réseau).

Prouve : 2-3 variantes statiques d'un asset de base APPROUVÉ, chacune liée au
parent + en policy PENDING ; no-op si l'asset n'est pas validé ou si aucun
adaptateur statique n'a de clé ; la tâche Celery délègue à la fabrique.
"""
import os
from unittest.mock import Mock, patch

from django.test import TestCase

from authentication.models import Company

from apps.adsengine import creative_factory as cf
from apps.adsengine.models import CreativeAsset
from apps.adsengine.tasks import generate_creative_variants


class GenerateVariantsTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='V Co', slug='v-co')
        self.base = CreativeAsset.objects.create(
            company=self.company, asset_type=CreativeAsset.AssetType.STATIC,
            policy_stamp={'passed': True, 'rules_checked': [],
                          'checked_at': 'x', 'checked_by': 1})

    def test_generates_linked_pending_variants(self):
        adapter = cf.FalAdapter()
        with patch.dict(os.environ, {'FAL_API_KEY': 'k'}, clear=False):
            with patch.object(cf, '_first_enabled_static_adapter',
                              return_value=adapter), \
                 patch.object(adapter, 'submit', return_value='job'), \
                 patch.object(adapter, 'poll', return_value=b'IMG'), \
                 patch('apps.adsengine.creative_factory._store_bytes',
                       return_value='adsengine/1/v.png'):
                variants = cf.generate_variants(
                    self.base, brand_fields={'logo': 'x'}, count=3,
                    http_client=Mock())
        self.assertEqual(len(variants), 3)
        for v in variants:
            self.assertEqual(v.parent_id, self.base.id)
            self.assertEqual(v.source_lane, 'fal')
            self.assertFalse(v.is_policy_passed)  # PENDING

    def test_noop_when_base_not_approved(self):
        base = CreativeAsset.objects.create(
            company=self.company, asset_type=CreativeAsset.AssetType.STATIC)
        self.assertFalse(base.is_policy_passed)
        variants = cf.generate_variants(base, count=2, http_client=Mock())
        self.assertEqual(variants, [])

    def test_noop_when_no_static_adapter_keyed(self):
        with patch.object(cf, '_first_enabled_static_adapter',
                          return_value=None):
            variants = cf.generate_variants(self.base, count=2)
        self.assertEqual(variants, [])


class GenerateVariantsTaskTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='VT Co', slug='vt-co')
        self.base = CreativeAsset.objects.create(
            company=self.company, asset_type=CreativeAsset.AssetType.STATIC,
            policy_stamp={'passed': True})

    def test_task_delegates_to_factory(self):
        fake_variants = [Mock(), Mock()]
        with patch('apps.adsengine.creative_factory.generate_variants',
                   return_value=fake_variants) as mock_gen:
            result = generate_creative_variants(self.base.id, count=2)
        mock_gen.assert_called_once()
        self.assertEqual(result, {'variants_created': 2})

    def test_task_noop_when_asset_missing(self):
        result = generate_creative_variants(999999)
        self.assertEqual(result, {'variants_created': 0})
