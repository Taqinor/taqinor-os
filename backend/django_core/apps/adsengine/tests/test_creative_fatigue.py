"""ADSDEEP45 — Tests de la fatigue créative COMBINÉE (fréquence × déclin CTR
[× hausse CPA]), barre Motion (benchmark concurrent §2).

Prouve : le détecteur PUR (``anomaly.detect_creative_fatigue``) applique les
seuils du dossier (CTR −25/35 %, fréquence >4, CPA +40/50 %), sa branche
``insufficient_data`` ALERTE toujours (jamais un skip muet, jamais un déclin
fabriqué à partir d'un CTR de référence absent) ; et le câblage moteur
(``rules_engine.evaluate_creative_fatigue``) matérialise une ``AnomalyEvent``
kind ``creative_fatigue`` + une ``EngineAction`` ROTATE_CREATIVE PROPOSÉE
(jamais auto-appliquée) sur un cas fatigué en fixture.
"""
import datetime

from django.contrib.contenttypes.models import ContentType
from django.test import SimpleTestCase, TestCase

from authentication.models import Company

from apps.adsengine import anomaly, rules_engine
from apps.adsengine.rules import SEVERITY_CRITICAL, SEVERITY_WARNING
from apps.adsengine.models import AdMirror, EngineAction, InsightSnapshot

TODAY = datetime.date(2026, 7, 16)


class DetectCreativeFatigueTests(SimpleTestCase):
    def test_fires_warning_on_frequency_and_ctr_decline(self):
        # Fréquence 4.5 (> seuil 4) + CTR passé de 0.02 à 0.014 (−30 %, dans la
        # bande warning [25 %, 35 %[).
        d = anomaly.detect_creative_fatigue(
            frequency=4.5, ctr_current=0.014, ctr_baseline=0.02,
            recent_samples=5, baseline_samples=10)
        self.assertTrue(d.fired)
        self.assertEqual(d.severity, SEVERITY_WARNING)
        self.assertEqual(d.kind, anomaly.KIND_CREATIVE_FATIGUE)
        self.assertAlmostEqual(d.computed['ctr_decline_pct'], 0.3, places=3)

    def test_escalates_to_critical_on_deep_ctr_decline(self):
        d = anomaly.detect_creative_fatigue(
            frequency=5.0, ctr_current=0.012, ctr_baseline=0.02,
            recent_samples=5, baseline_samples=10)
        self.assertTrue(d.fired)
        self.assertEqual(d.severity, SEVERITY_CRITICAL)  # déclin 40% >= 35%

    def test_cpa_increase_confirms_even_with_mild_ctr_decline(self):
        # CTR décline seulement de 10% (sous le seuil warning 25%) mais le CPA
        # explose de +55% : la confirmation CPA suffit à déclencher.
        d = anomaly.detect_creative_fatigue(
            frequency=4.2, ctr_current=0.018, ctr_baseline=0.02,
            cpa_current=155.0, cpa_baseline=100.0,
            recent_samples=5, baseline_samples=10)
        self.assertTrue(d.fired)
        self.assertEqual(d.severity, SEVERITY_CRITICAL)  # cpa +55% >= 50%

    def test_no_fire_below_frequency_ceiling(self):
        # CTR décline fortement mais la fréquence reste sous le seuil (3.0).
        d = anomaly.detect_creative_fatigue(
            frequency=3.0, ctr_current=0.010, ctr_baseline=0.02,
            recent_samples=5, baseline_samples=10)
        self.assertFalse(d.fired)
        self.assertFalse(d.insufficient_data)

    def test_no_fire_when_ctr_and_cpa_stable(self):
        d = anomaly.detect_creative_fatigue(
            frequency=4.5, ctr_current=0.020, ctr_baseline=0.021,
            cpa_current=100.0, cpa_baseline=98.0,
            recent_samples=5, baseline_samples=10)
        self.assertFalse(d.fired)

    def test_insufficient_data_below_sample_floor(self):
        d = anomaly.detect_creative_fatigue(
            frequency=5.0, ctr_current=0.01, ctr_baseline=0.02,
            recent_samples=1, baseline_samples=10, min_samples=3)
        self.assertFalse(d.fired)
        self.assertTrue(d.insufficient_data)

    def test_insufficient_data_when_baseline_ctr_missing_never_fake_decline(self):
        # Pas de CTR de référence (ad neuve) : jamais un déclin fabriqué.
        d = anomaly.detect_creative_fatigue(
            frequency=5.0, ctr_current=0.01, ctr_baseline=None,
            recent_samples=5, baseline_samples=10)
        self.assertTrue(d.insufficient_data)
        self.assertFalse(d.fired)

    def test_insufficient_data_when_baseline_ctr_zero(self):
        d = anomaly.detect_creative_fatigue(
            frequency=5.0, ctr_current=0.01, ctr_baseline=0.0,
            recent_samples=5, baseline_samples=10)
        self.assertTrue(d.insufficient_data)

    def test_configurable_thresholds_override_defaults(self):
        # Seuil de fréquence relevé à 6 : une fréquence de 4.5 ne suffit plus.
        d = anomaly.detect_creative_fatigue(
            frequency=4.5, ctr_current=0.01, ctr_baseline=0.02,
            recent_samples=5, baseline_samples=10, freq_ceiling=6.0)
        self.assertFalse(d.fired)


class EvaluateCreativeFatigueEngineTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(
            nom='Fatigue Co', slug='fatigue-co')
        self.ad = AdMirror.objects.create(
            company=self.company, meta_id='ad-fat-1', name='Reel v3')
        self.ct = ContentType.objects.get_for_model(AdMirror)

    def _snap(self, day, *, spend, clicks, impressions, results, frequency):
        InsightSnapshot.objects.create(
            company=self.company, content_type=self.ct, object_id=self.ad.pk,
            date=day, spend=spend, clicks=clicks, impressions=impressions,
            results=results, frequency=frequency)

    def _seed_fatigued_ad(self):
        # Fenêtre de référence (14 j avant la fenêtre courte) : bon CTR.
        for i in range(10):
            day = TODAY - datetime.timedelta(days=8 + i)
            self._snap(day, spend='20.00', clicks=40, impressions=2000,
                       results=2, frequency=2.0)
        # Fenêtre courte (7 j) : CTR effondré + fréquence en fuite.
        for i in range(5):
            day = TODAY - datetime.timedelta(days=i)
            self._snap(day, spend='20.00', clicks=10, impressions=2000,
                       results=1, frequency=4.8)

    def test_fires_and_creates_anomaly_and_proposes_rotation(self):
        self._seed_fatigued_ad()
        findings = rules_engine.evaluate_creative_fatigue(
            self.company, now=TODAY)
        self.assertEqual(len(findings), 1)
        entry = findings[0]
        self.assertTrue(entry['fired'])
        self.assertIn('action', entry)
        self.assertEqual(entry['action']['kind'],
                         EngineAction.Kind.ROTATE_CREATIVE)

        from apps.adsengine.models import AnomalyEvent
        anomaly_qs = AnomalyEvent.objects.filter(
            company=self.company, kind=anomaly.KIND_CREATIVE_FATIGUE)
        self.assertEqual(anomaly_qs.count(), 1)

        action = EngineAction.objects.get(pk=entry['action']['id'])
        self.assertEqual(action.status, EngineAction.Statut.PROPOSEE)
        self.assertTrue(action.reason_fr)

    def test_healthy_ad_never_fires(self):
        for i in range(10):
            day = TODAY - datetime.timedelta(days=8 + i)
            self._snap(day, spend='20.00', clicks=40, impressions=2000,
                       results=2, frequency=2.0)
        for i in range(5):
            day = TODAY - datetime.timedelta(days=i)
            self._snap(day, spend='20.00', clicks=38, impressions=2000,
                       results=2, frequency=2.1)
        findings = rules_engine.evaluate_creative_fatigue(
            self.company, now=TODAY)
        self.assertFalse(findings[0]['fired'])
        self.assertFalse(findings[0]['insufficient_data'])

    def test_no_baseline_history_is_insufficient_never_fake_fire(self):
        # Seulement la fenêtre courte, aucune référence.
        for i in range(5):
            day = TODAY - datetime.timedelta(days=i)
            self._snap(day, spend='20.00', clicks=10, impressions=2000,
                       results=1, frequency=4.8)
        findings = rules_engine.evaluate_creative_fatigue(
            self.company, now=TODAY)
        self.assertTrue(findings[0]['insufficient_data'])
        self.assertFalse(findings[0]['fired'])

    def test_configurable_thresholds_passed_through(self):
        self._seed_fatigued_ad()
        findings = rules_engine.evaluate_creative_fatigue(
            self.company, now=TODAY,
            thresholds={'freq_ceiling': 10.0})  # plafond relevé : plus fatigué
        self.assertFalse(findings[0]['fired'])
