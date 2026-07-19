"""PUB34 — Tests de la règle de santé structurelle (doctrine Andromeda).

Prouve le détecteur PUR (``detect_structural_fragmentation``) ET son câblage
DB (``evaluate_structural_fragmentation``) : trop d'ad sets actifs et/ou trop
peu de créations par ad set matérialise une ``EngineAlert`` FR avec un plan de
consolidation suggéré — **jamais une action automatique**.
"""
from django.test import SimpleTestCase, TestCase

from authentication.models import Company

from apps.adsengine import anomaly
from apps.adsengine.models import (
    AdCampaignMirror, AdMirror, AdSetMirror, EngineAction, EngineAlert,
)
from apps.adsengine.rules import SEVERITY_INFO, SEVERITY_WARNING


class DetectStructuralFragmentationTests(SimpleTestCase):
    def test_too_many_adsets_flags_attention(self):
        d = anomaly.detect_structural_fragmentation(6, [20, 20, 20, 20, 20, 20])
        self.assertTrue(d.fired)
        self.assertEqual(d.severity, SEVERITY_WARNING)
        self.assertEqual(d.kind, anomaly.KIND_STRUCTURAL_FRAGMENTATION)
        self.assertIn('6 ad sets', d.message_fr)
        self.assertIn('consolidation', d.message_fr.lower())
        self.assertIn('AUCUNE action automatique', d.message_fr)

    def test_starved_creatives_flags_attention(self):
        d = anomaly.detect_structural_fragmentation(2, [3, 5])
        self.assertTrue(d.fired)
        self.assertIn('créations diverses', d.message_fr)

    def test_ideal_structure_not_flagged(self):
        d = anomaly.detect_structural_fragmentation(3, [18, 20, 22])
        self.assertFalse(d.fired)
        self.assertFalse(d.insufficient_data)

    def test_unknown_adset_count_is_insufficient(self):
        d = anomaly.detect_structural_fragmentation(None, [])
        self.assertFalse(d.fired)
        self.assertTrue(d.insufficient_data)
        self.assertEqual(d.severity, SEVERITY_INFO)

    def test_both_signals_combine_in_one_message(self):
        d = anomaly.detect_structural_fragmentation(5, [3, 4, 3])
        self.assertTrue(d.fired)
        self.assertIn('5 ad sets', d.message_fr)
        self.assertIn('créations diverses', d.message_fr)

    def test_zero_active_adsets_not_flagged(self):
        # Campagne synchronisée mais sans ad set actif : pas de fragmentation
        # à signaler (jamais confondu avec « pas de donnée »).
        d = anomaly.detect_structural_fragmentation(0, [])
        self.assertFalse(d.fired)
        self.assertFalse(d.insufficient_data)


class EvaluateStructuralFragmentationEngineTests(TestCase):
    """Câblage DB : lit les miroirs déjà synchronisés (AdSetMirror/AdMirror),
    matérialise une EngineAlert (recommandation), jamais une EngineAction."""

    def setUp(self):
        self.company = Company.objects.create(nom='SF Co', slug='sf-co')
        self.camp = AdCampaignMirror.objects.create(
            company=self.company, meta_id='c1', name='Fragmented Camp')

    def _make_adset(self, meta_id, *, status='ACTIVE', n_ads=3):
        adset = AdSetMirror.objects.create(
            company=self.company, meta_id=meta_id, name=meta_id,
            campaign=self.camp, status=status)
        for i in range(n_ads):
            AdMirror.objects.create(
                company=self.company, meta_id=f'{meta_id}-ad{i}',
                name=f'{meta_id}-ad{i}', adset=adset, status='ACTIVE')
        return adset

    def test_fragmented_campaign_creates_engine_alert(self):
        for i in range(6):
            self._make_adset(f'as{i}', n_ads=2)  # 6 ad sets, 2 créas chacun
        detection = anomaly.evaluate_structural_fragmentation(
            self.company, self.camp)
        self.assertTrue(detection.fired)
        alert = EngineAlert.objects.get(company=self.company)
        self.assertEqual(alert.alert_type, EngineAlert.Type.ANOMALIE)
        self.assertIn('consolidation', alert.message.lower())
        self.assertEqual(
            alert.entity_key, 'structural_fragmentation:campaign:c1')
        # Recommandation seulement — jamais une action.
        self.assertEqual(
            EngineAction.objects.filter(company=self.company).count(), 0)

    def test_healthy_campaign_no_alert(self):
        for i in range(3):
            self._make_adset(f'ok{i}', n_ads=18)
        detection = anomaly.evaluate_structural_fragmentation(
            self.company, self.camp)
        self.assertFalse(detection.fired)
        self.assertEqual(
            EngineAlert.objects.filter(company=self.company).count(), 0)

    def test_paused_adsets_excluded_from_active_count(self):
        for i in range(3):
            self._make_adset(f'ok{i}', n_ads=18)
        for i in range(5):
            self._make_adset(f'paused{i}', status='PAUSED', n_ads=1)
        detection = anomaly.evaluate_structural_fragmentation(
            self.company, self.camp)
        self.assertFalse(detection.fired)
        self.assertEqual(detection.computed['active_adsets'], 3)

    def test_no_synced_adsets_is_insufficient_data(self):
        detection = anomaly.evaluate_structural_fragmentation(
            self.company, self.camp)
        self.assertTrue(detection.insufficient_data)
        self.assertEqual(
            EngineAlert.objects.filter(company=self.company).count(), 0)

    def test_dedup_within_cooldown_does_not_duplicate(self):
        for i in range(6):
            self._make_adset(f'as{i}', n_ads=2)
        anomaly.evaluate_structural_fragmentation(self.company, self.camp)
        anomaly.evaluate_structural_fragmentation(self.company, self.camp)
        self.assertEqual(
            EngineAlert.objects.filter(company=self.company).count(), 1)

    def test_company_scoped(self):
        other = Company.objects.create(nom='Other SF', slug='other-sf')
        for i in range(6):
            self._make_adset(f'as{i}', n_ads=2)
        anomaly.evaluate_structural_fragmentation(self.company, self.camp)
        self.assertEqual(EngineAlert.objects.filter(company=other).count(), 0)
