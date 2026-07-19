"""PUB89 — Tests du score de qualité de la chaîne d'attribution.

Prouve : (1) le cœur pur ``chain_quality`` note la complétude de jointure par
enregistrement + agrège (score/maillon faible), et ``trend`` reste honnête sous
peu de données ; (2) sur fixtures, une dégradation simulée (webhook mort → clid/
téléphone/ad manquants) FAIT CHUTER le score et LÈVE une alerte brake-only.
"""
from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase

from authentication.models import Company
from apps.crm.models import Lead

from apps.adsengine import data_quality
from apps.adsengine.models import (
    AdCampaignMirror, AdMirror, AdSetMirror, CtwaReferral, EngineAlert,
)

User = get_user_model()


class ChainQualityPureTests(SimpleTestCase):
    def test_complete_record_scores_one(self):
        flags = {'clid': True, 'phone_matched': True,
                 'stage_known': True, 'ad_resolved': True}
        self.assertEqual(data_quality.record_completeness(flags), 1.0)

    def test_broken_record_scores_zero(self):
        flags = {'clid': False, 'phone_matched': False,
                 'stage_known': False, 'ad_resolved': False}
        self.assertEqual(data_quality.record_completeness(flags), 0.0)

    def test_aggregate_score_and_weakest_dimension(self):
        records = [
            {'clid': True, 'phone_matched': True, 'stage_known': True,
             'ad_resolved': False},
            {'clid': True, 'phone_matched': False, 'stage_known': True,
             'ad_resolved': False},
        ]
        q = data_quality.chain_quality(records)
        # ad_resolved jamais présent → maillon le plus faible.
        self.assertEqual(q['weakest_dimension'], 'ad_resolved')
        self.assertEqual(q['per_dimension_rate']['ad_resolved'], 0.0)
        self.assertEqual(q['n'], 2)

    def test_no_records_is_insufficient_not_zero(self):
        q = data_quality.chain_quality([])
        self.assertTrue(q['insufficient_data'])
        self.assertIsNone(q['score'])

    def test_trend_insufficient_under_min_samples(self):
        tr = data_quality.trend(0.9, 0.5, recent_n=2, prior_n=10)
        self.assertTrue(tr['insufficient_data'])
        self.assertEqual(tr['direction'], 'inconnue')

    def test_trend_detects_drop(self):
        tr = data_quality.trend(0.5, 0.9, recent_n=10, prior_n=10)
        self.assertEqual(tr['direction'], 'baisse')
        self.assertLess(tr['delta'], 0)


class AttributionQualityModelTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='DQ Co', slug='dq-co')
        camp = AdCampaignMirror.objects.create(
            company=self.company, meta_id='cmp_1', name='Solaire',
            status='PAUSED')
        adset = AdSetMirror.objects.create(
            company=self.company, meta_id='ast_1', name='Toit', campaign=camp)
        AdMirror.objects.create(
            company=self.company, meta_id='ad_100', name='Reel', adset=adset)
        # stage prend son défaut NEW → lead_current_stage résout (stage_known).
        self.lead = Lead.objects.create(company=self.company, nom='Prospect')

    def _good_referral(self, msg_id):
        return CtwaReferral.objects.create(
            company=self.company, wa_message_id=msg_id, ad_id='ad_100',
            ctwa_clid='clid_' + msg_id, phone_key='2126000',
            crm_lead_id=self.lead.pk)

    def _broken_referral(self, msg_id):
        # Webhook dégradé : ni clid, ni téléphone, ni ad résolue, ni lead.
        return CtwaReferral.objects.create(
            company=self.company, wa_message_id=msg_id, ad_id='',
            ctwa_clid='', phone_key='', crm_lead_id=None)

    def test_healthy_chain_scores_high(self):
        for i in range(4):
            self._good_referral(f'ok-{i}')
        q = data_quality.attribution_quality(self.company)
        self.assertEqual(q['score'], 1.0)
        self.assertFalse(q['below_threshold'])

    def test_degradation_drops_score_below_threshold(self):
        self._good_referral('ok-1')
        for i in range(5):
            self._broken_referral(f'bad-{i}')
        q = data_quality.attribution_quality(self.company)
        # 1 complet (1.0) + 5 vides (0.0) sur 6 → ~0.167 < seuil 0.6.
        self.assertLess(q['score'], data_quality.DEFAULT_THRESHOLD)
        self.assertTrue(q['below_threshold'])
        self.assertEqual(q['weakest_dimension'] in
                         data_quality.DEFAULT_DIMENSIONS, True)

    def test_check_raises_brake_only_alert_on_degradation(self):
        for i in range(5):
            self._broken_referral(f'bad-{i}')
        before = EngineAlert.objects.count()
        result = data_quality.check_attribution_quality(self.company)
        self.assertIsNotNone(result['alert_id'])
        self.assertEqual(EngineAlert.objects.count(), before + 1)
        alert = EngineAlert.objects.get(pk=result['alert_id'])
        # Brake-only : anomalie signalée, AUCUNE action liée (jamais de pause auto).
        self.assertEqual(alert.alert_type, EngineAlert.Type.ANOMALIE)
        self.assertIsNone(alert.action)

    def test_healthy_chain_raises_no_alert(self):
        for i in range(4):
            self._good_referral(f'ok-{i}')
        before = EngineAlert.objects.count()
        result = data_quality.check_attribution_quality(self.company)
        self.assertIsNone(result['alert_id'])
        self.assertEqual(EngineAlert.objects.count(), before)
