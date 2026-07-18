"""ADSDEEP38 — Tests du vocabulaire de conditions v2 du Gardien.

Prouve, en DRY-RUN (``dry_run=True`` — rien n'est appliqué ni alerté), que les
sept nouveaux gabarits paramétrés FR évaluent correctement : métriques dérivées
vs seuil (coût/conversation, CTR lien, rétention vidéo 6 s), FENÊTRES COMPARÉES
(« CPA 3 j > CPA 7 j × facteur », surf-scaling à la baisse), et CLASSEMENT top-N
(top dépensiers sans résultat). Chaque évaluation écrit ``last_result`` (jamais
un skip muet) et — en simulation — ne crée AUCUNE action ni alerte.
"""
import datetime

from django.contrib.contenttypes.models import ContentType
from django.test import TestCase

from authentication.models import Company
from apps.adsengine import rules_engine
from apps.adsengine.models import (
    AdCampaignMirror, AdMirror, AdSetMirror, EngineAction, EngineAlert,
    InsightSnapshot, RulePolicy,
)

TODAY = datetime.date(2026, 7, 16)


def _snap(company, target, *, day_offset, **fields):
    ct = ContentType.objects.get_for_model(type(target))
    return InsightSnapshot.objects.create(
        company=company, content_type=ct, object_id=target.pk,
        date=TODAY - datetime.timedelta(days=day_offset), **fields)


def _last(policy):
    policy.refresh_from_db()
    return policy.last_result


def _finding(policy, meta_id):
    for f in _last(policy).get('findings', []):
        if f.get('target') == meta_id:
            return f
    return None


class VocabV2BaseMixin:
    def setUp(self):
        self.company = Company.objects.create(nom='V2 Co', slug='v2-co')

    def _rule(self, template_key, **kw):
        defaults = dict(company=self.company, template_key=template_key,
                        enabled=True, dry_run=True,
                        mode=RulePolicy.Mode.PROPOSE)
        defaults.update(kw)
        return RulePolicy.objects.create(**defaults)

    def _run(self, policy):
        rules_engine.evaluate_company(self.company, now=TODAY)
        return policy

    def _assert_dry_run_no_side_effects(self):
        # Simulation : aucune action ni alerte matérialisée.
        self.assertEqual(
            EngineAction.objects.filter(company=self.company).count(), 0)
        self.assertEqual(
            EngineAlert.objects.filter(company=self.company).count(), 0)


class ThresholdMetricTests(VocabV2BaseMixin, TestCase):
    def test_cost_per_conversation_high_fires_above_threshold(self):
        camp = AdCampaignMirror.objects.create(
            company=self.company, meta_id='c1', name='Camp')
        for i in range(4):
            _snap(self.company, camp, day_offset=i,
                  spend='100.00', conversations=1)
        rule = self._run(self._rule('cost_per_conversation_high'))
        f = _finding(rule, 'c1')
        self.assertTrue(f['fired'])                  # 400/4 = 100 > 50
        self.assertEqual(f['computed']['metric'], 'cost_per_conversation')
        self.assertAlmostEqual(f['computed']['value'], 100.0)
        self._assert_dry_run_no_side_effects()

    def test_cost_per_conversation_not_fired_below_threshold(self):
        camp = AdCampaignMirror.objects.create(
            company=self.company, meta_id='c1', name='Camp')
        for i in range(4):
            _snap(self.company, camp, day_offset=i,
                  spend='10.00', conversations=1)   # 40/4 = 10 < 50
        rule = self._run(self._rule('cost_per_conversation_high'))
        self.assertFalse(_finding(rule, 'c1')['fired'])
        self.assertTrue(_last(rule)['evaluated'])

    def test_link_ctr_low_fires_below_min(self):
        ad = AdMirror.objects.create(
            company=self.company, meta_id='a1', name='Ad')
        for i in range(4):
            _snap(self.company, ad, day_offset=i,
                  impressions=1000, link_clicks=1)   # 4/4000 = 0.001 < 0.005
        rule = self._run(self._rule('link_ctr_low'))
        f = _finding(rule, 'a1')
        self.assertTrue(f['fired'])
        self.assertEqual(f['computed']['operator'], 'lt')

    def test_hold_rate_low_uses_video_6s_metric(self):
        ad = AdMirror.objects.create(
            company=self.company, meta_id='a1', name='Ad')
        for i in range(4):
            _snap(self.company, ad, day_offset=i,
                  impressions=1000, video_metrics={'s6': 100})  # 400/4000 = 0.1
        rule = self._run(self._rule('hold_rate_low'))
        f = _finding(rule, 'a1')
        self.assertTrue(f['fired'])                  # 0.10 < 0.15
        self.assertEqual(f['computed']['metric'], 'hold_rate')

    def test_insufficient_data_when_too_few_samples(self):
        camp = AdCampaignMirror.objects.create(
            company=self.company, meta_id='c1', name='Camp')
        _snap(self.company, camp, day_offset=0, spend='100.00', conversations=1)
        rule = self._run(self._rule('cost_per_conversation_high'))
        f = _finding(rule, 'c1')
        self.assertFalse(f['fired'])
        self.assertTrue(f['insufficient_data'])


