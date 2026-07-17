"""ADSENG52 — Tests de contrat de l'adaptateur TikTok (STUB, rien d'activé).

Prouve : le stub satisfait le contrat ``AdsPlatform`` ; il n'active RIEN ; il
reste GATED (hors matrice ADSENG49) ; ET — le test EXIGÉ par la tâche — la
« création sans PAUSED forcé est impossible » (garde ADSENG49 : TikTok n'est pas
paused-par-défaut, donc le forçage PAUSED est structurel).
"""
from django.test import SimpleTestCase

from apps.adsengine.platforms import capabilities as caps
from apps.adsengine.platforms.base import AdsPlatform
from apps.adsengine.platforms.tiktok import (
    PlatformNotEnabledError, TikTokPlatform,
)


class TikTokStubContractTests(SimpleTestCase):
    def setUp(self):
        self.platform = TikTokPlatform()

    def test_is_an_adsplatform(self):
        self.assertIsInstance(self.platform, AdsPlatform)
        self.assertEqual(self.platform.name, 'tiktok')

    def test_stays_gated_out_of_capability_matrix(self):
        self.assertNotIn('tiktok', caps.known_platforms())
        entry = self.platform.capabilities()
        self.assertEqual(entry['platform'], 'tiktok')
        self.assertFalse(entry['paused_by_default'])

    def test_every_operation_is_gated_no_spend(self):
        for call in (
            lambda: self.platform.get_campaigns(),
            lambda: self.platform.get_adsets(),
            lambda: self.platform.get_ads(),
            lambda: self.platform.get_insights('x'),
            lambda: self.platform.create_campaign(name='C', objective='REACH'),
            lambda: self.platform.create_adset(name='A', campaign_id='1'),
            lambda: self.platform.create_ad(name='Ad', adset_id='1'),
            lambda: self.platform.update_status_paused(object_id='1'),
        ):
            with self.assertRaises(PlatformNotEnabledError):
                call()

    def test_no_activation_method_exists(self):
        for forbidden in (
            'activate', 'unpause', 'resume', 'enable', 'set_active',
            'set_status', 'go_live', 'update_status_active',
        ):
            self.assertFalse(
                hasattr(self.platform, forbidden),
                f'Aucune méthode « {forbidden} » ne doit exister (invariant #3).')

    # ── LE test exigé par ADSENG52 : PAUSED forcé, impossible à contourner ────
    def test_creation_without_forced_paused_is_impossible(self):
        # 1. La garde ADSENG49 (données) est active pour TikTok : pas de
        #    paused-par-défaut ⇒ forçage PAUSED requis côté client.
        self.assertFalse(caps.paused_by_default('tiktok'))
        self.assertTrue(caps.requires_forced_paused('tiktok'))
        self.assertFalse(self.platform.paused_by_default())

        # 2. Le SEUL statut qu'une création peut porter est PAUSED (en dur).
        self.assertEqual(self.platform.forced_status, 'PAUSED')
        self.assertEqual(self.platform._forced_create_status(), 'PAUSED')

        # 3. Aucune signature de création n'accepte un ``status`` : impossible de
        #    glisser un ACTIVE (le langage lève ``TypeError``).
        with self.assertRaises(TypeError):
            self.platform.create_campaign(
                name='C', objective='REACH', status='ACTIVE')
        with self.assertRaises(TypeError):
            self.platform.create_adset(
                name='A', campaign_id='1', status='ACTIVE')
        with self.assertRaises(TypeError):
            self.platform.create_ad(name='Ad', adset_id='1', status='ACTIVE')

        # 4. Et de toute façon, toute création est gated (aucune dépense) : il
        #    n'existe donc AUCUN chemin qui crée quoi que ce soit en non-PAUSED.
        with self.assertRaises(PlatformNotEnabledError):
            self.platform.create_campaign(name='C', objective='REACH')
