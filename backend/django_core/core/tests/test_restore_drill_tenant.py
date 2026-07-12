"""NTPLT62 — le drill de restauration compare les comptages PAR SOCIÉTÉ."""
from django.test import SimpleTestCase

from core.backup import detecter_ecarts_tenant


class RestoreDrillPerTenantTests(SimpleTestCase):
    def test_no_ecart_when_data_restored(self):
        top_live = {1: 100, 2: 50}
        restored = {1: 98, 2: 50}  # restauré <= live = normal
        comptages, ecarts = detecter_ecarts_tenant(top_live, restored)
        self.assertEqual(ecarts, [])
        self.assertEqual(comptages['1'], {'live': 100, 'restore': 98})

    def test_ecart_when_tenant_lost(self):
        # Société 2 a des données live mais ZÉRO restaurée → écart signalé.
        top_live = {1: 100, 2: 50}
        restored = {1: 100, 2: 0}
        comptages, ecarts = detecter_ecarts_tenant(top_live, restored)
        self.assertEqual(ecarts, [2])
        self.assertEqual(comptages['2'], {'live': 50, 'restore': 0})

    def test_zero_live_is_not_an_ecart(self):
        top_live = {3: 0}
        restored = {3: 0}
        _comptages, ecarts = detecter_ecarts_tenant(top_live, restored)
        self.assertEqual(ecarts, [])
