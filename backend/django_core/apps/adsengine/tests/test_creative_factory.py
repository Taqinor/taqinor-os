"""ENG17 — Tests de la fabrique créative key-gated (mocked, aucun réseau).

Prouve : sans clé, chaque adaptateur no-ope (aucun asset) ; avec clé (mockée),
submit→poll→store crée un ``CreativeAsset`` en stamp policy PENDING (jamais
validé automatiquement), avec la bonne ``source_lane``.
"""
import os
from unittest.mock import Mock, patch

from django.test import TestCase

from authentication.models import Company

from apps.adsengine import creative_factory as cf
from apps.adsengine.models import CreativeAsset

ALL_ENV_KEYS = [c.env_key for c in cf.ADAPTERS.values()]


class NoKeyNoOpTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='NF Co', slug='nf-co')

    def test_every_adapter_noops_without_key(self):
        with patch.dict(os.environ, {}, clear=False):
            for key in ALL_ENV_KEYS:
                os.environ.pop(key, None)
            for name, cls in cf.ADAPTERS.items():
                adapter = cls()
                self.assertFalse(adapter.is_enabled(), name)
                result = adapter.run(self.company, {}, http_client=Mock())
                self.assertIsNone(result, name)
        self.assertEqual(CreativeAsset.objects.count(), 0)

    def test_enabled_adapters_lists_only_keyed(self):
        with patch.dict(os.environ, {}, clear=False):
            for key in ALL_ENV_KEYS:
                os.environ.pop(key, None)
            os.environ['FAL_API_KEY'] = 'k-73951'
            self.assertEqual(cf.enabled_adapters(), ['fal'])


class AdapterRunTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='AF Co', slug='af-co')

    def _run_adapter(self, name, cls):
        adapter = cls()
        with patch.dict(os.environ, {adapter.env_key: 'k-73951'}, clear=False):
            with patch.object(adapter, 'submit', return_value='job1'), \
                 patch.object(adapter, 'poll', return_value=b'MEDIA-BYTES'), \
                 patch('apps.adsengine.creative_factory._store_bytes',
                       return_value=f'adsengine/1/{name}.bin') as mock_store:
                asset = adapter.run(
                    self.company, {'cost_cents': 250}, http_client=Mock())
        self.assertIsNotNone(asset, name)
        mock_store.assert_called_once()
        return asset

    def test_each_adapter_creates_pending_asset(self):
        for name, cls in cf.ADAPTERS.items():
            asset = self._run_adapter(name, cls)
            self.assertEqual(asset.source_lane, name)
            self.assertEqual(asset.cost_cents, 250)
            # Stamp PENDING : jamais validé automatiquement.
            self.assertEqual(asset.policy_stamp, {})
            self.assertFalse(asset.is_policy_passed)

    def test_poll_returning_nothing_creates_no_asset(self):
        adapter = cf.FalAdapter()
        with patch.dict(os.environ, {'FAL_API_KEY': 'k'}, clear=False):
            with patch.object(adapter, 'submit', return_value='job1'), \
                 patch.object(adapter, 'poll', return_value=None):
                asset = adapter.run(self.company, {}, http_client=Mock())
        self.assertIsNone(asset)
