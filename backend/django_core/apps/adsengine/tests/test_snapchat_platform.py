"""ADSENG51 — Tests de contrat de l'adaptateur Snapchat (STUB, rien d'activé).

Prouve : le stub satisfait le contrat ``AdsPlatform`` ; il n'active RIEN ;
l'invariant #3 survit (aucun ``status`` de création, aucune méthode d'activation) ;
la plateforme reste GATED (absente de la matrice ADSENG49).
"""
from django.test import SimpleTestCase

from apps.adsengine.platforms import capabilities as caps
from apps.adsengine.platforms.base import AdsPlatform
from apps.adsengine.platforms.snapchat import (
    PlatformNotEnabledError, SnapchatPlatform,
)


class SnapchatStubContractTests(SimpleTestCase):
    def setUp(self):
        self.platform = SnapchatPlatform()

    def test_is_an_adsplatform(self):
        self.assertIsInstance(self.platform, AdsPlatform)
        self.assertEqual(self.platform.name, 'snapchat')

    def test_stays_gated_out_of_capability_matrix(self):
        self.assertNotIn('snapchat', caps.known_platforms())
        entry = self.platform.capabilities()
        self.assertEqual(entry['platform'], 'snapchat')
        self.assertFalse(entry['paused_by_default'])

    def test_every_operation_is_gated_no_spend(self):
        for call in (
            lambda: self.platform.get_campaigns(),
            lambda: self.platform.get_adsets(),
            lambda: self.platform.get_ads(),
            lambda: self.platform.get_insights('x'),
            lambda: self.platform.create_campaign(name='C', objective='STORY'),
            lambda: self.platform.create_adset(name='A', campaign_id='1'),
            lambda: self.platform.create_ad(name='Ad', adset_id='1'),
            lambda: self.platform.update_status_paused(object_id='1'),
        ):
            with self.assertRaises(PlatformNotEnabledError):
                call()

    def test_no_create_path_accepts_status(self):
        with self.assertRaises(TypeError):
            self.platform.create_campaign(
                name='C', objective='STORY', status='ACTIVE')
        with self.assertRaises(TypeError):
            self.platform.create_adset(
                name='A', campaign_id='1', status='ACTIVE')
        with self.assertRaises(TypeError):
            self.platform.create_ad(name='Ad', adset_id='1', status='ACTIVE')

    def test_no_activation_method_exists(self):
        for forbidden in (
            'activate', 'unpause', 'resume', 'enable', 'set_active',
            'set_status', 'go_live', 'update_status_active',
        ):
            self.assertFalse(
                hasattr(self.platform, forbidden),
                f'Aucune méthode « {forbidden} » ne doit exister (invariant #3).')

    def test_forced_create_status_is_paused(self):
        self.assertEqual(self.platform.forced_status, 'PAUSED')
        self.assertEqual(self.platform._forced_create_status(), 'PAUSED')
