"""PUB33 — Tests de la vigie vélocité d'apprentissage (~50 événements/7 j).

Prouve le détecteur PUR (``detect_learning_velocity``) ET son câblage DB
(``evaluate_learning_velocity``) : un ad set sous le seuil sur des fixtures
``InsightSnapshot`` réelles matérialise une ``EngineAlert`` FR explicative avec
le déficit et une suggestion de consolidation — jamais une action auto.
"""
import datetime

from django.contrib.contenttypes.models import ContentType
from django.test import SimpleTestCase, TestCase

from authentication.models import Company

from apps.adsengine import anomaly
from apps.adsengine.models import (
    AdCampaignMirror, AdSetMirror, EngineAction, EngineAlert, InsightSnapshot,
)
from apps.adsengine.rules import SEVERITY_INFO, SEVERITY_WARNING

TODAY = datetime.date(2026, 7, 19)


class DetectLearningVelocityTests(SimpleTestCase):
    def test_below_threshold_fires_with_deficit(self):
        d = anomaly.detect_learning_velocity([2, 3, 1, 2, 1, 2, 1])  # total=12
        self.assertTrue(d.fired)
        self.assertEqual(d.severity, SEVERITY_WARNING)
        self.assertEqual(d.kind, anomaly.KIND_LEARNING_VELOCITY)
        self.assertIn('12', d.message_fr)
        self.assertIn('38', d.message_fr)  # déficit = 50 - 12
        self.assertIn('consolider', d.message_fr.lower())

    def test_above_threshold_not_flagged(self):
        d = anomaly.detect_learning_velocity([10, 10, 10, 10, 10, 10, 10])
        self.assertFalse(d.fired)
        self.assertFalse(d.insufficient_data)

    def test_exactly_at_threshold_not_flagged(self):
        # 50 pile = seuil atteint, pas de déficit.
        d = anomaly.detect_learning_velocity([10, 10, 10, 10, 10, 0, 0])
        self.assertFalse(d.fired)

    def test_insufficient_history_always_alerts(self):
        d = anomaly.detect_learning_velocity([1, 2], min_samples=3)
        self.assertFalse(d.fired)
        self.assertTrue(d.insufficient_data)
        self.assertEqual(d.severity, SEVERITY_INFO)

    def test_none_values_ignored_not_crashed(self):
        d = anomaly.detect_learning_velocity([None, None, 5, 5, 5])
        # 3 échantillons propres >= min_samples par défaut (3).
        self.assertFalse(d.insufficient_data)
        self.assertEqual(d.computed['samples'], 3)

    def test_custom_threshold_respected(self):
        d = anomaly.detect_learning_velocity(
            [5, 5, 5, 5, 5, 5, 5], min_events_per_week=20)
        self.assertFalse(d.fired)  # 35 >= 20


class EvaluateLearningVelocityEngineTests(TestCase):
    """Câblage DB : lit InsightSnapshot déjà synchronisés, matérialise une
    EngineAlert (recommandation), jamais une EngineAction."""

    def setUp(self):
        self.company = Company.objects.create(nom='LV Co', slug='lv-co')
        self.camp = AdCampaignMirror.objects.create(
            company=self.company, meta_id='c1', name='Camp')
        self.adset = AdSetMirror.objects.create(
            company=self.company, meta_id='as1', name='Starved AdSet',
            campaign=self.camp)
        ct = ContentType.objects.get_for_model(AdSetMirror)
        for i in range(7):
            InsightSnapshot.objects.create(
                company=self.company, content_type=ct, object_id=self.adset.pk,
                date=TODAY - datetime.timedelta(days=i),
                spend='10.00', results=2)

    def test_starved_adset_creates_engine_alert(self):
        detection = anomaly.evaluate_learning_velocity(
            self.company, self.adset, now=TODAY)
        self.assertTrue(detection.fired)
        alert = EngineAlert.objects.get(company=self.company)
        self.assertEqual(alert.alert_type, EngineAlert.Type.ANOMALIE)
        self.assertIn('apprentissage', alert.message.lower())
        self.assertEqual(alert.entity_key, 'learning_velocity:adset:as1')
        # Recommandation seulement — jamais une action.
        self.assertEqual(
            EngineAction.objects.filter(company=self.company).count(), 0)

    def test_healthy_adset_no_alert(self):
        healthy = AdSetMirror.objects.create(
            company=self.company, meta_id='as2', name='Healthy AdSet',
            campaign=self.camp)
        ct = ContentType.objects.get_for_model(AdSetMirror)
        for i in range(7):
            InsightSnapshot.objects.create(
                company=self.company, content_type=ct, object_id=healthy.pk,
                date=TODAY - datetime.timedelta(days=i),
                spend='10.00', results=10)
        detection = anomaly.evaluate_learning_velocity(
            self.company, healthy, now=TODAY)
        self.assertFalse(detection.fired)
        self.assertEqual(EngineAlert.objects.filter(company=self.company).count(), 0)

    def test_dedup_within_cooldown_does_not_duplicate(self):
        anomaly.evaluate_learning_velocity(self.company, self.adset, now=TODAY)
        anomaly.evaluate_learning_velocity(self.company, self.adset, now=TODAY)
        self.assertEqual(
            EngineAlert.objects.filter(company=self.company).count(), 1)

    def test_company_scoped(self):
        other = Company.objects.create(nom='Other LV', slug='other-lv')
        anomaly.evaluate_learning_velocity(self.company, self.adset, now=TODAY)
        self.assertEqual(EngineAlert.objects.filter(company=other).count(), 0)
