"""ADSENG29 — Tests de l'arbitrage DCO.

Prouve : l'exclusion mutuelle DCO ↔ rotation multi-ads (invariant validé au
niveau service, testé dans les deux sens), les plafonds d'assets DCO natifs, et
le choix EXPLICITE de mode par ad set (bootstrap à froid vs rotation avec
signal).
"""
import datetime

from django.contrib.contenttypes.models import ContentType
from django.test import TestCase

from authentication.models import Company
from apps.adsengine import dco
from apps.adsengine.models import (
    AdCampaignMirror, AdSetMirror, InsightSnapshot,
)


class MutualExclusionTests(TestCase):
    def test_dco_conflicts_with_multi_ad_adset(self):
        with self.assertRaises(dco.DcoModeConflict):
            dco.validate_mutual_exclusion(
                mode=dco.MODE_DCO_BOOTSTRAP, existing_ad_count=3)

    def test_multi_ad_conflicts_with_dco_enabled_adset(self):
        with self.assertRaises(dco.DcoModeConflict):
            dco.validate_mutual_exclusion(
                mode=dco.MODE_MULTI_AD_ROTATION, is_dynamic_creative=True)

    def test_dco_ok_on_single_ad_adset(self):
        self.assertEqual(
            dco.validate_mutual_exclusion(
                mode=dco.MODE_DCO_BOOTSTRAP, existing_ad_count=1),
            dco.MODE_DCO_BOOTSTRAP)

    def test_multi_ad_ok_without_dco_flag(self):
        self.assertEqual(
            dco.validate_mutual_exclusion(
                mode=dco.MODE_MULTI_AD_ROTATION, is_dynamic_creative=False),
            dco.MODE_MULTI_AD_ROTATION)

    def test_unknown_mode_rejected(self):
        with self.assertRaises(dco.DcoModeConflict):
            dco.validate_mutual_exclusion(mode='autre')


class AssetCapTests(TestCase):
    def test_within_caps_ok(self):
        spec = {'images': ['a', 'b'], 'bodies': ['x'], 'titles': ['t']}
        self.assertEqual(dco.validate_dco_asset_spec(spec), 4)

    def test_too_many_images_rejected(self):
        with self.assertRaises(dco.DcoCapExceeded):
            dco.validate_dco_asset_spec({'images': list(range(11))})

    def test_total_over_thirty_rejected(self):
        spec = {'images': list(range(10)), 'videos': list(range(10)),
                'bodies': list(range(5)), 'titles': list(range(5)),
                'descriptions': list(range(5))}  # 35 total > 30
        with self.assertRaises(dco.DcoCapExceeded):
            dco.validate_dco_asset_spec(spec)


class ExplicitModePerAdsetTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='Dc Co', slug='dc-co')
        self.camp = AdCampaignMirror.objects.create(
            company=self.company, meta_id='c1')

    def _adset(self, meta_id):
        return AdSetMirror.objects.create(
            company=self.company, meta_id=meta_id, campaign=self.camp)

    def _add_signal(self, adset):
        ct = ContentType.objects.get_for_model(AdSetMirror)
        InsightSnapshot.objects.create(
            company=self.company, content_type=ct, object_id=adset.pk,
            date=datetime.date(2026, 7, 13), spend=50, results=2)

    def test_cold_start_adset_chooses_dco_bootstrap(self):
        cold = self._adset('as-cold')
        decision = dco.plan_adset_creative_mode(cold, existing_ad_count=0)
        self.assertEqual(decision.mode, dco.MODE_DCO_BOOTSTRAP)
        self.assertTrue(decision.is_cold_start)

    def test_signal_adset_chooses_multi_ad_rotation(self):
        warm = self._adset('as-warm')
        self._add_signal(warm)
        decision = dco.plan_adset_creative_mode(warm, existing_ad_count=1)
        self.assertEqual(decision.mode, dco.MODE_MULTI_AD_ROTATION)
        self.assertFalse(decision.is_cold_start)

    def test_dco_requested_on_warm_adset_is_refused(self):
        # DCO = bootstrap ONLY : refusé quand un signal existe déjà.
        warm = self._adset('as-warm2')
        self._add_signal(warm)
        with self.assertRaises(dco.DcoModeConflict):
            dco.plan_adset_creative_mode(
                warm, requested_mode=dco.MODE_DCO_BOOTSTRAP)

    def test_choice_is_explicit_and_differs_per_adset(self):
        cold = self._adset('as-a')
        warm = self._adset('as-b')
        self._add_signal(warm)
        d_cold = dco.plan_adset_creative_mode(cold)
        d_warm = dco.plan_adset_creative_mode(warm, existing_ad_count=1)
        self.assertNotEqual(d_cold.mode, d_warm.mode)
        self.assertEqual(d_cold.adset_ref, cold.pk)
        self.assertEqual(d_warm.adset_ref, warm.pk)
