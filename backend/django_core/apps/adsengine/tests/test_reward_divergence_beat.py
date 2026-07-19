"""PUB15 — Câblage de la boucle de divergence CRM/proxy (``rewards``) en beat.

Prouve que le beat HEBDO ``adsengine.run_reward_divergence_check`` (resté sans
appelant production) est planifié + routé, et qu'une divergence proxy/CRM sur
fixtures produit une proposition REBALANCE propose-only visible dans Approbations
(``EngineAction`` proposee, jamais appliquée seule).
"""
import datetime
from decimal import Decimal

from django.conf import settings
from django.contrib.contenttypes.models import ContentType
from django.test import SimpleTestCase, TestCase

from authentication.models import Company
from apps.crm.models import Lead
from apps.crm.stages import CONTACTED

from apps.adsengine.models import (
    AdCampaignMirror, AdMirror, AdSetMirror, ArmDailyStat, EngineAction,
    Experiment, ExperimentArm, InsightSnapshot,
)
from apps.adsengine.tasks import run_reward_divergence_check


class BeatRegistrationTests(SimpleTestCase):
    def test_beat_scheduled_and_routed(self):
        from erp_agentique.celery import app
        names = {e['task'] for e in app.conf.beat_schedule.values()}
        self.assertIn('adsengine.run_reward_divergence_check', names)
        route = settings.CELERY_TASK_ROUTES[
            'adsengine.run_reward_divergence_check']
        self.assertEqual(route['queue'], 'scheduled')


class DivergenceBeatTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='RD Co', slug='rd-co')
        self.camp = AdCampaignMirror.objects.create(
            company=self.company, meta_id='cmp', name='Solaire', status='PAUSED')
        self.adset = AdSetMirror.objects.create(
            company=self.company, meta_id='ast', name='Toit', campaign=self.camp)
        self.exp = Experiment.objects.create(
            company=self.company, name='Test hook',
            status=Experiment.Statut.EN_COURS)
        self.ct = ContentType.objects.get_for_model(AdMirror)
        self.today = datetime.date.today()

    def _ad(self, meta_id):
        return AdMirror.objects.create(
            company=self.company, meta_id=meta_id, name=meta_id,
            adset=self.adset)

    def _arm(self, ad, label, impressions, conversions):
        arm = ExperimentArm.objects.create(
            company=self.company, experiment=self.exp, label=label,
            ad_id=ad.meta_id)
        ArmDailyStat.upsert(arm=arm, date=self.today,
                            impressions=impressions, conversations=conversions)
        return arm

    def _spend(self, ad, amount):
        InsightSnapshot.objects.create(
            company=self.company, content_type=self.ct, object_id=ad.pk,
            date=self.today, spend=Decimal(amount), results=1)

    def _qualified_leads(self, ad, count):
        for _ in range(count):
            Lead.objects.create(
                company=self.company, nom='Prospect', stage=CONTACTED,
                meta_ad_id=ad.meta_id, canal=Lead.Canal.META_ADS)

    def _build_divergent(self):
        # Proxy A>B>C ; coût CRM C<B<A (inversion de 2 positions).
        ad_a, ad_b, ad_c = self._ad('ad_A'), self._ad('ad_B'), self._ad('ad_C')
        self._arm(ad_a, 'A', 1000, 40)
        self._arm(ad_b, 'B', 1000, 30)
        self._arm(ad_c, 'C', 1000, 20)
        for ad in (ad_a, ad_b, ad_c):
            self._spend(ad, '100.00')
        self._qualified_leads(ad_a, 2)
        self._qualified_leads(ad_b, 4)
        self._qualified_leads(ad_c, 6)

    def test_beat_proposes_rebalance_on_divergence(self):
        self._build_divergent()
        result = run_reward_divergence_check()
        self.assertEqual(result['rebalance_proposed'], 1)
        # Une proposition REBALANCE visible dans Approbations (proposee, non-auto).
        action = EngineAction.objects.get(
            company=self.company,
            kind=EngineAction.Kind.REBALANCE_BUDGET)
        self.assertEqual(action.status, EngineAction.Statut.PROPOSEE)
        self.assertFalse(action.auto)
        self.assertTrue(action.reason_fr.strip())
        # Jamais une action auto-appliquée.
        self.assertFalse(
            EngineAction.objects.filter(
                company=self.company, auto=True).exists())

    def test_beat_noop_without_arms(self):
        result = run_reward_divergence_check()
        self.assertEqual(result['rebalance_proposed'], 0)
        self.assertEqual(EngineAction.objects.count(), 0)