class WindowRegressionTests(VocabV2BaseMixin, TestCase):
    def test_cpa_window_regression_fires_when_short_worse(self):
        camp = AdCampaignMirror.objects.create(
            company=self.company, meta_id='c1', name='Camp')
        # 3 jours récents chers (CPL 100), 4 jours plus vieux moins chers (40).
        for i in range(3):
            _snap(self.company, camp, day_offset=i, spend='100.00', results=1)
        for i in range(3, 7):
            _snap(self.company, camp, day_offset=i, spend='40.00', results=1)
        rule = self._run(self._rule('cpa_window_regression'))
        f = _finding(rule, 'c1')
        self.assertTrue(f['fired'])
        # court = 300/3 = 100 ; long = 460/7 ≈ 65.7 ; borne = ×1.2 ≈ 78.9.
        self.assertAlmostEqual(f['computed']['short'], 100.0)
        self.assertGreater(f['computed']['short'], f['computed']['boundary'])

    def test_cpa_window_regression_not_fired_when_stable(self):
        camp = AdCampaignMirror.objects.create(
            company=self.company, meta_id='c1', name='Camp')
        for i in range(7):
            _snap(self.company, camp, day_offset=i, spend='50.00', results=1)
        rule = self._run(self._rule('cpa_window_regression'))
        self.assertFalse(_finding(rule, 'c1')['fired'])

    def test_surf_scale_fires_when_cpl_improving(self):
        adset = AdSetMirror.objects.create(
            company=self.company, meta_id='as1', name='AdSet')
        # 3 jours récents peu chers (CPL 50), 4 vieux plus chers (100).
        for i in range(3):
            _snap(self.company, adset, day_offset=i, spend='50.00', results=1)
        for i in range(3, 7):
            _snap(self.company, adset, day_offset=i, spend='100.00', results=1)
        rule = self._run(self._rule('surf_scale_budget'))
        f = _finding(rule, 'as1')
        self.assertTrue(f['fired'])
        self.assertEqual(f['computed']['direction'], 'down')
        self.assertLess(f['computed']['short'], f['computed']['boundary'])


class RankingTests(VocabV2BaseMixin, TestCase):
    def test_top_spend_low_result_flags_top_spender_without_result(self):
        waste = AdCampaignMirror.objects.create(
            company=self.company, meta_id='waste', name='Waste')
        good = AdCampaignMirror.objects.create(
            company=self.company, meta_id='good', name='Good')
        for i in range(3):
            _snap(self.company, waste, day_offset=i, spend='100.00', results=0)
            _snap(self.company, good, day_offset=i, spend='50.00', results=1)
        rule = self._run(self._rule('top_spend_low_result'))
        self.assertTrue(_finding(rule, 'waste')['fired'])    # top spend, 0 result
        self.assertFalse(_finding(rule, 'good')['fired'])    # has results
        self.assertEqual(_finding(rule, 'waste')['computed']['rank'], 1)
        self._assert_dry_run_no_side_effects()
