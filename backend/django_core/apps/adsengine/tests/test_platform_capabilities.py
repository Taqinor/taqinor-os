"""ADSENG49 — Tests de la matrice de capacités plateforme (données → gardes).

Prouve : la matrice est seedée (Meta paused-par-défaut, budget min, granularité) ;
elle PILOTE la garde — une plateforme sans paused-par-défaut ⇒ forçage PAUSED
requis ; une plateforme inconnue résout sur le défaut prudent (PAUSED forcé).
"""
from django.test import SimpleTestCase

from apps.adsengine.platforms import capabilities as caps
from apps.adsengine.platforms.meta import MetaPlatform


class CapabilityMatrixTests(SimpleTestCase):
    def test_meta_is_paused_by_default(self):
        entry = caps.capabilities_for('meta')
        self.assertTrue(entry['paused_by_default'])
        self.assertEqual(entry['platform'], 'meta')
        self.assertEqual(entry['min_daily_budget_mad'], 10)
        self.assertEqual(entry['insight_granularity'], caps.GRANULARITY_AD)
        self.assertTrue(caps.paused_by_default('meta'))

    def test_matrix_is_data_and_copied(self):
        # Muter la copie ne touche pas la matrice source (données protégées).
        entry = caps.capabilities_for('meta')
        entry['paused_by_default'] = False
        self.assertTrue(caps.paused_by_default('meta'))

    def test_known_platforms_is_meta_only(self):
        # Les plateformes GATED (google/snapchat/tiktok) NE SONT PAS construites.
        self.assertEqual(caps.known_platforms(), ['meta'])


class GuardDrivenByMatrixTests(SimpleTestCase):
    def test_meta_needs_no_extra_forcing(self):
        # Meta force déjà PAUSED → la garde de forçage ne s'impose pas.
        self.assertFalse(caps.requires_forced_paused('meta'))

    def test_unknown_platform_defaults_to_forced_paused(self):
        # Défaut PRUDENT : une plateforme sans paused-par-défaut ⇒ forcer PAUSED.
        entry = caps.capabilities_for('tiktok')
        self.assertFalse(entry['paused_by_default'])
        self.assertEqual(entry['platform'], 'tiktok')
        self.assertTrue(caps.requires_forced_paused('tiktok'))
        self.assertTrue(caps.requires_forced_paused('n_importe_quoi'))

    def test_meta_platform_reads_matrix(self):
        # L'adaptateur Meta (ADSENG48) lit désormais la matrice de capacités.
        class _Stub:
            pass
        platform = MetaPlatform.from_client(_Stub())
        caps_dict = platform.capabilities()
        self.assertEqual(caps_dict['platform'], 'meta')
        self.assertTrue(caps_dict['paused_by_default'])
        self.assertTrue(platform.paused_by_default())
