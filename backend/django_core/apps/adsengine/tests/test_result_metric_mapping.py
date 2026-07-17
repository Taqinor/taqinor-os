"""ADSDEEP6 — Tests : le mapping objectif→métrique « résultats » (CTWA ⇒
conversations, OUTCOME_LEADS ⇒ leads…) est correct ; le dashboard
(cost_per_signature) affiche « conversations » pour une campagne CTWA.
"""
from django.test import SimpleTestCase, TestCase

from authentication.models import Company

from apps.adsengine import sync
from apps.adsengine.metrics import (
    cost_per_signature, result_metric_for_objective,
)


class ResultMetricMappingTests(SimpleTestCase):
    def test_ctwa_maps_to_conversations(self):
        info = result_metric_for_objective('OUTCOME_ENGAGEMENT')
        self.assertEqual(info['metric'], 'conversations')
        self.assertEqual(info['label_fr'], 'conversations')

    def test_leads_maps_to_leads(self):
        info = result_metric_for_objective('OUTCOME_LEADS')
        self.assertEqual(info['metric'], 'leads_count')
        self.assertEqual(info['label_fr'], 'leads')

    def test_unknown_objective_defaults_to_results(self):
        info = result_metric_for_objective('SOMETHING_NEW')
        self.assertEqual(info['metric'], 'results')
        self.assertEqual(info['label_fr'], 'résultats')

    def test_none_objective_safe(self):
        self.assertEqual(
            result_metric_for_objective(None)['label_fr'], 'résultats')

    def test_resolve_results_uses_conversations_for_ctwa(self):
        norm = {'conversations': 6, 'leads_count': 1, 'results': 0}
        self.assertEqual(
            sync.resolve_results('OUTCOME_ENGAGEMENT', norm), 6)

    def test_resolve_results_uses_leads_for_leadgen(self):
        norm = {'conversations': 6, 'leads_count': 4, 'results': 0}
        self.assertEqual(sync.resolve_results('OUTCOME_LEADS', norm), 4)

    def test_resolve_results_falls_back_to_raw_results(self):
        norm = {'results': 9}
        self.assertEqual(
            sync.resolve_results('OUTCOME_ENGAGEMENT', norm), 9)


class DashboardLabelTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='CTWA Co', slug='ctwa')

    def test_dashboard_labels_ctwa_campaign_conversations(self):
        sync.sync_campaigns(self.company, [
            {'id': 'c-ctwa', 'name': 'WA Camp',
             'objective': 'OUTCOME_ENGAGEMENT'},
            {'id': 'c-lead', 'name': 'Lead Camp',
             'objective': 'OUTCOME_LEADS'},
        ])
        rows = {r['campaign_meta_id']: r for r in cost_per_signature(self.company)}
        self.assertEqual(rows['c-ctwa']['result_metric_label'], 'conversations')
        self.assertEqual(rows['c-lead']['result_metric_label'], 'leads')
