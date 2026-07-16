"""ADSENG16 — Tests des 5 détecteurs d'anomalies SMB-relatifs (dd-guardian §b).

Prouve chaque formule (pic/chute de dépense, bande CPL ±2×, zéro-delivery 2
niveaux, fréquence en fuite + pente, ad refusée) ET sa branche
``insufficient_data`` (qui ALERTE toujours — info — jamais un skip muet). Plus
le câblage moteur de la bande CPL (matérialise une ``AnomalyEvent`` + alerte,
aucune action puisque template alerte-seule).
"""
import datetime

from django.contrib.contenttypes.models import ContentType
from django.test import SimpleTestCase, TestCase

from authentication.models import Company
from apps.adsengine import anomaly, rules_engine
from apps.adsengine.rules import (
    SEVERITY_CRITICAL, SEVERITY_INFO, SEVERITY_WARNING,
)
from apps.adsengine.models import (
    AdCampaignMirror, AnomalyEvent, EngineAction, EngineAlert, InsightSnapshot,
    RulePolicy,
)

TODAY = datetime.date(2026, 7, 16)


class SpendAnomalyTests(SimpleTestCase):
    def test_spike_flags_warning(self):
        d = anomaly.detect_spend_anomaly([10, 10, 10, 10, 10, 10, 10], 100)
        self.assertTrue(d.fired)
        self.assertEqual(d.severity, SEVERITY_WARNING)
        self.assertEqual(d.kind, anomaly.KIND_COST_SPIKE)

    def test_collapse_flags_critical(self):
        d = anomaly.detect_spend_anomaly([100, 100, 100, 100, 100, 100, 100], 5)
        self.assertTrue(d.fired)
        self.assertEqual(d.severity, SEVERITY_CRITICAL)

    def test_floor_suppresses_meaningless_spike(self):
        # 1 MAD → 4 MAD est un « 4× » sous le plancher : jamais déclenché.
        d = anomaly.detect_spend_anomaly([1, 1, 1, 1, 1, 1, 1], 4)
        self.assertFalse(d.fired)

    def test_insufficient_history_always_alerts(self):
        d = anomaly.detect_spend_anomaly([10, 10], 100, min_samples=3)
        self.assertFalse(d.fired)
        self.assertTrue(d.insufficient_data)
        self.assertEqual(d.severity, SEVERITY_INFO)

    def test_stable_spend_not_flagged(self):
        d = anomaly.detect_spend_anomaly([10, 10, 10, 10, 10, 10, 10], 15)
        self.assertFalse(d.fired)
        self.assertFalse(d.insufficient_data)


class CplBandTests(SimpleTestCase):
    def test_above_band_flags(self):
        d = anomaly.detect_cpl_band([100, 100, 100, 100, 100], 300, n_leads=10)
        self.assertTrue(d.fired)
        self.assertEqual(d.computed['band_high'], 200.0)

    def test_below_band_flags(self):
        d = anomaly.detect_cpl_band([100, 100, 100, 100, 100], 20, n_leads=10)
        self.assertTrue(d.fired)

    def test_within_band_not_flagged(self):
        d = anomaly.detect_cpl_band([100, 100, 100, 100, 100], 120, n_leads=10)
        self.assertFalse(d.fired)

    def test_too_few_leads_always_alerts(self):
        d = anomaly.detect_cpl_band([100, 100], 300, n_leads=2, min_samples=5)
        self.assertFalse(d.fired)
        self.assertTrue(d.insufficient_data)
        self.assertEqual(d.severity, SEVERITY_INFO)


class ZeroDeliveryTests(SimpleTestCase):
    def test_tier1_spend_no_impressions_is_critical(self):
        d = anomaly.detect_zero_delivery(
            spend=50, impressions=0, clicks=0, leads=0, hours_since_launch=48)
        self.assertTrue(d.fired)
        self.assertEqual(d.severity, SEVERITY_CRITICAL)
        self.assertEqual(d.kind, anomaly.KIND_ZERO_DELIVERY)

    def test_tier2_clicks_no_leads_is_warning(self):
        d = anomaly.detect_zero_delivery(
            spend=50, impressions=1000, clicks=20, leads=0,
            hours_since_launch=48)
        self.assertTrue(d.fired)
        self.assertEqual(d.severity, SEVERITY_WARNING)
        self.assertEqual(d.kind, anomaly.KIND_ZERO_RESULTS)

    def test_new_campaign_under_24h_not_tier2(self):
        d = anomaly.detect_zero_delivery(
            spend=50, impressions=1000, clicks=20, leads=0,
            hours_since_launch=6)
        self.assertFalse(d.fired)

    def test_unknown_impressions_always_alerts(self):
        d = anomaly.detect_zero_delivery(
            spend=50, impressions=None, clicks=None, leads=0,
            hours_since_launch=48)
        self.assertFalse(d.fired)
        self.assertTrue(d.insufficient_data)
        self.assertEqual(d.severity, SEVERITY_INFO)

    def test_healthy_delivery_not_flagged(self):
        d = anomaly.detect_zero_delivery(
            spend=50, impressions=1000, clicks=20, leads=5,
            hours_since_launch=48)
        self.assertFalse(d.fired)


class FrequencyRunawayTests(SimpleTestCase):
    def test_over_ceiling_flags(self):
        d = anomaly.detect_frequency_runaway([2.0, 2.5, 3.5])
        self.assertTrue(d.fired)
        self.assertEqual(d.kind, anomaly.KIND_FREQUENCY_HIGH)

    def test_climbing_below_ceiling_early_warning(self):
        # Encore sous le plafond (3,0) mais au-dessus de 70 % ET en hausse.
        d = anomaly.detect_frequency_runaway(
            [2.1, 2.2, 2.3], freq_ceiling=3.0)
        self.assertTrue(d.fired)
        self.assertTrue(d.computed['climbing'])

    def test_stable_low_not_flagged(self):
        d = anomaly.detect_frequency_runaway([1.0, 1.0, 1.0])
        self.assertFalse(d.fired)

    def test_insufficient_series_always_alerts(self):
        d = anomaly.detect_frequency_runaway([3.5], min_samples=3)
        self.assertFalse(d.fired)
        self.assertTrue(d.insufficient_data)
        self.assertEqual(d.severity, SEVERITY_INFO)


class DisapprovedTests(SimpleTestCase):
    def test_disapproved_status_flags_critical(self):
        d = anomaly.detect_disapproved('DISAPPROVED', rejection_reason='Texte')
        self.assertTrue(d.fired)
        self.assertEqual(d.severity, SEVERITY_CRITICAL)
        self.assertIn('Texte', d.message_fr)

    def test_with_issues_flags(self):
        self.assertTrue(anomaly.detect_disapproved('WITH_ISSUES').fired)

    def test_active_not_flagged(self):
        self.assertFalse(anomaly.detect_disapproved('ACTIVE').fired)

    def test_unknown_status_always_alerts(self):
        d = anomaly.detect_disapproved('')
        self.assertFalse(d.fired)
        self.assertTrue(d.insufficient_data)
        self.assertEqual(d.severity, SEVERITY_INFO)


class CplBandEngineWiringTests(TestCase):
    """Le détecteur bande CPL est CÂBLÉ dans le moteur : un dépassement de bande
    matérialise une ``AnomalyEvent`` + une alerte, sans action (alerte-seule)."""

    def setUp(self):
        self.company = Company.objects.create(nom='CB Co', slug='cb-co')
        self.camp = AdCampaignMirror.objects.create(
            company=self.company, meta_id='c1', name='C', status='PAUSED')
        ct = ContentType.objects.get_for_model(AdCampaignMirror)
        # 6 jours trainants à CPL 100 (avec ≥1 lead), aujourd'hui à CPL 300.
        for i in range(1, 7):
            InsightSnapshot.objects.create(
                company=self.company, content_type=ct, object_id=self.camp.pk,
                date=TODAY - datetime.timedelta(days=i),
                spend='50.00', results=1, cpl='100.00')
        InsightSnapshot.objects.create(
            company=self.company, content_type=ct, object_id=self.camp.pk,
            date=TODAY, spend='50.00', results=1, cpl='300.00')

    def test_out_of_band_records_anomaly_and_alerts_no_action(self):
        RulePolicy.objects.create(
            company=self.company, template_key='cpl_band', enabled=True,
            dry_run=False, mode=RulePolicy.Mode.PROPOSE)
        rules_engine.evaluate_company(self.company, now=TODAY)
        self.assertEqual(
            AnomalyEvent.objects.filter(company=self.company).count(), 1)
        anomaly_row = AnomalyEvent.objects.get(company=self.company)
        self.assertEqual(anomaly_row.entity_meta_id, 'c1')
        self.assertEqual(anomaly_row.kind, anomaly.KIND_COST_SPIKE)
        self.assertTrue(EngineAlert.objects.filter(
            company=self.company).exists())
        # Template alerte-seule : jamais d'EngineAction.
        self.assertEqual(
            EngineAction.objects.filter(company=self.company).count(), 0)
